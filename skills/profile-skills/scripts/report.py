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


def fmt_duration(ms):
    """Format a duration in milliseconds as seconds: 340 -> '0.3s', 14300 -> '14.3s'."""
    if not ms:
        return "-"
    return f"{ms / 1000:.1f}s"


def short_model(name):
    """Trim provider/date suffixes so reports stay readable: claude-opus-4-7-20251022 -> opus-4-7."""
    if not name:
        return ""
    n = name
    if n.startswith("claude-"):
        n = n[len("claude-"):]
    # Drop trailing date suffix like -20251022
    parts = n.split("-")
    if parts and parts[-1].isdigit() and len(parts[-1]) >= 6:
        parts = parts[:-1]
    return "-".join(parts)


def flatten_entries(entries):
    """Yield each skill invocation (root or sub) as a flat dict carrying its
    own-segment tokens / duration / model. Lets aggregation code stay agnostic
    to the legacy flat schema vs. the nested one with `sub_skills`.
    """
    for e in entries:
        yield {
            "skill": e.get("skill", ""),
            "ts": e.get("ts", ""),
            "source": e.get("source", ""),
            "model": e.get("model", ""),
            "duration_ms": e.get("duration_ms", 0) or 0,
            "output_tokens": e.get("output_tokens", 0) or 0,
        }
        for sub in e.get("sub_skills") or []:
            yield {
                "skill": sub.get("skill", ""),
                "ts": sub.get("ts", ""),
                "source": sub.get("source", ""),
                "model": sub.get("model", ""),
                "duration_ms": sub.get("duration_ms", 0) or 0,
                "output_tokens": sub.get("output_tokens", 0) or 0,
            }


def aggregate_sub_calls(entries):
    """Return {root_skill: Counter({sub_skill: tokens})} for entries that have
    a `sub_skills` array. Used for the parenthetical breakdown next to a
    parent skill's row."""
    aggr = defaultdict(Counter)
    for e in entries:
        subs = e.get("sub_skills") or []
        if not subs:
            continue
        root = normalize_skill(e.get("skill", ""))
        for sub in subs:
            name = normalize_skill(sub.get("skill", ""))
            aggr[root][name] += sub.get("output_tokens", 0) or 0
    return aggr


def aggregate_per_skill(calls):
    """Compute per-skill token totals, duration totals, and primary model from
    flat call dicts (already non-overlapping own-segment values)."""
    skill_tokens = defaultdict(int)
    skill_duration = defaultdict(int)
    skill_models = defaultdict(Counter)
    for c in calls:
        s = normalize_skill(c["skill"])
        skill_tokens[s] += c.get("output_tokens", 0) or 0
        skill_duration[s] += c.get("duration_ms", 0) or 0
        model = c.get("model", "") or ""
        if model:
            skill_models[s][model] += 1
    primary_model = {
        s: (counter.most_common(1)[0][0] if counter else "")
        for s, counter in skill_models.items()
    }
    return skill_tokens, skill_duration, primary_model


def format_sub_breakdown(sub_counter):
    """Render a Counter({sub: tokens}) as 'subA: 1.2K, subB: 300', sorted by
    descending tokens. Returns '' if empty."""
    if not sub_counter:
        return ""
    parts = [f"{name}: {fmt_tokens(tok)}" for name, tok in sub_counter.most_common()]
    return ", ".join(parts)


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


