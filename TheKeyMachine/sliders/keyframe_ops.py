"""
TheKeyMachine - Keyframe-level Slider Operations

Tweening and blending operations translated from keyToolsMod.
"""

import math

import maya.cmds as cmds
try:
    from maya.api import OpenMaya as om
except ImportError:
    om = None

import TheKeyMachine.core.runtimeManager as runtime
from . import mode_values, utils
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
        affected_map, time_range = utils.resolve_keyframe_targets(session)
        session.targets.affected_map = affected_map
        session.targets.time_range = time_range
        session.targets.resolved = True
    return session.targets.affected_map, session.targets.time_range


# ---------------------------------------------------------------------------------------------------------------------
#                                              Keyframe Value Helpers                                                 #
# ---------------------------------------------------------------------------------------------------------------------


def _has_keyframes(attr_full):
    try:
        return bool(cmds.keyframe(attr_full, query=True) or [])
    except Exception:
        return False


def _apply_world_space_blend(attr_full, time, target_frame, blend):
    initial_time = cmds.currentTime(query=True)
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
    finally:
        if cmds.currentTime(query=True) != initial_time:
            cmds.currentTime(initial_time, edit=True)


def _interpolate_matrix(prev_mat, next_mat, t):
    """Interpolate decomposed transforms with quaternion rotation."""
    prev_values = list(prev_mat[0]) if len(prev_mat) == 1 and hasattr(prev_mat[0], "__iter__") else list(prev_mat)
    next_values = list(next_mat[0]) if len(next_mat) == 1 and hasattr(next_mat[0], "__iter__") else list(next_mat)
    if om is None or len(prev_values) != 16 or len(next_values) != 16:
        return [prev_values[i] + (next_values[i] - prev_values[i]) * t for i in range(min(len(prev_values), len(next_values)))]
    try:
        previous = om.MTransformationMatrix(om.MMatrix(prev_values))
        following = om.MTransformationMatrix(om.MMatrix(next_values))
        result = om.MTransformationMatrix()
        prev_translation = previous.translation(om.MSpace.kWorld)
        next_translation = following.translation(om.MSpace.kWorld)
        result.setTranslation(prev_translation + (next_translation - prev_translation) * t, om.MSpace.kWorld)
        prev_rotation = previous.rotation(asQuaternion=True)
        next_rotation = following.rotation(asQuaternion=True)
        rotation = om.MQuaternion.slerp(prev_rotation, next_rotation, t)
        result.setRotationQuaternion(rotation.x, rotation.y, rotation.z, rotation.w)
        prev_scale = previous.scale(om.MSpace.kWorld)
        next_scale = following.scale(om.MSpace.kWorld)
        result.setScale(tuple(utils.lerp(a, b, t) for a, b in zip(prev_scale, next_scale)), om.MSpace.kWorld)
        prev_shear = previous.shear(om.MSpace.kWorld)
        next_shear = following.shear(om.MSpace.kWorld)
        result.setShear(tuple(utils.lerp(a, b, t) for a, b in zip(prev_shear, next_shear)), om.MSpace.kWorld)
        return list(result.asMatrix())
    except Exception:
        return [prev_values[i] + (next_values[i] - prev_values[i]) * t for i in range(16)]


def _remap_time(time, target_times, source_start, source_end):
    target_start, target_end = min(target_times), max(target_times)
    if target_end == target_start:
        return max(source_start, min(source_end, float(time)))
    ratio = (float(time) - target_start) / float(target_end - target_start)
    return source_start + ratio * (source_end - source_start)


def _scaled_angle(angle, source_span, target_span):
    if angle is None or source_span <= 0.0 or target_span <= 0.0:
        return angle
    return math.degrees(math.atan(math.tan(math.radians(float(angle))) * source_span / target_span))


