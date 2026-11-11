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

## DEC-008: Phase 0 closed; editor audit deferred by user
- **Decision:** Phase 0 is VERIFIED against the user's completion list. The editor repo audit stays deferred until the user names the repo (user instruction, 2026-11-11).
- **Affects:** `docs/PHASE_STATUS.json`, `docs/INTEGRATION_STATUS.md`.

## DEC-009: Push of e84a7c7 authorised with conditions
- **Decision:** Pushed `08e9aae..e84a7c7` as a fast-forward to `initial-pipeline`. Verified with `git ls-remote`. No force push, no change to main.
- **Note:** The remote has no `main` branch (`git ls-remote` lists only `initial-pipeline`). Local `main` (eaceac8) is not on the remote.

## DEC-010: Pre-push guard
- **Decision:** `.githooks/pre-push` blocks pushes to main/master, branch deletion, and non-fast-forward updates. Enable with `git config core.hooksPath .githooks`.
- **Tested:** four cases (main push refused, fast-forward allowed, rewrite refused, deletion refused).

## DEC-011: jsonschema is a runtime dependency
- **Decision:** `uvs/project.py` validates documents with jsonschema, so it moves from test-only to runtime in `requirements.txt`.
- **Reason:** One validator for the schema file, rather than a hand-written copy that could drift.

## DEC-012: Clip removal keeps neighbouring transitions
- **Decision:** Removing a middle video clip keeps the successor's transition and reflows. Removing the first clip turns the new first clip into a cut.
- **Reason:** The earlier design (turn successor into cut) could not be undone correctly, because the undo record did not cover the side effect.

## DEC-013: Phase 1 scope
- **Decision:** Scene graph nodes are modelled and tested, but not rendered. Nested sequences are not built. Keyframes are not attached to clips.
- **Reason:** Rendering the scene graph belongs with the motion engine (Phase 4). Building it now would be untested rework.

## DEC-014: Narrative planner is a separate layer over the director
- **Decision:** `uvs/narrative.py` builds on `uvs/director.py` (scene segmentation, pacing, transitions) rather than replacing it. The director's API and output are unchanged.
- **Reason:** Keeps the existing pipeline and its tests stable.

## DEC-015: No audience inference
- **Decision:** `audience` is reported as "not supplied" unless the caller passes it.
- **Reason:** Guessing an audience from text is speculation; the spec asks for analysis, not invention.

## DEC-016: Lexicon noise is fixed by removing terms, not by adding special cases
- **Decision:** `stop` was removed from the urgency lexicon because it is also a noun. Stopwords were extended for topic keywords.
- **Affects:** `uvs/narrative.py`.

## DEC-017: Media retrieval is lexical, not semantic
- **Decision:** `uvs/retrieval.py` matches scene words against sidecar tags, descriptions and file names, with a small hand-written synonym list. No embeddings.
- **Reason:** No embedding model is installed, and downloading one needs authorisation. A lexical match can be explained word by word, which a model score cannot.
- **Consequence:** A word with no listed synonym does not match, even if the meaning is close. Tests check this on purpose.

## DEC-018: Motion is measured as scene cuts per second
- **Decision:** `media_index` reports `motion_per_second` = ffmpeg scene-score cuts (threshold 0.3) divided by duration. The first frame is never counted.
- **Reason:** It is cheap, reproducible, and verified on synthetic clips (static = 0, one hard cut = 1 cut).
- **Not measured:** Subject motion and camera motion.

## DEC-019: Cache holds media metrics only
- **Decision:** The cache stores content-derived metrics keyed by SHA-256 and index version. Tags, description and provenance are re-read from the sidecar on every scan.
- **Reason:** Sidecar text changes without changing the file. A cached licence would be a stale legal claim.

## DEC-020: Motion engine renders by compositing PIL layers, not ffmpeg filters
- **Decision:** `uvs/animate.py` draws each node into a full-frame RGBA layer, transforms it with PIL's affine transform, and pipes raw frames to ffmpeg.
- **Reason:** The scene graph's matrices map directly onto PIL's affine coefficients. Frames can be checked pixel by pixel in tests. An ffmpeg filter graph would be harder to verify at pixel level.
- **Cost:** Full-frame layers are slow at large sizes. Tiling is a later optimisation.

## DEC-021: Unsupported node kinds are refused, not skipped
- **Decision:** A node kind the renderer cannot draw raises `AnimationError` when the renderer is built.
- **Reason:** A skipped node would produce a video with missing content and no warning.

## DEC-022: Natural Earth data is loaded at run time, not bundled
- **Decision:** `load_countries` reads a path given by the caller or `UVS_NATURAL_EARTH_SHP`. The shapefile is not committed.
- **Reason:** The data is public domain, but the repository should carry only what it needs. The 110 m file is available from the `geopandas` wheel for anyone who needs it.

