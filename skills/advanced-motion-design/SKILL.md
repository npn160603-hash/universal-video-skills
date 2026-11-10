# advanced-motion-design

Status: **partial**. Easing curves and keyframe tracks are implemented and tested. Animated layers on video are
limited to caption fades and keyword pops (ASS tags). Parenting, masks, camera moves, and text
path effects are not implemented.

## Purpose
Motion values that look intentional: easing functions with exact endpoints, and keyframe tracks for scalars
or tuples (position, colour), sampled frame-accurately.

## Easings (`uvs/motion.py`)
`linear`, `ease_in`, `ease_out`, `ease_in_out` (cubic bezier), `cubic_bezier(x1, y1, x2, y2)`,
`spring(zeta, omega)` (damped spring, normalized), `elastic_out`, `bounce_out`, `overshoot`,
`damped_oscillation`. Every easing gives f(0) = 0 and f(1) = 1.

## Execution
```python
from uvs import motion as M
track = M.Track([M.Keyframe(0.0, (0, 300), easing="ease_out"), M.Keyframe(0.8, (0, 0))])
values = track.sample(fps=30, duration=1.0)   # one value per frame
```
Schema: `schemas/animation.schema.json`.

## Constraints
- Keyframes must have distinct times and the same dimensions.
- Curves are evaluated per segment, using the easing on the leading keyframe.
- Overshoot, spring, and elastic curves exceed [0, 1] on purpose. Check the target range before using them.
- Nothing here draws on video frames yet. Use the output values as inputs to a renderer.

## Tests
`tests/unit/test_motion.py` (18 tests): endpoints, clamping, bezier vs linear, symmetry, overshoot, spring,
bounce range, keyframe interpolation, tuple tracks, frame sampling, rejection of bad tracks.
