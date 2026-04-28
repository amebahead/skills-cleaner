#!/usr/bin/env python3
"""Collect all installed SKILL.md frontmatter in one pass.

Scans:
  ~/.claude/skills/         (personal skills)
  ~/.claude/plugins/cache/  (plugin skills)

Deduplicates by name+plugin, keeping the latest version path.
Default output is a grouped text table; `--format json` emits the raw array.
"""

import argparse
import json
import os
import re
from collections import defaultdict
from pathlib import Path

SKILLS_DIR = Path.home() / ".claude" / "skills"
PLUGINS_CACHE = Path.home() / ".claude" / "plugins" / "cache"


def extract_frontmatter(path: Path) -> dict:
    """Extract name and description from YAML frontmatter."""
    try:
        text = path.read_text(encoding="utf-8", errors="replace")
    except OSError:
        return {}

    match = re.match(r"^---\s*\n(.*?)\n---", text, re.DOTALL)
    if not match:
        return {}

    fm = {}
    for line in match.group(1).splitlines():
        m = re.match(r"^(name|description):\s*(.+)", line)
        if m:
            val = m.group(2).strip()
            # Strip surrounding quotes
            if len(val) >= 2 and val[0] == val[-1] and val[0] in ('"', "'"):
                val = val[1:-1]
            fm[m.group(1)] = val
    return fm


def get_plugin_name(filepath: Path) -> str:
    """Extract plugin name from cache path structure."""
    rel = filepath.relative_to(PLUGINS_CACHE)
    parts = rel.parts
    if len(parts) >= 2:
        # Pattern: <org>/<plugin>/version/... or <plugin>/<plugin>/version/...
        first_dir = PLUGINS_CACHE / parts[0]
        second_dir = first_dir / parts[1]
        if second_dir.is_dir() and parts[0] != parts[1]:
            return parts[1]  # org/plugin structure
        return parts[0]  # plugin/plugin structure
    return parts[0] if parts else "unknown"


def collect() -> list:
    entries = {}  # key: (name, plugin) -> entry

    # Personal skills
    if SKILLS_DIR.is_dir():
        for skill_file in SKILLS_DIR.rglob("SKILL.md"):
            fm = extract_frontmatter(skill_file)
            if "name" in fm:
                key = (fm["name"], "personal")
                entries[key] = {
                    "name": fm["name"],
                    "description": fm.get("description", ""),
                    "path": str(skill_file),
                    "source": "personal",
                    "plugin": "personal",
                }

    # Plugin skills (cache only)
    if PLUGINS_CACHE.is_dir():
        for skill_file in sorted(PLUGINS_CACHE.rglob("SKILL.md"), reverse=True):
            fm = extract_frontmatter(skill_file)
            if "name" in fm:
                plugin = get_plugin_name(skill_file)
                key = (fm["name"], plugin)
                if key not in entries:  # first match = latest version (reverse sorted)
                    entries[key] = {
                        "name": fm["name"],
                        "description": fm.get("description", ""),
                        "path": str(skill_file),
                        "source": "plugin",
                        "plugin": plugin,
                    }

    return sorted(entries.values(), key=lambda e: (e["plugin"], e["name"]))


def _truncate(s, n=60):
    return s if len(s) <= n else s[: n - 3] + "..."


def format_text(entries):
    """Render collected entries as a grouped text table:
      - personal first, then plugin groups alphabetically
      - skills sorted alphabetically within each group
      - two columns (name, truncated description)
    """
    groups = defaultdict(list)
    for e in entries:
        groups[e.get("plugin") or "personal"].append(e)

    plugin_names = sorted(groups.keys(), key=lambda p: (p != "personal", p))
    name_width = max((len(e["name"]) for e in entries), default=0)
    name_width = max(name_width, 4)

    lines = [f"Installed Skills ({len(entries)} total)", ""]
    for plugin in plugin_names:
        items = sorted(groups[plugin], key=lambda e: e["name"])
        lines.append(f"{plugin} ({len(items)} skills)")
        for e in items:
            desc = _truncate(e.get("description", "") or "")
            lines.append(f"  {e['name']:<{name_width}}  {desc}")
        lines.append("")
    return "\n".join(lines).rstrip() + "\n"


def main():
    parser = argparse.ArgumentParser(description="List installed skills.")
    parser.add_argument(
        "--format", "-f",
        choices=["text", "json"],
        default="text",
        help="Output format (default: text)",
    )
    args = parser.parse_args()

    entries = collect()
    if args.format == "json":
        print(json.dumps(entries, indent=2, ensure_ascii=False))
    else:
        print(format_text(entries), end="")


if __name__ == "__main__":
    main()
