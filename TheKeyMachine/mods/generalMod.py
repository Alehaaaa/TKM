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
import json
import subprocess
import os
import sys
from TheKeyMachine.core import selection_targets


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
    USERNAME = os.environ.get("USERNAME") or os.environ.get("USER")

    default_config = {
        "INSTALL_PATH": os.path.join(USER_MAYA_DIR, "scripts"),
        "USER_FOLDER_PATH": os.path.join(USER_MAYA_DIR, "scripts"),
        "INTERNET_CONNECTION": True,
        "BUG_REPORT": True,
        "CUSTOM_TOOLS_MENU": True,
        "CUSTOM_TOOLS_EDITABLE_BY_USER": True,
        "CUSTOM_SCRIPTS_MENU": True,
        "CUSTOM_SCRIPTS_EDITABLE_BY_USER": True,
    }

    for key, default_value in default_config.items():
        if key not in config or config[key] == "":
            config[key] = default_value

    for key in ["INSTALL_PATH", "USER_FOLDER_PATH"]:
        if "{USERNAME}" in config[key]:
            config[key] = config[key].replace("{USERNAME}", USERNAME)

    return config


config = load_config()


INSTALL_PATH = config["INSTALL_PATH"]
USER_FOLDER_PATH = config["USER_FOLDER_PATH"]


# ------------------------------------------------------------------------


def get_thekeymachine_version():
    import TheKeyMachine

    return getattr(TheKeyMachine, "__version__", "unknown")


def get_thekeymachine_stage_version():
    import TheKeyMachine

    return getattr(TheKeyMachine, "__stage__", "unknown")


def get_thekeymachine_build_version():
    import TheKeyMachine

    return getattr(TheKeyMachine, "__build__", "unknown")


def get_thekeymachine_codename():
    import TheKeyMachine

    return getattr(TheKeyMachine, "__codename__", "unknown")


# ----- RUTAS ----------------------------------------------------------------------


def get_tkm_node_image():
    return os.path.join(INSTALL_PATH, "TheKeyMachine", "data", "img", "tkm_node.png")


def get_tool_data_path(tool_name, filename=None):
    """Generic factory for tool-specific user data paths."""
    folder = os.path.join(USER_FOLDER_PATH, "TheKeyMachine_user_data/tools", tool_name)
    if filename:
        return os.path.join(folder, filename)
    return folder


# MIRROR EXCEPTIONS ___________________
def get_mirror_exceptions_file():
    return get_tool_data_path("mirror", "mirror_data.json")


# SET DEFAULT VALUES ___________________
def get_set_default_data_file():
    return get_tool_data_path("default_default", "default_default_data.json")


# COPY PASTE ANIMATION ___________________
def get_copy_animation_file():
    return get_tool_data_path("copy_animation", "copy_animation_data.json")


# COPY PASTE POSE ___________________
def get_copy_paste_pose_file():
    return get_tool_data_path("copy_paste_pose", "copy_paste_pose_data.json")


# TEMP PIVOT _____________________________
def get_temp_pivot_data_file():
    return get_tool_data_path("temp_pivot", "temp_pivot_data.json")


def get_temp_pivot_data_folder():
    return get_tool_data_path("temp_pivot")


# COPY LINK ______________________________
def get_copy_link_data_file():
    return get_tool_data_path("copy_link", "copy_link_data.json")


def get_copy_link_data_folder():
    return get_tool_data_path("copy_link")


# COPY WORLDSPACE ________________________
def get_copy_worldspace_data_file():
    return get_tool_data_path("copy_worldspace", "copy_worldspace_data.json")


def get_copy_worldspace_data_folder():
    return get_tool_data_path("copy_worldspace")


def get_copy_worldspace_single_frame_data_file():
    return get_tool_data_path("copy_worldspace", "copy_worldspace_single_frame_data.json")


def get_copy_worldspace_single_frame_data_folder():
    return get_tool_data_path("copy_worldspace")


# ------------------------------------------------------------------------


