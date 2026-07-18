from TheKeyMachine.core.toolbox import ToolObject, load_tooltips
from TheKeyMachine.data import colors as toolColors
from TheKeyMachine.tools.depth_mover import api


TOOLTIPS = load_tooltips(__file__)


class DepthMoverToolObject(ToolObject):
    ORDER = 610
    TOOLS = {
        "depth_mover": {
            "type": "check",
            "state_key": "depth_mover",
            "label": "Depth Mover",
            "icon": "depth_mover",
            "callback": api.toggle,
            "get_checked": api.is_enabled,
            "set_checked": api.toggle,
            "tooltip": TOOLTIPS["depth_mover"],
        },
    }
    SECTION = {
        "id": "depth_mover_tools",
        "label": "Depth Mover",
        "color": toolColors.TOOLBAR_PURPLE,
        "items": [{"id": "depth_mover"}],
    }
