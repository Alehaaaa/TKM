


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
from maya import OpenMaya as om
import maya.api.OpenMaya as om
import maya.OpenMayaUI as mui
import maya.mel as mel

try:
    from PySide2 import QtCore, QtWidgets, QtGui
    from PySide2.QtWidgets import QApplication, QDesktopWidget
    from shiboken2 import wrapInstance
except ImportError:
    from shiboken6 import wrapInstance
    from PySide6 import QtWidgets, QtCore, QtGui
    from PySide6.QtWidgets import *
    from PySide6.QtGui import *
    from PySide6.QtCore import *


import json
import os
import sys
import math
import platform
import importlib
import functools


# ----------------------------------------------------------------------


import TheKeyMachine.mods.keyToolsMod as keyTools
import TheKeyMachine.mods.generalMod as general


python_version = f"{sys.version_info.major}{sys.version_info.minor}"

# -------------------------------------------------------------------------




global down_one_level
down_one_level_var = False


original_bg_color = None
original_fg_color = None
original_key_color = None


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



def set_temp_timeslider_colors():
    global python_version, original_bg_color, original_fg_color, original_key_color

    # fix para maya 2024
    if python_version == '310':
    
        # Store the original colors
        original_bg_color = cmds.displayRGBColor('timeControlBackground', query=True)
        original_key_color = cmds.displayRGBColor('timeControlKey', query=True)

        # Set temporary colors
        cmds.displayRGBColor('timeControlBackground', 0.20530900359153748, 0.2126081883907318, 0.22100000083446503)
        cmds.displayRGBColor('timeControlKey', 0.31883829832077026, 0.3369826376438141, 0.3578431308269501)
        cmds.refresh(f=True)
    else:
        
        # Store the original colors
        original_bg_color = cmds.displayRGBColor('timeSliderBackground', query=True)
        original_fg_color = cmds.displayRGBColor('timeSliderForeground', query=True)
        original_key_color = cmds.displayRGBColor('timeSliderKey', query=True)

        # Set temporary colors
        cmds.displayRGBColor('timeSliderBackground', 0.20530900359153748, 0.2126081883907318, 0.22100000083446503)
        cmds.displayRGBColor('timeSliderForeground', 0.13725490868091583, 0.13725490868091583, 0.13725490868091583)
        cmds.displayRGBColor('timeSliderKey', 0.31883829832077026, 0.3369826376438141, 0.3578431308269501)
        cmds.refresh(f=True)


def restore_timeslider_colors():
    global python_version, original_bg_color, original_fg_color, original_key_color

    #fix para maya 2024
    if python_version == '310':
        
        if original_bg_color:
            # Restore original colors
            cmds.displayRGBColor('timeControlBackground', original_bg_color[0], original_bg_color[1], original_bg_color[2])
            cmds.displayRGBColor('timeControlKey', original_key_color[0], original_key_color[1], original_key_color[2])

    else:
        
        if original_bg_color and original_fg_color:
            # Restore original colors
            cmds.displayRGBColor('timeSliderBackground', original_bg_color[0], original_bg_color[1], original_bg_color[2])
            cmds.displayRGBColor('timeSliderForeground', original_fg_color[0], original_fg_color[1], original_fg_color[2])
            cmds.displayRGBColor('timeSliderKey', original_key_color[0], original_key_color[1], original_key_color[2])




def openCustomGraph():

    import TheKeyMachine.core.customGraph
    importlib.reload(TheKeyMachine.core.customGraph)
    TheKeyMachine.core.customGraph.openCustomGraph()





def mod_delete_animation(*args):
    # Get the current state of the modifiers
    mods = mel.eval('getModifiers')
    shift_pressed = bool(mods % 2)  # Check if Shift is pressed

    if shift_pressed:
        delete_time_slider_animation()
    else:
        delete_animation()



def delete_time_slider_animation():
    
    # Obtener selección actual
    selection = cmds.ls(selection=True)
    
    # Verificar si hay algo seleccionado
    if not selection:
        cmds.warning("Please select at least one object.")
        return

    mel.eval('timeSliderClearKey;')



def delete_animation():

    # Obtener canales seleccionados
    selected_channels = keyTools.get_selected_channels()
    
    # Obtener selección actual
    selection = cmds.ls(selection=True)
    
    # Verificar si hay algo seleccionado
    if not selection:
        cmds.warning("Please select at least one object.")
        return

    # Si hay canales seleccionados, solo borra esos canales
    if selected_channels:
        for obj in selection:
            for channel in selected_channels:
                cmds.cutKey(obj, attribute=channel, clear=True)
    # Si no hay canales seleccionados, borra todos los canales
    else:
        for obj in selection:
            cmds.cutKey(obj, clear=True)




def createLocator():
    selection = cmds.ls(selection=True)
    if selection:
        
        # Verificar si el grupo 'TheKeyMachine' existe, si no, crearlo
        if not cmds.objExists('TheKeyMachine'):
            general.create_TheKeyMachine_node()
        
        # Verificar si el grupo 'temp_locators' existe, si no, crearlo
        if not cmds.objExists('temp_locators'):
            cmds.group(em=True, name='temp_locators')
            # Hacer 'temp_locators' hijo de 'TheKeyMachine'
            cmds.parent('temp_locators', 'TheKeyMachine')
        
        for i, obj in enumerate(selection):
            locator = cmds.spaceLocator()[0]
            cmds.matchTransform(locator, obj)

            cmds.setAttr(locator + ".overrideEnabled", 1)
            cmds.setAttr(locator + ".overrideColor", 13)

            cmds.setAttr(locator + ".localScaleZ", 5)
            cmds.setAttr(locator + ".localScaleX", 5)
            cmds.setAttr(locator + ".localScaleY", 5)

            locator = cmds.rename(locator, f'tkm_temp_locator_{i}')  # Renombrar el locator con un índice único y almacenar el nuevo nombre
            
            # Añadir el locator al grupo 'temp_locators'
            cmds.parent(locator, 'temp_locators')
        cmds.select(selection)
    else:
        cmds.warning('Please select at least one object.')


def selectTempLocators(*args):
    # Buscar en la escena los objetos con el patrón 'tkm_temp_locator_*'
    potential_locators = cmds.ls('tkm_temp_locator_*')
    
    # Filtrar la lista para solo obtener objetos que terminen con un número
    locators = [loc for loc in potential_locators if loc.split('_')[-1].isdigit()]

    if locators:
        cmds.select(locators)
    else:
        cmds.warning('There are no temp locators in the scene.')


def deleteTempLocators(*args):
    if cmds.objExists('temp_locators'):
        # Lista todos los hijos del grupo 'temp_locators' y los borra
        potential_locators = cmds.ls('tkm_temp_locator_*')
        locators = [loc for loc in potential_locators if loc.split('_')[-1].isdigit()]
        if locators:
            cmds.delete(locators)
        else:
            cmds.warning('There are no temp locators in the scene.')
    else:
        cmds.warning('There are no temp locators group')



#___________________________ Set Tangets _______________________________________

def getSelectedCurves():
    curveNames = []

    # get the current selection list
    selectionList = om.MSelectionList()
    om.MGlobal.getActiveSelectionList(selectionList)

    # filter through the anim curves
    listIter = om.MItSelectionList(selectionList,  om.MFn.kAnimCurve)
    while not listIter.isDone():
        # Retrieve current item's MObject
        mobj = om.MObject()
        listIter.getDependNode(mobj)

        # Convert MObject to MFnDependencyNode
        depNodeFn = om.MFnDependencyNode(mobj)
        curveName = depNodeFn.name()

        curveNames.append(curveName)
        listIter.next()

    return curveNames

def get_graph_editor_selected_keyframes():
    anim_curves = cmds.keyframe(q=True, selected=True, name=True)
    if not anim_curves:
        return []

    keyframes = []
    for curve in anim_curves:
        keyframes += [(curve, frame) for frame in cmds.keyframe(curve, q=True, selected=True)]

    return keyframes



def setTangent(tangent_type):
    
    selectedKeyframes = get_graph_editor_selected_keyframes()

    if selectedKeyframes:
        for curve, frame in selectedKeyframes:
            cmds.keyTangent(curve, time=(frame,), itt=tangent_type, ott=tangent_type)
    else:
        # Si no hay curvas seleccionadas, ejecutar el comando MEL
        mel_command = 'timeSliderSetTangent {}'.format(tangent_type)
        mel.eval(mel_command)



def align_selected_objects(*args, pos=True, rot=True, scl=False):
    # Obtener los objetos seleccionados
    sel = cmds.ls(selection=True)

    # Asegurarse de que hay al menos dos objetos seleccionados
    if len(sel) < 2:
        cmds.warning("Please select at least two objects.")
        return

    # Obtener el objeto destino (último objeto en la lista de selección)
    target_obj = sel[-1]
    source_objs = sel[:-1]  # Todos los objetos excepto el último (objeto destino)

    # Obtener el tiempo actual
    current_time = cmds.currentTime(query=True)

    # Suspender la actualización de la vista
    cmds.refresh(suspend=True)

    try:
        # Obtener el rango de tiempo seleccionado
        time_range = keyTools.get_time_range_selected()

        # Crear una barra de progreso
        gMainProgressBar = mel.eval('$tmp = $gMainProgressBar')
        cmds.progressBar(gMainProgressBar, edit=True, beginProgress=True, isInterruptable=True, status='Alineando objetos...', maxValue=100)

        try:
            # Si hay un rango de tiempo seleccionado y no es igual al tiempo actual
            if time_range and time_range[0] != current_time:
                start_frame, end_frame = time_range[0], time_range[1]

                # Calcular el número total de frames en el rango
                total_frames = int(end_frame - start_frame + 1)

                # Iterar sobre cada frame en el rango y alinear los objetos
                for frame in range(int(start_frame), int(end_frame) + 1):
                    # Mover el tiempo actual al frame
                    cmds.currentTime(frame)

                    # Alinear los objetos fuente con el objeto destino en este frame
                    for source_obj in source_objs:
                        cmds.matchTransform(source_obj, target_obj, pos=pos, rot=rot, scl=scl)

                        # Definir un keyframe para el objeto fuente en este punto en el tiempo
                        cmds.setKeyframe(source_obj)

                    # Actualizar la barra de progreso
                    cmds.progressBar(gMainProgressBar, edit=True, progress=int((frame - start_frame) / total_frames * 100))

            else:
                # Si no hay un rango de tiempo seleccionado o es igual al tiempo actual, alinear en el tiempo actual
                for source_obj in source_objs:
                    cmds.matchTransform(source_obj, target_obj, pos=pos, rot=rot, scl=scl)
        finally:
            # Terminar la barra de progreso
            cmds.progressBar(gMainProgressBar, edit=True, endProgress=True)
    finally:
        # Reanudar la actualización de la vista
        cmds.refresh(suspend=False)




            

#___________________________ iso Rig _____________________________________

def toggle_down_one_level(value):
    global down_one_level_var
    down_one_level_var = value




def get_root_node(node, down_one_level=False):
    previous_node = None

    # Obtén el nombre completo del nodo para evitar conflictos de nombres duplicados
    node = cmds.ls(node, long=True)[0]  
    
    while True:
        parents = cmds.listRelatives(node, parent=True, fullPath=True)
        
        if not parents:
            # Si down_one_level está activado, queremos el nodo anterior al nodo raíz
            # Si estamos en el nodo raíz y down_one_level está activado, devolveremos el previous_node
            # Si down_one_level no está activado, simplemente devolveremos el nodo actual
            return previous_node if down_one_level else node  
        
        # Guardar el nodo actual antes de movernos al siguiente nodo padre
        previous_node = node
        
        # Actualizar el nodo actual al nodo padre para la próxima iteración
        node = parents[0]




