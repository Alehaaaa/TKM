from contextlib import contextmanager
from dataclasses import dataclass
import math

from maya import cmds, OpenMayaUI as maya_api

from TheKeyMachine.core.Qt import QtCore, QtGui, QtWidgets  # type: ignore

from TheKeyMachine.maya import runtime as maya_runtime
from TheKeyMachine.core import runtime
from TheKeyMachine.maya import selection
from TheKeyMachine.data.colors import COLORS
from TheKeyMachine.ui.widgets import util as wutil


@dataclass(frozen=True)
class TimeContext:
    mode: str
    start_frame: float
    end_frame: float
    frames: tuple = ()

    @property
    def timerange(self):
        return (self.start_frame, self.end_frame)


def get_playback_range():
    return (
        int(cmds.playbackOptions(query=True, minTime=True)),
        int(cmds.playbackOptions(query=True, maxTime=True)),
    )


def get_current_frame_range():
    current = float(cmds.currentTime(query=True))
    return current, current


def get_frames_timerange(frames):
    normalized_frames = []
    for frame in frames or []:
        try:
            normalized_frames.append(int(frame))
        except Exception:
            continue
    if not normalized_frames:
        return None
    return min(normalized_frames), max(normalized_frames)


def get_animation_data_timerange(animation_data, frame_key="keyframes"):
    frames = []
    for channel_map in (animation_data or {}).values():
        if not isinstance(channel_map, dict):
            continue
        for anim_data in channel_map.values():
            if not isinstance(anim_data, dict):
                continue
            frames.extend(anim_data.get(frame_key) or [])
    return get_frames_timerange(frames)


_active_frame_picker = None
FRAME_PICKER_COLOR = (235, 235, 235, 125)
_TIME_SLIDER_UPDATE_DEPTH = 0
def _set_native_selected_range(start_frame, end_frame):
    """Set the visible range endpoints through Maya's native 2024+ API."""
    cmds.playbackOptions(
        edit=True,
        selectionStartTime=start_frame,
        selectionEndTime=end_frame,
        selectionVisible=True,
    )


