"""Media asset management (Phase 1.5).

- Asset identity: a short id derived from the content checksum.
- Portable paths: assets are stored relative to the project folder, with forward slashes.
- Path safety: absolute paths, '..' segments, and symlinks that point outside the project are refused.
- Checksums: SHA-256, streamed so large files are not loaded whole.
- Missing and changed media: detected by comparing the file against its recorded checksum.
- Dependency tracking: which assets each clip uses, and which assets nothing uses.
- Cache: a content-addressed folder with a size limit, pruned least-recently-used first.

User media is never moved, renamed, or deleted by this module. The cache only holds files it created.
"""
from __future__ import annotations

import hashlib
import json
import shutil
from dataclasses import dataclass
from pathlib import Path

KIND_BY_EXTENSION = {
    ".mp4": "video", ".mov": "video", ".mkv": "video", ".webm": "video",
    ".jpg": "image", ".jpeg": "image", ".png": "image", ".webp": "image",
    ".wav": "audio", ".mp3": "audio", ".m4a": "audio", ".aac": "audio",
}


class AssetError(ValueError):
    """A path or asset is unsafe or unusable."""


@dataclass(frozen=True)
class ProjectRoot:
    path: Path

    def __post_init__(self):
        object.__setattr__(self, "path", Path(self.path).resolve())

    def resolve(self, relpath: str) -> Path:
        """Turn a stored project path into an absolute path, refusing anything that escapes the root."""
        if not relpath or "\x00" in relpath:
            raise AssetError("asset path is empty or contains a NUL byte")
        p = Path(relpath)
        if p.is_absolute() or p.drive or relpath.startswith("/"):
            raise AssetError(f"absolute path {relpath!r} is not portable; store it relative to the project folder")
        if ".." in p.parts:
            raise AssetError(f"path {relpath!r} contains '..'")
        full = (self.path / p).resolve()
        if not full.is_relative_to(self.path):
            raise AssetError(f"path {relpath!r} resolves outside the project folder (symlink?)")
        return full

    def relpath(self, absolute: Path) -> str:
        """Portable (forward-slash) path of a file inside the root."""
        target = Path(absolute).resolve()
        if not target.is_relative_to(self.path):
            raise AssetError(f"{absolute} is outside the project folder; copy it in before registering")
        return target.relative_to(self.path).as_posix()


def sha256_file(path: Path, chunk: int = 1 << 20) -> str:
    h = hashlib.sha256()
    with open(path, "rb") as fh:
        for block in iter(lambda: fh.read(chunk), b""):
            h.update(block)
    return h.hexdigest()


def kind_of(path: Path) -> str:
    return KIND_BY_EXTENSION.get(Path(path).suffix.lower(), "unknown")


def register(root: ProjectRoot, path: Path) -> dict:
    """Describe a media file inside the project as an asset record (matches the project schema)."""
    p = Path(path)
    if not p.is_file():
        raise AssetError(f"media file not found: {path}")
    digest = sha256_file(p)
    return {
        "id": "a" + digest[:10],
        "path": root.relpath(p),
        "sha256": digest,
        "kind": kind_of(p),
        "portable": True,
    }


def check(root: ProjectRoot, assets: list[dict]) -> list[dict]:
    """Report each asset as ok, missing, changed (checksum differs), or unsafe (bad path)."""
    report = []
    for a in assets:
        entry = {"id": a["id"], "path": a["path"], "status": "ok"}
        try:
            full = root.resolve(a["path"]) if a.get("portable", True) else Path(a["path"])
        except AssetError as exc:
            entry.update(status="unsafe", detail=str(exc))
            report.append(entry)
            continue
        if not full.is_file():
            entry.update(status="missing", detail="file not found")
        elif a.get("sha256") and sha256_file(full) != a["sha256"]:
            entry.update(status="changed", detail="checksum differs from the recorded value")
        report.append(entry)
    return report


def usage(doc: dict) -> dict[str, list[str]]:
    """Map asset id -> clip ids that use it, across all tracks of a project document."""
    out: dict[str, list[str]] = {a["id"]: [] for a in doc.get("assets", [])}
    for clips in doc.get("tracks", {}).values():
        for c in clips:
            out.setdefault(c["asset_id"], []).append(c["id"])
    return out


def unused(doc: dict) -> list[str]:
    return sorted(aid for aid, clips in usage(doc).items() if not clips)


class Cache:
    """Content-addressed cache folder with a byte limit. Only files it writes are pruned."""

    def __init__(self, folder: Path, max_bytes: int = 2 * 1024**3):
        self.folder = Path(folder)
        self.max_bytes = max_bytes
        self.folder.mkdir(parents=True, exist_ok=True)

    @staticmethod
    def key(*parts) -> str:
        blob = json.dumps(parts, sort_keys=True, default=str).encode("utf-8")
        return hashlib.sha256(blob).hexdigest()

    def path_for(self, key: str, suffix: str) -> Path:
        if not key.isalnum() or not suffix.startswith("."):
            raise AssetError("cache keys are hex digests and suffixes start with '.'")
        return self.folder / (key + suffix)

    def has(self, key: str, suffix: str) -> bool:
        return self.path_for(key, suffix).is_file()

    def put(self, key: str, src: Path, suffix: str) -> Path:
        dst = self.path_for(key, suffix)
        shutil.copy2(src, dst)
        return dst

    def get(self, key: str, suffix: str) -> Path | None:
        p = self.path_for(key, suffix)
        if not p.is_file():
            return None
        p.touch()  # mark as recently used
        return p

    def size_bytes(self) -> int:
        return sum(p.stat().st_size for p in self.folder.iterdir() if p.is_file())

    def prune(self) -> list[str]:
        """Remove least-recently-used files until the folder is within max_bytes."""
        files = sorted((p for p in self.folder.iterdir() if p.is_file()), key=lambda p: p.stat().st_mtime)
        total = sum(p.stat().st_size for p in files)
        removed = []
        for p in files:
            if total <= self.max_bytes:
                break
            total -= p.stat().st_size
            p.unlink()
            removed.append(p.name)
        return removed
