from maya import cmds

from TheKeyMachine.core import animation_context
from TheKeyMachine.core import animlayers
import TheKeyMachine.mods.selectionMod as selectionMod
from TheKeyMachine.tools import common as toolCommon
import TheKeyMachine.widgets.util as wutil


def _collect_keyframes(objects, attributes=None, layer_context=None):
    frames = set()
    for obj in objects or []:
        plugs = [
            "{}.{}".format(obj, attribute)
            for attribute in (attributes or ())
        ]
        if plugs and animlayers.has_anim_layers():
            for plug in plugs:
                destination = animlayers.selected_destination_for_plug(
                    plug, context=layer_context
                )
                if destination.get("blocked"):
                    continue
                curve = animlayers.get_anim_curve_for_plug(
                    plug,
                    layer_name=destination.get("layer"),
                )
                if not curve:
                    continue
                for frame in cmds.keyframe(curve, query=True, timeChange=True) or []:
                    frames.add(float(frame))
        else:
            for frame in cmds.keyframe(obj, query=True, timeChange=True) or []:
                frames.add(float(frame))
    return sorted(frames)


def _target_keyframes_for_context(
    target_object, time_context, attributes=None, layer_context=None
):
    """Return only real target keys allowed by the active time selection."""
    target_frames = _collect_keyframes(
        [target_object],
        attributes=attributes,
        layer_context=layer_context,
    )
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


def _apply_auto_euler_filter(objects, layer_context=None):
    from TheKeyMachine.tools.attribute_switcher import api as attributeSwitcherApi

    if not attributeSwitcherApi.is_euler_filter_enabled():
        return

    plugs = [
        "{}.{}".format(obj, attr)
        for obj in objects
        for attr in ("rotateX", "rotateY", "rotateZ")
        if cmds.objExists("{}.{}".format(obj, attr))
    ]
    curves = []
    for plug in plugs:
        destination = animlayers.selected_destination_for_plug(
            plug, context=layer_context
        )
        if destination.get("blocked"):
            continue
        curve = animlayers.get_anim_curve_for_plug(
            plug,
            layer_name=destination.get("layer"),
        )
        if curve:
            curves.append(curve)
    if not animlayers.has_anim_layers():
        curves = selectionMod.get_anim_curves_from_plugs(plugs)
    if curves:
        cmds.filterCurve(*list(dict.fromkeys(curves)))


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
    layer_context = animlayers.capture_context()
    key_attributes = _keyable_transform_attributes(pos, rot, scl)
    with toolCommon.suspend_maya_refresh():
        try:
            frames = []
            set_keys = False
            if key_scope == "all":
                frames = _collect_keyframes(
                    [target_object],
                    attributes=key_attributes,
                    layer_context=layer_context,
                )
                set_keys = True
            else:
                time_context = animation_context.resolve_targets(
                    default_mode="current_frame"
                )["time_context"]
                if time_context.mode in ("graph_editor_keys", "time_slider_range"):
                    frames = _target_keyframes_for_context(
                        target_object,
                        time_context,
                        attributes=key_attributes,
                        layer_context=layer_context,
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

            with toolCommon.tool_operation(
                tool_id="align_selected_objects",
                label="Aligning Objects",
                progress_max=len(frames),
                undo=True,
            ) as operation:
                locked_destination = False
                for frame in operation.iterate(frames):
                    if operation.cancelled:
                        break
                    cmds.currentTime(frame)
                    for source_object in source_objects:
                        groups, blocked = animlayers.group_attributes_by_destination(
                            source_object,
                            key_attributes,
                            context=layer_context,
                        )
                        locked_destination = locked_destination or bool(blocked)
                        if not groups:
                            continue
                        cmds.matchTransform(
                            source_object, target_object, pos=pos, rot=rot, scl=scl
                        )
                        _keyed, blocked = animlayers.set_keyframe_in_destination(
                            source_object,
                            key_attributes,
                            time=frame,
                            context=layer_context,
                        )
                        locked_destination = locked_destination or bool(blocked)
                        if source_object not in modified_objects:
                            modified_objects.append(source_object)

                if locked_destination:
                    wutil.make_inViewMessage("Current animation layer is locked")
                if rot and modified_objects:
                    _apply_auto_euler_filter(
                        modified_objects, layer_context=layer_context
                    )
        finally:
            cmds.currentTime(start_frame)
            if modified_objects:
                cmds.select(modified_objects, replace=True)
