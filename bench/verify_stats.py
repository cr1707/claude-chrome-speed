#!/usr/bin/env python3
"""Independent cross-check of bench/analyze.py (claude-chrome-speed). Standard library only, Python 3.8+.

Written outside the repo by a reviewer. It re-derives the pre-registered numbers with different
code and, where useful, different methods, so the final README numbers can be checked.

  A. Plan replication (primary, as pre-registered)
     - exact two-sided permutation p for the difference in mean time: full enumeration of all
       C(20,10) = 184,756 splits instead of 100,000 random shuffles; Holm over all cells
     - median % change with the same percentile bootstrap (own seed: CI ends may differ from
       analyze.py by ~1-2 points of Monte Carlo noise; the point estimate must match exactly)
     - pooled one-sided stratified permutation per model (the headline statistic)
  B. Alternative methods (sensitivity)
     - exact Wilcoxon rank-sum / Mann-Whitney p (enumeration with mid-ranks), Holm
       (analyze.py's rank-based sensitivity test is the Monte Carlo version of this)
     - Hodges-Lehmann change on log(time): the median of all with/without time ratios, with the
       exact distribution-free 95% CI from inverting the Mann-Whitney test
     - paired by repetition (the two arms of a task run back to back): exact sign-flip p on
       log(with/without), geometric-mean % change
     - pooled log-scale statistic (geometric-mean change averaged over tasks) and bootstrap CIs
  S. Amendment-2 sensitivity analyses, re-derived: repetitions 6-10 only, excluding API stalls
     over 60 s; plus an intention-to-treat check that puts excluded-but-finished runs back
  C. Design checks: n per cell, duplicates, unpaired reps, errors, time-outs, re-runs, model id and
     Claude Code version per run, order (carry-over) effect, effect by CLI block, start-up time
     outside duration_ms

Negative % = faster with the plugin. p values are two-sided unless marked one-sided.

Usage:
  python3 bench/verify_stats.py                                   # repo defaults (sonnet-5-5 + opus)
  python3 bench/analyze.py > /tmp/analyze_out.md            # then diff the two:
  python3 verify_stats.py --compare /tmp/analyze_out.md
  python3 verify_stats.py --sonnet path/runs.jsonl --label-sonnet "Sonnet 5" --opus path/runs.jsonl
"""
import argparse
import json
import math
import random
import re
import statistics as st
from collections import Counter, defaultdict
from datetime import datetime
from itertools import combinations
from pathlib import Path

TASKS = ["books", "form", "wiki", "spa", "catalog", "suppliers"]
EXPECTED_N = 10
ENUM_LIMIT = 3_000_000  # enumerate all splits up to this many, else Monte Carlo
STALL_S = 60


# ============================================================================ helpers
def fmt_pct(x):
    return "n/a" if x is None else f"{x * 100:+.0f}%"


def fmt_p(p):
    if p is None:
        return "n/a"
    return f"{p:.4f}" if p >= 0.0001 else f"{p:.1e}"


def star(p):
    return " *" if p is not None and p < 0.05 else ""


def midranks(values):
    order = sorted(range(len(values)), key=lambda i: values[i])
    ranks = [0.0] * len(values)
    i = 0
    while i < len(order):
        j = i
        while j + 1 < len(order) and values[order[j + 1]] == values[order[i]]:
            j += 1
        for k in range(i, j + 1):
            ranks[order[k]] = (i + j) / 2 + 1
        i = j + 1
    return ranks


def holm(pvals):
    """Holm step-down adjusted p-values; None entries are skipped. Returns (adjusted, m)."""
    idx = [i for i, p in enumerate(pvals) if p is not None]
    out, running = [None] * len(pvals), 0.0
    for rank, i in enumerate(sorted(idx, key=lambda i: pvals[i])):
        running = max(running, min(1.0, (len(idx) - rank) * pvals[i]))
        out[i] = running
    return out, len(idx)


# ============================================================================ two-sample methods
def split_test(values_b, values_f, rng, perms):
    """Two-sided permutation p for |mean(b) - mean(f)|; exact enumeration when feasible."""
    pooled = list(values_b) + list(values_f)
    nb, nf = len(values_b), len(values_f)
    total = sum(pooled)
    obs = abs(sum(values_b) / nb - sum(values_f) / nf)
    tol = 1e-9 * max(1.0, obs)
    n_splits = math.comb(nb + nf, nb)
    if n_splits <= ENUM_LIMIT:
        hits = 0
        for c in combinations(pooled, nb):
            s = sum(c)
            if abs(s / nb - (total - s) / nf) >= obs - tol:
                hits += 1
        return hits / n_splits, "exact"
    hits, work = 0, pooled[:]
    for _ in range(perms):
        rng.shuffle(work)
        s = sum(work[:nb])
        hits += abs(s / nb - (total - s) / nf) >= obs - tol
    return (hits + 1) / (perms + 1), "MC"


