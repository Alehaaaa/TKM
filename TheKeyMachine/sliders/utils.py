"""
TheKeyMachine - Slider Utilities

Session state and shared helper functions for sliders.
"""

import maya.cmds as cmds
from dataclasses import dataclass, field
from typing import Optional, List, Dict, Any, Tuple

from TheKeyMachine.tools import common as toolCommon
from TheKeyMachine.core import selection_targets


@dataclass
class SliderTargetContext:
    """Holds targeting information resolved at the start of a slider interaction."""
    resolved: bool = False
    curves: List[str] = field(default_factory=list)
    # The map of attribute/curve to its affected keyframe times
    affected_map: Dict[str, List[float]] = field(default_factory=dict)
    time_range: Optional[Tuple[float, float]] = None
    has_graph_keys: bool = False

    def clear(self):
        self.resolved = False
        self.curves.clear()
        self.affected_map.clear()
        self.time_range = None
        self.has_graph_keys = False


@dataclass
class SliderCaches:
    """Holds various caches used during a slider drag to ensure stability."""
    is_cached: bool = False
    original_keyframes: Dict[str, Dict[float, float]] = field(default_factory=dict)
    generated_positions: Dict[str, List[float]] = field(default_factory=dict)
    initial_noise: Dict[str, List[float]] = field(default_factory=dict)
    frame_data: Dict[Tuple[str, float], Any] = field(default_factory=dict)
    tween_frame_data: Dict[Tuple[str, float], Any] = field(default_factory=dict)
    pose_buffer: Dict[Tuple[str, float], float] = field(default_factory=dict)

    def clear(self, keep_pose=False):
        self.is_cached = False
        self.original_keyframes.clear()
        self.generated_positions.clear()
        self.initial_noise.clear()
        self.frame_data.clear()
        self.tween_frame_data.clear()
        if not keep_pose:
            self.pose_buffer.clear()


@dataclass
class TweenFrameData:
    needsCalculation: bool
    use_direct_attr: bool = False
    previousValue: Optional[float] = None
    nextValue: Optional[float] = None
    currentValue: Optional[float] = None
    prev_f: Optional[float] = None
    next_f: Optional[float] = None


@dataclass
class BlendFrameData:
    original_value: Optional[float] = None
    use_direct_attr: bool = False
    previousValue: Optional[float] = None
    nextValue: Optional[float] = None
    prevTanType: Optional[str] = None
    prev_f: Optional[float] = None
    next_f: Optional[float] = None
    defaultValue: Optional[float] = None
    leftValue: Optional[float] = None
    rightValue: Optional[float] = None
    leftFrame: Optional[float] = None
    rightFrame: Optional[float] = None
    bufferValue: Optional[float] = None


def get_block_neighbors(time, target_times_set, all_keys):
    """Finds the bounding keyframes outside a continuous selection block."""
    c_time = float(time)
    if c_time in all_keys:
        idx = all_keys.index(c_time)
        left_idx = idx
        while left_idx > 0 and all_keys[left_idx - 1] in target_times_set:
            left_idx -= 1
        p_time = all_keys[left_idx - 1] if left_idx > 0 else all_keys[left_idx]
        right_idx = idx
        while right_idx < len(all_keys) - 1 and all_keys[right_idx + 1] in target_times_set:
            right_idx += 1
        n_time = all_keys[right_idx + 1] if right_idx < len(all_keys) - 1 else all_keys[right_idx]
    else:
        prev_ks = [f for f in all_keys if f < c_time]
        next_ks = [f for f in all_keys if f > c_time]
        p_time = prev_ks[-1] if prev_ks else (all_keys[0] if all_keys else c_time)
        n_time = next_ks[0] if next_ks else (all_keys[-1] if all_keys else c_time)
    return p_time, n_time


def lerp(a, b, t):
    return a + (b - a) * t


def lerp_towards(left, right, t, current):
    if t < 0.0:
        return lerp(left, current, t + 1.0)
    if t > 0.0:
        return lerp(current, right, t)
    return current


