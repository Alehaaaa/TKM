from TheKeyMachine.tools.registry import ToolObject, load_tooltips
from TheKeyMachine.tools.orbit import api


TOOLTIPS = load_tooltips(__file__)


class OrbitToolObject(ToolObject):
    ORDER = 1000
    TOOLS = {
        "orbit": {
            "type": "check",
            "state_key": "orbit",
            "label": "Orbit",
            "text": "Orb",
            "icon": "orbit_ui",
            "callback": api.toggle,
            "get_checked": api.is_orbit_window_open,
            "set_checked": api.toggle,
            "bind_checked_fn": api.bind_orbit_toolbar_button,
            "tooltip": TOOLTIPS["orbit"],
        },
        "orbit_window": {
            "type": "tool",
            "label": "Orbit Window",
            "icon": "orbit_ui",
            "callback": api.orbit_window,
            "tooltip": TOOLTIPS["orbit"],
        },
    }
    SECTION = {
        "id": "orbit_tools", "i18n_key": "orbit",
        "label": "Orbit",
        "items": [{"id": "orbit"}],
    }
