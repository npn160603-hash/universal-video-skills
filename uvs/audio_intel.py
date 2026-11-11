"""Music intelligence, emotional sound direction, gain automation, audio QA (Phase 8.2-8.5).

Tempo and beats come from an onset envelope computed on decoded PCM (ffmpeg -> numpy): short-time
RMS, positive flux, peak picking, median inter-onset interval. Verified on synthetic click tracks
at known BPM. Loudness, true peak, clipping and silence are measured with ffmpeg (ebur128,
astats, volumedetect, silencedetect) — real measurements, not estimates.

Nothing here invents numbers: every measurement runs a tool on the actual audio.
"""
from __future__ import annotations

import json
import math
import re
import shutil
import subprocess
from dataclasses import dataclass, field
from pathlib import Path
from typing import Sequence

import numpy as np

DEFAULT_SR = 22050
HOP = 512


class AudioIntelError(ValueError):
    pass


def _need_ffmpeg() -> None:
    if shutil.which("ffmpeg") is None or shutil.which("ffprobe") is None:
        raise AudioIntelError("ffmpeg and ffprobe are required")


def decode_mono(path: str | Path, sr: int = DEFAULT_SR) -> np.ndarray:
    _need_ffmpeg()
    out = subprocess.run(["ffmpeg", "-v", "error", "-i", str(path), "-ac", "1", "-ar", str(sr),
                          "-f", "f32le", "-"], capture_output=True)
    if out.returncode != 0:
        raise AudioIntelError(f"decode failed: {out.stderr.decode('utf-8','replace')[-300:]}")
    return np.frombuffer(out.stdout, dtype=np.float32)


# ---------------------------------------------------------------------------
# Onsets, tempo, beats, energy
# ---------------------------------------------------------------------------

