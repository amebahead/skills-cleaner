#!/usr/bin/env python3
"""Collect all installed SKILL.md frontmatter in one pass.

Scans:
  ~/.claude/skills/         (personal skills)
  ~/.claude/plugins/cache/  (plugin skills)
  <project>/.claude/skills/ (project-local skills, walking up from --project-dir)

Deduplicates by name+plugin, keeping the latest version path.
Output formats:
  text     - grouped table for terminals; ANSI colors when stdout is a TTY
             (or `--color always`); off when writing to file or piped.
  markdown - chat-friendly bullet list with bold names; paste directly
             (no fenced code block) so bold renders.
  json     - raw array.
"""

import argparse
import json
import os
import re
import sys
from collections import defaultdict
from pathlib import Path

SKILLS_DIR = Path.home() / ".claude" / "skills"
PLUGINS_CACHE = Path.home() / ".claude" / "plugins" / "cache"

# Pushy "use when..." framings that hide the actual purpose. When followed
# by " - explanation" or ". Explanation", we prefer the explanation half.
TRIGGER_PREFIXES = (
    "This skill should be used when ",
    "Use this skill alongside ",
    "Use this skill to ",
    "Use this skill ",
    "Use this to ",
    "Use when ",
    "Use whenever ",
    "You MUST use this before ",
    "You MUST use this ",
    "TRIGGER when ",
    "Triggers when ",
    "Trigger when ",
)


def extract_frontmatter(path: Path) -> dict:
    """Extract name and description from YAML frontmatter, including
    multi-line description values that wrap onto subsequent lines."""
    try:
        text = path.read_text(encoding="utf-8", errors="replace")
    except OSError:
        return {}

    match = re.match(r"^---\s*\n(.*?)\n---", text, re.DOTALL)
    if not match:
        return {}

    fm = {}
    current_key = None
    for line in match.group(1).splitlines():
        m = re.match(r"^([A-Za-z_][A-Za-z0-9_-]*)\s*:\s*(.*)$", line)
        if m:
            key, val = m.group(1), m.group(2).strip()
            if len(val) >= 2 and val[0] == val[-1] and val[0] in ('"', "'"):
                val = val[1:-1]
            if key in ("name", "description"):
                fm[key] = val
                current_key = key
            else:
                current_key = None
        elif current_key == "description" and line.strip():
            fm["description"] = (fm.get("description", "") + " " + line.strip()).strip()
    return fm


def get_plugin_name(filepath: Path) -> str:
    """Extract plugin name from cache path structure."""
    rel = filepath.relative_to(PLUGINS_CACHE)
    parts = rel.parts
    if len(parts) >= 2:
        first_dir = PLUGINS_CACHE / parts[0]
        second_dir = first_dir / parts[1]
        if second_dir.is_dir() and parts[0] != parts[1]:
            return parts[1]
        return parts[0]
    return parts[0] if parts else "unknown"


def find_project_skills_dir(start: Path):
    """Walk up from `start` looking for `.claude/skills/`. Stops at filesystem
    root, and skips the user's home `.claude` (that's the personal scope).
    Returns the matching directory, or None.
    """
    home = Path.home().resolve()
    cur = start.resolve()
    while True:
        if cur != home:
            cand = cur / ".claude" / "skills"
            if cand.is_dir():
                return cand
        if cur.parent == cur:
            return None
        cur = cur.parent


def collect(project_dir=None) -> list:
    entries = {}

    # Project-local first so it wins over personal/plugin on name collisions.
    if project_dir is not None:
        proj_skills = find_project_skills_dir(project_dir)
        if proj_skills:
            for skill_file in proj_skills.rglob("SKILL.md"):
                fm = extract_frontmatter(skill_file)
                if "name" in fm:
                    key = (fm["name"], "project")
                    entries[key] = {
                        "name": fm["name"],
                        "description": fm.get("description", ""),
                        "path": str(skill_file),
                        "source": "project",
                        "plugin": "project",
                    }

    if SKILLS_DIR.is_dir():
        for skill_file in SKILLS_DIR.rglob("SKILL.md"):
            fm = extract_frontmatter(skill_file)
            if "name" in fm:
                key = (fm["name"], "personal")
                if key not in entries:
                    entries[key] = {
                        "name": fm["name"],
                        "description": fm.get("description", ""),
                        "path": str(skill_file),
                        "source": "personal",
                        "plugin": "personal",
                    }

    if PLUGINS_CACHE.is_dir():
        for skill_file in sorted(PLUGINS_CACHE.rglob("SKILL.md"), reverse=True):
            fm = extract_frontmatter(skill_file)
            if "name" in fm:
                plugin = get_plugin_name(skill_file)
                key = (fm["name"], plugin)
                if key not in entries:
                    entries[key] = {
                        "name": fm["name"],
                        "description": fm.get("description", ""),
                        "path": str(skill_file),
                        "source": "plugin",
                        "plugin": plugin,
                    }

    return sorted(entries.values(), key=lambda e: (e["plugin"], e["name"]))


