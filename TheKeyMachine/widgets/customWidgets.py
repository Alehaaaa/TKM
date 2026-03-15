from __future__ import annotations
import re

"""
TheKeyMachine Custom Widgets
===========================
Centralized repository for UI components used throughout the toolbar.
Includes QFlatToolButton with automated sizing, hover effects (glow), 
and user preference integration.
"""

try:
    from PySide6 import QtWidgets, QtCore, QtGui

    PYSIDE = 6
except ImportError:
    from PySide2 import QtWidgets, QtCore, QtGui

    PYSIDE = 2


try:
    import TheKeyMachine_user_data.preferences.user_preferences as user_preferences  # type: ignore
except ImportError:
    user_preferences = None


class QFlatHoverableIcon:
    HIGHLIGHT_HEX = "#282828"

    @staticmethod
    def apply(btn, icon_path, highlight=False, brighten_amount=80):
        if not icon_path:
            return

        base_icon = QtGui.QIcon(icon_path)
        icon_size = btn.iconSize()

        if highlight:
            btn._icon_normal = QFlatHoverableIcon._color_icon(base_icon, QFlatHoverableIcon.HIGHLIGHT_HEX, icon_size)
        else:
            btn._icon_normal = base_icon

        # For hover, we create a brightened version WITH a 2px glow effect
        btn._icon_hover = QFlatHoverableIcon._generate_hover_icon(btn._icon_normal, icon_size, brighten_amount)
        btn.setIcon(btn._icon_normal)

    @staticmethod
    def _color_icon(icon: QtGui.QIcon, color: str | QtGui.QColor, size: QtCore.QSize) -> QtGui.QIcon:
        if isinstance(color, (str, bytes)):
            color = QtGui.QColor(color)

        pix = icon.pixmap(size)
        img = pix.toImage()
        for x in range(img.width()):
            for y in range(img.height()):
                c = img.pixelColor(x, y)
                if c.alpha() > 0:
                    img.setPixelColor(x, y, QtGui.QColor(color.red(), color.green(), color.blue(), c.alpha()))

        return QtGui.QIcon(QtGui.QPixmap.fromImage(img))

    @staticmethod
    def _generate_hover_icon(icon: QtGui.QIcon, size: QtCore.QSize, brighten: int) -> QtGui.QIcon:
        # 1. Get the original pixmap and create a brightened version for the "top" part
        pix = icon.pixmap(size)
        img = pix.toImage().convertToFormat(QtGui.QImage.Format_ARGB32)

        # Slightly brighten the primary icon so it's the brightest part
        bright_img = img.copy()
        for x in range(bright_img.width()):
            for y in range(bright_img.height()):
                c = bright_img.pixelColor(x, y)
                if c.alpha() > 0:
                    bright_img.setPixelColor(
                        x,
                        y,
                        QtGui.QColor(
                            min(c.red() + 40, 255),
                            min(c.green() + 40, 255),
                            min(c.blue() + 40, 255),
                            c.alpha(),
                        ),
                    )
        bright_pix = QtGui.QPixmap.fromImage(bright_img)

        # 2. Add very subtle 1px glow effect behind it
        out_pix = QtGui.QPixmap(size)
        out_pix.fill(QtCore.Qt.transparent)

        painter = QtGui.QPainter(out_pix)
        painter.setRenderHint(QtGui.QPainter.Antialiasing)
        painter.setRenderHint(QtGui.QPainter.SmoothPixmapTransform)

        # Create a white "glow silhouette" (softer)
        glow_img = img.copy()
        for x in range(glow_img.width()):
            for y in range(glow_img.height()):
                c = glow_img.pixelColor(x, y)
                if c.alpha() > 0:
                    # Softer white glow (alpha 5)
                    glow_img.setPixelColor(x, y, QtGui.QColor(255, 255, 255, 5))

        glow_pix = QtGui.QPixmap.fromImage(glow_img)

        # Draw silhouette at tight 1px offsets (this creates the 1px border)
        for dx, dy in [(-1, -1), (1, 1), (-1, 1), (1, -1), (0, -1), (0, 1), (-1, 0), (1, 0)]:
            painter.drawPixmap(dx, dy, glow_pix)

        # Draw the brightened icon on top (centered)
        painter.drawPixmap(0, 0, bright_pix)
        painter.end()

        return QtGui.QIcon(out_pix)


