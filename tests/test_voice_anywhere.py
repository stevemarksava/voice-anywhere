"""Pure-logic tests: no microphone, keyboard hook or speech model needed.

Run from the repo root:  python -m unittest discover -s tests -v
"""
import os
import sys
import tempfile
import unittest
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
        self.assertEqual(a.key, "right ctrl")
        self.assertEqual(a.model, "base")
        self.assertIsNone(a.language)
        self.assertFalse(a.auto_send)
        self.assertFalse(a.restore_clipboard)
        self.assertFalse(a.background)
        self.assertFalse(a.no_tray)
        self.assertGreaterEqual(a.threads, 1)
        self.assertLessEqual(a.threads, 8)

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
