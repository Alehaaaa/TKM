


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
import maya.OpenMaya as om
import maya.OpenMayaUI as mui

try:
    from shiboken2 import wrapInstance
    from PySide2 import QtWidgets, QtCore
    from PySide2.QtWidgets import QApplication, QDesktopWidget
    from PySide2 import QtWidgets
    from PySide2.QtCore import *
    from PySide2.QtGui import *
    from PySide2.QtWidgets import *
    from PySide2.QtGui import QRegExpValidator
    from PySide2.QtCore import QRegExp
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
import urllib.request
import re
import shutil
import base64
from functools import partial
from collections import Counter

import TheKeyMachine


python_version = f"{sys.version_info.major}{sys.version_info.minor}"


import TheKeyMachine.core.customGraph as cg
import TheKeyMachine.core.toolbar as tb
import TheKeyMachine.mods.mediaMod as media
import TheKeyMachine.mods.generalMod as general
import TheKeyMachine.mods.uiMod as ui
import TheKeyMachine.mods.keyToolsMod as keyTools
import TheKeyMachine.mods.selSetsMod as selSets


# _____________________________________________________ General _______________________________________________________________#

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



def clear_timeslider_selection():

    # fix temporal para limpiar el timeslider
    selection = cmds.ls(selection=True)

    # Crear y eliminar un nodo temporal
    empty_node = cmds.createNode('transform', name='tempNode')
    cmds.delete(empty_node)

    # Restaurar la selección original, si había algo seleccionado
    if selection:
        cmds.select(selection)




def get_time_range_selected():
    aTimeSlider = mel.eval('$tmpVar=$gPlayBackSlider')
    timeRange = cmds.timeControl(aTimeSlider, q=True, rangeArray=True)
    
    # Verificar que el rango de tiempo seleccionado no esta vacío
    if timeRange[0] == timeRange[1]:
        return None

    return timeRange



# Esta es una version nueva que evalua correctamente si es un rango o no. Dejo la otra porque se usa en algunos sitios. Hay que limpiar.
def get_selected_time_range():
    aTimeSlider = mel.eval('$tmpVar=$gPlayBackSlider')
    timeRange = cmds.timeControl(aTimeSlider, q=True, rangeArray=True)
    current_time = cmds.currentTime(query=True)

    # Verificar si el rango de tiempo seleccionado es más que un solo frame
    if (timeRange[1] - timeRange[0]) > 1 or (timeRange[0] != current_time and timeRange[1] != current_time + 1):
        return timeRange
    else:
        return None


def get_graph_editor_selected_keyframes():
    anim_curves = cmds.keyframe(q=True, selected=True, name=True)
    if not anim_curves:
        return []

    keyframes = []
    for curve in anim_curves:
        keyframes += [(curve, frame) for frame in cmds.keyframe(curve, q=True, selected=True)]

    return keyframes


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


def get_selected_channels():
    # Obtén el nombre del Channel Box principal
    main_channel_box = mel.eval('global string $gChannelBoxName; $temp=$gChannelBoxName;')

    # Obtén los canales seleccionados
    selected_channels = cmds.channelBox(main_channel_box, query=True, selectedMainAttributes=True)

    return selected_channels





# Estas dos funciones la idea era usarlas para hacer overlap

def find_root_in_selection(objects):
    """
    Encuentra el nodo raíz en una selección.
    Sube por la jerarquía hasta el nodo raíz y verifica si los hijos están en la lista.
    """
    # Ordenamos los objetos por nombre para garantizar que procesamos primero el nodo padre si está presente.
    objects_sorted = sorted(objects)
    
    for obj in objects_sorted:
        # Obtiene la lista de descendientes
        descendants = cmds.listRelatives(obj, allDescendents=True) or []
        
        # Verifica si algún descendiente coincide con nuestra lista de objetos
        matching_descendants = [desc for desc in descendants if desc in objects]
        
        # Si hay coincidencias, significa que el objeto actual es un nodo raíz para los objetos seleccionados.
        if matching_descendants:
            return obj

    return None



def find_all_roots_in_selection():
    """
    Identifica todos los nodos raíces en la selección.
    """
    selection = cmds.ls(selection=True)
    root_nodes = []
    
    while selection:
        root_node = find_root_in_selection(selection)
        if root_node:
            root_nodes.append(root_node)
            
            # Obtiene la lista de descendientes del nodo raíz
            descendants = cmds.listRelatives(root_node, allDescendents=True) or []
            
            # Elimina el nodo raíz y todos sus descendientes de la lista de selección
            for obj in [root_node] + descendants:
                if obj in selection:
                    selection.remove(obj)
        else:
            break
    
    return root_nodes




# --------------------------------------------------- LINK OBJECTS -----------------------------------------------------


def mod_link_objects(*args):
    # Get the current state of the modifiers
    mods = mel.eval('getModifiers')
    shift_pressed = bool(mods % 2)  # Check if Shift is pressed

    if shift_pressed:
        paste_link()
    else:
        copy_link()



# Variables globales
relative_data = {}


def load_relative_data():
    global relative_data

    matrix_file_path = general.get_copy_link_data_file()
    
    # Verificar si el archivo existe
    if not os.path.exists(matrix_file_path):
        cmds.warning("No saved relative matrix data found")
        return
    
    # Leer el diccionario del archivo JSON
    with open(matrix_file_path, 'r') as f:
        relative_data = json.load(f)



def copy_link(*args):

    import json
    import os
    import maya.cmds as cmds
    import maya.api.OpenMaya as om


    matrix_file_path = general.get_copy_link_data_file()
    
    seleccion = cmds.ls(selection=True)
    if len(seleccion) < 2:
        print("Select at least 2 objects")
        return
    
    main_obj = seleccion[-1]
    follow_objs = seleccion[:-1]
    
    save_dict = {"main_obj": main_obj, "relative_matrices": {}}
    
    for follow_obj in follow_objs:
        main_matrix = cmds.xform(main_obj, query=True, matrix=True, worldSpace=True)
        follow_matrix = cmds.xform(follow_obj, query=True, matrix=True, worldSpace=True)
        
        main_mmatrix = om.MMatrix(main_matrix)
        follow_mmatrix = om.MMatrix(follow_matrix)
        
        relative_matrix = follow_mmatrix * main_mmatrix.inverse()
        
        # Guardar la matriz relativa en el diccionario
        save_dict["relative_matrices"][follow_obj] = [relative_matrix.getElement(i, j) for i in range(4) for j in range(4)]
    
    # Guardar el diccionario en un archivo JSON

    matrix_file_folder = general.get_copy_link_data_folder()
    os.makedirs(matrix_file_folder, exist_ok=True)
    with open(matrix_file_path, 'w') as f:
        json.dump(save_dict, f)

    print("Copied link data")



    load_relative_data()



def paste_link(*args):
    import json
    import os
    import maya.cmds as cmds
    import maya.api.OpenMaya as om

    global relative_data

    main_obj = relative_data.get("main_obj")
    relative_matrices = relative_data.get("relative_matrices", {})
    
    # No necesitamos verificar la selección. Usamos directamente los objetos de relative_data.
    follow_objs = list(relative_matrices.keys())
    
    # Verificar si existe un rango seleccionado en el timeline
    playback_range = cmds.playbackOptions(query=True, minTime=True), cmds.playbackOptions(query=True, maxTime=True)
    range_start, range_end = cmds.timeControl('timeControl1', q=True, rangeArray=True)
    
    if range_start != playback_range[0] or range_end != playback_range[1]:
        frames = list(range(int(range_start), int(range_end)))
    else:
        # Si no hay un rango seleccionado, aplicar solo al frame actual
        frames = [cmds.currentTime(query=True)]
    
    for frame in frames:
        cmds.currentTime(frame)
        
        for follow_obj in follow_objs:
            if follow_obj in relative_matrices:
                relative_matrix_list = relative_matrices[follow_obj]
                relative_matrix = om.MMatrix()
                for i in range(4):
                    for j in range(4):
                        relative_matrix.setElement(i, j, relative_matrix_list[i * 4 + j])
                
                main_matrix = cmds.xform(main_obj, query=True, matrix=True, worldSpace=True)
                main_mmatrix = om.MMatrix(main_matrix)
                
                new_follow_matrix = relative_matrix * main_mmatrix
                new_follow_matrix_list = [new_follow_matrix.getElement(i, j) for i in range(4) for j in range(4)]
                
                cmds.xform(follow_obj, matrix=new_follow_matrix_list, worldSpace=True)
                cmds.setKeyframe(follow_obj, attribute='translate', t=frame)
                cmds.setKeyframe(follow_obj, attribute='rotate', t=frame)
                cmds.setKeyframe(follow_obj, attribute='scale', t=frame)
            else:
                cmds.warning(f"Could not save relative matrix for {follow_obj}")




# Esta version esta simplificada y no mira si hay un rango seleccionado, de esta forma el callback
# es más rápido y actualiza sin dar problemas al rotar o mover el objeto


def paste_link_callback():
    import maya.api.OpenMaya as om

    global relative_data

    main_obj = relative_data.get("main_obj")
    relative_matrices = relative_data.get("relative_matrices", {})
    
    # No necesitamos verificar la selección. Usamos directamente los objetos de relative_data.
    follow_objs = list(relative_matrices.keys())

    for follow_obj in follow_objs:
        if follow_obj in relative_matrices:
            relative_matrix_list = relative_matrices[follow_obj]
            relative_matrix = om.MMatrix()
            for i in range(4):
                for j in range(4):
                    relative_matrix.setElement(i, j, relative_matrix_list[i * 4 + j])
            
            main_matrix = cmds.xform(main_obj, query=True, matrix=True, worldSpace=True)
            main_mmatrix = om.MMatrix(main_matrix)
            
            new_follow_matrix = relative_matrix * main_mmatrix
            new_follow_matrix_list = [new_follow_matrix.getElement(i, j) for i in range(4) for j in range(4)]
            
            cmds.xform(follow_obj, matrix=new_follow_matrix_list, worldSpace=True)

        else:
            cmds.warning(f"Could not save relative matrix for {follow_obj}")







attribute_callback_id = None
time_callback_id = None
process_callback = False


def add_link_obj_callbacks(*args):
    import maya.api.OpenMaya as om

    global relative_data, attribute_callback_id, time_callback_id, eval_callback_id, process_callback

    process_callback = True
    
    # Obtén el nombre del objeto principal desde relative_data
    main_obj_name = relative_data.get("main_obj")
    if not main_obj_name:
        cmds.warning("Relative data object not found")
        return
    
    # Obtén el MObject del objeto principal
    selection_list = om.MSelectionList()
    selection_list.add(main_obj_name)
    main_obj_mobject = selection_list.getDependNode(0)
    
    # Registra el callback de atributo
    attribute_callback_id = om.MNodeMessage.addAttributeChangedCallback(main_obj_mobject, attribute_callback_function)
    
    # Registra el callback de cambio de tiempo
    time_callback_id = om.MEventMessage.addEventCallback('timeChanged', time_callback_function)






def attribute_callback_function(msg, plug, otherPlug, clientData):
    import maya.api.OpenMaya as om
    global process_callback
    
    if not process_callback:
        return
    
    if msg & om.MNodeMessage.kAttributeSet:
        process_callback = False
        paste_link_callback()
        process_callback = True

def time_callback_function(clientData):
    import maya.api.OpenMaya as om
    global process_callback
    if not process_callback:
        return
    process_callback = False
    paste_link_callback()  # Llamada a tu función set_matrix
    process_callback = True



def remove_link_obj_callbacks(*args):
    import maya.api.OpenMaya as om
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



# ---------------------------------------------------------- SHARE KEYS ---------------------------------------------------------


def share_keys(*args):
    objetos = cmds.ls(selection=True)
    
    if len(objetos) < 2:
        print("Select at least 2 objects")
        return
    
    objeto_principal = objetos[0]
    objetos_secundarios = objetos[1:]

    time_range = get_time_range_selected()

    # Eliminamos la verificación de canales seleccionados
    frames_claves = []
    if not time_range or (time_range[1] - time_range[0] == 1):
        frames_claves = cmds.keyframe(objeto_principal, query=True)
    else:
        frames_claves = cmds.keyframe(objeto_principal, query=True, time=(time_range[0], time_range[1]))

    if not frames_claves:
        cmds.warning(f"There is no keys in {objeto_principal}")
        return

    for objeto_secundario in objetos_secundarios:
        if time_range:
            frames_secundario = cmds.keyframe(objeto_secundario, query=True, time=(time_range[0], time_range[1])) or []
        else:
            frames_secundario = cmds.keyframe(objeto_secundario, query=True) or []

        if not frames_secundario:
            for frame in frames_claves:
                cmds.setKeyframe(objeto_secundario, time=frame)
            continue

        for frame in frames_claves:
            if frame not in frames_secundario:
                cmds.setKeyframe(objeto_secundario, time=frame, insert=True)
        
        for frame in frames_secundario:
            if frame not in frames_claves:
                cmds.cutKey(objeto_secundario, time=(frame, frame))




# ______________________________________ ReBlock Move


import maya.cmds as cmds
from collections import Counter

