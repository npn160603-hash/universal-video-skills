"""Phase 6 render path: chart/explainer videos encode, and infographics compose on a timeline."""
import shutil
import subprocess
import tempfile
import unittest
from fractions import Fraction
from pathlib import Path

from uvs.infographics import ChartSpec, Series, chart_video
from uvs.explainers import (Timeline as TLine, Event, render_timeline_frame, Diagram, DiagNode,
                            DiagEdge, render_diagram_frame, Metaphor, render_metaphor_frame,
                            render_video)
from uvs.visuals import render_visual, to_timeline_clip, Controls
from uvs import timeline as TL

HAS_FFMPEG = shutil.which("ffmpeg") is not None and shutil.which("ffprobe") is not None


def _nb_frames(path) -> int:
    out = subprocess.run(["ffprobe", "-v", "error", "-select_streams", "v:0", "-count_frames",
                          "-show_entries", "stream=nb_read_frames", "-of", "csv=p=0", str(path)],
                         capture_output=True, text=True, check=True)
    return int(out.stdout.strip())


@unittest.skipUnless(HAS_FFMPEG, "ffmpeg not installed")
class ChartVideoTests(unittest.TestCase):
    def setUp(self):
        self._tmp = tempfile.TemporaryDirectory()
        self.dir = Path(self._tmp.name)

    def tearDown(self):
        self._tmp.cleanup()

    def test_comparison_chart_encodes_with_expected_frame_count(self):
        cs = ChartSpec("comparison", ("22", "23"), (Series("a", (4, 6)), Series("b", (3, 2))),
                       title="Cmp", source="demo", width=320, height=240, duration=1.0)
        out = self.dir / "cmp.mp4"
        info = chart_video(cs, out, fps=20, hold_seconds=0.5)
        self.assertEqual(info["frames"], _nb_frames(out))
        self.assertEqual(info["frames"], 30)  # 1.5s * 20fps

    def test_timeline_and_diagram_and_metaphor_encode(self):
        tl = TLine("historical", (Event(2000, "a"), Event(2010, "b")), width=320, height=240)
        dg = Diagram("process", (DiagNode("a", "A", 0), DiagNode("b", "B", 1)),
                     (DiagEdge("a", "b"),), width=320, height=240, node_w=120, node_h=70)
        m = Metaphor("time_passing", width=240, height=320)
        for name, fn, w, h in [("tl", lambda p: render_timeline_frame(tl, p), 320, 240),
                               ("dg", lambda p: render_diagram_frame(dg, p), 320, 240),
                               ("mt", lambda p: render_metaphor_frame(m, p), 240, 320)]:
            with self.subTest(name=name):
                out = self.dir / f"{name}.mp4"
                info = render_video(fn, out, duration=1.0, fps=20, width=w, height=h, hold=0.0)
                self.assertEqual(info["frames"], _nb_frames(out))


@unittest.skipUnless(HAS_FFMPEG, "ffmpeg not installed")
class TimelineIntegrationTests(unittest.TestCase):
    def setUp(self):
        self._tmp = tempfile.TemporaryDirectory()
        self.dir = Path(self._tmp.name)

    def tearDown(self):
        self._tmp.cleanup()

    def test_two_infographics_compose_on_a_timeline(self):
        cs = ChartSpec("vertical_bar", ("A", "B", "C"), (Series("x", (10, 20, 15)),),
                       source="demo", width=320, height=240, duration=0.8)
        dg = Diagram("process", (DiagNode("a", "Start", 0), DiagNode("b", "End", 1)),
                     (DiagEdge("a", "b"),), width=320, height=240, node_w=120, node_h=70)
        i1 = render_visual(lambda p: __import__("uvs.infographics", fromlist=["render_chart_frame"])
                           .render_chart_frame(cs, p), self.dir / "i1.mp4", duration=0.8, fps=24,
                           width=320, height=240, hold=0.2)
        i2 = render_visual(lambda p: render_diagram_frame(dg, p), self.dir / "i2.mp4", duration=0.8,
                           fps=24, width=320, height=240, hold=0.2, controls=Controls(zoom_from=1.0, zoom_to=1.1))
        c1 = to_timeline_clip("chart", str(self.dir / "i1.mp4"), i1["frames"], 24, start=0)
        c2 = to_timeline_clip("diag", str(self.dir / "i2.mp4"), i2["frames"], 24, start=i1["frames"])
        tl = TL.Timeline(fps=Fraction(24), width=320, height=240,
                         tracks=[TL.Track("video", "main", [c1, c2])])
        errors = [i for i in TL.validate(tl, check_files=True) if i.level == "error"]
        self.assertEqual(errors, [])
        out = self.dir / "composed.mp4"
        TL.render(tl, out)
        self.assertEqual(_nb_frames(out), i1["frames"] + i2["frames"])


if __name__ == "__main__":
    unittest.main()
