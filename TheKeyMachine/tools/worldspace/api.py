from maya import cmds

from TheKeyMachine.core import animation_context
import TheKeyMachine.core.toolbox as toolbox
import TheKeyMachine.mods.selectionMod as selectionMod
from TheKeyMachine.tools import clipboard
from TheKeyMachine.tools import common as toolCommon
import TheKeyMachine.widgets.timeline as timelineWidgets
import TheKeyMachine.widgets.util as wutil


def _active_tint_color(tool_id):
    return toolbox.get_tool_tint_color(tool_id)


def worldspace_copy_animation(*args):
    target_info = animation_context.resolve_targets(default_mode="all_animation", ordered_selection=True, long_names=False)
    selected_objects = target_info["target_objects"]
    if not selected_objects:
        return

    # Comprobar si los objetos seleccionados tienen claves de animación
    if not cmds.keyframe(selected_objects, query=True):
        return

    animation_data = {}

    # Guardar el tiempo actual antes de realizar cambios
    original_time = cmds.currentTime(query=True)

    time_context = target_info["time_context"]
    keyframe_query = {"query": True}
    if time_context.mode != "all_animation":
        keyframe_query["time"] = time_context.timerange

    try:
        all_keyframes = sorted(list(set(cmds.keyframe(selected_objects, **keyframe_query) or [])))
        if not all_keyframes:
            return

        with toolCommon.tool_operation(
            tool_id="worldspace",
            label="World Space animation copied",
            progress=True,
            progress_max=len(all_keyframes),
            tint="range",
            timerange=(int(all_keyframes[0]), int(all_keyframes[-1])),
            undo=False,
            suspend_refresh=True,
        ) as operation:
            for frame in all_keyframes:
                if operation.cancelled:
                    break

                cmds.currentTime(frame)

                for source_obj in selected_objects:
                    # Asegurarse de que el objeto tiene claves en este frame
                    if cmds.keyframe(source_obj, query=True, time=(frame, frame)):
                        worldspace_values = cmds.xform(source_obj, query=True, translation=True, worldSpace=True) + cmds.xform(
                            source_obj, query=True, rotation=True, worldSpace=True
                        )
                        if source_obj not in animation_data:
                            animation_data[source_obj] = {}

                        animation_data[source_obj][int(frame)] = worldspace_values

                operation.step()

            # Save to clipboard
            payload = {
                "meta": {"ordered_objects": selected_objects},
                "data": animation_data,
            }
            clipboard.save("worldspace", payload)
            operation.success = True
    finally:
        # Restaurar el tiempo actual a su estado original
        cmds.currentTime(original_time)


# -------------------- Copy range World Space


def copy_range_worldspace_animation(*args):
    target_info = animation_context.resolve_targets(default_mode="current_frame", ordered_selection=True, long_names=False)
    selected_objects = target_info["target_objects"]
    if not selected_objects:
        return

    time_context = target_info["time_context"]
    if time_context.mode != "time_slider_range":
        return copy_worldspace_single_frame(*args)

    animation_data = {}

    # Guardar el tiempo actual antes de realizar cambios
    original_time = cmds.currentTime(query=True)

    frames_to_copy = list(time_context.frames or [])

    try:
        if not frames_to_copy:
            return

        with toolCommon.tool_operation(
            tool_id="ws_copy_range",
            label="World Space range copied",
            progress=True,
            progress_max=len(frames_to_copy),
            tint="range",
            timerange=(int(frames_to_copy[0]), int(frames_to_copy[-1])),
            undo=False,
            suspend_refresh=True,
        ) as operation:
            for frame in frames_to_copy:
                if operation.cancelled:
                    break

                cmds.currentTime(frame)

                for source_obj in selected_objects:
                    worldspace_values = cmds.xform(source_obj, query=True, translation=True, worldSpace=True) + cmds.xform(
                        source_obj, query=True, rotation=True, worldSpace=True
                    )
                    if source_obj not in animation_data:
                        animation_data[source_obj] = {}

                    animation_data[source_obj][int(frame)] = worldspace_values

                operation.step()

            # Save to clipboard
            payload = {
                "meta": {"ordered_objects": selected_objects},
                "data": animation_data,
            }
            clipboard.save("worldspace", payload)
            operation.success = True
    finally:
        timelineWidgets.clear_time_slider_selection()
        cmds.currentTime(original_time)


# ............. copy single frame World Space


def copy_worldspace_single_frame(*args):
    selected_objects = selectionMod.get_selected_objects(orderedSelection=True)
    if not selected_objects:
        return

    animation_data = {}

    # Obtener el tiempo actual
    current_time = cmds.currentTime(query=True)

    try:
        with toolCommon.tool_operation(
            tool_id="ws_copy_frame",
            label="World Space current frame copied",
            progress=False,
            tint="current",
            undo=False,
            suspend_refresh=True,
        ) as operation:
            for source_obj in selected_objects:
                worldspace_values = cmds.xform(source_obj, query=True, translation=True, worldSpace=True) + cmds.xform(
                    source_obj, query=True, rotation=True, worldSpace=True
                )
                animation_data[source_obj] = {int(current_time): worldspace_values}

            # Save to clipboard
            payload = {
                "meta": {"ordered_objects": selected_objects},
                "data": animation_data,
            }
            clipboard.save("worldspace_frame", payload)
            operation.success = True

    finally:
        pass


