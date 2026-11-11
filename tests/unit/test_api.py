"""Local API: path safety, analysis, planning, styles, timeline, QA (no network)."""
import tempfile
import unittest
from pathlib import Path

from uvs.api import UVSApi, ApiError
from uvs.assets import AssetError

WORDS = [{"text": w, "start": i * 0.4, "end": i * 0.4 + 0.35}
         for i, w in enumerate("We learn to say no and everything changes for the better".split())]


class ApiTests(unittest.TestCase):
    def setUp(self):
        self._tmp = tempfile.TemporaryDirectory()
        self.api = UVSApi(self._tmp.name)

    def tearDown(self):
        self.api.jobs.shutdown()
        self._tmp.cleanup()

    def test_path_traversal_is_refused(self):
        for bad in ("../escape", "/etc/passwd", "a/../../b"):
            with self.subTest(bad=bad):
                with self.assertRaises((AssetError, ApiError)):
                    self.api._resolve(bad)

    def test_project_name_must_be_simple(self):
        self.assertEqual(self.api.create_project("demo")["project"], "demo")
        for bad in ("../x", "a/b", ".hidden"):
            with self.assertRaises(ApiError):
                self.api.create_project(bad)

    def test_analyze_and_plan(self):
        self.assertIn("tone", self.api.analyze_script(WORDS))
        plan = self.api.plan_narrative(WORDS, title="T")
        self.assertIn("scenes", plan)

    def test_bad_words_rejected(self):
        with self.assertRaises(ApiError):
            self.api.analyze_script([{"text": "x"}])  # missing timings

    def test_styles_and_select(self):
        self.assertEqual(len(self.api.list_styles()), 10)
        self.assertEqual(self.api.select_style("viral_storytelling")["color_grade"],
                         "high_contrast_editorial")
        with self.assertRaises(Exception):
            self.api.select_style("nope")

    def test_generate_timeline_and_qa(self):
        tl = self.api.generate_timeline(WORDS, "emotional_storytelling")
        self.assertIn("instructions", tl)
        self.assertTrue(self.api.qa_timeline(tl)["ok"])

    def test_generate_timeline_with_overrides(self):
        sid = self.api.plan_narrative(WORDS)["scenes"][0]["id"]
        tl = self.api.generate_timeline(WORDS, "modern_lifestyle", overrides={sid: {"transition": "dissolve"}})
        self.assertEqual(tl["decisions"][0]["selected"]["transition"], "dissolve")

    def test_info(self):
        info = self.api.info()
        self.assertEqual(info["api_version"], "1.0.0")
        self.assertIn("emotional_storytelling", info["styles"])


if __name__ == "__main__":
    unittest.main()
