# Development ledger

## Current state
- Branch: `initial-pipeline`. Clean at the start of this pass (HEAD `08e9aae` = `origin/initial-pipeline`).
- Current phase: **0** (repository audit), status **PARTIAL**.
- Blocked: editor repo audit (not identified). See `INTEGRATION_STATUS.md`.
- Phases 1–15: spec text was not in the received prompt. Not started.

## Completed phases
- None fully. Phase 0 is PARTIAL.

## Changed files (this pass)
- `docs/PHASE_STATUS.json` (new)
- `docs/DEVELOPMENT_LEDGER.md` (new)
- `docs/DECISIONS.md` (new)
- `docs/KNOWN_LIMITATIONS.md` (new)
- `docs/INTEGRATION_STATUS.md` (new)
- `docs/audit/CAPABILITY_MATRIX.md` (new)
- `docs/audit/DEPENDENCY_INVENTORY.md` (new)
- `docs/audit/RENDERER_ARCHITECTURE.md` (new)
- `docs/audit/BASELINE_RESULTS.md` (new)
- `docs/audit/TECHNICAL_DEBT.md` (new)

No code files changed in this pass.

## Tests
- Passing: 125 of 125 (`python3 -m unittest discover -s tests -t .`, 117 s). Run against the code at `08e9aae`.
- Failing: none.

## Render outputs
- Demo: `python3 -m uvs.pipeline examples/demo_pipeline/spec.json <out>`. Output is not committed (`out/` is git-ignored).
- Last run: `qa_overall = pass`. 1080×1920, H.264, 30 fps, 9.33 s, AAC, −13.9 LUFS, true peak −7.8 dBTP. Stage timings and QA in `docs/audit/BASELINE_RESULTS.md`.
- Demo inputs (footage, voice, music, impact) are synthetic stand-ins.

## Dependencies
- See `docs/audit/DEPENDENCY_INVENTORY.md`.
- Key versions: Python 3.13.18, Pillow 12.3.0, ffmpeg 6.1.1, jsonschema 4.26.0 (tests).
- `gh` is not authenticated in the sandbox.

## Decisions
See `docs/DECISIONS.md`.

## Known blockers
1. Editor repo not identified. Phase 0 editor audit and integration cannot proceed until the user names it.
2. Phases 1–15 spec text was cut off in the received prompt. The text ends mid-sentence in Phase 0's completion criteria.
3. `gh` cannot authenticate. Pushes rely on the sandbox git proxy.

## Next executable tasks
1. Ask the user for the editor repo name, or confirm it is local-only. (Blocker 1.)
2. Ask the user for the rest of the prompt (Phases 1–15 and the end of Phase 0's completion criteria). (Blocker 2.)
3. Fix D-01 and D-02 from `docs/audit/TECHNICAL_DEBT.md` (per-scene look application; spec validation). These are within the existing project scope and do not need the missing spec.
4. Fix D-07 (font fallback measurement mismatch) and add a test for it.
5. Add a render test for overlay tracks (currently IMPLEMENTED_UNVERIFIED).
