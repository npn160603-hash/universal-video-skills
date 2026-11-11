"""Phase 8 with real audio: tempo on click tracks, loudness/clipping QA, voice-chain mix."""
import math
import shutil
import struct
import tempfile
import unittest
import wave
from pathlib import Path

import numpy as np

from uvs.audio_intel import (estimate_tempo, detect_beats, energy_envelope, measure_loudness,
                             detect_clipping, voice_music_balance, audio_qa)
from uvs.audio import AudioClip, build_mix_graph, mix_to_file

HAS_FFMPEG = shutil.which("ffmpeg") is not None and shutil.which("ffprobe") is not None
SR = 22050


def click_track(path: Path, bpm: float, seconds: float = 8.0, sr: int = SR):
    period = 60.0 / bpm
    n = int(seconds * sr)
    s = np.zeros(n)
    for k in range(int(seconds / period)):
        t0 = int(k * period * sr)
        for i in range(int(0.02 * sr)):
            if t0 + i < n:
                s[t0 + i] += 0.8 * math.sin(2 * math.pi * 1000 * i / sr) * math.exp(-i / (0.005 * sr))
    _write(path, s, sr)


def tone(path: Path, freq: float, amp: float, seconds: float = 3.0, sr: int = 48000):
    n = int(seconds * sr)
    _write(path, amp * np.sin(2 * math.pi * freq * np.arange(n) / sr), sr)


def _write(path: Path, samples, sr):
    with wave.open(str(path), "wb") as w:
        w.setnchannels(1)
        w.setsampwidth(2)
        w.setframerate(sr)
        w.writeframes(b"".join(struct.pack("<h", int(max(-1, min(1, x)) * 32767)) for x in samples))


@unittest.skipUnless(HAS_FFMPEG, "ffmpeg not installed")
class TempoTests(unittest.TestCase):
    def setUp(self):
        self._tmp = tempfile.TemporaryDirectory()
        self.dir = Path(self._tmp.name)

    def tearDown(self):
        self._tmp.cleanup()

    def test_tempo_within_tolerance_for_known_bpm(self):
        for bpm in (90, 120, 140):
            with self.subTest(bpm=bpm):
                f = self.dir / f"c{bpm}.wav"
                click_track(f, bpm)
                t = estimate_tempo(f)
                self.assertLess(abs(t.bpm - bpm), bpm * 0.05, f"got {t.bpm:.1f}")
                self.assertGreater(t.confidence, 0.8)

    def test_beats_are_evenly_spaced_at_120(self):
        f = self.dir / "c120.wav"
        click_track(f, 120)
        beats = detect_beats(f)
        self.assertGreaterEqual(len(beats), 10)
        gaps = np.diff(beats)
        self.assertAlmostEqual(float(np.median(gaps)), 0.5, delta=0.05)

    def test_energy_envelope_tracks_clicks(self):
        f = self.dir / "c120.wav"
        click_track(f, 120)
        env = energy_envelope(f, window=0.1)
        self.assertGreater(env.peak(), 0.0)


@unittest.skipUnless(HAS_FFMPEG, "ffmpeg not installed")
class AudioQATests(unittest.TestCase):
    def setUp(self):
        self._tmp = tempfile.TemporaryDirectory()
        self.dir = Path(self._tmp.name)

    def tearDown(self):
        self._tmp.cleanup()

    def test_loudness_is_measured(self):
        f = self.dir / "v.wav"
        tone(f, 440, 0.3)
        r = measure_loudness(f)
        self.assertLess(r.integrated_lufs, 0)
        self.assertLess(r.true_peak_dbtp, 6)

    def test_clipping_detected_only_when_present(self):
        clean = self.dir / "clean.wav"
        hot = self.dir / "hot.wav"
        tone(clean, 300, 0.3)
        tone(hot, 300, 1.5)   # amplitude > 1 clips
        self.assertFalse(detect_clipping(clean)["clips"])
        self.assertTrue(detect_clipping(hot)["clips"])

    def test_voice_music_balance_detects_loud_music(self):
        v = self.dir / "v.wav"
        m = self.dir / "m.wav"
        tone(v, 440, 0.2)
        tone(m, 220, 0.6)
        bal = voice_music_balance(v, m)
        self.assertFalse(bal["voice_leads"])  # music is louder here

    def test_qa_report_flags_clipped_file(self):
        hot = self.dir / "hot.wav"
        tone(hot, 300, 1.5)
        self.assertTrue(audio_qa(hot).issues())


@unittest.skipUnless(HAS_FFMPEG, "ffmpeg not installed")
class VoiceChainMixTests(unittest.TestCase):
    def setUp(self):
        self._tmp = tempfile.TemporaryDirectory()
        self.dir = Path(self._tmp.name)

    def tearDown(self):
        self._tmp.cleanup()

    def test_voice_chain_with_eq_and_deess_mixes_to_target(self):
        voice = self.dir / "voice.wav"
        music = self.dir / "music.wav"
        tone(voice, 300, 0.3, seconds=2.0)
        tone(music, 180, 0.4, seconds=2.0)
        inp, graph, _ = build_mix_graph(
            [AudioClip("VOICE", str(voice)), AudioClip("MUSIC", str(music))], deess=True)
        self.assertIn("deesser", graph)
        self.assertIn("equalizer", graph)
        out = self.dir / "mix.m4a"
        result = mix_to_file([AudioClip("VOICE", str(voice)), AudioClip("MUSIC", str(music))],
                             out, target_lufs=-16.0, duration=2.0)
        self.assertTrue(Path(result["output"]).exists())
        measured = measure_loudness(out)
        self.assertLess(abs(measured.integrated_lufs - (-16.0)), 2.5)


if __name__ == "__main__":
    unittest.main()
