"""Presentation timing tests using synthetic bars, never human review data."""
import importlib.util
import unittest
from dataclasses import replace
from pathlib import Path
from types import SimpleNamespace

from test_research import synthetic_bars

_path = Path(__file__).resolve().parents[1] / 'research/r1/mobile_review.py'
_spec = importlib.util.spec_from_file_location('mobile_review', _path)
mobile = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(mobile)


class MobileTimingTests(unittest.TestCase):
    def test_exact_cutoff_and_future_extension_invariance(self):
        bars = synthetic_bars([100 + i / 10 for i in range(240)])
        cutoff = bars[199].date.isoformat()
        prefix = SimpleNamespace(bars=bars[:200], calendar=[b.date for b in bars[:200]])
        extended = SimpleNamespace(bars=bars, calendar=[b.date for b in bars])
        before = mobile.visible_window(prefix, cutoff)
        self.assertEqual(before, mobile.visible_window(extended, cutoff))
        self.assertEqual(before, bars[20:200])
        # An invalid future quote must not be read to build a past chart.
        extended.bars = bars[:200] + [replace(bars[200], low=-1)]
        self.assertEqual(before, mobile.visible_window(extended, cutoff))

    def test_unknown_gap_starts_new_window_without_filling(self):
        bars = synthetic_bars([100] * 25)
        dataset = SimpleNamespace(bars=bars[:10] + bars[11:], calendar=[b.date for b in bars])
        self.assertEqual(mobile.visible_window(dataset, bars[-1].date.isoformat()), bars[11:])

    def test_unavailable_cutoff_never_substitutes_latest(self):
        bars = synthetic_bars([100] * 10)
        dataset = SimpleNamespace(bars=bars[:-1], calendar=[b.date for b in bars])
        with self.assertRaisesRegex(ValueError, 'never substitute'):
            mobile.visible_window(dataset, bars[-1].date.isoformat())

    def test_zero_volume_cutoff_never_fills_or_changes_date(self):
        bars = synthetic_bars([100] * 10)
        dataset = SimpleNamespace(bars=bars[:-1] + [replace(bars[-1], volume=0)], calendar=[b.date for b in bars])
        with self.assertRaisesRegex(ValueError, 'positive-volume'):
            mobile.visible_window(dataset, bars[-1].date.isoformat())

    def test_invalid_history_rejected(self):
        bars = synthetic_bars([100])
        dataset = SimpleNamespace(bars=bars, calendar=[bars[0].date])
        with self.assertRaisesRegex(ValueError, 'history'):
            mobile.visible_window(dataset, bars[0].date.isoformat(), history=0)


if __name__ == '__main__':
    unittest.main()
