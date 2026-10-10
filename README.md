# claude-chrome-speed

A Claude Code plugin that makes [Claude in Chrome](https://claude.com/chrome) faster.
It adds a short set of rules at the start of each session: batch browser steps, read pages
as text instead of screenshots, pull paginated data with one script, and click in a way
that doesn't silently miss.

## Results

30 headless runs, October 2026: 3 tasks × 5 runs, with and without the plugin, on Sonnet.
Medians per run:

| Task | Time | Turns | Input tokens | Correct |
|---|---|---|---|---|
| `books`: top 3 from a 2-page category | 47.6 s → **28.5 s** (−40%) | 15 → **6** | −63% | 5/5 → 5/5 |
| `form`: fill 10 fields and submit | 53.1 s → **23.2 s** (−56%) | 20 → **6** | −48% | 5/5 → 5/5 |
| `wiki`: 3-page lookup | 23.6 s → 22.7 s (−4%) | 7 → 7 | −3% | 5/5 → 5/5 |
| **All runs** | 44.8 s → **25.4 s (−43%)** | 15 → **6** | **−51%** | 15/15 → 15/15 |

Same answers, in about half the time and half the tokens. The simple lookup barely moves:
the default is already efficient there. The gains come from multi-page data and forms.
Full tables: [`bench/results/RESULTS.md`](bench/results/RESULTS.md). Per-run data:
[`bench/results/runs.jsonl`](bench/results/runs.jsonl).

## Install

In Claude Code:

```
/plugin marketplace add cr1707/claude-chrome-speed
/plugin install chrome-speed@claude-chrome-speed
```

Or paste [`rules/chrome-speed.md`](rules/chrome-speed.md) into `~/.claude/CLAUDE.md`.
Same effect, no plugin.

The rules are about 400 tokens and load once per session (they're cached after the first
request). Nothing else to configure.

## Stop the permission prompts too

The benchmark runs pre-approved, so it doesn't count the time you spend clicking "Allow".
In daily use that's often the biggest delay. Add the Chrome tools to your
`~/.claude/settings.json`, plus the sites you trust:

```json
{
  "permissions": {
    "allow": [
      "mcp__claude-in-chrome",
      "ClaudeInChromeDomain(example.com)"
    ]
  }
}
```

`mcp__claude-in-chrome` approves the browser tools. Each site still needs its own
`ClaudeInChromeDomain(...)` entry, so Claude can't wander onto new domains without asking.
A copy is in [`settings/permissions.example.json`](settings/permissions.example.json).

## Three things worth knowing about the browser tools

Found while building the benchmark (Claude Code 2.1.281, macOS, Retina display,
October 2026). Each one cost extra turns in the test runs.

1. **A click by `ref` silently misses until the tab has had a screenshot.** The tool reports
   "Clicked on element", but no click event reaches the page. After any screenshot in that
   tab, even one at `scale: 0.1`, the same ref click lands on the element's exact centre.
   The rules add that 0.1-scale screenshot before the first click.
2. **`read_page` with `filter: "interactive"` only returns what's on screen.** Form fields
   and buttons below the fold are left out, so Claude has to scan the page again. Without
   the filter, everything is included.
3. **Clicking a link and reading the page in the same batch can read the old page.** The
   read runs before the next page has loaded. Getting the link's URL and calling `navigate`
   waits for the page to load.

## What the rules change

| Default habit | Rule |
|---|---|
| `tabs_context` → `tabs_create` → `navigate` | `navigate` with no tab ID (it creates the tab itself) |
| Screenshot to read a page | `get_page_text`, or a script that returns JSON |
| Visit page 1, page 2, page 3… | One `javascript_tool` call that fetches and parses all pages |
| One call per form field | One full `read_page`, then every field, the submit and the read in one `browser_batch` |
| Click a link, then read | Get its URL, `navigate`, then read |
| Full-size screenshots | `scale: 0.5`, or `0.1` just to prime clicks |

They change how Claude works, not what it's allowed to do. Permission checks and
confirmations still apply.

## Why a hook and not a skill

The first draft was a skill. Claude loaded it reliably, but loading it is a tool call of its
own, about 6 seconds. On short tasks that cost more than the rules saved: on the Wikipedia
task the two arms did exactly the same browser work, and the skill arm was 6 s slower.
Injecting the rules at session start removes that turn. The draft's runs are kept in
[`bench/results/skill-draft/`](bench/results/skill-draft/).

## How the benchmark works

[`bench/run.py`](bench/run.py) runs each task as a fresh headless session
(`claude -p --chrome`), once without the plugin and once with `--plugin-dir`, and
alternates which goes first on each repetition. Every run starts in an empty temporary
folder with no `CLAUDE.md`, memory or other MCP servers. Answers are checked against
known values, so a fast wrong answer doesn't count as a win.

| Task | What it does | Checked against |
|---|---|---|
| `books` | Finds the 3 most expensive books in a 2-page category on [books.toscrape.com](https://books.toscrape.com) | Titles and prices |
| `form` | Fills and submits a 10-field form ([local page](bench/fixtures/form.html)) | Confirmation code, which is a hash of every field |
| `wiki` | 2018 World Cup winner → its capital → population in the Wikipedia infobox | City and number |

Run it yourself:

```bash
(cd bench/fixtures && python3 -m http.server 8799 --bind 127.0.0.1 &)
python3 bench/run.py --reps 5          # opens tabs in your Chrome
python3 bench/summarize.py
```

It needs Claude Code with the Claude in Chrome extension connected. The runs open tabs in
your browser, and each run counts against your plan like any other session.
[`bench/settings.json`](bench/settings.json) pre-approves only the three test sites.
Each run's full log is written to `bench/results/raw/`. Those logs aren't committed,
because they hold copied page text and local paths. `python3 bench/run.py --regrade`
re-scores saved runs from them.

## Limits

- One model (Sonnet), three tasks, five runs each. Expect the exact percentages to move
  with model, extension version and site.
- Sonnet already batches without help, because the browser tool's own description tells it
  to. Most of the gain comes from the three tool quirks above and from one-script extraction.
- The click quirk was seen on a 2× display. It may not happen everywhere; the 0.1-scale
  screenshot costs almost nothing either way.
- Public test sites can change. If a reference answer drifts, update `bench/tasks.json`.
- Not affiliated with Anthropic.

## License

MIT
