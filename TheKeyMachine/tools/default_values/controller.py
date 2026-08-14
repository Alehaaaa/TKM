from maya import cmds

from TheKeyMachine.maya import animation
from TheKeyMachine.tools.snapshot_rig import rig_snapshot
from TheKeyMachine.maya import selection
from TheKeyMachine.tools import common as toolCommon
from TheKeyMachine.ui.widgets import util as wutil


TRANSLATION_ATTRS = {"translate", "translateX", "translateY", "translateZ"}
ROTATION_ATTRS = {"rotate", "rotateX", "rotateY", "rotateZ"}
SCALE_ATTRS = {"scale", "scaleX", "scaleY", "scaleZ"}


def _stored_default(node, attr):
    values = rig_snapshot.resolve_control_snapshot(node, "default", compute_fn=lambda n: {})
    stored = rig_snapshot.get_attr_value(node, values, attr)
    if stored is not None:
        return stored
    fallback = cmds.attributeQuery(attr, node=node, listDefault=True)
    return fallback[0] if fallback else None


def remove_selected():
    selected = selection.get_selected_objects(long=True)
    if not selected:
        return wutil.make_inViewMessage("Select at least one object")
    groups = rig_snapshot.group_controls_by_rig(selected)
    if not groups:
        return wutil.make_inViewMessage("Selected controls are not part of a recognizable rig")

    operation = toolCommon.current_tool_operation()
    if operation:
        operation.set_total(len(selected))
    for rig_id, group in groups.items():
        entries = {}
        for node in group["controls"]:
            if operation and operation.cancelled:
                return
            entries[rig_snapshot.control_key(node)] = {}
            if operation:
                operation.step()
        rig_snapshot.merge_control_entries(rig_id, "default", entries)
    wutil.make_inViewMessage("Saved defaults removed for the selection")


def clear_all():
    rig_ids = rig_snapshot.list_rig_ids()
    if not rig_ids:
        return wutil.make_inViewMessage("No saved default values found")
    for rig_id in rig_ids:
        rig_snapshot.clear_section(rig_id, "default")
    wutil.make_inViewMessage("All saved default values cleared")


def _matches(attr, translations, rotations, scales):
    if not any((translations, rotations, scales)):
        return True
    return ((translations and attr in TRANSLATION_ATTRS)
            or (rotations and attr in ROTATION_ATTRS)
            or (scales and attr in SCALE_ATTRS))


def apply_defaults(translations=False, rotations=False, scales=False):
    tool_id = "default_trs" if all((translations, rotations, scales)) else (
        "default_translations" if translations else "default_rotations" if rotations else
        "default_scales" if scales else "default_object_values"
    )
    target_info = animation.resolve_context(
        default_mode="current_frame",
        include_channels=True,
    )
    selected = target_info.objects
    if not selected and not target_info.plugs:
        return wutil.make_inViewMessage("Select objects, channels, or Graph Editor keys")

    with toolCommon.tool_operation(
        tool_id=tool_id,
        undo=True,
        tint="context",
        default_mode="current_frame",
    ) as operation:
        if target_info.time.mode == "graph_editor_keys":
            operation.set_total(len(target_info.selected_keys))
            for curve, frame in target_info.selected_keys:
                if operation.cancelled:
                    return
                destinations = cmds.listConnections(
                    curve + ".output",
                    plugs=True,
                    source=False,
                    destination=True,
                ) or []
                if not destinations or "." not in destinations[0]:
                    operation.step()
                    continue
                node, attr = destinations[0].split(".", 1)
                if not _matches(attr, translations, rotations, scales):
                    operation.step()
                    continue
                value = _stored_default(node, attr)
                if value is not None:
                    try:
                        cmds.keyframe(curve, edit=True, valueChange=value, time=(frame, frame))
                    except RuntimeError:
                        pass
                operation.step()
            return

        operation.set_total(len(target_info.plugs))
        for plug in target_info.plugs:
            if operation.cancelled:
                return
            if "." not in plug:
                operation.step()
                continue
            node, attr = plug.split(".", 1)
            if not _matches(attr, translations, rotations, scales) or not cmds.getAttr(plug, settable=True):
                operation.step()
                continue
            value = _stored_default(node, attr)
            if value is None:
                operation.step()
                continue
            time_context = target_info.time
            try:
                if time_context.mode == "current_frame":
                    cmds.setAttr(plug, value)
                    operation.step()
                    continue
                frames = cmds.keyframe(plug, query=True, time=time_context.timerange) or []
                if frames:
                    cmds.setKeyframe(node, attribute=attr, time=frames, value=value)
            except RuntimeError:
                pass
            operation.step()
