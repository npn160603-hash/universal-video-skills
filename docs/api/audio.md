# Audio and sound design (Phase 8) — public interface

Status: PARTIAL. Voice chain, music intelligence, emotional direction, gain automation, audio QA.

## Voice chain (`uvs.audio`)
- `build_mix_graph(clips, denoise, deess, duck_threshold, duck_ratio)`, `mix_to_file(clips, out, target_lufs, true_peak, lra, denoise, duration)`.
- VOICE chain: high-pass, optional denoise, presence EQ (−2 dB @250 Hz, +2 dB @4 kHz), compression, optional de-ess, two-pass loudnorm, limiter.
- Categories: VOICE, MUSIC (sidechain-ducked), SFX, AMBIENCE. `AudioClip(category, path, start, duration, gain_db, loop, duck)`.

## Music intelligence (`uvs.audio_intel`)
- `estimate_tempo(path) -> Tempo(bpm, onset_count, confidence)` (onset-IOI; verified within 5% on click tracks).
- `detect_beats(path)`, `onset_times(path)`, `beat_aligned_cuts(beats, desired_times, max_shift)`.
- `energy_envelope(path, window) -> Envelope(times, rms)`.

## Emotional sound direction
- `sound_direction(emotion) -> SoundDirection(music_gain_db, ambience_gain_db, sfx_gain_db, duck_ratio, silence_before_key_moment, notes)`. Emotions: reflective, suspense, educational, inspirational, neutral.

## Gain automation
- `GainAutomation(points)` with `GainPoint(time, gain_db)`; `gain_at(t)` (piecewise-linear dB), `to_volume_expr()` (ffmpeg volume expression).

## Audio QA
- `measure_loudness(path) -> LoudnessReport(integrated_lufs, loudness_range, true_peak_dbtp)` (ebur128).
- `detect_clipping(path)`, `detect_silence_spans(path)`, `voice_music_balance(voice, music)`, `audio_qa(path, target_lufs) -> AudioQAReport` with `.issues()`.

## Limits
- Beat tracking verified on click tracks; polyphonic music may mis-track.
- No source separation or speech-enhancement models.