def shorten_description(desc: str, n: int = 50) -> str:
    """Boil a description down to its purpose-revealing core.

    Strategy: many skills front-load triggering language ("Use when X - ...",
    "You MUST use this before Y. Z.") that buries what the skill actually does.
    When that pattern is present we keep the explanatory half. Then we take
    just the first sentence and truncate.
    """
    if not desc:
        return ""
    desc = desc.strip()

    lower = desc.lower()
    for prefix in TRIGGER_PREFIXES:
        if lower.startswith(prefix.lower()):
            tail_start = len(prefix)
            for sep in (" — ", " - ", ". "):
                idx = desc.find(sep, tail_start)
                if idx != -1:
                    rest = desc[idx + len(sep):].strip()
                    if len(rest) >= 8:
                        desc = (rest[0].upper() + rest[1:]) if rest else rest
                    break
            break

    for sep in (". ", "다. ", "! ", "? "):
        if sep in desc:
            desc = desc.split(sep, 1)[0]
            break
    desc = desc.rstrip(".!?")

    if len(desc) > n:
        desc = desc[: n - 1].rstrip(",.;: ") + "…"
    return desc


def _ansi(code: str, s: str) -> str:
    return f"\033[{code}m{s}\033[0m"


def format_text(entries, *, color: bool = False, project_root=None) -> str:
    groups = defaultdict(list)
    for e in entries:
        groups[e.get("plugin") or "personal"].append(e)

    # Order: project, personal, then plugins alphabetical.
    def group_key(p):
        return ({"project": 0, "personal": 1}.get(p, 2), p)

    plugin_names = sorted(groups.keys(), key=group_key)
    name_width = max((len(e["name"]) for e in entries), default=0)
    name_width = max(name_width, 4)

    def style_name(s):
        return _ansi("1;36", s) if color else s  # bold cyan

    def style_group(s):
        return _ansi("1;33", s) if color else s  # bold yellow

    lines = [f"Installed Skills ({len(entries)} total)"]
    if project_root:
        lines.append(f"  project: {project_root}")
    lines.append("")
    for plugin in plugin_names:
        items = sorted(groups[plugin], key=lambda e: e["name"])
        lines.append(f"{style_group(plugin)} ({len(items)} skills)")
        for e in items:
            desc = shorten_description(e.get("description", "") or "")
            pad = " " * (name_width - len(e["name"]))
            lines.append(f"  {style_name(e['name'])}{pad}  {desc}")
        lines.append("")
    return "\n".join(lines).rstrip() + "\n"


def format_markdown(entries, *, project_root=None) -> str:
    """Chat-friendly markdown. Skill names are wrapped in inline code so they
    render in a distinct accent color in the Claude Code chat panel — bold
    alone only changes weight, not color, in CommonMark renderers.
    """
    groups = defaultdict(list)
    for e in entries:
        groups[e.get("plugin") or "personal"].append(e)

    def group_key(p):
        return ({"project": 0, "personal": 1}.get(p, 2), p)

    plugin_names = sorted(groups.keys(), key=group_key)

    lines = [f"**Installed Skills ({len(entries)} total)**"]
    if project_root:
        lines.append(f"_project: `{project_root}`_")
    lines.append("")
    for plugin in plugin_names:
        items = sorted(groups[plugin], key=lambda e: e["name"])
        word = "skill" if len(items) == 1 else "skills"
        lines.append(f"### {plugin} ({len(items)} {word})")
        lines.append("")
        for e in items:
            desc = shorten_description(e.get("description", "") or "")
            label = f"`{e['name']}`"
            lines.append(f"- {label} — {desc}" if desc else f"- {label}")
        lines.append("")
    return "\n".join(lines).rstrip() + "\n"


def main():
    parser = argparse.ArgumentParser(description="List installed skills.")
    parser.add_argument(
        "--format", "-f",
        choices=["text", "markdown", "json"],
        default="text",
    )
    parser.add_argument(
        "--out", "-o",
        help="Write output to this path instead of stdout (creates parent dirs).",
    )
    parser.add_argument(
        "--project-dir",
        default=os.environ.get("PWD", os.getcwd()),
        help="Where to look for .claude/skills/ (defaults to $PWD).",
    )
    parser.add_argument(
        "--no-project",
        action="store_true",
        help="Skip scanning for project-local skills.",
    )
    parser.add_argument(
        "--color",
        choices=["always", "auto", "never"],
        default="auto",
        help="ANSI color in text format (default: auto — on for tty stdout).",
    )
    args = parser.parse_args()

    project_dir = None if args.no_project else Path(args.project_dir)

    if args.color == "always":
        color = True
    elif args.color == "never":
        color = False
    else:
        color = (
            args.format == "text"
            and args.out is None
            and sys.stdout.isatty()
        )

    entries = collect(project_dir=project_dir)

    project_root = None
    if project_dir is not None:
        proj_skills = find_project_skills_dir(project_dir)
        if proj_skills:
            project_root = str(proj_skills.parent.parent)

    if args.format == "json":
        payload = json.dumps(entries, indent=2, ensure_ascii=False) + "\n"
    elif args.format == "markdown":
        payload = format_markdown(entries, project_root=project_root)
    else:
        payload = format_text(entries, color=color, project_root=project_root)

    if args.out:
        out_path = Path(os.path.expanduser(args.out))
        out_path.parent.mkdir(parents=True, exist_ok=True)
        out_path.write_text(payload, encoding="utf-8")
    else:
        print(payload, end="")


if __name__ == "__main__":
    main()
