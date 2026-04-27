from maya import cmds

try:
    from PySide2 import QtCore, QtGui, QtWidgets  # type: ignore
except ImportError:
    from PySide6 import QtCore, QtGui, QtWidgets  # type: ignore

import TheKeyMachine.core.trigger as trigger
import TheKeyMachine.mods.mediaMod as media
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


def _parent_widget():
    return wutil.get_maya_qt(qt=QtWidgets.QWidget)


def _emit_orbit_window_state(is_open):
    try:
        orbit_window_bus.stateChanged.emit(bool(is_open))
    except Exception:
        pass


def _orbit_auto_transparency_enabled():
    return settings.get_setting(ORBIT_AUTO_TRANSPARENCY_KEY, True, namespace=ORBIT_SETTINGS_NAMESPACE)


def _set_orbit_auto_transparency_enabled(enabled):
    settings.set_setting(ORBIT_AUTO_TRANSPARENCY_KEY, bool(enabled), namespace=ORBIT_SETTINGS_NAMESPACE)
    win = get_orbit_window()
    if win and wutil.is_valid_widget(win):
        win._auto_transparency = bool(enabled)
        win.update_transparency_state(win._hovered)


def _orbit_stays_on_top():
    return settings.get_setting("stays_on_top", False, namespace=ORBIT_SETTINGS_NAMESPACE)


def _set_orbit_stays_on_top(enabled):
    settings.set_setting("stays_on_top", bool(enabled), namespace=ORBIT_SETTINGS_NAMESPACE)
    win = get_orbit_window()
    if win and wutil.is_valid_widget(win):
        win.apply_stay_on_top_setting()


ORBIT_ACTIONS = (
    "isolate_master",
    "align_selected_objects",
    "create_tracer",
    "reset_objects_mods",
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

DEFAULT_ORBIT_ACTIONS = (
    "reset_objects_mods",
    "delete_all_animation",
    "select_opposite",
    "opposite_copy",
    "mirror",
    "select_hierarchy",
    "isolate_master",
)

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
        toolCommon.open_undo_chunk(tool_id=action_identifier)
        chunk_opened = True
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


class OrbitWindowBus(QtCore.QObject):
    stateChanged = QtCore.Signal(bool)


orbit_window_bus = OrbitWindowBus()


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


def bind_orbit_toolbar_button(button):
    toolCommon.bind_toolbar_button_context_menu(
        orbit_toolbar_toggle,
        button,
        "_tkm_orbit_context_menu_slot",
        lambda parent: build_orbit_context_menu(parent=parent),
    )


def toggle_orbit_window():
    if orbit_toolbar_toggle:
        orbit_toolbar_toggle.toggle()
    elif is_orbit_window_open():
        close_orbit_window()
    else:
        orbit_window(reuse_existing=True)


def _get_orbit_toolbar_button():
    button = getattr(orbit_toolbar_toggle, "_button", None)
    if button and wutil.is_valid_widget(button) and button.isVisible():
        return button
    return None


def restore_orbit_default_position():
    settings.set_setting("orbit_geometry", None, namespace=ORBIT_SETTINGS_NAMESPACE)
    win = get_orbit_window()
    if win and wutil.is_valid_widget(win):
        win.place_above_toolbar_button(_get_orbit_toolbar_button())


def build_orbit_context_menu(parent=None):
    menu = cw.OpenMenuWidget(parent)

    auto_transparency_action = menu.addAction(
        QtGui.QIcon(media.orbit_ui_image),
        "Auto Transparency",
        description="Make the floating Orbit tool palette translucent when the cursor is not over it.",
    )
    auto_transparency_action.setCheckable(True)
    auto_transparency_action.setChecked(_orbit_auto_transparency_enabled())
    auto_transparency_action.triggered.connect(_set_orbit_auto_transparency_enabled)

    menu.addSeparator()

    stays_on_top_action = menu.addAction(
        QtGui.QIcon(media.settings_image),
        "Stay on Top",
        description="Keep the floating Orbit tool palette above other Maya windows.",
    )
    stays_on_top_action.setCheckable(True)
    stays_on_top_action.setChecked(_orbit_stays_on_top())
    stays_on_top_action.triggered.connect(_set_orbit_stays_on_top)

    restore_position_action = menu.addAction(
        QtGui.QIcon(media.orbit_ui_image),
        "Restore Position",
        description="Reset the floating Orbit tool palette to its default position above the Orbit toolbar button.",
    )
    restore_position_action.triggered.connect(lambda *_: restore_orbit_default_position())

    return menu
