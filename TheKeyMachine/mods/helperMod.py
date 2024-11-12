

'''

    TheKeyMachine - Animation Toolset for Maya Animators                                           
                                                                                                                                              
                                                                                                                                              
    This file is part of TheKeyMachine, an open source software for Autodesk Maya licensed under the GNU General Public License v3.0 (GPL-3.0).                                           
    You are free to use, modify, and distribute this code under the terms of the GPL-3.0 license.                                              
    By using this code, you agree to keep it open source and share any modifications.                                                          
    This code is provided "as is," without any warranty. For the full license text, visit https://www.gnu.org/licenses/gpl-3.0.html

    thekeymachine.xyz / x@thekeymachine.xyz                                                                                                                                        
                                                                                                                                              
    Developed by: Rodrigo Torres / rodritorres.com                                                                                             
                                                                                                                                             


'''


import maya.cmds as cmds
import os
import sys
import platform 
from PySide2.QtWidgets import QApplication, QDesktopWidget

import TheKeyMachine.mods.mediaMod as media

from TheKeyMachine.mods.generalMod import config

INSTALL_PATH                    = config["INSTALL_PATH"]


# ---------------------------------------------


def getImage(image):
    img_dir = os.path.join(INSTALL_PATH, "TheKeyMachine/data/img/")

    fullImgDir = os.path.join(img_dir, image)
    return fullImgDir


# images -------------------------------------

isolate_image = getImage("isolate.png")
create_locator_image = getImage("cube.png")
match_image = getImage("magnet.png")
tracer_image = getImage("tracer.png")
reset_animation_image = getImage("eraser.png")
delete_animation_image = getImage("trash.png")





# style ------------------------------------

desktop = QDesktopWidget()
screen_resolution = desktop.screenGeometry()
screen_width = screen_resolution.width()

if screen_width == 3840:
    font_size_enun ="25px"
    font_size ="18px"
else:
    font_size_enun ="20px"
    font_size ="12px"

# ----------------------------------------------  TOOLTIPS  --------------------------------------------------------


#-------- KeyBox


move_key_left_b_widget_tooltip_text = (
    f"<font style='color: #cccccc; font-size:{font_size_enun};'><b>Nudge Keys Left</b></font><br><br>"
    "Move the selected keyframes by the number of frames specified in the central box.<br><br>"
    ""
)


remove_inbetween_b_widget_tooltip_text = (
    f"<font style='color: #cccccc; font-size:{font_size_enun};'><b>Remove Inbetween </b></font><br><br>"
    "Remove one inbetween.<br><br>"
    ""
)


move_keyframes_intField_widget_tooltip_text = (
    f"<font style='color: #cccccc; font-size:{font_size_enun};'><b>Set</b></font><br><br>"
    "Set the number of frames to move when using the 'Nudge' tool.<br><br>"
    ""
)

add_inbetween_b_widget_tooltip_text = (
    f"<font style='color: #cccccc; font-size:{font_size_enun};'><b>Add Inbetween </b></font><br><br>"
    "Add one inbetween<br><br>"
    ""
)


move_key_right_b_widget_tooltip_text = (
    f"<font style='color: #cccccc; font-size:{font_size_enun};'><b>Nudge Keys Right </b></font><br><br>"
    "Move the selected keyframes by the number of frames specified in the central box.<br><br>"
    ""
)


clear_selected_keys_widget_tooltip_text = (
    f"<font style='color: #cccccc; font-size:{font_size_enun};'><b>Break Keys Selection</b></font><br><br>"
    "When you select a range in the Time Slider and click on 'Nudge Keys Left' or 'Nudge Keys Right',"
    " the animation keys within that range will be automatically selected.<br><br>"
    "To nudge only a single frame again, you need to deselect the currently selected keys.<br>"
    "This tool allows you to deselect those keys.<br><br>"
)


