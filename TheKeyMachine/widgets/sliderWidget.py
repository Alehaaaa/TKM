from __future__ import annotations

from typing import Optional
import os
import importlib
import traceback

try:
    from PySide6.QtCore import Qt, QObject, QRect, Signal, QTimer, QPoint, QEvent, QSignalBlocker # type: ignore
    from PySide6.QtGui import QColor, QCursor, QFont, QMouseEvent, QPainter, QWheelEvent, QPen, QPainterPath, QActionGroup, QIcon # type: ignore
    from PySide6.QtWidgets import QHBoxLayout, QSizePolicy, QSlider, QWidget, QPushButton, QStyle, QStyleOptionSlider, QLayout # type: ignore
except ImportError:
    from PySide2.QtCore import Qt, QObject, QRect, Signal, QTimer, QPoint, QEvent, QSignalBlocker # type: ignore
    from PySide2.QtGui import QColor, QCursor, QFont, QMouseEvent, QPainter, QWheelEvent, QPen, QPainterPath, QIcon # type: ignore
    from PySide2.QtWidgets import QWidget, QHBoxLayout, QSizePolicy, QSlider, QPushButton, QActionGroup, QStyle, QStyleOptionSlider, QLayout # type: ignore

import TheKeyMachine.mods.uiMod as ui
import TheKeyMachine.mods.reportMod as report
import TheKeyMachine.widgets.util as wutil
import TheKeyMachine.widgets.customWidgets as cw
import TheKeyMachine.mods.settingsMod as settings
from TheKeyMachine.sliders import api as slider_api
import TheKeyMachine.core.runtime_manager as runtime
from TheKeyMachine.tools import colors as toolColors

from TheKeyMachine.tooltips import QFlatTooltipManager, format_tooltip_shortcut

importlib.reload(ui)
importlib.reload(report)
importlib.reload(wutil)
importlib.reload(cw)
importlib.reload(settings)


class _GlobalSignals(QObject):
    overshootChanged = Signal(bool)
    eulerFilterChanged = Signal(bool)


globalSignals = _GlobalSignals()


class SliderMode:
    """Professional object representation of a slider mode."""

    def __init__(self, key, label=None, icon=None, description="", worldSpace=False, frameButtons=False, shortcut=None):
        self.key = key
        self.label = label or key.replace("_", " ").title()
        self.icon = icon  # Short text for the handle
        self.description = description
        self.worldSpace = worldSpace
        self.frameButtons = frameButtons
        self.shortcut = list(shortcut or [])

    def __repr__(self):
        return f"<SliderMode {self.key}>"


class ResetWithoutEmit:
    """Context manager to reset a slider without triggering signal emissions."""

    def __init__(self, slider: QSlider):
        self._slider = slider
        self._blocker = None

    def __enter__(self):
        self._blocker = QSignalBlocker(self._slider)
        self._slider.setValue(getattr(self._slider, "defaultValue", 0))
        return self

    def __exit__(self, exc_type, exc_val, exc_tb):
        self._blocker = None


"""
QFlatSliderWidget — COLOR-faithful, single-file recreation (no picks)
===============================================================

Self-contained slider that mimics the original AnimBot/COLOR style but
behaves like a tweenmachine: a centered horizontal scrub from -100..+100.
No A/B picks. Context menu on right-click (hook point kept).

What's new (same behavior, nicer structure):
- Wheel works from anywhere inside QFlatSliderWidget (buttons/overlays/empty).
- Centralized wheel logic via apply_wheel_delta().
- Clearer separation of responsibilities & comments.

PySide6 or PySide2 (Maya 2017+). No external COLOR import.
"""


UI_COLORS = toolColors.UI_COLORS
SLIDER_HANDLE_NEUTRAL_HEX = "#444444"
SLIDER_VALUE_TEXT_HEX = "#747474"


def _format_shortcut(shortcut) -> str:
    return format_tooltip_shortcut(shortcut)


def _shortcut_to_mask(shortcut) -> int:
    shortcut = shortcut or []
    mask = 0
    if Qt.Key_Shift in shortcut:
        mask |= 1
    if Qt.Key_Control in shortcut:
        mask |= 4
    if Qt.Key_Alt in shortcut:
        mask |= 8
    return mask


