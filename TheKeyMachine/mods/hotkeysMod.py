




'''

    TheKeyMachine - Animation Toolset for Maya Animators                                           
                                                                                                                                              
                                                                                                                                              
    This file is part of TheKeyMachine, an open source software for Autodesk Maya licensed under the GNU General Public License v3.0 (GPL-3.0).                                           
    You are free to use, modify, and distribute this code under the terms of the GPL-3.0 license.                                              
    By using this code, you agree to keep it open source and share any modifications.                                                          
    This code is provided "as is," without any warranty. For the full license text, visit https://www.gnu.org/licenses/gpl-3.0.html

    thekeymachine.xyz / x@thekeymachine.xyz                                                                                                                                        
                                                                                                                                              
    Developed by: Rodrigo Torres / rodritorres.com                                                                                             
    Modified by: Alehaaaa / alehaaaa.github.io                                                                                                 
                                                                                                                                             


'''



import maya.cmds as cmds
import maya.mel as mel
import platform
import sys
import os



def create_TheKeyMachine_hotkeys(*args):  


    open_customGraph = 'import TheKeyMachine;import TheKeyMachine.core.customGraph as cg; cg.createCustomGraph()'

    add_inbetween = 'import TheKeyMachine.mods.hotkeysMod as hotkeys; hotkeys.add_inbetween()'

    remove_inbetween = 'import TheKeyMachine.mods.hotkeysMod as hotkeys; hotkeys.remove_inbetween()'

    move_keyframes_right = 'import TheKeyMachine.mods.hotkeysMod as hotkeys; hotkeys.move_keyframes_right()'

    move_keyframes_left = 'import TheKeyMachine.mods.hotkeysMod as hotkeys; hotkeys.move_keyframes_left()'

    smart_rotation = 'import TheKeyMachine.mods.hotkeysMod as hotkeys; hotkeys.smart_rotation_manipulator()'

    smart_rotation_release = 'import TheKeyMachine.mods.hotkeysMod as hotkeys; hotkeys.smart_rotation_manipulator_release()'

    smart_translation = 'import TheKeyMachine.mods.hotkeysMod as hotkeys; hotkeys.smart_translate_manipulator()'

    smart_translation_release = 'import TheKeyMachine.mods.hotkeysMod as hotkeys; hotkeys.smart_translate_manipulator_release()'

    open_orbit_window = 'import TheKeyMachine.mods.uiMod as ui; ui.orbit_window(offset_x=-160, offset_y=-10)'

    close_orbit_window = 'import TheKeyMachine.mods.uiMod as ui; ui.orbit_window_close()'

    isolate_master = 'import TheKeyMachine.mods.barMod as bar; bar.isolate_master()'

    select_rig_controls = 'import TheKeyMachine.mods.barMod as bar; bar.select_rig_controls()'

    select_animated_rig_controls = 'import TheKeyMachine.mods.barMod as bar; bar.select_animated_rig_controls()'

    depth_mover = 'import TheKeyMachine.mods.barMod as bar; bar.depth_mover()'

    createLocator = 'import TheKeyMachine.mods.barMod as bar; bar.createLocator()'

    align_selected_objects = 'import TheKeyMachine.mods.barMod as bar; bar.align_selected_objects()'

    create_tracer = 'import TheKeyMachine.mods.barMod as bar; bar.create_tracer()'

    refresh_tracer = 'import TheKeyMachine.mods.barMod as bar; bar.refresh_tracer()'

    reset_object_values = 'import TheKeyMachine.mods.keyToolsMod as key; key.reset_object_values()'

    reset_object_values_translate = 'import TheKeyMachine.mods.keyToolsMod as key; key.reset_object_values(reset_translations=True)'

    reset_object_values_rotate = 'import TheKeyMachine.mods.keyToolsMod as key; key.reset_object_values(reset_rotations=True)'

    delete_animation = 'import TheKeyMachine.mods.barMod as bar; bar.delete_animation()'

    delete_time_slider_animation = 'import TheKeyMachine.mods.barMod as bar; bar.delete_time_slider_animation()'

    selectOpposite = 'import TheKeyMachine.mods.keyToolsMod as key; key.selectOpposite()'

    copyOpposite = 'import TheKeyMachine.mods.keyToolsMod as key; key.copyOpposite()'

    mirror = 'import TheKeyMachine.mods.keyToolsMod as key; key.mirror()'

    copy_animation = 'import TheKeyMachine.mods.keyToolsMod as key; key.copy_animation()'

    paste_animation = 'import TheKeyMachine.mods.keyToolsMod as key; key.paste_animation()'

    paste_insert_animation = 'import TheKeyMachine.mods.keyToolsMod as key; key.paste_insert_animation()'

    paste_opposite_animation = 'import TheKeyMachine.mods.keyToolsMod as key; key.paste_opposite_animation()'

    copy_pose = 'import TheKeyMachine.mods.keyToolsMod as key; key.copy_pose()'

    paste_pose = 'import TheKeyMachine.mods.keyToolsMod as key; key.paste_pose()'

    selectHierarchy = 'import TheKeyMachine.mods.barMod as bar; bar.selectHierarchy()'

    toggleAnimOffsetButton = 'import TheKeyMachine.core.toolbar as toolbar; toolbar.tb.toggleAnimOffsetButton()'

    create_follow_cam = 'import TheKeyMachine.mods.barMod as bar; bar.create_follow_cam(translation=True, rotation=True)'

    copy_link = 'import TheKeyMachine.mods.keyToolsMod as key; key.copy_link()'

    paste_link = 'import TheKeyMachine.mods.keyToolsMod as key; key.copy_link()'

    color_copy_worldspace_animation = 'import TheKeyMachine.mods.barMod as bar; bar.color_copy_worldspace_animation()'

    color_paste_worldspace_animation = 'import TheKeyMachine.mods.barMod as bar; bar.color_paste_worldspace_animation()'

    copy_range_worldspace_animation = 'import TheKeyMachine.mods.barMod as bar; bar.copy_range_worldspace_animation()'

    copy_worldspace_single_frame = 'import TheKeyMachine.mods.barMod as bar; bar.copy_worldspace_single_frame()'

    paste_worldspace_single_frame = 'import TheKeyMachine.mods.barMod as bar; bar.paste_worldspace_single_frame()'

    create_temp_pivot = 'import TheKeyMachine.mods.barMod as bar; bar.create_temp_pivot(False)'

    create_temp_pivot_last = 'import TheKeyMachine.mods.barMod as bar; bar.create_temp_pivot(True)'

    set_auto_tangent = 'import TheKeyMachine.mods.barMod as bar; bar.setTangent("auto")'

    set_spline_tangent = 'import TheKeyMachine.mods.barMod as bar; bar.setTangent("spline")'

    set_linear_tangent = 'import TheKeyMachine.mods.barMod as bar; bar.setTangent("linear")'

    set_step_tangent = 'import TheKeyMachine.mods.barMod as bar; bar.setTangent("step")'

    SelectionSetsToggle = 'import TheKeyMachine.core.toolbar as toolbar; toolbar.tb.toggle_selection_sets_workspace()'



    # Crear hotkeys
    hotkeys = [
        ('openCustomGraph', 'Open customGraph', open_customGraph),
        ('addInbetween', 'Add inbetween', add_inbetween),
        ('removeInbetween', 'Remove inbetween', remove_inbetween),
        ('moveKeyframesRight', 'Move keyframes right', move_keyframes_right),
        ('moveKeyframesLeft', 'Move keyframes left', move_keyframes_left),
        ('smartRotation', 'Smart Rotation Manipulator', smart_rotation),
        ('smartRotationRelease', 'Smart Rotation Manipulator Release', smart_rotation_release),
        ('smartTranslation', 'Smart Translation Manipulator', smart_translation),
        ('smartTranslationRelease', 'Smart Translation Manipulator Release', smart_translation_release),
        ('orbitWindow', 'Open Orbit Window', open_orbit_window),
        ('orbitWindowRelease', 'Close Orbit Window - Release', close_orbit_window),
        ('isolate', 'Isolate tool', isolate_master),
        ('selectRigControls', 'Select Rig Controls', select_rig_controls),
        ('selectAnimatedRigControls', 'Select Animated Rig Controls', select_animated_rig_controls),
        ('depthMover', 'Adjust object depth in camera', depth_mover),
        ('createLocator', 'Create temp locator on the spot in the selected object ', createLocator),
        ('align_selected_objects', 'Align Selected objects ', align_selected_objects),
        ('create_tracer', 'Create Tracer, a custom motion trail in the selected object', create_tracer),
        ('refresh_tracer', 'Refresh Tracer', refresh_tracer),
        ('reset_object_values', 'Reset All Object Values', reset_object_values),
        ('reset_object_values_translate', 'Reset Translate Object Values', reset_object_values_translate),
        ('reset_object_values_rotate', 'Reset Rotation Object Values', reset_object_values_rotate),
        ('delete_animation', 'Delete Objects Animation', delete_animation),
        ('delete_time_slider_animation', 'Delete Selected Time Slider Animation', delete_animation),
        ('selectOpposite', 'Select Opposite', selectOpposite),
        ('copyOpposite', 'Copy Opposite', copyOpposite),
        ('mirror', 'Mirror', mirror),
        ('copy_animation', 'Copy Animation', copy_animation),
        ('paste_animation', 'Paste Animation', paste_animation),
        ('paste_insert_animation', 'Paste Insert Animation', paste_insert_animation),
        ('paste_opposite_animation', 'Paste Opposite Animation', paste_opposite_animation),
        ('copy_pose', 'Copy Pose', copy_pose),
        ('paste_pose', 'Paste Pose', paste_pose),
        ('selectHierarchy', 'Select Hierarchy', selectHierarchy),
        ('toggleAnimOffset', 'Animation Offset Toggle', toggleAnimOffsetButton),
        ('create_follow_cam', 'Create Follow Cam', create_follow_cam),
        ('copy_link', 'Link Objects Copy', copy_link),
        ('paste_link', 'Link Objets Paste', paste_link),
        ('copy_worldspace_animation', 'Copy Worldspace - All Animation', color_copy_worldspace_animation),
        ('paste_worldspace_animation', 'Paste Worldspace', color_paste_worldspace_animation),
        ('copy_range_worldspace_animation', 'Copy Worldspace - Selected Range', copy_range_worldspace_animation),
        ('copy_worldspace_single_frame', 'Copy Worldspace - Current Frame', copy_worldspace_single_frame),
        ('paste_worldspace_single_frame', 'Paste Worldspace - Current Frame', paste_worldspace_single_frame),
        ('create_temp_pivot', 'Create Temp Pivot', create_temp_pivot),
        ('create_temp_pivot_last', 'Create Temp Pivot - Last Pivot Used', create_temp_pivot_last),
        ('set_auto_tangent', 'Set Auto Tangent', set_auto_tangent),
        ('set_spline_tangent', 'Set Auto Tangent', set_spline_tangent),
        ('set_linear_tangent', 'Set Auto Tangent', set_linear_tangent),
        ('set_step_tangent', 'Set Auto Tangent', set_step_tangent),
        ('SelectionSetsToggle', 'Toggle SelectionSets workspace', SelectionSetsToggle),



    ]


    for hotkey_name, annotation, command in hotkeys:
        # Primero, eliminar el comando existente si existe
        if cmds.runTimeCommand(hotkey_name, query=True, exists=True):
            cmds.runTimeCommand(hotkey_name, edit=True, delete=True)

        # Ahora, crear el nuevo comando
        cmds.runTimeCommand(hotkey_name, annotation=annotation, category='TheKeyMachine', command=command)


    cmds.warning("TheKeyMachine hotkeys were added to the Hotkey Editor under Custom Scripts")





