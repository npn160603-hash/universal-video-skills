"""Rendering interface (Phase 1.4).

The editing model (uvs.timeline, uvs.edit_ops, uvs.scenegraph) describes WHAT to show. A RenderBackend
decides HOW it is encoded. The project's existing ffmpeg renderer is wrapped as FFmpegBackend without
being rewritten. Other backends can implement the same methods later.
"""
from __future__ import annotations

import subprocess
from abc import ABC, abstractmethod
from functools import lru_cache
from pathlib import Path

from uvs import render as R
from uvs import timeline as T


class RenderBackend(ABC):
    name = "abstract"

    @abstractmethod
    def capabilities(self) -> dict:
        """Describe what this backend can do, as plain data (for capability reports)."""

    @abstractmethod
    def render_timeline(self, tl: T.Timeline, out: str | Path, crf: int = 18) -> Path:
        """Composite a validated timeline into a video file."""

    @abstractmethod
    def burn_captions(self, src: str | Path, ass_file: str | Path, out: str | Path) -> Path:
        """Burn ASS subtitles into a video file."""


@lru_cache(maxsize=1)
def _ffmpeg_info(binary: str) -> dict:
    version = subprocess.run([binary, "-hide_banner", "-version"], capture_output=True, text=True)
    encoders = subprocess.run([binary, "-hide_banner", "-encoders"], capture_output=True, text=True).stdout
    filters = subprocess.run([binary, "-hide_banner", "-filters"], capture_output=True, text=True).stdout
    hwaccels = subprocess.run([binary, "-hide_banner", "-hwaccels"], capture_output=True, text=True).stdout
    names_enc = {line.split()[1] for line in encoders.splitlines() if line.startswith(" ") and len(line.split()) > 1}
    names_flt = {line.split()[1] for line in filters.splitlines() if line.startswith(" ") and len(line.split()) > 1}
    return {
        "version": version.stdout.splitlines()[0] if version.stdout else "unknown",
        "encoders": sorted(names_enc),
        "filters": sorted(names_flt),
        "hwaccels": [h for h in hwaccels.splitlines()[1:] if h.strip()],
    }


class FFmpegBackend(RenderBackend):
    name = "ffmpeg"

    def __init__(self, binary: str = "ffmpeg"):
        self.binary = binary

    def capabilities(self) -> dict:
        info = _ffmpeg_info(self.binary)
        enc, flt = set(info["encoders"]), set(info["filters"])
        return {
            "backend": self.name,
            "ffmpeg": info["version"],
            "codecs": {
                "h264": "libx264" in enc,
                "h265": "libx265" in enc,
                "aac": "aac" in enc,
            },
            "filters": {f: f in flt for f in ("xfade", "ass", "overlay", "loudnorm", "alimiter",
                                               "sidechaincompress", "lut3d", "afftdn")},
            "hardware_accel": info["hwaccels"],
        }

    def render_timeline(self, tl: T.Timeline, out: str | Path, crf: int = 18) -> Path:
        return T.render(tl, out, crf=crf)

    def burn_captions(self, src: str | Path, ass_file: str | Path, out: str | Path) -> Path:
        return R.burn_captions(src, ass_file, out)


def default_backend() -> RenderBackend:
    return FFmpegBackend()
