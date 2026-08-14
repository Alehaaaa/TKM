#!/usr/bin/env python3
"""
Render the TheKeyMachine/changelog entry for a specific version as Markdown,
for use as GitHub release notes.

Usage: render_release_notes.py <version> [--previous-version <version>]

Loads TheKeyMachine/tools/update/changelog.py directly (it has no Maya dependency)
so the parsing/labeling rules stay in exactly one place instead of being
reimplemented here.
"""

import argparse
import importlib.util
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[2]
CHANGELOG_MODULE_PATH = (
    REPO_ROOT / "TheKeyMachine" / "tools" / "update" / "changelog.py"
)
CHANGELOG_FILE = REPO_ROOT / "TheKeyMachine" / "changelog"
COMPARE_URL = "https://github.com/Alehaaaa/TKM/compare/TKM-{previous}...TKM-{current}"


def load_changelog_module():
    spec = importlib.util.spec_from_file_location(
        "thekeymachine_changelog", CHANGELOG_MODULE_PATH
    )
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def render_markdown(entries, changelog_module, version, previous_version=None):
    if not entries:
        notes = "No changelog entries recorded for this version."
    else:
        lines = []
        for entry in entries:
            label = changelog_module.change_kind_label(entry.get("kind", ""))
            lines.append("- **{}:** {}".format(label, entry.get("description", "")))
        notes = "\n".join(lines)

    if previous_version:
        compare_url = COMPARE_URL.format(previous=previous_version, current=version)
        notes += "\n\n**Full Changelog**: {}".format(compare_url)

    return notes


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("version", help="Version to look up, e.g. 0.1.32")
    parser.add_argument(
        "--previous-version",
        help="Previous tagged version used to append a GitHub compare link",
    )
    args = parser.parse_args()

    changelog_module = load_changelog_module()
    raw = CHANGELOG_FILE.read_text(encoding="utf-8") if CHANGELOG_FILE.is_file() else ""
    entries = changelog_module.parse_changelog_entries(raw, args.version)
    print(render_markdown(entries, changelog_module, args.version, args.previous_version))


if __name__ == "__main__":
    main()
