"""
TheKeyMachine - Slider Utilities

Internal state management and shared helper functions for sliders.
"""

import maya.cmds as cmds
import maya.mel as mel
from TheKeyMachine.tools import common as toolCommon
from TheKeyMachine.core.selection_targets import (
    resolve_target_attribute_plugs as shared_resolve_target_attribute_plugs,
)


# Persistent session state for slider operations
is_dragging = False
original_keyframes = {}
original_values = {}
original_keyframe_values = {}
generated_keyframe_positions = {}
initial_noise_values = {}
pose_buffer = {}
preserved_time_range = None

# Caching for keyframe operations
is_cached = False
frame_data_cache = {}
tween_frame_data_cache = {}

def start_dragging(tool_id=None, title=None, description="", tooltip_template=None):
    """Starts a Maya undo chunk if not already dragging and resets session data."""
    global is_dragging, preserved_time_range
    if not is_dragging:
        reset_session_data()
        preserved_time_range = _get_time_slider_range_selection()
        # Use a consistent chunk name for all TKM slider operations to ensure clean undos
        chunk_name = toolCommon.make_undo_chunk_name(
            tool_id=tool_id,
            title=title or "Slider Operation",
            description=description,
            tooltip_template=tooltip_template,
        )
        cmds.undoInfo(openChunk=True, chunkName=chunk_name)
        is_dragging = True


def stop_dragging():
    """Closes the current Maya undo chunk and resets local state."""
    global is_dragging
    if is_dragging:
        _restore_time_slider_range_selection()
        try:
            cmds.undoInfo(closeChunk=True)
        except Exception:
            pass
        is_dragging = False
    reset_session_data()


def reset_session_data():
    """Clears stored keyframe data for the current manipulation session."""
    global original_keyframes, original_values, original_keyframe_values
    global generated_keyframe_positions, initial_noise_values
    global is_cached, frame_data_cache, tween_frame_data_cache, preserved_time_range

    original_keyframes = {}
    original_values = {}
    original_keyframe_values = {}
    generated_keyframe_positions.clear()
    initial_noise_values.clear()

    is_cached = False
    frame_data_cache = {}
    tween_frame_data_cache = {}
    preserved_time_range = None


def _playback_slider_name():
    try:
        return mel.eval("$tmpVar=$gPlayBackSlider")
    except Exception:
        return None


def _get_time_slider_range_selection():
    slider = _playback_slider_name()
    if not slider:
        return None
    try:
        time_range = cmds.timeControl(slider, q=True, rangeArray=True)
        current_time = cmds.currentTime(query=True)
    except Exception:
        return None
    if not time_range or len(time_range) < 2:
        return None
    if (time_range[1] - time_range[0]) > 1 or (time_range[0] != current_time and time_range[1] != current_time + 1):
        return tuple(time_range)
    return None


def _restore_time_slider_range_selection():
    slider = _playback_slider_name()
    if not slider or not preserved_time_range:
        return
    current_range = _get_time_slider_range_selection()
    if current_range == preserved_time_range:
        return
    try:
        cmds.timeControl(slider, edit=True, rangeArray=preserved_time_range)
    except Exception:
        pass


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
    if is_dragging:
        _restore_time_slider_range_selection()
    return shared_resolve_target_attribute_plugs()
