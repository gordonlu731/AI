"""Synthetic fixtures test correctness, never investment performance."""

from __future__ import annotations

import csv
import json
import math
import os
import random
import subprocess
import sys
import tempfile
import unittest
from dataclasses import asdict, replace
from datetime import date, timedelta
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))

from ashare_quant.data import Bar, adjust_bars, calendar_gaps, read_bars, sha256, validate_bars
from ashare_quant.evaluation import HORIZONS, evaluate, summarize
from ashare_quant.strategy import Assessment, Parameters, assess, assess_sessions, risk_reward
from ashare_quant.structure import DirectionalChanges, Pivot, centers, identify, make_legs, wicks


def synthetic_bars(prices, volumes=None):
    """Artificial test prices with weekday dates; no external market data."""
    days, d = [], date(2020, 1, 1)
    while len(days) < len(prices):
        if d.weekday() < 5:
            days.append(d)
        d += timedelta(days=1)
    return [Bar(days[i], float(v), float(v) * 1.01, float(v) * 0.99,
                float(v), float(volumes[i] if volumes else 100)) for i, v in enumerate(prices)]


def synthetic_signal(bars, index=0, stop=80.0, target=200.0):
    return Assessment(index, bars[index].date.isoformat(), "trend_pullback", True, True,
                      (), stop, target, stop, 5.0, {})


class DataTests(unittest.TestCase):
    def test_invalid_prices_order_and_duplicates(self):
        bars = synthetic_bars([10, 11])
        invalid = [[], bars[::-1], [bars[0], bars[0]],
                   [replace(bars[0], high=9)], [replace(bars[0], volume=-1)],
                   [replace(bars[0], adj_factor=0)], [replace(bars[0], close=math.nan)],
                   [replace(bars[0], open=math.inf)]]
        for data in invalid:
            with self.subTest(data=data), self.assertRaises(ValueError):
                validate_bars(data)

    def test_fixed_anchor_adjustment_and_prefix_invariance(self):
        raw = synthetic_bars([10, 5, 6])
        raw = [replace(b, adj_factor=f) for b, f in zip(raw, [2, 4, 4])]
        adjusted = adjust_bars(raw)
        self.assertEqual([b.close for b in adjusted], [10, 10, 12])
        self.assertEqual(adjusted[:2], adjust_bars(raw[:2]))
        self.assertEqual([b.volume for b in adjusted], [100] * 3)

    def test_calendar_detects_missing_sessions_and_foreign_dates(self):
        bars = synthetic_bars([10, 11, 12])
        self.assertEqual(calendar_gaps([bars[0], bars[2]], [b.date for b in bars]), [bars[1].date])
        with self.assertRaises(ValueError):
            calendar_gaps(bars, [bars[0].date])

    def test_csv_requires_explicit_factor(self):
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "bad.csv"
            path.write_text("date,close\n2020-01-01,10\n")
            with self.assertRaises(ValueError):
                read_bars(path)


