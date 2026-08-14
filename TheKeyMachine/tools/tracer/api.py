"""Tracer creation, display presets, and responsive auto refresh."""

import threading
import time
import re
from functools import partial

from maya import cmds
from maya.api import OpenMaya as om

from TheKeyMachine.core.Qt import QtCore  # type: ignore
from TheKeyMachine.core import runtime
from TheKeyMachine.maya import selection
import TheKeyMachine.ui.widgets.util as wutil
from TheKeyMachine.maya.runtime import TkmSceneNode
from TheKeyMachine.data import icons


TRACER_NODE = "tracer"
TRACER_HANDLE = "tracerHandle"
TRACER_SHAPE = "tracerHandleShape"
TRACER_GROUP = "Tracer"
TRACER_FOLLOW = "Tracer_Follow"
TRACER_OFFSET = "Tracer_Offset"
TRACER_CONSTRAINT = "Tracer_parentConstraint"
TRACERS_GROUP = "Tracers"
_TRACER_GROUP_ATTR = "tkmTracerGroup"

_STYLE_OPTION = "TKM_TracerStyle"
_SIZE_OPTION = "TKM_TracerSize"
_COLOR_OPTION = "TKM_TracerColor"
_RANGE_OPTION = "TKM_TracerRange"
_PERFORMANCE_OPTION = "TKM_TracerPerformance"
_AUTO_UPDATE_OPTION = "TKM_TracerAutoUpdate"
_FALLOFF_OPTION = "TKM_TracerFalloff"
_XRAY_OPTION = "TKM_TracerXray"
_DIRECTION_OPTION = "TKM_TracerDirection"
_ACTIVE_TRACER_OPTION = "TKM_ActiveTracer"
_CALLBACK_KEY = "tracer:auto_update"

# Deliberately process-local: offsets survive tracer removal/recreation during
# this Maya session without becoming a permanent preference or scene setting.
_SESSION_OFFSETS = {}


# These change how the tracer is drawn, rather than merely recoloring it.
STYLE_PRESETS = {
    "clean": {
        "label": "Clean",
        "description": "A clear path with compact key markers.",
        "attrs": {
            "trailDrawMode": 0,
            "showKeyframes": True,
            "showExtraKeys": False,
            "showFrameMarkers": False,
            "showFrameMarkerFrames": False,
            "xrayDraw": True,
        },
    },
    "timing": {
        "label": "Timing",
        "description": "Show spacing and timing changes along the path.",
        "attrs": {
            "trailDrawMode": 1,
            "showKeyframes": True,
            "showExtraKeys": False,
            "showFrameMarkers": False,
            "showFrameMarkerFrames": False,
            "xrayDraw": True,
        },
    },
    "frames": {
        "label": "Frame Dots",
        "description": "Emphasize sampled frames with dots along a light path.",
        "attrs": {
            "trailDrawMode": 0,
            "showKeyframes": False,
            "showExtraKeys": False,
            "showFrameMarkers": True,
            "showFrameMarkerFrames": False,
            "xrayDraw": True,
        },
    },
    "bold": {
        "label": "Key Focus",
        "description": "Emphasize translation and extra animation keys.",
        "attrs": {
            "trailDrawMode": 0,
            "showKeyframes": True,
            "showExtraKeys": True,
            "showFrameMarkers": False,
            "showFrameMarkerFrames": False,
            "xrayDraw": True,
        },
    },
    "current": {
        "label": "Current Frame",
        "description": "Focus the display around the current frame.",
        "attrs": {
            "trailDrawMode": 2,
            "showKeyframes": True,
            "showExtraKeys": False,
            "showFrameMarkers": False,
            "showFrameMarkerFrames": False,
            "fadeInoutFrames": 12,
            "xrayDraw": True,
        },
    },
}
STYLE_ORDER = ("clean", "timing", "frames", "bold", "current")

COLOR_PRESETS = {
    "grey": ((0.2879, 0.2932, 0.358), (0.122, 0.122, 0.122)),
    "red": ((0.8143, 0.5109, 0.5318), (0.4398, 0.1724, 0.1908)),
    "blue": ((0.1615, 0.1766, 0.3581), (0.2879, 0.2932, 0.358)),
}

RANGE_VALUES = (6, 12, 24, 48, 0)

SIZE_PRESETS = {
    "fine": {"label": "Fine", "thickness": 1, "key_size": 1, "frame_size": 1},
    "regular": {"label": "Regular", "thickness": 2, "key_size": 1, "frame_size": 1},
    "large": {"label": "Large", "thickness": 4, "key_size": 2, "frame_size": 2},
}
SIZE_ORDER = ("fine", "regular", "large")

DIRECTION_PRESETS = {
    "before": {"label": "Before Current Frame", "value": 0},
    "all": {"label": "All Directions", "value": 1},
    "after": {"label": "After Current Frame", "value": 2},
}
DIRECTION_ORDER = ("before", "all", "after")