class TimelineFramePicker(QtCore.QObject):
    """Preview timeline frames while scrubbing and commit one on release."""

    TINT_KEY = "slider_frame_picker"

    def __init__(
        self,
        callback,
        owner=None,
        color=None,
        cancel_callback=None,
        preview_callback=None,
    ):
        super().__init__(owner or runtime.get_runtime_manager())
        self._callback = callback
        self._cancel_callback = cancel_callback
        self._preview_callback = preview_callback
        self._color = color or FRAME_PICKER_COLOR
        self._timeline = TimelineTint.get_timeline_widget()
        self._frame = None
        self._previewed_frame = None
        self._scrubbing = False
        if self._timeline:
            self._timeline.setMouseTracking(True)
            self._timeline.installEventFilter(self)
            app = QtWidgets.QApplication.instance()
            if app:
                app.installEventFilter(self)

    def cancel(self, notify=True):
        global _active_frame_picker
        self._scrubbing = False
        self._clear_frame()
        app = QtWidgets.QApplication.instance()
        if app:
            try:
                app.removeEventFilter(self)
            except (RuntimeError, TypeError):
                pass
        if self._timeline and wutil.is_valid_widget(self._timeline):
            try:
                self._timeline.removeEventFilter(self)
            except (RuntimeError, TypeError):
                pass
        self._timeline = None
        if _active_frame_picker is self:
            _active_frame_picker = None
        if notify and self._cancel_callback:
            self._cancel_callback()
        self.deleteLater()

    @property
    def available(self):
        return self._timeline is not None and wutil.is_valid_widget(self._timeline)

    @staticmethod
    def _global_pos(event):
        if hasattr(event, "globalPosition"):
            return event.globalPosition().toPoint()
        if hasattr(event, "globalPos"):
            return event.globalPos()
        return QtGui.QCursor.pos()

    def _timeline_pos(self, event):
        if not self._timeline or not wutil.is_valid_widget(self._timeline):
            return None
        return self._timeline.mapFromGlobal(self._global_pos(event))

    def _frame_at(self, pos):
        if not self._timeline or self._timeline.width() <= 0:
            return None
        start, end = get_playback_range()
        span = float(end - start + 1)
        usable_width = float(self._timeline.width()) * 0.99
        x = max(0.0, min(usable_width - 0.001, float(pos.x()) - float(self._timeline.width()) * 0.005))
        return max(start, min(end, int(start + (x / usable_width) * span)))

    def _set_frame(self, frame, preview=False):
        if frame is None:
            return
        if frame != self._frame:
            self._frame = frame
            show_timeline_tint(
                timerange=(frame, frame), color=self._color, duration_ms=None,
                key=self.TINT_KEY, center_line=False, z_index=1,
            )
        if preview and frame != self._previewed_frame:
            self._previewed_frame = frame
            if self._preview_callback:
                self._preview_callback(frame)

    def _clear_frame(self):
        runtime.get_runtime_manager().clear_managed_widget(self.TINT_KEY)
        self._frame = None

    def _commit_frame(self, frame):
        self._scrubbing = False
        if frame is None:
            self.cancel()
            return
        self._set_frame(frame, preview=True)
        try:
            self._callback(frame)
        finally:
            self.cancel(notify=False)

    def eventFilter(self, watched, event):
        event_type = event.type()
        if event_type == QtCore.QEvent.KeyPress and event.key() == QtCore.Qt.Key_Escape:
            self.cancel()
            event.accept()
            return True

        mouse_events = (
            QtCore.QEvent.MouseMove,
            QtCore.QEvent.MouseButtonPress,
            QtCore.QEvent.MouseButtonRelease,
            QtCore.QEvent.MouseButtonDblClick,
        )
        if event_type in mouse_events:
            pos = self._timeline_pos(event)
            inside = pos is not None and self._timeline.rect().contains(pos)
            if event_type == QtCore.QEvent.MouseMove:
                if self._scrubbing and pos is not None:
                    self._set_frame(self._frame_at(pos), preview=True)
                    event.accept()
                    return True
                if inside:
                    self._set_frame(self._frame_at(pos))
                elif self._frame is not None:
                    self._clear_frame()
                return False

            is_left_button = event.button() == QtCore.Qt.LeftButton
            if inside and is_left_button and event_type == QtCore.QEvent.MouseButtonPress:
                self._scrubbing = True
                self._set_frame(self._frame_at(pos), preview=True)
                event.accept()
                return True

            if is_left_button and event_type == QtCore.QEvent.MouseButtonRelease and self._scrubbing:
                frame = self._frame_at(pos) if pos is not None else self._frame
                self._commit_frame(frame)
                event.accept()
                return True

            if inside:
                event.accept()
                return True

        if (
            watched is self._timeline
            and event_type == QtCore.QEvent.Leave
            and self._frame is not None
            and not self._scrubbing
        ):
            self._clear_frame()
        return False


def shutdown():
    """Cancel any in-flight frame picker before an in-process module reload.

    ``TimelineFramePicker.__init__`` installs an app-level event filter
    that only ``cancel()`` removes (see its ``app.installEventFilter(self)``
    above). A reload landing mid-drag on the timeline scrubber would
    otherwise leave that filter permanently installed on Maya's persistent
    QApplication, referencing a picker instance whose module is about to be
    purged. ``notify=False`` matches ``_commit_frame``'s own use of a quiet
    cancel -- the owning tool is being torn down, not asking to abort.
    """
    global _active_frame_picker
    if _active_frame_picker is not None:
        _active_frame_picker.cancel(notify=False)
        _active_frame_picker = None


def begin_frame_picker(
    callback,
    owner=None,
    color=None,
    cancel_callback=None,
    preview_callback=None,
):
    """Begin previewing snapped playback frames, committing one on release."""
    global _active_frame_picker
    if _active_frame_picker is not None:
        _active_frame_picker.cancel()
    _active_frame_picker = TimelineFramePicker(
        callback,
        owner=owner,
        color=color,
        cancel_callback=cancel_callback,
        preview_callback=preview_callback,
    )
    if not _active_frame_picker.available:
        _active_frame_picker.cancel()
        return None
    return _active_frame_picker


