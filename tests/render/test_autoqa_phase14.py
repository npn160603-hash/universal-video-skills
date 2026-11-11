"""Phase 14 with real media: detect defects in deliberately broken videos; loudness repair."""
import shutil
import subprocess
import tempfile
import unittest
from pathlib import Path

from uvs import autoqa as Q
from uvs.qa import QAConfig
from uvs.audio_intel import measure_loudness

HAS_FFMPEG = shutil.which("ffmpeg") is not None and shutil.which("ffprobe") is not None


@unittest.skipUnless(HAS_FFMPEG, "ffmpeg not installed")
class DefectDetectionTests(unittest.TestCase):
    def setUp(self):
        self._tmp = tempfile.TemporaryDirectory()
        self.dir = Path(self._tmp.name)

    def tearDown(self):
        self._tmp.cleanup()

    def test_black_intro_is_detected(self):
        out = self.dir / "black.mp4"
        subprocess.run(["ffmpeg", "-hide_banner", "-loglevel", "error", "-y",
                        "-f", "lavfi", "-i", "color=c=black:s=320x240:d=1.5:r=15",
                        "-f", "lavfi", "-i", "testsrc2=s=320x240:d=1.5:r=15",
                        "-filter_complex", "[0][1]concat=n=2:v=1", "-c:v", "libx264", str(out)], check=True)
        report = Q.run_qa(out, QAConfig(expect_width=320, expect_height=240, expect_fps=15,
                                        expect_audio_codec=None, black_min_duration=0.5))
        self.assertIn(report.overall, {"warn", "fail"})
        self.assertTrue(any("black" in c.id.lower() for c in report.checks))

    def test_frozen_segment_is_detected(self):
        out = self.dir / "frozen.mp4"
        # a still image held for 2s = frozen frames
        subprocess.run(["ffmpeg", "-hide_banner", "-loglevel", "error", "-y",
                        "-f", "lavfi", "-i", "color=c=green:s=320x240:d=2:r=15",
                        "-c:v", "libx264", str(out)], check=True)
        report = Q.run_qa(out, QAConfig(expect_width=320, expect_height=240, expect_fps=15,
                                        expect_audio_codec=None, freeze_min_duration=1.0))
        self.assertTrue(any("freeze" in c.id.lower() or "frozen" in c.detail.lower()
                            for c in report.checks))


@unittest.skipUnless(HAS_FFMPEG, "ffmpeg not installed")
class LoudnessRepairTests(unittest.TestCase):
    def setUp(self):
        self._tmp = tempfile.TemporaryDirectory()
        self.dir = Path(self._tmp.name)

    def tearDown(self):
        self._tmp.cleanup()

    def test_quiet_file_is_brought_to_target_without_touching_original(self):
        quiet = self.dir / "quiet.mp4"
        subprocess.run(["ffmpeg", "-hide_banner", "-loglevel", "error", "-y",
                        "-f", "lavfi", "-i", "sine=440:d=1", "-f", "lavfi",
                        "-i", "color=c=blue:s=64x64:d=1:r=10",
                        "-filter_complex", "[0:a]volume=-30dB[a]", "-map", "[a]", "-map", "1:v",
                        "-c:v", "libx264", "-c:a", "aac", "-shortest", str(quiet)], check=True)
        before = measure_loudness(quiet).integrated_lufs
        fixed = self.dir / "fixed.mp4"
        result = Q.repair_loudness(quiet, fixed, target_lufs=-14)
        self.assertTrue(result.applied)
        self.assertTrue(quiet.exists())  # original preserved
        after = measure_loudness(fixed).integrated_lufs
        self.assertGreater(after, before)
        self.assertLess(abs(after - (-14)), 3.0)


if __name__ == "__main__":
    unittest.main()
