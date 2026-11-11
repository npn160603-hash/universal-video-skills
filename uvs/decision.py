"""AI editing decision engine (Phase 11).

Consumes a narrative plan, a locked style, the available media, voice timing, the video format,
the target duration and the render capabilities, and produces one scored EditDecision per scene plus
an executable list of timeline instructions. Every scene carries a decision record: what was chosen,
why, the alternatives, the parameters, a relevance score, a confidence and the technical limits.

Critical editing rules are enforced, not just listed: effects need a narrative reason, irrelevant
footage is dropped, long pauses are preserved, repeated camera moves are varied, transitions are
capped, and an over-budget scene is simplified. Manual overrides replace chosen fields and survive
regeneration, so a user edit is not lost when the timeline is rebuilt.
"""
from __future__ import annotations

from dataclasses import dataclass, field, asdict
from fractions import Fraction
from typing import Any

from uvs.styles import StyleLock, VideoStyle
from uvs.audio_intel import sound_direction


DECISION_FIELDS = ("shot_duration_s", "broll", "visual_composition", "camera_animation",
                   "motion_graphics", "map_usage", "chart_usage", "transition", "caption_style",
                   "music_behavior", "sound_effects", "color_grading")

SCORE_CRITERIA = ("narrative_relevance", "emotional_relevance", "visual_clarity",
                  "media_appropriateness", "scene_continuity", "motion_consistency",
                  "audio_readability", "style_coherence", "render_feasibility")

GENERATED_VISUALS = {"chart", "graphics", "text_emphasis", "negative_space", "map"}


class DecisionError(ValueError):
    pass


@dataclass
class Capabilities:
    maps: bool = True
    charts: bool = True
    audio: bool = True
    broll_library: bool = False   # is real footage available?
    max_transition_fraction: float = 0.5   # at most this fraction of cuts may be dissolves


@dataclass
class EditContext:
    plan: dict
    style: StyleLock
    width: int = 1080
    height: int = 1920
    fps: int = 30
    target_duration: float | None = None
    capabilities: Capabilities = field(default_factory=Capabilities)
    media_matches: dict[str, float] = field(default_factory=dict)  # scene_id -> best b-roll score
    broll_min_score: float = 0.3

    def validate(self) -> None:
        if not self.plan.get("scenes"):
            raise DecisionError("plan has no scenes")
        if self.fps <= 0 or self.width <= 0 or self.height <= 0:
            raise DecisionError("bad video format")


@dataclass
class EditDecision:
    scene_id: str
    selected: dict
    reason: str
    alternatives: list[str]
    parameters: dict
    relevance_score: float
    scores: dict
    confidence: float
    uncertainty: list[str]
    technical_limitations: list[str]
    overridden_fields: list[str] = field(default_factory=list)

    def to_dict(self) -> dict:
        return asdict(self)


# ---------------------------------------------------------------------------
# Scoring
# ---------------------------------------------------------------------------

def _score_scene(scene: dict, selected: dict, ctx: EditContext) -> dict:
    style = ctx.style.style
    emotion = scene.get("narrative_emotion", "neutral")
    attention = scene.get("attention", {})
    over = bool(attention.get("over_budget"))
    load = float(attention.get("load", 0.0))
    budget = float(attention.get("budget", 2.0)) or 2.0

    media_ok = 1.0
    if selected["broll"] == "footage":
        media_ok = min(1.0, ctx.media_matches.get(scene["id"], 0.0) / max(ctx.broll_min_score, 1e-6))

    scores = {
        "narrative_relevance": 0.9 if scene.get("turning_point") else 0.75,
        "emotional_relevance": 0.6 + 0.1 * (emotion != "neutral") + 0.2 * (emotion in
                               {"grief", "tension", "hope", "reflection", "joy"}),
        "visual_clarity": max(0.2, 1.0 - max(0.0, load - budget) / budget) if over else
                          max(0.4, 1.0 - load / (2 * budget)),
        "media_appropriateness": media_ok,
        "scene_continuity": 0.8,   # adjusted below for repeated camera
        "motion_consistency": 0.85,
        "audio_readability": 0.9 if selected["music_behavior"] != "loud" else 0.6,
        "style_coherence": 1.0,    # decisions are derived from the locked style
        "render_feasibility": 1.0,
    }
    if selected["map_usage"] and not ctx.capabilities.maps:
        scores["render_feasibility"] = 0.0
    if selected["chart_usage"] and not ctx.capabilities.charts:
        scores["render_feasibility"] = min(scores["render_feasibility"], 0.0)
    return {k: round(min(1.0, max(0.0, v)), 3) for k, v in scores.items()}