def mann_whitney_p(b, f, rng, perms):
    r = midranks(list(b) + list(f))  # mean rank is monotone in the rank sum: exact Wilcoxon test
    return split_test(r[:len(b)], r[len(b):], rng, perms)[0]


_UCACHE = {}


def u_null_cdf(m, n):
    """CDF of the Mann-Whitney U null distribution (continuous data) for sizes m, n."""
    if (m, n) not in _UCACHE:
        f = [[None] * (n + 1) for _ in range(m + 1)]
        for i in range(m + 1):
            for j in range(n + 1):
                if i == 0 or j == 0:
                    f[i][j] = [1]
                    continue
                row = [0] * (i * j + 1)
                for u, c in enumerate(f[i - 1][j]):
                    row[u + j] += c
                for u, c in enumerate(f[i][j - 1]):
                    row[u] += c
                f[i][j] = row
        total, acc, cdf = sum(f[m][n]), 0, []
        for c in f[m][n]:
            acc += c
            cdf.append(acc / total)
        _UCACHE[(m, n)] = cdf
    return _UCACHE[(m, n)]


def hodges_lehmann_log(b, f, alpha=0.05):
    """(change, lo, hi, achieved confidence); change = exp(HL shift of log time) - 1."""
    d = sorted(math.log(y) - math.log(x) for x in b for y in f)
    est = math.exp(st.median(d)) - 1
    cdf = u_null_cdf(len(b), len(f))
    cands = [k for k in range(len(cdf)) if cdf[k] <= alpha / 2]
    if not cands:
        return est, None, None, None
    c = max(cands)  # P(U <= c) <= alpha/2 -> CI = [D_(c+1), D_(mn-c)], 1-indexed
    return est, math.exp(d[c]) - 1, math.exp(d[len(d) - c - 1]) - 1, 1 - 2 * cdf[c]


def median_change_boot(b, f, rng, boots):
    point = (st.median(f) - st.median(b)) / st.median(b)
    draws = []
    for _ in range(boots):
        mf = st.median(rng.choices(f, k=len(f)))
        mb = st.median(rng.choices(b, k=len(b)))
        draws.append((mf - mb) / mb)
    draws.sort()
    return point, draws[int(0.025 * boots)], draws[int(0.975 * boots) - 1]


def paired_signflip(pairs, rng, perms):
    """pairs: [(b, f)]. Returns (geometric-mean change, two-sided sign-flip p); exact up to 2^20."""
    d = [math.log(f) - math.log(b) for b, f in pairs]
    k = len(d)
    if k < 2:
        return None, None
    obs = abs(sum(d))
    tol = 1e-9 * max(1.0, obs)
    if k <= 20:
        hits = 0
        for mask in range(1 << k):
            s = sum(-x if (mask >> i) & 1 else x for i, x in enumerate(d))
            hits += abs(s) >= obs - tol
        p = hits / (1 << k)
    else:
        hits = sum(abs(sum(x if rng.random() < 0.5 else -x for x in d)) >= obs - tol for _ in range(perms))
        p = (hits + 1) / (perms + 1)
    return math.exp(sum(d) / k) - 1, p


# ============================================================================ pooled / stratified
def _plan_stat(groups):
    return st.mean((sum(b) / len(b) - sum(f) / len(f)) / (sum(b) / len(b)) for b, f in groups)


def _log_stat(groups):
    return st.mean(sum(map(math.log, b)) / len(b) - sum(map(math.log, f)) / len(f) for b, f in groups)


def pooled_stratified(by_task, rng, perms):
    """One-sided (plugin faster) permutation, labels shuffled within task.

    plan: mean over tasks of (mean_b - mean_f) / mean_b      (analyze.py's headline statistic)
    log : mean over tasks of (mean log b - mean log f)        (reported as geometric-mean change)
    Returns (plan_obs, p_plan, gm_change, p_log).
    """
    groups = [(list(b), list(f)) for b, f in by_task.values()]
    obs_p, obs_l = _plan_stat(groups), _log_stat(groups)
    work = [(b + f, len(b)) for b, f in groups]
    hp = hl = 0
    for _ in range(perms):
        sh = []
        for pooled, nb in work:
            rng.shuffle(pooled)
            sh.append((pooled[:nb], pooled[nb:]))
        hp += _plan_stat(sh) >= obs_p - 1e-12
        hl += _log_stat(sh) >= obs_l - 1e-12
    return obs_p, (hp + 1) / (perms + 1), math.exp(-obs_l) - 1, (hl + 1) / (perms + 1)