def reblock_move(*args):
    # Obtener la lista de objetos seleccionados
    objetos = cmds.ls(selection=True, long=True)  # Usar nombres largos para mayor precisión

    # Verificar que haya al menos un objeto seleccionado
    if len(objetos) < 1:
        print("Select at least one object")
        return

    # Obtener las curvas de animación de los objetos seleccionados y sus shapes
    curvas = []
    objetos_procesados = set()  # Conjunto para almacenar nombres de objetos ya procesados

    for objeto in objetos:
        # Saltar objetos repetidos
        if objeto in objetos_procesados:
            continue
        objetos_procesados.add(objeto)

        # Obtener las curvas del transform node
        curvas_objeto = cmds.listConnections(objeto, type="animCurve")
        if curvas_objeto:
            curvas.extend(curvas_objeto)

        # Obtener las curvas del shape node
        shapes = cmds.listRelatives(objeto, shapes=True, fullPath=True)
        if shapes:
            for shape in shapes:
                curvas_shape = cmds.listConnections(shape, type="animCurve")
                if curvas_shape:
                    curvas.extend(curvas_shape)

    # Crear un diccionario para contar perfiles
    perfiles = Counter()

    # Identificar perfil de cada curva y actualizar el contador
    for curva in curvas:
        keyframes = cmds.keyframe(curva, query=True, timeChange=True)
        if keyframes is None:
            continue
        fotogramas = tuple(sorted(keyframes))
        perfiles[fotogramas] += 1

    # Identificar el perfil mayoritario
    perfil_mayoritario, _ = perfiles.most_common(1)[0]

    # Corregir curvas que no coinciden con el perfil mayoritario
    for curva in curvas:
        keyframes = cmds.keyframe(curva, query=True, timeChange=True)
        if keyframes is None:
            continue
        fotogramas = tuple(sorted(keyframes))

        if fotogramas != perfil_mayoritario:
            # Ajustar el número de keyframes
            if len(fotogramas) < len(perfil_mayoritario):
                # Añadir keyframes faltantes
                for frame in perfil_mayoritario:
                    if frame not in fotogramas:
                        cmds.setKeyframe(curva, time=frame, value=0)  # Añadir keyframe en la posición correcta

            elif len(fotogramas) > len(perfil_mayoritario):
                # Eliminar keyframes sobrantes
                for frame in fotogramas:
                    if frame not in perfil_mayoritario:
                        cmds.cutKey(curva, time=(frame, frame), option="keys")  # Eliminar keyframe

            # Volver a obtener los keyframes después de añadir/eliminar
            keyframes = cmds.keyframe(curva, query=True, timeChange=True)
            fotogramas = tuple(sorted(keyframes))

            # Determinar si la curva minoritaria está adelantada o retrasada
            adelantada = fotogramas[0] > perfil_mayoritario[0]

            # Mover keyframes en la dirección adecuada
            rango_keyframes = range(min(len(fotogramas), len(perfil_mayoritario)))
            if adelantada:
                # Mover keyframes de inicio a fin
                for i in rango_keyframes:
                    frame = fotogramas[i]
                    frame_objetivo = perfil_mayoritario[i]
                    cmds.keyframe(curva, edit=True, time=(frame,), timeChange=frame_objetivo)
            else:
                # Mover keyframes de fin a inicio
                for i in reversed(rango_keyframes):
                    frame = fotogramas[i]
                    frame_objetivo = perfil_mayoritario[i]
                    cmds.keyframe(curva, edit=True, time=(frame,), timeChange=frame_objetivo)





def reblock_insert(*args):
    # Obtener la lista de objetos actualmente seleccionados en la escena
    objetos = cmds.ls(selection=True)

    # Verificar que haya al menos dos objetos seleccionados
    if len(objetos) < 2:
        print("Select at least one objects")
        return

    # Crear una lista de fotogramas clave de todos los objetos
    frames_claves = []
    for objeto in objetos:
        fotogramas = cmds.keyframe(objeto, query=True, timeChange=True)
        if fotogramas is not None:
            frames_claves.extend(fotogramas)

    # Identificar los fotogramas clave "mayoritarios" como los más comunes
    contador_frames = Counter(frames_claves)
    frames_mayoritarios = {frame for frame, count in contador_frames.items() if count >= len(objetos) / 2}

    for objeto in objetos:
        # Obtener los fotogramas clave específicos del objeto actual
        frames_objeto = set(cmds.keyframe(objeto, query=True, timeChange=True) or [])
        
        for frame in frames_objeto:
            # Si el fotograma no es mayoritario, encontrar el fotograma mayoritario más cercano y insertar una nueva clave allí
            if frame not in frames_mayoritarios:
                frame_mayoritario_cercano = min(frames_mayoritarios, key=lambda x: abs(x - frame))
                valor = cmds.keyframe(objeto, query=True, time=(frame, frame), valueChange=True)
                if valor:
                    cmds.setKeyframe(objeto, time=frame_mayoritario_cercano, value=valor[0], insert=True)
                    cmds.cutKey(objeto, time=(frame, frame))




#___________________________ BAKE ANIM  _____________________________________



#import maya.OpenMayaUI as mui
#from PySide2 import QtWidgets, QtCore
#from shiboken2 import wrapInstance


def bake_animation(bake_interval=1, window=None):

    cmds.undoInfo(openChunk=True)

    try:
        # Obtener los objetos seleccionados.
        selected_objects = cmds.ls(selection=True)

        # Verificar si no hay objetos seleccionados.
        if not selected_objects:
            print("Select at least one object before baking")
            return

        # Definir el rango de tiempo de la animación.
        start_frame = cmds.playbackOptions(query=True, minTime=True)
        end_frame = cmds.playbackOptions(query=True, maxTime=True)

        # Hacer bake a las curvas de animación de los objetos seleccionados.
        cmds.bakeResults(
            selected_objects,
            time=(start_frame, end_frame),
            sampleBy=bake_interval,
            preserveOutsideKeys=True,
            sparseAnimCurveBake=False,
            removeBakedAttributeFromLayer=False,
            bakeOnOverrideLayer=False,
            controlPoints=False,
            shape=True
        )

        # Cambiar las tangentes de las claves a stepped.
        for obj in selected_objects:
            anim_curves = cmds.listConnections(obj, type='animCurve')
            if anim_curves:
                for curve in anim_curves:
                    cmds.selectKey(curve, add=True, keyframe=True)
                    cmds.keyTangent(inTangentType='stepnext', outTangentType='step')

    
    except Exception as e:
        cmds.warning("An error occurred: {}".format(e))
    
    finally:
        # Cerrar el chunk de undo
        cmds.undoInfo(closeChunk=True)

    if window:
        window.close()

def bake_anim_window(*args):
    screen_width, screen_height = get_screen_resolution()
    screen_width = screen_width

    # Variables para implementar el drag
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

    def bake_button_clicked():
        interval = bake_interval_line_edit.text()

        if interval:
            try:
                bake_interval = float(interval)
                bake_animation(bake_interval=bake_interval, window=window)
                
            except ValueError:
                cmds.warning("Please enter a valid number for bake interval")

    parent = wrapInstance(int(mui.MQtUtil.mainWindow()), QtWidgets.QWidget)

    window = QtWidgets.QWidget(parent, QtCore.Qt.Window | QtCore.Qt.FramelessWindowHint)
    window.resize(200, 100)
    window.setObjectName('BakeAnimWindow')
    window.setWindowTitle('Bake Anim')
    window.setWindowOpacity(1.0) 
    window.setAttribute(QtCore.Qt.WA_TranslucentBackground)

    window.mousePressEvent = mousePressEvent
    window.mouseMoveEvent = mouseMoveEvent
    window.mouseReleaseEvent = mouseReleaseEvent

    central_widget = QtWidgets.QWidget(window)
    central_widget.setStyleSheet("""
        QWidget {
            background-color: #454545; 
            border-radius: 10px;
            border: 2px solid #393939;
        }
        QLabel {
            border: none;
        }
        """)
    layout = QtWidgets.QVBoxLayout(central_widget)
    layout.setContentsMargins(10, 10, 10, 10)

    window_layout = QtWidgets.QVBoxLayout(window)
    window_layout.addWidget(central_widget)
    window.setLayout(window_layout)

    close_button = QtWidgets.QPushButton('X')
    close_button.setFixedSize(20, 20)
    close_button.setStyleSheet(
        "QPushButton {"
        "    background-color: #585858;"
        "    color: #ccc;"
        "    border-radius: 4px;"
        "    border: none;"
        "}"
        "QPushButton:hover {"
        "    background-color: #c56054;"
        "    border-radius: 4px;"
        "    border: none;"
        "}"
    )
    close_button.clicked.connect(window.close)

    # Definición de los widgets 
    bake_label = QtWidgets.QLabel("Add interval to bake:")
    bake_label.setStyleSheet("color: #ccc;")

    bake_interval_line_edit = QtWidgets.QLineEdit()
    bake_interval_line_edit.setStyleSheet("background-color: #282828; color: #ccc; border-radius: 5px; padding: 5px; border: none;")
    bake_interval_line_edit.setFixedSize(40, 30)
    # Limitar la entrada a dos dígitos numéricos

    try:
        from PySide6.QtCore import QRegularExpression
        from PySide6.QtGui import QRegularExpressionValidator

        def create_regex(pattern):
            return QRegularExpression(pattern)

        def create_validator(pattern, parent=None):
            return QRegularExpressionValidator(QRegularExpression(pattern), parent)
    except ImportError:
        from PySide2.QtCore import QRegExp
        from PySide2.QtGui import QRegExpValidator

        def create_regex(pattern):
            return QRegExp(pattern)

        def create_validator(pattern, parent=None):
            return QRegExpValidator(QRegExp(pattern), parent)



    reg_ex = create_regex("^[0-9]{1,2}$")
    input_validator = create_validator("^[0-9]{1,2}$", bake_interval_line_edit)
    bake_interval_line_edit.setValidator(input_validator)


    bake_button = QtWidgets.QPushButton('Bake')
    bake_button.setFixedSize(80, 30)
    bake_button.setStyleSheet(
        "QPushButton {"
        "    background-color: #525252;"
        "    border: none;"
        "    border-radius: 5px;"
        "    color: #ccc;"
        "    border: none;"
        "}"
        "QPushButton:hover {"
        "    background-color: #626262;"
        "    border-radius: 5px;"
        "    border: none;"
        "}"
    )


    if screen_width == 3840:
        window.resize(350, 100)
        layout.setContentsMargins(20, 20, 20, 20)
        close_button.setFixedSize(40, 40)
        bake_label.setStyleSheet("color: #ccc; font: 20px;")
        bake_interval_line_edit.setStyleSheet("background-color: #282828; color: #ccc; border-radius: 5px; padding: 5px; border: none;")
        bake_interval_line_edit.setFixedSize(100, 50)
        bake_button.setFixedSize(150, 50)



    bake_button.clicked.connect(bake_button_clicked)

    # Crear un QHBoxLayout para el QLineEdit y el QPushButton
    bake_layout = QtWidgets.QHBoxLayout()
    bake_layout.addWidget(bake_interval_line_edit)
    bake_layout.addWidget(bake_button)

    layout.addWidget(close_button, alignment=QtCore.Qt.AlignRight)
    layout.addWidget(bake_label, alignment=QtCore.Qt.AlignLeft)
    layout.addLayout(bake_layout)
    window.show()
    # Adjust the window position
    parent_geometry = parent.geometry()
    x = parent_geometry.x() + parent_geometry.width() / 2 - window.width() + 15
    y = parent_geometry.y() + parent_geometry.height() / 2 - window.height() / 2 + 250
    window.move(x, y)



# ____________________________________________________ ShiftKeys Box _____________________________________________________________#


def delete_keyframes_before_current_time():
    # Obtén los objetos seleccionados
    selected = cmds.ls(selection=True)

    if not selected:
        print('No hay objetos seleccionados')
        return

    # Obtiene el tiempo actual
    current_time = cmds.currentTime(query=True)

    for obj in selected:
        # Obtiene todos los keyframes del objeto
        keyframes = cmds.keyframe(obj, query=True)

        if not keyframes:
           # print(f'No hay keyframes en el objeto: {obj}')
            continue

        # Elimina los keyframes que están antes de la currentTime
        for keyframe in sorted(keyframes):
            if keyframe < current_time:
                cmds.cutKey(obj, time=(keyframe, keyframe))


def delete_keyframes_after_current_time():
    # Obtén los objetos seleccionados
    selected = cmds.ls(selection=True)

    if not selected:
        print('No hay objetos seleccionados')
        return

    # Obtiene el tiempo actual
    current_time = cmds.currentTime(query=True)

    for obj in selected:
        # Obtiene todos los keyframes del objeto
        keyframes = cmds.keyframe(obj, query=True)

        if not keyframes:
          #  print(f'No hay keyframes en el objeto: {obj}')
            continue

        # Elimina los keyframes que están después de la currentTime
        for keyframe in sorted(keyframes):
            if keyframe > current_time:
                cmds.cutKey(obj, time=(keyframe, keyframe))


