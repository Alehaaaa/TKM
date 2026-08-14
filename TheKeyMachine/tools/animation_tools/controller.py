"""Animation curve editing, cleanup, smart-key, and snapping behavior."""

from contextlib import contextmanager
import math

from maya import cmds

from TheKeyMachine.maya import animation
from TheKeyMachine.maya import maya_api
from TheKeyMachine.maya import selection
from TheKeyMachine.core import settings
from TheKeyMachine.tools import clipboard as toolClipboard
from TheKeyMachine.tools import common as toolCommon
from TheKeyMachine.ui.widgets import timeline
from TheKeyMachine.ui.widgets import util as wutil


_CURVE_CLIPBOARD_SLOT = "curve_keys"
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

# ----------------------------
# Undo-free, refireable time navigation batching
# ----------------------------
_nav_pending_actions = []
_nav_flush_scheduled = False
_nav_idle_callback_id = None
_NAV_TIME_TOLERANCE = 0.000001


def _nav_queue(kind, amount, context=()):
    global _nav_flush_scheduled

    try:
        amount = int(amount)
    except (TypeError, ValueError, OverflowError):
        return False
    if not amount:
        return False
    context = context if kind == "curve_key" else ()
    if kind == "curve_key" and not context:
        return False

    signature = (kind, context)
    if _nav_pending_actions and _nav_pending_actions[-1][:2] == signature:
        combined = _nav_pending_actions[-1][2] + amount
        if combined:
            _nav_pending_actions[-1] = (kind, context, combined)
        else:
            _nav_pending_actions.pop()
    else:
        _nav_pending_actions.append((kind, context, amount))

    if not _nav_pending_actions or _nav_flush_scheduled:
        return True
    _nav_flush_scheduled = True
    _nav_schedule_flush()
    return True


def _nav_request_frame_step(amount):
    """Queue an unclamped frame step and combine rapid repeated requests."""
    return _nav_queue("frame", amount)


def _nav_request_curve_key_step(amount, curves, time_range=None):
    """Queue a native step through selected animation curves."""
    curves = tuple(dict.fromkeys(curves or []))
    normalized_range = None
    if time_range:
        try:
            normalized_range = tuple(sorted((
                float(time_range[0]),
                float(time_range[1]),
            )))
        except (IndexError, TypeError, ValueError):
            normalized_range = None
    if not curves and not normalized_range:
        return False
    return _nav_queue("curve_key", amount, (curves, normalized_range))


def _nav_accumulate_pending_key_step(amount):
    """Add to an already queued key step without querying curve data again."""
    if not _nav_pending_actions or _nav_pending_actions[-1][0] != "curve_key":
        return False
    try:
        amount = int(amount)
    except (TypeError, ValueError, OverflowError):
        return False
    if not amount:
        return True

    kind, times, pending_amount = _nav_pending_actions[-1]
    combined = pending_amount + amount
    if combined:
        _nav_pending_actions[-1] = (kind, times, combined)
    else:
        _nav_pending_actions.pop()
    return True


def _nav_schedule_flush():
    global _nav_idle_callback_id
    _nav_idle_callback_id = maya_api.add_event_callback("idle", _nav_flush_from_idle)
    if _nav_idle_callback_id is None:
        _nav_flush_pending()


def _nav_flush_from_idle(*_args):
    global _nav_idle_callback_id
    callback_id = _nav_idle_callback_id
    _nav_idle_callback_id = None
    maya_api.remove_callback(callback_id)
    return _nav_flush_pending()


def _nav_flush_pending(*_args):
    """Apply the accumulated navigation batch with one Maya API time change."""
    global _nav_flush_scheduled

    actions = list(_nav_pending_actions)
    _nav_pending_actions[:] = []
    _nav_flush_scheduled = False
    if not actions:
        return False

    current = maya_api.current_time()
    if current is None:
        return False
    for kind, context, amount in actions:
        if kind == "frame":
            current += amount
        elif kind == "curve_key":
            curves, time_range = context
            if curves:
                destination = maya_api.step_anim_curve_key_time(
                    curves,
                    current,
                    amount,
                    time_range=time_range,
                    tolerance=_NAV_TIME_TOLERANCE,
                )
            else:
                destination = None
            current = destination if destination is not None else current + amount
            if time_range:
                current = max(time_range[0], min(time_range[1], current))
    return maya_api.set_current_time(current)


def cancel_pending_navigation():
    """Discard queued work when the TKM runtime is shutting down."""
    global _nav_flush_scheduled, _nav_idle_callback_id
    maya_api.remove_callback(_nav_idle_callback_id)
    _nav_idle_callback_id = None
    _nav_pending_actions[:] = []
    _nav_flush_scheduled = False


def cleanup():
    """Release runtime resources held by this tool. Called on TKM shutdown."""
    cancel_pending_navigation()


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
    closest_value = maya_api.closest_euler_angle_cut(value, reference)
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
        float(value) for value in target_info.key_times(curve)
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
    with animation.preserve_key_selection():
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
    target_info = animation.resolve_context(
        include_channels=True, include_shapes=True, resolve_curves=True
    )
    curves = target_info.curves
    if not _validate_curve_tool_targets(target_info, curves, "delete"):
        return None
    current_time = cmds.currentTime(query=True)
    operation = toolCommon.current_tool_operation()
    if operation is not None:
        operation.set_total(len(curves)).set_status("Deleting Keys Before Current")
    deleted = False
    for curve in curves:
        if operation is not None and operation.cancelled:
            break
        keyframes = cmds.keyframe(curve, query=True, timeChange=True) or []
        before = [frame for frame in keyframes if frame < current_time]
        if before:
            cmds.cutKey(curve, time=(min(before), max(before)), clear=True)
            deleted = True
        if operation is not None:
            operation.step()
    if not deleted:
        return animation.notify_empty("keys", "delete")


