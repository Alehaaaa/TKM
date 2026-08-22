import threading

from maya import cmds

from TheKeyMachine.maya import animation
from TheKeyMachine.maya import maya_api
from TheKeyMachine.maya import selection
from TheKeyMachine.core import settings
from TheKeyMachine.tools import common as toolCommon
from TheKeyMachine.ui.widgets import timeline as timelineWidgets
from TheKeyMachine.ui.widgets import util as wutil
from TheKeyMachine.tools.animation_tools import controller as animationToolsController


_COMMAND_ERRORS = (
    RuntimeError,
    ValueError,
    TypeError,
    AttributeError,
    KeyError,
    IndexError,
)
_NUDGE_APPLY_LOCK = threading.RLock()


def _on_main(operation, fn, *args, **kwargs):
    return operation.run_on_main(fn, *args, **kwargs) if operation else fn(*args, **kwargs)


def _run_threaded_nudge(operation, callback):
    def _worker():
        with _NUDGE_APPLY_LOCK:
            return callback()

    return toolCommon.run_on_worker_thread(_worker)


def nudge_value(default=1):
    try:
        return int(settings.get_setting("nudge_value", default))
    except (TypeError, ValueError):
        return default


def _unique(values):
    return list(dict.fromkeys(values or ()))


def _is_locked_plug(plug):
    if not plug:
        return False
    try:
        return bool(cmds.getAttr(plug, lock=True))
    except _COMMAND_ERRORS:
        return False


def _is_locked_node(node):
    if not node:
        return False
    try:
        locked = cmds.lockNode(node, query=True, lock=True) or []
    except _COMMAND_ERRORS:
        return False
    return bool(locked and locked[0])


class _CurveEditFilter(object):
    def __init__(self, layer_context=None, plugs=None):
        self.layer_context = layer_context or {}
        self.layer_locked = {}
        self.curve_layers = {}
        self.weight_curve_layers = {}
        snapshot = self.layer_context.get("context") or {}
        for layer_id, metadata in (snapshot.get("layers") or {}).items():
            if metadata.get("root"):
                layer_name = self.layer_context.get("root_name")
            else:
                layer_name = metadata.get("name") or layer_id
            if not layer_name:
                continue
            self.layer_locked[layer_name] = bool(metadata.get("locked"))
            if not metadata.get("root"):
                for curve in animation.weight_curves(layer_name):
                    self.weight_curve_layers[curve] = layer_name

        if plugs and self.layer_context.get("has_layers"):
            self.curve_layers.update(
                animation.layer_graph.ownership(
                    plugs,
                    self.layer_locked,
                    scene_layers=self.layer_context.get("scene_layers"),
                )
            )

    def is_editable(self, curve):
        if not curve:
            return False
        try:
            if not cmds.objExists(curve):
                return False
        except _COMMAND_ERRORS:
            return False
        if _is_locked_node(curve):
            return False

        layer_name = self.curve_layers.get(curve)
        if layer_name and self.layer_locked.get(layer_name):
            return False

        weight_layer = self.weight_curve_layers.get(curve)
        if weight_layer:
            return (
                not self.layer_locked.get(weight_layer)
                and not _is_locked_plug("{}.weight".format(weight_layer))
            )

        output_plugs = selection.get_anim_curve_output_plugs([curve])
        if output_plugs:
            return any(not _is_locked_plug(plug) for plug in output_plugs)
        return True


def _editable_curves(curves, edit_filter=None):
    edit_filter = edit_filter or _CurveEditFilter()
    return [
        curve for curve in _unique(curves)
        if edit_filter.is_editable(curve)
    ]


def _scene_curves():
    edit_filter = _CurveEditFilter(animation.layer_cache.tool_context())
    return _editable_curves(
        cmds.ls(
            type=("animCurveTL", "animCurveTA", "animCurveTT", "animCurveTU")
        )
        or [],
        edit_filter=edit_filter,
    )