def _shortcut_requires_mid_click(shortcut) -> bool:
    return Qt.MiddleButton in (shortcut or [])


# --- tiny button with centered square ------------------------------------------
class SliderButton(cw.TooltipMixin, QPushButton):
    """Flat square-indicator button that emits its signed percent on click."""

    def __init__(self, parent: QWidget, *, percent: int, color: str, worldSpace: bool = False, frameButton: bool = False):
        super().__init__(parent)
        self._percent = percent
        self._color = color
        self._frameButton = bool(frameButton)
        self._box_sz = wutil.DPI(7) if (self._frameButton or abs(percent) == 100) else wutil.DPI(3)
        self.setFixedHeight(parent.height())
        self.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Fixed)

        self.setStyleSheet(
            f"QPushButton {{ background: none; border-radius: 0; }}QPushButton:pressed {{ background-color: {self._color}; border-radius: 0; }}"
        )

        self._worldSpace = worldSpace
        self._hover = False

        self._tooltip_title = ""
        self._tooltip_description = ""
        # Initial tooltip
        self._update_tooltip()

    def setColor(self, color: str):
        self._color = color
        self.update()

    def _update_tooltip(self):
        title = self._tooltip_title or "Value"
        value_label = "Set Frame" if self._frameButton else f"{self._percent}%"
        self.setToolTipData(text=f"{title}: {value_label}", description=self._tooltip_description)

    def setTooltipInfo(self, title: str, description: str = ""):
        self._tooltip_title = title
        self._tooltip_description = description
        self._update_tooltip()

    @property
    def percent(self) -> int:
        return self._percent

    def setWorldSpace(self, enabled: int):
        self._worldSpace = enabled
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
        p = QPainter(self)
        p.setRenderHint(QPainter.Antialiasing)

        w, h, s = self.width(), self.height(), self._box_sz
        x = (w - s) // 2
        y = (h - s) // 2

        base_color = QColor(self._color)
        if getattr(self, "_hover", False):
            main_color = QColor(
                min(base_color.red() + 60, 255), min(base_color.green() + 60, 255), min(base_color.blue() + 60, 255), base_color.alpha()
            )
            glow_color = QColor(255, 255, 255, 40)
            # Create a list of 8 offsets for silhouette glow + (0, 0) for main draw
            offsets = [(-1, -1), (1, 1), (-1, 1), (1, -1), (0, -1), (0, 1), (-1, 0), (1, 0), (0, 0)]
        else:
            main_color = base_color
            glow_color = Qt.transparent
            offsets = [(0, 0)]

        for dx, dy in offsets:
            is_glow = dx != 0 or dy != 0

            p.save()
            p.translate(dx, dy)

            if self._worldSpace:
                cx, cy = w // 2, h // 2
                r = wutil.DPI(int(min(w, h) * 0.24))  # smaller globe

                p.setPen(Qt.NoPen)
                p.setBrush(glow_color if is_glow else main_color)
                p.drawEllipse(QRect(cx - r, cy - r, 2 * r, 2 * r))

                if not is_glow:
                    # Black linework on top
                    pen = QPen(QColor(UI_COLORS.dark_gray.hex))
                    pen.setWidthF(0.85)
                    p.setPen(pen)
                    p.setBrush(Qt.NoBrush)

                    # Outer circle outline
                    p.drawEllipse(QRect(cx - r, cy - r, 2 * r, 2 * r))

                    # Equator
                    p.drawLine(cx - r + 1, cy, cx + r - 1, cy)

                    # Curved meridians (left/right)
                    mer_w = int(2 * r * 0.45)  # tweak curvature here (0.5–0.65 looks good)
                    mer_rect = QRect(cx - mer_w // 2, cy - r, mer_w, 2 * r)
                    p.drawArc(mer_rect, 90 * 14, 180 * 16)  # left arc
                    p.drawArc(mer_rect, 90 * 14, -180 * 16)  # right arc
            else:
                # Default: small filled square
                if is_glow:
                    p.setPen(Qt.NoPen)
                else:
                    p.setPen(QPen(Qt.black, 0.5))

                p.setBrush(glow_color if is_glow else main_color)
                p.drawRect(QRect(x, y, s, s))

            p.restore()
        p.end()


# --- core slider (custom painting & handle-only interaction) --------------------
class SliderHandle(cw.TooltipMixin, QSlider):
    """Horizontal slider that only drags when grabbing the handle."""

    started = Signal()
    moved = Signal(float)
    finished = Signal()

    def __init__(self, parent: QWidget, *, text: str, color: str):
        super().__init__(Qt.Horizontal, parent)

        # behavior
        self.setMouseTracking(True)
        self.setFocusPolicy(Qt.ClickFocus)
        self.setSingleStep(1)
        self.setPageStep(5)

        # theme/state
        self._color = color
        self._text = text
        self._thin_h = wutil.DPI(10)
        self._handle = wutil.DPI(24)
        self._handle_radius = wutil.DPI(5)
        self._padding_lr = 0
        self._pressOffset: Optional[int | bool] = None
        self._hover = False
        self._handle_hover = False
        self._tooltip_title = ""
        self._tooltip_description = ""
        self._icon_path = text if self._looks_like_icon_path(text) else None

        self._wheel_count = 0
        self._prev_wheel_direction = 0

        # fonts
        self._value_font = QFont()
        self._value_font.setPointSize(wutil.DPI(14))
        self._text_font = QFont()
        self._text_font.setPixelSize(int(wutil.DPI(11)))

        # size
        self.setFixedWidth(wutil.DPI(200))
        self.setFixedHeight(wutil.DPI(24))

        self._apply_stylesheet(thick=False)

    def setTooltipInfo(self, title: str, description: str = ""):
        self._tooltip_title = title
        self._tooltip_description = description
        self._update_self_tooltip()

    def enterEvent(self, e):
        self._hover = True
        self.update()
        super().enterEvent(e)

    def leaveEvent(self, e):
        QFlatTooltipManager.hide()

        self._hover = False
        self._handle_hover = False

        if self._pressOffset is not None and not self.isSliderDown():
            self._reset()

        self.update()
        super().leaveEvent(e)

    def _update_self_tooltip(self, _v=None):
        title = self._tooltip_title or self._text
        self.setToolTipData(text=title, description=self._tooltip_description)

    @staticmethod
    def _looks_like_icon_path(value: str) -> bool:
        if not value or not isinstance(value, str):
            return False
        return os.path.isabs(value) or os.path.splitext(value)[1].lower() in {".svg", ".png", ".jpg", ".jpeg", ".bmp", ".ico"}

    # --- public helpers ---------------------------------------------------------
    def handle_size(self) -> int:
        return self._handle

    def percent(self) -> float:
        # internal units = thousandths of a percent
        return round(self.value() / 1000.0, 3)

    def set_range(self, min_v: int, max_v: int):
        self.setRange(int(min_v * 1000), int(max_v * 1000))

    def apply_wheel_delta(self, delta_units: int):
        """Centralized wheel logic for slider."""
        # Acceleration logic: start smaller, get bigger
        direction = 1 if delta_units > 0 else -1
        if direction != self._prev_wheel_direction:
            self._wheel_count = 0
        self._prev_wheel_direction = direction
        self._wheel_count += 1

        # Multiplier: grows steadily with each notch
        multiplier = 1.0 + min(self._wheel_count * 0.2, 8.0)
        inc = int(delta_units / 15.0 * multiplier) * 1000

        if not inc:
            return

        # enter "active" visuals
        self._apply_stylesheet(thick=True)
        if not self.isSliderDown():
            self.started.emit()

        self.setValue(self.value() - inc)
        self.moved.emit(self.percent())

        self._pressOffset = True

    # --- internals --------------------------------------------------------------
    def _reset(self):
        self.finished.emit()

        with ResetWithoutEmit(self):
            self._pressOffset = None
            self._apply_stylesheet(thick=False)

        self._wheel_count = 0
        self._prev_wheel_direction = 0
        self.update()

    def _apply_stylesheet(self, *, thick: bool):
        h = self._handle
        gh = h if thick else self._thin_h
        mt = mb = 0
        if not thick:
            mt = mb = -int((h - gh) / 2)
        if thick:
            handle_bg = self._color
            handle_border = "none"
        else:
            handle_bg = SLIDER_HANDLE_NEUTRAL_HEX
            handle_border = f"{wutil.DPI(1)}px solid {UI_COLORS.darker_gray.hex}"
        self.setStyleSheet(
            f"""
QSlider::groove:horizontal {{
    background: {UI_COLORS.dark_gray.hex};
    height: {gh}px;
    border-radius: {self._handle_radius}px;
    margin: 0;
}}
QSlider::handle:horizontal {{
    width: {int(h * 1.05)}px;
    height: {h}px;
    margin-top: {mt}px;
    margin-bottom: {mb}px;
    border: {handle_border};
    border-radius: {self._handle_radius}px;
    background: {handle_bg};
}}
"""
        )

    def _is_active(self) -> bool:
        return self.isSliderDown() or (self._pressOffset is not None)

    def _groove_rect(self) -> QRect:
        opt = QStyleOptionSlider()
        self.initStyleOption(opt)
        return self.style().subControlRect(QStyle.CC_Slider, opt, QStyle.SC_SliderGroove, self)

    def _handle_rect(self) -> QRect:
        opt = QStyleOptionSlider()
        self.initStyleOption(opt)
        return self.style().subControlRect(QStyle.CC_Slider, opt, QStyle.SC_SliderHandle, self)

    def _handle_hit_rect(self) -> QRect:
        return self._handle_rect()

    # events (no groove click)
    def mousePressEvent(self, e: QMouseEvent):
        if e.button() == Qt.LeftButton:
            hrect = self._handle_hit_rect()
            if hrect.contains(e.pos()):
                self._apply_stylesheet(thick=True)
                self._pressOffset = e.pos().x() - hrect.x()
                self.setSliderDown(True)
                self.started.emit()
                e.accept()
                return
            e.accept()  # swallow (no snap-to-groove)
            return
        super().mousePressEvent(e)

    def mouseMoveEvent(self, e: QMouseEvent):
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

        if self.isSliderDown() and self._pressOffset is not None and self._pressOffset is not True:
            # Re-calculate track width based on style geometry
            groove_rect = self._groove_rect()
            handle_rect = self._handle_rect()
            track_left = groove_rect.left()
            track_w = groove_rect.width() - handle_rect.width()

            desired_left = e.pos().x() - int(self._pressOffset)
            if track_w > 0:
                desired_left = max(track_left, min(track_left + track_w, desired_left))
                ratio = (desired_left - track_left) / track_w
            else:
                ratio = 0.0
            rng = float(self.maximum() - self.minimum())
            self.setSliderPosition(int(round(self.minimum() + ratio * rng)))
            self.moved.emit(self.percent())
            e.accept()
            return
        super().mouseMoveEvent(e)

    def mouseReleaseEvent(self, e: QMouseEvent):
        if e.button() == Qt.LeftButton and self.isSliderDown():
            self.setSliderDown(False)
            self._apply_stylesheet(thick=False)
            self.finished.emit()

            self._reset()
            self._pressOffset = None
            return e.accept()
        super().mouseReleaseEvent(e)

    def wheelEvent(self, e: QWheelEvent):
        delta = e.angleDelta().x() + e.angleDelta().y()
        self.apply_wheel_delta(delta)
        e.accept()

    def keyPressEvent(self, e):
        super().keyPressEvent(e)
        self.moved.emit(self.percent())

    def keyReleaseEvent(self, e):
        super().keyReleaseEvent(e)
        self.moved.emit(self.percent())

    def sliderChange(self, change):
        super().sliderChange(change)
        if change == QSlider.SliderValueChange:
            self.moved.emit(self.percent())

    def paintEvent(self, e):
        super().paintEvent(e)
        p = QPainter(self)
        hrect = self._handle_rect()
        p.setRenderHint(QPainter.Antialiasing)

        base_color = QColor(self._color)
        handle_highlighted = getattr(self, "_handle_hover", False) or bool(self._pressOffset)
        if handle_highlighted:
            main_color = QColor(
                min(base_color.red() + 60, 255), min(base_color.green() + 60, 255), min(base_color.blue() + 60, 255), base_color.alpha()
            )
        else:
            main_color = base_color

        if self._icon_path:
            icon_size = int(min(hrect.width(), hrect.height()) * 0.68)
            qicon = QIcon(self._icon_path)
            if not qicon.isNull():
                icon_rect = QRect(0, 0, icon_size, icon_size)
                icon_rect.moveCenter(hrect.center())
                if handle_highlighted:
                    qicon = cw.QFlatHoverableIcon._color_icon(qicon, main_color, icon_rect.size())
                qicon.paint(p, icon_rect, Qt.AlignCenter)
        else:
            p.setFont(self._text_font)
            fm = p.fontMetrics()
            tw = fm.horizontalAdvance(self._text)
            tx = hrect.x() + (hrect.width() - tw) / 2.0
            ty = hrect.y() + (hrect.height() + fm.capHeight()) / 2.0

            path = QPainterPath()
            path.addText(tx, ty, self._text_font, self._text)

            p.setPen(QPen(QColor(UI_COLORS.dark_gray.hex), wutil.DPI(2.0), Qt.SolidLine, Qt.RoundCap, Qt.RoundJoin))
            p.setBrush(Qt.NoBrush)
            p.drawPath(path)

            if handle_highlighted:
                glow_color = QColor(255, 255, 255, 40)
                p.setBrush(glow_color)
                p.setPen(Qt.NoPen)
                for dx, dy in [(-1, -1), (1, 1), (-1, 1), (1, -1), (0, -1), (0, 1), (-1, 0), (1, 0)]:
                    glow_path = path.translated(dx, dy)
                    p.drawPath(glow_path)

            p.setPen(Qt.NoPen)
            p.setBrush(main_color)
            p.drawPath(path)

        if not self._pressOffset:
            p.end()
            return

        # live % display while dragging/wheeling
        cx = hrect.center().x()
        mid = self.width() // 2
        pad = wutil.DPI(10)  # slightly more padding from handle
        edge_pad = wutil.DPI(14)  # padding from the widget edges

        if cx < mid:
            # Handle is on the left half, draw text in the right half space
            text_start = cx + hrect.width() // 2 + pad
            text_width = max(0, self.width() - text_start - edge_pad)
            text_rect = QRect(text_start, 0, text_width, self.height())
            align = Qt.AlignVCenter | Qt.AlignRight
        else:
            # Handle is on the right half, draw text in the left half space
            text_width = max(0, cx - hrect.width() // 2 - pad - edge_pad)
            text_rect = QRect(edge_pad, 0, text_width, self.height())
            align = Qt.AlignVCenter | Qt.AlignLeft

        p.setFont(self._value_font)
        p.setPen(QColor(SLIDER_VALUE_TEXT_HEX))
        p.drawText(text_rect, align, f"{self.value() / 1000.0:.2f}")
        p.end()


# --- public composite widget ----------------------------------------------------
class QFlatSliderWidget(cw.TooltipMixin, QWidget):
    """
    Public composite widget.

    Signals:
      - valueChanged(float): live slider percent while dragging/wheeling/keys
      - valueSet(float): committed slider percent on release or button click
      - dragStarted()
      - dragFinished()
    """

    valueChanged = Signal(float)
    valueSet = Signal(float)
    dragStarted = Signal()
    dragFinished = Signal()
    modeSelected = Signal(str)
    modeRequested = Signal(str, bool)

    def __init__(
        self,
        name: str = "TKM_Slider",
        min: int = 0,
        max: int = 100,
        color: str = "#AAAAAA",
        text: str = "",
        dragCommand: Optional[callable] = None,
        tooltipTitle: str = "",
        tooltipDescription: str = "",
        p: Optional[QLayout] = None,
    ):
        super().__init__(None)
        self.setObjectName(name)

        self._scale = 1000  # internal units per 1%
        self._color = color

        self._worldSpace = False
        self._frameButtons = False
        self._tooltipTitle = tooltipTitle
        self._tooltipDescription = tooltipDescription
        self._dragCommand = None
        self._sliderSession = None

        self._section_parent = None
        self._section_prefix = ""
        self._internal_key = ""
        self._modifier_watch_connected = False

        self._modes: list[SliderMode | str] = []
        self._current_mode: Optional[SliderMode] = None
        self._temporary_mode: Optional[SliderMode] = None
        self._menu = None

        self.setContextMenuPolicy(Qt.CustomContextMenu)
        self.customContextMenuRequested.connect(self._show_context_menu)

        # base layout: only the slider; buttons live in overlay containers
        base = QHBoxLayout(self)
        base.setContentsMargins(1, 0, 1, 0)
        base.setSpacing(0)

        self._slider = SliderHandle(self, text=text, color=color)
        self._slider.setRange(int(min * self._scale), int(max * self._scale))
        self._slider.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Fixed)
        base.addWidget(self._slider)
        self._slider.installEventFilter(self)

        # overlay containers (left/right "stems"), on top of the slider
        self._leftOverlay = QWidget(self)
        self._rightOverlay = QWidget(self)
        for ov in (self._leftOverlay, self._rightOverlay):
            ov.setAttribute(Qt.WA_StyledBackground, False)
            ov.setMouseTracking(True)
            ov.setVisible(True)
            ov.setFixedHeight(self._slider._handle)
            ov.installEventFilter(self)

        # layouts inside overlays
        self._leftLayout = QHBoxLayout(self._leftOverlay)
        self._rightLayout = QHBoxLayout(self._rightOverlay)
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
            "#d7d7d7",
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
            "#d7d7d7",
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
            self.setTooltipInfo(tooltipTitle, tooltipDescription)
        else:
            self._slider._update_self_tooltip()

        # Connect to global signal and initialize
        self.setOvershoot(settings.get_setting("sliders_overshoot", False))
        globalSignals.overshootChanged.connect(self.setOvershoot)

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
        self.setFocusPolicy(Qt.StrongFocus)

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
        self._slider._icon_path = text if self._slider._looks_like_icon_path(text) else None
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
            if isinstance(m, dict):
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
                # Notify the section BEFORE changing _current_mode so it can unregister the old key
                section = getattr(self, "_section_parent", None)
                if section and hasattr(section, "notify_mode_changed"):
                    old_key = self._current_mode.key if self._current_mode else None
                    section.notify_mode_changed(self, old_key, found.key)

                self._current_mode = found
                self._temporary_mode = None
                self._setCurrentMode(found)
        else:
            # Fallback for initialization or unknown keys
            self._current_mode = None
            self._temporary_mode = None

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

    def setTooltipInfo(self, title: str, description: str = ""):
        """Sets tooltip and status tip info for the widget and all its components."""
        self._tooltipTitle = title
        self._tooltipDescription = description

        # Update the mixin state for the main widget (handles statusTip)
        cw.TooltipMixin.setTooltipInfo(self, title, description)

        # Update inner components
        self._slider.setTooltipInfo(title, description)
        for b in self._leftButtons + self._rightButtons:
            b.setTooltipInfo(title, description)


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
        if mode.icon:
            self.setText(mode.icon)

        self.setTooltipInfo(mode.label, mode.description)
        self.setWorldSpace(mode.worldSpace)
        self.setFrameButtonsVisible(mode.frameButtons)
        self._refresh_toolTipData()

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

    def _is_pointer_over_widget(self) -> bool:
        try:
            if self is None or not self.isVisible():
                return False
            return self.underMouse()
        except Exception:
            return False


    ############### CONTEXT MENU METHODS ###############

    def _show_context_menu(self, pos: QPoint):
        if not self._modes:
            return
        # Use the stable reference established during section registration
        section = self._section_parent

        menu = cw.MenuWidget(parent=self)
        menu.setTearOffEnabled(False)
        group = QActionGroup(menu)
        active = self.currentMode()

        for mode in self._modes:
            if mode == "separator":
                menu.addSeparator()
                continue

            label = mode.label
            shortcut_text = _format_shortcut(getattr(mode, "shortcut", None))
            if shortcut_text:
                label = "{}\t{}".format(mode.label, shortcut_text)

            act = menu.addAction(label, description=mode.description)
            act.setCheckable(True)
            act.setActionGroup(group)

            is_current = active and (mode.key == active.key or mode.label == active.label)
            act.setChecked(is_current)

            # Use the section's authoritative _mode_to_slot for an O(1) exclusivity check
            is_already_pinned = False
            if section and hasattr(section, "_mode_to_slot"):
                occupying_slot = section._mode_to_slot.get(mode.key)
                if occupying_slot:
                    occupying_widget = section._widgets.get(occupying_slot)
                    is_already_pinned = occupying_widget is not None and occupying_widget is not self and occupying_widget.isVisible()

            if is_current or is_already_pinned:
                act.setEnabled(False)

            act.triggered.connect(lambda *args, m=mode: self.modeSelected.emit(m.key))
            act.triggered.connect(lambda *args, m=mode: self.modeRequested.emit(m.key, False))

        menu.exec_(self.mapToGlobal(pos))
        menu.deleteLater()

    ############### GEOMETRY MANAGER METHODS ###############
    def resizeEvent(self, e):
        super().resizeEvent(e)
        self._update_buttons()

    def _update_buttons(self):
        s = self._slider
        if not s:
            return
        grect = s._groove_rect()
        h = s._handle

        side_w = max(0, (grect.width() - h) // 2)
        sx, sy = s.pos().x(), s.pos().y()
        y = sy + (s.height() - h) // 2

        self._leftOverlay.setGeometry(sx + grect.x(), y, side_w, h)
        self._rightOverlay.setGeometry(sx + grect.x() + grect.width() - side_w, y, side_w, h)

        self._leftOverlay.raise_()
        self._rightOverlay.raise_()

    def startFlash(self, flashes: int = 3, interval: int = 40):
        """
        Overlay the widget in white a given number of flashes, then remove it.

        flashes (int): Number of flashes.
        interval (int): Duration in ms for each flash.
        """
        overlay = QWidget(self)
        overlay.setStyleSheet("background-color: white;")
        overlay.setGeometry(self.rect())
        overlay.raise_()

        count = 0

        def flash():
            nonlocal count
            if count >= flashes * 2:
                overlay.deleteLater()
                return
            overlay.setVisible(count % 2 == 0)
            count += 1
            QTimer.singleShot(interval, flash)

        flash()

    ############### SIGNAL PLUMBING METHODS ###############

    def _on_drag_started(self):
        QFlatTooltipManager.hide()

        self.dragStarted.emit()

        self._leftOverlay.hide()
        self._rightOverlay.hide()

    def _on_drag_moved(self, percent: float):
        self.valueChanged.emit(float(percent))
        self._run_dragCommand(percent)

    def _on_drag_finished(self):
        self.dragFinished.emit()
        self._finish_active_session()

        self._leftOverlay.show()
        self._rightOverlay.show()

    def _on_button_clicked(self, btn: SliderButton):
        try:
            self.valueSet.emit(float(btn.percent))
            self._run_dragCommand(btn.percent)
        finally:
            self.dragFinished.emit()
            self._finish_active_session()
    
    def _finish_active_session(self):
        if self._sliderSession is not None:
            self._sliderSession.finish()
            self._sliderSession = None


    def _run_dragCommand(self, value: float):
        if self._dragCommand is None:
            return

        mode = self.currentMode()
        if mode is None:
            return

        if self._sliderSession is None:
            self._sliderSession = slider_api.create_session(mode.key)
        elif self._sliderSession.mode != mode.key:
            self._sliderSession.switch_mode(mode.key)

        try:
            self._dragCommand(mode.key, value, session=self._sliderSession)
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
                self._slider._reset()
            except Exception:
                pass

    def _on_modifiers_changed(self, *_args):
        if not self.idle():
            return
        if not self._is_pointer_over_widget():
            return
        self.setTemporaryMode(runtime.get_modifier_mask(), requires_mid_click=False)


    ############### EVENT METHODS ###############

    def leaveEvent(self, e):
        self._disconnect_modifier_watch()
        self.resetDefaultMode()
        # Finalize the interaction if we were wheeling when the mouse leaves the widget
        if self._slider and self._slider._pressOffset is not None and not self._slider.isSliderDown():
            self._slider._reset()
        super().leaveEvent(e)

    def enterEvent(self, e):
        self._connect_modifier_watch()
        if self.idle():
            self.setTemporaryMode(runtime.get_modifier_mask(), requires_mid_click=False)
        super().enterEvent(e)

    def wheelEvent(self, e: QWheelEvent):
        """Make the wheel change the slider"""
        delta = e.angleDelta().x() + e.angleDelta().y()
        self._slider.apply_wheel_delta(delta)
        e.accept()

    def eventFilter(self, obj, event):
        try:
            event_type = event.type()
        except Exception:
            return QWidget.eventFilter(self, obj, event)

        if event_type == QEvent.MouseButtonPress and getattr(event, "button", lambda: None)() == Qt.MiddleButton:
            if self.setTemporaryMode(runtime.get_modifier_mask(), requires_mid_click=True):
                event.accept()
                return True

        return QWidget.eventFilter(self, obj, event)
