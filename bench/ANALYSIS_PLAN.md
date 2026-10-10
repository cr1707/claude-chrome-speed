# Analysis plan

Written on 2026-10-10, before the final data was collected. The analysis in
[`analyze.py`](analyze.py) follows this plan and was committed with it.

## What was already seen

- Tasks `books`, `form` and `wiki`: a pilot of 5 runs per task, arm and model, on Sonnet and Opus.
- Tasks `spa`, `catalog` and `suppliers`: their first 5 runs per arm and model were in progress
  when this plan was written.

The pilot was used only to choose the sample size below. Nothing in the plugin's rules was
changed after the pilot, and the rules are not tuned to the new tasks.

## Design

- 6 tasks × 2 arms (without / with the plugin) × 2 models (Sonnet, Opus).
- **10 runs per task, arm and model**: 240 runs in total. This number is fixed. No runs are
  added or removed after looking at the results.
- Each run is a fresh headless `claude -p --chrome` session in an empty temporary folder. The two
  arms alternate order on each repetition.
- A run counts as correct only if its answer contains every expected value in `tasks.json`.

## Outcomes

- **Primary:** wall-clock time per run (`duration_ms` reported by Claude Code).
- **Secondary:** turns, input tokens, correctness.

## Tests

1. **Per task and model (12 tests):** two-sided permutation test on the difference in mean
   time between arms (100,000 random permutations). Significance threshold 0.05 after
   **Holm correction** across all 12 tests.
2. **Per model, all tasks pooled (2 tests):** one-sided permutation test that shuffles the arm
   labels within each task, on the mean relative change in time.
3. **Effect sizes:** median change in time per task, with a 95% bootstrap confidence interval
   (10,000 resamples), reported for every task whether significant or not.
4. **Correctness:** reported as counts per arm. If the plugin arm gets fewer answers right on
   any task, that is reported next to the time result.

## Reporting

All 12 per-task results go in the README, including the ones that are not significant. The
headline claims are limited to what the tests above support.

## Amendment 1: infrastructure failures (2026-10-10, before the final analysis)

During data collection one run (`suppliers`, baseline, Sonnet, repetition 5) never reached
the browser: every browser tool returned "Browser extension is not connected". That is a
failure of the test setup, not a result about the plugin.

Rule, applied the same way to both arms and decided without looking at timing results:
- A run is an **infrastructure failure** if any browser tool result in its log contains
  "Browser extension is not connected", or if the run times out before its first browser
  action completes.
- Infrastructure failures are excluded, listed in `bench/results/excluded.jsonl`, and re-run
  once with the same task, arm, model and repetition number after the main collection ends.
- If the re-run fails the same way, the cell is reported as missing, not imputed.
