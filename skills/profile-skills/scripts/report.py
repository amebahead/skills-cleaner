#!/usr/bin/env python3
"""Skill usage report generator — reads JSONL only, no transcript parsing."""
import json
import os
import argparse
from collections import Counter, defaultdict
from datetime import datetime, timedelta, timezone

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


def fmt_tokens(n):
    """Format token count: 1234 -> '1.2K', 12345 -> '12.3K', 123 -> '123'."""
    if n >= 1_000_000:
        return f"{n / 1_000_000:.1f}M"
    if n >= 1_000:
        return f"{n / 1_000:.1f}K"
    return str(n)


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

    counts = Counter(e["skill"] for e in entries)
    total = sum(counts.values())
    items = counts.most_common(top)

    # Aggregate tokens per skill from JSONL entries
    skill_tokens = defaultdict(int)
    for e in entries:
        tokens = e.get("output_tokens", 0)
        if tokens:
            skill_tokens[e["skill"]] += tokens

    has_tokens = bool(skill_tokens)

    # Column sizing
    max_name = max(len(name) for name, _ in items)
    col = max(max_name, 12)
    max_count_len = max(len(str(c)) for _, c in items)
    cw = max(max_count_len, 5)

    if has_tokens:
        tw = 8
        line_w = col + cw + tw + 8
    else:
        tw = 0
        line_w = col + cw + 5

    # Period label
    labels = {"day": "last 24h", "week": "last 7 days", "month": "last 30 days"}
    period_label = labels.get(period, "all time")

    print()
    print(f"  Skill Usage ({period_label})")
    print(f"  {'=' * line_w}")

    if has_tokens:
        print(f"  {'Skill':<{col}}  {'Count':>{cw}}  {'Tokens':>{tw}}")
        print(f"  {'-' * col}  {'-' * cw}  {'-' * tw}")
    else:
        print(f"  {'Skill':<{col}}  {'Count':>{cw}}")
        print(f"  {'-' * col}  {'-' * cw}")

    total_tokens = 0
    for skill, count in items:
        tok = skill_tokens.get(skill, 0)
        total_tokens += tok
        if has_tokens:
            tok_str = fmt_tokens(tok) if tok else "-"
            print(f"  {skill:<{col}}  {count:>{cw}}  {tok_str:>{tw}}")
        else:
            print(f"  {skill:<{col}}  {count:>{cw}}")

    print(f"  {'=' * line_w}")
    summary = f"  Total: {total} triggers | {len(counts)} unique skills"
    if has_tokens and total_tokens:
        summary += f" | {fmt_tokens(total_tokens)} output tokens"
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
            print(f"  Period: {earliest} -> {latest}")

    print()


def main():
    parser = argparse.ArgumentParser(description="Skill usage report")
    parser.add_argument(
        "--period", "-p",
        choices=["day", "week", "month", "all"],
        default=None,
    )
    parser.add_argument("--top", "-t", type=int, default=None)
    args = parser.parse_args()

    period = args.period if args.period != "all" else None
    report(period=period, top=args.top)


if __name__ == "__main__":
    main()
