from __future__ import annotations
"""
SliderWidget — COLOR-faithful, single-file recreation (no picks)
===============================================================

Self-contained slider that mimics the original AnimBot/COLOR style but
behaves like a tweenmachine: a centered horizontal scrub from -100..+100.
No A/B picks. Context menu on right-click (hook point kept).

What's new (same behavior, nicer structure):
- Wheel works from anywhere inside SliderWidget (buttons/overlays/empty).
- Centralized wheel logic via apply_wheel_delta().
- Clearer separation of responsibilities & comments.

PySide6 or PySide2 (Maya 2017+). No external COLOR import.
"""

from typing import Optional

# --- Qt compat (PySide6 / PySide2) ---------------------------------------------
try:  # Maya 2025+
    # from shiboken6 import wrapInstance  # type: ignore
    from PySide6.QtCore import Qt, QRect, Signal, QTimer, QSignalBlocker, QPoint  # type: ignore
    from PySide6.QtGui import QColor, QFont, QMouseEvent, QPainter, QWheelEvent, QPen  # type: ignore
    from PySide6.QtWidgets import ( # type: ignore
        QHBoxLayout, QSizePolicy, QSlider, QWidget, QPushButton
    )  # type: ignore
    PYSIDE = 6
except ImportError:  # Maya 2017–2024
    # from shiboken2 import wrapInstance
    from PySide2.QtCore import Qt, QRect, Signal, QTimer, QSignalBlocker, QPoint
    from PySide2.QtGui import QColor, QFont, QMouseEvent, QPainter, QWheelEvent, QPen
    from PySide2.QtWidgets import (
        QHBoxLayout, QSizePolicy, QSlider, QWidget, QPushButton
    )
    PYSIDE = 2

# Optional in Maya contexts; harmless if unused
try:
    import maya.OpenMayaUI as mui
except ImportError:
    import maya.api.OpenMayaUI as mui


import TheKeyMachine.mods.uiMod as ui



COLOR = ui.Color()


# --- utility: reset slider value without emitting signals -----------------------
class _ResetWithoutEmit:
    def __init__(self, slider: QSlider):
        self._slider = slider

    def __call__(self):
        blocker = QSignalBlocker(self._slider)
        self._slider.setValue(getattr(self._slider, "defaultValue", 0))
        if hasattr(self._slider, "_apply_stylesheet"):
            self._slider._apply_stylesheet(thick=False)  # type: ignore[attr-defined]
        if hasattr(self._slider, "_pressOffset"):
            self._slider._pressOffset = None  # type: ignore[attr-defined]


