import maya.cmds as cmds
import maya.mel as mel

try:
    from maya.api import OpenMaya as om
except ImportError:
    om = None


GRAPH_EDITOR_OUTLINER = "graphEditor1FromOutliner"
GRAPH_EDITOR = "graphEditor1GraphEd"
GRAPH_EDITOR_PANEL = "graphEditor1"


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
    except (RuntimeError, ValueError, TypeError, AttributeError, KeyError, IndexError):
        return _ls_selected(long=long)

    if not selection_strings:
        return []

    try:
        return cmds.ls(selection_strings, long=long) or selection_strings
    except (RuntimeError, ValueError, TypeError, AttributeError, KeyError, IndexError):
        return selection_strings


def get_valid_selected_objects(long=False, ordered=False, orderedSelection=None):
    raw = get_selected_objects(long=long, ordered=ordered, orderedSelection=orderedSelection)
    if not raw:
        return []
    curves = set(cmds.ls(raw, type="animCurve", long=long) or [])
    return [x for x in raw if x not in curves]

def get_selected_object_count():
    if om is not None:
        try:
            return om.MGlobal.getActiveSelectionList().length()
        except (RuntimeError, ValueError, TypeError, AttributeError, KeyError, IndexError):
            pass
    return len(_ls_selected())


def get_selected_time_range():
    try:
        time_range = _query_playback_slider(rangeArray=True)
    except (RuntimeError, ValueError, TypeError, AttributeError, KeyError, IndexError):
        return None

    if not time_range or len(time_range) < 2:
        return None

    if (time_range[1] - time_range[0]) > 1:
        return time_range
    try:
        current_time = cmds.currentTime(query=True)
    except (RuntimeError, ValueError, TypeError, AttributeError, KeyError, IndexError):
        return None
    if time_range[0] != current_time and time_range[1] != current_time + 1:
        return time_range
    return None


def get_selected_channels():
    try:
        main_channel_box = mel.eval("global string $gChannelBoxName; $temp=$gChannelBoxName;")
    except (RuntimeError, ValueError, TypeError, AttributeError, KeyError, IndexError):
        return []

    if not main_channel_box:
        return []

    attrs = []

    for query_flag in (
        "selectedMainAttributes",
        "selectedShapeAttributes",
        "selectedHistoryAttributes",
        "selectedOutputAttributes",
    ):
        try:
            values = cmds.channelBox(main_channel_box, query=True, **{query_flag: True}) or []
            attrs.extend(values)
        except (RuntimeError, ValueError, TypeError, AttributeError, KeyError, IndexError):
            pass

    return _unique(attrs)


def _unique(items):
    unique_items = []
    seen = set()
    for item in items or []:
        if item and item not in seen:
            seen.add(item)
            unique_items.append(item)
    return unique_items


def is_anim_curve(node):
    try:
        return bool(node and cmds.objExists(node) and cmds.nodeType(node).startswith("animCurve"))
    except (RuntimeError, ValueError, TypeError, AttributeError, KeyError, IndexError):
        return False


def is_rotation_anim_curve(node):
    try:
        return bool(node and cmds.objExists(node) and cmds.nodeType(node) in ("animCurveTA", "animCurveTU"))
    except (RuntimeError, ValueError, TypeError, AttributeError, KeyError, IndexError):
        return False


def get_keyable_scalar_attributes(node):
    try:
        return cmds.listAttr(node, keyable=True, scalar=True, visible=True) or []
    except (RuntimeError, ValueError, TypeError, AttributeError, KeyError, IndexError):
        return []


def get_anim_curve_output_plugs(curves):
    plugs = []
    for curve in curves or []:
        pending = ["{}.output".format(curve)]
        visited = set()
        while pending:
            source = pending.pop(0)
            if source in visited:
                continue
            visited.add(source)
            try:
                destinations = cmds.listConnections(
                    source,
                    source=False,
                    destination=True,
                    plugs=True,
                    skipConversionNodes=True,
                ) or []
            except (RuntimeError, ValueError, TypeError, AttributeError, KeyError, IndexError):
                destinations = []
            for destination in destinations:
                if not destination or "." not in destination:
                    continue
                node = destination.split(".", 1)[0]
                try:
                    node_type = cmds.nodeType(node)
                except (RuntimeError, ValueError, TypeError, AttributeError, KeyError, IndexError):
                    node_type = ""
                if str(node_type).startswith("animBlendNode"):
                    pending.append(node)
                else:
                    plugs.append(destination)
    return _unique(plugs)


