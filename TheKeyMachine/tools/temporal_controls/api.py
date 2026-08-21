"""Temporal Controls.

Left-click (``create_controls``) with a selection opens a small creation
dialog (see ``widgets.TemporalControlsDialog``) offering:

- **System**: the control's shape/hierarchy -- Simple (one curve), Group
  (curve + an offset buffer above it), Aim (curve + a keyable aim-target
  locator driving its rotation), or FK Chain (each new control parents
  under the previous one instead of flatly under the tool's root group).
- **Position / Orientation space**: how translate/rotate are driven back
  onto the object -- Object (direct channel passthrough, the original
  behavior), World (parent-safe world-space matrix network), Relative
  (additive offset from wherever the object started), Child (a real
  ``pointConstraint``/``orientConstraint``), Camera (currently an alias for
  World -- a live camera-relative follow would need to constrain the
  control to the active camera the way Follow Cam already does, which
  would fight that tool rather than complement it, so this is intentionally
  just the safe world-space network for now), or Grab Release (same
  additive-offset math as Relative -- a temporary "grab" that Revert
  cleanly lets go of).

Confirming the dialog calls ``create_controls_with_options()``, which
builds one control per object: sized and positioned to match it, carrying
a copy of its animation keys, and driving the object back through
whichever mechanism the chosen spaces call for.

Right-click gives Bake (``bake_controls`` -- extract the control's actual
keyframes onto the original object's channels, at the times they were set,
and remove the control) and Revert (``revert_controls`` -- remove the
control and restore whatever the object's channels were connected to, or
set to, before the control was created). Both work the same regardless of
which System/Space combination built the control, since the control's own
channels always stay the free, keyable source of truth -- only how that
result reaches the object differs.

Every control lives under a single ``TkmSceneNode`` group so the tool can
find and clean up its own nodes without touching anything else in the
scene, and is tagged with a locked boolean attribute (the same pattern
``global_curve`` uses) so Bake/Revert can look controls up by attribute
instead of by name or hierarchy.
"""

import json

from maya import cmds

from TheKeyMachine.core.Qt import QtWidgets  # type: ignore
from TheKeyMachine.maya import selection
from TheKeyMachine.maya.runtime import TkmSceneNode
from TheKeyMachine.data import icons
from TheKeyMachine.tools import common as toolCommon
import TheKeyMachine.ui.widgets.util as wutil


ROOT_GROUP = "Temporal_Controls"

TAG_ATTR = "tkmTemporalControl"
TARGET_ATTR = "tkmTemporalTarget"
DELETE_ROOT_ATTR = "tkmTemporalDeleteRoot"
RESTORE_ATTR = "tkmTemporalRestore"
DRIVER_NODES_ATTR = "tkmTemporalDriverNodes"

TRANSLATE_CHANNELS = ("translateX", "translateY", "translateZ")
ROTATE_CHANNELS = ("rotateX", "rotateY", "rotateZ")
SCALE_CHANNELS = ("scaleX", "scaleY", "scaleZ")
CHANNELS = TRANSLATE_CHANNELS + ROTATE_CHANNELS + SCALE_CHANNELS

DEFAULT_RADIUS = 10.0

SYSTEMS = (
    {"id": "simple", "label": "Simple Control"},
    {"id": "group", "label": "Group Control"},
    {"id": "aim", "label": "Aim Control"},
    {"id": "fk_chain", "label": "FK Chain Control"},
    {"id": "more", "label": "More to come...", "disabled": True},
)

SPACES = (
    {"id": "world", "label": "World Space"},
    {"id": "object", "label": "Object Space"},
    {"id": "relative", "label": "Relative Space"},
    {"id": "camera", "label": "Camera Space"},
    {"id": "child", "label": "Child Space"},
    {"id": "grab_release", "label": "Grab Release Space"},
)

DEFAULT_SYSTEM = "simple"
DEFAULT_SPACE = "object"

_SETTINGS_NAMESPACE = "temporal_controls"

_temporal_controls_dialog = None


# ----------------------------------------------------------------------
# Entry point / dialog plumbing
# ----------------------------------------------------------------------

def create_controls(*_args):
    selected = [
        obj for obj in selection.get_selected_objects(long=True, ordered=True)
        if cmds.ls(obj, type="transform")
    ]
    if not selected:
        return wutil.make_inViewMessage("Select at least one object")

    _open_creation_dialog(selected)


