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

from TheKeyMachine.data import movies as movie
from TheKeyMachine.mods.tooltipsMod import separator


# ----------------------------------------------  TOOLTIPS  --------------------------------------------------------


# -------- KeyBox


nudge_left_tooltip_text = [
    "Nudge the current keyframes or tangents by the number of frames specified in the central box.",
    movie.nudge,
]


remove_inbetween_tooltip_text = [
    "Remove inbetweens using the current nudge step value.",
]


move_keyframes_intField_widget_tooltip_text = [
    "Set the number of frames to move when using the Nudge tool.",
]

insert_inbetween_tooltip_text = [
    "Add inbetweens using the current nudge step value..",
]


nudge_right_tooltip_text = [
    "Nudge the current keyframes or tangents by the number of frames specified in the central box.",
    movie.nudge,
]


clear_selected_keys_widget_tooltip_text = [
    "When you select a range in the Time Slider and use the nudge tools, the keys in that range are selected automatically.",
    "Use this to clear that key selection so you can go back to nudging a single frame.",
]


select_scene_animation_widget_tooltip_text = [
    "Select all animation curves in the scene.",
    "Useful when you want to move all animation with the nudge tools.",
    "Select the curves, set the frame offset, then use Nudge Keys Left or Nudge Keys Right.",
]


# ------ Sliders


blend_tooltip_text = [
    "Blend between neighboring keyframe values.",
    "Select channels in the Channel Box to affect only those channels.",
]

connect_neighbors_tooltip_text = [
    "Connects a section of animation to a neighbor pose.",
    "Go to the first or last frame of the section you want to connect and nudge the slider.",
    "You can also select a specific range of keys.",
]

blend_to_default_tooltip_text = [
    "Blend the current value toward its default value.",
]

blend_to_frame_tooltip_text = [
    "Each button stores the current frame when pressed.",
    "The blend slider then blends between the stored frames.",
]

pull_push_tooltip_text = [
    "Soften or intensify the animation.",
]

tweener_tooltip_text = [
    "Tween between the previous and next keyframe.",
    "Select channels in the Channel Box to affect only those channels.",
]

tweener_world_space_tooltip_text = [
    "Tween between the previous and next keyframe in world space.",
]


# ----- Tangent


auto_tangent_tooltip_text = [
    "Set the tangents of the selected keyframes to Auto.",
]

spline_tangent_tooltip_text = [
    "Set the tangents of the selected keyframes to Spline.",
]

clamped_tangent_tooltip_text = [
    "Set the tangents of the selected keyframes to Clamped.",
]

linear_tangent_tooltip_text = [
    "Set the tangents of the selected keyframes to Linear.",
]

flat_tangent_tooltip_text = [
    "Set the tangents of the selected keyframes to Flat.",
]

step_tangent_tooltip_text = [
    "Set the tangents of the selected keyframes to Stepped.",
]

plateau_tangent_tooltip_text = [
    "Set the tangents of the selected keyframes to Plateau.",
]


# ----- ReBlock, ShareKeys, BakeKeys

reblock_move_tooltip_text = [
    "reBlock helps you place animation keys back onto the intended main poses.",
    "Useful when timing adjustments have left channels keyed on inconsistent frames.",
    movie.reblock,
]

bake_animation_4_tooltip_text = [
    "Bake the selected animation using 4-frame steps.",
    "Useful for stepped blocking passes or reducing key density while keeping pose timing readable.",
]


bake_animation_custom_tooltip_text = [
    "Bake the selected animation using a custom frame interval.",
    "Useful for stepped blocking passes or custom sampling density.",
]

bake_animation_1_tooltip_text = [
    "Bake the selected animation on every frame.",
]

bake_animation_from_last_selected_tooltip_text = [
    "Bake the target objects using the key times from the last selected object.",
    "Select the objects to bake first, then select the timing source last.",
]

bake_animation_2_tooltip_text = [
    "Bake the selected animation every two frames.",
]

bake_animation_3_tooltip_text = [
    "Bake the selected animation every three frames.",
]


gimbal_fixer_tooltip_text = [
    "Change rotation order without changing the visible animation result.",
    "Useful when a control is suffering from gimbal lock and needs a safer rotate order.",
]

