"""
TheKeyMachine - Slider Manager

Main entry point for sliders. Connects UI inputs to slider logic
using a robust dispatcher pattern to avoid complex if-elif chains.
"""

from . import utils
from . import curve_ops
from . import keyframe_ops
from TheKeyMachine.tools import common as toolCommon
import TheKeyMachine.mods.helperMod as helper


SLIDER_MODE_TOOLTIPS = {
    "tweener": helper.tweener_tooltip_text,
    "tweener_worldspace": helper.tweener_world_space_tooltip_text,
    "blend_to_buffer": helper.blend_tooltip_text,
    "blend_to_default": helper.blend_to_default_tooltip_text,
    "blend_to_ease": helper.blend_tooltip_text,
    "blend_to_frame": helper.blend_to_frame_tooltip_text,
    "blend_to_frame_ws": helper.blend_to_frame_tooltip_text,
    "blend_to_neighbors": helper.blend_tooltip_text,
    "blend_to_neighbors_ws": helper.blend_tooltip_text,
    "blend_to_infinity": helper.blend_tooltip_text,
    "blend_to_infinity_ws": helper.blend_tooltip_text,
    "blend_to_undo": helper.blend_tooltip_text,
    "connect_neighbors": helper.blend_tooltip_text,
    "ease_in_out": helper.blend_tooltip_text,
    "gap_stitcher": helper.blend_tooltip_text,
    "noise_wave": helper.blend_tooltip_text,
    "pull_push": helper.pull_push_tooltip_text,
    "simplify_bake": helper.blend_tooltip_text,
    "smooth_rough": helper.blend_tooltip_text,
    "time_offsetter": helper.blend_tooltip_text,
    "time_offsetter_stagger": helper.blend_tooltip_text,
    "scale_average": helper.blend_tooltip_text,
    "scale_selection": helper.blend_tooltip_text,
    "scale_default": helper.blend_tooltip_text,
    "scale_frame": helper.blend_tooltip_text,
    "scale_neighbor_left": helper.blend_tooltip_text,
    "scale_neighbor_right": helper.blend_tooltip_text,
    "blend_best_guess": helper.auto_tangent_tooltip_text,
    "blend_polished": helper.spline_tangent_tooltip_text,
    "blend_bounce": helper.step_tangent_tooltip_text,
    "blend_clamped": helper.step_tangent_tooltip_text,
    "blend_plateau": helper.auto_tangent_tooltip_text,
    "blend_auto": helper.auto_tangent_tooltip_text,
    "blend_spline": helper.spline_tangent_tooltip_text,
    "blend_linear": helper.linear_tangent_tooltip_text,
    "blend_flat": helper.step_tangent_tooltip_text,
    "blend_flow": helper.auto_tangent_tooltip_text,
}


def _start_mode_drag(mode):
    utils.start_dragging(
        title=toolCommon.humanize_tool_name(mode),
        tooltip_template=SLIDER_MODE_TOOLTIPS.get(mode),
    )

# ---------------------------------------------------------------------------------------------------------------------
#                                              Standard Dispatcher Maps                                               #
# ---------------------------------------------------------------------------------------------------------------------

# TWEEN MODES (Yellow Slider)
TWEEN_MODIFIER_DISPATCH = {
    "tweener": lambda v, ws: keyframe_ops.execute_tween(v, world_space=ws),
    "tweener_worldspace": lambda v, ws: keyframe_ops.execute_tween(v, world_space=True),
    "blend_to_buffer": lambda v, ws: keyframe_ops.execute_blend_to_buffer(v, world_space=ws),
    "blend_to_default": lambda v, ws: keyframe_ops.execute_blend_to_default(v, world_space=ws),
    "blend_to_ease": lambda v, ws: keyframe_ops.execute_blend_to_ease(v, world_space=ws),
    "blend_to_frame": lambda v, ws: keyframe_ops.execute_blend_to_frame(v, world_space=ws),
    "blend_to_frame_ws": lambda v, ws: keyframe_ops.execute_blend_to_frame(v, world_space=True),
    "blend_to_neighbors": lambda v, ws: keyframe_ops.execute_blend_to_neighbors(v, world_space=ws),
    "blend_to_neighbors_ws": lambda v, ws: keyframe_ops.execute_blend_to_neighbors(v, world_space=True),
    "blend_to_infinity": lambda v, ws: keyframe_ops.execute_blend_to_infinity(v, world_space=ws),
    "blend_to_infinity_ws": lambda v, ws: keyframe_ops.execute_blend_to_infinity(v, world_space=True),
    "blend_to_undo": lambda v, ws: keyframe_ops.execute_blend_to_undo(v, world_space=ws),
}

