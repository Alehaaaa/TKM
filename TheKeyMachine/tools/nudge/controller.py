from bisect import bisect_left

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
        cmds.currentTime(
            cmds.currentTime(query=True) + int(offset),
            edit=True,
            update=False,
        )
    except (RuntimeError, TypeError, ValueError):
        pass


def _edit_keyframe_batches(operation, items, batch_size=100, **kwargs):
    """Edit keys through the operation-owned batching and progress path."""
    items = list(items or [])
    if not items:
        return False

    def _edit_batch(batch):
        try:
            cmds.keyframe(batch, edit=True, **kwargs)
        except _COMMAND_ERRORS:
            edited = False
            for item in batch:
                try:
                    cmds.keyframe(item, edit=True, **kwargs)
                    edited = True
                except _COMMAND_ERRORS:
                    pass
            return edited
        return True

    return any(
        operation.process(
            items,
            _edit_batch,
            batch_size=batch_size,
            strategy="main",
            advance_progress=True,
            manage_progress=False,
        )
    )


def _snap_touched_collisions(operation, curve_targets):
    """Run Snap Keys' merge behavior only around nudged destination frames."""
    curve_targets = {
        curve: sorted(set(float(time) for time in times))
        for curve, times in (curve_targets or {}).items()
        if curve and times
    }
    if not curve_targets:
        return False

    def _snap_curve(curve, target_times):
        """Resolve and merge one curve without per-key thread crossings."""
        try:
            curve_times = cmds.keyframe(
                curve, query=True, timeChange=True
            ) or []
        except _COMMAND_ERRORS:
            return 0
        if not curve_times:
            return 0

        rounded_targets = {
            animationToolsController._nearest_whole_frame(target_time)
            for target_time in target_times
        }
        buckets = {}
        for curve_time in curve_times:
            rounded_time = animationToolsController._nearest_whole_frame(
                curve_time
            )
            if rounded_time in rounded_targets:
                buckets.setdefault(rounded_time, []).append(curve_time)

        curve_fn = maya_api.anim_curve_fn(curve)
        snapped_count = 0
        for rounded_time, key_times in sorted(buckets.items()):
            target_value = animationToolsController._curve_value_at_time(
                curve, curve_fn, rounded_time
            )
            if target_value is None:
                continue
            if animationToolsController._snap_curve_keys(
                curve,
                rounded_time,
                key_times,
                target_value,
                curve_times,
            ):
                snapped_count += 1
        return snapped_count

    def _snap_batch(batch):
        return sum(
            _snap_curve(curve, target_times)
            for curve, target_times in batch
        )

    snapped_count = sum(
        operation.process(
            curve_targets.items(),
            _snap_batch,
            batch_size=16,
            strategy="main",
            advance_progress=False,
            manage_progress=False,
        )
    )
    if snapped_count:
        operation.step(snapped_count)
    return bool(snapped_count)


