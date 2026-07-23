"""Copy/paste pose and animation behavior."""

from contextlib import contextmanager
import re

from maya import cmds

from TheKeyMachine.core import animation_context
from TheKeyMachine.core import animlayers
from TheKeyMachine.core import toolbox
from TheKeyMachine.data import icons
import TheKeyMachine.mods.selectionMod as selectionMod
from TheKeyMachine.tools import clipboard
from TheKeyMachine.tools import common as toolCommon
import TheKeyMachine.widgets.customDialogs as customDialogs
import TheKeyMachine.widgets.customWidgets as customWidgets
import TheKeyMachine.widgets.timeline as timelineWidgets
import TheKeyMachine.widgets.util as wutil


def _begin_timeline_tint(timerange, key, owner=None, color=None):
    return timelineWidgets.begin_timeline_tint(
        timerange=timerange,
        color=color or toolbox.get_tool_tint_color(key),
        owner=owner,
        key=key,
    )


# ______________________________________________________COPY PASTE ANIMATION ______________________________________________________________________________#


ANIMATION_SCHEMA_VERSION = 4
ANIMATION_CONTROLS_KEY = "controls"
ANIMATION_META_KEY = "meta"
ANIMATION_FRAME_KEY = "k"
ANIMATION_VALUE_KEY = "v"
ANIMATION_STATIC_VALUE_KEY = "sv"
ANIMATION_TANGENT_KEY = "t"
ANIMATION_LAYERS_KEY = "ly"
ANIMATION_LAYER_WEIGHT_KEY = "w"
ANIMATION_LAYER_META_KEY = "layers"
TANGENT_KEYS = {
    "itt": "inTangentType",
    "ott": "outTangentType",
    "ia": "inAngle",
    "oa": "outAngle",
    "iw": "inWeight",
    "ow": "outWeight",
    "wt": "weightedTangents",
}


def _is_animation_payload(data):
    return isinstance(data, dict) and isinstance(data.get(ANIMATION_CONTROLS_KEY), dict)


def _animation_controls(animation_data):
    return (animation_data or {}).get(ANIMATION_CONTROLS_KEY) or {}


def _copy_paste_targets(saved_data, selected_objects):
    if selected_objects:
        return selected_objects
    data = _animation_controls(saved_data) if _is_animation_payload(saved_data) else (saved_data or {})
    return [control for control in data.keys() if cmds.objExists(control)]


def _animation_layer_items(channel_data):
    layers = channel_data.get(ANIMATION_LAYERS_KEY) or []
    if isinstance(layers, dict):
        return [
            (
                layer_id,
                (entry.get("data") or entry),
                entry.get(ANIMATION_LAYER_WEIGHT_KEY) or entry.get("weight") or {},
            )
            for layer_id, entry in layers.items()
            if isinstance(entry, dict)
        ]
    items = []
    for entry in layers:
        if isinstance(entry, dict):
            items.append((entry.get("layer"), entry.get("data") or {}, entry.get("weight") or {}))
    return items


def _animation_data_key_count(animation_data, targets=None):
    count = 0
    controls = _animation_controls(animation_data)
    target_names = set(targets or controls.keys())
    for control, channels in controls.items():
        if control not in target_names:
            continue
        for anim_data in (channels or {}).values():
            count += len(anim_data.get(ANIMATION_FRAME_KEY) or [])
            for _layer_name, layer_data, weight_data in _animation_layer_items(anim_data):
                count += len(layer_data.get(ANIMATION_FRAME_KEY) or [])
                count += len(weight_data.get(ANIMATION_FRAME_KEY) or [])
    for metadata in (
        ((animation_data or {}).get(ANIMATION_META_KEY) or {})
        .get(ANIMATION_LAYER_META_KEY, {})
        .values()
    ):
        count += len((metadata.get("weight") or {}).get(ANIMATION_FRAME_KEY) or [])
    return count


def _animation_data_apply_count(animation_data, targets=None):
    count = _animation_data_key_count(animation_data, targets=targets)
    controls = _animation_controls(animation_data)
    target_names = set(targets or controls.keys())
    for control, channels in controls.items():
        if control not in target_names:
            continue
        for anim_data in (channels or {}).values():
            if ANIMATION_STATIC_VALUE_KEY in (anim_data or {}):
                count += 1
    return count


def _time_context_tint_range(time_context):
    if not time_context:
        return None
    if time_context.mode in ("graph_editor_keys", "time_slider_range"):
        return time_context.timerange
    if time_context.mode == "all_animation":
        return timelineWidgets.get_playback_range()
    return time_context.timerange


def _shift_timerange(timerange, offset):
    if not timerange:
        return None
    return (timerange[0] + offset, timerange[1] + offset)


def _animation_data_timerange(animation_data):
    meta_range = ((animation_data or {}).get(ANIMATION_META_KEY) or {}).get("range")
    if meta_range and len(meta_range) >= 2:
        return meta_range[0], meta_range[1]
    frames = []
    for channels in _animation_controls(animation_data).values():
        for anim_data in (channels or {}).values():
            frames.extend(anim_data.get(ANIMATION_FRAME_KEY) or [])
            for _layer_name, layer_data, weight_data in _animation_layer_items(anim_data):
                frames.extend(layer_data.get(ANIMATION_FRAME_KEY) or [])
                frames.extend(weight_data.get(ANIMATION_FRAME_KEY) or [])
    for metadata in (
        ((animation_data or {}).get(ANIMATION_META_KEY) or {})
        .get(ANIMATION_LAYER_META_KEY, {})
        .values()
    ):
        frames.extend((metadata.get("weight") or {}).get(ANIMATION_FRAME_KEY) or [])
    return timelineWidgets.get_frames_timerange(frames)