class StructureTests(unittest.TestCase):
    def test_pivot_waits_for_confirmation(self):
        detector = DirectionalChanges(0.1)
        for close in [99, 95, 90, 94, 98]:
            self.assertIsNone(detector.update(close))
        low = detector.update(100)
        self.assertEqual(low, Pivot("low", 2, 5, 90))
        self.assertIsNone(detector.update(110))
        self.assertEqual(detector.update(98), Pivot("high", 6, 7, 110))

    def test_confirmed_pivots_do_not_repaint(self):
        bars = synthetic_bars([100, 90, 101, 115, 100, 110, 95, 108, 120, 105])
        full, _, _ = identify(bars)
        for end in range(1, len(bars) + 1):
            prefix, _, _ = identify(bars[:end])
            self.assertEqual(prefix, [p for p in full if p.confirmed_index < end])

    def test_centers_are_independent_and_update_causally(self):
        prices = [100, 120, 110, 130, 90, 80, 100, 85, 105]
        bars = synthetic_bars(prices)
        pivots = [Pivot("low" if i % 2 == 0 else "high", i, i, value) for i, value in enumerate(prices)]
        legs = make_legs(bars, pivots)
        zones = centers(legs)
        self.assertEqual([(z.low, z.high) for z in zones], [(110, 120), (85, 90)])
        self.assertLess(zones[0].last_leg, zones[1].first_leg)
        self.assertEqual(zones[0].created_index, 3)
        self.assertEqual(zones[0].closed_index, 5)
        self.assertIsNone(centers(legs[:3])[0].closed_index)

    def test_zero_width_overlap_is_not_center(self):
        prices = [100, 110, 110, 120]
        bars = synthetic_bars(prices)
        pivots = [Pivot("low", i, i, p) for i, p in enumerate(prices)]
        self.assertEqual(centers(make_legs(bars, pivots)), [])

    def test_leg_energy_uses_only_prior_volume_baseline(self):
        bars = synthetic_bars([10, 10, 11, 12, 13, 10], [100, 100, 200, 200, 10000, 1])
        pivots = [Pivot("low", 1, 2, 10), Pivot("high", 3, 5, 12)]
        leg = make_legs(bars, pivots)[0]
        self.assertEqual(leg.duration, 2)
        self.assertEqual(leg.relative_volume, 2.0)
        self.assertAlmostEqual(leg.energy, math.log(1.2))

    def test_flat_series_and_wicks(self):
        self.assertEqual(identify(synthetic_bars([10] * 30)), ([], [], []))
        b = Bar(date(2020, 1, 1), 10, 14, 6, 12, 100)
        self.assertEqual(wicks(b), (0.5, 0.25))
        self.assertEqual(wicks(replace(b, open=10, high=10, low=10, close=10)), (0, 0))


class StrategyTests(unittest.TestCase):
    def test_synthetic_positive_bottom_requires_confirmation_and_cooldown(self):
        prices = ([85] * 20 + [100] * 10 + [100 - i for i in range(1, 41)]
                  + [60 + i for i in range(1, 21)] + [80 - 19 * i / 30 for i in range(1, 31)]
                  + [62, 63, 64, 65, 66, 67])
        rows = {s.index: s for s in assess(synthetic_bars(prices, [100] * 90 + [50] * 36))
                if s.strategy == "bottom_reversal"}
        self.assertIn("unconfirmed_bottom_sequence", rows[122].reasons)
        self.assertTrue(rows[123].emitted)
        self.assertTrue(rows[124].eligible)
        self.assertEqual(rows[124].reasons, ("cooldown",))
        self.assertIn("rr_below_min", rows[125].reasons)

    def test_synthetic_positive_trend_and_insufficient_rr(self):
        prices = ([80] * 60 + [80 + 4 * i for i in range(1, 11)]
                  + [120 - 20 * i / 15 for i in range(1, 16)]
                  + [100 + 5.6 * i for i in range(1, 11)]
                  + [156 - 30 * i / 26 for i in range(1, 27)] + [128, 130, 132, 134])
        volume = [100] * 60 + [300] * 10 + [100] * 15 + [400] * 10 + [50] * 30
        bars = synthetic_bars(prices, volume)
        rows = [s for s in assess(bars) if s.strategy == "trend_pullback"]
        self.assertTrue(rows[-1].emitted)
        self.assertFalse(rows[-2].emitted)
        # This positive case also participates in the strongest no-future-data check.
        self.assertEqual(assess(bars[:124]), [s for s in assess(bars) if s.index < 124])

    def test_unknown_session_resets_structures_and_warmup(self):
        bars = synthetic_bars([100 + i % 10 for i in range(260)])
        calendar = [b.date for b in bars]
        missing = bars[:125] + bars[126:]
        rows = assess_sessions(missing, calendar)
        self.assertFalse(any(125 <= s.index < 244 for s in rows))
        self.assertTrue(any(s.index == 244 for s in rows))
        prefix = assess_sessions(missing[:250], calendar)
        self.assertEqual(prefix, [s for s in rows if s.index < 250])

    def test_negative_and_warmup_samples_are_not_signals(self):
        self.assertEqual(assess(synthetic_bars([10] * 119)), [])
        rows = assess(synthetic_bars([10] * 130))
        self.assertEqual(len(rows), 22)
        self.assertFalse(any(x.emitted for x in rows))
        self.assertIn("missing_rr", rows[0].reasons)
        self.assertIn("no_center", rows[0].reasons)

    def test_every_assessment_is_prefix_invariant(self):
        rng = random.Random(7)
        prices = [100.0]
        for _ in range(179):
            prices.append(prices[-1] * (1 + rng.uniform(-0.09, 0.09)))
        bars = synthetic_bars(prices, [rng.randint(10, 1000) for _ in prices])
        params = Parameters(min_history=30)
        full = assess(bars, params)
        for end in (30, 31, 60, 90, 120, 150, 179):
            self.assertEqual(assess(bars[:end], params), [s for s in full if s.index < end])
        changed_future = bars[:120] + [replace(b, open=b.open * 8, high=b.high * 8,
                                               low=b.low * 8, close=b.close * 8) for b in bars[120:]]
        self.assertEqual([s for s in assess(changed_future, params) if s.index < 120],
                         [s for s in full if s.index < 120])

    def test_risk_reward_rejects_invalid_geometry(self):
        self.assertEqual(risk_reward(10, 9, 12), 2)
        for geometry in [(10, 10, 12), (10, 9, 10), (10, 11, 12)]:
            self.assertIsNone(risk_reward(*geometry))

    def test_invalid_parameters_are_rejected(self):
        for args in ({"reversal": 0}, {"min_history": 0}, {"volume_window": 1.5},
                     {"pullback_min": 0.5, "pullback_max": 0.1}, {"rr_min": math.nan},
                     {"bottom_decay": 2}, {"stop_buffer": 1}):
            with self.subTest(args=args), self.assertRaises(ValueError):
                Parameters(**args)


