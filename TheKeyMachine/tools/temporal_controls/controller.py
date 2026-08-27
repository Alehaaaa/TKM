"""Temporal Controls.

Left-click (``create_controls``) with a selection opens a small creation
dialog (see ``widgets.TemporalControlsDialog``) offering:

- **System**: the control's shape/hierarchy -- Simple (one curve), Group
  (curve + an offset buffer above it), Aim (curve + a small keyable
  aim-target control -- built from ``shapes.py``, not a raw locator --
  driving its rotation), or FK Chain (each new control parents under the
  previous one instead of flatly under the tool's root group).
- **Position / Orientation space**: how translate/rotate are driven back
  onto the object -- all six now go through a real
  ``pointConstraint``/``orientConstraint`` (see ``_drive_with_constraint``)
  instead of an expression/connectAttr hard-drive, so an object that's
  itself another Temporal Control's control stays nudgeable by hand on top
  of the drive instead of getting its channels locked outright. Camera
  Space adds a camera-relative anchor hierarchy above the visible control;
  position and orientation use independent camera-follow proxies, so mixed
  spaces remain valid. Object and World constrain coincident -- World used to be a hand-built
  parent-safe matrix network, but a plain constraint already accounts for
  the object and control having different parents, so that network was
  redundant. Relative, Grab Release, and Child constrain with the offset
  preserved instead (Grab Release is the same offset-preserving constraint
  as Relative -- a temporary "grab" that Revert cleanly lets go of). When
  both Position and Orientation use Relative Space with multiple objects
  selected, the last-selected object is instead the reference: it receives no
  control, every earlier selection's complete control hierarchy is parented
  directly below it. Existing object keys are converted at those same key
  times to keep their world-space poses; reference-parent keys never add
  samples, and an unkeyed object stays unkeyed at its current pose. A single
  selection still receives a normal control. Scale
  isn't offered a space choice and always passes straight through
  coincident, same as Object/World -- but, like every other channel
  group, through a real ``scaleConstraint`` rather than an expression.
  Nothing in this tool drives anything through an expression anymore.

Confirming the dialog calls ``create_controls_with_options()``, which
builds one control per object: sized and positioned to match it, with a
real copy of whatever animation it already had -- translate/rotate *and*
every other keyframed custom attribute (enums included) -- copied onto
the new control first if it was already animated. Every space uses one setup
path: ``_gather_copyable_animation`` finds the object's own per-channel keys;
``_TransformSpaceTransfer.capture`` reads its world matrices before any
control hierarchy or driver is built; then the same object's ``apply`` method
converts those exact keys into the completed destination space. Custom
attributes use ``_copy_source_extra_keys_to_control`` because they have no
spatial conversion
-- so the object keeps showing its original motion/values, now via
control, for the animator to key or nudge on top of instead of it just
vanishing the moment control takes over, for then to be applied back onto
the object at Bake time. This step reports progress through the same
progress bar/ETA (``ToolOperation``) the rest of control creation already
uses -- a heavily-keyed object can take far longer to hand off than the
control build itself. Only then does the object's own live connection
actually get freed up for the constraint to drive (``_capture_channel``),
and driving the object back through whichever mechanism the chosen spaces
call for -- *unless* the object being controlled is itself another
Temporal Control's control (nesting one Temporal Control inside another).
In that case Position/Orientation space
is ignored entirely and ``_parent_nested_control`` makes the new control a
real Maya parent of the nested one instead -- no constraint, no
expression, no connection of any kind, just an ordinary child transform
that keeps moving/keying exactly like any other child would. Bake/Revert
detect this the same way (``_nested_parent_for``) and reparent the nested
control back out before removing the new one, baking its motion down onto
its own channels first if Bake was used (``_bake_nested_control``).

The command-backed right-click menu declared in ``__init__.py`` gives:

- **Bake Mode**: Bake Keys or Bake Frames -- one setting, shared by every
  bake path in this tool. Both key target from control's world matrix at a
  set of times (``_key_target_from_control``/``_world_matrix_local_values``,
  a pure matrix query, not ``cmds.bakeResults``): Bake Frames samples every
  frame across the target's full animated range; Bake Keys samples only
  control's own key times, so the result lands "as keyed", not resampled.
- **Space**: re-drive the selected controls through a different Position/
  Orientation space live (``switch_controls_space``) -- everything
  ``SWITCHABLE_SPACES`` offers except Grab Release, which is a one-shot
  "temporary grab" concept, not something to switch back into later. A
  switch is one atomic OFF/snapshot/rebuild/ON transaction: restore the
  target's untouched source curves, capture their original world animation,
  convert it into the destination control space, then reconnect the rig.
- **Toggle Rig** (``toggle_temporal_control_rigs``): turn a rig OFF to expose
  its target's source animation, or ON to snapshot that currently-live source
  back into the control's current space and reconnect it.
- **Mute and Revert** / **Mute and Bake** (``mute_and_revert`` /
  ``mute_and_bake``): disconnect a control the same way Revert/Bake do,
  but leave the control node itself in the scene instead of deleting it,
  so it can drive its object again later without being recreated.
- **Revert** / **Bake** (``revert_controls`` / ``bake_controls``): remove
  the control entirely -- restoring the object's original channels (Revert)
  or extracting the control's animation onto it first (Bake). Both work
  the same regardless of which System/Space combination built the control,
  since the control's own channels always stay the free, keyable source of
  truth -- only how that result reaches the object differs. Both work from
  either end of the selection -- the control itself, or the object it
  drives.
- **Temp Controls Panel** (``open_temp_controls_panel``): opens ``panel.py``'s
  dedicated window -- every "rig" (target object + every Temporal Control
  tracing back to it, see ``list_rigs``/``root_target_for``) on the left,
  that rig's controls next to it, and, once a control is picked, a sidebar
  for its Position/Orientation space (independently of each other, unlike
  the live Space list above -- ``set_control_space``), shape
  (``set_control_shape``), size/rotation (``scale_control``/
  ``set_control_orientation``), and Add Child/Add Parent/Remove/Edit Pivot/
  Reset Pivot control-structure actions.

Every control lives under a single ``TkmSceneNode`` group so the tool can
find and clean up its own nodes without touching anything else in the
scene, and is tagged with a locked boolean attribute (the same pattern
``global_curve`` uses) so Bake/Revert can look controls up by attribute
instead of by name or hierarchy.

Implementation module. Public entry point is ``api.py``.
"""

import json
import math

from maya import cmds

from TheKeyMachine.core.Qt import QtCore, QtWidgets  # type: ignore
from TheKeyMachine.core import debug, i18n, trigger
from TheKeyMachine.maya import animation, maya_api, selection
from TheKeyMachine.maya.runtime import TkmSceneNode
from TheKeyMachine.data import icons
from TheKeyMachine.tools import common as toolCommon
from TheKeyMachine.tools.temporal_controls import shapes
from TheKeyMachine.tools.temporal_controls import (
    DEFAULT_BAKE_MODE,
    DEFAULT_SPACE,
    DEFAULT_SYSTEM,
)
import TheKeyMachine.ui.widgets.util as wutil


class _ControlsBus(QtCore.QObject):
    """Direct notification for the Temp Controls Panel's live sync -- see
    create_controls_with_options' emit and panel.py's
    _connect_live_refresh."""

    controlsCreated = QtCore.Signal()


controls_bus = _ControlsBus()

ROOT_GROUP = "Temporal_Controls"

TAG_ATTR = "tkmTemporalControl"
TARGET_ATTR = "tkmTemporalTarget"
DELETE_ROOT_ATTR = "tkmTemporalDeleteRoot"
RESTORE_ATTR = "tkmTemporalRestore"
DRIVER_NODES_ATTR = "tkmTemporalDriverNodes"
CAMERA_POSITION_GROUP_ATTR = "tkmTemporalCameraPositionGroup"
CAMERA_ORIENTATION_GROUP_ATTR = "tkmTemporalCameraOrientationGroup"
CAMERA_POSITION_SOURCE_ATTR = "tkmTemporalCameraPositionSource"
CAMERA_ORIENTATION_SOURCE_ATTR = "tkmTemporalCameraOrientationSource"
NESTED_PARENT_ATTR = "tkmTemporalNestedParent"
NESTED_ROOT_ATTR = "tkmTemporalNestedRoot"
MUTED_ATTR = "tkmTemporalMuted"
# JSON list of extra attribute names copied to control at creation; _copied_attrs_for reads it back for Bake.
COPIED_ATTRS_ATTR = "tkmTemporalCopiedAttrs"

# Backs the Temp Controls Panel: shape/size/orientation, position/orientation space, lock, and Add Child/Parent extras.
BASE_RADIUS_ATTR = "tkmTemporalBaseRadius"
SHAPE_ATTR = "tkmTemporalShape"
SIZE_MULT_ATTR = "tkmTemporalSizeMult"
ORIENTATION_ATTR = "tkmTemporalOrientation"
EXTRA_ATTR = "tkmTemporalExtra"
POSITION_SPACE_ATTR = "tkmTemporalPositionSpace"
ORIENTATION_SPACE_ATTR = "tkmTemporalOrientationSpace"
LOCK_SPACE_ATTR = "tkmTemporalSpaceLocked"
# Selection-order reference for a physically-parented Relative/Relative control, kept for switching back later.
RELATIVE_SOURCE_ATTR = "tkmTemporalRelativeSource"

TRANSLATE_CHANNELS = ("translateX", "translateY", "translateZ")
ROTATE_CHANNELS = ("rotateX", "rotateY", "rotateZ")
SCALE_CHANNELS = ("scaleX", "scaleY", "scaleZ")
CHANNELS = TRANSLATE_CHANNELS + ROTATE_CHANNELS + SCALE_CHANNELS

DEFAULT_RADIUS = 10.0

# Which shapes.SHAPES entry the Aim system's target pole uses; not yet user-facing.
AIM_TARGET_SHAPE = "sphere"

# Temp Controls Panel defaults (see the attribute block above).
DEFAULT_SIZE_MULT = 1.0
# Exponent step for the Size slider's -100..100 range; see TempControlsPanelWindow._size_factor_for.
SIZE_NUDGE_STEP = 1.25

# (id, (axis, degrees) or None) rotation that reaches each Rotation-slider pose from "up" -- slider order.
ORIENTATIONS = (
    ("up", None),
    ("down", ("x", 180.0)),
    ("forward", ("x", -90.0)),
    ("backward", ("x", 90.0)),
    ("right", ("z", 90.0)),
    ("left", ("z", -90.0)),
)
DEFAULT_ORIENTATION = ORIENTATIONS[0][0]
_ORIENTATION_TRANSFORMS = dict(ORIENTATIONS)

# Super Mode maps onto cmds.bakeResults' simulation flag for nested-control baking (the only remaining bakeResults path): correct-but-slower vs Maya's faster shortcut.
SUPER_MODE_SETTING = "super_mode"

_SETTINGS_NAMESPACE = "temporal_controls"

_temporal_controls_dialog = None
# Toolbar button that opened the creation dialog, captured here since the click's own operation is closed by confirm time.
_temporal_controls_source_button = None


# ----------------------------------------------------------------------
# Entry point / dialog plumbing
# ----------------------------------------------------------------------


def create_controls(*_args):
    global _temporal_controls_source_button
    operation = toolCommon.current_tool_operation()
    if operation is not None and wutil.is_valid_widget(operation.anchor_widget):
        _temporal_controls_source_button = operation.anchor_widget

    selected = [
        obj
        for obj in selection.get_selected_objects(long=True, ordered=True)
        if cmds.ls(obj, type="transform")
    ]
    if not selected:
        return wutil.make_inViewMessage("Select at least one object")

    _open_creation_dialog(selected)


def _open_creation_dialog(objects):
    global _temporal_controls_dialog
    from TheKeyMachine.tools.temporal_controls.widgets import TemporalControlsDialog

    if _temporal_controls_dialog is not None and wutil.is_valid_widget(
        _temporal_controls_dialog
    ):
        _temporal_controls_dialog.close()

    parent = wutil.get_maya_qt(qt=QtWidgets.QWidget)
    source_button = _temporal_controls_source_button

    def _on_confirmed(system, position_space, orientation_space, label, color):
        # Queue the edit so the apply command owns undo/rollback after this UI operation closes.
        QtCore.QTimer.singleShot(
            0,
            lambda: trigger.execute_command(
                "temporal_controls_create_apply",
                objects,
                system=system,
                position_space=position_space,
                orientation_space=orientation_space,
                label=label,
                color=color,
                _tkm_anchor_widget=source_button,
            ),
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
        "system": settings.get_setting(
            "last_system", DEFAULT_SYSTEM, namespace=_SETTINGS_NAMESPACE
        ),
        "position_space": settings.get_setting(
            "last_position_space", DEFAULT_SPACE, namespace=_SETTINGS_NAMESPACE
        ),
        "orientation_space": settings.get_setting(
            "last_orientation_space", DEFAULT_SPACE, namespace=_SETTINGS_NAMESPACE
        ),
        "color": settings.get_setting(
            "last_color", None, namespace=_SETTINGS_NAMESPACE
        ),
    }


def get_bake_mode():
    from TheKeyMachine.core import settings

    return settings.get_setting(
        "bake_mode", DEFAULT_BAKE_MODE, namespace=_SETTINGS_NAMESPACE
    )


def set_bake_mode(mode_id):
    from TheKeyMachine.core import settings

    settings.set_settings({"bake_mode": mode_id}, namespace=_SETTINGS_NAMESPACE)


def is_super_mode_enabled():
    from TheKeyMachine.core import settings

    return bool(
        settings.get_setting(SUPER_MODE_SETTING, False, namespace=_SETTINGS_NAMESPACE)
    )


def set_super_mode_enabled(enabled):
    from TheKeyMachine.core import settings

    settings.set_settings(
        {SUPER_MODE_SETTING: bool(enabled)}, namespace=_SETTINGS_NAMESPACE
    )


def _super_mode_simulation_flag():
    """The ``cmds.bakeResults(simulation=...)`` value Super Mode maps
    onto -- see SUPER_MODE_SETTING's documentation above."""
    return not is_super_mode_enabled()


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
    anchor_widget=None,
    tool_operation=None,
):
    objects = [obj for obj in objects if cmds.objExists(obj)]
    _debug_log(
        "creation requested",
        objects=objects,
        system=system,
        position_space=position_space,
        orientation_space=orientation_space,
        label=label,
        color=color,
    )
    if not objects:
        _debug_log("creation rejected", reason="no existing selected objects")
        return wutil.make_inViewMessage("Nothing left to control -- selection changed")

    # Relative/Relative physically parents (last object is the reference); mixed spaces stay on the independent constraint path.
    relative_parent = None
    if (
        len(objects) > 1
        and position_space == "relative"
        and orientation_space == "relative"
    ):
        relative_parent = objects[-1]
        objects = objects[:-1]
    _debug_log(
        "creation selection resolved",
        controlled_objects=objects,
        relative_reference=relative_parent,
        reference_receives_control=False if relative_parent else None,
    )

    operation = toolCommon.require_tool_operation(tool_operation)
    camera = None
    if "camera" in (position_space, orientation_space):
        camera = _active_viewport_camera()
        _debug_log("camera space resolved", camera=camera)
        if not camera:
            _debug_log("creation rejected", reason="no active viewport camera")
            return wutil.make_inViewMessage(
                "Focus or show a viewport to use Camera Space"
            )
    group = TkmSceneNode.root().child(ROOT_GROUP, icon=icons.temporal_controls)

    # The reference is a parent space, not an animation source, so progress/work totals skip it.
    start, end = _time_range_for(objects)
    if start is not None:
        toolCommon.ensure_operation_tint(
            operation,
            tint="range",
            timerange=(start, end),
            tint_key="temporal_controls",
        )
    else:
        toolCommon.ensure_operation_tint(
            operation,
            tint="current",
            default_mode="current_frame",
            tint_key="temporal_controls",
        )
    options = {
        "system": system,
        "position_space": position_space,
        "orientation_space": orientation_space,
        "label": (label or "").strip(),
        "color": color,
        "camera": camera,
        "relative_parent": relative_parent,
    }

    # Pre-scan objects for their existing animation so the progress bar's ETA reflects real work, not just object count.
    pending = [obj for obj in objects if not _existing_control_for(obj)]
    animation_by_obj = {obj: _gather_copyable_animation(obj) for obj in pending}
    total_steps = len(objects) + sum(
        _creation_animation_work(animation)
        for animation in animation_by_obj.values()
    )
    operation.set_total(total_steps).set_status("Creating Temporal Controls")
    _debug_log(
        "creation workload prepared",
        pending_objects=pending,
        total_steps=total_steps,
        tint_range=(start, end) if start is not None else None,
    )

    new_controls = []
    locked_report = []
    chain_parent = None
    for obj in objects:
        if operation.cancelled:
            break
        if not _existing_control_for(obj):
            options["chain_parent"] = chain_parent if system == "fk_chain" else None
            control, chain_anchor = _create_control_for(
                obj,
                group.name,
                options,
                locked_report=locked_report,
                operation=operation,
                animation=animation_by_obj.get(obj),
            )
            if control:
                new_controls.append(control)
                chain_parent = chain_anchor
        operation.step()

    if locked_report:
        _warn_locked_attributes(locked_report, anchor_widget=operation.anchor_widget)

    if new_controls:
        cmds.select(new_controls)
        controls_bus.controlsCreated.emit()
        _debug_log(
            "creation completed",
            controls=new_controls,
            locked_channels=locked_report,
            cancelled=operation.cancelled,
        )
        return new_controls
    _debug_log(
        "creation completed",
        controls=[],
        locked_channels=locked_report,
        cancelled=operation.cancelled,
    )
    return wutil.make_inViewMessage("Selected objects already have Temporal Controls")


