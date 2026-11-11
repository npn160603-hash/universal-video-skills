"""Ten full editing presets and a Style Lock system (Phase 10).

A VideoStyle is a complete editing preset, not a colour LUT: it fixes the narrative structure, shot
duration strategy, cut frequency, transition policy, typography, caption design, camera movement,
easing language, animation intensity, visual effects, colour grade, B-roll preference, music
direction, SFX intensity, map style, infographic style and safe area.

StyleLock resolves one preset for a whole project and hands out the same, validated configuration
for every scene. This replaces the old behaviour (technical debt D-01) where the whole video
inherited whatever look scene 0 happened to have. The locked style is chosen explicitly and applied
deterministically to every scene.
"""
from __future__ import annotations

from dataclasses import dataclass, field, asdict
from typing import FrozenSet

from uvs import grade as G
from uvs.captions import STYLES as CAPTION_STYLES
from uvs.audio_intel import EMOTION_SOUND
from uvs.infographics import THEMES as INFOGRAPHIC_THEMES


class StyleError(ValueError):
    pass


CUT_FREQUENCIES = ("low", "medium", "high")
SFX_INTENSITIES = ("none", "low", "medium", "high")
CAMERA_MOVEMENTS = ("static", "subtle", "dynamic", "kinetic")
MAP_STYLES = ("none", "minimal", "documentary", "route_focus")


@dataclass(frozen=True)
class SafeArea:
    top: float = 0.06
    bottom: float = 0.12
    left: float = 0.05
    right: float = 0.05

    def validate(self) -> None:
        for v in (self.top, self.bottom, self.left, self.right):
            if not (0.0 <= v < 0.4):
                raise StyleError("safe-area margins must be in [0, 0.4)")


@dataclass(frozen=True)
class VideoStyle:
    name: str
    narrative_structure: str
    shot_duration_strategy: str
    target_shot_seconds: float
    cut_frequency: str
    transition_policy: str
    typography: str            # caption style name
    camera_movement: str
    easing_language: str
    animation_intensity: str   # grade/motion intensity bucket
    visual_effects: FrozenSet[str]
    color_grade: str           # look name
    color_intensity: str
    broll_preference: str
    music_direction: str       # emotion key for sound direction
    sfx_intensity: str
    map_style: str
    infographic_theme: str
    safe_area: SafeArea = field(default_factory=SafeArea)

    def caption_style(self):
        return CAPTION_STYLES[self.typography]

    def look_filter(self) -> str:
        return G.look_filter(self.color_grade, self.color_intensity)

    def sound_direction(self):
        return EMOTION_SOUND[self.music_direction]

    def to_dict(self) -> dict:
        d = asdict(self)
        d["visual_effects"] = sorted(self.visual_effects)
        return d


def validate_style(s: VideoStyle) -> None:
    if s.typography not in CAPTION_STYLES:
        raise StyleError(f"unknown caption style {s.typography!r}")
    if s.color_grade not in G.LOOKS:
        raise StyleError(f"unknown look {s.color_grade!r}")
    if s.color_intensity not in G.INTENSITY:
        raise StyleError(f"unknown intensity {s.color_intensity!r}")
    if s.music_direction not in EMOTION_SOUND:
        raise StyleError(f"unknown music direction {s.music_direction!r}")
    if s.infographic_theme not in INFOGRAPHIC_THEMES:
        raise StyleError(f"unknown infographic theme {s.infographic_theme!r}")
    if s.cut_frequency not in CUT_FREQUENCIES:
        raise StyleError(f"cut_frequency must be one of {CUT_FREQUENCIES}")
    if s.sfx_intensity not in SFX_INTENSITIES:
        raise StyleError(f"sfx_intensity must be one of {SFX_INTENSITIES}")
    if s.camera_movement not in CAMERA_MOVEMENTS:
        raise StyleError(f"camera_movement must be one of {CAMERA_MOVEMENTS}")
    if s.map_style not in MAP_STYLES:
        raise StyleError(f"map_style must be one of {MAP_STYLES}")
    if s.target_shot_seconds <= 0:
        raise StyleError("target_shot_seconds must be positive")
    try:
        from uvs.motion import get_easing
        get_easing(s.easing_language)
    except KeyError as exc:
        raise StyleError(str(exc)) from exc
    s.safe_area.validate()


