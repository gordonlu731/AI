"""As-of candlesticks and real-human review workflow; plotting is optional."""
from __future__ import annotations

import csv
import hashlib
import json
import math
from dataclasses import asdict
from pathlib import Path

from .structures import reference_zone

MAIN_METHODS = ('r0_legacy', 'atr_intersection', 'density', 'support')
JUDGMENTS = ('unreviewed', 'correct', 'too_high', 'too_low', 'omission', 'false_detection')


def render_chart(bars, snapshot, path: Path, title: str, methods=MAIN_METHODS, blind=False,
                 history=180, blank=False):
    """Input must stop exactly at snapshot.date; no unused future-price access."""
    if not bars or bars[-1].date.isoformat() != snapshot.date or snapshot.index != len(bars) - 1:
        raise ValueError('chart input must end exactly at its as-of snapshot')
    import os
    os.environ.setdefault('MPLCONFIGDIR', '/tmp/ashare-r1-mpl')
    import matplotlib
    matplotlib.use('Agg')
    import matplotlib.pyplot as plt
    from matplotlib.patches import Rectangle
    plt.rcParams['svg.hashsalt'] = 'R1-S1'
    start = max(0, len(bars) - history)
    view = bars[start:]
    anchor = view[0].close
    scale = 100 / anchor
    n = len(view)
    selected = (None,) if blank else methods
    rows, cols = (1, 1) if blank else (2, 2)
    fig = plt.figure(figsize=(16, 5.5 if blank else 11))
    grid = fig.add_gridspec(rows * 2, cols, height_ratios=[3, 1] * rows, hspace=0.3, wspace=0.18)
    for k, method in enumerate(selected):
        row, col = (k // cols) * 2, k % cols
        ax = fig.add_subplot(grid[row, col])
        volume = fig.add_subplot(grid[row + 1, col], sharex=ax)
        for j, b in enumerate(view):
            x = j - n + 1
            color = '#c33737' if b.close >= b.open else '#16826c'
            ax.vlines(x, b.low * scale, b.high * scale, color=color, linewidth=0.7)
            bottom, height = min(b.open, b.close) * scale, abs(b.close - b.open) * scale
            ax.add_patch(Rectangle((x - .32, bottom), .64, max(height, .015), color=color, alpha=.85))
            volume.bar(x, b.volume / max(1, sum(v.volume for v in view) / n), color=color, width=.65)
        if method:
            pivots = snapshot.atr_pivots if method == 'atr_intersection' else snapshot.fixed_pivots
            known = [p for p in pivots if p.index >= start]
            ax.plot([p.index - snapshot.index for p in known], [p.price * scale for p in known],
                    color='#323f5d', linewidth=.8, label='confirmed extrema')
            for p in known[-12:]:
                if p.confirmed_index >= start:
                    ax.scatter(p.confirmed_index - snapshot.index, p.price * scale, marker='x', color='#85630a', s=18)
            zones = sorted(snapshot.zones[method], key=lambda z: z.confirmed_index, reverse=True)
            shown = [z for z in zones if z.valid or (z.invalid_index is not None and snapshot.index - z.invalid_index <= 40)][:4]
            valid_count = sum(z.valid for z in zones)
            for z in shown:
                left = max(start, z.confirmed_index) - snapshot.index
                right = min(snapshot.index, z.invalid_index if z.invalid_index is not None else snapshot.index) - snapshot.index
                color = '#3569ab' if z.valid else '#999999'
                ax.fill_between([left, right], z.lower * scale, z.upper * scale, color=color, alpha=.09)
                for value, style in ((z.lower, '-' if z.valid else '--'), (z.upper, '-' if z.valid else '--'), (z.centroid, ':')):
                    ax.plot([left, right], [value * scale] * 2, linestyle=style, linewidth=.9, color=color)
            name = chr(65 + k) if blind else method
            ax.set_title(f'{name} | valid centers: {valid_count}; shown: {len(shown)}', fontsize=10)
            if not valid_count:
                ax.text(.02, .92, 'NO CLEAR ACTIVE CENTER', transform=ax.transAxes, fontsize=9, color='#8b2e2e')
        else:
            ax.set_title('Human annotation first: no algorithm overlay', fontsize=10)
        ax.set_ylabel('price index (first visible close = 100)')
        volume.set_ylabel('vol / view mean', fontsize=8)
        ticks = sorted(set([-n + 1, -int(n * .66), -int(n * .33), 0]))
        volume.set_xticks(ticks)
        if blind:
            volume.set_xlabel('sessions relative to cutoff')
        else:
            volume.set_xticklabels([view[x + n - 1].date.isoformat() for x in ticks], fontsize=7)
        ax.tick_params(labelbottom=False)
        ax.grid(alpha=.15)
    fig.suptitle(title, fontsize=12)
    fig.text(.5, .01, 'As-of bars only | gold x = confirmation time | daily volume is not buy/sell flow | unverified vendor snapshot', ha='center', fontsize=8)
    fig.subplots_adjust(top=.93, bottom=.075)
    path.parent.mkdir(parents=True, exist_ok=True)
    fig.savefig(path.with_suffix('.png'), dpi=135)
    fig.savefig(path.with_suffix('.pdf'), metadata={'CreationDate': None, 'ModDate': None})
    plt.close(fig)


def select_blind_samples(registration):
    selected = []
    config = registration['blind_review']
    for symbol in registration['independent_symbols']:
        dates = sorted(config['pool_dates'], key=lambda day: hashlib.sha256(f"{config['seed']}:{symbol}:{day}".encode()).hexdigest())[:config['samples_per_independent_symbol']]
        for day in sorted(dates):
            selected.append((symbol, day))
    return [(f'B{i + 1:03d}', symbol, day) for i, (symbol, day) in enumerate(selected)]


def masked_methods(case_id):
    return tuple(sorted(MAIN_METHODS, key=lambda method: hashlib.sha256(f'R1-review-731:{case_id}:{method}'.encode()).hexdigest()))


def review_scores(human_rows: list[dict], algorithm_rows: list[dict]) -> dict:
    """Compute agreement only for explicitly completed real-human samples.

    Each human row: case_id, reviewed=yes/no, no_center=yes/no, lower/upper/centroid
    in chart-normalized units; multiple rows represent multiple human centers.
    """
    completed = {r['case_id'] for r in human_rows if r.get('reviewed') == 'yes'}
    if not completed:
        return {'status': 'pending_real_human_annotations', 'reviewed_cases': 0, 'comparisons': [], 'errors': []}
    comparisons, errors = [], []
    for case_id in sorted(completed):
        humans = [r for r in human_rows if r['case_id'] == case_id and r.get('reviewed') == 'yes']
        if any(r.get('no_center') == 'yes' for r in humans):
            if len(humans) > 1:
                raise ValueError('no_center cannot coexist with human regions')
            humans = []
        parsed = []
        for row in humans:
            low, high, center = (float(row[k]) for k in ('lower', 'upper', 'centroid'))
            if not all(math.isfinite(x) for x in (low, high, center)) or not 0 < low <= center <= high:
                raise ValueError('invalid human region')
            parsed.append((low, high, center))
        algs = [r for r in algorithm_rows if r['case_id'] == case_id]
        for label in ('A', 'B', 'C', 'D'):
            candidates = [r for r in algs if r['algorithm_label'] == label and r.get('zone_id')]
            unmatched = set(range(len(parsed)))
            matches = []
            for a in sorted(candidates, key=lambda row: row['zone_id']):
                low, high, center = (float(a[k]) for k in ('lower', 'upper', 'centroid'))
                pairs = []
                for j in unmatched:
                    hlow, hhigh, hcenter = parsed[j]
                    union = max(high, hhigh) - min(low, hlow)
                    iou = max(0, min(high, hhigh) - max(low, hlow)) / union if union else 1.0
                    pairs.append((iou, -j, j))
                best = max(pairs, default=(0, 0, None))
                if best[0] > 0:
                    j = best[2]
                    unmatched.remove(j)
                    atr = float(a['atr_units']) if a.get('atr_units') else None
                    delta = center - parsed[j][2]
                    matches.append({'zone_id': a['zone_id'], 'iou': best[0], 'centroid_error': delta,
                                    'centroid_error_atr': delta / atr if atr and atr > 0 else None})
                else:
                    errors.append({'case_id': case_id, 'algorithm_label': label, 'zone_id': a['zone_id'], 'error': 'false_detection'})
            errors.extend({'case_id': case_id, 'algorithm_label': label, 'human_region': j, 'error': 'omission'} for j in sorted(unmatched))
            comparisons.append({'case_id': case_id, 'algorithm_label': label, 'human_count': len(parsed),
                                'algorithm_count': len(candidates), 'count_difference': len(candidates) - len(parsed), 'matches': matches})
    return {'status': 'scored_real_human_annotations', 'reviewed_cases': len(completed), 'comparisons': comparisons, 'errors': errors,
            'matching_rule': 'deterministic greedy positive-IoU; structural agreement only, never performance selection'}
