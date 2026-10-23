"""Forward outcome labels, deliberately separate from signal generation.

These are overlapping event studies, not a portfolio or an execution simulator.
"""

from __future__ import annotations

import math
from collections import Counter
from dataclasses import asdict, dataclass
from datetime import date
from statistics import mean, median

from .data import Bar, calendar_gaps, validate_bars
from .strategy import Assessment, risk_reward

HORIZONS = (3, 5, 10, 20)


@dataclass(frozen=True)
class Outcome:
    signal_date: str
    strategy: str
    horizon: int
    status: str
    entry_date: str | None = None
    exit_date: str | None = None
    entry_price: float | None = None
    entry_rr: float | None = None
    gross_return: float | None = None
    net_return: float | None = None
    mae: float | None = None
    mfe: float | None = None
    close_max_drawdown: float | None = None
    loss: bool | None = None


def evaluate(bars: list[Bar], assessments: list[Assessment], calendar: list[date],
             cost_per_side: float = 0.001, rr_min: float = 2.0) -> list[Outcome]:
    validate_bars(bars)
    if not math.isfinite(cost_per_side) or not 0 <= cost_per_side < 1:
        raise ValueError("cost_per_side must be finite in [0, 1)")
    if not math.isfinite(rr_min) or rr_min <= 0:
        raise ValueError("rr_min must be finite and positive")
    if not calendar or calendar != sorted(set(calendar)):
        raise ValueError("calendar must be sorted and unique")
    calendar_gaps(bars, calendar)  # also rejects dates outside the calendar
    by_date = {b.date: b for b in bars}
    positions = {d: i for i, d in enumerate(calendar)}
    output = []
    for signal in (s for s in assessments if s.emitted):
        if signal.index >= len(bars) or signal.index < 0 or bars[signal.index].date.isoformat() != signal.date:
            raise ValueError("assessment does not match the supplied bar series")
        position = positions[date.fromisoformat(signal.date)] + 1
        for horizon in HORIZONS:
            base = {"signal_date": signal.date, "strategy": signal.strategy, "horizon": horizon}
            if position >= len(calendar) or calendar[position] > bars[-1].date:
                output.append(Outcome(**base, status="censored_entry"))
                continue
            entry_day = calendar[position]
            entry = by_date.get(entry_day)
            if entry is None or entry.volume <= 0:
                output.append(Outcome(**base, status="entry_unavailable", entry_date=entry_day.isoformat()))
                continue
            rr = risk_reward(entry.open, signal.stop, signal.resistance) if signal.stop is not None and signal.resistance is not None else None
            entry_base = {**base, "entry_date": entry_day.isoformat(), "entry_price": entry.open, "entry_rr": rr}
            if rr is None or rr < rr_min:
                output.append(Outcome(**entry_base, status="entry_rr_rejected"))
                continue
            end = position + horizon - 1
            if end >= len(calendar) or calendar[end] > bars[-1].date:
                output.append(Outcome(**entry_base, status="censored_horizon"))
                continue
            days = calendar[position:end + 1]
            if any(d not in by_date or by_date[d].volume <= 0 for d in days):
                output.append(Outcome(**entry_base, status="window_unavailable", exit_date=calendar[end].isoformat()))
                continue
            window = [by_date[d] for d in days]
            gross = window[-1].close / entry.open - 1
            net = window[-1].close * (1 - cost_per_side) / (entry.open * (1 + cost_per_side)) - 1
            peak, drawdown = entry.open, 0.0
            for b in window:
                peak = max(peak, b.close)
                drawdown = min(drawdown, b.close / peak - 1)
            output.append(Outcome(**entry_base, status="observed", exit_date=window[-1].date.isoformat(),
                                  gross_return=gross, net_return=net,
                                  mae=min(0.0, min(b.low for b in window) / entry.open - 1),
                                  mfe=max(0.0, max(b.high for b in window) / entry.open - 1),
                                  close_max_drawdown=drawdown, loss=net < 0))
    return output


def summarize(outcomes: list[Outcome]) -> list[dict]:
    summaries = []
    for strategy in ("trend_pullback", "bottom_reversal"):
        for horizon in HORIZONS:
            rows = [o for o in outcomes if o.strategy == strategy and o.horizon == horizon]
            observed = [o for o in rows if o.status == "observed"]
            returns = [o.net_return for o in observed]
            summaries.append({
                "strategy": strategy, "horizon": horizon, "events": len(rows),
                "observed": len(observed), "status_counts": dict(Counter(o.status for o in rows)),
                "mean_net_return": mean(returns) if returns else None,
                "median_net_return": median(returns) if returns else None,
                "win_rate": mean(r > 0 for r in returns) if returns else None,
                "loss_count": sum(o.loss for o in observed),
                "worst_net_return": min(returns) if returns else None,
                "worst_mae": min(o.mae for o in observed) if observed else None,
                "mean_mfe": mean(o.mfe for o in observed) if observed else None,
                "worst_close_drawdown": min(o.close_max_drawdown for o in observed) if observed else None,
            })
    return summaries
