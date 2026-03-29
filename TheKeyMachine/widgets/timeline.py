from dataclasses import dataclass

from maya import cmds, mel, OpenMayaUI as omui

try:
    from PySide6 import QtCore, QtGui, QtWidgets
except Exception:
    from PySide2 import QtCore, QtGui, QtWidgets

import TheKeyMachine.core.runtime_manager as runtime
from TheKeyMachine.tools import colors as toolColors
from TheKeyMachine.widgets import util


@dataclass(frozen=True)
class TimeContext:
    mode: str
    start_frame: int
    end_frame: int
    frames: tuple = ()

    @property
    def timerange(self):
        return (self.start_frame, self.end_frame)


def _playback_slider_name():
    return mel.eval("$tmpVar=$gPlayBackSlider")


def _normalize_slider_range(range_array):
    start = int(range_array[0])
    end = int(range_array[1] - 1)
    if end < start:
        end = start
    return start, end


def get_graph_editor_selected_frames():
    frames = cmds.keyframe(query=True, selected=True, tc=True) or []
    frames = sorted({int(frame) for frame in frames})
    return frames


def get_selected_time_slider_range():
    time_range = cmds.timeControl(_playback_slider_name(), q=True, rangeArray=True)
    current_time = int(cmds.currentTime(query=True))
    if (time_range[1] - time_range[0]) > 1 or (time_range[0] != current_time and time_range[1] != current_time + 1):
        return _normalize_slider_range(time_range)
    return None


def get_playback_range():
    return (
        int(cmds.playbackOptions(query=True, minTime=True)),
        int(cmds.playbackOptions(query=True, maxTime=True)),
    )


def get_current_frame_range():
    current = int(cmds.currentTime(query=True))
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