def isolate_master():
    global down_one_level_var
    down_one_level = down_one_level_var

    down_one_level = cmds.menuItem('down_level_checkbox', query=True, checkBox=True)
    
    # Guardar la selección actual
    current_selection = cmds.ls(selection=True)
    
    # Obtener los objetos actualmente seleccionados
    selected_objects = cmds.ls(selection=True)
    currentPanel = cmds.getPanel(wf=True)
    currentState = cmds.isolateSelect(currentPanel, query=True, state=True)
    
    # Si no hay objetos seleccionados y el estado de aislamiento es 0, salimos de la función.
    if not selected_objects and currentState == 0:
        cmds.warning("No objects selected.")
        return
    # Si no hay objetos seleccionados pero el aislamiento está activado, lo desactivamos.
    elif not selected_objects and currentState == 1:
        cmds.isolateSelect(currentPanel, state=0)
        return
    else:
        # Para cada objeto seleccionado, encontrar y seleccionar el objeto raíz
        for selected_object in selected_objects:
            root_object = get_root_node(selected_object, down_one_level=down_one_level)
            cmds.select(root_object, add=True)  # Añadir el objeto raíz a la selección
        

        # Fix para activar/desactivar el icono isolate que en maya 2024 esta en otro layout

        maya_version = cmds.about(version=True)


        if currentState == 0:
            cmds.isolateSelect(currentPanel, state=1)
            cmds.isolateSelect(currentPanel, addSelected=True)


            # Fix para activar y desactivar el icono de maya del isolate
            if currentPanel == "modelPanel1":
                if maya_version == "2024" or maya_version == "2025":
                    cmds.iconTextCheckBox("MainPane|viewPanes|modelPanel1|modelPanel1|modelEditorIconBar|flowLayout3|formLayout24|IsolateSelectedBtn", edit=True, value=True)
                else:
                    cmds.iconTextCheckBox("MainPane|viewPanes|modelPanel1|modelPanel1|modelEditorIconBar|flowLayout3|formLayout25|IsolateSelectedBtn", edit=True, value=True)

            elif currentPanel == "modelPanel2":
                if maya_version == "2024" or maya_version == "2025":
                    cmds.iconTextCheckBox("MainPane|viewPanes|modelPanel2|modelPanel2|modelEditorIconBar|flowLayout4|formLayout31|IsolateSelectedBtn", edit=True, value=True)
                else:
                    cmds.iconTextCheckBox("MainPane|viewPanes|modelPanel2|modelPanel2|modelEditorIconBar|flowLayout4|formLayout32|IsolateSelectedBtn", edit=True, value=True)

            elif currentPanel == "modelPanel3":
                if maya_version == "2024" or maya_version == "2025":
                    cmds.iconTextCheckBox("MainPane|viewPanes|modelPanel3|modelPanel3|modelEditorIconBar|flowLayout5|formLayout38|IsolateSelectedBtn", edit=True, value=True)
                else:
                    cmds.iconTextCheckBox("MainPane|viewPanes|modelPanel3|modelPanel3|modelEditorIconBar|flowLayout5|formLayout39|IsolateSelectedBtn", edit=True, value=True)

            elif currentPanel == "modelPanel4":
                if maya_version == "2024" or maya_version == "2025":
                    cmds.iconTextCheckBox("MainPane|viewPanes|modelPanel4|modelPanel4|modelEditorIconBar|flowLayout6|formLayout45|IsolateSelectedBtn", edit=True, value=True)
                else:
                    cmds.iconTextCheckBox("MainPane|viewPanes|modelPanel4|modelPanel4|modelEditorIconBar|flowLayout6|formLayout46|IsolateSelectedBtn", edit=True, value=True)


        else:
            cmds.isolateSelect(currentPanel, state=0)
            cmds.isolateSelect(currentPanel, removeSelected=True)


             # Fix para activar y desactivar el icono de maya del isolate
            if currentPanel == "modelPanel1":
                if maya_version == "2024" or maya_version == "2025":
                    cmds.iconTextCheckBox("MainPane|viewPanes|modelPanel1|modelPanel1|modelEditorIconBar|flowLayout3|formLayout24|IsolateSelectedBtn", edit=True, value=False)
                else:
                    cmds.iconTextCheckBox("MainPane|viewPanes|modelPanel1|modelPanel1|modelEditorIconBar|flowLayout3|formLayout25|IsolateSelectedBtn", edit=True, value=False)

            elif currentPanel == "modelPanel2":
                if maya_version == "2024" or maya_version == "2025":
                    cmds.iconTextCheckBox("MainPane|viewPanes|modelPanel2|modelPanel2|modelEditorIconBar|flowLayout4|formLayout31|IsolateSelectedBtn", edit=True, value=False)
                else:
                    cmds.iconTextCheckBox("MainPane|viewPanes|modelPanel2|modelPanel2|modelEditorIconBar|flowLayout4|formLayout32|IsolateSelectedBtn", edit=True, value=False)

            elif currentPanel == "modelPanel3":
                if maya_version == "2024" or maya_version == "2025":
                    cmds.iconTextCheckBox("MainPane|viewPanes|modelPanel3|modelPanel3|modelEditorIconBar|flowLayout5|formLayout38|IsolateSelectedBtn", edit=True, value=False)
                else:
                    cmds.iconTextCheckBox("MainPane|viewPanes|modelPanel3|modelPanel3|modelEditorIconBar|flowLayout5|formLayout39|IsolateSelectedBtn", edit=True, value=False)

            elif currentPanel == "modelPanel4":
                if maya_version == "2024" or maya_version == "2025":
                    cmds.iconTextCheckBox("MainPane|viewPanes|modelPanel4|modelPanel4|modelEditorIconBar|flowLayout6|formLayout45|IsolateSelectedBtn", edit=True, value=False)
                else:
                    cmds.iconTextCheckBox("MainPane|viewPanes|modelPanel4|modelPanel4|modelEditorIconBar|flowLayout6|formLayout46|IsolateSelectedBtn", edit=True, value=False)

                
    # Restaurar la selección previa
    if current_selection:
        cmds.select(current_selection)
    else:
        cmds.select(clear=True)  # Borra la selección si no había nada seleccionado previamente









#____________________________ selector jerarquia

def select_curves_with_ctrl(obj):
    # Obtén los descendientes del objeto
    children = cmds.listRelatives(obj, allDescendents=True, type="nurbsCurve")
    if children:
        # Invertir el orden de los hijos
        children.reverse()

        for child in children:
            try:
                # Comprueba si el descendiente es de tipo nurbsCurve
                if cmds.nodeType(child) == "nurbsCurve":
                    # Obtiene el transformador de la forma nurbsCurve
                    transform = cmds.listRelatives(child, parent=True)[0]
                    cmds.select(transform, add=True)
            except Exception as e:
                # Manejar cualquier excepción y continuar con el siguiente descendiente
                print(f"Error selecting: {e}")
                continue

def selectHierarchy():
    # Obtener la selección actual
    selection = cmds.ls(selection=True)

    if selection:
        for obj in selection:
            select_curves_with_ctrl(obj)
    else:
        cmds.warning("Please select at least one object")











# ---------------------------------------------------  TEMP PIVOT ------------------------------------------------------#


