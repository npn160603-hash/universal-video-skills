# professional-timeline-editing

Status: **partial**. Video chaining with cut, dissolve, and dip-to-black; audio and overlay placement; validation.
Multitrack compositing beyond overlays, nested sequences, and speed ramps are not implemented.

## Purpose
A frame-accurate timeline model with validation, and an ffmpeg render that joins video clips with transitions,
places audio clips, and composites overlay clips.

## Inputs and outputs
- In: a `Timeline` (fps as an exact fraction, width, height, tracks), or the JSON form saved by `save_timeline`.
  Schema: `schemas/timeline.schema.json`.
- Out: an MP4 (H.264, AAC if audio clips exist), or a list of validation issues.

## Execution
```python
from uvs import timeline as T
issues = T.validate(tl)          # errors block rendering
T.render(tl, "out/timeline.mp4")
```

## Track kinds
- `video`: sequential clips. `next.start = prev.start + prev.duration - next.transition_frames`.
- `audio`: clips placed by start frame, with gain in dB, then mixed.
- `overlay`: images or videos, placed by start frame at (x, y), with alpha.
- `subtitle`, `keyframe`: validated, not rendered (`not_rendered` warning). Captions burn in through the caption pipeline.

## Transitions
`cut` (concat), `dissolve` (xfade `fade`), `dip_black` (xfade `fadeblack`). Transition length in frames.

## Validation codes
Errors: `gap`, `conflicting_timing`, `non_positive_duration`, `negative_time`, `missing_asset`, `overlap`
(audio and overlay), `missing_transition_type`, `missing_transition_length`, `transition_too_long`,
`unknown_transition`, `unknown_track_kind`, `bad_frame_size`, `bad_fps`.
Warnings: `transition_on_first_clip`, `not_rendered`.

## Constraints
- Video tracks must be contiguous. Gaps are errors, not filled with black.
- Only one video track is rendered. A second video track is not composited.
- `fadeblack` reaches black inside its transition window, but the darkest frame is not always at the midpoint.
  The render test checks that black appears inside the window.
- Keyframes on overlays are not rendered yet.

## Tests
`tests/unit/test_timeline.py` (validation, JSON round-trip, NTSC timing).
`tests/render/test_timeline_render.py` (real renders; checks dissolve midpoint mixes two colours,
dip window reaches black, and audio starts at its frame).

## Integration
The pipeline builds one video track from the director plan (`build_timeline` in `uvs/pipeline.py`),
aligning each clip's start with its scene start, and extends each clip by the transition into the next.
