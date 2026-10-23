"""Causal R1 structure streams. Immutable snapshots never repaint earlier states."""
from __future__ import annotations

import math
from dataclasses import dataclass, replace
from statistics import mean

from ..data import Bar, validate_bars
from ..structure import Center, DirectionalChanges, Leg, Pivot, centers, make_legs


@dataclass(frozen=True)
class Config:
    fixed_reversal: float = 0.06
    atr_window: int = 14
    atr_multiple: float = 2.0
    atr_fraction_floor: float = 0.02
    atr_fraction_cap: float = 0.15
    density_window: int = 40
    density_bin_fraction: float = 0.02
    density_span_bins: int = 2
    density_min_count: int = 12
    density_min_span: int = 15
    density_persistence: int = 3
    support_min_gap: int = 5
    support_max_span: int = 60
    support_rebound: float = 0.05
    support_low_tolerance: float = 0.02
    support_band_buffer: float = 0.01
    birth_dedup_age: int = 60
    max_age: int = 60
    break_closes: int = 2
    break_buffer: float = 0.01
    test_separation: int = 5
    bottom_tolerance: float = 0.05
    bottom_rebound: float = 0.08
    bottom_min_gap: int = 10

    def __post_init__(self):
        from dataclasses import asdict
        if any(not math.isfinite(v) or v <= 0 for v in asdict(self).values()):
            raise ValueError("all R1 parameters must be finite and positive")
        for key in ("atr_window", "density_window", "density_span_bins", "density_min_count",
                    "density_min_span", "density_persistence", "support_min_gap", "support_max_span",
                    "birth_dedup_age", "max_age", "break_closes", "test_separation", "bottom_min_gap"):
            if type(getattr(self, key)) is not int:
                raise ValueError(f"{key} must be an integer")
        if not 0 < self.atr_fraction_floor <= self.atr_fraction_cap < 1:
            raise ValueError("invalid ATR fraction bounds")
        if self.density_min_count > self.density_window or self.support_min_gap > self.support_max_span:
            raise ValueError("invalid count/span")
        if max(self.fixed_reversal, self.density_bin_fraction, self.break_buffer,
               self.support_low_tolerance, self.support_band_buffer, self.bottom_tolerance) >= 1:
            raise ValueError("fraction out of range")


class ATRChanges:
    """Threshold is frozen at each candidate extreme using PRIOR completed ATR."""
    def __init__(self, config: Config):
        self.config = config
        self.pivots: list[Pivot] = []
        self.direction = "unknown"
        self.high = self.low = None
        self.index = -1

    def update(self, close: float, prior_atr: float | None) -> Pivot | None:
        if not math.isfinite(close) or close <= 0 or (prior_atr is not None and (not math.isfinite(prior_atr) or prior_atr < 0)):
            raise ValueError("invalid ATR input")
        self.index += 1
        p, i = self.config, self.index
        fraction = max(p.atr_fraction_floor, min(p.atr_fraction_cap, p.atr_multiple * (prior_atr or 0) / close))
        if self.high is None:
            self.high = self.low = (i, close, fraction)
            return None
        if self.direction in ("unknown", "up") and close > self.high[1]:
            self.high = (i, close, fraction)
        if self.direction in ("unknown", "down") and close < self.low[1]:
            self.low = (i, close, fraction)
        pivot = None
        if self.direction in ("unknown", "down") and close >= self.low[1] * (1 + self.low[2]):
            pivot = Pivot("low", self.low[0], i, self.low[1])
            self.direction, self.high = "up", (i, close, fraction)
        elif self.direction in ("unknown", "up") and close <= self.high[1] * (1 - self.high[2]):
            pivot = Pivot("high", self.high[0], i, self.high[1])
            self.direction, self.low = "down", (i, close, fraction)
        if pivot:
            self.pivots.append(pivot)
        return pivot


@dataclass(frozen=True)
class Zone:
    id: str
    algorithm: str
    formed_index: int
    confirmed_index: int
    lower: float
    upper: float
    centroid: float
    members: tuple[int, ...]
    status: str = "active"
    role: str = "support"
    last_test_index: int | None = None
    independent_tests: int = 0
    outside_count: int = 0
    flips: int = 0
    invalid_index: int | None = None
    structural_closed_index: int | None = None
    breach_index: int | None = None
    reclaim_sessions: int | None = None
    reclaim_fraction: float | None = None

    @property
    def valid(self):
        return self.status in ("active", "role_reversed", "legacy_retained")


def overlap(a: Zone, lower: float, upper: float) -> float:
    intersection = max(0.0, min(a.upper, upper) - max(a.lower, lower))
    union = max(a.upper, upper) - min(a.lower, lower)
    return intersection / union if union else 0.0


