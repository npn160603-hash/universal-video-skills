"""Audio mix (Fairlight-inspired, Phase 4).

Categories VOICE, MUSIC, SFX, AMBIENCE each get a default gain. Voice is kept
intelligible in three ways:
- MUSIC is ducked by a sidechain compressor keyed on the VOICE signal.
- VOICE gets a high-pass filter, optional noise reduction (afftdn), and gentle compression.
- Loudness is set with two-pass loudnorm to a configurable target, then an alimiter
  caps true peaks.

Not implemented: source separation, speech enhancement models, and spectral repair.
"""
from __future__ import annotations

import json
import subprocess
import tempfile
from dataclasses import dataclass
from pathlib import Path
from typing import Sequence

CATEGORIES = {"VOICE": 0.0, "MUSIC": -14.0, "SFX": -6.0, "AMBIENCE": -22.0}
LIMITER_LINEAR = 0.891   # about -1 dBTP as a linear sample limit


@dataclass(frozen=True)
class AudioClip:
    category: str
    path: str
    start: float = 0.0            # seconds on the mix timeline
    duration: float | None = None  # seconds; None = whole file
    gain_db: float | None = None   # None = category default
    loop: bool = False             # loop the source to cover the duration (ambience)
    duck: bool = True              # MUSIC only: duck under voice when voice is present


def _check(clips: Sequence[AudioClip]) -> None:
    for c in clips:
        if c.category not in CATEGORIES:
            raise ValueError(f"unknown audio category {c.category!r}; choose from {sorted(CATEGORIES)}")
        if not Path(c.path).exists():
            raise FileNotFoundError(c.path)
        if c.start < 0 or (c.duration is not None and c.duration <= 0):
            raise ValueError(f"bad timing for {c.path}")


def build_mix_graph(clips: Sequence[AudioClip], *, denoise: bool = False, deess: bool = False,
                    duck_threshold: float = 0.02, duck_ratio: float = 6.0) -> tuple[list[str], str, str]:
    """Return (ffmpeg input args, filter_complex, output label)."""
    _check(clips)
    inputs: list[str] = []
    parts: list[str] = []
    labels: dict[str, list[str]] = {k: [] for k in CATEGORIES}

    for i, c in enumerate(clips):
        if c.loop:
            inputs += ["-stream_loop", "-1", "-i", c.path]
        else:
            inputs += ["-i", c.path]
        chain = [f"[{i}:a]aformat=sample_fmts=fltp:sample_rates=48000:channel_layouts=stereo"]
        if c.duration is not None:
            chain.append(f"atrim=duration={c.duration:.6f}")
        chain.append("asetpts=PTS-STARTPTS")
        if c.category == "VOICE":
            chain.append("highpass=f=80")
            if denoise:
                chain.append("afftdn=nf=-25")
            # presence EQ: gentle low-mud cut and a presence lift for clarity
            chain.append("equalizer=f=250:t=q:w=1.0:g=-2")
            chain.append("equalizer=f=4000:t=q:w=1.0:g=2")
            chain.append("acompressor=threshold=-20dB:ratio=3:attack=20:release=250")
            if deess:
                # de-ess: tame sibilance around 6-7 kHz with a narrow dynamic dip
                chain.append("deesser=i=0.4")
        gain = CATEGORIES[c.category] if c.gain_db is None else c.gain_db
        chain.append(f"volume={gain}dB")
        if c.start > 0:
            chain.append(f"adelay={int(round(c.start * 1000))}:all=1")
        label = f"c{i}"
        parts.append(",".join(chain) + f"[{label}]")
        labels[c.category].append(label)

    # Voice bus. A separate key copy is only made when some music clip is ducked.
    voice_bus = None
    if labels["VOICE"]:
        if len(labels["VOICE"]) > 1:
            parts.append("".join(f"[{l}]" for l in labels["VOICE"])
                         + f"amix=inputs={len(labels['VOICE'])}:duration=longest:normalize=0[vbus]")
            voice_bus = "vbus"
        else:
            voice_bus = labels["VOICE"][0]
    needs_key = voice_bus is not None and any(c.category == "MUSIC" and c.duck for c in clips)
    voice_key = None
    voice_out = voice_bus
    if needs_key:
        parts.append(f"[{voice_bus}]asplit=2[vkey][vmix]")
        voice_key, voice_out = "vkey", "vmix"

    # Music: duck under the voice key when requested.
    ducked_labels: list[str] = []
    for i, c in enumerate(clips):
        if c.category != "MUSIC":
            continue
        src = f"c{i}"
        if c.duck and voice_key:
            out = f"d{i}"
            parts.append(f"[{src}][{voice_key}]sidechaincompress=threshold={duck_threshold}:"
                         f"ratio={duck_ratio}:attack=15:release=350[{out}]")
            ducked_labels.append(out)
        else:
            ducked_labels.append(src)

    final_inputs = ([voice_out] if voice_out else []) + ducked_labels + labels["SFX"] + labels["AMBIENCE"]
    if not final_inputs:
        raise ValueError("nothing to mix")
    if len(final_inputs) == 1:
        parts.append(f"[{final_inputs[0]}]alimiter=limit={LIMITER_LINEAR}:attack=5:release=50[mix]")
    else:
        parts.append("".join(f"[{l}]" for l in final_inputs)
                     + f"amix=inputs={len(final_inputs)}:duration=longest:normalize=0[msum]")
        parts.append(f"[msum]alimiter=limit={LIMITER_LINEAR}:attack=5:release=50[mix]")
    return inputs, ";".join(parts), "mix"


