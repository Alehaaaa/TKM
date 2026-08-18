"""
TheKeyMachine.tools.clipboard
=============================

Centralized read/write layer for all tool clipboard data (copy-paste temp files).

All tool clipboard operations, including animation, pose, worldspace, copy-link,
and temp-pivot, route through this module instead of
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
# Each entry maps a logical key -> either:
#   - a relative sub-folder name (str), with the filename defaulting to
#     "<key>_data.json", or
#   - an explicit (relative sub-folder, filename) tuple, to override the
#     filename for a slot that needs something other than that default
#     (e.g. two slots sharing one sub-folder with different filenames).
# The root folder is provided by application at call-time to avoid circular imports.
# ---------------------------------------------------------------------------

_SLOTS: dict = {
    "animation":        "copy_animation",
    "curve_keys":       "copy_animation",
    "pose":             "copy_pose",
    "selection_sets":   "selection_sets",
    "worldspace":       "copy_worldspace",
    "copy_link":        "copy_link",
    "temp_pivot":       "temp_pivot",
    "set_default":      "default_default",
    "mirror":           "mirror",
    "animation_layers": "animation_layers",
}

# Same-session copy/paste should not pay JSON serialization and parsing costs.
# Files remain the durable/exportable representation and the cache is refreshed
# whenever a slot is saved or imported.
_MEMORY: dict = {}


def _root() -> str:
    """Return the user data root folder (lazy import to avoid circular deps)."""
    from TheKeyMachine.core import application as general
    return general.USER_FOLDER_PATH


def _resolve(slot: str) -> str:
    """Return the absolute file path for a given clipboard slot key."""
    if slot not in _SLOTS:
        raise ValueError(
            "Unknown clipboard slot: {!r}. Valid slots: {}".format(slot, list(_SLOTS))
        )
    entry = _SLOTS[slot]
    if isinstance(entry, tuple):
        sub, filename = entry
    else:
        sub, filename = entry, "{}_data.json".format(slot)
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
        json.dump(data, fh, indent=2, ensure_ascii=False)
        fh.write("\n")


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
                from maya import cmds
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
                from maya import cmds
                cmds.warning(missing_warning)
            except ImportError:
                pass
        return None
    with open(file_path, "r", encoding="utf-8") as fh:
        return json.load(fh)


def export_to(slot: str, target: str, operation=None) -> Optional[str]:
    """Copy a clipboard slot to an explicit JSON path."""
    source = _resolve(slot)
    if not os.path.exists(source) or not target:
        return None
    if not target.lower().endswith(".json"):
        target += ".json"
    if operation is not None:
        operation.set_total(1, reset=True)
    target_dir = os.path.dirname(target)
    if target_dir:
        os.makedirs(target_dir, exist_ok=True)
    shutil.copyfile(source, target)
    if operation is not None:
        operation.step()
    return target


def import_from(slot: str, source: str, operation=None) -> Optional[Any]:
    """Load an explicit JSON file into a clipboard slot."""
    if not source:
        return None
    if operation is not None:
        operation.set_total(2, reset=True)
    data = load_raw(source, "Could not import file")
    if data is None:
        return None
    if operation is not None:
        operation.step()
    save(slot, data)
    if operation is not None:
        operation.step()
    return data


def export_dialog(slot: str, caption: str, operation=None) -> Optional[str]:
    """Open a Save dialog and copy the slot file to a user-chosen location.

    Returns the exported path, or None if the user cancelled / no data exists.
    """
    from maya import cmds
    from TheKeyMachine.ui.widgets import util as wutil

    file_path = _resolve(slot)
    if not os.path.exists(file_path):
        wutil.make_inViewMessage("No copied data found")
        return None
    result = cmds.fileDialog2(fileMode=0, caption=caption, fileFilter="JSON Files (*.json)")
    if not result:
        return None
    target = result[0]
    if operation is not None:
        operation.set_status(caption)
    target = export_to(slot, target, operation=operation)
    if not target:
        return None
    wutil.make_inViewMessage("File exported")
    return target


def import_dialog(slot: str, caption: str, operation=None) -> Optional[Any]:
    """Open an Open dialog, load JSON from the selected file, write it to *slot*.

    Returns the loaded data, or None if the user cancelled / the file was invalid.
    """
    from maya import cmds
    from TheKeyMachine.ui.widgets import util as wutil

    result = cmds.fileDialog2(fileMode=1, caption=caption, fileFilter="JSON Files (*.json)")
    if not result:
        return None
    source = result[0]
    if operation is not None:
        operation.set_status(caption)
    data = import_from(slot, source, operation=operation)
    if data is None:
        return None
    wutil.make_inViewMessage("File imported")
    return data
