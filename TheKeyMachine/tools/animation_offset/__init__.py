from TheKeyMachine.core.toolbox import ToolObject, load_tooltips
from TheKeyMachine.data import colors as toolColors
from TheKeyMachine.tools.animation_offset import api


TOOLTIPS = load_tooltips(__file__)


class AnimationOffsetToolObject(ToolObject):
    ORDER = 600
    TOOLS = {
        "animation_offset": {
            "type": "check",
            "state_key": "animation_offset",
            "label": "Animation Offset",
            "icon": "animation_offset",
            "callback": api.toggle,
            "get_checked": api.is_enabled,
            "set_checked": api.toggle,
            "tooltip": TOOLTIPS["animation_offset"],
            "operation": {"progress": False, "undo": False},
        }
    }
    SECTION = {
        "id": "animation_offset_tools",
        "label": "Animation Offset",
        "color": toolColors.TOOLBAR_PURPLE,
        "items": [{"id": "animation_offset"}],
    }
