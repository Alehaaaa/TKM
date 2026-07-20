"""Animation curve editing, cleanup, smart-key, and snapping behavior."""

from contextlib import contextmanager
import math

from maya import cmds

from TheKeyMachine.core import animation_context
from TheKeyMachine.core import openMayaUtils as open_maya
from TheKeyMachine.mods import selectionMod
from TheKeyMachine.mods import settingsMod as settings
from TheKeyMachine.tools import common as toolCommon
from TheKeyMachine.widgets import util as wutil


_key_clipboard_start_frame = None
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


def _apply_euler_filter(curves, target_info):
    changed_groups = 0
    with animation_context.preserve_key_selection():
        for curve in curves or []:
            for start_time, end_time, offset in _euler_turn_groups(
                curve, target_info, _euler_full_turn()
            ):
                cmds.keyframe(
                    curve,
                    edit=True,
                    time=(start_time, end_time),
                    relative=True,
                    valueChange=offset,
                )
                changed_groups += 1
    return changed_groups


def delete_keyframes_before_current_time():
    # Obtén los objetos seleccionados
    selected = selectionMod.get_selected_objects()

    if not selected:
        return wutil.make_inViewMessage("Select at least one object")

    # Obtiene el tiempo actual
    current_time = cmds.currentTime(query=True)

    for obj in selected:
        # Obtiene todos los keyframes del objeto
        keyframes = cmds.keyframe(obj, query=True)

        if not keyframes:
            continue

        # Elimina los keyframes que están antes de la currentTime
        for keyframe in sorted(keyframes):
            if keyframe < current_time:
                cmds.cutKey(obj, time=(keyframe, keyframe))


def delete_keyframes_after_current_time():
    # Obtén los objetos seleccionados
    selected = selectionMod.get_selected_objects()

    if not selected:
        return wutil.make_inViewMessage("Select at least one object")

    # Obtiene el tiempo actual
    current_time = cmds.currentTime(query=True)

    for obj in selected:
        # Obtiene todos los keyframes del objeto
        keyframes = cmds.keyframe(obj, query=True)

        if not keyframes:
            continue

        # Elimina los keyframes que están después de la currentTime
        for keyframe in sorted(keyframes):
            if keyframe > current_time:
                cmds.cutKey(obj, time=(keyframe, keyframe))


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
    label, tint_key=None, default_mode="all_animation", timerange=None, tint=True
):
    """Wrap animation hotkey commands with the shared tool operation.

    tint=False disables the timeline/context tint for commands that should feel silent.
    """
    operation_tint = "none"
    if tint:
        operation_tint = "range" if timerange is not None else "context"

    with toolCommon.tool_operation(
        tool_id=tint_key,
        label=label,
        progress=True,
        progress_max=1,
        undo=True,
        undo_name=toolCommon.make_undo_chunk_name(title=label),
        tint=operation_tint,
        timerange=timerange,
        default_mode=default_mode,
        tint_key=tint_key,
    ):
        yield


def _filter_curves_preserving_selection(
    curves, filter_name, command_label, target_info
):
    time_context = target_info.get("time_context")
    filter_kwargs = {}
    if time_context and time_context.mode == "graph_editor_keys":
        filter_kwargs["selectedKeys"] = True
    elif time_context and time_context.mode == "time_slider_range":
        filter_kwargs.update(
            startTime=time_context.start_frame,
            endTime=time_context.end_frame,
        )
    with animation_context.preserve_key_selection():
        try:
            return cmds.filterCurve(curves, filter=filter_name, **filter_kwargs)
        except (RuntimeError, TypeError) as exc:
            if filter_kwargs:
                cmds.warning(
                    "{} could not run on the selected time range: {}".format(
                        command_label, exc
                    )
                )
                return None
            raise


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


def apply_smart_euler_filter(*args):
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
        "Apply Smart Euler Filter", "apply_smart_euler_filter"
    ):
        return _apply_euler_filter(curves, target_info)


def clear_animation_keys(*args):
    return _run_key_command(cmds.cutKey, "clear_animation", clear=True)


def copy_keys(*args):
    global _key_clipboard_start_frame

    target_info, target_plugs, selected_objects, selected_channels = (
        animation_context.resolve_command_targets(default_mode="all_animation")
    )
    key_range = animation_context.key_range(
        target_info, target_plugs, selected_objects, selected_channels
    )
    _key_clipboard_start_frame = key_range[0] if key_range else None
    return _run_key_command(cmds.copyKey, "copy_keys", option="keys")


