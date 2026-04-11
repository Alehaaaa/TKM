from functools import partial
import re

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

TANGENT_TINT_COLOR = toolColors.UI_COLORS.orange.hex


def _tangent_menu_setup(tangent_type, tangent_label, icon_path):
    return lambda menu, source_widget=None: bar.build_tangent_menu(
        menu,
        tangent_type=tangent_type,
        tangent_label=tangent_label,
        icon_path=icon_path,
        source_widget=source_widget,
    )

TOOL_DEFINITIONS = {
    "share_keys": {
        "key": "share_keys",
        "label": "Share Keys",
        "text": "sK",
        "icon_path": media.share_keys_image,
        "callback": keyTools.share_keys,
        "menu_setup_fn": keyTools.build_share_keys_menu,
        "tooltip_template": helper.share_keys_tooltip_text,
        "shortcuts": [
            {"icon": media.share_keys_image, "label": "Share Keys", "keys": "Click"},
            {"icon": media.reblock_keys_image, "label": "reBlock", "keys": [QtCore.Qt.Key_Shift]},
        ],
        "shortcut_variants": [
            {
                "mask": 1,
                "text": "rB",
                "icon_path": media.reblock_keys_image,
                "tooltip_template": helper.reblock_move_tooltip_text,
                "description": "Reblock the selected animation.",
                "callback": keyTools.reblock_move,
            }
        ],
    },
    "reblock": {
        "key": "reblock",
        "label": "reBlock",
        "text": "rB",
        "icon_path": media.reblock_keys_image,
        "callback": keyTools.reblock_move,
        "tooltip_template": helper.reblock_move_tooltip_text,
        "description": "Reblock the selected animation.",
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
        "shortcuts": [
            {"icon": media.bake_animation_1_image, "label": "Bake on Ones", "keys": "Click"},
            {"icon": media.bake_animation_2_image, "label": "Bake on Twos", "keys": [QtCore.Qt.Key_Control]},
            {"icon": media.bake_animation_3_image, "label": "Bake on Threes", "keys": [QtCore.Qt.Key_Shift]},
            {"icon": media.bake_animation_3_image, "label": "Bake on Fours", "keys": [QtCore.Qt.Key_Control, QtCore.Qt.Key_Shift]},
            {"icon": media.bake_animation_custom_image, "label": "Bake Custom Interval", "keys": [QtCore.Qt.Key_Alt]},
        ],
        "shortcut_variants": [
            {
                "mask": 4,
                "text": "B2",
                "icon_path": media.bake_animation_2_image,
                "tooltip_template": helper.bake_animation_2_tooltip_text,
                "description": "Bake the animation using 2-frame steps.",
                "callback": keyTools.bake_animation_2,
            },
            {
                "mask": 1,
                "text": "B3",
                "icon_path": media.bake_animation_3_image,
                "tooltip_template": helper.bake_animation_3_tooltip_text,
                "description": "Bake the animation using 3-frame steps.",
                "callback": keyTools.bake_animation_3,
            },
            {
                "mask": 8,
                "text": "BC",
                "icon_path": media.bake_animation_custom_image,
                "tooltip_template": helper.bake_animation_custom_tooltip_text,
                "description": "Open the custom bake interval dialog.",
                "callback": bar.bake_animation_custom_window,
            },
            {
                "mask": 5,
                "text": "B4",
                "icon_path": media.bake_animation_3_image,
                "tooltip_template": helper.bake_animation_4_tooltip_text,
                "description": "Bake the animation using 4-frame steps.",
                "callback": keyTools.bake_animation_4,
            },
        ],
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
        "tooltip_template": helper.bake_animation_4_tooltip_text,
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
        "shortcuts": [
            {"icon": media.temp_pivot_image, "label": "Create Temp Pivot", "keys": "Click"},
            {"icon": media.temp_pivot_use_last_image, "label": "Use Last Pivot", "keys": [QtCore.Qt.Key_Shift]},
        ],
        "shortcut_variants": [
            {
                "mask": 1,
                "text": "TP+",
                "icon_path": media.temp_pivot_use_last_image,
                "tooltip_template": helper.temp_pivot_last_tooltip_text,
                "description": "Recreate the most recently used Temp Pivot setup.",
                "callback": lambda: bar.create_temp_pivot(True),
            }
        ],
    },
    "micro_move": {
        "key": "micro_move",
        "label": "Micro Move",
        "text": "MM",
        "icon_path": media.ruler_image,
        "tooltip_template": helper.micro_move_tooltip_text,
    },
    "move_left": {
        "key": "move_left",
        "label": "Nudge Left",
        "icon_path": media.nudge_left_image,
        "description": "Nudge selected keys to the left.",
        "shortcuts": [
            {"icon": media.nudge_left_image, "label": "Nudge Left", "keys": "Click"},
            {"icon": media.remove_inbetween_image, "label": "Remove Inbetween", "keys": [QtCore.Qt.Key_Shift]},
        ],
        "shortcut_variants": [
            {
                "mask": 1,
                "text": "-IB",
                "icon_path": media.remove_inbetween_image,
                "tooltip_template": helper.remove_inbetween_tooltip_text,
                "description": "Remove inbetweens using the current nudge step value.",
            }
        ],
    },
    "move_right": {
        "key": "move_right",
        "label": "Nudge Right",
        "icon_path": media.nudge_right_image,
        "description": "Nudge selected keys to the right.",
        "shortcuts": [
            {"icon": media.nudge_right_image, "label": "Nudge Right", "keys": "Click"},
            {"icon": media.insert_inbetween_image, "label": "Insert Inbetween", "keys": [QtCore.Qt.Key_Shift]},
        ],
        "shortcut_variants": [
            {
                "mask": 1,
                "text": "+IB",
                "icon_path": media.insert_inbetween_image,
                "tooltip_template": helper.insert_inbetween_tooltip_text,
                "description": "Insert inbetweens using the current nudge step value.",
            }
        ],
    },
    "static": {
        "key": "static",
        "label": "Delete Static Keys",
        "text": "S",
        "icon_path": media.delete_animation_image,
        "tooltip_template": helper.static_tooltip_text,
        "description": "Flatten the selected curve so it holds the first selected value.",
        "callback": lambda: keyTools.deleteStaticCurves(),
    },
    "match": {
        "key": "match",
        "label": "Match",
        "text": "M",
        "icon_path": media.match_image,
        "tooltip_template": helper.match_keys_tooltip_text,
        "description": "Match one selected curve to another.",
        "callback": lambda: keyTools.match_keys(),
    },
    "flip": {
        "key": "flip",
        "label": "Flip",
        "text": "F",
        "tooltip_template": helper.flip_tooltip_text,
        "description": "Inverts the selected curve vertically.",
        "callback": lambda: keyTools.flipCurves(),
    },
    "snap": {
        "key": "snap",
        "label": "Snap",
        "text": "Sn",
        "tooltip_template": helper.snap_tooltip_text,
        "description": "Snap selected sub-frame keys to the nearest whole frame.",
        "callback": lambda: keyTools.snapKeyframes(),
    },
    "overlap": {
        "key": "overlap",
        "label": "Overlap",
        "text": "O",
        "tooltip_template": helper.overlap_tooltip_text,
        "description": "Offset selected curves to create overlap.",
        "callback": keyTools.mod_overlap_animation,
    },
    "isolate_master": {
        "key": "isolate_master",
        "label": "Isolate",
        "icon_path": media.isolate_image,
        "callback": bar.isolate_master,
        "tooltip_template": helper.isolate_tooltip_text,
    },
    "align_selected_objects": {
        "key": "align_selected_objects",
        "label": "Align",
        "icon_path": media.match_image,
        "callback": bar.align_selected_objects,
        "tooltip_template": helper.align_tooltip_text,
        "shortcuts": [
            {"icon": media.match_image, "label": "Align All", "keys": "Click"},
            {"icon": media.align_menu_image, "label": "Align Translation", "keys": [QtCore.Qt.Key_Shift]},
            {"icon": media.align_menu_image, "label": "Align Rotation", "keys": [QtCore.Qt.Key_Control]},
            {"icon": media.align_menu_image, "label": "Align Scale", "keys": [QtCore.Qt.Key_Control, QtCore.Qt.Key_Shift]},
        ],
        "shortcut_variants": [
            {
                "mask": 1,
                "text": "AT",
                "icon_path": media.align_menu_image,
                "tooltip_template": helper.align_translation_tooltip_text,
                "description": "Match only translation values from the driver object.",
                "callback": partial(bar.align_selected_objects, pos=True, rot=False, scl=False),
            },
            {
                "mask": 4,
                "text": "AR",
                "icon_path": media.align_menu_image,
                "tooltip_template": helper.align_rotation_tooltip_text,
                "description": "Match only rotation values from the driver object.",
                "callback": partial(bar.align_selected_objects, pos=False, rot=True, scl=False),
            },
            {
                "mask": 5,
                "text": "AS",
                "icon_path": media.align_menu_image,
                "tooltip_template": helper.align_scale_tooltip_text,
                "description": "Match only scale values from the driver object.",
                "callback": partial(bar.align_selected_objects, pos=False, rot=False, scl=True),
            },
        ],
    },
    "mod_tracer": {
        "key": "mod_tracer",
        "label": "Tracer",
        "icon_path": media.tracer_image,
        "callback": bar.mod_tracer,
        "tooltip_template": helper.tracer_tooltip_text,
        "shortcuts": [
            {"icon": media.tracer_image, "label": "Create Tracer", "keys": "Click"},
            {"icon": media.refresh_image, "label": "Refresh Tracer", "keys": [QtCore.Qt.Key_Shift]},
            {"icon": media.tracer_show_hide_image, "label": "Toggle Tracer", "keys": [QtCore.Qt.Key_Control]},
            {"icon": media.remove_image, "label": "Remove Tracer", "keys": [QtCore.Qt.Key_Control, QtCore.Qt.Key_Alt]},
        ],
        "shortcut_variants": [
            {
                "mask": 1,
                "text": "TR+",
                "icon_path": media.refresh_image,
                "tooltip_template": helper.tracer_refresh_tooltip_text,
                "description": "Refresh the existing tracer without re-creating it.",
                "callback": bar.tracer_refresh,
            },
            {
                "mask": 4,
                "text": "TRo",
                "icon_path": media.tracer_show_hide_image,
                "tooltip_template": helper.tracer_toggle_tooltip_text,
                "description": "Show or hide the existing tracer.",
                "callback": bar.tracer_show_hide,
            },
            {
                "mask": 12,
                "text": "TRx",
                "icon_path": media.remove_image,
                "tooltip_template": helper.tracer_remove_tooltip_text,
                "description": "Remove the existing tracer node.",
                "callback": bar.remove_tracer_node,
            },
        ],
    },
    "reset_objects_mods": {
        "key": "reset_objects_mods",
        "label": "Reset Values",
        "command": "reset_values",
        "icon_path": media.asset_path("reset_animation_image"),
        "callback": keyTools.reset_objects_mods,
        "tooltip_template": helper.reset_values_tooltip_text,
        "shortcuts": [
            {"icon": media.asset_path("reset_animation_image"), "label": "Reset Values", "keys": "Click"},
            {"icon": media.asset_path("reset_animation_image"), "label": "Reset Translations", "keys": [QtCore.Qt.Key_Shift]},
            {"icon": media.asset_path("reset_animation_image"), "label": "Reset Rotations", "keys": [QtCore.Qt.Key_Control]},
            {"icon": media.asset_path("reset_animation_image"), "label": "Reset Scales", "keys": [QtCore.Qt.Key_Alt]},
            {
                "icon": media.asset_path("reset_animation_image"),
                "label": "Reset Translation Rotation Scale",
                "keys": [QtCore.Qt.Key_Control, QtCore.Qt.Key_Shift],
            },
        ],
        "shortcut_variants": [
            {
                "mask": 1,
                "command": "reset_translations",
                "text": "RT",
                "label": "Reset Translation",
                "icon_path": media.asset_path("reset_animation_image"),
                "tooltip_template": helper.reset_translations_tooltip_text,
                "description": "Reset only translation values for the selected objects.",
                "callback": lambda: keyTools.reset_object_values(reset_translations=True),
            },
            {
                "mask": 4,
                "command": "reset_rotations",
                "text": "RR",
                "label": "Reset Rotation",
                "icon_path": media.asset_path("reset_animation_image"),
                "tooltip_template": helper.reset_rotations_tooltip_text,
                "description": "Reset only rotation values for the selected objects.",
                "callback": lambda: keyTools.reset_object_values(reset_rotations=True),
            },
            {
                "mask": 8,
                "command": "reset_scales",
                "text": "RS",
                "label": "Reset Scales",
                "icon_path": media.asset_path("reset_animation_image"),
                "tooltip_template": helper.reset_scales_tooltip_text,
                "description": "Reset only scale values for the selected objects.",
                "callback": lambda: keyTools.reset_object_values(reset_scales=True),
            },
            {
                "mask": 5,
                "command": "reset_trs",
                "text": "RTRS",
                "label": "Reset Translation Rotation Scale",
                "icon_path": media.asset_path("reset_animation_image"),
                "tooltip_template": helper.reset_trs_tooltip_text,
                "description": "Reset translation, rotation, and scale values for the selected objects.",
                "callback": lambda: keyTools.reset_object_values(
                    reset_translations=True,
                    reset_rotations=True,
                    reset_scales=True,
                ),
            },
        ],
    },
    "delete_all_animation": {
        "key": "delete_all_animation",
        "label": "Delete All Animation",
        "command": "delete_all_animation",
        "icon_path": media.delete_animation_image,
        "callback": bar.mod_delete_animation,
        "tooltip_template": helper.delete_animation_tooltip_text,
        "shortcuts": [
            {"icon": media.delete_animation_image, "label": "Delete Animation", "keys": "Click"},
            {"icon": media.delete_animation_image, "label": "Delete Static Keys", "keys": [QtCore.Qt.Key_Shift]},
        ],
        "shortcut_variants": [
            {
                "mask": 1,
                "text": "S",
                "label": "Delete Static Keys",
                "icon_path": media.delete_animation_image,
                "tooltip_template": helper.static_tooltip_text,
                "description": "Flatten the selected curve so it holds the first selected value.",
                "callback": lambda: keyTools.deleteStaticCurves(),
                "shortcuts": [{"icon": media.delete_animation_image, "label": "Delete Static Keys", "keys": "Click"}],
            }
        ],
    },
    "select_rig_controls": {
        "key": "select_rig_controls",
        "label": "Select Rig Controls",
        "icon_path": media.select_rig_controls_image,
        "callback": bar.select_rig_controls,
        "tooltip_template": helper.select_rig_controls_tooltip_text,
        "description": "Select all rig controls. Ctrl+Click selects only animated rig controls.",
        "status_title": "Select Rig Controls",
        "status_description": "Select all rig controls. Ctrl+Click selects only animated rig controls.",
        "shortcuts": [
            {"icon": media.select_rig_controls_image, "label": "Select Rig Controls", "keys": "Click"},
            {"icon": media.select_rig_controls_animated_image, "label": "Select Animated Rig Controls", "keys": [QtCore.Qt.Key_Control]},
        ],
        "shortcut_variants": [
            {
                "mask": 4,
                "icon_path": media.select_rig_controls_animated_image,
                "tooltip_template": helper.select_rig_controls_animated_tooltip_text,
                "description": "Select only animated rig controls.",
                "status_title": "Select Animated Rig Controls",
                "status_description": "Select only animated rig controls.",
                "callback": bar.select_rig_controls_animated,
                "shortcuts": [{"icon": media.select_rig_controls_animated_image, "label": "Select Animated Rig Controls", "keys": "Click"}],
            }
        ],
    },
    "selectOpposite": {
        "key": "selectOpposite",
        "label": "Select Opposite",
        "icon_path": media.opposite_select_image,
        "callback": keyTools.selectOpposite,
        "tooltip_template": helper.opposite_select_tooltip_text,
        "shortcuts": [
            {"icon": media.opposite_select_image, "label": "Select Opposite", "keys": "Click"},
            {"icon": media.opposite_add_image, "label": "Add Opposite", "keys": [QtCore.Qt.Key_Shift]},
            {"icon": media.opposite_copy_image, "label": "Copy Opposite", "keys": [QtCore.Qt.Key_Alt]},
        ],
        "shortcut_variants": [
            {
                "mask": 1,
                "text": "AOp",
                "icon_path": media.opposite_add_image,
                "tooltip_template": helper.opposite_add_tooltip_text,
                "description": "Add the opposite control to the current selection.",
                "callback": keyTools.addSelectOpposite,
            },
            {
                "mask": 8,
                "text": "COp",
                "icon_path": media.opposite_copy_image,
                "tooltip_template": helper.opposite_copy_tooltip_text,
                "description": "Copy the opposite-name mapping for the current selection.",
                "callback": keyTools.copyOpposite,
            },
        ],
    },
    "copyOpposite": {
        "key": "copyOpposite",
        "label": "Copy Opposite",
        "icon_path": media.opposite_copy_image,
        "callback": keyTools.copyOpposite,
        "tooltip_template": helper.opposite_copy_tooltip_text,
    },
    "selection_sets": {
        "key": "selection_sets",
        "label": "Selection Sets",
        "text": "SS",
        "icon_path": media.selection_sets_image,
        "tooltip_template": helper.selection_sets_tooltip_text,
        "shortcuts": [
            {"icon": media.selection_sets_image, "label": "Selection Sets", "keys": "Click"},
            {"icon": media.selection_sets_export_image, "label": "Quick Export", "keys": [QtCore.Qt.Key_Control]},
            {"icon": media.selection_sets_import_image, "label": "Quick Import", "keys": [QtCore.Qt.Key_Control, QtCore.Qt.Key_Shift]},
            {"icon": media.selection_sets_export_image, "label": "Export", "keys": [QtCore.Qt.Key_Alt]},
            {"icon": media.selection_sets_import_image, "label": "Import", "keys": [QtCore.Qt.Key_Control, QtCore.Qt.Key_Alt]},
            {"icon": media.trash_image, "label": "Clear All Select Sets", "keys": [QtCore.Qt.Key_Control, QtCore.Qt.Key_Alt, QtCore.Qt.Key_Shift]},
        ],
        "shortcut_variants": [
            {
                "mask": 4,
                "text": "QEx",
                "icon_path": media.selection_sets_export_image,
                "tooltip_template": helper.quick_export_selection_sets_tooltip_text,
                "description": "Export selection sets to the shared quick file, overwriting it.",
                "callback": selectionSetsApi.quick_export_selection_sets,
            },
            {
                "mask": 5,
                "text": "QIm",
                "icon_path": media.selection_sets_import_image,
                "tooltip_template": helper.quick_import_selection_sets_tooltip_text,
                "description": "Import selection sets from the shared quick file.",
                "callback": selectionSetsApi.quick_import_selection_sets,
            },
            {
                "mask": 8,
                "text": "Ex",
                "icon_path": media.selection_sets_export_image,
                "tooltip_template": helper.export_selection_sets_tooltip_text,
                "description": "Export selection sets to a chosen file.",
                "callback": selectionSetsApi.export_selection_sets,
            },
            {
                "mask": 12,
                "text": "Im",
                "icon_path": media.selection_sets_import_image,
                "tooltip_template": helper.import_selection_sets_tooltip_text,
                "description": "Import selection sets from a chosen file.",
                "callback": selectionSetsApi.import_selection_sets,
            },
            {
                "mask": 13,
                "text": "Clr",
                "icon_path": media.trash_image,
                "tooltip_template": helper.clear_selection_sets_tooltip_text,
                "description": "Delete every selection set in the current scene.",
                "callback": selectionSetsApi.clear_all_selection_sets,
            },
        ],
    },
    "custom_graph": {
        "key": "custom_graph",
        "label": "Graph Editor Toolbar",
        "text": "GE",
        "icon_path": media.customGraph_image,
        "tooltip_template": helper.customGraph_tooltip_text,
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
        "key": "selectHierarchy",
        "label": "Select Hierarchy",
        "icon_path": media.select_hierarchy_image,
        "callback": bar.selectHierarchy,
        "tooltip_template": helper.select_hierarchy_tooltip_text,
    },
    "selector": {
        "key": "selector",
        "label": "Selector",
        "icon_path": media.selector_image,
        "callback": bar.selector_window,
        "tooltip_template": helper.selector_tooltip_text,
    },
    "create_locator": {
        "key": "create_locator",
        "label": "Create Locator",
        "icon_path": media.create_locator_image,
        "callback": bar.createLocator,
        "tooltip_template": helper.createLocator_tooltip_text,
    },
    "locator_select_temp": {
        "key": "locator_select_temp",
        "label": "Select Temp Locators",
        "icon_path": media.create_locator_image,
        "callback": bar.selectTempLocators,
    },
    "locator_remove_temp": {
        "key": "locator_remove_temp",
        "label": "Remove Temp Locators",
        "icon_path": media.create_locator_image,
        "callback": bar.deleteTempLocators,
    },
    "copy_pose": {
        "key": "copy_pose",
        "label": "Copy Pose",
        "icon_path": media.copy_pose_image,
        "callback": keyTools.copy_pose,
        "tooltip_template": helper.copy_pose_tooltip_text,
        "shortcuts": [
            {"icon": media.copy_pose_image, "label": "Copy Pose", "keys": "Click"},
            {"icon": media.paste_pose_image, "label": "Paste Pose", "keys": [QtCore.Qt.Key_Control]},
        ],
        "shortcut_variants": [
            {
                "mask": 4,
                "text": "PP",
                "icon_path": media.paste_pose_image,
                "tooltip_template": helper.paste_pose_tooltip_text,
                "description": "Paste the saved pose onto the current selection.",
                "callback": keyTools.paste_pose,
            }
        ],
    },
    "paste_pose": {
        "key": "paste_pose",
        "label": "Paste Pose",
        "icon_path": media.paste_pose_image,
        "callback": keyTools.paste_pose,
        "tooltip_template": helper.paste_pose_tooltip_text,
    },
    "copy_animation": {
        "key": "copy_animation",
        "label": "Copy Animation",
        "icon_path": media.copy_animation_image,
        "callback": keyTools.copy_animation,
        "tooltip_template": helper.copy_animation_tooltip_text,
        "status_title": "Copy Animation",
        "status_description": "Copy animation from the current selection.",
        "shortcuts": [
            {"icon": media.copy_animation_image, "label": "Copy Animation", "keys": "Click"},
            {"icon": media.paste_animation_image, "label": "Paste Animation", "keys": [QtCore.Qt.Key_Control]},
            {"icon": media.paste_insert_animation_image, "label": "Paste Insert", "keys": [QtCore.Qt.Key_Shift]},
            {"icon": media.paste_opposite_animation_image, "label": "Paste Opposite", "keys": [QtCore.Qt.Key_Control, QtCore.Qt.Key_Shift]},
        ],
        "shortcut_variants": [
            {
                "mask": 4,
                "text": "PA",
                "icon_path": media.paste_animation_image,
                "tooltip_template": helper.paste_animation_tooltip_text,
                "description": "Paste the saved animation onto the current selection.",
                "status_title": "Paste Animation",
                "status_description": "Paste the saved animation onto the current selection.",
                "callback": keyTools.paste_animation,
            },
            {
                "mask": 1,
                "text": "PI",
                "icon_path": media.paste_insert_animation_image,
                "tooltip_template": helper.paste_insert_animation_tooltip_text,
                "description": "Insert the saved animation while preserving surrounding timing.",
                "status_title": "Paste Insert Animation",
                "status_description": "Insert the saved animation while preserving surrounding timing.",
                "callback": keyTools.paste_insert_animation,
            },
            {
                "mask": 5,
                "text": "PO",
                "icon_path": media.paste_opposite_animation_image,
                "tooltip_template": helper.paste_opposite_animation_tooltip_text,
                "description": "Paste the saved animation onto the opposite side controls.",
                "status_title": "Paste Opposite Animation",
                "status_description": "Paste the saved animation onto the opposite side controls.",
                "callback": keyTools.paste_opposite_animation,
            },
        ],
    },
    "paste_animation": {
        "key": "paste_animation",
        "label": "Paste Animation",
        "icon_path": media.paste_animation_image,
        "callback": keyTools.paste_animation,
        "tooltip_template": helper.paste_animation_tooltip_text,
    },
    "paste_insert_animation": {
        "key": "paste_insert_animation",
        "label": "Paste Insert Animation",
        "icon_path": media.paste_insert_animation_image,
        "callback": keyTools.paste_insert_animation,
        "tooltip_template": helper.paste_insert_animation_tooltip_text,
    },
    "follow_cam": {
        "key": "follow_cam",
        "label": "Follow Cam",
        "icon_path": media.follow_cam_image,
        "callback": lambda *args: bar.create_follow_cam(translation=True, rotation=True),
        "tooltip_template": helper.follow_cam_tooltip_text,
        "shortcuts": [
            {"icon": media.follow_cam_image, "label": "Follow Translation Rotation", "keys": "Click"},
            {"icon": media.follow_cam_image, "label": "Follow Translation", "keys": [QtCore.Qt.Key_Shift]},
            {"icon": media.follow_cam_image, "label": "Follow Rotation", "keys": [QtCore.Qt.Key_Control]},
            {"icon": media.remove_image, "label": "Remove Follow Cam", "keys": [QtCore.Qt.Key_Control, QtCore.Qt.Key_Alt]},
        ],
        "shortcut_variants": [
            {
                "mask": 1,
                "text": "FT",
                "icon_path": media.follow_cam_image,
                "tooltip_template": helper.follow_translation_tooltip_text,
                "description": "Create a Follow Cam that inherits only translation.",
                "callback": lambda: bar.create_follow_cam(translation=True, rotation=False),
            },
            {
                "mask": 4,
                "text": "FR",
                "icon_path": media.follow_cam_image,
                "tooltip_template": helper.follow_rotation_tooltip_text,
                "description": "Create a Follow Cam that inherits only rotation.",
                "callback": lambda: bar.create_follow_cam(translation=False, rotation=True),
            },
            {
                "mask": 12,
                "text": "FX",
                "icon_path": media.remove_image,
                "tooltip_template": helper.remove_follow_cam_tooltip_text,
                "description": "Remove the current Follow Cam setup.",
                "callback": bar.remove_followCam,
            },
        ],
    },
    "animation_offset": {
        "key": "animation_offset",
        "label": "Anim Offset",
        "icon_path": media.animation_offset_image,
        "tooltip_template": helper.animation_offset_tooltip_text,
    },
    "mod_link_objects": {
        "key": "mod_link_objects",
        "label": "Copy/Paste Link",
        "icon_path": media.link_objects_image,
        "callback": keyTools.copy_link,
        "tooltip_template": helper.link_objects_tooltip_text,
        "shortcuts": [
            {"icon": media.link_objects_copy_image, "label": "Copy Link Position", "keys": "Click"},
            {"icon": media.link_objects_paste_image, "label": "Paste Link Position", "keys": [QtCore.Qt.Key_Shift]},
        ],
        "shortcut_variants": [
            {
                "mask": 1,
                "text": "LP",
                "icon_path": media.link_objects_paste_image,
                "tooltip_template": helper.paste_link_tooltip_text,
                "description": "Apply the saved link relationship to the current selection.",
                "callback": keyTools.paste_link,
            }
        ],
    },
    "copy_worldspace_single_frame": {
        "key": "copy_worldspace_single_frame",
        "label": "Copy World Space",
        "icon_path": media.worldspace_copy_frame_image,
        "callback": bar.copy_worldspace_single_frame,
        "tooltip_template": helper.copy_worldspace_tooltip_text,
        "shortcuts": [
            {"icon": media.worldspace_copy_frame_image, "label": "Copy World Space", "keys": "Click"},
            {"icon": media.worldspace_paste_frame_image, "label": "Paste World Space", "keys": [QtCore.Qt.Key_Control]},
            {"icon": media.worldspace_copy_animation_image, "label": "Copy World Space - Selected Range", "keys": [QtCore.Qt.Key_Shift]},
            {
                "icon": media.worldspace_paste_animation_image,
                "label": "Paste World Space - All Animation",
                "keys": [QtCore.Qt.Key_Control, QtCore.Qt.Key_Shift],
            },
        ],
        "shortcut_variants": [
            {
                "mask": 4,
                "text": "WSP",
                "icon_path": media.worldspace_paste_frame_image,
                "tooltip_template": helper.paste_worldspace_tooltip_text,
                "description": "Paste the saved World Space position for the current frame.",
                "callback": bar.paste_worldspace_single_frame,
            },
            {
                "mask": 1,
                "text": "WSR",
                "icon_path": media.worldspace_copy_animation_image,
                "tooltip_template": helper.copy_worldspace_range_tooltip_text,
                "description": "Copy World Space positions for the selected range or full animation.",
                "callback": bar.copy_range_worldspace_animation,
            },
            {
                "mask": 5,
                "text": "WSA",
                "icon_path": media.worldspace_paste_animation_image,
                "tooltip_template": helper.paste_worldspace_animation_tooltip_text,
                "description": "Paste saved World Space positions for the selected range or all animation.",
                "callback": bar.color_worldspace_paste_animation,
            },
        ],
    },
    "paste_worldspace_single_frame": {
        "key": "paste_worldspace_single_frame",
        "label": "Paste World Space",
        "icon_path": media.worldspace_paste_frame_image,
        "callback": bar.paste_worldspace_single_frame,
        "tooltip_template": helper.paste_worldspace_tooltip_text,
    },
    "align_translation": {
        "key": "align_translation",
        "label": "Translation",
        "icon_path": media.align_menu_image,
        "callback": partial(bar.align_selected_objects, pos=True, rot=False, scl=False),
    },
    "align_rotation": {
        "key": "align_rotation",
        "label": "Rotation",
        "icon_path": media.align_menu_image,
        "callback": partial(bar.align_selected_objects, pos=False, rot=True, scl=False),
    },
    "align_scale": {
        "key": "align_scale",
        "label": "Scale",
        "icon_path": media.align_menu_image,
        "callback": partial(bar.align_selected_objects, pos=False, rot=False, scl=True),
    },
    "align_range": {
        "key": "align_range",
        "label": "Match Range",
        "icon_path": media.match_image,
        "callback": bar.align_range,
    },
    "tracer_refresh": {
        "key": "tracer_refresh",
        "label": "Refresh Tracer",
        "icon_path": media.refresh_image,
        "callback": bar.tracer_refresh,
    },
    "tracer_show_hide": {
        "key": "tracer_show_hide",
        "label": "Toggle Tracer",
        "icon_path": media.tracer_show_hide_image,
        "callback": bar.tracer_show_hide,
    },
    "tracer_offset_node": {
        "key": "tracer_offset_node",
        "label": "Select Offset Object",
        "icon_path": media.tracer_select_offset_image,
        "callback": bar.select_tracer_offset_node,
    },
    "tracer_grey": {
        "key": "tracer_grey",
        "label": "Tracer Style: Grey",
        "icon_path": media.tracer_grey_image,
        "callback": bar.set_tracer_grey_color,
    },
    "tracer_red": {
        "key": "tracer_red",
        "label": "Tracer Style: Red",
        "icon_path": media.tracer_red_image,
        "callback": bar.set_tracer_red_color,
    },
    "tracer_blue": {
        "key": "tracer_blue",
        "label": "Tracer Style: Blue",
        "icon_path": media.tracer_blue_image,
        "callback": bar.set_tracer_blue_color,
    },
    "tracer_remove": {
        "key": "tracer_remove",
        "label": "Remove Tracer",
        "icon_path": media.remove_image,
        "callback": bar.remove_tracer_node,
    },
    "reset_set_defaults": {
        "key": "reset_set_defaults",
        "label": "Set Default Values For Selected",
        "icon_path": media.asset_path("reset_animation_image"),
        "callback": keyTools.save_default_values,
    },
    "reset_restore_defaults": {
        "key": "reset_restore_defaults",
        "label": "Restore Default Values For Selected",
        "icon_path": media.asset_path("reset_animation_image"),
        "callback": keyTools.remove_default_values_for_selected_object,
    },
    "reset_clear_all": {
        "key": "reset_clear_all",
        "label": "Clear All Saved Data",
        "icon_path": media.asset_path("reset_animation_image"),
        "callback": keyTools.restore_default_data,
    },
    "mirror": {
        "key": "mirror",
        "label": "Mirror",
        "icon_path": media.mirror_image,
        "callback": keyTools.mirror,
        "tooltip_template": helper.mirror_tooltip_text,
        "shortcuts": [
            {"icon": media.mirror_image, "label": "Mirror", "keys": "Click"},
            {"icon": media.mirror_image, "label": "Add Exception Invert", "keys": [QtCore.Qt.Key_Shift]},
            {"icon": media.mirror_image, "label": "Add Exception Keep", "keys": [QtCore.Qt.Key_Control]},
            {"icon": media.mirror_image, "label": "Remove Exception", "keys": [QtCore.Qt.Key_Control, QtCore.Qt.Key_Shift]},
        ],
        "shortcut_variants": [
            {
                "mask": 1,
                "text": "MI",
                "icon_path": media.mirror_image,
                "tooltip_template": helper.mirror_tooltip_text,
                "description": "Add an invert mirror exception for the current selection.",
                "callback": keyTools.add_mirror_invert_exception,
            },
            {
                "mask": 4,
                "text": "MK",
                "icon_path": media.mirror_image,
                "tooltip_template": helper.mirror_tooltip_text,
                "description": "Add a keep mirror exception for the current selection.",
                "callback": keyTools.add_mirror_keep_exception,
            },
            {
                "mask": 5,
                "text": "MR",
                "icon_path": media.mirror_image,
                "tooltip_template": helper.mirror_tooltip_text,
                "description": "Remove the mirror exception for the current selection.",
                "callback": keyTools.remove_mirror_invert_exception,
            },
        ],
    },
    "mirror_add_invert": {
        "key": "mirror_add_invert",
        "label": "Add Exception Invert",
        "icon_path": media.mirror_image,
        "callback": keyTools.add_mirror_invert_exception,
    },
    "mirror_add_keep": {
        "key": "mirror_add_keep",
        "label": "Add Exception Keep",
        "icon_path": media.mirror_image,
        "callback": keyTools.add_mirror_keep_exception,
    },
    "mirror_remove_exc": {
        "key": "mirror_remove_exc",
        "label": "Remove Exception",
        "icon_path": media.mirror_image,
        "callback": keyTools.remove_mirror_invert_exception,
    },
    "opposite_add": {
        "key": "opposite_add",
        "label": "Add Opposite",
        "icon_path": media.opposite_add_image,
        "callback": keyTools.addSelectOpposite,
        "tooltip_template": helper.opposite_add_tooltip_text,
    },
    "opposite_copy": {
        "key": "opposite_copy",
        "label": "Copy Opposite",
        "icon_path": media.opposite_copy_image,
        "callback": keyTools.copyOpposite,
        "tooltip_template": helper.opposite_copy_tooltip_text,
    },
    "paste_pose_direct": {
        "key": "paste_pose_direct",
        "label": "Paste Pose",
        "icon_path": media.paste_pose_image,
        "callback": keyTools.paste_pose,
    },
    "paste_animation_direct": {
        "key": "paste_animation_direct",
        "label": "Paste Animation",
        "icon_path": media.paste_animation_image,
        "callback": keyTools.paste_animation,
    },
    "paste_insert_animation_direct": {
        "key": "paste_insert_animation_direct",
        "label": "Paste Insert",
        "icon_path": media.paste_insert_animation_image,
        "callback": keyTools.paste_insert_animation,
    },
    "paste_opposite_animation_direct": {
        "key": "paste_opposite_animation_direct",
        "label": "Paste Opposite",
        "icon_path": media.paste_opposite_animation_image,
        "callback": keyTools.paste_opposite_animation,
    },
    "paste_animation_to": {
        "key": "paste_animation_to",
        "label": "Paste To",
        "icon_path": media.paste_animation_image,
        "callback": keyTools.paste_animation_to,
    },
    "tp_last_used": {
        "key": "tp_last_used",
        "label": "Use Last Pivot",
        "icon_path": media.temp_pivot_use_last_image,
        "callback": lambda: bar.create_temp_pivot(True),
    },
    "fcam_trans_only": {
        "key": "fcam_trans_only",
        "label": "Follow only Translation",
        "icon_path": media.follow_cam_image,
        "callback": lambda: bar.create_follow_cam(translation=True, rotation=False),
    },
    "fcam_rot_only": {
        "key": "fcam_rot_only",
        "label": "Follow only Rotation",
        "icon_path": media.follow_cam_image,
        "callback": lambda: bar.create_follow_cam(translation=False, rotation=True),
    },
    "fcam_remove": {
        "key": "fcam_remove",
        "label": "Remove Follow Cam",
        "icon_path": media.remove_image,
        "callback": bar.remove_followCam,
    },
    "link_copy": {
        "key": "link_copy",
        "label": "Copy Link Position",
        "icon_path": media.link_objects_copy_image,
        "callback": keyTools.copy_link,
    },
    "link_paste": {
        "key": "link_paste",
        "label": "Paste Link Position",
        "icon_path": media.link_objects_paste_image,
        "callback": keyTools.paste_link,
    },
    "ws_copy_range": {
        "key": "ws_copy_range",
        "label": "Copy World Space - Selected Range",
        "icon_path": media.worldspace_copy_animation_image,
        "callback": bar.copy_range_worldspace_animation,
        "tooltip_template": helper.copy_worldspace_range_tooltip_text,
    },
    "ws_paste_frame": {
        "key": "ws_paste_frame",
        "label": "Paste World Space",
        "icon_path": media.worldspace_paste_frame_image,
        "callback": bar.paste_worldspace_single_frame,
        "tooltip_template": helper.paste_worldspace_tooltip_text,
    },
    "ws_paste": {
        "key": "ws_paste",
        "label": "Paste World Space - All Animation",
        "icon_path": media.worldspace_paste_animation_image,
        "callback": bar.color_worldspace_paste_animation,
        "tooltip_template": helper.paste_worldspace_animation_tooltip_text,
    },
    "custom_tools": {
        "key": "custom_tools",
        "label": "Custom Tools",
        "icon_path": media.custom_tools_image,
        "tooltip_template": helper.custom_tools_tooltip_text,
    },
    "custom_scripts": {
        "key": "custom_scripts",
        "label": "Custom Scripts",
        "icon_path": media.custom_scripts_image,
        "tooltip_template": helper.custom_scripts_tooltip_text,
    },
    "settings": {
        "key": "settings",
        "label": "Settings",
        "icon_path": media.settings_image,
        "description": "Access global preferences, check for updates, and view credits.",
    },
    "graph_isolate_curves": {
        "key": "graph_isolate_curves",
        "label": "Isolate",
        "icon_path": media.isolate_image,
        "callback": keyTools.isolateCurve,
        "tooltip_template": helper.graph_isolate_curves_tooltip_text,
        "description": "Isolate selected curves.",
    },
    "graph_toggle_mute": {
        "key": "graph_toggle_mute",
        "label": "Mute",
        "text": "Mt",
        "callback": keyTools.toggleMute,
        "tooltip_template": helper.graph_mute_tooltip_text,
        "description": "Toggle mute on selected curves.",
    },
    "graph_toggle_lock": {
        "key": "graph_toggle_lock",
        "label": "Lock",
        "text": "Lk",
        "callback": keyTools.toggleLock,
        "tooltip_template": helper.graph_lock_tooltip_text,
        "description": "Toggle lock on selected curves.",
    },
    "graph_filter": {
        "key": "graph_filter",
        "label": "Filter",
        "text": "Fi",
        "tooltip_template": helper.graph_filter_tooltip_text,
        "description": "Filter selection in the GraphEditor. Shift+Click to deactivate.",
    },
    "graph_reset": {
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
        "key": "tangent_cycle_matcher",
        "label": "Cycle Matcher",
        "text": "CM",
        "icon_path": media.asset_path("match_curve_cycle_image"),
        "callback": keyTools.match_curve_cycle,
        "tint_color": TANGENT_TINT_COLOR,
        "tooltip_template": helper.tangent_cycle_matcher_tooltip_text,
        "description": "Curve cycle matcher.",
    },
    "tangent_bouncy": {
        "key": "tangent_bouncy",
        "label": "Bouncy Tangent",
        "text": "BO",
        "icon_path": media.bouncy_tangent_image,
        "callback": keyTools.bouncy_tangets,
        "tint_color": TANGENT_TINT_COLOR,
        "tooltip_template": helper.tangent_bouncy_tooltip_text,
        "description": "Set bouncy tangents.",
    },
    "tangent_auto": {
        "key": "tangent_auto",
        "label": "Auto Tangent",
        "text": "AU",
        "icon_path": media.auto_tangent_image,
        "callback": lambda: bar.setTangent("auto"),
        "tint_color": TANGENT_TINT_COLOR,
        "menu_setup_fn": _tangent_menu_setup("auto", "Auto Tangent", media.auto_tangent_image),
        "tooltip_template": helper.auto_tangent_tooltip_text,
        "description": "Set selected keys to Auto tangents.",
    },
    "tangent_spline": {
        "key": "tangent_spline",
        "label": "Spline Tangent",
        "text": "SP",
        "icon_path": media.spline_tangent_image,
        "callback": lambda: bar.setTangent("spline"),
        "tint_color": TANGENT_TINT_COLOR,
        "menu_setup_fn": _tangent_menu_setup("spline", "Spline Tangent", media.spline_tangent_image),
        "tooltip_template": helper.spline_tangent_tooltip_text,
        "description": "Set selected keys to Spline tangents.",
    },
    "tangent_clamped": {
        "key": "tangent_clamped",
        "label": "Clamped Tangent",
        "text": "CL",
        "icon_path": media.clamped_tangent_image,
        "callback": lambda: bar.setTangent("clamped"),
        "tint_color": TANGENT_TINT_COLOR,
        "menu_setup_fn": _tangent_menu_setup("clamped", "Clamped Tangent", media.clamped_tangent_image),
        "tooltip_template": helper.clamped_tangent_tooltip_text,
        "description": "Set selected keys to Clamped tangents.",
    },
    "tangent_linear": {
        "key": "tangent_linear",
        "label": "Linear Tangent",
        "text": "LI",
        "icon_path": media.linear_tangent_image,
        "callback": lambda: bar.setTangent("linear"),
        "tint_color": TANGENT_TINT_COLOR,
        "menu_setup_fn": _tangent_menu_setup("linear", "Linear Tangent", media.linear_tangent_image),
        "tooltip_template": helper.linear_tangent_tooltip_text,
        "description": "Set selected keys to Linear tangents.",
    },
    "tangent_flat": {
        "key": "tangent_flat",
        "label": "Flat Tangent",
        "text": "FT",
        "icon_path": media.flat_tangent_image,
        "callback": lambda: bar.setTangent("flat"),
        "tint_color": TANGENT_TINT_COLOR,
        "menu_setup_fn": _tangent_menu_setup("flat", "Flat Tangent", media.flat_tangent_image),
        "tooltip_template": helper.flat_tangent_tooltip_text,
        "description": "Set selected keys to Flat tangents.",
    },
    "tangent_step": {
        "key": "tangent_step",
        "label": "Step Tangent",
        "text": "ST",
        "icon_path": media.step_tangent_image,
        "callback": lambda: bar.setTangent("step"),
        "tint_color": TANGENT_TINT_COLOR,
        "menu_setup_fn": _tangent_menu_setup("step", "Step Tangent", media.step_tangent_image),
        "tooltip_template": helper.step_tangent_tooltip_text,
        "description": "Set selected keys to Stepped tangents.",
    },
    "tangent_plateau": {
        "key": "tangent_plateau",
        "label": "Plateau Tangent",
        "text": "PT",
        "icon_path": media.plateau_tangent_image,
        "callback": lambda: bar.setTangent("plateau"),
        "tint_color": TANGENT_TINT_COLOR,
        "menu_setup_fn": _tangent_menu_setup("plateau", "Plateau Tangent", media.plateau_tangent_image),
        "tooltip_template": helper.plateau_tangent_tooltip_text,
        "description": "Set selected keys to Plateau tangents.",
    },
}