def _query_anim_channel_data(source, time_context):
    if time_context.mode == "graph_editor_keys":
        keyframes = cmds.keyframe(source, query=True, selected=True, timeChange=True)
        values = cmds.keyframe(source, query=True, selected=True, valueChange=True)
    elif time_context.mode == "time_slider_range":
        keyframes = cmds.keyframe(source, query=True, time=(time_context.start_frame, time_context.end_frame))
        values = cmds.keyframe(source, query=True, vc=True, time=(time_context.start_frame, time_context.end_frame))
    else:
        keyframes = cmds.keyframe(source, query=True)
        values = cmds.keyframe(source, query=True, vc=True)

    keyframes = keyframes or []
    values = values or []
    return {
        ANIMATION_FRAME_KEY: keyframes,
        ANIMATION_VALUE_KEY: values,
        ANIMATION_TANGENT_KEY: _query_key_tangent_data(source, keyframes),
    }


def _query_static_channel_value(plug):
    try:
        value = cmds.getAttr(plug)
    except Exception:
        return {}
    return {ANIMATION_STATIC_VALUE_KEY: value}


def _query_layered_anim_channel_data(
    plug,
    time_context,
    layer_context=None,
    selected_curves=None,
):
    layer_context = layer_context or animlayers.capture_context()
    try:
        layer_entries = animlayers.get_anim_curves_by_layer_for_plug(plug)
    except Exception:
        layer_entries = []

    if not layer_entries:
        return _query_anim_channel_data(plug, time_context)

    allowed_layer_ids = set(layer_context.get("copy_layer_ids") or [])
    selected_curves = set(selected_curves or [])
    layer_data = {}
    for entry in layer_entries:
        curve = entry.get("curve")
        if not curve:
            continue
        layer_name = entry.get("layer")
        layer_id = animlayers.layer_id_for_name(layer_name)
        if allowed_layer_ids and layer_id not in allowed_layer_ids:
            continue
        if time_context.mode == "graph_editor_keys" and selected_curves and curve not in selected_curves:
            continue
        data = _query_anim_channel_data(curve, time_context)
        if not data.get(ANIMATION_FRAME_KEY):
            continue
        layer_data[layer_id] = {
            "data": data,
        }
    return {ANIMATION_LAYERS_KEY: layer_data} if layer_data else {}


def _query_anim_layer_weight_data(layer_name, time_context):
    if not layer_name:
        return {}
    weight_plug = "{}.weight".format(layer_name)
    if not cmds.objExists(weight_plug):
        return {}
    if time_context.mode == "graph_editor_keys":
        keyframes = cmds.keyframe(
            weight_plug,
            query=True,
            time=(time_context.start_frame, time_context.end_frame),
            timeChange=True,
        ) or []
        values = cmds.keyframe(
            weight_plug,
            query=True,
            time=(time_context.start_frame, time_context.end_frame),
            valueChange=True,
        ) or []
        data = {
            ANIMATION_FRAME_KEY: keyframes,
            ANIMATION_VALUE_KEY: values,
            ANIMATION_TANGENT_KEY: _query_key_tangent_data(
                weight_plug, keyframes
            ),
        }
    else:
        data = _query_anim_channel_data(weight_plug, time_context)
    return data if data else {}


def _apply_anim_layer_weight_data(
    layer_name,
    weight_data,
    progress=None,
    insert_time=None,
    time_shift=None,
):
    if not layer_name or not weight_data:
        return 0
    applied = 0
    try:
        layer_plug = "{}.weight".format(layer_name)
        if not cmds.objExists(layer_plug):
            return 0
        keyframes = weight_data.get(ANIMATION_FRAME_KEY) or []
        values = weight_data.get(ANIMATION_VALUE_KEY) or []
        if not keyframes or not values:
            return 0
        weight_time_shift = time_shift
        if weight_time_shift is None:
            weight_time_shift = (
                insert_time - keyframes[0] if insert_time is not None else 0
            )
        tangent_data = weight_data.get(ANIMATION_TANGENT_KEY) or {}
        _apply_channel_weighted_tangents(
            layer_name, "weight", tangent_data
        )
        for key_index, (key_time, value) in enumerate(zip(keyframes, values)):
            try:
                pasted_time = key_time + weight_time_shift
                cmds.setKeyframe(
                    layer_name,
                    time=(pasted_time,),
                    attribute="weight",
                    value=value,
                )
                _apply_key_tangent_data(
                    layer_name,
                    "weight",
                    pasted_time,
                    tangent_data,
                    key_index,
                )
                applied += 1
            except Exception:
                pass
            if progress and progress.step():
                return applied
    except Exception:
        return 0
    return applied


def _transform_channel_values(channel_data, transform_value):
    transformed = dict(channel_data or {})
    transformed[ANIMATION_VALUE_KEY] = [transform_value(v) for v in channel_data.get(ANIMATION_VALUE_KEY) or []]
    layers = []
    for layer_name, layer_data, weight_data in _animation_layer_items(channel_data):
        layer_entry = {"layer": layer_name, "data": _transform_channel_values(layer_data, transform_value)}
        if weight_data:
            layer_entry["weight"] = dict(weight_data)
        layers.append(layer_entry)
    if layers:
        transformed[ANIMATION_LAYERS_KEY] = layers
    return transformed


def _maybe_apply_paste_range(paste_range, anchor_widget=None):
    if not paste_range:
        return
    try:
        start_frame, end_frame = int(paste_range[0]), int(paste_range[1])
        current_range = (
            int(cmds.playbackOptions(query=True, minTime=True)),
            int(cmds.playbackOptions(query=True, maxTime=True)),
        )
    except Exception:
        return
    if current_range == (start_frame, end_frame):
        return

    apply_button = customDialogs.QFlatConfirmDialog.CustomButton("Apply Range", positive=True, icon=icons.apply)
    no_button = customDialogs.QFlatConfirmDialog.CustomButton("No", positive=False, icon=icons.cancel)
    clicked = customDialogs.QFlatTooltipConfirm.question(
        anchor_widget or wutil.get_maya_qt(),
        title="Apply paste range?",
        message="Set the timeline range to {} - {} from the copied data?".format(start_frame, end_frame),
        buttons=[apply_button, no_button],
        icon=icons.paste_animation,
        highlight=apply_button,
    )
    if clicked and clicked.get("positive"):
        cmds.playbackOptions(
            minTime=start_frame,
            maxTime=end_frame,
            animationStartTime=start_frame,
            animationEndTime=end_frame,
        )