def pooled_boot_ci(by_task, rng, boots):
    """Percentile CIs (bootstrap within task and arm) for the plan statistic and the GM change."""
    groups = [(list(b), list(f)) for b, f in by_task.values()]
    plan, lg = [], []
    for _ in range(boots):
        rs = [(rng.choices(b, k=len(b)), rng.choices(f, k=len(f))) for b, f in groups]
        plan.append(_plan_stat(rs))
        lg.append(_log_stat(rs))
    plan.sort()
    lg.sort()
    lo, hi = int(0.025 * boots), int(0.975 * boots) - 1
    return (plan[lo], plan[hi]), (math.exp(-lg[hi]) - 1, math.exp(-lg[lo]) - 1)


def strat_two_group_p(strata, rng, perms):
    """Two-sided stratified permutation p for the mean over strata of mean(g1) - mean(g2)."""
    def stat(groups):
        return st.mean(st.mean(a) - st.mean(b) for a, b in groups)
    groups = list(strata.values())
    obs = abs(stat(groups))
    work = [(a + b, len(a)) for a, b in groups]
    hits = 0
    for _ in range(perms):
        sh = []
        for pooled, na in work:
            rng.shuffle(pooled)
            sh.append((pooled[:na], pooled[na:]))
        hits += abs(stat(sh)) >= obs - 1e-12
    return obs, (hits + 1) / (perms + 1)


def order_effect(pairs_by_task, rng, perms):
    """run.py alternates: odd rep = baseline first, even rep = plugin first.

    With d = log(with/without): odd reps d = tau + pi, even reps d = tau - pi, where pi is the
    effect of running 2nd. Returns (pi as % change of the 2nd run, two-sided p, n pairs).
    """
    strata = {}
    for t, pairs in pairs_by_task.items():
        odd = [math.log(f / b) for rep, b, f in pairs if rep % 2 == 1]
        even = [math.log(f / b) for rep, b, f in pairs if rep % 2 == 0]
        if odd and even:
            strata[t] = (odd, even)
    if not strata:
        return None, None, 0
    obs, p = strat_two_group_p(strata, rng, perms)
    signed = st.mean(st.mean(o) - st.mean(e) for o, e in strata.values()) / 2
    return math.exp(signed) - 1, p, sum(len(o) + len(e) for o, e in strata.values())


# ============================================================================ data
def load_runs(path):
    return [json.loads(l) for l in Path(path).read_text().splitlines() if l.strip()]


def _ts(s):
    return datetime.fromisoformat(s.replace("Z", "+00:00"))


def read_raw(path):
    """Model id, CLI version, longest within-response gap (and the block after it), result info."""
    info = {"model": "?", "version": "?", "stall": 0.0, "stall_block": "", "result": False, "duration_s": None,
            "marker": False, "raw": False}
    p = Path(path)
    if not p.exists():
        return info
    text = p.read_text()
    info["raw"] = True
    info["marker"] = "Browser extension is not connected" in text
    by_msg = defaultdict(list)
    for line in text.splitlines():
        try:
            e = json.loads(line)
        except ValueError:
            continue
        t = e.get("type")
        if t == "system" and e.get("subtype") == "init":
            info["model"] = e.get("model") or "?"
            info["version"] = e.get("claude_code_version") or "?"
        elif t == "assistant" and e.get("timestamp"):
            by_msg[e.get("message", {}).get("id")].append(e)
        elif t == "result":
            info["result"] = True
            if e.get("duration_ms") is not None:
                info["duration_s"] = round(e["duration_ms"] / 1000, 1)
    for evs in by_msg.values():
        evs.sort(key=lambda e: e["timestamp"])
        for a, b in zip(evs, evs[1:]):
            gap = (_ts(b["timestamp"]) - _ts(a["timestamp"])).total_seconds()
            if gap > info["stall"]:
                blk = (b.get("message", {}).get("content") or [{}])[0]
                body = blk.get("input", blk.get("text", blk.get("thinking", "")))
                info["stall"] = gap
                info["stall_block"] = f"{blk.get('type', '?')} {blk.get('name', '')} {len(json.dumps(body))} chars".replace("  ", " ")
    return info