def _run(args: list[str]) -> subprocess.CompletedProcess:
    return subprocess.run(["ffmpeg", "-hide_banner", "-loglevel", "error", "-y", *args],
                          capture_output=True, text=True)


def _loudnorm_measure(path: Path, target: float, true_peak: float, lra: float) -> dict:
    proc = subprocess.run(
        ["ffmpeg", "-hide_banner", "-nostats", "-i", str(path),
         "-af", f"loudnorm=I={target}:TP={true_peak}:LRA={lra}:print_format=json",
         "-f", "null", "-"], capture_output=True, text=True)
    if proc.returncode != 0:
        raise RuntimeError(f"loudnorm measurement failed: {proc.stderr.strip()[-400:]}")
    text = proc.stderr
    data = json.loads(text[text.rfind("{"): text.rfind("}") + 1])
    return data


def mix_to_file(clips: Sequence[AudioClip], out: str | Path, *, target_lufs: float = -14.0,
                true_peak: float = -1.5, lra: float = 11.0, denoise: bool = False,
                duration: float | None = None) -> dict:
    """Mix clips, normalise loudness in two passes, and write an AAC file. Returns measurements."""
    inputs, graph, label = build_mix_graph(clips, denoise=denoise)
    out = Path(out)
    out.parent.mkdir(parents=True, exist_ok=True)
    with tempfile.TemporaryDirectory() as tmp:
        premix = Path(tmp) / "premix.wav"
        args = [*inputs, "-filter_complex", graph, "-map", f"[{label}]"]
        if duration is not None:
            args += ["-t", f"{duration:.6f}"]
        args += ["-ar", "48000", "-ac", "2", str(premix)]
        proc = _run(args)
        if proc.returncode != 0:
            raise RuntimeError(f"mix failed: {proc.stderr.strip()[-600:]}")

        m = _loudnorm_measure(premix, target_lufs, true_peak, lra)
        linear = (f"loudnorm=I={target_lufs}:TP={true_peak}:LRA={lra}:"
                  f"measured_I={m['input_i']}:measured_TP={m['input_tp']}:"
                  f"measured_LRA={m['input_lra']}:measured_thresh={m['input_thresh']}:"
                  f"offset={m['target_offset']}:linear=true")
        proc = _run(["-i", str(premix), "-af", linear, "-c:a", "aac", "-b:a", "192k", str(out)])
        if proc.returncode != 0:
            raise RuntimeError(f"loudness pass failed: {proc.stderr.strip()[-600:]}")
    return {"output": str(out), "measured_input": m}


def duck_music(music: str | Path, voice: str | Path, out: str | Path, *, threshold: float = 0.02,
               ratio: float = 6.0) -> Path:
    """Write a ducked copy of a music file keyed on a voice file. Used for direct measurement."""
    out = Path(out)
    out.parent.mkdir(parents=True, exist_ok=True)
    graph = (f"[1:a]aformat=channel_layouts=mono[vk];"
             f"[0:a]aformat=channel_layouts=mono[m];"
             f"[m][vk]sidechaincompress=threshold={threshold}:ratio={ratio}:attack=15:release=350[d]")
    proc = _run(["-i", str(music), "-i", str(voice), "-filter_complex", graph, "-map", "[d]",
                 "-ar", "48000", str(out)])
    if proc.returncode != 0:
        raise RuntimeError(f"ducking failed: {proc.stderr.strip()[-600:]}")
    return out