def _warn_locked_attributes(locked_plugs, anchor_widget=None):
    """Surface every locked attribute _drive_with_constraint had to skip
    as one auto-hiding message, anchored to *anchor_widget*. Falls back
    to a plain cmds.warning if the message widget can't be built."""
    unique_plugs = list(dict.fromkeys(locked_plugs))
    short_plugs = [_short_plug_name(plug) for plug in unique_plugs]
    try:
        from TheKeyMachine.ui.widgets import customDialogs

        lines = "".join("<text>{}</text>".format(plug) for plug in short_plugs)
        tooltip = (
            "<icon>{}</icon><title>Couldn't connect locked attributes</title>"
            "<text>The following attributes are locked and were left "
            "unconnected:</text>{}"
        ).format(icons.warning, lines)
        customDialogs.QFlatAutoHideMessage.show_message(
            tooltip, duration=5000, anchor_widget=anchor_widget
        )
    except Exception:
        cmds.warning(
            "Temporal Controls: couldn't connect locked attributes: {}".format(
                ", ".join(short_plugs)
            )
        )


def _plug(node, attribute):
    """``"node.attribute"``, the one place this module builds a plug
    string."""
    return "{}.{}".format(node, attribute)


def _short_plug_name(plug):
    """``some|long|dag|Path:node.attribute`` -> ``node.attribute`` -- the
    full path is Maya-uniqueness noise the user doesn't need to see in a
    "here's what I couldn't connect" message; the object's own (possibly
    namespaced) short name is all that's needed to identify it."""
    obj_part, _, attr_part = plug.rpartition(".")
    short_obj = obj_part.split("|")[-1] if obj_part else obj_part
    return _plug(short_obj, attr_part) if short_obj else plug


_TOOL_DEBUG = debug.is_enabled()


def _debug_log(event, **details):
    """Print one structured Temporal Controls diagnostic when debug is on."""
    if not _TOOL_DEBUG:
        return
    print("[TKM Temporal Controls] {}".format(event))
    for name in sorted(details):
        try:
            value = repr(details[name])
        except Exception as exc:
            value = "<repr failed: {}>".format(exc)
        print("    {}: {}".format(name, value))


def _debug_log_creation_step(
    step,
    obj,
    options,
    control=None,
    delete_root=None,
    chain_anchor=None,
    translate_channels=None,
    rotate_channels=None,
    scale_channels=None,
    driver_nodes=None,
):
    """Trace one control-creation decision point when _TOOL_DEBUG is on.
    Called at each real step in _create_control_for, not just at the end,
    so a build that fails partway still leaves a trail."""
    details = {
        "source": obj,
        "system": options.get("system"),
        "position_space": options.get("position_space"),
        "orientation_space": options.get("orientation_space"),
        "relative_parent": options.get("relative_parent"),
        "label": options.get("label"),
        "color": options.get("color"),
    }
    if control and cmds.objExists(control):
        try:
            obj_pos = (
                cmds.xform(obj, query=True, worldSpace=True, translation=True)
                if cmds.objExists(obj)
                else None
            )
            obj_rot = (
                cmds.xform(obj, query=True, worldSpace=True, rotation=True)
                if cmds.objExists(obj)
                else None
            )
            ctrl_pos = cmds.xform(
                control, query=True, worldSpace=True, translation=True
            )
            ctrl_rot = cmds.xform(control, query=True, worldSpace=True, rotation=True)
        except Exception as exc:
            obj_pos = obj_rot = ctrl_pos = ctrl_rot = "<xform query failed: {}>".format(
                exc
            )
        details.update(
            {
                "shape": shapes.DEFAULT_SHAPE,
                "radius": _control_radius(obj) if cmds.objExists(obj) else None,
                "control": control,
                "delete_root": delete_root,
                "chain_anchor": chain_anchor,
                "source_world_position": obj_pos,
                "source_world_rotation": obj_rot,
                "control_world_position": ctrl_pos,
                "control_world_rotation": ctrl_rot,
            }
        )
    if translate_channels is not None or rotate_channels is not None:
        details.update(
            {
                "translate_channels": translate_channels,
                "rotate_channels": rotate_channels,
                "scale_channels": scale_channels,
                "driver_nodes": driver_nodes,
            }
        )
    _debug_log("creation {}".format(step), **details)


def _create_control_for(
    obj, group, options, locked_report=None, operation=None, animation=None
):
    is_nested = _is_temporal_control(obj)
    source_animation = animation or _gather_copyable_animation(obj)
    transfer = None
    if not is_nested:
        # First mutating step regardless of destination space; nothing parented/constrained yet.
        transfer = _TransformSpaceTransfer.from_animation(
            obj, source_animation, operation
        )
        _debug_log(
            "creation transfer prepared",
            source=obj,
            groups=[
                {
                    "kind": group_data.kind,
                    "key_data": group_data.key_data,
                    "sample_times": group_data.sample_times,
                }
                for group_data in transfer.groups
            ],
        )
        if not transfer.capture():
            _debug_log("creation aborted", source=obj, reason="world capture failed")
            cmds.warning("Temporal Controls: could not capture source world animation")
            return None, None

    control, delete_root, chain_anchor = _build_control_hierarchy(obj, group, options)
    _debug_log_creation_step(
        "built",
        obj,
        options,
        control=control,
        delete_root=delete_root,
        chain_anchor=chain_anchor,
    )

    if options.get("color"):
        # Color the whole hierarchy, not just control, so secondary controls like Aim's target match too.
        _apply_control_color(delete_root, options["color"])

    if is_nested:
        # Nested control: real-parented via _parent_nested_control, which must run before _tag_control since it changes obj's DAG path.
        obj = _parent_nested_control(control, obj)
        _tag_control(control, obj, delete_root)
        _debug_log_creation_step(
            "nested (parented directly, no channel-driving)",
            obj,
            options,
            control=control,
        )
        return control, chain_anchor

    relative_parent = options.get("relative_parent")
    if relative_parent:
        _debug_log(
            "relative hierarchy decision",
            control=control,
            reference=relative_parent,
            delete_root=delete_root,
        )
        control, delete_root = _parent_control_system(
            control, delete_root, relative_parent
        )
        chain_anchor = control

    _tag_control(control, obj, delete_root)
    if relative_parent:
        _set_locked_string_attr(
            control,
            RELATIVE_SOURCE_ATTR,
            (cmds.ls(relative_parent, long=True) or [relative_parent])[0],
        )

    # Camera anchors must exist before captured world matrices are decomposed to locals.
    creation_camera_nodes = {}
    for group_data in transfer.groups:
        group_kind = group_data.kind
        space_mode = (
            options["position_space"]
            if group_kind == "translate"
            else options["orientation_space"]
        )
        if space_mode == "camera":
            creation_camera_nodes[group_kind] = _camera_space_driver(
                control, group_kind, options.get("camera")
            )

    if not transfer.apply(control):
        _debug_log(
            "creation aborted",
            source=obj,
            control=control,
            delete_root=delete_root,
            reason="transform key application failed",
        )
        cmds.warning(
            "Temporal Controls: could not copy source transform keys to {}".format(
                control
            )
        )
        if cmds.objExists(delete_root):
            cmds.delete(delete_root)
        return None, None

    # Transform animation already took the world-matrix path; reuse the copier only for custom attributes.
    _translate_key_data, _rotate_key_data, extra_attrs = source_animation
    copied_attrs = _copy_source_extra_keys_to_control(
        control, obj, extra_attrs, operation=operation
    )
    if copied_attrs:
        TkmSceneNode(control).set_attr(COPIED_ATTRS_ATTR, json.dumps(copied_attrs))

    restore_map = {}
    for channel in CHANNELS:
        captured = _capture_channel(control, obj, channel)
        if captured:
            channel_name, payload = captured
            restore_map[channel_name] = payload

    TkmSceneNode(control).set_attr(RESTORE_ATTR, json.dumps(restore_map))

    # Per-group driver nodes so the panel can re-space Position/Orientation independently.
    driver_nodes = {}
    translate_channels = [c for c in TRANSLATE_CHANNELS if c in restore_map]
    rotate_channels = [c for c in ROTATE_CHANNELS if c in restore_map]
    scale_channels = [c for c in SCALE_CHANNELS if c in restore_map]

    node = TkmSceneNode(control)
    if translate_channels:
        if "translate" in creation_camera_nodes:
            driver_nodes["translate"] = creation_camera_nodes[
                "translate"
            ] + _drive_constraint_for_space(
                control,
                obj,
                "translate",
                options["position_space"],
                locked_report=locked_report,
            )
        else:
            driver_nodes["translate"] = _drive_group(
                control,
                obj,
                translate_channels,
                options["position_space"],
                restore_map,
                locked_report=locked_report,
                space_source=options.get("camera"),
            )
        node.set_attr(POSITION_SPACE_ATTR, options["position_space"])
    if rotate_channels:
        if "rotate" in creation_camera_nodes:
            driver_nodes["rotate"] = creation_camera_nodes[
                "rotate"
            ] + _drive_constraint_for_space(
                control,
                obj,
                "rotate",
                options["orientation_space"],
                locked_report=locked_report,
            )
        else:
            driver_nodes["rotate"] = _drive_group(
                control,
                obj,
                rotate_channels,
                options["orientation_space"],
                restore_map,
                locked_report=locked_report,
                space_source=options.get("camera"),
            )
        node.set_attr(ORIENTATION_SPACE_ATTR, options["orientation_space"])
    # Scale driving is disabled: scaleConstraint has been seen crashing on locked/non-writable scale channels.

    node.set_attr(DRIVER_NODES_ATTR, json.dumps(driver_nodes))
    # Seed the panel's lock as on when both spaces matched at creation time.
    if (
        translate_channels
        and rotate_channels
        and options["position_space"] == options["orientation_space"]
    ):
        node.set_attr(LOCK_SPACE_ATTR, True, attributeType="bool")

    _debug_log_creation_step(
        "driven",
        obj,
        options,
        control=control,
        translate_channels=translate_channels,
        rotate_channels=rotate_channels,
        scale_channels=scale_channels,
        driver_nodes=driver_nodes,
    )
    return control, chain_anchor


def _build_control_hierarchy(obj, group, options):
    """Build the control (and, for some Systems, its secondary nodes).

    Returns ``(control, delete_root, chain_anchor)``: delete_root is what
    Bake/Revert deletes to remove everything this System added (control
    itself, or the offset buffer for Group/Aim); chain_anchor is what the
    next object's control parents under for FK Chain."""
    system = options.get("system", DEFAULT_SYSTEM)
    label = options.get("label") or ""
    radius = _control_radius(obj)
    short_name = obj.split("|")[-1].split(":")[-1]
    base_name = "{}_{}".format(label, short_name) if label else short_name

    control = shapes.build(
        shapes.DEFAULT_SHAPE, "{}_temporalCtrl#".format(base_name), radius
    )
    cmds.matchTransform(control, obj, position=True, rotation=True, scale=False)

    top_node = control
    if system in ("group", "aim"):
        top_node = cmds.group(control, name="{}_temporalBuf#".format(base_name))

    if system == "aim":
        _add_aim_target(control, top_node, base_name, radius)

    # Space-specific parenting happens only after source world animation is captured.
    parent_target = group
    if (
        not options.get("relative_parent")
        and system == "fk_chain"
        and options.get("chain_parent")
    ):
        parent_target = options["chain_parent"]
    cmds.parent(top_node, parent_target)

    return control, top_node, control


def _reset_offset_parent_matrix(node):
    """Reset *node*'s ``offsetParentMatrix`` to identity."""
    plug = "{}.offsetParentMatrix".format(node)
    if not cmds.objExists(plug) or not cmds.getAttr(plug, settable=True):
        return
    try:
        cmds.setAttr(
            plug,
            [
                1.0, 0.0, 0.0, 0.0,
                0.0, 1.0, 0.0, 0.0,
                0.0, 0.0, 1.0, 0.0,
                0.0, 0.0, 0.0, 1.0,
            ],
            type="matrix",
        )
    except RuntimeError:
        pass


def _parent_control_system(control, delete_root, parent):
    """Parent a complete System and return its resolved post-parent paths."""
    root_matches = cmds.ls(delete_root, long=True) or []
    control_matches = cmds.ls(control, long=True) or []
    if not root_matches or not control_matches:
        raise RuntimeError("Temporal Controls hierarchy could not be resolved")
    old_root = root_matches[0]
    control_suffix = control_matches[0][len(old_root) :]
    parented = cmds.parent(old_root, parent, absolute=True) or []
    new_roots = cmds.ls(parented[0], long=True) if parented else []
    if not new_roots:
        raise RuntimeError("Temporal Controls hierarchy could not be parented")
    new_root = new_roots[0]
    _reset_offset_parent_matrix(new_root)
    new_controls = cmds.ls(new_root + control_suffix, long=True) or []
    if not new_controls:
        raise RuntimeError("Temporal Controls control could not be resolved")
    _reset_offset_parent_matrix(new_controls[0])
    return new_controls[0], new_root


def _add_aim_target(control, buffer_node, base_name, radius):
    # Built from shapes.SHAPES, not cmds.spaceLocator, so it picks up _apply_control_color like other controls.
    target_radius = max(radius * 0.15, 0.5)
    aim_target = shapes.build(
        AIM_TARGET_SHAPE,
        "{}_temporalAim#".format(base_name),
        target_radius,
    )
    _initialize_control_visual_state(aim_target, target_radius, AIM_TARGET_SHAPE)
    cmds.matchTransform(aim_target, control, position=True, rotation=True)
    cmds.setAttr(
        aim_target + ".translateZ",
        cmds.getAttr(aim_target + ".translateZ") + radius * 2.0,
    )
    cmds.parent(aim_target, buffer_node)
    cmds.aimConstraint(
        aim_target,
        control,
        worldUpType="scene",
        aimVector=(0, 0, 1),
        maintainOffset=False,
    )


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


def _apply_control_color(root, color_hex):
    """Color *root* and everything under it -- not just *root*'s own shapes --
    so a secondary control parented alongside/under it (the Aim system's
    aim-target, the Group/Aim buffer) picks up the chosen color too, instead
    of only the top control being styled while secondary nodes stay default."""
    rgb = _hex_to_rgb01(color_hex)
    descendants = cmds.listRelatives(root, allDescendents=True, fullPath=True) or []
    for node in [root] + descendants:
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
        return tuple(int(color_hex[i : i + 2], 16) / 255.0 for i in (0, 2, 4))
    except ValueError:
        return (0.2, 0.6, 0.8)


# ----------------------------------------------------------------------
# Temp Controls Panel: shape / size / orientation
# ----------------------------------------------------------------------
# Size/orientation apply directly to the control's CVs rather than rebuilding the curve, so shape swaps keep them.


def _control_shape_nodes(control):
    return cmds.listRelatives(control, shapes=True, fullPath=True) or []