def delete_keyframes_after_current_time():
    target_info = animation.resolve_context(
        include_channels=True, include_shapes=True, resolve_curves=True
    )
    curves = target_info.curves
    if not _validate_curve_tool_targets(target_info, curves, "delete"):
        return None
    current_time = cmds.currentTime(query=True)
    operation = toolCommon.current_tool_operation()
    if operation is not None:
        operation.set_total(len(curves)).set_status("Deleting Keys After Current")
    deleted = False
    for curve in curves:
        if operation is not None and operation.cancelled:
            break
        keyframes = cmds.keyframe(curve, query=True, timeChange=True) or []
        after = [frame for frame in keyframes if frame > current_time]
        if after:
            cmds.cutKey(curve, time=(min(after), max(after)), clear=True)
            deleted = True
        if operation is not None:
            operation.step()
    if not deleted:
        return animation.notify_empty("keys", "delete")


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
        animation.notify_empty()


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
    preserve_time_selection=False,
):
    """Wrap animation hotkey commands with the shared tool operation.

    tint=False disables the timeline/context tint for commands that should feel silent.

    ``toolCommon.tool_operation()`` itself detects when core/trigger.py's
    dispatcher already has an operation open for this command and merges
    into it -- so calling it here, even from a command that dispatch already
    wrapped, still yields exactly one operation, one undo chunk, and one
    TKM_DEBUG_TIMING line per click. No reuse plumbing needed at this layer.
    """
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
        preserve_time_selection=preserve_time_selection,
    ) as operation:
        yield operation


@contextmanager
def _cleanup_command_context(label, tool_id):
    """Create a tint-less operation with caller-managed progress."""
    with _animation_command_context(
        label,
        tool_id,
        tint=False,
        progress_max=0,
    ) as operation:
        yield operation


def _run_key_command(
    command,
    command_name,
    default_mode="all_animation",
    target_context=None,
    tint_range=None,
    validate=True,
    preserve_time_selection=False,
    **base_kwargs
):
    if target_context:
        target_info, curves = target_context
    else:
        target_info = animation.resolve_context(
            default_mode=default_mode,
            include_channels=True,
            include_shapes=True,
            resolve_curves=True,
        )
        curves = target_info.curves
    action = {
        "clear_animation": "clear",
        "copy_keys": "copy",
        "cut_keys": "cut",
        "delete_keys": "delete",
    }.get(command_name, "edit")
    if validate and not _validate_curve_tool_targets(
        target_info,
        curves,
        action,
        require_keys=True,
    ):
        return None
    time_context = target_info.time

    with toolCommon.tool_operation(
        tool_id=command_name,
        label=toolCommon.humanize_tool_name(command_name),
        progress=False,
        undo=True,
        undo_name=toolCommon.make_undo_chunk_name(tool_id=command_name),
        tint="range" if tint_range else "none",
        timerange=tint_range,
        preserve_time_selection=preserve_time_selection,
    ):
        kwargs = dict(base_kwargs)
        selected_keyframes = target_info.selected_keys or []
        if selected_keyframes:
            curve_times = {}
            for curve, key_time in selected_keyframes:
                curve_times.setdefault(curve, []).append(float(key_time))
            result = None
            for curve, key_times in curve_times.items():
                for key_time in sorted(set(key_times)):
                    command_kwargs = dict(kwargs)
                    command_kwargs["time"] = (key_time, key_time)
                    result = command(curve, **command_kwargs)
            return result

        kwargs.update(animation.selection_time_kwargs(time_context))
        if default_mode == "current_frame" and not _has_key_time_filter(kwargs):
            frame = cmds.currentTime(query=True)
            kwargs["time"] = (frame, frame)

        result = None
        for curve in curves:
            result = command(curve, **kwargs)
        return result


def _has_key_time_filter(kwargs):
    return any(key in kwargs for key in ("time", "index", "float"))


def _is_explicit_channel_source(source):
    return source in (
        "channel_box",
        "graph_editor",
        "graph_editor_outliner",
    )


def _capture_curve_clipboard(target_info, curves):
    entries = []
    all_times = []
    layer_context = target_info.layer_scope or {}
    curve_layers = layer_context.get("curve_layers") or {}
    for curve in curves or []:
        key_data = target_info.key_data(curve)
        if not key_data:
            continue
        output_plugs = selection.get_anim_curve_output_plugs([curve])
        plug = output_plugs[0] if output_plugs else None
        attribute = plug.rsplit(".", 1)[-1] if plug and "." in plug else None
        key_times = [float(time) for time, _value in key_data]
        tangent_snapshots = animation.key_tangent_snapshots(
            curve,
            key_times,
        )
        keys = []
        for index, (time, value) in enumerate(key_data):
            time = float(time)
            keys.append({
                "time": time,
                "value": float(value),
                "tangent": (
                    tangent_snapshots[index]
                    if index < len(tangent_snapshots)
                    else {}
                ),
            })
            all_times.append(time)
        entries.append({
            "curve": curve,
            "plug": plug,
            "attribute": attribute,
            "layer": curve_layers.get(curve),
            "start": min(key_times),
            "end": max(key_times),
            "keys": keys,
        })
    if not entries:
        return None
    source_start = min(all_times)
    for entry in entries:
        curve = entry.get("curve")
        curve_fn = maya_api.anim_curve_fn(curve)
        entry["source_anchor_value"] = _curve_value_at_time(
            curve,
            curve_fn,
            source_start,
        )
    return {
        "schema": 2,
        "entries": entries,
        "start": source_start,
        "end": max(all_times),
    }


