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
    total_calls = sum(counts.values())

    # Aggregate tokens per skill
    skill_tokens = defaultdict(int)
    for e in entries:
        tokens = e.get("output_tokens", 0)
        if tokens:
            skill_tokens[e["skill"]] += tokens

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
    args = parser.parse_args()

    period = args.period if args.period != "all" else None
    report(period=period, top=args.top)


if __name__ == "__main__":
    main()
