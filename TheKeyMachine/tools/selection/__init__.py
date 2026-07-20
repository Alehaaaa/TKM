from TheKeyMachine.core.Qt import QtCore  # type: ignore
from TheKeyMachine.core.toolbox import ToolObject, load_tooltips
from TheKeyMachine.data.colors import COLORS
from TheKeyMachine.tools.selection import api


TOOLTIPS = load_tooltips(__file__)


class SelectionToolObject(ToolObject):
    ORDER = 370
    DOC_URL = "https://thekeymachine.gitbook.io/base/the-toolbar/selection-tools"

    TOOLS = {
        "selector": {
            "type": "tool", "label": "Selector", "icon": "selector",
            "callback": api.open_selector, "tooltip": TOOLTIPS["selector"],
        },
        "select_hierarchy": {
            "type": "tool", "label": "Select Hierarchy", "icon": "select_hierarchy",
            "callback": api.select_hierarchy, "tooltip": TOOLTIPS["hierarchy"],
        },
        "select_rig_controls": {
            "type": "tool", "label": "Select Rig Controls", "icon": "select_rig_controls",
            "callback": api.select_rig_controls, "tooltip": TOOLTIPS["rig_controls"],
        },
        "select_rig_controls_animated": {
            "type": "tool", "label": "Select Animated Rig Controls", "icon": "select_rig_controls_animated",
            "callback": api.select_rig_controls_animated, "tooltip": TOOLTIPS["animated_controls"],
        },
    }

    SECTION = {
        "id": "selection_tools", "label": "Selection", "color": COLORS.toolbar.green.hex,
        "items": [
            {"id": "selector"},
            {"id": "select_hierarchy"},
            {"id": "select_rig_controls", "shortcuts": [
                {"id": "select_rig_controls_animated", "keys": [QtCore.Qt.Key_Control]},
            ]},
            {"id": "select_rig_controls_animated"},
        ],
    }
