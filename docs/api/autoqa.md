# Automated QA (Phase 14) — public interface

Status: VERIFIED. Visual/audio detection, timeline QA, creative heuristics, safe repairs, reports.

## File QA (`uvs.qa.run_qa`)
Black frames, frozen frames, silence, clipping, true peak, loudness, format/dimensions/fps. Real ffmpeg measurements.

## Timeline + creative (`uvs.autoqa`)
- `qa_edit_plan(edit_plan) -> [TimelineIssue]`: gaps, overlaps, bad durations.
- `creative_heuristics(edit_plan) -> [HeuristicScore]`: scene diversity, transition variety, pacing, caption/graphic density. Labelled judgement, not measurement.

## Safe repairs (bounded, on a copy)
- `repair_loudness(src, out, target_lufs)` — new file, original untouched; in-place refused.
- `repair_timeline_timing(edit_plan) -> (fixed_copy, log)`; `run_safe_repairs(plan, max_passes)` — bounded, no infinite loop.
- `repair_caption_margins(overflowing, margin, max_tries)` — bounded.

## Reports
- `full_qa(video, edit_plan, cfg) -> QABundle`; `QABundle.to_dict()`, `.to_markdown()`; `write_reports(bundle, out_dir, stem)` writes JSON + Markdown.

## Limits
- No flicker/blur/overlay distinct checks; no A-V sync measurement. Not every defect has an auto-repair.
