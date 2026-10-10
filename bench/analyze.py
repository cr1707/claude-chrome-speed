#!/usr/bin/env python3
"""Pre-registered analysis (see ANALYSIS_PLAN.md, including amendment 2). Standard library only.

Usage: python3 bench/analyze.py
Reads bench/results/sonnet-5-5/ and bench/results/opus/ (runs.jsonl plus raw/ logs).
"""
import json
import random
import statistics as st
from collections import Counter
from datetime import datetime
from pathlib import Path

RESULTS = Path(__file__).resolve().parent / "results"
MODELS = {"Sonnet 5.5": RESULTS / "sonnet-5-5", "Opus 5.5": RESULTS / "opus"}
TASKS = ["books", "form", "wiki", "spa", "catalog", "suppliers"]
TARGET_N = 10
PERMS = 100_000
SENS_PERMS = 20_000
BOOTS = 10_000
STALL_S = 60
rng = random.Random(20261010)


def load(folder):
    rows = [json.loads(l) for l in (folder / "runs.jsonl").read_text().splitlines() if l.strip()]
    keys = Counter((r["task"], r["cond"], int(r["rep"])) for r in rows)
    dupes = [k for k, n in keys.items() if n > 1]
    if dupes:
        raise SystemExit(f"{folder}: duplicate rows {dupes}")
    return rows


def raw_log(folder, r):
    return folder / "raw" / f"{r['task']}-{r['cond']}-{r['rep']}.jsonl"


def longest_stall(path):
    """Longest gap (s) between consecutive streamed blocks of the same model response."""
    by_msg = {}
    for line in path.read_text().splitlines():
        try:
            e = json.loads(line)
        except json.JSONDecodeError:
            continue
        if e.get("type") == "assistant" and e.get("timestamp"):
            mid = e.get("message", {}).get("id")
            t = datetime.fromisoformat(e["timestamp"].replace("Z", "+00:00"))
            by_msg.setdefault(mid, []).append(t)
    gaps = [(b - a).total_seconds() for ts in by_msg.values() for a, b in zip(sorted(ts), sorted(ts)[1:])]
    return max(gaps, default=0.0)


def bash_denials(path):
    for line in reversed(path.read_text().splitlines()):
        try:
            e = json.loads(line)
        except json.JSONDecodeError:
            continue
        if e.get("type") == "result":
            return len(e.get("permission_denials") or [])
    return 0


def perm_two_sided(a, b, iters, ranks=False):
    if ranks:
        pooled = a + b
        order = sorted(range(len(pooled)), key=lambda i: pooled[i])
        r = [0.0] * len(pooled)
        i = 0
        while i < len(order):  # average ranks for ties
            j = i
            while j + 1 < len(order) and pooled[order[j + 1]] == pooled[order[i]]:
                j += 1
            for k in range(i, j + 1):
                r[order[k]] = (i + j) / 2 + 1
            i = j + 1
        a, b = r[:len(a)], r[len(a):]
    obs = abs(st.mean(a) - st.mean(b))
    pooled, n, hits = a + b, len(a), 0
    for _ in range(iters):
        rng.shuffle(pooled)
        hits += abs(st.mean(pooled[:n]) - st.mean(pooled[n:])) >= obs - 1e-9
    return (hits + 1) / (iters + 1)


def pooled_one_sided(by_task, iters):
    def stat(groups):
        return st.mean((st.mean(b) - st.mean(f)) / st.mean(b) for b, f in groups)
    groups = list(by_task.values())
    obs, hits = stat(groups), 0
    for _ in range(iters):
        shuffled = []
        for b, f in groups:
            pooled = b + f
            rng.shuffle(pooled)
            shuffled.append((pooled[:len(b)], pooled[len(b):]))
        hits += stat(shuffled) >= obs - 1e-12
    return obs, (hits + 1) / (iters + 1)


def median_change_ci(b, f):
    point = (st.median(f) - st.median(b)) / st.median(b)
    draws = []
    for _ in range(BOOTS):
        mb = st.median(rng.choices(b, k=len(b)))
        draws.append((st.median(rng.choices(f, k=len(f))) - mb) / mb)
    draws.sort()
    return point, draws[int(0.025 * BOOTS)], draws[int(0.975 * BOOTS) - 1]


def holm(pvals):
    order = sorted(range(len(pvals)), key=lambda i: pvals[i])
    adj, running = [0.0] * len(pvals), 0.0
    for rank, i in enumerate(order):
        running = max(running, min(1.0, (len(pvals) - rank) * pvals[i]))
        adj[i] = running
    return adj


def split(rows, task):
    b = [r["duration_s"] for r in rows if r["task"] == task and r["cond"] == "baseline"]
    f = [r["duration_s"] for r in rows if r["task"] == task and r["cond"] == "speed"]
    return b, f


