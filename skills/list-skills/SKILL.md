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
