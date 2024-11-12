

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
from maya import OpenMaya as om
from maya import OpenMayaUI as omui
from maya.api import OpenMaya as om



from shiboken2 import wrapInstance
from PySide2.QtGui import QIcon
from PySide2.QtGui import QPixmap
from PySide2.QtWidgets import QWidget
from PySide2.QtWidgets import *
from PySide2 import QtWidgets

import json
import os
import urllib.request
import ssl
import re
import shutil
import base64
import subprocess
import sys
import platform



def load_config():
    current_script_dir = os.path.dirname(__file__)
    config_path = os.path.join(current_script_dir, "../data/config/config.json")
    config_path = os.path.normpath(config_path)

    try:
        with open(config_path, "r") as file:
            config = json.load(file)
    except IOError:
        print("Unable to load config data from:", config_path)
        config = {}

    USER_MAYA_DIR = cmds.internalVar(userAppDir=True)
    USERNAME = os.environ.get('USERNAME') or os.environ.get('USER')

    default_config = {
        "STUDIO_INSTALL": False,
        "INSTALL_PATH": os.path.join(USER_MAYA_DIR, "scripts"),
        "USER_FOLDER_PATH": os.path.join(USER_MAYA_DIR, "scripts"),
        "LICENSE_FOLDER": os.path.join(USER_MAYA_DIR, "scripts/TheKeyMachine_user_data/license"), # obsoleto
        "LICENSE_FILE_NAME": "user",
        "UPDATER": False,
        "BUG_REPORT": True,
        "CUSTOM_TOOLS_MENU": True,
        "CUSTOM_TOOLS_EDITABLE_BY_USER": True,
        "CUSTOM_SCRIPTS_MENU": True,
        "CUSTOM_SCRIPTS_EDITABLE_BY_USER": True
    }

    for key, default_value in default_config.items():
        if key not in config or config[key] == "":
            config[key] = default_value

    for key in ["INSTALL_PATH", "USER_FOLDER_PATH", "LICENSE_FOLDER"]:
        if "{USERNAME}" in config[key]:
            config[key] = config[key].replace("{USERNAME}", USERNAME)

    return config

config = load_config()



INSTALL_PATH = config["INSTALL_PATH"]
USER_FOLDER_PATH = config["USER_FOLDER_PATH"]


# ------------------------------------------------------------------------

def get_thekeymachine_version():
    thekeymachine_version = "0.1.3"
    return thekeymachine_version

def get_thekeymachine_build_version():
    thekeymachine_build_version = "294"
    return thekeymachine_build_version

def get_thekeymachine_codename():
    thekeymachine_codename = "Gort"
    return thekeymachine_codename




# ----- RUTAS ----------------------------------------------------------------------

# MIRROR EXCEPTIONS ___________________
def get_mirror_exceptions_file():
    cache_folder = os.path.join(USER_FOLDER_PATH, "TheKeyMachine_user_data/tools/mirror")
    mirror_exceptions_file_path = os.path.join(cache_folder, "mirror_data.json")
    return mirror_exceptions_file_path

def get_mirror_exceptions_folder():
    folder = os.path.join(USER_FOLDER_PATH, "TheKeyMachine_user_data/tools/mirror")
    return folder


# SET DEFAULT VALUES ___________________
def get_set_default_data_file():
    cache_folder = os.path.join(USER_FOLDER_PATH, "TheKeyMachine_user_data/tools/reset_default")
    mirror_exceptions_file_path = os.path.join(cache_folder, "reset_default_data.json")
    return mirror_exceptions_file_path

def get_set_default_data_folder():
    folder = os.path.join(USER_FOLDER_PATH, "TheKeyMachine_user_data/tools/reset_default")
    return folder

# COPY PASTE ANIMATION ___________________
def get_copy_paste_animation_file():
    cache_folder = os.path.join(USER_FOLDER_PATH, "TheKeyMachine_user_data/tools/copy_paste_animation")
    copy_paste_animation_file_path = os.path.join(cache_folder, "copy_paste_animation_data.json")
    return copy_paste_animation_file_path


