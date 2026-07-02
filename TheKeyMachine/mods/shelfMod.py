"""
Shelf helpers for creating persistent TheKeyMachine shelf buttons.
"""

from __future__ import annotations

import os
import weakref

from maya import cmds

from TheKeyMachine.Qt import QtCore, QtGui  # type: ignore


_MENU_BUILDERS = {}
_OPEN_SHELF_MENUS = []


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


def _is_menu_open(menu):
    try:
        return bool(menu.isVisible() or menu.isTearOffMenuVisible())
    except Exception:
        return False


def _release_closed_menu(menu_ref):
    menu = menu_ref()
    if menu is None or _is_menu_open(menu):
        return
    try:
        _OPEN_SHELF_MENUS.remove(menu)
    except ValueError:
        pass


def _keep_menu_alive(menu):
    if menu not in _OPEN_SHELF_MENUS:
        _OPEN_SHELF_MENUS.append(menu)
    try:
        if menu.property("tkm_shelf_lifetime_bound"):
            return
        menu.setProperty("tkm_shelf_lifetime_bound", True)
        menu_ref = weakref.ref(menu)
        menu.aboutToHide.connect(lambda: QtCore.QTimer.singleShot(0, lambda: _release_closed_menu(menu_ref)))
        menu.destroyed.connect(lambda *_args: _release_closed_menu(menu_ref))
    except Exception:
        pass


def _exec_menu(menu):
    if not menu or not menu.actions():
        return None
    _keep_menu_alive(menu)
    result = menu.exec_(QtGui.QCursor.pos())
    QtCore.QTimer.singleShot(0, lambda: _release_closed_menu(weakref.ref(menu)))
    return result


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