# -------------------------------------------------------------------------


def set_smart_key():

    import maya.cmds as cmds
    # Obtén una lista de todos los objetos seleccionados
    selected_objects = cmds.ls(selection=True)

    if not selected_objects:
        print("Select at least one object")
    else:
        # Obtén el tiempo actual
        current_time = cmds.currentTime(query=True)

        # Para cada objeto en la lista de objetos seleccionados, añade un keyframe con la flag "insert"
        for obj in selected_objects:
            cmds.setKeyframe(obj, insert=True, time=current_time)




# -------------- smart rotation

def smart_rotation_manipulator():

    import maya.cmds as cmds
    import maya.mel as mel

    actual_mode = cmds.currentCtx()
    actual_rot_mode = cmds.manipRotateContext('Rotate', q=True, mode=True)

    mel.eval('buildRotateMM')
    current_rotate_mode = cmds.manipRotateContext('Rotate', q=True, mode=True)

    # Si el contexto actual y el anterior son "Rotate", cambiamos el modo
    if actual_mode == 'RotateSuperContext':
        if current_rotate_mode == 0:  # Si está en modo "object"
            cmds.manipRotateContext('Rotate', e=True, mode=1)  # Cambiar a modo "world"
        if current_rotate_mode == 1: # si esta en modo world
            cmds.manipRotateContext('Rotate', e=True, mode=2)  # Cambiar a modo "gimbal"
        if current_rotate_mode == 2: # si esta en modo gimbal
            cmds.manipRotateContext('Rotate', e=True, mode=0)  # Cambiar a modo "object"

