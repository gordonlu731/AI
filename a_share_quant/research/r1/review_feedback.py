"""Receive real mobile annotations; reveal only explicitly reviewed case IDs.

No model/outcome modules are imported. Price-bearing receipts, plots and pairs
stay local. Public results contain only counts, ratios, hashes and statuses.
"""
from __future__ import annotations

import argparse
import hashlib
import json
import math
import os
import subprocess
import sys
from dataclasses import asdict
from datetime import datetime, timezone
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / 'src'))
from ashare_quant.data import sha256
from ashare_quant.r1.io import load_dataset, write_json
from ashare_quant.r1.structures import Config, StructureStream
from ashare_quant.r1.features import bottom_state, explain_r0_bottom
from ashare_quant.r1.review import MAIN_METHODS, masked_methods
from ashare_quant.strategy import assess
from mobile_review import BATCH_ID, draw_figure, visible_window

NAMES = {'r0_legacy': 'R0 固定波段交集', 'atr_intersection': 'ATR 自适应波段交集',
         'density': '价格密集区', 'support': '动态承接区'}
CASE_IDS = [f'B{i:03d}' for i in range(1, 7)]


def validate_annotations(payload, counts):
    if payload.get('schema') != 'r1-human-batch1-v1' or payload.get('batch_id') != BATCH_ID:
        raise ValueError('wrong annotation schema or batch')
    cases = payload.get('cases', [])
    if [c.get('case_id') for c in cases] != CASE_IDS:
        raise ValueError('case IDs/order differ from the first delivery')
    if not isinstance(payload.get('history'), list):
        raise ValueError('original revision history is required')
    reviewed = []
    for c in cases:
        if type(c.get('reviewed')) is not bool:
            raise ValueError('reviewed must be a boolean, not a truthy string')
        regions = c.get('regions')
        if not isinstance(regions, list):
            raise ValueError('regions must be a list')
        ids = set()
        for r in regions:
            if r.get('type') not in ('center', 'bottom') or not r.get('region_id') or r['region_id'] in ids:
                raise ValueError('unknown region type or duplicate/missing region ID')
            ids.add(r['region_id'])
            a, b = r.get('k_start'), r.get('k_end')
            if type(a) is not int or type(b) is not int or not 1 <= a <= b <= counts[c['case_id']]:
                raise ValueError('K interval outside the originally visible window')
            lo, hi, center = r.get('lower'), r.get('upper'), r.get('centroid')
            if not all(type(x) in (float, int) and math.isfinite(x) for x in (lo, hi)) or not 0 < lo < hi:
                raise ValueError('invalid/non-finite price interval')
            if center is not None and (type(center) not in (int, float) or not math.isfinite(center) or not lo <= center <= hi):
                raise ValueError('invalid optional human centroid')
        for kind in ('center', 'bottom'):
            judgment = c.get(kind + '_judgment')
            has_regions = any(r['type'] == kind for r in regions)
            if judgment not in ('unreviewed', 'none', 'uncertain', 'regions'):
                raise ValueError('unknown human judgment')
            if (judgment == 'none' and has_regions) or (judgment == 'regions' and not has_regions):
                raise ValueError('judgment conflicts with region records')
        if c['reviewed']:
            if c['center_judgment'] == 'unreviewed':
                raise ValueError('reviewed flag lacks an explicit center judgment')
            reviewed.append(c)
    return reviewed


def upload_changes(current, previous, counts):
    """Unique-case progress: a repeated export is not another blind review."""
    reviewed = validate_annotations(current, counts)
    old = {c['case_id']: c for c in validate_annotations(previous, counts)} if previous else {}
    now = {c['case_id']: c for c in reviewed}
    if set(old) - set(now):
        raise ValueError('previously reviewed cases cannot silently disappear from cumulative export')
    return {'new_first_review_case_ids': sorted(set(now) - set(old)),
            'unchanged_previous_case_ids': sorted(cid for cid in old if now[cid] == old[cid]),
            'post_reveal_revision_case_ids': sorted(cid for cid in old if now[cid] != old[cid]),
            'unique_reviewed_case_count': len(now)}