def main():
    data = {m: load(folder) for m, folder in MODELS.items()}

    print("## Run counts (target", TARGET_N, "per task, arm and model)\n")
    for m, rows in data.items():
        cells = Counter((r["task"], r["cond"]) for r in rows)
        short = {k: v for k, v in cells.items() if v != TARGET_N}
        models = Counter(r.get("model_id") or "unrecorded" for r in rows)
        print(f"- {m}: {len(rows)} runs; model ids {dict(models)}; "
              + ("all cells complete" if not short else f"cells not at {TARGET_N}: {short}"))

    # Primary analysis (pre-registered).
    table = []
    for m, rows in data.items():
        for t in TASKS:
            b, f = split(rows, t)
            if not b or not f:
                continue
            ok = [sum(r["correct"] for r in rows if r["task"] == t and r["cond"] == c) for c in ("baseline", "speed")]
            point, lo, hi = median_change_ci(b, f)
            table.append({"model": m, "task": t, "n": (len(b), len(f)), "median": (st.median(b), st.median(f)),
                          "change": point, "ci": (lo, hi), "p": perm_two_sided(b, f, PERMS), "correct": ok})
    for r, adj in zip(table, holm([r["p"] for r in table])):
        r["p_holm"] = adj

    print("\n## Primary: per task (two-sided permutation test, Holm-corrected over", len(table), "tests)\n")
    print("| Model | Task | Runs (without/with) | Median time (s) | Change [95% CI] | p (Holm) | Correct (without → with) |")
    print("|---|---|---|---|---|---|---|")
    for r in table:
        sig = "**" if r["p_holm"] < 0.05 else ""
        print(f"| {r['model']} | `{r['task']}` | {r['n'][0]}/{r['n'][1]} | {r['median'][0]:.1f} → {r['median'][1]:.1f} | "
              f"{sig}{r['change']*100:+.0f}%{sig} [{r['ci'][0]*100:+.0f}%, {r['ci'][1]*100:+.0f}%] | "
              f"{r['p_holm']:.4f} | {r['correct'][0]}/{r['n'][0]} → {r['correct'][1]}/{r['n'][1]} |")

    print("\n## Primary: all tasks per model (one-sided permutation within tasks; headline statistic)\n")
    for m, rows in data.items():
        by_task = {t: split(rows, t) for t in TASKS if all(split(rows, t))}
        obs, p = pooled_one_sided(by_task, PERMS // 10)
        print(f"- {m}: mean time saved per task {obs*100:.0f}%, p = {p:.4f}")

    print("\n## Sensitivity analyses (secondary)\n")
    rank_rows = []
    for m, rows in data.items():
        for t in TASKS:
            b, f = split(rows, t)
            if b and f:
                rank_rows.append((m, t, perm_two_sided(b, f, SENS_PERMS, ranks=True)))
    adj = holm([p for _, _, p in rank_rows])
    print("Rank-based test per task (Holm): " + "; ".join(
        f"{m} {t} p={a:.4f}" for (m, t, _), a in zip(rank_rows, adj)))

    for label, keep in [("Repetitions 6-10 only (collected after the plan)", lambda r: int(r["rep"]) >= 6),
                        (f"Excluding runs with an API stall over {STALL_S} s",
                         lambda r, m=None: True)]:
        print(f"\n{label}:")
        for m, rows in data.items():
            folder = MODELS[m]
            if "stall" in label:
                sub = [r for r in rows if longest_stall(raw_log(folder, r)) <= STALL_S]
                dropped = [f"{r['task']}-{r['cond']}-{r['rep']}" for r in rows if r not in sub]
            else:
                sub = [r for r in rows if keep(r)]
                dropped = None
            by_task = {t: split(sub, t) for t in TASKS if all(split(sub, t))}
            if not by_task:
                print(f"- {m}: no data")
                continue
            obs, p = pooled_one_sided(by_task, SENS_PERMS // 10)
            med = "; ".join(f"{t} {st.median(b):.1f}→{st.median(f):.1f}" for t, (b, f) in by_task.items())
            extra = f" (dropped: {', '.join(dropped) or 'none'})" if dropped is not None else ""
            print(f"- {m}: time saved {obs*100:.0f}%, p = {p:.4f}; medians {med}{extra}")

    print("\nTool calls denied by the test harness, mostly Bash (per arm):")
    for m, rows in data.items():
        for c in ("baseline", "speed"):
            n = sum(bash_denials(raw_log(MODELS[m], r)) for r in rows if r["cond"] == c)
            print(f"- {m} {c}: {n}")


if __name__ == "__main__":
    main()
