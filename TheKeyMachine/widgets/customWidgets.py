from TheKeyMachine.tooltips import QFlatTooltipManager
from .util import DPI
import re

import TheKeyMachine.mods.settingsMod as settings  # type: ignore

try:
    from PySide6 import QtWidgets, QtCore, QtGui
    from shiboken6 import isValid

    PYSIDE = 6
except ImportError:
    from PySide2 import QtWidgets, QtCore, QtGui
    from shiboken2 import isValid

    PYSIDE = 2


try:
    import TheKeyMachine_user_data.preferences.user_preferences as user_preferences  # type: ignore
except ImportError:
    user_preferences = None


"""
TheKeyMachine Custom Widgets
===========================
Centralized repository for UI components used throughout the toolbar.
Includes QFlatToolButton with automated sizing, hover effects (glow), 
and user preference integration.
"""


class HelpSystem:
    """Centralized utility for pushing help text to all Maya help channels."""

    @staticmethod
    def clean(raw):
        if not raw:
            return ""
        # Strip HTML and normalize
        res = re.sub(r"<[^>]*>", "", str(raw))
        return re.sub(r"\s+", " ", res).strip()

    @staticmethod
    def get_desc(raw):
        if not raw:
            return ""
        # Get first line of description
        parts = re.split(r"<br\s*/?>|\r?\n", str(raw), flags=re.IGNORECASE)
        for p in parts:
            clean = HelpSystem.clean(p)
            if clean:
                return clean
        return ""

    @classmethod
    def push(cls, widget_or_action, title="", description=""):
        """Pushes data to StatusTip, ToolTip, and internal properties."""
        c_title = cls.clean(title or widget_or_action.objectName())
        c_desc = cls.get_desc(description)

        status = f"{c_title} - {c_desc}" if (c_title and c_desc) else (c_title or c_desc)

        # 1. Update standard Qt properties (triggers Maya's status bar)
        if hasattr(widget_or_action, "setStatusTip"):
            widget_or_action.setStatusTip(status)

        # 2. Store for our custom TKM floating tooltips
        if hasattr(widget_or_action, "setProperty"):
            widget_or_action.setProperty("tkm_title", title)
            widget_or_action.setProperty("tkm_description", description)
            widget_or_action.setProperty("description", description)  # Legacy support

        # 3. If it's an action, also try to push to its parent menu's status bar
        if isinstance(widget_or_action, QtGui.QAction) and widget_or_action.parent():
            p = widget_or_action.parent()
            if hasattr(p, "setStatusTip"):
                p.setStatusTip(status)


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

        if description or self.title():
            HelpSystem.push(self, self.title(), description)

        self.triggered.connect(self._on_action_triggered)
        self.hovered.connect(self._on_action_hovered)
        self._last_hovered_action = None

    def addAction(self, *args, **kwargs):
        description = kwargs.pop("description", None)
        action = QtWidgets.QMenu.addAction(self, *args, **kwargs)

        # Get the label: skip the icon and parent if provided in args
        label = ""
        for arg in args:
            if isinstance(arg, (str, bytes)):
                label = arg
                break

        HelpSystem.push(action, label, description)
        return action

    def addMenu(self, *args, **kwargs):
        description = kwargs.pop("description", None)
        item = QtWidgets.QMenu.addMenu(self, *args, **kwargs)

        # item can be QMenu or QAction depending on the overload
        action = item.menuAction() if hasattr(item, "menuAction") else item
        label = action.text()

        HelpSystem.push(action, label, description)
        return item

    def _on_action_hovered(self, action):
        if not action or self.actionGeometry(action).isNull():
            return

        if action == self._last_hovered_action and QFlatTooltipManager.is_active():
            return

        QFlatTooltipManager.hide()
        self._last_hovered_action = action

        # Force push to Maya channels
        title = action.property("tkm_title") or action.text()
        desc = action.property("tkm_description") or ""
        HelpSystem.push(action, title, desc)

        # Floating Tooltip
        if QFlatTooltipManager.enabled:
            template = f"<b>{title}</b><br><br>{desc}" if desc else f"<b>{title}</b>"
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
        self.setTearOffEnabled(True)

    def mouseReleaseEvent(self, e):
        action = self.actionAt(e.pos())
        if action and action.isEnabled():
            action.trigger()
            return
        MenuWidget.mouseReleaseEvent(self, e)


