from TheKeyMachine.tools.registry import ToolObject, load_tooltips
from TheKeyMachine.tools.global_tools import api


TOOLTIPS = load_tooltips(__file__)


class GlobalToolsToolObject(ToolObject):
    ORDER = 940
    TOOLS = {
        "smart_euler_filter": {
            "type": "setting",
            "label": "Auto Euler Filter",
            "menu_label": "Auto Euler Filter",
            "text": "EF",
            "icon": "euler_filter",
            "callback": api.toggle_euler_filter,
            "tooltip": TOOLTIPS["euler_filter"],
        },
        "overshoot_sliders": {
            "type": "setting",
            "label": "Overshoot Sliders",
            "menu_label": "Overshoot Sliders",
            "text": "OS",
            "icon": "sliders_overshoot",
            "callback": api.toggle_overshoot_sliders,
            "tooltip": TOOLTIPS["overshoot_sliders"],
        },
        "custom_graph": {
            "type": "setting",
            "label": "Graph Editor Toolbar",
            "menu_label": "Show Graph Editor Toolbar",
            "text": "GE",
            "icon": "customGraph",
            "callback": api.toggle_graph_toolbar,
            "tooltip": TOOLTIPS["custom_graph"],
        },
    }
    SECTION = {
        "id": "global_tools",
        "label": "Global Tools",
        "items": [
            {"id": "smart_euler_filter"},
            {"id": "overshoot_sliders"},
            {"id": "custom_graph"},
        ],
    }
