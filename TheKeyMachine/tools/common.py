from functools import lru_cache

import maya.cmds as cmds  # type: ignore

try:
    from PySide2 import QtCore, QtGui  # type: ignore
except ImportError:
    from PySide6 import QtCore, QtGui  # type: ignore

from TheKeyMachine.widgets import util as wutil
from TheKeyMachine.mods import settingsMod as settings


UNDO_PREFIX = "TKM"

def _split_lines(raw):
    return str(raw or "").replace("\r\n", "\n").replace("\r", "\n").split("\n")


def _first_sentence(text):
    value = clean_tool_text(text)
    if not value:
        return ""
    for index, char in enumerate(value):
        if char in ".!?":
            return value[: index + 1].strip()
    return value


def _humanize_compound_word(raw):
    text = str(raw or "").replace("_", " ").replace("-", " ")
    result = []
    prev = ""
    for char in text:
        if prev and prev.isalnum() and char.isupper() and not prev.isupper():
            result.append(" ")
        result.append(char)
        prev = char
    return "".join(result)


def _tooltip_parts(raw):
    if not raw:
        return "", ""

    if hasattr(raw, "title") or hasattr(raw, "body_lines"):
        return clean_tool_text(getattr(raw, "title", "")), clean_tool_text(getattr(raw, "first_line", ""))

    if isinstance(raw, (list, tuple)):
        title = clean_tool_text(raw[0] if len(raw) > 0 else "")
        body = raw[1] if len(raw) > 1 else ""
        body_lines = body if isinstance(body, (list, tuple)) else [body]
        for line in body_lines:
            if not isinstance(line, str):
                continue
            clean_line = clean_tool_text(line)
            if clean_line:
                return title, clean_line
        return title, ""

    return "", ""


def clean_tool_text(raw):
    if not raw:
        return ""
    return " ".join(str(raw).split()).strip()


def humanize_tool_name(raw):
    if not raw:
        return ""
    value = _humanize_compound_word(raw)
    return clean_tool_text(value).title()


def get_tool_summary(raw):
    if not raw:
        return ""

    _, tooltip_summary = _tooltip_parts(raw)
    if tooltip_summary:
        return _first_sentence(tooltip_summary)

    parts = [clean_tool_text(part) for part in _split_lines(raw)]
    first_line = next((part for part in parts if part), "")
    if not first_line:
        return ""
    return _first_sentence(first_line)


def get_tooltip_title(raw):
    if not raw:
        return ""
    title, _ = _tooltip_parts(raw)
    return title


def get_tooltip_summary(raw):
    if not raw:
        return ""
    _, summary = _tooltip_parts(raw)
    if summary:
        return summary
    return get_tool_summary(raw)


def resolve_status_metadata(title="", description="", tooltip_template=None, status_title=None, status_description=None, fallback_title=""):
    resolved_title = clean_tool_text(
        status_title or title or get_tooltip_title(tooltip_template) or fallback_title
    )
    resolved_description = status_description
    if resolved_description is None:
        resolved_description = get_tooltip_summary(tooltip_template) or description or ""
    return resolved_title, resolved_description


def format_tool_label(title, description="", prefix=UNDO_PREFIX):
    clean_title = clean_tool_text(title) or "Tool"
    clean_desc = get_tool_summary(description)
    label = clean_title if not clean_desc else f"{clean_title} - {clean_desc}"
    if prefix:
        return f"{prefix}: {label}"
    return label


@lru_cache(maxsize=256)
def _get_tool_definition(tool_id):
    if not tool_id:
        return None
    try:
        import TheKeyMachine.core.toolbox as toolbox

        return toolbox.get_tool(tool_id)
    except Exception:
        return None