def _refresh_animation_view():
    try:
        current_time = cmds.currentTime(query=True)
        cmds.currentTime(current_time, edit=True)
    except Exception:
        pass
    try:
        cmds.dgdirty(allPlugs=True)
    except Exception:
        pass
    try:
        cmds.refresh(force=True)
    except Exception:
        pass


def _query_key_tangent_data(plug, keyframes):
    tangent_data = {short_key: [] for short_key in TANGENT_KEYS}

    # Most animation copies contain a contiguous curve/range. Query every
    # tangent property once for that range instead of once per property/key.
    if keyframes:
        time_range = (min(keyframes), max(keyframes))
        try:
            range_frames = cmds.keyframe(plug, query=True, time=time_range) or []
        except Exception:
            range_frames = []
        if len(range_frames) == len(keyframes) and all(
            abs(float(a) - float(b)) <= 0.000001 for a, b in zip(range_frames, keyframes)
        ):
            for short_key, query_key in TANGENT_KEYS.items():
                if short_key == "wt":
                    continue
                try:
                    values = cmds.keyTangent(plug, query=True, time=time_range, **{query_key: True}) or []
                except Exception:
                    values = []
                tangent_data[short_key] = list(values[:len(keyframes)])
                if len(tangent_data[short_key]) < len(keyframes):
                    tangent_data[short_key].extend([None] * (len(keyframes) - len(tangent_data[short_key])))
            try:
                weighted_values = cmds.keyTangent(plug, query=True, weightedTangents=True) or []
                weighted = bool(weighted_values[0] if isinstance(weighted_values, list) else weighted_values)
            except Exception:
                weighted = None
            tangent_data["wt"] = [weighted] * len(keyframes)
            return tangent_data

    # Sparse graph-editor selections need exact per-key queries.
    for frame in keyframes or []:
        time_arg = (frame, frame)
        for short_key, query_key in TANGENT_KEYS.items():
            if short_key == "wt":
                continue
            try:
                values = cmds.keyTangent(plug, query=True, time=time_arg, **{query_key: True}) or []
                tangent_data[short_key].append(values[0] if values else None)
            except Exception:
                tangent_data[short_key].append(None)
        try:
            weighted = cmds.keyTangent(plug, query=True, weightedTangents=True)
            tangent_data["wt"].append(bool(weighted[0] if isinstance(weighted, list) else weighted))
        except Exception:
            tangent_data["wt"].append(None)
    return tangent_data


def _apply_key_tangent_data(target, channel, key_time, tangent_data, index, layer_name=None):
    if not tangent_data:
        return

    def _value(name):
        values = tangent_data.get(name) or []
        return values[index] if index < len(values) else None

    def _edit_tangent(**kwargs):
        if not kwargs:
            return
        try:
            if layer_name:
                kwargs["animLayer"] = layer_name
            cmds.keyTangent(target, attribute=channel, time=(key_time,), edit=True, **kwargs)
        except Exception as e:
            import TheKeyMachine.mods.reportMod as report

            report.report_detected_exception(e, context="paste animation tangent data")

    in_type = _value("itt")
    out_type = _value("ott")
    type_kwargs = {}
    if in_type is not None:
        type_kwargs["inTangentType"] = in_type
    if out_type is not None:
        type_kwargs["outTangentType"] = out_type

    detail_kwargs = {}
    if in_type not in ("auto", "autoease", "autoEase", "autoMix"):
        in_angle = _value("ia")
        in_weight = _value("iw")
        if in_angle is not None:
            detail_kwargs["inAngle"] = in_angle
        if in_weight is not None:
            detail_kwargs["inWeight"] = in_weight
    if out_type not in ("auto", "autoease", "autoEase", "autoMix"):
        out_angle = _value("oa")
        out_weight = _value("ow")
        if out_angle is not None:
            detail_kwargs["outAngle"] = out_angle
        if out_weight is not None:
            detail_kwargs["outWeight"] = out_weight

    _edit_tangent(**type_kwargs)
    _edit_tangent(**detail_kwargs)
    if detail_kwargs:
        _edit_tangent(**type_kwargs)


def _apply_channel_weighted_tangents(target, channel, tangent_data, layer_name=None):
    weighted_values = (tangent_data or {}).get("wt") or []
    weighted = next((value for value in weighted_values if value is not None), None)
    if weighted is None:
        return
    try:
        kwargs = {"weightedTangents": bool(weighted)}
        if layer_name:
            kwargs["animLayer"] = layer_name
        cmds.keyTangent(target, attribute=channel, edit=True, **kwargs)
    except Exception:
        pass


def _attr_exists_and_settable(node, attr):
    full_attr = f"{node}.{attr}"
    try:
        return bool(cmds.getAttr(full_attr, settable=True))
    except Exception:
        return False


def _set_attr_value(plug, value):
    if isinstance(value, list):
        if len(value) == 1 and isinstance(value[0], (list, tuple)):
            cmds.setAttr(plug, *value[0])
        else:
            cmds.setAttr(plug, *value)
    else:
        cmds.setAttr(plug, value)


@contextmanager
def _copy_paste_operation(
    tool_id,
    success_message,
    undo=False,
    tint="none",
    default_mode="current_frame",
    timerange=None,
    progress=False,
    progress_max=0,
):
    state = {"success": False, "timerange": None, "operation": None}
    tint_session = None
    operation_tint = "none"
    operation_timerange = None
    if tint == "range" and timerange:
        operation_tint = "range"
        operation_timerange = timerange
    elif tint == "current":
        operation_tint = "current"
    try:
        with toolCommon.tool_operation(
            tool_id=tool_id,
            label=success_message,
            progress=progress,
            progress_max=progress_max,
            undo=undo,
            undo_name=toolCommon.make_undo_chunk_name(tool_id=tool_id),
            tint=operation_tint,
            timerange=operation_timerange,
            default_mode=default_mode,
            tint_key=tool_id,
        ) as operation:
            state["operation"] = operation
            yield state

        if state.get("success"):
            if tint == "range" and state.get("timerange") and operation_tint == "none" and not tint_session:
                tint_session = _begin_timeline_tint(state["timerange"], tool_id)
            wutil.make_inViewMessage(success_message)
    finally:
        if tint_session:
            tint_session.finish()


