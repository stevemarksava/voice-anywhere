"""Pure-logic tests: no microphone, keyboard hook or speech model needed.

Run from the repo root:  python -m unittest discover -s tests -v
"""
import os
import sys
import tempfile
import unittest
from contextlib import redirect_stderr
from types import SimpleNamespace

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "plugins", "voice-anywhere",
                                "skills", "voice-anywhere", "scripts"))
import voice_anywhere as va  # noqa: E402

try:
    import PIL  # noqa: F401
    HAVE_PIL = True
except ImportError:
    HAVE_PIL = False

try:
    import numpy  # noqa: F401
    HAVE_NUMPY = True
except ImportError:
    HAVE_NUMPY = False


class ParserTests(unittest.TestCase):
    def test_defaults(self):
        a = va.build_parser().parse_args([])
        self.assertIsNone(a.key, "no --key: resolved later from the saved choice or the default")
        self.assertEqual(va.resolve_key(a.key, {}), ("right ctrl", "default"))
        self.assertEqual(a.model, "base")
        self.assertIsNone(a.language)
        self.assertFalse(a.auto_send)
        self.assertFalse(a.restore_clipboard)
        self.assertFalse(a.background)
        self.assertFalse(a.no_tray)
        self.assertGreaterEqual(a.threads, 1)
        self.assertLessEqual(a.threads, 8)


class SquadFixTests(unittest.TestCase):
    """Regression tests for the squad review findings (see .squad/reviews/2026-11-05-*.md)."""

    @staticmethod
    def make_app(key="right ctrl", paused=True):
        app = va.App.__new__(va.App)
        app.args = va.build_parser().parse_args(["--key", key, "--no-beep"])
        app.talk_down, app.chorded, app.paused = False, False, paused  # paused: don't start threads
        app.busy = __import__("threading").Lock()
        app.choosing_until, app.config_file, app.key_source, app.tray = 0.0, None, "default", None
        app.hold_until_release = False
        app.bg = lambda fn, *a: fn(*a)  # run "background" work inline so tests are deterministic
        app.told = []
        app.tell = app.told.append
        app.set_state = lambda s: None
        return app

    def test_k01_right_ctrl_does_not_match_left_ctrl(self):
        # The keyboard library names Left Ctrl events 'ctrl' and Right Ctrl events 'right ctrl'.
        self.assertTrue(va.key_matches("right ctrl", "right ctrl"))
        self.assertTrue(va.key_matches("Right  Ctrl", "right ctrl"))
        self.assertFalse(va.key_matches("right ctrl", "ctrl"))
        self.assertFalse(va.key_matches("right ctrl", "left ctrl"))
        self.assertFalse(va.key_matches("right ctrl", ""))
        self.assertFalse(va.key_matches("right ctrl", None))
        self.assertTrue(va.key_matches("f9", "F9"))
        self.assertFalse(va.key_matches("f9", "f10"))
        self.assertTrue(va.key_matches("left ctrl", "ctrl"))

    def test_k01_hook_ignores_left_ctrl_and_cancels_chords(self):
        app = self.make_app()
        ev = lambda t, n: SimpleNamespace(event_type=t, name=n)
        app.on_key_event(ev("down", "ctrl"))
        self.assertFalse(app.talk_down, "Left Ctrl must not start dictation")
        app.on_key_event(ev("down", "right ctrl"))
        self.assertTrue(app.talk_down)
        app.on_key_event(ev("down", "right ctrl"))  # auto-repeat
        self.assertFalse(app.chorded)
        app.on_key_event(ev("down", "c"))  # Right Ctrl+C
        self.assertTrue(app.chorded, "a shortcut with the talk key must cancel the recording")
        app.on_key_event(ev("up", "right ctrl"))
        self.assertFalse(app.talk_down)

    def test_r1_lost_release_does_not_block_next_press(self):
        app = self.make_app()
        app.talk_down, app.chorded = True, True  # stale state: release was never seen
        app.on_key_event(SimpleNamespace(event_type="down", name="right ctrl"))
        self.assertTrue(app.talk_down)
        self.assertFalse(app.chorded, "a fresh press must reset the shortcut flag")


