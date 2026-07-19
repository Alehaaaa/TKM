from TheKeyMachine.core.Qt import QtCore  # type: ignore
from TheKeyMachine.core.toolbox import ToolObject, load_tooltips
from TheKeyMachine.mods import generalMod as general
from TheKeyMachine.tools.isolate import api


TOOLTIPS = load_tooltips(__file__)


class IsolateToolObject(ToolObject):
    ORDER = 850
    DOC_URL = "https://thekeymachine.gitbook.io/base/the-toolbar/animation-tools/isolate"
    TOOLS = {
        "isolate_master": {
            "type": "tool", "label": "Isolate", "icon": "isolate",
            "callback": api.isolate_master, "tooltip": TOOLTIPS["isolate"],
            "menu": {
                "label": "Isolate", "icon": "isolate",
                "items": ["isolate_bookmarks", "isolate_down_level", "separator", "isolate_help"],
            },
        },
        "isolate_bookmarks": {
            "type": "tool", "label": "Isolate Bookmarks",
            "icon": "isolate_bookmarks",
            "callback": api.create_isolate_bookmarks_window,
            "tooltip": TOOLTIPS["isolate_bookmarks"],
        },
        "isolate_down_level": {
            "type": "check", "label": "Down one level", "text": "D1",
            "icon": "isolate", "callback": api.toggle_down_one_level,
            "get_checked": api.is_down_one_level,
            "set_checked": api.set_down_one_level,
            "tooltip": TOOLTIPS["down_level"],
        },
        "isolate_help": {
            "type": "tool", "label": "Help", "icon": "help", "pinnable": False,
            "callback": lambda: general.open_url(IsolateToolObject.DOC_URL),
            "tooltip": TOOLTIPS["help"],
        },
    }
    SECTION = {
        "id": "isolate_tools",
        "label": "Isolate",
        "items": [
            {
                "id": "isolate_master",
                "shortcuts": [{"id": "isolate_bookmarks", "keys": [QtCore.Qt.Key_Control]}],
            },
            {"id": "isolate_bookmarks"},
            "separator",
            {"id": "isolate_down_level"},
            "separator",
            {"id": "isolate_help"},
        ],
    }

