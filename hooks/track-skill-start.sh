#!/bin/bash
# PostToolUse hook: records pending skill for Stop hook to finalize with token data
# Receives JSON on stdin from Claude Code

INPUT=$(cat)

RESULT=$(echo "$INPUT" | python3 -c "
import sys, json
try:
    d = json.load(sys.stdin)
    tool_input = d.get('tool_input', {})
    if isinstance(tool_input, str):
        tool_input = json.loads(tool_input)
    skill = tool_input.get('skill', '')
    session = d.get('session_id', 'unknown')
    transcript = d.get('transcript_path', '')
    if skill:
        print(json.dumps({'skill': skill, 'session': session, 'transcript': transcript}))
except:
    pass
" 2>/dev/null)

if [ -n "$RESULT" ]; then
    SESSION=$(echo "$RESULT" | python3 -c "import sys,json;print(json.load(sys.stdin)['session'])" 2>/dev/null)
    PENDING="$HOME/.claude/.skill-pending-${SESSION}.jsonl"
    # Millisecond precision so segment boundaries match transcript-recorded
    # assistant timestamps cleanly (avoids off-by-one segment attribution).
    TS=$(python3 -c "from datetime import datetime, timezone; n=datetime.now(timezone.utc); print(n.strftime('%Y-%m-%dT%H:%M:%S.')+f'{n.microsecond//1000:03d}Z')")
    echo "{\"skill\":$(echo "$RESULT" | python3 -c "import sys,json;d=json.load(sys.stdin);print(json.dumps(d['skill']))" 2>/dev/null),\"session\":\"$SESSION\",\"transcript\":$(echo "$RESULT" | python3 -c "import sys,json;d=json.load(sys.stdin);print(json.dumps(d['transcript']))" 2>/dev/null),\"ts\":\"$TS\"}" >> "$PENDING"

    # Set terminal title
    SKILL=$(echo "$RESULT" | python3 -c "import sys,json;print(json.load(sys.stdin)['skill'])" 2>/dev/null)
    printf '\033]0;Claude · %s\033\\' "$SKILL" > /dev/tty 2>/dev/null || true
fi
