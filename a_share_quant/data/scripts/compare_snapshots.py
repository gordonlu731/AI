"""Compare archived raw vendor snapshots without merging or repairing them."""
import argparse
import csv
import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[2] / "src"))
from ashare_quant.data import sha256


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--sina", type=Path, required=True)
    parser.add_argument("--tencent", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    if args.output.exists():
        parser.error("refuse to replace existing audit")
    audits = []
    for symbol in ("sz002349", "sz300620"):
        a_path = args.sina / f"{symbol}.csv"
        b_path = args.tencent / f"{symbol}.raw.csv"
        with a_path.open() as f:
            a = {r["date"]: r for r in csv.DictReader(f)}
        with b_path.open() as f:
            b = {r["date"]: r for r in csv.DictReader(f)}
        issues, max_volume_difference = [], 0.0
        for day in sorted(a.keys() & b.keys()):
            price_error = max(abs(float(a[day][k]) - float(b[day][k])) for k in ("open", "high", "low", "close"))
            volume_error = abs(float(a[day]["volume"]) - float(b[day]["volume_vendor_lots"]) * 100)
            max_volume_difference = max(max_volume_difference, volume_error)
            if price_error > 0.0101 or volume_error > 101:
                # Publish dates/flags only, not the vendors' quotes.
                issues.append({"date": day, "ohlc_mismatch": price_error > 0.0101,
                               "volume_mismatch": volume_error > 101})
        audits.append({"symbol": symbol, "sina_sha256": sha256(a_path), "tencent_raw_sha256": sha256(b_path),
                       "date_coverage_equal": a.keys() == b.keys(), "overlap": len(a.keys() & b.keys()),
                       "comparison_tolerance": {"price_cny": 0.0101, "volume_shares": 101},
                       "volume_conversion_assumption": "Tencent lots x100; historical lot rounding allowed",
                       "issue_count": len(issues), "issues": issues,
                       "action": "retain separate sources; no automatic merge or repair",
                       "point_in_time_verified": False})
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(audits, ensure_ascii=False, indent=2) + "\n")
    print(json.dumps({"symbols": len(audits), "issue_counts": {r["symbol"]: r["issue_count"] for r in audits}}))


if __name__ == "__main__":
    main()
