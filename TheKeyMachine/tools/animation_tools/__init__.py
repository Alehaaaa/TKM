from TheKeyMachine.core.toolbox import ToolObject, load_tooltips
from TheKeyMachine.data.colors import COLORS
from TheKeyMachine.tools.animation_tools import api


TOOLTIPS = load_tooltips(__file__)


class AnimationToolsToolObject(ToolObject):
    ORDER = 330
    DOC_URL = "https://thekeymachine.gitbook.io/base/the-toolbar/animation-tools"

    TOOLS = {
        "animation_tools": {
            "type": "menu", "label": "Anim Curve Tools", "text": "AT",
            "tooltip": TOOLTIPS["animation_tools"],
            "menu": {"label": "Anim Curve Tools", "items": [
                "set_smart_key", "set_smart_key_all_channels", "separator",
                "apply_smart_euler_filter", "snap", "reverse_animation", "separator",
                "clear_animation", "crop_animation", "remove_redundant_keys",
                "remove_static_anim_curves", "separator",
                "copy_keys", "cut_keys", "delete_keys", "paste_keys", "paste_keys_relative",
                "separator", "go_to_next_key", "go_to_previous_key",
                "go_to_next_frame", "go_to_previous_frame",
            ]},
        },
        "set_smart_key": {"type": "tool", "label": "Set Smart Key", "text": "S", "callback": api.set_smart_key, "tooltip": TOOLTIPS["smart_key"], "operation": {"preserve_time_selection": True}},
        "set_smart_key_all_channels": {"type": "tool", "label": "Set Smart Key All Channels", "text": "S+", "callback": api.set_smart_key_all_channels, "tooltip": TOOLTIPS["smart_key_all"], "operation": {"preserve_time_selection": True}},
        "apply_smart_euler_filter": {"type": "tool", "label": "Apply Smart Euler Filter", "icon": "euler_filter", "callback": api.apply_smart_euler_filter, "tooltip": TOOLTIPS["euler_filter"]},
        "snap": {"type": "tool", "label": "Snap Keys", "text": "SpK", "icon": "snap", "callback": api.snap_keyframes, "tooltip": TOOLTIPS["snap"]},
        "clear_animation": {"type": "tool", "label": "Clear Animation", "icon": "delete_animation", "callback": api.clear_animation_keys, "tooltip": TOOLTIPS["clear_animation"]},
        "delete_all_animation": {"type": "tool", "label": "Clear Animation", "icon": "delete_animation", "callback": api.clear_animation_keys, "tooltip": TOOLTIPS["clear_animation"]},
        "delete_static_animation": {"type": "tool", "label": "Remove Static Anim Curves", "icon": "delete_animation", "callback": api.remove_static_anim_curves, "tooltip": TOOLTIPS["remove_static"]},
        "crop_animation": {"type": "tool", "label": "Crop Animation", "icon": "isolate", "callback": api.crop_animation, "tooltip": TOOLTIPS["crop"]},
        "remove_redundant_keys": {
            "type": "tool", "label": "Remove Redundant Keys", "icon": "remove_redundant_keys",
            "callback": api.remove_redundant_keys, "tooltip": TOOLTIPS["remove_redundant"],
            "menu": {"label": "Remove Redundant Keys", "icon": "remove_redundant_keys", "items": [
                {
                    "type": "choice",
                    "id": "remove_redundant_keys_mode",
                    "get_value": api.get_remove_redundant_mode,
                    "set_value": api.set_remove_redundant_mode,
                    "items": api.remove_redundant_mode_choices,
                },
            ]},
        },
        "remove_static_anim_curves": {"type": "tool", "label": "Remove Static Anim Curves", "icon": "remove_static_anim_curves", "callback": api.remove_static_anim_curves, "tooltip": TOOLTIPS["remove_static"]},
        "reverse_animation": {"type": "tool", "label": "Reverse Animation", "text": "Rev", "callback": api.reverse_animation, "tooltip": TOOLTIPS["reverse"]},
        "copy_keys": {"type": "tool", "label": "Copy Keys", "icon": "copy_animation", "callback": api.copy_keys, "tooltip": TOOLTIPS["copy_keys"]},
        "cut_keys": {"type": "tool", "label": "Cut Keys", "icon": "eraser", "callback": api.cut_keys, "tooltip": TOOLTIPS["cut_keys"]},
        "delete_keys": {"type": "tool", "label": "Delete Keys", "icon": "trash", "callback": api.delete_keys, "tooltip": TOOLTIPS["delete_keys"]},
        "paste_keys": {"type": "tool", "label": "Paste Keys", "icon": "paste_animation", "callback": api.paste_keys, "tooltip": TOOLTIPS["paste_keys"]},
        "paste_keys_relative": {"type": "tool", "label": "Paste Keys Relative", "icon": "paste_insert_animation", "callback": api.paste_keys_relative, "tooltip": TOOLTIPS["paste_keys_relative"]},
        "go_to_next_key": {"type": "tool", "label": "Go to Next Key", "text": "K>", "callback": api.go_to_next_key, "tooltip": TOOLTIPS["go_to_next_key"], "operation": {"progress": False, "undo": False}},
        "go_to_previous_key": {"type": "tool", "label": "Go to Previous Key", "text": "<K", "callback": api.go_to_previous_key, "tooltip": TOOLTIPS["go_to_previous_key"], "operation": {"progress": False, "undo": False}},
        "go_to_next_frame": {"type": "tool", "label": "Go to Next Frame", "text": "F>", "callback": api.go_to_next_frame, "tooltip": TOOLTIPS["go_to_next_frame"], "operation": {"progress": False, "undo": False}},
        "go_to_previous_frame": {"type": "tool", "label": "Go to Previous Frame", "text": "<F", "callback": api.go_to_previous_frame, "tooltip": TOOLTIPS["go_to_previous_frame"], "operation": {"progress": False, "undo": False}},
        "clear_selected_keys": {"type": "tool", "label": "Clear Key Selection", "text": "x", "callback": api.clear_selected_keys, "tooltip": TOOLTIPS["clear_selected"]},
        "select_scene_animation": {"type": "tool", "label": "Select Scene Animation", "text": "s", "callback": api.select_all_animation_curves, "tooltip": TOOLTIPS["select_scene"]},
        "delete_keys_before_current": {"type": "tool", "label": "Delete Keys Before Current Frame", "text": "<x", "callback": api.delete_keyframes_before_current_time, "tooltip": TOOLTIPS["delete_before"]},
        "delete_keys_after_current": {"type": "tool", "label": "Delete Keys After Current Frame", "text": "x>", "callback": api.delete_keyframes_after_current_time, "tooltip": TOOLTIPS["delete_after"]},
    }

    SECTION = {
        "id": "animation_tools", "label": "Anim Curve Tools", "color": COLORS.toolbar.green.hex,
        "items": [
            {"id": "animation_tools"}, "separator",
            {"id": "set_smart_key"}, {"id": "set_smart_key_all_channels"},
            {"id": "apply_smart_euler_filter"}, {"id": "snap"},
            {"id": "reverse_animation"}, "separator",
            {"id": "clear_animation"}, {"id": "crop_animation"},
            {"id": "remove_redundant_keys"}, {"id": "remove_static_anim_curves"},
            "separator",
            {"id": "copy_keys"}, {"id": "cut_keys"}, {"id": "delete_keys"},
            {"id": "paste_keys"}, {"id": "paste_keys_relative"},
            "separator",
            {"id": "go_to_next_key"}, {"id": "go_to_previous_key"},
            {"id": "go_to_next_frame"}, {"id": "go_to_previous_frame"},
            "separator",
            {"id": "clear_selected_keys"}, {"id": "select_scene_animation"},
            {"id": "delete_keys_before_current"}, {"id": "delete_keys_after_current"},
        ],
    }
