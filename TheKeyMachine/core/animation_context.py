"""Shared animation target, key-range, and selection-context helpers."""

from contextlib import contextmanager

from maya import cmds

from TheKeyMachine.mods import selectionMod as selection
from TheKeyMachine.widgets import timeline


_COMMAND_ERRORS = (RuntimeError, ValueError, TypeError, AttributeError, KeyError, IndexError)
_EXPLICIT_CHANNEL_SOURCES = {"channel_box", "graph_editor", "graph_editor_outliner"}
_TANGENT_QUERY_FLAGS = (
    "inAngle",
    "outAngle",
    "inWeight",
    "outWeight",
    "inTangentType",
    "outTangentType",
    "lock",
    "weightLock",
)


def notify_empty(target="animation", action=None):
    """Show the shared concise empty-result message for animation tools."""
    from TheKeyMachine.widgets import util as wutil

    message = "No {}".format(target)
    if action:
        message += " to {}".format(action)
    return wutil.make_inViewMessage(message)


def selection_time_kwargs(time_context):
    if time_context and time_context.mode in ("graph_editor_keys", "time_slider_range"):
        return {"time": (time_context.start_frame, time_context.end_frame)}
    return {}


def capture_time_slider_selection():
    """Capture Maya's native highlighted playback range without touching selection.

    Maya 2024 added editable playback-selection flags. Keeping their raw start
    and end values avoids the inclusive/exclusive conversion used by key tools.
    """
    try:
        visible = cmds.playbackOptions(query=True, selectionVisible=True)
        if visible:
            start_frame = cmds.playbackOptions(query=True, selectionStartTime=True)
            end_frame = cmds.playbackOptions(query=True, selectionEndTime=True)
            return "native", start_frame, end_frame
    except _COMMAND_ERRORS:
        pass
    selected_range = selection.get_selected_time_slider_range()
    return ("legacy",) + tuple(selected_range) if selected_range else None


def restore_time_slider_selection(selected_range):
    """Restore a captured playback range without reselecting objects."""
    if not selected_range:
        return False
    backend, start_frame, end_frame = selected_range
    if backend == "legacy":
        current = selection.get_selected_time_slider_range()
        if current == (start_frame, end_frame):
            return True
        frames = (
            (start_frame,)
            if start_frame == end_frame
            else (start_frame, end_frame)
        )
        return timeline.select_time_slider_range(frames)
    try:
        current = capture_time_slider_selection()
        if current == selected_range:
            return True
        undo_enabled = False
        try:
            undo_enabled = bool(cmds.undoInfo(query=True, state=True))
            if undo_enabled:
                cmds.undoInfo(stateWithoutFlush=False)
            cmds.playbackOptions(
                edit=True,
                selectionStartTime=start_frame,
                selectionEndTime=end_frame,
                selectionVisible=True,
            )
        finally:
            if undo_enabled:
                cmds.undoInfo(stateWithoutFlush=True)
        return True
    except _COMMAND_ERRORS:
        return False


@contextmanager
def preserve_time_slider_selection():
    """Keep a highlighted range across a command's side effects."""
    selected_range = capture_time_slider_selection()
    try:
        yield selected_range
    finally:
        restore_time_slider_selection(selected_range)


def selected_key_times(curve):
    try:
        return cmds.keyframe(curve, query=True, selected=True, timeChange=True) or []
    except _COMMAND_ERRORS:
        return []


def key_times(curve, target_info):
    time_context = (target_info or {}).get("time_context")
    if time_context and time_context.mode == "graph_editor_keys":
        selected = [
            float(key_time)
            for selected_curve, key_time in (
                (target_info or {}).get("selected_keyframes") or []
            )
            if selected_curve == curve
        ]
        if selected:
            return selected
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
    if time_context and time_context.mode == "graph_editor_keys":
        selected_times = key_times(curve, target_info)
        data = []
        for key_time in selected_times:
            try:
                values = cmds.keyframe(
                    curve,
                    query=True,
                    time=(key_time, key_time),
                    valueChange=True,
                ) or []
            except _COMMAND_ERRORS:
                values = []
            if values:
                data.append((float(key_time), float(values[0])))
        return data
    query_kwargs = {"query": True}
    if time_context and time_context.mode in ("current_frame", "time_slider_range"):
        query_kwargs["time"] = time_context.timerange
    try:
        times = cmds.keyframe(curve, timeChange=True, **query_kwargs) or []
        values = cmds.keyframe(curve, valueChange=True, **query_kwargs) or []
        if len(times) != len(values):
            return []
        return [(float(time), float(value)) for time, value in zip(times, values)]
    except _COMMAND_ERRORS:
        return []


