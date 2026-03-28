try:
    from PySide2 import QtCore, QtGui
except ImportError:
    from PySide6 import QtCore, QtGui

import TheKeyMachine.tools.orbit.api as orbitApi
from TheKeyMachine.widgets import customDialogs
from TheKeyMachine.tools.orbit.customWidgets import OrbitWindowMixin

class OrbitWindow(OrbitWindowMixin, customDialogs.QFlatCloseableFloatingWidget):
    def __init__(self, parent=None, offset_x=0, offset_y=0, rebuild=False):
        super().__init__(popup=False, parent=parent)
        self.setObjectName("orbit_window")
        self.setWindowTitle("Orbit")

        self._setup_orbit_ui()
        self._init_floating_window_behavior()

        saved_geom = orbitApi.settings.get_setting("orbit_geometry", namespace=orbitApi.ORBIT_SETTINGS_NAMESPACE)

        self.adjustSize()

        if saved_geom and len(saved_geom) == 4 and not rebuild:
            x, y, w, h = saved_geom
            self.setGeometry(x, y, w, h)
        elif saved_geom and len(saved_geom) >= 2:
            x, y = saved_geom[0], saved_geom[1]
            if rebuild:
                self.move(x, y)
            else:
                self.setGeometry(x, y, self.width(), self.height())
        else:
            if offset_x != 0 or offset_y != 0:
                self.move(QtGui.QCursor.pos() + QtCore.QPoint(offset_x, offset_y))
            else:
                self.place_above_toolbar_button(orbitApi._get_orbit_toolbar_button())

        self.apply_stay_on_top_setting()
        self.update_transparency_state(False)

    def _auto_transparency_setting_enabled(self):
        return orbitApi._orbit_auto_transparency_enabled()

    def _stays_on_top_setting_enabled(self):
        return orbitApi._orbit_stays_on_top()

    def _geometry_settings_key(self):
        return "orbit_geometry"

    def _geometry_settings_namespace(self):
        return orbitApi.ORBIT_SETTINGS_NAMESPACE

    def closeEvent(self, event):
        orbitApi._emit_orbit_window_state(False)
        super().closeEvent(event)
