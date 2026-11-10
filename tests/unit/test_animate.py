"""Motion engine: poses from keyframes, validation, and rendered pixels (no ffmpeg needed)."""
import tempfile
import unittest
from pathlib import Path

from PIL import Image

from uvs import animate as A
from uvs import scenegraph as G
from uvs.assets import ProjectRoot

RED = (255, 0, 0)
BLACK = (0, 0, 0)


def _shape(node_id, *, x=0.0, y=0.0, w=40, h=40, fill="#ff0000", rotation=0.0, anchor=(0.0, 0.0),
           opacity=1.0, crop=None, shape="rect"):
    return G.Node(id=node_id, kind="shape",
                  transform=G.Transform(x=x, y=y, rotation=rotation, anchor_x=anchor[0],
                                        anchor_y=anchor[1], opacity=opacity),
                  width=w, height=h, crop=crop,
                  payload={"fill": fill, "shape": shape})


def _graph(*children):
    return G.SceneGraph(root=G.Node(id="root", kind="group", children=list(children)))


def _linear(prop, start, end, seconds=1.0):
    return [{"time": 0, "value": start, "easing": "linear"}, {"time": seconds, "value": end}]


def _close(actual, expected, tol=6):
    return all(abs(a - e) <= tol for a, e in zip(actual, expected))


class PoseTests(unittest.TestCase):
    def test_pose_sets_transform_from_track_and_holds_after_the_end(self):
        g = _graph(_shape("sq"))
        anim = A.Animation.from_spec({"sq": {"x": _linear("x", 0, 100)}})
        self.assertEqual(G.find(A.pose(g, anim, 0.5), "sq").transform.x, 50.0)
        self.assertEqual(G.find(A.pose(g, anim, 0.0), "sq").transform.x, 0.0)
        self.assertEqual(G.find(A.pose(g, anim, 9.0), "sq").transform.x, 100.0)

    def test_pose_does_not_change_the_original_graph(self):
        g = _graph(_shape("sq"))
        anim = A.Animation.from_spec({"sq": {"x": _linear("x", 0, 100)}})
        A.pose(g, anim, 1.0)
        self.assertEqual(G.find(g, "sq").transform.x, 0.0)

    def test_tuple_keyframes_are_rejected_for_scalar_props(self):
        g = _graph(_shape("sq"))
        anim = A.Animation.from_spec({"sq": {"x": [{"time": 0, "value": [0, 0]}, {"time": 1, "value": [1, 1]}]}})
        self.assertTrue(any("takes a single number" in p for p in A.check(g, anim)))

    def test_unknown_node_and_property_are_reported(self):
        g = _graph(_shape("sq"))
        self.assertTrue(any("unknown node 'ghost'" in p
                            for p in A.check(g, A.Animation.from_spec({"ghost": {"x": _linear("x", 0, 1)}}))))
        self.assertTrue(any("cannot be animated" in p
                            for p in A.check(g, A.Animation.from_spec({"sq": {"kind": _linear("kind", 0, 1)}}))))

    def test_opacity_out_of_range_fails_at_pose_time(self):
        g = _graph(_shape("sq"))
        anim = A.Animation.from_spec({"sq": {"opacity": _linear("opacity", 1.0, 1.5)}})
        with self.assertRaises(A.AnimationError):
            A.pose(g, anim, 1.0)

    def test_malformed_specs_raise(self):
        bad = [
            "not a dict",
            {"sq": "x"},
            {"sq": {"x": []}},
            {"sq": {"x": [{"time": 0}]}},
            {"sq": {"x": [{"time": 0, "value": True}]}},
            {"sq": {"x": [{"time": 0, "value": 1, "easing": "wobble"}]}},
        ]
        for spec in bad:
            with self.subTest(spec=spec), self.assertRaises(A.AnimationError):
                A.Animation.from_spec(spec)

    def test_frame_times_match_track_sampling(self):
        times = A.frame_times(10, 1.0)
        self.assertEqual(len(times), 10)
        self.assertAlmostEqual(times[-1], 0.9)
        track = A.Animation.from_spec({"sq": {"x": _linear("x", 0, 100)}}).tracks["sq"]["x"]
        self.assertEqual(len(track.sample(10, 1.0)), len(times))


