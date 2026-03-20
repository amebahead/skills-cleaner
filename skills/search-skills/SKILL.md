---
name: search-skills
description: Search installed skills by name and show their installed path
---

# Search Skills

Search for installed skills by name and show their file paths.

## When to Use

- When the user wants to find where a specific skill is installed
- When looking up a skill by name or keyword

## Process

### Step 1: Get Search Query

The user provides a skill name or keyword as an argument. If no argument is given, ask:

```
What skill name would you like to search for?
```

### Step 2: Collect

Scan both paths for SKILL.md files:
1. `~/.claude/skills/**/SKILL.md` — personal skills
2. `~/.claude/plugins/cache/**/SKILL.md` — plugin skills

### Step 3: Match

Match the query against skill names using substring matching (case-insensitive).

### Step 4: Display Results

**Matches found:**

```
Search: "debug"  →  2 results

  debugging
    Source:  superpowers (plugin)
    Path:    ~/.claude/plugins/cache/superpowers/skills/systematic-debugging/SKILL.md

  debug-helper
    Source:  personal
    Path:    ~/.claude/skills/debug-helper/SKILL.md
```

**No matches:**

```
Search: "foobar"  →  0 results

No installed skills match "foobar".
```

### Display Rules

- Show the search query and result count on the first line
- For each match: name, source (personal or plugin name), and full path
- Sort results: exact matches first, then partial matches, alphabetically within each group
