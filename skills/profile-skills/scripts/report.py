#!/usr/bin/env python3
"""Skill usage report generator — reads JSONL only, no transcript parsing."""
import html as _html
import json
import os
import argparse
import webbrowser
import tempfile
from collections import Counter, defaultdict
from datetime import datetime, timedelta, timezone
from http.server import HTTPServer, SimpleHTTPRequestHandler
from pathlib import Path

LOG_FILE = os.path.expanduser("~/.claude/skill-usage.jsonl")


def load_entries(period=None):
    if not os.path.exists(LOG_FILE):
        return []

    entries = []
    now = datetime.now(timezone.utc)
    cutoff = None

    if period == "day":
        cutoff = now - timedelta(days=1)
    elif period == "week":
        cutoff = now - timedelta(weeks=1)
    elif period == "month":
        cutoff = now - timedelta(days=30)

    with open(LOG_FILE) as f:
        for line in f:
            line = line.strip()
            if not line:
                continue
            try:
                entry = json.loads(line)
                if cutoff:
                    ts = datetime.fromisoformat(entry["ts"].replace("Z", "+00:00"))
                    if ts < cutoff:
                        continue
                entries.append(entry)
            except (json.JSONDecodeError, KeyError, ValueError):
                continue

    return entries


def normalize_skill(name):
    """Merge qualified and short skill names: 'plugin:skill' -> 'skill'."""
    return name.split(":", 1)[1] if ":" in name else name


def _esc(s):
    """HTML-escape a string for safe interpolation into HTML."""
    return _html.escape(str(s))


def fmt_tokens(n):
    """Format token count: 1234 -> '1.2K', 12345 -> '12.3K', 123 -> '123'."""
    if n >= 1_000_000:
        return f"{n / 1_000_000:.1f}M"
    if n >= 1_000:
        return f"{n / 1_000:.1f}K"
    return str(n)


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
            pass

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


def build_html(counts, skill_tokens, skills_by_calls, skills_by_tokens,
               session_skills, sessions_sorted, all_skills_in_heatmap,
               session_times, period):
    labels = {"day": "last 24h", "week": "last 7 days", "month": "last 30 days"}
    period_label = labels.get(period, "all time")

    max_calls = max(counts[s] for s in skills_by_calls) if skills_by_calls else 1
    max_tokens = max(skill_tokens.get(s, 0) for s in skills_by_tokens) if skills_by_tokens else 1
    max_tokens = max_tokens or 1

    # Build calls bars HTML
    calls_bars = ""
    for skill in skills_by_calls:
        c = counts[skill]
        pct = (c / max_calls) * 100
        calls_bars += f"""
        <div class="bar-row">
          <span class="bar-label">{_esc(skill)}</span>
          <div class="bar-track">
            <div class="bar bar-calls" style="width:{pct:.1f}%"></div>
          </div>
          <span class="bar-value">{c}</span>
        </div>"""

    # Build tokens bars HTML
    tokens_bars = ""
    for skill in skills_by_tokens:
        t = skill_tokens.get(skill, 0)
        pct = (t / max_tokens) * 100
        tokens_bars += f"""
        <div class="bar-row">
          <span class="bar-label">{_esc(skill)}</span>
          <div class="bar-track">
            <div class="bar bar-tokens" style="width:{pct:.1f}%"></div>
          </div>
          <span class="bar-value">{fmt_tokens(t)}</span>
        </div>"""

    # Build heatmap
    max_heat = 0
    for sid in sessions_sorted:
        for skill in all_skills_in_heatmap:
            v = session_skills[sid].get(skill, 0)
            if v > max_heat:
                max_heat = v
    max_heat = max_heat or 1

    skill_headers = "".join(
        f'<div class="hm-header" title="{_esc(s)}">{_esc(s)}</div>' for s in all_skills_in_heatmap
    )

    heatmap_rows = ""
    for sid in sessions_sorted:
        ts_raw = session_times.get(sid, "")
        date_str = ts_raw[:10] if len(ts_raw) >= 10 else ""
        label = f"{sid} {date_str}" if date_str else sid
        cells = ""
        for skill in all_skills_in_heatmap:
            v = session_skills[sid].get(skill, 0)
            opacity = (v / max_heat) * 0.9 + 0.1 if v > 0 else 0
            title = f"{_esc(skill)}: {v} calls"
            cells += f'<div class="hm-cell" style="background:rgba(99,179,237,{opacity:.2f})" title="{title}">{v if v else ""}</div>'
        heatmap_rows += f"""
        <div class="hm-row-label">{label}</div>{cells}"""

    num_skills = len(all_skills_in_heatmap)
    grid_cols = f"120px repeat({num_skills}, minmax(50px, 1fr))"

    html = f"""<!DOCTYPE html>
<html lang="en">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>Skill Usage Report ({period_label})</title>
<style>
  * {{ margin: 0; padding: 0; box-sizing: border-box; }}
  body {{
    background: #1a1a2e; color: #e0e0e0;
    font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, monospace;
    padding: 2rem;
  }}
  h1 {{ font-size: 1.5rem; margin-bottom: 0.5rem; color: #fff; }}
  h2 {{ font-size: 1.15rem; margin: 2rem 0 1rem; color: #ccc; border-bottom: 1px solid #333; padding-bottom: 0.4rem; }}
  .subtitle {{ color: #888; margin-bottom: 2rem; font-size: 0.9rem; }}

  /* Bar charts */
  .bar-row {{ display: flex; align-items: center; margin-bottom: 0.35rem; }}
  .bar-label {{ width: 180px; text-align: right; padding-right: 12px; font-size: 0.85rem; white-space: nowrap; overflow: hidden; text-overflow: ellipsis; }}
  .bar-track {{ flex: 1; background: #2a2a3e; border-radius: 4px; height: 20px; overflow: hidden; }}
  .bar {{ height: 100%; border-radius: 4px; transition: width 0.3s; }}
  .bar-calls {{ background: linear-gradient(90deg, #3b82f6, #60a5fa); }}
  .bar-tokens {{ background: linear-gradient(90deg, #f59e0b, #fbbf24); }}
  .bar-value {{ width: 70px; text-align: right; font-size: 0.85rem; padding-left: 8px; color: #aaa; }}

  /* Heatmap */
  .heatmap {{ display: grid; grid-template-columns: {grid_cols}; gap: 2px; margin-top: 1rem; overflow-x: auto; }}
  .hm-header {{ font-size: 0.7rem; text-align: center; color: #888; writing-mode: vertical-rl; transform: rotate(180deg); height: 90px; overflow: hidden; text-overflow: ellipsis; display: flex; align-items: center; justify-content: center; }}
  .hm-row-label {{ font-size: 0.75rem; color: #aaa; display: flex; align-items: center; white-space: nowrap; overflow: hidden; text-overflow: ellipsis; }}
  .hm-cell {{ display: flex; align-items: center; justify-content: center; font-size: 0.7rem; color: rgba(255,255,255,0.7); border-radius: 3px; min-height: 24px; }}
</style>
</head>
<body>
  <h1>Skill Usage Report</h1>
  <div class="subtitle">{period_label}</div>

  <h2>Skill Usage (Calls)</h2>
  {calls_bars}

  <h2>Skill Usage (Tokens)</h2>
  {tokens_bars}

  <h2>Session &times; Skill Heatmap</h2>
  <div class="heatmap">
    <div class="hm-corner"></div>
    {skill_headers}
    {heatmap_rows}
  </div>
</body>
</html>"""
    return html


