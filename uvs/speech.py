"""Speech-aware editing interfaces: ASR, TTS, VAD, alignment, subtitles (Phase 7.1-7.4).

This module defines the interfaces and the parts that work without a speech model:
- capability detection that probes the environment for real engines (none are bundled);
- voice-activity / silence detection and loudness via ffmpeg, which need no model;
- an external-timestamp fallback so a caller who already has word timings can drive the pipeline;
- real test-audio TTS providers (silence and a word-aligned click track) that produce genuine WAV
  files for timing and mixing tests — they are not speech and say so.

Real ASR and real speech TTS are BLOCKED here: no engine (whisper, vosk, espeak-ng, piper, ...) is
installed, and installing one needs authorisation. The interfaces are ready for a provider to be
registered when a model is available; capability detection reports what is and is not present.
"""
from __future__ import annotations

import json
import math
import re
import shutil
import struct
import subprocess
import wave
from dataclasses import dataclass, field
from pathlib import Path
from typing import Protocol, Sequence

from uvs.captions import Word


class SpeechError(ValueError):
    pass


# ---------------------------------------------------------------------------
# Capability detection
# ---------------------------------------------------------------------------

ASR_ENGINES = {
    "whisper": lambda: _py_module("whisper") or shutil.which("whisper"),
    "faster_whisper": lambda: _py_module("faster_whisper"),
    "vosk": lambda: _py_module("vosk"),
}
TTS_ENGINES = {
    "espeak_ng": lambda: shutil.which("espeak-ng") or shutil.which("espeak"),
    "piper": lambda: shutil.which("piper"),
    "coqui": lambda: _py_module("TTS"),
}


def _py_module(name: str) -> bool:
    import importlib.util
    return importlib.util.find_spec(name) is not None


@dataclass(frozen=True)
class Capabilities:
    ffmpeg: bool
    asr: dict[str, bool]
    tts: dict[str, bool]

    @property
    def any_asr(self) -> bool:
        return any(self.asr.values())

    @property
    def any_tts_speech(self) -> bool:
        return any(self.tts.values())

    def report(self) -> dict:
        return {"ffmpeg": self.ffmpeg, "asr": self.asr, "tts": self.tts,
                "real_asr_available": self.any_asr, "real_speech_tts_available": self.any_tts_speech,
                "note": "test-audio TTS (silence, click track) is always available; "
                        "real ASR/TTS is BLOCKED until an engine is installed."}


def detect_capabilities() -> Capabilities:
    return Capabilities(
        ffmpeg=shutil.which("ffmpeg") is not None and shutil.which("ffprobe") is not None,
        asr={name: bool(probe()) for name, probe in ASR_ENGINES.items()},
        tts={name: bool(probe()) for name, probe in TTS_ENGINES.items()},
    )


# ---------------------------------------------------------------------------
# Provider interfaces
# ---------------------------------------------------------------------------

@dataclass(frozen=True)
class Transcript:
    words: tuple[Word, ...]
    language: str
    provider: str

    @property
    def text(self) -> str:
        return " ".join(w.text for w in self.words)


class ASRProvider(Protocol):
    name: str
    def available(self) -> bool: ...
    def transcribe(self, audio: str | Path, language: str | None = None) -> Transcript: ...


@dataclass(frozen=True)
class VoiceSpec:
    language: str = "en"
    voice: str = "default"
    rate: float = 1.0          # 1.0 = normal speaking rate
    sample_rate: int = 22050
    output_format: str = "wav"
    identity: str = ""         # free-form voice identity metadata
    pronunciation: dict = field(default_factory=dict)

    def validate(self) -> None:
        if self.rate <= 0:
            raise SpeechError("speaking rate must be positive")
        if self.sample_rate < 8000:
            raise SpeechError("sample rate is too low")
        if self.output_format not in {"wav"}:
            raise SpeechError("only wav output is supported by the built-in providers")


class TTSProvider(Protocol):
    name: str
    def available(self) -> bool: ...
    def synthesize(self, words: Sequence[Word], out: str | Path, voice: VoiceSpec) -> dict: ...


# ---------------------------------------------------------------------------
# Real, model-free TTS providers (genuine WAV output, not speech)
# ---------------------------------------------------------------------------

