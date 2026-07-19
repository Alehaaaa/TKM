from TheKeyMachine.core.Qt import QtCore  # type: ignore
from TheKeyMachine.core.toolbox import ToolObject, load_tooltips
from TheKeyMachine.data import colors as toolColors
import TheKeyMachine.mods.generalMod as general
from TheKeyMachine.tools.default_values import api


TOOLTIPS = load_tooltips(__file__)


class DefaultValuesToolObject(ToolObject):
    ORDER = 200
    DOC_URL = "https://thekeymachine.gitbook.io/base/the-toolbar/animation-tools/default-to-default"
    TOOLS = {
        "default_object_values": {"type": "tool", "label": "Default Pose", "icon": "default", "callback": api.apply_all, "tooltip": TOOLTIPS["all"]},
        "default_translations": {"type": "tool", "label": "Default Translations", "text": "RT", "icon": "default", "callback": api.apply_translations, "tooltip": TOOLTIPS["translations"]},
        "default_rotations": {"type": "tool", "label": "Default Rotations", "text": "RR", "icon": "default", "callback": api.apply_rotations, "tooltip": TOOLTIPS["rotations"]},
        "default_scales": {"type": "tool", "label": "Default Scales", "text": "RS", "icon": "default", "callback": api.apply_scales, "tooltip": TOOLTIPS["scales"]},
        "default_trs": {"type": "tool", "label": "Default Translation Rotation Scale", "text": "RTRS", "icon": "default", "callback": api.apply_trs, "tooltip": TOOLTIPS["trs"]},
        "default_set_defaults": {"type": "tool", "label": "Save Defaults for Selected", "icon": "default", "callback": api.save_selected, "tooltip": TOOLTIPS["save"]},
        "default_restore_defaults": {"type": "tool", "label": "Remove Saved Defaults for Selected", "icon": "default", "callback": api.remove_selected, "tooltip": TOOLTIPS["remove"]},
        "default_clear_all": {"type": "tool", "label": "Clear All Saved Defaults", "icon": "default", "callback": api.clear_all, "tooltip": TOOLTIPS["clear"]},
        "default_help": {"type": "tool", "label": "Help", "icon": "help", "callback": lambda: general.open_url(DefaultValuesToolObject.DOC_URL), "tooltip": TOOLTIPS["help"], "pinnable": False},
    }
    SECTION = {
        "id": "default_tools", "label": "Default", "color": toolColors.TOOLBAR_GREEN,
        "items": [
            {"id": "default_object_values", "shortcuts": [
                {"id": "default_translations", "keys": [QtCore.Qt.Key_Shift]},
                {"id": "default_rotations", "keys": [QtCore.Qt.Key_Control]},
                {"id": "default_scales", "keys": [QtCore.Qt.Key_Alt]},
                {"id": "default_trs", "keys": [QtCore.Qt.Key_Control, QtCore.Qt.Key_Shift]},
                {"id": "default_set_defaults", "keys": [QtCore.Qt.Key_Alt, QtCore.Qt.Key_Control, QtCore.Qt.Key_Shift]},
            ]},
            {"id": "default_translations"}, {"id": "default_rotations"},
            {"id": "default_scales"}, {"id": "default_trs"}, "separator",
            {"id": "default_set_defaults"}, {"id": "default_restore_defaults"},
            "separator", {"id": "default_clear_all"}, "separator", {"id": "default_help"},
        ],
    }

