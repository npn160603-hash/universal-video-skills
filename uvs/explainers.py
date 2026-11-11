"""Animated timelines, diagrams and visual metaphors (Phase 6.2–6.4).

Timelines place dated events on an axis with a moving playhead; the event nearest the playhead is
highlighted and its date counts up. Diagrams lay out nodes on levelled rows and route straight
connectors, checking that node boxes do not overlap and that labels stay inside their boxes.
Visual metaphors are abstract illustrations (stress, pressure, distance, ...) and always carry an
"Illustrative" tag, because they are not data.

All three render to PIL frames and encode through uvs.animate.encode_frames. Rendering a given
frame twice is byte-identical.
"""
from __future__ import annotations

import math
from dataclasses import dataclass, field
from pathlib import Path
from typing import Callable

from PIL import Image, ImageDraw

from uvs.infographics import Theme, THEMES, font, text_size, _blend
from uvs.motion import get_easing


class ExplainerError(ValueError):
    pass


# ---------------------------------------------------------------------------
# Timelines (6.2)
# ---------------------------------------------------------------------------

TIMELINE_KINDS = ("historical", "personal_journey", "event_chronology", "milestone",
                  "before_after", "process")


@dataclass(frozen=True)
class Event:
    position: float   # sort key; for historical, the year
    label: str
    detail: str = ""


@dataclass
class Timeline:
    kind: str
    events: tuple[Event, ...]
    title: str = ""
    source: str = ""
    theme: str = "dark"
    duration: float = 4.0
    easing: str = "ease_in_out"
    width: int = 1920
    height: int = 1080
    date_as_year: bool = True

    def resolved_theme(self) -> Theme:
        return THEMES[self.theme]


def validate_timeline(tl: Timeline) -> None:
    if tl.kind not in TIMELINE_KINDS:
        raise ExplainerError(f"unknown timeline kind {tl.kind!r}; options: {TIMELINE_KINDS}")
    if tl.theme not in THEMES:
        raise ExplainerError(f"unknown theme {tl.theme!r}")
    if len(tl.events) < 2:
        raise ExplainerError("a timeline needs at least two events")
    try:
        get_easing(tl.easing)
    except KeyError as exc:
        raise ExplainerError(str(exc)) from exc
    positions = [e.position for e in tl.events]
    for p in positions:
        if not math.isfinite(p):
            raise ExplainerError("event positions must be finite numbers")
    if list(positions) != sorted(positions):
        raise ExplainerError("events must be supplied in chronological order")
    if tl.kind == "before_after" and len(tl.events) != 2:
        raise ExplainerError("a before/after timeline takes exactly two events")


def playhead_index(tl: Timeline, p: float) -> int:
    """Index of the event the playhead has reached at eased progress p."""
    ease = get_easing(tl.easing)
    pe = ease(max(0.0, min(1.0, p)))
    n = len(tl.events)
    return min(n - 1, int(pe * n))


