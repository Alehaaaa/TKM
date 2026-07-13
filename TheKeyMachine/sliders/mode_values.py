"""
Shared value/cache helpers for slider modes.

Slider modes should cache curve-space values at drag start and write those
same values for preview and commit. Rotation animCurves stay in their native
curve units here; command-layer writes convert only at the last moment.
"""

import maya.cmds as cmds

import TheKeyMachine.core.openMayaUtils as omutils
import TheKeyMachine.mods.selectionMod as selectionMod


def curve_fn_for_attr(attr_full):
    curves = selectionMod.get_anim_curves_from_plugs([attr_full])
    if not curves:
        return None, None
    curve = curves[0]
    return curve, omutils.anim_curve_fn(curve)


def key_exists(curve_fn, time):
    return omutils.anim_curve_key_index(curve_fn, time) is not None


def find_or_add_key_index(session, curve_fn, time):
    if not getattr(session, "preview", False) or session.anim_change is None:
        return omutils.anim_curve_key_index(curve_fn, time)
    return omutils.add_anim_curve_key(curve_fn, time, change=session.anim_change)


def clamp_attr_value(attr_full, value):
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


def set_attr_value(attr_full, value):
    value = clamp_attr_value(attr_full, value)
    try:
        cmds.setAttr(attr_full, float(value))
        return
    except Exception:
        pass
    try:
        cmds.setAttr(attr_full, int(round(value)))
    except Exception:
        pass


def apply_attr_curve_value(
    session,
    attr_full,
    value,
    current_time,
    use_direct_attr=False,
    curve=None,
    key_index=None,
    create_key=False,
):
    attr_value = clamp_attr_value(attr_full, omutils.anim_curve_value_to_attr_value(curve, value))
    if use_direct_attr:
        if getattr(session, "preview", False):
            return
        set_attr_value(attr_full, attr_value)
        return

    if getattr(session, "preview", False):
        if session.anim_change is not None and curve and key_index is not None:
            curve_fn = omutils.anim_curve_fn(curve)
            omutils.set_anim_curve_value_by_index(curve_fn, key_index, value, change=session.anim_change)
        return

    if curve and key_index is not None and not key_exists(omutils.anim_curve_fn(curve), current_time):
        # A live preview can add a temporary key and cache its index. Releasing
        # the slider first undoes that preview, so the common commit path must
        # restore the key instead of treating the now-stale index as a no-op.
        should_create = create_key or getattr(session, "committing_preview", False)
        if not should_create:
            return
        _set_curve_key_value_with_cmds(curve, current_time, value)
        return

    try:
        cmds.setKeyframe(attr_full, time=(current_time,), value=float(attr_value), absolute=True)
    except Exception:
        try:
            cmds.keyframe(attr_full, edit=True, time=(current_time, current_time), valueChange=float(attr_value), absolute=True)
        except Exception:
            pass


def _set_curve_key_value_with_openmaya(session, curve, time, value, create=False):
    curve_fn = omutils.anim_curve_fn(curve)
    if curve_fn is None:
        return False

    index = omutils.anim_curve_key_index(curve_fn, time)
    if index is None and create:
        index = omutils.add_anim_curve_key(curve_fn, time, change=getattr(session, "anim_change", None))
    if index is None:
        return False

    return omutils.set_anim_curve_value_by_index(
        curve_fn,
        index,
        value,
        change=getattr(session, "anim_change", None),
    )


def _set_curve_key_value_with_cmds(curve, time, value):
    command_value = omutils.anim_curve_value_to_attr_value(curve, value)
    try:
        existing = cmds.keyframe(curve, query=True, time=(time, time), timeChange=True) or []
    except Exception:
        existing = []

    if existing:
        try:
            cmds.keyframe(curve, edit=True, time=(time, time), valueChange=command_value)
            return
        except Exception:
            pass

    cmds.setKeyframe(curve, time=(time,), value=command_value)


def apply_curve_value(session, curve, time, value, create=True, allow_cmds_fallback=True):
    if not getattr(session, "preview", False):
        if allow_cmds_fallback:
            _set_curve_key_value_with_cmds(curve, time, value)
        return

    wrote_with_openmaya = _set_curve_key_value_with_openmaya(session, curve, time, value, create=create)
    if wrote_with_openmaya:
        return
    if allow_cmds_fallback:
        _set_curve_key_value_with_cmds(curve, time, value)
