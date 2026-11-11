"""Animated infographics: charts, counters, progress indicators (Phase 6.1).

Ten chart kinds share one theme, one data-validation layer, one easing-driven animation, and one
frame renderer. Every chart carries a title, labels, units, source metadata, an optional legend,
font and colour theme, animation duration and easing. The last animation frame equals the data
exactly (frame-accurate), and rendering the same (data, progress) twice is byte-identical.

All values come from the caller. Nothing is generated, estimated or filled in. A value that is
missing, infinite or (where the chart needs it) negative makes validation fail; it is not skipped.

Chart kinds: vertical_bar, horizontal_bar, line, area, donut, pie, ranking, comparison,
progress, counter. Rendering uses PIL; encoding reuses uvs.animate.encode_frames.
"""
from __future__ import annotations

import math
from dataclasses import dataclass, field
from pathlib import Path
from typing import Callable, Sequence

from PIL import Image, ImageDraw, ImageFont

from uvs.captions import resolve_font_file
from uvs.motion import get_easing

SAFE_MARGIN = 0.06  # fraction of the shorter side kept clear of content


class InfographicError(ValueError):
    pass


# ---------------------------------------------------------------------------
# Theme and fonts
# ---------------------------------------------------------------------------

@dataclass(frozen=True)
class Theme:
    background: tuple[int, int, int] = (17, 20, 26)
    text: tuple[int, int, int] = (240, 236, 228)
    muted: tuple[int, int, int] = (150, 150, 150)
    grid: tuple[int, int, int] = (44, 50, 60)
    series: tuple[tuple[int, int, int], ...] = (
        (200, 161, 101), (94, 160, 214), (214, 94, 104), (120, 196, 140),
        (168, 132, 206), (224, 170, 90), (90, 200, 198), (210, 120, 160))
    font_family: str = "Inter"

    def color(self, i: int) -> tuple[int, int, int]:
        return self.series[i % len(self.series)]


DARK = Theme()
LIGHT = Theme(background=(246, 244, 240), text=(28, 30, 34), muted=(110, 110, 110),
              grid=(214, 212, 206))
THEMES = {"dark": DARK, "light": LIGHT}

_FONT_CACHE: dict[tuple[str, bool, int], ImageFont.FreeTypeFont | ImageFont.ImageFont] = {}


def font(theme: Theme, size: int, bold: bool = False):
    key = (theme.font_family, bold, size)
    if key not in _FONT_CACHE:
        path = resolve_font_file(theme.font_family, bold)
        _FONT_CACHE[key] = ImageFont.truetype(path, size) if path else ImageFont.load_default(size=size)
    return _FONT_CACHE[key]


def text_size(draw: ImageDraw.ImageDraw, s: str, f) -> tuple[int, int]:
    l, t, r, b = draw.textbbox((0, 0), s, font=f)
    return (r - l, b - t)


# ---------------------------------------------------------------------------
# Data and spec
# ---------------------------------------------------------------------------

@dataclass(frozen=True)
class Series:
    label: str
    values: tuple[float, ...]
    color: tuple[int, int, int] | None = None


@dataclass
class ChartSpec:
    kind: str
    categories: tuple[str, ...]            # x labels (one per value); empty for counter
    series: tuple[Series, ...]
    title: str = ""
    unit: str = ""
    source: str = ""
    legend: bool = False
    y_label: str = ""
    illustrative: bool = False             # draws an "Illustrative" tag
    theme: str = "dark"
    duration: float = 3.0
    easing: str = "ease_out"
    width: int = 1080
    height: int = 1350
    stagger: float = 0.0                   # 0..1 fraction of duration spread across series/bars

    def resolved_theme(self) -> Theme:
        if self.theme not in THEMES:
            raise InfographicError(f"unknown theme {self.theme!r}; options: {sorted(THEMES)}")
        return THEMES[self.theme]


KINDS = ("vertical_bar", "horizontal_bar", "line", "area", "donut", "pie", "ranking",
         "comparison", "progress", "counter")
