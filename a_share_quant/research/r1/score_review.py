"""Score user-supplied independent human regions, never fabricate annotations."""
import argparse
import csv
import sys
from pathlib import Path
ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / 'src'))
from ashare_quant.r1.review import review_scores
from ashare_quant.r1.io import write_json

parser = argparse.ArgumentParser(description=__doc__)
parser.add_argument('--human-regions', type=Path, required=True)
parser.add_argument('--algorithm-regions', type=Path, required=True)
parser.add_argument('--output', type=Path, required=True)
args = parser.parse_args()
if args.output.exists():
    parser.error('choose a new result path to preserve prior annotations')
with args.human_regions.open() as f:
    human = list(csv.DictReader(f))
with args.algorithm_regions.open() as f:
    algorithm = list(csv.DictReader(f))
write_json(args.output, review_scores(human, algorithm))
