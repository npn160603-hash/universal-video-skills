import json
import unittest
from fractions import Fraction
from pathlib import Path

import jsonschema
from jsonschema import Draft202012Validator

from uvs import director as D
from uvs import timeline as T
from uvs.captions import Word

ROOT = Path(__file__).resolve().parents[2]
SCHEMAS = ROOT / "schemas"
DEMO_SPEC = ROOT / "examples" / "demo_pipeline" / "spec.json"
DEMO_WORDS = ROOT / "examples" / "demo_caption" / "words.json"


def schema(name):
    return json.loads((SCHEMAS / name).read_text(encoding="utf-8"))


def check(name, instance):
    Draft202012Validator(schema(name)).validate(instance)


class SchemaFileTests(unittest.TestCase):
    def test_every_schema_is_a_valid_draft_2020_12_schema(self):
        for p in SCHEMAS.glob("*.schema.json"):
            with self.subTest(schema=p.name):
                Draft202012Validator.check_schema(json.loads(p.read_text(encoding="utf-8")))


class SchemaInstanceTests(unittest.TestCase):
    def test_demo_pipeline_spec_matches_project_schema(self):
        check("project.schema.json", json.loads(DEMO_SPEC.read_text(encoding="utf-8")))

    def test_project_schema_rejects_unknown_genre_and_extra_keys(self):
        good = json.loads(DEMO_SPEC.read_text(encoding="utf-8"))
        with self.assertRaises(jsonschema.ValidationError):
            check("project.schema.json", {**good, "genre": "reality_tv"})
        with self.assertRaises(jsonschema.ValidationError):
            check("project.schema.json", {**good, "bogus": 1})

    def test_director_scenes_match_scene_schema(self):
        from uvs.captions import load_words
        plan = D.plan(load_words(DEMO_WORDS), "real_life_storytelling", "demo")
        for scene in plan["scenes"]:
            with self.subTest(scene=scene["id"]):
                check("scene.schema.json", scene)

    def test_timeline_json_matches_timeline_schema(self):
        tl = T.Timeline(fps=Fraction(30000, 1001), width=1080, height=1920, tracks=[
            T.Track("video", "main", [
                T.Clip("a", "/x.mp4", start=0, duration=30),
                T.Clip("b", "/y.mp4", start=15, duration=30, transition="dissolve", transition_frames=15)]),
            T.Track("audio", "voice", [T.Clip("v", "/v.wav", start=0, duration=60, gain_db=-1.0)]),
        ])
        check("timeline.schema.json", T.timeline_to_dict(tl))

    def test_timeline_schema_rejects_bad_fps_and_unknown_transition(self):
        data = T.timeline_to_dict(T.Timeline(fps=Fraction(30), width=16, height=16, tracks=[]))
        data["fps"] = "thirty"
        with self.assertRaises(jsonschema.ValidationError):
            check("timeline.schema.json", data)
        bad = {"fps": "30", "width": 16, "height": 16, "tracks": [{"kind": "video", "clips": [
            {"id": "a", "source": "x", "duration": 5, "transition": "wipe_left"}]}]}
        with self.assertRaises(jsonschema.ValidationError):
            check("timeline.schema.json", bad)

    def test_animation_and_effect_schemas(self):
        check("animation.schema.json", {"keyframes": [
            {"time": 0, "value": [0, 100], "easing": "ease_out"},
            {"time": 1.5, "value": [50, 0]}]})
        with self.assertRaises(jsonschema.ValidationError):
            check("animation.schema.json", {"keyframes": [{"time": 0, "value": 1, "easing": "wobble"}]})
        check("effect.schema.json", {"look": "warm_lifestyle", "intensity": "subtle"})
        with self.assertRaises(jsonschema.ValidationError):
            check("effect.schema.json", {"look": "neon_tv"})


class SchemaSyncTests(unittest.TestCase):
    """Enum lists in the schemas must match the code registries, so they cannot drift apart."""

    def test_genre_and_look_enums_match_code(self):
        proj = schema("project.schema.json")
        self.assertEqual(set(proj["properties"]["genre"]["enum"]), set(D.GENRES))
        eff = schema("effect.schema.json")
        from uvs import grade as G
        self.assertEqual(set(eff["properties"]["look"]["enum"]), set(G.LOOKS))
        self.assertEqual(set(eff["properties"]["intensity"]["enum"]), set(G.INTENSITY))


if __name__ == "__main__":
    unittest.main()
