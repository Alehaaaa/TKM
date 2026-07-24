from __future__ import annotations

from typing import ClassVar, Optional
import os
import importlib
import traceback

from TheKeyMachine.core.Qt import QtCore, QtGui, QtWidgets  # type: ignore

import TheKeyMachine.mods.uiMod as ui
import TheKeyMachine.mods.reportMod as report
import TheKeyMachine.widgets.util as wutil
import TheKeyMachine.widgets.customWidgets as cw
import TheKeyMachine.mods.settingsMod as settings
from TheKeyMachine.tools.sliders import SliderMode
from TheKeyMachine.tools.sliders import utils as slider_utils
import TheKeyMachine.core.runtimeManager as runtime
import TheKeyMachine.widgets.timeline as timelineWidgets
from TheKeyMachine.data import icons
from TheKeyMachine.data.colors import COLORS

from TheKeyMachine.mods.tooltipsMod import QFlatTooltipManager, format_tooltip_shortcut

importlib.reload(ui)
importlib.reload(report)
importlib.reload(wutil)
importlib.reload(cw)
importlib.reload(settings)


"""
QFlatSliderWidget
===============================================================

Self-contained slider with a centered horizontal scrub from -100..+100.
No A/B picks. Context menu on right-click.
"""


SLIDER_HANDLE_NEUTRAL_HEX = "#444444"
SLIDER_VALUE_TEXT_HEX = "#747474"
SLIDER_FRAME_BUTTON_COLOR = "#d7d7d7"


def _slider_button_variant(value):
    value = int(value)
    if value == 0:
        return None
    return "big" if abs(value) == 100 else "small"


def _slider_button_icon(slider_type, variant):
    if not slider_type or variant not in {"small", "big", "frame"}:
        return None
    return icons.get("slider_{}/square_{}".format(slider_type, variant))


def _format_shortcut(shortcut) -> str:
    return format_tooltip_shortcut(shortcut)


def _shortcut_to_mask(shortcut) -> int:
    shortcut = shortcut or []
    mask = 0
    if QtCore.Qt.Key_Shift in shortcut:
        mask |= 1
    if QtCore.Qt.Key_Control in shortcut:
        mask |= 4
    if QtCore.Qt.Key_Alt in shortcut:
        mask |= 8
    return mask


def _shortcut_requires_mid_click(shortcut) -> bool:
    return QtCore.Qt.MiddleButton in (shortcut or [])


def _slider_command_name(prefix: str, mode: str, value: int) -> str:
    base_command_name = "slider_{}_{}".format(prefix, mode)
    value = int(value)
    if value == 0:
        return base_command_name
    suffix = "neg{}".format(abs(value)) if value < 0 else str(value)
    return "{}_{}".format(base_command_name, suffix)


