try:
    from PySide2 import QtCore, QtGui
except ImportError:
    from PySide6 import QtCore, QtGui

import TheKeyMachine.tools.attribute_switcher.api as attributeSwitcherApi
from TheKeyMachine.tools.attribute_switcher.customWidgets import AttributeSwitcherWidget


class AttributeSwitcherWindow(AttributeSwitcherWidget):
    def __init__(self, parent=None, popup=False):
        super().__init__(popup=popup, parent=parent)
        self.setObjectName("attribute_switcher_window")
        self.setWindowTitle("Attribute Switcher")

        if popup:
            self.place_near_cursor()

        self.setWindowFlag(QtCore.Qt.WindowStaysOnTopHint, attributeSwitcherApi._attribute_switcher_stays_on_top())
        self.show()
        self.raise_()
        self.activateWindow()

    def closeEvent(self, event):
        attributeSwitcherApi._emit_attribute_switcher_window_state(False)
        super().closeEvent(event)
