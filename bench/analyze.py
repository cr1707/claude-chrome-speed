#!/usr/bin/env python3
"""Pre-registered analysis (see ANALYSIS_PLAN.md). Standard library only.

Usage: python3 bench/analyze.py   # reads bench/results/runs.jsonl and bench/results/opus/runs.jsonl
"""
import json
import random
import statistics as st
from pathlib import Path

RESULTS = Path(__file__).resolve().parent / "results"
MODELS = {"Sonnet": RESULTS / "runs.jsonl", "Opus": RESULTS / "opus" / "runs.jsonl"}
TASKS = ["books", "form", "wiki", "spa", "catalog", "suppliers"]
PERMS = 100_000
BOOTS = 10_000
rng = random.Random(20261010)


def load(path):
    return [json.loads(line) for line in path.read_text().splitlines() if line.strip()]


def two_sided_perm(a, b):
    obs = abs(st.mean(a) - st.mean(b))
    pooled, n, hits = a + b, len(a), 0
    for _ in range(PERMS):
        rng.shuffle(pooled)
        hits += abs(st.mean(pooled[:n]) - st.mean(pooled[n:])) >= obs - 1e-9
    return (hits + 1) / (PERMS + 1)


def stratified_one_sided(by_task):
    def stat(groups):
        return st.mean((st.mean(b) - st.mean(f)) / st.mean(b) for b, f in groups)
    groups = [(b, f) for b, f in by_task.values()]
    obs, hits = stat(groups), 0
    for _ in range(PERMS // 10):
        shuffled = []
        for b, f in groups:
            pooled = b + f
            rng.shuffle(pooled)
            shuffled.append((pooled[:len(b)], pooled[len(b):]))
        hits += stat(shuffled) >= obs - 1e-12
    return obs, (hits + 1) / (PERMS // 10 + 1)


def median_change_ci(b, f):
    point = (st.median(f) - st.median(b)) / st.median(b)
    draws = sorted(
        (st.median(rng.choices(f, k=len(f))) - (mb := st.median(rng.choices(b, k=len(b))))) / mb
        for _ in range(BOOTS))
    return point, draws[int(0.025 * BOOTS)], draws[int(0.975 * BOOTS) - 1]


def holm(pvals):
    order = sorted(range(len(pvals)), key=lambda i: pvals[i])
    adj, running = [0.0] * len(pvals), 0.0
    for rank, i in enumerate(order):
        running = max(running, min(1.0, (len(pvals) - rank) * pvals[i]))
        adj[i] = running
    return adj


def main():
    rows_out = []
    pooled = {}
    for model, path in MODELS.items():
        runs = load(path)
        by_task = {}
        for t in TASKS:
            b = [r["duration_s"] for r in runs if r["task"] == t and r["cond"] == "baseline"]
            f = [r["duration_s"] for r in runs if r["task"] == t and r["cond"] == "speed"]
            if not b or not f:
                continue
            ok_b = sum(r["correct"] for r in runs if r["task"] == t and r["cond"] == "baseline")
            ok_f = sum(r["correct"] for r in runs if r["task"] == t and r["cond"] == "speed")
            point, lo, hi = median_change_ci(b, f)
            rows_out.append({"model": model, "task": t, "n": (len(b), len(f)),
                             "median": (st.median(b), st.median(f)), "change": point, "ci": (lo, hi),
                             "p": two_sided_perm(b, f), "correct": (ok_b, ok_f)})
            by_task[t] = (b, f)
        pooled[model] = stratified_one_sided(by_task)

    for r, adj in zip(rows_out, holm([r["p"] for r in rows_out])):
        r["p_holm"] = adj

    print("| Model | Task | Runs (without/with) | Median time (s) | Change [95% CI] | p (Holm) | Correct (without → with) |")
    print("|---|---|---|---|---|---|---|")
    for r in rows_out:
        sig = "**" if r["p_holm"] < 0.05 else ""
        print(f"| {r['model']} | `{r['task']}` | {r['n'][0]}/{r['n'][1]} | "
              f"{r['median'][0]:.1f} → {r['median'][1]:.1f} | "
              f"{sig}{r['change']*100:+.0f}%{sig} [{r['ci'][0]*100:+.0f}%, {r['ci'][1]*100:+.0f}%] | "
              f"{r['p_holm']:.4f} | {r['correct'][0]}/{r['n'][0]} → {r['correct'][1]}/{r['n'][1]} |")
    print()
    for model, (obs, p) in pooled.items():
        print(f"{model}, all tasks: mean relative time saved {obs*100:.0f}%, one-sided p = {p:.4f}")


if __name__ == "__main__":
    main()
