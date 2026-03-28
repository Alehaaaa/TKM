try:
    from PySide2 import QtCore, QtGui
except ImportError:
    from PySide6 import QtCore, QtGui

from TheKeyMachine.widgets import customWidgets as cw, util as wutil


class SelectionSetButton(cw.InlineRenameButton):
    def __init__(self, text="", parent=None):
        super().__init__(text, parent)
        self._match_state = "none"
        self._match_radius = wutil.DPI(7)
        self._subset_name = None
        self._controller = None

    def set_rename_target(self, controller, subset_name, display_name):
        self._controller = controller
        self._subset_name = subset_name
        super().set_rename_target(subset_name, display_name, self._commit_inline_rename)

    def _commit_inline_rename(self, subset_name, new_name):
        if self._controller and subset_name:
            self._controller.rename_set(subset_name, new_name)

    def set_match_state(self, match_state):
        self._match_state = match_state or "none"
        self.update()

    def paintEvent(self, event):
        super().paintEvent(event)
        if self._renaming_active or self._match_state not in ("exact", "partial"):
            return

        painter = QtGui.QPainter(self)
        painter.setRenderHint(QtGui.QPainter.Antialiasing, True)

        rect = self.rect().adjusted(1, 1, -1, -1)
        pen = QtGui.QPen(QtGui.QColor("#ffffff"))
        pen.setWidth(wutil.DPI(2))
        if self._match_state == "partial":
            color = pen.color()
            color.setAlphaF(0.7)
            pen.setColor(color)
            pen.setWidth(wutil.DPI(0.5))
            pen.setStyle(QtCore.Qt.CustomDashLine)
            pen.setDashPattern([wutil.DPI(4), wutil.DPI(3)])
        painter.setPen(pen)
        painter.setBrush(QtCore.Qt.NoBrush)
        painter.drawRoundedRect(rect, self._match_radius, self._match_radius)
        painter.end()