def interval_metrics(human, algorithm):
    """All-pairs description, NOT a new replacement for the frozen scorer.

    No centroid imputation, IoU threshold, weighting or automatic correctness.
    Temporal extent is reported separately: a human consolidation rectangle is
    not equivalent to an algorithm support/resistance lifetime.
    """
    lo, hi = human['lower'], human['upper']
    al, au = algorithm['lower'], algorithm['upper']
    union = max(hi, au) - min(lo, al)
    iou = max(0, min(hi, au) - max(lo, al)) / union if union else 1.0
    hc = human.get('centroid')
    delta = algorithm['centroid'] - hc if hc is not None else None
    atr = algorithm.get('atr_units')
    return {'human_region_id': human['region_id'], 'zone_id': algorithm['zone_id'],
            'price_iou': iou, 'lower_delta_human_width': (al - lo) / (hi - lo),
            'upper_delta_human_width': (au - hi) / (hi - lo), 'width_ratio': (au - al) / (hi - lo),
            'centroid_error': delta, 'centroid_error_atr': delta / atr if delta is not None and atr else None,
            'confirmed_in_human_interval': human['k_start'] <= algorithm['confirmed_k'] <= human['k_end']}


def describe_method(humans, zones, count, judgment='regions'):
    # All valid zones are retained. Window-context counts supplement, not replace,
    # inventory counts; old R0 retention must not silently become false detections.
    pairs = [interval_metrics(h, z) for h in humans for z in zones] if judgment != 'uncertain' else []
    recent = [z for z in zones if 1 <= z['confirmed_k'] <= count]
    complete_human = all(h.get('centroid') is not None for h in humans)
    return {'human_center_count': len(humans), 'all_retained_count': len(zones),
            'all_retained_count_minus_human': len(zones) - len(humans) if judgment != 'uncertain' else None,
            'confirmed_in_visible_window_count': len(recent),
            'window_confirmation_count_minus_human': len(recent) - len(humans) if judgment != 'uncertain' else None,
            'pairs': pairs, 'centroid_fields': ('not_applicable_no_human_centers' if not humans else
                'available' if complete_human else 'unavailable_human_centroid_missing'),
            'human_algorithm_judgments': 'pending',
            'automatic_correct_false_detection_labels': 'not_assigned'}


def overlay_chart(bars, snapshot, case, zones, method, pdf, output, historical_zones=()):
    from matplotlib.patches import Rectangle
    import matplotlib.pyplot as plt
    fig, meta = draw_figure(bars, case['case_id'])
    fig.subplots_adjust(top=.90)
    title = NAMES[method] if method else '你的原始标注'
    fig._suptitle.set_text(case['case_id'] + '｜' + title)
    if method:
        total = len(zones)
        recent = sum(1 <= z['confirmed_k'] <= len(bars) for z in zones)
        fig.text(.5, .936, f'末日保留 {total} 个；窗内新确认且仍保留 {recent} 个｜灰色示意历史终止区间，完整清单另附', ha='center', fontsize=8.5)
    start = snapshot.index - len(bars) + 1
    scale = 100 / bars[0].close
    for ax, panel in zip((fig.axes[0], fig.axes[2]), meta['panels']):
        for i, r in enumerate(case['regions']):
            color = '#9244b3' if r['type'] == 'center' else '#b67611'
            ax.add_patch(Rectangle((r['k_start'] - .5, r['lower']), r['k_end'] - r['k_start'] + 1,
                                  r['upper'] - r['lower'], facecolor='none', edgecolor=color,
                                  linestyle='--' if r['type'] == 'center' else '-.', linewidth=1.6))
            if r['k_end'] >= panel['first_k']:
                ax.text(max(r['k_start'], panel['first_k']), r['upper'],
                        '人工中枢' if r['type'] == 'center' else '人工底部', color=color, fontsize=8, va='bottom', clip_on=True)
            if r['type'] == 'center' and r.get('centroid') is not None:
                ax.hlines(r['centroid'], r['k_start'], r['k_end'], color=color, linestyle=':', linewidth=1)
        if method:
            pivots = snapshot.atr_pivots if method == 'atr_intersection' else snapshot.fixed_pivots
            visible = [p for p in pivots if p.index >= start]
            assert all(p.confirmed_index <= snapshot.index for p in visible)
            ax.plot([p.index - start + 1 for p in visible], [p.price * scale for p in visible],
                    color='#69717c', linewidth=.8, alpha=.75)
            for p in visible:
                ax.scatter(p.confirmed_index - start + 1, p.price * scale, marker='x', s=17, color='#85630a', linewidths=.7)
            terminated = [z for z in historical_zones if not z['valid'] and
                          1 <= z['confirmed_k'] <= len(bars) and z['invalid_k'] is not None and z['invalid_k'] >= 1]
            # Fixed newest-eight display cap, never selected using human overlap.
            for z in sorted(terminated, key=lambda z: z['confirmed_k'])[-8:]:
                left, right = max(panel['first_k'], z['confirmed_k']), min(len(bars), z['invalid_k'])
                if right < left or z['upper'] < panel['p_min'] or z['lower'] > panel['p_max']:
                    continue
                for value, style in ((z['lower'], '-.'), (z['upper'], '-.'), (z['centroid'], ':')):
                    ax.plot([left, right], [value, value], color='#8c8c8c', linestyle=style, alpha=.55, linewidth=.7)
                ax.text(left, z['upper'], z['display_id'], fontsize=6.5, color='#777777', clip_on=True)
            for z in zones:
                left = max(panel['first_k'], z['confirmed_k'])
                if left > len(bars) or z['upper'] < panel['p_min'] or z['lower'] > panel['p_max']:
                    continue
                old = z['confirmed_k'] < 1
                color, alpha = ('#718b9e', .5) if old else ('#126eb3', .95)
                for value, style in ((z['lower'], '--' if old else '-'), (z['upper'], '--' if old else '-'), (z['centroid'], ':')):
                    ax.plot([left, len(bars)], [value, value], linestyle=style, color=color, alpha=alpha, linewidth=.85)
                if not old:
                    ax.text(left, z['upper'], z['display_id'], fontsize=7.5, color=color, va='top', clip_on=True)
        # Overlays never change the original scale, time window or normalization.
        ax.set_xlim(panel['x_min'], panel['x_max'])
        ax.set_ylim(panel['p_min'], panel['p_max'])
    fig.text(.5, .043, '紫框：人工中枢；棕框：人工底部；蓝线：末日保留区间；点线：重心；灰点划线：历史终止（最多8条）', ha='center', fontsize=8)
    fig.text(.5, .030, '算法横段是截点保存的区间，并非逐日重演；灰线为已确认极值连接，× 标确认所在 K；无未来行情', ha='center', fontsize=8)
    fig.savefig(output, dpi=240, metadata={'Software': 'R1 reviewed-case comparison'})
    pdf.savefig(fig)
    plt.close(fig)


