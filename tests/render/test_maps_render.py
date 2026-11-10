"""Map engine on Natural Earth data and encoded to MP4. Real data needs UVS_NATURAL_EARTH_SHP."""
import os
import shutil
import subprocess
import tempfile
import unittest
from pathlib import Path

from uvs import maps as M

HAS_FFMPEG = shutil.which("ffmpeg") is not None and shutil.which("ffprobe") is not None
SHP = os.environ.get(M.ENV_VAR)
HAS_DATA = bool(SHP) and Path(SHP).exists()

HIGHLIGHT = "#d7263d"
MARKER = "#f4d35e"
W, H = 400, 300


@unittest.skipUnless(HAS_DATA, f"set {M.ENV_VAR} to a Natural Earth countries .shp file")
class RealDataTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.countries = M.load_countries(SHP)

    def test_file_has_177_countries_with_names_and_codes(self):
        self.assertEqual(len(self.countries), 177)
        vnm = [c for c in self.countries if c.iso3 == "VNM"]
        self.assertEqual(len(vnm), 1)
        self.assertEqual(vnm[0].name, "Vietnam")

    def test_only_south_africa_has_a_hole_in_this_file(self):
        with_holes = [c.name for c in self.countries if any(h for _, h in c.rings)]
        self.assertEqual(with_holes, ["South Africa"])

    def test_vietnam_is_highlighted_where_hanoi_is_and_laos_is_not(self):
        scene = M.MapScene(countries=self.countries, camera=M.Camera.still(M.View(95, 5, 120, 30)),
                           width=W, height=H, highlights={"VNM": HIGHLIGHT})
        f = scene.frame(0.0)
        proj = M.Projector(M.View(95, 5, 120, 30), W, H)
        hx, hy = (round(v) for v in proj.project(105.85, 21.03))   # Hanoi
        lx, ly = (round(v) for v in proj.project(102.6, 17.97))    # Vientiane, Laos
        self.assertEqual(f.getpixel((hx, hy)), (215, 38, 61))
        self.assertNotEqual(f.getpixel((lx, ly)), (215, 38, 61))

    def test_mercator_and_equirectangular_both_render(self):
        for proj_name in M.PROJECTIONS:
            with self.subTest(projection=proj_name):
                scene = M.MapScene(countries=self.countries, camera=M.Camera.still(M.WORLD),
                                   width=W, height=H, projection=proj_name)
                self.assertEqual(scene.frame(0.0).size, (W, H))


@unittest.skipUnless(HAS_FFMPEG, "ffmpeg not installed")
class VideoTests(unittest.TestCase):
    def setUp(self):
        self._tmp = tempfile.TemporaryDirectory()
        self.dir = Path(self._tmp.name)

    def tearDown(self):
        self._tmp.cleanup()

    def test_route_and_marker_encode_to_mp4_with_the_requested_frames(self):
        square = M._make_country("Square", "SQR", "t", [[(0, 0), (0, 10), (10, 10), (10, 0)]])
        route = M.Route(points=M.route_through([(-20, 0), (20, 0)], n_per_leg=20), start=0.2,
                        duration=0.6, color=MARKER, width=4, easing="linear")
        marker = M.Marker(lon=20, lat=0, start=0.8, color=MARKER, radius=6)
        scene = M.MapScene(countries=[square], camera=M.Camera.move(M.WORLD, M.View(-30, -10, 30, 10),
                                                                   start=0.0, duration=1.0),
                           width=160, height=120, highlights={"SQR": HIGHLIGHT},
                           routes=[route], markers=[marker])
        out = self.dir / "map.mp4"
        info = M.render_map_video(scene, out, fps=10, duration=1.5)
        self.assertEqual(info["frames"], 15)
        probe = subprocess.run(["ffprobe", "-v", "error", "-count_frames", "-select_streams", "v:0",
                                "-show_entries", "stream=nb_read_frames", "-of", "csv=p=0", str(out)],
                               capture_output=True, text=True, check=True)
        self.assertEqual(int(probe.stdout.strip()), 15)

    def test_wrong_size_frame_is_refused_by_the_encoder(self):
        from PIL import Image
        from uvs import animate as A
        with self.assertRaises(A.AnimationError):
            A.encode_frames(self.dir / "bad.mp4", fps=10, width=40, height=40,
                            frames=[Image.new("RGB", (30, 30))])


if __name__ == "__main__":
    unittest.main()
