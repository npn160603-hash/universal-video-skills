# Integration status

## Local editor (the user's localhost web tool)

- **Status: BLOCKED.**
- **Why:** The editor repo has not been identified. It was not named in the request or the project brief.
- **What the project memory says:** The user is building a local-first web app that auto-edits short vertical videos, and an AI editing skill pack for it. The skill pack lives in `npn160603-hash/shorts-ai-editing-skills`. That is a separate repo from the editor. The memory does not name the editor repo, and it may not be on GitHub at all.
- **Candidate repos in the account** (not verified; listed only so the user can name the right one): `Auto-Editing-OutlierY` (private), `Premiere-Auto-Cut-v0.6.12` (private), `ME-OutlierY` (private), `AESpace-v1` (private), `CapCut-Project-Packager` (private), `FB-Reels-Auto-Poster` (private).
- **What was not done:** No repo was attached. No code was read or copied from any repo other than this one.

### What can be built without the editor
An SDK and an adapter interface, so the editor can call the pipeline without a shared codebase. Neither exists yet. Status: NOT_IMPLEMENTED. Building them is a later phase and should wait for the editor's real API. A guessed API would be rework.

### What the editor integration needs to be verified
1. The editor repo or a local path to it.
2. Its entry point and how it calls a renderer (subprocess, HTTP, or import).
3. Its timeline and scene format, to compare with `schemas/`.

## Other integrations

| Integration | Status | Notes |
|---|---|---|
| GitHub (push to `origin`) | VERIFIED for `initial-pipeline` | Pushed in an earlier pass. This pass commits locally only (DEC-002). |
| `gh` CLI | BLOCKED | Token fails to authenticate. Not needed while git push works. |
| ffmpeg | VERIFIED | 6.1.1 with the filters used by the code. |
| Fonts (fontconfig) | IMPLEMENTED_UNVERIFIED on other platforms | Works on Linux with fc-match. Fallback not tested (D-07). |
| TTS, ASR, maps, paid APIs | NOT_IMPLEMENTED | None installed. None used. |
