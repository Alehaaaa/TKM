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
  of the drive instead of getting its channels locked outright. Object,
  World, and Camera constrain coincident -- World used to be a hand-built
  parent-safe matrix network, but a plain constraint already accounts for
  the object and control having different parents, so that network was
  redundant. Relative, Grab Release, and Child constrain with the offset
  preserved instead (Camera is currently an alias for World -- a live
  camera-relative follow would need to constrain the control to the active
  camera the way Follow Cam already does, which would fight that tool
  rather than complement it, so this is intentionally just the coincident
  constraint for now; Grab Release is the same offset-preserving constraint
  as Relative -- a temporary "grab" that Revert cleanly lets go of). Scale
  isn't offered a space choice and always passes straight through
  coincident, same as Object/World/Camera -- but, like every other channel
  group, through a real ``scaleConstraint`` rather than an expression.
  Nothing in this tool drives anything through an expression anymore.

Confirming the dialog calls ``create_controls_with_options()``, which
builds one control per object: sized and positioned to match it (a static
starting pose -- an already-animated object's own keys stay its own,
freed up for the constraint to drive rather than copied onto the new
control, see ``_capture_channel``), and driving the object back through
whichever mechanism the chosen spaces call for -- *unless* the object being
controlled is itself another Temporal Control's control (nesting one
Temporal Control inside another). In that case Position/Orientation space
is ignored entirely and ``_parent_nested_control`` makes the new control a
real Maya parent of the nested one instead -- no constraint, no
expression, no connection of any kind, just an ordinary child transform
that keeps moving/keying exactly like any other child would. Bake/Revert
detect this the same way (``_nested_parent_for``) and reparent the nested
control back out before removing the new one, baking its motion down onto
its own channels first if Bake was used (``_bake_nested_control``).

Right-click (``build_temporal_controls_context_menu``) gives:

- **Bake Mode**: Bake Keys or Bake Frames (``BAKE_MODES`` -- one setting,
  shared by every bake path in this tool). Both funnel through the same
  ``_bake_range_to_target`` (``cmds.bakeResults``) -- Bake Frames calls it
  once across the target's full animated range; Bake Keys calls it once
  per control key time instead (a single-frame ``(t, t)`` range each), so
  the result lands "as keyed", not resampled. **Lightning Mode** is a
  separate checkbox affecting either mode's underlying bake the same way:
  it maps onto ``bakeResults``' own ``simulation`` flag, trading
  guaranteed-correct per-frame evaluation for Maya's faster math-based
  shortcut wherever it decides that's safe -- Bake Keys just applies that
  trade-off once per key instead of once across a whole range.
- **Space**: re-drive the selected controls through a different Position/
  Orientation space live (``switch_controls_space``) -- everything
  ``SWITCHABLE_SPACES`` offers except Grab Release, which is a one-shot
  "temporary grab" concept, not something to switch back into later.
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
"""

import json
import math
from functools import partial

from maya import cmds

from TheKeyMachine.core.Qt import QtGui, QtWidgets  # type: ignore
from TheKeyMachine.maya import selection
from TheKeyMachine.maya.runtime import TkmSceneNode
from TheKeyMachine.data import icons
from TheKeyMachine.tools import common as toolCommon
from TheKeyMachine.tools.temporal_controls import shapes
import TheKeyMachine.ui.widgets.util as wutil


ROOT_GROUP = "Temporal_Controls"

TAG_ATTR = "tkmTemporalControl"
TARGET_ATTR = "tkmTemporalTarget"
DELETE_ROOT_ATTR = "tkmTemporalDeleteRoot"
RESTORE_ATTR = "tkmTemporalRestore"
DRIVER_NODES_ATTR = "tkmTemporalDriverNodes"
NESTED_PARENT_ATTR = "tkmTemporalNestedParent"
MUTED_ATTR = "tkmTemporalMuted"

# Temp Controls Panel state -- BASE_RADIUS/SHAPE/SIZE_MULT/ORIENTATION back
# the panel's shape picker + size/rotation sliders (see set_control_shape,
# scale_control, set_control_orientation); POSITION/ORIENTATION_SPACE back
# its Position/Orientation columns (see set_control_space);
# LOCK_SPACE_ATTR backs the lock between them; EXTRA_ATTR marks a control
# the panel itself added on top of a System's main control (Add Child/Add
# Parent), the only kind its Remove Control action is allowed to delete.
BASE_RADIUS_ATTR = "tkmTemporalBaseRadius"
SHAPE_ATTR = "tkmTemporalShape"
SIZE_MULT_ATTR = "tkmTemporalSizeMult"
ORIENTATION_ATTR = "tkmTemporalOrientation"
EXTRA_ATTR = "tkmTemporalExtra"
POSITION_SPACE_ATTR = "tkmTemporalPositionSpace"
ORIENTATION_SPACE_ATTR = "tkmTemporalOrientationSpace"
LOCK_SPACE_ATTR = "tkmTemporalSpaceLocked"

TRANSLATE_CHANNELS = ("translateX", "translateY", "translateZ")
ROTATE_CHANNELS = ("rotateX", "rotateY", "rotateZ")
SCALE_CHANNELS = ("scaleX", "scaleY", "scaleZ")
CHANNELS = TRANSLATE_CHANNELS + ROTATE_CHANNELS + SCALE_CHANNELS

DEFAULT_RADIUS = 10.0

# Which shapes.SHAPES entry the Aim system's aim-target ("pole") is built
# from. Not yet user-facing -- see shapes.py for the plan to expose this (and
# a shape choice for every System's main control) as a dialog column.
AIM_TARGET_SHAPE = "sphere"

SYSTEMS = (
    {"id": "simple", "label": "Simple Control", "icon": "temporal_controls_simple"},
    {"id": "group", "label": "Group Control", "icon": "temporal_controls_group"},
    {"id": "aim", "label": "Aim Control", "icon": "temporal_controls_aim"},
    {"id": "fk_chain", "label": "FK Chain Control", "icon": "temporal_controls_fk_chain"},
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

# The right-click menu's live re-space list (see switch_controls_space) --
# every SPACES entry except Grab Release, which is a one-shot "temporary
# grab" concept (see its SPACES docstring line in the module docstring
# above) that doesn't make sense to switch an already-settled control back
# into after the fact.
SWITCHABLE_SPACES = tuple(space for space in SPACES if space["id"] != "grab_release")

DEFAULT_SYSTEM = "simple"
DEFAULT_SPACE = "object"

# Temp Controls Panel defaults (see the attribute block above).
DEFAULT_SIZE_MULT = 1.0
# How much a full-throw Size slider drag scales a control by: the slider
# maps its -100..100 range onto 2**(SIZE_NUDGE_STEP * value/100), so a full
# drag to one edge doubles/halves the control (at the default 1.0) -- see
# TempControlsPanelWindow._size_factor_for.
SIZE_NUDGE_STEP = 1.0

# The Rotation slider isn't a free/cumulative nudge -- it has exactly 6
# stops, one per fixed pose a control can be snapped into relative to
# however it was originally built: the one it started in ("up"), fully
# flipped ("down"), and the four it reaches by tipping 90 degrees off "up"
# toward each side ("forward"/"backward"/"right"/"left"). Order here is
# both the slider's own left-to-right order and ORIENTATION_ATTR's set of
# valid values -- see set_control_orientation/_rotate_point.
ORIENTATIONS = (
    {"id": "up", "label": "Up"},
    {"id": "down", "label": "Down"},
    {"id": "forward", "label": "Forward"},
    {"id": "backward", "label": "Backward"},
    {"id": "right", "label": "Right"},
    {"id": "left", "label": "Left"},
)
DEFAULT_ORIENTATION = "up"

# Each pose above as the single (axis, degrees) rotation that reaches it
# from "up" (identity, no rotation) -- the shape's own as-built pose.
# forward/backward tip around X; right/left tip around Z; down is a full
# flip (either axis gives the same result for a symmetric-enough tip, X is
# just the one picked here for consistency with forward/backward).
_ORIENTATION_TRANSFORMS = {
    "up": None,
    "down": ("x", 180.0),
    "forward": ("x", -90.0),
    "backward": ("x", 90.0),
    "right": ("z", 90.0),
    "left": ("z", -90.0),
}

# Right-click menu: whether Bake (and Mute Bake, and the Bake half of the
# nested-control path) copies the control's existing keyframes as-is
# ("keys" -- see _extract_keys_to_target) or samples every frame across its
# animated range instead ("frames" -- see _bake_frames_to_target /
# _bake_nested_control). One setting, shared by every bake path in this
# tool, not a per-action choice.
BAKE_MODES = (
    {"id": "keys", "label": "Bake Keys"},
    {"id": "frames", "label": "Bake Frames"},
)
DEFAULT_BAKE_MODE = "keys"

# Right-click menu checkbox. Both bake modes go through the same
# cmds.bakeResults call now (_bake_range_to_target), so this applies
# either way -- Bake Keys just prunes the result down to sparse keys
# afterward, it isn't exempt from the initial dense bake's own
# speed/correctness trade-off. See cmds.bakeResults' own ``simulation``
# flag, which this maps directly onto:
# simulation=True evaluates the full scene at every frame (always correct,
# slower); simulation=False lets Maya compute results mathematically
# wherever it decides that's safe (faster, Maya's own "Lightning"-style
# shortcut) -- see _lightning_simulation_flag.
LIGHTNING_MODE_SETTING = "lightning_mode"

_SETTINGS_NAMESPACE = "temporal_controls"

_temporal_controls_dialog = None
# The toolbar button that opened the creation dialog -- captured here at
# click time (see create_controls) because by the time the dialog is
# actually confirmed, the toolbar click's own ToolOperation (and its
# anchor_widget) is long closed. Threaded through to
# create_controls_with_options so _warn_locked_attributes can anchor its
# message to this button instead of just floating near the cursor.
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
    source_button = _temporal_controls_source_button

    def _on_confirmed(system, position_space, orientation_space, label, color):
        create_controls_with_options(
            objects,
            system=system,
            position_space=position_space,
            orientation_space=orientation_space,
            label=label,
            color=color,
            anchor_widget=source_button,
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


def get_bake_mode():
    from TheKeyMachine.core import settings
    return settings.get_setting("bake_mode", DEFAULT_BAKE_MODE, namespace=_SETTINGS_NAMESPACE)


def set_bake_mode(mode_id):
    from TheKeyMachine.core import settings
    settings.set_settings({"bake_mode": mode_id}, namespace=_SETTINGS_NAMESPACE)


def is_lightning_mode_enabled():
    from TheKeyMachine.core import settings
    return bool(settings.get_setting(LIGHTNING_MODE_SETTING, False, namespace=_SETTINGS_NAMESPACE))


def set_lightning_mode_enabled(enabled):
    from TheKeyMachine.core import settings
    settings.set_settings({LIGHTNING_MODE_SETTING: bool(enabled)}, namespace=_SETTINGS_NAMESPACE)


def _lightning_simulation_flag():
    """The ``cmds.bakeResults(simulation=...)`` value Lightning Mode maps
    onto -- see LIGHTNING_MODE_SETTING's docstring above."""
    return not is_lightning_mode_enabled()


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
):
    objects = [obj for obj in objects if cmds.objExists(obj)]
    if not objects:
        return wutil.make_inViewMessage("Nothing left to control -- selection changed")

    # Opens the one real undo chunk / progress bar / tint session for this
    # whole multi-object operation (or merges into an already-open one --
    # see tool_operation's own docstring). This used to just read
    # current_tool_operation() and hope a dispatcher had already opened one,
    # but nothing does: the actual scene edit happens later, asynchronously,
    # when the creation dialog's own confirm button fires _on_confirmed --
    # never through the registered-command dispatcher that would otherwise
    # supply that operation. Without opening it here, confirming for N
    # objects left N+ separate undo steps instead of one.
    #
    # anchor_widget (the temporal_controls toolbar button, captured by
    # create_controls -- see _temporal_controls_source_button) is only
    # used if this actually opens a *new* operation; merging into an
    # add_parent_control/add_child_control caller's already-open one (its
    # own anchor_widget, e.g. the panel's own action button) wins instead,
    # same as every other tool_operation() argument in that case.
    with toolCommon.tool_operation(
        tool_id="temporal_controls",
        label="Create Temporal Controls",
        undo=True,
        anchor_widget=anchor_widget,
    ) as operation:
        group = TkmSceneNode.root().child(ROOT_GROUP, icon=icons.temporal_controls)

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
        locked_report = []
        chain_parent = None
        for obj in objects:
            if operation.cancelled:
                break
            if not _existing_control_for(obj):
                options["chain_parent"] = chain_parent if system == "fk_chain" else None
                control, chain_anchor = _create_control_for(obj, group.name, options, locked_report=locked_report)
                if control:
                    new_controls.append(control)
                    chain_parent = chain_anchor
            operation.step()

        if locked_report:
            _warn_locked_attributes(locked_report, anchor_widget=operation.anchor_widget)

        if new_controls:
            cmds.select(new_controls)
            return new_controls
        return wutil.make_inViewMessage("Selected objects already have Temporal Controls")