def _open_creation_dialog(objects):
    global _temporal_controls_dialog
    from TheKeyMachine.tools.temporal_controls.widgets import TemporalControlsDialog

    if _temporal_controls_dialog is not None and wutil.is_valid_widget(_temporal_controls_dialog):
        _temporal_controls_dialog.close()

    parent = wutil.get_maya_qt(qt=QtWidgets.QWidget)

    def _on_confirmed(system, position_space, orientation_space, label, color):
        create_controls_with_options(
            objects,
            system=system,
            position_space=position_space,
            orientation_space=orientation_space,
            label=label,
            color=color,
        )

    dialog = TemporalControlsDialog(objects, parent=parent, on_confirmed=_on_confirmed)

    def _clear_reference(*_args):
        global _temporal_controls_dialog
        _temporal_controls_dialog = None

    dialog.destroyed.connect(_clear_reference)
    dialog.show()
    dialog.raise_()
    dialog.activateWindow()
    _temporal_controls_dialog = dialog


def save_last_used_options(system, position_space, orientation_space, color_suffix):
    from TheKeyMachine.core import settings
    settings.set_settings(
        {
            "last_system": system,
            "last_position_space": position_space,
            "last_orientation_space": orientation_space,
            "last_color": color_suffix,
        },
        namespace=_SETTINGS_NAMESPACE,
    )


def clear_last_used_options():
    from TheKeyMachine.core import settings
    settings.set_settings(
        {
            "last_system": DEFAULT_SYSTEM,
            "last_position_space": DEFAULT_SPACE,
            "last_orientation_space": DEFAULT_SPACE,
            "last_color": None,
        },
        namespace=_SETTINGS_NAMESPACE,
    )


def get_last_used_options():
    from TheKeyMachine.core import settings
    return {
        "system": settings.get_setting("last_system", DEFAULT_SYSTEM, namespace=_SETTINGS_NAMESPACE),
        "position_space": settings.get_setting("last_position_space", DEFAULT_SPACE, namespace=_SETTINGS_NAMESPACE),
        "orientation_space": settings.get_setting("last_orientation_space", DEFAULT_SPACE, namespace=_SETTINGS_NAMESPACE),
        "color": settings.get_setting("last_color", None, namespace=_SETTINGS_NAMESPACE),
    }


# ----------------------------------------------------------------------
# Create
# ----------------------------------------------------------------------

def create_controls_with_options(
    objects,
    system=DEFAULT_SYSTEM,
    position_space=DEFAULT_SPACE,
    orientation_space=DEFAULT_SPACE,
    label="",
    color=None,
):
    objects = [obj for obj in objects if cmds.objExists(obj)]
    if not objects:
        return wutil.make_inViewMessage("Nothing left to control -- selection changed")

    group = TkmSceneNode.root().child(ROOT_GROUP, icon=icons.temporal_controls)

    operation = toolCommon.current_tool_operation()
    if operation is not None:
        start, end = _time_range_for(objects)
        if start is not None:
            toolCommon.ensure_operation_tint(
                operation, tint="range", timerange=(start, end), tint_key="temporal_controls",
            )
        else:
            toolCommon.ensure_operation_tint(
                operation, tint="current", default_mode="current_frame", tint_key="temporal_controls",
            )
        operation.set_total(len(objects)).set_status("Creating Temporal Controls")

    options = {
        "system": system,
        "position_space": position_space,
        "orientation_space": orientation_space,
        "label": (label or "").strip(),
        "color": color,
    }

    new_controls = []
    chain_parent = None
    for obj in objects:
        if operation is not None and operation.cancelled:
            break
        if not _existing_control_for(obj):
            options["chain_parent"] = chain_parent if system == "fk_chain" else None
            control, chain_anchor = _create_control_for(obj, group.name, options)
            if control:
                new_controls.append(control)
                chain_parent = chain_anchor
        if operation is not None:
            operation.step()

    if new_controls:
        cmds.select(new_controls)
        return new_controls
    return wutil.make_inViewMessage("Selected objects already have Temporal Controls")