## DEC-023: Map frames are drawn with PIL, not through the scene graph
- **Decision:** `uvs/maps.py` draws its own frames. Only the encoder, `uvs.animate.encode_frames`, is shared.
- **Reason:** Country polygons and great-circle routes do not fit the scene graph's node types. Keeping them separate avoids forcing a new node kind through the graph.

## DEC-024: Infographics render with PIL at progress p, encoded by the shared pipe
- **Decision:** Each chart/timeline/diagram/metaphor is a function frame(spec, p) -> PIL image. Video uses uvs.animate.encode_frames.
- **Reason:** Frames can be checked pixel by pixel (height proportionality, fill fraction, overlap), and the last frame equals the data exactly.

## DEC-025: Single-series bars are coloured per category
- **Decision:** A one-series bar/ranking chart colours each bar by its index, not one flat colour.
- **Reason:** Distinct bars read faster in short-form video. Multi-series charts colour by series instead.

## DEC-026: Visual metaphors are always tagged ILLUSTRATIVE
- **Decision:** Every metaphor frame draws an "ILLUSTRATIVE — not data" tag, enforced in the renderer.
- **Reason:** The spec requires metaphors that could be mistaken for data to be labelled. Making it unconditional removes the judgement call.

## DEC-027: Diagram layout refuses to render on overlap
- **Decision:** layout_diagram places nodes on levels; render_diagram_frame raises if any boxes overlap.
- **Reason:** A silently overlapping diagram is worse than an error. The caller widens the canvas or reduces node size.

## DEC-028: Real ASR/TTS stay BLOCKED; interfaces and model-free providers ship
- **Decision:** uvs/speech.py defines ASR/TTS Protocols and capability detection, but installs no engine. SilenceTTS and ClickTrackTTS produce real WAV for timing/mixing tests; they are not speech (speech=False).
- **Reason:** No engine is installed and apt/model installs need authorisation (DEC per V3 directive). A click track is enough to exercise alignment and silence detection with real audio.
- **Unblock:** install whisper/vosk (ASR) or espeak-ng/piper (TTS) and register a provider; capability detection will report it.

## DEC-029: Caption styles gain a background field; clean_modern uses an opaque box
- **Decision:** CaptionStyle adds background ("outline"|"box"), box_color, box_alpha, line_spacing, max_words. to_ass maps "box" to ASS BorderStyle 3.
- **Reason:** The spec requires a background treatment per style; a flat white style (clean_modern) needs a box to stay readable.

## DEC-030: Vietnamese text is NFC-normalized and measured with the real font
- **Decision:** Diacritic detection decomposes (NFD) to catch precomposed and combining forms; QA warns on non-NFC words.
- **Reason:** libass renders NFC reliably; detecting diacritics only in one form would miss half the cases.

## DEC-031: Tempo from onset inter-onset intervals, not autocorrelation
- **Decision:** estimate_tempo uses the median inter-onset interval of detected onsets.
- **Reason:** On click tracks, autocorrelation produced octave errors (140 BPM read as 70). Median IOI is accurate within 5% on 90/120/140 BPM and is honest about complex material (confidence score).
- **Limit:** Verified on click tracks; polyphonic music may still mis-track.

## DEC-032: Audio QA measures, never estimates
- **Decision:** Loudness/true-peak via ffmpeg ebur128; clipping by scanning decoded samples; silence via silencedetect.
- **Reason:** The directive forbids invented numbers. Every QA figure comes from a tool run on the actual audio.

## DEC-033: Colour analysis and shot matching run in numpy on decoded frames
- **Decision:** uvs/color.py decodes frames and measures mean RGB, luma, saturation, warmth, crush and clip directly. Shot matching computes a per-channel gain from measured means.
- **Reason:** The directive forbids invented numbers and asks for measurable colour reports. Matching is verified by the measured distance dropping.

## DEC-034: The ten spec-named looks live in uvs.grade.LOOKS natively
- **Decision:** Documentary Natural ... High Contrast Editorial are defined in grade.py (not injected from color.py), so LOOKS is complete regardless of import order; the effect schema enum is generated from LOOKS.
- **Reason:** An earlier version mutated LOOKS on import of color.py, making the schema-sync test import-order dependent.

## DEC-035: Style Lock replaces scene-0 look inheritance (fixes D-01)
- **Decision:** A project names a style (spec['style']); StyleLock resolves one VideoStyle preset and applies its look to every scene. Without a style, the pipeline falls back to the old scene-0 look but records it as a fallback.
- **Reason:** D-01: the whole video inherited whatever look scene 0 carried. Verified end to end that a locked style overrides scene 0.

## DEC-036: A VideoStyle is a full editing preset, not a LUT
- **Decision:** Each of the 10 presets fixes narrative, pacing, transitions, typography, camera, easing, animation, effects, grade, b-roll, music, sfx, map and infographic style, plus a safe area.
- **Reason:** The spec requires ten full presets. Validation keeps them internally consistent (every referenced look/caption/emotion exists).
