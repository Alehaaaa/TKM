from TheKeyMachine.core.Qt import QtCore  # type: ignore

from TheKeyMachine.core.toolbox import ToolObject, load_tooltips
from TheKeyMachine.data.colors import COLORS
import TheKeyMachine.mods.generalMod as general
from TheKeyMachine.tools.temp_pivot import api


TOOLTIPS = load_tooltips(__file__)


class TempPivotToolObject(ToolObject):
    ORDER = 615
    DOC_URL = "https://thekeymachine.gitbook.io/base/the-toolbar/animation-tools/temp-pivots"
    TOOLS = {
        "temp_pivot": {
            "type": "check", "state_key": "temp_pivot", "label": "Temp Pivot",
            "text": "TP", "icon": "temp_pivot", "callback": api.toggle,
            "get_checked": api.is_temp_pivot_active, "set_checked": api.toggle,
            "bind_checked_fn": api.bind_temp_pivot_toolbar_button,
            "tooltip": TOOLTIPS["temp_pivot"],
        },
        "temp_pivot_last_object": {
            "type": "tool", "label": "Temp Pivot to Last Object",
            "icon": "temp_pivot_last_object",
            "callback": api.create_last_object_temp_pivot,
            "tooltip": TOOLTIPS["last_object"], "pinnable": False,
        },
        "temp_pivot_centered": {
            "type": "tool", "label": "Temp Pivot Centered", "icon": "temp_pivot",
            "callback": api.create_centered_temp_pivot, "tooltip": TOOLTIPS["centered"],
        },
        "temp_pivot_worldspace": {
            "type": "tool", "label": "Temp Pivot WorldSpace",
            "icon": "temp_pivot_worldspace",
            "callback": api.create_worldspace_temp_pivot, "tooltip": TOOLTIPS["worldspace"],
        },
        "temp_pivot_edit": {
            "type": "tool", "label": "Edit Temp Pivot", "icon": "temp_pivot_edit",
            "callback": api.edit_temp_pivot, "tooltip": TOOLTIPS["edit"],
        },
        "temp_pivot_reset": {
            "type": "tool", "label": "Reset Temp Pivot", "icon": "temp_pivot_reset",
            "callback": api.reset_temp_pivot, "tooltip": TOOLTIPS["reset"],
        },
        "temp_pivot_help": {
            "type": "tool", "label": "Help", "icon": "help",
            "callback": lambda: general.open_url(TempPivotToolObject.DOC_URL),
            "tooltip": TOOLTIPS["help"], "pinnable": False,
        },
    }
    SECTION = {
        "id": "temp_pivot_tools", "label": "Temp Pivot",
        "color": COLORS.toolbar.purple.hex,
        "items": [
            {"id": "temp_pivot", "shortcuts": [
                {"id": "temp_pivot_reset", "keys": [QtCore.Qt.Key_Alt, QtCore.Qt.Key_Control]},
                {"id": "temp_pivot_centered", "keys": [QtCore.Qt.Key_Control]},
                {"id": "temp_pivot_last_object", "keys": [QtCore.Qt.Key_Shift]},
                {"id": "temp_pivot_worldspace", "keys": [QtCore.Qt.Key_Shift, QtCore.Qt.Key_Control]},
                {"id": "temp_pivot_edit", "keys": [QtCore.Qt.Key_Alt]},
            ]},
            {"id": "temp_pivot_last_object"}, {"id": "temp_pivot_centered"},
            {"id": "temp_pivot_worldspace"}, "separator", {"id": "temp_pivot_edit"},
            {"id": "temp_pivot_reset"}, "separator", {"id": "temp_pivot_help"},
        ],
    }

