"""End-to-end pipeline (Phase 6): words -> director plan -> captions -> timeline -> grade
-> captions burn-in -> audio mix -> mux -> QA. Each stage is timed and recorded in a report.

Stand-in media: when a voice, music, footage, or impact sound is not given, the pipeline
generates a clearly labelled synthetic stand-in. Synthetic audio is a tone per word, not speech.
Synthetic footage is a gradient, not real footage. Every stand-in is listed in the report.
"""
from __future__ import annotations

import array
import json
import math
import subprocess
import sys
import time
import wave
from dataclasses import asdict
from fractions import Fraction
from pathlib import Path

from uvs import audio as A
from uvs.backend import default_backend
from uvs import captions as C
from uvs import director as D
from uvs import grade as G
from uvs import qa as Q
from uvs import timeline as T
from uvs.styles import StyleLock

RATE = 48000
TAIL_SECONDS = 0.6
SYNTH_FOOTAGE_PALETTES = [("0x1d2b3a", "0xc8a165"), ("0x2a3d2f", "0xd9c27a"), ("0x3b2238", "0x7aa5c9")]


# ---------------------------------------------------------------------------
# Synthetic stand-ins
# ---------------------------------------------------------------------------

def _write_wav(path: Path, samples: list[float]) -> Path:
    path.parent.mkdir(parents=True, exist_ok=True)
    pcm = array.array("h", (int(max(-1.0, min(1.0, s)) * 32767) for s in samples))
    with wave.open(str(path), "wb") as w:
        w.setnchannels(1)
        w.setsampwidth(2)
        w.setframerate(RATE)
        w.writeframes(pcm.tobytes())
    return path


def synth_voice(words: list[C.Word], total: float, path: Path) -> Path:
    """One short tone burst per word, at the word's timing. A rhythm stand-in, not speech."""
    n = int(total * RATE)
    buf = [0.0] * n
    for w in words:
        a, b = int(w.start * RATE), min(n, int(w.end * RATE))
        span = max(1, b - a)
        for i in range(a, b):
            env = min(1.0, (i - a) / (0.01 * RATE), (b - i) / (0.01 * RATE))
            buf[i] += 0.28 * env * math.sin(2 * math.pi * 300 * (i / RATE))
    return _write_wav(path, buf)


def synth_music(total: float, path: Path) -> Path:
    n = int(total * RATE)
    buf = [0.09 * math.sin(2 * math.pi * 220 * i / RATE) + 0.06 * math.sin(2 * math.pi * 330 * i / RATE)
           for i in range(n)]
    return _write_wav(path, buf)


def synth_impact(path: Path, seconds: float = 0.6) -> Path:
    n = int(seconds * RATE)
    buf = [0.7 * math.exp(-8 * i / RATE) * math.sin(2 * math.pi * 80 * i / RATE) for i in range(n)]
    return _write_wav(path, buf)


def make_synthetic_footage(folder: Path, width: int, height: int, fps: int, seconds: float) -> list[Path]:
    folder.mkdir(parents=True, exist_ok=True)
    files = []
    for n, (c0, c1) in enumerate(SYNTH_FOOTAGE_PALETTES):
        p = folder / f"footage_{n}.mp4"
        proc = subprocess.run(
            ["ffmpeg", "-hide_banner", "-loglevel", "error", "-y", "-f", "lavfi", "-i",
             f"gradients=s={width}x{height}:d={seconds}:r={fps}:c0={c0}:c1={c1}:speed=0.03",
             "-c:v", "libx264", "-pix_fmt", "yuv420p", "-map_metadata", "-1", str(p)],
            capture_output=True, text=True)
        if proc.returncode != 0:
            raise RuntimeError(f"synthetic footage failed: {proc.stderr.strip()[-300:]}")
        files.append(p)
    return files


def _duration(path: Path) -> float:
    out = subprocess.run(["ffprobe", "-v", "error", "-show_entries", "format=duration", "-of", "json", str(path)],
                         capture_output=True, text=True, check=True).stdout
    return float(json.loads(out)["format"]["duration"])


# ---------------------------------------------------------------------------
# Timeline from the director plan
# ---------------------------------------------------------------------------

