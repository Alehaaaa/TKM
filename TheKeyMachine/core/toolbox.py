import TheKeyMachine.mods.mediaMod as media
import TheKeyMachine.mods.keyToolsMod as keyTools
import TheKeyMachine.mods.helperMod as helper
import TheKeyMachine.mods.barMod as bar
import TheKeyMachine.mods.uiMod as ui

"""
TheKeyMachine Toolbox
====================
Centralized definitions for all tools to ensure consistent naming, 
icons, callbacks, and documentation across different UI contexts 
(Main Toolbar, Custom Graph, Context Menus).
"""

TOOL_DEFINITIONS = {
    "share_keys": {
        "key": "share_keys",
        "label": "Share Keys",
        "text": "sK",
        "icon_path": media.share_keys_image,
        "callback": keyTools.share_keys,
        "tooltip_template": helper.share_keys_tooltip_text,
    },
    "reblock": {
        "key": "reblock",
        "label": "reBlock",
        "text": "rB",
        "icon_path": media.reblock_keys_image,
        "callback": keyTools.reblock_move,
        "tooltip_template": helper.reblock_move_tooltip_text,
    },
    "bake_animation_custom": {
        "key": "bake_animation_custom",
        "label": "Bake Custom Interval",
        "text": "BA",
        "icon_path": media.bake_animation_custom_image,
        "callback": bar.bake_animation_custom_window,
        "tooltip_template": helper.bake_animation_custom_tooltip_text,
    },
    "bake_animation_1": {
        "key": "bake_animation_1",
        "label": "Bake on Ones",
        "text": "BA",
        "icon_path": media.bake_animation_1_image,
        "callback": keyTools.bake_animation_1,
        "tooltip_template": helper.bake_animation_1_tooltip_text,
    },
    "bake_animation_2": {
        "key": "bake_animation_2",
        "label": "Bake on Twos",
        "text": "BA",
        "icon_path": media.bake_animation_2_image,
        "callback": keyTools.bake_animation_2,
        "tooltip_template": helper.bake_animation_2_tooltip_text,
    },
    "bake_animation_3": {
        "key": "bake_animation_3",
        "label": "Bake on Threes",
        "text": "BA",
        "icon_path": media.bake_animation_3_image,
        "callback": keyTools.bake_animation_3,
        "tooltip_template": helper.bake_animation_3_tooltip_text,
    },
    "bake_animation_4": {
        "key": "bake_animation_4",
        "label": "Bake on Fours",
        "text": "BA",
        "icon_path": media.bake_animation_3_image,
        "callback": keyTools.bake_animation_4,
        "tooltip_template": "Bake on Fours",
    },
    "orbit": {
        "key": "orbit",
        "label": "ToolBox Orbit",
        "text": "Orb",
        "icon_path": media.orbit_ui_image,
        "callback": lambda: ui.orbit_window(0, 0),
        "tooltip_template": helper.orbit_tooltip_text,
    },
    "attribute_switcher": {
        "key": "attribute_switcher",
        "label": "Attribute Switcher",
        "text": "SSw",
        "icon_path": media.attribute_switcher_image,
        "callback": lambda: ui.toggle_attribute_switcher_window(),
        "tooltip_template": helper.attribute_switcher_tooltip_text,
    },
    "gimbal": {
        "key": "gimbal",
        "label": "Gimbal Fixer",
        "text": "Gim",
        "icon_path": media.reblock_keys_image,
        "callback": bar.gimbal_fixer_window,
        "tooltip_template": helper.gimbal_fixer_tooltip_text,
    },
    "worldspace": {
        "key": "worldspace",
        "label": "World Space",
        "text": "WS",
        "icon_path": media.worldspace_copy_animation_image,
        "callback": bar.mod_worldspace_copy_animation,
        "tooltip_template": helper.copy_worldspace_tooltip_text,
    },
    "temp_pivot": {
        "key": "temp_pivot",
        "label": "Temp Pivot",
        "text": "TP",
        "icon_path": media.temp_pivot_image,
        "callback": lambda *args: bar.create_temp_pivot(False),
        "tooltip_template": helper.temp_pivot_tooltip_text,
    },
    "micro_move": {
        "key": "micro_move",
        "label": "Micro Move",
        "text": "MM",
        "icon_path": media.ruler_image,
        "tooltip_template": helper.micro_move_tooltip_text,
    },
    "static": {
        "key": "static",
        "label": "Static",
        "text": "S",
        "description": "Makes a static value of the selected curve from its first keyframe.",
        "callback": lambda: keyTools.deleteStaticCurves(),
    },
    "match": {
        "key": "match",
        "label": "Match",
        "text": "M",
        "icon_path": media.match_image,
        "description": "Makes a match of one curve with another, in this way both curves will be the same.",
        "callback": lambda: keyTools.match_keys(),
    },
    "flip": {
        "key": "flip",
        "label": "Flip",
        "text": "F",
        "description": "Inverts the selected curve vertically.",
        "callback": lambda: keyTools.flipCurves(),
    },
    "snap": {
        "key": "snap",
        "label": "Snap",
        "text": "Sn",
        "description": "Performs a cleanup and repositioning of the keys that are in a sub-frame to the nearest frame.",
        "callback": lambda: keyTools.snapKeyframes(),
    },
    "overlap": {
        "key": "overlap",
        "label": "Overlap",
        "text": "O",
        "description": "Applies an overlap frame to the selected curves.",
        "callback": keyTools.mod_overlap_animation,
    },
    "selection_sets": {
        "key": "selection_sets",
        "label": "Selection Sets",
        "text": "SS",
        "icon_path": media.selection_sets_image,
        "tooltip_template": helper.selection_sets_tooltip_text,
    },
    "custom_graph": {
        "key": "custom_graph",
        "label": "Graph Editor Toolbar",
        "text": "GE",
        "icon_path": media.customGraph_image,
        "tooltip_template": helper.customGraph_tooltip_text,
    },
    "extra_tools": {
        "key": "extra",
        "label": "Extra Tools",
        "text": "E",
        "description": "Additional curve utilities.",
        "callback": lambda: keyTools.snapKeyframes(),
    },
}


def get_tool(tool_id, **overrides):
    """Retrieve a tool definition with optional overrides."""
    if tool_id not in TOOL_DEFINITIONS:
        res = {"key": tool_id, "label": tool_id.replace("_", " ").capitalize()}
        res.update(overrides)
        return res

    # Merge base definition with overrides
    tool = TOOL_DEFINITIONS[tool_id].copy()
    tool.update(overrides)
    return tool