class ZoneBook:
    def __init__(self, config: Config, max_age: int | None = 60, allow_flip=True, legacy=False):
        self.config, self.max_age, self.allow_flip, self.legacy = config, max_age, allow_flip, legacy
        self.zones: dict[str, Zone] = {}

    def update(self, index: int, bar: Bar, candidates: list[Zone]) -> tuple[Zone, ...]:
        for z in candidates:
            if z.id not in self.zones:
                self.zones[z.id] = replace(z, role="support" if bar.close >= z.centroid else "resistance")
            elif self.legacy or z.algorithm == "atr_intersection":
                old = self.zones[z.id]
                self.zones[z.id] = replace(old, lower=z.lower, upper=z.upper, centroid=z.centroid,
                                           members=z.members, structural_closed_index=z.structural_closed_index)
        p = self.config
        for key, z in list(self.zones.items()):
            if not z.valid:
                continue
            if self.max_age is not None and index - z.confirmed_index > self.max_age:
                self.zones[key] = replace(z, status="expired", invalid_index=index)
                continue
            if bar.low <= z.upper and bar.high >= z.lower:
                tests = z.independent_tests + int(z.last_test_index is None or index - z.last_test_index >= p.test_separation)
                z = replace(z, last_test_index=index, independent_tests=tests)
            if bar.close < z.lower and z.breach_index is None:
                z = replace(z, breach_index=index)
            if z.breach_index is not None and bar.close >= z.centroid:
                z = replace(z, reclaim_sessions=index - z.breach_index,
                            reclaim_fraction=bar.close / z.lower - 1, breach_index=None)
            if self.legacy:
                self.zones[key] = replace(z, status="legacy_retained", role="both")
                continue
            broken = bar.close < z.lower * (1 - p.break_buffer) if z.role == "support" else bar.close > z.upper * (1 + p.break_buffer)
            z = replace(z, outside_count=z.outside_count + 1 if broken else 0)
            if z.outside_count >= p.break_closes:
                if self.allow_flip and z.flips == 0:
                    z = replace(z, role="resistance" if z.role == "support" else "support",
                                status="role_reversed", flips=1, outside_count=0)
                else:
                    z = replace(z, status="invalidated", invalid_index=index)
            self.zones[key] = z
        return tuple(self.zones.values())


@dataclass(frozen=True)
class Snapshot:
    index: int
    date: str
    prior_atr: float | None
    atr: float | None
    fixed_pivots: tuple[Pivot, ...]
    atr_pivots: tuple[Pivot, ...]
    fixed_legs: tuple[Leg, ...]
    atr_legs: tuple[Leg, ...]
    zones: dict[str, tuple[Zone, ...]]


