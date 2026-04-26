from functools import partial

try:
    from PySide6 import QtCore
except ImportError:
    from PySide2 import QtCore

import TheKeyMachine.mods.mediaMod as media
import TheKeyMachine.mods.keyToolsMod as keyTools
import TheKeyMachine.mods.helperMod as helper
import TheKeyMachine.mods.barMod as bar
import TheKeyMachine.mods.generalMod as general
import TheKeyMachine.mods.uiMod as ui
import TheKeyMachine.core.trigger as trigger
import TheKeyMachine.core.toolMenus as toolMenus
import TheKeyMachine.tools.ibookmarks.api as iBookmarksApi
import TheKeyMachine.tools.selection_sets.api as selectionSetsApi
from TheKeyMachine.tools import colors as toolColors
from TheKeyMachine.tools import common as toolCommon

"""
TheKeyMachine Toolbox
====================
Centralized definitions for all tools to ensure consistent naming, 
icons, callbacks, and documentation across different UI contexts 
(Main Toolbar, Custom Graph, Context Menus).
"""

TOOL_DEFINITIONS = {
    "share_keys": {
        "type": "tool",
        "key": "share_keys",
        "label": "Share Keys",
        "text": "sK",
        "icon_path": media.share_keys_image,
        "callback": keyTools.share_keys,
        "menu_setup_fn": toolMenus.build_share_keys_menu,
        "tooltip_template": helper.share_keys_tooltip_text,
    },
    "reblock": {
        "type": "tool",
        "key": "reblock",
        "label": "reBlock",
        "text": "rB",
        "icon_path": media.reblock_keys_image,
        "callback": keyTools.reblock_move,
        "tooltip_template": helper.reblock_move_tooltip_text,
        "description": "Reblock the selected animation.",
    },
    "bake_animation_custom": {
        "type": "tool",
        "key": "bake_animation_custom",
        "label": "Bake Custom Interval",
        "text": "BA",
        "icon_path": media.bake_animation_custom_image,
        "callback": bar.bake_animation_custom_window,
        "tooltip_template": helper.bake_animation_custom_tooltip_text,
    },
    "bake_animation_1": {
        "type": "tool",
        "key": "bake_animation_1",
        "label": "Bake on Ones",
        "text": "BA",
        "icon_path": media.bake_animation_1_image,
        "callback": keyTools.bake_animation_1,
        "tooltip_template": helper.bake_animation_1_tooltip_text,
    },
    "bake_animation_2": {
        "type": "tool",
        "key": "bake_animation_2",
        "label": "Bake on Twos",
        "text": "BA",
        "icon_path": media.bake_animation_2_image,
        "callback": keyTools.bake_animation_2,
        "tooltip_template": helper.bake_animation_2_tooltip_text,
    },
    "bake_animation_3": {
        "type": "tool",
        "key": "bake_animation_3",
        "label": "Bake on Threes",
        "text": "BA",
        "icon_path": media.bake_animation_3_image,
        "callback": keyTools.bake_animation_3,
        "tooltip_template": helper.bake_animation_3_tooltip_text,
    },
    "bake_animation_4": {
        "type": "tool",
        "key": "bake_animation_4",
        "label": "Bake on Fours",
        "text": "BA",
        "icon_path": media.bake_animation_3_image,
        "callback": keyTools.bake_animation_4,
        "tooltip_template": helper.bake_animation_4_tooltip_text,
    },
    "orbit": {
        "type": "check",
        "key": "orbit",
        "label": "Orbit",
        "text": "Orb",
        "icon_path": media.orbit_ui_image,
        "callback": lambda: ui.orbit_window(0, 0),
        "tooltip_template": helper.orbit_tooltip_text,
    },
    "attribute_switcher": {
        "type": "check",
        "key": "attribute_switcher",
        "label": "Attribute Switcher",
        "text": "SSw",
        "icon_path": media.attribute_switcher_image,
        "callback": lambda: ui.toggle_attribute_switcher_window(),
        "tooltip_template": helper.attribute_switcher_tooltip_text,
    },
    "gimbal": {
        "type": "tool",
        "key": "gimbal",
        "label": "Gimbal Fixer",
        "text": "Gim",
        "icon_path": media.reblock_keys_image,
        "callback": bar.gimbal_fixer_window,
        "tooltip_template": helper.gimbal_fixer_tooltip_text,
    },
    "worldspace": {
        "type": "tool",
        "key": "worldspace",
        "label": "World Space",
        "text": "WS",
        "icon_path": media.worldspace_copy_animation_image,
        "callback": bar.mod_worldspace_copy_animation,
        "tooltip_template": helper.copy_worldspace_tooltip_text,
    },
    "temp_pivot": {
        "type": "tool",
        "key": "temp_pivot",
        "label": "Temp Pivot",
        "text": "TP",
        "icon_path": media.temp_pivot_image,
        "callback": lambda *args: bar.create_temp_pivot(False),
        "tooltip_template": helper.temp_pivot_tooltip_text,
    },
    "micro_move": {
        "type": "check",
        "key": "micro_move",
        "label": "Micro Move",
        "text": "MM",
        "icon_path": media.ruler_image,
        "callback": trigger.make_command_callback("micro_move_toggle"),
        "tooltip_template": helper.micro_move_tooltip_text,
    },
    "move_left": {
        "type": "tool",
        "key": "move_left",
        "label": "Nudge Left",
        "icon_path": media.nudge_left_image,
        "callback": trigger.make_command_callback("nudge_left"),
        "description": "Nudge selected keys to the left.",
    },
    "move_right": {
        "type": "tool",
        "key": "move_right",
        "label": "Nudge Right",
        "icon_path": media.nudge_right_image,
        "callback": trigger.make_command_callback("nudge_right"),
        "description": "Nudge selected keys to the right.",
    },
    "nudge_remove_inbetween": {
        "type": "tool",
        "key": "nudge_remove_inbetween",
        "label": "Remove Inbetween",
        "icon_path": media.remove_inbetween_image,
        "callback": trigger.make_command_callback("remove_inbetween"),
        "tooltip_template": helper.remove_inbetween_tooltip_text,
        "description": "Remove inbetweens using the current nudge step value.",
    },
    "nudge_insert_inbetween": {
        "type": "tool",
        "key": "nudge_insert_inbetween",
        "label": "Insert Inbetween",
        "icon_path": media.insert_inbetween_image,
        "callback": trigger.make_command_callback("insert_inbetween"),
        "tooltip_template": helper.insert_inbetween_tooltip_text,
        "description": "Insert inbetweens using the current nudge step value.",
    },
    "clear_selected_keys": {
        "type": "tool",
        "key": "clear_sel",
        "label": "Clear Selection",
        "text": "x",
        "callback": trigger.make_command_callback("clear_selected_keys", keyTools.clear_selected_keys),
        "tooltip_template": helper.clear_selected_keys_widget_tooltip_text,
        "default_visible": False,
    },
    "select_scene_animation": {
        "type": "tool",
        "key": "select_scene",
        "label": "Select Scene Anim",
        "text": "s",
        "callback": trigger.make_command_callback("select_all_animation_curves", keyTools.select_all_animation_curves),
        "tooltip_template": helper.select_scene_animation_widget_tooltip_text,
        "default_visible": False,
    },
    "static": {
        "type": "tool",
        "key": "static",
        "label": "Delete Static Keys",
        "text": "S",
        "icon_path": media.delete_animation_image,
        "tooltip_template": helper.static_tooltip_text,
        "description": "Flatten the selected curve so it holds the first selected value.",
        "callback": lambda: keyTools.deleteStaticCurves(),
    },
    "match": {
        "type": "tool",
        "key": "match",
        "label": "Match",
        "text": "M",
        "icon_path": media.match_image,
        "tooltip_template": helper.match_keys_tooltip_text,
        "description": "Match one selected curve to another.",
        "callback": lambda: keyTools.match_keys(),
    },
    "flip": {
        "type": "tool",
        "key": "flip",
        "label": "Flip",
        "text": "F",
        "tooltip_template": helper.flip_tooltip_text,
        "description": "Inverts the selected curve vertically.",
        "callback": lambda: keyTools.flipCurves(),
    },
    "snap": {
        "type": "tool",
        "key": "snap",
        "label": "Snap",
        "text": "Sn",
        "tooltip_template": helper.snap_tooltip_text,
        "description": "Snap selected sub-frame keys to the nearest whole frame.",
        "callback": lambda: keyTools.snapKeyframes(),
    },
    "overlap": {
        "type": "tool",
        "key": "overlap",
        "label": "Overlap",
        "text": "O",
        "tooltip_template": helper.overlap_tooltip_text,
        "description": "Offset selected curves to create overlap.",
        "callback": keyTools.mod_overlap_animation,
    },
    "isolate_master": {
        "type": "tool",
        "key": "isolate_master",
        "label": "Isolate",
        "icon_path": media.isolate_image,
        "callback": bar.isolate_master,
        "tooltip_template": helper.isolate_tooltip_text,
    },
    "align_selected_objects": {
        "type": "tool",
        "key": "align_selected_objects",
        "label": "Align",
        "icon_path": media.match_image,
        "callback": bar.align_selected_objects,
        "tooltip_template": helper.align_tooltip_text,
    },
    "mod_tracer": {
        "type": "tool",
        "key": "mod_tracer",
        "label": "Tracer",
        "icon_path": media.tracer_image,
        "callback": bar.create_tracer,
        "tooltip_template": helper.tracer_tooltip_text,
    },
    "reset_objects_mods": {
        "type": "tool",
        "key": "reset_objects_mods",
        "label": "Reset Values",
        "command": "reset_values",
        "icon_path": media.asset_path("reset_animation_image"),
        "callback": keyTools.reset_objects_mods,
        "tooltip_template": helper.reset_values_tooltip_text,
    },
    "delete_all_animation": {
        "type": "tool",
        "key": "delete_all_animation",
        "label": "Delete All Animation",
        "command": "delete_all_animation",
        "icon_path": media.delete_animation_image,
        "callback": bar.mod_delete_animation,
        "tooltip_template": helper.delete_animation_tooltip_text,
    },
    "select_rig_controls": {
        "type": "tool",
        "key": "select_rig_controls",
        "label": "Select Rig Controls",
        "icon_path": media.select_rig_controls_image,
        "callback": bar.select_rig_controls,
        "tooltip_template": helper.select_rig_controls_tooltip_text,
        "description": "Select all rig controls. Ctrl+Click selects only animated rig controls.",
        "status_title": "Select Rig Controls",
        "status_description": "Select all rig controls. Ctrl+Click selects only animated rig controls.",
    },
    "pointer_sel_anim_rig": {
        "type": "tool",
        "key": "pointer_sel_anim_rig",
        "label": "Select Animated Rig Controls",
        "icon_path": media.select_rig_controls_animated_image,
        "tooltip_template": helper.select_rig_controls_animated_tooltip_text,
        "description": "Select only animated rig controls.",
        "status_title": "Select Animated Rig Controls",
        "status_description": "Select only animated rig controls.",
        "callback": bar.select_rig_controls_animated,
    },
    "pointer_depth_mover": {
        "type": "tool",
        "key": "pointer_depth_mover",
        "label": "Depth Mover",
        "icon_path": media.depth_mover_image,
        "callback": bar.depth_mover,
    },
    "selectOpposite": {
        "type": "tool",
        "key": "selectOpposite",
        "label": "Select Opposite",
        "icon_path": media.opposite_select_image,
        "callback": keyTools.selectOpposite,
        "tooltip_template": helper.opposite_select_tooltip_text,
    },
    "copyOpposite": {
        "type": "tool",
        "key": "copyOpposite",
        "label": "Copy Opposite",
        "icon_path": media.opposite_copy_image,
        "callback": keyTools.copyOpposite,
        "tooltip_template": helper.opposite_copy_tooltip_text,
    },
    "selection_sets": {
        "type": "check",
        "key": "selection_sets",
        "label": "Selection Sets",
        "text": "SS",
        "icon_path": media.selection_sets_image,
        "callback": trigger.make_command_callback("selection_sets_toggle"),
        "tooltip_template": helper.selection_sets_tooltip_text,
    },
    "selection_sets_quick_export": {
        "type": "tool",
        "key": "selection_sets_quick_export",
        "label": "Quick Export",
        "text": "QEx",
        "icon_path": media.selection_sets_export_image,
        "tooltip_template": helper.quick_export_selection_sets_tooltip_text,
        "description": "Export selection sets to the shared quick file, overwriting it.",
        "callback": selectionSetsApi.quick_export_selection_sets,
    },
    "selection_sets_quick_import": {
        "type": "tool",
        "key": "selection_sets_quick_import",
        "label": "Quick Import",
        "text": "QIm",
        "icon_path": media.selection_sets_import_image,
        "tooltip_template": helper.quick_import_selection_sets_tooltip_text,
        "description": "Import selection sets from the shared quick file.",
        "callback": selectionSetsApi.quick_import_selection_sets,
    },
    "selection_sets_export": {
        "type": "tool",
        "key": "selection_sets_export",
        "label": "Export",
        "text": "Ex",
        "icon_path": media.selection_sets_export_image,
        "tooltip_template": helper.export_selection_sets_tooltip_text,
        "description": "Export selection sets to a chosen file.",
        "callback": selectionSetsApi.export_selection_sets,
    },
    "selection_sets_import": {
        "type": "tool",
        "key": "selection_sets_import",
        "label": "Import",
        "text": "Im",
        "icon_path": media.selection_sets_import_image,
        "tooltip_template": helper.import_selection_sets_tooltip_text,
        "description": "Import selection sets from a chosen file.",
        "callback": selectionSetsApi.import_selection_sets,
    },
    "selection_sets_clear_all": {
        "type": "tool",
        "key": "selection_sets_clear_all",
        "label": "Clear All Select Sets",
        "text": "Clr",
        "icon_path": media.trash_image,
        "tooltip_template": helper.clear_selection_sets_tooltip_text,
        "description": "Delete every selection set in the current scene.",
        "callback": selectionSetsApi.clear_all_selection_sets,
    },
    "custom_graph": {
        "type": "check",
        "key": "custom_graph",
        "label": "Graph Editor Toolbar",
        "text": "GE",
        "icon_path": media.customGraph_image,
        "callback": trigger.make_command_callback("custom_graph_toggle"),
        "tooltip_template": helper.customGraph_tooltip_text,
    },
    "extra_graph_tools": {
        "type": "menu",
        "key": "extra",
        "label": "Extra Tools",
        "text": "E",
        "menu_setup_fn": toolMenus.build_extra_graph_tools_menu,
        "tooltip_template": helper.extra_tools_tooltip_text,
        "description": "Open extra graph tools.",
    },
    # "extra_tools": {
    #     "key": "extra",
    #     "label": "Extra Tools",
    #     "text": "E",
    #     "tooltip_template": helper.extra_tools_tooltip_text,
    #     "description": "Additional curve utilities.",
    #     "callback": lambda: keyTools.snapKeyframes(),
    # },
    "selectHierarchy": {
        "type": "tool",
        "key": "selectHierarchy",
        "label": "Select Hierarchy",
        "icon_path": media.select_hierarchy_image,
        "callback": bar.selectHierarchy,
        "tooltip_template": helper.select_hierarchy_tooltip_text,
    },
    "selector": {
        "type": "tool",
        "key": "selector",
        "label": "Selector",
        "icon_path": media.selector_image,
        "callback": bar.selector_window,
        "tooltip_template": helper.selector_tooltip_text,
    },
    "create_locator": {
        "type": "tool",
        "key": "create_locator",
        "label": "Create Locator",
        "icon_path": media.create_locator_image,
        "callback": bar.createLocator,
        "tooltip_template": helper.createLocator_tooltip_text,
    },
    "locator_select_temp": {
        "type": "tool",
        "key": "locator_select_temp",
        "label": "Select Temp Locators",
        "icon_path": media.create_locator_image,
        "callback": bar.selectTempLocators,
    },
    "locator_remove_temp": {
        "type": "tool",
        "key": "locator_remove_temp",
        "label": "Remove Temp Locators",
        "icon_path": media.create_locator_image,
        "callback": bar.deleteTempLocators,
    },
    "isolate_bookmarks": {
        "type": "tool",
        "key": "isolate_bookmarks",
        "label": "Bookmarks",
        "icon_path": media.ibookmarks_menu_image,
        "callback": iBookmarksApi.create_ibookmarks_window,
    },
    "isolate_help": {
        "type": "tool",
        "key": "isolate_help",
        "label": "Help",
        "icon_path": media.help_menu_image,
        "callback": lambda: general.open_url("https://thekeymachine.gitbook.io/base/the-toolbar/animation-tools/isolate"),
        "pinnable": False,
    },
    "align_help": {
        "type": "tool",
        "key": "align_help",
        "label": "Help",
        "icon_path": media.help_menu_image,
        "callback": lambda: general.open_url("https://thekeymachine.gitbook.io/base/the-toolbar/animation-tools/match-align"),
        "pinnable": False,
    },
    "copy_pose": {
        "type": "tool",
        "key": "copy_pose",
        "label": "Copy Pose",
        "icon_path": media.copy_pose_image,
        "callback": keyTools.copy_pose,
        "tooltip_template": helper.copy_pose_tooltip_text,
    },
    "paste_pose": {
        "type": "tool",
        "key": "paste_pose",
        "label": "Paste Pose",
        "icon_path": media.paste_pose_image,
        "callback": keyTools.paste_pose,
        "tooltip_template": helper.paste_pose_tooltip_text,
    },
    "copy_animation": {
        "type": "tool",
        "key": "copy_animation",
        "label": "Copy Animation",
        "icon_path": media.copy_animation_image,
        "callback": keyTools.copy_animation,
        "tooltip_template": helper.copy_animation_tooltip_text,
        "status_title": "Copy Animation",
        "status_description": "Copy animation from the current selection.",
    },
    "paste_animation": {
        "type": "tool",
        "key": "paste_animation",
        "label": "Paste Animation",
        "icon_path": media.paste_animation_image,
        "callback": keyTools.paste_animation,
        "tooltip_template": helper.paste_animation_tooltip_text,
    },
    "paste_insert_animation": {
        "type": "tool",
        "key": "paste_insert_animation",
        "label": "Paste Insert Animation",
        "icon_path": media.paste_insert_animation_image,
        "callback": keyTools.paste_insert_animation,
        "tooltip_template": helper.paste_insert_animation_tooltip_text,
    },
    "follow_cam": {
        "type": "tool",
        "key": "follow_cam",
        "label": "Follow Cam",
        "icon_path": media.follow_cam_image,
        "callback": lambda *args: bar.create_follow_cam(translation=True, rotation=True),
        "tooltip_template": helper.follow_cam_tooltip_text,
    },
    "animation_offset": {
        "type": "check",
        "key": "animation_offset",
        "label": "Anim Offset",
        "icon_path": media.animation_offset_image,
        "callback": trigger.make_command_callback("animation_offset_toggle"),
        "tooltip_template": helper.animation_offset_tooltip_text,
    },
    "mod_link_objects": {
        "type": "tool",
        "key": "mod_link_objects",
        "label": "Copy/Paste Link",
        "icon_path": media.link_objects_image,
        "callback": keyTools.copy_link,
        "tooltip_template": helper.link_objects_tooltip_text,
    },
    "copy_worldspace_single_frame": {
        "type": "tool",
        "key": "copy_worldspace_single_frame",
        "label": "Copy World Space",
        "icon_path": media.worldspace_copy_frame_image,
        "callback": bar.copy_worldspace_single_frame,
        "tooltip_template": helper.copy_worldspace_tooltip_text,
    },
    "paste_worldspace_single_frame": {
        "type": "tool",
        "key": "paste_worldspace_single_frame",
        "label": "Paste World Space",
        "icon_path": media.worldspace_paste_frame_image,
        "callback": bar.paste_worldspace_single_frame,
        "tooltip_template": helper.paste_worldspace_tooltip_text,
    },
    "align_translation": {
        "type": "tool",
        "key": "align_translation",
        "label": "Translation",
        "icon_path": media.align_menu_image,
        "callback": partial(bar.align_selected_objects, pos=True, rot=False, scl=False),
    },
    "align_rotation": {
        "type": "tool",
        "key": "align_rotation",
        "label": "Rotation",
        "icon_path": media.align_menu_image,
        "callback": partial(bar.align_selected_objects, pos=False, rot=True, scl=False),
    },
    "align_scale": {
        "type": "tool",
        "key": "align_scale",
        "label": "Scale",
        "icon_path": media.align_menu_image,
        "callback": partial(bar.align_selected_objects, pos=False, rot=False, scl=True),
    },
    "align_range": {
        "type": "tool",
        "key": "align_range",
        "label": "Match Range",
        "icon_path": media.match_image,
        "callback": bar.align_range,
    },
    "tracer_refresh": {
        "type": "tool",
        "key": "tracer_refresh",
        "label": "Refresh Tracer",
        "icon_path": media.refresh_image,
        "callback": bar.tracer_refresh,
    },
    "tracer_show_hide": {
        "type": "tool",
        "key": "tracer_show_hide",
        "label": "Toggle Tracer",
        "icon_path": media.tracer_show_hide_image,
        "callback": bar.tracer_show_hide,
    },
    "tracer_offset_node": {
        "type": "tool",
        "key": "tracer_offset_node",
        "label": "Select Offset Object",
        "icon_path": media.tracer_select_offset_image,
        "callback": bar.select_tracer_offset_node,
    },
    "tracer_grey": {
        "type": "tool",
        "key": "tracer_grey",
        "label": "Tracer Style: Grey",
        "icon_path": media.tracer_grey_image,
        "callback": bar.set_tracer_grey_color,
    },
    "tracer_red": {
        "type": "tool",
        "key": "tracer_red",
        "label": "Tracer Style: Red",
        "icon_path": media.tracer_red_image,
        "callback": bar.set_tracer_red_color,
    },
    "tracer_blue": {
        "type": "tool",
        "key": "tracer_blue",
        "label": "Tracer Style: Blue",
        "icon_path": media.tracer_blue_image,
        "callback": bar.set_tracer_blue_color,
    },
    "tracer_remove": {
        "type": "tool",
        "key": "tracer_remove",
        "label": "Remove Tracer",
        "icon_path": media.remove_image,
        "callback": bar.remove_tracer_node,
    },
    "reset_set_defaults": {
        "type": "tool",
        "key": "reset_set_defaults",
        "label": "Set Default Values For Selected",
        "icon_path": media.asset_path("reset_animation_image"),
        "callback": keyTools.save_default_values,
    },
    "reset_restore_defaults": {
        "type": "tool",
        "key": "reset_restore_defaults",
        "label": "Restore Default Values For Selected",
        "icon_path": media.asset_path("reset_animation_image"),
        "callback": keyTools.remove_default_values_for_selected_object,
    },
    "reset_clear_all": {
        "type": "tool",
        "key": "reset_clear_all",
        "label": "Clear All Saved Data",
        "icon_path": media.asset_path("reset_animation_image"),
        "callback": keyTools.restore_default_data,
    },
    "reset_help": {
        "type": "tool",
        "key": "reset_help",
        "label": "Help",
        "icon_path": media.help_menu_image,
        "callback": lambda: general.open_url("https://thekeymachine.gitbook.io/base/the-toolbar/animation-tools/reset-to-default"),
        "pinnable": False,
    },
    "mirror": {
        "type": "tool",
        "key": "mirror",
        "label": "Mirror",
        "icon_path": media.mirror_image,
        "callback": keyTools.mirror,
        "tooltip_template": helper.mirror_tooltip_text,
    },
    "mirror_add_invert": {
        "type": "tool",
        "key": "mirror_add_invert",
        "label": "Add Exception Invert",
        "icon_path": media.mirror_image,
        "callback": keyTools.add_mirror_invert_exception,
    },
    "mirror_add_keep": {
        "type": "tool",
        "key": "mirror_add_keep",
        "label": "Add Exception Keep",
        "icon_path": media.mirror_image,
        "callback": keyTools.add_mirror_keep_exception,
    },
    "mirror_remove_exc": {
        "type": "tool",
        "key": "mirror_remove_exc",
        "label": "Remove Exception",
        "icon_path": media.mirror_image,
        "callback": keyTools.remove_mirror_invert_exception,
    },
    "mirror_help": {
        "type": "tool",
        "key": "mirror_help",
        "label": "Help",
        "icon_path": media.help_menu_image,
        "callback": lambda: general.open_url("https://thekeymachine.gitbook.io/base/the-toolbar/animation-tools/mirror"),
        "pinnable": False,
    },
    "opposite_add": {
        "type": "tool",
        "key": "opposite_add",
        "label": "Add Opposite",
        "icon_path": media.opposite_add_image,
        "callback": keyTools.addSelectOpposite,
        "tooltip_template": helper.opposite_add_tooltip_text,
    },
    "opposite_copy": {
        "type": "tool",
        "key": "opposite_copy",
        "label": "Copy Opposite",
        "icon_path": media.opposite_copy_image,
        "callback": keyTools.copyOpposite,
        "tooltip_template": helper.opposite_copy_tooltip_text,
    },
    "paste_pose_direct": {
        "type": "tool",
        "key": "paste_pose_direct",
        "label": "Paste Pose",
        "icon_path": media.paste_pose_image,
        "callback": keyTools.paste_pose,
    },
    "pose_help": {
        "type": "tool",
        "key": "pose_help",
        "label": "Help",
        "icon_path": media.help_menu_image,
        "callback": lambda: general.open_url("https://thekeymachine.gitbook.io/base/the-toolbar/animation-tools/copy-paste-animation#pose-tools"),
        "pinnable": False,
    },
    "paste_animation_direct": {
        "type": "tool",
        "key": "paste_animation_direct",
        "label": "Paste Animation",
        "icon_path": media.paste_animation_image,
        "callback": keyTools.paste_animation,
    },
    "paste_insert_animation_direct": {
        "type": "tool",
        "key": "paste_insert_animation_direct",
        "label": "Paste Insert",
        "icon_path": media.paste_insert_animation_image,
        "callback": keyTools.paste_insert_animation,
    },
    "paste_opposite_animation_direct": {
        "type": "tool",
        "key": "paste_opposite_animation_direct",
        "label": "Paste Opposite",
        "icon_path": media.paste_opposite_animation_image,
        "callback": keyTools.paste_opposite_animation,
    },
    "paste_animation_to": {
        "type": "tool",
        "key": "paste_animation_to",
        "label": "Paste To",
        "icon_path": media.paste_animation_image,
        "callback": keyTools.paste_animation_to,
    },
    "copy_animation_help": {
        "type": "tool",
        "key": "cp_help",
        "label": "Help",
        "icon_path": media.help_menu_image,
        "callback": lambda: general.open_url("https://thekeymachine.gitbook.io/base/the-toolbar/animation-tools/copy-paste-animation"),
        "pinnable": False,
    },
    "tp_last_used": {
        "type": "tool",
        "key": "tp_last_used",
        "label": "Use Last Pivot",
        "icon_path": media.temp_pivot_use_last_image,
        "callback": lambda: bar.create_temp_pivot(True),
    },
    "temp_pivot_help": {
        "type": "tool",
        "key": "tp_help",
        "label": "Help",
        "icon_path": media.help_menu_image,
        "callback": lambda: general.open_url("https://thekeymachine.gitbook.io/base/the-toolbar/animation-tools/temp-pivots"),
        "pinnable": False,
    },
    "fcam_trans_only": {
        "type": "tool",
        "key": "fcam_trans_only",
        "label": "Follow only Translation",
        "icon_path": media.follow_cam_image,
        "callback": lambda: bar.create_follow_cam(translation=True, rotation=False),
    },
    "fcam_rot_only": {
        "type": "tool",
        "key": "fcam_rot_only",
        "label": "Follow only Rotation",
        "icon_path": media.follow_cam_image,
        "callback": lambda: bar.create_follow_cam(translation=False, rotation=True),
    },
    "fcam_remove": {
        "type": "tool",
        "key": "fcam_remove",
        "label": "Remove Follow Cam",
        "icon_path": media.remove_image,
        "callback": bar.remove_followCam,
    },
    "link_copy": {
        "type": "tool",
        "key": "link_copy",
        "label": "Copy Link Position",
        "icon_path": media.link_objects_copy_image,
        "callback": keyTools.copy_link,
    },
    "link_paste": {
        "type": "tool",
        "key": "link_paste",
        "label": "Paste Link Position",
        "icon_path": media.link_objects_paste_image,
        "callback": keyTools.paste_link,
    },
    "link_help": {
        "type": "tool",
        "key": "link_help",
        "label": "Help",
        "icon_path": media.help_menu_image,
        "callback": lambda: general.open_url("https://thekeymachine.gitbook.io/base/the-toolbar/animation-tools/link-objects"),
        "pinnable": False,
    },
    "ws_copy_range": {
        "type": "tool",
        "key": "ws_copy_range",
        "label": "Copy World Space - Selected Range",
        "icon_path": media.worldspace_copy_animation_image,
        "callback": bar.copy_range_worldspace_animation,
        "tooltip_template": helper.copy_worldspace_range_tooltip_text,
    },
    "ws_paste_frame": {
        "type": "tool",
        "key": "ws_paste_frame",
        "label": "Paste World Space",
        "icon_path": media.worldspace_paste_frame_image,
        "callback": bar.paste_worldspace_single_frame,
        "tooltip_template": helper.paste_worldspace_tooltip_text,
    },
    "ws_paste": {
        "type": "tool",
        "key": "ws_paste",
        "label": "Paste World Space - All Animation",
        "icon_path": media.worldspace_paste_animation_image,
        "callback": bar.color_worldspace_paste_animation,
        "tooltip_template": helper.paste_worldspace_animation_tooltip_text,
    },
    "worldspace_help": {
        "type": "tool",
        "key": "ws_help",
        "label": "Help",
        "description": "World Space tools.",
        "icon_path": media.help_menu_image,
        "callback": lambda: general.open_url("https://thekeymachine.gitbook.io/base/the-toolbar/animation-tools/copy-paste-animation#worldspace-tools"),
        "pinnable": False,
    },
    "custom_tools": {
        "type": "menu",
        "key": "custom_tools",
        "label": "Custom Tools",
        "icon_path": media.custom_tools_image,
        "menu_setup_fn": toolMenus.build_custom_tools_menu,
        "tooltip_template": helper.custom_tools_tooltip_text,
    },
    "custom_scripts": {
        "type": "menu",
        "key": "custom_scripts",
        "label": "Custom Scripts",
        "icon_path": media.custom_scripts_image,
        "menu_setup_fn": toolMenus.build_custom_scripts_menu,
        "tooltip_template": helper.custom_scripts_tooltip_text,
    },
    "settings": {
        "type": "menu",
        "key": "settings",
        "label": "Settings",
        "icon_path": media.settings_image,
        "description": "Access global preferences, check for updates, and view credits.",
    },
    "graph_isolate_curves": {
        "type": "tool",
        "key": "graph_isolate_curves",
        "label": "Isolate",
        "icon_path": media.isolate_image,
        "callback": keyTools.isolateCurve,
        "tooltip_template": helper.graph_isolate_curves_tooltip_text,
        "description": "Isolate selected curves.",
    },
    "graph_toggle_mute": {
        "type": "tool",
        "key": "graph_toggle_mute",
        "label": "Mute",
        "text": "Mt",
        "callback": keyTools.toggleMute,
        "tooltip_template": helper.graph_mute_tooltip_text,
        "description": "Toggle mute on selected curves.",
    },
    "graph_toggle_lock": {
        "type": "tool",
        "key": "graph_toggle_lock",
        "label": "Lock",
        "text": "Lk",
        "callback": keyTools.toggleLock,
        "tooltip_template": helper.graph_lock_tooltip_text,
        "description": "Toggle lock on selected curves.",
    },
    "graph_filter": {
        "type": "tool",
        "key": "graph_filter",
        "label": "Filter",
        "text": "Fi",
        "callback": ui.customGraph_filter_mods,
        "tooltip_template": helper.graph_filter_tooltip_text,
        "description": "Filter selection in the GraphEditor. Shift+Click to deactivate.",
    },
    "graph_reset": {
        "type": "tool",
        "key": "graph_reset",
        "label": "Reset",
        "text": "R",
        "command": "reset_values",
        "icon_path": media.asset_path("reset_animation_image"),
        "callback": keyTools.reset_objects_mods,
        "tooltip_template": helper.reset_values_tooltip_text,
        "description": "Reset the selected objects or graph targets to their default values.",
    },
    "graph_reset_translation": {
        "type": "tool",
        "key": "graph_reset_translation",
        "label": "Reset Translations",
        "text": "RT",
        "command": "reset_translations",
        "icon_path": media.asset_path("reset_animation_image"),
        "callback": lambda: keyTools.reset_object_values(reset_translations=True),
        "tooltip_template": helper.reset_translations_tooltip_text,
        "description": "Reset only translation values for the selected objects or graph targets.",
    },
    "graph_reset_rotation": {
        "type": "tool",
        "key": "graph_reset_rotation",
        "label": "Reset Rotations",
        "text": "RR",
        "command": "reset_rotations",
        "icon_path": media.asset_path("reset_animation_image"),
        "callback": lambda: keyTools.reset_object_values(reset_rotations=True),
        "tooltip_template": helper.reset_rotations_tooltip_text,
        "description": "Reset only rotation values for the selected objects or graph targets.",
    },
    "graph_reset_scales": {
        "type": "tool",
        "key": "graph_reset_scales",
        "label": "Reset Scales",
        "text": "RS",
        "command": "reset_scales",
        "icon_path": media.asset_path("reset_animation_image"),
        "callback": lambda: keyTools.reset_object_values(reset_scales=True),
        "tooltip_template": helper.reset_scales_tooltip_text,
        "description": "Reset only scale values for the selected objects or graph targets.",
    },
    "graph_reset_trs": {
        "type": "tool",
        "key": "graph_reset_trs",
        "label": "Reset Translation Rotation Scale",
        "text": "RTRS",
        "command": "reset_trs",
        "icon_path": media.asset_path("reset_animation_image"),
        "callback": lambda: keyTools.reset_object_values(
            reset_translations=True,
            reset_rotations=True,
            reset_scales=True,
        ),
        "tooltip_template": helper.reset_trs_tooltip_text,
        "description": "Reset translation, rotation, and scale values for the selected objects or graph targets.",
    },
    "tangent_cycle_matcher": {
        "type": "tool",
        "key": "tangent_cycle_matcher",
        "label": "Cycle Matcher",
        "text": "CM",
        "icon_path": media.asset_path("match_curve_cycle_image"),
        "callback": keyTools.match_curve_cycle,
        "tooltip_template": helper.tangent_cycle_matcher_tooltip_text,
        "description": "Curve cycle matcher.",
    },
    "tangent_bouncy": {
        "type": "tool",
        "key": "tangent_bouncy",
        "label": "Bouncy Tangent",
        "text": "BO",
        "icon_path": media.bouncy_tangent_image,
        "callback": keyTools.bouncy_tangets,
        "tooltip_template": helper.tangent_bouncy_tooltip_text,
        "description": "Set bouncy tangents.",
    },
    "tangent_auto": {
        "type": "tool",
        "key": "tangent_auto",
        "label": "Auto Tangent",
        "text": "AU",
        "icon_path": media.auto_tangent_image,
        "callback": lambda: bar.setTangent("auto"),
        "menu_setup_fn": partial(toolMenus.build_tangent_menu, tangent_type="auto", tangent_label="Auto Tangent", icon_path=media.auto_tangent_image),
        "tooltip_template": helper.auto_tangent_tooltip_text,
        "description": "Set selected keys to Auto tangents.",
    },
    "tangent_spline": {
        "type": "tool",
        "key": "tangent_spline",
        "label": "Spline Tangent",
        "text": "SP",
        "icon_path": media.spline_tangent_image,
        "callback": lambda: bar.setTangent("spline"),
        "menu_setup_fn": partial(toolMenus.build_tangent_menu, tangent_type="spline", tangent_label="Spline Tangent", icon_path=media.spline_tangent_image),
        "tooltip_template": helper.spline_tangent_tooltip_text,
        "description": "Set selected keys to Spline tangents.",
    },
    "tangent_clamped": {
        "type": "tool",
        "key": "tangent_clamped",
        "label": "Clamped Tangent",
        "text": "CL",
        "icon_path": media.clamped_tangent_image,
        "callback": lambda: bar.setTangent("clamped"),
        "menu_setup_fn": partial(toolMenus.build_tangent_menu, tangent_type="clamped", tangent_label="Clamped Tangent", icon_path=media.clamped_tangent_image),
        "tooltip_template": helper.clamped_tangent_tooltip_text,
        "description": "Set selected keys to Clamped tangents.",
    },
    "tangent_linear": {
        "type": "tool",
        "key": "tangent_linear",
        "label": "Linear Tangent",
        "text": "LI",
        "icon_path": media.linear_tangent_image,
        "callback": lambda: bar.setTangent("linear"),
        "menu_setup_fn": partial(toolMenus.build_tangent_menu, tangent_type="linear", tangent_label="Linear Tangent", icon_path=media.linear_tangent_image),
        "tooltip_template": helper.linear_tangent_tooltip_text,
        "description": "Set selected keys to Linear tangents.",
    },
    "tangent_flat": {
        "type": "tool",
        "key": "tangent_flat",
        "label": "Flat Tangent",
        "text": "FT",
        "icon_path": media.flat_tangent_image,
        "callback": lambda: bar.setTangent("flat"),
        "menu_setup_fn": partial(toolMenus.build_tangent_menu, tangent_type="flat", tangent_label="Flat Tangent", icon_path=media.flat_tangent_image),
        "tooltip_template": helper.flat_tangent_tooltip_text,
        "description": "Set selected keys to Flat tangents.",
    },
    "tangent_step": {
        "type": "tool",
        "key": "tangent_step",
        "label": "Step Tangent",
        "text": "ST",
        "icon_path": media.step_tangent_image,
        "callback": lambda: bar.setTangent("step"),
        "menu_setup_fn": partial(toolMenus.build_tangent_menu, tangent_type="step", tangent_label="Step Tangent", icon_path=media.step_tangent_image),
        "tooltip_template": helper.step_tangent_tooltip_text,
        "description": "Set selected keys to Stepped tangents.",
    },
    "tangent_plateau": {
        "type": "tool",
        "key": "tangent_plateau",
        "label": "Plateau Tangent",
        "text": "PT",
        "icon_path": media.plateau_tangent_image,
        "callback": lambda: bar.setTangent("plateau"),
        "menu_setup_fn": partial(toolMenus.build_tangent_menu, tangent_type="plateau", tangent_label="Plateau Tangent", icon_path=media.plateau_tangent_image),
        "tooltip_template": helper.plateau_tangent_tooltip_text,
        "description": "Set selected keys to Plateau tangents.",
    },
}

