"""Orbit tool public API.

Provides functions to open/close the Orbit window, toggle settings, and bind the toolbar button. The module has been refactored for clearer naming and a shared binding utility.
"""

__all__ = [
    "orbit_window",
    "close_orbit_window",
    "toggle_orbit_window",
    "set_orbit_auto_transparency",
    "set_orbit_stay_on_top",
    "bind_orbit_toolbar_button",
]

from maya import cmds

try:
    from PySide2 import QtCore, QtGui, QtWidgets  # type: ignore
except ImportError:
    from PySide6 import QtCore, QtGui, QtWidgets  # type: ignore

from TheKeyMachine.data import icons
from TheKeyMachine.core import trigger
import TheKeyMachine.mods.settingsMod as settings
from TheKeyMachine.tools.common import ToolbarWindowToggle
from TheKeyMachine.tools import common as toolCommon
from TheKeyMachine.widgets import customWidgets as cw, util as wutil

ORBIT_SETTINGS_NAMESPACE = "orbit_window"
ORBIT_AUTO_TRANSPARENCY_KEY = "orbit_auto_transparency"
ORBIT_BUTTON_CONFIGURATION_KEY = "button_configuration"

def _window_class():
    from TheKeyMachine.tools.orbit.customDialogs import OrbitWindow
    return OrbitWindow

# Default actions for the Orbit toolbar
DEFAULT_ORBIT_ACTIONS = (
    "default_object_values",
    "delete_all_animation",
    "select_opposite",
    "opposite_copy",
    "mirror",
    "select_hierarchy",
    "isolate_master",
)

# Define the list of available orbit actions used throughout the module.
ORBIT_ACTIONS = (
    "align_objects",
    "create_tracer",
    "default_object_values",
    "delete_all_animation",
    "select_opposite",
    "opposite_copy",
    "mirror",
    "copy_animation",
    "paste_animation",
    "paste_insert_animation",
    "copy_pose",
    "paste_pose",
    "select_hierarchy",
    "link_copy",
    "temp_pivot",
    "ws_copy_frame",
    "ws_paste_frame",
)
ORBIT_ACTION_SET = set(ORBIT_ACTIONS)
ORBIT_ACTION_MIGRATIONS = {
    "copy_opposite": "opposite_copy",
}

DEFAULT_ORBIT_CONFIGURATION = {
    "button{}".format(index): action_identifier for index, action_identifier in enumerate(DEFAULT_ORBIT_ACTIONS, start=1)
}

def _orbit_button_sort_key(button_id):
    suffix = str(button_id).replace("button", "")
    return int(suffix) if suffix.isdigit() else 9999

def sanitize_orbit_configuration(config):
    sanitized = {}
    seen_actions = set()

    for button_id in sorted(config.keys(), key=_orbit_button_sort_key):
        if not str(button_id).startswith("button"):
            continue
        action_identifier = config.get(button_id, "")
        action_identifier = ORBIT_ACTION_MIGRATIONS.get(action_identifier, action_identifier)
        if action_identifier not in ORBIT_ACTION_SET or action_identifier in seen_actions:
            continue
        sanitized[button_id] = action_identifier
        seen_actions.add(action_identifier)

    return sanitized

def execute_action(action_identifier):
    if action_identifier not in ORBIT_ACTION_SET or not trigger.has_command(action_identifier):
        return

    chunk_opened = False
    try:
        chunk_opened = toolCommon.open_undo_chunk()
        trigger.invoke(action_identifier)
    finally:
        if chunk_opened:
            toolCommon.close_undo_chunk()

def save_orbit_button_config():
    sanitized = sanitize_orbit_configuration(orbit_configuration)
    settings.set_setting(
        ORBIT_BUTTON_CONFIGURATION_KEY,
        sanitized,
        namespace=ORBIT_SETTINGS_NAMESPACE,
    )

def load_orbit_configuration():
    config = dict(DEFAULT_ORBIT_CONFIGURATION)
    stored_config = settings.get_setting(
        ORBIT_BUTTON_CONFIGURATION_KEY,
        None,
        namespace=ORBIT_SETTINGS_NAMESPACE,
    )

    if isinstance(stored_config, dict):
        config.update(sanitize_orbit_configuration(stored_config))
    else:
        stored_config = None

    sanitized = sanitize_orbit_configuration(config)
    if stored_config != sanitized:
        settings.set_setting(
            ORBIT_BUTTON_CONFIGURATION_KEY,
            sanitized,
            namespace=ORBIT_SETTINGS_NAMESPACE,
        )

    return sanitized

orbit_configuration = load_orbit_configuration()
orbit_window_bus = toolCommon.WindowStateBus()

def _parent_widget():
    return wutil.get_maya_qt(qt=QtWidgets.QWidget)

def _emit_orbit_window_state(is_open: bool) -> None:
    """Emit the window state change via the bus.

    Args:
        is_open: True if the Orbit window is now open, False otherwise.
    """
    orbit_window_bus.stateChanged.emit(bool(is_open))

def get_orbit_window():
    window_class = _window_class()
    for widget in QtWidgets.QApplication.topLevelWidgets():
        if isinstance(widget, window_class) and wutil.is_valid_widget(widget):
            return widget
    return None

def is_orbit_window_open():
    win = get_orbit_window()
    return bool(win and win.isVisible())

