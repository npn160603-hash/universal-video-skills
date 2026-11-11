"""Colour grading (cinematic-post-production, colour part, Phase 4).

A look is a set of original parameters, not a copied preset:
- eq: brightness, contrast, saturation, gamma (neutral values are 0, 1, 1, 1)
- colorbalance: lift (shadows), gamma (midtones), gain (highlights) per RGB channel
- vignette and film grain, both optional

Looks scale with an intensity: subtle, standard, cinematic, dynamic. Deviations from
neutral are multiplied, and the result is clamped so the image is not overprocessed.

Optional LUT workflow: a .cube file applied with lut3d. No LUT is bundled.
"""
from __future__ import annotations

import subprocess
from dataclasses import dataclass, field, replace
from pathlib import Path

INTENSITY = {"subtle": 0.5, "standard": 1.0, "cinematic": 1.3, "dynamic": 1.55}


@dataclass(frozen=True)
class Look:
    name: str
    brightness: float = 0.0
    contrast: float = 1.0
    saturation: float = 1.0
    gamma: float = 1.0
    shadows: tuple[float, float, float] = (0.0, 0.0, 0.0)
    midtones: tuple[float, float, float] = (0.0, 0.0, 0.0)
    highlights: tuple[float, float, float] = (0.0, 0.0, 0.0)
    vignette_angle: float | None = None   # radians; smaller angle = stronger vignette
    grain: float = 0.0                    # noise strength, 0 = none


LOOKS: dict[str, Look] = {
    "clean_documentary": Look("clean_documentary", contrast=1.05, saturation=0.95),
    "natural_daylight": Look("natural_daylight", contrast=1.03,
                             midtones=(0.02, 0.01, 0.0)),
    "warm_lifestyle": Look("warm_lifestyle", contrast=1.05, saturation=1.05, gamma=1.02,
                           midtones=(0.03, 0.0, -0.03), highlights=(0.05, 0.02, -0.05),
                           vignette_angle=1.2),
    "moody_cinematic": Look("moody_cinematic", brightness=-0.04, contrast=1.12, saturation=0.85,
                            shadows=(0.0, 0.0, 0.06), highlights=(0.04, 0.0, -0.02),
                            vignette_angle=0.9),
    "dark_investigative": Look("dark_investigative", brightness=-0.06, contrast=1.15, saturation=0.6,
                               shadows=(0.0, 0.0, 0.04), vignette_angle=0.75, grain=6.0),
    "desaturated_emotional": Look("desaturated_emotional", contrast=1.02, saturation=0.55,
                                  midtones=(0.0, 0.0, 0.02)),
    "bright_educational": Look("bright_educational", brightness=0.04, saturation=1.1),
    "modern_commercial": Look("modern_commercial", contrast=1.1, saturation=1.1,
                              highlights=(0.02, 0.01, 0.0)),
    "retro_film": Look("retro_film", contrast=0.95, saturation=0.8, gamma=1.05,
                       shadows=(0.0, 0.0, 0.03), highlights=(0.06, 0.03, -0.04),
                       vignette_angle=0.9, grain=10.0),
    "soft_romantic": Look("soft_romantic", brightness=0.02, contrast=0.95, saturation=0.9,
                          highlights=(0.03, 0.0, 0.01), grain=3.0),
    # The ten spec-named cinematic looks (Phase 9.3 / Phase 10). Original parameter sets.
    "documentary_natural": Look("documentary_natural", contrast=1.04, saturation=0.97),
    "warm_lifestyle_v2": Look("warm_lifestyle_v2", contrast=1.05, saturation=1.06, gamma=1.02,
                              midtones=(0.03, 0.0, -0.03), highlights=(0.05, 0.02, -0.05),
                              vignette_angle=1.2),
    "moody_cinematic_v2": Look("moody_cinematic_v2", brightness=-0.04, contrast=1.12,
                               saturation=0.85, shadows=(0.0, 0.0, 0.06),
                               highlights=(0.04, 0.0, -0.02), vignette_angle=0.9),
    "soft_romantic_v2": Look("soft_romantic_v2", brightness=0.02, contrast=0.95, saturation=0.9,
                             highlights=(0.03, 0.0, 0.01), grain=3.0),
    "dark_investigative_v2": Look("dark_investigative_v2", brightness=-0.06, contrast=1.15,
                                  saturation=0.6, shadows=(0.0, 0.0, 0.04),
                                  vignette_angle=0.75, grain=6.0),
    "bright_educational_v2": Look("bright_educational_v2", brightness=0.04, saturation=1.1),
    "neutral_commercial": Look("neutral_commercial", contrast=1.06, saturation=1.03,
                               highlights=(0.01, 0.01, 0.0)),
    "vintage_film": Look("vintage_film", contrast=0.95, saturation=0.8, gamma=1.05,
                         shadows=(0.0, 0.0, 0.03), highlights=(0.06, 0.03, -0.04),
                         vignette_angle=0.9, grain=10.0),
    "desaturated_emotional_v2": Look("desaturated_emotional_v2", contrast=1.02, saturation=0.55,
                                     midtones=(0.0, 0.0, 0.02)),
    "high_contrast_editorial": Look("high_contrast_editorial", contrast=1.25, saturation=1.05,
                                    shadows=(-0.02, -0.02, -0.02), highlights=(0.03, 0.03, 0.03)),
}


