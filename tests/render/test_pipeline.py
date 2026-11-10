"""Integration tests that run real ffmpeg. Each QA test builds a clip with a known defect
and checks that the matching check catches it. Skipped when ffmpeg is missing."""
import json
import shutil
import subprocess
import tempfile
import unittest
from pathlib import Path

from uvs import qa as Q
from uvs.render import render_captioned

ROOT = Path(__file__).resolve().parents[2]
DEMO = ROOT / "examples" / "demo_caption" / "words.json"
HAS_FFMPEG = shutil.which("ffmpeg") is not None and shutil.which("ffprobe") is not None


def _ff(args):
    proc = subprocess.run(["ffmpeg", "-hide_banner", "-loglevel", "error", "-y", *args],
                          capture_output=True, text=True)
    if proc.returncode != 0:
        raise RuntimeError(proc.stderr)


def _clip(path: Path, video_filter: str = "", audio_filter: str = "", silent: bool = False):
    """320x240 25fps 3s clip: 1s black + 2s test pattern. Audio is a 440 Hz tone or silence."""
    audio_in = (["-f", "lavfi", "-i", "anullsrc=r=48000:cl=stereo"] if silent
                else ["-f", "lavfi", "-i", "sine=f=440:d=3:sample_rate=48000"])
    args = [
        "-f", "lavfi", "-i", "color=c=black:s=320x240:r=25:d=1",
        "-f", "lavfi", "-i", "testsrc2=s=320x240:r=25:d=2",
        *audio_in,
        "-filter_complex", "[0:v][1:v]concat=n=2:v=1:a=0[v]",
        "-map", "[v]", "-map", "2:a",
        "-t", "3",
        "-c:v", "libx264", "-pix_fmt", "yuv420p", "-c:a", "aac",
    ]
    if audio_filter:
        args += ["-af", audio_filter]
    _ff([*args, str(path)])
    return path


@unittest.skipUnless(HAS_FFMPEG, "ffmpeg/ffprobe not installed")
class QATests(unittest.TestCase):
    def setUp(self):
        self._tmp = tempfile.TemporaryDirectory()
        self.tmp = Path(self._tmp.name)
        self.cfg = Q.QAConfig(expect_width=320, expect_height=240, expect_fps=25.0,
                              expect_video_codec="h264", expect_audio_codec="aac")

    def tearDown(self):
        self._tmp.cleanup()

    def checks(self, report):
        return {c.id: c for c in report.checks}

    def test_clean_clip_detects_leading_black_and_passes_technical(self):
        clip = _clip(self.tmp / "clean.mp4")
        report = Q.run_qa(clip, self.cfg)
        c = self.checks(report)
        self.assertEqual(c["dimensions"].status, "pass")
        self.assertEqual(c["fps"].status, "pass")
        self.assertEqual(c["decode"].status, "pass")
        self.assertEqual(c["black_frames"].status, "warn")
        self.assertLess(c["black_frames"].value[0], 0.1)  # black starts at t=0

    def test_wrong_fps_is_a_failure(self):
        clip = _clip(self.tmp / "clean.mp4")
        cfg = Q.QAConfig(expect_width=320, expect_height=240, expect_fps=30.0, expect_video_codec="h264")
        report = Q.run_qa(clip, cfg)
        self.assertEqual(self.checks(report)["fps"].status, "fail")
        self.assertEqual(report.overall, "fail")

    def test_clipping_is_detected(self):
        clip = _clip(self.tmp / "loud.mp4", audio_filter="volume=30dB")
        report = Q.run_qa(clip, self.cfg)
        self.assertEqual(self.checks(report)["clipping"].status, "fail")

    def test_long_silence_is_detected(self):
        clip = _clip(self.tmp / "silent.mp4", silent=True)
        report = Q.run_qa(clip, self.cfg)
        self.assertEqual(self.checks(report)["long_silence"].status, "warn")

    def test_loudness_and_true_peak_are_measured(self):
        clip = _clip(self.tmp / "clean.mp4")
        report = Q.run_qa(clip, self.cfg)
        c = self.checks(report)
        self.assertIn("loudness", c)
        self.assertIsNotNone(c["loudness"].value)
        self.assertIsNotNone(c["true_peak"].value)


@unittest.skipUnless(HAS_FFMPEG, "ffmpeg/ffprobe not installed")
class RenderTests(unittest.TestCase):
    def test_demo_renders_at_9x16_h264_aac_with_captions(self):
        with tempfile.TemporaryDirectory() as tmp:
            result = render_captioned(DEMO, tmp, style="bold_shorts", keywords=("cháo", "5"))
            self.assertNotEqual(result["qa_overall"], "fail")
            self.assertEqual(result["cues"], 4)
            final = Path(result["final"])
            self.assertTrue(final.exists() and final.stat().st_size > 10_000)
            probe = json.loads(subprocess.run(
                ["ffprobe", "-v", "error", "-print_format", "json", "-show_streams", str(final)],
                capture_output=True, text=True, check=True).stdout)
            video = next(s for s in probe["streams"] if s["codec_type"] == "video")
            audio = next(s for s in probe["streams"] if s["codec_type"] == "audio")
            self.assertEqual((video["width"], video["height"]), (1080, 1920))
            self.assertEqual(video["codec_name"], "h264")
            self.assertEqual(audio["codec_name"], "aac")
            self.assertEqual(video["avg_frame_rate"], "30/1")
            # Captions must be present as subtitle text in the ASS file the render used.
            ass = Path(result["captions"]["ass"]).read_text(encoding="utf-8")
            self.assertIn("vẫn dậy lúc", ass)


if __name__ == "__main__":
    unittest.main()