def create_temp_pivot(use_saved_position=False, *args):


    attribute_callback_id = None
    time_callback_id = None
    process_callback = True

    seleccion = cmds.ls(selection=True)

    if not seleccion:
        cmds.warning("Please select at least one object")
        return

    if cmds.objExists("tkm_temp_pivot"):

        cmds.warning("Temp pivot already exists. Please unselect the current object to remove it.")
        return

    # Variables globales
    temp_pivot_relative_data = {}


    def get_temp_pivot_relation():
        cmds.undoInfo(openChunk=True)

        matrix_file_path = general.get_temp_pivot_data_file()
        
        seleccion = cmds.ls(selection=True)
        
        if not seleccion:
            cmds.warning("Please select at least one obj")
            return
        
        general.create_TheKeyMachine_node()

        # 1. Crear el nodo transform
        cmds.undoInfo(openChunk=True)
        temp_pivot_obj = cmds.createNode('transform', name="tkm_temp_pivot")
        cmds.parent("tkm_temp_pivot", "TheKeyMachine")
        
        if use_saved_position:
            if os.path.exists(matrix_file_path):
                with open(matrix_file_path, 'r') as f:
                    data = json.load(f)
                saved_position = data.get("tkm_temp_pivot_position", [0, 0, 0])
                saved_rotation = data.get("tkm_temp_pivot_rotation", [0, 0, 0])

                cmds.setAttr(f"{temp_pivot_obj}.translateX", saved_position[0])
                cmds.setAttr(f"{temp_pivot_obj}.translateY", saved_position[1])
                cmds.setAttr(f"{temp_pivot_obj}.translateZ", saved_position[2])
                
                cmds.setAttr(f"{temp_pivot_obj}.rotateX", saved_rotation[0])
                cmds.setAttr(f"{temp_pivot_obj}.rotateY", saved_rotation[1])
                cmds.setAttr(f"{temp_pivot_obj}.rotateZ", saved_rotation[2])
            else:
                cmds.warning("Saved temp pivot data not found!")
        else:
            # Calcula la posición basada en la selección
            total_x, total_y, total_z = 0, 0, 0
            for obj in seleccion:
                pos = cmds.xform(obj, query=True, translation=True, worldSpace=True)
                total_x += pos[0]
                total_y += pos[1]
                total_z += pos[2]
            
            num_objs = len(seleccion)
            mid_x = total_x / num_objs
            mid_y = total_y / num_objs
            mid_z = total_z / num_objs
            
            # Establecer la posición de tkm_temp_pivot en el punto medio
            cmds.setAttr(f"{temp_pivot_obj}.translateX", mid_x)
            cmds.setAttr(f"{temp_pivot_obj}.translateY", mid_y)
            cmds.setAttr(f"{temp_pivot_obj}.translateZ", mid_z)
        
        follow_objs = seleccion  # Todos los objetos seleccionados serán follow_objs
        save_dict = {"temp_pivot_obj": temp_pivot_obj, "follow_temp_pivot_objs": {}}
        
        for follow_obj in follow_objs:
            main_matrix = cmds.xform(temp_pivot_obj, query=True, matrix=True, worldSpace=True)
            follow_matrix = cmds.xform(follow_obj, query=True, matrix=True, worldSpace=True)
            
            main_mmatrix = om.MMatrix(main_matrix)
            follow_mmatrix = om.MMatrix(follow_matrix)
            
            relative_matrix = follow_mmatrix * main_mmatrix.inverse()
            
            # Guardar la matriz relativa en el diccionario
            save_dict["follow_temp_pivot_objs"][follow_obj] = [relative_matrix.getElement(i, j) for i in range(4) for j in range(4)]
        
        # Guardar el diccionario en un archivo JSON
        matrix_file_folder = general.get_temp_pivot_data_folder()
        os.makedirs(matrix_file_folder, exist_ok=True)
        with open(matrix_file_path, 'w') as f:
            json.dump(save_dict, f)

        cmds.select(temp_pivot_obj)
        get_c_Ctx = cmds.currentCtx()

        if get_c_Ctx == "selectSuperContext":
            cmds.setToolTo('moveSuperContext')
        cmds.select(temp_pivot_obj)
        cmds.ctxEditMode()




    def load_temp_pivot_data():
        global temp_pivot_relative_data

        # Rutas

        matrix_file_path = general.get_temp_pivot_data_file()
        
        # Verificar si el archivo existe
        if not os.path.exists(matrix_file_path):
            cmds.warning("Error, need temp pivot data first")
            return
        
        # Leer el diccionario del archivo JSON
        with open(matrix_file_path, 'r') as f:
            temp_pivot_relative_data = json.load(f)


    def set_temp_pivot_relation():
        global temp_pivot_relative_data

        temp_pivot_obj = temp_pivot_relative_data.get("temp_pivot_obj")
        follow_temp_pivot_objs = temp_pivot_relative_data.get("follow_temp_pivot_objs", {})
        
        seleccion = cmds.ls(selection=True)
        if not seleccion:
            cmds.warning("Please select one obj first")
            return
        
        if temp_pivot_obj in seleccion:
            follow_objs = list(follow_temp_pivot_objs.keys())
        else:
            follow_objs = seleccion

        for follow_obj in follow_objs:
            if follow_obj in follow_temp_pivot_objs:
                relative_matrix_list = follow_temp_pivot_objs[follow_obj]
                relative_matrix = om.MMatrix()
                for i in range(4):
                    for j in range(4):
                        relative_matrix.setElement(i, j, relative_matrix_list[i * 4 + j])
                
                main_matrix = cmds.xform(temp_pivot_obj, query=True, matrix=True, worldSpace=True)
                main_mmatrix = om.MMatrix(main_matrix)
                
                new_follow_matrix = relative_matrix * main_mmatrix
                new_follow_matrix_list = [new_follow_matrix.getElement(i, j) for i in range(4) for j in range(4)]
                
                cmds.xform(follow_obj, matrix=new_follow_matrix_list, worldSpace=True)

            else:
                cmds.warning(f"There is not temp pivot data for {follow_obj}.")


    get_temp_pivot_relation()


    def add_callbacks_link():
        global attribute_callback_id, time_callback_id, process_callback
        
        process_callback = True
        
        temp_pivot_obj_name = "tkm_temp_pivot"
        
        # Obtén el MObject del objeto principal
        selection_list = om.MSelectionList()
        selection_list.add(temp_pivot_obj_name)
        temp_pivot_obj_mobject = selection_list.getDependNode(0)
        
        # Registra el callback de atributo
        attribute_callback_id = om.MNodeMessage.addAttributeChangedCallback(temp_pivot_obj_mobject, attribute_callback_function)
        
        # Registra el callback de cambio de tiempo
        time_callback_id = om.MEventMessage.addEventCallback('timeChanged', time_callback_function)



    def remove_callbacks_link():
        global attribute_callback_id, time_callback_id
        try:
            if attribute_callback_id:
                om.MMessage.removeCallback(attribute_callback_id)
                attribute_callback_id = None
            if time_callback_id:
                om.MMessage.removeCallback(time_callback_id)
                time_callback_id = None
        except Exception as e:
            print(f"Error removing callback: {e}")


    def attribute_callback_function(msg, plug, otherPlug, clientData):
        global process_callback
        
        if not process_callback:
            return
        
        if msg & om.MNodeMessage.kAttributeSet:
            process_callback = False
            set_temp_pivot_relation()
            process_callback = True


    def time_callback_function(clientData):
        global process_callback
        if not process_callback:
            return
        process_callback = False
        set_temp_pivot_relation()  # Llamada a tu función set_matrix
        process_callback = True



    load_temp_pivot_data()
    add_callbacks_link()



    def update_temp_pivot_transform_in_file(position, rotation):

        matrix_file_path = general.get_temp_pivot_data_file()
        
        # Cargar datos actuales
        with open(matrix_file_path, 'r') as f:
            data = json.load(f)
        
        # Actualizar la posición de "tkm_temp_pivot"
        data["tkm_temp_pivot_position"] = position
        data["tkm_temp_pivot_rotation"] = rotation
        
        # Guardar datos actualizados
        with open(matrix_file_path, 'w') as f:
            json.dump(data, f)


    def temp_pivot_scriptJob_SelectionChanged():

        if not cmds.objExists("tkm_temp_pivot"):
            return
        else:

            # Crear un locator y hacer matchTransform a tkm_temp_pivot
            locator = cmds.spaceLocator()[0]
            cmds.matchTransform(locator, "tkm_temp_pivot")

            # Obtener la posición y rotación del locator
            position = cmds.xform(locator, query=True, translation=True, worldSpace=True)
            rotation = cmds.xform(locator, query=True, rotation=True, worldSpace=True)

            # Guardar la posición y rotación en el archivo
            update_temp_pivot_transform_in_file(position, rotation)

            # Remover los callbacks y eliminar los objetos
            remove_callbacks_link()
            cmds.delete("tkm_temp_pivot")
            cmds.delete(locator)

            cmds.undoInfo(closeChunk=True)
            cmds.undoInfo(closeChunk=True)


        
    cmds.scriptJob(runOnce = True, killWithScene = True,  event =('SelectionChanged',  temp_pivot_scriptJob_SelectionChanged))





# ---------------------------------------------------  COPY/PASTE WORLDSPACE ANIMATION  ------------------------------------------------------#



def mod_copy_worldspace_animation(*args):
    # Get the current state of the modifiers
    mods = mel.eval('getModifiers')
    shift_pressed = bool(mods % 2)  # Check if Shift is pressed

    if shift_pressed:
        color_paste_worldspace_animation()
    else:
        color_copy_worldspace_animation()



def color_copy_worldspace_animation(*args):
    set_temp_timeslider_colors()
    cmds.evalDeferred(copy_worldspace_animation)
    cmds.evalDeferred(restore_timeslider_colors)



def color_paste_worldspace_animation(*args):
    set_temp_timeslider_colors()
    cmds.evalDeferred(paste_worldspace_animation)
    cmds.evalDeferred(restore_timeslider_colors)


def copy_worldspace_animation(*args):

    selected_objects = cmds.ls(selection=True)
    if not selected_objects:
        cmds.warning("No objects selected.")
        return

    # Comprobar si los objetos seleccionados tienen claves de animación
    if not cmds.keyframe(selected_objects, query=True):
        cmds.warning("Selected objects do not have any animation.")
        return

    animation_data = {}

    # Guardar el tiempo actual antes de realizar cambios
    original_time = cmds.currentTime(query=True)

    # Suspender la actualización de la vista
    cmds.refresh(suspend=True)

    # Crear una barra de progreso
    gMainProgressBar = mel.eval('$tmp = $gMainProgressBar')
    total_frames = len(set(cmds.keyframe(selected_objects, query=True)))
    cmds.progressBar(gMainProgressBar, edit=True, beginProgress=True, isInterruptable=True, status='Copying worldspace animation...', maxValue=total_frames)

    try:
        all_keyframes = sorted(list(set(cmds.keyframe(selected_objects, query=True))))
        for frame in all_keyframes:
            # Verificar si el proceso fue interrumpido por el usuario
            if cmds.progressBar(gMainProgressBar, query=True, isCancelled=True):
                break

            cmds.currentTime(frame)

            for source_obj in selected_objects:
                # Asegurarse de que el objeto tiene claves en este frame
                if cmds.keyframe(source_obj, query=True, time=(frame, frame)):
                    worldspace_values = cmds.xform(source_obj, query=True, translation=True, worldSpace=True) + \
                                        cmds.xform(source_obj, query=True, rotation=True, worldSpace=True)
                    if source_obj not in animation_data:
                        animation_data[source_obj] = {}

                    animation_data[source_obj][int(frame)] = worldspace_values

            # Actualizar la barra de progreso
            cmds.progressBar(gMainProgressBar, edit=True, step=1)

        # Save to JSON


        worldspace_anim_data_file = general.get_copy_worldspace_data_file()
        worldspace_anim_data_folder = general.get_copy_worldspace_data_folder()

        if not os.path.exists(worldspace_anim_data_folder):
            os.makedirs(worldspace_anim_data_folder)

        with open(worldspace_anim_data_file, 'w') as json_file:
            json.dump(animation_data, json_file)

    finally:
        # Restaurar la actualización de la vista y cerrar la barra de progreso
        cmds.refresh(suspend=False)
        cmds.progressBar(gMainProgressBar, edit=True, endProgress=True)
        # Restaurar el tiempo actual a su estado original
        cmds.currentTime(original_time)
        cmds.warning("Worldspace animation copied")




# -------------------- Copy range worldspace

def copy_range_worldspace_animation(*args):

    selected_objects = cmds.ls(selection=True)
    if not selected_objects:
        cmds.warning("No objects selected.")
        return

    # Comprobar si los objetos seleccionados tienen claves de animación
    if not cmds.keyframe(selected_objects, query=True):
        cmds.warning("Selected objects do not have any animation.")
        return

    time_range = keyTools.get_selected_time_range()
    print(time_range)
    if time_range is None:
        cmds.warning("No time range selected on the timeslider.")
        return

    animation_data = {}

    # Guardar el tiempo actual antes de realizar cambios
    original_time = cmds.currentTime(query=True)

    # Suspender la actualización de la vista
    cmds.refresh(suspend=True)

    # Crear una barra de progreso
    gMainProgressBar = mel.eval('$tmp = $gMainProgressBar')
    all_keyframes = sorted(list(set(cmds.keyframe(selected_objects, query=True, time=(time_range[0], time_range[1])))))
    total_frames = len(all_keyframes)
    cmds.progressBar(gMainProgressBar, edit=True, beginProgress=True, isInterruptable=True, status='Copying worldspace animation...', maxValue=total_frames)

    try:
        for frame in all_keyframes:
            # Verificar si el proceso fue interrumpido por el usuario
            if cmds.progressBar(gMainProgressBar, query=True, isCancelled=True):
                break

            cmds.currentTime(frame)

            for source_obj in selected_objects:
                # Asegurarse de que el objeto tiene claves en este frame
                if cmds.keyframe(source_obj, query=True, time=(frame, frame)):
                    worldspace_values = cmds.xform(source_obj, query=True, translation=True, worldSpace=True) + \
                                        cmds.xform(source_obj, query=True, rotation=True, worldSpace=True)
                    if source_obj not in animation_data:
                        animation_data[source_obj] = {}

                    animation_data[source_obj][int(frame)] = worldspace_values

            # Actualizar la barra de progreso
            cmds.progressBar(gMainProgressBar, edit=True, step=1)

        # Save to JSON
        worldspace_anim_data_file = general.get_copy_worldspace_data_file()
        worldspace_anim_data_folder = general.get_copy_worldspace_data_folder()

        if not os.path.exists(worldspace_anim_data_folder):
            os.makedirs(worldspace_anim_data_folder)

        with open(worldspace_anim_data_file, 'w') as json_file:
            json.dump(animation_data, json_file)

    finally:
        # Restaurar la actualización de la vista y cerrar la barra de progreso
        cmds.refresh(suspend=False)
        cmds.progressBar(gMainProgressBar, edit=True, endProgress=True)
        # Restaurar el tiempo actual a su estado original
        keyTools.clear_timeslider_selection()
        cmds.currentTime(original_time)
        cmds.warning("Worldspace animation copied")



