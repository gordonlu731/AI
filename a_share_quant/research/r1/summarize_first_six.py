"""Descriptive first-six human agreement; no outcome computation or fitting."""
from __future__ import annotations
import argparse
import base64
import csv
import hashlib
import json
import os
import statistics
import sys
from pathlib import Path

from review_feedback import ROOT, CASE_IDS, NAMES, MAIN_METHODS, interval_metrics
from mobile_review import visible_window
from ashare_quant.r1.io import load_dataset, write_json
from ashare_quant.data import sha256

SCOPES = ('end_inventory', 'end_window', 'historical_window')


def candidates(zones, scope, count, human=None):
    if scope == 'end_inventory':
        return [z for z in zones if z['valid']]
    if scope == 'end_window':
        return [z for z in zones if z['valid'] and 1 <= z['confirmed_k'] <= count]
    if scope != 'historical_window':
        raise ValueError('unknown comparison scope')
    eligible = [z for z in zones if 1 <= z['confirmed_k'] <= count]
    if human is not None:
        eligible = [z for z in eligible if z['confirmed_k'] <= human['k_end'] and
                    (z['invalid_k'] if z['invalid_k'] is not None else count) >= human['k_start']]
    return eligible


def region_description(human, zones):
    pairs = [interval_metrics(human, z) for z in zones]
    best = sorted(pairs, key=lambda x: (-x['price_iou'], x['zone_id']))[0] if pairs else None
    return {'human_region_id': human['region_id'], 'candidate_count': len(zones), 'pairs': pairs,
            'maximum_price_iou': best['price_iou'] if best else None,
            'best_positive_overlap': best if best and best['price_iou'] > 0 else None,
            'no_candidate': not zones,
            'candidates_but_no_positive_price_overlap': bool(best is not None and best['price_iou'] == 0)}


def aggregate_regions(rows):
    values = [r['maximum_price_iou'] for r in rows if r['maximum_price_iou'] is not None]
    matched = [r['best_positive_overlap'] for r in rows if r['best_positive_overlap'] is not None]
    median = lambda xs: statistics.median(xs) if xs else None
    return {'human_region_denominator': len(rows), 'with_candidate': len(values),
            'without_candidate': sum(r['no_candidate'] for r in rows),
            'candidates_but_no_positive_price_overlap': sum(r['candidates_but_no_positive_price_overlap'] for r in rows),
            'positive_overlap': len(matched), 'median_maximum_iou_given_candidate': median(values),
            'maximum_iou_values_given_candidate': values,
            'positive_overlap_edge_denominator': len(matched),
            'median_width_ratio_given_positive_overlap': median([r['width_ratio'] for r in matched]),
            'median_lower_delta_human_width': median([r['lower_delta_human_width'] for r in matched]),
            'median_upper_delta_human_width': median([r['upper_delta_human_width'] for r in matched]),
            'narrower_than_human': sum(r['width_ratio'] < 1 for r in matched),
            'wider_than_human': sum(r['width_ratio'] > 1 for r in matched),
            'both_edges_higher': sum(r['lower_delta_human_width'] > 0 and r['upper_delta_human_width'] > 0 for r in matched),
            'both_edges_lower': sum(r['lower_delta_human_width'] < 0 and r['upper_delta_human_width'] < 0 for r in matched),
            'all_edges_are_descriptive_not_human_error_labels': True}