def _warn_locked_attributes(locked_plugs, anchor_widget=None):
    """Surface every locked destination attribute _drive_with_constraint had
    to skip (see its own docstring) as one auto-hiding message instead of
    letting them fail silently. Anchors to *anchor_widget* (the temporal
    controls toolbar button, or whichever button actually triggered this
    operation -- see create_controls_with_options) when it's still valid,
    same as a tooltip would. Best-effort -- if the auto-hide widget can't
    be imported/built for some reason, this falls back to a plain
    cmds.warning rather than raising out of control creation."""
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
        customDialogs.QFlatAutoHideMessage.show_message(tooltip, duration=5000, anchor_widget=anchor_widget)
    except Exception:
        cmds.warning(
            "Temporal Controls: couldn't connect locked attributes: {}".format(", ".join(short_plugs))
        )


def _plug(node, attribute):
    """``"node.attribute"`` -- the one place this module builds a plug
    string, instead of ``"{}.{}".format(node, attribute)`` inline at each
    of the dozen-plus call sites that used to repeat it. There's no shared
    core/-level version of this to reuse instead: it's an established
    per-module convention across the codebase (e.g. animation_layers'
    own ``_plug``, animation_offset's ``_plug_name``) rather than
    something centralized, so this follows that same local-helper pattern
    rather than inventing a new one."""
    return "{}.{}".format(node, attribute)


def _short_plug_name(plug):
    """``some|long|dag|Path:node.attribute`` -> ``node.attribute`` -- the
    full path is Maya-uniqueness noise the user doesn't need to see in a
    "here's what I couldn't connect" message; the object's own (possibly
    namespaced) short name is all that's needed to identify it."""
    obj_part, _, attr_part = plug.rpartition(".")
    short_obj = obj_part.split("|")[-1] if obj_part else obj_part
    return _plug(short_obj, attr_part) if short_obj else plug


def _debug_enabled():
    """The same TKM_TOOL_DEBUG switch every other developer-only print in
    the app already gates on (TheKeyMachine.core.debug.is_enabled()) --
    off by default, on via that env var/.env entry. Wrapped in try/except
    since this gets called on every control creation and a debug-module
    import failure shouldn't be able to break actual control creation."""
    try:
        from TheKeyMachine.core import debug

        return debug.is_enabled()
    except Exception:
        return False