def _save_curve_clipboard(data):
    if not data:
        return False
    toolClipboard.save(_CURVE_CLIPBOARD_SLOT, data)
    return True


def _load_curve_clipboard():
    data = toolClipboard.load(_CURVE_CLIPBOARD_SLOT)
    if not isinstance(data, dict) or not data.get("entries"):
        return None
    return data


def _spec_attribute(spec):
    plug = spec.get("plug")
    if not plug and spec.get("curve"):
        output_plugs = selection.get_anim_curve_output_plugs([spec["curve"]])
        plug = output_plugs[0] if output_plugs else None
    return plug.rsplit(".", 1)[-1] if plug and "." in plug else None


def _pair_explicit_paste_targets(specs, entries):
    """Pair explicit Graph Editor/Channel Box targets without silent cycling."""
    if not specs or not entries:
        return []
    if len(entries) == 1:
        return [(spec, entries[0]) for spec in specs]
    if len(specs) == len(entries):
        return list(zip(specs, entries))

    entries_by_attribute = {}
    ambiguous_attributes = set()
    for entry in entries:
        attribute = entry.get("attribute")
        if not attribute:
            continue
        if attribute in entries_by_attribute:
            ambiguous_attributes.add(attribute)
        else:
            entries_by_attribute[attribute] = entry
    return [
        (spec, entries_by_attribute[attribute])
        for spec in specs
        for attribute in [_spec_attribute(spec)]
        if attribute in entries_by_attribute
        and attribute not in ambiguous_attributes
    ]


def _paste_layer_mapping(entries, layer_context):
    scope_layers = list(layer_context.get("scope_layer_names") or [])
    source_layers = list(dict.fromkeys(
        entry.get("layer") for entry in entries or []
    ))
    if not scope_layers:
        return {layer: None for layer in source_layers}
    if len(source_layers) == 1:
        source_layer = source_layers[0]
        destination = (
            source_layer
            if source_layer in scope_layers
            else layer_context.get("active_layer") or scope_layers[-1]
        )
        return {source_layer: destination}
    if all(layer in scope_layers for layer in source_layers):
        return {layer: layer for layer in source_layers}
    if len(source_layers) == len(scope_layers):
        return dict(zip(source_layers, scope_layers))
    return {
        layer: layer for layer in source_layers
        if layer in scope_layers
    }


def _assign_paste_layers(mappings, layer_mapping):
    assigned = []
    for spec, entry in mappings:
        spec = dict(spec)
        source_layer = entry.get("layer")
        if source_layer not in layer_mapping:
            continue
        spec["layer"] = layer_mapping[source_layer]
        assigned.append((spec, entry))
    return assigned


def _paste_target_mappings(target_info, clipboard_data):
    entries = list((clipboard_data or {}).get("entries") or [])
    if not entries:
        return []
    layer_context = target_info.layer_scope or {}
    layer_mapping = _paste_layer_mapping(entries, layer_context)

    time_context = target_info.time
    current_time = float(cmds.currentTime(query=True))
    anchor_time = (
        float(time_context.start_frame)
        if time_context and time_context.mode == "time_slider_range"
        else current_time
    )
    selected_keyframes = (
        target_info.selected_keys or []
        if target_info.source == "graph_editor"
        else []
    )
    if selected_keyframes:
        curve_frames = {}
        for curve, frame in selected_keyframes:
            curve_frames.setdefault(curve, []).append(float(frame))
        specs = [
            {"curve": curve, "plug": None, "anchor": min(frames)}
            for curve, frames in curve_frames.items()
        ]
        return _pair_explicit_paste_targets(specs, entries)

    selected_objects = target_info.objects or []
    channel_plugs = target_info.plugs or []
    if target_info.source == "channel_box" and channel_plugs:
        specs = [
            {"curve": None, "plug": plug, "anchor": anchor_time}
            for plug in _unique(channel_plugs)
        ]
        return _assign_paste_layers(
            _pair_explicit_paste_targets(specs, entries),
            layer_mapping,
        )

    object_entries = [
        entry for entry in entries if entry.get("attribute") != "weight"
    ]
    entries_by_object = {}
    for entry in object_entries:
        source_plug = entry.get("plug")
        source_object = (
            source_plug.rsplit(".", 1)[0]
            if source_plug and "." in source_plug
            else None
        )
        entries_by_object.setdefault(source_object, []).append(entry)

    if len(entries_by_object) == 1:
        source_groups = [next(iter(entries_by_object.values()))] * len(selected_objects)
    elif len(entries_by_object) == len(selected_objects):
        source_groups = list(entries_by_object.values())
    else:
        source_groups = []

    mappings = []
    for obj, object_group in zip(selected_objects, source_groups):
        try:
            attributes = set(cmds.listAttr(obj) or [])
        except _COMMAND_ERRORS:
            attributes = set()
        for entry in object_group:
            attribute = entry.get("attribute")
            if not attribute:
                continue
            if entry.get("layer") not in layer_mapping:
                continue
            if attribute not in attributes:
                continue
            mappings.append((
                {
                    "curve": None,
                    "plug": "{}.{}".format(obj, attribute),
                    "anchor": anchor_time,
                    "layer": layer_mapping.get(entry.get("layer")),
                },
                entry,
            ))

    scope_layers = layer_context.get("scope_layer_names") or []
    weight_entries = [
        entry for entry in entries if entry.get("attribute") == "weight"
    ]
    if len(weight_entries) == 1:
        weight_pairs = [
            (layer_name, weight_entries[0]) for layer_name in scope_layers
        ]
    else:
        weight_pairs = [
            (layer_mapping[entry.get("layer")], entry)
            for entry in weight_entries
            if entry.get("layer") in layer_mapping
        ]
    for layer_name, entry in weight_pairs:
        weight_curves = animation.weight_curves(layer_name)
        mappings.append((
            {
                "curve": weight_curves[0] if weight_curves else None,
                "plug": "{}.weight".format(layer_name),
                "anchor": anchor_time,
                "layer": layer_name,
                "layer_weight": True,
            },
            entry,
        ))
    return mappings


