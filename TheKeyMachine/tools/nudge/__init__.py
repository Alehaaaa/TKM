from TheKeyMachine.core.Qt import QtCore  # type: ignore
from TheKeyMachine.tools.registry import ToolObject, load_tooltips
from TheKeyMachine.data.colors import COLORS
from TheKeyMachine.tools.nudge import api, widgets

TOOLTIPS = load_tooltips(__file__)


def _queued_nudge(group, delta):
    return {"queue_group": "nudge_{}".format(group), "queue_delta": delta}


class NudgeToolObject(ToolObject):
    ORDER = 100
    OPERATION = {
        "capture_animation_context": True,
        "suspend_refresh": True,
    }
    TOOLS = {
        "nudge_value": {
            "type": "widget",
            "label": "Nudge Value",
            "text": "NV",
            "tooltip": TOOLTIPS["value"],
            "widget_factory": widgets.create_nudge_value_widget,
        },
        "nudge_left": {
            "type": "tool",
            "label": "Nudge Left",
            "icon": "nudge_left",
            "callback": api.nudge_left,
            "tooltip": TOOLTIPS["left"],
            "operation": _queued_nudge("range", -1),
            "menu": {
                "label": "Nudge Left",
                "icon": "nudge_left",
                "items": [
                    "nudge_left_all_keys",
                    "nudge_left_scene",
                    "nudge_remove_inbetween",
                    "nudge_remove_inbetween_scene",
                    "separator",
                    {"type": "check", "command": "nudge_snap_collision"},
                ],
            },
        },
        "nudge_left_all_keys": {
            "type": "tool",
            "label": "Nudge Left - All Keys",
            "icon": "nudge_left_all_keys",
            "callback": api.nudge_left_all_keys,
            "tooltip": TOOLTIPS["left_all"],
            "operation": _queued_nudge("all_keys", -1),
        },
        "nudge_left_scene": {
            "type": "tool",
            "label": "Nudge Left - Scene",
            "icon": "nudge_left_scene",
            "callback": api.nudge_left_scene,
            "tooltip": TOOLTIPS["left_scene"],
            "operation": _queued_nudge("scene", -1),
        },
        "nudge_right": {
            "type": "tool",
            "label": "Nudge Right",
            "icon": "nudge_right",
            "callback": api.nudge_right,
            "tooltip": TOOLTIPS["right"],
            "operation": _queued_nudge("range", 1),
            "menu": {
                "label": "Nudge Right",
                "icon": "nudge_right",
                "items": [
                    "nudge_right_all_keys",
                    "nudge_right_scene",
                    "nudge_insert_inbetween",
                    "nudge_insert_inbetween_scene",
                    "separator",
                    {"type": "check", "command": "nudge_snap_collision"},
                ],
            },
        },
        "nudge_right_all_keys": {
            "type": "tool",
            "label": "Nudge Right - All Keys",
            "icon": "nudge_right_all_keys",
            "callback": api.nudge_right_all_keys,
            "tooltip": TOOLTIPS["right_all"],
            "operation": _queued_nudge("all_keys", 1),
        },
        "nudge_right_scene": {
            "type": "tool",
            "label": "Nudge Right - Scene",
            "icon": "nudge_right_scene",
            "callback": api.nudge_right_scene,
            "tooltip": TOOLTIPS["right_scene"],
            "operation": _queued_nudge("scene", 1),
        },
        "nudge_snap_collision": {
            "type": "check",
            "state_key": "nudge_snap_collision",
            "label": "Snap Collisions",
            "callback": api.set_snap_collision_enabled,
            "get_checked": api.is_snap_collision_enabled,
            "set_checked": api.set_snap_collision_enabled,
            "tooltip": TOOLTIPS["snap_collision"],
            "operation": {"progress": False, "undo": False},
        },
        "nudge_insert_inbetween": {
            "type": "tool",
            "label": "Insert Inbetween",
            "icon": "nudge_insert_inbetween",
            "callback": api.nudge_insert_inbetween,
            "tooltip": TOOLTIPS["insert"],
            "operation": _queued_nudge("inbetween", 1),
        },
        "nudge_insert_inbetween_scene": {
            "type": "tool",
            "label": "Insert Inbetween - Scene",
            "icon": "nudge_insert_inbetween_scene",
            "callback": api.nudge_insert_inbetween_scene,
            "tooltip": TOOLTIPS["insert_scene"],
            "operation": _queued_nudge("inbetween_scene", 1),
        },
        "nudge_remove_inbetween": {
            "type": "tool",
            "label": "Remove Inbetween",
            "icon": "nudge_remove_inbetween",
            "callback": api.nudge_remove_inbetween,
            "tooltip": TOOLTIPS["remove"],
            "operation": _queued_nudge("inbetween", -1),
        },
        "nudge_remove_inbetween_scene": {
            "type": "tool",
            "label": "Remove Inbetween - Scene",
            "icon": "nudge_remove_inbetween_scene",
            "callback": api.nudge_remove_inbetween_scene,
            "tooltip": TOOLTIPS["remove_scene"],
            "operation": _queued_nudge("inbetween_scene", -1),
        },
    }
    SECTION = {
        "id": "nudge_tools",
        "label": "Nudge",
        "color": COLORS.toolbar.green.hex,
        "items": [
            {
                "id": "nudge_left",
                "shortcuts": [
                    {"id": "nudge_remove_inbetween", "keys": [QtCore.Qt.Key_Shift]},
                    {
                        "id": "nudge_left_all_keys",
                        "keys": [QtCore.Qt.Key_Control, QtCore.Qt.Key_Shift],
                    },
                    {
                        "id": "nudge_left_scene",
                        "keys": [
                            QtCore.Qt.Key_Alt,
                            QtCore.Qt.Key_Control,
                            QtCore.Qt.Key_Shift,
                        ],
                    },
                ],
            },
            {"id": "nudge_remove_inbetween"},
            {
                "id": "nudge_right",
                "shortcuts": [
                    {"id": "nudge_insert_inbetween", "keys": [QtCore.Qt.Key_Shift]},
                    {
                        "id": "nudge_right_all_keys",
                        "keys": [QtCore.Qt.Key_Control, QtCore.Qt.Key_Shift],
                    },
                    {
                        "id": "nudge_right_scene",
                        "keys": [
                            QtCore.Qt.Key_Alt,
                            QtCore.Qt.Key_Control,
                            QtCore.Qt.Key_Shift,
                        ],
                    },
                ],
            },
            {"id": "nudge_insert_inbetween"},
            {"id": "nudge_left_all_keys"},
            {"id": "nudge_left_scene"},
            {"id": "nudge_right_all_keys"},
            {"id": "nudge_right_scene"},
            {"id": "nudge_insert_inbetween_scene"},
            {"id": "nudge_remove_inbetween_scene"},
            {"id": "nudge_value"},
        ],
    }
