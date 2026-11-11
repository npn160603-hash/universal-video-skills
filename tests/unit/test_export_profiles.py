"""Export profile math and capability-matrix logic (no ffmpeg for dimension tests)."""
import unittest

from uvs.export import ExportProfile, standard_profiles, ASPECTS, RESOLUTIONS, ExportError, Hardware


class ProfileDimensionTests(unittest.TestCase):
    def test_vertical_1080p_is_portrait(self):
        w, h = ExportProfile("t", "9:16", "1080p", "h264").dimensions()
        self.assertEqual(h, 1080)
        self.assertLess(w, h)

    def test_horizontal_1080p_is_landscape(self):
        w, h = ExportProfile("t", "16:9", "1080p", "h264").dimensions()
        self.assertEqual(h, 1080)
        self.assertGreater(w, h)

    def test_square_is_equal(self):
        w, h = ExportProfile("t", "1:1", "720p", "h264").dimensions()
        self.assertEqual(w, h)
        self.assertEqual(w, 720)

    def test_dimensions_are_even(self):
        for aspect in ASPECTS:
            for res in RESOLUTIONS:
                w, h = ExportProfile("t", aspect, res, "h264").dimensions()
                self.assertEqual(w % 2, 0)
                self.assertEqual(h % 2, 0)

    def test_standard_profiles_cover_required_matrix(self):
        profiles = standard_profiles()
        self.assertEqual(len(profiles), 6)  # 3 aspects x 2 resolutions
        aspects = {p.aspect for p in profiles.values()}
        self.assertEqual(aspects, {"9:16", "16:9", "1:1"})

    def test_bad_profile_rejected(self):
        with self.assertRaises(ExportError):
            ExportProfile("t", "4:3", "1080p", "h264").validate()
        with self.assertRaises(ExportError):
            ExportProfile("t", "9:16", "8k", "h264").validate()
        with self.assertRaises(ExportError):
            ExportProfile("t", "9:16", "1080p", "vp9").validate()

    def test_encoder_mapping(self):
        self.assertEqual(ExportProfile("t", "1:1", "720p", "h264").encoder(), "libx264")
        self.assertEqual(ExportProfile("t", "1:1", "720p", "h265").encoder(), "libx265")


class CapabilityMatrixLogicTests(unittest.TestCase):
    def test_matrix_marks_exportable_from_working_encoders(self):
        from uvs.export import export_capability_matrix
        hw = Hardware(cpu_cores=2, ram_gb=8, gpu_present=False, gpu_name="none",
                      working_video_encoders=("libx264",), working_audio_encoders=("aac",),
                      listed_hwaccels=(), filter_count=100)
        matrix = export_capability_matrix(hw)
        self.assertTrue(all(r["exportable"] for r in matrix["profiles"]))  # h264 works
        self.assertEqual(matrix["hardware"]["cpu_cores"], 2)


if __name__ == "__main__":
    unittest.main()