# ............. copy single frame worldspace

def copy_worldspace_single_frame(*args):
    selected_objects = cmds.ls(selection=True)
    if not selected_objects:
        cmds.warning("No objects selected.")
        return

    animation_data = {}

    # Obtener el tiempo actual
    current_time = cmds.currentTime(query=True)

    for source_obj in selected_objects:
        worldspace_values = cmds.xform(source_obj, query=True, translation=True, worldSpace=True) + \
                            cmds.xform(source_obj, query=True, rotation=True, worldSpace=True)
        animation_data[source_obj] = {int(current_time): worldspace_values}

    # Save to JSON
    worldspace_anim_data_file = general.get_copy_worldspace_single_frame_data_file()
    worldspace_anim_data_folder = general.get_copy_worldspace_single_frame_data_folder()

    if not os.path.exists(worldspace_anim_data_folder):
        os.makedirs(worldspace_anim_data_folder)

    with open(worldspace_anim_data_file, 'w') as json_file:
        json.dump(animation_data, json_file)

    cmds.warning("Worldspace values for current frame copied")



def paste_worldspace_single_frame(*args):
    
    # Rutas
    worldspace_anim_data_file = general.get_copy_worldspace_single_frame_data_file()

    if not os.path.exists(worldspace_anim_data_file):
        cmds.warning("No worldspace data found.")
        return

    with open(worldspace_anim_data_file, 'r') as json_file:
        animation_data = json.load(json_file)

    # Aplicar valores de worldspace guardados del primer frame disponible
    for obj, obj_data in animation_data.items():
        # Tomar el primer frame disponible
        first_frame = next(iter(obj_data))
        values = obj_data[first_frame]
        if cmds.objExists(obj):
            cmds.xform(obj, translation=values[:3], worldSpace=True)
            cmds.xform(obj, rotation=values[3:], worldSpace=True)
        else:
            cmds.warning(f"Object {obj} not found in the scene.")

    cmds.warning("Worldspace values applied")




def paste_worldspace_animation(*args):
    original_time = cmds.currentTime(query=True)

    # Rutas
    worldspace_anim_data_file = general.get_copy_worldspace_data_file()

    if not os.path.exists(worldspace_anim_data_file):
        print("No worldspace animation data found.")
        return

    with open(worldspace_anim_data_file, 'r') as json_file:
        animation_data = json.load(json_file)

    # Filtrar solo objetos existentes en la escena
    existing_objects = {obj: data for obj, data in animation_data.items() if cmds.objExists(obj)}

    if not existing_objects:
        cmds.warning("No valid objects found in the scene. Animation paste aborted.")
        return

    # Eliminar animación previa de los objetos existentes
    for obj in existing_objects.keys():
        cmds.cutKey(obj, attribute=['tx', 'ty', 'tz', 'rx', 'ry', 'rz'])

    # Obtener todos los frames únicos donde hay animación
    all_frames = sorted(set(frame for obj_data in existing_objects.values() for frame in obj_data.keys()), key=int)

    # Suspender la actualización de la vista
    cmds.refresh(suspend=True)

    # Crear barra de progreso
    gMainProgressBar = mel.eval('$tmp = $gMainProgressBar')
    cmds.progressBar(gMainProgressBar, edit=True, beginProgress=True, isInterruptable=True, status='Pasting worldspace animation...', maxValue=len(all_frames))

    try:
        for frame in all_frames:
            cmds.progressBar(gMainProgressBar, edit=True, step=1)
            if cmds.progressBar(gMainProgressBar, query=True, isCancelled=True):
                break

            cmds.currentTime(frame)
            for obj, obj_data in existing_objects.items():
                if frame in obj_data:
                    values = obj_data[frame]
                    cmds.xform(obj, translation=values[:3], worldSpace=True)
                    cmds.xform(obj, rotation=values[3:], worldSpace=True)
                    cmds.setKeyframe(obj)

    finally:
        cmds.filterCurve(list(existing_objects.keys()))  # Filtrar solo los objetos válidos
        cmds.refresh(suspend=False)
        cmds.progressBar(gMainProgressBar, edit=True, endProgress=True)
        cmds.currentTime(original_time)
        cmds.warning("Worldspace animation restored successfully")






# ____________________________________ Tracer _______________________________________________

def mod_tracer(*args):
    # Get the current state of the modifiers
    mods = mel.eval('getModifiers')

    shift_pressed = bool(mods & 1)  # Check if Shift is pressed
    ctrl_pressed = bool(mods & 4)  # Check if Ctrl is pressed
    alt_pressed = bool(mods & 8)  # Check if Alt is pressed

    if shift_pressed:
        tracer_refresh()
    elif ctrl_pressed and not alt_pressed:

        tracer_show_hide()
    elif ctrl_pressed and alt_pressed:

        remove_tracer_node()
    else:
        create_tracer()


def create_tracer(*args):


    selected_objects = cmds.ls(selection=True)
    
    # Verificar si hay exactamente un objeto seleccionado.
    if len(selected_objects) != 1:
        cmds.warning("Please select only one object.")
        return

    # Verifica o crea el grupo 'TheKeyMachine'
    if not cmds.objExists("TheKeyMachine"):
        general.create_TheKeyMachine_node() 
    
    # Verifica si 'CTracer' existe y si no, lo crea o lo reinicia
    if cmds.objExists("TKM_Tracer"):
        cmds.delete("TKM_Tracer")
    
    selected_objects_start = cmds.ls(selection=True)
    cmds.createNode("transform", name="TKM_Tracer")
    cmds.parent("TKM_Tracer", "TheKeyMachine")
    
    # Crea un nuevo nodo para 'tracer_offset' dentro de 'TKM_Tracer'
    cmds.createNode("transform", name="tracer_offset")
    cmds.parent("tracer_offset", "TKM_Tracer")
    
    cmds.select(selected_objects_start)
    
    selected_objects = cmds.ls(selection=True)
    
    if not selected_objects:
        cmds.warning("Please select an object to trace")
        return

    if cmds.objExists("tracerHandle"):
        cmds.delete("tracerHandle")

    startFrame = cmds.playbackOptions(query=True, minTime=True)
    endFrame = cmds.playbackOptions(query=True, maxTime=True)
    cmds.snapshot(n="tracer", mt=True, constructionHistory=True, startTime=startFrame, endTime=endFrame, increment=1)
    cmds.setAttr("tracerHandleShape.trailDrawMode", 1)
    cmds.setAttr("tracerHandleShape.extraTrailColor", 0.8143, 0.5109, 0.5318, type="double3")
    cmds.setAttr("tracerHandleShape.trailColor", 0.4398, 0.1724, 0.1908, type="double3")
    cmds.setAttr("tracerHandleShape.keyframeColor", 1.0, 1.0, 1.0, type="double3")
    cmds.disconnectAttr("tracer.points", "tracerHandleShape.points")
    cmds.parent("tracerHandle", "tracer_offset")  # Coloca "tracerHandle" dentro de "tracer_offset"
    tracer_update_checkbox(False)
    cmds.select(selected_objects)




def select_tracer_offset_node(*args):
    if cmds.objExists("tracer_offset"):
        cmds.select("tracer_offset", replace=True)
    else:
        cmds.warning("tracer_offset node does not exist.")


def remove_tracer_node(*args):
    if cmds.objExists("TKM_Tracer"):
        cmds.delete("TKM_Tracer")




def tracer_connected(connected=False, update_cb=None, *args):

    if not cmds.objExists("tracerHandle"):
        cmds.warning("No tracer node in the scene")
        return
    
    is_connected = cmds.isConnected("tracer.points", "tracerHandleShape.points")

    # Si queremos conectar pero ya está conectado, o si queremos desconectar pero ya está desconectado, regresamos.
    if (connected and is_connected) or (not connected and not is_connected):
        return

    if connected:
        cmds.connectAttr("tracer.points", "tracerHandleShape.points", force=True)
        cmds.setAttr("tracer.increment", 1)
    else:
        cmds.disconnectAttr("tracer.points", "tracerHandleShape.points")

    # Actualizamos el estado del checkbox si se proporciona la función de actualización.
    if update_cb:
        update_cb(connected)



def tracer_update_checkbox(value):
    cmds.menuItem('tracer_checkbox_menuItem', e=True, checkBox=value)



def tracer_refresh(*args):
    if not cmds.objExists("tracerHandle"):
        cmds.warning("No tracer node in the scene")
    else:
        is_connected = cmds.isConnected("tracer.points", "tracerHandleShape.points")
        if is_connected:
            cmds.warning("Tracer is already connected")
        else:
            cmds.connectAttr("tracer.points", "tracerHandleShape.points", force=True)
            cmds.setAttr("tracer.increment", 1);
            cmds.setAttr("tracer.increment", 2);
            cmds.setAttr("tracer.increment", 1);
            cmds.disconnectAttr("tracer.points", "tracerHandleShape.points")


def set_tracer_blue_color(*args):

    if cmds.objExists("tracerHandle"):
        cmds.setAttr("tracerHandleShape.extraTrailColor", 0.1615, 0.1766, 0.3581, type="double3")
        cmds.setAttr("tracerHandleShape.trailColor", 0.2879, 0.2932, 0.358, type="double3")
        cmds.setAttr("tracerHandleShape.keyframeColor", 1.0, 1.0, 1.0, type="double3")
    else:
        cmds.warning("No tracer node in the scene")

def set_tracer_red_color(*args):

    if cmds.objExists("tracerHandle"):
        cmds.setAttr("tracerHandleShape.extraTrailColor", 0.8143, 0.5109, 0.5318, type="double3")
        cmds.setAttr("tracerHandleShape.trailColor", 0.4398, 0.1724, 0.1908, type="double3")
        cmds.setAttr("tracerHandleShape.keyframeColor", 1.0, 1.0, 1.0, type="double3")
    else:
        cmds.warning("No tracer node in the scene")

def set_tracer_grey_color(*args):

    if cmds.objExists("tracerHandle"):
        cmds.setAttr("tracerHandleShape.extraTrailColor", 0.2879, 0.2932, 0.358, type="double3")
        cmds.setAttr("tracerHandleShape.trailColor", 0.122, 0.122, 0.122, type="double3")
        cmds.setAttr("tracerHandleShape.keyframeColor", 1.0, 1.0, 1.0, type="double3")
    else:
        cmds.warning("No tracer node in the scene")

def tracer_show_hide(*args):

    if not cmds.objExists("tracerHandle"):
        pass
    else:
        visibility = cmds.getAttr("tracerHandle.visibility")
        cmds.setAttr("tracerHandle.visibility", not visibility)




# FollowCam _________________________________________________________________

followCam_original_camera = None

