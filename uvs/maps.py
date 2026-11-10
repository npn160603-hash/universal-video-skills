"""Animated map engine (Phase 5): country shapes, projections, great-circle routes, camera moves.

Data: Natural Earth 110 m countries (public domain) read with pyshp from a path given by the caller
or from the UVS_NATURAL_EARTH_SHP environment variable. The data is not bundled in this repository.
Rings are unwrapped across the antimeridian, so Russia and Fiji draw as one piece; the world view
clips the part beyond 180 degrees.

Projections: equirectangular and Mercator (latitude clamped to +/-85.0511). The view is fitted to
the canvas with uniform scale (contain), so shapes keep their proportions.

Routes: great-circle arcs between waypoints, revealed along arc length with an easing curve.
Markers: a dot that expands and settles after its start time.
Camera: the view box moves between two regions with keyframe tracks from uvs.motion.

Not done: text labels, country-border styling beyond outlines, data-driven choropleths, and
polygon simplification for large views (the 110 m file is small enough for full detail).
"""
from __future__ import annotations

import math
import os
from dataclasses import dataclass, field
from pathlib import Path

from PIL import Image, ImageDraw

from uvs.motion import Keyframe, Track, get_easing

ENV_VAR = "UVS_NATURAL_EARTH_SHP"
PROJECTIONS = ("equirectangular", "mercator")
MERCATOR_LIMIT = 85.0511
COORD_EPS = 1e-6  # Natural Earth stores some values such as 180.00000000000006


class MapError(ValueError):
    pass


# ---------------------------------------------------------------------------
# Geometry
# ---------------------------------------------------------------------------

def _signed_area(ring: list[tuple[float, float]]) -> float:
    s = 0.0
    for (x0, y0), (x1, y1) in zip(ring, ring[1:] + ring[:1]):
        s += x0 * y1 - x1 * y0
    return s / 2.0


def unwrap_ring(ring: list[tuple[float, float]]) -> list[tuple[float, float]]:
    """Make longitude continuous across the antimeridian, so a ring crossing 180 does not jump."""
    if not ring:
        return ring
    out = [ring[0]]
    offset = 0.0
    prev = ring[0][0]
    for lon, lat in ring[1:]:
        delta = lon - prev
        if delta > 180:
            offset -= 360
        elif delta < -180:
            offset += 360
        out.append((lon + offset, lat))
        prev = lon
    return out


@dataclass
class Country:
    name: str
    iso3: str
    continent: str
    rings: list[tuple[list[tuple[float, float]], bool]]  # (ring of (lon, lat), is_hole)
    bbox: tuple[float, float, float, float]               # min_lon, min_lat, max_lon, max_lat


def _make_country(name, iso3, continent, raw_rings) -> Country:
    rings = []
    for raw in raw_rings:
        ring = unwrap_ring(raw)
        if len(ring) < 3:
            continue
        is_hole = _signed_area(ring) > 0  # ESRI outer rings are clockwise (negative area)
        rings.append((ring, is_hole))
    if not rings:
        raise MapError(f"country {name!r} has no usable rings")
    lons = [p[0] for ring, _ in rings for p in ring]
    lats = [p[1] for ring, _ in rings for p in ring]
    return Country(name, iso3, continent, rings, (min(lons), min(lats), max(lons), max(lats)))


def load_countries(path: str | Path | None = None) -> list[Country]:
    """Read country polygons. Falls back to the UVS_NATURAL_EARTH_SHP environment variable."""
    import shapefile  # pyshp; imported here so the rest of the module works without it

    target = path or os.environ.get(ENV_VAR)
    if not target:
        raise MapError(f"no countries file: pass a path or set {ENV_VAR}")
    target = Path(target)
    if not target.exists():
        raise MapError(f"countries file not found: {target}")
    countries: list[Country] = []
    reader = shapefile.Reader(str(target))
    for shp, rec in zip(reader.iterShapes(), reader.iterRecords()):
        pts = [(float(x), float(y)) for x, y in shp.points]
        for lon, lat in pts:
            if not (-180 - COORD_EPS <= lon <= 180 + COORD_EPS and -90 - COORD_EPS <= lat <= 90 + COORD_EPS):
                raise MapError(f"coordinate ({lon}, {lat}) outside lon/lat range")
        parts = list(shp.parts) + [len(pts)]
        raw = [pts[parts[i]:parts[i + 1]] for i in range(len(parts) - 1)]
        d = rec.as_dict()
        countries.append(_make_country(str(d.get("name", "unknown")), str(d.get("iso_a3", "")),
                                       str(d.get("continent", "")), raw))
    return countries