# --- tiny button with centered square ------------------------------------------
class _SliderButton(QPushButton):
    """Flat square-indicator button that emits its signed percent on click."""
    def __init__(self, parent: QWidget, *, percent: int, color: str, worldSpace: bool = False):
        super().__init__(parent)
        self._percent = percent
        self._color = color
        self._box_sz = 6 if abs(percent) == 100 else 3
        self.setFixedHeight(parent.height())
        self.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Fixed)
        self.setToolTip(f"{percent:+d}%")
        self.setStatusTip(f"{percent:+d}%")
        self.setStyleSheet(
            "QPushButton { background: none; border-radius: 0; }"
            f"QPushButton:pressed {{ background-color: {self._color}; border-radius: 0; }}"
        )

        self._worldSpace = worldSpace if abs(percent) == 100 else False

    @property
    def percent(self) -> int:
        return self._percent
    
    def setWorldSpace(self, enabled: int):
        self._worldSpace = enabled
        self.update()


    def paintEvent(self, e):
        super().paintEvent(e)
        p = QPainter(self)
        p.setRenderHint(QPainter.Antialiasing)

        w, h, s = self.width(), self.height(), self._box_sz
        x = (w - s) // 2
        y = (h - s) // 2

        if self._worldSpace:
            cx, cy = w // 2, h // 2
            r = int(min(w, h) * 0.275)  # smaller globe

            # Fill the circle with self._color (background)
            p.setPen(Qt.NoPen)
            p.setBrush(QColor(self._color))
            p.drawEllipse(QRect(cx - r, cy - r, 2 * r, 2 * r))

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
            mer_w = int(2 * r * 0.45)               # tweak curvature here (0.5–0.65 looks good)
            mer_rect = QRect(cx - mer_w // 2, cy - r, mer_w, 2 * r)
            p.drawArc(mer_rect, 90 * 14,  180 * 16)  # left arc
            p.drawArc(mer_rect, 90 * 14, -180 * 16)  # right arc
        else:
            # Default: small filled square
            p.setPen(QPen(Qt.black, 0.5))
            p.setBrush(QColor(self._color))
            p.drawRect(QRect(x, y, s, s))

        p.end()



# --- core slider (custom painting & handle-only interaction) --------------------
class _HandleOnlySlider(QSlider):
    """Horizontal slider that only drags when grabbing the handle."""
    started = Signal()
    moved = Signal(float)
    finished = Signal(float)

    def __init__(self, parent: QWidget, *, value: int, text: str, color: str):
        super().__init__(Qt.Horizontal, parent)

        # behavior
        self.setMouseTracking(True)
        self.setFocusPolicy(Qt.ClickFocus)
        self.setSingleStep(1)
        self.setPageStep(5)

        # theme/state
        self.defaultValue = value
        self._color = color
        self._text = text
        self._thin_h = 10
        self._handle = 24
        self._handle_radius = 5
        self._border_px = 1
        self._padding_lr = 8
        self._pressOffset: Optional[int | bool] = None  # bool True = "wheel active"
        self._hover = False

        # wheel-reset timer (end interaction after a pause)
        self._wheel_reset_timer = QTimer(self)
        self._wheel_reset_timer.setSingleShot(True)
        self._wheel_reset_timer.setInterval(500)
        self._wheel_reset_timer.timeout.connect(self._reset_without_emit)

        # fonts
        self._value_font = QFont()
        self._value_font.setPointSize(14)
        self._text_font = QFont()
        self._text_font.setPointSize(8)

        # size
        self.setFixedWidth(200)
        self.setFixedHeight(24)

        self.setToolTip(f"Slider for {text}")
        self.setStatusTip(f"Slider for {text}")

        self._apply_stylesheet(thick=False)

        # sync moved on any value change
        self.valueChanged.connect(lambda _v: self.moved.emit(self.percent()))

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
        inc = int(delta_units / 5.0) * 1000  # 120 units ≈ 6% per notch
        if not inc:
            return

        # enter "active" visuals
        self._apply_stylesheet(thick=True)
        if not self.isSliderDown():
            self.started.emit()

        # adjust
        self.setValue(self.value() + inc)
        self.moved.emit(self.percent())

        # mark interaction as active for paint overlay
        self._pressOffset = True

        # debounce finish
        self._wheel_reset_timer.stop()
        self._wheel_reset_timer.start()

    # --- internals --------------------------------------------------------------
    def _reset_without_emit(self):
        reset = _ResetWithoutEmit(self)
        reset()
        self.finished.emit(self.percent())

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
            handle_border = f"{self._border_px}px solid {COLOR.color.darkerGray}"
        self.setStyleSheet(
            f"""
QSlider::groove:horizontal {{
    background: {COLOR.color.darkGray};
    height: {gh}px;
    border-radius: {self._handle_radius}px;
    margin: 0 {self._padding_lr}px;
}}
QSlider::handle:horizontal {{
    width: {int(h*1.05)}px;
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
        gh = self._handle if self._is_active() else self._thin_h
        return QRect(self._padding_lr, (self.height() - gh)//2,
                    self.width()-2*self._padding_lr, gh)

    def _handle_rect(self) -> QRect:
        track_w = self.width() - 2*self._padding_lr - self._handle
        if track_w <= 0:
            x = self._padding_lr
        else:
            rng = float(self.maximum() - self.minimum())
            ratio = (self.sliderPosition() - self.minimum()) / (rng or 1.0)
            x = int(self._padding_lr + ratio * track_w)
        gh = self._handle if self._is_active() else self._thin_h
        y  = (self.height() - gh) // 2
        return QRect(x, y, self._handle, gh)

    def _handle_hit_rect(self) -> QRect:
        r = self._handle_rect()
        r.setY((self.height() - self._handle) // 2)
        r.setHeight(self._handle)
        return r

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
        if self.isSliderDown() and self._pressOffset is not None and self._pressOffset is not True:
            track_left = self._padding_lr
            track_w = self.width() - 2 * self._padding_lr - self._handle
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

        # text shadow
        p.setPen(QColor(QColor(COLOR.color.darkGray)))
        for dx, dy in [(-1, 0), (1, 0), (0, -1), (0, 1)]:
            p.drawText(hrect.translated(dx, dy), Qt.AlignCenter, self._text)

        # label text
        p.setFont(self._text_font)
        p.setPen(QColor(self._color))
        p.drawText(hrect, Qt.AlignCenter, self._text)

        if not self._pressOffset:
            p.end()
            return

        # live % display while dragging/wheeling
        g = self._groove_rect()
        cx = hrect.center().x()
        mid = self.width() // 2
        pad = 6
        if cx < mid:
            text_rect = QRect(cx + hrect.width() // 2 + pad, g.y(),
                              g.right() - (cx + hrect.width() // 2) - pad + 1, g.height())
            align = Qt.AlignVCenter | Qt.AlignRight
        else:
            text_rect = QRect(g.x(), g.y(),
                              max(0, cx - hrect.width() // 2 - pad - g.x()), g.height())
            align = Qt.AlignVCenter | Qt.AlignLeft
        p.setFont(self._value_font)
        p.setPen(QColor(COLOR.color.lightGray))
        p.drawText(text_rect, align, f"{self.value() / 1000.0:.2f}")
        p.end()


# --- public composite widget ----------------------------------------------------
class SliderWidget(QWidget):
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

    def __init__(
        self,
        name: str,
        min: int = -100,
        max: int = 100,
        value: int = 0,
        text: str = "SL",
        color: str = "#444444",
        dragCommand=None,
        dropCommand=None,
        worldSpace=None,
        p=None
    ):
        super().__init__(None)
        if name:
            self.setObjectName(name)

        self._scale = 1000  # internal units per 1%
        self._color = color
        self._worldSpace = worldSpace

        # base layout: only the slider; buttons live in overlay containers
        base = QHBoxLayout(self)
        base.setContentsMargins(0, 0, 0, 0)
        base.setSpacing(0)

        self._slider = _HandleOnlySlider(self, value=int(value * self._scale), text=text, color=color)
        self._slider.setRange(int(min * self._scale), int(max * self._scale))
        self._slider.setSizePolicy(QSizePolicy.Fixed, QSizePolicy.Fixed)
        base.addWidget(self._slider, 0, Qt.AlignCenter)

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
            b = _SliderButton(self._leftOverlay, percent=-abs(v), color=color, worldSpace=self._worldSpace)
            b.clicked.connect(lambda _c=False, btn=b: self._on_button_clicked(btn))
            self._leftLayout.addWidget(b, 1)
            self._leftButtons.append(b)


        # right side buttons (AlignLeft)
        self._rightButtons = []
        for v in reversed(values):
            b = _SliderButton(self._rightOverlay, percent=v, color=color)
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

        # initial geometry sync
        self._update_buttons()

        # add to provided layout, if any
        if p is not None:
            try:
                p.addWidget(self)
            except Exception as e:
                print("SliderWidget: could not add to provided layout:", e)

        # Nice-to-have: accept wheel focus from anywhere in the widget
        self.setFocusPolicy(Qt.StrongFocus)

    # --- public API -------------------------------------------------------------
    def setText(self, text: str):
        self._slider._text = text

    def setColor(self, color: str):
        self._slider._color = color
        self._slider._apply_stylesheet(thick=False)
    
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
        try: self.valueChanged.disconnect()
        except Exception: pass
        self.valueChanged.connect(dragCommand)
    
    def setDropCommand(self, dropCommand):
        try: self.dragFinished.disconnect()
        except Exception: pass
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

    # --- parent-wide wheel handling --------------------------------------------
    def wheelEvent(self, e: QWheelEvent):
        """Make the wheel change the slider even if the cursor is over overlays/buttons."""
        delta = e.angleDelta().x() + e.angleDelta().y()
        self._slider.apply_wheel_delta(delta)
        e.accept()

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

    # --- signal plumbing --------------------------------------------------------
    def _on_drag_started(self):
        self.dragStarted.emit()
        self._leftOverlay.hide()
        self._rightOverlay.hide()

    def _on_inner_moved(self, pct: float):
        self.valueChanged.emit(self.percent())

    def _on_inner_finished(self, pct: float):
        self.dragFinished.emit()
        self._leftOverlay.show()
        self._rightOverlay.show()

    def _on_button_clicked(self, btn: _SliderButton):
        # keep existing behavior: emit valueChanged with the button's percent
        self.valueChanged.emit(float(btn.percent))
