"""Frame-accurate timeline with validation and an ffmpeg render (professional-timeline-editing, Phase 1).

Model
- A Timeline has an fps (exact fraction), a frame size, and tracks.
- Track kinds: "video" (sequential clips joined by transitions), "audio" (clips mixed at
  their start frame), "overlay" (images or videos placed on top, with a position).
- Clips are stored in whole frames. Video clips chain: next.start = prev.start + prev.duration
  - next.transition_frames. Gaps, overlaps, and bad transitions are reported before any render.

Not rendered here (validated only): "keyframe" tracks, which the motion module samples, and
"subtitle" tracks, which are burned in by the caption pipeline.
"""
from __future__ import annotations

import json
import subprocess
from dataclasses import asdict, dataclass, field
from fractions import Fraction
from pathlib import Path
from typing import Iterable

TRACK_KINDS = {"video", "audio", "overlay", "subtitle", "keyframe"}
RENDERED_KINDS = {"video", "audio", "overlay"}
TRANSITIONS = {"cut": None, "dissolve": "fade", "dip_black": "fadeblack"}


@dataclass
class Clip:
    id: str
    source: str
    start: int = 0             # frame on the timeline (computed for video tracks)
    duration: int = 0          # frames
    in_point: int = 0          # frame offset in the source (videos only)
    transition: str = "cut"    # video tracks: transition into this clip
    transition_frames: int = 0
    gain_db: float = 0.0       # audio tracks
    x: int = 0                 # overlay position
    y: int = 0
    is_image: bool = False     # overlay/video source that is a still image


@dataclass
class Track:
    kind: str
    name: str
    clips: list[Clip] = field(default_factory=list)


@dataclass
class Timeline:
    fps: Fraction
    width: int
    height: int
    tracks: list[Track] = field(default_factory=list)

    @property
    def total_frames(self) -> int:
        ends = [c.start + c.duration for t in self.tracks for c in t.clips]
        return max(ends, default=0)

    def seconds(self, frames: int) -> float:
        return float(Fraction(frames) / self.fps)


@dataclass(frozen=True)
class Issue:
    level: str   # "error" | "warning"
    code: str
    message: str


# ---------------------------------------------------------------------------
# Load / save
# ---------------------------------------------------------------------------

def timeline_from_dict(data: dict) -> Timeline:
    fps = Fraction(str(data["fps"]))
    tracks = []
    for t in data.get("tracks", []):
        clips = [Clip(**c) for c in t.get("clips", [])]
        tracks.append(Track(kind=t["kind"], name=t.get("name", t["kind"]), clips=clips))
    return Timeline(fps=fps, width=int(data["width"]), height=int(data["height"]), tracks=tracks)


def timeline_to_dict(tl: Timeline) -> dict:
    return {
        "fps": f"{tl.fps.numerator}/{tl.fps.denominator}",
        "width": tl.width,
        "height": tl.height,
        "tracks": [{"kind": t.kind, "name": t.name, "clips": [asdict(c) for c in t.clips]}
                   for t in tl.tracks],
    }


def load_timeline(path: str | Path) -> Timeline:
    return timeline_from_dict(json.loads(Path(path).read_text(encoding="utf-8")))


def save_timeline(tl: Timeline, path: str | Path) -> Path:
    p = Path(path)
    p.parent.mkdir(parents=True, exist_ok=True)
    p.write_text(json.dumps(timeline_to_dict(tl), ensure_ascii=False, indent=2), encoding="utf-8")
    return p


# ---------------------------------------------------------------------------
# Validation
# ---------------------------------------------------------------------------