def resolve_undo_metadata(tool_id=None, title=None, description="", tooltip_template=None):
    resolved_title = title or ""
    resolved_description = description or ""

    tool = _get_tool_definition(tool_id)
    if tool:
        resolved_title = (
            tool.get("status_title")
            or tool.get("label")
            or tool.get("text")
            or resolved_title
        )
        resolved_description = (
            tool.get("status_description")
            or tool.get("description")
            or resolved_description
        )
        tooltip_template = tool.get("tooltip_template") or tooltip_template

    if tooltip_template:
        resolved_title, resolved_description = resolve_status_metadata(
            title=resolved_title,
            description=resolved_description,
            tooltip_template=tooltip_template,
            status_title=resolved_title or None,
            status_description=resolved_description or None,
            fallback_title=tool_id or "tool",
        )

    resolved_title = resolved_title or humanize_tool_name(tool_id or "tool")
    return resolved_title, resolved_description


def make_undo_chunk_name(tool_id=None, title=None, description="", tooltip_template=None):
    resolved_title, resolved_description = resolve_undo_metadata(
        tool_id=tool_id,
        title=title,
        description=description,
        tooltip_template=tooltip_template,
    )
    return format_tool_label(resolved_title, resolved_description)


def open_undo_chunk(tool_id=None, title=None, description="", tooltip_template=None):
    return open_named_undo_chunk(
        make_undo_chunk_name(
            tool_id=tool_id,
            title=title,
            description=description,
            tooltip_template=tooltip_template,
        )
    )


def open_named_undo_chunk(chunk_name):
    try:
        cmds.undoInfo(openChunk=True, chunkName=chunk_name)
        return True
    except Exception:
        return False


def close_undo_chunk(chunk_opened=True):
    if not chunk_opened:
        return
    try:
        cmds.undoInfo(closeChunk=True)
    except Exception:
        pass


class _SignalRelay(QtCore.QObject):
    def __init__(self, callback, parent=None):
        super().__init__(parent)
        self._callback = callback

    def trigger(self, *args):
        if self._callback is None:
            return
        self._callback(*args)


def safe_signal_connect(signal, slot):
    try:
        signal.connect(slot)
        return True
    except Exception:
        return False


def clear_tracked_connection(owner, attr_name):
    relay = getattr(owner, attr_name, None)
    if relay is None:
        return False
    setattr(owner, attr_name, None)
    try:
        relay.deleteLater()
    except Exception:
        pass
    return True


def replace_tracked_connection(owner, attr_name, signal, callback, parent=None):
    clear_tracked_connection(owner, attr_name)
    relay = _SignalRelay(callback, parent=parent)
    if not safe_signal_connect(signal, relay.trigger):
        try:
            relay.deleteLater()
        except Exception:
            pass
        return None
    setattr(owner, attr_name, relay)
    return relay


def clear_tracked_connections(owner, attr_name):
    relays = getattr(owner, attr_name, None)
    if not relays:
        setattr(owner, attr_name, [])
        return False
    setattr(owner, attr_name, [])
    for relay in relays:
        try:
            relay.deleteLater()
        except Exception:
            pass
    return True


def replace_tracked_connections(owner, attr_name, pairs, parent=None):
    clear_tracked_connections(owner, attr_name)
    relays = []
    for signal, callback in pairs:
        relay = _SignalRelay(callback, parent=parent)
        if safe_signal_connect(signal, relay.trigger):
            relays.append(relay)
        else:
            try:
                relay.deleteLater()
            except Exception:
                pass
    setattr(owner, attr_name, relays)
    return relays


