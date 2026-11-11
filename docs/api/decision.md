# AI editing decision engine (Phase 11) — public interface

Status: VERIFIED. Scored per-scene decisions, enforced critical rules, overrides, executable instructions.

## Inputs (`uvs.decision.EditContext`)
`plan` (narrative plan), `style` (StyleLock), `width/height/fps`, `target_duration`, `capabilities` (Capabilities: maps, charts, audio, broll_library, max_transition_fraction), `media_matches` (scene_id -> best b-roll score), `broll_min_score`.

## Decisions (`decide(ctx, overrides) -> EditPlan`)
Per scene, an `EditDecision` with `selected` (all 12 fields: shot_duration_s, broll, visual_composition, camera_animation, motion_graphics, map_usage, chart_usage, transition, caption_style, music_behavior, sound_effects, color_grading), `scores` (9 criteria), `relevance_score`, `reason`, `alternatives`, `parameters`, `confidence`, `uncertainty`, `technical_limitations`, `overridden_fields`.

`EditPlan.instructions` is an executable list of per-scene timeline instructions (start_frame, duration_frames, source_kind, visual, transition, caption_style, look, camera, music, sfx).

## Critical rules (enforced)
Dissolves capped (max_transition_fraction); irrelevant footage dropped below broll_min_score; over-budget scenes drop motion graphics; neutral non-turning scenes get no decorative effects; repeated camera varied; maps/charts gated by capabilities; reflective quiet scenes keep silence.

## Overrides and regeneration
`decide(ctx, overrides={scene_id: {field: value}})`; `regenerate(ctx, previous, new_overrides)` preserves prior overrides and merges new ones.

## Limits
- Instructions are produced and tested; the pipeline still renders via the director path.
- Uniform scoring weights; caption/subject overlap handled via safe margins, not detection.
