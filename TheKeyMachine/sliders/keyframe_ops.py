"""
TheKeyMachine - Keyframe-level Slider Operations

Tweening and blending operations translated from keyToolsMod.
"""

import maya.cmds as cmds

from . import utils
from .utils import TweenFrameData, BlendFrameData

# ---------------------------------------------------------------------------------------------------------------------
#                                                Keyframe Target Resolution                                           #
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


# Removed local _resolve_contiguous_neighbors in favor of utils.get_block_neighbors


def _resolve_keyframe_targets_for_session(session):
    """Cache the resolved keyframe target map on the session."""
    if not session.targets.resolved:
        affected_map, time_range = utils.resolve_keyframe_targets()
        session.targets.affected_map = affected_map
        session.targets.time_range = time_range
        session.targets.resolved = True
    return session.targets.affected_map, session.targets.time_range


def _ensure_keys_at_times(attr_plugs, times):
    """Ensures keys exist at specified times for all given attribute plugs."""
    if isinstance(attr_plugs, str):
        attr_plugs = [attr_plugs]

    for attr in attr_plugs:
        if not cmds.objExists(attr) or cmds.getAttr(attr, lock=True) or not cmds.getAttr(attr, settable=True):
            continue
        if cmds.getAttr(attr, type=True) in ("enum", "string", "message"):
            continue

        for t in times:
            try:
                cmds.setKeyframe(attr, time=t)
            except Exception:
                pass


# ---------------------------------------------------------------------------------------------------------------------
#                                              Keyframe Value Helpers                                                 #
# ---------------------------------------------------------------------------------------------------------------------


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
    try:
        cmds.setKeyframe(attr_full, time=(current_time,), value=float(value), absolute=True)
    except Exception:
        try:
            cmds.keyframe(attr_full, edit=True, time=(current_time, current_time), valueChange=float(value), absolute=True)
        except Exception:
            pass


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


def _interpolate_matrix(prev_mat, next_mat, t):
    # Simple linear interpolation for world matrices (sufficient for most poses)
    return [prev_mat[i] + (next_mat[i] - prev_mat[i]) * t for i in range(16)]


# ---------------------------------------------------------------------------------------------------------------------
#                                                Keyframe Data Caches                                                 #
# ---------------------------------------------------------------------------------------------------------------------


def prepare_tween_data(session, objs=None, attrs=None, attr_plugs=None, time_range=None):
    """Caches keyframe context for efficient tweening, supporting multiple keys."""
    session.cache.tween_frame_data.clear()

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
        affected_map, _tr = utils.resolve_keyframe_targets()
        if time_range is None:
            time_range = _tr

    right_frame = _right_frame_from_time_range(time_range)

    for attr_full, times in affected_map.items():
        if not cmds.objExists(attr_full):
            continue

        keyframes = None  # lazy load

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
                    session.cache.tween_frame_data[(attr_full, current_time)] = TweenFrameData(
                        previousValue=prev_v,
                        nextValue=next_v,
                        currentValue=current_v,
                        needsCalculation=(prev_v is not None and next_v is not None),
                        prev_f=time_range[0],
                        next_f=right_frame,
                    )
                    continue
                except Exception:
                    pass

            # Case B: Neighbor-based Tweening (Individual Keys)
            if keyframes is None:
                keyframes = sorted([float(k) for k in (cmds.keyframe(attr_full, query=True) or [])])
                target_times_set = set(float(t) for t in times)

            if not keyframes:
                session.cache.tween_frame_data[(attr_full, current_time)] = TweenFrameData(needsCalculation=False, use_direct_attr=True)
                continue

            prev_f, next_f = utils.get_block_neighbors(current_time, target_times_set, keyframes)

            # If no neighbor on one side, fallback to the other
            if prev_f is None and next_f is None:
                session.cache.tween_frame_data[(attr_full, current_time)] = TweenFrameData(needsCalculation=False)
                continue

            if prev_f is None:
                prev_f = next_f
            elif next_f is None:
                next_f = prev_f

            prev_v = cmds.getAttr(attr_full, time=prev_f)
            next_v = cmds.getAttr(attr_full, time=next_f)

            session.cache.tween_frame_data[(attr_full, current_time)] = TweenFrameData(
                previousValue=prev_v,
                nextValue=next_v,
                currentValue=current_v,
                needsCalculation=True,
                use_direct_attr=False,
                prev_f=prev_f,
                next_f=next_f,
            )
    return session.cache.tween_frame_data


