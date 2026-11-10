"""Technical quality checks for rendered video (video-quality-assurance).

Uses ffprobe for stream facts and ffmpeg analysis filters for black frames, frozen
frames, silence, clipping and EBU R128 loudness / true peak. Every check reports a
measured value. Creative scores are not produced here.

Parsing is kept in pure functions so it can be unit-tested without media files.
"""
from __future__ import annotations

import argparse
import json
import re
import subprocess
import sys
from dataclasses import asdict, dataclass, field
from fractions import Fraction
from pathlib import Path


@dataclass
class QAConfig:
    expect_width: int | None = 1080
    expect_height: int | None = 1920
    expect_fps: float | None = 30.0
    expect_video_codec: str | None = "h264"
    expect_audio_codec: str | None = "aac"
    expect_duration: float | None = None
    duration_tolerance: float = 0.1
    black_min_duration: float = 0.5
    freeze_min_duration: float = 1.0
    silence_min_duration: float = 1.0
    clip_threshold_db: float = -0.1      # max sample peak at/above this suggests clipping
    true_peak_max_dbtp: float = -1.0     # warn when true peak exceeds this
    loudness_target_lufs: float | None = None
    loudness_tolerance_lu: float = 1.0


@dataclass
class Check:
    id: str
    category: str
    status: str   # "pass" | "warn" | "fail" | "info"
    detail: str
    value: object = None


@dataclass
class QAReport:
    file: str
    checks: list[Check] = field(default_factory=list)

    @property
    def overall(self) -> str:
        statuses = {c.status for c in self.checks}
        if "fail" in statuses:
            return "fail"
        if "warn" in statuses:
            return "warn"
        return "pass"

    def to_dict(self) -> dict:
        counts = {s: 0 for s in ("pass", "warn", "fail", "info")}
        for c in self.checks:
            counts[c.status] += 1
        return {"file": self.file, "overall": self.overall, "summary": counts,
                "checks": [asdict(c) for c in self.checks]}


# ---------------------------------------------------------------------------
# Pure parsers (testable without media)
# ---------------------------------------------------------------------------

BLACK_RE = re.compile(r"black_start:(?P<s>[\d.]+)\s+black_end:(?P<e>[\d.]+)\s+black_duration:(?P<d>[\d.]+)")
FREEZE_START_RE = re.compile(r"freeze_start:\s*(?P<s>[\d.]+)")
FREEZE_DUR_RE = re.compile(r"freeze_duration:\s*(?P<d>[\d.]+)")
SILENCE_END_RE = re.compile(r"silence_end:\s*(?P<e>-?[\d.]+)\s*\|\s*silence_duration:\s*(?P<d>[\d.]+)")
SILENCE_START_RE = re.compile(r"silence_start:\s*(?P<s>-?[\d.]+)")
MEAN_VOL_RE = re.compile(r"mean_volume:\s*(?P<v>-?[\d.]+)\s*dB")
MAX_VOL_RE = re.compile(r"max_volume:\s*(?P<v>-?[\d.]+)\s*dB")
LUFS_RE = re.compile(r"\bI:\s*(?P<v>-?[\d.]+)\s*LUFS")
TRUE_PEAK_RE = re.compile(r"Peak:\s*(?P<v>-?[\d.]+)\s*dBFS")


def parse_blackdetect(stderr: str) -> list[tuple[float, float, float]]:
    return [(float(m["s"]), float(m["e"]), float(m["d"])) for m in BLACK_RE.finditer(stderr)]


def parse_freezedetect(stderr: str) -> list[tuple[float, float]]:
    starts = [float(m["s"]) for m in FREEZE_START_RE.finditer(stderr)]
    durs = [float(m["d"]) for m in FREEZE_DUR_RE.finditer(stderr)]
    return list(zip(starts, durs))


def parse_silencedetect(stderr: str) -> list[tuple[float, float]]:
    """Return (silence_duration, silence_end) pairs. Starts are not needed for the report."""
    return [(float(m["d"]), float(m["e"])) for m in SILENCE_END_RE.finditer(stderr)]


def parse_volumedetect(stderr: str) -> dict[str, float]:
    out: dict[str, float] = {}
    if m := MEAN_VOL_RE.search(stderr):
        out["mean_db"] = float(m["v"])
    if m := MAX_VOL_RE.search(stderr):
        out["max_db"] = float(m["v"])
    return out


def parse_ebur128_summary(stderr: str) -> dict[str, float]:
    """Read the final 'Summary:' block only. Per-frame lines also contain 'I:' values, and the
    early ones are gated (for example -70 LUFS) before any block passes the gate."""
    out: dict[str, float] = {}
    idx = stderr.rfind("Summary:")
    if idx < 0:
        return out
    summary = stderr[idx:]
    if m := LUFS_RE.search(summary):
        out["integrated_lufs"] = float(m["v"])
    if m := TRUE_PEAK_RE.search(summary):
        out["true_peak_dbtp"] = float(m["v"])
    return out


