"""
TheKeyMachine - Slider Manager

Main entry point for sliders. Connects UI inputs to slider logic
using a robust dispatcher pattern to avoid complex if-elif chains.
"""

from . import utils
from . import curve_ops
from . import keyframe_ops

# ---------------------------------------------------------------------------------------------------------------------
#                                              Standard Dispatcher Maps                                               #
# ---------------------------------------------------------------------------------------------------------------------

# TWEEN MODES (Yellow Slider)
TWEEN_MODIFIER_DISPATCH = {
    "tweener": lambda v, ws: keyframe_ops.execute_tween(v, world_space=ws),
    "tweener_worldspace": lambda v, ws: keyframe_ops.execute_tween(v, world_space=True),
    "blend_to_buffer": lambda v, ws: keyframe_ops.execute_blend_to_key(v),  # Placeholder logic
    "blend_to_default": lambda v, ws: keyframe_ops.execute_blend_to_default(v, world_space=ws),
    "blend_to_frame": lambda v, ws: keyframe_ops.execute_blend_to_frame(v),
    "blend_to_neighbors": lambda v, ws: keyframe_ops.execute_blend_to_neighbors(v, world_space=ws),
    "blend_to_neighbors_ws": lambda v, ws: keyframe_ops.execute_blend_to_neighbors(v, world_space=True),
}

# BLEND/MODIFIER MODES (Green Slider)
CURVE_MODIFIER_DISPATCH = {
    "connect_neighbors": lambda c, v: curve_ops.apply_smooth(c, v / 100.0),  # Placeholder
    "ease_in_out": lambda c, v: curve_ops.apply_ease(c, (v + 100) / 200.0),
    "noise_wave": lambda c, v: curve_ops.apply_noise(c, abs(v) / 200.0) if v < 0 else curve_ops.apply_wave(c, v / 40.0),
    "smooth_rough": lambda c, v: curve_ops.apply_smooth(c, abs(v) / 200.0) if v < 0 else None,
    "scale_average": lambda c, v: curve_ops.apply_scale(c, 0.7 + ((v + 100) / 200.0 * 0.6)),
    "scale_selection": lambda c, v: curve_ops.apply_scale_selection(c, 0.7 + ((v + 100) / 200.0 * 0.6)),
}

# TANGENT MODES (Orange Slider)
TANGENT_BLEND_DISPATCH = {
    "blend_auto": lambda c, v: curve_ops.apply_smooth(c, v / 2.0),
    "blend_spline": lambda c, v: curve_ops.apply_smooth(c, v / 2.0),
    "blend_linear": lambda c, v: curve_ops.apply_linear(c, v),
    "blend_flat": lambda c, v: curve_ops.apply_flat(c, v),
    "blend_flow": lambda c, v: curve_ops.apply_ease(c, v),
}

# ---------------------------------------------------------------------------------------------------------------------
#                                                Entry Point Functions                                                #
# ---------------------------------------------------------------------------------------------------------------------


def execute_tween(mode, value, world_space=False):
    """Entry point for the Yellow slider modes."""
    func = TWEEN_MODIFIER_DISPATCH.get(mode)
    if func:
        func(value, world_space)
    else:
        # Default behavior
        keyframe_ops.execute_tween(value, world_space=world_space)


def execute_curve_modifier(mode, value):
    """Dispatcher for the Green slider modes."""
    utils.start_dragging()
    func = CURVE_MODIFIER_DISPATCH.get(mode)
    if func:
        curves = utils.get_target_curves()
        if curves:
            func(curves, value)


def execute_tangent_blend(mode, value):
    """Dispatcher for the Orange slider modes."""
    func = TANGENT_BLEND_DISPATCH.get(mode)
    if func:
        curves = utils.get_target_curves()
        if curves:
            func(curves, value / 100.0)


def stop_dragging():
    """Proxy for utils.stop_dragging."""
    utils.stop_dragging()
