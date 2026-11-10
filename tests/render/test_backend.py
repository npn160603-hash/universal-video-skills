"""Render-level checks for Phase 1: frame precision, deterministic output, and undo at pixel level."""
import json
import subprocess
import tempfile
import unittest
from fractions import Fraction
from pathlib import Path

from uvs import backend as B
from uvs import edit_ops as E
from uvs import timeline as T

W, H = 180, 320


def _make_clip(path: Path, color: str, seconds: float = 4.0) -> Path:
    subprocess.run(["ffmpeg", "-hide_banner", "-loglevel", "error", "-y", "-f", "lavfi",
                    "-i", f"color=c={color}:size={W}x{H}:rate=30", "-t", str(seconds),
                    "-pix_fmt", "yuv420p", "-c:v", "libx264", "-crf", "23", str(path)], check=True)
    return path


def _frame_count(path: Path) -> int:
    out = subprocess.run(["ffprobe", "-v", "error", "-count_frames", "-select_streams", "v:0",
                          "-show_entries", "stream=nb_read_frames", "-of", "json", str(path)],
                         capture_output=True, text=True, check=True).stdout
    return int(json.loads(out)["streams"][0]["nb_read_frames"])


def _framemd5(path: Path) -> str:
    out = subprocess.run(["ffmpeg", "-hide_banner", "-loglevel", "error", "-i", str(path),
                          "-map", "0:v:0", "-f", "framemd5", "-"], capture_output=True, text=True, check=True)
    return out.stdout


class BackendRenderTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls._tmp = tempfile.TemporaryDirectory()
        base = Path(cls._tmp.name)
        cls.red = _make_clip(base / "red.mp4", "red")
        cls.blue = _make_clip(base / "blue.mp4", "blue")
        cls.base = base

    @classmethod
    def tearDownClass(cls):
        cls._tmp.cleanup()

    def _timeline(self) -> T.Timeline:
        return T.Timeline(fps=Fraction(30), width=W, height=H, tracks=[T.Track("video", "main", [
            T.Clip(id="a", source=str(self.red), start=0, duration=60),
            T.Clip(id="b", source=str(self.blue), start=54, duration=60,
                   transition="dissolve", transition_frames=6),
        ])])

    def test_capabilities_report_real_codecs_and_filters(self):
        caps = B.FFmpegBackend().capabilities()
        self.assertTrue(caps["codecs"]["h264"])
        self.assertTrue(caps["filters"]["xfade"])
        self.assertIn("ffmpeg", caps["ffmpeg"].lower())

    def test_rendered_frame_count_is_exact(self):
        tl = self._timeline()
        self.assertEqual(tl.total_frames, 114)
        out = B.FFmpegBackend().render_timeline(tl, self.base / "t1.mp4")
        self.assertEqual(_frame_count(out), 114)

    def test_same_timeline_renders_identical_frames(self):
        backend = B.FFmpegBackend()
        a = backend.render_timeline(self._timeline(), self.base / "det_a.mp4")
        b = backend.render_timeline(self._timeline(), self.base / "det_b.mp4")
        self.assertEqual(_framemd5(a), _framemd5(b))

    def test_undo_at_pixel_level_restores_the_original_render(self):
        backend = B.FFmpegBackend()
        original = self._timeline()
        before = _framemd5(backend.render_timeline(original, self.base / "orig.mp4"))

        edited, rec = E.apply_op(original, "set_duration", {"track": "main", "clip_id": "a", "frames": 90})
        edited_out = backend.render_timeline(edited, self.base / "edited.mp4")
        self.assertEqual(_frame_count(edited_out), 144)  # 84 + 60 frames

        restored = E.undo(edited, rec)
        after = _framemd5(backend.render_timeline(restored, self.base / "restored.mp4"))
        self.assertEqual(before, after)

    def test_timeline_saved_and_reloaded_renders_the_same_frames(self):
        backend = B.FFmpegBackend()
        tl = self._timeline()
        path = T.save_timeline(tl, self.base / "saved.json")
        reloaded = T.load_timeline(path)
        a = _framemd5(backend.render_timeline(tl, self.base / "s1.mp4"))
        b = _framemd5(backend.render_timeline(reloaded, self.base / "s2.mp4"))
        self.assertEqual(a, b)


if __name__ == "__main__":
    unittest.main()
