"""
TheKeyMachine - Keyframe-level Slider Operations

Tweening and blending operations translated from keyToolsMod.
"""

import maya.cmds as cmds
from . import utils

# ---------------------------------------------------------------------------------------------------------------------
#                                                     Helpers                                                         #
# ---------------------------------------------------------------------------------------------------------------------


def _right_frame_from_time_range(time_range):
    if not time_range:
        return None
    try:
        start, end = time_range
    except Exception:
        return None
    if end <= start:
        return None
    return end - 1


def _ensure_keys_at_current_time(attr_plugs):
    current_time = cmds.currentTime(query=True)
    for attr_full in attr_plugs:
        try:
            if not cmds.objExists(attr_full):
                continue
            existing_keys = cmds.keyframe(attr_full, query=True) or []
            if not existing_keys:
                continue
            if cmds.getAttr(attr_full, lock=True) or not cmds.getAttr(attr_full, settable=True):
                continue
            if cmds.getAttr(attr_full, type=True) in ("enum", "string", "message"):
                continue
            cmds.setKeyframe(attr_full, time=current_time)
        except Exception:
            pass


def _has_keyframes(attr_full):
    try:
        return bool(cmds.keyframe(attr_full, query=True) or [])
    except Exception:
        return False


def _clamp_numeric_attr_value(attr_full, value):
    try:
        obj, attr = attr_full.split(".", 1)
    except ValueError:
        return value
    try:
        if cmds.attributeQuery(attr, node=obj, minExists=True):
            value = max(value, cmds.attributeQuery(attr, node=obj, minimum=True)[0])
        if cmds.attributeQuery(attr, node=obj, maxExists=True):
            value = min(value, cmds.attributeQuery(attr, node=obj, maximum=True)[0])
    except Exception:
        pass
    return value


def _set_attr_value(attr_full, value):
    value = _clamp_numeric_attr_value(attr_full, value)
    try:
        cmds.setAttr(attr_full, float(value))
        return
    except Exception:
        pass
    try:
        cmds.setAttr(attr_full, int(round(value)))
    except Exception:
        pass


def _apply_cached_value(attr_full, value, current_time, use_direct_attr=False):
    value = _clamp_numeric_attr_value(attr_full, value)
    if use_direct_attr:
        _set_attr_value(attr_full, value)
        return
    
    # setKeyframe is generally more reliable than keyframe(edit=True) for sub-frames
    # and ensuring autokey/undo behavior is consistent.
    try:
        cmds.setKeyframe(attr_full, time=(current_time,), value=float(value), absolute=True)
    except Exception:
        try:
            # Fallback to keyframe edit if setKeyframe fails (e.g. on non-standard anim curves)
            cmds.keyframe(attr_full, edit=True, time=(current_time, current_time), valueChange=float(value), absolute=True)
        except Exception:
            pass


def _resolve_affected_attribute_plugs():
    """Returns a map of {attr_plug: [frames]} and the active time range."""
    plugs, _source, time_range, has_graph_keys = utils.resolve_target_attribute_plugs()
    if not plugs:
        return {}, time_range

    current_time = cmds.currentTime(query=True)
    affected_data = {}

    for plug in plugs:
        times = []
        if has_graph_keys:
            # If in Graph Editor, prefer selected keys for this specific plug
            times = cmds.keyframe(plug, q=True, selected=True, timeChange=True) or []
            if not times:
                # Fallback to current time if no keys are selected on this curve specifically
                times = [current_time]
        elif time_range:
            # If a range is selected in timeline, get all keys in that range
            times = cmds.keyframe(plug, q=True, time=(time_range[0], time_range[1]), timeChange=True) or []
            if not times:
                # If no keys in range, affect the current time as a fallback
                times = [current_time]
        else:
            times = [current_time]

        affected_data[plug] = sorted(list(set(times)))

    # Ensure keys exist at all target times to avoid missing values during drag
    for plug, times in affected_data.items():
        missing = []
        for t in times:
            try:
                # Quick check if keyed at time t
                if not cmds.keyframe(plug, q=True, time=(t, t), timeChange=True):
                    missing.append(t)
            except Exception:
                missing.append(t)
        
        if missing:
            _ensure_keys_at_times(plug, missing)

    return affected_data, time_range


