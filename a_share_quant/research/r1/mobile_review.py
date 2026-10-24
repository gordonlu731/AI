"""Prepare the first six EXISTING blind cases, with no algorithm/result payload.

Only presentation changes: strategy modules, registry, sample order and sealed
outcomes are untouched. Price-bearing outputs stay in ignored local directories.
"""
from __future__ import annotations

import argparse
import base64
import csv
import json
import os
import sys
import zipfile
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / 'src'))
from ashare_quant.data import session_segments, sha256
from ashare_quant.r1.io import load_dataset, write_json
from ashare_quant.r1.review import select_blind_samples

BATCH_ID = 'R1-human-B001-B006-v1'


def visible_window(dataset, cutoff: str, history=180):
    if history < 1:
        raise ValueError('history must be positive')
    index = next((i for i, b in enumerate(dataset.bars) if b.date.isoformat() == cutoff), None)
    if index is None:
        raise ValueError('registered cutoff is unavailable; never substitute another date')
    prefix = dataset.bars[:index + 1]
    calendar = [d for d in dataset.calendar if d.isoformat() <= cutoff]
    segment = next(((a, end) for a, end in session_segments(prefix, calendar) if a <= index < end), None)
    if segment is None:
        raise ValueError('cutoff is not in a positive-volume segment; never fill missing bars')
    return prefix[segment[0]:][-history:]


