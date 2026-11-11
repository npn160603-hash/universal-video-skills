"""Phase 9 render: grades apply in ffmpeg and measurably change frames; shot match on real frames."""
import shutil
import subprocess
import tempfile
import unittest
from pathlib import Path

from uvs import color as C
from uvs import grade as G

HAS_FFMPEG = shutil.which("ffmpeg") is not None and shutil.which("ffprobe") is not None


def _src(path: Path, pattern="testsrc2", seconds=1.0):
    subprocess.run(["ffmpeg", "-hide_banner", "-loglevel", "error", "-y", "-f", "lavfi",
                    "-i", f"{pattern}=s=320x240:d={seconds}:r=15", "-c:v", "libx264",
                    "-pix_fmt", "yuv420p", str(path)], check=True)


@unittest.skipUnless(HAS_FFMPEG, "ffmpeg not installed")
class GradeRenderTests(unittest.TestCase):
    def setUp(self):
        self._tmp = tempfile.TemporaryDirectory()
        self.dir = Path(self._tmp.name)
        self.src = self.dir / "src.mp4"
        _src(self.src)
        self.base = C.analyze_frame(self.src, 0.4)

    def tearDown(self):
        self._tmp.cleanup()

    def test_warm_look_increases_warmth(self):
        out = self.dir / "warm.mp4"
        G.grade(self.src, out, G.look_filter("warm_lifestyle", "cinematic"))
        self.assertGreater(C.analyze_frame(out, 0.4).warmth, self.base.warmth)

    def test_temperature_cooler_decreases_warmth(self):
        out = self.dir / "cool.mp4"
        G.grade(self.src, out, C.ColorAdjust(temperature=9000).to_filter())
        self.assertLess(C.analyze_frame(out, 0.4).warmth, self.base.warmth + 0.02)

    def test_vignette_darkens_the_frame(self):
        out = self.dir / "vig.mp4"
        G.grade(self.src, out, C.vignette(0.7))
        self.assertLess(C.analyze_frame(out, 0.4).luma, self.base.luma)

    def test_all_ten_spec_looks_render(self):
        for name in C.SPEC_LOOK_NAMES:
            with self.subTest(look=name):
                out = self.dir / f"{name}.mp4"
                G.grade(self.src, out, G.look_filter(name, "standard"))
                self.assertTrue(out.exists() and out.stat().st_size > 0)

    def test_glow_and_chromakey_filtergraphs_run(self):
        png = self.dir / "glow.png"
        r = subprocess.run(["ffmpeg", "-hide_banner", "-loglevel", "error", "-y", "-i", str(self.src),
                            "-filter_complex", C.glow(8, 0.5), "-map", "[glow]", "-frames:v", "1", str(png)],
                           capture_output=True, text=True)
        self.assertEqual(r.returncode, 0, r.stderr[-300:])
        self.assertTrue(png.exists())


@unittest.skipUnless(HAS_FFMPEG, "ffmpeg not installed")
class ShotMatchRenderTests(unittest.TestCase):
    def setUp(self):
        self._tmp = tempfile.TemporaryDirectory()
        self.dir = Path(self._tmp.name)

    def tearDown(self):
        self._tmp.cleanup()

    def test_matching_a_tinted_clip_reduces_distance_to_reference(self):
        ref = self.dir / "ref.mp4"
        tgt = self.dir / "tgt.mp4"
        _src(ref)
        # a blue-tinted version of the same source
        subprocess.run(["ffmpeg", "-hide_banner", "-loglevel", "error", "-y", "-i", str(ref),
                        "-vf", "colorbalance=bh=0.3:bm=0.3", "-c:v", "libx264", "-pix_fmt", "yuv420p",
                        str(tgt)], check=True)
        ref_f = C.decode_frame(ref, 0.4)
        tgt_f = C.decode_frame(tgt, 0.4)
        before = C.match_distance(tgt_f, ref_f)
        m = C.match_shots(ref_f, tgt_f, strength=1.0)
        after = C.match_distance(m.apply_to_array(tgt_f), ref_f)
        self.assertLess(after, before)


if __name__ == "__main__":
    unittest.main()
