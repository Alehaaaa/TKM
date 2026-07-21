from TheKeyMachine.core import runtimeManager as runtime
from TheKeyMachine.mods import settingsMod as settings
from TheKeyMachine.tools import common as toolCommon
from TheKeyMachine.widgets import customWidgets as cw
from TheKeyMachine.widgets import util as wutil


def create_nudge_value_widget(section, item_data, owner=None):
    widget = cw.QFlatSpinBox()
    widget.setFixedWidth(wutil.DPI(50))
    widget.setValue(settings.get_setting("nudge_value", 1))
    manager = runtime.get_runtime_manager()

    def save_value(value):
        settings.set_setting("nudge_value", value)
        manager.nudgeValueChanged.emit(value)

    def sync_value(value):
        if not wutil.is_valid_widget(widget):
            return
        blocked = widget.blockSignals(True)
        widget.setValue(value)
        widget.blockSignals(blocked)

    def commit_and_clear_focus():
        widget.interpretText()
        line_edit = widget.lineEdit()
        if line_edit is not None:
            line_edit.clearFocus()
        widget.clearFocus()

    widget.valueChanged.connect(save_value)
    line_edit = widget.lineEdit()
    if line_edit is not None:
        line_edit.returnPressed.connect(commit_and_clear_focus)
    toolCommon.replace_tracked_connection(
        widget, "_tkm_nudge_value_sync", manager.nudgeValueChanged, sync_value, parent=widget
    )
    section.addWidget(
        widget, item_data.get("label", "Nudge Value"), item_data.get("id", "nudge_value"),
        default=item_data.get("default", True), tooltip=item_data.get("tooltip"),
        pinnable=item_data.get("pinnable", True),
    )
    if owner is not None:
        owner.move_keyframes_intField = widget
    return widget
