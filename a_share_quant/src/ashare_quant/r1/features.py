"""Separate causal descriptors; no assumed buy/sell volume and no weighted score."""
from __future__ import annotations

from statistics import mean

from ..data import Bar
from ..structure import Leg, Pivot, wicks
from .structures import Config, Snapshot, reference_zone

FEATURE_GROUPS = {
    "wave_size_speed": ["up_abs_return", "down_abs_return", "up_duration", "down_duration", "up_speed", "down_speed"],
    "wave_volume_efficiency": ["up_relative_volume", "down_relative_volume", "up_efficiency", "down_efficiency"],
    "retracement": ["retracement", "drawdown20", "rebound20"],
    "center_damage": ["center_damage", "lower_damage", "close_to_centroid", "band_width"],
    "wicks_close": ["lower_wick", "upper_wick", "close_location"],
    "reclaim": ["breach_age", "reclaim_sessions", "reclaim_fraction"],
    "round_changes": ["up_size_change", "down_size_change", "up_speed_change", "down_speed_change", "up_volume_change", "down_volume_change"],
    "center_lifecycle": ["zone_present", "zone_age", "zone_tests", "zone_flips", "recent_invalidations"],
    "bottom_shape": ["bottom_shape", "bottom_depth", "first_rebound", "second_low_difference", "bottom_confirmation_age"],
}


def ratio(a, b):
    return a / b if a is not None and b is not None and b != 0 else None


def leg_values(bars: list[Bar], leg: Leg | None) -> dict:
    if leg is None:
        return {k: None for k in ("abs_return", "duration", "speed", "relative_volume", "efficiency")}
    relative = []
    for j in range(leg.start.index + 1, leg.end.index + 1):
        if j < 20:
            continue
        baseline = mean(b.volume for b in bars[j - 20:j])
        if baseline > 0:
            relative.append(bars[j].volume / baseline)
    magnitude = abs(leg.end.price / leg.start.price - 1)
    volume = mean(relative) if relative else None
    return {"abs_return": magnitude, "duration": leg.duration, "speed": magnitude / leg.duration,
            "relative_volume": volume, "efficiency": ratio(magnitude, volume)}


def bottom_state(bars: list[Bar], pivots: tuple[Pivot, ...], config: Config) -> dict:
    i = len(bars) - 1
    latest = None
    for j in range(len(pivots) - 2):
        triple = pivots[j:j + 3]
        if [p.kind for p in triple] == ["low", "high", "low"]:
            latest = triple
    data = {"phase": "no_confirmed_double_bottom", "bottom_shape": 0, "bottom_depth": None,
            "first_rebound": None, "second_low_difference": None, "bottom_confirmation_age": None,
            "first_low_index": None, "rebound_index": None, "second_low_index": None,
            "second_low_confirmed_index": None, "reasons": ["no_confirmed_low_high_low"]}
    if latest is None:
        if pivots:
            data["phase"] = "first_low_confirmed" if pivots[-1].kind == "low" else "rebound_or_downswing_pending"
        return data
    a, h, b = latest
    peak = max(x.close for x in bars[max(0, a.index - 119):a.index + 1])
    conditions = {"retest_outside_band": abs(b.price / a.price - 1) <= config.bottom_tolerance,
                  "first_rebound_too_small": h.price / a.price - 1 >= config.bottom_rebound,
                  "bottoms_too_close": b.index - a.index >= config.bottom_min_gap,
                  "confirmation_stale": i - b.confirmed_index <= 20,
                  "second_low_broken": bars[-1].close >= b.price}
    rejected = [key for key, passed in conditions.items() if not passed]
    data.update({"phase": "second_low_confirmed" if not rejected else "confirmed_shape_rejected",
                 "bottom_shape": int(not rejected), "bottom_depth": 1 - a.price / peak,
                 "first_rebound": h.price / a.price - 1, "second_low_difference": b.price / a.price - 1,
                 "bottom_confirmation_age": i - b.confirmed_index, "first_low_index": a.index,
                 "rebound_index": h.index, "second_low_index": b.index,
                 "second_low_confirmed_index": b.confirmed_index, "reasons": rejected})
    return data


