---
name: profile-skills
description: "Track and report Claude Code skill usage statistics. Use this whenever the user asks about skill usage, skill stats, skill reports, which skills are used most or least, wants to clean up unused skills, optimize their skill set, or mentions skill profiling, skill tracking, skill usage frequency, or any question about how often skills get triggered."
---

# Skill Usage Profiler

Generate skill usage reports from tracked data stored at `~/.claude/skill-usage.jsonl`.

## Generating Reports

Run the bundled report script:

```bash
python3 "${CLAUDE_PLUGIN_ROOT}/skills/profile-skills/scripts/report.py" [OPTIONS]
```

Options:
- `--period day|week|month|all` — Filter by time period (default: all)
- `--top N` — Show only top N skills
- `--detail` — Open an HTML visualization report in the browser (bar charts + heatmap)

Examples:
- All-time stats: `python3 "${CLAUDE_PLUGIN_ROOT}/skills/profile-skills/scripts/report.py"`
- This week only: `python3 "${CLAUDE_PLUGIN_ROOT}/skills/profile-skills/scripts/report.py" --period week`
- Top 5 skills this month: `python3 "${CLAUDE_PLUGIN_ROOT}/skills/profile-skills/scripts/report.py" --period month --top 5`
- Visual report: `python3 "${CLAUDE_PLUGIN_ROOT}/skills/profile-skills/scripts/report.py" --detail`
- Visual report (this week): `python3 "${CLAUDE_PLUGIN_ROOT}/skills/profile-skills/scripts/report.py" --detail --period week`

## Output Rules

**ALWAYS paste the script's terminal output verbatim as a fenced code block.** Do not summarize, rephrase, or reformat the table into prose. The script already produces a well-formatted table — show it exactly as printed. No additional commentary is needed before or after the table unless the user asks a follow-up question.

When `--detail` is used, the script opens a browser automatically. Print the URL from script output and tell the user to press Ctrl+C when done.

## Token / Model / Duration Tracking

The `Stop` hook captures per-turn metrics after each skill invocation:

- `output_tokens` — summed from assistant entries in the transcript tail
- `model` — the Claude model ID used during the turn (from the transcript's assistant message)
- `duration_ms` — elapsed milliseconds between the skill invocation (PostToolUse / UserPromptSubmit) and the `Stop` hook firing

All three fields are recorded for both Claude-initiated (`source: "claude"`) and user-initiated (`source: "user"`) calls. The report aggregates average duration per call and the primary model used per skill.

## If No Data Found

The tracking hooks log skill invocations to `~/.claude/skill-usage.jsonl`. If the file is missing or empty, the hooks may not be configured. Check that `~/.claude/settings.json` (or the plugin's `plugin.json`) has:

1. A `PostToolUse` hook with `Skill` matcher — tracks Claude-initiated skill calls
2. A `UserPromptSubmit` hook — tracks user-initiated `/skill-name` calls

Both hooks are bundled with this plugin and registered automatically via `plugin.json`.

## Log Format

Each line in `skill-usage.jsonl` is a JSON object:

```jsonl
{"skill":"brainstorming","ts":"2026-04-10T02:19:18Z","session":"abc123","source":"claude","model":"claude-opus-4-7-20251022","duration_ms":12400,"output_tokens":2566}
{"skill":"list-skills","ts":"2026-04-10T03:00:00Z","session":"def456","source":"user","model":"claude-sonnet-4-6-20250929","duration_ms":2100,"output_tokens":1234}
```

- `source: "claude"` — Claude invoked the skill via the Skill tool
- `source: "user"` — User typed `/skill-name` directly
- `model`, `duration_ms`, `output_tokens` — captured by the `Stop` hook from the transcript tail and pending-entry timestamp
