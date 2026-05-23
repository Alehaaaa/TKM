from functools import partial

try:
    from PySide6 import QtCore  # type: ignore
except ImportError:
    from PySide2 import QtCore  # type: ignore

from TheKeyMachine.data import icons
import TheKeyMachine.mods.keyToolsMod as keyTools
import TheKeyMachine.mods.helperMod as helper
import TheKeyMachine.mods.barMod as bar
import TheKeyMachine.mods.generalMod as general
import TheKeyMachine.mods.uiMod as ui
import TheKeyMachine.core.trigger as trigger
import TheKeyMachine.core.toolMenus as toolMenus
import TheKeyMachine.tools.ibookmarks.api as iBookmarksApi
import TheKeyMachine.tools.selection_sets.api as selectionSetsApi
import TheKeyMachine.tools.temp_pivot.api as tempPivotApi
from TheKeyMachine.tools import colors as toolColors

"""
TheKeyMachine Toolbox
====================
Centralized definitions for all tools to ensure consistent naming, 
icons, callbacks, and documentation across different UI contexts 
(Main Toolbar, Custom Graph, Context Menus).
"""


def _tool_menu_builder(builder_name, **pdefault_kwargs):
    def _build(menu, source_widget=None):

        builder = getattr(toolMenus, builder_name)
        return builder(menu, source_widget=source_widget, **pdefault_kwargs)

    return _build