def cache_neighbor_keyframe_data(session, affected_map, time_range=None):
    """Caches values for blend-to-neighbors style operations, supporting multiple keys."""
    session.cache.frame_data.clear()

    right_frame = _right_frame_from_time_range(time_range)

    for attr_full, times in affected_map.items():
        if not cmds.objExists(attr_full):
            continue

        keyframes = None  # lazy load

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
                    keyframes = sorted([float(k) for k in (cmds.keyframe(attr_full, query=True) or [])])
                    target_times_set = set(float(t) for t in times)

                prev_f, next_f = utils.get_block_neighbors(current_time, target_times_set, keyframes)

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

            session.cache.frame_data[(attr_full, current_time)] = BlendFrameData(
                original_value=original_value,
                previousValue=previous_value,
                nextValue=next_value,
                prevTanType=prev_tan_type,
                prev_f=prev_f,
                next_f=next_f,
                use_direct_attr=not _has_keyframes(attr_full),
            )

    return session.cache.frame_data


# ---------------------------------------------------------------------------------------------------------------------
#                                                     Tween Logic                                                     #
# ---------------------------------------------------------------------------------------------------------------------


def apply_tween(session, value, world_space=False):
    """Core tweening logic. Disregards current value, blending between neighbors."""
    if not session.cache.tween_frame_data:
        affected_map, time_range = _resolve_keyframe_targets_for_session(session)
        if not affected_map:
            return
        session.snapshot_pose_buffer(affected_map)
        prepare_tween_data(session, attr_plugs=affected_map, time_range=time_range)

    t = (float(value) + 100.0) / 200.0
    initial_time = cmds.currentTime(query=True)

    try:
        for (attr_full, time), cache in session.cache.tween_frame_data.items():
            if not cache.needsCalculation or not cmds.objExists(attr_full):
                continue

            prev_v, next_v = cache.previousValue, cache.nextValue
            if prev_v is None or next_v is None:
                continue

            if world_space:
                obj = attr_full.split(".")[0]
                prev_m = cmds.getAttr(f"{obj}.worldMatrix[0]", time=cache.prev_f if cache.prev_f is not None else time)
                next_m = cmds.getAttr(f"{obj}.worldMatrix[0]", time=cache.next_f if cache.next_f is not None else time)
                new_m = _interpolate_matrix(prev_m, next_m, t)

                if cmds.currentTime(query=True) != time:
                    cmds.currentTime(time, edit=True)
                cmds.xform(obj, matrix=new_m, ws=True)
                cmds.setKeyframe(obj, time=time, respectKeyable=True)
            else:
                new_v = utils.lerp(prev_v, next_v, t)
                _apply_cached_value(attr_full, new_v, time, use_direct_attr=cache.use_direct_attr)
    finally:
        if world_space and cmds.currentTime(query=True) != initial_time:
            cmds.currentTime(initial_time, edit=True)


# ---------------------------------------------------------------------------------------------------------------------
#                                                     Blend Logic                                                     #
# ---------------------------------------------------------------------------------------------------------------------


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

    if attr_full:
        try:
            node, attr = attr_full.split(".", 1)
            default_query = cmds.attributeQuery(attr, node=node, listDefault=True)
            if default_query:
                return default_query[0]
        except Exception:
            pass
        return 0.0  # Extreme fallback

    return None


def _resolve_neighbor_blend_pair(prev_value, next_value, attr_full=None):
    left_target = _resolve_neighbor_blend_target(prev_value, next_value, -1.0, attr_full=attr_full)
    right_target = _resolve_neighbor_blend_target(prev_value, next_value, 1.0, attr_full=attr_full)
    return left_target, right_target


