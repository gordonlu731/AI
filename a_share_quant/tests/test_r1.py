"""R1 synthetic invariants and timing tests; fixtures are not market evidence."""
import sys
from dataclasses import asdict, replace
from datetime import date
from pathlib import Path
import unittest
import importlib.util

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))
from test_research import synthetic_bars
from ashare_quant.r1.structures import ATRChanges, Config, StructureStream, Zone, ZoneBook
from ashare_quant.r1.features import bottom_state, feature_row
from ashare_quant.r1.outcomes import event_labels, first_touch, split_name
from ashare_quant.structure import identify
from ashare_quant.r1.review import review_scores, render_chart


class R1StructureTests(unittest.TestCase):
    def test_atr_threshold_frozen_at_extreme(self):
        engine = ATRChanges(Config())
        engine.update(100, 5)
        # Later tiny ATR must not retroactively lower the 10% threshold.
        self.assertIsNone(engine.update(95, 0.1))
        self.assertIsNone(engine.update(94, 0.1))
        high = engine.update(90, 0.1)
        self.assertEqual((high.kind, high.index, high.confirmed_index), ("high", 0, 3))

    def test_all_methods_features_prefix_invariance(self):
        prices = [100 + 7 * __import__('math').sin(i / 4) + i / 20 for i in range(180)]
        bars = synthetic_bars(prices)
        stream = StructureStream()
        snapshots, features = [], []
        for b in bars:
            s = stream.update(b)
            snapshots.append(s)
            features.append({m: feature_row(stream.bars, s, m, stream.config) for m in s.zones})
        frozen = asdict(snapshots[99])
        for end in [40, 60, 100, 150]:
            other = StructureStream()
            for b in bars[:end]:
                prefix = other.update(b)
            self.assertEqual(prefix, snapshots[end - 1])
            self.assertEqual({m: feature_row(other.bars, prefix, m, other.config) for m in prefix.zones}, features[end - 1])
        self.assertEqual(asdict(snapshots[99]), frozen)

    def test_r0_legacy_matches_frozen_r0_geometry(self):
        bars = synthetic_bars([100 + 15 * __import__('math').sin(i / 8) + i / 10 for i in range(200)])
        stream = StructureStream()
        for b in bars:
            snapshot = stream.update(b)
        pivots, _, zones = identify(bars)
        self.assertEqual(snapshot.fixed_pivots, tuple(pivots))
        self.assertEqual([(z.lower, z.upper) for z in snapshot.zones['r0_legacy']], [(z.low, z.high) for z in zones])

    def test_density_members_not_reused_and_confirmation_delayed(self):
        bars = synthetic_bars([100 + i % 3 / 10 for i in range(150)])
        stream = StructureStream()
        born = {}
        for b in bars:
            snapshot = stream.update(b)
            for z in snapshot.zones['density']:
                born[z.id] = z
        self.assertTrue(born)
        seen = set()
        for z in born.values():
            self.assertFalse(seen & set(z.members))
            self.assertGreaterEqual(z.confirmed_index, 41)
            self.assertLessEqual(max(z.members), z.confirmed_index)
            self.assertTrue(z.lower <= z.centroid <= z.upper)
            seen.update(z.members)

    def test_policy_ablation_keeps_same_births(self):
        stream = StructureStream()
        for b in synthetic_bars([100 + i % 2 for i in range(160)]):
            s = stream.update(b)
        signatures = [set((z.id, z.confirmed_index, z.lower, z.upper) for z in s.zones[m])
                      for m in ['density', 'density_no_flip', 'density_perpetual']]
        self.assertEqual(signatures[0], signatures[1])
        self.assertEqual(signatures[0], signatures[2])

    def test_no_center_is_valid_output(self):
        stream = StructureStream()
        for b in synthetic_bars([100 + i * 5 for i in range(50)]):
            s = stream.update(b)
        self.assertFalse(s.zones['support'])
        self.assertFalse(s.zones['density'])

    def test_support_requires_second_low_confirmation(self):
        bars = synthetic_bars([110] * 30 + [115, 120, 110, 100, 104, 110, 120, 111, 102, 105, 107, 109])
        stream = StructureStream()
        counts = []
        for b in bars:
            s = stream.update(b)
            counts.append(len(s.zones['support']))
        self.assertEqual(counts[-2], 0)
        self.assertEqual(counts[-1], 1)
        z = s.zones['support'][0]
        self.assertEqual(z.confirmed_index, len(bars) - 1)
        self.assertEqual(z.members, (33, 38))

    def test_expiry_and_role_conversion_are_terminal_or_explicit(self):
        p = Config(max_age=3)
        zone = Zone('z', 'density', 0, 0, 95, 105, 100, (0,))
        bars = synthetic_bars([102, 90, 90, 110, 110])
        book = ZoneBook(p, max_age=None)
        states = [book.update(i, b, [zone] if i == 0 else [])[0] for i, b in enumerate(bars)]
        self.assertEqual(states[2].status, 'role_reversed')
        self.assertEqual(states[2].role, 'resistance')
        self.assertEqual(states[4].status, 'invalidated')
        self.assertEqual(states[0].status, 'active')
        expiry = ZoneBook(p, max_age=3)
        for i, b in enumerate(synthetic_bars([100] * 7)):
            result = expiry.update(i, b, [zone] if i == 0 else [])[0]
        self.assertEqual((result.status, result.invalid_index), ('expired', 4))
        no_flip = ZoneBook(p, max_age=None, allow_flip=False)
        for i, b in enumerate(bars[:3]):
            result = no_flip.update(i, b, [zone] if i == 0 else [])[0]
        self.assertEqual(result.status, 'invalidated')

    def test_reclaim_uses_only_observed_closes(self):
        book = ZoneBook(Config(), max_age=None, legacy=True)
        zone = Zone('z', 'density', 0, 0, 95, 105, 100, (0,))
        for i, b in enumerate(synthetic_bars([100, 94, 96, 101])):
            z = book.update(i, b, [zone] if i == 0 else [])[0]
        self.assertEqual(z.reclaim_sessions, 2)
        self.assertAlmostEqual(z.reclaim_fraction, 101 / 95 - 1)

    def test_invalidated_atr_zone_geometry_is_frozen(self):
        book = ZoneBook(Config(), max_age=None, allow_flip=False)
        z = Zone('a', 'atr_intersection', 0, 0, 95, 105, 100, (0, 1, 2))
        for i, b in enumerate(synthetic_bars([100, 90, 90])):
            last = book.update(i, b, [z] if i == 0 else [])[0]
        self.assertEqual(last.status, 'invalidated')
        updated = replace(z, lower=99, upper=101, centroid=100, members=(0, 1, 2, 3))
        frozen = book.update(3, synthetic_bars([100, 90, 90, 100])[-1], [updated])[0]
        self.assertEqual(frozen, last)

    def test_invalid_config_is_rejected(self):
        for args in [{'atr_window': 0}, {'density_window': 1}, {'atr_fraction_floor': 0.5}, {'max_age': 1.5}]:
            with self.subTest(args=args), self.assertRaises(ValueError):
                Config(**args)