def _write_wav(path: Path, samples: Sequence[float], sample_rate: int) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with wave.open(str(path), "wb") as w:
        w.setnchannels(1)
        w.setsampwidth(2)
        w.setframerate(sample_rate)
        frames = b"".join(struct.pack("<h", int(max(-1.0, min(1.0, s)) * 32767)) for s in samples)
        w.writeframes(frames)


class SilenceTTS:
    """Generates silence spanning the words' duration. Useful as a timing bed. Real WAV, no speech."""
    name = "silence"

    def available(self) -> bool:
        return True

    def synthesize(self, words: Sequence[Word], out: str | Path, voice: VoiceSpec) -> dict:
        voice.validate()
        if not words:
            raise SpeechError("no words to synthesize")
        total = max(w.end for w in words)
        n = int(total * voice.sample_rate)
        _write_wav(Path(out), [0.0] * n, voice.sample_rate)
        return {"path": str(out), "provider": self.name, "seconds": total, "speech": False}


class ClickTrackTTS:
    """A short tone at each word's start, so audio aligns with the word timings. Real WAV, no speech."""
    name = "click_track"

    def available(self) -> bool:
        return True

    def synthesize(self, words: Sequence[Word], out: str | Path, voice: VoiceSpec) -> dict:
        voice.validate()
        if not words:
            raise SpeechError("no words to synthesize")
        total = max(w.end for w in words)
        sr = voice.sample_rate
        n = int(total * sr)
        samples = [0.0] * n
        for w in words:
            f = 320.0 + 40.0 * (len(w.text) % 6)       # vary pitch a little per word
            dur = min(0.12, (w.end - w.start) or 0.08)
            for i in range(int(dur * sr)):
                idx = int(w.start * sr) + i
                if idx < n:
                    env = math.sin(math.pi * i / (dur * sr))     # fade in/out
                    samples[idx] += 0.5 * env * math.sin(2 * math.pi * f * i / sr)
        _write_wav(Path(out), samples, sr)
        return {"path": str(out), "provider": self.name, "seconds": total, "speech": False}


TEST_TTS_PROVIDERS = {"silence": SilenceTTS(), "click_track": ClickTrackTTS()}


def get_tts_provider(name: str) -> TTSProvider:
    if name in TEST_TTS_PROVIDERS:
        return TEST_TTS_PROVIDERS[name]
    if name in TTS_ENGINES:
        raise SpeechError(f"TTS provider {name!r} is not installed (BLOCKED); "
                          f"install the engine and register a provider to enable it")
    raise SpeechError(f"unknown TTS provider {name!r}; available test providers: "
                      f"{sorted(TEST_TTS_PROVIDERS)}")


# ---------------------------------------------------------------------------
# External-timestamp fallback (works without any model)
# ---------------------------------------------------------------------------

def words_from_timestamps(items: Sequence[dict]) -> list[Word]:
    """Accept externally supplied timings: [{"text","start","end"}, ...]. Validates monotonic order."""
    words = []
    last_end = -1.0
    for i, it in enumerate(items):
        try:
            w = Word(text=str(it["text"]), start=float(it["start"]), end=float(it["end"]))
        except (KeyError, TypeError) as exc:
            raise SpeechError(f"item {i} needs text, start, end: {exc}") from exc
        if w.start < last_end - 1e-6:
            raise SpeechError(f"word {w.text!r} starts before the previous word ends")
        last_end = w.end
        words.append(w)
    if not words:
        raise SpeechError("no timestamped words supplied")
    return words


class ExternalTimestampASR:
    """A fallback 'ASR' that simply returns caller-supplied word timings. Always available."""
    name = "external_timestamps"

    def __init__(self, items: Sequence[dict], language: str = "und"):
        self._words = tuple(words_from_timestamps(items))
        self._language = language

    def available(self) -> bool:
        return True

    def transcribe(self, audio: str | Path, language: str | None = None) -> Transcript:
        return Transcript(words=self._words, language=language or self._language,
                          provider=self.name)


# ---------------------------------------------------------------------------
# Voice activity / silence detection (ffmpeg, no model)
# ---------------------------------------------------------------------------

@dataclass(frozen=True)
class Segment:
    start: float
    end: float
    kind: str   # "speech" | "silence"

    @property
    def duration(self) -> float:
        return self.end - self.start