_NEEDS_NONNEG = {"vertical_bar", "horizontal_bar", "donut", "pie", "ranking", "comparison",
                 "progress", "area"}


def validate(spec: ChartSpec) -> None:
    if spec.kind not in KINDS:
        raise InfographicError(f"unknown chart kind {spec.kind!r}; options: {KINDS}")
    if not spec.source or not spec.source.strip():
        raise InfographicError("a source is required for every chart")
    if not spec.series:
        raise InfographicError("no series supplied")
    if spec.duration <= 0:
        raise InfographicError("duration must be positive")
    if spec.theme not in THEMES:
        raise InfographicError(f"unknown theme {spec.theme!r}; options: {sorted(THEMES)}")
    try:
        get_easing(spec.easing)
    except KeyError as exc:
        raise InfographicError(str(exc)) from exc
    if not (0.0 <= spec.stagger <= 1.0):
        raise InfographicError("stagger must be between 0 and 1")
    if spec.width < 64 or spec.height < 64:
        raise InfographicError("chart is too small to render")
    labels = [s.label for s in spec.series]
    if len(set(labels)) != len(labels):
        raise InfographicError("series labels must be unique")

    counts = {len(s.values) for s in spec.series}
    for s in spec.series:
        if not s.values:
            raise InfographicError(f"series {s.label!r} has no values")
        for v in s.values:
            if not isinstance(v, (int, float)) or isinstance(v, bool) or not math.isfinite(v):
                raise InfographicError(f"series {s.label!r} has a missing or non-finite value")
            if spec.kind in _NEEDS_NONNEG and v < 0:
                raise InfographicError(f"series {s.label!r} has a negative value, "
                                       f"which {spec.kind} cannot show")
    if len(counts) != 1:
        raise InfographicError("all series must have the same number of values")
    n = counts.pop()
    if spec.kind == "counter":
        if n != 1 or len(spec.series) != 1:
            raise InfographicError("counter takes exactly one series with one value")
    elif spec.kind == "progress":
        for s in spec.series:
            if any(v > 1.0 for v in s.values):
                raise InfographicError("progress values must be fractions in [0, 1]")
    else:
        if spec.categories and len(spec.categories) != n:
            raise InfographicError(f"{len(spec.categories)} categories for {n} values")
    if spec.kind in {"pie", "donut"}:
        if len(spec.series) != 1:
            raise InfographicError(f"{spec.kind} takes exactly one series")
        if sum(spec.series[0].values) <= 0:
            raise InfographicError(f"{spec.kind} needs at least one positive value")


# ---------------------------------------------------------------------------
# Animation helpers
# ---------------------------------------------------------------------------

def _progress_for(index: int, count: int, p: float, stagger: float, ease: Callable[[float], float]) -> float:
    """Per-item eased progress with an optional staggered start."""
    if stagger <= 0 or count <= 1:
        return ease(max(0.0, min(1.0, p)))
    start = stagger * (index / count)
    span = 1.0 - stagger + (stagger / count)
    local = (p - start) / span
    return ease(max(0.0, min(1.0, local)))


def _fmt(value: float, unit: str = "") -> str:
    s = f"{value:,.0f}" if abs(value - round(value)) < 1e-9 else f"{value:,.1f}"
    return f"{s} {unit}".strip() if unit else s


def _header(img: Image.Image, draw: ImageDraw.ImageDraw, spec: ChartSpec, theme: Theme) -> tuple[int, int, int, int]:
    """Draw title, source and illustrative tag. Returns the content box (x0, y0, x1, y1)."""
    w, h = img.size
    margin = int(min(w, h) * SAFE_MARGIN)
    y = margin
    if spec.title:
        f = font(theme, max(12, int(h * 0.040)), bold=True)
        draw.text((margin, y), spec.title, font=f, fill=theme.text)
        y += text_size(draw, spec.title, f)[1] + int(h * 0.02)
    if spec.illustrative:
        f = font(theme, max(10, int(h * 0.020)), bold=True)
        tag = "ILLUSTRATIVE"
        tw, th = text_size(draw, tag, f)
        draw.rectangle((w - margin - tw - 12, margin, w - margin, margin + th + 8),
                       fill=(90, 60, 60) if theme is DARK else (220, 200, 200))
        draw.text((w - margin - tw - 6, margin + 4), tag, font=f, fill=theme.text)
    bottom = h - margin
    if spec.source:
        f = font(theme, max(10, int(h * 0.019)))
        draw.text((margin, h - margin - text_size(draw, "X", f)[1]),
                  f"Source: {spec.source}", font=f, fill=theme.muted)
        bottom -= int(h * 0.04)
    if spec.legend and spec.kind not in {"counter", "progress"}:
        bottom = _legend(draw, spec, theme, margin, bottom, w)
    return (margin, y, w - margin, bottom)


