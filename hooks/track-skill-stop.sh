#!/bin/bash
# Stop hook: reads pending skill entries for this session, slices the turn's
# assistant messages by skill-invocation boundaries, computes each skill's
# own-segment output_tokens / duration_ms / model, and writes a single
# nested entry to skill-usage.jsonl per turn (root + optional sub_skills array).

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


def parse_ts(ts):
    if not ts:
        return None
    try:
        return datetime.fromisoformat(ts.replace("Z", "+00:00"))
    except ValueError:
        return None


def collect_turn_assistants(transcript_path):
    """Return ordered list of (timestamp, output_tokens, model) for assistant
    entries in the most recent turn (everything after the last user-text
    message). Reads the whole transcript so the turn boundary is always found.
    """
    if not transcript_path:
        return []
    try:
        with open(transcript_path) as f:
            lines = f.readlines()
    except OSError:
        return []

    entries = []
    for l in lines:
        l = l.strip()
        if not l:
            continue
        try:
            entries.append(json.loads(l))
        except json.JSONDecodeError:
            pass

    turn_start = 0
    for i in range(len(entries) - 1, -1, -1):
        e = entries[i]
        if e.get("type") == "user":
            content = e.get("message", {}).get("content", [])
            if any(isinstance(b, dict) and b.get("type") == "text" for b in content):
                turn_start = i
                break

    out = []
    for e in entries[turn_start:]:
        if e.get("type") != "assistant":
            continue
        ts = parse_ts(e.get("timestamp", ""))
        msg = e.get("message", {})
        tokens = msg.get("usage", {}).get("output_tokens", 0) or 0
        model = msg.get("model", "") or ""
        out.append((ts, tokens, model))
    return out


def find_segment_idx(ts, boundaries):
    """Largest i such that boundaries[i] <= ts; defaults to 0 (root) when ts
    precedes all boundaries (e.g. user-prompt hook fires before the first
    assistant message)."""
    idx = 0
    for i, b in enumerate(boundaries):
        if b is not None and b <= ts:
            idx = i
        else:
            break
    return idx


now = datetime.now(timezone.utc)

try:
    with open(pending_path) as f:
        pending_lines = f.readlines()
except OSError:
    sys.exit(0)

pending = []
for line in pending_lines:
    line = line.strip()
    if not line:
        continue
    try:
        d = json.loads(line)
    except json.JSONDecodeError:
        continue
    if d.get("skill"):
        pending.append(d)

if not pending:
    try:
        os.remove(pending_path)
    except OSError:
        pass
    sys.exit(0)

# Sort by ts: first invocation = root, rest = sub-skills in invocation order.
pending.sort(key=lambda e: parse_ts(e.get("ts", "")) or datetime.fromtimestamp(0, tz=timezone.utc))

transcript_path = pending[0].get("transcript", "")
assistants = collect_turn_assistants(transcript_path)

boundaries = [parse_ts(p.get("ts", "")) for p in pending]

segments = [{"tokens": 0, "model": ""} for _ in pending]
for ts, tokens, model in assistants:
    if ts is None:
        continue
    idx = find_segment_idx(ts, boundaries)
    seg = segments[idx]
    seg["tokens"] += tokens
    if model and not seg["model"]:
        seg["model"] = model


def segment_duration_ms(i):
    start = boundaries[i]
    if start is None:
        return 0
    end = boundaries[i + 1] if i + 1 < len(boundaries) else now
    if end is None:
        end = now
    return max(0, int((end - start).total_seconds() * 1000))


root = pending[0]
entry = {
    "skill": root.get("skill", ""),
    "ts": root.get("ts", ""),
    "session": root.get("session", ""),
    "source": root.get("source", "claude"),
    "model": segments[0]["model"],
    "duration_ms": segment_duration_ms(0),
    "output_tokens": segments[0]["tokens"],
}

if len(pending) > 1:
    sub_skills = []
    for i in range(1, len(pending)):
        sub_skills.append({
            "skill": pending[i].get("skill", ""),
            "ts": pending[i].get("ts", ""),
            "source": pending[i].get("source", "claude"),
            "model": segments[i]["model"],
            "duration_ms": segment_duration_ms(i),
            "output_tokens": segments[i]["tokens"],
        })
    entry["sub_skills"] = sub_skills

with open(log_path, "a") as out:
    out.write(json.dumps(entry) + "\n")

try:
    os.remove(pending_path)
except OSError:
    pass
PY