def detect_silences(audio: str | Path, *, noise_db: float = -30.0,
                    min_silence: float = 0.35) -> list[tuple[float, float]]:
    """Silence intervals via ffmpeg silencedetect. Returns [(start, end), ...]."""
    if shutil.which("ffmpeg") is None:
        raise SpeechError("ffmpeg is required for silence detection")
    proc = subprocess.run(
        ["ffmpeg", "-hide_banner", "-nostats", "-i", str(audio),
         "-af", f"silencedetect=noise={noise_db}dB:d={min_silence}", "-f", "null", "-"],
        capture_output=True, text=True)
    silences = []
    start = None
    for line in proc.stderr.splitlines():
        m = re.search(r"silence_start:\s*(-?[\d.]+)", line)
        if m:
            start = float(m.group(1))
        m = re.search(r"silence_end:\s*(-?[\d.]+)", line)
        if m and start is not None:
            silences.append((max(0.0, start), float(m.group(1))))
            start = None
    return silences


def audio_duration(audio: str | Path) -> float:
    if shutil.which("ffprobe") is None:
        raise SpeechError("ffprobe is required")
    out = subprocess.run(["ffprobe", "-v", "error", "-show_entries", "format=duration",
                          "-of", "csv=p=0", str(audio)], capture_output=True, text=True, check=True)
    return float(out.stdout.strip())


def speech_segments(audio: str | Path, *, noise_db: float = -30.0,
                    min_silence: float = 0.35) -> list[Segment]:
    """Invert silence intervals to get speech/silence segments across the whole file."""
    total = audio_duration(audio)
    silences = detect_silences(audio, noise_db=noise_db, min_silence=min_silence)
    segs: list[Segment] = []
    cursor = 0.0
    for s0, s1 in silences:
        s0, s1 = max(0.0, s0), min(total, s1)
        if s0 > cursor + 1e-3:
            segs.append(Segment(cursor, s0, "speech"))
        segs.append(Segment(s0, s1, "silence"))
        cursor = s1
    if cursor < total - 1e-3:
        segs.append(Segment(cursor, total, "speech"))
    return segs


# ---------------------------------------------------------------------------
# Word / phrase / sentence timing from words
# ---------------------------------------------------------------------------

SENTENCE_END = re.compile(r"[.!?…]$")


@dataclass(frozen=True)
class Phrase:
    start: float
    end: float
    words: tuple[Word, ...]

    @property
    def text(self) -> str:
        return " ".join(w.text for w in self.words)


def sentence_boundaries(words: Sequence[Word]) -> list[Phrase]:
    """Group words into sentences using terminal punctuation."""
    out: list[Phrase] = []
    cur: list[Word] = []
    for w in words:
        cur.append(w)
        if SENTENCE_END.search(w.text.strip()):
            out.append(Phrase(cur[0].start, cur[-1].end, tuple(cur)))
            cur = []
    if cur:
        out.append(Phrase(cur[0].start, cur[-1].end, tuple(cur)))
    return out


def phrase_boundaries(words: Sequence[Word], *, max_gap: float = 0.4,
                      max_words: int = 7) -> list[Phrase]:
    """Split words into phrases at long gaps, sentence ends, or a word-count cap."""
    out: list[Phrase] = []
    cur: list[Word] = []
    for i, w in enumerate(words):
        if cur:
            gap = w.start - cur[-1].end
            if gap > max_gap or len(cur) >= max_words or SENTENCE_END.search(cur[-1].text.strip()):
                out.append(Phrase(cur[0].start, cur[-1].end, tuple(cur)))
                cur = []
        cur.append(w)
    if cur:
        out.append(Phrase(cur[0].start, cur[-1].end, tuple(cur)))
    return out


def silences_between_words(words: Sequence[Word], *, min_gap: float = 0.3) -> list[tuple[float, float]]:
    """Gaps between consecutive words longer than min_gap (pause detection from timings)."""
    gaps = []
    for a, b in zip(words, words[1:]):
        if b.start - a.end >= min_gap:
            gaps.append((a.end, b.start))
    return gaps


def subtitle_timeline(words: Sequence[Word], *, max_gap: float = 0.4, max_words: int = 7) -> list[dict]:
    """A simple cue timeline from word timings, for callers that only need start/end/text."""
    return [{"start": p.start, "end": p.end, "text": p.text}
            for p in phrase_boundaries(words, max_gap=max_gap, max_words=max_words)]