class RenderedPixelTests(unittest.TestCase):
    W, H = 200, 120

    def _frame(self, g, anim, t):
        return A.render_frame(g, anim, t, width=self.W, height=self.H)

    def test_square_is_at_its_start_position_at_t0_and_moves_linearly(self):
        g = _graph(_shape("sq", y=40))
        anim = A.Animation.from_spec({"sq": {"x": _linear("x", 0, 100)}})
        f0 = self._frame(g, anim, 0.0)
        self.assertEqual(f0.getpixel((20, 60)), RED)
        self.assertEqual(f0.getpixel((120, 60)), BLACK)
        f_half = self._frame(g, anim, 0.5)
        self.assertEqual(f_half.getpixel((70, 60)), RED)
        self.assertEqual(f_half.getpixel((30, 60)), BLACK)
        self.assertEqual(f_half.getpixel((95, 60)), BLACK)

    def test_held_position_after_the_last_keyframe(self):
        g = _graph(_shape("sq", y=40))
        anim = A.Animation.from_spec({"sq": {"x": _linear("x", 0, 100)}})
        f_end = self._frame(g, anim, 3.0)
        self.assertEqual(f_end.getpixel((120, 60)), RED)
        self.assertEqual(f_end.getpixel((20, 60)), BLACK)

    def test_opacity_halves_the_colour(self):
        g = _graph(_shape("sq", x=60, y=40))
        anim = A.Animation.from_spec({"sq": {"opacity": _linear("opacity", 1.0, 0.0)}})
        r, g_, b = self._frame(g, anim, 0.5).getpixel((80, 60))
        self.assertAlmostEqual(r, 127.5, delta=4)
        self.assertEqual((g_, b), (0, 0))

    def test_parent_opacity_multiplies_child_opacity(self):
        child = _shape("sq", x=60, y=40)
        parent = G.Node(id="p", kind="group", transform=G.Transform(opacity=0.5), children=[child])
        anim = A.Animation.from_spec({})
        r, _, _ = A.render_frame(_graph(parent), anim, 0.0, width=self.W, height=self.H).getpixel((80, 60))
        self.assertAlmostEqual(r, 127.5, delta=4)

    def test_rotation_turns_a_wide_rectangle_into_a_tall_one(self):
        # 80 x 20 rectangle, pivot at its centre, centre placed at (160, 120 -> 60). Rotate 90 deg.
        node = _shape("bar", x=160, y=60, w=80, h=20, rotation=90, anchor=(40, 10))
        g = G.SceneGraph(root=G.Node(id="root", kind="group", children=[node]))
        f = A.render_frame(g, A.Animation.from_spec({}), 0.0, width=200, height=120)
        self.assertEqual(f.getpixel((160, 30)), RED)   # upper arm of the rotated bar
        self.assertEqual(f.getpixel((160, 90)), RED)   # lower arm
        self.assertEqual(f.getpixel((190, 60)), BLACK)  # would be red if not rotated
        self.assertEqual(f.getpixel((130, 60)), BLACK)

    def test_crop_hides_the_cropped_part(self):
        node = _shape("sq", x=0, y=40, w=40, h=40, crop=G.Crop(right=20))
        g = _graph(node)
        f = self._frame(g, A.Animation.from_spec({}), 0.0)
        self.assertEqual(f.getpixel((10, 60)), RED)
        self.assertEqual(f.getpixel((30, 60)), BLACK)

    def test_ellipse_is_round(self):
        g = _graph(_shape("e", x=40, y=20, w=80, h=80, shape="ellipse"))
        f = self._frame(g, A.Animation.from_spec({}), 0.0)
        self.assertEqual(f.getpixel((80, 60)), RED)
        self.assertEqual(f.getpixel((42, 22)), BLACK)  # corner of the box is outside the circle

    def test_later_nodes_draw_on_top(self):
        g = _graph(_shape("under", x=40, y=40, fill="#0000ff"), _shape("over", x=50, y=50, fill="#ff0000"))
        f = self._frame(g, A.Animation.from_spec({}), 0.0)
        self.assertEqual(f.getpixel((60, 60)), RED)
        self.assertEqual(f.getpixel((45, 45)), (0, 0, 255))

    def test_rendering_is_deterministic(self):
        g = _graph(_shape("sq", y=40))
        anim = A.Animation.from_spec({"sq": {"x": _linear("x", 0, 100), "rotation": _linear("rotation", 0, 45)}})
        self.assertEqual(self._frame(g, anim, 0.37).tobytes(), self._frame(g, anim, 0.37).tobytes())

    def test_background_colour_is_used(self):
        f = A.render_frame(_graph(), A.Animation.from_spec({}), 0.0, width=self.W, height=self.H,
                           background=(10, 20, 30))
        self.assertEqual(f.getpixel((5, 5)), (10, 20, 30))


class ImageNodeTests(unittest.TestCase):
    def test_image_node_reads_through_the_project_root(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = ProjectRoot(tmp)
            Image.new("RGB", (16, 16), (0, 255, 0)).save(Path(tmp) / "g.png")
            node = G.Node(id="img", kind="image", transform=G.Transform(x=50, y=50), width=40, height=40,
                          payload={"src": "g.png"})
            f = A.render_frame(_graph(node), A.Animation.from_spec({}), 0.0, width=160, height=120, root=root)
            self.assertTrue(_close(f.getpixel((70, 70)), (0, 255, 0)))
            self.assertEqual(f.getpixel((20, 20)), BLACK)

    def test_image_node_without_root_is_refused(self):
        node = G.Node(id="img", kind="image", width=40, height=40, payload={"src": "g.png"})
        with self.assertRaises(A.AnimationError):
            A.FrameRenderer(_graph(node), A.Animation.from_spec({}), width=50, height=50)

    def test_image_path_escape_is_refused(self):
        with tempfile.TemporaryDirectory() as tmp:
            node = G.Node(id="img", kind="image", width=40, height=40, payload={"src": "../secret.png"})
            with self.assertRaises(Exception):
                A.FrameRenderer(_graph(node), A.Animation.from_spec({}), width=50, height=50,
                                root=ProjectRoot(tmp))


class UnsupportedKindTests(unittest.TestCase):
    def test_text_node_is_refused_rather_than_skipped(self):
        node = G.Node(id="t", kind="text", width=40, height=40, payload={"text": "hi"})
        with self.assertRaises(A.AnimationError) as ctx:
            A.FrameRenderer(_graph(node), A.Animation.from_spec({}), width=50, height=50)
        self.assertIn("does not render yet", str(ctx.exception))


if __name__ == "__main__":
    unittest.main()
