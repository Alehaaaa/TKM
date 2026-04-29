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

try:
    from PySide6 import QtCore
    from PySide6.QtCore import QTimer
except ImportError:
    from PySide2 import QtCore
    from PySide2.QtCore import QTimer

try:
    from importlib import reload
except ImportError:
    from imp import reload
except ImportError:
    pass


import TheKeyMachine.core.runtime_manager as runtime
import os
import platform
import shutil

import TheKeyMachine.mods.generalMod as general
import TheKeyMachine.mods.keyToolsMod as keyTools
import TheKeyMachine.mods.mediaMod as media
import TheKeyMachine.mods.barMod as bar
import TheKeyMachine.mods.reportMod as report
import TheKeyMachine.mods.updater as updater
from TheKeyMachine.core import selection_targets
import TheKeyMachine.tools.colors as toolColors
import TheKeyMachine.tools.orbit.api as orbitApi
import TheKeyMachine.tools.attribute_switcher.api as attributeSwitcherApi
import TheKeyMachine.tools.selection_sets.api as selectionSetsApi

from TheKeyMachine.widgets import customDialogs, customWidgets as cw, util as wutil
from TheKeyMachine.mods import settingsMod as settings

mods = [
    general,
    keyTools,
    media,
    bar,
    customDialogs,
    cw,
    wutil,
    updater,
    settings,
    report,
    toolColors,
    orbitApi,
    attributeSwitcherApi,
    selectionSetsApi,
]

for m in mods:
    reload(m)

ORBIT_SETTINGS_NAMESPACE = orbitApi.ORBIT_SETTINGS_NAMESPACE
ATTRIBUTE_SWITCHER_SETTINGS_NAMESPACE = attributeSwitcherApi.ATTRIBUTE_SWITCHER_SETTINGS_NAMESPACE
SELECTION_SETS_SETTINGS_NAMESPACE = selectionSetsApi.SELECTION_SETS_SETTINGS_NAMESPACE

INSTALL_PATH = general.config["INSTALL_PATH"]
USER_FOLDER_PATH = general.config["USER_FOLDER_PATH"]


orbit_window = orbitApi.orbit_window
close_orbit_window = orbitApi.close_orbit_window
bind_orbit_toolbar_button = orbitApi.bind_orbit_toolbar_button

attribute_switcher_window = attributeSwitcherApi.attribute_switcher_window
close_attribute_switcher_window = attributeSwitcherApi.close_attribute_switcher_window
bind_attribute_switcher_toolbar_button = attributeSwitcherApi.bind_attribute_switcher_toolbar_button
toggle_attribute_switcher_window = attributeSwitcherApi.toggle_attribute_switcher_window

open_selection_set_creation_dialog = selectionSetsApi.open_selection_set_creation_dialog
open_selection_sets_toolbar_action = selectionSetsApi.open_selection_sets_toolbar_action
toggle_selection_sets_window = selectionSetsApi.toggle_selection_sets_window
refresh_selection_sets_window = selectionSetsApi.refresh_selection_sets_window
close_selection_sets_window = selectionSetsApi.close_selection_sets_window
bind_selection_sets_toolbar_button = selectionSetsApi.bind_selection_sets_toolbar_button


class Color:
    def __init__(self, palette=None):
        self.color = palette or toolColors.UI_COLORS


# ________________________________________________ Sync  ______________________________________________________ #


# Se usa en customGraph para la funcion de filtro

filterMode_sync_on_code = """

global proc syncChannelBoxFcurveEd()
{{
    global string $gChannelBoxName;

    string $selAttrs[] = `selectedChannelBoxPlugs`;
    selectionConnection -e -clear {graph_editor_outliner};
    if (size($selAttrs) > 0) {{
        for ($attr in $selAttrs) {{
            selectionConnection -e -select $attr {graph_editor_outliner};
        }}
        filterUIFilterSelection graphEditor1OutlineEd "";
    }} else if (size($selAttrs) == 0) {{
        string $objects[] = `channelBoxObjects`;
        for ($obj in $objects) {{
            selectionConnection -e -select $obj {graph_editor_outliner};

        }}
        filterUIClearFilter graphEditor1OutlineEd;

    }}
}}
syncChannelBoxFcurveEd();
""".format(graph_editor_outliner=selection_targets.GRAPH_EDITOR_OUTLINER)

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
    link = "https://github.com/Alehaaaa/TKM"
    msg = (
        "The development of TheKeyMachine is a big effort in terms of time and energy.",
        "If you use this tool professionally or regularly, please try to make a donation.",
        "This will greatly help the project grow and have continuity. Every small amount counts.",
        "Thank you!",
        "",
        f"Support TheKeyMachine <a href='{link}' style='color:#86CDAD;'><br>{link}</a>",
    )

    dlg = customDialogs.QFlatConfirmDialog(
        parent=None,
        window="Donate",
        title="Donate to TheKeyMachine",
        message=msg,
        closeButton=True,
        icon="",
    )
    dlg.message_label.setTextFormat(QtCore.Qt.RichText)
    dlg.message_label.setTextInteractionFlags(QtCore.Qt.TextBrowserInteraction)
    dlg.message_label.setOpenExternalLinks(True)
    return dlg.exec_()


def about_window():
    dlg = customDialogs.TKMAboutDialog(parent=None)
    dlg.exec_()


send_bug_report = report.send_bug_report
report_detected_exception = report.report_detected_exception
safe_execute = report.safe_execute
wrap_callback = report.wrap_callback
install_bug_exception_handler = report.install_bug_exception_handler
uninstall_bug_exception_handler = report.uninstall_bug_exception_handler
bug_report_window = report.bug_report_window
