


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
import maya.mel as mel
import maya.OpenMayaUI as mui

import os
import sys
import platform
import subprocess
import urllib.request
import importlib

# Try importing PySide2 or PySide6
try:
    from PySide2 import QtWidgets, QtCore, QtGui
    from PySide2.QtWidgets import QApplication, QDesktopWidget
    import shiboken2
    from shiboken2 import wrapInstance
except ImportError:
    from PySide6 import QtWidgets, QtCore, QtGui
    from PySide6.QtWidgets import QApplication
    from PySide6.QtGui import QScreen
    from PySide6.QtCore import QTimer
    import shiboken6
    from shiboken6 import wrapInstance


# -----------------------------------------------------------------------------------------------------------------------------
#                                             Loading necessary modules from TheKeyMachine                                    #
# -----------------------------------------------------------------------------------------------------------------------------

import TheKeyMachine.mods.generalMod as general
import TheKeyMachine.mods.uiMod as ui
import TheKeyMachine.mods.keyToolsMod as keyTools
import TheKeyMachine.mods.selSetsMod as selSets
import TheKeyMachine.mods.mediaMod as media
import TheKeyMachine.mods.styleMod as style

mods = [general,
        ui,
        keyTools,
        selSets,
        media,
        style]

for m in mods:
    importlib.reload(m)




# -----------------------------------------------------------------------------------------------------------------------------
#                                                     Global variables                                                        #
# -----------------------------------------------------------------------------------------------------------------------------


customGraphVersion = general.get_thekeymachine_version()

float_slider = None
slider_value = 0.0
curves_optionMenu = None
customGraphWin = None


curve_mode_slider = None
is_dragging = False
original_keyframes = {}



# -----------------------------------------------------------------------------------------------------------------------------
#                                                       customGraph build                                                     #
# -----------------------------------------------------------------------------------------------------------------------------

def get_screen_resolution():
    app = QApplication.instance()
    if not app:
        app = QApplication([])

    try:
        # PySide2
        from PySide2.QtGui import QDesktopWidget
        desktop = QDesktopWidget()
        screen_rect = desktop.screenGeometry()
    except ImportError:
        # PySide6
        screen = app.primaryScreen()
        screen_rect = screen.geometry()

    screen_width = screen_rect.width()
    screen_height = screen_rect.height()
    
    return screen_width, screen_height


def apply_base_stylesheet(button):
    screen_width, screen_height = get_screen_resolution()
    screen_width = screen_width

    if screen_width == 3840:
        button.setStyleSheet('''
            QPushButton {
                color: #bfbfbf;
                background-color: #555;
                border-radius: 3px;
                font: 16px;
            }
            QPushButton:hover:!pressed {
                color: #ffffff;
                background-color: #646464;
                border-radius: 3px;
                font: 16px;
            }
            QToolTip {
                color: #ccc;
                font-size: 20px;
                border: 2px solid #333;
                background-color:  #4a4a4a;
                padding: 4px;
                border-radius: 4px;
            }

            ''')
    else:
        button.setStyleSheet('''
            QPushButton {
                color: #bfbfbf;
                background-color: #555;
                border-radius: 3px;
                font: 11px;
            }
            QPushButton:hover:!pressed {
                color: #ffffff;
                background-color: #646464;
                border-radius: 3px;
                font: 11px;
            }
            QToolTip {
                color: #ccc;
                font-size: 12px;
                border: 2px solid #333;
                background-color:  #4a4a4a;
                padding: 4px;
                border-radius: 4px;
            }

            ''')






