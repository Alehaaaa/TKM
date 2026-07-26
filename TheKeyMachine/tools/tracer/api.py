from maya import cmds

import TheKeyMachine.mods.selectionMod as selectionMod
import TheKeyMachine.widgets.util as wutil
from TheKeyMachine.core.scene_nodes import TkmSceneNode
from TheKeyMachine.data import icons


def create_tracer(*_args):
    selected_objects = selectionMod.get_selected_objects()
    if len(selected_objects) != 1:
        return wutil.make_inViewMessage("Select only one object")
    if cmds.objExists("Tracer"):
        cmds.delete("Tracer")

    tracer_node = TkmSceneNode.root().child("Tracer", icon=icons.tracer)
    tracer_node.child("Tracer_Offset")
    cmds.select(selected_objects)
    if cmds.objExists("tracerHandle"):
        cmds.delete("tracerHandle")

    start_frame = cmds.playbackOptions(query=True, minTime=True)
    end_frame = cmds.playbackOptions(query=True, maxTime=True)
    cmds.snapshot(name="tracer", motionTrail=True, constructionHistory=True, startTime=start_frame, endTime=end_frame, increment=1)
    cmds.setAttr("tracerHandleShape.trailDrawMode", 1)
    set_tracer_red_color()
    cmds.disconnectAttr("tracer.points", "tracerHandleShape.points")
    cmds.parent("tracerHandle", "Tracer_Offset")
    cmds.select(selected_objects)


def select_tracer_offset_node(*_args):
    if cmds.objExists("Tracer_Offset"):
        cmds.select("Tracer_Offset", replace=True)


def remove_tracer(*_args):
    if cmds.objExists("Tracer"):
        cmds.delete("Tracer")


def is_connected():
    return bool(
        cmds.objExists("tracer")
        and cmds.objExists("tracerHandleShape")
        and cmds.isConnected("tracer.points", "tracerHandleShape.points")
    )


def set_connected(connected=False, update_cb=None, *_args):
    if not cmds.objExists("tracerHandle"):
        return wutil.make_inViewMessage("No tracer node in the scene")
    current = is_connected()
    if connected != current:
        if connected:
            cmds.connectAttr("tracer.points", "tracerHandleShape.points", force=True)
            cmds.setAttr("tracer.increment", 1)
        else:
            cmds.disconnectAttr("tracer.points", "tracerHandleShape.points")
    if update_cb:
        update_cb(bool(connected))


def refresh_tracer(*_args):
    if not cmds.objExists("tracerHandle"):
        return wutil.make_inViewMessage("No tracer node in the scene")
    if is_connected():
        return
    cmds.connectAttr("tracer.points", "tracerHandleShape.points", force=True)
    for increment in (1, 2, 1):
        cmds.setAttr("tracer.increment", increment)
    cmds.disconnectAttr("tracer.points", "tracerHandleShape.points")


def set_tracer_blue_color(*_args):
    _set_colors((0.1615, 0.1766, 0.3581), (0.2879, 0.2932, 0.358))


def set_tracer_red_color(*_args):
    _set_colors((0.8143, 0.5109, 0.5318), (0.4398, 0.1724, 0.1908))


def set_tracer_grey_color(*_args):
    _set_colors((0.2879, 0.2932, 0.358), (0.122, 0.122, 0.122))


def _set_colors(extra_color, trail_color):
    if not cmds.objExists("tracerHandle"):
        return
    cmds.setAttr("tracerHandleShape.extraTrailColor", *extra_color, type="double3")
    cmds.setAttr("tracerHandleShape.trailColor", *trail_color, type="double3")
    cmds.setAttr("tracerHandleShape.keyframeColor", 1.0, 1.0, 1.0, type="double3")


def toggle_tracer(*_args):
    if cmds.objExists("tracerHandle"):
        cmds.setAttr("tracerHandle.visibility", not cmds.getAttr("tracerHandle.visibility"))
