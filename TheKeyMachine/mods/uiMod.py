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
import maya.mel as mel
import maya.OpenMayaUI as mui

try:
    from shiboken2 import wrapInstance
    from PySide2.QtWidgets import QDesktopWidget
    from PySide2 import QtCore, QtGui, QtWidgets
except ImportError:
    from shiboken6 import wrapInstance
    from PySide6.QtCore import QTimer
    from PySide6 import QtCore, QtGui, QtWidgets

try:
    from importlib import reload
except ImportError:
    from imp import reload
except ImportError:
    pass

import ssl

import TheKeyMachine.core.runtime_manager as runtime
import re
import os
import platform
import sys
import urllib.request
import urllib.parse
import shutil
from functools import partial

import TheKeyMachine.mods.generalMod as general
import TheKeyMachine.mods.keyToolsMod as keyTools
import TheKeyMachine.mods.mediaMod as media
import TheKeyMachine.mods.barMod as bar
import TheKeyMachine.mods.updater as updater
import TheKeyMachine.tools.colors as toolColors
import TheKeyMachine.tools.orbit.api as orbitApi
import TheKeyMachine.tools.attribute_switcher.api as attributeSwitcherApi
import TheKeyMachine.tools.selection_sets.api as selectionSetsApi

from TheKeyMachine.widgets import customDialogs, customWidgets as cw, util as wutil
from TheKeyMachine.mods import settingsMod as settings

mods = [general, keyTools, media, bar, customDialogs, cw, wutil, updater, settings, toolColors, orbitApi, attributeSwitcherApi, selectionSetsApi]

for m in mods:
    reload(m)

ORBIT_SETTINGS_NAMESPACE = orbitApi.ORBIT_SETTINGS_NAMESPACE
ATTRIBUTE_SWITCHER_SETTINGS_NAMESPACE = attributeSwitcherApi.ATTRIBUTE_SWITCHER_SETTINGS_NAMESPACE
SELECTION_SETS_SETTINGS_NAMESPACE = selectionSetsApi.SELECTION_SETS_SETTINGS_NAMESPACE

INSTALL_PATH = general.config["INSTALL_PATH"]
USER_FOLDER_PATH = general.config["USER_FOLDER_PATH"]


def orbit_window(*args, **kwargs):
    return orbitApi.orbit_window(*args, **kwargs)


def close_orbit_window(*args, **kwargs):
    return orbitApi.close_orbit_window(*args, **kwargs)


def bind_orbit_toolbar_button(*args, **kwargs):
    return orbitApi.bind_orbit_toolbar_button(*args, **kwargs)


def attribute_switcher_window(*args, **kwargs):
    return attributeSwitcherApi.attribute_switcher_window(*args, **kwargs)


def close_attribute_switcher_window(*args, **kwargs):
    return attributeSwitcherApi.close_attribute_switcher_window(*args, **kwargs)


def bind_attribute_switcher_toolbar_button(*args, **kwargs):
    return attributeSwitcherApi.bind_attribute_switcher_toolbar_button(*args, **kwargs)


def toggle_attribute_switcher_window(*args, **kwargs):
    return attributeSwitcherApi.toggle_attribute_switcher_window(*args, **kwargs)


def open_selection_set_creation_dialog(*args, **kwargs):
    return selectionSetsApi.open_selection_set_creation_dialog(*args, **kwargs)


def open_selection_sets_toolbar_action(*args, **kwargs):
    return selectionSetsApi.open_selection_sets_toolbar_action(*args, **kwargs)


def toggle_selection_sets_window(*args, **kwargs):
    return selectionSetsApi.toggle_selection_sets_window(*args, **kwargs)


def refresh_selection_sets_window(*args, **kwargs):
    return selectionSetsApi.refresh_selection_sets_window(*args, **kwargs)


def close_selection_sets_window(*args, **kwargs):
    return selectionSetsApi.close_selection_sets_window(*args, **kwargs)


def bind_selection_sets_toolbar_button(*args, **kwargs):
    return selectionSetsApi.bind_selection_sets_toolbar_button(*args, **kwargs)


class Color:
    def __init__(self, palette=None):
        self.color = palette or toolColors.UI_COLORS


# ________________________________________________ General  ______________________________________________________ #


def getImage(*args, image):
    img_dir = os.path.join(INSTALL_PATH, "TheKeyMachine/data/img/")

    # Ruta del archivo de configuración
    fullImgDir = os.path.join(img_dir, image)

    return fullImgDir