def _capture_buffer_curve_targets(curve, target_times):
    """Sample a Maya buffer curve onto existing target times without moving keys."""
    target_times = sorted(set(float(time) for time in target_times or []))
    if not curve or not target_times:
        return {}
    try:
        if not cmds.bufferCurve(curve, query=True, exists=True):
            return {}
    except Exception:
        return {}

    swapped = False
    try:
        cmds.bufferCurve(curve, swap=True)
        swapped = True
        source_keys = sorted(float(time) for time in (cmds.keyframe(curve, query=True, timeChange=True) or []))
        if not source_keys:
            return {}
        source_start, source_end = source_keys[0], source_keys[-1]
        source_times = [_remap_time(time, target_times, source_start, source_end) for time in target_times]
        from TheKeyMachine.core import curveFitting

        source_shape = curveFitting.capture([curve], source_times).get(curve, {})
        source_span = max(0.0, source_end - source_start)
        target_span = max(0.0, max(target_times) - min(target_times))
        result = {}
        for target_time, source_time in zip(target_times, source_times):
            sample = source_shape.get(float(source_time))
            if not sample:
                continue
            result[target_time] = {
                "value": sample.get("value"),
                "in_angle": _scaled_angle(sample.get("in_angle"), source_span, target_span),
                "out_angle": _scaled_angle(sample.get("out_angle"), source_span, target_span),
            }
        return result
    finally:
        if swapped:
            try:
                cmds.bufferCurve(curve, swap=True)
            except Exception:
                pass