class StructureStream:
    def __init__(self, config: Config | None = None):
        self.config = config or Config()
        p = self.config
        self.fixed = DirectionalChanges(p.fixed_reversal)
        self.adaptive = ATRChanges(p)
        self.bars: list[Bar] = []
        self.ranges: list[float] = []
        self.fixed_legs: list[Leg] = []
        self.atr_legs: list[Leg] = []
        self.r0_zones: list[Zone] = []
        self.atr_zones: list[Zone] = []
        self.density_births: list[Zone] = []
        self.support_births: list[Zone] = []
        self.density_used: set[int] = set()
        self.support_used: set[int] = set()
        self.persistence: dict[int, int] = {}
        self.books = {"r0_legacy": ZoneBook(p, None, legacy=True),
                      "atr_intersection": ZoneBook(p, p.max_age),
                      "density": ZoneBook(p, p.max_age), "support": ZoneBook(p, p.max_age),
                      "density_perpetual": ZoneBook(p, None), "density_no_flip": ZoneBook(p, p.max_age, False),
                      "support_perpetual": ZoneBook(p, None), "support_no_flip": ZoneBook(p, p.max_age, False)}

    def _intersection_zones(self, legs: list[Leg], name: str) -> list[Zone]:
        result = []
        for c in centers(legs):
            result.append(Zone(f"{name}:{c.first_leg}", name, legs[c.first_leg].start.index,
                               c.created_index, c.low, c.high, (c.low + c.high) / 2,
                               tuple(range(c.first_leg, c.last_leg + 1)),
                               structural_closed_index=c.closed_index))
        return result

    def _density(self, index: int) -> list[Zone]:
        p = self.config
        if index + 1 < p.density_window:
            return []
        step = math.log1p(p.density_bin_fraction)
        buckets: dict[int, list[int]] = {}
        for j in range(index - p.density_window + 1, index + 1):
            if j in self.density_used:
                continue
            b = math.floor(math.log(self.bars[j].close) / step)
            buckets.setdefault(b, []).append(j)
        candidates = []
        for key in sorted({k - offset for k in buckets for offset in range(p.density_span_bins)}):
            members = sorted(j for offset in range(p.density_span_bins) for j in buckets.get(key + offset, []))
            if len(members) >= p.density_min_count and members[-1] - members[0] >= p.density_min_span:
                candidates.append((key, members))
        active_keys = {key for key, _ in candidates}
        self.persistence = {key: self.persistence.get(key, 0) + 1 for key in active_keys}
        born = []
        for key, members in sorted(candidates, key=lambda pair: (-len(pair[1]), pair[0])):
            lower, upper = math.exp(key * step), math.exp((key + p.density_span_bins) * step)
            if self.persistence[key] < p.density_persistence or any(j in self.density_used for j in members):
                continue
            if any(index - old.confirmed_index <= p.birth_dedup_age and overlap(old, lower, upper) > 0.3 for old in self.density_births):
                continue
            total_volume = sum(self.bars[j].volume for j in members)
            centroid = sum(self.bars[j].close * self.bars[j].volume for j in members) / total_volume if total_volume else mean(self.bars[j].close for j in members)
            z = Zone(f"density:{key}:{index}", "density", members[0], index, lower, upper, centroid, tuple(members))
            born.append(z)
            self.density_births.append(z)
            self.density_used.update(members)
        return born

    def _support(self, index: int, new_pivot: Pivot | None) -> list[Zone]:
        if new_pivot is None or new_pivot.kind != "low":
            return []
        lows = [x for x in self.fixed.pivots if x.kind == "low"]
        if len(lows) < 2:
            return []
        a, b = lows[-2:]
        p = self.config
        if a.index in self.support_used or b.index in self.support_used:
            return []
        if not p.support_min_gap <= b.index - a.index <= p.support_max_span or b.price < a.price * (1 - p.support_low_tolerance):
            return []
        if max(x.close for x in self.bars[a.index:b.index + 1]) < a.price * (1 + p.support_rebound):
            return []
        z = Zone(f"support:{a.index}:{b.index}", "support", a.index, index,
                 min(a.price, b.price) * (1 - p.support_band_buffer),
                 max(a.price, b.price) * (1 + p.support_band_buffer), (a.price + b.price) / 2, (a.index, b.index))
        self.support_used.update(z.members)
        self.support_births.append(z)
        return [z]

    def update(self, bar: Bar) -> Snapshot:
        validate_bars([bar])
        if self.bars and bar.date <= self.bars[-1].date:
            raise ValueError("stream dates must increase")
        p, i = self.config, len(self.bars)
        prior_atr = mean(self.ranges[-p.atr_window:]) if len(self.ranges) >= p.atr_window else None
        previous_close = self.bars[-1].close if self.bars else bar.close
        self.ranges.append(max(bar.high - bar.low, abs(bar.high - previous_close), abs(bar.low - previous_close)))
        self.bars.append(bar)
        current_atr = mean(self.ranges[-p.atr_window:]) if len(self.ranges) >= p.atr_window else None
        fixed_new, atr_new = self.fixed.update(bar.close), self.adaptive.update(bar.close, prior_atr)
        if fixed_new:
            self.fixed_legs = make_legs(self.bars, self.fixed.pivots)
            self.r0_zones = self._intersection_zones(self.fixed_legs, "r0_legacy")
        if atr_new:
            self.atr_legs = make_legs(self.bars, self.adaptive.pivots)
            self.atr_zones = self._intersection_zones(self.atr_legs, "atr_intersection")
        density_new, support_new = self._density(i), self._support(i, fixed_new)
        values = {}
        for name, book in self.books.items():
            candidates = self.r0_zones if name == "r0_legacy" else self.atr_zones if name == "atr_intersection" else density_new if name.startswith("density") else support_new
            values[name] = book.update(i, bar, candidates)
        rolling = self.bars[-20:]
        if len(rolling) == 20:
            lower, upper = min(b.low for b in rolling), max(b.high for b in rolling)
            values["rolling20"] = (Zone(f"rolling20:{i}", "rolling20", i - 19, i, lower, upper,
                                        mean(b.close for b in rolling), tuple(range(i - 19, i + 1)), role="both"),)
        else:
            values["rolling20"] = ()
        return Snapshot(i, bar.date.isoformat(), prior_atr, current_atr, tuple(self.fixed.pivots),
                        tuple(self.adaptive.pivots), tuple(self.fixed_legs), tuple(self.atr_legs), values)


def reference_zone(zones: tuple[Zone, ...]) -> Zone | None:
    return max((z for z in zones if z.valid), key=lambda z: (z.confirmed_index, z.id), default=None)
