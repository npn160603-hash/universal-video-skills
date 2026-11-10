"""Map engine: projection, great circles, routes, camera, and pixels on synthetic countries (no data file)."""
import math
import os
import unittest
from pathlib import Path

from uvs import maps as M

RED = (255, 0, 0)
SEA = (11, 22, 32)
BASE = (34, 54, 74)
ROUTE = (244, 211, 94)


def _square(name, iso, lon0, lat0, lon1, lat1):
    """Clockwise outer ring (ESRI convention), so it is not treated as a hole."""
    ring = [(lon0, lat0), (lon0, lat1), (lon1, lat1), (lon1, lat0)]
    return M._make_country(name, iso, "test", [ring])


def _scene(countries=(), *, view=(-5, -5, 15, 15), size=200, **kw):
    cam = M.Camera.still(M.View(*view))
    return M.MapScene(countries=list(countries), camera=cam, width=size, height=size, **kw)


class ProjectionTests(unittest.TestCase):
    def test_contain_fit_centres_the_view_and_keeps_aspect(self):
        proj = M.Projector(M.View(0, 0, 10, 10), 200, 100)
        self.assertEqual(proj.scale, 10.0)              # limited by height: 100 px / 10 deg
        self.assertEqual(proj.project(0, 0), (50.0, 100.0))   # bottom-left of the fitted square
        self.assertEqual(proj.project(10, 10), (150.0, 0.0))  # top-right
        self.assertEqual(proj.project(5, 5), (100.0, 50.0))

    def test_northern_latitudes_are_higher_on_screen(self):
        proj = M.Projector(M.View(0, -60, 10, 60), 300, 300)
        self.assertLess(proj.project(5, 50)[1], proj.project(5, 0)[1])

    def test_mercator_places_mid_latitudes_lower_than_equirectangular(self):
        view = M.View(0, 0, 10, 80)
        eq = M.Projector(view, 300, 600, "equirectangular")
        mc = M.Projector(view, 300, 600, "mercator")
        self.assertAlmostEqual(eq.project(5, 40)[1], 300.0, delta=1.0)  # halfway up the fitted view
        self.assertGreater(mc.project(5, 40)[1], eq.project(5, 40)[1])  # Mercator: 40 deg sits lower
        self.assertTrue(all(math.isfinite(v) for v in mc.project(5, 80)))

    def test_bad_view_and_projection_are_refused(self):
        with self.assertRaises(M.MapError):
            M.View(10, 0, 5, 10)
        with self.assertRaises(M.MapError):
            M.Projector(M.WORLD, 100, 100, "orthographic")


class GeometryTests(unittest.TestCase):
    def test_great_circle_follows_the_equator_and_hits_its_midpoint(self):
        pts = M.great_circle((0, 0), (90, 0), n=3)
        self.assertEqual(pts[0], (0, 0))
        self.assertEqual(pts[-1], (90, 0))
        self.assertAlmostEqual(pts[1][0], 45.0, places=9)
        self.assertAlmostEqual(pts[1][1], 0.0, places=9)

    def test_great_circle_points_lie_on_the_sphere(self):
        for lon, lat in M.great_circle((105.8, 21.0), (-0.1, 51.5), n=20):
            la, lo = math.radians(lat), math.radians(lon)
            v = (math.cos(la) * math.cos(lo), math.cos(la) * math.sin(lo), math.sin(la))
            self.assertAlmostEqual(sum(c * c for c in v), 1.0, places=9)

    def test_great_circle_bulges_poleward_between_distant_points(self):
        # Hanoi to London: the arc passes well north of the straight latitude line.
        pts = M.great_circle((105.8, 21.0), (-0.1, 51.5), n=101)
        self.assertGreater(max(lat for _, lat in pts), 51.5)

    def test_antipodal_and_degenerate_inputs(self):
        with self.assertRaises(M.MapError):
            M.great_circle((0, 0), (180, 0))
        with self.assertRaises(M.MapError):
            M.great_circle((0, 0), (1, 1), n=1)

    def test_route_through_joins_legs_without_duplicate_points(self):
        pts = M.route_through([(0, 0), (10, 0), (20, 0)], n_per_leg=5)
        self.assertEqual(len(pts), 9)  # 5 + 5 - 1 shared joint
        self.assertEqual(pts[4], (10, 0))

    def test_unwrap_ring_removes_the_antimeridian_jump(self):
        self.assertEqual(M.unwrap_ring([(170, 0), (-170, 0), (-175, 5)]),
                         [(170, 0), (190, 0), (185, 5)])

    def test_signed_area_identifies_outer_and_hole_rings(self):
        outer = M._make_country("o", "O", "t", [[(0, 0), (0, 10), (10, 10), (10, 0)]])
        self.assertEqual([h for _, h in outer.rings], [False])
        with_hole = M._make_country("h", "H", "t", [[(0, 0), (0, 10), (10, 10), (10, 0)],
                                                    [(4, 4), (6, 4), (6, 6), (4, 6)]])
        self.assertEqual([h for _, h in with_hole.rings], [False, True])


