"""
Shelf helpers for creating persistent TheKeyMachine shelf buttons.
"""

from __future__ import annotations

import os

from maya import cmds

from TheKeyMachine.Qt import QtGui  # type: ignore


def _current_shelf():
    try:
        return cmds.tabLayout("ShelfLayout", query=True, selectTab=True)
    except Exception:
        return None


def _normalize_icon(icon):
    if isinstance(icon, (str, bytes)):
        return os.path.normpath(icon.decode() if isinstance(icon, bytes) else icon)
    return ""


def _tool_label(tool_name):
    return "TKM - {}".format(tool_name or "Tool")


def _dedupe_shelf_button(parent, label, command):
    for child in cmds.shelfLayout(parent, query=True, childArray=True) or []:
        try:
            if cmds.objectTypeUI(child) != "shelfButton":
                continue
            if cmds.shelfButton(child, query=True, label=True) == label or cmds.shelfButton(child, query=True, command=True) == command:
                cmds.deleteUI(child)
        except Exception:
            continue


def create_tool_shelf_button(tool_id, tool_name, icon=None):
    if not tool_id:
        return None

    parent = _current_shelf()
    if not parent:
        return None

    label = _tool_label(tool_name)
    try:
        from TheKeyMachine.core import trigger

        command = trigger.command_string(tool_id)
    except Exception:
        return None

    _dedupe_shelf_button(parent, label, command)
    return cmds.shelfButton(
        parent=parent,
        image=_normalize_icon(icon),
        command=command,
        label=label,
        annotation=label,
        style="iconOnly",
    )


def show_tool_menu_at_cursor(tool_id):
    from TheKeyMachine.core import toolbox
    from TheKeyMachine.widgets.customWidgets import OpenMenuWidget

    try:
        tool = toolbox.get_tool(tool_id)
    except Exception:
        return None

    setup_fn = tool.get("menu")
    if not callable(setup_fn):
        callback = tool.get("callback")
        if callable(callback):
            return callback()
        return None

    menu = OpenMenuWidget()
    try:
        built_menu = setup_fn(menu, source_widget=None)
    except TypeError:
        built_menu = setup_fn(menu)
    if built_menu is not None and built_menu is not False:
        menu = built_menu
    if not menu.actions():
        return None
    return menu.exec_(QtGui.QCursor.pos())
