import math
import unittest

from uvs import motion as M


class EasingTests(unittest.TestCase):
    def test_all_easings_hit_endpoints_exactly(self):
        for name, f in M.EASINGS.items():
            with self.subTest(easing=name):
                self.assertAlmostEqual(f(0.0), 0.0, places=9)
                self.assertAlmostEqual(f(1.0), 1.0, places=9)

    def test_clamps_outside_unit_interval(self):
        for name, f in M.EASINGS.items():
            with self.subTest(easing=name):
                self.assertAlmostEqual(f(-0.5), 0.0, places=9)
                self.assertAlmostEqual(f(1.5), 1.0, places=9)

    def test_bezier_linear_matches_linear(self):
        f = M.cubic_bezier(0.0, 0.0, 1.0, 1.0)
        for i in range(0, 101):
            t = i / 100
            self.assertAlmostEqual(f(t), t, places=6)

    def test_ease_in_out_is_symmetric_around_half(self):
        f = M.ease_in_out
        self.assertAlmostEqual(f(0.5), 0.5, places=6)
        for t in (0.1, 0.25, 0.4):
            self.assertAlmostEqual(f(t) + f(1 - t), 1.0, places=5)

    def test_ease_in_is_slower_at_start_than_linear(self):
        self.assertLess(M.ease_in(0.25), 0.25)
        self.assertGreater(M.ease_out(0.25), 0.25)

    def test_bezier_rejects_out_of_range_x(self):
        with self.assertRaises(ValueError):
            M.cubic_bezier(1.5, 0, 0.5, 1)

    def test_overshoot_exceeds_one_before_settling(self):
        values = [M.overshoot(i / 200) for i in range(201)]
        self.assertGreater(max(values), 1.0)
        self.assertAlmostEqual(values[-1], 1.0)

    def test_spring_overshoots_and_settles(self):
        f = M.spring(zeta=0.4, omega=14)
        values = [f(i / 300) for i in range(301)]
        self.assertGreater(max(values), 1.0)
        self.assertLess(abs(values[-2] - 1.0), 0.02)

    def test_spring_rejects_critically_or_over_damped(self):
        with self.assertRaises(ValueError):
            M.spring(zeta=1.0)

    def test_bounce_stays_within_unit_range(self):
        values = [M.bounce_out(i / 500) for i in range(501)]
        self.assertGreaterEqual(min(values), -1e-9)
        self.assertLessEqual(max(values), 1.0 + 1e-9)

    def test_elastic_overshoots(self):
        values = [M.elastic_out(i / 500) for i in range(501)]
        self.assertGreater(max(values), 1.0)

    def test_unknown_easing_name_is_rejected(self):
        with self.assertRaises(KeyError):
            M.get_easing("wobble")


class TrackTests(unittest.TestCase):
    def test_scalar_track_interpolates_linearly_and_holds_ends(self):
        track = M.Track([M.Keyframe(0.0, 0.0), M.Keyframe(2.0, 10.0)])
        self.assertEqual(track.value_at(-1), 0.0)
        self.assertEqual(track.value_at(1.0), 5.0)
        self.assertEqual(track.value_at(9), 10.0)

    def test_tuple_track_interpolates_each_component(self):
        track = M.Track([M.Keyframe(0.0, (0.0, 100.0)), M.Keyframe(1.0, (50.0, 0.0))])
        x, y = track.value_at(0.5)
        self.assertAlmostEqual(x, 25.0)
        self.assertAlmostEqual(y, 50.0)

    def test_easing_applies_from_the_leading_keyframe(self):
        track = M.Track([M.Keyframe(0.0, 0.0, easing="ease_in"), M.Keyframe(1.0, 1.0)])
        self.assertLess(track.value_at(0.25), 0.25)

    def test_frame_sampling_is_frame_accurate(self):
        track = M.Track([M.Keyframe(0.0, 0.0), M.Keyframe(1.0, 1.0)])
        samples = track.sample(fps=30, duration=1.0)
        self.assertEqual(len(samples), 30)
        self.assertAlmostEqual(samples[0], 0.0)
        self.assertAlmostEqual(samples[15], 0.5)

    def test_rejects_duplicate_times_and_mixed_dimensions(self):
        with self.assertRaises(ValueError):
            M.Track([M.Keyframe(0.0, 0.0), M.Keyframe(0.0, 1.0)])
        with self.assertRaises(ValueError):
            M.Track([M.Keyframe(0.0, (0.0, 0.0)), M.Keyframe(1.0, 1.0)])

    def test_rejects_empty_track(self):
        with self.assertRaises(ValueError):
            M.Track([])


if __name__ == "__main__":
    unittest.main()
