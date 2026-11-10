# universal-video-skills

A standalone, free/open-source start on an AI-assisted short-video editing system. It is not the full system in the
master prompt. What exists is tested against real ffmpeg output, and what doesn't exist is listed in
`architecture/capability-matrix.md`.

## What runs
- **Pipeline** (`uvs/pipeline.py`): words → director plan → captions → timeline → grade → caption burn-in
  → audio mix (ducking, two-pass loudness, limiter) → mux → QA. Writes a plan, captions, the video, audio,
  a QA report, and a pipeline report with stage timings, decisions, and stand-ins.
- **Director** (`uvs/director.py`): scenes, pacing, transitions, music level, sound-effect rules, and an
  edit decision record. Rule-based and deterministic.
- **Timeline** (`uvs/timeline.py`): frame-accurate model, validation, render with cut / dissolve / dip-to-black,
  audio and overlay tracks.
- **Captions** (`uvs/captions.py`): cue segmentation, measured two-line layout, four styles, ASS/SRT/VTT, validation.
- **Motion** (`uvs/motion.py`): easing curves (including spring, elastic, bounce, overshoot) and keyframe tracks.
- **Colour** (`uvs/grade.py`): 10 named looks, intensity scaling, LUT path.
- **Audio** (`uvs/audio.py`): categories, voice high-pass and compression, sidechain ducking, two-pass loudness.
- **Charts** (`uvs/charts.py`): bar chart with eased animation. Refuses to render without data and a source.
- **Media index** (`uvs/media_index.py`): metadata, provenance sidecars, duplicate detection, ranking.
- **QA** (`uvs/qa.py`): technical checks, black, frozen, silence, clipping, true peak, loudness. JSON report.
- **Schemas** (`schemas/`): project, scene, timeline, animation, effect.

## Requirements
- Python 3.13 (tested). Pillow (`requirements.txt`). jsonschema is used by the tests.
- ffmpeg and ffprobe with libx264, aac, and libass. Tested with ffmpeg 6.1.1.
- fontconfig (`fc-match`) and the Inter font family.

No paid APIs, no cloud services, no network access at runtime.

## Run
```bash
python3 -m uvs.pipeline examples/demo_pipeline/spec.json out/pipeline_demo   # ~75 s
python3 -m uvs.render --out out/demo                                        # captioned clip only
python3 -m uvs.captions examples/demo_caption/words.json --style bold_shorts --out-dir out/captions
python3 -m uvs.qa out/pipeline_demo/final.mp4 --duration 9.35 --json out/qa.json
python3 -m unittest discover -s tests -t .                                  # about 2 min
```

Word timings are an input. Nothing here does speech-to-text. `examples/demo_caption/words.json` and the demo
spec are hand-authored placeholders.

## Layout
```
uvs/                    Python package (captions, qa, render, director, timeline, motion, grade, audio,
                        charts, media_index, pipeline)
skills/                 SKILL.md for each implemented skill, with its real limits
schemas/                JSON schemas (enums are checked against the code)
architecture/           capability-matrix.md
examples/               demo_caption (words), demo_pipeline (spec)
tests/unit/             pure-logic tests and schema tests
tests/render/           ffmpeg integration tests on real clips and renders
```

## Known limits
- The demo's footage, voice, music, and impact are synthetic stand-ins. Each is listed in `pipeline_report.json`.
  No real speech, footage, or narration is used anywhere.
- The four required demos from the master prompt are not produced. They need real footage, narration, and licensed
  map or chart data.
- Not implemented: speech-to-text, TTS, maps, embedding-based (semantic) media search, skin-tone protection, shot matching,
  multitrack compositing beyond overlays, motion graphics, and visual defect checks (flicker, blur, crop).
- QA measures and reports. It does not repair anything automatically.
- Creative quality is not evaluated. QA produces no creative scores.
