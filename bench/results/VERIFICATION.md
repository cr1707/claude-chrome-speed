# Independent verification of the pre-registered analysis

Files: Sonnet 5.5 = bench/results/sonnet-5-5/runs.jsonl; Opus 5.5 = bench/results/opus/runs.jsonl
Holm family size m = 12 (plan: 12). Seed 777; bootstrap 10000; Monte Carlo permutations 20000.

## A. Primary analysis, re-derived (compare with bench/analyze.py)

| Model | Task | n w/o / with | Median s (w/o → with) | Median change [boot 95% CI] | p mean-diff (exact) | p Holm | Correct w/o → with |
|---|---|---|---|---|---|---|---|
| Sonnet 5.5 | books | 10/10 | 27.5 → 15.4 | -44% [-51%, -32%] | 1.1e-05 | 0.0001 * | 10/10 → 10/10 |
| Sonnet 5.5 | form | 10/10 | 44.5 → 18.4 | -59% [-62%, -56%] | 1.1e-05 | 0.0001 * | 10/10 → 10/10 |
| Sonnet 5.5 | wiki | 10/10 | 28.5 → 21.2 | -25% [-30%, -20%] | 1.1e-05 | 0.0001 * | 10/10 → 10/10 |
| Sonnet 5.5 | spa | 10/10 | 49.6 → 23.7 | -52% [-61%, -48%] | 1.1e-05 | 0.0001 * | 10/10 → 10/10 |
| Sonnet 5.5 | catalog | 10/10 | 24.8 → 21.1 | -15% [-19%, -10%] | 2.2e-05 | 0.0002 * | 10/10 → 10/10 |
| Sonnet 5.5 | suppliers | 10/10 | 26.7 → 20.6 | -23% [-33%, -11%] | 0.0001 | 0.0007 * | 10/10 → 10/10 |
| Opus 5.5 | books | 10/10 | 17.4 → 15.4 | -11% [-15%, -1%] | 0.1475 | 0.2949 | 10/10 → 10/10 |
| Opus 5.5 | form | 10/10 | 43.7 → 20.4 | -53% [-66%, -31%] | 7.6e-05 | 0.0005 * | 10/10 → 10/10 |
| Opus 5.5 | wiki | 10/10 | 26.1 → 21.6 | -17% [-35%, +0%] | 0.0333 | 0.1331 | 10/10 → 10/10 |
| Opus 5.5 | spa | 10/10 | 58.5 → 26.2 | -55% [-62%, -50%] | 1.1e-05 | 0.0001 * | 10/10 → 10/10 |
| Opus 5.5 | catalog | 10/10 | 30.2 → 24.1 | -20% [-42%, -1%] | 0.0439 | 0.1331 | 10/10 → 10/10 |
| Opus 5.5 | suppliers | 10/10 | 23.7 → 20.7 | -13% [-24%, +16%] | 0.2619 | 0.2949 | 10/10 → 10/10 |

`*` = significant at 0.05 after Holm. CIs are 95% and not adjusted for multiplicity.

### Pooled per model (one-sided, plugin faster; plan test 2 = headline)

| Model | Tasks | Plan: mean time saved per task [boot CI] | p one-sided | Log scale: GM change [boot CI] | p one-sided |
|---|---|---|---|---|---|
| Sonnet 5.5 | 6 | 40% [34%, 44%] | 5.0e-05 | -39% [-43%, -36%] | 5.0e-05 |
| Opus 5.5 | 6 | 28% [23%, 33%] | 5.0e-05 | -30% [-35%, -26%] | 5.0e-05 |

The CIs are not in the plan; they describe the average over these six tasks only.

## B. Alternative methods

| Model | Task | p rank-sum (exact) | Holm | HL change [exact CI] | Pairs | Paired GM change | p sign-flip | Holm | Agree? |
|---|---|---|---|---|---|---|---|---|---|
| Sonnet 5.5 | books | 1.1e-05 | 0.0001 * | -42% [-50%, -35%] | 10 | -41% | 0.0020 | 0.0234 * | yes |
| Sonnet 5.5 | form | 1.1e-05 | 0.0001 * | -59% [-61%, -56%] | 10 | -58% | 0.0020 | 0.0234 * | yes |
| Sonnet 5.5 | wiki | 1.1e-05 | 0.0001 * | -26% [-30%, -21%] | 10 | -25% | 0.0020 | 0.0234 * | yes |
| Sonnet 5.5 | spa | 1.1e-05 | 0.0001 * | -53% [-59%, -48%] | 10 | -53% | 0.0020 | 0.0234 * | yes |
| Sonnet 5.5 | catalog | 2.2e-05 | 0.0002 * | -15% [-20%, -10%] | 10 | -27% | 0.0020 | 0.0234 * | yes |
| Sonnet 5.5 | suppliers | 0.0001 | 0.0008 * | -22% [-30%, -13%] | 10 | -22% | 0.0020 | 0.0234 * | yes |
| Opus 5.5 | books | 0.0855 | 0.1710 | -9% [-15%, +3%] | 10 | -8% | 0.0820 | 0.1641 | yes |
| Opus 5.5 | form | 0.0001 | 0.0008 * | -51% [-63%, -29%] | 10 | -50% | 0.0039 | 0.0234 * | yes |
| Opus 5.5 | wiki | 0.0335 | 0.1004 | -19% [-30%, -0%] | 10 | -19% | 0.0430 | 0.1641 | yes |
| Opus 5.5 | spa | 1.1e-05 | 0.0001 * | -57% [-62%, -50%] | 10 | -58% | 0.0020 | 0.0234 * | yes |
| Opus 5.5 | catalog | 0.0155 | 0.0620 | -19% [-37%, -4%] | 10 | -21% | 0.0410 | 0.1641 | yes |
| Opus 5.5 | suppliers | 0.1378 | 0.1710 | -8% [-23%, +3%] | 10 | -8% | 0.2930 | 0.2930 | yes |

