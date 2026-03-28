try:
    from PySide2 import QtCore, QtGui, QtWidgets
except ImportError:
    from PySide6 import QtCore, QtGui, QtWidgets

import TheKeyMachine.mods.mediaMod as media
import TheKeyMachine.mods.settingsMod as settings
from TheKeyMachine.tools.common import ToolbarWindowToggle
from TheKeyMachine.tools.attribute_switcher.common import (
    ATTRIBUTE_SWITCHER_GEOMETRY_KEY,
    ATTRIBUTE_SWITCHER_SETTINGS_NAMESPACE,
    ATTRIBUTE_SWITCHER_STAYS_ON_TOP_KEY,
)
from TheKeyMachine.tools.attribute_switcher.customDialogs import AttributeSwitcherWindow
from TheKeyMachine.widgets import customWidgets as widgets, util

_attribute_switcher_instance = None


class AttributeSwitcherWindowBus(QtCore.QObject):
    stateChanged = QtCore.Signal(bool)


attribute_switcher_window_bus = AttributeSwitcherWindowBus()


def _parent_widget():
    return util.get_maya_qt(qt=QtWidgets.QWidget)


def _emit_attribute_switcher_window_state(is_open):
    try:
        attribute_switcher_window_bus.stateChanged.emit(bool(is_open))
    except Exception:
        pass


def _attribute_switcher_stays_on_top():
    return settings.get_setting(ATTRIBUTE_SWITCHER_STAYS_ON_TOP_KEY, False, namespace=ATTRIBUTE_SWITCHER_SETTINGS_NAMESPACE)


def get_attribute_switcher_window():
    global _attribute_switcher_instance
    if _attribute_switcher_instance and util.is_valid_widget(_attribute_switcher_instance):
        return _attribute_switcher_instance
    _attribute_switcher_instance = None
    return None


def is_attribute_switcher_window_open():
    dlg = get_attribute_switcher_window()
    return bool(dlg and dlg.isVisible())


def _get_attribute_switcher_toolbar_button():
    button = getattr(attribute_switcher_toolbar_toggle, "_button", None)
    if button and util.is_valid_widget(button) and button.isVisible():
        return button
    return None


def close_attribute_switcher_window():
    global _attribute_switcher_instance
    dlg = get_attribute_switcher_window()
    if dlg and util.is_valid_widget(dlg):
        dlg.close()
    _attribute_switcher_instance = None
    _emit_attribute_switcher_window_state(False)


def attribute_switcher_window(reuse_existing=True, popup=True, anchor_to_toolbar=False):
    global _attribute_switcher_instance
    dlg = get_attribute_switcher_window()
    if reuse_existing and dlg and util.is_valid_widget(dlg):
        if not dlg.isVisible():
            dlg.show()
        dlg.setWindowFlag(QtCore.Qt.WindowStaysOnTopHint, _attribute_switcher_stays_on_top())
        dlg.show()
        if anchor_to_toolbar:
            dlg.place_above_toolbar_button(_get_attribute_switcher_toolbar_button(), gap=util.DPI(18))
        elif popup:
            dlg.place_near_cursor()
        dlg.raise_()
        dlg.activateWindow()
        _emit_attribute_switcher_window_state(True)
        return dlg

    close_attribute_switcher_window()

    dlg = AttributeSwitcherWindow(parent=_parent_widget(), popup=popup)
    dlg.setWindowFlag(QtCore.Qt.WindowStaysOnTopHint, _attribute_switcher_stays_on_top())
    dlg.show()
    if anchor_to_toolbar:
        dlg.place_above_toolbar_button(_get_attribute_switcher_toolbar_button(), gap=util.DPI(18))
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
    settings.set_setting(ATTRIBUTE_SWITCHER_GEOMETRY_KEY, None, namespace=ATTRIBUTE_SWITCHER_SETTINGS_NAMESPACE)
    dlg = get_attribute_switcher_window()
    if dlg and util.is_valid_widget(dlg):
        dlg.place_above_toolbar_button(_get_attribute_switcher_toolbar_button(), gap=util.DPI(18))


def _set_attribute_switcher_stays_on_top(enabled):
    settings.set_setting(ATTRIBUTE_SWITCHER_STAYS_ON_TOP_KEY, bool(enabled), namespace=ATTRIBUTE_SWITCHER_SETTINGS_NAMESPACE)
    dlg = get_attribute_switcher_window()
    if dlg and util.is_valid_widget(dlg):
        dlg.setWindowFlag(QtCore.Qt.WindowStaysOnTopHint, bool(enabled))
        dlg.show()
        dlg.raise_()
        dlg.activateWindow()


def build_attribute_switcher_context_menu(parent=None):
    menu = widgets.OpenMenuWidget(parent)

    stays_on_top_action = menu.addAction(
        QtGui.QIcon(media.settings_image),
        "Stay on Top",
        description="Keep the floating Attribute Switcher window above other Maya windows.",
    )
    stays_on_top_action.setCheckable(True)
    stays_on_top_action.setChecked(_attribute_switcher_stays_on_top())
    stays_on_top_action.triggered.connect(_set_attribute_switcher_stays_on_top)

    restore_position_action = menu.addAction(
        QtGui.QIcon(media.attribute_switcher_image),
        "Restore Position",
        description="Reset the Attribute Switcher position above its toolbar button.",
    )
    restore_position_action.triggered.connect(lambda *_: restore_attribute_switcher_default_position())

    return menu


def _show_attribute_switcher_toolbar_context_menu(button, pos):
    menu = build_attribute_switcher_context_menu(parent=button)
    exec_fn = getattr(menu, "exec", None) or getattr(menu, "exec_", None)
    exec_fn(button.mapToGlobal(pos))


def bind_attribute_switcher_toolbar_button(button):
    attribute_switcher_toolbar_toggle.attach_button(button)
    if button:
        try:
            button.customContextMenuRequested.disconnect()
        except Exception:
            pass
        button.setContextMenuPolicy(QtCore.Qt.CustomContextMenu)
        button.customContextMenuRequested.connect(lambda pos, b=button: _show_attribute_switcher_toolbar_context_menu(b, pos))


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