# A refresh is progressively refined.  The interaction-biased profile waits
# until the animator has settled, then deliberately stops at a coarser sample.
PERFORMANCE_PROFILES = {
    "update": {
        "label": "Faster Update",
        "description": "Refresh quickly at full frame accuracy.",
        "debounce_ms": 45,
        "increments": (1,),
        "pass_gap_ms": 0,
    },
    "balanced": {
        "label": "Balanced",
        "description": "Show a coarse result first, then refine it.",
        "debounce_ms": 180,
        "increments": (3, 1),
        "pass_gap_ms": 70,
    },
    "interaction": {
        "label": "Faster Interaction",
        "description": "Wait longer and keep fewer samples in heavy scenes.",
        "debounce_ms": 650,
        "increments": (8, 4),
        "pass_gap_ms": 140,
    },
}
PERFORMANCE_ORDER = ("update", "balanced", "interaction")


def _option_value(name, default):
    try:
        if cmds.optionVar(exists=name):
            return cmds.optionVar(query=name)
    except (RuntimeError, TypeError, ValueError, AttributeError):
        pass
    return default


def _set_option(name, value):
    try:
        if isinstance(value, bool):
            cmds.optionVar(integerValue=(name, int(value)))
        elif isinstance(value, int):
            cmds.optionVar(integerValue=(name, value))
        else:
            cmds.optionVar(stringValue=(name, str(value)))
    except (RuntimeError, TypeError, ValueError, AttributeError):
        pass


def _stored_tracer_group(node_name):
    plug = "{}.{}".format(node_name, _TRACER_GROUP_ATTR)
    try:
        if cmds.objExists(plug):
            value = cmds.getAttr(plug)
            if value:
                return str(value)
    except (RuntimeError, TypeError, ValueError, AttributeError):
        pass
    return None


def _set_active_names(node_name, group_name=None):
    global TRACER_NODE, TRACER_HANDLE, TRACER_SHAPE
    global TRACER_GROUP, TRACER_FOLLOW, TRACER_OFFSET
    global TRACER_CONSTRAINT
    node_name = str(node_name or "tracer")
    suffix = node_name[len("tracer"):] if node_name.startswith("tracer") else ""
    group_name = group_name or _stored_tracer_group(node_name) or "Tracer{}".format(suffix)
    TRACER_NODE = node_name
    TRACER_HANDLE = "{}Handle".format(node_name)
    TRACER_SHAPE = "{}Shape".format(TRACER_HANDLE)
    TRACER_GROUP = group_name
    TRACER_FOLLOW = "{}_Follow".format(group_name)
    TRACER_OFFSET = "{}_Offset".format(group_name)
    TRACER_CONSTRAINT = "{}_parentConstraint".format(group_name)
    _set_option(_ACTIVE_TRACER_OPTION, node_name)


def _tracer_names():
    try:
        candidates = cmds.ls("tracer*") or []
    except (RuntimeError, TypeError, ValueError, AttributeError):
        candidates = []
    result = []
    for candidate in candidates:
        handle_shape = "{}HandleShape".format(candidate)
        if cmds.objExists("{}.points".format(candidate)) and cmds.objExists(handle_shape):
            if candidate not in result:
                result.append(candidate)
    return result


def _sync_active_names():
    requested = str(_option_value(_ACTIVE_TRACER_OPTION, TRACER_NODE))
    if cmds.objExists(requested) and cmds.objExists("{}HandleShape".format(requested)):
        _set_active_names(requested)
        return requested
    names = _tracer_names()
    _set_active_names(names[-1] if names else "tracer")
    return names[-1] if names else None


def _has_tracer():
    return bool(_sync_active_names())


def has_any_tracer():
    return bool(_tracer_names())


def _publish_tracer_state():
    state = has_any_tracer()
    try:
        runtime.get_runtime_manager().set_control_state("create_tracer", state)
    except (RuntimeError, TypeError, ValueError, AttributeError):
        pass
    return state


def _next_tracer_name():
    if not cmds.objExists("tracer"):
        return "tracer"
    index = 2
    while cmds.objExists("tracer{}".format(index)):
        index += 1
    return "tracer{}".format(index)


def _object_tracer_group_name(source_object):
    leaf_name = str(source_object).rsplit("|", 1)[-1].rsplit(":", 1)[-1]
    object_name = re.sub(r"[^A-Za-z0-9_]+", "_", leaf_name).strip("_") or "Object"
    base_name = "{}_Tracer".format(object_name)
    if not cmds.objExists(base_name):
        return base_name
    index = 2
    while cmds.objExists("{}{}".format(base_name, index)):
        index += 1
    return "{}{}".format(base_name, index)


def _offset_session_key(source_object):
    """Use the object's DAG leaf name, including its namespace."""
    return str(source_object).rsplit("|", 1)[-1]


def _remember_offset(source_object, offset_node):
    if not source_object or not cmds.objExists(offset_node):
        return
    try:
        _SESSION_OFFSETS[_offset_session_key(source_object)] = {
            "translate": tuple(cmds.getAttr("{}.translate".format(offset_node))[0]),
            "rotate": tuple(cmds.getAttr("{}.rotate".format(offset_node))[0]),
        }
    except (RuntimeError, TypeError, ValueError, AttributeError, IndexError):
        pass


