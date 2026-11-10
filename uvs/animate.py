"""Animated scene graphs: keyframe tracks on node transforms, rendered to frames and video (Phase 4).

An Animation maps node ids to keyframe tracks (uvs.motion.Track) for x, y, rotation, scale_x,
scale_y and opacity. pose() copies a SceneGraph and sets those transform fields at time t.
FrameRenderer draws the posed graph with PIL: each drawable node becomes a full-frame RGBA layer,
is moved by the inverse of its world matrix, has its alpha multiplied by its world opacity, and
is composited in draw order.

Renderable kinds: shape (rect or ellipse with a solid fill), image (a file inside a ProjectRoot,
scaled to the node's size), group (no pixels of its own). Any other kind raises AnimationError,
because it would otherwise be silently skipped. Text, video, masks and camera are not rendered yet.

Limits: keyframes attach to scene-graph nodes, not to timeline clips. Layers are full-frame, so
cost grows with frame size and node count. There is no motion blur, and no sub-pixel anti-aliasing
beyond PIL's bilinear sampling.
"""
from __future__ import annotations

import subprocess
from dataclasses import dataclass, field
from pathlib import Path
from typing import Iterable

from PIL import Image, ImageDraw

from uvs import scenegraph as G
from uvs.assets import ProjectRoot
from uvs.motion import Keyframe, Track

ANIMATABLE = ("x", "y", "rotation", "scale_x", "scale_y", "opacity")
RENDERABLE = {"shape", "image", "group"}


class AnimationError(ValueError):
    pass


def _value(raw):
    if isinstance(raw, bool):
        raise AnimationError("keyframe values must be numbers or lists of numbers")
    if isinstance(raw, (int, float)):
        return float(raw)
    if isinstance(raw, (list, tuple)) and raw and all(isinstance(v, (int, float)) and not isinstance(v, bool) for v in raw):
        return tuple(float(v) for v in raw)
    raise AnimationError(f"keyframe value {raw!r} must be a number or a list of numbers")


@dataclass
class Animation:
    tracks: dict[str, dict[str, Track]] = field(default_factory=dict)

    @classmethod
    def from_spec(cls, spec: dict) -> "Animation":
        """Build from {node_id: {prop: [{"time": s, "value": v, "easing": name}, ...]}}."""
        if not isinstance(spec, dict):
            raise AnimationError("animation spec must be an object keyed by node id")
        tracks: dict[str, dict[str, Track]] = {}
        for node_id, props in spec.items():
            if not isinstance(props, dict):
                raise AnimationError(f"node {node_id!r}: properties must be an object")
            tracks[str(node_id)] = {}
            for prop, kfs in props.items():
                if not isinstance(kfs, list) or not kfs:
                    raise AnimationError(f"{node_id!r}.{prop}: needs a non-empty list of keyframes")
                keyframes = []
                for k in kfs:
                    if not isinstance(k, dict) or "time" not in k or "value" not in k:
                        raise AnimationError(f"{node_id!r}.{prop}: each keyframe needs 'time' and 'value'")
                    keyframes.append(Keyframe(time=float(k["time"]), value=_value(k["value"]),
                                              easing=str(k.get("easing", "linear"))))
                try:
                    tracks[str(node_id)][str(prop)] = Track(keyframes)
                except (ValueError, KeyError) as exc:
                    raise AnimationError(f"{node_id!r}.{prop}: {exc}") from exc
        return cls(tracks)


def check(graph: G.SceneGraph, anim: Animation) -> list[str]:
    """Problems that stop the animation from being applied. Empty means it can be used."""
    problems: list[str] = []
    try:
        idx = G.index(graph)
    except G.SceneGraphError as exc:
        return [str(exc)]
    for node_id, props in anim.tracks.items():
        if node_id not in idx:
            problems.append(f"animation targets unknown node {node_id!r}")
            continue
        for prop, track in props.items():
            if prop not in ANIMATABLE:
                problems.append(f"node {node_id!r}: property {prop!r} cannot be animated; "
                                f"allowed: {', '.join(ANIMATABLE)}")
            elif any(isinstance(k.value, tuple) for k in track.keyframes):
                problems.append(f"node {node_id!r}: {prop} takes a single number, not a list")
    return problems


def pose(graph: G.SceneGraph, anim: Animation, t: float) -> G.SceneGraph:
    """Return a copy of the graph with the animated transform values at time t."""
    problems = check(graph, anim)
    if problems:
        raise AnimationError("; ".join(problems))
    posed = G.from_dict(G.to_dict(graph))
    idx = G.index(posed)
    for node_id, props in anim.tracks.items():
        node = idx[node_id][0]
        for prop, track in props.items():
            setattr(node.transform, prop, float(track.value_at(t)))
    problems = G.validate(posed)
    if problems:
        raise AnimationError(f"posed graph at t={t} is invalid: " + "; ".join(problems))
    return posed


