# Animated map engine (Phase 5) — public interface

Status: PARTIAL. Country shapes, projections, great-circle routes, markers and camera moves render to frames and MP4.

## Data
- `load_countries(path=None) -> list[Country]`: reads a Natural Earth countries `.shp` (pyshp). With no path, uses the `UVS_NATURAL_EARTH_SHP` environment variable. Raises `MapError` if neither is set or the file is missing.
- Data is **not bundled**. The 110 m file is public domain and is available in the `geopandas` 0.14.4 wheel under `geopandas/datasets/naturalearth_lowres/`.
- `Country(name, iso3, continent, rings, bbox)`: rings are `(list[(lon, lat)], is_hole)`. Holes come from the ESRI winding rule (outer rings clockwise). Only South Africa has a hole in this file (Lesotho).
- Antimeridian: `unwrap_ring` makes each ring's longitude continuous. The world view clips anything beyond ±180°.

## Projection and view
- `View(min_lon, min_lat, max_lon, max_lat)`, validated. `WORLD` = the full map.
- `Projector(view, width, height, projection)`: `projection` is `equirectangular` or `mercator` (latitude clamped to ±85.0511). The view is scaled uniformly to fit the canvas (contain) and centred.

## Routes, markers, camera
- `great_circle(a, b, n)`, `route_through(waypoints, n_per_leg)`: great-circle arcs, not straight lines in lon/lat.
- `Route(points, start, duration, color, width, easing)`: revealed along projected arc length using an easing from `uvs.motion`. Drawn in segments, so routes that cross the antimeridian are split, not drawn across the map.
- `Marker(lon, lat, start, color, radius, settle_seconds)`: appears at `start`, expands and settles.
- `Camera.still(view)`, `Camera.move(start_view, end_view, start, duration, easing)`: bounds are keyframe tracks from `uvs.motion`.

## Scene and output
- `MapScene(countries, camera, width, height, projection, base_fill, sea, border, highlights, routes, markers).frame(t) -> PIL.Image (RGB)`
  - Countries outside the view are skipped. Highlighted countries use `highlights[iso3]`. Holes are drawn in the sea colour.
- `render_map_video(scene, out, fps, duration, crf=18) -> dict`: pipes frames through `uvs.animate.encode_frames` (H.264, yuv420p).
- Demo: `UVS_NATURAL_EARTH_SHP=... python3 examples/map_demo/demo.py out/map_demo.mp4`

## Limits
- No text labels. Country names are in the data but are not drawn.
- No choropleths (data-driven colour), no polygon simplification, no globe (orthographic) projection.
- Only Natural Earth 110 m is tested. Larger files will be slower; no tiling.
- Visual quality was checked by inspecting frames at three times. No automated reference images.