def _control_base_radius(control):
    stored = TkmSceneNode(control).get_attr(BASE_RADIUS_ATTR)
    try:
        if stored is not None:
            return float(stored)
    except (TypeError, ValueError):
        pass
    # Older Aim controls without visual-state metadata still need shape swaps to preserve size.
    try:
        bbox = cmds.xform(control, query=True, boundingBox=True)
    except RuntimeError:
        bbox = None
    if bbox and len(bbox) == 6:
        span = max(bbox[3] - bbox[0], bbox[4] - bbox[1], bbox[5] - bbox[2])
        if span > 1e-6:
            return span * 0.5
    return DEFAULT_RADIUS


def _ensure_control_base_radius(control):
    """Persist an inferred radius before editing a legacy secondary control."""
    radius = _control_base_radius(control)
    if not cmds.objExists(_plug(control, BASE_RADIUS_ATTR)):
        TkmSceneNode(control).set_attr(BASE_RADIUS_ATTR, radius)
    return radius


def get_control_size_mult(control):
    stored = TkmSceneNode(control).get_attr(SIZE_MULT_ATTR)
    try:
        return float(stored) if stored is not None else DEFAULT_SIZE_MULT
    except (TypeError, ValueError):
        return DEFAULT_SIZE_MULT


def get_control_orientation(control):
    stored = TkmSceneNode(control).get_attr(ORIENTATION_ATTR)
    return stored if stored in _ORIENTATION_TRANSFORMS else DEFAULT_ORIENTATION


def get_control_shape_id(control):
    stored = TkmSceneNode(control).get_attr(SHAPE_ATTR)
    if stored:
        return stored
    # Backward compatibility for Aim targets created before visual state was recorded.
    if "_temporalAim" in str(control).rsplit("|", 1)[-1]:
        return AIM_TARGET_SHAPE
    return shapes.DEFAULT_SHAPE


def _shape_cv_selector(shape_nodes):
    """Every curve CV across *shape_nodes*, as individual ``node.cv[i]``
    component strings cmds.scale/cmds.rotate can act on in one call --
    listed through ``cmds.ls(..., flatten=True)`` rather than a
    ``node.cv[0:n-1]`` range built from a queried CV count, which isn't a
    reliable way to size a curve's CVs across shape types/degrees."""
    selectors = []
    for shape_node in shape_nodes:
        if not cmds.objExists(shape_node) or cmds.nodeType(shape_node) != "nurbsCurve":
            continue
        selectors += cmds.ls("{}.cv[*]".format(shape_node), flatten=True) or []
    return selectors


def _shape_color(control):
    """Read back the override color currently applied to control's own
    shape nodes (if any), so a shape swap (set_control_shape) can re-apply
    it to the new shape instead of resetting to Maya's default gray."""
    for shape_node in _control_shape_nodes(control):
        if cmds.attributeQuery(
            "overrideRGBColors", node=shape_node, exists=True
        ) and cmds.getAttr(shape_node + ".overrideRGBColors"):
            return tuple(cmds.getAttr(shape_node + ".overrideColorRGB")[0])
    return None


def _apply_shape_color(shape_nodes, rgb):
    if not rgb:
        return
    for shape_node in shape_nodes:
        if not cmds.attributeQuery("overrideEnabled", node=shape_node, exists=True):
            continue
        cmds.setAttr(shape_node + ".overrideEnabled", True)
        cmds.setAttr(shape_node + ".overrideRGBColors", True)
        cmds.setAttr(shape_node + ".overrideColorRGB", *rgb)


def get_control_color(control):
    """The override color currently applied to control's own shape nodes
    (see _shape_color), as a "#rrggbb" hex string, or None if it has none
    -- used by the Temp Controls Panel's rig list to show each rig's color
    swatch."""
    rgb = _shape_color(control)
    if not rgb:
        return None
    return "#{:02x}{:02x}{:02x}".format(
        *(max(0, min(255, round(channel * 255))) for channel in rgb)
    )


def set_control_color(control, color_hex):
    """Apply *color_hex* to an existing Temporal Control hierarchy."""
    if not cmds.objExists(control) or not _is_temporal_control(control):
        return False
    delete_root = TkmSceneNode(control).get_attr(DELETE_ROOT_ATTR) or control
    if not cmds.objExists(delete_root):
        delete_root = control
    _apply_control_color(delete_root, color_hex)
    return True


def set_rig_color(root_target, color_hex):
    """Apply one color to every Temporal Control belonging to a panel rig."""
    changed = False
    for control in list_rigs().get(root_target, []):
        changed = set_control_color(control, color_hex) or changed
    return changed


def scale_control(control, factor):
    """Scale control's curve CVs by *factor* (a relative multiplier, e.g.
    1.02 to grow 2%). Scales each CV directly in object space rather than
    ``cmds.scale``'s pivot flag, which is a world-space point regardless
    of objectSpace and grows a control away from the origin, not itself."""
    if (
        not cmds.objExists(control)
        or not factor
        or factor <= 0
        or abs(factor - 1.0) < 1e-9
    ):
        return False
    cvs = _shape_cv_selector(_control_shape_nodes(control))
    if not cvs:
        return False
    _ensure_control_base_radius(control)
    for cv in cvs:
        x, y, z = cmds.xform(cv, query=True, translation=True, objectSpace=True)
        cmds.xform(
            cv, translation=(x * factor, y * factor, z * factor), objectSpace=True
        )
    node = TkmSceneNode(control)
    node.set_attr(SIZE_MULT_ATTR, get_control_size_mult(control) * factor)
    return True


def _rotate_point(x, y, z, axis, degrees):
    """Rotate (x, y, z) by *degrees* around one local principal *axis*
    ("x" or "z" -- see _ORIENTATION_TRANSFORMS, nothing here needs "y")."""
    theta = math.radians(degrees)
    cos_t, sin_t = math.cos(theta), math.sin(theta)
    if axis == "x":
        return x, y * cos_t - z * sin_t, y * sin_t + z * cos_t
    if axis == "z":
        return x * cos_t - y * sin_t, x * sin_t + y * cos_t, z
    return (
        x * cos_t + z * sin_t,
        y,
        -x * sin_t + z * cos_t,
    )  # "y", unused today but complete


def _apply_orientation_transform(cvs, transform):
    """Apply one _ORIENTATION_TRANSFORMS entry (an (axis, degrees) pair,
    or None for "up"/identity) to every cv in *cvs*, in place in the
    scene. Assumes *cvs* are currently at "up" -- a freshly built shape
    (set_control_shape's own temp curve) always starts there."""
    if not transform:
        return
    axis, degrees = transform
    for cv in cvs:
        x, y, z = cmds.xform(cv, query=True, translation=True, objectSpace=True)
        cmds.xform(
            cv, translation=_rotate_point(x, y, z, axis, degrees), objectSpace=True
        )


def set_control_orientation(control, orientation_id):
    """Snap control's curve CVs to one of ORIENTATIONS' 6 fixed poses
    (Up/Down/Forward/Backward/Right/Left), relative to the shape's
    original build pose. Undoes the current pose first, then applies the
    target one, via per-CV object-space translation (not ``cmds.rotate``,
    whose component-target flags proved unreliable here)."""
    if not cmds.objExists(control) or orientation_id not in _ORIENTATION_TRANSFORMS:
        return False
    current_id = get_control_orientation(control)
    if current_id == orientation_id:
        return False
    cvs = _shape_cv_selector(_control_shape_nodes(control))
    if not cvs:
        return False
    current = _ORIENTATION_TRANSFORMS[current_id]
    target = _ORIENTATION_TRANSFORMS[orientation_id]
    try:
        for cv in cvs:
            x, y, z = cmds.xform(cv, query=True, translation=True, objectSpace=True)
            if current:
                axis, degrees = current
                x, y, z = _rotate_point(x, y, z, axis, -degrees)
            if target:
                axis, degrees = target
                x, y, z = _rotate_point(x, y, z, axis, degrees)
            cmds.xform(cv, translation=(x, y, z), objectSpace=True)
    except RuntimeError as exc:
        cmds.warning(
            "Temporal Controls Panel: couldn't orient {}: {}".format(control, exc)
        )
        return False
    node = TkmSceneNode(control)
    node.set_attr(ORIENTATION_ATTR, orientation_id)
    return True


def set_control_shape(control, shape_id):
    """Swap control's own curve shape(s) for *shape_id* (see shapes.py), at
    its current accumulated size/orientation (SIZE_MULT_ATTR/
    ORIENTATION_ATTR), preserving whatever override color it already had.
    Only touches control's own shape nodes -- see this section's docstring
    above."""
    if not cmds.objExists(control) or shape_id == get_control_shape_id(control):
        return False

    color = _shape_color(control)
    old_shapes = _control_shape_nodes(control)
    radius = _ensure_control_base_radius(control) * get_control_size_mult(control)

    short_name = control.split("|")[-1].split(":")[-1]
    temp = shapes.build(shape_id, "{}_shapeSwap#".format(short_name), radius)

    try:
        # Apply the control's current pose on top of shapes.build()'s default "up" pose.
        orientation_id = get_control_orientation(control)
        cvs = _shape_cv_selector(
            cmds.listRelatives(temp, shapes=True, fullPath=True) or []
        )
        _apply_orientation_transform(cvs, _ORIENTATION_TRANSFORMS.get(orientation_id))

        for shape_node in cmds.listRelatives(temp, shapes=True, fullPath=True) or []:
            cmds.parent(shape_node, control, shape=True, relative=True)
        cmds.delete(temp)
        if old_shapes:
            existing_old = [node for node in old_shapes if cmds.objExists(node)]
            if existing_old:
                cmds.delete(existing_old)

        _apply_shape_color(_control_shape_nodes(control), color)
        TkmSceneNode(control).set_attr(SHAPE_ATTR, shape_id)
        return True
    finally:
        try:
            if cmds.objExists(temp):
                cmds.delete(temp)
            if cmds.objExists(control):
                cmds.select(control)
        except RuntimeError:
            pass


def _tag_control(control, obj, delete_root):
    """Stamp control's identifying attributes via TkmSceneNode. *obj* may
    be ``None`` (e.g. add_child_control's free control), stored as an
    empty TARGET_ATTR. RESTORE_ATTR/DRIVER_NODES_ATTR aren't set here --
    only once real driving happens, in _create_control_for."""
    target_matches = cmds.ls(obj, long=True) if obj else []
    delete_root_matches = cmds.ls(delete_root, long=True)
    if obj and not target_matches:
        raise RuntimeError("Temporal Controls target no longer exists: {}".format(obj))
    if not delete_root_matches:
        raise RuntimeError(
            "Temporal Controls hierarchy no longer exists: {}".format(delete_root)
        )

    node = TkmSceneNode(control)
    node.set_attr(TAG_ATTR, True, attributeType="bool")
    node.set_attr(TARGET_ATTR, target_matches[0] if target_matches else "")
    node.set_attr(DELETE_ROOT_ATTR, delete_root_matches[0])
    node.set_attr(
        BASE_RADIUS_ATTR, _control_radius(obj) if obj else _control_radius(control)
    )
    for attr in (TAG_ATTR, TARGET_ATTR, DELETE_ROOT_ATTR, BASE_RADIUS_ATTR):
        cmds.setAttr(_plug(control, attr), lock=True)
    # Shape/size/orientation tags start at shapes.DEFAULT_SHAPE and are updated by the panel over the control's life.
    _initialize_control_visual_state(
        control,
        _control_radius(obj) if obj else _control_radius(control),
        shapes.DEFAULT_SHAPE,
    )


def _initialize_control_visual_state(control, base_radius, shape_id):
    """Record the panel-editable appearance of any curve control.

    Secondary system controls intentionally remain outside TAG_ATTR so bake,
    revert, and space-driving discovery keep their existing ownership. Their
    shape, size, and orientation are nevertheless edited by the same panel
    APIs as tagged controls, so those three pieces of state live on both.
    """
    node = TkmSceneNode(control)
    if not cmds.objExists(_plug(control, BASE_RADIUS_ATTR)):
        node.set_attr(BASE_RADIUS_ATTR, base_radius)
    node.set_attr(SHAPE_ATTR, shape_id)
    node.set_attr(SIZE_MULT_ATTR, DEFAULT_SIZE_MULT)
    node.set_attr(ORIENTATION_ATTR, DEFAULT_ORIENTATION)


def _channel_is_keyed(obj, channel):
    """Whether *obj*'s *channel* has any keyframes on it. Uses
    ``cmds.keyframe(keyframeCount=True)`` rather than a direct-connection
    check, since that would miss a channel routed through an intermediate
    node (e.g. unitConversion) before the animCurve."""
    plug = _plug(obj, channel)
    if not cmds.objExists(plug):
        return False
    return bool(cmds.keyframe(plug, query=True, keyframeCount=True))


def _key_times_for(obj, channel):
    """Every keyframe time on *obj*'s *channel*, sorted -- empty if it has
    none. One plug per call (not a batched list) -- matching exactly the
    per-channel-then-union pattern _extract_keys_to_target already uses
    for the same query, the one other place in this tool needs a
    channel's own key times."""
    plug = _plug(obj, channel)
    if not cmds.objExists(plug):
        return []
    return sorted(set(cmds.keyframe(plug, query=True, timeChange=True) or []))


def _key_times_by_channel(obj, channels):
    """Copy/Paste-style per-channel key time payload."""
    return [
        (channel, times)
        for channel in channels
        for times in (_key_times_for(obj, channel),)
        if times
    ]


def _gather_copyable_animation(obj):
    """*obj*'s pre-existing animation, for copying onto a new control.

    Returns ``(translate_key_data, rotate_key_data, extra_attrs)``:
    translate/rotate are ``(channel_name, key_times)`` tuples; extra_attrs
    is ``(attr_name, enum_names_or_None, key_times)`` tuples. Key times are
    kept per channel/attribute, not merged, so copying doesn't stamp keys
    onto frames that were never actually keyed. Scale is out of scope."""
    translate_key_data = _key_times_by_channel(obj, TRANSLATE_CHANNELS)
    rotate_key_data = _key_times_by_channel(obj, ROTATE_CHANNELS)

    extra_attrs = []
    for attr_name in cmds.listAttr(obj, userDefined=True, keyable=True) or []:
        if attr_name in CHANNELS:
            continue
        plug = _plug(obj, attr_name)
        if not cmds.objExists(plug) or cmds.getAttr(plug, lock=True):
            continue
        if not _channel_is_keyed(obj, attr_name):
            continue
        enum_names = None
        if cmds.getAttr(plug, type=True) == "enum":
            try:
                enum_names = cmds.attributeQuery(attr_name, node=obj, listEnum=True)[0]
            except (RuntimeError, ValueError, TypeError, IndexError):
                enum_names = None
        extra_attrs.append((attr_name, enum_names, _key_times_for(obj, attr_name)))

    result = (translate_key_data, rotate_key_data, extra_attrs)
    _debug_log(
        "source animation discovered",
        source=obj,
        translate_keys=translate_key_data,
        rotate_keys=rotate_key_data,
        extra_attributes=extra_attrs,
    )
    return result


def _ensure_matching_attribute(control, obj, attr_name, enum_names):
    """Ensure *control* has an attribute matching obj's *attr_name* (enum
    fields must match) before copying keys across. Returns False, skipping
    the attribute, for types this can't safely recreate (string/message/
    compound)."""
    control_plug = _plug(control, attr_name)
    if cmds.objExists(control_plug):
        return not cmds.getAttr(control_plug, lock=True)

    obj_plug = _plug(obj, attr_name)
    attr_type = cmds.getAttr(obj_plug, type=True)
    try:
        if attr_type == "enum":
            if not enum_names:
                return False
            cmds.addAttr(
                control,
                longName=attr_name,
                attributeType="enum",
                enumName=enum_names,
                keyable=True,
            )
        elif attr_type == "bool":
            cmds.addAttr(
                control, longName=attr_name, attributeType="bool", keyable=True
            )
        elif attr_type in ("long", "short", "byte"):
            cmds.addAttr(
                control, longName=attr_name, attributeType="long", keyable=True
            )
        elif attr_type in ("double", "float", "doubleLinear", "doubleAngle"):
            cmds.addAttr(
                control, longName=attr_name, attributeType=attr_type, keyable=True
            )
        else:
            return False
    except RuntimeError:
        return False

    cmds.setAttr(control_plug, keyable=True)
    return True


