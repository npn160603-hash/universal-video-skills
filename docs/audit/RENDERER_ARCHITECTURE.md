# Renderer architecture (Phase 0 audit)

Describes the code at commit `08e9aae`. Source is the code itself; the README was not used as a reference.

## Module map

| Module | Lines | Role | Key public functions |
|---|---|---|---|
| `uvs/pipeline.py` | 277 | Orchestrates one run end to end | `run`, `build_timeline`, `synth_voice`, `synth_music`, `synth_impact`, `make_synthetic_footage`, `_mux` |
| `uvs/director.py` | 224 | Scenes, pacing, transitions, music level, SFX, decision record | `segment_scenes`, `analyze_scene`, `plan`, `write_plan` |
| `uvs/captions.py` | 539 | Word timing → cues → layout → ASS/SRT/VTT | `load_words`, `segment_words`, `layout_lines`, `build_captions`, `write_outputs`, `validate_cues` |
| `uvs/timeline.py` | 297 | Frame-accurate clip model, validation, ffmpeg filter graph, render | `validate`, `build_filter_graph`, `render`, `load_timeline`, `save_timeline` |
| `uvs/grade.py` | 142 | Colour looks as ffmpeg filter chains, LUT path, colour sampling | `look_filter`, `lut_filter`, `grade`, `sample_rgb` |
| `uvs/audio.py` | 175 | Mix graph with sidechain ducking, two-pass loudnorm, limiter | `build_mix_graph`, `mix_to_file`, `duck_music` |
| `uvs/render.py` | 120 | Standalone captioned clip (base + caption burn-in) | `make_base`, `burn_captions`, `render_captioned` |
| `uvs/qa.py` | 304 | Technical checks; pure parsers for ffmpeg output | `run_qa`, `probe`, `parse_ebur128_summary`, `parse_blackdetect`, … |
| `uvs/motion.py` | 218 | Easing functions and keyframe tracks | `cubic_bezier`, `spring`, `elastic_out`, `bounce_out`, `overshoot`, `damped_oscillation`, `Track` |
| `uvs/media_index.py` | 255 | Asset metadata, duplicates, ranking, sidecars | `index_file`, `scan`, `find_duplicates`, `rank`, `pick_diverse`, `save_index` |
| `uvs/charts.py` | 135 | Bar chart PNG and animated MP4 | `validate`, `compute_layout`, `chart_png`, `chart_video` |
| `schemas/*.json` | — | Data contracts (project, scene, timeline, animation, effect) | not called at runtime |

## Pipeline stages (from `uvs/pipeline.py:run`)

Each stage is timed and recorded in `pipeline_report.json`.

1. **load_words**: read word timings from `spec.json`'s `words` file.
2. **director**: `D.plan(words, genre, title)`. Writes `director_plan.json`.
3. **captions**: `C.build_captions(...)`. Errors abort the run. Writes `captions.ass`, `.srt`, `.vtt`.
4. **synthetic_footage** (only if `spec.footage` is absent): three gradient clips.
5. **timeline**: `build_timeline` puts one clip per scene, then `T.validate`. Errors abort the run.
6. **render_timeline**: `T.render` builds one `filter_complex` (`xfade` for dissolves and `fadeblack` for dip-to-black), writes `timeline.mp4`. **Lossy encode #1** (libx264, CRF 18).
7. **grade**: `G.grade` applies one look from scene 0 to the whole timeline. Writes `graded.mp4`. **Lossy encode #2.**
8. **burn_captions**: `R.burn_captions` adds the ASS subtitles, writes `video_captioned.mp4`. **Lossy encode #3.**
9. **synth_voice / synth_music / synth_impact**: stand-in audio (tone per word, two sine tones, one low impact). Each is recorded as a stand-in.
10. **audio_mix**: `A.mix_to_file`. Measures the input, runs the two-pass loudnorm to −14 LUFS with a −1.5 dBTP limiter, writes `audio_mix.m4a`.
11. **mux**: `_mux` copies both streams (`-c:v copy -c:a copy`) into `final.mp4`. **No re-encode.**
12. **qa**: `Q.run_qa` probes the final file. Writes `qa_report.json`.

## Data flow

```
spec.json ──► words.json ──► director ──► director_plan.json
                 │                │
                 ▼                ▼ (per-scene decisions, transitions, music level)
              captions ──► .ass ──────────────────────────────┐
                                                              │
footage (real or synthetic) ──► timeline.mp4 ──► graded.mp4 ──► video_captioned.mp4 ──► mux ──► final.mp4
                                                                                          ▲
voice / music / impact (real or synthetic) ──► audio_mix.m4a ─────────────────────────────┘
                                                                                          │
                                                                                     qa_report.json
```

## Timeline model

- Times are stored as integer frames at the project's fps.
- Each clip's `start` = previous `start + duration − next.transition_frames`.
- Video, audio, and overlay tracks are rendered (`RENDERED_KINDS`). Overlays use the `overlay=` filter, but no test renders one. Subtitle and keyframe tracks are validated and reported as not rendered.
- `TRANSITIONS = {"cut": None, "dissolve": "fade", "dip_black": "fadeblack"}`.

## Caption model

- `Word` → `Cue` (max 2.8 s soft, 3.4 s hard, with an orphan-word warning).
- `layout_lines` measures text with Pillow using the resolved Inter font. Two lines maximum.
- Output formats: ASS (used for burn-in), SRT, WebVTT.

## Concerns for later phases

- **Three lossy re-encodes** before the final mux. Each re-encode adds generation loss. Phase work that adds stages should consider a single-pass filter graph.
- **Style lock uses the first scene's look.** Per-scene looks in the plan are not applied.
- **Render entry points disagree.** `uvs/render.py` (standalone) and `pipeline.run` each build their own base and caption path.
- **No input validation** for `spec.json` before the pipeline runs.
- **Subtitle and keyframe tracks are validated but not rendered.** Overlays are rendered but untested.
- **Keyframe tracks are not used by any renderer.**
