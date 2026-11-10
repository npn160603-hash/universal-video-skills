# Known limitations

Status uses the contract legend. Each item was checked against code at `08e9aae`.

| # | Limitation (from the project brief) | Status | Current fact |
|---|---|---|---|
| 1 | No completed animated map engine | NOT_IMPLEMENTED | No map code, no geodata. |
| 2 | No semantic media search | PARTIAL | Lexical search over sidecar tags, descriptions and file names, with a small synonym list. No embeddings, so no visual-content matching. |
| 12 | Motion is measured as scene-cut rate only | PARTIAL | `motion_per_second` counts hard cuts. Subject and camera motion are not measured. |
| 3 | No integrated speech recognition | NOT_IMPLEMENTED | Word timings are an input file. No ASR installed. |
| 4 | No complete TTS workflow | NOT_IMPLEMENTED | Demo voice is one tone per word, not speech. |
| 5 | No complete genre-style preset system | PARTIAL | 12 genres map to a caption style and director rules. The 10 required video presets do not exist. |
| 6 | Only four of seven caption styles | PARTIAL | Still true: Documentary Minimal, Cinematic, Bold Shorts, Emotional Storytelling. Missing: Clean Modern, Podcast Highlight, Educational. |
| 7 | No complete visual quality analysis | NOT_IMPLEMENTED | QA checks stream facts, black, frozen frames, silence, clipping, and loudness only. |
| 8 | No professional real-footage demonstration | NOT_IMPLEMENTED | Demo footage is generated gradients. |
| 9 | No integration audit of the user's local web editor | BLOCKED | Editor repo not identified. |
| 10 | No verified 16:9, 1:1, 4K, or H.265 export | IMPLEMENTED_UNVERIFIED (16:9, 1:1) / NOT_IMPLEMENTED (4K, H.265) | Width and height are parameters, but never rendered in tests. No H.265 code path. |
| 11 | Demo used synthetic audio and visual stand-ins | PARTIAL | Still true for the demo. The stand-ins are listed in `pipeline_report.json`. |

## Additional limitations found in Phase 0
- Style lock uses the first scene's look for the whole timeline (D-01).
- No input validation for `spec.json` (D-02).
- Three lossy re-encodes in the main path (D-03).
- Subtitle and keyframe tracks are not rendered (D-06).
- Overlay tracks are rendered but have no test (D-06).
- Font fallback can mismatch measurement and rendering (D-07).
- Demo word timings are hand-authored (D-10).
- Output is not byte-deterministic (not verified).
- `gh` cannot authenticate in the sandbox (D-14).
