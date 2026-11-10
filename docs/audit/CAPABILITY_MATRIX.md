# Capability matrix (Phase 0 audit)

Audited commit: `08e9aae` on branch `initial-pipeline` (clean working tree, matches `origin/initial-pipeline`).
Detailed per-feature notes: `architecture/capability-matrix.md`. This file applies the audit status legend.

## Status legend
- **VERIFIED**: implemented, and its tests pass on real output where the feature touches media.
- **IMPLEMENTED_UNVERIFIED**: code exists but no test exercises that path.
- **PARTIAL**: some of the feature works; the rest is listed in the row.
- **BLOCKED**: cannot be done with current inputs or access.
- **NOT_IMPLEMENTED**: no code.

## Matrix

| Area | Capability | Status | Evidence |
|---|---|---|---|
| Captions | Segmentation, measured two-line layout, ASS/SRT/VTT export, validation | VERIFIED | 26 unit tests (`test_captions.py`); demo output |
| Captions | Vietnamese text, NFC normalization | VERIFIED | demo words include an NFD word; frames checked |
| Captions | Keyword highlight | VERIFIED | caption unit tests; demo keywords |
| Captions | Named styles | PARTIAL | 4 of 7 required: Documentary Minimal, Cinematic, Bold Shorts, Emotional Storytelling |
| Captions | Clean Modern, Podcast Highlight, Educational styles | NOT_IMPLEMENTED | not in `STYLES` |
| Captions | Speech-to-text, speaker-aware styles, extra languages | NOT_IMPLEMENTED | no ASR installed |
| QA | ffprobe stream checks, decode, A/V duration sync | VERIFIED | `qa_report.json`, 15 pass on demo |
| QA | Black, frozen, silence, clipping, true peak, loudness | VERIFIED | parser unit tests (9); demo measurements |
| QA | Flicker, blur, bad crop, aspect errors, voice/music balance | NOT_IMPLEMENTED | — |
| QA | Creative quality scores | NOT_IMPLEMENTED | — |
| Render | 9:16 H.264 + AAC with caption burn-in | VERIFIED | `test_pipeline.py`, `test_pipeline_e2e.py`, demo |
| Render | 16:9 and 1:1 output | IMPLEMENTED_UNVERIFIED | width/height are parameters; never rendered in tests |
| Render | 4K, H.265, hardware encoders | NOT_IMPLEMENTED | libx265 exists in the sandbox ffmpeg but no code path uses it |
| Render | Deterministic output | IMPLEMENTED_UNVERIFIED | metadata stripped; no bitexact flag; not byte-compared |
| Director | Scene segmentation, pacing, transitions, music level, SFX rule, decision record | PARTIAL | 13 unit tests; rule-based only |
| Director | Genre-specific narrative analysis, LLM reasoning | NOT_IMPLEMENTED | — |
| Timeline | Frame-accurate model, validation, JSON load/save | VERIFIED | 11 unit tests |
| Timeline | Video track rendered | VERIFIED | 2 render tests with pixel checks |
| Timeline | Overlay track rendered (`overlay=` filter) | IMPLEMENTED_UNVERIFIED | code path exists; no test renders an overlay |
| Timeline | Audio track rendered | VERIFIED | `test_audio_clip_is_mixed_at_its_start_frame` |
| Timeline | Cut, dissolve, dip-to-black | VERIFIED | `test_timeline_render.py` |
| Timeline | Subtitle and keyframe tracks rendered | NOT_IMPLEMENTED | validation reports them as not rendered (`test_keyframe_and_subtitle_tracks_are_reported_as_not_rendered`) |
| Timeline | Whip, zoom, mask, wipes, speed ramp, J/L cuts, match cuts, B-roll insertion | NOT_IMPLEMENTED | — |
| Motion | Easings (incl. spring, elastic, bounce, overshoot, damped), cubic bezier | VERIFIED | 18 unit tests |
| Motion | Keyframe tracks | PARTIAL | sampled in unit tests; not used by any renderer |
| Motion | Transform hierarchy, masks, camera, parallax, motion graphics | NOT_IMPLEMENTED | — |
| Grade | 10 colour looks, intensity scaling, LUT path | VERIFIED | 9 render tests on decoded pixels |
| Grade | The 10 required video presets (Cinematic Documentary, Viral Storytelling, etc.) | NOT_IMPLEMENTED | the 10 looks have other names and define colour only |
| Grade | Style lock | PARTIAL | one look (scene 0's) applied to the whole timeline; per-scene looks in the plan are ignored |
| Grade | White balance, curves, skin protection, shot matching | NOT_IMPLEMENTED | — |
| Audio | Sidechain ducking, two-pass loudnorm to −14 LUFS, true-peak limiter | VERIFIED | 9 render tests; demo −13.9 LUFS |
| Audio | Per-scene loudness and music automation | NOT_IMPLEMENTED | plan-level only |
| Audio | Speech enhancement, source separation, denoise | NOT_IMPLEMENTED | `afftdn` available but not used |
| Maps | Animated routes, geodata | NOT_IMPLEMENTED | no offline geodata |
| Charts | Bar chart with eased animation; refuses missing or unsourced data | VERIFIED | `test_charts_media.py`, PNG pixel heights |
| Charts | Line, pie, counters, timelines, comparisons | NOT_IMPLEMENTED | — |
| Media | SHA-256 and dHash duplicate detection, provenance sidecars | VERIFIED | `test_charts_media.py` |
| Media | Ranking and diverse picking | PARTIAL | metadata-based only |
| Media | Semantic search, motion scoring, subject tracking | NOT_IMPLEMENTED | — |
| Schemas | project, scene, timeline, animation, effect | VERIFIED | 8 tests; enums checked against code |
| Schemas | Runtime validation of inputs and outputs | NOT_IMPLEMENTED | schemas are not called by the pipeline |
| Pipeline | End-to-end run, stage timings, stand-in list, report | VERIFIED | `test_pipeline_e2e.py` (5); demo run |
| Pipeline | Input validation of `spec.json` | NOT_IMPLEMENTED | unknown genre raises a raw KeyError |
| Pipeline | Interactive override / manual edit loop | NOT_IMPLEMENTED | intermediate JSON is written but not re-read |
| Editor | Audit of the user's editor repo | BLOCKED | editor repo not identified (see `INTEGRATION_STATUS.md`) |
| Editor | SDK or adapter for the editor | NOT_IMPLEMENTED | — |
| Demos | Demos 1–4 with real footage, narration, licensed data | NOT_IMPLEMENTED | needs real assets |

## Summary counts (counted from the table, 47 rows)
- VERIFIED: 17
- PARTIAL: 5
- IMPLEMENTED_UNVERIFIED: 3
- BLOCKED: 1
- NOT_IMPLEMENTED: 21
