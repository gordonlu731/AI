"""Date-aligned event labels and honest daily-bar touch ordering."""
from __future__ import annotations

from datetime import date

from ..data import Bar

HORIZONS = (3, 5, 10, 20)


def split_name(day: date, calendar: list[date], splits: dict) -> str:
    position = {d: i for i, d in enumerate(calendar)}[day]
    if splits["sealed_test"][0] <= day.isoformat() <= splits["sealed_test"][1]:
        return "sealed_test"
    for name in ("train", "validation"):
        start, end = map(date.fromisoformat, splits[name])
        if start <= day <= end:
            first = next((i for i, d in enumerate(calendar) if d >= start), len(calendar))
            last = max((i for i, d in enumerate(calendar) if d <= end), default=-1)
            if name == "validation" and position < first + splits["embargo_sessions"]:
                return "embargo"
            if position > last - splits["purge_sessions"]:
                return "purged"
            return name
    return "outside_split"


def first_touch(window: list[Bar], lower: float | None, upper: float | None) -> tuple[str, str | None]:
    if lower is None or upper is None or lower >= upper:
        return "missing_barriers", None
    for bar in window:
        if bar.open >= upper:
            return "upper_first", bar.date.isoformat()
        if bar.open <= lower:
            return "lower_first", bar.date.isoformat()
        above, below = bar.high >= upper, bar.low <= lower
        if above and below:
            return "ambiguous", bar.date.isoformat()
        if above:
            return "upper_first", bar.date.isoformat()
        if below:
            return "lower_first", bar.date.isoformat()
    return "neither", None


def event_labels(bars: list[Bar], benchmark: list[Bar], calendar: list[date], day: date,
                 lower: float | None, upper: float | None, cost_per_side=0.001) -> list[dict]:
    if not 0 <= cost_per_side < 1:
        raise ValueError("invalid costs")
    if calendar != sorted(set(calendar)) or day not in calendar:
        raise ValueError("invalid calendar/signal date")
    by_date, index_by_date = {b.date: b for b in bars}, {b.date: b for b in benchmark}
    if day not in by_date:
        raise ValueError("signal day missing")
    entry_position = calendar.index(day) + 1
    result = []
    for horizon in HORIZONS:
        row = {"horizon": horizon, "status": None, "return": None, "net_return": None, "benchmark_return": None,
               "excess_return": None, "mae": None, "mfe": None, "path_drawdown": None,
               "touch_order": "not_observed", "touch_date": None, "entry_date": None, "exit_date": None}
        end = entry_position + horizon - 1
        if entry_position >= len(calendar) or calendar[entry_position] > bars[-1].date:
            row["status"] = "censored_entry"
        elif calendar[entry_position] not in by_date or by_date[calendar[entry_position]].volume <= 0:
            row.update(status="entry_unavailable", entry_date=calendar[entry_position].isoformat())
        elif end >= len(calendar) or calendar[end] > bars[-1].date:
            row.update(status="censored_horizon", entry_date=calendar[entry_position].isoformat())
        else:
            days = calendar[entry_position:end + 1]
            row.update(entry_date=days[0].isoformat(), exit_date=days[-1].isoformat())
            if any(d not in by_date or by_date[d].volume <= 0 for d in days):
                row["status"] = "window_unavailable"
            else:
                window = [by_date[d] for d in days]
                entry = window[0].open
                gross = window[-1].close / entry - 1
                net = window[-1].close * (1 - cost_per_side) / (entry * (1 + cost_per_side)) - 1
                peak, drawdown = entry, 0.0
                for b in window:
                    peak = max(peak, b.close)
                    drawdown = min(drawdown, b.close / peak - 1)
                order, touched = first_touch(window, lower, upper)
                benchmark_return = index_by_date[days[-1]].close / index_by_date[days[0]].open - 1 if all(d in index_by_date for d in days) else None
                row.update(status="observed", **{"return": gross}, net_return=net,
                           benchmark_return=benchmark_return, excess_return=net - benchmark_return if benchmark_return is not None else None,
                           mae=min(0.0, min(b.low for b in window) / entry - 1),
                           mfe=max(0.0, max(b.high for b in window) / entry - 1), path_drawdown=drawdown,
                           touch_order=order, touch_date=touched)
        result.append(row)
    return result
