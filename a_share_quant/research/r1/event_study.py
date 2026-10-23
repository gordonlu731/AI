"""Stage 2: fixed-anchor exploratory labels; independent test outcomes stay sealed."""
from __future__ import annotations

import argparse
import csv
import gzip
import json
import sys
import subprocess
from collections import Counter, defaultdict
from datetime import date
from pathlib import Path
from statistics import mean, median

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / 'src'))
from ashare_quant.data import session_segments, sha256
from ashare_quant.strategy import assess_sessions
from ashare_quant.r1.io import load_benchmark, load_dataset, write_csv, write_json
from ashare_quant.r1.structures import Config, StructureStream
from ashare_quant.r1.features import barriers, feature_row
from ashare_quant.r1.outcomes import HORIZONS, event_labels, split_name


def write_gzip_csv(path, rows):
    keys = list(dict.fromkeys(k for r in rows for k in r))
    with gzip.open(path, 'wt', newline='', encoding='utf-8') as f:
        writer = csv.DictWriter(f, fieldnames=keys, lineterminator='\n')
        writer.writeheader()
        for r in rows:
            writer.writerow({k: json.dumps(v, ensure_ascii=False, allow_nan=False) if isinstance(v, (dict, list, tuple)) else v for k, v in r.items()})


def distribution(values):
    values = sorted(v for v in values if v is not None)
    if not values:
        return {'n': 0, 'mean': None, 'median': None, 'q10': None, 'q90': None, 'min': None, 'max': None}
    def quantile(q):
        x = (len(values) - 1) * q
        low = int(x)
        return values[low] + (values[min(low + 1, len(values) - 1)] - values[low]) * (x - low)
    return {'n': len(values), 'mean': mean(values), 'median': median(values), 'q10': quantile(.1),
            'q90': quantile(.9), 'min': values[0], 'max': values[-1]}