def _restore_offset(source_object, offset_node):
    values = _SESSION_OFFSETS.get(_offset_session_key(source_object))
    if not values or not cmds.objExists(offset_node):
        return False
    try:
        cmds.setAttr("{}.translate".format(offset_node), *values["translate"])
        cmds.setAttr("{}.rotate".format(offset_node), *values["rotate"])
        return True
    except (RuntimeError, TypeError, ValueError, AttributeError, KeyError):
        return False


def _configure_offset_channels(offset_node):
    """Expose editable, non-keyable translation/rotation only."""
    visible_channels = (
        "translateX", "translateY", "translateZ",
        "rotateX", "rotateY", "rotateZ",
    )
    hidden_channels = (
        "scaleX", "scaleY", "scaleZ",
        "visibility", "rotateOrder",
        "shearXY", "shearXZ", "shearYZ",
    )
    for attr_name in visible_channels:
        plug = "{}.{}".format(offset_node, attr_name)
        try:
            cmds.setAttr(plug, lock=False)
            cmds.setAttr(plug, keyable=False)
            cmds.setAttr(plug, channelBox=True)
        except (RuntimeError, TypeError, ValueError, AttributeError):
            pass
    for attr_name in hidden_channels:
        plug = "{}.{}".format(offset_node, attr_name)
        try:
            cmds.setAttr(plug, keyable=False)
            cmds.setAttr(plug, channelBox=False)
            cmds.setAttr(plug, lock=True)
        except (RuntimeError, TypeError, ValueError, AttributeError):
            pass


def _remember_tracer_offset(node_name):
    sources = _tracer_sources_for(node_name)
    group_name = _stored_tracer_group(node_name)
    if sources and group_name:
        _remember_offset(sources[0], "{}_Offset".format(group_name))


def _store_tracer_group(node_name, group_name):
    try:
        if not cmds.attributeQuery(_TRACER_GROUP_ATTR, node=node_name, exists=True):
            cmds.addAttr(node_name, longName=_TRACER_GROUP_ATTR, dataType="string")
        cmds.setAttr(
            "{}.{}".format(node_name, _TRACER_GROUP_ATTR),
            group_name,
            type="string",
        )
    except (RuntimeError, TypeError, ValueError, AttributeError):
        pass


def _set_asset_black_box(node_name):
    try:
        if cmds.objExists("{}.blackBox".format(node_name)):
            cmds.setAttr("{}.blackBox".format(node_name), True)
    except (RuntimeError, TypeError, ValueError, AttributeError):
        pass


def _make_tracer_unselectable():
    """Reference-display the native DAG nodes so viewport clicks ignore them."""
    for node_name in (TRACER_HANDLE, TRACER_SHAPE):
        try:
            if cmds.objExists("{}.overrideEnabled".format(node_name)):
                cmds.setAttr("{}.overrideEnabled".format(node_name), True)
                cmds.setAttr("{}.overrideDisplayType".format(node_name), 2)
        except (RuntimeError, TypeError, ValueError, AttributeError):
            pass


def _connect_tracer_follow(source_object):
    """Track source world translation and rotation on the follow branch."""
    if cmds.objExists(TRACER_CONSTRAINT):
        cmds.delete(TRACER_CONSTRAINT)
    constraints = cmds.parentConstraint(
        source_object,
        TRACER_FOLLOW,
        maintainOffset=False,
        name=TRACER_CONSTRAINT,
    ) or []
    return constraints[0] if constraints else None


def _connect_offset_to_tracer():
    """Sample the offset point through the source animation over time."""
    cmds.connectAttr(
        "{}.translate".format(TRACER_OFFSET),
        "{}.localPosition".format(TRACER_NODE),
        force=True,
    )

    # Keep non-DAG support nodes inside the black-boxed tracer asset as well.
    try:
        support_nodes = [
            node_name
            for node_name in (TRACER_NODE, TRACER_CONSTRAINT)
            if cmds.objExists(node_name)
        ]
        cmds.container(
            TRACER_GROUP,
            edit=True,
            addNode=support_nodes,
            force=True,
        )
    except (RuntimeError, TypeError, ValueError, AttributeError):
        pass


def _set_shape_attr(name, value):
    plug = "{}.{}".format(TRACER_SHAPE, name)
    try:
        if cmds.objExists(plug):
            cmds.setAttr(plug, value)
    except (RuntimeError, TypeError, ValueError, AttributeError):
        pass


def _set_shape_attr_for(node_name, name, value):
    plug = "{}HandleShape.{}".format(node_name, name)
    try:
        if cmds.objExists(plug):
            cmds.setAttr(plug, value)
    except (RuntimeError, TypeError, ValueError, AttributeError):
        pass


def _set_shape_attr_globally(name, value):
    for node_name in _tracer_names():
        _set_shape_attr_for(node_name, name, value)