class R1OutcomeTests(unittest.TestCase):
    def test_daily_order_ambiguous_not_guessed_from_close(self):
        b = synthetic_bars([100])[0]
        both = replace(b, low=85, high=115, close=110)
        self.assertEqual(first_touch([both], 90, 110)[0], 'ambiguous')
        self.assertEqual(first_touch([replace(both, open=112)], 90, 110)[0], 'upper_first')
        self.assertEqual(first_touch([replace(both, open=88)], 90, 110)[0], 'lower_first')
        self.assertEqual(first_touch([b], None, 110)[0], 'missing_barriers')
        self.assertEqual(first_touch([b], 90, 110)[0], 'neither')

    def test_labels_benchmark_alignment_and_censoring(self):
        bars = synthetic_bars([100, 100, 99, 98, 97, 96])
        benchmark = synthetic_bars([100, 100, 101, 102, 103, 104])
        rows = event_labels(bars, benchmark, [b.date for b in bars], bars[0].date, 90, 110)
        self.assertAlmostEqual(rows[0]['return'], -0.02)
        self.assertAlmostEqual(rows[0]['benchmark_return'], 0.02)
        self.assertAlmostEqual(rows[0]['excess_return'], rows[0]['net_return'] - 0.02)
        self.assertEqual(rows[2]['status'], 'censored_horizon')
        self.assertIsNone(rows[2]['return'])

    def test_gap_not_shifted_to_next_observation(self):
        bars = synthetic_bars([100] * 25)
        calendar = [b.date for b in bars]
        rows = event_labels(bars[:2] + bars[3:], bars, calendar, bars[0].date, 90, 110)
        self.assertTrue(all(r['status'] == 'window_unavailable' for r in rows))

    def test_splits_purge_embargo_and_sealed(self):
        from datetime import timedelta
        days = [date(2019, 1, 1) + timedelta(days=i) for i in range(2600)]
        splits = {'train': ['2010-01-01', '2020-12-31'], 'validation': ['2021-01-01', '2023-12-31'],
                  'sealed_test': ['2024-01-01', '2026-10-22'], 'purge_sessions': 20, 'embargo_sessions': 20}
        self.assertEqual(split_name(date(2020, 12, 30), days, splits), 'purged')
        self.assertEqual(split_name(date(2021, 1, 10), days, splits), 'embargo')
        self.assertEqual(split_name(date(2021, 6, 1), days, splits), 'validation')
        self.assertEqual(split_name(date(2024, 1, 1), days, splits), 'sealed_test')


