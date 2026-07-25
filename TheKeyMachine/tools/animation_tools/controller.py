"""Animation curve editing, cleanup, smart-key, and snapping behavior."""

from contextlib import contextmanager
import math

from maya import cmds

from TheKeyMachine.core import animation_context, curveFitting
from TheKeyMachine.core import animlayers
from TheKeyMachine.core import openMayaUtils as open_maya
from TheKeyMachine.mods import selectionMod
from TheKeyMachine.mods import settingsMod as settings
from TheKeyMachine.tools import common as toolCommon
from TheKeyMachine.tools.animation_tools import time_navigation
from TheKeyMachine.widgets import util as wutil


_key_clipboard_start_frame = None
_key_clipboard = None
REMOVE_REDUNDANT_MODE_SETTING = "remove_redundant_keys_mode"
REMOVE_REDUNDANT_MODE_FLAT = "flat_keys"
REMOVE_REDUNDANT_MODE_ALL = "all_redundant"
REMOVE_REDUNDANT_MODES = (REMOVE_REDUNDANT_MODE_FLAT, REMOVE_REDUNDANT_MODE_ALL)
_COMMAND_ERRORS = (
    RuntimeError,
    ValueError,
    TypeError,
    AttributeError,
    KeyError,
    IndexError,
)


def _unique(items):
    return list(dict.fromkeys(items or []))


def _euler_full_turn():
    try:
        angular_unit = cmds.currentUnit(query=True, angle=True)
    except _COMMAND_ERRORS:
        angular_unit = "deg"
    return math.tau if str(angular_unit).lower().startswith("rad") else 360.0


def _closest_turn_offset(value, reference, full_turn):
    if (
        not all(math.isfinite(float(item)) for item in (value, reference, full_turn))
        or full_turn <= 0.0
    ):
        return 0.0
    closest_value = open_maya.closest_euler_angle_cut(value, reference)
    if closest_value is not None:
        return float(closest_value) - float(value)
    turns = math.floor(((float(reference) - float(value)) / float(full_turn)) + 0.5)
    return float(turns) * float(full_turn)


def _euler_turn_groups(curve, target_info, full_turn):
    try:
        key_times = [
            float(value)
            for value in (cmds.keyframe(curve, query=True, timeChange=True) or [])
        ]
        key_values = [
            float(value)
            for value in (cmds.keyframe(curve, query=True, valueChange=True) or [])
        ]
    except _COMMAND_ERRORS:
        return []
    if not key_times or len(key_times) != len(key_values):
        return []

    target_times = set(
        float(value) for value in animation_context.key_times(curve, target_info)
    )
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
        offset = (
            0.0
            if previous_value is None
            else _closest_turn_offset(key_value, previous_value, full_turn)
        )
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


def _apply_euler_filter(curves, target_info, operation=None):
    changed_groups = 0
    full_turn = _euler_full_turn()
    with animation_context.preserve_key_selection():
        for curve in curves or []:
            if operation is not None and operation.cancelled:
                break
            for start_time, end_time, offset in _euler_turn_groups(
                curve, target_info, full_turn
            ):
                cmds.keyframe(
                    curve,
                    edit=True,
                    time=(start_time, end_time),
                    relative=True,
                    valueChange=offset,
                )
                changed_groups += 1
            if operation is not None:
                operation.step()
    return changed_groups


def delete_keyframes_before_current_time():
    selected = selectionMod.get_selected_objects()
    if not selected:
        return wutil.make_inViewMessage("Select at least one object")
    current_time = cmds.currentTime(query=True)
    operation = toolCommon.current_tool_operation()
    if operation is not None:
        operation.set_total(len(selected)).set_status("Deleting Keys Before Current")
    for obj in selected:
        if operation is not None and operation.cancelled:
            break
        keyframes = cmds.keyframe(obj, query=True, timeChange=True) or []
        before = [frame for frame in keyframes if frame < current_time]
        if before:
            cmds.cutKey(obj, time=(min(before), max(before)), clear=True)
        if operation is not None:
            operation.step()


def delete_keyframes_after_current_time():
    selected = selectionMod.get_selected_objects()
    if not selected:
        return wutil.make_inViewMessage("Select at least one object")
    current_time = cmds.currentTime(query=True)
    operation = toolCommon.current_tool_operation()
    if operation is not None:
        operation.set_total(len(selected)).set_status("Deleting Keys After Current")
    for obj in selected:
        if operation is not None and operation.cancelled:
            break
        keyframes = cmds.keyframe(obj, query=True, timeChange=True) or []
        after = [frame for frame in keyframes if frame > current_time]
        if after:
            cmds.cutKey(obj, time=(min(after), max(after)), clear=True)
        if operation is not None:
            operation.step()


def select_all_animation_curves(*args):
    # Tipos de curvas de animación que quieres seleccionar
    tipos_de_curvas = ["animCurveTL", "animCurveTA", "animCurveTT", "animCurveTU"]

    # Lista para almacenar las curvas seleccionadas
    curvas_seleccionadas = []

    # Recorre todos los tipos de curvas y busca las que coinciden
    for tipo in tipos_de_curvas:
        curvas = cmds.ls(type=tipo)
        if curvas:
            curvas_seleccionadas.extend(curvas)

    # Selecciona las curvas encontradas
    if curvas_seleccionadas:
        cmds.select(curvas_seleccionadas)
        cmds.selectKey(add=True)
    else:
        wutil.make_inViewMessage("No anim curves found")


def clear_selected_keys(*args):
    cmds.selectKey(clear=True)


