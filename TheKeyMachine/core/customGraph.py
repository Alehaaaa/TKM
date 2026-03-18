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

import maya.cmds as cmds
import maya.OpenMayaUI as mui

import importlib
import random
from functools import partial

try:
    from PySide2 import QtCore, QtGui, QtWidgets
    from PySide2.QtWidgets import QActionGroup
except ImportError:
    from PySide6 import QtCore, QtGui, QtWidgets
    from PySide6.QtGui import QActionGroup


# -----------------------------------------------------------------------------------------------------------------------------
#                                             Loading necessary modules from TheKeyMachine                                    #
# -----------------------------------------------------------------------------------------------------------------------------

import TheKeyMachine.mods.generalMod as general
import TheKeyMachine.mods.uiMod as ui
import TheKeyMachine.mods.keyToolsMod as keyTools
import TheKeyMachine.mods.selSetsMod as selSets
import TheKeyMachine.mods.mediaMod as media
import TheKeyMachine.mods.styleMod as style

from TheKeyMachine.widgets import sliderWidget as sw  # type: ignore
from TheKeyMachine.widgets import customWidgets as cw  # type: ignore
from TheKeyMachine.widgets import util as wutil  # type: ignore
import TheKeyMachine.mods.settingsMod as settings  # type: ignore

mods = [general, ui, keyTools, selSets, media, style, sw, cw]

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


curveModeSlider = None
is_dragging = False
original_keyframes = {}
generated_keyframe_positions = {}
COLOR = ui.Color()
current_tangent_mode = settings.get_setting("current_tangent_mode", "Smooth")
current_modifier_mode = settings.get_setting("current_modifier_mode", "Wave")


# -----------------------------------------------------------------------------------------------------------------------------
#                                                       customGraph build                                                     #
# -----------------------------------------------------------------------------------------------------------------------------


def apply_base_stylesheet(button):
    """Fallback stylesheet for standard buttons if needed"""
    pass


def create_config_menu(parent_button):
    """Creates a config menu consistent with the main toolbar"""
    from TheKeyMachine.tooltips import QFlatTooltipManager
    import TheKeyMachine.mods.hotkeysMod as hotkeys

    menu = cw.MenuWidget(parent=parent_button)

    # Help submenu
    help_menu = cw.MenuWidget(QtGui.QIcon(media.help_menu_image), "Help", description="Resources for help and learning.")
    menu.addMenu(help_menu)
    help_menu.addAction(
        QtGui.QIcon(media.discord_image),
        "Discord Community",
        lambda: general.open_url("https://discord.gg/G2J5yyjz"),
        description="Join the community for support.",
    )
    help_menu.addAction(
        QtGui.QIcon(media.help_menu_image),
        "Knowledge base",
        lambda: general.open_url("https://thekeymachine.gitbook.io/base"),
        description="Read the official documentation.",
    )
    help_menu.addAction(
        QtGui.QIcon(media.youtube_image),
        "Youtube channel",
        lambda: general.open_url("https://www.youtube.com/@TheKeyMachineAnimationTools"),
        description="Watch tutorials.",
    )

    # Config submenu
    config_menu = cw.MenuWidget(QtGui.QIcon(media.settings_image), "Config", description="Tool configuration and preferences.")
    menu.addMenu(config_menu)

    config_menu.addSection("Tools settings")
    show_tt = settings.get_setting("show_tooltips", True)
    tt_action = config_menu.addAction("Show tooltips", description="Show or hide floating tooltips.")
    tt_action.setCheckable(True)
    tt_action.setChecked(show_tt)

    def toggle_tt(state):
        settings.set_setting("show_tooltips", state)
        QFlatTooltipManager.hide()

    tt_action.toggled.connect(toggle_tt)

    config_menu.addSection("Toolbar's icons alignment")
    align_group = QActionGroup(config_menu)
    left_align = config_menu.addAction("Left", description="Align icons to the left.")
    center_align = config_menu.addAction("Center", description="Align icons to the center.")
    right_align = config_menu.addAction("Right", description="Align icons to the right.")

    current_align = settings.get_setting("graph_toolbar_alignment", "Center")
    align_map = {"Left": left_align, "Center": center_align, "Right": right_align}

    for label, act in align_map.items():
        act.setCheckable(True)
        align_group.addAction(act)
        if label == current_align:
            act.setChecked(True)

        def set_align(state, alignment_label=label):
            if state:
                settings.set_setting("graph_toolbar_alignment", alignment_label)
                createCustomGraph()

        act.toggled.connect(set_align)

    config_menu.addSection("Hotkeys")
    config_menu.addAction("Add TKM Hotkeys", hotkeys.create_TheKeyMachine_hotkeys, description="Setup Maya hotkeys.")

    config_menu.addSection("General")
    config_menu.addAction(QtGui.QIcon(media.reload_image), "Reload", createCustomGraph, description="Refresh the TKM interface.")

    menu.addSeparator()
    menu.addAction(QtGui.QIcon(media.uninstall_image), "Uninstall", ui.uninstall, description="Remove TKM from Maya.")
    menu.addAction(QtGui.QIcon(media.about_image), "About", ui.about_window, description="Show version info and credits.")

    return menu


