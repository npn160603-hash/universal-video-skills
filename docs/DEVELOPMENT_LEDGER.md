# Development ledger

## Current state
- Branch: `initial-pipeline`. Local commits ahead of `origin/initial-pipeline` (`e84a7c7`): `ea0dc39` (Phase 1), `2528e21` (Phase 2), and the Phase 3 commit. **Not pushed.** Push needs explicit authorisation (fast-forward only; verify with `git ls-remote`).
- Current phase: **4** (motion engine), not started. Phase 3 is **PARTIAL**.
- Blocked: editor repo audit and Phase 12 integration (repo not named). See `INTEGRATION_STATUS.md`.
- Full suite: 265 tests, OK (`python3 -m unittest discover -s tests -t .`, about 120 s).

## Phase status
| Phase | Status | Summary |
|---|---|---|
| 0 Repository audit | VERIFIED | Audit docs in `docs/audit/`. Editor audit deferred until the repo is named. |
| 1 Core architecture | PARTIAL | Versioned project format, scene graph, undoable edit ops, asset registry and cache, render backend. Scene graph is not rendered yet. |
| 2 AI director / narrative | PARTIAL | Rule-based planner (`uvs/narrative.py`). Lexicons are English-focused. No language model. |
| 3 Media intelligence | PARTIAL | Sidecar tags, lexical retrieval with explained scores, licence gate, scene B-roll assignment, video scene-cut rate, metric cache, CLI. No embeddings. |
| 4–15 | NOT_STARTED | See `PHASE_STATUS.json`. |

## Phase 3 changed files
- `uvs/media_index.py`: sidecar `tags` and `description`; `motion_per_second`; metric cache (`index_file`/`scan` take `cache_dir`); `rank(require_known_licence=...)`.
- `uvs/retrieval.py` (new): lexical search, synonym groups, plan B-roll assignment, CLI.
- `tests/unit/test_retrieval.py` (new, 20 tests), `tests/render/test_media_motion.py` (new, 10 tests: motion on real clips, cache, CLI).
- `docs/api/media-retrieval.md`, `docs/PHASE_STATUS.json`, `docs/DECISIONS.md` (DEC-017..019), `docs/KNOWN_LIMITATIONS.md`, `README.md`.

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
1. Phase 4: motion engine (keyframes, easing, transforms through the scene graph) with tests that compare rendered frames.
2. Fix D-01 (style lock uses scene 0's look) and D-02 (spec validation), which are inside existing scope.
3. Fix D-07 (font fallback mismatch) with a test.
4. Add a render test for overlay tracks (still IMPLEMENTED_UNVERIFIED).
