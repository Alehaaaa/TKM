from maya import cmds

from TheKeyMachine.maya import animation
from TheKeyMachine.maya import maya_api
from TheKeyMachine.tools import registry
from TheKeyMachine.tools import clipboard
from TheKeyMachine.tools import common as toolCommon
import TheKeyMachine.ui.widgets.timeline as timelineWidgets
import TheKeyMachine.ui.widgets.util as wutil


WORLDSPACE_CLIPBOARD = "worldspace"
WORLDSPACE_FRAME_BATCH_SIZE = 8
WORLDSPACE_TARGET_BATCH_SIZE = 16


def _world_matrix(node, frame=None):
    return maya_api.world_matrix_at_time(node, frame)


def _apply_worldspace_values(node, values):
    if not values or len(values) != 16:
        return False
    cmds.xform(node, matrix=values, worldSpace=True)
    return True


def _copy_worldspace_frames(selected_objects, frames, timerange, tool_id, label, operation):
    animation_data = {}
    frames = tuple(dict.fromkeys(frames or ()))
    if not frames:
        return

    operation.set_status(label)
    toolCommon.ensure_operation_tint(
        operation,
        tint="range",
        timerange=timerange,
        tint_color=registry.get_tool_tint_color(tool_id),
        tint_key=tool_id,
    )

    def _collect_frames(frame_batch):
        for frame in frame_batch:
            for source_obj in selected_objects:
                worldspace_values = _world_matrix(source_obj, frame)
                if worldspace_values is None:
                    continue
                animation_data.setdefault(source_obj, {})[int(frame)] = worldspace_values

    operation.process(
        frames,
        _collect_frames,
        batch_size=WORLDSPACE_FRAME_BATCH_SIZE,
        strategy="worker",
    )

    payload = {
        "meta": {
            "ordered_objects": selected_objects,
            "layer_context": animation.layer_cache.capture(),
        },
        "data": animation_data,
    }
    clipboard.save(WORLDSPACE_CLIPBOARD, payload)
    operation.succeed()


def _worldspace_copy(default_mode, tool_id, label, tool_operation=None):
    operation = toolCommon.require_tool_operation(tool_operation)
    target_info = animation.resolve_context(
        default_mode=default_mode,
        include_channels=True,
    )
    selected_objects = list(dict.fromkeys(target_info.objects or []))
    if not selected_objects:
        return

    time_context = target_info.time
    selected_range = (
        time_context.timerange
        if time_context.mode == "time_slider_range"
        else None
    )
    if time_context.mode == "graph_editor_keys":
        frames = list(dict.fromkeys(time_context.frames))
        timerange = (
            (min(frames), max(frames)) if frames else time_context.timerange
        )
    elif time_context.mode == "current_frame":
        frames = list(time_context.frames)
        timerange = time_context.timerange
    else:
        timerange = selected_range or timelineWidgets.get_playback_range()
        frames = range(int(timerange[0]), int(timerange[1]) + 1)
    try:
        return _copy_worldspace_frames(
            selected_objects,
            frames,
            timerange,
            tool_id,
            label,
            operation,
        )
    finally:
        if selected_range:
            timelineWidgets.clear_selected_range()


def worldspace_copy_frame(*args, tool_operation=None, **_kwargs):
    """Copy world-space transforms. Copies the current frame when nothing
    is selected, or the selected time-slider range / graph editor keys."""
    return _worldspace_copy(
        "current_frame", "copy_worldspace", "World Space copied", tool_operation
    )


def worldspace_copy_animation(*args, tool_operation=None, **_kwargs):
    """Copy world-space animation. Copies the visible playback range when
    nothing is selected, or the selected time-slider range / graph editor keys."""
    return _worldspace_copy(
        "all_animation", "ws_copy_range", "World Space animation copied", tool_operation
    )


