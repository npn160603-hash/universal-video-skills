# Capability matrix

Updated after the second build pass. Earlier Phase 0 notes are kept at the end.

## Environment (as tested)
- Linux, Python 3.13, ffmpeg/ffprobe 6.1.1 (libx264, libx265, aac, libass, xfade, sidechaincompress, loudnorm,
  alimiter, afftdn, lut3d, signalstats, blackdetect, freezedetect, silencedetect, volumedetect, ebur128, gradients).
- Python packages: Pillow 12.3, jsonschema 4.26 (tests only).
- Not available: a TTS engine, speech-to-text, real footage, real narration, licensed map data.
- An existing editor repo was not connected. The project is standalone.

## Status legend
`Done` = implemented and covered by a passing test on real output (or a pure-logic test where noted).
`Partial` = some of the feature works; the rest is listed. `Missing` = not implemented.

## Matrix

| Feature (master prompt section) | Status | Where | Test |
|---|---|---|---|
| Phase 0 audit of an existing editor repo (§1) | Missing | — | — (no editor repo connected) |
| Capability matrix and integration plan (§1) | Done | this file | — |
| Caption segmentation, measured layout, ASS/SRT/VTT, validation (§8) | Done | `uvs/captions.py` | `tests/unit/test_captions.py` |
| Vietnamese Unicode, NFC normalization (§8) | Done | `uvs/captions.py` | demo words include NFD input; frames checked |
| Keyword highlight, keyword pop (§8) | Done | `uvs/captions.py` | `ExportTests` |
| Caption styles (§8) | Partial | 4 of 7 named styles | demo build |
| Speech-to-text, speaker-aware styles, extra languages (§8) | Missing | — | — |
| Video QA technical checks (§16) | Done | `uvs/qa.py` | `tests/render/test_pipeline.py` |
| Black, frozen, silence, clipping, true peak, loudness (§16) | Done | `uvs/qa.py` | `tests/render/test_pipeline.py`, parser tests |
| Flicker, blur, bad crop, aspect errors, voice/music balance (§16) | Missing | — | — |
| Creative quality scores (§16) | Missing | — | — |
| Render: synthetic base + libass burn-in, 9:16 H.264/AAC (§13) | Done | `uvs/render.py` | `tests/render/test_pipeline.py` |
| Render: 16:9 and 1:1 output (§13) | Partial | width/height arguments | not run |
| Render: 4K, H.265, GPU, cache, incremental render (§13) | Missing | — | — |
| Deterministic output (§13) | Partial | metadata stripped, bitexact not set | not verified |
| Director: scenes, pacing, transitions, music level, SFX rules, decision record (§2, §12) | Partial | `uvs/director.py` | `tests/unit/test_director.py` (13) |
| Director: genre-specific narrative analysis, LLM reasoning (§2) | Missing | — | — |
| Timeline: frame-accurate model, validation, JSON (§3.1) | Done | `uvs/timeline.py` | `tests/unit/test_timeline.py` (11) |
| Timeline: video, audio, overlay tracks rendered (§3.1) | Partial | `uvs/timeline.py` | `tests/render/test_timeline_render.py` |
| Timeline: subtitle and keyframe tracks rendered (§3.1) | Missing | validated, not rendered | — |
| Transitions: cut, dissolve, dip to black (§3.4) | Done | `uvs/timeline.py` | `tests/render/test_timeline_render.py` (pixel checks) |
| Transitions: whip, zoom, mask, light sweep, wipes, speed ramp (§3.4) | Missing | — | — |
| Editing techniques: J/L cuts, match cuts, B-roll insertion (§3.2–3.3) | Missing | — | — |
| Motion: easings, cubic bezier, spring, elastic, bounce, overshoot, damped (§4.1) | Done | `uvs/motion.py` | `tests/unit/test_motion.py` (18) |
| Motion: keyframe tracks, frame sampling (§4.1) | Done | `uvs/motion.py` | `tests/unit/test_motion.py` |
| Motion: transform hierarchy, masks, camera, parallax (§4.1, §4.4–4.5) | Missing | — | — |
| Motion graphics: lower thirds, callouts, statistics, quote cards (§4.2) | Missing | — | — |
| Text: keyword pop and fades (§4.3) | Partial | ASS tags in captions | captions tests |
| Colour: named looks, intensity, LUT path (§5.1–5.2) | Partial | `uvs/grade.py` | `tests/render/test_grade.py` (9) |
| Colour: white balance, curves, skin protection, shot matching (§5.1) | Missing | — | — |
| Audio: highpass, compression, optional denoise (§5.3) | Partial | `uvs/audio.py` | `tests/render/test_audio.py` |
| Audio: sidechain ducking under voice (§5.3, §9) | Done | `uvs/audio.py` | `test_ducking_lowers_music_under_voice_by_several_db` |
| Audio: two-pass loudness target, true-peak limiter (§5.3) | Done | `uvs/audio.py` | `test_mix_hits_loudness_target_and_limits_true_peak` |
| Audio: per-scene loudness and music automation (§9) | Missing | plan level only | — |
| Audio: real speech enhancement, source separation (§5.3) | Missing | — | — |
| Maps and animated routes (§6) | Missing | no offline geodata available | — |
| Charts: bar chart with eased animation, source required (§7) | Partial | `uvs/charts.py` | `tests/render/test_charts_media.py` |
| Charts: line, pie, counters, timelines, comparisons (§7) | Missing | — | — |
| Media index: metadata, provenance, duplicates (§10) | Partial | `uvs/media_index.py` | `tests/render/test_charts_media.py` |
| Media: ranking and diverse picking (§10) | Partial | `uvs/media_index.py` | same |
| Media: semantic search, motion scoring, subject tracking (§10) | Missing | — | — |
| Style presets: the 10 required presets (§11: Cinematic Documentary, Viral Storytelling, etc.) | Missing | the 10 colour looks in `uvs/grade.py` have different names and define colour only | — |
| Style lock: one look held across the whole timeline (§11) | Partial | `uvs/pipeline.py` | pipeline e2e |
| Style presets: typography, transition policy, camera, graphic density (§11) | Missing | — | — |
| JSON schemas: project, scene, timeline, animation, effect (§14) | Done | `schemas/` | `tests/unit/test_schemas.py` (8) |
| End-to-end pipeline with stage timings and report (§15, §20) | Partial | `uvs/pipeline.py` | `tests/render/test_pipeline_e2e.py` (5) |
| Intermediate inspection and manual override (§15) | Partial | JSON plan and timeline files written | — |
| Demos 1–4 with real footage and narration (§17) | Not produced | needs real footage, voice, licensed data | — |

