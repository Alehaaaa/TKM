"""Shared animation target, key-range, and selection-context helpers."""

from contextlib import contextmanager

from maya import cmds

from TheKeyMachine.mods import selectionMod as selection
from TheKeyMachine.widgets import timeline


_COMMAND_ERRORS = (RuntimeError, ValueError, TypeError, AttributeError, KeyError, IndexError)
_EXPLICIT_CHANNEL_SOURCES = {"channel_box", "graph_editor", "graph_editor_outliner"}


def selection_time_kwargs(time_context):
    if time_context and time_context.mode in ("graph_editor_keys", "time_slider_range"):
        return {"time": (time_context.start_frame, time_context.end_frame)}
    return {}


def selected_key_times(curve):
    try:
        return cmds.keyframe(curve, query=True, selected=True, timeChange=True) or []
    except _COMMAND_ERRORS:
        return []


def key_times(curve, target_info):
    time_context = (target_info or {}).get("time_context")
    if time_context and time_context.mode == "graph_editor_keys":
        return selected_key_times(curve)

    query_kwargs = {"query": True, "timeChange": True}
    if time_context and time_context.mode in ("current_frame", "time_slider_range"):
        query_kwargs["time"] = time_context.timerange
    try:
        return cmds.keyframe(curve, **query_kwargs) or []
    except _COMMAND_ERRORS:
        return []


def key_data(curve, target_info):
    """Return aligned ``(time, value)`` pairs for the active context."""
    time_context = (target_info or {}).get("time_context")
    query_kwargs = {"query": True}
    if time_context and time_context.mode == "graph_editor_keys":
        query_kwargs["selected"] = True
    elif time_context and time_context.mode in ("current_frame", "time_slider_range"):
        query_kwargs["time"] = time_context.timerange
    try:
        times = cmds.keyframe(curve, timeChange=True, **query_kwargs) or []
        values = cmds.keyframe(curve, valueChange=True, **query_kwargs) or []
        if len(times) != len(values):
            return []
        return [(float(time), float(value)) for time, value in zip(times, values)]
    except _COMMAND_ERRORS:
        return []


def resolve_targets(default_mode="all_animation", ordered_selection=False, long_names=True):
    selection_context = selection.resolve_target_context()
    target_plugs = selection_context["plugs"]
    has_graph_keys = selection_context["has_graph_keys"]
    target_objects = selection.object_names_from_plugs(target_plugs)
    if not target_objects:
        target_objects = selection.get_selected_objects(
            orderedSelection=ordered_selection,
            long=long_names,
        )
    return {
        "target_plugs": target_plugs,
        "target_objects": target_objects,
        "selected_channels": selection.attribute_names_from_plugs(target_plugs),
        "selected_curves": selection.get_anim_curves_from_plugs(target_plugs),
        "selected_keyframes": selection.get_graph_editor_selected_keyframes() if has_graph_keys else [],
        "time_context": timeline.resolve_time_context(default_mode=default_mode),
        "source": selection_context["source"],
        "has_graph_keys": has_graph_keys,
    }


def resolve_command_targets(default_mode="all_animation", include_shapes=True):
    """Return targets for key-edit commands using shared UI precedence rules."""
    target_info = resolve_targets(default_mode=default_mode, ordered_selection=True, long_names=True)
    selected_nodes = selection.get_selected_objects(long=True)
    channel_plugs, channel_source = selection.get_attribute_plugs_from_nodes(selected_nodes)

    # Explicit graph keys win. Otherwise an active Channel Box selection wins
    # over passive Graph Editor/outliner contents.
    if channel_source == "channel_box" and channel_plugs and target_info.get("source") != "graph_editor":
        target_info = dict(target_info)
        target_info.update(
            target_plugs=list(dict.fromkeys(channel_plugs)),
            target_objects=selection.object_names_from_plugs(channel_plugs),
            selected_channels=selection.attribute_names_from_plugs(channel_plugs),
            selected_curves=selection.get_anim_curves_from_plugs(channel_plugs),
            selected_keyframes=[],
            source="channel_box",
            has_graph_keys=False,
        )

    target_plugs = list(dict.fromkeys(target_info.get("target_plugs") or []))
    selected_objects = list(dict.fromkeys(target_info.get("target_objects") or []))
    selected_channels = list(dict.fromkeys(target_info.get("selected_channels") or []))
    if include_shapes and selected_objects:
        shaped_objects = list(selected_objects)
        for obj in selected_objects:
            try:
                shaped_objects.extend(cmds.listRelatives(obj, shapes=True, fullPath=True) or [])
            except _COMMAND_ERRORS:
                continue
        selected_objects = list(dict.fromkeys(shaped_objects))
    return target_info, target_plugs, selected_objects, selected_channels