# ________________________________________________ Sync  ______________________________________________________ #


# Se usa en customGraph para la funcion de filtro

filterMode_sync_on_code = """

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
"""

filterMode_sync_off_code = """

global proc syncChannelBoxFcurveEd()
{

}
syncChannelBoxFcurveEd();

filterUIClearFilter graphEditor1OutlineEd;

"""


def filterMode_sync_on():
    mel.eval(filterMode_sync_on_code)


def filterMode_sync_off():
    mel.eval(filterMode_sync_off_code)


def customGraph_filter_mods(*args):
    # Get the current state of the modifiers
    mods = runtime.get_modifier_mask()
    shift_pressed = bool(mods & 1)

    if shift_pressed:
        filterMode_sync_off()
    else:
        filterMode_sync_on()


# ---------------------------------------------------- STARTUP SCRIPT ----------------------------------------------------------------------------


def check_userSetup():
    userSetupFile = os.path.join(os.getenv("MAYA_APP_DIR"), "scripts", "userSetup.py")

    startCode = "# start TheKeyMachine"

    try:
        with open(userSetupFile, "r") as input_file:
            lines = input_file.readlines()
            for line in lines:
                if line.strip() == startCode:
                    return True
    except IOError:
        pass

    return False


def install_userSetup(install=True):
    userSetupFile = os.path.join(os.getenv("MAYA_APP_DIR"), "scripts", "userSetup.py")

    cmds_import = "from maya import cmds\n"
    newUserSetup = ""
    startCode, endCode = "# start TheKeyMachine", "# end TheKeyMachine"

    try:
        with open(userSetupFile, "r") as input_file:
            lines = input_file.readlines()

            # Remove existing block between startCode and endCode
            inside_block = False
            for line in lines:
                if line == cmds_import:
                    cmds_import = ""
                if line.strip() == startCode:
                    inside_block = True
                if not inside_block:
                    newUserSetup += line
                if line.strip() == endCode:
                    inside_block = False

            # Ensure there's always a two-line gap at the end
            newUserSetup = newUserSetup.rstrip() + "\n\n"

    except IOError:
        newUserSetup = ""

    run_script = "import TheKeyMachine; TheKeyMachine.toggle()"
    tkm_run_code = (
        "{}\n\n".format(startCode)
        + "{0}".format(cmds_import)
        + "if not cmds.about(batch=True):\n"
        + '    cmds.evalDeferred(lambda: cmds.evalDeferred("{}", lowestPriority=True))\n\n'.format(run_script)
        + "{}".format(endCode)
    )

    if install:
        newUserSetup += tkm_run_code

    # Write the updated userSetup file
    with open(userSetupFile, "w") as output_file:
        output_file.write(newUserSetup)


# ---------------------------------------------------- UNINSTALL ---------------------------------------------------------------------------------


def uninstall():
    # Muestra un cuadro de diálogo para confirmar la desinstalación
    result = cmds.confirmDialog(
        title="Uninstall TheKeyMachine",
        message="Do you want to uninstall TheKeyMachine?",
        button=["Uninstall", "Cancel"],
        defaultButton="Uninstall",
        cancelButton="Cancel",
        dismissString="Cancel",
    )

    if result == "Uninstall":
        try:
            tkm_folder_path = (
                os.path.join(INSTALL_PATH, "TheKeyMachine")
                if INSTALL_PATH
                else os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
            )

            # Crear una carpeta llamada "uninstalled" dentro de TheKeyMachine si no existe
            uninstalled_folder_path = os.path.join(tkm_folder_path, "uninstalled")
            if not os.path.exists(uninstalled_folder_path):
                os.makedirs(uninstalled_folder_path)
            else:
                cmds.warning('"uninstalled" folder already exists inside "TheKeyMachine".')

            # obsolete - Lista de carpetas a eliminar dentro de TheKeyMachine. En Win hay problemas al descargar el modulo de pyarmor, por eso no se intenta borra ya que daría error
            if platform.system() == "Windows":
                if os.path.exists(tkm_folder_path):
                    shutil.rmtree(tkm_folder_path)
                else:
                    cmds.warning("TheKeyMachine folder not found")
            else:
                # Para Linux y Darwin (macOS), intenta eliminar toda la carpeta "TheKeyMachine"
                if os.path.exists(tkm_folder_path):
                    shutil.rmtree(tkm_folder_path)
                else:
                    cmds.warning("TheKeyMachine folder not found")

            # Elimina customGraph
            if cmds.columnLayout("customGraph_columnLayout", exists=True):
                cmds.deleteUI("customGraph_columnLayout")

            # Necesitamos retrasar la eliminacion del workspace para dar tiempo a parar el callback 'centrar toolbar'
            def remove_tkm_workspace():
                # Elimina el workspaceControl llamado "k" y "s""
                if cmds.workspaceControl("k", exists=True):
                    cmds.workspaceControl("k", e=True, fl=True)  # La hacemos flotante
                    cmds.workspaceLayoutManager(s=True)  # Salvar workspace
                    cmds.workspaceControl("k", e=True, close=True)  # Cerrar
                    cmds.deleteUI("k", control=True)
                else:
                    cmds.warning('The workspaceControl "k" does not exist.')

                if cmds.workspaceControl("s", exists=True):
                    cmds.deleteUI("s", control=True)
                else:
                    cmds.warning('The workspaceControl "s" does not exist.')

                cmds.warning("TheKeyMachine has been uninstalled")

            QTimer.singleShot(700, remove_tkm_workspace)

        except Exception as e:
            cmds.error(f"An error occurred during uninstallation: {e}")
    else:
        print("Uninstallation cancelled by user")


