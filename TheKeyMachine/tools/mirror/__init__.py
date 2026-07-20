from TheKeyMachine.core.Qt import QtCore  # type: ignore
from TheKeyMachine.core.toolbox import ToolObject, load_tooltips
from TheKeyMachine.data.colors import COLORS
from TheKeyMachine.mods import generalMod as general
from TheKeyMachine.tools.mirror import api


TOOLTIPS = load_tooltips(__file__)


class MirrorToolObject(ToolObject):
    ORDER = 390
    DOC_URL = "https://thekeymachine.gitbook.io/base/the-toolbar/animation-tools/mirror"

    TOOLS = {
        "select_opposite": {
            "type": "tool", "label": "Select Opposite", "icon": "opposite_select",
            "callback": api.select_opposite, "tooltip": TOOLTIPS["select_opposite"],
        },
        "opposite_add": {
            "type": "tool", "label": "Add Opposite", "icon": "opposite_add",
            "callback": api.add_select_opposite, "tooltip": TOOLTIPS["add_opposite"],
        },
        "opposite_copy": {
            "type": "tool", "label": "Copy Opposite", "icon": "opposite_copy",
            "callback": api.copy_opposite, "tooltip": TOOLTIPS["copy_opposite"],
        },
        "mirror": {
            "type": "tool",
            "label": "Mirror",
            "icon": "mirror",
            "callback": api.mirror,
            "tooltip": TOOLTIPS["mirror"],
            "menu": {
                "label": "Mirror",
                "icon": "mirror",
                "items": [
                    "mirror_to_right",
                    "mirror_to_left",
                    "mirror_all_keys",
                    "separator",
                    "mirror_add_invert",
                    "mirror_add_keep",
                    "mirror_remove_exc",
                    "separator",
                    "mirror_help",
                ],
            },
        },
        "mirror_to_right": {
            "type": "tool", "label": "Mirror to Right", "icon": "mirror",
            "callback": api.mirror_to_right, "tooltip": TOOLTIPS["to_right"],
        },
        "mirror_to_left": {
            "type": "tool", "label": "Mirror to Left", "icon": "mirror",
            "callback": api.mirror_to_left, "tooltip": TOOLTIPS["to_left"],
        },
        "mirror_all_keys": {
            "type": "tool", "label": "Mirror All Keys", "icon": "mirror",
            "callback": api.mirror_all_keys, "tooltip": TOOLTIPS["all_keys"],
        },
        "mirror_add_invert": {
            "type": "tool", "label": "Add Exception Invert", "icon": "mirror",
            "callback": api.add_invert_exception, "tooltip": TOOLTIPS["add_invert"],
        },
        "mirror_add_keep": {
            "type": "tool", "label": "Add Exception Keep", "icon": "mirror",
            "callback": api.add_keep_exception, "tooltip": TOOLTIPS["add_keep"],
        },
        "mirror_remove_exc": {
            "type": "tool", "label": "Remove Exception", "icon": "mirror",
            "callback": api.remove_exception, "tooltip": TOOLTIPS["remove_exception"],
        },
        "mirror_help": {
            "type": "tool", "label": "Help", "icon": "help", "pinnable": False,
            "callback": lambda: general.open_url(MirrorToolObject.DOC_URL),
            "tooltip": TOOLTIPS["help"],
        },
    }

    SECTIONS = (
        {
            "id": "opposite_tools",
            "label": "Opposite",
            "color": COLORS.toolbar.green.hex,
            "items": [
                {"id": "select_opposite"},
                {"id": "opposite_add"},
                {"id": "opposite_copy"},
            ],
        },
        {
            "id": "mirror_tools",
            "label": "Mirror",
            "color": COLORS.toolbar.green.hex,
            "items": [
                {
                    "id": "mirror",
                    "shortcuts": [
                        {"id": "mirror_add_invert", "keys": [QtCore.Qt.Key_Shift]},
                        {"id": "mirror_add_keep", "keys": [QtCore.Qt.Key_Control]},
                        {"id": "mirror_remove_exc", "keys": [QtCore.Qt.Key_Control, QtCore.Qt.Key_Shift]},
                    ],
                },
                {"id": "mirror_to_right"},
                {"id": "mirror_to_left"},
                {"id": "mirror_all_keys"},
                "separator",
                {"id": "mirror_add_invert"},
                {"id": "mirror_add_keep"},
                {"id": "mirror_remove_exc"},
                "separator",
                {"id": "mirror_help"},
            ],
        },
    )
