"""Technical-debt fixes: D-02 (spec validation) and D-07 (font fallback)."""
import unittest
from unittest import mock

from uvs.pipeline import validate_spec
from uvs.captions import resolve_font_file, _font_file_on_disk


class SpecValidationTests(unittest.TestCase):
    """D-02: pipeline specs are validated before running."""

    def test_valid_spec_passes(self):
        self.assertEqual(validate_spec({"words": "w.json", "genre": "real_life_storytelling"}), [])

    def test_unknown_genre_reported(self):
        problems = validate_spec({"words": "w.json", "genre": "nope"})
        self.assertTrue(any("genre" in p for p in problems))

    def test_missing_words_and_genre_reported(self):
        problems = validate_spec({})
        self.assertTrue(any("words" in p for p in problems))
        self.assertTrue(any("genre" in p for p in problems))

    def test_bad_dimensions_reported(self):
        self.assertTrue(validate_spec({"words": "w", "genre": "real_life_storytelling", "width": -5}))
        self.assertTrue(validate_spec({"words": "w", "genre": "real_life_storytelling", "fps": "x"}))

    def test_unknown_style_reported(self):
        self.assertTrue(validate_spec({"words": "w", "genre": "real_life_storytelling", "style": "nope"}))

    def test_footage_must_be_list(self):
        self.assertTrue(validate_spec({"words": "w", "genre": "real_life_storytelling", "footage": "x"}))


class FontFallbackTests(unittest.TestCase):
    """D-07: the font resolver finds a family on disk when fc-match is unavailable."""

    def test_disk_fallback_finds_inter(self):
        self.assertIsNotNone(_font_file_on_disk("Inter", False))
        self.assertIsNotNone(_font_file_on_disk("Inter", True))

    def test_resolve_without_fc_match_uses_disk(self):
        resolve_font_file.cache_clear()
        with mock.patch("uvs.captions.shutil.which", return_value=None):
            path = resolve_font_file("Inter", False)
        resolve_font_file.cache_clear()
        self.assertIsNotNone(path)
        self.assertIn("Inter", path)

    def test_unknown_family_returns_none(self):
        self.assertIsNone(_font_file_on_disk("ThisFontDoesNotExistAnywhere", False))


if __name__ == "__main__":
    unittest.main()
