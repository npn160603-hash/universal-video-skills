# Baseline results (Phase 0 audit)

Commit: `08e9aae`. Working tree clean. The test run and the demo run used the same code (the only later edits were to documentation).

## 1. Test suite

Command: `python3 -m unittest discover -s tests -t .`

| Result | Value |
|---|---|
| Tests run | 125 |
| Outcome | OK (all pass) |
| Wall time | 117.2 s (real 1 m 57 s) |
| CPU user time | 3 m 17 s |

Tests per file:

| File | Tests |
|---|---|
| `tests/unit/test_captions.py` | 26 |
| `tests/unit/test_qa_parsers.py` | 9 |
| `tests/unit/test_motion.py` | 18 |
| `tests/unit/test_director.py` | 13 |
| `tests/unit/test_timeline.py` | 11 |
| `tests/unit/test_schemas.py` | 8 |
| `tests/render/test_pipeline.py` | 6 |
| `tests/render/test_timeline_render.py` | 2 |
| `tests/render/test_grade.py` | 9 |
| `tests/render/test_audio.py` | 9 |
| `tests/render/test_charts_media.py` | 9 |
| `tests/render/test_pipeline_e2e.py` | 5 |
| **Total** | **125** |

## 2. Demo pipeline

Command: `python3 -m uvs.pipeline examples/demo_pipeline/spec.json /tmp/uvs_demo`
Exit status 0. `qa_overall = pass`.

### Output file

| Property | Measured | Expected | Result |
|---|---|---|---|
| Container | MP4 | MP4 | pass |
| Video codec | h264 | h264 | pass |
| Resolution | 1080 × 1920 | 1080 × 1920 | pass |
| Frame rate | 30.000 fps | 30 | pass |
| Duration (container) | 9.333 s | 9.350 s ± 0.15 | pass |
| Audio codec | aac | aac | pass |
| A/V duration drift | 0.011 s (audio 9.322 s, video 9.333 s) | — | pass |
| Full decode | no errors | no errors | pass |
| Black frames | none | none | pass |
| Frozen frames | none | none | pass |
| Long silence | none | none | pass |
| Max sample peak | −7.8 dBFS | < 0 | pass |
| Mean level | −16.3 dBFS | — | info |
| True peak | −7.8 dBTP | ≤ −1 | pass |
| Integrated loudness | −13.9 LUFS | −14 ± 1 | pass |
| Final file size | 2,544,576 bytes | — | — |

### QA summary
15 pass, 0 warn, 0 fail, 1 info.

### Stage timings

| Stage | Seconds |
|---|---|
| load_words | 0.00 |
| director | 0.00 |
| captions | 0.02 |
| synthetic_footage | 26.09 |
| timeline | 0.17 |
| render_timeline | 12.87 |
| grade | 19.63 |
| burn_captions | 11.87 |
| synth_voice | 0.16 |
| synth_music | 0.16 |
| synth_impact | 0.01 |
| audio_mix | 0.97 |
| mux | 0.07 |
| qa | 3.44 |
| **Sum** | **75.46** |

Notes:
- Synthetic footage generation takes about a third of the run. It is a cost of the demo, not of real-footage edits.
- The three re-encodes (timeline, grade, burn-in) take about 44 s together.
- Run-to-run variation was not measured. This is one run.

### Demo report
- `scenes = 3`, `genre = real_life_storytelling`, `transitions = {cut: 0, dissolve: 2, dip_black: 0}`.
- 11 director decisions recorded.
- Stand-ins recorded: synthetic gradient footage, tone-per-word voice, two sine-tone music, one synthetic impact. None is real footage, speech, or music.

## 3. Report validity
- `pipeline_report.json` and `qa_report.json` both parse as valid JSON.
- No JSON schema exists for either report. Validity is only "parses and has the expected keys".

## 4. Environment at baseline
- Python 3.13.18, Pillow 12.3.0, ffmpeg/ffprobe 6.1.1, Node 22.23.4, git 2.43.0.
- 2 vCPU, 8 GB RAM.

## 5. Not measured
- Performance on other resolutions, longer videos, or other hardware.
- Repeat runs (variance).
- Determinism: output bytes were not compared between runs.
