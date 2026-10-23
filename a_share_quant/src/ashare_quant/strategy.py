"""All assessments are emitted at the current close; no future labels here."""

from __future__ import annotations

from dataclasses import asdict, dataclass, replace
from datetime import date

from .data import Bar, session_segments, validate_bars
from .structure import DirectionalChanges, centers, make_legs, wicks


@dataclass(frozen=True)
class Parameters:
    reversal: float = 0.06
    min_history: int = 120
    volume_window: int = 20
    breakout_window: int = 20
    breakout_lookback: int = 40
    breakout_volume_ratio: float = 1.5
    pullback_min: float = 0.03
    pullback_max: float = 0.15
    trend_energy_ratio: float = 1.2
    bottom_drawdown: float = 0.30
    bottom_rebound: float = 0.08
    retest_tolerance: float = 0.05
    bottom_decay: float = 0.8
    rr_min: float = 2.0
    stop_buffer: float = 0.01
    cooldown: int = 5

    def __post_init__(self):
        import math
        if not all(math.isfinite(v) for v in asdict(self).values()):
            raise ValueError("parameters must be finite")
        if not 0 < self.reversal < 1 or not 0 <= self.stop_buffer < 1:
            raise ValueError("invalid reversal or stop buffer")
        if not 0 <= self.pullback_min <= self.pullback_max < 1:
            raise ValueError("invalid pullback range")
        for key in ("min_history", "volume_window", "breakout_window", "breakout_lookback", "cooldown"):
            if not isinstance(getattr(self, key), int) or getattr(self, key) < 1:
                raise ValueError(f"{key} must be a positive integer")
        if min(self.breakout_volume_ratio, self.trend_energy_ratio, self.rr_min) <= 0:
            raise ValueError("ratios must be positive")
        if not (0 < self.bottom_drawdown < 1 and self.bottom_rebound > 0
                and 0 <= self.retest_tolerance < 1 and 0 < self.bottom_decay <= 1):
            raise ValueError("invalid bottom parameters")


@dataclass(frozen=True)
class Assessment:
    index: int
    date: str
    strategy: str
    eligible: bool
    emitted: bool
    reasons: tuple[str, ...]
    support: float | None
    resistance: float | None
    stop: float | None
    rr: float | None
    metrics: dict[str, float | int | None]


def risk_reward(entry: float, stop: float, target: float) -> float | None:
    if not 0 < stop < entry < target:
        return None
    return (target - entry) / (entry - stop)


def assess(bars: list[Bar], params: Parameters | None = None) -> list[Assessment]:
    validate_bars(bars)
    p = params or Parameters()
    detector = DirectionalChanges(p.reversal)
    result: list[Assessment] = []
    breakouts: list[int] = []
    last_emitted: dict[str, int] = {}
    for i, bar in enumerate(bars):
        detector.update(bar.close)
        if i >= max(p.breakout_window, p.volume_window):
            previous_high = max(b.high for b in bars[i - p.breakout_window:i])
            previous_volume = sum(b.volume for b in bars[i - p.volume_window:i]) / p.volume_window
            if previous_volume > 0 and bar.close > previous_high and bar.volume >= previous_volume * p.breakout_volume_ratio:
                breakouts.append(i)
        if i + 1 < p.min_history:
            continue
        pivots = detector.pivots
        legs = make_legs(bars[:i + 1], pivots, p.volume_window)
        zones = centers(legs)
        lows = [x for x in pivots if x.kind == "low"]
        highs = [x for x in pivots if x.kind == "high"]
        zone_edges = [edge for c in zones for edge in (c.low, c.high)]
        support = max((x for x in [p.price for p in lows] + zone_edges if x < bar.close), default=None)
        resistance = min((x for x in [p.price for p in highs] + zone_edges if x > bar.close), default=None)
        stop = support * (1 - p.stop_buffer) if support is not None else None
        rr = risk_reward(bar.close, stop, resistance) if stop is not None and resistance is not None else None
        up = next((x for x in reversed(legs) if x.direction == "up"), None)
        down = next((x for x in reversed(legs) if x.direction == "down"), None)
        energy_ratio = up.energy / down.energy if up and down and down.energy > 0 else None
        pullback = 1 - bar.close / max(b.close for b in bars[max(0, i - 59):i + 1])
        lower_wick, upper_wick = wicks(bar)
        metrics = {"pivots": len(pivots), "centers": len(zones), "energy_ratio": energy_ratio,
                   "pullback": pullback, "lower_wick": lower_wick, "upper_wick": upper_wick}
        common = {"zero_volume": bar.volume > 0, "missing_rr": rr is not None,
                  "rr_below_min": rr is not None and rr >= p.rr_min}
        trend = {
            **common,
            "lows_not_rising": len(lows) >= 2 and lows[-1].price > lows[-2].price,
            "highs_not_rising": len(highs) >= 2 and highs[-1].price > highs[-2].price,
            "no_prior_volume_breakout": any(i - p.breakout_lookback <= x < i for x in breakouts),
            "pullback_outside_range": p.pullback_min <= pullback <= p.pullback_max,
            "up_energy_insufficient": energy_ratio is not None and energy_ratio >= p.trend_energy_ratio,
            "no_center": bool(zones),
            "latest_low_broken": bool(lows) and bar.close >= lows[-1].price,
        }
        bottom = {**common, "unconfirmed_bottom_sequence": False, "not_deep_decline": False,
                  "weak_first_rebound": False, "retest_outside_band": False,
                  "selling_not_decaying": False, "recovery_not_confirmed": False}
        if len(pivots) >= 4 and [x.kind for x in pivots[-4:]] == ["high", "low", "high", "low"]:
            h0, l1, h1, l2 = pivots[-4:]
            # Peak must precede the first bottom; do not use the later rebound as its peak.
            history_peak = max(b.close for b in bars[max(0, i - 119):l1.index + 1]) if l1.index >= max(0, i - 119) else None
            first_down, second_down = legs[-3], legs[-1]
            bottom.update({
                "unconfirmed_bottom_sequence": True,
                "not_deep_decline": history_peak is not None and 1 - l1.price / history_peak >= p.bottom_drawdown,
                "weak_first_rebound": h1.price / l1.price - 1 >= p.bottom_rebound,
                "retest_outside_band": abs(l2.price / l1.price - 1) <= p.retest_tolerance,
                "selling_not_decaying": first_down.energy > 0 and second_down.energy <= first_down.energy * p.bottom_decay,
                "recovery_not_confirmed": bar.close >= l2.price * (1 + p.reversal) and bar.close > bars[i - 1].close,
            })
        for name, checks in (("trend_pullback", trend), ("bottom_reversal", bottom)):
            reasons = tuple(k for k, ok in checks.items() if not ok)
            eligible = not reasons
            emitted = eligible and i - last_emitted.get(name, -p.cooldown) >= p.cooldown
            if emitted:
                last_emitted[name] = i
            elif eligible:
                reasons = ("cooldown",)
            result.append(Assessment(i, bar.date.isoformat(), name, eligible, emitted, reasons,
                                     support, resistance, stop, rr, dict(metrics)))
    return result


def assess_sessions(bars: list[Bar], calendar: list[date], params: Parameters | None = None) -> list[Assessment]:
    """Never carry structures through missing/zero-volume sessions."""
    result = []
    for first, end in session_segments(bars, calendar):
        result.extend(replace(s, index=s.index + first) for s in assess(bars[first:end], params))
    return result
