# Motion engine (Phase 4) — public interface

Status: PARTIAL. Keyframes drive scene-graph node transforms; shapes and images are rendered to frames and MP4.

## Animation spec
`Animation.from_spec({node_id: {prop: [{"time": s, "value": v, "easing": name}, ...]}})`
- Animatable props: `x`, `y`, `rotation` (degrees, clockwise), `scale_x`, `scale_y`, `opacity` (0–1, checked at pose time).
- Easings: any name in `uvs.motion.EASINGS` (linear, ease_in, ease_out, ease_in_out, bounce_out, elastic_out, overshoot, spring, damped_oscillation). Values hold before the first and after the last keyframe.
- `check(graph, anim) -> list[str]`: unknown nodes, non-animatable props, list values on scalar props.

## Posing and rendering
- `pose(graph, anim, t) -> SceneGraph`: a copy with transforms set at time t. The input graph is not changed. The posed graph is validated (`uvs.scenegraph.validate`).
- `FrameRenderer(graph, anim, *, width, height, root=None, background=(0,0,0)).frame(t) -> PIL.Image (RGB)`
  - Each drawable node is a full-frame RGBA layer, moved by the inverse of its world matrix, alpha-scaled by its world opacity, and composited in draw order.
  - `shape` nodes: payload `{"fill": "#rrggbb", "shape": "rect" | "ellipse"}`. Crop is applied.
  - `image` nodes: payload `{"src": "relative/path.png"}`, read through a `ProjectRoot` (path escape is refused). A root is required.
  - `group` nodes: no pixels, but they carry transforms and opacity to children.
  - Any other kind (`text`, `video`, `mask`, `camera`, `chart`, `map`, `particle`, `overlay`) raises `AnimationError` at construction. It is not skipped silently.
- `render_frame(graph, anim, t, *, width, height, root=None, background=...)`: one frame.
- `frame_times(fps, duration)`: same frame count and times as `Track.sample`.
- `render_video(graph, anim, out, *, fps, duration, width, height, root=None, background=..., crf=18) -> dict`
  - Pipes RGB frames to ffmpeg, encodes H.264 yuv420p with faststart. Width and height must be even. On ffmpeg failure, raises `AnimationError` and leaves no ffmpeg process running.
- CLI: `python3 -m uvs.animate <scene.json> <animation.json> --out out.mp4 --duration S [--fps 30] [--width 1280] [--height 720] [--root DIR]`
  - Scene files use the `uvs-scenegraph` format (`uvs.scenegraph.to_dict`).

## Limits
- Keyframes attach to scene-graph nodes, not to timeline clips.
- Only shape, image and group nodes render. Text, video, mask, camera, chart, map, particle and overlay do not.
- Full-frame layers: cost grows with frame size times node count. Not tuned for 4K.
- No motion blur. Sampling is PIL bilinear, so edges are soft at fractional positions.
- Rendered pixel values are checked in tests, not compared against a reference image set.
