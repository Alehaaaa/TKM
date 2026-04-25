"""
TheKeyMachine - Tangent Operations

Proper tangent blending and manipulation logic.
"""

import maya.cmds as cmds
from . import utils


def _resolve_targets_for_session(session):
    """Reuse centralized resolution logic."""
    if not session.targets.resolved:
        curves, times_map, time_range, has_graph_keys = utils.resolve_curve_targets()
        session.targets.curves = curves
        session.targets.affected_map = times_map
        session.targets.time_range = time_range
        session.targets.has_graph_keys = has_graph_keys
        session.targets.resolved = True
    return session.targets.curves, session.targets.affected_map


def _ensure_tangent_cache(session, curve, keys):
    """Caches original tangent states using batched commands for performance."""
    if (curve, "tangents") in session.cache.frame_data:
        return
        
    cache = {}
    try:
        # Batch query all properties at once for the entire curve (filtered by keys later)
        # Maya's keyTangent is extremely efficient when passed multiple times
        in_angles = cmds.keyTangent(curve, query=True, time=(keys[0], keys[-1]), inAngle=True) or []
        out_angles = cmds.keyTangent(curve, query=True, time=(keys[0], keys[-1]), outAngle=True) or []
        in_weights = cmds.keyTangent(curve, query=True, time=(keys[0], keys[-1]), inWeight=True) or []
        out_weights = cmds.keyTangent(curve, query=True, time=(keys[0], keys[-1]), outWeight=True) or []
        all_times = cmds.keyTangent(curve, query=True, time=(keys[0], keys[-1]), timeChange=True) or []
        
        # Zip them into a lookup map
        full_curve_data = {}
        for i, t in enumerate(all_times):
            full_curve_data[float(t)] = {
                "inAngle": in_angles[i],
                "outAngle": out_angles[i],
                "inWeight": in_weights[i],
                "outWeight": out_weights[i],
            }
            
        # Only cache the ones we actually care about
        for t in keys:
            if t in full_curve_data:
                cache[t] = full_curve_data[t]
                
    except Exception:
        pass
        
    session.cache.frame_data[(curve, "tangents")] = cache


def apply_tangent_type_blend(session, curves=None, tangent_type="auto", factor=1.0):
    """Blends the selected tangents toward a specific Maya tangent type."""
    resolved_curves, affected_map = _resolve_targets_for_session(session)
    
    for curve in resolved_curves:
        keys = affected_map.get(curve, [])
        if not keys:
            continue
            
        _ensure_tangent_cache(session, curve, keys)
        orig_tangents = session.cache.frame_data.get((curve, "tangents"), {})
        
        target_cache_key = (curve, f"target_{tangent_type}")
        if target_cache_key not in session.cache.frame_data:
            targets = {}
            # To get target values, we temporarily set the type and query, then restore.
            # We do this in one batch per curve for maximum speed.
            try:
                # 1. Save current types to restore them
                curr_in_types = cmds.keyTangent(curve, query=True, time=(keys[0], keys[-1]), inTangentType=True) or []
                curr_out_types = cmds.keyTangent(curve, query=True, time=(keys[0], keys[-1]), outTangentType=True) or []
                all_times = cmds.keyTangent(curve, query=True, time=(keys[0], keys[-1]), timeChange=True) or []
                
                # 2. Set ALL keys on curve to target type temporarily
                cmds.keyTangent(curve, time=(keys[0], keys[-1]), inTangentType=tangent_type, outTangentType=tangent_type)
                
                # 3. Query the resulting angles/weights
                t_in_a = cmds.keyTangent(curve, query=True, time=(keys[0], keys[-1]), inAngle=True) or []
                t_out_a = cmds.keyTangent(curve, query=True, time=(keys[0], keys[-1]), outAngle=True) or []
                t_in_w = cmds.keyTangent(curve, query=True, time=(keys[0], keys[-1]), inWeight=True) or []
                t_out_w = cmds.keyTangent(curve, query=True, time=(keys[0], keys[-1]), outWeight=True) or []
                
                # 4. Restore original types key by key (unfortunately batch restoration of types is tricky if they vary)
                for i, t in enumerate(all_times):
                    cmds.keyTangent(curve, time=(t,), inTangentType=curr_in_types[i], outTangentType=curr_out_types[i])
                    
                    if float(t) in keys:
                        targets[float(t)] = {
                            "inAngle": t_in_a[i],
                            "outAngle": t_out_a[i],
                            "inWeight": t_in_w[i],
                            "outWeight": t_out_w[i]
                        }
            except Exception:
                pass
            session.cache.frame_data[target_cache_key] = targets

        target_tangents = session.cache.frame_data[target_cache_key]
        is_weighted = cmds.animCurveInfo(curve, query=True, weightedTangents=True)
        
        for time in keys:
            if time not in orig_tangents or time not in target_tangents:
                continue
                
            orig = orig_tangents[time]
            target = target_tangents[time]
            
            # Blend angles
            new_in_a = utils.lerp(orig["inAngle"], target["inAngle"], factor)
            new_out_a = utils.lerp(orig["outAngle"], target["outAngle"], factor)
            
            # Blend weights if curve is weighted
            if is_weighted:
                new_in_w = utils.lerp(orig["inWeight"], target["inWeight"], factor)
                new_out_w = utils.lerp(orig["outWeight"], target["outWeight"], factor)
                cmds.keyTangent(curve, time=(time,), inAngle=new_in_a, outAngle=new_out_a, inWeight=new_in_w, outWeight=new_out_w)
            else:
                cmds.keyTangent(curve, time=(time,), inAngle=new_in_a, outAngle=new_out_a)
