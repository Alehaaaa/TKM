from TheKeyMachine.tools.registry import ToolObject, load_tooltips
from TheKeyMachine.data.colors import COLORS
from TheKeyMachine.tools.micro_move import api


TOOLTIPS = load_tooltips(__file__)


class MicroMoveToolObject(ToolObject):
    ORDER = 605
    TOOLS = {
        "micro_move": {
            "type": "check",
            "state_key": "micro_move",
            "label": "Micro Move",
            "text": "MM",
            "icon": "ruler",
            "callback": api.toggle,
            "get_checked": api.is_enabled,
            "set_checked": api.toggle,
            "tooltip": TOOLTIPS["micro_move"],
        },
    }
    SECTION = {
        "id": "movers_tools",
        "label": "Movers",
        "color": COLORS.toolbar.purple.hex,
        "items": [{"id": "micro_move"}, {"id": "depth_mover"}],
    }
