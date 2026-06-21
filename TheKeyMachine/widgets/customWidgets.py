from functools import partial

from TheKeyMachine.mods.tooltipsMod import QFlatTooltipManager
import TheKeyMachine.mods.settingsMod as settings  # type: ignore
from TheKeyMachine.data import icons
import TheKeyMachine.core.runtimeManager as runtime  # type: ignore
from TheKeyMachine.tools import colors as toolColors  # type: ignore
from TheKeyMachine.tools import common as toolCommon  # type: ignore

from .util import DPI

try:
    import TheKeyMachine_user_data.preferences.user_preferences as user_preferences  # type: ignore
except ImportError:
    user_preferences = None

from TheKeyMachine.Qt import QtCompat, QtCore, QtGui, QtWidgets  # type: ignore


"""
TheKeyMachine Custom Widgets
===========================
Centralized repository for UI components used throughout the toolbar.
Includes QFlatToolButton with automated sizing, hover effects (glow), 
and user preference integration.
"""


def _status_description(description="", status_description=None, tooltip_template=None):
    _title, resolved_description = toolCommon.resolve_status_metadata(
        description=description,
        tooltip_template=tooltip_template,
        status_description=status_description,
    )
    return resolved_description


def _help_title(text="", status_title=None, tooltip_template=None):
    resolved_title, _description = toolCommon.resolve_status_metadata(
        title=text,
        tooltip_template=tooltip_template,
        status_title=status_title,
    )
    return resolved_title


def _push_help(widget, data):
    HelpSystem.push(
        widget,
        _help_title(
            text=data.get("text", ""),
            status_title=data.get("status_title"),
            tooltip_template=data.get("tooltip_template"),
        ),
        _status_description(
            description=data.get("description", ""),
            status_description=data.get("status_description"),
            tooltip_template=data.get("tooltip_template"),
        ),
    )


def get_widget_tint_color(widget, default=None):
    if not widget:
        return default
    try:
        if hasattr(widget, "get_tint_color"):
            color = widget.get_tint_color()
            if color is not None:
                return color
    except Exception:
        pass
    try:
        color = widget.property("tkm_tint_color")
        if color is not None:
            return color
    except Exception:
        pass
    return default


def _default_pressed_color_hex():
    return toolColors.UI_COLORS.gray.hex


def _color_to_hex(color, default=None):
    if default is None:
        default = _default_pressed_color_hex()
    resolved = toolColors.to_hex(color)
    if resolved:
        return str(resolved)
    try:
        qcolor = QtGui.QColor(color)
        if qcolor.isValid():
            return qcolor.name()
    except Exception:
        pass
    return str(color) if isinstance(color, str) else default


class HelpSystem:
    """Centralized utility for pushing help text to all Maya help channels."""

    @staticmethod
    def clean(raw):
        return toolCommon.clean_tool_text(raw)

    @staticmethod
    def get_desc(raw):
        return toolCommon.get_tool_summary(raw)

    @classmethod
    def push(cls, widget_or_action, title="", description=""):
        """Pushes data to StatusTip, ToolTip, and internal properties."""
        raw_title = title or ""
        raw_desc = description or ""

        c_title = cls.clean(raw_title)
        if not c_title and hasattr(widget_or_action, "objectName"):
            c_title = cls.clean(widget_or_action.objectName())

        c_desc = cls.get_desc(raw_desc)
        # Avoid redundancy: if description starts with/is the title, strip it
        if c_title and c_desc:
            if c_title.lower() == c_desc.lower():
                c_desc = ""
            elif c_desc.lower().startswith(c_title.lower()):
                c_desc = c_desc[len(c_title) :].strip(" -:,.")
                # Restore sentence case safely
                if c_desc:
                    c_desc = c_desc[0].upper() + c_desc[1:]

        status = f"{c_title} - {c_desc}" if (c_title and c_desc) else (c_title or c_desc)

        is_action = isinstance(widget_or_action, QtGui.QAction)
        if hasattr(widget_or_action, "setStatusTip") and not is_action:
            widget_or_action.setStatusTip(status)
            try:
                status_event = QtGui.QStatusTipEvent(status)
                QtWidgets.QApplication.sendEvent(widget_or_action, status_event)
            except Exception:
                pass

        if hasattr(widget_or_action, "setProperty"):
            widget_or_action.setProperty("tkm_title", raw_title)
            widget_or_action.setProperty("tkm_description", raw_desc)
            widget_or_action.setProperty("description", raw_desc)

        # Maya 2023's embedded Qt can crash in QtGui.QAction::showStatusText while
        # hovering menus if custom menu actions push native status-tip events.
        # Keep TKM metadata for our own tooltip UI, but leave menu QtGui.QAction
        # status text to Qt's default empty state.


class LogoAction(QtWidgets.QWidgetAction):
    def __init__(self, parent, clickable=True):
        super().__init__(parent)
        self.setStatusTip("")
        self.setToolTip("")

        self._container = QtWidgets.QWidget(parent)
        layout = QtWidgets.QVBoxLayout(self._container)
        layout.setContentsMargins(0, 10, 0, 10)
        layout.setSpacing(0)

        logo_pix = QtGui.QPixmap(icons.TheKeyMachine_logo_250)
        if not logo_pix.isNull():
            self.logo_label = QtWidgets.QLabel()
            self.logo_label.setPixmap(logo_pix.scaledToHeight(DPI(60), QtCore.Qt.SmoothTransformation))
            self.logo_label.setAlignment(QtCore.Qt.AlignCenter)
            layout.addWidget(self.logo_label)

        self.setDefaultWidget(self._container)
        self.clickable = clickable
        if clickable:
            self._container.setCursor(QtGui.QCursor(QtCore.Qt.PointingHandCursor))
            self._container.mouseReleaseEvent = self._on_clicked

    def isClickable(self):
        return self.clickable

    def _on_clicked(self, event):
        import webbrowser

        webbrowser.open("https://github.com/Alehaaaa/TKM")
        if self.parent() and hasattr(self.parent(), "hide"):
            self.parent().hide()


