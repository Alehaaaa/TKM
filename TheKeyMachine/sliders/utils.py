"""
TheKeyMachine - Slider Utilities

Internal state management and shared helper functions for sliders.
"""

import maya.cmds as cmds
from TheKeyMachine.tools import common as toolCommon
from TheKeyMachine.core.selection_targets import (
    get_graph_editor_selected_attribute_plugs,
    get_selected_channels,
    get_selected_time_range,
    resolve_target_attribute_plugs as shared_resolve_target_attribute_plugs,
)


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


def start_dragging(tool_id=None, title=None, description="", tooltip_template=None):
    """Starts a Maya undo chunk if not already dragging."""
    global is_dragging
    if not is_dragging:
        toolCommon.open_undo_chunk(
            tool_id=tool_id,
            title=title,
            description=description,
            tooltip_template=tooltip_template,
        )
        is_dragging = True


def stop_dragging():
    """Closes the current Maya undo chunk and resets local state."""
    global is_dragging
    if is_dragging:
        toolCommon.close_undo_chunk()
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


def resolve_target_attribute_plugs():
    global _target_attr_plugs, _target_source, _target_time_range, _target_has_graph_keys

    if _target_attr_plugs is not None:
        return _target_attr_plugs, _target_source, _target_time_range, _target_has_graph_keys

    _target_attr_plugs, _target_source, _target_time_range, _target_has_graph_keys = shared_resolve_target_attribute_plugs()
    return _target_attr_plugs, _target_source, _target_time_range, _target_has_graph_keys
