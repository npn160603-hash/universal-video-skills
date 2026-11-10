# data-visual-storytelling

Status: **partial**. A bar chart with eased animation. Line charts, pies, counters, timelines, maps, and comparison
layouts are not implemented.

## Rules
- Every bar comes from the supplied values. Nothing is generated or estimated.
- Values must be finite and non-negative. Missing or NaN values raise an error. They are not skipped.
- Labels must be unique. The chart cannot be built without a `source` string, which is printed on the frame.

## Execution
```python
from uvs import charts as C
C.chart_png([C.Bar("2024", 120), C.Bar("2025", 180)], "Company report p.4", "out/chart.png",
            title="Revenue", unit="M")
C.chart_video([C.Bar("2024", 120), C.Bar("2025", 180)], "Company report p.4", "out/chart.mp4", seconds=4)
```
`chart_video` renders each frame with `motion.ease_out`. The final frame equals the data.

## Output
A 1080x1350 PNG, or an H.264 MP4 at 30 fps. Layout is returned by `compute_layout`, so tests can measure bars.

## Tests
`tests/render/test_charts_media.py`: bar heights measured from pixels match the 1 : 2 : 4 ratio of the data; the animated
video ends on the data; validation rejects missing, NaN, negative, duplicate, or unsourced input.

## Constraints
- Fonts come from fontconfig. If Inter is missing, Pillow's default font is used.
- Only vertical bars. No axis ticks, legends, or log scales.
