"""
TheKeyMachine - Slider Utilities

Internal state management and shared helper functions for sliders.
"""

import maya.cmds as cmds


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
    
    original_keyframes = {}
    original_values = {}
    original_keyframe_values = {}
    generated_keyframe_positions.clear()
    initial_noise_values.clear()
    
    is_cached = False
    frame_data_cache = {}
    tween_frame_data_cache = {}



def get_target_curves(graph_editor=True):
    """
    Identifies which curves to operate on.
    Prefers Graph Editor's selectionConnection if graph_editor is True.
    """
    if graph_editor:
        curves = cmds.selectionConnection("graphEditor1FromOutliner", query=True, object=True)
        if curves:
            return curves
    # Fallback to general curve selection
    return cmds.keyframe(query=True, name=True, sl=True) or []
