from TheKeyMachine.core.Qt import QtCore, QtWidgets  # type: ignore
from TheKeyMachine.widgets import util as wutil


class GimbalOrderButton(QtWidgets.QFrame):
    clicked = QtCore.Signal(str)

    def __init__(self, parent=None):
        super().__init__(parent)
        self.order = ""
        self.setCursor(QtCore.Qt.PointingHandCursor)
        self.setFixedHeight(wutil.DPI(42))

        layout = QtWidgets.QGridLayout(self)
        layout.setContentsMargins(wutil.DPI(8), wutil.DPI(4), wutil.DPI(8), wutil.DPI(4))
        layout.setHorizontalSpacing(wutil.DPI(8))
        layout.setVerticalSpacing(wutil.DPI(2))

        self.rank_label = QtWidgets.QLabel("", self)
        self.rank_label.setFixedWidth(wutil.DPI(42))
        self.order_label = QtWidgets.QLabel("", self)
        self.order_label.setStyleSheet("font-size: %spx; font-weight: bold; color: #eeeeee;" % wutil.DPI(15))
        self.score_label = QtWidgets.QLabel("", self)
        self.score_label.setAlignment(QtCore.Qt.AlignRight | QtCore.Qt.AlignVCenter)
        self.score_label.setFixedWidth(wutil.DPI(42))

        self.bar = QtWidgets.QProgressBar(self)
        self.bar.setTextVisible(False)
        self.bar.setRange(0, 100)
        self.bar.setFixedHeight(wutil.DPI(5))

        layout.addWidget(self.rank_label, 0, 0, 2, 1)
        layout.addWidget(self.order_label, 0, 1)
        layout.addWidget(self.score_label, 0, 2)
        layout.addWidget(self.bar, 1, 1, 1, 2)
        self.set_data("", "", 100)

    def set_data(self, rank, order, percentage, current=False):
        self.order = order
        self.rank_label.setText(rank)
        self.order_label.setText(order.upper() if order else "-")
        self.score_label.setText("%s%%" % percentage if order else "-")
        self.bar.setValue(max(0, min(100, 100 - int(percentage))))

        if rank == "Best":
            fill = "#91c79f"
        elif rank == "Good":
            fill = "#c0bd7c"
        elif rank == "OK":
            fill = "#c99b6d"
        else:
            fill = "#b86f6f"

        border = "#d8d8d8" if current else "#4b4b4b"
        self.setStyleSheet(
            """
            QFrame {{
                background: #3d3d3d;
                border: 1px solid {border};
                border-radius: 6px;
            }}
            QLabel {{
                background: transparent;
                border: none;
                color: #cfcfcf;
            }}
            QProgressBar {{
                background: #292929;
                border: none;
                border-radius: 2px;
            }}
            QProgressBar::chunk {{
                background: {fill};
                border-radius: 2px;
            }}
            """.format(border=border, fill=fill)
        )

    def mousePressEvent(self, event):
        if event.button() == QtCore.Qt.LeftButton and self.order:
            self.clicked.emit(self.order)
        super().mousePressEvent(event)

from maya import cmds

from TheKeyMachine.core.Qt import QtWidgets  # type: ignore
import TheKeyMachine.core.runtimeManager as runtime
from TheKeyMachine.data import icons
import TheKeyMachine.mods.selectionMod as selectionMod
from TheKeyMachine.tools import common as toolCommon
from TheKeyMachine.tools.gimbal_fixer.controller import (
    GimbalAnalyzer,
    ROTATE_ORDERS,
    WINDOW_NAME,
    convert_rotation_order,
    has_rotate_order,
    rotate_gimbal_state,
    selected_control,
)
from TheKeyMachine.widgets import customDialogs
from TheKeyMachine.widgets import util as wutil


_gimbal_fixer_window = None
gimbal_fixer_window_bus = toolCommon.WindowStateBus()


def _emit_gimbal_fixer_window_state(is_open):
    state = bool(is_open)
    try:
        gimbal_fixer_window_bus.stateChanged.emit(state)
    except Exception:
        pass
    try:
        import TheKeyMachine.core.runtimeManager as runtime
        runtime.get_runtime_manager().set_tool_state("gimbal", state)
    except Exception:
        pass


