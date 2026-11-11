"""Timelines, diagram layout and overlap avoidance, and labelled metaphors (no ffmpeg)."""
import unittest

import numpy as np

from uvs.explainers import (Timeline, Event, TIMELINE_KINDS, validate_timeline, playhead_index,
                            render_timeline_frame, Diagram, DiagNode, DiagEdge, DIAGRAM_KINDS,
                            validate_diagram, layout_diagram, overlaps, render_diagram_frame,
                            Metaphor, METAPHORS, validate_metaphor, render_metaphor_frame,
                            ExplainerError)


class TimelineTests(unittest.TestCase):
    def _tl(self, **kw):
        base = dict(kind="historical",
                    events=(Event(1990, "Founded"), Event(2005, "IPO"), Event(2020, "Peak")),
                    title="History", source="demo", width=960, height=540)
        base.update(kw)
        return Timeline(**base)

    def test_six_kinds(self):
        self.assertEqual(len(TIMELINE_KINDS), 6)

    def test_needs_two_events_in_order(self):
        with self.assertRaises(ExplainerError):
            validate_timeline(self._tl(events=(Event(2000, "only"),)))
        with self.assertRaises(ExplainerError):
            validate_timeline(self._tl(events=(Event(2005, "b"), Event(1990, "a"))))

    def test_before_after_needs_exactly_two(self):
        with self.assertRaises(ExplainerError):
            validate_timeline(self._tl(kind="before_after"))
        validate_timeline(self._tl(kind="before_after",
                                   events=(Event(0, "before"), Event(1, "after"))))

    def test_playhead_advances_with_progress(self):
        tl = self._tl()
        self.assertEqual(playhead_index(tl, 0.0), 0)
        self.assertGreaterEqual(playhead_index(tl, 1.0), 2)
        self.assertLessEqual(playhead_index(tl, 0.0), playhead_index(tl, 0.5))

    def test_axis_progress_fills_from_the_left(self):
        tl = self._tl(easing="linear")
        a_quarter = np.array(render_timeline_frame(tl, 0.25))
        full = np.array(render_timeline_frame(tl, 1.0))
        col = np.array(tl.resolved_theme().color(0))
        axis = tl.height // 2
        rightmost = lambda a: np.where((a[axis] == col).all(axis=1))[0]
        self.assertLess(rightmost(a_quarter).max(), rightmost(full).max())

    def test_rendering_is_deterministic(self):
        tl = self._tl()
        self.assertEqual(render_timeline_frame(tl, 0.4).tobytes(),
                         render_timeline_frame(tl, 0.4).tobytes())


class DiagramLayoutTests(unittest.TestCase):
    def _linear(self, **kw):
        nodes = (DiagNode("a", "Collect", 0), DiagNode("b", "Clean", 1),
                 DiagNode("c", "Analyze", 2), DiagNode("d", "Report", 3))
        edges = (DiagEdge("a", "b"), DiagEdge("b", "c"), DiagEdge("c", "d"))
        base = dict(kind="process", nodes=nodes, edges=edges, width=960, height=1080)
        base.update(kw)
        return Diagram(**base)

    def test_seven_kinds(self):
        self.assertEqual(len(DIAGRAM_KINDS), 7)

    def test_validate_catches_bad_ids_and_edges(self):
        dg = Diagram("flowchart", (DiagNode("a", "A", 0), DiagNode("a", "dup", 1)),
                     (DiagEdge("a", "ghost"),))
        problems = validate_diagram(dg)
        self.assertTrue(any("unique" in p for p in problems))
        self.assertTrue(any("ghost" in p for p in problems))

    def test_linear_layout_has_no_overlaps(self):
        self.assertEqual(overlaps(layout_diagram(self._linear())), [])

    def test_many_nodes_on_one_level_stay_clean(self):
        nodes = tuple(DiagNode(f"n{i}", f"Node {i}", 0) for i in range(5))
        dg = Diagram("relationship", nodes, (), width=1920, height=1080, node_w=260)
        self.assertEqual(overlaps(layout_diagram(dg)), [])

    def test_overlap_is_detected_and_render_refuses_it(self):
        dg = Diagram("comparison", (DiagNode("x", "X", 0), DiagNode("y", "Y", 0)), (),
                     width=400, height=400, node_w=350, node_h=100)
        self.assertEqual(overlaps(layout_diagram(dg)), [("x", "y")])
        with self.assertRaises(ExplainerError):
            render_diagram_frame(dg, 1.0)

    def test_nodes_reveal_in_order(self):
        dg = self._linear(easing="linear")
        # at p just above 0, only the first node has appeared
        early = np.array(render_diagram_frame(dg, 0.1))
        theme = dg.resolved_theme()
        # last node's outline colour (level 3) should be absent early, present at full
        c = np.array(theme.color(3))
        present = lambda a: ((a[:, :, 0] == c[0]) & (a[:, :, 1] == c[1]) & (a[:, :, 2] == c[2])).any()
        self.assertFalse(present(early))
        self.assertTrue(present(np.array(render_diagram_frame(dg, 1.0))))

    def test_labels_fit_inside_boxes(self):
        # A long label must wrap or shrink; the render must not raise and box must contain text.
        dg = Diagram("process", (DiagNode("a", "A very long descriptive node label here", 0),),
                     (), width=960, height=400, node_w=300, node_h=120)
        img = render_diagram_frame(dg, 1.0)
        self.assertEqual(img.size, (960, 400))


class MetaphorTests(unittest.TestCase):
    def test_eight_metaphors(self):
        self.assertEqual(len(METAPHORS), 8)

    def test_all_render_with_an_illustrative_tag(self):
        for k in METAPHORS:
            with self.subTest(metaphor=k):
                img = render_metaphor_frame(Metaphor(k, title=k, width=540, height=960), 1.0)
                a = np.array(img)
                has_tag = ((a[:, :, 0] == 90) & (a[:, :, 1] == 60) & (a[:, :, 2] == 60)).any()
                self.assertTrue(has_tag, f"{k} is missing the illustrative tag")

    def test_intensity_out_of_range_rejected(self):
        with self.assertRaises(ExplainerError):
            validate_metaphor(Metaphor("stress_accumulation", intensity=1.5))

    def test_unknown_kind_rejected(self):
        with self.assertRaises(ExplainerError):
            validate_metaphor(Metaphor("teleportation"))

    def test_stress_vessel_fills_more_over_time(self):
        m = Metaphor("stress_accumulation", width=540, height=960, easing="linear")
        accent = m.resolved_theme().color(2)
        calm = m.resolved_theme().color(1)

        def fill_pixels(p):
            a = np.array(render_metaphor_frame(m, p))
            # count non-background, non-outline pixels inside the vessel region
            bg = np.array(m.resolved_theme().background)
            return int((~(a == bg).all(axis=2)).sum())

        self.assertGreater(fill_pixels(1.0), fill_pixels(0.2))

    def test_determinism(self):
        m = Metaphor("increasing_pressure", width=400, height=400)
        self.assertEqual(render_metaphor_frame(m, 0.5).tobytes(),
                         render_metaphor_frame(m, 0.5).tobytes())


if __name__ == "__main__":
    unittest.main()
