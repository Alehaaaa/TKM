"""Declarative tooltip-media references and movie path lookup."""

from __future__ import annotations

import os
from dataclasses import dataclass


MOVIE_ROOT = os.path.join(os.path.dirname(__file__), "movies")


@dataclass(frozen=True)
class TooltipMedia:
    path: str

    def __post_init__(self):
        object.__setattr__(self, "path", str(self.path))


def path(filename: str | None, default=None):
    if not filename:
        return default
    return os.path.join(MOVIE_ROOT, filename)


def get_path(name: str, default=None):
    filename = name if os.path.splitext(name)[1] else "{}.gif".format(name)
    resolved = path(filename)
    return resolved if os.path.exists(resolved) else default


def get(name: str, default=None):
    resolved = get_path(name)
    return TooltipMedia(resolved) if resolved else default


def __getattr__(name):
    return get(name)
