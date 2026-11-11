"""Hardware detection, export profiles, render cache and benchmarking (Phase 13).

Hardware detection reports the real CPU count and RAM, whether a GPU is actually present (not just
whether ffmpeg lists an nvenc encoder), and which encoders actually work — each candidate is
test-encoded, so a compiled-in but non-functional encoder is reported as unavailable. Nothing here
assumes hardware acceleration.

Export profiles cover 9:16, 16:9 and 1:1 at 720p/1080p (1440p/4K optional) with H.264 or H.265 and
AAC audio. The render cache keys finished files by a content hash of their inputs, so an unchanged
render is reused. Benchmarking measures real duration, output size, encoding FPS, memory and decode
validity — no figure is invented.
"""
from __future__ import annotations

import hashlib
import json
import os
import shutil
import subprocess
import time
from dataclasses import dataclass, field
from pathlib import Path

try:
    import psutil
except ImportError:  # pragma: no cover
    psutil = None


class ExportError(ValueError):
    pass


def _ffmpeg() -> None:
    if shutil.which("ffmpeg") is None or shutil.which("ffprobe") is None:
        raise ExportError("ffmpeg and ffprobe are required")


# ---------------------------------------------------------------------------
# Hardware detection (13.1)
# ---------------------------------------------------------------------------

@dataclass(frozen=True)
class Hardware:
    cpu_cores: int
    ram_gb: float
    gpu_present: bool
    gpu_name: str
    working_video_encoders: tuple[str, ...]
    working_audio_encoders: tuple[str, ...]
    listed_hwaccels: tuple[str, ...]
    filter_count: int

    def as_dict(self) -> dict:
        return {"cpu_cores": self.cpu_cores, "ram_gb": round(self.ram_gb, 2),
                "gpu_present": self.gpu_present, "gpu_name": self.gpu_name,
                "working_video_encoders": list(self.working_video_encoders),
                "working_audio_encoders": list(self.working_audio_encoders),
                "listed_hwaccels": list(self.listed_hwaccels), "filter_count": self.filter_count}


def _test_video_encoder(name: str) -> bool:
    """True only if the encoder actually produces output here (not merely compiled in)."""
    r = subprocess.run(["ffmpeg", "-hide_banner", "-loglevel", "error", "-y", "-f", "lavfi",
                        "-i", "color=c=black:s=64x64:d=0.1:r=5", "-c:v", name, "-frames:v", "1",
                        "-f", "null", "-"], capture_output=True)
    return r.returncode == 0


def _test_audio_encoder(name: str) -> bool:
    r = subprocess.run(["ffmpeg", "-hide_banner", "-loglevel", "error", "-y", "-f", "lavfi",
                        "-i", "sine=frequency=440:duration=0.1", "-c:a", name, "-f", "null", "-"],
                       capture_output=True)
    return r.returncode == 0


def _gpu() -> tuple[bool, str]:
    if shutil.which("nvidia-smi"):
        r = subprocess.run(["nvidia-smi", "--query-gpu=name", "--format=csv,noheader"],
                           capture_output=True, text=True)
        if r.returncode == 0 and r.stdout.strip():
            return True, r.stdout.strip().splitlines()[0]
    return False, "none"


def detect_hardware() -> Hardware:
    _ffmpeg()
    cpu = os.cpu_count() or 1
    if psutil is not None:
        ram = psutil.virtual_memory().total / 1e9
    else:  # pragma: no cover
        ram = 0.0
        try:
            for line in Path("/proc/meminfo").read_text().splitlines():
                if line.startswith("MemTotal"):
                    ram = int(line.split()[1]) * 1024 / 1e9
        except OSError:
            pass
    gpu_present, gpu_name = _gpu()
    video = tuple(e for e in ("libx264", "libx265", "libvpx-vp9") if _test_video_encoder(e))
    # Only test hardware encoders if a GPU is actually present (avoid false positives).
    if gpu_present:
        video += tuple(e for e in ("h264_nvenc", "hevc_nvenc") if _test_video_encoder(e))
    audio = tuple(e for e in ("aac", "libopus", "libmp3lame") if _test_audio_encoder(e))
    accels = subprocess.run(["ffmpeg", "-hide_banner", "-hwaccels"], capture_output=True, text=True).stdout
    hwaccels = tuple(a for a in accels.split() if a not in {"Hardware", "acceleration", "methods:"})
    nfilters = subprocess.run(["ffmpeg", "-hide_banner", "-filters"], capture_output=True, text=True
                              ).stdout.count("\n")
    return Hardware(cpu, ram, gpu_present, gpu_name, video, audio, hwaccels, nfilters)


