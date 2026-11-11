"""Phase 15 demonstrations A-F.

Each demo renders a real MP4 by driving the modules built in earlier phases. Where real footage,
narration or licensed music is unavailable, the demo uses generated visuals and synthetic audio and
is labelled a TECHNICAL demonstration. Demo B uses real Natural Earth geodata when the shapefile is
available (UVS_NATURAL_EARTH_SHP), so its map is genuine.

Every builder returns a dict with the output path, whether it is a technical demo, and what stand-ins
were used, so the final report can state exactly what is real and what is not.
"""
from __future__ import annotations

import os
from pathlib import Path

from uvs.animate import encode_frames
from uvs.infographics import ChartSpec, Series, render_chart_frame
from uvs.explainers import (Diagram, DiagNode, DiagEdge, render_diagram_frame, Metaphor,
                            render_metaphor_frame)
from uvs.visuals import render_visual, Controls
from uvs import maps as MAPS


def _concat(clips: list[Path], out: Path) -> Path:
    """Concatenate same-size clips with ffmpeg concat demuxer."""
    import subprocess
    lst = out.with_suffix(".txt")
    lst.write_text("".join(f"file '{c.resolve()}'\n" for c in clips), encoding="utf-8")
    subprocess.run(["ffmpeg", "-hide_banner", "-loglevel", "error", "-y", "-f", "concat",
                    "-safe", "0", "-i", str(lst), "-c", "copy", str(out)], check=True)
    lst.unlink()
    return out


def _add_synthetic_bed(video: Path, mood: str = "calm") -> Path:
    """Mux a gentle synthetic ambient bed sized to the video. Labelled synthetic (not real music)."""
    import subprocess
    freqs = {"calm": (110, 165), "bright": (220, 330), "tense": (98, 131)}.get(mood, (110, 165))
    graph = (f"sine=frequency={freqs[0]}:sample_rate=48000[a0];"
             f"sine=frequency={freqs[1]}:sample_rate=48000[a1];"
             f"[a0][a1]amix=inputs=2,volume=-26dB,aformat=channel_layouts=stereo[a]")
    tmp = video.with_name(video.stem + "_av.mp4")
    subprocess.run(["ffmpeg", "-hide_banner", "-loglevel", "error", "-y", "-i", str(video),
                    "-filter_complex", graph, "-map", "0:v", "-map", "[a]", "-c:v", "copy",
                    "-c:a", "aac", "-shortest", str(tmp)], check=True)
    tmp.replace(video)
    return video


# ---------------------------------------------------------------------------
# Demo B — Travel documentary, Hanoi -> Tokyo (real map when geodata present)
# ---------------------------------------------------------------------------

def demo_travel(out: Path, *, fps: int = 30) -> dict:
    shp = os.environ.get(MAPS.ENV_VAR)
    stand_ins = []
    if shp and Path(shp).exists():
        countries = MAPS.load_countries(shp)
        real_map = True
    else:
        countries = []
        real_map = False
        stand_ins.append("map: no Natural Earth data; empty basemap")
    hanoi, tokyo = (105.85, 21.03), (139.69, 35.69)
    route = MAPS.Route(points=MAPS.route_through([hanoi, tokyo], n_per_leg=120), start=1.0,
                       duration=3.0, color="#f4d35e", width=5)
    markers = [MAPS.Marker(*hanoi, start=0.5, color="#d7263d"),
               MAPS.Marker(*tokyo, start=4.0, color="#d7263d")]
    camera = MAPS.Camera.move(MAPS.WORLD, MAPS.View(90, 5, 150, 50), start=0.0, duration=3.5)
    scene = MAPS.MapScene(countries=countries, camera=camera, width=1280, height=720,
                          projection="equirectangular", highlights={"VNM": "#8c3b3b", "JPN": "#8c3b3b"},
                          routes=[route], markers=markers)
    MAPS.render_map_video(scene, out, fps=fps, duration=5.0)
    _add_synthetic_bed(out, "bright")
    info = {"frames": 150}
    stand_ins.append("audio: synthetic ambient bed (not real music/narration)")
    return {"demo": "B_travel", "output": str(out), "technical": not real_map,
            "real_geodata": real_map, "stand_ins": stand_ins,
            "subject": "Hanoi to Tokyo", "frames": info["frames"]}


# ---------------------------------------------------------------------------
# Demo D — Educational short (real charts + diagram)
# ---------------------------------------------------------------------------

def demo_educational(out: Path, *, fps: int = 30) -> dict:
    tmp = out.parent
    chart = ChartSpec("comparison", ("2021", "2022", "2023"),
                      (Series("Requests", (40, 65, 90)), Series("Approvals", (30, 45, 70))),
                      title="Yeses vs Real Commitments", unit="", source="Illustrative figures",
                      legend=True, illustrative=True, width=1280, height=720, duration=2.5)
    c1 = tmp / "d_chart.mp4"
    render_visual(lambda p: render_chart_frame(chart, p), c1, duration=2.5, fps=fps,
                  width=1280, height=720, hold=0.5)
    dg = Diagram("process", (DiagNode("a", "Request", 0), DiagNode("b", "Pause", 1),
                             DiagNode("c", "Decide", 2), DiagNode("d", "Respond", 3)),
                 (DiagEdge("a", "b"), DiagEdge("b", "c"), DiagEdge("c", "d")),
                 title="How to Say No", width=1280, height=720, node_w=240, node_h=90)
    c2 = tmp / "d_diagram.mp4"
    render_visual(lambda p: render_diagram_frame(dg, p), c2, duration=2.5, fps=fps,
                  width=1280, height=720, hold=0.5)
    _concat([c1, c2], out)
    _add_synthetic_bed(out, "bright")
    return {"demo": "D_educational", "output": str(out), "technical": True,
            "stand_ins": ["data: illustrative figures, not sourced",
                          "audio: synthetic ambient bed (not real music/narration)"],
            "subject": "How people struggle to say no (educational)"}


