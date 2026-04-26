"""

TheKeyMachine - Animation Toolset for Maya Animators


This file is part of TheKeyMachine, an open source software for Autodesk Maya licensed under the GNU General Public License v3.0 (GPL-3.0).
You are free to use, modify, and distribute this code under the terms of the GPL-3.0 license.
By using this code, you agree to keep it open source and share any modifications.
This code is provided "as is," without any warranty. For the full license text, visit https://www.gnu.org/licenses/gpl-3.0.html

thekeymachine.xyz / x@thekeymachine.xyz

Developed by: Rodrigo Torres / rodritorres.com
Modified by: Alehaaaa / alehaaaa.github.io



"""

import os

import TheKeyMachine.mods.mediaMod as media
from TheKeyMachine.mods.generalMod import config
from TheKeyMachine.tooltips.tooltip import separator, tooltip_media, tool_tooltip

INSTALL_PATH = config["INSTALL_PATH"]
TOOLTIPS_MOVIES_PATH = os.path.join(INSTALL_PATH, "TheKeyMachine", "tooltips", "movies")


# ----------------------------------------------  TOOLTIPS  --------------------------------------------------------


class _TooltipMovieLibrary:
    def __getattr__(self, name):
        return tooltip_media(os.path.join(TOOLTIPS_MOVIES_PATH, f"{name}.gif"))


movie = _TooltipMovieLibrary()


# -------- KeyBox


nudge_keyleft_b_widget_tooltip_text = (
    "Nudge Keys Left",
    ["Nudge the selected keyframes by the number of frames specified in the central box."],
)


remove_inbetween_b_widget_tooltip_text = (
    "Remove Inbetween",
    ["Remove one inbetween."],
)


move_keyframes_intField_widget_tooltip_text = (
    "Set",
    ["Set the number of frames to move when using the Nudge tool."],
)

insert_inbetween_b_widget_tooltip_text = (
    "Insert Inbetween",
    ["Add one inbetween."],
)


nudge_keyright_b_widget_tooltip_text = (
    "Nudge Keys Right",
    ["Nudge the selected keyframes by the number of frames specified in the central box."],
)


clear_selected_keys_widget_tooltip_text = (
    "Break Keys Selection",
    [
        "When you select a range in the Time Slider and use the nudge tools, the keys in that range are selected automatically.",
        "Use this to clear that key selection so you can go back to nudging a single frame.",
    ],
)


select_scene_animation_widget_tooltip_text = (
    "Select Scene Animation",
    [
        "Select all animation curves in the scene.",
        "Useful when you want to move all animation with the nudge tools.",
        "Select the curves, set the frame offset, then use Nudge Keys Left or Nudge Keys Right.",
    ],
)


# ------ Sliders


blend_tooltip_text = (
    "Blend to Neighbor",
    [
        "Blend between neighboring keyframe values.",
        "Select channels in the Channel Box to affect only those channels.",
    ],
)

blend_to_default_tooltip_text = (
    "Blend to Default",
    ["Blend the current value toward its default value."],
)

blend_to_frame_tooltip_text = (
    "Blend to Frame",
    [
        "Each button stores the current frame when pressed.",
        "The blend slider then blends between the stored frames.",
    ],
)

pull_push_tooltip_text = (
    "Pull | Push",
    ["Soften or intensify the animation."],
)

tweener_tooltip_text = (
    "Tweener",
    [
        "Tween between the previous and next keyframe.",
        "Select channels in the Channel Box to affect only those channels.",
    ],
)

tweener_world_space_tooltip_text = (
    "Tweener World Space",
    ["Tween between the previous and next keyframe in world space."],
)


# ----- Tangent


auto_tangent_tooltip_text = (
    "Auto Tangent",
    ["Set the tangents of the selected keyframes to Auto."],
    media.auto_tangent_image,
)

spline_tangent_tooltip_text = (
    "Spline Tangent",
    ["Set the tangents of the selected keyframes to Spline."],
    media.spline_tangent_image,
)

clamped_tangent_tooltip_text = (
    "Clamped Tangent",
    ["Set the tangents of the selected keyframes to Clamped."],
    media.clamped_tangent_image,
)

