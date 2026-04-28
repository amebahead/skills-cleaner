---
name: list-skills
description: List all installed skills and show which plugin each belongs to
---

# List Skills

Show all installed skills with their source plugin and path.

## When to Use

- When the user wants to see what skills are installed
- When checking which plugin a skill belongs to

## Process

### Step 1: Run the collection script

The bundled script scans personal skills (`~/.claude/skills/**/SKILL.md`) and plugin skills (`~/.claude/plugins/cache/**/SKILL.md`), extracts the frontmatter, deduplicates across versions, and prints a grouped, aligned table by default. Use the absolute path from this skill's directory when invoking it:

```bash
python3 "${CLAUDE_PLUGIN_ROOT}/skills/list-skills/scripts/collect_skills.py"
```

The default text output is already in the right shape (personal first, then plugin groups alphabetically; skills alphabetised within each group; descriptions truncated at 60 chars). Pass `--format json` only if you need the raw array for further processing.

### Step 2: Display based on `verbose`

How the table reaches the user depends on their `verbose` setting (in `~/.claude/settings.json`). Long Bash tool results are collapsed to "+N lines (ctrl+o to expand)" unless `verbose: true`, so the execution path differs:

1. **Read `~/.claude/settings.json`** (or `~/.claude/settings.local.json` if it overrides) once before deciding.

2. **If `verbose === true`** — run the script directly:

   ```bash
   python3 "${CLAUDE_PLUGIN_ROOT}/skills/list-skills/scripts/collect_skills.py"
   ```

   The Bash result panel shows the full table. Stay silent — do not re-paste, summarize, or reformat.

3. **If `verbose !== true`** (false or absent) — pass `--out` so the script writes the table itself (no shell redirect, so `Bash(python3:*)` matches cleanly and the Bash panel stays empty):

   ```bash
   python3 "${CLAUDE_PLUGIN_ROOT}/skills/list-skills/scripts/collect_skills.py" --out ~/.claude/.cache/skills-cleaner-list.txt
   ```

   Then Read `~/.claude/.cache/skills-cleaner-list.txt` and paste its contents **verbatim as a fenced code block**. This becomes the user's only visible output. Don't rephrase or reformat.

   The script creates the parent dir if missing. stderr is untouched, so any error stays visible in the Bash panel for debugging.

Never add commentary before or after unless the user follows up.
