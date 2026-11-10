# universal-video-skills

A standalone, free/open-source starting point for an AI-assisted short-video editing system.
Current scope: **caption design, technical QA, and a captioned render pipeline**, all tested with real ffmpeg output.

It is not the full system described in the master prompt. Most of that prompt is still missing.
See `architecture/capability-matrix.md` for a per-feature status.

## What works

- `professional-caption-design`: phrase segmentation, two-line layout measured with the real font,
  four caption styles, ASS / SRT / WebVTT export, validation report. Vietnamese (NFC) verified.
- `video-quality-assurance`: ffprobe and ffmpeg analysis checks (dimensions, fps, codec, duration,
  decode, black and frozen frames, silence, clipping, true peak, loudness). JSON report.
- Render pipeline: synthetic 9:16 base clip → libass burn-in → H.264 / AAC → QA.

## Requirements

- Python 3.10+ and Pillow (`pip install -r requirements.txt`)
- ffmpeg and ffprobe with libx264, aac, and libass (`ass` filter). Tested with ffmpeg 6.1.1.
- fontconfig (`fc-match`) and the Inter font family for the default styles.

No paid APIs, no cloud services, no network access at runtime.

## Run

```bash
python3 -m uvs.render --out out/demo          # render demo, then QA
python3 -m uvs.captions examples/demo_caption/words.json --style bold_shorts --out-dir out/captions
python3 -m uvs.qa out/demo/final.mp4 --json out/demo/qa_report.json
python3 -m unittest discover -s tests -t .    # 41 tests, about 35 s (includes ffmpeg renders)
```

Word timings are an input. The repo does not bundle speech-to-text. Provide a JSON file of
`{"text", "start", "end"}` entries. `examples/demo_caption/words.json` is hand-timed and only for testing.

## Layout

```
uvs/                    Python package: captions.py, qa.py, render.py
skills/                 SKILL.md for each implemented skill (only implemented skills are listed)
architecture/           capability-matrix.md (Phase 0 audit and status)
examples/demo_caption/  word timings for the caption demo
tests/unit/             caption and QA-parser tests (no media needed)
tests/render/           ffmpeg integration tests (real clips with known defects)
```

## Known limits

- The demo video is synthetic: a gradient and a tone. It has no footage and no narration.
- No speech-to-text, TTS, or voice processing is included or claimed.
- The four required demos in the master prompt cannot be produced yet. They need real footage, narration,
  and licensed data.
- QA measures and reports. It does not repair anything automatically.
- Creative quality is not evaluated. The QA module gives no creative scores.

## Repository status

The repository is not yet pushed to GitHub. The `gh` token in the build environment was invalid at the time
of writing, and no repo-creation tool was available.