def frame_times(fps: float, duration: float) -> list[float]:
    """Times of frames 0..round(duration * fps) - 1, matching Track.sample."""
    if fps <= 0 or duration <= 0:
        raise AnimationError("fps and duration must be positive")
    n = max(1, int(round(duration * fps)))
    return [i / fps for i in range(n)]


def _parse_fill(text: str) -> tuple[int, int, int, int]:
    s = str(text).strip()
    if len(s) != 7 or not s.startswith("#"):
        raise AnimationError(f"fill {text!r} must be '#rrggbb'")
    try:
        r, g, b = int(s[1:3], 16), int(s[3:5], 16), int(s[5:7], 16)
    except ValueError as exc:
        raise AnimationError(f"fill {text!r} must be hex") from exc
    return (r, g, b, 255)


def _scale_alpha(img: Image.Image, k: float) -> Image.Image:
    out = img.copy()
    out.putalpha(img.getchannel("A").point(lambda v: round(v * k)))
    return out


class FrameRenderer:
    """Renders frames of one animated graph. Layers and images are prepared once."""

    def __init__(self, graph: G.SceneGraph, anim: Animation, *, width: int, height: int,
                 root: ProjectRoot | None = None, background: tuple[int, int, int] = (0, 0, 0)):
        if width <= 0 or height <= 0:
            raise AnimationError("width and height must be positive")
        problems = check(graph, anim) + G.validate(graph)
        if problems:
            raise AnimationError("; ".join(problems))
        self.graph = graph
        self.anim = anim
        self.size = (int(width), int(height))
        self.root = root
        self.background = tuple(int(c) for c in background)
        self._layers: dict[str, Image.Image | None] = {}
        for node, _, _ in G.walk(graph):
            if node.kind not in RENDERABLE:
                raise AnimationError(f"node {node.id!r} has kind {node.kind!r}, which the motion engine "
                                     f"does not render yet (supported: {', '.join(sorted(RENDERABLE))})")
            self._layers[node.id] = None if node.kind == "group" else self._build_layer(node)

    def _build_layer(self, node: G.Node) -> Image.Image:
        w = max(1, int(round(node.width)))
        h = max(1, int(round(node.height)))
        if node.kind == "shape":
            fill = _parse_fill(node.payload.get("fill", "#ffffff"))
            layer = Image.new("RGBA", (w, h), (0, 0, 0, 0))
            draw = ImageDraw.Draw(layer)
            shape = node.payload.get("shape", "rect")
            if shape == "rect":
                draw.rectangle([0, 0, w - 1, h - 1], fill=fill)
            elif shape == "ellipse":
                draw.ellipse([0, 0, w - 1, h - 1], fill=fill)
            else:
                raise AnimationError(f"node {node.id!r}: shape {shape!r} is not rect or ellipse")
        else:  # image
            if self.root is None:
                raise AnimationError(f"image node {node.id!r} needs a ProjectRoot to read its file")
            src = node.payload.get("src")
            if not src:
                raise AnimationError(f"image node {node.id!r} has no 'src'")
            path = self.root.resolve(str(src))
            with Image.open(path) as im:
                layer = im.convert("RGBA").resize((w, h), Image.Resampling.LANCZOS)
        layer = self._apply_crop(node, layer)
        return layer

    @staticmethod
    def _apply_crop(node: G.Node, layer: Image.Image) -> Image.Image:
        c = node.crop
        if c is None:
            return layer
        w, h = layer.size
        mask = Image.new("L", (w, h), 0)
        ImageDraw.Draw(mask).rectangle(
            [int(round(c.left)), int(round(c.top)),
             w - 1 - int(round(c.right)), h - 1 - int(round(c.bottom))], fill=255)
        out = layer.copy()
        out.putalpha(_mul_alpha(layer.getchannel("A"), mask))
        return out

    def frame(self, t: float) -> Image.Image:
        posed = pose(self.graph, self.anim, t)
        canvas = Image.new("RGBA", self.size, (0, 0, 0, 0))
        for node, _, _ in G.walk(posed):
            layer = self._layers.get(node.id)
            if layer is None:
                continue
            opacity = G.world_opacity(posed, node.id)
            if opacity <= 0:
                continue
            inv = G.invert(G.world_matrix(posed, node.id))
            coeffs = (inv[0][0], inv[0][1], inv[0][2], inv[1][0], inv[1][1], inv[1][2])
            placed = layer.transform(self.size, Image.Transform.AFFINE, coeffs,
                                     Image.Resampling.BILINEAR)
            if opacity < 1:
                placed = _scale_alpha(placed, opacity)
            canvas = Image.alpha_composite(canvas, placed)
        base = Image.new("RGBA", self.size, self.background + (255,))
        return Image.alpha_composite(base, canvas).convert("RGB")


