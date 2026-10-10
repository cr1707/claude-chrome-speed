#!/usr/bin/env python3
"""Draw the README results chart from the benchmark data.

Reads bench/results/runs.jsonl (Sonnet) and bench/results/opus/runs.jsonl (Opus)
and writes docs/results.svg (light) and docs/results-dark.svg (dark). Standard
library only, so it runs anywhere the benchmark does:

  python3 bench/chart.py
"""
import json
import math
import statistics
from pathlib import Path

REPO = Path(__file__).resolve().parent.parent
RESULTS = REPO / "bench" / "results"
DOCS = REPO / "docs"

PANELS = [
    ("Sonnet", RESULTS / "runs.jsonl"),
    ("Opus", RESULTS / "opus" / "runs.jsonl"),
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
LABEL_COL = 52   # task names left of the bars
BAR = 14         # bar thickness
GAP = 2          # surface gap between the two bars of a task
PITCH = 46       # top of one task group to the next
RADIUS = 4       # rounded data end; the baseline end stays square


def load(path):
    rows = [json.loads(line) for line in path.read_text().splitlines() if line.strip()]
    tasks = list(dict.fromkeys(r["task"] for r in rows))

    def med(task, cond):
        return statistics.median(r["duration_s"] for r in rows
                                 if r["cond"] == cond and (task is None or r["task"] == task))

    def ok(cond):
        arm = [r for r in rows if r["cond"] == cond]
        return sum(r["correct"] for r in arm), len(arm)

    reps = len([r for r in rows if r["task"] == tasks[0] and r["cond"] == "baseline"])
    return {
        "tasks": [(t, med(t, "baseline"), med(t, "speed")) for t in tasks],
        "all": (med(None, "baseline"), med(None, "speed")),
        "correct": (ok("baseline"), ok("speed")),
        "reps": reps,
        "runs": len(rows),
    }


def pct(before, after):
    return round((after - before) / before * 100)


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
    return len(s) * size * (0.60 if bold else 0.55)


def render(data, theme):
    c = THEMES[theme]
    vmax = max(v for d in data.values() for _, a, b in d["tasks"] for v in (a, b))
    xmax = math.ceil(vmax / 20) * 20
    ticks = list(range(0, xmax + 1, 20))

    panel_w = (W - 2 * PAD - GUTTER) / 2
    plot_w = panel_w - LABEL_COL
    scale = plot_w / xmax

    n_tasks = max(len(d["tasks"]) for d in data.values())
    head_y = 104
    rows_y = 122
    rows_end = rows_y + (n_tasks - 1) * PITCH + 2 * BAR + GAP
    tick_y = rows_end + 22
    H = tick_y + 22

    out = []
    add = out.append
    total = sum(d["runs"] for d in data.values())
    desc = "; ".join(
        f"{name}: " + ", ".join(f"{t} {a:.1f} to {b:.1f} s" for t, a, b in d["tasks"])
        + f", all runs {d['all'][0]:.1f} to {d['all'][1]:.1f} s"
        for name, d in data.items())
    add(f'<svg xmlns="http://www.w3.org/2000/svg" width="{W}" height="{H}" viewBox="0 0 {W} {H}" '
        f'role="img" aria-labelledby="t d">')
    add('<title id="t">Median time per browser task, without and with the chrome-speed plugin</title>')
    add(f'<desc id="d">Median seconds per run, without to with the plugin. {desc}.</desc>')
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
    ok_all = all(d["correct"][0][0] == d["correct"][0][1] and d["correct"][1][0] == d["correct"][1][1]
                 for d in data.values())
    sub = f"{total} headless Claude in Chrome runs, October 2026. Lower is better."
    if ok_all:
        sub += " Every run in both arms answered correctly."
    add(f'<text x="{PAD}" y="68" font-size="13.5" fill="{c["secondary"]}">{sub}</text>')

    for i, (name, d) in enumerate(data.items()):
        px = PAD + i * (panel_w + GUTTER)
        x0 = px + LABEL_COL
        x_end = px + panel_w

        add(f'<text x="{px}" y="{head_y}" font-size="15" font-weight="600" fill="{c["primary"]}">{name}'
            f'<tspan font-size="12.5" font-weight="400" fill="{c["muted"]}" dx="8">'
            f'{d["reps"]} runs per task and arm</tspan></text>')
        a, b = d["all"]
        add(f'<text x="{x_end:.1f}" y="{head_y}" font-size="13" text-anchor="end" fill="{c["secondary"]}">'
            f'all runs <tspan font-weight="600" fill="{c["primary"]}">{minus(pct(a, b))}%</tspan></text>')

        # Hairline grid; the zero line is the baseline the bars grow from.
        for t in ticks:
            x = x0 + t * scale
            color = c["baseline"] if t == 0 else c["grid"]
            add(f'<line x1="{x:.1f}" y1="{rows_y - 8}" x2="{x:.1f}" y2="{rows_end + 6}" '
                f'stroke="{color}" stroke-width="1"/>')
            label = f"{t} s" if t == ticks[-1] else f"{t}"
            add(f'<text class="num" x="{x:.1f}" y="{tick_y}" font-size="12" text-anchor="middle" '
                f'fill="{c["muted"]}">{label}</text>')

        for j, (task, before, after) in enumerate(d["tasks"]):
            gy = rows_y + j * PITCH
            add(f'<text x="{x0 - 10:.1f}" y="{gy + BAR + GAP / 2:.1f}" dy="0.35em" font-size="13" '
                f'text-anchor="end" fill="{c["secondary"]}">{task}</text>')
            for k, (key, value) in enumerate((("without", before), ("with", after))):
                y = gy + k * (BAR + GAP)
                length = value * scale
                add(f'<path d="{bar_path(x0 + 0.5, y, length)}" fill="{c[key]}"/>')
                label = f'<tspan fill="{c["secondary"]}">{value:.1f}</tspan>'
                width = text_width(f"{value:.1f}", 12.5)
                if key == "with":
                    change = f"{minus(pct(before, value))}%"
                    label += f'<tspan dx="8" font-weight="600" fill="{c["primary"]}">{change}</tspan>'
                    width += 8 + text_width(change, 12.5, bold=True)
                lx = x0 + length + 6
                assert lx + width <= x_end + GUTTER / 2, f"label for {name}/{task} runs off the panel"
                add(f'<text class="num" x="{lx:.1f}" y="{y + BAR / 2:.1f}" dy="0.35em" font-size="12.5">'
                    f'{label}</text>')

    add("</svg>")
    return "\n".join(out) + "\n"


def main():
    data = {name: load(path) for name, path in PANELS}
    DOCS.mkdir(exist_ok=True)
    for theme, filename in (("light", "results.svg"), ("dark", "results-dark.svg")):
        (DOCS / filename).write_text(render(data, theme))
        print(f"wrote docs/{filename}")


if __name__ == "__main__":
    main()
