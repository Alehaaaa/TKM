from TheKeyMachine.core.toolbox import ToolObject, load_tooltips
from TheKeyMachine.data import colors as toolColors
from TheKeyMachine.tools.attribute_switcher import api


TOOLTIPS = load_tooltips(__file__)


class AttributeSwitcherToolObject(ToolObject):
    ORDER = 800
    TOOLS = {
        "attribute_switcher": {
            "type": "check",
            "state_key": "attribute_switcher",
            "label": "Attribute Switcher",
            "text": "SSw",
            "icon": "attribute_switcher",
            "callback": api.toggle_window,
            "get_checked": api.is_attribute_switcher_window_open,
            "set_checked": api.toggle_window,
            "bind_checked_fn": api.bind_attribute_switcher_toolbar_button,
            "tooltip": TOOLTIPS["attribute_switcher"],
        },
    }
    SECTION = {
        "id": "attribute_tools",
        "label": "Attribute Switcher",
        "color": toolColors.TOOLBAR_GREEN,
        "items": [{"id": "attribute_switcher"}, {"id": "gimbal"}],
    }