def _paste_layer_for_entry(entry, layer_context):
    scope_layers = layer_context.get("scope_layer_names") or []
    copied_layer = entry.get("layer")
    if copied_layer in scope_layers:
        return copied_layer
    active_layer = layer_context.get("active_layer")
    return active_layer if active_layer in scope_layers else None


def _paste_curves_for_plug(plug, layer_context, layer_name=None):
    scope_layers = layer_context.get("scope_layer_names") or []
    requested_layers = [layer_name] if layer_name in scope_layers else scope_layers
    if layer_context.get("has_layers"):
        return list(animation.layer_graph.ownership(
            [plug],
            requested_layers,
            scene_layers=layer_context.get("scene_layers"),
        ))
    try:
        curves = cmds.keyframe(
            plug,
            query=True,
            name=True,
            animation="objects",
        ) or []
    except _COMMAND_ERRORS:
        curves = []
    if isinstance(curves, str):
        curves = [curves]
    return _unique(curves)


def _create_paste_curve(
    plug,
    layer_context,
    time,
    value,
    layer_name=None,
    layer_weight=False,
):
    if not plug or "." not in plug:
        return None
    node, attribute = plug.rsplit(".", 1)
    kwargs = {
        "attribute": attribute,
        "time": (time,),
        "value": value,
    }
    if layer_name and layer_context.get("has_layers") and not layer_weight:
        kwargs["animLayer"] = layer_name
    try:
        cmds.setKeyframe(node, **kwargs)
    except _COMMAND_ERRORS:
        return None
    if layer_weight:
        curves = animation.weight_curves(node)
        return curves[-1] if curves else None
    curves = _paste_curves_for_plug(
        plug,
        layer_context,
        layer_name=layer_name,
    )
    return curves[-1] if curves else None


def _curve_anchor_data(curve, time):
    try:
        values = cmds.keyframe(
            curve,
            query=True,
            time=(time, time),
            valueChange=True,
        ) or []
    except _COMMAND_ERRORS:
        values = []
    if values:
        snapshots = animation.key_tangent_snapshots(curve, [time])
        return float(values[0]), snapshots[0] if snapshots else {}, True
    try:
        values = cmds.keyframe(
            curve,
            query=True,
            time=(time, time),
            eval=True,
        ) or []
    except _COMMAND_ERRORS:
        values = []
    return (float(values[0]), {}, False) if values else (None, {}, False)


def _plug_value_at_time(plug, time):
    try:
        return float(cmds.getAttr(plug, time=time))
    except _COMMAND_ERRORS:
        return None


def _paste_entry_to_curve(
    curve,
    entry,
    anchor,
    source_start,
    relative=False,
    anchor_data=None,
):
    keys = entry.get("keys") or []
    if not keys:
        return False
    if anchor_data is None:
        anchor_data = _curve_anchor_data(curve, anchor)
    anchor_value, anchor_tangent, anchor_exists = anchor_data
    source_anchor_value = entry.get("source_anchor_value")
    if source_anchor_value is None:
        source_anchor_value = float(keys[0]["value"])
    if relative and anchor_value is None:
        return False
    value_offset = (
        float(anchor_value) - float(source_anchor_value)
        if relative
        else 0.0
    )

    changed = False
    weighted_applied = False
    for key in keys:
        destination_time = anchor + (float(key["time"]) - source_start)
        if (
            relative
            and anchor_exists
            and math.isclose(
                destination_time,
                anchor,
                rel_tol=0.0,
                abs_tol=1e-8,
            )
        ):
            continue
        value = float(key["value"]) + value_offset
        cmds.setKeyframe(curve, time=(destination_time,), value=value)
        tangent = key.get("tangent") or {}
        animation.apply_key_tangent_snapshot(
            curve,
            destination_time,
            tangent,
            apply_weighted=not weighted_applied,
        )
        weighted_applied = weighted_applied or "weightedTangents" in tangent
        changed = True

    if relative and anchor_exists:
        cmds.keyframe(
            curve,
            edit=True,
            time=(anchor, anchor),
            valueChange=anchor_value,
        )
        animation.apply_key_tangent_snapshot(
            curve,
            anchor,
            anchor_tangent,
        )
    return changed