# ---------------------------------------------------------------------------
# ffmpeg / ffprobe runners
# ---------------------------------------------------------------------------

def _run(args: list[str]) -> subprocess.CompletedProcess:
    return subprocess.run(args, capture_output=True, text=True)


def probe(path: str | Path) -> dict:
    proc = _run(["ffprobe", "-v", "error", "-print_format", "json", "-show_format", "-show_streams", str(path)])
    if proc.returncode != 0:
        raise RuntimeError(f"ffprobe failed: {proc.stderr.strip()}")
    return json.loads(proc.stdout)


def _fps(stream: dict) -> float | None:
    rate = stream.get("avg_frame_rate") or stream.get("r_frame_rate")
    if not rate or rate == "0/0":
        return None
    return float(Fraction(rate))


def _analysis(path: str, vf: str | None = None, af: str | None = None, map_: str | None = None) -> str:
    cmd = ["ffmpeg", "-hide_banner", "-nostats", "-i", path]
    if map_:
        cmd += ["-map", map_]
    if vf:
        cmd += ["-vf", vf, "-an"]
    if af:
        cmd += ["-af", af, "-vn"]
    cmd += ["-f", "null", "-"]
    proc = _run(cmd)
    if proc.returncode != 0:
        raise RuntimeError(f"ffmpeg analysis failed ({vf or af}): {proc.stderr.strip()[-400:]}")
    return proc.stderr


# ---------------------------------------------------------------------------
# Checks
# ---------------------------------------------------------------------------

