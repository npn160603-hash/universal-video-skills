"""Python SDK for the local UVS JSON API (Phase 12).

A thin, dependency-free client over the loopback HTTP server in uvs.server. It mirrors the API
methods and adds a blocking `wait_for_job` helper. Use it from a local editor or a script; it never
talks to anything but the host you give it.
"""
from __future__ import annotations

import json
import time
import urllib.error
import urllib.request


class SDKError(RuntimeError):
    pass


class UVSClient:
    def __init__(self, base_url: str = "http://127.0.0.1:8721", timeout: float = 120.0):
        self.base = base_url.rstrip("/")
        self.timeout = timeout

    def _request(self, method: str, path: str, body: dict | None = None) -> dict:
        url = f"{self.base}{path}"
        data = json.dumps(body).encode("utf-8") if body is not None else None
        req = urllib.request.Request(url, data=data, method=method,
                                     headers={"Content-Type": "application/json"})
        try:
            with urllib.request.urlopen(req, timeout=self.timeout) as resp:
                return json.loads(resp.read())
        except urllib.error.HTTPError as exc:
            try:
                msg = json.loads(exc.read()).get("error", str(exc))
            except Exception:
                msg = str(exc)
            raise SDKError(f"{exc.code}: {msg}") from exc
        except urllib.error.URLError as exc:
            raise SDKError(f"cannot reach {url}: {exc}") from exc

    # -- API methods -------------------------------------------------------
    def info(self) -> dict:
        return self._request("GET", "/v1/info")

    def analyze(self, words, genre="real_life_storytelling") -> dict:
        return self._request("POST", "/v1/analyze", {"words": words, "genre": genre})

    def plan(self, words, genre="real_life_storytelling", title="untitled") -> dict:
        return self._request("POST", "/v1/plan", {"words": words, "genre": genre, "title": title})

    def styles(self) -> list:
        return self._request("POST", "/v1/styles", {})["styles"]

    def select_style(self, name: str) -> dict:
        return self._request("POST", "/v1/select_style", {"name": name})

    def generate_timeline(self, words, style, **kw) -> dict:
        return self._request("POST", "/v1/generate_timeline", {"words": words, "style": style, **kw})

    def retrieve(self, folder, query, count=5, require_licence=False) -> list:
        return self._request("POST", "/v1/retrieve", {"folder": folder, "query": query,
                                                      "count": count, "require_licence": require_licence})["hits"]

    def render_chart(self, spec, out, fps=30) -> str:
        return self._request("POST", "/v1/render_chart", {"spec": spec, "out": out, "fps": fps})["job_id"]

    def captions(self, words, style, out_dir, frame_w=1080, frame_h=1920) -> dict:
        return self._request("POST", "/v1/captions", {"words": words, "style": style,
                                                      "out_dir": out_dir, "frame_w": frame_w, "frame_h": frame_h})

    def qa(self, edit_plan) -> dict:
        return self._request("POST", "/v1/qa", {"edit_plan": edit_plan})

    def job(self, job_id: str) -> dict:
        return self._request("GET", f"/v1/jobs/{job_id}")

    def cancel(self, job_id: str) -> dict:
        return self._request("POST", f"/v1/jobs/{job_id}/cancel")

    def retry(self, job_id: str) -> str:
        return self._request("POST", f"/v1/jobs/{job_id}/retry")["job_id"]

    def wait_for_job(self, job_id: str, timeout: float = 120.0, poll: float = 0.1) -> dict:
        deadline = time.time() + timeout
        while time.time() < deadline:
            st = self.job(job_id)
            if st["status"] in {"succeeded", "failed", "cancelled"}:
                return st
            time.sleep(poll)
        raise SDKError(f"job {job_id} did not finish within {timeout}s")
