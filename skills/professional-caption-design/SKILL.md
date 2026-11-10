# professional-caption-design

Turns timed words into on-screen captions for vertical video. Status: **implemented and tested**.

## Purpose
Group words into readable cues, lay them out with measured line widths, style them in a
small set of named looks, export ASS / SRT / WebVTT, and report layout problems.

## Supported inputs
- Word timings: JSON list of `{"text", "start", "end"}` or `{"words": [...]}`, times in seconds.
  Text is normalized to Unicode NFC on load, so Vietnamese diacritics compare and render reliably.
- Optional keyword list to highlight, and an optional flag to highlight tokens that contain digits.

**Speech-to-text is not included.** Word timings must come from the caller.

## Supported outputs
- `captions.ass` (libass-styled, burned in by the render pipeline)
- `captions.srt`, `captions.vtt` (plain text, for players and platforms)
- A list of issues with `level` (`error` | `warning`), `code`, `message`, and `cue` index

## Execution
```bash
python3 -m uvs.captions examples/demo_caption/words.json --style bold_shorts \
  --keywords "cháo,5" --out-dir out/captions
```
Exit code is 1 if any error-level issue exists. In Python: `uvs.captions.build_captions(...)`
then `write_outputs(build, out_dir)`.

## Parameters
- `style`: `documentary_minimal`, `bold_shorts`, `cinematic`, `emotional_storytelling`.
  Each style sets font, size, weight, colors, outline, shadow, bottom safe margin
  (`margin_v`), side margin, max lines (2), and animation (`fade`, `pop`, `none`).
- `frame_w`, `frame_h`: default 1080x1920.
- `SegmentConfig`: `max_gap` (0.45 s), `max_duration` (2.8 s, target), `hard_max_duration`
  (3.4 s, a sentence end may finish a cue up to this), `min_duration` (0.7 s).

## Dependencies
- Python 3.10+, Pillow.
- fontconfig (`fc-match`) to locate the font file. Without it, Pillow's default font is used and
  width checks are approximate. The validator does not report that fallback, so keep fontconfig installed.
- The font family named in the style (default `Inter`) must be installed for libass and fontconfig.

## Layout rules
- Widths are measured with the real font file. The usable width is
  `frame_w - 2*margin_h - 2*outline`.
- Two-line splits are balanced by measured width, with a small bonus for breaking after punctuation.
- Cues break on sentence ends, long silences, the duration limits, or when the next word would
  not fit within two lines.
- Highlighted keywords use a colour change. In the `bold_shorts` style they also scale up briefly
  (`pop`). Other words do not animate, so not every word moves the same way.
- ASS override syntax (`{`, `}`, `\`) in user text is replaced with look-alike characters.

## Examples
`examples/demo_caption/words.json` is a hand-timed Vietnamese placeholder. It is not matched to
real narration. Run the demo: `python3 -m uvs.render --out out/demo`.

## Constraints
- Not validated against platform caption rules (for example each platform's line-length or
  reading-speed limits). The `too_fast` threshold (22 characters per second) is a heuristic.
- No speaker-aware styles, no per-language line-break dictionaries (Vietnamese breaks at spaces only).
- "Documentary Minimal", "Bold Shorts", "Cinematic", "Emotional Storytelling" are implemented.
  "Clean Modern", "Podcast Highlight", and "Educational" are not.

## Error handling
- Empty text, negative times, or times out of order raise `ValueError` when loading.
- Unknown style raises `KeyError`.
- Layout problems are reported as issues rather than silently fixed: `line_overflow`, `too_many_lines`,
  `overlap`, `outside_frame`, `non_positive_duration`, `empty_cue` (errors);
  `short_cue`, `long_cue`, `orphan_word`, `too_fast`, `space_before_punctuation`,
  `missing_space_after_punctuation`, `double_space`, `not_nfc` (warnings).
- `render_captioned` refuses to render when there are errors.

## Tests
`tests/unit/test_captions.py` (loading, layout, segmentation, validation, export).
`tests/render/test_pipeline.py::RenderTests` renders the demo and checks dimensions, codecs, frame rate,
and that the caption text reaches the ASS file.

## Integration
The render pipeline (`uvs/render.py`) calls `build_captions` and `write_outputs`, then burns the ASS
file with `ffmpeg -vf ass=...`. The style and keyword options map directly onto the pipeline's CLI.