def create_follow_cam(translation=True, rotation=True, *args):
    global followCam_original_camera

    # Obtén el objeto seleccionado en la escena
    selected_objects = cmds.ls(selection=True)

    # Verifica si existe el grupo "TheKeyMachine"
    if not cmds.objExists('TheKeyMachine'):
        general.create_TheKeyMachine_node()

    if not selected_objects:
        cmds.warning('No objects selected.')
        return

    target_object = selected_objects[0]

    mpanel = ["modelPanel1", "modelPanel2", "modelPanel3", "modelPanel4"]

    # Obtén el panel con el foco actualmente y encuentra la cámara activa
    panel = cmds.getPanel(withFocus=True)
    if panel not in mpanel:
        cmds.warning("There is no active viewport. Please select one.")
        return
    camera = cmds.modelEditor(panel, query=True, camera=True)
    followCam_original_camera = camera


    # Si ya existe el nodo "tkm_followCam", crea una cámara y grupo temporales
    if cmds.objExists('tkm_followCam'):
        follow_cam = cmds.duplicate(camera, name='followCam_tmp')[0]
        follow_cam_group = cmds.group(follow_cam, name='tkm_followCam_tmp')
    else:
        # Duplica la cámara activa y renómbrala
        follow_cam = cmds.duplicate(camera, name='followCam')[0]
        follow_cam_group = cmds.group(follow_cam, name='tkm_followCam')

    # Mueve el grupo "tkm_followCam" dentro del grupo "TheKeyMachine"
    cmds.parent(follow_cam_group, 'TheKeyMachine')

    # Desparenta temporalmente el nodo del dagContainer
    cmds.parent(follow_cam_group, world=True)

    if translation and not rotation:
        cmds.pointConstraint(target_object, follow_cam_group, maintainOffset=True)
    else:
        # Usa comandos de Python en lugar de MEL para establecer parentConstraint
        skip_trans = []
        skip_rot = []

        if not translation:
            skip_trans = ['x', 'y', 'z']
        if not rotation:
            skip_rot = ['x', 'y', 'z']

        cmds.parentConstraint(target_object, follow_cam_group, maintainOffset=True, skipTranslate=skip_trans, skipRotate=skip_rot)

    # Regresa el nodo al dagContainer
    cmds.parent(follow_cam_group, 'TheKeyMachine')
    
    # Si se creó un grupo y una cámara temporal, renombra estos para reemplazar los existentes
    if cmds.objExists('tkm_followCam_tmp'):
        cmds.delete('tkm_followCam')
        cmds.rename('tkm_followCam_tmp', 'tkm_followCam')
        cmds.rename('followCam_tmp', 'followCam')
        follow_cam = 'followCam'  # Asegura que follow_cam contenga el nombre correcto de la cámara

    # Si la cámara activa en el panel no es 'followCam', cambia la vista a 'followCam'
    if camera != 'followCam':
        cmds.lookThru(panel, follow_cam)
    
    cmds.select(selected_objects)


def remove_followCam(*args):
    global followCam_original_camera
    # Obtén el panel con el foco actualmente
    panel = cmds.getPanel(withFocus=True)
    
    # Comprueba si el panel es un visor (modelPanel)
    if cmds.getPanel(typeOf=panel) != "modelPanel":
        # Si no es un visor, selecciona el panel 'persp' por defecto
        panel = "modelPanel4"  # generalmente corresponde al visor perspectiva
    
    current_camera = cmds.modelEditor(panel, query=True, camera=True)

    if cmds.objExists('tkm_followCam'):
        cmds.delete('tkm_followCam')

        # Si el nombre de la cámara actual no es "persp", cambia la vista a "persp"
        print(followCam_original_camera)
        cmds.lookThru(panel, followCam_original_camera)
    else:
        print("No followCam in the scene")



# ________________________SELECTOR______________


def selektor_window(*args):
    window_name = "selectedObjectsWindow"
    if cmds.window(window_name, exists=True):
        cmds.deleteUI(window_name)

    window = cmds.window(window_name, title="Selector", widthHeight=(230, 365), sizeable=False)
    cmds.columnLayout(adjustableColumn=True)

    object_list = cmds.textScrollList(nr=30, allowMultiSelection=True, width=100, height=332)
    reload_button = cmds.button(label="Reload", width=100, height=30, command=functools.partial(reload_selected_objects, object_list))
    cmds.textScrollList(object_list, edit=True, sc=functools.partial(select_objects_from_list, object_list))
    reload_selected_objects(object_list)
    cmds.showWindow(window)

def select_objects_from_list(list_name, *args):
    # Obtener los elementos seleccionados en la lista
    selected_objects = cmds.textScrollList(list_name, query=True, selectItem=True)

    # Seleccionar los objetos en la escena
    cmds.select(selected_objects, replace=True)

def reload_selected_objects(list_name, *args):
    selected_objects = cmds.ls(selection=True)
    sorted_objects = sorted(selected_objects)

    # Borrar los elementos actuales en la lista
    cmds.textScrollList(list_name, edit=True, removeAll=True)

    # Agregar los objetos seleccionados ordenados alfabéticamente a la lista
    cmds.textScrollList(list_name, edit=True, append=sorted_objects)




# _____________________ SELECT RIG CHARACTER CONTROLS

def select_rig_controls(*args):
    def find_curves(node):
        curves = []
        shapes = cmds.listRelatives(node, shapes=True, fullPath=True)
        if shapes:
            for shape in shapes:
                if cmds.nodeType(shape) == 'nurbsCurve':
                    curves.append(node)
        children = cmds.listRelatives(node, children=True, fullPath=True)
        if children:
            for child in children:
                curves += find_curves(child)
        return curves

    selected = cmds.ls(selection=True, long=True)

    if not selected:
        cmds.warning("Please select at least one control.")
        return

    # Obtener los namespaces de los objetos seleccionados
    namespaces = set()
    no_namespace = False
    for obj in selected:
        namespace_parts = obj.split(':')
        if len(namespace_parts) > 1:
            namespace = namespace_parts[0]
            namespaces.add(namespace)
        else:
            no_namespace = True

    all_curves = []

    for obj in selected:
        while True:
            parent = cmds.listRelatives(obj, parent=True, fullPath=True)
            if parent:
                obj = parent[0]
            else:
                break

        curves = find_curves(obj)
        all_curves += curves

    cmds.select(clear=True)

    if all_curves:
        if namespaces:  # Si hay namespaces, filtra las curvas que comiencen con algún namespace
            filtered_curves = [curve for curve in all_curves if any(curve.startswith(ns + ':') for ns in namespaces)]
        else:
            filtered_curves = all_curves

        if no_namespace:  # Si hay objetos sin namespace, incluye curvas sin namespace
            filtered_curves += [curve for curve in all_curves if ':' not in curve]

        cmds.select(filtered_curves, replace=True)
    else:
        cmds.warning("There are no curve-type controls to select.")



# ______________ SELECT ANIMATED RIG CONTROLS 

def select_animated_rig_controls(*args):
    cache = {}

    def find_controls(node):
        if node in cache:
            return cache[node]

        controls = []
        transforms = cmds.listRelatives(node, parent=True, fullPath=True) or [node]
        for transform in transforms:
            # Comprobar si el transform es un joint
            if cmds.nodeType(transform) == 'joint':
                if is_animated_and_keyable(transform):
                    controls.append(transform)
            elif cmds.nodeType(transform) == 'transform':
                shapes = cmds.listRelatives(transform, shapes=True, fullPath=True)
                if shapes:
                    for shape in shapes:
                        if cmds.nodeType(shape) == 'nurbsCurve':
                            if is_animated_and_keyable(transform):
                                controls.append(transform)

        children = cmds.listRelatives(node, children=True, fullPath=True)
        if children:
            for child in children:
                controls += find_controls(child)

        cache[node] = controls
        return controls

    def is_animated_and_keyable(node):
        if node in cache:
            return cache[node]

        attrs = cmds.listAttr(node, keyable=True)
        if not attrs:
            cache[node] = False
            return False

        for attr in attrs:
            if not cmds.getAttr(node + '.' + attr, lock=True):
                connections = cmds.listConnections(node + '.' + attr, type='animCurve')
                if connections:
                    for conn in connections:
                        if cmds.nodeType(conn) in ['animCurveTA', 'animCurveTL', 'animCurveTU']:
                            cache[node] = True
                            return True

        cache[node] = False
        return False

    selected = cmds.ls(selection=True, long=True)

    if not selected:
        cmds.warning("Please select at least one control.")
        return

    namespaces = set()
    for obj in selected:
        namespace_parts = obj.split(':')
        if len(namespace_parts) > 1:
            namespace = namespace_parts[0]
            namespaces.add(namespace)

    all_controls = []

    for obj in selected:
        while True:
            parent = cmds.listRelatives(obj, parent=True, fullPath=True)
            if parent:
                obj = parent[0]
            else:
                break

        controls = find_controls(obj)
        all_controls += controls

    cmds.select(clear=True)

    if all_controls:
        if namespaces:  # Si hay namespaces, filtra los controles que comienzan con alguno de los namespaces
            filtered_controls = [control for control in all_controls if any(control.startswith(ns + ':') for ns in namespaces)]
        else:  # Si no hay namespaces, selecciona todos los controles tal como están
            filtered_controls = all_controls

        cmds.select(filtered_controls, replace=True)
    else:
        cmds.warning("There are no suitable controls to select.")




# _______________________________________ DEPTH MOVER

def activeCamera():
    panel = cmds.getPanel(withFocus=True)
    if cmds.getPanel(typeOf=panel) != 'modelPanel':
        for p in cmds.getPanel(visiblePanels=True):
            if cmds.getPanel(typeOf=p) == 'modelPanel':
                panel = p
                break
    if cmds.getPanel(typeOf=panel) != 'modelPanel':
        OpenMaya.MGlobal.displayWarning('There is no camera selected.')
        return None

    camShape = cmds.modelEditor(panel, query=True, camera=True)
    if not camShape:
        return None

    if cmds.nodeType(camShape) == 'transform':
        return camShape
    elif cmds.nodeType(camShape) in ['camera', 'stereoRigCamera']:
        return cmds.listRelatives(camShape, parent=True, path=True)[0]
    return None

class Coord3D:
    def __init__(self, x=0, y=0, z=0):
        self.x, self.y, self.z = x, y, z

    def __iter__(self):
        return iter((self.x, self.y, self.z))

    def __add__(self, other):
        return Coord3D(self.x + other.x, self.y + other.y, self.z + other.z)

    def __sub__(self, other):
        return Coord3D(self.x - other.x, self.y - other.y, self.z - other.z)

    def __mul__(self, other):
        if isinstance(other, Coord3D):
            return Coord3D(self.x * other.x, self.y * other.y, self.z * other.z)
        elif isinstance(other, (float, int)):
            return Coord3D(self.x * other, self.y * other, self.z * other)
        raise TypeError("Unsupported operand type(s) for *: 'Coord3D' and '{}'".format(type(other).__name__))

    def magnitude(self):
        return math.sqrt(self.x**2 + self.y**2 + self.z**2)

    def normalize(self):
        mag = self.magnitude()
        return Coord3D(self.x / mag, self.y / mag, self.z / mag) if mag else self

class MouseDragger(object):
    def __init__(self, name='mlMouseDraggerContext', title='MouseDragger', multiplier=0.1, cursor='hand'):
        self.multiplier = multiplier
        self.draggerContext = name
        if not cmds.draggerContext(self.draggerContext, exists=True):
            self.draggerContext = cmds.draggerContext(self.draggerContext)

        cmds.draggerContext(self.draggerContext, edit=True, pressCommand=self.onPress, dragCommand=self.onDrag, releaseCommand=self.onRelease, cursor=cursor, drawString=title, undoMode='all')

    def onPress(self):
        self.anchorPoint = cmds.draggerContext(self.draggerContext, query=True, anchorPoint=True)
        cmds.undoInfo(openChunk=True)

    def onDrag(self):
        dragPoint = cmds.draggerContext(self.draggerContext, query=True, dragPoint=True)
        self.x = (dragPoint[0] - self.anchorPoint[0]) * self.multiplier
        self.y = (dragPoint[1] - self.anchorPoint[1]) * self.multiplier
        self.performDrag()
        cmds.refresh() 

    def onRelease(self):
        cmds.undoInfo(closeChunk=True)
        cmds.setToolTo('selectSuperContext')

    def performDrag(self):
        pass

    def activateTool(self):
        cmds.setToolTo(self.draggerContext)