def _apply_animation_channels_to_targets(
    targets,
    channels_data,
    replace=False,
    insert_time=None,
    time_shift=None,
    replace_range=(0, 10000),
    progress=None,
    layer_metadata=None,
    layer_scope=None,
):
    keys_set = 0
    attr_settable_cache = {}
    progress_batch_size = 25
    destination_context = animlayers.capture_context()
    copied_layers = layer_metadata or {}
    created_layers = {}
    applied_weights = set()
    blocked_layers = set()

    def _source_entries(channel_data):
        entries = []
        if channel_data.get(ANIMATION_FRAME_KEY):
            entries.append((animlayers.BASE_LAYER_ID, channel_data, {}))
        for layer_id, data, weight_data in _animation_layer_items(channel_data):
            if not weight_data:
                weight_data = _layer_meta(layer_id).get("weight") or {}
            entries.append((layer_id, data, weight_data))
        return entries

    def _layer_meta(layer_id):
        metadata = dict(copied_layers.get(layer_id) or {})
        if layer_id == animlayers.BASE_LAYER_ID:
            metadata.setdefault("root", True)
            metadata.setdefault("name", destination_context.get("root_name"))
        else:
            metadata.setdefault("root", False)
            metadata.setdefault("name", layer_id)
        return metadata

    def _ensure_source_layer(layer_id, target, channel):
        if layer_id in (None, animlayers.BASE_LAYER_ID):
            return None
        metadata = _layer_meta(layer_id)
        layer_name = metadata.get("name") or layer_id
        existing = layer_name in animlayers.scene_layer_names(include_root=False)
        if existing:
            existing_meta = animlayers.layer_metadata(layer_name)
            if existing_meta.get("locked"):
                blocked_layers.add(layer_name)
                return False
        else:
            layer_name = animlayers.create_layer(metadata)
            if not layer_name:
                return False
            created_layers[layer_name] = metadata
        if not animlayers.layer_contains_plug(layer_name, "{}.{}".format(target, channel)):
            if not animlayers.add_plug_to_layer(
                layer_name, "{}.{}".format(target, channel)
            ):
                return False
        return layer_name

    def _destination_entries(target, channel, channel_data):
        source_entries = _source_entries(channel_data)
        if not source_entries:
            return []

        non_base = [
            layer_id
            for layer_id, _data, _weight in source_entries
            if layer_id != animlayers.BASE_LAYER_ID
        ]
        recreate_stack = bool(non_base and not destination_context.get("has_layers"))
        plug = "{}.{}".format(target, channel)
        if destination_context.get("selection_explicit") and not recreate_stack:
            destination = animlayers.selected_destination_for_plug(
                plug, context=destination_context
            )
            if destination.get("blocked"):
                blocked_name = (
                    destination.get("layer")
                    or destination_context.get("root_name")
                )
                blocked_layers.add(blocked_name or "BaseAnimation")
                return []
            destination_id = destination.get("layer_id")
            matching = [
                entry for entry in source_entries if entry[0] == destination_id
            ]
            if not matching and len(source_entries) == 1:
                matching = source_entries
            if not matching and destination_id == animlayers.BASE_LAYER_ID:
                matching = [
                    entry
                    for entry in source_entries
                    if entry[0] == animlayers.BASE_LAYER_ID
                ]
            if not matching:
                return []
            _source_id, data, _weight_data = matching[0]
            return [(destination.get("layer"), data, {})]

        preserve_stack = (
            recreate_stack
            or layer_scope in (None, "all")
            or len(source_entries) > 1
        )
        if preserve_stack:
            resolved = []
            for layer_id, data, weight_data in source_entries:
                layer_name = _ensure_source_layer(layer_id, target, channel)
                if layer_name is False:
                    continue
                resolved.append((layer_name, data, weight_data))
            return resolved

        destination = animlayers.selected_destination_for_plug(
            plug, context=destination_context
        )
        if destination.get("blocked"):
            blocked_name = destination.get("layer") or destination_context.get("root_name")
            blocked_layers.add(blocked_name or "BaseAnimation")
            return []
        _source_id, data, _weight_data = source_entries[0]
        return [(destination.get("layer"), data, {})]

    def _cut_destination_keys(target, channel, layer_name, timerange):
        try:
            if animlayers.has_anim_layers():
                curve = animlayers.get_anim_curve_for_plug(
                    "{}.{}".format(target, channel),
                    layer_name=layer_name,
                )
                if curve:
                    cmds.cutKey(curve, time=timerange, option="keys")
                return
            cmds.cutKey(
                target,
                time=timerange,
                attribute=channel,
                option="keys",
            )
        except Exception:
            pass

    def _apply_channel_data(target, channel, channel_data, layer_name=None):
        applied = 0
        pending_progress = 0
        keyframes = channel_data.get(ANIMATION_FRAME_KEY) or []
        values = channel_data.get(ANIMATION_VALUE_KEY) or []
        if not keyframes or not values:
            return applied

        paste_layer = layer_name
        channel_time_shift = time_shift
        if channel_time_shift is None:
            channel_time_shift = insert_time - keyframes[0] if insert_time is not None else 0
        tangent_data = channel_data.get(ANIMATION_TANGENT_KEY) or {}
        _apply_channel_weighted_tangents(target, channel, tangent_data, layer_name=paste_layer)
        for key_index, (frame, value) in enumerate(zip(keyframes, values)):
            try:
                key_time = frame + channel_time_shift
                key_kwargs = {"time": (key_time,), "attribute": channel, "value": value}
                if paste_layer:
                    key_kwargs["animLayer"] = paste_layer
                cmds.setKeyframe(target, **key_kwargs)
                _apply_key_tangent_data(target, channel, key_time, tangent_data, key_index, layer_name=paste_layer)
                applied += 1
            except Exception as e:
                import TheKeyMachine.mods.reportMod as report

                report.report_detected_exception(e, context="paste animation set key")
            pending_progress += 1
            if progress and pending_progress >= progress_batch_size:
                if progress.step(amount=pending_progress):
                    return applied
                pending_progress = 0
        if progress and pending_progress:
            progress.step(amount=pending_progress)
        return applied

    with toolCommon.suspend_maya_refresh():
        for target in targets or []:
            for channel, anim_data in (channels_data or {}).items():
                if progress and progress.cancelled:
                    break
                cache_key = (target, channel)
                if cache_key not in attr_settable_cache:
                    attr_settable_cache[cache_key] = _attr_exists_and_settable(target, channel)
                if not attr_settable_cache[cache_key]:
                    continue

                if ANIMATION_STATIC_VALUE_KEY in (anim_data or {}):
                    destination = animlayers.selected_destination_for_plug(
                        "{}.{}".format(target, channel),
                        context=destination_context,
                    )
                    if destination.get("blocked"):
                        blocked_layers.add(
                            destination.get("layer")
                            or destination_context.get("root_name")
                            or "BaseAnimation"
                        )
                        continue
                    try:
                        value = anim_data.get(ANIMATION_STATIC_VALUE_KEY)
                        if destination.get("layer"):
                            static_time = (
                                insert_time
                                if insert_time is not None
                                else cmds.currentTime(query=True)
                            )
                            cmds.setKeyframe(
                                target,
                                attribute=channel,
                                time=(static_time,),
                                value=value,
                                animLayer=destination["layer"],
                            )
                        else:
                            _set_attr_value(f"{target}.{channel}", value)
                        keys_set += 1
                    except Exception as e:
                        import TheKeyMachine.mods.reportMod as report

                        report.report_detected_exception(e, context="paste animation static attribute set")
                    if progress:
                        progress.step()

                destinations = _destination_entries(target, channel, anim_data)
                cut_destinations = set()
                for layer_name, layer_data, weight_data in destinations:
                    if progress and progress.cancelled:
                        break
                    if replace and layer_name not in cut_destinations:
                        _cut_destination_keys(
                            target, channel, layer_name, replace_range
                        )
                        cut_destinations.add(layer_name)
                    keys_set += _apply_channel_data(target, channel, layer_data, layer_name=layer_name)
                    weight_key = layer_name
                    if weight_data and weight_key not in applied_weights:
                        keys_set += _apply_anim_layer_weight_data(
                            layer_name,
                            weight_data,
                            progress=progress,
                            insert_time=insert_time,
                            time_shift=time_shift,
                        )
                        applied_weights.add(weight_key)
            if progress and progress.cancelled:
                break

    for layer_name, metadata in created_layers.items():
        animlayers.restore_layer_state(layer_name, metadata)
    if blocked_layers:
        locked_name = sorted(blocked_layers)[0]
        wutil.make_inViewMessage("Current animation layer '{}' is locked".format(locked_name))

    return keys_set