def uncaptured_overhead(runs, raw_dir):
    """Per arm: gap between the end of the previous run and the start implied by duration_ms.

    Uses raw-log modification times (written when the process exits) and the append order of
    runs.jsonl. Gaps outside 0-120 s (pauses, re-runs) are dropped. Best effort only.
    """
    out = defaultdict(list)
    prev_end = None
    for r in runs:
        p = Path(raw_dir) / f"{r['task']}-{r['cond']}-{r['rep']}.jsonl"
        if not p.exists():
            prev_end = None
            continue
        end = p.stat().st_mtime
        if prev_end is not None:
            gap = (end - r["duration_s"]) - prev_end
            if 0 <= gap <= 120:
                out[r["cond"]].append(gap)
        prev_end = end
    return out


def rep_ranges(reps):
    reps, out = sorted(reps), []
    start = prev = None
    for r in reps + [None]:
        if start is None:
            start = prev = r
        elif r is not None and r == prev + 1:
            prev = r
        else:
            out.append(f"{start}-{prev}" if start != prev else f"{start}")
            start = prev = r
    return ",".join(out)


def split_arms(rows, task):
    b = [r["duration_s"] for r in rows if r["task"] == task and r["cond"] == "baseline"]
    f = [r["duration_s"] for r in rows if r["task"] == task and r["cond"] == "speed"]
    return b, f


def by_task_of(rows):
    out = {}
    for t in TASKS:
        b, f = split_arms(rows, t)
        if b and f:
            out[t] = (b, f)
    return out


