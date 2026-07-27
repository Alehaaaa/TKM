#!/usr/bin/env python3
"""
Render the TheKeyMachine/changelog entry for a specific version as Markdown,
for use as GitHub release notes.

Usage: render_release_notes.py <version>

Loads TheKeyMachine/mods/changelogMod.py directly (it has no Maya dependency)
so the parsing/labeling rules stay in exactly one place instead of being
reimplemented here.
"""

import argparse
import importlib.util
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[2]
CHANGELOG_MOD_PATH = REPO_ROOT / "TheKeyMachine" / "mods" / "changelogMod.py"
CHANGELOG_FILE = REPO_ROOT / "TheKeyMachine" / "changelog"


def load_changelog_mod():
    spec = importlib.util.spec_from_file_location("changelogMod", CHANGELOG_MOD_PATH)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def render_markdown(entries, changelog_mod):
    if not entries:
        return "No changelog entries recorded for this version."

    lines = []
    for entry in entries:
        label = changelog_mod.change_kind_label(entry.get("kind", ""))
        lines.append("- **{}:** {}".format(label, entry.get("description", "")))
    return "\n".join(lines)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("version", help="Version to look up, e.g. 0.1.32")
    args = parser.parse_args()

    changelog_mod = load_changelog_mod()
    raw = CHANGELOG_FILE.read_text(encoding="utf-8") if CHANGELOG_FILE.is_file() else ""
    entries = changelog_mod.parse_changelog_entries(raw, args.version)
    print(render_markdown(entries, changelog_mod))


if __name__ == "__main__":
    main()
