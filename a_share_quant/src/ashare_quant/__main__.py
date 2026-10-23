from __future__ import annotations

import argparse
import json
import subprocess
from collections import Counter
from dataclasses import asdict
from datetime import datetime, timezone
from pathlib import Path

from . import __version__
from .data import adjust_bars, calendar_gaps, read_bars, read_calendar, session_segments, sha256
from .evaluation import evaluate, summarize
from .strategy import Parameters, assess_sessions
from .structure import identify


def write_json(path: Path, value) -> None:
    path.write_text(json.dumps(value, ensure_ascii=False, indent=2, allow_nan=False) + "\n", encoding="utf-8")


def main() -> None:
    parser = argparse.ArgumentParser(description="R0 causal A-share research; no live trading")
    sub = parser.add_subparsers(dest="command", required=True)
    for name in ("validate", "research"):
        cmd = sub.add_parser(name)
        cmd.add_argument("--bars", type=Path, required=True)
        cmd.add_argument("--manifest", type=Path, required=True)
        cmd.add_argument("--calendar", type=Path, required=True)
        if name == "research":
            cmd.add_argument("--output", type=Path, required=True)
            cmd.add_argument("--allow-snapshot-research", action="store_true",
                             help="explicitly permit unverified factors/calendar for exploratory labels only")
            cmd.add_argument("--cost-per-side", type=float, default=0.001)
            cmd.add_argument("--params", type=Path, help="JSON matching Parameters; no automatic tuning")
    args = parser.parse_args()
    try:
        raw = read_bars(args.bars)
        calendar = read_calendar(args.calendar)
        manifest = json.loads(args.manifest.read_text(encoding="utf-8"))
        required = ("symbol", "source", "retrieved_at_utc", "adjustment", "volume_unit",
                    "redistribution", "sha256", "calendar_sha256", "point_in_time_verified",
                    "calendar_verified")
        if any(k not in manifest for k in required):
            raise ValueError("manifest missing required provenance fields")
        if manifest["volume_unit"] != "shares" or manifest["adjustment"] != "cumulative_factor":
            raise ValueError("unsupported adjustment or volume unit")
        if manifest["sha256"] != sha256(args.bars) or manifest["calendar_sha256"] != sha256(args.calendar):
            raise ValueError("data/calendar checksum mismatch")
        gaps = calendar_gaps(raw, calendar)
        validation = {"symbol": manifest["symbol"], "bars": len(raw),
                      "first": raw[0].date.isoformat(), "last": raw[-1].date.isoformat(),
                      "missing_sessions": len(gaps), "missing_dates": [d.isoformat() for d in gaps],
                      "zero_volume_bars": sum(b.volume == 0 for b in raw),
                      "point_in_time_verified": manifest["point_in_time_verified"],
                      "calendar_verified": manifest["calendar_verified"]}
        if args.command == "validate":
            print(json.dumps(validation, ensure_ascii=False, indent=2))
            return
        verified = (manifest["point_in_time_verified"] is True and manifest["calendar_verified"] is True
                    and bool(manifest.get("verification_evidence")))
        if not verified and not args.allow_snapshot_research:
            raise ValueError("PIT factors/calendar lack verification evidence; only explicit --allow-snapshot-research is available")
        p = Parameters(**json.loads(args.params.read_text(encoding="utf-8"))) if args.params else Parameters()
        bars = adjust_bars(raw)
        segments = session_segments(bars, calendar)
        assessments = assess_sessions(bars, calendar, p)
        outcomes = evaluate(bars, assessments, calendar, args.cost_per_side, p.rr_min)
        structures = []
        for first, end in segments:
            pivots, legs, zones = identify(bars[first:end], p.reversal, p.volume_window)
            structures.append({"first_bar_index": first, "end_bar_index_exclusive": end,
                               "indices_are_segment_local": True,
                               "pivots": [asdict(x) for x in pivots], "legs": [asdict(x) for x in legs],
                               "centers": [asdict(x) for x in zones]})
        # Complete all validation/calculation before creating an immutable report directory.
        args.output.mkdir(parents=True, exist_ok=False)
        try:
            commit = subprocess.check_output(["git", "rev-parse", "HEAD"], text=True, stderr=subprocess.DEVNULL).strip()
            dirty = bool(subprocess.check_output(["git", "status", "--porcelain"], text=True))
        except (subprocess.CalledProcessError, FileNotFoundError):
            commit, dirty = None, None
        code_hashes = {f.name: sha256(f) for f in sorted(Path(__file__).parent.glob("*.py"))}
        metadata = {"version": __version__, "code_commit": commit, "working_tree_dirty": dirty,
                    "code_sha256": code_hashes, "generated_at_utc": datetime.now(timezone.utc).isoformat(),
                    "study_type": "overlapping_event_labels_not_portfolio_backtest",
                    "verification": "verified_inputs" if verified else "UNVERIFIED_SNAPSHOT_EXPLORATION",
                    "execution_constraints_verified": False, "parameters": asdict(p),
                    "cost_per_side_assumption": args.cost_per_side, "manifest": manifest,
                    "validation": validation, "signals": sum(s.emitted for s in assessments),
                    "gap_policy": "reset structures and warmup after every missing/zero-volume session",
                    "segments": segments, "assessed_rows": len(assessments) // 2,
                    "rejection_counts": dict(Counter(r for s in assessments for r in s.reasons)),
                    "limitations": ["No verified opening limit/ST/security status or fill simulation",
                                    "No portfolio returns, annualization, or Sharpe ratio",
                                    "Overlapping labels and post-selected case securities",
                                    "Current vendor snapshots may include subsequent corrections"]}
        write_json(args.output / "run.json", metadata)
        write_json(args.output / "summary.json", summarize(outcomes))
        write_json(args.output / "structures.json", structures)
        for name, values in (("assessments.jsonl", assessments), ("outcomes.jsonl", outcomes)):
            with (args.output / name).open("w", encoding="utf-8") as f:
                for x in values:
                    f.write(json.dumps(asdict(x), ensure_ascii=False, allow_nan=False) + "\n")
        print(json.dumps({"output": str(args.output), "signals": metadata["signals"],
                          "verification": metadata["verification"]}, ensure_ascii=False))
    except (ValueError, OSError, KeyError, TypeError) as error:
        parser.exit(2, f"error: {error}\n")


if __name__ == "__main__":
    main()