def run_qa(path: str | Path, cfg: QAConfig = QAConfig()) -> QAReport:
    path = str(path)
    report = QAReport(file=path)
    info = probe(path)
    streams = info.get("streams", [])
    video = next((s for s in streams if s.get("codec_type") == "video"), None)
    audio = next((s for s in streams if s.get("codec_type") == "audio"), None)
    duration = float(info.get("format", {}).get("duration", 0.0))

    # --- technical -------------------------------------------------------
    if video is None:
        report.checks.append(Check("video_stream", "technical", "fail", "no video stream"))
        return report
    report.checks.append(Check("video_stream", "technical", "pass", "video stream present"))

    if cfg.expect_width and cfg.expect_height:
        w, h = int(video["width"]), int(video["height"])
        ok = (w, h) == (cfg.expect_width, cfg.expect_height)
        report.checks.append(Check("dimensions", "technical", "pass" if ok else "fail",
                                   f"{w}x{h}, expected {cfg.expect_width}x{cfg.expect_height}", [w, h]))

    if cfg.expect_fps:
        fps = _fps(video)
        ok = fps is not None and abs(fps - cfg.expect_fps) < 0.01
        report.checks.append(Check("fps", "technical", "pass" if ok else "fail",
                                   f"{fps:.3f} fps, expected {cfg.expect_fps:g}" if fps else "fps unknown",
                                   fps))

    if cfg.expect_video_codec:
        codec = video.get("codec_name")
        report.checks.append(Check("video_codec", "technical",
                                   "pass" if codec == cfg.expect_video_codec else "fail",
                                   f"codec {codec}, expected {cfg.expect_video_codec}", codec))

    if cfg.expect_duration is not None:
        ok = abs(duration - cfg.expect_duration) <= cfg.duration_tolerance
        report.checks.append(Check("duration", "technical", "pass" if ok else "fail",
                                   f"{duration:.3f}s, expected {cfg.expect_duration:.3f}s ±{cfg.duration_tolerance}",
                                   duration))

    decode = _run(["ffmpeg", "-v", "error", "-i", path, "-f", "null", "-"])
    decode_ok = decode.returncode == 0 and not decode.stderr.strip()
    report.checks.append(Check("decode", "technical", "pass" if decode_ok else "fail",
                               "full decode without errors" if decode_ok
                               else f"decode errors: {decode.stderr.strip()[-300:]}"))

    if audio is None:
        report.checks.append(Check("audio_stream", "audio", "fail", "no audio stream"))
    else:
        report.checks.append(Check("audio_stream", "audio", "pass", "audio stream present"))
        if cfg.expect_audio_codec:
            acodec = audio.get("codec_name")
            report.checks.append(Check("audio_codec", "technical",
                                       "pass" if acodec == cfg.expect_audio_codec else "fail",
                                       f"codec {acodec}, expected {cfg.expect_audio_codec}", acodec))
        a_dur = float(audio.get("duration", duration) or duration)
        v_dur = float(video.get("duration", duration) or duration)
        drift = abs(a_dur - v_dur)
        report.checks.append(Check("av_sync_duration", "timeline",
                                   "pass" if drift <= 0.1 else "warn",
                                   f"audio {a_dur:.3f}s vs video {v_dur:.3f}s (drift {drift:.3f}s)", drift))

    # --- visual ----------------------------------------------------------
    blacks = parse_blackdetect(_analysis(path, vf=f"blackdetect=d={cfg.black_min_duration}:pix_th=0.10"))
    if blacks:
        report.checks.append(Check("black_frames", "visual", "warn",
                                   f"{len(blacks)} black interval(s), first at {blacks[0][0]:.2f}s",
                                   [round(b[0], 3) for b in blacks]))
    else:
        report.checks.append(Check("black_frames", "visual", "pass", "no black intervals"))

    frozen = [f for f in parse_freezedetect(
        _analysis(path, vf=f"freezedetect=n=0.003:d={cfg.freeze_min_duration}")) if f[1] >= cfg.freeze_min_duration]
    report.checks.append(Check("frozen_frames", "visual", "warn" if frozen else "pass",
                               f"{len(frozen)} frozen interval(s) >= {cfg.freeze_min_duration}s" if frozen
                               else "no frozen intervals", [round(f[0], 3) for f in frozen]))

    # --- audio -----------------------------------------------------------
    if audio is not None:
        sil = [s for s in parse_silencedetect(
            _analysis(path, af=f"silencedetect=noise=-50dB:d={cfg.silence_min_duration}", map_="0:a:0"))
            if s[0] >= cfg.silence_min_duration]
        report.checks.append(Check("long_silence", "audio", "warn" if sil else "pass",
                                   f"{len(sil)} silence gap(s) >= {cfg.silence_min_duration}s" if sil
                                   else "no long silence", [round(s[0], 3) for s in sil]))

        vol = parse_volumedetect(_analysis(path, af="volumedetect", map_="0:a:0"))
        if "max_db" in vol:
            clipped = vol["max_db"] >= cfg.clip_threshold_db
            report.checks.append(Check("clipping", "audio", "fail" if clipped else "pass",
                                       f"max sample {vol['max_db']:.1f} dBFS", vol["max_db"]))
        if "mean_db" in vol:
            report.checks.append(Check("mean_level", "audio", "info",
                                       f"mean {vol['mean_db']:.1f} dBFS", vol["mean_db"]))

        loud = parse_ebur128_summary(_analysis(path, af="ebur128=peak=true", map_="0:a:0"))
        if "true_peak_dbtp" in loud:
            tp = loud["true_peak_dbtp"]
            report.checks.append(Check("true_peak", "audio",
                                       "pass" if tp <= cfg.true_peak_max_dbtp else "warn",
                                       f"true peak {tp:.1f} dBTP, limit {cfg.true_peak_max_dbtp:g}", tp))
        if "integrated_lufs" in loud:
            lufs = loud["integrated_lufs"]
            status, detail = "info", f"integrated loudness {lufs:.1f} LUFS (measured, no target set)"
            if cfg.loudness_target_lufs is not None:
                ok = abs(lufs - cfg.loudness_target_lufs) <= cfg.loudness_tolerance_lu
                status = "pass" if ok else "warn"
                detail = (f"integrated {lufs:.1f} LUFS, target {cfg.loudness_target_lufs:g} "
                          f"±{cfg.loudness_tolerance_lu:g}")
            report.checks.append(Check("loudness", "audio", status, detail, lufs))

    return report


def main(argv: list[str] | None = None) -> int:
    p = argparse.ArgumentParser(description="Run technical QA on a rendered video.")
    p.add_argument("video")
    p.add_argument("--width", type=int, default=1080)
    p.add_argument("--height", type=int, default=1920)
    p.add_argument("--fps", type=float, default=30.0)
    p.add_argument("--codec", default="h264")
    p.add_argument("--duration", type=float, default=None)
    p.add_argument("--target-lufs", type=float, default=None)
    p.add_argument("--json", default=None, help="write the full report to this path")
    args = p.parse_args(argv)

    cfg = QAConfig(expect_width=args.width, expect_height=args.height, expect_fps=args.fps,
                   expect_video_codec=args.codec, expect_duration=args.duration,
                   loudness_target_lufs=args.target_lufs)
    report = run_qa(args.video, cfg)
    data = report.to_dict()
    if args.json:
        Path(args.json).parent.mkdir(parents=True, exist_ok=True)
        Path(args.json).write_text(json.dumps(data, ensure_ascii=False, indent=2), encoding="utf-8")
    print(json.dumps(data, ensure_ascii=False, indent=2))
    return 1 if report.overall == "fail" else 0


if __name__ == "__main__":
    sys.exit(main())
