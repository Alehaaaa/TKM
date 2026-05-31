from TheKeyMachine.Qt import QtCore, QtGui, QtWidgets

from TheKeyMachine.data import icons
import TheKeyMachine.mods.settingsMod as settings
import TheKeyMachine.core.runtimeManager as runtime
from TheKeyMachine.tools import common as toolCommon
from TheKeyMachine.tools.common import ToolbarWindowToggle
from TheKeyMachine.tools.attribute_switcher.common import (
    ATTRIBUTE_SWITCHER_GEOMETRY_KEY,
    ATTRIBUTE_SWITCHER_SETTINGS_NAMESPACE,
    ATTRIBUTE_SWITCHER_STAYS_ON_TOP_KEY,
)
from TheKeyMachine.tools.attribute_switcher.customDialogs import AttributeSwitcherWindow
import TheKeyMachine.tools.gimbal_fixer.api as gimbalFixerApi
from TheKeyMachine.widgets import customWidgets as widgets, util as wutil

# Public API surface
__all__ = [
    "attribute_switcher_window",
    "close_attribute_switcher_window",
    "toggle_attribute_switcher_window",
    "show",
    "popup",
    "is_euler_filter_enabled",
    "set_euler_filter_enabled",
    "is_stay_on_top",
    "set_stay_on_top",
    "bind_attribute_switcher_toolbar_button",
]

_attribute_switcher_instance = None
attribute_switcher_window_bus = toolCommon.WindowStateBus()


def _parent_widget():
    return wutil.get_maya_qt(qt=QtWidgets.QWidget)


def _emit_attribute_switcher_window_state(is_open):
    try:
        attribute_switcher_window_bus.stateChanged.emit(bool(is_open))
    except Exception:
        pass


def is_stay_on_top():
    """Return whether the Attribute Switcher window is set to stay on top."""
    return settings.get_setting(
        ATTRIBUTE_SWITCHER_STAYS_ON_TOP_KEY,
        False,
        namespace=ATTRIBUTE_SWITCHER_SETTINGS_NAMESPACE,
    )


def is_euler_filter_enabled():
    """Return the current euler‑filter setting for the Attribute Switcher."""
    return bool(
        settings.get_setting(
            "euler_filter", True, namespace=ATTRIBUTE_SWITCHER_SETTINGS_NAMESPACE
        )
    )


def emit_attribute_switcher_euler_filter_state():
    try:
        runtime.get_runtime_manager().eulerFilterChanged.emit(is_euler_filter_enabled())
    except Exception:
        pass


def bind_attribute_switcher_euler_filter_toggle(widget):
    if widget is None:
        return
    def _sync(enabled):
        try:
            if not wutil.is_valid_widget(widget):
                return
        except Exception:
            pass
        toolCommon.set_checked_safely(widget, bool(enabled))
    toolCommon.set_checked_safely(widget, is_euler_filter_enabled())
    toolCommon.replace_tracked_connection(
        widget,
        "_tkm_attribute_switcher_euler_filter_sync_relay",
        runtime.get_runtime_manager().eulerFilterChanged,
        _sync,
        parent=widget,
    )


def set_euler_filter_enabled(enabled):
    settings.set_setting(
        "euler_filter", bool(enabled), namespace=ATTRIBUTE_SWITCHER_SETTINGS_NAMESPACE
    )
    dlg = get_attribute_switcher_window()
    if dlg and wutil.is_valid_widget(dlg):
        try:
            dlg.euler_filter = bool(enabled)
        except Exception:
            pass
    emit_attribute_switcher_euler_filter_state()


def get_attribute_switcher_window():
    global _attribute_switcher_instance
    if (
        _attribute_switcher_instance
        and wutil.is_valid_widget(_attribute_switcher_instance)
    ):
        return _attribute_switcher_instance
    _attribute_switcher_instance = None
    return None


def is_attribute_switcher_window_open():
    dlg = get_attribute_switcher_window()
    return bool(dlg and dlg.isVisible())


def _get_attribute_switcher_toolbar_button():
    button = getattr(attribute_switcher_toolbar_toggle, "_button", None)
    if button and wutil.is_valid_widget(button) and button.isVisible():
        return button
    return None


def close_attribute_switcher_window():
    global _attribute_switcher_instance
    dlg = get_attribute_switcher_window()
    if dlg and wutil.is_valid_widget(dlg):
        dlg.close()
    _attribute_switcher_instance = None
    _emit_attribute_switcher_window_state(False)


