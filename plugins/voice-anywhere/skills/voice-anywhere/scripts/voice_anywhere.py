"""Voice Anywhere: local push-to-talk dictation for any app on Windows.

Hold the talk key (default: Right Ctrl), speak, and let go. Your words are
transcribed on this machine (offline, with faster-whisper) and pasted wherever
your cursor is: Teams, WhatsApp, Outlook, a browser, an AI chat, a terminal.

Optional read-aloud: select any text and press Ctrl+Alt+R to hear it.

Run `python voice_anywhere.py --help` for all options.
"""
from __future__ import annotations

import argparse
import os
import queue
import re
import sys
import tempfile
import threading
import time

__version__ = "0.1.0"
SAMPLE_RATE = 16000


# ---------------------------------------------------------------------------
# Pure helpers (no audio or keyboard needed; covered by tests)
# ---------------------------------------------------------------------------

def default_threads() -> int:
    """Half the logical cores, capped at 8. More threads were slower in testing."""
    return max(1, min(8, (os.cpu_count() or 2) // 2))


def build_parser() -> argparse.ArgumentParser:
    p = argparse.ArgumentParser(
        prog="voice-anywhere",
        description="Hold a key, speak, release: your words are typed wherever your cursor is. "
                    "Transcription runs locally; audio never leaves your machine.",
    )
    p.add_argument("--key", default="right ctrl",
                   help="key to hold while talking (default: 'right ctrl'; e.g. 'f9', 'right alt', 'scroll lock')")
    p.add_argument("--model", default="base",
                   help="Whisper model: tiny, base, small, medium, large-v3 (default: base; bigger = more accurate, slower)")
    p.add_argument("--language", default=None,
                   help="language code such as en, de, nl, fr (default: auto-detect)")
    p.add_argument("--vocab", default="",
                   help="names and jargon to help recognition, e.g. \"Avanade, Copilot, Fabric\"")
    p.add_argument("--threads", type=int, default=default_threads(),
                   help=f"CPU threads for transcription (default: {default_threads()} on this machine)")
    p.add_argument("--device", default="cpu", choices=["cpu", "cuda", "auto"],
                   help="cpu (default), or cuda if you have an NVIDIA GPU with CUDA libraries")
    p.add_argument("--mic", default=None,
                   help="microphone name or index (default: system default; see --list-mics)")
    p.add_argument("--type", dest="type_text", action="store_true",
                   help="type the text key by key instead of pasting (for apps that block paste)")
    p.add_argument("--restore-clipboard", action="store_true",
                   help="put your previous clipboard back after pasting (default: transcript stays on clipboard)")
    p.add_argument("--auto-send", action="store_true",
                   help="press Enter after pasting (sends chat messages immediately; off by default)")
    p.add_argument("--no-beep", action="store_true", help="no start/stop chimes")
    p.add_argument("--chime-volume", type=float, default=0.35, help="chime loudness 0..1 (default: 0.35)")
    p.add_argument("--overlay", default="bottom", choices=["bottom", "cursor", "off"],
                   help="big glowing knot while you talk: bottom-centre of the screen (default), "
                        "next to the mouse pointer, or off")
    p.add_argument("--overlay-size", type=int, default=260, help="size of the big knot in pixels (default: 260)")
    p.add_argument("--read-key", default="ctrl+alt+r", help="read selected text aloud (default: ctrl+alt+r)")
    p.add_argument("--stop-key", default="ctrl+alt+s", help="stop reading aloud (default: ctrl+alt+s)")
    p.add_argument("--quit-key", default="ctrl+alt+q", help="quit (default: ctrl+alt+q)")
    p.add_argument("--no-read", action="store_true", help="disable the read-aloud hotkeys")
    p.add_argument("--no-tray", action="store_true", help="no system-tray icon")
    p.add_argument("--background", action="store_true",
                   help="always-on mode for sign-in: no window needed, log to file, one instance only, "
                        "restart automatically after errors; the knot appears briefly when ready")
    p.add_argument("--log", default=None,
                   help="log file (default in --background: %%LOCALAPPDATA%%\\voice-anywhere\\voice-anywhere.log)")
    p.add_argument("--list-mics", action="store_true", help="list microphones and exit")
    p.add_argument("--self-test", action="store_true",
                   help="check the install without a microphone: synthesise a sentence, transcribe it, report speed")
    p.add_argument("--version", action="version", version=f"%(prog)s {__version__}")
    return p


def clean_for_speech(text: str) -> str:
    """Strip Markdown and URLs so read-aloud sounds natural."""
    text = re.sub(r"```.*?```", " (code block skipped) ", text, flags=re.S)
    text = re.sub(r"!\[[^\]]*\]\([^)]*\)", "", text)
    text = re.sub(r"\[([^\]]+)\]\([^)]*\)", r"\1", text)
    text = re.sub(r"https?://\S+", "link", text)
    text = re.sub(r"^\s*(?:[-*\u2022]|\d+\.)\s+", "", text, flags=re.M)
    text = re.sub(r"[`*_#>|~]", "", text)
    return re.sub(r"\s+", " ", text).strip()


def join_segments(segments) -> str:
    return " ".join(s.text.strip() for s in segments if s.text.strip()).strip()


def word_overlap(expected: str, actual: str) -> float:
    """Share of expected words found in actual (case- and punctuation-insensitive)."""
    norm = lambda s: re.findall(r"[a-z0-9']+", s.lower())
    exp, act = norm(expected), set(norm(actual))
    return sum(w in act for w in exp) / len(exp) if exp else 0.0


# Tray tooltips per state
STATES = {
    "loading": "Voice Anywhere: starting...",
    "ready": "Voice Anywhere: on - hold {key} to talk",
    "recording": "Voice Anywhere: listening...",
    "transcribing": "Voice Anywhere: transcribing...",
    "paused": "Voice Anywhere: paused",
}


def tray_tooltip(state: str, key: str) -> str:
    return STATES[state].format(key=key.upper())[:127]  # Windows tooltip limit


def voice_level(rms: float) -> float:
    """Map microphone RMS (0..1) to a 0..1 glow level; normal speech lands around 0.4-0.9."""
    import math
    if rms <= 1e-5:
        return 0.0
    db = 20 * math.log10(rms)          # quiet room ~ -60 dB, speech ~ -30..-15 dB
    return max(0.0, min(1.0, (db + 50) / 35))


CHIME_RATE = 48000


def make_chime(freqs, volume=0.35, note=0.09, gap=0.03, lead=0.15, rate=CHIME_RATE):
    """A soft bell-like run of notes as float32 samples. `lead` is silence up front so
    Bluetooth headsets that wake their audio link on demand don't swallow the start."""
    import numpy as np
    parts = [np.zeros(int(lead * rate), dtype=np.float32)]
    for f in freqs:
        t = np.arange(int(note * rate)) / rate
        env = np.minimum(1.0, t / 0.006) * np.exp(-t * 22)
        tone = np.sin(2 * np.pi * f * t) + 0.25 * np.sin(4 * np.pi * f * t)
        parts += [(volume / 1.25 * env * tone).astype(np.float32), np.zeros(int(gap * rate), dtype=np.float32)]
    return np.concatenate(parts)


class Tray:
    """Trinity-knot indicators: a small tray icon (dim when on) and a large floating knot that
    appears while you talk and glows with your voice. Each part silently switches itself off if
    its dependencies are unavailable."""

    FPS = 20

    def __init__(self, app):
        self.app = app
        self.icon = None
        self.frames = None
        self.big = None
        self.overlay = None
        self.state = "loading"
        self.level = 0.0
        self._anim = None

    def start(self):
        try:
            sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
            from trinity_icon import KnotFrames
        except ImportError as e:
            print(f"(no indicators: {e})", flush=True)
            return
        if not self.app.args.no_tray:
            self._start_icon(KnotFrames)
        if self.app.args.overlay != "off":
            threading.Thread(target=self._start_overlay, args=(KnotFrames,), daemon=True).start()

    def _start_icon(self, KnotFrames):
        try:
            import pystray
        except ImportError as e:
            print(f"(no tray icon: {e})", flush=True)
            return
        self.frames = KnotFrames(64)
        menu = pystray.Menu(
            pystray.MenuItem(lambda _: f"Hold {self.app.args.key.upper()} to talk", None, enabled=False),
            pystray.MenuItem("Paused", self.toggle_pause, checked=lambda _: self.app.paused),
            pystray.MenuItem("Auto-send (press Enter)", self.toggle_auto_send,
                             checked=lambda _: self.app.args.auto_send),
            pystray.MenuItem("Open log", self.open_log, visible=bool(self.app.log_path)),
            pystray.Menu.SEPARATOR,
            pystray.MenuItem("Quit Voice Anywhere", self.quit),
        )
        self.icon = pystray.Icon("voice-anywhere", self.frames.image("loading"),
                                 tray_tooltip("loading", self.app.args.key), menu)
        self.icon.run_detached()
        threading.Thread(target=self._promote, daemon=True).start()

    def _start_overlay(self, KnotFrames):
        try:
            from overlay import Overlay
            import ctypes
            scale = ctypes.windll.user32.GetDpiForSystem() / 96
            size = int(self.app.args.overlay_size * scale)
            self.big = KnotFrames(size, n_frames=16, thick=1.6, margin=1.45, ss=2)
            ov = Overlay(position=self.app.args.overlay)
            if not ov.start():
                return
            self.overlay = ov
            self._hello()
        except Exception as e:
            print(f"(no overlay: {e})", flush=True)

    def _hello(self):
        """Brief appearance at start-up so you know it's on (e.g. after signing in)."""
        if self.state not in ("ready", "loading"):
            return
        import math
        n = int(self.FPS * 1.8)
        for f in range(n):
            if self.state not in ("ready", "loading"):
                return
            self.overlay.show(self.big.image("speaking", f, math.sin(math.pi * f / n)))
            time.sleep(1 / self.FPS)
        if self.state in ("ready", "loading"):
            self.overlay.hide()

    @staticmethod
    def _promote():
        """Windows 11 hides new tray icons under the ^ overflow. Pin ours to the taskbar
        (takes effect from the next start). Users can still hide it in Settings."""
        time.sleep(5)
        try:
            import winreg
            root = r"Control Panel\NotifyIconSettings"
            with winreg.OpenKey(winreg.HKEY_CURRENT_USER, root) as k:
                for i in range(winreg.QueryInfoKey(k)[0]):
                    name = winreg.EnumKey(k, i)
                    with winreg.OpenKey(k, name, 0, winreg.KEY_READ | winreg.KEY_WRITE) as sub:
                        try:
                            tip = winreg.QueryValueEx(sub, "InitialTooltip")[0]
                        except OSError:
                            continue
                        if str(tip).startswith("Voice Anywhere"):
                            try:
                                winreg.QueryValueEx(sub, "IsPromoted")  # respect a user's own choice
                            except OSError:
                                winreg.SetValueEx(sub, "IsPromoted", 0, winreg.REG_DWORD, 1)
        except OSError:
            pass

    def set(self, state):
        self.state = state
        try:
            if self.icon:
                self.icon.title = tray_tooltip(state, self.app.args.key)
            if state in ("recording", "transcribing"):
                if (self.icon or self.overlay) and not (self._anim and self._anim.is_alive()):
                    self._anim = threading.Thread(target=self._animate, daemon=True)
                    self._anim.start()
            else:
                if self.icon:
                    self.icon.icon = self.frames.image(state)
                if self.overlay:
                    self.overlay.hide()
        except Exception:
            pass

    def _animate(self):
        frame, shown = 0, 0.0
        while self.state in ("recording", "transcribing"):
            if self.state == "recording":
                shown += (self.level - shown) * (0.6 if self.level > shown else 0.25)  # fast attack, slow decay
                kind = "speaking"
            else:
                kind = "transcribing"
            try:
                if self.icon and frame % 2 == 0:  # the tray doesn't need 20 fps
                    self.icon.icon = self.frames.image(kind, frame // 2, shown)
                if self.overlay:
                    self.overlay.show(self.big.image(kind, frame, shown))
            except Exception:
                pass
            frame += 1
            time.sleep(1 / self.FPS)
        try:
            if self.icon:
                self.icon.icon = self.frames.image(self.state)
            if self.overlay:
                self.overlay.hide()
        except Exception:
            pass

    def toggle_pause(self, *_):
        self.app.paused = not self.app.paused
        self.set("paused" if self.app.paused else "ready")
        print("Paused." if self.app.paused else "Resumed.", flush=True)

    def toggle_auto_send(self, *_):
        self.app.args.auto_send = not self.app.args.auto_send

    def open_log(self, *_):
        if self.app.log_path and os.path.exists(self.app.log_path):
            os.startfile(self.app.log_path)

    def quit(self, *_):
        self.app.quit_event.set()

    def stop(self):
        if self.overlay:
            self.overlay.stop()
        if self.icon:
            try:
                self.icon.stop()
            except Exception:
                pass


# ---------------------------------------------------------------------------
# Runtime
# ---------------------------------------------------------------------------

def load_model(args):
    from faster_whisper import WhisperModel
    import numpy as np

    print(f"Loading Whisper '{args.model}' model (first run downloads it once)...", flush=True)
    t = time.time()
    compute = "int8" if args.device == "cpu" else "default"
    model = WhisperModel(args.model, device=args.device, compute_type=compute, cpu_threads=args.threads)
    list(model.transcribe(np.zeros(SAMPLE_RATE, dtype="float32"), beam_size=1)[0])  # warm-up
    print(f"Model ready in {time.time() - t:.1f}s.", flush=True)
    return model


def transcribe(model, audio, args):
    segments, info = model.transcribe(
        audio,
        language=args.language,
        initial_prompt=args.vocab or None,
        vad_filter=True,
        beam_size=1,
        without_timestamps=True,
    )
    return join_segments(segments), info.language


def resolve_mic(mic):
    if mic is None:
        return None
    return int(mic) if str(mic).isdigit() else mic


def list_mics():
    import sounddevice as sd
    default_in = sd.default.device[0]
    for i, d in enumerate(sd.query_devices()):
        if d["max_input_channels"] > 0:
            mark = "*" if i == default_in else " "
            print(f"{mark} {i:>3}  {d['name']}")
    print("\n* = default. Use --mic <index or name>.")


def self_test(args) -> int:
    import wave
    import numpy as np

    sentence = "Hello, this is a quick test of local voice transcription on this computer."
    print(f"Python {sys.version.split()[0]} on {sys.platform}")
    try:
        import sounddevice as sd
        print(f"Microphone: {sd.query_devices(kind='input')['name']}")
    except Exception as e:  # no mic is not fatal for the self-test
        print(f"Microphone: none found ({e})")

    path = os.path.join(tempfile.gettempdir(), "voice-anywhere-selftest.wav")
    try:
        import win32com.client
        voice = win32com.client.Dispatch("SAPI.SpVoice")
        stream = win32com.client.Dispatch("SAPI.SpFileStream")
        fmt = win32com.client.Dispatch("SAPI.SpAudioFormat")
        fmt.Type = 18  # 16 kHz, 16-bit, mono
        stream.Format = fmt
        stream.Open(path, 3)
        voice.AudioOutputStream = stream
        voice.Speak(sentence)
        stream.Close()
        with wave.open(path) as w:
            audio = np.frombuffer(w.readframes(w.getnframes()), dtype=np.int16).astype("float32") / 32768
    finally:
        if os.path.exists(path):
            os.remove(path)

    model = load_model(args)
    t = time.time()
    text, lang = transcribe(model, audio, args)
    secs = time.time() - t
    score = word_overlap(sentence, text)
    print(f"Clip length: {len(audio) / SAMPLE_RATE:.1f}s, transcribed in {secs:.2f}s ({lang})")
    print(f"Heard: {text}")
    print(f"Word match: {score:.0%}")
    ok = score >= 0.8
    print("SELF-TEST PASSED" if ok else "SELF-TEST FAILED")
    return 0 if ok else 1


class App:
    def __init__(self, args, model, log_path=None):
        self.args = args
        self.model = model
        self.log_path = log_path
        self.busy = threading.Lock()
        self.paused = False
        self.quit_event = threading.Event()
        self.speech_q: "queue.Queue[str | None]" = queue.Queue()
        self.tray = Tray(self) if not (args.no_tray and args.overlay == "off") else None
        self.chimes = {"start": make_chime((660, 990), args.chime_volume, lead=0.06),
                       "stop": make_chime((990, 660), args.chime_volume, lead=0.06)}

    def set_state(self, state):
        if self.tray:
            self.tray.set(state)

    def chime(self, kind, blocking=False):
        if self.args.no_beep:
            return
        try:
            import sounddevice as sd
            sd.play(self.chimes[kind], CHIME_RATE, blocking=blocking)
        except Exception as e:
            print(f"  (chime failed: {e})", flush=True)

    def record_while_held(self):
        import keyboard
        import numpy as np
        import sounddevice as sd

        chunks = []
        live = threading.Event()
        def cb(indata, frames, t, status):
            chunks.append(indata.copy())
            live.set()
            if self.tray:
                self.tray.level = voice_level(float(np.sqrt(np.mean(indata ** 2))))
        chimed = False
        with sd.InputStream(samplerate=SAMPLE_RATE, channels=1, dtype="float32",
                            device=resolve_mic(self.args.mic), callback=cb):
            while keyboard.is_pressed(self.args.key):
                if not chimed and live.is_set():
                    self.chime("start")  # the mic is delivering audio: speak now
                    chimed = True
                time.sleep(0.02)
        return np.concatenate(chunks).flatten() if chunks else np.zeros(0, dtype="float32")

    def deliver(self, text):
        import keyboard
        import pyperclip

        previous = pyperclip.paste() if self.args.restore_clipboard else None
        pyperclip.copy(text)
        if self.args.type_text:
            keyboard.write(text, delay=0.005)
        else:
            keyboard.send("ctrl+v")
        if self.args.auto_send:
            time.sleep(0.1)
            keyboard.send("enter")
        if previous is not None:
            time.sleep(0.4)
            pyperclip.copy(previous)

    def talk(self):
        if not self.busy.acquire(blocking=False):
            return
        try:
            self.set_state("recording")
            print("Listening... release to stop", flush=True)
            audio = self.record_while_held()
            self.chime("stop")
            if len(audio) < SAMPLE_RATE * 0.4:
                print(f"  Too short ({len(audio) / SAMPLE_RATE:.1f}s of audio), ignored.", flush=True)
                return
            self.set_state("transcribing")
            t = time.time()
            text, lang = transcribe(self.model, audio, self.args)
            if not text:
                print("  Heard nothing.", flush=True)
                return
            shown = f"{len(text)} characters" if self.args.background else text  # no transcripts in log files
            print(f"  [{lang}, {time.time() - t:.1f}s] {shown}", flush=True)
            self.deliver(text)
        except Exception as e:
            print(f"  Error: {e}", flush=True)
        finally:
            self.set_state("paused" if self.paused else "ready")
            self.busy.release()

    def on_talk_key(self, _event):
        if not self.paused and not self.busy.locked():  # ignore key auto-repeat while held
            threading.Thread(target=self.talk, daemon=True).start()

    def read_selection(self):
        import keyboard
        import pyperclip

        while keyboard.is_pressed("ctrl") or keyboard.is_pressed("alt"):
            time.sleep(0.03)
        previous = pyperclip.paste()
        pyperclip.copy("")
        keyboard.send("ctrl+c")
        time.sleep(0.25)
        text = pyperclip.paste() or previous  # nothing selected: read the clipboard
        if not text:
            print("Nothing selected to read.", flush=True)
            return
        print(f"Reading {len(text)} characters aloud...", flush=True)
        self.speech_q.put(clean_for_speech(text))

    def speaker(self):
        import pythoncom
        import win32com.client

        pythoncom.CoInitialize()
        voice = win32com.client.Dispatch("SAPI.SpVoice")
        while True:
            try:
                item = self.speech_q.get(timeout=0.1)
            except queue.Empty:
                pythoncom.PumpWaitingMessages()
                continue
            voice.Speak(item or "", 3)  # 3 = async + purge earlier speech (empty string = stop)

    def run(self):
        import keyboard

        keyboard.on_press_key(self.args.key, self.on_talk_key)
        lines = [f"Hold {self.args.key.upper()} and speak; release to paste where your cursor is."]
        if not self.args.no_read:
            threading.Thread(target=self.speaker, daemon=True).start()
            keyboard.add_hotkey(self.args.read_key,
                                lambda: threading.Thread(target=self.read_selection, daemon=True).start())
            keyboard.add_hotkey(self.args.stop_key, lambda: self.speech_q.put(None))
            lines.append(f"Select text and press {self.args.read_key.upper()} to hear it; "
                         f"{self.args.stop_key.upper()} stops.")
        lines.append(f"{self.args.quit_key.upper()} quits.")
        lines.append("Auto-send is ON." if self.args.auto_send else "Auto-send is off: you press Enter.")
        print("\nVoice Anywhere is running.\n  " + "\n  ".join(lines), flush=True)
        keyboard.add_hotkey(self.args.quit_key, self.quit_event.set)
        if self.tray:
            self.tray.start()
            self.set_state("ready")
        try:
            self.quit_event.wait()
        finally:
            keyboard.unhook_all()
            if self.tray:
                self.tray.stop()
        print("Bye.", flush=True)


def default_log_path() -> str:
    base = os.environ.get("LOCALAPPDATA") or tempfile.gettempdir()
    return os.path.join(base, "voice-anywhere", "voice-anywhere.log")


def redirect_output(path: str, max_bytes: int = 1_000_000):
    """Send prints to a log file (pythonw has no console). Keeps one old copy."""
    os.makedirs(os.path.dirname(path), exist_ok=True)
    if os.path.exists(path) and os.path.getsize(path) > max_bytes:
        os.replace(path, path + ".old")
    log = open(path, "a", encoding="utf-8", buffering=1)
    sys.stdout = sys.stderr = log
    print(f"\n=== Voice Anywhere {__version__} started {time.strftime('%Y-%m-%d %H:%M:%S')} ===")


def acquire_single_instance():
    """Return a mutex handle, or None if another instance is already running."""
    import win32api
    import win32event
    handle = win32event.CreateMutex(None, False, "Local\\VoiceAnywhereSingleInstance")
    if win32api.GetLastError() == 183:  # ERROR_ALREADY_EXISTS
        return None
    return handle


def run_background(args) -> int:
    log_path = args.log or default_log_path()
    redirect_output(log_path)
    mutex = acquire_single_instance()
    if mutex is None:
        print("Already running; this copy exits.")
        return 0
    model = None
    failures = 0
    while True:
        try:
            if model is None:
                model = load_model(args)
            app = App(args, model, log_path)
            app.run()
            return 0  # quit key pressed
        except Exception as e:
            import traceback
            failures += 1
            traceback.print_exc()
            wait = min(60, 5 * failures)
            print(f"Error ({e}); restarting in {wait}s.", flush=True)
            try:
                import keyboard
                keyboard.unhook_all()
            except Exception:
                pass
            time.sleep(wait)


def main(argv=None) -> int:
    args = build_parser().parse_args(argv)
    if sys.platform != "win32":
        print("Voice Anywhere currently supports Windows 10/11 only.", file=sys.stderr)
        return 2
    os.environ.setdefault("HF_HUB_DISABLE_SYMLINKS_WARNING", "1")
    if args.list_mics:
        list_mics()
        return 0
    if args.self_test:
        return self_test(args)
    if args.background:
        return run_background(args)
    if args.log:
        redirect_output(args.log)
    if acquire_single_instance() is None:
        print("Voice Anywhere is already running (probably in the background). "
              "Press Ctrl+Alt+Q to stop it first if you want this copy instead.")
        return 1
    App(args, load_model(args), args.log).run()
    return 0


if __name__ == "__main__":
    sys.exit(main())