share_keys_tooltip_text = [
    "Share keyframe times across the selected channels or objects.",
    "Useful for aligning blocking keys across controls while preserving their values.",
    movie.share_keys,
    separator,
    "Tip: Select a range in the time slider to limit the operation to that range.",
]

share_keys_from_last_selected_tooltip_text = [
    "Copy the key times from the last selected object onto the target objects.",
    "Select targets first, then select the object with the timing you want to use last.",
]

orbit_tooltip_text = [
    "Open the floating quick-access panel for your most-used animation tools.",
    "Configure which actions appear in it and keep it close to the main toolbar while animating.",
]

donate_tooltip_text = [
    "Support the development of TheKeyMachine.",
    "The KeyMachine is free to use and always will be.",
    "Any support is greatly appreciated!",
]

attribute_switcher_tooltip_text = [
    "Open the floating Attribute Switcher for the current selection.",
    "Useful for switch attributes, rotate-order changes, and current-frame or all-keys switching.",
]


# ----- Pointer


select_rig_controls_tooltip_text = [
    "Will select all the controls of a rig hierarchy.",
    "Only NURBS-curve controls are included.",
]

select_rig_controls_animated_tooltip_text = [
    "Select only rig controls that currently have animation.",
    "Only NURBS-curve controls are included.",
]

depth_mover_tooltip_text = [
    "Adjust object depth without changing its apparent camera-space framing.",
]


# ----- Isolate


isolate_tooltip_text = [
    "Isolate a character or asset by simply selecting a control.",
    "Useful for working on one or more characters without scene clutter.",
    "You can isolate several characters at once by selecting multiple controls from different characters or assets.",
    movie.isolate,
    separator,
    "Tip: If your characters or assets are within a node, for example, all characters are inside a group called \"characters\", use the \"Down one level\" option in the dropdown menu.",
]


isolate_bookmarks_window_tooltip_text = [
    "Save groups of isolates so that you can quickly change what you see in a viewport."
        "This is ideal when you have multiple characters interacting with multiple elements.",
    movie.isolate,
    separator,
    "All bookmarks appear in the dropdown menu of the \"Isolate\" button.",
]


createLocator_tooltip_text = [
    "Create temporary locators from the current selection.",
    "Useful for marking positions or building quick references during blocking and cleanup.",
]

align_tooltip_text = [
    "This tool allows aligning one object with another.",
    "By default, this tool aligns in all modes.",
    movie.align_objects,
    separator,
    "When you select a range on the Time Slider, the alignment is carried out over that range.",
    movie.align_objects_range,
    separator,
    "Tip: Right-click to access the alignment options.",
]

tracer_tooltip_text = [
    "Draw a trace for the path of a moving object.",
    "When the tracer is deactivated, there are no ongoing calculations.",
    movie.tracer,
    separator,
    "Tip: Use \"Refresh Tracer\" to update the motion trail without having to activate it.",
]

tracer_refresh_tooltip_text = [
    "Refresh the current tracer without rebuilding the setup.",
]

tracer_toggle_tooltip_text = [
    "Show or hide the existing tracer display.",
]

tracer_offset_tooltip_text = [
    "Select the tracer offset object so you can move or adjust the whole trail display.",
]

tracer_grey_tooltip_text = [
    "Set the active tracer trail to the grey display style.",
]

tracer_red_tooltip_text = [
    "Set the active tracer trail to the red display style.",
]

tracer_blue_tooltip_text = [
    "Set the active tracer trail to the blue display style.",
]

tracer_remove_tooltip_text = [
    "Remove the active tracer setup from the scene.",
]

tracer_connected_tooltip_text = [
    "Keep the tracer connected so the trail updates live while the animation changes.",
]

default_values_tooltip_text = [
    "Reset objects, attributes or keys to their default values.",
    movie.default_values,
    separator,
    "Tip: Select channels in the Channel Box to default only specific attributes.",
]

delete_animation_tooltip_text = [
    "Delete animation from the current selection.",
    "Select channels in the Channel Box to limit the deletion to specific attributes.",
    movie.delete_all_animation,
    separator,
    "Tip: You can select a time range to delete keys only inside that range.",
    movie.delete_all_animation_selection,
]


