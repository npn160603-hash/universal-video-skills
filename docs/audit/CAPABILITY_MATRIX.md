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
| Captions | Named styles | VERIFIED | all 7 required styles; each builds valid ASS, rendered (`test_caption_styles.py`, `test_captions_phase7.py`) |
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


## Phase 6 additions

| Area | Capability | Status | Evidence |
|---|---|---|---|
| Infographics | 10 animated chart kinds with validation and metadata | VERIFIED | 21 tests (`test_infographics.py`); pixel checks |
| Infographics | Animated timelines (6 kinds), playhead, dates | VERIFIED | `test_explainers.py` |
| Infographics | Diagram engine (7 kinds), overlap avoidance | VERIFIED | `test_explainers.py`; render refuses overlap |
| Infographics | Visual metaphors (8), illustrative tag | VERIFIED | `test_explainers.py` |
| Infographics | Animation controls (zoom/pan/exit) | VERIFIED | `test_visuals.py` |
| Infographics | Timeline integration of visuals | VERIFIED | `test_infographics_render.py` composes 2 clips |

## Phase 7 additions

| Area | Capability | Status | Evidence |
|---|---|---|---|
| Speech | Capability detection (ASR/TTS engines) | VERIFIED | `test_speech.py` |
| Speech | Model-free TTS (silence, click track) real WAV | VERIFIED | `test_speech.py` word-aligned energy |
| Speech | Silence/VAD via ffmpeg, segmentation | VERIFIED | `test_speech.py`, `test_captions_phase7.py` |
| Speech | External-timestamp fallback | VERIFIED | `test_speech.py` |
| Speech | Real ASR / real speech TTS | BLOCKED | no engine installed; interfaces ready |
| Captions | Typography effects, layout QA, Vietnamese | VERIFIED | `test_caption_styles.py`; frames inspected |

## Phase 8 additions

| Area | Capability | Status | Evidence |
|---|---|---|---|
| Audio | Voice chain (HPF, EQ, compression, de-ess, loudnorm, limiter) | VERIFIED | mix hits -16 LUFS (`test_audio_phase8.py`) |
| Audio | Tempo/beat detection | VERIFIED | within 5% on 90/120/140 BPM clicks |
| Audio | Beat-aligned cuts, gain automation | VERIFIED | `test_audio_intel.py` |
| Audio | Emotional sound direction | VERIFIED | `test_audio_intel.py` |
| Audio | Audio QA (LUFS, TP, clipping, silence, balance) | VERIFIED | real measurements (`test_audio_phase8.py`) |

## Phase 9 additions

| Area | Capability | Status | Evidence |
|---|---|---|---|
| Colour | Primitives (exposure, WB, tint, curves, LGG) | VERIFIED | chains run and change frames (`test_color_phase9.py`) |
| Colour | Frame analysis + shot matching | VERIFIED | distance 78->1.5 on real frames |
| Colour | 20 looks (10 + 10 spec-named) | VERIFIED | all render; schema in sync |
| Colour | Colour QA (sat/crush/clip) | VERIFIED | `test_color.py` |
| Colour | Compositing builders (chroma, blur, glow, vignette, grain, leak) | VERIFIED | glow/chroma run |

## Phase 10 additions

| Area | Capability | Status | Evidence |
|---|---|---|---|
| Styles | 10 full editing presets (all 17 fields) | VERIFIED | `test_styles.py` |
| Styles | Style Lock, deterministic per-scene config | VERIFIED | `test_styles.py` |
| Styles | D-01 fixed (locked style, not scene 0) | VERIFIED | pipeline e2e; `test_styles_phase10.py` |
| Styles | 10 styles grade to distinct looks | VERIFIED | 10/10 distinct signatures |

## Phase 11 additions

| Area | Capability | Status | Evidence |
|---|---|---|---|
| Decision | 12 decisions + 9 scores per scene | VERIFIED | `test_decision.py` |
| Decision | Critical rules enforced | VERIFIED | each rule has a firing test |
| Decision | Decision records (reason, alternatives, confidence) | VERIFIED | `test_decision.py` |
| Decision | Overrides preserved on regeneration | VERIFIED | `test_decision.py` |
| Decision | Real-plan integration | VERIFIED | `test_decision.py` |

## Phase 12 additions

| Area | Capability | Status | Evidence |
|---|---|---|---|
| API | Core API over all capabilities | VERIFIED | `test_api.py` |
| API | Job manager (status/progress/cancel/retry) | VERIFIED | `test_jobs.py` |
| API | Localhost JSON server (loopback only) | VERIFIED | `test_server_sdk.py` |
| API | Python SDK + TypeScript client | VERIFIED | SDK flow tested; TS type-checks |
| API | Reference harness (labelled demo) | VERIFIED | runs full flow |
| API | Direct editor integration | BLOCKED | editor repo not identified |

## Phase 13 additions

| Area | Capability | Status | Evidence |
|---|---|---|---|
| Export | Hardware/encoder detection (verified) | VERIFIED | `test_export_phase13.py`; nvenc excluded without GPU |
| Export | Profiles 9:16/16:9/1:1 x 720p/1080p, H.264/H.265, AAC | VERIFIED | correct dims, decode valid |
| Export | Render cache | VERIFIED | reuse verified (render runs once) |
| Export | Benchmark (duration/size/fps/decode) | VERIFIED | `EXPORT_BENCHMARK.json` |

## Phase 14 additions

| Area | Capability | Status | Evidence |
|---|---|---|---|
| QA | Visual detection (black, frozen) | VERIFIED | detected on broken videos (`test_autoqa_phase14.py`) |
| QA | Timeline QA (gaps/overlaps/durations) | VERIFIED | `test_autoqa.py` |
| QA | Creative heuristics (labelled) | VERIFIED | `test_autoqa.py` |
| QA | Safe repairs (bounded, copy) | VERIFIED | loudness -51.8->-14; original preserved |
| QA | JSON + Markdown reports | VERIFIED | `write_reports` |