def _copy_driven_channel_keys(
    sample_node, control, channel_key_data, cleanup, operation=None
):
    """Copy/Paste-style copy from a temporarily-driven sampling node:
    sample frames/values per channel while the temporary driver is live,
    clean it up, then paste those arrays onto control with explicit
    setKeyframe calls, avoiding writes while the plug is still connected."""
    current_time = cmds.currentTime(query=True)
    sampled = {channel: [] for channel, _times in channel_key_data}
    channels_by_time = {}
    for channel, times in channel_key_data:
        for frame in times:
            channels_by_time.setdefault(frame, []).append(channel)
    try:
        if operation is not None:
            operation.set_status("Copying Source Animation")
        # Evaluate each distinct frame once instead of once per channel, which was expensive for dense controls.
        for frame in sorted(channels_by_time):
            cmds.currentTime(frame, edit=True, update=False)
            for channel in channels_by_time[frame]:
                plug = _plug(sample_node, channel)
                if not cmds.objExists(plug) or cmds.getAttr(plug, lock=True):
                    continue
                try:
                    sampled[channel].append((frame, cmds.getAttr(plug)))
                except RuntimeError:
                    pass
    finally:
        try:
            cmds.currentTime(current_time, edit=True, update=False)
        except RuntimeError:
            pass
        cleanup()

    for channel, frame_values in sampled.items():
        for frame, value in frame_values:
            try:
                cmds.setKeyframe(
                    control,
                    time=(frame,),
                    attribute=channel,
                    value=value,
                    shape=False,
                )
            except RuntimeError:
                pass
            if operation is not None:
                operation.step()


def _copy_source_extra_keys_to_control(control, obj, extra_attrs, operation=None):
    """Copy keyed custom attributes after the shared transform setup path.

    Transform animation is always handled first through world-matrix capture
    and conversion. Custom numeric/enum attributes have no spatial meaning,
    so they retain the established direct-connect/sample/disconnect path and
    their own exact key times. Returns the attributes successfully copied.
    """
    copied_attrs = []

    extra_key_data = []
    extra_connections = []
    for attr_name, enum_names, attr_key_times in extra_attrs:
        if not attr_key_times:
            continue
        if not _ensure_matching_attribute(control, obj, attr_name, enum_names):
            continue
        obj_plug = _plug(obj, attr_name)
        control_plug = _plug(control, attr_name)
        if cmds.getAttr(control_plug, lock=True):
            continue
        try:
            cmds.connectAttr(obj_plug, control_plug, force=True)
        except RuntimeError:
            continue
        extra_key_data.append((attr_name, attr_key_times))
        extra_connections.append((obj_plug, control_plug))
        copied_attrs.append(attr_name)

    if extra_key_data:

        def _disconnect_extra_attrs():
            for source_plug, destination_plug in extra_connections:
                try:
                    if cmds.isConnected(source_plug, destination_plug):
                        cmds.disconnectAttr(source_plug, destination_plug)
                except RuntimeError:
                    pass

        _copy_driven_channel_keys(
            control,
            control,
            extra_key_data,
            _disconnect_extra_attrs,
            operation=operation,
        )

    return copied_attrs


def _capture_channel(control, obj, channel):
    """Free one of *obj*'s channels for the real constraint to drive,
    recording what drove it before so Bake/Revert can restore it.

    Returns ``(channel, restore_payload)``, or ``None`` if left untouched
    (locked, or already driven by something else). Never writes to
    *control*'s own plug -- control and obj live in unrelated local
    spaces, so obj's raw local value isn't meaningful on control."""
    obj_plug = _plug(obj, channel)
    if not cmds.objExists(obj_plug) or cmds.getAttr(obj_plug, lock=True):
        _debug_log(
            "source channel capture skipped",
            plug=obj_plug,
            reason="missing or locked",
        )
        return None

    base_value = cmds.getAttr(obj_plug)
    connections = (
        cmds.listConnections(obj_plug, source=True, destination=False, plugs=True) or []
    )
    source_plug = connections[0] if connections else None

    if source_plug:
        source_node = source_plug.split(".")[0]
        if not cmds.nodeType(source_node).startswith("animCurve"):
            # Already driven by a constraint/expression/other setup -- leave it alone.
            _debug_log(
                "source channel capture skipped",
                plug=obj_plug,
                source_plug=source_plug,
                source_type=cmds.nodeType(source_node),
                reason="source is not a direct animCurve",
            )
            return None
        cmds.disconnectAttr(source_plug, obj_plug)
        _debug_log(
            "source channel captured",
            plug=obj_plug,
            mode="curve",
            source_plug=source_plug,
            base_value=base_value,
        )
        return channel, {
            "mode": "curve",
            "source": source_plug,
            "base_value": base_value,
        }

    if not cmds.getAttr(obj_plug, settable=True):
        _debug_log(
            "source channel capture skipped",
            plug=obj_plug,
            reason="not settable",
        )
        return None

    _debug_log(
        "source channel captured",
        plug=obj_plug,
        mode="value",
        base_value=base_value,
    )
    return channel, {"mode": "value", "value": base_value, "base_value": base_value}


# ----------------------------------------------------------------------
# Position / Orientation space driving
# ----------------------------------------------------------------------


def _active_viewport_camera():
    """Return the transform of the best available model-panel camera."""
    panels = []
    focused = cmds.getPanel(withFocus=True)
    if focused:
        panels.append(focused)
    panels.extend(cmds.getPanel(visiblePanels=True) or [])
    panels.extend(cmds.getPanel(type="modelPanel") or [])

    for panel in dict.fromkeys(panels):
        try:
            if cmds.getPanel(typeOf=panel) != "modelPanel":
                continue
            camera = cmds.modelPanel(panel, query=True, camera=True)
            if not camera or not cmds.objExists(camera):
                continue
            if cmds.nodeType(camera) == "camera":
                parents = cmds.listRelatives(camera, parent=True, fullPath=True) or []
                camera = parents[0] if parents else None
            if camera and cmds.objExists(camera):
                return (cmds.ls(camera, long=True) or [camera])[0]
        except (RuntimeError, TypeError, ValueError):
            continue
    return None


def _stored_space_group(control, attribute):
    stored = TkmSceneNode(control).get_attr(attribute)
    if not stored:
        return None
    matches = cmds.ls(stored, long=True) or []
    if not matches:
        matches = cmds.ls(str(stored).rsplit("|", 1)[-1], long=True) or []
    return matches[0] if len(matches) == 1 else None


def _stored_relative_source(control):
    """Resolve the persistent Relative/Relative reference, if it still exists."""
    return _stored_space_group(control, RELATIVE_SOURCE_ATTR)


def _set_locked_string_attr(node, attribute, value):
    plug = _plug(node, attribute)
    if cmds.objExists(plug):
        cmds.setAttr(plug, lock=False)
    TkmSceneNode(node).set_attr(attribute, value)
    cmds.setAttr(plug, lock=True)


def _ensure_camera_space_hierarchy(control):
    """Insert independent position/orientation anchors above a control."""
    control = (cmds.ls(control, long=False) or [control])[0]
    position_group = _stored_space_group(control, CAMERA_POSITION_GROUP_ATTR)
    orientation_group = _stored_space_group(control, CAMERA_ORIENTATION_GROUP_ATTR)
    if position_group and orientation_group:
        return position_group, orientation_group

    node = TkmSceneNode(control)
    delete_root = node.get_attr(DELETE_ROOT_ATTR) or control
    if not cmds.objExists(delete_root):
        return None, None

    delete_root = (cmds.ls(delete_root, long=True) or [delete_root])[0]
    parent = cmds.listRelatives(delete_root, parent=True, fullPath=True) or []
    position = cmds.xform(delete_root, query=True, worldSpace=True, translation=True)
    rotation = cmds.xform(delete_root, query=True, worldSpace=True, rotation=True)
    short_name = control.rsplit("|", 1)[-1]

    position_group = cmds.createNode(
        "transform", name="{}_cameraPositionSpace#".format(short_name)
    )
    if parent:
        position_group = cmds.parent(position_group, parent[0], absolute=True)[0]
    cmds.xform(position_group, worldSpace=True, translation=position)

    orientation_group = cmds.createNode(
        "transform",
        name="{}_cameraOrientationSpace#".format(short_name),
        parent=position_group,
    )
    cmds.xform(
        orientation_group,
        worldSpace=True,
        translation=position,
        rotation=rotation,
    )
    cmds.parent(delete_root, orientation_group, absolute=True)
    _reset_offset_parent_matrix(delete_root)

    position_group = (cmds.ls(position_group, long=True) or [position_group])[0]
    orientation_group = (cmds.ls(orientation_group, long=True) or [orientation_group])[
        0
    ]
    _set_locked_string_attr(control, CAMERA_POSITION_GROUP_ATTR, position_group)
    _set_locked_string_attr(control, CAMERA_ORIENTATION_GROUP_ATTR, orientation_group)
    _set_locked_string_attr(control, DELETE_ROOT_ATTR, position_group)
    return position_group, orientation_group


def _camera_space_driver(control, group_kind, camera):
    """Build one camera-follow proxy and its position/orientation driver."""
    if not camera or not cmds.objExists(camera):
        raise RuntimeError("Camera Space requires an active viewport camera")
    position_group, orientation_group = _ensure_camera_space_hierarchy(control)
    driven_group = position_group if group_kind == "translate" else orientation_group
    if not driven_group:
        raise RuntimeError("Could not create the Camera Space hierarchy")

    marker = cmds.createNode(
        "transform",
        name="{}_camera{}Proxy#".format(
            str(control).rsplit("|", 1)[-1],
            "Position" if group_kind == "translate" else "Orientation",
        ),
    )
    cmds.matchTransform(
        marker,
        driven_group,
        position=True,
        rotation=True,
        scale=False,
    )
    marker = cmds.parent(marker, camera, absolute=True)[0]
    if cmds.attributeQuery("hiddenInOutliner", node=marker, exists=True):
        cmds.setAttr(_plug(marker, "hiddenInOutliner"), True)

    constrain = (
        cmds.pointConstraint if group_kind == "translate" else cmds.orientConstraint
    )
    constraint = constrain(marker, driven_group, maintainOffset=False)[0]
    control = (cmds.ls(control, long=False) or [control])[0]
    source_attribute = (
        CAMERA_POSITION_SOURCE_ATTR
        if group_kind == "translate"
        else CAMERA_ORIENTATION_SOURCE_ATTR
    )
    TkmSceneNode(control).set_attr(
        source_attribute, (cmds.ls(camera, long=True) or [camera])[0]
    )
    return [constraint, marker]


def _drive_group(
    control,
    obj,
    channels,
    space_mode,
    restore_map,
    locked_report=None,
    space_source=None,
):
    """Wire one channel group (all-translate or all-rotate) from *control*
    to *obj* per *space_mode*, via a real constraint (see
    ``_drive_with_constraint``). Object/World constrain coincident
    (maintainOffset=False); Relative/Grab Release/Child preserve the
    offset (maintainOffset=True). Returns the extra nodes created, for
    Bake/Revert to clean up."""
    if not channels:
        return []

    group_kind = "translate" if channels[0].startswith("translate") else "rotate"

    if space_mode == "camera":
        camera_nodes = _camera_space_driver(control, group_kind, space_source)
        return camera_nodes + _drive_constraint_for_space(
            control, obj, group_kind, space_mode, locked_report=locked_report
        )
    return _drive_constraint_for_space(
        control, obj, group_kind, space_mode, locked_report=locked_report
    )


def _drive_constraint_for_space(
    control, obj, group_kind, space_mode, locked_report=None
):
    """Shared target-constraint half of creation and live space switching."""
    if space_mode not in (
        "relative",
        "grab_release",
        "child",
        "object",
        "world",
        "camera",
    ):
        _debug_log(
            "driver rejected",
            control=control,
            target=obj,
            group=group_kind,
            space=space_mode,
            reason="unknown space",
        )
        raise ValueError("Unknown Temporal Controls space: {}".format(space_mode))
    maintain_offset = space_mode in ("relative", "grab_release", "child")
    _debug_log(
        "driver requested",
        control=control,
        target=obj,
        group=group_kind,
        space=space_mode,
        maintain_offset=maintain_offset,
    )
    nodes = _drive_with_constraint(
        control,
        obj,
        group_kind,
        maintain_offset=maintain_offset,
        locked_report=locked_report,
    )
    _debug_log(
        "driver completed",
        control=control,
        target=obj,
        group=group_kind,
        space=space_mode,
        nodes=nodes,
        success=bool(nodes),
    )
    return nodes


_CONSTRAINT_CHANNELS = {
    "translate": TRANSLATE_CHANNELS,
    "rotate": ROTATE_CHANNELS,
    "scale": SCALE_CHANNELS,
}

_CONSTRAINT_COMMANDS = {
    "translate": cmds.pointConstraint,
    "rotate": cmds.orientConstraint,
    "scale": cmds.scaleConstraint,
}


def _drive_with_constraint(
    control, obj, group_kind, maintain_offset, locked_report=None
):
    """Constrain *obj* to *control* with a real point/orient/scale
    constraint, priming an unkeyed channel first so Maya inserts its usual
    pairBlend (keeps *obj* nudgeable by hand on top of the drive). Falls
    back to a plain constraint if priming fails (e.g. scaleConstraint).
    Locked channels are skipped and appended to *locked_report*.

    Returns the constraint node plus any pairBlend/priming animCurve it
    created, for ``_delete_driver_nodes`` to clean up later."""
    channels = _CONSTRAINT_CHANNELS[group_kind]
    primed_curves = []
    skip_axes = []
    for channel in channels:
        plug = _plug(obj, channel)
        if not cmds.objExists(plug):
            continue
        if cmds.getAttr(plug, lock=True):
            skip_axes.append(channel[-1].lower())
            if locked_report is not None:
                locked_report.append(plug)
            continue
        if not cmds.keyframe(plug, query=True, keyframeCount=True):
            try:
                cmds.setKeyframe(plug, value=cmds.getAttr(plug))
            except RuntimeError:
                continue
            primed_curves += (
                cmds.listConnections(
                    plug, source=True, destination=False, type="animCurve"
                )
                or []
            )

    if len(skip_axes) == len(channels):
        # Every channel in this group is locked, so constraining would be a no-op.
        _debug_log(
            "constraint rejected",
            control=control,
            target=obj,
            group=group_kind,
            reason="all destination axes are locked",
            skip_axes=skip_axes,
        )
        return []

    constrain = _CONSTRAINT_COMMANDS[group_kind]
    constrain_kwargs = {"maintainOffset": maintain_offset}
    if skip_axes:
        constrain_kwargs["skip"] = skip_axes
    try:
        node = constrain(control, obj, **constrain_kwargs)[0]
    except RuntimeError as first_error:
        _debug_log(
            "constraint retrying",
            control=control,
            target=obj,
            group=group_kind,
            reason="primed constraint failed",
            error=first_error,
            primed_curves=primed_curves,
            kwargs=constrain_kwargs,
        )
        for curve in primed_curves:
            if cmds.objExists(curve):
                cmds.delete(curve)
        primed_curves = []
        try:
            node = constrain(control, obj, **constrain_kwargs)[0]
        except RuntimeError as exc:
            _debug_log(
                "constraint failed",
                control=control,
                target=obj,
                group=group_kind,
                kwargs=constrain_kwargs,
                error=exc,
            )
            cmds.warning(
                "Temporal Controls: couldn't drive {} on {}: {}".format(
                    group_kind, obj, exc
                )
            )
            return []

    driver_nodes = [node]
    for curve in primed_curves:
        if curve not in driver_nodes:
            driver_nodes.append(curve)
    for channel in channels:
        plug = _plug(obj, channel)
        if not cmds.objExists(plug):
            continue
        pair_blends = (
            cmds.listConnections(plug, source=True, destination=False, type="pairBlend")
            or []
        )
        for pair_blend in pair_blends:
            if pair_blend not in driver_nodes:
                driver_nodes.append(pair_blend)

    _debug_log(
        "constraint created",
        control=control,
        target=obj,
        group=group_kind,
        maintain_offset=maintain_offset,
        skip_axes=skip_axes,
        primed_curves=primed_curves,
        driver_nodes=driver_nodes,
    )
    return driver_nodes


# ----------------------------------------------------------------------
# Position / Orientation space conversion & live switching
# ----------------------------------------------------------------------