# -------------- smart rotation release

def smart_rotation_manipulator_release():
    import maya.mel as mel
    mel.eval('destroySTRSMarkingMenu RotateTool')




# -------------- smart translation

def smart_translate_manipulator():

    import maya.cmds as cmds
    import maya.mel as mel

    actual_mode = cmds.currentCtx()
    actual_move_mode = cmds.manipMoveContext('Move', q=True, mode=True)

    mel.eval('buildTranslateMM')
    current_move_mode = cmds.manipMoveContext('Move', q=True, mode=True)
    if actual_mode == 'moveSuperContext':
        if current_move_mode == 0:  # Si está en modo "world"
            cmds.manipMoveContext('Move', e=True, mode=2)  # Cambiar a modo "object"
        else:
            cmds.manipMoveContext('Move', e=True, mode=0)  # Cambiar a modo "world"



# -------------- smart translation release

def smart_translate_manipulator_release():
    import maya.mel as mel
    mel.eval('destroySTRSMarkingMenu MoveTool')




def add_inbetween(*args):
    mel.eval('timeSliderEditKeys addInbetween')
    currentT = cmds.currentTime(q=True)
    moveLeft = currentT +1
    cmds.currentTime(moveLeft)


def remove_inbetween(*args):
    mel.eval('timeSliderEditKeys removeInbetween')
    currentT = cmds.currentTime(q=True)
    moveLeft = currentT -1
    cmds.currentTime(moveLeft)


def move_keyframes_left():

    import TheKeyMachine.mods.keyToolsMod as keyTools

    desplazamiento = cmds.intField("move_keyframes_int", q=True, value=True)
    desplazamiento = desplazamiento *-1
    keyTools.move_keyframes_in_range(-1)


def move_keyframes_right():

    import TheKeyMachine.mods.keyToolsMod as keyTools

    desplazamiento = cmds.intField("move_keyframes_int", q=True, value=True)
    keyTools.move_keyframes_in_range(desplazamiento)
