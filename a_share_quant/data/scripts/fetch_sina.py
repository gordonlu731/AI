#!/usr/bin/env python3
"""Fetch raw full-history Sina bars + separately archived cumulative factors.

Optional pinned AKShare supplies only the established compressed-data decoder.
Network access uses urllib, TLS verification, bounded timeouts and inherited proxy.
Remote responses are parsed as data, never eval'd as Python or JavaScript.
"""
from __future__ import annotations

import argparse
import csv
import hashlib
import importlib.metadata
import json
import math
import sys
import time
import urllib.request
from bisect import bisect_right
from datetime import date, datetime, timedelta, timezone
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "src"))
from ashare_quant.data import read_bars, sha256  # noqa: E402


def json_write(path, obj):
    path.write_text(json.dumps(obj, ensure_ascii=False, indent=2, allow_nan=False) + "\n", encoding="utf-8")


def archive(cache: Path, name: str, url: str):
    path, audit = cache / name, cache / (name + ".audit.json")
    if path.exists() and audit.exists():
        payload = path.read_bytes()
        meta = json.loads(audit.read_text(encoding="utf-8"))
        if meta["url"] != url or meta["sha256"] != hashlib.sha256(payload).hexdigest():
            raise ValueError("cached response provenance mismatch")
        return payload.decode(), meta
    for attempt in range(3):
        try:
            req = urllib.request.Request(url, headers={"User-Agent": "Mozilla/5.0 (A-share research)",
                                                      "Referer": "https://finance.sina.com.cn/"})
            with urllib.request.urlopen(req, timeout=25) as response:
                payload = response.read()
            meta = {"url": url, "retrieved_at_utc": datetime.now(timezone.utc).isoformat(),
                    "sha256": hashlib.sha256(payload).hexdigest()}
            path.write_bytes(payload)
            json_write(audit, meta)
            return payload.decode(), meta
        except Exception:
            if attempt == 2:
                raise
            time.sleep(0.5 * (attempt + 1))


def csv_write(path, fields, rows):
    with path.open("w", newline="", encoding="utf-8") as f:
        writer = csv.writer(f)
        writer.writerow(fields)
        writer.writerows(rows)


