#!/usr/bin/env python3
"""Archive and diagnose actual Tencent raw/hfq snapshots; NOT factor extraction.

Public endpoint access does not establish redistribution rights or PIT validity.
Data and responses remain local/ignored. Resumable raw cache; never replaces a
completed processed snapshot. Tencent volume is provisionally interpreted as lots.
"""

from __future__ import annotations

import argparse
import csv
import hashlib
import json
import sys
import time
import urllib.parse
import urllib.request
from concurrent.futures import ThreadPoolExecutor
from datetime import date, datetime, timedelta, timezone
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "src"))
from ashare_quant.data import read_bars, sha256  # noqa: E402


def json_write(path, obj):
    path.write_text(json.dumps(obj, ensure_ascii=False, indent=2, allow_nan=False) + "\n", encoding="utf-8")


def fetch(cache: Path, symbol: str, year: int, mode: str, end: date) -> tuple:
    first, last = f"{year}-01-01", min(date(year, 12, 31), end).isoformat()
    param = f"{symbol},day,{first},{last},640,{mode}"
    url = "https://web.ifzq.gtimg.cn/appstock/app/fqkline/get?" + urllib.parse.urlencode({"param": param})
    target = cache / f"{symbol}-{year}-{mode or 'raw'}.json"
    audit = target.with_suffix(".audit.json")
    if target.exists() and audit.exists():
        meta = json.loads(audit.read_text(encoding="utf-8"))
        payload = target.read_bytes()
        if meta["url"] != url or meta["sha256"] != hashlib.sha256(payload).hexdigest():
            raise ValueError(f"cached request/checksum mismatch: {target.name}")
    else:
        for attempt in range(3):
            try:
                request = urllib.request.Request(url, headers={"User-Agent": "ashare-research/0.1"})
                with urllib.request.urlopen(request, timeout=25) as response:
                    payload = response.read()
                parsed = json.loads(payload)
                if parsed.get("code") != 0:
                    raise ValueError(f"vendor error: {parsed.get('msg')}")
                meta = {"url": url, "retrieved_at_utc": datetime.now(timezone.utc).isoformat(),
                        "sha256": hashlib.sha256(payload).hexdigest()}
                target.write_bytes(payload)
                json_write(audit, meta)
                break
            except Exception:
                if attempt == 2:
                    raise
                time.sleep(0.5 * (attempt + 1))
    parsed = json.loads(payload)
    if parsed.get("code") != 0:
        raise ValueError("invalid cached vendor response")
    stock = parsed.get("data", {}).get(symbol, {})
    rows = stock.get(f"{mode}day", stock.get("day", []))
    if not isinstance(rows, list):
        raise ValueError(f"invalid daily rows for {symbol}/{year}")
    # A request must not silently return recent bars outside its requested year.
    for row in rows:
        if len(row) < 6 or not first <= row[0] <= last:
            raise ValueError(f"unexpected row/range for {symbol}/{year}")
    return symbol, year, mode, rows, meta