class TooltipMixin:
    def setData(self, text="", description="", shortcuts=None, icon=None):
        self._help_data = {"text": text, "description": description, "shortcuts": shortcuts or [], "icon": icon}
        HelpSystem.push(self, text, description)

    def set_tooltip_data(self, **kwargs):
        self._has_tooltip = True
        self.setData(**kwargs)

    def set_tooltip_info(self, title: str, description: str = ""):
        self.set_tooltip_data(text=title, description=description)

    def enterEvent(self, event: QtCore.QEvent):
        # Refresh description and trigger Maya event
        data = getattr(self, "_help_data", {})
        HelpSystem.push(self, data.get("text", ""), data.get("description", ""))

        try:
            super().enterEvent(event)
        except (AttributeError, TypeError):
            pass

        if QFlatTooltipManager.enabled and getattr(self, "_has_tooltip", False):
            if data.get("text") or data.get("description"):
                QFlatTooltipManager.delayed_show(anchor_widget=self, **data)

    def leaveEvent(self, event: QtCore.QEvent):
        QFlatTooltipManager.cancel_timer()
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
    def __init__(self, parent=None, icon=None, text=None, tooltip=None, description=None, shortcuts=None, highlight=False, pressed_color=None):
        super().__init__(parent)
        self.setCursor(QtCore.Qt.PointingHandCursor)
        self.setAutoRaise(True)
        self.pressed_color = pressed_color or "#666666"

        if text:
            self.setText(text)
            self.setToolButtonStyle(QtCore.Qt.ToolButtonTextBesideIcon if icon else QtCore.Qt.ToolButtonTextOnly)

        # Enforce styling: squared corners, no border on hover, background on press
        self.setStyleSheet(f"""
            QToolButton {{
                border: none;
                border-radius: 0px;
                background-color: transparent;
                color: #bfbfbf;
            }}
            QToolButton:hover {{
                border: none;
                background-color: transparent;
                color: #ffffff;
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
    def __init__(self, parent=None, margin=0, Hspacing=-1, Vspacing=-1, alignment=None, **kwargs):
        super().__init__(parent)
        self._item_list = []

        # Handle 'Wspacing' alias from toolbar.py
        self._Hspacing = kwargs.get("Wspacing", Hspacing)
        self._Vspacing = kwargs.get("Hspacing", Vspacing) if "Wspacing" in kwargs else Vspacing

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

    def addSpacing(self, size):
        self.addItem(QtWidgets.QSpacerItem(size, 0, QtWidgets.QSizePolicy.Fixed, QtWidgets.QSizePolicy.Minimum))

    def addStretch(self, stretch=0):
        self.addItem(QtWidgets.QSpacerItem(0, 0, QtWidgets.QSizePolicy.Expanding, QtWidgets.QSizePolicy.Minimum))

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

        space_x = self._Hspacing if self._Hspacing != -1 else 5
        space_y = self._Vspacing if self._Vspacing != -1 else 5

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
                else:  # Default is AlignLeft
                    current_x = effective_rect.x()

                for item in line_items:
                    item_size = item.sizeHint()
                    dy = (lh - item_size.height()) / 2
                    item.setGeometry(QtCore.QRect(QtCore.QPoint(int(current_x), int(current_y + dy)), item_size))
                    current_x += item_size.width() + space_x

                current_y += lh + space_y

        # Total layout height required
        return y + line_height - rect.y() + margins.bottom()


class QFlowContainer(QtWidgets.QWidget):
    """A QWidget that automatically sizes its height to its QFlowLayout.

    Drop-in replacement for a plain QWidget when using QFlowLayout as its
    layout.  Whenever the widget is resized (including the initial show or
    a parent resize after a tool reload) it recomputes ``heightForWidth``
    and pins itself to exactly that height via ``setFixedHeight``.  This
    prevents the "only first row visible" bug that occurs when Maya's
    columnLayout wrapper doesn't propagate Qt's heightForWidth protocol.
    """

    def sizeHint(self):
        return self.minimumSize()

    def minimumSizeHint(self):
        return self.minimumSize()

    def resizeEvent(self, event):
        super().resizeEvent(event)
        self._update_height()

    def _update_height(self):
        lay = self.layout()
        if lay is not None and lay.hasHeightForWidth():
            new_h = lay.heightForWidth(self.width())
            if new_h > 0 and self.height() != new_h:
                self.setFixedHeight(new_h)


# QPainter for the shelf tabBar


class QFlatSectionWidget(QtWidgets.QWidget):
    """
    A container for toolbar sections that provides a hover-activated overlay
    for toggling the visibility of its child widgets.
    """

    def __init__(self, parent=None, spacing=2, hiddeable=True):
        super().__init__(parent)
        self.setLayout(QtWidgets.QHBoxLayout())
        self.layout().setContentsMargins(0, 3, 0, 3)
        self.layout().setSpacing(spacing)
        self._hiddeable = hiddeable

        if self._hiddeable:
            # Overlay button: tiny checkbox in the bottom-left
            self._overlay_btn = QtWidgets.QToolButton(self)
            self._overlay_btn.setFixedSize(8, 8)
            self._overlay_btn.setCursor(QtCore.Qt.PointingHandCursor)
            self._overlay_btn.setVisible(False)
            self._overlay_btn.setToolTip("Pin hidden tools for this Section")
            self._overlay_btn.setStyleSheet("""
                QToolButton {
                    border: none;
                    background-color: #333333;
                }
                QToolButton:hover {
                    background-color: #383838;
                }
            """)

            self._overlay_btn.clicked.connect(self._show_menu)
            # Menu for toggling children
            self._menu = OpenMenuWidget(self)

        self._widgets = {}  # key -> widget mapping
        self._actions = {}  # key -> QAction mapping

    def addWidget(self, widget, label, key, default_visible=True, description=None):
        """Add a widget to the section with a toggle key."""
        self.layout().addWidget(widget)
        self._widgets[key] = widget

        if self._hiddeable:
            # Create checkable action for the menu
            action = self._menu.addAction(label, description=description)
            action.setCheckable(True)
            action.setChecked(default_visible)

            # Connect using a closure-like method to ensure 'key' is frozen at addition time
            action.triggered.connect(self._make_toggle_handler(key))
            widget.setVisible(default_visible)

            self._actions[key] = action
        return widget

    def toggle_widget(self, key, visible, save_setting=True):
        if self._hiddeable:
            """Toggle widget visibility and update menu/settings if needed."""
            widget = self._widgets.get(key)
            if widget and isValid(widget):
                widget.setHidden(not visible)

            action = self._actions.get(key)
            if action and isValid(action):
                action.blockSignals(True)
                action.setChecked(visible)
                action.blockSignals(False)

            if save_setting:
                settings.set_setting(f"pin_{key}", visible)

            self._menu.update()

    def addSeparator(self):
        """Add a separator to the customization menu."""
        self._menu.addSeparator()

    def add_final_actions(self, default_keys):
        """Add Pin Defaults and Pin All at the bottom."""
        self._menu.addSeparator()

        # Use default values for the signal's 'checked' state to prevent missing argument errors.
        pin_defaults_action = self._menu.addAction("Pin Defaults")
        pin_defaults_action.triggered.connect(lambda checked=False, d=default_keys: self.pin_defaults(d))

        pin_all_action = self._menu.addAction("Pin All")
        pin_all_action.triggered.connect(lambda checked=False: self.pin_all())

    def pin_defaults(self, default_keys):
        for key in self._widgets:
            self.toggle_widget(key, key in default_keys)
        self._refresh_layout()

    def pin_all(self):
        for key in self._widgets:
            self.toggle_widget(key, True)
        self._refresh_layout()

    def _make_toggle_handler(self, key):
        """Creates a handler function that captures 'key'."""

        def handler(checked):
            self.toggle_widget(key, checked)
            self._refresh_layout()

        return handler

    def _refresh_layout(self):
        """Trigger a height recalculation."""
        QtCore.QTimer.singleShot(100, self.parent()._update_height)

    def _show_menu(self):
        if self._hiddeable:
            self._menu.exec_(QtGui.QCursor.pos())

    def enterEvent(self, event):
        if self._hiddeable:
            self._overlay_btn.setVisible(True)
            self._overlay_btn.raise_()
            pos = QtCore.QPoint(self.width() - self._overlay_btn.width(), self.height() - self._overlay_btn.height())
            self._overlay_btn.move(pos)
        super().enterEvent(event)

    def leaveEvent(self, event):
        if self._hiddeable:
            self._overlay_btn.setVisible(False)
        super().leaveEvent(event)


class QFlatShelfPainter(QtWidgets.QWidget):
    def __init__(self, parent=None):
        QtWidgets.QWidget.__init__(self, parent)
        self.tabbar_width = DPI(16)
        self.line_thickness = DPI(1)
        self.line_color = QtGui.QColor(130, 130, 130)
        self.margin = DPI(4)
        self.center = DPI(5)
        self.offset = DPI(1.5)

    def paintEvent(self, event):
        self.setAttribute(QtCore.Qt.WA_TransparentForMouseEvents)

        color = self.palette().color(self.backgroundRole())
        painter = QtGui.QPainter(self)
        painter.setPen(QtGui.QPen(color, self.tabbar_width))
        painter.drawLine(self.tabbar_width // 2, 0, self.tabbar_width // 2, self.height())

        pen = QtGui.QPen(self.line_color)
        pen.setWidth(1)  # Line width of 1 pixel
        pen.setStyle(QtCore.Qt.CustomDashLine)  # Enable custom dash pattern
        pen.setDashPattern([0.01, DPI(3)])  # 1 pixel dot, 1 pixel space
        painter.setPen(pen)

        painter.drawLine(
            QtCore.QPointF(self.center - self.offset, self.margin / 3),
            QtCore.QPointF(self.center - self.offset, self.height() - self.margin),
        )
        painter.drawLine(
            QtCore.QPointF(self.center + self.offset, self.margin / 3),
            QtCore.QPointF(self.center + self.offset, self.height() - self.margin),
        )

    def resizeEvent(self, event):
        self.update()

    def updateDrawingParameters(
        self,
        tabbar_width=None,
        line_thickness=None,
        line_color=None,
        margin=None,
        center=None,
        offset=None,
    ):
        """Update drawing parameters and refresh the widget."""
        if tabbar_width is not None:
            self.tabbar_width = tabbar_width.width()
        if line_thickness is not None:
            self.line_thickness = line_thickness
        if line_color is not None:
            self.line_color = line_color
        if margin is not None:
            self.margin = margin
        if center is not None:
            self.center = center
        if offset is not None:
            self.offset = offset
        self.update()