class TalkKeyChoiceTests(unittest.TestCase):
    """v0.2.3: laptops without Right Ctrl can pick their own talk key."""

    ev = staticmethod(lambda t, n: SimpleNamespace(event_type=t, name=n))

    def test_allowed_and_refused_keys(self):
        for ok in ("caps lock", "f8", "right alt", "alt gr", "right shift", "scroll lock", "insert", "menu", "f23"):
            self.assertIsNone(va.talk_key_problem(ok), ok)
        for bad in ("a", "7", ";", "space", "enter", "tab", "backspace", "esc", "left", "page up",
                    "ctrl", "shift", "alt", "windows", "", "unknown"):
            self.assertIsNotNone(va.talk_key_problem(bad), bad)

    def test_only_non_modifiers_are_swallowed(self):
        self.assertTrue(va.suppresses_key("caps lock"))
        self.assertTrue(va.suppresses_key("F8"))
        self.assertFalse(va.suppresses_key("right ctrl"))
        self.assertFalse(va.suppresses_key("right alt"))

    def test_hook_return_values(self):
        app = SquadFixTests.make_app("caps lock", paused=False)
        app.busy.acquire()  # pretend a recording is running so no thread is started
        try:
            self.assertFalse(app.on_key_event(self.ev("down", "caps lock")), "caps lock must not toggle caps")
            self.assertFalse(app.on_key_event(self.ev("up", "caps lock")))
            self.assertTrue(app.on_key_event(self.ev("down", "x")), "other keys always pass through")
        finally:
            app.busy.release()
        app.paused = True
        self.assertTrue(app.on_key_event(self.ev("down", "caps lock")), "paused: caps lock works normally")
        rc = SquadFixTests.make_app("right ctrl", paused=True)
        self.assertTrue(rc.on_key_event(self.ev("down", "right ctrl")), "modifier talk keys are never swallowed")

    def test_hook_never_raises_or_blocks_on_error(self):
        app = SquadFixTests.make_app()
        self.assertTrue(app.on_key_event(object()), "a broken event must be let through, not block typing")

    def test_choose_key_flow(self):
        import time as _time
        app = SquadFixTests.make_app()
        app.config_file = os.path.join(tempfile.mkdtemp(), "config.json")
        app.chime = lambda kind, blocking=False: None
        app.choosing_until = _time.time() + 10
        # Copilot key sends Windows+Shift+F23: the modifiers are skipped, F23 is taken.
        self.assertTrue(app.on_key_event(self.ev("down", "left windows")))
        self.assertTrue(app.on_key_event(self.ev("down", "shift")))
        self.assertFalse(app.on_key_event(self.ev("down", "f23")), "the chosen key isn't passed to the app")
        self.assertEqual(app.args.key, "f23")
        self.assertEqual(va.load_config(app.config_file), {"key": "f23"})
        # A letter is refused and nothing changes.
        app.choosing_until = _time.time() + 10
        app.on_key_event(self.ev("down", "q"))
        self.assertEqual(app.args.key, "f23")
        self.assertEqual(app.choosing_until, 0.0)
        # Esc cancels.
        app.choosing_until = _time.time() + 10
        app.on_key_event(self.ev("down", "esc"))
        self.assertEqual(app.args.key, "f23")
        # Timeout: the next key is treated normally, not as a choice.
        app.choosing_until = _time.time() - 1
        app.on_key_event(self.ev("down", "caps lock"))
        self.assertEqual(app.args.key, "f23")

    def test_chosen_key_held_down_does_not_start_recording(self):
        """Vera 0.2.3 fix 1: auto-repeat of the key you just chose must not start dictation."""
        import time as _time
        app = SquadFixTests.make_app(paused=False)
        app.config_file = os.path.join(tempfile.mkdtemp(), "config.json")
        app.chime = lambda kind, blocking=False: None
        starts = []
        app.talk = lambda: starts.append(1)
        app.choosing_until = _time.time() + 10
        self.assertFalse(app.on_key_event(self.ev("down", "caps lock")))  # chosen
        for _ in range(5):
            self.assertFalse(app.on_key_event(self.ev("down", "caps lock")), "auto-repeat is still swallowed")
        _time.sleep(0.1)
        self.assertEqual(starts, [], "holding the just-chosen key must not start a recording")
        self.assertFalse(app.on_key_event(self.ev("up", "caps lock")))
        self.assertFalse(app.hold_until_release)
        app.on_key_event(self.ev("down", "caps lock"))  # a real, new press
        _time.sleep(0.1)
        self.assertEqual(starts, [1])

    def test_releases_pass_while_choosing(self):
        """Vera 0.2.3 fix 3: a key-up during choosing (e.g. Enter from the tray menu) is never swallowed."""
        import time as _time
        app = SquadFixTests.make_app()
        app.choosing_until = _time.time() + 10
        self.assertTrue(app.on_key_event(self.ev("up", "enter")))
        self.assertGreater(app.choosing_until, 0, "a release doesn't end choosing")

    def test_resolve_key_precedence_and_config_roundtrip(self):
        path = os.path.join(tempfile.mkdtemp(), "sub", "config.json")
        self.assertEqual(va.load_config(path), {})
        va.save_config({"key": "caps lock"}, path)
        va.save_config({"other": 1}, path)
        cfg = va.load_config(path)
        self.assertEqual(cfg, {"key": "caps lock", "other": 1})
        self.assertEqual(va.resolve_key(None, cfg), ("caps lock", "saved choice"))
        self.assertEqual(va.resolve_key("f9", cfg), ("f9", "command line"))
        self.assertEqual(va.resolve_key(None, {"key": "  "}), ("right ctrl", "default"))
        with open(path, "w") as f:
            f.write("not json")
        self.assertEqual(va.load_config(path), {})

    def test_k02_console_windows_never_auto_send(self):
        self.assertTrue(va.is_console_class("ConsoleWindowClass"))
        self.assertTrue(va.is_console_class("CASCADIA_HOSTING_WINDOW_CLASS"))
        self.assertFalse(va.is_console_class("Chrome_WidgetWin_1"))
        self.assertFalse(va.is_console_class(""))
        self.assertFalse(va.is_console_class(None))

    def test_v1d4_ranges_validated(self):
        p = va.build_parser()
        for bad in (["--threads", "0"], ["--threads", "65"], ["--chime-volume", "9"], ["--chime-volume", "-1"],
                    ["--overlay-size", "-5"], ["--overlay-size", "5000"], ["--threads", "abc"]):
            with self.assertRaises(SystemExit, msg=bad):
                with open(os.devnull, "w") as null, redirect_stderr(null):
                    p.parse_args(bad)
        a = p.parse_args(["--threads", "1", "--chime-volume", "0", "--overlay-size", "64"])
        self.assertEqual((a.threads, a.chime_volume, a.overlay_size), (1, 0.0, 64))

    def test_v1d8_voice_level_non_finite(self):
        self.assertEqual(va.voice_level(float("nan")), 0.0)
        self.assertEqual(va.voice_level(float("inf")), 0.0)
        self.assertEqual(va.voice_level(-0.5), 0.0)

    def test_v1d13_snake_case_stays_readable(self):
        self.assertEqual(va.clean_for_speech("call my_var_name now"), "call my var name now")
        self.assertEqual(va.clean_for_speech("_italic_ and __bold__"), "italic and bold")

    def test_k09_retry_backoff(self):
        self.assertEqual([va.retry_delay(n) for n in (1, 2, 3, 4)], [5, 10, 20, 40])
        self.assertEqual(va.retry_delay(50), 600)
        self.assertEqual(va.retry_delay(0), 5)

    def test_v1d3_bad_key_names_fail_fast(self):
        try:
            import keyboard  # noqa: F401
        except ImportError:
            self.skipTest("keyboard not installed")
        p = va.build_parser()
        self.assertIsNone(va.validate_keys(p.parse_args([])))
        self.assertIn("--key", va.validate_keys(p.parse_args(["--key", "notakey"])))
        self.assertIn("--read-key", va.validate_keys(p.parse_args(["--read-key", "ctrl+alt+nonsense"])))

    def test_vf_model_loads_offline_first(self):
        """Vera final gate: once cached, loading the model must not touch the network."""
        import types
        calls = []

        class FakeModel:
            def __init__(self, name, **kw):
                calls.append(kw.get("local_files_only", False))
                if kw.get("local_files_only") and fake_cached is False:
                    raise OSError("not cached")

            def transcribe(self, *a, **k):
                return iter([]), None

        fake = types.ModuleType("faster_whisper")
        fake.WhisperModel = FakeModel
        args = va.build_parser().parse_args([])
        saved = sys.modules.get("faster_whisper")
        sys.modules["faster_whisper"] = fake
        try:
            if not HAVE_NUMPY:
                self.skipTest("numpy not installed")
            with open(os.devnull, "w") as null:
                from contextlib import redirect_stdout
                fake_cached = True
                with redirect_stdout(null):
                    va.load_model(args)
                self.assertEqual(calls, [True], "cached model: one offline load, no download attempt")
                calls.clear()
                fake_cached = False
                with redirect_stdout(null):
                    va.load_model(args)
                self.assertEqual(calls, [True, False], "not cached: offline attempt, then one download")
        finally:
            if saved is not None:
                sys.modules["faster_whisper"] = saved
            else:
                sys.modules.pop("faster_whisper", None)

    def test_v2d4_local_timestamp_format(self):
        import re
        self.assertRegex(va.local_timestamp(), r"^\d{4}-\d\d-\d\d \d\d:\d\d:\d\d$")


