"""Public API for the Search tool."""

from TheKeyMachine.Qt import QtWidgets  # type: ignore

import TheKeyMachine.core.runtimeManager as runtime
from TheKeyMachine.tools import common as toolCommon
from TheKeyMachine.tools.common import ToolbarWindowToggle
from TheKeyMachine.tools.search.constants import SEARCH_WINDOW_KEY
from TheKeyMachine.widgets import util as wutil


__all__ = [
    "show_search_window",
    "close_search_window",
    "toggle_search_window",
    "set_search_window_open",
    "is_search_window_open",
    "bind_search_toolbar_button",
    "get_search_window",
]


search_window_bus = toolCommon.WindowStateBus()


def _emit_search_window_state(is_open):
    state = bool(is_open)
    search_window_bus.stateChanged.emit(state)
    runtime.get_runtime_manager().set_tool_state("search", state)


def _window_class():
    from TheKeyMachine.tools.search.custom_dialogs import SearchDialog

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


def show_search_window(*_args):
    existing = get_search_window()
    if existing:
        existing.focus_search()
        _emit_search_window_state(True)
        return existing

    manager = runtime.get_runtime_manager()
    dialog = _window_class()(parent=wutil.get_maya_qt())
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
)


def toggle_search_window(*_args):
    return search_toolbar_toggle.toggle()


def bind_search_toolbar_button(button):
    connect_window_toggle = getattr(button, "connect_window_toggle", None)
    if callable(connect_window_toggle):
        connect_window_toggle(search_toolbar_toggle)
    else:
        search_toolbar_toggle.attach_button(button)
    return True
