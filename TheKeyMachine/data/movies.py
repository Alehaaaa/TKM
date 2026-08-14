"""Tooltip media paths owned by individual tool packages."""

from __future__ import annotations

import os
from dataclasses import dataclass


TOOLS_ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), os.pardir, "tools"))


@dataclass(frozen=True)
class TooltipMedia:
    path: str

    def __post_init__(self):
        object.__setattr__(self, "path", str(self.path))


def path(filename: str | None, default=None):
    if not filename:
        return default
    matches = []
    for tool_name in os.listdir(TOOLS_ROOT):
        candidate = os.path.join(TOOLS_ROOT, tool_name, "media", filename)
        if os.path.isfile(candidate):
            matches.append(candidate)
    if len(matches) > 1:
        raise RuntimeError("Tooltip movie {!r} has multiple tool owners".format(filename))
    return matches[0] if matches else default


def get_path(name: str, default=None):
    filename = name if os.path.splitext(name)[1] else "{}.gif".format(name)
    return path(filename, default=default)


def get(name: str, default=None):
    resolved = get_path(name)
    return TooltipMedia(resolved) if resolved else default
