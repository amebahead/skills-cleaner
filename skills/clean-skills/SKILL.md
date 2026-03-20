---
name: clean-skills
description: Compare installed skills for similarity, identify overlapping functionality, and clean up redundant skills — covers personal skills and plugin skills
---

# Clean Skills

Compare all installed skills to identify similar/redundant ones, then interactively guide cleanup.

## When to Use

- When asked to clean up or organize skills
- When checking for duplicate or overlapping skills
- After installing new skills to check for conflicts with existing ones

## Process Flow

```dot
digraph skills_cleaner {
    "Stage 1: Collect" [shape=box];
    "Show skill list to user" [shape=box];
    "Stage 2: Parallel Compare" [shape=box];
    "Pairs <= 30?" [shape=diamond];
    "All parallel" [shape=box];
    "Batch by 10" [shape=box];
    "Stage 3: Report" [shape=box];
    "Any pairs >= 70%?" [shape=diamond];
    "Stage 4: Interactive Select" [shape=box];
    "Final Confirmation" [shape=diamond];
    "Stage 5: Execute Deletion" [shape=box];
    "Done" [shape=doublecircle];

    "Stage 1: Collect" -> "Show skill list to user";
    "Show skill list to user" -> "Stage 2: Parallel Compare";
    "Stage 2: Parallel Compare" -> "Pairs <= 30?";
    "Pairs <= 30?" -> "All parallel" [label="yes"];
    "Pairs <= 30?" -> "Batch by 10" [label="no"];
    "All parallel" -> "Stage 3: Report";
    "Batch by 10" -> "Stage 3: Report";
    "Stage 3: Report" -> "Any pairs >= 70%?";
    "Any pairs >= 70%?" -> "Stage 4: Interactive Select" [label="yes"];
    "Any pairs >= 70%?" -> "Done" [label="no similar pairs"];
    "Stage 4: Interactive Select" -> "Final Confirmation";
    "Final Confirmation" -> "Stage 5: Execute Deletion" [label="yes"];
    "Final Confirmation" -> "Done" [label="no"];
    "Stage 5: Execute Deletion" -> "Done";
}
```

## Stage 1: Collect Skills

Collect SKILL.md files from two paths:
1. `~/.claude/skills/**/SKILL.md` — personal skills
2. `~/.claude/plugins/cache/**/SKILL.md` — plugin skills

Extract from each: name, description, full body content, file path, source (personal/plugin).

Show the collected list to the user:

```
Found 16 skills:
  [personal]  my-custom-skill    ~/.claude/skills/my-custom-skill/
  [plugin]    brainstorming      ~/.claude/plugins/cache/.../brainstorming/
  ...
```

## Stage 2: Parallel Comparison with Subagents

**You MUST use subagents in parallel.** Do NOT compare sequentially in a single agent.

One skill pair = one subagent. Generate N*(N-1)/2 pairs from N skills.

### Subagent Prompt Template

Pass the following prompt along with the full SKILL.md content of both skills to each subagent:

```
Read the full SKILL.md content of both skills and compare them across these 4 dimensions:

1. Purpose similarity — Do they solve the same problem?
2. Trigger similarity — Are they invoked in the same situations?
3. Process similarity — Do their workflows overlap?
4. Output similarity — Do they produce the same type of result?

Scoring guidelines:
- High similarity requires solving the same problem in the same way
- Skills covering the same topic but with different roles (e.g., requesting vs receiving) are complementary, NOT duplicates
- If one skill borrows principles from another but applies them to a different domain, score LOW
- Skills at different stages of a workflow are NOT duplicates

Respond ONLY in this format:

similarity_percent: (integer 0-100)
overlapping_features:
  - "overlapping feature 1"
  - "overlapping feature 2"
differences:
  - "difference 1"
  - "difference 2"
recommendation: "reason for removal or retention"
```

### Batch Strategy

- 30 pairs or fewer: run all subagents in parallel at once
- More than 30 pairs: run in batches of 10

### Failure Handling

If a subagent fails or returns a malformed response, skip that pair. Show the skip count in the report.

## Stage 3: Report

**Only include pairs at 70% or above.** Never include pairs below 70%.

Sort by similarity descending. Follow this exact format:

```
Skills Similarity Report
14 skills · 91 pairs · Threshold: 70%

Found 3 similar pairs:

#1  executing-plans  VS  subagent-driven-development
    ██████████████████░░ 85%  ·  plugin VS plugin

    Overlap
      · Both execute implementation plans via subagents
      · Both include a code review stage

    Diff
      · executing-plans: runs in a separate session
      · subagent-driven-development: runs in the current session

    → Choose one based on whether session isolation is needed

---

#2  ...

---

Summary
  🔴  90%+   Remove candidate   0 pairs
  🟡  70-89% Review suggested   3 pairs
  🟢  <70%   Unique             (skills not in any similar pair)
```

### Similarity Bar

20-character progress bar: `██████████████████░░ 85%`

### Similarity Grades

- 90%+ → 🔴 Remove candidate (nearly identical)
- 70-89% → 🟡 Review suggested (overlapping functionality)
- <70% → Excluded from report

## Stage 4: Interactive Removal Guide

After the report, ask the user:

```
Found N similar pairs. Review them one by one? (y/n)
```

Ask about **one pair at a time** in descending similarity order. Wait for the user's response before showing the next pair. Never show multiple pairs at once.

```
#1  executing-plans  VS  subagent-driven-development  (85%)

    a) Remove executing-plans
    b) Remove subagent-driven-development
    c) Keep both (skip)
```

After the user responds:

```
#2  (next pair)...
```

### Auto-Skip Rule

If the user chose to remove skill A, automatically skip any subsequent pairs that include A, and notify the user.

### Final Confirmation Gate

After reviewing all pairs, always confirm before any actual deletion:

```
To be removed: executing-plans, my-redundant-skill
Proceed? (y/n)
```

### Removal Actions

After the user confirms "Proceed? (y/n)" with yes, **immediately execute deletion** using the Bash tool.

**Personal skills** (`~/.claude/skills/<skill-name>/`):
- Delete the skill directory: `rm -rf ~/.claude/skills/<skill-name>/`
- Verify deletion: `ls ~/.claude/skills/<skill-name>/ 2>&1` (should show "No such file or directory")

**Plugin skills** (`~/.claude/plugins/cache/<plugin>/<plugin>/<version>/skills/<skill-name>/`):
- Delete the skill directory from the plugin cache: `rm -rf <full-path-to-skill-directory>/`
- Verify deletion: `ls <full-path-to-skill-directory>/ 2>&1` (should show "No such file or directory")
- **Important**: After deleting a plugin skill, warn the user:
  ```
  ⚠️  Plugin skill "<skill-name>" was removed from the cache.
      This skill may be restored when the plugin "<plugin-name>" is updated.
      To permanently prevent this, remove the plugin: claude plugins remove <plugin-name>
  ```

For each skill, show the deletion result inline:

```
Removing executing-plans...
  ✅ Deleted: ~/.claude/skills/executing-plans/

Removing old-brainstorm...
  ✅ Deleted: ~/.claude/plugins/cache/superpowers/.../old-brainstorm/
  ⚠️  May be restored on plugin update. To prevent: claude plugins remove superpowers
```

If deletion fails (permission denied, path not found, etc.), show the error and continue with the next skill:

```
Removing broken-skill...
  ❌ Failed: Permission denied — ~/.claude/skills/broken-skill/
```

### Completion Summary

```
Review complete.

  ✅ Removed: 2 skills (executing-plans, old-brainstorm)
  ❌ Failed:  1 skill (broken-skill — Permission denied)
  Kept:      11 skills
  Skipped:   1 pair
```

## Common Mistakes

| Mistake | Correct Approach |
|---------|-----------------|
| Sequential comparison in a single agent | Always use parallel subagents |
| Including pairs below 70% in the report | Only include 70% and above |
| Only providing guidance without actual deletion | Execute `rm -rf` on the skill directory after user confirmation |
| Deleting without final confirmation | Always require final confirmation gate before any deletion |
| Not verifying deletion succeeded | Always verify with `ls` after each `rm -rf` |
| Not warning about plugin skill restoration | Always warn that plugin updates may restore deleted plugin skills |
| Missing source (personal/plugin) labels | Always show Source for each pair |
| Skipping final confirmation before deletion | Always require final confirmation gate |
| Showing multiple pairs at once | Ask one pair at a time, wait for response |
| Treating complementary skills as duplicates | Score low when roles differ |
| Stopping on a single deletion failure | Show error and continue with remaining skills |
