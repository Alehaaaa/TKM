from TheKeyMachine.core.Qt import QtCore  # type: ignore

from TheKeyMachine.tools.registry import ToolObject, load_tooltips
from TheKeyMachine.data.colors import COLORS
import TheKeyMachine.core.application as general
from TheKeyMachine.tools.link_objects import api


TOOLTIPS = load_tooltips(__file__)


class LinkObjectsToolObject(ToolObject):
    ORDER = 480
    DOC_URL = "https://thekeymachine.gitbook.io/base/the-toolbar/animation-tools/link-objects"
    TOOLS = {
        "link_copy": {
            "type": "tool",
            "label": "Copy Relationship",
            "icon": "link_relative",
            "callback": api.copy_relationship,
            "tooltip": TOOLTIPS["copy_relationship"],
        },
        "link_paste": {
            "type": "tool",
            "label": "Paste Relationship",
            "icon": "link_relative_paste",
            "callback": api.paste_relationship,
            "tooltip": TOOLTIPS["paste_relationship"],
        },
        "link_paste_range": {
            "type": "tool",
            "label": "Paste Relationship to Range",
            "icon": "link_relative_paste",
            "callback": api.paste_relationship_to_range,
            "tooltip": TOOLTIPS["paste_range"],
        },
        "link_autolink": {
            "type": "check",
            "state_key": "link_autolink",
            "label": "Auto Link",
            "icon": "link_relative_on",
            "callback": api.set_auto_link_enabled,
            "get_checked": api.is_auto_link_enabled,
            "set_checked": api.set_auto_link_enabled,
            "tooltip": TOOLTIPS["auto_link"],
        },
        "link_help": {
            "type": "tool",
            "label": "Copy Relationship Help",
            "icon": "help",
            "callback": lambda: general.open_url(LinkObjectsToolObject.DOC_URL),
            "tooltip": TOOLTIPS["help"],
            "pinnable": False,
        },
    }
    SECTION = {
        "id": "link_tools",
        "label": "Relationships & Worldspace",
        "color": COLORS.toolbar.green.hex,
        "items": [
            {"section": "relationship_tools"},
            {"section": "worldspace_tools"},
        ],
    }
    SECTIONS = ({
        "id": "relationship_tools",
        "label": "Relationships",
        "color": COLORS.toolbar.green.hex,
        "items": [
            {
                "id": "link_copy",
                "shortcuts": [
                    {"id": "link_paste", "keys": [QtCore.Qt.Key_Control]},
                    {"id": "link_paste_range", "keys": [QtCore.Qt.Key_Shift]},
                    {"id": "link_autolink", "keys": [QtCore.Qt.Key_Alt]},
                ],
            },
            {"id": "link_paste"},
            {"id": "link_paste_range"},
            "separator",
            {"id": "link_autolink"},
            "separator",
            {"id": "link_help"},
        ],
    },)