def switch_controls_space(space_id, *_args, tool_operation=None):
    """Re-drive every selected (or targeted) Temporal Control through
    *space_id* for both Position and Orientation, live -- toggles the rig
    off, converts the target's captured world animation into the new
    space, and toggles it back on. Same invariant as the panel's
    independent Position/Orientation switch. Skips nested and muted
    controls."""
    controls = [
        control
        for control in _controls_to_process()
        if _nested_parent_for(control) is None
        and not TkmSceneNode(control).get_attr(MUTED_ATTR)
    ]
    _debug_log(
        "menu space switch requested",
        destination_space=space_id,
        eligible_controls=controls,
    )
    if not controls:
        _debug_log("menu space switch rejected", reason="no eligible controls")
        return wutil.make_inViewMessage("No Temporal Controls to switch")
    camera = _active_viewport_camera() if space_id == "camera" else None
    if space_id == "camera" and not camera:
        _debug_log("menu space switch rejected", reason="no active viewport camera")
        return wutil.make_inViewMessage("Focus or show a viewport to use Camera Space")

    operation = toolCommon.require_tool_operation(tool_operation)
    switches = []
    for control in controls:
        control = (cmds.ls(control, long=False) or [control])[0]
        switch = _ControlSpaceSwitch(
            control,
            ("translate", "rotate"),
            space_id,
            camera,
            operation,
        )
        if switch.valid:
            switches.append(switch)

    if not switches:
        _debug_log("menu space switch rejected", reason="no valid switch operations")
        return wutil.make_inViewMessage("Nothing to switch")
    _configure_space_switch_operation(operation, switches)

    switched = [
        switch.control for switch in switches if switch.run()
    ]

    if switched:
        cmds.select(switched)
        _debug_log(
            "menu space switch completed",
            destination_space=space_id,
            switched_controls=switched,
        )
        return switched
    _debug_log(
        "menu space switch completed",
        destination_space=space_id,
        switched_controls=[],
    )
    return wutil.make_inViewMessage("Nothing to switch")


def switch_controls_to_world_space(*_args, tool_operation=None):
    return switch_controls_space("world", tool_operation=tool_operation)


def switch_controls_to_object_space(*_args, tool_operation=None):
    return switch_controls_space("object", tool_operation=tool_operation)


def switch_controls_to_camera_space(*_args, tool_operation=None):
    return switch_controls_space("camera", tool_operation=tool_operation)


def switch_controls_to_relative_space(*_args, tool_operation=None):
    return switch_controls_space("relative", tool_operation=tool_operation)


def switch_controls_to_child_space(*_args, tool_operation=None):
    return switch_controls_space("child", tool_operation=tool_operation)


def get_control_position_space(control):
    return TkmSceneNode(control).get_attr(POSITION_SPACE_ATTR) or DEFAULT_SPACE


def get_control_orientation_space(control):
    return TkmSceneNode(control).get_attr(ORIENTATION_SPACE_ATTR) or DEFAULT_SPACE


def is_control_space_locked(control):
    return bool(TkmSceneNode(control).get_attr(LOCK_SPACE_ATTR))


def set_control_space_locked(control, locked):
    """Lock/unlock the Temp Controls Panel's Position/Orientation columns
    together. Locking immediately re-drives Orientation to match Position's
    current space (matching the panel's grayed-out Orientation column when
    locked); unlocking just stops future Position changes from cascading."""
    node = TkmSceneNode(control)
    node.set_attr(LOCK_SPACE_ATTR, bool(locked), attributeType="bool")
    if locked:
        set_control_space(control, "rotate", get_control_position_space(control))


def _animation_transform_key_groups(animation):
    """Both transform groups in the shared space-conversion shape.

    Empty key data is intentional: the group still captures and applies its
    current world pose, while ``_TransformSpaceTransfer`` creates no keys for
    it. This keeps keyed and unkeyed creation on exactly the same path.
    """
    translate_key_data, rotate_key_data, _extra_attrs = animation
    return [
        (group_kind, key_data)
        for group_kind, key_data in (
            ("translate", translate_key_data),
            ("rotate", rotate_key_data),
        )
    ]


def _owned_space_sample_times(key_data, group_kind):
    """Owned keys plus current pose when any group channel is unkeyed."""
    key_times = sorted(
        {
            key_time
            for _channel, channel_times in key_data
            for key_time in channel_times
        }
    )
    keyed_channels = {channel for channel, _channel_times in key_data}
    if len(keyed_channels) < len(_CONSTRAINT_CHANNELS[group_kind]):
        key_times.append(cmds.currentTime(query=True))
    return sorted(set(key_times))


def _space_conversion_work(key_data, group_kind):
    """Capture + exact-key/static-channel work units for progress and ETA."""
    channels = _CONSTRAINT_CHANNELS[group_kind]
    keyed_channels = {channel for channel, _times in key_data}
    apply_steps = sum(len(times) for _channel, times in key_data)
    apply_steps += len(channels) - len(keyed_channels)
    return len(_owned_space_sample_times(key_data, group_kind)) + apply_steps


def _set_temporal_key(control, channel, key_time, value):
    """Set and verify one converted key on a deterministic animation layer.

    Maya can silently return zero from an otherwise valid ``setKeyframe``
    when animation layers exist and no destination layer is specified. Match
    the codebase's Copy/Paste behavior by explicitly targeting BaseAnimation
    in that situation, then verify that the key really exists before the
    source animation is disconnected.
    """
    kwargs = {
        "time": (key_time,),
        "attribute": channel,
        "value": value,
        "shape": False,
    }
    has_layers = animation.has_anim_layers()
    root_layer = None
    if has_layers:
        root_layer = animation.root_layer_name()
        if root_layer:
            kwargs["animLayer"] = root_layer
    _debug_log(
        "key write requested",
        control=control,
        channel=channel,
        time=key_time,
        value=value,
        has_animation_layers=has_layers,
        destination_layer=root_layer,
        kwargs=kwargs,
    )
    try:
        result = cmds.setKeyframe(control, **kwargs)
    except (RuntimeError, ValueError, TypeError) as exc:
        _debug_log(
            "key write failed",
            control=control,
            channel=channel,
            time=key_time,
            error=exc,
        )
        cmds.warning(
            "Temporal Controls: could not set {}.{} at {}: {}".format(
                control, channel, key_time, exc
            )
        )
        return False

    plug = _plug(control, channel)
    try:
        key_count = cmds.keyframe(
            plug,
            query=True,
            time=(key_time, key_time),
            keyframeCount=True,
        )
    except (RuntimeError, ValueError, TypeError):
        key_count = 0
    _debug_log(
        "key write verified",
        control=control,
        plug=plug,
        time=key_time,
        set_keyframe_result=result,
        verification_key_count=key_count,
        destination_layer=root_layer,
    )
    if result or key_count:
        return True
    cmds.warning(
        "Temporal Controls: Maya did not create {} at {}".format(plug, key_time)
    )
    return False


def _creation_animation_work(animation):
    """Universal capture-first creation workload for every space mode."""
    _translate, _rotate, extra_attrs = animation
    return sum(
        _space_conversion_work(key_data, group_kind)
        for group_kind, key_data in _animation_transform_key_groups(animation)
    ) + sum(
        len(attr_key_times)
        for _name, _enum, attr_key_times in extra_attrs
    )


class _TransformKeyGroup(object):
    """One translate/rotate group's owned keys and captured world matrices."""

    def __init__(self, kind, key_data):
        self.kind = kind
        self.key_data = list(key_data or [])
        self.sample_times = _owned_space_sample_times(self.key_data, kind)
        self.world_values = {}

    @property
    def work(self):
        return _space_conversion_work(self.key_data, self.kind)

    @property
    def owned_key_times(self):
        return [
            key_time
            for _channel, channel_times in self.key_data
            for key_time in channel_times
        ]


class _TransformSpaceTransfer(object):
    """Capture-first, key-for-key world-space transfer shared by all spaces."""

    def __init__(self, source, groups, operation):
        self.source = source
        self.groups = [
            _TransformKeyGroup(kind, key_data) for kind, key_data in groups
        ]
        self.operation = operation

    @classmethod
    def from_animation(cls, source, animation, operation):
        return cls(source, _animation_transform_key_groups(animation), operation)

    @property
    def work(self):
        return sum(group.work for group in self.groups)

    @property
    def owned_key_times(self):
        return [
            key_time
            for group in self.groups
            for key_time in group.owned_key_times
        ]

    def capture(self):
        """First pipeline stage: read world matrices before scene changes."""
        self.operation.set_status("Capturing Temporal Control World Space")
        for group in self.groups:
            _debug_log(
                "world capture group",
                source=self.source,
                group=group.kind,
                owned_keys=group.key_data,
                sample_times=group.sample_times,
            )
            for key_time in group.sample_times:
                matrix = maya_api.world_matrix_at_time(
                    self.source, key_time
                )
                group.world_values[key_time] = matrix
                _debug_log(
                    "world capture result",
                    source=self.source,
                    group=group.kind,
                    time=key_time,
                    matrix=matrix,
                    success=matrix is not None,
                )
                self.operation.step()
        success = all(
            matrix is not None
            for group in self.groups
            for matrix in group.world_values.values()
        )
        _debug_log("world capture completed", source=self.source, success=success)
        return success

    def apply(self, control):
        """Final pipeline stage: convert captured matrices into destination locals."""
        self.operation.set_status("Converting Temporal Control Space")
        rotate_order = cmds.getAttr(_plug(control, "rotateOrder"))
        _debug_log(
            "space conversion started",
            source=self.source,
            control=control,
            rotate_order=rotate_order,
            groups=[group.kind for group in self.groups],
        )
        for group in self.groups:
            if not self._apply_group(control, group, rotate_order):
                _debug_log(
                    "space conversion failed",
                    source=self.source,
                    control=control,
                    group=group.kind,
                )
                return False
        _debug_log(
            "space conversion completed",
            source=self.source,
            control=control,
            success=True,
        )
        return True

    def _apply_group(self, control, group, rotate_order):
        channels = _CONSTRAINT_CHANNELS[group.kind]
        local_values_by_time = {}
        for key_time in group.sample_times:
            parent_inverse = maya_api.parent_inverse_matrix_at_time(control, key_time)
            local_matrix = maya_api.multiply_matrices(
                group.world_values[key_time], parent_inverse
            )
            local_values = maya_api.decompose_local_matrix(local_matrix, rotate_order)
            _debug_log(
                "local conversion result",
                control=control,
                group=group.kind,
                time=key_time,
                parent_inverse=parent_inverse,
                local_matrix=local_matrix,
                local_values=local_values,
                success=local_values is not None,
            )
            if local_values:
                local_values_by_time[key_time] = dict(
                    zip(channels, local_values[group.kind])
                )

        keyed_times = dict(group.key_data)
        current_time = cmds.currentTime(query=True)
        current_values = local_values_by_time.get(current_time)
        if len(local_values_by_time) != len(group.sample_times):
            _debug_log(
                "local conversion rejected",
                control=control,
                group=group.kind,
                expected_samples=len(group.sample_times),
                converted_samples=len(local_values_by_time),
            )
            return False

        for channel in channels:
            channel_times = keyed_times.get(channel, [])
            if channel_times:
                try:
                    cmds.cutKey(control, attribute=channel, clear=True)
                except RuntimeError:
                    pass
                for key_time in channel_times:
                    if not _set_temporal_key(
                        control,
                        channel,
                        key_time,
                        local_values_by_time[key_time][channel],
                    ):
                        _debug_log(
                            "channel key application rejected",
                            control=control,
                            group=group.kind,
                            channel=channel,
                            time=key_time,
                        )
                        return False
                    self.operation.step()
            elif current_values is not None:
                try:
                    cmds.setAttr(_plug(control, channel), current_values[channel])
                    _debug_log(
                        "static channel applied",
                        control=control,
                        group=group.kind,
                        channel=channel,
                        time=current_time,
                        value=current_values[channel],
                    )
                except RuntimeError as exc:
                    _debug_log(
                        "static channel application failed",
                        control=control,
                        group=group.kind,
                        channel=channel,
                        time=current_time,
                        error=exc,
                    )
                self.operation.step()
        return True


def _configure_space_switch_operation(operation, switches):
    """One tint/progress/ETA setup shared by panel and menu space switches."""
    owned_key_times = [
        key_time
        for switch in switches
        for key_time in switch.transfer.owned_key_times
    ]
    if owned_key_times:
        toolCommon.ensure_operation_tint(
            operation,
            tint="range",
            timerange=(min(owned_key_times), max(owned_key_times)),
            tint_key="temporal_controls_space",
        )
    else:
        toolCommon.ensure_operation_tint(
            operation,
            tint="current",
            default_mode="current_frame",
            tint_key="temporal_controls_space",
        )
    operation.set_total(
        sum(switch.transfer.work for switch in switches),
        reset=True,
    )


def _restore_key_data(restore_map, group_kind):
    """Original per-channel keys held by a Temporal Control restore payload."""
    key_data = []
    for channel in _CONSTRAINT_CHANNELS[group_kind]:
        payload = restore_map.get(channel) or {}
        if payload.get("mode") != "curve":
            continue
        source = payload.get("source")
        source_node = source.split(".")[0] if source else None
        if not source_node or not cmds.objExists(source_node):
            continue
        try:
            times = sorted(
                set(cmds.keyframe(source_node, query=True, timeChange=True) or [])
            )
        except (RuntimeError, ValueError, TypeError):
            times = []
        if times:
            key_data.append((channel, times))
    return key_data


def _stored_camera_source(control, group_kind):
    attribute = (
        CAMERA_POSITION_SOURCE_ATTR
        if group_kind == "translate"
        else CAMERA_ORIENTATION_SOURCE_ATTR
    )
    return _stored_space_group(control, attribute)


class _TemporalControlRigToggle(object):
    """Atomic OFF/ON lifecycle for a driven Temporal Control rig."""

    def __init__(self, control):
        self.control = control
        self.target = _target_for(control)
        self.restore_map = _restore_map_for(control)

    @property
    def valid(self):
        return bool(self.target and self.restore_map)

    def turn_off(self, mark_muted=False):
        """Remove all drivers and reconnect the untouched source animation."""
        if not self.valid:
            return False
        _debug_log(
            "temporal rig turning off",
            control=self.control,
            target=self.target,
            restore_channels=sorted(self.restore_map),
        )
        _delete_driver_nodes(self.control)
        _restore_target_channels(self.target, self.restore_map)
        node = TkmSceneNode(self.control)
        node.set_attr(MUTED_ATTR, bool(mark_muted), attributeType="bool")
        node.set_attr(DRIVER_NODES_ATTR, json.dumps({}))
        _debug_log(
            "temporal rig turned off",
            control=self.control,
            target=self.target,
            muted=bool(mark_muted),
        )
        return True

    def turn_on(self, spaces, camera_nodes=None, cameras=None):
        """Recapture original target channels and reconnect both rig groups."""
        if not self.target or not cmds.objExists(self.target):
            return False
        camera_nodes = camera_nodes or {}
        cameras = cameras or {}
        new_restore_map = {}
        # Scale isn't driven by Temporal Controls; an older restore payload's scale curves stay live once turned on.
        for channel in TRANSLATE_CHANNELS + ROTATE_CHANNELS:
            captured = _capture_channel(self.control, self.target, channel)
            if captured:
                channel_name, payload = captured
                new_restore_map[channel_name] = payload

        node = TkmSceneNode(self.control)
        node.set_attr(RESTORE_ATTR, json.dumps(new_restore_map))
        driver_nodes = {}
        for group_kind, channels in (
            ("translate", TRANSLATE_CHANNELS),
            ("rotate", ROTATE_CHANNELS),
        ):
            driven_channels = [
                channel for channel in channels if channel in new_restore_map
            ]
            if not driven_channels:
                continue
            space_id = spaces[group_kind]
            if group_kind in camera_nodes:
                new_nodes = camera_nodes[group_kind] + _drive_constraint_for_space(
                    self.control, self.target, group_kind, space_id
                )
            else:
                new_nodes = _drive_group(
                    self.control,
                    self.target,
                    driven_channels,
                    space_id,
                    new_restore_map,
                    space_source=cameras.get(group_kind),
                )
            driver_nodes[group_kind] = new_nodes
            node.set_attr(
                POSITION_SPACE_ATTR
                if group_kind == "translate"
                else ORIENTATION_SPACE_ATTR,
                space_id,
            )
        node.set_attr(DRIVER_NODES_ATTR, json.dumps(driver_nodes))
        node.set_attr(MUTED_ATTR, False, attributeType="bool")
        self.restore_map = new_restore_map
        _debug_log(
            "temporal rig turned on",
            control=self.control,
            target=self.target,
            spaces=spaces,
            restore_channels=sorted(new_restore_map),
            driver_nodes=driver_nodes,
        )
        return bool(driver_nodes)


