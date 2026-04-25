"""
TheKeyMachine - Slider mode operations

Mode-facing slider functions.

This is intentionally a thin adapter: public dispatch calls execute_* here,
while keyframe editing details stay in keyframe_ops and curve editing details
stay in curve_ops.
"""

from . import curve_ops
from . import keyframe_ops
from . import tangent_ops
from . import time_ops


def execute_tween(session, value, world_space=False):
    return keyframe_ops.apply_tween(session, value, world_space=world_space)


def execute_blend_to_neighbors(session, percentage, world_space=False):
    return keyframe_ops.apply_blend_to_neighbors(session, percentage, world_space=world_space)


def execute_blend_to_ease(session, percentage, world_space=False):
    return keyframe_ops.apply_blend_to_ease(session, percentage, world_space=world_space)


def execute_blend_to_default(session, percentage, world_space=False):
    return keyframe_ops.apply_blend_to_default(session, percentage, world_space=world_space)


def execute_blend_to_key(session, percentage, objs=None):
    return keyframe_ops.apply_blend_to_key(session, percentage, objs=objs)


def execute_blend_to_frame(session, percentage, left_frame=None, right_frame=None, objs=None, world_space=False):
    return keyframe_ops.apply_blend_to_frame(
        session,
        percentage,
        left_frame=left_frame,
        right_frame=right_frame,
        objs=objs,
        world_space=world_space,
    )


def execute_blend_to_infinity(session, percentage, world_space=False):
    return keyframe_ops.apply_blend_to_infinity(session, percentage, world_space=world_space)


def execute_blend_to_buffer(session, percentage, world_space=False):
    return keyframe_ops.apply_blend_to_buffer(session, percentage, world_space=world_space)


def execute_blend_to_undo(session, percentage, world_space=False):
    return keyframe_ops.apply_blend_to_undo(session, percentage, world_space=world_space)


# ---------------------------------------------------------------------------------------------------------------------
#                                             Blend / Curve Modifier Modes                                            #
# ---------------------------------------------------------------------------------------------------------------------


def execute_connect_neighbors(session, curves, value):
    return curve_ops.apply_connect_neighbors(session, curves, abs(value) / 100.0)


def execute_ease_in_out(session, curves, value):
    return curve_ops.apply_ease(session, curves, (value + 100) / 200.0)


def execute_gap_stitcher(session, curves, value):
    return curve_ops.apply_gap_stitcher(session, curves, abs(value) / 100.0)


def execute_noise_wave(session, curves, value):
    if value < 0:
        return curve_ops.apply_noise(session, curves, abs(value) / 60.0)
    return curve_ops.apply_wave(session, curves, value / 30.0)


def execute_pull_push(session, curves, value):
    return curve_ops.apply_pull_push(session, curves, value / 100.0)


def execute_simplify_bake(session, curves, value):
    if value < 0:
        return curve_ops.apply_simplify(session, curves, abs(value) / 100.0)
    return curve_ops.apply_bake(session, curves, value / 100.0)


def execute_smooth_rough(session, curves, value):
    if value < 0:
        return curve_ops.apply_smooth(session, curves, abs(value) / 100.0)
    return curve_ops.apply_noise(session, curves, value / 60.0)


def execute_scale_average(session, curves, value):
    return curve_ops.apply_scale(session, curves, 1.0 + (value / 100.0))


def execute_scale_selection(session, curves, value):
    return curve_ops.apply_scale_selection(session, curves, 1.0 + (value / 100.0))


def execute_scale_default(session, curves, value):
    return curve_ops.apply_scale_default(session, curves, 1.0 + (value / 100.0))


def execute_scale_frame(session, curves, value):
    return curve_ops.apply_scale_frame(session, curves, 1.0 + (value / 100.0))


def execute_scale_neighbor_left(session, curves, value):
    return curve_ops.apply_scale_neighbor_left(session, curves, 1.0 + (value / 100.0))


def execute_scale_neighbor_right(session, curves, value):
    return curve_ops.apply_scale_neighbor_right(session, curves, 1.0 + (value / 100.0))


# ---------------------------------------------------------------------------------------------------------------------
#                                                  Tangent Blend Modes                                                #
# ---------------------------------------------------------------------------------------------------------------------


def execute_blend_best_guess(session, curves, value):
    return tangent_ops.apply_tangent_type_blend(session, curves, "auto", value)


def execute_blend_polished(session, curves, value):
    return tangent_ops.apply_tangent_type_blend(session, curves, "spline", value)


def execute_blend_bounce(session, curves, value):
    return tangent_ops.apply_tangent_type_blend(session, curves, "step", value)


def execute_blend_auto(session, curves, value):
    return tangent_ops.apply_tangent_type_blend(session, curves, "auto", value)


def execute_blend_spline(session, curves, value):
    return tangent_ops.apply_tangent_type_blend(session, curves, "spline", value)


def execute_blend_clamped(session, curves, value):
    return tangent_ops.apply_tangent_type_blend(session, curves, "clamped", value)


def execute_blend_linear(session, curves, value):
    return tangent_ops.apply_tangent_type_blend(session, curves, "linear", value)


def execute_blend_flat(session, curves, value):
    return tangent_ops.apply_tangent_type_blend(session, curves, "flat", value)


def execute_blend_flow(session, curves, value):
    return tangent_ops.apply_tangent_type_blend(session, curves, "plateau", value)


def execute_blend_plateau(session, curves, value):
    return tangent_ops.apply_tangent_type_blend(session, curves, "plateau", value)


# ---------------------------------------------------------------------------------------------------------------------
#                                                     Time Modes                                                      #
# ---------------------------------------------------------------------------------------------------------------------


def execute_time_offsetter(session, curves, value):
    # Convert slider -100..100 to frame offset (e.g. -10..10 frames)
    return time_ops.apply_time_offset(session, curves, value / 10.0)


def execute_time_stagger(session, curves, value):
    return time_ops.apply_time_stagger(session, curves, value / 10.0)