def _debug_log_creation_step(step, obj, options, control=None, delete_root=None, chain_anchor=None,
                              translate_channels=None, rotate_channels=None, scale_channels=None,
                              driver_nodes=None):
    """Trace every judgement/input that went into building one control --
    only when TKM_TOOL_DEBUG is on (_debug_enabled) -- so a placement or
    space-driving bug (an object landing at the wrong position/rotation,
    or driven through the wrong space) can be diagnosed from the Script
    Editor instead of guessed at. Called at each real decision point in
    _create_control_for rather than once at the end, so a build that fails
    partway through (an exception, or the early nested-control return)
    still leaves a trail up to wherever it stopped."""
    if not _debug_enabled():
        return
    lines = ["object: {}".format(obj), "step: {}".format(step)]
    lines.append(
        "options: system={} position_space={} orientation_space={} label={!r} color={}".format(
            options.get("system"), options.get("position_space"),
            options.get("orientation_space"), options.get("label"), options.get("color"),
        )
    )
    if control and cmds.objExists(control):
        try:
            obj_pos = cmds.xform(obj, query=True, worldSpace=True, translation=True) if cmds.objExists(obj) else None
            obj_rot = cmds.xform(obj, query=True, worldSpace=True, rotation=True) if cmds.objExists(obj) else None
            ctrl_pos = cmds.xform(control, query=True, worldSpace=True, translation=True)
            ctrl_rot = cmds.xform(control, query=True, worldSpace=True, rotation=True)
        except Exception as exc:
            obj_pos = obj_rot = ctrl_pos = ctrl_rot = "<xform query failed: {}>".format(exc)
        lines.append("shape: {}  radius: {}".format(shapes.DEFAULT_SHAPE, _control_radius(obj) if cmds.objExists(obj) else "?"))
        lines.append("control: {}  delete_root: {}  chain_anchor: {}".format(control, delete_root, chain_anchor))
        lines.append("object world xform:   pos={} rot={}".format(obj_pos, obj_rot))
        lines.append("control world xform:  pos={} rot={}".format(ctrl_pos, ctrl_rot))
    if translate_channels is not None or rotate_channels is not None:
        lines.append("translate_channels: {}  driven through: {}".format(translate_channels, options.get("position_space")))
        lines.append("rotate_channels: {}  driven through: {}".format(rotate_channels, options.get("orientation_space")))
        lines.append("scale_channels (present but not driven -- see _create_control_for): {}".format(scale_channels))
        lines.append("driver_nodes: {}".format(driver_nodes))
    print("[TKM Temporal Controls] {}".format(lines[0]))
    for line in lines[1:]:
        print("    {}".format(line))


def _create_control_for(obj, group, options, locked_report=None):
    control, delete_root, chain_anchor = _build_control_hierarchy(obj, group, options)
    _debug_log_creation_step("built", obj, options, control=control, delete_root=delete_root, chain_anchor=chain_anchor)

    if options.get("color"):
        # Color the whole hierarchy this System built -- not just *control* --
        # so a helper like the Aim system's aim-target control picks up the
        # chosen color too instead of being left at its unstyled default.
        _apply_control_color(delete_root, options["color"])

    _tag_control(control, obj, delete_root)

    if _is_temporal_control(obj):
        # obj is itself another Temporal Control's control -- nesting one
        # Temporal Control inside another. See _parent_nested_control: real
        # parenting instead of channel-driving, so there's nothing here for
        # RESTORE_ATTR/DRIVER_NODES_ATTR to track -- they're left at their
        # empty default (both getters already treat "unset" as empty).
        _parent_nested_control(control, obj)
        _debug_log_creation_step("nested (parented directly, no channel-driving)", obj, options, control=control)
        return control, chain_anchor

    restore_map = {}
    for channel in CHANNELS:
        captured = _capture_channel(control, obj, channel)
        if captured:
            channel_name, payload = captured
            restore_map[channel_name] = payload

    TkmSceneNode(control).set_attr(RESTORE_ATTR, json.dumps(restore_map))

    # Per-group (translate/rotate/scale) instead of one flat list -- the Temp
    # Controls Panel needs to re-space Position and Orientation independently
    # (see set_control_space), which means being able to tear down and
    # rebuild just one group's driver nodes without touching the others'.
    driver_nodes = {}
    translate_channels = [c for c in TRANSLATE_CHANNELS if c in restore_map]
    rotate_channels = [c for c in ROTATE_CHANNELS if c in restore_map]
    scale_channels = [c for c in SCALE_CHANNELS if c in restore_map]

    node = TkmSceneNode(control)
    if translate_channels:
        driver_nodes["translate"] = _drive_group(
            control, obj, translate_channels, options["position_space"], restore_map, locked_report=locked_report
        )
        node.set_attr(POSITION_SPACE_ATTR, options["position_space"])
    if rotate_channels:
        driver_nodes["rotate"] = _drive_group(
            control, obj, rotate_channels, options["orientation_space"], restore_map, locked_report=locked_report
        )
        node.set_attr(ORIENTATION_SPACE_ATTR, options["orientation_space"])
    # Scale connection is temporarily disabled -- scaleConstraint has been
    # seen hard-crashing control creation on a locked/non-writable scale
    # channel (e.g. a referenced rig control) in a way _drive_with_constraint's
    # own skip= handling doesn't fully protect against yet. Until that's
    # sorted out, scale just isn't driven at all rather than risking the
    # whole control failing to build. scale_channels itself is still kept
    # around (not driven) -- _debug_log_creation_step below reports it so
    # it's visible in the trace that it was captured but deliberately not
    # connected, rather than silently dropped.

    node.set_attr(DRIVER_NODES_ATTR, json.dumps(driver_nodes))
    # Seed the panel's Position/Orientation lock from how this control was
    # actually built: if both spaces were the same at creation, treat that
    # as "locked" from the start rather than defaulting to unlocked --
    # matches how most controls get built in practice (one space picked for
    # both), and lets the panel show the lock already toggled for them.
    if translate_channels and rotate_channels and options["position_space"] == options["orientation_space"]:
        node.set_attr(LOCK_SPACE_ATTR, True, attributeType="bool")

    _debug_log_creation_step(
        "driven", obj, options, control=control,
        translate_channels=translate_channels, rotate_channels=rotate_channels,
        scale_channels=scale_channels, driver_nodes=driver_nodes,
    )
    return control, chain_anchor


def _build_control_hierarchy(obj, group, options):
    """Build the control (and, for some Systems, its helper nodes).

    Returns ``(control, delete_root, chain_anchor)``:

    - *delete_root* is the node Bake/Revert should ``cmds.delete()`` to
      remove everything this System added (the control itself for Simple/FK
      Chain, or the offset buffer for Group/Aim, whose deletion cascades to
      the control and any helper control/constraint parented under it).
    - *chain_anchor* is the node the *next* object's control should parent
      under when System is FK Chain (always the control itself, so each
      link visually carries the next -- never the buffer).
    """
    system = options.get("system", DEFAULT_SYSTEM)
    label = options.get("label") or ""
    radius = _control_radius(obj)
    short_name = obj.split("|")[-1].split(":")[-1]
    base_name = "{}_{}".format(label, short_name) if label else short_name

    control = shapes.build(shapes.DEFAULT_SHAPE, "{}_temporalCtrl#".format(base_name), radius)
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
    # Built from shapes.SHAPES rather than cmds.spaceLocator -- a real curve
    # control instead of a raw Maya locator, so it picks up
    # _apply_control_color like every other control here.
    aim_target = shapes.build(
        AIM_TARGET_SHAPE, "{}_temporalAim#".format(base_name), max(radius * 0.15, 0.5),
    )
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


def _apply_control_color(root, color_hex):
    """Color *root* and everything under it -- not just *root*'s own shapes --
    so a helper control parented alongside/under it (the Aim system's
    aim-target, the Group/Aim buffer) picks up the chosen color too, instead
    of only the top control being styled while its helpers stay default."""
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
        return tuple(int(color_hex[i:i + 2], 16) / 255.0 for i in (0, 2, 4))
    except ValueError:
        return (0.2, 0.6, 0.8)


# ----------------------------------------------------------------------
# Temp Controls Panel: shape / size / orientation
# ----------------------------------------------------------------------
# Size and orientation are applied straight to the control's own curve CVs
# (cmds.scale / the per-CV xform math in set_control_orientation) rather
# than by rebuilding the curve from shapes.py each time -- cheap, keeps
# whatever shape is currently active, and the CVs themselves stay the only
# source of truth (SIZE_MULT_ATTR/ORIENTATION_ATTR just track the
# accumulated total so a later shape swap can rebuild at the same size/
# orientation). Only control's own shape nodes are touched -- a System's
# helper nodes (Aim's aim-target, Group/Aim's buffer) are a deliberate v1
# scope cut, not part of this.