def set_temporal_control_rig_enabled(control, enabled, tool_operation=None):
    """Turn one Temporal Control rig OFF or ON without deleting its control.

    OFF restores the target animation held by the restore payload. ON treats
    the target's currently-live animation as the source, snapshots it at its
    own key times, converts it into the control's current space hierarchy,
    then captures/reconnects the target again.
    """
    if not cmds.objExists(control) or _nested_parent_for(control) is not None:
        return False
    control = (cmds.ls(control, long=False) or [control])[0]
    rig = _TemporalControlRigToggle(control)
    if not enabled:
        return rig.turn_off(mark_muted=True)
    if not TkmSceneNode(control).get_attr(MUTED_ATTR):
        return True
    if not rig.target or not cmds.objExists(rig.target):
        return False

    operation = toolCommon.require_tool_operation(tool_operation)
    source_animation = _gather_copyable_animation(rig.target)
    transfer = _TransformSpaceTransfer.from_animation(
        rig.target, source_animation, operation
    )
    operation.set_total(transfer.work, reset=True)
    if not transfer.capture():
        return False

    spaces = {
        "translate": get_control_position_space(control),
        "rotate": get_control_orientation_space(control),
    }
    cameras = {
        group_kind: _stored_camera_source(control, group_kind)
        for group_kind, space_id in spaces.items()
        if space_id == "camera"
    }
    camera_nodes = {
        group_kind: _camera_space_driver(
            control, group_kind, cameras.get(group_kind)
        )
        for group_kind in cameras
        if cameras.get(group_kind)
    }
    if not transfer.apply(control):
        return False
    return rig.turn_on(
        spaces,
        camera_nodes=camera_nodes,
        cameras=cameras,
    )


def toggle_temporal_control_rigs(*_args, enabled=None, tool_operation=None):
    """Toggle selected Temporal Control rigs, or force all to *enabled*."""
    controls = [
        control
        for control in _controls_to_process()
        if _nested_parent_for(control) is None
    ]
    if not controls:
        return wutil.make_inViewMessage("No Temporal Controls to toggle")
    changed = []
    operation = toolCommon.require_tool_operation(tool_operation)
    for control in controls:
        desired = (
            bool(TkmSceneNode(control).get_attr(MUTED_ATTR))
            if enabled is None
            else bool(enabled)
        )
        if set_temporal_control_rig_enabled(
            control, desired, tool_operation=operation
        ):
            changed.append(control)
    if changed:
        cmds.select(changed)
        return changed
    return wutil.make_inViewMessage("Nothing toggled")


def _resolve_reparented_node(previous_path, hierarchy_root):
    """Resolve *previous_path* below a hierarchy after its DAG path changes."""
    if not previous_path:
        return None
    short_name = str(previous_path).rsplit("|", 1)[-1]
    matches = cmds.ls(short_name, long=True) or []
    hierarchy_root = (cmds.ls(hierarchy_root, long=True) or [hierarchy_root])[0]
    descendants = [
        match
        for match in matches
        if match == hierarchy_root or match.startswith(hierarchy_root + "|")
    ]
    return descendants[0] if len(descendants) == 1 else None


class _ControlSpaceHierarchy(object):
    """Resolve and apply the physical DAG parent for one space transition.

    Only Relative/Relative is a physically-parented mode. Mixed combinations
    use the neutral Temporal Controls hierarchy, matching creation behavior;
    their Position and Orientation differences are represented by their
    independent drivers. Keeping this rule in one object prevents a UI label
    from saying World while the control still inherits its old reference.
    """

    def __init__(self, control, destination_groups, destination_space):
        self.control = control
        self.current_spaces = {
            "translate": get_control_position_space(control),
            "rotate": get_control_orientation_space(control),
        }
        self.destination_spaces = dict(self.current_spaces)
        for group_kind in destination_groups:
            self.destination_spaces[group_kind] = destination_space
        self.relative_source = _stored_relative_source(control)
        self._remember_legacy_relative_source()

    def _delete_root(self):
        return _stored_space_group(self.control, DELETE_ROOT_ATTR) or self.control

    def _remember_legacy_relative_source(self):
        """Recover the reference for controls made before it was persisted."""
        if self.relative_source or set(self.current_spaces.values()) != {"relative"}:
            return
        delete_root = self._delete_root()
        parents = cmds.listRelatives(delete_root, parent=True, fullPath=True) or []
        if not parents or parents[0].rsplit("|", 1)[-1] == ROOT_GROUP:
            return
        self.relative_source = parents[0]
        _set_locked_string_attr(
            self.control, RELATIVE_SOURCE_ATTR, self.relative_source
        )
        _debug_log(
            "legacy relative reference recovered",
            control=self.control,
            relative_source=self.relative_source,
        )

    def _destination_parent(self):
        if (
            self.destination_spaces["translate"] == "relative"
            and self.destination_spaces["rotate"] == "relative"
            and self.relative_source
        ):
            return self.relative_source
        return TkmSceneNode.root().child(
            ROOT_GROUP, icon=icons.temporal_controls
        ).name

    def apply(self):
        delete_root = self._delete_root()
        desired_parent = self._destination_parent()
        current_parent = cmds.listRelatives(
            delete_root, parent=True, fullPath=True
        ) or []
        current_parent = current_parent[0] if current_parent else None
        desired_parent = (cmds.ls(desired_parent, long=True) or [desired_parent])[0]
        _debug_log(
            "space hierarchy decision",
            control=self.control,
            current_spaces=self.current_spaces,
            destination_spaces=self.destination_spaces,
            relative_source=self.relative_source,
            delete_root=delete_root,
            current_parent=current_parent,
            destination_parent=desired_parent,
        )
        if current_parent == desired_parent:
            return self.control

        position_group = _stored_space_group(
            self.control, CAMERA_POSITION_GROUP_ATTR
        )
        orientation_group = _stored_space_group(
            self.control, CAMERA_ORIENTATION_GROUP_ATTR
        )
        control, new_root = _parent_control_system(
            self.control, delete_root, desired_parent
        )
        self.control = control
        _set_locked_string_attr(control, DELETE_ROOT_ATTR, new_root)
        for attribute, previous_path in (
            (CAMERA_POSITION_GROUP_ATTR, position_group),
            (CAMERA_ORIENTATION_GROUP_ATTR, orientation_group),
        ):
            resolved = _resolve_reparented_node(previous_path, new_root)
            if resolved:
                _set_locked_string_attr(control, attribute, resolved)
        _debug_log(
            "space hierarchy moved",
            control=control,
            delete_root=new_root,
            destination_parent=desired_parent,
        )
        return control


class _ControlSpaceSwitch(object):
    """Rig OFF -> original snapshot -> hierarchy -> convert -> rig ON."""

    def __init__(self, control, group_kinds, space_id, camera, operation):
        self.control = control
        self.target = _target_for(control)
        self.space_id = space_id
        self.camera = camera
        self.operation = operation
        self.rig = _TemporalControlRigToggle(control)
        self.hierarchy = _ControlSpaceHierarchy(
            control, group_kinds, space_id
        )
        self.transfer = _TransformSpaceTransfer(
            self.target,
            [
                (
                    group_kind,
                    _restore_key_data(self.rig.restore_map, group_kind),
                )
                for group_kind in ("translate", "rotate")
            ],
            operation,
        )
        _debug_log(
            "space switch prepared",
            control=control,
            target=self.target,
            requested_groups=list(group_kinds),
            original_key_groups=[
                {"kind": group.kind, "key_data": group.key_data}
                for group in self.transfer.groups
            ],
            destination_space=space_id,
            camera=camera,
            valid=self.valid,
        )

    @property
    def valid(self):
        return bool(self.rig.valid and self.transfer.groups)

    def run(self):
        if not self.valid:
            _debug_log(
                "space switch rejected",
                control=self.control,
                reason="missing target or transferable groups",
            )
            return False
        if not self.rig.turn_off(mark_muted=False):
            _debug_log(
                "space switch rejected",
                control=self.control,
                reason="rig could not turn off",
            )
            return False
        if not self.transfer.capture():
            _debug_log(
                "space switch rejected",
                control=self.control,
                reason="original target world capture failed",
            )
            self.rig.turn_on(self.hierarchy.current_spaces)
            return False

        self.control = self.hierarchy.apply()
        self.rig.control = self.control
        destination_spaces = self.hierarchy.destination_spaces
        cameras = {}
        for group_kind, destination in destination_spaces.items():
            if destination != "camera":
                continue
            camera = (
                self.camera
                if self.space_id == "camera"
                else _stored_camera_source(self.control, group_kind)
            )
            if camera:
                cameras[group_kind] = camera
        camera_nodes = {
            group.kind: (
                _camera_space_driver(
                    self.control, group.kind, cameras.get(group.kind)
                )
                if destination_spaces[group.kind] == "camera"
                else []
            )
            for group in self.transfer.groups
        }
        _debug_log(
            "space switch destination hierarchy built",
            control=self.control,
            destination_space=self.space_id,
            camera_nodes=camera_nodes,
        )
        if not self.transfer.apply(self.control):
            _debug_log(
                "space switch rejected",
                control=self.control,
                reason="transform key application failed",
            )
            self.rig.turn_on(
                destination_spaces,
                camera_nodes=camera_nodes,
                cameras=cameras,
            )
            return False

        if not self.rig.turn_on(
            destination_spaces,
            camera_nodes=camera_nodes,
            cameras=cameras,
        ):
            _debug_log(
                "space switch rejected",
                control=self.control,
                reason="rig could not turn on",
            )
            return False
        _debug_log(
            "space switch completed",
            control=self.control,
            target=self.target,
            destination_spaces=destination_spaces,
        )
        return True


def set_control_space(control, group_kind, space_id, tool_operation=None):
    """Re-drive just control's *group_kind* ("translate" or "rotate")
    through *space_id*, leaving the other group alone -- unlike
    switch_controls_space, which always moves both. If Position changes
    and the panel's lock is on, Orientation follows. Skips nested and
    muted controls, same as switch_controls_space. Returns True if
    anything changed."""
    _debug_log(
        "panel space switch requested",
        control=control,
        requested_group=group_kind,
        destination_space=space_id,
    )
    if not cmds.objExists(control):
        _debug_log("panel space switch rejected", control=control, reason="missing control")
        return False
    control = (cmds.ls(control, long=False) or [control])[0]
    if _nested_parent_for(control) is not None or TkmSceneNode(control).get_attr(
        MUTED_ATTR
    ):
        _debug_log(
            "panel space switch rejected",
            control=control,
            reason="nested or muted control",
        )
        return False
    target = _target_for(control)
    if not target:
        _debug_log("panel space switch rejected", control=control, reason="missing target")
        return False
    camera = _active_viewport_camera() if space_id == "camera" else None
    if space_id == "camera" and not camera:
        _debug_log(
            "panel space switch rejected",
            control=control,
            reason="no active viewport camera",
        )
        wutil.make_inViewMessage("Focus or show a viewport to use Camera Space")
        return False

    operation = toolCommon.require_tool_operation(tool_operation)
    node = TkmSceneNode(control)
    group_kinds = [group_kind]
    if group_kind == "translate" and node.get_attr(LOCK_SPACE_ATTR):
        group_kinds.append("rotate")
    _debug_log(
        "panel space groups resolved",
        control=control,
        requested_group=group_kind,
        effective_groups=group_kinds,
        spaces_locked=len(group_kinds) > 1,
    )

    switch = _ControlSpaceSwitch(
        control, group_kinds, space_id, camera, operation
    )
    if not switch.valid:
        return False
    _configure_space_switch_operation(operation, [switch])
    return switch.run()


# ----------------------------------------------------------------------
# Bake / Revert
# ----------------------------------------------------------------------


def bake_control(control):
    """Bake -- and remove -- a single Temporal Control: extract its
    animation onto its target, then delete the control. Returns the
    target baked onto, or ``None`` if there was none. Shared per-control
    step for both ``bake_controls`` and the panel's Remove and Bake.
    Removal always happens, even if baking the target's animation fails
    partway through -- a bake error should never leave a control stuck
    undeletable in the scene."""
    if not cmds.objExists(control):
        return None
    target = _target_for(control)
    restore_map = _restore_map_for(control)
    nested_parent = _nested_parent_for(control)

    # Delete driver nodes before keying target: while still connected, a key would land on the pairBlend's input curve, not target's plug, and get orphaned once it's torn down.
    _delete_driver_nodes(control)

    if target:
        try:
            if nested_parent is not None:
                target = _bake_nested_control(control, target, nested_parent)
            elif get_bake_mode() == "frames":
                _bake_frames_to_target(control, target)
            else:
                _extract_keys_to_target(control, target, restore_map)

            # Runs right after translate/rotate handling; a no-op for controls that were never given extra copied attributes.
            _apply_copied_attrs_to_target(control, target, _copied_attrs_for(control))
        except RuntimeError:
            _debug_log("bake failed, removing control anyway", control=control, target=target)

    _delete_control_nodes(control)
    return target


def bake_controls(*_args, tool_operation=None):
    operation = toolCommon.require_tool_operation(tool_operation)
    controls = _controls_to_process()
    if not controls:
        return wutil.make_inViewMessage("No Temporal Controls to bake")

    start, end = _time_range_for(controls)
    if start is not None:
        toolCommon.ensure_operation_tint(
            operation,
            tint="range",
            timerange=(start, end),
            tint_key="temporal_controls_bake",
        )
    operation.set_total(len(controls)).set_status("Baking Temporal Controls")

    baked_targets = []
    queued = list(controls)
    processed = set()
    while queued:
        control = queued.pop(0)
        if operation.cancelled:
            break
        if not cmds.objExists(control):
            continue
        control_long = cmds.ls(control, long=True)[0]
        if control_long in processed:
            continue
        processed.add(control_long)
        target = bake_control(control)
        if target:
            baked_targets.append(target)
            if cmds.objExists(target) and _is_temporal_control(target):
                target_long = cmds.ls(target, long=True)[0]
                if target_long not in processed:
                    queued.insert(0, target_long)
        operation.step()

    if baked_targets:
        # Re-check existence right before selecting; baking earlier entries in this batch can delete later ones' nodes.
        existing = [node for node in baked_targets if cmds.objExists(node)]
        if existing:
            cmds.select(existing)
        return baked_targets
    return wutil.make_inViewMessage("Nothing baked")


def _camera_space_key_times(control, group_kind):
    space = (
        get_control_position_space(control)
        if group_kind == "translate"
        else get_control_orientation_space(control)
    )
    if space != "camera":
        return []
    source_attribute = (
        CAMERA_POSITION_SOURCE_ATTR
        if group_kind == "translate"
        else CAMERA_ORIENTATION_SOURCE_ATTR
    )
    camera = TkmSceneNode(control).get_attr(source_attribute)
    if not camera:
        return []
    matches = cmds.ls(camera, long=True) or []
    if not matches:
        matches = cmds.ls(str(camera).rsplit("|", 1)[-1], long=True) or []
    camera = matches[0] if len(matches) == 1 else None
    if not camera:
        return []
    try:
        return (
            cmds.keyframe(camera, query=True, timeChange=True, hierarchy="above") or []
        )
    except (RuntimeError, TypeError, ValueError):
        return cmds.keyframe(camera, query=True, timeChange=True) or []


def _control_motion_range(control):
    times = list(cmds.keyframe(control, query=True, timeChange=True) or [])
    times.extend(_camera_space_key_times(control, "translate"))
    times.extend(_camera_space_key_times(control, "rotate"))
    return (min(times), max(times)) if times else (None, None)


def _bakeable_target_channels(control, target, restore_map=None):
    """Driven, unlocked channels that can be baked from *control* to *target*."""
    return [
        channel
        for channel in (restore_map.keys() if restore_map else CHANNELS)
        if cmds.objExists(_plug(control, channel))
        and cmds.objExists(_plug(target, channel))
        and not cmds.getAttr(_plug(target, channel), lock=True)
    ]