STYLES: dict[str, VideoStyle] = {
    "cinematic_documentary": VideoStyle(
        name="cinematic_documentary", narrative_structure="hook_context_conflict_revelation_payoff",
        shot_duration_strategy="measured", target_shot_seconds=3.2, cut_frequency="low",
        transition_policy="dissolve_on_emotion", typography="documentary_minimal",
        camera_movement="subtle", easing_language="ease_in_out", animation_intensity="standard",
        visual_effects=frozenset({"vignette", "film_grain"}), color_grade="documentary_natural",
        color_intensity="cinematic", broll_preference="observational", music_direction="reflective",
        sfx_intensity="low", map_style="documentary", infographic_theme="dark"),
    "emotional_storytelling": VideoStyle(
        name="emotional_storytelling", narrative_structure="hook_context_conflict_revelation_payoff",
        shot_duration_strategy="lingering", target_shot_seconds=3.6, cut_frequency="low",
        transition_policy="slow_dissolve", typography="emotional_storytelling",
        camera_movement="subtle", easing_language="ease_in_out", animation_intensity="subtle",
        visual_effects=frozenset({"vignette"}), color_grade="soft_romantic_v2",
        color_intensity="standard", broll_preference="intimate", music_direction="reflective",
        sfx_intensity="low", map_style="none", infographic_theme="dark"),
    "modern_lifestyle": VideoStyle(
        name="modern_lifestyle", narrative_structure="hook_context_conflict_revelation_payoff",
        shot_duration_strategy="brisk", target_shot_seconds=2.2, cut_frequency="medium",
        transition_policy="clean_cuts", typography="clean_modern", camera_movement="dynamic",
        easing_language="ease_out", animation_intensity="standard",
        visual_effects=frozenset({"glow"}), color_grade="warm_lifestyle_v2",
        color_intensity="standard", broll_preference="aspirational", music_direction="inspirational",
        sfx_intensity="medium", map_style="none", infographic_theme="light"),
    "psychology_explainer": VideoStyle(
        name="psychology_explainer", narrative_structure="question_explanation_evidence_conclusion",
        shot_duration_strategy="measured", target_shot_seconds=2.8, cut_frequency="medium",
        transition_policy="clean_cuts", typography="clean_modern", camera_movement="subtle",
        easing_language="ease_in_out", animation_intensity="standard",
        visual_effects=frozenset({"vignette"}), color_grade="desaturated_emotional_v2",
        color_intensity="standard", broll_preference="metaphorical", music_direction="reflective",
        sfx_intensity="low", map_style="none", infographic_theme="dark"),
    "educational_shorts": VideoStyle(
        name="educational_shorts", narrative_structure="question_explanation_evidence_conclusion",
        shot_duration_strategy="punchy", target_shot_seconds=1.8, cut_frequency="high",
        transition_policy="clean_cuts", typography="educational", camera_movement="dynamic",
        easing_language="ease_out", animation_intensity="dynamic",
        visual_effects=frozenset(), color_grade="bright_educational_v2", color_intensity="standard",
        broll_preference="illustrative", music_direction="educational", sfx_intensity="medium",
        map_style="minimal", infographic_theme="light"),
    "viral_storytelling": VideoStyle(
        name="viral_storytelling", narrative_structure="hook_context_conflict_revelation_payoff",
        shot_duration_strategy="punchy", target_shot_seconds=1.5, cut_frequency="high",
        transition_policy="hard_cuts", typography="bold_shorts", camera_movement="kinetic",
        easing_language="overshoot", animation_intensity="dynamic",
        visual_effects=frozenset({"glow"}), color_grade="high_contrast_editorial",
        color_intensity="dynamic", broll_preference="high_energy", music_direction="inspirational",
        sfx_intensity="high", map_style="none", infographic_theme="dark"),
    "minimal_premium": VideoStyle(
        name="minimal_premium", narrative_structure="hook_context_conflict_revelation_payoff",
        shot_duration_strategy="measured", target_shot_seconds=3.0, cut_frequency="low",
        transition_policy="clean_cuts", typography="clean_modern", camera_movement="subtle",
        easing_language="ease_in_out", animation_intensity="subtle",
        visual_effects=frozenset(), color_grade="neutral_commercial", color_intensity="subtle",
        broll_preference="restrained", music_direction="neutral", sfx_intensity="low",
        map_style="none", infographic_theme="light"),
    "investigative_documentary": VideoStyle(
        name="investigative_documentary", narrative_structure="setup_tension_twist_resolution",
        shot_duration_strategy="measured", target_shot_seconds=3.0, cut_frequency="medium",
        transition_policy="dip_to_black", typography="documentary_minimal", camera_movement="subtle",
        easing_language="ease_in_out", animation_intensity="cinematic",
        visual_effects=frozenset({"vignette", "film_grain"}), color_grade="dark_investigative_v2",
        color_intensity="cinematic", broll_preference="evidentiary", music_direction="suspense",
        sfx_intensity="medium", map_style="route_focus", infographic_theme="dark"),
    "travel_story": VideoStyle(
        name="travel_story", narrative_structure="hook_context_conflict_revelation_payoff",
        shot_duration_strategy="brisk", target_shot_seconds=2.4, cut_frequency="medium",
        transition_policy="dissolve_on_emotion", typography="cinematic", camera_movement="dynamic",
        easing_language="ease_out", animation_intensity="standard",
        visual_effects=frozenset({"glow", "vignette"}), color_grade="warm_lifestyle_v2",
        color_intensity="cinematic", broll_preference="scenic", music_direction="inspirational",
        sfx_intensity="medium", map_style="route_focus", infographic_theme="light"),
    "motion_graphics_explainer": VideoStyle(
        name="motion_graphics_explainer", narrative_structure="question_explanation_evidence_conclusion",
        shot_duration_strategy="punchy", target_shot_seconds=2.0, cut_frequency="high",
        transition_policy="clean_cuts", typography="clean_modern", camera_movement="kinetic",
        easing_language="overshoot", animation_intensity="dynamic",
        visual_effects=frozenset({"glow"}), color_grade="neutral_commercial",
        color_intensity="standard", broll_preference="graphic", music_direction="educational",
        sfx_intensity="medium", map_style="minimal", infographic_theme="dark"),
}

