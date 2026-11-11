"""AI editing decision engine: decisions, scoring, critical rules, overrides, regeneration."""
import unittest

from uvs.styles import StyleLock
from uvs.decision import (EditContext, Capabilities, EditDecision, decide, decide_scene, regenerate,
                          DECISION_FIELDS, SCORE_CRITERIA, DecisionError)


def scene(sid="S01", **kw):
    base = dict(id=sid, narrative_emotion="reflection", transition="cut", target_shot_seconds=2.5,
                visual="medium", music_level=0.3, attention={"load": 1.0, "budget": 2.0})
    base.update(kw)
    return base


def ctx(scenes, style="emotional_storytelling", **kw):
    cap = kw.pop("capabilities", Capabilities(broll_library=False))
    return EditContext(plan={"scenes": scenes, "duration": sum(1 for _ in scenes)},
                       style=StyleLock.resolve(style), capabilities=cap, **kw)


class DecisionShapeTests(unittest.TestCase):
    def test_every_scene_gets_all_decision_fields(self):
        ep = decide(ctx([scene("S01"), scene("S02")]))
        self.assertEqual(len(ep.decisions), 2)
        for d in ep.decisions:
            self.assertEqual(set(d.selected), set(DECISION_FIELDS))

    def test_every_decision_scores_all_criteria(self):
        d = decide(ctx([scene()])).decisions[0]
        self.assertEqual(set(d.scores), set(SCORE_CRITERIA))
        self.assertTrue(0 <= d.relevance_score <= 1)
        self.assertTrue(0 <= d.confidence <= 1)

    def test_decision_record_has_reason_and_parameters(self):
        d = decide(ctx([scene()])).decisions[0]
        self.assertTrue(d.reason)
        self.assertIn("look", d.parameters)
        self.assertIn("caption_style", d.parameters)

    def test_instructions_are_contiguous_frames(self):
        ep = decide(ctx([scene("S01"), scene("S02"), scene("S03")]))
        fs = [(i["start_frame"], i["duration_frames"]) for i in ep.instructions]
        for k in range(1, len(fs)):
            self.assertEqual(fs[k][0], fs[k - 1][0] + fs[k - 1][1])

    def test_empty_plan_rejected(self):
        with self.assertRaises(DecisionError):
            decide(EditContext(plan={"scenes": []}, style=StyleLock.resolve("minimal_premium")))


class CriticalRuleTests(unittest.TestCase):
    def test_dissolves_are_capped(self):
        scenes = [scene(f"S{i:02d}", transition="dissolve") for i in range(8)]
        ep = decide(ctx(scenes, capabilities=Capabilities(max_transition_fraction=0.5)))
        dissolves = sum(1 for i in ep.instructions if i["transition"] in ("dissolve", "dip_black"))
        self.assertLessEqual(dissolves, int(7 * 0.5))

    def test_irrelevant_footage_is_dropped(self):
        s = scene("S1", narrative_emotion="neutral", visual="medium")
        c = ctx([s], style="modern_lifestyle",
                capabilities=Capabilities(broll_library=True))
        c.media_matches = {"S1": 0.1}
        self.assertEqual(decide_scene(s, c).selected["broll"], "generated")

    def test_good_footage_is_used(self):
        s = scene("S1", narrative_emotion="neutral", visual="medium")
        c = ctx([s], style="modern_lifestyle", capabilities=Capabilities(broll_library=True))
        c.media_matches = {"S1": 0.8}
        self.assertEqual(decide_scene(s, c).selected["broll"], "footage")

    def test_over_budget_scene_drops_motion_graphics(self):
        s = scene("S1", narrative_emotion="tension", visual="graphics", turning_point=True,
                  attention={"load": 3.0, "budget": 2.0, "over_budget": True})
        d = decide_scene(s, ctx([s], style="educational_shorts"))
        self.assertFalse(d.selected["motion_graphics"])
        self.assertIn("attention budget", d.reason)

    def test_neutral_scene_gets_no_decorative_motion_graphics(self):
        s = scene("S1", narrative_emotion="neutral", visual="medium", turning_point=False)
        d = decide_scene(s, ctx([s], style="minimal_premium"))
        self.assertFalse(d.selected["motion_graphics"])

    def test_repeated_camera_is_varied(self):
        scenes = [scene("S01"), scene("S02")]
        ep = decide(ctx(scenes, style="travel_story"))   # dynamic camera
        cams = [d.selected["camera_animation"] for d in ep.decisions]
        self.assertNotEqual(cams[0], cams[1])

    def test_capability_gates_maps_and_charts(self):
        s_map = scene("S1", visual="map")
        s_chart = scene("S2", visual="chart")
        ep = decide(ctx([s_map, s_chart], style="educational_shorts",
                        capabilities=Capabilities(maps=False, charts=False)))
        self.assertFalse(ep.decisions[0].selected["map_usage"])
        self.assertFalse(ep.decisions[1].selected["chart_usage"])

    def test_reflective_quiet_scene_preserves_silence(self):
        s = scene("S1", narrative_emotion="reflection", music_level=0.1)
        d = decide_scene(s, ctx([s], style="emotional_storytelling"))
        self.assertEqual(d.selected["music_behavior"], "silent")
        self.assertEqual(d.selected["sound_effects"], "none")