def summarize(cases, stock_groups):
    if [c['case_id'] for c in cases] != CASE_IDS or not all(c['human']['reviewed'] for c in cases):
        raise ValueError('six distinct completed first reviews required before aggregation')
    records, methods = [], {}
    for c in cases:
        humans = [r for r in c['human']['regions'] if r['type'] == 'center']
        row = {'case_id': c['case_id'], 'human_center_count': len(humans),
               'human_bottom_count': sum(r['type'] == 'bottom' for r in c['human']['regions']),
               'human_center_judgment': c['human']['center_judgment'], 'methods': {}}
        for method in MAIN_METHODS:
            history = c['methods'][method]['all_zone_history']
            row['methods'][method] = {}
            for scope in SCOPES:
                zs = candidates(history, scope, c['bar_count'])
                row['methods'][method][scope] = {'case_candidate_inventory_count': len(zs),
                    'human_regions': [region_description(h, candidates(history, scope, c['bar_count'], h)) for h in humans],
                    'manual_none_algorithm_output_disagreement': c['human']['center_judgment'] == 'none' and bool(zs)}
        records.append(row)
    for method in MAIN_METHODS:
        methods[method] = {}
        for scope in SCOPES:
            rows = [h for c in records for h in c['methods'][method][scope]['human_regions']]
            methods[method][scope] = {**aggregate_regions(rows),
                'case_inventory_counts': {c['case_id']: c['methods'][method][scope]['case_candidate_inventory_count'] for c in records},
                'manual_none_disagreement_case_ids': [c['case_id'] for c in records if c['methods'][method][scope]['manual_none_algorithm_output_disagreement']]}
    return {'status': 'descriptive_first_six_complete_manual_algorithm_judgments_pending',
        'unique_first_review_cases': 6, 'registered_cases_total': 12, 'withheld_cases': [f'B{i:03d}' for i in range(7, 13)],
        'stock_group_count': stock_groups, 'cases_are_not_independent_stock_samples': True,
        'human_center_regions': sum(c['human_center_count'] for c in records),
        'human_bottom_regions': sum(c['human_bottom_count'] for c in records),
        'manual_none_case_ids': [c['case_id'] for c in records if c['human_center_judgment'] == 'none'],
        'human_centroid_errors': 'unavailable_not_imputed', 'manual_correctness_judgments': 'pending',
        'scopes': list(SCOPES), 'methods': methods, 'cases': records,
        'new_fits': 0, 'parameter_searches': 0, 'independent_test_outcomes_computed': 0}


