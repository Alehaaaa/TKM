from TheKeyMachine.core.Qt import QtCore  # type: ignore
from TheKeyMachine.tools.registry import ToolObject, load_tooltips
from TheKeyMachine.data.colors import COLORS
from TheKeyMachine.tools.share_keys import api


TOOLTIPS = load_tooltips(__file__)


class ShareKeysToolObject(ToolObject):
    ORDER = 310
    OPERATION = {"capture_animation_context": True}
    DOC_URL = "https://thekeymachine.gitbook.io/base/the-toolbar/animation-tools/share-keys"
    TOOLS = {
        "share_keys": {
            "type": "tool", "label": "Share Keys", "text": "sK", "icon": "share_keys",
            "callback": api.share_keys, "tooltip": TOOLTIPS["share"],
            "keywords": ["synchronize key timing", "propagate keyframes"],
            "menu": {
                "label": "Share Keys",
                "items": [
                    {
                        "type": "choice",
                        "id": "share_keys_mode",
                        "get_value": api.get_share_keys_mode,
                        "set_value": api.set_share_keys_mode,
                        "items": api.share_keys_mode_choices,
                    },
                    "separator",
                    "share_keys_from_last_selected",
                    "reblock",
                ],
            },
        },
        "share_keys_from_last_selected": {"keywords": ["synchronize key timing from last selected", "propagate keyframes from last selected"], "type": "tool", "label": "Share Keys From Last Selected", "icon": "share_keys", "callback": api.share_keys_from_last_selected, "tooltip": TOOLTIPS["share_last"]},
        "reblock": {"keywords": ["redistribute key timing", "retime blocked keys"], "type": "tool", "label": "Reblock", "text": "rB", "icon": "reblock", "callback": api.reblock_move, "tooltip": TOOLTIPS["reblock"]},
        "reblock_insert": {"keywords": ["redistribute key timing insert", "retime blocked keys insert"], "type": "tool", "label": "Reblock Insert", "text": "rB+", "icon": "reblock", "callback": api.reblock_insert, "tooltip": TOOLTIPS["reblock_insert"]},
        "bake_animation_1": {
            "type": "tool", "label": "Bake on Ones", "icon": "bake_animation_1",
            "callback": api.bake_animation_1, "tooltip": TOOLTIPS["bake_1"],
            "keywords": ["plot keyframes on ones", "resample animation on ones"],
            "menu": {
                "label": "Bake",
                "items": [
                    {
                        "type": "choice",
                        "id": "bake_tangent_mode",
                        "get_value": api.get_bake_tangent_mode,
                        "set_value": api.set_bake_tangent_mode,
                        "items": api.bake_tangent_mode_choices,
                    },
                    "separator",
                    "bake_animation_2",
                    "bake_animation_3",
                    "bake_animation_4",
                    "bake_animation_custom",
                    "separator",
                    "bake_animation_from_last_selected",
                ],
            },
        },
        "bake_animation_2": {"keywords": ["plot keyframes on twos", "resample animation on twos"], "type": "tool", "label": "Bake on Twos", "icon": "bake_animation_2", "callback": api.bake_animation_2, "tooltip": TOOLTIPS["bake_2"]},
        "bake_animation_3": {"keywords": ["plot keyframes on threes", "resample animation on threes"], "type": "tool", "label": "Bake on Threes", "icon": "bake_animation_3", "callback": api.bake_animation_3, "tooltip": TOOLTIPS["bake_3"]},
        "bake_animation_4": {"keywords": ["plot keyframes on fours", "resample animation on fours"], "type": "tool", "label": "Bake on Fours", "icon": "bake_animation_3", "callback": api.bake_animation_4, "tooltip": TOOLTIPS["bake_4"]},
        "bake_animation_custom": {
            "type": "tool", "label": "Bake Custom Interval", "icon": "bake_animation_custom",
            "callback": api.bake_animation_custom, "tooltip": TOOLTIPS["bake_custom"],
            "keywords": ["open custom bake interval", "configure keyframe sampling"],
            "operation": {"progress": False, "undo": False},
        },
        "bake_animation_custom_apply": {
            "type": "tool", "label": "Bake Custom Interval", "icon": "bake_animation_custom",
            "callback": api.apply_custom_bake, "tooltip": TOOLTIPS["bake_custom"],
            "keywords": ["bake chosen frame interval", "apply custom key sampling"],
            "pinnable": False,
        },
        "bake_animation_from_last_selected": {"keywords": ["bake from last picked control", "sample from last chosen object"], "type": "tool", "label": "Bake From Last Selected", "icon": "bake_animation_1", "callback": api.bake_animation_from_last_selected, "tooltip": TOOLTIPS["bake_last"]},
    }
    SECTIONS = (
        {"id": "key_sync_tools", "label": "Key Sync", "color": COLORS.toolbar.green.hex, "items": [
            {"id": "share_keys", "shortcuts": [
                {"id": "share_keys_from_last_selected", "keys": [QtCore.Qt.Key_Control]},
                {"id": "reblock", "keys": [QtCore.Qt.Key_Shift]},
            ]}, {"id": "reblock"}, {"id": "share_keys_from_last_selected"},
        ]},
        {"id": "bake_tools", "label": "Bake", "color": COLORS.toolbar.green.hex, "items": [
            {"id": "bake_animation_1", "shortcuts": [
                {"id": "bake_animation_2", "keys": [QtCore.Qt.Key_Control]},
                {"id": "bake_animation_3", "keys": [QtCore.Qt.Key_Shift]},
                {"id": "bake_animation_4", "keys": [QtCore.Qt.Key_Control, QtCore.Qt.Key_Shift]},
                {"id": "bake_animation_custom", "keys": [QtCore.Qt.Key_Alt]},
                {"id": "bake_animation_from_last_selected", "keys": [QtCore.Qt.Key_Alt, QtCore.Qt.Key_Shift]},
            ]},
            {"id": "bake_animation_2"},
            {"id": "bake_animation_3"},
            {"id": "bake_animation_4"},
            {"id": "bake_animation_custom"},
            "separator",
            {"id": "bake_animation_from_last_selected"},
        ]},
    )
