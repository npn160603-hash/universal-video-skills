import unicodedata
import unittest
from pathlib import Path

from uvs import captions as C

ROOT = Path(__file__).resolve().parents[2]
DEMO = ROOT / "examples" / "demo_caption" / "words.json"


def W(text, start, end):
    return C.Word(text=text, start=start, end=end)


class WordTests(unittest.TestCase):
    def test_rejects_empty_text(self):
        with self.assertRaises(ValueError):
            W("   ", 0, 1)

    def test_rejects_negative_or_inverted_timing(self):
        with self.assertRaises(ValueError):
            W("a", -0.1, 1)
        with self.assertRaises(ValueError):
            W("a", 2, 1)

    def test_key_strips_punctuation_and_keeps_vietnamese_letters(self):
        self.assertEqual(W("Cháo,", 0, 1).key, "cháo")
        self.assertEqual(W("5", 0, 1).key, "5")


class LoadTests(unittest.TestCase):
    def test_demo_words_load_in_order_and_are_nfc(self):
        words = C.load_words(DEMO)
        self.assertGreater(len(words), 20)
        for w in words:
            self.assertEqual(w.text, unicodedata.normalize("NFC", w.text))
        # The demo stores 'dậy' decomposed on purpose. After loading it must match the NFC form.
        self.assertIn("dậy", [w.text for w in words])

    def test_out_of_order_words_are_rejected(self):
        with self.assertRaises(ValueError):
            C.load_words([{"text": "a", "start": 2, "end": 2.5}, {"text": "b", "start": 1, "end": 1.5}])


class LayoutTests(unittest.TestCase):
    style = C.STYLES["bold_shorts"]

    def test_short_text_fits_one_line(self):
        words = [W("Xin", 0, 0.2), W("chào", 0.2, 0.5)]
        lines = C.layout_lines(words, self.style, 900)
        self.assertEqual(len(lines), 1)

    def test_long_text_splits_into_two_balanced_lines(self):
        words = [W(t, i * 0.3, i * 0.3 + 0.25) for i, t in enumerate(
            "Mỗi sáng bà tôi vẫn dậy lúc năm giờ".split())]
        first = " ".join(w.text for w in words[:4])   # "Mỗi sáng bà tôi"
        second = " ".join(w.text for w in words[4:])  # "vẫn dậy lúc năm giờ"
        # Budget that fits both halves, but not the whole sentence on one line.
        budget = max(C.text_width(first, self.style), C.text_width(second, self.style)) + 1
        self.assertGreater(C.text_width(" ".join(w.text for w in words), self.style), budget)
        lines = C.layout_lines(words, self.style, budget)
        self.assertIsNotNone(lines)
        self.assertEqual(len(lines), 2)
        for line in lines:
            self.assertLessEqual(C.text_width(" ".join(x.text for x in line), self.style), budget)

    def test_returns_none_when_three_lines_would_be_needed(self):
        words = [W(f"word{i}", i * 0.3, i * 0.3 + 0.25) for i in range(12)]
        self.assertIsNone(C.layout_lines(words, self.style, 200))

    def test_widths_come_from_the_real_font(self):
        short = C.text_width("iiii", self.style)
        wide = C.text_width("MMMM", self.style)
        self.assertGreater(wide, short)