def _flux(y: np.ndarray, sr: int, hop: int) -> tuple[np.ndarray, float]:
    frames = max(1, (len(y) - hop) // hop)
    rms = np.array([np.sqrt(np.mean(y[i * hop:(i + 1) * hop] ** 2) + 1e-12) for i in range(frames)])
    flux = np.diff(rms, prepend=rms[:1])
    flux[flux < 0] = 0.0
    return flux, sr / hop


def onset_times(path: str | Path, *, sr: int = DEFAULT_SR, hop: int = HOP,
                sensitivity: float = 1.0) -> list[float]:
    """Times (s) of detected onsets: peaks in the positive RMS flux above an adaptive threshold."""
    y = decode_mono(path, sr)
    flux, fps = _flux(y, sr, hop)
    if flux.size < 3:
        return []
    thr = flux.mean() + sensitivity * flux.std()
    peaks = []
    for i in range(1, len(flux) - 1):
        if flux[i] > thr and flux[i] >= flux[i - 1] and flux[i] > flux[i + 1]:
            peaks.append(i / fps)
    return peaks


@dataclass(frozen=True)
class Tempo:
    bpm: float
    onset_count: int
    confidence: float   # 0..1 from the consistency of inter-onset intervals


def estimate_tempo(path: str | Path, *, sr: int = DEFAULT_SR, hop: int = HOP) -> Tempo:
    ons = onset_times(path, sr=sr, hop=hop)
    if len(ons) < 2:
        raise AudioIntelError("not enough onsets to estimate tempo")
    iois = np.diff(ons)
    med = float(np.median(iois))
    if med <= 0:
        raise AudioIntelError("degenerate inter-onset interval")
    bpm = 60.0 / med
    # confidence: fraction of IOIs within 15% of the median (tolerant of missed/extra onsets)
    close = np.mean(np.abs(iois - med) <= 0.15 * med)
    return Tempo(bpm=bpm, onset_count=len(ons), confidence=float(close))


def detect_beats(path: str | Path, *, sr: int = DEFAULT_SR, hop: int = HOP) -> list[float]:
    """Beat times: onsets, used directly. For music with a steady pulse these are the beats."""
    return onset_times(path, sr=sr, hop=hop)


def beat_aligned_cuts(beats: Sequence[float], desired_times: Sequence[float],
                      *, max_shift: float = 0.25) -> list[float]:
    """Snap each desired cut to the nearest beat within max_shift; otherwise keep the desired time."""
    if not beats:
        return list(desired_times)
    beats = sorted(beats)
    out = []
    for t in desired_times:
        nearest = min(beats, key=lambda b: abs(b - t))
        out.append(nearest if abs(nearest - t) <= max_shift else t)
    return out


@dataclass(frozen=True)
class Envelope:
    times: tuple[float, ...]
    rms: tuple[float, ...]

    def peak(self) -> float:
        return max(self.rms) if self.rms else 0.0


def energy_envelope(path: str | Path, *, sr: int = DEFAULT_SR, window: float = 0.1) -> Envelope:
    y = decode_mono(path, sr)
    hop = max(1, int(window * sr))
    frames = max(1, len(y) // hop)
    times, rms = [], []
    for i in range(frames):
        seg = y[i * hop:(i + 1) * hop]
        rms.append(float(np.sqrt(np.mean(seg ** 2) + 1e-12)))
        times.append(i * hop / sr)
    return Envelope(tuple(times), tuple(rms))


# ---------------------------------------------------------------------------
# Emotional sound direction (8.3)
# ---------------------------------------------------------------------------

@dataclass(frozen=True)
class SoundDirection:
    emotion: str
    music_gain_db: float
    ambience_gain_db: float
    sfx_gain_db: float
    duck_ratio: float
    silence_before_key_moment: float   # seconds of held silence for emphasis
    notes: str


EMOTION_SOUND = {
    "reflective": SoundDirection("reflective", -20.0, -24.0, -12.0, 8.0, 0.6,
                                 "minimal music, gentle ambience, restrained effects"),
    "suspense": SoundDirection("suspense", -16.0, -20.0, -6.0, 6.0, 0.9,
                               "low-frequency ambience, rising tension, meaningful silence"),
    "educational": SoundDirection("educational", -18.0, -26.0, -10.0, 9.0, 0.2,
                                  "clear narration, rhythmic but unobtrusive music"),
    "inspirational": SoundDirection("inspirational", -12.0, -24.0, -8.0, 5.0, 0.3,
                                    "gradual musical build, controlled emotional payoff"),
    "neutral": SoundDirection("neutral", -16.0, -24.0, -8.0, 6.0, 0.0,
                              "balanced bed under narration"),
}


def sound_direction(emotion: str) -> SoundDirection:
    return EMOTION_SOUND.get(emotion, EMOTION_SOUND["neutral"])


# ---------------------------------------------------------------------------
# Gain automation (8.4)
# ---------------------------------------------------------------------------

@dataclass(frozen=True)
class GainPoint:
    time: float
    gain_db: float


@dataclass
class GainAutomation:
    points: tuple[GainPoint, ...]

    def __post_init__(self):
        if len(self.points) < 1:
            raise AudioIntelError("gain automation needs at least one point")
        if list(self.points) != sorted(self.points, key=lambda p: p.time):
            raise AudioIntelError("gain points must be in time order")

    def gain_at(self, t: float) -> float:
        pts = self.points
        if t <= pts[0].time:
            return pts[0].gain_db
        if t >= pts[-1].time:
            return pts[-1].gain_db
        for a, b in zip(pts, pts[1:]):
            if a.time <= t <= b.time:
                f = (t - a.time) / (b.time - a.time) if b.time > a.time else 0.0
                return a.gain_db + (b.gain_db - a.gain_db) * f
        return pts[-1].gain_db

    def to_volume_expr(self) -> str:
        """An ffmpeg volume expression (linear) piecewise-interpolating the dB points over time."""
        # Build nested if() across segments; volume filter evaluates 'volume' expr per sample with t.
        def lin(db): return 10 ** (db / 20.0)
        pts = self.points
        expr = f"{lin(pts[-1].gain_db):.6f}"
        for a, b in reversed(list(zip(pts, pts[1:]))):
            la, lb = lin(a.gain_db), lin(b.gain_db)
            seg = (f"({la:.6f}+({lb - la:.6f})*(t-{a.time:.6f})/{max(1e-6, b.time - a.time):.6f})")
            expr = f"if(lt(t,{b.time:.6f}),{seg},{expr})"
        expr = f"if(lt(t,{pts[0].time:.6f}),{lin(pts[0].gain_db):.6f},{expr})"
        return expr


# ---------------------------------------------------------------------------
# Audio QA (8.5)
# ---------------------------------------------------------------------------

@dataclass(frozen=True)
class LoudnessReport:
    integrated_lufs: float
    loudness_range: float
    true_peak_dbtp: float


def measure_loudness(path: str | Path) -> LoudnessReport:
    """Integrated loudness, LRA and true peak via ffmpeg ebur128."""
    _need_ffmpeg()
    proc = subprocess.run(["ffmpeg", "-hide_banner", "-nostats", "-i", str(path),
                           "-af", "ebur128=peak=true", "-f", "null", "-"],
                          capture_output=True, text=True)
    txt = proc.stderr
    def grab(label):
        m = re.findall(rf"{label}:\s*(-?[\d.]+|-inf)", txt)
        return float(m[-1]) if m and m[-1] != "-inf" else float("-inf")
    # ebur128 summary block uses "I:", "LRA:", "Peak:"
    integrated = grab("I")
    lra = grab("LRA")
    peak = grab("Peak")
    if integrated == float("-inf") and peak == float("-inf"):
        raise AudioIntelError(f"loudness measurement failed: {txt[-300:]}")
    return LoudnessReport(integrated, lra, peak)


def detect_clipping(path: str | Path, *, sr: int = 48000, threshold: float = 0.999) -> dict:
    """Count samples at or above full scale (clipping)."""
    y = decode_mono(path, sr)
    clipped = int(np.sum(np.abs(y) >= threshold))
    return {"clipped_samples": clipped, "total_samples": int(y.size),
            "clipping_fraction": clipped / y.size if y.size else 0.0,
            "clips": clipped > 0}


def detect_silence_spans(path: str | Path, *, noise_db: float = -50.0,
                         min_silence: float = 0.5) -> list[tuple[float, float]]:
    from uvs.speech import detect_silences
    return detect_silences(path, noise_db=noise_db, min_silence=min_silence)


def voice_music_balance(voice: str | Path, music: str | Path) -> dict:
    """Difference in integrated loudness between a voice bed and a music bed (voice should lead)."""
    v = measure_loudness(voice).integrated_lufs
    m = measure_loudness(music).integrated_lufs
    return {"voice_lufs": v, "music_lufs": m, "voice_minus_music_db": v - m,
            "voice_leads": v > m}


@dataclass(frozen=True)
class AudioQAReport:
    loudness: LoudnessReport
    clipping: dict
    silence_spans: list
    target_lufs: float

    def issues(self) -> list[str]:
        out = []
        if self.clipping["clips"]:
            out.append(f"clipping: {self.clipping['clipped_samples']} samples at full scale")
        if self.loudness.true_peak_dbtp > -1.0:
            out.append(f"true peak {self.loudness.true_peak_dbtp:.1f} dBTP exceeds -1.0")
        if self.loudness.integrated_lufs != float("-inf") and \
                abs(self.loudness.integrated_lufs - self.target_lufs) > 2.0:
            out.append(f"loudness {self.loudness.integrated_lufs:.1f} LUFS is far from "
                       f"target {self.target_lufs:.1f}")
        return out


def audio_qa(path: str | Path, *, target_lufs: float = -14.0) -> AudioQAReport:
    return AudioQAReport(loudness=measure_loudness(path), clipping=detect_clipping(path),
                         silence_spans=detect_silence_spans(path), target_lufs=target_lufs)
