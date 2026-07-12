"""
TheKeyMachine - Time Operations

Slider modes that modify keyframe timing (offsetting and staggering).
"""

import maya.cmds as cmds
from TheKeyMachine.core import curveFitting
from . import mode_values
from . import utils


def _resolve_targets_for_session(session):
    """Resolve and cache curve targets on the session for the lifetime of one drag."""
    return utils.resolve_curve_targets_for_session(session)


def _curve_owner(curve):
    try:
        plugs = cmds.listConnections(
            "{}.output".format(curve), source=False, destination=True, plugs=True
        ) or []
    except Exception:
        plugs = []
    if not plugs:
        return curve
    return plugs[0].split(".", 1)[0]


def apply_time_offset(session, curves=None, amount=0.0):
    """Shift animation shape in time while preserving every destination key time."""
    resolved_curves, affected_map = _resolve_targets_for_session(session)
    for curve in resolved_curves:
        keys = affected_map.get(curve, [])
        if not keys:
            continue
        source_times = [float(destination_time) - float(amount) for destination_time in keys]
        source_shape = curveFitting.capture([curve], source_times).get(curve, {})
        for destination_time, source_time in zip(keys, source_times):
            # Positive drag moves the visible shape later, so each fixed key
            # samples an earlier point from the untouched source curve.
            source_sample = source_shape.get(float(source_time), {})
            source_value = source_sample.get("value")
            if source_value is None:
                continue
            mode_values.apply_curve_value(
                session, curve, destination_time, source_value,
                create=False, allow_cmds_fallback=True,
            )
            if session.preview or len(keys) < 2:
                continue
            # Preserve automatic tangent types. Only already-manual sides are
            # rotated to the fitted shifted shape, matching bake keep-shape.
            try:
                key_range = (destination_time, destination_time)
                in_type = (
                    cmds.keyTangent(curve, query=True, time=key_range, inTangentType=True) or [None]
                )[0]
                out_type = (
                    cmds.keyTangent(curve, query=True, time=key_range, outTangentType=True) or [None]
                )[0]
                angle_kwargs = {"absolute": True}
                if in_type == "fixed" and source_sample.get("in_angle") is not None:
                    angle_kwargs["inAngle"] = source_sample["in_angle"]
                if out_type == "fixed" and source_sample.get("out_angle") is not None:
                    angle_kwargs["outAngle"] = source_sample["out_angle"]
                if len(angle_kwargs) > 1:
                    cmds.keyTangent(curve, edit=True, time=key_range, **angle_kwargs)
            except Exception:
                pass


def apply_time_stagger(session, curves=None, amount=0.0):
    """Stagger whole-object key timing while keeping each object's channels together."""
    resolved_curves, affected_map = _resolve_targets_for_session(session)
    if not resolved_curves:
        return
        
    owner_order = []
    for curve in resolved_curves:
        owner = _curve_owner(curve)
        if owner not in owner_order:
            owner_order.append(owner)
    owner_offsets = {owner: index * amount for index, owner in enumerate(owner_order)}

    for curve in resolved_curves:
        keys = affected_map.get(curve, [])
        if not keys:
            continue
            
        if (curve, "times") not in session.cache.auxiliary:
            session.cache.auxiliary[(curve, "times")] = list(keys)
        orig_times = session.cache.auxiliary[(curve, "times")]
        stagger_offset = owner_offsets[_curve_owner(curve)]
        
        indexed_keys = list(enumerate(keys))
        indexed_keys.sort(key=lambda item: item[1], reverse=stagger_offset > 0.0)
        updated = {}
        for j, t in indexed_keys:
            orig_t = orig_times[j]
            new_t = orig_t + stagger_offset
            cmds.keyframe(curve, edit=True, time=(t, t), timeChange=new_t)
            updated[j] = new_t
        for j, new_t in updated.items():
            keys[j] = new_t
