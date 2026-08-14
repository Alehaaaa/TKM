from TheKeyMachine.tools.registry import ToolObject, load_tooltips
from TheKeyMachine.tools.animation_recovery import api


TOOLTIPS = load_tooltips(__file__)


class AnimationRecoveryToolObject(ToolObject):
    ORDER = 970
    TOOLS = {
        "animation_recovery": {
            "type": "tool",
            "label": "Animation Recovery",
            "icon": "animation_recovery",
            "callback": api.show,
            "tooltip": TOOLTIPS["animation_recovery"],
            "operation": {"progress": False, "undo": False},
        },
    }
    SECTION = {
        "id": "animation_recovery_tools", "i18n_key": "animation_recovery",
        "label": "Animation Recovery",
        "items": [{"id": "animation_recovery"}],
    }
