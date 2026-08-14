"""Preview and commit animation values for interactive slider sessions."""

from maya import cmds

from TheKeyMachine.maya import maya_api
from TheKeyMachine.tools.sliders import targeting


def curve_for_attribute(session, attribute):
    return targeting.editable_curve_for_attribute(session, attribute)


def find_or_add_key_index(session, curve_fn, time):
    if not session.preview or session.anim_change is None:
        return maya_api.anim_curve_key_index(curve_fn, time)
    return maya_api.add_anim_curve_key(curve_fn, time, change=session.anim_change)


def _clamp_attribute_value(attribute, value):
    try:
        node, attribute_name = attribute.split(".", 1)
    except ValueError:
        return value
    try:
        if cmds.attributeQuery(attribute_name, node=node, minExists=True):
            value = max(value, cmds.attributeQuery(attribute_name, node=node, minimum=True)[0])
        if cmds.attributeQuery(attribute_name, node=node, maxExists=True):
            value = min(value, cmds.attributeQuery(attribute_name, node=node, maximum=True)[0])
    except Exception:
        pass
    return value


def _set_attribute_value(attribute, value):
    value = _clamp_attribute_value(attribute, value)
    try:
        cmds.setAttr(attribute, float(value))
        return
    except Exception:
        pass
    try:
        cmds.setAttr(attribute, int(round(value)))
    except Exception:
        pass


def write_attribute_curve_value(
    session,
    attribute,
    value,
    current_time,
    use_direct_attribute=False,
    curve=None,
    key_index=None,
    create_key=False,
):
    attribute_value = _clamp_attribute_value(
        attribute,
        maya_api.anim_curve_value_to_attr_value(curve, value),
    )
    if use_direct_attribute:
        if not session.preview:
            _set_attribute_value(attribute, attribute_value)
        return

    if session.preview:
        if session.anim_change is not None and curve and key_index is not None:
            curve_fn = maya_api.anim_curve_fn(curve)
            maya_api.set_anim_curve_value_by_index(
                curve_fn,
                key_index,
                value,
                change=session.anim_change,
            )
        return

    if curve and key_index is not None:
        curve_fn = maya_api.anim_curve_fn(curve)
        if maya_api.anim_curve_key_index(curve_fn, current_time) is None:
            if not (create_key or session.committing_preview):
                return
            _write_curve_with_commands(curve, current_time, value)
            return

    try:
        cmds.setKeyframe(
            attribute,
            time=(current_time,),
            value=float(attribute_value),
            absolute=True,
        )
    except Exception:
        try:
            cmds.keyframe(
                attribute,
                edit=True,
                time=(current_time, current_time),
                valueChange=float(attribute_value),
                absolute=True,
            )
        except Exception:
            pass


def _write_curve_with_maya_api(session, curve, time, value, create=False):
    curve_fn = maya_api.anim_curve_fn(curve)
    if curve_fn is None:
        return False
    index = maya_api.anim_curve_key_index(curve_fn, time)
    if index is None and create:
        index = maya_api.add_anim_curve_key(
            curve_fn,
            time,
            change=session.anim_change,
        )
    if index is None:
        return False
    return maya_api.set_anim_curve_value_by_index(
        curve_fn,
        index,
        value,
        change=session.anim_change,
    )


def _write_curve_with_commands(curve, time, value):
    command_value = maya_api.anim_curve_value_to_attr_value(curve, value)
    try:
        existing = cmds.keyframe(
            curve,
            query=True,
            time=(time, time),
            timeChange=True,
        ) or []
    except Exception:
        existing = []
    if existing:
        try:
            cmds.keyframe(
                curve,
                edit=True,
                time=(time, time),
                valueChange=command_value,
            )
            return
        except Exception:
            pass
    cmds.setKeyframe(curve, time=(time,), value=command_value)


def write_curve_value(
    session,
    curve,
    time,
    value,
    create=True,
    allow_command_fallback=True,
):
    if not session.preview:
        if allow_command_fallback:
            _write_curve_with_commands(curve, time, value)
        return
    if _write_curve_with_maya_api(session, curve, time, value, create=create):
        return
    if allow_command_fallback:
        _write_curve_with_commands(curve, time, value)
