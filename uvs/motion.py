"""Motion engine: easing curves and keyframe tracks (advanced-motion-design, Phase 2).

Every easing maps t in [0, 1] to a progress value with f(0) = 0 and f(1) = 1 exactly.
Overshoot, elastic, and spring curves may leave [0, 1] in between, on purpose.
Keyframe tracks interpolate scalars or tuples (for example x/y position or RGB).
"""
from __future__ import annotations

import math
from dataclasses import dataclass
from typing import Callable, Sequence, Union

Number = float
Value = Union[float, Sequence[float]]
Easing = Callable[[float], float]


def _clamp01(t: float) -> float:
    return 0.0 if t <= 0 else 1.0 if t >= 1 else t


# ---------------------------------------------------------------------------
# Basic and bezier easings
# ---------------------------------------------------------------------------

def linear(t: float) -> float:
    return _clamp01(t)


def cubic_bezier(x1: float, y1: float, x2: float, y2: float) -> Easing:
    """CSS-style cubic bezier easing with control points (x1, y1) and (x2, y2).

    Solves x(s) = t with Newton's method, falling back to bisection, then returns y(s).
    """
    if not (0.0 <= x1 <= 1.0 and 0.0 <= x2 <= 1.0):
        raise ValueError("bezier x control points must be within [0, 1]")

    def bx(s: float) -> float:
        return 3 * (1 - s) ** 2 * s * x1 + 3 * (1 - s) * s ** 2 * x2 + s ** 3

    def by(s: float) -> float:
        return 3 * (1 - s) ** 2 * s * y1 + 3 * (1 - s) * s ** 2 * y2 + s ** 3

    def dbx(s: float) -> float:
        return (3 * (1 - s) ** 2 * x1 + 6 * (1 - s) * s * (x2 - x1) + 3 * s ** 2 * (1 - x2))

    def ease(t: float) -> float:
        t = _clamp01(t)
        if t in (0.0, 1.0):
            return t
        s = t
        for _ in range(8):  # Newton
            err = bx(s) - t
            d = dbx(s)
            if abs(err) < 1e-9 or abs(d) < 1e-9:
                break
            s = min(1.0, max(0.0, s - err / d))
        else:
            lo, hi = 0.0, 1.0  # bisection fallback
            s = t
            for _ in range(60):
                mid = (lo + hi) / 2
                if bx(mid) < t:
                    lo = mid
                else:
                    hi = mid
                s = mid
        return by(s)

    return ease


ease_in = cubic_bezier(0.42, 0.0, 1.0, 1.0)
ease_out = cubic_bezier(0.0, 0.0, 0.58, 1.0)
ease_in_out = cubic_bezier(0.42, 0.0, 0.58, 1.0)


# ---------------------------------------------------------------------------
# Physically motivated easings
# ---------------------------------------------------------------------------

def spring(zeta: float = 0.45, omega: float = 14.0) -> Easing:
    """Damped spring step response, normalized so that spring(0) = 0 and spring(1) = 1.

    zeta < 1 gives an underdamped spring that overshoots and settles. omega sets speed.
    """
    if not 0.0 < zeta < 1.0:
        raise ValueError("zeta must be in (0, 1) for an oscillating spring")
    wd = omega * math.sqrt(1 - zeta ** 2)

    def response(time: float) -> float:
        decay = math.exp(-zeta * omega * time)
        return 1 - decay * (math.cos(wd * time) + (zeta / math.sqrt(1 - zeta ** 2)) * math.sin(wd * time))

    end = response(1.0)

    def ease(t: float) -> float:
        t = _clamp01(t)
        if t == 0.0:
            return 0.0
        if t == 1.0:
            return 1.0
        return response(t) / end

    return ease


def elastic_out(t: float) -> float:
    t = _clamp01(t)
    if t == 0.0 or t == 1.0:
        return t
    return 2 ** (-10 * t) * math.sin((t - 0.075) * (2 * math.pi) / 0.3) + 1


