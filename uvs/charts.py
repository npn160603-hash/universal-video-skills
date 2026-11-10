"""Data-driven bar chart (data-visual-storytelling, Phase 5).

Rules that keep it honest:
- Every bar comes from the supplied values. Nothing is generated or estimated.
- Values must be finite, non-negative numbers. Missing values make the call fail; they are not skipped silently.
- A source string is required. The chart prints it on the frame.
- Animation eases each bar from 0 to its value using motion.ease_out. The last frame equals the data.
"""
from __future__ import annotations

import math
import shutil
import subprocess
import tempfile
from dataclasses import dataclass
from pathlib import Path
from typing import Sequence

from PIL import Image, ImageDraw, ImageFont

from uvs.captions import resolve_font_file
from uvs.motion import ease_out

BG = (17, 20, 26)
BAR = (200, 161, 101)
TEXT = (240, 236, 228)
MUTED = (150, 150, 150)


@dataclass(frozen=True)
class Bar:
    label: str
    value: float


@dataclass(frozen=True)
class Layout:
    width: int
    height: int
    baseline: int
    rects: list[tuple[int, int, int, int]]   # x0, y0, x1, y1 of each bar at full height


def _font(bold: bool, size: int):
    path = resolve_font_file("Inter", bold)
    return ImageFont.truetype(path, size) if path else ImageFont.load_default(size=size)


def validate(bars: Sequence[Bar], source: str) -> None:
    if not source or not source.strip():
        raise ValueError("a source is required for every chart")
    if not bars:
        raise ValueError("no data to chart")
    labels = [b.label for b in bars]
    if len(set(labels)) != len(labels):
        raise ValueError("bar labels must be unique")
    for b in bars:
        if not isinstance(b.value, (int, float)) or not math.isfinite(b.value):
            raise ValueError(f"value for {b.label!r} is missing or not a finite number")
        if b.value < 0:
            raise ValueError(f"value for {b.label!r} is negative; bar charts here take non-negative values")


def compute_layout(n: int, width: int, height: int) -> Layout:
    margin_x, top, bottom = int(width * 0.08), int(height * 0.22), int(height * 0.16)
    baseline = height - bottom
    avail = width - 2 * margin_x
    gap = int(avail * 0.06)
    bar_w = (avail - gap * (n - 1)) // n
    rects = []
    for i in range(n):
        x0 = margin_x + i * (bar_w + gap)
        rects.append((x0, top, x0 + bar_w, baseline))
    return Layout(width=width, height=height, baseline=baseline, rects=rects)


def draw_frame(bars: Sequence[Bar], source: str, title: str, unit: str, progress: float,
               width: int = 1080, height: int = 1350, layout: Layout | None = None) -> Image.Image:
    """Render one frame. progress in [0, 1] scales bars with ease_out."""
    lay = layout or compute_layout(len(bars), width, height)
    img = Image.new("RGB", (width, height), BG)
    d = ImageDraw.Draw(img)
    f_title = _font(True, int(height * 0.045))
    f_label = _font(False, int(height * 0.028))
    f_value = _font(True, int(height * 0.032))
    f_src = _font(False, int(height * 0.02))
    d.text((lay.rects[0][0], int(height * 0.08)), title, font=f_title, fill=TEXT)
    d.line((lay.rects[0][0], lay.baseline, lay.rects[-1][2], lay.baseline), fill=MUTED, width=2)

    p = ease_out(max(0.0, min(1.0, progress)))
    max_value = max(b.value for b in bars) or 1.0
    full_h = lay.baseline - lay.rects[0][1]
    for bar, (x0, y0, x1, y1) in zip(bars, lay.rects):
        h = full_h * (bar.value / max_value) * p
        top = lay.baseline - h
        if h >= 1:
            d.rectangle((x0, top, x1, lay.baseline), fill=BAR)
        shown = bar.value * p
        value_text = (f"{shown:,.0f}" if float(bar.value).is_integer() else f"{shown:,.1f}") + (f" {unit}" if unit else "")
        d.text((x0, top - int(height * 0.04)), value_text, font=f_value, fill=TEXT)
        d.text((x0, lay.baseline + int(height * 0.015)), bar.label, font=f_label, fill=TEXT)
    d.text((lay.rects[0][0], height - int(height * 0.05)), f"Source: {source}", font=f_src, fill=MUTED)
    return img


def chart_png(bars: Sequence[Bar], source: str, out: str | Path, *, title: str = "", unit: str = "",
              width: int = 1080, height: int = 1350) -> Path:
    validate(bars, source)
    out = Path(out)
    out.parent.mkdir(parents=True, exist_ok=True)
    draw_frame(bars, source, title, unit, 1.0, width, height).save(out)
    return out


def chart_video(bars: Sequence[Bar], source: str, out: str | Path, *, title: str = "", unit: str = "",
                seconds: float = 4.0, fps: int = 30, width: int = 1080, height: int = 1350) -> Path:
    """Animated bars rendered frame by frame, then encoded to H.264. The final frame equals the data."""
    if shutil.which("ffmpeg") is None:
        raise RuntimeError("ffmpeg is required for chart video")
    validate(bars, source)
    out = Path(out)
    out.parent.mkdir(parents=True, exist_ok=True)
    frames = max(2, int(round(seconds * fps)))
    with tempfile.TemporaryDirectory() as tmp:
        for i in range(frames):
            t = i / (frames - 1)
            draw_frame(bars, source, title, unit, t, width, height).save(Path(tmp) / f"f{i:05d}.png")
        proc = subprocess.run(
            ["ffmpeg", "-hide_banner", "-loglevel", "error", "-y", "-framerate", str(fps),
             "-i", str(Path(tmp) / "f%05d.png"), "-c:v", "libx264", "-pix_fmt", "yuv420p",
             "-crf", "18", "-preset", "medium", "-map_metadata", "-1", "-movflags", "+faststart", str(out)],
            capture_output=True, text=True)
        if proc.returncode != 0:
            raise RuntimeError(f"chart encode failed: {proc.stderr.strip()[-400:]}")
    return out