linear_tangent_tooltip_text = (
    "Linear Tangent",
    ["Set the tangents of the selected keyframes to Linear."],
    media.linear_tangent_image,
)

flat_tangent_tooltip_text = (
    "Flat Tangent",
    ["Set the tangents of the selected keyframes to Flat."],
    media.flat_tangent_image,
)

step_tangent_tooltip_text = (
    "Step Tangent",
    ["Set the tangents of the selected keyframes to Stepped."],
    media.step_tangent_image,
)

plateau_tangent_tooltip_text = (
    "Plateau Tangent",
    ["Set the tangents of the selected keyframes to Plateau."],
    media.plateau_tangent_image,
)


# ----- ReBlock, ShareKeys, BakeKeys

reblock_move_tooltip_text = (
    "reBlock",
    [
        "reBlock helps you place animation keys back onto the intended main poses.",
        "Useful when timing adjustments have left channels keyed on inconsistent frames.",
        "Select the objects and run the tool.",
    ],
    media.reblock_keys_image,
)

bake_animation_4_tooltip_text = (
    "Bake on Fours",
    [
        "Bake the selected animation using 4-frame steps.",
        "Useful for stepped blocking passes or reducing key density while keeping pose timing readable.",
    ],
    media.bake_animation_3_image,
)


bake_animation_custom_tooltip_text = (
    "Bake Custom Interval",
    [
        "Bake the selected animation using a custom frame interval.",
        "Useful for stepped blocking passes or custom sampling density.",
    ],
    media.bake_animation_custom_image,
)

bake_animation_1_tooltip_text = (
    "Bake on Ones",
    ["Bake the selected animation on every frame."],
    media.bake_animation_1_image,
)

bake_animation_2_tooltip_text = (
    "Bake on Twos",
    ["Bake the selected animation every two frames."],
    media.bake_animation_2_image,
)

bake_animation_3_tooltip_text = (
    "Bake on Threes",
    ["Bake the selected animation every three frames."],
    media.bake_animation_3_image,
)


gimbal_fixer_tooltip_text = (
    "Gimbal Fixer",
    [
        "Change rotation order without changing the visible animation result.",
        "Useful when a control is suffering from gimbal lock and needs a safer rotate order.",
    ],
    media.reblock_keys_image,
)

share_keys_tooltip_text = (
    "Share Keys",
    [
        "Share keyframe times across the selected channels or objects.",
        "Useful for aligning blocking keys across controls while preserving their values.",
        "If a time range is active, the operation is limited to that range.",
    ],
    media.share_keys_image,
)

orbit_tooltip_text = (
    "Orbit",
    [
        "Open the floating quick-access panel for your most-used animation tools.",
        "Configure which actions appear in it and keep it close to the main toolbar while animating.",
    ],
    media.orbit_ui_image,
)

attribute_switcher_tooltip_text = (
    "Attribute Switcher",
    [
        "Open the floating Attribute Switcher for the current selection.",
        "Useful for switch attributes, rotate-order changes, and current-frame or all-keys switching.",
    ],
    media.attribute_switcher_image,
)


# ----- Pointer


select_rig_controls_tooltip_text = (
    "Select Rig Controls",
    [
        "Will select all the controls of a rig hierarchy.",
        "Only NURBS-curve controls are included.",
    ],
    media.select_rig_controls_image,
)

select_rig_controls_animated_tooltip_text = (
    "Select Animated Rig Controls",
    [
        "Select only rig controls that currently have animation.",
        "Only NURBS-curve controls are included.",
    ],
    media.select_rig_controls_animated_image,
)

depth_mover_tooltip_text = (
    "Depth Mover",
    ["Adjust object depth without changing its apparent camera-space framing."],
    media.depth_mover_image,
)


# ----- Isolate


isolate_tooltip_text = (
    "Isolate",
    [
        "Isolate an entire rig or object hierarchy from a single selected control.",
        "Useful for working on one or more characters without scene clutter.",
        "Right-click for bookmarks and additional isolate options.",
    ],
    media.isolate_image,
)


createLocator_tooltip_text = (
    "Temp Locator",
    [
        "Create temporary locators from the current selection.",
        "Useful for marking positions or building quick references during blocking and cleanup.",
    ],
    media.create_locator_image,
)