class OutcomeTests(unittest.TestCase):
    def test_all_horizons_start_at_next_open_and_include_losses(self):
        bars = synthetic_bars([100] * 2 + [99 - i for i in range(24)])
        rows = evaluate(bars, [synthetic_signal(bars)], [b.date for b in bars])
        self.assertEqual([r.horizon for r in rows], list(HORIZONS))
        self.assertTrue(all(r.status == "observed" and r.loss for r in rows))
        self.assertEqual(rows[0].entry_date, bars[1].date.isoformat())
        self.assertEqual(rows[0].exit_date, bars[3].date.isoformat())
        self.assertAlmostEqual(rows[0].gross_return, bars[3].close / bars[1].open - 1)
        self.assertAlmostEqual(rows[0].net_return, bars[3].close * 0.999 / (bars[1].open * 1.001) - 1)
        self.assertAlmostEqual(rows[0].mae, min(b.low for b in bars[1:4]) / 100 - 1)
        self.assertEqual(summarize(rows)[0]["loss_count"], 1)

    def test_insufficient_future_is_censored_never_zero(self):
        bars = synthetic_bars([100] * 5)
        rows = evaluate(bars, [synthetic_signal(bars)], [b.date for b in bars])
        self.assertEqual(rows[0].status, "observed")
        self.assertEqual([r.status for r in rows[1:]], ["censored_horizon"] * 3)
        self.assertTrue(all(r.net_return is None for r in rows[1:]))
        last = evaluate(bars, [synthetic_signal(bars, index=4)], [b.date for b in bars])
        self.assertTrue(all(r.status == "censored_entry" for r in last))

    def test_missing_or_zero_volume_not_silently_skipped(self):
        bars = synthetic_bars([100] * 25)
        calendar = [b.date for b in bars]
        signal = synthetic_signal(bars)
        self.assertTrue(all(r.status == "window_unavailable" for r in evaluate(bars[:2] + bars[3:], [signal], calendar)))
        self.assertTrue(all(r.status == "entry_unavailable" for r in evaluate([bars[0]] + bars[2:], [signal], calendar)))
        bars[2] = replace(bars[2], volume=0)
        self.assertTrue(all(r.status == "window_unavailable" for r in evaluate(bars, [signal], calendar)))

    def test_gap_open_rechecks_rr_and_preserves_rejection(self):
        bars = synthetic_bars([100, 190] + [100] * 24)
        rows = evaluate(bars, [synthetic_signal(bars)], [b.date for b in bars])
        self.assertTrue(all(r.status == "entry_rr_rejected" for r in rows))
        self.assertTrue(all(r.net_return is None for r in rows))

    def test_existing_labels_unchanged_by_extra_future(self):
        bars = synthetic_bars([100 + i / 10 for i in range(40)])
        signals = [synthetic_signal(bars)]
        self.assertEqual(evaluate(bars[:25], signals, [b.date for b in bars[:25]]),
                         evaluate(bars, signals, [b.date for b in bars]))

    def test_empty_study_does_not_claim_zero_return(self):
        summary = summarize([])
        self.assertEqual(len(summary), 8)
        self.assertTrue(all(s["mean_net_return"] is None and s["observed"] == 0 for s in summary))

    def test_invalid_cost_or_signal_series_rejected(self):
        bars = synthetic_bars([100] * 25)
        for cost in (-0.1, math.inf, math.nan, 1):
            with self.assertRaises(ValueError):
                evaluate(bars, [], [b.date for b in bars], cost)
        with self.assertRaises(ValueError):
            evaluate(bars, [replace(synthetic_signal(bars), index=2)], [b.date for b in bars])


