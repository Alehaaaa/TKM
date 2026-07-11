import math

from TheKeyMachine.Qt import QtCore, QtGui, QtWidgets

import TheKeyMachine.core.runtimeManager as runtime
from TheKeyMachine.data import icons
from TheKeyMachine.widgets import util as wutil
from TheKeyMachine.widgets import timeline


class AnimationOffsetTimelineTint(timeline.TimelineTint):
    """Persistent animation-offset tint with draggable range handles."""

    rangeChanged = QtCore.Signal(object)

    HANDLE_SIZE = 26
    HANDLE_PROPERTY = "animationOffsetEdge"
    MINIMUM_FRAME_COUNT = 2

    def __init__(self, timerange, color, parent=None, center_line=True, icon=None, full_width=False, icon_scale=1.0, z_index=0):
        self._handles = []
        self._drag_edge = None
        super().__init__(timerange, color, None, parent, center_line, icon, full_width, icon_scale, z_index)
        if self.timerange and not self._full_width and self._parent_widget:
            self._create_handles()

    def eventFilter(self, watched, event):
        if watched in self._handles:
            event_type = event.type()
            if event_type == QtCore.QEvent.MouseButtonPress and event.button() == QtCore.Qt.LeftButton:
                self._drag_edge = int(watched.property(self.HANDLE_PROPERTY))
                watched.setDown(True)
                watched.grabMouse()
                return True
            if event_type == QtCore.QEvent.MouseMove and self._drag_edge is not None:
                self._set_edge_from_parent_x(self._parent_widget.mapFromGlobal(event.globalPos()).x())
                return True
            if event_type == QtCore.QEvent.MouseButtonRelease and self._drag_edge is not None:
                self._set_edge_from_parent_x(self._parent_widget.mapFromGlobal(event.globalPos()).x())
                self._drag_edge = None
                watched.setDown(False)
                watched.releaseMouse()
                return True
        return super().eventFilter(watched, event)

    def _create_handles(self):
        for edge in (0, 1):
            handle = QtWidgets.QToolButton(self._parent_widget)
            handle.setProperty("tkm_floating_widget", True)
            handle.setProperty(self.HANDLE_PROPERTY, edge)
            self._update_handle_hint(handle, edge)
            handle.setFocusPolicy(QtCore.Qt.NoFocus)
            handle.setAutoRaise(True)
            handle.setIcon(QtGui.QIcon(icons.animation_offset_range_handle))
            icon_size = int(wutil.DPI(self.HANDLE_SIZE))
            handle.setIconSize(QtCore.QSize(icon_size, icon_size))
            handle.setStyleSheet(
                "QToolButton { background: transparent; border: none; padding: 0; margin: 0; } "
                "QToolButton:pressed { background-color: #242424; border: none; }"
            )
            handle.installEventFilter(self)
            handle.show()
            self._handles.append(handle)
        self._sync_handles()

    def _handle_rects(self):
        tint_rect = self._current_tint_rect()
        size = max(4, int(wutil.DPI(self.HANDLE_SIZE)))
        y = int(round(tint_rect.bottom() - size * 0.5))
        return tuple(QtCore.QRect(int(round(x - size * 0.5)), y, size, size) for x in (tint_rect.left(), tint_rect.right()))

    def _sync_geometry(self):
        super()._sync_geometry()
        self._sync_handles()

    def _sync_handles(self):
        for handle, geometry in zip(self._handles, self._handle_rects()):
            handle.setGeometry(geometry)
            handle.raise_()

    def _set_edge_from_parent_x(self, x):
        playback_start, playback_end = timeline.get_playback_range()
        width = float(self.width())
        usable_width = width * 0.99
        if usable_width <= 0:
            return
        span = float(playback_end - playback_start + 1)
        normalized_x = (float(x) - width * 0.005) / usable_width
        frame = int(math.floor(playback_start + normalized_x * span))
        frame = max(playback_start, min(playback_end, frame))
        start_frame, end_frame = self.timerange
        minimum_span = self.MINIMUM_FRAME_COUNT - 1

        if self._drag_edge == 0:
            if frame >= end_frame + minimum_span:
                new_range = (end_frame, frame)
                self._swap_handle_roles()
                self._drag_edge = 1
            else:
                new_range = (min(frame, end_frame - minimum_span), end_frame)
        else:
            if frame <= start_frame - minimum_span:
                new_range = (frame, start_frame)
                self._swap_handle_roles()
                self._drag_edge = 0
            else:
                new_range = (start_frame, max(frame, start_frame + minimum_span))

        if new_range != self.timerange:
            self.timerange = new_range
            self.update()
            self._sync_handles()
            self.rangeChanged.emit(new_range)

    def _swap_handle_roles(self):
        self._handles.reverse()
        for edge, handle in enumerate(self._handles):
            handle.setProperty(self.HANDLE_PROPERTY, edge)
            self._update_handle_hint(handle, edge)

    @staticmethod
    def _update_handle_hint(handle, edge):
        boundary = "Start" if edge == 0 else "End"
        hint = "Edit Animation Offset {} Frame".format(boundary)
        handle.setToolTip(hint)
        handle.setStatusTip(hint)

    def delete_tint(self):
        handles, self._handles = self._handles, []
        for handle in handles:
            try:
                handle.setDown(False)
                if QtWidgets.QWidget.mouseGrabber() is handle:
                    handle.releaseMouse()
                handle.removeEventFilter(self)
                handle.hide()
                handle.setParent(None)
                handle.deleteLater()
            except (RuntimeError, AttributeError):
                pass
        self._drag_edge = None
        super().delete_tint()


def show_animation_offset_tint(timerange, color, owner=None, key=None, range_changed=None, center_line=True, icon=None, icon_scale=1.0, z_index=0):
    """Create and register the animation-offset range tint."""
    requested_range = tuple(int(frame) for frame in timerange)
    start_frame, end_frame = requested_range
    playback_start, playback_end = timeline.get_playback_range()
    if end_frame <= start_frame and playback_end > playback_start:
        if start_frame < playback_end:
            end_frame = start_frame + 1
        else:
            start_frame = end_frame - 1
    normalized_range = (start_frame, end_frame)
    widget = AnimationOffsetTimelineTint(
        timerange=normalized_range,
        color=color,
        full_width=normalized_range == timeline.get_playback_range(),
        center_line=center_line,
        icon=icon,
        icon_scale=icon_scale,
        z_index=z_index,
    )
    if range_changed is not None:
        widget.rangeChanged.connect(range_changed)
        if normalized_range != requested_range:
            range_changed(normalized_range)
    return runtime.get_runtime_manager().register_managed_widget(widget, key=key, owner=owner)
