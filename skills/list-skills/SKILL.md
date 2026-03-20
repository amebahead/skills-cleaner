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

### Step 1: Collect

Scan both paths for SKILL.md files:
1. `~/.claude/skills/**/SKILL.md` — personal skills
2. `~/.claude/plugins/cache/**/SKILL.md` — plugin skills

Extract from each: name (from frontmatter), description (from frontmatter), file path, source type.

### Step 2: Identify Plugin Names

For plugin skills, extract the plugin name from the cache path structure:
`~/.claude/plugins/cache/<plugin-name>/...`

For personal skills, label as `personal`.

### Step 3: Display

Group by source and display in this format:

```
Installed Skills (16 total)

personal (2 skills)
  my-custom-skill       Custom automation tool
  my-helper             Helper for daily tasks

superpowers (10 skills)
  brainstorming         Explore intent and requirements before implementation
  writing-plans         Create implementation plans from specs
  debugging             Systematic debugging workflow
  ...

other-plugin (4 skills)
  some-skill            Description here
  ...
```

### Display Rules

- Group by plugin name, personal skills first
- Sort skills alphabetically within each group
- Show skill name and description in two columns
- Truncate description at 60 characters if needed
- Show total count in the header and per-group count