def create_tracer(*_args):
    selected_objects = selection.get_selected_objects()
    if len(selected_objects) != 1:
        return wutil.make_inViewMessage("Select only one object")

    if has_any_tracer():
        return None
    return _build_tracer(
        selected_objects[0],
        base_name="tracer",
        group_name=_object_tracer_group_name(selected_objects[0]),
        replace=False,
    )


def create_additional_tracer(*_args):
    selected_objects = selection.get_selected_objects()
    if len(selected_objects) != 1:
        return wutil.make_inViewMessage("Select one object for the new tracer")
    return _build_tracer(
        selected_objects[0],
        base_name=_next_tracer_name(),
        group_name=_object_tracer_group_name(selected_objects[0]),
        replace=False,
    )


def set_tracer_enabled(enabled=False, *_args):
    if bool(enabled):
        return create_tracer()
    return remove_tracer()


def _build_tracer(
    source_object,
    anchor_transform=None,
    base_name=None,
    group_name=None,
    replace=True,
):
    """Build the native Maya tracer, optionally relative to an anchor."""

    if base_name is None:
        _sync_active_names()
        base_name = TRACER_NODE
        group_name = group_name or TRACER_GROUP
    group_name = group_name or _object_tracer_group_name(source_object)
    _set_active_names(base_name, group_name=group_name)
    if replace:
        _remember_offset(source_object, TRACER_OFFSET)
        if cmds.objExists(TRACER_GROUP):
            cmds.delete(TRACER_GROUP)
        if cmds.objExists(TRACER_HANDLE):
            cmds.delete(TRACER_HANDLE)
        if cmds.objExists(TRACER_NODE):
            cmds.delete(TRACER_NODE)
        if cmds.objExists(TRACER_CONSTRAINT):
            cmds.delete(TRACER_CONSTRAINT)

    tracers_node = TkmSceneNode.root().child(
        TRACERS_GROUP,
        icon=icons.tracer,
        lock_transform=True,
    )
    tracer_node = tracers_node.child(TRACER_GROUP, icon=icons.tracer)
    follow_node = tracer_node.child(TRACER_FOLLOW)
    follow_node.child(TRACER_OFFSET)
    _connect_tracer_follow(source_object)
    _restore_offset(source_object, TRACER_OFFSET)
    _configure_offset_channels(TRACER_OFFSET)
    cmds.select(source_object, replace=True)

    start_frame = cmds.playbackOptions(query=True, minTime=True)
    end_frame = cmds.playbackOptions(query=True, maxTime=True)
    snapshot_options = dict(
        name=TRACER_NODE,
        motionTrail=True,
        constructionHistory=True,
        startTime=start_frame,
        endTime=end_frame,
        increment=1,
        update="demand",
    )
    if anchor_transform:
        snapshot_options["anchorTransform"] = anchor_transform
    cmds.snapshot(source_object, **snapshot_options)
    _store_tracer_group(TRACER_NODE, TRACER_GROUP)
    apply_tracer_style(get_tracer_style())
    set_tracer_size(get_tracer_size())
    set_tracer_color(get_tracer_color())
    set_tracer_range(get_tracer_range())
    set_transparency_falloff(has_transparency_falloff())
    set_xray(is_xray_enabled())
    set_tracer_direction(get_tracer_direction())
    if is_physically_connected():
        cmds.disconnectAttr("{}.points".format(TRACER_NODE), "{}.points".format(TRACER_SHAPE))
    # The rendered motion tracer is a sibling of the tracking branch.  It
    # must not inherit the source object's world motion through Offset.
    cmds.parent(TRACER_HANDLE, TRACER_GROUP)
    _connect_offset_to_tracer()
    _make_tracer_unselectable()
    _set_asset_black_box(TRACER_GROUP)
    cmds.select(source_object, replace=True)
    if bool(_option_value(_AUTO_UPDATE_OPTION, True)):
        controller = get_controller()
        controller.enable()
        controller.request_refresh(immediate=True)
    _publish_tracer_state()


def _tracer_sources_for(node_name):
    if not cmds.objExists("{}.snapshotObject".format(node_name)):
        return []
    try:
        return cmds.listConnections(
            "{}.snapshotObject".format(node_name),
            source=True,
            destination=False,
        ) or []
    except (RuntimeError, TypeError, ValueError, AttributeError):
        return []


def _tracer_source():
    _sync_active_names()
    connections = _tracer_sources_for(TRACER_NODE)
    return connections[0] if connections else None


def _tracer_anchor():
    _sync_active_names()
    if not cmds.objExists("{}.anchorTransform".format(TRACER_NODE)):
        return None
    try:
        connections = cmds.listConnections(
            "{}.anchorTransform".format(TRACER_NODE),
            source=True,
            destination=False,
        ) or []
    except (RuntimeError, TypeError, ValueError, AttributeError):
        return None
    return connections[0] if connections else None


def set_world_space(*_args):
    source_object = _tracer_source()
    if not source_object:
        return wutil.make_inViewMessage("No tracer node in the scene")
    return _build_tracer(source_object)


