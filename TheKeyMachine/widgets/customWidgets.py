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
    def __init__(
        self, parent=None, icon=None, text=None, tooltip=None, description=None, shortcuts=None, highlight=False, pressed_color=None
    ):
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

        self._widgets = {}  # slot_key -> widget mapping
        self._menu_metadata = []  # for non-slider sections (toolbar buttons etc.)
        self._default_keys = []
        self._active_menu = None
        self._all_modes = []  # Full ordered mode list (SliderMode objects + "separator")
        self._mode_to_slot = {}  # mode_key -> slot_key (live, authoritative mapping)

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
            self._menu_metadata.append(
                {"type": "widget", "key": key, "label": label, "description": description, "default": default_visible}
            )

            # Load stored visibility or use default
            visible = settings.get_setting(f"pin_{key}", default_visible)
            widget.setVisible(visible)

        return widget

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

        # Step 1: which desired modes are already covered by a slider?
        covered = {cm.key: slot for slot, w in pool.items() if (cm := getattr(w, "_current_mode", None)) and cm.key in desired_mode_keys}

        # Step 2: which desired modes have NO slider yet?
        unoccupied = [mk for mk in desired_mode_keys if mk not in covered]

        # Step 3: free sliders — those whose current mode is NOT in the desired set
        free_slots = [slot for slot, w in pool.items() if getattr(getattr(w, "_current_mode", None), "key", None) not in desired_mode_keys]

        # Step 4: reassign free sliders to unoccupied desired modes
        free_iter = iter(free_slots)
        for mode_key in unoccupied:
            slot = next(free_iter, None)
            if slot is None:
                break  # Pool exhausted (more modes than sliders)
            # setCurrentMode triggers notify_mode_changed → updates _mode_to_slot
            pool[slot].setCurrentMode(mode_key)

        # Step 5: reconcile visibility — show sliders whose mode is desired, hide others
        for slot, widget in pool.items():
            cm = getattr(widget, "_current_mode", None)
            visible = cm is not None and cm.key in desired_mode_keys
            widget.setVisible(visible)
            settings.set_setting(f"pin_{slot}", visible)

        # Step 6: sync check states in the active menu (keyed by mode key)
        if self._active_menu and isValid(self._active_menu):
            actions = getattr(self._active_menu, "_tkm_actions", {})
            for mode_key, action in actions.items():
                if isValid(action):
                    action.blockSignals(True)
                    action.setChecked(mode_key in desired_mode_keys)
                    action.blockSignals(False)

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