def _target_curves():
    target_info = animation.resolve_context(
        default_mode="all_animation",
        include_channels=True,
        include_shapes=True,
        resolve_curves=True,
    )
    return _editable_curves(
        target_info.curves,
        edit_filter=_CurveEditFilter(
            target_info.layer_scope,
            plugs=target_info.plugs,
        ),
    )


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
    edited = False
    for start in range(0, len(items), batch_size):
        if operation.cancelled:
            return edited
        batch = items[start : start + batch_size]
        try:
            _on_main(operation, cmds.keyframe, batch, edit=True, **kwargs)
        except _COMMAND_ERRORS:
            for item in batch:
                if operation.cancelled:
                    return edited
                try:
                    _on_main(operation, cmds.keyframe, item, edit=True, **kwargs)
                    edited = True
                except _COMMAND_ERRORS:
                    pass
                operation.step()
            continue
        edited = True
        operation.step(len(batch))
    return edited


def _snap_touched_collisions(operation, curve_targets):
    """Run Snap Keys' merge behavior only around nudged destination frames."""
    curve_targets = {
        curve: sorted(set(float(time) for time in times))
        for curve, times in (curve_targets or {}).items()
        if curve and times
    }
    if not curve_targets:
        return False

    snapped = False
    for curve, target_times in curve_targets.items():
        if operation.cancelled:
            return snapped
        try:
            curve_times = _on_main(
                operation,
                cmds.keyframe,
                curve,
                query=True,
                timeChange=True,
            ) or []
        except _COMMAND_ERRORS:
            continue
        if not curve_times:
            continue

        buckets = {}
        for curve_time in curve_times:
            for target_time in target_times:
                rounded_target = animationToolsController._nearest_whole_frame(target_time)
                rounded_time = animationToolsController._nearest_whole_frame(curve_time)
                if rounded_time == rounded_target:
                    buckets.setdefault(rounded_time, []).append(curve_time)
                    break

        curve_fn = _on_main(operation, maya_api.anim_curve_fn, curve)
        for rounded_time, key_times in sorted(buckets.items()):
            if operation.cancelled:
                return snapped
            target_value = _on_main(
                operation,
                animationToolsController._curve_value_at_time,
                curve,
                curve_fn,
                rounded_time,
            )
            if target_value is None:
                continue
            snapped = (
                _on_main(
                    operation,
                    animationToolsController._snap_curve_keys,
                    curve,
                    rounded_time,
                    key_times,
                    target_value,
                    curve_times,
                )
                or snapped
            )
            operation.step()
    return snapped


def _collision_targets(curves, source_start, source_end, offset, tolerance=1e-6):
    """Return target frames where nudged keys would land on existing keys."""
    collisions = {}
    try:
        lower, upper = sorted((float(source_start), float(source_end)))
        offset = float(offset)
    except (TypeError, ValueError):
        return collisions
    for curve in curves or []:
        try:
            times = sorted(float(time) for time in (cmds.keyframe(curve, query=True, tc=True) or []))
        except _COMMAND_ERRORS:
            continue
        source_times = [
            time for time in times
            if lower - tolerance <= time <= upper + tolerance
        ]
        if not source_times:
            continue
        target_times = [time + offset for time in source_times]
        for target_time in target_times:
            if any(
                abs(time - target_time) <= tolerance
                and all(abs(time - source_time) > tolerance for source_time in source_times)
                for time in times
            ):
                collisions.setdefault(curve, []).append(target_time)
    return collisions


def _collision_targets_for_times(curve_times, offset, tolerance=1e-6):
    collisions = {}
    try:
        offset = float(offset)
    except (TypeError, ValueError):
        return collisions
    for curve, source_times in (curve_times or {}).items():
        try:
            all_times = sorted(float(time) for time in (cmds.keyframe(curve, query=True, tc=True) or []))
        except _COMMAND_ERRORS:
            continue
        source_times = sorted(set(float(time) for time in source_times))
        for target_time in (time + offset for time in source_times):
            if any(
                abs(time - target_time) <= tolerance
                and all(abs(time - source_time) > tolerance for source_time in source_times)
                for time in all_times
            ):
                collisions.setdefault(curve, []).append(target_time)
    return collisions


def _restore_nudged_time_range(timerange, offset):
    if not timerange:
        return False
    try:
        start_frame = float(timerange[0]) + float(offset)
        end_frame = float(timerange[1]) + float(offset)
    except (TypeError, ValueError):
        return False
    try:
        if timelineWidgets.highlight_timeline_range((start_frame, end_frame)):
            return True
    except _COMMAND_ERRORS:
        pass
    return timelineWidgets.select_time_slider_range((start_frame, end_frame))


