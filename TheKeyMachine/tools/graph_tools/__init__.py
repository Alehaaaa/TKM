from TheKeyMachine.core.Qt import QtCore  # type: ignore
from TheKeyMachine.tools.registry import ToolObject, load_tooltips
from TheKeyMachine.data.colors import COLORS
from TheKeyMachine.tools.graph_tools import api


TOOLTIPS = load_tooltips(__file__)


class GraphToolsToolObject(ToolObject):
    ORDER = 940
    OPERATION = {"capture_animation_context": True}
    TOOLS = {
        "graph_extra_tools": {
            "type": "menu", "label": "Graph Extras", "text": "E",
            "tooltip": TOOLTIPS["extras"],
            "menu": {"label": "Graph Extras", "items": [
                "graph_select_object_from_curve", "graph_isolate_curves", "separator",
                "graph_flip", "graph_overlap_forward", "graph_overlap_backward", "separator",
                "graph_toggle_mute", "graph_toggle_lock", "graph_match_keys", "separator",
                "enable_graph_filter", "disable_graph_filter",
            ]},
        },
        "graph_select_object_from_curve": {
            "type": "tool", "label": "Select Object from Curve", "icon": "isolate",
            "callback": api.select_objects_from_selected_curves,
            "tooltip": TOOLTIPS["select_object"],
        },
        "graph_isolate_curves": {
            "type": "tool", "label": "Isolate Curves", "icon": "isolate",
            "callback": api.isolate_curves, "tooltip": TOOLTIPS["isolate"],
        },
        "graph_flip": {
            "type": "tool", "label": "Flip Curves", "text": "F",
            "callback": api.flip_curves, "tooltip": TOOLTIPS["flip"],
        },
        "graph_overlap_forward": {
            "type": "tool", "label": "Overlap Forward", "text": "O>",
            "callback": api.overlap_forward, "tooltip": TOOLTIPS["overlap"],
        },
        "graph_overlap_backward": {
            "type": "tool", "label": "Overlap Backward", "text": "O<",
            "callback": api.overlap_backward, "tooltip": TOOLTIPS["overlap"],
        },
        "graph_toggle_mute": {
            "type": "tool", "label": "Mute Curves", "text": "Mt",
            "callback": api.toggle_mute, "tooltip": TOOLTIPS["mute"],
        },
        "graph_toggle_lock": {
            "type": "tool", "label": "Lock Curves", "text": "Lk",
            "callback": api.toggle_lock, "tooltip": TOOLTIPS["lock"],
        },
        "graph_match_keys": {
            "type": "tool", "label": "Match Curves", "text": "M", "icon": "align",
            "callback": api.match_keys, "tooltip": TOOLTIPS["match"],
        },
        "enable_graph_filter": {
            "type": "tool", "label": "Enable Graph Filter", "text": "EnF",
            "callback": api.enable_filter, "tooltip": TOOLTIPS["filter"],
        },
        "disable_graph_filter": {
            "type": "tool", "label": "Disable Graph Filter", "text": "DiF",
            "callback": api.disable_filter, "tooltip": TOOLTIPS["filter"],
        },
    }
    SECTION = {
        "id": "graph_tools", "label": "Graph Tools", "color": COLORS.toolbar.orange.hex,
        "items": [
            {"id": "graph_extra_tools"},
            {"id": "graph_select_object_from_curve"},
            {"id": "graph_isolate_curves"},
            "separator",
            {"id": "graph_flip"},
            {"id": "graph_overlap_forward", "shortcuts": [
                {"id": "graph_overlap_backward", "keys": [QtCore.Qt.Key_Shift]},
            ]},
            "separator",
            {"id": "graph_toggle_mute"},
            {"id": "graph_toggle_lock"},
            {"id": "graph_match_keys"},
            {"id": "enable_graph_filter", "shortcuts": [
                {"id": "disable_graph_filter", "keys": [QtCore.Qt.Key_Control]},
            ]},
        ],
    }
