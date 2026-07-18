from TheKeyMachine.core.Qt import QtCore  # type: ignore

from TheKeyMachine.core.toolbox import ToolObject, load_tooltips
from TheKeyMachine.data import colors as toolColors
from TheKeyMachine.tools.locators import api


TOOLTIPS = load_tooltips(__file__)


class LocatorsToolObject(ToolObject):
    ORDER = 300
    TOOLS = {
        "create_locator": {"type": "tool", "label": "Create Locator", "icon": "cube", "callback": api.create_locator, "tooltip": TOOLTIPS["create"]},
        "locator_select_temp": {"type": "tool", "label": "Select Temp Locators", "icon": "cube", "callback": api.select_temp_locators, "tooltip": TOOLTIPS["select_temp"]},
        "locator_remove_temp": {"type": "tool", "label": "Remove Temp Locators", "icon": "cube", "callback": api.delete_temp_locators, "tooltip": TOOLTIPS["remove_temp"]},
    }
    SECTION = {
            "id": "locator_tools",
            "label": "Locators",
            "color": toolColors.TOOLBAR_RED,
            "items": [
                {"id": "create_locator", "shortcuts": [
                    {"id": "locator_select_temp", "keys": [QtCore.Qt.Key_Control]},
                    {"id": "locator_remove_temp", "keys": [QtCore.Qt.Key_Control, QtCore.Qt.Key_Shift, QtCore.Qt.Key_Alt]},
                ]},
                {"id": "locator_select_temp"},
                {"id": "locator_remove_temp"},
            ],
        }
