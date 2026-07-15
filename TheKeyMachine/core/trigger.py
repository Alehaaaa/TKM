"""
Central trigger registry for toolbar tools, hotkeys, and slider commands.

This module keeps command names stable for Maya hotkeys/shelf buttons while
leaving behavior in the feature modules that own it.
"""

from __future__ import annotations

import importlib
import inspect
import keyword
from dataclasses import dataclass
from functools import wraps
from typing import Callable, Dict, Optional


SLIDER_BUTTON_VALUES = (-150, -125, -105, -100, -50, -15, -5, 0, 5, 15, 50, 100, 105, 125, 150)

_COMMANDS: Dict[str, Callable] = {}
_BUILTINS_LOADED = False
_SLIDERS_LOADED = False
_TOOLBOX_LOADED = False

_SHELF_MENU_COMMANDS = (
    "TKM",
    "main_preferences_menu",
    "main_dock_menu",
    "main_system_menu",
    "help_menu",
    "graph_settings_menu",
    "graph_dock_menu",
)


@dataclass(frozen=True)
class OperationPolicy:
    progress: bool = True
    undo: bool = True
    suspend_refresh: bool = False


def _operation_policy(command_name: str) -> OperationPolicy:
    """Central lifecycle policy for registered commands.

    Windows and menus still use ToolOperation for consistent dispatch/error
    boundaries, but they must not show a progress bar while waiting for input or
    hold an empty undo chunk open for the lifetime of an interactive UI.
    """
    interactive = command_name in _SHELF_MENU_COMMANDS or command_name.endswith(("_menu", "_window"))
    return OperationPolicy(progress=not interactive, undo=not interactive)

_MODULE_COMMANDS = {
    "toolbar_toggle": ("TheKeyMachine.core.toolbar", "toggle"),
    "toolbar_reload": ("TheKeyMachine.core.toolbar", "reload_current"),
    "toolbar_unload": ("TheKeyMachine.core.toolbar", "unload_current"),
    "toolbar_add_shelf_button": ("TheKeyMachine.core.toolbar", "create_shelf_icon_current"),
    "check_for_updates": ("TheKeyMachine.mods.updater", "check_for_updates", (), {"force": True}),
    "selection_sets": ("TheKeyMachine.core.toolbar", "toggle_selection_sets_workspace"),
    "animation_offset": ("TheKeyMachine.core.toolbar", "toggle_animation_offset"),
    "micro_move": ("TheKeyMachine.core.toolbar", "toggle_micro_move"),
    "custom_graph": ("TheKeyMachine.tools.graph_toolbar.api", "toggle_graph_toolbar_enabled"),
    "overshoot_sliders": ("TheKeyMachine.core.toolbox", "toggle_overshoot_sliders_enabled"),
    "attribute_switcher_euler_filter": ("TheKeyMachine.tools.attribute_switcher.api", "toggle_euler_filter_enabled"),
    "background_runner_channelbox_selection_highlight": (
        "TheKeyMachine.core.backgroundRunners",
        "toggle_channelbox_selection_highlight",
    ),
    "background_runner_channelbox_clear_on_selection_change": (
        "TheKeyMachine.core.backgroundRunners",
        "toggle_channelbox_clear_on_selection_change",
    ),
    "background_runner_camera_orbit_selection": (
        "TheKeyMachine.core.backgroundRunners",
        "toggle_camera_orbit_selection",
    ),
    "about_window": ("TheKeyMachine.mods.uiMod", "about_window"),
    "donate_window": ("TheKeyMachine.mods.uiMod", "donate_window"),
    "bug_report_window": ("TheKeyMachine.mods.reportMod", "bug_report_window"),
    "orbit_window": ("TheKeyMachine.mods.uiMod", "toggle_orbit_window"),
    "hotkeys_window": ("TheKeyMachine.mods.hotkeysMod", "show_hotkeys_window"),
    "version_history_window": ("TheKeyMachine.widgets.customDialogs", "show_version_history_dialog"),
    "search_window": ("TheKeyMachine.tools.search.api", "toggle_search_window"),
    "smart_rotation": ("TheKeyMachine.mods.keyToolsMod", "smart_rotation_manipulator"),
    "smart_rotation_release": ("TheKeyMachine.mods.keyToolsMod", "smart_rotation_manipulator_release"),
    "smart_translation": ("TheKeyMachine.mods.keyToolsMod", "smart_translate_manipulator"),
    "smart_translation_release": ("TheKeyMachine.mods.keyToolsMod", "smart_translate_manipulator_release"),
    "create_locator": ("TheKeyMachine.mods.barMod", "create_locator"),
    "depth_mover": ("TheKeyMachine.mods.barMod", "depth_mover"),
    "isolate_master": ("TheKeyMachine.mods.barMod", "isolate_master"),
    "select_rig_controls": ("TheKeyMachine.mods.barMod", "select_rig_controls"),
    "select_rig_controls_animated": ("TheKeyMachine.mods.barMod", "select_rig_controls_animated"),
    "select_hierarchy": ("TheKeyMachine.mods.barMod", "select_hierarchy"),
    "align_selected_objects": ("TheKeyMachine.mods.barMod", "align_selected_objects"),
    "create_tracer": ("TheKeyMachine.mods.barMod", "create_tracer"),
    "tracer_refresh": ("TheKeyMachine.mods.barMod", "tracer_refresh"),
    "ws_copy_frame": ("TheKeyMachine.mods.barMod", "copy_worldspace_single_frame"),
    "ws_paste_frame": ("TheKeyMachine.mods.barMod", "paste_worldspace_single_frame"),
    "ws_copy_range": ("TheKeyMachine.mods.barMod", "copy_range_worldspace_animation"),
    "ws_paste": ("TheKeyMachine.mods.barMod", "worldspace_paste_animation"),
    "follow_cam": ("TheKeyMachine.mods.barMod", "create_follow_cam", (), {"translation": True, "rotation": True}),
    "temp_pivot": ("TheKeyMachine.tools.temp_pivot.api", "toggle_temp_pivot"),
    "temp_pivot_last_object": ("TheKeyMachine.tools.temp_pivot.api", "create_last_object_temp_pivot"),
    "temp_pivot_centered": ("TheKeyMachine.tools.temp_pivot.api", "create_centered_temp_pivot"),
    "temp_pivot_worldspace": ("TheKeyMachine.tools.temp_pivot.api", "create_worldspace_temp_pivot"),
    "temp_pivot_edit": ("TheKeyMachine.tools.temp_pivot.api", "edit_temp_pivot"),
    "temp_pivot_reset": ("TheKeyMachine.tools.temp_pivot.api", "reset_temp_pivot"),
    "temp_pivot_last": ("TheKeyMachine.tools.temp_pivot.api", "create_last_object_temp_pivot"),
}

