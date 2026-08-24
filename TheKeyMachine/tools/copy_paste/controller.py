"""Copy/paste pose and animation behavior."""

import re
import time

from maya import cmds

from TheKeyMachine.maya import animation
from TheKeyMachine.data import icons
from TheKeyMachine.maya import selection
from TheKeyMachine.tools import clipboard
from TheKeyMachine.tools import common as toolCommon
from TheKeyMachine.ui.widgets import customDialogs
import TheKeyMachine.ui.widgets.timeline as timelineWidgets
import TheKeyMachine.ui.widgets.util as wutil
from TheKeyMachine.tools.copy_paste import widgets as copy_paste_widgets

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
POSE_SCHEMA_VERSION = 2
POSE_CONTROLS_KEY = "controls"
POSE_META_KEY = "meta"
TANGENT_KEYS = {
    "itt": "inTangentType",
    "ott": "outTangentType",
    "ia": "inAngle",
    "oa": "outAngle",
    "iw": "inWeight",
    "ow": "outWeight",
    "wt": "weightedTangents",
}
ANIMATION_CHANNEL_BATCH_SIZE = 16
POSE_ATTRIBUTE_BATCH_SIZE = 32
PASTE_CHANNEL_BATCH_SIZE = 32
PASTE_CONTROL_BATCH_SIZE = 32


def _result_message(data_type, action):
    """Emit the shared concise copy/paste result language."""
    return wutil.make_inViewMessage(
        "No {} to {}".format(data_type, action)
    )


def _load_clipboard_data(slot, data_type):
    data = clipboard.load(slot)
    if not data:
        _result_message(data_type, "paste")
    return data


def _locked_layer_message():
    return wutil.make_inViewMessage("Selected layer is locked")


def _is_animation_payload(data):
    metadata = data.get(ANIMATION_META_KEY) if isinstance(data, dict) else None
    return (
        isinstance(metadata, dict)
        and metadata.get("type") == "animation"
        and metadata.get("version") == ANIMATION_SCHEMA_VERSION
        and isinstance(data.get(ANIMATION_CONTROLS_KEY), dict)
    )


def _animation_controls(animation_data):
    if not _is_animation_payload(animation_data):
        return {}
    return animation_data.get(ANIMATION_CONTROLS_KEY) or {}


def _is_pose_payload(data):
    metadata = data.get(POSE_META_KEY) if isinstance(data, dict) else None
    return (
        isinstance(metadata, dict)
        and metadata.get("type") == "pose"
        and metadata.get("version") == POSE_SCHEMA_VERSION
        and isinstance(data.get(POSE_CONTROLS_KEY), dict)
    )


def _pose_controls(pose_data):
    return (
        pose_data.get(POSE_CONTROLS_KEY) or {}
        if _is_pose_payload(pose_data)
        else {}
    )


def _pose_layer_context(pose_data):
    if not _is_pose_payload(pose_data):
        return None
    return (pose_data.get(POSE_META_KEY) or {}).get("layer_context")


def _copy_paste_targets(saved_data, selected_objects):
    if selected_objects:
        return selected_objects
    return [control for control in (saved_data or {}) if cmds.objExists(control)]


def _canonical_scene_node(node):
    """Return one node's unambiguous full DAG path when it still exists."""
    if not node:
        return None
    try:
        matches = cmds.ls(node, long=True) or []
    except Exception:
        return None
    return matches[0] if len(matches) == 1 else None


def _animation_target_mappings(animation_data, selected_objects):
    """Match copied controls to selected instances by Maya node identity.

    Resolve both saved and selected controls to full DAG paths so Maya's
    short-name presentation cannot break identity matching. Ambiguous names
    are deliberately refused.
    """
    controls = _animation_controls(animation_data)
    selected_objects = list(dict.fromkeys(selected_objects or []))
    if not selected_objects:
        return [
            (source, source)
            for source in controls
            if cmds.objExists(source)
        ]

    sources_by_path = {}
    for source in controls:
        source_path = _canonical_scene_node(source)
        if source_path:
            sources_by_path.setdefault(source_path, []).append(source)

    mappings = []
    for target in selected_objects:
        if target in controls:
            mappings.append((target, target))
            continue
        target_path = _canonical_scene_node(target)
        matching_sources = sources_by_path.get(target_path) or []
        if len(matching_sources) == 1:
            mappings.append((matching_sources[0], target))
    return mappings


def _animation_layer_items(channel_data):
    layers = channel_data.get(ANIMATION_LAYERS_KEY) or {}
    if not isinstance(layers, dict):
        return []
    return [
        (
            layer_id,
            entry.get("data") or {},
            entry.get(ANIMATION_LAYER_WEIGHT_KEY) or {},
        )
        for layer_id, entry in layers.items()
        if isinstance(entry, dict)
    ]


def _key_pair_count(channel_data):
    """Return the number of key attempts the paste loop will perform."""
    channel_data = channel_data or {}
    return min(
        len(channel_data.get(ANIMATION_FRAME_KEY) or []),
        len(channel_data.get(ANIMATION_VALUE_KEY) or []),
    )


def _animation_channels_key_count(channels, layer_metadata=None):
    """Count channel and layer-weight keys for one destination control."""
    count = 0
    counted_weight_layers = set()
    layer_metadata = layer_metadata or {}
    for anim_data in (channels or {}).values():
        count += _key_pair_count(anim_data)
        for layer_id, layer_data, weight_data in _animation_layer_items(anim_data):
            count += _key_pair_count(layer_data)
            if layer_id in counted_weight_layers:
                continue
            weight_data = weight_data or (
                (layer_metadata.get(layer_id) or {}).get("weight") or {}
            )
            count += _key_pair_count(weight_data)
            counted_weight_layers.add(layer_id)
    return count


def _animation_data_key_count(animation_data, targets=None):
    controls = _animation_controls(animation_data)
    target_names = set(controls.keys() if targets is None else targets)
    layer_metadata = (
        ((animation_data or {}).get(ANIMATION_META_KEY) or {}).get(
            ANIMATION_LAYER_META_KEY
        )
        or {}
    )
    return sum(
        _animation_channels_key_count(channels, layer_metadata=layer_metadata)
        for control, channels in controls.items()
        if control in target_names
    )


def _animation_data_apply_count(animation_data, targets=None):
    count = _animation_data_key_count(animation_data, targets=targets)
    controls = _animation_controls(animation_data)
    target_names = set(controls.keys() if targets is None else targets)
    for control, channels in controls.items():
        if control not in target_names:
            continue
        for anim_data in (channels or {}).values():
            if ANIMATION_STATIC_VALUE_KEY in (anim_data or {}):
                count += 1
    return count


