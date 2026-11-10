import json
import unittest

from uvs import narrative as N
from uvs.captions import Word

REFLECTIVE = ("I remember the kitchen at home. My grandma used to cook there every morning. "
              "She is gone now, and I miss those quiet years. But I think about her often. "
              "Maybe love stays, even when people leave. Subscribe for more stories.")
DATA = ("In 2023 the city built 40 new schools. Enrollment rose from 12000 to 18000 students. "
        "But only 25 percent of teachers were trained. Why did this happen? "
        "Hanoi and Tokyo both faced the same problem. We learned that funding matters most.")
FAST = ("Stop waiting. Start today. Quick wins matter now. You must act immediately! "
        "Every hour counts. Build the habit now! Go!")


def timed(text: str, wps: float = 2.4) -> list[Word]:
    out, t, dt = [], 0.0, 1.0 / wps
    for tok in text.split():
        out.append(Word(tok, round(t, 3), round(t + dt * 0.9, 3)))
        t += dt
    return out


class ValidationTests(unittest.TestCase):
    def test_empty_words_are_refused(self):
        self.assertEqual(N.validate_words([]), ["no words: provide at least one timed word"])
        with self.assertRaises(ValueError):
            N.build([], "educational_explainer")

    def test_out_of_order_words_are_reported(self):
        words = [Word("a", 1.0, 1.5), Word("b", 0.5, 0.9)]
        problems = " | ".join(N.validate_words(words))
        self.assertIn("starts before the previous word", problems)

    def test_word_type_itself_refuses_empty_text_and_inverted_timing(self):
        with self.assertRaises(ValueError):
            Word("   ", 0.0, 0.5)
        with self.assertRaises(ValueError):
            Word("c", 3.0, 2.5)

    def test_unknown_genre_raises_key_error(self):
        with self.assertRaises(KeyError):
            N.build(timed(REFLECTIVE), "not_a_genre")


class AnalysisTests(unittest.TestCase):
    def test_reflective_script_is_read_as_reflective_with_warm_hook(self):
        plan = N.build(timed(REFLECTIVE), "real_life_storytelling", "r")
        a = plan["analysis"]
        self.assertEqual(a["tone"], "reflective")
        self.assertIn("move the viewer", a["objective"])
        self.assertEqual(a["hook"]["scene"], plan["scenes"][0]["id"])
        self.assertEqual(a["resolution"]["scene"], plan["scenes"][-1]["id"])
        self.assertEqual(len(a["emotional_development"]), len(plan["scenes"]))

    def test_call_to_action_detected_when_present_and_null_when_absent(self):
        with_cta = N.build(timed(REFLECTIVE), "real_life_storytelling")["analysis"]["call_to_action"]
        without = N.build(timed(DATA), "educational_explainer")["analysis"]["call_to_action"]
        self.assertEqual(with_cta, "Subscribe")
        self.assertIsNone(without)

    def test_audience_is_not_invented(self):
        self.assertEqual(N.build(timed(DATA), "educational_explainer")["analysis"]["audience"], "not supplied")
        self.assertEqual(N.build(timed(DATA), "educational_explainer", audience="students")["analysis"]["audience"],
                         "students")

    def test_numeric_tokens_and_topic_keywords(self):
        a = N.build(timed(DATA), "educational_explainer")["analysis"]
        self.assertIn("2023", a["key_events"]["numeric_tokens"])
        self.assertIn("40", a["key_events"]["numeric_tokens"])
        self.assertFalse(set(a["topic_keywords"]) & N.STOPWORDS)

    def test_turning_points_reference_real_scenes(self):
        plan = N.build(timed(DATA), "educational_explainer")
        ids = {s["id"] for s in plan["scenes"]}
        self.assertTrue(set(plan["analysis"]["turning_points"]) <= ids)


class StructureAndActsTests(unittest.TestCase):
    def test_question_script_gets_question_structure(self):
        self.assertEqual(N.choose_structure(timed("Why? How? It works like this.")),
                         "question_explanation_evidence_conclusion")

    def test_tension_with_two_turns_gets_setup_structure(self):
        words = timed("A secret waited. But the danger grew. Suddenly the truth surfaced. However it ended.")
        self.assertEqual(N.choose_structure(words), "setup_tension_twist_resolution")

    def test_problem_with_discovery_gets_problem_structure(self):
        words = timed("We struggled with the problem. Then we discovered the fix and changed.")
        self.assertEqual(N.choose_structure(words), "problem_struggle_discovery_change")

    def test_default_structure_is_hook_context(self):
        self.assertEqual(N.choose_structure(timed("Plain words here only.")),
                         "hook_context_conflict_revelation_payoff")

    def test_beats_cover_all_labels_in_order(self):
        beats = N.assign_beats(10, ["A", "B", "C"])
        self.assertEqual(beats[0], "A")
        self.assertEqual(beats[-1], "C")
        self.assertEqual(beats, sorted(beats))

    def test_acts_are_three_ordered_groups_covering_every_scene(self):
        plan = N.build(timed(REFLECTIVE), "real_life_storytelling")
        labels = [a["label"] for a in plan["acts"]]
        self.assertEqual(labels, ["Act 1: setup", "Act 2: confrontation", "Act 3: resolution"])
        covered = [sid for a in plan["acts"] for sid in a["scenes"]]
        self.assertEqual(covered, [s["id"] for s in plan["scenes"]])


