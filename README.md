# Skills Cleaner

A Claude Code plugin for managing installed skills — list, search, clean up duplicates, and track usage.

## Installation

```bash
claude plugin marketplace add amebahead/skills-cleaner
claude plugin install skills-cleaner
```

Or within Claude Code:

```
/plugin marketplace add amebahead/skills-cleaner
/plugin install skills-cleaner
```

## Commands

| Command | Description |
|---------|-------------|
| `/list-skills` | List all installed skills grouped by plugin |
| `/search-skills` | Search for a skill by name and show its path |
| `/clean-skills` | Compare skills for similarity and clean up duplicates |
| `/profile-skills` | Show skill usage statistics and reports |

### /list-skills

Shows all installed skills grouped by source (personal or plugin name).

```
Installed Skills (16 total)

personal (2 skills)
  my-custom-skill       Custom automation tool
  my-helper             Helper for daily tasks

superpowers (10 skills)
  brainstorming         Explore intent and requirements before implementation
  writing-plans         Create implementation plans from specs
  ...
```

### /search-skills

Find a skill by name and see where it's installed.

```
Search: "debug"  →  2 results

  debugging
    Source:  superpowers (plugin)
    Path:    ~/.claude/plugins/cache/superpowers/skills/systematic-debugging/SKILL.md

  debug-helper
    Source:  personal
    Path:    ~/.claude/skills/debug-helper/SKILL.md
```

### /clean-skills

Compares all installed skills for similarity, generates a report, and interactively guides cleanup.

**4-stage pipeline:**

```
Collect → Parallel Compare → Report → Interactive Removal
```

Report shows only 70%+ similarity pairs:

```
#1  executing-plans  VS  subagent-driven-development
    ██████████████████░░ 85%  ·  plugin VS plugin
```

| Grade | Similarity | Meaning |
|-------|-----------|---------|
| 🔴 | 90%+ | Remove candidate |
| 🟡 | 70-89% | Review suggested |
| 🟢 | <70% | Unique (excluded from report) |

Then presents similar pairs one at a time for interactive removal with a final confirmation gate.

- **Personal skills**: Deletes the skill directory directly
- **Plugin skills**: Never deletes directly — provides guidance on deactivation or removal

### /profile-skills

Shows skill usage statistics with per-skill token consumption.

```
  Skill Usage (all time)
  ===============================================
  Skill                       Count    Tokens
  --------------------------  -----  --------
  brainstorming                  12    45.2K
  list-skills                     8    12.8K
  clean-skills                    5     8.3K
  ===============================================
  Total: 25 triggers | 3 unique skills | 66.3K output tokens
  Period: 2026-04-01 -> 2026-04-10
```

Token data is extracted from session transcripts (`~/.claude/projects/`) by tracing each Skill tool invocation through its response turn.

Options:
- `--period day|week|month|all` — Filter by time period
- `--top N` — Show only top N skills

## Usage Tracking

This plugin automatically tracks skill usage via two hooks registered in `plugin.json`:

| Hook | Event | Tracks |
|------|-------|--------|
| `track-skill.sh` | `PostToolUse` (Skill matcher) | Claude-initiated skill calls |
| `track-skill-prompt.sh` | `UserPromptSubmit` | User-initiated `/skill-name` calls |

Usage data is logged to `~/.claude/skill-usage.jsonl`:

```jsonl
{"skill":"brainstorming","ts":"2026-04-10T02:19:18Z","session":"abc123","source":"claude"}
{"skill":"list-skills","ts":"2026-04-10T03:00:00Z","session":"def456","source":"user"}
```

## License

MIT
