"""
TheKeyMachine - Sliders public API

Public entry points used by toolbar widgets, hotkeys, and trigger commands.
"""

from . import manager
from . import sliderMod
from . import utils
from TheKeyMachine.tools import common as toolCommon


# Dispatch maps for various slider types
DISPATCH_MAPS = {
    "tween": {
        "tweener": sliderMod.execute_tweener,
        "tweener_worldspace": lambda s, v, ws: sliderMod.execute_tweener(s, v, world_space=True),
        "blend_to_buffer": sliderMod.execute_blend_to_buffer,
        "blend_to_default": sliderMod.execute_blend_to_default,
        "blend_to_ease": sliderMod.execute_blend_to_ease,
        "blend_to_frame": sliderMod.execute_blend_to_frame,
        "blend_to_frame_ws": lambda s, v, ws: sliderMod.execute_blend_to_frame(s, v, world_space=True),
        "blend_to_neighbors": sliderMod.execute_blend_to_neighbors,
        "blend_to_neighbors_ws": lambda s, v, ws: sliderMod.execute_blend_to_neighbors(s, v, world_space=True),
        "blend_to_infinity": sliderMod.execute_blend_to_infinity,
        "blend_to_infinity_ws": lambda s, v, ws: sliderMod.execute_blend_to_infinity(s, v, world_space=True),
        "blend_to_undo": sliderMod.execute_blend_to_undo,
    },
    "curve": {
        "connect_neighbors": sliderMod.execute_connect_neighbors,
        "ease_in_out": sliderMod.execute_ease_in_out,
        "gap_stitcher": sliderMod.execute_gap_stitcher,
        "noise_wave": sliderMod.execute_noise_wave,
        "pull_push": sliderMod.execute_pull_push,
        "simplify_bake": sliderMod.execute_simplify_bake,
        "smooth_rough": sliderMod.execute_smooth_rough,
        "scale_average": sliderMod.execute_scale_average,
        "scale_selection": sliderMod.execute_scale_selection,
        "scale_default": sliderMod.execute_scale_default,
        "scale_frame": sliderMod.execute_scale_frame,
        "scale_neighbor_left": sliderMod.execute_scale_neighbor_left,
        "scale_neighbor_right": sliderMod.execute_scale_neighbor_right,
    },
    "tangent": {
        "blend_best_guess": sliderMod.execute_blend_best_guess,
        "blend_polished": sliderMod.execute_blend_polished,
        "blend_bounce": sliderMod.execute_blend_bounce,
        "blend_auto": sliderMod.execute_blend_auto,
        "blend_spline": sliderMod.execute_blend_spline,
        "blend_clamped": sliderMod.execute_blend_clamped,
        "blend_linear": sliderMod.execute_blend_linear,
        "blend_flat": sliderMod.execute_blend_flat,
        "blend_flow": sliderMod.execute_blend_flow,
        "blend_plateau": sliderMod.execute_blend_plateau,
    },
    "time": {
        "time_offsetter": sliderMod.execute_time_offsetter,
        "time_offsetter_stagger": sliderMod.execute_time_stagger,
    },
}


def _resolve_type_key(type_key, mode):
    """Return the registered slider family for a mode, falling back to the requested family."""
    if mode in DISPATCH_MAPS.get(type_key, {}):
        return type_key
    for candidate_type, dispatch in DISPATCH_MAPS.items():
        if mode in dispatch:
            return candidate_type
    return type_key


def create_session(mode):
    """Create a per-interaction slider session for the given mode."""
    return utils.SliderSession(
        mode,
        title=toolCommon.humanize_tool_name(mode),
        tooltip_template=manager.SLIDER_MODE_TOOLTIPS.get(mode),
    )


def _resolve_session(mode, session):
    """Ensures we have a valid session, switching its mode if necessary."""
    if session is None:
        return create_session(mode), True
    session.switch_mode(
        mode,
        title=toolCommon.humanize_tool_name(mode),
        tooltip_template=manager.SLIDER_MODE_TOOLTIPS.get(mode),
    )
    return session, False


def start_dragging(mode):
    """Public entry to start a drag session."""
    return create_session(mode)


def stop_dragging(session=None):
    """Public entry to finalize a drag session."""
    if session:
        session.finish()


def _execute_slider_op(type_key, mode, value, world_space=False, session=None):
    """Unified internal dispatcher for all slider operations."""
    type_key = _resolve_type_key(type_key, mode)
    session, should_finish = _resolve_session(mode, session)
    try:
        dispatch = DISPATCH_MAPS.get(type_key, {})
        func = dispatch.get(mode)

        if not func:
            # Fallback for generic tween if mode not explicitly mapped
            if type_key == "tween":
                session.ensure_undo_open()
                sliderMod.execute_tweener(session, value, world_space=world_space)
            return session

        session.ensure_undo_open()

        # Call with appropriate signature based on type
        if type_key == "tween":
            func(session, value, world_space)
        elif type_key == "tangent":
            func(session, None, value / 100.0)
        else:
            # Curve and time ops both expect the raw slider percentage.
            func(session, None, value)

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
    """Legacy helper for frame buttons."""
    return execute_tween_slider("blend_to_frame", value, session=session)