def nudge_all_keys(direction):
    curves = _target_curves()
    if not curves:
        return animation.notify_empty("animation", "nudge")
    offset = nudge_value() * int(direction)
    if not offset:
        return
    with toolCommon.tool_operation(
        tool_id="nudge_all_keys",
        label="Nudge All Keys",
        progress_max=len(curves),
        undo=True,
    ) as operation:
        def _apply():
            edited = _edit_keyframe_batches(
                operation,
                curves,
                relative=True,
                includeUpperBound=True,
                option="over",
                timeChange=offset,
            )
            if edited:
                _on_main(operation, _move_current_time, offset)

        _run_threaded_nudge(operation, _apply)


def nudge_scene(direction):
    curves = _scene_curves()
    if not curves:
        return animation.notify_empty("animation in the scene")
    offset = nudge_value() * int(direction)
    if not offset:
        return
    with toolCommon.tool_operation(
        tool_id="nudge_scene_keys",
        label="Nudge Scene Keys",
        progress_max=len(curves),
        undo=True,
    ) as operation:
        def _apply():
            edited = _edit_keyframe_batches(
                operation,
                curves,
                relative=True,
                includeUpperBound=True,
                option="over",
                timeChange=offset,
            )
            if edited:
                _on_main(operation, _move_current_time, offset)

        _run_threaded_nudge(operation, _apply)


def shift_inbetween(direction, scene=False):
    count = nudge_value() * int(direction)
    if not count:
        return
    curves = _scene_curves() if scene else None
    if scene and not curves:
        return animation.notify_empty("animation in the scene")
    current = cmds.currentTime(query=True)
    with toolCommon.tool_operation(
        tool_id="nudge_inbetween",
        label="Shift Inbetween",
        progress_max=len(curves) if curves else 1,
        undo=True,
    ) as operation:
        def _apply():
            args = (curves,) if curves else ()
            if not scene and not _on_main(operation, cmds.keyframe, query=True):
                return
            if curves:
                _edit_keyframe_batches(
                    operation,
                    curves,
                    time=("{}:".format(current + 1),),
                    relative=True,
                    timeChange=count,
                    option="over",
                )
            else:
                selected_curves = _on_main(
                    operation,
                    lambda: _editable_curves(
                        cmds.keyframe(query=True, selected=True, name=True) or [],
                        edit_filter=_CurveEditFilter(
                            animation.layer_cache.tool_context()
                        ),
                    ),
                )
                if selected_curves:
                    operation.set_total(len(selected_curves))
                    _edit_keyframe_batches(
                        operation,
                        selected_curves,
                        time=("{}:".format(current + 1),),
                        relative=True,
                        timeChange=count,
                        option="over",
                    )
                else:
                    try:
                        _on_main(
                            operation,
                            cmds.keyframe,
                            *args,
                            edit=True,
                            time=("{}:".format(current + 1),),
                            relative=True,
                            timeChange=count,
                            option="over",
                        )
                    except _COMMAND_ERRORS:
                        return
                    operation.step()

        _run_threaded_nudge(operation, _apply)