# ---------------------------------------------------------------------------
# Export profiles (13.3)
# ---------------------------------------------------------------------------

ASPECTS = {"9:16": (1080, 1920), "16:9": (1920, 1080), "1:1": (1080, 1080)}
RESOLUTIONS = {"720p": 720, "1080p": 1080, "1440p": 1440, "4k": 2160}


@dataclass(frozen=True)
class ExportProfile:
    name: str
    aspect: str
    resolution: str
    vcodec: str        # h264 | h265
    acodec: str = "aac"
    crf: int = 20
    fps: int = 30

    def dimensions(self) -> tuple[int, int]:
        base_w, base_h = ASPECTS[self.aspect]
        short = RESOLUTIONS[self.resolution]
        if self.aspect == "9:16":
            w, h = short * 9 // 16, short
        elif self.aspect == "16:9":
            w, h = short * 16 // 9, short
        else:
            w = h = short
        return (w - w % 2, h - h % 2)

    def encoder(self) -> str:
        return {"h264": "libx264", "h265": "libx265"}[self.vcodec]

    def validate(self) -> None:
        if self.aspect not in ASPECTS:
            raise ExportError(f"aspect must be one of {sorted(ASPECTS)}")
        if self.resolution not in RESOLUTIONS:
            raise ExportError(f"resolution must be one of {sorted(RESOLUTIONS)}")
        if self.vcodec not in {"h264", "h265"}:
            raise ExportError("vcodec must be h264 or h265")


def standard_profiles() -> dict[str, ExportProfile]:
    """9:16, 16:9, 1:1 at 720p and 1080p, H.264 — the required tested set."""
    profiles = {}
    for aspect in ("9:16", "16:9", "1:1"):
        for res in ("720p", "1080p"):
            name = f"{aspect.replace(':', 'x')}_{res}_h264"
            profiles[name] = ExportProfile(name=name, aspect=aspect, resolution=res, vcodec="h264")
    return profiles


def export(src: str | Path, out: str | Path, profile: ExportProfile, *,
           hardware: Hardware | None = None) -> dict:
    """Transcode src to the profile. Falls back to h264 if h265 is not a working encoder."""
    profile.validate()
    _ffmpeg()
    hw = hardware or detect_hardware()
    encoder = profile.encoder()
    if encoder not in hw.working_video_encoders:
        if "libx264" in hw.working_video_encoders:
            encoder = "libx264"
        else:
            raise ExportError(f"no working encoder for {profile.vcodec}")
    w, h = profile.dimensions()
    out = Path(out)
    out.parent.mkdir(parents=True, exist_ok=True)
    vf = f"scale={w}:{h}:force_original_aspect_ratio=decrease,pad={w}:{h}:(ow-iw)/2:(oh-ih)/2,setsar=1"
    r = subprocess.run(["ffmpeg", "-hide_banner", "-loglevel", "error", "-y", "-i", str(src),
                        "-vf", vf, "-c:v", encoder, "-crf", str(profile.crf), "-pix_fmt", "yuv420p",
                        "-r", str(profile.fps), "-c:a", profile.acodec, "-movflags", "+faststart",
                        str(out)], capture_output=True, text=True)
    if r.returncode != 0:
        raise ExportError(f"export failed: {r.stderr.strip()[-400:]}")
    return {"output": str(out), "encoder": encoder, "width": w, "height": h,
            "aspect": profile.aspect, "resolution": profile.resolution}


