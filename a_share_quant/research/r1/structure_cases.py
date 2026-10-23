"""Stage 1: as-of structures, designated-case explanations, blind review packets."""
from __future__ import annotations

import argparse
import hashlib
import json
import sys
from collections import Counter
from dataclasses import asdict
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / 'src'))
from ashare_quant.data import session_segments, sha256
from ashare_quant.strategy import assess_sessions
from ashare_quant.r1.io import load_dataset, write_csv, write_json
from ashare_quant.r1.structures import Config, StructureStream
from ashare_quant.r1.features import bottom_state, feature_row, explain_r0_bottom
from ashare_quant.r1.review import MAIN_METHODS, masked_methods, render_chart, review_scores, select_blind_samples


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--output', type=Path, required=True, help='ignored local directory')
    parser.add_argument('--public', type=Path, required=True, help='non-price audit/template directory')
    parser.add_argument('--no-plots', action='store_true')
    args = parser.parse_args()
    args.output.mkdir(parents=True, exist_ok=False)
    args.public.mkdir(parents=True, exist_ok=False)
    registry = ROOT / 'research/r1/preregister.json'
    r = json.loads(registry.read_text())
    config = Config(**r['structural_parameters'])
    blind = select_blind_samples(r)
    case_rows, chart_inventory, blind_key, region_rows, human_rows, judgment_rows, snapshots = [], [], [], [], [], [], []
    audit = []
    for symbol in r['case_symbols'] + r['independent_symbols']:
        case = symbol in r['case_symbols']
        dataset = load_dataset(ROOT, symbol, case)
        audit.append(dataset.manifest)
        requested = {day: (f'{symbol}-{day}', False) for day in r['case_dates'].get(symbol, [])}
        requested.update({day: (case_id, True) for case_id, s, day in blind if s == symbol})
        assessment_map = {(a.date, a.strategy): a for a in assess_sessions(dataset.bars, dataset.calendar)} if case else {}
        daily_case = []
        for first, end in session_segments(dataset.bars, dataset.calendar):
            stream = StructureStream(config)
            for global_i in range(first, end):
                bar = dataset.bars[global_i]
                snapshot = stream.update(bar)
                day = bar.date.isoformat()
                diagnostic_window = (symbol == 'sz300620' and '2026-06-01' <= day <= '2026-08-31') or (symbol == 'sz002349' and ('2014-09-01' <= day <= '2014-12-31' or '2022-02-01' <= day <= '2022-04-30'))
                if case and diagnostic_window and (day, 'bottom_reversal') in assessment_map:
                    bottom = assessment_map[(day, 'bottom_reversal')]
                    trend = assessment_map[(day, 'trend_pullback')]
                    row = {'symbol': symbol, 'date': day, 'r0_bottom': explain_r0_bottom(stream.bars, snapshot.fixed_pivots, snapshot.fixed_legs, bottom),
                           'r0_trend_rejections': list(trend.reasons), 'r0_trend_emitted': trend.emitted,
                           'r1_fixed_bottom': bottom_state(stream.bars, snapshot.fixed_pivots, config),
                           'r1_atr_bottom': bottom_state(stream.bars, snapshot.atr_pivots, config),
                           'methods': {m: {'valid_centers': sum(z.valid for z in snapshot.zones[m]),
                               'invalid_or_expired': sum(not z.valid for z in snapshot.zones[m]),
                               'features': feature_row(stream.bars, snapshot, m, config)} for m in MAIN_METHODS}}
                    # No absolute prices in published diagnostics.
                    daily_case.append(row)
                if day not in requested:
                    continue
                case_id, is_blind = requested[day]
                methods = masked_methods(case_id) if is_blind else MAIN_METHODS
                chart_path = args.output / ('blind' if is_blind else 'cases') / case_id
                if not args.no_plots:
                    render_chart(stream.bars, snapshot, chart_path, case_id if is_blind else f'{symbol} as of {day}', methods=methods, blind=is_blind)
                    if is_blind:
                        render_chart(stream.bars, snapshot, chart_path.with_name(case_id + '-blank'), case_id, blind=True, blank=True)
                chart_inventory.append({'case_id': case_id, 'cohort': 'independent_blind' if is_blind else 'designated_case',
                    'asof_visible_only': True, 'snapshot_verified_pit': False, 'path': str(chart_path.relative_to(args.output)) + '.png',
                    'status': 'not_rendered' if args.no_plots else 'rendered_local_only'})
                snapshots.append({'case_id': case_id, 'symbol': symbol, 'asof': day, 'snapshot': asdict(snapshot)})
                if is_blind:
                    blind_key.append({'case_id': case_id, 'symbol': symbol, 'asof': day, 'algorithm_key': dict(zip('ABCD', methods))})
                    human_rows.append({'case_id': case_id, 'reviewed': 'no', 'no_center': '', 'lower': '', 'upper': '', 'centroid': '', 'reviewer': '', 'notes': ''})
                    scale = 100 / stream.bars[max(0, len(stream.bars) - 180)].close
                    for label, method in zip('ABCD', methods):
                        valid = [z for z in snapshot.zones[method] if z.valid]
                        # Compare all valid centers, even when only four can fit in the image.
                        for z in valid:
                            region_rows.append({'case_id': case_id, 'algorithm_label': label, 'zone_id': z.id,
                                'lower': z.lower * scale, 'upper': z.upper * scale, 'centroid': z.centroid * scale,
                                'atr_units': snapshot.atr * scale if snapshot.atr else None})
                        if not valid:
                            region_rows.append({'case_id': case_id, 'algorithm_label': label, 'zone_id': '', 'lower': '', 'upper': '', 'centroid': '', 'atr_units': ''})
                        judgment_rows.append({'case_id': case_id, 'algorithm_label': label, 'judgment': 'unreviewed', 'notes': ''})
        if daily_case:
            write_json(args.public / f'{symbol}-daily-diagnostics.json', daily_case)
            counts = Counter(reason for row in daily_case for reason in row['r0_bottom']['rejections'])
            case_rows.append({'symbol': symbol, 'diagnostic_days': len(daily_case), 'r0_bottom_signals': sum(row['r0_bottom']['emitted'] for row in daily_case),
                              'r0_bottom_rejection_counts': dict(counts), 'r0_trend_signals': sum(row['r0_trend_emitted'] for row in daily_case),
                              'r1_fixed_bottom_shape_days': sum(row['r1_fixed_bottom']['bottom_shape'] for row in daily_case),
                              'r1_atr_bottom_shape_days': sum(row['r1_atr_bottom']['bottom_shape'] for row in daily_case)})
    write_json(args.output / 'snapshot-price-details.json', snapshots)
    write_json(args.output / 'PRIVATE-unblinding-key.json', blind_key)
    write_csv(args.output / 'algorithm_regions.csv', region_rows)
    write_csv(args.public / 'human_regions_template.csv', human_rows)
    write_csv(args.public / 'algorithm_judgments_template.csv', judgment_rows)
    write_json(args.public / 'human_agreement.json', review_scores(human_rows, region_rows))
    write_json(args.public / 'chart_inventory.json', chart_inventory)
    write_json(args.public / 'case_summary.json', case_rows)
    write_json(args.public / 'structure_stage.json', {'stage': 'structure_and_case_diagnostics_complete', 'preregister_sha256': sha256(registry),
               'data_manifests': audit, 'parameters': asdict(config), 'local_price_figures_only': True,
               'human_scoring': 'pending_real_annotations', 'requested_charts': len(chart_inventory),
               'rendered': not args.no_plots, 'failed_or_missing_samples': sorted(set(f'{s}-{d}' for s in r['case_symbols'] for d in r['case_dates'][s]) - {x['case_id'] for x in chart_inventory if x['cohort'] == 'designated_case'})})
    print(json.dumps({'charts': len(chart_inventory), 'cases': case_rows, 'human_review': 'pending'}, ensure_ascii=False))


if __name__ == '__main__':
    main()
