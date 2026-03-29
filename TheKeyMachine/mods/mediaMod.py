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
import TheKeyMachine.tools.colors as toolColors

from TheKeyMachine.mods.generalMod import config

INSTALL_PATH = config["INSTALL_PATH"]


def getImage(image):
    img_dir = os.path.join(INSTALL_PATH, "TheKeyMachine", "data", "img")
    return os.path.join(img_dir, image)


def getSelectionSetsImage(image):
    return getImage(os.path.join("selection_sets", image))


# __________________ Install _________________________________ #

tool_icon = getImage("TheKeyMachine_icon.png")
stripe_image = getImage("stripe.png")
TheKeyMachine_logo_250_image = getImage("TheKeyMachine_logo_250.png")

# __________________ Nodes _________________________________ #

tkm_node_image = getImage("tkm_node.png")

install_image = getImage("install.png")
skip_image = getImage("skip.png")

# __________________ Toolbar Images _________________________________ #

nudge_left_image = getImage("nudge_left.svg")
nudge_right_image = getImage("nudge_right.svg")

insert_inbetween_image = getImage("nudge_insert_inbetween.svg")
remove_inbetween_image = getImage("nudge_remove_inbetween.svg")

pointer_image = getImage("pointer.svg")
depth_mover_image = getImage("depth_mover.svg")
select_rig_controls_image = getImage("select_rig_controls.svg")
select_rig_controls_animated_image = getImage("select_rig_controls_animated.svg")

isolate_image = getImage("isolate.svg")
create_locator_image = getImage("cube.svg")
align_menu_image = getImage("magnet.svg")
tracer_image = getImage("tracer.svg")
reset_animation_image = getImage("eraser.svg")
delete_animation_image = getImage("delete_animation.svg")
match_image = getImage("magnet.svg")

opposite_select_image = getImage("opposite_select.svg")
opposite_copy_image = getImage("opposite_copy.svg")
opposite_add_image = getImage("opposite_add.svg")
mirror_image = getImage("mirror.svg")
copy_animation_image = getImage("copy_animation.svg")
paste_animation_image = getImage("paste_animation.svg")
paste_insert_animation_image = getImage("paste_insert_animation.svg")
paste_opposite_animation_image = getImage("paste_opposite_animation.svg")

copy_pose_image = getImage("copy_pose.svg")
paste_pose_image = getImage("paste_pose.svg")
reblock_keys_image = getImage("reblock.svg")
share_keys_image = getImage("share_keys.svg")

bake_animation_custom_image = getImage("bake_animation_custom.svg")
bake_animation_1_image = getImage("bake_animation_1.svg")
bake_animation_2_image = getImage("bake_animation_2.svg")
bake_animation_3_image = getImage("bake_animation_3.svg")

selector_image = getImage("selector.svg")
select_hierarchy_image = getImage("select_hierarchy.svg")
animation_offset_image = getImage("animation_offset.svg")
follow_cam_image = getImage("camera.svg")

link_objects_image = getImage("link_relative.svg")
link_objects_copy_image = getImage("link_relative_copy.svg")
link_objects_paste_image = getImage("link_relative_paste.svg")
link_objects_on_image = getImage("link_relative_on.svg")

worldspace_copy_animation_image = getImage("worldspace_copy_animation.svg")
worldspace_paste_animation_image = getImage("worldspace_paste_animation.svg")
worldspace_copy_frame_image = getImage("worldspace_copy_frame.svg")
worldspace_paste_frame_image = getImage("worldspace_paste_frame.svg")

temp_pivot_image = getImage("temp_pivot.svg")
temp_pivot_use_last_image = getImage("temp_pivot_use_last.svg")
ruler_image = getImage("ruler.svg")

auto_tangent_image = getImage("auto_tangent.svg")
spline_tangent_image = getImage("spline_tangent.svg")
linear_tangent_image = getImage("linear_tangent.svg")
step_tangent_image = getImage("step_tangent.svg")
match_curve_cycle_image = getImage("match_curve_cycle.svg")
bouncy_curve_image = getImage("bouncy_curve.svg")

playblast_image = getImage("playblast.svg")

selection_sets_image = getImage("selection_sets.svg")
selection_sets_add_image = getImage("selection_sets_add.svg")
selection_sets_reload_image = getImage("selection_sets_reload.svg")
selection_sets_import_image = getImage("selection_sets_import.svg")
selection_sets_export_image = getImage("selection_sets_export.svg")

customGraph_image = getImage("customGraph.svg")

orbit_ui_image = getImage("orbit_ui.svg")
attribute_switcher_image = getImage("attribute_switcher.svg")
globe_image = getImage("globe.svg")
custom_tools_image = getImage("tools_folder.svg")
custom_scripts_image = getImage("scripts_folder.svg")

settings_image = getImage("settings.svg")
settings_update_image = getImage("settings_update.svg")


close_image = getImage("close.svg")
apply_image = getImage("apply.svg")
cancel_image = getImage("cancel.svg")
add_image = getImage("add.svg")
subtract_image = getImage("subtract.svg")
rename_image = getImage("rename.svg")

trash_image = getImage("trash.svg")

# remove_selection_set_image = getImage("close.svg")

# ________________ dot colors __________________________________________#

green_dot_image = getImage("green_dot.png")
red_dot_image = getImage("red_dot.png")
grey_dot_image = getImage("grey_dot.png")
blue_dot_image = getImage("blue_dot.png")
yellow_dot_image = getImage("yellow_dot.png")

grey_got_image = getImage("grey_dot.png")

default_dot_image = getImage("round_dot.png")


# ________________ Selection Sets ________________________________________#

_selection_set_icon_shade_names = {
    "light": "Light",
    "base": "",
    "dark": "Dark",
}


def _selection_set_icon_filename(color):
    shade = _selection_set_icon_shade_names.get(color.shade, "")
    return f"_{color.family}{shade}_set.svg"


selection_set_color_icon_names = {
    color.suffix: _selection_set_icon_filename(color) for color in toolColors.SELECTION_SET_COLORS
}
selection_set_color_images = {suffix: getSelectionSetsImage(filename) for suffix, filename in selection_set_color_icon_names.items()}
selection_set_color_trash_images = {
    suffix: getSelectionSetsImage(filename.replace(".svg", "_trash.svg")) for suffix, filename in selection_set_color_icon_names.items()
}

color_image = getImage("color.svg")

# ________________ Menus Images __________________________________________#

reload_image = getImage("reload.png")
remove_image = getImage("remove.svg")
dock_image = getImage("dock.png")
check_updates_image = getImage("check_updates.svg")
check_updates_image_available = getImage("check_updates_available.svg")
report_a_bug_image = getImage("bug.svg")
about_image = getImage("about.png")

refresh_image = getImage("refresh.svg")

# ___________________Help / Tooltips Images ______________________________#

help_menu_image = getImage("help.svg")
ibookmarks_menu_image = getImage("ibookmarks_menu.png")

discord_image = getImage("discord.svg")
youtube_image = getImage("youtube.svg")

# ___________________ Tracer ______________________________#

tracer_show_hide_image = getImage("tracer_show_hide.svg")
tracer_select_offset_image = getImage("tracer_select_offset.svg")
tracer_set_color_image = getImage("tracer_set_color.svg")
tracer_red_image = getImage("tracer_red.svg")
tracer_grey_image = getImage("tracer_grey.svg")
tracer_blue_image = getImage("tracer_blue.svg")
