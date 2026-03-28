try:
    from PySide2 import QtCore, QtGui
except ImportError:
    from PySide6 import QtCore, QtGui

from TheKeyMachine.widgets import util as wutil
from TheKeyMachine.mods import settingsMod as settings


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

    def _on_button_toggled(self, checked):
        if self._syncing:
            return
        if checked:
            self._open_fn()
        else:
            self._close_fn()

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
        if not self._is_open_fn():
            self._open_fn()

    def close(self):
        if self._is_open_fn():
            self._close_fn()

    def toggle(self):
        if self._is_open_fn():
            self._close_fn()
        else:
            self._open_fn()

    def _on_window_state_changed(self, is_open):
        if not self._button:
            return
        self._syncing = True
        try:
            self._button.setChecked(bool(is_open))
        finally:
            self._syncing = False


class FloatingToolWindowMixin:
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
