"""Publish non-price, derived event labels and audit metadata from local runs.

No raw bars, factor values, pivot prices, or support/resistance levels are copied.
Optional --plot needs matplotlib; statistics export uses only the standard library.
"""
from __future__ import annotations

import argparse
import csv
import importlib.metadata
import json
from pathlib import Path


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--runs", type=Path, nargs="+", required=True)
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--plot", action="store_true")
    args = parser.parse_args()
    args.output.mkdir(parents=True, exist_ok=False)
    summaries, outcomes, audit = [], [], []
    for directory in args.runs:
        run = json.loads((directory / "run.json").read_text(encoding="utf-8"))
        symbol = run["manifest"]["symbol"]
        audit.append(run)
        summaries.extend({"symbol": symbol, **r} for r in json.loads((directory / "summary.json").read_text()))
        for line in (directory / "outcomes.jsonl").read_text().splitlines():
            record = json.loads(line)
            outcomes.append({"symbol": symbol, **{k: v for k, v in record.items() if k not in ("entry_price", "entry_rr")}})
    for name, rows in (("summary", summaries), ("all_event_labels", outcomes)):
        (args.output / f"{name}.json").write_text(json.dumps(rows, ensure_ascii=False, indent=2, allow_nan=False) + "\n")
        if rows:
            with (args.output / f"{name}.csv").open("w", newline="", encoding="utf-8") as f:
                writer = csv.DictWriter(f, fieldnames=list(rows[0]), lineterminator="\n")
                writer.writeheader()
                writer.writerows({k: json.dumps(v, ensure_ascii=False) if isinstance(v, dict) else v
                                 for k, v in row.items()} for row in rows)
    (args.output / "audit.json").write_text(json.dumps(audit, ensure_ascii=False, indent=2, allow_nan=False) + "\n")
    if args.plot:
        import matplotlib
        matplotlib.use("Agg")
        import matplotlib.pyplot as plt
        plt.rcParams["svg.hashsalt"] = "ashare-r0-2026-10-23"
        fig, axes = plt.subplots(1, 2, figsize=(12, 4.8))
        for symbol in sorted({r["symbol"] for r in summaries}):
            for strategy in ("trend_pullback", "bottom_reversal"):
                rows = [r for r in summaries if r["symbol"] == symbol and r["strategy"] == strategy and r["observed"] > 0]
                if not rows:
                    continue
                label = f"{symbol} {strategy} (N=" + "/".join(str(r["observed"]) for r in rows) + ")"
                for axis, key in zip(axes, ("mean_net_return", "worst_mae")):
                    axis.plot([r["horizon"] for r in rows], [100 * r[key] for r in rows], marker="o", label=label)
        for axis, title in zip(axes, ("Mean return after assumed 10bp per side", "Worst intrawindow adverse excursion")):
            axis.axhline(0, color="#666666", linewidth=0.7)
            axis.set(xticks=[3, 5, 10, 20], xlabel="Exchange-session horizon (provisional calendar)", ylabel="%", title=title)
            axis.grid(alpha=0.2)
        axes[0].legend(fontsize=7, loc="lower right")
        fig.suptitle("R0: UNVERIFIED snapshot event study — no tradable-performance claim", fontsize=12)
        fig.text(0.5, 0.01, "No sz300620 bottom signals. Overlapping, post-selected cases; no execution constraints or out-of-sample test.", ha="center", fontsize=8)
        fig.tight_layout(rect=(0, 0.04, 1, 0.94))
        fig.savefig(args.output / "event-study.svg", metadata={"Date": None})
        svg_path = args.output / "event-study.svg"
        svg_path.write_text("\n".join(line.rstrip() for line in svg_path.read_text().splitlines()) + "\n")
        plt.close(fig)
        (args.output / "plot_environment.json").write_text(json.dumps({"matplotlib": importlib.metadata.version("matplotlib")}, indent=2) + "\n")
    print(json.dumps({"published_events_including_failures": len(outcomes), "summary_groups": len(summaries),
                      "output": str(args.output)}))


if __name__ == "__main__":
    main()
