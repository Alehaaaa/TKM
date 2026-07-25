from functools import partial
import inspect
import warnings

from TheKeyMachine.mods.tooltipsMod import QFlatTooltipManager
import TheKeyMachine.mods.settingsMod as settings  # type: ignore
from TheKeyMachine.data import icons
import TheKeyMachine.core.runtimeManager as runtime  # type: ignore
from TheKeyMachine.data.colors import COLORS  # type: ignore
from TheKeyMachine.tools import common as toolCommon  # type: ignore

from .util import DPI

try:
    import TheKeyMachine_user_data.preferences.user_preferences as user_preferences  # type: ignore
except ImportError:
    user_preferences = None

from TheKeyMachine.core.Qt import QtCompat, QtCore, QtGui, QtWidgets  # type: ignore


"""
TheKeyMachine Custom Widgets
===========================
Centralized repository for UI components used throughout the toolbar.
Includes QFlatToolButton with automated sizing and user preference integration.
"""


def _status_description(description="", status_description=None, tooltip=None):
    _title, resolved_description = toolCommon.resolve_status_metadata(
        description=description,
        tooltip=tooltip,
        status_description=status_description,
    )
    return resolved_description


def _help_title(text="", status_title=None, tooltip=None):
    resolved_title, _description = toolCommon.resolve_status_metadata(
        title=text,
        tooltip=tooltip,
        status_title=status_title,
    )
    return resolved_title


def _format_menu_status_tip(name, description="", tooltip=None):
    clean_name = toolCommon.clean_tool_text(name)
    clean_description = (
        toolCommon.get_tool_summary(description)
        or toolCommon.get_tooltip_summary(tooltip)
    )
    if clean_name and clean_description:
        return "{} - {}".format(clean_name, clean_description)
    return clean_name or clean_description


