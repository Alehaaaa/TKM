from maya import cmds

import TheKeyMachine.mods.selectionMod as selectionMod
from TheKeyMachine.tools import common as toolCommon
import TheKeyMachine.widgets.timeline as timelineWidgets
import TheKeyMachine.widgets.util as wutil


def _collect_keyframes(objects):
    frames = set()
    for obj in objects or []:
        for frame in cmds.keyframe(obj, query=True, timeChange=True) or []:
            frames.add(float(frame))
    return sorted(frames)


def _target_keyframes_for_context(target_object, time_context):
    """Return only real target keys allowed by the active time selection."""
    target_frames = _collect_keyframes([target_object])
    if time_context.mode == "graph_editor_keys":
        selected_frames = {float(frame) for frame in time_context.frames}
        return [frame for frame in target_frames if frame in selected_frames]
    if time_context.mode == "time_slider_range":
        return [
            frame
            for frame in target_frames
            if time_context.start_frame <= frame <= time_context.end_frame
        ]
    return []


def _keyable_transform_attributes(pos, rot, scl):
    attributes = []
    if pos:
        attributes.extend(("translateX", "translateY", "translateZ"))
    if rot:
        attributes.extend(("rotateX", "rotateY", "rotateZ"))
    if scl:
        attributes.extend(("scaleX", "scaleY", "scaleZ"))
    return attributes


def _apply_auto_euler_filter(objects):
    from TheKeyMachine.tools.attribute_switcher import api as attributeSwitcherApi

    if not attributeSwitcherApi.is_euler_filter_enabled():
        return

    plugs = [
        "{}.{}".format(obj, attr)
        for obj in objects
        for attr in ("rotateX", "rotateY", "rotateZ")
        if cmds.objExists("{}.{}".format(obj, attr))
    ]
    curves = selectionMod.get_anim_curves_from_plugs(plugs)
    if curves:
        cmds.filterCurve(*curves)


def align_selected_objects(*_args, **kwargs):
    pos = kwargs.get("pos", True)
    rot = kwargs.get("rot", True)
    scl = kwargs.get("scl", False)
    key_scope = kwargs.get("key_scope", "selection")
    selection = selectionMod.get_selected_objects(ordered=True)
    if len(selection) < 2:
        return wutil.make_inViewMessage("Select at least two objects")

    source_objects = selection[:-1]
    target_object = selection[-1]
    start_frame = cmds.currentTime(query=True)
    modified_objects = []
    with toolCommon.suspend_maya_refresh():
        try:
            frames = []
            set_keys = False
            if key_scope == "all":
                frames = _collect_keyframes([target_object])
                set_keys = True
            else:
                time_context = timelineWidgets.resolve_time_context(
                    default_mode="current_frame"
                )
                if time_context.mode in ("graph_editor_keys", "time_slider_range"):
                    frames = _target_keyframes_for_context(
                        target_object, time_context
                    )
                    set_keys = True

            if set_keys and not frames:
                return wutil.make_inViewMessage(
                    "No matching-object keys available in the selected time scope."
                )

            if not set_keys:
                for source_object in source_objects:
                    cmds.matchTransform(
                        source_object, target_object, pos=pos, rot=rot, scl=scl
                    )
                    modified_objects.append(source_object)
                return

            key_attributes = _keyable_transform_attributes(pos, rot, scl)
            with toolCommon.tool_operation(
                tool_id="align_selected_objects",
                label="Aligning Objects",
                progress_max=len(frames),
                undo=True,
            ) as operation:
                for frame in operation.iterate(frames):
                    if operation.cancelled:
                        break
                    cmds.currentTime(frame)
                    for source_object in source_objects:
                        cmds.matchTransform(
                            source_object, target_object, pos=pos, rot=rot, scl=scl
                        )
                        cmds.setKeyframe(
                            source_object, attribute=key_attributes
                        )
                        if source_object not in modified_objects:
                            modified_objects.append(source_object)

                if rot and modified_objects:
                    _apply_auto_euler_filter(modified_objects)
        finally:
            cmds.currentTime(start_frame)
            if modified_objects:
                cmds.select(modified_objects, replace=True)