def select_all_animation_curves(*args):
    # Tipos de curvas de animación que quieres seleccionar
    tipos_de_curvas = ["animCurveTL", "animCurveTA", "animCurveTT", "animCurveTU"]

    # Lista para almacenar las curvas seleccionadas
    curvas_seleccionadas = []

    # Recorre todos los tipos de curvas y busca las que coinciden
    for tipo in tipos_de_curvas:
        curvas = cmds.ls(type=tipo)
        if curvas:
            curvas_seleccionadas.extend(curvas)

    # Selecciona las curvas encontradas
    if curvas_seleccionadas:
        cmds.select(curvas_seleccionadas)
        cmds.selectKey(add=True)
    else:
        print("No anim curves found")
        

def clear_selected_keys(*args):
    cmds.selectKey(clear=True)



# For Hotkeys

def hotkey_move_keyframes_left():
    desplazamiento = cmds.intField("move_keyframes_int", q=True, value=True)
    desplazamiento = desplazamiento *-1
    keyTools.move_keyframes_in_range(-1)


def hotkey_move_keyframes_right():
    desplazamiento = cmds.intField("move_keyframes_int", q=True, value=True)
    keyTools.move_keyframes_in_range(desplazamiento)

# _____


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


def move_keyframes_in_range(*args):

    desplazamiento = cmds.intField("move_keyframes_int", q=True, value=True)

    if args[0] == -1:
        desplazamiento = -int(desplazamiento)


    currentT = cmds.currentTime(q=True)

    # Obtén el control deslizante de tiempo actual
    aTimeSlider = mel.eval('$tmpVar=$gPlayBackSlider')

    # Obtén el rango seleccionado en el rangeSlider
    timeRange = cmds.timeControl(aTimeSlider, q=True, rangeArray=True)

    start_frame = int(timeRange[0])
    end_frame = int(timeRange[1])

    # Verifica si hay un rango seleccionado
    if abs(end_frame - start_frame) > 1:
        cmds.undoInfo(openChunk=True)

        # Obtén todas las curvas de animación en la escena
        animation_curves = cmds.ls(type='animCurve')
        cmds.selectKey(clear=True)

        for curve in animation_curves:
            # Filtra las curvas que no tienen keyframes en el rango de tiempo
            if not cmds.keyframe(curve, query=True, time=(start_frame, end_frame)):
                continue

            # Selecciona todos los keyframes de la curva dentro del rango seleccionado
            cmds.selectKey(curve, time=(start_frame, end_frame), add=True)
        
        # Mueve los keyframes seleccionados
        # Inicia un nuevo bloque de deshacer
        cmds.keyframe(edit=True, includeUpperBound=True, animation='keys', relative=True, option='over', timeChange=desplazamiento)

        # Mover el tiempo un frame a la izquierda
        moveLeft = currentT + desplazamiento
        cmds.currentTime(moveLeft)
        cmds.undoInfo(closeChunk=True)


    else:
        selection = cmds.ls(selection=True)

        if not selection:
            print("No object selected")
        else:

            # Comprobar si hay keyframes seleccionados
            selected_keys = mel.eval('keyframe -query -selected')
            if selected_keys:
                # Si hay keyframes seleccionados, moverlos
                mel.eval('keyframe -e -iub true -animation keys -r -o over -tc {}'.format(desplazamiento))
            else:
                for obj in selection:
                    # Verificar si el objeto seleccionado tiene un keyframe en el tiempo actual
                    hasKeyframe = cmds.keyframe(obj, query=True, time=(currentT, currentT))
                    if hasKeyframe:
                        # Comprobar si hay un keyframe en currentT + 1
                        hasKeyframeBefore = cmds.keyframe(obj, query=True, time=(currentT + 1, currentT + 1))

                        # Opción 2: mover el keyframe en currentT - 1 a currentT - 2
                        if hasKeyframeBefore:
                            cmds.keyframe(obj, edit=True, timeChange=desplazamiento, relative=True, time=(currentT + 1, currentT + 1))

                        # Mover el keyframe un frame a la izquierda
                        cmds.keyframe(obj, edit=True, timeChange=desplazamiento, relative=True, time=(currentT, currentT))

                # Mover el tiempo un frame a la izquierda
                moveLeft = currentT + desplazamiento
                cmds.currentTime(moveLeft)




# _____________________________________________________________________________________________________________________

is_dragging = False
original_keyframes = {}
original_values = {}  # Vamos a guardar el valor original de cada atributo
frame_data_cache = {}  # New dictionary to cache frame data for performance
original_keyframe_values = {} 

global tween_frame_data_cache
tween_frame_data_cache = {}

global original_auto_key_state
original_auto_key_state = None

def handle_autokey_start():
    global original_auto_key_state
    # Solo guarda el estado original si aún no se ha guardado
    if original_auto_key_state is None:
        original_auto_key_state = cmds.autoKeyframe(query=True, state=True)
        cmds.autoKeyframe(state=False)


def handle_autokey_end():
    global original_auto_key_state
    # Solo restaura el estado si se ha guardado previamente
    if original_auto_key_state is not None:
        cmds.autoKeyframe(state=original_auto_key_state)
        original_auto_key_state = None  # Restablecer para la próxima operación





def blend_pull_and_push(value, objs=None, selection=True):
    global original_values, original_keyframe_values, is_dragging

    selected_channels = get_selected_channels()
    
    if not objs and not selection:
        raise ValueError("No objects given to blend_pull_and_push")

    if not objs:
        objs = cmds.ls(selection=True)

    if not is_dragging:
        cmds.undoInfo(openChunk=True)
        is_dragging = True

    selected_keyframes = get_graph_editor_selected_keyframes()

    # Define los factores de cambio
    rotation_factor = 2.0  # Ajusta este factor según tus necesidades para los atributos de rotación
    translation_factor = 0.1  # Ajusta este factor según tus necesidades para los atributos de translación
    other_factor = 0.2  # Ajusta este factor según tus necesidades para otros atributos

    for obj in objs:
        if not cmds.objExists(obj):
            continue

        attrs = selected_channels if selected_channels else cmds.listAttr(obj, keyable=True)

        if attrs is None:
            continue

        for attr in attrs:
            if not cmds.attributeQuery(attr, node=obj, exists=True):
                continue

            attrFull = f'{obj}.{attr}'

            if cmds.getAttr(attrFull, lock=True) or not cmds.getAttr(attrFull, keyable=True):
                # Si el atributo está bloqueado o no es keyable, continuar con el siguiente
                continue

            if attrFull not in original_values:
                # Guardar el valor original solo si es numérico
                original_attr_value = cmds.getAttr(attrFull)
                if isinstance(original_attr_value, (float, int)):
                    original_values[attrFull] = original_attr_value
                else:
                    # Si no es numérico, imprimir una advertencia y continuar con el siguiente atributo
                    print(f"Warning: Non-numeric attribute value detected for {attrFull}: {original_attr_value}")
                    continue

            if selected_keyframes:
                for curve, frame in selected_keyframes:
                    if curve.startswith(obj) and curve.endswith(attr):
                        key_identifier = f"{curve}_{frame}"  # Crea un identificador único para el keyframe
                        if key_identifier not in original_keyframe_values:
                            original_keyframe_values[key_identifier] = cmds.keyframe(curve, time=(frame,), q=True, valueChange=True)[0]

                        original_value = original_keyframe_values[key_identifier]

                        if attr in ['rx', 'ry', 'rz']:
                            # Aplicar un factor de cambio para los atributos de rotación
                            newValue = original_value + value * rotation_factor
                        elif attr in ['tx', 'ty', 'tz']:
                            # Aplicar un factor de cambio para los atributos de translación
                            newValue = original_value + value * translation_factor
                        else:
                            # Aplicar un factor de cambio para otros atributos
                            newValue = original_value + value * other_factor

                        cmds.keyframe(curve, time=(frame,), valueChange=newValue)
            else:
                currentValue = original_values.get(attrFull)
                if currentValue is not None:
                    if attr in ['rx', 'ry', 'rz']:
                        # Aplicar un factor de cambio para los atributos de rotación
                        newValue = currentValue + value * rotation_factor
                    elif attr in ['tx', 'ty', 'tz']:
                        # Aplicar un factor de cambio para los atributos de translación
                        newValue = currentValue + value * translation_factor
                    else:
                        # Aplicar un factor de cambio para otros atributos
                        newValue = currentValue + value * other_factor

                    # Limitar el valor entre un min y un max si existe
                    minValue, maxValue = None, None
                    if cmds.attributeQuery(attr, node=obj, minExists=True):
                        minValue = cmds.attributeQuery(attr, node=obj, min=True)[0]
                    if cmds.attributeQuery(attr, node=obj, maxExists=True):
                        maxValue = cmds.attributeQuery(attr, node=obj, max=True)[0]

                    if minValue is not None and newValue < minValue:
                        continue

                    if maxValue is not None and newValue > maxValue:
                        continue

                    cmds.setAttr(attrFull, newValue)




# Blend normal .................................................................................

is_cached = False
frame_data_cache = {}
def cache_keyframe_data(objs):
    keyframe_data = {}
    currentTime = cmds.currentTime(query=True)
    for obj in objs:
        attrs = cmds.listAttr(obj, keyable=True) or []
        for attr in attrs:
            attrFull = f'{obj}.{attr}'
            if cmds.objExists(attrFull):
                keyframes = cmds.keyframe(attrFull, query=True) or []
                original_value = cmds.getAttr(attrFull)
                previousKeyframes = [frame for frame in keyframes if frame < currentTime]
                laterKeyframes = [frame for frame in keyframes if frame > currentTime]

                previousFrame = max(previousKeyframes) if previousKeyframes else None
                nextFrame = min(laterKeyframes) if laterKeyframes else None
                previousValue = cmds.getAttr(attrFull, time=previousFrame) if previousFrame is not None else None
                nextValue = cmds.getAttr(attrFull, time=nextFrame) if nextFrame is not None else None

                minValue, maxValue = None, None
                if cmds.attributeQuery(attr, node=obj, minExists=True):
                    minValue = cmds.attributeQuery(attr, node=obj, min=True)[0]
                if cmds.attributeQuery(attr, node=obj, maxExists=True):
                    maxValue = cmds.attributeQuery(attr, node=obj, max=True)[0]

                # Obtener el tipo de tangente para el keyframe anterior
                prevTanType = None
                if previousKeyframes:
                    prevTanType = cmds.keyTangent(attrFull, query=True, time=(previousFrame,), outTangentType=True)[0]

                keyframe_data[attrFull] = {
                    "original_value": original_value,
                    "previousValue": previousValue,
                    "nextValue": nextValue,
                    "minValue": minValue,
                    "maxValue": maxValue,
                    "prevTanType": prevTanType  # Añadir tipo de tangente
                }
    return keyframe_data






# Esta es la funcion para el modo Blend normal

def blend_to_key(percentage, objs=None, selection=True):

    global is_dragging, frame_data_cache, is_cached, last_autokey_time, autokey_interval


    if not is_dragging:
        cmds.undoInfo(openChunk=True)
        is_dragging = True

    if objs is None and selection:
        objs = cmds.ls(selection=True)

    if not objs:
        if is_dragging:
            cmds.undoInfo(closeChunk=True)
            is_dragging = False
        return

    if not is_cached:

        frame_data_cache = cache_keyframe_data(objs)
        is_cached = True

    currentTime = cmds.currentTime(query=True)  

    for obj in objs:
        # Sólo atributos escalares keyables (evita double3 compuestos como rotate/translate)
        attrs = cmds.listAttr(obj, keyable=True, scalar=True) or []

        for attr in attrs:
            attrFull = f"{obj}.{attr}"

            # salta si no existe en la caché
            if attrFull not in frame_data_cache:
                continue

            # salta si está bloqueado o no es seteable
            if cmds.getAttr(attrFull, lock=True) or not cmds.getAttr(attrFull, settable=True):
                continue

            # salta tipos no numéricos
            a_type = cmds.getAttr(attrFull, type=True)
            if a_type in ("enum", "string", "message"):
                continue

            cachedData = frame_data_cache[attrFull]

            # nombres tal cual en tu cache: "original_value", "previousValue", "nextValue"
            orig = cachedData.get("original_value")
            nxt  = cachedData.get("nextValue")
            prev = cachedData.get("previousValue")

            # si por cualquier motivo llega lista/tupla, pasa
            if any(isinstance(v, (list, tuple)) for v in (orig, nxt, prev) if v is not None):
                continue

            # también salta si orig no es número
            if not isinstance(orig, (int, float)):
                continue

            if nxt is not None and isinstance(nxt, (int, float)) and percentage > 0:
                difference = nxt - orig
            elif prev is not None and isinstance(prev, (int, float)):
                difference = orig - prev
            else:
                continue

            weightedDifference = (difference * abs(percentage)) / 50.0
            currentValue = orig + weightedDifference if percentage > 0 else orig - weightedDifference

            try:
                cmds.setAttr(attrFull, float(currentValue))
            except Exception:
                # por si un attr acepta sólo enteros o tiene límites
                try:
                    cmds.setAttr(attrFull, int(round(currentValue)))
                except Exception:
                    continue





# blend to frame ......................................................................................