# Validate every preset at import so a malformed preset fails loudly.
for _s in STYLES.values():
    validate_style(_s)

STYLE_NAMES = tuple(STYLES)


@dataclass(frozen=True)
class StyleLock:
    """A style locked for a whole project. Hands out the same config for every scene (fixes D-01)."""
    style: VideoStyle

    @classmethod
    def resolve(cls, name: str) -> "StyleLock":
        if name not in STYLES:
            raise StyleError(f"unknown style {name!r}; choose from {STYLE_NAMES}")
        return cls(STYLES[name])

    def look_filter(self) -> str:
        return self.style.look_filter()

    def caption_style_name(self) -> str:
        return self.style.typography

    def scene_config(self, scene_index: int, scene: dict | None = None) -> dict:
        """Deterministic per-scene config. Every scene gets the locked style; nothing from scene 0."""
        return {
            "style": self.style.name,
            "color_grade": self.style.color_grade,
            "color_intensity": self.style.color_intensity,
            "caption_style": self.style.typography,
            "target_shot_seconds": self.style.target_shot_seconds,
            "transition_policy": self.style.transition_policy,
            "camera_movement": self.style.camera_movement,
            "easing": self.style.easing_language,
            "animation_intensity": self.style.animation_intensity,
            "music_direction": self.style.music_direction,
            "sfx_intensity": self.style.sfx_intensity,
            "scene_index": scene_index,
        }

    def signature(self) -> str:
        """A stable string identifying the locked style, for determinism checks."""
        d = self.style.to_dict()
        return "|".join(f"{k}={d[k]}" for k in sorted(d) if k != "safe_area")
