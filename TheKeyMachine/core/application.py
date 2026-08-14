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

from maya import cmds
import json
import shutil
import subprocess
import os
import sys


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
    return os.path.join(INSTALL_PATH, "TheKeyMachine", "data", "icons", "tkm_node.png")


def get_tool_data_path(tool_name, filename=None):
    """Generic factory for tool-specific user data paths."""
    folder = os.path.join(USER_FOLDER_PATH, "TheKeyMachine_user_data/tools", tool_name)
    if filename:
        return os.path.join(folder, filename)
    return folder


# ------------------------------------------------------------------------


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
        import TheKeyMachine.tools.bug_report.controller as report

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
            import TheKeyMachine.tools.bug_report.controller as report

            report.report_detected_exception(e, context="open file")

    elif sys.platform == "darwin":
        subprocess.call(["open", file_path])

    elif sys.platform == "linux":
        try:
            subprocess.run(["xdg-open", file_path], check=True, stdout=subprocess.PIPE, stderr=subprocess.PIPE)
        except subprocess.CalledProcessError as e:
            # Si xdg-open produce un error, intenta cambiar temporalmente LD_LIBRARY_PATH y volver a intentar
            import TheKeyMachine.tools.bug_report.controller as report

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


def _tkm_folder_path():
    if INSTALL_PATH:
        return os.path.join(INSTALL_PATH, "TheKeyMachine")
    return os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))


def _backup_uninstalled_marker(tkm_folder_path):
    """Create the "uninstalled" marker folder inside TheKeyMachine, if missing."""
    uninstalled_folder_path = os.path.join(tkm_folder_path, "uninstalled")
    if os.path.exists(uninstalled_folder_path):
        cmds.warning('"uninstalled" folder already exists inside "TheKeyMachine".')
        return
    os.makedirs(uninstalled_folder_path)


def _remove_tkm_install(tkm_folder_path):
    if not os.path.exists(tkm_folder_path):
        cmds.warning("TheKeyMachine folder not found")
        return
    shutil.rmtree(tkm_folder_path)


def _remove_tkm_workspace_controls():
    """Close and delete TheKeyMachine's workspace controls ("k" the toolbar, "s" the search panel)."""
    for control_name in ("k", "s"):
        if not cmds.workspaceControl(control_name, exists=True):
            cmds.warning('The workspaceControl "{}" does not exist.'.format(control_name))
            continue
        if control_name == "k":
            cmds.workspaceControl(control_name, edit=True, floating=True)
            cmds.workspaceLayoutManager(save=True)
            cmds.workspaceControl(control_name, edit=True, close=True)
        cmds.deleteUI(control_name, control=True)

    cmds.warning("TheKeyMachine has been uninstalled")


def uninstall():
    from TheKeyMachine.core.Qt import QtCore
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

    if result != "Uninstall":
        print("Uninstallation cancelled by user")
        return

    try:
        tkm_folder_path = _tkm_folder_path()
        _backup_uninstalled_marker(tkm_folder_path)
        _remove_tkm_install(tkm_folder_path)
        # Remove the auto-launch block from userSetup.py so Maya doesn't try to
        # import TheKeyMachine on next startup against a folder that no longer exists.
        install_userSetup(install=False)
        # Delay the workspace teardown to give the "recenter toolbar" callback time to stop.
        QtCore.QTimer.singleShot(700, _remove_tkm_workspace_controls)
    except Exception as e:
        cmds.error(f"An error occurred during uninstallation: {e}")