def _animation_channels_apply_count(channels, layer_metadata=None):
    return _animation_channels_key_count(
        channels, layer_metadata=layer_metadata
    ) + sum(
        1
        for anim_data in (channels or {}).values()
        if ANIMATION_STATIC_VALUE_KEY in (anim_data or {})
    )


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


def _query_anim_channel_data(source, time_context, selected_times=None):
    if not source:
        return {}
    try:
        if time_context.mode == "graph_editor_keys":
            if selected_times is None:
                keyframes = cmds.keyframe(source, query=True, selected=True, timeChange=True)
                values = cmds.keyframe(source, query=True, selected=True, valueChange=True)
            else:
                keyframes = []
                values = []
                for key_time in sorted(set(float(value) for value in selected_times)):
                    queried_values = cmds.keyframe(
                        source,
                        query=True,
                        time=(key_time, key_time),
                        valueChange=True,
                    ) or []
                    if queried_values:
                        keyframes.append(key_time)
                        values.append(queried_values[0])
        elif time_context.mode == "time_slider_range":
            keyframes = cmds.keyframe(source, query=True, time=(time_context.start_frame, time_context.end_frame))
            values = cmds.keyframe(source, query=True, vc=True, time=(time_context.start_frame, time_context.end_frame))
        else:
            keyframes = cmds.keyframe(source, query=True)
            values = cmds.keyframe(source, query=True, vc=True)
    except Exception:
        keyframes, values = [], []

    keyframes = keyframes or []
    values = values or []
    return {
        ANIMATION_FRAME_KEY: keyframes,
        ANIMATION_VALUE_KEY: values,
        ANIMATION_TANGENT_KEY: _query_key_tangent_data(source, keyframes),
    }


def _query_static_channel_value(plug):
    try:
        attr_type = cmds.getAttr(plug, type=True)
        if attr_type in ("message", "matrix", "fltMatrix", "stringArray", "doubleArray", "Int32Array", "vectorArray", "pointArray"):
            return {}
        value = cmds.getAttr(plug)
    except Exception:
        return {}
    return {ANIMATION_STATIC_VALUE_KEY: value}


def _query_layered_anim_channel_data(
    plug,
    time_context,
    layer_context=None,
    selected_curves=None,
    selected_keyframes=None,
    scene_layers=None,
):
    layer_context = (
        layer_context
        or animation.layer_cache.tool_context()["context"]
    )
    try:
        layer_entries = animation.layer_graph.curves_by_layer(
            plug,
            scene_layers=scene_layers,
        )
    except Exception:
        layer_entries = []

    if not layer_entries:
        return _query_anim_channel_data(plug, time_context)

    allowed_layer_ids = set(layer_context.get("copy_layer_ids") or [])
    selected_curves = set(selected_curves or [])
    selected_times_by_curve = {}
    for selected_curve, key_time in selected_keyframes or []:
        selected_times_by_curve.setdefault(selected_curve, []).append(float(key_time))
    layer_data = {}
    for entry in layer_entries:
        curve = entry.get("curve")
        if not curve:
            continue
        layer_name = entry.get("layer")
        layer_id = animation.layer_id_for_name(layer_name)
        if allowed_layer_ids and layer_id not in allowed_layer_ids:
            continue
        if time_context.mode == "graph_editor_keys" and selected_curves and curve not in selected_curves:
            continue
        data = _query_anim_channel_data(
            curve,
            time_context,
            selected_times=selected_times_by_curve.get(curve),
        )
        if not data.get(ANIMATION_FRAME_KEY):
            continue
        layer_data[layer_id] = {
            "data": data,
        }
    return {ANIMATION_LAYERS_KEY: layer_data} if layer_data else {}


def _query_anim_layer_weight_data(layer_name, time_context, selected_keyframes=None):
    if not layer_name:
        return {}
    weight_plug = "{}.weight".format(layer_name)
    if not cmds.objExists(weight_plug):
        return {}
    # Only query if the weight plug actually has an animCurve driving it.
    # Unkeyed layers have a static weight (1.0) with no curve; querying them
    # with cmds.keyframe can raise "Unable to parse the argument list".
    weight_curves = animation.weight_curves(layer_name)
    if not weight_curves:
        return {}
    if time_context.mode == "graph_editor_keys":
        selected_times = [
            float(key_time)
            for curve, key_time in selected_keyframes or []
            if curve in weight_curves
        ]
        data = _query_anim_channel_data(
            weight_curves[0],
            time_context,
            selected_times=selected_times,
        )
    else:
        try:
            data = _query_anim_channel_data(weight_plug, time_context)
        except Exception:
            data = {}
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
        pasted_times = []
        pasted_tangents = []
        for key_index, (key_time, value) in enumerate(zip(keyframes, values)):
            if value is None or key_time is None:
                continue
            try:
                pasted_time = float(key_time) + float(weight_time_shift)
                cmds.setKeyframe(
                    f"{layer_name}.weight",
                    time=(pasted_time,),
                    value=float(value),
                )
                pasted_times.append(pasted_time)
                pasted_tangents.append(
                    _key_tangent_snapshot(tangent_data, key_index)
                )
                applied += 1
            except Exception:
                pass
            if progress and progress.step():
                return applied
        if pasted_times and any(pasted_tangents):
            curves = animation.weight_curves(layer_name)
            tangent_curve = curves[0] if curves else None
            if tangent_curve:
                _apply_channel_weighted_tangents(
                    tangent_curve,
                    None,
                    tangent_data,
                )
                animation.apply_key_tangent_snapshots(
                    tangent_curve,
                    pasted_times,
                    pasted_tangents,
                    apply_weighted=False,
                )
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


def _refresh_animation_view(targets=None):
    targets = list(dict.fromkeys(targets or ()))
    try:
        current_time = cmds.currentTime(query=True)
        cmds.currentTime(current_time, edit=True)
    except Exception:
        pass
    if targets:
        try:
            cmds.dgdirty(targets)
        except Exception:
            pass
    try:
        cmds.refresh(currentView=True)
    except Exception:
        pass


def _query_key_tangent_data(plug, keyframes):
    snapshots = animation.key_tangent_snapshots(plug, keyframes)
    return {
        short_key: [snapshot.get(query_key) for snapshot in snapshots]
        for short_key, query_key in TANGENT_KEYS.items()
    }


def _key_tangent_snapshot(tangent_data, index):
    snapshot = {}
    for short_key, query_key in TANGENT_KEYS.items():
        values = (tangent_data or {}).get(short_key) or []
        if index < len(values) and values[index] is not None:
            snapshot[query_key] = values[index]
    return snapshot