# ---------------------------------------------------------------------------
# Per-scene decision
# ---------------------------------------------------------------------------

def _base_selection(scene: dict, ctx: EditContext, prev_camera: str | None) -> tuple[dict, list[str], list[str]]:
    style: VideoStyle = ctx.style.style
    reasons: list[str] = []
    limits: list[str] = []
    visual = scene.get("visual")
    if isinstance(visual, dict):
        visual = visual.get("selected", "medium")
    emotion = scene.get("narrative_emotion", "neutral")
    attention = scene.get("attention", {})
    over = bool(attention.get("over_budget"))

    # shot duration: the narrative target, nudged toward the style's target
    narr = float(scene.get("target_shot_seconds", style.target_shot_seconds))
    shot_s = round((narr + style.target_shot_seconds) / 2, 2)

    # b-roll vs generated visual
    is_generated = visual in GENERATED_VISUALS
    match = ctx.media_matches.get(scene["id"], 0.0)
    if is_generated:
        broll = "none"
    elif ctx.capabilities.broll_library and match >= ctx.broll_min_score:
        broll = "footage"
        reasons.append(f"b-roll footage (match {match:.2f})")
    else:
        broll = "generated"
        if not ctx.capabilities.broll_library:
            limits.append("no footage library; using generated visual")
        elif match < ctx.broll_min_score:
            # critical rule: no irrelevant footage
            reasons.append(f"footage match {match:.2f} below {ctx.broll_min_score}; not used")

    # camera: style default, varied if it repeats the previous scene (avoid repetitive camera)
    camera = style.camera_movement
    if prev_camera == camera and camera not in ("static",):
        camera = "subtle" if camera != "subtle" else "static"
        reasons.append("camera varied to avoid repetition")

    # motion graphics only with a narrative reason (turning point, or informational visual)
    motion_graphics = bool(scene.get("turning_point")) or visual in {"chart", "graphics"}

    map_usage = (visual == "map") and style.map_style != "none"
    chart_usage = (visual == "chart")

    transition = scene.get("transition", "cut")

    # music behaviour from the style's emotional direction and the scene's music level
    direction = sound_direction(style.music_direction)
    level = float(scene.get("music_level", 0.3))
    pause_heavy = emotion in {"reflection", "grief"} and level < 0.25
    music = "silent" if pause_heavy else ("soft" if level < 0.45 else "present")

    sfx = "none" if style.sfx_intensity == "none" or pause_heavy else style.sfx_intensity

    selected = {
        "shot_duration_s": shot_s,
        "broll": broll,
        "visual_composition": visual,
        "camera_animation": camera,
        "motion_graphics": motion_graphics,
        "map_usage": map_usage,
        "chart_usage": chart_usage,
        "transition": transition,
        "caption_style": style.typography,
        "music_behavior": music,
        "sound_effects": sfx,
        "color_grading": style.color_grade,
    }
    return selected, reasons, limits


def _apply_critical_rules(scene: dict, selected: dict, ctx: EditContext,
                          dissolve_budget: list[int]) -> list[str]:
    notes: list[str] = []
    attention = scene.get("attention", {})
    # over-budget scene: prefer readable graphics — drop motion graphics, simplify
    if attention.get("over_budget"):
        if selected["motion_graphics"]:
            selected["motion_graphics"] = False
            notes.append("dropped motion graphics: scene is over attention budget")
    # effects need a narrative reason: neutral, non-turning scene gets no decorative motion graphics
    if (selected["motion_graphics"] and not scene.get("turning_point")
            and scene.get("narrative_emotion", "neutral") == "neutral"
            and selected["visual_composition"] not in {"chart", "graphics"}):
        selected["motion_graphics"] = False
        notes.append("dropped motion graphics: no narrative purpose")
    # avoid excessive transitions: cap dissolves
    if selected["transition"] in {"dissolve", "dip_black"}:
        if dissolve_budget[0] <= 0:
            selected["transition"] = "cut"
            notes.append("transition reduced to cut: dissolve budget exhausted")
        else:
            dissolve_budget[0] -= 1
    # capability gating
    if selected["map_usage"] and not ctx.capabilities.maps:
        selected["map_usage"] = False
        selected["visual_composition"] = "graphics"
        notes.append("map disabled: renderer cannot draw maps")
    if selected["chart_usage"] and not ctx.capabilities.charts:
        selected["chart_usage"] = False
        notes.append("chart disabled: renderer cannot draw charts")
    return notes


