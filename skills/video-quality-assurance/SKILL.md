# video-quality-assurance

Checks a rendered video file for technical and basic audio/visual defects, and reports measured values.
Status: **implemented and tested**. This is a QA gate, not a creative judge.

## Purpose
Confirm that a rendered file has the expected dimensions, frame rate, codecs, and duration, decodes
cleanly, and has no black or frozen spans, long silence, clipping, or true-peak overshoot. It also
reports integrated loudness.

## Supported inputs
- Any file ffprobe can read. Expectations are passed in through `QAConfig` or CLI flags.

## Supported outputs
- A `QAReport` with one `Check` per item: `id`, `category` (technical / visual / audio / timeline),
  `status` (`pass` | `warn` | `fail` | `info`), `detail`, and `value`.
- `overall`: worst status across checks. Also a JSON file when `--json` is given.

## Execution
```bash
python3 -m uvs.qa out/demo_bold/final.mp4 --width 1080 --height 1920 --fps 30 \
  --codec h264 --duration 9.55 --json out/demo_bold/qa_report.json
```
Exit code 1 if `overall` is `fail`. In Python: `uvs.qa.run_qa(path, QAConfig(...))`.

## Parameters (`QAConfig`)
- `expect_width`, `expect_height`, `expect_fps`, `expect_video_codec` (default `h264`),
  `expect_audio_codec` (default `aac`), `expect_duration`, `duration_tolerance` (0.1 s).
- `black_min_duration` (0.5 s), `freeze_min_duration` (1.0 s), `silence_min_duration` (1.0 s).
- `clip_threshold_db` (-0.1 dBFS): a sample peak at or above this is a clipping failure.
- `true_peak_max_dbtp` (-1.0 dBTP): above this is a warning.
- `loudness_target_lufs`, `loudness_tolerance_lu`: optional. With no target, loudness is reported as info.

## Dependencies
ffmpeg and ffprobe (tested with ffmpeg 6.1). The analysis filters used are `blackdetect`,
`freezedetect`, `silencedetect`, `volumedetect`, and `ebur128`. No Python packages beyond the standard library.

## Constraints
- Black frames at the start of a clip are reported as a warning, not a failure. Fade-ins are intentional.
- No creative scoring is produced. Rhythm, story, and style checks are not implemented.
- Loudness is measured in EBU R128 (integrated, true peak). It is not normalized here.
- Frozen-frame detection uses a fixed noise threshold (`n=0.003`) and may misfire on static graphics.
- Long analysis passes are sequential. A 10-second clip takes a few seconds per analysis filter.

## Error handling
- Missing video stream: `video_stream` fails and the run stops.
- ffmpeg analysis errors raise `RuntimeError` with the tail of stderr.
- Decode errors are captured in the `decode` check (full decode with `-v error`).

## Tests
- `tests/unit/test_qa_parsers.py`: parsers for each filter's output, including the regression where
  the first per-frame `I:` line was read instead of the summary.
- `tests/render/test_pipeline.py::QATests`: real clips with known defects. Covers a wrong fps (fail),
  clipping (fail), long silence (warn), leading black (warn), and loudness/true-peak being measured.

## Integration
The render pipeline calls `run_qa` after encoding and writes `qa_report.json` next to the output.
`render_captioned` returns `qa_overall`. Pipeline stages that change timing or audio can call the
same function to re-check.
