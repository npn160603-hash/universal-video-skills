"""Map demo: Vietnam highlighted, great-circle route to London, camera moves from world to route.

Needs Natural Earth 110 m countries (public domain, not bundled):
    UVS_NATURAL_EARTH_SHP=/path/naturalearth_lowres.shp python3 examples/map_demo/demo.py out/map_demo.mp4
"""
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[2]))
from uvs import maps as M  # noqa: E402


def build_scene(countries):
    hanoi, london = (105.85, 21.03), (-0.13, 51.51)
    route = M.Route(points=M.route_through([hanoi, london], n_per_leg=120), start=1.0, duration=2.5,
                    color="#f4d35e", width=4)
    markers = [M.Marker(*hanoi, start=0.4, color="#f4d35e"), M.Marker(*london, start=3.5, color="#f4d35e")]
    camera = M.Camera.move(M.WORLD, M.View(-30, 0, 130, 65), start=0.0, duration=3.0)
    return M.MapScene(countries=countries, camera=camera, width=1280, height=720,
                      projection="equirectangular", highlights={"VNM": "#d7263d"},
                      routes=[route], markers=markers)


def main(argv):
    out = Path(argv[1] if len(argv) > 1 else "out/map_demo.mp4")
    scene = build_scene(M.load_countries())
    info = M.render_map_video(scene, out, fps=30, duration=4.5)
    print(info)
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv))