def _control_shape_nodes(control):
    return cmds.listRelatives(control, shapes=True, fullPath=True) or []


def _control_base_radius(control):
    stored = TkmSceneNode(control).get_attr(BASE_RADIUS_ATTR)
    try:
        return float(stored) if stored is not None else DEFAULT_RADIUS
    except (TypeError, ValueError):
        return DEFAULT_RADIUS


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
    return TkmSceneNode(control).get_attr(SHAPE_ATTR) or shapes.DEFAULT_SHAPE


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
        if cmds.attributeQuery("overrideRGBColors", node=shape_node, exists=True) and cmds.getAttr(shape_node + ".overrideRGBColors"):
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
    return "#{:02x}{:02x}{:02x}".format(*(max(0, min(255, round(channel * 255))) for channel in rgb))


def scale_control(control, factor):
    """Scale control's own curve CVs by *factor* (a relative multiplier,
    e.g. 1.02 to grow 2%) -- the panel's Size slider calls this
    continuously while dragging, with a small incremental *factor* each
    tick, rather than one fixed step on release.

    Scales each CV directly in the shape's own object space (the same
    per-CV ``cmds.xform`` pattern ``set_control_orientation`` uses) instead
    of ``cmds.scale``'s ``pivot`` flag -- that pivot is a world-space
    point regardless of ``objectSpace`` (which only picks the axes the
    scale is applied along, not where the pivot itself sits), so a control
    sitting away from the scene origin was visibly growing away from world
    (0, 0, 0) instead of from its own center every time this ran.
    """
    if not cmds.objExists(control) or not factor or factor <= 0 or abs(factor - 1.0) < 1e-9:
        return False
    cvs = _shape_cv_selector(_control_shape_nodes(control))
    if not cvs:
        return False
    for cv in cvs:
        x, y, z = cmds.xform(cv, query=True, translation=True, objectSpace=True)
        cmds.xform(cv, translation=(x * factor, y * factor, z * factor), objectSpace=True)
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
    return x * cos_t + z * sin_t, y, -x * sin_t + z * cos_t  # "y", unused today but complete


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
        cmds.xform(cv, translation=_rotate_point(x, y, z, axis, degrees), objectSpace=True)


def set_control_orientation(control, orientation_id):
    """Snap control's own curve CVs to one of ORIENTATIONS' 6 fixed poses
    (Up/Down/Forward/Backward/Right/Left) relative to however the shape
    was originally built -- not a free-spinning nudge. The panel's
    Rotation slider has exactly 6 stops, one per pose, and calls this with
    whichever one the handle just landed on.

    Undoes the control's *current* pose first (each pose's own inverse --
    same axis, negated angle) before applying the target one, so this
    always measures from the shape's real "up" creation pose instead of
    drifting across repeated switches.

    Deliberately does its own rotation-matrix math per CV via
    ``cmds.xform(..., translation=..., objectSpace=True)`` instead of
    ``cmds.rotate(...)`` on the component list: ``cmds.rotate``'s
    relative/objectSpace/pivot flag combination for *component* targets
    (as opposed to transform nodes) went through several different, all
    apparently-inert flag combinations across earlier attempts at this
    function, which strongly suggests something about how that command
    interprets those flags for components specifically doesn't do what's
    expected here. Querying and setting each CV's own object-space
    translation directly sidesteps all of that -- there's no flag
    ambiguity left to get wrong.

    Note a shape that's symmetric under a given pose's particular tip/flip
    (most obviously a plain circle/sphere, the default "circle" every
    control starts as -- symmetric under all of them) will genuinely show
    no visible change; pick an asymmetric shape (Square, Locator,
    Diamond, ...) from the panel's shape picker to see it clearly."""
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
        cmds.warning("Temp Controls Panel: couldn't orient {}: {}".format(control, exc))
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
    radius = _control_base_radius(control) * get_control_size_mult(control)

    short_name = control.split("|")[-1].split(":")[-1]
    temp = shapes.build(shape_id, "{}_shapeSwap#".format(short_name), radius)

    # shapes.build() always comes out at "up" -- apply whatever pose
    # control is currently in on top of that, same as set_control_orientation
    # does for an existing shape's CVs.
    orientation_id = get_control_orientation(control)
    cvs = _shape_cv_selector(cmds.listRelatives(temp, shapes=True, fullPath=True) or [])
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


def _tag_control(control, obj, delete_root):
    """Stamp control's identifying attributes through TkmSceneNode -- the
    project's own node-tagging wrapper (see maya/runtime.py), the same one
    ``create_controls_with_options`` already uses to create the tool's root
    group -- instead of hand-rolled addAttr/setAttr pairs.

    *obj* may be ``None`` -- the Temp Controls Panel's Add Child Control
    action (``add_child_control``) tags a free control with no external
    target this way, which TARGET_ATTR then just stores as "" (the same
    "unset" TARGET_ATTR already means for anything _target_for reads).

    RESTORE_ATTR/DRIVER_NODES_ATTR aren't declared here: they're only ever
    written once real driving happens (_create_control_for), and both
    readers (_restore_map_for, _driver_nodes_for) already treat a plug that
    was never created as empty."""
    node = TkmSceneNode(control)
    node.set_attr(TAG_ATTR, True, attributeType="bool")
    node.set_attr(TARGET_ATTR, cmds.ls(obj, long=True)[0] if obj else "")
    node.set_attr(DELETE_ROOT_ATTR, cmds.ls(delete_root, long=True)[0])
    node.set_attr(BASE_RADIUS_ATTR, _control_radius(obj) if obj else _control_radius(control))
    for attr in (TAG_ATTR, TARGET_ATTR, DELETE_ROOT_ATTR, BASE_RADIUS_ATTR):
        cmds.setAttr(_plug(control, attr), lock=True)
    # Shape/size/orientation state -- left unlocked, the Temp Controls
    # Panel updates these over the control's lifetime (set_control_shape,
    # scale_control, set_control_orientation). Every control starts life
    # built from shapes.DEFAULT_SHAPE (_build_control_hierarchy /
    # add_child_control), so that's the accurate starting tag here.
    node.set_attr(SHAPE_ATTR, shapes.DEFAULT_SHAPE)
    node.set_attr(SIZE_MULT_ATTR, DEFAULT_SIZE_MULT)
    node.set_attr(ORIENTATION_ATTR, DEFAULT_ORIENTATION)


def _capture_channel(control, obj, channel):
    """Free one of *obj*'s channels up so the real constraint (see
    ``_drive_group``/``_drive_with_constraint``) can take over driving it,
    and record whatever was driving it before so Bake/Revert can put it
    back later.

    Returns ``(channel, restore_payload)``, or ``None`` if the channel was
    left untouched (locked, or already driven by something this tool
    shouldn't take over). The payload always carries ``base_value`` -- the
    object's value at capture time -- for Bake/Revert's own bookkeeping.

    Deliberately never writes to *control*'s own plug. *control* is built
    under the Temporal Controls group, not reparented into *obj*'s own
    hierarchy, so *obj*'s local channel value and *control*'s local channel
    value live in unrelated spaces -- writing one onto the other (this used
    to ``setAttr``/``copyKey`` obj's raw local value straight onto control)
    is only ever correct by coincidence. *control* is already sitting on
    *obj*'s exact world transform from ``matchTransform`` at build time
    (see ``_build_control_hierarchy``), which is what the downstream
    ``maintainOffset=False``/``True`` constraint actually needs -- so the
    right move here is to leave *control* alone. Writing obj's raw local
    value onto it was collapsing both to world-space identity whenever obj
    was a "zeroed" rig control (local channels at/near 0, real position
    coming from static offset ancestor groups) -- once control got zeroed
    the same way, the maintainOffset=False constraint just matched obj to
    it, in world space, at (0, 0, 0).
    """
    obj_plug = _plug(obj, channel)
    if not cmds.objExists(obj_plug) or cmds.getAttr(obj_plug, lock=True):
        return None

    base_value = cmds.getAttr(obj_plug)
    connections = cmds.listConnections(obj_plug, source=True, destination=False, plugs=True) or []
    source_plug = connections[0] if connections else None

    if source_plug:
        source_node = source_plug.split(".")[0]
        if not cmds.nodeType(source_node).startswith("animCurve"):
            # Already driven by a constraint/expression/other setup -- leave it alone.
            return None
        cmds.disconnectAttr(source_plug, obj_plug)
        return channel, {"mode": "curve", "source": source_plug, "base_value": base_value}

    if not cmds.getAttr(obj_plug, settable=True):
        return None

    return channel, {"mode": "value", "value": base_value, "base_value": base_value}