def set_camera_space(*_args):
    source_object = _tracer_source()
    if not source_object:
        return wutil.make_inViewMessage("No tracer node in the scene")
    try:
        panel = cmds.getPanel(withFocus=True)
        if not panel or cmds.getPanel(typeOf=panel) != "modelPanel":
            return wutil.make_inViewMessage("Focus a viewport to use its camera")
        camera = cmds.modelPanel(panel, query=True, camera=True)
        if cmds.nodeType(camera) == "camera":
            parents = cmds.listRelatives(camera, parent=True, fullPath=True) or []
            camera = parents[0] if parents else camera
    except (RuntimeError, TypeError, ValueError, AttributeError):
        return wutil.make_inViewMessage("Could not resolve the active viewport camera")
    return _build_tracer(source_object, anchor_transform=camera)


def set_relative_space(*_args):
    source_object = _tracer_source()
    if not source_object:
        return wutil.make_inViewMessage("No tracer node in the scene")
    anchors = [node for node in selection.get_selected_objects() if node != source_object]
    if len(anchors) != 1:
        return wutil.make_inViewMessage("Select one object to use as the relative-space anchor")
    return _build_tracer(source_object, anchor_transform=anchors[0])


def get_tracer_space():
    anchor = _tracer_anchor()
    if not anchor:
        return "World"
    try:
        shapes = cmds.listRelatives(anchor, shapes=True, fullPath=True) or []
        if any(cmds.nodeType(shape) == "camera" for shape in shapes):
            return "Camera"
    except (RuntimeError, TypeError, ValueError, AttributeError):
        pass
    return "Relative"


def select_tracer_offset_node(*_args):
    _sync_active_names()
    if cmds.objExists(TRACER_OFFSET):
        _configure_offset_channels(TRACER_OFFSET)
        cmds.select(TRACER_OFFSET, replace=True)


def _select_tracer_offset(node_name, *_args):
    _set_active_names(node_name)
    if cmds.objExists(TRACER_OFFSET):
        _configure_offset_channels(TRACER_OFFSET)
        cmds.select(TRACER_OFFSET, replace=True)


def populate_tracer_offsets_menu(menu, *_args):
    """Rebuild the Offset submenu from every managed tracer in the scene."""
    menu.clear()
    tracer_names = _tracer_names()
    if not tracer_names:
        action = menu.addAction("No Tracers")
        action.setEnabled(False)
        return menu

    for node_name in tracer_names:
        group_name = _stored_tracer_group(node_name) or node_name
        menu.addAction(
            group_name,
            callback=partial(_select_tracer_offset, node_name),
            description="Select {}'s offset object.".format(group_name),
        )
    return menu


def remove_tracer(*_args):
    cleanup()
    for node_name in reversed(_tracer_names()):
        _set_active_names(node_name)
        _remember_tracer_offset(node_name)
        if cmds.objExists(TRACER_GROUP):
            cmds.delete(TRACER_GROUP)
        elif cmds.objExists(TRACER_HANDLE):
            cmds.delete(TRACER_HANDLE)
        if cmds.objExists(TRACER_NODE):
            cmds.delete(TRACER_NODE)
        if cmds.objExists(TRACER_CONSTRAINT):
            cmds.delete(TRACER_CONSTRAINT)
    if cmds.objExists(TRACERS_GROUP):
        cmds.delete(TRACERS_GROUP)
    _set_active_names("tracer")
    _publish_tracer_state()


def is_physically_connected():
    _sync_active_names()
    return bool(
        cmds.objExists(TRACER_NODE)
        and cmds.objExists(TRACER_SHAPE)
        and cmds.isConnected(
            "{}.points".format(TRACER_NODE),
            "{}.points".format(TRACER_SHAPE),
        )
    )


def is_connected():
    """Return the auto-update state (and migrate the old live connection)."""
    enabled = bool(_option_value(_AUTO_UPDATE_OPTION, True))
    if has_any_tracer() and is_physically_connected():
        enabled = True
        _set_option(_AUTO_UPDATE_OPTION, True)
        cmds.disconnectAttr(
            "{}.points".format(TRACER_NODE),
            "{}.points".format(TRACER_SHAPE),
        )
    if enabled and _has_tracer():
        get_controller().enable()
    return enabled


def set_connected(connected=False, update_cb=None, *_args):
    connected = bool(connected)
    _set_option(_AUTO_UPDATE_OPTION, connected)

    if not _has_tracer():
        controller = get_controller(create=False)
        if controller is not None and not connected:
            controller.disable()
        if update_cb:
            update_cb(connected)
        return connected

    # Legacy versions left the expensive points connection live.  The new
    # controller connects only for each scheduled refresh pass.
    if is_physically_connected():
        cmds.disconnectAttr("{}.points".format(TRACER_NODE), "{}.points".format(TRACER_SHAPE))

    controller = get_controller() if connected else get_controller(create=False)
    if controller is not None:
        if connected:
            controller.enable()
            controller.request_refresh(immediate=True)
        else:
            controller.disable()
    if update_cb:
        update_cb(connected)