## Phase status (§18)
- Phase 0 (audit): partial. Sandbox audited. No editor repo.
- Phase 1 (core editing): partial. Timeline with cut, dissolve, dip to black; captions; baseline render.
- Phase 2 (motion): partial. Easing and keyframes are done. Motion graphics are not.
- Phase 3 (storytelling): partial. Director rules and media index are done. Semantic selection and B-roll are not.
- Phase 4 (post-production): partial. Looks, LUT path, audio mix, ducking, and loudness are done.
- Phase 5 (advanced visuals): partial. Bar chart only. No maps.
- Phase 6 (automation): partial. Pipeline runs end to end on the demo. Interactive override is not built.
- Phase 7 (QA): partial. Technical and audio QA are done. Visual defect checks are not.

## Known limits
- The demo uses synthetic footage (gradients), synthetic voice (one tone per word), synthetic music, and a synthetic impact. None is real speech or footage.
- Demo word timings are hand-authored, not matched to any narration.
- The demo's integrated loudness and levels come from the synthetic tones. They show the chain works, not that a mix is well balanced.

## Earlier Phase 0 notes
- Editor repo: not connected. No code from any other project was used.
- Sandbox: ffmpeg 6.1.1 with the filters above. Node 22. Python 3.13.18. Pillow 12.3.0.
