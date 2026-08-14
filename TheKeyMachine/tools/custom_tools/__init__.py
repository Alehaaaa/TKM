from TheKeyMachine.tools.registry import ToolObject, load_tooltips
from TheKeyMachine.tools.custom_tools import api


TOOLTIPS = load_tooltips(__file__)


class CustomToolsToolObject(ToolObject):
    ORDER = 970
    TOOLS = {
        "custom_tools": {
            "type": "menu",
            "label": "Custom Tools",
            "icon": "custom_tools",
            "callback": api.show_menu,
            "menu": api.build_menu,
            "tooltip": TOOLTIPS["custom_tools"],
        },
    }
    SECTION = {
        "id": "custom_tools_section", "i18n_key": "custom_tools",
        "label": "Custom Tools",
        "type": "connect_entries",
        "connect_kind": "tools",
        "items": [{"id": "custom_tools"}],
    }
