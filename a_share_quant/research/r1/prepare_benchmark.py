"""Decode the already archived index snapshot; no new network or fabricated rows."""
import csv
import importlib.util
import json
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
spec = importlib.util.spec_from_file_location('sina_adapter', ROOT / 'data/scripts/fetch_sina.py')
module = importlib.util.module_from_spec(spec)
spec.loader.exec_module(module)
from akshare.stock.cons import hk_js_decode

path = ROOT / 'data/raw/sina-through-2026-10-22/sh000001-raw.js'
audit = json.loads(path.with_name(path.name + '.audit.json').read_text())
assert module.sha256(path) == audit['sha256']
registration = json.loads((ROOT / 'research/r1/preregister.json').read_text())
start, end = registration['splits']['train'][0], registration['snapshot_end']
decoded = module.decode_history(path.read_text(), hk_js_decode)
rows = [r for r in decoded if start <= str(r['date'])[:10] <= end]
output = ROOT / 'data/processed/r1-benchmark'
output.mkdir(parents=True, exist_ok=False)
csv_path = output / 'sh000001.csv'
with csv_path.open('w', newline='') as f:
    w = csv.writer(f, lineterminator='\n')
    w.writerow(['date', 'open', 'high', 'low', 'close', 'volume', 'adj_factor'])
    for r in rows:
        w.writerow([str(r['date'])[:10], r['open'], r['high'], r['low'], r['close'], r['volume'], 1])
module.read_bars(csv_path)
module.json_write(output / 'manifest.json', {'symbol': 'sh000001', 'source': audit,
    'sha256': module.sha256(csv_path), 'price_index_not_total_return': True,
    'point_in_time_verified': False, 'redistribution': 'unconfirmed; local only',
    'study_start': start, 'study_end': end, 'outside_study_rows_not_loaded': len(decoded) - len(rows)})
print(json.dumps({'benchmark_bars': len(rows), 'output': str(output)}))