def _world_matrix_local_values(source, destination, t, rotate_order):
    """*destination*'s local translate/rotate that reproduce *source*'s
    world matrix at time *t*, via a pure matrix query -- same mechanism
    ``_apply_group`` uses in reverse to put source's animation onto a new
    control at creation. Reads plug values at an explicit time context, no
    ``cmds.currentTime`` scrubbing and no dependency on *destination*'s
    live drive. Returns ``(translate_values, rotate_values)`` dicts keyed
    by channel name, or ``(None, None)`` on failure."""
    world_matrix = maya_api.world_matrix_at_time(source, t)
    parent_inverse = maya_api.parent_inverse_matrix_at_time(destination, t)
    local_matrix = (
        maya_api.multiply_matrices(world_matrix, parent_inverse)
        if world_matrix is not None and parent_inverse is not None
        else None
    )
    local_values = (
        maya_api.decompose_local_matrix(local_matrix, rotate_order)
        if local_matrix is not None
        else None
    )
    if not local_values:
        return None, None
    return (
        dict(zip(TRANSLATE_CHANNELS, local_values["translate"])),
        dict(zip(ROTATE_CHANNELS, local_values["rotate"])),
    )


def _key_target_from_control(control, target, t, channels, rotate_order):
    """Key *target*'s *channels* at time *t* from control's world matrix
    (translate/rotate) or control's own value directly (scale -- never
    matrix-converted, see the tool docstring's "Scale ... always passes
    straight through coincident"). Creates a key regardless of whether
    target already had one there, so an originally-unkeyed target still
    ends up animated. Returns whether anything got keyed."""
    translate_channels = [c for c in TRANSLATE_CHANNELS if c in channels]
    rotate_channels = [c for c in ROTATE_CHANNELS if c in channels]
    scale_channels = [c for c in SCALE_CHANNELS if c in channels]

    keyed = False
    if translate_channels or rotate_channels:
        translate_values, rotate_values = _world_matrix_local_values(
            control, target, t, rotate_order
        )
        if translate_values is None:
            _debug_log(
                "matrix conversion failed", control=control, target=target, time=t
            )
        else:
            for channel in translate_channels:
                keyed = _set_temporal_key(target, channel, t, translate_values[channel]) or keyed
            for channel in rotate_channels:
                keyed = _set_temporal_key(target, channel, t, rotate_values[channel]) or keyed
    for channel in scale_channels:
        keyed = _set_temporal_key(target, channel, t, cmds.getAttr(_plug(control, channel), time=t)) or keyed
    return keyed


def _bake_current_pose_to_target(control, target, restore_map=None):
    """Commit control's current evaluated pose onto target as one key.

    A control with no keys still has a meaningful pose. Explicitly baking
    that one frame before its driver nodes are removed avoids relying on a
    constraint/pairBlend teardown to leave the target at its driven value.
    """
    channels = _bakeable_target_channels(control, target, restore_map)
    if not channels:
        return False
    current = cmds.currentTime(query=True)
    rotate_order = cmds.getAttr(_plug(target, "rotateOrder"))
    return _key_target_from_control(control, target, current, channels, rotate_order)


def _extract_keys_to_target(control, target, restore_map):
    """Key *target* at exactly control's key times (Bake Keys mode), not
    resampled every frame like ``_bake_frames_to_target``. See
    ``_world_matrix_local_values`` for why this reads control's world
    matrix directly instead of sampling target's live-driven value."""
    channels = _bakeable_target_channels(control, target, restore_map)
    if not channels:
        return

    keyed_channels = [
        channel
        for channel in channels
        if cmds.keyframe(_plug(control, channel), query=True, keyframeCount=True)
    ]
    camera_key_times = {
        "translate": _camera_space_key_times(control, "translate"),
        "rotate": _camera_space_key_times(control, "rotate"),
    }
    camera_channels = []
    if camera_key_times["translate"]:
        camera_channels.extend(
            channel for channel in channels if channel in TRANSLATE_CHANNELS
        )
    if camera_key_times["rotate"]:
        camera_channels.extend(
            channel for channel in channels if channel in ROTATE_CHANNELS
        )
    bake_channels = list(dict.fromkeys(keyed_channels + camera_channels))
    if not bake_channels:
        # Control has no keys of its own -- still commit its current pose.
        _bake_current_pose_to_target(control, target, restore_map)
        return

    key_times = set()
    for channel in keyed_channels:
        key_times.update(
            cmds.keyframe(_plug(control, channel), query=True, timeChange=True) or []
        )
    key_times.update(camera_key_times["translate"])
    key_times.update(camera_key_times["rotate"])
    if not key_times:
        return

    rotate_order = cmds.getAttr(_plug(target, "rotateOrder"))
    for t in sorted(key_times):
        _key_target_from_control(control, target, t, bake_channels, rotate_order)


def _apply_copied_attrs_to_target(control, target, copied_attrs):
    """Reapply control's copy of *copied_attrs* (custom attributes, see
    _copy_source_extra_keys_to_control) back onto target at Bake time. A
    plain value copy at control's key times, unlike translate/rotate --
    these were never live-driven, and a custom attribute's value isn't
    parent-space-relative, so there's no space mismatch to sidestep."""
    for attr_name in copied_attrs:
        control_plug = _plug(control, attr_name)
        target_plug = _plug(target, attr_name)
        if not cmds.objExists(control_plug) or not cmds.objExists(target_plug):
            continue
        if cmds.getAttr(target_plug, lock=True):
            continue
        times = sorted(
            set(cmds.keyframe(control_plug, query=True, timeChange=True) or [])
        )
        if not times:
            if cmds.getAttr(target_plug, settable=True):
                cmds.setAttr(target_plug, cmds.getAttr(control_plug))
            continue
        for t in times:
            try:
                cmds.setKeyframe(
                    target_plug, time=(t, t), value=cmds.getAttr(control_plug, time=t)
                )
            except RuntimeError:
                pass


def _bake_range_to_target(target, channels, start, end):
    """``cmds.bakeResults`` over a continuous range -- used only by
    ``_bake_nested_control``, onto a temporary node driven by a plain,
    unprimed constraint (no pairBlend, so bakeResults is safe there; the
    normal constraint+pairBlend drive isn't -- see ``_world_matrix_local_values``).
    Respects Super Mode. Returns whether it happened; a failure is
    surfaced via cmds.warning, not swallowed."""
    _debug_log(
        "bake range requested",
        target=target,
        channels=list(channels),
        start=start,
        end=end,
        simulation=_super_mode_simulation_flag(),
    )
    try:
        cmds.bakeResults(
            target,
            simulation=_super_mode_simulation_flag(),
            time=(start, end),
            attribute=list(channels),
            preserveOutsideKeys=True,
            disableImplicitControl=True,
        )
        return True
    except RuntimeError as exc:
        cmds.warning("Temporal Controls: bake onto {} failed: {}".format(target, exc))
        _debug_log("bake range failed", target=target, channels=list(channels), error=str(exc))
        return False


def _bake_frames_to_target(control, target):
    """Bake Frames mode (see get_bake_mode): resample control's motion onto
    target every frame across its full animated range, instead of copying
    control's existing keyframes as-is like _extract_keys_to_target (Bake
    Keys mode) does. Same per-frame matrix conversion as Bake Keys, just
    called once per frame instead of once per control key time."""
    if not cmds.objExists(target):
        return
    start, end = _control_motion_range(control)
    if start is None:
        start = end = cmds.currentTime(query=True)
    rotate_order = cmds.getAttr(_plug(target, "rotateOrder"))
    frame = start
    while frame <= end + 1e-6:
        _key_target_from_control(control, target, frame, CHANNELS, rotate_order)
        frame += 1.0


def _bake_nested_control(control, obj, original_parent):
    """Bake a wrapper's world motion onto the complete nested System root.

    Baking ``nested_root`` while it is still parented below ``control`` only
    records its local values and therefore misses the wrapper's animation.
    Capture its evaluated world transform on a temporary transform living in
    the original parent space, restore the complete hierarchy, then bake that
    captured motion onto the restored root.
    """
    if not cmds.objExists(obj):
        return obj
    nested_root = _nested_root_for(control, obj)
    if not nested_root or not cmds.objExists(nested_root):
        return obj
    hierarchy = [nested_root]
    hierarchy.extend(
        cmds.listRelatives(
            nested_root, allDescendents=True, type="transform", fullPath=True
        )
        or []
    )
    start, end = _time_range_for([control] + hierarchy)
    if start is None:
        current = cmds.currentTime(query=True)
        start = end = current

    capture = cmds.createNode("transform", name="TKM_nestedBakeCapture#")
    if original_parent and cmds.objExists(original_parent):
        parented = cmds.parent(capture, original_parent) or []
        if parented:
            capture = parented[0]
    capture_matches = cmds.ls(capture, long=True) or [capture]
    capture = capture_matches[0]

    try:
        capture_constraints = _constrain_nested_bake_transform(nested_root, capture)
        _bake_range_to_target(capture, CHANNELS, start, end)
        if capture_constraints:
            cmds.delete(capture_constraints)

        obj = _restore_nested_parent(control, obj, original_parent)
        nested_root = _nested_root_for(control, obj)
        if not nested_root or not cmds.objExists(nested_root):
            return obj

        apply_constraints = _constrain_nested_bake_transform(capture, nested_root)
        _bake_range_to_target(nested_root, CHANNELS, start, end)
        if apply_constraints:
            cmds.delete(apply_constraints)
        return obj
    finally:
        if cmds.objExists(capture):
            cmds.delete(capture)


def _constrain_nested_bake_transform(source, target):
    """Constrain all transform groups used by nested world-space baking."""
    nodes = []
    nodes.extend(cmds.parentConstraint(source, target, maintainOffset=False) or [])
    try:
        nodes.extend(cmds.scaleConstraint(source, target, maintainOffset=False) or [])
    except RuntimeError:
        # Translate/rotate are the supported channels; scale stays best-effort.
        pass
    return nodes


def revert_control(control):
    """Revert -- and remove -- a single Temporal Control: restore its
    target's original channels (or, for a nested control, hand the target
    back to its original parent), then delete the control. Returns the
    target restored, or ``None`` if *control* had no target (a free "Add
    Child" extra control just gets removed). The single-control counterpart
    to bake_control -- see its docstring, including why removal always
    happens even if the restore step fails partway through."""
    if not cmds.objExists(control):
        return None
    target = _target_for(control)
    restore_map = _restore_map_for(control)
    nested_parent = _nested_parent_for(control)
    _delete_driver_nodes(control)

    if target:
        # Reparent obj out before deleting control, or it would get deleted along with it.
        try:
            if nested_parent is not None:
                target = _restore_nested_parent(control, target, nested_parent)
            else:
                _restore_target_channels(target, restore_map)
        except RuntimeError:
            _debug_log("revert failed, removing control anyway", control=control, target=target)

    _delete_control_nodes(control)
    return target


def revert_controls(*_args, tool_operation=None):
    operation = toolCommon.require_tool_operation(tool_operation)
    controls = _controls_to_process()
    if not controls:
        return wutil.make_inViewMessage("No Temporal Controls to revert")

    start, end = _time_range_for(controls)
    if start is not None:
        toolCommon.ensure_operation_tint(
            operation,
            tint="range",
            timerange=(start, end),
            tint_key="temporal_controls_revert",
        )
    operation.set_total(len(controls)).set_status("Reverting Temporal Controls")

    reverted_targets = []
    queued = list(controls)
    processed = set()
    while queued:
        control = queued.pop(0)
        if operation.cancelled:
            break
        if not cmds.objExists(control):
            continue
        control_long = cmds.ls(control, long=True)[0]
        if control_long in processed:
            continue
        processed.add(control_long)
        target = revert_control(control)
        if target:
            reverted_targets.append(target)
            if cmds.objExists(target) and _is_temporal_control(target):
                target_long = cmds.ls(target, long=True)[0]
                if target_long not in processed:
                    queued.insert(0, target_long)
        operation.step()

    if reverted_targets:
        # Re-check existence right before selecting, same as bake_controls.
        existing = [node for node in reverted_targets if cmds.objExists(node)]
        if existing:
            cmds.select(existing)
        return reverted_targets
    return wutil.make_inViewMessage("Nothing reverted")


def _restore_target_channels(target, restore_map):
    """Put *target*'s channels back to whatever ``restore_map`` (see
    ``_capture_channel``) says they were connected to or set to before a
    control took them over. Shared by ``revert_controls`` and
    ``mute_and_revert`` -- the only difference between full Revert and Mute
    Revert is whether the control itself gets deleted afterward."""
    for channel, payload in restore_map.items():
        obj_plug = _plug(target, channel)
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


def mute_and_revert(*_args):
    """Mute Revert: same teardown as Revert, but leaves the control node in
    the scene so it can drive the target again later. Skips nested
    controls, which were never driven through a constraint."""
    controls = [
        control
        for control in _controls_to_process()
        if _nested_parent_for(control) is None
    ]
    if not controls:
        return wutil.make_inViewMessage("No Temporal Controls to mute")

    muted = []
    for control in controls:
        if _TemporalControlRigToggle(control).turn_off(mark_muted=True):
            muted.append(control)

    cmds.select(muted)
    return muted


def mute_and_bake(*_args):
    """Mute Bake: disconnect selected Temporal Controls the same way Mute
    Revert does, but first explicitly bakes the target's current evaluated
    pose. This works even when the control has no animation keys and avoids
    relying on constraint/pairBlend deletion to freeze the driven result.
    The control stays in the scene, ready to drive again later."""
    controls = [
        control
        for control in _controls_to_process()
        if _nested_parent_for(control) is None
    ]
    if not controls:
        return wutil.make_inViewMessage("No Temporal Controls to mute")

    muted = []
    for control in controls:
        target = _target_for(control)
        # Delete driver nodes before baking, not after -- same ordering as bake_control.
        _delete_driver_nodes(control)
        if target:
            _bake_current_pose_to_target(
                control, target, _restore_map_for(control)
            )
        node = TkmSceneNode(control)
        node.set_attr(MUTED_ATTR, True, attributeType="bool")
        node.set_attr(DRIVER_NODES_ATTR, json.dumps({}))
        muted.append(control)

    cmds.select(muted)
    return muted


# ----------------------------------------------------------------------
# Temp Controls Panel: rig list, add/remove control, pivot
# ----------------------------------------------------------------------
# A rig is one target plus every Temporal Control tracing back to it; the panel lists one row per rig.


def list_rigs():
    """Every rig currently in the scene, as ``{root_target: [control, ...]}``
    -- see this section's docstring above. Controls whose root can't be
    resolved (nothing left to trace back to -- e.g. a stale node from a
    scene edited outside this tool) are skipped."""
    rigs = {}
    for control in cmds.ls("*." + TAG_ATTR, objectsOnly=True) or []:
        root_target = root_target_for(control)
        if root_target:
            rigs.setdefault(root_target, []).append(control)
    return rigs


def list_panel_rigs():
    """Rig rows with every visible curve control, including untagged
    secondary ones (e.g. Aim's target sphere) that ``list_rigs`` omits
    since bake/revert/space switching only operate on tagged controls."""
    rigs = list_rigs()
    panel_rigs = {}
    for root_target, tagged_controls in rigs.items():
        controls = list(tagged_controls)
        seen = set()
        for control in controls:
            matches = cmds.ls(control, long=True) or [control]
            seen.add(matches[0])

        for control in tagged_controls:
            delete_root = TkmSceneNode(control).get_attr(DELETE_ROOT_ATTR) or control
            if not cmds.objExists(delete_root):
                continue
            candidates = [delete_root]
            candidates.extend(
                cmds.listRelatives(
                    delete_root,
                    allDescendents=True,
                    type="transform",
                    fullPath=True,
                )
                or []
            )
            for candidate in candidates:
                matches = cmds.ls(candidate, long=True) or [candidate]
                candidate = matches[0]
                if candidate in seen:
                    continue
                shape_nodes = _control_shape_nodes(candidate)
                if not any(
                    cmds.nodeType(shape_node) == "nurbsCurve"
                    for shape_node in shape_nodes
                ):
                    continue
                seen.add(candidate)
                controls.append(candidate)

        panel_rigs[root_target] = controls
    return panel_rigs


def root_target_for(control):
    """Walk *control*'s target chain up to the real scene object it
    ultimately traces back to -- following nested-parent/Add-Parent links
    (control -> control -> ... -> object) until reaching a target that
    isn't itself a Temporal Control. A control with no target of its own
    (an "Add Child" extra -- see add_child_control) falls back to its Maya
    parent chain instead, since that's the only relationship it has."""
    seen = set()
    current = control
    while current and current not in seen and cmds.objExists(current):
        seen.add(current)
        target = TkmSceneNode(current).get_attr(TARGET_ATTR)
        if target and cmds.objExists(target):
            if _is_temporal_control(target):
                current = target
                continue
            return target
        parent = cmds.listRelatives(current, parent=True, fullPath=True)
        current = parent[0] if parent else None
    return None


