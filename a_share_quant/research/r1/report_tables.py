"""Produce concise, non-price tables/plots from the complete fixed-run outputs."""
import argparse
import json
import math
import sys
from collections import defaultdict
from pathlib import Path
from statistics import mean, median

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / 'src'))
from ashare_quant.r1.io import write_json, write_csv

parser = argparse.ArgumentParser(description=__doc__)
parser.add_argument('--events', type=Path, required=True)
parser.add_argument('--models', type=Path, required=True)
parser.add_argument('--labels', type=Path, required=True)
parser.add_argument('--output', type=Path, required=True)
args = parser.parse_args()
args.output.mkdir(parents=True, exist_ok=False)
summary = json.loads((args.events / 'event_summary.json').read_text())
metrics = json.loads((args.models / 'incremental_metrics.json').read_text())
labels = json.loads(args.labels.read_text())
unconditional = [r for r in summary if r['cohort'] == 'independent' and r['split'] == 'validation' and r['method'] == 'rolling20']
rmse = [{k: r[k] for k in ('method', 'horizon', 'variant', 'validation_n')} | {'rmse': math.sqrt(r['mse_or_brier'])}
        for r in metrics if r.get('target') == 'net_return' and r.get('horizon') == 20 and r.get('variant') in ('null_mean', 'baseline', 'full')]
groups = defaultdict(list)
for r in metrics:
    if r.get('target') == 'net_return' and r.get('variant', '').startswith('add:'):
        groups[r['variant']].append(r)
increments = [{'group': group, 'comparisons': len(rows), 'positive_delta_count': sum(r['delta_loss_positive_better'] > 0 for r in rows),
               'cluster_interval_wholly_positive': sum(r['descriptive_two_way_cluster_interval'][0] > 0 for r in rows)} for group, rows in groups.items()]
geometries = []
for method in sorted({r['method'] for r in labels}):
    rows = [r for r in labels if r['cohort'] == 'independent' and r['split'] == 'validation' and r['horizon'] == 20
            and r['method'] == method and r['status'] == 'observed']
    matched = [r for r in rows if r['lower_distance'] is not None and r['upper_distance'] is not None]
    geometries.append({'method': method, 'total_observed': len(rows), 'legal_two_boundaries': len(matched),
                       'median_lower_distance': median(r['lower_distance'] for r in matched) if matched else None,
                       'median_upper_distance': median(r['upper_distance'] for r in matched) if matched else None,
                       'ambiguous': sum(r['touch_order'] == 'ambiguous' for r in rows),
                       'missing_barriers': sum(r['touch_order'] == 'missing_barriers' for r in rows)})
h3 = [r for r in json.loads((args.events / 'bottom_shape_summary.json').read_text())
      if r['cohort'] == 'independent' and r['split'] == 'validation' and r['method'] == 'r0_legacy']
for name, rows in [('validation_unconditional', unconditional), ('net20_rmse', rmse), ('increment_counts', increments),
                   ('barrier_geometry', geometries), ('h3_validation', h3)]:
    write_json(args.output / f'{name}.json', rows)
    write_csv(args.output / f'{name}.csv', rows)
targets, positive_intervals = [], []
for target in ('net_return', 'excess_return', 'mae', 'mfe', 'path_drawdown', 'upper_first'):
    additions = [r for r in metrics if r.get('target') == target and r.get('variant', '').startswith('add:')]
    fulls = [r for r in metrics if r.get('target') == target and r.get('variant') == 'full']
    targets.append({'target': target, 'add_positive': sum(r['delta_loss_positive_better'] > 0 for r in additions),
                    'add_total': len(additions), 'add_interval_wholly_positive': sum(r['descriptive_two_way_cluster_interval'][0] > 0 for r in additions),
                    'full_positive': sum(r['delta_loss_positive_better'] > 0 for r in fulls), 'full_total': len(fulls),
                    'full_interval_wholly_positive': sum(r['descriptive_two_way_cluster_interval'][0] > 0 for r in fulls)})
    positive_intervals.extend(r for r in additions if r['descriptive_two_way_cluster_interval'][0] > 0)
for name, rows in [('target_increment_overview', targets), ('positive_cluster_intervals', positive_intervals)]:
    write_json(args.output / f'{name}.json', rows)
    write_csv(args.output / f'{name}.csv', rows)
import os
os.environ.setdefault('MPLCONFIGDIR', '/tmp/ashare-r1-mpl')
import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt
plt.rcParams['svg.hashsalt'] = 'R1-S1-derived'
methods = ['r0_legacy', 'atr_intersection', 'density', 'support']
fig, ax = plt.subplots(figsize=(9, 4.5))
xs = list(range(len(methods)))
for offset, variant, label in [(-.2, 'baseline', 'momentum/ATR/index baseline'), (.2, 'full', 'full decomposed features')]:
    values = [next(r['rmse'] * 100 for r in rmse if r['method'] == method and r['variant'] == variant) for method in methods]
    ax.bar([x + offset for x in xs], values, .38, label=label)
null = next(r['rmse'] * 100 for r in rmse if r['variant'] == 'null_mean')
ax.axhline(null, color='#555555', linestyle='--', label='training-mean null')
ax.set(xticks=xs, xticklabels=methods, ylabel='validation RMSE, percentage points', ylim=(0, max(r['rmse'] * 100 for r in rmse) * 1.2),
       title='R1: 20-session return prediction (190 validation anchors)')
ax.legend(fontsize=8)
fig.text(.5, .01, 'Exploratory unverified snapshots; six current stocks; sealed independent test not evaluated.', ha='center', fontsize=8)
fig.tight_layout(rect=(0, .04, 1, 1))
path = args.output / 'validation-rmse.svg'
fig.savefig(path, metadata={'Date': None})
path.write_text('\n'.join(line.rstrip() for line in path.read_text().splitlines()) + '\n')
plt.close(fig)