def _select_existing_targets(targets):
    targets = [target for target in (targets or []) if target and cmds.objExists(target)]
    if not targets:
        return
    try:
        cmds.select(targets, replace=True)
    except Exception:
        pass


def _apply_animation_data(animation_data, selected_objects, replace=False, insert_time=None, progress=None):
    targets = _copy_paste_targets(animation_data, selected_objects)
    if not targets:
        return 0, []

    controls = _animation_controls(animation_data)
    metadata = (animation_data or {}).get(ANIMATION_META_KEY) or {}
    keys_set = 0
    pasted_targets = []
    for control in targets:
        if control in controls:
            applied = _apply_animation_channels_to_targets(
                [control],
                controls[control],
                replace=replace,
                insert_time=insert_time,
                replace_range=(
                    _animation_data_timerange(animation_data) or (0, 10000)
                ),
                progress=progress,
                layer_metadata=metadata.get(ANIMATION_LAYER_META_KEY) or {},
                layer_scope=metadata.get("layer_scope"),
            )
            keys_set += applied
            if applied:
                pasted_targets.append(control)

    return keys_set, pasted_targets


def _is_valid_pose_attribute_value(value):
    if isinstance(value, (float, int)):
        return True
    if isinstance(value, list) and all(isinstance(v, (float, int)) for v in value):
        return True
    if (
        isinstance(value, list)
        and len(value) == 1
        and isinstance(value[0], (list, tuple))
        and all(isinstance(v, (float, int)) for v in value[0])
    ):
        return True
    if isinstance(value, str) and not re.search(r"[# ]", value):
        return True
    return False


def _pose_target_mappings(pose_data, selected_objects):
    pose_data = pose_data or {}
    selected_objects = list(selected_objects or [])

    if len(pose_data) == 1 and len(selected_objects) == 1:
        return [(next(iter(pose_data)), selected_objects[0])]

    targets = _copy_paste_targets(pose_data, selected_objects)
    return [(target, target) for target in targets if target in pose_data]


def _apply_pose_data(pose_data, selected_objects, progress=None, mappings=None):
    mappings = (
        list(mappings)
        if mappings is not None
        else _pose_target_mappings(pose_data, selected_objects)
    )
    if not mappings:
        return 0, []

    attrs_set = 0
    pasted_targets = []
    for source_control, target_control in mappings:
        control_attrs_set = 0
        for attr, value in pose_data[source_control].items():
            if progress and progress.cancelled:
                return attrs_set, pasted_targets
            if not _is_valid_pose_attribute_value(value):
                if progress:
                    progress.step()
                continue
            if not _attr_exists_and_settable(target_control, attr):
                if progress:
                    progress.step()
                continue
            try:
                _set_attr_value(f"{target_control}.{attr}", value)
                attrs_set += 1
                control_attrs_set += 1
            except RuntimeError as e:
                import TheKeyMachine.mods.reportMod as report

                report.report_detected_exception(e, context="paste pose attribute set")
            if progress:
                progress.step()
        if control_attrs_set:
            pasted_targets.append(target_control)

    return attrs_set, pasted_targets


