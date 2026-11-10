"""Motion engine end to end: animated graph encoded to MP4, then decoded and checked."""
import json
import shutil
import subprocess
import tempfile
import unittest
from pathlib import Path

from uvs import animate as A
from uvs import scenegraph as G

HAS_FFMPEG = shutil.which("ffmpeg") is not None and shutil.which("ffprobe") is not None
W, H, FPS = 160, 120, 10


def _scene():
    square = G.Node(id="sq", kind="shape", transform=G.Transform(y=40), width=40, height=40,
                    payload={"fill": "#ff0000"})
    return G.SceneGraph(root=G.Node(id="root", kind="group", children=[square]))


def _anim():
    return A.Animation.from_spec({"sq": {"x": [{"time": 0, "value": 0, "easing": "linear"},
                                              {"time": 1.0, "value": 100}]}})


def _decode_frames(path: Path) -> list[bytes]:
    proc = subprocess.run(["ffmpeg", "-hide_banner", "-loglevel", "error", "-i", str(path),
                           "-f", "rawvideo", "-pix_fmt", "rgb24", "-"], capture_output=True, check=True)
    size = W * H * 3
    data = proc.stdout
    return [data[i:i + size] for i in range(0, len(data) - size + 1, size)]


def _pixel(frame: bytes, x: int, y: int):
    i = (y * W + x) * 3
    return frame[i], frame[i + 1], frame[i + 2]


@unittest.skipUnless(HAS_FFMPEG, "ffmpeg not installed")
class VideoRenderTests(unittest.TestCase):
    def setUp(self):
        self._tmp = tempfile.TemporaryDirectory()
        self.out = Path(self._tmp.name) / "motion.mp4"
        self.info = A.render_video(_scene(), _anim(), self.out, fps=FPS, duration=1.0,
                                   width=W, height=H)

    def tearDown(self):
        self._tmp.cleanup()

    def test_frame_count_and_duration_match_the_request(self):
        probe = subprocess.run(["ffprobe", "-v", "error", "-count_frames", "-select_streams", "v:0",
                                "-show_entries", "stream=nb_read_frames,width,height",
                                "-of", "json", str(self.out)], capture_output=True, text=True, check=True)
        stream = json.loads(probe.stdout)["streams"][0]
        self.assertEqual(int(stream["nb_read_frames"]), FPS)
        self.assertEqual((int(stream["width"]), int(stream["height"])), (W, H))
        self.assertEqual(self.info["frames"], FPS)

    def test_square_starts_left_and_ends_right(self):
        frames = _decode_frames(self.out)
        self.assertEqual(len(frames), FPS)
        # First frame: square spans x 0..39, centre at (20, 60). Last frame: x = 90, centre (110, 60).
        r, g, b = _pixel(frames[0], 20, 60)
        self.assertTrue(r > 180 and g < 80 and b < 80, (r, g, b))
        r, g, b = _pixel(frames[0], 110, 60)
        self.assertTrue(r < 40 and g < 40 and b < 40, (r, g, b))
        r, g, b = _pixel(frames[-1], 110, 60)
        self.assertTrue(r > 180 and g < 80 and b < 80, (r, g, b))
        r, g, b = _pixel(frames[-1], 20, 60)
        self.assertTrue(r < 40 and g < 40 and b < 40, (r, g, b))

    def test_unknown_container_fails_with_a_clear_error(self):
        with self.assertRaises(A.AnimationError) as ctx:
            A.render_video(_scene(), _anim(), Path(self._tmp.name) / "bad.xyz", fps=FPS,
                           duration=1.0, width=W, height=H)
        self.assertIn("ffmpeg failed", str(ctx.exception))

    def test_odd_dimensions_are_refused_before_encoding(self):
        with self.assertRaises(A.AnimationError):
            A.render_video(_scene(), _anim(), Path(self._tmp.name) / "odd.mp4", fps=FPS,
                           duration=1.0, width=161, height=120)


if __name__ == "__main__":
    unittest.main()