# COPY PASTE POSE ___________________
def get_copy_paste_pose_file():
    cache_folder = os.path.join(USER_FOLDER_PATH, "TheKeyMachine_user_data/tools/copy_paste_pose")
    copy_paste_pose_file_path = os.path.join(cache_folder, "copy_paste_pose_data.json")
    return copy_paste_pose_file_path


# TEMP PIVOT _____________________________
def get_temp_pivot_data_file():
    cache_folder = os.path.join(USER_FOLDER_PATH, "TheKeyMachine_user_data/tools/temp_pivot")
    temp_pivot_file_path = os.path.join(cache_folder, "temp_pivot_data.json")
    return temp_pivot_file_path

def get_temp_pivot_data_folder():
    temp_pivot_data_folder = os.path.join(USER_FOLDER_PATH, "TheKeyMachine_user_data/tools/temp_pivot")
    return temp_pivot_data_folder

# COPY LINK ______________________________
def get_copy_link_data_file():
    cache_folder = os.path.join(USER_FOLDER_PATH, "TheKeyMachine_user_data/tools/copy_link")
    copy_link_file_path = os.path.join(cache_folder, "copy_link_data.json")
    return copy_link_file_path

def get_copy_link_data_folder():
    copy_link_data_folder = os.path.join(USER_FOLDER_PATH, "TheKeyMachine_user_data/tools/copy_link")
    return copy_link_data_folder

# COPY WORLDSPACE ________________________
def get_copy_worldspace_data_file():
    cache_folder = os.path.join(USER_FOLDER_PATH, "TheKeyMachine_user_data/tools/copy_worldspace")
    copy_worldspace_file_path = os.path.join(cache_folder, "copy_worldspace_data.json")
    return copy_worldspace_file_path

def get_copy_worldspace_data_folder():
    copy_worldspace_data_folder = os.path.join(USER_FOLDER_PATH, "TheKeyMachine_user_data/tools/copy_worldspace")
    return copy_worldspace_data_folder


def get_copy_worldspace_single_frame_data_file():
    cache_folder = os.path.join(USER_FOLDER_PATH, "TheKeyMachine_user_data/tools/copy_worldspace")
    copy_worldspace_single_frame_file_path = os.path.join(cache_folder, "copy_worldspace_single_frame_data.json")
    return copy_worldspace_single_frame_file_path

def get_copy_worldspace_single_frame_data_folder():
    copy_worldspace_single_frame_data_folder = os.path.join(USER_FOLDER_PATH, "TheKeyMachine_user_data/tools/copy_worldspace")
    return copy_worldspace_single_frame_data_folder


# ------------------------------------------------------------------------


def getImage(image):
    img_dir = os.path.join(INSTALL_PATH, "TheKeyMachine/data/img/")

    fullImgDir = os.path.join(img_dir, image)
    return fullImgDir


def create_TheKeyMachine_node():
    # Guardar la selección inicial
    initial_selection = cmds.ls(selection=True)

    tkm_version = get_thekeymachine_version()
    tkm_codename = get_thekeymachine_codename()

    if not cmds.objExists("TheKeyMachine"):
        # Crear el assetNode en lugar de un nodo de transformación
        node = cmds.container(type='dagContainer', name="TheKeyMachine")

        # Establecer el icono del assetNode
        icon_path = getImage("tkm_node.png")  # Usar la función para obtener la ruta del icono
        cmds.setAttr(node + '.iconName', icon_path, type='string')

        # Bloquear y ocultar todos los atributos de transformación
        attributes = ["translateX", "translateY", "translateZ",
                      "rotateX", "rotateY", "rotateZ",
                      "scaleX", "scaleY", "scaleZ",
                      "visibility"]
        
        for attr in attributes:
            cmds.setAttr(node + "." + attr, lock=True, keyable=False, channelBox=False)

        # Añadir los atributos "codeEnum" y "version"
        cmds.addAttr(node, longName="version", niceName="version", attributeType="enum", enumName=tkm_version, keyable=True)
        cmds.addAttr(node, longName="series", niceName="series", attributeType="enum", enumName=tkm_codename, keyable=True)

        # Restaurar la selección inicial
        if initial_selection:
            cmds.select(initial_selection, replace=True)



