



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
import maya.OpenMaya as om
import maya.OpenMayaUI as mui

from shiboken2 import wrapInstance
from PySide2 import QtWidgets, QtGui, QtCore
from PySide2.QtWidgets import QApplication, QDesktopWidget
from PySide2 import QtWidgets
from PySide2.QtCore import *
from PySide2.QtGui import *
from PySide2.QtWidgets import *
from PySide2.QtCore import QTimer

import json
import ssl
import os
import platform
import sys
import urllib.request
import urllib.parse
import re
import shutil
import base64
import importlib
import zipfile
from functools import partial


import TheKeyMachine.core.customGraph as cg
import TheKeyMachine.core.toolbar as tb
import TheKeyMachine.mods.generalMod as general
import TheKeyMachine.mods.uiMod as ui
import TheKeyMachine.mods.keyToolsMod as keyTools
import TheKeyMachine.mods.selSetsMod as selSets
import TheKeyMachine.mods.mediaMod as media
import TheKeyMachine.mods.barMod as bar

from TheKeyMachine.mods.generalMod import config

INSTALL_PATH                    = config["INSTALL_PATH"]
USER_FOLDER_PATH                = config["USER_FOLDER_PATH"]
LICENSE_FOLDER                  = config["LICENSE_FOLDER"]




# ________________________________________________ General  ______________________________________________________ #

def getImage(*args, image):
    img_dir = os.path.join(INSTALL_PATH, "TheKeyMachine/data/img/")

    # Ruta del archivo de configuración
    fullImgDir = os.path.join(img_dir, image)

    return fullImgDir


def toggle_shelf(*args):
    mel.eval('ToggleShelf')


def ref(value, widget):
    widget.setWindowOpacity(value)


def desactivado(*args):
    print("desactivado")


def reloadUI():
    cmds.evalDeferred("import TheKeyMachine.core.customGraph as cg; cg.createCustomGraph()", lowestPriority=True)


def getUiName():
    getUi=cmds.getPanel(withFocus=True)
    print(getUi)





# ________________________________________________ Sync  ______________________________________________________ #


# Se usa en customGraph para la funcion de filtro

filterMode_sync_on_code = '''

global proc syncChannelBoxFcurveEd()
{
    global string $gChannelBoxName;

    string $selAttrs[] = `selectedChannelBoxPlugs`;
    selectionConnection -e -clear graphEditor1FromOutliner;
    if (size($selAttrs) > 0) {
        for ($attr in $selAttrs) {
            selectionConnection -e -select $attr graphEditor1FromOutliner;
        }
        filterUIFilterSelection graphEditor1OutlineEd "";
    } else if (size($selAttrs) == 0) {
        string $objects[] = `channelBoxObjects`;
        for ($obj in $objects) {
            selectionConnection -e -select $obj graphEditor1FromOutliner;

        }
        filterUIClearFilter graphEditor1OutlineEd;
        
    }
}
syncChannelBoxFcurveEd();
'''

filterMode_sync_off_code = '''

global proc syncChannelBoxFcurveEd()
{

}
syncChannelBoxFcurveEd();

filterUIClearFilter graphEditor1OutlineEd;

'''

def filterMode_sync_on():
    mel.eval(filterMode_sync_on_code)

def filterMode_sync_off():
    mel.eval(filterMode_sync_off_code)


def customGraph_filter_mods(*args):
    # Get the current state of the modifiers
    mods = mel.eval('getModifiers')
    shift_pressed = bool(mods % 2)  # Check if Shift is pressed

    if shift_pressed:
        filterMode_sync_off()
    else:
        filterMode_sync_on()




# ---------------------------------------------------- UNINSTALL ---------------------------------------------------------------------------------



