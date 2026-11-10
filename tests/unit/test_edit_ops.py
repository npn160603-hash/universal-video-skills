import copy
import unittest
from fractions import Fraction

from uvs import edit_ops as E
from uvs import timeline as T


def _clip(cid, start, dur, **kw):
    return T.Clip(id=cid, source=f"media/{cid}.mp4", start=start, duration=dur, **kw)


def _timeline() -> T.Timeline:
    """Video chain a(0..60) -dissolve 6-> b(54..114) -cut-> c(114..144); overlay title at 10."""
    return T.Timeline(fps=Fraction(30), width=1080, height=1920, tracks=[
        T.Track("video", "main", [
            _clip("a", 0, 60),
            _clip("b", 54, 60, transition="dissolve", transition_frames=6),
            _clip("c", 114, 30),
        ]),
        T.Track("overlay", "titles", [_clip("t", 10, 20, x=40, y=40)]),
        T.Track("audio", "voice", [_clip("v", 0, 144)]),
    ])


def _starts(tl):
    return [c.start for c in tl.tracks[0].clips]


class VideoChainEditTests(unittest.TestCase):
    def test_set_duration_reflows_following_clips(self):
        tl = _timeline()
        new, rec = E.apply_op(tl, "set_duration", {"track": "main", "clip_id": "a", "frames": 90})
        self.assertEqual(_starts(new), [0, 84, 144])
        self.assertEqual(_starts(tl), [0, 54, 114])  # original untouched

    def test_undo_restores_exact_serialization(self):
        tl = _timeline()
        new, rec = E.apply_op(tl, "set_duration", {"track": "main", "clip_id": "a", "frames": 90})
        self.assertEqual(T.timeline_to_dict(E.undo(new, rec)), T.timeline_to_dict(tl))

    def test_set_transition_changes_overlap_and_undo_restores(self):
        tl = _timeline()
        new, rec = E.apply_op(tl, "set_transition", {"clip_id": "c", "kind": "dip_black", "frames": 15})
        self.assertEqual(_starts(new), [0, 54, 99])
        self.assertEqual(T.timeline_to_dict(E.undo(new, rec)), T.timeline_to_dict(tl))

    def test_first_clip_cannot_take_a_transition(self):
        with self.assertRaises(E.EditError):
            E.apply_op(_timeline(), "set_transition", {"clip_id": "a", "kind": "dissolve", "frames": 6})

    def test_transition_longer_than_neighbour_is_rejected_and_original_survives(self):
        tl = _timeline()
        before = T.timeline_to_dict(tl)
        with self.assertRaises(E.EditError) as ctx:
            E.apply_op(tl, "set_transition", {"clip_id": "c", "kind": "dissolve", "frames": 500})
        self.assertIn("transition_too_long", str(ctx.exception))
        self.assertEqual(T.timeline_to_dict(tl), before)

    def test_remove_middle_clip_keeps_successor_transition_and_undo_restores(self):
        # c dissolves in (6 frames) from b. Removing b makes c dissolve from a instead.
        tl = T.Timeline(fps=Fraction(30), width=10, height=10, tracks=[T.Track("video", "main", [
            _clip("a", 0, 60),
            _clip("b", 54, 60, transition="dissolve", transition_frames=6),
            _clip("c", 108, 30, transition="dissolve", transition_frames=6),
        ])])
        new, rec = E.apply_op(tl, "remove_clip", {"track": "main", "clip_id": "b"})
        self.assertEqual([c.id for c in new.tracks[0].clips], ["a", "c"])
        self.assertEqual(new.tracks[0].clips[1].transition, "dissolve")
        self.assertEqual(new.tracks[0].clips[1].start, 54)
        restored = E.undo(new, rec)
        self.assertEqual(T.timeline_to_dict(restored), T.timeline_to_dict(tl))

    def test_remove_first_clip_then_undo_restores(self):
        tl = _timeline()
        new, rec = E.apply_op(tl, "remove_clip", {"track": "main", "clip_id": "a"})
        self.assertEqual(new.tracks[0].clips[0].id, "b")
        self.assertEqual(new.tracks[0].clips[0].transition_frames, 0)
        self.assertEqual(T.timeline_to_dict(E.undo(new, rec)), T.timeline_to_dict(tl))

    def test_add_clip_at_index_reflows_and_undo_removes_it(self):
        tl = _timeline()
        new, rec = E.apply_op(tl, "add_clip", {"track": "main", "index": 1,
                                               "clip": {"id": "x", "source": "media/x.mp4", "start": 0,
                                                        "duration": 30}})
        self.assertEqual([c.id for c in new.tracks[0].clips], ["a", "x", "b", "c"])
        self.assertEqual(T.timeline_to_dict(E.undo(new, rec)), T.timeline_to_dict(tl))

    def test_video_clip_cannot_be_moved_directly(self):
        with self.assertRaises(E.EditError):
            E.apply_op(_timeline(), "move_clip", {"track": "main", "clip_id": "b", "start": 0})

    def test_duplicate_clip_id_is_rejected(self):
        with self.assertRaises(E.EditError):
            E.apply_op(_timeline(), "add_clip", {"track": "main", "clip": {"id": "a", "source": "x", "start": 0,
                                                                          "duration": 10}})


