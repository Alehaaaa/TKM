


'''

    TheKeyMachine - Animation Toolset for Maya Animators                                           
                                                                                                                                              
                                                                                                                                              
    This file is part of TheKeyMachine an open source software for Autodesk Maya, licensed under the GNU General Public License v3.0 (GPL-3.0).                                           
    You are free to use, modify, and distribute this code under the terms of the GPL-3.0 license.                                              
    By using this code, you agree to keep it open source and share any modifications.                                                          
    This code is provided "as is," without any warranty. For the full license text, visit https://www.gnu.org/licenses/gpl-3.0.html            
                                                                                                                                              
                                                                                                                                              
    Developed by: Rodrigo Torres / rodritorres.com                                                                                             
    Modified by: Alehaaaa / alehaaaa.github.io                                                                                                 
                                                                                                                                             


'''



import maya.cmds as cmds
import maya.mel as mel
import maya.OpenMaya as om

import json
import os
import sys
import platform
import urllib.request
import re
import shutil
import base64


import TheKeyMachine

import TheKeyMachine.core.customGraph as cg
import TheKeyMachine.mods.generalMod as general
import TheKeyMachine.mods.uiMod as ui
import TheKeyMachine.mods.keyToolsMod as keyTools

from TheKeyMachine.mods.generalMod import config

INSTALL_PATH                    = config["INSTALL_PATH"]
USER_FOLDER_PATH                = config["USER_FOLDER_PATH"]


# ________________________________________________ Selection Sets  ______________________________________________________ #


# Ruta del archivo JSON
user_scripts_folder = os.path.join(USER_FOLDER_PATH, "TheKeyMachine_user_data/tools/cg_selection_sets")

json_file = os.path.join(user_scripts_folder, "cg_selections_sets_data.json")



def set_button_value(button_name):
    selection = cmds.ls(selection=True)
    button_selections = load_button_selections()
    if button_name in button_selections and button_selections[button_name]["locked"]:
        cmds.warning("SelectionSet is locked. Unlock before overwriting")
        return
    button_selections[button_name] = {"selection": selection, "locked": False}
    save_button_selections(button_selections)


def lock_button_selection(button_name):
    button_selections = load_button_selections()
    if button_name in button_selections:
        button_selections[button_name]["locked"] = True
    else:
        button_selections[button_name] = {"selection": [], "locked": True}
    save_button_selections(button_selections)

def unlock_button_selection(button_name):
    button_selections = load_button_selections()
    if button_name in button_selections:
        button_selections[button_name]["locked"] = False
    else:
        button_selections[button_name] = {"selection": [], "locked": False}
    save_button_selections(button_selections)


def load_button_selection(button_name):
    # Cargar el archivo JSON existente o crear uno nuevo si no existe
    button_selections = load_button_selections()

    # Obtener la selección guardada para el botón y seleccionar los objetos correspondientes
    if button_name in button_selections:
        selection_names = button_selections[button_name]["selection"]
        selection = cmds.ls(selection_names)
        cmds.select(selection, replace=True)
    else:
        cmds.select(clear=True)


def load_button_selections():
    # Cargar el archivo JSON existente o crear uno nuevo si no existe
    button_selections = {}
    if os.path.exists(json_file):
        with open(json_file, "r") as f:
            button_selections = json.load(f)
    return button_selections


def add_button_selection(button_name):
    # Obtener la selección actual en la escena
    selection = cmds.ls(selection=True)

    # Cargar el archivo JSON existente o crear uno nuevo si no existe
    button_selections = load_button_selections()

    # Verificar si el botón ya tiene una selección guardada
    if button_name in button_selections:
        if button_selections[button_name]["locked"]:
            cmds.warning("SelectionSet is locked. Unlock before modifying")
            return
        # Si la tecla Ctrl está presionada, realizar suma de selecciones
        if cmds.getModifiers() & 4:  # 4 representa la tecla Ctrl
            button_selections[button_name]["selection"] += selection
        # Si la tecla Ctrl no está presionada, agregar objetos seleccionados sin duplicados
        else:
            button_selections[button_name]["selection"] = list(set(button_selections[button_name]["selection"] + selection))
    else:
        # Guardar la selección como nueva si no hay una existente
        button_selections[button_name] = {"selection": selection, "locked": False}

    # Guardar el diccionario actualizado en el archivo JSON
    save_button_selections(button_selections)


def remove_button_selection(button_name):
    # Obtener la selección actual en la escena
    selection = cmds.ls(selection=True)

    # Cargar el archivo JSON existente o crear uno nuevo si no existe
    button_selections = load_button_selections()

    # Verificar si el botón tiene una selección guardada
    if button_name in button_selections:
        if button_selections[button_name]["locked"]:
            cmds.warning("SelectionSet is locked. Unlock before modifying")
            return
        # Si la tecla Shift está presionada, realizar resta de selecciones
        if cmds.getModifiers() & 1:  # 1 representa la tecla Shift
            button_selections[button_name]["selection"] = [obj for obj in button_selections[button_name]["selection"] if obj not in selection]
        # Si la tecla Shift no está presionada, eliminar solo los objetos seleccionados
        else:
            button_selections[button_name]["selection"] = [obj for obj in button_selections[button_name]["selection"] if obj not in selection]

        # Eliminar la entrada del botón si la lista queda vacía
        if not button_selections[button_name]["selection"]:
            del button_selections[button_name]

    # Guardar el diccionario actualizado en el archivo JSON
    save_button_selections(button_selections)


def handle_button_selection(button_name):
    modifiers = cmds.getModifiers()
    # Verificar si la tecla Shift está presionada
    if modifiers & 1:  # 1 representa la tecla Shift
        load_button_selection(button_name)
    # Verificar si la tecla Ctrl está presionada
    elif modifiers & 4:  # 4 representa la tecla Ctrl
        remove_button_selection(button_name)
    else:
        load_button_selection(button_name)


def save_button_selections(button_selections):
    json_file = os.path.join(user_scripts_folder, "cg_selections_sets_data.json")

    os.makedirs(os.path.dirname(json_file), exist_ok=True)
    # Guardar el diccionario actualizado en el archivo JSON
    with open(json_file, "w") as f:
        json.dump(button_selections, f)

    print("Saved button selection")