class PacingAndShotTests(unittest.TestCase):
    def test_reflective_script_is_not_forced_into_fast_editing(self):
        slow = N.build(timed(REFLECTIVE), "real_life_storytelling")["summary"]["mean_target_shot_seconds"]
        fast = N.build(timed(FAST), "self_improvement_motivational")["summary"]["mean_target_shot_seconds"]
        self.assertGreater(slow, 3.0)
        self.assertLess(fast, 2.0)
        self.assertGreater(slow, fast + 1.0)

    def test_chart_chosen_for_numeric_informational_scene(self):
        plan = N.build(timed(DATA), "educational_explainer")
        self.assertEqual(plan["scenes"][0]["visual"], "chart")
        rejected = plan["scenes"][0]["decision"]["rejected_alternatives"]
        self.assertTrue(rejected)  # other conditions were considered, with reasons
        self.assertTrue(all("reason" in r for r in rejected))

    def test_map_chosen_when_documentary_names_a_location(self):
        words = timed("Our journey begins in Hanoi. The road is long and quiet. We reach the coast at dawn.")
        plan = N.build(words, "geography_travel")
        self.assertEqual(plan["scenes"][0]["visual"], "map")

    def test_close_up_for_grief_scene(self):
        words = timed("She is gone and I miss her so much. The tears will not stop.")
        plan = N.build(words, "real_life_storytelling")
        self.assertEqual(plan["scenes"][0]["visual"], "close_up")

    def test_turning_point_gets_detail_insert_shot_when_scene_has_several_shots(self):
        # One long sentence with a turn word at its start; the director splits it at clause breaks.
        long_turn = ("But the day changed, and we walked the long road through the quiet old town, "
                     "remembering each stop along the way, and the light faded slowly over the river.")
        plan = N.build(timed(long_turn, wps=2.0), "mystery_investigative")
        multi_turn = [s for s in plan["scenes"] if s["turning_point"] and len(s["shots"]) >= 2]
        self.assertTrue(multi_turn, "test input must give a turning-point scene with several shots")
        for s in multi_turn:
            self.assertEqual(s["shots"][-1]["visual"], "detail")

    def test_shots_partition_each_scene_in_time(self):
        plan = N.build(timed(REFLECTIVE), "real_life_storytelling")
        for s in plan["scenes"]:
            self.assertAlmostEqual(s["shots"][0]["start"], s["start"], places=3)
            self.assertAlmostEqual(s["shots"][-1]["end"], s["end"], places=3)
            for a, b in zip(s["shots"], s["shots"][1:]):
                self.assertLessEqual(a["end"], b["start"] + 1e-6)


class CinematicGrammarTests(unittest.TestCase):
    def test_emotional_dissolve_produces_j_cut(self):
        plan = N.build(timed(REFLECTIVE), "real_life_storytelling")
        types = {a["type"] for a in plan["cinematic"]["applied"]}
        self.assertIn("j_cut", types)

    def test_sentence_end_cut_is_motivated_and_same_look_is_continuity(self):
        plan = N.build(timed(DATA), "educational_explainer")
        types = {a["type"] for a in plan["cinematic"]["applied"]}
        self.assertIn("motivated_cut", types)
        self.assertIn("continuity", types)

    def test_fast_scene_with_short_shots_gets_rhythmic_montage(self):
        words = timed("Stop waiting. Start today. Quick wins matter now. You must act immediately! "
                      "Every hour counts. Build the habit now! Go!", wps=4.0)
        plan = N.build(words, "self_improvement_motivational")
        scene = next(s for s in plan["scenes"] if s["pacing"] == "FAST")
        short = [sh for sh in scene["shots"] if sh["duration_s"] < 1.5]
        self.assertGreaterEqual(len(short), 3, "test input must produce a run of short shots")
        types = {a["type"] for a in plan["cinematic"]["applied"]}
        self.assertIn("rhythmic_montage", types)

    def test_unimplemented_techniques_are_declared_not_faked(self):
        plan = N.build(timed(DATA), "educational_explainer")
        self.assertEqual(set(plan["cinematic"]["not_applied"]), {"match_cut", "parallel_montage", "cross_cutting"})
        applied_types = {a["type"] for a in plan["cinematic"]["applied"]}
        self.assertFalse(applied_types & set(plan["cinematic"]["not_applied"]))