class ParserOptionTests(unittest.TestCase):
    def test_options(self):
        a = va.build_parser().parse_args(
            ["--key", "f9", "--model", "small", "--language", "de", "--vocab", "Avanade, Fabric",
             "--auto-send", "--type", "--background", "--no-tray", "--mic", "3"])
        self.assertEqual((a.key, a.model, a.language, a.vocab), ("f9", "small", "de", "Avanade, Fabric"))
        self.assertTrue(a.auto_send and a.type_text and a.background and a.no_tray)
        self.assertEqual(va.resolve_mic(a.mic), 3)
        self.assertEqual(va.resolve_mic("Headset"), "Headset")
        self.assertIsNone(va.resolve_mic(None))


class TextTests(unittest.TestCase):
    def test_clean_for_speech(self):
        md = "# Title\n- **Bold** item\n1. See [docs](https://x.y/z) or https://a.b\n```py\nprint(1)\n```\n![img](p.png)"
        out = va.clean_for_speech(md)
        self.assertNotIn("**", out)
        self.assertNotIn("#", out)
        self.assertNotIn("https", out)
        self.assertNotIn("print(1)", out)
        self.assertIn("Bold item", out)
        self.assertIn("docs", out)
        self.assertIn("code block skipped", out)

    def test_join_segments(self):
        segs = [SimpleNamespace(text=" Hello"), SimpleNamespace(text="  "), SimpleNamespace(text="world. ")]
        self.assertEqual(va.join_segments(segs), "Hello world.")

    def test_word_overlap(self):
        self.assertEqual(va.word_overlap("Hello there, world", "hello world there!"), 1.0)
        self.assertAlmostEqual(va.word_overlap("one two three four", "one two"), 0.5)
        self.assertEqual(va.word_overlap("", "x"), 0.0)