def add_parent_control(control):
    """Add a new Temporal Control that becomes *control*'s real Maya
    parent, via the normal nested-control creation path. Flagged
    EXTRA_ATTR so Remove Control can delete it later, and inherits
    control's color. The mirror of add_child_control below."""
    if not cmds.objExists(control):
        return None
    new_controls = create_controls_with_options(
        [control], color=get_control_color(control)
    )
    if not new_controls:
        return None
    parent_control = new_controls[0]
    node = TkmSceneNode(parent_control)
    node.set_attr(EXTRA_ATTR, True, attributeType="bool")
    cmds.setAttr(_plug(parent_control, EXTRA_ATTR), lock=True)
    cmds.select(parent_control)
    return parent_control


def add_child_control(parent_control):
    """Add a new Temporal Control as a real Maya child of *parent_control*
    -- the mirror of add_parent_control. Free-standing (TARGET_ATTR left
    empty), flagged EXTRA_ATTR, and inherits parent_control's color."""
    if not cmds.objExists(parent_control):
        return None
    radius = max(
        _control_base_radius(parent_control)
        * get_control_size_mult(parent_control)
        * 0.6,
        0.5,
    )
    short_name = parent_control.split("|")[-1].split(":")[-1]
    child_control = shapes.build(
        shapes.DEFAULT_SHAPE, "{}_temporalChild#".format(short_name), radius
    )
    cmds.matchTransform(
        child_control, parent_control, position=True, rotation=True, scale=False
    )
    cmds.parent(child_control, parent_control)

    _tag_control(child_control, None, child_control)
    node = TkmSceneNode(child_control)
    node.set_attr(EXTRA_ATTR, True, attributeType="bool")
    cmds.setAttr(_plug(child_control, EXTRA_ATTR), lock=True)

    color = get_control_color(parent_control)
    if color:
        _apply_control_color(child_control, color)

    cmds.select(child_control)
    # Not routed through create_controls_with_options, so fire controlsCreated here too for other listeners.
    controls_bus.controlsCreated.emit()
    return child_control


def remove_extra_control(control):
    """Remove a control the panel itself added on top of a System's main
    control (Add Child/Add Parent, EXTRA_ATTR) -- an "extra" control, not a
    System's main control, which Remove and Bake/Revert exist for instead
    and which this refuses to touch."""
    if not cmds.objExists(control) or not _is_temporal_control(control):
        return wutil.make_inViewMessage("Not a Temporal Control")
    if not TkmSceneNode(control).get_attr(EXTRA_ATTR):
        return wutil.make_inViewMessage(
            "Can't remove a System's main control here -- use Remove and Bake/Revert"
        )

    target = _target_for(control)
    nested_parent = _nested_parent_for(control)
    _delete_driver_nodes(control)
    if target and nested_parent is not None:
        _restore_nested_parent(control, target, nested_parent)

    # Release anything stacked on top of this control to world before deleting it.
    for child in (
        cmds.listRelatives(control, children=True, type="transform", fullPath=True)
        or []
    ):
        if cmds.objExists(child) and _is_temporal_control(child):
            cmds.parent(child, world=True)

    _delete_control_nodes(control)
    return True


def edit_pivot(control):
    """Enter Maya's interactive pivot-edit mode (the Move tool's Insert-key
    mode) on *control* -- lets the user drag its rotate/scale pivot by
    hand, same as picking it from the viewport and pressing Insert."""
    if not cmds.objExists(control):
        return False
    cmds.select(control)
    cmds.setToolTo("moveSuperContext")
    cmds.manipMoveContext("Move", edit=True, editPivotMode=True)
    return True


def reset_pivot(control):
    """Reset control's rotate/scale pivot back to its own object-space
    origin."""
    if not cmds.objExists(control):
        return False
    cmds.xform(control, pivots=(0, 0, 0), objectSpace=True)
    return True


_temp_controls_panel = None


def open_temp_controls_panel(*_args):
    """Open (or re-focus) the Temp Controls Panel -- see panel.py for the
    window itself. Reuses the same single-instance-plus-destroyed-signal
    pattern _open_creation_dialog uses for the creation dialog."""
    global _temp_controls_panel
    from TheKeyMachine.tools.temporal_controls.panel import TempControlsPanelWindow

    if _temp_controls_panel is not None and wutil.is_valid_widget(_temp_controls_panel):
        _temp_controls_panel.refresh()
        _temp_controls_panel.place_near_cursor()
        _temp_controls_panel.raise_()
        _temp_controls_panel.activateWindow()
        return _temp_controls_panel

    parent = wutil.get_maya_qt(qt=QtWidgets.QWidget)
    panel = TempControlsPanelWindow(parent=parent)

    def _clear_reference(*_args):
        global _temp_controls_panel
        _temp_controls_panel = None

    panel.destroyed.connect(_clear_reference)
    panel.place_near_cursor()
    panel.activateWindow()
    _temp_controls_panel = panel
    return panel


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
    """Every Temporal Control relevant to the current selection: one whose
    control or target is selected (either end works for Bake/Revert), plus
    any parent Temporal Controls driving it, recursively. A selected
    secondary curve resolves to its System's tagged control. Falls back to
    every control in the scene only when nothing at all is selected --
    an unrelated selection means nothing relevant, not everything."""
    all_controls = cmds.ls("*." + TAG_ATTR, objectsOnly=True) or []
    if not all_controls:
        return []
    all_controls = [
        cmds.ls(control, long=True)[0]
        for control in all_controls
        if cmds.objExists(control) and cmds.ls(control, long=True)
    ]

    selected = selection.get_selected_objects(long=True)
    if not selected:
        return _dependency_ordered_controls(all_controls, all_controls)

    selected = set(selected)
    picked = []
    picked_set = set()
    for control in all_controls:
        if control in selected:
            picked.append(control)
            picked_set.add(control)
            continue
        # _target_for already returns a full path, so no need to re-normalize it.
        target = _target_for(control)
        if target and target in selected:
            picked.append(control)
            picked_set.add(control)
            continue

        # Secondary controls don't carry TAG_ATTR; treat a selected descendant as selecting its tagged owner via DELETE_ROOT_ATTR.
        delete_root = TkmSceneNode(control).get_attr(DELETE_ROOT_ATTR) or control
        delete_root_matches = cmds.ls(delete_root, long=True) or []
        if not delete_root_matches:
            continue
        hierarchy = {delete_root_matches[0]}
        hierarchy.update(
            cmds.listRelatives(
                delete_root_matches[0],
                allDescendents=True,
                type="transform",
                fullPath=True,
            )
            or []
        )
        if selected.intersection(hierarchy):
            picked.append(control)
            picked_set.add(control)

    # Include controls driving the picked ones (Add Parent/nested stacks), repeated until stable for grandparent chains.
    changed = True
    while changed:
        changed = False
        for control in all_controls:
            if control in picked_set:
                continue
            target = _target_for(control)
            if target and target in picked_set:
                picked.append(control)
                picked_set.add(control)
                changed = True

    return _dependency_ordered_controls(all_controls, picked)


def _dependency_ordered_controls(all_controls, controls):
    """Order controls so parent/nested controls are processed before the
    controls they target. Deleting a direct child first can invalidate its
    parent control's target, so batch Bake/Revert/Mute all use this."""
    wanted = set(controls or [])
    if not wanted:
        return []

    parents_by_target = {}
    for control in all_controls:
        if control not in wanted:
            continue
        target = _target_for(control)
        if target in wanted:
            parents_by_target.setdefault(target, []).append(control)

    ordered = []
    visiting = set()
    visited = set()

    def visit(control):
        if control in visited or control in visiting:
            return
        visiting.add(control)
        for parent_control in parents_by_target.get(control, []):
            visit(parent_control)
        visiting.remove(control)
        visited.add(control)
        if control in wanted and cmds.objExists(control):
            ordered.append(control)

    for control in all_controls:
        if control in wanted:
            visit(control)
    return ordered


def _target_for(control):
    target = TkmSceneNode(control).get_attr(TARGET_ATTR)
    return target if target and cmds.objExists(target) else None


def _is_temporal_control(node):
    return TkmSceneNode(node).get_attr(TAG_ATTR) is not None


def _parent_nested_control(control, obj):
    """Wrap *obj*'s complete Temporal System without dismantling it.

    Group and Aim controls own a buffer plus secondary nodes. Reparenting
    only the selected main curve separates those nodes and breaks the
    System's constraint relationships, so the stored DELETE_ROOT hierarchy
    is moved as one unit. The returned value is *obj*'s new full DAG path.
    """
    obj_matches = cmds.ls(obj, long=True) or []
    if not obj_matches:
        raise RuntimeError("Temporal Controls target no longer exists: {}".format(obj))
    obj = obj_matches[0]

    stored_root = TkmSceneNode(obj).get_attr(DELETE_ROOT_ATTR)
    root_matches = cmds.ls(stored_root, long=True) if stored_root else []
    nested_root = root_matches[0] if root_matches else obj
    if obj != nested_root and not obj.startswith(nested_root + "|"):
        nested_root = obj
    target_suffix = obj[len(nested_root) :]

    original_parent = cmds.listRelatives(nested_root, parent=True, fullPath=True) or []
    node = TkmSceneNode(control)
    node.set_attr(NESTED_PARENT_ATTR, original_parent[0] if original_parent else "")
    cmds.setAttr(_plug(control, NESTED_PARENT_ATTR), lock=True)

    old_root = nested_root
    parented = cmds.parent(nested_root, control) or []
    if not parented:
        raise RuntimeError(
            "Temporal Controls could not parent {} under {}".format(
                nested_root, control
            )
        )
    matches = cmds.ls(parented[0], long=True) or []
    if not matches:
        raise RuntimeError(
            "Temporal Controls could not resolve {} after parenting".format(nested_root)
        )
    nested_root = matches[0]
    _reset_offset_parent_matrix(nested_root)
    _remap_temporal_dag_paths(old_root, nested_root)

    node.set_attr(NESTED_ROOT_ATTR, nested_root)
    cmds.setAttr(_plug(control, NESTED_ROOT_ATTR), lock=True)
    target_matches = cmds.ls(nested_root + target_suffix, long=True) or []
    if not target_matches:
        raise RuntimeError(
            "Temporal Controls could not resolve {} after parenting".format(obj)
        )
    return target_matches[0]


def _nested_parent_for(control):
    """The parent *control*'s target should return to on Bake/Revert, or
    ``None`` if *control* isn't a nested-control parent -- i.e. it was
    built through the normal channel-driving path in
    ``_create_control_for`` rather than ``_parent_nested_control``.
    ``TkmSceneNode.get_attr``'s ``None`` default already draws exactly that
    line: unset means "not nested", while "" (a control that was at world)
    is a legitimate, distinct answer."""
    return TkmSceneNode(control).get_attr(NESTED_PARENT_ATTR)


def _nested_root_for(control, obj=None):
    stored = TkmSceneNode(control).get_attr(NESTED_ROOT_ATTR)
    matches = cmds.ls(stored, long=True) if stored else []
    if matches:
        return matches[0]
    matches = cmds.ls(obj, long=True) if obj else []
    return matches[0] if matches else None


def _remap_temporal_dag_paths(old_root, new_root):
    """Update absolute path metadata after moving a Temporal hierarchy."""
    if not old_root or old_root == new_root:
        return
    path_attrs = (
        TARGET_ATTR,
        DELETE_ROOT_ATTR,
        CAMERA_POSITION_GROUP_ATTR,
        CAMERA_ORIENTATION_GROUP_ATTR,
        CAMERA_POSITION_SOURCE_ATTR,
        CAMERA_ORIENTATION_SOURCE_ATTR,
        NESTED_PARENT_ATTR,
        NESTED_ROOT_ATTR,
    )
    for control in cmds.ls("*." + TAG_ATTR, objectsOnly=True, long=True) or []:
        node = TkmSceneNode(control)
        for attr in path_attrs:
            plug = _plug(control, attr)
            if not cmds.objExists(plug):
                continue
            value = node.get_attr(attr)
            if not isinstance(value, str):
                continue
            if value == old_root:
                remapped = new_root
            elif value.startswith(old_root + "|"):
                remapped = new_root + value[len(old_root) :]
            else:
                continue
            locked = bool(cmds.getAttr(plug, lock=True))
            if locked:
                cmds.setAttr(plug, lock=False)
            node.set_attr(attr, remapped)
            if locked:
                cmds.setAttr(plug, lock=True)


def _restore_nested_parent(control, obj, original_parent):
    """Hand a nested control's target back to its original parent.

    ``cmds.parent(..., absolute=True)`` (the implicit mode here) can write
    a compensating ``offsetParentMatrix`` onto a node whose translate/
    rotate are keyed, to keep its world position unchanged across the
    reparent -- see ``_reset_offset_parent_matrix``. Left in place, that
    silently corrupts anything read via parentInverseMatrix afterward
    (Bake's constrain-and-sample step, or just Revert leaving the object
    visibly offset), so it's cleared right after every reparent here.
    """
    nested_root = _nested_root_for(control, obj)
    obj_matches = cmds.ls(obj, long=True) if obj else []
    if not nested_root or not obj_matches:
        return obj
    obj = obj_matches[0]
    if obj != nested_root and not obj.startswith(nested_root + "|"):
        return obj
    target_suffix = obj[len(nested_root) :]
    old_root = nested_root

    if original_parent and cmds.objExists(original_parent):
        parented = cmds.parent(nested_root, original_parent) or []
    elif cmds.listRelatives(nested_root, parent=True, fullPath=True):
        parented = cmds.parent(nested_root, world=True) or []
    else:
        parented = [nested_root]
    matches = cmds.ls(parented[0], long=True) if parented else []
    if not matches:
        return obj
    nested_root = matches[0]
    _reset_offset_parent_matrix(nested_root)
    _remap_temporal_dag_paths(old_root, nested_root)
    target_matches = cmds.ls(nested_root + target_suffix, long=True) or []
    return target_matches[0] if target_matches else obj


def _existing_control_for(obj):
    long_obj = cmds.ls(obj, long=True)[0]
    for control in cmds.ls("*." + TAG_ATTR, objectsOnly=True) or []:
        # target is already a full path; see the matching note in _controls_to_process.
        if _target_for(control) == long_obj:
            return control
    return None


def _restore_map_for(control):
    raw = TkmSceneNode(control).get_attr(RESTORE_ATTR)
    if not raw:
        return {}
    try:
        return json.loads(raw)
    except (TypeError, ValueError):
        return {}


def _copied_attrs_for(control):
    """COPIED_ATTRS_ATTR as a plain list -- see its own declaration above
    and _gather_copyable_animation/_copy_source_extra_keys_to_control, which
    write it. Empty for any control that was never given a copy of an
    already-animated obj's extra attributes (including every control
    built before this existed)."""
    raw = TkmSceneNode(control).get_attr(COPIED_ATTRS_ATTR)
    if not raw:
        return []
    try:
        data = json.loads(raw)
    except (TypeError, ValueError):
        return []
    return data if isinstance(data, list) else []


def _driver_nodes_map_for(control):
    """Return the current per-channel-group driver-node mapping."""
    raw = TkmSceneNode(control).get_attr(DRIVER_NODES_ATTR)
    if not raw:
        return {}
    try:
        data = json.loads(raw)
    except (TypeError, ValueError):
        return {}
    if not isinstance(data, dict):
        return {}
    return {
        group: [node for node in (nodes or []) if node and cmds.objExists(node)]
        for group, nodes in data.items()
    }


def _driver_nodes_for(control):
    nodes = []
    for group_nodes in _driver_nodes_map_for(control).values():
        for node in group_nodes:
            if node not in nodes:
                nodes.append(node)
    return nodes


def _delete_driver_nodes(control):
    """Delete every constraint/pairBlend/expression node this control's
    driving mechanism created on or around the *target* object. These live
    outside the control's own hierarchy, so Bake/Revert must clean them up
    explicitly before deleting the control itself."""
    nodes = _driver_nodes_for(control)
    if nodes:
        cmds.delete(nodes)


def _delete_control_nodes(control):
    """Delete the control (and, for Group/Aim Systems, its offset buffer --
    deleting the buffer cascades to the control and any secondary control it parents).
    """
    stored = TkmSceneNode(control).get_attr(DELETE_ROOT_ATTR)
    delete_root = stored if stored and cmds.objExists(stored) else control
    if cmds.objExists(delete_root):
        cmds.delete(delete_root)
    elif cmds.objExists(control):
        cmds.delete(control)