class MenuWidget(QtWidgets.QMenu):
    def __init__(self, *args, **kwargs):
        description = kwargs.pop("description", None)
        tearoff = kwargs.pop("tearoff", True)

        icon = None
        new_args = []
        for arg in args:
            if isinstance(arg, QtGui.QIcon):
                icon = arg
            else:
                new_args.append(arg)

        QtWidgets.QMenu.__init__(self, *new_args, **kwargs)
        self.setTearOffEnabled(tearoff)

        if self.parent() and hasattr(self.parent(), "destroyed"):
            self.parent().destroyed.connect(self.close)

        if icon:
            self.setIcon(icon)

        if description or self.title():
            HelpSystem.push(self, self.title(), description)

        self.hovered.connect(self._on_action_hovered)

    def _action_tooltip_key(self, action):
        if action is None or not QtCompat.isValid(action) or isinstance(action, QtWidgets.QWidgetAction):
            return None
        try:
            key = action.property("tkm_tooltip_source_key")
            if not key:
                key = "menu-action:{}".format(id(action))
                action.setProperty("tkm_tooltip_source_key", key)
            return key
        except (RuntimeError, ValueError, TypeError, AttributeError, KeyError, IndexError):
            return None

    @staticmethod
    def _clear_native_action_tips(action):
        try:
            action.setStatusTip("")
            action.setToolTip("")
        except (RuntimeError, ValueError, TypeError, AttributeError, KeyError, IndexError):
            pass

    def _set_action_help(self, action, title, description="", tooltip_template=None):
        if action is None or not QtCompat.isValid(action):
            return
        if isinstance(action, QtWidgets.QWidgetAction):
            self._clear_native_action_tips(action)
            return
        if hasattr(action, "setProperty"):
            action.setProperty("tkm_tooltip_template", tooltip_template)
            self._action_tooltip_key(action)
        HelpSystem.push(action, title, description)
        self._clear_native_action_tips(action)

    @staticmethod
    def _cursor_target_rect(pos=None):
        return QtCore.QRect(pos or QtGui.QCursor.pos(), QtCore.QSize(1, 1))

    def addAction(self, *args, **kwargs):
        description = kwargs.pop("description", None)
        tooltip_template = kwargs.pop("tooltip_template", None)
        callback = kwargs.pop("callback", None)
        label_override = kwargs.pop("label", None)
        keep_open = kwargs.pop("open", False)

        res = QtWidgets.QMenu.addAction(self, *args, **kwargs)
        action = args[0] if (len(args) > 0 and isinstance(args[0], QtGui.QAction)) else res

        if keep_open and hasattr(action, "setProperty"):
            action.setProperty("tkm_keep_menu_open", True)

        if callback:
            action.triggered.connect(callback)

        label = ""
        for arg in args:
            if isinstance(arg, (str, bytes)):
                label = arg
                break

        title = label_override or toolCommon.get_tooltip_title(tooltip_template) or label or action.text()
        resolved_description = _status_description(
            description=description or "",
            tooltip_template=tooltip_template,
        )
        if title or resolved_description or tooltip_template:
            self._set_action_help(action, title, resolved_description, tooltip_template)
        else:
            self._clear_native_action_tips(action)
        return action

    def addMenu(self, *args, **kwargs):
        description = kwargs.pop("description", None)
        item = QtWidgets.QMenu.addMenu(self, *args, **kwargs)
        action = item.menuAction() if hasattr(item, "menuAction") else item

        label = action.text()
        self._set_action_help(action, label, description)
        return item

    def _on_action_hovered(self, action):
        if action is None or not QtCompat.isValid(action) or isinstance(action, QtWidgets.QWidgetAction):
            QFlatTooltipManager.cancel_timer()
            return

        source_key = self._action_tooltip_key(action)
        if not source_key:
            return
        if QFlatTooltipManager.is_current_source(source_key):
            return

        try:
            title = action.property("tkm_title") or action.text()
            desc = action.property("tkm_description") or ""
            tooltip_template = action.property("tkm_tooltip_template") or None
        except (RuntimeError, ValueError, TypeError, AttributeError, KeyError, IndexError):
            return

        if not (title or desc or tooltip_template):
            QFlatTooltipManager.cancel_timer()
            return

        if QFlatTooltipManager.enabled:
            display_template = tooltip_template or ((title, [desc], None) if desc else title)

            cursor_pos = QtGui.QCursor.pos()
            icon = action.icon() if not action.icon().isNull() else None
            QFlatTooltipManager.delayed_show(
                text=title,
                anchor_widget=self,
                target_rect=self._cursor_target_rect(cursor_pos),
                target_pos=cursor_pos,
                description=desc,
                tooltip_template=display_template,
                icon_obj=icon,
                source_key=source_key,
            )

    def hideEvent(self, event):
        QFlatTooltipManager.hide()
        QtWidgets.QMenu.hideEvent(self, event)

    def leaveEvent(self, event):
        QFlatTooltipManager.cancel_timer()
        QtWidgets.QMenu.leaveEvent(self, event)

    def mouseReleaseEvent(self, e):
        action = self.actionAt(e.pos())
        if isinstance(action, QtWidgets.QWidgetAction):
            if hasattr(action, "isClickable") and not action.isClickable():
                e.accept()
                return
        QtWidgets.QMenu.mouseReleaseEvent(self, e)


class OpenMenuWidget(MenuWidget):
    def __init__(self, *args, **kwargs):
        MenuWidget.__init__(self, *args, **kwargs)
        self.setTearOffEnabled(True)

    def mouseReleaseEvent(self, e):
        action = self.actionAt(e.pos())
        keep_open = False
        if action and hasattr(action, "property"):
            try:
                keep_open = bool(action.property("tkm_keep_menu_open"))
            except (RuntimeError, ValueError, TypeError, AttributeError, KeyError, IndexError):
                keep_open = False
        if action and action.isEnabled() and (action.isCheckable() or keep_open):
            action.trigger()
            e.accept()
            return
        QtWidgets.QMenu.mouseReleaseEvent(self, e)


class TooltipMixin:
    def setData(
        self, text="", description="", shortcuts=None, icon=None, tooltip_template=None, status_title=None, status_description=None
    ):
        # Automatically pick up the widget's icon if not provided
        if not icon and hasattr(self, "_icon"):
            icon = self._icon

        self._toolTipData = {
            "text": text,
            "description": description,
            "shortcuts": shortcuts or [],
            "icon": icon,
            "tooltip_template": tooltip_template,
            "status_title": status_title,
            "status_description": _status_description(
                description=description,
                status_description=status_description,
                tooltip_template=tooltip_template,
            ),
        }
        _push_help(self, self._toolTipData)

    def get_toolTipData(self):
        return getattr(self, "_toolTipData", {})

    def setToolTipData(self, **kwargs):
        self._has_tooltip = True
        self.setData(**kwargs)

    def setTooltipInfo(self, title: str, description: str = ""):
        self.setToolTipData(text=title, description=description)

    def enterEvent(self, event: QtCore.QEvent):
        # Refresh description and trigger Maya event
        data = getattr(self, "_toolTipData", {})
        _push_help(self, data)

        try:
            super().enterEvent(event)
        except (AttributeError, TypeError):
            pass

        if QFlatTooltipManager.enabled and getattr(self, "_has_tooltip", False):
            if data.get("text") or data.get("description") or data.get("tooltip_template"):
                source_key = "widget:{}".format(id(self))
                if QFlatTooltipManager.is_current_source(source_key):
                    return
                # Pass the template directly to the tooltip manager
                QFlatTooltipManager.delayed_show(anchor_widget=self, source_key=source_key, **data)

    def leaveEvent(self, event: QtCore.QEvent):
        QFlatTooltipManager.cancel_timer()
        try:
            super().leaveEvent(event)
        except (AttributeError, TypeError):
            pass


class QFlatButton(QtWidgets.QPushButton):
    """A customizable, flat-styled button for the bottom bar."""

    STYLE_SHEET = """
    QPushButton {
        color: %s;
        background-color: %s;
        border-radius: %spx;
        padding: %spx %spx;
        font-weight: %s;
        font-size: %spx;
    }
    QPushButton:hover {
        background-color: %s;
    }
    QPushButton:pressed {
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
        icon=None,
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
        if icon:
            icons.QHoverableIcon.apply(self, icon, highlight=highlight)

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
    A container widget for arranging QFlat Buttons horizontally.
    """

    def __init__(self, buttons=[], margins=8, spacing=6, parent=None):
        QtWidgets.QFrame.__init__(self, parent)
        self.setSizePolicy(QtWidgets.QSizePolicy.Expanding, QtWidgets.QSizePolicy.Fixed)

        layout = QtWidgets.QHBoxLayout(self)
        layout.setContentsMargins(DPI(margins), DPI(margins), DPI(margins), DPI(margins))
        layout.setSpacing(DPI(spacing))

        for button in buttons:
            if button is None:
                continue
            if button.parentWidget() is None:
                button.setParent(self)
            layout.addWidget(button)