# BLEND/MODIFIER MODES (Green Slider)
CURVE_MODIFIER_DISPATCH = {
    "connect_neighbors": lambda c, v: curve_ops.apply_connect_neighbors(c, abs(v) / 100.0),
    "ease_in_out": lambda c, v: curve_ops.apply_ease(c, (v + 100) / 200.0),
    "gap_stitcher": lambda c, v: curve_ops.apply_gap_stitcher(c, abs(v) / 100.0),
    "noise_wave": lambda c, v: curve_ops.apply_noise(c, abs(v) / 60.0) if v < 0 else curve_ops.apply_wave(c, v / 30.0),
    "pull_push": lambda c, v: curve_ops.apply_pull_push(c, v / 100.0),
    "simplify_bake": lambda c, v: curve_ops.apply_simplify(c, abs(v) / 100.0) if v < 0 else curve_ops.apply_bake(c, v / 100.0),
    "smooth_rough": lambda c, v: curve_ops.apply_smooth(c, abs(v) / 100.0) if v < 0 else curve_ops.apply_noise(c, v / 60.0),
    "scale_average": lambda c, v: curve_ops.apply_scale(c, 1.0 + (v / 100.0)),
    "scale_selection": lambda c, v: curve_ops.apply_scale_selection(c, 1.0 + (v / 100.0)),
    "scale_default": lambda c, v: curve_ops.apply_scale_default(c, 1.0 + (v / 100.0)),
    "scale_frame": lambda c, v: curve_ops.apply_scale_frame(c, 1.0 + (v / 100.0)),
    "scale_neighbor_left": lambda c, v: curve_ops.apply_scale_neighbor_left(c, 1.0 + (v / 100.0)),
    "scale_neighbor_right": lambda c, v: curve_ops.apply_scale_neighbor_right(c, 1.0 + (v / 100.0)),
}

# TANGENT MODES (Orange Slider)
TANGENT_BLEND_DISPATCH = {
    "blend_best_guess": lambda c, v: curve_ops.apply_smooth(c, max(0.0, v)),
    "blend_polished": lambda c, v: curve_ops.apply_smooth(c, max(0.0, v)),
    "blend_bounce": lambda c, v: curve_ops.apply_wave(c, abs(v) * 2.0),
    "blend_auto": lambda c, v: curve_ops.apply_smooth(c, v / 2.0),
    "blend_spline": lambda c, v: curve_ops.apply_smooth(c, v / 2.0),
    "blend_clamped": lambda c, v: curve_ops.apply_smooth(c, max(0.0, v)),
    "blend_linear": lambda c, v: curve_ops.apply_linear(c, v),
    "blend_flat": lambda c, v: curve_ops.apply_flat(c, v),
    "blend_flow": lambda c, v: curve_ops.apply_ease(c, v),
    "blend_plateau": lambda c, v: curve_ops.apply_flat(c, max(0.0, v)),
}

# ---------------------------------------------------------------------------------------------------------------------
#                                                Entry Point Functions                                                #
# ---------------------------------------------------------------------------------------------------------------------


def execute_tween(mode, value, world_space=False):
    """Entry point for the Yellow slider modes."""
    _start_mode_drag(mode)
    func = TWEEN_MODIFIER_DISPATCH.get(mode)
    if func:
        func(value, world_space)
    else:
        # Default behavior
        keyframe_ops.execute_tween(value, world_space=world_space)


def execute_curve_modifier(mode, value):
    """Dispatcher for the Green slider modes."""
    _start_mode_drag(mode)
    func = CURVE_MODIFIER_DISPATCH.get(mode)
    if func:
        curves = utils.get_target_curves()
        if curves:
            func(curves, value)


def execute_tangent_blend(mode, value):
    """Dispatcher for the Orange slider modes."""
    _start_mode_drag(mode)
    func = TANGENT_BLEND_DISPATCH.get(mode)
    if func:
        curves = utils.get_target_curves()
        if curves:
            func(curves, value / 100.0)


def stop_dragging():
    """Proxy for utils.stop_dragging."""
    utils.stop_dragging()
