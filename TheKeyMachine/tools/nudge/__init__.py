from TheKeyMachine.core.Qt import QtCore  # type: ignore
from TheKeyMachine.core.toolbox import ToolObject, load_tooltips
from TheKeyMachine.data.colors import COLORS
from TheKeyMachine.tools.nudge import api, widgets


TOOLTIPS = load_tooltips(__file__)


class NudgeToolObject(ToolObject):
    ORDER = 100
    TOOLS = {
        "nudge_value": {
            "type": "widget", "label": "Nudge Value", "text": "NV", "tooltip": TOOLTIPS["value"],
            "widget_factory": widgets.create_nudge_value_widget,
        },
        "nudge_left": {
            "type": "tool", "label": "Nudge Left", "icon": "nudge_left",
            "callback": api.nudge_left, "tooltip": TOOLTIPS["left"],
            "menu": {"label": "Nudge Left", "icon": "nudge_left", "items": [
                "nudge_left_all_keys", "nudge_left_scene", "nudge_remove_inbetween", "nudge_remove_inbetween_scene",
            ]},
        },
        "nudge_left_all_keys": {"type": "tool", "label": "Nudge Left - All Keys", "icon": "nudge_left_all_keys", "callback": api.nudge_left_all_keys, "tooltip": TOOLTIPS["left_all"]},
        "nudge_left_scene": {"type": "tool", "label": "Nudge Left - Scene", "icon": "nudge_left_scene", "callback": api.nudge_left_scene, "tooltip": TOOLTIPS["left_scene"]},
        "nudge_right": {
            "type": "tool", "label": "Nudge Right", "icon": "nudge_right",
            "callback": api.nudge_right, "tooltip": TOOLTIPS["right"],
            "menu": {"label": "Nudge Right", "icon": "nudge_right", "items": [
                "nudge_right_all_keys", "nudge_right_scene", "nudge_insert_inbetween", "nudge_insert_inbetween_scene",
            ]},
        },
        "nudge_right_all_keys": {"type": "tool", "label": "Nudge Right - All Keys", "icon": "nudge_right_all_keys", "callback": api.nudge_right_all_keys, "tooltip": TOOLTIPS["right_all"]},
        "nudge_right_scene": {"type": "tool", "label": "Nudge Right - Scene", "icon": "nudge_right_scene", "callback": api.nudge_right_scene, "tooltip": TOOLTIPS["right_scene"]},
        "nudge_insert_inbetween": {"type": "tool", "label": "Insert Inbetween", "icon": "nudge_insert_inbetween", "callback": api.nudge_insert_inbetween, "tooltip": TOOLTIPS["insert"]},
        "nudge_insert_inbetween_scene": {"type": "tool", "label": "Insert Inbetween - Scene", "icon": "nudge_insert_inbetween_scene", "callback": api.nudge_insert_inbetween_scene, "tooltip": TOOLTIPS["insert_scene"]},
        "nudge_remove_inbetween": {"type": "tool", "label": "Remove Inbetween", "icon": "nudge_remove_inbetween", "callback": api.nudge_remove_inbetween, "tooltip": TOOLTIPS["remove"]},
        "nudge_remove_inbetween_scene": {"type": "tool", "label": "Remove Inbetween - Scene", "icon": "nudge_remove_inbetween_scene", "callback": api.nudge_remove_inbetween_scene, "tooltip": TOOLTIPS["remove_scene"]},
    }
    SECTION = {
        "id": "nudge_tools", "label": "Nudge", "color": COLORS.toolbar.green.hex,
        "items": [
            {"id": "nudge_left", "shortcuts": [
                {"id": "nudge_remove_inbetween", "keys": [QtCore.Qt.Key_Shift]},
                {"id": "nudge_left_all_keys", "keys": [QtCore.Qt.Key_Control, QtCore.Qt.Key_Shift]},
                {"id": "nudge_left_scene", "keys": [QtCore.Qt.Key_Alt, QtCore.Qt.Key_Control, QtCore.Qt.Key_Shift]},
            ]},
            {"id": "nudge_remove_inbetween"},
            {"id": "nudge_right", "shortcuts": [
                {"id": "nudge_insert_inbetween", "keys": [QtCore.Qt.Key_Shift]},
                {"id": "nudge_right_all_keys", "keys": [QtCore.Qt.Key_Control, QtCore.Qt.Key_Shift]},
                {"id": "nudge_right_scene", "keys": [QtCore.Qt.Key_Alt, QtCore.Qt.Key_Control, QtCore.Qt.Key_Shift]},
            ]},
            {"id": "nudge_insert_inbetween"},
            {"id": "nudge_left_all_keys"}, {"id": "nudge_left_scene"},
            {"id": "nudge_right_all_keys"}, {"id": "nudge_right_scene"},
            {"id": "nudge_insert_inbetween_scene"},
            {"id": "nudge_remove_inbetween_scene"},
            {"id": "nudge_value"},
        ],
    }

