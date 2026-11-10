import tempfile
import unittest
from fractions import Fraction
from pathlib import Path

from uvs import timeline as T


def _tl(*clips, kind="video", fps=Fraction(30)):
    return T.Timeline(fps=fps, width=320, height=240,
                      tracks=[T.Track(kind=kind, name="main", clips=list(clips))])


def _existing_file(d):
    p = Path(d) / "x.mp4"
    p.write_bytes(b"x")
    return str(p)


class ValidationTests(unittest.TestCase):
    def setUp(self):
        self._tmp = tempfile.TemporaryDirectory()
        self.src = _existing_file(self._tmp.name)

    def tearDown(self):
        self._tmp.cleanup()

    def codes(self, tl, **kw):
        return {i.code for i in T.validate(tl, **kw) if i.level == "error"}

    def test_valid_chain_has_no_errors(self):
        tl = _tl(
            T.Clip("a", self.src, start=0, duration=30),
            T.Clip("b", self.src, start=15, duration=30, transition="dissolve", transition_frames=15),
        )
        self.assertEqual(self.codes(tl), set())

    def test_gap_between_video_clips_is_an_error(self):
        tl = _tl(
            T.Clip("a", self.src, start=0, duration=30),
            T.Clip("b", self.src, start=40, duration=30),
        )
        self.assertIn("gap", self.codes(tl))

    def test_conflicting_start_is_an_error(self):
        tl = _tl(
            T.Clip("a", self.src, start=0, duration=30),
            T.Clip("b", self.src, start=10, duration=30, transition="dissolve", transition_frames=15),
        )
        self.assertIn("conflicting_timing", self.codes(tl))

    def test_non_positive_duration_is_an_error(self):
        tl = _tl(T.Clip("a", self.src, start=0, duration=0))
        self.assertIn("non_positive_duration", self.codes(tl))

    def test_missing_asset_is_an_error(self):
        tl = _tl(T.Clip("a", "/no/such/file.mp4", start=0, duration=30))
        self.assertIn("missing_asset", self.codes(tl))
        self.assertNotIn("missing_asset", self.codes(tl, check_files=False))

    def test_transition_type_and_length_must_agree(self):
        tl = _tl(
            T.Clip("a", self.src, start=0, duration=30),
            T.Clip("b", self.src, start=15, duration=30, transition="cut", transition_frames=15),
        )
        self.assertIn("missing_transition_type", self.codes(tl))
        tl2 = _tl(
            T.Clip("a", self.src, start=0, duration=30),
            T.Clip("b", self.src, start=30, duration=30, transition="dissolve", transition_frames=0),
        )
        self.assertIn("missing_transition_length", self.codes(tl2))

    def test_transition_longer_than_neighbour_is_an_error(self):
        tl = _tl(
            T.Clip("a", self.src, start=0, duration=10),
            T.Clip("b", self.src, start=0, duration=30, transition="dissolve", transition_frames=20),
        )
        self.assertIn("transition_too_long", self.codes(tl))

    def test_overlap_on_audio_track_is_an_error(self):
        tl = _tl(T.Clip("a", self.src, start=0, duration=30),
                 T.Clip("b", self.src, start=20, duration=30), kind="audio")
        self.assertIn("overlap", self.codes(tl))

    def test_keyframe_and_subtitle_tracks_are_reported_as_not_rendered(self):
        tl = _tl(T.Clip("k", self.src, start=0, duration=30), kind="keyframe")
        warns = [i.code for i in T.validate(tl) if i.level == "warning"]
        self.assertIn("not_rendered", warns)

    def test_round_trip_json_keeps_fps_and_clips(self):
        tl = _tl(T.Clip("a", self.src, start=0, duration=30), fps=Fraction(30000, 1001))
        data = T.timeline_to_dict(tl)
        self.assertEqual(data["fps"], "30000/1001")
        back = T.timeline_from_dict(data)
        self.assertEqual(back.fps, Fraction(30000, 1001))
        self.assertEqual(back.tracks[0].clips[0].id, "a")

    def test_seconds_are_exact_for_ntsc_rate(self):
        tl = _tl(T.Clip("a", self.src, start=0, duration=30), fps=Fraction(30000, 1001))
        self.assertAlmostEqual(tl.seconds(30), 30 * 1001 / 30000, places=9)


if __name__ == "__main__":
    unittest.main()