def build_timeline(plan: dict, footage: list[Path], fps: int, width: int, height: int,
                   decisions: list[str]) -> tuple[T.Timeline, int]:
    scenes = plan["scenes"]
    rate = Fraction(fps)
    start0 = scenes[0]["start"]
    starts = [round((s["start"] - start0) * fps) for s in scenes]   # frame of each scene
    total_frames = round((plan["duration"] - start0 + TAIL_SECONDS) * fps)
    lengths = [starts[i + 1] - starts[i] for i in range(len(scenes) - 1)] + [total_frames - starts[-1]]

    # Transition into scene i (i >= 1), clamped so it never exceeds a neighbouring scene.
    trans_frames = [0]
    for i in range(1, len(scenes)):
        wanted = round(scenes[i]["transition_duration"] * fps)
        allowed = min(lengths[i - 1], lengths[i])
        t = min(wanted, allowed)
        if t < wanted:
            decisions.append(f"{scenes[i]['id']}: transition clamped from {wanted} to {t} frames")
        if scenes[i]["transition"] == "cut" or t == 0:
            t = 0
        trans_frames.append(t)

    clips = []
    for i, s in enumerate(scenes):
        src = footage[i % len(footage)]
        t_in = trans_frames[i]
        # The next clip overlaps this one by its transition, so extend this clip by that amount.
        dur = lengths[i] + (trans_frames[i + 1] if i + 1 < len(scenes) else 0)
        clips.append(T.Clip(
            id=s["id"], source=str(src), start=starts[i], duration=dur,
            transition=("cut" if t_in == 0 else s["transition"]), transition_frames=t_in,
        ))
    # Source footage must cover each clip.
    for c in clips:
        if _duration(Path(c.source)) + 1e-6 < c.duration / fps:
            raise ValueError(f"footage {c.source} is shorter than clip {c.id}")
    tl = T.Timeline(fps=rate, width=width, height=height, tracks=[T.Track("video", "main", clips)])
    return tl, total_frames


# ---------------------------------------------------------------------------
# Run
# ---------------------------------------------------------------------------

def _mux(video: Path, audio_file: Path, out: Path) -> Path:
    proc = subprocess.run(
        ["ffmpeg", "-hide_banner", "-loglevel", "error", "-y", "-i", str(video), "-i", str(audio_file),
         "-map", "0:v:0", "-map", "1:a:0", "-c:v", "copy", "-c:a", "copy", "-shortest",
         "-map_metadata", "-1", "-movflags", "+faststart", str(out)],
        capture_output=True, text=True)
    if proc.returncode != 0:
        raise RuntimeError(f"mux failed: {proc.stderr.strip()[-400:]}")
    return out


def validate_spec(spec: dict) -> list[str]:
    """Validate a pipeline spec before running (fixes D-02). Returns a list of problems."""
    problems: list[str] = []
    if "words" not in spec:
        problems.append("spec is missing 'words'")
    genre = spec.get("genre")
    if genre is None:
        problems.append("spec is missing 'genre'")
    elif genre not in D.GENRES:
        problems.append(f"unknown genre {genre!r}; choose from {sorted(D.GENRES)}")
    for key in ("width", "height", "fps"):
        if key in spec:
            try:
                if int(spec[key]) <= 0:
                    problems.append(f"{key} must be positive")
            except (TypeError, ValueError):
                problems.append(f"{key} must be an integer")
    if "style" in spec:
        from uvs.styles import STYLES
        if spec["style"] not in STYLES:
            problems.append(f"unknown style {spec['style']!r}; choose from {sorted(STYLES)}")
    if "footage" in spec and not isinstance(spec["footage"], list):
        problems.append("'footage' must be a list of paths")
    return problems