def uninstall():
    # Muestra un cuadro de diálogo para confirmar la desinstalación
    result = cmds.confirmDialog(
        title='Uninstall TheKeyMachine',
        message='Do you want to uninstall TheKeyMachine?',
        button=['Uninstall', 'Cancel'],
        defaultButton='Uninstall',
        cancelButton='Cancel',
        dismissString='Cancel'
    )

    if result == 'Uninstall':
        try:
            # Desactiva el thread para centrar la toolbar 
            run_centerToolbar = False

            # Definiendo las rutas
            user_app_dir = cmds.internalVar(userAppDir=True)
            user_dir = cmds.internalVar(userScriptDir=True)
            tkm_folder_path = os.path.join(INSTALL_PATH, "TheKeyMachine")
            
            version_maya = cmds.about(version=True)
            maya_dir = os.path.join(user_app_dir, version_maya)
            env_file_path = os.path.join(maya_dir, "Maya.env")
            
            # Crear una carpeta llamada "uninstalled" dentro de TheKeyMachine si no existe
            uninstalled_folder_path = os.path.join(tkm_folder_path, "uninstalled")
            if not os.path.exists(uninstalled_folder_path):
                os.makedirs(uninstalled_folder_path)
            else:
                cmds.warning('"uninstalled" folder already exists inside "TheKeyMachine".')

            # obsolete - Lista de carpetas a eliminar dentro de TheKeyMachine. En Win hay problemas al descargar el modulo de pyarmor, por eso no se intenta borra ya que daría error
            if platform.system() == 'Windows':
                if os.path.exists(tkm_folder_path):
                    shutil.rmtree(tkm_folder_path)
                else:
                    cmds.warning("TheKeyMachine folder not found.")
            else:
                # Para Linux y Darwin (macOS), intenta eliminar toda la carpeta "TheKeyMachine"
                if os.path.exists(tkm_folder_path):
                    shutil.rmtree(tkm_folder_path)
                else:
                    cmds.warning("TheKeyMachine folder not found.")

            # Borra la carpeta de la licencia del usuario
            if os.path.exists(LICENSE_FOLDER):
                shutil.rmtree(LICENSE_FOLDER)
            else:
                print("")

            # Borra las líneas de código en Maya.env
            if os.path.exists(env_file_path):
                with open(env_file_path, 'r') as f:
                    lines = f.readlines()

                with open(env_file_path, 'w') as f:
                    in_tkm_code_block = False
                    for line in lines:
                        if line.strip() == "# THIS LINE IS HERE FOR UNINSTALLING PURPOSES, PLEASE DO NOT TOUCH. START OF THEKEYMACHINE CODE":
                            in_tkm_code_block = True
                        elif line.strip() == "# END OF THEKEYMACHINE CODE":
                            in_tkm_code_block = False
                        elif not in_tkm_code_block:
                            f.write(line)
            else:
                cmds.warning('Maya.env file does not exist.')


            # Elimina customGraph
            if cmds.columnLayout("customGraph_columnLayout", exists=True):
                cmds.deleteUI("customGraph_columnLayout")

            # Necesitamos retrasar la eliminacion del workspace para dar tiempo a parar el callback 'centrar toolbar'
            def remove_tkm_workspace():
                # Elimina el workspaceControl llamado "k" y "s""
                if cmds.workspaceControl('k', exists=True):
                    cmds.workspaceControl('k', e=True, fl=True) # La hacemos flotante
                    cmds.workspaceLayoutManager( s=True ) # Salvar workspace 
                    cmds.workspaceControl('k', e=True, close=True) # Cerrar
                    cmds.deleteUI('k', control=True)
                else:
                    cmds.warning('The workspaceControl "k" does not exist.')

                if cmds.workspaceControl('s', exists=True):
                    cmds.deleteUI('s', control=True)
                else:
                    cmds.warning('The workspaceControl "s" does not exist.')
                    
                cmds.warning('TheKeyMachine has been uninstalled')

            QTimer.singleShot(700, remove_tkm_workspace)
            
        except Exception as e:
            cmds.error(f'An error occurred during uninstallation: {e}')
    else:
        print("Uninstallation cancelled by user.")






# ___________________________________________________________ ORBIT _____________________________________________________________


def accion_temp_pivot():
    bar.create_temp_pivot(False)



acciones = {
    "isolate_master": "bar.isolate_master",
    "align_selected_objects": "bar.align_selected_objects",
    "mod_tracer": "bar.mod_tracer",
    "reset_objects_mods": "keyTools.reset_objects_mods",
    "deleteAnimation": "bar.deleteAnimation",
    "selectOpposite": "keyTools.selectOpposite",
    "copyOpposite": "keyTools.copyOpposite",
    "mirror": "keyTools.mirror",
    "copy_animation": "keyTools.copy_animation",
    "paste_animation": "keyTools.paste_animation",
    "paste_insert_animation": "keyTools.paste_insert_animation",
    "selectHierarchy": "bar.selectHierarchy",
    "mod_link_objects": "keyTools.mod_link_objects",
    "accion_temp_pivot": "accion_temp_pivot",
    "copy_pose": "keyTools.copy_pose",
    "paste_pose": "keyTools.paste_pose",
    "copy_worldspace_single_frame": "bar.copy_worldspace_single_frame",
    "paste_worldspace_single_frame": "bar.paste_worldspace_single_frame"



}


iconos_acciones = {
    "bar.isolate_master": media.isolate_image,
    "bar.align_selected_objects": media.aling_menu_image,
    "bar.mod_tracer": media.tracer_menu_image,
    "keyTools.reset_objects_mods": media.reset_animation_image,
    "bar.deleteAnimation": media.delete_animation_image,
    "keyTools.selectOpposite": media.select_opposite_image,
    "keyTools.copyOpposite": media.copy_opposite_image,
    "keyTools.mirror": media.mirror_image,
    "keyTools.copy_animation": media.copy_paste_animation_image,
    "keyTools.paste_animation": media.paste_animation_image,
    "keyTools.paste_insert_animation": media.paste_insert_animation_image,
    "bar.selectHierarchy": media.select_hierarchy_image,
    "keyTools.mod_link_objects": media.link_objects_image,
    "accion_temp_pivot": media.temp_pivot_image,
    "keyTools.copy_pose": media.copy_pose_image,
    "keyTools.paste_pose": media.paste_pose_image,
    "bar.copy_worldspace_single_frame": media.copy_worldspace_frame_animation_image,
    "bar.paste_worldspace_single_frame": media.paste_worldspace_frame_animation_image
}


def ejecutar_accion(identificador):
    if identificador == "isolate_master":
        bar.isolate_master()
    elif identificador == "align_selected_objects":
        bar.align_selected_objects()
    elif identificador == "mod_tracer":
        bar.mod_tracer()
    elif identificador == "reset_objects_mods":
        keyTools.reset_objects_mods()
    elif identificador == "deleteAnimation":
        bar.deleteAnimation()
    elif identificador == "selectOpposite":
        keyTools.selectOpposite()
    elif identificador == "copyOpposite":
        keyTools.copyOpposite()
    elif identificador == "mirror":
        keyTools.mirror()
    elif identificador == "copy_animation":
        keyTools.copy_animation()
    elif identificador == "paste_animation":
        keyTools.paste_animation()
    elif identificador == "paste_insert_animation":
        keyTools.paste_insert_animation()
    elif identificador == "copy_pose":
        keyTools.copy_pose()
    elif identificador == "paste_pose":
        keyTools.paste_pose()
    elif identificador == "selectHierarchy":
        bar.selectHierarchy()
    elif identificador == "mod_link_objects":
        keyTools.mod_link_objects()
    elif identificador == "accion_temp_pivot":
        accion_temp_pivot()
    elif identificador == "copy_worldspace_single_frame":
        bar.copy_worldspace_single_frame()
    elif identificador == "paste_worldspace_single_frame":
        bar.paste_worldspace_single_frame()
    else:
        pass


