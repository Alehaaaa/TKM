"""
Central trigger registry for toolbar tools, hotkeys, and slider commands.
"""

from __future__ import annotations

from typing import Callable, Dict, Iterable, Optional


SLIDER_BUTTON_VALUES = (-150, -125, -105, -100, -50, -15, -5, 0, 5, 15, 50, 100, 105, 125, 150)

_COMMANDS: Dict[str, Callable] = {}
_ALIASES: Dict[str, str] = {}
_BUILTINS_LOADED = False
_SLIDERS_LOADED = False
_TOOLBOX_LOADED = False


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


def register_command(name: str, callback: Callable, aliases: Optional[Iterable[str]] = None) -> Callable:
    """Register or replace a callable command."""
    _COMMANDS[name] = callback
    _ALIASES[name] = name
    for alias in aliases or ():
        if alias:
            _ALIASES[alias] = name
    return callback


def get_command(name: str) -> Optional[Callable]:
    resolved_name = resolve_command_name(name)
    callback = _COMMANDS.get(resolved_name)
    if callback is None:
        _ensure_builtin_commands()
        _ensure_slider_commands()
        _ensure_toolbox_commands()
        callback = _COMMANDS.get(resolve_command_name(name))
    return callback


def list_commands() -> list[str]:
    _ensure_builtin_commands()
    _ensure_slider_commands()
    _ensure_toolbox_commands()
    return sorted(_COMMANDS.keys())


def has_command(name: str) -> bool:
    resolved_name = resolve_command_name(name)
    if resolved_name in _COMMANDS:
        return True
    _ensure_builtin_commands()
    _ensure_slider_commands()
    _ensure_toolbox_commands()
    return resolve_command_name(name) in _COMMANDS


def resolve_command_name(name: str) -> str:
    return _ALIASES.get(name, name)


def invoke(name: str, *args, **kwargs):
    callback = get_command(name)
    if callback is None:
        raise AttributeError("Unknown TheKeyMachine trigger command: {}".format(name))
    return callback(*args, **kwargs)


def make_command_callback(name: str, callback: Optional[Callable] = None, aliases: Optional[Iterable[str]] = None) -> Callable:
    """Register a command and return a stable callback proxy that invokes it by name."""
    if callback is not None:
        register_command(name, callback, aliases=aliases)

    def _proxy(*args, **kwargs):
        return invoke(name, *args, **kwargs)

    _proxy.__name__ = name
    return _proxy


def command_string(name: str, *args) -> str:
    """Return a Maya-friendly python command string."""
    serialized_args = ", ".join(repr(arg) for arg in args)
    if serialized_args:
        serialized_args = ", " + serialized_args
    return "import TheKeyMachine.core as TKM_CORE; TKM_CORE.trigger.invoke({!r}{})".format(name, serialized_args)


def execute_slider(prefix: str, mode: str, value: int = 0):
    """Execute a slider mode directly without a live slider widget."""
    import TheKeyMachine.sliders as sliders

    if prefix == "blend":
        return sliders.execute_curve_modifier(mode, value)
    if prefix == "tween":
        return sliders.execute_tween(mode, value)
    if prefix == "tangent":
        return sliders.execute_tangent_blend(mode, value)
    raise ValueError("Unknown slider prefix: {}".format(prefix))


def _slider_value_suffix(value: int) -> str:
    value = int(value)
    if value < 0:
        return "neg{}".format(abs(value))
    return str(value)