def get_anim_curves_from_plugs(plugs):
    try:
        from TheKeyMachine.core import animlayers
    except Exception:
        return []
    valid_plugs = [
        plug
        for plug in plugs or []
        if plug and cmds.objExists(plug)
    ]
    return animlayers.get_anim_curves_from_plugs(
        valid_plugs,
        include_all_layers=True,
    )


def get_anim_curves_for_nodes(nodes, include_shapes=False):
    lookup_nodes = list(nodes or [])
    if include_shapes:
        for node in nodes or []:
            try:
                lookup_nodes.extend(cmds.listRelatives(node, shapes=True, fullPath=True) or [])
            except (RuntimeError, ValueError, TypeError, AttributeError, KeyError, IndexError):
                pass

    curves = []
    for node in _unique(lookup_nodes):
        if not node or not cmds.objExists(node):
            continue
        try:
            curves.extend(cmds.listConnections(node, type="animCurve", connections=False, plugs=False) or [])
        except (RuntimeError, ValueError, TypeError, AttributeError, KeyError, IndexError):
            pass
    return _unique(curves)


def get_attribute_plugs_from_nodes(nodes):
    nodes = _unique(nodes)
    if not nodes:
        return [], "none"

    selected_channels = get_selected_channels()

    if selected_channels:
        plugs = []
        for obj in nodes:
            for attr in selected_channels:
                plug = "{}.{}".format(obj, attr)
                if cmds.objExists(plug):
                    plugs.append(plug)

        if plugs:
            return _unique(plugs), "channel_box"

    plugs = []
    for obj in nodes:
        attrs = get_keyable_scalar_attributes(obj)
        for attr in attrs:
            plug = "{}.{}".format(obj, attr)
            if cmds.objExists(plug):
                plugs.append(plug)

    return _unique(plugs), "keyable_scalar"

def is_plug_animated(plug):
    return bool(get_anim_curves_from_plugs([plug]))


def is_channel_animated(node, attr):
    if not node or not attr:
        return False
    plug = "{}.{}".format(node, attr)
    return cmds.objExists(plug) and is_plug_animated(plug)


def is_node_animated(node, keyable_only=True, unlocked_only=True):
    if not node or not cmds.objExists(node):
        return False

    attrs = get_keyable_scalar_attributes(node) if keyable_only else (cmds.listAttr(node) or [])
    for attr in attrs:
        plug = "{}.{}".format(node, attr)
        if not cmds.objExists(plug):
            continue
        if unlocked_only:
            try:
                if cmds.getAttr(plug, lock=True):
                    continue
            except (RuntimeError, ValueError, TypeError, AttributeError, KeyError, IndexError):
                continue
        if is_plug_animated(plug):
            return True
    return False


def get_animated_channels_for_node(node, keyable_only=True, settable_only=False):
    if not node or not cmds.objExists(node):
        return []

    attrs = get_keyable_scalar_attributes(node) if keyable_only else (cmds.listAttr(node) or [])
    animated = []
    for attr in attrs:
        plug = "{}.{}".format(node, attr)
        if not cmds.objExists(plug):
            continue
        if settable_only:
            try:
                if not cmds.getAttr(plug, settable=True):
                    continue
            except (RuntimeError, ValueError, TypeError, AttributeError, KeyError, IndexError):
                continue
        if is_plug_animated(plug):
            animated.append(attr)
    return animated


def split_plug(plug):
    if not plug or "." not in plug:
        return None, None
    return plug.split(".", 1)


def object_names_from_plugs(plugs):
    objects = []
    for plug in plugs or []:
        obj, _attr = split_plug(plug)
        if obj:
            objects.append(obj)
    return _unique(objects)


def attribute_names_from_plugs(plugs):
    attrs = []
    for plug in plugs or []:
        _obj, attr = split_plug(plug)
        if attr:
            attrs.append(attr)
    return _unique(attrs)


