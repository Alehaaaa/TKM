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
    return _unique(
        cmds.ls(
            type=("animCurveTL", "animCurveTA", "animCurveTT", "animCurveTU")
        )
        or []
    )


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


def _edit_keyframe_batches(operation, items, batch_size=100, **kwargs):
    """Run one Maya edit per bounded batch while reporting item progress."""
    items = list(items or [])
    if not items:
        return False
    for start in range(0, len(items), batch_size):
        if operation.cancelled:
            return False
        batch = items[start : start + batch_size]
        cmds.keyframe(batch, edit=True, **kwargs)
        operation.step(len(batch))
    return True


def nudge_all_keys(direction):
    curves = _target_curves()
    if not curves:
        return wutil.make_inViewMessage("No animation curves found.")
    offset = nudge_value() * int(direction)
    if not offset:
        return
    with toolCommon.tool_operation(
        tool_id="nudge_all_keys",
        label="Nudge All Keys",
        progress_max=len(curves),
        undo=True,
    ) as operation:
        edited = _edit_keyframe_batches(
            operation,
            curves,
            relative=True,
            includeUpperBound=True,
            option="over",
            timeChange=offset,
        )
        if edited:
            _move_current_time(offset)


def nudge_scene(direction):
    curves = _scene_curves()
    if not curves:
        return wutil.make_inViewMessage("No animation curves found in the scene.")
    offset = nudge_value() * int(direction)
    if not offset:
        return
    with toolCommon.tool_operation(
        tool_id="nudge_scene_keys",
        label="Nudge Scene Keys",
        progress_max=len(curves),
        undo=True,
    ) as operation:
        edited = _edit_keyframe_batches(
            operation,
            curves,
            relative=True,
            includeUpperBound=True,
            option="over",
            timeChange=offset,
        )
        if edited:
            _move_current_time(offset)


def shift_inbetween(direction, scene=False):
    count = nudge_value() * int(direction)
    if not count:
        return
    curves = _scene_curves() if scene else None
    if scene and not curves:
        return wutil.make_inViewMessage("No animation curves found in the scene.")
    current = cmds.currentTime(query=True)
    with toolCommon.tool_operation(
        tool_id="nudge_inbetween",
        label="Shift Inbetween",
        progress_max=len(curves) if curves else 1,
        undo=True,
    ) as operation:
        args = (curves,) if curves else ()
        if not scene and not cmds.keyframe(query=True):
            return
        if curves:
            edited = _edit_keyframe_batches(
                operation,
                curves,
                time=("{}:".format(current + 1),),
                relative=True,
                timeChange=count,
                option="over",
            )
        else:
            cmds.keyframe(
                *args,
                edit=True,
                time=("{}:".format(current + 1),),
                relative=True,
                timeChange=count,
                option="over",
            )
            operation.step()


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

    with toolCommon.tool_operation(
        tool_id="nudge_range", label="Nudge Keys", undo=True
    ) as operation:
        if target_info["has_graph_keys"]:
            operation.set_total(1)
            cmds.keyframe(edit=True, animation="keys", relative=True, includeUpperBound=True, option="over", timeChange=offset)
            operation.step()
            _move_current_time(offset)
            return
        if time_context.mode == "time_slider_range":
            curves = _unique(target_curves)
            if not curves and selection:
                curves = cmds.keyframe(selection, query=True, name=True) or []
            curves = _unique(
                cmds.keyframe(
                    curves,
                    query=True,
                    name=True,
                    time=(start_frame, end_frame),
                )
                or []
            )
            if not curves:
                return
            operation.set_total(len(curves))
            _edit_keyframe_batches(
                operation,
                curves,
                relative=True,
                includeUpperBound=True,
                option="over",
                time=(start_frame, end_frame),
                timeChange=offset,
            )
            if not edited:
                return
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
        operation.set_total(len(target_plugs)).set_status("Resolving Nudge Targets")
        for plug in target_plugs:
            if operation.cancelled:
                return
            times = sorted(set(cmds.keyframe(plug, query=True, tc=True) or []))
            if current_time in times:
                at_current.append(plug)
                operation.step()
                continue
            candidates = [time for time in times if time < current_time] if offset > 0 else [time for time in times if time > current_time]
            source = candidates[-1] if offset > 0 and candidates else (candidates[0] if candidates else None)
            if source is not None:
                grouped.setdefault(source, []).append(plug)
            operation.step()
        edit_total = len(at_current) + sum(len(plugs) for plugs in grouped.values())
        operation.set_total(len(target_plugs) + edit_total).set_status("Nudging Keys")
        if at_current:
            cmds.keyframe(at_current, edit=True, relative=True, option="over",
                          time=(current_time, current_time), timeChange=offset)
            operation.step(len(at_current))
            cmds.currentTime(current_time + offset)
            return
        for source, plugs in grouped.items():
            if operation.cancelled:
                return
            cmds.keyframe(plugs, edit=True, absolute=True, option="over",
                          time=(source, source), timeChange=current_time)
            operation.step(len(plugs))
