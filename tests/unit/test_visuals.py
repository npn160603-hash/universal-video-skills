"""Animation controls (zoom, pan, exit fade) and timeline integration (no ffmpeg for the unit part)."""
import unittest

import numpy as np
from PIL import Image

from uvs.visuals import Controls, apply_controls, to_timeline_clip
from uvs.infographics import ChartSpec, Series, render_chart_frame


def _counter(val=100, size=200):
    return render_chart_frame(
        ChartSpec("counter", (), (Series("n", (val,)),), source="d", width=size, height=size), 1.0)


class ControlsValidationTests(unittest.TestCase):
    def test_bad_zoom_pan_fade_rejected(self):
        for c in (Controls(zoom_from=0.0), Controls(zoom_to=-1.0),
                  Controls(pan_from=(1.5, 0.5)), Controls(exit_fade=-0.2)):
            with self.subTest(controls=c):
                with self.assertRaises(ValueError):
                    c.validate()

    def test_default_controls_are_a_no_op(self):
        base = _counter()
        self.assertEqual(apply_controls(base, Controls(), 0.0).tobytes(), base.tobytes())


class ZoomPanTests(unittest.TestCase):
    def test_zoom_changes_the_frame(self):
        base = _counter()
        zoomed = apply_controls(base, Controls(zoom_from=2.0, zoom_to=2.0), 0.0)
        self.assertNotEqual(base.tobytes(), zoomed.tobytes())
        self.assertEqual(zoomed.size, base.size)

    def test_zoom_magnifies_central_content(self):
        # A centred number zoomed 2x covers more pixels than at 1x.
        base = _counter()
        bg = np.array(base)[0, 0]
        def content_px(img):
            a = np.array(img)
            return int((~(a == bg).all(axis=2)).sum())
        zoomed = apply_controls(base, Controls(zoom_from=2.0, zoom_to=2.0), 0.0)
        self.assertGreater(content_px(zoomed), content_px(base))

    def test_pan_moves_the_crop_window(self):
        base = _counter()
        left = apply_controls(base, Controls(zoom_from=2.0, zoom_to=2.0, pan_from=(0.2, 0.5),
                                             pan_to=(0.2, 0.5)), 0.0)
        right = apply_controls(base, Controls(zoom_from=2.0, zoom_to=2.0, pan_from=(0.8, 0.5),
                                              pan_to=(0.8, 0.5)), 0.0)
        self.assertNotEqual(left.tobytes(), right.tobytes())

    def test_interpolates_across_clip_time(self):
        base = _counter()
        c = Controls(zoom_from=1.0, zoom_to=2.0)
        start = apply_controls(base, c, 0.0)
        end = apply_controls(base, c, 1.0)
        self.assertEqual(start.tobytes(), base.tobytes())   # no zoom at t=0
        self.assertNotEqual(end.tobytes(), base.tobytes())  # full zoom at t=1


class TimelineClipTests(unittest.TestCase):
    def test_clip_carries_duration_and_source(self):
        clip = to_timeline_clip("chart", "/tmp/x.mp4", 48, 24.0, start=10,
                                transition="crossfade", transition_frames=6)
        self.assertEqual(clip.id, "chart")
        self.assertEqual(clip.source, "/tmp/x.mp4")
        self.assertEqual(clip.duration, 48)
        self.assertEqual(clip.start, 10)
        self.assertEqual(clip.transition, "crossfade")


if __name__ == "__main__":
    unittest.main()
