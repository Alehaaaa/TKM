from TheKeyMachine.tools.registry import ToolObject, load_tooltips
import TheKeyMachine.core.application as general
from TheKeyMachine.tools.snapshot_rig import api


TOOLTIPS = load_tooltips(__file__)


class SnapshotRigToolObject(ToolObject):
    ORDER = 970
    DOC_URL = "https://thekeymachine.gitbook.io/base/the-toolbar/animation-tools/snapshot-rig"

    TOOLS = {
        "snapshot_rig": {
            "type": "tool", "label": "Snapshot Rig", "icon": "mirror",
            "callback": api.snapshot_rig, "tooltip": TOOLTIPS["rig"],
            "operation": {"undo": False, "suspend_refresh": True},
        },
        "snapshot_default": {
            "type": "tool", "label": "Snapshot Default", "icon": "default",
            "callback": api.snapshot_default, "tooltip": TOOLTIPS["default"],
            "operation": {"undo": False, "suspend_refresh": True},
        },
        "snapshot_opposite": {
            "type": "tool", "label": "Snapshot Opposite", "icon": "opposite_select",
            "callback": api.snapshot_opposite, "tooltip": TOOLTIPS["opposite"],
            "operation": {"undo": False, "suspend_refresh": True},
        },
        "snapshot_mirror": {
            "type": "tool", "label": "Snapshot Mirror", "icon": "mirror",
            "callback": api.snapshot_mirror, "tooltip": TOOLTIPS["mirror"],
            "operation": {"undo": False, "suspend_refresh": True},
        },
        "snapshot_help": {
            "type": "tool", "label": "Help", "icon": "help", "pinnable": False,
            "callback": lambda: general.open_url(SnapshotRigToolObject.DOC_URL),
            "tooltip": TOOLTIPS["help"],
        },
    }

    SECTION = {
        "id": "snapshot_rig_tools",
        "label": "Snapshot",
        "items": [
            {"id": "snapshot_rig"},
            {"id": "snapshot_default"},
            {"id": "snapshot_opposite"},
            {"id": "snapshot_mirror"},
            "separator",
            {"id": "snapshot_help"},
        ],
    }
