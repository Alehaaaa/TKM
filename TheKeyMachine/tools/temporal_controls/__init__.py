from TheKeyMachine.core.Qt import QtCore  # type: ignore

from TheKeyMachine.tools.registry import ToolObject, load_tooltips
from TheKeyMachine.data.colors import COLORS
from TheKeyMachine.tools.temporal_controls import api


TOOLTIPS = load_tooltips(__file__)


class TemporalControlsToolObject(ToolObject):
    ORDER = 625
    TOOLS = {
        "temporal_controls": {
            "type": "tool", "label": "Temporal Controls", "icon": "temporal_controls",
            "callback": api.create_controls, "tooltip": TOOLTIPS["temporal_controls"],
            # Callable, not the declarative {"label"/"icon"/"items"} dict every
            # other section item uses -- this menu needs an exclusive Bake
            # Mode group, a Lightning Mode checkbox, and a live Space-switch
            # list, none of which a plain list of command ids can express.
            # See api.build_temporal_controls_context_menu.
            "menu": api.build_temporal_controls_context_menu,
        },
        "temporal_controls_bake": {
            "type": "tool", "label": "Bake", "icon": "bake_animation_1",
            "callback": api.bake_controls, "tooltip": TOOLTIPS["temporal_controls_bake"],
        },
        "temporal_controls_revert": {
            "type": "tool", "label": "Revert", "icon": "refresh",
            "callback": api.revert_controls, "tooltip": TOOLTIPS["temporal_controls_revert"],
        },
    }
    SECTION = {
        "id": "temporal_controls_tools", "label": "Temporal Controls",
        "color": COLORS.toolbar.turquoise.hex,
        "items": [
            {"id": "temporal_controls", "shortcuts": [
                {"id": "temporal_controls_bake", "keys": [QtCore.Qt.Key_Shift]},
                {"id": "temporal_controls_revert", "keys": [QtCore.Qt.Key_Control]},
            ]},
        ],
    }
