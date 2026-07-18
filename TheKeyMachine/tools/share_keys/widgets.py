"""Bake interval input owned by the Share Keys package."""

from TheKeyMachine.core.Qt import QtWidgets  # type: ignore
from TheKeyMachine.tools.share_keys import controller
from TheKeyMachine.widgets.customDialogs import QFlatNumberInput


def open_custom_bake():
    for widget in QtWidgets.QApplication.topLevelWidgets():
        if isinstance(widget, QFlatNumberInput) and widget.windowTitle() == "Bake Custom Interval":
            widget.close()
            widget.deleteLater()

    dialog = QFlatNumberInput(
        callback=lambda value, window: controller.bake_animation(bake_interval=value, window=window),
        parent=None,
    )
    dialog.place_near_cursor()
    dialog.show()
    return dialog