# For Hotkeys


# _____


# _____________________________________________________ Key Tools  Customgraph _______________________________________________________________#


# --------------------------------------------------- Anim Curve hotkey helpers ---------------------------------------------------


@contextmanager
def _animation_command_context(
    label,
    tint_key=None,
    default_mode="all_animation",
    timerange=None,
    tint=True,
    progress_max=1,
    tool_operation=None,
):
    """Wrap animation hotkey commands with the shared tool operation.

    tint=False disables the timeline/context tint for commands that should feel silent.

    ``tool_operation`` is the operation core/trigger.py's dispatcher already
    opened for this command (forwarded through the callback's ``**kwargs`` --
    see ``_make_dispatched_command``). When present, reuse it instead of
    nesting a second ``tool_operation()``: exactly one operation, one undo
    chunk, one TKM_DEBUG_TIMING line per command, regardless of entry point.
    Only a direct/standalone call that bypasses dispatch falls through to
    opening its own operation below.
    """
    if tool_operation is not None:
        tool_operation.set_status(label)
        if progress_max:
            tool_operation.set_total(progress_max, reset=True)
        operation_tint = ("range" if timerange is not None else "context") if tint else "none"
        toolCommon.ensure_operation_tint(
            tool_operation,
            tint=operation_tint,
            timerange=timerange,
            default_mode=default_mode,
            tint_key=tint_key,
        )
        yield tool_operation
        return

    operation_tint = "none"
    if tint:
        operation_tint = "range" if timerange is not None else "context"

    with toolCommon.tool_operation(
        tool_id=tint_key,
        label=label,
        progress=True,
        progress_max=progress_max,
        undo=True,
        undo_name=toolCommon.make_undo_chunk_name(title=label),
        tint=operation_tint,
        timerange=timerange,
        default_mode=default_mode,
        tint_key=tint_key,
    ) as operation:
        yield operation


@contextmanager
def _cleanup_command_context(tool_operation, label, tool_id):
    """Cleanup-command alias: tint-less, caller-managed progress, dispatch-reused."""
    with _animation_command_context(
        label,
        tool_id,
        tint=False,
        progress_max=0,
        tool_operation=tool_operation,
    ) as operation:
        yield operation


def _run_key_command(
    command, command_name, default_mode="all_animation", **base_kwargs
):
    target_info, target_plugs, selected_objects, _selected_channels = (
        animation_context.resolve_command_targets(
            default_mode=default_mode,
            include_shapes=False,
        )
    )

    has_graph_keys = bool(target_info.get("has_graph_keys"))
    time_context = target_info.get("time_context")
    source = target_info.get("source")

    target_plugs = _unique(target_plugs)
    selected_objects = _unique(selected_objects)

    if not target_plugs and not selected_objects and not has_graph_keys:
        return wutil.make_inViewMessage("Select at least one object, channel, or key")

    with toolCommon.tool_operation(
        tool_id=command_name,
        label=toolCommon.humanize_tool_name(command_name),
        progress=False,
        undo=True,
        undo_name=toolCommon.make_undo_chunk_name(tool_id=command_name),
    ):
        kwargs = dict(base_kwargs)

        if has_graph_keys:
            kwargs.setdefault("animation", "keys")
            return command(**kwargs)

        kwargs.update(animation_context.selection_time_kwargs(time_context))

        if default_mode == "current_frame" and not _has_key_time_filter(kwargs):
            frame = cmds.currentTime(query=True)
            kwargs["time"] = (frame, frame)

        if source == "channel_box" and target_plugs:
            return _run_command_on_plugs(command, target_plugs, **kwargs)

        targets = (
            target_plugs if _is_explicit_channel_source(source) else selected_objects
        )
        if not targets:
            targets = target_plugs or selected_objects
        return command(targets, **kwargs)


def _has_key_time_filter(kwargs):
    return any(key in kwargs for key in ("time", "index", "float"))


def _is_explicit_channel_source(source):
    return source in (
        "channel_box",
        "graph_editor",
        "graph_editor_outliner",
    )


def _run_command_on_plugs(command, plugs, **kwargs):
    result = None
    for plug in plugs or []:
        if not plug or "." not in plug:
            continue
        node, attr = plug.rsplit(".", 1)
        result = command(node, attribute=attr, **kwargs)
    return result


def _paste_key_targets(target_plugs, selected_objects, selected_channels, **kwargs):
    if target_plugs:
        return _run_command_on_plugs(cmds.pasteKey, target_plugs, **kwargs)

    if selected_channels:
        kwargs["attribute"] = selected_channels
    return cmds.pasteKey(selected_objects, **kwargs)


def _curve_key_snapshot(curve, target_info):
    keys = animation_context.key_data(curve, target_info)
    if not keys:
        return []
    snapshots = []
    for time, value in keys:
        tangent = {}
        for flag in (
            "inAngle", "outAngle", "inWeight", "outWeight",
            "inTangentType", "outTangentType", "lock", "weightLock",
        ):
            try:
                result = cmds.keyTangent(
                    curve, query=True, time=(time, time), **{flag: True}
                ) or []
                if result:
                    tangent[flag] = result[0]
            except _COMMAND_ERRORS:
                continue
        snapshots.append({"time": float(time), "value": float(value), "tangent": tangent})
    return snapshots