def nudge_range(direction):
    offset = nudge_value() * int(direction)
    if not offset:
        return

    with toolCommon.tool_operation(
        tool_id="nudge_range", label="Nudge Keys", undo=True
    ) as operation:
        def _apply():
            def _collect_context():
                target_info = animation.resolve_context(
                    default_mode="all_animation",
                    include_channels=True,
                    include_shapes=True,
                    resolve_curves=True,
                )
                edit_filter = _CurveEditFilter(
                    target_info.layer_scope,
                    plugs=target_info.plugs,
                )
                return {
                    "current_time": cmds.currentTime(query=True),
                    "target_info": target_info,
                    "edit_filter": edit_filter,
                    "target_curves": _editable_curves(
                        target_info.curves,
                        edit_filter=edit_filter,
                    ),
                    "time_context": target_info.time,
                    "selected_timerange": selection.get_selected_time_range(),
                }

            context = _on_main(operation, _collect_context)
            current_time = context["current_time"]
            target_info = context["target_info"]
            edit_filter = context["edit_filter"]
            target_curves = context["target_curves"]
            time_context = context["time_context"]
            start_frame, end_frame = time_context.timerange

            if target_info.has_graph_keys:
                curve_times = {}
                for curve, key_time in target_info.selected_keys or []:
                    if not _on_main(operation, edit_filter.is_editable, curve):
                        continue
                    curve_times.setdefault(curve, []).append(float(key_time))
                if not curve_times:
                    return
                collisions = _on_main(
                    operation,
                    _collision_targets_for_times,
                    curve_times,
                    offset,
                )
                operation.set_total(len(curve_times))
                edited_any = False
                for curve, key_times in curve_times.items():
                    if operation.cancelled:
                        return
                    edited_any = _edit_keyframe_batches(
                        operation,
                        [curve],
                        time=[(time, time) for time in sorted(set(key_times))],
                        relative=True,
                        includeUpperBound=True,
                        option="over",
                        timeChange=offset,
                    ) or edited_any
                if edited_any:
                    if collisions:
                        operation.set_status("Snapping Collisions")
                        operation.set_total(
                            len(curve_times)
                            + sum(len(times) for times in collisions.values())
                        )
                        _snap_touched_collisions(operation, collisions)
                    _on_main(operation, _move_current_time, offset)
                return

            if time_context.mode == "time_slider_range":
                curves = _unique(target_curves)
                if not curves:
                    return
                selected_timerange = context["selected_timerange"] or (
                    start_frame,
                    end_frame,
                )
                collisions = _on_main(
                    operation,
                    _collision_targets,
                    curves,
                    start_frame,
                    end_frame,
                    offset,
                )
                operation.set_total(len(curves))

                def _move_range():
                    with timelineWidgets.suspend_time_slider_updates():
                        edited = maya_api.move_anim_curve_keys(
                            curves,
                            start_frame,
                            end_frame,
                            offset,
                            cancelled=lambda: operation.cancelled,
                            progress=operation.step,
                        )
                        if not edited:
                            return False
                        cmds.currentTime(current_time + offset)
                        return True

                if not _on_main(operation, _move_range):
                    return
                if collisions:
                    operation.set_status("Snapping Collisions")
                    operation.set_total(
                        len(curves)
                        + sum(len(times) for times in collisions.values())
                    )
                    _snap_touched_collisions(operation, collisions)
                _on_main(
                    operation,
                    _restore_nudged_time_range,
                    selected_timerange,
                    offset,
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
                times = sorted(
                    set(
                        _on_main(
                            operation,
                            cmds.keyframe,
                            curve,
                            query=True,
                            tc=True,
                        )
                        or []
                    )
                )
                if current_time in times:
                    at_current.append(curve)
                    operation.step()
                    continue
                candidates = (
                    [time for time in times if time < current_time]
                    if offset > 0
                    else [time for time in times if time > current_time]
                )
                source = (
                    candidates[-1]
                    if offset > 0 and candidates
                    else (candidates[0] if candidates else None)
                )
                if source is not None:
                    grouped.setdefault(source, []).append(curve)
                operation.step()
            edit_total = len(at_current) + sum(len(items) for items in grouped.values())
            operation.set_total(len(curves) + edit_total).set_status("Nudging Keys")
            if at_current:
                collisions = _on_main(
                    operation,
                    _collision_targets_for_times,
                    {curve: [current_time] for curve in at_current},
                    offset,
                )
                edited = _edit_keyframe_batches(
                    operation,
                    at_current,
                    relative=True,
                    option="over",
                    time=(current_time, current_time),
                    timeChange=offset,
                )
                if edited:
                    if collisions:
                        operation.set_status("Snapping Collisions")
                        operation.set_total(
                            len(curves)
                            + edit_total
                            + sum(len(times) for times in collisions.values())
                        )
                        _snap_touched_collisions(operation, collisions)
                    _on_main(operation, cmds.currentTime, current_time + offset)
                    return
            for source, source_curves in grouped.items():
                if operation.cancelled:
                    return
                _edit_keyframe_batches(
                    operation,
                    source_curves,
                    absolute=True,
                    option="over",
                    time=(source, source),
                    timeChange=current_time,
                )

        _run_threaded_nudge(operation, _apply)
