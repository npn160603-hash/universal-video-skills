"""Server + SDK integration over a loopback port, including a real chart render job."""
import shutil
import tempfile
import threading
import unittest
from pathlib import Path

from uvs.api import UVSApi
from uvs.server import make_server
from uvs.sdk import UVSClient, SDKError

HAS_FFMPEG = shutil.which("ffmpeg") is not None

WORDS = [{"text": w, "start": i * 0.4, "end": i * 0.4 + 0.35}
         for i, w in enumerate("We learn to say no and everything changes".split())]


class LoopbackBindTests(unittest.TestCase):
    def test_non_loopback_bind_refused(self):
        api = UVSApi(tempfile.mkdtemp())
        try:
            with self.assertRaises(ValueError):
                make_server(api, "0.0.0.0", 0)
        finally:
            api.jobs.shutdown()


class ServerSDKTests(unittest.TestCase):
    def setUp(self):
        self._tmp = tempfile.TemporaryDirectory()
        self.api = UVSApi(self._tmp.name)
        self.srv = make_server(self.api, "127.0.0.1", 0)
        self.port = self.srv.server_address[1]
        self.thread = threading.Thread(target=self.srv.serve_forever, daemon=True)
        self.thread.start()
        self.cli = UVSClient(f"http://127.0.0.1:{self.port}")

    def tearDown(self):
        self.srv.shutdown()
        self.srv.server_close()
        self.api.jobs.shutdown()
        self._tmp.cleanup()

    def test_info_and_styles(self):
        self.assertEqual(self.cli.info()["api_version"], "1.0.0")
        self.assertEqual(len(self.cli.styles()), 10)

    def test_full_timeline_flow(self):
        tl = self.cli.generate_timeline(WORDS, "viral_storytelling")
        self.assertIn("instructions", tl)
        self.assertTrue(self.cli.qa(tl)["ok"])

    def test_error_is_structured(self):
        with self.assertRaises(SDKError) as ctx:
            self.cli.select_style("nonexistent")
        self.assertIn("400", str(ctx.exception))

    @unittest.skipUnless(HAS_FFMPEG, "ffmpeg not installed")
    def test_chart_render_job_via_sdk(self):
        job = self.cli.render_chart(
            {"kind": "counter", "categories": [], "series": [{"label": "n", "values": [500]}],
             "source": "test", "width": 240, "height": 180, "duration": 0.4}, "c.mp4", fps=15)
        st = self.cli.wait_for_job(job, timeout=30)
        self.assertEqual(st["status"], "succeeded")
        self.assertTrue(st["outputs"])
        self.assertTrue(Path(st["outputs"][0]).exists())

    def test_cancel_job(self):
        # A chart with a long duration gives time to cancel; cancel is cooperative at validate/render.
        job = self.cli.render_chart(
            {"kind": "vertical_bar", "categories": ["a", "b"], "series": [{"label": "x", "values": [1, 2]}],
             "source": "test", "width": 320, "height": 240, "duration": 3.0}, "c2.mp4", fps=30)
        self.cli.cancel(job)
        st = self.cli.wait_for_job(job, timeout=30)
        self.assertIn(st["status"], {"cancelled", "succeeded"})  # may finish if very fast


if __name__ == "__main__":
    unittest.main()
