#!/usr/bin/env python3
"""Turn bench/results/runs.jsonl into the Markdown results table used in the README."""
import json
import statistics
import sys
from pathlib import Path

RUNS = Path(sys.argv[1]) if len(sys.argv) > 1 else Path(__file__).resolve().parent / "results" / "runs.jsonl"

rows = [json.loads(l) for l in RUNS.read_text().splitlines() if l.strip()]
tasks = list(dict.fromkeys(r["task"] for r in rows))
metrics = [
    ("duration_s", "Time (s)", "{:.1f}"),
    ("turns", "Turns", "{:.0f}"),
    ("screenshots", "Screenshots", "{:.0f}"),
    ("input_tokens", "Input tokens", "{:,.0f}"),
    ("cost_usd_list", "Cost (USD, list)", "{:.3f}"),
]


def med(rs, key):
    vals = [r[key] for r in rs if r.get(key) is not None]
    return statistics.median(vals) if vals else float("nan")


def change(a, b):
    if not a:
        return "—"
    pct = (b - a) / a * 100
    return f"{pct:+.0f}%"


def table(subset, title):
    base = [r for r in subset if r["cond"] == "baseline"]
    fast = [r for r in subset if r["cond"] == "speed"]
    out = [f"### {title}", "", "| Median per run | Without plugin | With plugin | Change |", "|---|---|---|---|"]
    for key, label, fmt in metrics:
        a, b = med(base, key), med(fast, key)
        out.append(f"| {label} | {fmt.format(a)} | {fmt.format(b)} | {change(a, b)} |")
    ok_a = sum(r["correct"] for r in base)
    ok_b = sum(r["correct"] for r in fast)
    out.append(f"| Correct answers | {ok_a}/{len(base)} | {ok_b}/{len(fast)} | |")
    return "\n".join(out)


print(table(rows, f"All tasks ({len(rows)} runs)"))
for t in tasks:
    print()
    print(table([r for r in rows if r["task"] == t], f"Task: {t}"))