def _capture_key_clipboard(target_info, target_plugs):
    entries = []
    plugs = _unique(target_plugs)
    curves = animation_context.curves(target_info, include_shapes=False)
    if not plugs:
        plugs = selectionMod.get_anim_curve_output_plugs(curves)
    for curve in curves:
        curve_plugs = selectionMod.get_anim_curve_output_plugs([curve])
        plug = curve_plugs[0] if curve_plugs else None
        if plugs and plug not in plugs:
            continue
        keys = _curve_key_snapshot(curve, target_info)
        if keys:
            entries.append({"curve": curve, "plug": plug, "keys": keys})
    return {"entries": entries}


def _selected_destination_times():
    result = {}
    for curve in selectionMod.get_graph_editor_selected_curves():
        try:
            frames = cmds.keyframe(
                curve, query=True, selected=True, timeChange=True
            ) or []
        except _COMMAND_ERRORS:
            frames = []
        if frames:
            result[curve] = sorted(set(float(frame) for frame in frames))
    return result


def _map_clipboard_entries(target_curves):
    entries = list((_key_clipboard or {}).get("entries") or [])
    targets = _unique(target_curves)
    if not entries or not targets:
        return []
    by_curve = {entry["curve"]: entry for entry in entries}
    if set(targets) == set(by_curve):
        return [(curve, by_curve[curve]) for curve in targets]
    by_plug = {
        entry["plug"]: entry for entry in entries if entry.get("plug")
    }
    target_plugs = {
        curve: (selectionMod.get_anim_curve_output_plugs([curve]) or [None])[0]
        for curve in targets
    }
    if all(target_plugs[curve] in by_plug for curve in targets):
        return [(curve, by_plug[target_plugs[curve]]) for curve in targets]
    return list(zip(targets, entries))


def _apply_key_tangent_snapshot(curve, time, tangent):
    for flag in (
        "inTangentType", "outTangentType", "lock", "weightLock",
        "inAngle", "outAngle", "inWeight", "outWeight",
    ):
        if flag not in tangent:
            continue
        try:
            cmds.keyTangent(
                curve,
                edit=True,
                time=(time, time),
                **{flag: tangent[flag]}
            )
        except _COMMAND_ERRORS:
            continue


def _paste_snapshot_to_selected_times(destination_times):
    mappings = _map_clipboard_entries(destination_times)
    if not mappings:
        return False
    changed = False
    for curve, entry in mappings:
        times = destination_times.get(curve)
        source_keys = entry.get("keys") or []
        if not times or not source_keys:
            continue
        last_destination = len(times) - 1
        last_source = len(source_keys) - 1
        for index, destination_time in enumerate(times):
            source_index = (
                0 if not last_destination else round(index * last_source / last_destination)
            )
            source = source_keys[source_index]
            cmds.setKeyframe(curve, time=destination_time, value=source["value"])
            _apply_key_tangent_snapshot(
                curve, destination_time, source.get("tangent") or {}
            )
            changed = True
    return changed


def _clipboard_ordered_targets(target_plugs):
    targets = _unique(target_plugs)
    source = [
        entry.get("plug")
        for entry in ((_key_clipboard or {}).get("entries") or [])
        if entry.get("plug")
    ]
    if source and set(source) == set(targets):
        return _unique(source)
    return targets


def _navigation_key_context():
    curves = selectionMod.get_key_navigation_curves()
    selected_range = selectionMod.get_graph_editor_selected_range()
    if selected_range is None:
        selected_range = selectionMod.get_selected_time_slider_range()
    if selected_range is None:
        try:
            min_time = cmds.playbackOptions(query=True, minTime=True)
            max_time = cmds.playbackOptions(query=True, maxTime=True)
            selected_range = (min_time, max_time)
        except _COMMAND_ERRORS:
            selected_range = None
    return curves, selected_range


def _go_to_key(amount):
    if time_navigation.accumulate_pending_key_step(amount):
        return True
    curves, selected_range = _navigation_key_context()
    return time_navigation.request_curve_key_step(
        amount,
        curves,
        time_range=selected_range,
    )


def go_to_next_key(*args):
    return _go_to_key(1)


def go_to_previous_key(*args):
    return _go_to_key(-1)


def go_to_next_frame(*args):
    return time_navigation.request_frame_step(1)


def go_to_previous_frame(*args):
    return time_navigation.request_frame_step(-1)


def apply_smart_euler_filter(*args, **kwargs):
    tool_operation = kwargs.pop("tool_operation", None)
    target_info, _target_plugs, _selected_objects, _selected_channels = (
        animation_context.resolve_command_targets(default_mode="all_animation")
    )
    curves = []
    for curve in animation_context.curves(target_info):
        if selectionMod.is_rotation_anim_curve(curve):
            curves.append(curve)

    if not curves:
        return wutil.make_inViewMessage("No rotation animation curves found")

    with _animation_command_context(
        "Apply Smart Euler Filter",
        "apply_smart_euler_filter",
        progress_max=len(curves),
        tool_operation=tool_operation,
    ) as operation:
        return _apply_euler_filter(curves, target_info, operation)


def clear_animation_keys(*args):
    return _run_key_command(cmds.cutKey, "clear_animation", clear=True)


def copy_keys(*args):
    global _key_clipboard, _key_clipboard_start_frame

    target_info, target_plugs, selected_objects, selected_channels = (
        animation_context.resolve_command_targets(default_mode="all_animation")
    )
    key_range = animation_context.key_range(
        target_info, target_plugs, selected_objects, selected_channels
    )
    _key_clipboard_start_frame = key_range[0] if key_range else None
    _key_clipboard = _capture_key_clipboard(target_info, target_plugs)
    return _run_key_command(cmds.copyKey, "copy_keys", option="keys")