def cache_blend_frame_data(objs, left_frame, right_frame):
    frame_data_cache = {}
    currentTime = cmds.currentTime(query=True)
    for obj in objs:
        attrs = cmds.listAttr(obj, keyable=True, scalar=True) or []  # Solo atributos escalares (numéricos)
        for attr in attrs:
            attrFull = f'{obj}.{attr}'
            if cmds.objExists(attrFull):
                leftValue = cmds.getAttr(attrFull, time=left_frame) if left_frame is not None else None
                rightValue = cmds.getAttr(attrFull, time=right_frame) if right_frame is not None else None

                # Obtener el tipo de tangente para el keyframe anterior
                keyframes = cmds.keyframe(attrFull, query=True) or []
                previousKeyframes = [frame for frame in keyframes if frame < currentTime]
                prevTanType = None
                if previousKeyframes:
                    previousFrame = max(previousKeyframes)
                    prevTanType = cmds.keyTangent(attrFull, query=True, time=(previousFrame,), outTangentType=True)[0]

                frame_data_cache[attrFull] = {
                    "leftValue": leftValue,
                    "rightValue": rightValue,
                    "original_value": cmds.getAttr(attrFull),
                    "needsCalculation": True,
                    "prevTanType": prevTanType  # Añadir tipo de tangente
                }
    return frame_data_cache








# Esta es la funcion para el modo Blend to Frame

def blend_to_frame(percentage, left_frame=None, right_frame=None, objs=None, selection=True):
    global is_dragging, frame_data_cache, is_cached

    if not objs and not selection:
        raise ValueError("No objects given to blend_to_frame")

    if not objs:
        objs = cmds.ls(selection=True)

    if not is_dragging:
        cmds.undoInfo(openChunk=True)
        is_dragging = True

    if not is_cached:
        frame_data_cache = cache_blend_frame_data(objs, left_frame, right_frame)
        is_cached = True

    for obj in objs:
        attrs = cmds.listAttr(obj, keyable=True, scalar=True) or []

        for attr in attrs:
            attrFull = f'{obj}.{attr}'
            if attrFull not in frame_data_cache:
                continue

            cachedData = frame_data_cache[attrFull]
            if not cachedData["needsCalculation"]:
                continue

            original_value = cachedData["original_value"]
            previousValue = cachedData["leftValue"]
            nextValue = cachedData["rightValue"]



            if nextValue is not None and percentage > 0:
                difference = nextValue - original_value
            elif previousValue is not None:
                difference = original_value - previousValue

            else:
                continue

            weightedDifference = (difference * abs(percentage)) / 50.0
            currentValue = original_value + weightedDifference if percentage > 0 else original_value - weightedDifference

            cmds.setAttr(attrFull, currentValue)








def blendSliderReset(slider):
    global original_keyframes, original_values, is_dragging, frame_data_cache, original_keyframe_values, is_cached

    # Comprobar si frame_data_cache tiene elementos
    if frame_data_cache:
        currentTime = cmds.currentTime(query=True)
        for attrFull, cacheData in frame_data_cache.items():
            if 'prevTanType' in cacheData:
                prevTanType = cacheData['prevTanType']
                # Ajustar 'step' a 'stepnext'
                if prevTanType == 'step':
                    prevTanType = 'stepnext'
                # Crear un nuevo keyframe
                cmds.setKeyframe(attrFull, time=currentTime)
                # Aplicar la tangente al keyframe
                cmds.keyTangent(attrFull, edit=True, time=(currentTime,), inTangentType=prevTanType, outTangentType=prevTanType)

        frame_data_cache = {}
        is_cached = False

    # Resetear las variables globales
    original_keyframes = {}
    original_values = {}
    original_keyframe_values = {}

    if is_dragging:
        cmds.undoInfo(closeChunk=True)
        is_dragging = False

    cmds.floatSlider(slider, edit=True, value=0)




# _____________________________________________________ Tween Machine _______________________________________________________________#







def prepare_tween_data(objs=None, attrs=None):
    global tween_frame_data_cache
    tween_frame_data_cache = {}
    currentTime = cmds.currentTime(query=True)


    for obj in objs or cmds.ls(selection=True):
        if not cmds.objExists(obj):
            continue

        current_attrs = attrs if attrs else cmds.listAttr(obj, keyable=True)
        if current_attrs is None:
            continue

        for attr in current_attrs:
            attrFull = '%s.%s' % (obj, attr)
            keyframes = cmds.keyframe(attrFull, query=True) or []
            
            if not keyframes:
                continue

            previousKeyframes = [frame for frame in keyframes if frame < currentTime]
            laterKeyframes = [frame for frame in keyframes if frame > currentTime]
            
            if not previousKeyframes or not laterKeyframes:
                tween_frame_data_cache[attrFull] = {"needsCalculation": False}
                continue

            previousFrame = max(previousKeyframes)
            nextFrame = min(laterKeyframes)

            previousValue = cmds.getAttr(attrFull, time=previousFrame)
            nextValue = cmds.getAttr(attrFull, time=nextFrame)
            
            tween_frame_data_cache[attrFull] = {
                "previousValue": previousValue,
                "nextValue": nextValue,
                "needsCalculation": previousValue != nextValue
            }

            previousKeyframes = [frame for frame in keyframes if frame < currentTime]
            if previousKeyframes:
                previousFrame = max(previousKeyframes)
                prevTanType = cmds.keyTangent(attrFull, query=True, time=(previousFrame,), outTangentType=True)[0]

                tween_frame_data_cache[attrFull]["prevTanType"] = prevTanType

    return tween_frame_data_cache




def tween(percentage):
    global is_dragging, tween_frame_data_cache

    if not tween_frame_data_cache:
        tween_frame_data_cache = prepare_tween_data()

    if not is_dragging:
        cmds.undoInfo(openChunk=True)
        is_dragging = True

    currentTime = cmds.currentTime(query=True)
    adjustments = []

    for attrFull, cache in tween_frame_data_cache.items():
        if not cache.get("needsCalculation", False):
            continue

        # salta attrs inexistentes/bloqueados/no seteables/no numéricos
        try:
            if not cmds.objExists(attrFull):
                continue
            if cmds.getAttr(attrFull, lock=True) or not cmds.getAttr(attrFull, settable=True):
                continue
            a_type = cmds.getAttr(attrFull, type=True)
            if a_type in ("enum", "string", "message"):
                continue
        except Exception:
            continue

        previousValue = cache.get("previousValue")
        nextValue = cache.get("nextValue")

        # sin valores válidos, nada que hacer
        if previousValue is None or nextValue is None:
            continue

        # evita restar listas/tuplas (double3, matrices, etc.)
        if isinstance(previousValue, (list, tuple)) or isinstance(nextValue, (list, tuple)):
            continue

        # exige número escalar
        if not isinstance(previousValue, (int, float)) or not isinstance(nextValue, (int, float)):
            continue

        difference = nextValue - previousValue
        weightedDifference = (difference * percentage) / 100.0
        currentValue = previousValue + weightedDifference

        adjustments.append((attrFull, currentValue))


    apply_tween_adjustments(adjustments, currentTime, tween_frame_data_cache)
    

def apply_tween_adjustments(adjustments, currentTime, tween_frame_data_cache):
    for attrFull, currentValue in adjustments:
        obj, attr = attrFull.split('.')
        
        if cmds.attributeQuery(attr, node=obj, minExists=True):
            minLimit = cmds.attributeQuery(attr, node=obj, minimum=True)[0]
            currentValue = max(currentValue, minLimit)

        if cmds.attributeQuery(attr, node=obj, maxExists=True):
            maxLimit = cmds.attributeQuery(attr, node=obj, maximum=True)[0]
            currentValue = min(currentValue, maxLimit)
                
        cmds.setAttr(attrFull, currentValue)



def tweenSliderReset(slider):
    global original_keyframes, original_values, is_dragging, tween_frame_data_cache

    currentTime = cmds.currentTime(query=True)

    # Comprobar si tween_frame_data_cache tiene elementos
    if tween_frame_data_cache:
        for attrFull, cacheData in tween_frame_data_cache.items():
            # Crear un nuevo keyframe
            cmds.setKeyframe(attrFull, time=currentTime)

            if 'prevTanType' in cacheData:
                prevTanType = cacheData['prevTanType']
                # Ajustar 'step' a 'stepnext'
                if prevTanType == 'step':
                    prevTanType = 'step'
                # Aplicar la tangente al keyframe
                cmds.keyTangent(attrFull, edit=True, time=(currentTime,), inTangentType=prevTanType, outTangentType=prevTanType)

            if 'currentValue' in cacheData:
                currentValue = cacheData['currentValue']
                cmds.setAttr(attrFull, currentValue)




    # Resetear las variables globales
    original_keyframes = {}
    original_values = {}
    tween_frame_data_cache = {}

    if is_dragging:
        cmds.undoInfo(closeChunk=True)
        is_dragging = False





# _____________________________________________________ Key Tools  Customgraph _______________________________________________________________#


def deleteStaticCurves():
    # Obtener los objetos seleccionados con sus nombres completos una sola vez
    selected_objects = cmds.ls(selection=True, long=True)

    # También incluir las formas de los objetos seleccionados
    selected_shapes = []
    for obj in selected_objects:
        shapes = cmds.listRelatives(obj, shapes=True, fullPath=True)
        if shapes:
            selected_shapes.extend(shapes)
    
    # Fusionar las listas de objetos y formas
    all_selected = list(set(selected_objects + selected_shapes))

    # Recopilar todas las curvas de animación para todos los objetos seleccionados una sola vez
    curves_to_delete = []
    for obj in all_selected:
        anim_curves = cmds.listConnections(obj, type="animCurve", connections=False, plugs=False) or []
        for curve in anim_curves:
            keyframes = cmds.keyframe(curve, query=True, timeChange=True) or []
            values = cmds.keyframe(curve, query=True, valueChange=True) or []
            if len(set(values)) == 1:  # Usar un conjunto para buscar valores únicos
                curves_to_delete.append(curve)

    # Eliminar todas las curvas recopiladas en un solo comando
    if curves_to_delete:
        cmds.delete(curves_to_delete)



def snapKeyframes():
# Obtén la selección actual
    selected_objects = cmds.ls(sl=True)

    for obj in selected_objects:

        if not cmds.attributeQuery('translateX', node=obj, exists=True):
            print(f"Objet {obj} is not animatable")
            continue

        # Obtén las curvas de animación para el objeto
        anim_curves = cmds.listConnections(obj, type="animCurve")

        # Si el objeto no tiene curvas de animación, continúa con el siguiente objeto
        if not anim_curves:
            continue

        for curve in anim_curves:
            # Obtén todos los keyframes para la curva
            keyframes = cmds.keyframe(curve, query=True)

            # Si no hay keyframes, continúa con la siguiente curva
            if not keyframes:
                continue

            for key in keyframes:
                # Si el keyframe no está en un fotograma completo, redondea al más cercano
                if not key.is_integer():
                    # Almacena el valor del keyframe antes de eliminarlo
                    value = cmds.keyframe(curve, time=(key, key), query=True, valueChange=True)

                    # Almacena las tangentes del keyframe antes de eliminarlo
                    in_tangent = cmds.keyTangent(curve, time=(key,), query=True, inTangentType=True)
                    out_tangent = cmds.keyTangent(curve, time=(key,), query=True, outTangentType=True)

                    # Borra el keyframe
                    cmds.cutKey(curve, time=(key, key))

                    # Redondea el fotograma
                    rounded_key = round(key)

                    # Establece el valor del keyframe borrado al nuevo fotograma redondeado
                    cmds.setKeyframe(curve, time=rounded_key, value=value[0])

                    # Establece las tangentes del keyframe redondeado
                    cmds.keyTangent(curve, time=(rounded_key,), edit=True, inTangentType=in_tangent[0])
                    cmds.keyTangent(curve, time=(rounded_key,), edit=True, outTangentType=out_tangent[0])



def shareKeys():
    # Obtener los keyframes de todas las curvas
    all_times = cmds.keyframe(query=True, timeChange=True)

    # Obtener las curvas seleccionadas
    selected_curves = cmds.keyframe(selected=True, query=True, name=True)

    # Verificar si hay al menos una curva seleccionada
    if selected_curves:
        for curve in selected_curves:
            # Obtener el valor del primer y último keyframe de la curva seleccionada
            first_frame_value = cmds.keyframe(curve, query=True, time=(all_times[0], all_times[0]), valueChange=True)
            last_frame_value = cmds.keyframe(curve, query=True, time=(all_times[-1], all_times[-1]), valueChange=True)

            # Si la curva tiene keyframes, establecer todos los keyframes con el valor del primer y último frame
            if first_frame_value and last_frame_value:
                first_frame_value = first_frame_value[0]
                last_frame_value = last_frame_value[0]

                # Crear todos los keyframes con el mismo valor del primer y último frame
                for time in all_times:
                    if time == all_times[0] or time == all_times[-1]:
                        cmds.setKeyframe(curve, time=time, value=first_frame_value)
                    else:
                        # Obtener la lista de los keyframes actuales de la curva
                        curve_times = cmds.keyframe(curve, query=True, timeChange=True)
                        if time in curve_times:
                            # Si el frame actual ya tiene un keyframe, usar su valor
                            frame_value = cmds.keyframe(curve, query=True, time=(time, time), valueChange=True)[0]
                        else:
                            # Si no, usar el valor del primer keyframe
                            frame_value = first_frame_value

                        cmds.setKeyframe(curve, time=time, value=frame_value)