def _ensure_keys_at_times(attr_plug, times):
    for t in times:
        try:
            if not cmds.objExists(attr_plug):
                continue
            if cmds.getAttr(attr_plug, lock=True) or not cmds.getAttr(attr_plug, settable=True):
                continue
            if cmds.getAttr(attr_plug, type=True) in ("enum", "string", "message"):
                continue
            cmds.setKeyframe(attr_plug, time=t)
        except Exception:
            pass

# ---------------------------------------------------------------------------------------------------------------------
#                                                     Tween Logic                                                     #
# ---------------------------------------------------------------------------------------------------------------------


def prepare_tween_data(objs=None, attrs=None, attr_plugs=None, time_range=None):
    """Caches keyframe context for efficient tweening, supporting multiple keys."""
    utils.tween_frame_data_cache = {}
    
    if attr_plugs is not None:
        # If we got a dict {plug: [times]}, we use it directly
        if isinstance(attr_plugs, dict):
            affected_map = attr_plugs
        else:
            # If we got a list, we assume current time for each
            t = [cmds.currentTime(query=True)]
            affected_map = {p: t for p in attr_plugs}
    else:
        # Resolve from scratch
        affected_map, _tr = _resolve_affected_attribute_plugs()
        if time_range is None:
            time_range = _tr

    right_frame = _right_frame_from_time_range(time_range)

    for attr_full, times in affected_map.items():
        if not cmds.objExists(attr_full):
            continue

        keyframes = None # lazy load

        for current_time in times:
            try:
                current_v = cmds.getAttr(attr_full, time=current_time)
            except Exception:
                continue

            # Case A: Boundary-based Tweening (Selected Range)
            if time_range and right_frame is not None:
                try:
                    prev_v = cmds.getAttr(attr_full, time=time_range[0])
                    next_v = cmds.getAttr(attr_full, time=right_frame)
                    utils.tween_frame_data_cache[(attr_full, current_time)] = {
                        "previousValue": prev_v,
                        "nextValue": next_v,
                        "currentValue": current_v,
                        "needsCalculation": (prev_v is not None and next_v is not None),
                        "prev_f": time_range[0],
                        "next_f": right_frame,
                    }
                    continue
                except Exception:
                    pass

            # Case B: Neighbor-based Tweening (Individual Keys)
            if keyframes is None:
                keyframes = cmds.keyframe(attr_full, query=True) or []
            
            if not keyframes:
                utils.tween_frame_data_cache[(attr_full, current_time)] = {"needsCalculation": False, "use_direct_attr": True}
                continue

            prev_keys = [f for f in keyframes if f < current_time]
            next_keys = [f for f in keyframes if f > current_time]

            # If no neighbor on one side, fallback to the other
            if not prev_keys and not next_keys:
                utils.tween_frame_data_cache[(attr_full, current_time)] = {"needsCalculation": False}
                continue

            prev_f = max(prev_keys) if prev_keys else min(next_keys)
            next_f = min(next_keys) if next_keys else max(prev_keys)

            prev_v = cmds.getAttr(attr_full, time=prev_f)
            next_v = cmds.getAttr(attr_full, time=next_f)

            utils.tween_frame_data_cache[(attr_full, current_time)] = {
                "previousValue": prev_v,
                "nextValue": next_v,
                "currentValue": current_v,
                "needsCalculation": True,
                "use_direct_attr": False,
                "prev_f": prev_f,
                "next_f": next_f,
            }
    return utils.tween_frame_data_cache


def _interpolate_scalar(prev, nxt, t):
    return prev + (nxt - prev) * t


def _lerp_between(a, b, t):
    return a + (b - a) * t


def _lerp_towards(a, b, t, current):
    if t < 0.0:
        return _lerp_between(a, current, t + 1.0)
    if t > 0.0:
        return _lerp_between(current, b, t)
    return current


def _interpolate_matrix(prev_mat, next_mat, t):
    # Simple linear interpolation for world matrices (sufficient for most poses)
    return [prev_mat[i] + (next_mat[i] - prev_mat[i]) * t for i in range(16)]


