# Style system (Phase 10) — public interface

Status: VERIFIED. Ten full editing presets, Style Lock, validation, D-01 fixed.

## Presets (`uvs.styles.STYLES`)
Ten `VideoStyle` presets: cinematic_documentary, emotional_storytelling, modern_lifestyle, psychology_explainer, educational_shorts, viral_storytelling, minimal_premium, investigative_documentary, travel_story, motion_graphics_explainer.

Each defines: narrative_structure, shot_duration_strategy, target_shot_seconds, cut_frequency, transition_policy, typography (caption style), camera_movement, easing_language, animation_intensity, visual_effects, color_grade (look), color_intensity, broll_preference, music_direction (emotion), sfx_intensity, map_style, infographic_theme, safe_area.

- `validate_style(style)` raises `StyleError` on any inconsistent field. All presets validate at import.
- `VideoStyle.caption_style()`, `.look_filter()`, `.sound_direction()`, `.to_dict()`.

## Style Lock (`uvs.styles.StyleLock`)
- `StyleLock.resolve(name)` — one preset for a whole project.
- `.scene_config(i)` — identical locked config for every scene (does not depend on scene 0; fixes D-01).
- `.look_filter()`, `.caption_style_name()`, `.signature()` (deterministic).

## Pipeline integration
- `spec["style"] = "<preset>"` locks the style; the grade uses the locked look for every scene.
- Without a style, the pipeline falls back to the legacy scene-0 look and records it as a fallback.

## Limits
- Policy fields (cut frequency, b-roll preference) are recorded; the Phase 11 decision engine consumes them. Grade, caption and look are enforced now.