def guardar_configuracion_botones():
    config_path = USER_FOLDER_PATH + "/TheKeyMachine_user_data/tools/orbit/orbit.py"
    
    with open(config_path, "r") as file:
        lineas = file.readlines()

    # Actualizar la línea correspondiente a cada botón
    for button_id, action_name in configuracion_orbit.items():
        linea_a_actualizar = f"{button_id} = "
        indice_linea = next((i for i, linea in enumerate(lineas) if linea.startswith(linea_a_actualizar)), None)
        
        if indice_linea is not None:
            lineas[indice_linea] = f"{button_id} = '{action_name}'\n"
        else:
            # Si el botón no está en el archivo, añadirlo al final
            lineas.append(f"{button_id} = '{action_name}'\n")

    # Reescribir el archivo con las líneas actualizadas
    with open(config_path, "w") as file:
        file.writelines(lineas)



def leer_configuracion_orbit():
    config_path = USER_FOLDER_PATH + "/TheKeyMachine_user_data/tools/orbit/orbit.py"
    config_dir = os.path.dirname(config_path)
    configuracion_orbit = {
        "button1": "reset_objects_mods",
        "button2": "deleteAnimation",
        "button3": "selectOpposite",
        "button4": "copyOpposite",
        "button5": "mirror",
        "button6": "selectHierarchy",
        "button7": "isolate_master"
    }

    # Crear el directorio si no existe
    if not os.path.exists(config_dir):
        os.makedirs(config_dir)

    try:
        with open(config_path, "r") as file:
            lines = file.readlines()
        for line in lines:
            if line.startswith("button"):
                key, value = line.split('=')
                key = key.strip()
                value = value.strip().strip("'")
                configuracion_orbit[key] = value
    except FileNotFoundError:
        # Crear el archivo si no existe
        with open(config_path, "w") as file:
            for key, value in configuracion_orbit.items():
                file.write(f"{key} = '{value}'\n")

    return configuracion_orbit

configuracion_orbit = leer_configuracion_orbit()

