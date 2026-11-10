"""Measured audio tests on synthetic WAV files generated here (a pulsed tone as voice, a steady tone as music)."""
import array
import math
import shutil
import subprocess
import tempfile
import unittest
import wave
from pathlib import Path

from uvs import audio as A
from uvs import qa as Q

RATE = 48000
HAS_FFMPEG = shutil.which("ffmpeg") is not None


def _write_wav(path: Path, seconds: float, freq: float, amp: float, gate=None):
    n = int(seconds * RATE)
    samples = array.array("h")
    for i in range(n):
        t = i / RATE
        g = 1.0 if gate is None or gate(t) else 0.0
        samples.append(int(32767 * amp * g * math.sin(2 * math.pi * freq * t)))
    with wave.open(str(path), "wb") as w:
        w.setnchannels(1)
        w.setsampwidth(2)
        w.setframerate(RATE)
        w.writeframes(samples.tobytes())
    return path


def _read_mono(path: Path):
    raw = subprocess.run(["ffmpeg", "-hide_banner", "-loglevel", "error", "-i", str(path),
                          "-f", "s16le", "-ac", "1", "-ar", str(RATE), "-"],
                         capture_output=True, check=True).stdout
    arr = array.array("h")
    arr.frombytes(raw)
    return arr


def _rms_db(samples, t0, t1):
    seg = samples[int(t0 * RATE): int(t1 * RATE)]
    if not seg:
        return -999.0
    ms = sum((s / 32768.0) ** 2 for s in seg) / len(seg)
    return 10 * math.log10(ms) if ms > 0 else -999.0


def _ebur(path: Path):
    proc = subprocess.run(["ffmpeg", "-hide_banner", "-nostats", "-i", str(path), "-map", "0:a:0",
                           "-af", "ebur128=peak=true", "-vn", "-f", "null", "-"],
                          capture_output=True, text=True, check=True)
    return Q.parse_ebur128_summary(proc.stderr)


@unittest.skipUnless(HAS_FFMPEG, "ffmpeg not installed")
class AudioRenderTests(unittest.TestCase):
    def setUp(self):
        self._tmp = tempfile.TemporaryDirectory()
        self.dir = Path(self._tmp.name)
        # Voice: 330 Hz, on for [1,2), [3,4), [5,6), [7,8) seconds, off otherwise.
        self.voice = _write_wav(self.dir / "voice.wav", 8.0, 330, 0.3,
                                gate=lambda t: int(t) % 2 == 1)
        self.music = _write_wav(self.dir / "music.wav", 8.0, 220, 0.2)
        self.ambience = _write_wav(self.dir / "amb.wav", 2.0, 440, 0.02)

    def tearDown(self):
        self._tmp.cleanup()

    def test_ducking_lowers_music_under_voice_by_several_db(self):
        ducked = A.duck_music(self.music, self.voice, self.dir / "ducked.wav")
        samples = _read_mono(ducked)
        voice_off = _rms_db(samples, 0.2, 0.8)   # music alone
        voice_on = _rms_db(samples, 1.2, 1.8)    # music under voice
        self.assertGreater(voice_off - voice_on, 4.0)

    def test_mix_hits_loudness_target_and_limits_true_peak(self):
        out = self.dir / "mix.m4a"
        clips = [
            A.AudioClip("VOICE", str(self.voice)),
            A.AudioClip("MUSIC", str(self.music)),
            A.AudioClip("AMBIENCE", str(self.ambience), loop=True, duration=8.0),
        ]
        result = A.mix_to_file(clips, out, target_lufs=-14.0, true_peak=-1.5, duration=8.0)
        self.assertTrue(out.exists())
        measured = _ebur(out)
        self.assertAlmostEqual(measured["integrated_lufs"], -14.0, delta=1.0)
        self.assertLessEqual(measured["true_peak_dbtp"], -1.0)
        self.assertIn("measured_input", result)

    def test_sfx_placed_at_its_start_time(self):
        sfx = _write_wav(self.dir / "sfx.wav", 0.3, 1000, 0.5)
        out = self.dir / "sfx_mix.wav"
        clips = [A.AudioClip("SFX", str(sfx), start=2.0)]
        inputs, graph, label = A.build_mix_graph(clips)
        proc = subprocess.run(["ffmpeg", "-hide_banner", "-loglevel", "error", "-y", *inputs,
                               "-filter_complex", graph, "-map", f"[{label}]", "-ar", str(RATE),
                               str(out)], capture_output=True, text=True)
        self.assertEqual(proc.returncode, 0, proc.stderr)
        samples = _read_mono(out)
        self.assertLess(_rms_db(samples, 0.0, 1.8), -60.0)
        self.assertGreater(_rms_db(samples, 2.05, 2.25), -30.0)


class AudioGraphTests(unittest.TestCase):
    def setUp(self):
        self._tmp = tempfile.TemporaryDirectory()
        self.dir = Path(self._tmp.name)
        self.f = _write_wav(self.dir / "f.wav", 0.5, 440, 0.1)

    def tearDown(self):
        self._tmp.cleanup()

    def test_unknown_category_and_missing_file_are_rejected(self):
        with self.assertRaises(ValueError):
            A.build_mix_graph([A.AudioClip("BASS", str(self.f))])
        with self.assertRaises(FileNotFoundError):
            A.build_mix_graph([A.AudioClip("VOICE", "/no/such.wav")])

    def test_music_is_sidechained_only_when_voice_is_present(self):
        _, with_voice, _ = A.build_mix_graph([A.AudioClip("VOICE", str(self.f)),
                                              A.AudioClip("MUSIC", str(self.f))])
        _, without_voice, _ = A.build_mix_graph([A.AudioClip("MUSIC", str(self.f))])
        self.assertIn("sidechaincompress", with_voice)
        self.assertNotIn("sidechaincompress", without_voice)

    def test_ducking_can_be_disabled_per_clip(self):
        _, graph, _ = A.build_mix_graph([A.AudioClip("VOICE", str(self.f)),
                                         A.AudioClip("MUSIC", str(self.f), duck=False)])
        self.assertNotIn("sidechaincompress", graph)
        self.assertNotIn("asplit", graph)

    def test_loop_flag_adds_stream_loop_input(self):
        inputs, _, _ = A.build_mix_graph([A.AudioClip("AMBIENCE", str(self.f), loop=True)])
        self.assertIn("-stream_loop", inputs)

    def test_denoise_is_opt_in(self):
        _, plain, _ = A.build_mix_graph([A.AudioClip("VOICE", str(self.f))])
        _, dn, _ = A.build_mix_graph([A.AudioClip("VOICE", str(self.f))], denoise=True)
        self.assertNotIn("afftdn", plain)
        self.assertIn("afftdn", dn)

    def test_output_is_limited_by_alimiter(self):
        _, graph, label = A.build_mix_graph([A.AudioClip("VOICE", str(self.f))])
        self.assertIn("alimiter", graph)
        self.assertEqual(label, "mix")


if __name__ == "__main__":
    unittest.main()
