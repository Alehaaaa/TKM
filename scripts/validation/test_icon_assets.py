"""Validate icon assets used by the registered toolbar tools."""

import ast
from pathlib import Path
import unittest
import xml.etree.ElementTree as ElementTree


ROOT = Path(__file__).resolve().parents[2]
ICON_ROOT = ROOT / "TheKeyMachine" / "data" / "icons"
TOOL_ROOT = ROOT / "TheKeyMachine" / "tools"
ICON_EXTENSIONS = (".svg", ".png", ".jpg", ".jpeg")


def registered_icon_names():
    """Return literal icon names declared by tool registration modules."""
    names = set()
    for path in TOOL_ROOT.rglob("__init__.py"):
        tree = ast.parse(path.read_text(encoding="utf-8"), filename=str(path))
        for node in ast.walk(tree):
            if not isinstance(node, ast.Dict):
                continue
            for key, value in zip(node.keys, node.values):
                if (isinstance(key, ast.Constant) and key.value == "icon"
                        and isinstance(value, ast.Constant) and isinstance(value.value, str)):
                    names.add(value.value)
    return names


def resolve_icon(name):
    candidate = ICON_ROOT / name
    if candidate.suffix:
        return candidate if candidate.is_file() else None
    return next((candidate.with_suffix(ext) for ext in ICON_EXTENSIONS
                 if candidate.with_suffix(ext).is_file()), None)


class IconAssetTests(unittest.TestCase):
    def test_all_registered_tool_icons_exist(self):
        missing = sorted(name for name in registered_icon_names() if resolve_icon(name) is None)
        self.assertEqual(missing, [])

    def test_issue_10_assets_are_files(self):
        required = {
            "hotkeys", "reverse_animation",
            "slider_blend/connect_neighbors",
            "slider_tween/blend_to_buffer",
            "slider_tangent/tangent_auto",
        }
        self.assertEqual(sorted(name for name in required if resolve_icon(name) is None), [])

    def test_svg_assets_are_well_formed(self):
        broken = []
        for path in ICON_ROOT.rglob("*.svg"):
            try:
                ElementTree.parse(path)
            except ElementTree.ParseError as error:
                broken.append("{}: {}".format(path.relative_to(ICON_ROOT), error))
        self.assertEqual(broken, [])


if __name__ == "__main__":
    unittest.main()
