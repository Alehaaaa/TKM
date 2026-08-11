from maya import cmds

from TheKeyMachine.core import animation_context, curveFitting, toolbox
from TheKeyMachine.mods import selectionMod
from TheKeyMachine.mods import settingsMod as settings
from TheKeyMachine.tools import common as toolCommon
from TheKeyMachine.widgets import timeline
from TheKeyMachine.widgets import util as wutil

CYCLE_MATCH_MODE_SETTING = "cycle_match_mode"
CYCLE_MATCH_MODE_ORIENTATION = "tangent_orientation"
CYCLE_MATCH_MODE_KEY_COPY = "key_copy"
CYCLE_MATCH_MODES = (CYCLE_MATCH_MODE_ORIENTATION, CYCLE_MATCH_MODE_KEY_COPY)


def get_cycle_match_mode():
    mode = settings.get_setting(CYCLE_MATCH_MODE_SETTING, CYCLE_MATCH_MODE_ORIENTATION)
    return mode if mode in CYCLE_MATCH_MODES else CYCLE_MATCH_MODE_ORIENTATION


def set_cycle_match_mode(mode):
    if mode not in CYCLE_MATCH_MODES:
        mode = CYCLE_MATCH_MODE_ORIENTATION
    settings.set_setting(CYCLE_MATCH_MODE_SETTING, mode)


def _normalize_frames(frames):
    normalized = []
    for frame in frames or ():
        try:
            normalized.append(float(frame))
        except (TypeError, ValueError):
            continue
    return sorted(set(normalized))


def _filter_targets_by_scope(targets, key_scope):
    targets = {curve: list(frames or ()) for curve, frames in (targets or {}).items() if frames}
    if key_scope not in ("first", "last") or not targets:
        return targets
    all_frames = sorted({frame for frames in targets.values() for frame in frames})
    if not all_frames:
        return {}
    target_frame = all_frames[0] if key_scope == "first" else all_frames[-1]
    return {curve: [target_frame] for curve, frames in targets.items() if target_frame in frames}


def _collect_targets(key_scope="selection"):
    default_mode = "all_animation" if key_scope == "all" else "current_frame"
    target_info = animation_context.resolve_tool_context(
        default_mode=default_mode,
        include_channels=True,
        include_shapes=True,
        resolve_curves=True,
    )
    if not target_info.get("target_objects") and not target_info.get("target_plugs"):
        return {}, target_info.get("time_context")

    selected = []
    time_context = target_info.get("time_context")
    if key_scope != "all" and time_context and time_context.mode == "graph_editor_keys":
        selected = target_info.get("selected_keyframes") or []
    if selected:
        by_curve = {}
        for curve, frame in selected:
            by_curve.setdefault(curve, set()).add(float(frame))
        targets = {curve: sorted(frames) for curve, frames in by_curve.items()}
    else:
        targets = {
            curve: _normalize_frames(animation_context.key_times(curve, target_info))
            for curve in target_info["selected_curves"]
        }
    return _filter_targets_by_scope(targets, key_scope), time_context


def _target_range(targets):
    frames = sorted({frame for curve_frames in targets.values() for frame in curve_frames})
    return (frames[0], frames[-1]) if frames else None


def _set_tangent_on_target(target, tangent_type, frames, handle_mode="both"):
    frames = list(frames) if isinstance(frames, (list, tuple, set)) else [frames]
    kwargs = {"time": [(frame, frame) for frame in frames]}
    if handle_mode in ("both", "out"):
        kwargs["ott"] = tangent_type
    if handle_mode in ("both", "in"):
        if tangent_type == "step":
            if handle_mode == "in":
                kwargs["itt"] = "stepnext"
        else:
            kwargs["itt"] = tangent_type
    if len(kwargs) > 1:
        cmds.keyTangent(target, **kwargs)


def set_maya_default(tangent_type):
    cmds.keyTangent(**{"global": True, "inTangentType": tangent_type, "outTangentType": tangent_type})


def set_tangent(tangent_type, handle_mode="both", key_scope="selection", tint_color=None):
    targets, time_context = _collect_targets(key_scope)
    if not targets:
        return animation_context.notify_empty("keys", "edit")
    timerange = _target_range(targets) or (time_context.timerange if time_context else None)
    tint = timeline.begin_timeline_tint(
        timerange=timerange,
        color=tint_color
        or toolbox.get_tool_tint_color("tangent_{}".format(tangent_type)),
        key="tangent_{}".format(tangent_type),
    ) if timerange else None
    try:
        operation = toolCommon.current_tool_operation()
        if operation:
            operation.set_total(len(targets))
        for curve, frames in targets.items():
            if operation and operation.cancelled:
                return
            _set_tangent_on_target(curve, tangent_type, frames, handle_mode)
            if operation:
                operation.step()
    finally:
        if tint:
            tint.finish()


def _filter_bouncy_targets(targets, key_scope):
    if key_scope not in ("first", "last"):
        return targets
    frames = sorted({float(frame) for _curve, frame in targets})
    if not frames:
        return []
    target = frames[0] if key_scope == "first" else frames[-1]
    return [(curve, frame) for curve, frame in targets if float(frame) == target]