# ----------------------------------------------------------------------
# Position / Orientation space driving
# ----------------------------------------------------------------------

def _drive_group(control, obj, channels, space_mode, restore_map, locked_report=None):
    """Wire one channel group (all-translate or all-rotate) from *control*
    to *obj* per *space_mode*. Returns the extra node names created outside
    the control's own hierarchy, for Bake/Revert to clean up later.

    Every mode drives *obj* through a real constraint now -- see
    ``_drive_with_constraint`` -- instead of the expression/connectAttr
    hard-drives this used to build per mode. Object, World, and Camera
    constrain coincident (``maintainOffset=False``): a plain constraint
    already computes correctly regardless of whether *obj* and *control*
    share a parent, so the old hand-built World matrix network was doing
    extra work for nothing World/Camera-specific. Relative, Grab Release,
    and Child constrain with the offset preserved (``maintainOffset=True``).
    """
    if not channels:
        return []

    group_kind = "translate" if channels[0].startswith("translate") else "rotate"

    if space_mode in ("relative", "grab_release", "child"):
        return _drive_with_constraint(control, obj, group_kind, maintain_offset=True, locked_report=locked_report)

    # "object", "world", "camera", and any unknown/legacy value all land here.
    return _drive_with_constraint(control, obj, group_kind, maintain_offset=False, locked_report=locked_report)


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


def _drive_with_constraint(control, obj, group_kind, maintain_offset, locked_report=None):
    """Constrain *obj* to *control* with a real point/orient/scale
    constraint -- "parents" -- and prime a keyframe on *obj* first if it has
    none, so Maya wires in its automatic ``blendParent1``/pairBlend blend
    the same way it already would for a channel that had prior animation on
    it. No expression involved for any channel group -- translate, rotate,
    and scale are all a constraint now.

    That blend is what keeps *obj* nudgeable by hand on top of the
    control's drive afterward. Without it, constraining a channel that has
    never been keyed drives it outright through a bare connection, and
    dragging the object in the viewport does nothing -- which is exactly
    what broke when one Temporal Control's object was itself another
    Temporal Control's control: a freshly-built circle, with no keys of its
    own yet, so Maya never inserted the blend.

    Returns the constraint node, the pairBlend Maya inserted (if any), and
    the priming animCurve itself -- so Bake/Revert's
    ``_delete_driver_nodes`` cleans up all three. Leaving any one behind
    would either strand *obj*'s channel fed by a now-dangling pairBlend
    (instead of freed for revert's ``setAttr``/``connectAttr`` to land on),
    or leave the priming animCurve as an orphaned, unused node once the
    pairBlend that referenced it is gone -- harmless, but exactly the kind
    of node litter Bake/Revert are supposed to leave nothing of.

    Not every constraint type actually honors the priming trick, though --
    ``scaleConstraint`` in particular has been seen refusing the connection
    outright ("Destination attribute must be writable") instead of
    inserting a blend the way point/orientConstraint do for the same
    never-keyed channel. If the constrain call itself fails, the priming
    keys for this group are undone and it's retried once plain, so *obj*
    still ends up controlled -- just without the nudge-on-top blend for
    this particular channel group -- rather than the whole control failing
    to build.

    A genuinely *locked* destination channel (not just never-keyed) is a
    harder case Maya's own constraint commands can refuse outright too
    ("Destination is locked") -- rather than let that crash the whole
    control build, any locked channel is passed to the constraint's own
    ``skip`` flag up front so Maya never attempts it, and the full plug
    name is appended to *locked_report* (when given a list) so the caller
    can tell the user afterward which attributes it couldn't connect."""
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
            primed_curves += cmds.listConnections(plug, source=True, destination=False, type="animCurve") or []

    if len(skip_axes) == len(channels):
        # Every channel in this group is locked -- nothing left to
        # constrain, and calling the constraint command with all axes
        # skipped is a no-op at best. Already recorded above.
        return []

    constrain = _CONSTRAINT_COMMANDS[group_kind]
    constrain_kwargs = {"maintainOffset": maintain_offset}
    if skip_axes:
        constrain_kwargs["skip"] = skip_axes
    try:
        node = constrain(control, obj, **constrain_kwargs)[0]
    except RuntimeError:
        for curve in primed_curves:
            if cmds.objExists(curve):
                cmds.delete(curve)
        primed_curves = []
        try:
            node = constrain(control, obj, **constrain_kwargs)[0]
        except RuntimeError as exc:
            cmds.warning("Temporal Controls: couldn't drive {} on {}: {}".format(group_kind, obj, exc))
            return []

    driver_nodes = [node]
    for curve in primed_curves:
        if curve not in driver_nodes:
            driver_nodes.append(curve)
    for channel in channels:
        plug = _plug(obj, channel)
        if not cmds.objExists(plug):
            continue
        pair_blends = cmds.listConnections(plug, source=True, destination=False, type="pairBlend") or []
        for pair_blend in pair_blends:
            if pair_blend not in driver_nodes:
                driver_nodes.append(pair_blend)

    return driver_nodes


# ----------------------------------------------------------------------
# Bake / Revert
# ----------------------------------------------------------------------

def bake_control(control):
    """Bake -- and remove -- a single Temporal Control: extract its
    animation onto its target (or, for a nested control, bake the target's
    motion under it and hand the target back to its original parent), then
    delete the control. Returns the target node baked onto, or ``None`` if
    *control* had no target to bake (a free "Add Child" extra control just
    gets removed). The shared per-control step both the batch
    ``bake_controls`` (right-click menu, whole selection) and the Temp
    Controls Panel's single-control Remove and Bake button call -- the
    panel scopes to whichever control is selected in its list, independent
    of the scene's actual selection."""
    if not cmds.objExists(control):
        return None
    target = _target_for(control)
    restore_map = _restore_map_for(control)
    nested_parent = _nested_parent_for(control)

    if target:
        # Reparent obj back out from under control *before* deleting control
        # below, or obj -- still control's child at that point -- would get
        # deleted along with it.
        #
        # Every path here has to run *before* _delete_driver_nodes: Bake
        # Frames' cmds.bakeResults and Bake Keys' own per-key-time sampling
        # (see _extract_keys_to_target) both read target's live, still-
        # actually-driven value -- deleting the constraint first would
        # leave target frozen at one static pose for either to just copy
        # across every sampled frame/key, instead of its real motion. A
        # nested control's obj was never driven by these nodes to begin
        # with (see _parent_nested_control), so the ordering makes no
        # difference for it, but there's no reason to special-case it.
        if nested_parent is not None:
            _bake_nested_control(control, target, nested_parent)
        elif get_bake_mode() == "frames":
            _bake_frames_to_target(control, target)
        else:
            _extract_keys_to_target(control, target, restore_map)

    _delete_driver_nodes(control)
    _delete_control_nodes(control)
    return target


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
        target = bake_control(control)
        if target:
            baked_targets.append(target)
        if operation is not None:
            operation.step()

    if baked_targets:
        # Filter for existence right before selecting: baking a nested
        # control whose target is itself another Temporal Control's
        # control can, earlier in this same batch, delete a node another
        # entry in baked_targets refers to.
        existing = [node for node in baked_targets if cmds.objExists(node)]
        if existing:
            cmds.select(existing)
        return baked_targets
    return wutil.make_inViewMessage("Nothing baked")