def cut_keys(*args):
    global _key_clipboard, _key_clipboard_start_frame

    target_info, target_plugs, selected_objects, selected_channels = (
        animation_context.resolve_command_targets(default_mode="all_animation")
    )
    key_range = animation_context.key_range(
        target_info, target_plugs, selected_objects, selected_channels
    )
    _key_clipboard_start_frame = key_range[0] if key_range else None
    _key_clipboard = _capture_key_clipboard(target_info, target_plugs)
    return _run_key_command(cmds.cutKey, "cut_keys", option="keys")


def delete_keys(*args):
    return _run_key_command(
        cmds.cutKey,
        "delete_keys",
        default_mode="current_frame",
        clear=True,
    )


def paste_keys(*args, **kwargs):
    tool_operation = kwargs.pop("tool_operation", None)
    target_info, target_plugs, selected_objects, selected_channels = (
        animation_context.resolve_command_targets(
            default_mode="current_frame", include_shapes=False
        )
    )
    if not target_plugs and not selected_objects:
        return wutil.make_inViewMessage("Select at least one object or channel")

    with _animation_command_context(
        "Paste Keys", "paste_keys", default_mode="current_frame", tool_operation=tool_operation
    ):
        destination_times = _selected_destination_times()
        if destination_times and _paste_snapshot_to_selected_times(destination_times):
            return True
        kwargs = {"option": "merge"}
        return _paste_key_targets(
            _clipboard_ordered_targets(target_plugs),
            selected_objects,
            selected_channels,
            **kwargs
        )


def paste_keys_relative(*args, **kwargs):
    global _key_clipboard_start_frame

    tool_operation = kwargs.pop("tool_operation", None)
    target_info, target_plugs, selected_objects, selected_channels = (
        animation_context.resolve_command_targets(
            default_mode="current_frame", include_shapes=False
        )
    )
    if not target_plugs and not selected_objects:
        return wutil.make_inViewMessage("Select at least one object or channel")

    paste_time = target_info["time_context"].start_frame
    with _animation_command_context(
        "Paste Keys Relative",
        "paste_keys_relative",
        default_mode="current_frame",
        tool_operation=tool_operation,
    ):
        destination_times = _selected_destination_times()
        if destination_times and _paste_snapshot_to_selected_times(destination_times):
            return True
        time_offset = paste_time
        if _key_clipboard_start_frame is not None:
            time_offset = paste_time - _key_clipboard_start_frame
        kwargs = {"option": "merge", "timeOffset": time_offset}
        return _paste_key_targets(
            _clipboard_ordered_targets(target_plugs),
            selected_objects,
            selected_channels,
            **kwargs
        )


def crop_animation(*args, **kwargs):
    tool_operation = kwargs.pop("tool_operation", None)
    target_info, target_plugs, selected_objects, selected_channels = (
        animation_context.resolve_command_targets(default_mode="all_animation")
    )
    if not target_plugs and not selected_objects:
        return wutil.make_inViewMessage("Select at least one object or channel")

    time_context = target_info["time_context"]
    crop_range = (time_context.start_frame, time_context.end_frame)
    curves = animation_context.curves(target_info)
    if not curves:
        return wutil.make_inViewMessage("No animation curves found")

    with _animation_command_context(
        "Crop Animation", "crop_animation", timerange=crop_range, tool_operation=tool_operation
    ):
        for curve in curves:
            frames = cmds.keyframe(curve, query=True, timeChange=True) or []
            for frame in frames:
                if frame < crop_range[0] or frame > crop_range[1]:
                    cmds.cutKey(curve, time=(frame, frame), clear=True)


def _flat_redundant_key_times(curve, target_info, tolerance=1e-8):
    try:
        all_times = [
            float(value)
            for value in (cmds.keyframe(curve, query=True, timeChange=True) or [])
        ]
        all_values = [
            float(value)
            for value in (cmds.keyframe(curve, query=True, valueChange=True) or [])
        ]
    except _COMMAND_ERRORS:
        return []
    if len(all_times) < 3 or len(all_times) != len(all_values):
        return []

    target_times = {
        float(value) for value in animation_context.key_times(curve, target_info)
    }
    redundant = []
    for index in range(1, len(all_times) - 1):
        if all_times[index] not in target_times:
            continue
        previous_value = all_values[index - 1]
        value = all_values[index]
        next_value = all_values[index + 1]
        if math.isclose(
            previous_value, value, rel_tol=1e-9, abs_tol=tolerance
        ) and math.isclose(
            value,
            next_value,
            rel_tol=1e-9,
            abs_tol=tolerance,
        ):
            redundant.append(all_times[index])
    return redundant


def _remove_flat_redundant_keys(curves, target_info, operation=None):
    removed = 0
    with animation_context.preserve_key_selection():
        for curve in curves:
            if operation is not None and operation.cancelled:
                break
            redundant_times = _flat_redundant_key_times(curve, target_info)
            for key_time in reversed(redundant_times):
                cmds.cutKey(curve, time=(key_time, key_time), clear=True)
                removed += 1
            if operation is not None:
                operation.step()
    return removed


