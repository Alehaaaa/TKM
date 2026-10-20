from TheKeyMachine.tools.registry import ToolObject, load_tooltips
from TheKeyMachine.data.colors import COLORS
from TheKeyMachine.tools.manipulators import api


TOOLTIPS = load_tooltips(__file__)


class ManipulatorsToolObject(ToolObject):
    ORDER = 475
    TOOLS = {
        "smart_rotation": {
            "type": "tool", "label": "Smart Rotation", "icon": "slider_tangent/tangent_auto",
            "callback": api.smart_rotation, "tooltip": TOOLTIPS["smart_rotation"],
            "keywords": ["smart orientation", "smart rotate channels"],
        },
        "smart_rotation_release": {
            "type": "tool", "label": "Smart Rotation Release", "icon": "slider_tangent/tangent_auto",
            "callback": api.smart_rotation_release, "tooltip": TOOLTIPS["smart_rotation_release"],
            "keywords": ["smart orientation release", "smart rotate channels release"],
        },
        "smart_translation": {
            "type": "tool", "label": "Smart Translation", "icon": "cube",
            "callback": api.smart_translation, "tooltip": TOOLTIPS["smart_translation"],
            "keywords": ["smart position", "smart translate channels"],
        },
        "smart_translation_release": {
            "type": "tool", "label": "Smart Translation Release", "icon": "cube",
            "callback": api.smart_translation_release, "tooltip": TOOLTIPS["smart_translation_release"],
            "keywords": ["smart position release", "smart translate channels release"],
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
