"""Chart measurements from rendered pixels, and media index checks on real files."""
import json
import shutil
import subprocess
import tempfile
import unittest
from pathlib import Path

from PIL import Image, ImageDraw

from uvs import charts as C
from uvs import media_index as M

HAS_FFMPEG = shutil.which("ffmpeg") is not None and shutil.which("ffprobe") is not None


def _bar_pixels_height(img: Image.Image, rect) -> int:
    """Count bar-coloured pixels in the centre column of a bar, from the baseline upward."""
    x0, y0, x1, y1 = rect
    cx = (x0 + x1) // 2
    count = 0
    for y in range(y1 - 1, y0 - 1, -1):
        r, g, b = img.getpixel((cx, y))
        if abs(r - C.BAR[0]) < 12 and abs(g - C.BAR[1]) < 12 and abs(b - C.BAR[2]) < 12:
            count += 1
        elif count:
            break
    return count


class ChartValidationTests(unittest.TestCase):
    def test_source_is_required(self):
        with self.assertRaises(ValueError):
            C.validate([C.Bar("a", 1)], "")

    def test_missing_nan_and_negative_values_are_rejected(self):
        with self.assertRaises(ValueError):
            C.validate([C.Bar("a", None)], "src")  # type: ignore[arg-type]
        with self.assertRaises(ValueError):
            C.validate([C.Bar("a", float("nan"))], "src")
        with self.assertRaises(ValueError):
            C.validate([C.Bar("a", -3)], "src")

    def test_empty_and_duplicate_labels_are_rejected(self):
        with self.assertRaises(ValueError):
            C.validate([], "src")
        with self.assertRaises(ValueError):
            C.validate([C.Bar("a", 1), C.Bar("a", 2)], "src")


@unittest.skipUnless(HAS_FFMPEG, "ffmpeg not installed")
class ChartRenderTests(unittest.TestCase):
    def setUp(self):
        self._tmp = tempfile.TemporaryDirectory()
        self.dir = Path(self._tmp.name)

    def tearDown(self):
        self._tmp.cleanup()

    def test_bar_heights_in_png_match_the_data_ratio(self):
        bars = [C.Bar("A", 10), C.Bar("B", 20), C.Bar("C", 40)]
        out = C.chart_png(bars, "Test data set", self.dir / "chart.png", title="t")
        img = Image.open(out).convert("RGB")
        lay = C.compute_layout(3, img.width, img.height)
        heights = [_bar_pixels_height(img, r) for r in lay.rects]
        full = heights[2]
        self.assertGreater(full, 100)
        self.assertAlmostEqual(heights[0] / full, 0.25, delta=0.02)
        self.assertAlmostEqual(heights[1] / full, 0.5, delta=0.02)

    def test_animated_chart_ends_on_the_data(self):
        bars = [C.Bar("A", 10), C.Bar("B", 40)]
        out = C.chart_video(bars, "Test data set", self.dir / "chart.mp4", seconds=2.0, fps=30)
        probe = subprocess.run(["ffprobe", "-v", "error", "-show_entries", "format=duration",
                                "-of", "json", str(out)], capture_output=True, text=True, check=True)
        self.assertAlmostEqual(float(json.loads(probe.stdout)["format"]["duration"]), 2.0, delta=0.1)
        last = self.dir / "last.png"
        subprocess.run(["ffmpeg", "-hide_banner", "-loglevel", "error", "-y", "-sseof", "-0.05", "-i", str(out),
                        "-frames:v", "1", str(last)], check=True)
        img = Image.open(last).convert("RGB")
        lay = C.compute_layout(2, img.width, img.height)
        h0 = _bar_pixels_height(img, lay.rects[0])
        h1 = _bar_pixels_height(img, lay.rects[1])
        self.assertAlmostEqual(h0 / h1, 0.25, delta=0.05)


@unittest.skipUnless(HAS_FFMPEG, "ffmpeg not installed")
class MediaIndexTests(unittest.TestCase):
    def setUp(self):
        self._tmp = tempfile.TemporaryDirectory()
        self.dir = Path(self._tmp.name)
        # Portrait image with a visible pattern.
        portrait = Image.new("RGB", (540, 960), (30, 40, 60))
        d = ImageDraw.Draw(portrait)
        d.rectangle((100, 300, 440, 700), fill=(200, 160, 100))
        portrait.save(self.dir / "portrait.png")
        # Landscape image, and a resized copy of it (near-duplicate, different bytes).
        land = Image.new("RGB", (960, 540), (20, 80, 120))
        ImageDraw.Draw(land).ellipse((300, 150, 660, 390), fill=(230, 200, 90))
        land.save(self.dir / "land.png")
        land.resize((480, 270)).save(self.dir / "land_small.png")
        # Sidecar provenance for the portrait image.
        (self.dir / "portrait.png.json").write_text(
            json.dumps({"source": "own footage", "license": "owned"}), encoding="utf-8")
        # Short video with audio.
        subprocess.run(["ffmpeg", "-hide_banner", "-loglevel", "error", "-y", "-f", "lavfi", "-i",
                        "testsrc2=s=320x568:r=25:d=1.5", "-f", "lavfi", "-i", "sine=f=300:d=1.5",
                        "-c:v", "libx264", "-pix_fmt", "yuv420p", "-c:a", "aac", "-shortest",
                        str(self.dir / "clip.mp4")], check=True)

    def tearDown(self):
        self._tmp.cleanup()

    def test_scan_reads_dimensions_orientation_and_video_facts(self):
        assets = {Path(a.path).name: a for a in M.scan(self.dir)}
        self.assertEqual(assets["portrait.png"].orientation, "portrait")
        self.assertEqual(assets["land.png"].orientation, "landscape")
        clip = assets["clip.mp4"]
        self.assertEqual(clip.kind, "video")
        self.assertEqual(clip.fps, 25.0)
        self.assertTrue(clip.has_audio)
        self.assertAlmostEqual(clip.duration, 1.5, delta=0.1)

    def test_sidecar_provenance_is_read_and_missing_is_unknown(self):
        assets = {Path(a.path).name: a for a in M.scan(self.dir)}
        self.assertEqual(assets["portrait.png"].provenance["license"], "owned")
        self.assertEqual(assets["land.png"].provenance["license"], "unknown")
        self.assertIn("no provenance sidecar", assets["land.png"].notes)

    def test_near_duplicate_images_are_grouped(self):
        assets = M.scan(self.dir)
        groups = M.find_duplicates(assets)
        names = [sorted(Path(p).name for p in g) for g in groups]
        self.assertIn(["land.png", "land_small.png"], names)
        self.assertNotIn(["portrait.png"], names)

    def test_ranking_prefers_requested_orientation_and_pick_skips_duplicates(self):
        assets = M.scan(self.dir)
        ranked = M.rank(assets, orientation="portrait", kind="image")
        self.assertEqual(Path(ranked[0][1].path).name, "portrait.png")
        picked = M.pick_diverse(ranked, count=3)
        names = [Path(a.path).name for a in picked]
        self.assertFalse({"land.png", "land_small.png"} <= set(names))


if __name__ == "__main__":
    unittest.main()
