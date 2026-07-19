from TheKeyMachine.core.toolbox import ToolObject, load_tooltips
from TheKeyMachine.tools.graph_toolbar import api


TOOLTIPS = load_tooltips(__file__)


class GraphToolbarToolObject(ToolObject):
    ORDER = 950
    TOOLS = {
        "graph_settings_menu": {
            "type": "menu", "label": "Graph Toolbar Settings", "icon": "settings",
            "callback": api.show_settings_menu, "tooltip": TOOLTIPS["settings_menu"],
        },
        "graph_dock_menu": {
            "type": "menu", "label": "Graph Toolbar Dock", "icon": "dock",
            "callback": api.show_dock_menu, "tooltip": TOOLTIPS["dock_menu"],
        },
    }

