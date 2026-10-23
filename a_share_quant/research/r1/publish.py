"""Publish derived artifacts, compressing large JSON without losing any records.

Only accepts the known non-price stage outputs. Never publishes chart/snapshot
price details, unblinding keys, vendor CSVs, raw responses, or local fits inputs.
"""
import argparse
import gzip
import hashlib
import json
import shutil
from pathlib import Path

parser = argparse.ArgumentParser(description=__doc__)
parser.add_argument('--source', type=Path, required=True)
parser.add_argument('--output', type=Path, required=True)
args = parser.parse_args()
allowed = {'algorithm_judgments_template.csv', 'case_summary.json', 'chart_inventory.json', 'human_agreement.json',
           'human_regions_template.csv', 'structure_stage.json', 'sz002349-daily-diagnostics.json', 'sz300620-daily-diagnostics.json',
           'all_daily_states.jsonl.gz', 'anchor_features.csv.gz', 'all_event_labels.csv.gz', 'anchor_register.csv',
           'event_summary.json', 'year_regime_summary.json', 'bottom_shape_summary.json', 'coverage.json', 'event_audit.json',
           'incremental_metrics.json', 'incremental_metrics.csv', 'trained_model_audit.json', 'model_protocol_audit.json'}
files = [p for p in args.source.iterdir() if p.is_file()]
if not files or any(p.name not in allowed for p in files):
    raise ValueError('unexpected or empty publication input')
args.output.mkdir(parents=True, exist_ok=False)
manifest = []
for path in sorted(files):
    original = path.read_bytes()
    compressed = path.suffix == '.json' and len(original) > 262144
    name = path.name + '.gz' if compressed else path.name
    payload = gzip.compress(original, mtime=0) if compressed else original
    (args.output / name).write_bytes(payload)
    manifest.append({'source_file': path.name, 'published_file': name, 'source_sha256': hashlib.sha256(original).hexdigest(),
                     'published_sha256': hashlib.sha256(payload).hexdigest(), 'lossless_gzip': compressed})
(args.output / 'publication_manifest.json').write_text(json.dumps(manifest, indent=2) + '\n')
print(json.dumps({'published_files': len(manifest), 'output': str(args.output)}))
