# Improve `list-skills` output: project scope, terser descriptions, name emphasis

## Summary

Three improvements to the `list-skills` skill so the listing is more useful at a
glance:

1. **Project-local skills are now included.** The collector walks up from the
   current working directory looking for `.claude/skills/**/SKILL.md` and shows
   them in their own `project` group at the top of the listing, alongside the
   project root path. This complements the existing personal
   (`~/.claude/skills/`) and plugin-cache scans.
2. **Descriptions are condensed to a keyword-style summary.** A new
   `shorten_description()` strips pushy trigger framings (`Use when …`,
   `This skill should be used when …`, `You MUST use this before …`, etc.),
   keeps the explanatory half when the original used a `<trigger> — <purpose>`
   pattern, then takes only the first sentence and truncates to ~50 characters.
3. **Skill names are visually emphasised.** Terminal output (text format) now
   uses bold ANSI cyan for names and bold yellow for group headers when stdout
   is a TTY or `--color always` is passed. Chat output uses a new `markdown`
   format that wraps names in inline code so they render in the chat panel's
   accent color (CommonMark bold only changes weight, not color).

## Script changes (`scripts/collect_skills.py`)

- New `find_project_skills_dir()` walks up from `--project-dir` (defaults to
  `$PWD`) to find the nearest `.claude/skills/`, skipping the user's home dir
  so it doesn't collide with the personal scope.
- `collect()` accepts `project_dir` and adds project entries first, so they
  win over personal/plugin entries on name collisions.
- `extract_frontmatter()` now handles multi-line description values that wrap
  onto subsequent indented lines.
- New `shorten_description()` heuristic (described above).
- New `format_markdown()` renderer for chat output. New `format_text()`
  renderer with optional ANSI color.
- New CLI flags: `--format {text,markdown,json}`, `--color
  {always,auto,never}`, `--project-dir <path>`, `--no-project`.

## SKILL.md changes

- Documents the new project-local scan.
- `verbose: true` path now passes `--color always` so the Bash result panel
  renders the ANSI-coloured table.
- `verbose: false` path now requests the markdown format
  (`--format markdown --out …`) and instructs Claude to paste the file's
  contents as plain markdown — explicitly **not** inside a fenced code block,
  since the names need to render as inline-code for the colour to come through.

## Test plan

- [ ] Run the script directly with `--format markdown` and confirm
      `personal` / `project` (when present) / plugin groups appear in the
      expected order, with shortened descriptions.
- [ ] Run with `--color always` in a terminal and confirm names/headers are
      coloured.
- [ ] In a directory containing `.claude/skills/<name>/SKILL.md`, confirm the
      `project` group appears at the top with the project root path shown.
- [ ] Run `/skills-cleaner:list-skills` from Claude Code with
      `verbose: false` and confirm skill names render in the inline-code
      accent colour in the chat panel.
- [ ] Run `/skills-cleaner:list-skills` with `verbose: true` and confirm the
      ANSI-coloured table renders in the Bash result panel.