def _extract_keys_to_target(control, target, restore_map):
    """Key *target*'s own channels at exactly the times control has keys --
    not resampled every frame the way ``_bake_frames_to_target``/Bake
    Frames mode is -- so it still reads "as keyed", just correctly.

    This must run while *target* is still actually being driven by the
    live constraint (before ``_delete_driver_nodes`` -- see ``bake_control``,
    which now calls this first). A channel control has no keys on needs
    nothing done at all: target is already sitting at the right, live,
    driven value, and it just stays there, frozen, the moment the driver
    nodes come down right after this returns.

    For a keyed channel, this used to ``copyKey``/``pasteKey`` control's
    own curve directly onto target -- copying control's raw *local* number
    onto target's own, differently-parented, local channel, exactly the
    same space-mismatch bug ``_capture_channel`` used to have (control
    lives under Temporal_Controls, target is wherever its own rig
    hierarchy actually put it; their local values aren't interchangeable).
    ``_bake_range_to_target`` -- the same call ``_bake_frames_to_target``/
    Bake Frames mode uses, our one trusted bake mechanism, not a hand-
    rolled substitute -- sidesteps that entirely by reading target's own
    already-correctly-computed value instead of copying control's number.
    Called once per control key time (a single-frame ``(t, t)`` range, not
    the whole span) so the result still lands "as keyed", not resampled --
    and each of those calls still goes through Lightning Mode's own
    simulation-vs-math-shortcut trade-off (``_lightning_simulation_flag``,
    baked into ``_bake_range_to_target`` itself) exactly like Bake Frames'
    single full-range call does, just one key at a time instead of one
    continuous sweep. (A hand-rolled ``getAttr``-then-``setKeyframe`` per
    time would also have to fight the pairBlend priming
    ``_drive_with_constraint`` relies on to keep target nudgeable --
    writing a key onto a primed channel can shift ``blendParent``'s own
    weighting and throw off every *later* sample -- bakeResults doesn't
    have that problem since it drives each frame's evaluation itself
    rather than writing keys as it goes.)
    """
    channels = [
        channel for channel in (restore_map.keys() if restore_map else CHANNELS)
        if cmds.objExists(_plug(control, channel))
        and cmds.objExists(_plug(target, channel))
        and not cmds.getAttr(_plug(target, channel), lock=True)
    ]
    if not channels:
        return

    keyed_channels = [
        channel for channel in channels
        if cmds.keyframe(_plug(control, channel), query=True, keyframeCount=True)
    ]
    if not keyed_channels:
        return

    key_times = set()
    for channel in keyed_channels:
        key_times.update(
            cmds.keyframe(_plug(control, channel), query=True, timeChange=True) or []
        )
    if not key_times:
        return

    for t in sorted(key_times):
        _bake_range_to_target(target, keyed_channels, t, t)


def _bake_range_to_target(target, channels, start, end):
    """The one ``cmds.bakeResults`` call every bake path in this tool
    funnels through -- Bake Frames (``_bake_frames_to_target``) uses its
    result as-is; Bake Keys (``_extract_keys_to_target``) prunes it down to
    just control's own key times afterward. Centralizing this means both
    modes share the exact same, single, guaranteed-correct-against-the-
    live-driven-DG bake call instead of each hand-rolling their own.
    Respects Lightning Mode (``_lightning_simulation_flag``) either way.
    Returns whether the bake actually happened."""
    try:
        cmds.bakeResults(
            target, simulation=_lightning_simulation_flag(),
            time=(start, end), attribute=list(channels),
        )
        return True
    except RuntimeError:
        return False


def _bake_frames_to_target(control, target):
    """Bake Frames mode (see BAKE_MODES/get_bake_mode): sample *control*'s
    motion onto *target* across its full animated range with
    _bake_range_to_target, instead of copying the control's existing
    keyframes as-is like _extract_keys_to_target (Bake Keys mode) does."""
    if not cmds.objExists(target):
        return
    start, end = _time_range_for([control])
    if start is None:
        current = cmds.currentTime(query=True)
        start = end = current
    _bake_range_to_target(target, CHANNELS, start, end)


def _bake_nested_control(control, obj, original_parent):
    """The nested-control counterpart to ``_extract_keys_to_target``: obj
    was never channel-driven to begin with (see ``_parent_nested_control``
    -- it's a real Maya child of control instead), so there are no keys on
    control to copy over. Bake obj's motion under control down onto its own
    channels instead (via _bake_range_to_target, the same bake mechanism
    every other path in this tool uses), then hand it back to
    *original_parent*."""
    if not cmds.objExists(obj):
        return
    start, end = _time_range_for([control, obj])
    if start is None:
        current = cmds.currentTime(query=True)
        start = end = current
    _bake_range_to_target(obj, CHANNELS, start, end)
    _restore_nested_parent(obj, original_parent)


def revert_control(control):
    """Revert -- and remove -- a single Temporal Control: restore its
    target's original channels (or, for a nested control, hand the target
    back to its original parent), then delete the control. Returns the
    target restored, or ``None`` if *control* had no target (a free "Add
    Child" extra control just gets removed). The single-control counterpart
    to bake_control -- see its docstring."""
    if not cmds.objExists(control):
        return None
    target = _target_for(control)
    restore_map = _restore_map_for(control)
    nested_parent = _nested_parent_for(control)
    _delete_driver_nodes(control)

    if target:
        # Reparent obj back out from under control *before* deleting control
        # below, or obj -- still control's child at that point -- would get
        # deleted along with it.
        if nested_parent is not None:
            _restore_nested_parent(target, nested_parent)
        else:
            _restore_target_channels(target, restore_map)

    _delete_control_nodes(control)
    return target


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
        target = revert_control(control)
        if target:
            reverted_targets.append(target)
        if operation is not None:
            operation.step()

    if reverted_targets:
        # Filter for existence right before selecting -- same reasoning as
        # bake_controls' equivalent filter above.
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
    """Mute Revert: disconnect selected Temporal Controls (same teardown as
    Revert -- delete the constraint/pairBlend/priming-curve driver nodes,
    then put the target's channels back the way they were) but leave the
    control node itself in the scene instead of deleting it, so it can
    drive the object again later without recreating it from scratch.
    Nested Temporal Controls (real-parented -- see _parent_nested_control)
    are skipped: muting isn't meaningful for them, since they were never
    driven through a constraint to begin with."""
    controls = [control for control in _controls_to_process() if _nested_parent_for(control) is None]
    if not controls:
        return wutil.make_inViewMessage("No Temporal Controls to mute")

    muted = []
    for control in controls:
        target = _target_for(control)
        restore_map = _restore_map_for(control)
        _delete_driver_nodes(control)
        if target:
            _restore_target_channels(target, restore_map)
        node = TkmSceneNode(control)
        node.set_attr(MUTED_ATTR, True, attributeType="bool")
        node.set_attr(DRIVER_NODES_ATTR, json.dumps([]))
        muted.append(control)

    cmds.select(muted)
    return muted


def mute_and_bake(*_args):
    """Mute Bake: disconnect selected Temporal Controls the same way Mute
    Revert does, but *without* restoring the target's channels -- deleting
    the constraint/pairBlend freezes the target at whatever value the drive
    last produced, which is the point: the resulting motion stays applied
    instead of snapping back, while the control -- which already carries
    that same motion on its own channels, per this tool's usual "the
    control's channels are the free, keyable source of truth" rule -- stays
    in the scene, ready to drive again later."""
    controls = [control for control in _controls_to_process() if _nested_parent_for(control) is None]
    if not controls:
        return wutil.make_inViewMessage("No Temporal Controls to mute")

    muted = []
    for control in controls:
        _delete_driver_nodes(control)
        node = TkmSceneNode(control)
        node.set_attr(MUTED_ATTR, True, attributeType="bool")
        node.set_attr(DRIVER_NODES_ATTR, json.dumps([]))
        muted.append(control)

    cmds.select(muted)
    return muted


