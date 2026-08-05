from maya import cmds

from TheKeyMachine.core import animation_context
from TheKeyMachine.core import openMayaUtils as omutils
from TheKeyMachine.mods import settingsMod as settings
from TheKeyMachine.tools import common as toolCommon
from TheKeyMachine.widgets import timeline as timelineWidgets
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
    target_info = animation_context.resolve_tool_context(
        default_mode="all_animation",
        include_channels=True,
        include_shapes=True,
        resolve_curves=True,
    )
    return _unique(target_info["selected_curves"])


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
        return animation_context.notify_empty("animation", "nudge")
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
        return animation_context.notify_empty("animation in the scene")
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
        return animation_context.notify_empty("animation in the scene")
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
    target_info = animation_context.resolve_tool_context(
        default_mode="all_animation",
        include_channels=True,
        include_shapes=True,
        resolve_curves=True,
    )
    target_curves = target_info["selected_curves"]
    time_context = target_info["time_context"]
    start_frame, end_frame = time_context.timerange

    with toolCommon.tool_operation(
        tool_id="nudge_range", label="Nudge Keys", undo=True
    ) as operation:
        if target_info["has_graph_keys"]:
            curve_times = {}
            for curve, key_time in target_info.get("selected_keyframes") or []:
                curve_times.setdefault(curve, []).append(float(key_time))
            operation.set_total(len(curve_times))
            for curve, key_times in curve_times.items():
                if operation.cancelled:
                    return
                cmds.keyframe(
                    curve,
                    edit=True,
                    time=[(time, time) for time in sorted(set(key_times))],
                    relative=True,
                    includeUpperBound=True,
                    option="over",
                    timeChange=offset,
                )
                operation.step()
            _move_current_time(offset)
            return
        if time_context.mode == "time_slider_range":
            curves = _unique(target_curves)
            if not curves:
                return
            operation.set_total(len(curves))
            with timelineWidgets.suspend_time_slider_updates():
                edited = omutils.move_anim_curve_keys(
                    curves,
                    start_frame,
                    end_frame,
                    offset,
                    cancelled=lambda: operation.cancelled,
                    progress=operation.step,
                )
                if not edited:
                    return
                cmds.currentTime(current_time + offset)
                # Keep playbackOptions last, immediately before the time
                # slider is managed and redrawn at its finished range.
                timelineWidgets.select_time_slider_range(
                    (start_frame + offset, end_frame + offset)
                )
            return
        curves = _unique(target_curves)
        if not curves:
            return

        at_current = []
        grouped = {}
        operation.set_total(len(curves)).set_status("Resolving Nudge Targets")
        for curve in curves:
            if operation.cancelled:
                return
            times = sorted(set(cmds.keyframe(curve, query=True, tc=True) or []))
            if current_time in times:
                at_current.append(curve)
                operation.step()
                continue
            candidates = [time for time in times if time < current_time] if offset > 0 else [time for time in times if time > current_time]
            source = candidates[-1] if offset > 0 and candidates else (candidates[0] if candidates else None)
            if source is not None:
                grouped.setdefault(source, []).append(curve)
            operation.step()
        edit_total = len(at_current) + sum(len(items) for items in grouped.values())
        operation.set_total(len(curves) + edit_total).set_status("Nudging Keys")
        if at_current:
            cmds.keyframe(at_current, edit=True, relative=True, option="over",
                          time=(current_time, current_time), timeChange=offset)
            operation.step(len(at_current))
            cmds.currentTime(current_time + offset)
            return
        for source, source_curves in grouped.items():
            if operation.cancelled:
                return
            cmds.keyframe(source_curves, edit=True, absolute=True, option="over",
                          time=(source, source), timeChange=current_time)
            operation.step(len(source_curves))