class HumanReviewTests(unittest.TestCase):
    def test_chart_rejects_future_bars_before_loading_plotting_library(self):
        stream = StructureStream()
        bars = synthetic_bars([100] * 25)
        for b in bars[:20]:
            snapshot = stream.update(b)
        with self.assertRaises(ValueError):
            render_chart(bars, snapshot, Path('/tmp/never-render-future'), 'as-of guard test')

    def test_pending_human_is_not_zero_error(self):
        result = review_scores([{'case_id': 'B001', 'reviewed': 'no'}], [])
        self.assertEqual(result['status'], 'pending_real_human_annotations')
        self.assertEqual(result['comparisons'], [])

    def test_real_regions_report_location_and_count_errors(self):
        human = [{'case_id': 'B001', 'reviewed': 'yes', 'no_center': 'no', 'lower': '90', 'upper': '110', 'centroid': '100'}]
        algorithm = [{'case_id': 'B001', 'algorithm_label': 'A', 'zone_id': 'masked1', 'lower': '95', 'upper': '115', 'centroid': '105', 'atr_units': '5'}]
        result = review_scores(human, algorithm)
        comparison = result['comparisons'][0]
        self.assertAlmostEqual(comparison['matches'][0]['iou'], 15 / 25)
        self.assertEqual(comparison['matches'][0]['centroid_error_atr'], 1)
        self.assertEqual(len(result['errors']), 3)  # Other algorithms have an omission.

    def test_no_center_preserves_algorithm_false_detection(self):
        human = [{'case_id': 'B001', 'reviewed': 'yes', 'no_center': 'yes'}]
        algorithm = [{'case_id': 'B001', 'algorithm_label': 'A', 'zone_id': 'masked1', 'lower': '95', 'upper': '115', 'centroid': '105'}]
        result = review_scores(human, algorithm)
        self.assertEqual(result['errors'][0]['error'], 'false_detection')


@unittest.skipUnless(importlib.util.find_spec('numpy'), 'optional numpy; mandatory in r1-research CI job')
class R1ModelTests(unittest.TestCase):
    def test_training_only_scaling_missingness_and_validation_isolation(self):
        import numpy as np
        from ashare_quant.r1.models import fit_ridge
        rows = [{'x': float(i), 'missing': None} for i in range(20)]
        model = fit_ridge(rows, [2 * i + 1 for i in range(20)], ['x', 'missing'])
        frozen = model.audit()
        predictions = model.predict([{'x': 10, 'missing': None}, {'x': 1e10, 'missing': 5}])
        self.assertTrue(np.isfinite(predictions).all())
        self.assertEqual(model.audit(), frozen)
        self.assertEqual(model.centers[0], 9.5)
        self.assertEqual(model.medians[1], 0)
        # Neither future rows nor labels enter fitting; a rerun on the same train data agrees.
        self.assertEqual(fit_ridge(rows, [2 * i + 1 for i in range(20)], ['x', 'missing']).audit(), frozen)

    def test_correlated_rows_share_bootstrap_cluster_weight(self):
        import numpy as np
        from ashare_quant.r1.models import cluster_weights
        rows = [{'symbol': 'a', 'time_block': 1}, {'symbol': 'a', 'time_block': 1}, {'symbol': 'b', 'time_block': 2}]
        weights = cluster_weights(rows, 50)
        self.assertTrue(np.allclose(weights[:, 0], weights[:, 1]))
        self.assertTrue(np.allclose(weights.sum(axis=1), 1))


if __name__ == '__main__':
    unittest.main()
