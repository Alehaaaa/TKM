"""
Central trigger registry for toolbar tools, hotkeys, and slider commands.
"""

from __future__ import annotations

import importlib
from typing import Callable, Dict, Optional


SLIDER_BUTTON_VALUES = (-150, -125, -105, -100, -50, -15, -5, 0, 5, 15, 50, 100, 105, 125, 150)

_COMMANDS: Dict[str, Callable] = {}
_BUILTINS_LOADED = False
_SLIDERS_LOADED = False
_TOOLBOX_LOADED = False


def _register_core_commands() -> None:
    register_command("toolbar_toggle", _toggle_main_toolbar)
    register_command("toolbar_reload", _reload_main_toolbar)
    register_command("toolbar_unload", _unload_main_toolbar)
    register_command("toolbar_add_shelf_button", _create_toolbar_shelf_button)
    register_command("check_for_updates", _check_for_updates)
    register_command("selection_sets", _toggle_selection_sets)
    register_command("animation_offset", _toggle_animation_offset)
    register_command("micro_move", _toggle_micro_move)
    register_command("custom_graph", _toggle_graph_toolbar)
    register_command("overshoot_sliders", _toggle_sliders_overshoot)
    register_command("attribute_switcher_euler_filter", _toggle_attribute_switcher_euler_filter)
    register_command("custom_tools", _open_custom_tools_config)
    register_command("custom_scripts", _open_custom_scripts_config)
    register_command("about_window", _open_about_window)
    register_command("donate_window", _open_donate_window)
    register_command("bug_report_window", _open_bug_report_window)
    register_command("orbit_window", _open_orbit_window)


def _ensure_builtin_commands() -> None:
    global _BUILTINS_LOADED
    if _BUILTINS_LOADED:
        return
    try:
        _register_builtin_commands()
    except Exception:
        return
    _BUILTINS_LOADED = True


def _ensure_slider_commands() -> None:
    global _SLIDERS_LOADED
    if _SLIDERS_LOADED:
        return
    try:
        _register_slider_commands()
    except Exception:
        return
    _SLIDERS_LOADED = True


def _ensure_toolbox_commands() -> None:
    global _TOOLBOX_LOADED
    if _TOOLBOX_LOADED:
        return
    try:
        import TheKeyMachine.core.toolbox  # noqa: F401
    except Exception:
        return
    _TOOLBOX_LOADED = True


def register_command(name: str, callback: Callable) -> Callable:
    """Register or replace a callable command."""
    _COMMANDS[name] = callback
    return callback


def get_command(name: str) -> Optional[Callable]:
    callback = _COMMANDS.get(name)
    if callback is None:
        _ensure_builtin_commands()
        _ensure_slider_commands()
        _ensure_toolbox_commands()
        callback = _COMMANDS.get(name)
    return callback


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


def invoke(name: str, *args, **kwargs):
    callback = get_command(name)
    if callback is None:
        raise AttributeError("Unknown TheKeyMachine trigger command: {}".format(name))
    return callback(*args, **kwargs)


def make_command_callback(name: str, callback: Optional[Callable] = None) -> Callable:
    """Register a command and return a stable callback proxy that invokes it by name."""
    if callback is not None:
        register_command(name, callback)

    def _proxy(*args, **kwargs):
        return invoke(name, *args, **kwargs)

    _proxy.__name__ = name
    _proxy._tkm_trigger_proxy = True
    return _proxy


def command_string(name: str, *args) -> str:
    """Return a Maya-friendly python command string."""
    serialized_args = ", ".join(repr(arg) for arg in args)
    if serialized_args:
        serialized_args = ", " + serialized_args
    return "import TheKeyMachine.core as TKM_CORE; TKM_CORE.trigger.invoke({!r}{})".format(name, serialized_args)


