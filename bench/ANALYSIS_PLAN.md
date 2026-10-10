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

## Amendment 2: models, exclusions and sensitivity analyses (2026-10-10, before the final analysis)

An independent audit of the runs collected so far found the following. These changes were
decided before the remaining runs were collected and before any final test was run.

**Two Sonnet models.** Updating Claude Code from 2.1.281 to 2.1.296 changed what the alias
`--model sonnet` points to: `books`, `form` and `wiki` repetitions 1–5 ran on
`claude-sonnet-5`, the new tasks on `claude-sonnet-5-5`. From now on the full model id is
passed, and every row records `model_id` and `claude_code_version`.
- The final Sonnet results use **`claude-sonnet-5-5` only**: all six tasks, 10 repetitions
  per arm, in `bench/results/sonnet-5-5/`. `books`, `form` and `wiki` are collected again from
  repetition 1 on this model.
- The `claude-sonnet-5` runs are a pilot, kept in `bench/results/sonnet-5/` and reported
  separately. They are not part of the final tests.
- Opus is `claude-opus-5-5` throughout. Its `books`, `form` and `wiki` repetitions 1–3 ran on
  Claude Code 2.1.281, everything else on 2.1.296; both arms are affected equally. This is
  disclosed.

**Infrastructure failures (complete list so far).** Amendment 1 named one run, but its rule
matches three: Sonnet 5.5 `suppliers` repetition 5 in both arms (no answer), and Opus `spa`
baseline repetition 1 (disconnected at its first browser action, recovered, 121 s). All
three are excluded with `bench/exclude.py`, which moves the raw log to `raw/excluded/`,
removes the row and records it in `excluded.jsonl`. Each excluded run is collected again
once at the end; later failures are handled the same way. The scripts refuse to overwrite a
raw log, and `analyze.py` stops on duplicate rows and reports cells that are not at 10.

**Headline statistic.** The headline per model is the pooled statistic from test 2 (mean time
saved per task, stratified permutation test), not a median pooled across tasks.

**Sensitivity analyses (secondary, reported next to the primary results):**
1. A rank-based permutation test per task, Holm-corrected.
2. Repetitions 6–10 only: collected after this plan, all on Claude Code 2.1.296.
3. Excluding runs with an API stall over 60 s inside a single model response (one Sonnet 5.5
   pilot-era run had an 87 s stall).
4. Bash calls denied by the test harness, counted per arm. The harness allows only the
   browser tools in both arms and this stays unchanged, so the arms remain comparable.

**Disclosure.** The three new tasks were designed by the plugin's author after the rules were
written, and two of them involve situations the rules address (fields that only register real
input events; paginated data). The rules were not changed for them.

## Amendment 3: independent review (2026-10-10, before the final analysis)

An independent statistical review checked `analyze.py` against exact calculations and
synthetic data with known effects: the implementation matches this plan, and its false-positive
rate is about 5% as intended. Following the review:

- **Exclusion tool aligned with amendment 1.** `bench/exclude.py` now excludes only runs where
  the browser was not connected, or that ended without a result before any browser action
  completed. A run that did browser work and then timed out is a real (slow) outcome and stays
  in. Exclusions are reported per arm.
- **Additional reported analyses** (secondary, computed by `bench/verify_stats.py`, written by
  the reviewer): an exact rank test per task; the Hodges–Lehmann change on log time with an
  exact confidence interval, as a robust "typical % change"; a paired analysis of the
  back-to-back runs with a check for an order effect; and an intention-to-treat check that puts
  completed excluded runs back in. The 12 per-task tests and the 2 pooled tests are separate
  families; Holm correction applies within the 12.
- **Disclosures added to the report:** between about 11:00 and 11:25 CEST the review ran
  simulations on the same Mac at background priority while runs were being collected (both arms
  alternate back to back, so any effect should be equal); Claude Code is not updated again until
  collection ends, and each row records its version.
