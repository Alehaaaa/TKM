from TheKeyMachine.tools.registry import ToolObject, load_tooltips
from TheKeyMachine.data.colors import COLORS
from TheKeyMachine.tools.pause_viewport import api


TOOLTIPS = load_tooltips(__file__)


class PauseViewportToolObject(ToolObject):
    ORDER = 705
    TOOLS = {
        "pause_viewport": {
            "type": "check", "label": "Pause Viewport", "icon": "pause_viewport",
            "callback": api.set_viewport_paused, "get_checked": api.is_viewport_paused,
            "set_checked": api.set_viewport_paused, "tooltip": TOOLTIPS["pause_viewport"],
        },
    }
    SECTION = {
        "id": "pause_viewport_tools", "i18n_key": "pause_viewport",
        "label": "Pause Viewport", "color": COLORS.toolbar.red.hex,
        "items": [
            {"id": "pause_viewport"},
        ],
    }
