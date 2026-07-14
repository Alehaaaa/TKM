"""Selection-aware Euler closest-cut filtering."""

import math

from maya import cmds

from TheKeyMachine.core import animation_context
from TheKeyMachine.core import openMayaUtils as open_maya


_COMMAND_ERRORS = (RuntimeError, ValueError, TypeError, AttributeError, KeyError, IndexError)


def _full_turn():
    try:
        angular_unit = cmds.currentUnit(query=True, angle=True)
    except _COMMAND_ERRORS:
        angular_unit = "deg"
    return math.tau if str(angular_unit).lower().startswith("rad") else 360.0


def _closest_turn_offset(value, reference, full_turn):
    if not all(math.isfinite(float(item)) for item in (value, reference, full_turn)) or full_turn <= 0.0:
        return 0.0
    closest_value = open_maya.closest_euler_angle_cut(value, reference)
    if closest_value is not None:
        return float(closest_value) - float(value)
    turns = math.floor(((float(reference) - float(value)) / float(full_turn)) + 0.5)
    return float(turns) * float(full_turn)


def _turn_groups(curve, target_info, full_turn):
    try:
        key_times = [float(value) for value in (cmds.keyframe(curve, query=True, timeChange=True) or [])]
        key_values = [float(value) for value in (cmds.keyframe(curve, query=True, valueChange=True) or [])]
    except _COMMAND_ERRORS:
        return []
    if not key_times or len(key_times) != len(key_values):
        return []
    target_times = set(float(value) for value in animation_context.key_times(curve, target_info))
    if not target_times:
        return []

    groups = []
    group_start = group_end = group_offset = None
    previous_value = None

    def finish_group():
        if group_start is not None:
            groups.append((group_start, group_end, group_offset))

    for key_time, key_value in zip(key_times, key_values):
        if key_time not in target_times:
            finish_group()
            group_start = group_end = group_offset = None
            previous_value = key_value
            continue
        offset = 0.0 if previous_value is None else _closest_turn_offset(key_value, previous_value, full_turn)
        filtered_value = key_value + offset
        if abs(offset) <= 1e-10:
            finish_group()
            group_start = group_end = group_offset = None
        elif group_start is not None and abs(offset - group_offset) <= 1e-10:
            group_end = key_time
        else:
            finish_group()
            group_start = group_end = key_time
            group_offset = offset
        previous_value = filtered_value
    finish_group()
    return groups


def apply(curves, target_info):
    """Apply closest-cut filtering only to keys in ``target_info``."""
    changed_groups = 0
    with animation_context.preserve_key_selection():
        for curve in curves or []:
            for start_time, end_time, offset in _turn_groups(curve, target_info, _full_turn()):
                cmds.keyframe(
                    curve,
                    edit=True,
                    time=(start_time, end_time),
                    relative=True,
                    valueChange=offset,
                )
                changed_groups += 1
    return changed_groups
