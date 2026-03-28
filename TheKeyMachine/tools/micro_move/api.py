from maya import cmds, utils

try:
    from PySide6 import QtCore
    from shiboken6 import isValid
except Exception:
    from PySide2 import QtCore
    from shiboken2 import isValid

import TheKeyMachine.mods.barMod as bar
import TheKeyMachine.mods.settingsMod as settings


class MicroMoveController(QtCore.QObject):
    def __init__(self, owner):
        super().__init__(owner)
        self._owner = owner
        self._enabled = bool(settings.get_setting("micro_move_button_state", False))
        self._timer = QtCore.QTimer(self)
        self._timer.setInterval(500)
        self._timer.timeout.connect(self._refresh_context)

    def is_enabled(self):
        return self._enabled

    def _refresh_context(self):
        if not self._enabled or not isValid(self._owner):
            return
        utils.executeDeferred(bar.activate_micro_move)

    def activate(self):
        cmds.undoInfo(openChunk=True)
        self._enabled = True
        settings.set_setting("micro_move_button_state", True)
        bar.activate_micro_move()
        self._timer.start()

    def deactivate(self):
        self._enabled = False
        settings.set_setting("micro_move_button_state", False)
        self._timer.stop()
        try:
            cmds.manipMoveContext("dummyCtx")
            cmds.setToolTo("dummyCtx")
        except Exception:
            pass
        try:
            cmds.undoInfo(closeChunk=True)
        except Exception:
            pass

    def toggle(self, checked=None, button_widget=None):
        if checked is None:
            checked = not self._enabled

        checked = bool(checked)

        if button_widget and isValid(button_widget):
            button_widget.blockSignals(True)
            button_widget.setChecked(checked)
            button_widget.blockSignals(False)

        if checked:
            self.activate()
        else:
            self.deactivate()