select_scene_animation_widget_tooltip_text = (
    f"<font style='color: #cccccc; font-size:{font_size_enun};'><b>Select Scene Animation</b></font><br><br>"
    "Select all animation curves in the scene. Useful when you want to move all the animation in the scene. <br><br>"
    "To do this:<br>"
    "- Click on the button to select all the scene's animation curves.<br>"
    "- Enter the number of frames you want to move the animation by.<br>"
    "- Click on the '<b>Nudge Keys Left</b>' or '<b>Nudge Keys Right</b>' button, depending on the case.<br><br>"
    ""
)


# ------ Sliders


blend_slider_tooltip_text = (
    f"<font style='color: #cccccc; font-size:20px;'><b>Blend Slider </b></font><br><br>"
    "Blend between previous and next keyframe value.<br><br>"
    "Select channels in the Channel Box to adjust only those channels.<br><br>"
    ""
)

blend_to_frame_slider_tooltip_text = (
    f"<font style='color: #cccccc; font-size:20px;'><b>Blend to Frame </b></font><br><br>"
    "Upon pressing each button, the current frame is assigned to the button.<br>"
    "The blend slider will perform the blending function between the assigned frames.<br><br>"
    ""
)

tween_slider_tooltip_text = (
    f"<font style='color: #cccccc; font-size:20px;'><b>Tween Slider </b></font><br><br>"
    "Tween between previous and next keyframe.<br><br>"
    "Select channels in the Channel Box to adjust only those channels.<br><br>"
    ""
)


# ----- ReBlock, ShareKeys, BakeKeys

block_keys_tooltip_text = (
    f"<font style='color: #cccccc; font-size:{font_size_enun};'><b>reBlock </b></font><img src='{media.reblock_keys_image}' width='30'><br><br>"
    f"<font style='color: #cccccc; font-size:{font_size};'>"
    "reBlock helps you place all animation keys where your main poses are. Especially useful when some keyframes have moved out of place.<br><br>"
    "Use: Simply select the objects and run the tool.<br>"
    "</font>"
    "<br><br>"

    f"<font style='color: #cccccc; font-size:{font_size_enun};'><b>Share Keys </b></font><img src='{media.reblock_keys_image}' width='30'><br><br>"
    f"<font style='color: #cccccc; font-size:{font_size};'>"
    "This tool allows you to share keys position between one object and another so that both objects have the same keyframes position.<br><br>"
    "You can share keys to more than one object at the same time.<br><br>"
    "Select a range in the Range Slider to share keys only in that range.<br><br>"
    "Use: First select the object that has the keyframes, followed by the objects you want to share the keyframes with.<br>"
    "</font>"
    "<br><br>"

    f"<font style='color: #cccccc; font-size:{font_size_enun};'><b>Bake Anim </b></font><img src='{media.reblock_keys_image}' width='30'><br><br>"
    f"<font style='color: #cccccc; font-size:{font_size};'>"
    "A simple way of baking all your animation. By default this tool switch your curves to step mode.<br><br>"
    "Select the objects you want to bake and run the tool.<br><br>"
    "Use: Add '2' in interval to bake you animation every 2 frames.<br><br>"
    "</font>"
    ""

    f"<font style='color: #cccccc; font-size:{font_size_enun};'><b>Gimbal Fixer </b></font><img src='{media.reblock_keys_image}' width='30'><br><br>"
    f"<font style='color: #cccccc; font-size:{font_size};'>"
    "Gimbal Fixer allows you to change the rotation order of a control or object without altering the existing animation.<br>"
    "It is ideal for changing the rotation order when we have a control with gimbal lock.<br><br>"
    "The tool displays a list of options where the lowest percentage is the best choice.<br><br>"
    "</font>"
    ""

)


# ----- Pointer


pointer_tooltip_text = (
    f"<font style='color: #cccccc; font-size:{font_size_enun};'><b>Select Rig Controls </b></font><img src='{media.select_rig_controls_image}' width='30'><br><br>"
    f"<font style='color: #cccccc; font-size:{font_size};'>"
    "This tool selects all rig controls. Selected controls will be only nurbs curves.."
    "</font>"
    "<br><br>"

    f"<font style='color: #cccccc; font-size:{font_size_enun};'><b>Select Animated Rig Controls </b></font><img src='{media.select_animated_rig_controls_image}' width='30'><br><br>"
    f"<font style='color: #cccccc; font-size:{font_size};'>"
    "This tool selects all animated rig controls. Selected controls will be only nurbs curves."
    "</font>"
    "<br><br>"

    f"<font style='color: #cccccc; font-size:{font_size_enun};'><b>Depth Mover </b></font><img src='{media.depth_mover_image}' width='30'><br><br>"
    f"<font style='color: #cccccc; font-size:{font_size};'>"
    "Adjust object depth without altering its camera-relative position or angle.<br><br>"
    "</font>"
    ""

)