def paste_worldspace_single_frame(*args):
    operation_context = None
    tint_session = None
    try:
        operation_context = toolCommon.tool_operation(
            tool_id="ws_paste_frame",
            label="Paste World Space Frame",
            progress=False,
            undo=True,
        )
        operation_context.__enter__()

        # Load from clipboard
        payload = clipboard.load("worldspace_frame", "No World Space data found. Please copy a frame first.")
        if payload is None:
            return

        selection_mismatch_message = "Selection missmatched to paste worldspace"

        if isinstance(payload, dict) and "data" in payload:
            animation_data = payload.get("data") or {}
            ordered_sources = (payload.get("meta") or {}).get("ordered_objects") or list(animation_data.keys())
        else:
            animation_data = payload or {}
            ordered_sources = list(animation_data.keys())

        ordered_sources = [obj for obj in ordered_sources if obj in animation_data]
        if not ordered_sources:
            return wutil.make_inViewMessage("No World Space data found")

        frame_range = timelineWidgets.get_animation_data_timerange(
            {obj_name: {"frames": list((animation_data.get(obj_name) or {}).keys())} for obj_name in ordered_sources},
            frame_key="frames",
        )
        if frame_range:
            tint_session = timelineWidgets.begin_timeline_tint(
                timerange=frame_range,
                color=_active_tint_color("ws_paste_frame"),
                key="ws_paste_frame",
            )

        target_objects = selectionMod.get_selected_objects(orderedSelection=True)

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
                if cmds.objExists(obj):
                    cmds.xform(obj, translation=values[:3], worldSpace=True)
                    cmds.xform(obj, rotation=values[3:], worldSpace=True)
            return

        # Multi-source: paste in order (source[0]->target[0], ...)
        for idx, target_obj in enumerate(target_objects):
            source_obj = ordered_sources[idx]
            values = _first_frame_values(source_obj)
            if not values:
                return wutil.make_inViewMessage("No World Space data found")
            if cmds.objExists(target_obj):
                cmds.xform(target_obj, translation=values[:3], worldSpace=True)
                cmds.xform(target_obj, rotation=values[3:], worldSpace=True)

        return

    finally:
        if tint_session:
            tint_session.finish()
        if operation_context:
            try:
                operation_context.__exit__(None, None, None)
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
            progress=False,
            undo=True,
            suspend_refresh=True,
        ) as operation:
            payload = clipboard.load("worldspace", "No World Space animation data found. Please copy first.")
            if payload is None:
                return

            selection_mismatch_message = "Selection missmatched to paste worldspace"

            if isinstance(payload, dict) and "data" in payload:
                animation_data = payload.get("data") or {}
                ordered_sources = (payload.get("meta") or {}).get("ordered_objects") or list(animation_data.keys())
            else:
                animation_data = payload or {}
                ordered_sources = list(animation_data.keys())

            ordered_sources = [obj for obj in ordered_sources if obj in animation_data]
            if not ordered_sources:
                return wutil.make_inViewMessage("No World Space animation data found")

            target_objects = selectionMod.get_selected_objects(orderedSelection=True)

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

            # Cut existing animation on targets
            for _, target_obj in mapping:
                if cmds.objExists(target_obj):
                    cmds.cutKey(target_obj, attribute=["tx", "ty", "tz", "rx", "ry", "rz"])

            # Frames to paste (union of used sources)
            mapped_animation_data = {}
            mapped_frame_values = {}
            frame_set = set()
            for source_obj, _ in mapping:
                values_by_frame = _worldspace_frame_value_map(animation_data.get(source_obj) or {})
                if values_by_frame:
                    mapped_frame_values[source_obj] = values_by_frame
                    mapped_animation_data[source_obj] = {"frames": list(values_by_frame.keys())}
                    frame_set.update(values_by_frame.keys())

            paste_range = timelineWidgets.get_animation_data_timerange(mapped_animation_data, frame_key="frames")
            if not paste_range:
                return wutil.make_inViewMessage("No World Space animation data found")

            operation.timerange = paste_range
            operation.tint = "range"

            all_frames = sorted(frame_set)

            # Reconfigure progress now that we know max items
            operation.progress_obj.max_items = len(all_frames)
            operation.progress_obj._enabled = True

            for frame in all_frames:
                if operation.cancelled:
                    break

                cmds.currentTime(frame)
                for source_obj, target_obj in mapping:
                    if not cmds.objExists(target_obj):
                        continue
                    values = (mapped_frame_values.get(source_obj) or {}).get(frame)
                    if values is None:
                        continue
                    cmds.xform(target_obj, translation=values[:3], worldSpace=True)
                    cmds.xform(target_obj, rotation=values[3:], worldSpace=True)
                    cmds.setKeyframe(target_obj, time=(frame,), attribute=["tx", "ty", "tz", "rx", "ry", "rz"])
                operation.step()

            valid_targets = [t for _, t in mapping if cmds.objExists(t)]
            if valid_targets:
                cmds.filterCurve(valid_targets)
            
            operation.success = True

    finally:
        cmds.currentTime(original_time)
