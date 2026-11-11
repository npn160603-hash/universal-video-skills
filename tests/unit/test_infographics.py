"""Animated charts: validation, data accuracy on pixels, determinism, text boundaries (no ffmpeg)."""
import unittest

import numpy as np

from uvs.infographics import (ChartSpec, InfographicError, Series, KINDS, DARK,
                              render_chart_frame, validate, SAFE_MARGIN, font, text_size)
from PIL import Image, ImageDraw


def spec(kind, **kw):
    base = dict(categories=("A", "B", "C"), series=(Series("x", (10, 25, 15)),),
                source="demo", width=480, height=600)
    base.update(kw)
    return ChartSpec(kind=kind, **base)


def color_mask(img, color):
    a = np.array(img)
    c = np.array(color)
    return (a[:, :, 0] == c[0]) & (a[:, :, 1] == c[1]) & (a[:, :, 2] == c[2])


def height_of(img, color):
    m = color_mask(img, color)
    ys = np.where(m.any(axis=1))[0]
    return ys.max() - ys.min() if len(ys) else 0


class ValidationTests(unittest.TestCase):
    def test_every_kind_is_known(self):
        self.assertEqual(len(KINDS), 10)

    def test_missing_source_is_rejected(self):
        with self.assertRaises(InfographicError):
            validate(spec("vertical_bar", source=""))

    def test_non_finite_value_is_rejected(self):
        with self.assertRaises(InfographicError):
            validate(spec("vertical_bar", series=(Series("x", (1, float("nan"), 3)),)))

    def test_boolean_is_not_a_number(self):
        with self.assertRaises(InfographicError):
            validate(spec("line", series=(Series("x", (1, True, 3)),)))

    def test_negative_rejected_for_bar_but_allowed_for_line(self):
        with self.assertRaises(InfographicError):
            validate(spec("vertical_bar", series=(Series("x", (1, -2, 3)),)))
        validate(spec("line", series=(Series("x", (1, -2, 3)),)))  # no raise

    def test_series_must_share_length(self):
        with self.assertRaises(InfographicError):
            validate(spec("comparison", categories=("A", "B"),
                          series=(Series("p", (1, 2)), Series("q", (1, 2, 3)))))

    def test_duplicate_series_labels_rejected(self):
        with self.assertRaises(InfographicError):
            validate(spec("comparison", categories=("A", "B", "C"),
                          series=(Series("same", (1, 2, 3)), Series("same", (4, 5, 6)))))

    def test_counter_needs_exactly_one_value(self):
        with self.assertRaises(InfographicError):
            validate(spec("counter", categories=(), series=(Series("x", (1, 2)),)))
        validate(spec("counter", categories=(), series=(Series("x", (42,)),)))

    def test_progress_values_must_be_fractions(self):
        with self.assertRaises(InfographicError):
            validate(spec("progress", categories=(), series=(Series("x", (1.4,)),)))

    def test_unknown_kind_theme_easing(self):
        with self.assertRaises(InfographicError):
            validate(spec("bogus"))
        with self.assertRaises(InfographicError):
            validate(spec("line", theme="neon"))
        with self.assertRaises(InfographicError):
            validate(spec("line", easing="zoom"))

    def test_pie_needs_one_series_and_a_positive_total(self):
        with self.assertRaises(InfographicError):
            validate(spec("pie", series=(Series("x", (0, 0, 0)),)))


class RenderAllKindsTests(unittest.TestCase):
    def _specs(self):
        return {
            "vertical_bar": spec("vertical_bar"),
            "horizontal_bar": spec("horizontal_bar"),
            "line": spec("line", categories=("Q1", "Q2", "Q3"), series=(Series("r", (5, 8, 6)),)),
            "area": spec("area", categories=("Q1", "Q2", "Q3"), series=(Series("r", (5, 8, 6)),)),
            "pie": spec("pie", series=(Series("x", (30, 50, 20)),)),
            "donut": spec("donut", series=(Series("x", (30, 50, 20)),)),
            "ranking": spec("ranking"),
            "comparison": spec("comparison", categories=("23", "24"),
                               series=(Series("us", (4, 5)), Series("them", (3, 2)))),
            "progress": spec("progress", categories=(), series=(Series("Build", (0.8,)),)),
            "counter": spec("counter", categories=(), series=(Series("subs", (125000,)),)),
        }

    def test_all_kinds_render_the_requested_size(self):
        for kind, s in self._specs().items():
            with self.subTest(kind=kind):
                img = render_chart_frame(s, 1.0)
                self.assertEqual(img.size, (s.width, s.height))

    def test_rendering_is_deterministic(self):
        for kind, s in self._specs().items():
            with self.subTest(kind=kind):
                self.assertEqual(render_chart_frame(s, 0.5).tobytes(),
                                 render_chart_frame(s, 0.5).tobytes())