align_tooltip_text = (
    "Align",
    [
        "Align one object to another.",
        "Select the driven object first, then the source object.",
        "If a time range is active, alignment can be applied across that range.",
    ],
    media.match_image,
)

tracer_tooltip_text = (
    "Tracer",
    [
        "Create a motion trail for the selected object.",
        "The tracer can be refreshed, shown or hidden, and reused without rebuilding it each time.",
    ],
    media.tracer_image,
)

reset_values_tooltip_text = (
    "Reset to Default",
    [
        "Reset objects or attributes to their default values.",
        "Select channels in the Channel Box to reset only specific attributes.",
    ],
    media.asset_path("reset_animation_image"),
)

delete_animation_tooltip_text = (
    "Delete Animation",
    [
        "Delete animation from the current selection.",
        "Select channels in the Channel Box to limit the deletion to specific attributes.",
        movie.delete_all_animation,
        separator,
        "Tip: You can select a time range to delete keys only inside that range.",
        movie.delete_all_animation_selection,
    ],
    media.delete_animation_image,
)


opposite_select_tooltip_text = (
    "Select Opposite",
    [
        "Select the opposite-side control for the current rig selection.",
        "Works with one or more selected controls.",
    ],
    media.opposite_select_image,
)

opposite_add_tooltip_text = (
    "Add Opposite",
    ["Add the opposite-side control to the current selection."],
    media.opposite_select_image,
)

opposite_copy_tooltip_text = (
    "Copy Opposite",
    [
        "Copy current values from the selected controls to their opposite-side controls.",
        "Mirror exceptions affect how opposite mapping is resolved.",
    ],
    media.opposite_copy_image,
)

mirror_tooltip_text = (
    "Mirror",
    [
        "Mirror the selected controls to their opposite-side equivalents.",
        "Mirror exceptions can be configured per rig and are saved for reuse.",
    ],
    media.mirror_image,
)

copy_animation_tooltip_text = (
    "Copy Animation",
    [
        "Copy animation from the selected objects or controls.",
        "The copied data is stored on disk so it can be pasted in another Maya session.",
    ],
    media.copy_animation_image,
)

paste_animation_tooltip_text = (
    "Paste Animation",
    ["Paste the saved animation onto the current selection."],
    media.paste_animation_image,
)

paste_insert_animation_tooltip_text = (
    "Paste Insert Animation",
    ["Insert the saved animation while preserving surrounding timing."],
    media.paste_insert_animation_image,
)

copy_pose_tooltip_text = (
    "Copy Pose",
    [
        "Copy the current pose from the selected controls.",
        "The pose can be pasted later in the same scene or another Maya session.",
    ],
    media.copy_pose_image,
)


selector_tooltip_text = (
    "Selector",
    [
        "Open a window showing the current selection as an easy-to-manage list.",
        "Useful for large control sets, quick re-selection, and grouped picks.",
    ],
    media.selector_image,
)

select_hierarchy_tooltip_text = (
    "Select Hierarchy",
    [
        "Select the descending hierarchy from the current selection.",
        "Useful for FK chains, finger sets, and grouped rig controls.",
    ],
    media.select_hierarchy_image,
)

animation_offset_tooltip_text = (
    "Animation Offset",
    [
        "Offset the position of animated objects without destroying their existing motion.",
        "The offset propagates across the full animation range for the selected controls.",
        movie.animation_offset,
        separator,
        "Tip: You can select a time range to offset only inside that range.",
    ],
    media.animation_offset_image,
)

link_objects_tooltip_text = (
    "Link Objects",
    [
        "Save and restore parent-style relationships without creating constraints.",
        "Useful for quick object linking, relinking, and lightweight follow setups.",
        "Right-click for copy, paste, and auto-link options.",
    ],
    media.link_objects_image,
)

copy_link_tooltip_text = (
    "Copy Link Position",
    ["Save the current relative relationship from the selected objects."],
    media.link_objects_copy_image,
)

follow_cam_tooltip_text = (
    "Follow Cam",
    [
        "Create a camera that follows the selected object.",
        "Useful for editing moving animation while keeping the subject visually stable in frame.",
    ],
    media.follow_cam_image,
)

