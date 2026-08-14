from maya import cmds

from TheKeyMachine.maya import animation
from TheKeyMachine.maya import maya_api
from TheKeyMachine.tools import registry
from TheKeyMachine.maya import selection
from TheKeyMachine.tools import clipboard
from TheKeyMachine.tools import common as toolCommon
import TheKeyMachine.ui.widgets.timeline as timelineWidgets
import TheKeyMachine.ui.widgets.util as wutil


WORLDSPACE_CLIPBOARD = "worldspace"


def _world_matrix(node, frame=None):
    return maya_api.world_matrix_at_time(node, frame)


def _apply_worldspace_values(node, values):
    if not values or len(values) != 16:
        return False
    cmds.xform(node, matrix=values, worldSpace=True)
    return True


def _copy_worldspace_frames(selected_objects, frames, timerange, tool_id, label):
    animation_data = {}
    frames = tuple(dict.fromkeys(frames or ()))
    if not frames:
        return

    with toolCommon.tool_operation(
        tool_id=tool_id,
        label=label,
        progress=True,
        progress_max=len(frames),
        tint="range",
        timerange=timerange,
        tint_color=registry.get_tool_tint_color(tool_id),
        undo=False,
        suspend_refresh=True,
    ) as operation:
        def _collect_frame(frame):
            for source_obj in selected_objects:
                worldspace_values = _world_matrix(source_obj, frame)
                if worldspace_values is None:
                    continue
                animation_data.setdefault(source_obj, {})[int(frame)] = worldspace_values

        def _collect_all():
            for frame in frames:
                if operation.cancelled:
                    break
                operation.run_on_main(_collect_frame, frame)
                operation.step()

        # Off the main thread so a Cancel press actually gets a chance to
        # register while this samples potentially many frames' worth of
        # world matrices -- a tight loop of OpenMaya calls on the main
        # thread never gives Qt a chance to notice one. See
        # attribute_switcher's controller for the same pattern applied
        # first, and tools/common.py's run_on_worker_thread/
        # ToolOperation.run_on_main for the mechanics.
        toolCommon.run_on_worker_thread(_collect_all)

        payload = {
            "meta": {
                "ordered_objects": selected_objects,
                "layer_context": animation.layer_cache.capture(),
            },
            "data": animation_data,
        }
        clipboard.save(WORLDSPACE_CLIPBOARD, payload)
        operation.success = True


def _worldspace_copy(default_mode, tool_id, label):
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
        )
    finally:
        if selected_range:
            timelineWidgets.clear_selected_range()


def worldspace_copy_frame(*args):
    """Copy world-space transforms. Copies the current frame when nothing
    is selected, or the selected time-slider range / graph editor keys."""
    return _worldspace_copy("current_frame", "ws_copy_frame", "World Space copied")


def worldspace_copy_animation(*args):
    """Copy world-space animation. Copies the visible playback range when
    nothing is selected, or the selected time-slider range / graph editor keys."""
    return _worldspace_copy("all_animation", "ws_copy_range", "World Space animation copied")


def paste_worldspace_single_frame(*args):
    # frame_range (needed for the tint) isn't known until the clipboard
    # payload is loaded and inspected below, so -- like every other
    # timerange-dependent tint in this codebase -- it's requested via
    # ensure_operation_tint() once it's known, rather than passed to
    # tool_operation() up front. tool_operation()'s own teardown finishes
    # whatever tint_session ends up on the operation, on every exit path
    # (early return, cancel, or exception), so there's nothing to track
    # or finish by hand here.
    with toolCommon.tool_operation(
        tool_id="ws_paste_frame",
        label="Paste World Space Frame",
        progress=False,
        undo=True,
        rollback_on_cancel=True,
    ) as operation:
        # Load from clipboard
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

        target_objects = list(
            dict.fromkeys(
                selection.get_selected_objects(ordered=True)
            )
        )

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

            def _paste_single():
                for obj in target_objects:
                    if operation.cancelled:
                        return
                    operation.run_on_main(_paste_to_target, obj, values)
                    operation.step()

            toolCommon.run_on_worker_thread(_paste_single)
            return

        # Multi-source: paste in order (source[0]->target[0], ...). Returns
        # a message string if a target ran out of source data mid-loop, so
        # the caller (still on the main thread once the worker returns) can
        # surface it -- wutil.make_inViewMessage is a Qt call and can't be
        # made directly from the worker thread this now runs on.
        def _paste_multi():
            for idx, target_obj in enumerate(target_objects):
                if operation.cancelled:
                    return None
                source_obj = ordered_sources[idx]
                values = _first_frame_values(source_obj)
                if not values:
                    return "No World Space data found"
                operation.run_on_main(_paste_to_target, target_obj, values)
                operation.step()
            return None

        message = toolCommon.run_on_worker_thread(_paste_multi)
        if message:
            return wutil.make_inViewMessage(message)


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


def worldspace_paste_animation(*args):
    original_time = cmds.currentTime(query=True)
    created_layers = {}
    try:
        with toolCommon.tool_operation(
            tool_id="ws_paste",
            label="Paste World Space Animation",
            progress=True,
            progress_max=1,
            undo=True,
            suspend_refresh=True,
            rollback_on_cancel=True,
        ) as operation:
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

            target_objects = list(
                dict.fromkeys(
                    selection.get_selected_objects(ordered=True)
                )
            )

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

            operation.timerange = paste_range
            operation.tint_session = timelineWidgets.begin_timeline_tint(
                timerange=paste_range,
                color=registry.get_tool_tint_color("ws_paste"),
                key="ws_paste",
            )

            operation.set_total(len(all_frames), reset=True)

            def _paste_frame(frame):
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

            def _paste_all_frames():
                for frame in all_frames:
                    if operation.cancelled:
                        break
                    operation.run_on_main(_paste_frame, frame)
                    operation.step()

            # Off the main thread so a Cancel press actually gets a chance
            # to register while this scrubs through potentially many
            # frames -- see _copy_worldspace_frames above and
            # attribute_switcher's controller for the same pattern.
            toolCommon.run_on_worker_thread(_paste_all_frames)

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
            
            operation.success = True

    finally:
        animation.restore_created_layer_states(created_layers)
        cmds.currentTime(original_time)
