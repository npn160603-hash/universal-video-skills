"""Speech interfaces: capability detection, test-audio TTS, external fallback, segmentation."""
import shutil
import tempfile
import unittest
import wave
from pathlib import Path

from uvs.captions import Word
from uvs.speech import (detect_capabilities, Capabilities, VoiceSpec, SilenceTTS, ClickTrackTTS,
                        get_tts_provider, words_from_timestamps, ExternalTimestampASR,
                        sentence_boundaries, phrase_boundaries, silences_between_words,
                        subtitle_timeline, SpeechError, Transcript)

HAS_FFMPEG = shutil.which("ffmpeg") is not None and shutil.which("ffprobe") is not None


class CapabilityTests(unittest.TestCase):
    def test_detection_reports_known_engines(self):
        caps = detect_capabilities()
        self.assertIn("whisper", caps.asr)
        self.assertIn("espeak_ng", caps.tts)
        r = caps.report()
        self.assertEqual(r["real_asr_available"], caps.any_asr)

    def test_no_bundled_real_engine_is_claimed_without_one(self):
        caps = detect_capabilities()
        # In this environment no real engine is installed; detection must not claim otherwise.
        self.assertEqual(caps.any_asr, any(caps.asr.values()))
        self.assertEqual(caps.any_tts_speech, any(caps.tts.values()))


class TestTTSProviderTests(unittest.TestCase):
    def setUp(self):
        self._tmp = tempfile.TemporaryDirectory()
        self.dir = Path(self._tmp.name)
        self.words = [Word("one", 0.0, 0.4), Word("two", 1.0, 1.4), Word("three", 2.0, 2.6)]

    def tearDown(self):
        self._tmp.cleanup()

    def test_silence_tts_writes_real_wav_of_the_right_length(self):
        info = SilenceTTS().synthesize(self.words, self.dir / "s.wav", VoiceSpec(sample_rate=16000))
        self.assertFalse(info["speech"])
        with wave.open(str(self.dir / "s.wav")) as w:
            self.assertEqual(w.getframerate(), 16000)
            self.assertAlmostEqual(w.getnframes() / 16000, 2.6, delta=0.01)

    def test_click_track_has_energy_at_word_starts(self):
        ClickTrackTTS().synthesize(self.words, self.dir / "c.wav", VoiceSpec(sample_rate=16000))
        with wave.open(str(self.dir / "c.wav")) as w:
            import struct
            frames = w.readframes(w.getnframes())
            amp = struct.unpack("<%dh" % (len(frames) // 2), frames)
        # energy near t=1.0 (word "two") should exceed energy at t=0.7 (a gap)
        at_word = sum(abs(a) for a in amp[16000:16000 + 800])
        at_gap = sum(abs(a) for a in amp[int(0.7 * 16000):int(0.7 * 16000) + 800])
        self.assertGreater(at_word, at_gap)

    def test_empty_words_rejected(self):
        with self.assertRaises(SpeechError):
            SilenceTTS().synthesize([], self.dir / "x.wav", VoiceSpec())

    def test_voice_spec_validation(self):
        with self.assertRaises(SpeechError):
            VoiceSpec(rate=0).validate()
        with self.assertRaises(SpeechError):
            VoiceSpec(sample_rate=1000).validate()

    def test_get_provider_blocks_unavailable_real_engine(self):
        self.assertIs(type(get_tts_provider("silence")), SilenceTTS)
        with self.assertRaises(SpeechError):
            get_tts_provider("espeak_ng")   # known engine, not installed -> BLOCKED
        with self.assertRaises(SpeechError):
            get_tts_provider("nonsense")


class ExternalFallbackTests(unittest.TestCase):
    def test_timestamps_validated_and_ordered(self):
        words = words_from_timestamps([{"text": "a", "start": 0, "end": 0.5},
                                       {"text": "b", "start": 0.6, "end": 1.0}])
        self.assertEqual([w.text for w in words], ["a", "b"])
        with self.assertRaises(SpeechError):
            words_from_timestamps([{"text": "a", "start": 0, "end": 1.0},
                                   {"text": "b", "start": 0.5, "end": 1.2}])  # overlaps backwards
        with self.assertRaises(SpeechError):
            words_from_timestamps([{"text": "a", "start": 0}])  # missing end

    def test_external_asr_returns_supplied_words(self):
        asr = ExternalTimestampASR([{"text": "hello", "start": 0, "end": 0.5}], language="en")
        t = asr.transcribe("anything.wav")
        self.assertIsInstance(t, Transcript)
        self.assertEqual(t.text, "hello")
        self.assertEqual(t.provider, "external_timestamps")


class SegmentationTests(unittest.TestCase):
    def setUp(self):
        self.ws = [Word("I", 0, 0.2), Word("said", 0.2, 0.5), Word("no.", 0.5, 0.9),
                   Word("Then", 1.5, 1.8), Word("I", 1.8, 2.0), Word("left.", 2.0, 2.4)]

    def test_sentences_split_on_terminal_punctuation(self):
        self.assertEqual([p.text for p in sentence_boundaries(self.ws)], ["I said no.", "Then I left."])

    def test_phrases_split_on_long_gap(self):
        phrases = phrase_boundaries(self.ws, max_gap=0.4, max_words=10)
        self.assertEqual(len(phrases), 2)  # gap of 0.6s between "no." and "Then"

    def test_phrases_split_on_word_cap(self):
        words = [Word(f"w{i}", i * 0.3, i * 0.3 + 0.25) for i in range(10)]
        phrases = phrase_boundaries(words, max_gap=5.0, max_words=4)
        self.assertTrue(all(len(p.words) <= 4 for p in phrases))

    def test_pause_detection(self):
        self.assertEqual(silences_between_words(self.ws, min_gap=0.3), [(0.9, 1.5)])

    def test_subtitle_timeline_shape(self):
        tl = subtitle_timeline(self.ws)
        self.assertTrue(all({"start", "end", "text"} <= set(c) for c in tl))


@unittest.skipUnless(HAS_FFMPEG, "ffmpeg not installed")
class SilenceDetectionTests(unittest.TestCase):
    def setUp(self):
        self._tmp = tempfile.TemporaryDirectory()
        self.dir = Path(self._tmp.name)

    def tearDown(self):
        self._tmp.cleanup()

    def test_click_track_silences_fall_between_words(self):
        from uvs.speech import detect_silences, speech_segments
        words = [Word("one", 0.0, 0.4), Word("two", 1.0, 1.4), Word("three", 2.0, 2.6)]
        ClickTrackTTS().synthesize(words, self.dir / "c.wav", VoiceSpec(sample_rate=16000))
        sils = detect_silences(self.dir / "c.wav", noise_db=-40, min_silence=0.3)
        self.assertGreaterEqual(len(sils), 2)
        # a silence should cover the gap around t=0.6..0.9
        self.assertTrue(any(s0 < 0.6 < s1 for s0, s1 in sils))
        segs = speech_segments(self.dir / "c.wav", noise_db=-40, min_silence=0.3)
        self.assertTrue(any(s.kind == "speech" for s in segs))
        self.assertTrue(any(s.kind == "silence" for s in segs))


if __name__ == "__main__":
    unittest.main()
