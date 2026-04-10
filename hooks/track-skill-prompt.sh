#!/bin/bash
# UserPromptSubmit hook: tracks skill usage when user types /skill-name directly
# Receives JSON on stdin from Claude Code

INPUT=$(cat)

# Extract user prompt - try common field names
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

# Check if prompt starts with /skill-name pattern
SKILL=$(echo "$PROMPT" | python3 -c "
import sys, re
line = sys.stdin.readline().strip()
m = re.match(r'^/([a-zA-Z][a-zA-Z0-9_:-]*)', line)
if m:
    print(m.group(1))
else:
    print('')
" 2>/dev/null)

if [ -n "$SKILL" ]; then
    LOG_FILE="$HOME/.claude/skill-usage.jsonl"
    TS=$(date -u +%Y-%m-%dT%H:%M:%SZ)
    echo "{\"skill\":\"$SKILL\",\"ts\":\"$TS\",\"session\":\"$SESSION_ID\",\"source\":\"user\"}" >> "$LOG_FILE"
fi
