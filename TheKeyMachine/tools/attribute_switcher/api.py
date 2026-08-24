from functools import partial

from TheKeyMachine.core.Qt import QtCore, QtGui, QtWidgets

from TheKeyMachine.data import icons
from TheKeyMachine.core import i18n, settings
from TheKeyMachine.core import runtime
from TheKeyMachine.tools import common as toolCommon
from TheKeyMachine.tools.common import ToolbarWindowToggle
from TheKeyMachine.tools.attribute_switcher.controller import (
    ATTRIBUTE_SWITCHER_SETTINGS_NAMESPACE,
    ATTRIBUTE_SWITCHER_STAYS_ON_TOP_KEY,
    SUPER_MODE_KEY,
)
import TheKeyMachine.tools.gimbal_fixer.api as gimbalFixerApi
from TheKeyMachine.ui.widgets import customWidgets as widgets, util as wutil

# Public API surface
__all__ = [
    "attribute_switcher_window",
    "close_attribute_switcher_window",
    "toggle_window",
    "show",
    "popup",
    "is_euler_filter_enabled",
    "set_euler_filter_enabled",
    "is_stay_on_top",
    "set_stay_on_top",
    "is_super_mode_enabled",
    "set_super_mode_enabled",
    "bind_attribute_switcher_toolbar_button",
]

_attribute_switcher_instance = None
attribute_switcher_window_bus = toolCommon.WindowStateBus()


def _window_class():
    from TheKeyMachine.tools.attribute_switcher.widgets import AttributeSwitcherWindow

    return AttributeSwitcherWindow


def _emit_attribute_switcher_window_state(is_open):
    state = bool(is_open)
    try:
        attribute_switcher_window_bus.stateChanged.emit(state)
    except Exception:
        pass
    runtime.get_runtime_manager().set_tool_state("attribute_switcher", state)


def is_stay_on_top():
    """Return whether the Attribute Switcher window is set to stay on top."""
    return settings.get_setting(
        ATTRIBUTE_SWITCHER_STAYS_ON_TOP_KEY,
        False,
        namespace=ATTRIBUTE_SWITCHER_SETTINGS_NAMESPACE,
    )


def is_super_mode_enabled():
    """Return whether rotate order conversion uses the fast, math-only path.

    Off by default (Normal mode): the frame-by-frame, world-matrix-
    preserving conversion that works with every rig. Super mode skips
    that for eligible controls and converts keyed rotations with pure
    Euler math instead, at the cost of automatically falling back to
    Normal for rigs it can't safely fast-path (animation layers, driven
    keys, expressions).
    """
    return bool(
        settings.get_setting(
            SUPER_MODE_KEY,
            False,
            namespace=ATTRIBUTE_SWITCHER_SETTINGS_NAMESPACE,
        )
    )