def _paste_clipboard(relative=False):
    clipboard_data = _load_curve_clipboard()
    if not clipboard_data:
        return animation.notify_empty("keys", "paste")

    target_info = animation.resolve_context(
        default_mode="current_frame",
        include_channels=True,
        resolve_curves=True,
    )
    layer_context = target_info.layer_scope or {}
    mappings = _paste_target_mappings(target_info, clipboard_data)
    if not mappings:
        if not target_info.objects:
            return wutil.make_inViewMessage("Select an object")
        return animation.notify_empty("channels", "paste")
    uses_layer_destination = any(not spec.get("curve") for spec, _entry in mappings)
    if (
        uses_layer_destination
        and layer_context.get("selection_explicit")
        and not layer_context.get("selected_unlocked")
    ):
        return wutil.make_inViewMessage("Selected layer is locked")

    source_start = float(clipboard_data["start"])
    source_end = float(clipboard_data["end"])
    tint_start = min(spec["anchor"] for spec, _entry in mappings)
    tint_end = max(
        spec["anchor"] + (source_end - source_start)
        for spec, _entry in mappings
    )
    changed = False
    with _animation_command_context(
        "Paste Keys Relative" if relative else "Paste Keys",
        "paste_keys_relative" if relative else "paste_keys",
        timerange=(tint_start, tint_end),
    ):
        for spec, entry in mappings:
            keys = entry.get("keys") or []
            if not keys:
                continue
            anchor = float(spec["anchor"])
            targets = [spec["curve"]] if spec.get("curve") else []
            target_layer = spec.get("layer") or _paste_layer_for_entry(
                entry,
                layer_context,
            )
            if not targets and spec.get("plug"):
                targets = _paste_curves_for_plug(
                    spec["plug"],
                    layer_context,
                    layer_name=target_layer,
                )
            if not targets and spec.get("plug"):
                anchor_value = _plug_value_at_time(spec["plug"], anchor)
                source_anchor_value = entry.get("source_anchor_value")
                if source_anchor_value is None:
                    source_anchor_value = float(keys[0]["value"])
                value_offset = (
                    float(anchor_value) - float(source_anchor_value)
                    if relative and anchor_value is not None
                    else 0.0
                )
                first_key = keys[0]
                first_time = anchor + (
                    float(first_key["time"]) - source_start
                )
                first_value = float(first_key["value"]) + value_offset
                if relative:
                    if anchor_value is None:
                        continue
                curve = _create_paste_curve(
                    spec["plug"],
                    layer_context,
                    first_time,
                    first_value,
                    layer_name=target_layer,
                    layer_weight=bool(spec.get("layer_weight")),
                )
                targets = [curve] if curve else []
                if curve:
                    changed = _paste_entry_to_curve(
                        curve,
                        entry,
                        anchor,
                        source_start,
                        relative=relative,
                        anchor_data=(anchor_value, {}, False),
                    ) or changed
                    continue

            for curve in targets:
                changed = _paste_entry_to_curve(
                    curve,
                    entry,
                    anchor,
                    source_start,
                    relative=relative,
                ) or changed

    if not changed:
        return animation.notify_empty("keys", "paste")
    return True


def _navigation_key_context():
    target_info = animation.resolve_context(
        include_channels=True, include_shapes=True, resolve_curves=True
    )
    curves = target_info.curves
    time_context = target_info.time
    selected_range = (
        time_context.timerange
        if time_context is not None
        else None
    )
    return curves, selected_range


def _go_to_key(amount):
    if _nav_accumulate_pending_key_step(amount):
        return True
    curves, selected_range = _navigation_key_context()
    return _nav_request_curve_key_step(
        amount,
        curves,
        time_range=selected_range,
    )


def go_to_next_key(*args):
    return _go_to_key(1)


def go_to_previous_key(*args):
    return _go_to_key(-1)


def go_to_next_frame(*args):
    return _nav_request_frame_step(1)


def go_to_previous_frame(*args):
    return _nav_request_frame_step(-1)


def apply_smart_euler_filter(*args):
    target_info = animation.resolve_context(
        include_channels=True, include_shapes=True, resolve_curves=True
    )
    target_curves = target_info.curves
    if not _validate_curve_tool_targets(target_info, target_curves, "filter"):
        return None
    curves = []
    for curve in target_curves:
        if selection.is_rotation_anim_curve(curve):
            curves.append(curve)

    if not curves:
        return wutil.make_inViewMessage("No rotation to filter")

    with _animation_command_context(
        "Apply Smart Euler Filter",
        "apply_smart_euler_filter",
        progress_max=len(curves),
    ) as operation:
        return _apply_euler_filter(curves, target_info, operation)


def clear_animation_keys(*args):
    return _run_key_command(cmds.cutKey, "clear_animation", clear=True)


def copy_keys(*args):
    target_info = animation.resolve_context(
        include_channels=True, include_shapes=True, resolve_curves=True
    )
    curves = target_info.curves
    if not _validate_curve_tool_targets(
        target_info, curves, "copy", require_keys=True
    ):
        return None
    clipboard_data = _capture_curve_clipboard(target_info, curves)
    if not _save_curve_clipboard(clipboard_data):
        return animation.notify_empty("keys", "copy")
    tint_range = (clipboard_data["start"], clipboard_data["end"])
    with toolCommon.tool_operation(
        tool_id="copy_keys",
        label=toolCommon.humanize_tool_name("copy_keys"),
        progress=False,
        undo=False,
        tint="range",
        timerange=tint_range,
        preserve_time_selection=True,
    ):
        return True