class IndicatorTests(unittest.TestCase):
    def test_voice_level(self):
        self.assertEqual(va.voice_level(0.0), 0.0)
        quiet, speech, loud = va.voice_level(0.001), va.voice_level(0.05), va.voice_level(0.5)
        self.assertLess(quiet, speech)
        self.assertLessEqual(speech, loud)
        self.assertEqual(loud, 1.0)
        self.assertGreaterEqual(quiet, 0.0)

    def test_tooltips(self):
        for state in va.STATES:
            tip = va.tray_tooltip(state, "right ctrl")
            self.assertTrue(tip.startswith("Voice Anywhere"))
            self.assertLessEqual(len(tip), 127)
        self.assertIn("RIGHT CTRL", va.tray_tooltip("ready", "right ctrl"))

    def test_default_log_path(self):
        self.assertTrue(va.default_log_path().endswith(os.path.join("voice-anywhere", "voice-anywhere.log")))

    @unittest.skipUnless(HAVE_NUMPY, "numpy not installed")
    def test_make_chime(self):
        c = va.make_chime((660, 990), volume=0.4, lead=0.1)
        self.assertEqual(c.dtype.name, "float32")
        self.assertGreater(len(c), int(0.1 * va.CHIME_RATE) + int(0.15 * va.CHIME_RATE))
        self.assertLessEqual(float(abs(c).max()), 0.4 + 1e-6)
        self.assertEqual(float(abs(c[: int(0.1 * va.CHIME_RATE)]).max()), 0.0, "lead-in should be silent")
        self.assertEqual(float(abs(va.make_chime((660,), volume=0.0)).max()), 0.0)

    def test_overlay_position(self):
        import overlay
        self.assertEqual(overlay.bottom_centre(200, 100, (0, 0, 1920, 1040), 40), (860, 900))
        self.assertEqual(overlay.bottom_centre(200, 100, (1920, 0, 3840, 1040), 40), (2780, 900))

    @unittest.skipUnless(HAVE_PIL and HAVE_NUMPY, "Pillow/numpy not installed")
    def test_premultiplied_bgra(self):
        from PIL import Image
        import overlay
        img = Image.new("RGBA", (2, 1))
        img.putpixel((0, 0), (200, 100, 50, 255))
        img.putpixel((1, 0), (200, 100, 50, 128))
        b = overlay.to_premultiplied_bgra(img)
        self.assertEqual(tuple(b[0:4]), (50, 100, 200, 255))
        self.assertEqual(tuple(b[4:8]), (25, 50, 100, 128))

    def test_overlay_option(self):
        a = va.build_parser().parse_args(["--overlay", "cursor", "--overlay-size", "300", "--chime-volume", "0.5"])
        self.assertEqual((a.overlay, a.overlay_size, a.chime_volume), ("cursor", 300, 0.5))
        self.assertEqual(va.build_parser().parse_args([]).overlay, "bottom")

    @unittest.skipUnless(HAVE_PIL, "Pillow not installed")
    def test_knot_frames(self):
        import trinity_icon as ti
        fr = ti.KnotFrames(size=32, n_frames=3)
        idle = fr.image("idle")
        quiet = fr.image("speaking", 0, 0.0)
        loud = fr.image("speaking", 0, 1.0)
        self.assertEqual(idle.size, (32, 32))
        self.assertEqual(idle.mode, "RGBA")
        alpha = lambda im: sum(im.getchannel("A").tobytes())
        def brightness(im):
            b = im.tobytes()
            return sum((b[i] + b[i + 1] + b[i + 2]) * b[i + 3] for i in range(0, len(b), 4))
        self.assertGreater(alpha(loud), alpha(quiet), "louder speech should glow more")
        self.assertGreater(brightness(loud), brightness(idle), "speaking should be brighter than idle")
        self.assertGreater(brightness(loud), brightness(quiet), "colours should dim in silence")
        r, g, b, a = fr.image("paused").convert("RGBA").getpixel((16, 16))
        self.assertTrue(a == 0 or (abs(r - g) < 3 and abs(g - b) < 3), "paused should be grey")

    @unittest.skipUnless(HAVE_PIL, "Pillow not installed")
    def test_write_ico(self):
        import trinity_icon as ti
        path = os.path.join(tempfile.mkdtemp(), "t.ico")
        ti.write_ico(path)
        with open(path, "rb") as f:
            self.assertEqual(f.read(4), b"\x00\x00\x01\x00")


if __name__ == "__main__":
    unittest.main()