def _snapshot_pose_buffer(affected_map):
    utils.pose_buffer = {}
    for attr_full, times in (affected_map or {}).items():
        if not cmds.objExists(attr_full):
            continue
        for current_time in times:
            try:
                value = cmds.getAttr(attr_full, time=current_time)
            except Exception:
                continue
            if isinstance(value, (int, float)):
                utils.pose_buffer[(attr_full, current_time)] = float(value)


def _prepare_targets():
    affected_map, time_range = _resolve_affected_attribute_plugs()
    if not affected_map:
        return None, None
    return affected_map, time_range


def execute_tween(value, world_space=False):
    """Core tweening logic. Disregards current value, blending between neighbors."""
    utils.start_dragging(title="Tweener" if not world_space else "World Space Tweener")
    
    if not utils.tween_frame_data_cache:
        # Resolve affected plugs if cache is empty (start of drag OR atomic click)
        affected_map, time_range = _prepare_targets()
        if not affected_map:
            return
        _snapshot_pose_buffer(affected_map)
        prepare_tween_data(attr_plugs=affected_map, time_range=time_range)

    # Scaling [-100, 100] to [0, 1] t-value between prev and next
    # -100 = 100% Prev, 0 = 50/50, 100 = 100% Next
    t = (float(value) + 100.0) / 200.0

    for (attr_full, time), cache in utils.tween_frame_data_cache.items():
        if not cache.get("needsCalculation", False):
            continue

        if not cmds.objExists(attr_full):
            continue
            
        prev_v = cache.get("previousValue")
        next_v = cache.get("nextValue")
        if prev_v is None or next_v is None:
            continue
        
        if world_space:
            try:
                obj = attr_full.split(".")[0]
                prev_m = cmds.getAttr(f"{obj}.worldMatrix[0]", time=cache.get("prev_f", time))
                next_m = cmds.getAttr(f"{obj}.worldMatrix[0]", time=cache.get("next_f", time))
                new_m = _interpolate_matrix(prev_m, next_m, t)
                
                # Use xform to apply world space matrix at time
                cmds.currentTime(time, edit=True)
                cmds.xform(obj, matrix=new_m, ws=True)
                cmds.setKeyframe(obj, time=time, respectKeyable=True)
                continue
            except Exception:
                pass

        new_v = _interpolate_scalar(prev_v, next_v, t)
        _apply_cached_value(attr_full, new_v, time, use_direct_attr=cache.get("use_direct_attr", False))


# ---------------------------------------------------------------------------------------------------------------------
#                                                     Blend Logic                                                     #
# ---------------------------------------------------------------------------------------------------------------------


def cache_keyframe_data(affected_map, time_range=None):
    """Caches values for blend-to-neighbors style operations, supporting multiple keys."""
    utils.frame_data_cache = {}
    
    right_frame = _right_frame_from_time_range(time_range)

    for attr_full, times in affected_map.items():
        if not cmds.objExists(attr_full):
            continue

        keyframes = None # lazy load

        for current_time in times:
            try:
                original_value = cmds.getAttr(attr_full, time=current_time)
            except Exception:
                continue

            previous_value = None
            next_value = None
            prev_tan_type = None
            prev_f = None
            next_f = None

            if time_range and right_frame is not None:
                try:
                    previous_value = cmds.getAttr(attr_full, time=time_range[0])
                    next_value = cmds.getAttr(attr_full, time=right_frame)
                    prev_f = time_range[0]
                    next_f = right_frame
                except Exception:
                    pass
            else:
                if keyframes is None:
                    keyframes = cmds.keyframe(attr_full, query=True) or []
                
                prev_ks = [f for f in keyframes if f < current_time]
                next_ks = [f for f in keyframes if f > current_time]

                prev_f = max(prev_ks) if prev_ks else None
                next_f = min(next_ks) if next_ks else None

                if prev_f is not None:
                    try:
                        previous_value = cmds.getAttr(attr_full, time=prev_f)
                        prev_tan_type = cmds.keyTangent(attr_full, query=True, time=(prev_f,), outTangentType=True)[0]
                    except Exception:
                        pass

                if next_f is not None:
                    try:
                        next_value = cmds.getAttr(attr_full, time=next_f)
                    except Exception:
                        pass

            utils.frame_data_cache[(attr_full, current_time)] = {
                "original_value": original_value,
                "previousValue": previous_value,
                "nextValue": next_value,
                "prevTanType": prev_tan_type,
                "prev_f": prev_f,
                "next_f": next_f,
                "use_direct_attr": not _has_keyframes(attr_full),
            }

    return utils.frame_data_cache


