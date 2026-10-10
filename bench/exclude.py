#!/usr/bin/env python3
"""Find and exclude infrastructure failures (ANALYSIS_PLAN.md, amendments 1 and 2).

A run is an infrastructure failure if its raw log contains "Browser extension is not
connected", or has no result event (it never finished). Excluding a run moves its raw log
to raw/excluded/, removes its row from runs.jsonl and records it in excluded.jsonl, so the
same task/arm/repetition can be run again once.

  python3 bench/exclude.py bench/results/opus            # list failures, change nothing
  python3 bench/exclude.py bench/results/opus --apply    # exclude them; prints "task cond rep"
"""
import json
import sys
import time
from pathlib import Path

MARKER = "Browser extension is not connected"


def failure_reason(raw_text):
    if MARKER in raw_text:
        return "browser extension not connected"
    for line in raw_text.splitlines():
        try:
            if json.loads(line).get("type") == "result":
                return None
        except json.JSONDecodeError:
            continue
    return "no result event (did not finish)"


def main():
    folder = Path(sys.argv[1])
    apply = "--apply" in sys.argv[2:]
    raw_dir, runs_path, log_path = folder / "raw", folder / "runs.jsonl", folder / "excluded.jsonl"
    rows = [json.loads(l) for l in runs_path.read_text().splitlines() if l.strip()] if runs_path.exists() else []

    failures = []
    for raw in sorted(raw_dir.glob("*.jsonl")):
        reason = failure_reason(raw.read_text())
        if reason:
            task, cond, rep = raw.stem.rsplit("-", 2)
            failures.append((task, cond, int(rep), reason, raw))

    for task, cond, rep, reason, raw in failures:
        print(f"{task} {cond} {rep}" + ("" if apply else f"   ({reason})"))
    if not apply or not failures:
        return

    (raw_dir / "excluded").mkdir(exist_ok=True)
    keys = {(t, c, r) for t, c, r, _, _ in failures}
    kept = [r for r in rows if (r["task"], r["cond"], int(r["rep"])) not in keys]
    runs_path.write_text("".join(json.dumps(r) + "\n" for r in kept))
    with log_path.open("a") as log:
        for task, cond, rep, reason, raw in failures:
            dest = raw_dir / "excluded" / raw.name
            n = 1
            while dest.exists():
                dest = raw_dir / "excluded" / f"{raw.stem}.{n}.jsonl"
                n += 1
            raw.rename(dest)
            log.write(json.dumps({"task": task, "cond": cond, "rep": rep, "reason": reason,
                                  "raw": str(dest.relative_to(folder)),
                                  "excluded_at": time.strftime("%Y-%m-%dT%H:%M:%S%z")}) + "\n")


if __name__ == "__main__":
    main()
