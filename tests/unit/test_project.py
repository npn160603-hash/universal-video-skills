import copy
import json
import tempfile
import unittest
from fractions import Fraction
from pathlib import Path

from uvs import project as P
from uvs import timeline as T


def _valid_doc() -> dict:
    doc = P.new_project("demo_01", "Demo", 1080, 1920, "30")
    doc["assets"] = [{"id": "a1", "path": "media/a.mp4", "sha256": "", "kind": "video", "portable": True}]
    doc["tracks"]["video"] = [
        {"id": "v1", "asset_id": "a1", "start_frame": 0, "duration_frames": 60, "transition": "cut"},
        {"id": "v2", "asset_id": "a1", "start_frame": 54, "duration_frames": 60, "in_frame": 0,
         "transition": "dissolve", "transition_frames": 6},
    ]
    return doc


def _v0_timeline() -> dict:
    """A timeline written by uvs.timeline.save_timeline before versioning existed."""
    tl = T.Timeline(fps=Fraction(30), width=1080, height=1920, tracks=[
        T.Track("video", "main", [
            T.Clip(id="c1", source="/abs/elsewhere/clip1.mp4", start=0, duration=60),
            T.Clip(id="c2", source="media/clip2.mp4", start=54, duration=60, transition="dissolve",
                   transition_frames=6),
        ]),
        T.Track("overlay", "titles", [T.Clip(id="t1", source="media/title.png", start=10, duration=30,
                                             is_image=True, x=40, y=40)]),
        T.Track("subtitle", "subs", []),
    ])
    return T.timeline_to_dict(tl)


class VersionedProjectTests(unittest.TestCase):
    def test_new_project_is_valid_and_has_derived_aspect_ratio(self):
        doc = P.new_project("p1", "Title", 1080, 1920)
        self.assertEqual(doc["format_settings"]["aspect_ratio"], "9:16")
        self.assertEqual(P.validate(doc), [])

    def test_valid_project_with_references_passes(self):
        self.assertEqual(P.validate(_valid_doc()), [])

    def test_structural_errors_carry_path_and_hint(self):
        doc = _valid_doc()
        del doc["project"]["title"]
        doc["format_settings"]["width"] = 5
        issues = P.validate(doc)
        paths = {i.path for i in issues}
        self.assertIn("project", paths)
        self.assertIn("format_settings/width", paths)
        width = next(i for i in issues if i.path == "format_settings/width")
        self.assertEqual(width.hint, "use a larger value")

    def test_unknown_field_is_rejected_with_a_hint(self):
        doc = _valid_doc()
        doc["surprise"] = 1
        issue = next(i for i in P.validate(doc) if "surprise" in i.message or i.path == "(root)")
        self.assertIn("remove or rename", issue.hint)

    def test_unknown_asset_reference_is_reported(self):
        doc = _valid_doc()
        doc["tracks"]["video"][1]["asset_id"] = "missing"
        issues = P.validate(doc)
        self.assertTrue(any(i.path == "tracks/video/1/asset_id" for i in issues))

    def test_duplicate_clip_and_asset_ids_are_reported(self):
        doc = _valid_doc()
        doc["tracks"]["video"][1]["id"] = "v1"
        doc["assets"].append(copy.deepcopy(doc["assets"][0]))
        messages = " | ".join(i.message for i in P.validate(doc))
        self.assertIn("duplicate clip id", messages)
        self.assertIn("duplicate asset id", messages)

    def test_overlapping_scenes_are_reported(self):
        doc = _valid_doc()
        doc["scenes"] = [{"id": "s1", "start_frame": 0, "end_frame": 60},
                         {"id": "s2", "start_frame": 50, "end_frame": 120}]
        self.assertTrue(any("overlaps" in i.message for i in P.validate(doc)))

    def test_unsorted_keyframes_are_reported(self):
        doc = _valid_doc()
        doc["keyframes"] = [{"target": "v1", "property": "opacity",
                             "keys": [{"frame": 30, "value": 1}, {"frame": 10, "value": 0}]}]
        self.assertTrue(any("strictly increasing" in i.message for i in P.validate(doc)))

    def test_aspect_ratio_must_match_pixels(self):
        doc = _valid_doc()
        doc["format_settings"]["aspect_ratio"] = "16:9"
        issue = next(i for i in P.validate(doc) if i.path == "format_settings/aspect_ratio")
        self.assertIn("9:16", issue.hint)

    def test_portable_path_with_parent_segment_is_rejected(self):
        doc = _valid_doc()
        doc["assets"][0]["path"] = "../outside.mp4"
        self.assertTrue(any("'..'" in i.message for i in P.validate(doc)))


class MigrationTests(unittest.TestCase):
    def test_v0_timeline_migrates_to_v1_and_validates(self):
        doc = P.migrate(_v0_timeline())
        self.assertEqual(doc["schema_version"], 1)
        self.assertEqual(P.validate(doc), [])
        self.assertEqual(doc["format_settings"]["aspect_ratio"], "9:16")

    def test_migration_maps_tracks_and_reports_what_was_dropped(self):
        doc = P.migrate(_v0_timeline())
        self.assertEqual(len(doc["tracks"]["video"]), 2)
        self.assertEqual(len(doc["tracks"]["graphics"]), 1)  # overlay -> graphics
        notes = " | ".join(doc["quality"]["migration_notes"])
        self.assertIn("'subs'", notes)            # subtitle track has no v1 equivalent
        self.assertIn("absolute path", notes)     # absolute media path is flagged

    def test_migration_creates_one_asset_per_source_and_marks_absolute_paths(self):
        doc = P.migrate(_v0_timeline())
        by_path = {a["path"]: a for a in doc["assets"]}
        self.assertFalse(by_path["/abs/elsewhere/clip1.mp4"]["portable"])
        self.assertTrue(by_path["media/clip2.mp4"]["portable"])
        self.assertEqual(by_path["media/title.png"]["kind"], "image")

    def test_newer_version_is_refused_with_upgrade_hint(self):
        doc = _valid_doc()
        doc["schema_version"] = 99
        with self.assertRaises(P.ProjectError) as ctx:
            P.migrate(doc)
        self.assertIn("upgrade", ctx.exception.issues[0].hint)

    def test_unrecognised_document_is_refused(self):
        with self.assertRaises(P.ProjectError):
            P.migrate({"hello": "world"})


class FileTests(unittest.TestCase):
    def test_save_then_load_round_trip_and_bytes_are_deterministic(self):
        with tempfile.TemporaryDirectory() as tmp:
            p1, p2 = Path(tmp, "a.uvs.json"), Path(tmp, "b.uvs.json")
            P.save(_valid_doc(), p1)
            P.save(P.load(p1), p2)
            self.assertEqual(p1.read_bytes(), p2.read_bytes())
            self.assertEqual(P.load(p1), _valid_doc())

    def test_invalid_json_reports_line_number(self):
        with tempfile.TemporaryDirectory() as tmp:
            p = Path(tmp, "bad.json")
            p.write_text('{\n  "format": \n', encoding="utf-8")
            with self.assertRaises(P.ProjectError) as ctx:
                P.load(p)
            self.assertIn("line", ctx.exception.issues[0].message)

    def test_save_refuses_an_invalid_document(self):
        doc = _valid_doc()
        doc["tracks"]["video"][0]["asset_id"] = "nope"
        with tempfile.TemporaryDirectory() as tmp:
            with self.assertRaises(P.ProjectError):
                P.save(doc, Path(tmp, "x.json"))
            self.assertFalse(Path(tmp, "x.json").exists())


if __name__ == "__main__":
    unittest.main()
