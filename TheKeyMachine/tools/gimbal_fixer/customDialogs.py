from maya import cmds

from TheKeyMachine.Qt import QtWidgets  # type: ignore
import TheKeyMachine.core.runtimeManager as runtime
from TheKeyMachine.data import icons
import TheKeyMachine.mods.selectionMod as selectionMod
from TheKeyMachine.tools import common as toolCommon
from TheKeyMachine.tools.gimbal_fixer.analyzer import GimbalAnalyzer
from TheKeyMachine.tools.gimbal_fixer.constants import ROTATE_ORDERS, WINDOW_NAME
from TheKeyMachine.tools.gimbal_fixer.controller import (
    convert_rotation_order,
    has_rotate_order,
    rotate_gimbal_state,
    selected_control,
)
from TheKeyMachine.tools.gimbal_fixer.customWidgets import GimbalOrderButton
from TheKeyMachine.widgets import customDialogs
from TheKeyMachine.widgets import util as wutil


_gimbal_fixer_window = None


class GimbalFixerWindow(customDialogs.QFlatToolBarDialog):
    def __init__(self, parent=None):
        self.title = "Gimbal Fixer"
        self.icon = icons.reblock
        self.COLOR_BG_TRACK = self.DARK_BG_COLOR
        super().__init__(parent=parent, popup=False, closeButton=True)

        self.setObjectName(WINDOW_NAME)
        self.setMinimumWidth(wutil.DPI(310))
        self.title_label.setText(self.title)
        self.analyzer = GimbalAnalyzer()
        self._analysis = []
        self._runtime_manager = runtime.get_runtime_manager()
        self._callbacks_connected = False

        self.control_label = QtWidgets.QLabel("Select a control", self)
        self.control_label.setStyleSheet("color:#d8d8d8; font-size:%spx;" % wutil.DPI(12))
        self.mainLayout.addWidget(self.control_label)

        self.current_label = QtWidgets.QLabel("Current order: -", self)
        self.current_label.setStyleSheet("color:#a8a8a8; font-size:%spx;" % wutil.DPI(11))
        self.mainLayout.addWidget(self.current_label)

        self.order_buttons = []
        for _ in ROTATE_ORDERS:
            button = GimbalOrderButton(self)
            button.clicked.connect(self.apply_order)
            self.order_buttons.append(button)
            self.mainLayout.addWidget(button)

        self.setBottomBar(
            buttons=[
                customDialogs.QFlatDialogButton("Apply Best", callback=self.apply_best_order, icon=icons.apply, highlight=True),
            ],
            closeButton=True,
            margins=0,
            spacing=2,
            highlight="Apply Best",
        )
        self._connect_runtime_manager()
        self.refresh()

    def _connect_runtime_manager(self):
        if self._callbacks_connected:
            return
        manager = getattr(self, "_runtime_manager", None)
        if manager is None:
            return
        toolCommon.replace_tracked_connections(
            self,
            "_runtime_manager_relays",
            (
                (manager.selection_changed, self.refresh),
            ),
            parent=self,
        )
        self._callbacks_connected = True

    def _disconnect_runtime_manager(self):
        if not self._callbacks_connected:
            return
        toolCommon.clear_tracked_connections(self, "_runtime_manager_relays")
        self._callbacks_connected = False

    def _clear_analysis(self):
        self._analysis = []
        for button in self.order_buttons:
            button.set_data("", "", 100)

    def refresh(self, *_args):
        obj = selected_control()
        if not obj:
            self.control_label.setText("Select a control")
            self.current_label.setText("Current order: -")
            self._clear_analysis()
            return
        if not has_rotate_order(obj):
            self.control_label.setText(obj.split("|")[-1])
            self.current_label.setText("Selection has no rotate order")
            self._clear_analysis()
            return

        current_index = cmds.getAttr("%s.rotateOrder" % obj)
        current_order = ROTATE_ORDERS[current_index]
        data = self.analyzer.analyze(obj)
        if not data:
            percentages = rotate_gimbal_state(obj)
            data = {
                order: {"percentage": int(round(percentages[index] * 100)), "label": ""}
                for index, order in enumerate(ROTATE_ORDERS)
            }

        ranked = sorted(
            ((info.get("percentage", 100), order, info.get("label", "")) for order, info in data.items()),
            key=lambda item: item[0],
        )
        rank_names = ["Best", "Good", "OK", "Risky", "Poor", "Bad"]
        self._analysis = ranked

        self.control_label.setText(obj.split("|")[-1])
        self.current_label.setText("Current order: %s" % current_order.upper())
        for index, button in enumerate(self.order_buttons):
            percentage, order, label = ranked[index]
            rank = label or rank_names[min(index, len(rank_names) - 1)]
            button.set_data(rank, order, percentage, current=order == current_order)

    def apply_order(self, order):
        convert_rotation_order(order)
        self.refresh()

    def apply_best_order(self, *_args):
        if not self._analysis:
            self.refresh()
        if self._analysis:
            self.apply_order(self._analysis[0][1])

    def closeEvent(self, event):
        self._disconnect_runtime_manager()
        super().closeEvent(event)


def existing_gimbal_fixer_window():
    global _gimbal_fixer_window
    if _gimbal_fixer_window and wutil.is_valid_widget(_gimbal_fixer_window):
        return _gimbal_fixer_window
    _gimbal_fixer_window = None

    for widget in QtWidgets.QApplication.topLevelWidgets():
        if widget.objectName() == WINDOW_NAME and isinstance(widget, GimbalFixerWindow) and wutil.is_valid_widget(widget):
            _gimbal_fixer_window = widget
            return widget
    return None


def show_gimbal_fixer_window():
    global _gimbal_fixer_window
    existing = existing_gimbal_fixer_window()
    if existing:
        existing.refresh()
        existing.show()
        existing.raise_()
        existing.activateWindow()
        return existing

    if cmds.window(WINDOW_NAME, exists=True):
        cmds.deleteUI(WINDOW_NAME)

    window = GimbalFixerWindow(parent=wutil.get_maya_qt(qt=QtWidgets.QWidget))
    _gimbal_fixer_window = window

    def _on_destroyed(*_):
        global _gimbal_fixer_window
        _gimbal_fixer_window = None

    window.destroyed.connect(_on_destroyed)
    window.show()
    window.raise_()
    window.activateWindow()

    if not selectionMod.get_selected_objects():
        wutil.make_inViewMessage("Select a control and reload")

    return window
