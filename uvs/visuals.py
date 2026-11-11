"""Animation controls and timeline integration for Phase 6 visuals (6.5 + integration).

The chart, timeline, diagram and metaphor renderers each expose a frame function ``f(progress)``.
This module wraps any such function with camera controls — pan, zoom and an exit fade — then
encodes the result and returns a uvs.timeline.Clip so the visual can be dropped onto the editing
timeline like any other source.

Which 6.5 control lives where:
- build / reveal / data interpolation / staggered entrance / highlight: inside the chart, timeline
  and diagram renderers (driven by progress, easing and the stagger parameter).
- camera pan / zoom / exit animation: ``Controls`` here, applied per frame.
- layer compositing: the motion engine (uvs.animate), which composites scene-graph nodes.
"""
from __future__ import annotations

from dataclasses import dataclass
from fractions import Fraction
from pathlib import Path
from typing import Callable

from PIL import Image

from uvs import timeline as TL


@dataclass(frozen=True)
class Controls:
    """Camera moves applied over a clip's own [0, 1] timeline (not the inner animation progress)."""
    zoom_from: float = 1.0         # scale at clip start
    zoom_to: float = 1.0           # scale at clip end
    pan_from: tuple[float, float] = (0.5, 0.5)   # focus point (fraction of w, h) at start
    pan_to: tuple[float, float] = (0.5, 0.5)     # focus point at end
    exit_fade: float = 0.0         # seconds of fade-to-background at the end
    background: tuple[int, int, int] = (0, 0, 0)

    def validate(self) -> None:
        if self.zoom_from <= 0 or self.zoom_to <= 0:
            raise ValueError("zoom factors must be positive")
        for pt in (self.pan_from, self.pan_to):
            if not (0.0 <= pt[0] <= 1.0 and 0.0 <= pt[1] <= 1.0):
                raise ValueError("pan focus must be within the frame")
        if self.exit_fade < 0:
            raise ValueError("exit_fade cannot be negative")


def _lerp(a, b, t):
    return a + (b - a) * t


def apply_controls(frame: Image.Image, controls: Controls, clip_t: float) -> Image.Image:
    """Apply zoom + pan + exit fade for a frame at clip fraction clip_t in [0, 1]."""
    w, h = frame.size
    scale = _lerp(controls.zoom_from, controls.zoom_to, clip_t)
    fx = _lerp(controls.pan_from[0], controls.pan_to[0], clip_t)
    fy = _lerp(controls.pan_from[1], controls.pan_to[1], clip_t)
    out = frame
    if abs(scale - 1.0) > 1e-6 or (fx, fy) != (0.5, 0.5):
        crop_w, crop_h = w / scale, h / scale
        cx, cy = fx * w, fy * h
        left = min(max(cx - crop_w / 2, 0), w - crop_w)
        top = min(max(cy - crop_h / 2, 0), h - crop_h)
        out = frame.resize((w, h), Image.Resampling.BILINEAR,
                           box=(left, top, left + crop_w, top + crop_h))
    return out


def render_visual(frame_fn: Callable[[float], Image.Image], out: str | Path, *, duration: float,
                  fps: float, width: int, height: int, controls: Controls | None = None,
                  hold: float = 0.6, crf: int = 18) -> dict:
    """Encode frame_fn over its animation plus a hold, applying camera controls across the whole clip."""
    from uvs.animate import encode_frames

    controls = controls or Controls()
    controls.validate()
    total = duration + max(0.0, hold)
    n = max(2, int(round(total * fps)))
    fade_frames = int(round(controls.exit_fade * fps))

    def frames():
        for i in range(n):
            clip_t = i / (n - 1)
            inner = min(1.0, (clip_t * total) / duration)
            frame = apply_controls(frame_fn(inner), controls, clip_t)
            remaining = n - 1 - i
            if fade_frames and remaining < fade_frames:
                k = remaining / fade_frames
                frame = Image.blend(Image.new("RGB", frame.size, controls.background), frame, k)
            yield frame

    written = encode_frames(out, fps=fps, width=width, height=height, frames=frames(), crf=crf)
    return {"path": str(out), "frames": written, "fps": fps, "width": width, "height": height,
            "duration_frames": written}


def to_timeline_clip(clip_id: str, source: str, frames: int, fps: float, *, start: int = 0,
                     transition: str = "cut", transition_frames: int = 0) -> TL.Clip:
    """A timeline video clip for a rendered visual file."""
    return TL.Clip(id=clip_id, source=source, start=start, duration=frames, in_point=0,
                   transition=transition, transition_frames=transition_frames)