class QFlatSpinBox(QtWidgets.QSpinBox):
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.setFixedHeight(24)
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
        shortcut_variants=None,
        highlight=False,
        pressed_color=None,
    ):
        super().__init__(parent)
        self.setAutoRaise(True)
        self.pressed_color = pressed_color
        self._modifier_watch_connected = False
        self._shortcut_variants = []
        self._variant_state_lock = False
        self._active_variant_mask = None
        self._section = None
        self._section_key = None

        if text:
            self.setText(text)
            self.setToolButtonStyle(QtCore.Qt.ToolButtonIconOnly if icon else QtCore.Qt.ToolButtonTextOnly)
        else:
            self.setToolButtonStyle(QtCore.Qt.ToolButtonIconOnly)

        self._refresh_button_stylesheet()

        # Centralized size
        w = 28
        h = 28
        if user_preferences:
            w = getattr(user_preferences, "toolbar_icon_w", 28)
            h = getattr(user_preferences, "toolbar_icon_h", 28)

        self.setFixedSize(w, h)
        # Small margin to prevent glow clipping (w-2 x h-2)
        self.setIconSize(QtCore.QSize(w - 2, h - 2))

        self._icon = icon
        self._highlight = highlight
        self._base_state = {
            "text": text,
            "description": description,
            "shortcuts": shortcuts or [],
            "tooltip_template": tooltip_template,
            "icon": icon,
            "status_title": None,
            "status_description": None,
        }
        if icon:
            self._apply_icon_visual(icon)
        self.setToolTipData(
            text=text,
            description=description,
            shortcuts=shortcuts,
            tooltip_template=tooltip_template,
            icon=icon,
        )
        self.setShortcutVariants(shortcut_variants or [])

    def connect_tool(self, callback=None, *, checkable=None, state_fn=None, bind_fn=None, changed_signal=None):
        """
        Bind this tool button to its action in the same place its check state is wired.

        Tool descriptors can still use ``create_tool_button_from_data``. Direct callers
        can use this when they need a button first and wiring second.
        """
        return toolCommon.connect_tool_control(
            self,
            callback,
            checkable=checkable,
            getter=state_fn,
            changed_signal=changed_signal,
            bind_fn=bind_fn,
        )

    def connect_window_toggle(self, toggle, *, menu_factory=None, context_attr="_tkm_window_toggle_context_menu"):
        return toolCommon.connect_window_toggle_control(
            self,
            toggle,
            menu_factory=menu_factory,
            context_attr=context_attr,
        )

    def setIcon(self, icon):
        """Mixin of QToolButton.setIcon that also handles TKM path tracking and hover effects."""
        if isinstance(icon, (str, bytes)):
            self._icon = str(icon)
            self._apply_icon_visual(self._icon)
            data = getattr(self, "_toolTipData", {})
            self.setToolTipData(icon=self._icon, **data)
        elif icon:
            super().setIcon(icon)

    def setToolTipData(self, **kwargs):
        display_text = kwargs.pop("display_text", None)
        super().setToolTipData(**kwargs)
        if not self._variant_state_lock:
            if display_text is not None:
                self._base_state["text"] = display_text
            elif self._base_state.get("text") is None:
                self._base_state["text"] = kwargs.get("text")
            self._base_state["description"] = kwargs.get("description", self._base_state.get("description"))
            self._base_state["shortcuts"] = kwargs.get("shortcuts", self._base_state.get("shortcuts", []))
            self._base_state["tooltip_template"] = kwargs.get("tooltip_template", self._base_state.get("tooltip_template"))
            self._base_state["icon"] = kwargs.get("icon", self._base_state.get("icon"))
            self._base_state["status_title"] = kwargs.get("status_title", self._base_state.get("status_title"))
            self._base_state["status_description"] = kwargs.get("status_description", self._base_state.get("status_description"))

    def setShortcutVariants(self, variants):
        self._shortcut_variants = list(variants or [])
        self._active_variant_mask = None

    def on_added_to_section(self, section, key):
        self._section = section
        self._section_key = key
        self._refresh_button_stylesheet()

    def set_tint_color(self, color):
        self.setProperty("tkm_tint_color", color)
        self._refresh_button_stylesheet()

    def get_tint_color(self):
        color = self.property("tkm_tint_color")
        if color is not None:
            return color
        section = getattr(self, "_section", None)
        if section and hasattr(section, "get_tint_color"):
            return section.get_tint_color()
        return None

    def _resolve_pressed_color(self):
        if self.pressed_color:
            return self.pressed_color
        return _color_to_hex(self.get_tint_color())

    def _refresh_button_stylesheet(self):
        pressed_bg = _color_to_hex(self._resolve_pressed_color())
        self.setStyleSheet(
            f"""
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
            QToolButton:pressed,
            QToolButton:checked {{
                background-color: {pressed_bg};
                color: #ffffff;
            }}
            """
        )

    def triggerToolCallback(self, base_callback, *args, **kwargs):
        variant = self._get_active_shortcut_variant()
        callback = variant.get("callback") if variant else None
        chunk_opened = False
        try:
            chunk_opened = toolCommon.open_undo_chunk()
            if callback:
                return callback(*args, **kwargs)
            if base_callback:
                return base_callback(*args, **kwargs)
        finally:
            if chunk_opened:
                try:
                    toolCommon.close_undo_chunk()
                except Exception:
                    pass

    def _apply_icon_visual(self, icon):
        if isinstance(icon, (str, bytes)):
            icons.QHoverableIcon.apply(self, str(icon), highlight=self._highlight)
        elif icon:
            super().setIcon(icon)

    def _get_active_shortcut_variant(self):
        if not self._shortcut_variants:
            return None
        current_mask = runtime.get_modifier_mask()
        best = None
        best_bits = -1
        for variant in self._shortcut_variants:
            mask = int(variant.get("mask", 0))
            if current_mask != mask:
                continue
            bits = bin(mask).count("1")
            if bits > best_bits:
                best = variant
                best_bits = bits
        return best

    def _apply_display_state(self, state):
        self._variant_state_lock = True
        try:
            text = state.get("text")
            tooltip_template = state.get("tooltip_template", text)
            description = state.get("description", "")
            shortcuts = state.get("shortcuts", [])
            icon = state.get("icon")
            status_title = state.get("status_title")
            status_description = state.get("status_description")
            self.setText(text or "")
            self._apply_icon_visual(icon)
            TooltipMixin.setToolTipData(
                self,
                text=status_title or text,
                description=description,
                shortcuts=shortcuts,
                tooltip_template=tooltip_template,
                icon=icon,
                status_title=status_title,
                status_description=status_description,
            )
        finally:
            self._variant_state_lock = False

    def _variant_to_state(self, variant):
        if not variant:
            return {
                "text": self._base_state.get("text"),
                "description": self._base_state.get("description"),
                "shortcuts": self._base_state.get("shortcuts", []),
                "tooltip_template": self._base_state.get("tooltip_template"),
                "icon": self._base_state.get("icon"),
                "status_title": self._base_state.get("status_title"),
                "status_description": self._base_state.get("status_description"),
            }
        tooltip_template = variant.get("tooltip_template")
        return {
            "text": variant.get("text", self._base_state.get("text")),
            "description": variant.get("description", ""),
            "shortcuts": variant.get("shortcuts", []),
            "tooltip_template": tooltip_template,
            "icon": variant.get("icon", self._base_state.get("icon")),
            "status_title": (
                variant.get("status_title")
                or variant.get("label")
                or toolCommon.get_tooltip_title(tooltip_template)
                or self._base_state.get("status_title")
            ),
            "status_description": _status_description(
                description=variant.get("description", ""),
                status_description=variant.get("status_description"),
                tooltip_template=tooltip_template,
            ),
        }

    def _refresh_modifier_variant_state(self):
        variant = self._get_active_shortcut_variant()
        target_mask = int(variant.get("mask", 0)) if variant else None
        if target_mask == self._active_variant_mask:
            return False
        self._active_variant_mask = target_mask
        self._apply_display_state(self._variant_to_state(variant))
        return True

    def _restore_base_state(self):
        if self._active_variant_mask is None:
            return
        self._active_variant_mask = None
        self._apply_display_state(self._variant_to_state(None))

    def _connect_modifier_variant_watch(self):
        if not self._shortcut_variants or self._modifier_watch_connected:
            return
        try:
            runtime.get_runtime_manager().modifiers_changed.connect(self._on_modifier_state_changed)
            self._modifier_watch_connected = True
        except Exception:
            self._modifier_watch_connected = False

    def _disconnect_modifier_variant_watch(self):
        if not self._modifier_watch_connected:
            return
        try:
            runtime.get_runtime_manager().modifiers_changed.disconnect(self._on_modifier_state_changed)
        except Exception:
            pass
        self._modifier_watch_connected = False

    def _on_modifier_state_changed(self, *_args):
        if not self.underMouse() or not self._shortcut_variants:
            return
        if not self._refresh_modifier_variant_state():
            return
        data = getattr(self, "_toolTipData", {})
        QFlatTooltipManager.hide()
        if data.get("text") or data.get("description") or data.get("tooltip_template"):
            QFlatTooltipManager.delayed_show(anchor_widget=self, **data)

    def enterEvent(self, event: QtCore.QEvent):
        self._connect_modifier_variant_watch()
        if self._shortcut_variants and runtime.get_modifier_mask():
            self._refresh_modifier_variant_state()
        TooltipMixin.enterEvent(self, event)

    def leaveEvent(self, event: QtCore.QEvent):
        self._disconnect_modifier_variant_watch()
        if self._shortcut_variants:
            self._restore_base_state()
        TooltipMixin.leaveEvent(self, event)