def match_keys():
    # Obtener las curvas seleccionadas
    selected_curves = cmds.keyframe(selected=True, query=True, name=True)

    # Verificar si hay al menos dos curvas seleccionadas
    if not selected_curves:
        print("Select at least two animation curves")

    else:

        # Obtener los keyframes de la primera curva seleccionada
        first_curve_times = cmds.keyframe(selected_curves[-1], query=True, timeChange=True)
        first_curve_values = cmds.keyframe(selected_curves[-1], query=True, valueChange=True)

        # Para cada curva restante, ajustar los keyframes para que coincidan con la primera curva
        for curve in selected_curves[:-1]:
            # Obtener los keyframes actuales de la curva
            curve_times = cmds.keyframe(curve, query=True, timeChange=True)
            
            # Borrar keyframes que no están en la primera curva
            extra_frames = set(curve_times) - set(first_curve_times)
            for frame in extra_frames:
                cmds.cutKey(curve, time=(frame, frame))

            # Agregar o ajustar keyframes para que coincidan con la primera curva
            for time, value in zip(first_curve_times, first_curve_values):
                cmds.setKeyframe(curve, time=time, value=value)


def flipCurves():
    selectedCurves = cmds.keyframe(n=1, sl=1, q=1)
    
    if selectedCurves is not None:
        for curve in selectedCurves:
            # Obtener todos los valores de keyframes para la curva
            values = cmds.keyframe(curve, query=True, valueChange=True)

            # Calcular el punto medio de los keyframes
            pivot = (min(values) + max(values)) / 2

            # Realizar el flip usando el punto medio como pivote
            cmds.scaleKey(curve, valueScale=-1, valuePivot=pivot)



def flipKeyGroup():

    # Obtener las curvas con keyframes seleccionados
    selectedCurves = cmds.keyframe(q=True, name=True, sl=True)
    
    if selectedCurves is not None:
        for curve in selectedCurves:
            # Obtener los tiempos de los keyframes seleccionados para la curva
            selected_times = cmds.keyframe(curve, query=True, timeChange=True, sl=True)
            
            # Obtener los valores de los keyframes seleccionados en base a los tiempos
            selected_values = [cmds.keyframe(curve, query=True, time=(t, t), valueChange=True)[0] for t in selected_times]

            # Calcular el punto medio de los keyframes seleccionados
            pivot = (min(selected_values) + max(selected_values)) / 2

            # Realizar el flip de los keyframes seleccionados usando el punto medio como pivote
            for t in selected_times:
                value = cmds.keyframe(curve, query=True, time=(t, t), valueChange=True)[0]
                flipped_value = pivot + (pivot - value)  # Calcula el valor opuesto en relación al pivot
                cmds.keyframe(curve, edit=True, time=(t, t), valueChange=flipped_value)
    else:
        print("Select at least one keyframe in Graph Editor")




def flipFromKeyframe():
    selectedCurves=cmds.keyframe(n=1, sl=1, q=1)

    if selectedCurves is not None:
        for piv in selectedCurves:
            pivot = cmds.keyframe(query=True, valueChange=True)[0]
        
        for s in selectedCurves:
            cmds.scaleKey(s, valueScale=-1, valuePivot=pivot, scaleSpecifiedKeys=1)
    else:
        cmds.warning("No keys selected")






# ------------------------------ OVERLAP


def mod_overlap_animation(*args):
    # Get the current state of the modifiers
    mods = mel.eval('getModifiers')
    shift_pressed = bool(mods % 2)  # Check if Shift is pressed

    if shift_pressed:
        overlap_backward()
    else:
        overlap_forward()




def get_selected_objects():
    """
    Devuelve una lista de objetos seleccionados en el orden en que se seleccionaron.
    """
    return cmds.ls(orderedSelection=True, long=True)


def overlap_forward(*args):
    frames_to_move = 1

    # Obtén el orden de los objetos seleccionados
    selected_objects_order = get_selected_objects()
    # Intenta obtener las curvas seleccionadas del Graph Editor
    selected_anim_curves = getSelectedCurves()

    # Si no hay curvas seleccionadas en el Graph Editor, obtén las curvas de los canales seleccionados
    if not selected_anim_curves:
        selected_channels = get_selected_channels()
        
        # Si no hay canales seleccionados, muestra un mensaje al usuario y termina la ejecución
        if not selected_channels:
            print("Select animation curves or channels in the Channel Box")
            return
        
        selected_anim_curves = [cmds.listConnections(f'{obj}.{channel}', type='animCurve')[0] for obj in selected_objects_order for channel in selected_channels if cmds.listConnections(f'{obj}.{channel}', type='animCurve')]

    # Elimina los duplicados de la lista manteniendo el orden original
    seen = set()
    selected_anim_curves = [x for x in selected_anim_curves if x not in seen and not seen.add(x)]

    # Si hay curvas seleccionadas...
    if selected_anim_curves:
        for i, curve in enumerate(selected_anim_curves):
            cmds.keyframe(curve, edit=True, includeUpperBound=True, relative=True, option="over", timeChange=i*frames_to_move)


def overlap_backward(*args):
    frames_to_move = -1

    # Obtén el orden de los objetos seleccionados
    selected_objects_order = get_selected_objects()

    # Intenta obtener las curvas seleccionadas del Graph Editor
    selected_anim_curves = getSelectedCurves()

    # Si no hay curvas seleccionadas en el Graph Editor, obtén las curvas de los canales seleccionados
    if not selected_anim_curves:
        selected_channels = get_selected_channels()
        
        # Si no hay canales seleccionados, muestra un mensaje al usuario y termina la ejecución
        if not selected_channels:
            print("Select animation curves or channels in the Channel Box")
            return
        
        selected_anim_curves = [cmds.listConnections(f'{obj}.{channel}', type='animCurve')[0] for obj in selected_objects_order for channel in selected_channels if cmds.listConnections(f'{obj}.{channel}', type='animCurve')]

    # Elimina los duplicados de la lista manteniendo el orden original
    seen = set()
    selected_anim_curves = [x for x in selected_anim_curves if x not in seen and not seen.add(x)]

    # Si hay curvas seleccionadas...
    if selected_anim_curves:
        for i, curve in enumerate(selected_anim_curves):
            cmds.keyframe(curve, edit=True, includeUpperBound=True, relative=True, option="over", timeChange=i*frames_to_move)



# __________________________________________________ Iso / Mute / Lock ____________________________________________________________#


def isolateCurve():
    # Obtén las curvas seleccionadas en el Graph Editor
    selected_objects = cmds.selectionConnection('graphEditor1FromOutliner', q=1, object=1)

    if not selected_objects:
        cmds.warning("There are not selected curves in Graph Editor")
    else:
        for s in selected_objects:
            mel.eval("isolateAnimCurve true graphEditor1FromOutliner graphEditor1GraphEd;")


def toggleMute():
    # Obtener las curvas seleccionadas en el Graph Editor
    selected_curves = cmds.selectionConnection('graphEditor1FromOutliner', q=1, object=1)
    
    if selected_curves:
        for curve in selected_curves:
            # Reemplazar guiones bajos por puntos en el nombre del canal
            #curve = curve.replace("_", "")
            
            # Consultar si el canal está en mute
            is_muted = cmds.mute(curve, q=True)
            
            if is_muted:
                # Desactivar el mute del canal
                cmds.mute(curve, disable=True)
            else:
                # Activar el mute del canal
                cmds.mute(curve)



def toggleLock():
    # Obtén las curvas seleccionadas en el Graph Editor
    selected_objects = cmds.selectionConnection('graphEditor1FromOutliner', q=1, object=1)

    # Si no hay objetos seleccionados, lanza un error
    if not selected_objects:
        cmds.warning("There are not selected curves in Graph Editor")
        return

    # Por cada objeto seleccionado
    for obj in selected_objects:
        # Obtén las curvas de animación de este objeto
        anim_curves = cmds.listConnections(obj, type='animCurve')

        # Si no hay curvas de animación, lanza un error y continua con el siguiente objeto
        if not anim_curves:
            cmds.warning(f"No animation curves found for {obj}")
            continue

        # Por cada curva de animación
        for curve in anim_curves:
            # Obtén el estado actual de bloqueo (lock) de la curva
            is_locked = cmds.getAttr(curve + '.ktv', lock=True)

            # Si la curva está bloqueada (locked), desbloquéala (unlock).
            # Si no está bloqueada (unlocked), blóquela (lock).
            cmds.setAttr(curve + '.ktv', lock= not is_locked)




# _____________________________________________________ Resets _______________________________________________________________#


def reset_objects_mods(*args):
    # Get the current state of the modifiers
    mods = mel.eval('getModifiers')
    shift_pressed = bool(mods % 2)  # Check if Shift is pressed
    ctrl_pressed = bool(mods & 4)  # Check if Ctrl is pressed

    if shift_pressed:
        reset_object_values(reset_translations=True)
    elif ctrl_pressed:
        reset_object_values(reset_rotations=True)
    else:
        reset_object_values()


def save_default_values(*args):
    # Obtener objetos seleccionados
    objetos_seleccionados = cmds.ls(selection=True, long=True)

    json_file_path = general.get_set_default_data_file()

    # Asegurar que la carpeta donde se guardará el archivo exista
    os.makedirs(os.path.dirname(json_file_path), exist_ok=True)

    # Leer datos existentes del archivo JSON, si existe
    if os.path.exists(json_file_path):
        with open(json_file_path, 'r') as file:
            data = json.load(file)
    else:
        data = {}

    for obj in objetos_seleccionados:
        # Extraer el namespace y el nombre corto del objeto
        partes = obj.split(':')
        namespace = partes[0] if len(partes) > 1 else 'default'
        nombre_corto = partes[-1]

        # Agregar namespace al diccionario si no existe
        if namespace not in data:
            data[namespace] = {}

        # Obtener atributos claveables que no estén ocultos o bloqueados
        atributos = cmds.listAttr(obj, keyable=True, unlocked=True, visible=True) or []

        # Actualizar o agregar valores de los atributos, excluyendo el atributo "tag"
        for attr in atributos:
            if attr == "tag":
                continue  # Ignorar el atributo "tag"
            atributo_completo = f'{nombre_corto}.{attr}'
            valor = cmds.getAttr(f'{obj}.{attr}')
            data[namespace][atributo_completo] = valor

    # Guardar los datos actualizados en un archivo JSON
    with open(json_file_path, 'w') as file:
        json.dump(data, file, indent=4)

    cmds.warning(f'Data saved')



def restore_default_data(*args):

    json_file_path = general.get_set_default_data_file()

    # Verificar si el archivo existe y vaciar su contenido
    if os.path.exists(json_file_path):
        with open(json_file_path, 'w') as file:
            json.dump({}, file)  # Escribe un diccionario vacío en el archivo

        cmds.warning(f"All default values restored")
    else:
        print("There is not a JSON file to restore")




def remove_default_values_for_selected_object(*args):

    json_file_path = general.get_set_default_data_file()

    # Leer datos existentes del archivo JSON, si existe
    if os.path.exists(json_file_path):
        with open(json_file_path, 'r') as file:
            data = json.load(file)
    else:
        print("There is not a JSON file")
        return

    # Obtener objetos seleccionados
    objetos_seleccionados = cmds.ls(selection=True, long=True)

    for obj in objetos_seleccionados:
        # Extraer el namespace y el nombre corto del objeto
        partes = obj.split(':')
        namespace = partes[0] if len(partes) > 1 else 'default'
        nombre_corto = partes[-1]

        # Eliminar la información del objeto del JSON
        if namespace in data:
            # Crear una lista de claves a eliminar para evitar modificar el diccionario durante la iteración
            keys_to_remove = [key for key in data[namespace] if key.startswith(nombre_corto + "")]

            for key in keys_to_remove:
                del data[namespace][key]

            # Si el namespace queda vacío, eliminarlo también
            if not data[namespace]:
                del data[namespace]

    # Guardar los datos actualizados en un archivo JSON
    with open(json_file_path, 'w') as file:
        json.dump(data, file, indent=4)

    print(f"Data removed from JSON {json_file_path}")





def reset_object_values(reset_translations=False, reset_rotations=False):

    cmds.undoInfo(openChunk=True)

    try:
        json_file_path = general.get_set_default_data_file()

        # Leer datos del archivo JSON si existe
        if os.path.exists(json_file_path):
            with open(json_file_path, 'r') as file:
                data = json.load(file)
        else:
            data = {}

        selected_objects = cmds.ls(selection=True, long=True)
        selected_channels = get_selected_channels()

        for obj in selected_objects:
            # Extraer el namespace y el nombre corto del objeto
            partes = obj.split(':')
            namespace = partes[0] if len(partes) > 1 else 'default'
            nombre_corto = partes[-1]

            attrs = selected_channels if selected_channels else cmds.listAttr(obj, keyable=True)

            if not attrs:
                continue

            for attr in attrs:
                attr_full = f'{nombre_corto}.{attr}'

                # Comprobar si hay datos guardados para el atributo
                if namespace in data and attr_full in data[namespace]:
                    # Restaurar valores desde el JSON
                    try:
                        cmds.setAttr(obj + "." + attr, data[namespace][attr_full])
                    except Exception as e:
                        print(f"Could not process the attribute {attr} on {obj}: {str(e)}")
                else:
                    # Restablecer a los valores por defecto
                    if reset_translations and not attr.startswith('translate'):
                        continue
                    if reset_rotations and not attr.startswith('rotate'):
                        continue
                    
                    try:
                        is_locked = cmds.getAttr(obj + "." + attr, lock=True)
                        if is_locked:
                            continue

                        connections = cmds.listConnections(obj + "." + attr, source=True, destination=False, plugs=True)
                        if connections:
                            node_type = cmds.nodeType(connections[0].split('.')[0])
                            if node_type not in ["animCurveTL", "animCurveTA", "animCurveTT", "animCurveTU"]:
                                cmds.disconnectAttr(connections[0], obj + "." + attr)

                        default_value = cmds.attributeQuery(attr, node=obj, listDefault=True)
                        if default_value:
                            cmds.setAttr(obj + "." + attr, default_value[0])
                    except Exception as e:
                        print(f"Could not process the attribute {attr} on {obj}: {str(e)}")
                        continue

    except Exception as e:
        cmds.warning("Error during reset: {}".format(str(e)))
    finally:
        cmds.undoInfo(closeChunk=True)



