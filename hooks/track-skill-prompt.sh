#!/bin/bash
# UserPromptSubmit hook: tracks skill usage when user types /skill-name directly.
# Before adding the new entry, flushes any pre-existing pending state — so
# a previous turn's pending (if its Stop hook didn't fire reliably) is
# emitted as its OWN log entry instead of being merged into this turn.

INPUT=$(cat)

PROMPT=$(echo "$INPUT" | python3 -c "
import sys, json
try:
    d = json.load(sys.stdin)
    for key in ('prompt', 'message', 'user_input', 'input', 'content'):
        v = d.get(key, '')
        if v:
            print(v)
            break
    else:
        print('')
except:
    print('')
" 2>/dev/null)

SESSION_ID=$(echo "$INPUT" | python3 -c "
import sys, json
try:
    d = json.load(sys.stdin)
    print(d.get('session_id', 'unknown'))
except:
    print('unknown')
" 2>/dev/null)

SKILL=$(echo "$PROMPT" | python3 -c "
import sys, re
line = sys.stdin.readline().strip()
m = re.match(r'^/([a-zA-Z][a-zA-Z0-9_:-]*)', line)
if m:
    print(m.group(1))
else:
    print('')
" 2>/dev/null)

[ -n "$SKILL" ] || exit 0

TRANSCRIPT_PATH=$(echo "$INPUT" | python3 -c "
import sys, json
try:
    print(json.load(sys.stdin).get('transcript_path', ''))
except:
    print('')
" 2>/dev/null)

PENDING="$HOME/.claude/.skill-pending-${SESSION_ID}.jsonl"
LOG_FILE="$HOME/.claude/skill-usage.jsonl"
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"

# Flush any leftover pending from a prior turn before recording this one.
python3 "${SCRIPT_DIR}/_pending_flush.py" "$PENDING" "$LOG_FILE"

TS=$(date -u +%Y-%m-%dT%H:%M:%SZ)
echo "{\"skill\":\"$SKILL\",\"session\":\"$SESSION_ID\",\"transcript\":\"$TRANSCRIPT_PATH\",\"ts\":\"$TS\",\"source\":\"user\"}" >> "$PENDING"
