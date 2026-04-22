import os

import maya.cmds as cmds

try:
    from PySide2 import QtCore, QtGui, QtWidgets
except ImportError:
    from PySide6 import QtCore, QtGui, QtWidgets

import TheKeyMachine.mods.barMod as bar
import TheKeyMachine.mods.generalMod as general
import TheKeyMachine.mods.keyToolsMod as keyTools
import TheKeyMachine.mods.mediaMod as media
import TheKeyMachine.mods.settingsMod as settings
from TheKeyMachine.tools.common import ToolbarWindowToggle
from TheKeyMachine.tools import common as toolCommon
from TheKeyMachine.widgets import customWidgets as cw, util as wutil

ORBIT_SETTINGS_NAMESPACE = "orbit_window"
ORBIT_AUTO_TRANSPARENCY_KEY = "orbit_auto_transparency"

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


def temp_pivot_action():
    bar.create_temp_pivot(False)


orbit_actions = {
    "isolate_master": "bar.isolate_master",
    "align_selected_objects": "bar.align_selected_objects",
    "mod_tracer": "bar.mod_tracer",
    "reset_objects_mods": "keyTools.reset_objects_mods",
    "delete_all_animation": "bar.delete_all_animation",
    "selectOpposite": "keyTools.selectOpposite",
    "copyOpposite": "keyTools.copyOpposite",
    "mirror": "keyTools.mirror",
    "copy_animation": "keyTools.copy_animation",
    "paste_animation": "keyTools.paste_animation",
    "paste_insert_animation": "keyTools.paste_insert_animation",
    "selectHierarchy": "bar.selectHierarchy",
    "mod_link_objects": "keyTools.copy_link",
    "temp_pivot": "temp_pivot_action",
    "copy_pose": "keyTools.copy_pose",
    "paste_pose": "keyTools.paste_pose",
    "copy_worldspace_single_frame": "bar.copy_worldspace_single_frame",
    "paste_worldspace_single_frame": "bar.paste_worldspace_single_frame",
}

orbit_action_icons = {
    "bar.isolate_master": media.isolate_image,
    "bar.align_selected_objects": media.align_menu_image,
    "bar.mod_tracer": media.tracer_image,
    "keyTools.reset_objects_mods": media.asset_path("reset_animation_image"),
    "bar.delete_all_animation": media.delete_animation_image,
    "keyTools.selectOpposite": media.opposite_select_image,
    "keyTools.copyOpposite": media.opposite_copy_image,
    "keyTools.mirror": media.mirror_image,
    "keyTools.copy_animation": media.copy_animation_image,
    "keyTools.paste_animation": media.paste_animation_image,
    "keyTools.paste_insert_animation": media.paste_insert_animation_image,
    "bar.selectHierarchy": media.select_hierarchy_image,
    "keyTools.copy_link": media.link_objects_image,
    "temp_pivot_action": media.temp_pivot_image,
    "keyTools.copy_pose": media.copy_pose_image,
    "keyTools.paste_pose": media.paste_pose_image,
    "bar.copy_worldspace_single_frame": media.worldspace_copy_frame_image,
    "bar.paste_worldspace_single_frame": media.worldspace_paste_frame_image,
}

DEFAULT_ORBIT_CONFIGURATION = {
    "button1": "reset_objects_mods",
    "button2": "delete_all_animation",
    "button3": "selectOpposite",
    "button4": "copyOpposite",
    "button5": "mirror",
    "button6": "selectHierarchy",
    "button7": "isolate_master",
}

LEGACY_ACTION_ALIASES = {"accion_temp_pivot": "temp_pivot"}


def normalize_action_identifier(action_identifier):
    return LEGACY_ACTION_ALIASES.get(action_identifier, action_identifier)


def _orbit_button_sort_key(button_id):
    suffix = str(button_id).replace("button", "")
    return int(suffix) if suffix.isdigit() else 9999


def sanitize_orbit_configuration(config):
    valid_actions = set(orbit_actions.keys())
    sanitized = {}
    seen_actions = set()

    for button_id in sorted(config.keys(), key=_orbit_button_sort_key):
        if not str(button_id).startswith("button"):
            continue
        action_identifier = normalize_action_identifier(config.get(button_id, ""))
        if action_identifier not in valid_actions or action_identifier in seen_actions:
            continue
        sanitized[button_id] = action_identifier
        seen_actions.add(action_identifier)

    return sanitized


def execute_action(action_identifier):
    action_identifier = normalize_action_identifier(action_identifier)
    chunk_opened = False
    try:
        toolCommon.open_undo_chunk(tool_id=action_identifier)
        chunk_opened = True

        if action_identifier == "isolate_master":
            bar.isolate_master()
        elif action_identifier == "align_selected_objects":
            bar.align_selected_objects()
        elif action_identifier == "mod_tracer":
            bar.mod_tracer()
        elif action_identifier == "reset_objects_mods":
            keyTools.reset_objects_mods()
        elif action_identifier == "delete_all_animation":
            bar.mod_delete_animation()
        elif action_identifier == "selectOpposite":
            keyTools.selectOpposite()
        elif action_identifier == "copyOpposite":
            keyTools.copyOpposite()
        elif action_identifier == "mirror":
            keyTools.mirror()
        elif action_identifier == "copy_animation":
            keyTools.copy_animation()
        elif action_identifier == "paste_animation":
            keyTools.paste_animation()
        elif action_identifier == "paste_insert_animation":
            keyTools.paste_insert_animation()
        elif action_identifier == "copy_pose":
            keyTools.copy_pose()
        elif action_identifier == "paste_pose":
            keyTools.paste_pose()
        elif action_identifier == "selectHierarchy":
            bar.selectHierarchy()
        elif action_identifier == "mod_link_objects":
            keyTools.copy_link()
        elif action_identifier == "temp_pivot":
            temp_pivot_action()
        elif action_identifier == "copy_worldspace_single_frame":
            bar.copy_worldspace_single_frame()
        elif action_identifier == "paste_worldspace_single_frame":
            bar.paste_worldspace_single_frame()
    finally:
        if chunk_opened:
            toolCommon.close_undo_chunk()


def _config_path():
    return os.path.join(general.config["USER_FOLDER_PATH"], "TheKeyMachine_user_data", "tools", "orbit", "orbit.py")


def save_orbit_button_config():
    config_path = _config_path()
    config_dir = os.path.dirname(config_path)
    if not os.path.exists(config_dir):
        os.makedirs(config_dir)

    sanitized = sanitize_orbit_configuration(orbit_configuration)
    with open(config_path, "w") as file:
        for button_id in sorted(sanitized.keys(), key=_orbit_button_sort_key):
            file.write(f"{button_id} = '{sanitized[button_id]}'\n")


def load_orbit_configuration():
    config_path = _config_path()
    config_dir = os.path.dirname(config_path)
    config = dict(DEFAULT_ORBIT_CONFIGURATION)
    if not os.path.exists(config_dir):
        os.makedirs(config_dir)

    try:
        with open(config_path, "r") as file:
            for line in file.readlines():
                if line.startswith("button"):
                    key, value = line.split("=")
                    config[key.strip()] = value.strip().strip("'")
    except FileNotFoundError:
        with open(config_path, "w") as file:
            for key, value in config.items():
                file.write(f"{key} = '{value}'\n")

    return sanitize_orbit_configuration(config)


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
