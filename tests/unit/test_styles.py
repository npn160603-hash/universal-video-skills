"""Ten editing presets, Style Lock, validation, determinism (Phase 10)."""
import unittest

from uvs.styles import (STYLES, STYLE_NAMES, VideoStyle, SafeArea, StyleLock, validate_style,
                        StyleError)
from uvs import grade as G
from uvs.captions import STYLES as CAPTION_STYLES

REQUIRED = {"cinematic_documentary", "emotional_storytelling", "modern_lifestyle",
            "psychology_explainer", "educational_shorts", "viral_storytelling",
            "minimal_premium", "investigative_documentary", "travel_story",
            "motion_graphics_explainer"}

REQUIRED_FIELDS = {"narrative_structure", "shot_duration_strategy", "target_shot_seconds",
                   "cut_frequency", "transition_policy", "typography", "camera_movement",
                   "easing_language", "animation_intensity", "visual_effects", "color_grade",
                   "color_intensity", "broll_preference", "music_direction", "sfx_intensity",
                   "map_style", "infographic_theme", "safe_area"}


class PresetCompletenessTests(unittest.TestCase):
    def test_exactly_the_ten_required_presets(self):
        self.assertEqual(set(STYLES), REQUIRED)

    def test_every_preset_defines_every_required_field(self):
        for name, s in STYLES.items():
            with self.subTest(style=name):
                d = s.to_dict()
                self.assertTrue(REQUIRED_FIELDS <= set(d), REQUIRED_FIELDS - set(d))

    def test_every_preset_validates(self):
        for name in STYLE_NAMES:
            with self.subTest(style=name):
                validate_style(STYLES[name])

    def test_presets_reference_real_looks_and_caption_styles(self):
        for s in STYLES.values():
            self.assertIn(s.color_grade, G.LOOKS)
            self.assertIn(s.typography, CAPTION_STYLES)


class ValidationTests(unittest.TestCase):
    def _base(self, **kw):
        base = dict(name="t", narrative_structure="x", shot_duration_strategy="y",
                    target_shot_seconds=2.0, cut_frequency="low", transition_policy="clean_cuts",
                    typography="clean_modern", camera_movement="subtle", easing_language="ease_out",
                    animation_intensity="standard", visual_effects=frozenset(),
                    color_grade="documentary_natural", color_intensity="standard",
                    broll_preference="x", music_direction="neutral", sfx_intensity="low",
                    map_style="none", infographic_theme="dark")
        base.update(kw)
        return VideoStyle(**base)

    def test_bad_values_are_rejected(self):
        for bad in (dict(typography="nope"), dict(color_grade="nope"), dict(color_intensity="nope"),
                    dict(music_direction="nope"), dict(cut_frequency="nope"),
                    dict(camera_movement="nope"), dict(easing_language="nope"),
                    dict(target_shot_seconds=0), dict(infographic_theme="neon")):
            with self.subTest(bad=bad):
                with self.assertRaises(StyleError):
                    validate_style(self._base(**bad))

    def test_safe_area_bounds(self):
        with self.assertRaises(StyleError):
            SafeArea(top=0.5).validate()


class StyleLockTests(unittest.TestCase):
    def test_resolve_unknown_raises(self):
        with self.assertRaises(StyleError):
            StyleLock.resolve("nonexistent")

    def test_every_scene_gets_the_same_locked_config(self):
        # This is the D-01 fix: the look does not depend on which scene is first.
        lock = StyleLock.resolve("investigative_documentary")
        configs = [lock.scene_config(i) for i in range(6)]
        self.assertEqual({c["color_grade"] for c in configs}, {"dark_investigative_v2"})
        self.assertEqual({c["caption_style"] for c in configs}, {"documentary_minimal"})
        self.assertEqual([c["scene_index"] for c in configs], list(range(6)))

    def test_lock_is_deterministic(self):
        self.assertEqual(StyleLock.resolve("viral_storytelling").signature(),
                         StyleLock.resolve("viral_storytelling").signature())

    def test_distinct_styles_differ(self):
        self.assertNotEqual(StyleLock.resolve("viral_storytelling").signature(),
                            StyleLock.resolve("minimal_premium").signature())

    def test_look_filter_builds(self):
        self.assertIsInstance(StyleLock.resolve("travel_story").look_filter(), str)


class StyleContrastTests(unittest.TestCase):
    def test_viral_is_faster_than_documentary(self):
        self.assertLess(STYLES["viral_storytelling"].target_shot_seconds,
                        STYLES["cinematic_documentary"].target_shot_seconds)

    def test_cut_frequencies_span_the_range(self):
        freqs = {s.cut_frequency for s in STYLES.values()}
        self.assertTrue({"low", "medium", "high"} <= freqs)


if __name__ == "__main__":
    unittest.main()