def set_super_mode_enabled(enabled):
    """Switch the Attribute Switcher between Normal and Super modes."""
    settings.set_setting(
        SUPER_MODE_KEY,
        bool(enabled),
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
    state = is_euler_filter_enabled()
    try:
        runtime.get_runtime_manager().eulerFilterChanged.emit(state)
    except Exception:
        pass
    runtime.get_runtime_manager().set_tool_state("attribute_switcher_euler_filter", state)


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


def close_attribute_switcher_window():
    dlg = get_attribute_switcher_window()
    if dlg and wutil.is_valid_widget(dlg):
        dlg.close()
    _emit_attribute_switcher_window_state(False)


def attribute_switcher_window(reuse_existing=True, popup=True, anchor_button=None):
    global _attribute_switcher_instance
    dlg = get_attribute_switcher_window()
    if not (reuse_existing and dlg and wutil.is_valid_widget(dlg)):
        close_attribute_switcher_window()
        dlg = _window_class()(parent=wutil.get_maya_qt(qt=QtWidgets.QWidget), popup=popup)

        created_dialog = dlg

        def _on_destroyed(*_):
            global _attribute_switcher_instance
            if _attribute_switcher_instance is not created_dialog:
                return
            _attribute_switcher_instance = None
            _emit_attribute_switcher_window_state(False)

        dlg.destroyed.connect(_on_destroyed)
        _attribute_switcher_instance = dlg
    else:
        # closeEvent disables auto-close, but the widget is intentionally
        # reusable. Restore its requested mode before refresh sizes the footer.
        dlg.set_popup_mode(popup)
        dlg._connect_runtime_manager()
        dlg.refresh()

    dlg.setWindowFlag(QtCore.Qt.WindowStaysOnTopHint, is_stay_on_top())
    if anchor_button and wutil.is_valid_widget(anchor_button):
        dlg.present_above_toolbar_button(anchor_button)
    elif popup:
        dlg.present_beside_cursor()
    else:
        dlg.present_floating_window()

    _emit_attribute_switcher_window_state(True)
    return dlg


attribute_switcher_toolbar_toggle = ToolbarWindowToggle(
    is_attribute_switcher_window_open,
    lambda anchor_button=None: attribute_switcher_window(
        reuse_existing=True,
        popup=True,
        anchor_button=anchor_button,
    ),
    close_attribute_switcher_window,
    attribute_switcher_window_bus.stateChanged,
    tool_id="attribute_switcher",
)


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


def _set_rotate_order_mode(checked, super_mode):
    # Checkable actions in an exclusive QActionGroup both re-emit their
    # toggle when the selection changes -- the one being unchecked as well
    # as the one being checked -- so only act on the action actually being
    # turned on.
    if checked:
        set_super_mode_enabled(super_mode)


def _add_rotate_order_mode_actions(menu):
    """Normal vs Super mode, as an exclusive choice.

    Covers every switch the Attribute Switcher can apply, not just rotate
    order: Super mode skips per-frame evaluation with pure math wherever
    it's safe to do so (rotate order always; other switches only for plain,
    default-pivot, non-joint transforms), falling back to Normal mode for
    anything it can't safely fast-path.
    """
    from TheKeyMachine.core import i18n

    super_mode_enabled = is_super_mode_enabled()

    section_label, _desc, _tooltip = i18n.localize_menu_action(
        "rotate_order_section", __file__, "Switch Speed"
    )
    menu.addSection(section_label)

    group = QtGui.QActionGroup(menu)
    group.setExclusive(True)

    normal_label, normal_description, normal_tooltip = i18n.localize_menu_action(
        "rotate_order_normal_mode",
        __file__,
        "Normal Mode",
        description="Preserve world position and orientation by evaluating the scene at every keyframe.",
        tooltip="Slower, but safe for every rig and switchable attribute. This includes animation layers, driven keys, expressions, and joints.",
    )
    normal_action = menu.addAction(
        normal_label,
        description=normal_description,
        tooltip=normal_tooltip,
        callback=toolCommon.mark_non_tool_action(
            partial(_set_rotate_order_mode, super_mode=False)
        ),
    )
    normal_action.setCheckable(True)
    normal_action.setChecked(not super_mode_enabled)
    group.addAction(normal_action)

    super_label, super_description, super_tooltip = i18n.localize_menu_action(
        "rotate_order_super_mode",
        __file__,
        "Super Mode",
        description="Skip per-frame evaluation with pure math wherever it's safe to do so.",
        tooltip="Much faster. Automatically falls back to Normal Mode for anything it can't safely fast-path (joints, custom pivots, animation layers, driven keys, expressions).",
    )
    super_action = menu.addAction(
        super_label,
        description=super_description,
        tooltip=super_tooltip,
        callback=toolCommon.mark_non_tool_action(
            partial(_set_rotate_order_mode, super_mode=True)
        ),
    )
    super_action.setCheckable(True)
    super_action.setChecked(super_mode_enabled)
    group.addAction(super_action)

    return group


def build_attribute_switcher_context_menu(parent=None):
    menu = widgets.OpenMenuWidget(parent)
    menu.addAction(
        QtGui.QIcon(icons.reblock),
        i18n.tr_text("Gimbal Fixer"),
        description=i18n.tr_text("Open the Gimbal Fixer rotation-order analyzer."),
        callback=lambda *_: gimbalFixerApi.show_gimbal_fixer_window(),
    )

    menu.addSeparator()

    _add_rotate_order_mode_actions(menu)

    menu.addSeparator()

    toolCommon.add_floating_window_actions(
        menu,
        is_stay_on_top,
        set_stay_on_top,
    )
    return menu


def bind_attribute_switcher_toolbar_button(button):
    button.connect_window_toggle(
        attribute_switcher_toolbar_toggle,
        context_attr="_tkm_attribute_switcher_context_menu_slot",
        menu_factory=lambda parent: build_attribute_switcher_context_menu(parent=parent),
    )
    return True


def toggle_window(checked=None, *_args):
    if isinstance(checked, bool):
        return (
            attribute_switcher_window(reuse_existing=True, popup=True)
            if checked
            else close_attribute_switcher_window()
        )
    if attribute_switcher_toolbar_toggle:
        return attribute_switcher_toolbar_toggle.toggle()
    elif is_attribute_switcher_window_open():
        return close_attribute_switcher_window()
    return attribute_switcher_window(reuse_existing=True, popup=True)


def show():
    return attribute_switcher_window(reuse_existing=True, popup=False)


def popup():
    return attribute_switcher_window(reuse_existing=True, popup=True)