_KEYTOOLS_COMMANDS = {
    "apply_smart_euler_filter": "apply_smart_euler_filter",
    "clear_animation": "clear_animation_keys",
    "copy_keys": "copy_keys",
    "crop_animation": "crop_animation",
    "cut_keys": "cut_keys",
    "delete_keys": "delete_keys",
    "paste_keys": "paste_keys",
    "paste_keys_relative": "paste_keys_relative",
    "remove_redundant_keys": "remove_redundant_keys",
    "remove_static_anim_curves": "remove_static_anim_curves",
    "reverse_animation": "reverse_animation",
    "set_smart_key": "set_smart_key",
    "set_smart_key_all_channels": "set_smart_key_all_channels",
    "delete_all_animation": "clear_animation_keys",
    "delete_static_animation": "remove_static_anim_curves",
    "default_object_values": "default_object_values",
    "select_opposite": "select_opposite",
    "opposite_add": "add_select_opposite",
    "opposite_copy": "copy_opposite",
    "mirror": "mirror",
    "mirror_to_right": "mirror_to_right",
    "mirror_to_left": "mirror_to_left",
    "mirror_all_keys": "mirror_all_keys",
    "copy_pose": "copy_pose",
    "paste_pose": "paste_pose",
    "paste_mirror_pose": "paste_mirror_pose",
    "paste_pose_to": "paste_pose_to",
    "export_pose_file": "export_pose_file",
    "import_pose_file": "import_pose_file",
    "copy_animation": "copy_animation",
    "paste_animation": "paste_animation",
    "paste_insert_animation": "paste_insert_animation",
    "paste_opposite_animation": "paste_opposite_animation",
    "paste_animation_to": "paste_animation_to",
    "export_animation_file": "export_animation_file",
    "import_animation_file": "import_animation_file",
    "link_copy": "copy_link",
    "link_paste": "paste_link",
    "share_keys_from_last_selected": "share_keys_from_last_selected",
    "bake_animation_from_last_selected": "bake_animation_from_last_selected",
}