def execute_slider(prefix: str, mode: str, value: int = 0, session=None):
    """Execute a slider mode directly without a live slider widget."""
    import TheKeyMachine.sliders as sliders

    if prefix == "blend":
        return sliders.execute_blend_slider(mode, value, session=session)
    if prefix == "tween":
        return sliders.execute_tween_slider(mode, value, session=session)
    if prefix == "tangent":
        return sliders.execute_tangent_slider(mode, value, session=session)
    raise ValueError("Unknown slider prefix: {}".format(prefix))


def _slider_value_suffix(value: int) -> str:
    value = int(value)
    if value < 0:
        return "neg{}".format(abs(value))
    return str(value)


def register_slider_mode(prefix: str, mode: str) -> None:
    base_command_name = "slider_{}_{}".format(prefix, mode)
    for slider_value in SLIDER_BUTTON_VALUES:
        command_name = "{}_{}".format(base_command_name, _slider_value_suffix(slider_value))
        register_command(
            command_name,
            lambda p=prefix, m=mode, v=slider_value: execute_slider(p, m, v),
        )


def _toolbar():
    from TheKeyMachine.core.toolbar import get_toolbar

    return get_toolbar()


def _nudge_value(default: int = 1) -> int:
    toolbar = _toolbar()
    widget = getattr(toolbar, "move_keyframes_intField", None)
    if widget is None:
        return default
    try:
        value = int(widget.value())
    except Exception:
        return default
    return value or default


def _toggle_animation_offset(*_args, **_kwargs):
    toolbar = _toolbar()
    if toolbar:
        return toolbar.toggleAnimOffsetButton()
    return None


def _toggle_micro_move(*_args, **_kwargs):
    toolbar = _toolbar()
    if toolbar:
        return toolbar.toggle_micro_move_button()
    return None


def _toggle_selection_sets(*_args, **_kwargs):
    toolbar = _toolbar()
    if toolbar:
        return toolbar.toggle_selection_sets_workspace()
    return None


def _toggle_graph_toolbar(state: bool = True, *_args, **_kwargs):
    import TheKeyMachine.mods.reportMod as report
    import TheKeyMachine.tools.graph_toolbar.api as graphToolbarApi

    return report.safe_execute(
        graphToolbarApi.set_graph_toolbar_enabled,
        bool(state),
        apply=True,
        context="graph toolbar toggle",
    )


def _toggle_sliders_overshoot(*_args, **_kwargs):
    import TheKeyMachine.mods.settingsMod as settings
    import TheKeyMachine.widgets.sliderWidget as sw

    state = not bool(settings.get_setting("sliders_overshoot", False))
    settings.set_setting("sliders_overshoot", state)
    sw.globalSignals.overshootChanged.emit(state)
    return state


def _toggle_attribute_switcher_euler_filter(*_args, **_kwargs):
    import TheKeyMachine.tools.attribute_switcher.api as attributeSwitcherApi

    state = not attributeSwitcherApi.get_attribute_switcher_euler_filter_enabled()
    attributeSwitcherApi.set_attribute_switcher_euler_filter_enabled(state)
    return state


def _open_custom_tools_config(*_args, **_kwargs):
    import TheKeyMachine.mods.generalMod as general

    return general.open_file("TheKeyMachine_user_data/connect/tools", "tools.py")


def _open_custom_scripts_config(*_args, **_kwargs):
    import TheKeyMachine.mods.generalMod as general

    return general.open_file("TheKeyMachine_user_data/connect/scripts", "scripts.py")


def _toggle_main_toolbar(*_args, **_kwargs):
    import TheKeyMachine.core.toolbar as toolbar_mod

    return toolbar_mod.toggle()


def _reload_main_toolbar(*_args, **_kwargs):
    toolbar = _toolbar()
    if toolbar:
        return toolbar.reload()
    return None


def _unload_main_toolbar(*_args, **_kwargs):
    toolbar = _toolbar()
    if toolbar:
        return toolbar.unload()
    return None


def _create_toolbar_shelf_button(*_args, **_kwargs):
    toolbar = _toolbar()
    if toolbar:
        return toolbar.create_shelf_icon()
    return None


def _check_for_updates(*_args, **_kwargs):
    import TheKeyMachine.mods.updater as updater

    return updater.check_for_updates(force=True)


