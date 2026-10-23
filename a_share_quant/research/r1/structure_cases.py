"""Stage 1: as-of structures, designated-case explanations, blind review packets."""
from __future__ import annotations

import argparse
import hashlib
import json
import sys
import subprocess
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
            last_breakout = None
            for global_i in range(first, end):
                bar = dataset.bars[global_i]
                snapshot = stream.update(bar)
                day = bar.date.isoformat()
                recent = stream.bars[-21:-1]
                volume_ratio = bar.volume / (sum(x.volume for x in recent) / 20) if len(recent) == 20 and sum(x.volume for x in recent) > 0 else None
                breakout_today = bool(volume_ratio is not None and volume_ratio >= 1.5 and bar.close > max(x.high for x in recent))
                prior_breakout_date = last_breakout
                if breakout_today:
                    last_breakout = day
                diagnostic_window = (symbol == 'sz300620' and '2026-06-01' <= day <= '2026-08-31') or (symbol == 'sz002349' and ('2014-09-01' <= day <= '2014-12-31' or '2022-02-01' <= day <= '2022-04-30'))
                if case and diagnostic_window and (day, 'bottom_reversal') in assessment_map:
                    bottom = assessment_map[(day, 'bottom_reversal')]
                    trend = assessment_map[(day, 'trend_pullback')]
                    row = {'symbol': symbol, 'date': day, 'r0_bottom': explain_r0_bottom(stream.bars, snapshot.fixed_pivots, snapshot.fixed_legs, bottom),
                           'volume_ratio_prior20': volume_ratio, 'volume_breakout_today': breakout_today,
                           'last_prior_volume_breakout': prior_breakout_date,
                           'live_drawdown_from_recent20_peak': 1 - bar.close / max(x.close for x in stream.bars[-20:]),
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
                date_fields = ('formed_index', 'confirmed_index', 'last_test_index', 'invalid_index', 'structural_closed_index')
                dated_zones = {m: [{**asdict(z), **{key.replace('_index', '_date'): stream.bars[getattr(z, key)].date.isoformat()
                    if getattr(z, key) is not None else None for key in date_fields},
                    'member_kind': 'leg_ids' if m in ('r0_legacy', 'atr_intersection') else 'bar_indices'} for z in zones]
                    for m, zones in snapshot.zones.items()}
                snapshots.append({'case_id': case_id, 'symbol': symbol, 'asof': day, 'snapshot': asdict(snapshot), 'dated_zones': dated_zones})
                if is_blind:
                    blind_key.append({'case_id': case_id, 'symbol': symbol, 'asof': day, 'algorithm_key': dict(zip('ABCD', methods))})
                    human_rows.append({'case_id': case_id, 'reviewed': 'no', 'no_center': '', 'lower': '', 'upper': '', 'centroid': '', 'reviewer': '', 'notes': ''})
                    scale = 100 / stream.bars[max(0, len(stream.bars) - 180)].close
                    for label, method in zip('ABCD', methods):
                        valid = [z for z in snapshot.zones[method] if z.valid]
                        # Compare all valid centers, even when only four can fit in the image.
                        for z in valid:
                            masked_id = hashlib.sha256(f'{case_id}:{label}:{z.id}'.encode()).hexdigest()[:12]
                            region_rows.append({'case_id': case_id, 'algorithm_label': label, 'zone_id': masked_id,
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
               'code_commit': subprocess.check_output(['git', 'rev-parse', 'HEAD'], cwd=ROOT, text=True).strip(),
               'working_tree_dirty': bool(subprocess.check_output(['git', 'status', '--porcelain'], cwd=ROOT, text=True)),
               'source_code_sha256': {p.name: sha256(p) for p in (ROOT / 'src/ashare_quant/r1').glob('*.py')},
               'data_manifests': audit, 'parameters': asdict(config), 'local_price_figures_only': True,
               'human_scoring': 'pending_real_annotations', 'requested_charts': len(chart_inventory),
               'rendered': not args.no_plots, 'failed_or_missing_samples': sorted(set(f'{s}-{d}' for s in r['case_symbols'] for d in r['case_dates'][s]) - {x['case_id'] for x in chart_inventory if x['cohort'] == 'designated_case'})})
    print(json.dumps({'charts': len(chart_inventory), 'cases': case_rows, 'human_review': 'pending'}, ensure_ascii=False))


if __name__ == '__main__':
    main()