class OverrideTests(unittest.TestCase):
    def test_override_replaces_a_field(self):
        s = scene("S1")
        ep = decide(ctx([s]), overrides={"S1": {"transition": "dip_black"}})
        self.assertEqual(ep.decisions[0].selected["transition"], "dip_black")
        self.assertIn("transition", ep.decisions[0].overridden_fields)

    def test_override_of_unknown_field_rejected(self):
        s = scene("S1")
        with self.assertRaises(DecisionError):
            decide(ctx([s]), overrides={"S1": {"nonsense": 1}})

    def test_regenerate_preserves_prior_overrides(self):
        s = scene("S1")
        first = decide(ctx([s]), overrides={"S1": {"caption_style": "bold_shorts"}})
        again = regenerate(ctx([s]), first)
        self.assertEqual(again.decisions[0].selected["caption_style"], "bold_shorts")
        self.assertIn("caption_style", again.decisions[0].overridden_fields)

    def test_regenerate_merges_new_overrides(self):
        s = scene("S1")
        first = decide(ctx([s]), overrides={"S1": {"caption_style": "bold_shorts"}})
        again = regenerate(ctx([s]), first, new_overrides={"S1": {"transition": "dip_black"}})
        self.assertEqual(again.decisions[0].selected["caption_style"], "bold_shorts")
        self.assertEqual(again.decisions[0].selected["transition"], "dip_black")


class DeterminismTests(unittest.TestCase):
    def test_same_input_gives_same_decisions(self):
        scenes = [scene("S01"), scene("S02", narrative_emotion="tension")]
        a = decide(ctx(scenes)).to_dict()
        b = decide(ctx(scenes)).to_dict()
        self.assertEqual(a, b)


class RealPlanIntegrationTests(unittest.TestCase):
    def test_decides_over_a_real_narrative_plan(self):
        from uvs import narrative as N
        from uvs.captions import Word
        text = ("We spend years saying yes to everyone. One day we learn to say no. "
                "Everything changes. The weight lifts. We breathe again. Boundaries protect us.")
        words = [Word(w, i * 0.4, i * 0.4 + 0.35) for i, w in enumerate(text.split())]
        plan = N.build(words, "real_life_storytelling", title="Boundaries")
        c = EditContext(plan=plan, style=StyleLock.resolve("emotional_storytelling"), fps=30)
        ep = decide(c)
        self.assertEqual(len(ep.decisions), len(plan["scenes"]))
        self.assertEqual([d.scene_id for d in ep.decisions], [s["id"] for s in plan["scenes"]])
        # every instruction references the locked style's look and caption
        for inst in ep.instructions:
            self.assertEqual(inst["look"], "soft_romantic_v2")
            self.assertEqual(inst["caption_style"], "emotional_storytelling")


if __name__ == "__main__":
    unittest.main()
