from __future__ import annotations

from typing import Optional
import importlib

try:
    from PySide6.QtCore import Qt, QObject, QRect, Signal, QTimer, QPoint
    from PySide6.QtGui import QColor, QFont, QMouseEvent, QPainter, QWheelEvent, QPen, QPainterPath, QActionGroup
    from PySide6.QtWidgets import QHBoxLayout, QSizePolicy, QSlider, QWidget, QPushButton, QStyle, QStyleOptionSlider
    from PySide6 import QtWidgets
except ImportError:
    from PySide2.QtCore import Qt, QObject, QRect, Signal, QTimer, QPoint
    from PySide2.QtGui import QColor, QFont, QMouseEvent, QPainter, QWheelEvent, QPen, QPainterPath
    from PySide2.QtWidgets import (
        QWidget,
        QHBoxLayout,
        QSizePolicy,
        QSlider,
        QPushButton,
        QActionGroup,
        QStyle,
        QStyleOptionSlider,
    )
    from PySide2 import QtWidgets

import TheKeyMachine.mods.uiMod as ui
import TheKeyMachine.widgets.util as util
import TheKeyMachine.widgets.customWidgets as cw
import TheKeyMachine.mods.settingsMod as settings

importlib.reload(ui)
importlib.reload(util)
importlib.reload(cw)


class _GlobalSignals(QObject):
    overshootChanged = Signal(bool)


globalSignals = _GlobalSignals()


class SliderMode:
    """Professional object representation of a slider mode."""

    def __init__(self, key, label=None, icon=None, description=""):
        self.key = key
        self.label = label or key.replace("_", " ").title()
        self.icon = icon  # Short text for the handle
        self.description = description

    def __repr__(self):
        return f"<SliderMode {self.key}>"


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


COLOR = ui.Color()