def _import_module(module_name: str):
    try:
        return importlib.import_module(module_name)
    except Exception:
        return None


def _invoke_module_attr(module_name: str, attr_name: str, *args, **kwargs):
    module = _import_module(module_name)
    if not module or not hasattr(module, attr_name):
        return None
    return getattr(module, attr_name)(*args, **kwargs)


def _make_module_command(module_name: str, attr_name: str, *preset_args, **preset_kwargs) -> Callable:
    def _command(*args, **kwargs):
        call_args = preset_args + args
        call_kwargs = dict(preset_kwargs)
        call_kwargs.update(kwargs)
        return _invoke_module_attr(module_name, attr_name, *call_args, **call_kwargs)

    _command.__name__ = attr_name
    return _command


def _open_about_window(*_args, **_kwargs):
    ui = _import_module("TheKeyMachine.mods.uiMod")
    if ui and hasattr(ui, "about_window"):
        return ui.about_window()
    return None


def _open_donate_window(*_args, **_kwargs):
    ui = _import_module("TheKeyMachine.mods.uiMod")
    if ui and hasattr(ui, "donate_window"):
        return ui.donate_window()
    return None


def _open_bug_report_window(*_args, **_kwargs):
    report = _import_module("TheKeyMachine.mods.reportMod")
    if report and hasattr(report, "bug_report_window"):
        return report.bug_report_window()
    return None


def _open_orbit_window(*_args, **_kwargs):
    ui = _import_module("TheKeyMachine.mods.uiMod")
    if ui and hasattr(ui, "toggle_orbit_window"):
        return ui.toggle_orbit_window()
    return None