def render_timeline_frame(tl: Timeline, p: float) -> Image.Image:
    validate_timeline(tl)
    theme = tl.resolved_theme()
    ease = get_easing(tl.easing)
    pe = ease(max(0.0, min(1.0, p)))
    img = Image.new("RGB", (tl.width, tl.height), theme.background)
    d = ImageDraw.Draw(img)
    margin = int(min(tl.width, tl.height) * 0.08)
    if tl.title:
        f = font(theme, max(14, int(tl.height * 0.05)), bold=True)
        d.text((margin, int(tl.height * 0.04)), tl.title, font=f, fill=theme.text)
    axis_y = tl.height // 2
    x0, x1 = margin, tl.width - margin
    positions = [e.position for e in tl.events]
    lo, hi = min(positions), max(positions)
    span = (hi - lo) or 1.0

    def ex(e):
        return x0 + (x1 - x0) * ((e.position - lo) / span)

    # revealed portion of the axis
    head_x = x0 + (x1 - x0) * pe
    d.line((x0, axis_y, x1, axis_y), fill=theme.grid, width=3)
    d.line((x0, axis_y, head_x, axis_y), fill=theme.color(0), width=5)

    active = playhead_index(tl, p)
    f_lab = font(theme, max(12, int(tl.height * 0.030)))
    f_date = font(theme, max(12, int(tl.height * 0.034)), bold=True)
    for i, e in enumerate(tl.events):
        x = ex(e)
        revealed = x <= head_x + 1
        reached = i <= active
        col = theme.color(0) if reached else theme.grid
        r = int(tl.height * (0.016 if not reached else 0.022))
        d.ellipse((x - r, axis_y - r, x + r, axis_y + r), fill=col)
        if revealed:
            above = i % 2 == 0
            ly = axis_y - int(tl.height * 0.12) if above else axis_y + int(tl.height * 0.06)
            lbl = e.label
            tw = text_size(d, lbl, f_lab)[0]
            lx = max(x0, min(x - tw // 2, x1 - tw))
            d.text((lx, ly), lbl, font=f_lab, fill=theme.text if reached else theme.muted)
            if tl.date_as_year:
                date = str(int(e.position))
            else:
                date = f"{e.position:g}"
            dw = text_size(d, date, f_date)[0]
            d.text((max(x0, min(x - dw // 2, x1 - dw)),
                    ly - int(tl.height * 0.045) if above else ly + int(tl.height * 0.04)),
                   date, font=f_date, fill=col)
    # playhead marker
    d.polygon([(head_x, axis_y - int(tl.height * 0.03)), (head_x - 10, axis_y - int(tl.height * 0.06)),
               (head_x + 10, axis_y - int(tl.height * 0.06))], fill=theme.text)
    if tl.source:
        f = font(theme, max(10, int(tl.height * 0.020)))
        d.text((margin, tl.height - margin), f"Source: {tl.source}", font=f, fill=theme.muted)
    return img


# ---------------------------------------------------------------------------
# Diagram engine (6.3)
# ---------------------------------------------------------------------------

DIAGRAM_KINDS = ("flowchart", "decision_tree", "cause_effect", "relationship",
                 "process", "hierarchy", "comparison")


@dataclass(frozen=True)
class DiagNode:
    id: str
    label: str
    level: int            # row (0 at top)


@dataclass(frozen=True)
class DiagEdge:
    src: str
    dst: str
    label: str = ""


@dataclass
class Diagram:
    kind: str
    nodes: tuple[DiagNode, ...]
    edges: tuple[DiagEdge, ...]
    title: str = ""
    theme: str = "dark"
    duration: float = 3.0
    easing: str = "ease_out"
    width: int = 1920
    height: int = 1080
    node_w: int = 260
    node_h: int = 110

    def resolved_theme(self) -> Theme:
        return THEMES[self.theme]


def validate_diagram(dg: Diagram) -> list[str]:
    """Structural problems. Empty means the diagram can be laid out."""
    problems: list[str] = []
    if dg.kind not in DIAGRAM_KINDS:
        problems.append(f"unknown diagram kind {dg.kind!r}")
    if not dg.nodes:
        problems.append("a diagram needs at least one node")
    ids = [n.id for n in dg.nodes]
    if len(set(ids)) != len(ids):
        problems.append("node ids must be unique")
    idset = set(ids)
    for e in dg.edges:
        if e.src not in idset:
            problems.append(f"edge from unknown node {e.src!r}")
        if e.dst not in idset:
            problems.append(f"edge to unknown node {e.dst!r}")
    for n in dg.nodes:
        if n.level < 0:
            problems.append(f"node {n.id!r} has a negative level")
    return problems


def layout_diagram(dg: Diagram) -> dict[str, tuple[int, int, int, int]]:
    """Place each node as a box (x0, y0, x1, y1). Rows are levels; nodes spread across each row."""
    problems = validate_diagram(dg)
    if problems:
        raise ExplainerError("; ".join(problems))
    margin = int(min(dg.width, dg.height) * 0.08)
    top = margin + (int(dg.height * 0.06) if dg.title else 0)
    levels: dict[int, list[DiagNode]] = {}
    for n in dg.nodes:
        levels.setdefault(n.level, []).append(n)
    n_levels = max(levels) + 1
    usable_h = dg.height - top - margin
    row_gap = usable_h / n_levels
    boxes: dict[str, tuple[int, int, int, int]] = {}
    for lvl, nodes in levels.items():
        k = len(nodes)
        cy = int(top + row_gap * (lvl + 0.5))
        usable_w = dg.width - 2 * margin
        slot = usable_w / k
        for i, node in enumerate(nodes):
            cx = int(margin + slot * (i + 0.5))
            x0 = cx - dg.node_w // 2
            y0 = cy - dg.node_h // 2
            boxes[node.id] = (x0, y0, x0 + dg.node_w, y0 + dg.node_h)
    return boxes


def overlaps(boxes: dict[str, tuple[int, int, int, int]], pad: int = 8) -> list[tuple[str, str]]:
    """Pairs of node boxes that overlap (with padding). Empty means the layout is clean."""
    bad = []
    items = list(boxes.items())
    for i in range(len(items)):
        for j in range(i + 1, len(items)):
            (ia, a), (ib, b) = items[i], items[j]
            if not (a[2] + pad <= b[0] or b[2] + pad <= a[0]
                    or a[3] + pad <= b[1] or b[3] + pad <= a[1]):
                bad.append((ia, ib))
    return bad


def _fit_label(d: ImageDraw.ImageDraw, label: str, box, theme, max_size: int) -> tuple:
    """Largest font (down to a floor) whose text fits inside the box; wraps to two lines if needed."""
    w = box[2] - box[0] - 16
    h = box[3] - box[1] - 12
    for size in range(max_size, 9, -2):
        f = font(theme, size, bold=True)
        tw, th = text_size(d, label, f)
        if tw <= w and th <= h:
            return (f, [label])
        # try two lines on the middle space
        if " " in label:
            words = label.split()
            mid = len(words) // 2
            l1, l2 = " ".join(words[:mid]), " ".join(words[mid:])
            t1, t2 = text_size(d, l1, f), text_size(d, l2, f)
            if max(t1[0], t2[0]) <= w and t1[1] + t2[1] + 4 <= h:
                return (f, [l1, l2])
    return (font(theme, 10, bold=True), [label])


def render_diagram_frame(dg: Diagram, p: float) -> Image.Image:
    boxes = layout_diagram(dg)
    bad = overlaps(boxes)
    if bad:
        raise ExplainerError(f"node boxes overlap: {bad}")
    theme = dg.resolved_theme()
    ease = get_easing(dg.easing)
    pe = ease(max(0.0, min(1.0, p)))
    img = Image.new("RGB", (dg.width, dg.height), theme.background)
    d = ImageDraw.Draw(img)
    if dg.title:
        f = font(theme, max(14, int(dg.height * 0.05)), bold=True)
        d.text((int(dg.width * 0.06), int(dg.height * 0.04)), dg.title, font=f, fill=theme.text)
    n = len(dg.nodes)
    # staggered reveal: node i appears as p passes i/n
    def node_alpha(i):
        return max(0.0, min(1.0, pe * n - i))

    # edges first (behind nodes), revealed with their source node
    id_index = {node.id: i for i, node in enumerate(dg.nodes)}
    for e in dg.edges:
        a, b = boxes[e.src], boxes[e.dst]
        if node_alpha(id_index[e.dst]) <= 0:
            continue
        p0 = ((a[0] + a[2]) // 2, a[3])
        p1 = ((b[0] + b[2]) // 2, b[1])
        d.line([p0, p1], fill=theme.muted, width=3)
        # arrowhead
        ang = math.atan2(p1[1] - p0[1], p1[0] - p0[0])
        ah = 12
        d.polygon([p1,
                   (p1[0] - ah * math.cos(ang - 0.4), p1[1] - ah * math.sin(ang - 0.4)),
                   (p1[0] - ah * math.cos(ang + 0.4), p1[1] - ah * math.sin(ang + 0.4))],
                  fill=theme.muted)
        if e.label:
            fe = font(theme, max(10, int(dg.height * 0.020)))
            mx, my = (p0[0] + p1[0]) // 2, (p0[1] + p1[1]) // 2
            tw, th = text_size(d, e.label, fe)
            d.rectangle((mx - tw // 2 - 4, my - th // 2 - 2, mx + tw // 2 + 4, my + th // 2 + 2),
                        fill=theme.background)
            d.text((mx - tw // 2, my - th // 2), e.label, font=fe, fill=theme.muted)

    for i, node in enumerate(dg.nodes):
        a = node_alpha(i)
        if a <= 0:
            continue
        box = boxes[node.id]
        col = _blend(theme.background, theme.color(node.level), a)
        d.rounded_rectangle(box, radius=16, fill=col, outline=theme.color(node.level), width=3)
        f, lines = _fit_label(d, node.label, box, theme, max(12, int(dg.height * 0.030)))
        total_h = sum(text_size(d, ln, f)[1] for ln in lines) + (len(lines) - 1) * 4
        cy = (box[1] + box[3]) // 2 - total_h // 2
        for ln in lines:
            tw, th = text_size(d, ln, f)
            d.text(((box[0] + box[2]) // 2 - tw // 2, cy), ln, font=f, fill=theme.text)
            cy += th + 4
    return img


# ---------------------------------------------------------------------------
# Visual metaphors (6.4) — always illustrative
# ---------------------------------------------------------------------------

METAPHORS = ("stress_accumulation", "emotional_isolation", "increasing_pressure",
             "personal_boundaries", "time_passing", "growing_distance",
             "competing_choices", "progress_toward_goal")


@dataclass
class Metaphor:
    kind: str
    title: str = ""
    theme: str = "dark"
    duration: float = 4.0
    easing: str = "ease_in_out"
    width: int = 1080
    height: int = 1920
    intensity: float = 1.0   # 0..1 how far the metaphor develops at p=1

    def resolved_theme(self) -> Theme:
        return THEMES[self.theme]


def validate_metaphor(m: Metaphor) -> None:
    if m.kind not in METAPHORS:
        raise ExplainerError(f"unknown metaphor {m.kind!r}; options: {METAPHORS}")
    if m.theme not in THEMES:
        raise ExplainerError(f"unknown theme {m.theme!r}")
    if not (0.0 <= m.intensity <= 1.0):
        raise ExplainerError("intensity must be between 0 and 1")
    try:
        get_easing(m.easing)
    except KeyError as exc:
        raise ExplainerError(str(exc)) from exc


def _tag(d, m, theme):
    f = font(theme, max(10, int(m.height * 0.016)), bold=True)
    tag = "ILLUSTRATIVE — not data"
    tw, th = text_size(d, tag, f)
    margin = int(min(m.width, m.height) * 0.04)
    d.rectangle((m.width - margin - tw - 12, margin, m.width - margin, margin + th + 8),
                fill=(90, 60, 60) if theme.background[0] < 128 else (220, 200, 200))
    d.text((m.width - margin - tw - 6, margin + 4), tag, font=f, fill=theme.text)
    if m.title:
        ft = font(theme, max(14, int(m.height * 0.030)), bold=True)
        d.text((margin, margin), m.title, font=ft, fill=theme.text)


def render_metaphor_frame(m: Metaphor, p: float) -> Image.Image:
    validate_metaphor(m)
    theme = m.resolved_theme()
    ease = get_easing(m.easing)
    k = ease(max(0.0, min(1.0, p))) * m.intensity
    img = Image.new("RGB", (m.width, m.height), theme.background)
    d = ImageDraw.Draw(img)
    cx, cy = m.width // 2, m.height // 2
    accent = theme.color(2)
    calm = theme.color(1)

    if m.kind == "stress_accumulation":
        # a vessel filling with rising colour
        vw, vh = int(m.width * 0.4), int(m.height * 0.5)
        vx, vy = cx - vw // 2, cy - vh // 2
        d.rectangle((vx, vy, vx + vw, vy + vh), outline=theme.text, width=4)
        fill_h = int(vh * k)
        d.rectangle((vx, vy + vh - fill_h, vx + vw, vy + vh), fill=_blend(calm, accent, k))
    elif m.kind == "emotional_isolation":
        # one figure centred, others drifting outward
        for i in range(8):
            ang = i * math.pi / 4
            dist = int(min(m.width, m.height) * 0.12) + int(min(m.width, m.height) * 0.28 * k)
            px, py = cx + dist * math.cos(ang), cy + dist * math.sin(ang)
            r = int(min(m.width, m.height) * 0.03)
            d.ellipse((px - r, py - r, px + r, py + r), fill=theme.muted)
        r = int(min(m.width, m.height) * 0.045)
        d.ellipse((cx - r, cy - r, cx + r, cy + r), fill=accent)
    elif m.kind == "increasing_pressure":
        # walls closing in on a central shape
        gap = int(m.width * 0.4 * (1 - k)) + int(m.width * 0.05)
        d.rectangle((0, cy - 300, cx - gap // 2, cy + 300), fill=_blend(theme.background, accent, 0.6))
        d.rectangle((cx + gap // 2, cy - 300, m.width, cy + 300), fill=_blend(theme.background, accent, 0.6))
        r = int(min(m.width, m.height) * 0.05)
        d.ellipse((cx - r, cy - r, cx + r, cy + r), fill=calm)
    elif m.kind == "personal_boundaries":
        # a ring that strengthens (thicker, brighter) as k rises
        r = int(min(m.width, m.height) * 0.22)
        width = max(2, int(2 + 20 * k))
        d.ellipse((cx - r, cy - r, cx + r, cy + r), outline=_blend(theme.muted, accent, k), width=width)
        rr = int(min(m.width, m.height) * 0.05)
        d.ellipse((cx - rr, cy - rr, cx + rr, cy + rr), fill=calm)
    elif m.kind == "time_passing":
        # a bar sweeping left to right, with tick marks
        bar_y = cy
        d.line((int(m.width * 0.1), bar_y, int(m.width * 0.9), bar_y), fill=theme.grid, width=6)
        hx = int(m.width * 0.1 + m.width * 0.8 * k)
        d.line((int(m.width * 0.1), bar_y, hx, bar_y), fill=accent, width=6)
        for i in range(11):
            tx = int(m.width * 0.1 + m.width * 0.08 * i)
            d.line((tx, bar_y - 20, tx, bar_y + 20), fill=theme.muted, width=3)
    elif m.kind == "growing_distance":
        # two figures moving apart
        off = int(m.width * 0.12) + int(m.width * 0.3 * k)
        r = int(min(m.width, m.height) * 0.05)
        d.ellipse((cx - off - r, cy - r, cx - off + r, cy + r), fill=calm)
        d.ellipse((cx + off - r, cy - r, cx + off + r, cy + r), fill=accent)
    elif m.kind == "competing_choices":
        # a fork: one path dims, the other brightens as k rises
        base = (cx, int(m.height * 0.75))
        left = (int(m.width * 0.25), int(m.height * 0.3))
        right = (int(m.width * 0.75), int(m.height * 0.3))
        d.line([base, left], fill=_blend(theme.muted, accent, k), width=max(3, int(4 + 16 * k)))
        d.line([base, right], fill=_blend(theme.muted, theme.background, k), width=max(3, int(20 * (1 - k)) + 3))
    elif m.kind == "progress_toward_goal":
        # a path with a marker advancing toward a flag
        y = cy
        d.line((int(m.width * 0.1), y, int(m.width * 0.9), y), fill=theme.grid, width=8)
        gx = int(m.width * 0.9)
        d.rectangle((gx, y - 80, gx + 6, y), fill=theme.text)
        d.polygon([(gx + 6, y - 80), (gx + 6, y - 50), (gx + 60, y - 65)], fill=accent)
        mx = int(m.width * 0.1 + m.width * 0.8 * k)
        r = int(min(m.width, m.height) * 0.03)
        d.ellipse((mx - r, y - r, mx + r, y + r), fill=calm)

    _tag(d, m, theme)
    return img


# ---------------------------------------------------------------------------
# Shared encoding
# ---------------------------------------------------------------------------

def render_video(frame_fn: Callable[[float], Image.Image], out: str | Path, *, duration: float,
                 fps: float, width: int, height: int, hold: float = 0.6, crf: int = 18) -> dict:
    from uvs.animate import encode_frames

    total = duration + max(0.0, hold)
    n = max(2, int(round(total * fps)))

    def frames():
        for i in range(n):
            t = (i / (n - 1)) * total
            yield frame_fn(min(1.0, t / duration))

    written = encode_frames(out, fps=fps, width=width, height=height, frames=frames(), crf=crf)
    return {"path": str(out), "frames": written, "fps": fps, "width": width, "height": height}
