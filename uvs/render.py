"""Render pipeline: synthetic base clip -> burned-in captions (libass) -> H.264/AAC -> QA.

The base clip is a generated gradient with a low sine tone. It is a pipeline test
signal, not footage and not narration. Real footage and voice audio are not bundled.
"""
from __future__ import annotations

import argparse
import json
import subprocess
import sys
from pathlib import Path

from uvs.captions import build_captions, write_outputs
from uvs.qa import QAConfig, run_qa

HERE = Path(__file__).resolve().parent.parent
DEMO_WORDS = HERE / "examples" / "demo_caption" / "words.json"


def _ffmpeg(args: list[str], cwd: str | None = None) -> None:
    proc = subprocess.run(["ffmpeg", "-hide_banner", "-loglevel", "error", "-y", *args],
                          capture_output=True, text=True, cwd=cwd)
    if proc.returncode != 0:
        raise RuntimeError(f"ffmpeg failed: {proc.stderr.strip()[-600:]}")


def make_base(out: str | Path, width: int, height: int, fps: int, duration: float,
              tone_hz: float = 220.0) -> Path:
    """Generate a synthetic gradient clip with a quiet sine tone (pipeline test signal only)."""
    out = Path(out)
    out.parent.mkdir(parents=True, exist_ok=True)
    _ffmpeg([
        "-f", "lavfi", "-i", f"gradients=s={width}x{height}:d={duration}:r={fps}:"
                             f"c0=0x1d2b3a:c1=0xc8a165:speed=0.03",
        "-f", "lavfi", "-i", f"sine=frequency={tone_hz}:duration={duration}:sample_rate=48000",
        "-filter:a", "volume=-20dB",
        "-t", str(duration),
        "-map", "0:v:0", "-map", "1:a:0",
        "-c:v", "libx264", "-preset", "medium", "-crf", "18", "-pix_fmt", "yuv420p",
        "-c:a", "aac", "-b:a", "192k",
        "-map_metadata", "-1", "-movflags", "+faststart",
        str(out),
    ])
    return out


def burn_captions(base: str | Path, ass_file: str | Path, out: str | Path) -> Path:
    """Overlay an ASS subtitle file onto the base video with libass and encode H.264/AAC."""
    base = Path(base).resolve()
    ass_file = Path(ass_file).resolve()
    out = Path(out).resolve()
    out.parent.mkdir(parents=True, exist_ok=True)
    # Run from the ASS folder with a plain filename so the filter argument needs no escaping.
    _ffmpeg([
        "-i", str(base),
        "-vf", f"ass=filename={ass_file.name}",
        "-c:v", "libx264", "-preset", "medium", "-crf", "18", "-pix_fmt", "yuv420p",
        "-c:a", "copy",
        "-map_metadata", "-1", "-movflags", "+faststart",
        str(out),
    ], cwd=str(ass_file.parent))
    return out


def render_captioned(words: str | Path, out_dir: str | Path, style: str = "bold_shorts",
                     width: int = 1080, height: int = 1920, fps: int = 30,
                     keywords: tuple[str, ...] = (), auto_numbers: bool = False,
                     duration: float | None = None) -> dict:
    out_dir = Path(out_dir)
    out_dir.mkdir(parents=True, exist_ok=True)

    build = build_captions(words, style, width, height, keywords, auto_numbers)
    if build.errors:
        raise ValueError("caption build has errors: " +
                         "; ".join(f"[{i.code}] {i.message}" for i in build.errors))
    files = write_outputs(build, out_dir, stem="captions")

    last_end = max(c.end for c in build.cues)
    total = duration if duration is not None else round(last_end + 0.6, 2)
    base = make_base(out_dir / "base.mp4", width, height, fps, total)
    final = burn_captions(base, files["ass"], out_dir / "final.mp4")

    qa_cfg = QAConfig(expect_width=width, expect_height=height, expect_fps=float(fps),
                      expect_duration=total, duration_tolerance=0.15)
    report = run_qa(final, qa_cfg)
    qa_path = out_dir / "qa_report.json"
    qa_path.write_text(json.dumps(report.to_dict(), ensure_ascii=False, indent=2), encoding="utf-8")

    return {
        "final": str(final),
        "base": str(base),
        "captions": files,
        "qa": str(qa_path),
        "qa_overall": report.overall,
        "cues": len(build.cues),
        "caption_warnings": [i.__dict__ for i in build.issues if i.level == "warning"],
    }


def main(argv: list[str] | None = None) -> int:
    p = argparse.ArgumentParser(description="Render captioned video from word timings.")
    p.add_argument("words", nargs="?", default=str(DEMO_WORDS), help="word timing JSON")
    p.add_argument("--out", default="out/render")
    p.add_argument("--style", default="bold_shorts")
    p.add_argument("--width", type=int, default=1080)
    p.add_argument("--height", type=int, default=1920)
    p.add_argument("--fps", type=int, default=30)
    p.add_argument("--keywords", default="cháo,5")
    p.add_argument("--auto-numbers", action="store_true")
    args = p.parse_args(argv)
    kws = tuple(k.strip() for k in args.keywords.split(",") if k.strip())
    result = render_captioned(args.words, args.out, args.style, args.width, args.height, args.fps,
                              kws, args.auto_numbers)
    print(json.dumps(result, ensure_ascii=False, indent=2))
    return 0 if result["qa_overall"] != "fail" else 1


if __name__ == "__main__":
    sys.exit(main())
