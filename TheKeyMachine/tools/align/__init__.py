from functools import partial

from TheKeyMachine.core.Qt import QtCore  # type: ignore

from TheKeyMachine.core.toolbox import ToolObject, load_tooltips
from TheKeyMachine.data.colors import COLORS
import TheKeyMachine.mods.generalMod as general
from TheKeyMachine.tools.align import api


TOOLTIPS = load_tooltips(__file__)


class AlignToolObject(ToolObject):
    ORDER = 400
    DOC_URL = (
        "https://thekeymachine.gitbook.io/base/the-toolbar/animation-tools/match-align"
    )

    TOOLS = {
        "align_objects": {
            "type": "tool",
            "label": "Align Objects",
            "icon": "align",
            "callback": api.align_selected_objects,
            "tooltip": TOOLTIPS["align"],
        },
        "align_objects_all_keys": {
            "type": "tool",
            "label": "Align Objects All Keys",
            "icon": "align",
            "callback": partial(api.align_selected_objects, key_scope="all"),
            "tooltip": TOOLTIPS["align"],
        },
        "align_object_translation": {
            "type": "tool",
            "label": "Align Object Translation",
            "icon": "align",
            "callback": partial(
                api.align_selected_objects, pos=True, rot=False, scl=False
            ),
            "tooltip": TOOLTIPS["translation"],
        },
        "align_object_translation_all_keys": {
            "type": "tool",
            "label": "Align Object Translation All Keys",
            "icon": "align",
            "callback": partial(
                api.align_selected_objects,
                pos=True,
                rot=False,
                scl=False,
                key_scope="all",
            ),
            "tooltip": TOOLTIPS["translation_all"],
        },
        "align_object_rotation": {
            "type": "tool",
            "label": "Align Object Rotation",
            "icon": "align",
            "callback": partial(
                api.align_selected_objects, pos=False, rot=True, scl=False
            ),
            "tooltip": TOOLTIPS["rotation"],
        },
        "align_object_rotation_all_keys": {
            "type": "tool",
            "label": "Align Object Rotation All Keys",
            "icon": "align",
            "callback": partial(
                api.align_selected_objects,
                pos=False,
                rot=True,
                scl=False,
                key_scope="all",
            ),
            "tooltip": TOOLTIPS["rotation_all"],
        },
        "align_object_scale": {
            "type": "tool",
            "label": "Align Object Scale",
            "icon": "align",
            "callback": partial(
                api.align_selected_objects, pos=False, rot=False, scl=True
            ),
            "tooltip": TOOLTIPS["scale"],
        },
        "align_object_scale_all_keys": {
            "type": "tool",
            "label": "Align Object Scale All Keys",
            "icon": "align",
            "callback": partial(
                api.align_selected_objects,
                pos=False,
                rot=False,
                scl=True,
                key_scope="all",
            ),
            "tooltip": TOOLTIPS["scale_all"],
        },
        "align_objects_help": {
            "type": "tool",
            "label": "Align Objects Help",
            "icon": "help",
            "callback": lambda: general.open_url(AlignToolObject.DOC_URL),
            "tooltip": TOOLTIPS["help"],
            "pinnable": False,
        },
    }
    SECTION = {
        "id": "align_tools",
        "label": "Align Objects",
        "color": COLORS.toolbar.green.hex,
        "items": [
            {
                "id": "align_objects",
                "shortcuts": [
                    {"id": "align_objects_all_keys", "keys": [QtCore.Qt.Key_Alt]},
                    {"id": "align_object_translation", "keys": [QtCore.Qt.Key_Shift]},
                    {
                        "id": "align_object_translation_all_keys",
                        "keys": [QtCore.Qt.Key_Alt, QtCore.Qt.Key_Shift],
                    },
                    {"id": "align_object_rotation", "keys": [QtCore.Qt.Key_Control]},
                    {
                        "id": "align_object_rotation_all_keys",
                        "keys": [QtCore.Qt.Key_Alt, QtCore.Qt.Key_Control],
                    },
                    {
                        "id": "align_object_scale",
                        "keys": [QtCore.Qt.Key_Control, QtCore.Qt.Key_Shift],
                    },
                    {
                        "id": "align_object_scale_all_keys",
                        "keys": [
                            QtCore.Qt.Key_Alt,
                            QtCore.Qt.Key_Control,
                            QtCore.Qt.Key_Shift,
                        ],
                    },
                ],
            },
            {"id": "align_object_translation"},
            {"id": "align_object_rotation"},
            {"id": "align_object_scale"},
            "separator",
            {"id": "align_objects_all_keys"},
            {"id": "align_object_translation_all_keys"},
            {"id": "align_object_rotation_all_keys"},
            {"id": "align_object_scale_all_keys"},
            "separator",
            {"id": "align_objects_help"},
        ],
    }
