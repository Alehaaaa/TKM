"""
TheKeyMachine - Sliders public API

Public entry points used by toolbar widgets, hotkeys, and trigger commands.
"""

from . import curve_ops, keyframe_ops, manager, tangent_ops, time_ops, utils
from TheKeyMachine.tools import common as toolCommon


# Dispatch maps for various slider types
DISPATCH_MAPS = {
    "tween": {
        "tweener": keyframe_ops.apply_tween,
        "tweener_worldspace": keyframe_ops.apply_tween,
        "blend_to_buffer": keyframe_ops.apply_blend_to_buffer,
        "blend_to_default": keyframe_ops.apply_blend_to_default,
        "blend_to_ease": keyframe_ops.apply_blend_to_ease,
        "blend_to_frame": keyframe_ops.apply_blend_to_frame,
        "blend_to_frame_ws": keyframe_ops.apply_blend_to_frame,
        "blend_to_neighbors": keyframe_ops.apply_blend_to_neighbors,
        "blend_to_neighbors_ws": keyframe_ops.apply_blend_to_neighbors,
        "blend_to_infinity": keyframe_ops.apply_blend_to_infinity,
        "blend_to_infinity_ws": keyframe_ops.apply_blend_to_infinity,
        "blend_to_undo": keyframe_ops.apply_blend_to_undo,
    },
    "curve": {
        "connect_neighbors": (curve_ops.apply_connect_neighbors, "percent"),
        "ease_in_out": (curve_ops.apply_ease, "ease"),
        "gap_stitcher": (curve_ops.apply_gap_stitcher, "percent"),
        "noise_wave": ((curve_ops.apply_noise, curve_ops.apply_wave), "signed_percent"),
        "pull_push": (curve_ops.apply_pull_push, "percent"),
        "simplify_bake": ((curve_ops.apply_simplify, curve_ops.apply_bake), "signed_percent"),
        "smooth_rough": ((curve_ops.apply_smooth, curve_ops.apply_rough), "signed_percent"),
        "scale_average": (curve_ops.apply_scale, "scale"),
        "scale_selection": (curve_ops.apply_scale, "scale"),
        "scale_default": (curve_ops.apply_scale_default, "scale"),
        "scale_frame": (curve_ops.apply_scale_frame, "scale"),
        "scale_neighbor_left": (curve_ops.apply_scale_neighbor_left, "scale"),
        "scale_neighbor_right": (curve_ops.apply_scale_neighbor_right, "scale"),
    },
    "tangent": {
        "blend_best_guess": "auto",
        "blend_polished": "spline",
        "blend_bounce": "bounce",
        "blend_auto": "auto",
        "blend_spline": "spline",
        "blend_clamped": "clamped",
        "blend_linear": "linear",
        "blend_flat": "flat",
        "blend_flow": "plateau",
        "blend_plateau": "plateau",
    },
    "time": {
        "time_offsetter": time_ops.apply_time_offset,
        "time_offsetter_stagger": time_ops.apply_time_stagger,
    },
}

COMMAND_ONLY_PREVIEW_MODES = {
    "blend_to_frame_ws",
    "blend_to_neighbors_ws",
    "blend_to_infinity_ws",
    "tweener_worldspace",
}


def _can_preview(mode, world_space=False):
    return not (world_space or mode in COMMAND_ONLY_PREVIEW_MODES)


def _resolve_type_key(type_key, mode):
    """Return the registered slider family for a mode, falling back to the requested family."""
    if mode in DISPATCH_MAPS.get(type_key, {}):
        return type_key
    for candidate_type, dispatch in DISPATCH_MAPS.items():
        if mode in dispatch:
            return candidate_type
    return type_key


def _execute_curve_operation(operation_spec, session, value):
    operation, value_mode = operation_spec
    if value_mode == "signed_percent":
        negative_operation, positive_operation = operation
        operation = negative_operation if value < 0 else positive_operation
        operation_value = abs(value) / 100.0 if value < 0 else value / 100.0
    elif value_mode == "ease":
        operation_value = (value + 100) / 200.0
    elif value_mode == "scale":
        operation_value = 1.0 + value / 100.0
    else:
        operation_value = value / 100.0
    return operation(session, None, operation_value)