def close_orbit_window():
    win = get_orbit_window()
    maya_window_closed = False
    if cmds.window("orbit_window", exists=True):
        cmds.deleteUI("orbit_window")
        maya_window_closed = True

    if win and wutil.is_valid_widget(win):
        win.close()
    elif maya_window_closed:
        _emit_orbit_window_state(False)

def orbit_window(*args, offset_x=0, offset_y=0, rebuild=False, reuse_existing=False):
    existing_win = get_orbit_window()
    if reuse_existing and not rebuild and offset_x == 0 and offset_y == 0 and existing_win:
        if not existing_win.isVisible():
            existing_win.show()
        existing_win.apply_stay_on_top_setting()
        existing_win.raise_()
        existing_win.activateWindow()
        _emit_orbit_window_state(True)
        return existing_win

    if cmds.window("orbit_window", exists=True):
        cmds.deleteUI("orbit_window")

    win = _window_class()(parent=_parent_widget(), offset_x=offset_x, offset_y=offset_y, rebuild=rebuild)

    def _on_destroyed(*_):
        _emit_orbit_window_state(False)

    win.destroyed.connect(_on_destroyed)
    win.show()
    _emit_orbit_window_state(True)
    return win

orbit_toolbar_toggle = ToolbarWindowToggle(
    is_orbit_window_open,
    lambda: orbit_window(reuse_existing=True),
    close_orbit_window,
    orbit_window_bus.stateChanged,
)

def _orbit_auto_transparency_enabled():
    """Return whether auto‑transparency is enabled for the Orbit palette."""
    return settings.get_setting(
        ORBIT_AUTO_TRANSPARENCY_KEY,
        False,
        namespace=ORBIT_SETTINGS_NAMESPACE,
    )

def _set_orbit_auto_transparency_enabled(enabled: bool):
    """Enable or disable auto‑transparency and update the window if open."""
    settings.set_setting(
        ORBIT_AUTO_TRANSPARENCY_KEY,
        bool(enabled),
        namespace=ORBIT_SETTINGS_NAMESPACE,
    )
    win = get_orbit_window()
    if win and wutil.is_valid_widget(win):
        win.update_transparency_state(bool(enabled))

def _orbit_stays_on_top():
    """Return whether the Orbit window should stay on top."""
    return settings.get_setting(
        "orbit_stay_on_top",
        False,
        namespace=ORBIT_SETTINGS_NAMESPACE,
    )

def _set_orbit_stays_on_top(enabled: bool):
    """Set stay‑on‑top setting and apply to window if open."""
    settings.set_setting(
        "orbit_stay_on_top",
        bool(enabled),
        namespace=ORBIT_SETTINGS_NAMESPACE,
    )
    win = get_orbit_window()
    if win and wutil.is_valid_widget(win):
        win.apply_stay_on_top_setting()

def _get_orbit_toolbar_button():
    """Return the Orbit toolbar button widget if visible."""
    button = getattr(orbit_toolbar_toggle, "_button", None)
    if button and wutil.is_valid_widget(button) and button.isVisible():
        return button
    return None

def restore_orbit_default_position():
    """Reset the floating Orbit window to its default geometry."""
    settings.set_setting(
        "orbit_geometry",
        None,
        namespace=ORBIT_SETTINGS_NAMESPACE,
    )
    win = get_orbit_window()
    if win and wutil.is_valid_widget(win):
        win.place_above_toolbar_button(_get_orbit_toolbar_button())

def build_orbit_context_menu(parent=None):
    menu = cw.OpenMenuWidget(parent)

    auto_transparency_action = menu.addAction(
        QtGui.QIcon(icons.orbit_ui),
        "Auto Transparency",
        description="Make the floating Orbit tool palette translucent when the cursor is not over it.",
    )
    toolCommon.connect_checkable_action(
        auto_transparency_action,
        _orbit_auto_transparency_enabled,
        _set_orbit_auto_transparency_enabled,
    )

    menu.addSeparator()

    stays_on_top_action = menu.addAction(
        QtGui.QIcon(icons.settings),
        "Stay on Top",
        description="Keep the floating Orbit tool palette above other Maya windows.",
    )
    toolCommon.connect_checkable_action(stays_on_top_action, _orbit_stays_on_top, _set_orbit_stays_on_top)

    restore_position_action = menu.addAction(
        QtGui.QIcon(icons.orbit_ui),
        "Restore Position",
        description="Reset the floating Orbit tool palette to its default position above the Orbit toolbar button.",
    )
    toolCommon.connect_action(restore_position_action, lambda *_: restore_orbit_default_position())

    return menu

def bind_orbit_toolbar_button(button):
    """Bind a toolbar button to the Orbit toggle using the shared helper."""
    from TheKeyMachine.tools.common_toolbar_utils import bind_toolbar_button_common

    bind_toolbar_button_common(
        orbit_toolbar_toggle,
        button,
        "_tkm_orbit_context_menu_slot",
        lambda parent: build_orbit_context_menu(parent=parent),
    )

def toggle_orbit_window():
    """Toggle the Orbit window via the toolbar toggle."""
    if orbit_toolbar_toggle:
        orbit_toolbar_toggle.toggle()
    elif is_orbit_window_open():
        close_orbit_window()
    else:
        orbit_window(reuse_existing=True)

set_orbit_auto_transparency = _set_orbit_auto_transparency_enabled
set_orbit_stay_on_top = _set_orbit_stays_on_top