TOOL_DEFINITIONS = {
    "toolbar_toggle": {
        "type": "tool",
        "label": "Toggle Toolbar",
        "icon": icons.TheKeyMachine_icon,
    },
    "toolbar_add_shelf_button": {
        "type": "tool",
        "label": "Add Toggle Button To Shelf",
        "icon": icons.TheKeyMachine_icon,
    },
    "toolbar_reload": {
        "type": "tool",
        "label": "Reload",
        "icon": icons.reload,
    },
    "toolbar_unload": {
        "type": "tool",
        "label": "Unload",
        "icon": icons.close,
    },
    "check_for_updates": {
        "type": "tool",
        "label": "Check for Updates",
        "icon": icons.check_updates,
    },

    # ---------------------------------------------------------------  WINDOWS  --------------------------------------------------------------

    "orbit_window": {
        "type": "tool",
        "label": "Orbit Window",
        "icon": icons.orbit_ui,
    },
    "hotkeys_window": {
        "type": "tool",
        "label": "Hotkeys",
        "icon": icons.hotkeys,
    },
    "about_window": {
        "type": "tool",
        "label": "About",
        "icon": icons.about,
    },
    "donate_window": {
        "type": "tool",
        "label": "Donate",
        "icon": icons.donate,
        "tooltip_template": helper.donate_tooltip_text,
        "callback": trigger._open_donate_window,
    },
    "bug_report_window": {
        "type": "tool",
        "label": "Bug Report",
        "icon": icons.bug,
    },

    # ---------------------------------------------------------------  SMART TOOLS  --------------------------------------------------------------

    "smart_rotation": {
        "type": "tool",
        "label": "Smart Rotation",
        "icon": icons.tangent_auto,
    },
    "smart_rotation_release": {
        "type": "tool",
        "label": "Smart Rotation Release",
        "icon": icons.tangent_auto,
    },
    "smart_translation": {
        "type": "tool",
        "label": "Smart Translation",
        "icon": icons.cube,
    },
    "smart_translation_release": {
        "type": "tool",
        "label": "Smart Translation Release",
        "icon": icons.cube,
    },


    "depth_mover": {
        "type": "tool",
        "label": "Depth Mover",
        "icon": icons.depth_mover,
    },

    # ---------------------------------------------------------------  SHARE KEYS  --------------------------------------------------------------

    "share_keys": {
        "type": "tool",
        "label": "Share Keys",
        "text": "sK",
        "icon": icons.share_keys,
        "callback": keyTools.share_keys,
        "menu": _tool_menu_builder("build_share_keys_menu"),
        "tooltip_template": helper.share_keys_tooltip_text,
    },
    "share_keys_from_last_selected": {
        "type": "tool",
        "label": "Share Keys From Last Selected",
        "text": "sK",
        "icon": icons.share_keys,
        "callback": keyTools.share_keys_from_last_selected,
        "tooltip_template": helper.share_keys_tooltip_text,
        "default": False,
    },
    "reblock": {
        "type": "tool",
        "label": "reBlock",
        "text": "rB",
        "icon": icons.reblock,
        "callback": keyTools.reblock_move,
        "tooltip_template": helper.reblock_move_tooltip_text,
    },

    # ---------------------------------------------------------------  BAKE ANIMATION  --------------------------------------------------------------

    "bake_animation_custom": {
        "type": "tool",
        "label": "Bake Custom Interval",
        "text": "BA",
        "icon": icons.bake_animation_custom,
        "callback": bar.bake_animation_custom_window,
        "tooltip_template": helper.bake_animation_custom_tooltip_text,
    },
    "bake_animation_from_last_selected": {
        "type": "tool",
        "label": "Bake From Last Selected",
        "text": "BA",
        "icon": icons.bake_animation_1,
        "callback": keyTools.bake_animation_from_last_selected,
        "tooltip_template": helper.bake_animation_1_tooltip_text,
        "default": False,
    },
    "bake_animation_1": {
        "type": "tool",
        "label": "Bake on Ones",
        "text": "BA",
        "icon": icons.bake_animation_1,
        "callback": keyTools.bake_animation_1,
        "menu": _tool_menu_builder("build_bake_menu"),
        "tooltip_template": helper.bake_animation_1_tooltip_text,
    },
    "bake_animation_2": {
        "type": "tool",
        "label": "Bake on Twos",
        "text": "BA",
        "icon": icons.bake_animation_2,
        "callback": keyTools.bake_animation_2,
        "tooltip_template": helper.bake_animation_2_tooltip_text,
    },
    "bake_animation_3": {
        "type": "tool",
        "label": "Bake on Threes",
        "text": "BA",
        "icon": icons.bake_animation_3,
        "callback": keyTools.bake_animation_3,
        "tooltip_template": helper.bake_animation_3_tooltip_text,
    },
    "bake_animation_4": {
        "type": "tool",
        "label": "Bake on Fours",
        "text": "BA",
        "icon": icons.bake_animation_3,
        "callback": keyTools.bake_animation_4,
        "tooltip_template": helper.bake_animation_4_tooltip_text,
    },

    # ---------------------------------------------------------------  TOOL DIALOGS  --------------------------------------------------------------

    "orbit": {
        "type": "check",
        "label": "Orbit",
        "text": "Orb",
        "icon": icons.orbit_ui,
        "callback": lambda: ui.orbit_window(0, 0),
        "tooltip_template": helper.orbit_tooltip_text,
    },
    "attribute_switcher": {
        "type": "check",
        "label": "Attribute Switcher",
        "text": "SSw",
        "icon": icons.attribute_switcher,
        "callback": lambda: ui.toggle_attribute_switcher_window(),
        "tooltip_template": helper.attribute_switcher_tooltip_text,
    },
    "gimbal": {
        "type": "tool",
        "label": "Gimbal Fixer",
        "text": "Gim",
        "icon": icons.reblock,
        "callback": bar.gimbal_fixer_window,
        "tooltip_template": helper.gimbal_fixer_tooltip_text,
    },

    # ---------------------------------------------------------------  TEMP PIVOT --------------------------------------------------------------

    "temp_pivot": {
        "type": "check",
        "label": "Temp Pivot",
        "text": "TP",
        "icon": icons.temp_pivot,
        "callback": tempPivotApi.toggle_temp_pivot,
        "get_checked": tempPivotApi.is_temp_pivot_active,
        "bind_checked_fn": tempPivotApi.bind_temp_pivot_toolbar_button,
        "tooltip_template": helper.temp_pivot_tooltip_text,
    },
    "temp_pivot_last_object": {
        "type": "tool",
        "label": "Temp Pivot to Last Object",
        "icon": icons.temp_pivot,
        "callback": tempPivotApi.create_last_object_temp_pivot,
        "tooltip_template": helper.temp_pivot_last_object_tooltip_text,
        "pinnable": False,
    },
    "temp_pivot_centered": {
        "type": "tool",
        "label": "Temp Pivot Centered",
        "icon": icons.temp_pivot,
        "callback": tempPivotApi.create_centered_temp_pivot,
        "tooltip_template": helper.temp_pivot_centered_tooltip_text,
    },
    "temp_pivot_worldspace": {
        "type": "tool",
        "label": "Temp Pivot WorldSpace",
        "icon": icons.globe,
        "callback": tempPivotApi.create_worldspace_temp_pivot,
        "tooltip_template": helper.temp_pivot_worldspace_tooltip_text,
    },
    "temp_pivot_edit": {
        "type": "tool",
        "label": "Edit Temp Pivot",
        "icon": icons.temp_pivot,
        "callback": tempPivotApi.edit_temp_pivot,
        "tooltip_template": helper.temp_pivot_edit_tooltip_text,
    },
    "temp_pivot_reset": {
        "type": "tool",
        "label": "Reset Temp Pivot",
        "icon": icons.refresh,
        "callback": tempPivotApi.reset_temp_pivot,
        "tooltip_template": helper.temp_pivot_reset_tooltip_text,
    },
    "temp_pivot_help": {
        "type": "tool",
        "label": "Help",
        "description": "Open Documentation for Temp Pivots tools.",
        "icon": icons.help,
        "callback": lambda: general.open_url("https://thekeymachine.gitbook.io/base/the-toolbar/animation-tools/temp-pivots"),
        "pinnable": False,
    },
    "micro_move": {
        "type": "check",
        "label": "Micro Move",
        "text": "MM",
        "icon": icons.ruler,
        "callback": trigger.make_command_callback("micro_move"),
        "tooltip_template": helper.micro_move_tooltip_text,
    },

    # ----------------------------------------------  SETTINGS  --------------------------------------------------------

    "overshoot_sliders": {
        "type": "check",
        "label": "Overshoot Sliders",
        "menu_label": "Overshoot Sliders",
        "text": "OS",
        "icon": icons.sliders_overshoot,
        "callback": trigger.make_command_callback("overshoot_sliders"),
        "description": "Set range for sliders to -150/150, from -100/100.",
        "setting_toggle": "overshoot_sliders",
    },
    "attribute_switcher_euler_filter": {
        "type": "check",
        "label": "Auto Euler Filter",
        "menu_label": "Auto Euler Filter",
        "text": "EF",
        "icon": icons.euler_filter,
        "callback": trigger.make_command_callback("attribute_switcher_euler_filter"),
        "description": "Apply Euler filtering after Attribute Switcher changes rotation order.",
        "setting_toggle": "attribute_switcher_euler_filter",
    },

    # ----------------------------------------------  NUDGE  --------------------------------------------------------

    "nudge_value": {
        "type": "widget",
        "label": "Nudge Value",
        "tooltip_template": helper.move_keyframes_intField_widget_tooltip_text,
        "default": True,
    },
    "nudge_left": {
        "type": "tool",
        "label": "Nudge Left",
        "icon": icons.nudge_left,
        "callback": trigger.make_command_callback("nudge_left"),
        "menu": _tool_menu_builder("build_nudge_left_menu"),
        "tooltip_template": helper.nudge_left_tooltip_text,
    },
    "nudge_left_all_keys": {
        "type": "tool",
        "label": "Nudge Left All Keys",
        "icon": icons.nudge_left,
        "callback": trigger.make_command_callback("nudge_left_all_keys"),
        "tooltip_template": helper.nudge_left_tooltip_text,
        "default": False,
    },
    "nudge_left_scene": {
        "type": "tool",
        "label": "Nudge Left Scene",
        "icon": icons.nudge_left,
        "callback": trigger.make_command_callback("nudge_left_scene"),
        "tooltip_template": helper.nudge_left_tooltip_text,
        "default": False,
    },

    "nudge_right": {
        "type": "tool",
        "label": "Nudge Right",
        "icon": icons.nudge_right,
        "callback": trigger.make_command_callback("nudge_right"),
        "menu": _tool_menu_builder("build_nudge_right_menu"),
        "tooltip_template": helper.nudge_right_tooltip_text,
    },
    "nudge_right_all_keys": {
        "type": "tool",
        "label": "Nudge Right All Keys",
        "icon": icons.nudge_right,
        "callback": trigger.make_command_callback("nudge_right_all_keys"),
        "tooltip_template": helper.nudge_right_tooltip_text,
        "default": False,
    },
    "nudge_right_scene": {
        "type": "tool",
        "label": "Nudge Right Scene",
        "icon": icons.nudge_right,
        "callback": trigger.make_command_callback("nudge_right_scene"),
        "tooltip_template": helper.nudge_right_tooltip_text,
        "default": False,
    },

    "nudge_insert_inbetween": {
        "type": "tool",
        "label": "Insert Inbetween",
        "icon": icons.nudge_insert_inbetween,
        "callback": trigger.make_command_callback("nudge_insert_inbetween"),
        "tooltip_template": helper.insert_inbetween_tooltip_text,
    },
    "nudge_insert_inbetween_scene": {
        "type": "tool",
        "label": "Insert Inbetween Scene",
        "icon": icons.nudge_insert_inbetween,
        "callback": trigger.make_command_callback("nudge_insert_inbetween_scene"),
        "tooltip_template": helper.insert_inbetween_tooltip_text,
        "default": False,
    },
    "nudge_remove_inbetween": {
        "type": "tool",
        "label": "Remove Inbetween",
        "icon": icons.nudge_remove_inbetween,
        "callback": trigger.make_command_callback("nudge_remove_inbetween"),
        "tooltip_template": helper.remove_inbetween_tooltip_text,
    },
    "nudge_remove_inbetween_scene": {
        "type": "tool",
        "label": "Remove Inbetween Scene",
        "icon": icons.nudge_remove_inbetween,
        "callback": trigger.make_command_callback("nudge_remove_inbetween_scene"),
        "tooltip_template": helper.remove_inbetween_tooltip_text,
        "default": False,
    },

    # ----------------------------------------------  SELECTIONS  --------------------------------------------------------

    "clear_selected_keys": {
        "type": "tool",
        "label": "Clear Selection",
        "text": "x",
        "callback": trigger.make_command_callback("clear_selected_keys", keyTools.clear_selected_keys),
        "tooltip_template": helper.clear_selected_keys_widget_tooltip_text,
    },
    "select_scene_animation": {
        "type": "tool",
        "label": "Select Scene Anim",
        "text": "s",
        "callback": keyTools.select_all_animation_curves,
        "tooltip_template": helper.select_scene_animation_widget_tooltip_text,
    },
    "delete_static_animation": {
        "type": "tool",
        "label": "Delete Static Keys",
        "text": "S",
        "icon": icons.delete_animation,
        "tooltip_template": helper.delete_static_animation_tooltip_text,
        "callback": lambda: keyTools.deleteStaticCurves(),
    },
    "graph_match_keys": {
        "type": "tool",
        "label": "Match",
        "text": "M",
        "icon": icons.magnet,
        "tooltip_template": helper.graph_match_keys_tooltip_text,
        "callback": lambda: keyTools.graph_match_keys(),
    },
    "graph_flip": {
        "type": "tool",
        "label": "Flip",
        "text": "F",
        "tooltip_template": helper.flip_tooltip_text,
        "callback": lambda: keyTools.flipCurves(),
    },
    "snap": {
        "type": "tool",
        "label": "Snap Keys",
        "text": "SpK",
        "icon": icons.snap,
        "tooltip_template": helper.snap_tooltip_text,
        "callback": lambda: keyTools.snapKeyframes(),
    },
    "graph_overlap_forward": {
        "type": "tool",
        "label": "Overlap Forward",
        "text": "O>",
        "tooltip_template": helper.overlap_tooltip_text,
        "callback": keyTools.overlap_forward,
    },
    "graph_overlap_backward": {
        "type": "tool",
        "label": "Overlap Backward",
        "text": "O<",
        "tooltip_template": helper.overlap_tooltip_text,
        "callback": keyTools.overlap_backward,
    },

# ---------------------------------------------------------------  ISOLATE --------------------------------------------------------------

    "isolate_master": {
        "type": "tool",
        "label": "Isolate",
        "icon": icons.isolate,
        "callback": bar.isolate_master,
        "tooltip_template": helper.isolate_tooltip_text,
    },
    "isolate_down_level": {
        "type": "widget",
        "label": "Down one level",
    },
    "isolate_bookmarks": {
        "type": "tool",
        "label": "Isolate Bookmarks",
        "icon": icons.ibookmarks_menu,
        "callback": iBookmarksApi.create_ibookmarks_window,
        "tooltip_template": helper.ibookmarks_window_tooltip_text,
    },
    "isolate_help": {
        "type": "tool",
        "label": "Help",
        "description": "Open Documentation for Isolate tools.",
        "icon": icons.help,
        "callback": lambda: general.open_url("https://thekeymachine.gitbook.io/base/the-toolbar/animation-tools/isolate"),
        "pinnable": False,
    },

# ---------------------------------------------------------------  DEFAULT POSE --------------------------------------------------------------

    "default_object_values": {
        "type": "tool",
        "label": "Default Pose",
        "icon": icons.default,
        "callback": keyTools.default_object_values,
        "tooltip_template": helper.default_values_tooltip_text,
    },
    "default_translations": {
        "type": "tool",
        "label": "Default Translations",
        "text": "RT",
        "icon": icons.default,
        "callback": lambda: keyTools.default_object_values(default_translations=True),
        "tooltip_template": helper.default_translations_tooltip_text,
    },
    "default_rotations": {
        "type": "tool",
        "label": "Default Rotations",
        "text": "RR",
        "icon": icons.default,
        "callback": lambda: keyTools.default_object_values(default_rotations=True),
        "tooltip_template": helper.default_rotations_tooltip_text,
    },
    "default_scales": {
        "type": "tool",
        "label": "Default Scales",
        "text": "RS",
        "icon": icons.default,
        "callback": lambda: keyTools.default_object_values(default_scales=True),
        "tooltip_template": helper.default_scales_tooltip_text,
    },
    "default_trs": {
        "type": "tool",
        "label": "Default Translation Rotation Scale",
        "text": "RTRS",
        "icon": icons.default,
        "callback": lambda: keyTools.default_object_values(
            default_translations=True,
            default_rotations=True,
            default_scales=True,
        ),
        "tooltip_template": helper.default_trs_tooltip_text,
    },

    "delete_all_animation": {
        "type": "tool",
        "label": "Delete All Animation",
        "icon": icons.delete_animation,
        "callback": bar.delete_animation,
        "tooltip_template": helper.delete_animation_tooltip_text,
    },

    "default_set_defaults": {
        "type": "tool",
        "label": "Set Default Values For Selected",
        "icon": icons.default,
        "callback": keyTools.save_default_values,
    },
    "default_restore_defaults": {
        "type": "tool",
        "label": "Restore Default Values For Selected",
        "icon": icons.default,
        "callback": keyTools.remove_default_values_for_selected_object,
    },
    "default_clear_all": {
        "type": "tool",
        "label": "Clear All Default Settings",
        "icon": icons.default,
        "callback": keyTools.restore_default_data,
    },

    "default_help": {
        "type": "tool",
        "label": "Help",
        "description": "Open Documentation for Default tools.",
        "icon": icons.help,
        "callback": lambda: general.open_url("https://thekeymachine.gitbook.io/base/the-toolbar/animation-tools/default-to-default"),
        "pinnable": False,
    },

    # ---------------------------------------------------------------  SELECT --------------------------------------------------------------

    "select_rig_controls": {
        "type": "tool",
        "label": "Select Rig Controls",
        "icon": icons.select_rig_controls,
        "callback": bar.select_rig_controls,
        "tooltip_template": helper.select_rig_controls_tooltip_text,
    },
    "select_rig_controls_animated": {
        "type": "tool",
        "label": "Select Animated Rig Controls",
        "icon": icons.select_rig_controls_animated,
        "tooltip_template": helper.select_rig_controls_animated_tooltip_text,
        "callback": bar.select_rig_controls_animated,
    },
    "select_opposite": {
        "type": "tool",
        "label": "Select Opposite",
        "icon": icons.opposite_select,
        "callback": keyTools.selectOpposite,
        "tooltip_template": helper.opposite_select_tooltip_text,
    },

    # ---------------------------------------------------------------  SELECTION SETS --------------------------------------------------------------

    "selection_sets": {
        "type": "check",
        "label": "Selection Sets",
        "text": "SS",
        "icon": icons.selection_sets,
        "callback": trigger.make_command_callback("selection_sets"),
        "tooltip_template": helper.selection_sets_tooltip_text,
    },
    "selection_sets_quick_export": {
        "type": "tool",
        "label": "Quick Export",
        "text": "QEx",
        "icon": icons.selection_sets_export,
        "tooltip_template": helper.quick_export_selection_sets_tooltip_text,
        "callback": selectionSetsApi.quick_export_selection_sets,
    },
    "selection_sets_quick_import": {
        "type": "tool",
        "label": "Quick Import",
        "text": "QIm",
        "icon": icons.selection_sets_import,
        "tooltip_template": helper.quick_import_selection_sets_tooltip_text,
        "callback": selectionSetsApi.quick_import_selection_sets,
    },
    "selection_sets_export": {
        "type": "tool",
        "label": "Export",
        "text": "Ex",
        "icon": icons.selection_sets_export,
        "tooltip_template": helper.export_selection_sets_tooltip_text,
        "callback": selectionSetsApi.export_selection_sets,
    },
    "selection_sets_import": {
        "type": "tool",
        "label": "Import",
        "text": "Im",
        "icon": icons.selection_sets_import,
        "tooltip_template": helper.import_selection_sets_tooltip_text,
        "callback": selectionSetsApi.import_selection_sets,
    },
    "selection_sets_clear_all": {
        "type": "tool",
        "label": "Clear All Select Sets",
        "text": "Clr",
        "icon": icons.trash,
        "tooltip_template": helper.clear_selection_sets_tooltip_text,
        "callback": selectionSetsApi.clear_all_selection_sets,
    },
    "custom_graph": {
        "type": "check",
        "label": "Graph Editor Toolbar",
        "menu_label": "Show Graph Editor Toolbar",
        "text": "GE",
        "icon": icons.customGraph,
        "callback": trigger.make_command_callback("custom_graph"),
        "tooltip_template": helper.customGraph_tooltip_text,
        "description": "Show the TKM toolbar in the Graph Editor.",
        "setting_toggle": "custom_graph",
    },
    "graph_extra_tools": {
        "type": "menu",
        "label": "Extra Tools",
        "text": "E",
        "menu": _tool_menu_builder("build_graph_extra_tools_menu"),
        "tooltip_template": helper.extra_tools_tooltip_text,
    },
    "select_hierarchy": {
        "type": "tool",
        "label": "Select Hierarchy",
        "icon": icons.select_hierarchy,
        "callback": bar.selectHierarchy,
        "tooltip_template": helper.select_hierarchy_tooltip_text,
    },
    "selector": {
        "type": "tool",
        "label": "Selector",
        "icon": icons.selector,
        "callback": bar.selector_window,
        "tooltip_template": helper.selector_tooltip_text,
        "default": True,
    },

    # ---------------------------------------------------------------  TEMP LOCATOR  --------------------------------------------------------------

    "create_locator": {
        "type": "tool",
        "label": "Create Locator",
        "icon": icons.cube,
        "callback": bar.createLocator,
        "tooltip_template": helper.createLocator_tooltip_text,
    },
    "locator_select_temp": {
        "type": "tool",
        "label": "Select Temp Locators",
        "icon": icons.cube,
        "callback": bar.selectTempLocators,
        "description": "Select all temporary locators in the scene.",
    },
    "locator_remove_temp": {
        "type": "tool",
        "label": "Remove Temp Locators",
        "icon": icons.cube,
        "callback": bar.deleteTempLocators,
        "description": "Remove all temporary locators from the scene.",
    },

    # ---------------------------------------------------------------  COPY POSE/ANIMATION --------------------------------------------------------------

    "copy_pose": {
        "type": "tool",
        "label": "Copy Pose",
        "icon": icons.copy_pose,
        "callback": keyTools.copy_pose,
        "tooltip_template": helper.copy_pose_tooltip_text,
    },
    "paste_pose": {
        "type": "tool",
        "label": "Paste Pose",
        "icon": icons.paste_pose,
        "callback": keyTools.paste_pose,
        "tooltip_template": helper.paste_pose_tooltip_text,
    },
    "copy_animation": {
        "type": "tool",
        "label": "Copy Animation",
        "icon": icons.copy_animation,
        "callback": keyTools.copy_animation,
        "tooltip_template": helper.copy_animation_tooltip_text,
    },

    "paste_animation": {
        "type": "tool",
        "label": "Paste Replace Animation",
        "icon": icons.paste_animation,
        "callback": keyTools.paste_animation,
        "tooltip_template": helper.paste_animation_tooltip_text,
    },
    "paste_insert_animation": {
        "type": "tool",
        "label": "Paste Insert Animation",
        "icon": icons.paste_insert_animation,
        "callback": keyTools.paste_insert_animation,
        "tooltip_template": helper.paste_insert_animation_tooltip_text,
    },
    "paste_animation_to": {
        "type": "tool",
        "label": "Paste To",
        "icon": icons.paste_animation,
        "callback": keyTools.paste_animation_to,
    },

    "pose_help": {
        "type": "tool",
        "label": "Help",
        "description": "Open Documentation for Copy/Paste Pose tools.",
        "icon": icons.help,
        "callback": lambda: general.open_url(
            "https://thekeymachine.gitbook.io/base/the-toolbar/animation-tools/copy-paste-animation#pose-tools"
        ),
        "pinnable": False,
    },
    "copy_animation_help": {
        "type": "tool",
        "label": "Help",
        "description": "Open Documentation for Copy/Paste Animation tools.",
        "icon": icons.help,
        "callback": lambda: general.open_url("https://thekeymachine.gitbook.io/base/the-toolbar/animation-tools/copy-paste-animation"),
        "pinnable": False,
    },

    # ---------------------------------------------------------------  FOLLOW CAMERAS --------------------------------------------------------------

    "follow_cam": {
        "type": "tool",
        "label": "Follow Cam",
        "icon": icons.camera,
        "callback": lambda *args: bar.create_follow_cam(translation=True, rotation=True),
        "tooltip_template": helper.follow_cam_tooltip_text,
    },
    "follow_cam_translation": {
        "type": "tool",
        "label": "Follow only Translation",
        "icon": icons.camera,
        "callback": lambda: bar.create_follow_cam(translation=True, rotation=False),
        "tooltip_template": helper.follow_cam_tooltip_text,
    },
    "follow_cam_rotation": {
        "type": "tool",
        "label": "Follow only Rotation",
        "icon": icons.camera,
        "callback": lambda: bar.create_follow_cam(translation=False, rotation=True),
        "tooltip_template": helper.follow_cam_tooltip_text,
    },
    "follow_cam_remove": {
        "type": "tool",
        "label": "Remove Follow Cam",
        "icon": icons.remove,
        "callback": bar.remove_followCam,
    },
    "animation_offset": {
        "type": "check",
        "label": "Anim Offset",
        "icon": icons.animation_offset,
        "callback": trigger.make_command_callback("animation_offset"),
        "tooltip_template": helper.animation_offset_tooltip_text,
    },
    "ws_copy_frame": {
        "type": "tool",
        "label": "Copy World Space",
        "icon": icons.worldspace_copy_frame,
        "callback": bar.copy_worldspace_single_frame,
        "tooltip_template": helper.copy_worldspace_tooltip_text,
    },

    # ---------------------------------------------------------------  ALIGN OBJECTS --------------------------------------------------------------

    "align_objects": {
        "type": "tool",
        "label": "Align Objects",
        "icon": icons.magnet,
        "callback": bar.align_selected_objects,
        "tooltip_template": helper.align_tooltip_text,
    },
    "align_object_translation": {
        "type": "tool",
        "label": "Align Object Translation",
        "icon": icons.magnet,
        "callback": partial(bar.align_selected_objects, pos=True, rot=False, scl=False),
    },
    "align_object_rotation": {
        "type": "tool",
        "label": "Align Object Rotation",
        "icon": icons.magnet,
        "callback": partial(bar.align_selected_objects, pos=False, rot=True, scl=False),
    },
    "align_object_scale": {
        "type": "tool",
        "label": "Align Object Scale",
        "icon": icons.magnet,
        "callback": partial(bar.align_selected_objects, pos=False, rot=False, scl=True),
    },
    "align_objects_help": {
        "type": "tool",
        "label": "Align Objects Help",
        "description": "Open Documentation for Align tools.",
        "icon": icons.help,
        "callback": lambda: general.open_url("https://thekeymachine.gitbook.io/base/the-toolbar/animation-tools/match-align"),
        "pinnable": False,
    },

    # ---------------------------------------------------------------  TRACER --------------------------------------------------------------

    "create_tracer": {
        "type": "tool",
        "label": "Tracer",
        "icon": icons.tracer,
        "callback": bar.create_tracer,
        "menu": _tool_menu_builder("build_tracer_menu"),
        "tooltip_template": helper.tracer_tooltip_text,
    },
    "tracer_refresh": {
        "type": "tool",
        "label": "Refresh Tracer",
        "icon": icons.refresh,
        "callback": bar.tracer_refresh,
    },
    "tracer_show_hide": {
        "type": "tool",
        "label": "Toggle Tracer",
        "icon": icons.tracer_show_hide,
        "callback": bar.tracer_show_hide,
    },
    "tracer_offset_node": {
        "type": "tool",
        "label": "Select Offset Object",
        "icon": icons.tracer_select_offset,
        "callback": bar.select_tracer_offset_node,
    },
    "tracer_grey": {
        "type": "tool",
        "label": "Tracer Style: Grey",
        "icon": icons.tracer_grey,
        "callback": bar.set_tracer_grey_color,
    },
    "tracer_red": {
        "type": "tool",
        "label": "Tracer Style: Red",
        "icon": icons.tracer_red,
        "callback": bar.set_tracer_red_color,
    },
    "tracer_blue": {
        "type": "tool",
        "label": "Tracer Style: Blue",
        "icon": icons.tracer_blue,
        "callback": bar.set_tracer_blue_color,
    },
    "tracer_remove": {
        "type": "tool",
        "label": "Remove Tracer",
        "icon": icons.remove,
        "callback": bar.remove_tracer_node,
    },
    "tracer_connected": {
        "type": "widget",
        "label": "Connected",
    },

# ---------------------------------------------------------------  MIRROR --------------------------------------------------------------

    "mirror": {
        "type": "tool",
        "label": "Mirror",
        "icon": icons.mirror,
        "callback": keyTools.mirror,
        "tooltip_template": helper.mirror_tooltip_text,
    },
    "mirror_add_invert": {
        "type": "tool",
        "label": "Add Exception Invert",
        "icon": icons.mirror,
        "callback": keyTools.add_mirror_invert_exception,
    },
    "mirror_add_keep": {
        "type": "tool",
        "label": "Add Exception Keep",
        "icon": icons.mirror,
        "callback": keyTools.add_mirror_keep_exception,
    },
    "mirror_remove_exc": {
        "type": "tool",
        "label": "Remove Exception",
        "icon": icons.mirror,
        "callback": keyTools.remove_mirror_invert_exception,
    },
    "mirror_help": {
        "type": "tool",
        "label": "Help",
        "description": "Open Documentation for Mirror tools.",
        "icon": icons.help,
        "callback": lambda: general.open_url("https://thekeymachine.gitbook.io/base/the-toolbar/animation-tools/mirror"),
        "pinnable": False,
    },
    "opposite_add": {
        "type": "tool",
        "label": "Add Opposite",
        "icon": icons.opposite_add,
        "callback": keyTools.addSelectOpposite,
        "tooltip_template": helper.opposite_add_tooltip_text,
    },
    "opposite_copy": {
        "type": "tool",
        "label": "Copy Opposite",
        "icon": icons.opposite_copy,
        "callback": keyTools.copyOpposite,
        "tooltip_template": helper.opposite_copy_tooltip_text,
    },
    "paste_opposite_animation": {
        "type": "tool",
        "label": "Paste Opposite",
        "icon": icons.paste_opposite_animation,
        "callback": keyTools.paste_opposite_animation,
    },

# ---------------------------------------------------------------  LINK OBJECTS --------------------------------------------------------------

    "link_copy": {
        "type": "tool",
        "label": "Copy Link Position",
        "icon": icons.link_relative,
        "callback": keyTools.copy_link,
        "tooltip_template": helper.link_objects_tooltip_text,
    },
    "link_paste": {
        "type": "tool",
        "label": "Paste Link Position",
        "icon": icons.link_relative_paste,
        "callback": keyTools.paste_link,
        "tooltip_template": helper.paste_link_tooltip_text,
    },
    "link_autolink": {
        "type": "check",
        "label": "Auto Link Position",
        "icon": icons.link_relative,
        "checkable": True,
        "tooltip_template": helper.auto_link_tooltip_text,
    },
    "link_help": {
        "type": "tool",
        "label": "Help",
        "description": "Open Documentation for Link Objects tools.",
        "icon": icons.help,
        "callback": lambda: general.open_url("https://thekeymachine.gitbook.io/base/the-toolbar/animation-tools/link-objects"),
        "pinnable": False,
    },


    # ---------------------------------------------------------------  WORLD SPACE --------------------------------------------------------------

    "ws_copy_range": {
        "type": "tool",
        "label": "Copy World Space - Selected Range",
        "icon": icons.worldspace_copy_animation,
        "callback": bar.copy_range_worldspace_animation,
        "tooltip_template": helper.copy_worldspace_range_tooltip_text,
    },
    "ws_paste_frame": {
        "type": "tool",
        "label": "Paste World Space",
        "icon": icons.worldspace_paste_frame,
        "callback": bar.paste_worldspace_single_frame,
        "tooltip_template": helper.paste_worldspace_tooltip_text,
    },
    "ws_paste": {
        "type": "tool",
        "label": "Paste World Space - All Animation",
        "icon": icons.worldspace_paste_animation,
        "callback": bar.worldspace_paste_animation,
        "tooltip_template": helper.paste_worldspace_animation_tooltip_text,
    },
    "worldspace_help": {
        "type": "tool",
        "label": "Help - World Space",
        "description": "Open Documentation for World Space tools.",
        "icon": icons.help,
        "callback": lambda: general.open_url(
            "https://thekeymachine.gitbook.io/base/the-toolbar/animation-tools/copy-paste-animation#worldspace-tools"
        ),
        "pinnable": False,
    },
    "custom_tools": {
        "type": "menu",
        "label": "Custom Tools",
        "icon": icons.tools_folder,
        "callback": trigger.make_command_callback("custom_tools"),
        "menu": _tool_menu_builder("build_custom_tools_menu"),
        "tooltip_template": helper.custom_tools_tooltip_text,
    },
    "custom_scripts": {
        "type": "menu",
        "label": "Custom Scripts",
        "icon": icons.scripts_folder,
        "callback": trigger.make_command_callback("custom_scripts"),
        "menu": _tool_menu_builder("build_custom_scripts_menu"),
        "tooltip_template": helper.custom_scripts_tooltip_text,
    },
    "settings": {
        "type": "menu",
        "label": "Settings",
        "icon": icons.settings,
        "description": "Access global preferences, check for updates, and view credits.",
    },
    "graph_isolate_curves": {
        "type": "tool",
        "label": "Isolate Selected Curves",
        "icon": icons.isolate,
        "callback": keyTools.isolateCurve,
        "tooltip_template": helper.graph_isolate_curves_tooltip_text,
    },
    "graph_select_object_from_curve": {
        "type": "tool",
        "label": "Select object from selected curve",
        "icon": icons.isolate,
        "callback": keyTools.select_objects_from_selected_curves,
    },
    "graph_toggle_mute": {
        "type": "tool",
        "label": "Mute",
        "text": "Mt",
        "callback": keyTools.toggleMute,
        "tooltip_template": helper.graph_mute_tooltip_text,
    },
    "graph_toggle_lock": {
        "type": "tool",
        "label": "Lock",
        "text": "Lk",
        "callback": keyTools.toggleLock,
        "tooltip_template": helper.graph_lock_tooltip_text,
    },
    "enable_graph_filter": {
        "type": "tool",
        "label": "Enable Filter",
        "text": "EnF",
        "callback": ui.filterMode_sync_on,
        "tooltip_template": helper.graph_filter_tooltip_text,
    },
    "disable_graph_filter": {
        "type": "tool",
        "label": "Disable Filter",
        "text": "DiF",
        "callback": ui.filterMode_sync_off,
        "tooltip_template": helper.graph_filter_tooltip_text,
    },


    # ---------------------------------------------------- TANGENTS ---------------------------------------------

    "tangent_cycle_matcher": {
        "type": "tool",
        "label": "Cycle Matcher",
        "text": "CM",
        "icon": icons.match_curve_cycle,
        "callback": keyTools.match_curve_cycle,
        "menu": _tool_menu_builder("build_cycle_matcher_menu", icon=icons.match_curve_cycle),
        "tooltip_template": helper.tangent_cycle_matcher_tooltip_text,
    },
    "tangent_bouncy": {
        "type": "tool",
        "label": "Bouncy Tangent",
        "text": "BO",
        "icon": icons.tangent_bouncy,
        "callback": keyTools.bouncy_tangets,
        "menu": _tool_menu_builder(
            "build_tangent_menu", tangent_type="bouncy", tangent_label="Bouncy Tangent", icon=icons.tangent_bouncy
        ),
        "tooltip_template": helper.tangent_bouncy_tooltip_text,
    },
    "tangent_auto": {
        "type": "tool",
        "label": "Auto Tangent",
        "text": "AU",
        "icon": icons.tangent_auto,
        "callback": lambda: bar.setTangent("auto"),
        "menu": _tool_menu_builder(
            "build_tangent_menu",
            tangent_type="auto",
            tangent_label="Auto Tangent",
            icon=icons.tangent_auto,
            maya_default_tangent=True,
        ),
        "tooltip_template": helper.auto_tangent_tooltip_text,
    },
    "tangent_spline": {
        "type": "tool",
        "label": "Spline Tangent",
        "text": "SP",
        "icon": icons.tangent_spline,
        "callback": lambda: bar.setTangent("spline"),
        "menu": _tool_menu_builder(
            "build_tangent_menu",
            tangent_type="spline",
            tangent_label="Spline Tangent",
            icon=icons.tangent_spline,
            maya_default_tangent=True,
        ),
        "tooltip_template": helper.spline_tangent_tooltip_text,
    },
    "tangent_clamped": {
        "type": "tool",
        "label": "Clamped Tangent",
        "text": "CL",
        "icon": icons.tangent_clamped,
        "callback": lambda: bar.setTangent("clamped"),
        "menu": _tool_menu_builder(
            "build_tangent_menu",
            tangent_type="clamped",
            tangent_label="Clamped Tangent",
            icon=icons.tangent_clamped,
            maya_default_tangent=True,
        ),
        "tooltip_template": helper.clamped_tangent_tooltip_text,
    },
    "tangent_linear": {
        "type": "tool",
        "label": "Linear Tangent",
        "text": "LI",
        "icon": icons.tangent_linear,
        "callback": lambda: bar.setTangent("linear"),
        "menu": _tool_menu_builder(
            "build_tangent_menu",
            tangent_type="linear",
            tangent_label="Linear Tangent",
            icon=icons.tangent_linear,
            maya_default_tangent=True,
        ),
        "tooltip_template": helper.linear_tangent_tooltip_text,
    },
    "tangent_flat": {
        "type": "tool",
        "label": "Flat Tangent",
        "text": "FT",
        "icon": icons.tangent_flat,
        "callback": lambda: bar.setTangent("flat"),
        "menu": _tool_menu_builder(
            "build_tangent_menu",
            tangent_type="flat",
            tangent_label="Flat Tangent",
            icon=icons.tangent_flat,
            maya_default_tangent=True,
        ),
        "tooltip_template": helper.flat_tangent_tooltip_text,
    },
    "tangent_step": {
        "type": "tool",
        "label": "Step Tangent",
        "text": "ST",
        "icon": icons.tangent_step,
        "callback": lambda: bar.setTangent("step"),
        "menu": _tool_menu_builder(
            "build_tangent_menu",
            tangent_type="step",
            tangent_label="Step Tangent",
            icon=icons.tangent_step,
            maya_default_tangent=True,
        ),
        "tooltip_template": helper.step_tangent_tooltip_text,
    },
    "tangent_plateau": {
        "type": "tool",
        "label": "Plateau Tangent",
        "text": "PT",
        "icon": icons.tangent_plateau,
        "callback": lambda: bar.setTangent("plateau"),
        "menu": _tool_menu_builder(
            "build_tangent_menu",
            tangent_type="plateau",
            tangent_label="Plateau Tangent",
            icon=icons.tangent_plateau,
            maya_default_tangent=True,
        ),
        "tooltip_template": helper.plateau_tangent_tooltip_text,
    },
}
TOOL_SECTION_DEFINITIONS = {
    # --- Hotkey/System Tools ---
    "window_tools": {
        "label": "Windows",
        "hotkey_only": True,
        "items": [
            {"id": "toolbar_toggle"},
            {"id": "toolbar_add_shelf_button"},
            {"id": "toolbar_reload"},
            {"id": "toolbar_unload"},
            {"id": "check_for_updates"},
            {"id": "orbit_window"},
            {"id": "hotkeys_window"},
            {"id": "about_window"},
            {"id": "donate_window"},
            {"id": "bug_report_window"},
        ],
    },
    "manipulator_tools": {
        "label": "Manipulators",
        "hotkey_only": True,
        "items": [
            {"id": "smart_rotation"},
            {"id": "smart_rotation_release"},
            {"id": "smart_translation"},
            {"id": "smart_translation_release"},
            {"id": "depth_mover"},
        ],
    },
    # --- Key Editing ---
    "nudge_tools": {
        "label": "Nudge",
        "color": toolColors.TOOLBAR_GREEN,
        "items": [
            {
                "id": "nudge_left",
                "default": True,
                "shortcuts": [{"id": "nudge_remove_inbetween", "keys": [QtCore.Qt.Key_Shift]}],
            },
            {"id": "nudge_remove_inbetween"},
            {
                "id": "nudge_right",
                "default": True,
                "shortcuts": [{"id": "nudge_insert_inbetween", "keys": [QtCore.Qt.Key_Shift]}],
            },
            {"id": "nudge_insert_inbetween"},
            {"id": "nudge_left_all_keys", "default": False},
            {"id": "nudge_left_scene", "default": False},
            {"id": "nudge_right_all_keys", "default": False},
            {"id": "nudge_right_scene", "default": False},
            {"id": "nudge_insert_inbetween_scene", "default": False},
            {"id": "nudge_remove_inbetween_scene", "default": False},
            {"type": "widget", "id": "nudge_value", "default": True},
        ],
    },
    "default_tools": {
        "label": "Default",
        "color": toolColors.TOOLBAR_GREEN,
        "items": [
            {
                "id": "default_object_values",
                "default": True,
                "shortcuts": [
                    {"id": "default_translations", "keys": [QtCore.Qt.Key_Shift]},
                    {"id": "default_rotations", "keys": [QtCore.Qt.Key_Control]},
                    {"id": "default_scales", "keys": [QtCore.Qt.Key_Alt]},
                    {"id": "default_trs", "keys": [QtCore.Qt.Key_Control, QtCore.Qt.Key_Shift]},
                    {"id": "default_set_defaults", "keys": [QtCore.Qt.Key_Alt, QtCore.Qt.Key_Control, QtCore.Qt.Key_Shift]},
                ],
            },
            {"id": "default_translations"},
            {"id": "default_rotations"},
            {"id": "default_scales"},
            {"id": "default_trs"},
            "separator",
            {"id": "default_set_defaults"},
            {"id": "default_restore_defaults"},
            "separator",
            {"id": "default_clear_all"},
            "separator",
            {"id": "default_help"},
        ],
    },
    "bake_tools": {
        "label": "Bake",
        "color": toolColors.TOOLBAR_GREEN,
        "items": [
            {
                "id": "bake_animation_1",
                "default": True,
                "shortcuts": [
                    {"id": "bake_animation_2", "keys": [QtCore.Qt.Key_Control]},
                    {"id": "bake_animation_3", "keys": [QtCore.Qt.Key_Shift]},
                    {"id": "bake_animation_4", "keys": [QtCore.Qt.Key_Control, QtCore.Qt.Key_Shift]},
                    {"id": "bake_animation_custom", "keys": [QtCore.Qt.Key_Alt]},
                ],
            },
            {"id": "bake_animation_2"},
            {"id": "bake_animation_3"},
            {"id": "bake_animation_4"},
            {"id": "bake_animation_custom"},
            "separator",
            {"id": "bake_animation_from_last_selected", "default": False},
        ],
    },
    "key_sync_tools": {
        "label": "Key Sync",
        "color": toolColors.TOOLBAR_GREEN,
        "items": [
            {
                "id": "share_keys",
                "default": True,
                "shortcuts": [{"id": "reblock", "keys": [QtCore.Qt.Key_Shift]}],
            },
            {"id": "reblock"},
            "separator",
            {"id": "share_keys_from_last_selected", "default": False},
        ],
    },
    "key_selection_tools": {
        "label": "Key Selection",
        "color": toolColors.TOOLBAR_GREEN,
        "items": [
            {"id": "clear_selected_keys"},
            {"id": "select_scene_animation"},
        ],
    },
    "delete_tools": {
        "label": "Delete Animation",
        "color": toolColors.TOOLBAR_RED,
        "items": [
            {
                "id": "delete_all_animation",
                "default": True,
                "shortcuts": [{"id": "delete_static_animation", "keys": [QtCore.Qt.Key_Shift]}],
            },
            {"id": "delete_static_animation"},
        ],
    },
    "main_key_editing": {
        "label": "Key Editing",
        "color": toolColors.TOOLBAR_GREEN,
        "toolbar": False,
        "items": [
            {"section": "nudge_tools"},
            "separator",
            {"section": "key_sync_tools"},
            {"id": "clear_selected_keys"},
            {"id": "select_scene_animation"},
            "separator",
            {"section": "bake_tools"},
        ],
    },
    # --- Sliders ---
    "slider_blend": {
        "label": "Blend Sliders",
        "color": toolColors.TOOLBAR_GREEN,
        "type": "slider",
        "slider_type": "blend",
        "modes_attr": "BLEND_MODES",
        "default_modes": ["connect_neighbors"],
    },
    "slider_tween": {
        "label": "Tween Sliders",
        "color": toolColors.TOOLBAR_YELLOW,
        "type": "slider",
        "slider_type": "tween",
        "modes_attr": "TWEEN_MODES",
        "default_modes": ["tweener"],
    },
    "slider_tangent": {
        "label": "Tangent Sliders",
        "color": toolColors.TOOLBAR_ORANGE,
        "icon": icons.tangent_auto,
        "type": "slider",
        "slider_type": "tangent",
        "modes_attr": "TANGENT_MODES",
        "default_modes": ["blend_best_guess"],
    },
    # --- Scene Tools ---
    "pointer_tools": {
        "label": "Pointer",
        "color": toolColors.TOOLBAR_RED,
        "items": [
            {
                "id": "select_rig_controls",
                "default": True,
                "shortcuts": [{"id": "select_rig_controls_animated", "keys": [QtCore.Qt.Key_Control]}],
            },
            {"id": "select_rig_controls_animated"},
            "separator",
            {"id": "depth_mover"},
        ],
    },
    "isolate_tools": {
        "label": "Isolate Tools",
        "color": toolColors.TOOLBAR_RED,
        "items": [
            {
                "id": "isolate_master",
                "default": True,
                "shortcuts": [
                    {"id": "isolate_bookmarks", "keys": [QtCore.Qt.Key_Control]},
                ],
            },
            {"id": "isolate_bookmarks"},
            "separator",
            {"type": "widget", "id": "isolate_down_level"},
            "separator",
            {"id": "isolate_help"},
        ],
    },
    "locator_tools": {
        "label": "Locators",
        "color": toolColors.TOOLBAR_RED,
        "items": [
            {"id": "create_locator", "shortcuts": [
                {"id": "locator_select_temp", "keys": [QtCore.Qt.Key_Control]},
                {"id": "locator_remove_temp", "keys": [QtCore.Qt.Key_Control, QtCore.Qt.Key_Shift, QtCore.Qt.Key_Alt]}]},
            {"id": "locator_select_temp"},
            {"id": "locator_remove_temp"},
        ],
    },
    # --- Selection & Pose ---
    "selector_tools": {
        "label": "Selector",
        "color": toolColors.TOOLBAR_GREEN,
        "items": [
            {"id": "selector"},
            {"id": "select_hierarchy"},
        ],
    },
    "opposite_tools": {
        "label": "Opposite",
        "color": toolColors.TOOLBAR_GREEN,
        "items": [
            {
                "id": "select_opposite",
                "default": True,
                "shortcuts": [
                    {"id": "opposite_add", "keys": [QtCore.Qt.Key_Shift]},
                    {"id": "opposite_copy", "keys": [QtCore.Qt.Key_Alt]},
                ],
            },
            {"id": "opposite_add"},
            {"id": "opposite_copy"},
        ],
    },
    "mirror_tools": {
        "label": "Mirror",
        "color": toolColors.TOOLBAR_GREEN,
        "items": [
            {
                "id": "mirror",
                "default": True,
                "shortcuts": [
                    {"id": "mirror_add_invert", "keys": [QtCore.Qt.Key_Shift]},
                    {"id": "mirror_add_keep", "keys": [QtCore.Qt.Key_Control]},
                    {"id": "mirror_remove_exc", "keys": [QtCore.Qt.Key_Control, QtCore.Qt.Key_Shift]},
                ],
            },
            {"id": "mirror_add_invert"},
            {"id": "mirror_add_keep"},
            {"id": "mirror_remove_exc"},
            "separator",
            {"id": "mirror_help"},
        ],
    },
    "align_tools": {
        "label": "Align Objects",
        "color": toolColors.TOOLBAR_GREEN,
        "items": [
            {
                "id": "align_objects",
                "default": True,
                "shortcuts": [
                    {"id": "align_object_translation", "keys": [QtCore.Qt.Key_Shift]},
                    {"id": "align_object_rotation", "keys": [QtCore.Qt.Key_Control]},
                    {"id": "align_object_scale", "keys": [QtCore.Qt.Key_Control, QtCore.Qt.Key_Shift]},
                ],
            },
            {"id": "align_object_translation"},
            {"id": "align_object_rotation"},
            {"id": "align_object_scale"},
            "separator",
            {"id": "align_objects_help"},
        ],
    },
    "selection_tools": {
        "label": "Selection",
        "color": toolColors.TOOLBAR_GREEN,
        "toolbar": False,
        "items": [
            {"id": "selector"},
            {"section": "opposite_tools"},
            {"section": "mirror_tools"},
            {"id": "select_hierarchy"},
        ],
    },
    "pose_animation_section": {
        "label": "Pose & Animation",
        "color": toolColors.TOOLBAR_GREEN,
        "items": [
            {
                "id": "copy_pose",
                "default": True,
                "shortcuts": [{"id": "paste_pose", "keys": [QtCore.Qt.Key_Control]}],
            },
            {"id": "paste_pose"},
            "separator",
            {
                "id": "copy_animation",
                "default": True,
                "shortcuts": [
                    {"id": "paste_animation", "keys": [QtCore.Qt.Key_Shift]},
                    {"id": "paste_insert_animation", "keys": [QtCore.Qt.Key_Control]},
                    {"id": "paste_opposite_animation", "keys": [QtCore.Qt.Key_Control, QtCore.Qt.Key_Shift]},
                ],
            },
            {"id": "paste_animation"},
            {"id": "paste_insert_animation"},
            {"id": "paste_opposite_animation"},
            {"id": "paste_animation_to"},
        ],
    },
    # --- Tangents ---
    "tangent_buttons": {
        "label": "Tangents",
        "icon": icons.tangent_auto,
        "color": toolColors.TOOLBAR_ORANGE,
        "items": [
            {"id": "tangent_cycle_matcher"},
            {"id": "tangent_bouncy", "default": True},
            "separator",
            {"id": "tangent_auto", "default": True},
            {"id": "tangent_spline", "default": True},
            {"id": "tangent_clamped"},
            {"id": "tangent_linear", "default": True},
            {"id": "tangent_flat"},
            {"id": "tangent_step", "default": True},
            {"id": "tangent_plateau"},
        ],
    },
    # --- Special Tools ---
    "animation_offset_tools": {
        "label": "Animation Offset",
        "color": toolColors.TOOLBAR_PURPLE,
        "items": [
            {"id": "animation_offset", "default": True},
        ],
    },
    "micro_move_tools": {
        "label": "Micro Move",
        "color": toolColors.TOOLBAR_PURPLE,
        "items": [
            {"id": "micro_move"},
        ],
    },
    "temp_pivot_tools": {
        "label": "Temp Pivot",
        "color": toolColors.TOOLBAR_PURPLE,
        "items": [
            {"id": "temp_pivot", "default": True},
            {"id": "temp_pivot_last_object"},
            {"id": "temp_pivot_centered"},
            {"id": "temp_pivot_worldspace"},
            "separator",
            {"id": "temp_pivot_edit"},
            {"id": "temp_pivot_reset"},
            "separator",
            {"id": "temp_pivot_help"},
        ],
    },
    "follow_cam_tools": {
        "label": "Follow Cam",
        "color": toolColors.TOOLBAR_PURPLE,
        "items": [
            {
                "id": "follow_cam",
                "default": True,
                "shortcuts": [
                    {"id": "follow_cam_translation", "keys": [QtCore.Qt.Key_Shift]},
                    {"id": "follow_cam_rotation", "keys": [QtCore.Qt.Key_Control]},
                    {"id": "follow_cam_remove", "keys": [QtCore.Qt.Key_Control, QtCore.Qt.Key_Alt]},
                ],
            },
            {"id": "follow_cam_translation"},
            {"id": "follow_cam_rotation"},
            "separator",
            {"id": "follow_cam_remove"},
        ],
    },
    "special_tools_section": {
        "label": "Special Tools",
        "color": toolColors.TOOLBAR_PURPLE,
        "toolbar": False,
        "items": [
            {"id": "animation_offset"},
            "separator",
            {"id": "micro_move"},
            "separator",
            {"section": "temp_pivot_tools"},
            {"section": "follow_cam_tools"},
        ],
    },
    # --- Links & Worldspace ---
    "link_worldspace_tools": {
        "label": "Links & Worldspace",
        "color": toolColors.TOOLBAR_GREEN,
        "items": [
            {
                "id": "link_copy",
                "default": True,
                "shortcuts": [
                    {"id": "link_paste", "keys": [QtCore.Qt.Key_Control]},
                    {"id": "link_autolink", "keys": [QtCore.Qt.Key_Alt]},
                ],
            },
            {"id": "link_autolink"},
            "separator",
            {"id": "link_paste"},
            "separator",
            {
                "id": "ws_copy_frame",
                "label": "Copy World Space",
                "default": True,
                "shortcuts": [
                    {"id": "ws_paste_frame", "keys": [QtCore.Qt.Key_Control]},
                    {"id": "ws_copy_range", "keys": [QtCore.Qt.Key_Shift]},
                    {"id": "ws_paste", "keys": [QtCore.Qt.Key_Control, QtCore.Qt.Key_Shift]},
                ],
            },
            {"id": "ws_copy_range"},
            "separator",
            {"id": "ws_paste_frame"},
            {"id": "ws_paste"},
        ],
    },
    "attribute_tools": {
        "label": "Attributes Switcher",
        "color": toolColors.TOOLBAR_GREEN,
        "items": [
            {"id": "attribute_switcher", "default": True},
            {"id": "gimbal"},
        ],
    },
    # --- Workspaces & Extensions ---
    "selection_set_tools": {
        "label": "Selection Sets",
        "items": [
            {
                "id": "selection_sets",
                "default": True,
                "shortcuts": [
                    {"id": "selection_sets_quick_export", "keys": [QtCore.Qt.Key_Control]},
                    {"id": "selection_sets_quick_import", "keys": [QtCore.Qt.Key_Control, QtCore.Qt.Key_Shift]},
                    {"id": "selection_sets_export", "keys": [QtCore.Qt.Key_Alt]},
                    {"id": "selection_sets_import", "keys": [QtCore.Qt.Key_Control, QtCore.Qt.Key_Alt]},
                    {"id": "selection_sets_clear_all", "keys": [QtCore.Qt.Key_Control, QtCore.Qt.Key_Alt, QtCore.Qt.Key_Shift]},
                ],
            },
            {"id": "selection_sets_quick_export"},
            {"id": "selection_sets_quick_import"},
            {"id": "selection_sets_export"},
            {"id": "selection_sets_import"},
            {"id": "selection_sets_clear_all"},
        ],
    },
    "orbit_tools": {
        "label": "Orbit",
        "items": [
            {"id": "orbit", "default": True},
        ],
    },
    "tracer_tools": {
        "label": "Tracer",
        "color": toolColors.TOOLBAR_RED,
        "items": [
            {
                "id": "create_tracer",
                "default": True,
                "shortcuts": [
                    {"id": "tracer_refresh", "keys": [QtCore.Qt.Key_Control]},
                    {"id": "tracer_show_hide", "keys": [QtCore.Qt.Key_Shift]},
                    {"id": "tracer_remove", "keys": [QtCore.Qt.Key_Control, QtCore.Qt.Key_Alt]},
                ],
            },
            {"type": "widget", "id": "tracer_connected"},
            "separator",
            {"id": "tracer_refresh"},
            {"id": "tracer_show_hide"},
            {"id": "tracer_offset_node"},
            "separator",
            {"id": "tracer_grey"},
            {"id": "tracer_red"},
            {"id": "tracer_blue"},
            "separator",
            {"id": "tracer_remove"},
        ],
    },
    "extension_tools": {
        "label": "Extensions",
        "toolbar": True,
        "items": [
            {"type": "widget", "id": "overshoot_sliders", "default": True},
            {"type": "widget", "id": "attribute_switcher_euler_filter"},
            {"id": "custom_graph"},
            "separator",
            {"id": "custom_tools"},
            {"id": "custom_scripts"},
        ],
    },
    # --- Extra Specific ---
    "extra_tools": {
        "label": "Extra Tools",
        "items": [
            {"id": "graph_extra_tools", "default": True},
            {"id": "graph_select_object_from_curve"},
            {"id": "graph_isolate_curves"},
            "separator",
            {"id": "graph_flip"},
            {"id": "graph_overlap_forward", "shortcuts": [{"id": "graph_overlap_backward", "keys": [QtCore.Qt.Key_Shift]}]},
            "separator",
            {"id": "graph_toggle_mute"},
            {"id": "graph_toggle_lock"},
            {"id": "graph_match_keys"},
            {
                "id": "enable_graph_filter",
                "shortcuts": [
                    {"id": "disable_graph_filter", "keys": [QtCore.Qt.Key_Control]},
                ],
            },
            "separator",
            {"id": "snap", "default": True},
        ],
    },
    "system": {
        "label": "System",
        "hiddeable": False,
        "items": [{"id": "settings"}],
    },
}

