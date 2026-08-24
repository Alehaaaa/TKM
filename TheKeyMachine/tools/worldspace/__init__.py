from TheKeyMachine.core.Qt import QtCore  # type: ignore

from TheKeyMachine.data.colors import COLORS
import TheKeyMachine.core.application as general
from TheKeyMachine.tools.registry import ToolObject, load_tooltips
from TheKeyMachine.tools.worldspace import api


TOOLTIPS = load_tooltips(__file__)


class WorldspaceToolObject(ToolObject):
    OPERATION = {"capture_animation_context": True}
    ORDER = 500
    DOC_URL = "https://thekeymachine.gitbook.io/base/the-toolbar/animation-tools/copy-paste-animation#worldspace-tools"

    TOOLS = {
        "ws_copy_frame": {
            "type": "tool",
            "label": "Copy World Space",
            "icon": "worldspace_copy_frame",
            "callback": api.worldspace_copy_frame,
            "tooltip": TOOLTIPS["copy_frame"],
            "operation": {"undo": False, "suspend_refresh": True},
        },
        "ws_copy_range": {
            "type": "tool",
            "label": "Copy World Space - Selected Range",
            "icon": "worldspace_copy_animation",
            "callback": api.worldspace_copy_animation,
            "tooltip": TOOLTIPS["copy_range"],
            "operation": {"undo": False, "suspend_refresh": True},
        },
        "ws_paste_frame": {
            "type": "tool",
            "label": "Paste World Space",
            "icon": "worldspace_paste_frame",
            "callback": api.paste_worldspace_single_frame,
            "tooltip": TOOLTIPS["paste_frame"],
            "operation": {"rollback_on_cancel": True},
        },
        "ws_paste": {
            "type": "tool",
            "label": "Paste World Space - All Animation",
            "icon": "worldspace_paste_animation",
            "callback": api.worldspace_paste_animation,
            "tooltip": TOOLTIPS["paste_animation"],
            "operation": {
                "suspend_refresh": True,
                "rollback_on_cancel": True,
            },
        },
        "worldspace_help": {
            "type": "tool",
            "label": "Help - World Space",
            "tooltip": TOOLTIPS["help"],
            "icon": "help",
            "callback": lambda: general.open_url(WorldspaceToolObject.DOC_URL),
            "pinnable": False,
        },
    }

    SECTION = {
            "id": "worldspace_tools",
            "label": "Worldspace",
            "color": COLORS.toolbar.green.hex,
            "items": [
                {
                    "id": "ws_copy_frame",
                    "shortcuts": [
                        {"id": "ws_paste_frame", "keys": [QtCore.Qt.Key_Control]},
                        {"id": "ws_copy_range", "keys": [QtCore.Qt.Key_Shift]},
                        {"id": "ws_paste", "keys": [QtCore.Qt.Key_Control, QtCore.Qt.Key_Shift]},
                    ],
                },
                {"id": "ws_copy_range"},
                "separator",
                {"id": "ws_paste_frame"},
                {"id": "ws_paste"},
            ],
        }