class GimbalFixerWindow(
    toolCommon.FloatingToolWindowMixin,
    customDialogs.QFlatToolBarPopupDialog,
):
    def __init__(self, parent=None, popup=True):
        self.title = "Gimbal Fixer"
        self.icon = icons.reblock
        self.COLOR_BG_TRACK = self.DARK_BG_COLOR
        self._pinned = not popup
        super().__init__(parent=parent, popup=popup, closeButton=False)

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

        self._set_action_bar(include_close=not popup)
        self._connect_runtime_manager()
        self.refresh()

    def _set_action_bar(self, include_close):
        self.setBottomBar(
            buttons=[
                customDialogs.QFlatDialogButton("Apply Best", callback=self.apply_best_order, icon=icons.apply, highlight=True),
            ],
            closeButton=include_close,
            margins=0,
            spacing=2,
            highlight="Apply Best",
        )

    def set_popup_mode(self, popup):
        """Restore transient or pinned presentation when reusing the window."""
        self._popup = bool(popup)
        self._pinned = not popup
        self._opened = False
        self._set_action_bar(include_close=not popup)

    def _pin_after_reposition(self):
        if self._pinned:
            return
        self._pinned = True
        self._popup = False
        self._set_action_bar(include_close=True)

    def mouseReleaseEvent(self, event):
        was_dragging = self._is_dragging
        drag_start = QtCore.QPoint(self._drag_start_pos)
        global_position = wutil.event_global_pos(event)
        super().mouseReleaseEvent(event)
        if (
            was_dragging
            and (global_position - drag_start).manhattanLength() > wutil.DPI(10)
        ):
            self._pin_after_reposition()

    def changeEvent(self, event):
        if self._pinned:
            customDialogs.QFlatToolBarDialog.changeEvent(self, event)
            return
        super().changeEvent(event)

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
        _emit_gimbal_fixer_window_state(False)
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


def is_gimbal_fixer_window_open():
    window = existing_gimbal_fixer_window()
    return bool(window and window.isVisible())


def close_gimbal_fixer_window():
    window = existing_gimbal_fixer_window()
    if window and wutil.is_valid_widget(window):
        window.close()
    else:
        _emit_gimbal_fixer_window_state(False)


def show_gimbal_fixer_window(anchor_button=None, popup=True):
    global _gimbal_fixer_window
    existing = existing_gimbal_fixer_window()
    if existing:
        existing.set_popup_mode(popup)
        existing._connect_runtime_manager()
        existing.refresh()
        if anchor_button and wutil.is_valid_widget(anchor_button):
            existing.present_above_toolbar_button(anchor_button)
        elif popup:
            existing.present_beside_cursor()
        else:
            existing.present_floating_window()
        _emit_gimbal_fixer_window_state(True)
        return existing

    if cmds.window(WINDOW_NAME, exists=True):
        cmds.deleteUI(WINDOW_NAME)

    window = GimbalFixerWindow(
        parent=wutil.get_maya_qt(qt=QtWidgets.QWidget),
        popup=popup,
    )
    _gimbal_fixer_window = window

    def _on_destroyed(*_):
        global _gimbal_fixer_window
        _gimbal_fixer_window = None
        _emit_gimbal_fixer_window_state(False)

    window.destroyed.connect(_on_destroyed)
    if anchor_button and wutil.is_valid_widget(anchor_button):
        window.present_above_toolbar_button(anchor_button)
    elif popup:
        window.present_beside_cursor()
    else:
        window.present_floating_window()
    _emit_gimbal_fixer_window_state(True)

    if not selectionMod.get_selected_objects():
        wutil.make_inViewMessage("Select a control and reload")

    return window


gimbal_fixer_toolbar_toggle = toolCommon.ToolbarWindowToggle(
    is_gimbal_fixer_window_open,
    lambda anchor_button=None: show_gimbal_fixer_window(
        anchor_button=anchor_button,
        popup=True,
    ),
    close_gimbal_fixer_window,
    gimbal_fixer_window_bus.stateChanged,
)


def bind_gimbal_fixer_toolbar_button(button):
    button.connect_window_toggle(gimbal_fixer_toolbar_toggle)
    return True
