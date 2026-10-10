# Claude in Chrome: fast path

Each browser tool call costs a full model turn. Cut turns, not keystrokes. These rules change speed only; permissions and confirmations still apply.

- Load tools once: if the mcp__claude-in-chrome__* tools are deferred, fetch every one you will need in a single ToolSearch (navigate, browser_batch, get_page_text, find, read_page, form_input, javascript_tool, computer, tabs_close_mcp).
- Start with `navigate` + url and no tabId. It creates the tab group itself; skip tabs_context_mcp and tabs_create_mcp.
- Follow links by URL: get the href (from find, read_page or JS) and `navigate` to it. Do not click a link and read in the same batch; the read can run before the next page loads.
- Read text, not pixels: `get_page_text` for what a page says; one `javascript_tool` call returning JSON for tables, lists and specific values. Screenshot only for visual questions, with `scale: 0.5`.
- Paginated data: one `javascript_tool` call that `await fetch()`es every same-origin page and parses it with DOMParser. Do not visit pages one by one.
- Clicks: click by `ref`, not by coordinates. But a ref click silently misses if the tab has had no screenshot yet, so put one `computer` screenshot with `scale: 0.1` (almost free) before the first click in each tab, in the same batch.
- Forms: one `read_page` with NO filter (`filter: "interactive"` only returns on-screen elements and misses fields below the fold). Then ONE `browser_batch`: every `form_input`, the 0.1-scale screenshot, the submit click by `ref`, and `get_page_text` to read the result. Do not re-read or screenshot to check fields first; the result page is the check. Read results with `get_page_text`, since `read_page` can drop inline text.
- Change pages through `form_input` and clicks, not JS; they fire the events frameworks listen for. Keep JS read-only.
- Put `tabs_close_mcp` in the same batch as your final read.
- If an API, MCP connector or CLI covers the task, use it instead of the browser.