class ToolbarWindowToggle(QtCore.QObject):
    """Keeps a toolbar button in sync with a floating window."""

    def __init__(self, is_open_fn, open_fn, close_fn, state_signal=None, parent=None):
        super().__init__(parent)
        self._button = None
        self._syncing = False
        self._button_toggled_relay = None
        self._button_destroyed_relay = None
        self._is_open_fn = is_open_fn
        self._open_fn = open_fn
        self._close_fn = close_fn
        if state_signal is not None:
            state_signal.connect(self._on_window_state_changed)

    def attach_button(self, button):
        if not button:
            return
        if self._button and self._button is not button:
            self._disconnect_button(self._button)
        self._button = button
        self._button.setCheckable(True)
        self._syncing = True
        try:
            self._button.setChecked(bool(self._is_open_fn()))
        finally:
            self._syncing = False
        self._disconnect_button(self._button)
        self._button_toggled_relay = replace_tracked_connection(
            self,
            "_button_toggled_relay",
            self._button.toggled,
            self._on_button_toggled,
            parent=self._button,
        )
        self._button_destroyed_relay = replace_tracked_connection(
            self,
            "_button_destroyed_relay",
            self._button.destroyed,
            self._on_button_destroyed,
            parent=self._button,
        )

    def _set_button_checked(self, checked):
        if not self._button:
            return
        self._syncing = True
        try:
            self._button.setChecked(bool(checked))
        finally:
            self._syncing = False

    def _reconcile_button_state(self):
        if not self._button:
            return
        try:
            is_open = bool(self._is_open_fn())
        except Exception:
            return
        self._set_button_checked(is_open)

    def _on_button_toggled(self, checked):
        if self._syncing:
            return
        import TheKeyMachine.mods.reportMod as report

        if checked:
            report.safe_execute(self._open_fn, context="toolbar window toggle open")
        else:
            report.safe_execute(self._close_fn, context="toolbar window toggle close")
        self._reconcile_button_state()

    def _on_button_destroyed(self, *_):
        if not self._button:
            return
        self._disconnect_button(self._button)
        self._button = None

    def _disconnect_button(self, button):
        if not button:
            return
        clear_tracked_connection(self, "_button_toggled_relay")
        clear_tracked_connection(self, "_button_destroyed_relay")

    def open(self):
        import TheKeyMachine.mods.reportMod as report

        if not self._is_open_fn():
            result = report.safe_execute(self._open_fn, context="toolbar window toggle open")
            self._reconcile_button_state()
            return result

    def close(self):
        import TheKeyMachine.mods.reportMod as report

        if self._is_open_fn():
            result = report.safe_execute(self._close_fn, context="toolbar window toggle close")
            self._reconcile_button_state()
            return result

    def toggle(self):
        import TheKeyMachine.mods.reportMod as report

        if self._is_open_fn():
            result = report.safe_execute(self._close_fn, context="toolbar window toggle close")
        else:
            result = report.safe_execute(self._open_fn, context="toolbar window toggle open")
        self._reconcile_button_state()
        return result

    def _on_window_state_changed(self, is_open):
        if not self._button:
            return
        self._syncing = True
        try:
            self._button.setChecked(bool(is_open))
        finally:
            self._syncing = False


