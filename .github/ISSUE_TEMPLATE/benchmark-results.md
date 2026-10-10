---
name: Benchmark results
about: Share results from running the benchmark on your machine
title: "Results: <OS> / <model>"
labels: results
---

**Machine**
- OS and version:
- Display (e.g. 1x external, 2x Retina):
- Chrome version:
- Claude in Chrome extension version:
- Claude Code version (`claude --version`):
- Model (`--model`):

**Results**
Paste the output of `python3 bench/summarize.py <your runs.jsonl>`:

```
```

**Click quirk**
Does `bench/fixtures/click-probe.html` drop the first click until a screenshot?
- [ ] Yes, dropped until a screenshot
- [ ] No, the first click lands
- `document.hasFocus()` before the first click:

**Anything else**
Window in front or behind other apps, other extensions, anything unusual:
