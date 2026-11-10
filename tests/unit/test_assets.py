import os
import tempfile
import unittest
from pathlib import Path

from uvs import assets as A


class PathSafetyTests(unittest.TestCase):
    def setUp(self):
        self._tmp = tempfile.TemporaryDirectory()
        self.base = Path(self._tmp.name)
        self.root = A.ProjectRoot(self.base / "project")
        self.root.path.mkdir()
        (self.root.path / "media").mkdir()
        (self.root.path / "media" / "a.mp4").write_bytes(b"x")

    def tearDown(self):
        self._tmp.cleanup()

    def test_relative_path_inside_root_resolves(self):
        self.assertEqual(self.root.resolve("media/a.mp4"), self.root.path / "media" / "a.mp4")

    def test_absolute_path_is_refused(self):
        with self.assertRaises(A.AssetError) as ctx:
            self.root.resolve("/etc/passwd")
        self.assertIn("not portable", str(ctx.exception))

    def test_parent_segments_are_refused(self):
        for bad in ("../secret.mp4", "media/../../secret.mp4"):
            with self.subTest(path=bad), self.assertRaises(A.AssetError):
                self.root.resolve(bad)

    def test_nul_byte_and_empty_are_refused(self):
        for bad in ("", "a\x00b.mp4"):
            with self.subTest(path=repr(bad)), self.assertRaises(A.AssetError):
                self.root.resolve(bad)

    def test_symlink_pointing_outside_is_refused(self):
        outside = self.base / "outside.mp4"
        outside.write_bytes(b"secret")
        link = self.root.path / "media" / "link.mp4"
        os.symlink(outside, link)
        with self.assertRaises(A.AssetError) as ctx:
            self.root.resolve("media/link.mp4")
        self.assertIn("outside the project folder", str(ctx.exception))

    def test_relpath_refuses_files_outside_root(self):
        with self.assertRaises(A.AssetError):
            self.root.relpath(self.base / "outside.mp4")

    def test_relpath_uses_forward_slashes(self):
        self.assertEqual(self.root.relpath(self.root.path / "media" / "a.mp4"), "media/a.mp4")


class RegisterAndCheckTests(unittest.TestCase):
    def setUp(self):
        self._tmp = tempfile.TemporaryDirectory()
        self.root = A.ProjectRoot(Path(self._tmp.name) / "p")
        (self.root.path / "media").mkdir(parents=True)
        self.file = self.root.path / "media" / "clip.mp4"
        self.file.write_bytes(b"original bytes")

    def tearDown(self):
        self._tmp.cleanup()

    def test_register_records_checksum_portable_path_and_kind(self):
        rec = A.register(self.root, self.file)
        self.assertEqual(rec["path"], "media/clip.mp4")
        self.assertEqual(rec["kind"], "video")
        self.assertTrue(rec["portable"])
        self.assertEqual(rec["sha256"], A.sha256_file(self.file))
        self.assertEqual(rec["id"], "a" + rec["sha256"][:10])

    def test_register_missing_file_is_an_error(self):
        with self.assertRaises(A.AssetError):
            A.register(self.root, self.root.path / "media" / "nope.mp4")

    def test_check_reports_ok_missing_and_changed(self):
        rec = A.register(self.root, self.file)
        self.assertEqual(A.check(self.root, [rec])[0]["status"], "ok")

        self.file.write_bytes(b"edited bytes")
        self.assertEqual(A.check(self.root, [rec])[0]["status"], "changed")

        self.file.unlink()
        self.assertEqual(A.check(self.root, [rec])[0]["status"], "missing")

    def test_check_flags_unsafe_paths_without_touching_disk(self):
        rec = {"id": "x", "path": "../escape.mp4", "sha256": "", "portable": True}
        self.assertEqual(A.check(self.root, [rec])[0]["status"], "unsafe")

    def test_check_never_modifies_user_media(self):
        before = self.file.read_bytes()
        A.check(self.root, [A.register(self.root, self.file)])
        self.assertEqual(self.file.read_bytes(), before)
        self.assertTrue(self.file.exists())


class DependencyTests(unittest.TestCase):
    def test_usage_and_unused_assets(self):
        doc = {
            "assets": [{"id": "a1"}, {"id": "a2"}, {"id": "a3"}],
            "tracks": {
                "video": [{"id": "v1", "asset_id": "a1"}, {"id": "v2", "asset_id": "a1"}],
                "audio": [{"id": "m1", "asset_id": "a2"}],
                "graphics": [],
            },
        }
        self.assertEqual(A.usage(doc), {"a1": ["v1", "v2"], "a2": ["m1"], "a3": []})
        self.assertEqual(A.unused(doc), ["a3"])


class CacheTests(unittest.TestCase):
    def setUp(self):
        self._tmp = tempfile.TemporaryDirectory()
        self.base = Path(self._tmp.name)

    def tearDown(self):
        self._tmp.cleanup()

    def test_keys_are_deterministic_and_input_sensitive(self):
        self.assertEqual(A.Cache.key("scene", 1, {"b": 2, "a": 1}), A.Cache.key("scene", 1, {"a": 1, "b": 2}))
        self.assertNotEqual(A.Cache.key("scene", 1), A.Cache.key("scene", 2))

    def test_put_then_get_round_trip(self):
        cache = A.Cache(self.base / "cache")
        src = self.base / "frame.bin"
        src.write_bytes(b"payload")
        key = A.Cache.key("x")
        self.assertIsNone(cache.get(key, ".bin"))
        cache.put(key, src, ".bin")
        self.assertTrue(cache.has(key, ".bin"))
        self.assertEqual(cache.get(key, ".bin").read_bytes(), b"payload")

    def test_prune_removes_least_recently_used_until_under_limit(self):
        cache = A.Cache(self.base / "cache", max_bytes=250)
        for i, size in enumerate((100, 100, 100)):
            p = self.base / f"f{i}.bin"
            p.write_bytes(b"x" * size)
            cache.put(A.Cache.key("item", i), p, ".bin")
            os.utime(cache.path_for(A.Cache.key("item", i), ".bin"), (1000 + i, 1000 + i))
        cache.get(A.Cache.key("item", 0), ".bin")  # touch the oldest so it survives
        removed = cache.prune()
        self.assertEqual(len(removed), 1)
        self.assertLessEqual(cache.size_bytes(), 250)
        self.assertTrue(cache.has(A.Cache.key("item", 0), ".bin"))

    def test_path_for_rejects_unsafe_keys(self):
        cache = A.Cache(self.base / "cache")
        for bad_key, bad_suffix in (("../../etc", ".bin"), ("abc", "bin")):
            with self.subTest(key=bad_key, suffix=bad_suffix), self.assertRaises(A.AssetError):
                cache.path_for(bad_key, bad_suffix)


if __name__ == "__main__":
    unittest.main()
