# Known limitations

Status uses the contract legend. Each item was checked against code at `08e9aae`.

| # | Limitation (from the project brief) | Status | Current fact |
|---|---|---|---|
| 1 | No completed animated map engine | PARTIAL | Country shapes, projections, great-circle routes, markers, and camera moves are implemented and tested on Natural Earth 110 m. No labels, choropleths, or bundled data. |
| 2 | No semantic media search | PARTIAL | Lexical search over sidecar tags, descriptions and file names, with a small synonym list. No embeddings, so no visual-content matching. |
| 12 | Motion is measured as scene-cut rate only | PARTIAL | `motion_per_second` counts hard cuts. Subject and camera motion are not measured. |
| 20 | Beat tracking verified on click tracks only | PARTIAL | Tempo within 5% on synthetic clicks; polyphonic music may mis-track (octave errors). |
| 17 | Real ASR is unavailable | BLOCKED | No whisper/vosk model installed; download not authorised. Interface + external-timestamp fallback work. |
| 18 | Real speech TTS is unavailable | BLOCKED | No espeak-ng/piper; apt/model install not authorised. Real WAV test providers (silence, click track) work. |
| 19 | Speaker diarization from audio | PARTIAL | Interface and colour differentiation only; no diarization model. |
| 14 | Chart set is the 10 required kinds | PARTIAL | No scatter, stacked or radar charts. The 10 required kinds are implemented and tested. |
| 15 | Diagram label/connector crossings | PARTIAL | Node boxes never overlap (checked), but dense graphs may still cross connectors. |
| 16 | Visual metaphors are a fixed set of 8 | PARTIAL | Each is a hand-built illustration, always tagged illustrative. Not a general metaphor composer. |
| 13 | Motion engine renders shapes, images and groups only | PARTIAL | Keyframes drive node transforms and render to MP4. Text, video, mask, camera, chart, map, particle and overlay nodes are refused, not drawn. |
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
