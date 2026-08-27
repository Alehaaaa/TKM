from TheKeyMachine.core.Qt import QtCore  # type: ignore
from TheKeyMachine.core import i18n

from TheKeyMachine.tools.registry import ToolObject, load_tooltips
from TheKeyMachine.data.colors import COLORS

# User-facing choice lists and their defaults, colocated with the menu/
# command definitions below that present them. Imported back by api.py
# and controller.py -- keep this above the `from ... import api` import
# a few lines down.
SYSTEMS = (
    {"id": "simple", "label": "Simple Control", "icon": "temporal_controls_simple"},
    {"id": "group", "label": "Group Control", "icon": "temporal_controls_group"},
    {"id": "aim", "label": "Aim Control", "icon": "temporal_controls_aim"},
    {
        "id": "fk_chain",
        "label": "FK Chain Control",
        "icon": "temporal_controls_fk_chain",
    },
    {"id": "more", "label": "More to come...", "disabled": True},
)
DEFAULT_SYSTEM = "simple"

SPACES = (
    {"id": "world", "label": "World Space"},
    {"id": "object", "label": "Object Space"},
    {"id": "camera", "label": "Camera Space"},
    {"id": "relative", "label": "Relative Space"},
    {"id": "child", "label": "Child Space"},
    {"id": "grab_release", "label": "Grab Release Space"},
)
DEFAULT_SPACE = "world"
# Live re-space menu list: every space except Grab Release, a one-shot concept not meant to switch back into.
SWITCHABLE_SPACES = tuple(space for space in SPACES if space["id"] != "grab_release")

DEFAULT_BAKE_MODE = "keys"

from TheKeyMachine.tools.temporal_controls import api

TOOLTIPS = load_tooltips(__file__)


def _bake_mode_choices():
    modes = (
        ("keys", "Bake Keys", "Bake copies only the control's existing keyframes onto its object."),
        ("frames", "Bake Frames", "Bake samples every frame across the control's animated range onto its object."),
    )
    localized = []
    for mode_id, label, description in modes:
        label, description, _tooltip = i18n.localize_menu_action(
            "temporal_controls_bake_mode_{}".format(mode_id), __file__, label, description=description
        )
        localized.append({"value": mode_id, "label": label, "description": description})
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
                    "temporal_controls_toggle_rig",
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
        "temporal_controls_toggle_rig": {
            "type": "tool",
            "label": "Toggle Rig",
            "icon": "temporal_controls",
            "callback": api.toggle_temporal_control_rigs,
            "tooltip": TOOLTIPS["temporal_controls_toggle_rig"],
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
        "color": COLORS.toolbar.cyan.hex,
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
            # Plain entries so every command in this tool shares the section's
            # tint instead of some falling back to the untinted default.
            {"id": "temporal_controls_create_apply"},
            {"id": "temporal_controls_super_mode"},
            {"id": "temporal_controls_world_space"},
            {"id": "temporal_controls_object_space"},
            {"id": "temporal_controls_camera_space"},
            {"id": "temporal_controls_relative_space"},
            {"id": "temporal_controls_child_space"},
            {"id": "temporal_controls_mute_revert"},
            {"id": "temporal_controls_toggle_rig"},
        ],
    }
