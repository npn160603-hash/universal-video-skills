"""Colour management, shot matching, compositing and colour QA (Phase 9).

Colour operations build ffmpeg filter chains (exposure, contrast, white balance, tint, saturation,
curves, lift/gamma/gain, LUT). Frame analysis and shot matching are done in numpy on decoded pixels,
so every number is measured, not guessed. Shot matching computes a per-channel gain that brings one
shot's colour toward a reference, scaled by a configurable strength. Colour QA measures saturation,
shadow crush and highlight clipping and flags images that are overprocessed.

Compositing provides filter builders for alpha-over, blend modes, chroma key, masks, blur, glow,
vignette, film grain and light leaks. The grading looks live in uvs.grade; this module adds the ten
spec-named cinematic looks there and the analysis the grade cannot do by itself.
"""
from __future__ import annotations

import subprocess
from dataclasses import dataclass, field
from pathlib import Path

import numpy as np

from uvs import grade as G


class ColorError(ValueError):
    pass


# ---------------------------------------------------------------------------
# Colour-management primitives (9.1)
# ---------------------------------------------------------------------------

@dataclass(frozen=True)
class ColorAdjust:
    exposure: float = 0.0        # stops; 0 = neutral
    contrast: float = 1.0
    saturation: float = 1.0
    gamma: float = 1.0
    temperature: int = 6500      # Kelvin; 6500 = neutral
    tint: float = 0.0            # -1 (green) .. +1 (magenta)
    lift: tuple[float, float, float] = (0.0, 0.0, 0.0)     # shadows per RGB
    gamma_rgb: tuple[float, float, float] = (0.0, 0.0, 0.0)  # midtones per RGB
    gain: tuple[float, float, float] = (0.0, 0.0, 0.0)     # highlights per RGB

    def validate(self) -> None:
        if not (-4.0 <= self.exposure <= 4.0):
            raise ColorError("exposure must be within +/- 4 stops")
        if not (1000 <= self.temperature <= 40000):
            raise ColorError("temperature must be 1000-40000 K")
        if not (-1.0 <= self.tint <= 1.0):
            raise ColorError("tint must be within +/- 1")
        if self.contrast <= 0 or self.saturation < 0 or self.gamma <= 0:
            raise ColorError("contrast, gamma must be positive and saturation non-negative")

    def to_filter(self) -> str:
        self.validate()
        parts = []
        if abs(self.exposure) > 1e-6:
            parts.append(f"exposure=exposure={self.exposure:.4f}")
        if (abs(self.contrast - 1) > 1e-6 or abs(self.saturation - 1) > 1e-6
                or abs(self.gamma - 1) > 1e-6):
            parts.append(f"eq=contrast={self.contrast:.4f}:saturation={self.saturation:.4f}:"
                         f"gamma={self.gamma:.4f}")
        if self.temperature != 6500:
            # colortemperature filter sets the target temperature of the image
            parts.append(f"colortemperature=temperature={self.temperature}")
        if abs(self.tint) > 1e-6:
            # push green<->magenta via the green channel
            g = 1.0 - 0.3 * self.tint
            parts.append(f"colorchannelmixer=0:0:0:0:0:{g:.4f}:0:0:0:0:0:0")
        bal = [*self.lift, *self.gamma_rgb, *self.gain]
        if any(abs(v) > 1e-9 for v in bal):
            parts.append("colorbalance=" + ":".join(f"{v:.4f}" for v in bal))
        return ",".join(parts) if parts else "null"


def curves_filter(points: list[tuple[float, float]], channel: str = "all") -> str:
    """A tone curve from control points in [0,1]. channel: all, r, g, b."""
    if channel not in {"all", "r", "g", "b"}:
        raise ColorError("channel must be all, r, g or b")
    if len(points) < 2:
        raise ColorError("a curve needs at least two points")
    for x, y in points:
        if not (0 <= x <= 1 and 0 <= y <= 1):
            raise ColorError("curve points must be within [0, 1]")
    spec = " ".join(f"{x:.3f}/{y:.3f}" for x, y in points)
    key = {"all": "all", "r": "r", "g": "g", "b": "b"}[channel]
    return f"curves={key}='{spec}'"


