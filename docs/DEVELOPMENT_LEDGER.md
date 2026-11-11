# Development ledger

## Current state
- Branch: `initial-pipeline`. Local commits ahead of `origin/initial-pipeline` (`e84a7c7`): `ea0dc39` (Phase 1), `2528e21` (Phase 2), `f8b0943` (Phase 3), `efb508c` (Phase 4), and the Phase 5 commit (the newest local commit). **Not pushed.** Push needs explicit authorisation (fast-forward only; verify with `git ls-remote`).
- Current phase: **10** (styles), not started. Phases 2–9 are **PARTIAL**.
- Blocked: editor repo audit and Phase 12 integration (repo not named). See `INTEGRATION_STATUS.md`.
- Full suite: 447 tests OK, 4 skipped (real-data map tests need `UVS_NATURAL_EARTH_SHP`). (`python3 -m unittest discover -s tests -t .`, about 120 s).

## Phase status
| Phase | Status | Summary |
|---|---|---|
| 0 Repository audit | VERIFIED | Audit docs in `docs/audit/`. Editor audit deferred until the repo is named. |
| 1 Core architecture | PARTIAL | Versioned project format, scene graph, undoable edit ops, asset registry and cache, render backend. Scene graph is not rendered yet. |
| 2 AI director / narrative | PARTIAL | Rule-based planner (`uvs/narrative.py`). Lexicons are English-focused. No language model. |
| 3 Media intelligence | PARTIAL | Sidecar tags, lexical retrieval with explained scores, licence gate, scene B-roll assignment, video scene-cut rate, metric cache, CLI. No embeddings. |
| 4 Motion engine | PARTIAL | Keyframes on scene-graph node transforms; shape, image and group nodes rendered to frames and MP4. Text, video, mask and camera not rendered. |
| 5 Animated maps | PARTIAL | Natural Earth 110 m countries, equirectangular and Mercator projections, great-circle routes, markers, camera moves. No labels or choropleths. Data not bundled. |
| 6 Infographics | PARTIAL | 10 chart kinds, 6 timeline kinds, 7 diagram kinds (overlap-checked), 8 metaphors, animation controls, timeline integration. |
| 7 Speech & captions | PARTIAL | Interfaces + capability detection, model-free TTS, silence/segmentation, 7 caption styles, typography, QA, Vietnamese. Real ASR/TTS BLOCKED. |
| 8 Sound design | PARTIAL | Voice chain (EQ, de-ess), tempo/beat detection (within 5% on clicks), beat-aligned cuts, emotional direction, gain automation, audio QA (LUFS, TP, clipping). |
| 9 Colour & VFX | PARTIAL | Colour primitives, numpy frame analysis, shot matching, 20 looks, compositing builders, colour QA. No keyframed masks. |
| 10–15 | NOT_STARTED | See `PHASE_STATUS.json`. |

## Phase 3 changed files
- `uvs/media_index.py`: sidecar `tags` and `description`; `motion_per_second`; metric cache (`index_file`/`scan` take `cache_dir`); `rank(require_known_licence=...)`.
- `uvs/retrieval.py` (new): lexical search, synonym groups, plan B-roll assignment, CLI.
- `tests/unit/test_retrieval.py` (new, 20 tests), `tests/render/test_media_motion.py` (new, 10 tests: motion on real clips, cache, CLI).
- `docs/api/media-retrieval.md`, `docs/PHASE_STATUS.json`, `docs/DECISIONS.md` (DEC-017..019), `docs/KNOWN_LIMITATIONS.md`, `README.md`.

## Phase 9 changed files
- `uvs/color.py` (new), `uvs/grade.py` (10 spec-named looks added), `schemas/effect.schema.json` (look enum).
- `tests/unit/test_color.py` (16), `tests/render/test_color_phase9.py` (5).
- `docs/api/color.md`, DEC-033..034, capability matrix Phase 9 rows.

## Phase 8 changed files
- `uvs/audio_intel.py` (new), `uvs/audio.py` (EQ + de-ess in voice chain).
- `tests/unit/test_audio_intel.py` (13), `tests/render/test_audio_phase8.py` (8).
- `docs/api/audio.md`, DEC-031..032, capability matrix Phase 8 rows.

## Phase 7 changed files
- `uvs/speech.py` (new), `uvs/typography.py` (new), `uvs/captions.py` (3 styles + background field, ASS BorderStyle).
- `tests/unit/test_speech.py` (18), `tests/unit/test_caption_styles.py` (14), `tests/render/test_captions_phase7.py` (3).
- `docs/api/speech-captions.md`, DEC-028..030, capability matrix Phase 7 rows (caption styles now 7/7).

## Phase 6 changed files
- `uvs/infographics.py` (charts), `uvs/explainers.py` (timelines, diagrams, metaphors), `uvs/visuals.py` (controls + timeline integration).
- `tests/unit/test_infographics.py` (21), `tests/unit/test_explainers.py` (19), `tests/unit/test_visuals.py` (10), `tests/render/test_infographics_render.py` (10 incl. 4 skip without ffmpeg).
- `docs/api/infographics.md`, DEC-024..027, capability matrix Phase 6 rows.

## Phase 5 changed files
- `uvs/maps.py` (new), `uvs/animate.py` (encode_frames factored out).
- `tests/unit/test_maps.py` (new, 27 tests), `tests/render/test_maps_render.py` (new, 6 tests; real-data ones skip without `UVS_NATURAL_EARTH_SHP`).
- `examples/map_demo/demo.py`, `docs/api/map-engine.md`, DEC-022..023, `requirements.txt` (pyshp).

## Phase 4 changed files
- `uvs/animate.py` (new): Animation spec, pose, FrameRenderer, render_frame, render_video, CLI.
- `tests/unit/test_animate.py` (new, 21 tests), `tests/render/test_animate_render.py` (new, 4 tests).
- `examples/motion_demo/` (scene and animation specs, README), `docs/api/motion-engine.md`, DEC-020..021.

## Phase 2 changed files
- `uvs/narrative.py`, `tests/unit/test_narrative.py` (36 tests), `examples/narrative_demo/`, `docs/api/narrative.md`.

## Dependencies
- Python 3.13.18, Pillow 12.3.0, ffmpeg 6.1.1, jsonschema 4.26.0 (runtime, for project validation).
- No speech, TTS, or embedding model is installed. Downloading one needs authorisation.
- `gh` is not authenticated in the sandbox. Pushes use the sandbox git proxy.

## Decisions
See `docs/DECISIONS.md`.

## Known blockers
1. Editor repo not identified. Phase 0 editor audit and Phase 12 direct integration wait for the user to name it.
2. Phase 7 speech recognition and TTS: no engine or model installed. Model downloads need authorisation.
3. Push of local commits to `initial-pipeline` needs fresh authorisation.
4. The master prompt was truncated in what was received (Phases 1–15 spec ends mid-Phase-0). Work follows the phase titles and the user's stated constraints.

## Next executable tasks
1. Phase 10: ten full editing presets (not just LUTs) with all required fields; Style Lock; fix D-01 (style lock uses scene 0's look) in pipeline.py.
2. Phase 11 decision engine, Phase 12 SDK, Phase 13 export, Phase 14 QA, Phase 15 demos.