class CLITests(unittest.TestCase):
    def test_snapshot_guard_checksums_and_report_bundle(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            bars_path, calendar = root / "bars.csv", root / "calendar.csv"
            bars = synthetic_bars([10] * 130)
            with bars_path.open("w", newline="") as f:
                writer = csv.writer(f)
                writer.writerow(["date", "open", "high", "low", "close", "volume", "adj_factor"])
                for b in bars:
                    writer.writerow([b.date, b.open, b.high, b.low, b.close, b.volume, 1])
            calendar.write_text("date\n" + "\n".join(b.date.isoformat() for b in bars) + "\n")
            manifest = root / "manifest.json"
            manifest.write_text(json.dumps({"symbol": "SYNTHETIC", "source": "unit test only",
                "retrieved_at_utc": "2020-01-01T00:00:00Z", "adjustment": "cumulative_factor",
                "volume_unit": "shares", "redistribution": "synthetic", "point_in_time_verified": False,
                "calendar_verified": False, "sha256": sha256(bars_path), "calendar_sha256": sha256(calendar)}))
            env = {**os.environ, "PYTHONPATH": str(Path(__file__).resolve().parents[1] / "src")}
            command = [sys.executable, "-m", "ashare_quant", "research", "--bars", str(bars_path),
                       "--manifest", str(manifest), "--calendar", str(calendar), "--output", str(root / "report")]
            rejected = subprocess.run(command, env=env, capture_output=True, text=True)
            self.assertEqual(rejected.returncode, 2)
            self.assertIn("PIT", rejected.stderr)
            self.assertFalse((root / "report").exists())
            success = subprocess.run(command + ["--allow-snapshot-research"], env=env, capture_output=True, text=True)
            self.assertEqual(success.returncode, 0, success.stderr)
            self.assertEqual(len((root / "report" / "assessments.jsonl").read_text().splitlines()), 22)
            run = json.loads((root / "report" / "run.json").read_text())
            self.assertEqual(run["verification"], "UNVERIFIED_SNAPSHOT_EXPLORATION")
            self.assertFalse(run["execution_constraints_verified"])
            self.assertIn("strategy.py", run["code_sha256"])
            # A different snapshot may never reuse old provenance.
            calendar.write_text(calendar.read_text() + "2025-01-01\n")
            mismatch = subprocess.run(command, env=env, capture_output=True, text=True)
            self.assertEqual(mismatch.returncode, 2)
            self.assertIn("checksum", mismatch.stderr)


if __name__ == "__main__":
    unittest.main()