# ---------------------------------------------------------------------------
# Frame analysis (numpy, measured)
# ---------------------------------------------------------------------------

@dataclass(frozen=True)
class ColorStats:
    mean_rgb: tuple[float, float, float]
    luma: float                # 0..255
    contrast: float            # luma std
    saturation: float          # mean HSV saturation 0..1
    warmth: float              # R/B ratio; >1 warm, <1 cool
    shadow_crush: float        # fraction of pixels with luma < 8
    highlight_clip: float      # fraction of pixels with luma > 247

    def as_dict(self) -> dict:
        return {"mean_rgb": [round(c, 2) for c in self.mean_rgb], "luma": round(self.luma, 2),
                "contrast": round(self.contrast, 2), "saturation": round(self.saturation, 3),
                "warmth": round(self.warmth, 3), "shadow_crush": round(self.shadow_crush, 4),
                "highlight_clip": round(self.highlight_clip, 4)}


def analyze_array(img: np.ndarray) -> ColorStats:
    a = img.astype(np.float64)
    mean = a.reshape(-1, 3).mean(0)
    luma = 0.299 * a[..., 0] + 0.587 * a[..., 1] + 0.114 * a[..., 2]
    hi = a.max(axis=2)
    lo = a.min(axis=2)
    sat = np.where(hi > 0, (hi - lo) / np.maximum(hi, 1e-6), 0.0)
    return ColorStats(
        mean_rgb=(float(mean[0]), float(mean[1]), float(mean[2])),
        luma=float(luma.mean()),
        contrast=float(luma.std()),
        saturation=float(sat.mean()),
        warmth=float(mean[0] / max(mean[2], 1e-6)),
        shadow_crush=float((luma < 8).mean()),
        highlight_clip=float((luma > 247).mean()),
    )


def decode_frame(path: str | Path, t: float = 0.0, *, width: int = 160) -> np.ndarray:
    """Decode one frame at time t to an RGB array (scaled to `width`, aspect kept)."""
    proc = subprocess.run(
        ["ffmpeg", "-hide_banner", "-loglevel", "error", "-ss", f"{t:.4f}", "-i", str(path),
         "-frames:v", "1", "-vf", f"scale={width}:-1", "-f", "rawvideo", "-pix_fmt", "rgb24", "-"],
        capture_output=True)
    if proc.returncode != 0 or not proc.stdout:
        raise ColorError("could not decode frame")
    # infer height from byte count
    n = len(proc.stdout) // 3
    h = n // width
    return np.frombuffer(proc.stdout[: width * h * 3], dtype=np.uint8).reshape(h, width, 3)


def analyze_frame(path: str | Path, t: float = 0.0) -> ColorStats:
    return analyze_array(decode_frame(path, t))


# ---------------------------------------------------------------------------
# Shot matching (9.2)
# ---------------------------------------------------------------------------

@dataclass(frozen=True)
class MatchResult:
    gain_rgb: tuple[float, float, float]
    strength: float

    def apply_to_array(self, img: np.ndarray) -> np.ndarray:
        g = 1.0 + (np.array(self.gain_rgb) - 1.0) * self.strength
        return np.clip(img.astype(np.float64) * g, 0, 255).astype(np.uint8)

    def to_filter(self) -> str:
        g = [1.0 + (c - 1.0) * self.strength for c in self.gain_rgb]
        return f"colorchannelmixer=rr={g[0]:.4f}:gg={g[1]:.4f}:bb={g[2]:.4f}"


def match_shots(reference: np.ndarray, target: np.ndarray, *, strength: float = 1.0) -> MatchResult:
    """Per-channel gain that brings `target`'s mean toward `reference`'s, scaled by strength."""
    if not (0.0 <= strength <= 1.0):
        raise ColorError("strength must be between 0 and 1")
    ref_mean = reference.astype(np.float64).reshape(-1, 3).mean(0)
    tgt_mean = target.astype(np.float64).reshape(-1, 3).mean(0)
    gain = ref_mean / np.maximum(tgt_mean, 1e-6)
    gain = np.clip(gain, 0.4, 2.5)
    return MatchResult(gain_rgb=(float(gain[0]), float(gain[1]), float(gain[2])), strength=strength)