def _selected_object_attribute_plugs():
    nodes = get_selected_objects()
    if not nodes:
        return [], "none"
    return get_attribute_plugs_from_nodes(nodes)


def _resolve_graph_outliner_items(items):
    plugs = []
    curves = []
    nodes = []
    for item in items or []:
        if not item:
            continue
        if "." in item and cmds.objExists(item):
            plugs.append(item)
        elif is_anim_curve(item):
            curves.append(item)
        else:
            nodes.append(item)

    node_plugs, _source = get_attribute_plugs_from_nodes(nodes)
    plugs = _unique(plugs + node_plugs + get_anim_curve_output_plugs(curves))
    curves = _unique(curves + get_anim_curves_from_plugs(plugs))
    return plugs, curves


def get_graph_editor_selected_attribute_plugs():
    if not is_graph_editor_visible():
        return []
    anim_curves = cmds.keyframe(q=True, selected=True, name=True) or []
    return get_anim_curve_output_plugs(anim_curves)


def is_graph_editor_visible():
    try:
        return GRAPH_EDITOR_PANEL in (cmds.getPanel(vis=True) or [])
    except (RuntimeError, ValueError, TypeError, AttributeError, KeyError, IndexError):
        return False


def get_graph_editor_outliner_items():
    if not is_graph_editor_visible():
        return []
    try:
        return cmds.selectionConnection(GRAPH_EDITOR_OUTLINER, query=True, object=True) or []
    except (RuntimeError, ValueError, TypeError, AttributeError, KeyError, IndexError):
        return []


def get_graph_editor_selected_curves():
    if not is_graph_editor_visible():
        return []
    try:
        selected_curves = cmds.keyframe(query=True, selected=True, name=True) or []
    except (RuntimeError, ValueError, TypeError, AttributeError, KeyError, IndexError):
        selected_curves = []
    if selected_curves:
        return selected_curves
    _plugs, curves = _resolve_graph_outliner_items(get_graph_editor_outliner_items())
    return curves


def get_graph_editor_selected_keyframes():
    anim_curves = get_graph_editor_selected_curves()
    if not anim_curves:
        return []

    selected_frames = set(get_graph_editor_selected_frames())
    keyframes = []
    for curve in anim_curves:
        try:
            curve_frames = cmds.keyframe(curve, query=True, selected=True) or []
        except (RuntimeError, ValueError, TypeError, AttributeError, KeyError, IndexError):
            curve_frames = []
        keyframes.extend((curve, frame) for frame in curve_frames if int(frame) in selected_frames)

    return keyframes


def get_target_curves():
    if not is_graph_editor_visible():
        return []
    _plugs, curves = _resolve_graph_outliner_items(get_graph_editor_outliner_items())
    if curves:
        return curves
    try:
        return cmds.keyframe(query=True, name=True, sl=True) or []
    except (RuntimeError, ValueError, TypeError, AttributeError, KeyError, IndexError):
        return []


def get_selected_object_curves():
    plugs, _source = _selected_object_attribute_plugs()
    return get_anim_curves_from_plugs(plugs)


def _resolve_slider_targets():
    """Resolve explicit editor selections before the Time Slider's visible curves."""
    time_range = get_selected_time_range()

    try:
        selected_key_curves = cmds.keyframe(query=True, selected=True, name=True) or []
    except (RuntimeError, ValueError, TypeError, AttributeError, KeyError, IndexError):
        selected_key_curves = []
    if selected_key_curves:
        return {
            "plugs": get_anim_curve_output_plugs(selected_key_curves),
            "curves": _unique(selected_key_curves),
            "source": "graph_editor",
            "time_range": time_range,
            "has_graph_keys": True,
        }

    plugs, source = _selected_object_attribute_plugs()
    if source == "channel_box" and plugs:
        return {
            "plugs": plugs,
            "curves": get_anim_curves_from_plugs(plugs),
            "source": source,
            "time_range": time_range,
            "has_graph_keys": False,
        }

    timeline_curves = get_time_slider_anim_curves()
    if timeline_curves:
        return {
            "plugs": get_anim_curve_output_plugs(timeline_curves),
            "curves": timeline_curves,
            "source": "time_slider",
            "time_range": time_range,
            "has_graph_keys": False,
        }

    return {"plugs": [], "curves": [], "source": "none", "time_range": time_range, "has_graph_keys": False}