def resolve_time_context(default_mode="all_animation", graph_frames=None):
    time_slider_range = selection.get_selected_time_range()
    if time_slider_range:
        start_frame, end_frame = time_slider_range
        first_whole = int(math.ceil(start_frame))
        last_whole = int(math.floor(end_frame))
        selected_frames = (
            tuple(range(first_whole, last_whole + 1))
            if last_whole >= first_whole
            else (start_frame, end_frame)
        )
        return TimeContext(
            mode="time_slider_range",
            start_frame=start_frame,
            end_frame=end_frame,
            frames=selected_frames,
        )

    graph_editor_frames = (
        selection.get_graph_editor_selected_frames()
        if graph_frames is None
        else sorted(set(float(frame) for frame in graph_frames))
    )
    if graph_editor_frames:
        return TimeContext(
            mode="graph_editor_keys",
            start_frame=graph_editor_frames[0],
            end_frame=graph_editor_frames[-1],
            frames=tuple(graph_editor_frames),
        )

    if default_mode == "current_frame":
        start_frame, end_frame = get_current_frame_range()
        return TimeContext(mode="current_frame", start_frame=start_frame, end_frame=end_frame, frames=(start_frame,))

    start_frame, end_frame = get_playback_range()
    return TimeContext(
        mode="all_animation",
        start_frame=start_frame,
        end_frame=end_frame,
        frames=tuple(range(start_frame, end_frame + 1)),
    )


def _time_slider_input_context():
    app = QtWidgets.QApplication.instance()
    slider = TimelineTint.get_timeline_widget()
    if not app or not slider or slider.width() <= 0:
        return None

    playback_start = float(cmds.playbackOptions(query=True, minTime=True))
    playback_end = float(cmds.playbackOptions(query=True, maxTime=True))
    span = playback_end - playback_start + 1.0
    if span <= 0:
        return None

    width = float(slider.width())
    step = (width - (width * 0.01)) / span

    def position(frame):
        x = int((float(frame) - playback_start) * step + (width * 0.005))
        return QtCore.QPoint(x, int(slider.height() / 2.0))

    return app, slider, playback_start, playback_end, position


def _send_time_slider_mouse_event(app, slider, event_type, position, button, buttons, modifier):
    event = QtGui.QMouseEvent(event_type, position, button, buttons, modifier)
    app.sendEvent(slider, event)


@contextmanager
def suspend_time_slider_updates():
    """Prevent intermediate time-slider redraws and restore its prior state."""
    global _TIME_SLIDER_UPDATE_DEPTH
    if _TIME_SLIDER_UPDATE_DEPTH:
        _TIME_SLIDER_UPDATE_DEPTH += 1
        try:
            yield
        finally:
            _TIME_SLIDER_UPDATE_DEPTH -= 1
        return

    _TIME_SLIDER_UPDATE_DEPTH = 1
    slider_name = None
    was_managed = True
    manage_changed = False
    refresh_suspended = False
    try:
        slider_name = selection.get_playback_slider()
        cmds.refresh(suspend=True)
        refresh_suspended = True
        queried_state = cmds.timeControl(slider_name, query=True, manage=True)
        if queried_state is not None:
            was_managed = bool(queried_state)
        cmds.timeControl(slider_name, edit=True, manage=False)
        manage_changed = True
        yield
    finally:
        try:
            if manage_changed and slider_name:
                cmds.timeControl(slider_name, edit=True, manage=was_managed)
        finally:
            if refresh_suspended:
                cmds.refresh(suspend=False)
            _TIME_SLIDER_UPDATE_DEPTH = 0


def _restore_current_frame(current_frame, playback_start):
    """Force Maya to repaint its range without leaving the playhead displaced."""
    if cmds.currentTime(query=True) == current_frame:
        return
    adjacent_frame = current_frame - 1 if current_frame > playback_start else current_frame + 1
    cmds.currentTime(adjacent_frame, edit=True)
    cmds.currentTime(current_frame, edit=True)


