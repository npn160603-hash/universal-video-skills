"""Automated QA: timeline checks, heuristics, safe repairs, reports (no ffmpeg)."""
import unittest

from uvs.autoqa import (qa_edit_plan, creative_heuristics, repair_timeline_timing, run_safe_repairs,
                        repair_caption_margins, QABundle, full_qa, AutoQAError, TimelineIssue,
                        HeuristicScore, BOUNDED_MAX)


def plan(*triples):
    """triples: (scene_id, start_frame, duration_frames, visual, transition)."""
    return {"instructions": [
        {"scene_id": s, "start_frame": sf, "duration_frames": df, "visual": v, "transition": t}
        for s, sf, df, v, t in triples]}


class TimelineQATests(unittest.TestCase):
    def test_clean_plan_has_no_issues(self):
        p = plan(("S1", 0, 30, "medium", "cut"), ("S2", 30, 30, "wide", "cut"))
        self.assertEqual(qa_edit_plan(p), [])

    def test_overlap_and_gap_detected(self):
        p = plan(("S1", 0, 30, "medium", "cut"), ("S2", 20, 30, "wide", "cut"),
                 ("S3", 80, 30, "chart", "cut"))
        codes = {i.code for i in qa_edit_plan(p)}
        self.assertIn("overlap", codes)
        self.assertIn("gap", codes)

    def test_bad_duration_detected(self):
        p = plan(("S1", 0, 0, "medium", "cut"))
        self.assertTrue(any(i.code == "bad_duration" for i in qa_edit_plan(p)))


class RepairTests(unittest.TestCase):
    def test_timing_repair_removes_issues_on_a_copy(self):
        p = plan(("S1", 0, 30, "a", "cut"), ("S2", 20, 30, "b", "cut"), ("S3", 80, 30, "c", "cut"))
        fixed, log = repair_timeline_timing(p)
        self.assertEqual(qa_edit_plan(fixed), [])
        self.assertTrue(log)
        # original preserved
        self.assertEqual(p["instructions"][1]["start_frame"], 20)

    def test_repair_clamps_zero_duration(self):
        p = plan(("S1", 0, 0, "a", "cut"))
        fixed, _ = repair_timeline_timing(p)
        self.assertEqual(fixed["instructions"][0]["duration_frames"], 1)

    def test_safe_repairs_are_bounded(self):
        # Even a pathological plan cannot loop forever.
        p = plan(("S1", 5, 10, "a", "cut"), ("S2", 2, 10, "b", "cut"))
        fixed, log = run_safe_repairs(p, max_passes=BOUNDED_MAX)
        self.assertEqual(qa_edit_plan(fixed), [])

    def test_caption_margin_repair_is_bounded(self):
        margin, log = repair_caption_margins(True, 300, max_tries=5)
        self.assertGreater(margin, 300)
        self.assertLessEqual(len(log), 5)

    def test_loudness_repair_refuses_in_place(self):
        with self.assertRaises(AutoQAError):
            from uvs.autoqa import repair_loudness
            repair_loudness("/tmp/x.mp4", "/tmp/x.mp4")


class HeuristicTests(unittest.TestCase):
    def test_diversity_higher_for_varied_visuals(self):
        varied = plan(("S1", 0, 30, "a", "cut"), ("S2", 30, 30, "b", "cut"), ("S3", 60, 30, "c", "cut"))
        same = plan(("S1", 0, 30, "a", "cut"), ("S2", 30, 30, "a", "cut"), ("S3", 60, 30, "a", "cut"))
        dv = next(h for h in creative_heuristics(varied) if h.name == "scene_diversity")
        ds = next(h for h in creative_heuristics(same) if h.name == "scene_diversity")
        self.assertGreater(dv.score, ds.score)

    def test_transition_variety_penalises_repeats(self):
        repeated = plan(("S1", 0, 30, "a", "dissolve"), ("S2", 30, 30, "b", "dissolve"),
                        ("S3", 60, 30, "c", "dissolve"))
        varied = plan(("S1", 0, 30, "a", "cut"), ("S2", 30, 30, "b", "dissolve"),
                      ("S3", 60, 30, "c", "cut"))
        hr = next(h for h in creative_heuristics(repeated) if h.name == "transition_variety")
        hv = next(h for h in creative_heuristics(varied) if h.name == "transition_variety")
        self.assertLess(hr.score, hv.score)

    def test_heuristics_labeled_as_judgement(self):
        for h in creative_heuristics(plan(("S1", 0, 30, "a", "cut"))):
            self.assertIsInstance(h, HeuristicScore)


class ReportTests(unittest.TestCase):
    def test_bundle_overall_and_markdown(self):
        p = plan(("S1", 0, 30, "a", "cut"), ("S2", 20, 30, "b", "cut"))  # overlap -> fail
        bundle = full_qa(edit_plan=p)
        self.assertEqual(bundle._overall(), "fail")
        md = bundle.to_markdown()
        self.assertIn("Automated QA report", md)
        self.assertIn("heuristic", md.lower())

    def test_clean_plan_passes(self):
        p = plan(("S1", 0, 30, "a", "cut"), ("S2", 30, 40, "b", "cut"))
        self.assertEqual(full_qa(edit_plan=p)._overall(), "pass")


if __name__ == "__main__":
    unittest.main()