def _refresh_pass(increment=1):
    """Recompute one sampling pass; must be called on Maya's main thread."""
    tracer_names = _tracer_names()
    if not tracer_names:
        return False
    active_name = _sync_active_names()
    increment = max(1, int(increment))
    for node_name in tracer_names:
        source = "{}.points".format(node_name)
        destination = "{}HandleShape.points".format(node_name)
        if cmds.isConnected(source, destination):
            cmds.disconnectAttr(source, destination)
        cmds.connectAttr(source, destination, force=True)
        try:
            # Touching a different value first guarantees that the snapshot is
            # dirtied even when this pass uses the same sampling as the last one.
            cmds.setAttr("{}.increment".format(node_name), increment + 1)
            cmds.setAttr("{}.increment".format(node_name), increment)
        finally:
            if cmds.isConnected(source, destination):
                cmds.disconnectAttr(source, destination)
    if active_name:
        _set_active_names(active_name)
    return True


def _refresh_offset_pass(node_name):
    """Resample only the tracer whose offset changed."""
    source = "{}.points".format(node_name)
    destination = "{}HandleShape.points".format(node_name)
    if not cmds.objExists(source) or not cmds.objExists(destination):
        return False
    if cmds.isConnected(source, destination):
        cmds.disconnectAttr(source, destination)
    try:
        cmds.connectAttr(source, destination, force=True)
        # Demand-mode snapshot nodes do not rebuild their sampled points from
        # localPosition dirtiness alone. Toggle this snapshot's current
        # increment to force its evaluation, without touching other tracers or
        # scheduling the progressive full-refresh passes.
        increment_plug = "{}.increment".format(node_name)
        increment = max(1, int(cmds.getAttr(increment_plug)))
        cmds.setAttr(increment_plug, increment + 1)
        cmds.setAttr(increment_plug, increment)
    finally:
        if cmds.isConnected(source, destination):
            cmds.disconnectAttr(source, destination)
    return True


def refresh_tracer(*_args):
    if not _has_tracer():
        return wutil.make_inViewMessage("No tracer node in the scene")
    controller = get_controller(create=False)
    if controller is not None:
        controller.cancel_pending()
    return _refresh_pass(1)


def set_tracer_playback_range(*_args):
    if not has_any_tracer():
        return wutil.make_inViewMessage("No tracer node in the scene")
    start_frame = cmds.playbackOptions(query=True, minTime=True)
    end_frame = cmds.playbackOptions(query=True, maxTime=True)
    for node_name in _tracer_names():
        cmds.setAttr("{}.startTime".format(node_name), start_frame)
        cmds.setAttr("{}.endTime".format(node_name), end_frame)
    return refresh_tracer()


def get_tracer_style():
    value = str(_option_value(_STYLE_OPTION, "clean"))
    return value if value in STYLE_PRESETS else "clean"


def tracer_style_choices():
    return [
        {
            "value": key,
            "label": STYLE_PRESETS[key]["label"],
            "description": STYLE_PRESETS[key]["description"],
        }
        for key in STYLE_ORDER
    ]


def apply_tracer_style(style, *_args):
    style = style if style in STYLE_PRESETS else "clean"
    _set_option(_STYLE_OPTION, style)
    for attr_name, value in STYLE_PRESETS[style]["attrs"].items():
        _set_shape_attr_globally(attr_name, value)
    # Style presets define their useful defaults, while these two switches
    # remain explicit user overrides in the parent menu.
    _set_shape_attr_globally("fadeInoutFrames", 12 if has_transparency_falloff() else 0)
    _set_shape_attr_globally("xrayDraw", is_xray_enabled())
    return style


def cycle_tracer_style(*_args):
    current = get_tracer_style()
    return apply_tracer_style(STYLE_ORDER[(STYLE_ORDER.index(current) + 1) % len(STYLE_ORDER)])


def tracer_size_choices():
    return [
        {
            "value": key,
            "label": SIZE_PRESETS[key]["label"],
            "description": "Set tracer and marker size to {}.".format(SIZE_PRESETS[key]["label"].lower()),
        }
        for key in SIZE_ORDER
    ]


def get_tracer_size():
    value = str(_option_value(_SIZE_OPTION, "regular"))
    return value if value in SIZE_PRESETS else "regular"


def set_tracer_size(value, *_args):
    value = value if value in SIZE_PRESETS else "regular"
    _set_option(_SIZE_OPTION, value)
    preset = SIZE_PRESETS[value]
    _set_shape_attr_globally("trailThickness", preset["thickness"])
    _set_shape_attr_globally("keyframeSize", preset["key_size"])
    _set_shape_attr_globally("frameMarkerSize", preset["frame_size"])
    return value


def get_tracer_color():
    value = str(_option_value(_COLOR_OPTION, "red"))
    return value if value in COLOR_PRESETS else "red"


def set_tracer_color(color, *_args):
    color = color if color in COLOR_PRESETS else "red"
    _set_option(_COLOR_OPTION, color)
    extra_color, trail_color = COLOR_PRESETS[color]
    _set_colors(extra_color, trail_color)
    return color


def set_tracer_blue_color(*_args):
    return set_tracer_color("blue")


