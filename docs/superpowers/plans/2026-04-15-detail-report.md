# `--detail` HTML Visualization Report Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Add `--detail` flag to `report.py` that generates and serves an HTML report with three CSS-based visualizations (calls bar chart, tokens bar chart, session×skill heatmap).

**Architecture:** Extend existing `report.py` with a `detail_report()` function that reuses `load_entries()` and `normalize_skill()` to aggregate data, generates a self-contained HTML string (inline CSS/JS, no CDN), writes it to `/tmp/skill-report.html`, and serves it on localhost via Python's `http.server` with auto browser open.

**Tech Stack:** Python 3 stdlib only (`http.server`, `webbrowser`, `json`, `collections`). Pure CSS bar charts and grid heatmap.

---

### Task 1: Add `--detail` argument and `detail_report()` skeleton

**Files:**
- Modify: `skills/profile-skills/scripts/report.py:132-147` (main/argparse section)

- [ ] **Step 1: Add `--detail` flag to argparse and routing**

In `main()`, add the `--detail` argument and route to `detail_report()`:

```python
parser.add_argument("--detail", "-d", action="store_true", help="Open HTML report in browser")
```

Update the bottom of `main()`:

```python
if args.detail:
    detail_report(period=period, top=args.top)
else:
    report(period=period, top=args.top)
```

- [ ] **Step 2: Add `detail_report()` stub**

Add above `main()`:

```python
def detail_report(period=None, top=None):
    entries = load_entries(period)
    if not entries:
        print("No skill usage data found.")
        return

    # Aggregate
    counts = Counter(normalize_skill(e["skill"]) for e in entries)
    skill_tokens = defaultdict(int)
    for e in entries:
        tokens = e.get("output_tokens", 0)
        if tokens:
            skill_tokens[normalize_skill(e["skill"])] += tokens

    skills_by_calls = sorted(counts.keys(), key=lambda s: -counts[s])
    skills_by_tokens = sorted(counts.keys(), key=lambda s: -skill_tokens.get(s, 0))
    if top:
        skills_by_calls = skills_by_calls[:top]
        skills_by_tokens = skills_by_tokens[:top]

    # Session matrix: {session_id: {skill: count}}
    session_skills = defaultdict(lambda: defaultdict(int))
    session_times = {}
    for e in entries:
        sid = e["session"][:8]
        skill = normalize_skill(e["skill"])
        session_skills[sid][skill] += 1
        if sid not in session_times:
            session_times[sid] = e.get("ts", "")

    sessions_sorted = sorted(session_times.keys(), key=lambda s: session_times[s])
    all_skills_in_heatmap = sorted(set(
        skill for row in session_skills.values() for skill in row
    ))

    html = build_html(counts, skill_tokens, skills_by_calls, skills_by_tokens,
                      session_skills, sessions_sorted, all_skills_in_heatmap,
                      session_times, period)
    serve_html(html)
```

- [ ] **Step 3: Commit**

```bash
git add skills/profile-skills/scripts/report.py
git commit -m "feat: add --detail flag and detail_report skeleton"
```

---

### Task 2: Implement `build_html()` — HTML generation

**Files:**
- Modify: `skills/profile-skills/scripts/report.py` (add `build_html()` function)

- [ ] **Step 1: Add `build_html()` function**

Add this function above `detail_report()`. It returns a complete HTML string with inline CSS and data.

