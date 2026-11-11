"""Localhost JSON API server for the local editor SDK (Phase 12).

A small stdlib HTTP server that exposes UVSApi over versioned JSON routes under /v1/. It binds to
127.0.0.1 by default (never 0.0.0.0), enforces a request-body size limit, and returns structured
JSON errors. It does not serve files from disk or shell out, so there is no path-traversal or
command-injection surface in the transport. This is a reference adapter for a local web editor —
not an integration with any specific editor.

Routes (all POST with a JSON body, except GET /v1/info and GET /v1/jobs/<id>):
  GET  /v1/info
  POST /v1/analyze            {words, genre}
  POST /v1/plan               {words, genre, title}
  POST /v1/styles             {}
  POST /v1/select_style       {name}
  POST /v1/generate_timeline  {words, style, genre, fps, width, height, capabilities, overrides}
  POST /v1/retrieve           {folder, query, count, require_licence}
  POST /v1/render_chart       {spec, out, fps}        -> {job_id}
  POST /v1/captions           {words, style, out_dir, frame_w, frame_h}
  POST /v1/qa                 {edit_plan}
  GET  /v1/jobs/<id>
  POST /v1/jobs/<id>/cancel
  POST /v1/jobs/<id>/retry
"""
from __future__ import annotations

import json
import threading
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path

from uvs.api import UVSApi, ApiError

MAX_BODY = 4 * 1024 * 1024   # 4 MiB request cap


class _Handler(BaseHTTPRequestHandler):
    api: UVSApi = None       # set by make_server
    server_version = "UVS/1.0"

    def log_message(self, *args):   # silence default logging
        pass

    def _send(self, code: int, payload: dict) -> None:
        body = json.dumps(payload).encode("utf-8")
        self.send_response(code)
        self.send_header("Content-Type", "application/json")
        self.send_header("Content-Length", str(len(body)))
        self.end_headers()
        self.wfile.write(body)

    def _body(self) -> dict:
        length = int(self.headers.get("Content-Length", 0))
        if length > MAX_BODY:
            raise ApiError("request body too large")
        if length == 0:
            return {}
        raw = self.rfile.read(length)
        try:
            data = json.loads(raw)
        except ValueError as exc:
            raise ApiError(f"invalid JSON: {exc}") from exc
        if not isinstance(data, dict):
            raise ApiError("request body must be a JSON object")
        return data

    def do_GET(self):
        try:
            parts = self.path.strip("/").split("/")
            if self.path == "/v1/info":
                return self._send(200, self.api.info())
            if len(parts) == 3 and parts[:2] == ["v1", "jobs"]:
                return self._send(200, self.api.job_status(parts[2]))
            self._send(404, {"error": "not found"})
        except KeyError as exc:
            self._send(404, {"error": f"unknown id {exc}"})
        except Exception as exc:  # noqa: BLE001
            self._send(400, {"error": str(exc)})

    def do_POST(self):
        try:
            parts = self.path.strip("/").split("/")
            data = self._body()
            if self.path == "/v1/analyze":
                return self._send(200, self.api.analyze_script(data["words"], data.get("genre", "real_life_storytelling")))
            if self.path == "/v1/plan":
                return self._send(200, self.api.plan_narrative(data["words"], data.get("genre", "real_life_storytelling"), data.get("title", "untitled")))
            if self.path == "/v1/styles":
                return self._send(200, {"styles": self.api.list_styles()})
            if self.path == "/v1/select_style":
                return self._send(200, self.api.select_style(data["name"]))
            if self.path == "/v1/generate_timeline":
                return self._send(200, self.api.generate_timeline(
                    data["words"], data["style"], data.get("genre", "real_life_storytelling"),
                    int(data.get("fps", 30)), int(data.get("width", 1080)), int(data.get("height", 1920)),
                    data.get("capabilities"), data.get("overrides")))
            if self.path == "/v1/retrieve":
                return self._send(200, {"hits": self.api.retrieve_media(
                    data["folder"], data["query"], int(data.get("count", 5)), bool(data.get("require_licence", False)))})
            if self.path == "/v1/render_chart":
                return self._send(202, {"job_id": self.api.render_chart(data["spec"], data["out"], float(data.get("fps", 30)))})
            if self.path == "/v1/captions":
                return self._send(200, self.api.render_captions(
                    data["words"], data["style"], data["out_dir"],
                    int(data.get("frame_w", 1080)), int(data.get("frame_h", 1920))))
            if self.path == "/v1/qa":
                return self._send(200, self.api.qa_timeline(data["edit_plan"]))
            if len(parts) == 4 and parts[:2] == ["v1", "jobs"] and parts[3] == "cancel":
                return self._send(200, self.api.cancel_job(parts[2]))
            if len(parts) == 4 and parts[:2] == ["v1", "jobs"] and parts[3] == "retry":
                return self._send(202, {"job_id": self.api.retry_job(parts[2])})
            self._send(404, {"error": "not found"})
        except KeyError as exc:
            self._send(400, {"error": f"missing field {exc}"})
        except (ApiError, ValueError) as exc:
            self._send(400, {"error": str(exc)})
        except Exception as exc:  # noqa: BLE001
            self._send(500, {"error": f"{type(exc).__name__}: {exc}"})


def make_server(api: UVSApi, host: str = "127.0.0.1", port: int = 0) -> ThreadingHTTPServer:
    """Create a localhost-bound server. host must be a loopback address."""
    if host not in {"127.0.0.1", "localhost", "::1"}:
        raise ValueError("server binds to loopback only; refusing a non-local host")
    handler = type("BoundHandler", (_Handler,), {"api": api})
    return ThreadingHTTPServer((host, port), handler)


def serve(workspace: str, host: str = "127.0.0.1", port: int = 8721) -> None:
    api = UVSApi(workspace)
    httpd = make_server(api, host, port)
    print(f"UVS API on http://{host}:{httpd.server_address[1]}/v1  (workspace: {workspace})")
    try:
        httpd.serve_forever()
    except KeyboardInterrupt:
        httpd.shutdown()


if __name__ == "__main__":
    import argparse
    ap = argparse.ArgumentParser(description="Local UVS JSON API (loopback only).")
    ap.add_argument("workspace")
    ap.add_argument("--host", default="127.0.0.1")
    ap.add_argument("--port", type=int, default=8721)
    args = ap.parse_args()
    serve(args.workspace, args.host, args.port)
