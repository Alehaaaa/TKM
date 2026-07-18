from maya import cmds

from TheKeyMachine.core import animation_context
from TheKeyMachine.mods import settingsMod as settings
from TheKeyMachine.tools import common as toolCommon
from TheKeyMachine.widgets import util as wutil


def nudge_value(default=1):
    try:
        return int(settings.get_setting("nudge_value", default))
    except (TypeError, ValueError):
        return default


def _unique(values):
    return list(dict.fromkeys(values or ()))


def _scene_curves():
    curves = []
    for curve_type in ("animCurveTL", "animCurveTA", "animCurveTT", "animCurveTU"):
        curves.extend(cmds.ls(type=curve_type) or [])
    return _unique(curves)


def _target_curves():
    target_info = animation_context.resolve_targets(default_mode="all_animation", ordered_selection=True, long_names=True)
    curves = _unique(target_info.get("selected_curves"))
    if curves:
        return curves
    objects = target_info.get("target_objects") or []
    return _unique(cmds.keyframe(objects, query=True, name=True) if objects else [])


def _move_current_time(offset):
    try:
        cmds.currentTime(cmds.currentTime(query=True) + int(offset))
    except (RuntimeError, TypeError, ValueError):
        pass


def nudge_all_keys(direction):
    curves = _target_curves()
    if not curves:
        return wutil.make_inViewMessage("No animation curves found.")
    offset = nudge_value() * int(direction)
    if not offset:
        return
    with toolCommon.tool_operation(tool_id="nudge_all_keys", label="Nudge All Keys", undo=True):
        cmds.keyframe(curves, edit=True, relative=True, includeUpperBound=True, option="over", timeChange=offset)
        _move_current_time(offset)


def nudge_scene(direction):
    curves = _scene_curves()
    if not curves:
        return wutil.make_inViewMessage("No animation curves found in the scene.")
    offset = nudge_value() * int(direction)
    if not offset:
        return
    with toolCommon.tool_operation(tool_id="nudge_scene_keys", label="Nudge Scene Keys", undo=True):
        cmds.keyframe(curves, edit=True, relative=True, includeUpperBound=True, option="over", timeChange=offset)
        _move_current_time(offset)


def shift_inbetween(direction, scene=False):
    count = nudge_value() * int(direction)
    if not count:
        return
    curves = _scene_curves() if scene else None
    if scene and not curves:
        return wutil.make_inViewMessage("No animation curves found in the scene.")
    current = cmds.currentTime(query=True)
    with toolCommon.tool_operation(tool_id="nudge_inbetween", label="Shift Inbetween", undo=True):
        args = (curves,) if curves else ()
        if not scene and not cmds.keyframe(query=True):
            return
        cmds.keyframe(*args, edit=True, time=("{}:".format(current + 1),), relative=True, timeChange=count, option="over")


def nudge_range(direction):
    offset = nudge_value() * int(direction)
    if not offset:
        return
    current_time = cmds.currentTime(query=True)
    target_info = animation_context.resolve_targets(default_mode="all_animation", ordered_selection=True, long_names=True)
    selection = target_info["target_objects"]
    target_plugs = target_info["target_plugs"]
    target_curves = target_info["selected_curves"]
    time_context = target_info["time_context"]
    start_frame, end_frame = time_context.timerange

    with toolCommon.tool_operation(tool_id="nudge_range", label="Nudge Keys", undo=True):
        if target_info["has_graph_keys"]:
            cmds.keyframe(edit=True, animation="keys", relative=True, includeUpperBound=True, option="over", timeChange=offset)
            _move_current_time(offset)
            return
        if time_context.mode == "time_slider_range":
            curves = _unique(target_curves)
            if not curves and selection:
                curves = cmds.keyframe(selection, query=True, name=True) or []
            curves = [curve for curve in curves if cmds.keyframe(curve, query=True, time=(start_frame, end_frame))]
            if not curves:
                return
            cmds.keyframe(curves, edit=True, relative=True, includeUpperBound=True, option="over",
                          time=(start_frame, end_frame), timeChange=offset)
            cmds.currentTime(current_time + offset)
            try:
                cmds.playbackOptions(sst=start_frame + offset, set=end_frame + offset, sv=True)
            except RuntimeError:
                pass
            return
        if not target_plugs:
            return

        at_current = []
        grouped = {}
        for plug in target_plugs:
            times = sorted(set(cmds.keyframe(plug, query=True, tc=True) or []))
            if current_time in times:
                at_current.append(plug)
                continue
            candidates = [time for time in times if time < current_time] if offset > 0 else [time for time in times if time > current_time]
            source = candidates[-1] if offset > 0 and candidates else (candidates[0] if candidates else None)
            if source is not None:
                grouped.setdefault(source, []).append(plug)
        if at_current:
            cmds.keyframe(at_current, edit=True, relative=True, option="over",
                          time=(current_time, current_time), timeChange=offset)
            cmds.currentTime(current_time + offset)
            return
        for source, plugs in grouped.items():
            cmds.keyframe(plugs, edit=True, absolute=True, option="over",
                          time=(source, source), timeChange=current_time)
