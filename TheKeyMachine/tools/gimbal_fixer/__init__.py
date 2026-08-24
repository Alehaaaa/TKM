from TheKeyMachine.tools.registry import ToolObject, load_tooltips
from TheKeyMachine.tools.gimbal_fixer import api


TOOLTIPS = load_tooltips(__file__)


class GimbalFixerToolObject(ToolObject):
    ORDER = 810
    TOOLS = {
        "gimbal_convert_rotation_order": {
            "type": "tool",
            "label": "Convert Rotation Order",
            "callback": api.convert_rotation_order,
            "pinnable": False,
            "operation": {
                "capture_animation_context": True,
                "rollback_on_cancel": True,
                "suspend_refresh": True,
            },
        },
        "gimbal": {
            "type": "check",
            "state_key": "gimbal",
            "label": "Gimbal Fixer",
            "text": "Gim",
            "icon": "reblock",
            "callback": api.toggle,
            "get_checked": api.is_gimbal_fixer_window_open,
            "set_checked": api.toggle,
            "bind_checked_fn": api.bind_gimbal_fixer_toolbar_button,
            "tooltip": TOOLTIPS["gimbal"],
        },
    }