def create_TheKeyMachine_node():
    # Guardar la selección inicial
    initial_selection = selection_targets.get_selected_objects()

    tkm_version = get_thekeymachine_version()
    tkm_stage = get_thekeymachine_stage_version()
    tkm_full_version = "v{} {}".format(tkm_version, tkm_stage)

    tkm_codename = get_thekeymachine_codename()

    if not cmds.objExists("TheKeyMachine"):
        # Crear el assetNode en lugar de un nodo de transformación
        node = cmds.container(type="dagContainer", name="TheKeyMachine")

        # Establecer el icono del assetNode
        icon = get_tkm_node_image()
        cmds.setAttr(node + ".iconName", icon, type="string")

        # Bloquear y ocultar todos los atributos de transformación
        attributes = ["translateX", "translateY", "translateZ", "rotateX", "rotateY", "rotateZ", "scaleX", "scaleY", "scaleZ", "visibility"]

        for attr in attributes:
            cmds.setAttr(node + "." + attr, lock=True, keyable=False, channelBox=False)

        # Añadir los atributos "codeEnum" y "version"
        cmds.addAttr(node, longName="version", niceName="version", attributeType="enum", enumName=tkm_full_version, keyable=True)
        cmds.addAttr(node, longName="series", niceName="series", attributeType="enum", enumName=tkm_codename, keyable=True)

        # Restaurar la selección inicial
        if initial_selection:
            cmds.select(initial_selection, replace=True)


def create_ibookmarks_node():
    # Guardar la selección inicial
    initial_selection = selection_targets.get_selected_objects()

    if not cmds.objExists("iBookmarks"):
        node = cmds.createNode("transform", name="iBookmarks")

        # Bloquear y ocultar todos los atributos de transformación
        attributes = ["translateX", "translateY", "translateZ", "rotateX", "rotateY", "rotateZ", "scaleX", "scaleY", "scaleZ", "visibility"]

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


def open_url(url):
    import webbrowser

    webbrowser.open(url)


def open_file(sub_directory, file_name):
    # scripts_dirm = cmds.internalVar(userAppDir=True)
    directory = os.path.join(USER_FOLDER_PATH, sub_directory)

    # Combinar el directorio y el nombre del archivo para obtener la ruta completa del archivo
    file_path = os.path.join(directory, file_name)

    # Comprueba si el archivo existe
    if not os.path.isfile(file_path):
        import TheKeyMachine.mods.reportMod as report

        report.report_detected_exception(
            context="open file",
            source_file=os.path.basename(__file__),
            traceback_text="File does not exist: {}".format(file_path),
        )
        return

    # Abrir el archivo con la aplicación predeterminada
    if sys.platform == "win32":
        try:
            os.startfile(file_path)
        except Exception as e:
            import TheKeyMachine.mods.reportMod as report

            report.report_detected_exception(e, context="open file")

    elif sys.platform == "darwin":
        subprocess.call(["open", file_path])

    elif sys.platform == "linux":
        try:
            subprocess.run(["xdg-open", file_path], check=True, stdout=subprocess.PIPE, stderr=subprocess.PIPE)
        except subprocess.CalledProcessError as e:
            # Si xdg-open produce un error, intenta cambiar temporalmente LD_LIBRARY_PATH y volver a intentar
            import TheKeyMachine.mods.reportMod as report

            report.report_detected_exception(e, context="open file with xdg-open")

            original_ld_path = os.environ.get("LD_LIBRARY_PATH", "")
            os.environ["LD_LIBRARY_PATH"] = "/usr/lib:/lib:/usr/local/lib"

            try:
                subprocess.run(["xdg-open", file_path], check=True, stdout=subprocess.PIPE, stderr=subprocess.PIPE)
            except subprocess.CalledProcessError as e:
                report.report_detected_exception(e, context="open file with modified LD_LIBRARY_PATH")
            finally:
                # Restaurar el valor original de LD_LIBRARY_PATH
                os.environ["LD_LIBRARY_PATH"] = original_ld_path