def draw_overview(case, bars, output):
    import matplotlib.pyplot as plt
    from matplotlib.patches import Rectangle
    fig = plt.figure(figsize=(9, 15), dpi=240, facecolor='white')
    grid = fig.add_gridspec(5, 1, height_ratios=[3, 3, 3, 3, .9], hspace=.50)
    n, scale = len(bars), 100 / bars[0].close
    low, high = min(b.low for b in bars) * scale, max(b.high for b in bars) * scale
    pad = max(.5, (high - low) * .07)
    for m, method in enumerate(MAIN_METHODS):
        ax = fig.add_subplot(grid[m])
        for j, b in enumerate(bars, 1):
            color = '#bc3838' if b.close >= b.open else '#17846f'
            ax.vlines(j, b.low * scale, b.high * scale, color=color, linewidth=.7)
            ax.add_patch(Rectangle((j - .32, min(b.open, b.close) * scale), .64,
                max(abs(b.close - b.open) * scale, .012), facecolor=color, edgecolor=color, linewidth=.3))
        for r in case['human']['regions']:
            color = '#9244b3' if r['type'] == 'center' else '#b67611'
            ax.add_patch(Rectangle((r['k_start'] - .5, r['lower']), r['k_end'] - r['k_start'] + 1,
                r['upper'] - r['lower'], facecolor='none', edgecolor=color,
                linestyle='--' if r['type'] == 'center' else '-.', linewidth=1.3))
        history = case['methods'][method]['all_zone_history']
        for z in history:
            left = max(1, z['confirmed_k'])
            right = n if z['invalid_k'] is None else min(n, z['invalid_k'])
            if right < left or z['upper'] < low - pad or z['lower'] > high + pad:
                continue
            if not z['valid'] and z['confirmed_k'] < 1:
                continue
            old = z['confirmed_k'] < 1
            color = '#126eb3' if z['valid'] and not old else '#718b9e' if z['valid'] else '#999999'
            for value, style in ((z['lower'], '-' if z['valid'] and not old else '-.'),
                                 (z['upper'], '-' if z['valid'] and not old else '-.'), (z['centroid'], ':')):
                ax.plot([left, right], [value, value], color=color, linestyle=style,
                        linewidth=.8 if z['valid'] else .6, alpha=.9 if z['valid'] and not old else .45)
            if 1 <= z['confirmed_k'] <= n:
                ax.text(left, z['upper'], z['display_id'], color=color, fontsize=6.5, clip_on=True)
        count = len(case['methods'][method]['zones'])
        recent = sum(1 <= z['confirmed_k'] <= n for z in case['methods'][method]['zones'])
        ax.set_title(f'{NAMES[method]}｜末日保留 {count}，其中窗内新确认 {recent}', loc='left', fontsize=12)
        ax.set_xlim(.25, n + .75); ax.set_ylim(low - pad, high + pad)
        ticks = sorted(set([1] + list(range(20, n + 1, 20)) + [n]))
        ax.set_xticks(ticks, [f'K{x:03d}' for x in ticks], fontsize=8)
        ax.set_ylabel('P', fontsize=10); ax.tick_params(axis='y', labelsize=9); ax.grid(alpha=.15)
    ax = fig.add_subplot(grid[4])
    mean = sum(b.volume for b in bars) / n
    ax.bar(range(1, n + 1), [b.volume / mean for b in bars], width=.65,
           color=['#bc3838' if b.close >= b.open else '#17846f' for b in bars])
    ax.set_xlim(.25, n + .75); ax.set_ylabel('相对量', fontsize=9)
    ax.set_xticks(ticks, [f'K{x:03d}' for x in ticks], fontsize=8)
    fig.suptitle(case['case_id'] + '｜四算法与人工原框', y=.99, fontsize=20, fontweight='bold')
    fig.text(.5, .962, '紫框：人工中枢；棕框：局部底部/承接区域；蓝线：末日保留；灰线：历史终止', ha='center', fontsize=9)
    fig.text(.5, .944, '同一截止点与 K/P 基准；灰线为截点保存几何的回顾对照，不是逐日信号重放', ha='center', fontsize=8.5)
    fig.text(.5, .018, '无股票身份、真实日期或未来行情；点线为算法重心，人工重心未填；详图含已确认波段与确认延迟', ha='center', fontsize=8)
    fig.subplots_adjust(left=.12, right=.97, top=.91, bottom=.06)
    fig.savefig(output, dpi=240, metadata={'Software': 'R1 first-six descriptive review'})
    plt.close(fig)


