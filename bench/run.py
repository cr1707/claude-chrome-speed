#!/usr/bin/env python3
"""A/B benchmark: the same browser tasks with and without the chrome-speed plugin.

Each run is a fresh headless `claude -p --chrome` session. Conditions alternate
order every repetition so time-of-day drift hits both arms equally.

Usage:
  python3 bench/run.py --reps 3                 # full matrix
  python3 bench/run.py --tasks form --conds speed --reps 1   # one run
  python3 bench/run.py --regrade                # re-score saved runs
"""
import argparse
import json
import os
import re
import subprocess
import sys
import tempfile
import time
from collections import Counter
from pathlib import Path

REPO = Path(__file__).resolve().parent.parent
BENCH = REPO / "bench"


def normalise(text):
    # Drop thousands separators between digits so "2,047,602" matches "2047602".
    return re.sub(r"(?<=\d)[,   ](?=\d{3}\b)", "", text)


def grade(task, result):
    flat = normalise(result)
    missing = [e for e in task["expect_all"] if e.lower() not in result.lower() and e.lower() not in flat.lower()]
    return not missing, missing


def tool_stats(events):
    calls = Counter()
    screenshots = 0
    tiny = 0  # scale < 0.25: a few hundred tokens, used to prime ref clicks

    def visit(name, inp):
        nonlocal screenshots, tiny
        short = name.replace("mcp__claude-in-chrome__", "")
        calls[short] += 1
        if short == "computer" and inp.get("action") in ("screenshot", "zoom"):
            if (inp.get("scale") or 1) < 0.25:
                tiny += 1
            else:
                screenshots += 1
        if short == "browser_batch":
            for item in inp.get("actions", []):
                visit(item.get("name", ""), item.get("input", {}))

    for ev in events:
        if ev.get("type") != "assistant":
            continue
        for block in ev.get("message", {}).get("content", []):
            if block.get("type") == "tool_use":
                visit(block["name"], block.get("input", {}))
    return calls, screenshots, tiny


def run_one(task, cond, rep, model, cwd, settings, raw_dir):
    cmd = [
        "claude", "-p", "--chrome",
        "--model", model,
        "--output-format", "stream-json", "--verbose",
        "--no-session-persistence",
        "--setting-sources", "project",
        "--strict-mcp-config",
        "--settings", str(settings),
    ]
    if cond == "speed":
        cmd += ["--plugin-dir", str(REPO)]
    cmd.append(task["prompt"])

    t0 = time.time()
    try:
        proc = subprocess.run(cmd, cwd=cwd, capture_output=True, text=True, timeout=900)
        stdout = proc.stdout
    except subprocess.TimeoutExpired as e:
        stdout = e.stdout.decode() if isinstance(e.stdout, bytes) else (e.stdout or "")
    wall = time.time() - t0

    raw_path = raw_dir / f"{task['id']}-{cond}-{rep}.jsonl"
    raw_path.write_text(stdout)
    return score(task, cond, rep, model, stdout, wall)


def score(task, cond, rep, model, stdout, wall=0.0):
    events = []
    for line in stdout.splitlines():
        try:
            events.append(json.loads(line))
        except json.JSONDecodeError:
            pass
    final = next((e for e in reversed(events) if e.get("type") == "result"), {})
    result_text = final.get("result") or ""
    # Grade everything Claude said, not just the last message: a run that gives the
    # answer and then reports "closed the tab" still answered correctly.
    said = [b.get("text", "") for e in events if e.get("type") == "assistant"
            for b in e.get("message", {}).get("content", []) if b.get("type") == "text"]
    ok, missing = grade(task, "\n".join(said + [result_text]))
    calls, screenshots, tiny = tool_stats(events)
    usage = final.get("usage", {})

    return {
        "task": task["id"],
        "cond": cond,
        "rep": rep,
        "model": model,
        "correct": ok,
        "missing": missing,
        "duration_s": round(final.get("duration_ms", wall * 1000) / 1000, 1),
        "turns": final.get("num_turns"),
        "browser_actions": sum(v for k, v in calls.items() if k not in ("ToolSearch", "Skill")),
        "screenshots": screenshots,
        "tiny_screenshots": tiny,
        "tool_calls": dict(calls),
        "input_tokens": usage.get("input_tokens", 0) + usage.get("cache_read_input_tokens", 0) + usage.get("cache_creation_input_tokens", 0),
        "output_tokens": usage.get("output_tokens", 0),
        "cost_usd_list": round(final.get("total_cost_usd", 0), 4),
        "error": final.get("is_error", True) or not final,
        "result": result_text[:600],
    }


def regrade(out):
    raw_dir = out.parent / "raw"
    """Re-score every row in runs.jsonl from its raw log, e.g. after fixing grade()."""
    tasks = {t["id"]: t for t in json.loads((BENCH / "tasks.json").read_text())}
    rows = [json.loads(l) for l in out.read_text().splitlines() if l.strip()]
    fresh = []
    for r in rows:
        raw = (raw_dir / f"{r['task']}-{r['cond']}-{r['rep']}.jsonl").read_text()
        fresh.append(score(tasks[r["task"]], r["cond"], r["rep"], r["model"], raw))
    out.write_text("".join(json.dumps(r) + "\n" for r in fresh))
    changed = sum(a["correct"] != b["correct"] for a, b in zip(rows, fresh))
    print(f"regraded {len(fresh)} runs, {changed} verdicts changed")


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--reps", type=int, default=3)
    ap.add_argument("--start-rep", type=int, default=1, help="number of the first repetition, to add runs to an existing results file")
    ap.add_argument("--tasks", default="")
    ap.add_argument("--conds", default="baseline,speed")
    ap.add_argument("--model", default="sonnet")
    ap.add_argument("--out", default=str(BENCH / "results" / "runs.jsonl"))
    ap.add_argument("--regrade", action="store_true", help="re-score existing runs from raw logs, run nothing")
    args = ap.parse_args()
    if args.regrade:
        return regrade(Path(args.out))

    tasks = json.loads((BENCH / "tasks.json").read_text())
    if args.tasks:
        keep = set(args.tasks.split(","))
        tasks = [t for t in tasks if t["id"] in keep]
    conds = args.conds.split(",")

    out = Path(args.out)
    # Raw logs sit next to the runs file, so each model's results stay separate.
    raw_dir = out.parent / "raw"
    raw_dir.mkdir(parents=True, exist_ok=True)
    # An empty working directory outside the repo, so no CLAUDE.md, memory or
    # skills from any parent folder leak into either arm.
    cwd = tempfile.mkdtemp(prefix="chrome-speed-bench-")
    settings = BENCH / "settings.json"

    for rep in range(args.start_rep, args.start_rep + args.reps):
        for task in tasks:
            order = conds if rep % 2 else list(reversed(conds))
            for cond in order:
                print(f"[rep {rep}] {task['id']:<6} {cond:<8} …", end=" ", flush=True)
                row = run_one(task, cond, rep, args.model, cwd, settings, raw_dir)
                with out.open("a") as f:
                    f.write(json.dumps(row) + "\n")
                print(f"{row['duration_s']:>6}s  turns={row['turns']}  shots={row['screenshots']}  "
                      f"ok={row['correct']}", flush=True)


if __name__ == "__main__":
    sys.exit(main())