def _create_control_for(obj, group, options):
    control, delete_root, chain_anchor = _build_control_hierarchy(obj, group, options)

    if options.get("color"):
        _apply_control_color(control, options["color"])

    _tag_control(control, obj, delete_root)

    restore_map = {}
    for channel in CHANNELS:
        captured = _capture_channel(control, obj, channel)
        if captured:
            channel_name, payload = captured
            restore_map[channel_name] = payload

    cmds.setAttr(control + "." + RESTORE_ATTR, json.dumps(restore_map), type="string")

    driver_nodes = []
    translate_channels = [c for c in TRANSLATE_CHANNELS if c in restore_map]
    rotate_channels = [c for c in ROTATE_CHANNELS if c in restore_map]
    scale_channels = [c for c in SCALE_CHANNELS if c in restore_map]

    if translate_channels:
        driver_nodes += _drive_group(control, obj, translate_channels, options["position_space"], restore_map)
    if rotate_channels:
        driver_nodes += _drive_group(control, obj, rotate_channels, options["orientation_space"], restore_map)
    if scale_channels:
        # Scale isn't offered a space choice -- it always passes straight through.
        driver_nodes.append(_drive_with_expression(control, obj, scale_channels))

    cmds.setAttr(control + "." + DRIVER_NODES_ATTR, json.dumps(driver_nodes), type="string")

    return control, chain_anchor


def _build_control_hierarchy(obj, group, options):
    """Build the control (and, for some Systems, its helper nodes).

    Returns ``(control, delete_root, chain_anchor)``:

    - *delete_root* is the node Bake/Revert should ``cmds.delete()`` to
      remove everything this System added (the control itself for Simple/FK
      Chain, or the offset buffer for Group/Aim, whose deletion cascades to
      the control and any helper locator/constraint parented under it).
    - *chain_anchor* is the node the *next* object's control should parent
      under when System is FK Chain (always the control itself, so each
      link visually carries the next -- never the buffer).
    """
    system = options.get("system", DEFAULT_SYSTEM)
    label = options.get("label") or ""
    radius = _control_radius(obj)
    short_name = obj.split("|")[-1].split(":")[-1]
    base_name = "{}_{}".format(label, short_name) if label else short_name

    control = cmds.circle(
        name="{}_temporalCtrl#".format(base_name),
        normal=(0, 1, 0),
        radius=radius,
        constructionHistory=False,
    )[0]
    cmds.matchTransform(control, obj, position=True, rotation=True, scale=False)

    top_node = control
    if system in ("group", "aim"):
        top_node = cmds.group(control, name="{}_temporalBuf#".format(base_name))

    if system == "aim":
        _add_aim_target(control, top_node, base_name, radius)

    parent_target = group
    if system == "fk_chain" and options.get("chain_parent"):
        parent_target = options["chain_parent"]
    cmds.parent(top_node, parent_target)

    return control, top_node, control


def _add_aim_target(control, buffer_node, base_name, radius):
    aim_target = cmds.spaceLocator(name="{}_temporalAim#".format(base_name))[0]
    for axis in "XYZ":
        cmds.setAttr("{}.localScale{}".format(aim_target, axis), max(radius * 0.15, 0.5))
    cmds.matchTransform(aim_target, control, position=True, rotation=True)
    cmds.setAttr(aim_target + ".translateZ", cmds.getAttr(aim_target + ".translateZ") + radius * 2.0)
    cmds.parent(aim_target, buffer_node)
    cmds.aimConstraint(aim_target, control, worldUpType="scene", aimVector=(0, 0, 1), maintainOffset=False)


def _control_radius(obj):
    try:
        bbox = cmds.xform(obj, query=True, boundingBox=True)
    except RuntimeError:
        bbox = None
    if not bbox or len(bbox) != 6:
        return DEFAULT_RADIUS

    span = max(bbox[3] - bbox[0], bbox[4] - bbox[1], bbox[5] - bbox[2])
    if span <= 1e-6:
        return DEFAULT_RADIUS
    return max(span * 0.6, 1.0)


def _apply_control_color(control, color_hex):
    rgb = _hex_to_rgb01(color_hex)
    shapes = cmds.listRelatives(control, shapes=True, fullPath=True) or []
    for node in [control] + shapes:
        if not cmds.attributeQuery("overrideEnabled", node=node, exists=True):
            continue
        cmds.setAttr(node + ".overrideEnabled", True)
        cmds.setAttr(node + ".overrideRGBColors", True)
        cmds.setAttr(node + ".overrideColorRGB", *rgb)