def report_lines(case, public=False, reviewed_ids=None):
    cid, human = case['case_id'], case['human']
    reviewed_ids = reviewed_ids or [cid]
    pending = [c for c in CASE_IDS if c not in reviewed_ids]
    lines = [f'# {cid}｜真实人工标注与冻结算法的第一次对照', '',
        '首批已归档标注：' + '、'.join(reviewed_ids) + '。' + ('未评审继续隐藏：' + '、'.join(pending) + '。' if pending else '首批六张均已标注。') + 'B007–B012 暂未展示。',
        '本次是结构识别一致性描述，不是收益验证。参数、独立测试和 PR #2 均不变。', '',
        '## 已收到的人工意见', human['notes'],
        f"中枢 {sum(r['type'] == 'center' for r in human['regions'])} 个，底部区域 {sum(r['type'] == 'bottom' for r in human['regions'])} 个。",
        '人工重心缺失则保持 unavailable，没有用几何中点代填。撤销记录和原始 JSON 完整保留，只取最终状态作本轮对照。', '']
    if not public:
        for r in human['regions']:
            lines.append(f"人工{r['type']}：K{r['k_start']:03d}–K{r['k_end']:03d}，P {r['lower']:.2f}–{r['upper']:.2f}，重心 {r.get('centroid')}。")
    lines += ['', '## 数量与价格区间', '',
        '| 算法 | 全部保留区间 | 窗内新确认 | 窗内新确认与人工中枢的最大价格 IoU |',
        '|---|---:|---:|---:|']
    for method in MAIN_METHODS:
        d = case['methods'][method]
        ids = {z['zone_id'] for z in d['zones'] if 1 <= z['confirmed_k'] <= case.get('bar_count', 180)}
        best = max((pair['price_iou'] for pair in d['pairs'] if pair['zone_id'] in ids), default=None)
        overlap = f'{best:.3f}' if best is not None else 'unavailable'
        lines.append(f"| {NAMES[method]} | {d['all_retained_count']} | {d['confirmed_in_visible_window_count']} | {overlap} |")
    lines += ['',
        'IoU = 两价格区间交集宽度 / 并集宽度；0 为不相交，1 为上下沿完全一致。这里是所有配对的描述，不是原预注册的一对一评分，也不设新的正确阈值。',
        '最大重叠只帮助定位该看的区间，不代表整套算法准确率，不用于按收益选择或改参数。全量配对保留，没有只留最大值。',
        '“窗内新确认”只统计确认 K 落在本可见窗口的区间，是补充口径，不能替换全库存量。人工只看了本窗口；窗前老区间不能仅因数量多就全部判误识别。',
        '人工框表示所见整理/底部范围；算法横线表示截至截点仍保留的中枢及其确认后时段，两者时间含义不同，不把矩形时间 IoU 当成同一指标。',
        'R0 legacy_retained 表示原规则继续保留，不表示支撑有效性已证实。角色转换区间也不一概解释为支撑。', '']
    if not public:
        lines += ['## 全部保留区间清单', '', '| 算法 | 图号 | 归一价格下沿–上沿 | 算法重心 | 形成 K | 确认 K | 状态/角色 |', '|---|---|---|---:|---:|---:|---|']
        for method in MAIN_METHODS:
            for z in case['methods'][method]['zones']:
                lines.append(f"| {NAMES[method]} | {z['display_id']} | {z['lower']:.2f}–{z['upper']:.2f} | {z['centroid']:.2f} | {z['formed_k']} | {z['confirmed_k']} | {z['status']}/{z['role']} |")
        lines += ['', 'K≤0 表示可见窗口之前。Zxx 为该算法全历史编号，不等于当前区间数量。图按原价格范围显示，范围以外区间仍在表中，不删记录。']
    bottom = case['bottom_diagnostics']
    fixed, atr, r0 = (bottom[k] for k in ('fixed_r1', 'atr_r1', 'r0'))
    lines += ['', '## 人工底部区域与二次探底规则',
        '人工底部区域与算法二次探底的含义不同，后者是具体的低–高–低及确认条件。没有触发二底规则不能直接记成“人工底部标错”，也不能把承接区自动视为已通过反转信号。']
    for label, state in [('固定波段 R1', fixed), ('ATR 波段 R1', atr)]:
        if state['first_low_k'] is None:
            lines.append(label + '：没有已确认的低–高–低序列；' + '、'.join(state['reasons']))
            continue
        lines.append(f"{label}：低点 K{state['first_low_k']} → 反弹高点 K{state['rebound_k']} → 低点 K{state['second_low_k']}，第二低点到 K{state['second_low_confirmed_k']} 才确认。第一反弹 {state['first_rebound']:.2%}（要求 8%）；二低相对一低 {state['second_low_difference']:.2%}（允许 ±5%）；两低间隔 {state['second_low_k'] - state['first_low_k']} 根（要求 10）。拒绝原因：" + ('、'.join(state['reasons']) or '无'))
    lines.append(f"R0 原策略底部信号：{'发出' if r0['emitted'] else '未发出'}；逐项拒绝代码：" + ('、'.join(r0['rejections']) or '无') + '。')
    if r0.get('values'):
        v = r0['values']
        pct = lambda x: f'{x:.2%}' if x is not None else 'unavailable'
        num = lambda x: f'{x:.3f}' if x is not None else 'unavailable'
        lines += [f"R0 按原窗口定义的首次探底跌幅 {pct(v['drawdown'])}（要求 30%），反弹 {pct(v['first_rebound'])}（要求 8%），二低差 {pct(v['second_low_difference'])}（允许 ±5%），RR {num(r0['rr'])}（要求 2）。",
            f"R0 下跌能量比 {num(v['down_energy_ratio'])}（要求 ≤0.8）、二低收复 {pct(v['close_over_second_low'])}（要求 ≥6%）、当日收涨 {v['close_rising']}。通过与拒绝项分别保存；R0 与 R1 的跌幅窗口不同，不混用数值。"]
    lines += ['', '## 待你的二次审阅',
        '请对四种算法分别记录：正确、偏高、偏低、遗漏、误识别或不确定，可附对应 Z 编号。算法揭示后的补充与首轮盲标分开保存。当前这些人工正确性判断仍 pending；不由程序代填。',
        f'本单例报告仅描述 {cid} 的位置/数量；首批汇总也不构成跨股票、年份或预测能力的验证。供应商行情仍未核验历史时点版本。']
    return lines


