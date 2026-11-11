"""Phase 13 with real encoding: hardware detection, exports, cache, benchmark."""
import shutil
import subprocess
import tempfile
import unittest
from pathlib import Path

from uvs import export as E

HAS_FFMPEG = shutil.which("ffmpeg") is not None and shutil.which("ffprobe") is not None


def _src(path: Path, w=640, h=360, seconds=1.0):
    subprocess.run(["ffmpeg", "-hide_banner", "-loglevel", "error", "-y", "-f", "lavfi",
                    "-i", f"testsrc2=s={w}x{h}:d={seconds}:r=15", "-f", "lavfi",
                    "-i", f"sine=440:d={seconds}", "-c:v", "libx264", "-c:a", "aac", "-shortest",
                    str(path)], check=True)


@unittest.skipUnless(HAS_FFMPEG, "ffmpeg not installed")
class HardwareTests(unittest.TestCase):
    def test_detection_reports_real_values(self):
        hw = E.detect_hardware()
        self.assertGreaterEqual(hw.cpu_cores, 1)
        self.assertGreater(hw.ram_gb, 0.5)
        self.assertIn("libx264", hw.working_video_encoders)
        self.assertIn("aac", hw.working_audio_encoders)

    def test_hw_encoders_not_claimed_without_a_gpu(self):
        hw = E.detect_hardware()
        if not hw.gpu_present:
            self.assertNotIn("h264_nvenc", hw.working_video_encoders)


@unittest.skipUnless(HAS_FFMPEG, "ffmpeg not installed")
class ExportTests(unittest.TestCase):
    def setUp(self):
        self._tmp = tempfile.TemporaryDirectory()
        self.dir = Path(self._tmp.name)
        self.src = self.dir / "src.mp4"
        _src(self.src)
        self.hw = E.detect_hardware()

    def tearDown(self):
        self._tmp.cleanup()

    def test_each_standard_profile_exports_to_correct_dimensions(self):
        for name, p in E.standard_profiles().items():
            with self.subTest(profile=name):
                out = self.dir / f"{name}.mp4"
                r = E.export(self.src, out, p, hardware=self.hw)
                w, h = p.dimensions()
                self.assertEqual((r["width"], r["height"]), (w, h))
                ok, frames = E.decode_valid(out)
                self.assertTrue(ok)
                self.assertGreater(frames, 0)

    def test_h265_exports_when_available(self):
        if "libx265" not in self.hw.working_video_encoders:
            self.skipTest("libx265 not available")
        out = self.dir / "h265.mp4"
        r = E.export(self.src, out, E.ExportProfile("t", "1:1", "720p", "h265"), hardware=self.hw)
        self.assertEqual(r["encoder"], "libx265")
        self.assertTrue(E.decode_valid(out)[0])

    def test_h265_falls_back_to_h264_without_encoder(self):
        hw = E.Hardware(2, 8, False, "none", ("libx264",), ("aac",), (), 100)
        out = self.dir / "fallback.mp4"
        r = E.export(self.src, out, E.ExportProfile("t", "1:1", "720p", "h265"), hardware=hw)
        self.assertEqual(r["encoder"], "libx264")


@unittest.skipUnless(HAS_FFMPEG, "ffmpeg not installed")
class CacheBenchmarkTests(unittest.TestCase):
    def setUp(self):
        self._tmp = tempfile.TemporaryDirectory()
        self.dir = Path(self._tmp.name)

    def tearDown(self):
        self._tmp.cleanup()

    def test_cache_reuses_an_unchanged_render(self):
        cache = E.RenderCache(self.dir / "cache")
        key = cache.key("inputs", "v1")
        calls = []

        def render(tmp):
            calls.append(1)
            subprocess.run(["ffmpeg", "-hide_banner", "-loglevel", "error", "-y", "-f", "lavfi",
                            "-i", "color=c=red:s=64x64:d=0.2:r=5", "-c:v", "libx264", str(tmp)], check=True)
        r1 = cache.get_or_render(key, render)
        r2 = cache.get_or_render(key, render)
        self.assertFalse(r1["cached"])
        self.assertTrue(r2["cached"])
        self.assertEqual(len(calls), 1)
        self.assertTrue(E.decode_valid(r2["path"])[0])

    def test_benchmark_measures_real_values(self):
        def render(out):
            subprocess.run(["ffmpeg", "-hide_banner", "-loglevel", "error", "-y", "-f", "lavfi",
                            "-i", "testsrc2=s=320x240:d=1:r=30", "-c:v", "libx264", str(out)], check=True)
        b = E.benchmark_render(render, self.dir / "bench.mp4")
        self.assertTrue(b.decode_ok)
        self.assertEqual(b.frames, 30)
        self.assertGreater(b.encoding_fps, 0)
        self.assertGreater(b.output_bytes, 0)

    def test_truncated_file_fails_decode_validity(self):
        good = self.dir / "good.mp4"
        subprocess.run(["ffmpeg", "-hide_banner", "-loglevel", "error", "-y", "-f", "lavfi",
                        "-i", "testsrc2=s=160x120:d=1:r=10", "-c:v", "libx264", str(good)], check=True)
        truncated = self.dir / "trunc.mp4"
        truncated.write_bytes(good.read_bytes()[:200])  # chop the file
        self.assertFalse(E.decode_valid(truncated)[0])


if __name__ == "__main__":
    unittest.main()