```python
def build_html(counts, skill_tokens, skills_by_calls, skills_by_tokens,
               session_skills, sessions_sorted, all_skills_in_heatmap,
               session_times, period):
    labels = {"day": "last 24h", "week": "last 7 days", "month": "last 30 days"}
    period_label = labels.get(period, "all time")

    max_calls = max(counts.values()) if counts else 1
    max_tokens = max(skill_tokens.values()) if skill_tokens else 1

    # Build bar chart rows for calls
    calls_bars = ""
    for skill in skills_by_calls:
        c = counts[skill]
        pct = c / max_calls * 100
        calls_bars += f"""
        <div class="bar-row">
          <span class="bar-label">{skill}</span>
          <div class="bar-track">
            <div class="bar-fill calls-fill" style="width:{pct}%"></div>
          </div>
          <span class="bar-value">{c}</span>
        </div>"""

    # Build bar chart rows for tokens
    tokens_bars = ""
    for skill in skills_by_tokens:
        t = skill_tokens.get(skill, 0)
        pct = t / max_tokens * 100 if max_tokens else 0
        tokens_bars += f"""
        <div class="bar-row">
          <span class="bar-label">{skill}</span>
          <div class="bar-track">
            <div class="bar-fill tokens-fill" style="width:{pct}%"></div>
          </div>
          <span class="bar-value">{fmt_tokens(t)}</span>
        </div>"""

    # Build heatmap
    max_heat = max(
        (session_skills[s].get(sk, 0) for s in sessions_sorted for sk in all_skills_in_heatmap),
        default=1
    ) or 1

    heatmap_header = "".join(
        f'<div class="hm-header">{sk}</div>' for sk in all_skills_in_heatmap
    )

    heatmap_rows = ""
    for sid in sessions_sorted:
        ts = session_times.get(sid, "")[:10]
        row_label = f"{sid} ({ts})"
        cells = ""
        for sk in all_skills_in_heatmap:
            v = session_skills[sid].get(sk, 0)
            opacity = v / max_heat if v else 0
            title = f"{sk}: {v} calls"
            cells += f'<div class="hm-cell" style="background:rgba(99,179,237,{opacity})" title="{title}">{v if v else ""}</div>'
        heatmap_rows += f"""
        <div class="hm-row-label">{row_label}</div>
        {cells}"""

    n_skills = len(all_skills_in_heatmap)
    grid_cols = f"140px repeat({n_skills}, 1fr)"

    total_calls = sum(counts.values())
    total_tokens = sum(skill_tokens.values())

    return f"""<!DOCTYPE html>
<html lang="en">
<head>
<meta charset="UTF-8">
<meta name="viewport" content="width=device-width, initial-scale=1.0">
<title>Skill Usage Report</title>
<style>
  * {{ margin: 0; padding: 0; box-sizing: border-box; }}
  body {{
    background: #1a1a2e; color: #e0e0e0;
    font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', monospace;
    padding: 2rem; line-height: 1.6;
  }}
  h1 {{ color: #63b3ed; margin-bottom: 0.5rem; font-size: 1.5rem; }}
  .subtitle {{ color: #888; margin-bottom: 2rem; font-size: 0.9rem; }}
  .section {{ background: #16213e; border-radius: 12px; padding: 1.5rem; margin-bottom: 2rem; }}
  h2 {{ color: #a0aec0; font-size: 1.1rem; margin-bottom: 1rem; }}
  .bar-row {{ display: flex; align-items: center; margin-bottom: 0.5rem; gap: 0.75rem; }}
  .bar-label {{ width: 220px; text-align: right; font-size: 0.85rem; white-space: nowrap; overflow: hidden; text-overflow: ellipsis; flex-shrink: 0; }}
  .bar-track {{ flex: 1; background: #0f3460; border-radius: 4px; height: 22px; overflow: hidden; }}
  .bar-fill {{ height: 100%; border-radius: 4px; transition: width 0.6s ease; min-width: 2px; }}
  .calls-fill {{ background: linear-gradient(90deg, #4a90d9, #63b3ed); }}
  .tokens-fill {{ background: linear-gradient(90deg, #d97706, #f59e0b); }}
  .bar-value {{ width: 60px; font-size: 0.85rem; color: #a0aec0; text-align: right; flex-shrink: 0; }}
  .heatmap {{ display: grid; grid-template-columns: {grid_cols}; gap: 2px; font-size: 0.75rem; }}
  .hm-header {{ background: #0f3460; padding: 6px 4px; text-align: center; font-weight: 600; color: #a0aec0;
    writing-mode: vertical-rl; text-orientation: mixed; min-height: 80px; border-radius: 4px;
    white-space: nowrap; overflow: hidden; text-overflow: ellipsis; }}
  .hm-row-label {{ background: #0f3460; padding: 6px; font-size: 0.7rem; color: #a0aec0; display: flex; align-items: center;
    border-radius: 4px; white-space: nowrap; overflow: hidden; text-overflow: ellipsis; }}
  .hm-cell {{ display: flex; align-items: center; justify-content: center; padding: 6px;
    border-radius: 4px; min-height: 32px; color: #e0e0e0; font-weight: 500; cursor: default; }}
  .summary {{ color: #888; font-size: 0.85rem; margin-top: 1rem; text-align: center; }}
</style>
</head>
<body>
  <h1>Skill Usage Report</h1>
  <div class="subtitle">{period_label} &middot; {total_calls} calls &middot; {fmt_tokens(total_tokens)} tokens &middot; {len(counts)} skills</div>

  <div class="section">
    <h2>Skill Usage (Calls)</h2>
    {calls_bars}
  </div>

  <div class="section">
    <h2>Skill Usage (Tokens)</h2>
    {tokens_bars}
  </div>

  <div class="section">
    <h2>Session &times; Skill Heatmap</h2>
    <div class="heatmap">
      <div class="hm-header" style="background:none"></div>
      {heatmap_header}
      {heatmap_rows}
    </div>
  </div>

  <div class="summary">Generated {datetime.now().strftime("%Y-%m-%d %H:%M")}</div>
</body>
</html>"""
```