def _contains_near(sorted_times, target, tolerance):
    """Return whether a sorted time list contains target within tolerance."""
    index = bisect_left(sorted_times, target - tolerance)
    return (
        index < len(sorted_times)
        and sorted_times[index] <= target + tolerance
    )


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
            if (
                _contains_near(times, target_time, tolerance)
                and not _contains_near(source_times, target_time, tolerance)
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
            if (
                _contains_near(all_times, target_time, tolerance)
                and not _contains_near(source_times, target_time, tolerance)
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


def nudge_all_keys(direction, tool_operation=None):
    operation = toolCommon.require_tool_operation(tool_operation)
    curves = _target_curves()
    if not curves:
        return animation.notify_empty("animation", "nudge")
    if not int(direction):
        return
    operation.set_total(len(curves))

    def _apply():
        offset = nudge_value() * int(direction)
        if not offset:
            return
        edited = _edit_keyframe_batches(
            operation,
            curves,
            relative=True,
            includeUpperBound=True,
            option="over",
            timeChange=offset,
        )
        if edited:
            operation.run_on_main(_move_current_time, offset)

    operation.run_worker(_apply)


def nudge_scene(direction, tool_operation=None):
    operation = toolCommon.require_tool_operation(tool_operation)
    curves = _scene_curves()
    if not curves:
        return animation.notify_empty("animation in the scene")
    if not int(direction):
        return
    operation.set_total(len(curves))

    def _apply():
        offset = nudge_value() * int(direction)
        if not offset:
            return
        edited = _edit_keyframe_batches(
            operation,
            curves,
            relative=True,
            includeUpperBound=True,
            option="over",
            timeChange=offset,
        )
        if edited:
            operation.run_on_main(_move_current_time, offset)

    operation.run_worker(_apply)


def shift_inbetween(direction, scene=False, tool_operation=None):
    operation = toolCommon.require_tool_operation(tool_operation)
    if not int(direction):
        return
    curves = _scene_curves() if scene else None
    if scene and not curves:
        return animation.notify_empty("animation in the scene")
    current = cmds.currentTime(query=True)
    operation.set_total(len(curves) if curves else 1)

    def _apply():
        count = nudge_value() * int(direction)
        if not count:
            return
        args = (curves,) if curves else ()
        if not scene and not operation.run_on_main(cmds.keyframe, query=True):
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
            selected_curves = operation.run_on_main(
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
                    operation.run_on_main(
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

    operation.run_worker(_apply)


def nudge_range(direction, tool_operation=None):
    operation = toolCommon.require_tool_operation(tool_operation)
    if not int(direction):
        return

    def _apply():
        offset = nudge_value() * int(direction)
        if not offset:
            return
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

        context = operation.run_on_main(_collect_context)
        current_time = context["current_time"]
        target_info = context["target_info"]
        edit_filter = context["edit_filter"]
        target_curves = context["target_curves"]
        time_context = context["time_context"]
        start_frame, end_frame = time_context.timerange

        if target_info.has_graph_keys:
            selected_curve_times = {}
            for curve, key_time in target_info.selected_keys or []:
                selected_curve_times.setdefault(curve, []).append(float(key_time))
            editable_curves = set(operation.run_on_main(
                lambda: _editable_curves(
                    selected_curve_times,
                    edit_filter=edit_filter,
                )
            ))
            curve_times = {
                curve: key_times
                for curve, key_times in selected_curve_times.items()
                if curve in editable_curves
            }
            if not curve_times:
                return
            collisions = operation.run_on_main(
                _collision_targets_for_times,
                curve_times,
                offset,
            )
            operation.set_total(len(curve_times))
            edited_any = False
            if len(curve_times) == len(selected_curve_times):
                def _move_active_keyset():
                    try:
                        cmds.keyframe(
                            edit=True,
                            animation="keys",
                            relative=True,
                            option="over",
                            timeChange=offset,
                        )
                    except _COMMAND_ERRORS:
                        return False
                    return True

                edited_any = operation.run_on_main(_move_active_keyset)
                operation.step(len(curve_times))
            else:
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
                operation.run_on_main(_move_current_time, offset)
            return

        if time_context.mode == "time_slider_range":
            curves = _unique(target_curves)
            if not curves:
                return
            selected_timerange = context["selected_timerange"] or (
                start_frame,
                end_frame,
            )
            collisions = operation.run_on_main(
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
                        return False, False
                    cmds.currentTime(
                        current_time + offset,
                        edit=True,
                        update=False,
                    )
                    range_restored = _restore_nudged_time_range(
                        selected_timerange,
                        offset,
                    )
                    return True, range_restored

            edited, range_restored = operation.run_on_main(_move_range)
            if not edited:
                return
            if collisions:
                operation.set_status("Snapping Collisions")
                operation.set_total(
                    len(curves)
                    + sum(len(times) for times in collisions.values())
                )
                _snap_touched_collisions(operation, collisions)
            if not range_restored:
                operation.run_on_main(
                    _restore_nudged_time_range,
                    selected_timerange,
                    offset,
                )
            return

        curves = _unique(target_curves)
        if not curves:
            return

        def _query_curve_batch(batch):
            result = []
            for curve in batch:
                try:
                    times = sorted(
                        set(cmds.keyframe(curve, query=True, tc=True) or [])
                    )
                except _COMMAND_ERRORS:
                    times = []
                result.append((curve, times))
            return result

        operation.set_total(len(curves)).set_status("Resolving Nudge Targets")
        queried_batches = operation.process(
            curves,
            _query_curve_batch,
            batch_size=32,
            strategy="main",
            manage_progress=False,
        )
        if operation.cancelled:
            return

        at_current = []
        grouped = {}
        for curve, times in (
            item for batch in queried_batches for item in batch
        ):
            if current_time in times:
                at_current.append(curve)
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
        edit_total = len(at_current) + sum(len(items) for items in grouped.values())
        operation.set_total(len(curves) + edit_total).set_status("Nudging Keys")
        if at_current:
            collisions = operation.run_on_main(
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
                operation.run_on_main(
                    cmds.currentTime,
                    current_time + offset,
                    edit=True,
                    update=False,
                )
                return
        for source, source_curves in grouped.items():
            if operation.cancelled:
                return
            single_offset = nudge_value() * (1 if offset > 0 else -1)
            destination = current_time + offset - single_offset
            _edit_keyframe_batches(
                operation,
                source_curves,
                absolute=True,
                option="over",
                time=(source, source),
                timeChange=destination,
            )
        if grouped and destination != current_time:
            operation.run_on_main(
                cmds.currentTime,
                destination,
                edit=True,
                update=False,
            )

    operation.run_worker(_apply)
