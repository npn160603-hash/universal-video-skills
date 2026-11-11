# Infographics and explainers (Phase 6) — public interface

Status: PARTIAL. Charts, timelines, diagrams, metaphors; animation controls; timeline integration.

## Charts (`uvs.infographics`)
- `ChartSpec(kind, categories, series, title, unit, source, legend, theme, duration, easing, width, height, stagger, illustrative)`; `Series(label, values, color)`.
- Kinds: vertical_bar, horizontal_bar, line, area, donut, pie, ranking, comparison, progress, counter.
- `validate(spec)` rejects missing/non-finite/boolean values, negatives where the kind can't show them, mismatched series lengths, bad pie totals, unknown kind/theme/easing.
- `render_chart_frame(spec, progress) -> PIL.Image` (progress 0..1; final frame equals data). `chart_png(spec, out)`, `chart_video(spec, out, fps, hold_seconds)`.
- Themes: `dark`, `light`.

## Timelines (`uvs.explainers`)
- `Timeline(kind, events, title, source, theme, duration, easing, width, height, date_as_year)`; `Event(position, label, detail)`.
- Kinds: historical, personal_journey, event_chronology, milestone, before_after, process.
- `render_timeline_frame(tl, p)`; `playhead_index(tl, p)`. Moving playhead, highlighted current event, counting dates.

## Diagrams (`uvs.explainers`)
- `Diagram(kind, nodes, edges, title, theme, duration, easing, width, height, node_w, node_h)`; `DiagNode(id, label, level)`, `DiagEdge(src, dst, label)`.
- Kinds: flowchart, decision_tree, cause_effect, relationship, process, hierarchy, comparison.
- `validate_diagram(dg) -> list[str]`, `layout_diagram(dg) -> {id: box}`, `overlaps(boxes) -> [(id, id)]`. `render_diagram_frame` raises on overlap; labels shrink or wrap to fit their box; nodes reveal in order.

## Visual metaphors (`uvs.explainers`)
- `Metaphor(kind, title, theme, duration, easing, width, height, intensity)`.
- Kinds: stress_accumulation, emotional_isolation, increasing_pressure, personal_boundaries, time_passing, growing_distance, competing_choices, progress_toward_goal.
- Every frame carries an "ILLUSTRATIVE — not data" tag. `render_metaphor_frame(m, p)`.

## Animation controls and integration (`uvs.visuals`)
- `Controls(zoom_from, zoom_to, pan_from, pan_to, exit_fade, background)`; `apply_controls(frame, controls, clip_t)`.
- `render_visual(frame_fn, out, duration, fps, width, height, controls, hold)` encodes any frame function with camera controls.
- `to_timeline_clip(id, source, frames, fps, start, transition, transition_frames) -> uvs.timeline.Clip`.
- Control coverage: build/reveal/data-interpolation/stagger/highlight live in the renderers; pan/zoom/exit in Controls; layer compositing in the motion engine.

## Limits
- Chart set is the 10 required kinds (no scatter, stacked, radar).
- Diagram node boxes never overlap, but dense graphs may still cross connectors.
- Metaphors are a fixed set of 8 hand-built illustrations.
- Camera pan/zoom is a frame crop, not a scene-graph camera.