TOOLBAR_DEFAULT_SLIDER_MODES = {
    "main": {
        "slider_blend": ["connect_neighbors"],
        "slider_tween": ["tweener"],
        "slider_tangent": [],
    },
    "graph": {
        "slider_blend": ["connect_neighbors"],
        "slider_tween": ["tweener"],
        "slider_tangent": ["blend_best_guess"],
    },
}


def _descriptor_overrides(item, *, include_keys=True):
    ignored = {"id", "section", "shortcuts"}
    if not include_keys:
        ignored.add("keys")
    return {key: value for key, value in item.items() if key not in ignored}


def _apply_shortcuts(tool, item):
    shortcut_items = item.get("shortcuts") or []
    if not shortcut_items:
        return tool

    key_masks = (
        (QtCore.Qt.Key_Shift, 1),
        (QtCore.Qt.Key_Control, 4),
        (QtCore.Qt.Key_Alt, 8),
    )

    def shortcut_display(tool_state, keys):
        return {
            "icon": tool_state.get("icon"),
            "label": tool_state.get("label") or tool_state.get("status_title") or tool_state.get("id"),
            "keys": keys,
        }

    def shortcut_mask(keys):
        return sum(mask for key, mask in key_masks if key in (keys or []))

    shortcuts = [shortcut_display(tool, "Click")]
    variants = []
    for shortcut_item in shortcut_items:
        tool_id = shortcut_item.get("id")
        if not tool_id:
            continue
        variant = get_tool(tool_id, **_descriptor_overrides(shortcut_item, include_keys=False))
        variant["mask"] = shortcut_mask(shortcut_item.get("keys", []))
        variant.setdefault("shortcuts", [shortcut_display(variant, "Click")])
        shortcuts.append(shortcut_display(variant, shortcut_item.get("keys", [])))
        variants.append(variant)

    tool["shortcuts"] = shortcuts
    tool["shortcut_variants"] = variants
    return tool


