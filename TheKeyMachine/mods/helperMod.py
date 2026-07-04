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

from TheKeyMachine.data import icons, movies as movie
from TheKeyMachine.mods.tooltipsMod import separator, tool_tooltip


# ----------------------------------------------  TOOLTIPS  --------------------------------------------------------


# -------- KeyBox


nudge_left_tooltip_text = tool_tooltip(
    None,
    ["Nudge the current keyframes or tangents by the number of frames specified in the central box.",
    movie.nudge],
)


remove_inbetween_tooltip_text = tool_tooltip(
    None,
    ["Remove inbetweens using the current nudge step value."],
)


move_keyframes_intField_widget_tooltip_text = tool_tooltip(
    None,
    ["Set the number of frames to move when using the Nudge tool."],
)

insert_inbetween_tooltip_text = tool_tooltip(
    None,
    ["Add inbetweens using the current nudge step value.."],
)


nudge_right_tooltip_text = tool_tooltip(
    None,
    ["Nudge the current keyframes or tangents by the number of frames specified in the central box.",
    movie.nudge],
)


clear_selected_keys_widget_tooltip_text = tool_tooltip(
    None,
    [
        "When you select a range in the Time Slider and use the nudge tools, the keys in that range are selected automatically.",
        "Use this to clear that key selection so you can go back to nudging a single frame.",
    ],
)


select_scene_animation_widget_tooltip_text = tool_tooltip(
    None,
    [
        "Select all animation curves in the scene.",
        "Useful when you want to move all animation with the nudge tools.",
        "Select the curves, set the frame offset, then use Nudge Keys Left or Nudge Keys Right.",
    ],
)


# ------ Sliders


blend_tooltip_text = tool_tooltip(
    None,
    [
        "Blend between neighboring keyframe values.",
        "Select channels in the Channel Box to affect only those channels.",
    ],
)

connect_neighbors_tooltip_text = tool_tooltip(
    None,
    [
        "Connects a section of animation to a neighbor pose.",
        "Go to the first or last frame of the section you want to connect and nudge the slider.",
        "You can also select a specific range of keys.",
    ],
)

blend_to_default_tooltip_text = tool_tooltip(
    None,
    ["Blend the current value toward its default value."],
)

blend_to_frame_tooltip_text = tool_tooltip(
    None,
    [
        "Each button stores the current frame when pressed.",
        "The blend slider then blends between the stored frames.",
    ],
)

pull_push_tooltip_text = tool_tooltip(
    None,
    ["Soften or intensify the animation."],
)

tweener_tooltip_text = tool_tooltip(
    None,
    [
        "Tween between the previous and next keyframe.",
        "Select channels in the Channel Box to affect only those channels.",
    ],
)

tweener_world_space_tooltip_text = tool_tooltip(
    None,
    ["Tween between the previous and next keyframe in world space."],
)


# ----- Tangent


auto_tangent_tooltip_text = tool_tooltip(
    None,
    ["Set the tangents of the selected keyframes to Auto."],
    icons.tangent_auto,
)

spline_tangent_tooltip_text = tool_tooltip(
    None,
    ["Set the tangents of the selected keyframes to Spline."],
    icons.tangent_spline,
)

clamped_tangent_tooltip_text = tool_tooltip(
    None,
    ["Set the tangents of the selected keyframes to Clamped."],
    icons.tangent_clamped,
)

linear_tangent_tooltip_text = tool_tooltip(
    None,
    ["Set the tangents of the selected keyframes to Linear."],
    icons.tangent_linear,
)

flat_tangent_tooltip_text = tool_tooltip(
    None,
    ["Set the tangents of the selected keyframes to Flat."],
    icons.tangent_flat,
)

step_tangent_tooltip_text = tool_tooltip(
    None,
    ["Set the tangents of the selected keyframes to Stepped."],
    icons.tangent_step,
)

plateau_tangent_tooltip_text = tool_tooltip(
    None,
    ["Set the tangents of the selected keyframes to Plateau."],
    icons.tangent_plateau,
)


# ----- ReBlock, ShareKeys, BakeKeys

reblock_move_tooltip_text = tool_tooltip(
    None,
    [
        "reBlock helps you place animation keys back onto the intended main poses.",
        "Useful when timing adjustments have left channels keyed on inconsistent frames.",
        movie.reblock
    ],
    icons.reblock,
)

