"""Local API over the Universal Video Skills capabilities (Phase 12).

UVSApi exposes project creation, script analysis, narrative planning, media indexing and retrieval,
style selection, timeline generation (via the decision engine), chart/map/caption rendering and QA.
Everything runs locally. All file paths are confined to a workspace root (ProjectRoot refuses
absolute paths, parent traversal and symlink escape), and nothing shells out on a user-supplied
string, so there is no command-injection surface here.

Long operations (rendering) run through the JobManager and return a job id; quick operations
(analysis, planning, retrieval, decisions) return results directly.
"""
from __future__ import annotations

import json
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from uvs.assets import ProjectRoot
from uvs.jobs import JobManager, JobHandle
from uvs import narrative as N
from uvs import director as D
from uvs import media_index as M
from uvs import retrieval as R
from uvs.captions import Word, build_captions, write_outputs
from uvs.styles import STYLES, STYLE_NAMES, StyleLock
from uvs.decision import EditContext, Capabilities, decide
from uvs.infographics import ChartSpec, Series, chart_video

API_VERSION = "1.0.0"


class ApiError(ValueError):
    pass


def _words(items: list[dict]) -> list[Word]:
    try:
        return [Word(text=str(w["text"]), start=float(w["start"]), end=float(w["end"])) for w in items]
    except (KeyError, TypeError, ValueError) as exc:
        raise ApiError(f"bad words: {exc}") from exc


@dataclass
class UVSApi:
    workspace: str                       # root folder; all file paths resolve under it
    jobs: JobManager = None              # type: ignore[assignment]

    def __post_init__(self):
        self.root = ProjectRoot(self.workspace)
        if self.jobs is None:
            self.jobs = JobManager()

    # -- path safety -------------------------------------------------------
    def _resolve(self, rel: str) -> Path:
        """Resolve a workspace-relative path safely. Rejects traversal and absolute paths."""
        return self.root.resolve(rel)

    # -- metadata ----------------------------------------------------------
    def info(self) -> dict:
        return {"api_version": API_VERSION, "workspace": str(self.root.path),
                "styles": list(STYLE_NAMES), "genres": sorted(D.GENRES),
                "capabilities": ["analyze", "plan", "index_media", "retrieve", "select_style",
                                 "generate_timeline", "render_chart", "captions", "qa"]}

    # -- project -----------------------------------------------------------
    def create_project(self, name: str) -> dict:
        if not name or "/" in name or "\\" in name or name.startswith("."):
            raise ApiError("project name must be a simple folder name")
        folder = self._resolve(name)
        folder.mkdir(parents=True, exist_ok=True)
        return {"project": name, "path": str(folder)}

    # -- analysis / planning ----------------------------------------------
    def analyze_script(self, words: list[dict], genre: str = "real_life_storytelling") -> dict:
        plan = N.build(_words(words), genre)
        return plan["analysis"]

    def plan_narrative(self, words: list[dict], genre: str = "real_life_storytelling",
                       title: str = "untitled") -> dict:
        return N.build(_words(words), genre, title=title)

    # -- media -------------------------------------------------------------
    def index_media(self, folder: str, cache: str | None = None) -> list[dict]:
        root = self._resolve(folder)
        cache_dir = self._resolve(cache) if cache else None
        return [dict(path=a.path, kind=a.kind, tags=a.tags, license=a.provenance.get("license"),
                     motion=a.motion_per_second) for a in M.scan(root, cache_dir)]

    def retrieve_media(self, folder: str, query: str, count: int = 5,
                       require_licence: bool = False) -> list[dict]:
        assets = M.scan(self._resolve(folder))
        return [h.to_dict() for h in R.search(assets, query, count=count,
                                              require_known_licence=require_licence)]

    # -- style -------------------------------------------------------------
    def list_styles(self) -> list[dict]:
        return [STYLES[n].to_dict() for n in STYLE_NAMES]

    def select_style(self, name: str) -> dict:
        return StyleLock.resolve(name).style.to_dict()

    # -- timeline (decision engine) ---------------------------------------
    def generate_timeline(self, words: list[dict], style: str, genre: str = "real_life_storytelling",
                          fps: int = 30, width: int = 1080, height: int = 1920,
                          capabilities: dict | None = None, overrides: dict | None = None) -> dict:
        plan = N.build(_words(words), genre)
        caps = Capabilities(**capabilities) if capabilities else Capabilities()
        ctx = EditContext(plan=plan, style=StyleLock.resolve(style), fps=fps, width=width,
                          height=height, capabilities=caps)
        ep = decide(ctx, overrides=overrides)
        return ep.to_dict()

    # -- rendering (jobs) --------------------------------------------------
    def render_chart(self, spec: dict, out: str, fps: float = 30.0) -> str:
        """Submit a chart render job. Returns a job id."""
        out_path = self._resolve(out)
        series = tuple(Series(label=s["label"], values=tuple(s["values"])) for s in spec["series"])
        chart = ChartSpec(kind=spec["kind"], categories=tuple(spec.get("categories", [])),
                          series=series, title=spec.get("title", ""), unit=spec.get("unit", ""),
                          source=spec.get("source", "api"), theme=spec.get("theme", "dark"),
                          width=int(spec.get("width", 1080)), height=int(spec.get("height", 1350)),
                          duration=float(spec.get("duration", 3.0)))

        def worker(h: JobHandle) -> dict:
            h.progress(0.1, "validating")
            h.check_cancelled()
            h.progress(0.3, "rendering")
            info = chart_video(chart, out_path, fps=fps)
            h.progress(1.0, "done")
            return {"outputs": [str(out_path)], "info": info}

        return self.jobs.submit("render_chart", worker)

    def render_captions(self, words: list[dict], style: str, out_dir: str,
                        frame_w: int = 1080, frame_h: int = 1920) -> dict:
        build = build_captions(_words(words), style, frame_w, frame_h)
        if build.errors:
            raise ApiError("; ".join(f"[{i.code}] {i.message}" for i in build.errors))
        files = write_outputs(build, self._resolve(out_dir), "captions")
        return {"cues": len(build.cues), "outputs": files}

    # -- QA ----------------------------------------------------------------
    def qa_timeline(self, edit_plan: dict) -> dict:
        issues = []
        instr = edit_plan.get("instructions", [])
        for i in range(1, len(instr)):
            prev, cur = instr[i - 1], instr[i]
            if cur["start_frame"] != prev["start_frame"] + prev["duration_frames"]:
                issues.append({"code": "gap", "scene": cur["scene_id"]})
        return {"scenes": len(instr), "issues": issues, "ok": not issues}

    # -- job passthrough ---------------------------------------------------
    def job_status(self, job_id: str) -> dict:
        return self.jobs.status(job_id)

    def cancel_job(self, job_id: str) -> dict:
        return self.jobs.cancel(job_id)

    def retry_job(self, job_id: str) -> str:
        return self.jobs.retry(job_id)
