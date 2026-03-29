"""
TheKeyMachine - Keyframe-level Slider Operations

Tweening and blending operations translated from keyToolsMod.
"""

import maya.cmds as cmds
from . import utils
from TheKeyMachine.widgets import util as wutil

# ---------------------------------------------------------------------------------------------------------------------
#                                                     Tween Logic                                                     #
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
    try:
        cmds.keyframe(attr_full, edit=True, time=(current_time, current_time), valueChange=float(value))
    except Exception:
        try:
            cmds.setKeyframe(attr_full, time=current_time, value=float(value))
        except Exception:
            pass


def _resolve_affected_attribute_plugs():
    plugs, _source, time_range, has_graph_keys = utils.resolve_target_attribute_plugs()
    if not plugs:
        return [], time_range

    current_time = cmds.currentTime(query=True)
    keyed_at_current = []
    for plug in plugs:
        try:
            times = cmds.keyframe(plug, q=True, time=(current_time, current_time), timeChange=True) or []
        except Exception:
            times = []
        if times:
            keyed_at_current.append(plug)

    if has_graph_keys:
        affected = plugs
        missing = [p for p in affected if p not in keyed_at_current]
        if missing:
            _ensure_keys_at_current_time(missing)
    else:
        affected = plugs
        _ensure_keys_at_current_time(affected)

    return affected, time_range


def prepare_tween_data(objs=None, attrs=None, attr_plugs=None, time_range=None):
    """Caches keyframe context for efficient tweening."""
    utils.tween_frame_data_cache = {}
    current_time = cmds.currentTime(query=True)

    right_frame = _right_frame_from_time_range(time_range)

    if attr_plugs is not None:
        plugs = list(attr_plugs)
    else:
        nodes = objs if objs else wutil.get_selected_objects()
        plugs = []
        for obj in nodes:
            if not cmds.objExists(obj):
                continue
            current_attrs = attrs if attrs else cmds.listAttr(obj, keyable=True)
            if not current_attrs:
                continue
            plugs.extend([f"{obj}.{a}" for a in current_attrs])

    for attr_full in plugs:
        if not cmds.objExists(attr_full):
            continue

        # Cache the current value once per drag so 0 stays stable/neutral.
        try:
            current_v = cmds.getAttr(attr_full, time=current_time)
        except Exception:
            continue

        if time_range and right_frame is not None:
            try:
                prev_v = cmds.getAttr(attr_full, time=time_range[0])
                next_v = cmds.getAttr(attr_full, time=right_frame)
            except Exception:
                utils.tween_frame_data_cache[attr_full] = {"needsCalculation": False}
                continue

            utils.tween_frame_data_cache[attr_full] = {
                "previousValue": prev_v,
                "nextValue": next_v,
                "currentValue": current_v,
                "needsCalculation": (prev_v != next_v) or (current_v != prev_v),
            }
            continue

        keyframes = cmds.keyframe(attr_full, query=True) or []
        if not keyframes:
            utils.tween_frame_data_cache[attr_full] = {"needsCalculation": False, "use_direct_attr": True}
            continue

        prev_keys = [f for f in keyframes if f < current_time]
        next_keys = [f for f in keyframes if f > current_time]

        if not prev_keys or not next_keys:
            utils.tween_frame_data_cache[attr_full] = {"needsCalculation": False}
            continue

        prev_f = max(prev_keys)
        next_f = min(next_keys)
        prev_v = cmds.getAttr(attr_full, time=prev_f)
        next_v = cmds.getAttr(attr_full, time=next_f)

        utils.tween_frame_data_cache[attr_full] = {
            "previousValue": prev_v,
            "nextValue": next_v,
            "currentValue": current_v,
            "needsCalculation": (prev_v != next_v) or (current_v != prev_v),
            "use_direct_attr": False,
        }
    return utils.tween_frame_data_cache