class QFlatSelectorButton(QFlatToolButton):
    def __init__(self, parent=None, icon=None, tooltip_template=None, description=None):
        super().__init__(parent=parent, icon=icon, tooltip_template=tooltip_template, description=description)
        self._count_text = "0"
        self.setText("")
        self.setToolButtonStyle(QtCore.Qt.ToolButtonIconOnly)

    def _format_count_text(self, value):
        try:
            count = int(value)
        except Exception:
            return str(value)

        if count >= 1000000:
            return "{}m".format(int(count / 1000000))
        if count >= 1000:
            return "{}k".format(int(count / 1000))
        return str(count)

    def setCount(self, value):
        self._count_text = self._format_count_text(value)
        self.update()

    def paintEvent(self, event):
        super().paintEvent(event)
        painter = QtGui.QPainter(self)
        painter.setRenderHint(QtGui.QPainter.TextAntialiasing)

        font = painter.font()
        font.setBold(False)
        font.setPixelSize(DPI(11))
        painter.setFont(font)

        color = QtGui.QColor("#ffffff" if self.underMouse() or self.isDown() or self.isChecked() else "#bfbfbf")
        painter.setPen(color)
        rect = self.rect().translated(0, -DPI(3))
        painter.drawText(rect, QtCore.Qt.AlignCenter, self._count_text)


def create_tool_button_from_data(tool_data, parent=None, **overrides):
    data = dict(tool_data or {})
    data.update(overrides)
    tooltip_template = data.get("tooltip_template")
    display_text = data.get("text")
    title = (
        data.get("status_title")
        or data.get("label")
        or toolCommon.get_tooltip_title(tooltip_template)
        or display_text
        or data.get("id")
        or ""
    )
    description = data.get("description")
    status_description = _status_description(
        description=description,
        status_description=data.get("status_description"),
        tooltip_template=tooltip_template,
    )

    btn = QFlatToolButton(
        parent=parent,
        icon=data.get("icon"),
        text=display_text,
        tooltip_template=tooltip_template,
        description=description,
        shortcuts=data.get("shortcuts"),
        shortcut_variants=data.get("shortcut_variants"),
    )
    btn.setToolTipData(
        text=title,
        description=description,
        shortcuts=data.get("shortcuts"),
        tooltip_template=tooltip_template,
        icon=data.get("icon"),
        status_title=title,
        status_description=status_description,
        display_text=display_text,
    )
    if data.get("tint_color") is not None:
        btn.set_tint_color(data.get("tint_color"))

    toolCommon.connect_control_from_data(btn, data)

    menu = data.get("menu")
    if callable(menu):
        btn.setContextMenuPolicy(QtCore.Qt.CustomContextMenu)

        def _show_tool_menu(pos, setup_fn=menu, widget=btn):
            menu = OpenMenuWidget(widget)
            try:
                built_menu = setup_fn(menu, source_widget=widget)
            except TypeError:
                built_menu = setup_fn(menu)
            if built_menu is not None and built_menu is not False:
                menu = built_menu
            if menu.actions():
                menu.exec_(widget.mapToGlobal(pos))

        btn.customContextMenuRequested.connect(_show_tool_menu)
        if data.get("type") == "menu":
            btn.clicked.connect(
                lambda _checked=False, widget=btn: widget.customContextMenuRequested.emit(widget.mapFromGlobal(QtGui.QCursor.pos()))
            )
    return btn


def _checked_state_fn(data):
    return toolCommon.checked_state_getter(data)


def _sync_checked_from_setting(control, state_fn):
    return toolCommon.sync_checked(control, state_fn)


def _setup_setting_synced_checkable(control, data):
    checkable = bool(data.get("checkable", data.get("type") == "check"))
    state_fn = _checked_state_fn(data)
    toolCommon.connect_control_from_data(control, data, callback=None)
    return checkable, state_fn


class QFlowLayout(QtWidgets.QLayout):
    DEFAULT_SPACING = 5

    def __init__(self, parent=None, margin=0, Hspacing=-1, Vspacing=-1, alignment=None, **kwargs):
        super().__init__(parent)
        self._item_list = []

        # Handle 'Wspacing'
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

    def setSpacing(self, spacing):
        super().setSpacing(spacing)
        self._Hspacing = spacing

    def addSpacing(self, size):
        """Use layout spacing for section gaps instead of inserting spacer items."""
        self.setSpacing(size)
        self.invalidate()

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

    def _should_skip_item(self, item):
        wid = item.widget()
        if wid is None:
            return item.isEmpty()
        if wid.isHidden():
            return True
        if hasattr(wid, "_has_visible_content") and not wid._has_visible_content():
            return True
        return False

    def _visible_items(self):
        return [item for item in self._item_list if not self._should_skip_item(item)]

    def _horizontal_spacing(self):
        return self._Hspacing if self._Hspacing != -1 else self.DEFAULT_SPACING

    def _vertical_spacing(self):
        return self._Vspacing if self._Vspacing != -1 else self.DEFAULT_SPACING

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
        return self._singleRowSize()

    def minimumSize(self):
        size = QtCore.QSize()
        for item in self._visible_items():
            size = size.expandedTo(item.minimumSize())

        margins = self.contentsMargins()
        size += QtCore.QSize(margins.left() + margins.right(), margins.top() + margins.bottom())
        return size

    def _singleRowSize(self):
        margins = self.contentsMargins()
        width = margins.left() + margins.right()
        height = margins.top() + margins.bottom()
        visible_count = 0
        spacing_x = self._horizontal_spacing()

        for item in self._visible_items():
            item_size = item.sizeHint()
            if visible_count:
                width += spacing_x
            width += item_size.width()
            height = max(height, item_size.height() + margins.top() + margins.bottom())
            visible_count += 1

        return QtCore.QSize(width, height)

    def doLayout(self, rect, test_only):
        margins = self.contentsMargins()
        effective_rect = rect.adjusted(+margins.left(), +margins.top(), -margins.right(), -margins.bottom())
        x = effective_rect.x()
        y = effective_rect.y()
        line_height = 0

        lines = []
        current_line = []
        current_line_width = 0

        space_x = self._horizontal_spacing()
        space_y = self._vertical_spacing()

        for item in self._item_list:
            if self._should_skip_item(item):
                if not test_only:
                    item.setGeometry(QtCore.QRect())
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


