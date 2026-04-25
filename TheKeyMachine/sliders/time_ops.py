"""
TheKeyMachine - Time Operations

Slider modes that modify keyframe timing (offsetting and staggering).
"""

import maya.cmds as cmds
from . import utils


def _resolve_targets_for_session(session):
    """Resolve and cache curve targets on the session for the lifetime of one drag."""
    if not session.targets.resolved:
        curves, times_map, time_range, has_graph_keys = utils.resolve_curve_targets()
        session.targets.curves = curves
        session.targets.affected_map = times_map
        session.targets.time_range = time_range
        session.targets.has_graph_keys = has_graph_keys
        session.targets.resolved = True
    return session.targets.curves, session.targets.affected_map


def apply_time_offset(session, curves=None, amount=0.0):
    """Shifts all selected keys by a specific frame amount."""
    resolved_curves, affected_map = _resolve_targets_for_session(session)
    
    for curve in resolved_curves:
        keys = affected_map.get(curve, [])
        if not keys:
            continue
            
        # Cache original times for stable dragging
        if (curve, "times") not in session.cache.frame_data:
            session.cache.frame_data[(curve, "times")] = list(keys)
            
        orig_times = session.cache.frame_data[(curve, "times")]
        
        # We must shift keys while avoiding collisions. 
        # For a simple offset, it's safer to move the whole block.
        # But since we are dragging, we should move from original positions.
        
        for i, t in enumerate(keys):
            orig_t = orig_times[i]
            new_t = orig_t + amount
            # Only move if it actually changed significantly to avoid sub-frame jitter
            cmds.keyframe(curve, edit=True, time=(t, t), timeChange=new_t)
            # Update affected map for next iteration
            keys[i] = new_t


def apply_time_stagger(session, curves=None, amount=0.0):
    """Staggers the timing of selected keys across different objects."""
    resolved_curves, affected_map = _resolve_targets_for_session(session)
    if not resolved_curves:
        return
        
    for i, curve in enumerate(resolved_curves):
        keys = affected_map.get(curve, [])
        if not keys:
            continue
            
        # Cache original times
        if (curve, "times") not in session.cache.frame_data:
            session.cache.frame_data[(curve, "times")] = list(keys)
            
        orig_times = session.cache.frame_data[(curve, "times")]
        
        # Stagger based on curve index
        stagger_offset = i * amount
        
        for j, t in enumerate(keys):
            orig_t = orig_times[j]
            new_t = orig_t + stagger_offset
            cmds.keyframe(curve, edit=True, time=(t, t), timeChange=new_t)
            keys[j] = new_t