def _resolve_neighbor_blend_target(prev_value, next_value, percentage, attr_full=None):
    has_prev = isinstance(prev_value, (int, float))
    has_next = isinstance(next_value, (int, float))

    if percentage > 0:
        if has_next:
            return next_value
        if has_prev:
            return prev_value
    elif percentage < 0:
        if has_prev:
            return prev_value
        if has_next:
            return next_value

    # NEW: Fallback for "keys without neighbors" - blend towards default value
    if attr_full:
        try:
            node, attr = attr_full.split(".", 1)
            default_query = cmds.attributeQuery(attr, node=node, listDefault=True)
            if default_query:
                return default_query[0]
        except Exception:
            pass
        return 0.0 # Extreme fallback

    return None


def _resolve_neighbor_blend_pair(prev_value, next_value, attr_full=None):
    left_target = _resolve_neighbor_blend_target(prev_value, next_value, -1.0, attr_full=attr_full)
    right_target = _resolve_neighbor_blend_target(prev_value, next_value, 1.0, attr_full=attr_full)
    return left_target, right_target


def _apply_world_space_blend(attr_full, time, target_frame, blend):
    try:
        obj = attr_full.split(".")[0]
        if target_frame is None:
            return False
        orig_m = cmds.getAttr(f"{obj}.worldMatrix[0]", time=time)
        target_m = cmds.getAttr(f"{obj}.worldMatrix[0]", time=target_frame)
        new_m = _interpolate_matrix(orig_m, target_m, abs(blend))
        cmds.currentTime(time, edit=True)
        cmds.xform(obj, matrix=new_m, ws=True)
        cmds.setKeyframe(obj, time=time, respectKeyable=True)
        return True
    except Exception:
        return False


def execute_blend_to_neighbors(percentage, world_space=False):
    """Blends the affected keys toward their previous/next neighbors."""
    utils.start_dragging(title="Blend to Neighbors")
    
    if not utils.is_cached:
        affected_map, time_range = _prepare_targets()
        if not affected_map:
            return
        _snapshot_pose_buffer(affected_map)
        cache_keyframe_data(affected_map, time_range=time_range)
        utils.is_cached = True

    for (attr_full, time), cache in utils.frame_data_cache.items():
        if cmds.getAttr(attr_full, lock=True) or not cmds.getAttr(attr_full, settable=True):
            continue

        orig = cache.get("original_value")
        nxt = cache.get("nextValue")
        prev = cache.get("previousValue")

        if not isinstance(orig, (int, float)):
            continue

        left_target, right_target = _resolve_neighbor_blend_pair(prev, nxt, attr_full=attr_full)
        if left_target is None and right_target is None:
            continue

        t = float(percentage) / 100.0

        if world_space:
            target_f = cache.get("next_f") if percentage > 0 else cache.get("prev_f")
            if _apply_world_space_blend(attr_full, time, target_f, t):
                continue

        new_v = _lerp_towards(left_target, right_target, t, orig)
        _apply_cached_value(attr_full, new_v, time, use_direct_attr=cache.get("use_direct_attr", False))


