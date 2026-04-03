import re
from functools import lru_cache

import maya.cmds as cmds

try:
    from PySide2 import QtCore, QtGui
except ImportError:
    from PySide6 import QtCore, QtGui

from TheKeyMachine.widgets import util as wutil
from TheKeyMachine.mods import settingsMod as settings


RE_HTML_TAGS = re.compile(r"<[^>]*>")
RE_WHITESPACE = re.compile(r"\s+")
RE_LINE_SPLIT = re.compile(r"<br\s*/?>|\r?\n", re.IGNORECASE)
RE_SENTENCE = re.compile(r"(.+?[.!?])(?:\s|$)")
RE_CAMEL_BREAK = re.compile(r"(?<=[a-z0-9])(?=[A-Z])")
RE_TOOLTIP_TITLE = re.compile(r"<b>(.*?)</b>", re.IGNORECASE | re.DOTALL)

UNDO_PREFIX = "TKM"


def clean_tool_text(raw):
    if not raw:
        return ""
    return RE_WHITESPACE.sub(" ", RE_HTML_TAGS.sub(" ", str(raw))).strip()


def humanize_tool_name(raw):
    if not raw:
        return ""
    value = RE_CAMEL_BREAK.sub(" ", str(raw).replace("_", " ").replace("-", " "))
    return clean_tool_text(value).title()


def get_tool_summary(raw):
    if not raw:
        return ""

    parts = [clean_tool_text(part) for part in RE_LINE_SPLIT.split(str(raw))]
    first_line = next((part for part in parts if part), "")
    if not first_line:
        return ""

    sentence = RE_SENTENCE.match(first_line)
    if sentence:
        return clean_tool_text(sentence.group(1))
    return first_line


def get_tooltip_title(raw):
    if not raw:
        return ""
    if hasattr(raw, "title"):
        return clean_tool_text(getattr(raw, "title", ""))
    match = RE_TOOLTIP_TITLE.search(str(raw))
    if match:
        return clean_tool_text(match.group(1))
    return ""


def get_tooltip_summary(raw):
    if not raw:
        return ""
    if hasattr(raw, "first_line"):
        return clean_tool_text(getattr(raw, "first_line", ""))
    return get_tool_summary(raw)


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
        resolved_title = resolved_title or get_tooltip_title(tooltip_template)
        resolved_description = resolved_description or get_tooltip_summary(tooltip_template)

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


class ToolbarWindowToggle(QtCore.QObject):
    """Keeps a toolbar button in sync with a floating window."""

    def __init__(self, is_open_fn, open_fn, close_fn, state_signal=None, parent=None):
        super().__init__(parent)
        self._button = None
        self._syncing = False
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
        self._button.toggled.connect(self._on_button_toggled)
        self._button.destroyed.connect(self._on_button_destroyed)

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
        try:
            button.toggled.disconnect(self._on_button_toggled)
        except Exception:
            pass
        try:
            button.destroyed.disconnect(self._on_button_destroyed)
        except Exception:
            pass

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