def _register_builtin_commands():
    _register_core_commands()
    register_command("hotkeys_window", _make_module_command("TheKeyMachine.mods.hotkeysMod", "show_hotkeys_window"))
    register_command("smart_rotation", _make_module_command("TheKeyMachine.mods.hotkeysMod", "smart_rotation_manipulator"))
    register_command("smart_rotation_release", _make_module_command("TheKeyMachine.mods.hotkeysMod", "smart_rotation_manipulator_release"))
    register_command("smart_translation", _make_module_command("TheKeyMachine.mods.hotkeysMod", "smart_translate_manipulator"))
    register_command(
        "smart_translation_release", _make_module_command("TheKeyMachine.mods.hotkeysMod", "smart_translate_manipulator_release")
    )

    register_command("create_locator", _make_module_command("TheKeyMachine.mods.barMod", "createLocator"))
    register_command("depth_mover", _make_module_command("TheKeyMachine.mods.barMod", "depth_mover"))
    register_command("isolate_master", _make_module_command("TheKeyMachine.mods.barMod", "isolate_master"))
    register_command("select_rig_controls", _make_module_command("TheKeyMachine.mods.barMod", "select_rig_controls"))
    register_command("select_rig_controls_animated", _make_module_command("TheKeyMachine.mods.barMod", "select_rig_controls_animated"))
    register_command("select_hierarchy", _make_module_command("TheKeyMachine.mods.barMod", "selectHierarchy"))
    register_command("align_selected_objects", _make_module_command("TheKeyMachine.mods.barMod", "align_selected_objects"))
    register_command("create_tracer", _make_module_command("TheKeyMachine.mods.barMod", "mod_tracer"))
    register_command("tracer_refresh", _make_module_command("TheKeyMachine.mods.barMod", "tracer_refresh"))
    register_command("delete_all_animation", _make_module_command("TheKeyMachine.mods.barMod", "mod_delete_animation"))
    register_command("ws_copy_frame", _make_module_command("TheKeyMachine.mods.barMod", "copy_worldspace_single_frame"))
    register_command("ws_paste_frame", _make_module_command("TheKeyMachine.mods.barMod", "paste_worldspace_single_frame"))
    register_command(
        "ws_copy_range", _make_module_command("TheKeyMachine.mods.barMod", "copy_range_worldspace_animation")
    )
    register_command("ws_paste", _make_module_command("TheKeyMachine.mods.barMod", "color_worldspace_paste_animation"))
    register_command("temp_pivot", _make_module_command("TheKeyMachine.mods.barMod", "create_temp_pivot", False))
    register_command("temp_pivot_last", _make_module_command("TheKeyMachine.mods.barMod", "create_temp_pivot", True))
    register_command("follow_cam", _make_module_command("TheKeyMachine.mods.barMod", "create_follow_cam", translation=True, rotation=True))
    register_command("default_objects_mods", _make_module_command("TheKeyMachine.mods.keyToolsMod", "default_objects_mods"))
    register_command(
        "default_translations",
        _make_module_command("TheKeyMachine.mods.keyToolsMod", "default_object_values", default_translations=True),
    )
    register_command(
        "default_rotations",
        _make_module_command("TheKeyMachine.mods.keyToolsMod", "default_object_values", default_rotations=True),
    )
    register_command("default_scales", _make_module_command("TheKeyMachine.mods.keyToolsMod", "default_object_values", default_scales=True))
    register_command(
        "default_trs",
        _make_module_command(
            "TheKeyMachine.mods.keyToolsMod",
            "default_object_values",
            default_translations=True,
            default_rotations=True,
            default_scales=True,
        ),
    )
    register_command("select_opposite", _make_module_command("TheKeyMachine.mods.keyToolsMod", "selectOpposite"))
    register_command("opposite_add", _make_module_command("TheKeyMachine.mods.keyToolsMod", "addSelectOpposite"))
    register_command("opposite_copy", _make_module_command("TheKeyMachine.mods.keyToolsMod", "copyOpposite"))
    register_command("copy_pose", _make_module_command("TheKeyMachine.mods.keyToolsMod", "copy_pose"))
    register_command("paste_pose", _make_module_command("TheKeyMachine.mods.keyToolsMod", "paste_pose"))
    register_command("copy_animation", _make_module_command("TheKeyMachine.mods.keyToolsMod", "copy_animation"))
    register_command("paste_animation", _make_module_command("TheKeyMachine.mods.keyToolsMod", "paste_animation"))
    register_command("paste_insert_animation", _make_module_command("TheKeyMachine.mods.keyToolsMod", "paste_insert_animation"))
    register_command("paste_opposite_animation", _make_module_command("TheKeyMachine.mods.keyToolsMod", "paste_opposite_animation"))
    register_command("paste_animation_to", _make_module_command("TheKeyMachine.mods.keyToolsMod", "paste_animation_to"))
    register_command("link_copy", _make_module_command("TheKeyMachine.mods.keyToolsMod", "copy_link"))
    register_command("link_paste", _make_module_command("TheKeyMachine.mods.keyToolsMod", "paste_link"))
    register_command(
        "nudge_insert_inbetween",
        lambda: _invoke_module_attr("TheKeyMachine.mods.keyToolsMod", "insert_inbetween", _nudge_value()),
    )
    register_command(
        "nudge_remove_inbetween",
        lambda: _invoke_module_attr("TheKeyMachine.mods.keyToolsMod", "remove_inbetween", _nudge_value()),
    )
    register_command(
        "nudge_left",
        lambda: _invoke_module_attr("TheKeyMachine.mods.keyToolsMod", "move_keyframes_in_range", -_nudge_value()),
    )
    register_command(
        "nudge_right",
        lambda: _invoke_module_attr("TheKeyMachine.mods.keyToolsMod", "move_keyframes_in_range", _nudge_value()),
    )


def _register_slider_commands():
    from TheKeyMachine.sliders import BLEND_MODES, TANGENT_MODES, TWEEN_MODES

    for prefix, modes in (("blend", BLEND_MODES), ("tween", TWEEN_MODES), ("tangent", TANGENT_MODES)):
        for mode in modes:
            if not isinstance(mode, dict):
                continue
            register_slider_mode(prefix, mode["key"])


def __getattr__(name: str):
    if has_command(name):
        return make_command_callback(name)
    raise AttributeError(name)


_register_core_commands()