def paste_worldspace_single_frame(*args, tool_operation=None, **_kwargs):
    operation = toolCommon.require_tool_operation(tool_operation)
    # The copied range is only known after loading the payload; attach it to
    # the already-open dispatcher operation once resolved.
    payload = clipboard.load(
        WORLDSPACE_CLIPBOARD,
        "No World Space data found. Please copy first.",
    )
    if payload is None:
        return

    selection_mismatch_message = "Selection missmatched to paste worldspace"

    if isinstance(payload, dict) and "data" in payload:
        animation_data = payload.get("data") or {}
        ordered_sources = (payload.get("meta") or {}).get("ordered_objects") or list(animation_data.keys())
    else:
        animation_data = payload or {}
        ordered_sources = list(animation_data.keys())

    ordered_sources = list(
        dict.fromkeys(
            obj for obj in ordered_sources if obj in animation_data
        )
    )
    if not ordered_sources:
        return wutil.make_inViewMessage("No World Space data found")

    copied_frames = [
        frame
        for obj_name in ordered_sources
        for frame_key in (animation_data.get(obj_name) or {})
        for frame in (_worldspace_frame_number(frame_key),)
        if frame is not None
    ]
    frame_range = (
        (min(copied_frames), max(copied_frames))
        if copied_frames
        else None
    )
    if frame_range:
        toolCommon.ensure_operation_tint(
            operation,
            tint="range",
            timerange=frame_range,
            tint_key="ws_paste_frame",
            tint_color=registry.get_tool_tint_color("ws_paste_frame"),
        )

    target_objects = list(animation.current_selection_snapshot().objects)

    # No selection: paste back to the originally copied objects (if they still exist)
    if not target_objects:
        target_objects = ordered_sources
        missing = [obj for obj in target_objects if not cmds.objExists(obj)]
        if missing:
            return wutil.make_inViewMessage(selection_mismatch_message)

    source_count = len(ordered_sources)
    target_count = len(target_objects)

    # Multi-source pastes require matching selection size
    if source_count > 1 and target_count != source_count:
        return wutil.make_inViewMessage(selection_mismatch_message)

    operation.set_total(len(target_objects))

    def _first_frame_values(obj_name):
        obj_data = animation_data.get(obj_name) or {}
        if not isinstance(obj_data, dict) or not obj_data:
            return None
        first_frame = next(iter(obj_data))
        return obj_data[first_frame]

    def _paste_to_target(obj, values):
        if cmds.objExists(obj):
            _apply_worldspace_values(obj, values)

    # Single-source: paste to any selection size (same transform for all targets)
    if source_count == 1:
        values = _first_frame_values(ordered_sources[0])
        if not values:
            return wutil.make_inViewMessage("No World Space data found")

        def _paste_targets(target_batch):
            for obj in target_batch:
                _paste_to_target(obj, values)

        operation.process(
            target_objects,
            _paste_targets,
            batch_size=WORLDSPACE_TARGET_BATCH_SIZE,
            strategy="worker",
        )
        return

    # Multi-source: paste in order (source[0]->target[0], ...). Returns
    # a message string if a target ran out of source data mid-loop, so
    # the caller (still on the main thread once the worker returns) can
    # surface it -- wutil.make_inViewMessage is a Qt call and can't be
    # made directly from the worker thread this now runs on.
    paste_items = []
    for source_obj, target_obj in zip(ordered_sources, target_objects):
        values = _first_frame_values(source_obj)
        if not values:
            return wutil.make_inViewMessage("No World Space data found")
        paste_items.append((target_obj, values))

    def _paste_pairs(pair_batch):
        for target_obj, values in pair_batch:
            _paste_to_target(target_obj, values)

    operation.process(
        paste_items,
        _paste_pairs,
        batch_size=WORLDSPACE_TARGET_BATCH_SIZE,
        strategy="worker",
    )


def _worldspace_frame_number(frame_key):
    try:
        return int(round(float(frame_key)))
    except Exception:
        return None


def _worldspace_frame_value_map(obj_data):
    values_by_frame = {}
    if not isinstance(obj_data, dict):
        return values_by_frame
    for frame_key, values in obj_data.items():
        frame = _worldspace_frame_number(frame_key)
        if frame is not None:
            values_by_frame[frame] = values
    return values_by_frame


