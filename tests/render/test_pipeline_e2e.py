"""End-to-end run of the pipeline on the demo spec (about 80 seconds with ffmpeg)."""
import shutil
import tempfile
import unittest
from pathlib import Path

from uvs import pipeline as P

ROOT = Path(__file__).resolve().parents[2]
SPEC = ROOT / "examples" / "demo_pipeline" / "spec.json"
HAS_FFMPEG = shutil.which("ffmpeg") is not None and shutil.which("ffprobe") is not None


@unittest.skipUnless(HAS_FFMPEG, "ffmpeg not installed")
class PipelineEndToEndTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls._tmp = tempfile.TemporaryDirectory()
        cls.out = Path(cls._tmp.name) / "run"
        cls.report = P.run(SPEC, cls.out)

    @classmethod
    def tearDownClass(cls):
        cls._tmp.cleanup()

    def test_pipeline_produces_a_passing_9x16_video_with_audio(self):
        self.assertEqual(self.report["qa_overall"], "pass")
        final = Path(self.report["final"])
        self.assertTrue(final.exists())
        self.assertAlmostEqual(self.report["duration_seconds"], 9.35, delta=0.05)

    def test_transitions_applied_match_the_plan_and_are_not_random(self):
        # Scene 1 has no incoming transition. Scenes 2 and 3 are both emotional, so both dissolve.
        self.assertEqual(self.report["transitions"]["dissolve"], 2)
        self.assertEqual(self.report["transitions"]["dip_black"], 0)
        self.assertEqual(self.report["transitions"]["cut"], 0)
        self.assertEqual(self.report["scenes"], 3)

    def test_every_stand_in_is_listed_and_no_real_media_is_claimed(self):
        text = " ".join(self.report["stand_ins"])
        self.assertIn("synthetic", text)
        self.assertIn("not speech", text)
        self.assertIn("not real footage", text)

    def test_decision_record_explains_choices(self):
        decisions = self.report["decisions"]
        self.assertTrue(any("dissolve" in d for d in decisions))
        self.assertTrue(any("style lock" in d for d in decisions))

    def test_report_files_are_written(self):
        for name in ("director_plan.json", "captions.ass", "timeline.mp4", "graded.mp4",
                     "audio_mix.m4a", "final.mp4", "qa_report.json", "pipeline_report.json"):
            self.assertTrue((self.out / name).exists(), name)


if __name__ == "__main__":
    unittest.main()
