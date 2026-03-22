from TheKeyMachine.tooltips import QFlatTooltipManager
from .util import DPI
import re

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
        res = QtWidgets.QMenu.addAction(self, *args, **kwargs)
        action = args[0] if (len(args) > 0 and isinstance(args[0], QAction)) else res

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

    def setToolTipData(self, **kwargs):
        self._has_tooltip = True
        self.setData(**kwargs)

    def setTooltipInfo(self, title: str, description: str = ""):
        self.setToolTipData(text=title, description=description)

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
            self.setToolTipData(text=tooltip)

    def enterEvent(self, event: QtCore.QEvent):
        self.setButtonSymbols(QtWidgets.QAbstractSpinBox.UpDownArrows)
        super().enterEvent(event)

    def leaveEvent(self, event: QtCore.QEvent):
        self.setButtonSymbols(QtWidgets.QAbstractSpinBox.NoButtons)
        super().leaveEvent(event)


class QFlatToolButton(TooltipMixin, QtWidgets.QToolButton):
    def __init__(self, parent=None, icon=None, text=None, tooltip=None, description=None, shortcuts=None, highlight=False, pressed_color=None):
        super().__init__(parent)
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
        self._highlight = highlight
        if icon:
            self.setIcon(icon)
        self.setToolTipData(text=tooltip, description=description, shortcuts=shortcuts, icon=icon)

    def setIcon(self, icon):
        """Mixin of QToolButton.setIcon that also handles TKM path tracking and hover effects."""
        if isinstance(icon, (str, bytes)):
            self._icon_path = str(icon)
            QFlatHoverableIcon.apply(self, self._icon_path, highlight=self._highlight)
            # Update tooltip icon as well
            data = getattr(self, "_help_data", {})
            self.setToolTipData(
                text=data.get("text", ""),
                description=data.get("description", ""),
                shortcuts=data.get("shortcuts", []),
                icon=self._icon_path,
            )
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

    def addWidget(self, widget, label, key, default_visible=True, description=None):
        """Add a widget to the section with a toggle key."""
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
            self._menu_metadata.append({"type": "widget", "key": key, "label": label, "description": description, "default": default_visible})

            # Load stored visibility or use default
            visible = settings.get_setting(f"pin_{key}", default_visible)
            widget.setVisible(visible)

        return widget

    def addWidgetGroup(self, widget, label, key, widgets, default_visible=True, description=None):
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
        # 1. Register the main widget in the section
        self.addWidget(widget, label, key, default_visible=default_visible, description=description)

        # 2. Resolve the group icon from the widget's stored path
        group_icon_path = getattr(widget, "_icon_path", None) or ""

        # 3. Build QMenu + pinnable_actions from the descriptor list
        menu = QtWidgets.QMenu(widget)
        pinnable_actions = []
        checkable_sync_pairs = []  # (QAction, is_checked_fn) for aboutToShow refresh

        for item in widgets:
            if item == "separator":
                menu.addSeparator()
                continue

            act_icon_path = item.get("icon_path") or ""
            act_label    = item.get("label", "")
            callback     = item.get("callback")
            checkable    = item.get("checkable", False)
            is_checked_fn = item.get("is_checked_fn")

            if checkable:
                action = menu.addAction(QtGui.QIcon(act_icon_path), act_label)
                action.setCheckable(True)
                if is_checked_fn:
                    try:
                        action.setChecked(is_checked_fn())
                    except Exception:
                        pass
                    checkable_sync_pairs.append((action, is_checked_fn))
                if callback:
                    action.triggered.connect(callback)
            else:
                if callback:
                    menu.addAction(QtGui.QIcon(act_icon_path), act_label, callback)
                else:
                    menu.addAction(QtGui.QIcon(act_icon_path), act_label)

            if item.get("pinnable") is not False:
                pinnable_actions.append({
                    "key":          item["key"],
                    "label":        act_label,
                    "icon_path":    item.get("icon_path"),
                    "callback":     callback,
                    "checkable":    checkable,
                    "is_checked_fn": is_checked_fn,
                    "tooltip":      item.get("tooltip"),
                    "description":  item.get("description"),
                })

        # Sync check states on every menu open (handles mutable state)
        if checkable_sync_pairs:
            def _sync(pairs=checkable_sync_pairs):
                for act, fn in pairs:
                    if isValid(act):
                        try:
                            act.setChecked(fn())
                        except Exception:
                            pass
            menu.aboutToShow.connect(_sync)

        # 4. Register group: wires right-click + tear-off on the parent widget
        self.register_action_group(key, label, group_icon_path, pinnable_actions, menu_factory=lambda: menu)

        return widget
    def register_action_group(self, widget_key, group_label, group_icon_path, pinnable_actions, menu_factory=None):
        """
        Register a tool group so its sub-actions can be pinned as standalone buttons.

        Parameters
        ----------
        widget_key : str
            The key used when the parent button was added via addWidget.
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
        self._tool_groups[widget_key] = {
            "label": group_label,
            "icon_path": group_icon_path,
            "menu_factory": menu_factory,
            "actions": pinnable_actions,
        }

        # Auto-wire right-click on the parent widget + enable tear-off
        if menu_factory:
            widget = self._widgets.get(widget_key)
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
                        m = mf()
                        if m and isValid(m):
                            m.exec_(w.mapToGlobal(pos))
                    except Exception:
                        pass

                widget.customContextMenuRequested.connect(_ctx)

        # Restore any previously pinned sub-actions on load
        for act_info in pinnable_actions:
            act_key = act_info["key"]
            if settings.get_setting(f"pin_action_{act_key}", False):
                self._create_pinned_action_button(widget_key, act_info)

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
        tooltip = act_info.get("tooltip") or act_info.get("label", "")
        description = act_info.get("description", "")
        callback = act_info.get("callback")
        checkable = act_info.get("checkable", False)
        is_checked_fn = act_info.get("is_checked_fn")

        btn = QFlatToolButton(icon=icon_path or None, tooltip=tooltip, description=description)
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
                            act_label = act_info.get("label", "")
                            act_icon_path = act_info.get("icon_path") or group_icon_path
                            existing_btn = self._pinned_action_buttons.get(act_key)
                            is_pinned = bool(existing_btn and isValid(existing_btn))

                            sub_action = menu.addAction(QtGui.QIcon(act_icon_path or ""), act_label)
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