def worldspace_paste_animation(*args, tool_operation=None, **_kwargs):
    operation = toolCommon.require_tool_operation(tool_operation)
    original_time = cmds.currentTime(query=True)
    created_layers = {}
    try:
        payload = clipboard.load(
            WORLDSPACE_CLIPBOARD,
            "No World Space animation data found. Please copy first.",
        )
        if payload is None:
            return

        selection_mismatch_message = "Selection missmatched to paste worldspace"

        if isinstance(payload, dict) and "data" in payload:
            animation_data = payload.get("data") or {}
            ordered_sources = (payload.get("meta") or {}).get("ordered_objects") or list(animation_data.keys())
        else:
            animation_data = payload or {}
            ordered_sources = list(animation_data.keys())

        ordered_sources = list(
            dict.fromkeys(
                obj for obj in ordered_sources if obj in animation_data
            )
        )
        if not ordered_sources:
            return wutil.make_inViewMessage("No World Space animation data found")

        target_objects = list(animation.current_selection_snapshot().objects)

        # No selection: paste back to the originally copied objects (if they still exist)
        if not target_objects:
            target_objects = ordered_sources
            missing = [obj for obj in target_objects if not cmds.objExists(obj)]
            if missing:
                return wutil.make_inViewMessage(selection_mismatch_message)

        source_count = len(ordered_sources)
        target_count = len(target_objects)

        # Multi-source pastes require matching selection size
        if source_count > 1 and target_count != source_count:
            return wutil.make_inViewMessage(selection_mismatch_message)

        # Map source data -> target objects (preserve order)
        if source_count == 1:
            mapping = [(ordered_sources[0], t) for t in target_objects]
        else:
            mapping = list(zip(ordered_sources, target_objects))

        valid_targets = list(
            dict.fromkeys(
                target_obj
                for _, target_obj in mapping
                if cmds.objExists(target_obj)
            )
        )

        # Frames to paste (union of used sources)
        mapped_frame_values = {}
        frame_set = set()
        for source_obj, _ in mapping:
            values_by_frame = _worldspace_frame_value_map(animation_data.get(source_obj) or {})
            if values_by_frame:
                mapped_frame_values[source_obj] = values_by_frame
                frame_set.update(values_by_frame.keys())

        if not frame_set:
            return wutil.make_inViewMessage("No World Space animation data found")

        all_frames = sorted(frame_set)
        paste_range = (all_frames[0], all_frames[-1])
        key_attributes = ["tx", "ty", "tz", "rx", "ry", "rz"]
        copied_layer_context = (
            (payload.get("meta") or {}).get("layer_context")
            if isinstance(payload, dict)
            else None
        )
        target_plugs = [
            "{}.{}".format(target, attribute)
            for target in valid_targets
            for attribute in key_attributes
        ]
        layer_context, created_layers = animation.LayerContext(
            copied_layer_context or {}
        ).prepare_paste(target_plugs)
        destination_groups = {}
        locked_destination = False
        if valid_targets:
            for target in valid_targets:
                groups, blocked = layer_context.group_by_destination(
                    target, key_attributes
                )
                destination_groups[target] = groups
                locked_destination = locked_destination or bool(blocked)
                blocked = layer_context.cut_keys(
                    target, key_attributes, paste_range
                )
                locked_destination = locked_destination or bool(blocked)
        if locked_destination:
            wutil.make_inViewMessage("Current animation layer is locked")

        toolCommon.ensure_operation_tint(
            operation,
            tint="range",
            timerange=paste_range,
            tint_color=registry.get_tool_tint_color("ws_paste"),
            tint_key="ws_paste",
        )

        def _paste_frames(frame_batch):
            for frame in frame_batch:
                cmds.currentTime(frame)
                for source_obj, target_obj in mapping:
                    if not cmds.objExists(target_obj):
                        continue
                    if not destination_groups.get(target_obj):
                        continue
                    values = (mapped_frame_values.get(source_obj) or {}).get(frame)
                    if values is None:
                        continue
                    if _apply_worldspace_values(target_obj, values):
                        layer_context.set_keyframe(
                            target_obj,
                            key_attributes,
                            time=frame,
                        )

        operation.process(
            all_frames,
            _paste_frames,
            batch_size=WORLDSPACE_FRAME_BATCH_SIZE,
            reset_progress=True,
            strategy="worker",
        )

        if valid_targets:
            curves = []
            for target, groups in destination_groups.items():
                for layer_name, attributes in groups.items():
                    for attribute in attributes:
                        curve = animation.layer_graph.curve_for_plug(
                            "{}.{}".format(target, attribute),
                            layer_name=layer_name,
                        )
                        if curve:
                            curves.append(curve)
            if curves:
                cmds.filterCurve(*list(dict.fromkeys(curves)))

        operation.succeed()

    finally:
        animation.restore_created_layer_states(created_layers)
        cmds.currentTime(original_time)