def set_tracer_red_color(*_args):
    return set_tracer_color("red")


def set_tracer_grey_color(*_args):
    return set_tracer_color("grey")


def _set_colors(extra_color, trail_color):
    for node_name in _tracer_names():
        shape = "{}HandleShape".format(node_name)
        cmds.setAttr("{}.extraTrailColor".format(shape), *extra_color, type="double3")
        cmds.setAttr("{}.trailColor".format(shape), *trail_color, type="double3")
        cmds.setAttr("{}.keyframeColor".format(shape), 1.0, 1.0, 1.0, type="double3")


def get_tracer_range():
    try:
        value = int(_option_value(_RANGE_OPTION, 24))
    except (TypeError, ValueError):
        value = 24
    return value if value in RANGE_VALUES else 24


def tracer_range_choices():
    return [
        {
            "value": value,
            "label": "All Frames" if value == 0 else "{} frames".format(value),
            "description": "Show the entire tracer." if value == 0 else "Show {} frames before and after the current frame.".format(value),
        }
        for value in RANGE_VALUES
    ]


def set_tracer_range(value, *_args):
    try:
        value = int(value)
    except (TypeError, ValueError):
        value = 24
    value = value if value in RANGE_VALUES else 24
    _set_option(_RANGE_OPTION, value)
    _set_shape_attr_globally("preFrame", value)
    _set_shape_attr_globally("postFrame", value)
    return value


def cycle_tracer_range(*_args):
    current = get_tracer_range()
    return set_tracer_range(RANGE_VALUES[(RANGE_VALUES.index(current) + 1) % len(RANGE_VALUES)])


def has_transparency_falloff():
    return bool(_option_value(_FALLOFF_OPTION, True))


def set_transparency_falloff(enabled=False, *_args):
    enabled = bool(enabled)
    _set_option(_FALLOFF_OPTION, enabled)
    _set_shape_attr_globally("fadeInoutFrames", 12 if enabled else 0)
    return enabled


def is_xray_enabled():
    return bool(_option_value(_XRAY_OPTION, True))


def set_xray(enabled=False, *_args):
    enabled = bool(enabled)
    _set_option(_XRAY_OPTION, enabled)
    _set_shape_attr_globally("xrayDraw", enabled)
    return enabled


def get_tracer_direction():
    value = str(_option_value(_DIRECTION_OPTION, "all"))
    return value if value in DIRECTION_PRESETS else "all"


def tracer_direction_choices():
    return [
        {
            "value": key,
            "label": DIRECTION_PRESETS[key]["label"],
            "description": "Choose which side of the current frame is drawn.",
        }
        for key in DIRECTION_ORDER
    ]


def set_tracer_direction(value, *_args):
    value = value if value in DIRECTION_PRESETS else "all"
    _set_option(_DIRECTION_OPTION, value)
    _set_shape_attr_globally("trailPathMode", DIRECTION_PRESETS[value]["value"])
    return value


def get_performance():
    value = str(_option_value(_PERFORMANCE_OPTION, "balanced"))
    return value if value in PERFORMANCE_PROFILES else "balanced"


def performance_choices():
    return [
        {
            "value": key,
            "label": PERFORMANCE_PROFILES[key]["label"],
            "description": PERFORMANCE_PROFILES[key]["description"],
        }
        for key in PERFORMANCE_ORDER
    ]


def set_performance(value, *_args):
    value = value if value in PERFORMANCE_PROFILES else "balanced"
    _set_option(_PERFORMANCE_OPTION, value)
    controller = get_controller(create=False)
    if controller is not None and controller.is_enabled():
        controller.request_refresh()
    return value


def cycle_performance(*_args):
    current = get_performance()
    return set_performance(
        PERFORMANCE_ORDER[(PERFORMANCE_ORDER.index(current) + 1) % len(PERFORMANCE_ORDER)]
    )


def toggle_tracer(*_args):
    _sync_active_names()
    if cmds.objExists(TRACER_HANDLE):
        cmds.setAttr(
            "{}.visibility".format(TRACER_HANDLE),
            not cmds.getAttr("{}.visibility".format(TRACER_HANDLE)),
        )


class _RefreshScheduler(QtCore.QThread):
    """Coalesce edit bursts and plan progressive passes off the UI thread."""

    refreshPass = QtCore.Signal(int, int)

    def __init__(self, parent=None):
        super().__init__(parent)
        self._condition = threading.Condition()
        self._generation = 0
        self._request = None
        self._stopping = False

    def schedule(self, profile, immediate=False):
        with self._condition:
            self._generation += 1
            generation = self._generation
            delay = 0 if immediate else int(profile["debounce_ms"])
            self._request = (
                generation,
                time.monotonic() + (delay / 1000.0),
                tuple(profile["increments"]),
                int(profile["pass_gap_ms"]),
            )
            self._condition.notify_all()
            return generation

    def stop(self):
        with self._condition:
            self._stopping = True
            self._request = None
            self._condition.notify_all()

    def cancel(self):
        with self._condition:
            self._generation += 1
            self._request = None
            self._condition.notify_all()
            return self._generation

    def run(self):
        while True:
            with self._condition:
                while not self._stopping and self._request is None:
                    self._condition.wait()
                if self._stopping:
                    return
                generation, deadline, increments, pass_gap_ms = self._request
                remaining = deadline - time.monotonic()
                if remaining > 0:
                    self._condition.wait(remaining)
                    continue
                self._request = None

            for index, increment in enumerate(increments):
                with self._condition:
                    if self._stopping:
                        return
                    if self._request is not None or generation != self._generation:
                        break
                self.refreshPass.emit(int(increment), int(generation))
                if index + 1 < len(increments) and pass_gap_ms:
                    with self._condition:
                        self._condition.wait(pass_gap_ms / 1000.0)