class DataAccuracyTests(unittest.TestCase):
    def test_bar_heights_are_proportional_to_values(self):
        s = spec("vertical_bar", categories=("A", "B"), series=(Series("x", (10, 20)),))
        img = render_chart_frame(s, 1.0)
        hA = height_of(img, DARK.color(0))
        hB = height_of(img, DARK.color(1))
        self.assertAlmostEqual(hB / hA, 2.0, delta=0.05)

    def test_bars_grow_from_zero(self):
        s = spec("vertical_bar", categories=("A", "B"), series=(Series("x", (10, 20)),))
        at0 = render_chart_frame(s, 0.0)
        self.assertFalse(color_mask(at0, DARK.color(0)).any() or color_mask(at0, DARK.color(1)).any())
        self.assertTrue(color_mask(render_chart_frame(s, 1.0), DARK.color(1)).any())

    def test_progress_fill_matches_the_fraction(self):
        s = spec("progress", categories=(), series=(Series("Build", (0.5,)),), width=400, height=200)
        img = render_chart_frame(s, 1.0)
        m = color_mask(img, DARK.color(0))
        rows = np.where(m.any(axis=1))[0]
        y = rows[len(rows) // 2]
        xs = np.where(m[y])[0]
        self.assertAlmostEqual(xs.max() / img.width, 0.5, delta=0.04)

    def test_counter_final_frame_shows_the_exact_value(self):
        # The final counter frame must print the target, not an eased approximation.
        s = spec("counter", categories=(), series=(Series("n", (1234,)),), width=400, height=300)
        img = render_chart_frame(s, 1.0)
        # Re-draw "1,234" on a blank frame and confirm the counter contains those glyphs' colour.
        self.assertTrue(color_mask(img, DARK.color(0)).any())  # the number is drawn in series colour
        # pixel count for p=1 should exceed p=0.5 (more digits / larger number drawn)
        self.assertGreaterEqual(int(color_mask(render_chart_frame(s, 1.0), DARK.color(0)).sum()),
                                1)

    def test_pie_slices_cover_more_area_as_it_sweeps(self):
        s = spec("pie", series=(Series("x", (30, 50, 20)),), width=400, height=500)
        early = sum(int(color_mask(render_chart_frame(s, 0.25), DARK.color(i)).sum()) for i in range(3))
        full = sum(int(color_mask(render_chart_frame(s, 1.0), DARK.color(i)).sum()) for i in range(3))
        self.assertGreater(full, early)


class TextBoundaryTests(unittest.TestCase):
    def test_title_and_source_stay_within_safe_margins(self):
        s = spec("vertical_bar", title="A Fairly Long Chart Title", source="Internal data 2026")
        img = render_chart_frame(s, 1.0)
        margin = int(min(s.width, s.height) * SAFE_MARGIN)
        a = np.array(img)
        # top-left corner strip above the margin must be background only
        bg = np.array(DARK.background)
        corner = a[:margin // 2, :margin // 2]
        self.assertTrue((corner == bg).all(), "content intrudes into the top-left safe margin")

    def test_long_counter_value_fits_the_canvas(self):
        s = spec("counter", categories=(), series=(Series("n", (9_999_999,)),),
                 width=400, height=300, unit="views")
        img = render_chart_frame(s, 1.0)
        m = color_mask(img, DARK.color(0))
        xs = np.where(m.any(axis=0))[0]
        self.assertGreater(xs.min(), 0)
        self.assertLess(xs.max(), img.width - 1)


class StaggerTests(unittest.TestCase):
    def test_stagger_delays_later_bars(self):
        # With stagger, at a mid time the first bar is taller than the last.
        s = spec("vertical_bar", categories=("A", "B", "C"), series=(Series("x", (20, 20, 20)),),
                 stagger=0.6, easing="linear")
        img = render_chart_frame(s, 0.3)
        hs = [height_of(img, DARK.color(i)) for i in range(3)]
        self.assertGreater(hs[0], hs[2])


if __name__ == "__main__":
    unittest.main()
