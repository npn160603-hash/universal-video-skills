"""Phase 15: representative demos render to valid A/V files; travel demo uses real geodata."""
import json
import os
import shutil
import subprocess
import tempfile
import unittest
from pathlib import Path

from uvs import demos as D
from uvs import maps as MAPS

HAS_FFMPEG = shutil.which("ffmpeg") is not None and shutil.which("ffprobe") is not None
HAS_GEODATA = bool(os.environ.get(MAPS.ENV_VAR)) and Path(os.environ.get(MAPS.ENV_VAR, "")).exists()


def _streams(path: Path) -> dict:
    pr = subprocess.run(["ffprobe", "-v", "error", "-show_entries",
                         "stream=codec_type,width,height:format=duration", "-of", "json", str(path)],
                        capture_output=True, text=True, check=True)
    meta = json.loads(pr.stdout)
    out = {s["codec_type"]: s for s in meta["streams"]}
    out["duration"] = float(meta["format"]["duration"])
    return out


@unittest.skipUnless(HAS_FFMPEG, "ffmpeg not installed")
class DemoRenderTests(unittest.TestCase):
    def setUp(self):
        self._tmp = tempfile.TemporaryDirectory()
        self.dir = Path(self._tmp.name)

    def tearDown(self):
        self._tmp.cleanup()

    def test_motion_graphics_demo_has_video_and_audio(self):
        r = D.demo_motion_graphics(self.dir / "F.mp4")
        s = _streams(self.dir / "F.mp4")
        self.assertIn("video", s)
        self.assertIn("audio", s)
        self.assertGreaterEqual(s["duration"], 3.0)
        self.assertTrue(r["technical"])

    def test_educational_demo_concatenates_chart_and_diagram(self):
        r = D.demo_educational(self.dir / "D.mp4")
        s = _streams(self.dir / "D.mp4")
        self.assertIn("audio", s)
        self.assertGreater(s["duration"], 4.0)  # chart + diagram
        self.assertTrue(any("illustrative" in x.lower() for x in r["stand_ins"]))

    def test_emotional_demo_is_labelled_technical(self):
        r = D.demo_emotional(self.dir / "A.mp4")
        self.assertTrue(r["technical"])
        self.assertTrue((self.dir / "A.mp4").exists())

    @unittest.skipUnless(HAS_GEODATA, "set UVS_NATURAL_EARTH_SHP for the real-map demo")
    def test_travel_demo_uses_real_geodata(self):
        r = D.demo_travel(self.dir / "B.mp4")
        self.assertTrue(r["real_geodata"])
        self.assertFalse(r["technical"])
        s = _streams(self.dir / "B.mp4")
        self.assertEqual((s["video"]["width"], s["video"]["height"]), (1280, 720))
        self.assertIn("audio", s)


if __name__ == "__main__":
    unittest.main()