def _remove_tendency_redundant_keys(
    curves, target_info, operation=None, tolerance=0.01
):
    """Remove low-detail keys while retaining the fitted motion tendency."""
    removed_count = 0
    with animation_context.preserve_key_selection():
        for curve in curves:
            if operation is not None and operation.cancelled:
                break
            keys = sorted(
                set(
                    float(value)
                    for value in animation_context.key_times(curve, target_info)
                )
            )
            if len(keys) <= 2:
                if operation is not None:
                    operation.step()
                continue

            priority, scores = curveFitting.detail_priority_with_scores(curve, keys)
            redundant = [
                frame
                for frame in reversed(priority)
                if scores.get(frame, 0.0) <= tolerance
            ]
            if redundant:
                redundant_set = set(redundant)
                kept = [frame for frame in keys if frame not in redundant_set]
                shape = curveFitting.capture([curve], kept)
                for frame in sorted(redundant, reverse=True):
                    cmds.cutKey(curve, time=(frame, frame), clear=True)
                    removed_count += 1
                curveFitting.apply(
                    shape,
                    set_values=False,
                    preserve_tangent_types=True,
                )
            if operation is not None:
                operation.step()
    return removed_count


def _redundant_key_targets():
    target_info, _target_plugs, _selected_objects, _selected_channels = (
        animation_context.resolve_command_targets(default_mode="all_animation")
    )
    curves = animation_context.curves(target_info)
    if not curves:
        wutil.make_inViewMessage("No animation curves found")
        return None, None, None

    time_context = target_info["time_context"]
    timerange = (time_context.start_frame, time_context.end_frame)
    return target_info, curves, timerange


def get_remove_redundant_mode():
    mode = settings.get_setting(
        REMOVE_REDUNDANT_MODE_SETTING,
        REMOVE_REDUNDANT_MODE_FLAT,
    )
    return mode if mode in REMOVE_REDUNDANT_MODES else REMOVE_REDUNDANT_MODE_FLAT


def set_remove_redundant_mode(mode):
    if mode not in REMOVE_REDUNDANT_MODES:
        mode = REMOVE_REDUNDANT_MODE_FLAT
    settings.set_setting(REMOVE_REDUNDANT_MODE_SETTING, mode)
    return mode


def remove_redundant_keys(*args, **kwargs):
    tool_operation = kwargs.pop("tool_operation", None)
    mode = get_remove_redundant_mode()
    remove_all = mode == REMOVE_REDUNDANT_MODE_ALL
    label = "Remove All Redundant Keys" if remove_all else "Remove Flat Redundant Keys"
    with _cleanup_command_context(
        tool_operation,
        label,
        "remove_redundant_keys",
    ) as operation:
        operation.start()
        target_info, curves, timerange = _redundant_key_targets()
        if not curves:
            return None
        operation.timerange = timerange
        if remove_all:
            operation.set_total(len(curves))
            removed = _remove_tendency_redundant_keys(
                curves, target_info, operation
            )
        else:
            operation.set_total(len(curves))
            removed = _remove_flat_redundant_keys(curves, target_info, operation)
    if removed == 0:
        wutil.make_inViewMessage("No redundant keys found")
    return removed


def remove_static_anim_curves(*args, **kwargs):
    tool_operation = kwargs.pop("tool_operation", None)
    with _cleanup_command_context(
        tool_operation,
        "Remove Static Anim Curves",
        "remove_static_anim_curves",
    ) as operation:
        operation.start()
        target_info, _target_plugs, _selected_objects, _selected_channels = (
            animation_context.resolve_command_targets(default_mode="all_animation")
        )
        curves = animation_context.curves(target_info)
        if not curves:
            return wutil.make_inViewMessage("No animation curves found")

        static_targets = {}
        operation.set_total(len(curves))
        for curve in curves:
            if operation.cancelled:
                return None
            key_data = animation_context.key_data(curve, target_info)
            if not key_data:
                operation.step()
                continue
            values = [value for _time, value in key_data]
            if max(values) - min(values) <= 1e-8:
                key_times = tuple(time for time, _value in key_data)
                static_targets.setdefault(key_times, []).append(curve)
            operation.step()

        if not static_targets:
            return wutil.make_inViewMessage("No static animation curves found")

        time_context = target_info["time_context"]
        operation.timerange = (time_context.start_frame, time_context.end_frame)
        operation.set_total(len(curves) + len(static_targets))
        removed = False
        for key_times, grouped_curves in static_targets.items():
            if operation.cancelled:
                return None
            try:
                cmds.cutKey(
                    grouped_curves,
                    time=[(key_time, key_time) for key_time in key_times],
                    clear=True,
                )
                removed = True
            except (
                RuntimeError,
                ValueError,
                TypeError,
                AttributeError,
                KeyError,
                IndexError,
            ):
                # Isolate a bad curve without losing the rest of the batch.
                for curve in grouped_curves:
                    try:
                        cmds.cutKey(
                            curve,
                            time=[(key_time, key_time) for key_time in key_times],
                            clear=True,
                        )
                        removed = True
                    except (
                        RuntimeError,
                        ValueError,
                        TypeError,
                        AttributeError,
                        KeyError,
                        IndexError,
                    ):
                        continue
            operation.step()
        if not removed:
            return wutil.make_inViewMessage(
                "Static animation curves could not be removed"
            )
        return True


def reverse_animation(*args, **kwargs):
    tool_operation = kwargs.pop("tool_operation", None)
    target_info, _target_plugs, _selected_objects, _selected_channels = (
        animation_context.resolve_command_targets(default_mode="all_animation")
    )
    curves = animation_context.curves(target_info)
    if not curves:
        return wutil.make_inViewMessage("No animation curves found")

    time_context = target_info["time_context"]
    reverse_range = (time_context.start_frame, time_context.end_frame)
    with _animation_command_context(
        "Reverse Animation",
        "reverse_animation",
        timerange=reverse_range,
        progress_max=len(curves),
        tool_operation=tool_operation,
    ) as operation:
        pivot = (reverse_range[0] + reverse_range[1]) * 0.5
        for curve in curves:
            if operation.cancelled:
                break
            cmds.scaleKey(curve, time=reverse_range, timeScale=-1, timePivot=pivot)
            operation.step()


