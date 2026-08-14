from TheKeyMachine.core.Qt import QtCore  # type: ignore

from TheKeyMachine.tools.registry import ToolObject, load_tooltips
from TheKeyMachine.data.colors import COLORS
from TheKeyMachine.tools.tracer import api


TOOLTIPS = load_tooltips(__file__)


class TracerToolObject(ToolObject):
    ORDER = 700
    TOOLS = {
        "create_tracer": {
            "type": "tool", "label": "Tracer", "icon": "tracer",
            "callback": api.create_tracer, "tooltip": TOOLTIPS["create"],
            "menu": {"label": "Tracer", "icon": "tracer", "items": [
                {"type": "check", "command": "tracer_connected"}, "separator",
                "tracer_refresh", "tracer_show_hide", "tracer_offset_node", "separator",
                "tracer_grey", "tracer_red", "tracer_blue", "separator", "tracer_remove",
            ]},
        },
        "tracer_refresh": {"type": "tool", "label": "Refresh Tracer", "icon": "tracer_refresh", "callback": api.refresh_tracer, "tooltip": TOOLTIPS["refresh"]},
        "tracer_show_hide": {"type": "tool", "label": "Toggle Tracer", "icon": "tracer_show_hide", "callback": api.toggle_tracer, "tooltip": TOOLTIPS["toggle"]},
        "tracer_offset_node": {"type": "tool", "label": "Select Offset Object", "icon": "tracer_select_offset", "callback": api.select_tracer_offset_node, "tooltip": TOOLTIPS["offset"]},
        "tracer_grey": {"type": "tool", "label": "Tracer Style: Grey", "icon": "tracer_grey", "callback": api.set_tracer_grey_color, "tooltip": TOOLTIPS["grey"]},
        "tracer_red": {"type": "tool", "label": "Tracer Style: Red", "icon": "tracer_red", "callback": api.set_tracer_red_color, "tooltip": TOOLTIPS["red"]},
        "tracer_blue": {"type": "tool", "label": "Tracer Style: Blue", "icon": "tracer_blue", "callback": api.set_tracer_blue_color, "tooltip": TOOLTIPS["blue"]},
        "tracer_remove": {"type": "tool", "label": "Remove Tracer", "icon": "tracer_remove", "callback": api.remove_tracer, "tooltip": TOOLTIPS["remove"]},
        "tracer_connected": {
            "type": "check", "label": "Auto Update", "icon": "tracer",
            "callback": api.set_connected, "get_checked": api.is_connected,
            "set_checked": api.set_connected, "tooltip": TOOLTIPS["connected"],
        },
    }
    SECTION = {
            "id": "tracer_tools", "i18n_key": "create_tracer",
            "label": "Tracer", "color": COLORS.toolbar.red.hex,
            "items": [
                {"id": "create_tracer", "shortcuts": [
                    {"id": "tracer_refresh", "keys": [QtCore.Qt.Key_Control]},
                    {"id": "tracer_show_hide", "keys": [QtCore.Qt.Key_Shift]},
                    {"id": "tracer_remove", "keys": [QtCore.Qt.Key_Control, QtCore.Qt.Key_Alt]},
                ]},
                {"id": "tracer_connected"}, "separator",
                {"id": "tracer_refresh"}, {"id": "tracer_show_hide"}, {"id": "tracer_offset_node"}, "separator",
                {"id": "tracer_grey"}, {"id": "tracer_red"}, {"id": "tracer_blue"}, "separator", {"id": "tracer_remove"},
            ],
        }