def apply_blend_to_neighbors(session, percentage, world_space=False):
    """Blends the affected keys toward their previous/next neighbors."""
    if not session.cache.is_cached:
        affected_map, time_range = _resolve_keyframe_targets_for_session(session)
        if not affected_map:
            return
        session.snapshot_pose_buffer(affected_map)
        cache_neighbor_keyframe_data(session, affected_map, time_range=time_range)
        session.cache.is_cached = True

    for (attr_full, time), cache in session.cache.frame_data.items():
        if cmds.getAttr(attr_full, lock=True) or not cmds.getAttr(attr_full, settable=True):
            continue

        orig = cache.original_value
        nxt = cache.nextValue
        prev = cache.previousValue

        if not isinstance(orig, (int, float)):
            continue

        left_target, right_target = _resolve_neighbor_blend_pair(prev, nxt, attr_full=attr_full)
        if left_target is None and right_target is None:
            continue

        t = float(percentage) / 100.0

        if world_space:
            target_f = cache.next_f if percentage > 0 else cache.prev_f
            if _apply_world_space_blend(attr_full, time, target_f, t):
                continue

        new_v = utils.lerp_towards(left_target, right_target, t, orig)
        _apply_cached_value(attr_full, new_v, time, use_direct_attr=cache.use_direct_attr)


def apply_blend_to_ease(session, percentage, world_space=False):
    """Tweener-inspired curve/ease mode based on the current key time within its neighbor segment."""
    if not session.cache.is_cached:
        affected_map, time_range = _resolve_keyframe_targets_for_session(session)
        if not affected_map:
            return
        session.snapshot_pose_buffer(affected_map)
        cache_neighbor_keyframe_data(session, affected_map, time_range=time_range)
        session.cache.is_cached = True

    blend = float(percentage) / 100.0
    for (attr_full, time), cache in session.cache.frame_data.items():
        orig = cache.original_value
        prev_v = cache.previousValue
        next_v = cache.nextValue
        prev_f = cache.prev_f
        next_f = cache.next_f

        if not isinstance(orig, (int, float)) or not isinstance(prev_v, (int, float)) or not isinstance(next_v, (int, float)):
            continue
        if prev_f is None or next_f is None or prev_f == next_f:
            continue

        segment_t = (float(time) - float(prev_f)) / float(next_f - prev_f)
        segment_t = max(0.0, min(1.0, segment_t))
        ease_in = segment_t * segment_t * segment_t
        inv = 1.0 - segment_t
        ease_out = 1.0 - (inv * inv * inv)
        left_target = utils.lerp(prev_v, next_v, ease_in)
        right_target = utils.lerp(prev_v, next_v, ease_out)
        new_v = utils.lerp_towards(left_target, right_target, blend, orig)
        _apply_cached_value(attr_full, new_v, time, use_direct_attr=cache.use_direct_attr)


def apply_blend_to_default(session, percentage, world_space=False):
    """Blends the current pose toward each attribute's default value."""
    if not session.cache.is_cached:
        affected_map, _time_range = _resolve_keyframe_targets_for_session(session)
        if not affected_map:
            return
        session.snapshot_pose_buffer(affected_map)

        session.cache.frame_data.clear()
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
                    session.cache.frame_data[(attr_full, current_time)] = BlendFrameData(
                        original_value=original_value,
                        defaultValue=default_value,
                        use_direct_attr=not has_keys,
                    )
                except Exception:
                    pass
        session.cache.is_cached = True

    t = float(percentage) / 100.0
    for (attr_full, current_time), cache in session.cache.frame_data.items():
        if cache.defaultValue is None:
            continue

        orig = cache.original_value
        default_value = cache.defaultValue

        mirrored = (2.0 * orig) - default_value
        new_value = utils.lerp_towards(mirrored, default_value, t, orig)

        _apply_cached_value(attr_full, new_value, current_time, use_direct_attr=cache.use_direct_attr)


def apply_blend_to_key(session, percentage, objs=None):
    return apply_blend_to_neighbors(session, percentage)