def match_distance(a: np.ndarray, b: np.ndarray) -> float:
    """Sum of absolute mean-channel differences; a simple colour distance."""
    return float(np.abs(a.astype(np.float64).reshape(-1, 3).mean(0)
                        - b.astype(np.float64).reshape(-1, 3).mean(0)).sum())


# ---------------------------------------------------------------------------
# Colour QA (9.5)
# ---------------------------------------------------------------------------

@dataclass(frozen=True)
class ColorQA:
    stats: ColorStats
    issues: list[str]

    @property
    def ok(self) -> bool:
        return not self.issues


def color_qa(stats: ColorStats, *, max_saturation: float = 0.85, max_crush: float = 0.05,
             max_clip: float = 0.05) -> ColorQA:
    issues = []
    if stats.saturation > max_saturation:
        issues.append(f"excessive saturation {stats.saturation:.2f} (limit {max_saturation})")
    if stats.shadow_crush > max_crush:
        issues.append(f"crushed shadows: {stats.shadow_crush:.1%} of pixels near black")
    if stats.highlight_clip > max_clip:
        issues.append(f"clipped highlights: {stats.highlight_clip:.1%} of pixels near white")
    return ColorQA(stats, issues)


# ---------------------------------------------------------------------------
# Compositing primitives (9.4)
# ---------------------------------------------------------------------------

BLEND_MODES = ("normal", "screen", "multiply", "overlay", "addition", "softlight", "lighten", "darken")


def chroma_key(color: str = "0x00FF00", similarity: float = 0.15, blend: float = 0.05) -> str:
    return f"chromakey={color}:{similarity:.4f}:{blend:.4f}"


def gaussian_blur(sigma: float = 6.0) -> str:
    if sigma <= 0:
        raise ColorError("blur sigma must be positive")
    return f"gblur=sigma={sigma:.3f}"


def glow(sigma: float = 12.0, amount: float = 0.6) -> str:
    """A bloom: blur a copy and screen it back. Returns a filter_complex fragment label [glow]."""
    if not (0.0 <= amount <= 1.0):
        raise ColorError("glow amount must be 0..1")
    return (f"split=2[base][b1];[b1]gblur=sigma={sigma:.3f}[bl];"
            f"[base][bl]blend=all_mode=screen:all_opacity={amount:.3f}[glow]")


def vignette(angle: float = 0.9) -> str:
    if angle <= 0:
        raise ColorError("vignette angle must be positive")
    return f"vignette=angle={angle:.4f}"


def film_grain(strength: float = 8.0) -> str:
    if strength < 0:
        raise ColorError("grain strength must be non-negative")
    return f"noise=alls={strength:.2f}:allf=t"


def unsharp(amount: float = 1.0) -> str:
    return f"unsharp=5:5:{amount:.3f}:5:5:0.0"


def light_leak(color: str = "orange", opacity: float = 0.25) -> str:
    """A soft diagonal colour wash, approximating a light leak, as a filter_complex fragment."""
    if not (0.0 <= opacity <= 1.0):
        raise ColorError("opacity must be 0..1")
    return (f"color=c={color}:s=iw*ih[cl];"
            f"[cl]gblur=sigma=60[leak];[in][leak]blend=all_mode=screen:all_opacity={opacity:.3f}")


def alpha_over(x: int = 0, y: int = 0) -> str:
    """Overlay the second input onto the first with alpha at (x, y)."""
    return f"overlay={x}:{y}:format=auto"


# ---------------------------------------------------------------------------
# The ten spec-named cinematic looks (9.3) live in uvs.grade.LOOKS.
# ---------------------------------------------------------------------------

# The ten canonical names, in spec order (Documentary Natural, Warm Lifestyle, Moody Cinematic,
# Soft Romantic, Dark Investigative, Bright Educational, Neutral Commercial, Vintage Film,
# Desaturated Emotional, High Contrast Editorial).
SPEC_LOOK_NAMES = ("documentary_natural", "warm_lifestyle_v2", "moody_cinematic_v2",
                   "soft_romantic_v2", "dark_investigative_v2", "bright_educational_v2",
                   "neutral_commercial", "vintage_film", "desaturated_emotional_v2",
                   "high_contrast_editorial")