def curves(target_info=None, include_shapes=True):
    if target_info is None:
        target_info, _plugs, _objects, _channels = resolve_command_targets(include_shapes=include_shapes)
    resolved = list(dict.fromkeys(target_info.get("selected_curves") or []))
    if resolved:
        return resolved
    target_plugs = list(dict.fromkeys(target_info.get("target_plugs") or []))
    resolved.extend(selection.get_anim_curves_from_plugs(target_plugs))
    if target_info.get("source") in _EXPLICIT_CHANNEL_SOURCES:
        return list(dict.fromkeys(resolved))
    selected_objects = list(dict.fromkeys(target_info.get("target_objects") or []))
    resolved.extend(selection.get_anim_curves_for_nodes(selected_objects, include_shapes=include_shapes))
    return list(dict.fromkeys(resolved))


def resolve_curve_context(default_mode="all_animation", include_shapes=True):
    target_info, _plugs, _objects, _channels = resolve_command_targets(
        default_mode=default_mode,
        include_shapes=include_shapes,
    )
    return target_info, curves(target_info, include_shapes=include_shapes)


def key_range(target_info, target_plugs=None, selected_objects=None, selected_channels=None):
    time_context = target_info.get("time_context")
    if time_context and time_context.mode == "graph_editor_keys" and time_context.frames:
        return time_context.start_frame, time_context.end_frame
    query_kwargs = {"query": True, "timeChange": True}
    if time_context and time_context.mode == "time_slider_range":
        query_kwargs["time"] = time_context.timerange
    frames = []
    if target_plugs:
        for plug in target_plugs:
            frames.extend(cmds.keyframe(plug, **query_kwargs) or [])
    else:
        if selected_channels:
            query_kwargs["attribute"] = selected_channels
        for obj in selected_objects or []:
            frames.extend(cmds.keyframe(obj, **query_kwargs) or [])
    return (min(frames), max(frames)) if frames else None


def capture_key_selection():
    scene_selection = cmds.ls(selection=True, long=True) or []
    try:
        selected_curves = cmds.keyframe(query=True, selected=True, name=True) or []
    except _COMMAND_ERRORS:
        selected_curves = []
    key_selection = []
    for curve in dict.fromkeys(selected_curves):
        key_selection.extend((curve, frame) for frame in selected_key_times(curve))
    return scene_selection, key_selection


def restore_key_selection(context):
    scene_selection, key_selection = context
    try:
        cmds.selectKey(clear=True)
    except _COMMAND_ERRORS:
        pass
    for curve, frame in key_selection:
        try:
            if cmds.keyframe(curve, query=True, time=(frame, frame)):
                cmds.selectKey(curve, add=True, keyframe=True, time=(frame, frame))
        except _COMMAND_ERRORS:
            continue
    try:
        existing = [item for item in scene_selection if cmds.objExists(item)]
        cmds.select(existing, replace=True) if existing else cmds.select(clear=True)
    except _COMMAND_ERRORS:
        pass


@contextmanager
def preserve_key_selection():
    context = capture_key_selection()
    try:
        yield
    finally:
        restore_key_selection(context)
