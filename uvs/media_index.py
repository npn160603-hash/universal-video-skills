"""Local media index (semantic-media-selection, Phase 3).

Indexes images, videos, and audio in a folder: dimensions, orientation, duration, fps, audio
presence, sharpness, dominant colours, perceptual hashes for duplicate detection, and motion
for video (scene changes per second, from ffmpeg's scene score).

Provenance and descriptive text come from an optional sidecar file named <asset>.json, for
example {"source": "...", "license": "...", "tags": ["city", "night"], "description": "..."}.
Missing provenance is reported as "unknown". Metrics are cached by content hash, so re-scanning
an unchanged file does not re-run ffprobe, ffmpeg or the image analysis; sidecar text is always
re-read.

Ranking scores orientation, resolution, sharpness, duration fit and licence status, then picks a
diverse set that skips near-duplicates. Text search (retrieval.py) is lexical, not semantic:
it matches words in tags, descriptions and file names, with a small hand-written synonym list.
There are no embeddings.
"""
from __future__ import annotations

import hashlib
import json
import math
import re
import subprocess
from dataclasses import asdict, dataclass, field
from fractions import Fraction
from pathlib import Path

from PIL import Image, ImageFilter

IMAGE_EXT = {".png", ".jpg", ".jpeg", ".webp", ".bmp"}
VIDEO_EXT = {".mp4", ".mov", ".mkv", ".webm"}
AUDIO_EXT = {".wav", ".mp3", ".m4a", ".aac", ".flac"}
INDEX_VERSION = 2          # bump when the metric fields change; stale cache entries are ignored
SCENE_THRESHOLD = 0.3      # ffmpeg scene score above which a frame counts as a cut
MAX_TAGS = 50
MAX_DESCRIPTION = 500
# Metric fields stored in the cache. Provenance, tags and description are never cached.
_METRIC_FIELDS = ("width", "height", "orientation", "duration", "fps", "has_audio", "sharpness",
                  "brightness", "dominant_colors", "dhash", "motion_per_second", "notes")


@dataclass
class Asset:
    path: str
    kind: str                       # image | video | audio
    sha256: str
    width: int | None = None
    height: int | None = None
    orientation: str | None = None  # portrait | landscape | square
    duration: float | None = None
    fps: float | None = None
    has_audio: bool | None = None
    sharpness: float | None = None  # variance of edge response, images only
    brightness: float | None = None # mean luma 0-255, images only
    dominant_colors: list[str] = field(default_factory=list)
    dhash: str | None = None
    motion_per_second: float | None = None  # scene cuts per second, video only
    tags: list[str] = field(default_factory=list)
    description: str = ""
    provenance: dict = field(default_factory=lambda: {"source": "unknown", "license": "unknown"})
    notes: list[str] = field(default_factory=list)


def _orientation(w: int, h: int) -> str:
    if w == h:
        return "square"
    return "portrait" if h > w else "landscape"


def _sha256(path: Path) -> str:
    h = hashlib.sha256()
    with path.open("rb") as f:
        for chunk in iter(lambda: f.read(1 << 20), b""):
            h.update(chunk)
    return h.hexdigest()


def dhash(img: Image.Image, size: int = 8) -> str:
    """Difference hash: 64 bits from horizontal gradients of a grayscale thumbnail."""
    g = img.convert("L").resize((size + 1, size), Image.Resampling.LANCZOS)
    px = list(g.tobytes())
    bits = []
    for y in range(size):
        for x in range(size):
            bits.append("1" if px[y * (size + 1) + x] > px[y * (size + 1) + x + 1] else "0")
    return f"{int(''.join(bits), 2):016x}"


def hamming(a: str, b: str) -> int:
    return bin(int(a, 16) ^ int(b, 16)).count("1")


def _image_metrics(path: Path, asset: Asset) -> None:
    with Image.open(path) as im:
        im = im.convert("RGB")
        asset.width, asset.height = im.size
        asset.orientation = _orientation(*im.size)
        small = im.copy()
        small.thumbnail((256, 256))
        gray = small.convert("L")
        hist = gray.histogram()
        total = sum(hist)
        asset.brightness = round(sum(i * n for i, n in enumerate(hist)) / total, 2)
        edges = gray.filter(ImageFilter.FIND_EDGES)
        vals = list(edges.tobytes())
        mean = sum(vals) / len(vals)
        asset.sharpness = round(sum((v - mean) ** 2 for v in vals) / len(vals), 2)
        quant = small.quantize(colors=4, method=Image.Quantize.MEDIANCUT)
        palette = quant.getpalette()[:12]
        counts = sorted(quant.getcolors(), reverse=True)
        colors = []
        for _, idx in counts[:4]:
            r, g, b = palette[idx * 3: idx * 3 + 3]
            colors.append(f"#{r:02x}{g:02x}{b:02x}")
        asset.dominant_colors = colors
        asset.dhash = dhash(im)