_KEYTOOLS_VARIANTS = {
    "default_translations": ("default_object_values", (), {"default_translations": True}),
    "default_rotations": ("default_object_values", (), {"default_rotations": True}),
    "default_scales": ("default_object_values", (), {"default_scales": True}),
    "default_trs": (
        "default_object_values",
        (),
        {"default_translations": True, "default_rotations": True, "default_scales": True},
    ),
    "nudge_insert_inbetween": ("insert_inbetween", (1,), {}),
    "nudge_remove_inbetween": ("remove_inbetween", (1,), {}),
    "nudge_left": ("move_keyframes_in_range", (-1,), {}),
    "nudge_right": ("move_keyframes_in_range", (1,), {}),
    "nudge_left_all_keys": ("nudge_all_keys", (-1,), {}),
    "nudge_left_scene": ("nudge_scene_keys", (-1,), {}),
    "nudge_right_all_keys": ("nudge_all_keys", (1,), {}),
    "nudge_right_scene": ("nudge_scene_keys", (1,), {}),
    "nudge_insert_inbetween_scene": ("inbetween_scene", (1,), {}),
    "nudge_remove_inbetween_scene": ("inbetween_scene", (-1,), {}),
}


def register_command(name: str, callback: Callable) -> Callable:
    """Register a command behind the shared ToolOperation dispatcher."""
    if getattr(callback, "_tkm_tool_dispatch", False) and getattr(callback, "_tkm_command_name", None) == name:
        dispatched = callback
    else:
        dispatched = _make_dispatched_command(name, callback)
    _COMMANDS[name] = dispatched
    return dispatched


def _make_dispatched_command(name: str, callback: Callable) -> Callable:
    @wraps(callback)
    def _dispatch(*args, **kwargs):
        from TheKeyMachine.tools import common as toolCommon

        label = kwargs.pop("_tkm_tool_label", None)
        anchor_widget = kwargs.pop("_tkm_anchor_widget", None)
        # A caller may forward its current operation; command dispatch owns the
        # canonical outer lifecycle and only passes the canonical instance on.
        kwargs.pop("tool_operation", None)
        policy = _operation_policy(name)
        with toolCommon.tool_operation(
            tool_id=name,
            label=label,
            anchor_widget=anchor_widget,
            progress=policy.progress,
            undo=policy.undo,
            suspend_refresh=policy.suspend_refresh,
        ) as operation:
            call_kwargs = dict(kwargs)
            call_kwargs.setdefault("tool_operation", operation)
            return callback(*args, **_supported_callback_kwargs(callback, call_kwargs))

    _dispatch.__name__ = name
    _dispatch._tkm_tool_dispatch = True
    _dispatch._tkm_command_name = name
    _dispatch._tkm_registered_callback = callback
    return _dispatch


def get_command(name: str) -> Optional[Callable]:
    callback = _COMMANDS.get(name)
    if callback is None:
        _ensure_builtin_commands()
        _ensure_slider_commands()
        _ensure_toolbox_commands()
        callback = _COMMANDS.get(name)
    return callback


def execute_command(name: str, *args, **kwargs):
    """Execute any registered command through its standardized operation."""
    callback = get_command(name)
    if callback is None:
        raise AttributeError("Unknown TheKeyMachine trigger command: {}".format(name))
    return callback(*args, **kwargs)


def list_commands() -> list[str]:
    _ensure_builtin_commands()
    _ensure_slider_commands()
    _ensure_toolbox_commands()
    return sorted(_COMMANDS.keys())


def has_command(name: str) -> bool:
    if name in _COMMANDS:
        return True
    _ensure_builtin_commands()
    _ensure_slider_commands()
    _ensure_toolbox_commands()
    return name in _COMMANDS


def command_name_for_callback(callback: Callable) -> Optional[str]:
    """Return the registered trigger name for a callback, when one exists."""
    if not callable(callback):
        return None
    name = getattr(callback, "__name__", None)
    if not name:
        return None
    if getattr(callback, "_tkm_trigger_proxy", False):
        return name
    if has_command(name):
        return name
    for command_name in list_commands():
        registered = get_command(command_name)
        if getattr(registered, "__name__", None) == name:
            return command_name
    return None


def make_command_callback(name: str, callback: Optional[Callable] = None) -> Callable:
    """Register a command and return a stable callback proxy that invokes it by name."""
    if callback is not None:
        register_command(name, callback)

    def _proxy(*args, **kwargs):
        return execute_command(name, *args, **kwargs)

    _proxy.__name__ = name
    _proxy._tkm_trigger_proxy = True
    return _proxy


def command_string(name: str, *args) -> str:
    """Return a Maya-friendly python command string."""
    if not name.isidentifier() or keyword.iskeyword(name):
        raise ValueError("Trigger command is not a valid Python attribute: {}".format(name))
    serialized_args = ", ".join(repr(arg) for arg in args)
    return "import TheKeyMachine.core as TKM_CORE; TKM_CORE.trigger.{}({})".format(name, serialized_args)