def get_default_value(node):
    type = cmds.nodeType(node)
    
    if "animCurve" in type: 
        target = cmds.listConnections(node + ".output", plugs=True, destination=False, source=True)
        if target:
            object, attr = target[0].split("")
        else:
            object, attr = None, None
    else:
        object, attr = node.split("")
    
    if not object or not attr:
        return None
    
    if cmds.attributeQuery(attr, node=object, exists=True):
        default_value = cmds.attributeQuery(attr, node=object, listDefault=True)[0]
        return default_value
    
    return None


def get_default_value_main():
    selected_curves = cmds.selectionConnection('graphEditor1FromOutliner', query=True, object=True)

    if selected_curves:
        for curve in selected_curves:
            selected_keyframes = cmds.keyframe(curve, query=True, selected=True, timeChange=True)
            if selected_keyframes:
                for keyframe in selected_keyframes:
                    default_value = get_default_value(curve)
                    if default_value is not None:
                        cmds.keyframe(curve, edit=True, valueChange=default_value, time=(keyframe, keyframe))



# _____________________________________________________ select object from selected curve _______________________________________________________________#


def get_namespace_from_selection(*args):
    # Obtener el namespace del objeto seleccionado (si existe)
    selected_objects = cmds.ls(selection=True)
    if selected_objects:
        object_name = selected_objects[0]
        if ':' in object_name:
            return object_name.split(':')[0]
    return None


def select_objects_from_selected_curves(*args):
    # Obtener los nombres de las curvas seleccionadas en el Graph Editor
    selected_curves = cmds.keyframe(query=True, name=True, selected=True)
    if not selected_curves:
        return

    # Obtener el namespace del objeto seleccionado
    namespace = get_namespace_from_selection()

    # Obtener y seleccionar los objetos asociados a las curvas seleccionadas
    selected_objects = set()
    for curve_name in selected_curves:
        object_name = '_'.join(curve_name.split('_')[:-1])  # Eliminar el sufijo "_rotateY"
        
        # Agregar el namespace al nombre del objeto si existe
        if namespace:
            object_name_with_namespace = f"{namespace}:{object_name}"
            if cmds.objExists(object_name_with_namespace):
                object_name = object_name_with_namespace
        
        if cmds.objExists(object_name):
            selected_objects.add(object_name)
    
    if selected_objects:
        cmds.selectKey(selected_curves, add=True)  # Seleccionar las claves en el Graph Editor
        mel.eval('isolateAnimCurve true graphEditor1FromOutliner graphEditor1GraphEd;')
        cmds.select(list(selected_objects), replace=True)  # Seleccionar los objetos en la vista 3D




# _____________________________ Patrones Mirror ______________________________________


MIRROR_PATTERNS = [
    ('R_', 'L_'),
    ('L_', 'R_'),

    ('_R', '_L'),
    ('_L', '_R'),

    ('_R_', '_L_'),
    ('_L_', '_R_'),

    ('r_', 'l_'),
    ('l_', 'r_'),

    ('_r_', '_l_'),
    ('_l_', '_r_'),

    ('_rt_', '_lf_'),
    ('_lf_', '_rt_'),

    ('_rg_', '_lf_'),
    ('_lf_', '_rg_'),

    ('_lf', '_rg'),
    ('_rg', '_lf'),

    ('RF_', 'LF_'),
    ('LF_', 'RF_'),

    ('left_', 'right_'),
    ('right_', 'left_'),

    ('_left', '_right_'),
    ('_right', '_left'),

    ('_left_', '_right_'),
    ('_right_', '_left_')
]



# __________ Funcion para buscar control opuesto ___________________________________

def find_opposite_name(name):
    global MIRROR_PATTERNS
    # Divide el nombre en partes (namespace y nombre del control)
    namespace, _, control_name = name.rpartition(':')

    for pattern, opposite_pattern in MIRROR_PATTERNS:
        if pattern in control_name:
            new_control_name = control_name.replace(pattern, opposite_pattern, 1)
            possible_opposite_name = f'{namespace}:{new_control_name}' if namespace else new_control_name
            if cmds.objExists(possible_opposite_name):
                return possible_opposite_name

    return None


#___________________________ SELECT OPPOSITE _____________________________________



def selectOppositeHandler(*args):
    mods = mel.eval('getModifiers')
    shift_pressed = bool(mods % 2)  # Shift

    if shift_pressed:
        addSelectOpposite(args)
    else:
        selectOpposite(args)


def selectOpposite(*args):
    global MIRROR_PATTERNS
    
    selected_objects = cmds.ls(selection=True)
    opposite_controls = []

    for obj in selected_objects:
        opposite_obj = find_opposite_name(obj)
        if opposite_obj and cmds.objExists(opposite_obj):
            opposite_controls.append(opposite_obj)

    if opposite_controls:
        cmds.select(opposite_controls)


def addSelectOpposite(*args):
    global MIRROR_PATTERNS
    
    selected_objects = cmds.ls(selection=True)
    opposite_controls = []

    for obj in selected_objects:
        opposite_obj = find_opposite_name(obj)
        if opposite_obj and cmds.objExists(opposite_obj):
            opposite_controls.append(opposite_obj)

    if opposite_controls:
        cmds.select(opposite_controls, add=True)






#___________________________ Copy Opposite _____________________________________


def copyOpposite(*args):
    cmds.undoInfo(openChunk=True)

    try:
        mirror_exceptions_file_path = general.get_mirror_exceptions_file()
        ATTRIBUTES_TO_IGNORE = {"tag"}

        def load_exceptions(file_path):
            if os.path.exists(file_path):
                with open(file_path, 'r') as file:
                    return json.load(file)
            else:
                return {}

        exceptions = load_exceptions(mirror_exceptions_file_path)

        def apply_exception(control, attr, value):
            control_name = control.rsplit(":", 1)[-1]
            if control_name in exceptions and attr in exceptions[control_name]:
                exception_type = exceptions[control_name][attr]
                if exception_type == "invert":
                    return -value
            return value

        def replace_pattern_in_attribute(attr):
            for from_pattern, to_pattern in MIRROR_PATTERNS:
                if from_pattern in attr:
                    return attr.replace(from_pattern, to_pattern)
            return attr

        selected_objects = cmds.ls(selection=True)

        for obj in selected_objects:
            opposite_obj = find_opposite_name(obj)

            # Comprobamos si el objeto opuesto es válido y existe
            if opposite_obj and cmds.objExists(opposite_obj):
                keyable_attrs = cmds.listAttr(obj, keyable=True)

                for attr in keyable_attrs:
                    if attr in ATTRIBUTES_TO_IGNORE:
                        continue

                    opposite_attr = replace_pattern_in_attribute(attr)

                    if not cmds.getAttr(f'{opposite_obj}.{opposite_attr}', lock=True):
                        try:
                            current_value = cmds.getAttr(f'{obj}.{attr}')
                            current_value = apply_exception(obj, attr, current_value)
                            cmds.setAttr(f'{opposite_obj}.{opposite_attr}', current_value)
                        except Exception as e:
                            print("Error compiling attribute:, {}".format(str(e)))

    except Exception as e:
        cmds.warning("Error during copy: {}".format(str(e)))
    finally:
        cmds.undoInfo(closeChunk=True)





# ________________________________________________________________ MIRROR _______________________________________________________________________ #

def load_exceptions():
    mirror_exceptions_file_path = general.get_mirror_exceptions_file()
    if os.path.exists(mirror_exceptions_file_path):
        with open(mirror_exceptions_file_path, 'r') as file:
            return json.load(file)
    else:
        return {}



def mirror(*args):

    cmds.undoInfo(openChunk=True)

    try:
        global MIRROR_PATTERNS
        mirror_exceptions_file_path = general.get_mirror_exceptions_file()

        ATTRIBUTES_TO_IGNORE = {"tag"}

        # Cargar excepciones
        def load_exceptions(file_path):
            if os.path.exists(file_path):
                with open(file_path, 'r') as file:
                    return json.load(file)
            else:
                return {}

        exceptions = load_exceptions(mirror_exceptions_file_path)

        def find_pattern_in_name(name, patterns):
            for pattern in patterns:
                if pattern in name:
                    return True
            return False

        def is_attribute_modifiable(control, attr):
            return cmds.getAttr(f"{control}.{attr}", settable=True)


        def find_opposite_name(name):
            # Divide el nombre en partes (namespace y nombre del control)
            namespace, _, control_name = name.rpartition(':')

            for pattern, opposite_pattern in MIRROR_PATTERNS:
                # Revisa si el patrón está en el nombre del control
                if pattern in control_name:
                    # Realiza el reemplazo solo para la primera aparición del patrón
                    new_control_name = control_name.replace(pattern, opposite_pattern, 1)
                    possible_opposite_name = f'{namespace}:{new_control_name}' if namespace else new_control_name
                    #print(f"Intentando reemplazar {pattern} por {opposite_pattern} en {control_name}, resultado: {possible_opposite_name}")  # Impresión de depuración
                    if cmds.objExists(possible_opposite_name):
                        return possible_opposite_name

            return None



        def apply_exception(control, attr, value):
            # Obtén el nombre del control sin el namespace
            control_name = control.rsplit(":", 1)[-1]

            if control_name in exceptions and attr in exceptions[control_name]:
                exception_type = exceptions[control_name][attr]
                if exception_type == "invert":
                    return -value
                elif exception_type == "keep":
                    return value  # Mantener el mismo valor
            return value


        def swap_control_values(control1, control2):
            if not cmds.objExists(control1):
                return

            attrs_to_swap = cmds.listAttr(control1, keyable=True)
            if not attrs_to_swap:
                return

            for attr in attrs_to_swap:
                if attr in ATTRIBUTES_TO_IGNORE or not is_attribute_modifiable(control1, attr):
                    continue

                try:
                    value1 = cmds.getAttr(f"{control1}.{attr}")

                    # Aplicar excepciones si es necesario
                    value1 = apply_exception(control1, attr, value1)

                    if control2 and cmds.objExists(control2) and is_attribute_modifiable(control2, attr):
                        value2 = cmds.getAttr(f"{control2}.{attr}")
                        value2 = apply_exception(control2, attr, value2)

                        cmds.setAttr(f"{control2}.{attr}", value1)
                        cmds.setAttr(f"{control1}.{attr}", value2)
                    else:  # Solo un control (central o único)
                        # Verificar si hay excepción para este control y atributo
                        control_name = control1.rsplit(":", 1)[-1]
                        if control_name in exceptions and attr in exceptions[control_name]:
                            exception_type = exceptions[control_name][attr]
                            if exception_type == "invert":

                                cmds.setAttr(f"{control1}.{attr}", value1 * 1)

                        else:
                            # Invertir solo los atributos específicos si no hay excepciones
                            if attr in ["translateX", "rotateZ", "rotateY"]:
                                cmds.setAttr(f"{control1}.{attr}", value1 * -1)


                except Exception as e:
                    cmds.warning(f"Could not process the attribute {attr} on {control1}: {str(e)}")



        def mirror_controls():
            selected_controls = cmds.ls(selection=True)
            
            if not selected_controls:
                print("Select a control")
                return

            processed_controls = set()

            for control in selected_controls:
                if control in processed_controls:
                    continue

                opposite_name = find_opposite_name(control)
                if opposite_name:
                    # Si el control opuesto no está seleccionado, aún así procede con el espejado
                    swap_control_values(control, opposite_name if cmds.objExists(opposite_name) else None)
                    processed_controls.add(control)
                    if opposite_name:
                        processed_controls.add(opposite_name)
                else:
                    # Tratar como control central o único si no se encuentra un opuesto
                    swap_control_values(control, None)
                    processed_controls.add(control)

        mirror_controls()
    except Exception as e:
        cmds.warning("Error during mirroring: {}".format(str(e)))
    finally:
        cmds.undoInfo(closeChunk=True)



#------------------------------- mirror to opposite


