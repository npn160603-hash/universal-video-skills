"""Real renders of a timeline with cut, dissolve, and dip-to-black transitions.
Pixel values are read back from the output file, so the transitions are checked, not assumed."""
import json
import shutil
import subprocess
import tempfile
import unittest
from fractions import Fraction
from pathlib import Path

from uvs import timeline as T

HAS_FFMPEG = shutil.which("ffmpeg") is not None and shutil.which("ffprobe") is not None


def _solid(path: Path, color: str, seconds: float = 1.0, with_tone: bool = False):
    args = ["ffmpeg", "-hide_banner", "-loglevel", "error", "-y",
            "-f", "lavfi", "-i", f"color=c={color}:s=320x240:r=30:d={seconds}"]
    if with_tone:
        args += ["-f", "lavfi", "-i", f"sine=f=330:d={seconds}:sample_rate=48000",
                 "-filter:a", "volume=-18dB", "-c:a", "aac"]
    args += ["-c:v", "libx264", "-pix_fmt", "yuv420p", str(path)]
    subprocess.run(args, check=True)
    return path


def _mean_rgb(path: Path, t: float):
    """Average colour of the frame at time t (scaled to a single pixel)."""
    proc = subprocess.run(
        ["ffmpeg", "-hide_banner", "-loglevel", "error", "-ss", f"{t:.4f}", "-i", str(path),
         "-frames:v", "1", "-vf", "scale=1:1", "-f", "rawvideo", "-pix_fmt", "rgb24", "-"],
        capture_output=True, check=True)
    r, g, b = proc.stdout[0], proc.stdout[1], proc.stdout[2]
    return int(r), int(g), int(b)


def _duration(path: Path) -> float:
    out = subprocess.run(
        ["ffprobe", "-v", "error", "-show_entries", "format=duration", "-of", "json", str(path)],
        capture_output=True, text=True, check=True).stdout
    return float(json.loads(out)["format"]["duration"])


@unittest.skipUnless(HAS_FFMPEG, "ffmpeg/ffprobe not installed")
class TimelineRenderTests(unittest.TestCase):
    def setUp(self):
        self._tmp = tempfile.TemporaryDirectory()
        self.dir = Path(self._tmp.name)
        self.red = _solid(self.dir / "red.mp4", "red", with_tone=True)
        self.green = _solid(self.dir / "green.mp4", "green")
        self.blue = _solid(self.dir / "blue.mp4", "blue")

    def tearDown(self):
        self._tmp.cleanup()

    def test_cut_dissolve_and_dip_to_black_render_with_expected_timing(self):
        tl = T.Timeline(fps=Fraction(30), width=320, height=240, tracks=[
            T.Track("video", "main", [
                T.Clip("a", str(self.red), start=0, duration=30),
                T.Clip("b", str(self.green), start=15, duration=30,
                       transition="dissolve", transition_frames=15),
                T.Clip("c", str(self.blue), start=30, duration=30,
                       transition="dip_black", transition_frames=15),
            ]),
        ])
        self.assertEqual([i for i in T.validate(tl) if i.level == "error"], [])
        out = T.render(tl, self.dir / "out.mp4")

        # Total = 30 + 15 + 15 frames = 2.0 s
        self.assertAlmostEqual(_duration(out), 2.0, delta=0.08)

        r, g, b = _mean_rgb(out, 0.25)          # clip a only
        self.assertGreater(r, 150)
        self.assertLess(g, 60)

        r, g, b = _mean_rgb(out, 0.75)          # dissolve midpoint: red and green mix
        self.assertGreater(r, 60)
        self.assertGreater(g, 60)
        self.assertLess(b, 60)

        # Dip to black: the transition window is [1.0, 1.5] s. Black must appear inside it.
        # ffmpeg's fadeblack holds a black plateau near 1.1 s, not at the exact midpoint.
        window = [_mean_rgb(out, 1.0 + i * 0.04) for i in range(13)]  # 1.00 .. 1.48 s
        darkest = min(range(len(window)), key=lambda i: max(window[i]))
        self.assertLess(max(window[darkest]), 15)
        self.assertGreater(darkest, 0)
        self.assertLess(darkest, len(window) - 1)

        r, g, b = _mean_rgb(out, 1.9)           # clip c only
        self.assertGreater(b, 150)
        self.assertLess(r, 60)

    def test_audio_clip_is_mixed_at_its_start_frame(self):
        tl = T.Timeline(fps=Fraction(30), width=320, height=240, tracks=[
            T.Track("video", "main", [T.Clip("a", str(self.green), start=0, duration=60)]),
            T.Track("audio", "tone", [T.Clip("t", str(self.red), start=30, duration=30, gain_db=0)]),
        ])
        out = T.render(tl, self.dir / "audio.mp4")
        probe = subprocess.run(["ffprobe", "-v", "error", "-select_streams", "a", "-show_entries",
                                "stream=codec_name", "-of", "csv=p=0", str(out)],
                               capture_output=True, text=True, check=True).stdout.strip()
        self.assertEqual(probe, "aac")
        # Silence before the tone starts (first second), tone after it.
        before = subprocess.run(
            ["ffmpeg", "-hide_banner", "-ss", "0", "-t", "0.8", "-i", str(out), "-af", "volumedetect",
             "-vn", "-f", "null", "-"], capture_output=True, text=True).stderr
        after = subprocess.run(
            ["ffmpeg", "-hide_banner", "-ss", "1.2", "-t", "0.6", "-i", str(out), "-af", "volumedetect",
             "-vn", "-f", "null", "-"], capture_output=True, text=True).stderr
        import re
        def max_db(s):
            m = re.search(r"max_volume: (-?[\d.]+) dB", s)
            return float(m.group(1)) if m else -999.0
        # Source tone peaks near -36 dBFS (sine at -18 dB, then volume -18 dB). Compare relative to silence.
        self.assertLess(max_db(before), -60.0)
        self.assertGreater(max_db(after), max_db(before) + 25.0)


if __name__ == "__main__":
    unittest.main()