def validate(tl: Timeline, check_files: bool = True) -> list[Issue]:
    issues: list[Issue] = []

    def err(code, msg):
        issues.append(Issue("error", code, msg))

    def warn(code, msg):
        issues.append(Issue("warning", code, msg))

    if tl.width <= 0 or tl.height <= 0:
        err("bad_frame_size", "width and height must be positive")
    if tl.fps <= 0:
        err("bad_fps", "fps must be positive")

    for t in tl.tracks:
        if t.kind not in TRACK_KINDS:
            err("unknown_track_kind", f"track {t.name!r} has unknown kind {t.kind!r}")
            continue
        if t.kind not in RENDERED_KINDS:
            warn("not_rendered", f"track {t.name!r} ({t.kind}) is validated but not rendered here")
        if t.kind == "video":
            _validate_video_chain(t, err, warn)
        for c in t.clips:
            if c.duration <= 0:
                err("non_positive_duration", f"clip {c.id!r} has duration {c.duration}")
            if c.start < 0 or c.in_point < 0:
                err("negative_time", f"clip {c.id!r} has a negative start or in-point")
            if check_files and t.kind in RENDERED_KINDS and not Path(c.source).exists():
                err("missing_asset", f"clip {c.id!r} source not found: {c.source}")
        # Overlapping clips on non-video tracks would sit on top of each other.
        if t.kind in ("audio", "overlay"):
            ordered = sorted(t.clips, key=lambda c: c.start)
            for a, b in zip(ordered, ordered[1:]):
                if a.start + a.duration > b.start:
                    err("overlap", f"clips {a.id!r} and {b.id!r} overlap on track {t.name!r}")
    return issues


def _validate_video_chain(t: Track, err, warn) -> None:
    clips = t.clips
    if not clips:
        return
    if clips[0].transition_frames:
        warn("transition_on_first_clip", f"first clip {clips[0].id!r} has an incoming transition")
    for i, c in enumerate(clips):
        if c.transition not in TRANSITIONS:
            err("unknown_transition", f"clip {c.id!r} uses unknown transition {c.transition!r}")
        if c.transition == "cut" and c.transition_frames:
            err("missing_transition_type", f"clip {c.id!r} has transition frames but type is 'cut'")
        if c.transition != "cut" and c.transition_frames <= 0:
            err("missing_transition_length", f"clip {c.id!r} has a {c.transition} with zero length")
        if i == 0:
            continue
        prev = clips[i - 1]
        if c.transition_frames > min(prev.duration, c.duration):
            err("transition_too_long", f"transition into {c.id!r} is longer than a neighbouring clip")
        expected = prev.start + prev.duration - c.transition_frames
        if c.start > expected:
            err("gap", f"gap of {c.start - expected} frame(s) before {c.id!r} on track {t.name!r}")
        elif c.start < expected:
            err("conflicting_timing",
                f"{c.id!r} starts {expected - c.start} frame(s) earlier than its transition allows")


# ---------------------------------------------------------------------------
# Render
# ---------------------------------------------------------------------------

def _frames_to_s(frames: int, fps: Fraction) -> str:
    return f"{float(Fraction(frames) / fps):.6f}"


