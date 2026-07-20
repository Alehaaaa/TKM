from functools import partial

from TheKeyMachine.core.Qt import QtCore  # type: ignore
from TheKeyMachine.core.toolbox import ToolObject, load_tooltips
from TheKeyMachine.data.colors import COLORS
from TheKeyMachine.tools.tangents import api


TOOLTIPS = load_tooltips(__file__)


def _tooltip(tooltip_key, tangent_label=None):
    values = TOOLTIPS[tooltip_key]
    if not tangent_label:
        return values
    return [value.replace("{tangent}", tangent_label) if isinstance(value, str) else value for value in values]


def _scope_action(label, callback, tooltip_key, tangent_label=None):
    return {"label": label, "callback": callback, "tooltip": _tooltip(tooltip_key, tangent_label)}


def _tangent_tool(tangent_type, label, text, maya_default=True):
    setter = api.set_bouncy if tangent_type == "bouncy" else partial(api.set_tangent, tangent_type)
    menu_items = []
    if tangent_type != "step":
        menu_items.extend([
            _scope_action("In Tangent", partial(setter, handle_mode="in"), "in", label),
            _scope_action("Out Tangent", partial(setter, handle_mode="out"), "out", label),
            "separator",
            _scope_action("First Key", partial(setter, key_scope="first"), "first", label),
            _scope_action("Last Key", partial(setter, key_scope="last"), "last", label),
            "separator",
        ])
    menu_items.append(_scope_action("All Keys", partial(setter, key_scope="all"), "all", label))
    if maya_default:
        menu_items.append(
            _scope_action("Set Maya Default Tangent", partial(api.set_maya_default, tangent_type), "default", label)
        )
    return {
        "type": "tool",
        "label": label,
        "text": text,
        "icon": "tangent_{}".format(tangent_type),
        "callback": setter,
        "tooltip": TOOLTIPS[tangent_type],
        "menu": {"label": label, "icon": "tangent_{}".format(tangent_type), "items": menu_items},
    }


def _shortcuts(tangent_type, maya_default=True):
    setter = api.set_bouncy if tangent_type == "bouncy" else partial(api.set_tangent, tangent_type)
    variants = []
    if maya_default:
        variants.append({
            "id": "tangent_{}_default".format(tangent_type),
            "label": "Set Maya Default Tangent",
            "keys": [QtCore.Qt.Key_Control],
            "callback": partial(api.set_maya_default, tangent_type),
        })
    if tangent_type != "step":
        variants.extend([
            {"id": "tangent_{}_both".format(tangent_type), "label": "{} Both Ends".format(tangent_type.title()), "keys": [QtCore.Qt.Key_Alt, QtCore.Qt.Key_Shift], "callback": setter},
            {"id": "tangent_{}_first".format(tangent_type), "label": "{} First Key".format(tangent_type.title()), "keys": [QtCore.Qt.Key_Shift], "callback": partial(setter, key_scope="first")},
            {"id": "tangent_{}_in".format(tangent_type), "label": "{} In".format(tangent_type.title()), "keys": [QtCore.Qt.Key_Control, QtCore.Qt.Key_Shift], "callback": partial(setter, handle_mode="in")},
            {"id": "tangent_{}_last".format(tangent_type), "label": "{} Last Key".format(tangent_type.title()), "keys": [QtCore.Qt.Key_Alt], "callback": partial(setter, key_scope="last")},
            {"id": "tangent_{}_out".format(tangent_type), "label": "{} Out".format(tangent_type.title()), "keys": [QtCore.Qt.Key_Control, QtCore.Qt.Key_Alt], "callback": partial(setter, handle_mode="out")},
        ])
    variants.append({
        "id": "tangent_{}_all".format(tangent_type),
        "label": "{} All Keys".format(tangent_type.title()),
        "keys": [QtCore.Qt.Key_Control, QtCore.Qt.Key_Shift, QtCore.Qt.Key_Alt],
        "callback": partial(setter, key_scope="all"),
    })
    return variants


class TangentsToolObject(ToolObject):
    ORDER = 350
    TOOLS = {
        "tangent_cycle_matcher": {
            "type": "tool", "label": "Cycle Matcher", "text": "CM",
            "icon": "match_curve_cycle", "callback": api.match_cycle,
            "tooltip": TOOLTIPS["cycle"],
            "menu": {"label": "Cycle Matcher", "icon": "match_curve_cycle", "items": [
                _scope_action("Match First Key", partial(api.match_cycle, target_key="first"), "cycle_first"),
                _scope_action("Match Last Key", partial(api.match_cycle, target_key="last"), "cycle_last"),
            ]},
        },
        "tangent_bouncy": _tangent_tool("bouncy", "Bouncy Tangent", "BO", maya_default=False),
        "tangent_auto": _tangent_tool("auto", "Auto Tangent", "AU"),
        "tangent_spline": _tangent_tool("spline", "Spline Tangent", "SP"),
        "tangent_clamped": _tangent_tool("clamped", "Clamped Tangent", "CL"),
        "tangent_linear": _tangent_tool("linear", "Linear Tangent", "LI"),
        "tangent_flat": _tangent_tool("flat", "Flat Tangent", "FT"),
        "tangent_step": _tangent_tool("step", "Step Tangent", "ST"),
        "tangent_plateau": _tangent_tool("plateau", "Plateau Tangent", "PT"),
    }
    SECTION = {
        "id": "tangents", "label": "Tangents", "icon": "tangent_auto",
        "color": COLORS.toolbar.orange.hex,
        "items": [
            {"id": "tangent_cycle_matcher"},
            {"id": "tangent_bouncy", "shortcuts": _shortcuts("bouncy", False)},
            "separator",
            {"id": "tangent_auto", "shortcuts": _shortcuts("auto")},
            {"id": "tangent_spline", "shortcuts": _shortcuts("spline")},
            {"id": "tangent_clamped", "shortcuts": _shortcuts("clamped")},
            {"id": "tangent_linear", "shortcuts": _shortcuts("linear")},
            {"id": "tangent_flat", "shortcuts": _shortcuts("flat")},
            {"id": "tangent_step", "shortcuts": _shortcuts("step")},
            {"id": "tangent_plateau", "shortcuts": _shortcuts("plateau")},
        ],
    }