def create_session(mode):
    """Create a per-interaction slider session for the given mode."""
    mode_def = manager.get_slider_mode(mode)
    tooltip = mode_def.get("tooltip") if mode_def else None
    return utils.SliderSession(
        mode,
        title=toolCommon.humanize_tool_name(mode),
        tooltip=tooltip,
        tint_color=manager.get_slider_color(mode),
    )


def _resolve_session(mode, session):
    """Ensures we have a valid session, switching its mode if necessary."""
    if session is None:
        return create_session(mode), True
    mode_def = manager.get_slider_mode(mode)
    tooltip = mode_def.get("tooltip") if mode_def else None
    session.switch_mode(
        mode,
        title=toolCommon.humanize_tool_name(mode),
        tooltip=tooltip,
        tint_color=manager.get_slider_color(mode),
    )
    return session, False


def start_dragging(mode):
    """Start a public slider drag session."""
    session = create_session(mode)
    session.begin_preview()
    return session


def stop_dragging(session=None):
    """Finish a public slider drag session."""
    if session:
        session.finish()


def _execute_slider_op(type_key, mode, value, world_space=False, session=None):
    """Unified internal dispatcher for all slider operations."""
    type_key = _resolve_type_key(type_key, mode)
    session, should_finish = _resolve_session(mode, session)
    world_space = world_space or mode in COMMAND_ONLY_PREVIEW_MODES
    try:
        if session.preview and not _can_preview(mode, world_space=world_space):
            return session

        dispatch = DISPATCH_MAPS.get(type_key, {})
        func = dispatch.get(mode)

        if not func:
            # Fallback for generic tween if mode not explicitly mapped
            if type_key == "tween":
                if not session.preview:
                    session.ensure_undo_open()
                keyframe_ops.apply_tween(session, value, world_space=world_space)
            return session

        if session.preview and mode == "simplify_bake":
            # Structural previews are rebuilt from the untouched drag-start
            # curve on every value change instead of accumulating edits.
            session.undo_preview_changes()

        if session.preview and mode == "time_offsetter":
            # Re-evaluate every drag position from the untouched curve shape.
            session.undo_preview_changes()

        # Tangent angles/types are edited through Maya commands. Keep their
        # entire live drag in one undo chunk so preview and final commit undo as
        # one operation while still updating continuously.
        if session.preview and (type_key == "tangent" or mode == "time_offsetter_stagger"):
            session.ensure_undo_open()
            session.command_preview = True

        if not session.preview:
            session.ensure_undo_open()

        # Call with appropriate signature based on type
        if type_key == "tween":
            if func is keyframe_ops.apply_blend_to_frame:
                func(session, value, world_space=world_space)
            else:
                func(session, value, world_space)
        elif type_key == "curve":
            _execute_curve_operation(func, session, value)
        elif type_key == "tangent":
            tangent_ops.apply_tangent_type_blend(session, None, func, value / 100.0)
        else:
            func(session, None, value / 10.0)

        return session
    finally:
        if should_finish:
            session.finish()


def execute_tween_slider(mode, value, world_space=False, session=None):
    """Yellow slider modes."""
    return _execute_slider_op("tween", mode, value, world_space, session)


def execute_blend_slider(mode, value, session=None):
    """Green slider modes."""
    return _execute_slider_op("curve", mode, value, session=session)


def execute_tangent_slider(mode, value, session=None):
    """Orange slider modes."""
    return _execute_slider_op("tangent", mode, value, session=session)


def execute_time_modifier(mode, value, session=None):
    """Modes that modify key timing."""
    return _execute_slider_op("time", mode, value, session=session)


def execute_blend_to_frame_with_button_values(value, session=None):
    """Execute the frame-target tween from a value button."""
    return execute_tween_slider("blend_to_frame", value, session=session)
