from TheKeyMachine.tools.registry import ToolObject, load_tooltips
from TheKeyMachine.data.colors import COLORS
from TheKeyMachine.tools.global_curve import api


TOOLTIPS = load_tooltips(__file__)


class GlobalCurveToolObject(ToolObject):
    ORDER = 710
    TOOLS = {
        "global_curve": {
            "type": "check", "label": "Global Curve", "icon": "global_curve",
            "state_key": "global_curve",
            "callback": api.set_enabled, "get_checked": api.has_global_curves,
            "set_checked": api.set_enabled, "tooltip": TOOLTIPS["global_curve"],
            "menu": {"label": "Global Curve", "icon": "global_curve", "items": [
                "global_curve_create", "global_curve_remove", "global_curve_edit",
                "separator",
                {
                    "type": "choice", "id": "global_curve_tangents",
                    "get_value": api.get_tangent_mode, "set_value": api.set_tangent_mode,
                    "items": api.tangent_mode_choices,
                },
                "separator",
                {"type": "check", "command": "global_curve_affect_time"},
                {"type": "check", "command": "global_curve_snap_keys"},
            ]},
        },
        "global_curve_create": {
            "type": "tool", "label": "Create", "icon": "global_curve",
            "callback": api.create_additional, "tooltip": TOOLTIPS["create"],
        },
        "global_curve_remove": {
            "type": "tool", "label": "Remove", "icon": "global_curve",
            "callback": api.remove_all, "tooltip": TOOLTIPS["remove"],
        },
        "global_curve_edit": {
            "type": "tool", "label": "Edit", "icon": "global_curve",
            "callback": api.recapture_active, "tooltip": TOOLTIPS["edit"],
        },
        "global_curve_affect_time": {
            "type": "check", "label": "Affect Time", "icon": "global_curve",
            "callback": api.set_affect_time, "get_checked": api.get_affect_time,
            "set_checked": api.set_affect_time, "tooltip": TOOLTIPS["affect_time"],
        },
        "global_curve_snap_keys": {
            "type": "check", "label": "Snap Keys", "icon": "global_curve",
            "callback": api.set_snap_keys, "get_checked": api.get_snap_keys,
            "set_checked": api.set_snap_keys, "tooltip": TOOLTIPS["snap_keys"],
        },
    }
    SECTION = {
        "id": "global_curve_tools", "label": "Global Curve",
        "color": COLORS.toolbar.red.hex,
        "items": [{"id": "global_curve"}],
    }