TOOL_GROUP_DEFINITIONS = {
    "delete_tools": [
        {"type": "tool", "id": "delete_all_animation", "overrides": {"key": "delete_anim", "default": True}},
        {"type": "tool", "id": "static"},
    ],
    "reset_tools": [
        {"type": "tool", "id": "reset_objects_mods", "overrides": {"key": "reset_values", "default": True}},
        {"type": "variant", "tool_id": "reset_objects_mods", "command": "reset_translations"},
        {"type": "variant", "tool_id": "reset_objects_mods", "command": "reset_rotations"},
        {"type": "variant", "tool_id": "reset_objects_mods", "command": "reset_scales"},
        {"type": "variant", "tool_id": "reset_objects_mods", "command": "reset_trs"},
        {"type": "tool", "id": "reset_set_defaults"},
        {"type": "tool", "id": "reset_restore_defaults"},
        "separator",
        {"type": "tool", "id": "reset_clear_all"},
        "separator",
        {
            "type": "raw",
            "data": {
                "key": "reset_help",
                "label": "Help",
                "icon_path": media.help_menu_image,
                "callback": lambda: general.open_url("https://thekeymachine.gitbook.io/base/the-toolbar/animation-tools/reset-to-default"),
                "pinnable": False,
            },
        },
    ],
}