# ----- Isolate


isolate_tooltip_text = (
    f"<font style='color: #cccccc; font-size:{font_size_enun};'><b>Isolate  </b></font><img src='{isolate_image}' width='30'><br><br>"
    f"<font style='color: #cccccc; font-size:{font_size};'>"
    "This tool allows you to isolate the entire rig by selecting just a single control.<br><br>"
    "You can utilize this tool to isolate multiple rigs simultaneously or select both<br>"
    "objects and rigs. In either scenario, the tool will isolate the top node in every hierarchy.<br><br>"
    "Use the 'down one level' option if you wish to move down one level, a handy feature when all your "
    "character rigs are housed within a group.<br><br>"
    "Open the <b>Bookmark</b> window to save isolate bookmarks. All bookmarks will be added to the isolate menu.<br><br>"
    "When creating bookmarks you need to select the objects you want in the bookmark in the OutLiner.<br><br>"
    "For additional assistance, please refer to the knowledge site.<br><br>"
    "Right-click for options.<br>"
    "</font>"

)



createLocator_tooltip_text = (
    f"<font style='color: #cccccc; font-size:{font_size_enun};'><b>Temp locator   </b></font><img src='{create_locator_image}' width='30'><br><br>"
    f"<font style='color: #cccccc; font-size:{font_size};'>"
    "Create temp locators on the spot in the selected object or objects.<br><br><br>"
    "Right-click for options.<br>"
    "</font>"
)

align_tooltip_text = (
    f"<font style='color: #cccccc; font-size:{font_size_enun};'><b>Match / Align  </b></font><img src='{match_image}' width='30'><br><br><br>"
    f"<font style='color: #cccccc; font-size:{font_size};'>"
    "Aling one object to another.<br><br>"
    "First select the child object, then the parent object.<br><br>"
    "If a range is selected on the TimeSlider the child object will be aligned during the selected range.<br>"
    "The parent object needs to have animation for this to work.<br><br>"
    "Right-click for options.<br>"
    "</font>"
)

tracer_tooltip_text = (
    f"<font style='color: #cccccc; font-size:{font_size_enun};'><b>Tracer  </b></font><img src='{tracer_image}' width='30'><br><br>"
    f"<font style='color: #cccccc; font-size:{font_size};'>"
    "Create a motion trail on the selected object<br><br>"
    "This is a modified Maya's motion trail. You can activate or desactivate it so that it will not refresh eveytime you move the tracked object<br><br>"
    "Use 'refresh' to refresh the trail without activating it.<br><br>"
    f"<font style='color: #869fac; font-size:{font_size};'><b>Keys Shortcuts:</b></font><br>"
    f"<font style='color: #869fac; font-size:{font_size};'>Shift &nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp; Refresh</font><br>"
    f"<font style='color: #869fac; font-size:{font_size};'>Ctrol &nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp; Show/Hide</font><br>"
    f"<font style='color: #869fac; font-size:{font_size};'>Ctrol + Alt &nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp; Remove</font><br>"
    "</font>"
)

reset_values_tooltip_text = (
    f"<font style='color: #cccccc; font-size:{font_size_enun};'><b>Reset to default  </b></font><img src='{reset_animation_image}' width='30'><br><br>"
    f"<font style='color: #cccccc; font-size:{font_size};'>"
    "Reset objects to their default values. Handy to reset a pose, or attributes in an object.<br><br>"
    "Select channels in the ChannelBox to reset only the selected channels.<br><br>"
    "</font>"
    f"<font style='color: #869fac; font-size:{font_size};'><b>Shortcuts:</b></font><br>"
    f"<font style='color: #869fac; font-size:{font_size};'>Shift &nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp; Reset Translations</font><br>"
    f"<font style='color: #869fac; font-size:{font_size};'>Ctrol &nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp; Reset Rotations</font><br>"
    "</font>"
)

