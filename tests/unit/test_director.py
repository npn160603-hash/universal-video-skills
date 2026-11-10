import json
import unittest
from pathlib import Path

from uvs import director as D
from uvs.captions import Word

ROOT = Path(__file__).resolve().parents[2]
DEMO = ROOT / "examples" / "demo_caption" / "words.json"


def sentence(text, start, wps=2.5):
    """Evenly timed words for one sentence starting at `start`. Returns words and end time."""
    tokens = text.split()
    step = 1.0 / wps
    words = []
    t = start
    for tok in tokens:
        words.append(Word(tok, round(t, 3), round(t + step * 0.8, 3)))
        t += step
    return words, t


def build(*sentences, wps=2.5):
    words, t = [], 0.0
    for s in sentences:
        ws, t = sentence(s, t + 0.2, wps)
        words += ws
    return words


class SegmentTests(unittest.TestCase):
    def test_splits_on_sentence_ends(self):
        words = build("We walked home together.", "It was late and cold outside.")
        scenes = D.segment_scenes(words)
        self.assertEqual(len(scenes), 2)

    def test_merges_very_short_scene_into_previous(self):
        words = build("This is a longer opening sentence here.", "Yes.")
        scenes = D.segment_scenes(words)
        self.assertEqual(len(scenes), 1)

    def test_long_scene_splits_at_clause_when_possible(self):
        text = "We packed the bags, then drove for hours through the rain and " \
               "stopped at a small roadside diner where nobody spoke much at all today"
        words = build(text, wps=3.0)
        scenes = D.segment_scenes(words)
        self.assertGreaterEqual(len(scenes), 2)
        for s in scenes:
            self.assertGreaterEqual(s[-1].end - s[0].start, D.DirectorConfig().min_scene - 1e-6)


class RuleTests(unittest.TestCase):
    def test_emotional_scene_is_slow_dissolve_with_low_music(self):
        words = build("Grandma kept the old kitchen warm for everyone who came home.", wps=1.6)
        p = D.plan(words, "personal_experience_life_lessons", "t")
        scene = p["scenes"][0]
        self.assertEqual(scene["pacing"], "SLOW")
        self.assertEqual(scene["transition"], "dissolve")
        self.assertLessEqual(scene["music_level"], 0.22)
        self.assertTrue(any("dissolve" in d for d in scene["decisions"]))

    def test_informational_fast_scene_is_cut(self):
        words = build("The engine converts heat into motion with a simple cycle of valves.", wps=4.0)
        scene = D.plan(words, "educational_explainer", "t")["scenes"][0]
        self.assertEqual(scene["pacing"], "FAST")
        self.assertEqual(scene["transition"], "cut")
        self.assertEqual(scene["caption_style"], "bold_shorts")

    def test_documentary_prefers_continuity_dissolve(self):
        words = build("In 1921 the treaty was signed in a small hall.", wps=2.5)
        scene = D.plan(words, "historical_documentary", "t")["scenes"][0]
        self.assertEqual(scene["transition"], "dissolve")

    def test_turning_point_in_tension_scene_dips_to_black_and_gets_one_sfx(self):
        words = build("They kept the secret for years, but then the truth came out!", wps=2.2)
        p = D.plan(words, "mystery_investigative", "t")
        turning = [s for s in p["scenes"] if s["turning_point"]]
        self.assertTrue(turning)
        self.assertEqual(turning[0]["transition"], "dip_black")
        self.assertEqual(turning[0]["sfx"], ["soft_impact"])

    def test_sfx_only_appears_at_turning_points(self):
        words = build("We ate dinner.", "The dishes were washed.", "Then it rained all night long.")
        p = D.plan(words, "business_technology", "t")
        for s in p["scenes"]:
            if not s["turning_point"]:
                self.assertEqual(s["sfx"], [])

    def test_every_scene_has_a_decision_record(self):
        words = build("Hello there friend.", "This is the second line.", wps=2.5)
        for s in D.plan(words, "short_lifestyle", "t")["scenes"]:
            self.assertGreaterEqual(len(s["decisions"]), 1)


class DeterminismTests(unittest.TestCase):
    def test_same_input_gives_identical_plan(self):
        a = D.plan(DEMO, "real_life_storytelling", "demo")
        b = D.plan(DEMO, "real_life_storytelling", "demo")
        self.assertEqual(json.dumps(a, sort_keys=True), json.dumps(b, sort_keys=True))

    def test_demo_plan_covers_all_words_in_order(self):
        p = D.plan(DEMO, "real_life_storytelling", "demo")
        scenes = p["scenes"]
        self.assertEqual(scenes[0]["start"], 0.2)
        for a, b in zip(scenes, scenes[1:]):
            self.assertLessEqual(a["end"], b["start"] + 1e-6)
        self.assertAlmostEqual(p["duration"], 8.95, places=2)

    def test_unsupported_genre_raises(self):
        with self.assertRaises(KeyError):
            D.plan(DEMO, "reality_tv", "t")

    def test_empty_input_raises(self):
        with self.assertRaises(ValueError):
            D.plan([], "real_life_storytelling", "t")


if __name__ == "__main__":
    unittest.main()
