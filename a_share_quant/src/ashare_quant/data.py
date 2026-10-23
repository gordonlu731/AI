"""Strict daily-bar contract. Prices remain raw until explicitly adjusted."""

from __future__ import annotations

import csv
import hashlib
import math
from dataclasses import dataclass, replace
from datetime import date
from pathlib import Path


@dataclass(frozen=True)
class Bar:
    date: date
    open: float
    high: float
    low: float
    close: float
    volume: float  # shares, never vendor 'lots'
    adj_factor: float = 1.0


def validate_bars(bars: list[Bar]) -> None:
    if not bars:
        raise ValueError("empty daily series")
    for i, b in enumerate(bars):
        if i and b.date <= bars[i - 1].date:
            raise ValueError("dates must be unique and strictly increasing")
        values = (b.open, b.high, b.low, b.close, b.volume, b.adj_factor)
        if not all(math.isfinite(v) for v in values):
            raise ValueError(f"non-finite value on {b.date}")
        if min(b.open, b.high, b.low, b.close, b.adj_factor) <= 0 or b.volume < 0:
            raise ValueError(f"invalid price/factor/volume on {b.date}")
        if not b.low <= min(b.open, b.close) <= max(b.open, b.close) <= b.high:
            raise ValueError(f"inconsistent OHLC on {b.date}")


def read_bars(path: str | Path) -> list[Bar]:
    with Path(path).open(newline="", encoding="utf-8") as f:
        rows = csv.DictReader(f)
        required = {"date", "open", "high", "low", "close", "volume", "adj_factor"}
        if not required.issubset(rows.fieldnames or []):
            raise ValueError(f"missing columns: {required - set(rows.fieldnames or [])}")
        bars = [Bar(date.fromisoformat(r["date"]), **{
            key: float(r[key]) for key in required - {"date"}
        }) for r in rows]
    validate_bars(bars)
    return bars


def adjust_bars(raw: list[Bar]) -> list[Bar]:
    """Fixed first-bar anchor: extending the series never rescales its past."""
    validate_bars(raw)
    anchor = raw[0].adj_factor
    return [replace(b, **{key: getattr(b, key) * b.adj_factor / anchor
                          for key in ("open", "high", "low", "close")},
                    adj_factor=1.0) for b in raw]


def read_calendar(path: str | Path) -> list[date]:
    with Path(path).open(newline="", encoding="utf-8") as f:
        days = [date.fromisoformat(r["date"]) for r in csv.DictReader(f)]
    if not days or days != sorted(set(days)):
        raise ValueError("calendar must be nonempty, sorted and unique")
    return days


def calendar_gaps(bars: list[Bar], calendar: list[date]) -> list[date]:
    known = {b.date for b in bars}
    sessions = set(calendar)
    if any(b.date not in sessions for b in bars):
        raise ValueError("daily bars contain dates outside the supplied calendar")
    return [d for d in calendar if bars[0].date <= d <= bars[-1].date and d not in known]


def sha256(path: str | Path) -> str:
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def session_segments(bars: list[Bar], calendar: list[date]) -> list[tuple[int, int]]:
    """Half-open contiguous, positive-volume ranges; unknown gaps reset history."""
    validate_bars(bars)
    if not calendar or calendar != sorted(set(calendar)):
        raise ValueError("calendar must be sorted and unique")
    calendar_gaps(bars, calendar)
    positions = {d: i for i, d in enumerate(calendar)}
    segments, first = [], None
    for i, b in enumerate(bars):
        if b.volume <= 0:
            if first is not None:
                segments.append((first, i))
                first = None
            continue
        if first is None:
            first = i
        elif positions[b.date] != positions[bars[i - 1].date] + 1:
            segments.append((first, i))
            first = i
    if first is not None:
        segments.append((first, len(bars)))
    return segments