def mirror_to_opposite(*args):
    global MIRROR_PATTERNS
    mirror_exceptions_file_path = general.get_mirror_exceptions_file()

    ATTRIBUTES_TO_IGNORE = {"tag"}

    # Cargar excepciones
    def load_exceptions(file_path):
        if os.path.exists(file_path):
            with open(file_path, 'r') as file:
                return json.load(file)
        else:
            return {}

    exceptions = load_exceptions(mirror_exceptions_file_path)

    def find_pattern_in_name(name, patterns):
        for pattern in patterns:
            if pattern in name:
                return True
        return False

    def is_attribute_modifiable(control, attr):
        return cmds.getAttr(f"{control}.{attr}", settable=True)


    def find_opposite_name(name):
        # Divide el nombre en partes (namespace y nombre del control)
        namespace, _, control_name = name.rpartition(':')

        for pattern, opposite_pattern in MIRROR_PATTERNS:
            # Revisa si el patrón está en el nombre del control
            if pattern in control_name:
                # Realiza el reemplazo solo para la primera aparición del patrón
                new_control_name = control_name.replace(pattern, opposite_pattern, 1)
                possible_opposite_name = f'{namespace}:{new_control_name}' if namespace else new_control_name
                #print(f"Intentando reemplazar {pattern} por {opposite_pattern} en {control_name}, resultado: {possible_opposite_name}")  # Impresión de depuración
                if cmds.objExists(possible_opposite_name):
                    return possible_opposite_name

        return None


    def apply_exception(control, attr, value):
        # Obtén el nombre del control sin el namespace
        control_name = control.rsplit(":", 1)[-1]

        if control_name in exceptions and attr in exceptions[control_name]:
            exception_type = exceptions[control_name][attr]
            if exception_type == "invert":
                return -value
        return value

    def swap_control_values(control1, control2):
        if not cmds.objExists(control1):
            return

        attrs_to_swap = cmds.listAttr(control1, keyable=True)
        if not attrs_to_swap:
            return

        for attr in attrs_to_swap:
            if attr in ATTRIBUTES_TO_IGNORE or not is_attribute_modifiable(control1, attr):
                continue

            try:
                value1 = cmds.getAttr(f"{control1}.{attr}")

                # Aplicar excepciones si es necesario
                modified_value1 = apply_exception(control1, attr, value1)

                if control2 and cmds.objExists(control2) and is_attribute_modifiable(control2, attr):
                    # Aplicar los valores modificados de control1 a control2
                    cmds.setAttr(f"{control2}.{attr}", modified_value1)
                else:  # Solo un control (central o único)
                    # Verificar si hay excepción para este control y atributo
                    control_name = control1.rsplit(":", 1)[-1]
                    if control_name in exceptions and attr in exceptions[control_name]:
                        exception_type = exceptions[control_name][attr]
                        if exception_type == "invert":
                            cmds.setAttr(f"{control1}.{attr}", modified_value1)
                    else:
                        # Invertir solo los atributos específicos si no hay excepciones
                        if attr in ["translateX", "rotateZ", "rotateY"]:
                            cmds.setAttr(f"{control1}.{attr}", modified_value1)

            except Exception as e:
                cmds.warning(f"Could not process the attribute {attr} on {control1}: {str(e)}")



    def mirror_controls():
        selected_controls = cmds.ls(selection=True)
        
        if not selected_controls:
            print("Select a control")
            return

        processed_controls = set()

        for control in selected_controls:
            if control in processed_controls:
                continue

            opposite_name = find_opposite_name(control)
            if opposite_name:
                # Si el control opuesto no está seleccionado, aún así procede con el espejado
                swap_control_values(control, opposite_name if cmds.objExists(opposite_name) else None)
                processed_controls.add(control)
                if opposite_name:
                    processed_controls.add(opposite_name)
            else:
                # Tratar como control central o único si no se encuentra un opuesto
                swap_control_values(control, None)
                processed_controls.add(control)

    mirror_controls()





# _____________________________________ add exception

def add_mirror_invert_exception(*args):
    def get_selected_channels():
        main_channel_box = mel.eval('global string $gChannelBoxName; $temp=$gChannelBoxName;')
        selected_channels = cmds.channelBox(main_channel_box, query=True, selectedMainAttributes=True)
        return selected_channels

    def get_long_name(obj, short_name):
        """ Obtiene el nombre largo del atributo a partir de su nombre corto. """
        return cmds.attributeQuery(short_name, node=obj, longName=True)

    def add_exceptions_to_json(selected_controls, selected_channels, json_path):
        # Asegurar que la carpeta donde se guardará el archivo exista
        os.makedirs(os.path.dirname(json_path), exist_ok=True)

        # Leer datos existentes del archivo JSON, si existe
        if os.path.exists(json_path):
            with open(json_path, 'r') as file:
                exceptions = json.load(file)
        else:
            exceptions = {}

        # Añade las nuevas excepciones
        for control in selected_controls:
            control_name = control.rsplit(":", 1)[-1]
            if control_name not in exceptions:
                exceptions[control_name] = {}
            for channel in selected_channels:
                long_name = get_long_name(control, channel)
                exceptions[control_name][long_name] = "invert"

        # Guarda las excepciones actualizadas en el archivo JSON
        with open(json_path, 'w') as file:
            json.dump(exceptions, file, indent=4)

    def create_mirror_exception():
        mirror_exceptions_file_path = general.get_mirror_exceptions_file()
        selected_controls = cmds.ls(selection=True)
        selected_channels = get_selected_channels()

        if selected_controls and selected_channels:
            add_exceptions_to_json(selected_controls, selected_channels, mirror_exceptions_file_path)
            cmds.warning("Exception created")
        else:
            print("Select controls and channels to create an exception")

    create_mirror_exception()




def add_mirror_keep_exception(*args):
    def get_selected_channels():
        main_channel_box = mel.eval('global string $gChannelBoxName; $temp=$gChannelBoxName;')
        selected_channels = cmds.channelBox(main_channel_box, query=True, selectedMainAttributes=True)
        return selected_channels

    def get_long_name(obj, short_name):
        """ Obtiene el nombre largo del atributo a partir de su nombre corto. """
        return cmds.attributeQuery(short_name, node=obj, longName=True)

    def add_exceptions_to_json(selected_controls, selected_channels, json_path):
        # Asegurar que la carpeta donde se guardará el archivo exista
        os.makedirs(os.path.dirname(json_path), exist_ok=True)

        # Leer datos existentes del archivo JSON, si existe
        if os.path.exists(json_path):
            with open(json_path, 'r') as file:
                exceptions = json.load(file)
        else:
            exceptions = {}

        # Añade las nuevas excepciones
        for control in selected_controls:
            control_name = control.rsplit(":", 1)[-1]
            if control_name not in exceptions:
                exceptions[control_name] = {}
            for channel in selected_channels:
                long_name = get_long_name(control, channel)
                exceptions[control_name][long_name] = "keep"

        # Guarda las excepciones actualizadas en el archivo JSON
        with open(json_path, 'w') as file:
            json.dump(exceptions, file, indent=4)

    def create_mirror_exception():
        mirror_exceptions_file_path = general.get_mirror_exceptions_file()
        selected_controls = cmds.ls(selection=True)
        selected_channels = get_selected_channels()

        if selected_controls and selected_channels:
            add_exceptions_to_json(selected_controls, selected_channels, mirror_exceptions_file_path)
            cmds.warning("Exception created")
        else:
            print("Select controls and channels to create an exception")

    create_mirror_exception()



# _____________________________________ remove exception


def remove_mirror_invert_exception(*args):
    def get_selected_channels():
        main_channel_box = mel.eval('global string $gChannelBoxName; $temp=$gChannelBoxName;')
        selected_channels = cmds.channelBox(main_channel_box, query=True, selectedMainAttributes=True)
        return selected_channels

    def get_long_name(obj, short_name):
        """ Obtiene el nombre largo del atributo a partir de su nombre corto. """
        return cmds.attributeQuery(short_name, node=obj, longName=True)

    def remove_exceptions_from_json(selected_controls, selected_channels, json_path):
        if os.path.exists(json_path):
            with open(json_path, 'r') as file:
                exceptions = json.load(file)
        else:
            exceptions = {}

        # Elimina las excepciones para los controles y canales seleccionados
        for control in selected_controls:
            # Obtén el nombre del control sin el namespace
            control_name = control.rsplit(":", 1)[-1]

            if control_name in exceptions:
                for channel in selected_channels:
                    long_name = get_long_name(control, channel)
                    if long_name in exceptions[control_name]:
                        del exceptions[control_name][long_name]

        # Guarda las excepciones actualizadas en el archivo JSON
        with open(json_path, 'w') as file:
            json.dump(exceptions, file, indent=4)

    def remove_mirror_exceptions():
        mirror_exceptions_file_path = general.get_mirror_exceptions_file()
        selected_controls = cmds.ls(selection=True)
        selected_channels = get_selected_channels()

        if selected_controls and selected_channels:
            remove_exceptions_from_json(selected_controls, selected_channels, mirror_exceptions_file_path)
            cmds.warning("Exception removed")
        else:
            print("Select controls and channels to remove exceptions")

    remove_mirror_exceptions()



# ______________________________________________________COPY PASTE ANIMATION ______________________________________________________________________________#


def copy_animation(*args):
    def get_animated_channels(control):
        animated_channels = []
        attributes = cmds.listAttr(control, keyable=True)
        for attr in attributes:
            if cmds.getAttr(f"{control}.{attr}", se=True):  # se = settable
                connections = cmds.listConnections(f"{control}.{attr}", s=True, d=False)
                if connections:
                    animated_channels.append(attr)
        return animated_channels

    # Función para guardar la animación en un archivo JSON
    def save_animation_to_json(json_file_path, animation_data):
        # Asegurar que la carpeta donde se guardará el archivo exista
        os.makedirs(os.path.dirname(json_file_path), exist_ok=True)
        
        with open(json_file_path, "w") as json_file:
            json.dump(animation_data, json_file, indent=4)

    selected_objects = cmds.ls(selection=True)

    if not selected_objects:
        print("Select at least one control")
        return

    time_range = get_selected_time_range()
    animation_data = {}

    try:
        # Procesar cada objeto seleccionado
        for control in selected_objects:
            control_name = control.rsplit(":", 1)[-1]  # Eliminar namespace
            animated_channels = get_animated_channels(control)

            # Obtener la animación de los canales animados
            animation_data[control_name] = {}
            for channel in animated_channels:
                if time_range:
                    keyframes = cmds.keyframe(f"{control}.{channel}", query=True, time=(time_range[0], time_range[1]))
                    values = cmds.keyframe(f"{control}.{channel}", query=True, vc=True, time=(time_range[0], time_range[1]))
                else:
                    keyframes = cmds.keyframe(f"{control}.{channel}", query=True)
                    values = cmds.keyframe(f"{control}.{channel}", query=True, vc=True)
                animation_data[control_name][channel] = {"keyframes": keyframes, "values": values}

        json_file_path = general.get_copy_paste_animation_file()

        save_animation_to_json(json_file_path, animation_data)

        if time_range:
            clear_timeslider_selection()

        print("Animation saved")
    except Exception as e:
        cmds.warning(f"Error saving animation: {e}")



# PASTE ANIMATION ___________________________________________________________________________

def paste_animation(*args):
    def apply_animation_from_json(json_file_path, selected_objects):
        # Leer el archivo JSON
        with open(json_file_path, "r") as json_file:
            animation_data = json.load(json_file)

        # Aplicar animación a los objetos seleccionados
        for control in selected_objects:
            control_name = control.rsplit(":", 1)[-1]  # Eliminar namespace

            if control_name in animation_data:
                for channel, anim_data in animation_data[control_name].items():
                    # Borrar animación existente
                    cmds.cutKey(control, time=(0, 10000), attribute=channel, option="keys")

                    # Aplicar nueva animación
                    for frame, value in zip(anim_data['keyframes'], anim_data['values']):
                        cmds.setKeyframe(control, time=frame, attribute=channel, value=value)

    # Obtener los objetos seleccionados
    selected_objects = cmds.ls(selection=True)

    if not selected_objects:
        print("Select at least one control")
        return


    json_file_path = general.get_copy_paste_animation_file()

    # Aplicar animación a los objetos seleccionados
    apply_animation_from_json(json_file_path, selected_objects)

    print("Animation restored")


# PASTE INSERT _________________________________________________________________________


def paste_insert_animation(*args):
    def apply_animation_from_json(json_file_path, selected_objects, insert_time):
        # Leer el archivo JSON
        with open(json_file_path, "r") as json_file:
            animation_data = json.load(json_file)

        # Aplicar animación a los objetos seleccionados
        for control in selected_objects:
            control_name = control.rsplit(":", 1)[-1]  # Eliminar namespace

            if control_name in animation_data:
                for channel, anim_data in animation_data[control_name].items():
                    if anim_data['keyframes']:
                        # Calcular la diferencia de tiempo
                        time_diff = insert_time - anim_data['keyframes'][0]

                        # Insertar animación ajustada
                        for frame, value in zip(anim_data['keyframes'], anim_data['values']):
                            adjusted_frame = frame + time_diff
                            cmds.setKeyframe(control, time=adjusted_frame, attribute=channel, value=value)

    # Obtener los objetos seleccionados y el tiempo actual
    selected_objects = cmds.ls(selection=True)
    current_time = cmds.currentTime(query=True)

    if not selected_objects:
        print("Select at least one control")
        return

    json_file_path = general.get_copy_paste_animation_file()

    # Aplicar animación a los objetos seleccionados en el tiempo actual
    apply_animation_from_json(json_file_path, selected_objects, current_time)

    print("Animation inserted")