- [ ] **Step 2: Commit**

```bash
git add skills/profile-skills/scripts/report.py
git commit -m "feat: implement build_html for detail report"
```

---

### Task 3: Implement `serve_html()` — server + browser open

**Files:**
- Modify: `skills/profile-skills/scripts/report.py` (add imports and `serve_html()`)

- [ ] **Step 1: Add imports at top of file**

Add to the existing imports:

```python
import webbrowser
import tempfile
from http.server import HTTPServer, SimpleHTTPRequestHandler
from pathlib import Path
```

- [ ] **Step 2: Add `serve_html()` function**

Add above `detail_report()`:

```python
def serve_html(html):
    out = Path(tempfile.gettempdir()) / "skill-report.html"
    out.write_text(html, encoding="utf-8")

    port = 8765

    class Handler(SimpleHTTPRequestHandler):
        def do_GET(self):
            self.send_response(200)
            self.send_header("Content-Type", "text/html; charset=utf-8")
            self.end_headers()
            self.wfile.write(out.read_bytes())

        def log_message(self, format, *args):
            pass  # suppress request logs

    server = HTTPServer(("127.0.0.1", port), Handler)
    url = f"http://127.0.0.1:{port}"
    print(f"\n  Detail report: {url}")
    print(f"  Press Ctrl+C to stop.\n")
    webbrowser.open(url)
    try:
        server.serve_forever()
    except KeyboardInterrupt:
        print("\n  Server stopped.")
    finally:
        server.server_close()
```

- [ ] **Step 3: Commit**

```bash
git add skills/profile-skills/scripts/report.py
git commit -m "feat: add serve_html with http.server and browser auto-open"
```

---

### Task 4: Update SKILL.md

**Files:**
- Modify: `skills/profile-skills/SKILL.md`

- [ ] **Step 1: Add `--detail` documentation**

In the Options section after `--top N`, add:

```
- `--detail` — Open an HTML visualization report in the browser (bar charts + heatmap)
```

Add a new example:

```
- Visual report: `python3 "${CLAUDE_PLUGIN_ROOT}/skills/profile-skills/scripts/report.py" --detail`
- Visual report (this week): `python3 "${CLAUDE_PLUGIN_ROOT}/skills/profile-skills/scripts/report.py" --detail --period week`
```

Add an output rule:

```
When `--detail` is used, the script opens a browser automatically. Print the URL from script output and tell the user to press Ctrl+C when done.
```

- [ ] **Step 2: Commit**

```bash
git add skills/profile-skills/SKILL.md
git commit -m "docs: add --detail option to SKILL.md"
```

---

### Task 5: Manual browser test

- [ ] **Step 1: Run `--detail` and verify in browser**

```bash
python3 skills/profile-skills/scripts/report.py --detail
```

Verify:
1. Browser opens automatically to `http://127.0.0.1:8765`
2. Three sections render: Calls bar chart, Tokens bar chart, Heatmap
3. Bar widths are proportional to values
4. Heatmap cells show correct intensity and tooltip on hover
5. Dark theme renders correctly
6. Ctrl+C stops the server cleanly

- [ ] **Step 2: Test with `--period` and `--top` flags combined**

```bash
python3 skills/profile-skills/scripts/report.py --detail --period week --top 5
```

Verify filters apply correctly to all three charts.