# --- tiny button with centered square ------------------------------------------
class SliderButton(cw.TooltipMixin, QPushButton):
    """Flat square-indicator button that emits its signed percent on click."""

    def __init__(self, parent: QWidget, *, percent: int, color: str, worldSpace: bool = False):
        super().__init__(parent)
        self._percent = percent
        self._color = color
        self._box_sz = util.DPI(6) if abs(percent) == 100 else util.DPI(3)
        self.setFixedHeight(parent.height())
        self.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Fixed)

        self.setStyleSheet(
            f"QPushButton {{ background: none; border-radius: 0; }}QPushButton:pressed {{ background-color: {self._color}; border-radius: 0; }}"
        )

        self._worldSpace = worldSpace if abs(percent) == 100 else False
        self._hover = False

        self._tooltip_title = ""
        self._tooltip_description = ""
        # Initial tooltip
        self._update_tooltip()

    def _update_tooltip(self):
        title = self._tooltip_title or "Value"
        self.set_tooltip_data(text=f"{title}: {self._percent}%", description=self._tooltip_description)

    def set_tooltip_info(self, title: str, description: str = ""):
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
                r = int(min(w, h) * 0.275)  # smaller globe

                p.setPen(Qt.NoPen)
                p.setBrush(glow_color if is_glow else main_color)
                p.drawEllipse(QRect(cx - r, cy - r, 2 * r, 2 * r))

                if not is_glow:
                    # Black linework on top
                    pen = QPen(QColor(COLOR.color.darkGray))
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
    finished = Signal(float)

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
        self._thin_h = util.DPI(10)
        self._handle = util.DPI(24)
        self._handle_radius = util.DPI(5)
        self._padding_lr = 0
        self._pressOffset: Optional[int | bool] = None  # bool True = "wheel active"
        self._hover = False
        self._handle_hover = False
        self._tooltip_title = ""
        self._tooltip_description = ""

        self._wheel_count = 0
        self._prev_wheel_direction = 0

        # wheel-reset timer (end interaction after a pause)
        self._wheel_reset_timer = QTimer(self)
        self._wheel_reset_timer.setSingleShot(True)
        self._wheel_reset_timer.setInterval(500)
        self._wheel_reset_timer.timeout.connect(self._reset_without_emit)

        # fonts
        self._value_font = QFont()
        self._value_font.setPointSize(util.DPI(14))
        self._text_font = QFont()
        self._text_font.setPointSize(util.DPI(8.5))

        # size
        self.setFixedWidth(util.DPI(200))
        self.setFixedHeight(util.DPI(24))

        self.valueChanged.connect(self._update_self_tooltip)

        self._apply_stylesheet(thick=False)

    def set_tooltip_info(self, title: str, description: str = ""):
        self._tooltip_title = title
        self._tooltip_description = description
        self._update_self_tooltip()

    def enterEvent(self, e):
        self._hover = True
        self.update()
        # super().enterEvent(e)

    def leaveEvent(self, e):
        self._hover = False
        self._handle_hover = False
        from TheKeyMachine.tooltips import QFlatTooltipManager

        QFlatTooltipManager.hide()

        # Added: Finalize wheel/drag visuals only when leaving the widget
        if self._pressOffset is not None and not self.isSliderDown():
            self._reset_without_emit()

        self.update()
        super().leaveEvent(e)

    def _update_self_tooltip(self, _v=None):
        title = self._tooltip_title or self._text
        self.set_tooltip_data(text=title, description=self._tooltip_description)

    # --- public helpers ---------------------------------------------------------
    def handle_size(self) -> int:
        return self._handle

    def percent(self) -> float:
        # internal units = thousandths of a percent
        return round(self.value() / 1000.0, 3)

    def set_percent(self, pct: float):
        self.setValue(int(round(pct * 1000)))
        self.moved.emit(self.percent())
        self.finished.emit(self.percent())

    def set_range(self, min_v: int, max_v: int):
        self.setRange(int(min_v * 1000), int(max_v * 1000))

    def apply_wheel_delta(self, delta_units: int):
        """Centralized wheel logic used by both this slider and the parent widget."""
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

        # adjust
        self.setValue(self.value() - inc)
        self.moved.emit(self.percent())

        # mark interaction as active for paint overlay
        self._pressOffset = True

    # --- internals --------------------------------------------------------------
    def _reset_without_emit(self):
        reset = util.ResetWithoutEmit(self)
        reset()
        self.finished.emit(self.percent())
        self._wheel_count = 0
        self._prev_wheel_direction = 0
        self._pressOffset = None
        self._apply_stylesheet(thick=False)
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
            handle_bg = COLOR.color.gray
            handle_border = f"{util.DPI(1)}px solid {COLOR.color.darkerGray}"
        self.setStyleSheet(
            f"""
QSlider::groove:horizontal {{
    background: {COLOR.color.darkGray};
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
        # active when dragging OR wheeling (wheeling sets _pressOffset to non-None)
        return self.isSliderDown() or (self._pressOffset is not None)

    # geometry helpers
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
            from TheKeyMachine.tooltips import QFlatTooltipManager

            if is_handle_hover:
                if hasattr(self, "_tooltip_data") and (self._tooltip_data.get("text") or self._tooltip_data.get("description")):
                    QFlatTooltipManager.delayed_show(anchor_widget=self, **self._tooltip_data)
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
            self.finished.emit(self.percent())
            self._reset_without_emit()
            self._pressOffset = None
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

        # label text with thin outline
        p.setFont(self._text_font)
        fm = p.fontMetrics()
        tw = fm.horizontalAdvance(self._text)
        # Calculate baseline position to center text in hrect
        tx = hrect.x() + (hrect.width() - tw) / 2.0
        ty = hrect.y() + (hrect.height() + fm.capHeight()) / 2.0

        path = QPainterPath()
        path.addText(tx, ty, self._text_font, self._text)

        # Draw thin outline (drawn first so it sits BEHIND the fill, growing only outwards)
        p.setPen(QPen(QColor(COLOR.color.darkGray), util.DPI(2.0), Qt.SolidLine, Qt.RoundCap, Qt.RoundJoin))
        p.setBrush(Qt.NoBrush)
        p.drawPath(path)

        base_color = QColor(self._color)
        if getattr(self, "_handle_hover", False):
            main_color = QColor(
                min(base_color.red() + 60, 255), min(base_color.green() + 60, 255), min(base_color.blue() + 60, 255), base_color.alpha()
            )
            glow_color = QColor(255, 255, 255, 40)
            # draw silhouette glow by shifting path
            p.setBrush(glow_color)
            p.setPen(Qt.NoPen)
            for dx, dy in [(-1, -1), (1, 1), (-1, 1), (1, -1), (0, -1), (0, 1), (-1, 0), (1, 0)]:
                glow_path = path.translated(dx, dy)
                p.drawPath(glow_path)
        else:
            main_color = base_color

        # Draw fill (drawn ON TOP of the outline, covering the inner half of the stroke)
        p.setPen(Qt.NoPen)
        p.setBrush(main_color)
        p.drawPath(path)

        if not self._pressOffset:
            p.end()
            return

        # live % display while dragging/wheeling
        cx = hrect.center().x()
        mid = self.width() // 2
        pad = util.DPI(10)  # slightly more padding from handle
        edge_pad = util.DPI(14)  # padding from the widget edges

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
        p.setPen(QColor(COLOR.color.lightGray))
        p.drawText(text_rect, align, f"{self.value() / 1000.0:.2f}")
        p.end()


# --- public composite widget ----------------------------------------------------
class QFlatSliderWidget(cw.TooltipMixin, QWidget):
    """
    Public composite widget.

    Signals:
      - valueChanged(float): slider percent (drag/wheel/keys or side buttons)
      - dragStarted()
      - dragFinished()
    """

    valueChanged = Signal(float)
    dragStarted = Signal()
    dragFinished = Signal()
    modeSelected = Signal(str)

    def __init__(
        self,
        name: str,
        min: int = -100,
        max: int = 100,
        text: str = "SL",
        color: str = "#444444",
        dragCommand=None,
        dropCommand=None,
        worldSpace=None,
        p=None,
        tooltipTitle: str = "",
        tooltipDescription: str = "",
    ):
        super().__init__(None)
        if name:
            self.setObjectName(name)

        self._scale = 1000  # internal units per 1%
        self._color = color
        self._worldSpace = worldSpace
        self._tooltipTitle = tooltipTitle
        self._tooltipDescription = tooltipDescription
        self._section_parent = None
        self._section_prefix = ""
        self._internal_key = ""

        self._modes: list[SliderMode | str] = []
        self._current_mode: Optional[SliderMode] = None
        self._menu = None

        self.setContextMenuPolicy(Qt.CustomContextMenu)
        self.customContextMenuRequested.connect(self._show_context_menu)

        # base layout: only the slider; buttons live in overlay containers
        base = QHBoxLayout(self)
        base.setContentsMargins(0, 0, 0, 0)
        base.setSpacing(0)

        self._slider = SliderHandle(self, text=text, color=color)
        self._slider.setRange(int(min * self._scale), int(max * self._scale))
        self._slider.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Fixed)
        base.addWidget(self._slider)

        # overlay containers (left/right "stems"), on top of the slider
        self._leftOverlay = QWidget(self)
        self._rightOverlay = QWidget(self)
        for ov in (self._leftOverlay, self._rightOverlay):
            ov.setAttribute(Qt.WA_StyledBackground, False)
            ov.setMouseTracking(True)
            ov.setVisible(True)
            ov.setFixedHeight(self._slider._handle)

        # layouts inside overlays
        self._leftLayout = QHBoxLayout(self._leftOverlay)
        self._rightLayout = QHBoxLayout(self._rightOverlay)
        for lay in (self._leftLayout, self._rightLayout):
            lay.setContentsMargins(0, 0, 0, 0)
            lay.setSpacing(0)

        values = [150, 125, 105, 100, 50, 15, 5]

        # left side buttons (near handle => AlignRight)
        self._leftButtons = []
        for v in values:
            b = SliderButton(self._leftOverlay, percent=-abs(v), color=color, worldSpace=self._worldSpace)
            b.clicked.connect(lambda _c=False, btn=b: self._on_button_clicked(btn))
            self._leftLayout.addWidget(b, 1)
            self._leftButtons.append(b)

        # right side buttons (AlignLeft)
        self._rightButtons = []
        for v in reversed(values):
            b = SliderButton(self._rightOverlay, percent=v, color=color)
            b.clicked.connect(lambda _c=False, btn=b: self._on_button_clicked(btn))
            self._rightLayout.addWidget(b, 1)
            self._rightButtons.append(b)

        # bridge slider signals
        self._slider.started.connect(self._on_drag_started)
        self._slider.moved.connect(self._on_inner_moved)
        self._slider.finished.connect(self._on_inner_finished)
        self._slider.valueChanged.connect(lambda _v: self.valueChanged.emit(self.percent()))

        if dragCommand:
            self.valueChanged.connect(dragCommand)
        if dropCommand:
            self.dragFinished.connect(dropCommand)

        # initial geometry & tooltip sync
        if tooltipTitle:
            self.setTooltipInfo(tooltipTitle, tooltipDescription)
        else:
            self._slider._update_self_tooltip()

        self._update_buttons()

        # Connect to global signal and initialize
        self.setOvershoot(settings.get_setting("sliders_overshoot", False))
        globalSignals.overshootChanged.connect(self.setOvershoot)

        # add to provided layout, if any
        if p is not None:
            try:
                # If parent is a QFlatSectionWidget, use its custom addWidget
                # that registers the widget in the toggle menu.
                if hasattr(p, "addWidget") and hasattr(p, "_widgets"):
                    p.addWidget(self, tooltipTitle or text, name or "slider")
                else:
                    p.addWidget(self)
            except Exception as e:
                print("QFlatSliderWidget: could not add to provided layout:", e)

        # Accept wheel focus from anywhere in the widget
        self.setFocusPolicy(Qt.StrongFocus)

    # --- public API -------------------------------------------------------------
    def setText(self, text: str):
        self._slider._text = text
        self._slider.update()

    def setColor(self, color: str):
        self._slider._color = color
        self._slider._apply_stylesheet(thick=False)
        self._slider.update()

    def setTooltipInfo(self, title: str, description: str = ""):
        """Sets tooltip and status tip info for the widget and all its components."""
        self._tooltipTitle = title
        self._tooltipDescription = description

        # Update the mixin state for the main widget (handles statusTip)
        cw.TooltipMixin.set_tooltip_info(self, title, description)

        # Update inner components
        self._slider.set_tooltip_info(title, description)
        for b in self._leftButtons:
            b.set_tooltip_info(title, description)
        for b in self._rightButtons:
            b.set_tooltip_info(title, description)

    def set_tooltip_info(self, title: str, description: str = ""):
        """Snake-case alias for compatibility."""
        self.setTooltipInfo(title, description)

    def setWorldSpace(self, enabled: int):
        if enabled == self._worldSpace:
            return

        for b in self._leftButtons:
            p = int(b.percent)
            if abs(p) == 100:
                b.setWorldSpace(enabled)

        for b in self._rightButtons:
            p = int(b.percent)
            if abs(p) == 100:
                b.setWorldSpace(enabled)

        self._worldSpace = enabled

    def setDragCommand(self, dragCommand):
        try:
            self.valueChanged.disconnect()
        except Exception:
            pass
        self.valueChanged.connect(dragCommand)

    def setDropCommand(self, dropCommand):
        try:
            self.dragFinished.disconnect()
        except Exception:
            pass
        self.dragFinished.connect(dropCommand)

    def setRange(self, min_v: int, max_v: int):
        self._slider.setRange(int(min_v * self._scale), int(max_v * self._scale))
        self._update_buttons()

    def setValue(self, v: int):
        """NOTE: retains original behavior (expects raw internal units)."""
        self._slider.setValue(int(v))

    def value(self) -> int:
        """Raw internal value (thousandths of percent)."""
        return int(self._slider.value())

    def percent(self) -> float:
        return round(self._slider.value() / float(self._scale), 3)

    def set_percent(self, pct: float):
        self._slider.setValue(int(round(pct * self._scale)))

    def setOvershoot(self, visible: bool):
        # Toggle only overshoot buttons (> |100|) and set range to the largest
        # overshoot found on each side (fallback to ±100).
        left_max = 100
        right_max = 100

        for b in self._leftButtons:
            p = int(b.percent)
            if abs(p) > 100:
                b.setVisible(visible)
                left_max = max(left_max, abs(p))

        for b in self._rightButtons:
            p = int(b.percent)
            if abs(p) > 100:
                b.setVisible(visible)
                right_max = max(right_max, abs(p))

        if visible:
            self._slider.set_range(-left_max, right_max)
        else:
            self._slider.set_range(-100, 100)

        self._update_buttons()

    def wheelEvent(self, e: QWheelEvent):
        """Make the wheel change the slider"""
        delta = e.angleDelta().x() + e.angleDelta().y()
        self._slider.apply_wheel_delta(delta)
        e.accept()

    def setModes(self, modes: list[dict | str]):
        """
        Stores a list of mode definitions as SliderMode objects.
        """
        self._modes = []
        for m in modes:
            if isinstance(m, dict):
                self._modes.append(SliderMode(**m))
            else:
                self._modes.append(m)  # Likely "separator"

    def setCurrentMode(self, identifier: str):
        """Updates the current mode and adjusts UI accordingly."""
        found = None
        for m in self._modes:
            if isinstance(m, SliderMode) and (m.key == identifier or m.label == identifier):
                found = m
                break

        if found:
            # Notify the section BEFORE changing _current_mode so it can unregister the old key
            section = getattr(self, "_section_parent", None)
            if section and hasattr(section, "notify_mode_changed"):
                old_key = self._current_mode.key if self._current_mode else None
                section.notify_mode_changed(self, old_key, found.key)

            self._current_mode = found
            if found.icon:
                self.setText(found.icon)
        else:
            # Fallback for initialization or unknown keys
            self._current_mode = None

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

    def _get_active_mode(self) -> Optional[SliderMode]:
        """Returns the current mode object, or the first available one as fallback."""
        if self._current_mode:
            return self._current_mode
        for m in self._modes:
            if isinstance(m, SliderMode):
                return m
        return None

    def _show_context_menu(self, pos: QPoint):
        if not self._modes:
            return

        # Use the stable reference established during section registration
        section = self._section_parent

        menu = cw.MenuWidget(parent=self)
        group = QActionGroup(menu)
        active = self._get_active_mode()

        for mode in self._modes:
            if mode == "separator":
                menu.addSeparator()
                continue

            act = menu.addAction(mode.label, description=mode.description)
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
                    is_already_pinned = (
                        occupying_widget is not None
                        and occupying_widget is not self
                        and occupying_widget.isVisible()
                    )

            if is_current or is_already_pinned:
                act.setEnabled(False)

            act.triggered.connect(lambda *args, m=mode: self.modeSelected.emit(m.key))

        menu.exec_(self.mapToGlobal(pos))
        menu.deleteLater()

    # --- geometry mgmt for overlays --------------------------------------------
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

        Args:
            flashes (int): Number of flashes (default: 2).
            interval (int): Duration in ms for each on/off toggle (default: 120).
        """
        overlay = QWidget(self)
        overlay.setStyleSheet("background-color: white;")
        overlay.setGeometry(self.rect())
        overlay.raise_()

        count = 0

        def toggle():
            nonlocal count
            if count >= flashes * 2:
                overlay.deleteLater()
                return
            overlay.setVisible(count % 2 == 0)
            count += 1
            QTimer.singleShot(interval, toggle)

        # Start first toggle
        toggle()

    # --- signal plumbing --------------------------------------------------------
    def _on_drag_started(self):
        from TheKeyMachine.tooltips import QFlatTooltipManager

        QFlatTooltipManager.hide()

        self.dragStarted.emit()
        self._leftOverlay.hide()
        self._rightOverlay.hide()

    def _on_inner_moved(self, pct: float):
        self.valueChanged.emit(self.percent())

    def _on_inner_finished(self, pct: float):
        self.dragFinished.emit()
        self._leftOverlay.show()
        self._rightOverlay.show()

    def _on_button_clicked(self, btn: SliderButton):
        self.valueChanged.emit(float(btn.percent))

    def leaveEvent(self, e):
        # Finalize the interaction if we were wheeling when the mouse leaves the widget
        if self._slider and self._slider._pressOffset is not None and not self._slider.isSliderDown():
            self._slider._reset_without_emit()
        super().leaveEvent(e)