# PASTE OPPOSITE ________________________________________________________________________

def paste_opposite_animation(*args):

    mirror_exceptions_file_path = general.get_mirror_exceptions_file()

    ATTRIBUTES_TO_IGNORE = {"tag"}

    # Cargar excepciones
    def load_exceptions(file_path):
        if os.path.exists(file_path):
            with open(file_path, 'r') as file:
                return json.load(file)
        else:
            return {}

    exceptions = load_exceptions(mirror_exceptions_file_path)


    def find_mirror_control(control_name):
        for pattern, opposite_pattern in MIRROR_PATTERNS:
            if pattern in control_name:
                return control_name.replace(pattern, opposite_pattern, 1)
        return None


    def mirror_value(attr, value):
        if attr in exceptions.get(control_name, {}):
            exception_type = exceptions[control_name][attr]
            if exception_type == "invert":
                return -value
        if attr in [""]:
            return -value
        return value


    json_file_path = general.get_copy_paste_animation_file()

    with open(json_file_path, "r") as json_file:
        animation_data = json.load(json_file)

    for control_name, anim_data in animation_data.items():
        mirror_control_name = find_mirror_control(control_name)

        if mirror_control_name:
            full_mirror_control_name = next((c for c in cmds.ls() if c.endswith(mirror_control_name)), None)
            if not full_mirror_control_name:
                continue

            for channel, channel_data in anim_data.items():
                mirrored_values = [mirror_value(channel, v) for v in channel_data['values']]
                cmds.cutKey(full_mirror_control_name, time=(0, 10000), attribute=channel, option="keys")
                for frame, value in zip(channel_data['keyframes'], mirrored_values):
                    cmds.setKeyframe(full_mirror_control_name, time=frame, attribute=channel, value=value)
    
    print("Mirror Animation Restored")


def paste_animation_to(source_control_name=None, replace=True, insert_at_current=False, *args, **kwargs):

    # Utilidades locales
    def _short(name):
        # quita namespace si lo hay
        return name.rsplit(":", 1)[-1]

    def _attr_exists_and_settable(node, attr):
        if not cmds.objExists(node):
            return False
        full_attr = f"{node}.{attr}"
        if not cmds.objExists(full_attr):
            return False
        try:
            # settable=True y no locked
            return cmds.getAttr(full_attr, se=True) and not cmds.getAttr(full_attr, lock=True)
        except Exception:
            return False

    def _load_animation(json_file_path):
        with open(json_file_path, "r") as f:
            return json.load(f)

    # Destinos: selección actual
    targets = cmds.ls(selection=True) or []
    if not targets:
        print("Select at least one destination control")
        return

    # Cargar JSON
    json_file_path = general.get_copy_paste_animation_file()
    if not os.path.exists(json_file_path):
        cmds.warning("No animation file found. Please copy animation first")
        return

    try:
        animation_data = _load_animation(json_file_path)
    except Exception as e:
        cmds.warning("Error reading animation file: {}".format(e))
        return

    if not isinstance(animation_data, dict) or not animation_data:
        cmds.warning("Animation file is empty or invalid")
        return

    # Determinar ORIGEN
    available_sources = list(animation_data.keys())

    if source_control_name is None:
        if len(available_sources) == 1:
            source_control_name = available_sources[0]
        else:
            cmds.warning(
                "Multiple sources found in animation file. "
                "Please specify source_control_name. Available: {}".format(", ".join(available_sources))
            )
            return
    else:
        # Aceptar tanto con como sin namespace; normalizamos a corto
        source_control_name = _short(source_control_name)

    # Buscar el nombre EXACTO en el JSON por comparación de cortos
    matched_source = None
    for k in available_sources:
        if _short(k) == source_control_name:
            matched_source = k
            break

    if matched_source is None:
        cmds.warning(
            "Source control '{}' not found in animation file. Available: {}".format(
                source_control_name, ", ".join(available_sources)
            )
        )
        return

    src_channels = animation_data.get(matched_source, {})
    if not src_channels:
        cmds.warning("No channel data found for source '{}'.".format(matched_source))
        return

    # Calcular desplazamiento temporal si insertamos en el tiempo actual
    time_shift = 0.0
    if insert_at_current:
        # Primer key del primer canal que tenga keys
        first_key_time = None
        for ch, data in src_channels.items():
            kfs = data.get("keyframes") or []
            if kfs:
                t0 = kfs[0]
                if first_key_time is None or (t0 is not None and t0 < first_key_time):
                    first_key_time = t0
        if first_key_time is not None:
            current = cmds.currentTime(query=True)
            time_shift = current - first_key_time

    # Aplicar a cada destino seleccionado
    total_keys_set = 0
    for dst in targets:
        # Para logs legibles, también mostramos el corto
        dst_short = _short(dst)

        for channel, anim_data in src_channels.items():
            keyframes = anim_data.get("keyframes") or []
            values = anim_data.get("values") or []

            if not keyframes or not values:
                continue

            if not _attr_exists_and_settable(dst, channel):
                # Canal no existe en el destino; lo saltamos
                continue

            if replace:
                try:
                    cmds.cutKey(dst, time=(0, 1e6), attribute=channel, option="keys")
                except Exception:
                    pass

            # Pegar keys (con posible desplazamiento)
            for frame, value in zip(keyframes, values):
                t = frame + time_shift
                try:
                    cmds.setKeyframe(dst, time=t, attribute=channel, value=value)
                    total_keys_set += 1
                except Exception as e:
                    # Si un key falla, seguimos con los demás canales
                    print("Failed to set key on {}.{} at {}: {}".format(dst, channel, t, e))

    if total_keys_set == 0:
        cmds.warning(
            "No keys were pasted. Check that destination controls have the needed attributes "
            "and that the source has keyframes."
        )
    else:
        mode = "inserted at current time" if insert_at_current else "pasted"
        repl = " (replaced existing keys)" if replace else ""
        cmds.warning("Animation {} from '{}' to {} target(s){} — {} keys set.".format(
            mode, _short(matched_source), len(targets), repl, total_keys_set
        ))




# COPY POSE ________________________________________________________________________


def copy_pose(*args):
    def save_pose_to_json(json_file_path, pose_data):
        os.makedirs(os.path.dirname(json_file_path), exist_ok=True)
        with open(json_file_path, "w") as json_file:
            json.dump(pose_data, json_file, indent=4)

    selected_objects = cmds.ls(selection=True)

    if not selected_objects:
        print("Select at least one control")
        return

    pose_data = {}

    # Procesar cada objeto seleccionado
    for control in selected_objects:
        control_name = control.rsplit(":", 1)[-1]  # Eliminar namespace
        attributes = cmds.listAttr(control, keyable=True)

        if attributes is None:
            continue  # Si no hay atributos keyable, continuar con el siguiente objeto

        pose_data[control_name] = {}
        for attr in attributes:
            if not cmds.getAttr(f"{control}.{attr}", lock=True) and \
               cmds.getAttr(f"{control}.{attr}", keyable=True):
                try:
                    values = cmds.getAttr(f"{control}.{attr}")
                    pose_data[control_name][attr] = values
                except:
                    pass  # Ignorar atributos que no pueden ser leídos

    json_file_path = general.get_copy_paste_pose_file()

    save_pose_to_json(json_file_path, pose_data)

    cmds.warning("Pose saved")





# PASTE POSE _____________________________________________________________



def paste_pose(*args):
    def is_valid_attribute_value(value):
        """
        Valida si el valor del atributo es estándar (numérico o lista numérica)
        y no contiene caracteres inusuales como '#'.
        """
        if isinstance(value, (float, int)):
            return True
        if isinstance(value, list) and all(isinstance(v, (float, int)) for v in value):
            return True
        if isinstance(value, str) and not re.search(r'[# ]', value):
            return True
        return False

    def apply_pose_from_json(json_file_path, selected_objects):
        # Leer el archivo JSON
        with open(json_file_path, "r") as json_file:
            pose_data = json.load(json_file)

        # Aplicar pose a los objetos seleccionados
        for control in selected_objects:
            control_name = control.rsplit(":", 1)[-1]  # Eliminar namespace

            if control_name in pose_data:
                for attr, value in pose_data[control_name].items():
                    # Validar el valor del atributo
                    if not is_valid_attribute_value(value):
                        continue

                    # Aplicar valor al atributo
                    if not cmds.getAttr(f"{control}.{attr}", lock=True):
                        try:
                            if isinstance(value, list):
                                cmds.setAttr(f"{control}.{attr}", *value)
                            else:
                                cmds.setAttr(f"{control}.{attr}", value)
                        except RuntimeError as e:
                            print(f"Error setting attribute {attr} on {control}: {e}")

    # Obtener los objetos seleccionados
    selected_objects = cmds.ls(selection=True)

    if not selected_objects:
        print("Select at least one control")
        return

    json_file_path = general.get_copy_paste_pose_file()

    # Aplicar pose a los objetos seleccionados
    apply_pose_from_json(json_file_path, selected_objects)

    cmds.warning("Pose restored")





# ______________________________________________ TANGENTS


# MATCH CYCLE

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


def match_curve_cycle(*args):
    curveNames = getSelectedCurves()

    for curve in curveNames:
        # Obtén el tiempo y valor del primer keyframe
        firstKeyTime = cmds.findKeyframe(curve, which='first')
        firstKeyValue = cmds.keyframe(curve, time=(firstKeyTime, firstKeyTime), query=True, valueChange=True)[0]

        # Obtén las propiedades de las tangentes del primer keyframe
        firstInTangentType = cmds.keyTangent(curve, time=(firstKeyTime,), query=True, inTangentType=True)[0]
        firstOutTangentType = cmds.keyTangent(curve, time=(firstKeyTime,), query=True, outTangentType=True)[0]
        firstOutAngle = cmds.keyTangent(curve, time=(firstKeyTime,), query=True, outAngle=True)[0]
        firstInAngle = cmds.keyTangent(curve, time=(firstKeyTime,), query=True, inAngle=True)[0]

        # Obtén el tiempo del último keyframe
        lastKeyTime = cmds.findKeyframe(curve, which='last')

        # Establece el valor del último keyframe igual al primer keyframe
        cmds.keyframe(curve, time=(lastKeyTime, lastKeyTime), valueChange=firstKeyValue)

        # Copia las propiedades de las tangentes del primer keyframe al último keyframe
        cmds.keyTangent(curve, time=(lastKeyTime,), edit=True, inTangentType=firstInTangentType, outTangentType=firstOutTangentType)

        # Ajusta los ángulos de las tangentes del último keyframe para que coincidan con los del primer keyframe
        cmds.keyTangent(curve, time=(lastKeyTime,), edit=True, inAngle=firstInAngle, outAngle=firstOutAngle)



# Bouncy tangets

def get_graph_editor_selected_keyframes():
    anim_curves = cmds.keyframe(q=True, selected=True, name=True)
    if not anim_curves:
        return []

    keyframes = []
    for curve in anim_curves:
        keyframes += [(curve, frame) for frame in cmds.keyframe(curve, q=True, selected=True)]

    return keyframes

def calculateTangentAngle(curve, time1, value1, time2, value2):
    # Calcula el ángulo de la tangente entre dos keyframes
    if time2 - time1 == 0:
        return 0  # Evitar división por cero
    angle_radians = math.atan2(value2 - value1, time2 - time1)
    angle_degrees = math.degrees(angle_radians)
    return angle_degrees

def bouncy_tangets(*args, angle_adjustment_factor=1.3):  # Ajuste de ángulo
    selectedKeyframes = get_graph_editor_selected_keyframes()

    if not selectedKeyframes:
        print("Select a keyframe in GraphEditor")
        return

    for curve, time in selectedKeyframes:
        # Obtener los tiempos y valores de los keyframes
        keyTimes = cmds.keyframe(curve, query=True, timeChange=True)
        keyValues = cmds.keyframe(curve, query=True, valueChange=True)

        # Encontrar índice del keyframe actual
        currentIndex = keyTimes.index(time)

        # Calcular ángulo para la tangente de entrada
        if currentIndex > 0:
            inAngle = calculateTangentAngle(curve, keyTimes[currentIndex - 1], keyValues[currentIndex - 1], time, keyValues[currentIndex])
        else:
            inAngle = 0  # No hay keyframe anterior

        # Calcular ángulo para la tangente de salida
        if currentIndex < len(keyTimes) - 1:
            outAngle = calculateTangentAngle(curve, time, keyValues[currentIndex], keyTimes[currentIndex + 1], keyValues[currentIndex + 1])
        else:
            outAngle = 0  # No hay keyframe posterior

        adjusted_in_angle = max(-85, min(85, inAngle * angle_adjustment_factor))
        adjusted_out_angle = max(-85, min(85, outAngle * angle_adjustment_factor))


        # Ajustar las tangentes con el factor de ajuste de ángulo
        cmds.keyTangent(curve, time=(time,), edit=True, lock=False, absolute=True, 
                        inAngle=adjusted_in_angle, 
                        outAngle=adjusted_out_angle)