copy_worldspace_tooltip_text = tool_tooltip(
    "Copy World Space",
    ["Copy the world-space transform of the current selection at the current frame."],
    media.worldspace_copy_frame_image,
)

copy_worldspace_range_tooltip_text = tool_tooltip(
    "Copy World Space - Selected Range",
    ["Copy world-space transforms across the selected time range or full animation."],
    media.worldspace_copy_animation_image,
)

paste_worldspace_tooltip_text = tool_tooltip(
    "Paste World Space",
    ["Paste the saved world-space transform onto the current frame."],
    media.worldspace_paste_frame_image,
)

paste_worldspace_animation_tooltip_text = tool_tooltip(
    "Paste World Space - All Animation",
    ["Paste saved world-space transforms across a selected range or the full animation."],
    media.worldspace_paste_animation_image,
)

temp_pivot_tooltip_text = (
    "Temp Pivot",
    [
        "Create temporary pivots without changing the original pivot or adding constraints.",
        "Useful for one-off rotations, arcs, and posing adjustments.",
    ],
    media.temp_pivot_image,
)


micro_move_tooltip_text = (
    "Micro Move",
    [
        "Move and rotate controls at a much slower rate for precision adjustments.",
        "Especially useful for facial work and fine control tweaks.",
        "Works with rotations in Gimbal mode and translations in Local or World mode.",
    ],
    media.ruler_image,
)

temp_pivot_last_tooltip_text = (
    "Use Last Pivot",
    [
        "Recreate the most recently used Temp Pivot setup on the current selection.",
        "Useful when repeating the same pivot placement across several controls.",
    ],
    media.temp_pivot_use_last_image,
)

remove_inbetween_tooltip_text = (
    "Remove Inbetween",
    ["Remove inbetweens using the current nudge step value."],
    media.remove_inbetween_image,
)

insert_inbetween_tooltip_text = (
    "Insert Inbetween",
    ["Insert inbetweens using the current nudge step value."],
    media.insert_inbetween_image,
)

static_tooltip_text = (
    "Delete Static Keys",
    ["Flatten the selected curve so it holds the value of its first selected key.", movie.delete_all_animation_static],
    media.delete_animation_image,
)

match_keys_tooltip_text = (
    "Match",
    ["Match one selected curve to another so both curves share the same values."],
    media.match_image,
)

flip_tooltip_text = (
    "Flip",
    ["Invert the selected curve values vertically."],
    media.asset_path("flip_curve_image"),
)

snap_tooltip_text = (
    "Snap",
    ["Snap selected sub-frame keys to the nearest whole frame."],
)

overlap_tooltip_text = (
    "Overlap",
    ["Offset the selected curves to create overlapping motion."],
)

align_translation_tooltip_text = (
    "Align Translation",
    ["Match only translation from the driver object to the target object."],
    media.align_menu_image,
)

align_rotation_tooltip_text = (
    "Align Rotation",
    ["Match only rotation from the driver object to the target object."],
    media.align_menu_image,
)

align_scale_tooltip_text = (
    "Align Scale",
    ["Match only scale from the driver object to the target object."],
    media.align_menu_image,
)

tracer_refresh_tooltip_text = (
    "Refresh Tracer",
    ["Refresh the current tracer without rebuilding the setup."],
    media.refresh_image,
)

tracer_toggle_tooltip_text = (
    "Toggle Tracer",
    ["Show or hide the existing tracer display."],
    media.tracer_show_hide_image,
)

tracer_remove_tooltip_text = (
    "Remove Tracer",
    ["Remove the active tracer setup from the scene."],
    media.remove_image,
)

reset_translations_tooltip_text = (
    "Reset Translation",
    ["Reset only translation values on the current selection."],
    media.asset_path("reset_animation_image"),
)

reset_rotations_tooltip_text = (
    "Reset Rotation",
    ["Reset only rotation values on the current selection."],
    media.asset_path("reset_animation_image"),
)

reset_scales_tooltip_text = (
    "Reset Scales",
    ["Reset only scale values on the current selection."],
    media.asset_path("reset_animation_image"),
)