def _frames_for_key_time_context(time_context):
    frames = tuple(getattr(time_context, "frames", ()) or ())
    if frames:
        return frames
    return (time_context.start_frame,)


def _frames_for_smart_key(time_context):
    """Keep a deliberately chosen sub-frame instead of expanding a UI range."""
    current_time = float(cmds.currentTime(query=True))
    if not math.isclose(
        current_time, round(current_time), rel_tol=0.0, abs_tol=1e-8
    ):
        return (current_time,)
    return _frames_for_key_time_context(time_context)


def _nearest_whole_frame(key_time):
    key_time = float(key_time)
    if key_time >= 0.0:
        return int(math.floor(key_time + 0.5))
    return int(math.ceil(key_time - 0.5))


def _curve_output_plug(curve):
    destinations = selectionMod.get_anim_curve_output_plugs([curve])
    return destinations[0] if destinations else None


def _curve_value_at_frame(curve, frame):
    try:
        values = cmds.keyframe(curve, query=True, eval=True, time=(frame, frame)) or []
        if values:
            return values[0]
    except (RuntimeError, ValueError, TypeError, AttributeError, KeyError, IndexError):
        pass

    plug = _curve_output_plug(curve)
    if plug:
        try:
            return cmds.getAttr(plug, time=frame)
        except (
            RuntimeError,
            ValueError,
            TypeError,
            AttributeError,
            KeyError,
            IndexError,
        ):
            pass
    return None


def _nearest_curve_key_time(curve, frame):
    try:
        key_times = cmds.keyframe(curve, query=True, timeChange=True) or []
    except (RuntimeError, ValueError, TypeError, AttributeError, KeyError, IndexError):
        key_times = []
    if not key_times:
        return None
    return min(key_times, key=lambda key_time: abs(key_time - frame))


def _curve_tangent_types_at_frame(curve, frame):
    source_time = frame
    try:
        key_exists = bool(cmds.keyframe(curve, query=True, time=(frame, frame)))
    except (RuntimeError, ValueError, TypeError, AttributeError, KeyError, IndexError):
        key_exists = False
    if not key_exists:
        source_time = _nearest_curve_key_time(curve, frame)
    if source_time is None:
        return None, None

    try:
        in_types = (
            cmds.keyTangent(
                curve, query=True, time=(source_time, source_time), inTangentType=True
            )
            or []
        )
        out_types = (
            cmds.keyTangent(
                curve, query=True, time=(source_time, source_time), outTangentType=True
            )
            or []
        )
    except (RuntimeError, ValueError, TypeError, AttributeError, KeyError, IndexError):
        return None, None

    return (in_types[0] if in_types else None), (out_types[0] if out_types else None)


def _set_key_on_curve_preserving_tangent(curve, frame):
    value = _curve_value_at_frame(curve, frame)
    if value is None:
        return False

    in_tangent, out_tangent = _curve_tangent_types_at_frame(curve, frame)
    cmds.setKeyframe(curve, time=(frame,), value=value)

    tangent_kwargs = {}
    if in_tangent:
        tangent_kwargs["inTangentType"] = in_tangent
    if out_tangent:
        tangent_kwargs["outTangentType"] = out_tangent
    if tangent_kwargs:
        cmds.keyTangent(curve, edit=True, time=(frame, frame), **tangent_kwargs)
    return True


def _set_selected_graph_editor_curves_current_time(operation=None):
    curves = _unique(selectionMod.get_graph_editor_selected_curves())
    if not curves:
        return False
    if operation is not None:
        operation.set_total(len(curves)).set_status("Setting Smart Keys")
    frame = cmds.currentTime(query=True)
    keyed = False
    for curve in curves:
        if operation is not None and operation.cancelled:
            break
        keyed = _set_key_on_curve_preserving_tangent(curve, frame) or keyed
        if operation is not None:
            operation.step()
    return keyed


def _filter_settable_keyable_attrs(obj, attrs):
    """Keep attrs that are free or driven only by a curve/blend/mute node --
    i.e. safe for Smart Key to key directly. Shared by both Smart Key
    entry points so they treat "keyable" the same way.
    """
    valid = []
    for attr in attrs:
        try:
            conns = cmds.listConnections(f"{obj}.{attr}", source=True, destination=False)
            if not conns:
                valid.append(attr)
                continue
            node_type = cmds.nodeType(conns[0])
            if "animCurve" in node_type or "animBlend" in node_type or "mute" in node_type:
                valid.append(attr)
        except Exception:
            pass
    return valid


def _key_attributes_layer_aware(obj, attributes, frame, layer_context=None):
    """Key ``attributes`` on ``obj`` at ``frame`` through the one shared
    animation-layer destination route (see ``core.animlayers``).

    An attribute that already has a curve on the resolved destination layer
    keeps its existing tangent shape; one that doesn't gets a fresh key,
    added to that layer the same way every other layer-aware tool in TKM
    does it. This is the single path both Smart Key and Smart Key All
    Channels use to actually set a key, so they behave identically.

    Returns ``(keyed_attrs, blocked_attrs)``.
    """
    if not attributes:
        return [], []
    groups, blocked = animlayers.group_attributes_by_destination(
        obj, attributes, context=layer_context
    )
    keyed_attrs = []
    for layer_name, grouped_attributes in groups.items():
        for attr in grouped_attributes:
            plug = "{}.{}".format(obj, attr)
            curve = animlayers.get_anim_curve_for_plug(plug, layer_name=layer_name)
            if curve and _set_key_on_curve_preserving_tangent(curve, frame):
                keyed_attrs.append(attr)
                continue
            key_kwargs = {"attribute": attr, "time": (frame,), "shape": False}
            if layer_name:
                key_kwargs["animLayer"] = layer_name
            try:
                if cmds.setKeyframe(obj, **key_kwargs):
                    keyed_attrs.append(attr)
            except (RuntimeError, ValueError, TypeError):
                pass
    return keyed_attrs, blocked


