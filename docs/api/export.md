# Performance and export (Phase 13) — public interface

Status: VERIFIED. Hardware detection, export profiles, render cache, benchmarking.

## Hardware (`uvs.export`)
- `detect_hardware() -> Hardware(cpu_cores, ram_gb, gpu_present, gpu_name, working_video_encoders, working_audio_encoders, listed_hwaccels, filter_count)`. Encoders are verified by test-encode; GPU via nvidia-smi. Hardware encoders are not claimed without a GPU.

## Export profiles
- `ExportProfile(name, aspect, resolution, vcodec, acodec, crf, fps)`; `.dimensions()`, `.encoder()`, `.validate()`.
- Aspects: 9:16, 16:9, 1:1. Resolutions: 720p, 1080p, 1440p, 4k. Codecs: h264, h265; audio aac.
- `standard_profiles()` -> the 6 required (3 aspects x 720p/1080p, H.264).
- `export(src, out, profile, hardware)` scales/pads to the profile and encodes; H.265 falls back to H.264 when unavailable.

## Render cache
- `RenderCache(root)`: `key(*parts)`, `has(key)`, `get_or_render(key, render_fn)` (atomic temp swap; reuse on hit), `clear()`.

## Benchmark
- `benchmark_render(render_fn, out) -> Benchmark(render_seconds, output_bytes, frames, encoding_fps, peak_memory_mb, decode_ok)`.
- `decode_valid(path) -> (ok, frame_count)`; `export_capability_matrix(hardware)`.

## Limits
- Cache is whole-output, not per-segment. 1440p/4K defined but not benchmarked here. No GPU path in this environment.
