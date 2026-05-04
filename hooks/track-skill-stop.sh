#!/bin/bash
# Stop hook: flush the per-session pending file into skill-usage.jsonl.
# Per-segment token / duration / model attribution lives in
# hooks/_pending_flush.py — both this hook and track-skill-prompt.sh
# call it.

INPUT=$(cat)

SESSION_ID=$(echo "$INPUT" | python3 -c "
import sys, json
try:
    print(json.load(sys.stdin).get('session_id', ''))
except:
    print('')
" 2>/dev/null)

[ -n "$SESSION_ID" ] || exit 0

PENDING="$HOME/.claude/.skill-pending-${SESSION_ID}.jsonl"
LOG_FILE="$HOME/.claude/skill-usage.jsonl"
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"

python3 "${SCRIPT_DIR}/_pending_flush.py" "$PENDING" "$LOG_FILE"
