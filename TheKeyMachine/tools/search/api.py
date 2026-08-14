"""Public API for the Search tool."""

from TheKeyMachine.core.Qt import QtCore, QtWidgets  # type: ignore

from TheKeyMachine.core import runtime
from TheKeyMachine.core import settings
from TheKeyMachine.tools import common as toolCommon
from TheKeyMachine.tools.common import ToolbarWindowToggle
from TheKeyMachine.tools.search.controller import (
    SEARCH_SETTINGS_NAMESPACE,
    SEARCH_STAYS_ON_TOP_KEY,
    SEARCH_WINDOW_KEY,
)
from TheKeyMachine.tools.search import controller
from TheKeyMachine.ui.widgets import customWidgets as cw, util as wutil


__all__ = [
    "show_search_window",
    "close_search_window",
    "toggle",
    "set_search_window_open",
    "is_search_window_open",
    "bind_search_toolbar_button",
    "get_search_window",
    "is_search_stays_on_top",
    "set_search_stays_on_top",
    "restore_search_default_position",
]


search_window_bus = toolCommon.WindowStateBus()


def _emit_search_window_state(is_open):
    state = bool(is_open)
    search_window_bus.stateChanged.emit(state)
    runtime.get_runtime_manager().set_tool_state("search", state)


def _window_class():
    from TheKeyMachine.tools.search.widgets import SearchDialog

    return SearchDialog


def get_search_window():
    manager = runtime.get_runtime_manager()
    existing = getattr(manager, "_managed_widgets", {}).get(SEARCH_WINDOW_KEY)
    if existing and wutil.is_valid_widget(existing, _window_class()):
        return existing

    window_class = _window_class()
    for widget in QtWidgets.QApplication.topLevelWidgets():
        if isinstance(widget, window_class) and wutil.is_valid_widget(widget):
            return widget
    return None


def is_search_window_open():
    window = get_search_window()
    return bool(window and window.isVisible())


def is_search_stays_on_top():
    return bool(
        settings.get_setting(
            SEARCH_STAYS_ON_TOP_KEY,
            False,
            namespace=SEARCH_SETTINGS_NAMESPACE,
        )
    )


def set_search_stays_on_top(enabled):
    settings.set_setting(
        SEARCH_STAYS_ON_TOP_KEY,
        bool(enabled),
        namespace=SEARCH_SETTINGS_NAMESPACE,
    )
    window = get_search_window()
    if not window:
        return
    was_visible = window.isVisible()
    geometry = window.geometry()
    window.setWindowFlag(QtCore.Qt.WindowStaysOnTopHint, bool(enabled))
    window.setGeometry(geometry)
    if was_visible:
        window.focus_search()


def restore_search_default_position():
    controller.clear_position()
    window = get_search_window()
    if window:
        window.restore_default_position()


def build_search_context_menu(parent=None):
    menu = cw.OpenMenuWidget(parent)
    toolCommon.add_floating_window_actions(
        menu,
        is_search_stays_on_top,
        set_search_stays_on_top,
        restore_search_default_position,
    )
    return menu


def show_search_window(*_args):
    existing = get_search_window()
    if existing:
        existing.focus_search()
        _emit_search_window_state(True)
        return existing

    manager = runtime.get_runtime_manager()
    dialog = _window_class()(parent=wutil.get_maya_qt())
    dialog.setWindowFlag(QtCore.Qt.WindowStaysOnTopHint, is_search_stays_on_top())
    manager.register_managed_widget(dialog, key=SEARCH_WINDOW_KEY)
    dialog.destroyed.connect(lambda *_: _emit_search_window_state(False))
    dialog.focus_search()
    _emit_search_window_state(True)
    return dialog


def close_search_window():
    window = get_search_window()
    if window:
        window.close()
        return True
    _emit_search_window_state(False)
    return False


def set_search_window_open(enabled):
    return show_search_window() if enabled else close_search_window()


search_toolbar_toggle = ToolbarWindowToggle(
    is_search_window_open,
    show_search_window,
    close_search_window,
    search_window_bus.stateChanged,
    tool_id="search_window",
)


def toggle(checked=None, *_args):
    if isinstance(checked, bool):
        return set_search_window_open(checked)
    return search_toolbar_toggle.toggle()


def bind_search_toolbar_button(button):
    button.connect_window_toggle(
        search_toolbar_toggle,
        context_attr="_tkm_search_context_menu_slot",
        menu_factory=lambda parent: build_search_context_menu(parent=parent),
    )
    return True