def _variant_command_name(tool_key, variant, index):
    variant_key = variant.get("key")
    if variant_key:
        return variant_key
    label = variant.get("label") or variant.get("text") or variant.get("description") or ""
    slug = re.sub(r"[^a-z0-9]+", "_", label.lower()).strip("_")
    if slug:
        return "{}_{}".format(tool_key, slug)
    return "{}_option_{}".format(tool_key, index)


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
    normalized.setdefault("shortcuts", fallback.get("shortcuts", []))
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


def _bind_variant_callback(tool_key, variant_state, index):
    callback = variant_state.get("callback")
    if not callback:
        return variant_state

    bound = dict(variant_state)
    command_name = bound.get("command") or _variant_command_name(tool_key, bound, index)
    bound["command"] = command_name
    bound["callback"] = trigger.make_command_callback(command_name, callback, aliases=bound.get("command_aliases"))
    return bound


def _resolve_tool_definition(tool_key, state):
    tool = _bind_tool_callback(tool_key, _normalize_tool_state(state))
    tool["shortcut_variants"] = [
        _bind_variant_callback(tool_key, _normalize_tool_state(variant, fallback=tool), index)
        for index, variant in enumerate(tool.get("shortcut_variants", []), start=1)
    ]
    return tool


def _resolve_group_item(item):
    if item == "separator":
        return "separator"

    item_type = item.get("type")
    if item_type == "tool":
        return get_tool(item["id"], **item.get("overrides", {}))

    if item_type == "variant":
        return get_tool_variant(item["tool_id"], item["command"], **item.get("overrides", {}))

    if item_type == "raw":
        return dict(item.get("data", {}))

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


def get_tool_variant(tool_id, command_name, **overrides):
    tool = get_tool(tool_id, **overrides)
    for variant in tool.get("shortcut_variants", []):
        if variant.get("command") == command_name:
            return variant
    return None


def get_tool_group(group_id):
    group_def = TOOL_GROUP_DEFINITIONS.get(group_id)
    if not group_def:
        return []

    resolved = []
    for item in group_def:
        resolved_item = _resolve_group_item(item)
        if resolved_item is not None:
            resolved.append(resolved_item)
    return resolved
