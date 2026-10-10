#!/usr/bin/env python3
"""Draw the README results chart from the final benchmark data.

Medians come from bench/results/sonnet-5-5/runs.jsonl and bench/results/opus/runs.jsonl.
Which tasks are significant after Holm correction, and the average time saved per model,
come from bench/results/FINAL_ANALYSIS.md (the output of bench/analyze.py), so the chart
shows exactly what the pre-registered analysis found. The medians are checked against that
file before anything is drawn.

Writes docs/results.svg (light) and docs/results-dark.svg (dark). Standard library only:

  python3 bench/chart.py
"""
import json
import math
import re
import statistics
from pathlib import Path

REPO = Path(__file__).resolve().parent.parent
RESULTS = REPO / "bench" / "results"
ANALYSIS = RESULTS / "FINAL_ANALYSIS.md"
TASKS = [t["id"] for t in json.loads((REPO / "bench" / "tasks.json").read_text())]
DOCS = REPO / "docs"

# Panel label, which must match the model name used in FINAL_ANALYSIS.md, and its runs file.
PANELS = [
    ("Sonnet 5.5", RESULTS / "sonnet-5-5" / "runs.jsonl"),
    ("Opus 5.5", RESULTS / "opus" / "runs.jsonl"),
]

FONT = "-apple-system, BlinkMacSystemFont, 'Segoe UI', 'Noto Sans', Helvetica, Arial, sans-serif"

THEMES = {
    "light": {
        "surface": "#fcfcfb", "border": "rgba(11,11,11,0.10)",
        "primary": "#0b0b0b", "secondary": "#52514e", "muted": "#898781",
        "grid": "#e1e0d9", "baseline": "#c3c2b7",
        "without": "#898781", "with": "#2a78d6",
    },
    "dark": {
        "surface": "#1a1a19", "border": "rgba(255,255,255,0.10)",
        "primary": "#ffffff", "secondary": "#c3c2b7", "muted": "#898781",
        "grid": "#2c2c2a", "baseline": "#383835",
        "without": "#898781", "with": "#3987e5",
    },
}

# Layout, in px of the 880-wide canvas.
W = 880
PAD = 28
GUTTER = 40
LABEL_COL = 78   # task names left of the bars
BAR = 12         # bar thickness
GAP = 2          # surface gap between the two bars of a task
PITCH = 36       # top of one task group to the next
RADIUS = 4       # rounded data end; the baseline end stays square
VALUE_PX = 12.5  # bar label size
DOT = "●"        # marks a change that is significant after Holm correction
DOT_PX = 9


def load_analysis(path):
    """Per-task medians, change and Holm p, plus the pooled saving, from analyze.py's output."""
    text = path.read_text()
    cells = {}
    row = re.compile(r"^\| (?P<model>[^|]+?) \| `(?P<task>[\w-]+)` \| [^|]+ \| (?P<b>[\d.]+) → (?P<f>[\d.]+) \| "
                     r"\**(?P<chg>[+-]\d+)%\**[^|]*\| (?P<p>[\d.]+) \|", re.M)
    for m in row.finditer(text):
        cells[(m["model"], m["task"])] = {
            "medians": (m["b"], m["f"]), "change": int(m["chg"]), "p_holm": float(m["p"])}
    pooled = {m["model"]: (int(m["pct"]), m["p"]) for m in re.finditer(
        r"^- (?P<model>.+?): mean time saved per task (?P<pct>\d+)%, p = (?P<p>[\d.]+)", text, re.M)}
    if not cells or not pooled:
        raise SystemExit(f"{path}: no results table found")
    return cells, pooled


def load(name, path, cells, pooled):
    rows = [json.loads(line) for line in path.read_text().splitlines() if line.strip()]

    def arm(task, cond):
        return [r for r in rows if r["task"] == task and r["cond"] == cond]

    tasks = []
    for t in TASKS:
        b, f = arm(t, "baseline"), arm(t, "speed")
        if not b or not f:
            continue
        mb = statistics.median(r["duration_s"] for r in b)
        mf = statistics.median(r["duration_s"] for r in f)
        change = round((mf - mb) / mb * 100)
        cell = cells.get((name, t))
        if cell is None:
            raise SystemExit(f"{name}/{t}: not in {ANALYSIS.name}; run bench/analyze.py first")
        # The chart must show the same numbers as the pre-registered analysis.
        if (f"{mb:.1f}", f"{mf:.1f}") != cell["medians"] or change != cell["change"]:
            raise SystemExit(f"{name}/{t}: medians {mb:.1f} → {mf:.1f} ({change}%) differ from "
                             f"{ANALYSIS.name} {cell['medians']} ({cell['change']}%)")
        tasks.append({"task": t, "before": mb, "after": mf, "change": change,
                      "sig": cell["p_holm"] < 0.05, "n": (len(b), len(f))})
    correct = sum(bool(r["correct"]) for r in rows)
    return {"tasks": tasks, "pooled": pooled[name], "runs": len(rows), "correct": correct,
            "reps": sorted({n for t in tasks for n in t["n"]})}