def _clear_selected_range_input(context, selected_range):
    app, slider, playback_start, playback_end, position = context
    if selected_range:
        start_frame, end_frame = selected_range
        space_before = start_frame - playback_start
        space_after = playback_end - end_frame
        clear_frame = (
            end_frame + (space_after * 0.5)
            if space_after >= space_before
            else playback_start + (space_before * 0.5)
        )
    else:
        clear_frame = cmds.currentTime(query=True)

    clear_position = position(clear_frame)
    for event_type, button, buttons in (
        (QtCore.QEvent.MouseButtonPress, QtCore.Qt.LeftButton, QtCore.Qt.LeftButton),
        (QtCore.QEvent.MouseButtonRelease, QtCore.Qt.LeftButton, QtCore.Qt.LeftButton),
    ):
        _send_time_slider_mouse_event(
            app, slider, event_type, clear_position, button, buttons, QtCore.Qt.NoModifier
        )


def clear_selected_range():
    """Clear the highlighted time-slider range without changing object selection."""
    if maya_runtime.supports_playback_selection():
        cmds.playbackOptions(edit=True, selectionVisible=False)
        return True

    context = _time_slider_input_context()
    if not context:
        return False

    current_frame = cmds.currentTime(query=True)
    selected_range = selection.get_selected_time_range()
    with suspend_time_slider_updates():
        _clear_selected_range_input(context, selected_range)
        context[0].processEvents()
        playback_start = context[2]
        _restore_current_frame(current_frame, playback_start)
    return True


def move_selected_range(offset):
    """Move the existing highlighted range without changing object selection."""
    try:
        offset = float(offset)
    except (TypeError, ValueError):
        return False
    if not offset:
        return False

    if maya_runtime.supports_playback_selection():
        if not cmds.playbackOptions(query=True, selectionVisible=True):
            return False
        start_frame = cmds.playbackOptions(query=True, selectionStartTime=True)
        end_frame = cmds.playbackOptions(query=True, selectionEndTime=True)
        cmds.playbackOptions(
            edit=True,
            selectionStartTime=start_frame + offset,
            selectionEndTime=end_frame + offset,
            selectionVisible=True,
        )
        return True

    selected_range = selection.get_selected_time_range()
    if not selected_range:
        return False
    start_frame, end_frame = selected_range
    moved_start = start_frame + offset
    moved_end = end_frame + offset
    return select_time_slider_range((moved_start, moved_end))


def select_time_slider_range(frames):
    """Highlight the inclusive range covered by ``frames`` on Maya's time slider."""
    frames = list(frames or [])
    if not frames:
        return False

    start_frame, end_frame = min(frames), max(frames)
    if maya_runtime.supports_playback_selection():
        _set_native_selected_range(start_frame, end_frame)
        return True

    context = _time_slider_input_context()
    if not context:
        return False
    app, slider, playback_start, _playback_end, position = context

    start_position = position(start_frame + 1)
    # Maya reports rangeArray's end one frame past the inclusive selection.
    end_position = position(end_frame + 1)
    current_frame = cmds.currentTime(query=True)

    with suspend_time_slider_updates():
        _clear_selected_range_input(context, (start_frame, end_frame))
        # Maya caches the time-slider hover position as its drag origin.
        # Prime it explicitly so backward drags do not retain the old end.
        _send_time_slider_mouse_event(
            app, slider, QtCore.QEvent.MouseMove, start_position,
            QtCore.Qt.NoButton, QtCore.Qt.NoButton, QtCore.Qt.ShiftModifier,
        )
        _send_time_slider_mouse_event(
            app, slider, QtCore.QEvent.MouseButtonPress, start_position,
            QtCore.Qt.LeftButton, QtCore.Qt.LeftButton, QtCore.Qt.ShiftModifier,
        )
        _send_time_slider_mouse_event(
            app, slider, QtCore.QEvent.MouseMove, end_position,
            QtCore.Qt.LeftButton, QtCore.Qt.LeftButton, QtCore.Qt.ShiftModifier,
        )
        _send_time_slider_mouse_event(
            app, slider, QtCore.QEvent.MouseButtonRelease, end_position,
            QtCore.Qt.LeftButton, QtCore.Qt.LeftButton, QtCore.Qt.ShiftModifier,
        )
        app.processEvents()
        _restore_current_frame(current_frame, playback_start)
    return True