def execute_tween(value, world_space=False):
    """Core tweening logic."""
    if not utils.tween_frame_data_cache:
        attr_plugs, time_range = _resolve_affected_attribute_plugs()
        if not attr_plugs:
            return
        prepare_tween_data(attr_plugs=attr_plugs, time_range=time_range)

    utils.start_dragging()
    current_time = cmds.currentTime(query=True)

    for attr_full, cache in utils.tween_frame_data_cache.items():
        if not cache.get("needsCalculation", False):
            continue

        # Validation
        if not cmds.objExists(attr_full):
            continue
        if cmds.getAttr(attr_full, lock=True) or not cmds.getAttr(attr_full, settable=True):
            continue
        if cmds.getAttr(attr_full, type=True) in ["enum", "string", "message"]:
            continue

        prev_v = cache.get("previousValue")
        next_v = cache.get("nextValue")
        cur_v = cache.get("currentValue")
        if prev_v is None or next_v is None or cur_v is None:
            continue
        if isinstance(prev_v, (list, tuple)) or isinstance(next_v, (list, tuple)):
            continue

        # Tweener-style: value in [-100..100] maps to t in [-1..1], with 0 being neutral (current value).
        t = float(value) / 100.0
        if t < 0.0:
            tt = t + 1.0  # remap [-1..0] to [0..1]
            new_v = prev_v + (cur_v - prev_v) * tt
        elif t > 0.0:
            new_v = cur_v + (next_v - cur_v) * t
        else:
            new_v = cur_v

        # Handle limits
        _apply_cached_value(attr_full, new_v, current_time, use_direct_attr=cache.get("use_direct_attr", False))


# ---------------------------------------------------------------------------------------------------------------------
#                                                     Blend Logic                                                     #
# ---------------------------------------------------------------------------------------------------------------------


def cache_keyframe_data(attr_plugs, time_range=None):
    """Caches values for blend-to-neighbors style operations."""
    utils.frame_data_cache = {}
    current_time = cmds.currentTime(query=True)
    right_frame = _right_frame_from_time_range(time_range)

    for attr_full in attr_plugs:
        if not cmds.objExists(attr_full):
            continue

        try:
            original_value = cmds.getAttr(attr_full, time=current_time)
        except Exception:
            continue

        previous_value = None
        next_value = None
        prev_tan_type = None

        if time_range and right_frame is not None:
            try:
                previous_value = cmds.getAttr(attr_full, time=time_range[0])
                next_value = cmds.getAttr(attr_full, time=right_frame)
            except Exception:
                previous_value = None
                next_value = None
        else:
            keyframes = cmds.keyframe(attr_full, query=True) or []
            prev_keys = [f for f in keyframes if f < current_time]
            next_keys = [f for f in keyframes if f > current_time]

            prev_f = max(prev_keys) if prev_keys else None
            next_f = min(next_keys) if next_keys else None

            if prev_f is not None:
                try:
                    previous_value = cmds.getAttr(attr_full, time=prev_f)
                except Exception:
                    previous_value = None
                try:
                    prev_tan_type = cmds.keyTangent(attr_full, query=True, time=(prev_f,), outTangentType=True)[0]
                except Exception:
                    prev_tan_type = None

            if next_f is not None:
                try:
                    next_value = cmds.getAttr(attr_full, time=next_f)
                except Exception:
                    next_value = None

        utils.frame_data_cache[attr_full] = {
            "original_value": original_value,
            "previousValue": previous_value,
            "nextValue": next_value,
            "prevTanType": prev_tan_type,
            "use_direct_attr": not _has_keyframes(attr_full),
        }

    return utils.frame_data_cache


def execute_blend_to_neighbors(percentage, world_space=False):
    """Blends the current pose toward previous/next neighbors (or time range boundaries if selected)."""
    utils.start_dragging()
    attr_plugs, time_range = _resolve_affected_attribute_plugs()
    if not attr_plugs:
        return

    if not utils.is_cached:
        cache_keyframe_data(attr_plugs, time_range=time_range)
        utils.is_cached = True

    current_time = cmds.currentTime(query=True)
    for attr_full, cache in utils.frame_data_cache.items():
        if cmds.getAttr(attr_full, lock=True) or not cmds.getAttr(attr_full, settable=True):
            continue

        orig = cache.get("original_value")
        nxt = cache.get("nextValue")
        prev = cache.get("previousValue")

        if any(isinstance(v, (list, tuple)) for v in (orig, nxt, prev) if v is not None):
            continue
        if not isinstance(orig, (int, float)):
            continue

        if percentage > 0:
            if nxt is None or not isinstance(nxt, (int, float)):
                continue
            t = min(abs(percentage), 100.0) / 100.0
            new_v = orig + (nxt - orig) * t
        elif percentage < 0:
            if prev is None or not isinstance(prev, (int, float)):
                continue
            t = min(abs(percentage), 100.0) / 100.0
            new_v = orig + (prev - orig) * t
        else:
            continue

        _apply_cached_value(attr_full, new_v, current_time, use_direct_attr=cache.get("use_direct_attr", False))