class FreePlacementTests(unittest.TestCase):
    def test_move_overlay_clip_and_undo(self):
        tl = _timeline()
        new, rec = E.apply_op(tl, "move_clip", {"track": "titles", "clip_id": "t", "start": 200})
        self.assertEqual(new.tracks[1].clips[0].start, 200)
        self.assertEqual(T.timeline_to_dict(E.undo(new, rec)), T.timeline_to_dict(tl))

    def test_overlapping_move_on_audio_track_is_rejected(self):
        tl = T.Timeline(fps=Fraction(30), width=10, height=10, tracks=[
            T.Track("audio", "voice", [_clip("v1", 0, 30), _clip("v2", 60, 30)])])
        with self.assertRaises(E.EditError) as ctx:
            E.apply_op(tl, "move_clip", {"track": "voice", "clip_id": "v2", "start": 20})
        self.assertIn("overlap", str(ctx.exception))

    def test_unknown_operation_and_unknown_track_are_reported(self):
        with self.assertRaises(E.EditError):
            E.apply_op(_timeline(), "explode", {})
        with self.assertRaises(E.EditError):
            E.apply_op(_timeline(), "move_clip", {"track": "nope", "clip_id": "t", "start": 0})


class ReplayAndBoundaryTests(unittest.TestCase):
    def test_replaying_records_reproduces_the_edited_timeline(self):
        tl = _timeline()
        records, current = [], tl
        steps = [
            ("set_duration", {"track": "main", "clip_id": "a", "frames": 75}),
            ("set_transition", {"clip_id": "c", "kind": "dissolve", "frames": 9}),
            ("move_clip", {"track": "titles", "clip_id": "t", "start": 40}),
        ]
        for op, args in steps:
            current, rec = E.apply_op(current, op, args)
            records.append(rec)
        replayed = E.replay(tl, records)
        self.assertEqual(T.timeline_to_dict(replayed), T.timeline_to_dict(current))

    def test_records_are_json_serializable(self):
        import json
        _, rec = E.apply_op(_timeline(), "remove_clip", {"track": "main", "clip_id": "b"})
        json.dumps(rec)  # must not raise

    def test_scene_boundaries_must_sit_on_clip_starts(self):
        tl = _timeline()
        self.assertEqual(E.validate_scene_boundaries(tl, [0, 54, 114]), [])
        problems = E.validate_scene_boundaries(tl, [0, 55])
        self.assertEqual(len(problems), 1)
        self.assertIn("frame 55", problems[0])

    def test_frame_precision_at_ntsc_rate(self):
        tl = T.Timeline(fps=Fraction(30000, 1001), width=10, height=10,
                        tracks=[T.Track("video", "main", [_clip("a", 0, 30000), _clip("b", 30000, 1001)])])
        new, _ = E.apply_op(tl, "set_duration", {"track": "main", "clip_id": "a", "frames": 30001})
        self.assertEqual(new.tracks[0].clips[1].start, 30001)
        self.assertEqual(new.total_frames, 31002)
        self.assertEqual(new.seconds(30001), float(Fraction(30001 * 1001, 30000)))


if __name__ == "__main__":
    unittest.main()