def _apply_channel_weighted_tangents(target, channel, tangent_data):
    weighted_values = (tangent_data or {}).get("wt") or []
    weighted = next((value for value in weighted_values if value is not None), None)
    if weighted is None:
        return
    animation.apply_weighted_tangents(
        target,
        weighted,
        attribute=channel or None,
    )


def _attr_exists_and_settable(node, attr):
    full_attr = f"{node}.{attr}"
    try:
        if not cmds.getAttr(full_attr, settable=True):
            return False
        conns = cmds.listConnections(full_attr, source=True, destination=False, plugs=False)
        if conns:
            for conn in conns:
                node_type = cmds.nodeType(conn)
                if not ("animCurve" in node_type or "animBlend" in node_type or "mute" in node_type):
                    return False
        return True
    except Exception:
        return False


_SETTABLE_SOURCE_TYPES = ("animCurve", "animBlendNodeBase", "mute")


def _settable_keyable_channels(node):
    """Return ``node``'s keyable, settable attribute names, excluding any
    driven by something other than an anim curve/anim-layer blend/mute node.

    Same rule as ``_attr_exists_and_settable``, but resolved with a handful
    of batched queries for the whole node instead of 2-3 cmds calls per
    attribute -- enumerating channels for many selected controls (e.g. Copy
    Animation) was otherwise dominated by per-attribute round-trips.
    """
    try:
        attrs = [a for a in (cmds.listAttr(node, keyable=True, settable=True) or []) if a != "tag"]
    except Exception:
        return []
    if not attrs:
        return []

    try:
        pairs = cmds.listConnections(
            ["{}.{}".format(node, attr) for attr in attrs],
            source=True,
            destination=False,
            plugs=True,
            connections=True,
        ) or []
    except Exception:
        pairs = []

    sources_by_attr = {}
    for index in range(0, len(pairs) - 1, 2):
        dest_attr = pairs[index].rsplit(".", 1)[-1]
        source_node = pairs[index + 1].split(".", 1)[0]
        sources_by_attr.setdefault(dest_attr, []).append(source_node)

    if not sources_by_attr:
        return attrs

    all_sources = sorted({source for sources in sources_by_attr.values() for source in sources})
    try:
        allowed_sources = set(cmds.ls(all_sources, type=_SETTABLE_SOURCE_TYPES) or [])
    except Exception:
        allowed_sources = set()

    return [
        attr
        for attr in attrs
        if all(source in allowed_sources for source in sources_by_attr.get(attr, ()))
    ]


def _set_attr_value(plug, value):
    if isinstance(value, list):
        if len(value) == 1 and isinstance(value[0], (list, tuple)):
            cmds.setAttr(plug, *value[0])
        else:
            cmds.setAttr(plug, *value)
    else:
        cmds.setAttr(plug, value)


def configure_copy_paste_operation(
    tool_id,
    success_message,
    tint="none",
    default_mode="current_frame",
    timerange=None,
    progress_max=0,
):
    """Apply copy/paste runtime details to the dispatcher-owned operation."""
    operation = toolCommon.require_tool_operation()
    operation.set_status(success_message)
    if progress_max:
        operation.set_total(progress_max)
    operation_tint = (
        "range" if tint == "range" and timerange
        else "current" if tint == "current"
        else "none"
    )
    toolCommon.ensure_operation_tint(
        operation,
        tint=operation_tint,
        timerange=timerange,
        default_mode=default_mode,
        tint_key=tool_id,
    )
    return operation