def resolve_keyframe_targets():
    """Unified entry for resolving attribute plugs and affected times."""
    plugs, _src, time_range, has_graph_keys = selection_targets.resolve_target_attribute_plugs()
    if not plugs:
        return {}, time_range

    curr = cmds.currentTime(q=True)
    affected = {}
    tangent_fs = set()
    if has_graph_keys:
        tangent_fs = set(float(f) for f in selection_targets.get_graph_editor_selected_tangent_frames())

    for plug in plugs:
        if has_graph_keys:
            ks = set(float(t) for t in (cmds.keyframe(plug, q=True, selected=True, timeChange=True) or []))
            if tangent_fs:
                ks |= (tangent_fs & set(float(t) for t in (cmds.keyframe(plug, q=True, timeChange=True) or [])))
            times = sorted(ks) if ks else [curr]
        elif time_range:
            times = cmds.keyframe(plug, q=True, time=(time_range[0], time_range[1]), timeChange=True) or [curr]
        else:
            times = [curr]
        affected[plug] = sorted(list(set(times)))
    return affected, time_range


def resolve_curve_targets():
    """Unified entry for resolving whole curves and affected times."""
    curves, _src, time_range, has_graph_keys = selection_targets.resolve_target_curves()
    if not curves:
        return [], {}, time_range, has_graph_keys

    curr = cmds.currentTime(q=True)
    times_map = {}
    for c in curves:
        if has_graph_keys:
            ks = cmds.keyframe(c, q=True, selected=True, timeChange=True) or [curr]
        elif time_range:
            ks = cmds.keyframe(c, q=True, time=(time_range[0], time_range[1]), timeChange=True) or [curr]
        else:
            ks = [curr]
        times_map[c] = sorted(list(set(float(t) for t in ks)))
    return curves, times_map, time_range, has_graph_keys



class SliderSession:
    """Per-interaction slider state.

    A session owns the caches for one live slider drag or atomic button action.
    It is finished on release, which closes the undo chunk and clears its data.
    """

    def __init__(self, mode, title=None, description="", tooltip_template=None):
        self.mode = mode
        self.title = title or "Slider Operation"
        self.description = description
        self.tooltip_template = tooltip_template

        self.targets = SliderTargetContext()
        self.cache = SliderCaches()
        self._is_open = False

    def ensure_undo_open(self):
        """Lazily open the undo chunk on the first operation."""
        if self._is_open:
            return
        chunk_name = toolCommon.make_undo_chunk_name(
            tool_id=self.mode,
            title=self.title,
            description=self.description,
            tooltip_template=self.tooltip_template,
        )
        cmds.undoInfo(openChunk=True, chunkName=chunk_name)
        self._is_open = True

    def switch_mode(self, mode, title=None, description="", tooltip_template=None):
        if mode == self.mode:
            return
        self.mode = mode
        self.title = title or self.title
        self.description = description
        self.tooltip_template = tooltip_template
        
        # If we switch modes mid-session, we keep the undo chunk open
        # but reset the resolved targets so they are re-calculated for the new mode.
        self.reset()

    def reset(self):
        """Clear drag-scoped caches while keeping the undo chunk open."""
        self.targets.clear()
        self.cache.clear(keep_pose=True)

    def snapshot_pose_buffer(self, affected_map):
        """Capture the current pose for modes that need an original-pose target."""
        self.cache.pose_buffer.clear()
        for attr_full, times in (affected_map or {}).items():
            if not cmds.objExists(attr_full):
                continue
            for current_time in times:
                try:
                    value = cmds.getAttr(attr_full, time=current_time)
                except Exception:
                    continue
                if isinstance(value, (int, float)):
                    self.cache.pose_buffer[(attr_full, current_time)] = float(value)

    def finish(self):
        """Close the undo chunk and clear all session-owned state."""
        if self._is_open:
            try:
                cmds.undoInfo(closeChunk=True)
            except Exception:
                pass
            self._is_open = False
        self.targets.clear()
        self.cache.clear()