opposite_select_tooltip_text = [
    "Select the opposite-side control for the current rig selection.",
    "Works with one or more selected controls.",
]

opposite_add_tooltip_text = [
    "Add the opposite-side control to the current selection.",
]

opposite_copy_tooltip_text = [
    "Copy current values from the selected controls to their opposite-side controls.",
    "Mirror exceptions affect how opposite mapping is resolved.",
]

mirror_tooltip_text = [
    "Mirror the selected controls to their opposite-side equivalents.",
    "Mirror exceptions can be configured per rig and are saved for reuse.",
]

mirror_to_right_tooltip_text = [
    "Copy current mirrored values from selected left-side controls to their right-side opposites.",
    "Invert exceptions multiply saved channels by -1 before writing them to the opposite control.",
]

mirror_to_left_tooltip_text = [
    "Copy current mirrored values from selected right-side controls to their left-side opposites.",
    "Invert exceptions multiply saved channels by -1 before writing them to the opposite control.",
]

mirror_all_keys_tooltip_text = [
    "Copy all keyed animation from selected controls to their opposite-side controls.",
    "Existing keys on the destination channels are replaced, and mirror exceptions are applied per channel.",
]

mirror_add_invert_tooltip_text = [
    "Save an Invert exception for the selected controls and Channel Box attributes.",
    "When Mirror or Paste Opposite uses this channel, the value is multiplied by -1.",
    "Use this for attributes that should flip sign across the rig side.",
]

mirror_add_keep_tooltip_text = [
    "Save a Keep exception for the selected controls and Channel Box attributes.",
    "When Mirror swaps opposite controls, this channel keeps its value instead of being sign-flipped.",
    "Use this for attributes that should transfer unchanged across the rig side.",
]

mirror_remove_exception_tooltip_text = [
    "Remove saved mirror exceptions from the selected controls and Channel Box attributes.",
    "After removal, those channels go back to the default mirror behavior.",
]

copy_animation_tooltip_text = [
    "Copy animation from the selected objects or controls.",
    "The copied data is stored on disk so it can be pasted in another Maya session.",
]

paste_animation_tooltip_text = [
    "Paste the saved animation onto the current selection.",
]

paste_insert_animation_tooltip_text = [
    "Insert the saved animation while preserving surrounding timing.",
]

copy_pose_tooltip_text = [
    "Copy the current pose from the selected controls.",
    "The pose can be pasted later in the same scene or another Maya session.",
]


selector_tooltip_text = [
    "Open a window showing the current selection as an easy-to-manage list.",
    "Useful for large control sets, quick re-selection, and grouped picks.",
]

select_hierarchy_tooltip_text = [
    "Select the descending hierarchy from the current selection.",
    "Useful for FK chains, finger sets, and grouped rig controls.",
    movie.select_hierarchy,
    separator,
    "Note: This tool may fail on certain occasions since some rigs are not created following standards.",
]

animation_offset_tooltip_text = [
    "Offset the position of animated objects without destroying their existing motion.",
    "The offset propagates across the full animation range for the selected controls.",
    movie.animation_offset,
    separator,
    "Tip: You can select a time range to offset only inside that range.",
]

link_objects_tooltip_text = [
    "Save the relationship between several objects and apply it back when needed."
        "Link objects is like using parent constraints without constraints.",
    movie.link_objects,
    separator,
    "Relationships are saved, so they can be used across different Maya sessions.",
    "Tip: Use the \"Auto Link\" option to update the object relationship in real-time.",
]

paste_link_tooltip_text = [
    "Apply the saved link relationship to the current selection.",
]

auto_link_tooltip_text = [
    "Toggle automatic pasting of link relationships.",
    movie.link_objects_auto_link,
]

follow_cam_tooltip_text = [
    "FollowCam creates a camera that will follow the selected object.",
    "By default, FollowCam tracks both translations and rotations.",
    "It's useful when you need to make changes to the animation of an object that is moving, this way the object will remain static in the camera's view.",
    movie.follow_cam,
    separator,
    "Tip: Right-click on the tool icon to create FollowCam for translations only or for rotations only.",
]

copy_worldspace_tooltip_text = [
    "Copy the world-space transform of the current selection at the current frame.",
]

