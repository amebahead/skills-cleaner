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

### Step 1: Collect via Script

Run the bundled collection script — it scans both paths and outputs JSON in one pass:

```bash
python3 "$(dirname "$SKILL_PATH")/scripts/collect_skills.py"
```

If `$SKILL_PATH` is not available, use the script's absolute path from this skill's directory.

The script scans:
1. `~/.claude/skills/**/SKILL.md` — personal skills
2. `~/.claude/plugins/cache/**/SKILL.md` — plugin skills

It extracts name and description from frontmatter, deduplicates across versions, and returns a sorted JSON array.

### Step 2: Format the Output

Parse the JSON and display using this exact format:

```
Installed Skills (N total)

personal (M skills)
  my-custom-skill       Custom automation tool
  my-helper             Helper for daily tasks

superpowers (14 skills)
  brainstorming         Explore intent and requirements before implementation
  writing-plans         Create implementation plans from specs
  ...
```

### Display Rules

- Group by plugin name, personal skills first, then plugin groups alphabetically
- Sort skills alphabetically within each group
- Show skill name and description in two columns, aligned
- Truncate description at 60 characters with `...` if needed
- Show total count in the header and per-group count
