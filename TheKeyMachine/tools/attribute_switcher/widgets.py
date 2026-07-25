from __future__ import division
# -*- coding: utf-8 -*-

from TheKeyMachine.core.Qt import QtCore, QtGui, QtWidgets

from TheKeyMachine.data.colors import COLORS
from TheKeyMachine.data import icons
from TheKeyMachine.tools.common import FloatingToolWindowMixin
from TheKeyMachine.tools.attribute_switcher import controller as switchController
from TheKeyMachine.tools.attribute_switcher.controller import (
    ATTRIBUTE_SWITCHER_GEOMETRY_KEY,
    ATTRIBUTE_SWITCHER_SETTINGS_NAMESPACE,
)
from TheKeyMachine.widgets import customDialogs as cd
from TheKeyMachine.widgets import customWidgets as cw
from TheKeyMachine.widgets import util as wutil


UI_COLOR = COLORS.ui
ACCENT_MAIN_COLOR = COLORS.selection.green
ACCENT_DARK_COLOR = ACCENT_MAIN_COLOR.dark
ACCENT_LIGHT_COLOR = ACCENT_MAIN_COLOR.light

COLOR_BG_MAIN = UI_COLOR.dark_gray.hex
COLOR_BG_POPUP = UI_COLOR.darkest_gray.hex
COLOR_BG_TRACK = UI_COLOR.darker_gray.hex
COLOR_ACCENT_DARK = ACCENT_DARK_COLOR.hex
COLOR_ACCENT_MAIN = ACCENT_MAIN_COLOR.hex
COLOR_ACCENT_LIGHT = ACCENT_LIGHT_COLOR.hex
COLOR_ACCENT_HOVER = ACCENT_MAIN_COLOR.hover.hex
COLOR_ACCENT_WHITE = ACCENT_LIGHT_COLOR.hover.hex
COLOR_TEXT_MAIN = UI_COLOR.darker_gray.hex
COLOR_TEXT_SECONDARY = UI_COLOR.dark_white.hex
COLOR_BLEND_MULTI = ACCENT_DARK_COLOR.hover.hex

ATTRIBUTE_SWITCHER_GLOBE_IMAGE = icons.globe


def _option_button_stylesheet(compact=False):
    """Return the shared enum-option style used by both switch popups."""
    if compact:
        return (
            "QPushButton { color: %s; background: %s; text-align: left; "
            "padding: %spx; border-radius: %spx; border: none; }"
            "QPushButton:hover { background: %s; }"
            "QPushButton:checked { color: %s; background: %s; font-weight: bold; }"
            % (
                COLOR_ACCENT_HOVER,
                COLOR_ACCENT_DARK,
                wutil.DPI(7),
                wutil.DPI(6),
                COLOR_ACCENT_MAIN,
                COLOR_BG_MAIN,
                COLOR_ACCENT_LIGHT,
            )
        )
    return (
        "QPushButton { color: %s; background: %s; text-align: left; "
        "padding: %spx %spx %spx %spx; border-radius: %spx; "
        "font-size: %spx; font-weight: bold; border: none; }"
        "QPushButton:hover, QPushButton:pressed { color: %s; background: %s; }"
        "QPushButton:checked { color: %s; background: %s; }"
        % (
            COLOR_ACCENT_HOVER,
            COLOR_ACCENT_DARK,
            wutil.DPI(8),
            wutil.DPI(18),
            wutil.DPI(8),
            wutil.DPI(8),
            wutil.DPI(6),
            wutil.DPI(11),
            COLOR_ACCENT_DARK,
            COLOR_ACCENT_MAIN,
            COLOR_BG_MAIN,
            COLOR_ACCENT_LIGHT,
        )
    )


def _configure_option_button(button, compact=False):
    """Apply the common interaction and appearance for enum options."""
    button.setFlat(True)
    button.setCursor(QtCore.Qt.PointingHandCursor)
    button.setStyleSheet(_option_button_stylesheet(compact=compact))


