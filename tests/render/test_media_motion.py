"""Video motion (scene cuts), metric cache, sidecar freshness, and the retrieval CLI on real files."""
import json
import shutil
import subprocess
import tempfile
import unittest
from pathlib import Path
from unittest import mock

from PIL import Image

from uvs import media_index as M
from uvs import retrieval as R

HAS_FFMPEG = shutil.which("ffmpeg") is not None and shutil.which("ffprobe") is not None


def _ffmpeg(*args):
    subprocess.run(["ffmpeg", "-hide_banner", "-loglevel", "error", "-y", *args], check=True)


def _still_clip(path: Path, colour: str, seconds: float = 2.0):
    _ffmpeg("-f", "lavfi", "-i", f"color=c={colour}:s=320x240:d={seconds}:r=30",
            "-c:v", "libx264", "-pix_fmt", "yuv420p", str(path))


def _cut_clip(path: Path):
    _ffmpeg("-f", "lavfi", "-i", "color=c=red:s=320x240:d=1:r=30",
            "-f", "lavfi", "-i", "color=c=blue:s=320x240:d=1:r=30",
            "-filter_complex", "[0][1]concat=n=2:v=1:a=0", "-c:v", "libx264", "-pix_fmt", "yuv420p", str(path))


@unittest.skipUnless(HAS_FFMPEG, "ffmpeg not installed")
class MotionTests(unittest.TestCase):
    def setUp(self):
        self._tmp = tempfile.TemporaryDirectory()
        self.dir = Path(self._tmp.name)

    def tearDown(self):
        self._tmp.cleanup()

    def test_static_clip_has_no_cuts(self):
        clip = self.dir / "still.mp4"
        _still_clip(clip, "gray")
        a = M.index_file(clip)
        self.assertEqual(a.motion_per_second, 0.0)

    def test_hard_cut_is_counted_once(self):
        clip = self.dir / "cut.mp4"
        _cut_clip(clip)
        a = M.index_file(clip)
        self.assertAlmostEqual(a.motion_per_second, 0.5, delta=0.03)  # one cut over about two seconds

    def test_images_have_no_motion_value(self):
        img = self.dir / "a.png"
        Image.new("RGB", (16, 16), (1, 2, 3)).save(img)
        self.assertIsNone(M.index_file(img).motion_per_second)


@unittest.skipUnless(HAS_FFMPEG, "ffmpeg not installed")
class CacheTests(unittest.TestCase):
    def setUp(self):
        self._tmp = tempfile.TemporaryDirectory()
        self.dir = Path(self._tmp.name) / "media"
        self.cache = Path(self._tmp.name) / "cache"
        self.dir.mkdir()
        _cut_clip(self.dir / "cut.mp4")

    def tearDown(self):
        self._tmp.cleanup()

    def test_second_scan_reuses_cached_metrics(self):
        with mock.patch.object(M, "_motion", wraps=M._motion) as motion:
            first = M.scan(self.dir, self.cache)
            self.assertEqual(motion.call_count, 1)
            second = M.scan(self.dir, self.cache)
            self.assertEqual(motion.call_count, 1)
        self.assertEqual(first[0].motion_per_second, second[0].motion_per_second)
        self.assertEqual(first[0].duration, second[0].duration)

    def test_changed_file_is_measured_again(self):
        M.scan(self.dir, self.cache)
        _still_clip(self.dir / "cut.mp4", "green")
        with mock.patch.object(M, "_motion", wraps=M._motion) as motion:
            changed = M.scan(self.dir, self.cache)
        self.assertEqual(motion.call_count, 1)
        self.assertEqual(changed[0].motion_per_second, 0.0)

    def test_sidecar_text_is_never_served_from_cache(self):
        clip = self.dir / "cut.mp4"
        M.scan(self.dir, self.cache)
        clip.with_suffix(".mp4.json").write_text(json.dumps({"tags": ["city"], "license": "cc0"}),
                                                 encoding="utf-8")
        after = M.scan(self.dir, self.cache)
        self.assertEqual(after[0].tags, ["city"])
        self.assertEqual(after[0].provenance["license"], "cc0")

    def test_unreadable_cache_entry_is_ignored(self):
        M.scan(self.dir, self.cache)
        for f in self.cache.glob("*.json"):
            f.write_text("{not json", encoding="utf-8")
        with mock.patch.object(M, "_motion", wraps=M._motion) as motion:
            M.scan(self.dir, self.cache)
        self.assertEqual(motion.call_count, 1)


class RetrievalCliTests(unittest.TestCase):
    def setUp(self):
        self._tmp = tempfile.TemporaryDirectory()
        self.dir = Path(self._tmp.name) / "stock"
        self.dir.mkdir()
        Image.new("RGB", (32, 32), (9, 9, 9)).save(self.dir / "city_night.png")
        Image.new("RGB", (32, 48), (90, 90, 90)).save(self.dir / "forest.png")
        (self.dir / "city_night.png.json").write_text(json.dumps(
            {"source": "own shot", "license": "cc0", "tags": ["city", "night"]}), encoding="utf-8")

    def tearDown(self):
        self._tmp.cleanup()

    def test_query_writes_ranked_hits_to_file(self):
        out = Path(self._tmp.name) / "hits.json"
        code = R.main([str(self.dir), "--query", "night city", "--out", str(out)])
        self.assertEqual(code, 0)
        data = json.loads(out.read_text(encoding="utf-8"))
        self.assertEqual(len(data["hits"]), 1)
        self.assertTrue(data["hits"][0]["path"].endswith("city_night.png"))
        self.assertEqual(data["hits"][0]["missing"], [])

    def test_plan_mode_writes_assignments(self):
        plan = Path(self._tmp.name) / "plan.json"
        plan.write_text(json.dumps({"scenes": [
            {"id": "s1", "visual": "b_roll", "text": "a city at night"},
            {"id": "s2", "visual": "b_roll", "text": "deep forest trees"}]}), encoding="utf-8")
        out = Path(self._tmp.name) / "assign.json"
        R.main([str(self.dir), "--plan", str(plan), "--out", str(out)])
        data = json.loads(out.read_text(encoding="utf-8"))
        statuses = [r["status"] for r in data["scenes"]]
        self.assertEqual(statuses, ["matched", "unfilled"])  # forest has no tags, so no match

    def test_exactly_one_mode_is_required(self):
        import contextlib
        import io
        with contextlib.redirect_stderr(io.StringIO()), self.assertRaises(SystemExit):
            R.main([str(self.dir)])


if __name__ == "__main__":
    unittest.main()
