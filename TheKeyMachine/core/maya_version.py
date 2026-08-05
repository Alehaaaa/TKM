"""Cached Maya version and release-specific command capability checks."""

from __future__ import annotations

import functools
import re

from maya import cmds


@functools.lru_cache(maxsize=None)
def major_version(value=None):
    """Return the four-digit release from Maya or an explicit version value."""
    raw_value = cmds.about(version=True) if value is None else value
    match = re.search(r"20\d{2}", str(raw_value))
    if not match:
        raise RuntimeError(
            "Could not determine the Maya version from {!r}.".format(raw_value)
        )
    return int(match.group())


def is_at_least(version):
    """Return whether the running Maya release is at least ``version``."""
    try:
        return major_version() >= int(version)
    except Exception:
        return False


@functools.lru_cache(maxsize=1)
def supports_playback_selection():
    """Return whether editable playback-selection flags are actually available."""
    if not is_at_least(2024):
        return False
    try:
        cmds.playbackOptions(query=True, selectionVisible=True)
    except Exception:
        return False
    return True
