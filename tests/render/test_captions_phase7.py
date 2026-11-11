"""Phase 7 render: the new caption styles and Vietnamese burn onto video with libass."""
import shutil
import subprocess
import tempfile
import unittest
from pathlib import Path

from uvs.captions import build_captions, to_ass, Word
from uvs.render import make_base, burn_captions
from uvs.speech import ClickTrackTTS, VoiceSpec, detect_silences, speech_segments

HAS_FFMPEG = shutil.which("ffmpeg") is not None and shutil.which("ffprobe") is not None


@unittest.skipUnless(HAS_FFMPEG, "ffmpeg not installed")
class CaptionRenderTests(unittest.TestCase):
    def setUp(self):
        self._tmp = tempfile.TemporaryDirectory()
        self.dir = Path(self._tmp.name)

    def tearDown(self):
        self._tmp.cleanup()

    def _render(self, style, words, keywords, tag):
        b = build_captions(words, style, frame_w=720, frame_h=1280, keywords=keywords)
        ass = self.dir / f"{tag}.ass"
        ass.write_text(to_ass(b.cues, b.style, 720, 1280, keys=b.keys), encoding="utf-8")
        base = make_base(self.dir / f"base_{tag}.mp4", 720, 1280, 30, 2.5)
        out = self.dir / f"cap_{tag}.mp4"
        burn_captions(base, ass, out)
        return out

    def test_new_styles_render(self):
        en = [Word("Learning", 0.0, 0.6), Word("to", 0.6, 0.8), Word("say", 0.8, 1.2),
              Word("no", 1.2, 1.8), Word("matters", 1.8, 2.4)]
        for style in ("clean_modern", "podcast_highlight", "educational"):
            with self.subTest(style=style):
                out = self._render(style, en, ["no"], style)
                self.assertTrue(out.exists() and out.stat().st_size > 0)

    def test_vietnamese_captions_render(self):
        vi = [Word("Tôi", 0.0, 0.5), Word("học", 0.5, 1.0), Word("cách", 1.0, 1.5),
              Word("nói", 1.5, 2.0), Word("không", 2.0, 2.4)]
        out = self._render("educational", vi, ["không"], "vi")
        probe = subprocess.run(["ffprobe", "-v", "error", "-select_streams", "v:0",
                                "-show_entries", "stream=width,height", "-of", "csv=p=0", str(out)],
                               capture_output=True, text=True, check=True)
        self.assertEqual(probe.stdout.strip(), "720,1280")

    def test_click_track_drives_silence_segmentation(self):
        words = [Word("one", 0.0, 0.4), Word("two", 1.2, 1.6), Word("three", 2.4, 2.8)]
        wav = self.dir / "c.wav"
        ClickTrackTTS().synthesize(words, wav, VoiceSpec(sample_rate=16000))
        sils = detect_silences(wav, noise_db=-40, min_silence=0.4)
        self.assertGreaterEqual(len(sils), 2)
        segs = speech_segments(wav, noise_db=-40, min_silence=0.4)
        self.assertTrue(any(s.kind == "speech" for s in segs))


if __name__ == "__main__":
    unittest.main()
