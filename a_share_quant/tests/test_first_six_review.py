"""Synthetic review fixtures; no market data or fabricated human judgments."""
import copy
import sys
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / 'research/r1'))
from review_feedback import upload_changes, CASE_IDS, MAIN_METHODS
from summarize_first_six import candidates, region_description, aggregate_regions, summarize
from test_review_feedback import synthetic_payload, synthetic_region


def zone(zid='synthetic-z', start=25, end=None, valid=True, low=95, high=105):
    return {'zone_id': zid, 'valid': valid, 'confirmed_k': start, 'invalid_k': end,
            'lower': low, 'upper': high, 'centroid': (low + high) / 2}


class FirstSixReviewTests(unittest.TestCase):
    def test_cumulative_export_counts_old_case_once(self):
        previous = synthetic_payload()
        previous['cases'][0].update(reviewed=True, center_judgment='regions', regions=[synthetic_region()])
        current = copy.deepcopy(previous)
        current['cases'][1].update(reviewed=True, center_judgment='none')
        result = upload_changes(current, previous, dict.fromkeys(CASE_IDS, 180))
        self.assertEqual(result['new_first_review_case_ids'], ['B002'])
        self.assertEqual(result['unchanged_previous_case_ids'], ['B001'])
        self.assertEqual(result['unique_reviewed_case_count'], 2)

    def test_post_reveal_edits_are_not_new_first_blind_reviews(self):
        previous = synthetic_payload()
        previous['cases'][0].update(reviewed=True, center_judgment='regions', regions=[synthetic_region()])
        current = copy.deepcopy(previous)
        current['cases'][0]['regions'][0]['lower'] = 91
        result = upload_changes(current, previous, dict.fromkeys(CASE_IDS, 180))
        self.assertEqual(result['new_first_review_case_ids'], [])
        self.assertEqual(result['post_reveal_revision_case_ids'], ['B001'])

    def test_old_completed_case_cannot_disappear(self):
        previous = synthetic_payload()
        previous['cases'][0].update(reviewed=True, center_judgment='none')
        with self.assertRaisesRegex(ValueError, 'disappear'):
            upload_changes(synthetic_payload(), previous, dict.fromkeys(CASE_IDS, 180))

    def test_history_scope_includes_expired_but_respects_human_time(self):
        zs = [zone('alive'), zone('expired', end=35, valid=False), zone('too-old', start=-20),
              zone('ended-before-human', start=1, end=10, valid=False), zone('confirmed-after-human', start=50)]
        h = synthetic_region()  # K20..40
        found = candidates(zs, 'historical_window', 180, h)
        self.assertEqual({z['zone_id'] for z in found}, {'alive', 'expired'})
        self.assertNotIn('expired', {z['zone_id'] for z in candidates(zs, 'end_inventory', 180)})

    def test_no_candidate_is_missing_disjoint_candidate_is_zero(self):
        h = synthetic_region()
        missing = region_description(h, [])
        disjoint = region_description(h, [zone(low=120, high=130)])
        self.assertIsNone(missing['maximum_price_iou'])
        self.assertEqual(disjoint['maximum_price_iou'], 0)
        self.assertIsNone(disjoint['best_positive_overlap'])
        s = aggregate_regions([missing, disjoint])
        self.assertEqual((s['human_region_denominator'], s['with_candidate'], s['without_candidate']), (2, 1, 1))
        self.assertEqual(s['candidates_but_no_positive_price_overlap'], 1)

    def test_summary_requires_all_six_unique_completed_cases(self):
        with self.assertRaisesRegex(ValueError, 'six distinct'):
            summarize([], 0)

    def test_multiple_human_centers_not_collapsed_and_all_pairs_kept(self):
        cases = []
        for cid in CASE_IDS:
            human = {'reviewed': True, 'center_judgment': 'none', 'regions': []}
            if cid == 'B005':
                a, b = synthetic_region(), synthetic_region()
                b.update(region_id='synthetic-r2', lower=120, upper=140)
                human.update(center_judgment='regions', regions=[a, b])
            cases.append({'case_id': cid, 'human': human, 'bar_count': 180,
                          'methods': {m: {'all_zone_history': [zone(), zone('z2', low=125, high=135)]} for m in MAIN_METHODS}})
        result = summarize(cases, 3)
        self.assertEqual(result['human_center_regions'], 2)
        for m in MAIN_METHODS:
            rows = result['cases'][4]['methods'][m]['end_window']['human_regions']
            self.assertEqual(len(rows), 2)
            self.assertEqual([len(r['pairs']) for r in rows], [2, 2])
            self.assertEqual(result['methods'][m]['end_window']['human_region_denominator'], 2)
        self.assertEqual(result['manual_correctness_judgments'], 'pending')


if __name__ == '__main__': unittest.main()