reset_trs_tooltip_text = (
    "Reset Translation Rotation Scale",
    ["Reset translation, rotation, and scale values on the current selection."],
    media.asset_path("reset_animation_image"),
)

quick_export_selection_sets_tooltip_text = (
    "Quick Export",
    ["Export selection sets to the shared quick file, overwriting the previous quick-export data."],
    media.selection_sets_export_image,
)

quick_import_selection_sets_tooltip_text = (
    "Quick Import",
    ["Import selection sets from the shared quick file."],
    media.selection_sets_import_image,
)

export_selection_sets_tooltip_text = (
    "Export Selection Sets",
    ["Export selection sets to a chosen file."],
    media.selection_sets_export_image,
)

import_selection_sets_tooltip_text = (
    "Import Selection Sets",
    ["Import selection sets from a chosen file."],
    media.selection_sets_import_image,
)

clear_selection_sets_tooltip_text = (
    "Clear All Selection Sets",
    ["Delete every saved selection set in the current scene."],
    media.trash_image,
)

extra_tools_tooltip_text = (
    "Extra Tools",
    ["Open additional curve utilities used for cleanup and adjustment work."],
)

paste_pose_tooltip_text = (
    "Paste Pose",
    ["Paste the saved pose onto the current selection."],
    media.paste_pose_image,
)

paste_opposite_animation_tooltip_text = (
    "Paste Opposite Animation",
    ["Paste the saved animation onto the opposite-side controls."],
    media.paste_opposite_animation_image,
)

follow_translation_tooltip_text = (
    "Follow Translation",
    ["Create a Follow Cam that inherits only translation from the selected object."],
    media.follow_cam_image,
)

follow_rotation_tooltip_text = (
    "Follow Rotation",
    ["Create a Follow Cam that inherits only rotation from the selected object."],
    media.follow_cam_image,
)

remove_follow_cam_tooltip_text = (
    "Remove Follow Cam",
    ["Remove the current Follow Cam setup."],
    media.remove_image,
)

paste_link_tooltip_text = (
    "Paste Link Position",
    ["Apply the saved link relationship to the current selection."],
    media.link_objects_paste_image,
)

graph_isolate_curves_tooltip_text = (
    "Isolate Curves",
    ["Show only the selected curves in the Graph Editor."],
    media.isolate_image,
)

graph_mute_tooltip_text = (
    "Mute Curves",
    ["Toggle mute on the selected curves."],
)

graph_lock_tooltip_text = (
    "Lock Curves",
    ["Toggle lock on the selected curves."],
)

graph_filter_tooltip_text = (
    "Filter",
    [
        "Filter the Graph Editor to the current selection.",
        "Use the alternate action to clear the filter when needed.",
    ],
)

graph_reset_tooltip_text = (
    "Reset Curves",
    ["Reset the selected curves to their default values."],
    media.asset_path("reset_animation_image"),
)

tangent_cycle_matcher_tooltip_text = (
    "Cycle Matcher",
    ["Match the selected curve ends for cleaner cyclic animation."],
    media.match_curve_cycle_image,
)

tangent_bouncy_tooltip_text = (
    "Bouncy Tangent",
    ["Set the selected curves to a bouncy tangent style."],
    media.bouncy_tangent_image,
)


selection_sets_tooltip_text = (
    "Selection Sets",
    [
        "Save and recall useful selections from a floating panel.",
        "Use color-coded sets to organize character picks, shot-specific groups, and quick imports or exports.",
    ],
    media.selection_sets_image,
)

customGraph_tooltip_text = (
    "Graph Editor Toolbar",
    [
        "Toggle the automatic TKM toolbar inside Maya's Graph Editor.",
        "This button manages the saved preference only; it does not open the Graph Editor itself.",
    ],
    media.customGraph_image,
)

custom_tools_tooltip_text = (
    "Custom Tools",
    [
        "Open your custom pipeline tool shortcuts from a single menu.",
        "Configure these entries carefully to avoid broken tool definitions.",
    ],
    media.custom_tools_image,
)

custom_scripts_tooltip_text = (
    "Custom Scripts",
    [
        "Open your personal and third-party script shortcuts from one menu.",
        "Useful when you want quick access without relying on Maya shelves.",
    ],
    media.custom_scripts_image,
)