def detail_report(period=None, top=None):
    entries = load_entries(period)
    if not entries:
        print("No skill usage data found.")
        return

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


def report(period=None, top=None):
    entries = load_entries(period)

    if not entries:
        print()
        print("  No skill usage data found.")
        if not os.path.exists(LOG_FILE):
            print("  Log file not found: ~/.claude/skill-usage.jsonl")
            print("  Make sure the tracking hooks are configured.")
        else:
            label = period or "all"
            print(f"  No entries for period: {label}")
        print()
        return

    counts = Counter(normalize_skill(e["skill"]) for e in entries)
    total_calls = sum(counts.values())

    # Aggregate tokens per skill
    skill_tokens = defaultdict(int)
    for e in entries:
        tokens = e.get("output_tokens", 0)
        if tokens:
            skill_tokens[normalize_skill(e["skill"])] += tokens

    # Sort by tokens desc; skills with no tokens go to the bottom
    skills_sorted = sorted(
        counts.keys(),
        key=lambda s: (skill_tokens.get(s, 0) == 0, -skill_tokens.get(s, 0)),
    )
    if top:
        skills_sorted = skills_sorted[:top]

    total_tokens = sum(skill_tokens.values())

    # Period label
    labels = {"day": "last 24h", "week": "last 7 days", "month": "last 30 days"}
    period_label = labels.get(period, "all time")

    # Dynamic skill column width based on longest name
    SKILL_W = max(len(s) for s in skills_sorted) if skills_sorted else 5
    SKILL_W = max(SKILL_W, 5)  # minimum width for "Skill" header
    print()
    print(f"  Skill Usage Report ({period_label})")
    print()
    print(f"  {'#':>2}  {'Skill':<{SKILL_W}}  {'Tokens':>7}  {'Calls':>5}")
    for rank, skill in enumerate(skills_sorted, 1):
        tok = skill_tokens.get(skill, 0)
        tok_str = fmt_tokens(tok) if tok else "-"
        print(f"  {rank:>2}  {skill:<{SKILL_W}}  {tok_str:>7}  {counts[skill]:>5}")

    print()
    summary = f"  Total: {fmt_tokens(total_tokens)} tokens | {total_calls} calls | {len(counts)} skills"
    print(summary)

    if top and len(counts) > top:
        print(f"  (showing top {top} of {len(counts)})")

    # Date range
    timestamps = []
    for e in entries:
        try:
            ts = datetime.fromisoformat(e["ts"].replace("Z", "+00:00"))
            timestamps.append(ts)
        except (KeyError, ValueError):
            pass

    if timestamps:
        earliest = min(timestamps).strftime("%Y-%m-%d")
        latest = max(timestamps).strftime("%Y-%m-%d")
        if earliest == latest:
            print(f"  Period: {earliest}")
        else:
            print(f"  Period: {earliest} ~ {latest}")

    print()


def main():
    parser = argparse.ArgumentParser(description="Skill usage report")
    parser.add_argument(
        "--period", "-p",
        choices=["day", "week", "month", "all"],
        default=None,
    )
    parser.add_argument("--top", "-t", type=int, default=None)
    parser.add_argument("--detail", "-d", action="store_true", help="Open HTML report in browser")
    args = parser.parse_args()

    period = args.period if args.period != "all" else None
    if args.detail:
        detail_report(period=period, top=args.top)
    else:
        report(period=period, top=args.top)


if __name__ == "__main__":
    main()
