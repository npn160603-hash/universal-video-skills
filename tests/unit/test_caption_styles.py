"""The seven caption styles and typography/layout QA (Phase 7.5-7.7)."""
import unittest

from uvs.captions import STYLES, build_captions, to_ass, validate_cues, Word, Cue, CaptionStyle
from uvs.typography import (TYPOGRAPHY_EFFECTS, typewriter, staggered_words, mask_reveal,
                            phrase_animation, speaker_color, has_vietnamese_diacritics, nfc,
                            layout_qa)

REQUIRED_STYLES = {"documentary_minimal", "clean_modern", "cinematic", "bold_shorts",
                   "podcast_highlight", "educational", "emotional_storytelling"}


def _cue(words):
    c = Cue(words[0].start, words[-1].end, list(words))
    c.lines = [list(words)]
    return c


class StyleCompletenessTests(unittest.TestCase):
    def test_all_seven_required_styles_exist(self):
        self.assertTrue(REQUIRED_STYLES <= set(STYLES), REQUIRED_STYLES - set(STYLES))

    def test_every_style_defines_the_required_fields(self):
        for name, s in STYLES.items():
            with self.subTest(style=name):
                self.assertTrue(s.font and s.size > 0)
                self.assertIn(s.background, {"outline", "box"})
                self.assertGreaterEqual(s.max_lines, 1)
                self.assertGreaterEqual(s.max_words, 1)
                self.assertIn(s.animation, {"fade", "pop", "none"})

    def test_each_style_builds_valid_ass(self):
        words = [Word("Learning", 0.0, 0.5), Word("to", 0.5, 0.7), Word("say", 0.7, 1.0),
                 Word("no", 1.0, 1.4), Word("matters", 1.5, 2.2)]
        for name in STYLES:
            with self.subTest(style=name):
                b = build_captions(words, name, 1080, 1920, keywords=["no"])
                ass = to_ass(b.cues, b.style, 1080, 1920, keys=b.keys)
                self.assertIn("[V4+ Styles]", ass)
                self.assertIn("Dialogue:", ass)
                self.assertEqual([i for i in validate_cues(b.cues, b.style, 1080, 1920)
                                  if i.level == "error"], [])

    def test_clean_modern_uses_a_box_background(self):
        b = build_captions([Word("x", 0, 1)], "clean_modern")
        ass = to_ass(b.cues, b.style, 1080, 1920)
        style_line = [l for l in ass.splitlines() if l.startswith("Style: Default")][0]
        self.assertEqual(style_line.split(",")[15], "3")  # BorderStyle 3 = opaque box


class TypographyTests(unittest.TestCase):
    def setUp(self):
        self.cue = _cue([Word("Tôi", 0, 0.5), Word("nói", 0.5, 1.0), Word("không", 1.0, 2.0)])

    def test_seven_effects_named(self):
        self.assertEqual(len(TYPOGRAPHY_EFFECTS), 7)

    def test_typewriter_reveals_each_character(self):
        s = typewriter(self.cue)
        self.assertEqual(s.count("\\alpha&HFF&"), len(self.cue.text))

    def test_staggered_words_delays_each_word(self):
        s = staggered_words(self.cue, per_word_ms=100)
        self.assertIn("\\t(0,", s)
        self.assertIn("\\t(100,", s)
        self.assertIn("\\t(200,", s)

    def test_phrase_and_mask_and_speaker(self):
        self.assertIn("\\move", phrase_animation(self.cue))
        self.assertIn("\\t(", mask_reveal(self.cue))
        with self.assertRaises(ValueError):
            mask_reveal(self.cue, direction="diagonal")
        self.assertIn("\\1c", speaker_color(self.cue, STYLES["educational"], 0, ["FF0000", "00FF00"]))
        with self.assertRaises(ValueError):
            speaker_color(self.cue, STYLES["educational"], 0, [])


class VietnameseTests(unittest.TestCase):
    def test_detects_precomposed_and_decomposed_diacritics(self):
        import unicodedata
        self.assertTrue(has_vietnamese_diacritics("không"))
        self.assertTrue(has_vietnamese_diacritics(unicodedata.normalize("NFD", "cà phê")))
        self.assertFalse(has_vietnamese_diacritics("hello"))

    def test_nfc_composes(self):
        import unicodedata
        self.assertEqual(nfc(unicodedata.normalize("NFD", "nói")), "nói")


class LayoutQATests(unittest.TestCase):
    def test_unreadable_font_is_flagged(self):
        tiny = CaptionStyle(name="t", font="Inter", size=10, bold=False, primary="FFFFFF",
                            highlight=None, outline=1, shadow=0, margin_v=100)
        cue = _cue([Word("hi", 0, 1)])
        report = layout_qa([cue], tiny, 1080, 1920)
        self.assertTrue(any(i.code == "unreadable_font" for i in report.errors))

    def test_good_style_passes(self):
        cue = _cue([Word("Learning", 0, 0.5), Word("to", 0.5, 1.0)])
        self.assertTrue(layout_qa([cue], STYLES["educational"], 1080, 1920).ok)

    def test_too_many_words_warned(self):
        words = [Word(f"w{i}", i * 0.2, i * 0.2 + 0.18) for i in range(9)]
        cue = _cue(words)
        report = layout_qa([cue], STYLES["bold_shorts"], 1080, 1920, max_words_per_phrase=5)
        self.assertTrue(any(i.code == "too_many_words" for i in report.issues))

    def test_non_nfc_word_warned(self):
        import unicodedata
        w = Word(unicodedata.normalize("NFD", "nói"), 0, 1)
        cue = _cue([w])
        report = layout_qa([cue], STYLES["educational"], 1080, 1920)
        self.assertTrue(any(i.code == "not_nfc" for i in report.issues))


if __name__ == "__main__":
    unittest.main()