def report(summary):
    s = summary
    lines = ['# R1 首批六张人工结构对照汇总', '',
        '**首次盲标 6/6 已完成；原 12 组仍有后六组未展示。** 本次新增 B002–B006，B001 未变，不重复计数。',
        f"共 {s['human_center_regions']} 个中枢、{s['human_bottom_regions']} 个局部底部/承接区域；B002 明确无中枢。所有人工重心未填，原件 133 条历史保留。",
        '结构算法/代码测试已完成；现在完成的是首批人工框收集与描述性位置对照。算法正确性判断仍 pending，投资有效性未验证。', '',
        '## 比较口径',
        '事先记录的 [汇总口径](../../../docs/r1/first_six_review_protocol.md) 同时保留末日全库存、末日有效且窗内新确认、历史阶段补充对照。全部配对保留，最大重叠不是一对一召回率，也没有人为正确阈值。',
        '以下表的 IoU 是价格区间交集/并集，1 为边界相同；— 为没有该范围的候选，不是零分。多个手工中枢逐个保留。', '']
    for scope, title in [('end_window', '末日仍保留、且窗内新确认的候选'), ('historical_window', '曾在人工阶段存续的历史候选（含随后失效）')]:
        lines += ['## ' + title, '', '| 人工框 | R0 | ATR | 密集区 | 承接区 |', '|---|---:|---:|---:|---:|']
        for c in s['cases']:
            rows = c['methods'][MAIN_METHODS[0]][scope]['human_regions']
            for i, row in enumerate(rows):
                vals = []
                for method in MAIN_METHODS:
                    v = c['methods'][method][scope]['human_regions'][i]['maximum_price_iou']
                    vals.append(f'{v:.3f}' if v is not None else '—')
                lines.append('| ' + c['case_id'] + '/' + row['human_region_id'] + ' | ' + ' | '.join(vals) + ' |')
        lines += ['', '| 算法 | 有候选的人工框/6 | 无候选 | 有候选但无价格交集 | 正重叠候选中较人工框窄/分母 |', '|---|---:|---:|---:|---:|']
        for method in MAIN_METHODS:
            m = s['methods'][method][scope]
            lines.append(f"| {NAMES[method]} | {m['with_candidate']}/6 | {m['without_candidate']} | {m['candidates_but_no_positive_price_overlap']} | {m['narrower_than_human']}/{m['positive_overlap_edge_denominator']} |")
        lines.append('')
    lines += ['## 无中枢的负例 B002', '', '| 算法 | 末日全库存 | 末日且窗内新确认 | 窗内历史曾确认 |', '|---|---:|---:|---:|']
    for method in MAIN_METHODS:
        c = next(c for c in s['cases'] if c['case_id'] == 'B002')['methods'][method]
        lines.append('| ' + NAMES[method] + ' | ' + ' | '.join(str(c[x]['case_candidate_inventory_count']) for x in SCOPES) + ' |')
    lines += ['', '算法输出与人工“无中枢”存在分歧的区间必须保留，不能只挑有重叠的成功案例；是否属于误识别，需用户看到具体算法框后评价。', '',
        '## 结构分歧的核查方向',
        '- 历史留存：核对 R0 大量窗前区间是否仍应作为当前结构。全库存数量差不是直接误识别数。',
        '- 生命周期：历史阶段与末日候选的差别单独报告，不把后来失效/到期全记成当时遗漏；灰线也不代表可交易有效。',
        '- 宽度与拆分：人工大框和算法多个窄框可能描述不同尺度；B005 两个独立人工中枢分别比较，不能只取一个最好配对代替。',
        '- 上下位置：全部配对记录上下沿差/人工宽度；没有正重叠时不从任意区间生成偏高/偏低标签，缺重心不造重心误差。', '',
        '## 底部与多空力量备注',
        '11 个底部框可以是局部止跌或中枢下沿承接，不等于 11 次双底反转信号。原 R0 与固定/ATR 二底条件逐样本保留。B001 在底部语义澄清前标注，其余在澄清后；不事后强行赋予同一底部子类。',
        'B002“空头强、多头未强”和 B005“疑似双顶、后续突破/跌破条件”均作为用户当前图上的主观/条件性假设保留；没有使用未来行情验证或改参数。', '',
        '## 验证边界与下一步',
        f"首批 6 个截点仅覆盖 {s['stock_group_count']} 个股票组，同股截点有关联，不能当 6 只独立股票或全市场证据。没有显著性检验、收益实验、模型拟合或参数搜索。",
        '尚未得到用户对算法正确/偏高/偏低/遗漏/误识别的揭示后判断；本报告只列结构分歧，不自动授予“正确”或“错误”。不据此宣称某算法优胜或 H1 已成立。',
        '建议先审 B002 的无中枢分歧和 B005 的两层中枢，再按用户反馈补充真实错误记录；B007–B012 继续保持未展示，独立测试封存，PR #2 不合并。',
        '本地价格图/完整坐标/原 JSON 不发布 Git。公开保存本报告、派生配对、口径和校验和；手机可直接看会话概览图或下载 30 页详图 PDF。']
    return '\n'.join(lines) + '\n'