# --- tiny button with centered square ------------------------------------------
class SliderButton(cw.TooltipMixin, QtWidgets.QPushButton):
    """Flat square-indicator button that emits its signed percent on click."""

    def __init__(self, parent: QtWidgets.QWidget, *, percent: int, color: str, worldSpace: bool = False, frameButton: bool = False):
        super().__init__(parent)
        self._percent = percent
        self._color = color
        self._frameButton = bool(frameButton)
        self._frameValue = None
        self._squareIconPath = None
        self._squareIcon = QtGui.QIcon()
        self.setCheckable(self._frameButton)
        self._box_sz = wutil.DPI(7) if (self._frameButton or abs(percent) == 100) else wutil.DPI(3)
        self.setFixedHeight(parent.height())
        self.setSizePolicy(QtWidgets.QSizePolicy.Expanding, QtWidgets.QSizePolicy.Fixed)

        self.setStyleSheet(
            f"QPushButton {{ background: none; border-radius: 0; }}"
            f"QPushButton:pressed, QPushButton:checked {{ background-color: {self._color}; border-radius: 0; }}"
        )

        self._worldSpace = worldSpace
        self._hover = False

        self._tooltip_title = ""
        self._tooltip_description = ""
        self._tooltip_command_id = None
        self._tooltip_command_label = None
        self._tooltip_command_icon = None
        # Initial tooltip
        self._update_tooltip()

    def setColor(self, color: str):
        self._color = color
        self.update()

    def setSquareIcon(self, icon_path: Optional[str]):
        self._squareIconPath = icon_path
        self._squareIcon = QtGui.QIcon(icon_path or "")
        self.update()

    @property
    def squareIconPath(self) -> Optional[str]:
        return self._squareIconPath

    def _update_tooltip(self):
        title = self._tooltip_title or "Value"
        value_label = "Set Frame" if self._frameButton else f"{self._percent}%"
        self.setToolTipData(
            text=f"{title}: {value_label}",
            description=self._tooltip_description,
            tooltip=getattr(self, "_tooltip", None),
            command_id=self._tooltip_command_id,
            command_label=self._tooltip_command_label,
            command_icon=self._tooltip_command_icon,
        )

    def setTooltipInfo(
        self,
        title: str,
        description: str = "",
        tooltip=None,
        command_id=None,
        command_label=None,
        command_icon=None,
    ):
        self._tooltip_title = title
        self._tooltip_description = description
        self._tooltip = tooltip
        self._tooltip_command_id = command_id
        self._tooltip_command_label = command_label
        self._tooltip_command_icon = command_icon
        self._update_tooltip()

    @property
    def percent(self) -> int:
        return self._percent

    def setWorldSpace(self, enabled: int):
        self._worldSpace = enabled
        self.update()

    def setFrameValue(self, frame):
        self._frameValue = frame
        self.update()

    def enterEvent(self, e):
        self._hover = True
        self.update()
        super().enterEvent(e)

    def leaveEvent(self, e):
        self._hover = False
        self.update()
        super().leaveEvent(e)

    def paintEvent(self, e):
        super().paintEvent(e)
        p = QtGui.QPainter(self)
        p.setRenderHint(QtGui.QPainter.Antialiasing)

        w, h, s = self.width(), self.height(), self._box_sz
        y = (h - s) // 2

        base_color = QtGui.QColor(self._color)
        if getattr(self, "_hover", False):
            main_color = QtGui.QColor(
                min(base_color.red() + 60, 255), min(base_color.green() + 60, 255), min(base_color.blue() + 60, 255), base_color.alpha()
            )
            glow_color = QtGui.QColor(255, 255, 255, 40)
            # Create a list of 8 offsets for silhouette glow + (0, 0) for main draw
            offsets = [(-1, -1), (1, 1), (-1, 1), (1, -1), (0, -1), (0, 1), (-1, 0), (1, 0), (0, 0)]
        else:
            main_color = base_color
            glow_color = QtCore.Qt.transparent
            offsets = [(0, 0)]

        if self._worldSpace:
            for dx, dy in offsets:
                is_glow = dx != 0 or dy != 0
                p.save()
                p.translate(dx, dy)
                cx, cy = w // 2, h // 2
                r = wutil.DPI(int(min(w, h) * 0.24))  # smaller globe

                p.setPen(QtCore.Qt.NoPen)
                p.setBrush(glow_color if is_glow else main_color)
                p.drawEllipse(QtCore.QRect(cx - r, cy - r, 2 * r, 2 * r))

                if not is_glow:
                    # Black linework on top
                    pen = QtGui.QPen(QtGui.QColor(COLORS.ui.dark_gray.hex))
                    pen.setWidthF(0.85)
                    p.setPen(pen)
                    p.setBrush(QtCore.Qt.NoBrush)

                    # Outer circle outline
                    p.drawEllipse(QtCore.QRect(cx - r, cy - r, 2 * r, 2 * r))

                    # Equator
                    p.drawLine(cx - r + 1, cy, cx + r - 1, cy)

                    # Curved meridians (left/right)
                    mer_w = int(2 * r * 0.45)  # tweak curvature here (0.5–0.65 looks good)
                    mer_rect = QtCore.QRect(cx - mer_w // 2, cy - r, mer_w, 2 * r)
                    p.drawArc(mer_rect, 90 * 14, 180 * 16)  # left arc
                    p.drawArc(mer_rect, 90 * 14, -180 * 16)  # right arc
                p.restore()
        elif not self._squareIcon.isNull():
            icon_mode = QtGui.QIcon.Active if self._hover else QtGui.QIcon.Normal
            icon_canvas_size = wutil.DPI(SliderHandle.HANDLE_SIZE)
            icon_rect = QtCore.QRect(0, 0, icon_canvas_size, icon_canvas_size)
            icon_rect.moveCenter(QtCore.QRect(0, 0, w, h).center())
            self._squareIcon.paint(
                p,
                icon_rect,
                QtCore.Qt.AlignCenter,
                icon_mode,
                QtGui.QIcon.Off,
            )

        if self._frameButton and self._frameValue is not None:
            font = QtGui.QFont(self.font())
            font.setPixelSize(max(wutil.DPI(7), min(wutil.DPI(9), y)))
            font.setBold(False)
            p.setFont(font)
            p.setPen(main_color)
            label_rect = QtCore.QRect(0, -wutil.DPI(1), w, max(1, y + wutil.DPI(1)))
            p.drawText(label_rect, QtCore.Qt.AlignHCenter | QtCore.Qt.AlignTop, str(int(self._frameValue)))
        p.end()


# --- core slider (custom painting & handle-only interaction) --------------------
class SliderHandle(cw.TooltipMixin, QtWidgets.QSlider):
    """Horizontal slider that only drags when grabbing the handle."""

    PERCENT_SCALE: ClassVar[int] = 1000

    DEFAULT_WIDTH: ClassVar[int] = 200
    DEFAULT_HEIGHT: ClassVar[int] = 24
    THIN_GROOVE_HEIGHT: ClassVar[int] = 10
    HANDLE_SIZE: ClassVar[int] = 24
    HANDLE_RADIUS: ClassVar[int] = 5

    VALUE_FONT_SIZE: ClassVar[int] = 14
    TEXT_FONT_SIZE: ClassVar[int] = 11
    VALUE_HANDLE_PADDING: ClassVar[int] = 10
    VALUE_EDGE_PADDING: ClassVar[int] = 14

    WHEEL_DELTA_STEP: ClassVar[float] = 15.0
    WHEEL_ACCELERATION_STEP: ClassVar[float] = 0.2
    WHEEL_ACCELERATION_LIMIT: ClassVar[float] = 8.0
    WHEEL_COMMIT_DELAY_MS: ClassVar[int] = 250

    started = QtCore.Signal()
    moved = QtCore.Signal(float)
    finished = QtCore.Signal()

    def __init__(self, parent: QtWidgets.QWidget, *, text: str, color: str, icon_color: Optional[str] = None):
        super().__init__(QtCore.Qt.Horizontal, parent)
        self.setObjectName("TKMSliderHandle")

        # behavior
        self.setMouseTracking(True)
        self.setFocusPolicy(QtCore.Qt.ClickFocus)
        self.setSingleStep(1)
        self.setPageStep(5)

        # theme/state
        self._color = color
        self._icon_color = icon_color or color
        self._text = text
        self._press_offset: Optional[int | bool] = None
        self._has_dragged = False
        self._hover = False
        self._handle_hover = False
        self._tooltip_title = ""
        self._tooltip_description = ""
        self._tooltip_command_id = None
        self._tooltip_command_label = None
        self._tooltip_command_icon = None
        self._icon = text if self._looks_like_icon(text) else None

        self._wheel_count = 0
        self._prev_wheel_direction = 0
        self._wheel_commit_timer = QtCore.QTimer(self)
        self._wheel_commit_timer.setSingleShot(True)
        self._wheel_commit_timer.setInterval(self.WHEEL_COMMIT_DELAY_MS)
        self._wheel_commit_timer.timeout.connect(self._finish_wheel_interaction)

        # fonts
        self._value_font = QtGui.QFont()
        self._value_font.setPointSize(wutil.DPI(self.VALUE_FONT_SIZE))
        self._text_font = QtGui.QFont()
        self._text_font.setPixelSize(int(wutil.DPI(self.TEXT_FONT_SIZE)))

        # size
        self.setFixedWidth(wutil.DPI(self.DEFAULT_WIDTH))
        self.setFixedHeight(wutil.DPI(self.DEFAULT_HEIGHT))

        self._apply_stylesheet(thick=False)

    def setTooltipInfo(
        self,
        title: str,
        description: str = "",
        tooltip=None,
        command_id=None,
        command_label=None,
        command_icon=None,
    ):
        self._tooltip_title = title
        self._tooltip_description = description
        self._tooltip = tooltip
        self._tooltip_command_id = command_id
        self._tooltip_command_label = command_label
        self._tooltip_command_icon = command_icon
        self._update_self_tooltip()

    def enterEvent(self, e):
        self._hover = True
        self.update()
        super().enterEvent(e)

    def leaveEvent(self, e):
        QFlatTooltipManager.hide()

        self._hover = False
        self._handle_hover = False

        if self._press_offset is not None and not self.isSliderDown():
            self._finish_interaction()

        self.update()
        super().leaveEvent(e)

    def _update_self_tooltip(self, _v=None):
        title = self._tooltip_title or self._text
        self.setToolTipData(
            text=title,
            description=self._tooltip_description,
            tooltip=getattr(self, "_tooltip", None),
            command_id=self._tooltip_command_id,
            command_label=self._tooltip_command_label,
            command_icon=self._tooltip_command_icon,
        )

    @staticmethod
    def _looks_like_icon(value: str) -> bool:
        if not value or not isinstance(value, str):
            return False
        return os.path.isabs(value) or os.path.splitext(value)[1].lower() in {".svg", ".png", ".jpg", ".jpeg", ".bmp", ".ico"}

    # --- public helpers ---------------------------------------------------------
    def handle_size(self) -> int:
        return wutil.DPI(self.HANDLE_SIZE)

    def percent(self) -> float:
        # internal units = thousandths of a percent
        return round(self.value() / float(self.PERCENT_SCALE), 3)

    def set_range(self, min_v: int, max_v: int):
        self.setRange(int(min_v * self.PERCENT_SCALE), int(max_v * self.PERCENT_SCALE))

    def apply_wheel_delta(self, delta_units: int):
        """Centralized wheel logic for slider."""
        # Acceleration logic: start smaller, get bigger
        direction = 1 if delta_units > 0 else -1
        if direction != self._prev_wheel_direction:
            self._wheel_count = 0
        self._prev_wheel_direction = direction
        self._wheel_count += 1

        # Multiplier: grows steadily with each notch
        multiplier = 1.0 + min(self._wheel_count * self.WHEEL_ACCELERATION_STEP, self.WHEEL_ACCELERATION_LIMIT)
        inc = int(delta_units / self.WHEEL_DELTA_STEP * multiplier) * self.PERCENT_SCALE

        if not inc:
            return

        starting_interaction = not self._is_active()
        self._press_offset = True
        self._has_dragged = True

        self._apply_stylesheet(thick=True)
        if starting_interaction:
            self.started.emit()

        self.setValue(self.value() - inc)
        self._wheel_commit_timer.start()

    # --- internals --------------------------------------------------------------
    def _reset_visual_state(self):
        self._wheel_commit_timer.stop()
        signal_blocker = QtCore.QSignalBlocker(self)
        try:
            self.setValue(getattr(self, "defaultValue", 0))
            self._press_offset = None
            self._has_dragged = False
            self._apply_stylesheet(thick=False)
        finally:
            del signal_blocker

        self._wheel_count = 0
        self._prev_wheel_direction = 0
        self.update()

    def _finish_interaction(self):
        if not self._is_active():
            return
        try:
            self.finished.emit()
        finally:
            self._reset_visual_state()

    def _finish_wheel_interaction(self):
        if self._is_wheel_session() and not self.isSliderDown():
            self._finish_interaction()

    def _apply_stylesheet(self, *, thick: bool):
        h = self.handle_size()
        radius = wutil.DPI(self.HANDLE_RADIUS)
        gh = h if thick else wutil.DPI(self.THIN_GROOVE_HEIGHT)
        mt = mb = 0
        if not thick:
            mt = mb = -int((h - gh) / 2)
        if thick:
            handle_bg = self._color
            handle_border = "none"
        else:
            handle_bg = SLIDER_HANDLE_NEUTRAL_HEX
            handle_border = f"{wutil.DPI(1)}px solid {COLORS.ui.darker_gray.hex}"
        self.setStyleSheet(
            f"""
QSlider#TKMSliderHandle::groove:horizontal {{
    background: {COLORS.ui.dark_gray.hex};
    height: {gh}px;
    border-radius: {radius}px;
    margin: 0;
}}
QSlider#TKMSliderHandle::handle:horizontal {{
    width: {int(h * 1.05)}px;
    height: {h}px;
    margin-top: {mt}px;
    margin-bottom: {mb}px;
    border: {handle_border};
    border-radius: {radius}px;
    background: {handle_bg};
}}
"""
        )

    def _is_active(self) -> bool:
        return self.isSliderDown() or (self._press_offset is not None)

    def _is_wheel_session(self) -> bool:
        return self._press_offset is True

    def _groove_rect(self) -> QtCore.QRect:
        opt = QtWidgets.QStyleOptionSlider()
        self.initStyleOption(opt)
        return self.style().subControlRect(QtWidgets.QStyle.CC_Slider, opt, QtWidgets.QStyle.SC_SliderGroove, self)

    def _handle_rect(self) -> QtCore.QRect:
        opt = QtWidgets.QStyleOptionSlider()
        self.initStyleOption(opt)
        return self.style().subControlRect(QtWidgets.QStyle.CC_Slider, opt, QtWidgets.QStyle.SC_SliderHandle, self)

    def _handle_hit_rect(self) -> QtCore.QRect:
        return self._handle_rect()

    # events (no groove click)
    def mousePressEvent(self, e: QtGui.QMouseEvent):
        if e.button() == QtCore.Qt.LeftButton:
            hrect = self._handle_hit_rect()
            if hrect.contains(e.pos()):
                self._apply_stylesheet(thick=True)
                self._press_offset = e.pos().x() - hrect.x()
                self._has_dragged = False
                self.setSliderDown(True)
                self.started.emit()
                e.accept()
                return
            e.accept()  # swallow (no snap-to-groove)
            return
        super().mousePressEvent(e)

    def mouseMoveEvent(self, e: QtGui.QMouseEvent):
        # Update handle hover state
        pos = e.pos()
        hrect = self._handle_hit_rect()
        is_handle_hover = hrect.contains(pos)

        was_handle_hover = getattr(self, "_handle_hover", False)
        self._handle_hover = is_handle_hover

        if is_handle_hover != was_handle_hover and not self._is_active():
            self.update()

            if is_handle_hover:
                if hasattr(self, "_toolTipData") and (self._toolTipData.get("text") or self._toolTipData.get("description")):
                    QFlatTooltipManager.delayed_show(anchor_widget=self, **self._toolTipData)
            else:
                QFlatTooltipManager.cancel_timer()

        if self.isSliderDown() and self._press_offset is not None and not self._is_wheel_session():
            # Re-calculate track width based on style geometry
            groove_rect = self._groove_rect()
            handle_rect = self._handle_rect()
            track_left = groove_rect.left()
            track_w = groove_rect.width() - handle_rect.width()

            desired_left = e.pos().x() - int(self._press_offset)
            if track_w > 0:
                desired_left = max(track_left, min(track_left + track_w, desired_left))
                ratio = (desired_left - track_left) / track_w
            else:
                ratio = 0.0
            rng = float(self.maximum() - self.minimum())
            self.setSliderPosition(int(round(self.minimum() + ratio * rng)))
            self._has_dragged = True
            e.accept()
            return
        super().mouseMoveEvent(e)

    def mouseReleaseEvent(self, e: QtGui.QMouseEvent):
        if e.button() == QtCore.Qt.LeftButton and self.isSliderDown():
            self.setSliderDown(False)
            self._finish_interaction()
            return e.accept()
        super().mouseReleaseEvent(e)

    def wheelEvent(self, e: QtGui.QWheelEvent):
        delta = e.angleDelta().x() + e.angleDelta().y()
        self.apply_wheel_delta(delta)
        e.accept()

    def keyPressEvent(self, e):
        super().keyPressEvent(e)

    def keyReleaseEvent(self, e):
        super().keyReleaseEvent(e)

    def sliderChange(self, change):
        super().sliderChange(change)
        if change == QtWidgets.QSlider.SliderValueChange:
            self.moved.emit(self.percent())

    def paintEvent(self, e):
        super().paintEvent(e)
        p = QtGui.QPainter(self)
        hrect = self._handle_rect()
        p.setRenderHint(QtGui.QPainter.Antialiasing)

        base_color = QtGui.QColor(self._icon_color)
        handle_highlighted = getattr(self, "_handle_hover", False) or bool(self._press_offset)
        if handle_highlighted:
            main_color = QtGui.QColor(
                min(base_color.red() + 60, 255), min(base_color.green() + 60, 255), min(base_color.blue() + 60, 255), base_color.alpha()
            )
        else:
            main_color = base_color

        if self._icon:
            icon_size = int(min(hrect.width(), hrect.height()) * 0.7038)
            qicon = QtGui.QIcon(self._icon)
            if not qicon.isNull():
                icon_rect = QtCore.QRect(0, 0, icon_size, icon_size)
                icon_rect.moveCenter(hrect.center())
                qicon.paint(p, icon_rect, QtCore.Qt.AlignCenter)
        else:
            p.setFont(self._text_font)
            fm = p.fontMetrics()
            tw = fm.horizontalAdvance(self._text)
            tx = hrect.x() + (hrect.width() - tw) / 2.0
            ty = hrect.y() + (hrect.height() + fm.capHeight()) / 2.0

            path = QtGui.QPainterPath()
            path.addText(tx, ty, self._text_font, self._text)

            p.setPen(QtGui.QPen(QtGui.QColor(COLORS.ui.dark_gray.hex), wutil.DPI(2.0), QtCore.Qt.SolidLine, QtCore.Qt.RoundCap, QtCore.Qt.RoundJoin))
            p.setBrush(QtCore.Qt.NoBrush)
            p.drawPath(path)

            if handle_highlighted:
                glow_color = QtGui.QColor(255, 255, 255, 40)
                p.setBrush(glow_color)
                p.setPen(QtCore.Qt.NoPen)
                for dx, dy in [(-1, -1), (1, 1), (-1, 1), (1, -1), (0, -1), (0, 1), (-1, 0), (1, 0)]:
                    glow_path = path.translated(dx, dy)
                    p.drawPath(glow_path)

            p.setPen(QtCore.Qt.NoPen)
            p.setBrush(main_color)
            p.drawPath(path)

        if not self._press_offset:
            p.end()
            return

        # live % display while dragging/wheeling
        cx = hrect.center().x()
        mid = self.width() // 2
        pad = wutil.DPI(self.VALUE_HANDLE_PADDING)
        edge_pad = wutil.DPI(self.VALUE_EDGE_PADDING)

        if cx < mid:
            # Handle is on the left half, draw text in the right half space
            text_start = cx + hrect.width() // 2 + pad
            text_width = max(0, self.width() - text_start - edge_pad)
            text_rect = QtCore.QRect(text_start, 0, text_width, self.height())
            align = QtCore.Qt.AlignVCenter | QtCore.Qt.AlignRight
        else:
            # Handle is on the right half, draw text in the left half space
            text_width = max(0, cx - hrect.width() // 2 - pad - edge_pad)
            text_rect = QtCore.QRect(edge_pad, 0, text_width, self.height())
            align = QtCore.Qt.AlignVCenter | QtCore.Qt.AlignLeft

        p.setFont(self._value_font)
        p.setPen(QtGui.QColor(SLIDER_VALUE_TEXT_HEX))
        p.drawText(text_rect, align, f"{self.value() / float(self.PERCENT_SCALE):.2f}")
        p.end()


# --- public composite widget ----------------------------------------------------
class QFlatSliderWidget(cw.TooltipMixin, QtWidgets.QWidget):
    """
    Public composite widget.

    Signals:
      - valueChanged(float): live slider percent while dragging/wheeling/keys
      - valueSet(float): committed slider percent on release or button click
      - dragStarted()
      - dragFinished()
    """

    valueChanged = QtCore.Signal(float)
    valueSet = QtCore.Signal(float)
    dragStarted = QtCore.Signal()
    dragFinished = QtCore.Signal()
    modeSelected = QtCore.Signal(str)
    modeRequested = QtCore.Signal(str, bool)
    currentModeChanged = QtCore.Signal(object, object, object)

    def __init__(
        self,
        name: str = "TKM_Slider",
        min: int = 0,
        max: int = 100,
        color: str = "#AAAAAA",
        icon_color: Optional[str] = None,
        text: str = "",
        dragCommand: Optional[callable] = None,
        sessionFactory: Optional[callable] = None,
        tooltipTitle: str = "",
        tooltipDescription: str = "",
        tooltip=None,
        p: Optional[QtWidgets.QLayout] = None,
    ):
        super().__init__(None)
        self.setObjectName(name)

        self._scale = 1000  # internal units per 1%
        self._color = color
        self._icon_color = icon_color or color

        self._worldSpace = False
        self._frameButtons = False
        self._tooltipTitle = tooltipTitle
        self._tooltipDescription = tooltipDescription
        self._tooltip = tooltip
        self._dragCommand = None
        self._sessionFactory = sessionFactory
        self._sliderSession = None
        self._drag_active = False
        self._framePicker = None
        self._pickedFrames = {}

        self._section_parent = None
        self._section_prefix = ""
        self._internal_key = ""
        self._modifier_watch_connected = False

        self._modes: list[SliderMode | str] = []
        self._current_mode: Optional[SliderMode] = None
        self._temporary_mode: Optional[SliderMode] = None
        self._menu = None
        self._mode_transition = None
        self._mode_transition_overlay = None

        self.setContextMenuPolicy(QtCore.Qt.CustomContextMenu)
        self.customContextMenuRequested.connect(self._show_context_menu)

        # base layout: only the slider; buttons live in overlay containers
        base = QtWidgets.QHBoxLayout(self)
        base.setContentsMargins(1, 0, 1, 0)
        base.setSpacing(0)

        self._slider = SliderHandle(self, text=text, color=color, icon_color=self._icon_color)
        self._slider.setRange(int(min * self._scale), int(max * self._scale))
        self._slider.setSizePolicy(QtWidgets.QSizePolicy.Expanding, QtWidgets.QSizePolicy.Fixed)
        base.addWidget(self._slider)
        self._slider.installEventFilter(self)

        # overlay containers (left/right "stems"), on top of the slider
        self._leftOverlay = QtWidgets.QWidget(self)
        self._rightOverlay = QtWidgets.QWidget(self)
        for ov in (self._leftOverlay, self._rightOverlay):
            ov.setAttribute(QtCore.Qt.WA_StyledBackground, False)
            ov.setMouseTracking(True)
            ov.setVisible(True)
            ov.setFixedHeight(self._slider.handle_size())
            ov.installEventFilter(self)

        # layouts inside overlays
        self._leftLayout = QtWidgets.QHBoxLayout(self._leftOverlay)
        self._rightLayout = QtWidgets.QHBoxLayout(self._rightOverlay)
        for lay in (self._leftLayout, self._rightLayout):
            lay.setContentsMargins(0, 0, 0, 0)
            lay.setSpacing(0)

        values = [150, 125, 105, 100, 50, 15, 5]

        self._leftButtons = []
        self._rightButtons = []
        self._leftFrameButton = None
        self._rightFrameButton = None

        def _add_button(layout, parent_widget, percent, button_color, world_space, aggregate_list, frame_button=False):
            btn = SliderButton(parent_widget, percent=percent, color=button_color, worldSpace=world_space, frameButton=frame_button)
            btn.clicked.connect(lambda _c=False, b=btn: self._on_button_clicked(b))
            layout.addWidget(btn, 1)
            aggregate_list.append(btn)
            btn.installEventFilter(self)
            return btn

        self._leftFrameButton = _add_button(
            self._leftLayout,
            self._leftOverlay,
            0,
            SLIDER_FRAME_BUTTON_COLOR,
            False,
            self._leftButtons,
            frame_button=True,
        )
        self._leftFrameButton.hide()

        # left side buttons
        for v in values:
            if self._worldSpace:
                _worldSpace = self._worldSpace if v == 100 else False
            else:
                _worldSpace = False
            _add_button(self._leftLayout, self._leftOverlay, -abs(v), color, _worldSpace, self._leftButtons)

        for v in reversed(values):
            if self._worldSpace:
                _worldSpace = self._worldSpace if v == 100 else False
            else:
                _worldSpace = False

            _add_button(self._rightLayout, self._rightOverlay, v, color, _worldSpace, self._rightButtons)

        # right side buttons
        self._rightFrameButton = _add_button(
            self._rightLayout,
            self._rightOverlay,
            0,
            SLIDER_FRAME_BUTTON_COLOR,
            False,
            self._rightButtons,
            frame_button=True,
        )
        self._rightFrameButton.hide()

        # bridge slider signals
        self._slider.started.connect(self._on_drag_started)
        self._slider.moved.connect(self._on_drag_moved)
        self._slider.finished.connect(self._on_drag_finished)

        if dragCommand:
            self._dragCommand = dragCommand

        # initial geometry & tooltip sync
        if tooltipTitle:
            self.setTooltipInfo(tooltipTitle, tooltipDescription, tooltip)
        else:
            self._slider._update_self_tooltip()

        # Connect to global signal and initialize
        manager = runtime.get_runtime_manager()
        self.setOvershoot(settings.get_setting("sliders_overshoot", False))
        manager.overshootChanged.connect(self.setOvershoot)
        manager.undo_performed.connect(self._on_maya_undo_performed)

        # add to provided layout, if any
        if p is not None:
            try:
                # If parent is a QFlatSectionWidget, use its custom addWidget
                # that registers the widget in the toggle menu.
                if hasattr(p, "addWidget") and hasattr(p, "_widgets"):
                    p.addWidget(self, tooltipTitle or text, name)
                else:
                    p.addWidget(self)
            except Exception as e:
                print("QFlatSliderWidget: could not add to provided layout:", e)

        self._update_buttons()

        # Accept wheel focus from anywhere in the widget
        self.setFocusPolicy(QtCore.Qt.StrongFocus)

    def _connect_modifier_watch(self):
        if self._modifier_watch_connected:
            return
        try:
            runtime.get_runtime_manager().modifiers_changed.connect(self._on_modifiers_changed)
            self._modifier_watch_connected = True
        except Exception:
            self._modifier_watch_connected = False

    def _disconnect_modifier_watch(self):
        if not self._modifier_watch_connected:
            return
        try:
            runtime.get_runtime_manager().modifiers_changed.disconnect(self._on_modifiers_changed)
        except Exception:
            pass
        self._modifier_watch_connected = False

    def _find_shortcut_mode(self, mask: int, requires_mid_click: bool) -> Optional[SliderMode]:
        for mode in self._modes:
            if not isinstance(mode, SliderMode):
                continue
            if _shortcut_requires_mid_click(mode.shortcut) != bool(requires_mid_click):
                continue
            if _shortcut_to_mask(mode.shortcut) != int(mask):
                continue
            return mode
        return None

    ################################ PUBLIC API ################################

    def setText(self, text: str):
        self._slider._text = text
        self._slider._icon = text if self._slider._looks_like_icon(text) else None
        self._slider.update()

    def setColor(self, color: str):
        self._color = color
        self._slider._color = color
        self._slider._apply_stylesheet(thick=False)
        for btn in self._leftButtons + self._rightButtons:
            if btn in (self._leftFrameButton, self._rightFrameButton):
                continue
            btn.setColor(color)
        self._slider.update()

    def setIconColor(self, color: str):
        self._icon_color = color
        self._slider._icon_color = color
        self._slider.update()

    def setWorldSpace(self, enabled: bool):
        self._worldSpace = enabled
        for btn in self._leftButtons + self._rightButtons:
            if abs(int(btn.percent)) == 100:
                btn.setWorldSpace(enabled)

    def setFrameButtonsVisible(self, visible: bool):
        self._frameButtons = bool(visible)
        if self._leftFrameButton:
            self._leftFrameButton.setVisible(visible)
        if self._rightFrameButton:
            self._rightFrameButton.setVisible(visible)

    def setDragCommand(self, dragCommand: callable):
        self._dragCommand = dragCommand

    def setRange(self, min_v: int, max_v: int):
        self._slider.setRange(int(min_v * self._scale), int(max_v * self._scale))
        self._update_buttons()

    def setValue(self, v: int):
        self._slider.setValue(int(v))

    def setOvershoot(self, visible: bool):
        # Toggles overshoot buttons (> |100|) and sets range to the largest overshoot found on each side (fallback to ±100).
        left_max = 100
        right_max = 100

        for b in self._leftButtons:
            if b is self._leftFrameButton:
                continue
            p = int(b.percent)
            if abs(p) > 100:
                left_max = max(left_max, abs(p))
                b.setVisible(visible)

        for b in self._rightButtons:
            if b is self._rightFrameButton:
                continue
            p = int(b.percent)
            if abs(p) > 100:
                right_max = max(right_max, abs(p))
                b.setVisible(visible)

        if visible:
            self._slider.set_range(-left_max, right_max)
        else:
            self._slider.set_range(-100, 100)

        self._update_buttons()

    def setModes(self, modes: list[dict | str]):
        """
        Stores a list of mode definitions as SliderMode objects.
        """
        self._modes = []
        for m in modes:
            if isinstance(m, SliderMode):
                self._modes.append(m)
            elif isinstance(m, dict):
                self._modes.append(SliderMode(**m))
            else:
                self._modes.append(m)  # Likely a separator

    def setCurrentMode(self, identifier: str, temporary: bool = False):
        """Updates the current mode and adjusts UI accordingly."""
        found = None
        for m in self._modes:
            if isinstance(m, SliderMode) and (m.key == identifier or m.label == identifier):
                found = m
                break

        if found:
            if temporary:
                if self._current_mode and found.key == self._current_mode.key:
                    self._temporary_mode = None
                    self._setCurrentMode(self._current_mode)
                else:
                    self._temporary_mode = found
                    self._setCurrentMode(found)
            else:
                old_key = self._current_mode.key if self._current_mode else None
                if old_key == found.key:
                    return False
                self._current_mode = found
                self._temporary_mode = None
                self._setCurrentMode(found)
                self.currentModeChanged.emit(self, old_key, found.key)
                return True
        else:
            # Fallback for initialization or unknown keys
            old_key = self._current_mode.key if self._current_mode else None
            self._current_mode = None
            self._temporary_mode = None
            if old_key:
                self.currentModeChanged.emit(self, old_key, None)

    def setTemporaryMode(self, mask: int, requires_mid_click: bool = False) -> bool:
        if not self.idle() or not self._is_pointer_over_widget():
            return False
        mode = self._find_shortcut_mode(mask, requires_mid_click)
        if not mode:
            self.resetDefaultMode()
            return False

        active_preview_key = self._temporary_mode.key if self._temporary_mode else None
        if active_preview_key == mode.key:
            return False
        if not self._temporary_mode and self._current_mode and self._current_mode.key == mode.key:
            return False
        self.modeRequested.emit(mode.key, True)
        return True

    def resetDefaultMode(self):
        if not self._temporary_mode or not self._current_mode:
            return False
        self.modeRequested.emit(self._current_mode.key, True)
        return True

    def setTooltipInfo(self, title: str, description: str = "", tooltip=None):
        """Sets tooltip and status tip info for the widget and all its components."""
        self._tooltipTitle = title
        self._tooltipDescription = description
        self._tooltip = tooltip

        handle_command = self._tooltip_command_metadata(0)
        cw.TooltipMixin.setToolTipData(
            self,
            text=title,
            description=description,
            tooltip=tooltip,
            command_id=handle_command[0],
            command_label=handle_command[1],
            command_icon=handle_command[2],
        )

        # Update inner components
        self._slider.setTooltipInfo(
            title,
            description,
            tooltip,
            command_id=handle_command[0],
            command_label=handle_command[1],
            command_icon=handle_command[2],
        )
        for b in self._leftButtons + self._rightButtons:
            if b in (self._leftFrameButton, self._rightFrameButton):
                b.setTooltipInfo(
                    title,
                    description,
                    tooltip,
                    command_icon=b.squareIconPath,
                )
                continue
            button_command = self._tooltip_command_metadata(b.percent)
            b.setTooltipInfo(
                title,
                description,
                tooltip,
                command_id=button_command[0],
                command_label=button_command[1],
                command_icon=button_command[2],
            )

    def _tooltip_command_metadata(self, value):
        mode = self.currentMode()
        if mode is None:
            return None, None, None

        command_id = None
        if self._section_prefix:
            command_id = _slider_command_name(
                self._section_prefix,
                mode.key,
                value,
            )

        value = int(value)
        if value:
            value_text = "+{}%".format(value) if value > 0 else "{}%".format(value)
            command_label = "{} {}".format(mode.label, value_text)
        else:
            command_label = mode.label
        if value and self._section_prefix:
            variant = _slider_button_variant(value)
            command_icon = _slider_button_icon(
                self._section_prefix,
                variant,
            )
        else:
            resolved_icon = mode.resolved_icon()
            command_icon = resolved_icon if SliderHandle._looks_like_icon(resolved_icon) else None
        return command_id, command_label, command_icon

    ################################ GETTERS ################################

    def value(self) -> int:
        return int(self._slider.value())

    def percent(self) -> float:
        return round(self._slider.value() / float(self._scale), 3)

    def currentMode(self) -> Optional[SliderMode]:
        """Returns the current mode object, or the first available one as fallback."""
        if self._current_mode:
            if self._temporary_mode:
                return self._temporary_mode
            return self._current_mode
        for m in self._modes:
            if isinstance(m, SliderMode):
                return m
        return None

    def idle(self) -> bool:
        return not self._slider._is_active()

    ################################ HELPERS ################################

    def _refresh_toolTipData(self):
        if not self._is_pointer_over_widget():
            return
        data = getattr(self, "_toolTipData", None)
        if not data:
            return

        # Keep Maya status/help channels and the floating tooltip in sync.
        cw.HelpSystem.push(
            self,
            data.get("status_title") or data.get("text", ""),
            data.get("status_description") or data.get("description", ""),
        )
        QFlatTooltipManager.hide()
        QFlatTooltipManager.delayed_show(anchor_widget=self, **data)

    def _setCurrentMode(self, mode: SliderMode):
        display_value = mode.display_value()
        if display_value:
            self.setText(display_value)

        self._refresh_button_icons()
        self.setTooltipInfo(mode.label, mode.description, mode.tooltip)
        self.setWorldSpace(mode.worldSpace)
        self.setFrameButtonsVisible(mode.frameButtons)
        self._update_frame_button_tooltips()
        self._refresh_toolTipData()

    def _refresh_button_icons(self):
        """Resolve the shared square variants for this slider type."""
        has_mode = self.currentMode() is not None
        for button in self._leftButtons + self._rightButtons:
            if not has_mode or not self._section_prefix:
                button.setSquareIcon(None)
                continue
            if button in (self._leftFrameButton, self._rightFrameButton):
                variant = "frame"
            else:
                variant = _slider_button_variant(button.percent)
            button.setSquareIcon(
                _slider_button_icon(
                    self._section_prefix,
                    variant,
                )
            )

    def refreshModePresentation(self):
        """Reload the active mode icon, falling back to its text when missing."""
        mode = self.currentMode()
        if mode is not None:
            self._setCurrentMode(mode)
        self._slider.update()
        self.update()

    def on_added_to_section(self, section, key: str):
        """Called automatically by QFlatSectionWidget to establish a stable reference."""
        self._section_parent = section
        self._internal_key = key
        # Extract operational prefix, e.g. "tween" from "tween_tweener"
        parts = key.split("_")
        if len(parts) > 1:
            self._section_prefix = parts[0]
        else:
            self._section_prefix = ""
        mode = self.currentMode()
        if mode is not None:
            self._refresh_button_icons()
            self.setTooltipInfo(mode.label, mode.description, mode.tooltip)
            self._update_frame_button_tooltips()

    def _is_pointer_over_widget(self) -> bool:
        try:
            if self is None or not self.isVisible():
                return False
            return self.underMouse()
        except Exception:
            return False

    ############### CONTEXT MENU METHODS ###############

    def _show_context_menu(self, pos: QtCore.QPoint):
        if not self._modes:
            return
        QFlatTooltipManager.hide()
        section = self._section_parent

        if self._menu is not None:
            try:
                self._menu.close()
                self._menu.deleteLater()
            except RuntimeError:
                pass

        menu = cw.MenuWidget(parent=self)
        menu.setTearOffEnabled(False)
        menu.addSection("Slider Mode")
        group = QtGui.QActionGroup(menu)
        group.setExclusive(True)
        active = self.currentMode()

        for mode in self._modes:
            if mode == "separator":
                menu.addSeparator()
                continue

            label = mode.label
            shortcut_text = _format_shortcut(getattr(mode, "shortcut", None))
            if shortcut_text:
                label = "{}\t{}".format(mode.label, shortcut_text)

            mode_icon = mode.resolved_icon()
            action_args = (QtGui.QIcon(mode_icon), label) if mode_icon else (label,)
            act = menu.addAction(
                *action_args,
                description=mode.description,
                tooltip=getattr(mode, "tooltip", None),
                label=mode.label,
                command_icon=mode_icon,
            )
            act.setCheckable(True)
            act.setActionGroup(group)

            is_current = active and (mode.key == active.key or mode.label == active.label)
            act.setChecked(is_current)

            # Use the section's visible modes so this menu matches the pinning menu live.
            is_already_pinned = False
            if section and hasattr(section, "_visible_slider_mode_keys"):
                is_already_pinned = mode.key in section._visible_slider_mode_keys() and not is_current

            if is_already_pinned:
                act.setEnabled(False)

            if not is_current and not is_already_pinned:
                def _select_mode(_checked=False, mode_key=mode.key):
                    self.modeSelected.emit(mode_key)
                    self.modeRequested.emit(mode_key, False)

                act.triggered.connect(_select_mode)

        self._menu = menu

        def _release_menu(target=menu):
            if self._menu is target:
                self._menu = None
            target.deleteLater()

        menu.aboutToHide.connect(_release_menu)
        menu.popup(self.mapToGlobal(pos))

    ############### GEOMETRY MANAGER METHODS ###############
    def resizeEvent(self, e):
        super().resizeEvent(e)
        self._update_buttons()

    def _update_buttons(self):
        s = self._slider
        if not s:
            return
        grect = s._groove_rect()
        h = s.handle_size()

        side_w = max(0, (grect.width() - h) // 2)
        sx, sy = s.pos().x(), s.pos().y()
        y = sy + (s.height() - h) // 2

        self._leftOverlay.setGeometry(sx + grect.x(), y, side_w, h)
        self._rightOverlay.setGeometry(sx + grect.x() + grect.width() - side_w, y, side_w, h)

        self._leftOverlay.raise_()
        self._rightOverlay.raise_()

    def startModeTransition(self):
        """Briefly highlight the slider after a permanent mode change."""
        if self._mode_transition is not None:
            self._mode_transition.stop()
            self._mode_transition.deleteLater()
            self._mode_transition = None
        if self._mode_transition_overlay is not None:
            self._mode_transition_overlay.deleteLater()

        overlay = QtWidgets.QWidget(self)
        overlay.setAttribute(QtCore.Qt.WA_TransparentForMouseEvents, True)
        overlay.setStyleSheet("background-color: rgba(255, 255, 255, 72); border-radius: 3px;")
        overlay.setGeometry(self.rect())
        overlay.raise_()
        effect = QtWidgets.QGraphicsOpacityEffect(overlay)
        overlay.setGraphicsEffect(effect)
        effect.setOpacity(1.0)

        animation = QtCore.QPropertyAnimation(effect, b"opacity", self)
        animation.setDuration(160)
        animation.setStartValue(1.0)
        animation.setEndValue(0.0)
        animation.setEasingCurve(QtCore.QEasingCurve.OutCubic)
        self._mode_transition = animation
        self._mode_transition_overlay = overlay

        def _finish(target_animation=animation, target_overlay=overlay):
            if self._mode_transition is target_animation:
                self._mode_transition = None
            if self._mode_transition_overlay is target_overlay:
                self._mode_transition_overlay = None
            target_overlay.deleteLater()
            target_animation.deleteLater()

        animation.finished.connect(_finish)
        animation.start()

    ############### SIGNAL PLUMBING METHODS ###############

    def _on_drag_started(self):
        QFlatTooltipManager.hide()
        self._cancel_frame_picker()
        self._finish_active_session()
        self._suspend_auto_update = False
        try:
            if self._start_slider_interaction(preview=True) is None:
                return
        except Exception as exc:
            self._on_drag_error(exc)
            return

        self._drag_active = True
        self.dragStarted.emit()
        self._leftOverlay.hide()
        self._rightOverlay.hide()

    def _on_drag_moved(self, percent: float):
        self.valueChanged.emit(float(percent))
        if getattr(self, "_suspend_auto_update", False):
            return
        self._preview_slider_value(percent)

    def _on_drag_finished(self):
        if self._sliderSession is None:
            self._restore_after_drag()
            return

        try:
            if not getattr(self._slider, "_has_dragged", False):
                return
            value = self.percent()
            self.valueSet.emit(float(value))
            self._commit_slider_value(value, require_existing_session=True)
        finally:
            self._finish_active_session()
            self._restore_after_drag()

    def _on_button_clicked(self, btn: SliderButton):
        if btn in (self._leftFrameButton, self._rightFrameButton):
            self._begin_frame_picker(-1 if btn is self._leftFrameButton else 1)
            return
        self._finish_active_session()
        try:
            self.valueSet.emit(float(btn.percent))
            self._commit_slider_value(btn.percent)
        finally:
            self.dragFinished.emit()
            self._finish_active_session()

    def _begin_frame_picker(self, side):
        self._cancel_frame_picker()
        mode = self.currentMode()
        if mode is None:
            return
        active_button = self._leftFrameButton if side < 0 else self._rightFrameButton
        active_button.setChecked(True)

        def _finish_pick():
            self._framePicker = None
            active_button.setChecked(False)
            self._update_frame_button_tooltips()

        def _picked(frame):
            frames = list(self._pickedFrames.get(mode.key, (None, None)))
            frames[0 if side < 0 else 1] = int(frame)
            self._pickedFrames[mode.key] = tuple(frames)
            _finish_pick()

        def _cancelled():
            _finish_pick()

        def _previewed(frame):
            active_button.setFrameValue(int(frame))

        self._framePicker = timelineWidgets.begin_frame_picker(
            _picked,
            owner=self,
            cancel_callback=_cancelled,
            preview_callback=_previewed,
        )

    def _cancel_frame_picker(self):
        if self._framePicker is not None:
            self._framePicker.cancel()
            self._framePicker = None
        if self._leftFrameButton:
            self._leftFrameButton.setChecked(False)
        if self._rightFrameButton:
            self._rightFrameButton.setChecked(False)

    def _update_frame_button_tooltips(self):
        mode = self.currentMode()
        if mode is None:
            return
        left, right = self._pickedFrames.get(mode.key, (None, None))
        if self._leftFrameButton:
            self._leftFrameButton.setFrameValue(left)
            left_description = "Pick left target frame"
            if left is not None:
                left_description += ": {}".format(left)
            self._leftFrameButton.setTooltipInfo(
                mode.label,
                left_description,
                mode.tooltip,
                command_icon=self._leftFrameButton.squareIconPath,
            )
        if self._rightFrameButton:
            self._rightFrameButton.setFrameValue(right)
            right_description = "Pick right target frame"
            if right is not None:
                right_description += ": {}".format(right)
            self._rightFrameButton.setTooltipInfo(
                mode.label,
                right_description,
                mode.tooltip,
                command_icon=self._rightFrameButton.squareIconPath,
            )

    def _finish_active_session(self):
        session = self._sliderSession
        if session is None:
            return
        self._sliderSession = None
        session.finish()

    def _restore_after_drag(self):
        if self._drag_active:
            self._drag_active = False
            self.dragFinished.emit()
        self._leftOverlay.show()
        self._rightOverlay.show()

    def _on_maya_undo_performed(self):
        self._finish_active_session()
        if self._slider:
            self._slider._reset_visual_state()

    def _start_slider_interaction(self, *, preview: bool):
        mode = self.currentMode()
        if mode is None:
            return None

        if self._sliderSession is None:
            if self._sessionFactory is None:
                self._sliderSession = slider_utils.SliderSession(
                    mode.key,
                    title=mode.label,
                    description=mode.description,
                    tooltip=mode.tooltip,
                    tint_color=self._color,
                )
            else:
                self._sliderSession = self._sessionFactory(mode.key)
        elif self._sliderSession.mode != mode.key:
            self._sliderSession.switch_mode(
                mode.key,
                title=mode.label,
                description=mode.description,
                tooltip=getattr(mode, "tooltip", None),
            )

        if preview:
            self._sliderSession.begin_preview()

        frames = self._pickedFrames.get(mode.key, (None, None))
        self._sliderSession.left_target_frame, self._sliderSession.right_target_frame = frames

        return self._sliderSession

    def _preview_slider_value(self, value: float):
        if self._dragCommand is None:
            return

        session = self._start_slider_interaction(preview=True)
        if session is None:
            return

        timer = QtCore.QElapsedTimer()
        timer.start()

        try:
            self._dragCommand(session.mode, value, session=session)
        except Exception as exc:
            self._on_drag_error(exc)

        if timer.elapsed() >= 150:
            self._suspend_auto_update = True

    def _commit_slider_value(self, value: float, require_existing_session: bool = False):
        if self._dragCommand is None:
            return

        if require_existing_session and self._sliderSession is None:
            return

        session = self._start_slider_interaction(preview=False)
        if session is None:
            return
        session.begin_commit()

        try:
            self._dragCommand(session.mode, value, session=session)
        except Exception as exc:
            self._on_drag_error(exc)

    def _on_drag_error(self, exc):
        self._finish_active_session()

        traceback_text = "".join(traceback.format_exception(type(exc), exc, exc.__traceback__))
        report._emit_exception_to_script_editor(traceback_text)
        report.report_detected_exception(
            exc=exc,
            context="slider drag",
            source_file=report._extract_exception_source_file(exc=exc),
            traceback_text=traceback_text,
        )

        if self._slider:
            try:
                self._slider.setSliderDown(False)
                self._slider._reset_visual_state()
            except Exception:
                pass
        self._restore_after_drag()

    def _on_modifiers_changed(self, *_args):
        if not self.idle():
            return
        if not self._is_pointer_over_widget():
            return
        self.setTemporaryMode(runtime.get_modifier_mask(), requires_mid_click=False)

    ############### EVENT METHODS ###############

    def leaveEvent(self, e):
        self._disconnect_modifier_watch()
        if self._slider and self._slider._is_active() and not self._slider.isSliderDown():
            self._slider._finish_interaction()
        self.resetDefaultMode()
        super().leaveEvent(e)

    def closeEvent(self, e):
        self._disconnect_modifier_watch()
        self._cancel_frame_picker()
        if self._slider:
            self._slider._reset_visual_state()
        self._finish_active_session()
        self._restore_after_drag()
        super().closeEvent(e)

    def enterEvent(self, e):
        self._connect_modifier_watch()
        if self.idle():
            self.setTemporaryMode(runtime.get_modifier_mask(), requires_mid_click=False)
        super().enterEvent(e)

    def wheelEvent(self, e: QtGui.QWheelEvent):
        """Make the wheel change the slider"""
        delta = e.angleDelta().x() + e.angleDelta().y()
        self._slider.apply_wheel_delta(delta)
        e.accept()

    def eventFilter(self, obj, event):
        try:
            event_type = event.type()
        except Exception:
            return QtWidgets.QWidget.eventFilter(self, obj, event)

        if event_type == QtCore.QEvent.MouseButtonPress and getattr(event, "button", lambda: None)() == QtCore.Qt.MiddleButton:
            if self.setTemporaryMode(runtime.get_modifier_mask(), requires_mid_click=True):
                event.accept()
                return True

        return QtWidgets.QWidget.eventFilter(self, obj, event)