def minus(n):
    return f"{n}".replace("-", "−")


def bar_path(x0, y, length, h=BAR, r=RADIUS):
    """Horizontal bar from the baseline x0, square there, rounded at the data end."""
    r = min(r, length / 2, h / 2)
    x1 = x0 + length
    return (f"M{x0:.1f},{y:.1f} H{x1 - r:.1f} A{r},{r} 0 0 1 {x1:.1f},{y + r:.1f} "
            f"V{y + h - r:.1f} A{r},{r} 0 0 1 {x1 - r:.1f},{y + h:.1f} H{x0:.1f} Z")


def text_width(s, size, bold=False):
    # Rough advance width of the system sans, used only to keep labels inside the frame.
    return len(s) * size * (0.62 if bold else 0.57)


def label_width(value, change=None):
    w = text_width(f"{value:.1f}", VALUE_PX)
    if change is not None:
        w += 8 + text_width(f"{minus(change)}%", VALUE_PX, bold=True) + 4 + DOT_PX * 0.8
    return w


def render(data, theme):
    c = THEMES[theme]
    panel_w = (W - 2 * PAD - GUTTER) / 2
    plot_w = panel_w - LABEL_COL

    # Largest scale at which every bar and its label stay inside their panel.
    scale = min((plot_w - 6 - label_width(v, chg)) / v
                for d in data.values() for t in d["tasks"]
                for v, chg in ((t["before"], None), (t["after"], t["change"])))
    step = 20
    ticks = list(range(0, int(plot_w / scale) + 1, step))

    n_tasks = max(len(d["tasks"]) for d in data.values())
    head_y = 112
    rows_y = 132
    rows_end = rows_y + (n_tasks - 1) * PITCH + 2 * BAR + GAP
    tick_y = rows_end + 22
    note_y = tick_y + 30
    H = note_y + 22

    out = []
    add = out.append
    total = sum(d["runs"] for d in data.values())
    all_correct = all(d["correct"] == d["runs"] for d in data.values())
    reps = sorted({n for d in data.values() for n in d["reps"]})

    desc = "; ".join(
        f"{name}, {d['pooled'][0]}% less time on average per task: " + ", ".join(
            f"{t['task']} {t['before']:.1f} to {t['after']:.1f} s ({minus(t['change'])}%, "
            f"{'significant' if t['sig'] else 'not significant'})" for t in d["tasks"])
        for name, d in data.items())
    add(f'<svg xmlns="http://www.w3.org/2000/svg" width="{W}" height="{H}" viewBox="0 0 {W} {H}" '
        f'role="img" aria-labelledby="t d">')
    add('<title id="t">Median time per browser task, without and with the chrome-speed plugin</title>')
    add(f'<desc id="d">Median seconds per run, without to with the plugin. {desc}. Significant means '
        f'significant after Holm correction across the 12 per-task tests.</desc>')
    add(f"<style>text{{font-family:{FONT};}} .num{{font-variant-numeric:tabular-nums;}}</style>")
    add(f'<rect x="0.5" y="0.5" width="{W - 1}" height="{H - 1}" rx="12" fill="{c["surface"]}" '
        f'stroke="{c["border"]}"/>')

    # Title and legend share the first line; the subtitle sits under them.
    add(f'<text x="{PAD}" y="44" font-size="18" font-weight="600" fill="{c["primary"]}">'
        f'Median time per browser task, in seconds</text>')
    legend = [("without", "Without plugin"), ("with", "With chrome-speed")]
    lx = W - PAD - sum(18 + text_width(label, 13) + 18 for _, label in legend) + 18
    for key, label in legend:
        add(f'<rect x="{lx:.1f}" y="33" width="12" height="12" rx="2" fill="{c[key]}"/>')
        add(f'<text x="{lx + 18:.1f}" y="44" font-size="13" fill="{c["secondary"]}">{label}</text>')
        lx += 18 + text_width(label, 13) + 18
    per_cell = f"{reps[0]} per task, arm and model" if len(reps) == 1 else "runs per task and arm vary"
    sub = f"{total} headless Claude in Chrome runs ({per_cell}), October 2026. Lower is better."
    if all_correct:
        sub += f" All {total} answers correct."
    add(f'<text x="{PAD}" y="68" font-size="13.5" fill="{c["secondary"]}">{sub}</text>')

    for i, (name, d) in enumerate(data.items()):
        px = PAD + i * (panel_w + GUTTER)
        x0 = px + LABEL_COL
        x_end = px + panel_w

        add(f'<text x="{px}" y="{head_y}" font-size="15" font-weight="600" fill="{c["primary"]}">{name}</text>')
        saved = d["pooled"][0]
        add(f'<text x="{x_end:.1f}" y="{head_y}" font-size="13" text-anchor="end" fill="{c["secondary"]}">'
            f'average per task: <tspan font-weight="600" fill="{c["primary"]}">{saved}% less time</tspan></text>')

        # Hairline grid; the zero line is the baseline the bars grow from.
        for t in ticks:
            x = x0 + t * scale
            color = c["baseline"] if t == 0 else c["grid"]
            add(f'<line x1="{x:.1f}" y1="{rows_y - 8}" x2="{x:.1f}" y2="{rows_end + 6}" '
                f'stroke="{color}" stroke-width="1"/>')
            label = f"{t} s" if t == ticks[-1] else f"{t}"
            add(f'<text class="num" x="{x:.1f}" y="{tick_y}" font-size="12" text-anchor="middle" '
                f'fill="{c["muted"]}">{label}</text>')

        for j, t in enumerate(d["tasks"]):
            gy = rows_y + j * PITCH
            add(f'<text x="{x0 - 10:.1f}" y="{gy + BAR + GAP / 2:.1f}" dy="0.35em" font-size="13" '
                f'text-anchor="end" fill="{c["secondary"]}">{t["task"]}</text>')
            for k, (key, value) in enumerate((("without", t["before"]), ("with", t["after"]))):
                y = gy + k * (BAR + GAP)
                length = value * scale
                add(f'<path d="{bar_path(x0 + 0.5, y, length)}" fill="{c[key]}"/>')
                lx = x0 + length + 6
                label = f'<tspan fill="{c["secondary"]}">{value:.1f}</tspan>'
                if key == "with":
                    change = f"{minus(t['change'])}%"
                    if t["sig"]:
                        label += (f'<tspan dx="8" font-weight="600" fill="{c["primary"]}">{change}</tspan>'
                                  f'<tspan dx="4" font-size="{DOT_PX}" fill="{c["primary"]}">{DOT}</tspan>')
                    else:
                        label += f'<tspan dx="8" fill="{c["secondary"]}">{change}</tspan>'
                width = label_width(value, t["change"] if key == "with" else None)
                assert lx + width <= x_end + 0.5, f"label for {name}/{t['task']} runs off the panel"
                # A surface-coloured halo keeps gridlines from running through the numbers.
                add(f'<text class="num" x="{lx:.1f}" y="{y + BAR / 2:.1f}" dy="0.35em" '
                    f'font-size="{VALUE_PX}" stroke="{c["surface"]}" stroke-width="4" stroke-linejoin="round" '
                    f'paint-order="stroke">{label}</text>')

    # Key for the significance marker.
    add(f'<text x="{PAD}" y="{note_y}" font-size="12.5" fill="{c["secondary"]}">'
        f'<tspan font-size="{DOT_PX}" fill="{c["primary"]}">{DOT}</tspan>'
        f'<tspan dx="6" font-weight="600" fill="{c["primary"]}">Bold with a dot:</tspan> significant after Holm '
        f'correction across the 12 per-task tests. The others are not significant on their own.</text>')

    add("</svg>")
    return "\n".join(out) + "\n"


def main():
    cells, pooled = load_analysis(ANALYSIS)
    data = {name: load(name, path, cells, pooled) for name, path in PANELS}
    DOCS.mkdir(exist_ok=True)
    for theme, filename in (("light", "results.svg"), ("dark", "results-dark.svg")):
        (DOCS / filename).write_text(render(data, theme))
        print(f"wrote docs/{filename}")


if __name__ == "__main__":
    main()
