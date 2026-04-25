import maya.cmds as cmds
import maya.mel as mel

try:
    from maya.api import OpenMaya as om
except Exception:
    om = None


GRAPH_EDITOR_OUTLINER = "graphEditor1FromOutliner"
GRAPH_EDITOR = "graphEditor1GraphEd"


def _ls_selected(long=False, ordered=False):
    if ordered:
        return cmds.ls(orderedSelection=True, long=long) or cmds.ls(selection=True, long=long) or []
    return cmds.ls(selection=True, long=long) or []


def get_selected_objects(long=False, ordered=False, orderedSelection=None):
    if orderedSelection is not None:
        ordered = bool(orderedSelection)

    if ordered:
        return _ls_selected(long=long, ordered=True)

    if om is None:
        return _ls_selected(long=long)

    try:
        selection_list = om.MGlobal.getActiveSelectionList()
        selection_strings = selection_list.getSelectionStrings()
    except Exception:
        return _ls_selected(long=long)

    if not selection_strings:
        return []

    try:
        return cmds.ls(selection_strings, long=long) or selection_strings
    except Exception:
        return selection_strings


def get_selected_object_count():
    if om is not None:
        try:
            return om.MGlobal.getActiveSelectionList().length()
        except Exception:
            pass
    return len(_ls_selected())


def get_selected_time_range():
    try:
        time_slider = get_playback_slider()
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


def get_graph_editor_outliner_items():
    try:
        return cmds.selectionConnection(GRAPH_EDITOR_OUTLINER, query=True, object=True) or []
    except Exception:
        return []


def get_graph_editor_selected_curves():
    try:
        selected_curves = cmds.keyframe(query=True, selected=True, name=True) or []
    except Exception:
        selected_curves = []
    if selected_curves:
        return selected_curves
    return get_graph_editor_outliner_items()


def get_target_curves():
    curves = get_graph_editor_outliner_items()
    if curves:
        return curves
    try:
        return cmds.keyframe(query=True, name=True, sl=True) or []
    except Exception:
        return []


def resolve_target_attribute_plugs():
    time_range = get_selected_time_range()

    graph_plugs = get_graph_editor_selected_attribute_plugs()
    if graph_plugs:
        return graph_plugs, "graph_editor", time_range, True

    nodes = get_selected_objects()
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


def get_playback_slider():
    return mel.eval("$tmpVar=$gPlayBackSlider")


def _normalize_slider_range(range_array):
    start = int(range_array[0])
    end = int(range_array[1] - 1)
    if end < start:
        end = start
    return start, end


def _normalize_frames(frames):
    normalized = set()
    for frame in frames or []:
        try:
            normalized.add(int(round(frame)))
        except Exception:
            continue
    return sorted(normalized)


def get_graph_editor_selected_tangent_frames():
    try:
        tangent_frames = cmds.keyTangent(query=True, selected=True, timeChange=True) or []
    except Exception:
        tangent_frames = []
    return _normalize_frames(tangent_frames)


def get_graph_editor_selected_frames(include_tangents=True):
    try:
        frames = list(cmds.keyframe(query=True, selected=True, tc=True) or [])
    except Exception:
        frames = []

    for curve in get_graph_editor_selected_curves():
        try:
            frames.extend(cmds.keyframe(curve, query=True, selected=True, timeChange=True) or [])
        except Exception:
            continue

    if include_tangents:
        try:
            frames.extend(get_graph_editor_selected_tangent_frames())
        except Exception:
            pass
    return _normalize_frames(frames)


def get_graph_editor_selected_range(include_tangents=True):
    frames = get_graph_editor_selected_frames(include_tangents=include_tangents)
    if not frames:
        return None
    return frames[0], frames[-1]


def get_selected_time_slider_range():
    time_range = cmds.timeControl(get_playback_slider(), q=True, rangeArray=True)
    current_time = int(cmds.currentTime(query=True))
    if (time_range[1] - time_range[0]) > 1 or (time_range[0] != current_time and time_range[1] != current_time + 1):
        return _normalize_slider_range(time_range)
    return None