class CustomButton(QtWidgets.QPushButton):
    def __init__(self, icon_path, button_id, parent=None, window=None):
        super(CustomButton, self).__init__(parent)
        self.setIcon(QtGui.QIcon(icon_path))
        self.window = window
        self.button_id = button_id

        desktop = QDesktopWidget()
        screen_resolution = desktop.screenGeometry()
        screen_width = screen_resolution.width()

        if screen_width == 3840:
            self.setIconSize(QtCore.QSize(45, 45))
        else:
            self.setIconSize(QtCore.QSize(25, 25))

    def mousePressEvent(self, event):
        if event.button() == QtCore.Qt.RightButton:
            self.showContextMenu(event.pos())
        else:
            super(CustomButton, self).mousePressEvent(event)

    def showContextMenu(self, position):
        menu = QtWidgets.QMenu()

        # Crear acciones con íconos
        action1 = QtWidgets.QAction(QtGui.QIcon(media.isolate_image), "Isolate", self)
        action2 = QtWidgets.QAction(QtGui.QIcon(media.aling_menu_image), "Align", self)
        action3 = QtWidgets.QAction(QtGui.QIcon(media.tracer_menu_image), "Tracer", self)
        action4 = QtWidgets.QAction(QtGui.QIcon(media.reset_animation_image), "Reset Values", self)
        action5 = QtWidgets.QAction(QtGui.QIcon(media.delete_animation_image), "Delete Animation", self)
        action6 = QtWidgets.QAction(QtGui.QIcon(media.select_opposite_image), "Select Opposite", self)
        action7 = QtWidgets.QAction(QtGui.QIcon(media.copy_opposite_image), "Copy Opposite", self)
        action8 = QtWidgets.QAction(QtGui.QIcon(media.mirror_image), "Mirror", self)
        action9 = QtWidgets.QAction(QtGui.QIcon(media.copy_paste_animation_image), "Copy Animation", self)
        action10 = QtWidgets.QAction(QtGui.QIcon(media.paste_animation_image), "Paste Animation", self)
        action11 = QtWidgets.QAction(QtGui.QIcon(media.paste_insert_animation_image), "Paste Insert Animation", self)
        action12 = QtWidgets.QAction(QtGui.QIcon(media.copy_pose_image), "Copy Pose", self)
        action13 = QtWidgets.QAction(QtGui.QIcon(media.paste_pose_image), "Paste Pose", self)
        action14 = QtWidgets.QAction(QtGui.QIcon(media.select_hierarchy_image), "Select Hierarchy", self)
        action15 = QtWidgets.QAction(QtGui.QIcon(media.link_objects_image), "Copy/Paste Link", self)
        action16 = QtWidgets.QAction(QtGui.QIcon(media.temp_pivot_image), "Temp Pivot", self)
        action17 = QtWidgets.QAction(QtGui.QIcon(media.copy_worldspace_frame_animation_image), "Copy Worldspace Current Frame", self)
        action18 = QtWidgets.QAction(QtGui.QIcon(media.paste_worldspace_frame_animation_image), "Paste Worldspace Current Frame", self)
        action_opacity = QtWidgets.QAction("Toggle Dynamic Opacity", self)
        
        menu.addAction(action1)
        menu.addAction(action2)
        menu.addAction(action3)
        menu.addAction(action4)
        menu.addAction(action5)
        menu.addAction(action6)
        menu.addAction(action7)
        menu.addAction(action8)
        menu.addAction(action9)
        menu.addAction(action10)
        menu.addAction(action11)
        menu.addAction(action12)
        menu.addAction(action13)
        menu.addAction(action14)
        menu.addAction(action15)
        menu.addAction(action16)
        menu.addAction(action17)
        menu.addAction(action18)
        menu.addSeparator()
        menu.addAction(action_opacity)

        action = menu.exec_(self.mapToGlobal(position))

        if action == action1:
            self.updateButton(media.isolate_image, "isolate_master")
        elif action == action2:
            self.updateButton(media.aling_menu_image, "align_selected_objects")
        elif action == action3:
            self.updateButton(media.tracer_menu_image, "mod_tracer")
        elif action == action4:
            self.updateButton(media.reset_animation_image, "reset_objects_mods")
        elif action == action5:
            self.updateButton(media.delete_animation_image, "deleteAnimation")
        elif action == action6:
            self.updateButton(media.select_opposite_image, "selectOpposite")
        elif action == action7:
            self.updateButton(media.copy_opposite_image, "copyOpposite")
        elif action == action8:
            self.updateButton(media.mirror_image, "mirror")
        elif action == action9:
            self.updateButton(media.copy_paste_animation_image, "copy_animation")
        elif action == action10:
            self.updateButton(media.paste_animation_image, "paste_animation")
        elif action == action11:
            self.updateButton(media.paste_insert_animation_image, "paste_insert_animation")
        elif action == action12:
            self.updateButton(media.copy_pose_image, "copy_pose")
        elif action == action13:
            self.updateButton(media.paste_pose_image, "paste_pose")
        elif action == action14:
            self.updateButton(media.select_hierarchy_image, "selectHierarchy")
        elif action == action15:
            self.updateButton(media.link_objects_image, "mod_link_objects")
        elif action == action16:
            self.updateButton(media.temp_pivot_image, "accion_temp_pivot")
        elif action == action17:
            self.updateButton(media.copy_worldspace_frame_animation_image, "copy_worldspace_single_frame")
        elif action == action18:
            self.updateButton(media.paste_worldspace_frame_animation_image, "paste_worldspace_single_frame")
        elif action == action_opacity:
            self.toggleDynamicOpacity()


    def updateButton(self, icon_path, action_identifier):
        self.setIcon(QtGui.QIcon(icon_path))

        # Desconectar y reconectar la señal
        try:
            self.clicked.disconnect()
        except RuntimeError:
            pass
        self.clicked.connect(lambda: ejecutar_accion(action_identifier))

        # Verificar si el identificador está en el diccionario de acciones
        if action_identifier in acciones:
            configuracion_orbit[self.button_id] = action_identifier
            guardar_configuracion_botones()
        else:
            pass

    def toggleDynamicOpacity(self):
        global dynamic_opacity
        dynamic_opacity = not dynamic_opacity
        if not dynamic_opacity:
            self.window.setWindowOpacity(1.0)
        else:
            self.window.setWindowOpacity(0.60)