def copy_animation(*args, **kwargs):
    def get_animation_channels(control):
        channels = []
        for attr in cmds.listAttr(control, keyable=True) or []:
            if attr == "tag":
                continue
            if _attr_exists_and_settable(control, attr):
                channels.append(attr)
        return channels

    target_info, target_plugs, selected_objects, _selected_channels = (
        animation_context.resolve_command_targets(
            default_mode="all_animation",
            include_shapes=False,
        )
    )
    selected_objects = list(dict.fromkeys(selected_objects or []))
    if not selected_objects:
        return

    time_context = target_info["time_context"]
    layer_context = animlayers.capture_context()
    if layer_context.get("selection_explicit") and not layer_context.get("copy_layer_ids"):
        return wutil.make_inViewMessage("Selected animation layer is locked")

    tint_range = _time_context_tint_range(time_context)
    copied_layer_ids = set(layer_context.get("copy_layer_ids") or [])
    copied_layers = {
        layer_id: dict(metadata)
        for layer_id, metadata in (layer_context.get("layers") or {}).items()
        if layer_id in copied_layer_ids
    }
    for layer_id, metadata in copied_layers.items():
        layer_name = metadata.get("name")
        if layer_id == animlayers.BASE_LAYER_ID or not layer_name:
            continue
        metadata["weight"] = _query_anim_layer_weight_data(
            layer_name, time_context
        )
    animation_data = {
        ANIMATION_META_KEY: {
            "type": "animation",
            "version": ANIMATION_SCHEMA_VERSION,
            "range": list(tint_range) if tint_range else None,
            "layer_scope": layer_context.get("copy_scope", "all"),
            "selected_layers": list(layer_context.get("selected_unlocked") or []),
            ANIMATION_LAYER_META_KEY: copied_layers,
        },
        ANIMATION_CONTROLS_KEY: {},
    }
    controls_data = animation_data[ANIMATION_CONTROLS_KEY]
    explicit_plugs = {}
    if target_info.get("source") in (
        "channel_box",
        "graph_editor",
        "graph_editor_outliner",
    ):
        for plug in target_plugs:
            if "." not in plug:
                continue
            control, channel = plug.rsplit(".", 1)
            explicit_plugs.setdefault(control, []).append(channel)
    channels_by_control = {
        control: list(
            dict.fromkeys(explicit_plugs.get(control) or get_animation_channels(control))
        )
        for control in selected_objects
    }
    channel_total = sum(len(channels) for channels in channels_by_control.values())

    try:
        with _copy_paste_operation(
            "copy_animation", "Animation Copied", tint="range", timerange=tint_range,
            progress=True, progress_max=channel_total,
        ) as operation:
            processor = operation["operation"]
            processor.set_status("Copying Animation")
            for control in selected_objects:
                if processor.cancelled:
                    return
                control_name = control
                animated_channels = channels_by_control[control]

                controls_data[control_name] = {}
                for channel in animated_channels:
                    plug = f"{control}.{channel}"
                    channel_data = _query_layered_anim_channel_data(
                        plug,
                        time_context,
                        layer_context=layer_context,
                        selected_curves=target_info.get("selected_curves"),
                    )
                    if channel_data.get(ANIMATION_FRAME_KEY) or channel_data.get(ANIMATION_LAYERS_KEY):
                        controls_data[control_name][channel] = channel_data
                    elif time_context.mode != "graph_editor_keys":
                        static_data = _query_static_channel_value(plug)
                        if static_data:
                            controls_data[control_name][channel] = static_data
                    processor.step()

            animation_data[ANIMATION_CONTROLS_KEY] = {
                control: channels
                for control, channels in controls_data.items()
                if channels
            }
            if not animation_data[ANIMATION_CONTROLS_KEY]:
                return wutil.make_inViewMessage(
                    "No animation found in the selected context"
                )

            if time_context.mode == "time_slider_range":
                timelineWidgets.clear_time_slider_selection()
            elif time_context.mode not in ("all_animation", "graph_editor_keys"):
                tint_range = _animation_data_timerange(animation_data)

            animation_data[ANIMATION_META_KEY]["range"] = list(tint_range) if tint_range else None
            clipboard.save("animation", animation_data)

            operation["timerange"] = tint_range
            operation["success"] = True
    except Exception as e:
        cmds.warning(f"Error saving animation: {e}")


# PASTE ANIMATION ___________________________________________________________________________


def paste_animation(*args, anchor_widget=None, **kwargs):
    selected_objects = selectionMod.get_selected_objects()

    animation_data = clipboard.load("animation", "No animation file found. Please copy animation first")
    if not animation_data:
        return

    targets = _copy_paste_targets(animation_data, selected_objects)
    paste_range = _animation_data_timerange(animation_data)
    key_count = _animation_data_apply_count(animation_data, targets=targets)
    prompt_range = None
    with _copy_paste_operation("paste_animation", "Animation Pasted", undo=True, tint="range", timerange=paste_range, progress=True, progress_max=key_count) as operation:
        processor = operation["operation"].set_status("Pasting Animation")
        keys_set, pasted_targets = _apply_animation_data(animation_data, selected_objects, replace=True, progress=processor)
        if keys_set:
            operation["timerange"] = paste_range
            operation["success"] = True
            _select_existing_targets(pasted_targets)
            _refresh_animation_view()
            prompt_range = paste_range
        else:
            cmds.warning("No matching animation targets found")
    _maybe_apply_paste_range(prompt_range, anchor_widget=anchor_widget)


# PASTE INSERT _________________________________________________________________________