def set_smart_key(*args, **kwargs):
    tool_operation = kwargs.pop("tool_operation", None)
    target_info, target_plugs, selected_objects, selected_channels = (
        animation_context.resolve_command_targets(
            default_mode="current_frame",
            include_shapes=False,
        )
    )

    selected_objects = _unique(selected_objects)
    target_plugs = _unique(target_plugs)

    frames = _frames_for_smart_key(target_info["time_context"])
    source = target_info.get("source")
    has_graph_keys = bool(target_info.get("has_graph_keys"))

    # Passive Graph Editor/outliner contents must not replace the actual Maya
    # object selection. Only explicitly selected keys or Channel Box channels
    # take precedence over plain selected-object behavior.
    scene_objects = _unique(selectionMod.get_valid_selected_objects(long=True))
    if scene_objects and not has_graph_keys and source != "channel_box":
        selected_objects = scene_objects
        source = "objects"

    layer_context = animlayers.capture_context()

    with _animation_command_context(
        "Set Smart Key",
        tint=False,
        progress_max=0,
        tool_operation=tool_operation,
    ) as operation:
        keyed = (
            _set_selected_graph_editor_curves_current_time(operation)
            if has_graph_keys
            else False
        )

        if not keyed and _is_explicit_channel_source(source) and target_plugs:
            if source == "channel_box":
                operation.set_total(
                    len(target_plugs), reset=has_graph_keys
                ).set_status(
                    "Setting Smart Keys"
                )
                for plug in target_plugs:
                    if operation.cancelled:
                        break
                    if not plug or "." not in plug:
                        operation.step()
                        continue

                    node, attr = plug.rsplit(".", 1)

                    for frame in frames:
                        keyed_attrs, _blocked = _key_attributes_layer_aware(
                            node, [attr], frame, layer_context
                        )
                        keyed = keyed or bool(keyed_attrs)
                    operation.step()
            else:
                curves = animation_context.curves(target_info, include_shapes=False)
                operation.set_total(len(curves), reset=has_graph_keys).set_status(
                    "Setting Smart Keys"
                )
                curve_frames = frames
                if source in (
                    "graph_editor",
                    "graph_editor_outliner",
                ) and not target_info.get("selected_keyframes"):
                    curve_frames = (cmds.currentTime(query=True),)

                for curve in curves:
                    if operation.cancelled:
                        break
                    for frame in curve_frames:
                        keyed = (
                            _set_key_on_curve_preserving_tangent(curve, frame) or keyed
                        )
                    operation.step()

        elif not keyed:
            if not selected_objects:
                return wutil.make_inViewMessage("Select at least one object")

            operation.set_total(
                len(selected_objects), reset=has_graph_keys
            ).set_status(
                "Setting Smart Keys"
            )
            for obj in selected_objects:
                if operation.cancelled:
                    break

                attrs = selectionMod.get_keyable_scalar_attributes(obj)
                if not attrs:
                    operation.step()
                    continue

                valid_attrs = _filter_settable_keyable_attrs(obj, attrs)
                if not valid_attrs:
                    operation.step()
                    continue

                # "Smart" means: touch only channels already animated
                # somewhere (any layer, not just BaseAnimation) if the
                # object has any; otherwise key everything so the object
                # can start being animated.
                animated_attrs = [
                    attr for attr in valid_attrs
                    if animlayers.get_anim_curves_by_layer_for_plug(
                        "{}.{}".format(obj, attr)
                    )
                ]
                target_attrs = animated_attrs or valid_attrs

                for frame in frames:
                    keyed_attrs, _blocked = _key_attributes_layer_aware(
                        obj, target_attrs, frame, layer_context
                    )
                    keyed = keyed or bool(keyed_attrs)
                operation.step()

        if not keyed:
            return wutil.make_inViewMessage("No keyable channels found")


def set_smart_key_all_channels(*args, **kwargs):
    tool_operation = kwargs.pop("tool_operation", None)
    target_info, _target_plugs, selected_objects, _selected_channels = (
        animation_context.resolve_command_targets(
            default_mode="current_frame",
            include_shapes=False,
        )
    )

    selected_objects = _unique(selected_objects)

    frames = _frames_for_smart_key(target_info["time_context"])
    layer_context = animlayers.capture_context()

    with _animation_command_context(
        "Set Smart Key All Channels",
        tint=False,
        progress_max=0,
        tool_operation=tool_operation,
    ) as operation:
        if not selected_objects:
            return wutil.make_inViewMessage("Select at least one object")

        keyed = False
        operation.set_total(len(selected_objects)).set_status(
            "Setting All Smart Keys"
        )
        for obj in selected_objects:
            if operation.cancelled:
                break
            attrs = selectionMod.get_keyable_scalar_attributes(obj)
            if not attrs:
                operation.step()
                continue

            valid_attrs = _filter_settable_keyable_attrs(obj, attrs)
            if not valid_attrs:
                operation.step()
                continue

            for frame in frames:
                keyed_attrs, _blocked = _key_attributes_layer_aware(
                    obj, valid_attrs, frame, layer_context
                )
                keyed = keyed or bool(keyed_attrs)
            operation.step()

        if not keyed:
            return wutil.make_inViewMessage("No keyable channels found")


