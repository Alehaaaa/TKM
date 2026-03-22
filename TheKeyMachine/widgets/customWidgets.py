from TheKeyMachine.tooltips import QFlatTooltipManager
from .util import DPI
import re
from functools import partial

import TheKeyMachine.mods.settingsMod as settings  # type: ignore
import TheKeyMachine.mods.mediaMod as media  # type: ignore

try:
    import TheKeyMachine_user_data.preferences.user_preferences as user_preferences  # type: ignore
except ImportError:
    user_preferences = None

try:
    from PySide6 import QtWidgets, QtCore, QtGui
    from shiboken6 import isValid

    QAction = QtGui.QAction
except ImportError:
    from PySide2 import QtWidgets, QtCore, QtGui
    from shiboken2 import isValid

    QAction = QtWidgets.QAction


"""
TheKeyMachine Custom Widgets
===========================
Centralized repository for UI components used throughout the toolbar.
Includes QFlatToolButton with automated sizing, hover effects (glow), 
and user preference integration.
"""


# Pre-compiled regular expressions for performance
RE_HTML_TAGS = re.compile(r"<[^>]*>")
RE_WHITESPACE = re.compile(r"\s+")
RE_BR_SPLIT = re.compile(r"<br\s*/?>", re.IGNORECASE)
RE_NEWLINE_SPLIT = re.compile(r"<br\s*/?>|\r?\n", re.IGNORECASE)
RE_TKM_TT_SPLIT = re.compile(r"(?:<br\s*/?>\s*){2,}", re.IGNORECASE)
RE_HELP_SPLIT = re.compile(r"(\.[\s\r\n]|<br\s*/?>|\r?\n)", re.IGNORECASE)


class HelpSystem:
    """Centralized utility for pushing help text to all Maya help channels."""

    @staticmethod
    def clean(raw):
        if not raw:
            return ""
        # 1. Replace all HTML tags with a space to avoid joining words
        res = RE_HTML_TAGS.sub(" ", str(raw))
        # 2. Normalize whitespace and strip
        return RE_WHITESPACE.sub(" ", res).strip()

    @staticmethod
    def get_desc(raw):
        if not raw:
            return ""
        # Get first line or first sentence of description
        parts = RE_HELP_SPLIT.split(str(raw), maxsplit=1)
        if parts:
            # Reconstruct the sentence if split by period
            res = parts[0]
            if len(parts) > 1 and parts[1].startswith("."):
                res += "."

            clean = HelpSystem.clean(res)
            if clean:
                return clean
        return ""

    @classmethod
    def push(cls, widget_or_action, title="", description=""):
        """Pushes data to StatusTip, ToolTip, and internal properties."""
        raw_title = title or ""
        raw_desc = description or ""

        # If title contains TKM's double-break format, split it
        if not raw_desc and "<br" in raw_title.lower():
            parts = RE_TKM_TT_SPLIT.split(raw_title, maxsplit=1)
            if len(parts) > 1:
                raw_title, raw_desc = parts
            else:
                parts = RE_NEWLINE_SPLIT.split(raw_title, maxsplit=1)
                if len(parts) > 1:
                    raw_title, raw_desc = parts

        c_title = cls.clean(raw_title)
        if not c_title and hasattr(widget_or_action, "objectName"):
            c_title = cls.clean(widget_or_action.objectName())

        c_desc = cls.get_desc(raw_desc)
        # Avoid redundancy: if description starts with/is the title, strip it
        if c_title and c_desc:
            if c_title.lower() == c_desc.lower():
                c_desc = ""
            elif c_desc.lower().startswith(c_title.lower()):
                pattern = re.compile(re.escape(c_title), re.IGNORECASE)
                c_desc = pattern.sub("", c_desc, count=1).strip()
                # Restore sentence case safely
                if c_desc:
                    c_desc = c_desc[0].upper() + c_desc[1:]

        status = f"{c_title} - {c_desc}" if (c_title and c_desc) else (c_title or c_desc)

        if hasattr(widget_or_action, "setStatusTip"):
            widget_or_action.setStatusTip(status)

        if hasattr(widget_or_action, "setProperty"):
            widget_or_action.setProperty("tkm_title", raw_title)
            widget_or_action.setProperty("tkm_description", raw_desc)
            widget_or_action.setProperty("description", raw_desc)

        # 3. If it's an action, also try to push to its parent menu's status bar
        if isinstance(widget_or_action, QAction) and widget_or_action.parent():
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


