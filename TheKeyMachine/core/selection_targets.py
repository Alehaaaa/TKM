import maya.cmds as cmds
import maya.mel as mel

from TheKeyMachine.widgets import util as wutil


def get_selected_time_range():
    try:
        time_slider = mel.eval("$tmpVar=$gPlayBackSlider")
        time_range = cmds.timeControl(time_slider, q=True, rangeArray=True)
        current_time = cmds.currentTime(query=True)
    except Exception:
        return None

    if not time_range or len(time_range) < 2:
        return None

    if (time_range[1] - time_range[0]) > 1 or (time_range[0] != current_time and time_range[1] != current_time + 1):
        return time_range
    return None


def get_selected_channels():
    try:
        main_channel_box = mel.eval("global string $gChannelBoxName; $temp=$gChannelBoxName;")
        selected_channels = cmds.channelBox(main_channel_box, query=True, selectedMainAttributes=True)
        return selected_channels or None
    except Exception:
        return None


def get_graph_editor_selected_attribute_plugs():
    anim_curves = cmds.keyframe(q=True, selected=True, name=True) or []
    if not anim_curves:
        return []

    plugs = []
    seen = set()
    for curve in anim_curves:
        try:
            dest = cmds.listConnections("{}.output".format(curve), s=False, d=True, p=True) or []
        except Exception:
            dest = []
        for plug in dest:
            if not plug or plug in seen or "." not in plug:
                continue
            seen.add(plug)
            plugs.append(plug)
    return plugs


def resolve_target_attribute_plugs():
    time_range = get_selected_time_range()

    graph_plugs = get_graph_editor_selected_attribute_plugs()
    if graph_plugs:
        return graph_plugs, "graph_editor", time_range, True

    nodes = wutil.get_selected_objects()
    if not nodes:
        return [], "none", time_range, False

    selected_channels = get_selected_channels()
    if selected_channels:
        candidates = ["{}.{}".format(obj, attr) for obj in nodes for attr in selected_channels]
        source = "channel_box"
    else:
        candidates = []
        for obj in nodes:
            attrs = cmds.listAttr(obj, keyable=True, scalar=True) or []
            candidates.extend(["{}.{}".format(obj, attr) for attr in attrs])
        source = "keyable_scalar"

    candidates = [plug for plug in candidates if plug and cmds.objExists(plug)]
    return candidates, source, time_range, False