def _snap_curve_keys(
    curve, rounded_time, key_times, target_value, curve_times
):
    """Merge one whole-frame bucket, keeping its nearest sub-frame key."""
    if not key_times:
        return False
    key_time = min(
        key_times,
        key=lambda value: (abs(float(value) - float(rounded_time)), float(value)),
    )
    try:
        destination_exists = any(
            math.isclose(
                float(existing_time), float(rounded_time), rel_tol=0.0, abs_tol=1e-8
            )
            and not math.isclose(
                float(existing_time), float(key_time), rel_tol=0.0, abs_tol=1e-8
            )
            for existing_time in curve_times
        )
        if destination_exists:
            # Maya's "over" move can leave two nearly coincident keys.
            cmds.cutKey(curve, time=(rounded_time, rounded_time), clear=True)

        for redundant_time in key_times:
            if math.isclose(
                float(redundant_time), float(key_time), rel_tol=0.0, abs_tol=1e-8
            ):
                continue
            cmds.cutKey(
                curve, time=(redundant_time, redundant_time), clear=True
            )

        # Sampled before any deletion, target_value preserves the curve's value
        # at the whole frame. Moving the closest key retains the most relevant
        # tangent weights, locks, and breakdown state.
        cmds.keyframe(
            curve,
            edit=True,
            time=(key_time, key_time),
            absolute=True,
            option="over",
            timeChange=rounded_time,
            valueChange=target_value,
        )
    except (RuntimeError, ValueError, TypeError, AttributeError, KeyError, IndexError):
        return False
    return True


def _curve_value_at_time(curve, curve_fn, time):
    value = open_maya.evaluate_anim_curve(curve_fn, time)
    if value is not None:
        return open_maya.anim_curve_value_to_attr_value(curve, value)
    try:
        values = (
            cmds.keyframe(
                curve,
                time=(time, time),
                query=True,
                eval=True,
            )
            or []
        )
    except _COMMAND_ERRORS:
        values = []
    return values[0] if values else None


def _resolve_snap_targets():
    """Resolve explicit keys first, then the selected scene objects.

    A visible Graph Editor can retain passive curve/outliner state. That state
    must not override an object-only selection for this command.
    """
    target_info, _target_plugs, _selected_objects, _selected_channels = (
        animation_context.resolve_command_targets(
            default_mode="all_animation",
            include_shapes=True,
        )
    )
    if target_info.get("has_graph_keys"):
        return target_info, animation_context.curves(target_info)

    selected_objects = _unique(selectionMod.get_selected_objects(long=True))
    if not selected_objects:
        return target_info, animation_context.curves(target_info)

    target_plugs, source = selectionMod.get_attribute_plugs_from_nodes(
        selected_objects
    )
    if source == "channel_box" and target_plugs:
        curves = selectionMod.get_anim_curves_from_plugs(target_plugs)
    else:
        curves = selectionMod.get_anim_curves_for_nodes(
            selected_objects, include_shapes=True
        )

    object_target_info = dict(target_info)
    object_target_info.update(
        target_plugs=target_plugs,
        target_objects=selected_objects,
        selected_channels=selectionMod.attribute_names_from_plugs(target_plugs),
        selected_curves=curves,
        selected_keyframes=[],
        source=source,
        has_graph_keys=False,
    )
    return object_target_info, curves


def snap_keyframes():
    target_info, curves = _resolve_snap_targets()
    if not curves:
        return wutil.make_inViewMessage("No animation curves found")

    curve_key_times = []
    for curve in curves:
        curve_times = cmds.keyframe(curve, query=True, timeChange=True) or []
        curve_fn = open_maya.anim_curve_fn(curve)
        buckets = {}
        for key_time in animation_context.key_times(curve, target_info):
            rounded_time = _nearest_whole_frame(key_time)
            if math.isclose(
                float(rounded_time),
                float(key_time),
                rel_tol=0.0,
                abs_tol=1e-8,
            ):
                continue
            buckets.setdefault(rounded_time, []).append(key_time)

        snap_data = []
        for rounded_time, key_times in sorted(buckets.items()):
            target_value = _curve_value_at_time(
                curve,
                curve_fn,
                rounded_time,
            )
            if target_value is not None:
                snap_data.append((rounded_time, key_times, target_value))
        if snap_data:
            curve_key_times.append((curve, curve_times, snap_data))
    work_items = sum(
        len(snap_data) for _curve, _curve_times, snap_data in curve_key_times
    )

    if not work_items:
        return wutil.make_inViewMessage("No sub-frame keys found")

    snapped = False
    with toolCommon.tool_operation(
        tool_id="snap",
        label="Snap Keyframes",
        progress=True,
        progress_max=work_items,
        undo=True,
    ) as operation:
        operation.start()
        for curve, curve_times, snap_data in curve_key_times:
            for rounded_time, key_times, target_value in snap_data:
                if operation.cancelled:
                    return
                snapped = (
                    _snap_curve_keys(
                        curve,
                        rounded_time,
                        key_times,
                        target_value,
                        curve_times,
                    )
                    or snapped
                )
                operation.step()

    if not snapped:
        return wutil.make_inViewMessage("No sub-frame keys found")