def set_bouncy(handle_mode="both", key_scope="selection", tint_color=None, angle_adjustment_factor=1.3):
    default_mode = "all_animation" if key_scope == "all" else "current_frame"
    target_info = animation_context.resolve_tool_context(
        default_mode=default_mode,
        include_channels=True,
        include_shapes=True,
        resolve_curves=True,
    )
    selected = target_info.get("selected_keyframes") or []
    if selected and key_scope != "all":
        targets = [(curve, float(frame)) for curve, frame in selected]
    else:
        targets = []
        seen = set()
        for curve in target_info["selected_curves"]:
            for frame in animation_context.key_times(curve, target_info):
                item = (curve, float(frame))
                if item not in seen:
                    seen.add(item)
                    targets.append(item)
    targets = _filter_bouncy_targets(targets, key_scope)
    if not targets:
        return animation_context.notify_empty("keys", "edit")

    frames = sorted({float(frame) for _curve, frame in targets})
    timerange = (frames[0], frames[-1]) if frames else None
    tint = timeline.begin_timeline_tint(
        timerange=timerange,
        color=tint_color or toolbox.get_tool_tint_color("tangent_bouncy"),
        key="tangent_bouncy",
    ) if timerange else None
    try:
        operation = toolCommon.current_tool_operation()
        if operation:
            operation.set_total(len(targets))
        for curve, frame in targets:
            if operation and operation.cancelled:
                return
            in_angle, out_angle = curveFitting.bouncy_tangent_angles(
                curve, frame, angle_adjustment_factor=angle_adjustment_factor
            )
            kwargs = {"time": (frame, frame), "edit": True, "lock": False, "absolute": True}
            if handle_mode in ("both", "in"):
                kwargs["inAngle"] = in_angle
            if handle_mode in ("both", "out"):
                kwargs["outAngle"] = out_angle
            cmds.keyTangent(curve, **kwargs)
            if operation:
                operation.step()
    finally:
        if tint:
            tint.finish()


def _copy_key_state(curve, source_time, target_time, copy_value=True):
    """Copy tangent orientation (and, optionally, the key value) between keys.

    copy_value=False (the "Tangents Only" mode) leaves each key's own value
    untouched and only matches tangent type/angles, so a cycle's start and
    end poses stay whatever they were animated to be -- only their tangents
    are made to agree. copy_value=True (the "Tangents + Value" mode) also
    overwrites the target key's value, fully replacing it with the source's.
    """
    if copy_value:
        value = cmds.keyframe(curve, time=(source_time, source_time), query=True, valueChange=True)[0]
        cmds.keyframe(curve, time=(target_time, target_time), valueChange=value)
    in_type = cmds.keyTangent(curve, time=(source_time,), query=True, inTangentType=True)[0]
    out_type = cmds.keyTangent(curve, time=(source_time,), query=True, outTangentType=True)[0]
    in_angle = cmds.keyTangent(curve, time=(source_time,), query=True, inAngle=True)[0]
    out_angle = cmds.keyTangent(curve, time=(source_time,), query=True, outAngle=True)[0]
    cmds.keyTangent(curve, time=(target_time,), edit=True, inTangentType=in_type, outTangentType=out_type)
    cmds.keyTangent(curve, time=(target_time,), edit=True, inAngle=in_angle, outAngle=out_angle)


def _selected_end_by_curve(target_info):
    """Map each curve with an unambiguous end selected to "first" or "last".

    Only a curve whose Graph Editor selection sits on exactly one of its two
    end keys (not both, not some middle key) gets an entry -- that single
    selected end is "current" and will be overwritten to match the opposite
    end.
    """
    by_curve = {}
    for curve, frame in target_info.get("selected_keyframes") or ():
        by_curve.setdefault(curve, set()).add(float(frame))

    selected_end = {}
    for curve, frames in by_curve.items():
        first = cmds.findKeyframe(curve, which="first")
        last = cmds.findKeyframe(curve, which="last")
        at_first = first in frames
        at_last = last in frames
        if at_first and not at_last:
            selected_end[curve] = "first"
        elif at_last and not at_first:
            selected_end[curve] = "last"
    return selected_end


def match_cycle(target_key="last"):
    """Match the current end of the cycle to its opposite end.

    When a curve has exactly one end key selected in the Graph Editor, that
    key is treated as "current" and gets overwritten to match the opposite
    end -- regardless of which menu entry was used. Curves with no such
    selection fall back to target_key ("first" or "last") naming which end
    is "current".
    """
    target_info = animation_context.resolve_tool_context(
        default_mode="all_animation",
        include_channels=True,
        include_shapes=True,
        resolve_curves=True,
    )
    curves = target_info["selected_curves"]
    selected_end_by_curve = _selected_end_by_curve(target_info)
    copy_value = get_cycle_match_mode() == CYCLE_MATCH_MODE_KEY_COPY
    operation = toolCommon.current_tool_operation()
    if operation:
        operation.set_total(len(curves))
    for curve in curves:
        if operation and operation.cancelled:
            return
        first = cmds.findKeyframe(curve, which="first")
        last = cmds.findKeyframe(curve, which="last")
        curve_target_key = selected_end_by_curve.get(curve, target_key)
        if curve_target_key == "first":
            _copy_key_state(curve, last, first, copy_value=copy_value)
        else:
            _copy_key_state(curve, first, last, copy_value=copy_value)
        if operation:
            operation.step()