def register_slider_mode(prefix: str, mode: str, aliases: Optional[Iterable[str]] = None) -> None:
    base_command_name = "slider_{}_{}".format(prefix, mode)
    for slider_value in SLIDER_BUTTON_VALUES:
        command_name = "{}_{}".format(base_command_name, _slider_value_suffix(slider_value))
        command_aliases = aliases if slider_value == 0 else None
        register_command(
            command_name,
            lambda p=prefix, m=mode, v=slider_value: execute_slider(p, m, v),
            aliases=command_aliases,
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


def _register_builtin_commands():
    import TheKeyMachine.core.customGraph as customGraph
    import TheKeyMachine.mods.barMod as bar
    import TheKeyMachine.mods.hotkeysMod as hotkeys
    import TheKeyMachine.mods.keyToolsMod as keyTools
    import TheKeyMachine.mods.uiMod as ui

    register_command("toolbar_toggle", _toggle_main_toolbar, aliases=["toggle_main_toolbar"])
    register_command("toolbar_reload", _reload_main_toolbar)
    register_command("toolbar_unload", _unload_main_toolbar)
    register_command("toolbar_add_shelf_button", _create_toolbar_shelf_button)
    register_command("check_for_updates", _check_for_updates)
    register_command("open_custom_graph", customGraph.createCustomGraph)
    register_command("hotkeys_window", hotkeys.show_hotkeys_window)
    register_command("about_window", ui.about_window)
    register_command("donate_window", ui.donate_window)
    register_command("bug_report_window", ui.bug_report_window)
    register_command("smart_rotation", hotkeys.smart_rotation_manipulator)
    register_command("smart_rotation_release", hotkeys.smart_rotation_manipulator_release)
    register_command("smart_translation", hotkeys.smart_translate_manipulator)
    register_command("smart_translation_release", hotkeys.smart_translate_manipulator_release)
    register_command("orbit_window", ui.toggle_orbit_window, aliases=["orbit"])
    register_command("selection_sets_toggle", _toggle_selection_sets, aliases=["selection_sets"])
    register_command("animation_offset_toggle", _toggle_animation_offset, aliases=["animation_offset"])
    register_command("micro_move_toggle", _toggle_micro_move, aliases=["micro_move"])
    register_command("custom_graph_toggle", _toggle_graph_toolbar, aliases=["custom_graph"])
    register_command("create_locator", bar.createLocator)
    register_command("depth_mover", bar.depth_mover)
    register_command("isolate_master", bar.isolate_master)
    register_command("select_rig_controls", bar.select_rig_controls)
    register_command("select_rig_controls_animated", bar.select_rig_controls_animated)
    register_command("select_hierarchy", bar.selectHierarchy)
    register_command("align_selected_objects", bar.align_selected_objects)
    register_command("create_tracer", bar.mod_tracer)
    register_command("refresh_tracer", bar.tracer_refresh)
    register_command("delete_animation", bar.mod_delete_animation)
    register_command("delete_all_animation", bar.mod_delete_animation)
    register_command("copy_worldspace_single_frame", bar.copy_worldspace_single_frame)
    register_command("paste_worldspace_single_frame", bar.paste_worldspace_single_frame)
    register_command("copy_range_worldspace_animation", bar.copy_range_worldspace_animation)
    register_command("worldspace_paste_animation", bar.color_worldspace_paste_animation)
    register_command("worldspace_copy_animation", bar.color_worldspace_copy_animation)
    register_command("create_temp_pivot", lambda: bar.create_temp_pivot(False))
    register_command("create_temp_pivot_last", lambda: bar.create_temp_pivot(True))
    register_command("create_follow_cam", lambda: bar.create_follow_cam(translation=True, rotation=True))
    register_command("reset_values", keyTools.reset_objects_mods, aliases=["reset_objects_mods"])
    register_command("reset_translations", lambda: keyTools.reset_object_values(reset_translations=True))
    register_command("reset_rotations", lambda: keyTools.reset_object_values(reset_rotations=True))
    register_command("reset_scales", lambda: keyTools.reset_object_values(reset_scales=True))
    register_command(
        "reset_trs",
        lambda: keyTools.reset_object_values(
            reset_translations=True,
            reset_rotations=True,
            reset_scales=True,
        ),
    )
    register_command("select_opposite", keyTools.selectOpposite, aliases=["selectOpposite"])
    register_command("add_opposite", keyTools.addSelectOpposite, aliases=["opposite_add"])
    register_command("copy_opposite", keyTools.copyOpposite, aliases=["copyOpposite"])
    register_command("copy_pose", keyTools.copy_pose)
    register_command("paste_pose", keyTools.paste_pose)
    register_command("copy_animation", keyTools.copy_animation)
    register_command("paste_animation", keyTools.paste_animation)
    register_command("paste_insert_animation", keyTools.paste_insert_animation)
    register_command("paste_opposite_animation", keyTools.paste_opposite_animation)
    register_command("paste_animation_to", keyTools.paste_animation_to)
    register_command("copy_link", keyTools.copy_link)
    register_command("paste_link", keyTools.paste_link)

    register_command("insert_inbetween", lambda: keyTools.insert_inbetween(_nudge_value()), aliases=["nudge_insertInbetween"])
    register_command("remove_inbetween", lambda: keyTools.remove_inbetween(_nudge_value()), aliases=["nudge_removeInbetween"])
    register_command(
        "nudge_left",
        lambda: keyTools.move_keyframes_in_range(-_nudge_value()),
        aliases=["move_left", "move_keyframes_left"],
    )
    register_command(
        "nudge_right",
        lambda: keyTools.move_keyframes_in_range(_nudge_value()),
        aliases=["move_right", "move_keyframes_right"],
    )

    register_command("set_auto_tangent", lambda: bar.setTangent("auto"))
    register_command("set_spline_tangent", lambda: bar.setTangent("spline"))
    register_command("set_clamped_tangent", lambda: bar.setTangent("clamped"))
    register_command("set_linear_tangent", lambda: bar.setTangent("linear"))
    register_command("set_flat_tangent", lambda: bar.setTangent("flat"))
    register_command("set_step_tangent", lambda: bar.setTangent("step"))
    register_command("set_plateau_tangent", lambda: bar.setTangent("plateau"))


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