class DepthControlDragger(MouseDragger):
    def __init__(self):
        super(DepthControlDragger, self).__init__(name='mlDepthControlDraggerContext', title='DepthControl', multiplier=0.1)

        cam = activeCamera()
        if not cam:
            om.MGlobal.displayWarning('No camera found.')
            return

        sel = cmds.ls(sl=True)
        if not sel:
            om.MGlobal.displayWarning('Please select an object.')
            return

        self.cameraCoord = Coord3D(*cmds.xform(cam, query=True, worldSpace=True, rotatePivot=True))
        self.objs = [(obj, Coord3D(*cmds.xform(obj, query=True, worldSpace=True, rotatePivot=True)) - self.cameraCoord) for obj in sel if cmds.getAttr(obj+'.translate', settable=True)]

        if not self.objs:
            om.MGlobal.displayWarning('Selected objects do not have translate attributes to apply this tool.')
            return

        self.activateTool()

    def performDrag(self):
        for obj, coord in self.objs:
            newPos = (coord.normalize() * self.x) + coord + self.cameraCoord
            cmds.move(newPos.x, newPos.y, newPos.z, obj, absolute=True, worldSpace=True)

def depth_mover(*args):
    DepthControlDragger()






# ___________________________________________  GIMBAL FIXER  _______________________________________



ROTATE_ORDERS = ['xyz', 'yzx', 'zxy', 'xzy', 'yxz', 'zyx']

class UndoSetup():
    def __enter__(self):
        cmds.undoInfo(openChunk=True)

    def __exit__(self, *args):
        cmds.undoInfo(closeChunk=True)

class StopRefresh():
    def __enter__(self):
        self.resetAutoKey = cmds.autoKeyframe(query=True, state=True)
        cmds.autoKeyframe(state=False)
        cmds.refresh(suspend=True)

    def __exit__(self, *args):
        cmds.autoKeyframe(state=self.resetAutoKey)
        cmds.refresh(suspend=False)

def gimbal_fixer_window(*args):
    if cmds.window("gimbal_fixer", exists=True):
        cmds.deleteUI("gimbal_fixer")

    main_window = gimbal_fixer_build()

    if cmds.ls(sl=True):  # Verifica si hay una selección
        update_rotation_order(main_window)  # Ejecuta el botón "Reload"
    else:
        cmds.warning("Please select a control and reload")

def update_rotation_order(window):
    sel = cmds.ls(sl=True)
    if not sel:
        cmds.warning("Please select a control.")
        return

    current_rotate_order = cmds.getAttr(f'{sel[0]}.rotateOrder')
    current_rotate_order_text = ROTATE_ORDERS[current_rotate_order]

    tolerances = rotate_gimbal_state(sel[0])
    rotate_orders = ['xyz', 'yzx', 'zxy', 'xzy', 'yxz', 'zyx']
    tolerances_with_orders = list(zip(tolerances, rotate_orders))
    sorted_tolerances = sorted(tolerances_with_orders)

    button_names = ["Best", "Good", "Moderate", "Average", "Poor", "Inadequate"]
    
    for button_name, (_, order) in zip(button_names, sorted_tolerances):
        button = window.findChild(QtWidgets.QPushButton, f"{button_name.lower()}_button")
        if button:
            button.setText(order)

    quality_names = ["Best", "Good", "Moderate", "Average", "Poor", "Inadequate"]

    for quality_name, (tolerance, order) in zip(["Best", "Good", "Moderate", "Average", "Poor", "Inadequate"], sorted_tolerances):
        line_edit = window.findChild(QtWidgets.QLineEdit, f"{quality_name.lower()}_edit")
        if line_edit:
            percentage = round(tolerance * 100)
            line_edit.setText(f"{percentage}%")
            # Cambiar el estilo si coincide con el orden actual
            if order == current_rotate_order_text:
                line_edit.setStyleSheet("QLineEdit { color: #d9d9d9; }")
            else:
                line_edit.setStyleSheet("QLineEdit { color: #a5a5a5; }")

    control_name_edit = window.findChild(QtWidgets.QLineEdit, "control_name_edit")
    if control_name_edit:
        object_name = sel[0].split(':')[-1]
        control_name_edit.setText(object_name)

    rotation_order_edit = window.findChild(QtWidgets.QLineEdit, "rotation_order_edit")
    if rotation_order_edit:
        rotate_order = cmds.getAttr(f'{sel[0]}.rotateOrder')
        rotation_order_edit.setText(ROTATE_ORDERS[rotate_order])

    tolerances = rotate_gimbal_state(sel[0])
    gimbal_state_edit = window.findChild(QtWidgets.QLineEdit, "gimbal_state_edit")
    if gimbal_state_edit:
        gimbal_quality = get_gimbal_quality(tolerances)
        gimbal_state_edit.setText(gimbal_quality)

    cmds.select(sel)

def rotate_gimbal_state(obj):
    rot_data = cmds.duplicate(obj, name='temp#', parentOnly=True)[0]

    tolerences = list()
    for rot_order in ROTATE_ORDERS:
        cmds.xform(rot_data, preserve=True, rotateOrder=rot_order)
        tolerences.append(gimbal_tolerence(rot_data))

    cmds.delete(rot_data)
    return tolerences

def get_gimbal_quality(tolerances):
    index = tolerances.index(min(tolerances))
    quality_names = ["Best", "Good", "Moderate", "Average", "Poor", "Inadequate"]
    return quality_names[index]

def gimbal_tolerence(obj):
    rotateOrder = ROTATE_ORDERS[cmds.getAttr(obj+'.rotateOrder')]
    midValue = cmds.getAttr(obj+'.r'+rotateOrder[1])
    gimbalTest = abs(((midValue+90) % 180) - 90) / 90
    return gimbalTest

def get_order_from_button(button):
    return button.text()

def xyz(*args):
    convert_rotation_order(rot_order='xyz')

def yzx(*args):
    convert_rotation_order(rot_order='yzx')

def zxy(*args):
    convert_rotation_order(rot_order='zxy')

def xzy(*args):
    convert_rotation_order(rot_order='xzy')

def yxz(*args):
    convert_rotation_order(rot_order='yxz')

def zyx(*args):
    convert_rotation_order(rot_order='zyx')

def convert_rotation_order(rot_order='zxy'):
    if not rot_order in ROTATE_ORDERS:
        om.MGlobal.displayWarning('Wrong rotation order '+str(rot_order))
        return

    sel = cmds.ls(sl=True)

    if not sel:
        om.MGlobal.displayWarning('Please select a control.')
        return

    time = cmds.currentTime(query=True)

    key_times = dict()
    prevrot_order = dict()
    key_data = list()
    keyed_data_objs = list()
    unkeyed_data_objs = list()

    for obj in sel:
        rotKeys = cmds.keyframe(obj, attribute='rotate', query=True, timeChange=True)
        if rotKeys:
            key_times[obj] = list(set(rotKeys))
            prevrot_order[obj] = ROTATE_ORDERS[cmds.getAttr(obj+'.rotateOrder')]
            key_data.extend(rotKeys)
            keyed_data_objs.append(obj)
        else:
            unkeyed_data_objs.append(obj)

    with UndoSetup():
        if keyed_data_objs:

            key_data = list(set(key_data))
            key_data.sort()

            with StopRefresh():
                for frame in key_data:
                    cmds.currentTime(frame, edit=True)
                    for obj in keyed_data_objs:
                        if frame in key_times[obj]:
                            cmds.setKeyframe(obj, attribute='rotate')

                for frame in key_data:
                    cmds.currentTime(frame, edit=True)
                    for obj in keyed_data_objs:
                        if frame in key_times[obj]:

                            cmds.xform(obj, preserve=True, rotateOrder=rot_order)
                            cmds.setKeyframe(obj, attribute='rotate')
                            cmds.xform(obj, preserve=False, rotateOrder=prevrot_order[obj])

                cmds.currentTime(time, edit=True)

                for each in keyed_data_objs:
                    cmds.xform(each, preserve=False, rotateOrder=rot_order)
                    cmds.filterCurve(each)

        if unkeyed_data_objs:
            for obj in unkeyed_data_objs:
                cmds.xform(obj, preserve=True, rotateOrder=rot_order)