class TimelineTint(QtWidgets.QWidget):
    def __init__(
        self,
        timerange,
        color=(200, 120, 200),
        duration_ms=200,
        parent=None,
        center_line=False,
        icon=None,
        full_width=False,
        icon_scale=1.0,
        z_index=0,
    ):
        self._full_width = bool(full_width)
        self._z_index = int(z_index or 0)
        parent_widget = parent or self.get_timeline_widget(full_width=self._full_width)
        super().__init__(parent_widget)
        self._parent_widget = parent_widget

        if not parent_widget:
            self.timerange = None
            self._persistent = True
            return

        start_frame, end_frame = timerange
        self.timerange = (int(start_frame), int(end_frame))
        self._persistent = duration_ms is None

        self.color = _normalize_tint_color(color)
        self.center_line = bool(center_line)
        self.icon = icon
        self.icon_scale = max(0.5, float(icon_scale or 1.0))
        self._icon = QtGui.QPixmap(icon) if icon else QtGui.QPixmap()
        self.setAttribute(QtCore.Qt.WA_TransparentForMouseEvents, True)
        self.setFocusPolicy(QtCore.Qt.NoFocus)
        parent_widget.installEventFilter(self)

        self._sync_geometry()
        self.show()
        self._sync_z_order()

        if not self._persistent:
            lifetime_ms = max(300, int(duration_ms or 0))
            self._timer = QtCore.QTimer(self)
            self._timer.setSingleShot(True)
            self._timer.timeout.connect(self.delete_tint)
            self._timer.start(lifetime_ms)

    @classmethod
    def get_timeline_widget(cls, full_width=False):
        timeline_name = selection.get_playback_slider()
        ptr = maya_api.MQtUtil.findControl(timeline_name) or maya_api.MQtUtil.findLayout(timeline_name) or maya_api.MQtUtil.findMenuItem(timeline_name)
        if ptr:
            widget = wutil.get_maya_qt(ptr, QtWidgets.QWidget)
            if widget and full_width:
                return widget.parentWidget() or widget
            return widget
        return None

    def paintEvent(self, event):
        if not self.timerange:
            return

        painter = QtGui.QPainter(self)
        rect = self._current_tint_rect()
        if rect.isEmpty():
            return

        pen = QtGui.QPen(self.color)
        pen.setWidth(max(1, int(rect.height())))
        painter.setPen(pen)
        painter.fillRect(rect, QtGui.QBrush(self.color))

        if self.center_line:
            line_color = _light_tint_line_color(self.color)
            line_pen = QtGui.QPen(line_color)
            line_pen.setWidth(max(2, int(wutil.DPI(2))))
            painter.setPen(line_pen)
            line_y = self.height() * 0.5
            painter.drawLine(QtCore.QPointF(rect.left(), line_y), QtCore.QPointF(rect.right(), line_y))

        if not self._icon.isNull():
            base_icon_size = min(wutil.DPI(18), int(max(12, rect.width() - wutil.DPI(6))), max(12, self.height() - wutil.DPI(4)))
            icon_size = int(max(12, round(base_icon_size * self.icon_scale)))
            icon_size = min(icon_size, int(max(12, rect.width() - wutil.DPI(2))), int(max(12, self.height() - wutil.DPI(2))))
            icon_rect = QtCore.QRectF(
                rect.center().x() - (icon_size * 0.5),
                (self.height() - icon_size) * 0.5,
                icon_size,
                icon_size,
            )
            painter.drawPixmap(icon_rect.toRect(), self._icon)

    def delete_tint(self):
        try:
            if self._parent_widget and wutil.is_valid_widget(self._parent_widget):
                self._parent_widget.removeEventFilter(self)
        except Exception:
            pass
        runtime.delete_widget(self)

    def eventFilter(self, watched, event):
        if watched is self._parent_widget and event.type() in (
            QtCore.QEvent.Resize,
            QtCore.QEvent.Move,
            QtCore.QEvent.Show,
            QtCore.QEvent.LayoutRequest,
            QtCore.QEvent.Paint,
            QtCore.QEvent.UpdateRequest,
        ):
            self._sync_geometry()
        return super().eventFilter(watched, event)

    def _sync_geometry(self):
        if not self._parent_widget or not wutil.is_valid_widget(self._parent_widget):
            return
        new_geometry = self._parent_widget.rect()
        if self.geometry() != new_geometry:
            self.setGeometry(new_geometry)
        self._sync_z_order()
        self.update()

    def _sync_z_order(self):
        if self._z_index < 0:
            self._stack_under_managed_tints()
        elif self._z_index > 0:
            self.raise_()

    def _stack_under_managed_tints(self):
        parent = self.parentWidget()
        if parent is None:
            return
        for sibling in parent.findChildren(TimelineTint):
            if sibling is self:
                continue
            if getattr(sibling, "_z_index", 0) >= 0:
                try:
                    self.stackUnder(sibling)
                except RuntimeError:
                    pass
                return

    def _current_tint_rect(self):
        if self._full_width:
            return QtCore.QRectF(self.rect())

        start = cmds.playbackOptions(q=True, minTime=True)
        end = cmds.playbackOptions(q=True, maxTime=True)
        span = float(end - start + 1)
        if span <= 0:
            return QtCore.QRectF()

        total_width = float(self.width())
        step = (total_width - (total_width * 0.01)) / span

        start_frame, end_frame = self.timerange
        rect_start = (start_frame - start) * step + (total_width * 0.005)
        rect_end = (end_frame + 1 - start) * step + (total_width * 0.005)
        return QtCore.QRectF(QtCore.QPointF(rect_start, 0), QtCore.QPointF(rect_end, self.height()))