class RoutesAndMarkersTests(unittest.TestCase):
    def _route_scene(self, start=1.0, duration=2.0):
        route = M.Route(points=[(0, 0), (10, 0)], start=start, duration=duration,
                        color="#f4d35e", width=4, easing="linear")
        return _scene(routes=[route])

    def test_route_is_absent_before_its_start(self):
        f = self._route_scene().frame(0.5)
        self.assertNotEqual(f.getpixel((75, 150)), ROUTE)

    def test_route_reveals_half_its_length_at_half_time(self):
        f = self._route_scene().frame(2.0)   # p = 0.5 with linear easing; equator is at y = 150
        self.assertEqual(f.getpixel((75, 150)), ROUTE)
        self.assertNotEqual(f.getpixel((125, 150)), ROUTE)

    def test_route_is_complete_after_its_duration(self):
        f = self._route_scene().frame(4.0)
        self.assertEqual(f.getpixel((145, 150)), ROUTE)

    def test_marker_appears_at_its_start(self):
        marker = M.Marker(lon=5, lat=5, start=1.0, color="#ff0000", radius=6)
        s = _scene(markers=[marker])
        self.assertEqual(s.frame(0.5).getpixel((100, 100)), SEA)
        self.assertEqual(s.frame(1.0).getpixel((100, 100)), RED)

    def test_route_needs_two_points_and_a_known_easing(self):
        with self.assertRaises(M.MapError):
            M.Route(points=[(0, 0)], start=0, duration=1)
        with self.assertRaises(KeyError):
            M.Route(points=[(0, 0), (1, 0)], start=0, duration=1, easing="wobble")

    def test_route_crossing_the_antimeridian_is_split(self):
        proj = M.Projector(M.WORLD, 360, 180)
        segs = M._segments([(179, 0), (-179, 0)], proj)
        self.assertEqual(len(segs), 2)


class CountryPixelTests(unittest.TestCase):
    def test_highlighted_country_fills_its_area_and_others_use_base(self):
        sq = _square("Square", "SQR", 0, 0, 10, 10)
        other = _square("Other", "OTH", 0, 12, 4, 14)
        s = _scene([sq, other], highlights={"SQR": "#ff0000"})
        f = s.frame(0.0)
        self.assertEqual(f.getpixel((100, 100)), RED)
        self.assertEqual(f.getpixel((10, 10)), SEA)
        self.assertEqual(f.getpixel((70, 20)), BASE)   # lon 2, lat 13: inside the unhighlighted country

    def test_hole_is_drawn_as_sea(self):
        ring = [(0, 0), (0, 10), (10, 10), (10, 0)]
        hole = [(4, 4), (6, 4), (6, 6), (4, 6)]
        c = M._make_country("Donut", "DNT", "t", [ring, hole])
        f = _scene([c], highlights={"DNT": "#ff0000"}).frame(0.0)
        self.assertEqual(f.getpixel((100, 100)), SEA)      # centre (5, 5) is in the hole
        self.assertEqual(f.getpixel((70, 100)), RED)       # lon 2.5 is solid

    def test_countries_outside_the_view_are_skipped(self):
        far = _square("Far", "FAR", 100, 60, 110, 70)
        f = _scene([far], view=(-5, -5, 15, 15), highlights={"FAR": "#ff0000"}).frame(0.0)
        self.assertEqual(f.getpixel((100, 100)), SEA)

    def test_frame_size_matches_the_scene(self):
        self.assertEqual(_scene(size=120).frame(0.0).size, (120, 120))


class CameraTests(unittest.TestCase):
    def test_move_starts_and_ends_on_the_given_views(self):
        start, end = M.WORLD, M.View(100, 0, 120, 20)
        cam = M.Camera.move(start, end, start=1.0, duration=2.0)
        self.assertEqual(cam.view_at(0.0), start)
        self.assertEqual(cam.view_at(1.0), start)
        self.assertEqual(cam.view_at(3.0), end)
        self.assertEqual(cam.view_at(9.0), end)

    def test_move_is_between_the_ends_in_the_middle(self):
        start, end = M.WORLD, M.View(100, 0, 120, 20)
        mid = M.Camera.move(start, end, start=0.0, duration=2.0).view_at(1.0)
        self.assertGreater(mid.min_lon, start.min_lon)
        self.assertLess(mid.min_lon, end.min_lon)

    def test_still_camera_never_moves(self):
        cam = M.Camera.still(M.View(0, 0, 10, 10))
        self.assertEqual(cam.view_at(0.0), cam.view_at(5.0))

    def test_zero_duration_move_is_refused(self):
        with self.assertRaises(M.MapError):
            M.Camera.move(M.WORLD, M.WORLD, start=0.0, duration=0.0)


class LoaderTests(unittest.TestCase):
    def test_no_path_and_no_env_is_a_clear_error(self):
        saved = os.environ.pop(M.ENV_VAR, None)
        try:
            with self.assertRaises(M.MapError) as ctx:
                M.load_countries()
            self.assertIn(M.ENV_VAR, str(ctx.exception))
        finally:
            if saved is not None:
                os.environ[M.ENV_VAR] = saved

    def test_missing_file_is_a_clear_error(self):
        with self.assertRaises(M.MapError):
            M.load_countries(Path("/nonexistent/countries.shp"))


if __name__ == "__main__":
    unittest.main()
