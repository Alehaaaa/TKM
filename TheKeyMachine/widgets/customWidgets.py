from __future__ import annotations
from TheKeyMachine.tooltips import QFlatTooltipManager
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
    def __init__(self, *args, **kwargs):
        description = kwargs.pop("description", None)
        
        icon = None
        new_args = []
        for arg in args:
            if isinstance(arg, QtGui.QIcon):
                icon = arg
            else:
                new_args.append(arg)
                
        QtWidgets.QMenu.__init__(self, *new_args, **kwargs)

        if self.parent() and hasattr(self.parent(), "destroyed"):
            self.parent().destroyed.connect(self.close)
            
        if icon:
            self.setIcon(icon)
        
        if description:
            self.setProperty("description", description)
            title = self.title().replace("&", "").strip()
            self.setStatusTip("{} - {}".format(title, description))

        self.triggered.connect(self._on_action_triggered)
        self.hovered.connect(self._on_action_hovered)
        self._last_hovered_action = None

    def addAction(self, *args, **kwargs):
        description = kwargs.pop("description", None)
        action = QtWidgets.QMenu.addAction(self, *args, **kwargs)
        if description:
            action.setProperty("description", description)
            title = action.text().replace("&", "").strip()
            action.setStatusTip("{} - {}".format(title, description))
        return action

    def addMenu(self, *args, **kwargs):
        description = kwargs.pop("description", None)
        item = QtWidgets.QMenu.addMenu(self, *args, **kwargs)
        if description:
            # item can be QMenu or QAction depending on the overload
            action = item.menuAction() if hasattr(item, "menuAction") else item
            action.setProperty("description", description)
            title = action.text().replace("&", "").strip()
            action.setStatusTip("{} - {}".format(title, description))
        return item

    def _on_action_hovered(self, action):
        if not action or self.actionGeometry(action).isNull():
            return

        if action == self._last_hovered_action and QFlatTooltipManager.is_active():
            return

        QFlatTooltipManager.hide()
        self._last_hovered_action = action

        desc = action.property("description")
        if desc:
            title = action.text().replace("&", "").strip()
            template = "<title>{}</title><text>{}</text>".format(title, desc)

            geometry = self.actionGeometry(action)
            target_rect = QtCore.QRect(self.mapToGlobal(geometry.topLeft()), geometry.size())

            icon = action.icon() if not action.icon().isNull() else None
            QFlatTooltipManager.delayed_show(
                text=title, anchor_widget=self, target_rect=target_rect, description=desc, template=template, icon_obj=icon
            )

    def hideEvent(self, event):
        self._last_hovered_action = None
        QFlatTooltipManager.hide()
        QtWidgets.QMenu.hideEvent(self, event)

    def leaveEvent(self, event):
        self._last_hovered_action = None

        QFlatTooltipManager.cancel_timer()
        QtWidgets.QMenu.leaveEvent(self, event)

    def _on_action_triggered(self, action):
        if isinstance(action, QtWidgets.QWidgetAction):
            return


class OpenMenuWidget(MenuWidget):
    def __init__(self, *args, **kwargs):
        MenuWidget.__init__(self, *args, **kwargs)

    def mouseReleaseEvent(self, e):
        action = self.actionAt(e.pos())
        if action and action.isEnabled():
            if action.isCheckable():
                action.setEnabled(False)
                MenuWidget.mouseReleaseEvent(self, e)
                action.setEnabled(True)
                action.trigger()
            elif action.data() == "keep_open":
                action.trigger()
            else:
                MenuWidget.mouseReleaseEvent(self, e)
        else:
            MenuWidget.mouseReleaseEvent(self, e)


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


class QFlowLayout(QtWidgets.QLayout):
    def __init__(self, parent=None, margin=0, Hspacing=-1, Vspacing=-1, alignment=None):
        super().__init__(parent)
        self._item_list = []
        self._Hspacing = Hspacing
        self._Vspacing = Vspacing
        
        # PySide/PyQt cross-compatibility
        self.setContentsMargins(margin, margin, margin, margin)
        
        self.setSpacing(self._Hspacing)
            
        if alignment is not None:
             self.setAlignment(alignment)

    def __del__(self):
        item = self.takeAt(0)
        while item:
            item = self.takeAt(0)

    def addItem(self, item):
        self._item_list.append(item)

    def count(self):
        return len(self._item_list)

    def itemAt(self, index):
        if 0 <= index < len(self._item_list):
            return self._item_list[index]
        return None

    def takeAt(self, index):
        if 0 <= index < len(self._item_list):
            return self._item_list.pop(index)
        return None

    def expandingDirections(self):
        return QtCore.Qt.Orientations(0)

    def hasHeightForWidth(self):
        return True

    def heightForWidth(self, width):
        return self.doLayout(QtCore.QRect(0, 0, width, 0), True)

    def setGeometry(self, rect):
        super().setGeometry(rect)
        self.doLayout(rect, False)

    def sizeHint(self):
        return self.minimumSize()

    def minimumSize(self):
        size = QtCore.QSize()
        for item in self._item_list:
            size = size.expandedTo(item.minimumSize())

        margins = self.contentsMargins()
        size += QtCore.QSize(margins.left() + margins.right(), margins.top() + margins.bottom())
        return size

    def doLayout(self, rect, test_only):
        margins = self.contentsMargins()
        effective_rect = rect.adjusted(+margins.left(), +margins.top(), -margins.right(), -margins.bottom())
        x = effective_rect.x()
        y = effective_rect.y()
        line_height = 0

        lines = []
        current_line = []
        current_line_width = 0

        space_x = self.spacing()
        space_y = self.spacing()
        if space_x == -1:
            space_x = 5
        if space_y == -1:
            space_y = 5

        for item in self._item_list:
            wid = item.widget()
            if wid is not None and wid.isHidden():
                continue

            item_size = item.sizeHint()
            next_x = x + item_size.width() + space_x

            # Check for wrap
            if next_x - space_x > effective_rect.right() and line_height > 0:
                lines.append((current_line, current_line_width, line_height))
                x = effective_rect.x()
                y = y + line_height + space_y
                next_x = x + item_size.width() + space_x
                line_height = 0
                current_line = []
                current_line_width = 0

            current_line.append(item)
            x = next_x
            current_line_width = x - effective_rect.x() - space_x
            line_height = max(line_height, item_size.height())

        if current_line:
            lines.append((current_line, current_line_width, line_height))

        # Now go through the lines and apply alignment
        if not test_only:
            current_y = effective_rect.y()
            try:
                alignment = int(self.alignment())
            except (TypeError, ValueError):
                alignment = 0

            for line_items, line_width, lh in lines:
                if alignment & int(QtCore.Qt.AlignRight):
                    current_x = effective_rect.right() - line_width + 1
                elif alignment & int(QtCore.Qt.AlignHCenter):
                    current_x = effective_rect.x() + (effective_rect.width() - line_width) / 2
                else: # Default is AlignLeft
                    current_x = effective_rect.x()

                for item in line_items:
                    item_size = item.sizeHint()
                    dy = (lh - item_size.height()) / 2
                    item.setGeometry(QtCore.QRect(QtCore.QPoint(int(current_x), int(current_y + dy)), item_size))
                    current_x += item_size.width() + space_x

                current_y += lh + space_y
                
        # Total layout height required
        return y + line_height - rect.y() + margins.bottom()