def _add_option_state_indicator(button, is_current=False, is_keyed=False):
    """Add the standard current/keyed dot used by attribute options."""
    dot_layout = QtWidgets.QHBoxLayout(button)
    dot_layout.setContentsMargins(0, 0, wutil.DPI(6), 0)
    dot_layout.addStretch(1)

    dot = QtWidgets.QWidget(button)
    dot.setAttribute(QtCore.Qt.WA_TransparentForMouseEvents)
    dot_size = wutil.DPI(10)
    dot.setFixedSize(dot_size, dot_size)
    if is_current:
        color = COLOR_BG_TRACK
    elif is_keyed:
        color = COLOR_BLEND_MULTI
    else:
        color = "transparent"
    dot.setStyleSheet(
        "background: {}; border-radius: {}px;".format(color, dot_size // 2)
    )
    dot_layout.addWidget(dot)


def _connect_checkable_button(button, callback, *callback_args):
    """Connect checked buttons across Qt bindings that omit clicked(bool)."""
    def _dispatch(*_signal_args):
        callback(button.isChecked(), *callback_args)

    button.clicked.connect(_dispatch)


def _multi_select_modifier_held():
    """Query Ctrl/Cmd directly instead of relying on Maya key delivery."""
    query_modifiers = getattr(
        QtGui.QGuiApplication, "queryKeyboardModifiers", None
    )
    if callable(query_modifiers):
        modifiers = query_modifiers()
    else:
        modifiers = QtWidgets.QApplication.keyboardModifiers()
    return bool(
        modifiers & (QtCore.Qt.ControlModifier | QtCore.Qt.MetaModifier)
    )


class Grip(QtWidgets.QSizeGrip):
    """
    A custom size grip that signals the parent to pause auto-closing on resizing.
    """

    def __init__(self, parent):
        QtWidgets.QSizeGrip.__init__(self, parent)
        self._parent_widget = parent
        self._start_geom = None

    def mousePressEvent(self, e):
        self._start_geom = self._parent_widget.geometry()
        self._parent_widget._suspend_auto_close()
        QtWidgets.QSizeGrip.mousePressEvent(self, e)

    def mouseReleaseEvent(self, e):
        QtWidgets.QSizeGrip.mouseReleaseEvent(self, e)
        if self._start_geom and self._parent_widget.geometry() != self._start_geom:
            self._parent_widget.showBottomBar()
        self._start_geom = None


class _ContentHeightScrollArea(QtWidgets.QScrollArea):
    """A scroll area that collapses fully and derives height from its content."""

    def minimumSizeHint(self):
        return QtCore.QSize(0, 0)

    def contentSizeHint(self):
        content = self.widget()
        if content is None:
            return QtCore.QSize(0, 0)
        # With widgetResizable enabled, the content widget may already have
        # been collapsed to the viewport. Its layout retains the intrinsic
        # size of the child rows and avoids that sizing feedback loop.
        content_layout = content.layout()
        content_hint = (
            content_layout.sizeHint()
            if content_layout is not None
            else content.sizeHint()
        )
        frame_size = self.frameWidth() * 2
        return QtCore.QSize(
            max(0, content_hint.width()) + frame_size,
            max(0, content_hint.height()) + frame_size,
        )

    def sizeHint(self):
        return self.contentSizeHint()


class FloatingWidget(cd.QFlatDialog):
    """
    A draggable, frameless, rounded widget wrapper.
    Can be instantiated as a temporary popup or a pinned window.
    """

    BORDER_RADIUS = wutil.DPI(5)
    AUTO_CLOSE_DIST = wutil.DPI(10)
    AUTO_CLOSE_PERIOD_MS = 300
    # Newly shown/positioned popups can report stale geometry for a moment
    # (present_beside_cursor() moves+shows before the window manager has
    # finished applying it), which made _is_cursor_within_bounds() see the
    # cursor as "outside" the window on the very first open and close it
    # within ~200ms. Ignore auto-close requests until geometry has settled.
    AUTO_CLOSE_GRACE_MS = 400
    TEXT_COLOR = COLOR_TEXT_SECONDARY

    def __init__(self, popup=False, parent=None):
        cd.QFlatDialog.__init__(self, parent)
        self.setWindowFlags(self.windowFlags() | QtCore.Qt.Tool | QtCore.Qt.FramelessWindowHint)
        self.setAttribute(QtCore.Qt.WA_TranslucentBackground)
        self.setAttribute(QtCore.Qt.WA_DeleteOnClose, False)

        self._is_dragging = False
        self._drag_offset = QtCore.QPoint()
        self._drag_start_pos = QtCore.QPoint()

        self._auto_close_active = True if popup else None
        self._shown_elapsed = QtCore.QElapsedTimer()

        # Event-driven auto-close mechanism
        self._auto_close_timer = QtCore.QTimer(self)
        self._auto_close_timer.setSingleShot(True)
        self._auto_close_timer.setInterval(200)
        self._auto_close_timer.timeout.connect(self._process_auto_close_request)

        self._setup_ui()
        self.setMouseTracking(True)

    def showEvent(self, event):
        # Restart the grace window every time the popup (re)appears, not just
        # on first construction -- a reused/hidden-then-reshown widget can hit
        # the same stale-geometry window.
        self._shown_elapsed.start()
        cd.QFlatDialog.showEvent(self, event)

    def enterEvent(self, event):
        self._auto_close_timer.stop()
        cd.QFlatDialog.enterEvent(self, event)

    def leaveEvent(self, event):
        if self._auto_close_active:
            self._auto_close_timer.start()
        cd.QFlatDialog.leaveEvent(self, event)

    def _process_auto_close_request(self):
        """Evaluates whether the window should close based on current cursor position."""
        if not self._auto_close_active or not self.isVisible():
            return

        if not self._shown_elapsed.isValid() or not self._shown_elapsed.hasExpired(self.AUTO_CLOSE_GRACE_MS):
            return

        if self._is_cursor_within_bounds():
            return  # Cursor is in a valid interaction zone

        cursor_pos = QtGui.QCursor.pos()
        bounds = self.frameGeometry()

        # Calculate Manhattan distance slop for a more forgiving interaction feel
        dx = max(bounds.left() - cursor_pos.x(), 0, cursor_pos.x() - bounds.right())
        dy = max(bounds.top() - cursor_pos.y(), 0, cursor_pos.y() - bounds.bottom())

        if (dx * dx + dy * dy) > (self.AUTO_CLOSE_DIST * self.AUTO_CLOSE_DIST):
            self.close()

    def _is_cursor_within_bounds(self):
        """Geometric intersection check for the main widget and its active sub-popups."""
        cursor_pos = QtGui.QCursor.pos()
        if not wutil.is_valid_widget(self):
            return False

        if self.frameGeometry().contains(cursor_pos):
            return True

        if (
            hasattr(self, "_active_popup")
            and self._active_popup
            and wutil.is_valid_widget(self._active_popup)
            and self._active_popup.isVisible()
        ):
            if self._active_popup.frameGeometry().contains(cursor_pos):
                return True
        if (
            hasattr(self, "_multi_switch_dialog")
            and self._multi_switch_dialog
            and wutil.is_valid_widget(self._multi_switch_dialog)
            and self._multi_switch_dialog.isVisible()
        ):
            if self._multi_switch_dialog.frameGeometry().contains(cursor_pos):
                return True
        return False

    def _setup_ui(self):
        self.mainContent = QtWidgets.QWidget(self)
        self.mainLayout = QtWidgets.QVBoxLayout(self.mainContent)
        self.mainLayout.setContentsMargins(wutil.DPI(6), wutil.DPI(8), wutil.DPI(6), wutil.DPI(8))
        self.mainLayout.setSpacing(2)

        self.root_layout.insertWidget(0, self.mainContent, 1)

        self.grip = Grip(self)
        self.grip.setCursor(QtCore.Qt.SizeBDiagCursor)

    def paintEvent(self, event):
        if not self.isVisible():
            return
        p = QtGui.QPainter(self)
        p.setRenderHint(QtGui.QPainter.Antialiasing, True)
        p.setPen(QtCore.Qt.NoPen)
        p.setBrush(QtGui.QColor(COLOR_BG_TRACK))

        # Use drawRoundedRect for clean, all-around rounded corners
        rect = self.rect()
        r = self.BORDER_RADIUS
        p.drawRoundedRect(rect, r, r)

    def setBottomBar(self, *args, **kwargs):
        """Overrides QFlatDialog to manage bottom bar while allowing popup timer to persist."""
        if self.bottomBar:
            self.bottomBar.setParent(None)
            self.bottomBar.deleteLater()
            self.bottomBar = None

        kwargs.setdefault("margins", 0)
        cd.QFlatDialog.setBottomBar(self, *args, **kwargs)

    def showBottomBar(self):
        """Disables auto-kill and adds a default close button if no bar exists."""
        if hasattr(self, "_refresh_footer"):
            self._refresh_footer()
        elif not self.bottomBar:
            self.setBottomBar(closeButton=True)
        self._disable_auto_close()

    def set_popup_mode(self, popup):
        """Reset the presentation mode when a reusable window is opened again."""
        self._auto_close_timer.stop()
        self._auto_close_active = True if popup else None
        if hasattr(self, "_refresh_footer"):
            self._refresh_footer()

    def resizeEvent(self, event):
        s = self.grip.sizeHint()
        self.grip.setFixedSize(s)
        self.grip.move(self.width() - s.width(), 0)
        self.grip.raise_()
        cd.QFlatDialog.resizeEvent(self, event)

    def mousePressEvent(self, e):
        if e.button() == QtCore.Qt.LeftButton:
            self._is_dragging = True
            global_position = wutil.event_global_pos(e)
            self._drag_start_pos = global_position
            self._drag_offset = global_position - self.frameGeometry().topLeft()
            self._suspend_auto_close()
        cd.QFlatDialog.mousePressEvent(self, e)

    def mouseMoveEvent(self, e):
        if self._is_dragging and (e.buttons() & QtCore.Qt.LeftButton):
            global_position = wutil.event_global_pos(e)
            self.move(global_position - self._drag_offset)
        cd.QFlatDialog.mouseMoveEvent(self, e)

    def mouseReleaseEvent(self, e):
        if e.button() == QtCore.Qt.LeftButton and self._is_dragging:
            self._is_dragging = False
            global_position = wutil.event_global_pos(e)

            # Check if we moved enough to convert to "show mode" (persistent window)
            drag_dist = (global_position - self._drag_start_pos).manhattanLength()
            if drag_dist > wutil.DPI(10):
                self.showBottomBar()
            elif self._auto_close_active is False:
                # Resume tracking after small click/drag
                self._auto_close_active = True
                self._resume_auto_close()

        cd.QFlatDialog.mouseReleaseEvent(self, e)

    def _resume_auto_close(self):
        """Restarts the auto-close timer if the cursor is currently outside the bounds."""
        if self._auto_close_active is True and not self._is_cursor_within_bounds():
            self._auto_close_timer.start()

    def _suspend_auto_close(self):
        """Pauses the auto-close timer and updates tracking state."""
        if self._auto_close_active is True:
            self._auto_close_active = False
        if hasattr(self, "_auto_close_timer"):
            self._auto_close_timer.stop()

    def _disable_auto_close(self):
        """Permanently stops the auto-close mechanism for the lifetime of the widget."""
        if hasattr(self, "_auto_close_timer") and self._auto_close_timer:
            self._auto_close_timer.stop()
        self._auto_close_active = None

    def closeEvent(self, e):
        self._disable_auto_close()
        cd.QFlatDialog.closeEvent(self, e)


# =================================================================================
#  3. SPECIFIC WIDGETS
# =================================================================================


class PillSlider(QtWidgets.QWidget):
    """
    A custom pill-shaped slider for numeric attributes.
    """

    HEIGHT = wutil.DPI(32)
    HANDLE_RADIUS = wutil.DPI(13)

    SNAP_POINTS = [0.0, 0.5, 1.0]
    SNAP_THRESHOLD = 0.06

    def __init__(self, value, min_val, max_val, callback, parent=None):
        QtWidgets.QWidget.__init__(self, parent)
        self.setFixedSize(wutil.DPI(140), self.HEIGHT)
        self.value = float(value)
        self.min_val = float(min_val)
        self.max_val = float(max_val)
        self.callback = callback
        self._dragging = False
        self._original_value = self.value
        self.setCursor(QtCore.Qt.PointingHandCursor)

    def _val_to_pos(self, val):
        offset = self.height() / 2.0
        if self.max_val <= self.min_val:
            return self.width() // 2
        w_inner = self.width() - (2 * offset)
        ratio = (val - self.min_val) / (self.max_val - self.min_val)
        return int(offset + ratio * w_inner)

    def _pos_to_val(self, x):
        offset = self.height() / 2.0
        w_inner = self.width() - (2 * offset)
        if w_inner <= 0:
            return self.min_val
        ratio = (x - offset) / float(w_inner)
        ratio = max(0.0, min(1.0, ratio))

        # Autosnap at snap points
        for snap in self.SNAP_POINTS:
            if abs(ratio - snap) < self.SNAP_THRESHOLD:
                ratio = snap
                break

        return self.min_val + ratio * (self.max_val - self.min_val)

    def paintEvent(self, event):
        painter = QtGui.QPainter(self)
        painter.setRenderHint(QtGui.QPainter.Antialiasing)

        # Track
        rect = self.rect().adjusted(1, 1, -1, -1)
        r = rect.height() / 2
        painter.setPen(QtCore.Qt.NoPen)
        painter.setBrush(QtGui.QColor(COLOR_ACCENT_DARK))
        painter.drawRoundedRect(rect, r, r)

        hy = self.height() / 2
        hr = self.HANDLE_RADIUS

        # Shadow Handle (Original position)
        if self._dragging:
            sx = self._val_to_pos(self._original_value)
            painter.setBrush(QtGui.QColor(COLOR_BLEND_MULTI))
            painter.drawEllipse(QtCore.QPoint(sx, int(hy)), hr, hr)

        # Handle
        hx = self._val_to_pos(self.value)
        painter.setBrush(QtGui.QColor(COLOR_BG_TRACK))
        painter.drawEllipse(QtCore.QPoint(hx, int(hy)), hr, hr)

    def mousePressEvent(self, event):
        if event.button() == QtCore.Qt.LeftButton:
            self._dragging = True
            self._original_value = self.value
            self.value = self._pos_to_val(event.x())
            self.update()

    def mouseMoveEvent(self, event):
        if self._dragging:
            self.value = self._pos_to_val(event.x())
            self.update()

    def mouseReleaseEvent(self, event):
        if event.button() == QtCore.Qt.LeftButton:
            self._dragging = False
            self.callback(self.value)


class _PopupOptionButton(QtWidgets.QPushButton):
    """Option button supporting menu-style press, drag, and release."""

    def __init__(self, text, popup, index, all_frames):
        QtWidgets.QPushButton.__init__(self, text, popup.main_frame)
        self.popup = popup
        self.option_index = index
        self.all_frames = all_frames

    @staticmethod
    def _global_pos(event):
        return wutil.event_global_pos(event)

    def mousePressEvent(self, event):
        if event.button() == QtCore.Qt.LeftButton:
            self.grabMouse()
            self.popup._begin_option_drag(self)
            event.accept()
            return
        QtWidgets.QPushButton.mousePressEvent(self, event)

    def mouseMoveEvent(self, event):
        if self.popup._drag_active:
            self.popup._update_option_drag(self._global_pos(event))
            event.accept()
            return
        QtWidgets.QPushButton.mouseMoveEvent(self, event)

    def mouseReleaseEvent(self, event):
        if event.button() == QtCore.Qt.LeftButton and self.popup._drag_active:
            global_pos = self._global_pos(event)
            try:
                self.releaseMouse()
            except RuntimeError:
                pass
            self.popup._finish_option_drag(global_pos)
            event.accept()
            return
        QtWidgets.QPushButton.mouseReleaseEvent(self, event)


class AttributePopup(QtWidgets.QWidget):
    """
    A floating popup that lists attribute options with a dot for the selected one.
    """

    ALL_KEYFRAMES = "All Keyframes"
    CURRENT_KEYFRAMES = "Current Keyframes"

    def __init__(self, item_widget, on_select):
        QtWidgets.QWidget.__init__(self, item_widget.window())
        self.setWindowFlags(QtCore.Qt.ToolTip | QtCore.Qt.FramelessWindowHint | QtCore.Qt.WindowStaysOnTopHint)
        self.setAttribute(QtCore.Qt.WA_TranslucentBackground)
        self.setAttribute(QtCore.Qt.WA_ShowWithoutActivating)

        self.item_widget = item_widget
        self.options = item_widget.options
        self.current_idx = item_widget.current_idx
        self.indices = item_widget.indices
        self.current_indices = item_widget.current_indices
        self.marked_indices = item_widget.marked_indices
        self.on_select = on_select
        self._option_buttons = []
        self._drag_active = False

        any_obj = next(iter(item_widget.objects_map.values()))
        self.is_enum = any_obj.get("type") == "enum"
        self.min_val = any_obj.get("min", 0)
        self.max_val = any_obj.get("max", 1)

        self._setup_ui()

    def _setup_ui(self):
        """Main entry point for UI construction."""
        self.main_frame = QtWidgets.QFrame(self)
        self.main_frame.setObjectName("PopupFrame")
        self.main_frame.setStyleSheet(
            """
            QFrame#PopupFrame {{
                background-color: {};
                border-radius: {}px;
            }}
        """.format(COLOR_BG_POPUP, wutil.DPI(8))
        )

        self.content_layout = QtWidgets.QVBoxLayout(self.main_frame)
        self.content_layout.setContentsMargins(wutil.DPI(20), wutil.DPI(10), wutil.DPI(18), wutil.DPI(16))
        self.content_layout.setSpacing(wutil.DPI(1))

        if self.is_enum:
            self._build_enum_ui()
        else:
            self._build_numeric_ui()

        # Finalize structure and size
        self.adjustSize()
        self.outer_layout = QtWidgets.QVBoxLayout(self)
        self.outer_layout.setContentsMargins(wutil.DPI(10), 0, 0, 0)
        self.outer_layout.addWidget(self.main_frame)

    def _build_enum_ui(self):
        """Builds sections for enum discrete options."""
        is_ro = self.item_widget.enum_attr == "rotateOrder"

        if is_ro:
            self._add_category(self.ALL_KEYFRAMES, is_all=True, is_rr=True)
        else:
            self._add_category(self.CURRENT_KEYFRAMES, is_all=False)
            self._add_separator()
            self._add_category(self.ALL_KEYFRAMES, is_all=True)

    def _build_numeric_ui(self):
        """Builds sections for continuous numeric sliders."""
        self._add_slider_section(self.CURRENT_KEYFRAMES, is_all=False)
        self._add_separator()
        self._add_slider_section(self.ALL_KEYFRAMES, is_all=True)

    def _add_category(self, title_text, is_all, is_rr=False):
        """Creates a section with a title and a list of option buttons."""
        self.content_layout.addWidget(self._create_title(title_text))

        for i, opt in enumerate(self.options):
            # Special formatting for rotation orders
            display_text = opt
            if is_rr and self.item_widget.gimbal_info:
                info = self.item_widget.gimbal_info.get(opt, {})
                label = info.get("label", "")
                if label:
                    display_text = "{} ({})".format(opt, label)

            btn = self._create_option_button(display_text, i, is_all)
            self.content_layout.addWidget(btn)

            # Extra visual grouping for rotation orders (3+3)
            if is_rr and i == 2:
                self.content_layout.addSpacing(wutil.DPI(5))

    def _create_title(self, text):
        title = QtWidgets.QLabel(text)
        title.setContentsMargins(0, 0, 0, wutil.DPI(4))
        title.setAlignment(QtCore.Qt.AlignLeft | QtCore.Qt.AlignVCenter)
        title.setStyleSheet("color: {}; font-size: {}px;".format(COLOR_TEXT_SECONDARY, wutil.DPI(11)))
        return title

    def _add_separator(self):
        line = QtWidgets.QFrame()
        line.setFrameShape(QtWidgets.QFrame.HLine)
        line.setFixedHeight(1)
        line.setStyleSheet("background-color: {};".format(COLOR_BG_TRACK))
        self.content_layout.addSpacing(wutil.DPI(10))
        self.content_layout.addWidget(line)
        self.content_layout.addSpacing(wutil.DPI(10))

    def _add_slider_section(self, title_text, is_all):
        """Creates a section with a title and a PillSlider."""
        self.content_layout.addWidget(self._create_title(title_text))

        slider = PillSlider(
            self.current_idx, self.min_val, self.max_val, lambda v, m=is_all: self.select_option(v, all_frames=m), parent=self.main_frame
        )
        self.content_layout.addWidget(slider)

    def _create_option_button(self, text, index, is_all):
        btn = _PopupOptionButton(text, self, index, is_all)
        _configure_option_button(btn)
        btn.setMinimumWidth(wutil.DPI(60))
        btn.setSizePolicy(QtWidgets.QSizePolicy.Minimum, QtWidgets.QSizePolicy.Fixed)
        _add_option_state_indicator(
            btn,
            is_current=index in self.current_indices,
            is_keyed=index in self.marked_indices,
        )
        self._option_buttons.append(btn)
        return btn

    def _button_at_global_pos(self, global_pos):
        for button in self._option_buttons:
            if not wutil.is_valid_widget(button) or not button.isVisible():
                continue
            local_pos = button.mapFromGlobal(global_pos)
            if button.rect().contains(local_pos):
                return button
        return None

    def _set_drag_hover_button(self, button):
        for option_button in self._option_buttons:
            if wutil.is_valid_widget(option_button):
                option_button.setDown(option_button is button)

    def _begin_option_drag(self, button):
        self._drag_active = True
        self._set_drag_hover_button(button)
        self.item_widget._set_popup_active(True)

    def _update_option_drag(self, global_pos):
        self._set_drag_hover_button(self._button_at_global_pos(global_pos))

    def _finish_option_drag(self, global_pos):
        button = self._button_at_global_pos(global_pos)
        self._drag_active = False
        self._set_drag_hover_button(None)
        if button is not None:
            self.select_option(
                button.option_index, all_frames=button.all_frames
            )

    def paintEvent(self, event):
        painter = QtGui.QPainter(self)
        painter.setRenderHint(QtGui.QPainter.Antialiasing)
        painter.setPen(QtCore.Qt.NoPen)
        painter.setBrush(QtGui.QColor(COLOR_BG_POPUP))

        arrow_w = wutil.DPI(10)
        arrow_h = wutil.DPI(15)

        side = getattr(self, "side", "right")
        arrow_y = getattr(self, "arrow_y", self.height() / 2)

        if side == "right":
            # Pointing left, attached to the left side of the frame
            poly = QtGui.QPolygonF(
                [
                    QtCore.QPointF(0, arrow_y),
                    QtCore.QPointF(arrow_w + 1, arrow_y - arrow_h / 2),
                    QtCore.QPointF(arrow_w + 1, arrow_y + arrow_h / 2),
                ]
            )
        else:
            # Pointing right, attached to the right side of the frame
            w = self.width()
            poly = QtGui.QPolygonF(
                [
                    QtCore.QPointF(w, arrow_y),
                    QtCore.QPointF(w - arrow_w - 1, arrow_y - arrow_h / 2),
                    QtCore.QPointF(w - arrow_w - 1, arrow_y + arrow_h / 2),
                ]
            )
        painter.drawPolygon(poly)

    def select_option(self, idx, all_frames=None):
        self.on_select(idx, all_frames=all_frames)
        # closing triggers closeEvent which clears parent handle and resumes timer
        self.close()

    def enterEvent(self, event):
        # Notify parent for unified interaction state
        p = self.parent()
        if p and hasattr(p, "_update_interaction_state"):
            p._update_interaction_state(True)
        QtWidgets.QWidget.enterEvent(self, event)

    def leaveEvent(self, event):
        p = self.parent()
        if p and hasattr(p, "_update_interaction_state"):
            # Delay to check if focus moved back to main area
            QtCore.QTimer.singleShot(150, lambda: p._update_interaction_state(False))
        QtWidgets.QWidget.leaveEvent(self, event)

    def closeEvent(self, event):
        self._drag_active = False
        self._set_drag_hover_button(None)
        mouse_grabber = QtWidgets.QWidget.mouseGrabber()
        if mouse_grabber in self._option_buttons:
            try:
                mouse_grabber.releaseMouse()
            except RuntimeError:
                pass
        if wutil.is_valid_widget(self.item_widget):
            self.item_widget._set_popup_active(False)
        p = self.parent()
        if p:
            # Re-evaluate parent's close conditions
            if hasattr(p, "_active_popup") and p._active_popup == self:
                p._active_popup = None
            if hasattr(p, "_resume_auto_close"):
                p._resume_auto_close()
        QtWidgets.QWidget.closeEvent(self, event)

    def show_beside(self, widget):
        self.adjustSize()
        w, h = self.width(), self.height()

        # Global center Y of the source widget
        target_y_global = widget.mapToGlobal(QtCore.QPoint(0, widget.height() // 2)).y()

        # Default: show on the right
        pos = widget.mapToGlobal(QtCore.QPoint(widget.width(), 0))

        screen = QtGui.QGuiApplication.screenAt(pos) or QtGui.QGuiApplication.primaryScreen()
        geo = screen.availableGeometry()

        self.side = "right"
        # If it overflows on the right, flip to left
        if pos.x() + w > geo.right():
            self.side = "left"
            pos.setX(widget.mapToGlobal(QtCore.QPoint(0, 0)).x() - w)

        # Vertical positioning: center it relative to widget
        y = target_y_global - h // 2

        # Ensure it doesn't go off screen vertically
        if y + h > geo.bottom():
            y = geo.bottom() - h - wutil.DPI(5)
        if y < geo.top():
            y = geo.top() + wutil.DPI(5)

        pos.setY(y)
        # Store local y for the arrow tip to keep pointing at the target
        self.arrow_y = target_y_global - y

        # Update margins based on which side the arrow is on
        arrow_w = wutil.DPI(10)
        if self.side == "right":
            self.outer_layout.setContentsMargins(arrow_w, 0, 0, 0)
        else:
            self.outer_layout.setContentsMargins(0, 0, arrow_w, 0)

        self.move(pos)
        self.show()


class MultiAttributeSwitchDialog(FloatingWidget):
    """Stage independent enum choices in a responsive column grid."""

    def __init__(self, parent_dialog, entries):
        FloatingWidget.__init__(self, popup=False, parent=parent_dialog)
        self.parent_dialog = parent_dialog
        self.entries = list(entries or [])
        self._selected_options = {}
        self._option_groups = []
        self._column_widgets = []
        self._all_frames = False
        self.setWindowTitle("Switch Multiple Attributes")
        self.setMinimumWidth(wutil.DPI(220))
        self._build_ui()

    def _build_ui(self):
        title = QtWidgets.QLabel(
            "Switch {} channels".format(len(self.entries)), self.mainContent
        )
        title.setStyleSheet(
            "color: {}; font-size: {}px; font-weight: bold;".format(
                COLOR_TEXT_SECONDARY, wutil.DPI(14)
            )
        )
        self.mainLayout.addWidget(title)

        self.mainLayout.addSpacing(wutil.DPI(10))
        self._add_scope_controls()
        self.mainLayout.addSpacing(wutil.DPI(10))
        self._columns_grid = QtWidgets.QGridLayout()
        self._columns_grid.setContentsMargins(0, 0, 0, 0)
        self._columns_grid.setHorizontalSpacing(wutil.DPI(6))
        self._columns_grid.setVerticalSpacing(wutil.DPI(6))
        self.mainLayout.addLayout(self._columns_grid)
        self._build_columns()
        self._layout_columns(QtGui.QGuiApplication.primaryScreen())

        self.setBottomBar(
            buttons=[
                cd.QFlatDialogButton(
                    "Cancel", callback=self._cancel, icon=icons.cancel
                ),
                cd.QFlatDialogButton(
                    "Apply",
                    callback=self._apply,
                    icon=icons.apply,
                    highlight=True,
                ),
            ],
            closeButton=False,
            highlight="Apply",
        )
        self._apply_button = next(
            (
                button
                for button in self.bottomBar.findChildren(QtWidgets.QPushButton)
                if button.text() == "Apply"
            ),
            None,
        )
        if self._apply_button is not None:
            self._apply_button.setEnabled(False)

    def _add_scope_controls(self):
        layout = QtWidgets.QHBoxLayout()
        layout.setSpacing(wutil.DPI(4))
        label = QtWidgets.QLabel("Keyframes", self.mainContent)
        label.setStyleSheet(
            "color: {}; font-size: {}px;".format(
                COLOR_TEXT_SECONDARY, wutil.DPI(11)
            )
        )
        layout.addWidget(label)
        layout.addStretch(1)

        group = QtWidgets.QButtonGroup(self)
        group.setExclusive(True)
        for text, all_frames in (
            (AttributePopup.CURRENT_KEYFRAMES, False),
            (AttributePopup.ALL_KEYFRAMES, True),
        ):
            button = QtWidgets.QPushButton(text, self.mainContent)
            button.setCheckable(True)
            _configure_option_button(button, compact=True)
            _connect_checkable_button(
                button, self._choose_scope, all_frames
            )
            group.addButton(button)
            layout.addWidget(button)
            if not all_frames:
                button.setChecked(True)
        self._scope_group = group
        self.mainLayout.addLayout(layout)

    def _build_columns(self):
        for entry_index, (item, options_map) in enumerate(self.entries):
            column = QtWidgets.QWidget(self.mainContent)
            column.setFixedWidth(wutil.DPI(165))
            column.setStyleSheet("background: transparent;")
            layout = QtWidgets.QVBoxLayout(column)
            layout.setContentsMargins(
                wutil.DPI(5), wutil.DPI(5), wutil.DPI(5), wutil.DPI(5)
            )
            layout.setSpacing(wutil.DPI(3))

            object_heading = QtWidgets.QLabel(item.object_label, column)
            object_heading.setWordWrap(False)
            object_heading.setStyleSheet(
                "color: {}; font-size: {}px; background: transparent;".format(
                    COLOR_TEXT_SECONDARY, wutil.DPI(11)
                )
            )
            object_heading.setToolTip(item.object_label)
            layout.addWidget(object_heading)

            attribute_text = item.attribute_label
            if item.has_mixed_key_values:
                attribute_text += " *"
            attribute_heading = QtWidgets.QLabel(attribute_text, column)
            attribute_heading.setWordWrap(False)
            attribute_heading.setStyleSheet(
                "color: {}; font-size: {}px; font-weight: bold; background: transparent;".format(
                    COLOR_TEXT_SECONDARY, wutil.DPI(11)
                )
            )
            attribute_heading.setToolTip(item.attribute_label)
            layout.addWidget(attribute_heading)

            group = QtWidgets.QButtonGroup(self)
            group.setExclusive(True)
            self._option_groups.append(group)
            option_count = 0
            for option_index, option in enumerate(item.options):
                if option not in options_map:
                    continue
                option_count += 1
                button = QtWidgets.QPushButton(option, column)
                button.setCheckable(True)
                _configure_option_button(button)
                _connect_checkable_button(
                    button, self._choose_option, entry_index, option
                )
                _add_option_state_indicator(
                    button,
                    is_current=option_index in item.current_indices,
                    is_keyed=option_index in item.marked_indices,
                )
                group.addButton(button)
                layout.addWidget(button)
            if not option_count:
                empty = QtWidgets.QLabel("No options", column)
                empty.setStyleSheet(
                    "color: {}; background: transparent;".format(
                        COLOR_TEXT_SECONDARY
                    )
                )
                layout.addWidget(empty)
            layout.addStretch(1)
            self._column_widgets.append(column)

    def _layout_columns(self, screen):
        while self._columns_grid.count():
            self._columns_grid.takeAt(0)
        available_width = wutil.DPI(700)
        if screen is not None:
            available_width = screen.availableGeometry().width() - wutil.DPI(80)
        column_step = wutil.DPI(171)
        columns_per_row = max(
            1,
            min(len(self._column_widgets), available_width // column_step),
        )
        for index, column in enumerate(self._column_widgets):
            self._columns_grid.addWidget(
                column,
                index // columns_per_row,
                index % columns_per_row,
            )

    def _choose_scope(self, checked, all_frames):
        if checked:
            self._all_frames = all_frames

    def _choose_option(self, checked, entry_index, option):
        if not checked:
            return
        self._selected_options[entry_index] = option
        if self._apply_button is not None:
            self._apply_button.setEnabled(True)

    def _apply(self):
        if not self._selected_options:
            return
        staged_entries = [
            (self.entries[index][0], self.entries[index][1], option)
            for index, option in sorted(self._selected_options.items())
        ]
        self.parent_dialog._apply_multi_switch(
            staged_entries, self._all_frames
        )

    def _cancel(self):
        self.parent_dialog._close_multi_switch_dialog(clear_selection=True)

    def reject(self):
        self._cancel()

    def show_beside(self, widget):
        position = widget.mapToGlobal(QtCore.QPoint(widget.width(), 0))
        screen = (
            QtGui.QGuiApplication.screenAt(position)
            or QtGui.QGuiApplication.primaryScreen()
        )
        self._layout_columns(screen)
        self.adjustSize()
        if screen is not None:
            available = screen.availableGeometry()
            if position.x() + self.width() > available.right():
                position.setX(
                    widget.mapToGlobal(QtCore.QPoint(0, 0)).x() - self.width()
                )
            position.setX(
                max(
                    available.left(),
                    min(position.x(), available.right() - self.width()),
                )
            )
            position.setY(
                max(
                    available.top(),
                    min(position.y(), available.bottom() - self.height()),
                )
            )
        self.move(position)
        self.show()
        self.raise_()


class AttributeItem(QtWidgets.QWidget):
    """
    A row item that shows an attribute name and a pill with the current value.
    """

    def __init__(
        self,
        object_label,
        attribute_label,
        enum_attr,
        unique_controls,
        objects_map,
        parent_dialog,
    ):
        QtWidgets.QWidget.__init__(self, parent_dialog.mainContent)
        self.object_label = object_label
        self.attribute_label = attribute_label
        self.label_text = "{} {}".format(object_label, attribute_label)
        self.enum_attr = enum_attr
        self.unique_controls = unique_controls
        self.objects_map = objects_map
        self.parent_dialog = parent_dialog

        # Extract options and status
        any_obj = next(iter(objects_map.values()))
        self.is_enum = any_obj.get("type") == "enum"
        self.min_val = any_obj.get("min", 0)
        self.max_val = any_obj.get("max", 1)

        self.options = any_obj.get("enum", [])
        self.current_indices = {obj.get("current") for obj in objects_map.values()}
        self.marked_indices = {idx for obj in objects_map.values() for idx in obj.get("marked", [])}
        keyed_values = {
            idx
            for obj in objects_map.values()
            for idx in obj.get("keyed_values", [])
        }
        self.has_mixed_key_values = self.is_enum and len(keyed_values) > 1
        self.indices = self.current_indices | self.marked_indices
        self.current_idx = any_obj.get("current", 0)
        self.gimbal_info = any_obj.get("gimbal", {})

        self.is_toggle = self.is_enum and len(self.options) <= 2
        self._hover_active = False
        self._popup_active = False
        self.setMouseTracking(True)
        self.setSizePolicy(QtWidgets.QSizePolicy.Preferred, QtWidgets.QSizePolicy.Fixed)
        self._setup_ui()

    def _setup_ui(self):
        self.main_layout = QtWidgets.QHBoxLayout(self)
        self.main_layout.setContentsMargins(wutil.DPI(6), wutil.DPI(6), wutil.DPI(6), wutil.DPI(6))
        self.main_layout.setSpacing(wutil.DPI(6))

        self.multi_checkbox = QtWidgets.QCheckBox(self)
        self.multi_checkbox.setObjectName("HotkeyCommandCheckBox")
        self.multi_checkbox.setVisible(False)
        self.multi_checkbox.setToolTip("Select this channel for a staged multi-switch")
        self.multi_checkbox.setCursor(QtCore.Qt.PointingHandCursor)
        self.multi_checkbox.setSizePolicy(
            QtWidgets.QSizePolicy.Fixed, QtWidgets.QSizePolicy.Fixed
        )
        self.multi_checkbox.setFocusPolicy(QtCore.Qt.NoFocus)
        self.multi_checkbox.setStyleSheet(
            "#HotkeyCommandCheckBox{background:transparent;spacing:0px;}"
            "#HotkeyCommandCheckBox::indicator{width:%spx;height:%spx;border:1px solid #626262;border-radius:%spx;background:#262626;}"
            "#HotkeyCommandCheckBox::indicator:hover{border-color:#7d7d7d;background:#303030;}"
            "#HotkeyCommandCheckBox::indicator:checked{image:url(%s);border-color:#7d7d7d;background:#363636;}"
            % (wutil.DPI(11), wutil.DPI(11), wutil.DPI(3), icons.apply)
        )
        self.multi_checkbox.toggled.connect(self._on_multi_checked)

        display_label = self.label_text
        if self.has_mixed_key_values:
            display_label += " *"
        self.name_label = QtWidgets.QLabel(display_label, self)
        self.name_label.setStyleSheet("color: {}; font-size: {}px;".format(COLOR_TEXT_MAIN, wutil.DPI(11)))
        self.name_label.setAlignment(QtCore.Qt.AlignLeft | QtCore.Qt.AlignVCenter)
        self.name_label.setAttribute(QtCore.Qt.WA_TransparentForMouseEvents)

        self.pill_container = QtWidgets.QWidget(self)
        self.pill_container.setAttribute(QtCore.Qt.WA_TransparentForMouseEvents)
        self.pill_container.setFixedSize(wutil.DPI(60), wutil.DPI(16))
        self.pill_layout = QtWidgets.QHBoxLayout(self.pill_container)
        self.pill_layout.setContentsMargins(wutil.DPI(2), 0, wutil.DPI(2), 0)
        self.pill_layout.setSpacing(wutil.DPI(2))

        # Indicator 'Ball' style
        self.sq_btn = QtWidgets.QPushButton(self.pill_container)
        self.sq_btn.setFixedSize(wutil.DPI(12), wutil.DPI(12))
        self.sq_btn.setFocusPolicy(QtCore.Qt.NoFocus)
        self.sq_btn.setAttribute(QtCore.Qt.WA_TransparentForMouseEvents)

        self.val_label = QtWidgets.QLabel(
            self.options[int(self.current_idx)] if self.is_enum and self.options else "{:.2f}".format(self.current_idx), self.pill_container
        )
        self.val_label.setStyleSheet("color: {}; font-size: {}px;".format(COLOR_ACCENT_LIGHT, wutil.DPI(11)))
        self.val_label.setAlignment(QtCore.Qt.AlignCenter)

        # Toggles hide text until hover; Enums show text always; Numeric hide always
        self.val_label.setVisible(self.is_enum and not self.is_toggle)

        if self.is_enum:
            if self.is_toggle or self.enum_attr == "rotateOrder":
                self.pill_layout.addWidget(self.sq_btn)
                self.sq_btn.show()
            else:
                self.sq_btn.hide()
            self.pill_layout.addStretch()
            self.pill_layout.addWidget(self.val_label)
            self.pill_layout.addStretch()
        else:
            self.pill_layout.removeWidget(self.sq_btn)
            self.pill_layout.setContentsMargins(wutil.DPI(2), 0, wutil.DPI(2), 0)
            self.pill_layout.addWidget(self.val_label)
            self.sq_btn.setParent(self.pill_container)
            QtCore.QTimer.singleShot(0, self._update_numeric_ball_pos)

        self._refresh_pill_style()

        self.main_layout.addWidget(self.multi_checkbox, 0, QtCore.Qt.AlignVCenter)
        self.main_layout.addWidget(self.name_label, 1)
        self.main_layout.addWidget(self.pill_container)

        # Keep layout space but make transparent
        self.pill_opacity = QtWidgets.QGraphicsOpacityEffect(self.pill_container)
        self.pill_container.setGraphicsEffect(self.pill_opacity)
        self.pill_opacity.setOpacity(0.0)

    def _set_popup_active(self, active):
        self._popup_active = bool(active)
        self._hover_active = self._popup_active or self.underMouse()
        self.update()

    def _on_multi_checked(self, checked):
        self._update_multi_checkbox_visibility()
        self.update()
        handler = getattr(
            self.parent_dialog, "_on_attribute_multi_checked", None
        )
        if callable(handler):
            handler(self, checked)

    @staticmethod
    def _multi_select_modifier_held():
        return _multi_select_modifier_held()

    def _update_multi_checkbox_visibility(self):
        if not self.is_enum:
            self.multi_checkbox.hide()
            return
        cursor_inside = self.rect().contains(
            self.mapFromGlobal(QtGui.QCursor.pos())
        )
        should_show = self.multi_checkbox.isChecked() or (
            cursor_inside and self._multi_select_modifier_held()
        )
        self.multi_checkbox.setVisible(should_show)

    def _update_numeric_ball_pos(self):
        if self.is_enum:
            return
        w = self.pill_container.width()
        ball_w = self.sq_btn.width()
        padding = wutil.DPI(2)  # Match enum layout margins
        usable_w = w - ball_w - (padding * 2)

        if self.max_val <= self.min_val:
            x = padding + (usable_w // 2)
        else:
            ratio = (self.current_idx - self.min_val) / (self.max_val - self.min_val)
            ratio = max(0.0, min(1.0, ratio))
            x = int(padding + (ratio * usable_w))
        self.sq_btn.move(x, (self.pill_container.height() - self.sq_btn.height()) // 2)
        self.sq_btn.show()

    def _refresh_pill_style(self):
        # Colors from reference
        ball_color = COLOR_ACCENT_MAIN
        pill_bg = COLOR_ACCENT_DARK

        if self.current_idx in self.marked_indices:
            ball_color = COLOR_ACCENT_LIGHT

        if self.enum_attr == "rotateOrder":
            self.sq_btn.setStyleSheet("background: transparent; border: none;")
            icon = ATTRIBUTE_SWITCHER_GLOBE_IMAGE

            pixmap = QtGui.QPixmap(icon)
            if not pixmap.isNull():
                # Ensure sizes are integers
                target_size = int(wutil.DPI(12))
                if target_size < 1:
                    target_size = 12

                pixmap = pixmap.scaled(target_size, target_size, QtCore.Qt.KeepAspectRatio, QtCore.Qt.SmoothTransformation)

                # Tint the icon
                tinted = QtGui.QPixmap(pixmap.size())
                tinted.fill(QtCore.Qt.transparent)
                painter = QtGui.QPainter(tinted)
                painter.drawPixmap(0, 0, pixmap)
                painter.setCompositionMode(QtGui.QPainter.CompositionMode_SourceIn)
                painter.fillRect(tinted.rect(), QtGui.QColor(ball_color))
                painter.end()

                self.sq_btn.setIcon(QtGui.QIcon(tinted))
                self.sq_btn.setIconSize(QtCore.QSize(target_size, target_size))
            else:
                # Basic dot fallback if SVG fails to load
                self.sq_btn.setIcon(QtGui.QIcon())
                self.sq_btn.setStyleSheet("background: {}; border-radius: {}px; border: none;".format(ball_color, int(wutil.DPI(6))))
        else:
            self.sq_btn.setIcon(QtGui.QIcon())
            self.sq_btn.setStyleSheet("background: {}; border-radius: {}px; border: none;".format(ball_color, int(wutil.DPI(6))))

        self.pill_container.setStyleSheet("background: {}; border-radius: {}px;".format(pill_bg, wutil.DPI(8)))

    def paintEvent(self, event):
        painter = QtGui.QPainter(self)
        painter.setRenderHint(QtGui.QPainter.Antialiasing)

        # Draw row background as seen in reference
        rect = self.rect().adjusted(1, 1, -1, -1)
        bg_color = QtGui.QColor(COLOR_ACCENT_MAIN)
        if self.is_enum and self.multi_checkbox.isChecked():
            bg_color = QtGui.QColor(COLOR_BLEND_MULTI)
        elif self._hover_active:
            bg_color = QtGui.QColor(COLOR_ACCENT_WHITE)

        painter.setBrush(QtGui.QBrush(bg_color))
        painter.setPen(QtGui.QPen(QtGui.QColor(UI_COLOR.white.hex), 1))
        painter.drawRoundedRect(rect, 2, 2)

    def enterEvent(self, event):
        self._hover_active = True
        self._update_multi_checkbox_visibility()
        self.update()
        if self.parent_dialog:
            self.parent_dialog._handle_attr_hover(self)
            # Ensure parent interaction state is active when a row is hovered
            if hasattr(self.parent_dialog, "_update_interaction_state"):
                self.parent_dialog._update_interaction_state(True)
        QtWidgets.QWidget.enterEvent(self, event)

    def mouseMoveEvent(self, event):
        self._update_multi_checkbox_visibility()
        QtWidgets.QWidget.mouseMoveEvent(self, event)

    def mousePressEvent(self, event):
        if (
            event.button() == QtCore.Qt.LeftButton
            and self.is_enum
            and self.multi_checkbox.isVisible()
        ):
            self.multi_checkbox.toggle()
            event.accept()
            return
        QtWidgets.QWidget.mousePressEvent(self, event)

    def leaveEvent(self, event):
        self._hover_active = self._popup_active
        if not self.multi_checkbox.isChecked():
            self.multi_checkbox.hide()
        self.update()
        if self.parent_dialog:
            self.parent_dialog._handle_attr_leave(self)
        QtWidgets.QWidget.leaveEvent(self, event)

    def on_select(self, idx, all_frames=None):
        self.current_idx = idx
        if self.is_enum:
            self.val_label.setText(self.options[int(idx)])
        else:
            self._update_numeric_ball_pos()
        self._refresh_pill_style()

        # Immediate scene apply if mode is specified (selection from popup)
        if all_frames is not None:
            # Find the required data mapping from the parent dialog
            options_map = None
            # For numeric, we don't use the standard options_map label lookup
            if not self.is_enum:
                # Construct a virtual entry for the value
                options_map = {
                    idx: {
                        "objects": list(self.objects_map.keys()),
                        "index": idx,
                        "attrs": {o: d["attr"] for o, d in self.objects_map.items()},
                    }
                }
            else:
                for (attr, _), (item, o_map) in self.parent_dialog._active_switch_widgets.items():
                    if item == self:
                        options_map = o_map
                        break

            if options_map:
                val = idx if not self.is_enum else self.options[int(idx)]
                self.parent_dialog._apply_attribute_switch(val, self.enum_attr, options_map, all_frames_override=all_frames)

    def currentText(self):
        return self.options[int(self.current_idx)] if self.options else ""


# =================================================================================
#  4. SETUP DIALOGS
# =================================================================================


class SetupTargetsDialog(FloatingWidget):
    def __init__(self, parent, objects_dict, on_close):
        FloatingWidget.__init__(self, popup=False, parent=parent)
        self.on_close = on_close
        self.controller = parent.controller

        if parent and hasattr(parent, "_suspend_auto_close"):
            parent._suspend_auto_close()

        self.objects_dict = objects_dict
        self._create_layouts()
        self.setBottomBar(
            [cd.QFlatDialogButton("Add", callback=self._add_target, icon=icons.add, highlight=True)],
            closeButton=True,
            spacing=wutil.DPI(2),
        )

    def _add_target(self):
        for obj in self.controller.selected_nodes():
            self.targets_list.add_target(obj)

    def _create_layouts(self):
        title = QtWidgets.QLabel("Xform targets")
        title.setAlignment(QtCore.Qt.AlignLeft | QtCore.Qt.AlignVCenter)
        title.setStyleSheet("font-size: 16px; font-weight: bold; margin-bottom: 4px;")

        self.targets_list = TargetsList(
            self, is_valid_target=self.controller.object_exists
        )
        self.targets_list.setSizePolicy(QtWidgets.QSizePolicy.Expanding, QtWidgets.QSizePolicy.Expanding)

        for target in list(self.objects_dict.keys()):
            self.targets_list.add_target(target)

        self.mainLayout.addWidget(title)
        self.mainLayout.addWidget(self.targets_list)

    def closeEvent(self, event):
        new_order = self.targets_list.backing_store

        new_dict = {}
        for t in new_order:
            new_dict[t] = self.objects_dict.get(t) or list(self.objects_dict.values())[0]

        self.objects_dict.clear()
        self.objects_dict.update(new_dict)

        if callable(self.on_close):
            self.on_close(self.objects_dict.keys())

        parent = self.parent()
        if parent and hasattr(parent, "_resume_auto_close"):
            parent._resume_auto_close()

        FloatingWidget.closeEvent(self, event)


class TargetItemWidget(QtWidgets.QWidget):
    def __init__(self, name, list_ref):
        QtWidgets.QWidget.__init__(self)
        self.name = name
        self.list_ref = list_ref

        layout = QtWidgets.QHBoxLayout(self)
        layout.setContentsMargins(2, 0, 2, 0)
        layout.setSpacing(4)

        label = QtWidgets.QLabel(name.split(":")[-1])
        close_btn = QtWidgets.QPushButton()
        close_btn.setIcon(QtGui.QIcon(icons.close))

        close_btn.setIconSize(QtCore.QSize(15, 15))
        close_btn.setFixedSize(15, 15)
        close_btn.setFocusPolicy(QtCore.Qt.NoFocus)
        close_btn.clicked.connect(self._remove)
        close_btn.setStyleSheet(
            """
            QPushButton {
                border: none;
                background: transparent;
                padding: 0px;
                margin: 0px;
            }
            QPushButton:pressed {
                background: %s;
            }
            """
            % COLOR_BG_MAIN
        )

        layout.addWidget(label)
        layout.addStretch()
        layout.addWidget(close_btn)

    def _remove(self):
        self.list_ref.remove_target(self.name)


class TargetsList(QtWidgets.QListWidget):
    def __init__(self, parent=None, is_valid_target=None):
        QtWidgets.QListWidget.__init__(self, parent)
        self.backing_store = []
        self._is_valid_target = is_valid_target or (lambda _name: True)
        self.setStyleSheet("""
            QListWidget:focus {
                outline: none;
                border: none;
        }
        """)

    def add_target(self, name):
        if not self._is_valid_target(name) or name in self.backing_store:
            return

        self.backing_store.append(name)

        item = QtWidgets.QListWidgetItem()
        item.setFlags(QtCore.Qt.NoItemFlags)
        widget = TargetItemWidget(name, self)

        item.setSizeHint(widget.sizeHint())
        self.addItem(item)
        self.setItemWidget(item, widget)

    def remove_target(self, name):
        if name in self.backing_store:
            self.backing_store.remove(name)

        for i in range(self.count()):
            if self.itemWidget(self.item(i)).name == name:
                self.takeItem(i)
                break


# =================================================================================
#  5. APPLICATION (ATTRIBUTE SWITCHER)
# =================================================================================


class AttributeSwitcherWidget(FloatingToolWindowMixin, FloatingWidget):
    """
    The main widget for the Attribute Switcher tool.
    """

    def __init__(self, popup=False, parent=None):
        parent = parent or wutil.get_maya_qt()
        FloatingWidget.__init__(self, popup=popup, parent=parent)
        self._init_floating_window_behavior()

        self._active_popup = None
        self._multi_switch_dialog = None
        self._popup_pending_item = None
        self._is_ui_hovered = False
        self._popup_timer = QtCore.QTimer(self)
        self._popup_timer.setSingleShot(True)
        self._popup_timer.setInterval(100)
        self._popup_timer.timeout.connect(self._show_pending_popup)
        self._geometry_fit_pending = False
        self._geometry_anchor_bottom = None
        self.controller = switchController.AttributeSwitcherController(self)
        self._load_persistent_settings()

        self._create_layouts()
        self._create_selection_layout()
        self._connect_runtime_manager()

        self._active_switch_widgets = {}
        self._previous_selection = []
        self._last_multi_modifier_state = None
        self._modifier_poll_timer = QtCore.QTimer(self)
        self._modifier_poll_timer.setInterval(40)
        self._modifier_poll_timer.timeout.connect(
            self._poll_multi_select_modifier
        )

        self.refresh()
        saved_geom = self.controller.saved_geometry()
        if saved_geom and len(saved_geom) == 4:
            self.setGeometry(saved_geom[0], saved_geom[1], saved_geom[2], saved_geom[3])
        self._request_geometry_fit()

    def _auto_transparency_setting_enabled(self):
        return False

    def _stays_on_top_setting_enabled(self):
        return self.controller.stays_on_top()

    def _geometry_settings_key(self):
        return ATTRIBUTE_SWITCHER_GEOMETRY_KEY

    def _geometry_settings_namespace(self):
        return ATTRIBUTE_SWITCHER_SETTINGS_NAMESPACE

    def showBottomBar(self):
        """Pin the popup while preserving the visible attribute area."""
        geometry_before = QtCore.QRect(self.geometry())
        had_bottom_bar = bool(
            self.bottomBar and wutil.is_valid_widget(self.bottomBar)
        )
        FloatingWidget.showBottomBar(self)
        has_bottom_bar = bool(
            self.bottomBar and wutil.is_valid_widget(self.bottomBar)
        )
        if had_bottom_bar or not has_bottom_bar:
            return

        bottom_layout = self.bottomBar.layout()
        if bottom_layout:
            bottom_layout.activate()
        self.bottomBar.ensurePolished()
        footer_height = max(
            self.bottomBar.sizeHint().height(),
            self.bottomBar.minimumSizeHint().height(),
        )
        if footer_height <= 0:
            return

        screen = QtGui.QGuiApplication.screenAt(geometry_before.center())
        screen = screen or QtGui.QGuiApplication.primaryScreen()
        target_height = geometry_before.height() + footer_height
        target_y = geometry_before.y()
        if screen is not None:
            available = screen.availableGeometry()
            margin = wutil.DPI(10)
            target_height = min(
                target_height, available.height() - (margin * 2)
            )
            max_bottom = available.bottom() - margin
            overflow = target_y + target_height - 1 - max_bottom
            if overflow > 0:
                target_y = max(available.top() + margin, target_y - overflow)

        self.setGeometry(
            geometry_before.x(),
            target_y,
            geometry_before.width(),
            target_height,
        )
        self.root_layout.invalidate()
        self.root_layout.activate()

    def closeEvent(self, e):
        self._close_multi_switch_dialog(clear_selection=True)
        self._disconnect_runtime_manager()
        self.controller.save_geometry(
            [self.pos().x(), self.pos().y(), self.width(), self.height()],
        )
        FloatingWidget.closeEvent(self, e)

    # =================================================================================
    #  2. UI CONSTRUCTION & LIFECYCLE
    # =================================================================================

    def _create_layouts(self):
        """Builds the main container layouts."""
        self.mainContent.setMinimumWidth(wutil.DPI(220))
        self.mainContent.setContextMenuPolicy(QtCore.Qt.CustomContextMenu)
        self.mainContent.customContextMenuRequested.connect(self._show_context_menu)

        self.attributes_scroll = _ContentHeightScrollArea(self.mainContent)
        self.attributes_scroll.setMinimumSize(0, 0)
        self.attributes_scroll.setSizePolicy(
            QtWidgets.QSizePolicy.Expanding, QtWidgets.QSizePolicy.Preferred
        )
        self.attributes_scroll.setWidgetResizable(True)
        self.attributes_scroll.setFrameShape(QtWidgets.QFrame.NoFrame)
        self.attributes_scroll.setHorizontalScrollBarPolicy(QtCore.Qt.ScrollBarAlwaysOff)
        self.attributes_scroll.setVerticalScrollBarPolicy(QtCore.Qt.ScrollBarAsNeeded)
        self.attributes_scroll.setStyleSheet(
            "QScrollArea { background: transparent; border: none; }"
            "QScrollArea > QWidget > QWidget { background: transparent; }"
        )
        self.enums_container, self.enums_layout = self._new_attribute_container()
        self.attributes_scroll.setWidget(self.enums_container)
        self.attributes_scroll.verticalScrollBar().rangeChanged.connect(
            self._update_attribute_scrollbar_margin
        )
        self.mainLayout.addWidget(self.attributes_scroll)
        self.mainLayout.addStretch(1)

    @staticmethod
    def _new_attribute_container():
        container = QtWidgets.QWidget()
        layout = QtWidgets.QVBoxLayout(container)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(wutil.DPI(1))
        layout.setSizeConstraint(QtWidgets.QLayout.SetMinAndMaxSize)
        return container, layout

    def _update_attribute_area_geometry(self):
        """Notify Qt after atomically replacing the attribute content."""
        self.enums_layout.invalidate()
        self.enums_layout.activate()
        self.enums_container.adjustSize()
        self.enums_container.updateGeometry()
        self._update_attribute_scroll_minimum_height()
        self.attributes_scroll.updateGeometry()
        self.mainLayout.invalidate()
        self.mainLayout.activate()
        self._refresh_attribute_scrollbar_margin()

    def _update_attribute_scroll_minimum_height(self):
        """Fit at least one complete enum row whenever rows are available."""
        first_item = self.enums_layout.itemAt(0)
        first_widget = first_item.widget() if first_item is not None else None
        if first_widget is None:
            self.attributes_scroll.setMinimumHeight(0)
            return

        first_widget.ensurePolished()
        item_layout = first_widget.layout()
        if item_layout is not None:
            item_layout.activate()
        row_height = max(
            first_widget.sizeHint().height(),
            first_widget.minimumSizeHint().height(),
        )
        self.attributes_scroll.setMinimumHeight(
            row_height + (self.attributes_scroll.frameWidth() * 2)
        )

    def _update_attribute_scrollbar_margin(self, minimum, maximum):
        """Keep enum rows clear of an overlay-style vertical scrollbar."""
        right_margin = 0
        if maximum > minimum:
            scrollbar = self.attributes_scroll.verticalScrollBar()
            right_margin = scrollbar.sizeHint().width() + wutil.DPI(2)
        self.enums_layout.setContentsMargins(0, 0, right_margin, 0)

    def _refresh_attribute_scrollbar_margin(self):
        scrollbar = self.attributes_scroll.verticalScrollBar()
        self._update_attribute_scrollbar_margin(
            scrollbar.minimum(), scrollbar.maximum()
        )

    def _replace_attribute_content(self, switch_data):
        """Build a complete replacement off-screen, then swap it in once."""
        new_container, new_layout = self._new_attribute_container()
        new_widgets = {}

        for enum_name, data in (switch_data or {}).items():
            self._create_switch_item(
                enum_name,
                data,
                target_layout=new_layout,
                target_registry=new_widgets,
            )

        old_container = self.attributes_scroll.takeWidget()
        self.enums_container = new_container
        self.enums_layout = new_layout
        self._active_switch_widgets = new_widgets
        self.attributes_scroll.setWidget(new_container)
        if old_container is not None:
            old_container.deleteLater()

        self._update_attribute_area_geometry()

    def _fit_to_available_screen(self):
        """Fit content up to the available screen, then rely on scrolling."""
        screen = QtGui.QGuiApplication.screenAt(self.frameGeometry().center())
        if screen is None:
            screen = QtGui.QGuiApplication.screenAt(QtGui.QCursor.pos())
        screen = screen or QtGui.QGuiApplication.primaryScreen()
        if screen is None:
            return

        available = screen.availableGeometry()
        screen_margin = wutil.DPI(10)
        max_height = max(
            wutil.DPI(120), available.height() - (screen_margin * 2)
        )
        self.setMaximumHeight(max_height)

        # Clear the limit from a previous (possibly empty) refresh before
        # asking Qt for the new content-preferred geometry.
        self.attributes_scroll.setMaximumHeight(16777215)
        self.attributes_scroll.updateGeometry()

        # Measure the complete window chrome first. This includes the selection
        # header, layout margins, and the optional persistent-window bottom bar.
        self.mainLayout.invalidate()
        self.mainLayout.activate()
        if self.bottomBar and wutil.is_valid_widget(self.bottomBar):
            bottom_layout = self.bottomBar.layout()
            if bottom_layout:
                bottom_layout.activate()
            self.bottomBar.adjustSize()
            self.bottomBar.updateGeometry()
        self.root_layout.invalidate()
        self.root_layout.activate()

        scroll_height = self.attributes_scroll.contentSizeHint().height()
        preferred_height = self.root_layout.sizeHint().height()
        chrome_height = max(0, preferred_height - scroll_height)
        available_scroll_height = max(0, max_height - chrome_height)
        self.attributes_scroll.setMaximumHeight(
            min(scroll_height, available_scroll_height)
        )
        self.attributes_scroll.updateGeometry()

        self.mainLayout.invalidate()
        self.mainLayout.activate()
        self.root_layout.invalidate()
        self.root_layout.activate()
        desired_height = min(self.root_layout.sizeHint().height(), max_height)
        anchored_bottom = self._geometry_anchor_bottom
        if anchored_bottom is None:
            anchored_bottom = self.frameGeometry().bottom()
        self.resize(self.width(), desired_height)

        # Keep the bottom edge anchored: content grows upward and collapses
        # downward, which also preserves placement above the toolbar.
        min_y = available.top() + screen_margin
        max_y = available.bottom() - desired_height - screen_margin + 1
        anchored_y = anchored_bottom - desired_height + 1
        self.move(self.x(), max(min_y, min(anchored_y, max_y)))
        self._geometry_anchor_bottom = None

    def _request_geometry_fit(self):
        """Fit now when visible, or once Qt has polished the window for show."""
        self._geometry_fit_pending = True
        if not self.isVisible():
            return
        self._fit_to_available_screen()
        self._geometry_fit_pending = False

    def showEvent(self, event):
        super().showEvent(event)
        if hasattr(self, "_modifier_poll_timer"):
            self._last_multi_modifier_state = None
            self._modifier_poll_timer.start()
            self._poll_multi_select_modifier()
        if self._geometry_fit_pending:
            self._fit_to_available_screen()
            self._geometry_fit_pending = False

    def hideEvent(self, event):
        if hasattr(self, "_modifier_poll_timer"):
            self._modifier_poll_timer.stop()
            self._last_multi_modifier_state = None
        super().hideEvent(event)

    def _create_selection_layout(self):
        """Builds the header area showing tool title and current status."""
        selection_layout = QtWidgets.QVBoxLayout()
        selection_layout.setSpacing(wutil.DPI(5))
        selection_layout.setContentsMargins(0, wutil.DPI(6), 0, wutil.DPI(8))

        title_layout = QtWidgets.QHBoxLayout()
        title_layout.setSpacing(wutil.DPI(6))
        title_layout.setContentsMargins(0, 0, 0, 0)

        title_icon_size = wutil.DPI(25)
        title_icon = QtWidgets.QLabel()
        title_icon.setFixedSize(title_icon_size, title_icon_size)
        title_icon.setPixmap(
            QtGui.QIcon(icons.attribute_switcher).pixmap(
                title_icon_size,
                title_icon_size,
            )
        )
        title_icon.setAlignment(QtCore.Qt.AlignCenter)

        selection_title = QtWidgets.QLabel("Selection")
        selection_title.setStyleSheet(
            "font-size: %spx; color: %s; font-weight: bold; background: transparent;" % (wutil.DPI(18), self.TEXT_COLOR)
        )
        selection_title.setSizePolicy(QtWidgets.QSizePolicy.Ignored, QtWidgets.QSizePolicy.Fixed)
        selection_title.setWordWrap(False)
        selection_title.setFixedHeight(selection_title.fontMetrics().height() + 2)

        title_layout.addWidget(title_icon)
        title_layout.addWidget(selection_title, 1)

        self.selection_label = QtWidgets.QLabel("No switches for selection")
        self.selection_label.setStyleSheet("color: %s; background: transparent;" % self.TEXT_COLOR)

        selection_layout.addLayout(title_layout)
        selection_layout.addWidget(self.selection_label)

        self.mainLayout.insertLayout(0, selection_layout)

    def _refresh_footer(self):
        """Updates the interaction bar based on whether valid switches exist."""
        # Show Close only if not in popup mode (pinned)
        should_close = not self._auto_close_active
        has_bottom_bar = bool(
            self.bottomBar and wutil.is_valid_widget(self.bottomBar)
        )
        if has_bottom_bar == should_close:
            return
        self.setBottomBar(closeButton=should_close)
        self.root_layout.invalidate()
        self.root_layout.activate()

    # =================================================================================
    # 3. STATE & SETTINGS
    # =================================================================================

    def _load_persistent_settings(self):
        """Loads user preferences from local storage."""
        for key, value in self.controller.load_settings().items():
            setattr(self, key, value)

    def set_setting(self, setting, state, refresh=False):
        self.controller.set_setting(setting, state, refresh=refresh)

    # =================================================================================
    # 4. MAYA INTEGRATION
    # =================================================================================

    def _connect_runtime_manager(self):
        self.controller.connect_runtime()

    def apply_active_changes(self):
        """Commits all currently selected enum values to the scene."""
        self.controller.apply_active_changes(self._active_switch_widgets)

    def _disconnect_runtime_manager(self):
        self.controller.disconnect_runtime()

    # =================================================================================
    #  6. INTERACTION & HOVER LOGIC
    # =================================================================================

    def _update_interaction_state(self, is_active, force=False):
        """Unified interaction management for multi-window focus tracking."""
        if not is_active:
            cursor_pos = QtGui.QCursor.pos()
            if wutil.is_valid_widget(self) and self.frameGeometry().contains(cursor_pos):
                is_active = True
            if not is_active and self._active_popup and wutil.is_valid_widget(self._active_popup) and self._active_popup.isVisible():
                if self._active_popup.frameGeometry().contains(cursor_pos):
                    is_active = True
            multi_dialog = getattr(self, "_multi_switch_dialog", None)
            if (
                not is_active
                and multi_dialog
                and wutil.is_valid_widget(multi_dialog)
                and multi_dialog.isVisible()
                and multi_dialog.frameGeometry().contains(cursor_pos)
            ):
                is_active = True

        if not force and self._is_ui_hovered == is_active:
            return

        self._is_ui_hovered = is_active

        # Toggle auto-close based on interaction
        if self._is_ui_hovered:
            self._auto_close_timer.stop()
        else:
            self._resume_auto_close()

        for (enum_attr, _), (attr_item, _) in self._active_switch_widgets.items():
            if not wutil.is_valid_widget(attr_item):
                continue
            if hasattr(attr_item, "pill_opacity"):
                attr_item.pill_opacity.setOpacity(1.0 if self._is_ui_hovered else 0.0)

            if hasattr(attr_item, "val_label"):
                if not attr_item.is_enum:
                    attr_item.val_label.setVisible(False)
                elif attr_item.is_toggle:
                    attr_item.val_label.setVisible(self._is_ui_hovered)
                else:
                    attr_item.val_label.setVisible(True)
            attr_item.update()

    def _poll_multi_select_modifier(self):
        """Refresh once whenever the directly queried Ctrl/Cmd state changes."""
        if not self.isVisible():
            self._last_multi_modifier_state = None
            return
        modifier_held = _multi_select_modifier_held()
        if modifier_held == self._last_multi_modifier_state:
            return
        self._last_multi_modifier_state = modifier_held
        self._refresh_multi_checkbox_visibility()

    def _refresh_multi_checkbox_visibility(self):
        if not self.isVisible():
            return
        for item, _options_map in self._active_switch_widgets.values():
            if wutil.is_valid_widget(item):
                item._update_multi_checkbox_visibility()

    def enterEvent(self, event):
        self._update_interaction_state(True)
        FloatingWidget.enterEvent(self, event)

    def leaveEvent(self, event):
        # Small delay to see if we moved to the popup or just left
        QtCore.QTimer.singleShot(150, lambda: self._update_interaction_state(False))
        FloatingWidget.leaveEvent(self, event)

    def _handle_attr_hover(self, item):
        if item._multi_select_modifier_held() or self._selected_multi_entries():
            self._popup_timer.stop()
            self._popup_pending_item = None
            self._close_active_popup()
            return
        self._popup_pending_item = item
        self._popup_timer.start()

    def _handle_attr_leave(self, item):
        # Delay hiding to allow transition
        if self._popup_pending_item == item:
            self._popup_pending_item = None
        self._popup_timer.start()

    def _show_pending_popup(self):
        """Displays the attribute choice popup beside the hovered row."""
        if self._selected_multi_entries():
            self._popup_pending_item = None
            self._close_active_popup()
            return

        # Keep the popup while the cursor is over it or an option drag is active.
        if not self._popup_pending_item or not wutil.is_valid_widget(self._popup_pending_item):
            popup = self._active_popup
            if not popup or not wutil.is_valid_widget(popup):
                return
            if popup._drag_active or popup.underMouse():
                return
            self._close_active_popup()
            return

        item = self._popup_pending_item

        # If current is same item and visible, do nothing
        if (
            self._active_popup
            and wutil.is_valid_widget(self._active_popup)
            and self._active_popup.item_widget == item
            and self._active_popup.isVisible()
        ):
            return

        # Otherwise, switch
        self._close_active_popup()

        self._active_popup = AttributePopup(item, item.on_select)
        item._set_popup_active(True)
        self._active_popup.show_beside(item)

    def _close_active_popup(self):
        """Safely removes the current popup."""
        popup = getattr(self, "_active_popup", None)
        if not popup or not wutil.is_valid_widget(popup):
            self._active_popup = None
            return
        item = popup.item_widget
        if wutil.is_valid_widget(item):
            item._set_popup_active(False)
        popup.hide()
        popup.deleteLater()
        self._active_popup = None

    def _selected_multi_entries(self):
        """Return checked enum rows and their option maps in display order."""
        entries = []
        for _key, (item, options_map) in self._active_switch_widgets.items():
            if (
                wutil.is_valid_widget(item)
                and item.is_enum
                and item.multi_checkbox.isChecked()
            ):
                entries.append((item, options_map))
        return entries

    def _on_attribute_multi_checked(self, item, checked):
        """Update the staged multi-switch UI without changing the scene."""
        self._popup_timer.stop()
        self._popup_pending_item = None
        self._close_active_popup()

        entries = self._selected_multi_entries()
        self._close_multi_switch_dialog(clear_selection=False)
        if len(entries) < 2:
            return

        self._multi_switch_dialog = MultiAttributeSwitchDialog(self, entries)
        anchor = item if checked and wutil.is_valid_widget(item) else entries[-1][0]
        self._multi_switch_dialog.show_beside(anchor)
        self._update_interaction_state(True, force=True)

    def _close_multi_switch_dialog(self, clear_selection=False):
        """Close the staged dialog and optionally clear all checked rows."""
        dialog = getattr(self, "_multi_switch_dialog", None)
        self._multi_switch_dialog = None
        if dialog and wutil.is_valid_widget(dialog):
            dialog.hide()
            dialog.deleteLater()

        if clear_selection:
            for item, _options_map in self._selected_multi_entries():
                item.multi_checkbox.blockSignals(True)
                item.multi_checkbox.setChecked(False)
                item.multi_checkbox.blockSignals(False)
                item._update_multi_checkbox_visibility()
                item.update()
        self._update_interaction_state(self._is_cursor_within_bounds(), force=True)

    def _apply_multi_switch(self, staged_entries, all_frames):
        """Commit each staged channel option as one operation."""
        requests = [
            (option, item.enum_attr, options_map, all_frames)
            for item, options_map, option in staged_entries
            if option in options_map
        ]
        self._close_multi_switch_dialog(clear_selection=True)
        if requests:
            self.controller.apply_switches(requests)

    # =================================================================================
    #  8. HELPERS
    # =================================================================================

    def _format_object_name(self, objects):
        """Returns a human-friendly string for one or multiple objects."""
        if not objects:
            return ""
        if len(objects) == 1:
            name = objects[0].split("|")[-1]
            if ":" in name and not self.namespace_display:
                name = name.split(":")[-1]
            return ("..." + name[:50]) if len(name) > 50 else name
        return "(%s)" % len(objects)

    @staticmethod
    def formatXformTooltipObjects(objects):
        """Formats the HTML tooltip for target objects."""
        return "<html>Current xform target/s:<br>%s<br><br><b>Right-click to modify...</b></html>" % "<br>".join(objects)

    # =================================================================================
    #  5. REFRESH & UPDATE LOGIC
    # =================================================================================

    def refresh(self, timeChange=False, force=False, *args):
        """Main update orchestration. Synchronizes UI state with current Maya selection."""
        if timeChange:
            return

        # SetMinAndMaxSize may resize the dialog as soon as child geometry
        # changes. Capture the stable edge before any refresh mutation.
        if self.isVisible():
            self._geometry_anchor_bottom = self.frameGeometry().bottom()

        self._popup_timer.stop()
        self._popup_pending_item = None
        self._close_active_popup()
        current_sel = self.controller.selected_nodes(long=False)

        # Detect selection change or forced refresh
        selection_is_same = sorted(current_sel) == sorted(self._previous_selection)
        if selection_is_same and not force:
            self._refresh_footer()
            self._request_geometry_fit()
            return

        self._close_multi_switch_dialog(clear_selection=True)
        self._previous_selection = current_sel
        self._rebuild_active_widgets()

    def _rebuild_active_widgets(self):
        """Fetch data first, then atomically replace the visible attribute list."""
        try:
            switch_data = (
                self.controller.analyze(
                    self._previous_selection,
                    show_rotate_order=self.show_rotate_order,
                )
                if self._previous_selection
                else {}
            )
            self._replace_attribute_content(switch_data)
        except Exception as e:
            self.controller.warning(
                "Error rebuilding Attribute Switcher widgets: {}".format(e)
            )
            return

        self._switch_data = switch_data
        self.selection_label.setVisible(not bool(switch_data))
        self._update_interaction_state(self._is_ui_hovered, force=True)
        self._refresh_footer()
        self._request_geometry_fit()

    def _create_switch_item(
        self, enum_name, data, target_layout=None, target_registry=None
    ):
        """Instantiates and registers a single AttributeItem based on provided metadata."""
        if target_layout is None:
            target_layout = self.enums_layout
        target_registry = (
            target_registry
            if target_registry is not None
            else self._active_switch_widgets
        )
        target_nodes = sorted(data["objects"].keys())
        display_name = self._format_object_name(target_nodes)

        attr_item = AttributeItem(
            display_name,
            data["long"].title(),
            enum_name,
            target_nodes,
            data["objects"],
            self,
        )

        attr_item.setToolTip(self.formatXformTooltipObjects(target_nodes))
        attr_item.setContextMenuPolicy(QtCore.Qt.CustomContextMenu)
        attr_item.customContextMenuRequested.connect(lambda pos, s=attr_item, d=data: self._show_change_target_dialog(s, d))

        options_map = self.controller.build_options_map(data["objects"])
        target_registry[(enum_name, tuple(target_nodes))] = (
            attr_item,
            options_map,
        )
        target_layout.insertWidget(0, attr_item)

    def _apply_attribute_switch(
        self, enum_value, enum_attr, options_and_objects, all_frames_override=None
    ):
        self.controller.apply_switch(
            enum_value,
            enum_attr,
            options_and_objects,
            all_frames_override=all_frames_override,
        )

    def _show_context_menu(self, pos):
        """Displays global tool configuration menu."""
        self.context_menu = cw.OpenMenuWidget(self)
        self.context_menu.aboutToShow.connect(self._suspend_auto_close)
        self.context_menu.aboutToHide.connect(self._resume_auto_close)

        self.toggle_namespaces_action = self.context_menu.addAction("Show namespaces", description="Show namespaces for listed attributes.")
        self.toggle_namespaces_action.setCheckable(True)
        self.toggle_namespaces_action.setChecked(self.namespace_display)

        self.show_rotate_order_action = self.context_menu.addAction(
            "Enable Rotate Order", description="List Rotate Order attributes for selected objects."
        )
        self.show_rotate_order_action.setCheckable(True)
        self.show_rotate_order_action.setChecked(self.show_rotate_order)

        self.context_menu.addSeparator()

        self.euler_filter_action = self.context_menu.addAction(
            "Auto Euler Filter", description="Apply euler filter to switched attributes."
        )
        self.euler_filter_action.setCheckable(True)
        self.euler_filter_action.setChecked(self.euler_filter)

        self.show_rotate_order_action.toggled.connect(lambda state: self.set_setting("show_rotate_order", state, refresh=True))
        self.toggle_namespaces_action.toggled.connect(lambda state: self.set_setting("namespace_display", state, refresh=True))
        self.euler_filter_action.toggled.connect(lambda state: self.set_setting("euler_filter", state))

        exec_fn = getattr(self.context_menu, "exec", None) or getattr(self.context_menu, "exec_", None)
        exec_fn(QtGui.QCursor.pos())

    def _show_change_target_dialog(self, sender, data):
        """Opens the UI for multi-target management."""
        selection = self.controller.selected_nodes(long=False)

        def on_close(objects):
            self.controller.select(selection)
            self._connect_runtime_manager()
            sender.setToolTip(self.formatXformTooltipObjects(objects))

        objects_dict = data["objects"]
        self._disconnect_runtime_manager()
        dlg = SetupTargetsDialog(self, objects_dict, on_close=on_close)
        dlg.show()

    # =================================================================================
    #  7. APPLICATION ACTIONS
    # =================================================================================

import TheKeyMachine.tools.attribute_switcher.api as attributeSwitcherApi


class AttributeSwitcherWindow(AttributeSwitcherWidget):
    def __init__(self, parent=None, popup=False):
        super().__init__(popup=popup, parent=parent)
        self.setObjectName("attribute_switcher_window")
        self.setWindowTitle("Attribute Switcher")

    def closeEvent(self, event):
        attributeSwitcherApi._emit_attribute_switcher_window_state(False)
        super().closeEvent(event)