bake_animation_4_tooltip_text = tool_tooltip(
    None,
    [
        "Bake the selected animation using 4-frame steps.",
        "Useful for stepped blocking passes or reducing key density while keeping pose timing readable.",
    ],
    icons.bake_animation_3,
)


bake_animation_custom_tooltip_text = tool_tooltip(
    None,
    [
        "Bake the selected animation using a custom frame interval.",
        "Useful for stepped blocking passes or custom sampling density.",
    ],
    icons.bake_animation_custom,
)

bake_animation_1_tooltip_text = tool_tooltip(
    None,
    ["Bake the selected animation on every frame."],
    icons.bake_animation_1,
)

bake_animation_2_tooltip_text = tool_tooltip(
    None,
    ["Bake the selected animation every two frames."],
    icons.bake_animation_2,
)

bake_animation_3_tooltip_text = tool_tooltip(
    None,
    ["Bake the selected animation every three frames."],
    icons.bake_animation_3,
)


gimbal_fixer_tooltip_text = tool_tooltip(
    None,
    [
        "Change rotation order without changing the visible animation result.",
        "Useful when a control is suffering from gimbal lock and needs a safer rotate order.",
    ],
    icons.reblock,
)

share_keys_tooltip_text = tool_tooltip(
    None,
    [
        "Share keyframe times across the selected channels or objects.",
        "Useful for aligning blocking keys across controls while preserving their values.",
        movie.share_keys,
        separator,
        "Tip: Select a range in the time slider to limit the operation to that range.",
    ],
    icons.share_keys,
)

orbit_tooltip_text = tool_tooltip(
    None,
    [
        "Open the floating quick-access panel for your most-used animation tools.",
        "Configure which actions appear in it and keep it close to the main toolbar while animating.",
    ],
    icons.orbit_ui,
)

donate_tooltip_text = tool_tooltip(
    None,
    [
        "Support the development of TheKeyMachine.",
        "The KeyMachine is free to use and always will be.",
        "Any support is greatly appreciated!",
    ],
    icons.donate,
)

attribute_switcher_tooltip_text = tool_tooltip(
    None,
    [
        "Open the floating Attribute Switcher for the current selection.",
        "Useful for switch attributes, rotate-order changes, and current-frame or all-keys switching.",
    ],
    icons.attribute_switcher,
)


# ----- Pointer


select_rig_controls_tooltip_text = tool_tooltip(
    None,
    [
        "Will select all the controls of a rig hierarchy.",
        "Only NURBS-curve controls are included.",
    ],
    icons.select_rig_controls,
)

select_rig_controls_animated_tooltip_text = tool_tooltip(
    None,
    [
        "Select only rig controls that currently have animation.",
        "Only NURBS-curve controls are included.",
    ],
    icons.select_rig_controls_animated,
)

depth_mover_tooltip_text = tool_tooltip(
    None,
    ["Adjust object depth without changing its apparent camera-space framing."],
    icons.depth_mover,
)


# ----- Isolate


isolate_tooltip_text = tool_tooltip(
    None,
    [
        "Isolate a character or asset by simply selecting a control.",
        "Useful for working on one or more characters without scene clutter.",
        "You can isolate several characters at once by selecting multiple controls from different characters or assets.",
        movie.isolate,
        separator,
        "Tip: If your characters or assets are within a node, for example, all characters are inside a group called \"characters\", use the \"Down one level\" option in the dropdown menu."
    ],
    icons.isolate,
)


isolate_bookmarks_window_tooltip_text = tool_tooltip(
    None,
    [
        "Save groups of isolates so that you can quickly change what you see in a viewport."
        "This is ideal when you have multiple characters interacting with multiple elements.",
        movie.isolate,
        separator,
        "All bookmarks appear in the dropdown menu of the \"Isolate\" button."
    ],
)


createLocator_tooltip_text = tool_tooltip(
    None,
    [
        "Create temporary locators from the current selection.",
        "Useful for marking positions or building quick references during blocking and cleanup.",
    ],
    icons.cube,
)

