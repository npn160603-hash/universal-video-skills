# Editing core (Phase 1) — public interface

Status: PARTIAL. Model and operations VERIFIED by tests. Scene-graph rendering and nested sequences are not built.

## uvs.project
- `new_project(project_id, title, width, height, fps="30") -> dict`
- `validate(doc) -> list[Issue]` — structural (jsonschema) and semantic checks; each Issue has `path`, `message`, `hint`.
- `migrate(doc) -> dict` — v0 timeline JSON → v1 project. Unmapped items go to `quality.migration_notes`.
- `load(path) -> dict`, `save(doc, path)` — deterministic JSON (sorted keys). Raise `ProjectError` with all issues.
- Schema: `schemas/uvs_project.schema.json`.

## uvs.scenegraph
- `Node(id, kind, transform, crop, width, height, payload, children)`, `SceneGraph(root)`.
- `Transform(x, y, rotation, scale_x, scale_y, anchor_x, anchor_y, opacity)`; rotation in degrees, clockwise on screen.
- `to_world`, `to_local`, `world_matrix`, `world_opacity`, `world_rect`, `draw_order`, `reorder_child`, `validate`, `to_dict`, `from_dict`.
- Cycles and shared children raise `SceneGraphError`.

## uvs.edit_ops
- `apply_op(timeline, op, args) -> (new_timeline, record)` — never mutates the input.
- Operations: `move_clip` (non-video), `set_duration`, `set_transition`, `add_clip`, `remove_clip`.
- `undo(timeline, record)`, `replay(timeline, records)`.
- `validate_scene_boundaries(timeline, scene_starts)`.
- Invalid results raise `EditError`; the input is unchanged.
- Video clips form a chain: durations and transitions reflow the following clips. The first clip always starts at frame 0.

## uvs.assets
- `ProjectRoot(path)`: `resolve(relpath)` refuses absolute paths, `..`, NUL bytes, and symlinks that leave the root. `relpath(abs)`.
- `register(root, file) -> asset record` (SHA-256 id, portable path, kind).
- `check(root, assets)` → ok / missing / changed / unsafe.
- `usage(doc)`, `unused(doc)` — dependency tracking.
- `Cache(folder, max_bytes)`: `key`, `put`, `get`, `has`, `prune` (least recently used first). Only removes files it wrote.

## uvs.backend
- `RenderBackend` (abstract): `capabilities()`, `render_timeline(tl, out, crf)`, `burn_captions(src, ass, out)`.
- `FFmpegBackend` wraps the existing renderer (`uvs.timeline.render`, `uvs.render.burn_captions`). `default_backend()`.
- The pipeline uses `default_backend()`.

## Not in this phase
- Scene-graph nodes are not rendered by any backend.
- Nested sequences: not implemented.
- Keyframes from `uvs.motion` are not attached to timeline clips.
- Only one backend exists (ffmpeg).