copy_worldspace_range_tooltip_text = [
    "Copy world-space transforms across the selected time range or full animation.",
]

paste_worldspace_tooltip_text = [
    "Paste the saved world-space transform onto the current frame.",
]

paste_worldspace_animation_tooltip_text = [
    "Paste saved world-space transforms across a selected range or the full animation.",
]

temp_pivot_tooltip_text = [
    "Create temporary pivots without adding constraints.",
    movie.temp_pivot,
    separator,
    "Temp pivots can be applied to multiple objects at once and are destroyed when selection is changed.",
    movie.temp_pivot_chain,
    separator,
    "Tip: Useful for swinging bodies animation, arcs, posing...",
]


micro_move_tooltip_text = [
    "Move and rotate controls at a much slower rate for precision adjustments.",
    "Especially useful for facial work and fine control tweaks.",
    "Works with rotations in Gimbal mode and translations in Local or World mode.",
]

temp_pivot_last_object_tooltip_text = [
    "Create a Temp Pivot aligned to the last selected object's transform.",
]

temp_pivot_centered_tooltip_text = [
    "Create a Temp Pivot at the average world transform position of the selected objects.",
]

temp_pivot_worldspace_tooltip_text = [
    "Create a Temp Pivot that stays at its creation position when time changes.",
]

temp_pivot_edit_tooltip_text = [
    "Enter Maya edit-pivot manipulator mode for the current Temp Pivot.",
]

temp_pivot_reset_tooltip_text = [
    "Return the active Temp Pivot to the placement mode used when it was created.",
]

remove_inbetween_tooltip_text = [
    "Remove inbetweens using the current nudge step value.",
]

insert_inbetween_tooltip_text = [
    "Insert inbetweens using the current nudge step value.",
]

apply_smart_euler_filter_tooltip_text = [
    "Run an Euler filter on selected rotation animation curves.",
    "Use this to clean rotation flips while preserving the current key selection.",
]

clear_animation_keys_tooltip_text = [
    "Remove animation keys from the selected objects, channels, or curves.",
    "Uses the active Graph Editor selection, Channel Box selection, or Time Slider range when available.",
]

copy_keys_tooltip_text = [
    "Copy the selected animation keys.",
    "Works from Graph Editor key selections, selected channels, selected objects, or the active Time Slider range.",
]

crop_animation_tooltip_text = [
    "Keep keys inside the current time context and remove keys outside it.",
    "Use a Time Slider range or Graph Editor key selection to define the crop range.",
]

cut_keys_tooltip_text = [
    "Cut the selected animation keys and place them on Maya's key clipboard.",
    "Uses the same target rules as Copy Keys, then removes those keys from the curves.",
]

delete_keys_tooltip_text = [
    "Delete keys from the current frame, selected range, selected channels, or selected curves.",
    "Unlike Cut Keys, this clears the keys without preparing them for paste.",
]

paste_keys_tooltip_text = [
    "Paste copied keys onto the selected objects or channels.",
    "The keys merge at their stored timing unless Maya's key clipboard changes the paste behavior.",
]

paste_keys_relative_tooltip_text = [
    "Paste copied keys relative to the current frame.",
    "The first copied key is aligned to the current frame, keeping the copied spacing intact.",
]

delete_static_animation_tooltip_text = [
    "Remove animation curves whose keyed values never change.",
    "Useful after cleanup, baking, or blocking passes where dead channels were keyed by mistake.",
    movie.delete_all_animation_static,
]

remove_redundant_keys_tooltip_text = [
    "Remove unnecessary keys that do not change the shape of the selected animation.",
    "Use this after baking or dense edits to simplify curves while keeping the motion intact.",
]

remove_static_anim_curves_tooltip_text = delete_static_animation_tooltip_text

reverse_animation_tooltip_text = [
    "Reverse the selected animation over the current time context.",
    "Uses the selected Time Slider range, selected Graph Editor keys, or the playback range.",
]

set_smart_key_tooltip_text = [
    "Set keys only on the channels or curves that matter for the current selection.",
    "Uses selected Graph Editor keys, Channel Box channels, selected curves, or keyable channels as needed.",
]

