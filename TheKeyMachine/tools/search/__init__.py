from TheKeyMachine.core.toolbox import ToolObject, load_tooltips
from TheKeyMachine.tools.search import api


TOOLTIPS = load_tooltips(__file__)


class SearchToolObject(ToolObject):
    ORDER = 10000
    TOOLS = {
        "search_window": {
            "type": "check",
            "state_key": "search",
            "label": "Search",
            "icon": "search",
            "callback": api.toggle,
            "get_checked": api.is_search_window_open,
            "set_checked": api.set_search_window_open,
            "bind_checked_fn": api.bind_search_toolbar_button,
            "tooltip": TOOLTIPS["search"],
        },
    }
    SECTION = {
        "id": "search_tools",
        "label": "Search",
        "hiddeable": True,
        "items": [{"id": "search_window"}],
    }
