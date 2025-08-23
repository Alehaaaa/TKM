


'''

    TheKeyMachine - Animation Toolset for Maya Animators                                           
                                                                                                                                              
                                                                                                                                              
    This file is part of TheKeyMachine, an open source software for Autodesk Maya licensed under the GNU General Public License v3.0 (GPL-3.0).                                           
    You are free to use, modify, and distribute this code under the terms of the GPL-3.0 license.                                              
    By using this code, you agree to keep it open source and share any modifications.                                                          
    This code is provided "as is," without any warranty. For the full license text, visit https://www.gnu.org/licenses/gpl-3.0.html

    thekeymachine.xyz / x@thekeymachine.xyz                                                                                                                                        
                                                                                                                                              
    Developed by: Rodrigo Torres / rodritorres.com                                                                                             
                                                                                                                                             


'''




import os
import maya.cmds as cmds
import platform

from TheKeyMachine.mods.generalMod import config

INSTALL_PATH                    = config["INSTALL_PATH"]



def getImage(image):
    img_dir = os.path.join(INSTALL_PATH, "TheKeyMachine/data/img/")

    fullImgDir = os.path.join(img_dir, image)
    return fullImgDir


# __________________ Install _________________________________ #

shelf_icon = getImage("TheKeyMachine_shelf_icon.png")


# __________________ Nodes _________________________________ #

tkm_node_image = getImage("tkm_node.png")


# __________________ Toolbar Images _________________________________ #

if platform.system() == 'Darwin':

    pointer_image = getImage("100/pointer_105.svg")
    depth_mover_image = getImage("100/depth_mover_105.svg")
    select_rig_controls_image = getImage("100/select_rig_controls_105.svg")
    select_animated_rig_controls_image = getImage("100/select_animated_rig_controls_105.svg")
    isolate_image = getImage("100/isolate_105.svg")
    create_locator_image = getImage("100/cube_105.svg")
    align_menu_image = getImage("100/magnet_105.svg")
    tracer_menu_image = getImage("100/tracer_105.svg")
    reset_animation_image = getImage("100/eraser_105.svg")
    delete_animation_image = getImage("100/trash_105.svg")

    select_opposite_image = getImage("100/select_opposite_105.svg")
    copy_opposite_image = getImage("100/copy_opposite_105.svg")
    mirror_image = getImage("100/mirror_105.svg")
    copy_paste_animation_image = getImage("100/copy_paste_animation_105.svg")
    paste_animation_image = getImage("100/paste_animation_105.svg")
    paste_insert_animation_image = getImage("100/paste_insert_animation_105.svg")
    paste_opposite_animation_image = getImage("100/paste_opposite_animation_105.svg")
    copy_pose_image = getImage("100/copy_pose_105.svg")
    paste_pose_image = getImage("100/paste_pose_105.svg")
    reblock_keys_image = getImage("100/reblock_105.svg")
    share_keys_image = getImage("100/share_keys_105.svg")
    bake_animation_image = getImage("100/bake_animation_105.svg")

    selector_image = getImage("100/selector_105.svg")
    select_hierarchy_image = getImage("100/select_hierarchy_105.svg")
    animation_offset_image = getImage("100/animation_offset_105.svg")

    follow_cam_image = getImage("100/camera_105.svg")

    link_objects_image = getImage("100/link_relative_105.svg")
    link_objects_on_image = getImage("100/link_relative_on_105.svg")

    copy_worldspace_animation_image = getImage("100/copy_worldspace_animation_105.svg")
    copy_worldspace_frame_animation_image = getImage("100/copy_worldspace_frame_animation_105.svg")
    paste_worldspace_frame_animation_image = getImage("100/paste_worldspace_frame_animation_105.svg")
    paste_worldspace_animation_image = getImage("100/paste_worldspace_animation_105.svg")

    temp_pivot_image = getImage("100/temp_pivot_105.svg")
    ruler_image = getImage("100/ruler_105.svg")

    auto_tangent_image = getImage("100/auto_tangent_105.svg")
    spline_tangent_image = getImage("100/spline_tangent_105.svg")
    linear_tangent_image = getImage("100/linear_tangent_105.svg")
    step_tangent_image = getImage("100/step_tangent_105.svg")
    match_curve_cycle_image = getImage("100/match_curve_cycle.svg")
    bouncy_curve_image = getImage("100/bouncy_curve.svg")

    playblast_image = getImage("100/playblast_105.svg")
    selection_sets_image = getImage("100/selection_sets_105.svg")
    add_selection_set_image = getImage("100/add_selection_set_105.svg")
    customGraph_image = getImage("100/customGraph_105.svg")

    custom_tools_image = getImage("100/tools_folder_105.svg")
    custom_scripts_image = getImage("100/scripts_folder_105.svg")

    settings_image = getImage("100/settings_105.svg")
    settings_cg_image = getImage("100/settings_75.svg")
    settings_update_image = getImage("100/settings_update_105.svg")