class QFillFlowLayout(QtWidgets.QLayout):
    def __init__(self, parent=None, margin=0, Hspacing=-1, Vspacing=-1, alignment=None):
        super().__init__(parent)
        self._item_list = []
        self._Hspacing = Hspacing
        self._Vspacing = Vspacing
        self.setContentsMargins(margin, margin, margin, margin)
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
        return self._do_layout(QtCore.QRect(0, 0, width, 0), True)

    def setGeometry(self, rect):
        super().setGeometry(rect)
        self._do_layout(rect, False)

    def sizeHint(self):
        return self.minimumSize()

    def minimumSize(self):
        size = QtCore.QSize()
        for item in self._item_list:
            size = size.expandedTo(item.minimumSize())
        margins = self.contentsMargins()
        size += QtCore.QSize(margins.left() + margins.right(), margins.top() + margins.bottom())
        return size

    def _visible_items(self):
        visible_items = []
        for item in self._item_list:
            widget = item.widget()
            if widget is not None and widget.isHidden():
                continue
            visible_items.append(item)
        return visible_items

    def _build_rows(self, items, available_width, spacing_x):
        rows = []
        current_row = []
        current_width = 0
        current_height = 0

        for item in items:
            item_size = item.sizeHint()
            item_width = item_size.width()
            projected_width = item_width if not current_row else current_width + spacing_x + item_width

            if current_row and projected_width > available_width:
                rows.append((current_row, current_width, current_height))
                current_row = [item]
                current_width = item_width
                current_height = item_size.height()
                continue

            current_row.append(item)
            current_width = projected_width
            current_height = max(current_height, item_size.height())

        if current_row:
            rows.append((current_row, current_width, current_height))
        return rows

    def _do_layout(self, rect, test_only):
        margins = self.contentsMargins()
        effective_rect = rect.adjusted(+margins.left(), +margins.top(), -margins.right(), -margins.bottom())
        available_width = max(0, effective_rect.width())
        if available_width <= 0:
            return margins.top() + margins.bottom()

        spacing_x = self._Hspacing if self._Hspacing >= 0 else 5
        spacing_y = self._Vspacing if self._Vspacing >= 0 else 5
        visible_items = self._visible_items()
        if not visible_items:
            return margins.top() + margins.bottom()

        rows = self._build_rows(visible_items, available_width, spacing_x)
        current_y = effective_rect.y()

        if not test_only:
            for row_items, row_width, row_height in rows:
                count = len(row_items)
                extra_width = max(0, available_width - row_width)
                extra_each, extra_remainder = divmod(extra_width, count)
                current_x = effective_rect.x()

                for index, item in enumerate(row_items):
                    item_size = item.sizeHint()
                    item_width = item_size.width() + extra_each + (1 if index < extra_remainder else 0)
                    item_height = item_size.height()
                    dy = max(0, (row_height - item_height) // 2)
                    item.setGeometry(
                        QtCore.QRect(
                            QtCore.QPoint(int(current_x), int(current_y + dy)),
                            QtCore.QSize(int(item_width), int(item_height)),
                        )
                    )
                    current_x += item_width + spacing_x

                current_y += row_height + spacing_y
        else:
            for _, _, row_height in rows:
                current_y += row_height + spacing_y

        if rows:
            current_y -= spacing_y
        return current_y - rect.y() + margins.bottom()


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


class QFlatToolbar(QFlowContainer):
    """
    A unified, reusable toolbar widget that uses QFlowLayout to contain
    multiple QFlatSectionWidgets and dynamically updates its height.
    """

    def __init__(self, parent=None, settings_namespace=None, margin=2, spacing_w=10, spacing_h=6, alignment=None):
        super().__init__(parent)
        self.setObjectName("tkm_flat_toolbar")
        self._tkm_sections = []
        self._settings_namespace = settings_namespace

        # Use QFlowLayout to allow section wrapping
        layout = QFlowLayout(
            self,
            margin=margin,
            Wspacing=spacing_w,
            Hspacing=spacing_h,
            alignment=alignment or QtCore.Qt.AlignLeft
        )
        self.setLayout(layout)

    def add_section(self, spacing=0, hiddeable=True, color=None, settings_namespace=None):
        sec = QFlatSectionWidget(
            parent=self,
            spacing=spacing,
            hiddeable=hiddeable,
            settings_namespace=settings_namespace or self._settings_namespace,
            color=color,
        )
        self._tkm_sections.append(sec)
        self.layout().addWidget(sec)
        return sec

    def set_alignment(self, alignment):
        layout = self.layout()
        if layout:
            try:
                layout.setAlignment(alignment)
                layout.invalidate()
            except Exception:
                pass
        self.updateGeometry()
        self.update()
        self._update_height()


class PersistentPlaceholderLineEdit(QtWidgets.QLineEdit):
    def paintEvent(self, event):
        super().paintEvent(event)
        if self.text():
            return
        placeholder = self.placeholderText()
        if not placeholder:
            return

        painter = QtGui.QPainter(self)
        painter.setRenderHint(QtGui.QPainter.TextAntialiasing)
        color = self.palette().color(QtGui.QPalette.PlaceholderText)
        if not color.isValid():
            color = QtGui.QColor("#7b7b7b")
        painter.setPen(color)
        rect = self.rect().adjusted(DPI(6), 0, -DPI(6), 0)
        painter.drawText(rect, QtCore.Qt.AlignCenter, placeholder)
        painter.end()


class InlineRenameLineEdit(QtWidgets.QLineEdit):
    def keyPressEvent(self, event):
        if event.key() in (QtCore.Qt.Key_Return, QtCore.Qt.Key_Enter):
            self.returnPressed.emit()
            return
        if event.key() == QtCore.Qt.Key_Escape:
            self.clearFocus()
            return
        super().keyPressEvent(event)


class CompressibleScrollArea(QtWidgets.QScrollArea):
    def minimumSizeHint(self):
        return QtCore.QSize(0, 0)

    def sizeHint(self):
        return QtCore.QSize(0, 0)

    def viewportSizeHint(self):
        return QtCore.QSize(0, 0)


class InlineRenameButton(QtWidgets.QPushButton):
    def __init__(self, text="", parent=None, line_edit_class=None):
        super().__init__(text, parent)
        self._renaming_active = False
        self._original_text = text
        self._rename_hidden_text_stylesheet = None
        self._rename_payload = None
        self._rename_commit_callback = None
        editor_class = line_edit_class or InlineRenameLineEdit
        self.inline_rename_field = editor_class(self)
        self.inline_rename_field.setFrame(False)
        self.inline_rename_field.setAlignment(QtCore.Qt.AlignCenter)
        self.inline_rename_field.hide()
        self.inline_rename_field.returnPressed.connect(self._finish_inline_rename)
        self.inline_rename_field.editingFinished.connect(self._finish_inline_rename)

    def set_rename_target(self, rename_payload, display_name, commit_callback):
        self._rename_payload = rename_payload
        self._rename_commit_callback = commit_callback
        self._original_text = display_name
        self.setText(display_name)

    def mouseDoubleClickEvent(self, event):
        if event.button() == QtCore.Qt.LeftButton:
            self.start_inline_rename()
            event.accept()
            return
        super().mouseDoubleClickEvent(event)

    def resizeEvent(self, event):
        super().resizeEvent(event)
        if self._renaming_active:
            self._position_inline_rename()

    def start_inline_rename(self):
        if not self._rename_commit_callback or self._rename_payload is None:
            return
        self._renaming_active = True
        self._position_inline_rename()
        self._sync_inline_rename_style()
        self.inline_rename_field.setText(self._original_text)
        self._apply_hidden_text_style(True)
        self.inline_rename_field.show()
        self.inline_rename_field.raise_()
        self.inline_rename_field.setFocus(QtCore.Qt.ActiveWindowFocusReason)
        self.inline_rename_field.selectAll()
        self.update()

    def _position_inline_rename(self):
        rect = self.rect().adjusted(DPI(6), DPI(5), -DPI(6), -DPI(5))
        self.inline_rename_field.setGeometry(rect)

    def _finish_inline_rename(self):
        if not self._renaming_active:
            return
        self._renaming_active = False
        new_name = self.inline_rename_field.text().strip()
        self.inline_rename_field.hide()
        self._apply_hidden_text_style(False)
        self.update()
        if new_name and new_name != self._original_text and self._rename_commit_callback and self._rename_payload is not None:
            self._rename_commit_callback(self._rename_payload, new_name)

    def _apply_hidden_text_style(self, enabled):
        if enabled:
            if self._rename_hidden_text_stylesheet is None:
                self._rename_hidden_text_stylesheet = self.styleSheet()
            self.setStyleSheet(
                self._rename_hidden_text_stylesheet
                + """
                QPushButton {
                    color: transparent;
                }
                QPushButton:hover {
                    color: transparent;
                }
                """
            )
        elif self._rename_hidden_text_stylesheet is not None:
            self.setStyleSheet(self._rename_hidden_text_stylesheet)
            self._rename_hidden_text_stylesheet = None

    def _sync_inline_rename_style(self):
        text_color = self.property("tkm_text_color") or "#1a1a1a"
        self.inline_rename_field.setStyleSheet(
            """
            QLineEdit {
                background-color: transparent;
                border: none;
                color: %s;
                padding: 0px 6px;
            }
            """
            % text_color
        )


# QPainter for the shelf tabBar


class QFlatSectionWidget(QtWidgets.QWidget):
    """
    A container for toolbar sections that provides a hover-activated overlay
    for toggling the visibility of its child widgets.
    """

    sliderModesChanged = QtCore.Signal(object)

    def __init__(self, parent=None, spacing=0, hiddeable=True, settings_namespace=None, color=None):
        super().__init__(parent)
        self.setLayout(QtWidgets.QHBoxLayout())
        self.layout().setContentsMargins(0, 3, 0, 3)
        self.layout().setSpacing(spacing)
        self._hiddeable = hiddeable
        self._settings_namespace = settings_namespace
        self._tint_color = color

        self._widgets = {}  # slot_key -> widget mapping
        self._menu_metadata = []  # for non-slider sections (toolbar buttons etc.)
        self._default_keys = []
        self._all_modes = []  # Full ordered mode list (SliderMode objects + "separator")
        self._mode_to_slot = {}  # mode_key -> slot_key (live, authoritative mapping)
        self._persist_slider_modes = True

        if self._hiddeable:
            # Overlay button: tiny checkbox in the bottom-left
            self._overlay_btn = QtWidgets.QToolButton(self)
            self._overlay_btn.setFixedSize(8, 8)
            self._overlay_btn.setVisible(False)
            HelpSystem.push(self._overlay_btn, "Pinned Tools", "Manage which tools are pinned for quick access.")

            # Ensure the tiny button pushes its help to Maya on hover
            def _push_help(event, btn=self._overlay_btn):
                HelpSystem.push(btn, btn.property("tkm_title"), btn.property("tkm_description"))
                return QtWidgets.QToolButton.enterEvent(btn, event)

            self._overlay_btn.enterEvent = _push_help
            self._overlay_btn.setStyleSheet("""
                QToolButton {
                    border: none;
                    background-color: #2e2e2e;
                }
                QToolButton:hover {
                    background-color: #313131;
                }
            """)

            self._overlay_btn.pressed.connect(lambda: self.open_menu(QtGui.QCursor.pos()))

    def set_menu_identity(self, label=None, icon=None):
        self._menu_label = label
        self._menu_icon = icon

    def menu_label(self):
        return getattr(self, "_menu_label", None) or self.objectName() or "Tools"

    def menu_icon(self):
        return getattr(self, "_menu_icon", None)

    def has_pinnable_items(self):
        return bool(self._hiddeable and (self._all_modes or self._menu_metadata))

    def populate_pinning_menu(self, menu):
        self._populate_menu(menu)
        return menu

    def _has_visible_content(self):
        for widget in self._widgets.values():
            if widget and QtCompat.isValid(widget) and not widget.isHidden():
                return True
        return False

    def _sync_section_visibility(self):
        if not self._hiddeable:
            return
        should_show = self._has_visible_content()
        if self.isVisible() != should_show:
            self.setVisible(should_show)
            parent_layout = self.parentWidget().layout() if self.parentWidget() else None
            if parent_layout:
                parent_layout.invalidate()

    def set_settings_namespace(self, namespace):
        self._settings_namespace = namespace

    def set_persist_slider_modes(self, enabled):
        self._persist_slider_modes = bool(enabled)

    def set_tint_color(self, color):
        self._tint_color = color

    def get_tint_color(self):
        return self._tint_color

    def _get_setting(self, key, default_value=None):
        return settings.get_setting(key, default_value, namespace=self._settings_namespace)

    def _set_setting(self, key, value):
        settings.set_setting(key, value, namespace=self._settings_namespace)

    def addWidget(self, widget, label, key, default=True, description=None, tooltip_template=None, pinnable=True):
        """Add a widget to the section with a toggle key."""
        # Auto-extract help metadata from widget if not provided
        if (not tooltip_template or not description) and hasattr(widget, "get_toolTipData"):
            data = widget.get_toolTipData()
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
            if hasattr(widget, "currentModeChanged"):
                try:
                    widget.currentModeChanged.disconnect(self._on_slider_current_mode_changed)
                except (RuntimeError, TypeError):
                    pass
                widget.currentModeChanged.connect(self._on_slider_current_mode_changed)

            cm = getattr(widget, "_current_mode", None)
            if cm:
                saved_mode_key = cm.key
                if self._persist_slider_modes:
                    saved_mode_key = self._get_setting(f"slider_mode_{key}", cm.key)
                    if saved_mode_key != cm.key and hasattr(widget, "setCurrentMode"):
                        widget.setCurrentMode(saved_mode_key)
                # Register current mode in the section's live map
                current_cm = getattr(widget, "_current_mode", None)
                if current_cm:
                    self._mode_to_slot[current_cm.key] = key

        if self._hiddeable:
            if pinnable is not False:
                # Avoid duplicate metadata entries for the same key
                existing_entry = next((m for m in self._menu_metadata if m.get("id") == key), None)
                if existing_entry:
                    existing_entry.update(
                        {
                            "label": label,
                            "description": description,
                            "tooltip_template": tooltip_template,
                            "default": default,
                        }
                    )
                else:
                    self._menu_metadata.append(
                        {
                            "type": "widget",
                            "id": key,
                            "label": label,
                            "description": description,
                            "tooltip_template": tooltip_template,
                            "default": default,
                        }
                    )
                visible = self._get_setting(f"pin_{key}", default)
            else:
                visible = default
            widget.setVisible(visible)
            self._sync_section_visibility()

        if hasattr(widget, "setToolTipData"):
            d = description
            tt = tooltip_template
            existing = getattr(widget, "_toolTipData", {}) if hasattr(widget, "_toolTipData") else {}
            if not d and not tt and hasattr(widget, "_toolTipData"):
                d = existing.get("description")
                tt = existing.get("tooltip_template")
            status_description = existing.get("status_description")
            if status_description is None:
                status_description = _status_description(
                    description=d or "",
                    tooltip_template=tt,
                )

            widget.setToolTipData(
                text=label,
                description=d or "",
                shortcuts=existing.get("shortcuts", []),
                tooltip_template=tt,
                icon=existing.get("icon"),
                status_title=existing.get("status_title") or label,
                status_description=status_description,
            )
        else:
            HelpSystem.push(widget, label, description or "")

        return widget

    def addWidgetGroup(self, widgets_list, default=True):
        """
        Add a descriptor group as regular pinnable widgets sharing one right-click menu.

        Parameters
        ----------
        widgets : list
            List of action descriptors or the string ``"separator"``.
            Each descriptor dict may contain:
              key, label, icon, callback,
              checkable (bool), get_checked/get_checked_fn (callable),
              changed_signal, bind_checked_fn (callable), tooltip, description.
        """
        default_items = [
            i
            for i in widgets_list
            if isinstance(i, dict) and i.get("id") and i.get("pinnable", True) is not False
        ]

        group_widgets = []
        for default_item in default_items:
            widget = create_tool_button_from_data(
                default_item,
                callback=None,
                menu=None,
                tooltip_template=default_item.get("tooltip_template") or default_item.get("tooltip"),
                description=default_item.get("description") or "",
            )
            label = default_item.get("label", "Unknown")
            key = default_item.get("id", "unknown")
            item_default = default_item.get("default", default)

            toolCommon.connect_control_from_data(widget, default_item)

            # 1. Register the main widget in the section
            self.addWidget(
                widget,
                label,
                key,
                default=item_default,
                description=default_item.get("description"),
                tooltip_template=default_item.get("tooltip_template") or default_item.get("tooltip"),
                pinnable=default_item.get("pinnable", True),
            )
            group_widgets.append((key, widget))

        item_by_key = {item.get("id"): item for item in widgets_list if isinstance(item, dict) and item.get("id")}

        first_item = default_items[0] if default_items else {}

        def menu_factory(section=self, source_widget=None, widgets=widgets_list, source_items=item_by_key):
            menu = OpenMenuWidget(source_widget)
            menu.setTearOffEnabled(True)

            source_key = None
            if source_widget and QtCompat.isValid(source_widget):
                for k, w in section._widgets.items():
                    if w == source_widget:
                        source_key = k
                        break

            checkable_sync_pairs = []
            source_item = source_items.get(source_key) or {}
            setup_fn = source_item.get("menu") or first_item.get("menu")
            replace_group_actions = False
            if callable(setup_fn):
                try:
                    replace_group_actions = setup_fn(menu, source_widget=source_widget) is False
                except TypeError:
                    replace_group_actions = setup_fn(menu) is False
            if not replace_group_actions:
                for item in widgets:
                    if item == "separator":
                        menu.addSeparator()
                        continue

                    if item.get("id") == source_key:
                        continue
                    act_icon_p = item.get("icon") or ""
                    cb = item.get("callback")
                    checkable = item.get("checkable", False)

                    # Use raw label for display, but full tooltip for documentation
                    display_label = item.get("label", "")
                    full_tooltip = item.get("tooltip_template") or item.get("tooltip")
                    full_desc = item.get("description") or ""

                    if checkable:
                        action = menu.addAction(QtGui.QIcon(act_icon_p), display_label, tooltip_template=full_tooltip, description=full_desc)
                        _checkable, is_checked_f = _setup_setting_synced_checkable(action, item)
                        if is_checked_f:
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
                        if QtCompat.isValid(act):
                            _sync_checked_from_setting(act, fn)

                menu.aboutToShow.connect(_sync)
            return menu

        self.register_action_group([key for key, _widget in group_widgets], menu_factory=menu_factory)

        return group_widgets[0][1] if group_widgets else None

    def register_action_group(self, widget_keys, menu_factory=None):
        """Attach the same right-click menu factory to all widgets in a descriptor group."""
        keys_list = [widget_keys] if isinstance(widget_keys, str) else widget_keys

        for w_key in keys_list:
            if menu_factory:
                widget = self._widgets.get(w_key)
                if widget and QtCompat.isValid(widget):
                    widget.setContextMenuPolicy(QtCore.Qt.CustomContextMenu)

                    def _ctx(pos, mf=menu_factory, w=widget):
                        try:
                            m = mf(source_widget=w)
                            if m and QtCompat.isValid(m):
                                m.exec_(w.mapToGlobal(pos))
                        except (RuntimeError, ValueError, TypeError, AttributeError, KeyError, IndexError):
                            pass

                    widget.customContextMenuRequested.connect(_ctx)

    def toggle_widget(self, key, visible, save_setting=True, menu=None):
        """Toggle widget visibility and update menu/settings if needed."""
        widget = self._widgets.get(key)
        if widget and QtCompat.isValid(widget):
            widget.setVisible(visible)

        if save_setting:
            self._set_setting(f"pin_{key}", visible)
        self._sync_section_visibility()

        # Update the currently open menu action, keyed by mode key for mode-driven sections.
        if menu and QtCompat.isValid(menu):
            # Try to look up by slot key or by current mode key of that widget
            widget = self._widgets.get(key)
            current_cm = getattr(widget, "_current_mode", None) if widget else None
            action_key = current_cm.key if current_cm else key
            action = getattr(menu, "_tkm_actions", {}).get(action_key)
            if action and QtCompat.isValid(action):
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
            if QtCompat.isValid(w) and hasattr(w, "_modes") and w._modes:
                self._all_modes = w._modes
                break

    def _on_slider_current_mode_changed(self, widget, old_key, new_key):
        """Slot for QFlatSliderWidget.currentModeChanged."""
        slot_key = next((k for k, v in self._widgets.items() if v is widget), None)
        if not slot_key:
            return
        if old_key:
            self._mode_to_slot.pop(old_key, None)
        if new_key:
            self._mode_to_slot[new_key] = slot_key
            if self._persist_slider_modes:
                self._set_setting(f"slider_mode_{slot_key}", new_key)
        self._emit_slider_modes_changed()

    def _set_visible_modes(self, desired_mode_keys, menu=None):
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
            # setCurrentMode emits currentModeChanged, which updates _mode_to_slot.
            pool[slot].setCurrentMode(mode_key)
            newly_assigned.add(slot)

        active_slots = set(covered.values()).union(newly_assigned)

        # reconcile visibility — show EXACTLY the authorized representative sliders
        for slot, widget in pool.items():
            visible = slot in active_slots
            widget.setVisible(visible)
            self._set_setting(f"pin_{slot}", visible)
        self._sync_section_visibility()
        self._emit_slider_modes_changed()

        self._refresh_layout()

    def pin_defaults(self, default_keys, menu=None):
        """Show only the default modes, reassigning sliders as needed."""
        all_mode_keys = {m.key for m in self._all_modes if hasattr(m, "key")}
        default_mode_keys = set()
        for dk in default_keys:
            # default_keys are like "tween_tweener" — match against known mode keys
            for mk in all_mode_keys:
                if dk == mk or dk.endswith(f"_{mk}"):
                    default_mode_keys.add(mk)
                    break
        self._set_visible_modes(default_mode_keys, menu=menu)

    def pin_all(self, menu=None):
        """Show ALL modes, reassigning sliders to cover every mode in the list."""
        all_mode_keys = {m.key for m in self._all_modes if hasattr(m, "key")}
        self._set_visible_modes(all_mode_keys, menu=menu)

    def pin_widget_defaults(self, menu=None):
        """Non-slider sections: restore widget visibility and sub-action pins to defaults."""
        for item in self._menu_metadata:
            if item.get("type") != "widget":
                continue
            key = item.get("id")
            if not key:
                continue
            self.toggle_widget(key, bool(item.get("default", True)), save_setting=True, menu=menu)

        self._sync_widget_menu_actions(menu)
        self._refresh_layout()

    def pin_widget_all(self, menu=None):
        """Non-slider sections: show all widgets and pin all group sub-actions."""
        for item in self._menu_metadata:
            if item.get("type") != "widget":
                continue
            key = item.get("id")
            if not key:
                continue
            self.toggle_widget(key, True, save_setting=True, menu=menu)

        self._sync_widget_menu_actions(menu)
        self._refresh_layout()

    def _make_toggle_handler(self, key, menu=None):
        """Creates a handler function that captures 'key'."""

        def handler(checked):
            self.toggle_widget(key, checked, menu=menu)
            self._refresh_layout()

        return handler

    def _sync_widget_menu_actions(self, menu):
        if menu is None or not QtCompat.isValid(menu):
            return

        actions = getattr(menu, "_tkm_actions", {})
        for item in self._menu_metadata:
            if item.get("type") != "widget":
                continue
            key = item.get("id")
            action = actions.get(key)
            widget = self._widgets.get(key)
            if not key or action is None or not QtCompat.isValid(action) or widget is None or not QtCompat.isValid(widget):
                continue
            action.blockSignals(True)
            action.setChecked(widget.isVisible())
            action.blockSignals(False)

        menu.update()
        menu.repaint()

    def _visible_slider_mode_keys(self):
        modes = set()
        for widget in self._widgets.values():
            if not QtCompat.isValid(widget) or not widget.isVisible() or not hasattr(widget, "_current_mode"):
                continue
            current_mode = getattr(widget, "_current_mode", None)
            if current_mode:
                modes.add(current_mode.key)
        return modes

    def _emit_slider_modes_changed(self):
        if self._all_modes:
            self.sliderModesChanged.emit(self._visible_slider_mode_keys())

    def _bind_slider_mode_action(self, menu, action, mode_key):
        def sync_action(visible_modes, action=action, menu=menu, mode_key=mode_key):
            if not QtCompat.isValid(action):
                return
            action.blockSignals(True)
            action.setChecked(mode_key in set(visible_modes or []))
            action.blockSignals(False)
            if QtCompat.isValid(menu):
                menu.update()
                menu.repaint()

        self.sliderModesChanged.connect(sync_action)
        menu._tkm_slider_mode_syncs.append(sync_action)

        def disconnect_action(*_args, sync_fn=sync_action):
            try:
                self.sliderModesChanged.disconnect(sync_fn)
            except (RuntimeError, TypeError):
                pass

        action.destroyed.connect(disconnect_action)
        sync_action(self._visible_slider_mode_keys())
        return action

    def _refresh_layout(self):
        """Trigger a height recalculation."""
        if not QtCompat.isValid(self):
            return

        parent = self.parent()
        while parent:
            if hasattr(parent, "_update_height"):
                QtCore.QTimer.singleShot(100, parent._update_height)
                break
            parent = parent.parent()

    def _add_checkable_menu_action(
        self,
        menu,
        key,
        label,
        checked,
        handler,
        description="",
        title=None,
        icon=None,
        tooltip_template=None,
    ):
        if icon and not icon.isNull():
            action = menu.addAction(icon, label, description=description, tooltip_template=tooltip_template, label=title)
        else:
            action = menu.addAction(label, description=description, tooltip_template=tooltip_template, label=title)
        action.setCheckable(True)
        action.setChecked(bool(checked))
        action.triggered.connect(handler)
        menu._tkm_actions[key] = action
        return action

    def _populate_menu(self, menu):
        menu._tkm_actions = {}

        if self._all_modes:
            menu._tkm_slider_mode_syncs = []

            # Mode-driven sections (sliders): build from the full mode list.
            # Checked = a visible slider currently operates in that mode.
            for mode in self._all_modes:
                if mode == "separator":
                    menu.addSeparator()
                    continue

                is_visible = mode.key in self._visible_slider_mode_keys()

                def make_mode_toggle(mk):
                    def handler(checked):
                        # Compute the new desired visible set and apply it
                        current = {
                            getattr(w, "_current_mode", None).key
                            for w in self._widgets.values()
                            if QtCompat.isValid(w) and w.isVisible() and getattr(w, "_current_mode", None)
                        }
                        if checked:
                            current.add(mk)
                        else:
                            current.discard(mk)
                        self._set_visible_modes(current, menu=menu)

                    return handler

                self._add_checkable_menu_action(
                    menu,
                    mode.key,
                    mode.label,
                    is_visible,
                    make_mode_toggle(mode.key),
                    description=mode.description,
                    title=mode.label,
                    tooltip_template=getattr(mode, "tooltip_template", None),
                )
                self._bind_slider_mode_action(menu, menu._tkm_actions[mode.key], mode.key)

        else:
            # Non-slider sections (toolbar buttons): build from registration metadata
            for item in self._menu_metadata:
                if item["type"] == "separator":
                    menu.addSeparator()
                elif item["type"] == "widget":
                    key = item["id"]
                    widget = self._widgets.get(key)
                    if widget is None or not QtCompat.isValid(widget):
                        continue
                    self._add_checkable_menu_action(
                        menu,
                        key,
                        item["label"],
                        widget.isVisible(),
                        self._make_toggle_handler(key, menu=menu),
                        description=item.get("description") or "",
                        title=item["label"],
                        tooltip_template=item.get("tooltip_template"),
                    )
        menu.addSeparator()
        pin_def_action = menu.addAction(QtGui.QIcon(icons.dot_round), "Pin Defaults", open=True)
        if self._all_modes:
            pin_def_action.triggered.connect(lambda: self.pin_defaults(self._default_keys, menu=menu))
        else:
            pin_def_action.triggered.connect(lambda: self.pin_widget_defaults(menu=menu))
        pin_all_action = menu.addAction(QtGui.QIcon(icons.dot_round), "Pin All", open=True)
        if self._all_modes:
            pin_all_action.triggered.connect(lambda: self.pin_all(menu=menu))
        else:
            pin_all_action.triggered.connect(lambda: self.pin_widget_all(menu=menu))

    def _build_menu(self):
        if not self._hiddeable:
            return None

        menu = OpenMenuWidget(self)
        self._populate_menu(menu)

        return menu

    def open_menu(self, global_pos=None):
        if global_pos is None:
            global_pos = QtGui.QCursor.pos()

        menu = self._build_menu()
        if not menu:
            return
        menu.exec_(global_pos)

    def _show_menu(self):
        self.open_menu(QtGui.QCursor.pos())

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
