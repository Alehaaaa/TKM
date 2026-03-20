"""
TheKeyMachine - Keyframe-level Slider Operations

Tweening and blending operations translated from keyToolsMod.
"""

import maya.cmds as cmds
from . import utils

# ---------------------------------------------------------------------------------------------------------------------
#                                                     Tween Logic                                                     #
# ---------------------------------------------------------------------------------------------------------------------


def prepare_tween_data(objs=None, attrs=None):
    """Caches keyframe context for efficient tweening."""
    utils.tween_frame_data_cache = {}
    current_time = cmds.currentTime(query=True)

    nodes = objs if objs else cmds.ls(selection=True)
    for obj in nodes:
        if not cmds.objExists(obj):
            continue
        current_attrs = attrs if attrs else cmds.listAttr(obj, keyable=True)
        if not current_attrs:
            continue

        for attr in current_attrs:
            attr_full = f"{obj}.{attr}"
            keyframes = cmds.keyframe(attr_full, query=True) or []
            if not keyframes:
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

            utils.tween_frame_data_cache[attr_full] = {"previousValue": prev_v, "nextValue": next_v, "needsCalculation": (prev_v != next_v)}

            # Cache tangent type
            utils.tween_frame_data_cache[attr_full]["prevTanType"] = cmds.keyTangent(attr_full, query=True, time=(prev_f,), outTangentType=True)[0]
    return utils.tween_frame_data_cache


def execute_tween(value, world_space=False):
    """Core tweening logic."""
    if not utils.tween_frame_data_cache:
        prepare_tween_data()

    utils.start_dragging()

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
        if prev_v is None or next_v is None:
            continue
        if isinstance(prev_v, (list, tuple)) or isinstance(next_v, (list, tuple)):
            continue

        difference = next_v - prev_v
        weighted_diff = (difference * value) / 100.0
        new_v = prev_v + weighted_diff

        # Handle limits
        obj, attr = attr_full.split(".")
        if cmds.attributeQuery(attr, node=obj, minExists=True):
            new_v = max(new_v, cmds.attributeQuery(attr, node=obj, minimum=True)[0])
        if cmds.attributeQuery(attr, node=obj, maxExists=True):
            new_v = min(new_v, cmds.attributeQuery(attr, node=obj, maximum=True)[0])

        cmds.setAttr(attr_full, new_v)


# ---------------------------------------------------------------------------------------------------------------------
#                                                     Blend Logic                                                     #
# ---------------------------------------------------------------------------------------------------------------------


def cache_keyframe_data(objs):
    """Caches values for standard blending."""
    utils.frame_data_cache = {}
    current_time = cmds.currentTime(query=True)

    for obj in objs:
        attrs = cmds.listAttr(obj, keyable=True, scalar=True) or []
        for attr in attrs:
            attr_full = f"{obj}.{attr}"
            if not cmds.objExists(attr_full):
                continue

            keyframes = cmds.keyframe(attr_full, query=True) or []
            prev_keys = [f for f in keyframes if f < current_time]
            next_keys = [f for f in keyframes if f > current_time]

            prev_f = max(prev_keys) if prev_keys else None
            next_f = min(next_keys) if next_keys else None

            utils.frame_data_cache[attr_full] = {
                "original_value": cmds.getAttr(attr_full),
                "previousValue": cmds.getAttr(attr_full, time=prev_f) if prev_f is not None else None,
                "nextValue": cmds.getAttr(attr_full, time=next_f) if next_f is not None else None,
                "prevTanType": cmds.keyTangent(attr_full, query=True, time=(prev_f,), outTangentType=True)[0] if prev_f else None,
            }
    return utils.frame_data_cache


def execute_blend_to_key(percentage, objs=None):
    """Blends current value between previous and next keyframes."""
    utils.start_dragging()
    nodes = objs if objs else cmds.ls(selection=True)
    if not nodes:
        return

    if not utils.is_cached:
        cache_keyframe_data(nodes)
        utils.is_cached = True

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

        if nxt is not None and isinstance(nxt, (int, float)) and percentage > 0:
            diff = nxt - orig
        elif prev is not None and isinstance(prev, (int, float)):
            diff = orig - prev
        else:
            continue

        weighted_diff = (diff * abs(percentage)) / 50.0
        new_v = orig + weighted_diff if percentage > 0 else orig - weighted_diff

        try:
            cmds.setAttr(attr_full, float(new_v))
        except Exception:
            pass


def execute_blend_to_frame(percentage, left_frame=None, right_frame=None, objs=None):
    """Blends current value toward values at specific frames."""
    utils.start_dragging()
    nodes = objs if objs else cmds.ls(selection=True)
    if not nodes:
        return

    # If frames aren't provided, use a default (like current time -1/+1) or whatever keyTools did
    # For now, if none, we skip or use simple neighbor logic
    if left_frame is None or right_frame is None:
        # Fallback to standard neighbor blend if frames aren't specified (e.g. in Graph Editor)
        return execute_blend_to_key(percentage, objs=nodes)

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
