from TheKeyMachine.core.Qt import QtCore  # type: ignore
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
            "menu": api.build_pause_viewport_context_menu,
        },
        "auto_pause_viewport": {
            "type": "check", "state_key": "background_runner:auto_pause_viewport",
            "label": "Auto Pause Viewport", "icon": "auto_pause_viewport",
            "callback": api.set_auto_pause_enabled, "get_checked": api.is_auto_pause_enabled,
            "set_checked": api.set_auto_pause_enabled, "changed_signal": api.auto_pause_changed_signal(),
            "tooltip": TOOLTIPS["auto_pause_viewport"],
        },
    }
    SECTION = {
        "id": "pause_viewport_tools", "i18n_key": "pause_viewport",
        "label": "Pause Viewport", "color": COLORS.toolbar.red.hex,
        "items": [
            {
                "id": "pause_viewport",
                "shortcuts": [
                    {"id": "auto_pause_viewport", "keys": [QtCore.Qt.Key_Alt]},
                ],
            },
            {"id": "auto_pause_viewport"},
        ],
    }