def _mul_alpha(a: Image.Image, b: Image.Image) -> Image.Image:
    return Image.composite(a, Image.new("L", a.size, 0), b)


def render_frame(graph: G.SceneGraph, anim: Animation, t: float, *, width: int, height: int,
                 root: ProjectRoot | None = None, background: tuple[int, int, int] = (0, 0, 0)) -> Image.Image:
    return FrameRenderer(graph, anim, width=width, height=height, root=root,
                         background=background).frame(t)


def encode_frames(out: str | Path, *, fps: float, width: int, height: int, frames: Iterable[Image.Image],
                  crf: int = 18) -> int:
    """Pipe RGB frames to ffmpeg and encode H.264 yuv420p MP4. Returns the number of frames written."""
    if width % 2 or height % 2:
        raise AnimationError("width and height must be even for yuv420p output")
    out_path = Path(out)
    out_path.parent.mkdir(parents=True, exist_ok=True)
    cmd = ["ffmpeg", "-hide_banner", "-loglevel", "error", "-y",
           "-f", "rawvideo", "-pix_fmt", "rgb24", "-s", f"{width}x{height}", "-r", str(fps), "-i", "pipe:0",
           "-c:v", "libx264", "-pix_fmt", "yuv420p", "-crf", str(crf), "-movflags", "+faststart", str(out_path)]
    proc = subprocess.Popen(cmd, stdin=subprocess.PIPE, stderr=subprocess.PIPE)
    written = 0
    try:
        for frame in frames:
            if frame.size != (width, height):
                raise AnimationError(f"frame is {frame.size}, expected {(width, height)}")
            proc.stdin.write(frame.convert("RGB").tobytes())
            written += 1
    except BrokenPipeError:
        pass  # ffmpeg exited early; its error is reported below
    except BaseException:
        proc.kill()
        proc.wait()
        proc.stderr.close()
        try:
            proc.stdin.close()
        except OSError:
            pass
        raise
    try:
        proc.stdin.close()
    except OSError:
        pass
    stderr = proc.stderr.read().decode("utf-8", "replace")
    proc.stderr.close()
    code = proc.wait()
    if code != 0:
        raise AnimationError(f"ffmpeg failed ({code}): {stderr.strip()[-300:]}")
    return written


def render_video(graph: G.SceneGraph, anim: Animation, out: str | Path, *, fps: float, duration: float,
                 width: int, height: int, root: ProjectRoot | None = None,
                 background: tuple[int, int, int] = (0, 0, 0), crf: int = 18) -> dict:
    """Render frames and encode them to H.264 MP4. Width and height must be even (yuv420p)."""
    renderer = FrameRenderer(graph, anim, width=width, height=height, root=root, background=background)
    n = encode_frames(out, fps=fps, width=width, height=height,
                      frames=(renderer.frame(t) for t in frame_times(fps, duration)), crf=crf)
    return {"path": str(out), "frames": n, "fps": fps, "width": width, "height": height}


def main(argv: list[str] | None = None) -> int:
    """CLI: python3 -m uvs.animate <scene.json> <animation.json> --out out.mp4 [--root DIR] ..."""
    import argparse
    import json
    import sys

    ap = argparse.ArgumentParser(description="Render an animated scene graph to MP4.")
    ap.add_argument("scene")
    ap.add_argument("animation")
    ap.add_argument("--out", required=True)
    ap.add_argument("--fps", type=float, default=30.0)
    ap.add_argument("--duration", type=float, required=True)
    ap.add_argument("--width", type=int, default=1280)
    ap.add_argument("--height", type=int, default=720)
    ap.add_argument("--root", help="project folder for image nodes")
    args = ap.parse_args(argv)
    try:
        graph = G.from_dict(json.loads(Path(args.scene).read_text(encoding="utf-8")))
        anim = Animation.from_spec(json.loads(Path(args.animation).read_text(encoding="utf-8")))
        root = ProjectRoot(args.root) if args.root else None
        info = render_video(graph, anim, args.out, fps=args.fps, duration=args.duration,
                            width=args.width, height=args.height, root=root)
    except (AnimationError, G.SceneGraphError, OSError, ValueError) as exc:
        sys.stderr.write(f"error: {exc}\n")
        return 2
    sys.stdout.write(json.dumps(info) + "\n")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