def cut_keys(*args):
    global _key_clipboard_start_frame

    target_info, target_plugs, selected_objects, selected_channels = (
        animation_context.resolve_command_targets(default_mode="all_animation")
    )
    key_range = animation_context.key_range(
        target_info, target_plugs, selected_objects, selected_channels
    )
    _key_clipboard_start_frame = key_range[0] if key_range else None
    return _run_key_command(cmds.cutKey, "cut_keys", option="keys")


def delete_keys(*args):
    return _run_key_command(
        cmds.cutKey,
        "delete_keys",
        default_mode="current_frame",
        clear=True,
    )


def paste_keys(*args):
    target_info, target_plugs, selected_objects, selected_channels = (
        animation_context.resolve_command_targets(
            default_mode="current_frame", include_shapes=False
        )
    )
    if not target_plugs and not selected_objects:
        return wutil.make_inViewMessage("Select at least one object or channel")

    with _animation_command_context(
        "Paste Keys", "paste_keys", default_mode="current_frame"
    ):
        kwargs = {"option": "merge"}
        return _paste_key_targets(
            target_plugs, selected_objects, selected_channels, **kwargs
        )


def paste_keys_relative(*args):
    global _key_clipboard_start_frame

    target_info, target_plugs, selected_objects, selected_channels = (
        animation_context.resolve_command_targets(
            default_mode="current_frame", include_shapes=False
        )
    )
    if not target_plugs and not selected_objects:
        return wutil.make_inViewMessage("Select at least one object or channel")

    paste_time = target_info["time_context"].start_frame
    with _animation_command_context(
        "Paste Keys Relative", "paste_keys_relative", default_mode="current_frame"
    ):
        time_offset = paste_time
        if _key_clipboard_start_frame is not None:
            time_offset = paste_time - _key_clipboard_start_frame
        kwargs = {"option": "merge", "timeOffset": time_offset}
        return _paste_key_targets(
            target_plugs, selected_objects, selected_channels, **kwargs
        )


def crop_animation(*args):
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
        "Crop Animation", "crop_animation", timerange=crop_range
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


def _remove_flat_redundant_keys(curves, target_info):
    removed = 0
    with animation_context.preserve_key_selection():
        for curve in curves:
            redundant_times = _flat_redundant_key_times(curve, target_info)
            for key_time in reversed(redundant_times):
                cmds.cutKey(curve, time=(key_time, key_time), clear=True)
                removed += 1
    return removed


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


def remove_redundant_keys(*args):
    target_info, curves, timerange = _redundant_key_targets()
    if not curves:
        return None

    mode = get_remove_redundant_mode()
    remove_all = mode == REMOVE_REDUNDANT_MODE_ALL
    with _animation_command_context(
        "Remove All Redundant Keys" if remove_all else "Remove Flat Redundant Keys",
        "remove_redundant_keys",
        timerange=timerange,
        tint=False,
    ):
        if remove_all:
            return _filter_curves_preserving_selection(
                curves, "simplify", "Remove Redundant Keys", target_info
            )
        removed = _remove_flat_redundant_keys(curves, target_info)
    if removed == 0:
        wutil.make_inViewMessage("No flat redundant keys found")
    return removed


def remove_static_anim_curves(*args):
    target_info, _target_plugs, _selected_objects, _selected_channels = (
        animation_context.resolve_command_targets(default_mode="all_animation")
    )
    curves = animation_context.curves(target_info)
    if not curves:
        return wutil.make_inViewMessage("No animation curves found")

    static_targets = {}
    for curve in curves:
        key_data = animation_context.key_data(curve, target_info)
        if not key_data:
            continue
        values = [value for _time, value in key_data]
        if max(values) - min(values) <= 1e-8:
            key_times = tuple(time for time, _value in key_data)
            static_targets.setdefault(key_times, []).append(curve)

    if not static_targets:
        return wutil.make_inViewMessage("No static animation curves found")

    time_context = target_info["time_context"]
    _range = (time_context.start_frame, time_context.end_frame)

    with _animation_command_context(
        "Remove Static Anim Curves",
        "remove_static_anim_curves",
        timerange=_range,
        tint=False,
    ):
        removed = False
        for key_times, grouped_curves in static_targets.items():
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
        if not removed:
            return wutil.make_inViewMessage(
                "Static animation curves could not be removed"
            )
        return True