def switch_controls_space(space_id, *_args):
    """Re-drive every selected (or targeted) Temporal Control through
    *space_id* for both Position and Orientation -- a live version of the
    System/Space choice the creation dialog only offers up front. Tears
    down the control's current constraint/pairBlend/priming-curve driver
    nodes and rebuilds them through the new space, exactly the way
    _create_control_for originally built them.

    Nested Temporal Controls are skipped (real-parented, no space concept
    -- see _parent_nested_control), and so are muted ones (nothing to
    re-space until they're driving something again)."""
    controls = [
        control for control in _controls_to_process()
        if _nested_parent_for(control) is None and not TkmSceneNode(control).get_attr(MUTED_ATTR)
    ]
    if not controls:
        return wutil.make_inViewMessage("No Temporal Controls to switch")

    switched = []
    for control in controls:
        target = _target_for(control)
        if not target:
            continue
        restore_map = _restore_map_for(control)
        _delete_driver_nodes(control)

        driver_nodes = {}
        translate_channels = [channel for channel in TRANSLATE_CHANNELS if channel in restore_map]
        rotate_channels = [channel for channel in ROTATE_CHANNELS if channel in restore_map]
        scale_channels = [channel for channel in SCALE_CHANNELS if channel in restore_map]

        if translate_channels:
            driver_nodes["translate"] = _drive_group(control, target, translate_channels, space_id, restore_map)
        if rotate_channels:
            driver_nodes["rotate"] = _drive_group(control, target, rotate_channels, space_id, restore_map)
        # Scale connection is temporarily disabled -- see _create_control_for.
        del scale_channels

        node = TkmSceneNode(control)
        node.set_attr(DRIVER_NODES_ATTR, json.dumps(driver_nodes))
        # This right-click menu action always sets Position and Orientation
        # together -- the panel's set_control_space is the one that can move
        # them independently.
        node.set_attr(POSITION_SPACE_ATTR, space_id)
        node.set_attr(ORIENTATION_SPACE_ATTR, space_id)
        switched.append(control)

    if switched:
        cmds.select(switched)
        return switched
    return wutil.make_inViewMessage("Nothing to switch")


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


def set_control_space(control, group_kind, space_id):
    """Re-drive just control's *group_kind* channel group ("translate" or
    "rotate") through *space_id*, leaving the other group's driving alone --
    the Temp Controls Panel's Position/Orientation columns can be set
    independently, unlike the right-click menu's switch_controls_space,
    which always moves both together. When Position changes and the panel's
    lock is on, Orientation is re-driven to follow automatically.

    Skips nested Temporal Controls (real-parented, no space concept) and
    muted ones (nothing to re-space until they're driving something again)
    the same way switch_controls_space does. Returns True if anything
    changed."""
    if not cmds.objExists(control):
        return False
    if _nested_parent_for(control) is not None or TkmSceneNode(control).get_attr(MUTED_ATTR):
        return False
    target = _target_for(control)
    if not target:
        return False

    restore_map = _restore_map_for(control)
    channels = TRANSLATE_CHANNELS if group_kind == "translate" else ROTATE_CHANNELS
    relevant = [channel for channel in channels if channel in restore_map]
    if not relevant:
        return False

    _delete_driver_nodes_for_group(control, group_kind)
    new_nodes = _drive_group(control, target, relevant, space_id, restore_map)

    nodes_map = _driver_nodes_map_for(control)
    nodes_map[group_kind] = new_nodes
    node = TkmSceneNode(control)
    node.set_attr(DRIVER_NODES_ATTR, json.dumps(nodes_map))
    node.set_attr(POSITION_SPACE_ATTR if group_kind == "translate" else ORIENTATION_SPACE_ATTR, space_id)

    if group_kind == "translate" and node.get_attr(LOCK_SPACE_ATTR):
        set_control_space(control, "rotate", space_id)
    return True


# ----------------------------------------------------------------------
# Temp Controls Panel: rig list, add/remove control, pivot
# ----------------------------------------------------------------------
# A "rig" here is one target object plus every Temporal Control that traces
# back to it -- its original creation-dialog control, and anything layered
# on top afterward through Add Child/Add Parent below. The panel's left
# list shows one row per rig; its right list shows that rig's controls.

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
    parent -- reuses the normal nested-control creation path
    (create_controls_with_options -> _parent_nested_control fires because
    *control* is itself a Temporal Control) by targeting control itself,
    then flags the result EXTRA_ATTR so the panel's Remove Control action
    is allowed to delete it later, unlike a System's original main control.
    The mirror of add_child_control below."""
    if not cmds.objExists(control):
        return None
    new_controls = create_controls_with_options([control])
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
    -- the mirror of add_parent_control. Unlike a normal Temporal Control,
    this one doesn't drive an external object (TARGET_ATTR is left ""):
    it's a free, hand-key-able control layered under parent_control, purely
    local, flagged EXTRA_ATTR the same way add_parent_control's result is."""
    if not cmds.objExists(parent_control):
        return None
    radius = max(_control_base_radius(parent_control) * get_control_size_mult(parent_control) * 0.6, 0.5)
    short_name = parent_control.split("|")[-1].split(":")[-1]
    child_control = shapes.build(shapes.DEFAULT_SHAPE, "{}_temporalChild#".format(short_name), radius)
    cmds.matchTransform(child_control, parent_control, position=True, rotation=True, scale=False)
    cmds.parent(child_control, parent_control)

    _tag_control(child_control, None, child_control)
    node = TkmSceneNode(child_control)
    node.set_attr(EXTRA_ATTR, True, attributeType="bool")
    cmds.setAttr(_plug(child_control, EXTRA_ATTR), lock=True)

    cmds.select(child_control)
    return child_control