def execute_blend_to_ease(percentage, world_space=False):
    """Tweener-inspired curve/ease mode based on the current key time within its neighbor segment."""
    utils.start_dragging(title="Blend to Ease")

    if not utils.is_cached:
        affected_map, time_range = _prepare_targets()
        if not affected_map:
            return
        _snapshot_pose_buffer(affected_map)
        cache_keyframe_data(affected_map, time_range=time_range)
        utils.is_cached = True

    blend = float(percentage) / 100.0
    for (attr_full, time), cache in utils.frame_data_cache.items():
        orig = cache.get("original_value")
        prev_v = cache.get("previousValue")
        next_v = cache.get("nextValue")
        prev_f = cache.get("prev_f")
        next_f = cache.get("next_f")

        if not isinstance(orig, (int, float)) or not isinstance(prev_v, (int, float)) or not isinstance(next_v, (int, float)):
            continue
        if prev_f is None or next_f is None or prev_f == next_f:
            continue

        segment_t = (float(time) - float(prev_f)) / float(next_f - prev_f)
        segment_t = max(0.0, min(1.0, segment_t))
        ease_in = segment_t * segment_t * segment_t
        inv = 1.0 - segment_t
        ease_out = 1.0 - (inv * inv * inv)
        left_target = _lerp_between(prev_v, next_v, ease_in)
        right_target = _lerp_between(prev_v, next_v, ease_out)
        new_v = _lerp_towards(left_target, right_target, blend, orig)
        _apply_cached_value(attr_full, new_v, time, use_direct_attr=cache.get("use_direct_attr", False))


def execute_blend_to_default(percentage, world_space=False):
    """Blends the current pose toward each attribute's default value."""
    utils.start_dragging(title="Blend to Default")
    
    if not utils.is_cached:
        affected_map, _time_range = _prepare_targets()
        if not affected_map:
            return
        _snapshot_pose_buffer(affected_map)
        
        utils.frame_data_cache = {}
        for attr_full, times in affected_map.items():
            if not cmds.objExists(attr_full):
                continue
            if cmds.getAttr(attr_full, lock=True) or not cmds.getAttr(attr_full, settable=True):
                continue
            
            a_type = cmds.getAttr(attr_full, type=True)
            if a_type in ("enum", "string", "message"):
                continue

            node, attr = attr_full.split(".", 1)
            default_query = cmds.attributeQuery(attr, node=node, listDefault=True)
            if not default_query:
                continue
            default_value = float(default_query[0])
            
            has_keys = _has_keyframes(attr_full)

            for current_time in times:
                try:
                    original_value = float(cmds.getAttr(attr_full, time=current_time))
                    utils.frame_data_cache[(attr_full, current_time)] = {
                        "original_value": original_value,
                        "defaultValue": default_value,
                        "use_direct_attr": not has_keys,
                    }
                except Exception:
                    pass
        utils.is_cached = True

    t = float(percentage) / 100.0
    for (attr_full, current_time), cache in utils.frame_data_cache.items():
        if "defaultValue" not in cache:
            continue
        
        orig = cache.get("original_value")
        default_value = cache.get("defaultValue")
        
        mirrored = (2.0 * orig) - default_value
        new_value = _lerp_towards(mirrored, default_value, t, orig)
        
        _apply_cached_value(attr_full, new_value, current_time, use_direct_attr=cache.get("use_direct_attr", False))


def execute_blend_to_key(percentage, objs=None):
    """Back-compat alias."""
    return execute_blend_to_neighbors(percentage)


def execute_blend_to_frame(percentage, left_frame=None, right_frame=None, objs=None, world_space=False):
    """Blends current values toward values at specific frames, for all affected keys."""
    utils.start_dragging(title="Blend to Frame")
    
    if not utils.is_cached:
        affected_map, _tr = _prepare_targets()
        if not affected_map:
            return
        _snapshot_pose_buffer(affected_map)
        
        if left_frame is None or right_frame is None:
            return execute_blend_to_neighbors(percentage)

        utils.frame_data_cache = {}
        for attr_full, times in affected_map.items():
            if not cmds.objExists(attr_full):
                continue
            
            try:
                l_val = cmds.getAttr(attr_full, time=left_frame)
                r_val = cmds.getAttr(attr_full, time=right_frame)
            except Exception:
                continue
                
            has_keys = _has_keyframes(attr_full)
            for t in times:
                try:
                    orig = cmds.getAttr(attr_full, time=t)
                    utils.frame_data_cache[(attr_full, t)] = {
                        "original_value": orig,
                        "leftValue": l_val,
                        "rightValue": r_val,
                        "leftFrame": left_frame,
                        "rightFrame": right_frame,
                        "use_direct_attr": not has_keys,
                    }
                except Exception:
                    pass
        utils.is_cached = True

    for (attr_full, time), cache in utils.frame_data_cache.items():
        orig = cache.get("original_value")
        target_v = cache.get("rightValue") if percentage > 0 else cache.get("leftValue")
        
        if target_v is None or orig is None:
            continue

        t = float(percentage) / 100.0
        if world_space:
            target_f = cache.get("rightFrame") if percentage > 0 else cache.get("leftFrame")
            if _apply_world_space_blend(attr_full, time, target_f, t):
                continue
        new_v = _lerp_towards(cache.get("leftValue"), cache.get("rightValue"), t, orig)
        _apply_cached_value(attr_full, new_v, time, use_direct_attr=cache.get("use_direct_attr", False))


