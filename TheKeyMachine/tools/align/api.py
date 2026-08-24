from maya import cmds

from TheKeyMachine.maya import animation
from TheKeyMachine.tools import common as toolCommon
import TheKeyMachine.ui.widgets.util as wutil


def _collect_keyframes(objects, attributes=None, layer_context=None):
    layer_context = layer_context or animation.layer_cache.capture()
    frames = set()
    for obj in objects or []:
        plugs = [
            "{}.{}".format(obj, attribute)
            for attribute in (attributes or ())
        ]
        if plugs and animation.has_anim_layers():
            for plug in plugs:
                destination = layer_context.destination_for_plug(plug)
                if destination.get("blocked"):
                    continue
                curve = animation.layer_graph.curve_for_plug(
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


def _apply_auto_euler_filter(objects, target_info, layer_context=None, operation=None):
    from TheKeyMachine.tools.attribute_switcher import api as attributeSwitcherApi

    if not attributeSwitcherApi.is_euler_filter_enabled():
        return

    layer_context = layer_context or animation.layer_cache.capture()
    plugs = [
        "{}.{}".format(obj, attr)
        for obj in objects
        for attr in ("rotateX", "rotateY", "rotateZ")
        if cmds.objExists("{}.{}".format(obj, attr))
    ]
    curves = []
    for plug in plugs:
        destination = layer_context.destination_for_plug(plug)
        if destination.get("blocked"):
            continue
        curve = animation.layer_graph.curve_for_plug(
            plug,
            layer_name=destination.get("layer"),
        )
        if curve:
            curves.append(curve)
    if not animation.has_anim_layers():
        curves = animation.layer_graph.curves_for_plugs(
            plugs,
            include_all_layers=True,
        )
    if curves:
        with animation.preserve_key_selection():
            animation.apply_smart_euler_filter(
                list(dict.fromkeys(curves)),
                target_info,
                operation=operation,
            )


def align_selected_objects(*_args, **kwargs):
    pos = kwargs.get("pos", True)
    rot = kwargs.get("rot", True)
    scl = kwargs.get("scl", False)
    key_scope = kwargs.get("key_scope", "selection")
    operation = toolCommon.require_tool_operation(kwargs.get("tool_operation"))
    target_info = animation.resolve_context(
        default_mode="current_frame", include_channels=True
    )
    selection = list(target_info.selection_snapshot.objects)
    if len(selection) < 2:
        return wutil.make_inViewMessage("Select at least two objects")

    source_objects = selection[:-1]
    target_object = selection[-1]
    start_frame = target_info.selection_snapshot.current_time
    modified_objects = []
    layer_context = animation.layer_cache.capture()
    key_attributes = _keyable_transform_attributes(pos, rot, scl)
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
            time_context = target_info.time
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

        operation.set_total(len(frames)).set_status("Aligning Objects")
        locked_destination = False
        for frame in operation.iterate(frames):
            if operation.cancelled:
                break
            cmds.currentTime(frame)
            for source_object in source_objects:
                groups, blocked = layer_context.group_by_destination(
                    source_object, key_attributes
                )
                locked_destination = locked_destination or bool(blocked)
                if not groups:
                    continue
                cmds.matchTransform(
                    source_object, target_object, pos=pos, rot=rot, scl=scl
                )
                _keyed, blocked = layer_context.set_keyframe(
                    source_object,
                    key_attributes,
                    time=frame,
                )
                locked_destination = locked_destination or bool(blocked)
                if source_object not in modified_objects:
                    modified_objects.append(source_object)

        if locked_destination:
            wutil.make_inViewMessage("Current animation layer is locked")
        if rot and modified_objects:
            operation.set_status("Euler Filtering")
            _apply_auto_euler_filter(
                modified_objects,
                target_info,
                layer_context=layer_context,
                operation=operation,
            )
    finally:
        cmds.currentTime(start_frame)
        if modified_objects:
            cmds.select(modified_objects, replace=True)
