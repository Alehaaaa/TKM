"""
TheKeyMachine.tools.clipboard
=============================

Centralized read/write layer for all tool clipboard data (copy-paste temp files).

All tool clipboard operations — animation, pose, worldspace animation,
worldspace frame, copy-link, temp-pivot — route through this module instead of
scattering os.path / open / json.dump / json.load calls across every tool.

Usage (write):
    clipboard.save("worldspace", payload)

Usage (read):
    data = clipboard.load("worldspace")   # returns None + warning if missing

Usage (paths, for export/import dialogs):
    path = clipboard.path("animation")
"""
from __future__ import annotations

import json
import os
import shutil
from typing import Any, Optional

# ---------------------------------------------------------------------------
# Registry of known clipboard slots
# Each entry maps a logical key -> (relative sub-folder, filename)
# The root folder is provided by generalMod at call-time to avoid circular imports.
# ---------------------------------------------------------------------------

_SLOTS: dict = {
    "animation":        ("copy_animation",  "copy_animation_data.json"),
    "pose":             ("copy_pose",        "copy_pose_data.json"),
    "worldspace":       ("copy_worldspace", "copy_worldspace_data.json"),
    "worldspace_frame": ("copy_worldspace", "copy_worldspace_single_frame_data.json"),
    "copy_link":        ("copy_link",        "copy_link_data.json"),
    "temp_pivot":       ("temp_pivot",       "temp_pivot_data.json"),
    "set_default":      ("default_default",  "default_default_data.json"),
    "mirror":           ("mirror",           "mirror_data.json"),
}

# Same-session copy/paste should not pay JSON serialization and parsing costs.
# Files remain the durable/exportable representation and the cache is refreshed
# whenever a slot is saved or imported.
_MEMORY: dict = {}


def _root() -> str:
    """Return the user data root folder (lazy import to avoid circular deps)."""
    from TheKeyMachine.mods import generalMod as general
    return general.USER_FOLDER_PATH


def _resolve(slot: str) -> str:
    """Return the absolute file path for a given clipboard slot key."""
    if slot not in _SLOTS:
        raise ValueError(
            "Unknown clipboard slot: {!r}. Valid slots: {}".format(slot, list(_SLOTS))
        )
    sub, filename = _SLOTS[slot]
    return os.path.join(_root(), "TheKeyMachine_user_data", "tools", sub, filename)


# ---------------------------------------------------------------------------
# Public API
# ---------------------------------------------------------------------------


def path(slot: str) -> str:
    """Return the absolute file path for the given slot (for export/import dialogs)."""
    return _resolve(slot)


def exists(slot: str) -> bool:
    """Return True if a clipboard file exists for the given slot."""
    return os.path.exists(_resolve(slot))


def save(slot: str, data: Any) -> None:
    """Serialize *data* as JSON and write it to the clipboard slot file.

    Creates parent directories if they do not exist.
    """
    file_path = _resolve(slot)
    _MEMORY[slot] = data
    os.makedirs(os.path.dirname(file_path), exist_ok=True)
    with open(file_path, "w", encoding="utf-8") as fh:
        json.dump(data, fh, separators=(",", ":"))


def load(slot: str, missing_warning: Optional[str] = None) -> Optional[Any]:
    """Load and return the JSON data from the given clipboard slot.

    Returns ``None`` and emits a Maya warning if the file is absent.
    """
    if slot in _MEMORY:
        return _MEMORY[slot]

    file_path = _resolve(slot)
    if not os.path.exists(file_path):
        if missing_warning:
            try:
                import maya.cmds as cmds
                cmds.warning(missing_warning)
            except ImportError:
                pass
        return None
    with open(file_path, "r", encoding="utf-8") as fh:
        data = json.load(fh)
    _MEMORY[slot] = data
    return data


def load_raw(file_path: str, missing_warning: Optional[str] = None) -> Optional[Any]:
    """Load JSON from an arbitrary file path (not a slot key)."""
    if not os.path.exists(file_path):
        if missing_warning:
            try:
                import maya.cmds as cmds
                cmds.warning(missing_warning)
            except ImportError:
                pass
        return None
    with open(file_path, "r", encoding="utf-8") as fh:
        return json.load(fh)


def export_dialog(slot: str, caption: str) -> Optional[str]:
    """Open a Save dialog and copy the slot file to a user-chosen location.

    Returns the exported path, or None if the user cancelled / no data exists.
    """
    import maya.cmds as cmds
    from TheKeyMachine.widgets import customWidgets as wutil

    file_path = _resolve(slot)
    if not os.path.exists(file_path):
        wutil.make_inViewMessage("No copied data found")
        return None
    result = cmds.fileDialog2(fileMode=0, caption=caption, fileFilter="JSON Files (*.json)")
    if not result:
        return None
    target = result[0]
    if not target.lower().endswith(".json"):
        target += ".json"
    os.makedirs(os.path.dirname(target), exist_ok=True)
    shutil.copyfile(file_path, target)
    wutil.make_inViewMessage("File exported")
    return target


def import_dialog(slot: str, caption: str) -> Optional[Any]:
    """Open an Open dialog, load JSON from the selected file, write it to *slot*.

    Returns the loaded data, or None if the user cancelled / the file was invalid.
    """
    import maya.cmds as cmds
    from TheKeyMachine.widgets import customWidgets as wutil

    result = cmds.fileDialog2(fileMode=1, caption=caption, fileFilter="JSON Files (*.json)")
    if not result:
        return None
    source = result[0]
    data = load_raw(source, "Could not import file")
    if data is None:
        return None
    save(slot, data)
    wutil.make_inViewMessage("File imported")
    return data