class MenuWidget(QtWidgets.QMenu):
    def __init__(self, title=None, parent=None):
        if isinstance(title, QtWidgets.QWidget) and parent is None:
            parent = title
            title = None
        super(MenuWidget, self).__init__(title or "", parent)
        if parent and hasattr(parent, "destroyed"):
            parent.destroyed.connect(self.close)
        self.setMouseTracking(True)

    def mouseReleaseEvent(self, e):
        act = self.actionAt(e.pos()) or self.activeAction()
        try:
            if (
                act
                and act.isEnabled()
                and act.isCheckable()
                and not isinstance(act, QtWidgets.QWidgetAction)
                and getattr(act, "menu", lambda: None)() is None
            ):
                act.setChecked(not act.isChecked())
                act.trigger()
                e.accept()
                return
        except Exception:
            pass
        return super(MenuWidget, self).mouseReleaseEvent(e)


class TooltipMixin:
    def set_tooltip_data(self, text="", description="", shortcuts=None, icon=None):
        self._tooltip_data = {"text": text, "description": description, "shortcuts": shortcuts or [], "icon": icon}

        def clean_line(raw):
            if not raw:
                return ""
            # Remove all tags
            res = re.sub(r"<[^>]*>", "", raw)
            # Normalize whitespace
            res = re.sub(r"\s+", " ", res).strip()
            return res

        def get_status_desc(raw):
            if not raw:
                return ""
            # Split by line breakers to get the first actual line/paragraph
            parts = re.split(r"<br\s*/?>|\r?\n", raw, flags=re.IGNORECASE)
            for p in parts:
                clean = clean_line(p)
                if clean:
                    return clean
            return ""

        c_text = clean_line(text)
        c_desc = get_status_desc(description)

        if c_text and c_desc:
            status = f"{c_text} - {c_desc}"
        else:
            status = c_text or c_desc

        if hasattr(self, "setStatusTip"):
            self.setStatusTip(status)

    def set_tooltip_info(self, title: str, description: str = ""):
        self.set_tooltip_data(text=title, description=description)

    def enterEvent(self, event: QtCore.QEvent):
        from TheKeyMachine.tooltips import QFlatTooltipManager

        if hasattr(self, "_tooltip_data") and (self._tooltip_data.get("text") or self._tooltip_data.get("description")):
            QFlatTooltipManager.delayed_show(anchor_widget=self, **self._tooltip_data)
        try:
            super().enterEvent(event)
        except (AttributeError, TypeError):
            pass

    def leaveEvent(self, event: QtCore.QEvent):
        # QFlatTooltipManager.hide()  <-- Removed to let tooltip's internal check_auto_close handle it
        try:
            super().leaveEvent(event)
        except (AttributeError, TypeError):
            pass


class QFlatSpinBox(TooltipMixin, QtWidgets.QSpinBox):
    def __init__(self, *args, tooltip=None, **kwargs):
        super().__init__(*args, **kwargs)
        self.setButtonSymbols(QtWidgets.QAbstractSpinBox.NoButtons)
        if tooltip:
            self.set_tooltip_data(text=tooltip)

    def enterEvent(self, event: QtCore.QEvent):
        self.setButtonSymbols(QtWidgets.QAbstractSpinBox.UpDownArrows)
        super().enterEvent(event)

    def leaveEvent(self, event: QtCore.QEvent):
        self.setButtonSymbols(QtWidgets.QAbstractSpinBox.NoButtons)
        super().leaveEvent(event)


class QFlatToolButton(TooltipMixin, QtWidgets.QToolButton):
    def __init__(self, parent=None, icon=None, tooltip=None, description=None, shortcuts=None, highlight=False, pressed_color=None):
        super().__init__(parent)
        self.setCursor(QtCore.Qt.PointingHandCursor)
        self.setAutoRaise(True)
        self.pressed_color = pressed_color or "#666666"

        # Enforce styling: squared corners, no border on hover, background on press
        self.setStyleSheet(f"""
            QToolButton {{
                border: none;
                border-radius: 0px;
                background-color: transparent;
            }}
            QToolButton:hover {{
                border: none;
                background-color: transparent;
            }}
            QToolButton:pressed {{
                background-color: {self.pressed_color};
            }}
        """)

        # Centralized size
        w = 28
        h = 28
        if user_preferences:
            w = getattr(user_preferences, "toolbar_icon_w", 28)
            h = getattr(user_preferences, "toolbar_icon_h", 28)

        self.setFixedSize(w, h)
        # Small margin to prevent glow clipping (w-2 x h-2)
        self.setIconSize(QtCore.QSize(w - 2, h - 2))

        self._icon_path = icon
        if icon:
            QFlatHoverableIcon.apply(self, icon, highlight=highlight)

        self.set_tooltip_data(text=tooltip, description=description, shortcuts=shortcuts)

    def enterEvent(self, event: QtCore.QEvent):
        if hasattr(self, "_icon_hover"):
            self.setIcon(self._icon_hover)
        super().enterEvent(event)

    def leaveEvent(self, event: QtCore.QEvent):
        if hasattr(self, "_icon_normal"):
            self.setIcon(self._icon_normal)
        super().leaveEvent(event)