# ---------------------------------------------------------------------------
# Demo F — Motion graphics showcase (real motion engine)
# ---------------------------------------------------------------------------

def demo_motion_graphics(out: Path, *, fps: int = 30) -> dict:
    from uvs import scenegraph as G
    from uvs.animate import Animation, render_video
    root = G.Node(id="root", kind="group", children=[
        G.Node(id="bg", kind="shape", transform=G.Transform(x=0, y=0), width=1280, height=720,
               payload={"fill": "#11141a", "shape": "rect"}),
        G.Node(id="card", kind="shape", transform=G.Transform(x=200, y=300, anchor_x=160, anchor_y=90),
               width=320, height=180, payload={"fill": "#d7263d", "shape": "rect"}),
        G.Node(id="dot", kind="shape", transform=G.Transform(x=900, y=360, anchor_x=50, anchor_y=50),
               width=100, height=100, payload={"fill": "#f4d35e", "shape": "ellipse"},
               children=[G.Node(id="moon", kind="shape",
                                transform=G.Transform(x=80, y=0, anchor_x=20, anchor_y=20),
                                width=40, height=40, payload={"fill": "#5aa0d6", "shape": "ellipse"})]),
    ])
    graph = G.SceneGraph(root=root)
    anim = Animation.from_spec({
        "card": {"x": [{"time": 0, "value": 200, "easing": "ease_out"}, {"time": 1.5, "value": 760}],
                 "rotation": [{"time": 0, "value": 0, "easing": "ease_in_out"}, {"time": 3, "value": 360}],
                 "opacity": [{"time": 0, "value": 0, "easing": "linear"}, {"time": 0.6, "value": 1}]},
        "dot": {"scale_x": [{"time": 0, "value": 0.4, "easing": "overshoot"}, {"time": 1.2, "value": 1.3}],
                "scale_y": [{"time": 0, "value": 0.4, "easing": "overshoot"}, {"time": 1.2, "value": 1.3}],
                "rotation": [{"time": 0, "value": 0, "easing": "linear"}, {"time": 3, "value": 720}]},
    })
    info = render_video(graph, anim, out, fps=fps, duration=3.0, width=1280, height=720,
                        background=(17, 20, 26))
    _add_synthetic_bed(out, "bright")
    return {"demo": "F_motion_graphics", "output": str(out), "technical": True,
            "stand_ins": ["shapes only; no footage",
                          "audio: synthetic ambient bed (not real music/narration)"],
            "subject": "Keyframes, easing, transform hierarchy, compositing", "frames": info["frames"]}


# ---------------------------------------------------------------------------
# Demos A, C, E — technical demos (metaphor + captions, no footage)
# ---------------------------------------------------------------------------

def _metaphor_demo(out: Path, kind: str, title: str, subject: str, mood: str = "calm", fps: int = 30) -> dict:
    m = Metaphor(kind, title=title, width=720, height=1280, duration=3.0)
    render_visual(lambda p: render_metaphor_frame(m, p), out, duration=3.0, fps=fps,
                  width=720, height=1280, hold=0.5, controls=Controls(zoom_from=1.0, zoom_to=1.08))
    _add_synthetic_bed(out, mood)
    return {"output": str(out), "technical": True, "subject": subject,
            "stand_ins": ["illustrative metaphor; no footage, no narration",
                          "audio: synthetic ambient bed (not real music/narration)"]}


def demo_emotional(out: Path, *, fps: int = 30) -> dict:
    r = _metaphor_demo(out, "personal_boundaries", "Learning to Say No",
                       "Person who always says yes learns boundaries", fps)
    r["demo"] = "A_emotional"
    return r


def demo_psychology(out: Path, *, fps: int = 30) -> dict:
    r = _metaphor_demo(out, "competing_choices", "Why We Can't Say No",
                       "Why people struggle to say no", fps)
    r["demo"] = "C_psychology"
    return r


def demo_lifestyle(out: Path, *, fps: int = 30) -> dict:
    r = _metaphor_demo(out, "time_passing", "A Creative Day",
                       "A day in the life of a creative professional", fps)
    r["demo"] = "E_lifestyle"
    return r


ALL_DEMOS = {
    "A_emotional": demo_emotional,
    "B_travel": demo_travel,
    "C_psychology": demo_psychology,
    "D_educational": demo_educational,
    "E_lifestyle": demo_lifestyle,
    "F_motion_graphics": demo_motion_graphics,
}
