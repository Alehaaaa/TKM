"""
Shelf helpers for creating persistent TheKeyMachine shelf buttons.
"""

from __future__ import annotations

import os

from maya import cmds

from TheKeyMachine.Qt import QtGui  # type: ignore


_MENU_BUILDERS = {}


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


def register_menu_builder(tool_id, builder):
    if not tool_id or not callable(builder):
        return

    _MENU_BUILDERS[tool_id] = builder

    try:
        from TheKeyMachine.core import trigger

        def _show_menu_at_cursor():
            return show_tool_menu_at_cursor(tool_id)

        trigger.register_command(tool_id, _show_menu_at_cursor)
    except Exception:
        pass


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


def _exec_menu(menu):
    if not menu or not menu.actions():
        return None
    return menu.exec_(QtGui.QCursor.pos())


def _build_toolbox_menu(setup_fn):
    from TheKeyMachine.widgets.customWidgets import OpenMenuWidget

    menu = OpenMenuWidget()
    try:
        built_menu = setup_fn(menu, source_widget=None)
    except TypeError:
        built_menu = setup_fn(menu)
    if built_menu is not None and built_menu is not False:
        menu = built_menu
    return menu


def show_tool_menu_at_cursor(tool_id):
    if tool_id in _MENU_BUILDERS:
        return _exec_menu(_MENU_BUILDERS[tool_id]())

    try:
        from TheKeyMachine.core import toolMenus

        menu = toolMenus.build_menu_for_shelf(tool_id)
        if menu:
            return _exec_menu(menu)
    except Exception:
        pass

    from TheKeyMachine.core import toolbox

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

    return _exec_menu(_build_toolbox_menu(setup_fn))