def orbit_window(*args, offset_x=0, offset_y=0):

    desktop = QDesktopWidget()
    screen_resolution = desktop.screenGeometry()
    screen_width = screen_resolution.width()

    global dynamic_opacity
    dynamic_opacity = False 


    if cmds.window("orbit_window", exists=True):
        cmds.deleteUI("orbit_window")

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

    def change_opacity():
        # Verificar si el cursor aún está dentro de la ventana
        if window.rect().contains(window.mapFromGlobal(QtGui.QCursor.pos())):
            window.setWindowOpacity(1.0)  # Aumentar la opacidad

    # Crear un QTimer
    timer = QtCore.QTimer()
    timer.timeout.connect(change_opacity)
    timer.setSingleShot(True)  # El timer se dispara solo una vez

    def enterEvent(event):
        global dynamic_opacity
        if dynamic_opacity:
            timer.start(100)

    def leaveEvent(event):
        global dynamic_opacity
        if dynamic_opacity:
            timer.stop()  # Detener el timer si el mouse sale antes del retardo
            window.setWindowOpacity(0.60) 

    parent = wrapInstance(int(mui.MQtUtil.mainWindow()), QtWidgets.QWidget)
    window = QtWidgets.QWidget(parent, QtCore.Qt.Window | QtCore.Qt.FramelessWindowHint)

    if screen_width == 3840:
        window.resize(600, 60)
    else:
        window.resize(360, 15)

    window.setObjectName('orbit_window')
    window.setWindowTitle('Orbit')
    window.setWindowOpacity(1.0) 
    window.setAttribute(QtCore.Qt.WA_TranslucentBackground)
    window.mousePressEvent = mousePressEvent
    window.mouseMoveEvent = mouseMoveEvent
    window.mouseReleaseEvent = mouseReleaseEvent
    window.enterEvent = enterEvent
    window.leaveEvent = leaveEvent

    central_widget = QtWidgets.QWidget(window)
    central_widget.setStyleSheet("""
        QWidget {
            background-color: #444444; 
            border-radius: 6px;
            border: 1px solid #393939;
        }
        QLabel {
            border: none;
        }
        """)
    window_layout = QtWidgets.QVBoxLayout(window)
    window_layout.addWidget(central_widget)

    # Layout principal para todos los botones
    main_layout = QtWidgets.QHBoxLayout()
    central_widget.setLayout(main_layout)


    botones = []  # Lista para almacenar los botones

    for button_id in ["button1", "button2", "button3", "button4", "button5", "button6", "button7"]:
        action_name = configuracion_orbit.get(button_id, "")  # Obtener el nombre de la acción desde la configuración
        icon_path = iconos_acciones.get(acciones.get(action_name, ""), media.isolate_image)  # Obtener la ruta del icono

        boton = CustomButton(icon_path, button_id, window=window)
        
        # Conectar el botón a la acción correspondiente
        boton.clicked.connect(partial(ejecutar_accion, action_name))

        botones.append(boton)

        # Establecer el estilo del botón aquí (si es necesario)

        main_layout.addWidget(boton)
        spacer = QtWidgets.QSpacerItem(50, 10, QtWidgets.QSizePolicy.Expanding, QtWidgets.QSizePolicy.Minimum)
        main_layout.addSpacerItem(spacer)

        # Estilo para los botones
        button_style = """
            QPushButton {
                /* Estilos para el estado normal del botón */
                border: 0px solid #444444;
                border-radius: 0px;
            }
            QPushButton:hover {
                /* Estilos para cuando el cursor está sobre el botón */
                background-color: #505050;
            }
        """
        boton.setStyleSheet(button_style)


    # Botón de cierre
    close_button = QtWidgets.QPushButton('X')
    if screen_width == 3840:
        close_button.setFixedSize(30, 30)
    else:
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
    main_layout.addWidget(close_button)

    cursor_pos = QtGui.QCursor.pos()

    # Mover la ventana solo si los offsets no son ambos cero
    if not (offset_x == 0 and offset_y == 0):
        adjusted_pos = cursor_pos + QtCore.QPoint(offset_x, offset_y)
        window.move(adjusted_pos)

    window.show()


def orbit_window_close():
    if cmds.window("orbit_window", exists=True):
        cmds.deleteUI("orbit_window")




# ________________________________________________ Donate window  ______________________________________________________ #




def donate_window():

    desktop = QDesktopWidget()
    screen_resolution = desktop.screenGeometry()
    screen_width = screen_resolution.width()

    if cmds.window("tkm_donate_window", exists=True):
        cmds.deleteUI("tkm_donate_window")

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
    window.resize(350, 330)
    window.setWindowOpacity(1.0)
    window.setObjectName('tkm_donate_window')
    window.setWindowTitle('Donate')
    window.setAttribute(QtCore.Qt.WA_TranslucentBackground)

    window.mousePressEvent = mousePressEvent
    window.mouseMoveEvent = mouseMoveEvent
    window.mouseReleaseEvent = mouseReleaseEvent

    central_widget = QtWidgets.QWidget(window)
    central_widget.setStyleSheet("""
    QWidget {
        background-color: #454545; 
        border-radius: 10px;
        border: 1px solid #393939;
    }
    QLabel {
        border: none;
    }
    """)
    layout = QtWidgets.QVBoxLayout(central_widget)
    layout.setSpacing(0)
    layout.setContentsMargins(10, 10, 10, 10)

    header_layout = QtWidgets.QHBoxLayout()
    header_layout.addStretch()

    close_button = QtWidgets.QPushButton('X')
    close_button.setFixedSize(22, 22)
    close_button.setStyleSheet(
        "QPushButton {"
        "    background-color: #585858;"
        "    border: none;"
        "    color: #ccc;"
        "    border-radius: 5px;"
        "}"
        "QPushButton:hover {"
        "    background-color: #c56054;"
        "    border-radius: 5px;"
        "}"
    )
    close_button.clicked.connect(window.close)
    header_layout.addWidget(close_button)
    layout.addLayout(header_layout)

    # Código para mostrar la imagen
    image_label = QtWidgets.QLabel()
    image_label.setAlignment(QtCore.Qt.AlignCenter)
    layout.addWidget(image_label, 0, QtCore.Qt.AlignHCenter)
    about_image = ui.getImage(image="stripe.png")
    image_label.setPixmap(about_image)
    image_label.setSizePolicy(QtWidgets.QSizePolicy.Fixed, QtWidgets.QSizePolicy.Fixed)

    TheKeyMachine_version = general.get_thekeymachine_version()
    TheKeyMachine_build_version = general.get_thekeymachine_build_version()


    if screen_width == 3840:
        label6 = QtWidgets.QLabel("<br><span style='font-size: 14px; color:#cccccc'>"
                          "The development of TheKeyMachine is a big effort in terms of energy and time.<br><br>If you use this tool professionally or regularly, please try to make a donation.<br> This will greatly help the project grow and have continuity. Every small amount counts.<br>"
                          "Thank you!<br><br><br>"
                          "Support TheKeyMachine <a href='http://thekeymachine.xyz/donate.php' style='color:#86CDAD;'><br>http://thekeymachine.xyz/donate</a></span><br><br>")

    else:
        label6 = QtWidgets.QLabel("<br><span style='font-size: 12px; color:#cccccc'>"
                          "The development of TheKeyMachine is a big effort<br>in terms of time and energy.<br><br>If you use this tool professionally or regularly,<br>please try to make a donation.<br><br> This will greatly help the project grow<br> and have continuity. Every small amount counts.<br>"
                          "Thank you!<br><br><br>"
                          "Support TheKeyMachine<a href='http://thekeymachine.xyz/donate.php' style='color:#86CDAD;'><br>http://thekeymachine.xyz/donate</a></span><br><br>")



        # Habilitar interacciones de enlaces
        label6.setOpenExternalLinks(True)

          
    label6.setAlignment(QtCore.Qt.AlignCenter)
    layout.addWidget(label6)

    if screen_width == 3840:
        window.resize(480, 420)
        close_button.setFixedSize(32, 32)

    window_layout = QtWidgets.QVBoxLayout(window)
    window_layout.addWidget(central_widget)
    window.setLayout(window_layout)

    # Centrar la ventana en la ventana principal de Maya
    maya_geometry = general.get_maya_window_geometry()
    x = maya_geometry.x() + (maya_geometry.width() - window.width()) / 2
    y = maya_geometry.y() + (maya_geometry.height() - window.height()) / 2
    window.move(x, y)

    window.show()


