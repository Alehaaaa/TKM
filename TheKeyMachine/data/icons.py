"""
Runtime icon lookup.

The attribute name is the asset name:

    icons.bug               -> data/icons/bug.svg
    icons.sliders_overshoot -> data/icons/sliders_overshoot.svg

Missing icons return ``None``.
"""

from __future__ import annotations

import os

import TheKeyMachine.tools.colors as toolColors
from TheKeyMachine.mods.generalMod import config


INSTALL_PATH = config["INSTALL_PATH"]
IMAGE_ROOT = os.path.join(INSTALL_PATH, "TheKeyMachine", "data", "icons")
SELECTION_SETS_ROOT = os.path.join(IMAGE_ROOT, "selection_sets")
ICON_EXTENSIONS = (".svg", ".png", ".jpg", ".jpeg")


def path(filename: str | None, default=None):
    if not filename:
        return default
    return os.path.join(IMAGE_ROOT, filename)


def selection_set_path(filename: str | None, default=None):
    if not filename:
        return default
    return os.path.join(SELECTION_SETS_ROOT, filename)


def get(name: str | None, default=None):
    if not name:
        return default

    if os.path.splitext(name)[1]:
        candidate = path(name)
        return candidate if os.path.exists(candidate) else default

    for ext in ICON_EXTENSIONS:
        candidate = path("{}{}".format(name, ext))
        if os.path.exists(candidate):
            return candidate
    return default


def require(name: str) -> str:
    resolved = get(name)
    if resolved is None:
        raise AttributeError("Unknown icon: {}".format(name))
    return resolved


def exists(name: str) -> bool:
    return get(name) is not None


def _selection_set_icon_filename(color):
    if color.shade and color.shade != "base":
        shade = color.shade.capitalize()
    else: shade = ""
    return "_{}{}_set.svg".format(color.family, shade)


selection_set_color_icon_names = {color.suffix: _selection_set_icon_filename(color) for color in toolColors.SELECTION_SET_COLORS}
selection_set_color_icons = {suffix: selection_set_path(filename) for suffix, filename in selection_set_color_icon_names.items()}
selection_set_color_trash_icons = {
    suffix: selection_set_path(filename.replace(".svg", "_trash.svg")) for suffix, filename in selection_set_color_icon_names.items()
}


def __getattr__(name):
    return get(name)