def gimbal_fixer_build():

    screen_width, screen_height = get_screen_resolution()
    screen_width = screen_width
    
    # 4K fix
    if screen_width == 3840:
        win_w = 495
        win_h = 300
        close_button_size = 33
        control_name_w = 225
        control_name_h = 30
        rotation_order_w = 225
        rotation_order_h = 30
        button_w = 225
        button_h = 37
        percentage_line_w = 75
        percentage_line_h = 30
        reload_button_w = 375
        reload_button_h = 45
        layout_spacing = 37
        layout_margin = 15
        font_size = 16
    else:
        win_w = 330
        win_h = 200
        close_button_size = 22
        control_name_w = 150
        control_name_h = 20
        rotation_order_w = 150
        rotation_order_h = 20
        button_w = 150
        button_h = 25
        percentage_line_w = 50
        percentage_line_h = 20
        reload_button_w = 250
        reload_button_h = 30
        layout_spacing = 25
        layout_margin = 10
        font_size = 11





    drag = {"active": False, "position": QtCore.QPoint()}

    def mousePressEvent(event):
        if event.button() == QtCore.Qt.LeftButton:
            drag["active"] = True
            drag["position"] = event.globalPos() - window.frameGeometry().topLeft()
            event.accept()

    def mouseMoveEvent(event):
        if event.buttons() == QtCore.Qt.LeftButton and drag["active"]:
            window.move(event.globalPos() - drag["position"])
            event.accept()

    def mouseReleaseEvent(event):
        drag["active"] = False

    parent = wrapInstance(int(mui.MQtUtil.mainWindow()), QtWidgets.QWidget)
    window = QtWidgets.QWidget(parent, QtCore.Qt.Window | QtCore.Qt.FramelessWindowHint)

    window.resize(win_h, win_w)

    window.setWindowOpacity(1.0)
    window.setObjectName('gimbal_fixer')
    window.setWindowTitle('Gimbal Fixer')
    window.setAttribute(QtCore.Qt.WA_TranslucentBackground)

    window.mousePressEvent = mousePressEvent
    window.mouseMoveEvent = mouseMoveEvent
    window.mouseReleaseEvent = mouseReleaseEvent

    central_widget = QtWidgets.QWidget(window)
    central_widget.setStyleSheet(f"""
    QWidget {{
        border-radius: 10px;
        border: 1px solid #393939;
        font-size: {font_size}px;
    }}
    QLabel, QPushButton, QLineEdit {{
        border: none;
        color: #ccc;
    }}
    QPushButton {{
        background-color: #6E6E6E;
        border-radius: 5px;
    }}
    QPushButton:hover {{
        background-color: #7E7E7E;
    }}
    QLineEdit {{
        background-color: #323232;
        color: #ccc;
        border-radius: 5px;
    }}
    """)
    layout = QtWidgets.QVBoxLayout(central_widget)
    layout.setSpacing(5)
    layout.setContentsMargins(layout_margin, layout_margin, layout_margin, layout_margin)

    header_layout = QtWidgets.QHBoxLayout()
    header_layout.addStretch()
    close_button = QtWidgets.QPushButton('X')
    close_button.setFixedSize(close_button_size, close_button_size)
    close_button.clicked.connect(window.close)
    close_button.setStyleSheet(
        "QPushButton {"
        "    background-color: #505050;"
        "    border: none;"
        "    color: #ccc;"
        "    border-radius: 5px;"
        "}"
        "QPushButton:hover {"
        "    background-color: #ec7f70;"
        "    border-radius: 5px;"
        "    color: #fff;"
        "}"
    )
    header_layout.addWidget(close_button)
    layout.addLayout(header_layout)

    control_name_layout = QtWidgets.QHBoxLayout()
    control_name_label = QtWidgets.QLabel('Control name:')
    control_name_edit = QtWidgets.QLineEdit()
    control_name_edit.setObjectName("control_name_edit")
    control_name_edit.setStyleSheet("QLineEdit { color: #a5a5a5; }")
    control_name_edit.setFixedSize(control_name_w, control_name_h)
    control_name_edit.setReadOnly(True)
    control_name_layout.addWidget(control_name_label)
    control_name_layout.addWidget(control_name_edit)
    layout.addLayout(control_name_layout)

    rotation_order_layout = QtWidgets.QHBoxLayout()
    rotation_order_label = QtWidgets.QLabel('Rotation order:')
    rotation_order_edit = QtWidgets.QLineEdit()
    rotation_order_edit.setObjectName("rotation_order_edit")
    rotation_order_edit.setStyleSheet("QLineEdit { color: #d9d9d9; }")
    rotation_order_edit.setFixedSize(rotation_order_w, rotation_order_h)
    rotation_order_edit.setReadOnly(True)
    rotation_order_layout.addWidget(rotation_order_label)
    rotation_order_layout.addWidget(rotation_order_edit)
    layout.addLayout(rotation_order_layout)

    layout.addSpacing(layout_spacing)

    best_layout = QtWidgets.QHBoxLayout()
    best_button = QtWidgets.QPushButton('')
    best_button.setObjectName("best_button")
    best_edit = QtWidgets.QLineEdit()
    best_edit.setObjectName("best_edit")
    best_edit.setStyleSheet("QLineEdit { color: #a5a5a5; }")
    best_edit.setFixedSize(percentage_line_w, percentage_line_h)
    best_edit.setReadOnly(True)
    best_layout.addWidget(best_button)
    best_layout.addWidget(best_edit)
    layout.addLayout(best_layout)
    best_button.clicked.connect(lambda: [convert_rotation_order(get_order_from_button(best_button)), update_rotation_order(window)])
    best_button.setFixedSize(button_w, button_h)
    best_button.setStyleSheet(
        "QPushButton {"
        "    background-color: #638970;"
        "    border: none;"
        "    color: #e9e9e9;"
        "    border-radius: 5px;"
        "}"
        "QPushButton:hover {"
        "    background-color: #789883;"
        "    border-radius: 5px;"
        "}"
    )

    good_layout = QtWidgets.QHBoxLayout()
    good_button = QtWidgets.QPushButton('')
    good_button.setObjectName("good_button")
    good_edit = QtWidgets.QLineEdit()
    good_edit.setObjectName("good_edit")
    good_edit.setStyleSheet("QLineEdit { color: #a5a5a5; }")
    good_edit.setFixedSize(percentage_line_w, percentage_line_h)
    good_edit.setReadOnly(True)
    good_layout.addWidget(good_button)
    good_layout.addWidget(good_edit)
    good_button.clicked.connect(lambda: [convert_rotation_order(get_order_from_button(good_button)), update_rotation_order(window)])
    layout.addLayout(good_layout)
    good_button.setFixedSize(button_w, button_h)
    good_button.setStyleSheet(
        "QPushButton {"
        "    background-color: #74857b;"
        "    border: none;"
        "    color: #e9e9e9;"
        "    border-radius: 5px;"
        "}"
        "QPushButton:hover {"
        "    background-color: #839088;"
        "    border-radius: 5px;"
        "}"
    )

    average_layout = QtWidgets.QHBoxLayout()
    average_button = QtWidgets.QPushButton('')
    average_button.setObjectName("moderate_button")
    average_edit = QtWidgets.QLineEdit()
    average_edit.setObjectName("moderate_edit")
    average_edit.setStyleSheet("QLineEdit { color: #a5a5a5; }")
    average_edit.setFixedSize(percentage_line_w, percentage_line_h)
    average_edit.setReadOnly(True)
    average_layout.addWidget(average_button)
    average_button.clicked.connect(lambda: [convert_rotation_order(get_order_from_button(average_button)), update_rotation_order(window)])
    average_layout.addWidget(average_edit)
    layout.addLayout(average_layout)
    average_button.setFixedSize(button_w, button_h)
    average_button.setStyleSheet(
        "QPushButton {"
        "    background-color: #6b6b6b;"
        "    border: none;"
        "    color: #e9e9e9;"
        "    border-radius: 5px;"
        "}"
        "QPushButton:hover {"
        "    background-color: #7d7d7d;"
        "    border-radius: 5px;"
        "}"
    )

    average2_layout = QtWidgets.QHBoxLayout()
    average2_button = QtWidgets.QPushButton('')
    average2_button.setObjectName("average_button")
    average2_edit = QtWidgets.QLineEdit()
    average2_edit.setObjectName("average_edit")
    average2_edit.setStyleSheet("QLineEdit { color: #a5a5a5; }")
    average2_edit.setFixedSize(percentage_line_w, percentage_line_h)
    average2_edit.setReadOnly(True)
    average2_layout.addWidget(average2_button)
    average2_layout.addWidget(average2_edit)
    average2_button.clicked.connect(lambda: [convert_rotation_order(get_order_from_button(average2_button)), update_rotation_order(window)])
    layout.addLayout(average2_layout)
    average2_button.setFixedSize(button_w, button_h)
    average2_button.setStyleSheet(
        "QPushButton {"
        "    background-color: #6b6b6b;"
        "    border: none;"
        "    color: #e9e9e9;"
        "    border-radius: 5px;"
        "}"
        "QPushButton:hover {"
        "    background-color: #7d7d7d;"
        "    border-radius: 5px;"
        "}"
    )

    bad_layout = QtWidgets.QHBoxLayout()
    bad_button = QtWidgets.QPushButton('')
    bad_button.setObjectName("poor_button")
    bad_edit = QtWidgets.QLineEdit()
    bad_edit.setObjectName("poor_edit")
    bad_edit.setStyleSheet("QLineEdit { color: #a5a5a5; }")
    bad_edit.setFixedSize(percentage_line_w, percentage_line_h)
    bad_edit.setReadOnly(True)
    bad_layout.addWidget(bad_button)
    bad_layout.addWidget(bad_edit)
    layout.addLayout(bad_layout)
    bad_button.clicked.connect(lambda: [convert_rotation_order(get_order_from_button(bad_button)), update_rotation_order(window)])
    bad_button.setFixedSize(button_w, button_h)
    bad_button.setStyleSheet(
        "QPushButton {"
        "    background-color: #b38a88;"
        "    border: none;"
        "    color: #e9e9e9;"
        "    border-radius: 5px;"
        "}"
        "QPushButton:hover {"
        "    background-color: #c09a98;"
        "    border-radius: 5px;"
        "}"
    )

    worst_layout = QtWidgets.QHBoxLayout()
    worst_button = QtWidgets.QPushButton('')
    worst_button.setObjectName("inadequate_button")
    worst_edit = QtWidgets.QLineEdit()
    worst_edit.setObjectName("inadequate_edit")
    worst_edit.setStyleSheet("QLineEdit { color: #999; }")
    worst_edit.setFixedSize(percentage_line_w, percentage_line_h)
    worst_edit.setReadOnly(True)
    worst_layout.addWidget(worst_button)
    worst_layout.addWidget(worst_edit)
    worst_button.clicked.connect(lambda: [convert_rotation_order(get_order_from_button(worst_button)), update_rotation_order(window)])
    layout.addLayout(worst_layout)
    worst_button.setFixedSize(button_w, button_h)
    worst_button.setStyleSheet(
        "QPushButton {"
        "    background-color: #8f6b69;"
        "    border: none;"
        "    color: #e9e9e9;"
        "    border-radius: 5px;"
        "}"
        "QPushButton:hover {"
        "    background-color: #987371;"
        "    border-radius: 5px;"
        "}"
    )

    layout.addSpacing(layout_spacing)

    reload_button = QtWidgets.QPushButton('RELOAD')
    reload_button.clicked.connect(lambda: update_rotation_order(window))
    layout.addWidget(reload_button)
    reload_button.setFixedSize(reload_button_w, reload_button_h)
    reload_button.setStyleSheet(
        "QPushButton {"
        "    background-color: #515151;"
        "    border: none;"
        "    color: #e9e9e9;"
        "    border-radius: 5px;"
        "}"
        "QPushButton:hover {"
        "    background-color: #686868;"
        "    border-radius: 5px;"
        "}"
    )

    window_layout = QtWidgets.QVBoxLayout(window)
    window_layout.addWidget(central_widget)
    window.setLayout(window_layout)

    window.show()
    return window




# _________________________________ MICRO MOVE ________________________________________________________



micro_move_selected_objects = []
micro_move_callback_ids = []
micro_move_drivers = []
micro_move_animation_data = {}

def micro_move_copy_animation(object_name, attributes):
    global micro_move_animation_data
    
    if object_name not in micro_move_animation_data:
        micro_move_animation_data[object_name] = {}  # Inicializar un diccionario vacío para el objeto
    
    for attribute in attributes:
        keyframes = cmds.keyframe(object_name, attribute=attribute, query=True, timeChange=True)
        if keyframes:
            micro_move_animation_data[object_name][attribute] = {}
            for frame in keyframes:
                value = cmds.getAttr("{}.{}".format(object_name, attribute), time=frame)
                micro_move_animation_data[object_name][attribute][frame] = value
        else:
            pass


def micro_move_paste_animation(object_name):
    global micro_move_animation_data

    # Verificar si el objeto tiene datos de animación guardados
    if object_name in micro_move_animation_data:
        for attribute, frames in micro_move_animation_data[object_name].items():
            for frame, value in frames.items():
                # Establecer el valor del atributo en el frame específico
                cmds.setKeyframe(object_name, attribute=attribute, time=(frame,), value=value)
    else:
        pass


def micro_move_attribute_callback_function(msg, plug, other_plug, client_data):
    if msg & om.MNodeMessage.kAttributeSet:
        driver_name = client_data
        attr_name = plug.partialName()
        duplicated_name = f"{driver_name.replace('_driver', '_connect')}.{attr_name}"
        driver_value = cmds.getAttr(plug.name())

        if isinstance(driver_value, list) or isinstance(driver_value, tuple):
            modified_values = [value / 6 for value in driver_value[0]]
            cmds.setAttr(duplicated_name, *modified_values, type='double3')
        else:
            cmds.setAttr(duplicated_name, driver_value / 6)

def add_micro_move_callback(object_name):
    selection_list = om.MSelectionList()
    selection_list.add(object_name)
    mobject = selection_list.getDependNode(0)
    
    callback_id = om.MNodeMessage.addAttributeChangedCallback(mobject, micro_move_attribute_callback_function, object_name)
    micro_move_callback_ids.append(callback_id)