def execute_slider(prefix: str, mode: str, value: int = 0, session=None):
    """Execute a slider mode directly without a live slider widget."""
    from TheKeyMachine.sliders import api as slider_api

    if prefix == "blend":
        return slider_api.execute_blend_slider(mode, value, session=session)
    if prefix == "tween":
        return slider_api.execute_tween_slider(mode, value, session=session)
    if prefix == "tangent":
        return slider_api.execute_tangent_slider(mode, value, session=session)
    raise ValueError("Unknown slider prefix: {}".format(prefix))


def register_slider_mode(prefix: str, mode: str) -> None:
    base_command_name = "slider_{}_{}".format(prefix, mode)
    for slider_value in SLIDER_BUTTON_VALUES:
        command_name = "{}_{}".format(base_command_name, _slider_value_suffix(slider_value))
        register_command(command_name, lambda p=prefix, m=mode, v=slider_value: execute_slider(p, m, v))


def _ensure_builtin_commands() -> None:
    global _BUILTINS_LOADED
    if _BUILTINS_LOADED:
        return
    try:
        _register_builtin_commands()
    except (ImportError, RuntimeError, ValueError, TypeError, AttributeError, KeyError, IndexError):
        return
    _BUILTINS_LOADED = True


def _ensure_slider_commands() -> None:
    global _SLIDERS_LOADED
    if _SLIDERS_LOADED:
        return
    try:
        _register_slider_commands()
    except (ImportError, RuntimeError, ValueError, TypeError, AttributeError, KeyError, IndexError):
        return
    _SLIDERS_LOADED = True


def _ensure_toolbox_commands() -> None:
    global _TOOLBOX_LOADED
    if _TOOLBOX_LOADED:
        return
    try:
        import TheKeyMachine.core.toolbox  # noqa: F401
    except ImportError:
        return
    _TOOLBOX_LOADED = True


def _register_builtin_commands() -> None:
    for menu_name in _SHELF_MENU_COMMANDS:
        register_command(menu_name, _module_command(menu_name, "TheKeyMachine.mods.shelfMod", "show_tool_menu_at_cursor", menu_name))

    for command_name, spec in _MODULE_COMMANDS.items():
        module_name, attr_name = spec[:2]
        preset_args = spec[2] if len(spec) > 2 else ()
        preset_kwargs = spec[3] if len(spec) > 3 else {}
        register_command(command_name, _module_command(command_name, module_name, attr_name, *preset_args, **preset_kwargs))

    for command_name, attr_name in _KEYTOOLS_COMMANDS.items():
        register_command(command_name, _module_command(command_name, "TheKeyMachine.mods.keyToolsMod", attr_name))

    for command_name, (attr_name, preset_args, preset_kwargs) in _KEYTOOLS_VARIANTS.items():
        register_command(
            command_name,
            _module_command(command_name, "TheKeyMachine.mods.keyToolsMod", attr_name, *preset_args, **preset_kwargs),
        )


def _register_slider_commands() -> None:
    from TheKeyMachine.sliders.manager import BLEND_MODES, TANGENT_MODES, TWEEN_MODES

    for prefix, modes in (("blend", BLEND_MODES), ("tween", TWEEN_MODES), ("tangent", TANGENT_MODES)):
        for mode in modes:
            if not isinstance(mode, dict):
                continue
            register_slider_mode(prefix, mode["key"])


def _module_command(command_name: str, module_name: str, attr_name: str, *preset_args, **preset_kwargs) -> Callable:
    def _command(*args, **kwargs):
        module = _import_module(module_name)
        if not module or not hasattr(module, attr_name):
            return None
        callback = getattr(module, attr_name)
        call_args = preset_args + args
        call_kwargs = dict(preset_kwargs)
        call_kwargs.update(kwargs)
        return callback(*call_args, **_supported_callback_kwargs(callback, call_kwargs))

    _command.__name__ = command_name
    return _command


def _import_module(module_name: str):
    try:
        return importlib.import_module(module_name)
    except ImportError:
        return None


def _supported_callback_kwargs(callback: Callable, kwargs):
    if not kwargs:
        return kwargs
    try:
        signature = inspect.signature(callback)
    except Exception:
        return kwargs
    accepts_kwargs = any(
        parameter.kind == inspect.Parameter.VAR_KEYWORD
        for parameter in signature.parameters.values()
    )
    if accepts_kwargs:
        return kwargs
    return {key: value for key, value in kwargs.items() if key in signature.parameters}


def _slider_value_suffix(value: int) -> str:
    value = int(value)
    if value < 0:
        return "neg{}".format(abs(value))
    return str(value)


def __getattr__(name: str):
    if has_command(name):
        return make_command_callback(name)
    raise AttributeError(name)


_register_builtin_commands()