def reverse_animation(*args):
    target_info, _target_plugs, _selected_objects, _selected_channels = (
        animation_context.resolve_command_targets(default_mode="all_animation")
    )
    curves = animation_context.curves(target_info)
    if not curves:
        return wutil.make_inViewMessage("No animation curves found")

    time_context = target_info["time_context"]
    reverse_range = (time_context.start_frame, time_context.end_frame)
    with _animation_command_context(
        "Reverse Animation", "reverse_animation", timerange=reverse_range
    ):
        pivot = (reverse_range[0] + reverse_range[1]) * 0.5
        for curve in curves:
            cmds.scaleKey(curve, time=reverse_range, timeScale=-1, timePivot=pivot)


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


def _set_selected_graph_editor_curves_current_time():
    curves = _unique(selectionMod.get_graph_editor_selected_curves())
    if not curves:
        return False
    frame = cmds.currentTime(query=True)
    keyed = False
    for curve in curves:
        keyed = _set_key_on_curve_preserving_tangent(curve, frame) or keyed
    return keyed


def set_smart_key(*args):
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

    with _animation_command_context(
        "Set Smart Key",
        tint=False,
    ):
        keyed = (
            _set_selected_graph_editor_curves_current_time()
            if has_graph_keys
            else False
        )

        if not keyed and _is_explicit_channel_source(source) and target_plugs:
            if source == "channel_box":
                for plug in target_plugs:
                    if not plug or "." not in plug:
                        continue

                    node, attr = plug.rsplit(".", 1)

                    try:
                        for frame in frames:
                            cmds.setKeyframe(node, attribute=attr, time=(frame,))
                            keyed = True
                    except (RuntimeError, ValueError, TypeError):
                        pass
            else:
                curves = animation_context.curves(target_info, include_shapes=False)
                curve_frames = frames
                if source in (
                    "graph_editor",
                    "graph_editor_outliner",
                ) and not target_info.get("selected_keyframes"):
                    curve_frames = (cmds.currentTime(query=True),)

                for curve in curves:
                    for frame in curve_frames:
                        keyed = (
                            _set_key_on_curve_preserving_tangent(curve, frame) or keyed
                        )

        elif not keyed:
            if not selected_objects:
                return wutil.make_inViewMessage("Select at least one object")

            for obj in selected_objects:
                animated_attrs = selectionMod.get_animated_channels_for_node(obj)

                if animated_attrs:
                    animated_plugs = [
                        "{}.{}".format(obj, attr) for attr in animated_attrs
                    ]
                    curves = selectionMod.get_anim_curves_from_plugs(animated_plugs)
                    for curve in curves:
                        for frame in frames:
                            keyed = (
                                _set_key_on_curve_preserving_tangent(curve, frame)
                                or keyed
                            )
                    continue

                attrs = selectionMod.get_keyable_scalar_attributes(obj)
                if not attrs:
                    continue
                try:
                    for frame in frames:
                        cmds.setKeyframe(obj, attribute=attrs, time=(frame,))
                        keyed = True
                except (RuntimeError, ValueError, TypeError):
                    pass

        if not keyed:
            return wutil.make_inViewMessage("No keyable channels found")


def set_smart_key_all_channels(*args):
    target_info, _target_plugs, selected_objects, _selected_channels = (
        animation_context.resolve_command_targets(
            default_mode="current_frame",
            include_shapes=False,
        )
    )

    selected_objects = _unique(selected_objects)

    frames = _frames_for_smart_key(target_info["time_context"])

    with _animation_command_context(
        "Set Smart Key All Channels",
        tint=False,
    ):
        if not selected_objects:
            return wutil.make_inViewMessage("Select at least one object")

        keyed = False
        for obj in selected_objects:
            attrs = selectionMod.get_keyable_scalar_attributes(obj)
            if not attrs:
                continue

            try:
                for frame in frames:
                    cmds.setKeyframe(obj, attribute=attrs, time=(frame,))
                    keyed = True
            except (RuntimeError, ValueError, TypeError):
                pass

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