# ________________________________________________ About window  ______________________________________________________ #




def about_window():

    desktop = QDesktopWidget()
    screen_resolution = desktop.screenGeometry()
    screen_width = screen_resolution.width()

    if cmds.window("tkm_about_window", exists=True):
        cmds.deleteUI("tkm_about_window")

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
    window.resize(350, 330)
    window.setWindowOpacity(1.0)
    window.setObjectName('tkm_about_window')
    window.setWindowTitle('About')
    window.setAttribute(QtCore.Qt.WA_TranslucentBackground)

    window.mousePressEvent = mousePressEvent
    window.mouseMoveEvent = mouseMoveEvent
    window.mouseReleaseEvent = mouseReleaseEvent

    central_widget = QtWidgets.QWidget(window)
    central_widget.setStyleSheet("""
    QWidget {
        background-color: #454545; 
        border-radius: 10px;
        border: 1px solid #393939;
    }
    QLabel {
        border: none;
    }
    """)
    layout = QtWidgets.QVBoxLayout(central_widget)
    layout.setSpacing(0)
    layout.setContentsMargins(10, 10, 10, 10)

    header_layout = QtWidgets.QHBoxLayout()
    header_layout.addStretch()

    close_button = QtWidgets.QPushButton('X')
    close_button.setFixedSize(22, 22)
    close_button.setStyleSheet(
        "QPushButton {"
        "    background-color: #585858;"
        "    border: none;"
        "    color: #ccc;"
        "    border-radius: 5px;"
        "}"
        "QPushButton:hover {"
        "    background-color: #c56054;"
        "    border-radius: 5px;"
        "}"
    )
    close_button.clicked.connect(window.close)
    header_layout.addWidget(close_button)
    layout.addLayout(header_layout)

    # Código para mostrar la imagen
    image_label = QtWidgets.QLabel()
    image_label.setAlignment(QtCore.Qt.AlignCenter)
    layout.addWidget(image_label, 0, QtCore.Qt.AlignHCenter)
    about_image = ui.getImage(image="TheKeyMachine_logo_250.png")
    image_label.setPixmap(about_image)
    image_label.setSizePolicy(QtWidgets.QSizePolicy.Fixed, QtWidgets.QSizePolicy.Fixed)

    TheKeyMachine_version = general.get_thekeymachine_version()
    TheKeyMachine_build_version = general.get_thekeymachine_build_version()

    if screen_width == 3840:
        label2 = QtWidgets.QLabel("<span style='font-size: 16px; color:#cccccc'>Animation toolset for Maya Animators<br><br><br></span><br><span style='font-size: 20px; color:#cccccc'><b>Version:&nbsp;&nbsp;</b></span><span style='font-size: 20px; color:#86CDAD'>beta v{}</span><span style='font-size: 20px; color:#cccccc'><b>&nbsp;&nbsp;&nbsp;&nbsp;Build:&nbsp;&nbsp;</b></span><span style='font-size: 20px; color:#86CDAD'>{}</span><br><br><br>".format(TheKeyMachine_version, TheKeyMachine_build_version))
    else:
        label2 = QtWidgets.QLabel("<span style='font-size: 12px; color:#cccccc'>Animation toolset for Maya Animators<br><br><br></span><br><span style='font-size: 14px; color:#cccccc'><b>Version:&nbsp;&nbsp;</b></span><span style='font-size: 14px; color:#86CDAD'>beta v{}</span><span style='font-size: 14px; color:#cccccc'><b>&nbsp;&nbsp;&nbsp;&nbsp;Build:&nbsp;&nbsp;</b></span><span style='font-size: 14px; color:#86CDAD'>{}</span><br><br><br>".format(TheKeyMachine_version, TheKeyMachine_build_version))

    label2.setAlignment(QtCore.Qt.AlignCenter)
    layout.addWidget(label2, 0, QtCore.Qt.AlignHCenter)
    label2.setSizePolicy(QtWidgets.QSizePolicy.Fixed, QtWidgets.QSizePolicy.Fixed)

    if screen_width == 3840:
                label6 = QtWidgets.QLabel("<br><span style='font-size: 14px; color:#cccccc'>"
                                  "This tool is licensed under the GNU General Public License v3.0.<br>"
                                  "For more details, see <a href='https://www.gnu.org/licenses/gpl-3.0.en.html' style='color:#86CDAD;'>GNU GPL 3.0</a>.<br><br>"
                                  "Developed by: "
                                  "Rodrigo Torres - <a href='http://rodritorres.com' style='color:#86CDAD;'>rodritorres.com</a></span><br><br>"
                                  "<span style='font-size: 10px; color:#cccccc'>"
                                  "http://www.thekeymachine.xyz / "
                                  "x@thekeymachine.xyz</span>")
    else:
        label6 = QtWidgets.QLabel("<br><span style='font-size: 10px; color:#cccccc'>"
                                  "This tool is licensed under the GNU General Public License v3.0.<br>"
                                  "For more details, see <a href='https://www.gnu.org/licenses/gpl-3.0.en.html' style='color:#86CDAD;'>GNU GPL 3.0</a>.<br><br>"
                                  "Developed by: "
                                  "Rodrigo Torres - <a href='http://rodritorres.com' style='color:#86CDAD;'>rodritorres.com</a></span><br><br>"
                                  "<span style='font-size: 10px; color:#cccccc'>"
                                  "http://www.thekeymachine.xyz / "
                                  "x@thekeymachine.xyz</span>")

        # Habilitar interacciones de enlaces
        label6.setOpenExternalLinks(True)

          


    label6.setAlignment(QtCore.Qt.AlignCenter)
    layout.addWidget(label6)

    if screen_width == 3840:
        window.resize(480, 420)
        close_button.setFixedSize(32, 32)

    window_layout = QtWidgets.QVBoxLayout(window)
    window_layout.addWidget(central_widget)
    window.setLayout(window_layout)

    # Centrar la ventana en la ventana principal de Maya
    maya_geometry = general.get_maya_window_geometry()
    x = maya_geometry.x() + (maya_geometry.width() - window.width()) / 2
    y = maya_geometry.y() + (maya_geometry.height() - window.height()) / 2
    window.move(x, y)

    window.show()