def _hex_to_rgb01(color_hex):
    color_hex = (color_hex or "").lstrip("#")
    if len(color_hex) != 6:
        return (0.2, 0.6, 0.8)
    try:
        return tuple(int(color_hex[i:i + 2], 16) / 255.0 for i in (0, 2, 4))
    except ValueError:
        return (0.2, 0.6, 0.8)


def _tag_control(control, obj, delete_root):
    cmds.addAttr(control, longName=TAG_ATTR, attributeType="bool", defaultValue=True)
    cmds.setAttr(control + "." + TAG_ATTR, lock=True)

    cmds.addAttr(control, longName=TARGET_ATTR, dataType="string")
    cmds.setAttr(control + "." + TARGET_ATTR, cmds.ls(obj, long=True)[0], type="string", lock=True)

    cmds.addAttr(control, longName=DELETE_ROOT_ATTR, dataType="string")
    cmds.setAttr(control + "." + DELETE_ROOT_ATTR, cmds.ls(delete_root, long=True)[0], type="string", lock=True)

    cmds.addAttr(control, longName=RESTORE_ATTR, dataType="string")
    cmds.addAttr(control, longName=DRIVER_NODES_ATTR, dataType="string")


def _capture_channel(control, obj, channel):
    """Move one channel's driving relationship from *obj* onto *control*.

    Returns ``(channel, restore_payload)`` so it can be baked/reverted
    later, or ``None`` if the channel was left untouched (locked, or
    already driven by something this tool shouldn't take over). The
    payload always carries ``base_value`` -- the object's value at capture
    time -- since the Relative/Grab Release driving math needs a baseline
    regardless of whether the channel was keyed or static.
    """
    obj_plug = "{}.{}".format(obj, channel)
    if not cmds.objExists(obj_plug) or cmds.getAttr(obj_plug, lock=True):
        return None

    base_value = cmds.getAttr(obj_plug)
    ctrl_plug = "{}.{}".format(control, channel)
    connections = cmds.listConnections(obj_plug, source=True, destination=False, plugs=True) or []
    source_plug = connections[0] if connections else None

    if source_plug:
        source_node = source_plug.split(".")[0]
        if not cmds.nodeType(source_node).startswith("animCurve"):
            # Already driven by a constraint/expression/other setup -- leave it alone.
            return None
        try:
            cmds.copyKey(obj, attribute=channel)
            cmds.pasteKey(control, attribute=channel, option="replace")
        except RuntimeError:
            pass
        cmds.disconnectAttr(source_plug, obj_plug)
        return channel, {"mode": "curve", "source": source_plug, "base_value": base_value}

    if not cmds.getAttr(obj_plug, settable=True):
        return None

    cmds.setAttr(ctrl_plug, base_value)
    return channel, {"mode": "value", "value": base_value, "base_value": base_value}


# ----------------------------------------------------------------------
# Position / Orientation space driving
# ----------------------------------------------------------------------

def _drive_group(control, obj, channels, space_mode, restore_map):
    """Wire one channel group (all-translate or all-rotate) from *control*
    to *obj* per *space_mode*. Returns the extra node names created outside
    the control's own hierarchy, for Bake/Revert to clean up later."""
    if not channels:
        return []

    if space_mode == "object":
        return [_drive_with_expression(control, obj, channels)]

    if space_mode in ("world", "camera"):
        group_kind = "translate" if channels[0].startswith("translate") else "rotate"
        return _drive_with_world_matrix(control, obj, channels, group_kind)

    if space_mode in ("relative", "grab_release"):
        return [_drive_with_relative_expression(control, obj, channels, restore_map)]

    if space_mode == "child":
        group_kind = "translate" if channels[0].startswith("translate") else "rotate"
        return _drive_with_constraint(control, obj, group_kind)

    # Unknown/legacy value -- fall back to the original direct passthrough.
    return [_drive_with_expression(control, obj, channels)]


def _drive_with_expression(control, obj, channels):
    body = "\n".join(
        "{obj}.{ch} = {ctrl}.{ch};".format(obj=obj, ctrl=control, ch=channel)
        for channel in channels
    )
    expr_node = cmds.expression(string=body, object=control, alwaysEvaluate=True, unitConversion="all")
    return cmds.rename(expr_node, "{}_{}Expr".format(control, channels[0][:-1]))