def apply_blend_to_frame(session, percentage, left_frame=None, right_frame=None, objs=None, world_space=False):
    """Blends current values toward values at specific frames, for all affected keys."""
    if not session.cache.is_cached:
        affected_map, _tr = _resolve_keyframe_targets_for_session(session)
        if not affected_map:
            return
        session.snapshot_pose_buffer(affected_map)

        if left_frame is None or right_frame is None:
            return apply_blend_to_neighbors(session, percentage)

        session.cache.frame_data.clear()
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
                    session.cache.frame_data[(attr_full, t)] = BlendFrameData(
                        original_value=orig,
                        leftValue=l_val,
                        rightValue=r_val,
                        leftFrame=left_frame,
                        rightFrame=right_frame,
                        use_direct_attr=not has_keys,
                    )
                except Exception:
                    pass
        session.cache.is_cached = True

    for (attr_full, time), cache in session.cache.frame_data.items():
        orig = cache.original_value
        target_v = cache.rightValue if percentage > 0 else cache.leftValue

        if target_v is None or orig is None:
            continue

        t = float(percentage) / 100.0
        if world_space:
            target_f = cache.rightFrame if percentage > 0 else cache.leftFrame
            if _apply_world_space_blend(attr_full, time, target_f, t):
                continue
        new_v = utils.lerp_towards(cache.leftValue, cache.rightValue, t, orig)
        _apply_cached_value(attr_full, new_v, time, use_direct_attr=cache.use_direct_attr)


def apply_blend_to_infinity(session, percentage, world_space=False):
    """Blend toward simple pre/post-infinity extrapolated values."""
    if not session.cache.is_cached:
        affected_map, time_range = _resolve_keyframe_targets_for_session(session)
        if not affected_map:
            return
        session.snapshot_pose_buffer(affected_map)
        cache_neighbor_keyframe_data(session, affected_map, time_range=time_range)
        session.cache.is_cached = True

    t = float(percentage) / 100.0
    for (attr_full, time), cache in session.cache.frame_data.items():
        orig = cache.original_value
        prev_v = cache.previousValue
        next_v = cache.nextValue
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

        new_v = utils.lerp_towards(left_target, right_target, t, orig)
        _apply_cached_value(attr_full, new_v, time, use_direct_attr=cache.use_direct_attr)


def apply_blend_to_buffer(session, percentage, world_space=False):
    """Blend toward the last stored pose snapshot from a previous slider interaction."""
    affected_map, _time_range = _resolve_keyframe_targets_for_session(session)
    if not affected_map:
        return

    if not session.cache.is_cached:
        session.cache.frame_data.clear()
        for attr_full, times in affected_map.items():
            has_keys = _has_keyframes(attr_full)
            for current_time in times:
                try:
                    orig = cmds.getAttr(attr_full, time=current_time)
                except Exception:
                    continue
                buffer_value = session.cache.pose_buffer.get((attr_full, current_time), orig)
                session.cache.frame_data[(attr_full, current_time)] = BlendFrameData(
                    original_value=orig,
                    bufferValue=buffer_value,
                    use_direct_attr=not has_keys,
                )
        session.cache.is_cached = True

    t = max(-1.0, min(1.0, float(percentage) / 100.0))
    for (attr_full, current_time), cache in session.cache.frame_data.items():
        orig = cache.original_value
        buffer_value = cache.bufferValue
        if not isinstance(orig, (int, float)) or not isinstance(buffer_value, (int, float)):
            continue
        mirror_value = (2.0 * orig) - buffer_value
        new_value = utils.lerp_towards(mirror_value, buffer_value, t, orig)
        _apply_cached_value(attr_full, new_value, current_time, use_direct_attr=cache.use_direct_attr)


def apply_blend_to_undo(session, percentage, world_space=False):
    """Blend back toward the last pose snapshot, acting like a soft undo target."""
    return apply_blend_to_buffer(session, percentage, world_space=world_space)


def blend_slider_reset(session, slider_name=None):
    """Cleanup after slider interaction, handling tangent restoration."""
    if session.cache.frame_data:
        for (attr_full, time), cache in session.cache.frame_data.items():
            if cache.prevTanType == "step":
                try:
                    cmds.keyTangent(attr_full, edit=True, time=(time,), inTangentType="stepnext", outTangentType="stepnext")
                except Exception:
                    pass

    session.finish()
    if slider_name and cmds.floatSlider(slider_name, exists=True):
        cmds.floatSlider(slider_name, edit=True, value=0)