def great_circle(a: tuple[float, float], b: tuple[float, float], n: int = 64) -> list[tuple[float, float]]:
    """n points along the great circle from a to b, both given as (lon, lat)."""
    if n < 2:
        raise MapError("a great circle needs at least 2 points")

    def to_xyz(lon, lat):
        la, lo = math.radians(lat), math.radians(lon)
        return (math.cos(la) * math.cos(lo), math.cos(la) * math.sin(lo), math.sin(la))

    va, vb = to_xyz(*a), to_xyz(*b)
    dot = max(-1.0, min(1.0, sum(x * y for x, y in zip(va, vb))))
    omega = math.acos(dot)
    if omega > math.pi - 1e-6:
        raise MapError("antipodal points have no unique great circle")
    if omega < 1e-12:
        return [a for _ in range(n)]
    out = []
    for i in range(n):
        f = i / (n - 1)
        s1 = math.sin((1 - f) * omega) / math.sin(omega)
        s2 = math.sin(f * omega) / math.sin(omega)
        x, y, z = (s1 * p + s2 * q for p, q in zip(va, vb))
        out.append((math.degrees(math.atan2(y, x)), math.degrees(math.atan2(z, math.hypot(x, y)))))
    out[0], out[-1] = a, b
    return out


def route_through(waypoints: list[tuple[float, float]], n_per_leg: int = 64) -> list[tuple[float, float]]:
    if len(waypoints) < 2:
        raise MapError("a route needs at least 2 waypoints")
    pts: list[tuple[float, float]] = []
    for a, b in zip(waypoints, waypoints[1:]):
        leg = great_circle(a, b, n_per_leg)
        pts.extend(leg if not pts else leg[1:])
    return pts


# ---------------------------------------------------------------------------
# View and projection
# ---------------------------------------------------------------------------

@dataclass(frozen=True)
class View:
    min_lon: float
    min_lat: float
    max_lon: float
    max_lat: float

    def __post_init__(self):
        if not (-180 <= self.min_lon < self.max_lon <= 180 and -90 <= self.min_lat < self.max_lat <= 90):
            raise MapError(f"view bounds are invalid: {self}")


WORLD = View(-180.0, -85.0, 180.0, 85.0)


def _merc_y(lat: float) -> float:
    lat = max(-MERCATOR_LIMIT, min(MERCATOR_LIMIT, lat))
    return math.degrees(math.log(math.tan(math.pi / 4 + math.radians(lat) / 2)))


class Projector:
    """Maps lon/lat to canvas pixels (y down). The view is centred and scaled uniformly to fit."""

    def __init__(self, view: View, width: int, height: int, projection: str = "equirectangular"):
        if projection not in PROJECTIONS:
            raise MapError(f"projection must be one of {PROJECTIONS}")
        if width <= 0 or height <= 0:
            raise MapError("canvas size must be positive")
        self.view = view
        self.width = width
        self.height = height
        self.projection = projection
        y0, y1 = self._fy(view.min_lat), self._fy(view.max_lat)
        dx, dy = view.max_lon - view.min_lon, y1 - y0
        self.scale = min(width / dx, height / dy)
        self.cx = (view.min_lon + view.max_lon) / 2
        self.cy = (y0 + y1) / 2

    def _fy(self, lat: float) -> float:
        return _merc_y(lat) if self.projection == "mercator" else lat

    def project(self, lon: float, lat: float) -> tuple[float, float]:
        x = self.width / 2 + (lon - self.cx) * self.scale
        y = self.height / 2 - (self._fy(lat) - self.cy) * self.scale
        return (x, y)


# ---------------------------------------------------------------------------
# Animated elements
# ---------------------------------------------------------------------------

@dataclass
class Route:
    points: list[tuple[float, float]]  # lon/lat, already dense (see route_through)
    start: float
    duration: float
    color: str = "#f4d35e"
    width: int = 4
    easing: str = "ease_in_out"

    def __post_init__(self):
        if len(self.points) < 2:
            raise MapError("a route needs at least 2 points")
        if self.duration <= 0:
            raise MapError("route duration must be positive")
        get_easing(self.easing)


@dataclass
class Marker:
    lon: float
    lat: float
    start: float
    color: str = "#f4d35e"
    radius: float = 6.0
    settle_seconds: float = 0.8


@dataclass
class Camera:
    """View box that moves between keyframes. Each of the four bounds is a Track."""

    tracks: dict[str, Track]

    @classmethod
    def still(cls, view: View) -> "Camera":
        return cls.move(view, view, start=0.0, duration=1.0)

    @classmethod
    def move(cls, start_view: View, end_view: View, *, start: float, duration: float,
             easing: str = "ease_in_out") -> "Camera":
        if duration <= 0:
            raise MapError("camera move duration must be positive")
        tracks = {}
        for prop in ("min_lon", "min_lat", "max_lon", "max_lat"):
            kfs = []
            if start > 0:
                kfs.append(Keyframe(time=0.0, value=getattr(start_view, prop), easing="linear"))
            kfs.append(Keyframe(time=start, value=getattr(start_view, prop), easing=easing))
            kfs.append(Keyframe(time=start + duration, value=getattr(end_view, prop), easing="linear"))
            tracks[prop] = Track(kfs)
        return cls(tracks)

    def view_at(self, t: float) -> View:
        vals = {p: float(tr.value_at(t)) for p, tr in self.tracks.items()}
        return View(**vals)


