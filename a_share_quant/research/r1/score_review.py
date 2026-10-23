"""Score user-supplied independent human regions, never fabricate annotations."""
import argparse
import csv
import sys
from pathlib import Path
ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / 'src'))
from ashare_quant.r1.review import review_scores, JUDGMENTS
from ashare_quant.r1.io import write_json

parser = argparse.ArgumentParser(description=__doc__)
parser.add_argument('--human-regions', type=Path, required=True)
parser.add_argument('--algorithm-regions', type=Path, required=True)
parser.add_argument('--output', type=Path, required=True)
parser.add_argument('--judgments', type=Path, help='optional completed correct/high/low/omission/false-detection form')
args = parser.parse_args()
if args.output.exists():
    parser.error('choose a new result path to preserve prior annotations')
with args.human_regions.open() as f:
    human = list(csv.DictReader(f))
with args.algorithm_regions.open() as f:
    algorithm = list(csv.DictReader(f))
result = review_scores(human, algorithm)
if args.judgments:
    with args.judgments.open() as f:
        judgments = list(csv.DictReader(f))
    if any(r['judgment'] not in JUDGMENTS for r in judgments):
        parser.error('unknown judgment value')
    result['human_judgments'] = judgments
    result['human_error_records'] = [r for r in judgments if r['judgment'] not in ('unreviewed', 'correct')]
write_json(args.output, result)