def feature_row(bars: list[Bar], snapshot: Snapshot, method: str, config: Config,
                benchmark_momentum20: float | None = None) -> dict:
    i, bar = len(bars) - 1, bars[-1]
    legs = snapshot.atr_legs if method == "atr_intersection" else snapshot.fixed_legs
    pivots = snapshot.atr_pivots if method == "atr_intersection" else snapshot.fixed_pivots
    ups, downs = [x for x in legs if x.direction == "up"], [x for x in legs if x.direction == "down"]
    u, d = (ups[-1] if ups else None), (downs[-1] if downs else None)
    up, down = leg_values(bars, u), leg_values(bars, d)
    previous_up = next((x for x in reversed(ups) if d is not None and x.end.index <= d.start.index), None)
    previous_up_values = leg_values(bars, previous_up)
    lower, upper = wicks(bar)
    zone = reference_zone(snapshot.zones[method])
    bottom = bottom_state(bars, pivots, config)
    row = {"momentum20": bar.close / bars[i - 20].close - 1 if i >= 20 else None,
           "atr_fraction": ratio(snapshot.atr, bar.close), "benchmark_momentum20": benchmark_momentum20,
           "drawdown20": 1 - bar.close / max(x.close for x in bars[-20:]),
           "rebound20": bar.close / min(x.close for x in bars[-20:]) - 1,
           "lower_wick": lower, "upper_wick": upper,
           "close_location": (bar.close - bar.low) / (bar.high - bar.low) if bar.high > bar.low else 0.5,
           "retracement": ratio(down["abs_return"], previous_up_values["abs_return"]),
           "zone_present": int(zone is not None), "zone_age": i - zone.confirmed_index if zone else None,
           "zone_tests": zone.independent_tests if zone else None, "zone_flips": zone.flips if zone else None,
           "center_damage": max(0, 1 - bar.close / zone.centroid) if zone else None,
           "lower_damage": max(0, 1 - bar.close / zone.lower) if zone else None,
           "close_to_centroid": bar.close / zone.centroid - 1 if zone else None,
           "band_width": zone.upper / zone.lower - 1 if zone else None,
           "breach_age": i - zone.breach_index if zone and zone.breach_index is not None else None,
           "reclaim_sessions": zone.reclaim_sessions if zone else None,
           "reclaim_fraction": zone.reclaim_fraction if zone else None,
           "recent_invalidations": sum(z.invalid_index is not None and 0 <= i - z.invalid_index <= 20 for z in snapshot.zones[method]),
           **{k: bottom[k] for k in FEATURE_GROUPS["bottom_shape"]}}
    for prefix, values in (("up", up), ("down", down)):
        row.update({f"{prefix}_{key}": value for key, value in values.items()})
    for prefix, sequence, last in (("up", ups, up), ("down", downs, down)):
        previous = leg_values(bars, sequence[-2] if len(sequence) >= 2 else None)
        for key, field in (("size", "abs_return"), ("speed", "speed"), ("volume", "relative_volume")):
            row[f"{prefix}_{key}_change"] = ratio(last[field], previous[field])
        # Explicit round histories, not a fitted aggregate score.
        row[f"{prefix}_last_three"] = [leg_values(bars, leg) for leg in sequence[-3:]]
    return row


def barriers(bars: list[Bar], snapshot: Snapshot, method: str) -> tuple[float | None, float | None]:
    close = bars[-1].close
    zone = reference_zone(snapshot.zones[method])
    lower = zone.lower if zone and zone.lower < close else None
    valid = [z for z in snapshot.zones[method] if z.valid]
    upper_candidates = [z.lower for z in valid if z.lower > close] + [z.upper for z in valid if z.upper > close]
    if method != "rolling20":
        pivots = snapshot.atr_pivots if method == "atr_intersection" else snapshot.fixed_pivots
        upper_candidates += [p.price for p in pivots if p.kind == "high" and p.price > close]
    return lower, min(upper_candidates, default=None)


def explain_r0_bottom(bars, pivots, legs, assessment) -> dict:
    """Mirror frozen R0 predicates for explanation, checked against its reasons."""
    i = len(bars) - 1
    info = {"has_required_last_four": [p.kind for p in pivots[-4:]] == ["high", "low", "high", "low"],
            "last_pivot_kinds": [p.kind for p in pivots[-6:]], "rejections": list(assessment.reasons),
            "emitted": assessment.emitted, "eligible": assessment.eligible, "rr": assessment.rr,
            "required_rr": 2.0, "values": None}
    if info["has_required_last_four"]:
        h0, a, h, b = pivots[-4:]
        start = max(0, i - 119)
        peak = max(x.close for x in bars[start:a.index + 1]) if a.index >= start else None
        first_down, second_down = legs[-3], legs[-1]
        info["values"] = {"drawdown": 1 - a.price / peak if peak else None, "required_drawdown": 0.30,
                          "first_rebound": h.price / a.price - 1, "required_rebound": 0.08,
                          "second_low_difference": b.price / a.price - 1, "allowed_absolute_difference": 0.05,
                          "down_energy_ratio": ratio(second_down.energy, first_down.energy), "maximum_ratio": 0.8,
                          "close_over_second_low": bars[-1].close / b.price - 1, "required_recovery": 0.06,
                          "close_rising": bars[-1].close > bars[-2].close}
    return info