# ________________________________________________ Donate window  ______________________________________________________ #


def donate_window():
    from TheKeyMachine.widgets.customDialogs import QFlatConfirmDialog

    screen_width, screen_height = wutil.get_screen_resolution()

    msg = (
        (
            "<br><span style='font-size: 14px; color:#cccccc'>"
            "The development of TheKeyMachine is a big effort in terms of energy and time.<br><br>If you use this tool professionally or regularly, please try to make a donation.<br> This will greatly help the project grow and have continuity. Every small amount counts.<br>"
            "Thank you!<br><br><br>"
            "Support TheKeyMachine <a href='http://thekeymachine.xyz/donate.php' style='color:#86CDAD;'><br>http://thekeymachine.xyz/donate</a></span><br><br>"
        )
        if screen_width == 3840
        else (
            "<br><span style='font-size: 12px; color:#cccccc'>"
            "The development of TheKeyMachine is a big effort<br>in terms of time and energy.<br><br>If you use this tool professionally or regularly,<br>please try to make a donation.<br><br> This will greatly help the project grow<br> and have continuity. Every small amount counts.<br>"
            "Thank you!<br><br><br>"
            "Support TheKeyMachine <a href='http://thekeymachine.xyz/donate.php' style='color:#86CDAD;'><br>http://thekeymachine.xyz/donate</a></span><br><br>"
        )
    )

    # Convert a label-like hack in QFlatConfirmDialog to support link opening
    dlg = QFlatConfirmDialog(
        parent=None,
        window="Donate",
        title="",
        message=msg,
        icon=media.stripe_image,
        closeButton=True,
    )
    dlg.message_label.setOpenExternalLinks(True)
    dlg.exec_()


def about_window():
    dlg = customDialogs.TKMAboutDialog(parent=None)
    dlg.exec_()


def send_bug_report(name, email, explanation, script_error):
    url = ""

    # Obtener version de Python, OS y Maya
    python_version = sys.version
    os_version = platform.system()
    maya_version = cmds.about(version=True)
    tkm_version = general.get_thekeymachine_version()

    data = {
        "name": name,
        "email": email,
        "explanation": explanation,
        "script_error": script_error,
        "python_version": python_version,
        "os_version": os_version,
        "maya_version": maya_version,
        "tkm_version": tkm_version,
    }
    data = urllib.parse.urlencode(data).encode("utf-8")

    # Ruta al archivo .pem y creación del contexto SSL

    install_dir = os.path.join(INSTALL_PATH, "TheKeyMachine")
    cert_file_path = os.path.join(install_dir, "data/cert/thekeymachine.pem")
    context = ssl.create_default_context(cafile=cert_file_path)

    with urllib.request.urlopen(url, data, context=context) as response:
        response_data = response.read().decode("utf-8")
        if "success" in response_data:
            return True
        else:
            return False


def bug_report_window(*args):
    for widget in QtWidgets.QApplication.topLevelWidgets():
        if isinstance(widget, customDialogs.QFlatBugReportDialog):
            widget.close()
            widget.deleteLater()

    dlg = customDialogs.QFlatBugReportDialog(submit_callback=send_bug_report)
    dlg.show_centered()
    return dlg