def cut_keys(*args):
    target_info = animation.resolve_context(
        include_channels=True, include_shapes=True, resolve_curves=True
    )
    curves = target_info.curves
    if not _validate_curve_tool_targets(
        target_info, curves, "cut", require_keys=True
    ):
        return None
    clipboard_data = _capture_curve_clipboard(target_info, curves)
    if not _save_curve_clipboard(clipboard_data):
        return animation.notify_empty("keys", "cut")
    return _run_key_command(
        cmds.cutKey,
        "cut_keys",
        target_context=(target_info, curves),
        tint_range=(clipboard_data["start"], clipboard_data["end"]),
        validate=False,
        preserve_time_selection=True,
        clear=True,
    )


def delete_keys(*args):
    target_info = animation.resolve_context(
        default_mode="current_frame",
        include_channels=True,
        include_shapes=True,
        resolve_curves=True,
    )
    curves = target_info.curves
    time_context = target_info.time
    selected_range = (
        time_context.timerange
        if time_context and time_context.mode == "time_slider_range"
        else None
    )
    return _run_key_command(
        cmds.cutKey,
        "delete_keys",
        default_mode="current_frame",
        target_context=(target_info, curves),
        tint_range=selected_range,
        preserve_time_selection=True,
        clear=True,
    )


def paste_keys(*args):
    return _paste_clipboard(relative=False)


def paste_keys_relative(*args):
    return _paste_clipboard(relative=True)


def crop_animation(*args):
    target_info = animation.resolve_context(
        include_channels=True, include_shapes=True, resolve_curves=True
    )
    curves = target_info.curves
    if not _validate_curve_tool_targets(target_info, curves, "crop"):
        return None

    time_context = target_info.time
    crop_range = (time_context.start_frame, time_context.end_frame)
    clipboard_target_info = dict(target_info)
    clipboard_target_info.time = timeline.TimeContext(
        mode="time_slider_range",
        start_frame=crop_range[0],
        end_frame=crop_range[1],
    )
    clipboard_data = _capture_curve_clipboard(clipboard_target_info, curves)
    if not _save_curve_clipboard(clipboard_data):
        return animation.notify_empty("keys", "crop")

    with _animation_command_context(
        "Crop Animation", "crop_animation", timerange=crop_range
    ):
        for curve in curves:
            frames = cmds.keyframe(curve, query=True, timeChange=True) or []
            before = [frame for frame in frames if frame < crop_range[0]]
            after = [frame for frame in frames if frame > crop_range[1]]
            if before:
                cmds.cutKey(
                    curve,
                    time=(min(before), max(before)),
                    clear=True,
                )
            if after:
                cmds.cutKey(
                    curve,
                    time=(min(after), max(after)),
                    clear=True,
                )
        return True


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
        float(value) for value in target_info.key_times(curve)
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
    with animation.preserve_key_selection():
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
    with animation.preserve_key_selection():
        for curve in curves:
            if operation is not None and operation.cancelled:
                break
            keys = sorted(
                set(
                    float(value)
                    for value in target_info.key_times(curve)
                )
            )
            if len(keys) <= 2:
                if operation is not None:
                    operation.step()
                continue

            priority, scores = animation.detail_priority_with_scores(curve, keys)
            redundant = [
                frame
                for frame in reversed(priority)
                if scores.get(frame, 0.0) <= tolerance
            ]
            if redundant:
                redundant_set = set(redundant)
                kept = [frame for frame in keys if frame not in redundant_set]
                shape = animation.capture_curve_shape([curve], kept)
                for frame in sorted(redundant, reverse=True):
                    cmds.cutKey(curve, time=(frame, frame), clear=True)
                    removed_count += 1
                animation.apply_curve_shape(
                    shape,
                    set_values=False,
                    preserve_tangent_types=True,
                )
            if operation is not None:
                operation.step()
    return removed_count


