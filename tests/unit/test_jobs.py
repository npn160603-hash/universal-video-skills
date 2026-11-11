"""Job manager: lifecycle, progress, cancellation, retry, errors."""
import threading
import time
import unittest

from uvs.jobs import JobManager, JobHandle, JobCancelled, SUCCEEDED, FAILED, CANCELLED


class JobManagerTests(unittest.TestCase):
    def setUp(self):
        self.jm = JobManager(workers=2)

    def tearDown(self):
        self.jm.shutdown()

    def test_successful_job_reports_result_and_outputs(self):
        jid = self.jm.submit("test", lambda h: {"outputs": ["a.mp4"], "value": 42})
        st = self.jm.wait(jid, timeout=5)
        self.assertEqual(st["status"], SUCCEEDED)
        self.assertEqual(st["progress"], 1.0)
        self.assertEqual(st["outputs"], ["a.mp4"])
        self.assertEqual(self.jm.get(jid).result["value"], 42)

    def test_progress_is_reported(self):
        seen = []

        def worker(h: JobHandle):
            for p in (0.25, 0.5, 0.75):
                h.progress(p, f"at {p}")
                seen.append(p)
            return {}
        jid = self.jm.submit("test", worker)
        self.jm.wait(jid, timeout=5)
        self.assertEqual(seen, [0.25, 0.5, 0.75])

    def test_failing_job_records_error(self):
        def boom(h):
            raise RuntimeError("kaboom")
        jid = self.jm.submit("test", boom)
        st = self.jm.wait(jid, timeout=5)
        self.assertEqual(st["status"], FAILED)
        self.assertIn("kaboom", st["error"])

    def test_cancellation_is_cooperative(self):
        started = threading.Event()

        def long(h: JobHandle):
            started.set()
            for _ in range(100):
                h.check_cancelled()
                time.sleep(0.02)
            return {}
        jid = self.jm.submit("test", long)
        started.wait(timeout=2)
        self.jm.cancel(jid)
        st = self.jm.wait(jid, timeout=5)
        self.assertEqual(st["status"], CANCELLED)

    def test_retry_resubmits_a_failed_job(self):
        calls = {"n": 0}

        def flaky(h):
            calls["n"] += 1
            if calls["n"] == 1:
                raise ValueError("first fails")
            return {"outputs": ["ok"]}
        jid = self.jm.submit("test", flaky)
        self.assertEqual(self.jm.wait(jid, timeout=5)["status"], FAILED)
        jid2 = self.jm.retry(jid)
        self.assertEqual(self.jm.wait(jid2, timeout=5)["status"], SUCCEEDED)

    def test_retry_of_successful_job_rejected(self):
        jid = self.jm.submit("test", lambda h: {})
        self.jm.wait(jid, timeout=5)
        with self.assertRaises(ValueError):
            self.jm.retry(jid)

    def test_unknown_job_raises(self):
        with self.assertRaises(KeyError):
            self.jm.status("nope")


if __name__ == "__main__":
    unittest.main()
