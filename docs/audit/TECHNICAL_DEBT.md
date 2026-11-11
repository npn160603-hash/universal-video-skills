# Technical debt (Phase 0 audit)

Each item lists the evidence seen in code. Severity: H = blocks correct output or a planned feature; M = quality or maintainability; L = cosmetic.

| ID | Sev | Item | Evidence |
|---|---|---|---|
| D-01 | H | **Style lock applies only the first scene's look.** The plan has a per-scene `color_look`, but the whole timeline gets one look. The decision log still says "applied to every scene". | `uvs/pipeline.py` line 206–210 uses `plan["scenes"][0]["color_look"]`; `director.py:194` sets per-scene `color_look`. | — RESOLVED in Phase 10 (Style Lock; see DEC-035)
| D-02 | H | **No input validation for `spec.json`.** An unknown genre raises a raw KeyError. Footage resolution, fps, and count are not checked against the project. | `pipeline.run` reads `spec["genre"]` and `D.GENRES[...]` with no check. |
| D-03 | M | **Three lossy re-encodes** in the main path (timeline, grade, burn-in). Each adds generation loss. | `T.render`, `G.grade`, `R.burn_captions` each run libx264 at CRF 18. |
| D-04 | M | **Two render paths** (`uvs/render.py` standalone, `pipeline.run`) build base and captions separately. Fixes must be made twice. | `render.py:make_base`, `burn_captions`, `render_captioned` vs `pipeline.run`. |
| D-05 | M | **Schemas are not used at runtime.** Reports and plans are not checked against the schemas in `schemas/`. | `tests/unit/test_schemas.py` tests the schemas; no module imports them for validation. |
| D-06 | M | **Subtitle and keyframe tracks are not rendered**, and overlay tracks are rendered but untested. The model accepts subtitle and keyframe tracks, and validation reports them as not rendered. `motion.Track` is used only by unit tests. | `timeline.py` `RENDERED_KINDS = {"video", "audio", "overlay"}`; `test_keyframe_and_subtitle_tracks_are_reported_as_not_rendered`. |
| D-07 | H | **Font fallback can break measurement.** If `fc-match` is missing, `resolve_font_file` returns None and `_font` uses Pillow's default font, while the burn-in uses the Inter family through libass. Line-width checks would then measure a different font from the one rendered. Not tested. | `uvs/captions.py:138–160`. |
| D-08 | M | **Magic constants with no names or tests:** `music_gain` reference level 0.4, `TAIL_SECONDS`, `true_peak=-1.5` (the QA limit is −1), `duration_tolerance=0.15`, `CRF=18`. | `pipeline.py` `run()`. |
| D-09 | M | **Audio duration is taken from the plan.** The mix is trimmed to `total` and then QA compares it to the same value. The QA check is not independent of the plan. | `pipeline.py` passes `duration=total` into `mix_to_file`; QA gets `expect_duration=total`. |
| D-10 | M | **Demo word timings are hand-authored**, and the voice is one tone per word. Tests of caption timing do not test real speech alignment. | `examples/demo_caption/words.json`. |
| D-11 | M | **Test suite takes 2 minutes** and most of it is ffmpeg rendering. No way to run only fast tests except by choosing the file. | baseline timing. |
| D-12 | M | **No lint, type-check, or CI configuration.** | no config files in the repo. |
| D-13 | L | **Reports have no schema** (`pipeline_report.json`, `qa_report.json`). | see D-05. |
| D-14 | L | **`gh` is not authenticated** in the sandbox. Only the sandbox git proxy can push. | `gh auth status`. |
| D-15 | L | **Dependency pins are loose.** ffmpeg is not pinned; Python version is not pinned; no lock file. | `requirements.txt`. |
| D-16 | L | **Unused packages installed** (numpy, pytest). They do not affect the project but hide missing dependency declarations. | see `DEPENDENCY_INVENTORY.md`. |
| D-17 | L | **Caption and timeline output is not byte-deterministic** (not verified). Output is not compared across runs. | `BASELINE_RESULTS.md` §5. |

## Ordering suggestion for later phases
1. D-01 and D-02 before any new feature that depends on scene decisions or user input.
2. D-03 and D-04 before adding stages or effects, so the render path is not made worse.
3. D-05 and D-13 before any external integration, because the editor needs stable contracts.
4. D-06 before adding motion or subtitle tracks, so the model does not promise what the renderer does not do.
