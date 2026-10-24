"""Separate known-case structural diagnosis. No independent-test labels or fits."""
from __future__ import annotations

import argparse
import json
import os
import sys
import textwrap
from dataclasses import asdict
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / 'src'))
from ashare_quant.data import read_bars, read_calendar, adjust_bars, session_segments, sha256
from ashare_quant.strategy import assess_sessions
from ashare_quant.r1.structures import Config, StructureStream, reference_zone
from ashare_quant.r1.features import feature_row, bottom_state
from ashare_quant.r1.io import write_json, write_csv
from ashare_quant.r1.review import MAIN_METHODS, render_chart


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--data', type=Path, required=True)
    parser.add_argument('--output', type=Path, required=True)
    parser.add_argument('--public', type=Path, required=True)
    args = parser.parse_args()
    args.output.mkdir(parents=True, exist_ok=False)
    args.public.mkdir(parents=True, exist_ok=False)
    manifest = json.loads((args.data / 'sz002349.manifest.json').read_text())
    if sha256(args.data / 'sz002349.csv') != manifest['sha256'] or sha256(args.data / 'calendar.csv') != manifest['calendar_sha256']:
        raise ValueError('known-case source checksum mismatch')
    raw = read_bars(args.data / 'sz002349.csv')
    bars, calendar = adjust_bars(raw), read_calendar(args.data / 'calendar.csv')
    if bars[-1].date.isoformat() != '2026-10-23':
        raise ValueError('unexpected known-case cutoff; never substitute missing days')
    registration = json.loads((ROOT / 'research/r1/preregister.json').read_text())
    config = Config(**registration['structural_parameters'])
    cutoffs = ['2026-09-01', '2026-09-15', '2026-09-30', '2026-10-15', '2026-10-23']
    r0 = {(a.date, a.strategy): a for a in assess_sessions(bars, calendar)}
    rows, snapshots, selected = [], [], []
    anchor = next(b.close for b in bars if b.date.isoformat() == '2026-09-01')
    previous = {b.date: b for b in read_bars(ROOT / 'data/processed/sina-2026-10-22/sz002349.csv')}
    differences = [b.date.isoformat() for b in raw if '2026-09-01' <= b.date.isoformat() <= '2026-10-22' and b.date in previous and b != previous[b.date]]
    for first, end in session_segments(bars, calendar):
        stream = StructureStream(config)
        last_breakout = None
        for bar in bars[first:end]:
            snapshot = stream.update(bar)
            day = bar.date.isoformat()
            prior20 = stream.bars[-21:-1]
            relative = bar.volume / (sum(x.volume for x in prior20) / 20) if len(prior20) == 20 and sum(x.volume for x in prior20) else None
            breakout = bool(relative is not None and relative >= 1.5 and bar.close > max(x.high for x in prior20))
            if breakout:
                last_breakout = day
            if not '2026-09-01' <= day <= '2026-10-23':
                continue
            trend, bottom = r0.get((day, 'trend_pullback')), r0.get((day, 'bottom_reversal'))
            record = {'date': day, 'close_index_sep01': bar.close / anchor * 100,
                'relative_volume_prior20': relative, 'volume_breakout': breakout, 'last_breakout': last_breakout,
                'r0_trend_signal': trend.emitted if trend else False,
                'r0_trend_rejections': list(trend.reasons) if trend else ['warmup'],
                'r0_bottom_signal': bottom.emitted if bottom else False,
                'r0_bottom_rejections': list(bottom.reasons) if bottom else ['warmup'],
                'methods': {}}
            for method in MAIN_METHODS:
                zones = snapshot.zones[method]
                reference = reference_zone(zones)
                record['methods'][method] = {'valid_count': sum(z.valid for z in zones),
                    'invalid_or_expired_count': sum(not z.valid for z in zones),
                    'reference_role': reference.role if reference else None,
                    'reference_age': snapshot.index - reference.confirmed_index if reference else None,
                    'features': feature_row(stream.bars, snapshot, method, config)}
            rows.append(record)
            if day in cutoffs:
                render_chart(stream.bars, snapshot, args.output / f'known-case-{day}',
                             f'Known case 002349 | as of {day} | NOT a blind sample', history=100)
                selected.append(record)
                snapshots.append({'asof': day, 'snapshot': asdict(snapshot),
                    'dated_zones': {m: [{**asdict(z), 'formed_date': stream.bars[z.formed_index].date.isoformat(),
                        'confirmed_date': stream.bars[z.confirmed_index].date.isoformat(),
                        'last_test_date': stream.bars[z.last_test_index].date.isoformat() if z.last_test_index is not None else None,
                        'invalid_date': stream.bars[z.invalid_index].date.isoformat() if z.invalid_index is not None else None}
                        for z in snapshot.zones[m]] for m in MAIN_METHODS}})
    if len(selected) != len(cutoffs):
        raise ValueError('a fixed known-case checkpoint is unavailable')
    write_json(args.output / '完整价格结构.json', snapshots)
    write_json(args.output / '每日完整诊断.json', rows)
    write_json(args.public / 'daily_diagnosis.json', [{k: v for k, v in row.items() if k != 'close_index_sep01'} for row in rows])
    write_json(args.public / 'audit.json', {'type': 'known_case_excluded_from_blind_scores', 'symbol': 'sz002349',
        'period': ['2026-09-01', '2026-10-23'], 'snapshot_manifest': manifest,
        'same_registered_parameters': True, 'new_fits': 0, 'independent_test_outcomes_computed': 0,
        'earlier_snapshot_overlap_difference_dates': differences, 'preregister_sha256': sha256(ROOT / 'research/r1/preregister.json')})
    os.environ.setdefault('MPLCONFIGDIR', '/tmp/ashare-mobile-mpl')
    import matplotlib.pyplot as plt
    from matplotlib import font_manager
    from matplotlib.backends.backend_pdf import PdfPages
    from pypdf import PdfReader, PdfWriter
    font_manager.fontManager.addfont('/usr/share/fonts/opentype/noto/NotoSansCJK-Regular.ttc')
    plt.rcParams['font.family'] = font_manager.FontProperties(fname='/usr/share/fonts/opentype/noto/NotoSansCJK-Regular.ttc').get_name()
    breakout_dates = [r['date'] for r in rows if r['volume_breakout']]
    summary = [
        '# 精华制药 2026 年 9–10 月｜已知案例，不计入盲测评分',
        '', '数据截至 2026-10-23；10 月尚未结束，不包含其后行情。使用新增单股快照，未覆盖 R1 冻结数据。',
        '本次没有改参数、没有新增模型拟合、没有计算或解封独立测试集结果。各截点图只使用当时及以前行情。',
        f"本期日线 {len(rows)} 根；两接口近期核验结果见审计，历史时点版本/停牌/ST/涨跌停/可成交性仍未核验。",
        '满足原有 20 日价突破与 1.5 倍量条件的日期：' + ('、'.join(breakout_dates) if breakout_dates else '无。'),
        f"R0 趋势通过并发出信号 {sum(r['r0_trend_signal'] for r in rows)} 日；底部 {sum(r['r0_bottom_signal'] for r in rows)} 日。它们只是冻结规则的结果，不代表可成交买点。",
        '以下为机械结构记录，不把区间当成已证实支撑/压力；R0 legacy 的 valid 只是原逻辑保留，不能等同有效性已核验。', '']
    for r in selected:
        summary.append(f"## 截点 {r['date']}")
        summary.append(f"相对 9 月 1 日收盘指数 {r['close_index_sep01']:.2f}；当日相对前量 {r['relative_volume_prior20']:.2f}。")
        for m, value in r['methods'].items():
            f = value['features']
            damage = '无参考中枢' if f['lower_damage'] is None else f"下沿破坏比例 {f['lower_damage']:.2%}"
            summary.append(f"{m}：保留/有效 {value['valid_count']} 个，失效/到期 {value['invalid_or_expired_count']} 个；最新参考角色 {value['reference_role']}、年龄 {value['reference_age']}，{damage}。")
        summary.append('R0 趋势拒绝：' + ('、'.join(r['r0_trend_rejections']) or '无（规则通过）'))
        summary.append('R0 底部拒绝：' + ('、'.join(r['r0_bottom_rejections']) or '无（规则通过）'))
        summary.append('')
    summary += ['## 判读边界', '中枢为空、区域过宽、陈旧区间保留、角色转换和确认延迟均保留在逐日记录中，没有为本案例修改阈值。',
        '本报告不根据后续收益评价算法优劣；与首批匿名图分开，建议先独立完成匿名标注再阅读本已知案例。',
        '新旧快照重叠期不同的日期数：' + str(len(differences)) + '。不同则保留两份来源，不自动拼接或修复。']
    markdown = '\n'.join(summary) + '\n'
    public_markdown = '\n'.join(line for line in summary if not line.startswith('相对 9 月 1 日收盘指数')) + '\n'
    (args.public / 'known_case_report.md').write_text(public_markdown)
    (args.output / '精华制药_结构诊断.md').write_text(markdown)
    lines = []
    for paragraph in summary:
        lines.extend(textwrap.wrap(paragraph.lstrip('# '), width=45) or [''])
    text_path = args.output / 'known-case-text.pdf'
    with PdfPages(text_path, metadata={'Title': 'Known case 002349 2026-09 to 2026-10', 'CreationDate': None, 'ModDate': None}) as pdf:
        for start in range(0, len(lines), 36):
            fig = plt.figure(figsize=(9, 14))
            for j, line in enumerate(lines[start:start + 36]):
                fig.text(.07, .95 - j * .024, line, fontsize=11)
            pdf.savefig(fig)
            plt.close(fig)
    writer = PdfWriter()
    for path in [text_path] + [args.output / f'known-case-{d}.pdf' for d in cutoffs]:
        writer.append(PdfReader(path))
    writer.add_metadata({'/Title': '精华制药 2026年9至10月｜已知案例'})
    with (args.output / '精华制药_2026年9至10月_结构诊断.pdf').open('wb') as f:
        writer.write(f)
    print(json.dumps({'known_case_days': len(rows), 'fixed_checkpoints': len(selected), 'separate_from_blind_review': True,
                      'output': str(args.output), 'overlap_differences': len(differences)}, ensure_ascii=False))


if __name__ == '__main__':
    main()
