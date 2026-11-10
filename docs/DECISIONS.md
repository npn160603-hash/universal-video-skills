# Decisions

Each entry: the decision, the reason, and what it affects.

## DEC-001: Continue on branch `initial-pipeline`
- **Decision:** Keep working on `initial-pipeline`. Do not create another branch. Do not touch `main`.
- **Reason:** That is the development branch named in the project context. `main` is not to be overwritten or merged into.
- **Affects:** all commits from this pass.

## DEC-002: Local commits only; no push in this pass
- **Decision:** Commit locally. Do not push to `origin` without an explicit authorization for this pass.
- **Reason:** The execution contract (B2) says not to push without explicit authorization. An earlier authorization covered a single upload of an earlier version; it does not extend to this pass.
- **Affects:** the remote branch stays at `08e9aae` until the user says to push.

## DEC-003: Do not import or audit the editor from an unconfirmed repo
- **Decision:** Do not attach or read any repo from the user's GitHub account as "the editor". The editor repo was not named.
- **Reason:** The account has at least 18 repos. The project memory names a skill-pack repo (`shorts-ai-editing-skills`) and says the editor repo exists, but does not name it. Picking one would be a guess, and the contract forbids importing from unrelated projects.
- **Affects:** `docs/INTEGRATION_STATUS.md` marks the editor audit and adapter as BLOCKED.

## DEC-004: Re-use the existing test and demo runs as Phase 0 baseline
- **Decision:** The tests and demo were run on the same code at `08e9aae` in this pass. Only docs changed afterwards.
- **Reason:** Avoids re-running 2 minutes of tests without a code change. The tree was verified clean and unchanged.
- **Affects:** `docs/audit/BASELINE_RESULTS.md`.

## DEC-005: Status legend follows the contract
- **Decision:** Use VERIFIED, IMPLEMENTED_UNVERIFIED, PARTIAL, BLOCKED, NOT_IMPLEMENTED. Map the older Done/Partial/Missing labels onto them.
- **Reason:** B5 defines these statuses. The older matrix in `architecture/` is kept as a detailed reference.
- **Affects:** `docs/audit/CAPABILITY_MATRIX.md`.
- **Correction recorded in this pass:** the older matrix listed the required 10 video presets as partial. They are NOT_IMPLEMENTED. The 10 colour looks have different names and define colour only. The overlay track was listed as verified, but no test renders one (IMPLEMENTED_UNVERIFIED).

## DEC-006: Phases 1–15 are not started
- **Decision:** Record phases 1–15 as NOT_STARTED with the note "spec text not in the received prompt". Do not invent their contents.
- **Reason:** The received prompt contains the full spec only for Phase 0. The text is cut off mid-sentence. Building from guesses would produce work the user did not ask for.
- **Affects:** `docs/PHASE_STATUS.json`.

## DEC-007: No new features in Phase 0
- **Decision:** Phase 0 changes docs only. Defects found in the audit are logged in `docs/audit/TECHNICAL_DEBT.md`, not fixed here.
- **Reason:** Phase 0 is an audit. Fixes belong to the later phases, where the defect can be tested with the feature.
- **Affects:** `TECHNICAL_DEBT.md` lists D-01 to D-17 with a suggested order.