class LogoAction(QtWidgets.QWidgetAction):
    def __init__(self, parent):
        super().__init__(parent)
        self._container = QtWidgets.QWidget()
        layout = QtWidgets.QVBoxLayout(self._container)
        layout.setContentsMargins(0, 10, 0, 10)
        layout.setSpacing(0)

        logo_pix = QtGui.QPixmap(media.getImage("TheKeyMachine_logo_small.png"))
        if not logo_pix.isNull():
            self.logo_label = QtWidgets.QLabel()
            self.logo_label.setPixmap(logo_pix.scaledToHeight(DPI(60), QtCore.Qt.SmoothTransformation))
            self.logo_label.setAlignment(QtCore.Qt.AlignCenter)
            layout.addWidget(self.logo_label)

        self.setDefaultWidget(self._container)
        self._container.mouseReleaseEvent = self._on_clicked

    def _on_clicked(self, event):
        import webbrowser

        webbrowser.open("https://github.com/Alehaaaa/TKM")
        if self.parent() and hasattr(self.parent(), "hide"):
            self.parent().hide()


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
        self.setTearOffEnabled(True)

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
        tooltip_template = kwargs.pop("tooltip_template", kwargs.pop("template", kwargs.pop("tooltip", None)))
        callback = kwargs.pop("callback", None)
        label_override = kwargs.pop("label", None)

        res = QtWidgets.QMenu.addAction(self, *args, **kwargs)
        # Use QAction if it was passed directly as the first arg, else the result of addAction
        action = args[0] if (len(args) > 0 and isinstance(args[0], QAction)) else res

        if callback:
            action.triggered.connect(callback)

        # Determine the display label and help title from positional args if no override
        label = ""
        for arg in args:
            if isinstance(arg, (str, bytes)):
                label = arg
                break

        # Push documentation (use label_override, tooltip_template or label as help source)
        HelpSystem.push(action, label_override or tooltip_template or label or action.text(), description)
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
            # Reconstruct the full HTML template from the split properties
            # Note: we wrap the title in bold if it's plain text to ensure QFlatTooltip finds the header
            display_title = title if ("<" in title or ">" in title) else f"<b>{title}</b>"
            tooltip_template = f"{display_title}<br><br>{desc}" if desc else display_title

            geometry = self.actionGeometry(action)
            target_rect = QtCore.QRect(self.mapToGlobal(geometry.topLeft()), geometry.size())
            icon = action.icon() if not action.icon().isNull() else None
            QFlatTooltipManager.delayed_show(
                text=title, anchor_widget=self, target_rect=target_rect, description=desc, tooltip_template=tooltip_template, icon_obj=icon
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
    def setData(self, text="", description="", shortcuts=None, icon=None, tooltip_template=None):
        # Automatically pick up the widget's icon if not provided
        if not icon and hasattr(self, "_icon_path"):
            icon = self._icon_path

        self._help_data = {
            "text": text,
            "description": description,
            "shortcuts": shortcuts or [],
            "icon": icon,
            "tooltip_template": tooltip_template,
        }
        HelpSystem.push(self, tooltip_template or text, description)

    def get_help_data(self):
        return getattr(self, "_help_data", {})

    def setToolTipData(self, **kwargs):
        self._has_tooltip = True
        self.setData(**kwargs)

    def setTooltipInfo(self, title: str, description: str = ""):
        self.setToolTipData(text=title, description=description)

    def enterEvent(self, event: QtCore.QEvent):
        # Refresh description and trigger Maya event
        data = getattr(self, "_help_data", {})
        HelpSystem.push(self, data.get("tooltip_template") or data.get("text", ""), data.get("description", ""))

        try:
            super().enterEvent(event)
        except (AttributeError, TypeError):
            pass

        if QFlatTooltipManager.enabled and getattr(self, "_has_tooltip", False):
            if data.get("text") or data.get("description") or data.get("tooltip_template"):
                # Pass the template directly to the tooltip manager
                QFlatTooltipManager.delayed_show(anchor_widget=self, **data)

    def leaveEvent(self, event: QtCore.QEvent):
        QFlatTooltipManager.cancel_timer()
        try:
            super().leaveEvent(event)
        except (AttributeError, TypeError):
            pass


class QFlatButton(QtWidgets.QPushButton):
    """A customizable, flat-styled button for the bottom bar."""

    STYLE_SHEET = """
        QtWidgets.QPushButton {
            color: %s;
            background-color: %s;
            border-radius: %spx;
            padding: %spx %spx;
            font-weight: %s;
            font-size: %spx;
        }
        QtWidgets.QPushButton:hover {
            background-color: %s;
        }
        QtWidgets.QPushButton:pressed {
            background-color: %s;
        }
    """

    DEFAULT_COLOR = "#ffffff"
    DEFAULT_BACKGROUND = "#5D5D5D"
    DEFAULT_HOVER_BACKGROUND = "#707070"
    DEFAULT_PRESSED_BACKGROUND = "#252525"

    HIGHLIGHT_COLOR = "#282828"
    HIGHLIGHT_BACKGROUND = "#bdbdbd"
    HIGHLIGHT_HOVER_BACKGROUND = "#cfcfcf"
    HIGHLIGHT_PRESSED_BACKGROUND = "#707070"

    DEFAULT_FONT_SIZE = DPI(12)
    HIGHLIGHT_FONT_SIZE = DPI(15)

    BUTTON_BORDER_RADIUS = DPI(9)

    def __init__(
        self,
        text,
        color=DEFAULT_COLOR,
        background=DEFAULT_BACKGROUND,
        icon_path=None,
        border=BUTTON_BORDER_RADIUS,
        highlight=False,
        parent=None,
    ):
        QtWidgets.QPushButton.__init__(self, text, parent)
        self.setFlat(True)
        self.setCursor(QtCore.Qt.PointingHandCursor)
        self.setSizePolicy(QtWidgets.QSizePolicy.Expanding, QtWidgets.QSizePolicy.Fixed)
        self.setFixedHeight(DPI(34))

        # Consistent Icon Size
        self.setIconSize(QtCore.QSize(DPI(19), DPI(19)))
        if icon_path:
            QFlatHoverableIcon.apply(self, icon_path, highlight=highlight)

        v_padding = 2  # Tight padding since height is fixed

        if highlight:
            color = self.HIGHLIGHT_COLOR
            background = self.HIGHLIGHT_BACKGROUND
            hover_background = self.HIGHLIGHT_HOVER_BACKGROUND
            pressed_background = self.HIGHLIGHT_PRESSED_BACKGROUND
            font_size = self.HIGHLIGHT_FONT_SIZE
            weight = "bold"
        elif background != self.DEFAULT_BACKGROUND:
            try:
                base_background = int(background.lstrip("#"), 16)
                r, g, b = (
                    (base_background >> 16) & 0xFF,
                    (base_background >> 8) & 0xFF,
                    base_background & 0xFF,
                )
            except Exception:
                r, g, b = 93, 93, 93
            hover_background = "#%02x%02x%02x" % (min(r + 10, 255), min(g + 10, 255), min(b + 10, 255))
            pressed_background = "#%02x%02x%02x" % (max(r - 10, 0), max(g - 10, 0), max(b - 10, 0))
            font_size = self.DEFAULT_FONT_SIZE
            weight = "normal"
        else:
            hover_background = self.DEFAULT_HOVER_BACKGROUND
            pressed_background = self.DEFAULT_PRESSED_BACKGROUND
            font_size = self.DEFAULT_FONT_SIZE
            weight = "normal"

        actual_border = min(int(border), int(DPI(34)) // 2)

        self.setStyleSheet(
            self.STYLE_SHEET
            % (
                color,
                background,
                actual_border,
                int(DPI(v_padding)),
                int(DPI(12)),
                weight,
                int(font_size),
                hover_background,
                pressed_background,
            )
        )


class QFlatBottomBar(QtWidgets.QFrame):
    """
    A container widget for arranging QFlatButtons horizontally.
    """

    def __init__(self, buttons=[], margins=8, spacing=6, parent=None):
        QtWidgets.QFrame.__init__(self, parent)
        self.setSizePolicy(QtWidgets.QSizePolicy.Expanding, QtWidgets.QSizePolicy.Fixed)

        layout = QtWidgets.QHBoxLayout(self)
        layout.setContentsMargins(DPI(margins), DPI(margins), DPI(margins), DPI(margins))
        layout.setSpacing(DPI(spacing))

        for button in buttons:
            layout.addWidget(button)


class QFlatSpinBox(QtWidgets.QSpinBox):
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.setFixedSize(50, 24)
        self.setMinimum(1)
        self.setMaximum(99999)
        self.setValue(1)
        self.setStyleSheet("border: 0px;border-radius: 5px;")
        self.setButtonSymbols(QtWidgets.QAbstractSpinBox.NoButtons)
        self.setContextMenuPolicy(QtCore.Qt.CustomContextMenu)
        self.customContextMenuRequested.connect(self._show_context_menu)

    def _show_context_menu(self, pos):
        menu = MenuWidget(self)
        for val in [1, 2, 3, 4, 5]:
            menu.addAction(
                str(val),
                label="Set Nudge Value: " + str(val),
                description="Sets the number of frames to nudge or inbetween.",
                callback=partial(self.setValue, val),
            )
        menu.addSeparator()
        for val in [10, 20, 50, 100]:
            menu.addAction(
                str(val),
                label="Set Nudge Value: " + str(val),
                description="Sets the number of frames to nudge or inbetween.",
                callback=partial(self.setValue, val),
            )
        menu.exec_(self.mapToGlobal(pos))

    def enterEvent(self, event: QtCore.QEvent):
        self.setButtonSymbols(QtWidgets.QAbstractSpinBox.UpDownArrows)
        super().enterEvent(event)

    def leaveEvent(self, event: QtCore.QEvent):
        self.setButtonSymbols(QtWidgets.QAbstractSpinBox.NoButtons)
        super().leaveEvent(event)

    def on_added_to_section(self, section, key):
        """Automatically called when the widget is added to a QFlatSectionWidget."""
        self._persistence_key = f"spinbox_{key}"
        saved_val = settings.get_setting(self._persistence_key, self.value())
        self.setValue(saved_val)
        self.valueChanged.connect(self._save_value)

    def _save_value(self, val):
        if hasattr(self, "_persistence_key"):
            settings.set_setting(self._persistence_key, val)


class QFlatToolButton(TooltipMixin, QtWidgets.QToolButton):
    def __init__(
        self,
        parent=None,
        icon=None,
        text=None,
        tooltip_template=None,
        description=None,
        shortcuts=None,
        highlight=False,
        pressed_color=None,
    ):
        super().__init__(parent)
        self.setAutoRaise(True)
        self.pressed_color = pressed_color or "#666666"

        if text:
            self.setText(text)
            self.setToolButtonStyle(QtCore.Qt.ToolButtonIconOnly if icon else QtCore.Qt.ToolButtonTextOnly)
        else:
            self.setToolButtonStyle(QtCore.Qt.ToolButtonIconOnly)

        # Enforce styling: squared corners, no border on hover, background on press
        self.setStyleSheet(f"""
            QToolButton {{
                border: none;
                border-radius: 0px;
                background-color: transparent;
                color: #bfbfbf;
                font-size: 11px;
                font-weight: bold;

            }}
            QToolButton:hover {{
                border: none;
                background-color: transparent;
                color: #ffffff;
            }}
            QToolButton:pressed {{
                background-color: {self.pressed_color};
            }}
            QToolButton:checked {{
                background-color: #444444;
                color: #ffffff;
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
        self._highlight = highlight
        if icon:
            self.setIcon(icon)
        self.setToolTipData(
            text=tooltip_template or text, description=description, shortcuts=shortcuts, tooltip_template=tooltip_template, icon=icon
        )

    def setIcon(self, icon):
        """Mixin of QToolButton.setIcon that also handles TKM path tracking and hover effects."""
        if isinstance(icon, (str, bytes)):
            self._icon_path = str(icon)
            QFlatHoverableIcon.apply(self, self._icon_path, highlight=self._highlight)
            # Update tooltip icon as well
            data = getattr(self, "_help_data", {})
            self.setToolTipData(icon=self._icon_path, **data)
        elif icon:
            super().setIcon(icon)


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

        self._widgets = {}  # slot_key -> widget mapping
        self._menu_metadata = []  # for non-slider sections (toolbar buttons etc.)
        self._default_keys = []
        self._active_menu = None
        self._all_modes = []  # Full ordered mode list (SliderMode objects + "separator")
        self._mode_to_slot = {}  # mode_key -> slot_key (live, authoritative mapping)

        # Tool-group action pinning support
        # _tool_groups: widget_key -> {label, icon_path, menu_factory, actions: [...]}
        self._tool_groups = {}
        # _pinned_action_buttons: action_key -> QFlatToolButton (live instances)
        self._pinned_action_buttons = {}

        if self._hiddeable:
            # Overlay button: tiny checkbox in the bottom-left
            self._overlay_btn = QtWidgets.QToolButton(self)
            self._overlay_btn.setFixedSize(8, 8)
            self._overlay_btn.setVisible(False)
            HelpSystem.push(self._overlay_btn, "Section Config", "Manage which tools are pinned for quick access.")

            # Ensure the tiny button pushes its help to Maya on hover
            def _push_help(event, btn=self._overlay_btn):
                HelpSystem.push(btn, btn.property("tkm_title"), btn.property("tkm_description"))
                return QtWidgets.QToolButton.enterEvent(btn, event)

            self._overlay_btn.enterEvent = _push_help
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

    def addWidget(self, widget, label, key, default_visible=True, description=None, tooltip_template=None):
        """Add a widget to the section with a toggle key."""
        # Auto-extract help metadata from widget if not provided
        if (not tooltip_template or not description) and hasattr(widget, "get_help_data"):
            data = widget.get_help_data()
            tooltip_template = tooltip_template or data.get("tooltip_template") or data.get("text")
            description = description or data.get("description")

        self.layout().addWidget(widget)
        self._widgets[key] = widget

        # Propagate section context to widget
        from TheKeyMachine.widgets.util import is_valid_widget

        if is_valid_widget(widget) and hasattr(widget, "on_added_to_section"):
            widget.on_added_to_section(self, key)

        # If the widget is a mode-aware slider, restore its saved mode assignment
        if is_valid_widget(widget) and hasattr(widget, "_current_mode"):
            cm = getattr(widget, "_current_mode", None)
            if cm:
                saved_mode_key = settings.get_setting(f"slider_mode_{key}", cm.key)
                if saved_mode_key != cm.key and hasattr(widget, "setCurrentMode"):
                    widget.setCurrentMode(saved_mode_key)
                # Register current mode in the section's live map
                current_cm = getattr(widget, "_current_mode", None)
                if current_cm:
                    self._mode_to_slot[current_cm.key] = key

        if self._hiddeable:
            self._menu_metadata.append(
                {
                    "type": "widget",
                    "key": key,
                    "label": label,
                    "description": description,
                    "tooltip_template": tooltip_template,
                    "default": default_visible,
                }
            )

            # Load stored visibility or use default
            visible = settings.get_setting(f"pin_{key}", default_visible)
            widget.setVisible(visible)

        # Push documentation to the widget (syncs Maya Status Bar and TKM tooltips)
        if hasattr(widget, "setToolTipData"):
            # If no description/template provided to addWidget, try to preserve widget's own data
            d = description
            tt = tooltip_template
            if not d and not tt and hasattr(widget, "_help_data"):
                existing = widget._help_data
                d = existing.get("description")
                tt = existing.get("tooltip_template")

            widget.setToolTipData(text=label, description=d or "", tooltip_template=tt)
        else:
            HelpSystem.push(widget, tooltip_template or label, description or "")

        return widget

    def addWidgetGroup(self, widgets_list, default_visible=True):
        """
        All-in-one: adds a widget to the section AND builds its right-click menu
        from a descriptor list, enabling individual action pinning.

        Parameters
        ----------
        widget : QWidget
            The primary button/widget.
        label : str
            Display label in the section's pin menu.
        key : str
            Unique slot key.
        widgets : list
            List of action descriptors or the string ``"separator"``.
            Each descriptor dict may contain:
              key, label, icon_path, callback,
              checkable (bool), is_checked_fn (callable), tooltip, description.
        default_visible : bool
        description : str
        """
        default_items = [i for i in widgets_list if isinstance(i, dict) and i.get("default")]
        if not default_items:
            default_items = [widgets_list[0]] if widgets_list else []

        group_widgets = []
        for default_item in default_items:
            widget = QFlatToolButton(
                icon=default_item.get("icon_path"),
                text=default_item.get("text"),
                tooltip_template=default_item.get("tooltip_template") or default_item.get("tooltip") or default_item.get("label"),
                description=default_item.get("description") or "",
            )
            label = default_item.get("label", "Unknown")
            key = default_item.get("key", "unknown")

            if "callback" in default_item:
                widget.clicked.connect(default_item["callback"])

            # 1. Register the main widget in the section
            self.addWidget(
                widget,
                label,
                key,
                default_visible=default_visible,
                description=default_item.get("description"),
                tooltip_template=default_item.get("tooltip_template") or default_item.get("tooltip") or label,
            )
            group_widgets.append((key, widget))

        # 2. Resolve the group properties from the first default tool
        first_item = default_items[0] if default_items else {}
        group_label = first_item.get("label", "Group")
        group_icon_p = first_item.get("icon_path") or ""

        # 3. Build QMenu + pinnable_actions from the descriptor list
        pinnable_actions = []
        for item in widgets_list:
            if item == "separator":
                continue
            if item.get("pinnable") is not False:
                pinnable_actions.append(
                    {
                        "key": item["key"],
                        "label": item.get("label", ""),
                        "icon_path": item.get("icon_path"),
                        "callback": item.get("callback"),
                        "checkable": item.get("checkable", False),
                        "is_checked_fn": item.get("is_checked_fn"),
                        "tooltip_template": item.get("tooltip_template") or item.get("tooltip"),
                        "description": item.get("description"),
                    }
                )

        # 3. Build QMenu from the descriptor list (factory will manage visibility)
        def menu_factory(section=self, source_widget=None, widgets=widgets_list, group_pin_actions=pinnable_actions):
            menu = MenuWidget(source_widget)
            menu.setTearOffEnabled(True)

            source_key = None
            if source_widget and isValid(source_widget):
                for k, w in section._widgets.items():
                    if w == source_widget:
                        source_key = k
                        break

            checkable_sync_pairs = []
            for item in widgets:
                if item == "separator":
                    menu.addSeparator()
                    continue

                if item.get("key") == source_key:
                    continue
                act_icon_p = item.get("icon_path") or ""
                cb = item.get("callback")
                checkable = item.get("checkable", False)
                is_checked_f = item.get("is_checked_fn")

                # Use raw label for display, but full tooltip for documentation
                display_label = item.get("label", "")
                full_tooltip = item.get("tooltip_template") or item.get("tooltip") or display_label
                full_desc = item.get("description") or ""

                if checkable:
                    action = menu.addAction(QtGui.QIcon(act_icon_p), display_label, template=full_tooltip, description=full_desc)
                    action.setCheckable(True)
                    if is_checked_f:
                        try:
                            action.setChecked(is_checked_f())
                        except Exception:
                            pass
                        checkable_sync_pairs.append((action, is_checked_f))
                    if cb:
                        action.triggered.connect(cb)
                else:
                    if cb:
                        menu.addAction(QtGui.QIcon(act_icon_p), display_label, cb, tooltip_template=full_tooltip, description=full_desc)
                    else:
                        menu.addAction(QtGui.QIcon(act_icon_p), display_label, tooltip_template=full_tooltip, description=full_desc)

            if checkable_sync_pairs:

                def _sync(pairs=checkable_sync_pairs):
                    for act, fn in pairs:
                        if isValid(act):
                            try:
                                act.setChecked(fn())
                            except Exception:
                                pass

                menu.aboutToShow.connect(_sync)
            return menu

        # 4. Register group: wires right-click + tear-off on the parent widget(s)
        self.register_action_group(
            [k for k, w in group_widgets],
            group_label,
            group_icon_p,
            pinnable_actions,
            menu_factory=menu_factory,
        )

        return group_widgets[0][1] if group_widgets else None

    def register_action_group(self, widget_keys, group_label, group_icon_path, pinnable_actions, menu_factory=None):
        """
        Register a tool group so its sub-actions can be pinned as standalone buttons.

        Parameters
        ----------
        widget_keys : str or list of str
            The key(s) used when the parent button(s) were added via addWidget.
        group_label : str
            Display label for the group (e.g. "Pointer").
        group_icon_path : str
            Path to the group's main icon (used as fallback for actions).
        pinnable_actions : list of dict
            Each dict must contain:
                key         - unique string key for this action (scoped to section)
                label       - display label
                icon_path   - path to icon (or None)
                callback    - callable to invoke on click
                checkable   - bool (optional, default False)
                is_checked_fn - callable() -> bool (optional, for checkable items)
                tooltip     - str (optional)
                description - str (optional)
        menu_factory : callable() -> QMenu (optional)
            Returns the live right-click menu shared by all pinned buttons in this group.
        """
        keys_list = [widget_keys] if isinstance(widget_keys, str) else widget_keys

        for w_key in keys_list:
            self._tool_groups[w_key] = {
                "label": group_label,
                "icon_path": group_icon_path,
                "menu_factory": menu_factory,
                "actions": pinnable_actions,
            }

            # Auto-wire right-click on the parent widget + enable tear-off
            if menu_factory:
                widget = self._widgets.get(w_key)
                if widget and isValid(widget):
                    # Enable tear-off once on the live menu object
                    try:
                        m = menu_factory()
                        if m and isValid(m):
                            m.setTearOffEnabled(True)
                    except Exception:
                        pass

                    widget.setContextMenuPolicy(QtCore.Qt.CustomContextMenu)

                    def _ctx(pos, mf=menu_factory, w=widget):
                        try:
                            m = mf(source_widget=w)
                            if m and isValid(m):
                                m.exec_(w.mapToGlobal(pos))
                        except Exception:
                            pass

                    widget.customContextMenuRequested.connect(_ctx)

        # Restore any previously pinned sub-actions on load
        if keys_list:
            group_key = keys_list[0]
            for act_info in pinnable_actions:
                act_key = act_info["key"]
                if settings.get_setting(f"pin_action_{act_key}", False):
                    self._create_pinned_action_button(group_key, act_info)

    def _create_pinned_action_button(self, group_key, act_info):
        """Create and insert a pinned sub-action button into the section layout."""
        act_key = act_info["key"]
        # If already alive, just make sure it is visible
        existing = self._pinned_action_buttons.get(act_key)
        if existing and isValid(existing):
            existing.setVisible(True)
            return existing

        group_info = self._tool_groups.get(group_key, {})
        icon_path = act_info.get("icon_path") or group_info.get("icon_path") or ""
        tooltip_template = act_info.get("tooltip_template") or act_info.get("tooltip") or act_info.get("label", "")
        description = act_info.get("description", "")
        callback = act_info.get("callback")
        checkable = act_info.get("checkable", False)
        is_checked_fn = act_info.get("is_checked_fn")

        btn = QFlatToolButton(icon=icon_path or None, tooltip_template=tooltip_template, description=description)
        btn.setCheckable(checkable)
        if checkable and is_checked_fn:
            try:
                btn.setChecked(is_checked_fn())
            except Exception:
                pass

        if callback:
            if checkable:

                def _checked_cb(checked, cb=callback, b=btn, fn=is_checked_fn):
                    cb(checked)
                    if fn and isValid(b):
                        try:
                            b.setChecked(fn())
                        except Exception:
                            pass

                btn.clicked.connect(_checked_cb)
            else:
                btn.clicked.connect(lambda *_: callback())

        # Right-click: show the group's shared context menu
        menu_factory = group_info.get("menu_factory")
        if menu_factory:
            btn.setContextMenuPolicy(QtCore.Qt.CustomContextMenu)

            def _show_group_menu(pos, mf=menu_factory, b=btn):
                try:
                    m = mf()
                    if m and isValid(m):
                        m.exec_(b.mapToGlobal(pos))
                except Exception:
                    pass

            btn.customContextMenuRequested.connect(_show_group_menu)

        # Tag this button for later identification
        btn.setProperty("tkm_pinned_action_key", act_key)
        btn.setProperty("tkm_group_key", group_key)

        # Insert into layout right after the group's parent widget (and any existing siblings)
        layout = self.layout()
        group_widget = self._widgets.get(group_key)
        insert_index = layout.count()
        if group_widget and isValid(group_widget):
            for i in range(layout.count()):
                item = layout.itemAt(i)
                if item and item.widget() is group_widget:
                    insert_index = i + 1
                    # Skip over already-inserted siblings for the same group
                    while insert_index < layout.count():
                        sib_item = layout.itemAt(insert_index)
                        sib_w = sib_item.widget() if sib_item else None
                        if sib_w and sib_w.property("tkm_group_key") == group_key:
                            insert_index += 1
                        else:
                            break
                    break

        layout.insertWidget(insert_index, btn)
        self._pinned_action_buttons[act_key] = btn
        self._refresh_layout()
        return btn

    def _remove_pinned_action_button(self, act_key):
        """Remove a pinned sub-action button from the section layout."""
        btn = self._pinned_action_buttons.pop(act_key, None)
        if btn and isValid(btn):
            self.layout().removeWidget(btn)
            btn.setParent(None)
            btn.deleteLater()
        self._refresh_layout()

    def toggle_widget(self, key, visible, save_setting=True):
        """Toggle widget visibility and update menu/settings if needed."""
        widget = self._widgets.get(key)
        if widget and isValid(widget):
            widget.setVisible(visible)

        if save_setting:
            settings.set_setting(f"pin_{key}", visible)

        # Update action in active menu (keyed by mode_key for mode-driven sections)
        if self._active_menu and isValid(self._active_menu):
            # Try to look up by slot key or by current mode key of that widget
            widget = self._widgets.get(key)
            current_cm = getattr(widget, "_current_mode", None) if widget else None
            action_key = current_cm.key if current_cm else key
            action = getattr(self._active_menu, "_tkm_actions", {}).get(action_key)
            if action and isValid(action):
                action.blockSignals(True)
                action.setChecked(visible)
                action.blockSignals(False)

    def addSeparator(self):
        """Add a separator to the customization menu."""
        if self._hiddeable:
            self._menu_metadata.append({"type": "separator"})

    def add_final_actions(self, default_keys):
        """Store default keys and extract the full mode list from registered sliders."""
        self._default_keys = default_keys
        # Extract the full ordered mode list from the first slider that has one
        for w in self._widgets.values():
            if isValid(w) and hasattr(w, "_modes") and w._modes:
                self._all_modes = w._modes
                break

    def notify_mode_changed(self, widget, old_key, new_key):
        """Called by a slider when its mode changes. Updates the authoritative mode map."""
        slot_key = next((k for k, v in self._widgets.items() if v is widget), None)
        if not slot_key:
            return
        if old_key:
            self._mode_to_slot.pop(old_key, None)
        if new_key:
            self._mode_to_slot[new_key] = slot_key
            settings.set_setting(f"slider_mode_{slot_key}", new_key)

    def _set_visible_modes(self, desired_mode_keys):
        """
        Show exactly the given modes, reassigning sliders from the pool as needed.
        This is the single source of truth for all pin operations.
        """
        from TheKeyMachine.widgets.util import is_valid_widget

        # Pool: only mode-aware sliders
        pool = {slot: w for slot, w in self._widgets.items() if is_valid_widget(w) and hasattr(w, "_current_mode")}

        # which desired modes are already covered by a slider?
        covered = {cm.key: slot for slot, w in pool.items() if (cm := getattr(w, "_current_mode", None)) and cm.key in desired_mode_keys}

        # which desired modes have NO slider yet?
        unoccupied = [mk for mk in desired_mode_keys if mk not in covered]
        free_slots = [slot for slot, w in pool.items() if getattr(getattr(w, "_current_mode", None), "key", None) not in desired_mode_keys]

        # reassign free sliders to unoccupied desired modes
        free_iter = iter(free_slots)
        newly_assigned = set()
        for mode_key in unoccupied:
            slot = next(free_iter, None)
            if slot is None:
                break  # Pool exhausted (more modes than sliders)
            # setCurrentMode triggers notify_mode_changed → updates _mode_to_slot
            pool[slot].setCurrentMode(mode_key)
            newly_assigned.add(slot)

        active_slots = set(covered.values()).union(newly_assigned)

        # reconcile visibility — show EXACTLY the authorized representative sliders
        for slot, widget in pool.items():
            visible = slot in active_slots
            widget.setVisible(visible)
            settings.set_setting(f"pin_{slot}", visible)

        # sync check states in the active menu (keyed by mode key)
        if self._active_menu and isValid(self._active_menu):
            actions = getattr(self._active_menu, "_tkm_actions", {})

            # Recalculate which modes actively have a visible slider representative
            actual_visible_modes = {
                getattr(pool[slot], "_current_mode", None).key for slot in active_slots if getattr(pool[slot], "_current_mode", None)
            }

            for mode_key, action in actions.items():
                if isValid(action):
                    action.blockSignals(True)
                    action.setChecked(mode_key in actual_visible_modes)
                    action.blockSignals(False)

            # Force the menu to repaint so the visual check marks reflect the new state immediately
            self._active_menu.update()
            self._active_menu.repaint()

        self._refresh_layout()

    def pin_defaults(self, default_keys):
        """Show only the default modes, reassigning sliders as needed."""
        all_mode_keys = {m.key for m in self._all_modes if hasattr(m, "key")}
        default_mode_keys = set()
        for dk in default_keys:
            # default_keys are like "tween_tweener" — match against known mode keys
            for mk in all_mode_keys:
                if dk == mk or dk.endswith(f"_{mk}"):
                    default_mode_keys.add(mk)
                    break
        self._set_visible_modes(default_mode_keys)

    def pin_all(self):
        """Show ALL modes, reassigning sliders to cover every mode in the list."""
        all_mode_keys = {m.key for m in self._all_modes if hasattr(m, "key")}
        self._set_visible_modes(all_mode_keys)

    def _make_toggle_handler(self, key):
        """Creates a handler function that captures 'key'."""

        def handler(checked):
            self.toggle_widget(key, checked)
            self._refresh_layout()

        return handler

    def _refresh_layout(self):
        """Trigger a height recalculation."""
        if not isValid(self):
            return

        parent = self.parent()
        while parent:
            if hasattr(parent, "_update_height"):
                QtCore.QTimer.singleShot(100, parent._update_height)
                break
            parent = parent.parent()

    def _show_menu(self):
        if not self._hiddeable:
            return

        menu = OpenMenuWidget(self)
        menu._tkm_actions = {}
        self._active_menu = menu

        if self._all_modes:
            # Mode-driven sections (sliders): build from the full mode list.
            # Checked = a visible slider currently operates in that mode.
            for mode in self._all_modes:
                if mode == "separator":
                    menu.addSeparator()
                    continue

                slot_key = self._mode_to_slot.get(mode.key)
                widget = self._widgets.get(slot_key) if slot_key else None
                is_visible = widget is not None and isValid(widget) and widget.isVisible()

                action = menu.addAction(mode.label, description=mode.description)
                action.setCheckable(True)
                action.setChecked(is_visible)
                menu._tkm_actions[mode.key] = action

                def make_mode_toggle(mk):
                    def handler(checked):
                        # Compute the new desired visible set and apply it
                        current = {
                            getattr(w, "_current_mode", None).key
                            for w in self._widgets.values()
                            if w.isVisible() and getattr(w, "_current_mode", None)
                        }
                        if checked:
                            current.add(mk)
                        else:
                            current.discard(mk)
                        self._set_visible_modes(current)

                    return handler

                action.triggered.connect(make_mode_toggle(mode.key))

        else:
            # Non-slider sections (toolbar buttons): build from registration metadata
            for item in self._menu_metadata:
                if item["type"] == "separator":
                    menu.addSeparator()
                elif item["type"] == "widget":
                    key = item["key"]
                    widget = self._widgets.get(key)
                    if not widget or not isValid(widget):
                        continue
                    action = menu.addAction(item["label"], description=item["description"])
                    HelpSystem.push(
                        action,
                        title=item.get("tooltip_template") or item.get("tooltip") or item["label"],
                        description=item.get("description") or "",
                    )
                    action.setCheckable(True)
                    action.setChecked(widget.isVisible())
                    action.triggered.connect(self._make_toggle_handler(key))
                    menu._tkm_actions[key] = action

                    # If this widget has a registered action group, show its pinnable
                    # sub-actions inline (separated) so the user can pin them as buttons.
                    group_info = self._tool_groups.get(key)
                    if group_info and group_info.get("actions"):
                        group_icon_path = group_info.get("icon_path") or ""

                        for act_info in group_info["actions"]:
                            act_key = act_info["key"]
                            if act_key == key:
                                continue

                            act_label = act_info.get("label", "")
                            act_icon_path = act_info.get("icon_path") or group_icon_path
                            existing_btn = self._pinned_action_buttons.get(act_key)
                            is_pinned = bool(existing_btn and isValid(existing_btn))

                            sub_action = menu.addAction(QtGui.QIcon(act_icon_path or ""), act_label)
                            HelpSystem.push(
                                sub_action,
                                title=act_info.get("tooltip_template") or act_info.get("tooltip") or act_label,
                                description=act_info.get("description") or "",
                            )
                            sub_action.setCheckable(True)
                            sub_action.setChecked(is_pinned)

                            def _make_pin_handler(gk, ai, ak):
                                def handler(checked):
                                    if checked:
                                        settings.set_setting(f"pin_action_{ak}", True)
                                        self._create_pinned_action_button(gk, ai)
                                    else:
                                        settings.set_setting(f"pin_action_{ak}", False)
                                        self._remove_pinned_action_button(ak)

                                return handler

                            sub_action.triggered.connect(_make_pin_handler(key, act_info, act_key))

                        menu.addSeparator()

        menu.addSeparator()
        pin_def_action = menu.addAction(QtGui.QIcon(media.default_dot_image), "Pin Defaults")
        pin_def_action.triggered.connect(lambda: self.pin_defaults(self._default_keys))
        pin_all_action = menu.addAction(QtGui.QIcon(media.default_dot_image), "Pin All")
        pin_all_action.triggered.connect(self.pin_all)

        menu.exec_(QtGui.QCursor.pos())
        self._active_menu = None

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
