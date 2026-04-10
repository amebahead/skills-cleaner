#!/bin/bash
# PostToolUse hook: tracks skill usage when Claude invokes the Skill tool
# Receives JSON on stdin from Claude Code

INPUT=$(cat)

# Extract skill name and session_id
SKILL=$(echo "$INPUT" | python3 -c "
import sys, json
try:
    d = json.load(sys.stdin)
    tool_input = d.get('tool_input', {})
    if isinstance(tool_input, str):
        tool_input = json.loads(tool_input)
    print(tool_input.get('skill', ''))
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

if [ -n "$SKILL" ]; then
    LOG_FILE="$HOME/.claude/skill-usage.jsonl"
    TS=$(date -u +%Y-%m-%dT%H:%M:%SZ)
    echo "{\"skill\":\"$SKILL\",\"ts\":\"$TS\",\"session\":\"$SESSION_ID\",\"source\":\"claude\"}" >> "$LOG_FILE"

    # Set terminal title
    printf '\033]0;Claude · %s\033\\' "$SKILL" > /dev/tty 2>/dev/null || true
fi
