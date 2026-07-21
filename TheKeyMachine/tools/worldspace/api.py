from maya import cmds

from TheKeyMachine.core import openMayaUtils as open_maya
import TheKeyMachine.core.toolbox as toolbox
import TheKeyMachine.mods.selectionMod as selectionMod
from TheKeyMachine.tools import clipboard
from TheKeyMachine.tools import common as toolCommon
import TheKeyMachine.widgets.timeline as timelineWidgets
import TheKeyMachine.widgets.util as wutil


WORLDSPACE_CLIPBOARD = "worldspace"


def _world_matrix(node, frame=None):
    return open_maya.world_matrix_at_time(node, frame)


def _apply_worldspace_values(node, values):
    if not values:
        return False
    if len(values) == 16:
        cmds.xform(node, matrix=values, worldSpace=True)
    else:
        # Backwards compatibility with six-value worldspace clipboards.
        cmds.xform(node, translation=values[:3], worldSpace=True)
        cmds.xform(node, rotation=values[3:6], worldSpace=True)
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
        tint_color=toolbox.get_tool_tint_color(tool_id),
        undo=False,
        suspend_refresh=True,
    ) as operation:
        for frame in frames:
            if operation.cancelled:
                break

            for source_obj in selected_objects:
                worldspace_values = _world_matrix(source_obj, frame)
                if worldspace_values is None:
                    continue
                animation_data.setdefault(source_obj, {})[int(frame)] = worldspace_values
            operation.step()

        payload = {
            "meta": {"ordered_objects": selected_objects},
            "data": animation_data,
        }
        clipboard.save(WORLDSPACE_CLIPBOARD, payload)
        operation.success = True


def worldspace_copy_animation(*args):
    selected_objects = selectionMod.get_selected_objects(
        orderedSelection=True,
    )
    if not selected_objects:
        return

    selected_range = selectionMod.get_selected_time_slider_range()
    timerange = selected_range or timelineWidgets.get_playback_range()
    frames = range(int(timerange[0]), int(timerange[1]) + 1)
    try:
        return _copy_worldspace_frames(
            selected_objects,
            frames,
            timerange,
            "ws_copy_range",
            "World Space animation copied",
        )
    finally:
        if selected_range:
            timelineWidgets.clear_time_slider_selection()


def paste_worldspace_single_frame(*args):
    operation_manager = None
    operation_context = None
    tint_session = None
    try:
        operation_manager = toolCommon.tool_operation(
            tool_id="ws_paste_frame",
            label="Paste World Space Frame",
            progress=False,
            undo=True,
        )
        operation_context = operation_manager.__enter__()

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
            tint_session = timelineWidgets.begin_timeline_tint(
                timerange=frame_range,
                color=toolbox.get_tool_tint_color("ws_paste_frame"),
                key="ws_paste_frame",
            )

        target_objects = list(
            dict.fromkeys(
                selectionMod.get_selected_objects(orderedSelection=True)
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

        operation_context.set_total(len(target_objects))

        def _first_frame_values(obj_name):
            obj_data = animation_data.get(obj_name) or {}
            if not isinstance(obj_data, dict) or not obj_data:
                return None
            first_frame = next(iter(obj_data))
            return obj_data[first_frame]

        # Single-source: paste to any selection size (same transform for all targets)
        if source_count == 1:
            values = _first_frame_values(ordered_sources[0])
            if not values:
                return wutil.make_inViewMessage("No World Space data found")
            for obj in target_objects:
                if operation_context.cancelled:
                    return
                if cmds.objExists(obj):
                    _apply_worldspace_values(obj, values)
                operation_context.step()
            return

        # Multi-source: paste in order (source[0]->target[0], ...)
        for idx, target_obj in enumerate(target_objects):
            if operation_context.cancelled:
                return
            source_obj = ordered_sources[idx]
            values = _first_frame_values(source_obj)
            if not values:
                return wutil.make_inViewMessage("No World Space data found")
            if cmds.objExists(target_obj):
                _apply_worldspace_values(target_obj, values)
            operation_context.step()

        return

    finally:
        if tint_session:
            tint_session.finish()
        if operation_manager and operation_context is not None:
            try:
                operation_manager.__exit__(None, None, None)
            except Exception:
                pass


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
    try:
        with toolCommon.tool_operation(
            tool_id="ws_paste",
            label="Paste World Space Animation",
            progress=True,
            progress_max=1,
            undo=True,
            suspend_refresh=True,
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
                    selectionMod.get_selected_objects(orderedSelection=True)
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
            if valid_targets:
                cmds.cutKey(
                    valid_targets,
                    attribute=["tx", "ty", "tz", "rx", "ry", "rz"],
                    time=paste_range,
                )

            operation.timerange = paste_range
            operation.tint_session = timelineWidgets.begin_timeline_tint(
                timerange=paste_range,
                color=toolbox.get_tool_tint_color("ws_paste"),
                key="ws_paste",
            )

            operation.set_total(len(all_frames), reset=True)

            for frame in all_frames:
                if operation.cancelled:
                    break

                cmds.currentTime(frame)
                keyed_targets = []
                for source_obj, target_obj in mapping:
                    if not cmds.objExists(target_obj):
                        continue
                    values = (mapped_frame_values.get(source_obj) or {}).get(frame)
                    if values is None:
                        continue
                    if _apply_worldspace_values(target_obj, values):
                        keyed_targets.append(target_obj)
                if keyed_targets:
                    cmds.setKeyframe(
                        keyed_targets,
                        time=(frame,),
                        attribute=["tx", "ty", "tz", "rx", "ry", "rz"],
                    )
                operation.step()

            if valid_targets:
                cmds.filterCurve(valid_targets)
            
            operation.success = True

    finally:
        cmds.currentTime(original_time)
