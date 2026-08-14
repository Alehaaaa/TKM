"""Interaction state shared by all slider tools."""

from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional, Tuple

from maya import cmds
try:
    from maya.api import OpenMayaAnim as oma
except ImportError:
    oma = None

from TheKeyMachine.core import runtime
from TheKeyMachine.data.colors import COLORS
from TheKeyMachine.tools import common as tool_common
from TheKeyMachine.ui.widgets import timeline


@dataclass
class SliderTargetContext:
    resolved: bool = False
    curves: List[str] = field(default_factory=list)
    affected_map: Dict[str, List[float]] = field(default_factory=dict)
    time_range: Optional[Tuple[float, float]] = None
    has_graph_keys: bool = False
    layer_context: Dict[str, Any] = field(default_factory=dict)

    def clear(self):
        self.resolved = False
        self.curves.clear()
        self.affected_map.clear()
        self.time_range = None
        self.has_graph_keys = False
        self.layer_context.clear()


@dataclass
class SliderCaches:
    is_cached: bool = False
    original_keyframes: Dict[str, Dict[float, float]] = field(default_factory=dict)
    generated_positions: Dict[str, List[float]] = field(default_factory=dict)
    initial_noise: Dict[str, List[float]] = field(default_factory=dict)
    frame_data: Dict[Tuple[str, float], Any] = field(default_factory=dict)
    tween_frame_data: Dict[Tuple[str, float], Any] = field(default_factory=dict)
    pose_buffer: Dict[Tuple[str, float], float] = field(default_factory=dict)
    auxiliary: Dict[Any, Any] = field(default_factory=dict)

    def clear(self, keep_pose=False):
        self.is_cached = False
        self.original_keyframes.clear()
        self.generated_positions.clear()
        self.initial_noise.clear()
        self.frame_data.clear()
        self.tween_frame_data.clear()
        self.auxiliary.clear()
        if not keep_pose:
            self.pose_buffer.clear()


class SliderSession:
    """Per-interaction slider state.

    A session owns the caches for one live slider drag or atomic button action.
    It is finished on release, which closes the undo chunk and clears its data.
    """

    def __init__(self, mode, title=None, description="", tooltip=None, tint_color=None):
        self.mode = mode
        self.title = title or "Slider Operation"
        self.description = description
        self.tooltip = tooltip
        self.tint_color = tint_color or COLORS.toolbar.green.hex

        self.targets = SliderTargetContext()
        self.cache = SliderCaches()
        self._is_open = False
        self.preview = False
        self.committing_preview = False
        self.command_preview = False
        self.anim_change = self._new_anim_change()
        self._tint_key = "slider_{}_range".format(self.mode)
        self._tint_range = None

    def begin_preview(self):
        self.preview = True

    def begin_commit(self):
        was_previewing = self.preview
        self.preview = False
        # The preview MAnimCurveChange is undone before the final command write.
        # Keep this flag through the commit so shared writers know that a cached
        # key index may refer to a temporary preview key that must be recreated.
        self.committing_preview = was_previewing
        if was_previewing:
            self.undo_preview_changes()
        self.ensure_undo_open()

    def ensure_undo_open(self):
        """Lazily open the undo chunk on the first operation."""
        if self._is_open:
            return
        chunk_name = tool_common.make_undo_chunk_name(
            tool_id=self.mode,
            title=self.title,
            description=self.description,
            tooltip=self.tooltip,
        )
        cmds.undoInfo(openChunk=True, chunkName=chunk_name)
        self._is_open = True

    def switch_mode(
        self, mode, title=None, description="", tooltip=None, tint_color=None
    ):
        if mode == self.mode:
            return
        self.clear_tint()
        self.mode = mode
        self.title = title or self.title
        self.description = description
        self.tooltip = tooltip
        if tint_color is not None:
            self.tint_color = tint_color
        self._tint_key = "slider_{}_range".format(self.mode)

        # If we switch modes mid-session, we keep the undo chunk open
        # but reset the resolved targets so they are re-calculated for the new mode.
        self.reset()

    def reset(self):
        """Clear drag-scoped caches while keeping the undo chunk open."""
        self.undo_preview_changes()
        self.targets.clear()
        self.cache.clear(keep_pose=True)
        self._tint_range = None

    @staticmethod
    def _new_anim_change():
        change = oma.MAnimCurveChange() if oma is not None else None
        if change is not None:
            try:
                change.setInteractive(True)
            except Exception:
                pass
        return change

    def reset_anim_change(self):
        self.anim_change = self._new_anim_change()

    def undo_preview_changes(self):
        if self.anim_change is None:
            return
        try:
            self.anim_change.undoIt()
        except Exception:
            pass
        self.reset_anim_change()

    def show_tint(self, timerange, color=None, center_line=False):
        if not timerange:
            return
        try:
            tint_range = (round(timerange[0]), round(timerange[1]))
        except (
            RuntimeError,
            ValueError,
            TypeError,
            AttributeError,
            KeyError,
            IndexError,
        ):
            return
        if self._tint_range == tint_range:
            return
        self._tint_range = tint_range
        timeline.show_timeline_tint(
            timerange=tint_range,
            color=color or COLORS.toolbar.green.hex,
            duration_ms=None,
            key=self._tint_key,
            center_line=center_line,
        )

    def show_target_tint(self, timerange):
        self.show_tint(timerange, color=self.tint_color, center_line=False)

    def clear_tint(self):
        if not self._tint_range:
            return
        runtime.get_runtime_manager().clear_managed_widget(self._tint_key)
        self._tint_range = None

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
        cancel_command_preview = self.preview and self.command_preview and self._is_open
        if self.preview:
            self.undo_preview_changes()
        self.preview = False
        self.committing_preview = False
        self.clear_tint()
        if self._is_open:
            try:
                cmds.undoInfo(closeChunk=True)
            except Exception:
                pass
            self._is_open = False
        if cancel_command_preview:
            try:
                with runtime.suppress_undo_notifications():
                    cmds.undo()
            except Exception:
                pass
        self.command_preview = False
        self.targets.clear()
        self.cache.clear()