def createCustomGraph():

    #from TheKeyMachine.core.toolbar import tkm_lic_status

    graph_vis = cmds.getPanel(vis=True)

    if "graphEditor1" in graph_vis:
        if cmds.columnLayout("customGraph_columnLayout", exists=True):
            cmds.deleteUI("customGraph_columnLayout")
            cmds.columnLayout("customGraph_columnLayout", adj=1, p="graphEditor1")
        else:
            cmds.columnLayout("customGraph_columnLayout", adj=1, p="graphEditor1")
    else:
        cmds.GraphEditor()
        cmds.columnLayout("customGraph_columnLayout", adj=1, p="graphEditor1")



    cmds.flowLayout(wr=True, h=25, p="customGraph_columnLayout")
    separator = cmds.separator(style='none', width=5)



    #________________ Key Tools Buttons  ___________________#

    screen_width, screen_height = get_screen_resolution()
    screen_width = screen_width




    static_button = cmds.button(l='Static', c=lambda x: keyTools.deleteStaticCurves(), h=20, w=40)
    static_button_widget = wrapInstance(int(mui.MQtUtil.findControl(static_button)), QtWidgets.QPushButton)
    static_button_widget.setToolTip("Remove all statics curves")
    apply_base_stylesheet(static_button_widget)


    share_button = cmds.button(l='Share', c=lambda x: keyTools.shareKeys(), h=20, w=40)
    share_button_widget = wrapInstance(int(mui.MQtUtil.findControl(share_button)), QtWidgets.QPushButton)
    share_button_widget.setToolTip("Share keys between curves to ensure both curves have the same keys in the same position.<br><br> The first curve selected is the reference curve, which will share the position of its keys.")
    apply_base_stylesheet(share_button_widget)


    match_button = cmds.button(l='Match', c=lambda x: keyTools.match_keys(), h=20, w=45, annotation='First selected curve is the reference curve.\nAll other curves will be matched to the reference curve\n At least one keyframe need on the second curve')
    match_button_widget = wrapInstance(int(mui.MQtUtil.findControl(match_button)), QtWidgets.QPushButton)
    match_button_widget.setToolTip("Makes a match of one curve with another, in this way both curves will be the same.<br><br> The last curve in the selection will be the reference curve")
    apply_base_stylesheet(match_button_widget)


    flip_button = cmds.button(l='Flip', c=lambda x: keyTools.flipCurves(), h=20, w=40)
    flip_button_widget = wrapInstance(int(mui.MQtUtil.findControl(flip_button)), QtWidgets.QPushButton)
    flip_button_widget.setToolTip("Inverts the selected curve vertically.<br><br> Right-click to see more options.")
    apply_base_stylesheet(flip_button_widget)


    clean_button = cmds.button(l='Snap', c=lambda x: keyTools.snapKeyframes(), h=20, w=42)
    clean_button_widget = wrapInstance(int(mui.MQtUtil.findControl(clean_button)), QtWidgets.QPushButton)
    clean_button_widget.setToolTip(
        "Performs a cleanup and repositioning of the keys that are in a sub-frame "
        "to the nearest frame.<br><br>This tool doesn't just perform a simple snap, but "
        "it ensures to clean up and prevent multiple keyframes in the same frame.<br><br> "
        "Ideal for after scaling an animation."
    )
    apply_base_stylesheet(clean_button_widget)

    
    overlap_button = cmds.button(l='Overlap', c=keyTools.mod_overlap_animation, h=20, w=50)
    overlap_button_widget = wrapInstance(int(mui.MQtUtil.findControl(overlap_button)), QtWidgets.QPushButton)
    overlap_button_widget.setToolTip(
        "Applies an overlap frame to the selected curves or selected channels in the ChannelBox.<br><br>"
        "The application order is based on the selection order of the objects in the 3D view.<br><br>"
        "Use the <b>'Shift'</b> key to apply the overlap in the opposite direction."
    )
    apply_base_stylesheet(overlap_button_widget)

    reblock_button = cmds.button(l='reBlock', c=keyTools.reblock_move, h=20, w=50)
    reblock_button_widget = wrapInstance(int(mui.MQtUtil.findControl(reblock_button)), QtWidgets.QPushButton)
    reblock_button_widget.setToolTip(
        "reBlock allows you to realign all the curves so that all their keyframes match up with "
        "each other.<br><br> This tool is specially designed for the blocking process, where all the curves "
        "have keyframes in the same positions.<br> If for some reason this relationship is lost, this "
        "tool lets you recover that relationship.<br>"
    )
    apply_base_stylesheet(reblock_button_widget)


    flip_popup_menu = cmds.popupMenu(parent=flip_button)
    cmds.menuItem(label='Flip Curves', command=lambda x: keyTools.flipCurves(), parent=flip_popup_menu)
    cmds.menuItem(label='Flip from Selected Keyframe', command=lambda x: keyTools.flipFromKeyframe(), parent=flip_popup_menu)
    cmds.menuItem(label='Flip Selected Group', command=lambda x: keyTools.flipKeyGroup(), parent=flip_popup_menu)

    separator = cmds.separator(style='none', width=7)

    extra_button = cmds.button(l='Extra', c=lambda x: keyTools.snapKeyframes(), h=20, w=40)
    extra_button_widget = wrapInstance(int(mui.MQtUtil.findControl(extra_button)), QtWidgets.QPushButton)
    apply_base_stylesheet(extra_button_widget)

    extra_popup_menu = cmds.popupMenu(parent=extra_button, button=1, ctl=False, alt=False)
    cmds.menuItem(label="Select object from selected curve", parent=extra_popup_menu, c=lambda x: keyTools.select_objects_from_selected_curves())


    separator = cmds.separator(style='none', width=10)



    #___________________ Tween Machine  ____________________#


    cmds.separator(style='none', width=2)
    
    tweenSliderLabel=cmds.text(label="T")
    separator = cmds.separator(style='none', width=4)
    tweenSlider = cmds.floatSlider("customGraph_tween_slider", width=140, min=-20, max=120, value=50, step=1, ann="TweenMachine", 
                       dragCommand=lambda x: keyTools.tween(x, slider_name="customGraph_tween_slider"), 
                       changeCommand=lambda x: keyTools.tweenSliderReset(tweenSlider))

    tweenSlider_widget = wrapInstance(int(mui.MQtUtil.findControl(tweenSlider)), QtWidgets.QSlider)
    
    tweenSlider_bg_color= "#323232"
    tweenSlider_tick_color = "#adb66a"

    styleSheet = '''
        QSlider {{
            color: #909090;
            font: 10px;
        }}

        QSlider::groove:horizontal {{
            height: 2px;
            border: 2px solid {bg_color};
            background: qlineargradient(x1:0, y1:0, x2:1, y2:0, 
                            stop:0    {tick_color},
                            stop:0.02 {tick_color},
                            stop:0.03 {bg_color},

                            stop:0.15  {bg_color},
                            stop:0.155 {tick_color},
                            stop:0.165 {tick_color},  
                            stop:0.17 {bg_color},


                            stop:0.32 {bg_color},                   
                            stop:0.325 {tick_color},
                            stop:0.335 {tick_color},
                            stop:0.336 {bg_color},


                            stop:0.5 {bg_color},
                            stop:0.505  {tick_color},
                            stop:0.51  {tick_color},
                            stop:0.515 {bg_color},


                            stop:0.67 {bg_color},
                            stop:0.675 {tick_color},
                            stop:0.685 {tick_color},
                            stop:0.688 {bg_color},



                            stop:0.835 {bg_color},
                            stop:0.84 {tick_color},
                            stop:0.854  {tick_color},
                            stop:0.858 {bg_color},


                            stop:0.92 {bg_color},
                            stop:0.97 {bg_color},
                            stop:0.98 {tick_color},
                            stop:1    {tick_color});
            border-radius: 2.5px; /* Mitad de la altura para un rastro totalmente redondeado */
        }}

        QSlider::handle:horizontal {{
            background-color: #afafaf;
            height: 10px;
            width: 8px;
            margin: -5px 0;
            border-radius: 2px;
        }}
    '''.format(bg_color=tweenSlider_bg_color, tick_color=tweenSlider_tick_color)

    tweenSlider_widget.setStyleSheet(styleSheet)

    separator = cmds.separator(style='none', width=15)




    #____________________ Curve Tools  _____________________#




    def curve_mode_changed(*args):
        mode = cmds.optionMenu(curves_option_menu, query=True, value=True)
        if mode == "Smooth":
            cmds.floatSlider(curve_mode_slider, edit=True, min=0.0, max=0.5, value=0)
        elif mode == "Wave":
            cmds.floatSlider(curve_mode_slider, edit=True, min=-1, max=1, value=0)
        elif mode == "Scale":
            cmds.floatSlider(curve_mode_slider, edit=True, min=0.7, max=1.3, value=1)
        elif mode == "Scale Sel":
            cmds.floatSlider(curve_mode_slider, edit=True, min=0.7, max=1.3, value=1)
        elif mode == "Lineal":
            cmds.floatSlider(curve_mode_slider, edit=True, min=0.0, max=1.0, value=0)
        elif mode == "Flat":
            cmds.floatSlider(curve_mode_slider, edit=True, min=0, max=1.0, value=0)
        elif mode == "Ease in/out":
            cmds.floatSlider(curve_mode_slider, edit=True, min=0, max=1, value=0.5)
        elif mode == "Noise":
            cmds.floatSlider(curve_mode_slider, edit=True, min=0.0, max=0.5, value=0)
        elif mode == "Add":
            cmds.floatSlider(curve_mode_slider, edit=True, min=0.0, max=0.5, value=0)
        sliderReset()

    def curve_mode_slider_change(value):
        mode = cmds.optionMenu(curves_option_menu, query=True, value=True)
        if mode == "Smooth":
            apply_curves_smooth_function(value)
        elif mode == "Wave":
            apply_curves_wave_function(value)
        elif mode == "Scale":
            apply_curves_scale_function(value)
        elif mode == "Scale Sel":
            scale_curves_from_point(value)
        elif mode == "Lineal":
            apply_curves_linear_function(value)
        elif mode == "Flat":
            apply_curves_flat_function(value)
        elif mode == "Ease in/out":
            apply_curves_ease_function(value)
        elif mode == "Noise":
            apply_curves_noise_function(value)
        elif mode == "Add":
            add_random_keyframes_to_curve(value)





    # _____________ Add keyframes to curve
    import random
    generated_keyframe_positions = {}

    def reset_generated_positions(curve):
        keyframes = cmds.keyframe(curve, query=True, selected=True, timeChange=True)
        if keyframes:
            # Generar posiciones entre los keyframes existentes
            generated_keyframe_positions[curve] = []
            for i in range(1, len(keyframes)):
                start = int(keyframes[i-1])
                end = int(keyframes[i])
                generated_keyframe_positions[curve].extend(range(start + 1, end))

            random.shuffle(generated_keyframe_positions[curve])


    def add_random_keyframes_to_curve(value):
        global is_dragging

        curves = curves = cmds.keyframe(query=True, name=True, sl=True)
        if curves:
            for curve in curves:
                # Si la curva no tiene posiciones generadas o si se ha hecho un undo, reiniciar
                if curve not in generated_keyframe_positions or not cmds.keyframe(curve, query=True, timeChange=True):
                    reset_generated_positions(curve)
                    
                if not is_dragging:
                    cmds.undoInfo(openChunk=True)
                    is_dragging = True
                
                # Añadir un keyframe en la siguiente posición aleatoria disponible
                if generated_keyframe_positions[curve]:
                    next_position = generated_keyframe_positions[curve].pop(0)
                    current_value = cmds.keyframe(curve, query=True, eval=True, time=(next_position,))[0]
                    cmds.setKeyframe(curve, time=next_position, value=current_value)
                    
                else:
                    print("No more available positions to add keyframes.")
        else:
            print("Please select at least one animation curve in the Graph Editor.")




    # _____________ SCALE Selection

    def scale_curves_from_point(factor):
        global original_keyframes, is_dragging

        curves = cmds.keyframe(query=True, name=True, sl=True)

        if curves:
            for curve in curves:
                keyframes = cmds.keyframe(curve, query=True, timeChange=True, valueChange=True)
                selected_keyframes = cmds.keyframe(curve, query=True, selected=True, timeChange=True, valueChange=True)
                if keyframes and len(keyframes) % 2 == 0:
                    if curve not in original_keyframes:
                        # Store the original keyframes if they haven't been stored for this curve yet
                        original_keyframes[curve] = keyframes.copy()
                    if not is_dragging:
                        # Open an undo chunk only if is_dragging is False
                        cmds.undoInfo(openChunk=True)
                        is_dragging = True

                    if selected_keyframes and len(selected_keyframes) % 2 == 0:
                        # Use the mean of the selected keyframes
                        reference_keyframes = selected_keyframes
                    else:
                        # Use the mean of all keyframes
                        reference_keyframes = original_keyframes[curve]

                    mean_value = sum(reference_keyframes[i+1] for i in range(0, len(reference_keyframes), 2)) / (len(reference_keyframes) / 2)

                    for i in range(0, len(keyframes), 2):
                        time = keyframes[i]
                        initial_value = original_keyframes[curve][i + 1]
                        new_value = mean_value + (initial_value - mean_value) * factor
                        cmds.keyframe(curve, edit=True, time=(time, time), valueChange=new_value)
        else:
            print("Please select at least one animation curve in the Graph Editor.")



    # _____________ SCALE

    def apply_curves_scale_function(factor):
        global original_keyframes, is_dragging

        curves = cmds.selectionConnection('graphEditor1FromOutliner', query=True, object=True)
        if curves:
            for curve in curves:
                keyframes = cmds.keyframe(curve, query=True, selected=True, timeChange=True, valueChange=True)
                if keyframes and len(keyframes) % 2 == 0:
                    if curve not in original_keyframes:
                        # Store the original keyframes if they haven't been stored for this curve yet
                        original_keyframes[curve] = keyframes.copy()
                    if not is_dragging:
                        # Open an undo chunk only if is_dragging is False
                        cmds.undoInfo(openChunk=True)
                        is_dragging = True
                    mean_value = sum(original_keyframes[curve][i+1] for i in range(0, len(original_keyframes[curve]), 2)) / (len(original_keyframes[curve]) / 2)
                    for i in range(0, len(keyframes), 2):
                        time = keyframes[i]
                        initial_value = original_keyframes[curve][i + 1]
                        new_value = mean_value + (initial_value - mean_value) * factor
                        cmds.keyframe(curve, edit=True, time=(time, time), valueChange=new_value)

        else:
            print("Please select at least one animation curve in the Graph Editor.")



    # ______________ SMOOTH

    def apply_curves_smooth_function(factor):
        global is_dragging, original_keyframes

        curves = cmds.selectionConnection('graphEditor1FromOutliner', query=True, object=True)
        if curves:
            for curve in curves:
                keyframes = cmds.keyframe(curve, query=True, selected=True, valueChange=True)
                if not keyframes:
                    continue

                if curve not in original_keyframes:
                    original_keyframes[curve] = keyframes.copy()

                if not is_dragging:
                    cmds.undoInfo(openChunk=True)
                    is_dragging = True
                
                curves_smooth(curve, factor)
        else:
            print("Please select at least one animation curve in the Graph Editor.")



    def curves_smooth(selection, power=0.1):
        keys = cmds.keyframe(selection, query=True, selected=True)
        if not keys:
            return

        for key in keys:
            time = cmds.keyframe(selection, query=True, time=(key, key))
            value = cmds.keyframe(selection, query=True, time=(key, key), valueChange=True)
            
            prev_time = cmds.findKeyframe(selection, time=(time[0],), which='previous')
            prev_value = cmds.keyframe(selection, query=True, time=(prev_time, prev_time), valueChange=True) if prev_time else value
            
            next_time = cmds.findKeyframe(selection, time=(time[0],), which='next')
            next_value = cmds.keyframe(selection, query=True, time=(next_time, next_time), valueChange=True) if next_time else value
            
            # Asegurarse de que no estamos dividiendo por cero
            if prev_time and prev_time != time[0]:
                prev_diff = abs(time[0] - prev_time)
                weight_prev = 1.0 / prev_diff
            else:
                prev_diff = 0
                weight_prev = 0

            if next_time and next_time != time[0]:
                next_diff = abs(next_time - time[0])
                weight_next = 1.0 / next_diff
            else:
                next_diff = 0
                weight_next = 0
            
            # Ensure that at least one weight is non-zero to avoid division by zero
            if weight_prev + weight_next > 0:
                avg = (prev_value[0] * weight_prev + next_value[0] * weight_next) / (weight_prev + weight_next)
                smoothed_value = value[0] + (avg - value[0]) * power
                cmds.keyframe(selection, edit=True, time=(time[0], time[0]), valueChange=smoothed_value)





    # ______________NOISE

    import random

    # Diccionario para almacenar el ruido inicial de cada clave
    initial_noise_values = {}

    def apply_curves_noise_function(value):
        global original_keyframes, is_dragging

        curves = cmds.selectionConnection('graphEditor1FromOutliner', query=True, object=True)
        if curves:
            for curve in curves:
                keyframes = cmds.keyframe(curve, query=True, selected=True, timeChange=True, valueChange=True)
                if keyframes and len(keyframes) % 2 == 0:
                    if curve not in original_keyframes:
                        original_keyframes[curve] = keyframes.copy()
                        # Inicializa el ruido inicial para cada clave
                        initial_noise_values[curve] = [random.uniform(-1, 1) for _ in range(len(keyframes) // 2)]
                        
                    if not is_dragging:
                        cmds.undoInfo(openChunk=True)
                        is_dragging = True
                    
                    for i in range(0, len(keyframes), 2):
                        time = keyframes[i]
                        initial_value = original_keyframes[curve][i + 1]
                        
                        # Escala el valor de ruido inicial con el slider
                        noise = initial_noise_values[curve][i // 2] * value
                        new_value = initial_value + noise
                        
                        cmds.keyframe(curve, edit=True, time=(time, time), valueChange=new_value)
                else:
                    print("")
        else:
            print("Please select at least one animation curve in the Graph Editor.")




    # ______________WAVE

    def apply_curves_wave_function(value):
        global original_keyframes, is_dragging

        curves = cmds.selectionConnection('graphEditor1FromOutliner', query=True, object=True)
        if curves:
            for curve in curves:
                keyframes = cmds.keyframe(curve, query=True, selected=True, timeChange=True, valueChange=True)
                if keyframes and len(keyframes) % 2 == 0:
                    if curve not in original_keyframes:
                        # Store the original keyframes if they haven't been stored for this curve yet
                        original_keyframes[curve] = keyframes.copy()
                    if not is_dragging:
                        # Open an undo chunk only if is_dragging is False
                        cmds.undoInfo(openChunk=True)
                        is_dragging = True
                    for i in range(0, len(keyframes), 2):
                        time = keyframes[i]
                        initial_value = original_keyframes[curve][i + 1]
                        direction = 1 if (i // 2) % 2 == 0 else -1
                        new_value = initial_value + direction * value
                        cmds.keyframe(curve, edit=True, time=(time, time), valueChange=new_value)
                else:
                    print("")
        else:
            print("Please select at least one animation curve in the Graph Editor.")





    # __________ LINEAR


    def curves_linear_interpolation(curve, blend_factor=1.0):
        global original_keyframes, is_dragging

        keyframes = cmds.keyframe(curve, query=True, selected=True, timeChange=True, valueChange=True)

        if not keyframes or len(keyframes) % 2 != 0:
            print(f"Please select at least one keyframe on curve {curve}.")
            return

        # Store original keyframes for undo
        if curve not in original_keyframes:
            original_keyframes[curve] = keyframes.copy()

        # First and last keyframes remain unchanged
        min_time, min_value = keyframes[0], keyframes[1]
        max_time, max_value = keyframes[-2], keyframes[-1]

        for i in range(2, len(keyframes) - 2, 2):
            time = keyframes[i]
            original_value = original_keyframes[curve][i + 1]
            t = (time - min_time) / (max_time - min_time)
            new_value = min_value + t * (max_value - min_value)
            blended_value = original_value + blend_factor * (new_value - original_value)
            cmds.keyframe(curve, edit=True, time=(time, time), valueChange=blended_value)


    def apply_curves_linear_function(blend_factor=1.0):
        global is_dragging

        if not is_dragging:
            cmds.undoInfo(openChunk=True)
            is_dragging = True

        curves = cmds.selectionConnection('graphEditor1FromOutliner', query=True, object=True)
        if curves:
            for curve in curves:
                curves_linear_interpolation(curve, blend_factor)
        else:
            print("Please select at least one animation curve in the Graph Editor.")



    # _______________ EASE IN/OUT

    def lerp(a, b, t):
        """Linear interpolation."""
        return a + (b - a) * t

    def ease_in(t, power=3):
        return pow(t, power)

    def ease_out(t, power=3):
        return 1 - pow(1 - t, power)

    def apply_curves_ease_function(factor):
        global original_keyframes, is_dragging

        curves = cmds.selectionConnection('graphEditor1FromOutliner', query=True, object=True)
        if curves:
            for curve in curves:
                if curve not in original_keyframes:
                    # Almacena los keyframes originales
                    original_keyframes[curve] = cmds.keyframe(curve, query=True, valueChange=True, selected=True)
                
                if not is_dragging:
                    cmds.undoInfo(openChunk=True)
                    is_dragging = True

                if factor < 0.5:
                    ease_curves(curve, 1 - (factor * 2), ease_in)  # Cambio de ease_out a ease_in
                else:
                    ease_curves(curve, (factor - 0.5) * 2, ease_out) 
                    
        else:
            print("Please select at least one animation curve in the Graph Editor.")


    def ease_curves(curve, factor, ease_func):
        keys = cmds.keyframe(curve, query=True, selected=True)
        if not keys:
            return

        first_key = keys[0]
        last_key = keys[-1]
        total_time = last_key - first_key

        for i, key in enumerate(keys):
            elapsed_time = key - first_key
            time_position = elapsed_time / total_time

            eased_position = ease_func(time_position, power=factor*3+1)
            
            new_value = lerp(original_keyframes[curve][i], lerp(original_keyframes[curve][0], original_keyframes[curve][-1], eased_position), factor)
            
            cmds.keyframe(curve, edit=True, time=(key, key), valueChange=new_value)




    # __________________ FLAT


    def curves_flat_interpolation(curve, blend_factor=1.0):
        global original_keyframes, is_dragging

        keyframes = cmds.keyframe(curve, query=True, selected=True, timeChange=True, valueChange=True)

        if not keyframes or len(keyframes) % 2 != 0:
            print(f"Please select at least one keyframe on curve {curve}.")
            return

        # Store original keyframes for undo
        if curve not in original_keyframes:
            original_keyframes[curve] = keyframes.copy()

        # Calculate average value
        total_value = 0
        for i in range(1, len(keyframes), 2):
            total_value += keyframes[i]
        average_value = total_value / (len(keyframes) / 2)

        # Set all keys to average value
        for i in range(0, len(keyframes), 2):
            time = keyframes[i]
            original_value = original_keyframes[curve][i + 1]
            blended_value = original_value + blend_factor * (average_value - original_value)
            cmds.keyframe(curve, edit=True, time=(time, time), valueChange=blended_value)

    def apply_curves_flat_function(blend_factor=1.0):
        global is_dragging

        if not is_dragging:
            cmds.undoInfo(openChunk=True)
            is_dragging = True

        curves = cmds.selectionConnection('graphEditor1FromOutliner', query=True, object=True)
        if curves:
            for curve in curves:
                curves_flat_interpolation(curve, blend_factor)
        else:
            print("Please select at least one animation curve in the Graph Editor.")





    def sliderReset(*args):
        global is_dragging, original_keyframes
        original_keyframes = {}
        generated_keyframe_positions.clear()

        if is_dragging:
            cmds.undoInfo(closeChunk=True)
            is_dragging = False

        current_option = cmds.optionMenu(curves_option_menu, query=True, value=True)
        
        reset_value = 0  # Por defecto es 0
        if current_option == "Add":
            reset_value = 0
        if current_option == "Ease in/out":
            reset_value = 0.5
        if current_option == "Flat":
            reset_value = 0
        if current_option == "Lineal":
            reset_value = 0
        if current_option == "Noise":
            reset_value = 0
        if current_option == "Scale":
            reset_value = 1
        if current_option == "Scale Sel":
            reset_value = 1
        if current_option == "Smooth":
            reset_value = 0
        if current_option == "Wave":
            reset_value = 0

        cmds.floatSlider(curve_mode_slider, edit=True, value=reset_value)


    #global curve_mode_slider, curves_option_menu

    curve_mode_slider = cmds.floatSlider(width=140, min=0, max=1, value=0,
                               dragCommand=curve_mode_slider_change,
                               changeCommand=sliderReset)

    curve_mode_slider_widget = wrapInstance(int(mui.MQtUtil.findControl(curve_mode_slider)), QtWidgets.QSlider)
    
    curve_mode_slider_bg_color= "#323232"
    curve_mode_slider_tick_color = "#90d074"

    styleSheet = '''
        QSlider {{
            color: #909090;
            font: 10px;
        }}

        QSlider::groove:horizontal {{
            height: 2px;
            border: 2px solid {bg_color};
            background: qlineargradient(x1:0, y1:0, x2:1, y2:0, 
                            stop:0    {tick_color},
                            stop:0.02 {tick_color},
                            stop:0.03 {bg_color},
                            stop:0.24 {bg_color},
                            stop:0.25 {tick_color},
                            stop:0.26 {bg_color},
                            stop:0.49 {bg_color},
                            stop:0.5  {tick_color},
                            stop:0.51 {bg_color},
                            stop:0.74 {bg_color},
                            stop:0.75 {tick_color},
                            stop:0.76 {bg_color},
                            stop:0.97 {bg_color},
                            stop:0.98 {tick_color},
                            stop:1    {tick_color});
            border-radius: 2.5px; /* Mitad de la altura para un rastro totalmente redondeado */
        }}

        QSlider::handle:horizontal {{
            background-color: #afafaf;
            height: 10px;
            width: 8px;
            margin: -5px 0;
            border-radius: 2px;
        }}
    '''.format(bg_color=curve_mode_slider_bg_color, tick_color=curve_mode_slider_tick_color)

    curve_mode_slider_widget.setStyleSheet(styleSheet)

    separator = cmds.separator(style='none', width=5)
    curves_option_menu = cmds.optionMenu(label='', width=90, changeCommand=curve_mode_changed)
    cmds.menuItem(label='Add')
    cmds.menuItem(label='Ease in/out')
    cmds.menuItem(label='Flat')
    cmds.menuItem(label='Lineal')
    cmds.menuItem(label='Noise')
    cmds.menuItem(label='Scale')
    cmds.menuItem(label='Scale Sel')
    cmds.menuItem(label='Smooth')
    cmds.menuItem(label='Wave')





    #_________________  Iso / Mute / Lock  _________________#
    separator = cmds.separator(style='none', width=12)
    iso_button = cmds.button(l='Iso', c=lambda x: keyTools.isolateCurve(), h=20, w=40)
    iso_button_widget = wrapInstance(int(mui.MQtUtil.findControl(iso_button)), QtWidgets.QPushButton)
    apply_base_stylesheet(iso_button_widget)


    mute_button = cmds.button(l='Mute', c=lambda x: keyTools.toggleMute(), h=20, w=40)
    mute_button_widget = wrapInstance(int(mui.MQtUtil.findControl(mute_button)), QtWidgets.QPushButton)
    apply_base_stylesheet(mute_button_widget)

    lock_button = cmds.button(l='Lock', c=lambda x: keyTools.toggleLock(), h=20, w=40)
    lock_button_widget = wrapInstance(int(mui.MQtUtil.findControl(lock_button)), QtWidgets.QPushButton)
    apply_base_stylesheet(lock_button_widget)


    separator = cmds.separator(style='none', width=5)
    filter_button = cmds.button(l='Filter', h=20, w=40, c=lambda x: ui.customGraph_filter_mods())
    filter_button_widget = wrapInstance(int(mui.MQtUtil.findControl(filter_button)), QtWidgets.QPushButton)
    filter_button_widget.setToolTip(
        "The filter mode is used to filter the selection in the GraphEditor.<br> In this way, only certain animation channels are displayed<br><br>"
        "To use this tool:<br><br> "
        "- Select the channel or channels you want to filter in the ChannelBox (for example, RotateX)<br>"
        "- Press the 'Filter' button.<br>"
        "- All the controls that you select from now on will only show the RotateX channel."
        "<br><br>"
        "To break the filter, click on the filter menu icon located in the GraphEditor at the top left.<br><br>"
        "<font style='color: #869fac; font-size:11px;'><b>Shortcuts:</b></font><br>"
        "<font style='color: #869fac; font-size:11px;'>Shift + Click&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp; Desactive filter</font><br>"

    )

    apply_base_stylesheet(filter_button_widget)


    #____________________  Resets  _________________________#
    separator = cmds.separator(style='none', width=5)
    resetCurves_button = cmds.button(l='Reset', c=lambda x: keyTools.get_default_value_main(), h=20, w=40)
    resetCurves_button_widget = wrapInstance(int(mui.MQtUtil.findControl(resetCurves_button)), QtWidgets.QPushButton)
    resetCurves_button_widget.setToolTip(
        "Reset the selected curves to their default values<br>"
    )
    if screen_width == 3840:
        resetCurves_button_widget.setStyleSheet('''
            QPushButton {
                color: #f39090;
                background-color: #555555;
                border-radius: 3px;
                font: 16px;
            }
            QPushButton:hover:!pressed {
                color: #ffffff;
                background-color: #646464;
                border-radius: 3px;
                font: 16px;
            }
            QToolTip {
                color: #ccc;
                font-size: 20px;
                border: 2px solid #333;
                background-color:  #4a4a4a;
                padding: 4px;
                border-radius: 4px;
            }

            ''')
    else:
        resetCurves_button_widget.setStyleSheet('''
            QPushButton {
                color: #f39090;
                background-color: #555555;
                border-radius: 3px;
                font: 11px;
            }
            QPushButton:hover:!pressed {
                color: #ffffff;
                background-color: #646464;
                border-radius: 3px;
                font: 11px;
            }
            QToolTip {
                color: #ccc;
                font-size: 12px;
                border: 2px solid #333;
                background-color:  #4a4a4a;
                padding: 4px;
                border-radius: 4px;
            }

            ''')






    #________________  SelSets Buttons  ____________________#
    separator = cmds.separator(style='none', width=10)
    set01 = cmds.button(l=' 1 ', h=20, w=22, annotation='SelSet 01')
    set01_button_widget = wrapInstance(int(mui.MQtUtil.findControl(set01)), QtWidgets.QPushButton)
    if screen_width == 3840:
        set01_button_widget.setStyleSheet('''
            QPushButton {
                color: #333333;
                background-color: #CBC8AD;
                border-radius: 3px;
                font: 16px;
            }
            QPushButton:hover:!pressed {
                color: #333333;
                background-color: #E0DDBE;
                border-radius: 3px;
                font: 16px;
            }

            ''')
    else:
        set01_button_widget.setStyleSheet('''
        QPushButton {
            color: #333333;
            background-color: #CBC8AD;
            border-radius: 3px;
            font: 11px;
        }
        QPushButton:hover:!pressed {
            color: #333333;
            background-color: #E0DDBE;
            border-radius: 3px;
            font: 11px;
        }

        ''')



    set02 = cmds.button(l=' 2 ', h=20, w=22, annotation='SelSet 02')
    set02_button_widget = wrapInstance(int(mui.MQtUtil.findControl(set02)), QtWidgets.QPushButton)
    if screen_width == 3840: 
        set02_button_widget.setStyleSheet('''
            QPushButton {
                color: #333333;
                background-color: #7BA399;
                border-radius: 3px;
                font: 16px;
            }
            QPushButton:hover:!pressed {
                color: #333333;
                background-color: #97C7BB;
                border-radius: 3px;
                font: 16px;
            }

            ''')
    else:
        set02_button_widget.setStyleSheet('''
            QPushButton {
                color: #333333;
                background-color: #7BA399;
                border-radius: 3px;
                font: 11px;
            }
            QPushButton:hover:!pressed {
                color: #333333;
                background-color: #97C7BB;
                border-radius: 3px;
                font: 11px;
            }

            ''')


    set03 = cmds.button(l=' 3 ', h=20, w=22, annotation='SelSet 03')
    set03_button_widget = wrapInstance(int(mui.MQtUtil.findControl(set03)), QtWidgets.QPushButton)
    if screen_width == 3840: 
        set03_button_widget.setStyleSheet('''
            QPushButton {
                color: #333333;
                background-color: #93C2AD;
                border-radius: 3px;
                font: 16px;
            }
            QPushButton:hover:!pressed {
                color: #333333;
                background-color: #A4DCC3;
                border-radius: 3px;
                font: 16px;
            }

            ''')
    else:
        set03_button_widget.setStyleSheet('''
            QPushButton {
                color: #333333;
                background-color: #93C2AD;
                border-radius: 3px;
                font: 11px;
            }
            QPushButton:hover:!pressed {
                color: #333333;
                background-color: #A4DCC3;
                border-radius: 3px;
                font: 11px;
            }

            ''')

    set04 = cmds.button(l=' 4 ', h=20, w=22, annotation='SelSet 04')
    set04_button_widget = wrapInstance(int(mui.MQtUtil.findControl(set04)), QtWidgets.QPushButton)
    if screen_width == 3840:
        set04_button_widget.setStyleSheet('''
            QPushButton {
                color: #333333;
                background-color: #C29591;
                border-radius: 3px;
                font: 16px;
            }
            QPushButton:hover:!pressed {
                color: #333333;
                background-color: #DCA9A4;
                border-radius: 3px;
                font: 16px;
            }

            ''')
    else:
        set04_button_widget.setStyleSheet('''
            QPushButton {
                color: #333333;
                background-color: #C29591;
                border-radius: 3px;
                font: 11px;
            }
            QPushButton:hover:!pressed {
                color: #333333;
                background-color: #DCA9A4;
                border-radius: 3px;
                font: 11px;
            }

            ''')


    set05 = cmds.button(l=' 5 ', h=20, w=22, annotation='SelSet 05')
    set05_button_widget = wrapInstance(int(mui.MQtUtil.findControl(set05)), QtWidgets.QPushButton)
    if screen_width == 3840:
        set05_button_widget.setStyleSheet('''
            QPushButton {
                color: #333333;
                background-color: #A86465;
                border-radius: 3px;
                font: 16px;
            }
            QPushButton:hover:!pressed {
                color: #333333;
                background-color: #CD7C7E;
                border-radius: 3px;
                font: 16px;
            }

            ''')
    else:
        set05_button_widget.setStyleSheet('''
            QPushButton {
                color: #333333;
                background-color: #A86465;
                border-radius: 3px;
                font: 11px;
            }
            QPushButton:hover:!pressed {
                color: #333333;
                background-color: #CD7C7E;
                border-radius: 3px;
                font: 11px;
            }

            ''')





    # ____________________________

    separator = cmds.separator(style='none', width=10)
    match_curve_cycle_button = cmds.iconTextButton(l="", w=22, h=24, image=media.match_curve_cycle_image, c=keyTools.match_curve_cycle)
    match_curve_cycle_button_widget = wrapInstance(int(mui.MQtUtil.findControl(match_curve_cycle_button)), QtWidgets.QPushButton)
    match_curve_cycle_button_widget.setToolTip(
        "Curve cycle matcher."
    )

    match_curve_cycle_button_widget.setStyleSheet('''
        QPushButton {

        }
        QPushButton:hover:!pressed {

        }
        QToolTip {
            color: #ccc;
            font-size: 12px;
            border: 2px solid #333;
            background-color:  #4a4a4a;
            padding: 4px;
            border-radius: 4px;
        }

        ''')


    bouncy_curve_button = cmds.iconTextButton(l="", w=22, h=24, image=media.bouncy_curve_image, c=keyTools.bouncy_tangets)
    bouncy_curve_button_widget = wrapInstance(int(mui.MQtUtil.findControl(bouncy_curve_button)), QtWidgets.QPushButton)
    bouncy_curve_button_widget.setToolTip(
        "Set bouncy tangents."
    )

    bouncy_curve_button_widget.setStyleSheet('''
        QPushButton {

        }
        QPushButton:hover:!pressed {

        }
        QToolTip {
            color: #ccc;
            font-size: 12px;
            border: 2px solid #333;
            background-color:  #4a4a4a;
            padding: 4px;
            border-radius: 4px;
        }

        ''')






    #_________________  Opacity Slider  ____________________#


    def set_opacity_from_slider(value):
        graph_editor_window = get_graph_editor_window()
        if graph_editor_window is None:
            cmds.warning("GraphEditor opacity is not available when it's docked")
        else:
            graph_editor_window.setWindowOpacity(value)

    def get_graph_editor_window():
        if not cmds.window('graphEditor1Window', exists=True):
            cmds.GraphEditor()
        ptr = mui.MQtUtil.findWindow('graphEditor1Window')
        if ptr is not None:
            try:
                return shiboken2.wrapInstance(int(ptr), QtWidgets.QWidget)
            except:
                return shiboken6.wrapInstance(int(ptr), QtWidgets.QWidget)
        else:
            return None




    # La opacidad si graph editor esta docked hace crashear Maya. Si GE esta en modo docked se elimina el slider 
    separator = cmds.separator(style='none', width=10)

    if cmds.window("graphEditor1Window", exists=True):
        float_slider = cmds.floatSlider(min=0.1, max=1.0, v=1.0, dragCommand=lambda x: set_opacity_from_slider(x), w=40, hr=True)
        separator = cmds.separator(style='none', width=5)
    else:
        print("")



    #______________________  iMenu  ________________________#
    about_button = cmds.iconTextButton(l='  i  ', image=media.settings_cg_image, h=22, w=22, annotation='About')
    popup_menu = cmds.popupMenu(parent=about_button, button=1, ctl=False, alt=False)
    
    customGraph_help_submenu = cmds.menuItem(subMenu=True, label="Help", image=media.help_menu_image, parent=popup_menu)
    cmds.menuItem(l="Discord Community", image=media.help_menu_image, c=lambda x: general.open_url("https://discord.com/channels/1186722267212820610"), p=customGraph_help_submenu)
    cmds.menuItem(label="Knowledge base", image=media.help_menu_image, parent=customGraph_help_submenu, c=lambda x: general.open_url("https://thekeymachine.gitbook.io/base"))
    cmds.menuItem(label="Youtube channel", image=media.help_menu_image, parent=customGraph_help_submenu, c=lambda x: general.open_url("https://www.youtube.com/@TheKeyMachineMayaTools"))


    cmds.menuItem(divider=True, parent=popup_menu)  # Agregar un separador
    cmds.menuItem(label="About", parent=popup_menu, image=media.about_image, command=lambda x: ui.about_window())



    # ________________________________________________________  SelSets Menus __________________________________________________________ #

    button_ids = {}

    # ______identificadores
    set01_name = "button_1"
    set02_name = "button_2"
    set03_name = "button_3"
    set04_name = "button_4"
    set05_name = "button_5"


    # Conexión del evento al botón 1
    cmds.button(set01, edit=True, ebg=True)
    popup_menu = cmds.popupMenu(parent=set01)
    cmds.menuItem(label='Set', command=lambda x: selSets.set_button_value(set01_name), parent=popup_menu)
    cmds.menuItem(divider=True, parent=popup_menu)
    cmds.menuItem(label='Add', command=lambda x: selSets.add_button_selection(set01_name), parent=popup_menu)
    cmds.menuItem(label='Remove', command=lambda x: selSets.remove_button_selection(set01_name), parent=popup_menu)
    cmds.menuItem(divider=True, parent=popup_menu)
    cmds.menuItem(label='Lock', command=lambda x: selSets.lock_button_selection(set01_name), parent=popup_menu)
    cmds.menuItem(label='Unlock', command=lambda x: selSets.unlock_button_selection(set01_name), parent=popup_menu)
    cmds.button(set01, edit=True, c=lambda x: selSets.handle_button_selection(set01_name))


    # Conexión del evento al botón 2
    cmds.button(set02, edit=True, ebg=True)
    popup_menu = cmds.popupMenu(parent=set02)
    cmds.menuItem(label='Set', command=lambda x: selSets.set_button_value(set02_name), parent=popup_menu)
    cmds.menuItem(divider=True, parent=popup_menu)
    cmds.menuItem(label='Add', command=lambda x: selSets.add_button_selection(set02_name), parent=popup_menu)
    cmds.menuItem(label='Remove', command=lambda x: selSets.remove_button_selection(set02_name), parent=popup_menu)
    cmds.menuItem(divider=True, parent=popup_menu)
    cmds.menuItem(label='Lock', command=lambda x: selSets.lock_button_selection(set02_name), parent=popup_menu)
    cmds.menuItem(label='Unlock', command=lambda x: selSets.unlock_button_selection(set02_name), parent=popup_menu)
    cmds.button(set02, edit=True, c=lambda x: selSets.handle_button_selection(set02_name))


    # Conexión del evento al botón 3
    cmds.button(set03, edit=True, ebg=True)
    popup_menu = cmds.popupMenu(parent=set03)
    cmds.menuItem(label='Set', command=lambda x: selSets.set_button_value(set03_name), parent=popup_menu)
    cmds.menuItem(divider=True, parent=popup_menu)
    cmds.menuItem(label='Add', command=lambda x: selSets.add_button_selection(set03_name), parent=popup_menu)
    cmds.menuItem(label='Remove', command=lambda x: selSets.remove_button_selection(set03_name), parent=popup_menu)
    cmds.menuItem(divider=True, parent=popup_menu)
    cmds.menuItem(label='Lock', command=lambda x: selSets.lock_button_selection(set03_name), parent=popup_menu)
    cmds.menuItem(label='Unlock', command=lambda x: selSets.unlock_button_selection(set03_name), parent=popup_menu)
    cmds.button(set03, edit=True, c=lambda x: selSets.handle_button_selection(set03_name))


    # Conexión del evento al botón 4
    cmds.button(set04, edit=True, ebg=True)
    popup_menu = cmds.popupMenu(parent=set04)
    cmds.menuItem(label='Set', command=lambda x: selSets.set_button_value(set04_name), parent=popup_menu)
    cmds.menuItem(divider=True, parent=popup_menu)
    cmds.menuItem(label='Add', command=lambda x: selSets.add_button_selection(set04_name), parent=popup_menu)
    cmds.menuItem(label='Remove', command=lambda x: selSets.remove_button_selection(set04_name), parent=popup_menu)
    cmds.menuItem(divider=True, parent=popup_menu)
    cmds.menuItem(label='Lock', command=lambda x: selSets.lock_button_selection(set04_name), parent=popup_menu)
    cmds.menuItem(label='Unlock', command=lambda x: selSets.unlock_button_selection(set04_name), parent=popup_menu)
    cmds.button(set04, edit=True, c=lambda x: selSets.handle_button_selection(set04_name))


    # Conexión del evento al botón 5
    cmds.button(set05, edit=True, ebg=True)
    popup_menu = cmds.popupMenu(parent=set05)
    cmds.menuItem(label='Set', command=lambda x: selSets.set_button_value(set05_name), parent=popup_menu)
    cmds.menuItem(divider=True, parent=popup_menu)
    cmds.menuItem(label='Add', command=lambda x: selSets.add_button_selection(set05_name), parent=popup_menu)
    cmds.menuItem(label='Remove', command=lambda x: selSets.remove_button_selection(set05_name), parent=popup_menu)
    cmds.menuItem(divider=True, parent=popup_menu)
    cmds.menuItem(label='Lock', command=lambda x: selSets.lock_button_selection(set05_name), parent=popup_menu)
    cmds.menuItem(label='Unlock', command=lambda x: selSets.unlock_button_selection(set05_name), parent=popup_menu)
    cmds.button(set05, edit=True, c=lambda x: selSets.handle_button_selection(set05_name))
