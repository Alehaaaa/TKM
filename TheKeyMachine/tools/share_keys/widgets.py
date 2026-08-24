"""Bake Custom Interval window owned by the Share Keys package."""

from TheKeyMachine.core.Qt import QtWidgets  # type: ignore
from TheKeyMachine.core import trigger
from TheKeyMachine.data import icons
from TheKeyMachine.tools import common as toolCommon
from TheKeyMachine.ui.widgets import customDialogs
from TheKeyMachine.ui.widgets import customWidgets as cw
from TheKeyMachine.ui.widgets.util import DPI


WINDOW_NAME = "bake_custom_interval_window"


class BakeCustomIntervalWindow(
    toolCommon.FloatingToolWindowMixin,
    customDialogs.QFlatPinnableToolBarPopupDialog,
):
    """
    Flat floating dialog with:
        - title
        - optional icon
        - numeric input (spinbox)
        - action button

    Uses the shared pin-on-drag popup behavior (see
    ``QFlatPinnableToolBarPopupDialog``): opens as a transient popup that
    closes the moment Maya's UI steals activation, and turns into a pinned
    window with a Close button once dragged. Positioned the same way as
    every other floating tool window (``present_beside_cursor`` /
    ``present_above_toolbar_button``), rather than a bespoke placement call.
    """

    def __init__(self, callback=None, width=DPI(230), popup=True, parent=None):
        self.title = "Bake Custom Interval"
        self.icon = icons.bake_animation_custom
        self.start_value = 1.0

        self.COLOR_BG_TRACK = self.DARK_BG_COLOR
        self._callback = callback

        super().__init__(
            parent=parent,
            popup=popup,
            persistent_buttons=[
                customDialogs.QFlatDialogButton("Bake", icon=icons.apply, callback=self._on_accept, highlight=True),
            ],
            bottom_bar_kwargs={"margins": 0, "spacing": 2},
        )

        self.setObjectName(WINDOW_NAME)
        self.setMinimumWidth(width)
        self.title_label.setText(self.title)

        # Spinbox (replaces line edit) -- bake intervals can be fractional
        # (see controller._validate_bake_interval), so this is a float field.
        self.spinbox = cw.QFlatDoubleSpinBox(decimals=2, value=self.start_value, single_step=1.0)
        self.spinbox.setFixedHeight(DPI(30))

        # Enter key support (depends on your widget internals)
        if hasattr(self.spinbox, "lineEdit"):
            self.spinbox.lineEdit().returnPressed.connect(self._on_accept)

        self.mainLayout.addWidget(self.spinbox)
        self.spinbox.setFocus()
        self.spinbox.selectAll()

    # --- Value helpers ---
    def value(self):
        return self.spinbox.value()

    def int_value(self):
        return int(self.spinbox.value())

    def float_value(self):
        return float(self.spinbox.value())

    # --- Action ---
    def _on_accept(self, *args):
        if self._callback:
            self._callback(self.value(), self)


def open_custom_bake(anchor_button=None):
    for widget in QtWidgets.QApplication.topLevelWidgets():
        if widget.objectName() == WINDOW_NAME and isinstance(widget, BakeCustomIntervalWindow):
            widget.close()
            widget.deleteLater()

    dialog = BakeCustomIntervalWindow(
        callback=lambda value, window: trigger.execute_command(
            "bake_animation_custom_apply",
            bake_interval=value,
            window=window,
            _tkm_anchor_widget=window,
        ),
        parent=None,
    )
    if anchor_button is not None:
        dialog.present_above_toolbar_button(anchor_button)
    else:
        dialog.present_beside_cursor()
    return dialog