# ___________________________________________________ BUG Report ___________________________________________________________ #



def on_send_click(name_input, email_input, explanation_textbox, script_error_textbox, confirmation_label, window, send_button):
    name = name_input.text()
    email = email_input.text()
    explanation = explanation_textbox.toPlainText()
    script_error = script_error_textbox.toPlainText()

    if not validate_form(name, explanation):
        confirmation_label.setText("Please fill in the required fields.<br>")
        return

    success = send_bug_report(name, email, explanation, script_error)
    if success:
        confirmation_label.setText("Report sent successfully. Thanks!<br>")
        send_button.setStyleSheet("background-color: #525252; color: #666; border: none;")  # Ajusta el estilo a tu preferencia
        send_button.setEnabled(False)
        QTimer.singleShot(3100, window.close)
    else:
        confirmation_label.setText("Failed to send the report. Try again later.<br>")


def send_bug_report(name, email, explanation, script_error):
    url = ""

    # Obtener version de Python, OS y Maya
    python_version = sys.version
    os_version = platform.system()
    maya_version = cmds.about(version=True)
    tkm_version = general.get_thekeymachine_version()

    data = {
        'name': name,
        'email': email,
        'explanation': explanation,
        'script_error': script_error,
        'python_version': python_version,
        'os_version': os_version,
        'maya_version': maya_version,
        'tkm_version': tkm_version
    }
    data = urllib.parse.urlencode(data).encode('utf-8')

    # Ruta al archivo .pem y creación del contexto SSL

    install_dir = os.path.join(INSTALL_PATH, "TheKeyMachine")
    cert_file_path = os.path.join(install_dir, "data/cert/thekeymachine.pem")
    context = ssl.create_default_context(cafile=cert_file_path)

    with urllib.request.urlopen(url, data, context=context) as response:
        response_data = response.read().decode('utf-8')
        if "success" in response_data:
            return True
        else:
            return False


def validate_form(name, explanation):
    if not name.strip() or not explanation.strip():
        return False
    return True