def create_tkm_button(icon=None, text="", tooltip="", description="", command=None, p=None):
    """Helper to create a QFlatToolButton with our tooltip system"""
    btn = cw.QFlatToolButton(icon=icon, text=text)
    if tooltip:
        btn.set_tooltip_data(text=tooltip, description=description)
    if command:
        btn.clicked.connect(command)
    if p:
        p.addWidget(btn)
    return btn


def createCustomGraph():
    def add_to_flow(widget):
        if widget and wutil.is_valid_widget(widget):
            flowtoolbar_layout.addWidget(widget)
        return widget

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

    flow_qw = cw.QFlowContainer()
    flow_qw.setObjectName("tkm_customGraph_flowToolbar")

    align_str = settings.get_setting("graph_toolbar_alignment", "Center")
    align_val = QtCore.Qt.AlignLeft
    if align_str == "Center":
        align_val = QtCore.Qt.AlignHCenter
    elif align_str == "Right":
        align_val = QtCore.Qt.AlignRight

    flowtoolbar_layout = cw.QFlowLayout(flow_qw, margin=2, Wspacing=5, Hspacing=2, alignment=align_val)

    parent_ptr = mui.MQtUtil.findControl("customGraph_columnLayout")
    parent_qw = wutil.get_maya_qt(parent_ptr, QtWidgets.QWidget)
    if parent_qw and parent_qw.layout():
        parent_qw.layout().addWidget(flow_qw)

    # ________________ Config Button ___________________#
    config_btn = create_tkm_button(
        icon=media.settings_image, tooltip="Config", description="Tool configuration and preferences.", p=flowtoolbar_layout
    )
    config_menu = create_config_menu(config_btn)
    config_btn.clicked.connect(lambda: config_menu.exec_(QtGui.QCursor.pos()))

    # ________________ Key Tools Buttons  ___________________#

    create_tkm_button(
        icon=media.delete_animation_image,
        text="S",
        tooltip="Static",
        description="Remove all statics curves",
        command=lambda: keyTools.deleteStaticCurves(),
        p=flowtoolbar_layout,
    )

    create_tkm_button(
        icon=media.share_keys_image,
        text="H",
        tooltip="Share",
        description="Share keys between curves to ensure both curves have the same keys in the same position.",
        command=lambda: keyTools.shareKeys(),
        p=flowtoolbar_layout,
    )

    create_tkm_button(
        icon=media.match_image,
        text="M",
        tooltip="Match",
        description="Makes a match of one curve with another, in this way both curves will be the same.",
        command=lambda: keyTools.match_keys(),
        p=flowtoolbar_layout,
    )

    create_tkm_button(
        text="F", tooltip="Flip", description="Inverts the selected curve vertically.", command=lambda: keyTools.flipCurves(), p=flowtoolbar_layout
    )

    create_tkm_button(
        text="Sn",
        tooltip="Snap",
        description="Performs a cleanup and repositioning of the keys that are in a sub-frame to the nearest frame.",
        command=lambda: keyTools.snapKeyframes(),
        p=flowtoolbar_layout,
    )

    create_tkm_button(
        text="O",
        tooltip="Overlap",
        description="Applies an overlap frame to the selected curves.",
        command=keyTools.mod_overlap_animation,
        p=flowtoolbar_layout,
    )

    create_tkm_button(
        icon=media.reblock_keys_image,
        text="rB",
        tooltip="reBlock",
        description="reBlock allows you to realign all the curves so that all their keyframes match up.",
        command=keyTools.reblock_move,
        p=flowtoolbar_layout,
    )

    extra_btn = create_tkm_button(
        text="E", tooltip="Extra", description="Additional curve utilities.", command=lambda: keyTools.snapKeyframes(), p=flowtoolbar_layout
    )
    extra_menu = cw.MenuWidget(parent=extra_btn)
    extra_menu.addAction("Select object from selected curve", lambda: keyTools.select_objects_from_selected_curves())
    extra_btn.setContextMenuPolicy(QtCore.Qt.CustomContextMenu)
    extra_btn.customContextMenuRequested.connect(lambda pos: extra_menu.exec_(extra_btn.mapToGlobal(pos)))
    extra_btn.clicked.connect(lambda: extra_menu.exec_(QtGui.QCursor.pos()))

    flowtoolbar_layout.addSpacing(10)

    # ___________________ Tween Machine  ____________________#

    cmds.separator(style="none", width=2)

    _ = sw.QFlatSliderWidget(
        "customGraph_tween_slider",
        min=-100,
        max=100,
        value=0,
        text="TW",
        color=COLOR.color.yellow,
        dragCommand=lambda x: keyTools.tween(x, slider_name="customGraph_tween_slider"),
        p=flowtoolbar_layout,
    )
    """
    tweenSliderLabel=cmds.text(label="T")
    separator = cmds.separator(style='none', width=4)
    
    tweenSlider = cmds.floatSlider("customGraph_tween_slider", width=140, min=-20, max=120, value=50, step=1, ann="TweenMachine", 
                       dragCommand=lambda x: keyTools.tween(x, slider_name="customGraph_tween_slider"), 
                       changeCommand=lambda x: keyTools.tweenSliderReset(tweenSlider))

    tweenSlider_widget = wutil.get_control_widget(tweenSlider, QtWidgets.QSlider)
    
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

    tweenSlider_widget.setStyleSheet(styleSheet)"""

    flowtoolbar_layout.addSpacing(10)

    # ____________________ Curve Modifiers (Green) _____________________#

    global current_modifier_mode
    current_modifier_mode = settings.get_setting("current_modifier_mode", "Wave")

    modifier_modes = {
        "Add": "AD",
        "Noise": "NS",
        "Scale": "SC",
        "Scale Sel": "SS",
        "Wave": "WV",
    }

    # ____________________ Tangent Operations (Orange) _____________________#

    global current_tangent_mode
    current_tangent_mode = settings.get_setting("current_tangent_mode", "Smooth")

    tangent_modes = {
        "Ease in/out": "ES",
        "Flat": "FT",
        "Lineal": "LN",
        "Smooth": "SM",
    }

    flowtoolbar_layout.addSpacing(10)

    # _____________ Add keyframes to curve

    def reset_generated_positions(curve):
        keyframes = cmds.keyframe(curve, query=True, selected=True, timeChange=True)
        if keyframes:
            # Generar posiciones entre los keyframes existentes
            generated_keyframe_positions[curve] = []
            for i in range(1, len(keyframes)):
                start = int(keyframes[i - 1])
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
                    print("No more available positions to add keyframes")
        else:
            print("Please select at least one animation curve in the Graph Editor")

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

                    mean_value = sum(reference_keyframes[i + 1] for i in range(0, len(reference_keyframes), 2)) / (len(reference_keyframes) / 2)

                    for i in range(0, len(keyframes), 2):
                        time = keyframes[i]
                        initial_value = original_keyframes[curve][i + 1]
                        new_value = mean_value + (initial_value - mean_value) * factor
                        cmds.keyframe(curve, edit=True, time=(time, time), valueChange=new_value)
        else:
            print("Please select at least one animation curve in the Graph Editor")

    # _____________ SCALE

    def apply_curves_scale_function(factor):
        global original_keyframes, is_dragging

        curves = cmds.selectionConnection("graphEditor1FromOutliner", query=True, object=True)
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
                    mean_value = sum(original_keyframes[curve][i + 1] for i in range(0, len(original_keyframes[curve]), 2)) / (
                        len(original_keyframes[curve]) / 2
                    )
                    for i in range(0, len(keyframes), 2):
                        time = keyframes[i]
                        initial_value = original_keyframes[curve][i + 1]
                        new_value = mean_value + (initial_value - mean_value) * factor
                        cmds.keyframe(curve, edit=True, time=(time, time), valueChange=new_value)

        else:
            print("Please select at least one animation curve in the Graph Editor")

    # ______________ SMOOTH

    def apply_curves_smooth_function(factor):
        global is_dragging, original_keyframes

        curves = cmds.selectionConnection("graphEditor1FromOutliner", query=True, object=True)
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
            print("Please select at least one animation curve in the Graph Editor")

    def curves_smooth(selection, power=0.1):
        keys = cmds.keyframe(selection, query=True, selected=True)
        if not keys:
            return

        for key in keys:
            time = cmds.keyframe(selection, query=True, time=(key, key))
            value = cmds.keyframe(selection, query=True, time=(key, key), valueChange=True)

            prev_time = cmds.findKeyframe(selection, time=(time[0],), which="previous")
            prev_value = cmds.keyframe(selection, query=True, time=(prev_time, prev_time), valueChange=True) if prev_time else value

            next_time = cmds.findKeyframe(selection, time=(time[0],), which="next")
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

    # Diccionario para almacenar el ruido inicial de cada clave
    initial_noise_values = {}

    def apply_curves_noise_function(value):
        global original_keyframes, is_dragging

        curves = cmds.selectionConnection("graphEditor1FromOutliner", query=True, object=True)
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
            print("Please select at least one animation curve in the Graph Editor")

    # ______________WAVE

    def apply_curves_wave_function(value):
        global original_keyframes, is_dragging

        curves = cmds.selectionConnection("graphEditor1FromOutliner", query=True, object=True)
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
            print("Please select at least one animation curve in the Graph Editor")

    # __________ LINEAR

    def curves_linear_interpolation(curve, blend_factor=1.0):
        global original_keyframes, is_dragging

        keyframes = cmds.keyframe(curve, query=True, selected=True, timeChange=True, valueChange=True)

        if not keyframes or len(keyframes) % 2 != 0:
            print(f"Please select at least one keyframe on curve {curve}")
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

        curves = cmds.selectionConnection("graphEditor1FromOutliner", query=True, object=True)
        if curves:
            for curve in curves:
                curves_linear_interpolation(curve, blend_factor)
        else:
            print("Please select at least one animation curve in the Graph Editor")

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

        curves = cmds.selectionConnection("graphEditor1FromOutliner", query=True, object=True)
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
            print("Please select at least one animation curve in the Graph Editor")

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

            eased_position = ease_func(time_position, power=factor * 3 + 1)

            new_value = lerp(original_keyframes[curve][i], lerp(original_keyframes[curve][0], original_keyframes[curve][-1], eased_position), factor)

            cmds.keyframe(curve, edit=True, time=(key, key), valueChange=new_value)

    # __________________ FLAT

    def curves_flat_interpolation(curve, blend_factor=1.0):
        global original_keyframes, is_dragging

        keyframes = cmds.keyframe(curve, query=True, selected=True, timeChange=True, valueChange=True)

        if not keyframes or len(keyframes) % 2 != 0:
            print(f"Please select at least one keyframe on curve {curve}")
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

        curves = cmds.selectionConnection("graphEditor1FromOutliner", query=True, object=True)
        if curves:
            for curve in curves:
                curves_flat_interpolation(curve, blend_factor)
        else:
            print("Please select at least one animation curve in the Graph Editor")

    # Now that all helper functions are defined, wire up the modifier and tangent sliders

    def modifier_mode_changed(mode, refresh_slider=True):
        global current_modifier_mode
        current_modifier_mode = mode
        settings.set_setting("current_modifier_mode", mode)
        modifier_slider.setText(modifier_modes.get(mode, "CM"))
        if refresh_slider:
            sliderReset()

    def modifier_slider_change(value):
        mode = current_modifier_mode
        if mode == "Wave":
            v = (value - 50) / 40.0
            apply_curves_wave_function(v)
        elif mode in ["Scale", "Scale Sel"]:
            v = 0.7 + (value / 100.0 * 0.6)
            if mode == "Scale":
                apply_curves_scale_function(v)
            else:
                scale_curves_from_point(v)
        elif mode in ["Noise", "Add"]:
            v = value / 200.0
            if mode == "Noise":
                apply_curves_noise_function(v)
            else:
                add_random_keyframes_to_curve(v)

    modifier_slider = sw.QFlatSliderWidget(
        "modifierSlider",
        min=0,
        max=100,
        value=50,
        text=modifier_modes.get(current_modifier_mode, "CM"),
        color=COLOR.color.green,
        dragCommand=modifier_slider_change,
        p=flowtoolbar_layout,
        tooltipTitle="Curve Modifiers",
        tooltipDescription="Modifier modes (Wave, Scale, Noise, etc.)",
    )

    mod_menu = cw.MenuWidget(parent=modifier_slider)
    mod_group = QActionGroup(mod_menu)
    for mode in sorted(modifier_modes.keys()):
        act = mod_menu.addAction(mode)
        act.setCheckable(True)
        mod_group.addAction(act)
        if mode == current_modifier_mode:
            act.setChecked(True)
        act.triggered.connect(partial(modifier_mode_changed, mode))
    modifier_slider.setContextMenuPolicy(QtCore.Qt.CustomContextMenu)
    modifier_slider.customContextMenuRequested.connect(lambda pos: mod_menu.exec_(modifier_slider.mapToGlobal(pos)))

    def tangent_mode_changed(mode, refresh_slider=True):
        global current_tangent_mode
        current_tangent_mode = mode
        settings.set_setting("current_tangent_mode", mode)
        tangent_slider.setText(tangent_modes.get(mode, "TG"))
        if refresh_slider:
            sliderReset()

    def tangent_slider_change(value):
        mode = current_tangent_mode
        v = value / 100.0
        if mode == "Smooth":
            v = value / 200.0
            apply_curves_smooth_function(v)
        elif mode == "Lineal":
            apply_curves_linear_function(v)
        elif mode == "Flat":
            apply_curves_flat_function(v)
        elif mode == "Ease in/out":
            apply_curves_ease_function(v)

    tangent_slider = sw.QFlatSliderWidget(
        "tangentSlider",
        min=0,
        max=100,
        value=50,
        text=tangent_modes.get(current_tangent_mode, "TG"),
        color=COLOR.color.orange,
        dragCommand=tangent_slider_change,
        p=flowtoolbar_layout,
        tooltipTitle="Tangent Operations",
        tooltipDescription="Tangent blending and smoothing.",
    )

    tg_menu = cw.MenuWidget(parent=tangent_slider)
    tg_group = QActionGroup(tg_menu)
    for mode in sorted(tangent_modes.keys()):
        act = tg_menu.addAction(mode)
        act.setCheckable(True)
        tg_group.addAction(act)
        if mode == current_tangent_mode:
            act.setChecked(True)
        act.triggered.connect(partial(tangent_mode_changed, mode))
    tangent_slider.setContextMenuPolicy(QtCore.Qt.CustomContextMenu)
    tangent_slider.customContextMenuRequested.connect(lambda pos: tg_menu.exec_(tangent_slider.mapToGlobal(pos)))

    def sliderReset(*args):
        global is_dragging, original_keyframes
        original_keyframes = {}
        generated_keyframe_positions.clear()
        if is_dragging:
            cmds.undoInfo(closeChunk=True)
            is_dragging = False

        # Reset both sliders
        modifier_slider.set_percent(50 if current_modifier_mode in ["Scale", "Scale Sel", "Wave"] else 0)
        tangent_slider.set_percent(50 if current_tangent_mode == "Ease in/out" else 0)

    # Initialize slider states
    modifier_mode_changed(current_modifier_mode, refresh_slider=False)
    tangent_mode_changed(current_tangent_mode, refresh_slider=False)
    sliderReset()

    flowtoolbar_layout.addSpacing(10)

    # _________________  Iso / Mute / Lock  _________________#
    create_tkm_button(
        icon=media.isolate_image,
        text="I",
        tooltip="Iso",
        description="Isolate selected curves.",
        command=lambda: keyTools.isolateCurve(),
        p=flowtoolbar_layout,
    )
    create_tkm_button(
        text="Mt", tooltip="Mute", description="Toggle mute on selected curves.", command=lambda: keyTools.toggleMute(), p=flowtoolbar_layout
    )
    create_tkm_button(
        text="Lk", tooltip="Lock", description="Toggle lock on selected curves.", command=lambda: keyTools.toggleLock(), p=flowtoolbar_layout
    )

    create_tkm_button(
        text="Fi",
        tooltip="Filter",
        p=flowtoolbar_layout,
        command=lambda: ui.customGraph_filter_mods(),
        description="Filter selection in the GraphEditor. Shift+Click to deactivate.",
    )

    # ____________________  Resets  _________________________#
    create_tkm_button(
        icon=media.reset_animation_image,
        text="R",
        tooltip="Reset",
        description="Reset the selected curves to their default values.",
        command=lambda: keyTools.get_default_value_main(),
        p=flowtoolbar_layout,
    )

    # ________________  SelSets Buttons  ____________________#
    flowtoolbar_layout.addSpacing(5)
    color_map = {
        "1": "#CBC8AD",
        "2": "#7BA399",
        "3": "#93C2AD",
        "4": "#C29591",
        "5": "#A86465",
    }
    for i in range(1, 6):
        s_id = str(i)
        s_name = "button_" + s_id
        btn = create_tkm_button(
            text=s_id, tooltip="SelSet 0{}".format(s_id), description="Left-click to select, Right-click for options.", p=flowtoolbar_layout
        )
        btn.setStyleSheet("QPushButton {{ background-color: {}; color: #333; }}".format(color_map.get(s_id, "#555")))

        # Action menu
        menu = cw.MenuWidget(parent=btn)
        menu.addAction("Set", partial(selSets.set_button_value, s_name))
        menu.addSeparator()
        menu.addAction("Add", partial(selSets.add_button_selection, s_name))
        menu.addAction("Remove", partial(selSets.remove_button_selection, s_name))
        menu.addSeparator()
        menu.addAction("Lock", partial(selSets.lock_button_selection, s_name))
        menu.addAction("Unlock", partial(selSets.unlock_button_selection, s_name))

        btn.clicked.connect(partial(selSets.handle_button_selection, s_name))
        btn.setContextMenuPolicy(QtCore.Qt.CustomContextMenu)
        btn.customContextMenuRequested.connect(lambda pos, m=menu, b=btn: m.exec_(b.mapToGlobal(pos)))

    # ________________ Cycle / Bouncy ___________________#
    flowtoolbar_layout.addSpacing(5)
    create_tkm_button(
        icon=media.match_curve_cycle_image,
        tooltip="Cycle Matcher",
        description="Curve cycle matcher.",
        command=keyTools.match_curve_cycle,
        p=flowtoolbar_layout,
    )
    create_tkm_button(
        icon=media.bouncy_curve_image, tooltip="Bouncy", description="Set bouncy tangents.", command=keyTools.bouncy_tangets, p=flowtoolbar_layout
    )

    # _________________  Opacity Slider  ____________________#

    def set_opacity_from_slider(value):
        # Normalize percent to 0..1
        v = value / 100.0
        graph_editor_window = get_graph_editor_window()
        if graph_editor_window is None:
            cmds.warning("GraphEditor opacity is not available when it's docked")
        else:
            graph_editor_window.setWindowOpacity(v)

    def get_graph_editor_window():
        if not cmds.window("graphEditor1Window", exists=True):
            cmds.GraphEditor()
        ptr = mui.MQtUtil.findWindow("graphEditor1Window")
        if ptr is not None:
            return wutil.get_maya_qt(ptr, QtWidgets.QWidget)
        else:
            return None

    flowtoolbar_layout.addSpacing(10)
    # Opacity slider (optional, can be enabled via config later)

    # Deferred height sync: ensures the container gets the right height on
    # the very first show (before any user-triggered resize fires).
    QtCore.QTimer.singleShot(0, flow_qw._update_height)