def _drive_with_relative_expression(control, obj, channels, restore_map):
    lines = []
    for channel in channels:
        payload = restore_map.get(channel) or {}
        base_obj = payload.get("base_value", cmds.getAttr("{}.{}".format(obj, channel)))
        base_ctrl = cmds.getAttr("{}.{}".format(control, channel))
        lines.append(
            "{obj}.{ch} = {base_obj} + ({ctrl}.{ch} - {base_ctrl});".format(
                obj=obj, ch=channel, ctrl=control, base_obj=base_obj, base_ctrl=base_ctrl,
            )
        )
    expr_node = cmds.expression(string="\n".join(lines), object=control, alwaysEvaluate=True, unitConversion="all")
    return cmds.rename(expr_node, "{}_{}RelExpr".format(control, channels[0][:-1]))


def _drive_with_world_matrix(control, obj, channels, group_kind):
    mult_matrix = cmds.createNode("multMatrix", name="{}_{}WorldMM".format(control, group_kind), skipSelect=True)
    cmds.connectAttr(control + ".worldMatrix[0]", mult_matrix + ".matrixIn[0]")
    cmds.connectAttr(obj + ".parentInverseMatrix[0]", mult_matrix + ".matrixIn[1]")

    decompose = cmds.createNode("decomposeMatrix", name="{}_{}WorldDM".format(control, group_kind), skipSelect=True)
    cmds.connectAttr(mult_matrix + ".matrixSum", decompose + ".inputMatrix")

    out_attr = "outputTranslate" if group_kind == "translate" else "outputRotate"
    for channel in channels:
        axis = channel[-1]
        cmds.connectAttr("{}.{}{}".format(decompose, out_attr, axis), "{}.{}".format(obj, channel), force=True)

    return [mult_matrix, decompose]


def _drive_with_constraint(control, obj, group_kind):
    if group_kind == "translate":
        node = cmds.pointConstraint(control, obj, maintainOffset=True)[0]
    else:
        node = cmds.orientConstraint(control, obj, maintainOffset=True)[0]
    return [node]


# ----------------------------------------------------------------------
# Bake / Revert
# ----------------------------------------------------------------------

def bake_controls(*_args):
    controls = _controls_to_process()
    if not controls:
        return wutil.make_inViewMessage("No Temporal Controls to bake")

    operation = toolCommon.current_tool_operation()
    if operation is not None:
        start, end = _time_range_for(controls)
        if start is not None:
            toolCommon.ensure_operation_tint(
                operation, tint="range", timerange=(start, end), tint_key="temporal_controls_bake",
            )
        operation.set_total(len(controls)).set_status("Baking Temporal Controls")

    baked_targets = []
    for control in controls:
        if operation is not None and operation.cancelled:
            break
        target = _target_for(control)
        restore_map = _restore_map_for(control)
        # Drop every driver node first: pasteKey/setAttr both refuse to touch
        # a plug that's still driven by an expression, constraint, or connection.
        _delete_driver_nodes(control)
        if target:
            _extract_keys_to_target(control, target, restore_map)
            baked_targets.append(target)
        _delete_control_nodes(control)
        if operation is not None:
            operation.step()

    if baked_targets:
        cmds.select(baked_targets)
        return baked_targets
    return wutil.make_inViewMessage("Nothing baked")


def _extract_keys_to_target(control, target, restore_map):
    """Move the control's own keys (or current value) onto *target*'s channels.

    This copies the control's existing animCurve keyframes as-is -- at
    whatever times they were set -- rather than resampling every frame like
    ``cmds.bakeResults`` would. A channel with no keys on the control just
    hands its current value over instead. The control's own channels stay
    the free, keyable source of truth no matter which Position/Orientation
    space drove the object, so this needs no per-mode branching.
    """
    channels = restore_map.keys() if restore_map else CHANNELS
    for channel in channels:
        ctrl_plug = "{}.{}".format(control, channel)
        obj_plug = "{}.{}".format(target, channel)
        if not cmds.objExists(ctrl_plug) or not cmds.objExists(obj_plug):
            continue
        if cmds.getAttr(obj_plug, lock=True):
            continue

        if cmds.keyframe(ctrl_plug, query=True, keyframeCount=True):
            try:
                cmds.copyKey(control, attribute=channel)
                cmds.pasteKey(target, attribute=channel, option="replace")
            except RuntimeError:
                pass
        else:
            try:
                cmds.setAttr(obj_plug, cmds.getAttr(ctrl_plug))
            except RuntimeError:
                pass