def build_filter_graph(tl: Timeline) -> tuple[list[str], str, str | None]:
    """Return (inputs, filter_complex, audio_label). Video output label is [vout]."""
    inputs: list[str] = []
    parts: list[str] = []
    fps = tl.fps
    W, H = tl.width, tl.height

    def add_input(clip: Clip) -> int:
        idx = len(inputs) // 2
        if clip.is_image:
            length = _frames_to_s(clip.duration, fps)
            inputs.extend(["-loop", "1", "-t", length, "-i", clip.source])
        else:
            inputs.extend(["-i", clip.source])
        return idx

    # Video track: sequential clips chained with xfade or concat.
    video = next((t for t in tl.tracks if t.kind == "video"), None)
    if video and video.clips:
        labels = []
        for c in video.clips:
            i = add_input(c)
            lbl = f"v{i}"
            if c.is_image:
                trim = f"trim=duration={_frames_to_s(c.duration, fps)}"
            else:
                trim = (f"trim=start_frame={c.in_point}:end_frame={c.in_point + c.duration},"
                        f"setpts=PTS-STARTPTS")
            parts.append(
                f"[{i}:v]{trim},scale={W}:{H}:force_original_aspect_ratio=increase,"
                f"crop={W}:{H},fps={fps.numerator}/{fps.denominator},setsar=1,format=yuv420p[{lbl}]"
            )
            labels.append((lbl, c))
        cur, cur_len = labels[0][0], labels[0][1].duration
        for n, (lbl, c) in enumerate(labels[1:], start=1):
            out = f"vc{n}"
            if c.transition == "cut" or c.transition_frames == 0:
                parts.append(f"[{cur}][{lbl}]concat=n=2:v=1:a=0[{out}]")
                cur_len += c.duration
            else:
                d = c.transition_frames
                offset = (cur_len - d) / fps
                parts.append(
                    f"[{cur}][{lbl}]xfade=transition={TRANSITIONS[c.transition]}:"
                    f"duration={_frames_to_s(d, fps)}:offset={float(offset):.6f}[{out}]"
                )
                cur_len += c.duration - d
            cur = out
        parts.append(f"[{cur}]null[vseq]")
        base = "vseq"
    else:
        base = None

    # Overlay tracks: each clip is shifted to its start time and composited on top.
    if base is None:
        parts.append(f"color=c=black:s={W}x{H}:r={fps.numerator}/{fps.denominator}:"
                     f"d={_frames_to_s(tl.total_frames, fps)}[vseq]")
        base = "vseq"
    for t in tl.tracks:
        if t.kind != "overlay":
            continue
        for c in t.clips:
            i = add_input(c)
            lbl = f"ov{i}"
            shift = _frames_to_s(c.start, fps)
            parts.append(f"[{i}:v]setpts=PTS+{shift}/TB,format=rgba[{lbl}]")
            out = f"comp{i}"
            parts.append(f"[{base}][{lbl}]overlay=x={c.x}:y={c.y}:eof_action=pass:shortest=0[{out}]")
            base = out
    parts.append(f"[{base}]null[vout]")

    # Audio tracks: trim, gain, delay to start frame, mix.
    audio_label = None
    audio_parts: list[str] = []
    audio_inputs: list[str] = []
    for t in tl.tracks:
        if t.kind != "audio":
            continue
        for c in t.clips:
            i = add_input(c)
            # Audio comes from the same input index space; use only the audio stream.
            delay_ms = int(round(c.start * 1000 / fps))
            audio_parts.append(
                f"[{i}:a]atrim=start={_frames_to_s(c.in_point, fps)}:"
                f"duration={_frames_to_s(c.duration, fps)},asetpts=PTS-STARTPTS,"
                f"volume={c.gain_db}dB,adelay={delay_ms}:all=1[a{i}]"
            )
            audio_inputs.append(f"[a{i}]")
    if audio_inputs:
        audio_parts.append(
            f"{''.join(audio_inputs)}amix=inputs={len(audio_inputs)}:duration=longest:normalize=0[aout]"
        )
        audio_label = "aout"
    parts.extend(audio_parts)
    return inputs, ";".join(parts), audio_label


def render(tl: Timeline, out: str | Path, crf: int = 18) -> Path:
    issues = [i for i in validate(tl) if i.level == "error"]
    if issues:
        raise ValueError("timeline has errors: " + "; ".join(f"[{i.code}] {i.message}" for i in issues))
    inputs, graph, audio_label = build_filter_graph(tl)
    out = Path(out)
    out.parent.mkdir(parents=True, exist_ok=True)
    cmd = ["ffmpeg", "-hide_banner", "-loglevel", "error", "-y", *inputs,
           "-filter_complex", graph, "-map", "[vout]"]
    if audio_label:
        cmd += ["-map", f"[{audio_label}]", "-c:a", "aac", "-b:a", "192k"]
    cmd += ["-t", _frames_to_s(tl.total_frames, tl.fps),
            "-c:v", "libx264", "-preset", "medium", "-crf", str(crf), "-pix_fmt", "yuv420p",
            "-r", f"{tl.fps.numerator}/{tl.fps.denominator}",
            "-map_metadata", "-1", "-movflags", "+faststart", str(out)]
    proc = subprocess.run(cmd, capture_output=True, text=True)
    if proc.returncode != 0:
        raise RuntimeError(f"timeline render failed: {proc.stderr.strip()[-800:]}")
    return out
