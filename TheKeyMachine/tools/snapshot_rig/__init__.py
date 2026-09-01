from TheKeyMachine.core.Qt import QtCore  # type: ignore
from TheKeyMachine.tools.registry import ToolObject, load_tooltips
from TheKeyMachine.data.colors import COLORS
import TheKeyMachine.core.application as general
from TheKeyMachine.tools.snapshot_rig import api

TOOLTIPS = load_tooltips(__file__)


class SnapshotRigToolObject(ToolObject):
    OPERATION = {"capture_animation_context": True}
    ORDER = 970
    DOC_URL = (
        "https://thekeymachine.gitbook.io/base/the-toolbar/animation-tools/snapshot-rig"
    )

    TOOLS = {
        "snapshot_rig": {
            "type": "tool",
            "label": "Snapshot Rig",
            "icon": "snapshot",
            "callback": api.snapshot_rig,
            "tooltip": TOOLTIPS["rig"],
            "operation": {"undo": False, "suspend_refresh": True},
        },
        "snapshot_default": {
            "type": "tool",
            "label": "Snapshot Default",
            "icon": "snapshot_default",
            "callback": api.snapshot_default,
            "tooltip": TOOLTIPS["default"],
            "menu": {
                "label": "Snapshot Default",
                "icon": "snapshot_default",
                "items": ["default_restore_defaults", "default_clear_all"],
            },
            "operation": {"undo": False, "suspend_refresh": True},
        },
        "snapshot_opposite": {
            "type": "tool",
            "label": "Snapshot Opposite",
            "icon": "snapshot_opposite",
            "callback": api.snapshot_opposite,
            "tooltip": TOOLTIPS["opposite"],
            "menu": {
                "label": "Snapshot Opposite",
                "icon": "snapshot_opposite",
                "items": [
                    "snapshot_opposite_remove_selected",
                    "snapshot_opposite_clear_all",
                ],
            },
            "operation": {"undo": False, "suspend_refresh": True},
        },
        "snapshot_mirror": {
            "type": "tool",
            "label": "Snapshot Mirror",
            "icon": "snapshot_mirror",
            "callback": api.snapshot_mirror,
            "tooltip": TOOLTIPS["mirror"],
            "menu": {
                "label": "Snapshot Mirror",
                "icon": "snapshot_mirror",
                "items": [
                    "snapshot_mirror_remove_selected",
                    "snapshot_mirror_clear_all",
                ],
            },
            "operation": {"undo": False, "suspend_refresh": True},
        },
        "snapshot_opposite_remove_selected": {
            "type": "tool",
            "label": "Remove Selected Opposite Snapshots",
            "icon": "snapshot_opposite",
            "callback": api.remove_selected_opposites,
            "tooltip": TOOLTIPS["remove_selected_opposite"],
            "pinnable": False,
            "operation": {"undo": False},
        },
        "snapshot_opposite_clear_all": {
            "type": "tool",
            "label": "Clear All Opposite Snapshots",
            "icon": "snapshot_opposite",
            "callback": api.clear_all_opposites,
            "tooltip": TOOLTIPS["clear_all_opposite"],
            "pinnable": False,
            "operation": {"undo": False},
        },
        "snapshot_mirror_remove_selected": {
            "type": "tool",
            "label": "Remove Selected Mirror Snapshots",
            "icon": "snapshot_mirror",
            "callback": api.remove_selected_mirrors,
            "tooltip": TOOLTIPS["remove_selected_mirror"],
            "pinnable": False,
            "operation": {"undo": False},
        },
        "snapshot_mirror_clear_all": {
            "type": "tool",
            "label": "Clear All Mirror Snapshots",
            "icon": "snapshot_mirror",
            "callback": api.clear_all_mirrors,
            "tooltip": TOOLTIPS["clear_all_mirror"],
            "pinnable": False,
            "operation": {"undo": False},
        },
        "snapshot_help": {
            "type": "tool",
            "label": "Help",
            "icon": "help",
            "pinnable": False,
            "callback": lambda: general.open_url(SnapshotRigToolObject.DOC_URL),
            "tooltip": TOOLTIPS["help"],
        },
    }

    SECTION = {
        "id": "snapshot_rig_tools",
        "label": "Snapshot",
        "color": COLORS.toolbar.light_gray.hex,
        "items": [
            {"id": "snapshot_rig"},
            {
                "id": "snapshot_default",
                "shortcuts": [
                    {"id": "default_restore_defaults", "keys": [QtCore.Qt.Key_Shift]},
                    {
                        "id": "default_clear_all",
                        "keys": [QtCore.Qt.Key_Control, QtCore.Qt.Key_Shift],
                    },
                ],
            },
            {
                "id": "snapshot_opposite",
                "shortcuts": [
                    {
                        "id": "snapshot_opposite_remove_selected",
                        "keys": [QtCore.Qt.Key_Shift],
                    },
                    {
                        "id": "snapshot_opposite_clear_all",
                        "keys": [QtCore.Qt.Key_Control, QtCore.Qt.Key_Shift],
                    },
                ],
            },
            {
                "id": "snapshot_mirror",
                "shortcuts": [
                    {
                        "id": "snapshot_mirror_remove_selected",
                        "keys": [QtCore.Qt.Key_Shift],
                    },
                    {
                        "id": "snapshot_mirror_clear_all",
                        "keys": [QtCore.Qt.Key_Control, QtCore.Qt.Key_Shift],
                    },
                ],
            },
            "separator",
            {"id": "snapshot_help"},
        ],
    }
