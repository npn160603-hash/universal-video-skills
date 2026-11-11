# Speech and captions (Phase 7) — public interface

Status: PARTIAL. Interfaces, model-free providers, segmentation, 7 caption styles, typography, QA.
Real ASR and real speech TTS are BLOCKED (no engine installed).

## Capability detection (`uvs.speech`)
- `detect_capabilities() -> Capabilities`: probes whisper/faster_whisper/vosk (ASR) and espeak-ng/piper/coqui (TTS). `.report()` is a JSON-able summary. None are bundled.

## Providers
- Interfaces: `ASRProvider`, `TTSProvider` (Protocols). `VoiceSpec(language, voice, rate, sample_rate, output_format, identity, pronunciation)`.
- Real, model-free TTS: `SilenceTTS`, `ClickTrackTTS` — genuine WAV, `speech=False`. `get_tts_provider(name)` returns a test provider or raises (BLOCKED) for a known-but-uninstalled engine.
- `ExternalTimestampASR(items)` / `words_from_timestamps(items)`: fallback accepting `{text,start,end}` with monotonic-order validation.

## Timing (ffmpeg, no model)
- `detect_silences(audio, noise_db, min_silence)`, `speech_segments(audio, ...)`, `audio_duration(audio)`.
- From word timings: `sentence_boundaries`, `phrase_boundaries(max_gap, max_words)`, `silences_between_words(min_gap)`, `subtitle_timeline`.

## Caption styles (`uvs.captions.STYLES`)
Seven: documentary_minimal, clean_modern, cinematic, bold_shorts, podcast_highlight, educational, emotional_storytelling. Each defines font/weight/size/stroke/background/highlight/animation/margins/max_lines/max_words. `background="box"` → ASS BorderStyle 3.

## Typography (`uvs.typography`)
- `typewriter`, `staggered_words`, `phrase_animation`, `mask_reveal`, `speaker_color`, plus word/keyword highlight in the ASS writer. `TYPOGRAPHY_EFFECTS` lists the seven.

## Layout QA (`uvs.typography.layout_qa`)
Extends `validate_cues` with unreadable-font, words-per-phrase, and NFC/diacritic checks. `has_vietnamese_diacritics`, `nfc` handle Vietnamese (precomposed and decomposed).

## Limits
- Real ASR/TTS BLOCKED; speaker diarization is interface + colour only.
- `mask_reveal` is an ASS intent tag, not a pixel-accurate wipe.