def create_ibookmarks_node():
    # Guardar la selección inicial
    initial_selection = cmds.ls(selection=True)

    if not cmds.objExists("iBookmarks"):
        node = cmds.createNode("transform", name="iBookmarks")
        
        # Bloquear y ocultar todos los atributos de transformación
        attributes = ["translateX", "translateY", "translateZ",
                      "rotateX", "rotateY", "rotateZ",
                      "scaleX", "scaleY", "scaleZ",
                      "visibility"]
        
        for attr in attributes:
            cmds.setAttr(node + "." + attr, lock=True, keyable=False, channelBox=False)
        cmds.parent("iBookmarks", "TheKeyMachine")

    # Restaurar la selección inicial
    if initial_selection:
        cmds.select(initial_selection, replace=True)



def get_local_config_file():
    scripts_dirm = cmds.internalVar(userAppDir=True)
    scripts_dir = os.path.join(scripts_dirm, "scripts/TheKeyMachine/data/config")

    # Ruta del archivo de configuración
    config_file = os.path.join(scripts_dir, "configuration.py")

    return config_file


def get_maya_window_size():
    # Obtén el objeto de la ventana principal de Maya
    maya_main_window_ptr = omui.MQtUtil.mainWindow()
    maya_main_window = wrapInstance(int(maya_main_window_ptr), QtWidgets.QWidget)
    
    # Obtén el tamaño de la ventana
    width = maya_main_window.width()
    height = maya_main_window.height()
    
    return width, height


def get_maya_window_geometry():
    maya_main_window_ptr = omui.MQtUtil.mainWindow()
    maya_main_window = wrapInstance(int(maya_main_window_ptr), QtWidgets.QMainWindow)
    return maya_main_window.geometry()

    
def open_url(url):
    import webbrowser
    webbrowser.open(url)


def open_file(sub_directory, file_name):
    scripts_dirm = cmds.internalVar(userAppDir=True)
    directory = os.path.join(USER_FOLDER_PATH, sub_directory)

    # Combinar el directorio y el nombre del archivo para obtener la ruta completa del archivo
    file_path = os.path.join(directory, file_name)

     # Comprueba si el archivo existe
    if not os.path.isfile(file_path):
        print(f"Error: file '{file_path}' does not exist")
        return

    # Abrir el archivo con la aplicación predeterminada
    if sys.platform == "win32":
        try:
            os.startfile(file_path)
        except Exception as e:
            print(f"Error opening the file: {e}")
            
    elif sys.platform == "darwin":
        subprocess.call(['open', file_path])

    elif sys.platform == "linux":
        try:
            subprocess.run(['xdg-open', file_path], check=True, stdout=subprocess.PIPE, stderr=subprocess.PIPE)
        except subprocess.CalledProcessError as e:
            # Si xdg-open produce un error, intenta cambiar temporalmente LD_LIBRARY_PATH y volver a intentar
            print(f"Error opening the file with xdg-open: {e}")
            print("Attempting to open the file with modified LD_LIBRARY_PATH...")
            
            original_ld_path = os.environ.get('LD_LIBRARY_PATH', '')
            os.environ['LD_LIBRARY_PATH'] = '/usr/lib:/lib:/usr/local/lib'
            
            try:
                subprocess.run(['xdg-open', file_path], check=True, stdout=subprocess.PIPE, stderr=subprocess.PIPE)
            except subprocess.CalledProcessError as e:
                print(f"Error opening the file with modified LD_LIBRARY_PATH: {e}")
            finally:
                # Restaurar el valor original de LD_LIBRARY_PATH
                os.environ['LD_LIBRARY_PATH'] = original_ld_path