delete_animation_tooltip_text = (
    f"<font style='color: #cccccc; font-size:{font_size_enun};'><b>Delete Animation </b></font><img src='{delete_animation_image}' width='30'><br><br>"
    f"<font style='color: #cccccc; font-size:{font_size};'>"
    "Delete animation in all animation channels.<br><br>"
    "Select channels in the ChannelBox to remove animation only in the selected channels.<br><br>"
    "Use 'Shift' key to remove keyframes from TimeSlider.<br><br>"
    "</font>"
    f"<font style='color: #869fac; font-size:{font_size};'><b>Shortcuts:</b></font><br>"
    f"<font style='color: #869fac; font-size:{font_size};'>Shift + Click &nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;  Remove Time Slider keyframes</font><br>"
    "</font>"
    ""
    "</font>"

)


select_opposite_tooltip_text = (
    f"<font style='color: #cccccc; font-size:{font_size_enun};'><b>Select opposite </b></font><img src='{media.select_opposite_image}' width='30'><br><br>"
    f"<font style='color: #cccccc; font-size:{font_size};'>"
    "Select the opposite control of a rig. You can select more than one object at a time.<br><br>"
    ""
    "</font>"
    f"<font style='color: #869fac; font-size:{font_size};'><b>Shortcuts:</b></font><br>"
    f"<font style='color: #869fac; font-size:{font_size};'>Shift + Click &nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;  Add opposite</font><br>"
    "</font>"
)

copy_opposite_tooltip_text = (
    f"<font style='color: #cccccc; font-size:{font_size_enun};'><b>Copy opposite </b></font><img src='{media.copy_opposite_image}' width='30'><br><br>"
    f"<font style='color: #cccccc; font-size:{font_size};'>"
    "Copy the current values from the selected objects to their opposite.<br><br>"
    "Keep in mind that this tool works in conjunction with the Mirror tool. Any exception added in Mirror will affect this tool.<br><br>"
    ""
    "</font>"
)

mirror_tooltip_text = (
    f"<font style='color: #cccccc; font-size:{font_size_enun};'><b>Mirror </b></font><img src='{media.mirror_image}' width='30'><br><br>"
    f"<font style='color: #cccccc; font-size:{font_size};'>"
    "This tool creates mirror positions for the selected objects.<br><br>"
    "Given the large number of existing rigs, it may sometimes be necessary to configure the tool. This is done by adding exceptions so that the mirror functions correctly.<br>"
    "The mirror configuration is saved in a file, so it only needs to be done once per rig system.<br><br>"
    "Please visit the help page to understand how to configure the tool.<br><br>"
    ""
    "</font>"
)

copy_paste_animation_tooltip_text = (
    f"<font style='color: #cccccc; font-size:{font_size_enun};'><b>Copy Paste Animation </b></font><img src='{media.copy_paste_animation_image}' width='30'><br><br>"
    f"<font style='color: #cccccc; font-size:{font_size};'>"
    "Copy and paste animations of objects or controls. The animation is saved in a file, so it can be pasted in another Maya session.<br><br>"
    "If you have copied only one side of the controls, you can paste them on the opposite side.<br><br>"
    "</font>"
    f"<font style='color: #cccccc; font-size:{font_size_enun};'><b>Copy Paste Pose </b></font><img src='{media.copy_pose_image}' width='30'><br><br>"
    f"<font style='color: #cccccc; font-size:{font_size};'>"
    "Copy and paste poses between the same or different character. The pose is saved in a file, so it can be pasted in another Maya session.<br><br>"
    "To paste poses between characters, they must have the same control name.<br><br>"
    "</font>"
)




selector_tooltip_text = (
    f"<font style='color: #cccccc; font-size:{font_size_enun};'><b>Selector </b></font><img src='{media.selector_image}' width='30'><br><br>"
    f"<font style='color: #cccccc; font-size:{font_size};'>"
    "Display all selected items in a window where you can make individual or group selections.<br><br>"
    "The list is sorted in alphabetical or numerical order. Use the 'Reload' option to refresh the items you see in the window.<br><br>"
    ""
    "</font>"

)