HL CI achieved confidence: 95.7% (exact for continuous data; 0.1 s rounding ties make it approximate). Agree? = mean-diff and rank-sum give the same Holm verdict, and median, HL and paired changes have the same sign.

## S. Amendment-2 sensitivity analyses, re-derived (pooled plan statistic, one-sided)

- Sonnet 5.5, reps 6-10 only: 35% saved, p = 5.0e-05; GM change -37%, p = 5.0e-05
- Sonnet 5.5, no API stall > 60 s: 36% saved, p = 5.0e-05; GM change -38%, p = 5.0e-05 (dropped: catalog-baseline-4)
- Opus 5.5, reps 6-10 only: 28% saved, p = 5.0e-05; GM change -30%, p = 5.0e-05
- Opus 5.5, no API stall > 60 s: 28% saved, p = 5.0e-05; GM change -30%, p = 5.0e-05 (dropped: none)

Intention-to-treat check (excluded runs that did finish put back in place of their re-run):

- Sonnet 5.5: excluded per arm {'baseline': 1, 'speed': 1}; with them: suppliers: median change -19%, p mean-diff 0.0003, HL -21%; pooled 40% saved, p = 5.0e-05
- Opus 5.5: excluded per arm {'baseline': 1}; with them: spa: median change -56%, p mean-diff 1.1e-05, HL -58%; pooled 29% saved, p = 5.0e-05

## C. Design checks

Model id @ Claude Code version per task (both arms):

- Sonnet 5.5 books: claude-sonnet-5-5@2.1.296 reps 1-10
- Sonnet 5.5 form: claude-sonnet-5-5@2.1.296 reps 1-10
- Sonnet 5.5 wiki: claude-sonnet-5-5@2.1.296 reps 1-10
- Sonnet 5.5 spa: claude-sonnet-5-5@2.1.296 reps 1-10
- Sonnet 5.5 catalog: claude-sonnet-5-5@2.1.296 reps 1-10
- Sonnet 5.5 suppliers: claude-sonnet-5-5@2.1.296 reps 1-10
- Opus 5.5 books: claude-opus-5-5@2.1.281 reps 1-3 | claude-opus-5-5@2.1.296 reps 4-10
- Opus 5.5 form: claude-opus-5-5@2.1.281 reps 1-3 | claude-opus-5-5@2.1.296 reps 4-10
- Opus 5.5 wiki: claude-opus-5-5@2.1.281 reps 1-3 | claude-opus-5-5@2.1.296 reps 4-10
- Opus 5.5 spa: claude-opus-5-5@2.1.296 reps 1-10
- Opus 5.5 catalog: claude-opus-5-5@2.1.296 reps 1-10
- Opus 5.5 suppliers: claude-opus-5-5@2.1.296 reps 1-10

Order effect (2nd run of a back-to-back pair vs 1st; balanced alternation cancels it if it is equal in both arms):

- Sonnet 5.5: 2nd run +2% vs 1st (p = 0.5766, 59 pairs; re-run pairs left out)
- Opus 5.5: 2nd run +2% vs 1st (p = 0.6830, 59 pairs; re-run pairs left out)

Effect by Claude Code version, same tasks only (paired log ratios; low power, a warning sign only):

- Opus 5.5 on books, form, wiki: claude-opus-5-5@2.1.281 -33% (9 pairs) vs claude-opus-5-5@2.1.296 -26% (21 pairs); difference p = 0.3891

Time outside duration_ms (start of a run implied by duration_ms minus end of the previous run):

- Sonnet 5.5: baseline median 1.0 s (n=57); speed median 1.0 s (n=60) (a clear difference between arms = a cost duration_ms misses)
- Opus 5.5: baseline median 1.0 s (n=59); speed median 1.0 s (n=57) (a clear difference between arms = a cost duration_ms misses)

Data checks:
- Sonnet 5.5: 87 s gap inside one response, catalog/baseline/rep 4, next block: tool_use mcp__claude-in-chrome__javascript_tool 707 chars (long block = generation, short = stall)

## Cross-check against analyze.py output

Per-task rows compared: 12 (expected 12).
- everything within tolerance: analyze.py agrees
