---
name: list-skills
description: List all installed skills and show which plugin each belongs to
---

# List Skills

Show all installed skills with their source (project / personal / plugin) and a short purpose hint, names emphasised for scannability.

## When to Use

- When the user wants to see what skills are installed
- When checking which plugin a skill belongs to

## Process

### Step 1: Run the collection script

The bundled script scans three locations — project (`<cwd>/.claude/skills/**`, walking up to find the nearest one), personal (`~/.claude/skills/**`), and plugin cache (`~/.claude/plugins/cache/**`) — extracts each skill's frontmatter, deduplicates across versions, shortens each description to a keyword-style summary, and groups the result. Project skills come first when present, then personal, then plugin groups alphabetically.

### Step 2: Display based on `verbose`

How the table reaches the user depends on their `verbose` setting (in `~/.claude/settings.json`). Long Bash tool results are collapsed to "+N lines (ctrl+o to expand)" unless `verbose: true`, so the execution path differs:

1. **Read `~/.claude/settings.json`** (or `~/.claude/settings.local.json` if it overrides) once before deciding.

2. **If `verbose === true`** — run the script directly with ANSI color forced on so the Bash panel renders highlighted skill names:

   ```bash
   python3 "${CLAUDE_PLUGIN_ROOT}/skills/list-skills/scripts/collect_skills.py" --color always
   ```

   The Bash result panel shows the full table. Stay silent — do not re-paste, summarize, or reformat.

3. **If `verbose !== true`** (false or absent) — use the markdown format so bold skill names render in chat. Pass `--out` so the script writes the file itself (no shell redirect, so `Bash(python3:*)` matches cleanly and the Bash panel stays empty):

   ```bash
   python3 "${CLAUDE_PLUGIN_ROOT}/skills/list-skills/scripts/collect_skills.py" --format markdown --out ~/.claude/.cache/skills-cleaner-list.md
   ```

   Then Read `~/.claude/.cache/skills-cleaner-list.md` and paste its contents **verbatim as plain markdown — NOT inside a fenced code block**. Pasting in a code block would show literal `**name**` instead of bold names. The pasted markdown becomes the user's only visible output. Don't rephrase or reformat.

   The script creates the parent dir if missing. stderr is untouched, so any error stays visible in the Bash panel for debugging.

Never add commentary before or after unless the user follows up.

## Flags worth knowing

- `--no-project` — skip the project-local scan (useful when the cwd is irrelevant).
- `--project-dir <path>` — point the project scan somewhere other than `$PWD`.
- `--format json` — raw array, for piping into other tooling.
