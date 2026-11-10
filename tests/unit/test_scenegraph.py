import math
import unittest

from uvs import scenegraph as S


def _close(a, b, tol=1e-9):
    return all(abs(x - y) < tol for x, y in zip(a, b))


class TransformTests(unittest.TestCase):
    def test_translation_composes_through_parents(self):
        root = S.Node("root", "group")
        parent = S.Node("p", "group", S.Transform(x=100, y=50))
        child = S.Node("c", "shape", S.Transform(x=10, y=5), width=20, height=20)
        root.children.append(parent)
        parent.children.append(child)
        g = S.SceneGraph(root)
        self.assertTrue(_close(S.to_world(g, "c", 0, 0), (110, 55)))

    def test_rotation_is_clockwise_on_screen_for_y_down(self):
        # A point 1 unit to the right of a 90-degree clockwise rotation moves down the screen.
        root = S.Node("root", "group", S.Transform(rotation=90))
        g = S.SceneGraph(root)
        self.assertTrue(_close(S.to_world(g, "root", 1, 0), (0, 1)))

    def test_scale_and_anchor(self):
        # The anchor point (10, 10) of the node is placed at the transform position (100, 100).
        # Scaling by 2 about the anchor moves the origin to (100 - 20, 100 - 20) = (80, 80).
        n = S.Node("n", "image", S.Transform(x=100, y=100, scale_x=2, scale_y=2,
                                             anchor_x=10, anchor_y=10), width=20, height=20)
        g = S.SceneGraph(S.Node("root", "group", children=[n]))
        self.assertTrue(_close(S.to_world(g, "n", 10, 10), (100, 100)))
        self.assertTrue(_close(S.to_world(g, "n", 0, 0), (80, 80)))

    def test_local_and_global_conversion_round_trips(self):
        n = S.Node("n", "shape", S.Transform(x=30, y=-7, rotation=33.5, scale_x=1.7, scale_y=0.6,
                                             anchor_x=4, anchor_y=2))
        mid = S.Node("m", "group", S.Transform(x=-12, y=8, rotation=-20, scale_x=0.9, scale_y=1.2),
                     children=[n])
        g = S.SceneGraph(S.Node("root", "group", children=[mid]))
        for px, py in [(0, 0), (13.2, -4.5), (-100, 250)]:
            wx, wy = S.to_world(g, "n", px, py)
            lx, ly = S.to_local(g, "n", wx, wy)
            self.assertTrue(_close((lx, ly), (px, py), tol=1e-6))

    def test_opacity_multiplies_down_the_hierarchy(self):
        child = S.Node("c", "shape", S.Transform(opacity=0.5))
        parent = S.Node("p", "group", S.Transform(opacity=0.5), children=[child])
        g = S.SceneGraph(S.Node("root", "group", children=[parent]))
        self.assertAlmostEqual(S.world_opacity(g, "c"), 0.25)

    def test_zero_scale_is_refused_when_inverting(self):
        g = S.SceneGraph(S.Node("root", "group", S.Transform(scale_x=0)))
        with self.assertRaises(S.SceneGraphError):
            S.to_local(g, "root", 1, 1)

    def test_world_rect_respects_crop(self):
        n = S.Node("n", "image", S.Transform(x=10, y=10), width=100, height=50,
                   crop=S.Crop(left=10, top=5, right=10, bottom=5))
        g = S.SceneGraph(S.Node("root", "group", children=[n]))
        rect = S.world_rect(g, "n")
        self.assertEqual(rect, [(20, 15), (100, 15), (100, 55), (20, 55)])


class LayerOrderTests(unittest.TestCase):
    def test_draw_order_is_depth_first_and_later_children_are_on_top(self):
        g = S.SceneGraph(S.Node("root", "group", children=[
            S.Node("bg", "image"),
            S.Node("group", "group", children=[S.Node("a", "text"), S.Node("b", "text")]),
            S.Node("fg", "overlay"),
        ]))
        self.assertEqual(S.draw_order(g), ["root", "bg", "group", "a", "b", "fg"])

    def test_reorder_child_moves_layer_without_touching_original(self):
        g = S.SceneGraph(S.Node("root", "group", children=[
            S.Node("a", "shape"), S.Node("b", "shape"), S.Node("c", "shape")]))
        moved = S.reorder_child(g, "root", "a", 2)
        self.assertEqual([c.id for c in moved.root.children], ["b", "c", "a"])
        self.assertEqual([c.id for c in g.root.children], ["a", "b", "c"])

    def test_reorder_rejects_bad_index_and_unknown_child(self):
        g = S.SceneGraph(S.Node("root", "group", children=[S.Node("a", "shape")]))
        with self.assertRaises(S.SceneGraphError):
            S.reorder_child(g, "root", "a", 5)
        with self.assertRaises(S.SceneGraphError):
            S.reorder_child(g, "root", "zzz", 0)


class ValidationTests(unittest.TestCase):
    def test_valid_graph_has_no_problems(self):
        g = S.SceneGraph(S.Node("root", "group", children=[S.Node("a", "text", width=10, height=10)]))
        self.assertEqual(S.validate(g), [])

    def test_duplicate_ids_are_reported(self):
        g = S.SceneGraph(S.Node("root", "group", children=[S.Node("a", "text"), S.Node("a", "text")]))
        self.assertEqual(len(S.validate(g)), 1)
        self.assertIn("duplicate node id", S.validate(g)[0])

    def test_shared_child_is_a_cycle_or_sharing_error(self):
        shared = S.Node("s", "text")
        g = S.SceneGraph(S.Node("root", "group", children=[shared, shared]))
        self.assertIn("more than once", S.validate(g)[0])

    def test_cycle_terminates_and_is_reported(self):
        a = S.Node("a", "group")
        b = S.Node("b", "group", children=[a])
        a.children.append(b)
        g = S.SceneGraph(a)
        problems = S.validate(g)
        self.assertTrue(problems)
        with self.assertRaises(S.SceneGraphError):
            S.draw_order(g)

    def test_unknown_kind_opacity_and_crop_are_reported(self):
        bad = S.Node("x", "hologram", S.Transform(opacity=1.5), width=10, height=10,
                     crop=S.Crop(left=6, right=6))
        problems = S.validate(S.SceneGraph(S.Node("root", "group", children=[bad])))
        text = " | ".join(problems)
        self.assertIn("unknown kind", text)
        self.assertIn("opacity", text)
        self.assertIn("crop removes the whole node", text)

    def test_serialization_round_trip_is_exact(self):
        g = S.SceneGraph(S.Node("root", "group", children=[
            S.Node("t", "text", S.Transform(x=1.5, rotation=10), width=100, height=40,
                   crop=S.Crop(left=1), payload={"text": "Hanoi"})]))
        data = S.to_dict(g)
        again = S.to_dict(S.from_dict(data))
        self.assertEqual(data, again)
        self.assertEqual(S.draw_order(S.from_dict(data)), ["root", "t"])

    def test_from_dict_rejects_other_formats(self):
        with self.assertRaises(S.SceneGraphError):
            S.from_dict({"format": "something-else"})


if __name__ == "__main__":
    unittest.main()
