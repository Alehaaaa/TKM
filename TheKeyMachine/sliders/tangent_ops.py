"""
TheKeyMachine - Tangent Operations

Proper tangent blending and manipulation logic.
"""

import maya.cmds as cmds
from TheKeyMachine.core import curveFitting
from . import utils


def _ensure_tangent_cache(session, curve, keys):
    """Caches original tangent states using batched commands for performance."""
    if (curve, "tangents") in session.cache.auxiliary:
        return
        
    cache = {}
    keys = sorted(float(time) for time in keys)
    try:
        # Batch query all properties at once for the entire curve (filtered by keys later)
        # Maya's keyTangent is extremely efficient when passed multiple times
        in_angles = cmds.keyTangent(curve, query=True, time=(keys[0], keys[-1]), inAngle=True) or []
        out_angles = cmds.keyTangent(curve, query=True, time=(keys[0], keys[-1]), outAngle=True) or []
        in_weights = cmds.keyTangent(curve, query=True, time=(keys[0], keys[-1]), inWeight=True) or []
        out_weights = cmds.keyTangent(curve, query=True, time=(keys[0], keys[-1]), outWeight=True) or []
        in_types = cmds.keyTangent(curve, query=True, time=(keys[0], keys[-1]), inTangentType=True) or []
        out_types = cmds.keyTangent(curve, query=True, time=(keys[0], keys[-1]), outTangentType=True) or []
        locks = cmds.keyTangent(curve, query=True, time=(keys[0], keys[-1]), lock=True) or []
        all_times = cmds.keyframe(curve, query=True, time=(keys[0], keys[-1]), timeChange=True) or []
        
        result_count = min(
            len(all_times), len(in_angles), len(out_angles), len(in_weights),
            len(out_weights), len(in_types), len(out_types),
        )
        full_curve_data = {}
        for i in range(result_count):
            time = float(all_times[i])
            full_curve_data[time] = {
                "inAngle": in_angles[i],
                "outAngle": out_angles[i],
                "inWeight": in_weights[i],
                "outWeight": out_weights[i],
                "inType": in_types[i],
                "outType": out_types[i],
                "locked": bool(locks[i]) if i < len(locks) else False,
            }
            
        # Only cache the ones we actually care about
        for time in keys:
            if time in full_curve_data:
                cache[time] = full_curve_data[time]
                
    except Exception:
        pass
        
    session.cache.auxiliary[(curve, "tangents")] = cache


def _curve_has_weighted_tangents(curve):
    try:
        weighted = cmds.keyTangent(curve, query=True, weightedTangents=True)
        if isinstance(weighted, (list, tuple)):
            return bool(weighted[0]) if weighted else False
        return bool(weighted)
    except Exception:
        pass

    try:
        return bool(cmds.getAttr("{}.weightedTangents".format(curve)))
    except Exception:
        return False


def _bounce_targets(curve, keys, original_tangents, angle_factor=1.3):
    """Build the same neighbor-slope target used by the Bouncy Tangent tool."""
    targets = {}
    key_times = [float(value) for value in (cmds.keyframe(curve, query=True, timeChange=True) or [])]
    if not key_times:
        return targets

    for time in keys:
        if not any(abs(key_time - float(time)) < 0.0001 for key_time in key_times):
            continue
        original = original_tangents.get(time, {})
        in_angle, out_angle = curveFitting.bouncy_tangent_angles(curve, time, angle_adjustment_factor=angle_factor)
        targets[float(time)] = {
            "inAngle": in_angle,
            "outAngle": out_angle,
            "inWeight": original.get("inWeight", 1.0),
            "outWeight": original.get("outWeight", 1.0),
        }
    return targets