def run(spec_path: str | Path, out_dir: str | Path) -> dict:
    spec_path = Path(spec_path)
    spec = json.loads(spec_path.read_text(encoding="utf-8"))
    problems = validate_spec(spec)
    if problems:
        raise ValueError("invalid spec: " + "; ".join(problems))
    base = spec_path.parent
    out = Path(out_dir)
    out.mkdir(parents=True, exist_ok=True)
    W, H, fps = int(spec.get("width", 1080)), int(spec.get("height", 1920)), int(spec.get("fps", 30))
    stages: list[dict] = []
    stand_ins: list[str] = []
    decisions: list[str] = []

    def stage(name, fn):
        t0 = time.perf_counter()
        result = fn()
        stages.append({"stage": name, "seconds": round(time.perf_counter() - t0, 2)})
        return result

    # 1. Analyze
    words = stage("load_words", lambda: C.load_words(base / spec["words"]))
    plan = stage("director", lambda: D.plan(words, spec["genre"], spec.get("title", "untitled")))
    for s in plan["scenes"]:
        decisions.extend(f"{s['id']}: {d}" for d in s["decisions"])
    D.write_plan(plan, out / "director_plan.json")
    total = round(plan["duration"] - plan["scenes"][0]["start"] + TAIL_SECONDS, 3)

    # 2. Captions
    style = D.GENRES[spec["genre"]]["caption"]
    caption_build = stage("captions", lambda: C.build_captions(
        words, style, W, H, spec.get("keywords", []), spec.get("auto_numbers", False)))
    if caption_build.errors:
        raise ValueError("caption errors: " + "; ".join(f"[{i.code}] {i.message}" for i in caption_build.errors))
    cap_files = C.write_outputs(caption_build, out, "captions")

    # 3. Footage and timeline
    if spec.get("footage"):
        footage = [base / p for p in spec["footage"]]
    else:
        footage = stage("synthetic_footage", lambda: make_synthetic_footage(out / "footage", W, H, fps, total + 2))
        stand_ins.append(f"footage: {len(footage)} synthetic gradient clips (not real footage)")
    missing = [str(p) for p in footage if not p.exists()]
    if missing:
        raise FileNotFoundError("footage not found: " + ", ".join(missing))
    tl, total_frames = stage("timeline", lambda: build_timeline(plan, footage, fps, W, H, decisions))
    errors = [i for i in T.validate(tl) if i.level == "error"]
    if errors:
        raise ValueError("timeline errors: " + "; ".join(f"[{i.code}] {i.message}" for i in errors))
    backend = default_backend()
    timeline_mp4 = stage("render_timeline", lambda: backend.render_timeline(tl, out / "timeline.mp4"))
    applied_transitions = {"cut": 0, "dissolve": 0, "dip_black": 0}
    for c in tl.tracks[0].clips[1:]:
        applied_transitions[c.transition] += 1

    # 4. Grade. Style Lock (fixes D-01): the look comes from an explicit project style, not from
    # whatever look scene 0 happened to carry. A locked style is resolved once and applied to every
    # scene. If no style is named, fall back to the legacy scene-0 look but record it as a fallback.
    style_name = spec.get("style")
    if style_name:
        lock = StyleLock.resolve(style_name)
        look = lock.style.color_grade
        intensity = spec.get("look_intensity", lock.style.color_intensity)
        decisions.append(f"style lock: preset '{style_name}' -> look '{look}' at '{intensity}', "
                         f"applied identically to all {len(plan['scenes'])} scenes")
    else:
        look = plan["scenes"][0]["color_look"]
        intensity = spec.get("look_intensity", "standard")
        decisions.append(f"style lock: no project style named; fell back to scene-0 look '{look}' "
                         f"at '{intensity}' (set spec['style'] to lock a preset)")
    graded = stage("grade", lambda: G.grade(timeline_mp4, out / "graded.mp4", G.look_filter(look, intensity)))

    # 5. Captions burn-in (after grading, so captions keep their colours)
    captioned = stage("burn_captions", lambda: backend.burn_captions(graded, cap_files["ass"], out / "video_captioned.mp4"))

    # 6. Audio
    if spec.get("voice"):
        voice = base / spec["voice"]
    else:
        voice = stage("synth_voice", lambda: synth_voice(words, total, out / "voice_synthetic.wav"))
        stand_ins.append("voice: tone burst per word at the word timing (not speech)")
    if spec.get("music"):
        music = base / spec["music"]
    else:
        music = stage("synth_music", lambda: synth_music(total, out / "music_synthetic.wav"))
        stand_ins.append("music: two steady sine tones (not music)")
    mean_level = sum(s["music_level"] for s in plan["scenes"]) / len(plan["scenes"])
    music_gain = round(20 * math.log10(mean_level / 0.4), 2)
    decisions.append(f"music gain {music_gain:+.2f} dB from mean plan music level {mean_level:.2f}")
    clips = [A.AudioClip("VOICE", str(voice), duration=total),
             A.AudioClip("MUSIC", str(music), duration=total, gain_db=A.CATEGORIES["MUSIC"] + music_gain)]
    impact_scenes = [s for s in plan["scenes"] if s["sfx"]]
    if impact_scenes:
        impact = stage("synth_impact", lambda: synth_impact(out / "sfx_impact.wav"))
        stand_ins.append("sfx: one synthetic low impact at each turning point")
        for s in impact_scenes:
            clips.append(A.AudioClip("SFX", str(impact), start=round(s["start"] - plan["scenes"][0]["start"], 3)))
    mix = stage("audio_mix", lambda: A.mix_to_file(clips, out / "audio_mix.m4a", target_lufs=-14.0,
                                                   true_peak=-1.5, duration=total))

    # 7. Mux and QA
    final = stage("mux", lambda: _mux(captioned, out / "audio_mix.m4a", out / "final.mp4"))
    qa_cfg = Q.QAConfig(expect_width=W, expect_height=H, expect_fps=float(fps), expect_duration=total,
                        duration_tolerance=0.15, loudness_target_lufs=-14.0, loudness_tolerance_lu=1.0)
    qa = stage("qa", lambda: Q.run_qa(final, qa_cfg))
    qa_dict = qa.to_dict()
    (out / "qa_report.json").write_text(json.dumps(qa_dict, ensure_ascii=False, indent=2), encoding="utf-8")

    report = {
        "title": plan["title"],
        "genre": spec["genre"],
        "final": str(final),
        "duration_seconds": total,
        "scenes": len(plan["scenes"]),
        # Count only transitions actually applied on the timeline (the first clip has none).
        "transitions": applied_transitions,
        "qa_overall": qa.overall,
        "stand_ins": stand_ins,
        "decisions": decisions,
        "stages": stages,
        "audio": mix["measured_input"],
    }
    (out / "pipeline_report.json").write_text(json.dumps(report, ensure_ascii=False, indent=2), encoding="utf-8")
    return report


def main(argv: list[str] | None = None) -> int:
    argv = sys.argv[1:] if argv is None else argv
    if len(argv) != 2:
        print("usage: python3 -m uvs.pipeline <spec.json> <out_dir>", file=sys.stderr)
        return 2
    report = run(argv[0], argv[1])
    print(json.dumps(report, ensure_ascii=False, indent=2))
    return 0 if report["qa_overall"] != "fail" else 1


if __name__ == "__main__":
    sys.exit(main())