def _apply_preserved_blended_tangents(curve, time, target, blend):
    """Rotate already-manual tangents toward a fitted target without changing types."""
    if not curve or not target:
        return
    try:
        in_types = cmds.keyTangent(curve, query=True, time=(time, time), inTangentType=True) or []
        out_types = cmds.keyTangent(curve, query=True, time=(time, time), outTangentType=True) or []
        in_angles = cmds.keyTangent(curve, query=True, time=(time, time), inAngle=True) or []
        out_angles = cmds.keyTangent(curve, query=True, time=(time, time), outAngle=True) or []
        amount = min(1.0, max(0.0, abs(float(blend))))
        kwargs = {"absolute": True}
        if in_types and in_types[0] == "fixed" and in_angles and target.get("in_angle") is not None:
            target_angle = float(target["in_angle"])
            if blend < 0.0:
                target_angle = (2.0 * float(in_angles[0])) - target_angle
            kwargs["inAngle"] = utils.lerp(in_angles[0], target_angle, amount)
        if out_types and out_types[0] == "fixed" and out_angles and target.get("out_angle") is not None:
            target_angle = float(target["out_angle"])
            if blend < 0.0:
                target_angle = (2.0 * float(out_angles[0])) - target_angle
            kwargs["outAngle"] = utils.lerp(out_angles[0], target_angle, amount)
        if len(kwargs) > 1:
            cmds.keyTangent(curve, edit=True, time=(time, time), **kwargs)
    except Exception:
        pass


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
        affected_map, _tr = utils.resolve_keyframe_targets(session)
        if time_range is None:
            time_range = _tr

    right_frame = _right_frame_from_time_range(time_range)

    for attr_full, times in affected_map.items():
        if not cmds.objExists(attr_full):
            continue

        keyframes = None  # lazy load
        curve, curve_fn = mode_values.curve_fn_for_attr(attr_full)

        for current_time in times:
            try:
                current_v = mode_values.curve_value_at_time(curve_fn, current_time, cmds.getAttr(attr_full, time=current_time))
            except Exception:
                continue
            key_index = mode_values.find_or_add_key_index(session, curve_fn, current_time)
            if key_index is not None:
                current_v = mode_values.curve_value(curve_fn, key_index, current_v)

            # Case A: Boundary-based Tweening (Selected Range)
            if time_range and right_frame is not None:
                try:
                    prev_v = mode_values.curve_value_at_time(curve_fn, time_range[0], cmds.getAttr(attr_full, time=time_range[0]))
                    next_v = mode_values.curve_value_at_time(curve_fn, right_frame, cmds.getAttr(attr_full, time=right_frame))
                    session.cache.tween_frame_data[(attr_full, current_time)] = TweenFrameData(
                        previousValue=prev_v,
                        nextValue=next_v,
                        currentValue=current_v,
                        needsCalculation=(prev_v is not None and next_v is not None),
                        prev_f=time_range[0],
                        next_f=right_frame,
                        curve=curve,
                        keyIndex=key_index,
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

            prev_v = mode_values.curve_value_at_time(curve_fn, prev_f, cmds.getAttr(attr_full, time=prev_f))
            next_v = mode_values.curve_value_at_time(curve_fn, next_f, cmds.getAttr(attr_full, time=next_f))

            session.cache.tween_frame_data[(attr_full, current_time)] = TweenFrameData(
                previousValue=prev_v,
                nextValue=next_v,
                currentValue=current_v,
                needsCalculation=True,
                use_direct_attr=False,
                prev_f=prev_f,
                next_f=next_f,
                curve=curve,
                keyIndex=key_index,
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
        curve, curve_fn = mode_values.curve_fn_for_attr(attr_full)

        for current_time in times:
            try:
                original_value = mode_values.curve_value_at_time(curve_fn, current_time, cmds.getAttr(attr_full, time=current_time))
            except Exception:
                continue
            key_index = mode_values.find_or_add_key_index(session, curve_fn, current_time)
            if key_index is not None:
                original_value = mode_values.curve_value(curve_fn, key_index, original_value)

            previous_value = None
            next_value = None
            prev_tan_type = None
            prev_f = None
            next_f = None

            if time_range and right_frame is not None:
                try:
                    previous_value = mode_values.curve_value_at_time(curve_fn, time_range[0], cmds.getAttr(attr_full, time=time_range[0]))
                    next_value = mode_values.curve_value_at_time(curve_fn, right_frame, cmds.getAttr(attr_full, time=right_frame))
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
                        previous_value = mode_values.curve_value_at_time(curve_fn, prev_f, cmds.getAttr(attr_full, time=prev_f))
                        prev_tan_type = cmds.keyTangent(attr_full, query=True, time=(prev_f,), outTangentType=True)[0]
                    except Exception:
                        pass

                if next_f is not None:
                    try:
                        next_value = mode_values.curve_value_at_time(curve_fn, next_f, cmds.getAttr(attr_full, time=next_f))
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
                curve=curve,
                keyIndex=key_index,
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
    processed_world_targets = set()

    try:
        for (attr_full, time), cache in session.cache.tween_frame_data.items():
            if not cache.needsCalculation or not cmds.objExists(attr_full):
                continue

            prev_v, next_v = cache.previousValue, cache.nextValue
            if prev_v is None or next_v is None:
                continue

            if world_space:
                obj = attr_full.split(".")[0]
                world_target = (obj, float(time))
                if world_target in processed_world_targets:
                    continue
                prev_m = cmds.getAttr(f"{obj}.worldMatrix[0]", time=cache.prev_f if cache.prev_f is not None else time)
                next_m = cmds.getAttr(f"{obj}.worldMatrix[0]", time=cache.next_f if cache.next_f is not None else time)
                new_m = _interpolate_matrix(prev_m, next_m, t)

                if cmds.currentTime(query=True) != time:
                    cmds.currentTime(time, edit=True)
                cmds.xform(obj, matrix=new_m, ws=True)
                cmds.setKeyframe(obj, time=time, respectKeyable=True)
                processed_world_targets.add(world_target)
            else:
                new_v = utils.lerp(prev_v, next_v, t)
                mode_values.apply_attr_curve_value(
                    session,
                    attr_full,
                    new_v,
                    time,
                    use_direct_attr=cache.use_direct_attr,
                    curve=cache.curve,
                    key_index=cache.keyIndex,
                )
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

    # Preview the first applicable neighbor on the active side. This is also
    # the visual fallback used by Blend to Frame before either side is picked.
    target_frames = []
    for cache in session.cache.frame_data.values():
        frame = cache.next_f if percentage > 0 else cache.prev_f
        if frame is not None:
            target_frames.append(frame)
    if target_frames:
        target_frame = sorted(target_frames)[0]
        session.show_target_tint((target_frame, target_frame))

    processed_world_targets = set()
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
            world_target = (attr_full.split(".")[0], float(time))
            if world_target in processed_world_targets:
                continue
            target_f = cache.next_f if percentage > 0 else cache.prev_f
            if _apply_world_space_blend(attr_full, time, target_f, t):
                processed_world_targets.add(world_target)
                continue

        new_v = utils.lerp_towards(left_target, right_target, t, orig)
        mode_values.apply_attr_curve_value(
            session,
            attr_full,
            new_v,
            time,
            use_direct_attr=cache.use_direct_attr,
            curve=cache.curve,
            key_index=cache.keyIndex,
        )


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
        mode_values.apply_attr_curve_value(
            session,
            attr_full,
            new_v,
            time,
            use_direct_attr=cache.use_direct_attr,
            curve=cache.curve,
            key_index=cache.keyIndex,
        )


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
            curve, curve_fn = mode_values.curve_fn_for_attr(attr_full)

            for current_time in times:
                try:
                    original_value = mode_values.curve_value_at_time(curve_fn, current_time, cmds.getAttr(attr_full, time=current_time))
                    key_index = mode_values.find_or_add_key_index(session, curve_fn, current_time)
                    if key_index is not None:
                        original_value = mode_values.curve_value(curve_fn, key_index, original_value)
                    session.cache.frame_data[(attr_full, current_time)] = BlendFrameData(
                        original_value=original_value,
                        defaultValue=default_value,
                        use_direct_attr=not has_keys,
                        curve=curve,
                        keyIndex=key_index,
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

        mode_values.apply_attr_curve_value(
            session,
            attr_full,
            new_value,
            current_time,
            use_direct_attr=cache.use_direct_attr,
            curve=cache.curve,
            key_index=cache.keyIndex,
        )


def apply_blend_to_key(session, percentage, objs=None):
    return apply_blend_to_neighbors(session, percentage)


def apply_blend_to_frame(session, percentage, left_frame=None, right_frame=None, objs=None, world_space=False):
    """Blends current values toward values at specific frames, for all affected keys."""
    if left_frame is None:
        left_frame = getattr(session, "left_target_frame", None)
    if right_frame is None:
        right_frame = getattr(session, "right_target_frame", None)
    if left_frame is None and right_frame is None:
        return apply_blend_to_neighbors(session, percentage, world_space=world_space)
    if not session.cache.is_cached:
        affected_map, _tr = _resolve_keyframe_targets_for_session(session)
        if not affected_map:
            return
        session.snapshot_pose_buffer(affected_map)

        # A single picked side is useful on both halves until the other side is set.
        left_frame = left_frame if left_frame is not None else right_frame
        right_frame = right_frame if right_frame is not None else left_frame

        session.cache.frame_data.clear()
        for attr_full, times in affected_map.items():
            if not cmds.objExists(attr_full):
                continue

            try:
                curve, curve_fn = mode_values.curve_fn_for_attr(attr_full)
                l_val = mode_values.curve_value_at_time(curve_fn, left_frame, cmds.getAttr(attr_full, time=left_frame))
                r_val = mode_values.curve_value_at_time(curve_fn, right_frame, cmds.getAttr(attr_full, time=right_frame))
            except Exception:
                continue

            has_keys = _has_keyframes(attr_full)
            for t in times:
                try:
                    orig = mode_values.curve_value_at_time(curve_fn, t, cmds.getAttr(attr_full, time=t))
                    key_index = mode_values.find_or_add_key_index(session, curve_fn, t)
                    if key_index is not None:
                        orig = mode_values.curve_value(curve_fn, key_index, orig)
                    session.cache.frame_data[(attr_full, t)] = BlendFrameData(
                        original_value=orig,
                        leftValue=l_val,
                        rightValue=r_val,
                        leftFrame=left_frame,
                        rightFrame=right_frame,
                        use_direct_attr=not has_keys,
                        curve=curve,
                        keyIndex=key_index,
                    )
                except Exception:
                    pass
        session.cache.is_cached = True

    target_frame = right_frame if percentage > 0 else left_frame
    if target_frame is not None:
        session.show_target_tint((target_frame, target_frame))

    processed_world_targets = set()
    for (attr_full, time), cache in session.cache.frame_data.items():
        orig = cache.original_value
        target_v = cache.rightValue if percentage > 0 else cache.leftValue

        if target_v is None or orig is None:
            continue

        t = float(percentage) / 100.0
        if world_space:
            world_target = (attr_full.split(".")[0], float(time))
            if world_target in processed_world_targets:
                continue
            target_f = cache.rightFrame if percentage > 0 else cache.leftFrame
            if _apply_world_space_blend(attr_full, time, target_f, t):
                processed_world_targets.add(world_target)
                continue
        new_v = utils.lerp_towards(cache.leftValue, cache.rightValue, t, orig)
        mode_values.apply_attr_curve_value(
            session,
            attr_full,
            new_v,
            time,
            use_direct_attr=cache.use_direct_attr,
            curve=cache.curve,
            key_index=cache.keyIndex,
        )


def apply_blend_to_infinity(session, percentage, world_space=False):
    """Blend toward the curve's evaluated pre/post-infinity shape."""
    if not session.cache.is_cached:
        affected_map, _time_range = _resolve_keyframe_targets_for_session(session)
        if not affected_map:
            return
        session.snapshot_pose_buffer(affected_map)
        session.cache.frame_data.clear()
        for attr_full, times in affected_map.items():
            curve, curve_fn = mode_values.curve_fn_for_attr(attr_full)
            key_times = sorted(float(time) for time in (cmds.keyframe(attr_full, query=True, timeChange=True) or []))
            if not curve or not key_times:
                continue
            first_frame, last_frame = key_times[0], key_times[-1]
            span = max(1.0, last_frame - first_frame)
            pre_frame, post_frame = first_frame - span, last_frame + span
            try:
                pre_value = mode_values.curve_value_at_time(curve_fn, pre_frame, cmds.getAttr(attr_full, time=pre_frame))
                post_value = mode_values.curve_value_at_time(curve_fn, post_frame, cmds.getAttr(attr_full, time=post_frame))
            except Exception:
                continue
            has_keys = _has_keyframes(attr_full)
            for current_time in times:
                original = mode_values.curve_value_at_time(
                    curve_fn, current_time, cmds.getAttr(attr_full, time=current_time)
                )
                key_index = mode_values.find_or_add_key_index(session, curve_fn, current_time)
                if key_index is not None:
                    original = mode_values.curve_value(curve_fn, key_index, original)
                session.cache.frame_data[(attr_full, current_time)] = BlendFrameData(
                    original_value=original, leftValue=pre_value, rightValue=post_value,
                    leftFrame=pre_frame, rightFrame=post_frame, use_direct_attr=not has_keys,
                    curve=curve, keyIndex=key_index,
                )
        session.cache.is_cached = True

    t = float(percentage) / 100.0
    processed_world_targets = set()
    for (attr_full, time), cache in session.cache.frame_data.items():
        orig = cache.original_value
        if not isinstance(orig, (int, float)):
            continue
        if not isinstance(cache.leftValue, (int, float)) or not isinstance(cache.rightValue, (int, float)):
            continue
        if world_space:
            world_target = (attr_full.split(".")[0], float(time))
            if world_target in processed_world_targets:
                continue
            target_frame = cache.rightFrame if percentage > 0 else cache.leftFrame
            if _apply_world_space_blend(attr_full, time, target_frame, t):
                processed_world_targets.add(world_target)
                continue
        new_v = utils.lerp_towards(cache.leftValue, cache.rightValue, t, orig)
        mode_values.apply_attr_curve_value(
            session,
            attr_full,
            new_v,
            time,
            use_direct_attr=cache.use_direct_attr,
            curve=cache.curve,
            key_index=cache.keyIndex,
        )


def apply_blend_to_buffer(session, percentage, world_space=False):
    """Blend existing keys toward the normalized shape of Maya buffer curves."""
    affected_map, _time_range = _resolve_keyframe_targets_for_session(session)
    if not affected_map:
        return

    if not session.cache.is_cached:
        session.cache.frame_data.clear()
        for attr_full, times in affected_map.items():
            has_keys = _has_keyframes(attr_full)
            curve, curve_fn = mode_values.curve_fn_for_attr(attr_full)
            buffer_targets = _capture_buffer_curve_targets(curve, times)
            for current_time in times:
                try:
                    orig = mode_values.curve_value_at_time(curve_fn, current_time, cmds.getAttr(attr_full, time=current_time))
                except Exception:
                    continue
                key_index = mode_values.find_or_add_key_index(session, curve_fn, current_time)
                if key_index is not None:
                    orig = mode_values.curve_value(curve_fn, key_index, orig)
                target = buffer_targets.get(float(current_time), {})
                buffer_value = target.get("value")
                if not isinstance(buffer_value, (int, float)):
                    continue
                session.cache.frame_data[(attr_full, current_time)] = BlendFrameData(
                    original_value=orig,
                    bufferValue=buffer_value,
                    use_direct_attr=not has_keys,
                    curve=curve,
                    keyIndex=key_index,
                )
                session.cache.auxiliary[(attr_full, current_time, "buffer_shape")] = target
        session.cache.is_cached = True

    t = max(-1.0, min(1.0, float(percentage) / 100.0))
    for key, cache in session.cache.frame_data.items():
        if not isinstance(key, tuple) or len(key) != 2 or not isinstance(cache, BlendFrameData):
            continue
        attr_full, current_time = key
        orig = cache.original_value
        buffer_value = cache.bufferValue
        if not isinstance(orig, (int, float)) or not isinstance(buffer_value, (int, float)):
            continue
        mirror_value = (2.0 * orig) - buffer_value
        new_value = utils.lerp_towards(mirror_value, buffer_value, t, orig)
        mode_values.apply_attr_curve_value(
            session,
            attr_full,
            new_value,
            current_time,
            use_direct_attr=cache.use_direct_attr,
            curve=cache.curve,
            key_index=cache.keyIndex,
        )
        if not session.preview:
            target = session.cache.auxiliary.get((attr_full, current_time, "buffer_shape"))
            _apply_preserved_blended_tangents(cache.curve, current_time, target, t)


def apply_blend_to_undo(session, percentage, world_space=False):
    """Blend toward a curve-shape snapshot captured through Maya Undo/Redo."""
    affected_map, _time_range = _resolve_keyframe_targets_for_session(session)
    if not affected_map:
        return
    if not session.cache.is_cached:
        session.cache.frame_data.clear()
        current_data = {}
        for attr_full, times in affected_map.items():
            curve, curve_fn = mode_values.curve_fn_for_attr(attr_full)
            for current_time in times:
                current_data[(attr_full, current_time)] = {
                    "curve": curve,
                    "value": mode_values.curve_value_at_time(
                        curve_fn, current_time, cmds.getAttr(attr_full, time=current_time)
                    ),
                    "has_keys": _has_keyframes(attr_full),
                }

        undone_values = {}
        undone_shapes = {}
        did_undo = False
        with runtime.suppress_undo_notifications():
            try:
                if cmds.undoInfo(query=True, undoQueueEmpty=True):
                    return
                cmds.undo()
                did_undo = True
                from TheKeyMachine.core import curveFitting

                for attr_full, times in affected_map.items():
                    undone_curve, undone_curve_fn = mode_values.curve_fn_for_attr(attr_full)
                    if undone_curve:
                        shape = curveFitting.capture([undone_curve], times).get(undone_curve, {})
                    else:
                        shape = {}
                    for current_time in times:
                        fallback = cmds.getAttr(attr_full, time=current_time)
                        undone_values[(attr_full, current_time)] = mode_values.curve_value_at_time(
                            undone_curve_fn, current_time, fallback
                        )
                        undone_shapes[(attr_full, current_time)] = shape.get(float(current_time), {})
            finally:
                if did_undo:
                    cmds.redo()

        for (attr_full, current_time), current in current_data.items():
            target_value = undone_values.get((attr_full, current_time))
            if not isinstance(target_value, (int, float)):
                continue
            curve, curve_fn = mode_values.curve_fn_for_attr(attr_full)
            key_index = mode_values.find_or_add_key_index(session, curve_fn, current_time)
            session.cache.frame_data[(attr_full, current_time)] = BlendFrameData(
                original_value=current["value"], bufferValue=target_value,
                use_direct_attr=not current["has_keys"], curve=curve, keyIndex=key_index,
            )
            session.cache.auxiliary[(attr_full, current_time, "undo_shape")] = undone_shapes.get(
                (attr_full, current_time), {}
            )
        session.cache.is_cached = True

    t = max(-1.0, min(1.0, float(percentage) / 100.0))
    for key, cache in session.cache.frame_data.items():
        if not isinstance(key, tuple) or len(key) != 2 or not isinstance(cache, BlendFrameData):
            continue
        attr_full, current_time = key
        mirror_value = (2.0 * cache.original_value) - cache.bufferValue
        new_value = utils.lerp_towards(mirror_value, cache.bufferValue, t, cache.original_value)
        mode_values.apply_attr_curve_value(
            session, attr_full, new_value, current_time, use_direct_attr=cache.use_direct_attr,
            curve=cache.curve, key_index=cache.keyIndex,
        )
        if not session.preview:
            target = session.cache.auxiliary.get((attr_full, current_time, "undo_shape"))
            _apply_preserved_blended_tangents(cache.curve, current_time, target, t)


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
