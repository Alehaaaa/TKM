"""
Runtime icon lookup.

The attribute name is the asset name:

    icons.bug               -> data/icons/bug.svg
    icons.sliders_overshoot -> data/icons/sliders_overshoot.svg
    icons.slider_blend.icons.connect_neighbors
                            -> data/icons/slider_blend/connect_neighbors.svg

Missing icons return ``None``.
"""

from __future__ import annotations

import os

from TheKeyMachine.data.colors import COLORS


IMAGE_ROOT = os.path.join(os.path.dirname(__file__), "icons")
SELECTION_SETS_ROOT = os.path.join(IMAGE_ROOT, "selection_sets")
ICON_EXTENSIONS = (".svg", ".png", ".jpg", ".jpeg")


class _IconNamespace:
    """Attribute-based access to one nested icon directory."""

    def __init__(self, *parts):
        self._parts = tuple(parts)

    @property
    def icons(self):
        return self

    def __getattr__(self, name):
        parts = self._parts + (name,)
        directory = os.path.join(IMAGE_ROOT, *parts)
        if os.path.isdir(directory):
            return _IconNamespace(*parts)
        return get("/".join(parts))


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


def selection_set_icon_filename(color):
    if color.shade and color.shade != "base":
        shade = color.shade.capitalize()
    else: shade = ""
    return "_{}{}_set.svg".format(color.family, shade)


selection_set_color_icon_names = {
    color.suffix: selection_set_icon_filename(color)
    for color in COLORS.selection.all
}
selection_set_color_icons = {suffix: selection_set_path(filename) for suffix, filename in selection_set_color_icon_names.items()}
selection_set_color_trash_icons = {
    suffix: selection_set_path(filename.replace(".svg", "_trash.svg")) for suffix, filename in selection_set_color_icon_names.items()
}


def __getattr__(name):
    directory = os.path.join(IMAGE_ROOT, name)
    if os.path.isdir(directory):
        return _IconNamespace(name)
    return get(name)