align_tooltip_text = tool_tooltip(
    None,
    [
        "This tool allows aligning one object with another.",
        "By default, this tool aligns in all modes.",
        movie.align_objects,
        separator,
        "When you select a range on the Time Slider, the alignment is carried out over that range.",
        movie.align_objects_range,
        separator,
        "Tip: Right-click to access the alignment options.",
    ],
    icons.align,
)

tracer_tooltip_text = tool_tooltip(
    None,
    [
        "Draw a trace for the path of a moving object.",
        "When the tracer is deactivated, there are no ongoing calculations.",
        movie.tracer,
        separator,
        "Tip: Use \"Refresh Tracer\" to update the motion trail without having to activate it.",
    ],
    icons.tracer,
)

tracer_refresh_tooltip_text = tool_tooltip(
    None,
    ["Refresh the current tracer without rebuilding the setup."],
    icons.refresh,
)

tracer_toggle_tooltip_text = tool_tooltip(
    None,
    ["Show or hide the existing tracer display."],
    icons.tracer_show_hide,
)

tracer_offset_tooltip_text = tool_tooltip(
    None,
    ["Select the tracer offset object so you can move or adjust the whole trail display."],
    icons.tracer_select_offset,
)

tracer_grey_tooltip_text = tool_tooltip(
    None,
    ["Set the active tracer trail to the grey display style."],
    icons.tracer_grey,
)

tracer_red_tooltip_text = tool_tooltip(
    None,
    ["Set the active tracer trail to the red display style."],
    icons.tracer_red,
)

tracer_blue_tooltip_text = tool_tooltip(
    None,
    ["Set the active tracer trail to the blue display style."],
    icons.tracer_blue,
)

tracer_remove_tooltip_text = tool_tooltip(
    None,
    ["Remove the active tracer setup from the scene."],
    icons.remove,
)

tracer_connected_tooltip_text = tool_tooltip(
    None,
    ["Keep the tracer connected so the trail updates live while the animation changes."],
    icons.tracer,
)

default_values_tooltip_text = tool_tooltip(
    None,
    [
        "Reset objects, attributes or keys to their default values.",
        movie.default_values,
        separator,
        "Tip: Select channels in the Channel Box to default only specific attributes.",
    ],
    icons.default,
)

delete_animation_tooltip_text = tool_tooltip(
    None,
    [
        "Delete animation from the current selection.",
        "Select channels in the Channel Box to limit the deletion to specific attributes.",
        movie.delete_all_animation,
        separator,
        "Tip: You can select a time range to delete keys only inside that range.",
        movie.delete_all_animation_selection,
    ],
    icons.delete_animation,
)


opposite_select_tooltip_text = tool_tooltip(
    None,
    [
        "Select the opposite-side control for the current rig selection.",
        "Works with one or more selected controls.",
    ],
    icons.opposite_select,
)

opposite_add_tooltip_text = tool_tooltip(
    None,
    ["Add the opposite-side control to the current selection."],
    icons.opposite_select,
)

opposite_copy_tooltip_text = tool_tooltip(
    None,
    [
        "Copy current values from the selected controls to their opposite-side controls.",
        "Mirror exceptions affect how opposite mapping is resolved.",
    ],
    icons.opposite_copy,
)

mirror_tooltip_text = tool_tooltip(
    None,
    [
        "Mirror the selected controls to their opposite-side equivalents.",
        "Mirror exceptions can be configured per rig and are saved for reuse.",
    ],
    icons.mirror,
)

mirror_to_right_tooltip_text = tool_tooltip(
    None,
    [
        "Copy current mirrored values from selected left-side controls to their right-side opposites.",
        "Invert exceptions multiply saved channels by -1 before writing them to the opposite control.",
    ],
    icons.mirror,
)

mirror_to_left_tooltip_text = tool_tooltip(
    None,
    [
        "Copy current mirrored values from selected right-side controls to their left-side opposites.",
        "Invert exceptions multiply saved channels by -1 before writing them to the opposite control.",
    ],
    icons.mirror,
)

mirror_all_keys_tooltip_text = tool_tooltip(
    None,
    [
        "Copy all keyed animation from selected controls to their opposite-side controls.",
        "Existing keys on the destination channels are replaced, and mirror exceptions are applied per channel.",
    ],
    icons.mirror,
)