class SegmentTests(unittest.TestCase):
    style = C.STYLES["documentary_minimal"]

    def test_breaks_on_sentence_end(self):
        words = [W("One.", 0, 0.4), W("Two", 0.5, 0.8)]
        cues = C.segment_words(words, self.style, 1080)
        self.assertEqual([c.text for c in cues], ["One.", "Two"])

    def test_breaks_on_long_silence(self):
        words = [W("alpha", 0, 0.3), W("beta", 1.5, 1.8)]
        cues = C.segment_words(words, self.style, 1080)
        self.assertEqual(len(cues), 2)

    def test_soft_duration_keeps_sentence_end_on_same_cue(self):
        # 3.0 s span ends a sentence: over max_duration (2.8) but under hard max (3.4).
        # Every word before the last stays within max_duration (2.8 s); only the sentence end passes it.
        words = [W("a", 0, 0.5), W("b", 0.6, 1.0), W("c", 1.1, 1.6), W("d", 1.7, 2.2),
                 W("e", 2.3, 2.7), W("end.", 2.75, 3.0)]
        cues = C.segment_words(words, self.style, 1080)
        self.assertEqual(len(cues), 1)

    def test_hard_max_still_forces_break(self):
        words = [W(f"w{i}", i * 0.5, i * 0.5 + 0.45) for i in range(10)]
        cues = C.segment_words(words, self.style, 1080)
        for c in cues:
            self.assertLessEqual(c.end - c.start, C.SegmentConfig().hard_max_duration + 1e-6)

    def test_finalize_extends_short_cue_without_overlap(self):
        cues = [C.Cue(0.0, 0.2, [W("a", 0, 0.2)]), C.Cue(0.5, 1.0, [W("b", 0.5, 1.0)])]
        C.finalize_timings(cues)
        self.assertLessEqual(cues[0].end, cues[1].start)
        self.assertGreaterEqual(cues[0].end - cues[0].start, 0.2)


class ValidationTests(unittest.TestCase):
    style = C.STYLES["bold_shorts"]

    def cue(self, text, start, end):
        words = [W(t, start + i * 0.1, start + i * 0.1 + 0.05) for i, t in enumerate(text.split())]
        return C.Cue(start=start, end=end, words=words, lines=[words])

    def codes(self, cues, **kw):
        return {i.code for i in C.validate_cues(cues, self.style, 1080, 1920, **kw)}

    def test_overlap_is_error(self):
        cues = [self.cue("one two", 0, 2), self.cue("three four", 1.5, 3)]
        self.assertIn("overlap", self.codes(cues))

    def test_line_overflow_is_error(self):
        cues = [self.cue("supercalifragilisticexpialidociousxxxxxxxxxxxxxxxxxxx", 0, 2)]
        self.assertIn("line_overflow", self.codes(cues))

    def test_space_before_punctuation_warns(self):
        cues = [self.cue("hello ,world", 0, 2)]
        self.assertIn("space_before_punctuation", self.codes(cues))

    def test_orphan_word_warns_only_with_multiple_cues(self):
        cues = [self.cue("one two three", 0, 2), self.cue("four", 2.5, 3.2)]
        self.assertIn("orphan_word", self.codes(cues))
        self.assertNotIn("orphan_word", self.codes([self.cue("solo", 0, 2)]))

    def test_demo_build_has_no_errors(self):
        build = C.build_captions(DEMO, "bold_shorts", keywords=["cháo", "5"])
        self.assertEqual(build.errors, [])


class ExportTests(unittest.TestCase):
    def test_srt_and_vtt_timestamps(self):
        self.assertEqual(C._srt_time(3661.5), "01:01:01,500")
        self.assertEqual(C._vtt_time(3661.5), "01:01:01.500")

    def test_ass_time_centiseconds(self):
        self.assertEqual(C._ass_time(3661.5), "1:01:01.50")

    def test_ass_color_is_bgr(self):
        self.assertEqual(C._ass_color("FFD700"), "&H0000D7FF&")

    def test_escape_removes_override_syntax(self):
        self.assertEqual(C._escape_ass("{\\b1}x"), "(/b1)x")

    def test_only_keywords_get_highlight_tags(self):
        build = C.build_captions(DEMO, "bold_shorts", keywords=["cháo"])
        ass = C.to_ass(build.cues, build.style, 1080, 1920, build.keys, False)
        self.assertEqual(ass.count("\\t("), 1)  # one highlighted keyword in the demo
        self.assertIn("cháo", ass)

    def test_no_highlight_style_has_no_tags_for_keywords(self):
        build = C.build_captions(DEMO, "documentary_minimal", keywords=["cháo"])
        ass = C.to_ass(build.cues, build.style, 1080, 1920, build.keys, False)
        self.assertNotIn("\\t(", ass)

    def test_vtt_header_and_srt_numbering(self):
        build = C.build_captions(DEMO, "documentary_minimal")
        self.assertTrue(C.to_vtt(build.cues).startswith("WEBVTT"))
        self.assertTrue(C.to_srt(build.cues).startswith("1\n"))


if __name__ == "__main__":
    unittest.main()
