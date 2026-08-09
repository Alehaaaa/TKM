#!/usr/bin/env python3
"""
Keep TheKeyMachine/version, TheKeyMachine/__init__.py, the Drag & Drop
installer, and the README version badge in sync.

Source of truth:
  - __version__                        -> whichever of TheKeyMachine/version
                                           or __init__.py's __version__ is
                                           numerically newer (either can be
                                           bumped by hand; the other catches up)
  - __stage__, __build__, __codename__ -> TheKeyMachine/__init__.py

All files are normalized to report identical metadata. Run with no arguments;
it edits files in place and prints "version=<value>" on stdout (everything
else goes to stderr so this script is safe to redirect straight into
$GITHUB_OUTPUT).
"""

import re
import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[2]
VERSION_FILE = REPO_ROOT / "TheKeyMachine" / "version"
INIT_FILE = REPO_ROOT / "TheKeyMachine" / "__init__.py"
INSTALLER_FILE = REPO_ROOT / "TheKeyMachine_Drag&Drop_installer.py"
README_FILE = REPO_ROOT / "README.md"

FIELDS = ("__version__", "__stage__", "__build__", "__codename__")
README_BADGE_PATTERN = re.compile(r"(img\.shields\.io/badge/version-)[^-]+(-blue\.svg)")


def log(message):
    print(message, file=sys.stderr)


def parse_version(value):
    """Parse a dotted version string into a comparable tuple of ints.

    Returns None for anything that isn't purely numeric dot-separated
    parts (e.g. blank/corrupt), so a bad value loses the "newer" comparison
    to a well-formed one instead of raising.
    """
    if not value:
        return None
    try:
        return tuple(int(part) for part in value.strip().split("."))
    except ValueError:
        return None


def read_fields(path):
    text = path.read_text(encoding="utf-8")
    values = {}
    for field in FIELDS:
        match = re.search(r'^{}\s*=\s*"([^"]*)"'.format(field), text, re.MULTILINE)
        if match:
            values[field] = match.group(1)
    return values


def write_fields(path, values):
    text = path.read_text(encoding="utf-8")
    updated = text
    for field, value in values.items():
        pattern = re.compile(r'^{}\s*=\s*"[^"]*"'.format(field), re.MULTILINE)
        if not pattern.search(updated):
            raise SystemExit("{}: could not find {} to normalize".format(path, field))
        updated = pattern.sub('{} = "{}"'.format(field, value), updated, count=1)
    if updated != text:
        path.write_text(updated, encoding="utf-8")
        return True
    return False


def write_readme_badge(path, version):
    text = path.read_text(encoding="utf-8")
    if not README_BADGE_PATTERN.search(text):
        raise SystemExit("{}: could not find version badge to normalize".format(path))
    updated = README_BADGE_PATTERN.sub(r"\g<1>{}\g<2>".format(version), text, count=1)
    if updated != text:
        path.write_text(updated, encoding="utf-8")
        return True
    return False


def main():
    for path in (VERSION_FILE, INIT_FILE, INSTALLER_FILE, README_FILE):
        if not path.is_file():
            raise SystemExit("Missing required file: {}".format(path))

    version_file_value = VERSION_FILE.read_text(encoding="utf-8").strip()

    init_values = read_fields(INIT_FILE)
    missing_init = [field for field in FIELDS if field not in init_values]
    if missing_init:
        raise SystemExit("{}: missing fields {}".format(INIT_FILE, ", ".join(missing_init)))
    init_version_value = init_values.get("__version__")

    # TheKeyMachine/version and __init__.py's __version__ can each be
    # bumped by hand independently of the other -- adopt whichever is
    # numerically newer as canonical and sync the other one to match,
    # rather than always trusting one file. Ties (equal versions) keep the
    # version file's value, since it's still the one this workflow itself
    # watches.
    version_file_parsed = parse_version(version_file_value)
    init_version_parsed = parse_version(init_version_value)
    if version_file_parsed is None and init_version_parsed is None:
        raise SystemExit(
            "Could not parse a version from {} ({!r}) or {} ({!r})".format(
                VERSION_FILE, version_file_value, INIT_FILE, init_version_value
            )
        )
    if version_file_parsed is None:
        canonical_version = init_version_value
    elif init_version_parsed is None or version_file_parsed >= init_version_parsed:
        canonical_version = version_file_value
    else:
        canonical_version = init_version_value
        log(
            "{} ({}) is newer than {} ({}) -- adopting it as canonical.".format(
                INIT_FILE, init_version_value, VERSION_FILE, version_file_value
            )
        )

    installer_values = read_fields(INSTALLER_FILE)
    drift = {
        field: (init_values.get(field), installer_values.get(field))
        for field in FIELDS
        if field != "__version__" and installer_values.get(field) != init_values.get(field)
    }
    if drift:
        for field, (init_value, installer_value) in drift.items():
            log("Drift in {}: __init__.py={!r} installer={!r}".format(field, init_value, installer_value))

    # __init__.py is the source of truth for stage/build/codename.
    canonical = dict(init_values)
    canonical["__version__"] = canonical_version

    changed_files = []
    if version_file_value != canonical_version:
        VERSION_FILE.write_text(canonical_version + "\n", encoding="utf-8")
        changed_files.append(str(VERSION_FILE.relative_to(REPO_ROOT)))
    if write_fields(INIT_FILE, canonical):
        changed_files.append(str(INIT_FILE.relative_to(REPO_ROOT)))
    if write_fields(INSTALLER_FILE, canonical):
        changed_files.append(str(INSTALLER_FILE.relative_to(REPO_ROOT)))
    if write_readme_badge(README_FILE, canonical_version):
        changed_files.append(str(README_FILE.relative_to(REPO_ROOT)))

    if changed_files:
        log("Normalized version metadata in: {}".format(", ".join(changed_files)))
    else:
        log("Version metadata already in sync.")

    print("version={}".format(canonical_version))


if __name__ == "__main__":
    main()