def micro_move_pre_drag(*args):
    global micro_move_selected_objects, micro_move_drivers

    cmds.undoInfo(openChunk=True)

    micro_move_selected_objects = cmds.ls(selection=True)
    if not micro_move_selected_objects:
        raise Exception("Please select an object.")

    transform_attrs = ['translateX', 'translateY', 'translateZ']

    for selected in micro_move_selected_objects:
        for attr in transform_attrs:
            micro_move_copy_animation(selected, transform_attrs)

    for selected in micro_move_selected_objects:
        duplicated = cmds.duplicate(selected, name=f"{selected}_connect", parentOnly=True)[0]
        driver = cmds.duplicate(selected, name=f"{selected}_driver", parentOnly=True)[0]
        micro_move_drivers.append(driver)

        # Desactivar los límites de transformación para el driver
        for attr in transform_attrs:
            cmds.transformLimits(driver, e=True, tx=(0, 0), etx=(False, False))
            cmds.transformLimits(driver, e=True, ty=(0, 0), ety=(False, False))
            cmds.transformLimits(driver, e=True, tz=(0, 0), etz=(False, False))

        for attr in transform_attrs:
            if not cmds.getAttr(f"{selected}.{attr}", lock=True):
                original_value = cmds.getAttr(f"{selected}.{attr}")
                new_value = original_value * 6
                cmds.setAttr(f"{driver}.{attr}", new_value)

        for attr in transform_attrs:
            if cmds.getAttr(f"{selected}.{attr}", se=True):  # se = settable
                cmds.connectAttr(f"{duplicated}.{attr}", f"{selected}.{attr}", force=True)

        add_micro_move_callback(driver)

    if micro_move_drivers:
        cmds.select(micro_move_drivers)
    micro_move_drivers.clear()


def micro_move_post_drag():
    global micro_move_selected_objects, micro_move_animation_data

    for selected in micro_move_selected_objects:
        duplicate_name = f"{selected}_connect"
        if cmds.objExists(duplicate_name):
            translate_values = {}
            for attr in ['translateX', 'translateY', 'translateZ']:
                # Verificar si el atributo es settable antes de intentar leerlo
                if cmds.getAttr(f"{duplicate_name}.{attr}", se=True):
                    translate_values[attr] = cmds.getAttr(f"{duplicate_name}.{attr}")
            cmds.delete(duplicate_name)
        else:
            translate_values = {'translateX': 0, 'translateY': 0, 'translateZ': 0}
            cmds.delete(duplicate_name)

        driver_name = f"{selected}_driver"
        if cmds.objExists(driver_name):
            cmds.delete(driver_name)

        current_frame = cmds.currentTime(query=True)
        micro_move_paste_animation(selected)

        for attr, value in translate_values.items():
            # Nuevamente verificar si el atributo es settable antes de intentar modificarlo
            if cmds.getAttr(f"{selected}.{attr}", se=True):
                cmds.setAttr(f"{selected}.{attr}", value)

    remove_micro_move_callbacks()
    micro_move_animation_data.clear()
    cmds.select(micro_move_selected_objects)

    cmds.undoInfo(closeChunk=True)


def remove_micro_move_callbacks():
    global micro_move_callback_ids
    for id in micro_move_callback_ids:
        om.MMessage.removeCallback(id)
    micro_move_callback_ids = []

def micro_move_post_drag_deferred(*args):
    cmds.evalDeferred(micro_move_post_drag)






# _________________________________ MICRO ROTATE ________________________________________________________


micro_rotate_callback_ids = []  # Lista para almacenar los IDs de los callbacks
micro_rotate_selected_objects = []
micro_rotate_drivers = []
micro_rotate_connects = []
micro_rotate_animation_data = {}

def micro_rotate_copy_animation(object_name, attributes):
    global micro_rotate_animation_data
    
    if object_name not in micro_rotate_animation_data:
        micro_rotate_animation_data[object_name] = {}  # Inicializar un diccionario vacío para el objeto
    
    for attribute in attributes:
        keyframes = cmds.keyframe(object_name, attribute=attribute, query=True, timeChange=True)
        if keyframes:
            micro_rotate_animation_data[object_name][attribute] = {}
            for frame in keyframes:
                value = cmds.getAttr("{}.{}".format(object_name, attribute), time=frame)
                micro_rotate_animation_data[object_name][attribute][frame] = value
        else:
            pass


def micro_rotate_paste_animation(object_name):
    global micro_rotate_animation_data

    # Verificar si el objeto tiene datos de animación guardados
    if object_name in micro_rotate_animation_data:
        for attribute, frames in micro_rotate_animation_data[object_name].items():
            for frame, value in frames.items():
                # Establecer el valor del atributo en el frame específico
                cmds.setKeyframe(object_name, attribute=attribute, time=(frame,), value=value)
    else:
        pass


def micro_rotate_pack_funtion():
    global micro_rotate_selected_objects, micro_rotate_drivers, micro_rotate_connects

    def add_micro_rotate_callback(source_object, target_object):
        selection_list = om.MSelectionList()
        selection_list.add(source_object)
        mobject = selection_list.getDependNode(0)
        
        def add_micro_rotate_dirty_callback(mobject, plug, client_data):
            if plug.partialName() in ('r', 'rx', 'ry', 'rz'):
                rotation = cmds.getAttr(f"{source_object}.rotate")[0]  # Devuelve una tupla
                half_rotation = [value / 6 for value in rotation]
                cmds.rotate(half_rotation[0], half_rotation[1], half_rotation[2], target_object, absolute=True)

        callback_id = om.MNodeMessage.addNodeDirtyPlugCallback(mobject, add_micro_rotate_dirty_callback, None)
        micro_rotate_callback_ids.append(callback_id)

    def remove_micro_rotate_callbacks():
        global micro_rotate_callback_ids
        for id in micro_rotate_callback_ids:
            om.MMessage.removeCallback(id)
        micro_rotate_callback_ids = []  # Limpiar la lista después de eliminar los callbacks

    micro_rotate_selected_objects = cmds.ls(selection=True)

    transform_attrs = ['rotateX', 'rotateY', 'rotateZ']
    for selected in micro_rotate_selected_objects:
        for attr in transform_attrs:
            micro_rotate_copy_animation(selected, transform_attrs)

    for selected in micro_rotate_selected_objects:
        connect = cmds.duplicate(selected, name=f"{selected}_connect", parentOnly=True)[0]
        driver = cmds.duplicate(selected, name=f"{selected}_driver", parentOnly=True)[0]
        micro_rotate_drivers.append(driver)

        # Desactivar los límites de transformación para el driver
        for attr in transform_attrs:
            cmds.transformLimits(driver, e=True, rx=(0, 0), erx=(False, False))
            cmds.transformLimits(driver, e=True, ry=(0, 0), ery=(False, False))
            cmds.transformLimits(driver, e=True, rz=(0, 0), erz=(False, False))

        transform_attrs = ['rotateX', 'rotateY', 'rotateZ']
        for attr in transform_attrs:
            if not cmds.getAttr(f"{selected}.{attr}", lock=True):
                original_value = cmds.getAttr(f"{selected}.{attr}")
                new_value = original_value * 6
                cmds.setAttr(f"{driver}.{attr}", new_value)
        
        # Conectar los canales visibles y keyables
        for attr in transform_attrs:
            if cmds.getAttr(f"{selected}.{attr}", se=True):  # se = settable
                try:
                    cmds.connectAttr(f"{connect}.{attr}", f"{selected}.{attr}", force=True)
                except RuntimeError as e:
                    print(f"Unable to connect {attr} from {duplicated} to {selected}: {e}")

        add_micro_rotate_callback(driver, connect)
        
    if micro_rotate_drivers:
        cmds.select(micro_rotate_drivers)
    micro_rotate_drivers.clear()



def micro_rotate_pre_drag(*args):
    cmds.undoInfo(openChunk=True)
    micro_rotate_pack_funtion()

def micro_rotate_post_deferred():
    global micro_rotate_selected_objects, micro_rotate_animation_data

    for selected in micro_rotate_selected_objects:
        duplicate_name = f"{selected}_connect"
        driver_name = f"{selected}_driver"

        if cmds.objExists(duplicate_name):
            rotate_values = {}
            for attr in ['rotateX', 'rotateY', 'rotateZ']:
                # Verificar si el atributo es settable antes de intentar leerlo
                if cmds.getAttr(f"{duplicate_name}.{attr}", se=True):
                    rotate_values[attr] = cmds.getAttr(f"{duplicate_name}.{attr}")
            cmds.delete(duplicate_name)
        else:
            rotate_values = {'rotateX': 0, 'rotateY': 0, 'rotateZ': 0}
            cmds.delete(duplicate_name)

        if cmds.objExists(duplicate_name):
            cmds.delete(duplicate_name)
        if cmds.objExists(driver_name):
            cmds.delete(driver_name)

        current_frame = cmds.currentTime(query=True)
        micro_rotate_paste_animation(selected)

        for attr, value in rotate_values.items():
            # Nuevamente verificar si el atributo es settable antes de intentar modificarlo
            if cmds.getAttr(f"{selected}.{attr}", se=True):
                cmds.setAttr(f"{selected}.{attr}", value)

    remove_micro_rotate_callbacks()
    micro_rotate_animation_data.clear()
    cmds.undoInfo(closeChunk=True)
    cmds.select(micro_rotate_selected_objects)


def remove_micro_rotate_callbacks():
    global micro_rotate_callback_ids
    for id in micro_rotate_callback_ids:
        om.MMessage.removeCallback(id)
    micro_rotate_callback_ids = []

def micro_rotate_post_drag(*args):
    cmds.evalDeferred(micro_rotate_post_deferred)




# _______________________________________________ MICRO MOVE CALL __________________________________________________

def activate_micro_move(*args):

    current_context = cmds.currentCtx()
    microMoveContext = "microMoveCtx"
    microRotateContext = "microRotateCtx"


    if cmds.contextInfo("dummyCtx", exists=True):
        if cmds.contextInfo(microRotateContext, exists=True):
            cmds.deleteUI(microRotateContext, toolContext=True)

        if cmds.contextInfo(microMoveContext, exists=True):
            cmds.deleteUI(microMoveContext, toolContext=True)

        if cmds.contextInfo('dummyCtx', exists=True):
            cmds.deleteUI('dummyCtx', toolContext=True)

        cmds.setToolTo('moveSuperContext')

    else:

        if current_context == "RotateSuperContext":
            if cmds.contextInfo(microRotateContext, exists=True):
                cmds.setToolTo(microRotateContext)
            else:
                cmds.manipRotateContext(microRotateContext)
                # 0 object, 1 world, 2 gimbal
                cmds.manipRotateContext(microRotateContext, e=True, preDragCommand=(micro_rotate_pre_drag, 'transform'), postDragCommand=(micro_rotate_post_drag, 'transform'), mode=2)
                cmds.setToolTo(microRotateContext)

        elif current_context == "moveSuperContext":
            if cmds.contextInfo(microMoveContext, exists=True):
                cmds.setToolTo(microMoveContext)
            else:
                cmds.manipMoveContext(microMoveContext)
                cmds.manipMoveContext(microMoveContext, e=True, preDragCommand=(micro_move_pre_drag, 'transform'), postDragCommand=(micro_move_post_drag_deferred, 'transform'), mode=0)
                cmds.setToolTo(microMoveContext)