def write_csv(path, fields, rows):
    with path.open("w", newline="", encoding="utf-8") as f:
        writer = csv.writer(f)
        writer.writerow(fields)
        writer.writerows(rows)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--symbols", nargs="+", default=["sz002349", "sz300620"])
    parser.add_argument("--start-year", type=int, default=2010)
    parser.add_argument("--end", type=date.fromisoformat,
                        default=datetime.now(timezone.utc).date() - timedelta(days=1))
    parser.add_argument("--output", type=Path, required=True,
                        help="local snapshot directory under ignored data/processed/")
    args = parser.parse_args()
    if any(not (s.startswith(("sh", "sz")) and len(s) == 8 and s[2:].isdigit()) for s in args.symbols):
        parser.error("symbols must be sh/sz plus six digits")
    if args.start_year < 1990 or args.start_year > args.end.year:
        parser.error("invalid date range")
    if args.end >= datetime.now(timezone.utc).date():
        parser.error("end must precede today's UTC date to exclude incomplete sessions")
    if args.output.exists():
        parser.error("output already exists; choose a new immutable snapshot directory")
    cache = ROOT / "data" / "raw" / f"tencent-through-{args.end.isoformat()}"
    cache.mkdir(parents=True, exist_ok=True)
    jobs = [(symbol, year, mode) for symbol in args.symbols
            for year in range(args.start_year, args.end.year + 1) for mode in ("", "hfq")]
    # Observed benchmark sessions are a provisional calendar, NOT exchange-certified.
    jobs += [("sh000001", year, "") for year in range(args.start_year, args.end.year + 1)]
    results = []
    try:
        with ThreadPoolExecutor(max_workers=4) as pool:
            for result in pool.map(lambda job: fetch(cache, *job, args.end), jobs):
                results.append(result)
    except Exception as exc:
        json_write(cache / "acquisition_failure.json", {
            "time_utc": datetime.now(timezone.utc).isoformat(), "error": f"{type(exc).__name__}: {exc}",
            "completed_jobs_observed": len(results), "total_jobs": len(jobs)})
        raise
    args.output.mkdir(parents=True)
    sessions = sorted({r[0] for symbol, _, _, rows, _ in results if symbol == "sh000001" for r in rows})
    if not sessions:
        raise ValueError("empty benchmark calendar")
    calendar = args.output / "calendar.csv"
    write_csv(calendar, ["date"], [(d,) for d in sessions])
    verification = []
    for symbol in args.symbols:
        raw, adjusted, requests = {}, {}, []
        for sym, _, mode, rows, meta in results:
            if sym != symbol:
                continue
            requests.append(meta)
            destination = adjusted if mode == "hfq" else raw
            for r in rows:
                if r[0] in destination and destination[r[0]] != r:
                    raise ValueError(f"conflicting duplicate {symbol}/{r[0]}")
                destination[r[0]] = r
        if not raw or set(raw) != set(adjusted):
            raise ValueError(f"raw/adjusted date coverage mismatch for {symbol}")
        raw_out, hfq_out, issues = [], [], []
        max_price_error, max_volume_error = 0.0, 0.0
        for day in sorted(raw):
            # Vendor columns: date, open, close, high, low, volume(lots).
            r, a = raw[day], adjusted[day]
            factor = float(a[2]) / float(r[2])
            price_error = max(abs(float(r[k]) * factor - float(a[k])) / float(a[k]) for k in (1, 2, 3, 4))
            max_price_error = max(max_price_error, price_error)
            max_volume_error = max(max_volume_error, abs(float(r[5]) - float(a[5])))
            if price_error > 0.005 or abs(float(r[5]) - float(a[5])) > 0.01:
                issues.append({"date": day, "multiplicative_ohlc_relative_error": price_error,
                               "volume_difference_lots": abs(float(r[5]) - float(a[5]))})
            raw_out.append([day, r[1], r[3], r[4], r[2], r[5]])
            hfq_out.append([day, a[1], a[3], a[4], a[2], a[5]])
        # Never export a close-ratio 'factor': cash adjustments may be affine rather
        # than multiplicative, and matching rounded prices is not PIT verification.
        csv_path = args.output / f"{symbol}.raw.csv"
        hfq_path = args.output / f"{symbol}.vendor-hfq.csv"
        fields = ["date", "open", "high", "low", "close", "volume_vendor_lots"]
        write_csv(csv_path, fields, raw_out)
        write_csv(hfq_path, fields, hfq_out)
        missing = [d for d in sessions if raw_out[0][0] <= d <= raw_out[-1][0] and d not in raw]
        manifest = {
            "schema_version": 1, "symbol": symbol, "source": "Tencent public fqkline HTTPS snapshot",
            "retrieved_at_utc": datetime.now(timezone.utc).isoformat(),
            "adjustment": "vendor raw and hfq archived separately; NOT accepted by research loader",
            "factor_method": "REJECTED: hfq close/raw close is not a verified cumulative factor",
            "research_eligible": False, "point_in_time_verified": False,
            "volume_unit": "vendor lots, assumption only",
            "volume_unit_verified": False, "redistribution": "unconfirmed; local research only; do not commit bars/responses",
            "calendar_source": "observed sh000001 daily dates", "calendar_verified": False,
            "calendar_requests": [m for sym, _, _, _, m in results if sym == "sh000001"],
            "sha256": sha256(csv_path), "vendor_hfq_sha256": sha256(hfq_path),
            "calendar_sha256": sha256(calendar), "requests": requests,
            "coverage": {"bars": len(raw_out), "first": raw_out[0][0], "last": raw_out[-1][0],
                         "missing_observed_sessions": len(missing), "missing_dates": missing,
                         "zero_volume": sum(float(r[5]) == 0 for r in raw_out)},
            "checks": {"dates_unique_sorted": True, "raw_hfq_same_dates": True,
                       "max_relative_ohlc_factor_error": max_price_error,
                       "max_raw_hfq_volume_difference_lots": max_volume_error,
                       "independent_source_verified": False, "diagnostic_issue_count": len(issues)},
            "diagnostic_issues": issues,
        }
        json_write(args.output / f"{symbol}.manifest.json", manifest)
        verification.append({"symbol": symbol, **manifest["coverage"], "checks": manifest["checks"]})
    json_write(args.output / "verification.json", verification)
    print(json.dumps({"output": str(args.output), "verification": verification}, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
