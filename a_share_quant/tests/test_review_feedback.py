"""Synthetic inputs exercise review gates, not real human judgments."""
import copy
import sys
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / 'research/r1'))
from review_feedback import BATCH_ID, CASE_IDS, validate_annotations, interval_metrics, describe_method


def synthetic_payload():
    return {'schema': 'r1-human-batch1-v1', 'batch_id': BATCH_ID, 'history': [],
            'cases': [{'case_id': c, 'reviewed': False, 'center_judgment': 'unreviewed',
                       'bottom_judgment': 'unreviewed', 'regions': []} for c in CASE_IDS]}


def synthetic_region(kind='center'):
    return {'region_id': 'synthetic-r1', 'type': kind, 'k_start': 20, 'k_end': 40,
            'lower': 90., 'upper': 110., 'centroid': None}


class ReviewFeedbackTests(unittest.TestCase):
    def setUp(self):
        self.counts = dict.fromkeys(CASE_IDS, 180)

    def test_pending_samples_reveal_nothing(self):
        self.assertEqual(validate_annotations(synthetic_payload(), self.counts), [])

    def test_only_explicit_review_is_revealed_drafts_stay_hidden(self):
        p = synthetic_payload()
        p['cases'][0].update(reviewed=True, center_judgment='regions', regions=[synthetic_region()])
        p['cases'][1].update(center_judgment='regions', regions=[synthetic_region()])
        before = copy.deepcopy(p)
        self.assertEqual([r['case_id'] for r in validate_annotations(p, self.counts)], ['B001'])
        self.assertEqual(p, before)

    def test_invalid_order_and_truthy_review_flags_rejected(self):
        p = synthetic_payload()
        p['cases'][0]['reviewed'] = 'false'
        with self.assertRaisesRegex(ValueError, 'boolean'):
            validate_annotations(p, self.counts)
        p = synthetic_payload()
        p['cases'].reverse()
        with self.assertRaisesRegex(ValueError, 'order'):
            validate_annotations(p, self.counts)

    def test_no_center_conflict_and_invalid_future_k_rejected(self):
        for updates in [{'center_judgment': 'none'}, {}]:
            p = synthetic_payload()
            r = synthetic_region()
            if not updates:
                r['k_end'] = 181
            p['cases'][0].update(regions=[r], **updates)
            with self.assertRaises(ValueError):
                validate_annotations(p, self.counts)

    def test_bottom_only_cannot_mark_center_review_complete(self):
        p = synthetic_payload()
        p['cases'][0].update(reviewed=True, bottom_judgment='regions', regions=[synthetic_region('bottom')])
        with self.assertRaisesRegex(ValueError, 'center judgment'):
            validate_annotations(p, self.counts)

    def test_missing_centroid_stays_missing_with_analytic_overlap(self):
        h = synthetic_region()
        z = {'zone_id': 'synthetic-z', 'lower': 95., 'upper': 105., 'centroid': 100., 'confirmed_k': 30}
        m = interval_metrics(h, z)
        self.assertEqual(m['price_iou'], .5)
        self.assertIsNone(m['centroid_error'])
        self.assertIsNone(m['centroid_error_atr'])
        self.assertEqual(m['lower_delta_human_width'], .25)
        self.assertEqual(m['upper_delta_human_width'], -.25)
        self.assertTrue(m['confirmed_in_human_interval'])
        h['centroid'] = 98.
        z['atr_units'] = 4.
        self.assertEqual(interval_metrics(h, z)['centroid_error_atr'], .5)

    def test_all_inventory_and_recent_counts_are_distinct(self):
        zones = [{'zone_id': str(i), 'lower': 95., 'upper': 105., 'centroid': 100., 'confirmed_k': k}
                 for i, k in enumerate([-10, 30, 170])]
        d = describe_method([synthetic_region()], zones, 180)
        self.assertEqual((d['all_retained_count'], d['confirmed_in_visible_window_count']), (3, 2))
        self.assertEqual(len(d['pairs']), 3)
        self.assertEqual(d['human_algorithm_judgments'], 'pending')
        self.assertEqual(d['automatic_correct_false_detection_labels'], 'not_assigned')

    def test_uncertain_does_not_become_no_center_or_numeric_error(self):
        d = describe_method([synthetic_region()], [], 180, judgment='uncertain')
        self.assertEqual(d['pairs'], [])
        self.assertIsNone(d['all_retained_count_minus_human'])
        self.assertIsNone(d['window_confirmation_count_minus_human'])

    def test_nonfinite_and_boolean_prices_rejected(self):
        for value in [float('nan'), float('inf'), True]:
            p = synthetic_payload()
            r = synthetic_region()
            r['lower'] = value
            p['cases'][0]['regions'] = [r]
            with self.assertRaises(ValueError):
                validate_annotations(p, self.counts)


if __name__ == '__main__':
    unittest.main()