def bug_report_window(*args):
    desktop = QDesktopWidget()
    screen_resolution = desktop.screenGeometry()
    screen_width = screen_resolution.width()

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

    def limit_textbox_characters(textbox, max_chars):
        current_text = textbox.toPlainText()
        if len(current_text) > max_chars:
            textbox.setPlainText(current_text[:max_chars])
            textbox.moveCursor(QtGui.QTextCursor.End)

    parent = wrapInstance(int(mui.MQtUtil.mainWindow()), QtWidgets.QWidget)

    window = QtWidgets.QWidget(parent, QtCore.Qt.Window | QtCore.Qt.FramelessWindowHint)
    window.resize(600, 700)
    window.setObjectName('BugReportWindow')
    window.setWindowTitle('Report a Bug')
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
        border: 1px solid #393939;
    }
    QLabel {
        border: none;
    }
    """)

    layout = QtWidgets.QVBoxLayout(central_widget)
    layout.setContentsMargins(15, 15, 15, 15)
    layout.setAlignment(QtCore.Qt.AlignTop)

    window_layout = QtWidgets.QVBoxLayout(window)
    window_layout.addWidget(central_widget)
    window.setLayout(window_layout)


    # Styles
    apology_label_style = "color: #d37457; font-size: 20px;"
    apology_text_style = "color: #ccc; font-size: 14px;"
    name_label_style = "color: #bbb; font-size: 12px;"
    email_label_style = "color: #bbb; font-size: 12px;"
    error_label_style = "color: #bbb; font-size: 12px;"
    script_editor_label_style = "color: #bbb; font-size: 12px;"
    confirmation_label_style = "color: #9bbbca;"

    input_style = "background-color:  #2d2d2d ; font-size: 12px; border: none; border-radius: 5px; color: #bbb;"
    textbox_style = "background-color: #2d2d2d; font-size: 12px; border: none; border-radius: 5px; color: #bbb;"

    if screen_width == 3840:
        # Styles
        apology_label_style = "color: #d37457; font-size: 30px;"
        apology_text_style = "color: #ccc; font-size: 18px;"
        name_label_style = "color: #bbb; font-size: 20px;"
        email_label_style = "color: #bbb; font-size: 20px;"
        error_label_style = "color: #bbb; font-size: 20px;"
        script_editor_label_style = "color: #bbb; font-size: 20px;"
        confirmation_label_style = "color: #9bbbca; font-size: 18px;"
        input_style = "background-color:  #2d2d2d ; font-size: 20px; border: none; border-radius: 5px; color: #bbb;"
        textbox_style = "background-color: #2d2d2d; font-size: 20px; border: none; border-radius: 5px; color: #bbb;"
    
    button_style = (
        "QPushButton {"
        "    background-color: #525252;"
        "    border: none;"
        "    border-radius: 5px;"
        "    color: #ccc;"
        "}"
        "QPushButton:hover {"
        "    background-color: #626262;"
        "    border-radius: 5px;"
        "    border: none;"
        "}"
    )

    close_button = QtWidgets.QPushButton('X')
    close_button.setFixedSize(25, 25)
    close_button.setStyleSheet(
        "QPushButton {"
        "    background-color: #585858;"
        "    border: none;"
        "    color: #ccc;"
        "    border-radius: 5px;"
        "}"
        "QPushButton:hover {"
        "    background-color: #c56054;"
        "    border-radius: 5px;"
        "}"
    )
    close_button.clicked.connect(window.close)

    apology_label = QtWidgets.QLabel("<b>Report a Bug</b>")
    apology_label2 = QtWidgets.QLabel("Have you found a bug? Please fill the report and I will do")
    apology_label3 = QtWidgets.QLabel("my best to fix it in the next update.<br>")
    
    apology_label.setStyleSheet(apology_label_style)
    apology_label2.setStyleSheet(apology_text_style)
    apology_label3.setStyleSheet(apology_text_style)

    name_label = QtWidgets.QLabel("")
    name_label.setStyleSheet(name_label_style)
    name_input = QtWidgets.QLineEdit()
    name_input.setStyleSheet(input_style)
    name_input.setFixedSize(300, 25)
    name_input.setPlaceholderText("Your name")
    name_input.setMaxLength(50)

    email_label = QtWidgets.QLabel("")
    email_input = QtWidgets.QLineEdit()
    email_input.setStyleSheet(input_style)
    email_input.setFixedSize(300, 25)
    email_input.setPlaceholderText("Your email")
    email_input.setMaxLength(50)

    explanation_label = QtWidgets.QLabel("")
    explanation_textbox = QtWidgets.QTextEdit()
    explanation_textbox.setStyleSheet(textbox_style)
    explanation_textbox.setPlaceholderText("Please describe the problem or error you're experiencing. To identify and correct the issue, it's essential to reproduce it. Detail step-by-step the actions you've taken and specify which tool is causing the error.")
    explanation_textbox.textChanged.connect(lambda: limit_textbox_characters(explanation_textbox, 1200))

    script_error_label = QtWidgets.QLabel("")
    script_error_textbox = QtWidgets.QTextEdit()
    script_error_textbox.setStyleSheet(textbox_style)
    script_error_textbox.setPlaceholderText("If you see any errors in the Script Editor, please copy and paste the code here. The last 3 or 4 lines should be sufficient.")
    script_error_textbox.textChanged.connect(lambda: limit_textbox_characters(script_error_textbox, 1200))

    confirmation_label = QtWidgets.QLabel("<br>")
    confirmation_label.setStyleSheet(confirmation_label_style)
    
    send_button = QtWidgets.QPushButton("Send bug")
    send_button.setFixedSize(550, 40)
    send_button.setStyleSheet(button_style)
    send_button.clicked.connect(lambda: on_send_click(name_input, email_input, explanation_textbox, script_error_textbox, confirmation_label, window, send_button))

    layout.addWidget(close_button, alignment=QtCore.Qt.AlignRight)
    layout.addWidget(apology_label, alignment=QtCore.Qt.AlignCenter)
    layout.addWidget(apology_label2, alignment=QtCore.Qt.AlignCenter)
    layout.addWidget(apology_label3, alignment=QtCore.Qt.AlignCenter)
    layout.addWidget(confirmation_label, alignment=QtCore.Qt.AlignCenter)
    #layout.addWidget(name_label)
    layout.addWidget(name_input)
    #layout.addWidget(email_label)
    layout.addWidget(email_input)
    layout.addWidget(explanation_label)
    layout.addWidget(explanation_textbox)
    layout.addWidget(script_error_label)
    layout.addWidget(script_error_textbox)
    
    layout.addWidget(send_button, alignment=QtCore.Qt.AlignCenter)

    if screen_width == 3840:
        window.resize(800, 1000)
        layout.setContentsMargins(15, 15, 15, 15)
        close_button.setFixedSize(35, 35)
        name_input.setFixedSize(400, 40)
        email_input.setFixedSize(400, 40)
        send_button.setFixedSize(750, 50)



    window.show()

    # Adjust the window position
    parent_geometry = parent.geometry()
    x = parent_geometry.x() + parent_geometry.width() / 2 - window.width() / 2
    y = parent_geometry.y() + parent_geometry.height() / 2 - window.height() / 2
    window.move(x, y)