# ============================================================================ main
def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--repo", default=str(Path(__file__).resolve().parent.parent))
    ap.add_argument("--sonnet")
    ap.add_argument("--opus")
    ap.add_argument("--label-sonnet", default="Sonnet 5.5")
    ap.add_argument("--label-opus", default="Opus 5.5")
    ap.add_argument("--perms", type=int, default=20_000, help="Monte Carlo permutations (pooled, order, blocks)")
    ap.add_argument("--boots", type=int, default=10_000)
    ap.add_argument("--seed", type=int, default=777)
    ap.add_argument("--compare", help="saved output of `python3 bench/analyze.py`, diffed against these results")
    args = ap.parse_args()

    res = Path(args.repo) / "bench" / "results"
    files = {args.label_sonnet: Path(args.sonnet) if args.sonnet else res / "sonnet-5-5" / "runs.jsonl",
             args.label_opus: Path(args.opus) if args.opus else res / "opus" / "runs.jsonl"}
    rng = random.Random(args.seed)

    cells, checks = [], []
    data, raw_info, excluded, overhead = {}, {}, {}, {}
    for model, path in files.items():
        if not path.exists():
            checks.append(f"{model}: {path} not found, skipped")
            continue
        rows = load_runs(path)
        raw_dir = path.parent / "raw"
        data[model] = rows
        for k, v in Counter((r["task"], r["cond"], int(r["rep"])) for r in rows).items():
            if v > 1:
                checks.append(f"{model}: DUPLICATE {k} x{v}")
        info = {}
        for r in rows:
            i = read_raw(raw_dir / f"{r['task']}-{r['cond']}-{r['rep']}.jsonl")
            if r.get("model_id"):
                i["model"] = r["model_id"]
            if r.get("claude_code_version"):
                i["version"] = r["claude_code_version"]
            info[(r["task"], r["cond"], int(r["rep"]))] = i
            if r.get("error"):
                checks.append(f"{model}: error flag {r['task']}/{r['cond']}/rep {r['rep']} ({r['duration_s']} s)")
            if r["duration_s"] >= 890:
                checks.append(f"{model}: time-out (900 s cap) {r['task']}/{r['cond']}/rep {r['rep']}")
            if not i["raw"]:
                checks.append(f"{model}: no raw log for {r['task']}/{r['cond']}/rep {r['rep']}")
            elif i["marker"] or not i["result"]:
                checks.append(f"{model}: {r['task']}/{r['cond']}/rep {r['rep']} matches the infrastructure-failure "
                              f"rule ({'extension not connected' if i['marker'] else 'no result event'}) but is "
                              "still included: run bench/exclude.py, or keep it if it timed out after browser actions")
            if i["stall"] > STALL_S:
                checks.append(f"{model}: {i['stall']:.0f} s gap inside one response, {r['task']}/{r['cond']}/rep "
                              f"{r['rep']}, next block: {i['stall_block']} (long block = generation, short = stall)")
        raw_info[model] = info
        overhead[model] = uncaptured_overhead(rows, raw_dir)
        exc_path = path.parent / "excluded.jsonl"
        excluded[model] = load_runs(exc_path) if exc_path.exists() else []
        unknown = sorted({r["task"] for r in rows} - set(TASKS))
        if unknown:
            checks.append(f"{model}: tasks not in the plan, ignored: {unknown}")

        for t in TASKS:
            rb = {int(r["rep"]): r for r in rows if r["task"] == t and r["cond"] == "baseline"}
            rf = {int(r["rep"]): r for r in rows if r["task"] == t and r["cond"] == "speed"}
            b, f = split_arms(rows, t)
            if not b and not f:
                continue
            if len(b) != EXPECTED_N or len(f) != EXPECTED_N:
                checks.append(f"{model}: {t} n = {len(b)}/{len(f)} (plan {EXPECTED_N}/{EXPECTED_N})")
            if set(rb) ^ set(rf):
                checks.append(f"{model}: {t} reps in one arm only: {sorted(set(rb) ^ set(rf))}")
            ok = (sum(bool(r["correct"]) for r in rb.values()), sum(bool(r["correct"]) for r in rf.values()))
            cell = {"model": model, "task": t, "n": (len(b), len(f)), "correct": ok,
                    "med": (st.median(b) if b else None, st.median(f) if f else None)}
            if len(b) >= 2 and len(f) >= 2:
                cell["p_mean"], cell["kind"] = split_test(b, f, rng, args.perms)
                cell["p_mw"] = mann_whitney_p(b, f, rng, args.perms)
                cell["boot"] = median_change_boot(b, f, rng, args.boots)
                cell["hl"] = hodges_lehmann_log(b, f)
                pairs = [(rep, rb[rep]["duration_s"], rf[rep]["duration_s"]) for rep in sorted(set(rb) & set(rf))]
                cell["pairs"] = pairs
                cell["paired"] = paired_signflip([(x, y) for _, x, y in pairs], rng, args.perms)
            cells.append(cell)

    tested = [c for c in cells if "p_mean" in c]
    for key, src in (("p_mean_holm", "p_mean"), ("p_mw_holm", "p_mw")):
        adj, m = holm([c[src] for c in tested])
        for c, a in zip(tested, adj):
            c[key] = a
    adj, _ = holm([c["paired"][1] for c in tested])
    for c, a in zip(tested, adj):
        c["p_pair_holm"] = a

    # ------------------------------------------------------------------ A
    print("# Independent verification of the pre-registered analysis\n")
    print("Files: " + "; ".join(f"{k} = {v}" for k, v in files.items()))
    print(f"Holm family size m = {m} (plan: 12). Seed {args.seed}; bootstrap {args.boots}; "
          f"Monte Carlo permutations {args.perms}.\n")
    print("## A. Primary analysis, re-derived (compare with bench/analyze.py)\n")
    print("| Model | Task | n w/o / with | Median s (w/o → with) | Median change [boot 95% CI] | p mean-diff (exact) | p Holm | Correct w/o → with |")
    print("|---|---|---|---|---|---|---|---|")
    for c in cells:
        if "p_mean" not in c:
            print(f"| {c['model']} | {c['task']} | {c['n'][0]}/{c['n'][1]} | – | n<2 | – | – | – |")
            continue
        pt, lo, hi = c["boot"]
        print(f"| {c['model']} | {c['task']} | {c['n'][0]}/{c['n'][1]} | {c['med'][0]:.1f} → {c['med'][1]:.1f} | "
              f"{fmt_pct(pt)} [{fmt_pct(lo)}, {fmt_pct(hi)}] | {fmt_p(c['p_mean'])}{'' if c['kind'] == 'exact' else ' (MC)'} | "
              f"{fmt_p(c['p_mean_holm'])}{star(c['p_mean_holm'])} | {c['correct'][0]}/{c['n'][0]} → {c['correct'][1]}/{c['n'][1]} |")
    print("\n`*` = significant at 0.05 after Holm. CIs are 95% and not adjusted for multiplicity.\n")

    print("### Pooled per model (one-sided, plugin faster; plan test 2 = headline)\n")
    print("| Model | Tasks | Plan: mean time saved per task [boot CI] | p one-sided | Log scale: GM change [boot CI] | p one-sided |")
    print("|---|---|---|---|---|---|")
    pooled_out = {}
    for model, rows in data.items():
        bt = by_task_of(rows)
        if not bt:
            continue
        ps, pp, gm, pl = pooled_stratified(bt, rng, args.perms)
        (plo, phi), (glo, ghi) = pooled_boot_ci(bt, rng, args.boots)
        pooled_out[model] = (ps, pp)
        print(f"| {model} | {len(bt)} | {ps * 100:.0f}% [{plo * 100:.0f}%, {phi * 100:.0f}%] | {fmt_p(pp)} | "
              f"{fmt_pct(gm)} [{fmt_pct(glo)}, {fmt_pct(ghi)}] | {fmt_p(pl)} |")
    print("\nThe CIs are not in the plan; they describe the average over these six tasks only.\n")

    # ------------------------------------------------------------------ B
    print("## B. Alternative methods\n")
    print("| Model | Task | p rank-sum (exact) | Holm | HL change [exact CI] | Pairs | Paired GM change | p sign-flip | Holm | Agree? |")
    print("|---|---|---|---|---|---|---|---|---|---|")
    for c in tested:
        hl, hlo, hhi, conf = c["hl"]
        ci = f"[{fmt_pct(hlo)}, {fmt_pct(hhi)}]" if conf else "[n too small]"
        gm, pp = c["paired"]
        signs = {math.copysign(1, v) for v in (c["boot"][0], hl, gm) if v}
        agree = "yes" if (c["p_mean_holm"] < 0.05) == (c["p_mw_holm"] < 0.05) and len(signs) <= 1 else "**NO**"
        print(f"| {c['model']} | {c['task']} | {fmt_p(c['p_mw'])} | {fmt_p(c['p_mw_holm'])}{star(c['p_mw_holm'])} | "
              f"{fmt_pct(hl)} {ci} | {len(c['pairs'])} | {fmt_pct(gm)} | {fmt_p(pp)} | "
              f"{fmt_p(c['p_pair_holm'])}{star(c['p_pair_holm'])} | {agree} |")
    confs = {round(c["hl"][3] * 100, 1) for c in tested if c["hl"][3]}
    print(f"\nHL CI achieved confidence: {', '.join(f'{x}%' for x in sorted(confs)) or 'n/a'} "
          "(exact for continuous data; 0.1 s rounding ties make it approximate). Agree? = mean-diff and "
          "rank-sum give the same Holm verdict, and median, HL and paired changes have the same sign.\n")

    # ------------------------------------------------------------------ S
    print("## S. Amendment-2 sensitivity analyses, re-derived (pooled plan statistic, one-sided)\n")
    for model, rows in data.items():
        info = raw_info[model]
        late = [r for r in rows if int(r["rep"]) >= 6]
        nostall = [r for r in rows if info[(r["task"], r["cond"], int(r["rep"]))]["stall"] <= STALL_S]
        dropped = [f"{r['task']}-{r['cond']}-{r['rep']}" for r in rows
                   if info[(r["task"], r["cond"], int(r["rep"]))]["stall"] > STALL_S]
        variants = [("reps 6-10 only", late), (f"no API stall > {STALL_S} s", nostall)]
        if not all(r["correct"] for r in rows):  # not in the plan: only shown when some answers are wrong
            variants.append(("correct answers only (not in the plan)", [r for r in rows if r["correct"]]))
        for label, sub in variants:
            bt = by_task_of(sub)
            if not bt:
                print(f"- {model}, {label}: no data")
                continue
            ps, pp, gm, pl = pooled_stratified(bt, rng, args.perms)
            extra = f" (dropped: {', '.join(dropped) or 'none'})" if "stall" in label else ""
            print(f"- {model}, {label}: {ps * 100:.0f}% saved, p = {fmt_p(pp)}; GM change {fmt_pct(gm)}, "
                  f"p = {fmt_p(pl)}{extra}")
            pooled_out[(model, label)] = (ps, pp)
    print("\nIntention-to-treat check (excluded runs that did finish put back in place of their re-run):\n")
    any_itt = False
    for model, exc in excluded.items():
        if not exc:
            continue
        rows = data[model]
        folder = files[model].parent
        itt = [dict(r) for r in rows]
        per_arm = Counter(e["cond"] for e in exc)
        touched = set()
        seen = set()
        for e in exc:
            key = (e["task"], e["cond"], int(e["rep"]))
            if key in seen:
                continue  # only the first (original) attempt counts for ITT
            seen.add(key)
            i = read_raw(folder / e["raw"])
            if not i["result"] or i["duration_s"] is None:
                continue
            match = [r for r in itt if (r["task"], r["cond"], int(r["rep"])) == key]
            if match:
                match[0]["duration_s"] = i["duration_s"]
            else:
                itt.append({"task": key[0], "cond": key[1], "rep": key[2], "duration_s": i["duration_s"]})
            touched.add(key[0])
        line = f"- {model}: excluded per arm {dict(per_arm)}"
        if touched:
            any_itt = True
            parts = []
            for t in sorted(touched):
                b, f = split_arms(itt, t)
                p, _ = split_test(b, f, rng, args.perms)
                parts.append(f"{t}: median change {fmt_pct((st.median(f) - st.median(b)) / st.median(b))}, "
                             f"p mean-diff {fmt_p(p)}, HL {fmt_pct(hodges_lehmann_log(b, f)[0])}")
            ps, pp, _, _ = pooled_stratified(by_task_of(itt), rng, args.perms)
            line += "; with them: " + "; ".join(parts) + f"; pooled {ps * 100:.0f}% saved, p = {fmt_p(pp)}"
        else:
            line += "; none of them finished, nothing to put back"
        print(line)
    if not any_itt and not any(excluded.values()):
        print("- no excluded.jsonl entries")

    # ------------------------------------------------------------------ C
    print("\n## C. Design checks\n")
    print("Model id @ Claude Code version per task (both arms):\n")
    for model, info in raw_info.items():
        for t in TASKS:
            comp = defaultdict(set)
            for (tt, c, rep), i in info.items():
                if tt == t:
                    comp[(i["model"], i["version"])].add(rep)
            if comp:
                print(f"- {model} {t}: " + " | ".join(f"{mv[0]}@{mv[1]} reps {rep_ranges(reps)}"
                                                     for mv, reps in sorted(comp.items(), key=lambda kv: min(kv[1]))))
        ids = {i["model"] for i in info.values()}
        if len(ids) > 1:
            print(f"  **Warning: {model} mixes model ids {sorted(ids)}**")
        for (t, rep) in sorted({(k[0], k[2]) for k in info}):
            mb, mf = info.get((t, "baseline", rep)), info.get((t, "speed", rep))
            if mb and mf and (mb["model"], mb["version"]) != (mf["model"], mf["version"]):
                checks.append(f"{model}: {t} rep {rep}: arms on different model/CLI")

    print("\nOrder effect (2nd run of a back-to-back pair vs 1st; balanced alternation cancels it if it is equal in both arms):\n")
    for model, rows in data.items():
        pbt = {c["task"]: c["pairs"] for c in tested if c["model"] == model}
        reruns = {(e["task"], int(e["rep"])) for e in excluded.get(model, [])}
        pbt = {t: [p for p in prs if (t, p[0]) not in reruns] for t, prs in pbt.items()}
        pi, p, n = order_effect(pbt, rng, args.perms)
        if pi is not None:
            print(f"- {model}: 2nd run {fmt_pct(pi)} vs 1st (p = {fmt_p(p)}, {n} pairs; re-run pairs left out)")

    print("\nEffect by Claude Code version, same tasks only (paired log ratios; low power, a warning sign only):\n")
    shown = False
    for model, info in raw_info.items():
        blocks = defaultdict(lambda: defaultdict(list))
        for c in tested:
            if c["model"] != model:
                continue
            for rep, x, y in c["pairs"]:
                ib, iff = info[(c["task"], "baseline", rep)], info[(c["task"], "speed", rep)]
                if (ib["model"], ib["version"]) == (iff["model"], iff["version"]):
                    blocks[(ib["model"], ib["version"])][c["task"]].append(math.log(y / x))
        keys = sorted(blocks, key=lambda k: (k[1], k[0]))
        if len(keys) < 2:
            continue
        common = [t for t in TASKS if sum(1 for k in keys if blocks[k].get(t)) >= 2]
        if not common:
            continue
        shown = True
        strata = {t: (blocks[keys[0]].get(t, []), [x for k in keys[1:] for x in blocks[k].get(t, [])]) for t in common}
        strata = {t: v for t, v in strata.items() if v[0] and v[1]}
        _, p = strat_two_group_p(strata, rng, args.perms)
        desc = " vs ".join(
            f"{k[0]}@{k[1]} {fmt_pct(math.exp(st.mean(st.mean(blocks[k][t]) for t in common if blocks[k].get(t))) - 1)}"
            f" ({sum(len(blocks[k].get(t, [])) for t in common)} pairs)" for k in keys)
        print(f"- {model} on {', '.join(common)}: {desc}; difference p = {fmt_p(p)}")
    if not shown:
        print("- one model/CLI block per task: nothing to compare")

    print("\nTime outside duration_ms (start of a run implied by duration_ms minus end of the previous run):\n")
    for model, ov in overhead.items():
        parts = [f"{arm} median {st.median(v):.1f} s (n={len(v)})" for arm, v in sorted(ov.items()) if v]
        if parts:
            print(f"- {model}: " + "; ".join(parts) + " (a clear difference between arms = a cost duration_ms misses)")

    print("\nData checks:")
    print("\n".join(f"- {x}" for x in checks) if checks else "- none")

    if args.compare:
        compare_with_analyze(Path(args.compare), tested, pooled_out, list(files))