select_hierarchy_tooltip_text = (
    f"<font style='color: #cccccc; font-size:{font_size_enun};'><b>Select hierarchy </b></font><img src='{media.select_hierarchy_image}' width='30'><br><br>"
    f"<font style='color: #cccccc; font-size:{font_size};'>"
    "Select the descending hierarchy from the currently selected objects.<br><br>"
    "Select the shoulder control of an FK arm to select shoulder-forearm-wrist. It's also useful for selecting all the finger controls of a hand by only selecting the top controls.<br><br>"
    ""
    "</font>"
)

animation_offset_tooltip_text = (
    f"<font style='color: #cccccc; font-size:{font_size_enun};'><b>Animation offset </b></font><img src='{media.animation_offset_image}' width='30'><br><br>"
    f"<font style='color: #cccccc; font-size:{font_size};'>"
    "Animation offset allows you to move the position of an animated object without affecting the existing animation.<br>"
    "The position change made propagates throughout the entire existing animation.<br><br>"
    "For this tool to work properly, it should be executed when on a keyframe. Currently, it only works with one object at a time.<br><br>"
    ""
    "</font>"
)

link_objects_tooltip_text = (
    f"<font style='color: #cccccc; font-size:{font_size_enun};'><b>Link objects </b></font><img src='{media.link_objects_image}' width='30'><br><br>"
    f"<font style='color: #cccccc; font-size:{font_size};'>"
    "Link objects is like using parent constraints without constraints. The tool allows you to save the relationship between several objects and apply that relationship back when needed.<br><br>"
    "The usage is straightforward: first, select the objects that will follow then the main or target object. Run 'Copy Link Position'<br><br>"
    ""
    "To retrieve the object relationship, execute 'Paste Link Position'. At least one object must be selected.<br><br>"
    "The relationship between objects is saved to a file on disk, so this tool can be used across different Maya sessions.<br><br>"
    "Use the 'Auto Link' option to update the object relationship in real-time.<br><br>"
    "Right-click for options.<br><br><br>"
    f"<font style='color: #869fac; font-size:{font_size};'><b>Shortcuts:</b></font><br>"
    f"<font style='color: #869fac; font-size:{font_size};'>Click &nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;  Copy Link Position</font><br>"
    f"<font style='color: #869fac; font-size:{font_size};'>Shift + Click &nbsp;&nbsp;&nbsp;&nbsp;&nbsp; Paste Link Position</font>"
    "</font>"
)

follow_cam_tooltip_text = (
    f"<font style='color: #cccccc; font-size:{font_size_enun};'><b>FollowCam </b></font><img src='{media.follow_cam_image}' width='30'><br><br>"
    f"<font style='color: #cccccc; font-size:{font_size};'>"
    "FollowCam creates a camera that will follow the selected object.<br><br>"
    "It's useful when you need to make animation changes to an object that is moving, in this way the object will remain static in the camera's view.<br><br>"
    "Right-click for options.<br>"
    "</font>"
)

copy_worldspace_tooltip_text = (
    f"<font style='color: #cccccc; font-size:{font_size_enun};'><b>Copy WorldSpace </b></font><img src='{media.copy_worldspace_animation_image}' width='28'><br><br>"
    f"<font style='color: #cccccc; font-size:{font_size};'>"
    "Copy and paste world space positions. Useful for reseting, for example, the master control in a walking cycle.<br><br>"
    "To 'Copy' select a group of controls and click 'Copy worldspace'.<br><br>"
    "To 'Paste' just click 'Paste worldspace' there is not need of selecting any control.<br><br>"

    f"<font style='color: #869fac; font-size:{font_size};'><b>Shortcuts:</b></font><br>"
    f"<font style='color: #869fac; font-size:{font_size};'>Click &nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;  Copy worldspace</font><br>"
    f"<font style='color: #869fac; font-size:{font_size};'>Shift + Click &nbsp;&nbsp;&nbsp; Paste worldspace</font>"
    "</font><br><br>"

    f"<font style='color: #cccccc; font-size:{font_size_enun};'><b>Copy WorldSpace Current Frame </b></font><img src='{media.copy_worldspace_frame_animation_image}' width='28'><br><br>"
    f"<font style='color: #cccccc; font-size:{font_size};'>"
    "Copy and paste world space values for the current frame.<br><br>"
    "</font>"

)

