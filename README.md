# Skills Cleaner

A Claude Code plugin that compares installed skills for similarity, identifies overlapping or redundant skills, and interactively guides you through cleanup.

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

## Usage

The skill triggers automatically when you ask Claude Code things like:

- "Clean up my skills"
- "Check for duplicate skills"
- "Compare installed skills"

## How It Works

A 4-stage pipeline:

```
Collect → Parallel Compare → Report → Interactive Removal
```

### Stage 1: Collect Skills

Scans personal skills (`~/.claude/skills/`) and plugin skills (`~/.claude/plugins/cache/`) for SKILL.md files.

### Stage 2: Parallel Comparison

Uses subagents to compare skill pairs in parallel across 4 dimensions: purpose, trigger, process, and output similarity.

### Stage 3: Report

Displays only pairs with 70%+ similarity, sorted in descending order.

```
#1  executing-plans ↔ subagent-driven-development
    Similarity: ██████████████████░░ 85%
    Source: plugin ↔ plugin
```

| Grade | Similarity | Meaning |
|-------|-----------|---------|
| 🔴 | 90%+ | Remove candidate |
| 🟡 | 70-89% | Review suggested |
| 🟢 | <70% | Unique (excluded from report) |

### Stage 4: Interactive Removal

Presents similar pairs one at a time, asking you to remove or keep each. A final confirmation gate is required before any deletion.

- **Personal skills**: Deletes the skill directory directly
- **Plugin skills**: Never deletes directly — provides guidance on deactivation or removal

## Project Structure

```
skills-cleaner/
├── .claude-plugin/
│   ├── plugin.json
│   └── marketplace.json
├── skills/
│   └── skills-cleaner/
│       └── SKILL.md
└── docs/
    └── superpowers/specs/
        └── 2026-03-19-skills-cleaner-design.md
```

## License

MIT
