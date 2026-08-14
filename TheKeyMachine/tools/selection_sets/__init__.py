from TheKeyMachine.core.Qt import QtCore  # type: ignore

from TheKeyMachine.tools.registry import ToolObject, load_tooltips
from TheKeyMachine.tools.selection_sets import api


TOOLTIPS = load_tooltips(__file__)


class SelectionSetsToolObject(ToolObject):
    ORDER = 900
    TOOLS = {
        "selection_sets": {
            "type": "check", "state_key": "selection_sets", "label": "Selection Sets",
            "text": "SS", "icon": "selection_sets", "callback": api.toggle,
            "get_checked": api.is_selection_sets_window_open, "set_checked": api.toggle,
            "bind_checked_fn": api.bind_selection_sets_toolbar_button,
            "tooltip": TOOLTIPS["selection_sets"],
        },
        "selection_sets_quick_export": {
            "type": "tool", "label": "Quick Export", "text": "QEx",
            "icon": "selection_sets_export", "callback": api.quick_export_selection_sets,
            "tooltip": TOOLTIPS["quick_export"],
        },
        "selection_sets_quick_import": {
            "type": "tool", "label": "Quick Import", "text": "QIm",
            "icon": "selection_sets_import", "callback": api.quick_import_selection_sets,
            "tooltip": TOOLTIPS["quick_import"],
        },
        "selection_sets_export": {
            "type": "tool", "label": "Export", "text": "Ex",
            "icon": "selection_sets_export", "callback": api.export_selection_sets,
            "tooltip": TOOLTIPS["export"],
        },
        "selection_sets_import": {
            "type": "tool", "label": "Import", "text": "Im",
            "icon": "selection_sets_import", "callback": api.import_selection_sets,
            "tooltip": TOOLTIPS["import"],
        },
        "selection_sets_clear_all": {
            "type": "tool", "label": "Clear All Selection Sets", "text": "Clr",
            "icon": "trash", "callback": api.clear_all_selection_sets,
            "tooltip": TOOLTIPS["clear_all"],
        },
    }
    SECTION = {
        "id": "selection_set_tools", "i18n_key": "selection_sets",
        "label": "Selection Sets",
        "items": [
            {"id": "selection_sets", "shortcuts": [
                {"id": "selection_sets_quick_export", "keys": [QtCore.Qt.Key_Control]},
                {"id": "selection_sets_quick_import", "keys": [QtCore.Qt.Key_Control, QtCore.Qt.Key_Shift]},
                {"id": "selection_sets_export", "keys": [QtCore.Qt.Key_Alt]},
                {"id": "selection_sets_import", "keys": [QtCore.Qt.Key_Control, QtCore.Qt.Key_Alt]},
                {"id": "selection_sets_clear_all", "keys": [QtCore.Qt.Key_Control, QtCore.Qt.Key_Alt, QtCore.Qt.Key_Shift]},
            ]},
            {"id": "selection_sets_quick_export"}, {"id": "selection_sets_quick_import"},
            {"id": "selection_sets_export"}, {"id": "selection_sets_import"},
            {"id": "selection_sets_clear_all"},
        ],
    }