else:

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

    select_opposite_image = getImage("select_opposite.svg")
    copy_opposite_image = getImage("copy_opposite.svg")
    mirror_image = getImage("mirror.svg")
    copy_paste_animation_image = getImage("copy_paste_animation.svg")
    paste_animation_image = getImage("paste_animation.svg")
    paste_insert_animation_image = getImage("paste_insert_animation.svg")
    paste_opposite_animation_image = getImage("paste_opposite_animation.svg")

    copy_pose_image = getImage("copy_pose.svg")
    paste_pose_image = getImage("paste_pose.svg")
    reblock_keys_image = getImage("reblock.svg")
    share_keys_image = getImage("share_keys.svg")
    bake_animation_image = getImage("bake_animation.svg")

    selector_image = getImage("selector.svg")
    selector_30_image = getImage("selector_30.svg")
    select_hierarchy_image = getImage("select_hierarchy.svg")
    animation_offset_image = getImage("animation_offset.svg")
    follow_cam_image = getImage("camera.svg")
    link_objects_image = getImage("link_relative.svg")
    link_objects_on_image = getImage("link_relative_on.svg")

    copy_worldspace_animation_image = getImage("copy_worldspace_animation.svg")
    copy_worldspace_frame_animation_image = getImage("copy_worldspace_frame_animation.svg")
    paste_worldspace_frame_animation_image = getImage("paste_worldspace_frame_animation.svg")
    paste_worldspace_animation_image = getImage("paste_worldspace_animation.svg")

    temp_pivot_image = getImage("temp_pivot.svg")
    ruler_image = getImage("ruler.svg")

    auto_tangent_image = getImage("auto_tangent.svg")
    spline_tangent_image = getImage("spline_tangent.svg")
    linear_tangent_image = getImage("linear_tangent.svg")
    step_tangent_image = getImage("step_tangent.svg")
    match_curve_cycle_image = getImage("match_curve_cycle.svg")
    bouncy_curve_image = getImage("bouncy_curve.svg")
    end_tangent_match_image = getImage("end_tangent_match.svg")

    playblast_image = getImage("playblast.svg")
    selection_sets_image = getImage("selection_sets.svg")
    add_selection_set_image = getImage("add_selection_set.svg")
    customGraph_image = getImage("customGraph.svg")

    custom_tools_image = getImage("tools_folder.svg")
    custom_scripts_image = getImage("scripts_folder.svg")

    settings_image = getImage("settings.svg")
    settings_cg_image = getImage("settings.svg")
    settings_update_image = getImage("settings_update.svg")




close_image = getImage("close.png")
center_image = getImage("center.png")

remove_followCam = getImage("remove_followCam.svg")

#________________ dot colors __________________________________________#

green_dot_image = getImage("green_dot.png")
red_dot_image = getImage("red_dot.png")
grey_dot_image = getImage("grey_dot.png")
blue_dot_image = getImage("blue_dot.png")
yellow_dot_image = getImage("yellow_dot.png")


#________________ Selection Sets ________________________________________#

move_selection_set_image = getImage("move_selection_set.svg")
selector_selection_set_image = getImage("selector_selection_set.svg")
add_to_selection_set_image = getImage("add_to_selection_set.svg")
remove_from_selection_set_image = getImage("remove_from_selection_set.svg")
rename_selection_set_image = getImage("rename_selection_set.svg")
change_selection_set_color_image = getImage("change_selection_set_color.svg")
remove_selection_set_image = getImage("remove_selection_set.svg")


#________________ Menus Images __________________________________________#

grey_menu_image = getImage("grey_dot.png")



reload_image = getImage("reload.png")
remove_small_image = getImage("remove_small.png")
uninstall_image = getImage("uninstall.svg")
updater_image = getImage("update.svg")
report_a_bug_image = getImage("bug.svg")
about_image = getImage("about.svg")


#___________________Help / Tooltips Images ______________________________#

donate_menu_image = getImage("donate_01.svg")
help_menu_image = getImage("help.svg")
uninstall_menu_image = getImage("uninstall_menu.png")
ibookmarks_menu_image = getImage("ibookmarks_menu.png")

discord_image = getImage("discord.svg")
youtube_image = getImage("youtube.svg")


#___________________ Donate ______________________________#

donate_image = getImage("stripe.png")

#___________________ Tools ______________________________#

drop_down_arrow_image = getImage("drop_down_arrow.svg")

#___________________ Tracer ______________________________#

tracer_show_hide_image = getImage("tracer_show_hide.svg")
tracer_remove_image = getImage("remove_tracer.svg")
tracer_refresh_image = getImage("tracer_refresh.svg")
tracer_select_offset_image = getImage("tracer_select_offset.svg")
tracer_set_color_image = getImage("tracer_set_color.svg")
tracer_red_image = getImage("tracer_red.svg")
tracer_grey_image = getImage("tracer_grey.svg")
tracer_blue_image = getImage("tracer_blue.svg")