def decide_scene(scene: dict, ctx: EditContext, *, prev_camera: str | None = None,
                 dissolve_budget: list[int] | None = None,
                 override: dict | None = None) -> EditDecision:
    selected, reasons, limits = _base_selection(scene, ctx, prev_camera)
    if dissolve_budget is None:
        dissolve_budget = [999]
    rule_notes = _apply_critical_rules(scene, selected, ctx, dissolve_budget)
    reasons.extend(rule_notes)

    overridden: list[str] = []
    if override:
        for k, v in override.items():
            if k not in DECISION_FIELDS:
                raise DecisionError(f"override targets unknown field {k!r}")
            selected[k] = v
            overridden.append(k)
        reasons.append(f"manual override: {', '.join(sorted(overridden))}")

    scores = _score_scene(scene, selected, ctx)
    relevance = round(sum(scores.values()) / len(scores), 3)

    decision = scene.get("decision", {})
    alternatives = []
    vis = scene.get("visual")
    if isinstance(vis, dict):
        alternatives = [a.get("shot") if isinstance(a, dict) else str(a)
                        for a in vis.get("rejected_alternatives", [])][:3]

    confidence = round(min(0.95, 0.5 + 0.1 * len([s for s in scores.values() if s >= 0.8])), 3)
    uncertainty = [k for k, v in scores.items() if v < 0.6]

    return EditDecision(
        scene_id=scene["id"], selected=selected,
        reason="; ".join(reasons) if reasons else "style defaults applied",
        alternatives=alternatives,
        parameters={"shot_duration_s": selected["shot_duration_s"],
                    "transition": selected["transition"],
                    "caption_style": selected["caption_style"],
                    "look": selected["color_grading"]},
        relevance_score=relevance, scores=scores, confidence=confidence,
        uncertainty=uncertainty, technical_limitations=limits, overridden_fields=overridden)


# ---------------------------------------------------------------------------
# Whole-plan decision + executable instructions
# ---------------------------------------------------------------------------

@dataclass
class EditPlan:
    decisions: list[EditDecision]
    instructions: list[dict]   # executable timeline instructions
    style: str

    def to_dict(self) -> dict:
        return {"style": self.style, "decisions": [d.to_dict() for d in self.decisions],
                "instructions": self.instructions}


def decide(ctx: EditContext, *, overrides: dict[str, dict] | None = None) -> EditPlan:
    """Decide every scene. overrides maps scene_id -> {field: value} and survives regeneration."""
    ctx.validate()
    overrides = overrides or {}
    scenes = ctx.plan["scenes"]
    n_cuts = max(1, len(scenes) - 1)
    dissolve_budget = [int(n_cuts * ctx.capabilities.max_transition_fraction)]
    decisions: list[EditDecision] = []
    instructions: list[dict] = []
    prev_camera: str | None = None
    frame = 0
    for scene in scenes:
        d = decide_scene(scene, ctx, prev_camera=prev_camera, dissolve_budget=dissolve_budget,
                         override=overrides.get(scene["id"]))
        decisions.append(d)
        prev_camera = d.selected["camera_animation"]
        dur_frames = max(1, int(round(d.selected["shot_duration_s"] * ctx.fps)))
        instructions.append({
            "scene_id": scene["id"],
            "start_frame": frame,
            "duration_frames": dur_frames,
            "source_kind": d.selected["broll"],              # footage | generated | none
            "visual": d.selected["visual_composition"],
            "transition": d.selected["transition"],
            "caption_style": d.selected["caption_style"],
            "look": d.selected["color_grading"],
            "camera": d.selected["camera_animation"],
            "music": d.selected["music_behavior"],
            "sfx": d.selected["sound_effects"],
        })
        frame += dur_frames
    return EditPlan(decisions=decisions, instructions=instructions, style=ctx.style.style.name)


def regenerate(ctx: EditContext, previous: EditPlan, *,
               new_overrides: dict[str, dict] | None = None) -> EditPlan:
    """Rebuild the edit, preserving the overrides already applied in `previous` plus any new ones."""
    merged: dict[str, dict] = {}
    for d in previous.decisions:
        if d.overridden_fields:
            merged[d.scene_id] = {k: d.selected[k] for k in d.overridden_fields}
    for sid, fields in (new_overrides or {}).items():
        merged.setdefault(sid, {}).update(fields)
    return decide(ctx, overrides=merged)
