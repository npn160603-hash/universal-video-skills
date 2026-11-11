"""Music intelligence and audio helpers that need no ffmpeg: cuts, gain, direction, QA logic."""
import unittest

from uvs.audio_intel import (beat_aligned_cuts, GainAutomation, GainPoint, sound_direction,
                             EMOTION_SOUND, AudioIntelError, LoudnessReport, AudioQAReport)


class BeatCutTests(unittest.TestCase):
    def test_cut_snaps_to_nearest_beat_within_range(self):
        beats = [0.5, 1.0, 1.5, 2.0, 2.5]
        self.assertEqual(beat_aligned_cuts(beats, [1.1, 2.3]), [1.0, 2.5])

    def test_cut_kept_when_no_beat_is_close(self):
        beats = [0.5, 1.0]
        self.assertEqual(beat_aligned_cuts(beats, [5.0], max_shift=0.25), [5.0])

    def test_no_beats_returns_desired(self):
        self.assertEqual(beat_aligned_cuts([], [1.0, 2.0]), [1.0, 2.0])


class GainAutomationTests(unittest.TestCase):
    def test_interpolates_between_points(self):
        ga = GainAutomation((GainPoint(0, -20), GainPoint(1, 0), GainPoint(2, -20)))
        self.assertEqual(ga.gain_at(0.0), -20)
        self.assertEqual(ga.gain_at(0.5), -10)
        self.assertEqual(ga.gain_at(1.0), 0)
        self.assertEqual(ga.gain_at(1.5), -10)

    def test_holds_before_first_and_after_last(self):
        ga = GainAutomation((GainPoint(1, -6), GainPoint(2, 0)))
        self.assertEqual(ga.gain_at(0.0), -6)
        self.assertEqual(ga.gain_at(5.0), 0)

    def test_out_of_order_points_rejected(self):
        with self.assertRaises(AudioIntelError):
            GainAutomation((GainPoint(2, 0), GainPoint(1, -6)))

    def test_volume_expression_is_well_formed(self):
        expr = GainAutomation((GainPoint(0, -20), GainPoint(1, 0))).to_volume_expr()
        self.assertIn("if(lt(t,", expr)
        self.assertEqual(expr.count("("), expr.count(")"))


class SoundDirectionTests(unittest.TestCase):
    def test_known_emotions_have_direction(self):
        for e in ("reflective", "suspense", "educational", "inspirational"):
            self.assertEqual(sound_direction(e).emotion, e)

    def test_unknown_emotion_falls_back_to_neutral(self):
        self.assertEqual(sound_direction("confused").emotion, "neutral")

    def test_suspense_holds_more_silence_than_educational(self):
        self.assertGreater(sound_direction("suspense").silence_before_key_moment,
                           sound_direction("educational").silence_before_key_moment)

    def test_reflective_music_is_quieter_than_inspirational(self):
        self.assertLess(sound_direction("reflective").music_gain_db,
                        sound_direction("inspirational").music_gain_db)


class QALogicTests(unittest.TestCase):
    def test_issues_flag_clipping_and_hot_peak_and_loudness(self):
        report = AudioQAReport(
            loudness=LoudnessReport(integrated_lufs=-2.0, loudness_range=5.0, true_peak_dbtp=0.0),
            clipping={"clips": True, "clipped_samples": 100},
            silence_spans=[], target_lufs=-14.0)
        issues = report.issues()
        self.assertTrue(any("clipping" in i for i in issues))
        self.assertTrue(any("true peak" in i for i in issues))
        self.assertTrue(any("loudness" in i for i in issues))

    def test_clean_report_has_no_issues(self):
        report = AudioQAReport(
            loudness=LoudnessReport(integrated_lufs=-14.0, loudness_range=7.0, true_peak_dbtp=-1.5),
            clipping={"clips": False, "clipped_samples": 0},
            silence_spans=[], target_lufs=-14.0)
        self.assertEqual(report.issues(), [])


if __name__ == "__main__":
    unittest.main()
