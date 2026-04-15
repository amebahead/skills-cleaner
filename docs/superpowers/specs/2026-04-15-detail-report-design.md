# Design: `--detail` HTML Visualization Report

## Overview

Add `--detail` flag to `report.py` that generates an interactive HTML report with three visualizations and serves it on localhost via Python's built-in HTTP server.

## Flow

1. `report.py --detail` executed (combinable with `--period`, `--top`)
2. Load and normalize JSONL data via existing `load_entries()` + `normalize_skill()`
3. Aggregate data for three chart types
4. Generate self-contained HTML string (inline CSS/JS, no external dependencies)
5. Write to `/tmp/skill-report.html`
6. Serve on `localhost:8765` via `http.server` + auto-open browser with `webbrowser.open()`
7. Print URL to terminal, Ctrl+C to stop

## Visualizations

### 1. Skill Usage (Calls) — Horizontal Bar Chart
- CSS `div`-based horizontal bars
- Sorted by call count descending
- Each bar labeled with skill name and count

### 2. Skill Usage (Tokens) — Horizontal Bar Chart
- CSS `div`-based horizontal bars
- Sorted by token sum descending
- Each bar labeled with skill name and formatted token count

### 3. Session x Skill Heatmap
- CSS Grid table
- X-axis: skills, Y-axis: sessions (chronological order)
- Cell color intensity represents call count
- Session displayed as truncated ID + timestamp

## Style

- Dark theme (background `#1a1a2e`, text `#e0e0e0`)
- Bar chart colors: gradient palette
- Heatmap: transparent to accent color intensity scale
- Responsive layout

## Files Changed

- `skills/profile-skills/scripts/report.py` — add `--detail` flag and HTML generation logic
- `skills/profile-skills/SKILL.md` — document `--detail` option