def paste_insert_animation(*args, anchor_widget=None, **kwargs):
    selected_objects = selectionMod.get_selected_objects()
    current_time = cmds.currentTime(query=True)

    animation_data = clipboard.load("animation", "No animation file found. Please copy animation first")
    if not animation_data:
        return

    targets = _copy_paste_targets(animation_data, selected_objects)
    source_range = _animation_data_timerange(animation_data)
    first_source_frame = source_range[0] if source_range else current_time
    paste_range = _shift_timerange(source_range, current_time - first_source_frame)
    key_count = _animation_data_apply_count(animation_data, targets=targets)
    prompt_range = None
    with _copy_paste_operation("paste_insert_animation", "Animation Pasted", undo=True, tint="range", timerange=paste_range, progress=True, progress_max=key_count) as operation:
        processor = operation["operation"].set_status("Pasting Animation")
        keys_set, pasted_targets = _apply_animation_data(animation_data, selected_objects, insert_time=current_time, progress=processor)
        if keys_set:
            operation["timerange"] = paste_range
            operation["success"] = True
            _select_existing_targets(pasted_targets)
            _refresh_animation_view()
            prompt_range = paste_range
        else:
            cmds.warning("No matching animation targets found")
    _maybe_apply_paste_range(prompt_range, anchor_widget=anchor_widget)


# PASTE OPPOSITE ________________________________________________________________________


def paste_opposite_animation(*args, anchor_widget=None, **kwargs):
    from TheKeyMachine.tools.mirror import controller as mirror_controller

    exceptions = mirror_controller.load_exceptions()

    animation_data = clipboard.load("animation", "No animation file found. Please copy animation first")
    if not animation_data:
        return

    paste_range = _animation_data_timerange(animation_data)
    key_count = _animation_data_apply_count(animation_data)
    controls = _animation_controls(animation_data)
    scene_nodes = cmds.ls() or []
    scene_nodes_by_leaf = {
        node.rsplit("|", 1)[-1]: node for node in scene_nodes
    }
    prompt_range = None
    with _copy_paste_operation("paste_opposite_animation", "Animation Pasted", undo=True, tint="range", timerange=paste_range, progress=True, progress_max=key_count) as operation:
        keys_set = 0
        pasted_targets = []
        processor = operation["operation"].set_status("Pasting Opposite Animation")
        for control_name, anim_data in controls.items():
            if processor.cancelled:
                break
            mirror_control_name = mirror_controller.opposite_control_name(control_name)

            if mirror_control_name:
                full_mirror_control_name = scene_nodes_by_leaf.get(mirror_control_name)
                if not full_mirror_control_name:
                    continue

                mirrored_channels = {}
                for channel, channel_data in anim_data.items():
                    mirrored_channels[channel] = _transform_channel_values(
                        channel_data,
                        lambda value, attr=channel: mirror_controller.apply_exception(
                            exceptions, control_name, attr, value
                        ),
                    )
                applied = _apply_animation_channels_to_targets(
                    [full_mirror_control_name],
                    mirrored_channels,
                    replace=True,
                    progress=processor,
                    layer_metadata=(
                        (animation_data.get(ANIMATION_META_KEY) or {}).get(
                            ANIMATION_LAYER_META_KEY
                        )
                        or {}
                    ),
                    layer_scope=(animation_data.get(ANIMATION_META_KEY) or {}).get(
                        "layer_scope"
                    ),
                )
                keys_set += applied
                if applied:
                    pasted_targets.append(full_mirror_control_name)

        if keys_set:
            operation["timerange"] = paste_range
            operation["success"] = True
            _select_existing_targets(pasted_targets)
            _refresh_animation_view()
            prompt_range = paste_range
        else:
            cmds.warning("No matching animation targets found")
    _maybe_apply_paste_range(prompt_range, anchor_widget=anchor_widget)


def paste_animation_to(source_control_name=None, replace=True, insert_at_current=False, *args, anchor_widget=None, **kwargs):
    global _paste_to_dialog

    try:
        animation_data = clipboard.load("animation", "No animation file found. Please copy animation first")
    except Exception as e:
        cmds.warning("Error reading animation file: {}".format(e))
        return
    if animation_data is None:
        return

    if not isinstance(animation_data, dict) or not animation_data:
        cmds.warning("Animation file is empty or invalid")
        return

    def _apply_mappings(mappings, insert=False):
        current_time = cmds.currentTime(query=True) if insert else None
        pasted_data = {}
        source_range = _animation_data_timerange(animation_data)
        first_source_frame = source_range[0] if source_range else current_time
        paste_range = _shift_timerange(source_range, current_time - first_source_frame) if insert else source_range
        controls = _animation_controls(animation_data)
        key_count = sum(
            _animation_data_apply_count({ANIMATION_CONTROLS_KEY: {source_node: controls.get(source_node, {})}})
            for source_node, _ in mappings
        )
        prompt_range = None
        with _copy_paste_operation("paste_animation_to", "Animation Pasted", undo=True, tint="range", timerange=paste_range, progress=True, progress_max=key_count) as operation:
            total_keys_set = 0
            pasted_targets = []
            processor = operation["operation"].set_status("Pasting Animation")
            for source_node, target_node in mappings:
                if processor.cancelled:
                    break
                src_channels = controls.get(source_node, {})
                applied = _apply_animation_channels_to_targets(
                    [target_node],
                    src_channels,
                    replace=not insert,
                    insert_time=current_time if insert else None,
                    replace_range=(0, 1e6),
                    progress=processor,
                    layer_metadata=(
                        (animation_data.get(ANIMATION_META_KEY) or {}).get(
                            ANIMATION_LAYER_META_KEY
                        )
                        or {}
                    ),
                    layer_scope=(animation_data.get(ANIMATION_META_KEY) or {}).get(
                        "layer_scope"
                    ),
                )
                total_keys_set += applied
                if applied:
                    pasted_targets.append(target_node)
                if src_channels:
                    pasted_data[target_node] = src_channels

            if total_keys_set == 0:
                cmds.warning("No keys were pasted. Check that destination controls have the needed attributes and that the source has keyframes.")
                return False

            operation["timerange"] = paste_range or _animation_data_timerange(animation_data)
            operation["success"] = True
            _select_existing_targets(pasted_targets)
            _refresh_animation_view()
            prompt_range = operation["timerange"]
        _maybe_apply_paste_range(prompt_range, anchor_widget=anchor_widget)
        return True

    _paste_to_dialog = customWidgets.PasteToDialog(_animation_controls(animation_data), _apply_mappings, data_label="animation")
    _paste_to_dialog.show()