def main():
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument('--annotations', required=True, type=Path)
    p.add_argument('--original-packet', required=True, type=Path)
    p.add_argument('--private-audit', required=True, type=Path)
    p.add_argument('--output', required=True, type=Path)
    p.add_argument('--public', required=True, type=Path)
    p.add_argument('--previous-annotations', type=Path, help='last genuine cumulative export, to distinguish repeated/revised cases')
    args = p.parse_args()
    packet = json.loads((args.original_packet / 'packet_manifest.json').read_text())
    counts = {r['case_id']: r['bar_count'] for r in packet['cases']}
    source = args.annotations.read_bytes()
    payload = json.loads(source)
    reviewed = validate_annotations(payload, counts)
    previous = json.loads(args.previous_annotations.read_bytes()) if args.previous_annotations else None
    changes = upload_changes(payload, previous, counts)
    if not reviewed:
        p.error('no real reviewed samples: no algorithms will be revealed')
    if args.output.exists() or args.public.exists():
        p.error('use new output paths; preserve earlier receipts/results')
    args.output.mkdir(parents=True)
    args.public.mkdir(parents=True)
    (args.output / 'original-annotations.json').write_bytes(source)
    received = datetime.now(timezone.utc).isoformat()
    registry = ROOT / 'research/r1/preregister.json'
    registration = json.loads(registry.read_text())
    audit = json.loads((args.private_audit / 'PRIVATE-source-and-cutoffs.json').read_text())
    frozen = json.loads((ROOT / 'reports/local/r1-s1-structure-final/snapshot-price-details.json').read_text())
    config = Config(**registration['structural_parameters'])
    result, summary, inventory = [], [], []
    os.environ.setdefault('MPLCONFIGDIR', '/tmp/ashare-mobile-mpl')
    os.environ.setdefault('XDG_CACHE_HOME', '/tmp/ashare-mobile-cache')
    from matplotlib.backends.backend_pdf import PdfPages
    for case in reviewed:
        cid = case['case_id']
        entry = next(r for r in audit if r['case_id'] == cid)
        original = next(r for r in packet['cases'] if r['case_id'] == cid)
        assert sha256(args.original_packet / original['image']) == original['sha256']
        data = load_dataset(ROOT, entry['symbol'], False)
        assert data.manifest['sha256'] == entry['csv_sha256']
        bars = visible_window(data, entry['cutoff'], len(data.bars))
        view = bars[-counts[cid]:]
        assert [b.date.isoformat() for b in view] == entry['visible_bar_dates']
        stream = StructureStream(config)
        for b in bars:
            snapshot = stream.update(b)
        old = next(r for r in frozen if r['case_id'] == cid)
        assert json.loads(json.dumps(asdict(snapshot))) == old['snapshot']
        start, scale = len(bars) - len(view), 100 / view[0].close
        human_centers = [r for r in case['regions'] if r['type'] == 'center']
        assessed = [a for a in assess(bars) if a.index == len(bars) - 1 and a.strategy == 'bottom_reversal']
        bottom = {'fixed_r1': bottom_state(bars, snapshot.fixed_pivots, config),
                  'atr_r1': bottom_state(bars, snapshot.atr_pivots, config),
                  'r0': explain_r0_bottom(bars, snapshot.fixed_pivots, snapshot.fixed_legs, assessed[0])}
        # Convert internal indices to the already delivered K numbering, no dates.
        for b in bottom.values():
            for key in list(b):
                if key.endswith('_index'):
                    value = b.pop(key)
                    b[key.replace('_index', '_k')] = value - start + 1 if value is not None else None
        local_case = {'case_id': cid, 'bar_count': len(view), 'human': case, 'methods': {}, 'bottom_diagnostics': bottom}
        public_case = {'case_id': cid, 'human_center_count': len(human_centers),
                       'human_bottom_count': sum(r['type'] == 'bottom' for r in case['regions']),
                       'human_center_judgment': case['center_judgment'], 'methods': {},
                       'bottom_diagnostics': bottom, 'manual_correctness_judgments': 'pending_after_reveal'}
        with PdfPages(args.output / f'{cid}-comparison.pdf', metadata={'Title': cid + ' human-algorithm comparison', 'CreationDate': None, 'ModDate': None}) as pdf:
            paths = [args.output / f'{cid}-human.png']
            overlay_chart(view, snapshot, case, [], None, pdf, paths[-1])
            for method in MAIN_METHODS:
                label = 'ABCD'[masked_methods(cid).index(method)]
                zones, history = [], []
                for j, z in enumerate(sorted(snapshot.zones[method], key=lambda z: z.confirmed_index)):
                    zone = {'zone_id': hashlib.sha256(f'{cid}:{label}:{z.id}'.encode()).hexdigest()[:12],
                            'display_id': f'Z{j + 1:02d}', 'algorithm_label': label,
                            'lower': z.lower * scale, 'upper': z.upper * scale, 'centroid': z.centroid * scale,
                            'formed_k': z.formed_index - start + 1, 'confirmed_k': z.confirmed_index - start + 1,
                            'confirmation_delay': z.confirmed_index - z.formed_index,
                            'status': z.status, 'role': z.role, 'valid': z.valid,
                            'invalid_k': z.invalid_index - start + 1 if z.invalid_index is not None else None,
                            'last_test_k': z.last_test_index - start + 1 if z.last_test_index is not None else None,
                            'atr_units': snapshot.atr * scale if snapshot.atr else None}
                    history.append(zone)
                    if not z.valid:
                        continue
                    zones.append(zone)
                    inventory.append({'case_id': cid, 'method': method, **zone})
                description = describe_method(human_centers, zones, len(view), case['center_judgment'])
                local_case['methods'][method] = {'zones': zones, 'all_zone_history': history, **description}
                public_case['methods'][method] = description
                paths.append(args.output / f'{cid}-{method}.png')
                overlay_chart(view, snapshot, case, zones, method, pdf, paths[-1], history)
                # Do not assign centroid errors to uncertain/no-center judgments.
                public_case['methods'][method]['comparison_scope'] = case['center_judgment']
                if case['center_judgment'] == 'uncertain':
                    public_case['methods'][method]['pairs'] = []
                    public_case['methods'][method]['human_algorithm_judgments'] = 'deferred_uncertain'
        summary.append(public_case)
        result.append(local_case)
    write_json(args.output / 'comparison-full.json', result)
    write_json(args.output / 'all-retained-zones.json', inventory)
    write_json(args.public / 'comparison-derived.json', summary)
    for case in result:
        (args.output / (case['case_id'] + '-report.md')).write_text('\n'.join(report_lines(case, reviewed_ids=[c['case_id'] for c in reviewed])) + '\n')
        (args.public / (case['case_id'] + '-report.md')).write_text('\n'.join(report_lines(case, public=True, reviewed_ids=[c['case_id'] for c in reviewed])) + '\n')
    receipt = {'input_sha256': hashlib.sha256(source).hexdigest(), 'received_at_utc': received,
               'exported_at_user_device': payload.get('exported_at'), 'input_bytes': len(source),
               'history_entries_preserved': len(payload['history']), 'source_origin': 'user_attachment',
               'reviewed_case_ids': [c['case_id'] for c in reviewed],
               'withheld_case_ids': [c['case_id'] for c in payload['cases'] if not c['reviewed']],
               'code_base_commit': subprocess.check_output(['git', 'rev-parse', 'HEAD'], cwd=ROOT, text=True).strip(),
               'preregister_sha256': sha256(registry), 'frozen_snapshot_reproduced': True,
               'new_parameter_searches': 0, 'new_model_fits': 0, 'independent_test_outcomes_computed': 0,
               'matching': 'all-pairs descriptive interval overlap; not frozen one-to-one scoring; no correctness assigned',
               'human_centroids_imputed': 0, 'files': [{'name': p.name, 'sha256': sha256(p)} for p in sorted(args.output.iterdir()) if p.is_file()]}
    receipt['upload_changes'] = changes
    receipt['previous_annotations_sha256'] = sha256(args.previous_annotations) if args.previous_annotations else None
    receipt['historical_display'] = 'newest eight terminated zones confirmed in visible window; full history retained locally'
    receipt['working_tree_dirty'] = bool(subprocess.check_output(['git', 'status', '--porcelain'], cwd=ROOT, text=True))
    receipt['source_code_sha256'] = {str(p.relative_to(ROOT)): sha256(p) for p in [Path(__file__), ROOT / 'research/r1/mobile_review.py'] + list((ROOT / 'src/ashare_quant/r1').glob('*.py'))}
    write_json(args.public / 'receipt.json', receipt)
    print(json.dumps({'reviewed_and_revealed': receipt['reviewed_case_ids'], 'unreviewed_and_withheld': receipt['withheld_case_ids'],
                      'raw_input_preserved': True, 'human_centroids_imputed': 0}))


if __name__ == '__main__':
    main()
