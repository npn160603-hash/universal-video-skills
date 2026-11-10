"""Versioned project documents (Phase 1.1).

A project file has `"format": "uvs-project"` and an integer `schema_version`. Files written before
versioning existed (the timeline JSON written by `uvs.timeline.save_timeline`) are migrated on load.

Validation has two layers:
1. Structure: `schemas/uvs_project.schema.json`, checked with jsonschema. Every problem is reported
   with a path and a hint.
2. Semantics: references between assets and clips, unique ids, scene ordering, keyframe ordering,
   and that the aspect ratio matches the pixel size.

Loading never silently drops data. Anything a migration cannot carry over is recorded in
`quality.migration_notes`.
"""
from __future__ import annotations

import hashlib
import json
from dataclasses import dataclass
from fractions import Fraction
from pathlib import Path

from jsonschema import Draft202012Validator

CURRENT_VERSION = 1
FORMAT = "uvs-project"
SCHEMA_PATH = Path(__file__).resolve().parent.parent / "schemas" / "uvs_project.schema.json"
_TRACK_MAP = {"video": "video", "audio": "audio", "overlay": "graphics"}


class ProjectError(ValueError):
    """Raised when a project cannot be loaded or is invalid. `issues` lists every problem."""

    def __init__(self, issues: list["Issue"]):
        self.issues = issues
        super().__init__("; ".join(f"{i.path}: {i.message}" for i in issues))


@dataclass(frozen=True)
class Issue:
    path: str
    message: str
    hint: str = ""


def _asset_id(source: str) -> str:
    return "a" + hashlib.sha256(source.encode("utf-8")).hexdigest()[:10]


def new_project(project_id: str, title: str, width: int, height: int, fps: str = "30") -> dict:
    """Return an empty, valid version-1 project document."""
    return {
        "format": FORMAT,
        "schema_version": CURRENT_VERSION,
        "project": {"id": project_id, "title": title},
        "format_settings": {"width": width, "height": height, "fps": fps,
                            "aspect_ratio": aspect_ratio_text(width, height)},
        "assets": [],
        "tracks": {"video": [], "audio": [], "graphics": []},
    }


def aspect_ratio_text(width: int, height: int) -> str:
    r = Fraction(width, height)
    return f"{r.numerator}:{r.denominator}"


# ---------------------------------------------------------------------------
# Migrations
# ---------------------------------------------------------------------------

def _v0_to_v1(doc: dict) -> dict:
    """Timeline JSON (no `format` key) -> version 1 project."""
    notes: list[str] = []
    fps = str(doc.get("fps", "30"))
    width, height = int(doc["width"]), int(doc["height"])
    out = new_project("migrated", "Migrated timeline", width, height, fps)
    assets: dict[str, dict] = {}
    tracks = {"video": [], "audio": [], "graphics": []}
    for track in doc.get("tracks", []):
        kind = track.get("kind", "")
        target = _TRACK_MAP.get(kind)
        if target is None:
            notes.append(f"track {track.get('name', kind)!r} of kind {kind!r} was not carried over (no v1 equivalent)")
            continue
        for c in track.get("clips", []):
            source = str(c.get("source", ""))
            aid = _asset_id(source)
            is_image = bool(c.get("is_image", False))
            if aid not in assets:
                assets[aid] = {
                    "id": aid,
                    "path": source,
                    "sha256": "",
                    "kind": "image" if is_image else ("audio" if target == "audio" else "video"),
                    "portable": not Path(source).is_absolute(),
                }
                if assets[aid]["portable"] is False:
                    notes.append(f"asset {aid} uses an absolute path; it is not portable until relinked")
            tracks[target].append({
                "id": str(c.get("id", f"{target}{len(tracks[target]) + 1}")),
                "asset_id": aid,
                "start_frame": int(c.get("start", 0)),
                "duration_frames": int(c.get("duration", 1)),
                "in_frame": int(c.get("in_point", 0)),
                "transition": c.get("transition", "cut"),
                "transition_frames": int(c.get("transition_frames", 0)),
                "gain_db": float(c.get("gain_db", 0.0)),
                "x": int(c.get("x", 0)),
                "y": int(c.get("y", 0)),
            })
    out["assets"] = list(assets.values())
    out["tracks"] = tracks
    out["quality"] = {"migration_notes": notes, "migrated_from": 0}
    return out


MIGRATIONS = {0: _v0_to_v1}