def export_animation_file(*args, **kwargs):
    return clipboard.export_dialog(
        "animation",
        "Export Animation",
        operation=toolCommon.current_tool_operation(),
    )


def import_animation_file(*args, **kwargs):
    return clipboard.import_dialog(
        "animation",
        "Import Animation",
        operation=toolCommon.current_tool_operation(),
    )


def paste_pose_to(*args, anchor_widget=None, **kwargs):
    global _paste_to_dialog

    pose_data = clipboard.load("pose", "No pose file found. Please copy pose first")
    if not pose_data:
        return

    def _apply_mappings(mappings, insert=False):
        with _copy_paste_operation("paste_pose_to", "Pose Pasted", undo=True, tint="current") as operation:
            attrs_set = 0
            pasted_targets = []
            for source_node, target_node in mappings:
                source_attrs = pose_data.get(source_node, {})
                target_pose_data = {target_node: source_attrs}
                target_attrs_set, target_pasted = _apply_pose_data(target_pose_data, [target_node])
                attrs_set += target_attrs_set
                pasted_targets.extend(target_pasted)

            if not attrs_set:
                cmds.warning("No pose values were pasted. Check that destination controls have the needed attributes.")
                return False

            operation["success"] = True
            _select_existing_targets(pasted_targets)
            return True

    _paste_to_dialog = customWidgets.PasteToDialog(pose_data, _apply_mappings, data_label="pose")
    _paste_to_dialog.show()


# COPY POSE ________________________________________________________________________


def copy_pose(*args, **kwargs):
    selected_objects = selectionMod.get_selected_objects()

    if not selected_objects:
        return

    pose_data = {}
    attributes_by_control = {
        control: cmds.listAttr(control, keyable=True, unlocked=True) or []
        for control in selected_objects
    }
    attribute_total = sum(len(attrs) for attrs in attributes_by_control.values())

    with _copy_paste_operation(
        "copy_pose",
        "Pose Copied",
        tint="current",
        progress=True,
        progress_max=attribute_total,
    ) as operation:
        processor = operation["operation"].set_status("Copying Pose")
        for control in selected_objects:
            control_name = control
            attributes = attributes_by_control[control]

            pose_data[control_name] = {}
            for attr in attributes:
                if processor.cancelled:
                    return
                try:
                    values = cmds.getAttr(f"{control}.{attr}")
                    pose_data[control_name][attr] = values
                except Exception as e:
                    import TheKeyMachine.mods.reportMod as report

                    report.report_detected_exception(e, context="copy pose attribute read")
                processor.step()

        clipboard.save("pose", pose_data)
        operation["success"] = True


def export_pose_file(*args, **kwargs):
    return clipboard.export_dialog(
        "pose",
        "Export Pose",
        operation=toolCommon.current_tool_operation(),
    )


def import_pose_file(*args, **kwargs):
    return clipboard.import_dialog(
        "pose",
        "Import Pose",
        operation=toolCommon.current_tool_operation(),
    )


# PASTE POSE _____________________________________________________________


def paste_pose(*args, **kwargs):
    selected_objects = selectionMod.get_selected_objects()

    pose_data = clipboard.load("pose", "No pose file found. Please copy pose first")
    if not pose_data:
        return

    mappings = _pose_target_mappings(pose_data, selected_objects)
    attribute_total = sum(len(pose_data[source]) for source, _target in mappings)
    with _copy_paste_operation(
        "paste_pose",
        "Pose Pasted",
        undo=True,
        tint="current",
        progress=True,
        progress_max=attribute_total,
    ) as operation:
        processor = operation["operation"].set_status("Pasting Pose")
        attrs_set, pasted_targets = _apply_pose_data(
            pose_data,
            selected_objects,
            progress=processor,
            mappings=mappings,
        )
        if attrs_set:
            operation["success"] = True
            _select_existing_targets(pasted_targets)
        else:
            cmds.warning("No matching pose targets found")


def paste_mirror_pose(*args, **kwargs):
    """Paste copied pose values onto opposite controls using mirror exceptions."""
    from TheKeyMachine.tools.mirror import controller as mirror_controller

    exceptions = mirror_controller.load_exceptions()

    pose_data = clipboard.load("pose", "No pose file found. Please copy pose first")
    if not pose_data:
        return

    attrs_set = 0
    pasted_targets = []
    attribute_total = sum(len(attributes) for attributes in pose_data.values())
    with _copy_paste_operation(
        "paste_mirror_pose",
        "Pose Pasted",
        undo=True,
        tint="current",
        progress=True,
        progress_max=attribute_total,
    ) as operation:
        processor = operation["operation"].set_status("Pasting Mirror Pose")
        scene_nodes = {
            node.rsplit("|", 1)[-1]: node for node in (cmds.ls() or [])
        }
        for control_name, attributes in pose_data.items():
            mirror_name = mirror_controller.opposite_control_name(control_name)
            if not mirror_name:
                if attributes:
                    processor.step(amount=len(attributes))
                continue
            mirror_control = scene_nodes.get(mirror_name)
            if not mirror_control:
                if attributes:
                    processor.step(amount=len(attributes))
                continue

            control_attrs_set = 0
            for attr, value in attributes.items():
                if processor.cancelled:
                    return
                if not _is_valid_pose_attribute_value(value) or not _attr_exists_and_settable(mirror_control, attr):
                    processor.step()
                    continue
                mirrored_value = mirror_controller.apply_exception(exceptions, control_name, attr, value)
                try:
                    _set_attr_value("{}.{}".format(mirror_control, attr), mirrored_value)
                    attrs_set += 1
                    control_attrs_set += 1
                except RuntimeError as error:
                    import TheKeyMachine.mods.reportMod as report

                    report.report_detected_exception(error, context="paste mirror pose attribute set")
                processor.step()
            if control_attrs_set:
                pasted_targets.append(mirror_control)

        if attrs_set:
            operation["success"] = True
            _select_existing_targets(pasted_targets)
        else:
            cmds.warning("No matching mirror pose targets found")
