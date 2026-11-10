"""Measured colour tests: each look is applied to a solid patch and the decoded pixels are checked."""
import shutil
import subprocess
import tempfile
import unittest
from pathlib import Path

from uvs import grade as G

HAS_FFMPEG = shutil.which("ffmpeg") is not None


def _patch(path: Path, rgb_hex: str):
    subprocess.run(["ffmpeg", "-hide_banner", "-loglevel", "error", "-y", "-f", "lavfi", "-i",
                    f"color=c=0x{rgb_hex}:s=320x240:r=30:d=1", "-c:v", "libx264", "-pix_fmt", "yuv420p",
                    str(path)], check=True)
    return path


def _cube_swap_rb(path: Path):
    """Identity-size 2 LUT that swaps red and blue. Entries are ordered with red varying fastest."""
    lines = ["TITLE \"swap rb\"", "LUT_3D_SIZE 2"]
    for b in (0, 1):
        for g in (0, 1):
            for r in (0, 1):
                lines.append(f"{b} {g} {r}")  # output = (b, g, r) for input (r, g, b)
    path.write_text("\n".join(lines) + "\n", encoding="utf-8")
    return path


@unittest.skipUnless(HAS_FFMPEG, "ffmpeg not installed")
class GradeMeasuredTests(unittest.TestCase):
    def setUp(self):
        self._tmp = tempfile.TemporaryDirectory()
        self.dir = Path(self._tmp.name)
        self.gray = _patch(self.dir / "gray.mp4", "808080")
        self.red = _patch(self.dir / "red.mp4", "c83232")

    def tearDown(self):
        self._tmp.cleanup()

    def graded(self, src, look, intensity="standard"):
        out = G.grade(src, self.dir / f"{look}-{intensity}-{Path(src).stem}.mp4",
                      G.look_filter(look, intensity))
        return G.sample_rgb(out, 0.5)

    def test_warm_lifestyle_warms_neutral_grey(self):
        r, g, b = self.graded(self.gray, "warm_lifestyle")
        self.assertGreater(r - b, 3)

    def test_desaturated_emotional_reduces_saturation(self):
        before = G.saturation(G.sample_rgb(self.red, 0.5))
        after = G.saturation(self.graded(self.red, "desaturated_emotional"))
        self.assertLess(after, before - 0.1)

    def test_bright_educational_raises_brightness(self):
        before = sum(G.sample_rgb(self.gray, 0.5)) / 3
        after = sum(self.graded(self.gray, "bright_educational")) / 3
        self.assertGreater(after, before + 3)

    def test_dynamic_intensity_is_stronger_than_subtle(self):
        subtle = self.graded(self.gray, "warm_lifestyle", "subtle")
        dynamic = self.graded(self.gray, "warm_lifestyle", "dynamic")
        self.assertGreater(dynamic[0] - dynamic[2], subtle[0] - subtle[2])

    def test_lut_channel_swap_turns_red_blue(self):
        lut = _cube_swap_rb(self.dir / "swap.cube")
        vf = G.lut_filter(lut)
        out = G.grade(self.red, self.dir / "lut.mp4", vf)
        r, g, b = G.sample_rgb(out, 0.5)
        self.assertGreater(b, r + 60)


class GradeStringTests(unittest.TestCase):
    def test_every_named_look_builds_a_filter_chain(self):
        for name in G.LOOKS:
            for intensity in G.INTENSITY:
                vf = G.look_filter(name, intensity)
                self.assertTrue(vf.startswith("eq="), vf)

    def test_unknown_look_and_intensity_are_rejected(self):
        with self.assertRaises(KeyError):
            G.look_filter("neon_tv")
        with self.assertRaises(KeyError):
            G.look_filter("warm_lifestyle", "extreme")

    def test_scaling_clamps_values_to_safe_ranges(self):
        scaled = G._scale(G.LOOKS["retro_film"], 10.0)
        self.assertLessEqual(scaled.grain, 16.0)
        self.assertLessEqual(max(scaled.highlights), 0.25)
        self.assertLessEqual(scaled.saturation, 1.8)

    def test_lut_requires_cube_extension_and_existing_file(self):
        with tempfile.TemporaryDirectory() as d:
            with self.assertRaises(ValueError):
                G.lut_filter(Path(d) / "x.png")
            with self.assertRaises(FileNotFoundError):
                G.lut_filter(Path(d) / "missing.cube")


if __name__ == "__main__":
    unittest.main()
