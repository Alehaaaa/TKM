"""Validate that one release contains the complete supported native matrix."""

import argparse
import os
import sys


MAYA_VERSIONS = tuple(range(2022, 2028))
PLUGINS = (
    ("depth_mover", "tkmDepthMoverNative"),
    ("micro_move", "tkmMicroMove"),
)
TARGETS = (
    ("windows", "x86_64", ".mll", b"MZ"),
    ("linux", "x86_64", ".so", b"\x7fELF"),
    ("macos", "x86_64", ".bundle", None),
)
MACHO_MAGICS = {
    b"\xca\xfe\xba\xbe",
    b"\xca\xfe\xba\xbf",
    b"\xce\xfa\xed\xfe",
    b"\xcf\xfa\xed\xfe",
    b"\xfe\xed\xfa\xce",
    b"\xfe\xed\xfa\xcf",
}


def expected_binaries(root):
    for maya_version in MAYA_VERSIONS:
        targets = list(TARGETS)
        if maya_version >= 2024:
            targets.append(("macos", "arm64", ".bundle", None))
        for platform_name, architecture, extension, magic in targets:
            for tool, output_name in PLUGINS:
                yield (
                    os.path.join(
                        root,
                        "TheKeyMachine",
                        "tools",
                        tool,
                        "__builds__",
                        "{}-{}".format(platform_name, architecture),
                        "maya{}".format(maya_version),
                        output_name + extension,
                    ),
                    magic,
                    platform_name,
                )


def validate(root):
    errors = []
    checked = 0
    for path, magic, platform_name in expected_binaries(os.path.abspath(root)):
        if not os.path.isfile(path):
            errors.append("Missing: {}".format(path))
            continue
        if os.path.getsize(path) == 0:
            errors.append("Empty: {}".format(path))
            continue
        with open(path, "rb") as stream:
            header = stream.read(4)
        if platform_name == "macos":
            valid_header = header in MACHO_MAGICS
        else:
            valid_header = header.startswith(magic)
        if not valid_header:
            errors.append("Wrong binary format: {}".format(path))
            continue
        checked += 1
    return checked, errors


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument(
        "root",
        nargs="?",
        default=".",
        help="Directory containing the release-ready TheKeyMachine folder",
    )
    args = parser.parse_args()
    checked, errors = validate(args.root)
    if errors:
        print("\n".join(errors), file=sys.stderr)
        return 1
    print("Validated {} native plug-in binaries.".format(checked))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
