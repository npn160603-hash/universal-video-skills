"""Colour analysis, shot matching, QA and filter builders (numpy; no ffmpeg)."""
import unittest

import numpy as np

from uvs import color as C
from uvs import grade as G


def frame(mean, size=(60, 80), seed=0):
    rng = np.random.default_rng(seed)
    base = rng.normal(0, 18, (*size, 3))
    return np.clip(base + np.array(mean), 0, 255).astype(np.uint8)


class AnalysisTests(unittest.TestCase):
    def test_warmth_reflects_red_blue_ratio(self):
        warm = C.analyze_array(frame((160, 120, 90)))
        cool = C.analyze_array(frame((90, 120, 160)))
        self.assertGreater(warm.warmth, 1.0)
        self.assertLess(cool.warmth, 1.0)

    def test_crush_and_clip_fractions(self):
        dark = C.analyze_array(np.full((40, 40, 3), 3, np.uint8))
        bright = C.analyze_array(np.full((40, 40, 3), 252, np.uint8))
        self.assertGreater(dark.shadow_crush, 0.9)
        self.assertGreater(bright.highlight_clip, 0.9)

    def test_contrast_is_luma_std(self):
        flat = C.analyze_array(np.full((40, 40, 3), 128, np.uint8))
        self.assertAlmostEqual(flat.contrast, 0.0, delta=0.01)


class ShotMatchTests(unittest.TestCase):
    def test_match_reduces_colour_distance(self):
        ref = frame((130, 130, 130), seed=1)
        tgt = frame((90, 110, 170), seed=2)
        m = C.match_shots(ref, tgt, strength=1.0)
        matched = m.apply_to_array(tgt)
        self.assertLess(C.match_distance(matched, ref), C.match_distance(tgt, ref))

    def test_strength_is_monotonic(self):
        ref = frame((130, 130, 130), seed=1)
        tgt = frame((90, 110, 170), seed=2)
        d_full = C.match_distance(C.match_shots(ref, tgt, strength=1.0).apply_to_array(tgt), ref)
        d_half = C.match_distance(C.match_shots(ref, tgt, strength=0.5).apply_to_array(tgt), ref)
        d_zero = C.match_distance(tgt, ref)
        self.assertLess(d_full, d_half)
        self.assertLess(d_half, d_zero)

    def test_strength_out_of_range_rejected(self):
        with self.assertRaises(C.ColorError):
            C.match_shots(frame((1, 1, 1)), frame((2, 2, 2)), strength=1.5)

    def test_match_filter_is_well_formed(self):
        m = C.match_shots(frame((130, 130, 130)), frame((90, 110, 170)))
        self.assertIn("colorchannelmixer", m.to_filter())


class ColorQATests(unittest.TestCase):
    def test_excessive_saturation_flagged(self):
        oversat = np.zeros((40, 40, 3), np.uint8)
        oversat[..., 0] = 250
        issues = C.color_qa(C.analyze_array(oversat)).issues
        self.assertTrue(any("saturation" in i for i in issues))

    def test_crushed_and_clipped_flagged(self):
        self.assertTrue(any("shadow" in i for i in C.color_qa(C.analyze_array(np.full((30, 30, 3), 2, np.uint8))).issues))
        self.assertTrue(any("highlight" in i for i in C.color_qa(C.analyze_array(np.full((30, 30, 3), 253, np.uint8))).issues))

    def test_balanced_frame_passes(self):
        img = np.full((40, 40, 3), 128, np.uint8)
        img[0, 0] = [200, 150, 120]
        self.assertTrue(C.color_qa(C.analyze_array(img)).ok)


class FilterBuilderTests(unittest.TestCase):
    def test_color_adjust_validation(self):
        with self.assertRaises(C.ColorError):
            C.ColorAdjust(exposure=10).to_filter()
        with self.assertRaises(C.ColorError):
            C.ColorAdjust(temperature=500).to_filter()
        self.assertEqual(C.ColorAdjust().to_filter(), "null")

    def test_curves_requires_valid_points(self):
        with self.assertRaises(C.ColorError):
            C.curves_filter([(0, 0)])
        with self.assertRaises(C.ColorError):
            C.curves_filter([(0, 0), (1.5, 1)])
        self.assertIn("curves=", C.curves_filter([(0, 0), (1, 1)]))

    def test_compositing_builders_validate(self):
        with self.assertRaises(C.ColorError):
            C.gaussian_blur(-1)
        with self.assertRaises(C.ColorError):
            C.glow(amount=2.0)
        self.assertIn("chromakey", C.chroma_key())
        self.assertIn("vignette", C.vignette())
        self.assertIn("noise", C.film_grain())
        self.assertIn("blend", C.glow())


class SpecLooksTests(unittest.TestCase):
    def test_ten_spec_looks_registered(self):
        self.assertEqual(len(C.SPEC_LOOK_NAMES), 10)
        for name in C.SPEC_LOOK_NAMES:
            self.assertIn(name, G.LOOKS)

    def test_high_contrast_look_has_more_contrast_than_soft(self):
        self.assertGreater(G.LOOKS["high_contrast_editorial"].contrast,
                           G.LOOKS["soft_romantic_v2"].contrast)


if __name__ == "__main__":
    unittest.main()
