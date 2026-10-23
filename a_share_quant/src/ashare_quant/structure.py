"""Online close-based directional changes, confirmed legs and disjoint centers."""

from __future__ import annotations

import math
from dataclasses import dataclass

from .data import Bar, validate_bars


@dataclass(frozen=True)
class Pivot:
    kind: str
    index: int
    confirmed_index: int
    price: float


@dataclass(frozen=True)
class Leg:
    start: Pivot
    end: Pivot
    direction: str
    duration: int
    magnitude: float
    relative_volume: float
    energy: float


@dataclass(frozen=True)
class Center:
    first_leg: int
    last_leg: int
    low: float
    high: float
    created_index: int
    updated_index: int
    closed_index: int | None = None


class DirectionalChanges:
    def __init__(self, reversal: float = 0.06):
        if not 0 < reversal < 1:
            raise ValueError("reversal must be in (0, 1)")
        self.reversal = reversal
        self.pivots: list[Pivot] = []
        self._high: tuple[int, float] | None = None
        self._low: tuple[int, float] | None = None
        self._direction = "unknown"
        self._index = -1

    def update(self, close: float) -> Pivot | None:
        if not math.isfinite(close) or close <= 0:
            raise ValueError("close must be positive and finite")
        self._index += 1
        i, r = self._index, self.reversal
        if self._high is None:
            self._high = self._low = (i, close)
            return None
        if self._direction in ("unknown", "up") and close > self._high[1]:
            self._high = (i, close)
        if self._direction in ("unknown", "down") and close < self._low[1]:
            self._low = (i, close)
        pivot = None
        if self._direction in ("unknown", "down") and close >= self._low[1] * (1 + r):
            pivot = Pivot("low", self._low[0], i, self._low[1])
            self._direction, self._high = "up", (i, close)
        elif self._direction in ("unknown", "up") and close <= self._high[1] * (1 - r):
            pivot = Pivot("high", self._high[0], i, self._high[1])
            self._direction, self._low = "down", (i, close)
        if pivot:
            self.pivots.append(pivot)
        return pivot


def make_legs(bars: list[Bar], pivots: list[Pivot], volume_window: int = 20) -> list[Leg]:
    legs = []
    for a, b in zip(pivots, pivots[1:]):
        duration = b.index - a.index
        if duration <= 0 or b.confirmed_index >= len(bars):
            raise ValueError("invalid or not-yet-confirmed pivots")
        base = bars[max(0, a.index - volume_window):a.index]
        segment = bars[a.index + 1:b.index + 1]
        baseline = sum(x.volume for x in base) / len(base) if base else 0.0
        relative = (sum(x.volume for x in segment) / duration / baseline) if baseline > 0 else 0.0
        magnitude = abs(math.log(b.price / a.price))
        legs.append(Leg(a, b, "up" if b.price > a.price else "down", duration,
                        magnitude, relative, magnitude / duration * relative))
    return legs


def centers(legs: list[Leg]) -> list[Center]:
    """Each completed leg belongs to at most one center; no retrospective merge."""
    result: list[Center] = []
    first = 0
    while first + 2 < len(legs):
        triple = legs[first:first + 3]
        low = max(min(x.start.price, x.end.price) for x in triple)
        high = min(max(x.start.price, x.end.price) for x in triple)
        if low >= high:
            first += 1
            continue
        created = triple[-1].end.confirmed_index
        last, updated, closed = first + 2, created, None
        for j in range(first + 3, len(legs)):
            leg = legs[j]
            new_low = max(low, min(leg.start.price, leg.end.price))
            new_high = min(high, max(leg.start.price, leg.end.price))
            if new_low >= new_high:
                closed = leg.end.confirmed_index
                break
            low, high, last, updated = new_low, new_high, j, leg.end.confirmed_index
        result.append(Center(first, last, low, high, created, updated, closed))
        first = last + 1
    return result


def identify(bars: list[Bar], reversal: float = 0.06, volume_window: int = 20) -> tuple[list[Pivot], list[Leg], list[Center]]:
    validate_bars(bars)
    detector = DirectionalChanges(reversal)
    for b in bars:
        detector.update(b.close)
    legs = make_legs(bars, detector.pivots, volume_window)
    return detector.pivots, legs, centers(legs)


def wicks(bar: Bar) -> tuple[float, float]:
    span = bar.high - bar.low
    if span == 0:
        return 0.0, 0.0
    return ((min(bar.open, bar.close) - bar.low) / span,
            (bar.high - max(bar.open, bar.close)) / span)