def remove_extra_control(control):
    """Remove a control the panel itself added on top of a System's main
    control (Add Child/Add Parent, EXTRA_ATTR) -- an "extra" control, not a
    System's main control, which Remove and Bake/Revert exist for instead
    and which this refuses to touch."""
    if not cmds.objExists(control) or not _is_temporal_control(control):
        return wutil.make_inViewMessage("Not a Temporal Control")
    if not TkmSceneNode(control).get_attr(EXTRA_ATTR):
        return wutil.make_inViewMessage("Can't remove a System's main control here -- use Remove and Bake/Revert")

    target = _target_for(control)
    nested_parent = _nested_parent_for(control)
    _delete_driver_nodes(control)
    if target and nested_parent is not None:
        _restore_nested_parent(target, nested_parent)

    # Any Temporal Control further stacked on top of this one (another Add
    # Child/Add Parent, or a nested Temporal Control) needs to be released
    # to world *before* this one is deleted, or it would get deleted along
    # with it -- Bake/Revert's own nested-control handling has the same
    # concern, just one level removed.
    for child in cmds.listRelatives(control, children=True, type="transform", fullPath=True) or []:
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
    control is selected, or whose *target* (the original object it drives)
    is selected -- so Bake/Revert work from either end, control or object.

    Falls back to every Temporal Control in the scene only when nothing at
    all is selected. Selecting something that isn't a Temporal Control or
    a Temporal Control's target means "nothing relevant is selected", not
    "process everything" -- picking up unrelated controls just because an
    unrelated object was selected was the bug behind reverting/baking
    something the user never selected."""
    all_controls = cmds.ls("*." + TAG_ATTR, objectsOnly=True) or []
    if not all_controls:
        return []

    selected = selection.get_selected_objects(long=True)
    if not selected:
        return all_controls

    selected = set(selected)
    picked = []
    for control in all_controls:
        control_long = cmds.ls(control, long=True)[0]
        if control_long in selected:
            picked.append(control)
            continue
        # _target_for already returns a full path -- it's stored that way by
        # _tag_control (cmds.ls(obj, long=True)[0]) -- so no need to
        # re-normalize it through another cmds.ls round-trip here.
        target = _target_for(control)
        if target and target in selected:
            picked.append(control)
    return picked


def _target_for(control):
    target = TkmSceneNode(control).get_attr(TARGET_ATTR)
    return target if target and cmds.objExists(target) else None


def _is_temporal_control(node):
    return TkmSceneNode(node).get_attr(TAG_ATTR) is not None


def _parent_nested_control(control, obj):
    """Make *control* a real Maya parent of *obj* instead of driving it
    through a constraint -- used only when *obj* is itself another Temporal
    Control's control (nesting one Temporal Control inside another). obj is
    one of this tool's own nodes either way, so restructuring its hierarchy
    is safe -- nothing outside this tool references it -- and it means the
    nested control keeps moving/keying like any ordinary child transform:
    no expression, no constraint, no connection at all for Bake/Revert to
    unwind, just real parenting. Records obj's previous parent (possibly
    none, i.e. world) so Bake/Revert can hand it back later."""
    original_parent = cmds.listRelatives(obj, parent=True, fullPath=True) or []
    TkmSceneNode(control).set_attr(NESTED_PARENT_ATTR, original_parent[0] if original_parent else "")
    cmds.setAttr(_plug(control, NESTED_PARENT_ATTR), lock=True)
    cmds.parent(obj, control)


def _nested_parent_for(control):
    """The parent *control*'s target should return to on Bake/Revert, or
    ``None`` if *control* isn't a nested-control parent -- i.e. it was
    built through the normal channel-driving path in
    ``_create_control_for`` rather than ``_parent_nested_control``.
    ``TkmSceneNode.get_attr``'s ``None`` default already draws exactly that
    line: unset means "not nested", while "" (a control that was at world)
    is a legitimate, distinct answer."""
    return TkmSceneNode(control).get_attr(NESTED_PARENT_ATTR)


def _restore_nested_parent(obj, original_parent):
    if not cmds.objExists(obj):
        return
    if original_parent and cmds.objExists(original_parent):
        cmds.parent(obj, original_parent)
    elif cmds.listRelatives(obj, parent=True, fullPath=True):
        cmds.parent(obj, world=True)


def _existing_control_for(obj):
    long_obj = cmds.ls(obj, long=True)[0]
    for control in cmds.ls("*." + TAG_ATTR, objectsOnly=True) or []:
        # target is already a full path -- see the matching note in
        # _controls_to_process.
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


def _driver_nodes_map_for(control):
    """DRIVER_NODES_ATTR as ``{"translate": [...], "rotate": [...], "scale":
    [...]}`` -- per-group, so the Temp Controls Panel can tear down and
    rebuild just Position or just Orientation (set_control_space) without
    touching the other's driver nodes. A control saved before this grouping
    existed stored a flat list instead -- read back under a "legacy" key so
    _driver_nodes_for's full teardown still finds it, even though per-group
    switching won't (it just rebuilds that group fresh, same as a normal
    space switch)."""
    raw = TkmSceneNode(control).get_attr(DRIVER_NODES_ATTR)
    if not raw:
        return {}
    try:
        data = json.loads(raw)
    except (TypeError, ValueError):
        return {}
    if isinstance(data, list):
        return {"legacy": [node for node in data if node and cmds.objExists(node)]}
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


def _delete_driver_nodes_for_group(control, group_kind):
    """Delete and forget just *group_kind*'s ("translate"/"rotate") driver
    nodes, leaving the other groups' driving intact -- the per-group
    counterpart to _delete_driver_nodes' full teardown."""
    nodes_map = _driver_nodes_map_for(control)
    nodes = nodes_map.pop(group_kind, [])
    existing = [node for node in nodes if cmds.objExists(node)]
    if existing:
        cmds.delete(existing)
    TkmSceneNode(control).set_attr(DRIVER_NODES_ATTR, json.dumps(nodes_map))


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
    deleting the buffer cascades to the control and any helper it parents)."""
    stored = TkmSceneNode(control).get_attr(DELETE_ROOT_ATTR)
    delete_root = stored if stored and cmds.objExists(stored) else control
    if cmds.objExists(delete_root):
        cmds.delete(delete_root)
    elif cmds.objExists(control):
        cmds.delete(control)


# ----------------------------------------------------------------------
# Right-click context menu
# ----------------------------------------------------------------------

def build_temporal_controls_context_menu(menu, source_widget=None):
    """Right-click menu for the Temporal Controls toolbar button.

    Wired in through ``__init__.py``'s TOOLS entry as a callable ``"menu"``
    rather than the declarative dict every other section item uses (see
    ``ui/widgets/customWidgets.QFlatToolButton.attach_menu`` and
    ``ui/widgets/toolbar_widgets.add_graph_tool_item``'s own callable-menu
    override for the same pattern elsewhere) -- this menu needs an
    exclusive Bake Mode group, a standalone Lightning Mode checkbox, and a
    live Space-switch list, none of which the declarative "items" list of
    plain command ids can express.
    """
    _add_bake_mode_actions(menu)
    menu.addSeparator()
    _add_space_switch_actions(menu)
    menu.addSeparator()
    # Everything below actually edits the scene, unlike the settings toggles
    # above -- left un-marked so it goes through the normal undo-chunk/
    # progress handling ``mark_non_tool_action`` exists to skip, the same as
    # the existing Bake/Revert tool entries always have.
    menu.addAction(
        QtGui.QIcon(icons.eraser), "Mute and Revert",
        callback=mute_and_revert,
        description=(
            "Disconnect the selected Temporal Controls and restore their "
            "objects, but keep the controls in the scene to drive again later."
        ),
    )
    menu.addAction(
        QtGui.QIcon(icons.eraser), "Mute and Bake",
        callback=mute_and_bake,
        description=(
            "Disconnect the selected Temporal Controls, leaving their "
            "objects wherever the drive left them, but keep the controls "
            "in the scene to drive again later."
        ),
    )
    menu.addAction(
        QtGui.QIcon(icons.refresh), "Remove and Revert",
        callback=revert_controls,
        description="Remove the selected Temporal Controls and restore their objects completely.",
    )
    menu.addAction(
        QtGui.QIcon(icons.bake_animation_1), "Remove and Bake",
        callback=bake_controls,
        description="Extract the selected Temporal Controls' animation onto their objects and remove the controls.",
    )
    menu.addSeparator()
    menu.addAction(
        QtGui.QIcon(icons.temporal_controls), "Temp Controls Panel",
        callback=open_temp_controls_panel,
        description="Browse and manage every Temporal Control in the scene.",
    )
    return menu


def _add_bake_mode_actions(menu):
    current_mode = get_bake_mode()
    group = QtGui.QActionGroup(menu)
    group.setExclusive(True)
    for mode in BAKE_MODES:
        description = (
            "Bake copies only the control's existing keyframes onto its object."
            if mode["id"] == "keys" else
            "Bake samples every frame across the control's animated range onto its object."
        )
        action = menu.addAction(
            mode["label"],
            callback=toolCommon.mark_non_tool_action(partial(_set_bake_mode, mode_id=mode["id"])),
            description=description,
            open=True,
        )
        action.setCheckable(True)
        action.setChecked(mode["id"] == current_mode)
        group.addAction(action)

    lightning_action = menu.addAction(
        "Lightning Mode",
        callback=toolCommon.mark_non_tool_action(_set_lightning_mode),
        description=(
            "Speed up baking with Maya's faster math-based bake shortcut "
            "instead of evaluating the scene at every frame. Affects both "
            "Bake Frames and Bake Keys."
        ),
        open=True,
    )
    lightning_action.setCheckable(True)
    lightning_action.setChecked(is_lightning_mode_enabled())


def _set_bake_mode(checked, mode_id):
    # Checkable actions in an exclusive QActionGroup both re-emit their
    # toggle when the selection changes -- only act on the one being turned on.
    if checked:
        set_bake_mode(mode_id)


def _set_lightning_mode(checked):
    set_lightning_mode_enabled(checked)


def _add_space_switch_actions(menu):
    for space in SWITCHABLE_SPACES:
        menu.addAction(
            space["label"],
            callback=partial(switch_controls_space, space["id"]),
            description=(
                "Re-drive the selected Temporal Controls through {} instead "
                "of tearing them down and recreating them."
            ).format(space["label"]),
        )