set_smart_key_all_channels_tooltip_text = [
    "Set keys on all keyable scalar channels for the selected objects.",
    "Use this when you want a full pose key instead of only the currently focused channels.",
]

graph_match_keys_tooltip_text = [
    "Match one selected curve to another so both curves share the same values.",
]

flip_tooltip_text = [
    "Invert the selected curve values vertically.",
    movie.flip,
]

snap_tooltip_text = [
    "Snap selected sub-frame keys to the nearest whole frame.",
    "It doesn't just reposition the keyframes, it creates them on the nearest frame and removes all the keyframes that are off a frame.",
    "This way, the existing animation remains intact.",
    movie.snap,
    separator,
    "Note: Maya fails to apply snap and reports an error, whereas TKM applies the snap without any issues.",
]

overlap_tooltip_text = [
    "Offset the selected curves to create overlapping motion.",
    movie.overlap,
]

align_translation_tooltip_text = [
    "Match only translation from the driver object to the target object.",
]

align_rotation_tooltip_text = [
    "Match only rotation from the driver object to the target object.",
]

align_scale_tooltip_text = [
    "Match only scale from the driver object to the target object.",
]

default_translations_tooltip_text = [
    "Reset only translation values on the current selection.",
]

default_rotations_tooltip_text = [
    "Reset only rotation values on the current selection.",
]

default_scales_tooltip_text = [
    "Reset only scale values on the current selection.",
]

default_trs_tooltip_text = [
    "Reset translation, rotation, and scale values on the current selection.",
]

quick_export_selection_sets_tooltip_text = [
    "Export selection sets to the shared quick file, overwriting the previous quick-export data.",
]

quick_import_selection_sets_tooltip_text = [
    "Import selection sets from the shared quick file.",
]

export_selection_sets_tooltip_text = [
    "Export selection sets to a chosen file.",
]

import_selection_sets_tooltip_text = [
    "Import selection sets from a chosen file.",
]

clear_selection_sets_tooltip_text = [
    "Delete every saved selection set in the current scene.",
]

extra_tools_tooltip_text = [
    "Open additional curve utilities used for cleanup and adjustment work.",
]

paste_pose_tooltip_text = [
    "Paste the saved pose onto the current selection.",
]

paste_opposite_animation_tooltip_text = [
    "Paste the saved animation onto the opposite-side controls.",
]

follow_translation_tooltip_text = [
    "Create a Follow Cam that inherits only translation from the selected object.",
]

follow_rotation_tooltip_text = [
    "Create a Follow Cam that inherits only rotation from the selected object.",
]

remove_follow_cam_tooltip_text = [
    "Remove the current Follow Cam setup.",
]

graph_isolate_curves_tooltip_text = [
    "Show only the selected curves in the Graph Editor.",
    movie.isolate_curves,
]

graph_mute_tooltip_text = [
    "Toggle mute on the selected curves.",
    movie.mute_curves,
]

graph_lock_tooltip_text = [
    "Toggle lock on the selected curves.",
    movie.lock_curves,
]

graph_filter_tooltip_text = [
    "Filter the Graph Editor to the current selection.",
    "Use the alternate action to clear the filter when needed.",
]

graph_default_tooltip_text = [
    "Reset the selected curves to their default values.",
]

tangent_cycle_matcher_tooltip_text = [
    "Match the selected curve ends for cleaner cyclic animation.",
]

tangent_bouncy_tooltip_text = [
    "Set the selected curves to a bouncy tangent style.",
]


selection_sets_tooltip_text = [
    "Save and recall useful selections from a floating panel.",
    "Use color-coded sets to organize character picks, shot-specific groups, and quick imports or exports.",
]

customGraph_tooltip_text = [
    "Toggle the automatic TKM toolbar inside Maya's Graph Editor.",
    "This button manages the saved preference only; it does not open the Graph Editor itself.",
]

custom_tools_tooltip_text = [
    "Open your custom pipeline tool shortcuts from a single menu.",
    "Configure these entries carefully to avoid broken tool definitions.",
]

custom_scripts_tooltip_text = [
    "Open your personal and third-party script shortcuts from one menu.",
    "Useful when you want quick access without relying on Maya shelves.",
]