def migrate(doc: dict) -> dict:
    """Bring a document up to CURRENT_VERSION, one step at a time."""
    if doc.get("format") == FORMAT:
        version = doc.get("schema_version")
        if not isinstance(version, int):
            raise ProjectError([Issue("schema_version", "missing or not an integer",
                                      f"set schema_version to {CURRENT_VERSION}")])
    else:
        if not {"fps", "width", "height", "tracks"} <= doc.keys():
            raise ProjectError([Issue("(root)", "not a UVS project and not a recognised timeline file",
                                      "expected a uvs-project document or a timeline written by uvs.timeline")])
        version = 0
    if version > CURRENT_VERSION:
        raise ProjectError([Issue("schema_version",
                                  f"written by a newer version (v{version}); this build reads up to v{CURRENT_VERSION}",
                                  "upgrade universal-video-skills to open this project")])
    while version < CURRENT_VERSION:
        doc = MIGRATIONS[version](doc)
        version += 1
    return doc


# ---------------------------------------------------------------------------
# Validation
# ---------------------------------------------------------------------------

_HINTS = {
    "required": "add the missing field",
    "additionalProperties": "remove or rename the unknown field",
    "enum": "use one of the allowed values",
    "pattern": "match the expected format",
    "minimum": "use a larger value",
    "maximum": "use a smaller value",
    "type": "use the expected type",
    "const": "set it to the expected constant",
    "minItems": "provide at least one item",
}


def _schema_issues(doc: dict) -> list[Issue]:
    validator = Draft202012Validator(json.loads(SCHEMA_PATH.read_text(encoding="utf-8")))
    issues = []
    for err in sorted(validator.iter_errors(doc), key=lambda e: list(e.absolute_path)):
        path = "/".join(str(p) for p in err.absolute_path) or "(root)"
        issues.append(Issue(path, err.message, _HINTS.get(err.validator, "")))
    return issues


def validate(doc: dict) -> list[Issue]:
    """All problems with a version-1 document. Empty list means the document is usable."""
    issues = _schema_issues(doc)
    if issues:
        return issues  # semantic checks assume the structure is sound

    fs = doc["format_settings"]
    expected = aspect_ratio_text(fs["width"], fs["height"])
    if fs["aspect_ratio"] != expected:
        issues.append(Issue("format_settings/aspect_ratio",
                            f"{fs['aspect_ratio']} does not match {fs['width']}x{fs['height']} ({expected})",
                            f"set aspect_ratio to {expected}"))

    asset_ids: set[str] = set()
    for i, a in enumerate(doc["assets"]):
        if a["id"] in asset_ids:
            issues.append(Issue(f"assets/{i}/id", f"duplicate asset id {a['id']!r}", "give each asset a unique id"))
        asset_ids.add(a["id"])
        if a["portable"] and ".." in Path(a["path"]).parts:
            issues.append(Issue(f"assets/{i}/path", "portable path contains '..' and may escape the project folder",
                                "store a path inside the project folder, or mark the asset non-portable"))

    clip_ids: set[str] = set()
    for track_name, clips in doc["tracks"].items():
        for i, c in enumerate(clips):
            where = f"tracks/{track_name}/{i}"
            if c["id"] in clip_ids:
                issues.append(Issue(f"{where}/id", f"duplicate clip id {c['id']!r}", "give each clip a unique id"))
            clip_ids.add(c["id"])
            if c["asset_id"] not in asset_ids:
                issues.append(Issue(f"{where}/asset_id", f"unknown asset {c['asset_id']!r}",
                                    "add the asset to assets or fix the reference"))

    scenes = doc.get("scenes", [])
    for i, s in enumerate(scenes):
        if s["end_frame"] <= s["start_frame"]:
            issues.append(Issue(f"scenes/{i}", f"scene {s['id']!r} ends before it starts", "set end_frame after start_frame"))
        if i and s["start_frame"] < scenes[i - 1]["end_frame"]:
            issues.append(Issue(f"scenes/{i}", f"scene {s['id']!r} overlaps the previous scene",
                                "scenes must be ordered and non-overlapping"))

    for i, k in enumerate(doc.get("keyframes", [])):
        frames = [key["frame"] for key in k["keys"]]
        if frames != sorted(set(frames)):
            issues.append(Issue(f"keyframes/{i}/keys", "keys must have strictly increasing frames",
                                "sort the keys and remove duplicate frames"))
    return issues


def load(path: str | Path) -> dict:
    """Read, migrate, and validate a project file. Raises ProjectError with every problem."""
    p = Path(path)
    try:
        raw = json.loads(p.read_text(encoding="utf-8"))
    except json.JSONDecodeError as exc:
        raise ProjectError([Issue("(file)", f"not valid JSON: {exc.msg} at line {exc.lineno}",
                                  "fix the JSON syntax")]) from exc
    doc = migrate(raw)
    problems = validate(doc)
    if problems:
        raise ProjectError(problems)
    return doc


def save(doc: dict, path: str | Path) -> Path:
    """Write a project deterministically (sorted keys, stable formatting)."""
    problems = validate(doc)
    if problems:
        raise ProjectError(problems)
    p = Path(path)
    p.parent.mkdir(parents=True, exist_ok=True)
    p.write_text(json.dumps(doc, ensure_ascii=False, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    return p