temp_pivot_tooltip_text = (
    f"<font style='color: #cccccc; font-size:{font_size_enun};'><b>Temp pivot </b></font><img src='{media.temp_pivot_image}' width='30'><br><br>"
    f"<font style='color: #cccccc; font-size:{font_size};'>"
    "Temp pivot allows you to create temporary pivots.<br><br>"
    "These pivots are created without affecting object's animation or pivot and without using any kind of constraint.<br><br>"
    "Temp pivots can be applied to multiple objects at once. The temp pivots are destroyed when selection is changed."
    "<br><br>"
    "Right-click for options.<br>"
    "</font>"

)


micro_move_tooltip_text = (
    f"<font style='color: #cccccc; font-size:{font_size_enun};'><b>Micro Move </b></font><img src='{media.ruler_image}' width='30'><br><br>"
    f"<font style='color: #cccccc; font-size:{font_size};'>"
    "The tool allows you to move and rotate controls at a much slower speed than usual.<br><br>"
    "It is especially useful for adjusting facial controls. The tool has some limitations:<br><br>"
    "It works only with rotations in Gimbal mode and translations in Local or World mode."
    "<br><br>"
    "</font>"

)


selection_sets_tooltip_text = (
    f"<font style='color: #cccccc; font-size:{font_size_enun};'><b>Selection Sets </b></font><img src='{media.selection_sets_image}' width='30'><br><br>"
    f"<font style='color: #cccccc; font-size:{font_size};'>"
    "Create sets of selections.<br><br>"
    "Use the 'main' group to add selection sets that are not related to each other, or create 'Groups' to group all sets under the same category.<br><br>"
    "Groups are useful for creating selections sets for characters. "
    "Groups can be hidden or unhidden.<br><br>"
    "Import and export sets and groups between scenes."
    "<br>"
    "</font>"

)

customGraph_tooltip_text = (
    f"<font style='color: #cccccc; font-size:{font_size_enun};'><b>customGraph </b></font><img src='{media.customGraph_image}' width='30'><br><br>"
    f"<font style='color: #cccccc; font-size:{font_size};'>"
    "Open GraphEditor with the customGraph add-on.<br><br>"
    "customGraph is a specific set of tools for the GraphEditor. Manipulate animation curves, lock or mute channels, or create specific selection sets.<br><br>"
    "</font>"

)

custom_tools_tooltip_text = (
    f"<font style='color: #cccccc; font-size:{font_size_enun};'><b>Custom Tools </b></font><img src='{media.custom_tools_image}' width='30'><br><br>"
    f"<font style='color: #cccccc; font-size:{font_size};'>"
    "This tool it's designed to add shortcuts to the pipeline tools you use in your day-to-day.<br><br>"
    "</font>"
    f"<font style='color: #e67373; font-size:{font_size};'>Please refer to the help page to understand how this tool works and to avoid errors in TheKeyMachine."
    "</font>"
    "<br>"

)

custom_scripts_tooltip_text = (
    f"<font style='color: #cccccc; font-size:{font_size_enun};'><b>Custom Scripts </b></font><img src='{media.custom_scripts_image}' width='30', height='30'><br><br>"
    f"<font style='color: #cccccc; font-size:{font_size};'>"
    "This tool it's designed to add shortcuts to your personal scripts and third-party tools.<br><br>"
    "If you don't like using Maya's shelf, this is the perfect place to centralize your scripts. "
    "Add the tools you use most frequently and have immediate access to them from the menu."
    "</font><br><br>"
    f"<font style='color: #e67373; font-size:{font_size};'>Please refer to the help page to understand how this tool works and to avoid errors in TheKeyMachine."
    "</font>"
    "<br>"
)