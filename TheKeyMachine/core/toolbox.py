from functools import partial

try:
    from PySide6 import QtCore  # type: ignore
except ImportError:
    from PySide2 import QtCore  # type: ignore

import TheKeyMachine.mods.mediaMod as media
import TheKeyMachine.mods.keyToolsMod as keyTools
import TheKeyMachine.mods.helperMod as helper
import TheKeyMachine.mods.barMod as bar
import TheKeyMachine.mods.generalMod as general
import TheKeyMachine.mods.uiMod as ui
import TheKeyMachine.core.trigger as trigger
import TheKeyMachine.tools.ibookmarks.api as iBookmarksApi
import TheKeyMachine.tools.selection_sets.api as selectionSetsApi
from TheKeyMachine.tools import colors as toolColors

"""
TheKeyMachine Toolbox
====================
Centralized definitions for all tools to ensure consistent naming, 
icons, callbacks, and documentation across different UI contexts 
(Main Toolbar, Custom Graph, Context Menus).
"""


def _tool_menu_builder(builder_name, **preset_kwargs):
    def _build(menu, source_widget=None):
        import TheKeyMachine.core.toolMenus as toolMenus

        builder = getattr(toolMenus, builder_name)
        return builder(menu, source_widget=source_widget, **preset_kwargs)

    return _build


