from TheKeyMachine.core.toolbox import ToolObject, load_tooltips
from TheKeyMachine.data.colors import COLORS
from TheKeyMachine.tools.manipulators import api


TOOLTIPS = load_tooltips(__file__)


class ManipulatorsToolObject(ToolObject):
    ORDER = 475
    TOOLS = {
        "smart_rotation": {
            "type": "tool", "label": "Smart Rotation", "icon": "tangent_auto",
            "callback": api.smart_rotation, "tooltip": TOOLTIPS["smart_rotation"],
        },
        "smart_rotation_release": {
            "type": "tool", "label": "Smart Rotation Release", "icon": "tangent_auto",
            "callback": api.smart_rotation_release, "tooltip": TOOLTIPS["smart_rotation_release"],
        },
        "smart_translation": {
            "type": "tool", "label": "Smart Translation", "icon": "cube",
            "callback": api.smart_translation, "tooltip": TOOLTIPS["smart_translation"],
        },
        "smart_translation_release": {
            "type": "tool", "label": "Smart Translation Release", "icon": "cube",
            "callback": api.smart_translation_release, "tooltip": TOOLTIPS["smart_translation_release"],
        },
    }
    SECTION = {
        "id": "manipulator_tools",
        "label": "Manipulators",
        "color": COLORS.toolbar.purple.hex,
        "items": [
            {"id": "smart_rotation"},
            {"id": "smart_rotation_release"},
            {"id": "smart_translation"},
            {"id": "smart_translation_release"},
        ],
    }