def build_html(counts, skill_tokens, skill_duration, primary_model,
               skills_by_calls, skills_by_tokens, skills_by_duration,
               skill_info, period, sub_aggr=None):
    sub_aggr = sub_aggr or {}
    labels = {"day": "last 24h", "week": "last 7 days", "month": "last 30 days"}
    period_label = labels.get(period, "all time")

    max_calls = max(counts[s] for s in skills_by_calls) if skills_by_calls else 1
    max_tokens = max(skill_tokens.get(s, 0) for s in skills_by_tokens) if skills_by_tokens else 1
    max_tokens = max_tokens or 1
    max_duration = max(
        (skill_duration.get(s, 0) // counts[s] if counts[s] else 0)
        for s in skills_by_duration
    ) if skills_by_duration else 1
    max_duration = max_duration or 1

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
        breakdown = format_sub_breakdown(sub_aggr.get(skill))
        breakdown_html = f'<span class="bar-subs">({_esc(breakdown)})</span>' if breakdown else ""
        tokens_bars += f"""
        <div class="bar-row">
          <span class="bar-label">{_esc(skill)}</span>
          <div class="bar-track">
            <div class="bar bar-tokens" style="width:{pct:.1f}%"></div>
          </div>
          <span class="bar-value">{fmt_tokens(t)}</span>
          {breakdown_html}
        </div>"""

    # Build duration bars (average per call)
    duration_bars = ""
    for skill in skills_by_duration:
        calls = counts[skill] or 1
        avg = skill_duration.get(skill, 0) // calls
        pct = (avg / max_duration) * 100 if max_duration else 0
        duration_bars += f"""
        <div class="bar-row">
          <span class="bar-label">{_esc(skill)}</span>
          <div class="bar-track">
            <div class="bar bar-duration" style="width:{pct:.1f}%"></div>
          </div>
          <span class="bar-value">{fmt_duration(avg)}</span>
        </div>"""

    # Build skill description rows grouped by plugin.
    # Display label: "skill-name (plugin-name)"; rows are ordered by plugin,
    # then by skill name so that entries sharing a plugin sit together.
    all_skills = set(skills_by_calls) | set(skills_by_tokens) | set(skills_by_duration)

    def _sort_key(skill):
        info = skill_info.get(skill, {}) if isinstance(skill_info, dict) else {}
        plugins = info.get("plugins", []) or []
        primary_plugin = plugins[0] if plugins else "~"  # untracked → bottom
        return (primary_plugin, skill)

    desc_rows = ""
    for skill in sorted(all_skills, key=_sort_key):
        info = skill_info.get(skill, {}) if isinstance(skill_info, dict) else {}
        desc = _esc(info.get("description", ""))
        plugins = info.get("plugins", []) or []
        plugin_label = ", ".join(plugins) if plugins else ""
        label = f"{skill} ({plugin_label})" if plugin_label else skill
        desc_rows += f"""
        <tr>
          <td class="desc-name">{_esc(label)}</td>
          <td class="desc-text">{desc}</td>
        </tr>"""

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
  .bar-duration {{ background: linear-gradient(90deg, #10b981, #34d399); }}
  .bar-value {{ width: 70px; text-align: right; font-size: 0.85rem; padding-left: 8px; color: #aaa; }}
  .bar-subs {{ padding-left: 10px; font-size: 0.75rem; color: #7a7a8a; white-space: nowrap; }}

  /* Skill descriptions */
  .desc-table {{ width: 100%; border-collapse: collapse; margin-top: 1rem; }}
  .desc-table td {{ padding: 0.5rem 0.75rem; border-bottom: 1px solid #2a2a3e; vertical-align: top; }}
  .desc-name {{ width: 280px; font-weight: 600; color: #63b3ed; font-size: 0.85rem; white-space: nowrap; }}
  .desc-text {{ color: #aaa; font-size: 0.8rem; line-height: 1.4; }}
</style>
</head>
<body>
  <h1>Skill Usage Report</h1>
  <div class="subtitle">{period_label}</div>

  <h2>Skill Usage (Calls)</h2>
  {calls_bars}

  <h2>Skill Usage (Tokens)</h2>
  {tokens_bars}

  <h2>Skill Usage (Avg Duration)</h2>
  {duration_bars}

  <h2>Skill Descriptions</h2>
  <table class="desc-table">
    {desc_rows}
  </table>
</body>
</html>"""
    return html


def _collect_skill_info():
    """Build {short_name: {description, plugins}} map from installed skills.

    A short name can exist in multiple plugins (e.g. duplicated across
    personal + plugin installs), so plugins is a list.
    """
    script_dir = Path(__file__).resolve().parent
    collect_script = script_dir / "../../list-skills/scripts/collect_skills.py"
    if not collect_script.exists():
        return {}
    import importlib.util
    spec = importlib.util.spec_from_file_location("collect_skills", collect_script)
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    info = {}
    for e in mod.collect():
        name = e["name"]
        plugin = e.get("plugin", "")
        slot = info.setdefault(name, {"description": e.get("description", ""), "plugins": []})
        if plugin and plugin not in slot["plugins"]:
            slot["plugins"].append(plugin)
        if not slot["description"]:
            slot["description"] = e.get("description", "")
    return info


def detail_report(period=None, top=None):
    entries = load_entries(period)
    if not entries:
        print("No skill usage data found.")
        return

    calls = list(flatten_entries(entries))
    counts = Counter(normalize_skill(c["skill"]) for c in calls)
    skill_tokens, skill_duration, primary_model = aggregate_per_skill(calls)
    sub_aggr = aggregate_sub_calls(entries)

    skills_by_calls = sorted(counts.keys(), key=lambda s: -counts[s])
    skills_by_tokens = sorted(counts.keys(), key=lambda s: -skill_tokens.get(s, 0))
    skills_by_duration = sorted(
        counts.keys(),
        key=lambda s: -(skill_duration.get(s, 0) // counts[s] if counts[s] else 0),
    )
    if top:
        skills_by_calls = skills_by_calls[:top]
        skills_by_tokens = skills_by_tokens[:top]
        skills_by_duration = skills_by_duration[:top]

    skill_info = _collect_skill_info()

    html = build_html(counts, skill_tokens, skill_duration, primary_model,
                      skills_by_calls, skills_by_tokens, skills_by_duration,
                      skill_info, period, sub_aggr)
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

    calls = list(flatten_entries(entries))
    counts = Counter(normalize_skill(c["skill"]) for c in calls)
    total_calls = sum(counts.values())

    skill_tokens, skill_duration, primary_model = aggregate_per_skill(calls)
    sub_aggr = aggregate_sub_calls(entries)

    # Sort by tokens desc; skills with no tokens go to the bottom
    skills_sorted = sorted(
        counts.keys(),
        key=lambda s: (skill_tokens.get(s, 0) == 0, -skill_tokens.get(s, 0)),
    )
    if top:
        skills_sorted = skills_sorted[:top]

    total_tokens = sum(skill_tokens.values())
    total_duration = sum(skill_duration.values())

    # Period label
    labels = {"day": "last 24h", "week": "last 7 days", "month": "last 30 days"}
    period_label = labels.get(period, "all time")

    # Dynamic skill column width based on longest name
    SKILL_W = max(len(s) for s in skills_sorted) if skills_sorted else 5
    SKILL_W = max(SKILL_W, 5)  # minimum width for "Skill" header

    models_shown = [short_model(primary_model.get(s, "")) for s in skills_sorted]
    MODEL_W = max((len(m) for m in models_shown if m), default=5)
    MODEL_W = max(MODEL_W, 5)  # minimum width for "Model" header

    print()
    print(f"  Skill Usage Report ({period_label})")
    print()
    header = (
        f"  {'#':>2}  {'Skill':<{SKILL_W}}  {'Tokens':>7}  "
        f"{'Calls':>5}  {'AvgTime':>7}  {'Model':<{MODEL_W}}"
    )
    print(header)
    for rank, skill in enumerate(skills_sorted, 1):
        tok = skill_tokens.get(skill, 0)
        tok_str = fmt_tokens(tok) if tok else "-"
        avg_dur = skill_duration.get(skill, 0) // counts[skill] if counts[skill] else 0
        dur_str = fmt_duration(avg_dur)
        model_str = short_model(primary_model.get(skill, "")) or "-"
        breakdown = format_sub_breakdown(sub_aggr.get(skill))
        breakdown_str = f"  ({breakdown})" if breakdown else ""
        print(
            f"  {rank:>2}  {skill:<{SKILL_W}}  {tok_str:>7}  "
            f"{counts[skill]:>5}  {dur_str:>7}  {model_str:<{MODEL_W}}{breakdown_str}"
        )

    print()
    summary = (
        f"  Total: {fmt_tokens(total_tokens)} tokens | {total_calls} calls | "
        f"{len(counts)} skills | {fmt_duration(total_duration)} runtime"
    )
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