# ============================================================================ diff against analyze.py
def _num(x):
    return float(x.replace("*", "").replace("%", "").replace("+", "").strip())


def compare_with_analyze(path, tested, pooled_out, labels):
    print("\n## Cross-check against analyze.py output\n")
    mine = {(c["model"], c["task"]): c for c in tested}
    problems, seen = [], 0
    section = ""
    lab = "|".join(re.escape(x) for x in labels)
    for line in path.read_text().splitlines():
        if line.startswith("Repetitions 6-10"):
            section = "reps 6-10 only"
        elif line.startswith("Excluding runs with an API stall"):
            section = f"no API stall > {STALL_S} s"
        elif line.startswith("## Primary: all tasks") or line.startswith("Bash calls"):
            section = "pooled" if line.startswith("## Primary") else ""
        cols = [x.strip() for x in line.strip().strip("|").split("|")]
        if len(cols) == 7 and cols[0] in labels:
            key = (cols[0], cols[1].strip("`"))
            c = mine.get(key)
            if not c:
                problems.append(f"{key}: in analyze.py output but not here")
                continue
            seen += 1
            med = [float(x) for x in cols[3].split("→")]
            if any(abs(a - b) > 0.051 for a, b in zip(med, c["med"])):
                problems.append(f"{key}: medians {med} vs {c['med']}")
            point = _num(cols[4].split("[")[0])
            if abs(point - c["boot"][0] * 100) > 0.51:
                problems.append(f"{key}: median change {point}% vs {c['boot'][0] * 100:.1f}%")
            lo, hi = (_num(x) for x in cols[4].split("[")[1].rstrip("]").split(","))
            if abs(lo - c["boot"][1] * 100) > 4 or abs(hi - c["boot"][2] * 100) > 4:
                problems.append(f"{key}: bootstrap CI [{lo}, {hi}] vs [{c['boot'][1] * 100:.0f}, {c['boot'][2] * 100:.0f}]")
            p_mc, p_ex = float(cols[5]), c["p_mean_holm"]
            se = 12 * math.sqrt(max(c["p_mean"], 1e-5) * (1 - c["p_mean"]) / 100_000)
            if abs(p_mc - p_ex) > 4 * se + 1e-4:
                problems.append(f"{key}: Holm p {p_mc} vs exact {p_ex:.4f} (beyond Monte Carlo noise)")
            if (p_mc < 0.05) != (p_ex < 0.05):
                problems.append(f"{key}: VERDICT differs (analyze {p_mc}, exact {p_ex:.4f}): report the exact p")
            continue
        if line.startswith("Rank-based test per task (Holm):"):
            for m_, t_, p_ in re.findall(rf"({lab}) (\w+) p=([\d.]+)", line):
                c = mine.get((m_, t_))
                if not c:
                    continue
                p_mc, p_ex = float(p_), c["p_mw_holm"]
                se = 12 * math.sqrt(max(c["p_mw"], 1e-5) * (1 - c["p_mw"]) / 20_000)
                if abs(p_mc - p_ex) > 4 * se + 5e-4:
                    problems.append(f"rank test {m_} {t_}: Holm p {p_mc} vs exact {p_ex:.4f}")
                if (p_mc < 0.05) != (p_ex < 0.05):
                    problems.append(f"rank test {m_} {t_}: VERDICT differs (analyze {p_mc}, exact {p_ex:.4f})")
            continue
        m1 = re.match(rf"^- ({lab}): mean time saved per task (-?\d+)%, p = ([\d.]+)", line)
        m2 = re.match(rf"^- ({lab}): time saved (-?\d+)%, p = ([\d.]+)", line)
        m3 = re.match(rf"^({lab}), all tasks: mean relative time saved (-?\d+)%, one-sided p = ([\d.]+)", line)
        hit = m1 or m3 or (m2 if section.startswith(("reps", "no API")) else None)
        if hit:
            model, saved, p_mc = hit.group(1), float(hit.group(2)), float(hit.group(3))
            key = model if (m1 or m3) else (model, section)
            n_perm = 10_000 if (m1 or m3) else 2_000
            if key not in pooled_out:
                problems.append(f"{key}: in analyze.py output but not re-derived here")
                continue
            ps, pp = pooled_out[key]
            if abs(saved - ps * 100) > 0.51:
                problems.append(f"{key}: saving {saved}% vs {ps * 100:.1f}%")
            v = max(pp, 1e-4) * (1 - pp)
            if abs(p_mc - pp) > 4 * (math.sqrt(v / n_perm) + math.sqrt(v / 20_000)) + 5e-4:
                problems.append(f"{key}: p {p_mc} vs {pp:.4f} (beyond Monte Carlo noise)")
    print(f"Per-task rows compared: {seen} (expected {len(tested)}).")
    print("\n".join(f"- {x}" for x in problems) if problems else "- everything within tolerance: analyze.py agrees")


if __name__ == "__main__":
    main()