def _push_help(widget, data):
    HelpSystem.push(
        widget,
        _help_title(
            text=data.get("text", ""),
            status_title=data.get("status_title"),
            tooltip=data.get("tooltip"),
        ),
        _status_description(
            description=data.get("description", ""),
            status_description=data.get("status_description"),
            tooltip=data.get("tooltip"),
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
    return COLORS.ui.gray.hex


def _color_to_hex(color, default=None):
    if default is None:
        default = _default_pressed_color_hex()
    resolved = getattr(color, "hex", None)
    if resolved:
        return str(resolved)
    try:
        qcolor = QtGui.QColor(color)
        if qcolor.isValid():
            return qcolor.name()
    except Exception:
        pass
    return str(color) if isinstance(color, str) else default


def _tinted_icon(icon_path, color, size):
    source = QtGui.QPixmap(icon_path)
    if source.isNull():
        source = QtGui.QIcon(icon_path).pixmap(size)
    if source.isNull():
        return QtGui.QIcon(icon_path)

    pixmap = source.scaled(size, QtCore.Qt.KeepAspectRatio, QtCore.Qt.SmoothTransformation)
    if pixmap.isNull():
        return QtGui.QIcon(icon_path)

    tinted = QtGui.QPixmap(pixmap.size())
    tinted.fill(QtCore.Qt.transparent)

    painter = QtGui.QPainter(tinted)
    painter.drawPixmap(0, 0, pixmap)
    painter.setCompositionMode(QtGui.QPainter.CompositionMode_SourceIn)
    painter.fillRect(tinted.rect(), QtGui.QColor(color))
    painter.end()

    return QtGui.QIcon(tinted)


TOOLTIP_STATE_KEYS = (
    "text",
    "description",
    "shortcuts",
    "tooltip",
    "icon",
    "status_title",
    "status_description",
    "command_id",
    "command_label",
    "command_icon",
)


def _tool_command_label(data, fallback=""):
    tooltip = data.get("tooltip") if isinstance(data, dict) else None
    return (
        data.get("status_title")
        or data.get("label")
        or data.get("menu_label")
        or toolCommon.get_tooltip_title(tooltip)
        or data.get("text")
        or data.get("id")
        or fallback
        or ""
    )


def _tooltip_state_from_data(data, *, display_text=None):
    data = dict(data or {})
    tooltip = data.get("tooltip")
    description = data.get("description")
    if isinstance(tooltip, str):
        description = description or tooltip
    title = _tool_command_label(data)
    state = {
        "text": title,
        "description": description,
        "shortcuts": data.get("shortcuts"),
        "tooltip": tooltip,
        "icon": data.get("icon"),
        "status_title": title,
        "status_description": _status_description(
            description=description,
            status_description=data.get("status_description"),
            tooltip=tooltip,
        ),
        "command_id": data.get("id"),
        "command_label": title,
        "command_icon": data.get("icon"),
    }
    if display_text is not None:
        state["display_text"] = display_text
    return state


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
        # Python-side store for rich action help. Qt properties cannot safely
        # round-trip Tooltip subclasses or shortcut descriptor collections.
        self._action_help_store = {}
        parent = self.parentWidget()
        if isinstance(parent, QtWidgets.QMenu):
            self._tkm_source_widget = getattr(parent, "_tkm_source_widget", None)
        else:
            self._tkm_source_widget = parent

    def _callback_anchor(self):
        source = getattr(self, "_tkm_source_widget", None)
        return source if source is not None and QtCompat.isValid(source) else None

    def _close_menu_chain(self):
        menu = self
        while isinstance(menu, QtWidgets.QMenu):
            parent = menu.parentWidget()
            menu.close()
            menu = parent

    def mouseReleaseEvent(self, e):
        action = self.actionAt(e.pos())
        keep_open = False
        if action and hasattr(action, "property"):
            try:
                keep_open = bool(action.property("tkm_keep_menu_open"))
            except (RuntimeError, ValueError, TypeError, AttributeError, KeyError, IndexError):
                keep_open = False
        if action and action.isEnabled() and keep_open:
            action.trigger()
            e.accept()
            return
        QtWidgets.QMenu.mouseReleaseEvent(self, e)

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

    @staticmethod
    def _set_native_action_tips(action, title, description="", tooltip=None):
        try:
            action.setStatusTip(_format_menu_status_tip(title, description, tooltip))
            # QFlatTooltip owns the floating tooltip; retain only Qt's status-bar text.
            action.setToolTip("")
        except (RuntimeError, ValueError, TypeError, AttributeError, KeyError, IndexError):
            pass

    def _set_action_help(
        self,
        action,
        title,
        description="",
        tooltip=None,
        shortcuts=None,
        command_id=None,
        command_icon=None,
    ):
        if action is None or not QtCompat.isValid(action):
            return
        if isinstance(action, QtWidgets.QWidgetAction):
            self._clear_native_action_tips(action)
            return
        if hasattr(action, "setProperty"):
            # Store the full Tooltip in a Python dict (not via Qt property)
            # so that body_lines / TooltipMedia objects survive the round-trip.
            source_key = self._action_tooltip_key(action)
            if source_key:
                self._action_help_store[source_key] = {
                    "title": title,
                    "description": description,
                    "tooltip": tooltip,
                    "shortcuts": list(shortcuts or ()),
                    "command_id": command_id,
                    "command_label": title,
                    "command_icon": command_icon,
                }
            action.setProperty("tkm_command_id", command_id)
            action.setProperty("tkm_command_label", title)
            action.setProperty("tkm_command_icon", command_icon)
        HelpSystem.push(action, title, description)
        self._set_native_action_tips(action, title, description, tooltip)

    @staticmethod
    def _callback_from_args(args):
        for arg in args:
            if callable(arg) and not isinstance(arg, (QtGui.QIcon, QtGui.QAction)):
                return arg
        return None

    @staticmethod
    def _callback_accepts_checked(callback):
        try:
            parameters = inspect.signature(callback).parameters.values()
        except Exception:
            return False
        return any(
            parameter.kind in (inspect.Parameter.POSITIONAL_ONLY, inspect.Parameter.POSITIONAL_OR_KEYWORD, inspect.Parameter.VAR_POSITIONAL)
            for parameter in parameters
        )

    @staticmethod
    def _trigger_command_from_callback(callback):
        name = getattr(callback, "__name__", None)
        try:
            from TheKeyMachine.core import trigger

            return trigger.command_name_for_callback(callback)
        except Exception:
            return name if getattr(callback, "_tkm_trigger_proxy", False) else None

    @staticmethod
    def _cursor_target_rect(pos=None):
        return QtCore.QRect(pos or QtGui.QCursor.pos(), QtCore.QSize(1, 1))

    def _menu_at_global_pos(self, pos):
        widget = QtWidgets.QApplication.widgetAt(pos)
        visited = set()
        while widget:
            widget_id = id(widget)
            if widget_id in visited:
                break
            visited.add(widget_id)
            if isinstance(widget, QtWidgets.QMenu):
                return widget
            parent_widget = getattr(widget, "parentWidget", None)
            if callable(parent_widget):
                widget = parent_widget()
                continue
            parent = getattr(widget, "parent", None)
            widget = parent() if callable(parent) else None
        for widget in QtWidgets.QApplication.topLevelWidgets():
            if isinstance(widget, QtWidgets.QMenu) and widget.isVisible() and widget.frameGeometry().contains(pos):
                return widget
        return self

    def _action_global_rect(self, action, pos=None):
        pos = pos or QtGui.QCursor.pos()
        menu = self._menu_at_global_pos(pos)
        try:
            local_pos = menu.mapFromGlobal(pos)
            hovered_action = menu.actionAt(local_pos)
            rect_action = hovered_action or action
            rect = menu.actionGeometry(rect_action)
        except (RuntimeError, ValueError, TypeError, AttributeError, KeyError, IndexError):
            return self._cursor_target_rect(pos)
        if not rect.isValid():
            return self._cursor_target_rect(pos)
        rect.moveTo(menu.mapToGlobal(rect.topLeft()))
        return rect

    def addAction(self, *args, **kwargs):
        description = kwargs.pop("description", None)
        tooltip = kwargs.pop("tooltip", None)
        tooltip_enabled = kwargs.pop("tooltip_enabled", True)
        callback = kwargs.pop("callback", None)
        label_override = kwargs.pop("label", None)
        keep_open = kwargs.pop("open", False)
        shortcuts = kwargs.pop("shortcuts", None)
        command_id = kwargs.pop("command_id", None)
        command_icon = kwargs.pop("command_icon", None)
        positional_callback = self._callback_from_args(args)
        metadata_callback = callback or positional_callback

        # Do not let Qt connect positional callbacks directly; every executable
        # menu action must pass through the shared ToolOperation runner.
        qt_args = tuple(arg for arg in args if arg is not positional_callback)
        res = QtWidgets.QMenu.addAction(self, *qt_args, **kwargs)
        action = args[0] if (len(args) > 0 and isinstance(args[0], QtGui.QAction)) else res

        if keep_open and hasattr(action, "setProperty"):
            action.setProperty("tkm_keep_menu_open", True)
        if hasattr(action, "setProperty"):
            action.setProperty("tkm_tooltip_enabled", bool(tooltip_enabled))

        label = ""
        for arg in args:
            if isinstance(arg, (str, bytes)):
                label = arg
                break

        if command_id:
            try:
                from TheKeyMachine.core import toolbox

                toolbox_tooltip = toolbox.get_tool(command_id).get("tooltip")
            except Exception:
                toolbox_tooltip = None
            if isinstance(toolbox_tooltip, str):
                description = toolbox_tooltip
                tooltip = None

        title = label_override or toolCommon.get_tooltip_title(tooltip) or label or action.text()
        if command_id is None:
            command_id = self._trigger_command_from_callback(metadata_callback)

        if metadata_callback:
            def _invoke_menu_callback(
                checked=False,
                cb=metadata_callback,
            ):
                anchor = self._callback_anchor()
                try:
                    pass_checked = (
                        action.isCheckable()
                        and self._callback_accepts_checked(cb)
                    )
                except RuntimeError:
                    return

                def _run(
                    callback_anchor=anchor,
                    callback_accepts_checked=pass_checked,
                ):
                    call_args = (checked,) if callback_accepts_checked else ()
                    toolCommon.run_tool_callback(
                        callback_anchor,
                        cb,
                        *call_args,
                        _tkm_tool_id=command_id,
                        _tkm_tool_label=title,
                    )

                if not keep_open:
                    self._close_menu_chain()
                QtCore.QTimer.singleShot(0, _run)

            # Menu builders commonly call setCheckable/setChecked immediately
            # after addAction returns.  Defer choosing the signal until those
            # properties have been initialized; this also prevents setChecked
            # from executing the action callback while the menu is built.
            def _connect_menu_callback(target=action):
                if not QtCompat.isValid(target):
                    return
                if not target.isCheckable():
                    target.triggered.connect(_invoke_menu_callback)
                else:
                    target.toggled.connect(lambda checked: _invoke_menu_callback(checked))

            QtCore.QTimer.singleShot(0, _connect_menu_callback)

        resolved_description = _status_description(
            description=description or "",
            tooltip=tooltip,
        )
        if title or resolved_description or tooltip:
            self._set_action_help(
                action,
                title,
                resolved_description,
                tooltip,
                shortcuts=shortcuts,
                command_id=command_id,
                command_icon=command_icon,
            )
        else:
            self._clear_native_action_tips(action)
        return action

    def addMenu(self, *args, **kwargs):
        description = kwargs.pop("description", None)
        tooltip = kwargs.pop("tooltip", None)
        shortcuts = kwargs.pop("shortcuts", None)
        command_id = kwargs.pop("command_id", None)
        command_icon = kwargs.pop("command_icon", None)
        item = QtWidgets.QMenu.addMenu(self, *args, **kwargs)
        action = item.menuAction() if hasattr(item, "menuAction") else item

        label = action.text()
        if command_id:
            try:
                from TheKeyMachine.core import toolbox

                toolbox_tooltip = toolbox.get_tool(command_id).get("tooltip")
            except Exception:
                toolbox_tooltip = None
            if isinstance(toolbox_tooltip, str):
                description = toolbox_tooltip
                tooltip = None
            elif toolbox_tooltip is not None:
                tooltip = toolbox_tooltip
        resolved_description = _status_description(
            description=description or "",
            tooltip=tooltip,
        )
        self._set_action_help(
            action,
            label,
            resolved_description,
            tooltip,
            shortcuts=shortcuts,
            command_id=command_id,
            command_icon=command_icon,
        )
        return item

    def _on_action_hovered(self, action):
        if action is None or not QtCompat.isValid(action) or isinstance(action, QtWidgets.QWidgetAction):
            QFlatTooltipManager.cancel_timer()
            return
        if action.property("tkm_tooltip_enabled") is False:
            QFlatTooltipManager.cancel_timer()
            return

        source_key = self._action_tooltip_key(action)
        if not source_key:
            return
        if QFlatTooltipManager.is_current_source(source_key):
            return

        try:
            # Retrieve Python-side data to preserve Tooltip objects and shortcut descriptors.
            action_help = self._action_help_store.get(source_key, {})
            title = (
                action_help.get("title")
                or action.property("tkm_title")
                or action.text()
            )
            desc = action_help.get("description")
            if desc is None:
                desc = action.property("tkm_description") or ""
            tooltip = action_help.get("tooltip")
            shortcuts = action_help.get("shortcuts", ())
            command_id = (
                action_help.get("command_id")
                or action.property("tkm_command_id")
                or None
            )
            command_label = (
                action_help.get("command_label")
                or action.property("tkm_command_label")
                or title
            )
            command_icon = (
                action_help.get("command_icon")
                or action.property("tkm_command_icon")
                or None
            )
        except (RuntimeError, ValueError, TypeError, AttributeError, KeyError, IndexError):
            return

        if not (title or desc or tooltip):
            QFlatTooltipManager.cancel_timer()
            return

        if QFlatTooltipManager.enabled:
            if tooltip is not None:
                display_tooltip = tooltip
            elif desc:
                display_tooltip = tuple(desc) if isinstance(desc, (list, tuple)) else (desc,)
            else:
                display_tooltip = ""

            cursor_pos = QtGui.QCursor.pos()
            icon = action.icon() if not action.icon().isNull() else None
            QFlatTooltipManager.delayed_show(
                text=title,
                anchor_widget=self,
                target_rect=self._action_global_rect(action, cursor_pos),
                target_pos=cursor_pos,
                description=desc,
                tooltip=display_tooltip,
                shortcuts=shortcuts,
                icon_obj=icon,
                command_id=command_id,
                command_label=command_label,
                command_icon=command_icon,
                source_key=source_key,
            )

    def hideEvent(self, event):
        QFlatTooltipManager.hide()
        QtWidgets.QMenu.hideEvent(self, event)

    def leaveEvent(self, event):
        QFlatTooltipManager.source_left(anchor_widget=self)
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
    def _clear_tooltip_hover_state(self, anchor_unavailable=False):
        source_key = "widget:{}".format(id(self))
        QFlatTooltipManager.source_left(
            source_key=source_key,
            anchor_widget=self,
            anchor_unavailable=anchor_unavailable,
        )
        if hasattr(self, "_hover"):
            self._hover = False
        if hasattr(self, "_handle_hover"):
            self._handle_hover = False
        try:
            self.update()
        except (RuntimeError, AttributeError):
            pass

    def setData(
        self,
        text="",
        description="",
        shortcuts=None,
        icon=None,
        tooltip=None,
        status_title=None,
        status_description=None,
        command_id=None,
        command_label=None,
        command_icon=None,
    ):
        # Automatically pick up the widget's icon if not provided
        if not icon and hasattr(self, "_icon"):
            icon = self._icon

        self._toolTipData = {
            "text": text,
            "description": description,
            "shortcuts": shortcuts or [],
            "icon": icon,
            "tooltip": tooltip,
            "status_title": status_title,
            "status_description": _status_description(
                description=description,
                status_description=status_description,
                tooltip=tooltip,
            ),
            "command_id": command_id,
            "command_label": command_label,
            "command_icon": command_icon,
        }
        _push_help(self, self._toolTipData)

    def get_toolTipData(self):
        return getattr(self, "_toolTipData", {})

    def get_base_tooltip_data(self):
        """Return stable action help for controls without modifier variants."""
        return dict(self.get_toolTipData())

    def setToolTipData(self, **kwargs):
        self._has_tooltip = True
        self.setData(**kwargs)

    def setTooltipInfo(self, title: str, description: str = "", tooltip=None):
        self.setToolTipData(text=title, description=description, tooltip=tooltip)

    def enterEvent(self, event: QtCore.QEvent):
        # Refresh description and trigger Maya event
        data = getattr(self, "_toolTipData", {})
        _push_help(self, data)

        try:
            super().enterEvent(event)
        except (AttributeError, TypeError):
            pass

        if QFlatTooltipManager.enabled and getattr(self, "_has_tooltip", False):
            if data.get("text") or data.get("description") or data.get("tooltip"):
                source_key = "widget:{}".format(id(self))
                if QFlatTooltipManager.is_current_source(source_key):
                    return
                # Pass the rich tooltip directly to the tooltip manager.
                QFlatTooltipManager.delayed_show(anchor_widget=self, source_key=source_key, **data)

    def leaveEvent(self, event: QtCore.QEvent):
        self._clear_tooltip_hover_state()
        try:
            super().leaveEvent(event)
        except (AttributeError, TypeError):
            pass

    def hideEvent(self, event: QtCore.QEvent):
        self._clear_tooltip_hover_state(anchor_unavailable=True)
        try:
            super().hideEvent(event)
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
    QPushButton:disabled {
        color: %s;
        background-color: %s;
    }
    """

    DEFAULT_COLOR = "#ffffff"
    DEFAULT_BACKGROUND = "#5D5D5D"
    DEFAULT_HOVER_BACKGROUND = "#707070"
    DEFAULT_PRESSED_BACKGROUND = "#252525"
    DEFAULT_DISABLED_COLOR = "#8a8a8a"
    DEFAULT_DISABLED_BACKGROUND = "#444444"

    HIGHLIGHT_COLOR = "#282828"
    HIGHLIGHT_BACKGROUND = "#bdbdbd"
    HIGHLIGHT_HOVER_BACKGROUND = "#cfcfcf"
    HIGHLIGHT_PRESSED_BACKGROUND = "#707070"
    HIGHLIGHT_DISABLED_COLOR = "#d0d0d0"
    HIGHLIGHT_DISABLED_BACKGROUND = "#8a8a8a"

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

        icon_dim = DPI(24) if highlight else DPI(19)
        icon_size = QtCore.QSize(icon_dim, icon_dim)
        self.setIconSize(icon_size)
        v_padding = 2  # Tight padding since height is fixed

        if highlight:
            color = self.HIGHLIGHT_COLOR
            background = self.HIGHLIGHT_BACKGROUND
            hover_background = self.HIGHLIGHT_HOVER_BACKGROUND
            pressed_background = self.HIGHLIGHT_PRESSED_BACKGROUND
            disabled_color = self.HIGHLIGHT_DISABLED_COLOR
            disabled_background = self.HIGHLIGHT_DISABLED_BACKGROUND
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
            disabled_color = self.DEFAULT_DISABLED_COLOR
            disabled_background = self.DEFAULT_DISABLED_BACKGROUND
            font_size = self.DEFAULT_FONT_SIZE
            weight = "normal"
        else:
            hover_background = self.DEFAULT_HOVER_BACKGROUND
            pressed_background = self.DEFAULT_PRESSED_BACKGROUND
            disabled_color = self.DEFAULT_DISABLED_COLOR
            disabled_background = self.DEFAULT_DISABLED_BACKGROUND
            font_size = self.DEFAULT_FONT_SIZE
            weight = "normal"

        if icon:
            self.setIcon(_tinted_icon(icon, color, icon_size) if highlight else QtGui.QIcon(icon))

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
                disabled_color,
                disabled_background,
            )
        )

    def changeEvent(self, event):
        if event.type() == QtCore.QEvent.EnabledChange:
            cursor = QtCore.Qt.PointingHandCursor if self.isEnabled() else QtCore.Qt.ArrowCursor
            self.setCursor(cursor)
        QtWidgets.QPushButton.changeEvent(self, event)


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


def _paste_to_node_leaf(node):
    return str(node or "").split("|")[-1]


def _paste_to_node_namespace(node):
    leaf = _paste_to_node_leaf(node)
    if ":" not in leaf:
        return ""
    return leaf.rsplit(":", 1)[0]


def _paste_to_node_base_name(node):
    return _paste_to_node_leaf(node).rsplit(":", 1)[-1]


def _paste_to_node_with_namespace(base_name, namespace):
    namespace = str(namespace or "").strip().strip(":")
    return f"{namespace}:{base_name}" if namespace else base_name


def _paste_to_scene_namespaces():
    from maya import cmds

    namespaces = set()
    try:
        namespaces.update(cmds.namespaceInfo(listOnlyNamespaces=True, recurse=True) or [])
    except Exception:
        pass
    namespaces.discard("UI")
    namespaces.discard("shared")
    namespaces.discard(":")
    return [""] + sorted(ns.strip(":") for ns in namespaces if ns is not None)


def _paste_to_namespace_display(namespace):
    return namespace or ""


def _paste_to_resolve_node(source_node, namespace):
    from maya import cmds

    candidate = _paste_to_node_with_namespace(_paste_to_node_base_name(source_node), namespace)
    if cmds.objExists(candidate):
        return candidate
    matches = cmds.ls(candidate, long=False) or []
    return matches[0] if matches else None


def _paste_to_asset_key(source_node):
    namespace = _paste_to_node_namespace(source_node)
    return namespace or "<root>"


def _paste_to_asset_display(asset_key):
    return "" if asset_key == "<root>" else asset_key


class PasteToDialog:
    def __init__(self, saved_data, apply_callback, data_label="animation", parent=None):
        from TheKeyMachine.widgets import customDialogs

        self.saved_data = saved_data or {}
        self.apply_callback = apply_callback
        self.data_label = data_label
        self._asset_rows = {}
        self._asset_sources = {}

        title = f"Paste {data_label.title()} To..."
        buttons = []
        if data_label == "animation":
            buttons.append(
                customDialogs.QFlatDialogButton(
                    "Paste Insert Animation",
                    callback=lambda: self._apply(insert=True),
                    icon=icons.paste_insert_animation,
                    highlight=True,
                )
            )
        buttons.extend(
            [
                customDialogs.QFlatDialogButton(
                    f"Paste Replace {data_label.title()}",
                    callback=lambda: self._apply(insert=False),
                    icon=icons.paste_animation if data_label == "animation" else icons.paste_pose,
                    highlight=True,
                ),
                customDialogs.QFlatDialogButton("Close", callback=self.close, icon=icons.close),
            ]
        )

        self.dialog = customDialogs.QFlatDialog(parent=parent, buttons=buttons, closeButton=False)
        self.dialog.setWindowTitle(title)
        self.dialog.addWindowHeader(
            self.dialog.root_layout,
            text=title,
            icon=icons.paste_animation if data_label == "animation" else icons.paste_pose,
        )
        self._build_content()
        self.dialog.setBottomBar(buttons=buttons)
        self.dialog.resize(DPI(590), DPI(390))

    def show(self):
        self.dialog.show()
        self.dialog.raise_()

    def close(self):
        self.dialog.close()

    def _build_content(self):
        content = QtWidgets.QWidget(self.dialog)
        layout = QtWidgets.QVBoxLayout(content)
        layout.setContentsMargins(DPI(10), 0, DPI(10), DPI(10))
        layout.setSpacing(DPI(6))

        self.tree = QtWidgets.QTreeWidget(content)
        self.tree.setObjectName("pasteToAssetsTree")
        self.tree.setColumnCount(3)
        self.tree.setHeaderLabels(["Assets", "Scene Namespace", "Custom Namespace"])
        self.tree.setRootIsDecorated(False)
        self.tree.setUniformRowHeights(True)
        self.tree.setAlternatingRowColors(True)
        self.tree.setAllColumnsShowFocus(True)
        self.tree.setSelectionMode(QtWidgets.QAbstractItemView.ExtendedSelection)
        self.tree.setSelectionBehavior(QtWidgets.QAbstractItemView.SelectRows)
        self.tree.setFocusPolicy(QtCore.Qt.StrongFocus)
        self.tree.header().setStretchLastSection(True)
        self.tree.setStyleSheet(
            """
            QTreeWidget#pasteToAssetsTree {
                background-color: #282828;
                alternate-background-color: #303030;
                border: 1px solid #3b3b3b;
                color: #bdbdbd;
                outline: none;
            }
            QTreeWidget#pasteToAssetsTree::item:selected {
                background-color: #4a4a4a;
                color: #ffffff;
            }
            QTreeWidget#pasteToAssetsTree QLineEdit#pasteToCustomNamespace {
                background-color: #bdbdbd;
                border: none;
                border-radius: 5px;
                color: #202020;
                padding: 2px 7px;
                font-size: 11px;
            }
            QTreeWidget#pasteToAssetsTree QHeaderView::section {
                background-color: #444444;
                color: #c7c7c7;
                border: none;
                padding: 4px;
                font-weight: bold;
            }
            """
        )
        layout.addWidget(self.tree, 1)
        self.dialog.root_layout.addWidget(content)
        self._populate_tree()

    def _populate_tree(self):
        scene_namespaces = _paste_to_scene_namespaces()
        for source_node in sorted((self.saved_data or {}).keys()):
            asset_key = _paste_to_asset_key(source_node)
            self._asset_sources.setdefault(asset_key, []).append(source_node)

        for asset_key in sorted(self._asset_sources.keys(), key=lambda value: _paste_to_asset_display(value).lower()):
            source_namespace = _paste_to_asset_display(asset_key)
            preview_text = self._asset_preview(asset_key, source_namespace)
            item = QtWidgets.QTreeWidgetItem([source_namespace or "<root>", preview_text, ""])
            item.setData(0, QtCore.Qt.UserRole, asset_key)
            self.tree.addTopLevelItem(item)

            combo = QtWidgets.QComboBox(self.tree)
            combo.setObjectName("pasteToNamespaceCombo")
            for scene_namespace in scene_namespaces:
                combo.addItem(_paste_to_namespace_display(scene_namespace), scene_namespace)
            if source_namespace in scene_namespaces:
                combo.setCurrentIndex(scene_namespaces.index(source_namespace))
            elif scene_namespaces:
                combo.setCurrentIndex(0)

            custom = QtWidgets.QLineEdit(self.tree)
            custom.setObjectName("pasteToCustomNamespace")
            custom.textChanged.connect(lambda _text, source=asset_key: self._refresh_asset_preview(source))
            combo.currentIndexChanged.connect(lambda _idx, source=asset_key: self._refresh_asset_preview(source))

            self.tree.setItemWidget(item, 1, combo)
            self.tree.setItemWidget(item, 2, custom)
            self._asset_rows[asset_key] = {"combo": combo, "custom": custom, "item": item}

        QtCore.QTimer.singleShot(0, self._resize_columns)

    def _resize_columns(self):
        viewport_width = max(0, self.tree.viewport().width())
        if viewport_width <= 0:
            return
        first_width = int(viewport_width * 0.25)
        second_width = int(viewport_width * 0.25)
        self.tree.setColumnWidth(0, first_width)
        self.tree.setColumnWidth(1, second_width)
        self.tree.setColumnWidth(2, max(DPI(120), viewport_width - first_width - second_width))

    def _selected_namespace(self, asset_key):
        widgets = self._asset_rows.get(asset_key)
        if not widgets:
            return _paste_to_asset_display(asset_key)
        custom_text = widgets["custom"].text().strip().strip(":")
        if custom_text:
            return custom_text
        combo = widgets["combo"]
        return combo.currentData() if combo.currentIndex() >= 0 else ""

    def _asset_preview(self, asset_key, target_namespace):
        sources = self._asset_sources.get(asset_key) or []
        resolved = 0
        for source_node in sources:
            if _paste_to_resolve_node(source_node, target_namespace):
                resolved += 1
        return f"{resolved}/{len(sources)} controls" if sources else ""

    def _refresh_asset_preview(self, asset_key):
        widgets = self._asset_rows.get(asset_key)
        if not widgets:
            return
        widgets["item"].setText(1, self._asset_preview(asset_key, self._selected_namespace(asset_key)))

    def mappings(self):
        resolved = []
        missing = []
        items = self.tree.selectedItems() or [self.tree.topLevelItem(index) for index in range(self.tree.topLevelItemCount())]
        for item in items:
            asset_key = item.data(0, QtCore.Qt.UserRole)
            target_namespace = self._selected_namespace(asset_key)
            for source_node in self._asset_sources.get(asset_key, []):
                target_node = _paste_to_resolve_node(source_node, target_namespace)
                if target_node:
                    resolved.append((source_node, target_node))
                else:
                    missing.append(_paste_to_node_with_namespace(_paste_to_node_base_name(source_node), target_namespace))
        return resolved, missing

    def _apply(self, insert=False):
        from maya import cmds

        mappings, _missing = self.mappings()
        if not mappings:
            cmds.warning(f"No matching {self.data_label} targets found")
            return
        if self.apply_callback(mappings, insert=insert):
            self.close()


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
        tooltip=None,
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
        self._checked_state_getter = None
        self._checked_state_setter = None

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
        # Small margin inside the fixed button bounds.
        self.setIconSize(QtCore.QSize(w - 2, h - 2))

        self._icon = None
        self._base_state = {key: None for key in TOOLTIP_STATE_KEYS}
        self._base_state.update(
            {
                "text": text,
                "description": description,
                "shortcuts": shortcuts or [],
                "tooltip": tooltip,
                "icon": icon,
            }
        )
        self._icon = icon
        self.setIcon(QtGui.QIcon(icon or ""))
        self.setToolTipData(
            text=text,
            description=description,
            shortcuts=shortcuts,
            tooltip=tooltip,
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

    def configure_check_state(self, *, checkable=None, getter=None, setter=None, changed_signal=None, bind_fn=None, state_key=None):
        if checkable is not None:
            self.setCheckable(bool(checkable))
        self._checked_state_getter = getter if callable(getter) else None
        self._checked_state_setter = setter if callable(setter) else None
        self._tkm_check_binding_owns_trigger = False
        if self.isCheckable():
            initial_state = self.checked_state()
            self.set_checked_safely(initial_state)
            toolCommon.bind_checked_signal(self, changed_signal, self.checked_state, state_key=state_key)
            toolCommon.bind_tool_state_signal(self, state_key)
            toolCommon.publish_control_state(state_key, initial_state)
        if callable(bind_fn):
            try:
                self._tkm_check_binding_owns_trigger = bind_fn(self) is True
            except Exception:
                pass
        return self

    def is_checkable_compat(self):
        try:
            return bool(self.isCheckable())
        except Exception:
            return False

    def checked_state(self):
        if callable(self._checked_state_getter):
            return bool(self._checked_state_getter())
        try:
            return bool(self.isChecked())
        except Exception:
            return False

    def set_checked_safely(self, checked):
        blocked = False
        try:
            blocked = self.blockSignals(True)
        except Exception:
            blocked = False
        try:
            self.setChecked(bool(checked))
            return True
        except Exception:
            return False
        finally:
            try:
                self.blockSignals(blocked)
            except Exception:
                pass

    def set_checked_state(self, checked, *, apply=False):
        if apply and callable(self._checked_state_setter):
            try:
                self._checked_state_setter(bool(checked))
            except TypeError:
                self._checked_state_setter()
            return self.sync_checked_state()
        return self.set_checked_safely(checked)

    def sync_checked_state(self):
        if not self.is_checkable_compat():
            return False
        return self.set_checked_safely(self.checked_state())

    def connect_window_toggle(self, toggle, *, menu_factory=None, context_attr="_tkm_window_toggle_context_menu"):
        return toolCommon.connect_window_toggle_control(
            self,
            toggle,
            menu_factory=menu_factory,
            context_attr=context_attr,
        )

    def configure_from_data(self, data, *, display_text=None):
        state = _tooltip_state_from_data(data, display_text=display_text)
        self.setToolTipData(**state)
        self._has_tooltip = bool(data.get("tooltip_enabled", True))
        if data.get("tint_color") is not None:
            self.set_tint_color(data.get("tint_color"))
        self.setShortcutVariants(data.get("shortcut_variants") or [])
        return self

    def connect_from_data(self, data):
        toolCommon.connect_control_from_data(self, data)
        return self

    def attach_menu(self, setup_fn, *, popup_on_click=False):
        if not callable(setup_fn):
            return self

        self._tkm_menu_factory = setup_fn
        self.setContextMenuPolicy(QtCore.Qt.CustomContextMenu)

        def _show_tool_menu(pos, menu_factory=setup_fn, widget=self):
            menu = OpenMenuWidget(widget)
            try:
                built_menu = menu_factory(menu, source_widget=widget)
            except TypeError:
                built_menu = menu_factory(menu)
            if built_menu is not None and built_menu is not False:
                menu = built_menu
            if menu.actions():
                menu.exec_(widget.mapToGlobal(pos))

        self.customContextMenuRequested.connect(_show_tool_menu)
        if popup_on_click:
            self.clicked.connect(
                lambda _checked=False, widget=self: widget.customContextMenuRequested.emit(widget.mapFromGlobal(QtGui.QCursor.pos()))
            )
        return self

    def setToolTipData(self, **kwargs):
        display_text = kwargs.pop("display_text", None)
        super().setToolTipData(**kwargs)
        if not self._variant_state_lock:
            if display_text is not None:
                self._base_state["text"] = display_text
            elif self._base_state.get("text") is None:
                self._base_state["text"] = kwargs.get("text")
            for key in TOOLTIP_STATE_KEYS:
                if key != "text":
                    self._base_state[key] = kwargs.get(key, self._base_state.get(key))

    def get_base_tooltip_data(self):
        """Return stable base tool identity, not a hovered shortcut variant."""
        return dict(self._base_state)

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
        callback = variant.get("callback") if variant and variant.get("callback") else base_callback
        if variant:
            kwargs.setdefault("_tkm_tool_id", variant.get("id") or variant.get("key"))
            kwargs.setdefault(
                "_tkm_tool_label",
                variant.get("status_title") or variant.get("label") or variant.get("menu_label"),
            )
        return toolCommon.run_tool_callback(self, callback, *args, **kwargs)

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
            tooltip = state.get("tooltip", text)
            description = state.get("description", "")
            shortcuts = state.get("shortcuts", [])
            icon = state.get("icon")
            status_title = state.get("status_title")
            status_description = state.get("status_description")
            self.setText(text or "")
            self._icon = icon
            self.setIcon(QtGui.QIcon(icon or ""))
            TooltipMixin.setToolTipData(
                self,
                text=status_title or text,
                description=description,
                shortcuts=shortcuts,
                tooltip=tooltip,
                icon=icon,
                status_title=status_title,
                status_description=status_description,
                command_id=state.get("command_id"),
                command_label=state.get("command_label"),
                command_icon=state.get("command_icon"),
            )
        finally:
            self._variant_state_lock = False

    def _variant_to_state(self, variant):
        if not variant:
            return dict(self._base_state)
        tooltip = variant.get("tooltip")
        command_label = (
            variant.get("label")
            or variant.get("menu_label")
            or toolCommon.get_tooltip_title(tooltip)
            or variant.get("id")
        )
        return {
            "text": variant.get("text", self._base_state.get("text")),
            "description": variant.get("description", ""),
            "shortcuts": variant.get("shortcuts", []),
            "tooltip": tooltip,
            "icon": variant.get("icon", self._base_state.get("icon")),
            "status_title": (
                variant.get("status_title")
                or variant.get("label")
                or toolCommon.get_tooltip_title(tooltip)
                or self._base_state.get("status_title")
            ),
            "status_description": _status_description(
                description=variant.get("description", ""),
                status_description=variant.get("status_description"),
                tooltip=tooltip,
            ),
            "command_id": variant.get("id", self._base_state.get("command_id")),
            "command_label": command_label,
            "command_icon": variant.get("icon", self._base_state.get("command_icon")),
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
        if data.get("text") or data.get("description") or data.get("tooltip"):
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
    def __init__(self, parent=None, icon=None, tooltip=None, description=None):
        super().__init__(parent=parent, icon=icon, tooltip=tooltip, description=description)
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
    display_text = data.get("text")

    btn = QFlatToolButton(
        parent=parent,
        icon=data.get("icon"),
        text=display_text,
        tooltip=data.get("tooltip"),
        description=data.get("description"),
        shortcuts=data.get("shortcuts"),
        shortcut_variants=data.get("shortcut_variants"),
    )
    btn.configure_from_data(data, display_text=display_text)
    connection_data = dict(data)
    if data.get("type") == "menu" and callable(data.get("menu")):
        connection_data["callback"] = None
    btn.connect_from_data(connection_data)
    btn.attach_menu(data.get("menu"), popup_on_click=data.get("type") == "menu")
    return btn


def _checked_state_fn(data):
    return toolCommon.checked_state_getter(data)


def _setup_setting_synced_checkable(control, data):
    checkable = bool(data.get("checkable", data.get("type") in {"check", "setting"}))
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

    heightChanged = QtCore.Signal(int)

    def sizeHint(self):
        lay = self.layout()
        if lay is None:
            return super().sizeHint()
        width = max(1, self.width())
        height = lay.heightForWidth(width) if lay.hasHeightForWidth() else lay.sizeHint().height()
        return QtCore.QSize(lay.sizeHint().width(), max(0, height))

    def minimumSizeHint(self):
        # Do not feed the previous setFixedHeight() back into Maya's dock
        # layout. The flow layout is the sole source of the current height.
        return QtCore.QSize(0, 0)

    def resizeEvent(self, event):
        super().resizeEvent(event)
        self._update_height()

    def _update_height(self):
        lay = self.layout()
        if lay is not None and lay.hasHeightForWidth():
            lay.invalidate()
            lay.activate()
            new_h = lay.heightForWidth(max(1, self.contentsRect().width()))
            if new_h > 0 and self.height() != new_h:
                self.setFixedHeight(new_h)
                self.updateGeometry()
                self.heightChanged.emit(new_h)


class QFlatToolbar(QFlowContainer):
    """
    A unified, reusable toolbar widget that uses QFlowLayout to contain
    multiple QFlatSectionWidgets and dynamically updates its height.
    """

    def __init__(
        self,
        parent=None,
        settings_namespace=None,
        margin=2,
        vertical_margin=6,
        spacing_w=10,
        spacing_h=6,
        alignment=None,
    ):
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
        layout.setContentsMargins(
            margin,
            DPI(vertical_margin),
            margin,
            DPI(vertical_margin),
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

    pinsChanged = QtCore.Signal()
    ENTRY_ANIMATION_MS = 140

    def __init__(self, parent=None, spacing=0, hiddeable=True, settings_namespace=None, color=None):
        super().__init__(parent)
        self.setLayout(QtWidgets.QHBoxLayout())
        # Vertical padding belongs to QFlatToolbar's flow layout. Keeping it
        # here as well creates a second, harder-to-reason-about margin layer.
        self.layout().setContentsMargins(0, 0, 0, 0)
        self.layout().setSpacing(spacing)
        self._hiddeable = hiddeable
        self._settings_namespace = settings_namespace
        self._tint_color = color

        self._widgets = {}  # slot_key -> widget mapping
        self._menu_metadata = []  # for non-slider sections (toolbar buttons etc.)
        self._default_keys = []
        self._entry_animation = None
        self._entry_animation_state = None
        self._entry_animations_enabled = False
        self._layout_refresh_pending = False
        self._pending_shared_pin_states = {}
        self._shared_pin_flush_pending = False

        try:
            runtime.get_runtime_manager().controlStateChanged.connect(self._on_shared_control_state_changed)
        except Exception:
            pass

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

    def enable_entry_animations(self):
        """Animate controls added or revealed after initial toolbar population."""
        self._entry_animations_enabled = True

    def _restore_entry_constraints(self, state):
        if not QtCompat.isValid(self):
            return
        self.setMaximumWidth(state["maximum_width"])
        self.setMinimumWidth(state["minimum_width"])

    def _cancel_entry_animation(self):
        state = self._entry_animation_state
        if not state:
            return
        animation = self._entry_animation
        self._entry_animation = None
        self._entry_animation_state = None
        if animation is not None:
            animation.stop()
            animation.deleteLater()
        self._restore_entry_constraints(state)

    def _animate_widget_in(self, widget, start_width=None):
        if widget is None or not QtCompat.isValid(widget):
            return
        if start_width is None:
            start_width = self.width() if self.isVisible() else 0
        self._cancel_entry_animation()
        state = {
            "minimum_width": self.minimumWidth(),
            "maximum_width": self.maximumWidth(),
        }

        # Keep the new control at its final size and reveal it by expanding the
        # clipped section viewport around the already-laid-out contents.
        widget.show()
        self.show()
        layout = self.layout()
        if layout is not None:
            layout.invalidate()
            layout.activate()
        target_width = max(start_width, self.sizeHint().width(), 1)
        if start_width >= target_width:
            self._restore_entry_constraints(state)
            self._refresh_layout()
            return

        width_animation = QtCore.QPropertyAnimation(self, b"maximumWidth", self)
        width_animation.setDuration(self.ENTRY_ANIMATION_MS)
        width_animation.setStartValue(max(0, start_width))
        width_animation.setEndValue(target_width)
        width_animation.setEasingCurve(QtCore.QEasingCurve.OutCubic)
        width_animation.valueChanged.connect(lambda _value: self._refresh_layout())

        self._entry_animation = width_animation
        self._entry_animation_state = state
        self.setMinimumWidth(0)
        self.setMaximumWidth(max(0, start_width))

        def _finish(animation=width_animation, animation_state=state):
            if self._entry_animation is not animation:
                return
            self._entry_animation = None
            self._entry_animation_state = None
            self._restore_entry_constraints(animation_state)
            animation.deleteLater()
            self._refresh_layout()

        width_animation.finished.connect(_finish)
        width_animation.start()

    def _set_widget_visibility(self, widget, visible, animate=False):
        if widget is None or not QtCompat.isValid(widget):
            return
        visible = bool(visible)
        if not visible:
            self._cancel_entry_animation()
            widget.hide()
            return
        if animate and self._entry_animations_enabled:
            self._animate_widget_in(widget)
        else:
            self._cancel_entry_animation()
            widget.show()

    def set_menu_identity(self, label=None, icon=None):
        self._menu_label = label
        self._menu_icon = icon

    def menu_label(self):
        return getattr(self, "_menu_label", None) or self.objectName() or "Tools"

    def menu_icon(self):
        return getattr(self, "_menu_icon", None)

    def has_pinnable_items(self):
        return bool(self._hiddeable and self._menu_metadata)

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

    def set_tint_color(self, color):
        self._tint_color = color

    def get_tint_color(self):
        return self._tint_color

    def _get_setting(self, key, default_value=None):
        return settings.get_setting(key, default_value, namespace=self._settings_namespace)

    def _set_setting(self, key, value):
        settings.set_setting(key, value, namespace=self._settings_namespace)

    def _shared_namespace(self):
        return str(self._settings_namespace or self.objectName() or id(self))

    def _pin_state_key(self, widget_key):
        return "section_pin:{}:{}".format(self._shared_namespace(), widget_key)

    def _on_shared_control_state_changed(self, state_key, value):
        pin_prefix = "section_pin:{}:".format(self._shared_namespace())
        if state_key.startswith(pin_prefix):
            widget_key = state_key[len(pin_prefix):]
            if widget_key in self._widgets:
                desired_visible = bool(value)
                if self._is_pin_key_checked(widget_key) == desired_visible:
                    return
                self._pending_shared_pin_states[widget_key] = desired_visible
                if not self._shared_pin_flush_pending:
                    self._shared_pin_flush_pending = True
                    QtCore.QTimer.singleShot(0, self._flush_shared_pin_states)

    def _flush_shared_pin_states(self):
        self._shared_pin_flush_pending = False
        states = self._pending_shared_pin_states
        self._pending_shared_pin_states = {}
        if states and QtCompat.isValid(self):
            self._apply_widget_pin_states(states, publish=False)

    @staticmethod
    def _widget_help_data(widget):
        """Read stable tool identity without coupling sections to toolbox descriptors."""
        getter = getattr(widget, "get_base_tooltip_data", None)
        if not callable(getter):
            getter = getattr(widget, "get_toolTipData", None)
        if not callable(getter):
            return {}
        try:
            return dict(getter() or {})
        except (RuntimeError, ValueError, TypeError, AttributeError, KeyError, IndexError):
            return {}

    def addWidget(
        self,
        widget,
        label,
        key,
        default=True,
        description=None,
        tooltip=None,
        tooltip_enabled=True,
        pinnable=True,
        icon=None,
        command_icon=None,
    ):
        """Add a widget to the section with a toggle key."""
        widget_help = self._widget_help_data(widget)

        # Auto-extract help metadata from widget if not provided
        if not tooltip or not description:
            tooltip = tooltip or widget_help.get("tooltip") or widget_help.get("text")
            description = description or widget_help.get("description")

        self.layout().addWidget(widget)
        self._widgets[key] = widget

        # Propagate section context to widget
        from TheKeyMachine.widgets.util import is_valid_widget

        if is_valid_widget(widget) and hasattr(widget, "on_added_to_section"):
            widget.on_added_to_section(self, key)

        # If the widget is a mode-aware slider, restore its saved mode assignment
        if is_valid_widget(widget) and hasattr(widget, "_current_mode"):
            cm = getattr(widget, "_current_mode", None)
            if cm is not None:
                widget._tkm_default_mode_key = cm.key
            if hasattr(widget, "currentModeChanged"):
                with warnings.catch_warnings():
                    warnings.simplefilter("ignore", RuntimeWarning)
                    try:
                        widget.currentModeChanged.disconnect(self._on_slider_current_mode_changed)
                    except (RuntimeError, TypeError):
                        pass
                widget.currentModeChanged.connect(self._on_slider_current_mode_changed)

            if cm:
                saved_mode_key = self._get_setting(f"slider_mode_{key}", cm.key)
                if saved_mode_key != cm.key and hasattr(widget, "setCurrentMode"):
                    widget.setCurrentMode(saved_mode_key)

        if self._hiddeable:
            if pinnable is not False:
                # Avoid duplicate metadata entries for the same key
                menu_metadata = {
                    "label": label,
                    "description": description,
                    "tooltip": tooltip,
                    "icon": icon,
                    "command_icon": command_icon or icon,
                    "tooltip_enabled": tooltip_enabled,
                    "default": default,
                    "stable_help": hasattr(widget, "_tkm_default_mode_key"),
                    "mode_key": getattr(widget, "_tkm_default_mode_key", None),
                }
                existing_entry = next((m for m in self._menu_metadata if m.get("id") == key), None)
                if existing_entry:
                    existing_entry.update(menu_metadata)
                else:
                    menu_metadata.update({"type": "widget", "id": key})
                    self._menu_metadata.append(menu_metadata)
                visible = self._get_setting(f"pin_{key}", default)
            else:
                visible = default
            manager = runtime.get_runtime_manager()
            state_key = self._pin_state_key(key)
            if manager.has_control_state(state_key):
                visible = bool(manager.get_control_state(state_key))
            else:
                manager.set_control_state(state_key, bool(visible))
            self._set_widget_visibility(widget, visible, animate=bool(visible))
            self._sync_section_visibility()
        else:
            self._set_widget_visibility(widget, bool(default))

        if hasattr(widget, "setToolTipData"):
            d = description
            tt = tooltip
            existing = getattr(widget, "_toolTipData", {}) if hasattr(widget, "_toolTipData") else {}
            if not d and not tt and hasattr(widget, "_toolTipData"):
                d = existing.get("description")
                tt = existing.get("tooltip")
            status_description = existing.get("status_description")
            if status_description is None:
                status_description = _status_description(
                    description=d or "",
                    tooltip=tt,
                )

            widget.setToolTipData(
                text=label,
                description=d or "",
                shortcuts=existing.get("shortcuts", []),
                tooltip=tt,
                icon=existing.get("icon"),
                status_title=existing.get("status_title") or label,
                status_description=status_description,
                command_id=existing.get("command_id"),
                command_label=existing.get("command_label") or label,
                command_icon=existing.get("command_icon") or existing.get("icon"),
            )
            widget._has_tooltip = bool(tooltip_enabled)
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
                tooltip=default_item.get("tooltip"),
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
                tooltip=default_item.get("tooltip"),
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
                    full_tooltip = item.get("tooltip")
                    full_desc = item.get("description") or ""

                    if checkable:
                        action = menu.addAction(QtGui.QIcon(act_icon_p), display_label, tooltip=full_tooltip, description=full_desc)
                        _setup_setting_synced_checkable(action, item)
                    else:
                        if cb:
                            menu.addAction(QtGui.QIcon(act_icon_p), display_label, cb, tooltip=full_tooltip, description=full_desc)
                        else:
                            menu.addAction(QtGui.QIcon(act_icon_p), display_label, tooltip=full_tooltip, description=full_desc)

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

    def _apply_widget_pin(self, key, visible, save_setting=True, publish=True):
        """Apply a local pin state to a widget."""
        self._apply_widget_pin_states(
            {key: bool(visible)},
            save_setting=save_setting,
            publish=publish,
        )

    def _apply_widget_pin_states(
        self,
        states,
        save_setting=True,
        publish=True,
        menu=None,
        additional_settings=None,
    ):
        """Apply a set of pin states as one visibility and layout transaction.

        Every pin key -- slider or toolbutton -- maps to exactly one widget
        slot and only ever touches that slot's visibility. A slider's mode
        (what it currently displays) is a separate concern handled via
        right-click / _on_slider_current_mode_changed, not here.
        """
        start_width = self.width() if self.isVisible() else 0
        self._cancel_entry_animation()
        reveal_widget = None
        applied_states = {}

        for key, visible in states.items():
            widget = self._widgets.get(key)
            if widget is None or not QtCompat.isValid(widget):
                continue
            visible = bool(visible)
            if visible and widget.isHidden() and reveal_widget is None:
                reveal_widget = widget
            widget.setVisible(visible)
            applied_states[key] = visible
        setting_values = dict(additional_settings or {})
        if save_setting:
            setting_values.update({f"pin_{key}": visible for key, visible in applied_states.items()})
        if setting_values:
            settings.set_settings(
                setting_values,
                namespace=self._settings_namespace,
            )

        self._sync_section_visibility()
        if reveal_widget is not None and self._entry_animations_enabled:
            self._animate_widget_in(reveal_widget, start_width=start_width)

        if publish:
            for key, visible in applied_states.items():
                toolCommon.publish_control_state(self._pin_state_key(key), visible)

        self._sync_pin_menu_actions(menu)
        self.pinsChanged.emit()
        self._refresh_layout()

    def removeWidgetByKey(self, key):
        """Remove a dynamically discovered toolbar item without altering its pin setting."""
        widget = self._widgets.pop(key, None)
        if widget is None:
            return False
        self._cancel_entry_animation()
        self.layout().removeWidget(widget)
        self._menu_metadata = [item for item in self._menu_metadata if item.get("id") != key]
        self._default_keys = [item_key for item_key in self._default_keys if item_key != key]
        widget.setParent(None)
        widget.deleteLater()
        self._sync_section_visibility()
        return True

    def addSeparator(self):
        """Add a separator to the customization menu."""
        if self._hiddeable:
            self._menu_metadata.append({"type": "separator"})

    def _on_slider_current_mode_changed(self, widget, old_key, new_key):
        """Persist which mode a slot displays. Does not touch any pin/visibility state.

        A slot's pin key always means "is this slot's widget visible" -- the
        same as a toolbutton. Switching what content a visible slot shows
        (via right-click) is an orthogonal, per-slot preference, so it must
        never flip another slot's pin setting.
        """
        slot_key = next((k for k, v in self._widgets.items() if v is widget), None)
        if not slot_key:
            return
        if new_key:
            self._set_setting(f"slider_mode_{slot_key}", new_key)

        if QtCompat.isValid(widget):
            widget.updateGeometry()
            widget.update()
        layout = self.layout()
        if layout is not None:
            layout.invalidate()
        self._sync_section_visibility()
        self.pinsChanged.emit()
        self._refresh_layout()

    def pin_widget_defaults(self, menu=None):
        """Restore original slider modes and widget visibility defaults."""
        mode_settings = {}
        for key, widget in self._widgets.items():
            default_mode_key = getattr(widget, "_tkm_default_mode_key", None)
            if not default_mode_key or not hasattr(widget, "setCurrentMode"):
                continue
            blocked = widget.blockSignals(True)
            try:
                widget.setCurrentMode(default_mode_key)
            finally:
                widget.blockSignals(blocked)
            mode_settings[f"slider_mode_{key}"] = default_mode_key

        states = {
            item["id"]: bool(item.get("default", True))
            for item in self._menu_metadata
            if item.get("type") == "widget" and item.get("id")
        }
        self._apply_widget_pin_states(states, menu=menu, additional_settings=mode_settings)

    def pin_widget_all(self, menu=None):
        """Show every pinnable widget without changing slider modes."""
        states = {
            item["id"]: True
            for item in self._menu_metadata
            if item.get("type") == "widget" and item.get("id")
        }
        self._apply_widget_pin_states(states, menu=menu)

    def _make_toggle_handler(self, key):
        """Create a local pin handler that captures 'key'."""

        def handler(checked):
            self._apply_widget_pin(key, bool(checked))

        return handler

    def _visible_slider_mode_keys(self):
        """Modes currently shown by some *visible* slot in this section.

        Used only to warn a slot's own mode-select menu (sliderWidget.py)
        that a candidate mode is already being displayed elsewhere, so a
        user doesn't end up with two visible slots showing the same content.
        Not used for pin-menu checked state -- see _is_pin_key_checked.
        """
        modes = set()
        for widget in self._widgets.values():
            if not QtCompat.isValid(widget) or widget.isHidden() or not hasattr(widget, "_current_mode"):
                continue
            current_mode = getattr(widget, "_current_mode", None)
            if current_mode:
                modes.add(current_mode.key)
        return modes

    def _is_pin_key_checked(self, key):
        """A pin key is checked iff its own widget slot is visible.

        Sliders are pinned exactly like toolbuttons: one key, one widget,
        one visibility flag. Which mode a visible slider slot is currently
        displaying (changeable via right-click) never factors in here.
        """
        widget = self._widgets.get(key)
        return bool(widget and QtCompat.isValid(widget) and not widget.isHidden())

    @staticmethod
    def _force_menu_repaint(menu):
        """Force a QMenu to redraw its actions' current checked state.

        QMenu does not reliably repaint a checkable action's indicator when
        the action is checked/unchecked programmatically (as opposed to by a
        direct user click) while the menu stays open. This is most visible
        for a cascaded submenu the user is actively looking at -- e.g. right
        after "Pin All"/"Pin Defaults" is clicked with the section flyout
        still open. A plain update()/repaint() is sometimes a no-op because
        Qt doesn't consider anything dirty; toggling updatesEnabled forces a
        real invalidate first.
        """
        if menu is None or not QtCompat.isValid(menu):
            return
        menu.setUpdatesEnabled(False)
        menu.setUpdatesEnabled(True)
        menu.update()
        menu.repaint()

    def _bind_pin_menu_action(self, menu, action, key, checked):
        def sync_action(action=action, menu=menu, section=self, widget_key=key):
            if not QtCompat.isValid(action):
                return
            checked_now = section._is_pin_key_checked(widget_key)
            blocked = action.blockSignals(True)
            try:
                action.setChecked(checked_now)
            finally:
                action.blockSignals(blocked)
            section._force_menu_repaint(menu)

        try:
            toolCommon.replace_tracked_connection(
                action,
                "_tkm_pin_action_sync",
                self.pinsChanged,
                sync_action,
                parent=action,
            )
        except (RuntimeError, ValueError, TypeError, AttributeError, KeyError, IndexError):
            pass
        sync_action()
        return action

    def _sync_pin_menu_actions(self, menu):
        """Refresh every checkmark in an already-open section pin menu."""
        if menu is None or not QtCompat.isValid(menu):
            return
        for key, action in getattr(menu, "_tkm_actions", {}).items():
            if action is None or not QtCompat.isValid(action):
                continue
            checked = self._is_pin_key_checked(key)
            blocked = action.blockSignals(True)
            try:
                action.setChecked(checked)
            finally:
                action.blockSignals(blocked)
        self._force_menu_repaint(menu)

    def _refresh_layout(self):
        """Trigger a height recalculation."""
        if not QtCompat.isValid(self) or self._layout_refresh_pending:
            return
        self._layout_refresh_pending = True

        def _apply_refresh(section=self):
            if not QtCompat.isValid(section):
                return
            section._layout_refresh_pending = False
            section.updateGeometry()
            parent = section.parent()
            while parent:
                layout = parent.layout() if hasattr(parent, "layout") else None
                if layout is not None:
                    layout.invalidate()
                if hasattr(parent, "_update_height"):
                    parent._update_height()
                    break
                parent = parent.parent()

        QtCore.QTimer.singleShot(0, _apply_refresh)

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
        tooltip=None,
        tooltip_enabled=True,
        shortcuts=None,
        command_id=None,
        command_icon=None,
    ):
        menu_icon = icon if isinstance(icon, QtGui.QIcon) else QtGui.QIcon(icon or "")
        action_kwargs = {
            "description": description,
            "tooltip": tooltip,
            "tooltip_enabled": tooltip_enabled,
            "shortcuts": shortcuts,
            "label": title,
            "command_id": command_id,
            "command_icon": command_icon,
        }
        if not menu_icon.isNull():
            action = menu.addAction(
                menu_icon,
                label,
                **action_kwargs,
            )
        else:
            action = menu.addAction(
                label,
                **action_kwargs,
            )
        action.setCheckable(True)
        action.setChecked(bool(checked))
        action.triggered.connect(handler)
        menu._tkm_actions[key] = action
        return action

    def _populate_menu(self, menu):
        menu._tkm_actions = {}
        for item in self._menu_metadata:
            if item["type"] == "separator":
                menu.addSeparator()
            elif item["type"] == "widget":
                key = item["id"]
                widget = self._widgets.get(key)
                if widget is None or not QtCompat.isValid(widget):
                    continue
                action_help = dict(item)
                if not item.get("stable_help"):
                    widget_help = self._widget_help_data(widget)
                    for field in (
                        "description", "tooltip", "shortcuts", "icon", "command_id", "command_icon",
                    ):
                        if field in widget_help and widget_help[field] is not None:
                            action_help[field] = widget_help[field]
                action = self._add_checkable_menu_action(
                    menu, key, item["label"], self._is_pin_key_checked(key), self._make_toggle_handler(key),
                    description=action_help.get("description") or "",
                    title=item["label"], tooltip=action_help.get("tooltip"),
                    tooltip_enabled=item.get("tooltip_enabled", True),
                    shortcuts=action_help.get("shortcuts"), icon=action_help.get("icon"),
                    command_id=action_help.get("command_id"),
                    command_icon=action_help.get("command_icon") or action_help.get("icon"),
                )
                self._bind_pin_menu_action(menu, action, key, self._is_pin_key_checked(key))
        menu.addSeparator()
        pin_def_action = menu.addAction(QtGui.QIcon(icons.dot_round), "Pin Defaults", open=True)
        pin_def_action.triggered.connect(lambda: self.pin_widget_defaults(menu=menu))
        pin_all_action = menu.addAction(QtGui.QIcon(icons.dot_round), "Pin All", open=True)
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


class QFlatTabBarPainter(QtWidgets.QWidget):
    """Paint the shelf texture over the native tab bar only."""

    def __init__(self, tab_bar, background_source=None):
        super().__init__(tab_bar)
        self._tab_bar = tab_bar
        self._background_source = background_source or tab_bar
        # Maya owns the surrounding QTabWidget and may delete it while a paint
        # event for this child is still queued.  Do not dereference that wrapper
        # from paintEvent: PySide raises if its underlying C++ object is gone.
        self._background_color = self._resolve_background_color()
        self.setAttribute(QtCore.Qt.WA_TransparentForMouseEvents, True)
        self.setFocusPolicy(QtCore.Qt.NoFocus)
        tab_bar.installEventFilter(self)
        self.setGeometry(tab_bar.rect())
        self.show()
        self.raise_()

    def _resolve_background_color(self):
        source = self._background_source
        if source is not None and QtCompat.isValid(source):
            try:
                return QtGui.QColor(
                    source.palette().color(source.backgroundRole())
                )
            except RuntimeError:
                pass
        return QtGui.QColor(self.palette().color(self.backgroundRole()))

    def syncGeometry(self):
        """Keep compatibility with the toolbar's existing resize callback."""
        if self._tab_bar and QtCompat.isValid(self._tab_bar):
            self.setGeometry(self._tab_bar.rect())
            self.raise_()
            self.update()

    def eventFilter(self, watched, event):
        if watched is self._tab_bar and event.type() in (
            QtCore.QEvent.Resize,
            QtCore.QEvent.Show,
            QtCore.QEvent.LayoutRequest,
        ):
            self.setGeometry(self._tab_bar.rect())
            self.raise_()
            self.update()
        return super().eventFilter(watched, event)

    def paintEvent(self, event):
        painter = QtGui.QPainter(self)
        painter.fillRect(self.rect(), self._background_color)

        pen = QtGui.QPen(QtGui.QColor(130, 130, 130))
        pen.setWidth(max(1, DPI(1)))
        pen.setCapStyle(QtCore.Qt.RoundCap)
        painter.setPen(pen)

        center = DPI(5) - 1
        offset = DPI(1.5)
        top = 0.0
        bottom = float(self.height() - 1)
        dot_count = max(2, int(bottom // max(1, DPI(3))) + 1)
        spacing = bottom / float(dot_count - 1)
        for index in range(dot_count):
            y = top + spacing * index
            painter.drawPoint(QtCore.QPointF(center - offset, y))
            painter.drawPoint(QtCore.QPointF(center + offset, y))