def _scale(look: Look, k: float) -> Look:
    """Scale deviations from neutral by k and clamp to safe ranges."""
    def s(v: float, neutral: float, lo: float, hi: float) -> float:
        return min(hi, max(lo, neutral + (v - neutral) * k))

    def triple(t):
        return tuple(max(-0.25, min(0.25, c * k)) for c in t)

    return replace(
        look,
        brightness=max(-0.3, min(0.3, look.brightness * k)),
        contrast=s(look.contrast, 1.0, 0.5, 1.6),
        saturation=s(look.saturation, 1.0, 0.0, 1.8),
        gamma=s(look.gamma, 1.0, 0.6, 1.6),
        shadows=triple(look.shadows),
        midtones=triple(look.midtones),
        highlights=triple(look.highlights),
        vignette_angle=None if look.vignette_angle is None else max(0.5, look.vignette_angle / max(k, 0.1)),
        grain=max(0.0, min(16.0, look.grain * k)),
    )


def look_filter(name: str, intensity: str = "standard") -> str:
    """Return an ffmpeg -vf chain for a named look at an intensity level."""
    if name not in LOOKS:
        raise KeyError(f"unknown look {name!r}; choose from {sorted(LOOKS)}")
    if intensity not in INTENSITY:
        raise KeyError(f"unknown intensity {intensity!r}; choose from {sorted(INTENSITY)}")
    look = _scale(LOOKS[name], INTENSITY[intensity])
    parts = [
        f"eq=brightness={look.brightness:.4f}:contrast={look.contrast:.4f}:"
        f"saturation={look.saturation:.4f}:gamma={look.gamma:.4f}",
    ]
    bal = [*look.shadows, *look.midtones, *look.highlights]
    if any(abs(v) > 1e-9 for v in bal):
        parts.append("colorbalance=" + ":".join(f"{v:.4f}" for v in bal))
    if look.vignette_angle is not None:
        parts.append(f"vignette=angle={look.vignette_angle:.4f}")
    if look.grain > 0:
        parts.append(f"noise=alls={look.grain:.2f}:allf=t")
    return ",".join(parts)


def lut_filter(path: str | Path) -> str:
    """ffmpeg -vf chain for a .cube 3D LUT. Refuses paths that would need filter escaping."""
    p = Path(path)
    if p.suffix.lower() != ".cube":
        raise ValueError("LUT must be a .cube file")
    if not p.exists():
        raise FileNotFoundError(p)
    if any(ch in str(p) for ch in ":'\\,;[]"):
        raise ValueError("LUT path contains characters that need filter escaping; rename the file")
    return f"lut3d=file={p}:interp=tetrahedral"


def grade(src: str | Path, out: str | Path, vf: str, crf: int = 18) -> Path:
    out = Path(out)
    out.parent.mkdir(parents=True, exist_ok=True)
    proc = subprocess.run(
        ["ffmpeg", "-hide_banner", "-loglevel", "error", "-y", "-i", str(src),
         "-vf", vf, "-c:v", "libx264", "-preset", "medium", "-crf", str(crf), "-pix_fmt", "yuv420p",
         "-c:a", "copy", "-map_metadata", "-1", str(out)],
        capture_output=True, text=True)
    if proc.returncode != 0:
        raise RuntimeError(f"grade failed: {proc.stderr.strip()[-600:]}")
    return out


def sample_rgb(path: str | Path, t: float) -> tuple[int, int, int]:
    """Average RGB of the frame at time t, measured from the decoded pixels."""
    proc = subprocess.run(
        ["ffmpeg", "-hide_banner", "-loglevel", "error", "-ss", f"{t:.4f}", "-i", str(path),
         "-frames:v", "1", "-vf", "scale=1:1", "-f", "rawvideo", "-pix_fmt", "rgb24", "-"],
        capture_output=True)
    if proc.returncode != 0 or len(proc.stdout) < 3:
        raise RuntimeError("could not sample frame")
    return proc.stdout[0], proc.stdout[1], proc.stdout[2]


def saturation(rgb: tuple[int, int, int]) -> float:
    hi, lo = max(rgb), min(rgb)
    return 0.0 if hi == 0 else (hi - lo) / hi