# ---------------------------------------------------------------------------
# Render cache (13.2)
# ---------------------------------------------------------------------------

@dataclass
class RenderCache:
    root: Path

    def __post_init__(self):
        self.root = Path(self.root)
        self.root.mkdir(parents=True, exist_ok=True)

    def key(self, *parts: str) -> str:
        h = hashlib.sha256()
        for p in parts:
            h.update(p.encode("utf-8"))
            h.update(b"\x00")
        return h.hexdigest()[:24]

    def path_for(self, key: str, suffix: str = ".mp4") -> Path:
        return self.root / f"{key}{suffix}"

    def has(self, key: str, suffix: str = ".mp4") -> bool:
        return self.path_for(key, suffix).exists()

    def get_or_render(self, key: str, render_fn, *, suffix: str = ".mp4") -> dict:
        target = self.path_for(key, suffix)
        if target.exists():
            return {"path": str(target), "cached": True}
        # Keep the real suffix so ffmpeg can infer the container (e.g. key.tmp.mp4).
        tmp = target.with_name(f"{target.stem}.tmp{suffix}")
        render_fn(tmp)
        if not tmp.exists():
            raise ExportError("render function did not produce a file")
        tmp.replace(target)
        return {"path": str(target), "cached": False}

    def clear(self) -> int:
        n = 0
        for f in self.root.glob("*"):
            if f.is_file():
                f.unlink()
                n += 1
        return n


# ---------------------------------------------------------------------------
# Benchmarking (13.4)
# ---------------------------------------------------------------------------

def decode_valid(path: str | Path) -> tuple[bool, int]:
    """Decode the whole file; return (ok, frame_count). A truncated file fails here."""
    r = subprocess.run(["ffprobe", "-v", "error", "-count_frames", "-select_streams", "v:0",
                        "-show_entries", "stream=nb_read_frames", "-of", "csv=p=0", str(path)],
                       capture_output=True, text=True)
    if r.returncode != 0 or not r.stdout.strip().isdigit():
        return False, 0
    return True, int(r.stdout.strip())


@dataclass(frozen=True)
class Benchmark:
    render_seconds: float
    output_bytes: int
    frames: int
    encoding_fps: float
    peak_memory_mb: float
    decode_ok: bool

    def as_dict(self) -> dict:
        return {"render_seconds": round(self.render_seconds, 3), "output_bytes": self.output_bytes,
                "frames": self.frames, "encoding_fps": round(self.encoding_fps, 1),
                "peak_memory_mb": round(self.peak_memory_mb, 1), "decode_ok": self.decode_ok}


def benchmark_render(render_fn, out: Path) -> Benchmark:
    """Run render_fn(out), measuring wall time, size, fps and decode validity. Memory if psutil."""
    mem_before = psutil.Process().memory_info().rss / 1e6 if psutil else 0.0
    t0 = time.perf_counter()
    render_fn(out)
    dt = time.perf_counter() - t0
    mem_after = psutil.Process().memory_info().rss / 1e6 if psutil else 0.0
    ok, frames = decode_valid(out)
    size = Path(out).stat().st_size if Path(out).exists() else 0
    return Benchmark(render_seconds=dt, output_bytes=size, frames=frames,
                     encoding_fps=(frames / dt if dt > 0 else 0.0),
                     peak_memory_mb=max(mem_before, mem_after), decode_ok=ok)


def export_capability_matrix(hardware: Hardware | None = None) -> dict:
    """Which profiles can be exported here, given the working encoders. Measured, not assumed."""
    hw = hardware or detect_hardware()
    rows = []
    for name, p in standard_profiles().items():
        enc = p.encoder()
        usable = enc in hw.working_video_encoders or "libx264" in hw.working_video_encoders
        w, h = p.dimensions()
        rows.append({"profile": name, "aspect": p.aspect, "resolution": p.resolution,
                     "vcodec": p.vcodec, "dimensions": f"{w}x{h}", "exportable": usable})
    return {"hardware": hw.as_dict(), "profiles": rows}