def decode_history(text: str, decoder: str):
    from py_mini_racer import py_mini_racer
    # JSONDecoder consumes exactly the quoted encoded string, ignoring trailing JS comments.
    encoded, _ = json.JSONDecoder().raw_decode(text.split("=", 1)[1].lstrip())
    if not isinstance(encoded, str):
        raise ValueError("expected an encoded string")
    engine = py_mini_racer.MiniRacer()
    engine.eval(decoder, timeout=10000)
    result = engine.call("d", encoded, timeout=10000)
    if not isinstance(result, list) or not result:
        raise ValueError("empty/invalid decoded history")
    return result


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--symbols", nargs="+", default=["sz002349", "sz300620"])
    parser.add_argument("--end", type=date.fromisoformat,
                        default=datetime.now(timezone.utc).date() - timedelta(days=1))
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    if args.output.exists():
        parser.error("choose a new immutable snapshot directory")
    if args.end >= datetime.now(timezone.utc).date():
        parser.error("end must precede current UTC date")
    if any(not (s.startswith(("sh", "sz")) and len(s) == 8 and s[2:].isdigit()) for s in args.symbols):
        parser.error("invalid symbols")
    from akshare.stock.cons import hk_js_decode
    versions = {p: importlib.metadata.version(p) for p in ("akshare", "py-mini-racer")}
    if versions != {"akshare": "1.19.3", "py-mini-racer": "0.6.0"}:
        parser.error("install the pinned requirements-data.txt versions")
    cache = ROOT / "data" / "raw" / f"sina-through-{args.end.isoformat()}"
    cache.mkdir(parents=True, exist_ok=True)
    all_rows, provenance = {}, {}
    try:
        for symbol in ["sh000001"] + args.symbols:
            url = f"https://finance.sina.com.cn/realstock/company/{symbol}/hisdata_klc2/klc_kl.js"
            text, meta = archive(cache, f"{symbol}-raw.js", url)
            decoded = decode_history(text, hk_js_decode)
            rows = [r for r in decoded if str(r["date"])[:10] <= args.end.isoformat()]
            if not rows:
                raise ValueError(f"no complete rows for {symbol}")
            all_rows[symbol] = rows
            provenance[symbol] = [meta]
        factors_by_symbol, comparisons = {}, {}
        for symbol in args.symbols:
            text, meta = archive(cache, f"{symbol}-factor.js",
                                 f"https://finance.sina.com.cn/realstock/company/{symbol}/hfq.js")
            parsed, _ = json.JSONDecoder().raw_decode(text[text.index("{"):])
            factors = sorted((str(r["d"]), float(r["f"])) for r in parsed["data"])
            if not factors or len({d for d, f in factors}) != len(factors) or any(not math.isfinite(f) or f <= 0 for d, f in factors):
                raise ValueError("invalid cumulative factors")
            factors_by_symbol[symbol] = factors
            provenance[symbol].append(meta)
            # An additional daily endpoint checks decoder and declared share-volume units.
            text, meta = archive(cache, f"{symbol}-recent.json",
                "https://quotes.sina.cn/cn/api/json_v2.php/CN_MarketDataService.getKLineData?"
                f"symbol={symbol}&scale=240&ma=no&datalen=1023")
            recent = {r["day"]: r for r in json.loads(text) if r["day"] <= args.end.isoformat()}
            overlap, price_mismatches, volume_mismatches = 0, [], []
            for row in all_rows[symbol]:
                day = str(row["date"])[:10]
                if day not in recent:
                    continue
                other = recent[day]
                overlap += 1
                if max(abs(float(row[k]) - float(other[k])) for k in ("open", "high", "low", "close")) > 0.0101:
                    price_mismatches.append(day)
                if abs(float(row["volume"]) - float(other["volume"])) > 1:
                    volume_mismatches.append(day)
            comparisons[symbol] = {"same_vendor_endpoint_overlap": overlap,
                                   "price_mismatch_dates": price_mismatches,
                                   "volume_mismatch_dates": volume_mismatches,
                                   "independent_source_verified": False}
            provenance[symbol].append(meta)
            if overlap == 0 or price_mismatches or volume_mismatches:
                raise ValueError(f"same-vendor endpoint verification failed for {symbol}: {comparisons[symbol]}")
    except Exception as exc:
        json_write(cache / "acquisition_failure.json", {"time_utc": datetime.now(timezone.utc).isoformat(),
                   "error": f"{type(exc).__name__}: {exc}", "provenance_so_far": provenance})
        raise
    # All acquisition/endpoint checks finish before releasing any processed snapshot.
    args.output.mkdir(parents=True)
    sessions = sorted({str(r["date"])[:10] for r in all_rows["sh000001"]})
    calendar = args.output / "calendar.csv"
    csv_write(calendar, ["date"], [(d,) for d in sessions])
    summaries = []
    for symbol in args.symbols:
        factors = factors_by_symbol[symbol]
        factor_days = [d for d, f in factors]
        rows_out = []
        for row in all_rows[symbol]:
            day = str(row["date"])[:10]
            index = bisect_right(factor_days, day) - 1
            if index < 0:
                raise ValueError(f"no factor known on/before {day}; no backward fill allowed")
            rows_out.append([day, row["open"], row["high"], row["low"], row["close"],
                             row["volume"], factors[index][1]])
        path = args.output / f"{symbol}.csv"
        csv_write(path, ["date", "open", "high", "low", "close", "volume", "adj_factor"], rows_out)
        bars = read_bars(path)
        known_days = {b.date.isoformat() for b in bars}
        missing = [d for d in sessions if rows_out[0][0] <= d <= rows_out[-1][0] and d not in known_days]
        if known_days - set(sessions):
            raise ValueError("stock dates outside observed benchmark sessions")
        manifest = {
            "schema_version": 1, "symbol": symbol, "source": "Sina full-history raw daily snapshot + separate hfq factor snapshot",
            "retrieved_at_utc": datetime.now(timezone.utc).isoformat(), "adjustment": "cumulative_factor",
            "factor_method": "latest factor effective date <= bar date, never backfilled",
            "factor_anchor": "first observation; normalized at load time", "point_in_time_verified": False,
            "volume_unit": "shares", "volume_unit_verified": "consistent with separate same-vendor daily endpoint",
            "redistribution": "unconfirmed; local research only; do not commit bars/responses",
            "calendar_source": "observed Sina sh000001 daily dates; not exchange-certified",
            "calendar_verified": False, "calendar_requests": provenance["sh000001"],
            "sha256": sha256(path), "calendar_sha256": sha256(calendar), "requests": provenance[symbol],
            "decoder": {"packages": versions, "hk_js_decode_sha256": hashlib.sha256(hk_js_decode.encode()).hexdigest()},
            "coverage": {"bars": len(bars), "first": bars[0].date.isoformat(), "last": bars[-1].date.isoformat(),
                         "missing_observed_sessions": len(missing), "missing_dates": missing,
                         "zero_volume": sum(b.volume == 0 for b in bars)},
            "checks": comparisons[symbol],
        }
        json_write(args.output / f"{symbol}.manifest.json", manifest)
        summaries.append({"symbol": symbol, **manifest["coverage"], "checks": manifest["checks"]})
    json_write(args.output / "verification.json", summaries)
    print(json.dumps({"output": str(args.output), "verification": summaries}, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
