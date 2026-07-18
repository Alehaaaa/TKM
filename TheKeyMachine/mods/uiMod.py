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

from TheKeyMachine.core.Qt import QtCore

QTimer = QtCore.QTimer

try:
    from importlib import reload
except ImportError:
    from imp import reload
except ImportError:
    pass


import os
import platform
import shutil

import TheKeyMachine.mods.generalMod as general
import TheKeyMachine.mods.barMod as bar
import TheKeyMachine.mods.reportMod as report
import TheKeyMachine.mods.updater as updater
import TheKeyMachine.mods.selectionMod as selectionMod
from TheKeyMachine.data import colors as toolColors

from TheKeyMachine.widgets import customDialogs, customWidgets as cw, util as wutil
from TheKeyMachine.mods import settingsMod as settings

mods = [
    general,
    bar,
    customDialogs,
    cw,
    wutil,
    updater,
    settings,
    report,
    toolColors,
]

for m in mods:
    reload(m)

INSTALL_PATH = general.config["INSTALL_PATH"]
USER_FOLDER_PATH = general.config["USER_FOLDER_PATH"]


class Color:
    def __init__(self, palette=None):
        self.color = palette or toolColors.UI_COLORS


# ________________________________________________ Sync  ______________________________________________________ #


# Se usa en customGraph para la funcion de filtro

# ---------------------------------------------------- STARTUP SCRIPT ----------------------------------------------------------------------------


def _user_setup_path():
    maya_app_dir = os.getenv("MAYA_APP_DIR") or cmds.internalVar(userAppDir=True)
    return os.path.realpath(os.path.join(maya_app_dir, "scripts", "userSetup.py"))


def check_userSetup():
    user_setup_file = _user_setup_path()

    startCode = "# start TheKeyMachine"

    try:
        with open(user_setup_file, "r") as input_file:
            lines = input_file.readlines()
            for line in lines:
                if line.strip() == startCode:
                    return True
    except IOError:
        pass

    return False


def install_userSetup(install=True):
    user_setup_file = _user_setup_path()

    cmds_import = "from maya import cmds\n"
    newUserSetup = ""
    startCode, endCode = "# start TheKeyMachine", "# end TheKeyMachine"

    try:
        with open(user_setup_file, "r") as input_file:
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
    with open(user_setup_file, "w") as output_file:
        output_file.write(newUserSetup)


# ---------------------------------------------------- UNINSTALL ---------------------------------------------------------------------------------


def uninstall():
    # Muestra un cuadro de diálogo para confirmar la desinstalación
    from TheKeyMachine.tools import common as toolCommon

    toolCommon.finish_active_progress()
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


send_bug_report = report.send_bug_report
report_detected_exception = report.report_detected_exception
safe_execute = report.safe_execute
wrap_callback = report.wrap_callback
install_bug_exception_handler = report.install_bug_exception_handler
uninstall_bug_exception_handler = report.uninstall_bug_exception_handler
bug_report_window = report.bug_report_window
