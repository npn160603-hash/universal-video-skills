# Capability matrix (Phase 0 audit, 2026-11-10)

## Audit results

- **Editor repo:** not available to this session. No existing editor code was read, so no integration
  with a current renderer is claimed. This repo is standalone. Integration with the local Shorts editor
  is a later step, once its repo is connected.
- **Sandbox:** Linux, Python 3.13, ffmpeg/ffprobe 6.1.1 (libx264, libx265, aac, libass `ass`/`subtitles`,
  `drawtext`, `blackdetect`, `freezedetect`, `silencedetect`, `volumedetect`, `ebur128`, `gradients`),
  Pillow 12.3, Node 22, git 2.43.
- **Not available:** a TTS engine (no espeak, no piper), speech-to-text, any sample footage, any narration audio.
- **Fonts:** Inter (regular and bold) installed and verified for Vietnamese. Poppins also installed.
- **GitHub:** the `gh` token in this session is invalid, and there is no tool here to create repos.

## Status legend
`Done` = implemented and covered by a passing test or a checked render. `Partial` = some of it works.
`Missing` = not implemented.

## Matrix

| Feature (master prompt section) | Status | Integration approach | Dependencies | Test method |
|---|---|---|---|---|
| Phase 0 audit of an existing editor repo (§1) | Missing | Connect the editor repo, then inspect it | GitHub access | — |
| Word timings → phrase cues (§8) | Done | `uvs.captions.segment_words` | Pillow | `tests/unit/test_captions.py::SegmentTests` |
| Measured two-line layout, safe margins (§4.3, §8) | Done | Widths via real font file (fontconfig + Pillow) | fontconfig, Inter | `LayoutTests`, visual frame check |
| ASS / SRT / WebVTT export (§8) | Done | `to_ass`, `to_srt`, `to_vtt` | none | `ExportTests` |
| Caption validation: overlap, overflow, line count, punctuation, NFC (§8, §16) | Done | `validate_cues` | Pillow | `ValidationTests` |
| Vietnamese Unicode (§8) | Done | NFC on load; Inter renders diacritics | Inter | demo words include NFD input; frames inspected |
| Keyword highlighting (§8) | Done | keyword list + optional digit tokens | none | `test_only_keywords_get_highlight_tags` |
| Caption styles (§8) | Partial | 4 of 7 named styles | none | `test_no_highlight_style_has_no_tags_for_keywords`; other styles only exercised by the demo build |
| Word-level timestamps from speech-to-text (§8) | Partial | Accepts timings; no STT bundled | none | — |
| Speaker-aware styles, extra languages (§8) | Missing | — | — | — |
| Caption animation: fade, keyword pop (§8) | Done | ASS `\fad`, `\t` on highlighted words only | libass | frame check at highlight times |
| Synthetic base clip + libass burn-in (§13) | Done | `uvs.render` | ffmpeg | `RenderTests` |
| 9:16 H.264 + AAC output (§13) | Done | 1080x1920, 30 fps, CRF 18 | ffmpeg, libx264 | `RenderTests` |
| 16:9 and 1:1 output (§13) | Partial | Width/height arguments accepted | ffmpeg | not run |
| 4K, H.265, GPU, cache, incremental render (§13) | Missing | — | — | — |
| Deterministic output (§13) | Partial | metadata stripped; no byte-identity test | — | not verified |
| Structured render logs (§13) | Missing | QA report JSON only | — | — |
| Technical QA: dimensions, fps, codec, duration, decode, audio codec, A/V duration drift (§16) | Done | `uvs.qa.run_qa` | ffprobe | `QATests` |
| Black frames, frozen frames (§16) | Done | `blackdetect`, `freezedetect` | ffmpeg | `QATests::test_clean_clip...` |
| Silence, clipping, true peak, loudness (§16, §5.3) | Done (measure only) | `silencedetect`, `volumedetect`, `ebur128` | ffmpeg | `QATests`, parser tests |
| Loudness target / normalization (§5.3) | Partial | Target check optional; no normalization | — | not run |
| Excessive blur, flicker, bad crop, aspect error, voice/music balance (§16) | Missing | — | — | — |
| Creative scores (§16) | Missing | — | — | — |
| Timeline, multitrack, keyframes, nested sequences (§3.1) | Missing | — | — | — |
| Editing techniques and transition rules (§3.2–3.4) | Missing | — | — | — |
| Keyframes, easing, spring, motion graphics, camera (§4) | Missing | — | — | — |
| Color grading, LUTs, color spaces (§5.1–5.2) | Missing | — | — | — |
| Audio: normalization, ducking, categories (§5.3, §9) | Missing | — | — | — |
| Animated maps and routes (§6) | Missing | — | — | — |
| Charts and data graphics; no fabricated numbers (§7) | Missing | — | — | — |
| Asset indexing and semantic media selection (§10) | Missing | — | — | — |
| Style presets and style lock (§11) | Missing | — | — | — |
| AI director plan and decision record (§2, §12) | Missing | — | — | — |
| Demo 1: emotional life story (§17) | Not produced | Needs footage and voiceover | — | — |
| Demo 2: geography / travel (§17) | Not produced | Needs map data with licence terms | — | — |
| Demo 3: educational short (§17) | Not produced | Needs data for charts, icons | — | — |
| Demo 4: lifestyle story (§17) | Not produced | Needs lifestyle footage | — | — |

## Phase status (§18)

- **Phase 0 (audit):** partial. Sandbox audited. Editor repo not inspected.
- **Phase 1 (core editing):** partial. Caption timeline and baseline render exist. No multitrack timeline or transitions.
- **Phase 2 (motion):** missing, except the ASS fade and keyword pop used by captions.
- **Phase 3 (storytelling):** missing.
- **Phase 4 (post-production):** missing.
- **Phase 5 (advanced visuals):** missing.
- **Phase 6 (automation):** missing. The caption → render → QA chain runs as one call.
- **Phase 7 (QA):** partial. Technical and audio-measurement checks run. Visual defect checks and render benchmarks are missing.

## Known limits of what exists
- The demo uses a generated gradient and a 220 Hz tone. It is a pipeline test, not a video edit.
- The demo's caption timings are hand-written, not matched to any narration.
- Measured loudness on the demo is −42 LUFS. That is the synthetic tone's level, not a target.