def _legend(draw, spec, theme, margin, bottom, w) -> int:
    items = spec.series if spec.kind not in {"pie", "donut"} else [
        Series(c, (0,), theme.color(i)) for i, c in enumerate(spec.categories)]
    f = font(theme, max(10, int(spec.height * 0.020)))
    sw = int(spec.height * 0.022)
    x, y = margin, bottom - sw
    for i, s in enumerate(items):
        col = s.color or theme.color(i)
        label = s.label
        tw = text_size(draw, label, f)[0]
        if x + sw + 6 + tw > w - margin:
            break
        draw.rectangle((x, y, x + sw, y + sw), fill=col)
        draw.text((x + sw + 6, y), label, font=f, fill=theme.text)
        x += sw + 6 + tw + int(spec.height * 0.02)
    return y - int(spec.height * 0.015)


# ---------------------------------------------------------------------------
# Chart drawing: each returns a frame for a given progress
# ---------------------------------------------------------------------------

def _draw_vertical_bar(spec, theme, p, horizontal=False) -> Image.Image:
    img = Image.new("RGB", (spec.width, spec.height), theme.background)
    d = ImageDraw.Draw(img)
    x0, y0, x1, y1 = _header(img, d, spec, theme)
    ease = get_easing(spec.easing)
    vals = spec.series[0].values
    cats = spec.categories or tuple(str(i + 1) for i in range(len(vals)))
    vmax = max(v for s in spec.series for v in s.values) or 1.0
    n = len(vals)
    f_val = font(theme, max(10, int(spec.height * 0.026)), bold=True)
    f_lab = font(theme, max(10, int(spec.height * 0.024)))

    if not horizontal:
        plot_bottom = y1 - int(spec.height * 0.05)
        gap = int((x1 - x0) * 0.04)
        bw = (x1 - x0 - gap * (n - 1)) // n
        full_h = plot_bottom - y0
        d.line((x0, plot_bottom, x1, plot_bottom), fill=theme.muted, width=2)
        for i, (cat, v) in enumerate(zip(cats, vals)):
            pi = _progress_for(i, n, p, spec.stagger, ease)
            bx0 = x0 + i * (bw + gap)
            bh = full_h * (v / vmax) * pi
            col = spec.series[0].color or theme.color(i)
            if bh >= 1:
                d.rectangle((bx0, plot_bottom - bh, bx0 + bw, plot_bottom), fill=col)
            d.text((bx0, plot_bottom - bh - int(spec.height * 0.032)), _fmt(v * pi, spec.unit),
                   font=f_val, fill=theme.text)
            d.text((bx0, plot_bottom + int(spec.height * 0.012)), cat, font=f_lab, fill=theme.text)
    else:
        gap = int((y1 - y0) * 0.04)
        bh = (y1 - y0 - gap * (n - 1)) // n
        full_w = (x1 - x0) * 0.72
        label_x = x0
        for i, (cat, v) in enumerate(zip(cats, vals)):
            pi = _progress_for(i, n, p, spec.stagger, ease)
            by0 = y0 + i * (bh + gap)
            bar_x = x0 + int((x1 - x0) * 0.26)
            bw = full_w * (v / vmax) * pi
            col = spec.series[0].color or theme.color(i)
            d.text((label_x, by0 + bh // 2 - int(spec.height * 0.012)), cat, font=f_lab, fill=theme.text)
            if bw >= 1:
                d.rectangle((bar_x, by0, bar_x + bw, by0 + bh), fill=col)
            d.text((bar_x + bw + 8, by0 + bh // 2 - int(spec.height * 0.013)), _fmt(v * pi, spec.unit),
                   font=f_val, fill=theme.text)
    return img


def _draw_line_area(spec, theme, p, fill=False) -> Image.Image:
    img = Image.new("RGB", (spec.width, spec.height), theme.background)
    d = ImageDraw.Draw(img)
    x0, y0, x1, y1 = _header(img, d, spec, theme)
    ease = get_easing(spec.easing)
    pe = ease(max(0.0, min(1.0, p)))
    vals_all = [v for s in spec.series for v in s.values]
    vmax = max(vals_all) or 1.0
    vmin = min(0.0, min(vals_all))
    span = (vmax - vmin) or 1.0
    plot_bottom = y1 - int(spec.height * 0.05)
    cats = spec.categories or tuple(str(i + 1) for i in range(len(spec.series[0].values)))
    n = len(cats)
    for gi in range(5):
        gy = y0 + (plot_bottom - y0) * gi / 4
        d.line((x0, gy, x1, gy), fill=theme.grid, width=1)

    def pt(i, v):
        x = x0 + (x1 - x0) * (i / (n - 1) if n > 1 else 0.5)
        y = plot_bottom - (plot_bottom - y0) * ((v - vmin) / span)
        return (x, y)

    reveal = pe * (n - 1)
    for si, s in enumerate(spec.series):
        col = s.color or theme.color(si)
        pts = []
        for i, v in enumerate(s.values):
            if i <= reveal:
                pts.append(pt(i, v))
            elif i - 1 < reveal < i:
                f = reveal - (i - 1)
                v_prev, x_prev = s.values[i - 1], pt(i - 1, s.values[i - 1])
                x_cur = pt(i, v)
                pts.append((x_prev[0] + (x_cur[0] - x_prev[0]) * f,
                            x_prev[1] + (x_cur[1] - x_prev[1]) * f))
                break
        if fill and len(pts) >= 2:
            poly = pts + [(pts[-1][0], plot_bottom), (pts[0][0], plot_bottom)]
            d.polygon(poly, fill=_blend(col, theme.background, 0.5))
        if len(pts) >= 2:
            d.line(pts, fill=col, width=max(2, int(spec.height * 0.004)))
        for pp in pts:
            r = max(2, int(spec.height * 0.005))
            d.ellipse((pp[0] - r, pp[1] - r, pp[0] + r, pp[1] + r), fill=col)
    f_lab = font(theme, max(10, int(spec.height * 0.020)))
    for i, cat in enumerate(cats):
        x = pt(i, vmin)[0]
        d.text((x, plot_bottom + int(spec.height * 0.012)), cat, font=f_lab, fill=theme.muted)
    return img


def _blend(a, b, t):
    return tuple(int(a[i] * (1 - t) + b[i] * t) for i in range(3))


def _draw_pie(spec, theme, p, donut=False) -> Image.Image:
    img = Image.new("RGB", (spec.width, spec.height), theme.background)
    d = ImageDraw.Draw(img)
    x0, y0, x1, y1 = _header(img, d, spec, theme)
    ease = get_easing(spec.easing)
    pe = ease(max(0.0, min(1.0, p)))
    vals = spec.series[0].values
    total = sum(vals) or 1.0
    cats = spec.categories or tuple(str(i + 1) for i in range(len(vals)))
    size = int(min(x1 - x0, y1 - y0) * 0.86)
    cx = (x0 + x1) // 2
    cy = (y0 + y1) // 2
    box = (cx - size // 2, cy - size // 2, cx + size // 2, cy + size // 2)
    start = -90.0
    swept = 360.0 * pe
    acc = 0.0
    for i, v in enumerate(vals):
        frac = v / total
        seg = 360.0 * frac
        a0 = start + acc
        a1 = start + min(acc + seg, swept)
        if a1 > a0:
            d.pieslice(box, a0, a1, fill=theme.color(i))
        acc += seg
        if acc > swept:
            break
    if donut:
        r = size // 4
        d.ellipse((cx - r, cy - r, cx + r, cy + r), fill=theme.background)
        f = font(theme, max(12, int(spec.height * 0.034)), bold=True)
        tw, th = text_size(d, _fmt(total, spec.unit), f)
        d.text((cx - tw // 2, cy - th // 2), _fmt(total, spec.unit), font=f, fill=theme.text)
    return img


def _draw_ranking(spec, theme, p) -> Image.Image:
    """Horizontal bars sorted descending, with rank numbers. Bars interpolate toward final order."""
    ordered = sorted(enumerate(spec.series[0].values), key=lambda kv: -kv[1])
    cats = spec.categories or tuple(str(i + 1) for i in range(len(spec.series[0].values)))
    ranked = ChartSpec(kind="horizontal_bar",
                       categories=tuple(f"{r+1}. {cats[idx]}" for r, (idx, _) in enumerate(ordered)),
                       series=(Series(spec.series[0].label, tuple(v for _, v in ordered)),),
                       title=spec.title, unit=spec.unit, source=spec.source, theme=spec.theme,
                       duration=spec.duration, easing=spec.easing, width=spec.width, height=spec.height,
                       illustrative=spec.illustrative, stagger=spec.stagger)
    return _draw_vertical_bar(ranked, theme, p, horizontal=True)


def _draw_comparison(spec, theme, p) -> Image.Image:
    """Grouped vertical bars: several series per category, side by side."""
    img = Image.new("RGB", (spec.width, spec.height), theme.background)
    d = ImageDraw.Draw(img)
    x0, y0, x1, y1 = _header(img, d, spec, theme)
    ease = get_easing(spec.easing)
    cats = spec.categories or tuple(str(i + 1) for i in range(len(spec.series[0].values)))
    vmax = max(v for s in spec.series for v in s.values) or 1.0
    n_cat = len(cats)
    n_ser = len(spec.series)
    plot_bottom = y1 - int(spec.height * 0.05)
    group_gap = int((x1 - x0) * 0.06)
    group_w = (x1 - x0 - group_gap * (n_cat - 1)) // n_cat
    bar_gap = max(2, int(group_w * 0.06))
    bw = (group_w - bar_gap * (n_ser - 1)) // n_ser
    full_h = plot_bottom - y0
    d.line((x0, plot_bottom, x1, plot_bottom), fill=theme.muted, width=2)
    f_lab = font(theme, max(10, int(spec.height * 0.022)))
    for ci, cat in enumerate(cats):
        gx = x0 + ci * (group_w + group_gap)
        for si, s in enumerate(spec.series):
            pi = _progress_for(si, n_ser, p, spec.stagger, ease)
            v = s.values[ci]
            bx = gx + si * (bw + bar_gap)
            bh = full_h * (v / vmax) * pi
            if bh >= 1:
                d.rectangle((bx, plot_bottom - bh, bx + bw, plot_bottom),
                            fill=s.color or theme.color(si))
        tw = text_size(d, cat, f_lab)[0]
        d.text((gx + group_w // 2 - tw // 2, plot_bottom + int(spec.height * 0.012)), cat,
               font=f_lab, fill=theme.text)
    return img


def _draw_progress(spec, theme, p) -> Image.Image:
    """One or more horizontal progress bars with a percentage readout."""
    img = Image.new("RGB", (spec.width, spec.height), theme.background)
    d = ImageDraw.Draw(img)
    x0, y0, x1, y1 = _header(img, d, spec, theme)
    ease = get_easing(spec.easing)
    n = len(spec.series)
    row_h = (y1 - y0) // max(1, n)
    bar_h = int(row_h * 0.34)
    f_lab = font(theme, max(10, int(spec.height * 0.024)))
    f_val = font(theme, max(10, int(spec.height * 0.028)), bold=True)
    for i, s in enumerate(spec.series):
        pi = _progress_for(i, n, p, spec.stagger, ease)
        frac = s.values[0] * pi
        ry = y0 + i * row_h + row_h // 3
        d.text((x0, ry - int(spec.height * 0.032)), s.label, font=f_lab, fill=theme.text)
        d.rounded_rectangle((x0, ry, x1, ry + bar_h), radius=bar_h // 2, fill=theme.grid)
        fill_w = x0 + (x1 - x0) * max(0.0, min(1.0, frac))
        if fill_w > x0 + bar_h:
            d.rounded_rectangle((x0, ry, fill_w, ry + bar_h), radius=bar_h // 2,
                                fill=s.color or theme.color(i))
        pct = f"{frac * 100:.0f}%"
        d.text((x1 - text_size(d, pct, f_val)[0], ry - int(spec.height * 0.034)), pct,
               font=f_val, fill=theme.text)
    return img


def _draw_counter(spec, theme, p) -> Image.Image:
    """A single number counting from 0 to its value, centred."""
    img = Image.new("RGB", (spec.width, spec.height), theme.background)
    d = ImageDraw.Draw(img)
    x0, y0, x1, y1 = _header(img, d, spec, theme)
    ease = get_easing(spec.easing)
    pe = ease(max(0.0, min(1.0, p)))
    target = spec.series[0].values[0]
    shown = target * pe
    f_big = font(theme, max(24, int(spec.height * 0.16)), bold=True)
    text = _fmt(shown, spec.unit)
    tw, th = text_size(d, text, f_big)
    cx, cy = (x0 + x1) // 2, (y0 + y1) // 2
    d.text((cx - tw // 2, cy - th // 2), text, font=f_big, fill=theme.color(0))
    if spec.series[0].label:
        f_lab = font(theme, max(12, int(spec.height * 0.032)))
        lw = text_size(d, spec.series[0].label, f_lab)[0]
        d.text((cx - lw // 2, cy + th), spec.series[0].label, font=f_lab, fill=theme.text)
    return img


_DRAWERS: dict[str, Callable[[ChartSpec, Theme, float], Image.Image]] = {
    "vertical_bar": lambda s, t, p: _draw_vertical_bar(s, t, p, horizontal=False),
    "horizontal_bar": lambda s, t, p: _draw_vertical_bar(s, t, p, horizontal=True),
    "line": lambda s, t, p: _draw_line_area(s, t, p, fill=False),
    "area": lambda s, t, p: _draw_line_area(s, t, p, fill=True),
    "pie": lambda s, t, p: _draw_pie(s, t, p, donut=False),
    "donut": lambda s, t, p: _draw_pie(s, t, p, donut=True),
    "ranking": _draw_ranking,
    "comparison": _draw_comparison,
    "progress": _draw_progress,
    "counter": _draw_counter,
}


def render_chart_frame(spec: ChartSpec, progress: float) -> Image.Image:
    validate(spec)
    theme = spec.resolved_theme()
    return _DRAWERS[spec.kind](spec, theme, progress)


def chart_png(spec: ChartSpec, out: str | Path) -> Path:
    out = Path(out)
    out.parent.mkdir(parents=True, exist_ok=True)
    render_chart_frame(spec, 1.0).save(out)
    return out


def chart_video(spec: ChartSpec, out: str | Path, *, fps: float = 30.0, crf: int = 18,
                hold_seconds: float = 0.8) -> dict:
    """Animate from 0 to the data over `duration`, then hold the final frame. Even dimensions."""
    from uvs.animate import encode_frames

    validate(spec)
    total = spec.duration + max(0.0, hold_seconds)
    n = max(2, int(round(total * fps)))

    def frames():
        for i in range(n):
            t = (i / (n - 1)) * total
            yield render_chart_frame(spec, min(1.0, t / spec.duration))

    written = encode_frames(out, fps=fps, width=spec.width, height=spec.height,
                            frames=frames(), crf=crf)
    return {"path": str(out), "frames": written, "fps": fps,
            "width": spec.width, "height": spec.height, "kind": spec.kind}
