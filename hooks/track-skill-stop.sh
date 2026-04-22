#!/bin/bash
# Stop hook: reads pending skill file, extracts token usage + model from transcript tail,
# computes duration from pending ts to now, writes a complete entry to skill-usage.jsonl,
# then cleans up.

INPUT=$(cat)

SESSION_ID=$(echo "$INPUT" | python3 -c "
import sys, json
try:
    print(json.load(sys.stdin).get('session_id', ''))
except:
    print('')
" 2>/dev/null)

PENDING="$HOME/.claude/.skill-pending-${SESSION_ID}.jsonl"
[ -f "$PENDING" ] || exit 0

LOG_FILE="$HOME/.claude/skill-usage.jsonl"

python3 - "$PENDING" "$LOG_FILE" <<'PY'
import json, os, sys
from datetime import datetime, timezone

pending_path, log_path = sys.argv[1], sys.argv[2]


def extract_tokens_and_model(transcript_path):
    tokens, model = 0, ""
    if not transcript_path:
        return tokens, model
    try:
        with open(transcript_path) as f:
            lines = f.readlines()
    except OSError:
        return tokens, model

    tail = lines[-200:] if len(lines) > 200 else lines
    entries = []
    for l in tail:
        l = l.strip()
        if not l:
            continue
        try:
            entries.append(json.loads(l))
        except json.JSONDecodeError:
            pass

    # Walk backwards to find last user text message (turn boundary)
    turn_start = 0
    for i in range(len(entries) - 1, -1, -1):
        entry = entries[i]
        if entry.get("type") == "user":
            content = entry.get("message", {}).get("content", [])
            if any(isinstance(b, dict) and b.get("type") == "text" for b in content):
                turn_start = i
                break

    # Sum output_tokens per API call (consecutive assistant entries = one call)
    # Capture the first model seen in the turn
    i = turn_start
    while i < len(entries):
        if entries[i].get("type") == "assistant":
            msg = entries[i].get("message", {})
            tokens += msg.get("usage", {}).get("output_tokens", 0)
            if not model:
                model = msg.get("model", "") or model
            while i + 1 < len(entries) and entries[i + 1].get("type") == "assistant":
                i += 1
        i += 1

    return tokens, model


def parse_ts(ts):
    if not ts:
        return None
    try:
        return datetime.fromisoformat(ts.replace("Z", "+00:00"))
    except ValueError:
        return None


now = datetime.now(timezone.utc)

try:
    with open(pending_path) as f:
        pending_lines = f.readlines()
except OSError:
    sys.exit(0)

with open(log_path, "a") as out:
    for line in pending_lines:
        line = line.strip()
        if not line:
            continue
        try:
            d = json.loads(line)
        except json.JSONDecodeError:
            continue

        skill = d.get("skill", "")
        if not skill:
            continue

        ts = d.get("ts", "")
        start = parse_ts(ts)
        duration_ms = int((now - start).total_seconds() * 1000) if start else 0

        tokens, model = extract_tokens_and_model(d.get("transcript", ""))

        entry = {
            "skill": skill,
            "ts": ts,
            "session": d.get("session", ""),
            "source": d.get("source", "claude"),
            "model": model,
            "duration_ms": duration_ms,
            "output_tokens": tokens,
        }
        out.write(json.dumps(entry) + "\n")

try:
    os.remove(pending_path)
except OSError:
    pass
PY