mirror_add_invert_tooltip_text = tool_tooltip(
    None,
    [
        "Save an Invert exception for the selected controls and Channel Box attributes.",
        "When Mirror or Paste Opposite uses this channel, the value is multiplied by -1.",
        "Use this for attributes that should flip sign across the rig side.",
    ],
    icons.mirror,
)

mirror_add_keep_tooltip_text = tool_tooltip(
    None,
    [
        "Save a Keep exception for the selected controls and Channel Box attributes.",
        "When Mirror swaps opposite controls, this channel keeps its value instead of being sign-flipped.",
        "Use this for attributes that should transfer unchanged across the rig side.",
    ],
    icons.mirror,
)

mirror_remove_exception_tooltip_text = tool_tooltip(
    None,
    [
        "Remove saved mirror exceptions from the selected controls and Channel Box attributes.",
        "After removal, those channels go back to the default mirror behavior.",
    ],
    icons.mirror,
)

copy_animation_tooltip_text = tool_tooltip(
    None,
    [
        "Copy animation from the selected objects or controls.",
        "The copied data is stored on disk so it can be pasted in another Maya session.",
    ],
    icons.copy_animation,
)

paste_animation_tooltip_text = tool_tooltip(
    None,
    ["Paste the saved animation onto the current selection."],
    icons.paste_animation,
)

paste_insert_animation_tooltip_text = tool_tooltip(
    None,
    ["Insert the saved animation while preserving surrounding timing."],
    icons.paste_insert_animation,
)

copy_pose_tooltip_text = tool_tooltip(
    None,
    [
        "Copy the current pose from the selected controls.",
        "The pose can be pasted later in the same scene or another Maya session.",
    ],
    icons.copy_pose,
)


selector_tooltip_text = tool_tooltip(
    None,
    [
        "Open a window showing the current selection as an easy-to-manage list.",
        "Useful for large control sets, quick re-selection, and grouped picks.",
    ],
    icons.selector,
)

select_hierarchy_tooltip_text = tool_tooltip(
    None,
    [
        "Select the descending hierarchy from the current selection.",
        "Useful for FK chains, finger sets, and grouped rig controls.",
        movie.select_hierarchy,
        separator,
        "Note: This tool may fail on certain occasions since some rigs are not created following standards.",
    ],
    icons.select_hierarchy,
)

animation_offset_tooltip_text = tool_tooltip(
    None,
    [
        "Offset the position of animated objects without destroying their existing motion.",
        "The offset propagates across the full animation range for the selected controls.",
        movie.animation_offset,
        separator,
        "Tip: You can select a time range to offset only inside that range.",
    ],
    icons.animation_offset,
)

link_objects_tooltip_text = tool_tooltip(
    None,
    [
        "Save the relationship between several objects and apply it back when needed."
        "Link objects is like using parent constraints without constraints.",
        movie.link_objects,
        separator,
        "Relationships are saved, so they can be used across different Maya sessions.",
        "Tip: Use the \"Auto Link\" option to update the object relationship in real-time."
    ],
    icons.link_relative,
)

paste_link_tooltip_text = tool_tooltip(
    None,
    ["Apply the saved link relationship to the current selection."],
    icons.link_relative_paste,
)

auto_link_tooltip_text = tool_tooltip(
    None,
    ["Toggle automatic pasting of link relationships.", movie.link_objects_auto_link],
    icons.link_relative_on,
)

follow_cam_tooltip_text = tool_tooltip(
    None,
    [
        "FollowCam creates a camera that will follow the selected object.",
        "By default, FollowCam tracks both translations and rotations.",
        "It's useful when you need to make changes to the animation of an object that is moving, this way the object will remain static in the camera's view.",
        movie.follow_cam,
        separator,
        "Tip: Right-click on the tool icon to create FollowCam for translations only or for rotations only.",
    ],
    icons.follow_cam,
)

copy_worldspace_tooltip_text = tool_tooltip(
    None,
    ["Copy the world-space transform of the current selection at the current frame."],
    icons.worldspace_copy_frame,
)

copy_worldspace_range_tooltip_text = tool_tooltip(
    None,
    ["Copy world-space transforms across the selected time range or full animation."],
    icons.worldspace_copy_animation,
)