def attribute_switcher_window(reuse_existing=True, popup=True, anchor_to_toolbar=False):
    global _attribute_switcher_instance
    dlg = get_attribute_switcher_window()
    if reuse_existing and dlg and wutil.is_valid_widget(dlg):
        if not dlg.isVisible():
            dlg.show()
        dlg.setWindowFlag(QtCore.Qt.WindowStaysOnTopHint, is_stay_on_top())
        dlg.show()
        if anchor_to_toolbar:
            dlg.place_above_toolbar_button(_get_attribute_switcher_toolbar_button(), gap=wutil.DPI(18))
        elif popup:
            dlg.place_near_cursor()
        dlg.raise_()
        dlg.activateWindow()
        _emit_attribute_switcher_window_state(True)
        return dlg
    close_attribute_switcher_window()
    dlg = AttributeSwitcherWindow(parent=_parent_widget(), popup=popup)
    dlg.setWindowFlag(QtCore.Qt.WindowStaysOnTopHint, is_stay_on_top())
    dlg.show()
    if anchor_to_toolbar:
        dlg.place_above_toolbar_button(_get_attribute_switcher_toolbar_button(), gap=wutil.DPI(18))
    elif popup:
        dlg.place_near_cursor()
    def _on_destroyed(*_):
        global _attribute_switcher_instance
        _attribute_switcher_instance = None
        _emit_attribute_switcher_window_state(False)
    dlg.destroyed.connect(_on_destroyed)
    _attribute_switcher_instance = dlg
    _emit_attribute_switcher_window_state(True)
    return dlg


attribute_switcher_toolbar_toggle = ToolbarWindowToggle(
    is_attribute_switcher_window_open,
    lambda: attribute_switcher_window(reuse_existing=True, popup=False, anchor_to_toolbar=True),
    close_attribute_switcher_window,
    attribute_switcher_window_bus.stateChanged,
)


def restore_attribute_switcher_default_position():
    settings.set_setting(
        ATTRIBUTE_SWITCHER_GEOMETRY_KEY, None, namespace=ATTRIBUTE_SWITCHER_SETTINGS_NAMESPACE
    )
    dlg = get_attribute_switcher_window()
    if dlg and wutil.is_valid_widget(dlg):
        dlg.place_above_toolbar_button(_get_attribute_switcher_toolbar_button(), gap=wutil.DPI(18))


def set_stay_on_top(enabled):
    settings.set_setting(
        ATTRIBUTE_SWITCHER_STAYS_ON_TOP_KEY,
        bool(enabled),
        namespace=ATTRIBUTE_SWITCHER_SETTINGS_NAMESPACE,
    )
    dlg = get_attribute_switcher_window()
    if dlg and wutil.is_valid_widget(dlg):
        dlg.setWindowFlag(QtCore.Qt.WindowStaysOnTopHint, bool(enabled))
        dlg.show()
        dlg.raise_()
        dlg.activateWindow()


def build_attribute_switcher_context_menu(parent=None):
    menu = widgets.OpenMenuWidget(parent)
    menu.addAction(
        QtGui.QIcon(icons.reblock),
        "Gimbal Fixer",
        description="Open the Gimbal Fixer rotation-order analyzer.",
        callback=lambda *_: gimbalFixerApi.gimbal_fixer_window(),
    )

    menu.addSeparator()

    stays_on_top_action = menu.addAction(
        QtGui.QIcon(icons.settings),
        "Stay on Top",
        description="Keep the floating Attribute Switcher window above other Maya windows.",
    )
    toolCommon.connect_checkable_action(
        stays_on_top_action, is_stay_on_top, set_stay_on_top
    )
    restore_position_action = menu.addAction(
        QtGui.QIcon(icons.attribute_switcher),
        "Restore Position",
        description="Reset the Attribute Switcher position above its toolbar button.",
    )
    toolCommon.connect_action(
        restore_position_action, lambda *_: restore_attribute_switcher_default_position()
    )
    return menu


def bind_attribute_switcher_toolbar_button(button):
    """Bind a toolbar button to the Attribute Switcher toggle using the shared helper."""
    from TheKeyMachine.tools.common_toolbar_utils import bind_toolbar_button_common
    bind_toolbar_button_common(
        attribute_switcher_toolbar_toggle,
        button,
        "_tkm_attribute_switcher_context_menu_slot",
        lambda parent: build_attribute_switcher_context_menu(parent=parent),
    )


def toggle_attribute_switcher_window():
    if attribute_switcher_toolbar_toggle:
        attribute_switcher_toolbar_toggle.toggle()
    elif is_attribute_switcher_window_open():
        close_attribute_switcher_window()
    else:
        attribute_switcher_window(reuse_existing=True, popup=False, anchor_to_toolbar=True)


def show():
    return attribute_switcher_window(reuse_existing=False, popup=False)


def popup():
    return attribute_switcher_window(reuse_existing=False, popup=True)