def aggregate(rows, group_fields):
    groups = defaultdict(list)
    for r in rows:
        if r.get('horizon') in HORIZONS:
            groups[tuple(r.get(k) for k in group_fields)].append(r)
    result = []
    for key, values in sorted(groups.items(), key=lambda p: str(p[0])):
        observed = [v for v in values if v['status'] == 'observed']
        order = Counter(v['touch_order'] for v in observed)
        clear = order['upper_first'] + order['lower_first']
        result.append({**dict(zip(group_fields, key)), 'events': len(values), 'observed': len(observed),
            'statuses': dict(Counter(v['status'] for v in values)), 'touch_order_counts': dict(order),
            'upper_first_among_clear_hits': order['upper_first'] / clear if clear else None,
            'upper_first_among_all_observed': order['upper_first'] / len(observed) if observed else None,
            'lower_first_among_all_observed': order['lower_first'] / len(observed) if observed else None,
            'negative_net_count': sum(v['net_return'] < 0 for v in observed),
            **{field: distribution(v[field] for v in observed) for field in ('return', 'net_return', 'excess_return', 'mae', 'mfe', 'path_drawdown')}})
    return result


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--structure-stage', type=Path, required=True)
    parser.add_argument('--output', type=Path, required=True)
    parser.add_argument('--local', type=Path, required=True)
    args = parser.parse_args()
    registry = ROOT / 'research/r1/preregister.json'
    registration = json.loads(registry.read_text())
    stage = json.loads(args.structure_stage.read_text())
    if stage['stage'] != 'structure_and_case_diagnostics_complete' or stage['preregister_sha256'] != sha256(registry):
        raise ValueError('complete unchanged structure/case stage first')
    args.output.mkdir(parents=True, exist_ok=False)
    args.local.mkdir(parents=True, exist_ok=False)
    config = Config(**registration['structural_parameters'])
    benchmark, benchmark_manifest = load_benchmark(ROOT)
    benchmark_map = {b.date: i for i, b in enumerate(benchmark)}
    features, labels, anchors, manifests, coverage = [], [], [], [], []
    daily_path = args.output / 'all_daily_states.jsonl.gz'
    with gzip.open(daily_path, 'wt', encoding='utf-8') as daily_file:
        for symbol in registration['case_symbols'] + registration['independent_symbols']:
            is_case = symbol in registration['case_symbols']
            data = load_dataset(ROOT, symbol, is_case)
            manifests.append(data.manifest)
            positions = {d: i for i, d in enumerate(data.calendar)}
            r0 = {(a.date, a.strategy): a for a in assess_sessions(data.bars, data.calendar)}
            known_days = {b.date for b in data.bars}
            counts = Counter()
            for missing in (d for d in data.calendar if data.bars[0].date <= d <= data.bars[-1].date and d not in known_days and d.isoformat() >= registration['splits']['train'][0]):
                daily_file.write(json.dumps({'symbol': symbol, 'date': missing.isoformat(), 'status': 'data_gap_unknown_status', 'reason': 'no_bar_not_assumed_suspension'}) + '\n')
                counts['data_gap_days'] += 1
                if positions[missing] % registration['event_sampling']['calendar_stride'] == 0:
                    split = 'case_only' if is_case else split_name(missing, data.calendar, registration['splits'])
                    anchors.append({'symbol': symbol, 'date': missing.isoformat(), 'cohort': 'case' if is_case else 'independent',
                                    'split': split, 'status': 'signal_data_unavailable'})
            for first, end in session_segments(data.bars, data.calendar):
                stream = StructureStream(config)
                for global_i in range(first, end):
                    bar = data.bars[global_i]
                    snapshot = stream.update(bar)
                    day = bar.date.isoformat()
                    if day < registration['splits']['train'][0]:
                        continue
                    split = 'case_only' if is_case else split_name(bar.date, data.calendar, registration['splits'])
                    warmed = len(stream.bars) >= registration['event_sampling']['min_history']
                    state = {'symbol': symbol, 'date': day, 'split': split, 'status': 'assessed' if warmed else 'warmup',
                        'segment_start': data.bars[first].date.isoformat(),
                        'centers': {m: sum(z.valid for z in zones) for m, zones in snapshot.zones.items()},
                        'r0_rejections': {name: list(r0[(day, name)].reasons) if (day, name) in r0 else ['warmup']
                            for name in ('trend_pullback', 'bottom_reversal')}}
                    daily_file.write(json.dumps(state, ensure_ascii=False) + '\n')
                    counts[state['status']] += 1
                    if positions[bar.date] % registration['event_sampling']['calendar_stride'] != 0:
                        continue
                    status = 'ready' if warmed else 'warmup'
                    if not is_case and split not in ('train', 'validation'):
                        status = 'sealed_not_evaluated' if split == 'sealed_test' else split
                    anchor = {'symbol': symbol, 'date': day, 'cohort': 'case' if is_case else 'independent', 'split': split, 'status': status}
                    anchors.append(anchor)
                    counts[f'anchors_{status}'] += 1
                    if status != 'ready':
                        continue
                    bpos = benchmark_map.get(bar.date)
                    market_momentum = benchmark[bpos].close / benchmark[bpos - 20].close - 1 if bpos is not None and bpos >= 20 else None
                    regime = 'unavailable'
                    if bpos is not None and bpos >= 60:
                        regime = 'index60_up' if benchmark[bpos].close >= benchmark[bpos - 60].close else 'index60_down'
                    for method in registration['methods']:
                        f = feature_row(stream.bars, snapshot, method, config, market_momentum)
                        common = {**anchor, 'method': method, 'event_id': f'{symbol}:{day}', 'year': bar.date.year,
                                  'market_regime': regime, 'industry': 'unavailable',
                                  'time_block': positions[bar.date] // 20, 'structure_state': 'center' if f['zone_present'] else 'no_center'}
                        lower, upper = barriers(stream.bars, snapshot, method)
                        geometry = {'lower_distance': 1 - lower / bar.close if lower is not None else None,
                                    'upper_distance': upper / bar.close - 1 if upper is not None else None}
                        features.append({**common, **geometry, **f})
                        outcomes = event_labels(data.bars, benchmark, data.calendar, bar.date, lower, upper,
                                                registration['event_sampling']['cost_per_side_assumption'])
                        for outcome in outcomes:
                            # Never let a label extend beyond its own registered train/validation period.
                            if split in ('train', 'validation') and outcome['exit_date'] is not None and outcome['exit_date'] > registration['splits'][split][1]:
                                raise AssertionError('label crosses a split boundary')
                            labels.append({**common, **geometry, 'bottom_shape': f['bottom_shape'], 'zone_present': f['zone_present'],
                                           'r0_rejections': state['r0_rejections'], **outcome})
            coverage.append({'symbol': symbol, 'cohort': 'case' if is_case else 'independent', 'bars': len(data.bars),
                             'first': data.bars[0].date.isoformat(), 'last': data.bars[-1].date.isoformat(), 'counts': dict(counts)})
            print(json.dumps({'symbol': symbol, 'anchors_so_far': len(anchors), 'labels_so_far': len(labels)}), flush=True)
    assert not any(r['cohort'] == 'independent' and r['split'] == 'sealed_test' for r in labels)
    write_gzip_csv(args.output / 'anchor_features.csv.gz', features)
    write_gzip_csv(args.output / 'all_event_labels.csv.gz', labels)
    write_csv(args.output / 'anchor_register.csv', anchors)
    write_json(args.output / 'event_summary.json', aggregate(labels, ['cohort', 'split', 'method', 'horizon', 'structure_state']))
    write_json(args.output / 'year_regime_summary.json', aggregate(labels, ['cohort', 'split', 'method', 'horizon', 'year', 'market_regime']))
    write_json(args.output / 'bottom_shape_summary.json', aggregate(labels, ['cohort', 'split', 'method', 'horizon', 'bottom_shape']))
    write_json(args.output / 'coverage.json', coverage)
    write_json(args.output / 'event_audit.json', {'experiment': registration['experiment'], 'preregister_sha256': sha256(registry),
        'code_commit': subprocess.check_output(['git', 'rev-parse', 'HEAD'], cwd=ROOT, text=True).strip(),
        'working_tree_dirty': bool(subprocess.check_output(['git', 'status', '--porcelain'], cwd=ROOT, text=True)),
        'source_code_sha256': {p.name: sha256(p) for p in (ROOT / 'src/ashare_quant/r1').glob('*.py')},
        'verification': 'UNVERIFIED_SNAPSHOT_EXPLORATION', 'data_manifests': manifests, 'benchmark_manifest': benchmark_manifest,
        'benchmark_basis': 'SSE Composite price index; not total-return matched', 'sealed_independent_labels_computed': 0,
        'human_review': 'pending', 'label_count': len(labels), 'feature_rows': len(features), 'anchor_count': len(anchors),
        'anchor_status_counts': dict(Counter(a['status'] for a in anchors)),
        'industry_comparison': 'unavailable historical classification', 'execution_constraints_verified': False,
        'files': {p.name: sha256(p) for p in args.output.glob('*') if p.is_file()}})
    # These local records retain numeric types for modelling, with zero sealed-test outcomes.
    write_json(args.local / 'features.json', features)
    write_json(args.local / 'labels.json', labels)
    print(json.dumps({'events_complete': True, 'features': len(features), 'labels': len(labels), 'sealed_labels': 0}))


if __name__ == '__main__':
    main()