def _redundant_key_targets():
    target_info = animation.resolve_context(
        include_channels=True, include_shapes=True, resolve_curves=True
    )
    curves = target_info.curves
    if not _validate_curve_tool_targets(target_info, curves, "clean"):
        return None, None, None

    time_context = target_info.time
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
    mode = get_remove_redundant_mode()
    remove_all = mode == REMOVE_REDUNDANT_MODE_ALL
    label = "Remove All Redundant Keys" if remove_all else "Remove Flat Redundant Keys"
    with _cleanup_command_context(
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
        animation.notify_empty("keys", "remove")
    return removed


def remove_static_anim_curves(*args):
    with _cleanup_command_context(
        "Remove Static Anim Curves",
        "remove_static_anim_curves",
    ) as operation:
        operation.start()
        target_info = animation.resolve_context(
            include_channels=True, include_shapes=True, resolve_curves=True
        )
        curves = target_info.curves
        if not _validate_curve_tool_targets(target_info, curves, "clean"):
            return None

        static_targets = {}
        operation.set_total(len(curves))
        for curve in curves:
            if operation.cancelled:
                return None
            key_data = target_info.key_data(curve)
            if not key_data:
                operation.step()
                continue
            values = [value for _time, value in key_data]
            if max(values) - min(values) <= 1e-8:
                key_times = tuple(time for time, _value in key_data)
                static_targets.setdefault(key_times, []).append(curve)
            operation.step()

        if not static_targets:
            return wutil.make_inViewMessage("No static animation")

        time_context = target_info.time
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
            return wutil.make_inViewMessage("Could not remove static animation")
        return True


def reverse_animation(*args):
    target_info = animation.resolve_context(
        include_channels=True, include_shapes=True, resolve_curves=True
    )
    curves = target_info.curves
    if not _validate_curve_tool_targets(
        target_info,
        curves,
        "reverse",
        require_keys=True,
    ):
        return None

    time_context = target_info.time
    reverse_range = (time_context.start_frame, time_context.end_frame)
    if time_context.mode == "all_animation":
        key_times = [
            frame
            for curve in curves
            for frame in target_info.key_times(curve)
        ]
        if not key_times:
            return animation.notify_empty("keys", "reverse")
        reverse_range = (min(key_times), max(key_times))
    with _animation_command_context(
        "Reverse Animation",
        "reverse_animation",
        timerange=reverse_range,
        progress_max=len(curves),
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
    destinations = selection.get_anim_curve_output_plugs([curve])
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


def _curve_tangent_at_frame(curve, frame):
    source_time = frame
    try:
        key_exists = bool(cmds.keyframe(curve, query=True, time=(frame, frame)))
    except (RuntimeError, ValueError, TypeError, AttributeError, KeyError, IndexError):
        key_exists = False
    if not key_exists:
        source_time = _nearest_curve_key_time(curve, frame)
    if source_time is None:
        return {}
    snapshots = animation.key_tangent_snapshots(curve, [source_time])
    return snapshots[0] if snapshots else {}


def _set_key_on_curve_preserving_tangent(curve, frame):
    value = _curve_value_at_frame(curve, frame)
    if value is None:
        return False

    tangent = _curve_tangent_at_frame(curve, frame)
    cmds.setKeyframe(curve, time=(frame,), value=value)
    animation.apply_key_tangent_snapshot(curve, frame, tangent)
    return True


def _set_selected_graph_editor_curves_current_time(curves, operation=None):
    curves = _unique(curves)
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


def _key_attributes_layer_aware(
    obj,
    attributes,
    frame,
    layer_context=None,
    operation=None,
    scene_layers=None,
):
    """Key ``attributes`` on ``obj`` at ``frame`` through the one shared
    animation-layer destination route (see ``animation.layer_graph``).

    An attribute that already has a curve on the resolved destination layer
    keeps its existing tangent shape; one that doesn't gets a fresh key,
    added to that layer the same way every other layer-aware tool in TKM
    does it. This is the single path both Smart Key and Smart Key All
    Channels use to actually set a key, so they behave identically.

    Returns ``(keyed_attrs, blocked_attrs)``.
    """
    if not attributes:
        return [], []
    layer_context = layer_context or animation.layer_cache.capture()
    groups, blocked = layer_context.group_by_destination(obj, attributes)
    keyed_attrs = []
    if operation is not None and blocked:
        operation.step(len(blocked))
    for layer_name, grouped_attributes in groups.items():
        for attr in grouped_attributes:
            if operation is not None and operation.cancelled:
                return keyed_attrs, blocked
            plug = "{}.{}".format(obj, attr)
            try:
                curve = animation.layer_graph.curve_for_plug(
                    plug,
                    layer_name=layer_name,
                    scene_layers=scene_layers,
                )
                if curve and _set_key_on_curve_preserving_tangent(curve, frame):
                    keyed_attrs.append(attr)
                    continue
                key_kwargs = {
                    "attribute": attr,
                    "time": (frame,),
                    "shape": False,
                }
                if layer_name:
                    key_kwargs["animLayer"] = layer_name
                try:
                    if cmds.setKeyframe(obj, **key_kwargs):
                        keyed_attrs.append(attr)
                except (RuntimeError, ValueError, TypeError):
                    pass
            finally:
                if operation is not None:
                    operation.step()
    return keyed_attrs, blocked


def set_smart_key(*args):
    target_info = animation.resolve_context(
        default_mode="current_frame",
        include_channels=True,
    )
    target_plugs = target_info.plugs
    selected_objects = target_info.objects
    selected_channels = target_info.channels

    selected_objects = _unique(selected_objects)
    target_plugs = _unique(target_plugs)

    frames = _frames_for_smart_key(target_info.time)
    source = target_info.source
    has_graph_keys = bool(target_info.has_graph_keys)

    layer_scope = target_info.layer_scope or animation.layer_cache.tool_context()
    layer_context = layer_scope["context"]
    scene_layers = layer_scope["scene_layers"]

    with _animation_command_context(
        "Set Smart Key",
        tint=False,
        progress_max=0,
        preserve_time_selection=True,
    ) as operation:
        keyed = (
            _set_selected_graph_editor_curves_current_time(
                target_info.curves,
                operation,
            )
            if has_graph_keys
            else False
        )

        if not keyed and _is_explicit_channel_source(source) and target_plugs:
            if source == "channel_box":
                operation.set_total(
                    len(target_plugs) * len(frames), reset=has_graph_keys
                ).set_status(
                    "Setting Smart Keys"
                )
                for plug in target_plugs:
                    if operation.cancelled:
                        break
                    if not plug or "." not in plug:
                        operation.step(len(frames))
                        continue

                    node, attr = plug.rsplit(".", 1)

                    for frame in frames:
                        keyed_attrs, _blocked = _key_attributes_layer_aware(
                            node,
                            [attr],
                            frame,
                            layer_context,
                            operation=operation,
                            scene_layers=scene_layers,
                        )
                        keyed = keyed or bool(keyed_attrs)
            else:
                curves = target_info.curves
                curve_frames = frames
                if source in (
                    "graph_editor",
                    "graph_editor_outliner",
                ) and not target_info.selected_keys:
                    curve_frames = (cmds.currentTime(query=True),)
                operation.set_total(
                    len(curves) * len(curve_frames), reset=has_graph_keys
                ).set_status("Setting Smart Keys")

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
                return wutil.make_inViewMessage("Select an object")

            object_work = []
            for obj in selected_objects:
                attrs = selection.get_keyable_scalar_attributes(obj)
                if not attrs:
                    continue

                valid_attrs = _filter_settable_keyable_attrs(obj, attrs)
                if not valid_attrs:
                    continue

                # "Smart" means: touch only channels already animated
                # somewhere (any layer, not just BaseAnimation) if the
                # object has any; otherwise key everything so the object
                # can start being animated.
                animated_attrs = [
                    attr for attr in valid_attrs
                    if animation.layer_graph.curves_by_layer(
                        "{}.{}".format(obj, attr),
                        scene_layers=scene_layers,
                    )
                ]
                target_attrs = animated_attrs or valid_attrs
                object_work.append((obj, target_attrs))

            operation.set_total(
                sum(len(target_attrs) * len(frames) for _obj, target_attrs in object_work),
                reset=has_graph_keys,
            ).set_status("Setting Smart Keys")

            for obj, target_attrs in object_work:
                for frame in frames:
                    if operation.cancelled:
                        break
                    keyed_attrs, _blocked = _key_attributes_layer_aware(
                        obj,
                        target_attrs,
                        frame,
                        layer_context,
                        operation=operation,
                        scene_layers=scene_layers,
                    )
                    keyed = keyed or bool(keyed_attrs)
                if operation.cancelled:
                    break

        if not keyed:
            return animation.notify_empty("channels", "key")


def set_smart_key_all_channels(*args):
    target_info = animation.resolve_context(
        default_mode="current_frame",
        include_channels=True,
        include_graph=True,
    )
    selected_objects = target_info.objects
    target_plugs = target_info.plugs
    source = target_info.source

    selected_objects = _unique(selected_objects)

    frames = _frames_for_smart_key(target_info.time)
    layer_scope = target_info.layer_scope or animation.layer_cache.tool_context()
    layer_context = layer_scope["context"]
    scene_layers = layer_scope["scene_layers"]

    with _animation_command_context(
        "Set Smart Key All Channels",
        tint=False,
        progress_max=0,
        preserve_time_selection=True,
    ) as operation:
        if not selected_objects:
            return wutil.make_inViewMessage("Select an object")

        keyed = False
        object_work = []
        explicit_attrs = {}
        if source == "channel_box":
            for plug in target_plugs:
                if plug and "." in plug:
                    obj, attr = plug.rsplit(".", 1)
                    explicit_attrs.setdefault(obj, []).append(attr)

        work_objects = (
            list(explicit_attrs)
            if source == "channel_box"
            else selected_objects
        )
        for obj in work_objects:
            attrs = (
                _unique(explicit_attrs.get(obj) or [])
                if source == "channel_box"
                else selection.get_keyable_scalar_attributes(obj)
            )
            if not attrs:
                continue

            valid_attrs = _filter_settable_keyable_attrs(obj, attrs)
            if not valid_attrs:
                continue
            object_work.append((obj, valid_attrs))

        operation.set_total(
            sum(len(valid_attrs) * len(frames) for _obj, valid_attrs in object_work)
        ).set_status("Setting All Smart Keys")

        for obj, valid_attrs in object_work:
            for frame in frames:
                if operation.cancelled:
                    break
                keyed_attrs, _blocked = _key_attributes_layer_aware(
                    obj,
                    valid_attrs,
                    frame,
                    layer_context,
                    operation=operation,
                    scene_layers=scene_layers,
                )
                keyed = keyed or bool(keyed_attrs)
            if operation.cancelled:
                break

        if not keyed:
            return animation.notify_empty("channels", "key")


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
    value = maya_api.evaluate_anim_curve(curve_fn, time)
    if value is not None:
        return maya_api.anim_curve_value_to_attr_value(curve, value)
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


def _curve_tool_has_keys(curves, target_info):
    return any(
        target_info.key_times(curve)
        for curve in curves or []
    )


def _validate_curve_tool_targets(
    target_info,
    curves,
    action,
    require_keys=False,
):
    if (
        not target_info.objects
        and target_info.source != "graph_editor"
    ):
        wutil.make_inViewMessage("Select an object")
        return False
    layer_context = target_info.layer_scope or {}
    if (
        layer_context.get("selection_explicit")
        and not layer_context.get("selected_unlocked")
    ):
        wutil.make_inViewMessage("Selected layer is locked")
        return False
    if not curves:
        animation.notify_empty("animation", action)
        return False
    if require_keys and not _curve_tool_has_keys(curves, target_info):
        animation.notify_empty("keys", action)
        return False
    return True


def snap_keyframes():
    target_info = animation.resolve_context(
        include_channels=True, include_shapes=True, resolve_curves=True
    )
    curves = target_info.curves
    if not _validate_curve_tool_targets(target_info, curves, "snap"):
        return None

    curve_key_times = []
    for curve in curves:
        target_times = target_info.key_times(curve)
        try:
            curve_times = cmds.keyframe(
                curve,
                query=True,
                timeChange=True,
            ) or []
        except _COMMAND_ERRORS:
            curve_times = []
        buckets = {}
        for key_time in target_times:
            rounded_time = _nearest_whole_frame(key_time)
            if math.isclose(
                float(rounded_time),
                float(key_time),
                rel_tol=0.0,
                abs_tol=1e-8,
            ):
                continue
            buckets.setdefault(rounded_time, []).append(key_time)

        if not buckets:
            continue

        curve_fn = maya_api.anim_curve_fn(curve)
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
        return animation.notify_empty("keys", "snap")

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
        return animation.notify_empty("keys", "snap")
