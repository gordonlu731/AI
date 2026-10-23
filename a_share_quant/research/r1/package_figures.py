"""Package local price charts for review without publishing vendor price data."""
import argparse
import hashlib
import json
import zipfile
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
parser = argparse.ArgumentParser(description=__doc__)
parser.add_argument('--figures', type=Path, required=True)
parser.add_argument('--templates', type=Path, required=True)
parser.add_argument('--output', type=Path, required=True)
parser.add_argument('--manifest', type=Path, required=True)
args = parser.parse_args()
args.output.mkdir(parents=True, exist_ok=True)
manifest = []
for folder in ('cases', 'blind'):
    for p in sorted((args.figures / folder).glob('*')):
        if p.suffix not in ('.png', '.pdf'):
            continue
        manifest.append({'path': str(p.relative_to(args.figures)), 'sha256': hashlib.sha256(p.read_bytes()).hexdigest(),
                         'cutoff_rule': 'no bars beyond corresponding snapshot cutoff'})
args.manifest.write_text(json.dumps(manifest, indent=2) + '\n')
for name, folder in [('r1-case-charts.zip', 'cases'), ('r1-blind-review.zip', 'blind')]:
    target = args.output / name
    if target.exists():
        parser.error('refuse to replace an existing review packet')
    with zipfile.ZipFile(target, 'w', compression=zipfile.ZIP_DEFLATED) as archive:
        selected = [r for r in manifest if r['path'].startswith(folder + '/')]
        for record in selected:
            archive.write(args.figures / record['path'], record['path'])
        archive.writestr('figure_manifest.json', json.dumps(selected, indent=2) + '\n')
        if folder == 'blind':
            archive.write(args.figures / 'algorithm_regions.csv', 'algorithm_regions.csv')
            for template in ['human_regions_template.csv', 'algorithm_judgments_template.csv']:
                archive.write(args.templates / template, template)
            archive.write(ROOT / 'docs/r1/human_review.md', 'human_review.md')
    with zipfile.ZipFile(target) as archive:
        if any('PRIVATE' in n or 'snapshot-price' in n for n in archive.namelist()):
            raise ValueError('private key leaked into review packet')
    print(json.dumps({'packet': str(target), 'bytes': target.stat().st_size}))