TOOL_SECTION_DEFINITIONS = {
    "main_key_editing": {
        "label": "Key Editing",
        "color": toolColors.green,
        "icon": None,
        "items": [
            {
                "id": "move_left",
                "default": True,
                "shortcuts": [
                    {"id": "nudge_remove_inbetween", "keys": [QtCore.Qt.Key_Shift]},
                ],
            },
            {"id": "nudge_remove_inbetween"},
            {
                "id": "move_right",
                "default": True,
                "shortcuts": [
                    {"id": "nudge_insert_inbetween", "keys": [QtCore.Qt.Key_Shift]},
                ],
            },
            {"id": "nudge_insert_inbetween"},
            {"widget": "nudge_value"},
            {"id": "clear_selected_keys"},
            {"id": "select_scene_animation"},
            "separator",
            {
                "id": "share_keys",
                "default": True,
                "shortcuts": [
                    {"id": "reblock", "keys": [QtCore.Qt.Key_Shift]},
                ],
            },
            {"id": "reblock"},
            "separator",
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
        ],
    },
    "slider_blend": {
        "label": "Blend Sliders",
        "color": toolColors.UI_COLORS.green.hex,
        "icon": None,
        "type": "slider",
        "slider_type": "blend",
        "modes_attr": "BLEND_MODES",
        "default_modes": ["connect_neighbors"],
    },
    "slider_tween": {
        "label": "Tween Sliders",
        "color": toolColors.UI_COLORS.yellow.hex,
        "icon": None,
        "type": "slider",
        "slider_type": "tween",
        "modes_attr": "TWEEN_MODES",
        "default_modes": ["tweener"],
    },
    "slider_tangent": {
        "label": "Tangent Sliders",
        "color": toolColors.UI_COLORS.orange.hex,
        "icon": None,
        "type": "slider",
        "slider_type": "tangent",
        "modes_attr": "TANGENT_MODES",
        "default_modes": ["blend_best_guess"],
    },
    "pointer_tools": {
        "label": "Pointer",
        "color": toolColors.red,
        "icon": None,
        "items": [
            {
                "id": "select_rig_controls",
                "default": True,
                "shortcuts": [
                    {"id": "pointer_sel_anim_rig", "keys": [QtCore.Qt.Key_Control]},
                ],
            },
            {"id": "pointer_sel_anim_rig"},
            "separator",
            {"id": "pointer_depth_mover"},
        ],
    },
    "isolate_tools": {
        "label": "Isolate",
        "color": toolColors.red,
        "icon": None,
        "items": [
            {"id": "isolate_master", "key": "isolate", "default": True},
            {"id": "isolate_bookmarks"},
            "separator",
            {"widget": "isolate_down_level"},
            "separator",
            {"id": "isolate_help"},
        ],
    },
    "locator_tools": {
        "label": "Locators",
        "color": toolColors.red,
        "icon": None,
        "items": [
            {"id": "create_locator", "default": True},
            {"id": "locator_select_temp"},
            {"id": "locator_remove_temp"},
        ],
    },
    "align_tools": {
        "label": "Align",
        "color": toolColors.red,
        "icon": None,
        "items": [
            {
                "id": "align_selected_objects",
                "key": "align",
                "default": True,
                "shortcuts": [
                    {"id": "align_translation", "keys": [QtCore.Qt.Key_Shift]},
                    {"id": "align_rotation", "keys": [QtCore.Qt.Key_Control]},
                    {"id": "align_scale", "keys": [QtCore.Qt.Key_Control, QtCore.Qt.Key_Shift]},
                ],
            },
            {"id": "align_translation"},
            {"id": "align_rotation"},
            {"id": "align_scale"},
            "separator",
            {"id": "align_range"},
            "separator",
            {"id": "align_help"},
        ],
    },
    "tracer_tools": {
        "label": "Tracer",
        "color": toolColors.red,
        "icon": None,
        "items": [
            {
                "id": "mod_tracer",
                "key": "tracer",
                "default": True,
                "shortcuts": [
                    {"id": "tracer_refresh", "keys": [QtCore.Qt.Key_Shift]},
                    {"id": "tracer_show_hide", "keys": [QtCore.Qt.Key_Control]},
                    {"id": "tracer_remove", "keys": [QtCore.Qt.Key_Control, QtCore.Qt.Key_Alt]},
                ],
            },
            {"widget": "tracer_connected"},
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
    "reset_tools": {
        "label": "Reset",
        "color": None,
        "icon": None,
        "items": [
            {
                "id": "reset_objects_mods",
                "key": "reset_values",
                "default": True,
                "shortcuts": [
                    {"id": "graph_reset_translation", "keys": [QtCore.Qt.Key_Shift]},
                    {"id": "graph_reset_rotation", "keys": [QtCore.Qt.Key_Control]},
                    {"id": "graph_reset_scales", "keys": [QtCore.Qt.Key_Alt]},
                    {"id": "graph_reset_trs", "keys": [QtCore.Qt.Key_Control, QtCore.Qt.Key_Shift]},
                ],
            },
            {"id": "graph_reset_translation"},
            {"id": "graph_reset_rotation"},
            {"id": "graph_reset_scales"},
            {"id": "graph_reset_trs"},
            {"id": "reset_set_defaults"},
            {"id": "reset_restore_defaults"},
            "separator",
            {"id": "reset_clear_all"},
            "separator",
            {"id": "reset_help"},
        ],
    },
    "delete_tools": {
        "label": "Delete Animation",
        "color": toolColors.red,
        "icon": None,
        "items": [
            {
                "id": "delete_all_animation",
                "key": "delete_anim",
                "default": True,
                "shortcuts": [
                    {"id": "static", "keys": [QtCore.Qt.Key_Shift]},
                ],
            },
            {"id": "static"},
        ],
    },
    "main_scene_tools": {
        "label": "Scene Tools",
        "color": toolColors.red,
        "icon": None,
        "items": [
            {"section": "pointer_tools"},
            {"section": "isolate_tools"},
            {"section": "locator_tools"},
            {"section": "align_tools"},
            {"section": "tracer_tools"},
            {"section": "reset_tools"},
            {"section": "delete_tools"},
        ],
    },
    "selection_tools": {
        "label": "Selection",
        "color": toolColors.green,
        "icon": None,
        "items": [
            {"id": "selector"},
            {
                "id": "selectOpposite",
                "key": "opposite_select",
                "default": True,
                "shortcuts": [
                    {"id": "opposite_add", "keys": [QtCore.Qt.Key_Shift]},
                    {"id": "opposite_copy", "keys": [QtCore.Qt.Key_Alt]},
                ],
            },
            {"id": "opposite_add"},
            {"id": "opposite_copy"},
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
            {"id": "selectHierarchy"},
        ],
    },
    "copy_pose_animation": {
        "label": "Copy Pose And Animation",
        "color": toolColors.green,
        "icon": None,
        "items": [
            {
                "id": "copy_pose",
                "default": True,
                "shortcuts": [
                    {"id": "paste_pose_direct", "keys": [QtCore.Qt.Key_Control]},
                ],
            },
            {"id": "paste_pose_direct"},
            "separator",
            {
                "id": "copy_animation",
                "key": "cp_copy_anim",
                "default": True,
                "shortcuts": [
                    {"id": "paste_animation_direct", "keys": [QtCore.Qt.Key_Control]},
                    {"id": "paste_insert_animation_direct", "keys": [QtCore.Qt.Key_Shift]},
                    {"id": "paste_opposite_animation_direct", "keys": [QtCore.Qt.Key_Control, QtCore.Qt.Key_Shift]},
                ],
            },
            {"id": "paste_animation_direct"},
            {"id": "paste_insert_animation_direct"},
            {"id": "paste_opposite_animation_direct"},
            {"id": "paste_animation_to"},
        ],
    },
    "tangent_buttons": {
        "label": "Tangents",
        "color": toolColors.orange,
        "icon": None,
        "items": [
            {"id": "tangent_cycle_matcher", "key": "cycle", "default_visible": False},
            {"id": "tangent_bouncy", "key": "bouncy"},
            {"id": "tangent_auto"},
            {"id": "tangent_spline", "default_visible": False},
            {"id": "tangent_clamped", "default_visible": False},
            {"id": "tangent_linear", "default_visible": False},
            {"id": "tangent_flat", "default_visible": False},
            {"id": "tangent_step"},
            {"id": "tangent_plateau", "default_visible": False},
        ],
    },
    "animation_offset": {
        "label": "Animation Offset",
        "color": toolColors.purple,
        "icon": None,
        "items": [{"id": "animation_offset"}],
    },
    "pivot_micro_follow": {
        "label": "Pivot And Micro Tools",
        "color": toolColors.purple,
        "icon": None,
        "items": [
            {
                "id": "temp_pivot",
                "default": True,
                "shortcuts": [
                    {"id": "tp_last_used", "keys": [QtCore.Qt.Key_Shift]},
                ],
            },
            {"id": "tp_last_used"},
            "separator",
            {"id": "micro_move"},
            {
                "id": "follow_cam",
                "default": True,
                "shortcuts": [
                    {"id": "fcam_trans_only", "keys": [QtCore.Qt.Key_Shift]},
                    {"id": "fcam_rot_only", "keys": [QtCore.Qt.Key_Control]},
                    {"id": "fcam_remove", "keys": [QtCore.Qt.Key_Control, QtCore.Qt.Key_Alt]},
                ],
            },
            {"id": "fcam_trans_only"},
            {"id": "fcam_rot_only"},
            "separator",
            {"id": "fcam_remove"},
        ],
    },
    "link_worldspace": {
        "label": "Links And World Space",
        "color": toolColors.green,
        "icon": None,
        "items": [
            {
                "id": "mod_link_objects",
                "key": "link_objects",
                "default": True,
                "shortcuts": [
                    {"id": "link_paste", "keys": [QtCore.Qt.Key_Shift]},
                ],
            },
            {"id": "link_copy"},
            {"id": "link_paste"},
            "separator",
            {"widget": "link_autolink"},
            "separator",
            {
                "id": "copy_worldspace_single_frame",
                "key": "ws_copy_frame",
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
            {"id": "attribute_switcher", "default": True},
        ],
    },
    "workspace_tools": {
        "label": "Workspaces",
        "color": None,
        "icon": None,
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
            {"id": "orbit", "default": True},
        ],
    },
    "settings_toggles": {
        "label": "Toolbar Toggles",
        "color": None,
        "icon": None,
        "items": [
            {"widget": "overshoot_sliders"},
            {"widget": "attribute_switcher_euler_filter"},
            {"id": "custom_graph", "default_visible": False},
        ],
    },
    "custom_menus": {
        "label": "Custom Menus",
        "color": None,
        "icon": None,
        "items": [
            {"id": "custom_tools", "default_visible": False},
            {"id": "custom_scripts", "default_visible": False},
        ],
    },
    "main_extension_tools": {
        "label": "Extensions",
        "color": None,
        "icon": None,
        "items": [
            {"section": "settings_toggles"},
            {"section": "custom_menus"},
        ],
    },
    "system": {
        "label": "System",
        "color": None,
        "icon": None,
        "hiddeable": False,
        "items": [{"id": "settings"}],
    },
    "graph_key_tools": {
        "label": "Graph Key Tools",
        "color": None,
        "icon": None,
        "items": [
            {"id": "static", "default": True},
            {
                "id": "share_keys",
                "text": "sK",
                "default": True,
                "shortcuts": [
                    {"id": "reblock", "keys": [QtCore.Qt.Key_Shift]},
                ],
            },
            {"id": "match", "text": "M", "default": True},
            {"id": "flip", "text": "F", "default": True},
            {"id": "snap", "text": "Sn", "default": True},
            {"id": "overlap", "text": "O", "default": True},
            {"id": "extra_graph_tools", "default": True},
        ],
    },
    "graph_curve_tools": {
        "label": "Graph Curve Tools",
        "color": None,
        "icon": None,
        "items": [
            {"id": "graph_isolate_curves", "key": "iso"},
            {"id": "graph_toggle_mute", "key": "mute"},
            {"id": "graph_toggle_lock", "key": "lock"},
            {"id": "graph_filter", "key": "filter"},
        ],
    },
    "graph_system": {
        "label": "Graph System",
        "color": None,
        "icon": None,
        "hiddeable": False,
        "items": [{"id": "settings"}],
    },
}


TOOLBAR_SECTION_LAYOUTS = {
    "main": [
        "main_key_editing",
        "slider_blend",
        "slider_tween",
        "main_scene_tools",
        "selection_tools",
        "copy_pose_animation",
        "tangent_buttons",
        "animation_offset",
        "pivot_micro_follow",
        "link_worldspace",
        "workspace_tools",
        "main_extension_tools",
        "system",
    ],
    "graph": [
        "graph_key_tools",
        "slider_tween",
        "slider_blend",
        "slider_tangent",
        "graph_curve_tools",
        "reset_tools",
        "tangent_buttons",
        "graph_system",
    ],
}


def _normalize_tool_state(state, fallback=None):
    fallback = fallback or {}
    raw_state = dict(state or {})
    normalized = dict(fallback)
    normalized.update(raw_state)

    label = (
        raw_state.get("label")
        or toolCommon.get_tooltip_title(normalized.get("tooltip_template"))
        or raw_state.get("text")
        or normalized.get("label")
        or normalized.get("text")
        or normalized.get("key", "")
    )
    normalized.setdefault("description", fallback.get("description", ""))
    resolved_status_title, resolved_status_description = toolCommon.resolve_status_metadata(
        title=label,
        description=normalized.get("description", ""),
        tooltip_template=normalized.get("tooltip_template"),
        status_title=raw_state.get("status_title") if "status_title" in raw_state else None,
        status_description=raw_state.get("status_description") if "status_description" in raw_state else None,
        fallback_title=normalized.get("key", ""),
    )
    normalized["status_title"] = resolved_status_title
    normalized["status_description"] = resolved_status_description
    return normalized


def _bind_tool_callback(tool_key, tool_state):
    callback = tool_state.get("callback")
    if not callback:
        return tool_state

    bound = dict(tool_state)
    command_name = bound.get("command") or tool_key
    bound["command"] = command_name
    bound["callback"] = trigger.make_command_callback(command_name, callback, aliases=bound.get("command_aliases"))
    return bound


def _resolve_tool_definition(tool_key, state):
    return _bind_tool_callback(tool_key, _normalize_tool_state(state))


def _keys_to_mask(keys):
    keys = keys or []
    mask = 0
    if QtCore.Qt.Key_Shift in keys:
        mask |= 1
    if QtCore.Qt.Key_Control in keys:
        mask |= 4
    if QtCore.Qt.Key_Alt in keys:
        mask |= 8
    return mask


def _item_options(item, *, exclude_keys=False):
    ignored = {"id", "section", "widget", "shortcuts"}
    if exclude_keys:
        ignored.add("keys")
    return {key: value for key, value in item.items() if key not in ignored}


def _shortcut_display(tool_state, keys):
    return {
        "icon": tool_state.get("icon_path"),
        "label": tool_state.get("label") or tool_state.get("status_title") or tool_state.get("key"),
        "keys": keys,
    }


def _resolve_raw_item(item):
    if "data" in item:
        return dict(item.get("data", {}))
    return _item_options(item, exclude_keys=True)


def _resolve_shortcut_item(item):
    keys = item.get("keys", [])

    if item.get("id"):
        variant = get_tool(item["id"], **_item_options(item, exclude_keys=True))
    elif item.get("type") == "raw":
        variant = _normalize_tool_state(_resolve_raw_item(item))
        variant = _bind_tool_callback(variant.get("key", "shortcut"), variant)
    else:
        return None, None

    variant["mask"] = _keys_to_mask(keys)
    variant.setdefault("shortcuts", [_shortcut_display(variant, "Click")])
    return variant, _shortcut_display(variant, keys)


def _apply_section_shortcuts(tool, item):
    shortcut_items = item.get("shortcuts") or []
    if not shortcut_items:
        return tool

    resolved_shortcuts = [_shortcut_display(tool, "Click")]
    variants = []
    for shortcut_item in shortcut_items:
        variant, shortcut = _resolve_shortcut_item(shortcut_item)
        if variant is None:
            continue
        resolved_shortcuts.append(shortcut)
        variants.append(variant)

    tool["shortcuts"] = resolved_shortcuts
    tool["shortcut_variants"] = variants
    return tool


def _resolve_section_item_data(item):
    if item == "separator":
        return "separator"

    if item.get("id"):
        tool = get_tool(item["id"], **_item_options(item))
        return _apply_section_shortcuts(tool, item)

    item_type = item.get("type")
    if item_type == "raw":
        return _resolve_raw_item(item)

    if item.get("widget"):
        return dict(item)

    return None


def get_tool(tool_id, **overrides):
    """Retrieve a tool definition with optional overrides."""
    if tool_id not in TOOL_DEFINITIONS:
        res = {"key": tool_id, "label": tool_id.replace("_", " ").capitalize()}
        res.update(overrides)
        return _normalize_tool_state(res)

    # Merge base definition with overrides
    tool = TOOL_DEFINITIONS[tool_id].copy()
    tool.update(overrides)
    return _resolve_tool_definition(tool_id, tool)


def _resolve_section_item(item):
    if isinstance(item, str):
        return item

    if item.get("section"):
        section = get_tool_section(item["section"])
        return section.get("items", []) if section else []

    return _resolve_section_item_data(item)


def get_tool_section(section_id, resolve_items=True):
    section_def = TOOL_SECTION_DEFINITIONS.get(section_id)
    if not section_def:
        return None

    section = dict(section_def)
    if not resolve_items:
        section["items"] = list(section_def.get("items", []))
        return section

    resolved = []
    for item in section_def.get("items", []):
        resolved_item = _resolve_section_item(item)
        if resolved_item is None:
            continue
        if isinstance(resolved_item, list):
            resolved.extend(resolved_item)
        else:
            resolved.append(resolved_item)
    section["items"] = resolved
    return section


def get_toolbar_sections(layout_id, resolve_items=True):
    section_ids = TOOLBAR_SECTION_LAYOUTS.get(layout_id, [])
    return [
        section
        for section in (get_tool_section(section_id, resolve_items=resolve_items) for section_id in section_ids)
        if section is not None
    ]
