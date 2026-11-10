import unittest

from uvs import qa as Q

BLACK = """
[blackdetect @ 0x55] black_start:0 black_end:1.02 black_duration:1.02
[blackdetect @ 0x55] black_start:4.5 black_end:5.6 black_duration:1.1
"""

FREEZE = """
[freezedetect @ 0x1] lavfi.freezedetect.freeze_start: 2.0
[freezedetect @ 0x1] lavfi.freezedetect.freeze_duration: 1.5
[freezedetect @ 0x1] lavfi.freezedetect.freeze_end: 3.5
"""

SILENCE = """
[silencedetect @ 0x2] silence_start: 0
[silencedetect @ 0x2] silence_end: 2.25 | silence_duration: 2.25
[silencedetect @ 0x2] silence_start: 5
"""

VOLUME = """
[Parsed_volumedetect_0 @ 0x3] n_samples: 96000
[Parsed_volumedetect_0 @ 0x3] mean_volume: -22.4 dB
[Parsed_volumedetect_0 @ 0x3] max_volume: -3.1 dB
"""

EBUR = """
Summary:

  Integrated loudness:
    I:         -18.7 LUFS
    Threshold: -28.7 LUFS

  Loudness range:
    LRA:         4.2 LU
    Threshold: -38.7 LUFS

  True peak:
    Peak:       -1.4 dBFS
"""


class ParserTests(unittest.TestCase):
    def test_blackdetect(self):
        self.assertEqual(Q.parse_blackdetect(BLACK), [(0.0, 1.02, 1.02), (4.5, 5.6, 1.1)])

    def test_freezedetect(self):
        self.assertEqual(Q.parse_freezedetect(FREEZE), [(2.0, 1.5)])

    def test_silencedetect_pairs_end_with_duration(self):
        self.assertEqual(Q.parse_silencedetect(SILENCE), [(2.25, 2.25)])

    def test_volumedetect(self):
        self.assertEqual(Q.parse_volumedetect(VOLUME), {"mean_db": -22.4, "max_db": -3.1})

    def test_ebur128_summary(self):
        self.assertEqual(Q.parse_ebur128_summary(EBUR),
                         {"integrated_lufs": -18.7, "true_peak_dbtp": -1.4})

    def test_ebur128_uses_summary_not_gated_per_frame_lines(self):
        stderr = (
            "[Parsed_ebur128_0 @ 0x1] t: 0.1 TARGET:-23 LUFS M: -70.0 I: -70.0 LUFS LRA: 0.0 LU\n"
            "[Parsed_ebur128_0 @ 0x1] t: 9.5 TARGET:-23 LUFS M: -42.0 I: -42.0 LUFS LRA: 0.0 LU\n"
        ) + EBUR
        self.assertEqual(Q.parse_ebur128_summary(stderr),
                         {"integrated_lufs": -18.7, "true_peak_dbtp": -1.4})

    def test_ebur128_without_summary_returns_empty(self):
        self.assertEqual(Q.parse_ebur128_summary("[x] t: 0.1 I: -70.0 LUFS"), {})

    def test_empty_inputs_return_empty(self):
        self.assertEqual(Q.parse_blackdetect(""), [])
        self.assertEqual(Q.parse_freezedetect(""), [])
        self.assertEqual(Q.parse_silencedetect(""), [])
        self.assertEqual(Q.parse_volumedetect(""), {})
        self.assertEqual(Q.parse_ebur128_summary(""), {})


class ReportTests(unittest.TestCase):
    def test_overall_is_worst_status(self):
        r = Q.QAReport(file="x")
        r.checks.append(Q.Check("a", "t", "pass", ""))
        self.assertEqual(r.overall, "pass")
        r.checks.append(Q.Check("b", "t", "warn", ""))
        self.assertEqual(r.overall, "warn")
        r.checks.append(Q.Check("c", "t", "fail", ""))
        self.assertEqual(r.overall, "fail")


if __name__ == "__main__":
    unittest.main()