paste_worldspace_tooltip_text = tool_tooltip(
    None,
    ["Paste the saved world-space transform onto the current frame."],
    icons.worldspace_paste_frame,
)

paste_worldspace_animation_tooltip_text = tool_tooltip(
    None,
    ["Paste saved world-space transforms across a selected range or the full animation."],
    icons.worldspace_paste_animation,
)

temp_pivot_tooltip_text = tool_tooltip(
    None,
    [
        "Create temporary pivots without adding constraints.",
        movie.temp_pivot,
        separator,
        "Temp pivots can be applied to multiple objects at once and are destroyed when selection is changed.",
        movie.temp_pivot_chain,
        separator,
        "Tip: Useful for swinging bodies animation, arcs, posing...",
    ],
    icons.temp_pivot,
)


micro_move_tooltip_text = tool_tooltip(
    None,
    [
        "Move and rotate controls at a much slower rate for precision adjustments.",
        "Especially useful for facial work and fine control tweaks.",
        "Works with rotations in Gimbal mode and translations in Local or World mode.",
    ],
    icons.ruler,
)

temp_pivot_last_object_tooltip_text = tool_tooltip(
    None,
    [
        "Create a Temp Pivot aligned to the last selected object's transform.",
    ],
    icons.temp_pivot,
)

temp_pivot_centered_tooltip_text = tool_tooltip(
    None,
    [
        "Create a Temp Pivot at the average world transform position of the selected objects.",
    ],
    icons.temp_pivot,
)

temp_pivot_worldspace_tooltip_text = tool_tooltip(
    None,
    [
        "Create a Temp Pivot that stays at its creation position when time changes.",
    ],
    icons.globe,
)

temp_pivot_edit_tooltip_text = tool_tooltip(
    None,
    [
        "Enter Maya edit-pivot manipulator mode for the current Temp Pivot.",
    ],
    icons.temp_pivot,
)

temp_pivot_reset_tooltip_text = tool_tooltip(
    None,
    [
        "Return the active Temp Pivot to the placement mode used when it was created.",
    ],
    icons.refresh,
)

remove_inbetween_tooltip_text = tool_tooltip(
    None,
    ["Remove inbetweens using the current nudge step value."],
    icons.nudge_remove_inbetween,
)

insert_inbetween_tooltip_text = tool_tooltip(
    None,
    ["Insert inbetweens using the current nudge step value."],
    icons.nudge_insert_inbetween,
)

delete_static_animation_tooltip_text = tool_tooltip(
    None,
    [
        "These are the curves that have keys but where all the key values are the same, meaning there is no movement.",
        movie.delete_all_animation_static,
    ],
    icons.delete_animation,
)

graph_match_keys_tooltip_text = tool_tooltip(
    None,
    ["Match one selected curve to another so both curves share the same values."],
    icons.align,
)

flip_tooltip_text = tool_tooltip(
    None,
    [
        "Invert the selected curve values vertically.",
        movie.flip,
    ],
    icons.flip_curve,
)

snap_tooltip_text = tool_tooltip(
    None,
    [
        "Snap selected sub-frame keys to the nearest whole frame.",
        "It doesn't just reposition the keyframes, it creates them on the nearest frame and removes all the keyframes that are off a frame.",
        "This way, the existing animation remains intact.",
        movie.snap,
        separator,
        "Note: Maya fails to apply snap and reports an error, whereas TKM applies the snap without any issues.",
    ],
    icons.snap,
)

overlap_tooltip_text = tool_tooltip(
    None,
    [
        "Offset the selected curves to create overlapping motion.",
        movie.overlap,
    ],
    icons.overlap,
)

align_translation_tooltip_text = tool_tooltip(
    None,
    ["Match only translation from the driver object to the target object."],
    icons.align,
)

align_rotation_tooltip_text = tool_tooltip(
    None,
    ["Match only rotation from the driver object to the target object."],
    icons.align,
)

align_scale_tooltip_text = tool_tooltip(
    None,
    ["Match only scale from the driver object to the target object."],
    icons.align,
)

default_translations_tooltip_text = tool_tooltip(
    None,
    ["Reset only translation values on the current selection."],
    icons.default,
)

default_rotations_tooltip_text = tool_tooltip(
    None,
    ["Reset only rotation values on the current selection."],
    icons.default,
)

