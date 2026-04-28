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

The `Stop` hook records one entry per turn after collecting all skill invocations that fired in that turn. The first invocation in a turn is the **root** skill; any further skill calls that happened during the same turn are recorded as **sub-skills** nested under the root.

For each skill (root or sub) the hook captures its **own segment**:

- `output_tokens` — assistant output tokens whose timestamps fall between this skill's invocation and the next skill's invocation (or the turn's end). Non-overlapping, so summing across rows in a report gives the true total.
- `input_tokens` / `cache_read_input_tokens` / `cache_creation_input_tokens` — input-side counters from the same `usage` block, summed per segment with the same boundaries. Cache-read and cache-write are kept separate because their effective pricing differs (read ~0.1×, write ~1.25×).
- `model` — first model seen in the segment (typically the Claude model ID for the turn).
- `duration_ms` — elapsed time from this skill's invocation to the next boundary (next sub-skill invocation, or `Stop` firing for the last segment).

The report displays a parent's total inclusive of its sub-skills (e.g. `7.0K (brainstorming: 1.2K, writing-plans: 500)`) — the parenthesised breakdown is computed from the `sub_skills` array.

## If No Data Found

The tracking hooks log skill invocations to `~/.claude/skill-usage.jsonl`. If the file is missing or empty, the hooks may not be configured. Check that `~/.claude/settings.json` (or the plugin's `plugin.json`) has:

1. A `PostToolUse` hook with `Skill` matcher — tracks Claude-initiated skill calls
2. A `UserPromptSubmit` hook — tracks user-initiated `/skill-name` calls

Both hooks are bundled with this plugin and registered automatically via `plugin.json`.

## Log Format

Each line in `skill-usage.jsonl` is one JSON object per turn. A turn with only one skill invocation produces a flat entry; a turn with sub-skills nests them under `sub_skills`.

```jsonl
{"skill":"list-skills","ts":"2026-04-10T03:00:00Z","session":"def456","source":"user","model":"claude-sonnet-4-6","duration_ms":2100,"input_tokens":4,"cache_creation_input_tokens":0,"cache_read_input_tokens":21000,"output_tokens":1234}
{"skill":"skill-creator:skill-creator","ts":"2026-04-27T10:00:00Z","session":"abc","source":"user","model":"claude-opus-4-7","duration_ms":12000,"input_tokens":12,"cache_creation_input_tokens":26000,"cache_read_input_tokens":16700,"output_tokens":4000,"sub_skills":[{"skill":"superpowers:brainstorming","ts":"2026-04-27T10:01:00Z","source":"claude","model":"claude-opus-4-7","duration_ms":10000,"input_tokens":3,"cache_creation_input_tokens":500,"cache_read_input_tokens":40000,"output_tokens":800}]}
```

- `source: "claude"` — Claude invoked the skill via the Skill tool
- `source: "user"` — User typed `/skill-name` directly
- All token / duration fields are own-segment values, not inclusive of sub-skills (sum the row + `sub_skills[*]` to get the turn total).
- `sub_skills` — present only when more than one skill fired in the turn; ordered by invocation time.

Older log lines without `sub_skills` or input-side fields are still readable; the report treats missing token fields as zero (rendered as `-`).