def get_tool(tool_id, **overrides):
    """Retrieve a tool definition with optional overrides."""
    if tool_id not in TOOL_DEFINITIONS:
        raise KeyError("Unknown tool id: {}".format(tool_id))

    tool = dict(TOOL_DEFINITIONS[tool_id])
    tool.update(overrides)
    tool.setdefault("id", tool_id)
    tool.setdefault("default", False)

    callback = tool.get("callback")
    if callback:
        if getattr(callback, "__name__", None) != tool_id:
            tool["callback"] = trigger.make_command_callback(tool_id, callback)
        elif not getattr(callback, "_tkm_trigger_proxy", False):
            trigger.register_command(tool_id, callback)
    return tool


def _resolve_section_item(item, toolbar_id=None):
    if isinstance(item, str):
        return item

    section_ref = item.get("section")
    if section_ref:
        section = get_tool_section(section_ref, toolbar_id=toolbar_id)
        if section:
            return {"type": "group", "items": section.get("items", []), "label": section.get("label")}
        return []

    tool_id = item.get("id")
    if tool_id:
        return _apply_shortcuts(get_tool(tool_id, **_descriptor_overrides(item)), item)

    return None


def get_tool_section(section_id, resolve_items=True, toolbar_id=None):
    section_def = TOOL_SECTION_DEFINITIONS.get(section_id)
    if not section_def:
        return None

    section = dict(section_def)
    section["id"] = section_id
    if toolbar_id and section.get("type") == "slider":
        section["default_modes"] = list(TOOLBAR_DEFAULT_SLIDER_MODES.get(toolbar_id, {}).get(section_id, []))
    if not resolve_items:
        section["items"] = list(section_def.get("items", []))
        return section

    resolved = []
    for item in section_def.get("items", []):
        resolved_item = _resolve_section_item(item, toolbar_id=toolbar_id)
        if resolved_item is None:
            continue
        if isinstance(resolved_item, list):
            resolved.extend(resolved_item)
        else:
            resolved.append(resolved_item)
    section["items"] = resolved
    return section