def _probe(path: Path) -> dict:
    proc = subprocess.run(["ffprobe", "-v", "error", "-print_format", "json",
                           "-show_format", "-show_streams", str(path)], capture_output=True, text=True)
    if proc.returncode != 0:
        raise RuntimeError(f"ffprobe failed for {path}: {proc.stderr.strip()[-200:]}")
    return json.loads(proc.stdout)


def _media_metrics(path: Path, asset: Asset) -> None:
    info = _probe(path)
    streams = info.get("streams", [])
    v = next((s for s in streams if s.get("codec_type") == "video"), None)
    a = next((s for s in streams if s.get("codec_type") == "audio"), None)
    asset.duration = round(float(info.get("format", {}).get("duration", 0) or 0), 3)
    asset.has_audio = a is not None
    if v is not None:
        asset.width, asset.height = int(v["width"]), int(v["height"])
        asset.orientation = _orientation(asset.width, asset.height)
        rate = v.get("avg_frame_rate") or v.get("r_frame_rate")
        if rate and rate != "0/0":
            asset.fps = round(float(Fraction(rate)), 3)
    if asset.kind == "video" and asset.width is None:
        asset.notes.append("video without a video stream")


def _clean_tags(raw) -> list[str]:
    if isinstance(raw, str):
        raw = re.split(r"[,;]", raw)
    if not isinstance(raw, list):
        return []
    out: list[str] = []
    for t in raw:
        if isinstance(t, str) and t.strip():
            tag = " ".join(t.lower().split())[:60]
            if tag not in out:
                out.append(tag)
    return out[:MAX_TAGS]


def _provenance(path: Path, asset: Asset) -> None:
    side = path.with_suffix(path.suffix + ".json")
    if side.exists():
        try:
            data = json.loads(side.read_text(encoding="utf-8"))
            if not isinstance(data, dict):
                raise ValueError("sidecar must be a JSON object")
            asset.provenance = {"source": str(data.get("source", "unknown")),
                                "license": str(data.get("license", "unknown"))}
            asset.tags = _clean_tags(data.get("tags", []))
            asset.description = str(data.get("description", ""))[:MAX_DESCRIPTION]
        except (ValueError, OSError):
            asset.notes.append("provenance sidecar is unreadable")
    else:
        asset.notes.append("no provenance sidecar")


def _motion(path: Path, asset: Asset) -> None:
    """Scene cuts per second for video, from ffmpeg's scene score. The first frame is never a cut."""
    if asset.kind != "video" or not asset.duration:
        return
    proc = subprocess.run(
        ["ffmpeg", "-hide_banner", "-nostats", "-i", str(path),
         "-filter:v", f"select='gt(scene,{SCENE_THRESHOLD})',showinfo", "-an", "-f", "null", "-"],
        capture_output=True, text=True)
    if proc.returncode != 0:
        asset.notes.append("motion analysis failed")
        return
    cuts = sum(1 for line in proc.stderr.splitlines() if "Parsed_showinfo" in line and "pts_time:" in line)
    asset.motion_per_second = round(cuts / asset.duration, 3)


def _cache_path(cache_dir: Path, sha: str) -> Path:
    return cache_dir / f"{sha}.v{INDEX_VERSION}.json"


def _apply_metrics(asset: Asset, metrics: dict) -> None:
    for name in _METRIC_FIELDS:
        if name in metrics:
            setattr(asset, name, metrics[name])