def execute_blend_to_default(percentage, world_space=False):
    """Blends the current pose toward each attribute's default value."""
    utils.start_dragging()
    attr_plugs, _time_range = _resolve_affected_attribute_plugs()
    if not attr_plugs:
        return

    current_time = cmds.currentTime(query=True)
    t = float(percentage) / 100.0

    def _cache_default_data():
        utils.frame_data_cache = {}
        for attr_full in attr_plugs:
            try:
                if not cmds.objExists(attr_full):
                    continue
                if cmds.getAttr(attr_full, lock=True) or not cmds.getAttr(attr_full, settable=True):
                    continue
                a_type = cmds.getAttr(attr_full, type=True)
                if a_type in ("enum", "string", "message"):
                    continue

                obj, attr = attr_full.split(".", 1)
                default_query = cmds.attributeQuery(attr, node=obj, listDefault=True)
                if not default_query:
                    continue

                original_value = cmds.getAttr(attr_full, time=current_time)
                default_value = default_query[0]

                if isinstance(original_value, (list, tuple)) or isinstance(default_value, (list, tuple)):
                    continue
                if not isinstance(original_value, (int, float)) or not isinstance(default_value, (int, float)):
                    continue

                utils.frame_data_cache[attr_full] = {
                    "original_value": float(original_value),
                    "defaultValue": float(default_value),
                    "use_direct_attr": not _has_keyframes(attr_full),
                }
            except Exception:
                pass
        utils.is_cached = True

    needs_cache = (not utils.is_cached) or (not utils.frame_data_cache) or ("defaultValue" not in next(iter(utils.frame_data_cache.values())).keys())
    if needs_cache:
        _cache_default_data()

    for attr_full, cache in utils.frame_data_cache.items():
        if "defaultValue" not in cache:
            continue
        orig = cache.get("original_value")
        default_value = cache.get("defaultValue")
        if not isinstance(orig, (int, float)) or not isinstance(default_value, (int, float)):
            continue
        # Positive: blend from original -> default
        # Negative: move away from default in the same direction as the original.
        # Example: original=5, default=0 => -100 -> 10 (adds the distance to default again).
        if t > 0.0:
            new_value = orig + (default_value - orig) * t
        elif t < 0.0:
            mirrored = (2.0 * orig) - default_value
            u = min(abs(t), 1.0)
            new_value = orig + (mirrored - orig) * u
        else:
            new_value = orig
        _apply_cached_value(attr_full, new_value, current_time, use_direct_attr=cache.get("use_direct_attr", False))


def execute_blend_to_key(percentage, objs=None):
    """Back-compat alias (now matches blend-to-neighbors behavior)."""
    return execute_blend_to_neighbors(percentage)


def execute_blend_to_frame(percentage, left_frame=None, right_frame=None, objs=None):
    """Blends current value toward values at specific frames."""
    utils.start_dragging()
    nodes = objs if objs else wutil.get_selected_objects()
    if not nodes:
        return

    # If frames aren't provided, use a default (like current time -1/+1) or whatever keyTools did
    # For now, if none, we skip or use simple neighbor logic
    if left_frame is None or right_frame is None:
        # Fallback to standard neighbor blend if frames aren't specified (e.g. in Graph Editor)
        return execute_blend_to_neighbors(percentage)

    # Cache if needed (custom for these frames)
    # Note: In a real implementation, we'd cache the values at left_frame/right_frame
    for obj in nodes:
        attrs = cmds.listAttr(obj, keyable=True, scalar=True) or []
        for attr in attrs:
            attr_full = f"{obj}.{attr}"
            orig = cmds.getAttr(attr_full)
            
            if percentage > 0:
                target_v = cmds.getAttr(attr_full, time=right_frame)
            else:
                target_v = cmds.getAttr(attr_full, time=left_frame)
            
            if target_v is None:
                continue
                
            diff = target_v - orig
            weighted_diff = (diff * abs(percentage)) / 100.0
            new_v = orig + weighted_diff
            
            try:
                cmds.setAttr(attr_full, float(new_v))
            except Exception:
                pass


# ---------------------------------------------------------------------------------------------------------------------
#                                                   General Utils                                                     #
# ---------------------------------------------------------------------------------------------------------------------


def blend_slider_reset(slider_name=None):
    """Cleanup after slider interaction, handling tangent restoration."""
    current_time = cmds.currentTime(query=True)
    if utils.frame_data_cache:
        for attr_full, cache in utils.frame_data_cache.items():
            if cache.get("prevTanType") == "step":
                cmds.setKeyframe(attr_full, time=current_time)
                cmds.keyTangent(attr_full, edit=True, time=(current_time,), inTangentType="stepnext", outTangentType="stepnext")

    utils.stop_dragging()
    if slider_name and cmds.floatSlider(slider_name, exists=True):
        cmds.floatSlider(slider_name, edit=True, value=0)