def revert_controls(*_args):
    controls = _controls_to_process()
    if not controls:
        return wutil.make_inViewMessage("No Temporal Controls to revert")

    operation = toolCommon.current_tool_operation()
    if operation is not None:
        start, end = _time_range_for(controls)
        if start is not None:
            toolCommon.ensure_operation_tint(
                operation, tint="range", timerange=(start, end), tint_key="temporal_controls_revert",
            )
        operation.set_total(len(controls)).set_status("Reverting Temporal Controls")

    reverted_targets = []
    for control in controls:
        if operation is not None and operation.cancelled:
            break
        target = _target_for(control)
        restore_map = _restore_map_for(control)
        _delete_driver_nodes(control)

        if target:
            for channel, payload in restore_map.items():
                obj_plug = "{}.{}".format(target, channel)
                if not cmds.objExists(obj_plug):
                    continue
                mode = payload.get("mode")
                try:
                    if mode == "curve":
                        source = payload.get("source")
                        source_node = source.split(".")[0] if source else None
                        if source_node and cmds.objExists(source_node):
                            cmds.connectAttr(source, obj_plug, force=True)
                    elif mode == "value":
                        cmds.setAttr(obj_plug, payload.get("value"))
                except RuntimeError:
                    pass
            reverted_targets.append(target)

        _delete_control_nodes(control)
        if operation is not None:
            operation.step()

    if reverted_targets:
        cmds.select(reverted_targets)
        return reverted_targets
    return wutil.make_inViewMessage("Nothing reverted")


def _time_range_for(nodes):
    """Return ``(start, end)`` spanning every keyframe on *nodes*, or
    ``(None, None)`` if none of them have any -- used to tint the timeline
    over the range an operation is about to touch."""
    if not nodes:
        return None, None
    times = cmds.keyframe(nodes, query=True, timeChange=True) or []
    if not times:
        return None, None
    return min(times), max(times)


def _controls_to_process():
    """Selected Temporal Controls if any are selected, otherwise every one in the scene."""
    all_controls = cmds.ls("*." + TAG_ATTR, objectsOnly=True) or []
    if not all_controls:
        return []

    selected = set(selection.get_selected_objects(long=True))
    picked = [c for c in all_controls if cmds.ls(c, long=True)[0] in selected]
    return picked if picked else all_controls


def _target_for(control):
    plug = control + "." + TARGET_ATTR
    if not cmds.objExists(plug):
        return None
    target = cmds.getAttr(plug)
    return target if target and cmds.objExists(target) else None


def _existing_control_for(obj):
    long_obj = cmds.ls(obj, long=True)[0]
    for control in cmds.ls("*." + TAG_ATTR, objectsOnly=True) or []:
        target = _target_for(control)
        if target and cmds.ls(target, long=True)[0] == long_obj:
            return control
    return None


def _restore_map_for(control):
    plug = control + "." + RESTORE_ATTR
    if not cmds.objExists(plug):
        return {}
    raw = cmds.getAttr(plug)
    if not raw:
        return {}
    try:
        return json.loads(raw)
    except (TypeError, ValueError):
        return {}


def _driver_nodes_for(control):
    plug = control + "." + DRIVER_NODES_ATTR
    if not cmds.objExists(plug):
        return []
    raw = cmds.getAttr(plug)
    if not raw:
        return []
    try:
        nodes = json.loads(raw)
    except (TypeError, ValueError):
        return []
    return [node for node in nodes if node and cmds.objExists(node)]


def _delete_driver_nodes(control):
    """Delete every expression/matrix-network/constraint node this control's
    driving mechanism created on or around the *target* object. These live
    outside the control's own hierarchy, so Bake/Revert must clean them up
    explicitly before deleting the control itself."""
    nodes = _driver_nodes_for(control)
    if nodes:
        cmds.delete(nodes)


def _delete_control_nodes(control):
    """Delete the control (and, for Group/Aim Systems, its offset buffer --
    deleting the buffer cascades to the control and any helper it parents)."""
    plug = control + "." + DELETE_ROOT_ATTR
    delete_root = control
    if cmds.objExists(plug):
        stored = cmds.getAttr(plug)
        if stored and cmds.objExists(stored):
            delete_root = stored
    if cmds.objExists(delete_root):
        cmds.delete(delete_root)
    elif cmds.objExists(control):
        cmds.delete(control)