class FloatingToolWindowMixin:
    def _current_screen_geometry(self):
        if not wutil.is_valid_widget(self):
            return None
        frame_geo = self.frameGeometry()
        anchor = frame_geo.center() if frame_geo.isValid() else QtGui.QCursor.pos()
        screen = QtGui.QGuiApplication.screenAt(anchor) or QtGui.QGuiApplication.primaryScreen()
        if not screen:
            return None
        return screen.availableGeometry()

    def clamp_to_current_screen(self):
        if not wutil.is_valid_widget(self):
            return False
        geo = self._current_screen_geometry()
        if geo is None:
            return False

        width = min(self.width(), geo.width())
        height = min(self.height(), geo.height())
        x = max(geo.left(), min(self.x(), geo.right() - width))
        y = max(geo.top(), min(self.y(), geo.bottom() - height))

        if width != self.width() or height != self.height():
            self.setGeometry(x, y, width, height)
        else:
            self.move(x, y)
        return True

    def place_above_toolbar_button(self, button=None, gap=None):
        if not wutil.is_valid_widget(self):
            return False

        if not button or not wutil.is_valid_widget(button) or not button.isVisible():
            self.place_near_cursor()
            return False

        self.adjustSize()
        width = self.width()
        height = self.height()

        top_left = button.mapToGlobal(QtCore.QPoint(0, 0))
        button_rect = QtCore.QRect(top_left, button.size())
        anchor_point = button_rect.center()

        screen = QtGui.QGuiApplication.screenAt(anchor_point) or QtGui.QGuiApplication.primaryScreen()
        geo = screen.availableGeometry()
        gap = wutil.DPI(18) if gap is None else gap

        x = anchor_point.x() - width // 2
        y = button_rect.top() - height - gap

        if y < geo.top():
            y = button_rect.bottom() + gap

        x = max(geo.left(), min(x, geo.right() - width))
        y = max(geo.top(), min(y, geo.bottom() - height))

        self.move(x, y)
        self.clamp_to_current_screen()
        self.show()
        self.raise_()
        self.activateWindow()
        return True

    def _init_floating_window_behavior(self):
        self._hovered = False
        self._auto_transparency = self._auto_transparency_setting_enabled()
        self.setMouseTracking(True)
        self.setAttribute(QtCore.Qt.WA_Hover, True)

        self.fade_timer = QtCore.QTimer(self)
        self.fade_timer.setSingleShot(True)
        self.fade_timer.timeout.connect(self._apply_transparency)

        self.settings_timer = QtCore.QTimer(self)
        self.settings_timer.timeout.connect(self._check_settings)
        self.settings_timer.start(500)

    def _auto_transparency_setting_enabled(self):
        raise NotImplementedError

    def _stays_on_top_setting_enabled(self):
        raise NotImplementedError

    def _geometry_settings_key(self):
        raise NotImplementedError

    def _geometry_settings_namespace(self):
        raise NotImplementedError

    def _save_geometry_setting(self):
        try:
            key = self._geometry_settings_key()
            namespace = self._geometry_settings_namespace()
        except NotImplementedError:
            return
        settings.set_setting(
            key,
            [self.pos().x(), self.pos().y(), self.width(), self.height()],
            namespace=namespace,
        )

    def _restore_saved_geometry(self):
        try:
            key = self._geometry_settings_key()
            namespace = self._geometry_settings_namespace()
        except NotImplementedError:
            return False
        saved_geom = settings.get_setting(
            key,
            namespace=namespace,
        )
        if not saved_geom:
            return False
        if len(saved_geom) == 4:
            x, y, width, height = saved_geom
            self.setGeometry(x, y, width, height)
        elif len(saved_geom) >= 2:
            self.move(saved_geom[0], saved_geom[1])
        self.clamp_to_current_screen()
        return True

    def _check_settings(self):
        new_state = self._auto_transparency_setting_enabled()
        if new_state != self._auto_transparency:
            self._auto_transparency = new_state
            self.update_transparency_state(self._hovered)

    def _apply_transparency(self):
        if self._hovered:
            return
        self.setWindowOpacity(0.45 if self._auto_transparency else 1.0)

    def enterEvent(self, event):
        super().enterEvent(event)
        self.update_transparency_state(True)

    def leaveEvent(self, event):
        super().leaveEvent(event)
        self.update_transparency_state(False)

    def showEvent(self, event):
        super().showEvent(event)
        self.clamp_to_current_screen()
        if hasattr(self, "fade_timer"):
            self.update_transparency_state(self.rect().contains(self.mapFromGlobal(QtGui.QCursor.pos())))

    def update_transparency_state(self, hovered):
        if not hasattr(self, "fade_timer"):
            return
        self._hovered = hovered
        self.fade_timer.stop()
        if not self._auto_transparency:
            self.setWindowOpacity(1.0)
            return

        self.setWindowOpacity(0.80)
        if not hovered:
            self.fade_timer.start(800)

    def apply_stay_on_top_setting(self):
        was_visible = self.isVisible()
        geometry = self.geometry()
        self.setWindowFlag(QtCore.Qt.WindowStaysOnTopHint, self._stays_on_top_setting_enabled())
        self.setGeometry(geometry)
        if was_visible:
            self.show()
            self.raise_()
            self.activateWindow()

    def hideEvent(self, event):
        self._save_geometry_setting()
        super().hideEvent(event)