class TimelineTintSession(QtCore.QObject):
    def __init__(self, widget, key=None, min_duration=300, parent=None):
        session_parent = parent or runtime.get_runtime_manager()
        super().__init__(session_parent)
        self._widget = widget
        self._key = key
        self._min_duration = max(300, int(min_duration or 0))
        self._finished = False
        self._elapsed = QtCore.QElapsedTimer()
        self._elapsed.start()
        self._finish_timer = QtCore.QTimer(self)
        self._finish_timer.setSingleShot(True)
        self._finish_timer.timeout.connect(self._clear_widget)

    def finish(self):
        if self._finished:
            return
        self._finished = True
        remaining = max(0, self._min_duration - self._elapsed.elapsed())
        if remaining:
            self._finish_timer.start(remaining)
        else:
            self._clear_widget()

    def _clear_widget(self):
        try:
            self._finish_timer.stop()
        except Exception:
            pass
        if self._key:
            runtime.get_runtime_manager().clear_managed_widget(self._key)
        elif self._widget is not None:
            try:
                self._widget.delete_tint()
            except Exception:
                pass
        self._widget = None
        try:
            self.deleteLater()
        except Exception:
            pass


def show_timeline_tint(
    timerange=None, color=None, duration_ms=200, owner=None, key=None, center_line=False, icon=None, icon_scale=1.0, z_index=0
):
    color = color or _default_tint_color()
    context = timerange or resolve_time_context(default_mode="all_animation").timerange
    full_width = _is_full_playback_timerange(context)
    widget = TimelineTint(
        timerange=context,
        color=color,
        duration_ms=duration_ms,
        center_line=center_line,
        icon=icon,
        full_width=full_width,
        icon_scale=icon_scale,
        z_index=z_index,
    )
    return runtime.get_runtime_manager().register_managed_widget(widget, key=key, owner=owner)