def execute_blend_to_infinity(percentage, world_space=False):
    """Blend toward simple pre/post-infinity extrapolated values."""
    utils.start_dragging(title="Blend to Infinity")

    if not utils.is_cached:
        affected_map, time_range = _prepare_targets()
        if not affected_map:
            return
        _snapshot_pose_buffer(affected_map)
        cache_keyframe_data(affected_map, time_range=time_range)
        utils.is_cached = True

    t = float(percentage) / 100.0
    for (attr_full, time), cache in utils.frame_data_cache.items():
        orig = cache.get("original_value")
        prev_v = cache.get("previousValue")
        next_v = cache.get("nextValue")
        if not isinstance(orig, (int, float)):
            continue

        left_target = None
        right_target = None
        if isinstance(prev_v, (int, float)) and isinstance(next_v, (int, float)):
            delta = next_v - prev_v
            left_target = prev_v - delta
            right_target = next_v + delta
        elif isinstance(prev_v, (int, float)):
            left_target = prev_v
            right_target = prev_v
        elif isinstance(next_v, (int, float)):
            left_target = next_v
            right_target = next_v
        if left_target is None and right_target is None:
            continue

        new_v = _lerp_towards(left_target, right_target, t, orig)
        _apply_cached_value(attr_full, new_v, time, use_direct_attr=cache.get("use_direct_attr", False))


def execute_blend_to_buffer(percentage, world_space=False):
    """Blend toward the last stored pose snapshot from a previous slider interaction."""
    utils.start_dragging(title="Blend to Buffer")

    affected_map, _time_range = _prepare_targets()
    if not affected_map:
        return

    if not utils.is_cached:
        utils.frame_data_cache = {}
        for attr_full, times in affected_map.items():
            has_keys = _has_keyframes(attr_full)
            for current_time in times:
                try:
                    orig = cmds.getAttr(attr_full, time=current_time)
                except Exception:
                    continue
                buffer_value = utils.pose_buffer.get((attr_full, current_time), orig)
                utils.frame_data_cache[(attr_full, current_time)] = {
                    "original_value": orig,
                    "bufferValue": buffer_value,
                    "use_direct_attr": not has_keys,
                }
        utils.is_cached = True

    t = max(-1.0, min(1.0, float(percentage) / 100.0))
    for (attr_full, current_time), cache in utils.frame_data_cache.items():
        orig = cache.get("original_value")
        buffer_value = cache.get("bufferValue")
        if not isinstance(orig, (int, float)) or not isinstance(buffer_value, (int, float)):
            continue
        mirror_value = (2.0 * orig) - buffer_value
        new_value = _lerp_towards(mirror_value, buffer_value, t, orig)
        _apply_cached_value(attr_full, new_value, current_time, use_direct_attr=cache.get("use_direct_attr", False))


def execute_blend_to_undo(percentage, world_space=False):
    """Blend back toward the last pose snapshot, acting like a soft undo target."""
    return execute_blend_to_buffer(percentage, world_space=world_space)


def blend_slider_reset(slider_name=None):
    """Cleanup after slider interaction, handling tangent restoration."""
    if utils.frame_data_cache:
        for (attr_full, time), cache in utils.frame_data_cache.items():
            if cache.get("prevTanType") == "step":
                try:
                    cmds.keyTangent(attr_full, edit=True, time=(time,), inTangentType="stepnext", outTangentType="stepnext")
                except Exception:
                    pass

    utils.stop_dragging()
    if slider_name and cmds.floatSlider(slider_name, exists=True):
        cmds.floatSlider(slider_name, edit=True, value=0)