def _apply_animation_channels_to_targets(
    targets,
    channels_data=None,
    replace=False,
    insert_time=None,
    time_shift=None,
    replace_range=(0, 10000),
    progress=None,
    layer_metadata=None,
    channels_by_target=None,
    applied_targets=None,
):
    from TheKeyMachine.tools.animation_layers import controller as animation_layers_controller

    keys_set = 0
    targets = list(dict.fromkeys(targets or ()))
    channels_by_target = channels_by_target or {}
    applied_targets = applied_targets if applied_targets is not None else set()
    settable_channels = {
        target: set(_settable_keyable_channels(target))
        for target in targets
    }
    progress_batch_size = 25
    destination_context = animation.layer_cache.tool_context()["context"]
    scene_layers = animation.scene_layer_objects()
    existing_layer_names = set(
        animation.scene_layer_names(include_root=False)
    )
    copied_layers = layer_metadata or {}
    # Diagnostic only (TKM_DEBUG_TIMING): count how many keys actually land
    # on each resolved layer name, so a "keys ended up on the wrong layer"
    # report can be confirmed or ruled out from real setKeyframe results
    # instead of re-reading the destination-resolution logic again.
    _debug_layer_counts = {} if toolCommon.debug_timing_enabled() else None
    created_layers = {}
    applied_weights = set()
    blocked_layers = set()

    def _source_entries(channel_data):
        entries = []
        if channel_data.get(ANIMATION_FRAME_KEY):
            entries.append((animation.BASE_LAYER_ID, channel_data, {}))
        for layer_id, data, weight_data in _animation_layer_items(channel_data):
            if not weight_data:
                weight_data = _layer_meta(layer_id).get("weight") or {}
            entries.append((layer_id, data, weight_data))
        return entries

    def _layer_meta(layer_id):
        metadata = dict(copied_layers.get(layer_id) or {})
        if layer_id == animation.BASE_LAYER_ID:
            metadata.setdefault("root", True)
            metadata.setdefault("name", destination_context.get("root_name"))
        else:
            metadata.setdefault("root", False)
            metadata.setdefault("name", layer_id)
        return metadata

    def _ensure_source_layer(layer_id, target, channel):
        nonlocal scene_layers
        metadata = _layer_meta(layer_id)
        destination = destination_context.ensure_destination(
            layer_id,
            metadata,
            "{}.{}".format(target, channel),
            existing_layer_names=existing_layer_names,
        )
        layer_name = destination.get("layer")
        if destination.get("blocked"):
            blocked_layers.add(layer_name or "BaseAnimation")
            return False
        if not destination.get("member"):
            return False
        if destination.get("created"):
            created_layers[layer_name] = metadata
            if metadata.get("is_group"):
                # Mirrors tools.animation_layers.controller._import_layer's
                # own pattern: create_layer() (called inside
                # ensure_destination() above) has no notion of groups/color,
                # so a copied group is marked and colored here, right after
                # creation, the one place every paste entry point (Paste,
                # Paste Insert, Paste Opposite, Paste To) funnels through.
                animation_layers_controller.mark_as_group(layer_name)
                animation_layers_controller.set_group_color(layer_name, metadata.get("color"))
            # A new layer changes the blend-node graph used for exact curve
            # resolution. Refresh it once here, then reuse it for every
            # remaining pasted channel.
            animation.layer_cache.capture()
            scene_layers = animation.scene_layer_objects()
        return layer_name

    def _destination_entries(target, channel, channel_data):
        """Resolve where each copied layer's data goes on paste.

        Two rules, matching the original spec exactly: a deliberately
        selected NON-BASE destination layer in the Anim Layer Editor
        overrides everything and takes the whole paste. Otherwise every
        copied layer is restored by name -- matching an existing layer of
        the same name or recreating it -- regardless of whether the copy
        covered one layer or the whole stack.

        The redirect only fires for a non-base selection on purpose:
        BaseAnimation itself commonly shows as "selected" in Maya's Anim
        Layer Editor whenever nothing else has been explicitly picked (a
        fresh scene, or a layer that was since deleted), so treating any
        selection -- including Base -- as a deliberate redirect silently
        dumped a single named layer's keys into BaseAnimation instead of
        restoring it by name.
        """
        source_entries = _source_entries(channel_data)
        if not source_entries:
            return []

        non_base = [
            layer_id
            for layer_id, _data, _weight in source_entries
            if layer_id != animation.BASE_LAYER_ID
        ]
        recreate_stack = bool(non_base and not destination_context.get("has_layers"))
        plug = "{}.{}".format(target, channel)
        active_layer_id = destination_context.get("active")
        explicit_redirect = (
            destination_context.get("selection_explicit")
            and active_layer_id
            and active_layer_id != animation.BASE_LAYER_ID
            and not recreate_stack
        )
        if explicit_redirect:
            destination = destination_context.destination_for_plug(plug)
            if destination.get("blocked"):
                blocked_name = (
                    destination.get("layer")
                    or destination_context.get("root_name")
                )
                blocked_layers.add(blocked_name or "BaseAnimation")
                return []
            # explicit_redirect guarantees this is a non-base layer, so the
            # only ambiguity left is which source entry to send there.
            destination_id = destination.get("layer_id")
            matching = [
                entry for entry in source_entries if entry[0] == destination_id
            ]
            if not matching and len(source_entries) == 1:
                matching = source_entries
            if not matching:
                return []
            _source_id, data, _weight_data = matching[0]
            return [(destination.get("layer"), data, {})]

        resolved = []
        for layer_id, data, weight_data in source_entries:
            layer_name = _ensure_source_layer(layer_id, target, channel)
            if layer_name is False:
                if _debug_layer_counts is not None:
                    bucket = "{} [layer create/membership failed, skipped]".format(layer_id)
                    _debug_layer_counts[bucket] = _debug_layer_counts.get(bucket, 0) + 1
                continue
            resolved.append((layer_name, data, weight_data))
        return resolved

    def _cut_destination_keys(target, channel, layer_name, timerange):
        try:
            if animation.has_anim_layers():
                curve = animation.layer_graph.curve_for_plug(
                    "{}.{}".format(target, channel),
                    layer_name=layer_name,
                    scene_layers=scene_layers,
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

    def _cut_layer_weight_keys(layer_name, timerange):
        if not layer_name:
            return
        try:
            cmds.cutKey(
                "{}.weight".format(layer_name),
                time=timerange,
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
        if paste_layer is None and animation.has_anim_layers():
            # Once any anim layer exists, an implicit (no animLayer flag)
            # setKeyframe can hit Maya's own ambiguous-layer resolution and
            # silently key nothing. Target BaseAnimation by name instead of
            # leaving it to Maya to guess.
            paste_layer = animation.root_layer_name()
        channel_time_shift = time_shift
        if channel_time_shift is None:
            channel_time_shift = insert_time - keyframes[0] if insert_time is not None else 0
        tangent_data = channel_data.get(ANIMATION_TANGENT_KEY) or {}
        pasted_times = []
        pasted_tangents = []
        for key_index, (frame, value) in enumerate(zip(keyframes, values)):
            try:
                key_time = frame + channel_time_shift
                key_kwargs = {
                    "time": (key_time,),
                    "attribute": channel,
                    "value": value,
                    "shape": False,
                }
                if paste_layer:
                    key_kwargs["animLayer"] = paste_layer
                result = cmds.setKeyframe(target, **key_kwargs)
                pasted_times.append(key_time)
                pasted_tangents.append(
                    _key_tangent_snapshot(tangent_data, key_index)
                )
                applied += 1
                if _debug_layer_counts is not None:
                    bucket = paste_layer or "BaseAnimation(no layer flag)"
                    if not result:
                        bucket += " [setKeyframe returned falsy]"
                    _debug_layer_counts[bucket] = _debug_layer_counts.get(bucket, 0) + 1
            except Exception as e:
                import TheKeyMachine.tools.bug_report.controller as report

                report.report_detected_exception(e, context="paste animation set key")
            pending_progress += 1
            if progress and pending_progress >= progress_batch_size:
                if progress.step(amount=pending_progress):
                    return applied
                pending_progress = 0
        if progress and pending_progress:
            progress.step(amount=pending_progress)
        if pasted_times and any(pasted_tangents):
            tangent_curve = animation.layer_graph.curve_for_plug(
                "{}.{}".format(target, channel),
                layer_name=(
                    None
                    if paste_layer == animation.root_layer_name()
                    else paste_layer
                ),
                scene_layers=scene_layers,
            )
            if tangent_curve:
                _apply_channel_weighted_tangents(
                    tangent_curve,
                    None,
                    tangent_data,
                )
                animation.apply_key_tangent_snapshots(
                    tangent_curve,
                    pasted_times,
                    pasted_tangents,
                    apply_weighted=False,
                )
        return applied

    def _apply_channel(target, channel, anim_data):
        nonlocal keys_set
        if channel not in settable_channels.get(target, set()):
            return
        keys_before = keys_set

        if ANIMATION_STATIC_VALUE_KEY in (anim_data or {}):
            destination = destination_context.destination_for_plug(
                "{}.{}".format(target, channel)
            )
            if destination.get("blocked"):
                blocked_layers.add(
                    destination.get("layer")
                    or destination_context.get("root_name")
                    or "BaseAnimation"
                )
                return
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
                        shape=False,
                    )
                else:
                    _set_attr_value(f"{target}.{channel}", value)
                keys_set += 1
            except Exception as e:
                import TheKeyMachine.tools.bug_report.controller as report

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
                if replace:
                    # Weight belongs to the layer, not this channel,
                    # so it isn't covered by the per-channel cut
                    # above -- without this, old weight keys would
                    # linger alongside newly pasted ones.
                    _cut_layer_weight_keys(layer_name, replace_range)
                keys_set += _apply_anim_layer_weight_data(
                    layer_name,
                    weight_data,
                    progress=progress,
                    insert_time=insert_time,
                    time_shift=time_shift,
                )
                applied_weights.add(weight_key)
        if keys_set > keys_before:
            applied_targets.add(target)

    channel_items = [
        (target, channel, anim_data)
        for target in targets
        for channel, anim_data in (
            channels_by_target.get(target, channels_data) or {}
        ).items()
    ]

    def _apply_channel_batch(item_batch):
        for target, channel, anim_data in item_batch:
            _apply_channel(target, channel, anim_data)

    if progress:
        progress.process(
            channel_items,
            _apply_channel_batch,
            batch_size=PASTE_CHANNEL_BATCH_SIZE,
            strategy="worker",
            advance_progress=False,
            manage_progress=False,
        )
    else:
        _apply_channel_batch(channel_items)

    animation.restore_created_layer_states(created_layers)
    if blocked_layers:
        _locked_layer_message()

    if _debug_layer_counts is not None:
        print("[TKM timing] paste keys actually written, by resolved layer: {}".format(
            dict(_debug_layer_counts)
        ))

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
    mappings = _animation_target_mappings(animation_data, selected_objects)
    if not mappings:
        return 0, []

    controls = _animation_controls(animation_data)
    metadata = (animation_data or {}).get(ANIMATION_META_KEY) or {}
    channels_by_target = {
        target_control: controls[source_control]
        for source_control, target_control in mappings
    }
    pasted_targets = set()
    keys_set = _apply_animation_channels_to_targets(
        list(channels_by_target),
        replace=replace,
        insert_time=insert_time,
        replace_range=(
            _animation_data_timerange(animation_data) or (0, 10000)
        ),
        progress=progress,
        layer_metadata=metadata.get(ANIMATION_LAYER_META_KEY) or {},
        channels_by_target=channels_by_target,
        applied_targets=pasted_targets,
    )

    return keys_set, [
        target_control
        for _source_control, target_control in mappings
        if target_control in pasted_targets
    ]


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
    pose_data = _pose_controls(pose_data)
    selected_objects = list(selected_objects or [])

    if len(pose_data) == 1 and len(selected_objects) == 1:
        return [(next(iter(pose_data)), selected_objects[0])]

    targets = _copy_paste_targets(pose_data, selected_objects)
    return [(target, target) for target in targets if target in pose_data]


def _apply_pose_data(
    pose_data,
    selected_objects,
    progress=None,
    mappings=None,
    allowed_target_attributes=None,
):
    controls = _pose_controls(pose_data)
    mappings = (
        list(mappings)
        if mappings is not None
        else _pose_target_mappings(pose_data, selected_objects)
    )
    if not mappings:
        return 0, []

    def _attributes_for_mapping(source_control, target_control):
        attributes = controls.get(source_control) or {}
        if allowed_target_attributes is None:
            return attributes
        allowed = allowed_target_attributes.get(target_control) or set()
        return {
            attr: value
            for attr, value in attributes.items()
            if attr in allowed
        }

    target_plugs = [
        "{}.{}".format(target_control, attr)
        for source_control, target_control in mappings
        for attr in _attributes_for_mapping(source_control, target_control)
    ]
    layer_context, created_layers = animation.LayerContext(
        _pose_layer_context(pose_data) or {}
    ).prepare_paste(target_plugs)
    attrs_set = 0
    pasted_targets = []
    blocked_destination = False
    current_time = cmds.currentTime(query=True)
    settable_channels = {
        target_control: set(_settable_keyable_channels(target_control))
        for _source_control, target_control in mappings
    }

    def _apply_mapping(source_control, target_control):
        nonlocal attrs_set, blocked_destination
        control_attrs_set = 0
        attributes = _attributes_for_mapping(source_control, target_control)
        groups, blocked = layer_context.group_by_destination(
            target_control, attributes.keys()
        )
        blocked_destination = blocked_destination or bool(blocked)
        destinations = {
            attr: layer_name
            for layer_name, grouped_attrs in groups.items()
            for attr in grouped_attrs
        }
        for attr, value in attributes.items():
            if progress and progress.cancelled:
                return
            if (
                attr not in destinations
                or not _is_valid_pose_attribute_value(value)
                or attr not in settable_channels.get(target_control, set())
            ):
                if progress:
                    progress.step()
                continue
            layer_name = destinations[attr]
            try:
                if layer_context.get("has_layers") and isinstance(
                    value, (float, int)
                ):
                    paste_layer = layer_name or layer_context.get("root_name")
                    result = cmds.setKeyframe(
                        target_control,
                        attribute=attr,
                        time=(current_time,),
                        value=value,
                        animLayer=paste_layer,
                        shape=False,
                    )
                    if not result:
                        continue
                else:
                    # Scenes without layers and non-animatable values
                    # retain pose paste's traditional setAttr behavior.
                    _set_attr_value(
                        "{}.{}".format(target_control, attr), value
                    )
                attrs_set += 1
                control_attrs_set += 1
            except (RuntimeError, ValueError, TypeError) as e:
                import TheKeyMachine.tools.bug_report.controller as report

                report.report_detected_exception(
                    e, context="paste pose attribute set"
                )
            finally:
                if progress:
                    progress.step()
        if control_attrs_set:
            pasted_targets.append(target_control)

    def _apply_mapping_batch(mapping_batch):
        for source_control, target_control in mapping_batch:
            _apply_mapping(source_control, target_control)

    try:
        if progress:
            progress.process(
                mappings,
                _apply_mapping_batch,
                batch_size=PASTE_CONTROL_BATCH_SIZE,
                strategy="worker",
                advance_progress=False,
                manage_progress=False,
            )
        else:
            _apply_mapping_batch(mappings)
    finally:
        animation.restore_created_layer_states(created_layers)

    if blocked_destination:
        _locked_layer_message()
    return attrs_set, pasted_targets


def copy_animation(*args, **kwargs):
    from TheKeyMachine.tools.animation_layers import controller as animation_layers_controller

    get_animation_channels = _settable_keyable_channels

    _t0 = time.perf_counter() if toolCommon.debug_timing_enabled() else None

    target_info = animation.resolve_context(
        default_mode="all_animation",
        include_channels=True,
    )
    target_plugs = target_info.plugs
    selected_objects = target_info.objects
    selected_objects = list(dict.fromkeys(selected_objects or []))
    if not selected_objects:
        return wutil.make_inViewMessage("Select an object")

    _t_resolve = time.perf_counter() if toolCommon.debug_timing_enabled() else None

    time_context = target_info.time
    layer_scope = target_info.layer_scope or animation.layer_cache.tool_context()
    layer_context = layer_scope["context"]
    scene_layers = layer_scope["scene_layers"]
    if (
        layer_scope.get("selection_explicit")
        and not layer_scope.get("selected_unlocked")
    ):
        return _locked_layer_message()

    _t_layer_context = time.perf_counter() if toolCommon.debug_timing_enabled() else None

    tint_range = _time_context_tint_range(time_context)
    copied_layer_ids = set(layer_context.get("copy_layer_ids") or [])
    copied_layers = {
        layer_id: dict(metadata)
        for layer_id, metadata in (layer_context.get("layers") or {}).items()
        if layer_id in copied_layer_ids
    }
    for layer_id, metadata in copied_layers.items():
        layer_name = metadata.get("name")
        if layer_id == animation.BASE_LAYER_ID or not layer_name:
            continue
        metadata["weight"] = _query_anim_layer_weight_data(
            layer_name,
            time_context,
            selected_keyframes=target_info.selected_keys,
        )
        # Animation Layers' group/color are private node attributes that
        # this generic layer-metadata dict (AnimationLayer.as_dict()) never
        # carried -- read them straight from the scene here, the same way
        # `weight` just above is bolted on after the fact, so a copied
        # group's grouping and color survive the round trip to paste()
        # instead of coming back as an ordinary ungrouped layer.
        is_group = animation_layers_controller.is_group(layer_name)
        metadata["is_group"] = is_group
        metadata["color"] = animation_layers_controller.get_group_color(layer_name) if is_group else None

    if toolCommon.debug_timing_enabled():
        _t_weights = time.perf_counter()
        toolCommon.debug_timing_log(
            "copy_animation.setup ({} objects, {} layers)".format(
                len(selected_objects), len(copied_layers)
            ),
            resolve_tool_context=(_t_resolve - _t0) * 1000,
            capture_context=(_t_layer_context - _t_resolve) * 1000,
            weight_queries=(_t_weights - _t_layer_context) * 1000,
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
    if target_info.source in (
        "channel_box",
        "graph_editor",
        "graph_editor_outliner",
    ):
        for plug in target_plugs:
            if "." not in plug:
                continue
            control, channel = plug.rsplit(".", 1)
            explicit_plugs.setdefault(control, []).append(channel)
    _t_before_channels = time.perf_counter() if toolCommon.debug_timing_enabled() else None
    channels_by_control = {
        control: list(
            dict.fromkeys(explicit_plugs.get(control) or get_animation_channels(control))
        )
        for control in selected_objects
    }
    channel_total = sum(len(channels) for channels in channels_by_control.values())
    if toolCommon.debug_timing_enabled():
        toolCommon.debug_timing_log(
            "copy_animation.channel_enum ({} channels)".format(channel_total),
            enumerate_channels=(time.perf_counter() - _t_before_channels) * 1000,
        )

    try:
        processor = configure_copy_paste_operation(
            "copy_animation", "Animation Copied", tint="range", timerange=tint_range,
            progress_max=channel_total,
        ).set_status("Copying Animation")

        def _query_channel(plug):
            channel_data = _query_layered_anim_channel_data(
                plug,
                time_context,
                layer_context=layer_context,
                selected_curves=target_info.curves,
                selected_keyframes=target_info.selected_keys,
                scene_layers=scene_layers,
            )
            if channel_data.get(ANIMATION_FRAME_KEY) or channel_data.get(ANIMATION_LAYERS_KEY):
                return channel_data
            if time_context.mode != "graph_editor_keys":
                return _query_static_channel_value(plug)
            return {}

        channel_items = [
            (control, channel)
            for control in selected_objects
            for channel in channels_by_control[control]
        ]
        for control in selected_objects:
            controls_data[control] = {}

        def _copy_channel_batch(item_batch):
            for control, channel in item_batch:
                plug = f"{control}.{channel}"
                channel_data = _query_channel(plug)
                if channel_data:
                    controls_data[control][channel] = channel_data

        processor.process(
            channel_items,
            _copy_channel_batch,
            batch_size=ANIMATION_CHANNEL_BATCH_SIZE,
            strategy="worker",
        )
        if processor.cancelled:
            return

        animation_data[ANIMATION_CONTROLS_KEY] = {
            control: channels
            for control, channels in controls_data.items()
            if channels
        }
        if not animation_data[ANIMATION_CONTROLS_KEY]:
            return _result_message("animation", "copy")

        if time_context.mode == "time_slider_range":
            timelineWidgets.clear_selected_range()
        elif time_context.mode not in ("all_animation", "graph_editor_keys"):
            tint_range = _animation_data_timerange(animation_data)

        animation_data[ANIMATION_META_KEY]["range"] = list(tint_range) if tint_range else None
        clipboard.save("animation", animation_data)
        processor.succeed("Animation Copied", timerange=tint_range)
    except Exception:
        return wutil.make_inViewMessage("Animation could not be copied")


# PASTE ANIMATION ___________________________________________________________________________


def paste_animation(*args, anchor_widget=None, **kwargs):
    selected_objects = animation.resolve_context(
        default_mode="all_animation", include_channels=True
    ).objects

    animation_data = _load_clipboard_data("animation", "animation")
    if not animation_data:
        return

    targets = [
        source for source, _target in
        _animation_target_mappings(animation_data, selected_objects)
    ]
    paste_range = _animation_data_timerange(animation_data)
    key_count = _animation_data_apply_count(animation_data, targets=targets)
    prompt_range = None
    processor = configure_copy_paste_operation(
        "paste_animation", "Animation Pasted", tint="range",
        timerange=paste_range, progress_max=key_count,
    ).set_status("Pasting Animation")
    keys_set, pasted_targets = _apply_animation_data(animation_data, selected_objects, replace=True, progress=processor)
    if keys_set:
        processor.succeed("Animation Pasted", timerange=paste_range)
        _select_existing_targets(pasted_targets)
        _refresh_animation_view(pasted_targets)
        prompt_range = paste_range
    else:
        _result_message("animation", "paste")
    _maybe_apply_paste_range(prompt_range, anchor_widget=anchor_widget)


# PASTE INSERT _________________________________________________________________________


def paste_insert_animation(*args, anchor_widget=None, **kwargs):
    target_info = animation.resolve_context(
        default_mode="all_animation", include_channels=True
    )
    selected_objects = target_info.objects
    current_time = target_info.selection_snapshot.current_time

    animation_data = _load_clipboard_data("animation", "animation")
    if not animation_data:
        return

    targets = [
        source for source, _target in
        _animation_target_mappings(animation_data, selected_objects)
    ]
    source_range = _animation_data_timerange(animation_data)
    first_source_frame = source_range[0] if source_range else current_time
    paste_range = _shift_timerange(source_range, current_time - first_source_frame)
    key_count = _animation_data_apply_count(animation_data, targets=targets)
    prompt_range = None
    processor = configure_copy_paste_operation(
        "paste_insert_animation", "Animation Pasted", tint="range",
        timerange=paste_range, progress_max=key_count,
    ).set_status("Pasting Animation")
    keys_set, pasted_targets = _apply_animation_data(animation_data, selected_objects, insert_time=current_time, progress=processor)
    if keys_set:
        processor.succeed("Animation Pasted", timerange=paste_range)
        _select_existing_targets(pasted_targets)
        _refresh_animation_view(pasted_targets)
        prompt_range = paste_range
    else:
        _result_message("animation", "paste")
    _maybe_apply_paste_range(prompt_range, anchor_widget=anchor_widget)


# PASTE OPPOSITE ________________________________________________________________________


def paste_opposite_animation(*args, anchor_widget=None, **kwargs):
    from TheKeyMachine.tools.mirror import controller as mirror_controller

    animation_data = _load_clipboard_data("animation", "animation")
    if not animation_data:
        return

    paste_range = _animation_data_timerange(animation_data)
    controls = _animation_controls(animation_data)
    scene_nodes = cmds.ls() or []
    scene_nodes_by_leaf = {
        node.rsplit("|", 1)[-1]: node for node in scene_nodes
    }
    matched_sources = [
        control_name
        for control_name in controls
        if scene_nodes_by_leaf.get(control_name)
        and mirror_controller.find_opposite_name(scene_nodes_by_leaf[control_name])
    ]
    key_count = _animation_data_apply_count(
        animation_data, targets=matched_sources
    )
    prompt_range = None
    processor = configure_copy_paste_operation(
        "paste_opposite_animation", "Animation Pasted", tint="range",
        timerange=paste_range, progress_max=key_count,
    ).set_status("Pasting Opposite Animation")
    channels_by_target = {}
    for control_name, anim_data in controls.items():
        if processor.cancelled:
            break
        source_control = scene_nodes_by_leaf.get(control_name)
        full_mirror_control_name = (
            mirror_controller.find_opposite_name(source_control)
            if source_control else None
        )

        if full_mirror_control_name:

            mirrored_channels = {}
            for channel, channel_data in anim_data.items():
                mirrored_channels[channel] = _transform_channel_values(
                    channel_data,
                    lambda value, attr=channel: mirror_controller.apply_exception(
                        source_control, attr, value, target=full_mirror_control_name,
                        use_defaults=False,
                    ),
                )
            channels_by_target[full_mirror_control_name] = mirrored_channels

    pasted_targets = set()
    keys_set = _apply_animation_channels_to_targets(
        list(channels_by_target),
        replace=True,
        progress=processor,
        layer_metadata=(
            (animation_data.get(ANIMATION_META_KEY) or {}).get(
                ANIMATION_LAYER_META_KEY
            )
            or {}
        ),
        channels_by_target=channels_by_target,
        applied_targets=pasted_targets,
    )

    if keys_set:
        processor.succeed("Animation Pasted", timerange=paste_range)
        _select_existing_targets(sorted(pasted_targets))
        _refresh_animation_view(pasted_targets)
        prompt_range = paste_range
    else:
        _result_message("animation", "paste")
    _maybe_apply_paste_range(prompt_range, anchor_widget=anchor_widget)


def paste_animation_to(*_args, anchor_widget=None, **_kwargs):
    try:
        animation_data = _load_clipboard_data("animation", "animation")
    except Exception:
        return wutil.make_inViewMessage("Animation data could not be read")
    if animation_data is None:
        return

    if not _is_animation_payload(animation_data):
        return wutil.make_inViewMessage("Animation file is empty or invalid")

    _paste_to_dialog = copy_paste_widgets.PasteToDialog(
        _animation_controls(animation_data),
        "paste_animation_to_apply",
        animation_data,
        data_label="animation",
        parent=anchor_widget,
    )
    _paste_to_dialog.show()


def paste_animation_to_apply(animation_data, mappings, insert=False, anchor_widget=None, tool_operation=None):
    processor = toolCommon.require_tool_operation(tool_operation)
    snapshot = animation.current_selection_snapshot()
    current_time = snapshot.current_time if insert else None
    source_range = _animation_data_timerange(animation_data)
    first_source_frame = source_range[0] if source_range else current_time
    paste_range = _shift_timerange(source_range, current_time - first_source_frame) if insert else source_range
    controls = _animation_controls(animation_data)
    layer_metadata = (
        (animation_data.get(ANIMATION_META_KEY) or {}).get(ANIMATION_LAYER_META_KEY)
        or {}
    )
    processor.set_total(sum(
        _animation_channels_apply_count(controls.get(source_node, {}), layer_metadata=layer_metadata)
        for source_node, _target_node in mappings
    )).set_status("Pasting Animation")
    toolCommon.ensure_operation_tint(
        processor, tint="range", timerange=paste_range,
        tint_key="paste_animation_to_apply",
    )
    channels_by_target = {
        target_node: controls[source_node]
        for source_node, target_node in mappings
        if controls.get(source_node)
    }
    pasted_targets = set()
    total_keys_set = _apply_animation_channels_to_targets(
        list(channels_by_target), replace=not insert,
        insert_time=current_time if insert else None, replace_range=(0, 1e6),
        progress=processor, layer_metadata=layer_metadata,
        channels_by_target=channels_by_target, applied_targets=pasted_targets,
    )
    if not total_keys_set:
        _result_message("animation", "paste")
        return False
    processor.succeed(
        "Animation Pasted", timerange=paste_range or source_range
    )
    _select_existing_targets(sorted(pasted_targets))
    _refresh_animation_view(pasted_targets)
    _maybe_apply_paste_range(processor.timerange, anchor_widget=anchor_widget)
    return True


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
    pose_data = _load_clipboard_data("pose", "pose")
    if not pose_data:
        return
    controls = _pose_controls(pose_data)

    _paste_to_dialog = copy_paste_widgets.PasteToDialog(
        controls,
        "paste_pose_to_apply",
        pose_data,
        data_label="pose",
        parent=anchor_widget,
    )
    _paste_to_dialog.show()


def paste_pose_to_apply(pose_data, mappings, insert=False, tool_operation=None):
    processor = toolCommon.require_tool_operation(tool_operation)
    controls = _pose_controls(pose_data)
    processor.set_total(sum(
        len(controls.get(source_node) or {})
        for source_node, _target_node in mappings
    )).set_status("Pasting Pose")
    toolCommon.ensure_operation_tint(
        processor, tint="current", default_mode="current_frame",
        tint_key="paste_pose_to_apply",
    )
    attrs_set, pasted_targets = _apply_pose_data(
        pose_data,
        [target_node for _source_node, target_node in mappings],
        progress=processor,
        mappings=mappings,
    )
    if not attrs_set:
        _result_message("pose", "paste")
        return False
    processor.succeed("Pose Pasted")
    _select_existing_targets(pasted_targets)
    return True


# COPY POSE ________________________________________________________________________


def copy_pose(*args, **kwargs):
    target_info = animation.resolve_context(
        default_mode="current_frame",
        include_channels=True,
    )
    selected_objects = target_info.objects

    if not selected_objects:
        return wutil.make_inViewMessage("Select an object")

    layer_context = target_info.layer_scope["context"]
    pose_data = {}
    if target_info.source == "channel_box":
        attributes_by_control = {control: [] for control in selected_objects}
        for plug in target_info.plugs:
            if plug and "." in plug:
                control, attr = plug.rsplit(".", 1)
                attributes_by_control.setdefault(control, []).append(attr)
    else:
        attributes_by_control = {
            control: cmds.listAttr(control, keyable=True, unlocked=True) or []
            for control in selected_objects
        }
    attribute_total = sum(len(attrs) for attrs in attributes_by_control.values())

    processor = configure_copy_paste_operation(
        "copy_pose",
        "Pose Copied",
        tint="current",
        progress_max=attribute_total,
    ).set_status("Copying Pose")

    def _read_pose_attr(control, attr):
        try:
            return True, cmds.getAttr(f"{control}.{attr}")
        except Exception as e:
            import TheKeyMachine.tools.bug_report.controller as report

            report.report_detected_exception(e, context="copy pose attribute read")
            return False, None

    attribute_items = [
        (control, attr)
        for control in selected_objects
        for attr in attributes_by_control[control]
    ]
    for control in selected_objects:
        pose_data[control] = {}

    def _copy_attribute_batch(item_batch):
        for control, attr in item_batch:
            ok, values = _read_pose_attr(control, attr)
            if ok:
                pose_data[control][attr] = values

    processor.process(
        attribute_items,
        _copy_attribute_batch,
        batch_size=POSE_ATTRIBUTE_BATCH_SIZE,
        strategy="worker",
    )
    if processor.cancelled:
        return

    pose_data = {
        control: attributes
        for control, attributes in pose_data.items()
        if attributes
    }
    if not pose_data:
        return _result_message("pose", "copy")
    clipboard.save(
        "pose",
        {
            POSE_META_KEY: {
                "type": "pose",
                "version": POSE_SCHEMA_VERSION,
                "layer_context": layer_context,
            },
            POSE_CONTROLS_KEY: pose_data,
        },
    )
    processor.succeed("Pose Copied")


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
    target_info = animation.resolve_context(
        default_mode="current_frame",
        include_channels=True,
    )
    selected_objects = target_info.objects

    pose_data = _load_clipboard_data("pose", "pose")
    if not pose_data:
        return

    controls = _pose_controls(pose_data)
    mappings = _pose_target_mappings(pose_data, selected_objects)
    allowed_target_attributes = None
    if target_info.source == "channel_box":
        allowed_target_attributes = {}
        for plug in target_info.plugs:
            if plug and "." in plug:
                control, attr = plug.rsplit(".", 1)
                allowed_target_attributes.setdefault(control, set()).add(attr)
    attribute_total = sum(
        len(controls[source])
        if allowed_target_attributes is None
        else len(
            set(controls[source]).intersection(
                allowed_target_attributes.get(target) or set()
            )
        )
        for source, target in mappings
    )
    processor = configure_copy_paste_operation(
        "paste_pose",
        "Pose Pasted",
        tint="current",
        progress_max=attribute_total,
    ).set_status("Pasting Pose")
    attrs_set, pasted_targets = _apply_pose_data(
        pose_data,
        selected_objects,
        progress=processor,
        mappings=mappings,
        allowed_target_attributes=allowed_target_attributes,
    )
    if attrs_set:
        processor.succeed("Pose Pasted")
        _select_existing_targets(pasted_targets)
    else:
        _result_message("pose", "paste")


def paste_mirror_pose(*args, **kwargs):
    """Paste copied pose values onto opposite controls using mirror exceptions."""
    from TheKeyMachine.tools.mirror import controller as mirror_controller

    pose_data = _load_clipboard_data("pose", "pose")
    if not pose_data:
        return

    controls = _pose_controls(pose_data)
    attribute_total = sum(len(attributes) for attributes in controls.values())
    processor = configure_copy_paste_operation(
        "paste_mirror_pose",
        "Pose Pasted",
        tint="current",
        progress_max=attribute_total,
    ).set_status("Pasting Mirror Pose")
    scene_nodes = {
        node.rsplit("|", 1)[-1]: node for node in (cmds.ls() or [])
    }
    mirrored_controls = {}
    mappings = []
    for control_name, attributes in controls.items():
        source_control = scene_nodes.get(control_name)
        mirror_control = (
            mirror_controller.find_opposite_name(source_control)
            if source_control else None
        )
        if not mirror_control:
            if attributes:
                processor.step(amount=len(attributes))
            continue
        mirrored_controls[control_name] = {}
        mappings.append((control_name, mirror_control))
        for attr, value in attributes.items():
            if processor.cancelled:
                return
            mirrored_controls[control_name][attr] = (
                mirror_controller.apply_exception(
                    source_control, attr, value, target=mirror_control
                )
            )

    mirrored_payload = {
        POSE_META_KEY: dict(pose_data.get(POSE_META_KEY) or {}),
        POSE_CONTROLS_KEY: mirrored_controls,
    }
    attrs_set, pasted_targets = _apply_pose_data(
        mirrored_payload,
        [],
        progress=processor,
        mappings=mappings,
    )

    if attrs_set:
        processor.succeed("Pose Pasted")
        _select_existing_targets(pasted_targets)
    else:
        _result_message("pose", "paste")