def resolve_time_context(default_mode="all_animation"):
    graph_editor_frames = get_graph_editor_selected_frames()
    if graph_editor_frames:
        return TimeContext(
            mode="graph_editor_keys",
            start_frame=graph_editor_frames[0],
            end_frame=graph_editor_frames[-1],
            frames=tuple(graph_editor_frames),
        )

    time_slider_range = get_selected_time_slider_range()
    if time_slider_range:
        return TimeContext(
            mode="time_slider_range",
            start_frame=time_slider_range[0],
            end_frame=time_slider_range[1],
            frames=tuple(range(time_slider_range[0], time_slider_range[1] + 1)),
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


class TimelineTint(QtWidgets.QWidget):
    def __init__(self, timerange, color=(200, 120, 200), duration_ms=200, parent=None, center_line=False, icon_path=None, full_width=False):
        self._full_width = bool(full_width)
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
        self.icon_path = icon_path
        self._icon = QtGui.QPixmap(icon_path) if icon_path else QtGui.QPixmap()
        self.setAttribute(QtCore.Qt.WA_TransparentForMouseEvents, True)
        self.setFocusPolicy(QtCore.Qt.NoFocus)
        parent_widget.installEventFilter(self)

        self._sync_geometry()
        self.show()

        if not self._persistent:
            lifetime_ms = max(300, int(duration_ms or 0))
            self._timer = QtCore.QTimer(self)
            self._timer.setSingleShot(True)
            self._timer.timeout.connect(self.delete_tint)
            self._timer.start(lifetime_ms)

    @classmethod
    def get_timeline_widget(cls, full_width=False):
        timeline_name = _playback_slider_name()
        ptr = omui.MQtUtil.findControl(timeline_name) or omui.MQtUtil.findLayout(timeline_name) or omui.MQtUtil.findMenuItem(timeline_name)
        if ptr:
            widget = util.get_maya_qt(ptr, QtWidgets.QWidget)
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
            line_color = QtGui.QColor(255, 244, 196, 235)
            line_pen = QtGui.QPen(line_color)
            line_pen.setWidth(max(2, int(util.DPI(2))))
            painter.setPen(line_pen)
            line_y = self.height() * 0.5
            painter.drawLine(QtCore.QPointF(rect.left(), line_y), QtCore.QPointF(rect.right(), line_y))

        if not self._icon.isNull():
            icon_size = min(util.DPI(18), int(max(12, rect.width() - util.DPI(6))), max(12, self.height() - util.DPI(4)))
            icon_rect = QtCore.QRectF(
                rect.center().x() - (icon_size * 0.5),
                (self.height() - icon_size) * 0.5,
                icon_size,
                icon_size,
            )
            painter.drawPixmap(icon_rect.toRect(), self._icon)

    def delete_tint(self):
        try:
            if self._parent_widget and util.is_valid_widget(self._parent_widget):
                self._parent_widget.removeEventFilter(self)
        except Exception:
            pass
        try:
            self.setParent(None)
            self.deleteLater()
        except RuntimeError:
            pass

    def eventFilter(self, watched, event):
        if watched is self._parent_widget and event.type() in (
            QtCore.QEvent.Resize,
            QtCore.QEvent.Move,
            QtCore.QEvent.Show,
            QtCore.QEvent.LayoutRequest,
        ):
            self._sync_geometry()
        return super().eventFilter(watched, event)

    def _sync_geometry(self):
        if not self._parent_widget or not util.is_valid_widget(self._parent_widget):
            return
        new_geometry = self._parent_widget.rect()
        if self.geometry() != new_geometry:
            self.setGeometry(new_geometry)
        self.update()

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


def show_timeline_tint(timerange=None, color=None, duration_ms=200, owner=None, key=None, center_line=False, icon_path=None):
    color = color or _default_tint_color()
    context = timerange or resolve_time_context(default_mode="all_animation").timerange
    full_width = _is_full_playback_timerange(context)
    widget = TimelineTint(
        timerange=context,
        color=color,
        duration_ms=duration_ms,
        center_line=center_line,
        icon_path=icon_path,
        full_width=full_width,
    )
    return runtime.get_runtime_manager().register_managed_widget(widget, key=key, owner=owner)


def show_timeline_context(default_mode="all_animation", color=None, duration_ms=200, owner=None, key=None, center_line=False, icon_path=None):
    context = resolve_time_context(default_mode=default_mode)
    return show_timeline_tint(
        timerange=context.timerange,
        color=color,
        duration_ms=duration_ms,
        owner=owner,
        key=key,
        center_line=center_line,
        icon_path=icon_path,
    )


def clear_timeline_tint(key):
    runtime.get_runtime_manager().clear_managed_widget(key)


def begin_timeline_tint(timerange=None, color=None, owner=None, key=None, min_duration=300, center_line=False, icon_path=None):
    widget = show_timeline_tint(
        timerange=timerange,
        color=color,
        duration_ms=None,
        owner=owner,
        key=key,
        center_line=center_line,
        icon_path=icon_path,
    )
    return TimelineTintSession(widget, key=key, min_duration=min_duration, parent=owner)


def begin_timeline_context(default_mode="all_animation", color=None, owner=None, key=None, min_duration=300, center_line=False, icon_path=None):
    context = resolve_time_context(default_mode=default_mode)
    return begin_timeline_tint(
        timerange=context.timerange,
        color=color,
        owner=owner,
        key=key,
        min_duration=min_duration,
        center_line=center_line,
        icon_path=icon_path,
    )


def _default_tint_color():
    return toolColors.gray


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
    if isinstance(color, QtGui.QColor):
        qcolor = QtGui.QColor(color)
    elif hasattr(color, "base") and hasattr(color.base, "hex"):
        qcolor = QtGui.QColor(color.base.hex)
    elif hasattr(color, "hex"):
        qcolor = QtGui.QColor(color.hex)
    elif isinstance(color, (int, float)):
        hue = int(color) % 360
        qcolor = QtGui.QColor.fromHsv(hue, 75, 242, 52)
    else:
        rgb = list(color[:3])
        alpha = int(color[3]) if len(color) > 3 else 52
        qcolor = QtGui.QColor(rgb[0], rgb[1], rgb[2], alpha)

    if qcolor.alpha() == 255:
        qcolor.setAlpha(52)
    return qcolor