def draw_figure(bars, case_id):
    """No pivots/centers/algorithms/real dates/names or forward labels accepted."""
    os.environ.setdefault('MPLCONFIGDIR', '/tmp/ashare-mobile-mpl')
    os.environ.setdefault('XDG_CACHE_HOME', '/tmp/ashare-mobile-cache')
    import matplotlib
    matplotlib.use('Agg')
    import matplotlib.pyplot as plt
    from matplotlib import font_manager
    from matplotlib.patches import Rectangle
    font = Path('/usr/share/fonts/opentype/noto/NotoSansCJK-Regular.ttc')
    if font.exists():
        font_manager.fontManager.addfont(str(font))
        plt.rcParams['font.family'] = font_manager.FontProperties(fname=str(font)).get_name()
    plt.rcParams['axes.unicode_minus'] = False
    fig = plt.figure(figsize=(9, 14), dpi=240, facecolor='white')
    grid = fig.add_gridspec(11, 1, hspace=.65)
    n, anchor = len(bars), bars[0].close
    definitions = [('main', 0, fig.add_subplot(grid[0:4]), fig.add_subplot(grid[4:5])),
                   ('detail', max(0, n - 60), fig.add_subplot(grid[6:10]), fig.add_subplot(grid[10:11]))]
    panels = []
    for name, start, price, volume in definitions:
        view = bars[start:]
        mean_volume = sum(b.volume for b in bars) / n
        for j, b in enumerate(view, start=start + 1):
            scale = 100 / anchor
            color = '#bc3838' if b.close >= b.open else '#17846f'
            price.vlines(j, b.low * scale, b.high * scale, color=color, linewidth=1.05)
            bottom, height = min(b.open, b.close) * scale, abs(b.close - b.open) * scale
            price.add_patch(Rectangle((j - .32, bottom), .64, max(height, .012), facecolor=color, edgecolor=color, linewidth=.5))
            volume.bar(j, b.volume / mean_volume if mean_volume > 0 else 0, width=.65, color=color)
        low = min(b.low for b in view) * 100 / anchor
        high = max(b.high for b in view) * 100 / anchor
        padding = max((high - low) * .07, .5)
        price.set_ylim(low - padding, high + padding)
        price.set_xlim(start + .25, n + .75)
        volume.set_xlim(price.get_xlim())
        ticks = sorted(set([start + 1] + list(range(((start + 10) // 10) * 10, n + 1, 10)) + [n]))
        if len(ticks) > 12:
            ticks = ticks[::2] + ([n] if ticks[-1] != n else [])
        price.set_xticks(ticks, [f'K{x:03d}' for x in ticks], fontsize=10)
        volume.set_xticks(ticks, [f'K{x:03d}' for x in ticks], fontsize=10)
        price.tick_params(axis='y', labelsize=12)
        volume.tick_params(axis='y', labelsize=10)
        price.set_ylabel('P｜归一价格', fontsize=12)
        volume.set_ylabel('相对量', fontsize=10)
        price.grid(alpha=.19, linewidth=.6)
        volume.grid(axis='y', alpha=.15)
        title = f'完整窗口 K001–K{n:03d}' if name == 'main' else f'同一数据放大 K{start + 1:03d}–K{n:03d}'
        price.set_title(title, loc='left', fontsize=14, pad=10)
        panels.append((name, price, start + 1, n))
    fig.suptitle(case_id, fontsize=23, fontweight='bold', y=.987)
    fig.text(.5, .955, '红：收盘≥开盘　绿：收盘<开盘　｜　只含截点以前的日 K 与成交量', ha='center', fontsize=10)
    fig.text(.5, .018, 'P 以完整窗口第一根收盘=100；上下窗口坐标一致。可标多个区域，也可判断不明确。', ha='center', fontsize=10)
    fig.subplots_adjust(left=.14, right=.96, top=.92, bottom=.07)
    fig.canvas.draw()
    width, height = fig.canvas.get_width_height()
    mapping = []
    for name, ax, first, last in panels:
        bbox = ax.get_window_extent()
        mapping.append({'name': name, 'left': bbox.x0, 'right': bbox.x1, 'top': height - bbox.y1, 'bottom': height - bbox.y0,
                        'x_min': ax.get_xlim()[0], 'x_max': ax.get_xlim()[1], 'p_min': ax.get_ylim()[0], 'p_max': ax.get_ylim()[1],
                        'first_k': first, 'last_k': last})
    return fig, {'case_id': case_id, 'width': width, 'height': height, 'bar_count': n, 'panels': mapping}


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--output', type=Path, required=True)
    parser.add_argument('--audit', type=Path, required=True, help='private ignored audit directory, never included in packet')
    args = parser.parse_args()
    args.output.mkdir(parents=True, exist_ok=False)
    args.audit.mkdir(parents=True, exist_ok=False)
    registration = json.loads((ROOT / 'research/r1/preregister.json').read_text())
    selected = select_blind_samples(registration)[:6]
    if [x[0] for x in selected] != [f'B{i:03d}' for i in range(1, 7)]:
        raise ValueError('frozen case ordering changed')
    old_key = json.loads((ROOT / 'reports/local/r1-s1-structure-final/PRIVATE-unblinding-key.json').read_text())
    mapping = {r['case_id']: (r['symbol'], r['asof']) for r in old_key}
    os.environ.setdefault('MPLCONFIGDIR', '/tmp/ashare-mobile-mpl')
    os.environ.setdefault('XDG_CACHE_HOME', '/tmp/ashare-mobile-cache')
    from matplotlib.backends.backend_pdf import PdfPages
    import matplotlib.pyplot as plt
    payload, private_audit, shared_manifest = [], [], []
    with PdfPages(args.output / 'first-six-blank-mobile.pdf', metadata={'Title': BATCH_ID, 'Author': '', 'CreationDate': None, 'ModDate': None}) as pdf:
        for case_id, symbol, cutoff in selected:
            if mapping.get(case_id) != (symbol, cutoff):
                raise ValueError('original review mapping mismatch')
            data = load_dataset(ROOT, symbol, False)
            bars = visible_window(data, cutoff)
            if bars[-1].date.isoformat() != cutoff:
                raise ValueError('cutoff mismatch')
            fig, neutral = draw_figure(bars, case_id)
            path = args.output / f'{case_id}.png'
            fig.savefig(path, dpi=240, metadata={'Software': 'R1 human review'})
            pdf.savefig(fig)
            plt.close(fig)
            neutral['image'] = 'data:image/png;base64,' + base64.b64encode(path.read_bytes()).decode()
            payload.append(neutral)
            shared_manifest.append({'case_id': case_id, 'order': len(payload), 'bar_count': len(bars), 'image': path.name, 'sha256': sha256(path),
                                    'algorithm_overlay': False, 'future_bars': False})
            private_audit.append({'case_id': case_id, 'symbol': symbol, 'cutoff': cutoff, 'first_visible_date': bars[0].date.isoformat(),
                                  'csv_sha256': data.manifest['sha256'], 'point_in_time_verified': False,
                                  'visible_bar_dates': [b.date.isoformat() for b in bars], 'image_sha256': sha256(path)})
    template = (ROOT / 'research/r1/mobile_annotator.html').read_text()
    html = template.replace('__REVIEW_DATA__', json.dumps({'batch_id': BATCH_ID, 'cases': payload}, ensure_ascii=False).replace('</', r'<\/'))
    (args.output / '手机标注.html').write_text(html, encoding='utf-8')
    write_json(args.output / 'packet_manifest.json', {'batch_id': BATCH_ID, 'schema': 'r1-human-batch1-v1', 'cases': shared_manifest,
                'review_stage': 'human_only', 'algorithm_comparison': 'withheld_until_real_annotations', 'source': 'unverified vendor snapshot'})
    instructions = '''首批顺序 B001 → B002 → B003 → B004 → B005 → B006，不重新抽样。
每张上图为完整窗口，下图为同一数据末段放大，K 编号和 P 坐标一致。
方法一：直接看 PNG/PDF，用手机截图画多个框并写“中枢1/中枢2/底部1”。
方法二：下载“手机标注.html”用浏览器打开，选中枢/底部后拖框；支持多个框、手填坐标、无明确中枢、不确定、撤销以及导出 JSON/CSV。
Android 若不能打开本地 HTML，可直接截图或在会话回复 K起–K止、P下–P上、重心（可不填）。不要把缺少标注当作没有中枢。
你完成一张或多张后，回传截图、文字或导出的 JSON。只对收到真实标注的样本展示四种算法，不提前揭示其他样本。
示例格式（占位符，不是提示答案）：B001：中枢1 K起–K止/P下–P上；中枢2…；底部1…；或“没有明确中枢”。
所有人工标注和修改保留，不根据未来收益选择。图中不含股票名称、真实日期、算法标记或未来结果。
'''
    (args.output / '使用说明.txt').write_text(instructions, encoding='utf-8')
    with (args.output / '人工区域表.csv').open('w', newline='', encoding='utf-8-sig') as f:
        w = csv.writer(f, lineterminator='\n')
        w.writerow(['case_id', 'reviewed', 'center_judgment', 'bottom_judgment', 'region_id', 'type', 'k_start', 'k_end', 'lower', 'upper', 'centroid', 'notes'])
        for case_id, _, _ in selected:
            w.writerow([case_id, 'no', 'unreviewed', 'unreviewed'] + [''] * 8)
    write_json(args.audit / 'PRIVATE-source-and-cutoffs.json', private_audit)
    packet = args.output.parent / (args.output.name + '.zip')
    with zipfile.ZipFile(packet, 'w', zipfile.ZIP_DEFLATED) as z:
        for p in sorted(args.output.iterdir()):
            if p.is_file():
                z.write(p, p.name)
    print(json.dumps({'batch_id': BATCH_ID, 'case_ids': [r[0] for r in selected], 'output': str(args.output), 'zip': str(packet),
                      'dimensions': [[r['width'], r['height']] for r in payload], 'private_audit_in_packet': False}, ensure_ascii=False))


if __name__ == '__main__':
    main()