def main():
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument('--feedback', type=Path, required=True)
    p.add_argument('--public', type=Path, required=True)
    p.add_argument('--private-audit', type=Path, required=True)
    args = p.parse_args()
    cases = json.loads((args.feedback / 'comparison-full.json').read_text())
    audit = json.loads((args.private_audit / 'PRIVATE-source-and-cutoffs.json').read_text())
    groups = len({r['symbol'] for r in audit if r['case_id'] in CASE_IDS})
    s = summarize(cases, groups)
    for name in ['agreement-summary.json', 'README.md']:
        if (args.public / name).exists(): p.error('preserve existing summary, choose new paths')
    write_json(args.public / 'agreement-summary.json', s)
    markdown = report(s)
    (args.public / 'README.md').write_text(markdown)
    (args.feedback / '首批六张汇总.md').write_text(markdown)
    os.environ.setdefault('MPLCONFIGDIR', '/tmp/ashare-mobile-mpl')
    os.environ.setdefault('XDG_CACHE_HOME', '/tmp/ashare-mobile-cache')
    import matplotlib
    matplotlib.use('Agg')
    from matplotlib import font_manager
    font = Path('/usr/share/fonts/opentype/noto/NotoSansCJK-Regular.ttc')
    font_manager.fontManager.addfont(str(font))
    matplotlib.rcParams['font.family'] = font_manager.FontProperties(fname=str(font)).get_name()
    matplotlib.rcParams['axes.unicode_minus'] = False
    images = []
    for case in cases:
        entry = next(r for r in audit if r['case_id'] == case['case_id'])
        dataset = load_dataset(ROOT, entry['symbol'], False)
        bars = visible_window(dataset, entry['cutoff'])
        assert [b.date.isoformat() for b in bars] == entry['visible_bar_dates']
        path = args.feedback / (case['case_id'] + '-overview.png')
        draw_overview(case, bars, path)
        images.append(path)
    from pypdf import PdfWriter
    writer = PdfWriter()
    for cid in CASE_IDS: writer.append(args.feedback / (cid + '-comparison.pdf'))
    writer.write(args.feedback / 'first-six-comparisons.pdf')
    with (args.feedback / 'all-historical-window-zones.csv').open('w',newline='',encoding='utf-8-sig') as f:
        rows = [{'case_id': c['case_id'], 'method': m, **z} for c in cases for m in MAIN_METHODS
                for z in c['methods'][m]['all_zone_history'] if 1 <= z['confirmed_k'] <= c['bar_count']]
        w = csv.DictWriter(f, fieldnames=list(rows[0])); w.writeheader(); w.writerows(rows)
    html = '<!doctype html><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1"><title>首批六张四算法对照</title><style>body{font-family:system-ui;margin:10px}img{width:100%;height:auto}h2{padding-top:10px}</style><h1>首批六张已标注案例对照</h1><p>紫框：人工中枢；棕框：底部区域；蓝：末日保留；灰：历史终止。均无未来行情。可截图反馈。</p>'
    for path in images:
        html += '<h2>' + path.stem.split('-')[0] + '</h2><img src="data:image/png;base64,' + base64.b64encode(path.read_bytes()).decode() + '">'
    (args.feedback / '六张算法对照.html').write_text(html)
    write_json(args.public / 'summary-artifacts.json', {'source_script_sha256': sha256(Path(__file__)),
        'protocol_sha256': sha256(ROOT / 'docs/r1/first_six_review_protocol.md'),
        'images': [{'name': x.name, 'sha256': sha256(x)} for x in images],
        'combined_pdf_sha256': sha256(args.feedback / 'first-six-comparisons.pdf'),
        'local_only': True, 'human_correctness_judgments': 'pending'})
    print(json.dumps({'first_blind_review_complete':6,'human_centers':s['human_center_regions'],
        'human_bottoms':s['human_bottom_regions'],'stock_groups':groups,'combined_pdf_pages':30,'manual_algorithm_judgments':'pending'}))


if __name__ == '__main__': main()