def index_file(path: str | Path, cache_dir: str | Path | None = None) -> Asset | None:
    p = Path(path)
    ext = p.suffix.lower()
    if ext in IMAGE_EXT:
        kind = "image"
    elif ext in VIDEO_EXT:
        kind = "video"
    elif ext in AUDIO_EXT:
        kind = "audio"
    else:
        return None
    asset = Asset(path=str(p), kind=kind, sha256=_sha256(p))
    cached = None
    cache_file = _cache_path(Path(cache_dir), asset.sha256) if cache_dir else None
    if cache_file is not None and cache_file.exists():
        try:
            cached = json.loads(cache_file.read_text(encoding="utf-8"))
            if cached.get("kind") != kind:
                cached = None
        except (ValueError, OSError):
            cached = None
    if cached is not None:
        _apply_metrics(asset, cached["metrics"])
    else:
        if kind == "image":
            _image_metrics(p, asset)
        else:
            _media_metrics(p, asset)
            _motion(p, asset)
        if cache_file is not None:
            cache_file.parent.mkdir(parents=True, exist_ok=True)
            metrics = {name: getattr(asset, name) for name in _METRIC_FIELDS}
            cache_file.write_text(json.dumps({"kind": kind, "metrics": metrics}, ensure_ascii=False),
                                  encoding="utf-8")
    _provenance(p, asset)
    return asset


def scan(folder: str | Path, cache_dir: str | Path | None = None) -> list[Asset]:
    root = Path(folder)
    if not root.is_dir():
        raise NotADirectoryError(root)
    assets = []
    for p in sorted(root.rglob("*")):
        if p.is_file() and not p.name.endswith(".json"):
            a = index_file(p, cache_dir)
            if a is not None:
                assets.append(a)
    return assets


def find_duplicates(assets: list[Asset], max_distance: int = 5) -> list[list[str]]:
    """Groups of assets that are byte-identical (sha256) or visually near-identical (dHash)."""
    groups: list[list[str]] = []
    by_sha: dict[str, list[str]] = {}
    for a in assets:
        by_sha.setdefault(a.sha256, []).append(a.path)
    for paths in by_sha.values():
        if len(paths) > 1:
            groups.append(paths)
    images = [a for a in assets if a.dhash]
    seen: set[str] = set()
    for i, a in enumerate(images):
        if a.path in seen:
            continue
        group = [a.path]
        for b in images[i + 1:]:
            if b.path not in seen and hamming(a.dhash, b.dhash) <= max_distance and b.sha256 != a.sha256:
                group.append(b.path)
                seen.add(b.path)
        if len(group) > 1:
            groups.append(group)
            seen.add(a.path)
    return groups


def rank(assets: list[Asset], *, orientation: str | None = None, min_width: int = 0,
         min_duration: float = 0.0, kind: str | None = None,
         require_known_licence: bool = False) -> list[tuple[float, Asset, list[str]]]:
    """Score assets for a shot. Returns (score, asset, reasons), highest first.

    With require_known_licence=True, assets whose licence is "unknown" are dropped instead of
    penalised. Use it when the output will be published.
    """
    scored = []
    for a in assets:
        if kind and a.kind != kind:
            continue
        if require_known_licence and a.provenance.get("license", "unknown") == "unknown":
            continue
        score, reasons = 0.0, []
        if orientation:
            if a.orientation == orientation:
                score += 2
                reasons.append(f"{orientation} as requested")
            else:
                score -= 2
                reasons.append(f"orientation {a.orientation} differs from {orientation}")
        if a.width is not None:
            if a.width >= min_width:
                score += 1
            else:
                score -= 1.5
                reasons.append(f"width {a.width} below {min_width}")
        if a.sharpness is not None:
            score += min(2.0, math.log10(max(a.sharpness, 1.0)) / 2)
        if a.duration is not None and min_duration:
            if a.duration >= min_duration:
                score += 1
            else:
                score -= 2
                reasons.append(f"duration {a.duration}s below {min_duration}s")
        if a.provenance.get("license") == "unknown":
            score -= 0.5
            reasons.append("licence unknown")
        scored.append((round(score, 3), a, reasons))
    scored.sort(key=lambda x: (-x[0], x[1].path))
    return scored


def pick_diverse(ranked: list[tuple[float, Asset, list[str]]], count: int,
                 max_distance: int = 5) -> list[Asset]:
    """Take the best assets while skipping visual near-duplicates of ones already chosen."""
    chosen: list[Asset] = []
    for _, a, _ in ranked:
        if len(chosen) >= count:
            break
        if a.dhash and any(c.dhash and hamming(a.dhash, c.dhash) <= max_distance for c in chosen):
            continue
        if any(c.sha256 == a.sha256 for c in chosen):
            continue
        chosen.append(a)
    return chosen


def save_index(assets: list[Asset], out: str | Path) -> Path:
    p = Path(out)
    p.parent.mkdir(parents=True, exist_ok=True)
    p.write_text(json.dumps([asdict(a) for a in assets], ensure_ascii=False, indent=2), encoding="utf-8")
    return p