def bounce_out(t: float) -> float:
    t = _clamp01(t)
    n1, d1 = 7.5625, 2.75
    if t < 1 / d1:
        return n1 * t * t
    if t < 2 / d1:
        t -= 1.5 / d1
        return n1 * t * t + 0.75
    if t < 2.5 / d1:
        t -= 2.25 / d1
        return n1 * t * t + 0.9375
    t -= 2.625 / d1
    return n1 * t * t + 0.984375


def overshoot(t: float, s: float = 1.70158) -> float:
    """Back ease-out: rises past 1 and settles. Larger s means a bigger overshoot."""
    t = _clamp01(t)
    u = t - 1
    return 1 + (s + 1) * u ** 3 + s * u ** 2


def damped_oscillation(t: float, cycles: float = 2.5, decay: float = 4.0) -> float:
    """Step that oscillates around 1 and decays. Exactly 0 at t=0 and 1 at t=1."""
    t = _clamp01(t)
    if t == 0.0:
        return 0.0
    if t == 1.0:
        return 1.0
    return 1 - math.exp(-decay * t) * math.cos(2 * math.pi * cycles * t)


EASINGS: dict[str, Easing] = {
    "linear": linear,
    "ease_in": ease_in,
    "ease_out": ease_out,
    "ease_in_out": ease_in_out,
    "spring": spring(),
    "elastic_out": elastic_out,
    "bounce_out": bounce_out,
    "overshoot": overshoot,
    "damped_oscillation": damped_oscillation,
}


def get_easing(name: str) -> Easing:
    if name not in EASINGS:
        raise KeyError(f"unknown easing {name!r}; choose from {sorted(EASINGS)}")
    return EASINGS[name]


# ---------------------------------------------------------------------------
# Keyframes
# ---------------------------------------------------------------------------

@dataclass(frozen=True)
class Keyframe:
    time: float          # seconds
    value: Value         # scalar, or a tuple such as (x, y) or (r, g, b)
    easing: str = "linear"  # easing applied from this keyframe to the next


def _lerp(a: Value, b: Value, p: float) -> Value:
    if isinstance(a, (int, float)) and isinstance(b, (int, float)):
        return a + (b - a) * p
    if len(a) != len(b):
        raise ValueError("keyframe values must have the same dimensions")
    return tuple(x + (y - x) * p for x, y in zip(a, b))


class Track:
    """Ordered keyframes for one property. Holds the first value before the track and the last after it."""

    def __init__(self, keyframes: Sequence[Keyframe]):
        if not keyframes:
            raise ValueError("a track needs at least one keyframe")
        kfs = sorted(keyframes, key=lambda k: k.time)
        for a, b in zip(kfs, kfs[1:]):
            if a.time == b.time:
                raise ValueError(f"two keyframes at the same time {a.time}")
        dims = {len(k.value) if isinstance(k.value, (tuple, list)) else 1 for k in kfs}
        if len(dims) > 1:
            raise ValueError("all keyframes in a track must have the same dimensions")
        for k in kfs:
            get_easing(k.easing)  # validates the name early
        self.keyframes = kfs

    def value_at(self, t: float) -> Value:
        kfs = self.keyframes
        if t <= kfs[0].time:
            return kfs[0].value
        if t >= kfs[-1].time:
            return kfs[-1].value
        for a, b in zip(kfs, kfs[1:]):
            if a.time <= t <= b.time:
                p = (t - a.time) / (b.time - a.time)
                eased = get_easing(a.easing)(p)
                return _lerp(a.value, b.value, eased)
        raise AssertionError("unreachable")  # pragma: no cover

    def sample(self, fps: float, duration: float) -> list[Value]:
        """Frame-accurate samples for frames 0..round(duration * fps) - 1."""
        n = max(1, int(round(duration * fps)))
        return [self.value_at(i / fps) for i in range(n)]
