from TheKeyMachine.core.Qt import QtCore  # type: ignore
from TheKeyMachine.core import i18n

from TheKeyMachine.tools.registry import ToolObject, load_tooltips
from TheKeyMachine.data.colors import COLORS
from TheKeyMachine.tools.temporal_controls import api

TOOLTIPS = load_tooltips(__file__)


def _bake_mode_choices():
    choices = (
        (
            "keys",
            "Bake Keys",
            "Bake copies only the control's existing keyframes onto its object.",
        ),
        (
            "frames",
            "Bake Frames",
            "Bake samples every frame across the control's animated range onto its object.",
        ),
    )
    localized = []
    for value, label, description in choices:
        label, description, _tooltip = i18n.localize_menu_action(
            "temporal_controls_bake_mode_{}".format(value),
            __file__,
            label,
            description=description,
        )
        localized.append({"value": value, "label": label, "description": description})
    return localized


class TemporalControlsToolObject(ToolObject):
    ORDER = 625
    TOOLS = {
        "temporal_controls": {
            "type": "tool",
            "label": "Temporal Controls",
            "icon": "temporal_controls",
            "callback": api.create_controls,
            "tooltip": TOOLTIPS["temporal_controls"],
            "menu": {
                "label": "Temporal Controls",
                "icon": "temporal_controls",
                "items": [
                    {
                        "type": "choice",
                        "id": "temporal_controls_bake_mode",
                        "get_value": api.get_bake_mode,
                        "set_value": api.set_bake_mode,
                        "items": _bake_mode_choices,
                    },
                    {"type": "check", "command": "temporal_controls_super_mode"},
                    "separator",
                    "temporal_controls_world_space",
                    "temporal_controls_object_space",
                    "temporal_controls_camera_space",
                    "temporal_controls_relative_space",
                    "temporal_controls_child_space",
                    "separator",
                    "temporal_controls_mute_revert",
                    "temporal_controls_mute_bake",
                    "temporal_controls_revert",
                    "temporal_controls_bake",
                    "separator",
                    "temporal_controls_panel",
                ],
            },
            "operation": {"progress": False, "undo": False},
        },
        "temporal_controls_create_apply": {
            "type": "tool",
            "label": "Create Temporal Controls",
            "callback": api.create_controls_with_options,
            "pinnable": False,
            "operation": {
                "rollback_on_cancel": True,
                "suspend_refresh": True,
            },
        },
        "temporal_controls_super_mode": {
            "type": "check",
            "label": "Super Mode",
            "icon": "temporal_controls",
            "callback": api.set_super_mode_enabled,
            "get_checked": api.is_super_mode_enabled,
            "set_checked": api.set_super_mode_enabled,
            "tooltip": TOOLTIPS["temporal_controls_super_mode"],
            "operation": {"progress": False, "undo": False},
        },
        "temporal_controls_world_space": {
            "type": "tool",
            "label": "World Space",
            "icon": "temporal_controls",
            "callback": api.switch_controls_to_world_space,
            "tooltip": TOOLTIPS["temporal_controls_world_space"],
        },
        "temporal_controls_object_space": {
            "type": "tool",
            "label": "Object Space",
            "icon": "temporal_controls",
            "callback": api.switch_controls_to_object_space,
            "tooltip": TOOLTIPS["temporal_controls_object_space"],
        },
        "temporal_controls_camera_space": {
            "type": "tool",
            "label": "Camera Space",
            "icon": "temporal_controls",
            "callback": api.switch_controls_to_camera_space,
            "tooltip": TOOLTIPS["temporal_controls_camera_space"],
        },
        "temporal_controls_relative_space": {
            "type": "tool",
            "label": "Relative Space",
            "icon": "temporal_controls",
            "callback": api.switch_controls_to_relative_space,
            "tooltip": TOOLTIPS["temporal_controls_relative_space"],
        },
        "temporal_controls_child_space": {
            "type": "tool",
            "label": "Child Space",
            "icon": "temporal_controls",
            "callback": api.switch_controls_to_child_space,
            "tooltip": TOOLTIPS["temporal_controls_child_space"],
        },
        "temporal_controls_mute_revert": {
            "type": "tool",
            "label": "Mute and Revert",
            "icon": "temporal_controls_mute_revert",
            "callback": api.mute_and_revert,
            "tooltip": TOOLTIPS["temporal_controls_mute_revert"],
        },
        "temporal_controls_mute_bake": {
            "type": "tool",
            "label": "Mute and Bake",
            "icon": "temporal_controls_mute_bake",
            "callback": api.mute_and_bake,
            "tooltip": TOOLTIPS["temporal_controls_mute_bake"],
        },
        "temporal_controls_bake": {
            "type": "tool",
            "label": "Remove and Bake",
            "icon": "temporal_controls_bake",
            "callback": api.bake_controls,
            "tooltip": TOOLTIPS["temporal_controls_bake"],
        },
        "temporal_controls_revert": {
            "type": "tool",
            "label": "Remove and Revert",
            "icon": "temporal_controls_revert",
            "callback": api.revert_controls,
            "tooltip": TOOLTIPS["temporal_controls_revert"],
        },
        "temporal_controls_panel": {
            "type": "tool",
            "label": "Temporal Controls Panel",
            "icon": "temporal_controls_panel",
            "callback": api.open_temp_controls_panel,
            "tooltip": TOOLTIPS["temporal_controls_panel"],
        },
    }
    SECTION = {
        "id": "temporal_controls_tools",
        "i18n_key": "temporal_controls",
        "label": "Temporal Controls",
        "color": COLORS.toolbar.turquoise.hex,
        "items": [
            {
                "id": "temporal_controls",
                "shortcuts": [
                    {"id": "temporal_controls_bake", "keys": [QtCore.Qt.Key_Shift]},
                    {
                        "id": "temporal_controls_revert",
                        "keys": [
                            QtCore.Qt.Key_Control,
                            QtCore.Qt.Key_Shift,
                            QtCore.Qt.Key_Alt,
                        ],
                    },
                    {"id": "temporal_controls_mute_bake", "keys": [QtCore.Qt.Key_Alt]},
                    {
                        "id": "temporal_controls_panel",
                        "keys": [QtCore.Qt.Key_Control, QtCore.Qt.Key_Shift],
                    },
                ],
            },
        ],
    }
