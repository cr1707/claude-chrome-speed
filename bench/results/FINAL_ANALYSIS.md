## Run counts (target 10 per task, arm and model)

- Sonnet 5.5: 120 runs; model ids {'claude-sonnet-5-5': 120}; all cells complete
- Opus 5.5: 120 runs; model ids {'unrecorded': 59, 'claude-opus-5-5': 61}; all cells complete

## Primary: per task (two-sided permutation test, Holm-corrected over 12 tests)

| Model | Task | Runs (without/with) | Median time (s) | Change [95% CI] | p (Holm) | Correct (without → with) |
|---|---|---|---|---|---|---|
| Sonnet 5.5 | `books` | 10/10 | 27.5 → 15.4 | **-44%** [-51%, -32%] | 0.0001 | 10/10 → 10/10 |
| Sonnet 5.5 | `form` | 10/10 | 44.5 → 18.4 | **-59%** [-62%, -56%] | 0.0001 | 10/10 → 10/10 |
| Sonnet 5.5 | `wiki` | 10/10 | 28.5 → 21.2 | **-25%** [-31%, -20%] | 0.0002 | 10/10 → 10/10 |
| Sonnet 5.5 | `spa` | 10/10 | 49.6 → 23.7 | **-52%** [-61%, -48%] | 0.0002 | 10/10 → 10/10 |
| Sonnet 5.5 | `catalog` | 10/10 | 24.8 → 21.1 | **-15%** [-19%, -10%] | 0.0002 | 10/10 → 10/10 |
| Sonnet 5.5 | `suppliers` | 10/10 | 26.7 → 20.6 | **-23%** [-33%, -11%] | 0.0007 | 10/10 → 10/10 |
| Opus 5.5 | `books` | 10/10 | 17.4 → 15.4 | -11% [-15%, +0%] | 0.2962 | 10/10 → 10/10 |
| Opus 5.5 | `form` | 10/10 | 43.7 → 20.4 | **-53%** [-66%, -31%] | 0.0004 | 10/10 → 10/10 |
| Opus 5.5 | `wiki` | 10/10 | 26.1 → 21.6 | -17% [-36%, +0%] | 0.1282 | 10/10 → 10/10 |
| Opus 5.5 | `spa` | 10/10 | 58.5 → 26.2 | **-55%** [-62%, -50%] | 0.0001 | 10/10 → 10/10 |
| Opus 5.5 | `catalog` | 10/10 | 30.2 → 24.1 | -20% [-42%, -1%] | 0.1282 | 10/10 → 10/10 |
| Opus 5.5 | `suppliers` | 10/10 | 23.7 → 20.7 | -13% [-24%, +16%] | 0.2962 | 10/10 → 10/10 |

## Primary: all tasks per model (one-sided permutation within tasks; headline statistic)

- Sonnet 5.5: mean time saved per task 40%, p = 0.0001
- Opus 5.5: mean time saved per task 28%, p = 0.0001

## Sensitivity analyses (secondary)

Rank-based test per task (Holm): Sonnet 5.5 books p=0.0006; Sonnet 5.5 form p=0.0006; Sonnet 5.5 wiki p=0.0006; Sonnet 5.5 spa p=0.0006; Sonnet 5.5 catalog p=0.0009; Sonnet 5.5 suppliers p=0.0009; Opus 5.5 books p=0.1678; Opus 5.5 form p=0.0008; Opus 5.5 wiki p=0.0993; Opus 5.5 spa p=0.0008; Opus 5.5 catalog p=0.0676; Opus 5.5 suppliers p=0.1678

Repetitions 6-10 only (collected after the plan):
- Sonnet 5.5: time saved 35%, p = 0.0005; medians books 29.0→16.4; form 44.2→18.2; wiki 29.0→21.2; spa 51.0→24.2; catalog 24.9→21.4; suppliers 27.7→19.8
- Opus 5.5: time saved 28%, p = 0.0005; medians books 17.6→15.4; form 36.0→20.4; wiki 26.4→21.3; spa 54.4→27.2; catalog 29.8→25.8; suppliers 26.6→20.8

Excluding runs with an API stall over 60 s:
- Sonnet 5.5: time saved 36%, p = 0.0005; medians books 27.5→15.4; form 44.5→18.4; wiki 28.5→21.2; spa 49.6→23.7; catalog 24.7→21.1; suppliers 26.7→20.6 (dropped: catalog-baseline-4)
- Opus 5.5: time saved 28%, p = 0.0005; medians books 17.4→15.4; form 43.7→20.4; wiki 26.1→21.6; spa 58.5→26.2; catalog 30.2→24.1; suppliers 23.7→20.7 (dropped: none)

Tool calls denied by the test harness, mostly Bash (per arm):
- Sonnet 5.5 baseline: 86
- Sonnet 5.5 speed: 30
- Opus 5.5 baseline: 29
- Opus 5.5 speed: 21
