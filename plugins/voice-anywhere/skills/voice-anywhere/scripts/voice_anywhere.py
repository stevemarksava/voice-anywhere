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
    p.add_argument("--no-beep", action="store_true", help="no start/stop beeps")
    p.add_argument("--read-key", default="ctrl+alt+r", help="read selected text aloud (default: ctrl+alt+r)")
    p.add_argument("--stop-key", default="ctrl+alt+s", help="stop reading aloud (default: ctrl+alt+s)")
    p.add_argument("--quit-key", default="ctrl+alt+q", help="quit (default: ctrl+alt+q)")
    p.add_argument("--no-read", action="store_true", help="disable the read-aloud hotkeys")
    p.add_argument("--no-tray", action="store_true", help="no system-tray icon")
    p.add_argument("--background", action="store_true",
                   help="always-on mode for sign-in: no window needed, log to file, one instance only, "
                        "restart automatically after errors, double beep when ready")
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


class Tray:
    """Trinity-knot system-tray indicator: dim when on, glows with your voice while you talk.
    Silently does nothing if pystray or Pillow is unavailable."""

    FPS = 12

    def __init__(self, app):
        self.app = app
        self.icon = None
        self.frames = None
        self.state = "loading"
        self.level = 0.0
        self._anim = None

    def start(self):
        try:
            import pystray
            sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
            from trinity_icon import KnotFrames
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
        if not self.icon:
            return
        try:
            self.icon.title = tray_tooltip(state, self.app.args.key)
            if state in ("recording", "transcribing"):
                if not (self._anim and self._anim.is_alive()):
                    self._anim = threading.Thread(target=self._animate, daemon=True)
                    self._anim.start()
            else:
                self.icon.icon = self.frames.image(state)
        except Exception:
            pass

    def _animate(self):
        frame, shown = 0, 0.0
        while self.state in ("recording", "transcribing") and self.icon:
            if self.state == "recording":
                shown += (self.level - shown) * (0.6 if self.level > shown else 0.25)  # fast attack, slow decay
                img = self.frames.image("speaking", frame, shown)
            else:
                img = self.frames.image("transcribing", frame)
            try:
                self.icon.icon = img
            except Exception:
                return
            frame += 1
            time.sleep(1 / self.FPS)
        try:
            self.icon.icon = self.frames.image(self.state)
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
        self.tray = Tray(self) if not args.no_tray else None

    def set_state(self, state):
        if self.tray:
            self.tray.set(state)

    def beep(self, freq):
        if self.args.no_beep:
            return
        try:
            import winsound
            winsound.Beep(freq, 70)
        except Exception:
            pass

    def record_while_held(self):
        import keyboard
        import numpy as np
        import sounddevice as sd

        chunks = []
        def cb(indata, frames, t, status):
            chunks.append(indata.copy())
            if self.tray:
                self.tray.level = voice_level(float(np.sqrt(np.mean(indata ** 2))))
        with sd.InputStream(samplerate=SAMPLE_RATE, channels=1, dtype="float32",
                            device=resolve_mic(self.args.mic), callback=cb):
            while keyboard.is_pressed(self.args.key):
                time.sleep(0.03)
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
            self.beep(880)
            print("Listening... release to stop", flush=True)
            audio = self.record_while_held()
            self.beep(440)
            if len(audio) < SAMPLE_RATE * 0.4:
                print("  Too short, ignored.", flush=True)
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
            if not args.no_beep:
                app.beep(660)
                app.beep(990)  # double beep: ready
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