class TracerUpdateController(QtCore.QObject):
    """Own the worker scheduler; execute only the small Maya pass on main."""

    def __init__(self, manager):
        super().__init__(manager)
        self._manager = manager
        self._enabled = False
        self._generation = 0
        self._offset_tracers = {}
        self._pending_offset_refreshes = set()
        self._scheduler = _RefreshScheduler(self)
        self._scheduler.refreshPass.connect(self._apply_refresh_pass, QtCore.Qt.QueuedConnection)

    def is_enabled(self):
        return self._enabled

    def enable(self):
        if self._enabled:
            self.refresh_offset_watchers()
            return
        self._enabled = True
        if not self._scheduler.isRunning():
            self._scheduler.start()
        self._install_callbacks()

    def _install_callbacks(self):
        self._manager.disconnect_callbacks(_CALLBACK_KEY)
        self._manager.add_anim_curve_edited_callback(
            self._on_source_edited,
            key=_CALLBACK_KEY,
        )
        source_nodes = []
        offset_nodes = []
        self._offset_tracers = {}
        for node_name in _tracer_names():
            for source_node in _tracer_sources_for(node_name):
                if source_node not in source_nodes:
                    source_nodes.append(source_node)
            group_name = _stored_tracer_group(node_name)
            if not group_name:
                continue
            offset_name = "{}_Offset".format(group_name)
            if cmds.objExists(offset_name):
                offset_nodes.append(offset_name)
                self._offset_tracers[offset_name] = node_name
        self._manager.add_node_attribute_changed_callbacks(
            source_nodes,
            self._on_source_transform_edited,
            key=_CALLBACK_KEY,
        )
        self._manager.add_node_attribute_changed_callbacks(
            offset_nodes,
            self._on_offset_edited,
            key=_CALLBACK_KEY,
        )
        self._manager.connect_signal(
            self._manager.undo_performed,
            self._on_source_edited,
            key=_CALLBACK_KEY,
            unique=False,
        )

    def disable(self):
        self._enabled = False
        self._manager.disconnect_callbacks(_CALLBACK_KEY)

    def shutdown(self):
        self.disable()
        if self._scheduler.isRunning():
            self._scheduler.stop()
            self._scheduler.wait(1000)

    def _on_source_edited(self, *_args):
        self.request_refresh()

    def _on_source_transform_edited(self, message, *_args):
        if int(message) & int(om.MNodeMessage.kAttributeSet):
            self.request_refresh(immediate=True)

    def _on_offset_edited(self, message, *_args):
        if not int(message) & int(om.MNodeMessage.kAttributeSet):
            return
        offset_name = _args[-1] if _args else None
        tracer_node = self._offset_tracers.get(offset_name)
        if not tracer_node:
            return
        _remember_tracer_offset(tracer_node)
        if tracer_node in self._pending_offset_refreshes:
            return
        # Coalesce the translateX/Y/Z callbacks produced by one manipulator
        # movement into a single lightweight evaluation on Maya's UI thread.
        self._pending_offset_refreshes.add(tracer_node)
        QtCore.QTimer.singleShot(0, partial(self._apply_offset_refresh, tracer_node))

    def _apply_offset_refresh(self, tracer_node):
        self._pending_offset_refreshes.discard(tracer_node)
        if self._enabled:
            _refresh_offset_pass(tracer_node)

    def refresh_offset_watchers(self):
        if self._enabled:
            self._install_callbacks()

    def request_refresh(self, immediate=False):
        if not self._enabled or not _has_tracer():
            return
        profile = PERFORMANCE_PROFILES[get_performance()]
        self._generation = self._scheduler.schedule(profile, immediate=immediate)

    def cancel_pending(self):
        self._generation = self._scheduler.cancel()

    @QtCore.Slot(int, int)
    def _apply_refresh_pass(self, increment, generation):
        if not self._enabled or generation != self._generation:
            return
        _refresh_pass(increment)


_CONTROLLER = None


def get_controller(create=True):
    global _CONTROLLER
    if _CONTROLLER is None and create:
        _CONTROLLER = TracerUpdateController(runtime.get_runtime_manager())
    return _CONTROLLER


def cleanup():
    global _CONTROLLER
    controller = _CONTROLLER
    _CONTROLLER = None
    if controller is not None:
        controller.shutdown()
        controller.deleteLater()
