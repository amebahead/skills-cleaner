#!/bin/bash
# Stop hook: reads pending skill file, extracts token usage from transcript tail,
# writes complete entry (with tokens) to skill-usage.jsonl, then cleans up.

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

# Extract output_tokens from transcript tail for the current turn
extract_tokens() {
    local TRANSCRIPT_PATH="$1"
    python3 -c "
import json, sys

try:
    with open('$TRANSCRIPT_PATH') as f:
        lines = f.readlines()

    tail = lines[-200:] if len(lines) > 200 else lines
    entries = []
    for l in tail:
        l = l.strip()
        if l:
            try:
                entries.append(json.loads(l))
            except:
                pass

    # Walk backwards to find turn boundary (last user text message)
    turn_start = 0
    for i in range(len(entries) - 1, -1, -1):
        entry = entries[i]
        if entry.get('type') == 'user':
            content = entry.get('message', {}).get('content', [])
            if any(isinstance(b, dict) and b.get('type') == 'text' for b in content):
                turn_start = i
                break

    # Sum output_tokens from each unique API call in the turn
    # Consecutive assistant entries = one API call, take first only
    total = 0
    i = turn_start
    while i < len(entries):
        if entries[i].get('type') == 'assistant':
            usage = entries[i].get('message', {}).get('usage', {})
            total += usage.get('output_tokens', 0)
            # Skip remaining consecutive assistant entries (same API call)
            while i + 1 < len(entries) and entries[i + 1].get('type') == 'assistant':
                i += 1
        i += 1

    print(total)
except:
    print(0)
" 2>/dev/null
}

# Process each pending skill entry
LOG_FILE="$HOME/.claude/skill-usage.jsonl"

while IFS= read -r line; do
    [ -z "$line" ] && continue

    SKILL=$(echo "$line" | python3 -c "import sys,json;print(json.load(sys.stdin).get('skill',''))" 2>/dev/null)
    SESSION=$(echo "$line" | python3 -c "import sys,json;print(json.load(sys.stdin).get('session',''))" 2>/dev/null)
    TRANSCRIPT=$(echo "$line" | python3 -c "import sys,json;print(json.load(sys.stdin).get('transcript',''))" 2>/dev/null)
    TS=$(echo "$line" | python3 -c "import sys,json;print(json.load(sys.stdin).get('ts',''))" 2>/dev/null)
    SOURCE=$(echo "$line" | python3 -c "import sys,json;print(json.load(sys.stdin).get('source','claude'))" 2>/dev/null)

    [ -z "$SKILL" ] && continue

    TOKENS=$(extract_tokens "$TRANSCRIPT")
    [ -z "$TOKENS" ] && TOKENS=0

    echo "{\"skill\":\"$SKILL\",\"ts\":\"$TS\",\"session\":\"$SESSION\",\"source\":\"$SOURCE\",\"output_tokens\":$TOKENS}" >> "$LOG_FILE"

done < "$PENDING"

rm -f "$PENDING"