def get_section_icon(section_id):
    section = get_tool_section(section_id, toolbar_id="main")
    if not section:
        return None
    if section.get("icon"):
        return section.get("icon")

    def find_icon(items):
        for item in items:
            if item == "separator" or not isinstance(item, dict):
                continue
            if item.get("type") == "group":
                icon = find_icon(item.get("items", []))
                if icon:
                    return icon
                continue
            icon = item.get("icon")
            if icon:
                return icon
        return None

    return find_icon(section.get("items", []))


def get_tool_tint_color(tool_id, default=None):
    def find_tint(item, inherited_color=None):
        if item == "separator" or item is None:
            return None
        if not isinstance(item, dict):
            return None

        section_ref = item.get("section")
        if section_ref:
            section = TOOL_SECTION_DEFINITIONS.get(section_ref)
            if not section:
                return None
            section_color = section.get("color") or inherited_color
            for child in section.get("items", []):
                color = find_tint(child, inherited_color=section_color)
                if color is not None:
                    return color
            return None

        if item.get("id") == tool_id:
            return inherited_color

        for shortcut in item.get("shortcuts") or []:
            color = find_tint(shortcut, inherited_color=inherited_color)
            if color is not None:
                return color
        return None

    for section in TOOL_SECTION_DEFINITIONS.values():
        section_color = section.get("color")
        for item in section.get("items", []):
            color = find_tint(item, inherited_color=section_color)
            if color is not None:
                return color
    return default


def get_toolbar_sections(layout_id, resolve_items=True):
    if layout_id not in {"main", "graph"}:
        return []

    section_ids = list(TOOL_SECTION_DEFINITIONS.keys())
    return [
        section
        for section in (
            get_tool_section(section_id, resolve_items=resolve_items, toolbar_id=layout_id)
            for section_id in section_ids
            if not TOOL_SECTION_DEFINITIONS[section_id].get("hotkey_only")
            and TOOL_SECTION_DEFINITIONS[section_id].get("toolbar") is not False
        )
        if section is not None
    ]