@dataclass
class MapScene:
    countries: list[Country]
    camera: Camera
    width: int
    height: int
    projection: str = "equirectangular"
    base_fill: str = "#22364a"
    sea: str = "#0b1620"
    border: str = "#3d5a73"
    highlights: dict[str, str] = field(default_factory=dict)  # iso3 -> fill colour
    routes: list[Route] = field(default_factory=list)
    markers: list[Marker] = field(default_factory=list)

    def __post_init__(self):
        if self.width <= 0 or self.height <= 0:
            raise MapError("canvas size must be positive")
        if self.projection not in PROJECTIONS:
            raise MapError(f"projection must be one of {PROJECTIONS}")

    def frame(self, t: float) -> Image.Image:
        view = self.camera.view_at(t)
        proj = Projector(view, self.width, self.height, self.projection)
        img = Image.new("RGB", (self.width, self.height), self.sea)
        draw = ImageDraw.Draw(img)
        for c in self.countries:
            if not _overlaps(c.bbox, view):
                continue
            fill = self.highlights.get(c.iso3, self.base_fill)
            for ring, is_hole in c.rings:
                pts = [proj.project(lon, lat) for lon, lat in ring]
                draw.polygon(pts, fill=self.sea if is_hole else fill)
                if not is_hole:
                    draw.line(pts + [pts[0]], fill=self.border, width=1)
        for r in self.routes:
            if t < r.start:
                continue
            p = min(1.0, (t - r.start) / r.duration)
            segs = _segments(r.points, proj)
            partial = _truncate(segs, get_easing(r.easing)(p))
            for seg in partial:
                if len(seg) >= 2:
                    draw.line(seg, fill=r.color, width=r.width)
            if partial and partial[-1]:
                x, y = partial[-1][-1]
                rr = r.width
                draw.ellipse([x - rr, y - rr, x + rr, y + rr], fill=r.color)
        for m in self.markers:
            if t < m.start:
                continue
            x, y = proj.project(m.lon, m.lat)
            settle = min(1.0, (t - m.start) / m.settle_seconds)
            rad = m.radius * (1.0 + 0.5 * (1.0 - settle))
            draw.ellipse([x - rad, y - rad, x + rad, y + rad], fill=m.color)
        return img


def _overlaps(bbox, view: View) -> bool:
    return not (bbox[2] < view.min_lon or bbox[0] > view.max_lon
                or bbox[3] < view.min_lat or bbox[1] > view.max_lat)


def _segments(points: list[tuple[float, float]], proj: Projector) -> list[list[tuple[float, float]]]:
    """Project a route, starting a new segment wherever it jumps across the antimeridian."""
    segs: list[list[tuple[float, float]]] = [[]]
    prev = None
    for lon, lat in points:
        if prev is not None and abs(lon - prev) > 180:
            segs.append([])
        segs[-1].append(proj.project(lon, lat))
        prev = lon
    return segs


def _truncate(segs: list[list[tuple[float, float]]], fraction: float) -> list[list[tuple[float, float]]]:
    """Keep the first `fraction` of the total arc length of the projected route."""
    total = sum(math.dist(a, b) for seg in segs for a, b in zip(seg, seg[1:]))
    budget = max(0.0, min(1.0, fraction)) * total
    out: list[list[tuple[float, float]]] = []
    for seg in segs:
        if budget <= 0 or len(seg) < 2:
            break
        kept = [seg[0]]
        for a, b in zip(seg, seg[1:]):
            d = math.dist(a, b)
            if d <= budget:
                kept.append(b)
                budget -= d
            else:
                f = budget / d if d else 0.0
                kept.append((a[0] + (b[0] - a[0]) * f, a[1] + (b[1] - a[1]) * f))
                budget = 0.0
                break
        out.append(kept)
        if budget <= 0:
            break
    return out


def route_length_px(route: Route, proj: Projector) -> float:
    return sum(math.dist(a, b) for seg in _segments(route.points, proj) for a, b in zip(seg, seg[1:]))


def render_map_video(scene: MapScene, out: str | Path, *, fps: float, duration: float,
                     crf: int = 18) -> dict:
    from uvs.animate import encode_frames, frame_times

    times = frame_times(fps, duration)
    n = encode_frames(out, fps=fps, width=scene.width, height=scene.height,
                      frames=(scene.frame(t) for t in times), crf=crf)
    return {"path": str(out), "frames": n, "fps": fps, "width": scene.width, "height": scene.height}