def resolve_tool_context(
    default_mode="all_animation",
    include_channels=True,
    include_graph=True,
    include_shapes=False,
    resolve_curves=False,
):
    """Resolve the shared animation-tool selection and time precedence.

    A highlighted Time Slider range wins. Channel Box attributes then restrict
    the target channels. Without either, exact Graph Editor keys or tangent
    handles win; otherwise tools use selected objects and the default time.
    """
    from TheKeyMachine.core import animlayers

    # Capture the UI attribute selection before any scene or graph queries.
    # Every animation tool consumes this one snapshot for the whole command.
    channel_selection = (
        selection.get_selected_channels()
        if include_channels
        else []
    )
    selected_objects = list(dict.fromkeys(
        selection.get_selected_objects(
            long=True,
            orderedSelection=True,
        ) or []
    ))
    attribute_nodes = list(selected_objects)
    if include_shapes:
        for node in selected_objects:
            try:
                attribute_nodes.extend(
                    cmds.listRelatives(node, shapes=True, fullPath=True) or []
                )
            except _COMMAND_ERRORS:
                continue
        attribute_nodes = list(dict.fromkeys(attribute_nodes))
    channel_plugs = []
    channel_source = "none"
    if include_channels:
        channel_plugs, channel_source = selection.get_attribute_plugs_from_nodes(
            attribute_nodes,
            selected_only=True,
            selected_channels=channel_selection,
        )
    has_channel_selection = bool(
        channel_source == "channel_box" and channel_plugs
    )
    selected_keyframes = (
        selection.get_graph_editor_selected_keyframes(include_tangents=True)
        if include_graph
        else []
    )
    time_context = timeline.resolve_time_context(
        default_mode=default_mode,
        graph_frames=(
            []
            if has_channel_selection
            else [key_time for _curve, key_time in selected_keyframes]
        ),
    )
    target_plugs = []
    selected_curves = []
    selected_channels = []
    source = "objects" if selected_objects else "none"

    if has_channel_selection:
        target_plugs = list(dict.fromkeys(channel_plugs))
        selected_channels = selection.attribute_names_from_plugs(target_plugs)
        selected_keyframes = []
        source = "channel_box"
    elif time_context.mode == "graph_editor_keys":
        selected_curves = list(dict.fromkeys(
            curve for curve, _key_time in selected_keyframes
        ))
        target_plugs = selection.get_anim_curve_output_plugs(selected_curves)
        selected_channels = selection.attribute_names_from_plugs(target_plugs)
        graph_objects = selection.object_names_from_plugs(target_plugs)
        if graph_objects:
            selected_objects = graph_objects
        source = "graph_editor"
    else:
        selected_keyframes = []
    if (
        not has_channel_selection
        and time_context.mode != "graph_editor_keys"
        and include_channels
    ):
        channel_plugs, channel_source = selection.get_attribute_plugs_from_nodes(
            attribute_nodes,
            selected_only=False,
            selected_channels=channel_selection,
        )
        if channel_plugs:
            target_plugs = list(dict.fromkeys(channel_plugs))
            selected_channels = selection.attribute_names_from_plugs(target_plugs)
            source = channel_source

    layer_context = animlayers.curve_tool_context()
    target_info = {
        "target_plugs": target_plugs,
        "target_objects": selected_objects,
        "selected_channels": selected_channels,
        "selected_curves": selected_curves,
        "selected_keyframes": selected_keyframes,
        "time_context": time_context,
        "source": source,
        "has_graph_keys": bool(selected_keyframes),
        "layer_context": layer_context,
    }
    if resolve_curves:
        target_info["selected_curves"] = _resolve_curves(
            target_info,
            include_shapes=include_shapes,
        )
    return target_info


def key_tangent_snapshots(curve, key_times):
    """Capture tangent data with batched Maya queries when possible."""
    key_times = [float(value) for value in key_times or []]
    if not curve or not key_times:
        return []
    snapshots = [{} for _time in key_times]
    time_range = (min(key_times), max(key_times))
    try:
        queried_times = [
            float(value)
            for value in (
                cmds.keyframe(curve, query=True, time=time_range, timeChange=True)
                or []
            )
        ]
    except _COMMAND_ERRORS:
        queried_times = []
    can_batch = len(queried_times) == len(key_times) and all(
        abs(source - requested) <= 0.000001
        for source, requested in zip(queried_times, key_times)
    )

    if can_batch:
        for flag in _TANGENT_QUERY_FLAGS:
            try:
                values = cmds.keyTangent(
                    curve,
                    query=True,
                    time=time_range,
                    **{flag: True}
                ) or []
            except _COMMAND_ERRORS:
                values = []
            for index, value in enumerate(values[:len(snapshots)]):
                snapshots[index][flag] = value
    else:
        for index, key_time in enumerate(key_times):
            for flag in _TANGENT_QUERY_FLAGS:
                try:
                    values = cmds.keyTangent(
                        curve,
                        query=True,
                        time=(key_time, key_time),
                        **{flag: True}
                    ) or []
                except _COMMAND_ERRORS:
                    values = []
                if values:
                    snapshots[index][flag] = values[0]

    try:
        weighted = cmds.keyTangent(
            curve,
            query=True,
            weightedTangents=True,
        ) or []
    except _COMMAND_ERRORS:
        weighted = []
    if weighted:
        for snapshot in snapshots:
            snapshot["weightedTangents"] = bool(weighted[0])
    return snapshots


