"""Shared, UI-independent helpers for selection-set tools."""

from maya import cmds


def normalize_scene_items(items):
    """Return comparable long Maya paths for scene items."""
    if not items:
        return set()
    normalized = cmds.ls(items, long=True) or []
    return set(normalized or items)