class ShotVocabularyTests(unittest.TestCase):
    def test_graphics_is_chosen_for_a_numberless_explainer_sentence(self):
        words = timed("The cell membrane controls what enters and what leaves the living structure.")
        plan = N.build(words, "educational_explainer")
        self.assertEqual(plan["scenes"][0]["visual"], "graphics")

    def test_wide_is_chosen_for_reflective_documentary_beat_without_location(self):
        plan = N.build(timed("The first light rose over the empty fields. We stood and watched it slowly. "
                             "Maybe that was enough for the morning."), "historical_documentary")
        visuals = [s["visual"] for s in plan["scenes"][1:]]
        self.assertIn("wide", visuals)

    def test_reaction_cut_after_a_question_and_a_short_reply(self):
        plan = N.build(timed("Why did it fail? Look closer now."), "educational_explainer")
        types = {a["type"] for a in plan["cinematic"]["applied"]}
        self.assertIn("reaction_cut", types)


class AttentionBudgetTests(unittest.TestCase):
    def test_dense_numeric_scene_is_over_budget_with_an_action(self):
        plan = N.build(timed(DATA), "educational_explainer")
        over = [s for s in plan["scenes"] if s["attention"]["over_budget"]]
        self.assertTrue(over)
        for s in over:
            self.assertTrue(s["attention"]["actions"], "over-budget scene must suggest a reduction")
            self.assertGreater(s["attention"]["load"], s["attention"]["budget"])

    def test_calm_scene_is_within_budget(self):
        plan = N.build(timed("We sat by the window. The rain was soft. Nothing needed saying."),
                       "real_life_storytelling")
        self.assertFalse(plan["scenes"][0]["attention"]["over_budget"])
        self.assertEqual(plan["scenes"][0]["attention"]["actions"], [])

    def test_components_are_reported(self):
        comps = N.build(timed(DATA), "educational_explainer")["scenes"][0]["attention"]["components"]
        self.assertEqual(set(comps), {"caption_density", "movement", "background", "overlays", "information"})


class DecisionRecordTests(unittest.TestCase):
    REQUIRED = {"scene_id", "selected", "emotional_justification", "rejected_alternatives", "confidence", "uncertainty"}

    def test_every_scene_has_a_complete_decision_record(self):
        plan = N.build(timed(REFLECTIVE), "real_life_storytelling")
        for s in plan["scenes"]:
            d = s["decision"]
            self.assertTrue(self.REQUIRED <= set(d), d.keys())
            self.assertEqual(d["scene_id"], s["id"])
            self.assertTrue(0.0 <= d["confidence"] <= 1.0)
            self.assertEqual(set(d["selected"]) >= {"visual", "shot_count", "motion", "transition"}, True)

    def test_neutral_scene_reports_uncertainty_and_low_confidence(self):
        plan = N.build(timed("The table sits near the wall. A cup stands on it."), "news_explainer")
        d = plan["scenes"][0]["decision"]
        self.assertLess(d["confidence"], 0.5)
        self.assertTrue(d["uncertainty"])

    def test_plan_is_deterministic_and_json_serializable(self):
        a = N.build(timed(REFLECTIVE), "real_life_storytelling", "r")
        b = N.build(timed(REFLECTIVE), "real_life_storytelling", "r")
        self.assertEqual(json.dumps(a, sort_keys=True), json.dumps(b, sort_keys=True))


class MultiGenreTests(unittest.TestCase):
    GENRES = ["real_life_storytelling", "educational_explainer", "historical_documentary",
              "geography_travel", "mystery_investigative", "self_improvement_motivational",
              "news_explainer", "business_technology"]

    def test_every_tested_genre_produces_a_complete_plan(self):
        script = REFLECTIVE + " " + DATA
        for genre in self.GENRES:
            with self.subTest(genre=genre):
                plan = N.build(timed(script), genre, genre)
                self.assertEqual(plan["genre"], genre)
                self.assertEqual(plan["summary"]["scenes"], len(plan["scenes"]))
                self.assertTrue(plan["scenes"])
                for s in plan["scenes"]:
                    self.assertIn(s["visual"], N.SHOT_TYPES + ("medium",))
                    self.assertTrue(s["shots"])
                    self.assertIn(s["motion"], N.MOTION_ENERGY)

    def test_genre_changes_the_plan(self):
        script = timed(DATA)
        fast = N.build(script, "self_improvement_motivational")["summary"]["mean_target_shot_seconds"]
        doc = N.build(script, "historical_documentary")["summary"]["mean_target_shot_seconds"]
        self.assertNotEqual(fast, doc)


if __name__ == "__main__":
    unittest.main()