def apply_key_tangent_snapshot(
    curve,
    key_time,
    snapshot,
    apply_weighted=True,
    attribute=None,
):
    """Restore one tangent snapshot in an order that preserves its details."""
    if not curve or not snapshot:
        return False

    def _edit(**kwargs):
        if not kwargs:
            return True
        try:
            command_kwargs = {
                "edit": True,
                "time": (key_time, key_time),
            }
            if attribute:
                command_kwargs["attribute"] = attribute
            command_kwargs.update(kwargs)
            cmds.keyTangent(
                curve,
                **command_kwargs
            )
            return True
        except _COMMAND_ERRORS:
            return False

    weighted = snapshot.get("weightedTangents")
    if apply_weighted and weighted is not None:
        apply_weighted_tangents(curve, weighted, attribute=attribute)

    # Existing locks can prevent angle/weight edits. Restore them last.
    if "lock" in snapshot:
        _edit(lock=False)
    if "weightLock" in snapshot:
        _edit(weightLock=False)
    tangent_types = {
        flag: snapshot[flag]
        for flag in ("inTangentType", "outTangentType")
        if flag in snapshot
    }
    _edit(**tangent_types)

    details = {}
    if snapshot.get("inTangentType") not in ("auto", "autoease", "autoEase", "autoMix"):
        for flag in ("inAngle", "inWeight"):
            if flag in snapshot:
                details[flag] = snapshot[flag]
    if snapshot.get("outTangentType") not in ("auto", "autoease", "autoEase", "autoMix"):
        for flag in ("outAngle", "outWeight"):
            if flag in snapshot:
                details[flag] = snapshot[flag]
    _edit(**details)
    if details:
        _edit(**tangent_types)

    if "lock" in snapshot:
        _edit(lock=snapshot["lock"])
    if "weightLock" in snapshot:
        _edit(weightLock=snapshot["weightLock"])
    return True


def apply_weighted_tangents(curve, weighted, attribute=None):
    """Set the curve-level weighted-tangent state through one shared path."""
    if not curve or weighted is None:
        return False
    kwargs = {"edit": True, "weightedTangents": bool(weighted)}
    if attribute:
        kwargs["attribute"] = attribute
    try:
        cmds.keyTangent(curve, **kwargs)
        return True
    except _COMMAND_ERRORS:
        return False


def resolve_curves_for_plugs(target_info, plugs):
    """Resolve exact plugs to curves in the command's live layer scope."""
    plugs = list(dict.fromkeys(plug for plug in plugs or [] if plug))
    if not plugs:
        return []
    layer_context = target_info.get("layer_context") or {}
    if layer_context.get("has_layers"):
        from TheKeyMachine.core import animlayers

        scene_layers = layer_context["scene_layers"]
        curve_layers = animlayers.get_anim_curve_layer_map_for_plugs(
            plugs,
            layer_context.get("scope_layer_names") or [],
            scene_layers=scene_layers,
        )
        layer_context.setdefault("curve_layers", {}).update(curve_layers)
        return list(curve_layers)

    return selection.get_anim_curves_from_plugs(plugs)


def _resolve_curves(target_info, include_shapes=True):
    resolved = list(dict.fromkeys(target_info.get("selected_curves") or []))
    if target_info.get("source") == "graph_editor" and resolved:
        return resolved
    lookup_plugs = list(dict.fromkeys(target_info.get("target_plugs") or []))
    selected_objects = list(dict.fromkeys(target_info.get("target_objects") or []))
    if target_info.get("source") not in _EXPLICIT_CHANNEL_SOURCES:
        lookup_nodes = list(selected_objects)
        if include_shapes:
            for node in selected_objects:
                try:
                    lookup_nodes.extend(
                        cmds.listRelatives(node, shapes=True, fullPath=True) or []
                    )
                except _COMMAND_ERRORS:
                    continue
        lookup_nodes = list(dict.fromkeys(lookup_nodes))
        lookup_plugs.extend(
            "{}.{}".format(node, attribute)
            for node in lookup_nodes
            for attribute in selection.get_keyable_scalar_attributes(node)
        )
    lookup_plugs = list(dict.fromkeys(lookup_plugs))

    resolved.extend(resolve_curves_for_plugs(target_info, lookup_plugs))

    layer_context = target_info.get("layer_context") or {}
    if layer_context.get("has_layers") and target_info.get("source") != "channel_box":
        from TheKeyMachine.core import animlayers

        curve_layers = layer_context.setdefault("curve_layers", {})
        for layer_name in layer_context.get("scope_layer_names") or []:
            for curve in animlayers.weight_curves(layer_name):
                curve_layers[curve] = layer_name
                resolved.append(curve)
    return list(dict.fromkeys(resolved))


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
