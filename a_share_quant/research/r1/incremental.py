"""Stage 3: predetermined add-one/drop-one validation; zero independent test labels."""
from __future__ import annotations

import argparse
import json
import sys
import subprocess
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / 'src'))
from ashare_quant.data import sha256
from ashare_quant.r1.features import FEATURE_GROUPS
from ashare_quant.r1.io import write_json, write_csv
from ashare_quant.r1.models import fit_ridge, cluster_weights
from ashare_quant.r1.review import MAIN_METHODS


def target_value(row, target):
    if target == 'upper_first':
        return 1.0 if row['touch_order'] == 'upper_first' else 0.0 if row['touch_order'] == 'lower_first' else None
    return row.get(target)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--events', type=Path, required=True, help='local numeric JSON records')
    parser.add_argument('--event-audit', type=Path, required=True)
    parser.add_argument('--output', type=Path, required=True)
    args = parser.parse_args()
    registration = json.loads((ROOT / 'research/r1/preregister.json').read_text())
    event_audit = json.loads(args.event_audit.read_text())
    if event_audit['preregister_sha256'] != sha256(ROOT / 'research/r1/preregister.json') or event_audit['sealed_independent_labels_computed'] != 0:
        raise ValueError('event protocol mismatch')
    features = json.loads((args.events / 'features.json').read_text())
    outcomes = json.loads((args.events / 'labels.json').read_text())
    assert not any(r['cohort'] == 'independent' and r['split'] == 'sealed_test' for r in outcomes)
    args.output.mkdir(parents=True, exist_ok=False)
    import numpy as np
    baseline = registration['model']['baseline_features']
    all_groups = list(FEATURE_GROUPS)
    all_columns = baseline + [c for g in all_groups for c in FEATURE_GROUPS[g]]
    variants = {'baseline': baseline, **{f'add:{g}': baseline + FEATURE_GROUPS[g] for g in all_groups},
                'full': all_columns,
                **{f'drop:{g}': baseline + [c for other in all_groups if other != g for c in FEATURE_GROUPS[other]] for g in all_groups},
                'h3_simple': baseline + ['drawdown20', 'rebound20'],
                'h3_add_shape': baseline + ['drawdown20', 'rebound20'] + FEATURE_GROUPS['bottom_shape']}
    feature_map = {(r['event_id'], r['method']): r for r in features}
    metrics, coefficient_audit = [], []
    actual_fits = 0
    for method in MAIN_METHODS:
        for horizon in (3, 5, 10, 20):
            available = [r for r in outcomes if r['cohort'] == 'independent' and r['method'] == method and r['horizon'] == horizon
                         and r['split'] in ('train', 'validation') and r['status'] == 'observed']
            for target in ('net_return', 'excess_return', 'mae', 'mfe', 'path_drawdown', 'upper_first'):
                clear = [r for r in available if target_value(r, target) is not None]
                train = [r for r in clear if r['split'] == 'train']
                valid = [r for r in clear if r['split'] == 'validation']
                context = {'method': method, 'horizon': horizon, 'target': target, 'train_n': len(train), 'validation_n': len(valid),
                           'excluded_target_unavailable': len(available) - len(clear), 'evaluation': 'validation_only',
                           'stock_clusters': len({r['symbol'] for r in valid})}
                if len(train) < 30 or len(valid) < 10:
                    metrics.append({**context, 'variant': 'all', 'status': 'insufficient_data'})
                    continue
                x_train = [feature_map[(r['event_id'], method)] for r in train]
                x_valid = [feature_map[(r['event_id'], method)] for r in valid]
                y_train = np.asarray([target_value(r, target) for r in train])
                y_valid = np.asarray([target_value(r, target) for r in valid])
                weights = cluster_weights(valid, registration['model']['cluster_bootstrap_replicates'], registration['model']['seed'])
                losses = {}
                null_prediction = np.full(len(valid), y_train.mean())
                losses['null_mean'] = (null_prediction - y_valid) ** 2
                metrics.append({**context, 'variant': 'null_mean', 'status': 'evaluated', 'mse_or_brier': float(losses['null_mean'].mean()),
                                'mean_error': float((null_prediction - y_valid).mean())})
                for name, columns in variants.items():
                    model = fit_ridge(x_train, y_train, columns, registration['model']['alpha'])
                    actual_fits += 1
                    prediction = model.predict(x_valid)
                    if target == 'upper_first':
                        prediction = np.clip(prediction, 0, 1)
                    loss = (prediction - y_valid) ** 2
                    losses[name] = loss
                    reference = 'h3_simple' if name == 'h3_add_shape' else 'baseline' if not name.startswith('drop:') else 'full'
                    if name == 'baseline':
                        reference = 'null_mean'
                    difference = losses[reference] - loss if reference in losses else None
                    ci = np.quantile(weights @ difference, [.025, .975]).tolist() if difference is not None and len(weights) else None
                    metrics.append({**context, 'variant': name, 'status': 'evaluated', 'mse_or_brier': float(loss.mean()),
                                    'mean_error': float((prediction - y_valid).mean()), 'comparison_reference': reference,
                                    'delta_loss_positive_better': float(difference.mean()) if difference is not None else None,
                                    'descriptive_two_way_cluster_interval': ci})
                    coefficient_audit.append({**context, 'variant': name, **model.audit()})
    write_json(args.output / 'incremental_metrics.json', metrics)
    write_csv(args.output / 'incremental_metrics.csv', metrics)
    write_json(args.output / 'trained_model_audit.json', coefficient_audit)
    write_json(args.output / 'model_protocol_audit.json', {'preregister_sha256': sha256(ROOT / 'research/r1/preregister.json'),
        'code_commit': subprocess.check_output(['git', 'rev-parse', 'HEAD'], cwd=ROOT, text=True).strip(),
        'working_tree_dirty': bool(subprocess.check_output(['git', 'status', '--porcelain'], cwd=ROOT, text=True)),
        'input_features_sha256': sha256(args.events / 'features.json'), 'input_labels_sha256': sha256(args.events / 'labels.json'),
        'model_source_sha256': sha256(ROOT / 'src/ashare_quant/r1/models.py'),
        'actual_ridge_fits': actual_fits, 'variant_count': len(variants), 'model_runs': 1, 'hyperparameter_search_runs': 0,
        'sealed_test_labels_computed': 0, 'case_stocks_used_for_fit_or_validation': 0,
        'feature_groups': FEATURE_GROUPS, 'alpha': 10.0, 'numpy_version': np.__version__,
        'uncertainty': 'descriptive stock-and-time-block cluster resampling; six-stock survivor convenience sample; no significance claim',
        'interpretation': 'negative and positive incremental errors retained; no best-model selection from these metrics'})
    print(json.dumps({'fits': actual_fits, 'metrics': len(metrics), 'test_labels': 0}))


if __name__ == '__main__':
    main()
