"""In-process job manager for the local API (Phase 12).

Jobs run on a thread pool. Each job has an id, a status (queued, running, succeeded, failed,
cancelled), a progress fraction, an optional result, an error report, output paths and completion
metadata. Jobs can be cancelled cooperatively (the worker checks a flag) and failed jobs can be
retried. Nothing here touches the network or the shell.
"""
from __future__ import annotations

import threading
import time
import traceback
import uuid
from concurrent.futures import ThreadPoolExecutor
from dataclasses import dataclass, field
from typing import Any, Callable

QUEUED, RUNNING, SUCCEEDED, FAILED, CANCELLED = "queued", "running", "succeeded", "failed", "cancelled"
TERMINAL = {SUCCEEDED, FAILED, CANCELLED}


class JobCancelled(Exception):
    pass


@dataclass
class JobHandle:
    """Passed to a worker so it can report progress and check for cancellation."""
    job_id: str
    _manager: "JobManager"

    def progress(self, fraction: float, message: str = "") -> None:
        self._manager._set_progress(self.job_id, fraction, message)

    def check_cancelled(self) -> None:
        if self._manager._is_cancel_requested(self.job_id):
            raise JobCancelled(self.job_id)


@dataclass
class Job:
    id: str
    kind: str
    status: str = QUEUED
    progress: float = 0.0
    message: str = ""
    result: Any = None
    error: str | None = None
    outputs: list[str] = field(default_factory=list)
    created_at: float = field(default_factory=time.time)
    started_at: float | None = None
    finished_at: float | None = None
    _fn: Callable[[JobHandle], Any] | None = None
    _cancel: bool = False

    def to_dict(self) -> dict:
        return {"id": self.id, "kind": self.kind, "status": self.status,
                "progress": round(self.progress, 4), "message": self.message,
                "error": self.error, "outputs": list(self.outputs),
                "created_at": self.created_at, "started_at": self.started_at,
                "finished_at": self.finished_at,
                "duration_s": (round(self.finished_at - self.started_at, 3)
                               if self.started_at and self.finished_at else None)}


class JobManager:
    def __init__(self, workers: int = 2):
        self._pool = ThreadPoolExecutor(max_workers=workers)
        self._jobs: dict[str, Job] = {}
        self._lock = threading.Lock()

    def submit(self, kind: str, fn: Callable[[JobHandle], Any]) -> str:
        job_id = uuid.uuid4().hex[:16]
        job = Job(id=job_id, kind=kind, _fn=fn)
        with self._lock:
            self._jobs[job_id] = job
        self._pool.submit(self._run, job_id)
        return job_id

    def _run(self, job_id: str) -> None:
        with self._lock:
            job = self._jobs[job_id]
            if job._cancel:
                job.status = CANCELLED
                job.finished_at = time.time()
                return
            job.status = RUNNING
            job.started_at = time.time()
            fn = job._fn
        handle = JobHandle(job_id, self)
        try:
            result = fn(handle)
            with self._lock:
                job = self._jobs[job_id]
                job.status = SUCCEEDED
                job.progress = 1.0
                job.result = result
                if isinstance(result, dict) and "outputs" in result:
                    job.outputs = list(result["outputs"])
        except JobCancelled:
            with self._lock:
                self._jobs[job_id].status = CANCELLED
        except Exception as exc:  # noqa: BLE001 - we record any worker error
            with self._lock:
                job = self._jobs[job_id]
                job.status = FAILED
                job.error = f"{type(exc).__name__}: {exc}"
                job.message = traceback.format_exc().strip().splitlines()[-1]
        finally:
            with self._lock:
                self._jobs[job_id].finished_at = time.time()

    def _set_progress(self, job_id: str, fraction: float, message: str) -> None:
        with self._lock:
            job = self._jobs.get(job_id)
            if job and job.status == RUNNING:
                job.progress = max(0.0, min(1.0, fraction))
                if message:
                    job.message = message

    def _is_cancel_requested(self, job_id: str) -> bool:
        with self._lock:
            job = self._jobs.get(job_id)
            return bool(job and job._cancel)

    def get(self, job_id: str) -> Job:
        with self._lock:
            if job_id not in self._jobs:
                raise KeyError(job_id)
            return self._jobs[job_id]

    def status(self, job_id: str) -> dict:
        return self.get(job_id).to_dict()

    def cancel(self, job_id: str) -> dict:
        with self._lock:
            job = self._jobs.get(job_id)
            if job is None:
                raise KeyError(job_id)
            if job.status in TERMINAL:
                return job.to_dict()
            job._cancel = True
            if job.status == QUEUED:
                job.status = CANCELLED
                job.finished_at = time.time()
            return job.to_dict()

    def retry(self, job_id: str) -> str:
        with self._lock:
            job = self._jobs.get(job_id)
            if job is None:
                raise KeyError(job_id)
            if job.status not in {FAILED, CANCELLED}:
                raise ValueError(f"job {job_id} is {job.status}, only failed/cancelled jobs retry")
            fn = job._fn
            kind = job.kind
        return self.submit(kind, fn)

    def wait(self, job_id: str, timeout: float = 30.0, poll: float = 0.02) -> dict:
        deadline = time.time() + timeout
        while time.time() < deadline:
            st = self.status(job_id)
            if st["status"] in TERMINAL:
                return st
            time.sleep(poll)
        raise TimeoutError(f"job {job_id} did not finish within {timeout}s")

    def list_jobs(self) -> list[dict]:
        with self._lock:
            return [j.to_dict() for j in self._jobs.values()]

    def shutdown(self) -> None:
        self._pool.shutdown(wait=False, cancel_futures=True)
