"""Resolve slider targets, times, and editable animation-layer curves."""

from maya import cmds

from TheKeyMachine.maya import animation, maya_api
from TheKeyMachine.maya import selection


def editable_curve_for_attribute(session, attribute):
    layer_context = getattr(session.targets, "layer_context", None)
    if not layer_context:
        layer_context = animation.layer_cache.tool_context()
        session.targets.layer_context = layer_context
    curve = animation.layer_graph.editable_curve_for_plug(attribute, layer_context)
    return curve, maya_api.anim_curve_fn(curve) if curve else None


def resolve_keyframe_targets(session):
    target_info = animation.resolve_context(
        default_mode="current_frame",
        include_shapes=True,
        resolve_curves=True,
        snapshot=session.selection_snapshot,
    )
    session.targets.layer_context = dict(target_info.layer_scope or {})
    plugs = target_info.plugs
    time_context = target_info.time
    time_range = time_context.timerange if time_context.mode == "time_slider_range" else None
    has_graph_keys = bool(target_info.selected_keys)
    if not plugs:
        return {}, time_range

    current_time = cmds.currentTime(query=True)
    tangent_frames = set()
    if has_graph_keys:
        tangent_frames = {
            float(frame)
            for frame in selection.get_graph_editor_selected_tangent_frames()
        }

    affected = {}
    for plug in plugs:
        if has_graph_keys:
            times = {
                float(frame)
                for frame in (
                    cmds.keyframe(plug, query=True, selected=True, timeChange=True) or []
                )
            }
            if tangent_frames:
                times |= tangent_frames & {
                    float(frame)
                    for frame in (cmds.keyframe(plug, query=True, timeChange=True) or [])
                }
            times = sorted(times) if times else [current_time]
        elif time_range:
            times = cmds.keyframe(
                plug,
                query=True,
                time=(time_range[0], time_range[1]),
                timeChange=True,
            ) or [current_time]
        else:
            times = [current_time]
        affected[plug] = sorted(set(times))
    return affected, time_range


def resolve_curve_targets(session):
    target_info = animation.resolve_context(
        default_mode="current_frame",
        include_shapes=True,
        resolve_curves=True,
        snapshot=session.selection_snapshot,
    )
    session.targets.layer_context = dict(target_info.layer_scope or {})
    curves = target_info.curves
    time_context = target_info.time
    time_range = time_context.timerange if time_context.mode == "time_slider_range" else None
    has_graph_keys = bool(target_info.selected_keys)
    if not curves:
        return [], {}, time_range, has_graph_keys

    current_time = cmds.currentTime(query=True)
    times = {
        curve: sorted({float(frame) for frame in (target_info.key_times(curve) or [current_time])})
        for curve in curves
    }
    return curves, times, time_range, has_graph_keys


def _show_resolved_range(session):
    if session.targets.time_range:
        session.show_target_tint(session.targets.time_range)


def curves_for_session(session):
    if not session.targets.resolved:
        curves, times, time_range, has_graph_keys = resolve_curve_targets(session)
        session.targets.curves = curves
        session.targets.affected_map = times
        session.targets.time_range = time_range
        session.targets.has_graph_keys = has_graph_keys
        session.targets.resolved = True
        _show_resolved_range(session)
    return session.targets.curves, session.targets.affected_map


def keyframes_for_session(session):
    if not session.targets.resolved:
        affected, time_range = resolve_keyframe_targets(session)
        session.targets.affected_map = affected
        session.targets.time_range = time_range
        session.targets.resolved = True
        _show_resolved_range(session)
    return session.targets.affected_map, session.targets.time_range