def show_timeline_context(
    default_mode="all_animation", color=None, duration_ms=200, owner=None, key=None, center_line=False, icon=None, icon_scale=1.0, z_index=0
):
    context = resolve_time_context(default_mode=default_mode)
    return show_timeline_tint(
        timerange=context.timerange,
        color=color,
        duration_ms=duration_ms,
        owner=owner,
        key=key,
        center_line=center_line,
        icon=icon,
        icon_scale=icon_scale,
        z_index=z_index,
    )


def begin_timeline_tint(
    timerange=None, color=None, owner=None, key=None, min_duration=300, center_line=False, icon=None, icon_scale=1.0, z_index=0
):
    widget = show_timeline_tint(
        timerange=timerange,
        color=color,
        duration_ms=None,
        owner=owner,
        key=key,
        center_line=center_line,
        icon=icon,
        icon_scale=icon_scale,
        z_index=z_index,
    )
    return TimelineTintSession(widget, key=key, min_duration=min_duration, parent=owner)


def begin_timeline_context(
    default_mode="all_animation", color=None, owner=None, key=None, min_duration=300, center_line=False, icon=None, icon_scale=1.0, z_index=0
):
    context = resolve_time_context(default_mode=default_mode)
    return begin_timeline_tint(
        timerange=context.timerange,
        color=color,
        owner=owner,
        key=key,
        min_duration=min_duration,
        center_line=center_line,
        icon=icon,
        icon_scale=icon_scale,
        z_index=z_index,
    )


def _default_tint_color():
    return COLORS.toolbar.gray.hex


def _is_full_playback_timerange(timerange):
    if not timerange:
        return False
    try:
        start_frame, end_frame = int(timerange[0]), int(timerange[1])
    except Exception:
        return False
    playback_start, playback_end = get_playback_range()
    return start_frame == playback_start and end_frame == playback_end


def _normalize_tint_color(color):
    default_alpha = 80
    if isinstance(color, QtGui.QColor):
        qcolor = QtGui.QColor(color)
    elif isinstance(color, str):
        qcolor = QtGui.QColor(color)
    else:
        base_variant_hex = _resolve_tint_variant_hex(color, preferred_shades=("base",))
        if base_variant_hex is not None:
            qcolor = QtGui.QColor(base_variant_hex)
        elif isinstance(color, (int, float)):
            hue = int(color) % 360
            qcolor = QtGui.QColor.fromHsv(hue, 75, 242, default_alpha)
        else:
            try:
                channels = list(color)
            except TypeError:
                channels = []
            if len(channels) >= 3:
                alpha = int(channels[3]) if len(channels) > 3 else default_alpha
                qcolor = QtGui.QColor(
                    int(channels[0]),
                    int(channels[1]),
                    int(channels[2]),
                    alpha,
                )
            else:
                qcolor = QtGui.QColor()

    if not qcolor.isValid():
        qcolor = QtGui.QColor(_default_tint_color())
    if qcolor.alpha() == 255:
        qcolor.setAlpha(default_alpha)
    qcolor.setAlpha(max(0, min(255, int(round(qcolor.alpha() * 0.8)))))
    return qcolor


def _light_tint_line_color(color):
    variant_hex = _resolve_tint_variant_hex(color, preferred_shades=("light", "base", "dark"))
    if variant_hex is not None:
        qcolor = QtGui.QColor(variant_hex)
        qcolor.setAlpha(235)
        return qcolor

    qcolor = QtGui.QColor(color)
    if not qcolor.isValid():
        return QtGui.QColor(255, 244, 196, 235)

    line_color = qcolor.lighter(185)
    line_color.setAlpha(235)
    return line_color


def _resolve_tint_variant_hex(color, preferred_shades=("base",)):
    if color is None:
        return None

    family_name = getattr(color, "family", None)
    family_color = (
        COLORS.selection.families.get(family_name)
        if family_name
        else None
    )
    for shade in preferred_shades:
        variant = (
            family_color
            if shade == "base"
            else getattr(family_color, shade, None)
        )
        variant_hex = _color_hex(variant)
        if variant_hex is not None:
            return variant_hex

    return _color_hex(color)


def _color_hex(color):
    if isinstance(color, str):
        return color
    value = getattr(color, "hex", None)
    return value if isinstance(value, str) else None