default_scales_tooltip_text = tool_tooltip(
    None,
    ["Reset only scale values on the current selection."],
    icons.default,
)

default_trs_tooltip_text = tool_tooltip(
    None,
    ["Reset translation, rotation, and scale values on the current selection."],
    icons.default,
)

quick_export_selection_sets_tooltip_text = tool_tooltip(
    None,
    ["Export selection sets to the shared quick file, overwriting the previous quick-export data."],
    icons.selection_sets_export,
)

quick_import_selection_sets_tooltip_text = tool_tooltip(
    None,
    ["Import selection sets from the shared quick file."],
    icons.selection_sets_import,
)

export_selection_sets_tooltip_text = tool_tooltip(
    None,
    ["Export selection sets to a chosen file."],
    icons.selection_sets_export,
)

import_selection_sets_tooltip_text = tool_tooltip(
    None,
    ["Import selection sets from a chosen file."],
    icons.selection_sets_import,
)

clear_selection_sets_tooltip_text = tool_tooltip(
    None,
    ["Delete every saved selection set in the current scene."],
    icons.trash,
)

extra_tools_tooltip_text = tool_tooltip(
    None,
    ["Open additional curve utilities used for cleanup and adjustment work."],
)

paste_pose_tooltip_text = tool_tooltip(
    None,
    ["Paste the saved pose onto the current selection."],
    icons.paste_pose,
)

paste_opposite_animation_tooltip_text = tool_tooltip(
    None,
    ["Paste the saved animation onto the opposite-side controls."],
    icons.paste_opposite_animation,
)

follow_translation_tooltip_text = tool_tooltip(
    None,
    ["Create a Follow Cam that inherits only translation from the selected object."],
    icons.follow_cam,
)

follow_rotation_tooltip_text = tool_tooltip(
    None,
    ["Create a Follow Cam that inherits only rotation from the selected object."],
    icons.follow_cam,
)

remove_follow_cam_tooltip_text = tool_tooltip(
    None,
    ["Remove the current Follow Cam setup."],
    icons.remove,
)

graph_isolate_curves_tooltip_text = tool_tooltip(
    None,
    ["Show only the selected curves in the Graph Editor.",
    movie.isolate_curves],
    icons.isolate,
)

graph_mute_tooltip_text = tool_tooltip(
    None,
    ["Toggle mute on the selected curves.",
    movie.mute_curves],
)

graph_lock_tooltip_text = tool_tooltip(
    None,
    ["Toggle lock on the selected curves.",
    movie.lock_curves],
)

graph_filter_tooltip_text = tool_tooltip(
    None,
    [
        "Filter the Graph Editor to the current selection.",
        "Use the alternate action to clear the filter when needed.",
    ],
)

graph_default_tooltip_text = tool_tooltip(
    None,
    ["Reset the selected curves to their default values."],
    icons.default,
)

tangent_cycle_matcher_tooltip_text = tool_tooltip(
    None,
    ["Match the selected curve ends for cleaner cyclic animation."],
    icons.match_curve_cycle,
)

tangent_bouncy_tooltip_text = tool_tooltip(
    None,
    ["Set the selected curves to a bouncy tangent style."],
    icons.tangent_bouncy,
)


selection_sets_tooltip_text = tool_tooltip(
    None,
    [
        "Save and recall useful selections from a floating panel.",
        "Use color-coded sets to organize character picks, shot-specific groups, and quick imports or exports.",
    ],
    icons.selection_sets,
)

customGraph_tooltip_text = tool_tooltip(
    None,
    [
        "Toggle the automatic TKM toolbar inside Maya's Graph Editor.",
        "This button manages the saved preference only; it does not open the Graph Editor itself.",
    ],
    icons.customGraph,
)

custom_tools_tooltip_text = tool_tooltip(
    None,
    [
        "Open your custom pipeline tool shortcuts from a single menu.",
        "Configure these entries carefully to avoid broken tool definitions.",
    ],
    icons.tools_folder,
)

custom_scripts_tooltip_text = tool_tooltip(
    None,
    [
        "Open your personal and third-party script shortcuts from one menu.",
        "Useful when you want quick access without relying on Maya shelves.",
    ],
    icons.scripts_folder,
)
