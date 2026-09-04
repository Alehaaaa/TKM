from TheKeyMachine.tools.registry import ToolObject, load_tooltips
from TheKeyMachine.tools.pause_viewport import api

TOOLTIPS = load_tooltips(__file__)


class PauseViewportToolObject(ToolObject):
    ORDER = 705
    TOOLS = {
        "pause_viewport": {
            "type": "check",
            "label": "Pause Viewport",
            "icon": "pause_viewport",
            "callback": api.set_viewport_paused,
            "get_checked": api.is_viewport_paused,
            "set_checked": api.set_viewport_paused,
            "tooltip": TOOLTIPS["pause_viewport"],
            "menu": api.build_pause_viewport_context_menu,
        },
        "pause_viewport_auto": {
            "type": "check",
            "state_key": "background_runner:pause_viewport_auto",
            "label": "Auto Pause Viewport",
            "icon": "pause_viewport_auto",
            "callback": api.set_auto_pause_enabled,
            "get_checked": api.is_auto_pause_enabled,
            "set_checked": api.set_auto_pause_enabled,
            "changed_signal": api.auto_pause_changed_signal(),
            "tooltip": TOOLTIPS["pause_viewport_auto"],
        },
    }
