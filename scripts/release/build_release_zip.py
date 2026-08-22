#!/usr/bin/env python3
"""Build the distributable TheKeyMachine zip from the repository root."""

import argparse
import zipfile
from pathlib import Path


REPO_ROOT = Path(__file__).resolve().parents[2]
DEFAULT_DIST_DIR = REPO_ROOT / "dist"
PACKAGE_ITEMS = (
    "TheKeyMachine",
    "TheKeyMachine_Drag&Drop_installer.py",
    "README.md",
    "license_gpl-3.0.txt",
)
EXCLUDED_PARTS = {"__pycache__"}
EXCLUDED_SUFFIXES = {".pyc", ".pyo"}
EXCLUDED_PATHS = {
    Path("TheKeyMachine/tools/micro_move/_native"),
}


def should_include(path):
    relative = path.relative_to(REPO_ROOT)
    if any(part in EXCLUDED_PARTS for part in relative.parts):
        return False
    if path.suffix in EXCLUDED_SUFFIXES:
        return False
    return not any(relative == excluded or excluded in relative.parents for excluded in EXCLUDED_PATHS)


def iter_package_files():
    for item in PACKAGE_ITEMS:
        path = REPO_ROOT / item
        if not path.exists():
            raise SystemExit("Missing package item: {}".format(item))
        if path.is_file():
            yield path
            continue
        for child in sorted(path.rglob("*")):
            if child.is_file() and should_include(child):
                yield child


def build_zip(version, dist_dir):
    dist_dir.mkdir(parents=True, exist_ok=True)
    output = dist_dir / "TKM-{}.zip".format(version)
    with zipfile.ZipFile(output, "w", compression=zipfile.ZIP_DEFLATED) as archive:
        for path in iter_package_files():
            archive.write(path, path.relative_to(REPO_ROOT).as_posix())
    return output


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("version", help="Release version or artifact label")
    parser.add_argument("--dist-dir", default=str(DEFAULT_DIST_DIR))
    args = parser.parse_args()

    dist_dir = Path(args.dist_dir)
    if not dist_dir.is_absolute():
        dist_dir = REPO_ROOT / dist_dir

    output = build_zip(args.version, dist_dir)
    try:
        print(output.relative_to(REPO_ROOT).as_posix())
    except ValueError:
        print(output)


if __name__ == "__main__":
    main()
