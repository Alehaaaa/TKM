"""
TheKeyMachine - Slider Utilities

Internal state management and shared helper functions for sliders.
"""

import maya.cmds as cmds
import maya.mel as mel


# Persistent session state for slider operations
is_dragging = False
original_keyframes = {}
original_values = {}
original_keyframe_values = {}
generated_keyframe_positions = {}
initial_noise_values = {}

# Caching for keyframe operations
is_cached = False
frame_data_cache = {}
tween_frame_data_cache = {}

# Cached targeting context for the active slider drag
_target_attr_plugs = None
_target_source = None
_target_time_range = None
_target_has_graph_keys = False


def start_dragging():
    """Starts a Maya undo chunk if not already dragging."""
    global is_dragging
    if not is_dragging:
        cmds.undoInfo(openChunk=True)
        is_dragging = True


def stop_dragging():
    """Closes the current Maya undo chunk and resets local state."""
    global is_dragging
    if is_dragging:
        cmds.undoInfo(closeChunk=True)
        is_dragging = False
    reset_session_data()


def reset_session_data():
    """Clears stored keyframe data for the current manipulation session."""
    global original_keyframes, original_values, original_keyframe_values
    global generated_keyframe_positions, initial_noise_values
    global is_cached, frame_data_cache, tween_frame_data_cache
    global _target_attr_plugs, _target_source, _target_time_range, _target_has_graph_keys

    original_keyframes = {}
    original_values = {}
    original_keyframe_values = {}
    generated_keyframe_positions.clear()
    initial_noise_values.clear()

    is_cached = False
    frame_data_cache = {}
    tween_frame_data_cache = {}

    _target_attr_plugs = None
    _target_source = None
    _target_time_range = None
    _target_has_graph_keys = False


def get_target_curves():
    """
    Identifies which curves to operate on.
    Prefers Graph Editor's selectionConnection if graph_editor is True.
    """
    curves = cmds.selectionConnection("graphEditor1FromOutliner", query=True, object=True)
    if curves:
        return curves
    # Fallback to general curve selection
    return cmds.keyframe(query=True, name=True, sl=True) or []


def get_selected_time_range():
    """
    Returns a (start, end) rangeArray from Maya's timeControl when a range is selected, else None.
    Mirrors the more robust behavior in keyToolsMod.get_selected_time_range().
    """
    try:
        time_slider = mel.eval("$tmpVar=$gPlayBackSlider")
        time_range = cmds.timeControl(time_slider, q=True, rangeArray=True)
        current_time = cmds.currentTime(query=True)
    except Exception:
        return None

    if not time_range or len(time_range) < 2:
        return None

    # Consider it a selection if:
    # - it spans more than a single frame, OR
    # - it is not just the implicit (current, current+1) pseudo-range.
    if (time_range[1] - time_range[0]) > 1 or (time_range[0] != current_time and time_range[1] != current_time + 1):
        return time_range
    return None


def get_selected_channels():
    """Returns selected main attributes in the Channel Box, or None."""
    try:
        main_channel_box = mel.eval("global string $gChannelBoxName; $temp=$gChannelBoxName;")
        selected_channels = cmds.channelBox(main_channel_box, query=True, selectedMainAttributes=True)
        return selected_channels or None
    except Exception:
        return None


def get_graph_editor_selected_attribute_plugs():
    """
    Returns destination attribute plugs for any selected keys in the Graph Editor.
    This is the highest priority targeting mode.
    """
    anim_curves = cmds.keyframe(q=True, selected=True, name=True) or []
    if not anim_curves:
        return []

    plugs = []
    seen = set()
    for curve in anim_curves:
        try:
            dest = cmds.listConnections(f"{curve}.output", s=False, d=True, p=True) or []
        except Exception:
            dest = []
        for plug in dest:
            if not plug or plug in seen:
                continue
            if "." not in plug:
                continue
            seen.add(plug)
            plugs.append(plug)
    return plugs


def resolve_target_attribute_plugs():
    """
    Resolves the attribute plugs to affect for the current slider session.

    Priority:
    1) Graph Editor selected keys -> their destination plugs
    2) Channel Box selected channels (on selected objects)
    3) All keyable scalar channels (on selected objects)

    The returned list preserves the full selected target set.
    Animated plugs can be keyed later by the slider op, but unanimated plugs
    should remain available for direct attribute edits.
    """
    global _target_attr_plugs, _target_source, _target_time_range, _target_has_graph_keys

    if _target_attr_plugs is not None:
        return _target_attr_plugs, _target_source, _target_time_range, _target_has_graph_keys

    _target_time_range = get_selected_time_range()

    graph_plugs = get_graph_editor_selected_attribute_plugs()
    if graph_plugs:
        _target_attr_plugs = graph_plugs
        _target_source = "graph_editor"
        _target_has_graph_keys = True
        return _target_attr_plugs, _target_source, _target_time_range, _target_has_graph_keys

    nodes = cmds.ls(selection=True) or []
    if not nodes:
        _target_attr_plugs = []
        _target_source = "none"
        _target_has_graph_keys = False
        return _target_attr_plugs, _target_source, _target_time_range, _target_has_graph_keys

    selected_channels = get_selected_channels()
    if selected_channels:
        candidates = [f"{obj}.{attr}" for obj in nodes for attr in selected_channels]
        _target_source = "channel_box"
    else:
        candidates = []
        for obj in nodes:
            attrs = cmds.listAttr(obj, keyable=True, scalar=True) or []
            candidates.extend([f"{obj}.{a}" for a in attrs])
        _target_source = "keyable_scalar"

    # Filter to existing plugs
    candidates = [p for p in candidates if p and cmds.objExists(p)]

    _target_has_graph_keys = False
    _target_attr_plugs = candidates
    return _target_attr_plugs, _target_source, _target_time_range, _target_has_graph_keys