def resolve_target_context():
    return dict(_resolve_slider_targets())


def resolve_target_attribute_plugs():
    targets = resolve_target_context()
    return targets["plugs"], targets["source"], targets["time_range"], targets["has_graph_keys"]


def resolve_target_curves():
    targets = resolve_target_context()
    return targets["curves"], targets["source"], targets["time_range"], targets["has_graph_keys"]


_PLAYBACK_SLIDER = None


def get_playback_slider(refresh=False):
    global _PLAYBACK_SLIDER
    if refresh or _PLAYBACK_SLIDER is None:
        _PLAYBACK_SLIDER = mel.eval("$tmpVar=$gPlayBackSlider")
    return _PLAYBACK_SLIDER


def _query_playback_slider(**kwargs):
    global _PLAYBACK_SLIDER
    for refresh in (False, True):
        try:
            return cmds.timeControl(
                get_playback_slider(refresh=refresh),
                query=True,
                **kwargs
            )
        except (RuntimeError, ValueError, TypeError, AttributeError, KeyError, IndexError):
            _PLAYBACK_SLIDER = None
    return None


def get_time_slider_anim_curves():
    """Return the animation curves currently represented by the Time Slider."""
    return _unique(_query_playback_slider(animCurveNames=True) or [])


def get_key_navigation_curves():
    """Resolve key-navigation curves with one UI-context lookup path."""
    if is_graph_editor_visible():
        try:
            curves = cmds.keyframe(
                query=True,
                selected=True,
                name=True,
            ) or []
        except (RuntimeError, ValueError, TypeError, AttributeError, KeyError, IndexError):
            curves = []
        if curves:
            return _unique(curves)

        try:
            outliner_items = cmds.selectionConnection(
                GRAPH_EDITOR_OUTLINER,
                query=True,
                object=True,
            ) or []
        except (RuntimeError, ValueError, TypeError, AttributeError, KeyError, IndexError):
            outliner_items = []
        _plugs, curves = _resolve_graph_outliner_items(outliner_items)
        if curves:
            return _unique(curves)

    return get_time_slider_anim_curves()


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
        except (RuntimeError, ValueError, TypeError, AttributeError, KeyError, IndexError):
            continue
    return sorted(normalized)


def get_graph_editor_selected_tangent_frames():
    if not is_graph_editor_visible():
        return []
    try:
        tangent_frames = cmds.keyTangent(query=True, selected=True, timeChange=True) or []
    except (RuntimeError, ValueError, TypeError, AttributeError, KeyError, IndexError):
        tangent_frames = []
    return _normalize_frames(tangent_frames)


def get_graph_editor_selected_frames(include_tangents=True):
    if not is_graph_editor_visible():
        return []
    try:
        frames = list(cmds.keyframe(query=True, selected=True, tc=True) or [])
    except (RuntimeError, ValueError, TypeError, AttributeError, KeyError, IndexError):
        frames = []

    for curve in get_graph_editor_selected_curves():
        try:
            frames.extend(cmds.keyframe(curve, query=True, selected=True, timeChange=True) or [])
        except (RuntimeError, ValueError, TypeError, AttributeError, KeyError, IndexError):
            continue

    if include_tangents:
        try:
            frames.extend(get_graph_editor_selected_tangent_frames())
        except (RuntimeError, ValueError, TypeError, AttributeError, KeyError, IndexError):
            pass
    return _normalize_frames(frames)


def get_graph_editor_selected_range(include_tangents=True):
    frames = get_graph_editor_selected_frames(include_tangents=include_tangents)
    if not frames:
        return None
    return frames[0], frames[-1]


def get_selected_time_slider_range():
    time_range = _query_playback_slider(rangeArray=True)
    if not time_range or len(time_range) < 2:
        return None
    if (time_range[1] - time_range[0]) > 1:
        return _normalize_slider_range(time_range)
    try:
        current_time = int(cmds.currentTime(query=True))
    except (RuntimeError, ValueError, TypeError, AttributeError, KeyError, IndexError):
        return None
    if time_range[0] != current_time and time_range[1] != current_time + 1:
        return _normalize_slider_range(time_range)
    return None