TOOL_DEFINITIONS = {
    "toolbar_toggle": {
        "type": "tool",
        "label": "Toggle Toolbar",
        "icon_path": media.tool_icon,
    },
    "toolbar_add_shelf_button": {
        "type": "tool",
        "label": "Add Toggle Button To Shelf",
        "icon_path": media.asset_path("tool_icon"),
    },
    "toolbar_reload": {
        "type": "tool",
        "label": "Reload",
        "icon_path": media.reload_image,
    },
    "toolbar_unload": {
        "type": "tool",
        "label": "Unload",
        "icon_path": media.close_image,
    },
    "check_for_updates": {
        "type": "tool",
        "label": "Check for Updates",
        "icon_path": media.check_updates_image,
    },
    "orbit_window": {
        "type": "tool",
        "label": "Orbit Window",
        "icon_path": media.orbit_ui_image,
    },
    "hotkeys_window": {
        "type": "tool",
        "label": "Hotkeys",
        "icon_path": media.hotkeys_image,
    },
    "about_window": {
        "type": "tool",
        "label": "About",
        "icon_path": media.about_image,
    },
    "donate_window": {
        "type": "tool",
        "label": "Donate",
        "icon_path": media.stripe_image,
    },
    "bug_report_window": {
        "type": "tool",
        "label": "Bug Report",
        "icon_path": media.report_a_bug_image,
    },
    "smart_rotation": {
        "type": "tool",
        "label": "Smart Rotation",
        "icon_path": media.auto_tangent_image,
    },
    "smart_rotation_release": {
        "type": "tool",
        "label": "Smart Rotation Release",
        "icon_path": media.auto_tangent_image,
    },
    "smart_translation": {
        "type": "tool",
        "label": "Smart Translation",
        "icon_path": media.create_locator_image,
    },
    "smart_translation_release": {
        "type": "tool",
        "label": "Smart Translation Release",
        "icon_path": media.create_locator_image,
    },
    "depth_mover": {
        "type": "tool",
        "label": "Depth Mover",
        "icon_path": media.depth_mover_image,
    },
    "share_keys": {
        "type": "tool",
        "label": "Share Keys",
        "text": "sK",
        "icon_path": media.share_keys_image,
        "callback": keyTools.share_keys,
        "menu_setup_fn": _tool_menu_builder("build_share_keys_menu"),
        "tooltip_template": helper.share_keys_tooltip_text,
    },
    "reblock": {
        "type": "tool",
        "label": "reBlock",
        "text": "rB",
        "icon_path": media.reblock_keys_image,
        "callback": keyTools.reblock_move,
        "tooltip_template": helper.reblock_move_tooltip_text,
        "description": "Reblock the selected animation.",
    },
    "bake_animation_custom": {
        "type": "tool",
        "label": "Bake Custom Interval",
        "text": "BA",
        "icon_path": media.bake_animation_custom_image,
        "callback": bar.bake_animation_custom_window,
        "tooltip_template": helper.bake_animation_custom_tooltip_text,
    },
    "bake_animation_1": {
        "type": "tool",
        "label": "Bake on Ones",
        "text": "BA",
        "icon_path": media.bake_animation_1_image,
        "callback": keyTools.bake_animation_1,
        "tooltip_template": helper.bake_animation_1_tooltip_text,
    },
    "bake_animation_2": {
        "type": "tool",
        "label": "Bake on Twos",
        "text": "BA",
        "icon_path": media.bake_animation_2_image,
        "callback": keyTools.bake_animation_2,
        "tooltip_template": helper.bake_animation_2_tooltip_text,
    },
    "bake_animation_3": {
        "type": "tool",
        "label": "Bake on Threes",
        "text": "BA",
        "icon_path": media.bake_animation_3_image,
        "callback": keyTools.bake_animation_3,
        "tooltip_template": helper.bake_animation_3_tooltip_text,
    },
    "bake_animation_4": {
        "type": "tool",
        "label": "Bake on Fours",
        "text": "BA",
        "icon_path": media.bake_animation_3_image,
        "callback": keyTools.bake_animation_4,
        "tooltip_template": helper.bake_animation_4_tooltip_text,
    },
    "orbit": {
        "type": "check",
        "label": "Orbit",
        "text": "Orb",
        "icon_path": media.orbit_ui_image,
        "callback": lambda: ui.orbit_window(0, 0),
        "tooltip_template": helper.orbit_tooltip_text,
    },
    "attribute_switcher": {
        "type": "check",
        "label": "Attribute Switcher",
        "text": "SSw",
        "icon_path": media.attribute_switcher_image,
        "callback": lambda: ui.toggle_attribute_switcher_window(),
        "tooltip_template": helper.attribute_switcher_tooltip_text,
    },
    "gimbal": {
        "type": "tool",
        "label": "Gimbal Fixer",
        "text": "Gim",
        "icon_path": media.reblock_keys_image,
        "callback": bar.gimbal_fixer_window,
        "tooltip_template": helper.gimbal_fixer_tooltip_text,
    },
    "worldspace": {
        "type": "tool",
        "label": "World Space",
        "text": "WS",
        "icon_path": media.worldspace_copy_animation_image,
        "callback": bar.mod_worldspace_copy_animation,
        "tooltip_template": helper.copy_worldspace_tooltip_text,
    },
    "temp_pivot": {
        "type": "tool",
        "label": "Temp Pivot",
        "text": "TP",
        "icon_path": media.temp_pivot_image,
        "callback": lambda *args: bar.create_temp_pivot(False),
        "tooltip_template": helper.temp_pivot_tooltip_text,
    },
    "micro_move": {
        "type": "check",
        "label": "Micro Move",
        "text": "MM",
        "icon_path": media.ruler_image,
        "callback": trigger.make_command_callback("micro_move"),
        "tooltip_template": helper.micro_move_tooltip_text,
    },
    "isolate_down_level": {
        "type": "widget",
        "label": "Down one level",
    },
    "tracer_connected": {
        "type": "widget",
        "label": "Connected",
    },
    "link_autolink": {
        "type": "check",
        "label": "Auto-link",
        "icon_path": media.link_objects_image,
        "checkable": True,
        "pinnable": False,
    },
    "overshoot_sliders": {
        "type": "check",
        "label": "Overshoot Sliders",
        "text": "OS",
        "icon_path": media.sliders_overshoot_image,
        "callback": trigger.make_command_callback("overshoot_sliders"),
    },
    "attribute_switcher_euler_filter": {
        "type": "check",
        "label": "Auto Euler Filter",
        "text": "EF",
        "icon_path": media.euler_filter_image,
        "callback": trigger.make_command_callback("attribute_switcher_euler_filter"),
    },
    "nudge_left": {
        "type": "tool",
        "label": "Nudge Left",
        "icon_path": media.nudge_left_image,
        "callback": trigger.make_command_callback("nudge_left"),
        "tooltip_template": helper.nudge_keyleft_b_widget_tooltip_text,
        "description": "Nudge selected keys to the left.",
    },
    "nudge_right": {
        "type": "tool",
        "label": "Nudge Right",
        "icon_path": media.nudge_right_image,
        "callback": trigger.make_command_callback("nudge_right"),
        "tooltip_template": helper.nudge_keyright_b_widget_tooltip_text,
        "description": "Nudge selected keys to the right.",
    },
    "nudge_remove_inbetween": {
        "type": "tool",
        "label": "Remove Inbetween",
        "icon_path": media.remove_inbetween_image,
        "callback": trigger.make_command_callback("nudge_remove_inbetween"),
        "tooltip_template": helper.remove_inbetween_b_widget_tooltip_text,
        "description": "Remove inbetweens using the current nudge step value.",
    },
    "nudge_insert_inbetween": {
        "type": "tool",
        "label": "Insert Inbetween",
        "icon_path": media.insert_inbetween_image,
        "callback": trigger.make_command_callback("nudge_insert_inbetween"),
        "tooltip_template": helper.insert_inbetween_b_widget_tooltip_text,
        "description": "Insert inbetweens using the current nudge step value.",
    },
    "nudge_value": {
        "type": "widget",
        "label": "Nudge Value",
        "tooltip_template": helper.move_keyframes_intField_widget_tooltip_text,
        "default": True,
    },
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
        "icon_path": media.delete_animation_image,
        "tooltip_template": helper.static_tooltip_text,
        "description": "Flatten the selected curve so it holds the first selected value.",
        "callback": lambda: keyTools.deleteStaticCurves(),
    },
    "match": {
        "type": "tool",
        "label": "Match",
        "text": "M",
        "icon_path": media.match_image,
        "tooltip_template": helper.match_keys_tooltip_text,
        "description": "Match one selected curve to another.",
        "callback": lambda: keyTools.match_keys(),
    },
    "flip": {
        "type": "tool",
        "label": "Flip",
        "text": "F",
        "tooltip_template": helper.flip_tooltip_text,
        "description": "Inverts the selected curve vertically.",
        "callback": lambda: keyTools.flipCurves(),
    },
    "snap": {
        "type": "tool",
        "label": "Snap",
        "text": "Sn",
        "tooltip_template": helper.snap_tooltip_text,
        "description": "Snap selected sub-frame keys to the nearest whole frame.",
        "callback": lambda: keyTools.snapKeyframes(),
    },
    "overlap": {
        "type": "tool",
        "label": "Overlap",
        "text": "O",
        "tooltip_template": helper.overlap_tooltip_text,
        "description": "Offset selected curves to create overlap.",
        "callback": keyTools.mod_overlap_animation,
    },
    "isolate_master": {
        "type": "tool",
        "label": "Isolate",
        "icon_path": media.isolate_image,
        "callback": bar.isolate_master,
        "tooltip_template": helper.isolate_tooltip_text,
    },
    "align_selected_objects": {
        "type": "tool",
        "label": "Align",
        "icon_path": media.match_image,
        "callback": bar.align_selected_objects,
        "tooltip_template": helper.align_tooltip_text,
    },
    "create_tracer": {
        "type": "tool",
        "label": "Tracer",
        "icon_path": media.tracer_image,
        "callback": bar.create_tracer,
        "tooltip_template": helper.tracer_tooltip_text,
    },
    "reset_objects_mods": {
        "type": "tool",
        "label": "Reset Values",
        "icon_path": media.asset_path("reset_animation_image"),
        "callback": keyTools.reset_objects_mods,
        "tooltip_template": helper.reset_values_tooltip_text,
    },
    "delete_all_animation": {
        "type": "tool",
        "label": "Delete All Animation",
        "icon_path": media.delete_animation_image,
        "callback": bar.mod_delete_animation,
        "tooltip_template": helper.delete_animation_tooltip_text,
    },
    "select_rig_controls": {
        "type": "tool",
        "label": "Select Rig Controls",
        "icon_path": media.select_rig_controls_image,
        "callback": bar.select_rig_controls,
        "tooltip_template": helper.select_rig_controls_tooltip_text,
        "description": "Select all rig controls. Ctrl+Click selects only animated rig controls.",
        "status_title": "Select Rig Controls",
        "status_description": "Select all rig controls. Ctrl+Click selects only animated rig controls.",
    },
    "select_rig_controls_animated": {
        "type": "tool",
        "label": "Select Animated Rig Controls",
        "icon_path": media.select_rig_controls_animated_image,
        "tooltip_template": helper.select_rig_controls_animated_tooltip_text,
        "description": "Select only animated rig controls.",
        "status_title": "Select Animated Rig Controls",
        "status_description": "Select only animated rig controls.",
        "callback": bar.select_rig_controls_animated,
    },
    "select_opposite": {
        "type": "tool",
        "label": "Select Opposite",
        "icon_path": media.opposite_select_image,
        "callback": keyTools.selectOpposite,
        "tooltip_template": helper.opposite_select_tooltip_text,
    },
    "selection_sets": {
        "type": "check",
        "label": "Selection Sets",
        "text": "SS",
        "icon_path": media.selection_sets_image,
        "callback": trigger.make_command_callback("selection_sets"),
        "tooltip_template": helper.selection_sets_tooltip_text,
    },
    "selection_sets_quick_export": {
        "type": "tool",
        "label": "Quick Export",
        "text": "QEx",
        "icon_path": media.selection_sets_export_image,
        "tooltip_template": helper.quick_export_selection_sets_tooltip_text,
        "description": "Export selection sets to the shared quick file, overwriting it.",
        "callback": selectionSetsApi.quick_export_selection_sets,
    },
    "selection_sets_quick_import": {
        "type": "tool",
        "label": "Quick Import",
        "text": "QIm",
        "icon_path": media.selection_sets_import_image,
        "tooltip_template": helper.quick_import_selection_sets_tooltip_text,
        "description": "Import selection sets from the shared quick file.",
        "callback": selectionSetsApi.quick_import_selection_sets,
    },
    "selection_sets_export": {
        "type": "tool",
        "label": "Export",
        "text": "Ex",
        "icon_path": media.selection_sets_export_image,
        "tooltip_template": helper.export_selection_sets_tooltip_text,
        "description": "Export selection sets to a chosen file.",
        "callback": selectionSetsApi.export_selection_sets,
    },
    "selection_sets_import": {
        "type": "tool",
        "label": "Import",
        "text": "Im",
        "icon_path": media.selection_sets_import_image,
        "tooltip_template": helper.import_selection_sets_tooltip_text,
        "description": "Import selection sets from a chosen file.",
        "callback": selectionSetsApi.import_selection_sets,
    },
    "selection_sets_clear_all": {
        "type": "tool",
        "label": "Clear All Select Sets",
        "text": "Clr",
        "icon_path": media.trash_image,
        "tooltip_template": helper.clear_selection_sets_tooltip_text,
        "description": "Delete every selection set in the current scene.",
        "callback": selectionSetsApi.clear_all_selection_sets,
    },
    "custom_graph": {
        "type": "check",
        "label": "Graph Editor Toolbar",
        "text": "GE",
        "icon_path": media.customGraph_image,
        "callback": trigger.make_command_callback("custom_graph"),
        "tooltip_template": helper.customGraph_tooltip_text,
    },
    "extra_graph_tools": {
        "type": "menu",
        "label": "Extra Tools",
        "text": "E",
        "menu_setup_fn": _tool_menu_builder("build_extra_graph_tools_menu"),
        "tooltip_template": helper.extra_tools_tooltip_text,
        "description": "Open extra graph tools.",
    },
    "select_hierarchy": {
        "type": "tool",
        "label": "Select Hierarchy",
        "icon_path": media.select_hierarchy_image,
        "callback": bar.selectHierarchy,
        "tooltip_template": helper.select_hierarchy_tooltip_text,
    },
    "selector": {
        "type": "tool",
        "label": "Selector",
        "icon_path": media.selector_image,
        "callback": bar.selector_window,
        "tooltip_template": helper.selector_tooltip_text,
        "default": True,
    },
    "create_locator": {
        "type": "tool",
        "label": "Create Locator",
        "icon_path": media.create_locator_image,
        "callback": bar.createLocator,
        "tooltip_template": helper.createLocator_tooltip_text,
    },
    "locator_select_temp": {
        "type": "tool",
        "label": "Select Temp Locators",
        "icon_path": media.create_locator_image,
        "callback": bar.selectTempLocators,
    },
    "locator_remove_temp": {
        "type": "tool",
        "label": "Remove Temp Locators",
        "icon_path": media.create_locator_image,
        "callback": bar.deleteTempLocators,
    },
    "isolate_bookmarks": {
        "type": "tool",
        "label": "Bookmarks",
        "icon_path": media.ibookmarks_menu_image,
        "callback": iBookmarksApi.create_ibookmarks_window,
    },
    "isolate_help": {
        "type": "tool",
        "label": "Help",
        "icon_path": media.help_menu_image,
        "callback": lambda: general.open_url("https://thekeymachine.gitbook.io/base/the-toolbar/animation-tools/isolate"),
        "pinnable": False,
    },
    "align_help": {
        "type": "tool",
        "label": "Help",
        "icon_path": media.help_menu_image,
        "callback": lambda: general.open_url("https://thekeymachine.gitbook.io/base/the-toolbar/animation-tools/match-align"),
        "pinnable": False,
    },
    "copy_pose": {
        "type": "tool",
        "label": "Copy Pose",
        "icon_path": media.copy_pose_image,
        "callback": keyTools.copy_pose,
        "tooltip_template": helper.copy_pose_tooltip_text,
    },
    "paste_pose": {
        "type": "tool",
        "label": "Paste Pose",
        "icon_path": media.paste_pose_image,
        "callback": keyTools.paste_pose,
        "tooltip_template": helper.paste_pose_tooltip_text,
    },
    "copy_animation": {
        "type": "tool",
        "label": "Copy Animation",
        "icon_path": media.copy_animation_image,
        "callback": keyTools.copy_animation,
        "tooltip_template": helper.copy_animation_tooltip_text,
        "status_title": "Copy Animation",
        "status_description": "Copy animation from the current selection.",
    },
    "paste_animation": {
        "type": "tool",
        "label": "Paste Animation",
        "icon_path": media.paste_animation_image,
        "callback": keyTools.paste_animation,
        "tooltip_template": helper.paste_animation_tooltip_text,
    },
    "paste_insert_animation": {
        "type": "tool",
        "label": "Paste Insert Animation",
        "icon_path": media.paste_insert_animation_image,
        "callback": keyTools.paste_insert_animation,
        "tooltip_template": helper.paste_insert_animation_tooltip_text,
    },
    "follow_cam": {
        "type": "tool",
        "label": "Follow Cam",
        "icon_path": media.follow_cam_image,
        "callback": lambda *args: bar.create_follow_cam(translation=True, rotation=True),
        "tooltip_template": helper.follow_cam_tooltip_text,
    },
    "animation_offset": {
        "type": "check",
        "label": "Anim Offset",
        "icon_path": media.animation_offset_image,
        "callback": trigger.make_command_callback("animation_offset"),
        "tooltip_template": helper.animation_offset_tooltip_text,
    },
    "ws_copy_frame": {
        "type": "tool",
        "label": "Copy World Space",
        "icon_path": media.worldspace_copy_frame_image,
        "callback": bar.copy_worldspace_single_frame,
        "tooltip_template": helper.copy_worldspace_tooltip_text,
    },
    "align_translation": {
        "type": "tool",
        "label": "Translation",
        "icon_path": media.align_menu_image,
        "callback": partial(bar.align_selected_objects, pos=True, rot=False, scl=False),
    },
    "align_rotation": {
        "type": "tool",
        "label": "Rotation",
        "icon_path": media.align_menu_image,
        "callback": partial(bar.align_selected_objects, pos=False, rot=True, scl=False),
    },
    "align_scale": {
        "type": "tool",
        "label": "Scale",
        "icon_path": media.align_menu_image,
        "callback": partial(bar.align_selected_objects, pos=False, rot=False, scl=True),
    },
    "align_range": {
        "type": "tool",
        "label": "Match Range",
        "icon_path": media.match_image,
        "callback": bar.align_range,
    },
    "tracer_refresh": {
        "type": "tool",
        "label": "Refresh Tracer",
        "icon_path": media.refresh_image,
        "callback": bar.tracer_refresh,
    },
    "tracer_show_hide": {
        "type": "tool",
        "label": "Toggle Tracer",
        "icon_path": media.tracer_show_hide_image,
        "callback": bar.tracer_show_hide,
    },
    "tracer_offset_node": {
        "type": "tool",
        "label": "Select Offset Object",
        "icon_path": media.tracer_select_offset_image,
        "callback": bar.select_tracer_offset_node,
    },
    "tracer_grey": {
        "type": "tool",
        "label": "Tracer Style: Grey",
        "icon_path": media.tracer_grey_image,
        "callback": bar.set_tracer_grey_color,
    },
    "tracer_red": {
        "type": "tool",
        "label": "Tracer Style: Red",
        "icon_path": media.tracer_red_image,
        "callback": bar.set_tracer_red_color,
    },
    "tracer_blue": {
        "type": "tool",
        "label": "Tracer Style: Blue",
        "icon_path": media.tracer_blue_image,
        "callback": bar.set_tracer_blue_color,
    },
    "tracer_remove": {
        "type": "tool",
        "label": "Remove Tracer",
        "icon_path": media.remove_image,
        "callback": bar.remove_tracer_node,
    },
    "reset_set_defaults": {
        "type": "tool",
        "label": "Set Default Values For Selected",
        "icon_path": media.asset_path("reset_animation_image"),
        "callback": keyTools.save_default_values,
    },
    "reset_restore_defaults": {
        "type": "tool",
        "label": "Restore Default Values For Selected",
        "icon_path": media.asset_path("reset_animation_image"),
        "callback": keyTools.remove_default_values_for_selected_object,
    },
    "reset_clear_all": {
        "type": "tool",
        "label": "Clear All Saved Data",
        "icon_path": media.asset_path("reset_animation_image"),
        "callback": keyTools.restore_default_data,
    },
    "reset_help": {
        "type": "tool",
        "label": "Help",
        "icon_path": media.help_menu_image,
        "callback": lambda: general.open_url("https://thekeymachine.gitbook.io/base/the-toolbar/animation-tools/reset-to-default"),
        "pinnable": False,
    },
    "mirror": {
        "type": "tool",
        "label": "Mirror",
        "icon_path": media.mirror_image,
        "callback": keyTools.mirror,
        "tooltip_template": helper.mirror_tooltip_text,
    },
    "mirror_add_invert": {
        "type": "tool",
        "label": "Add Exception Invert",
        "icon_path": media.mirror_image,
        "callback": keyTools.add_mirror_invert_exception,
    },
    "mirror_add_keep": {
        "type": "tool",
        "label": "Add Exception Keep",
        "icon_path": media.mirror_image,
        "callback": keyTools.add_mirror_keep_exception,
    },
    "mirror_remove_exc": {
        "type": "tool",
        "label": "Remove Exception",
        "icon_path": media.mirror_image,
        "callback": keyTools.remove_mirror_invert_exception,
    },
    "mirror_help": {
        "type": "tool",
        "label": "Help",
        "icon_path": media.help_menu_image,
        "callback": lambda: general.open_url("https://thekeymachine.gitbook.io/base/the-toolbar/animation-tools/mirror"),
        "pinnable": False,
    },
    "opposite_add": {
        "type": "tool",
        "label": "Add Opposite",
        "icon_path": media.opposite_add_image,
        "callback": keyTools.addSelectOpposite,
        "tooltip_template": helper.opposite_add_tooltip_text,
    },
    "opposite_copy": {
        "type": "tool",
        "label": "Copy Opposite",
        "icon_path": media.opposite_copy_image,
        "callback": keyTools.copyOpposite,
        "tooltip_template": helper.opposite_copy_tooltip_text,
    },
    "pose_help": {
        "type": "tool",
        "label": "Help",
        "icon_path": media.help_menu_image,
        "callback": lambda: general.open_url(
            "https://thekeymachine.gitbook.io/base/the-toolbar/animation-tools/copy-paste-animation#pose-tools"
        ),
        "pinnable": False,
    },
    "paste_opposite_animation": {
        "type": "tool",
        "label": "Paste Opposite",
        "icon_path": media.paste_opposite_animation_image,
        "callback": keyTools.paste_opposite_animation,
    },
    "paste_animation_to": {
        "type": "tool",
        "label": "Paste To",
        "icon_path": media.paste_animation_image,
        "callback": keyTools.paste_animation_to,
    },
    "copy_animation_help": {
        "type": "tool",
        "label": "Help",
        "icon_path": media.help_menu_image,
        "callback": lambda: general.open_url("https://thekeymachine.gitbook.io/base/the-toolbar/animation-tools/copy-paste-animation"),
        "pinnable": False,
    },
    "temp_pivot_last": {
        "type": "tool",
        "label": "Use Last Pivot",
        "icon_path": media.temp_pivot_use_last_image,
        "callback": lambda: bar.create_temp_pivot(True),
    },
    "temp_pivot_help": {
        "type": "tool",
        "label": "Help",
        "icon_path": media.help_menu_image,
        "callback": lambda: general.open_url("https://thekeymachine.gitbook.io/base/the-toolbar/animation-tools/temp-pivots"),
        "pinnable": False,
    },
    "fcam_trans_only": {
        "type": "tool",
        "label": "Follow only Translation",
        "icon_path": media.follow_cam_image,
        "callback": lambda: bar.create_follow_cam(translation=True, rotation=False),
    },
    "fcam_rot_only": {
        "type": "tool",
        "label": "Follow only Rotation",
        "icon_path": media.follow_cam_image,
        "callback": lambda: bar.create_follow_cam(translation=False, rotation=True),
    },
    "fcam_remove": {
        "type": "tool",
        "label": "Remove Follow Cam",
        "icon_path": media.remove_image,
        "callback": bar.remove_followCam,
    },
    "link_copy": {
        "type": "tool",
        "label": "Copy Link Position",
        "icon_path": media.link_objects_copy_image,
        "callback": keyTools.copy_link,
        "tooltip_template": helper.copy_link_tooltip_text,
    },
    "link_paste": {
        "type": "tool",
        "label": "Paste Link Position",
        "icon_path": media.link_objects_paste_image,
        "callback": keyTools.paste_link,
        "tooltip_template": helper.paste_link_tooltip_text,
    },
    "link_help": {
        "type": "tool",
        "label": "Help",
        "icon_path": media.help_menu_image,
        "callback": lambda: general.open_url("https://thekeymachine.gitbook.io/base/the-toolbar/animation-tools/link-objects"),
        "pinnable": False,
    },
    "ws_copy_range": {
        "type": "tool",
        "label": "Copy World Space - Selected Range",
        "icon_path": media.worldspace_copy_animation_image,
        "callback": bar.copy_range_worldspace_animation,
        "tooltip_template": helper.copy_worldspace_range_tooltip_text,
    },
    "ws_paste_frame": {
        "type": "tool",
        "label": "Paste World Space",
        "icon_path": media.worldspace_paste_frame_image,
        "callback": bar.paste_worldspace_single_frame,
        "tooltip_template": helper.paste_worldspace_tooltip_text,
    },
    "ws_paste": {
        "type": "tool",
        "label": "Paste World Space - All Animation",
        "icon_path": media.worldspace_paste_animation_image,
        "callback": bar.color_worldspace_paste_animation,
        "tooltip_template": helper.paste_worldspace_animation_tooltip_text,
    },
    "worldspace_help": {
        "type": "tool",
        "label": "Help",
        "description": "World Space tools.",
        "icon_path": media.help_menu_image,
        "callback": lambda: general.open_url(
            "https://thekeymachine.gitbook.io/base/the-toolbar/animation-tools/copy-paste-animation#worldspace-tools"
        ),
        "pinnable": False,
    },
    "custom_tools": {
        "type": "menu",
        "label": "Custom Tools",
        "icon_path": media.custom_tools_image,
        "callback": trigger.make_command_callback("custom_tools"),
        "menu_setup_fn": _tool_menu_builder("build_custom_tools_menu"),
        "tooltip_template": helper.custom_tools_tooltip_text,
    },
    "custom_scripts": {
        "type": "menu",
        "label": "Custom Scripts",
        "icon_path": media.custom_scripts_image,
        "callback": trigger.make_command_callback("custom_scripts"),
        "menu_setup_fn": _tool_menu_builder("build_custom_scripts_menu"),
        "tooltip_template": helper.custom_scripts_tooltip_text,
    },
    "settings": {
        "type": "menu",
        "label": "Settings",
        "icon_path": media.settings_image,
        "description": "Access global preferences, check for updates, and view credits.",
    },
    "graph_isolate_curves": {
        "type": "tool",
        "label": "Isolate",
        "icon_path": media.isolate_image,
        "callback": keyTools.isolateCurve,
        "tooltip_template": helper.graph_isolate_curves_tooltip_text,
        "description": "Isolate selected curves.",
    },
    "graph_toggle_mute": {
        "type": "tool",
        "label": "Mute",
        "text": "Mt",
        "callback": keyTools.toggleMute,
        "tooltip_template": helper.graph_mute_tooltip_text,
        "description": "Toggle mute on selected curves.",
    },
    "graph_toggle_lock": {
        "type": "tool",
        "label": "Lock",
        "text": "Lk",
        "callback": keyTools.toggleLock,
        "tooltip_template": helper.graph_lock_tooltip_text,
        "description": "Toggle lock on selected curves.",
    },
    "graph_filter": {
        "type": "tool",
        "label": "Filter",
        "text": "Fi",
        "callback": ui.customGraph_filter_mods,
        "tooltip_template": helper.graph_filter_tooltip_text,
        "description": "Filter selection in the GraphEditor. Shift+Click to deactivate.",
    },
    "reset_translations": {
        "type": "tool",
        "label": "Reset Translations",
        "text": "RT",
        "icon_path": media.asset_path("reset_animation_image"),
        "callback": lambda: keyTools.reset_object_values(reset_translations=True),
        "tooltip_template": helper.reset_translations_tooltip_text,
        "description": "Reset only translation values for the selected objects or graph targets.",
    },
    "reset_rotations": {
        "type": "tool",
        "label": "Reset Rotations",
        "text": "RR",
        "icon_path": media.asset_path("reset_animation_image"),
        "callback": lambda: keyTools.reset_object_values(reset_rotations=True),
        "tooltip_template": helper.reset_rotations_tooltip_text,
        "description": "Reset only rotation values for the selected objects or graph targets.",
    },
    "reset_scales": {
        "type": "tool",
        "label": "Reset Scales",
        "text": "RS",
        "icon_path": media.asset_path("reset_animation_image"),
        "callback": lambda: keyTools.reset_object_values(reset_scales=True),
        "tooltip_template": helper.reset_scales_tooltip_text,
        "description": "Reset only scale values for the selected objects or graph targets.",
    },
    "reset_trs": {
        "type": "tool",
        "label": "Reset Translation Rotation Scale",
        "text": "RTRS",
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
        "label": "Cycle Matcher",
        "text": "CM",
        "icon_path": media.asset_path("match_curve_cycle_image"),
        "callback": keyTools.match_curve_cycle,
        "menu_setup_fn": _tool_menu_builder("build_cycle_matcher_menu", icon_path=media.asset_path("match_curve_cycle_image")),
        "tooltip_template": helper.tangent_cycle_matcher_tooltip_text,
        "description": "Curve cycle matcher.",
    },
    "tangent_bouncy": {
        "type": "tool",
        "label": "Bouncy Tangent",
        "text": "BO",
        "icon_path": media.bouncy_tangent_image,
        "callback": keyTools.bouncy_tangets,
        "menu_setup_fn": _tool_menu_builder(
            "build_tangent_menu", tangent_type="bouncy", tangent_label="Bouncy Tangent", icon_path=media.bouncy_tangent_image
        ),
        "tooltip_template": helper.tangent_bouncy_tooltip_text,
        "description": "Set bouncy tangents.",
    },
    "tangent_auto": {
        "type": "tool",
        "label": "Auto Tangent",
        "text": "AU",
        "icon_path": media.auto_tangent_image,
        "callback": lambda: bar.setTangent("auto"),
        "menu_setup_fn": _tool_menu_builder(
            "build_tangent_menu",
            tangent_type="auto",
            tangent_label="Auto Tangent",
            icon_path=media.auto_tangent_image,
            maya_default_tangent=True,
        ),
        "tooltip_template": helper.auto_tangent_tooltip_text,
        "description": "Set selected keys to Auto tangents.",
    },
    "tangent_spline": {
        "type": "tool",
        "label": "Spline Tangent",
        "text": "SP",
        "icon_path": media.spline_tangent_image,
        "callback": lambda: bar.setTangent("spline"),
        "menu_setup_fn": _tool_menu_builder(
            "build_tangent_menu",
            tangent_type="spline",
            tangent_label="Spline Tangent",
            icon_path=media.spline_tangent_image,
            maya_default_tangent=True,
        ),
        "tooltip_template": helper.spline_tangent_tooltip_text,
        "description": "Set selected keys to Spline tangents.",
    },
    "tangent_clamped": {
        "type": "tool",
        "label": "Clamped Tangent",
        "text": "CL",
        "icon_path": media.clamped_tangent_image,
        "callback": lambda: bar.setTangent("clamped"),
        "menu_setup_fn": _tool_menu_builder(
            "build_tangent_menu",
            tangent_type="clamped",
            tangent_label="Clamped Tangent",
            icon_path=media.clamped_tangent_image,
            maya_default_tangent=True,
        ),
        "tooltip_template": helper.clamped_tangent_tooltip_text,
        "description": "Set selected keys to Clamped tangents.",
    },
    "tangent_linear": {
        "type": "tool",
        "label": "Linear Tangent",
        "text": "LI",
        "icon_path": media.linear_tangent_image,
        "callback": lambda: bar.setTangent("linear"),
        "menu_setup_fn": _tool_menu_builder(
            "build_tangent_menu",
            tangent_type="linear",
            tangent_label="Linear Tangent",
            icon_path=media.linear_tangent_image,
            maya_default_tangent=True,
        ),
        "tooltip_template": helper.linear_tangent_tooltip_text,
        "description": "Set selected keys to Linear tangents.",
    },
    "tangent_flat": {
        "type": "tool",
        "label": "Flat Tangent",
        "text": "FT",
        "icon_path": media.flat_tangent_image,
        "callback": lambda: bar.setTangent("flat"),
        "menu_setup_fn": _tool_menu_builder(
            "build_tangent_menu",
            tangent_type="flat",
            tangent_label="Flat Tangent",
            icon_path=media.flat_tangent_image,
            maya_default_tangent=True,
        ),
        "tooltip_template": helper.flat_tangent_tooltip_text,
        "description": "Set selected keys to Flat tangents.",
    },
    "tangent_step": {
        "type": "tool",
        "label": "Step Tangent",
        "text": "ST",
        "icon_path": media.step_tangent_image,
        "callback": lambda: bar.setTangent("step"),
        "menu_setup_fn": _tool_menu_builder(
            "build_tangent_menu",
            tangent_type="step",
            tangent_label="Step Tangent",
            icon_path=media.step_tangent_image,
            maya_default_tangent=True,
        ),
        "tooltip_template": helper.step_tangent_tooltip_text,
        "description": "Set selected keys to Stepped tangents.",
    },
    "tangent_plateau": {
        "type": "tool",
        "label": "Plateau Tangent",
        "text": "PT",
        "icon_path": media.plateau_tangent_image,
        "callback": lambda: bar.setTangent("plateau"),
        "menu_setup_fn": _tool_menu_builder(
            "build_tangent_menu",
            tangent_type="plateau",
            tangent_label="Plateau Tangent",
            icon_path=media.plateau_tangent_image,
            maya_default_tangent=True,
        ),
        "tooltip_template": helper.plateau_tangent_tooltip_text,
        "description": "Set selected keys to Plateau tangents.",
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
    "match_tools": {
        "label": "Match",
        "hotkey_only": True,
        "items": [
            {"id": "match"},
            {"id": "align_selected_objects"},
            {"id": "align_translation"},
            {"id": "align_rotation"},
            {"id": "align_scale"},
            {"id": "align_range"},
        ],
    },
    "selection_sets_tools": {
        "label": "Selection Sets",
        "hotkey_only": True,
        "items": [
            {"id": "selection_sets"},
            {"id": "selection_sets_quick_export"},
            {"id": "selection_sets_quick_import"},
            {"id": "selection_sets_export"},
            {"id": "selection_sets_import"},
            {"id": "selection_sets_clear_all"},
        ],
    },
    # --- Key Editing ---
    "nudge_tools": {
        "label": "Nudge",
        "color": toolColors.green,
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
            {"type": "widget", "key": "nudge_value", "default": True},
        ],
    },
    "key_sync_tools": {
        "label": "Key Sync",
        "color": toolColors.green,
        "items": [
            {
                "id": "share_keys",
                "default": True,
                "shortcuts": [{"id": "reblock", "keys": [QtCore.Qt.Key_Shift]}],
            },
            {"id": "reblock"},
        ],
    },
    "bake_tools": {
        "label": "Bake",
        "color": toolColors.green,
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
        ],
    },
    "main_key_editing": {
        "label": "Key Editing",
        "color": toolColors.green,
        "items": [
            {"group": "nudge_tools"},
            "separator",
            {"group": "key_sync_tools"},
            {"id": "clear_selected_keys"},
            {"id": "select_scene_animation"},
            "separator",
            {"group": "bake_tools"},
        ],
    },
    # --- Sliders ---
    "slider_blend": {
        "label": "Blend Sliders",
        "color": toolColors.UI_COLORS.green.hex,
        "type": "slider",
        "slider_type": "blend",
        "modes_attr": "BLEND_MODES",
        "default_modes": ["connect_neighbors"],
    },
    "slider_tween": {
        "label": "Tween Sliders",
        "color": toolColors.UI_COLORS.yellow.hex,
        "type": "slider",
        "slider_type": "tween",
        "modes_attr": "TWEEN_MODES",
        "default_modes": ["tweener"],
    },
    "slider_tangent": {
        "label": "Tangent Sliders",
        "color": toolColors.UI_COLORS.orange.hex,
        "type": "slider",
        "slider_type": "tangent",
        "modes_attr": "TANGENT_MODES",
        "default_modes": ["blend_best_guess"],
    },
    # --- Scene Tools ---
    "pointer_tools": {
        "label": "Pointer",
        "color": toolColors.red,
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
        "label": "Isolate",
        "color": toolColors.red,
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
            {"type": "widget", "key": "isolate_down_level"},
            "separator",
            {"id": "isolate_help"},
        ],
    },
    "locator_tools": {
        "label": "Locators",
        "color": toolColors.red,
        "items": [
            {"id": "create_locator", "default": True},
            {"id": "locator_select_temp"},
            {"id": "locator_remove_temp"},
        ],
    },
    "align_tools": {
        "label": "Align",
        "color": toolColors.red,
        "items": [
            {
                "id": "align_selected_objects",
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
        "items": [
            {
                "id": "create_tracer",
                "default": True,
                "shortcuts": [
                    {"id": "tracer_refresh", "keys": [QtCore.Qt.Key_Shift]},
                    {"id": "tracer_show_hide", "keys": [QtCore.Qt.Key_Control]},
                    {"id": "tracer_remove", "keys": [QtCore.Qt.Key_Control, QtCore.Qt.Key_Alt]},
                ],
            },
            {"type": "widget", "key": "tracer_connected"},
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
        "items": [
            {
                "id": "reset_objects_mods",
                "default": True,
                "shortcuts": [
                    {"id": "reset_translations", "keys": [QtCore.Qt.Key_Shift]},
                    {"id": "reset_rotations", "keys": [QtCore.Qt.Key_Control]},
                    {"id": "reset_scales", "keys": [QtCore.Qt.Key_Alt]},
                    {"id": "reset_trs", "keys": [QtCore.Qt.Key_Control, QtCore.Qt.Key_Shift]},
                ],
            },
            {"id": "reset_translations"},
            {"id": "reset_rotations"},
            {"id": "reset_scales"},
            {"id": "reset_trs"},
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
        "items": [
            {
                "id": "delete_all_animation",
                "default": True,
                "shortcuts": [{"id": "delete_static_animation", "keys": [QtCore.Qt.Key_Shift]}],
            },
            {"id": "delete_static_animation"},
        ],
    },
    "main_scene_tools": {
        "label": "Scene Tools",
        "color": toolColors.red,
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
    # --- Selection & Pose ---
    "opposite_tools": {
        "label": "Opposite",
        "color": toolColors.green,
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
        "color": toolColors.green,
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
    "selection_tools": {
        "label": "Selection",
        "color": toolColors.green,
        "items": [
            {"id": "selector"},
            {"group": "opposite_tools"},
            {"group": "mirror_tools"},
            {"id": "select_hierarchy"},
        ],
    },
    "pose_tools": {
        "label": "Pose",
        "color": toolColors.green,
        "items": [
            {
                "id": "copy_pose",
                "default": True,
                "shortcuts": [{"id": "paste_pose", "keys": [QtCore.Qt.Key_Control]}],
            },
            {"id": "paste_pose"},
            "separator",
            {"id": "pose_help"},
        ],
    },
    "copy_animation_tools": {
        "label": "Copy Animation",
        "color": toolColors.green,
        "items": [
            {
                "id": "copy_animation",
                "default": True,
                "shortcuts": [
                    {"id": "paste_animation", "keys": [QtCore.Qt.Key_Control]},
                    {"id": "paste_insert_animation", "keys": [QtCore.Qt.Key_Shift]},
                    {"id": "paste_opposite_animation", "keys": [QtCore.Qt.Key_Control, QtCore.Qt.Key_Shift]},
                ],
            },
            {"id": "paste_animation"},
            {"id": "paste_insert_animation"},
            {"id": "paste_opposite_animation"},
            {"id": "paste_animation_to"},
            "separator",
            {"id": "copy_animation_help"},
        ],
    },
    "pose_animation_section": {
        "label": "Pose & Animation",
        "color": toolColors.green,
        "items": [
            {"group": "pose_tools"},
            {"group": "copy_animation_tools"},
        ],
    },
    # --- Tangents ---
    "tangent_buttons": {
        "label": "Tangents",
        "color": toolColors.orange,
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
    "temp_pivot_tools": {
        "label": "Temp Pivot",
        "color": toolColors.purple,
        "items": [
            {
                "id": "temp_pivot",
                "default": True,
                "shortcuts": [{"id": "temp_pivot_last", "keys": [QtCore.Qt.Key_Shift]}],
            },
            {"id": "temp_pivot_last"},
            "separator",
            {"id": "temp_pivot_help"},
        ],
    },
    "follow_cam_tools": {
        "label": "Follow Cam",
        "color": toolColors.purple,
        "items": [
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
    "special_tools_section": {
        "label": "Special Tools",
        "color": toolColors.purple,
        "items": [
            {"id": "animation_offset"},
            "separator",
            {"id": "micro_move"},
            "separator",
            {"group": "temp_pivot_tools"},
            {"group": "follow_cam_tools"},
        ],
    },
    # --- Links & Worldspace ---
    "link_tools": {
        "label": "Links",
        "color": toolColors.green,
        "items": [
            {
                "id": "link_copy",
                "default": True,
                "shortcuts": [
                    {"id": "link_paste", "keys": [QtCore.Qt.Key_Control]},
                    {"id": "link_autolink", "keys": [QtCore.Qt.Key_Alt]},
                ],
            },
            {"id": "link_paste"},
            "separator",
            {"id": "link_autolink"},
            "separator",
            {"id": "link_help"},
        ],
    },
    "worldspace_tools": {
        "label": "World Space",
        "color": toolColors.green,
        "items": [
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
            "separator",
            {"id": "worldspace_help"},
        ],
    },
    "link_worldspace_section": {
        "label": "Links & World Space",
        "color": toolColors.green,
        "items": [
            {"group": "link_tools"},
            {"group": "worldspace_tools"},
            {"id": "attribute_switcher", "default": True},
            "separator",
            {"id": "gimbal"},
        ],
    },
    # --- Workspaces & Extensions ---
    "workspace_tools": {
        "label": "Workspaces",
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
    "extension_tools": {
        "label": "Extensions",
        "items": [
            {"type": "widget", "key": "overshoot_sliders", "default": True},
            {"type": "widget", "key": "attribute_switcher_euler_filter"},
            {"id": "custom_graph"},
            "separator",
            {"id": "custom_tools"},
            {"id": "custom_scripts"},
        ],
    },
    "system": {
        "label": "System",
        "hiddeable": False,
        "items": [{"id": "settings"}],
    },
    # --- Graph Editor Specific ---
    "graph_key_tools": {
        "label": "Graph Key Tools",
        "items": [
            {
                "id": "delete_all_animation",
                "default": True,
                "shortcuts": [{"id": "delete_static_animation", "keys": [QtCore.Qt.Key_Shift]}],
            },
            {
                "id": "share_keys",
                "text": "sK",
                "default": True,
                "shortcuts": [{"id": "reblock", "keys": [QtCore.Qt.Key_Shift]}],
            },
            {"id": "flip", "text": "F", "default": True},
            {"id": "snap", "text": "Sn", "default": True},
            {"id": "overlap", "text": "O", "default": True},
            {"id": "extra_graph_tools", "default": True},
        ],
    },
    "graph_curve_tools": {
        "label": "Graph Curve Tools",
        "items": [
            {"id": "graph_isolate_curves", "default": True},
            {"id": "graph_toggle_mute", "default": True},
            {"id": "graph_toggle_lock", "default": True},
            {"id": "graph_filter", "default": True},
        ],
    },
}

TOOLBAR_SECTION_LAYOUTS = {
    "main": [
        "main_key_editing",
        "slider_blend",
        "slider_tween",
        "main_scene_tools",
        "selection_tools",
        "pose_animation_section",
        "tangent_buttons",
        "special_tools_section",
        "link_worldspace_section",
        "workspace_tools",
        "extension_tools",
        "system",
    ],
    "graph": [
        "graph_key_tools",
        "align_tools",
        "slider_tween",
        "slider_blend",
        "slider_tangent",
        "graph_curve_tools",
        "reset_tools",
        "tangent_buttons",
        "system",
    ],
}


def _resolve_tool_definition(tool_key, tool_state):
    """
    Finalizes a tool definition before use.
    Ensures canonical ids exist and callbacks are bound.
    """
    res = dict(tool_state)
    res.setdefault("id", tool_key)
    res.setdefault("key", tool_key)
    res.setdefault("default", False)

    callback = res.get("callback")
    if callback:
        if getattr(callback, "__name__", None) != tool_key:
            res["callback"] = trigger.make_command_callback(tool_key, callback)
        elif not getattr(callback, "_tkm_trigger_proxy", False):
            trigger.register_command(tool_key, callback)
    return res


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
        "label": tool_state.get("label") or tool_state.get("status_title") or tool_state.get("id"),
        "keys": keys,
    }


def _resolve_shortcut_item(item):
    keys = item.get("keys", [])

    if item.get("id"):
        variant = get_tool(item["id"], **_item_options(item, exclude_keys=True))
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

    if item.get("type") == "widget":
        tool_id = item.get("id") or item.get("key")
        if tool_id and tool_id in TOOL_DEFINITIONS:
            return get_tool(tool_id, **_item_options(item))
        return dict(item)

    return None


def get_tool(tool_id, **overrides):
    """Retrieve a tool definition with optional overrides."""
    if tool_id not in TOOL_DEFINITIONS:
        raise KeyError("Unknown tool id: {}".format(tool_id))

    # Merge base definition with overrides
    tool = dict(TOOL_DEFINITIONS[tool_id])
    tool.update(overrides)
    return _resolve_tool_definition(tool_id, tool)


def _resolve_section_item(item):
    if isinstance(item, str):
        return item

    if item.get("section"):
        section = get_tool_section(item["section"])
        if section:
            return {"type": "group", "items": section.get("items", []), "label": section.get("label")}
        return []

    if item.get("group"):
        group = get_tool_section(item["group"])
        if group:
            return {"type": "group", "items": group.get("items", []), "label": group.get("label")}
        return []

    return _resolve_section_item_data(item)


def get_tool_section(section_id, resolve_items=True):
    section_def = TOOL_SECTION_DEFINITIONS.get(section_id)
    if not section_def:
        return None

    section = dict(section_def)
    section["id"] = section_id
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


def _tool_color_to_hex(color):
    if color is None:
        return None
    if hasattr(color, "base") and hasattr(color.base, "hex"):
        return color.base.hex
    if hasattr(color, "hex"):
        return color.hex
    return color


def _section_item_tint_color(item, tool_key, inherited_color=None):
    if item == "separator" or item is None:
        return None

    if isinstance(item, str):
        return inherited_color if item == tool_key else None

    if not isinstance(item, dict):
        return None

    if item.get("section") or item.get("group"):
        section = TOOL_SECTION_DEFINITIONS.get(item.get("section") or item.get("group"))
        if not section:
            return None
        section_color = section.get("color", inherited_color)
        if section_color is None:
            section_color = inherited_color
        for child in section.get("items", []):
            color = _section_item_tint_color(child, tool_key, inherited_color=section_color)
            if color is not None:
                return color
        return None

    tool_id = item.get("id") or item.get("key")
    if tool_id == tool_key:
        return inherited_color

    for shortcut in item.get("shortcuts") or []:
        color = _section_item_tint_color(shortcut, tool_key, inherited_color=inherited_color)
        if color is not None:
            return color

    return None


def get_tool_tint_color(tool_key, default=None):
    for section in TOOL_SECTION_DEFINITIONS.values():
        section_color = section.get("color")
        for item in section.get("items", []):
            color = _section_item_tint_color(item, tool_key, inherited_color=section_color)
            if color is not None:
                return _tool_color_to_hex(color)
    return default


def get_toolbar_sections(layout_id, resolve_items=True):
    section_ids = TOOLBAR_SECTION_LAYOUTS.get(layout_id, [])
    return [
        section
        for section in (get_tool_section(section_id, resolve_items=resolve_items) for section_id in section_ids)
        if section is not None
    ]
