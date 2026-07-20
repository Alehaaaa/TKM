from TheKeyMachine.core.Qt import QtCore  # type: ignore

from TheKeyMachine.data.colors import COLORS
from TheKeyMachine.core.toolbox import ToolObject, load_tooltips
from TheKeyMachine.tools.follow_cam import api


TOOLTIPS = load_tooltips(__file__)


class FollowCamToolObject(ToolObject):
    ORDER = 620
    TOOLS = {
        "follow_cam": {
            "type": "tool",
            "label": "Follow Cam",
            "icon": "follow_cam",
            "callback": lambda *args: api.create_follow_cam(translation=True, rotation=True),
            "tooltip": TOOLTIPS["follow_cam"],
        },
        "follow_cam_translation": {
            "type": "tool",
            "label": "Follow only Translation",
            "icon": "follow_cam",
            "callback": lambda: api.create_follow_cam(translation=True, rotation=False),
            "tooltip": TOOLTIPS["follow_cam_translation"],
        },
        "follow_cam_rotation": {
            "type": "tool",
            "label": "Follow only Rotation",
            "icon": "follow_cam",
            "callback": lambda: api.create_follow_cam(translation=False, rotation=True),
            "tooltip": TOOLTIPS["follow_cam_rotation"],
        },
        "follow_cam_remove": {
            "type": "tool",
            "label": "Remove Follow Cam",
            "icon": "remove",
            "callback": api.remove_follow_cam,
            "tooltip": TOOLTIPS["remove_follow_cam"],
        },
    }

    SECTION = {
            "id": "follow_cam_tools",
            "label": "Follow Cam",
            "color": COLORS.toolbar.purple.hex,
            "items": [
                {
                    "id": "follow_cam",
                    "shortcuts": [
                        {"id": "follow_cam_translation", "keys": [QtCore.Qt.Key_Shift]},
                        {"id": "follow_cam_rotation", "keys": [QtCore.Qt.Key_Control]},
                        {"id": "follow_cam_remove", "keys": [QtCore.Qt.Key_Control, QtCore.Qt.Key_Alt]},
                    ],
                },
                {"id": "follow_cam_translation"},
                {"id": "follow_cam_rotation"},
                "separator",
                {"id": "follow_cam_remove"},
            ],
        }

