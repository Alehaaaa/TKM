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

from TheKeyMachine.mods.generalMod import config

INSTALL_PATH = config["INSTALL_PATH"]


def getImage(image):
    img_dir = os.path.join(INSTALL_PATH, "TheKeyMachine", "data", "img")
    return os.path.join(img_dir, image)


# __________________ Install _________________________________ #

tool_icon = getImage("TheKeyMachine_icon.png")

# __________________ Nodes _________________________________ #

tkm_node_image = getImage("tkm_node.png")

# __________________ Toolbar Images _________________________________ #

nudge_left_image = getImage("nudge_left.svg")
nudge_right_image = getImage("nudge_right.svg")

insert_inbetween_image = getImage("nudge_insert_inbetween.svg")
remove_inbetween_image = getImage("nudge_remove_inbetween.svg")

pointer_image = getImage("pointer.svg")
depth_mover_image = getImage("depth_mover.svg")
select_rig_controls_image = getImage("select_rig_controls.svg")
select_animated_rig_controls_image = getImage("select_animated_rig_controls.svg")

isolate_image = getImage("isolate.svg")
create_locator_image = getImage("cube.svg")
align_menu_image = getImage("magnet.svg")
tracer_menu_image = getImage("tracer.svg")
reset_animation_image = getImage("eraser.svg")
delete_animation_image = getImage("trash.svg")

match_image = getImage("magnet.svg")

select_opposite_image = getImage("select_opposite.svg")
copy_opposite_image = getImage("copy_opposite.svg")
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
bake_animation_image = getImage("bake_animation.svg")

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
ruler_image = getImage("ruler.svg")

auto_tangent_image = getImage("auto_tangent.svg")
spline_tangent_image = getImage("spline_tangent.svg")
linear_tangent_image = getImage("linear_tangent.svg")
step_tangent_image = getImage("step_tangent.svg")
match_curve_cycle_image = getImage("match_curve_cycle.svg")
bouncy_curve_image = getImage("bouncy_curve.svg")

playblast_image = getImage("playblast.svg")
selection_sets_image = getImage("selection_sets.svg")
add_selection_set_image = getImage("add_selection_set.svg")
customGraph_image = getImage("customGraph.svg")

orbit_ui_image = getImage("orbit_ui.svg")
custom_tools_image = getImage("tools_folder.svg")
custom_scripts_image = getImage("scripts_folder.svg")

settings_image = getImage("settings.svg")
settings_update_image = getImage("settings_update.svg")


close_image = getImage("close.png")
apply_image = getImage("apply.png")
cancel_image = getImage("cancel.png")

# ________________ dot colors __________________________________________#

green_dot_image = getImage("green_dot.png")
red_dot_image = getImage("red_dot.png")
grey_dot_image = getImage("grey_dot.png")
blue_dot_image = getImage("blue_dot.png")
yellow_dot_image = getImage("yellow_dot.png")

grey_got_image = getImage("grey_dot.png")

default_dot_image = getImage("round_dot.png")


# ________________ Selection Sets ________________________________________#

move_selection_set_image = getImage("move_selection_set.svg")
selector_selection_set_image = getImage("selector_selection_set.svg")
add_to_selection_set_image = getImage("add_to_selection_set.svg")
remove_from_selection_set_image = getImage("remove_from_selection_set.svg")
rename_selection_set_image = getImage("rename_selection_set.svg")
change_selection_set_color_image = getImage("change_selection_set_color.svg")
remove_selection_set_image = getImage("remove_selection_set.svg")
selection_set_color_icon_names = {
    "_01": "_redLight_set.svg",
    "_02": "_red_set.svg",
    "_03": "_redDark_set.svg",
    "_04": "_orangeLight_set.svg",
    "_05": "_orange_set.svg",
    "_06": "_orangeDark_set.svg",
    "_07": "_yellowLight_set.svg",
    "_08": "_yellow_set.svg",
    "_09": "_yellowDark_set.svg",
    "_10": "_greenLight_set.svg",
    "_11": "_green_set.svg",
    "_12": "_greenDark_set.svg",
    "_13": "_blueLight_set.svg",
    "_14": "_blue_set.svg",
    "_15": "_blueDark_set.svg",
    "_16": "_tealLight_set.svg",
    "_17": "_teal_set.svg",
    "_18": "_tealDark_set.svg",
    "_19": "_purpleLight_set.svg",
    "_20": "_purple_set.svg",
    "_21": "_purpleDark_set.svg",
    "_22": "_pinkLight_set.svg",
    "_23": "_pink_set.svg",
    "_24": "_pinkDark_set.svg",
}
selection_set_color_images = {suffix: getImage(filename) for suffix, filename in selection_set_color_icon_names.items()}

# ________________ Menus Images __________________________________________#

reload_image = getImage("reload.png")
remove_image = getImage("remove.svg")
dock_image = getImage("dock.png")
check_updates_image = getImage("check_updates.svg")
check_updates_image_available = getImage("check_updates_available.svg")
report_a_bug_image = getImage("bug.svg")
about_image = getImage("about.png")

# ___________________Help / Tooltips Images ______________________________#

help_menu_image = getImage("help.svg")
ibookmarks_menu_image = getImage("ibookmarks_menu.png")

discord_image = getImage("discord.svg")
youtube_image = getImage("youtube.svg")

# ___________________ Tracer ______________________________#

tracer_show_hide_image = getImage("tracer_show_hide.svg")
tracer_refresh_image = getImage("tracer_refresh.svg")
tracer_select_offset_image = getImage("tracer_select_offset.svg")
tracer_set_color_image = getImage("tracer_set_color.svg")
tracer_red_image = getImage("tracer_red.svg")
tracer_grey_image = getImage("tracer_grey.svg")
tracer_blue_image = getImage("tracer_blue.svg")