def _maya_type_targets(curve, keys, tangent_type):
    """Probe target rotations and always restore every original tangent type."""
    targets = {}
    originals = {}
    try:
        all_times = cmds.keyframe(curve, query=True, time=(keys[0], keys[-1]), timeChange=True) or []
        curr_in_types = cmds.keyTangent(curve, query=True, time=(keys[0], keys[-1]), inTangentType=True) or []
        curr_out_types = cmds.keyTangent(curve, query=True, time=(keys[0], keys[-1]), outTangentType=True) or []
        type_count = min(len(all_times), len(curr_in_types), len(curr_out_types))
        originals = {
            float(all_times[index]): (curr_in_types[index], curr_out_types[index])
            for index in range(type_count)
        }
        cmds.keyTangent(curve, time=(keys[0], keys[-1]), inTangentType=tangent_type, outTangentType=tangent_type)
        t_in_a = cmds.keyTangent(curve, query=True, time=(keys[0], keys[-1]), inAngle=True) or []
        t_out_a = cmds.keyTangent(curve, query=True, time=(keys[0], keys[-1]), outAngle=True) or []
        t_in_w = cmds.keyTangent(curve, query=True, time=(keys[0], keys[-1]), inWeight=True) or []
        t_out_w = cmds.keyTangent(curve, query=True, time=(keys[0], keys[-1]), outWeight=True) or []
        result_count = min(len(all_times), len(t_in_a), len(t_out_a), len(t_in_w), len(t_out_w))
        selected_times = set(float(time) for time in keys)
        for index in range(result_count):
            time = float(all_times[index])
            if time in selected_times:
                targets[time] = {
                    "inAngle": t_in_a[index], "outAngle": t_out_a[index],
                    "inWeight": t_in_w[index], "outWeight": t_out_w[index],
                }
    except Exception:
        pass
    finally:
        for time, (in_type, out_type) in originals.items():
            try:
                cmds.keyTangent(
                    curve, edit=True, time=(time, time),
                    inTangentType=in_type, outTangentType=out_type,
                )
            except Exception:
                pass
    return targets


def apply_tangent_type_blend(session, curves=None, tangent_type="auto", factor=1.0):
    """Blend toward a contextual target, or its vertical mirror on the left."""
    resolved_curves, affected_map = utils.resolve_curve_targets_for_session(session)
    
    for curve in resolved_curves:
        keys = affected_map.get(curve, [])
        if not keys:
            continue

        _ensure_tangent_cache(session, curve, keys)
        orig_tangents = session.cache.auxiliary.get((curve, "tangents"), {})
        
        target_cache_key = (curve, f"target_{tangent_type}")
        if target_cache_key not in session.cache.auxiliary:
            if tangent_type == "bounce":
                targets = _bounce_targets(curve, keys, orig_tangents)
            else:
                targets = _maya_type_targets(curve, keys, tangent_type)
            session.cache.auxiliary[target_cache_key] = targets

        target_tangents = session.cache.auxiliary[target_cache_key]
        is_weighted = _curve_has_weighted_tangents(curve)
        
        for time in keys:
            if time not in orig_tangents or time not in target_tangents:
                continue
                
            orig = orig_tangents[time]
            target = target_tangents[time]

            # The positive endpoint is authoritative: standard modes become
            # that actual Maya tangent type instead of merely resembling its
            # rotation. Bounce is custom and therefore remains a fixed-angle
            # contextual tangent.
            if factor >= 0.999999 and tangent_type != "bounce":
                cmds.keyTangent(
                    curve,
                    edit=True,
                    time=(time, time),
                    inTangentType=tangent_type,
                    outTangentType=tangent_type,
                    lock=orig["locked"],
                )
                continue
            
            # +100 reaches the contextual target rotation. -100 reaches its
            # vertical mirror (angle sign flipped), rather than extrapolating
            # a full rotation through and beyond the drag-start tangent.
            blend = min(1.0, max(0.0, abs(float(factor))))
            direction = 1.0 if factor >= 0.0 else -1.0
            target_in_angle = float(target["inAngle"]) * direction
            target_out_angle = float(target["outAngle"]) * direction
            new_in_a = utils.lerp(orig["inAngle"], target_in_angle, blend)
            new_out_a = utils.lerp(orig["outAngle"], target_out_angle, blend)
            tangent_kwargs = {"inAngle": new_in_a, "outAngle": new_out_a}

            # Blend weights if curve is weighted
            if is_weighted:
                tangent_kwargs["inWeight"] = utils.lerp(orig["inWeight"], target["inWeight"], blend)
                tangent_kwargs["outWeight"] = utils.lerp(orig["outWeight"], target["outWeight"], blend)
            cmds.keyTangent(curve, edit=True, time=(time, time), absolute=True, lock=False, **tangent_kwargs)
            # Fixed/manual tangents can retain both their type and blended
            # rotation. Maya necessarily promotes automatic tangents to fixed
            # when an explicit angle is authored.
            if orig["inType"] == "fixed" and orig["outType"] == "fixed":
                cmds.keyTangent(
                    curve, edit=True, time=(time, time),
                    inTangentType=orig["inType"], outTangentType=orig["outType"],
                )
            cmds.keyTangent(curve, edit=True, time=(time, time), lock=orig["locked"])
