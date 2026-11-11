"""Phase 10 render: each locked style grades to a distinct look; Style Lock integrates with grade."""
import shutil
import subprocess
import tempfile
import unittest
from pathlib import Path

from uvs.styles import STYLES, StyleLock
from uvs import grade as G
from uvs import color as C

HAS_FFMPEG = shutil.which("ffmpeg") is not None and shutil.which("ffprobe") is not None


@unittest.skipUnless(HAS_FFMPEG, "ffmpeg not installed")
class StyleRenderTests(unittest.TestCase):
    def setUp(self):
        self._tmp = tempfile.TemporaryDirectory()
        self.dir = Path(self._tmp.name)
        self.src = self.dir / "src.mp4"
        subprocess.run(["ffmpeg", "-hide_banner", "-loglevel", "error", "-y", "-f", "lavfi",
                        "-i", "testsrc2=s=320x180:d=0.3:r=6", "-c:v", "libx264", "-pix_fmt",
                        "yuv420p", str(self.src)], check=True)

    def tearDown(self):
        self._tmp.cleanup()

    def test_all_ten_styles_grade_and_are_mostly_distinct(self):
        sigs = {}
        for name in STYLES:
            out = self.dir / f"{name}.mp4"
            G.grade(self.src, out, StyleLock.resolve(name).look_filter())
            s = C.analyze_frame(out, 0.1)
            sigs[name] = (round(s.luma, 0), round(s.saturation, 2), round(s.warmth, 2))
            self.assertTrue(out.exists())
        # at least 8 of 10 colour signatures should be distinct
        self.assertGreaterEqual(len(set(sigs.values())), 8)

    def test_style_lock_look_differs_from_scene_zero_look(self):
        # D-01: locking a style must override whatever a scene's own look would be.
        lock = StyleLock.resolve("investigative_documentary")
        self.assertEqual(lock.style.color_grade, "dark_investigative_v2")
        # grading with the locked look yields the investigative look, not a bright one
        out = self.dir / "locked.mp4"
        G.grade(self.src, out, lock.look_filter())
        locked = C.analyze_frame(out, 0.1)
        # investigative is darker/desaturated; compare against a bright style
        bright = self.dir / "bright.mp4"
        G.grade(self.src, bright, StyleLock.resolve("educational_shorts").look_filter())
        self.assertLess(locked.luma, C.analyze_frame(bright, 0.1).luma)


if __name__ == "__main__":
    unittest.main()
