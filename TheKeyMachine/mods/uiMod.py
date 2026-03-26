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

from TheKeyMachine.widgets import customDialogs, customWidgets as cw, util as wutil
from TheKeyMachine.mods import settingsMod as settings

mods = [general, keyTools, media, bar, customDialogs, cw, wutil, updater, settings]

for m in mods:
    reload(m)

INSTALL_PATH = general.config["INSTALL_PATH"]
USER_FOLDER_PATH = general.config["USER_FOLDER_PATH"]

ORBIT_SETTINGS_NAMESPACE = "orbit_window"
SELECTION_SETS_SETTINGS_NAMESPACE = "selection_sets_window"
AUTO_TRANSPARENCY_KEY = "orbit_auto_transparency"


def _auto_transparency_enabled():
    return settings.get_setting(AUTO_TRANSPARENCY_KEY, True, namespace=ORBIT_SETTINGS_NAMESPACE)


color_codes = {
    "_01": "#878A90",  # gris
    "_02": "#E6DC54",  # amarillo
    "_03": "#96BEC7",  # azul claro
    "_04": "#598693",  # azul oscuro
    "_05": "#8190B8",  # purple
    "_06": "#45C46B",  # verde
    "_07": "#C9844B",  # naranja
    "_08": "#AD4D4E",  # rojo oscuro
}

color_codes_hover = {
    "_01": "#A0A5AF",  # gris
    "_02": "#EEE3C2",  # amarillo
    "_03": "#ABD9E3",  # azul claro
    "_04": "#77ABBA",  # azul oscuro
    "_05": "#A1AFD9",  # purple
    "_06": "#83C4B3",  # verde
    "_07": "#D99993",  # rojo claro
    "_08": "#D46668",  # rojo oscuro
}


class Color:
    class ColorPalette:
        gray = "#444444"
        darkGray = "#3C3C3C"
        darkerGray = "#333333"
        lightGray = "#747474"
        white = "#e9edf2"
        darkWhite = "#cfd6df"
        cyan = "#58e1ff"
        orange = "#C9844B"
        yellow = "#d4d361"
        green = "#4fb68d"
        blue = "#58e1ff"
        red = "#AD4D4E"
        purple = "#8190B8"

        def __init__(self):
            for k, v in self.__class__.__dict__.items():
                if not k.startswith("_") and not callable(v):
                    setattr(self, k, v)

    def __init__(self):
        self._color = self.ColorPalette()

    @property
    def color(self):
        return self._color


# ________________________________________________ General  ______________________________________________________ #


def getImage(*args, image):
    img_dir = os.path.join(INSTALL_PATH, "TheKeyMachine/data/img/")

    # Ruta del archivo de configuración
    fullImgDir = os.path.join(img_dir, image)

    return fullImgDir


def toggle_shelf(*args):
    mel.eval("ToggleShelf")


def ref(value, widget):
    widget.setWindowOpacity(value)


def desactivado(*args):
    print("desactivado")


def reloadUI():
    cmds.evalDeferred("import TheKeyMachine.core.customGraph as cg; cg.createCustomGraph()", lowestPriority=True)


def getUiName():
    print(cmds.playblast(activeEditor=True))


def get_screen_resolution():
    app = QtWidgets.QApplication.instance()
    if not app:
        app = QtWidgets.QApplication([])

    try:
        # PySide6
        screen = app.primaryScreen()
        screen_rect = screen.geometry()
    except Exception:
        # PySide2
        desktop = QDesktopWidget()
        screen_rect = desktop.screenGeometry()

    screen_width = screen_rect.width()
    screen_height = screen_rect.height()

    return screen_width, screen_height


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
    mods = mel.eval("getModifiers")
    shift_pressed = bool(mods % 2)  # Check if Shift is pressed

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


# ___________________________________________________________ ORBIT _____________________________________________________________


def temp_pivot_action():
    bar.create_temp_pivot(False)


orbit_actions = {
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
    "temp_pivot": "temp_pivot_action",
    "copy_pose": "keyTools.copy_pose",
    "paste_pose": "keyTools.paste_pose",
    "copy_worldspace_single_frame": "bar.copy_worldspace_single_frame",
    "paste_worldspace_single_frame": "bar.paste_worldspace_single_frame",
}


orbit_action_icons = {
    "bar.isolate_master": media.isolate_image,
    "bar.align_selected_objects": media.align_menu_image,
    "bar.mod_tracer": media.tracer_menu_image,
    "keyTools.reset_objects_mods": media.reset_animation_image,
    "bar.deleteAnimation": media.delete_animation_image,
    "keyTools.selectOpposite": media.select_opposite_image,
    "keyTools.copyOpposite": media.copy_opposite_image,
    "keyTools.mirror": media.mirror_image,
    "keyTools.copy_animation": media.copy_animation_image,
    "keyTools.paste_animation": media.paste_animation_image,
    "keyTools.paste_insert_animation": media.paste_insert_animation_image,
    "bar.selectHierarchy": media.select_hierarchy_image,
    "keyTools.mod_link_objects": media.link_objects_image,
    "temp_pivot_action": media.temp_pivot_image,
    "keyTools.copy_pose": media.copy_pose_image,
    "keyTools.paste_pose": media.paste_pose_image,
    "bar.copy_worldspace_single_frame": media.worldspace_copy_frame_image,
    "bar.paste_worldspace_single_frame": media.worldspace_paste_frame_image,
}


LEGACY_ACTION_ALIASES = {"accion_temp_pivot": "temp_pivot"}


def normalize_action_identifier(action_identifier):
    return LEGACY_ACTION_ALIASES.get(action_identifier, action_identifier)


def execute_action(action_identifier):
    action_identifier = normalize_action_identifier(action_identifier)

    if action_identifier == "isolate_master":
        bar.isolate_master()
    elif action_identifier == "align_selected_objects":
        bar.align_selected_objects()
    elif action_identifier == "mod_tracer":
        bar.mod_tracer()
    elif action_identifier == "reset_objects_mods":
        keyTools.reset_objects_mods()
    elif action_identifier == "deleteAnimation":
        bar.mod_delete_animation()
    elif action_identifier == "selectOpposite":
        keyTools.selectOpposite()
    elif action_identifier == "copyOpposite":
        keyTools.copyOpposite()
    elif action_identifier == "mirror":
        keyTools.mirror()
    elif action_identifier == "copy_animation":
        keyTools.copy_animation()
    elif action_identifier == "paste_animation":
        keyTools.paste_animation()
    elif action_identifier == "paste_insert_animation":
        keyTools.paste_insert_animation()
    elif action_identifier == "copy_pose":
        keyTools.copy_pose()
    elif action_identifier == "paste_pose":
        keyTools.paste_pose()
    elif action_identifier == "selectHierarchy":
        bar.selectHierarchy()
    elif action_identifier == "mod_link_objects":
        keyTools.mod_link_objects()
    elif action_identifier == "temp_pivot":
        temp_pivot_action()
    elif action_identifier == "copy_worldspace_single_frame":
        bar.copy_worldspace_single_frame()
    elif action_identifier == "paste_worldspace_single_frame":
        bar.paste_worldspace_single_frame()
    else:
        pass


def save_orbit_button_config():
    config_path = USER_FOLDER_PATH + "/TheKeyMachine_user_data/tools/orbit/orbit.py"

    with open(config_path, "r") as file:
        lines = file.readlines()

    # Update the line that stores each button assignment
    for button_id, action_name in orbit_configuration.items():
        line_prefix = f"{button_id} = "
        line_index = next((i for i, line_value in enumerate(lines) if line_value.startswith(line_prefix)), None)

        if line_index is not None:
            lines[line_index] = f"{button_id} = '{action_name}'\n"
        else:
            # If the button is missing from the file, append it at the end
            lines.append(f"{button_id} = '{action_name}'\n")

    # Rewrite the file with the updated assignments
    with open(config_path, "w") as file:
        file.writelines(lines)


def load_orbit_configuration():
    config_path = USER_FOLDER_PATH + "/TheKeyMachine_user_data/tools/orbit/orbit.py"
    config_dir = os.path.dirname(config_path)
    orbit_configuration = {
        "button1": "reset_objects_mods",
        "button2": "deleteAnimation",
        "button3": "selectOpposite",
        "button4": "copyOpposite",
        "button5": "mirror",
        "button6": "selectHierarchy",
        "button7": "isolate_master",
    }

    # Ensure the directory exists
    if not os.path.exists(config_dir):
        os.makedirs(config_dir)

    try:
        with open(config_path, "r") as file:
            lines = file.readlines()
        for line in lines:
            if line.startswith("button"):
                key, value = line.split("=")
                key = key.strip()
                value = value.strip().strip("'")
                orbit_configuration[key] = value
    except FileNotFoundError:
        # Create the file with defaults if it does not exist
        with open(config_path, "w") as file:
            for key, value in orbit_configuration.items():
                file.write(f"{key} = '{value}'\n")

    return {k: normalize_action_identifier(v) for k, v in orbit_configuration.items()}


orbit_configuration = load_orbit_configuration()


class OrbitWindowBus(QtCore.QObject):
    stateChanged = QtCore.Signal(bool)


orbit_window_bus = OrbitWindowBus()


class ToolbarWindowToggle(QtCore.QObject):
    """Keeps a toolbar button in sync with a floating window."""

    def __init__(self, is_open_fn, open_fn, close_fn, state_signal=None, parent=None):
        super().__init__(parent)
        self._button = None
        self._syncing = False
        self._is_open_fn = is_open_fn
        self._open_fn = open_fn
        self._close_fn = close_fn
        if state_signal is not None:
            state_signal.connect(self._on_window_state_changed)

    def attach_button(self, button):
        if not button:
            return
        self._button = button
        self._button.setCheckable(True)
        self._syncing = True
        try:
            self._button.setChecked(bool(self._is_open_fn()))
        finally:
            self._syncing = False
        self._button.toggled.connect(self._on_button_toggled)
        self._button.destroyed.connect(self._on_button_destroyed)

    def _on_button_toggled(self, checked):
        if self._syncing:
            return
        if checked:
            self._open_fn()
        else:
            self._close_fn()

    def _on_button_destroyed(self, *_):
        if not self._button:
            return
        try:
            self._button.toggled.disconnect(self._on_button_toggled)
        except Exception:
            pass
        self._button = None

    def open(self):
        if not self._is_open_fn():
            self._open_fn()

    def close(self):
        if self._is_open_fn():
            self._close_fn()

    def toggle(self):
        if self._is_open_fn():
            self._close_fn()
        else:
            self._open_fn()

    def _on_window_state_changed(self, is_open):
        if not self._button:
            return
        self._syncing = True
        try:
            self._button.setChecked(bool(is_open))
        finally:
            self._syncing = False


def _emit_orbit_window_state(is_open):
    try:
        orbit_window_bus.stateChanged.emit(bool(is_open))
    except Exception:
        pass


def get_orbit_window():
    for widget in QtWidgets.QApplication.topLevelWidgets():
        if isinstance(widget, OrbitWindow) and wutil.is_valid_widget(widget):
            return widget
    return None


def is_orbit_window_open():
    win = get_orbit_window()
    return bool(win and win.isVisible())


def close_orbit_window():
    win = get_orbit_window()
    maya_window_closed = False
    if cmds.window("orbit_window", exists=True):
        cmds.deleteUI("orbit_window")
        maya_window_closed = True

    if win and wutil.is_valid_widget(win):
        win.close()
    elif maya_window_closed:
        _emit_orbit_window_state(False)


class OrbitWindowMixin:
    def _get_menu_items(self):
        import TheKeyMachine.mods.helperMod as helper

        return [
            (media.isolate_image, "Isolate", "isolate_master", getattr(helper, "isolate_tooltip_text", "Isolate")),
            (media.align_menu_image, "Align", "align_selected_objects", getattr(helper, "align_tooltip_text", "Align")),
            (media.tracer_menu_image, "Tracer", "mod_tracer", getattr(helper, "tracer_tooltip_text", "Tracer")),
            (media.reset_animation_image, "Reset Values", "reset_objects_mods", getattr(helper, "reset_values_tooltip_text", "Reset Values")),
            (
                media.delete_animation_image,
                "Delete Animation",
                "deleteAnimation",
                getattr(helper, "delete_animation_tooltip_text", "Delete Animation"),
            ),
            (media.select_opposite_image, "Select Opposite", "selectOpposite", getattr(helper, "select_opposite_tooltip_text", "Select Opposite")),
            (media.copy_opposite_image, "Copy Opposite", "copyOpposite", getattr(helper, "copy_opposite_tooltip_text", "Copy Opposite")),
            (media.mirror_image, "Mirror", "mirror", getattr(helper, "mirror_tooltip_text", "Mirror")),
            (media.copy_animation_image, "Copy Animation", "copy_animation", getattr(helper, "copy_animation_tooltip_text", "Copy Animation")),
            (media.paste_animation_image, "Paste Animation", "paste_animation", getattr(helper, "paste_animation_tooltip_text", "Paste Animation")),
            (
                media.paste_insert_animation_image,
                "Paste Insert Animation",
                "paste_insert_animation",
                getattr(helper, "paste_insert_animation_tooltip_text", "Paste Insert Animation"),
            ),
            (media.copy_pose_image, "Copy Pose", "copy_pose", getattr(helper, "copy_pose_tooltip_text", "Copy Pose")),
            (media.paste_pose_image, "Paste Pose", "paste_pose", getattr(helper, "copy_pose_tooltip_text", "Paste Pose")),
            (
                media.select_hierarchy_image,
                "Select Hierarchy",
                "selectHierarchy",
                getattr(helper, "select_hierarchy_tooltip_text", "Select Hierarchy"),
            ),
            (media.link_objects_image, "Copy/Paste Link", "mod_link_objects", getattr(helper, "link_objects_tooltip_text", "Link objects")),
            (media.temp_pivot_image, "Temp Pivot", "temp_pivot", getattr(helper, "temp_pivot_tooltip_text", "Temp Pivot")),
            (
                media.worldspace_copy_frame_image,
                "Copy World Space Current Frame",
                "copy_worldspace_single_frame",
                getattr(helper, "copy_worldspace_tooltip_text", "Copy World Space"),
            ),
            (
                media.worldspace_paste_frame_image,
                "Paste World Space Current Frame",
                "paste_worldspace_single_frame",
                getattr(helper, "paste_worldspace_tooltip_text", "Paste World Space"),
            ),
        ]

    def _setup_orbit_ui(self):
        global orbit_configuration
        use_shared_header = all(hasattr(self, name) for name in ("clear_header_right_widgets", "set_header_left_widget", "add_header_right_widget"))
        if use_shared_header:
            # Build header row using the shared close-button/header layout from QFlatCloseableFloatingWidget.
            self.clear_header_right_widgets()

            self.orbit_buttons = []
            self.button_widgets = {}

            self.button_flow_container = cw.QFlowContainer()
            self.button_flow_layout = cw.QFlowLayout(
                self.button_flow_container,
                margin=0,
                Hspacing=wutil.DPI(6),
                Vspacing=wutil.DPI(6),
                alignment=QtCore.Qt.AlignLeft,
            )
            self.button_flow_container.setLayout(self.button_flow_layout)
            self.set_header_left_widget(self.button_flow_container, stretch=1)

            orbit_configuration = load_orbit_configuration()

            button_keys = sorted(
                [k for k in orbit_configuration.keys() if k.startswith("button")],
                key=lambda x: int(x.replace("button", "")) if x.replace("button", "").isdigit() else 99,
            )

            for button_id in button_keys:
                action_name = orbit_configuration.get(button_id, "")
                self._create_orbit_button(button_id, action_name)

            self.add_button = cw.QFlatToolButton(
                text="+", tooltip_template="Add Tool Option", description="Assign an extra tool to your Orbit window."
            )
            self.add_button.setFixedSize(wutil.DPI(20), wutil.DPI(20))

            self.add_button.setStyleSheet(
                self.add_button.styleSheet()
                + " QToolButton { color: #888888; font-size: "
                + str(wutil.DPI(18))
                + "px; } QToolButton:hover { color: #ffffff; }"
            )
            self.add_button.clicked.connect(self._setup_add_button_menu)
            # Right-click should also open the add menu.
            self.add_button.setContextMenuPolicy(QtCore.Qt.CustomContextMenu)
            self.add_button.customContextMenuRequested.connect(lambda *_: self._setup_add_button_menu())
            self.add_header_right_widget(self.add_button, before_close=True)
            return

        # Fallback for older sessions where customDialogs wasn't reloaded yet.
        if hasattr(self, "top_bar_layout") and self.top_bar_layout:
            try:
                self.top_bar_layout.setParent(None)
                self.top_bar_layout.deleteLater()
            except Exception:
                pass

        self.orbit_layout = QtWidgets.QHBoxLayout()
        self.orbit_layout.setContentsMargins(0, 0, 0, 0)
        self.orbit_layout.setSpacing(wutil.DPI(15))
        self.mainLayout.addLayout(self.orbit_layout)

        self.orbit_buttons = []
        self.button_widgets = {}

        self.button_flow_container = cw.QFlowContainer()
        self.button_flow_layout = cw.QFlowLayout(
            self.button_flow_container,
            margin=0,
            Hspacing=wutil.DPI(6),
            Vspacing=wutil.DPI(6),
            alignment=QtCore.Qt.AlignLeft,
        )
        self.button_flow_container.setLayout(self.button_flow_layout)
        self.orbit_layout.addWidget(self.button_flow_container, 1)
        self.orbit_layout.addSpacing(wutil.DPI(8))

        orbit_configuration = load_orbit_configuration()

        button_keys = sorted(
            [k for k in orbit_configuration.keys() if k.startswith("button")],
            key=lambda x: int(x.replace("button", "")) if x.replace("button", "").isdigit() else 99,
        )

        for button_id in button_keys:
            action_name = orbit_configuration.get(button_id, "")
            self._create_orbit_button(button_id, action_name)

        self.separator = QtWidgets.QFrame()
        self.separator.setFrameShape(QtWidgets.QFrame.VLine)
        self.separator.setFrameShadow(QtWidgets.QFrame.Sunken)
        self.separator.setFixedSize(2, wutil.DPI(20))
        self.separator.setStyleSheet("QFrame { background-color: #3d3d3d; border: none; }")
        self.orbit_layout.addWidget(self.separator)

        self.add_button = cw.QFlatToolButton(text="+", tooltip_template="Add Tool Option", description="Assign an extra tool to your Orbit window.")
        self.add_button.setFixedSize(wutil.DPI(20), wutil.DPI(20))
        self.add_button.setStyleSheet(
            self.add_button.styleSheet()
            + " QToolButton { color: #888888; font-size: "
            + str(wutil.DPI(18))
            + "px; } QToolButton:hover { color: #ffffff; }"
        )
        self.add_button.clicked.connect(self._setup_add_button_menu)
        # Right-click should also open the add menu.
        self.add_button.setContextMenuPolicy(QtCore.Qt.CustomContextMenu)
        self.add_button.customContextMenuRequested.connect(lambda *_: self._setup_add_button_menu())
        self.orbit_layout.addWidget(self.add_button)

        self.close_button.setFixedSize(wutil.DPI(20), wutil.DPI(20))
        self.close_button.setParent(None)
        self.orbit_layout.addWidget(self.close_button)

    def _remove_from_flow_layout(self, widget):
        if not hasattr(self, "button_flow_layout"):
            return
        for index in range(self.button_flow_layout.count()):
            item = self.button_flow_layout.itemAt(index)
            if item and item.widget() is widget:
                removed = self.button_flow_layout.takeAt(index)
                if removed:
                    child = removed.widget()
                    if child:
                        child.setParent(None)
                break

    def _get_action_display_info(self, action_identifier):
        icon_path = orbit_action_icons.get(orbit_actions.get(action_identifier, ""), media.isolate_image)
        label = "Tool"
        tooltip_text = label

        for ic, lbl, action_name, tooltip in self._get_menu_items():
            if action_name == action_identifier:
                icon_path = ic
                label = lbl
                tooltip_text = tooltip or lbl
                break

        return icon_path, label, tooltip_text

    def _create_orbit_button(self, button_id, action_identifier):
        icon_path, label, tooltip_text = self._get_action_display_info(action_identifier)

        btn = cw.QFlatToolButton(icon=icon_path or None, tooltip_template=tooltip_text)
        btn.setFixedSize(wutil.DPI(26), wutil.DPI(26))
        btn.setIconSize(QtCore.QSize(wutil.DPI(20), wutil.DPI(20)))
        btn.clicked.connect(partial(execute_action, action_identifier))
        btn.setContextMenuPolicy(QtCore.Qt.CustomContextMenu)
        btn.customContextMenuRequested.connect(partial(self._setup_orbit_button_menu, btn, button_id))

        if hasattr(self, "button_flow_layout"):
            self.button_flow_layout.addWidget(btn)
        else:
            self.orbit_layout.insertWidget(max(self.orbit_layout.count() - 3, 0), btn)

        self.orbit_buttons.append(btn)
        self.button_widgets[button_id] = btn
        return btn

    def _update_button(self, btn, action_identifier, button_id):
        icon_path, label, tooltip_text = self._get_action_display_info(action_identifier)
        btn.setIcon(QtGui.QIcon(icon_path))
        btn.setToolTipData(text=label, tooltip_template=tooltip_text, description=tooltip_text)
        try:
            btn.clicked.disconnect()
        except Exception:
            pass
        btn.clicked.connect(partial(execute_action, action_identifier))
        if action_identifier in orbit_actions:
            orbit_configuration[button_id] = action_identifier
            save_orbit_button_config()

    def _setup_orbit_button_menu(self, btn, button_id, *_):
        menu = cw.OpenMenuWidget()
        action_group = QtGui.QActionGroup(menu)
        action_group.setExclusive(True)

        current_action = orbit_configuration.get(button_id, "")
        used_actions = {value for key, value in orbit_configuration.items() if key != button_id and key.startswith("button")}

        for icon_path, label, action_ident, tooltip_text in self._get_menu_items():
            action = menu.addAction(QtGui.QIcon(icon_path), label, tooltip_template=tooltip_text)
            action.setCheckable(True)
            action_group.addAction(action)

            if action_ident == current_action:
                action.setChecked(True)
                action.setEnabled(False)
            else:
                action.setChecked(False)
                if action_ident in used_actions:
                    action.setEnabled(False)
                else:
                    action.triggered.connect(partial(self._update_button, btn, action_ident, button_id))

        menu.addSeparator()
        remove_action = menu.addAction(QtGui.QIcon(media.close_image), "Remove this Button")

        def _remove_and_close():
            self._remove_button(button_id)
            menu.close()

        remove_action.triggered.connect(_remove_and_close)

        menu.exec_(QtGui.QCursor.pos())

    def _setup_add_button_menu(self, *_):
        menu = cw.OpenMenuWidget()
        assigned_actions = {value for key, value in orbit_configuration.items() if key.startswith("button")}

        for icon_path, label, action_ident, tooltip_text in self._get_menu_items():
            action = menu.addAction(QtGui.QIcon(icon_path), label, tooltip_template=tooltip_text)
            action.setCheckable(True)
            checked = action_ident in assigned_actions
            action.setChecked(checked)
            action.toggled.connect(partial(self._handle_add_action_toggle, action, action_ident))

        menu.exec_(QtGui.QCursor.pos())

    def _handle_add_action_toggle(self, action, action_identifier, checked):
        is_assigned = self._is_action_assigned(action_identifier)
        if checked:
            if not is_assigned:
                self._add_new_tool(action_identifier)
            else:
                action.blockSignals(True)
                action.setChecked(True)
                action.blockSignals(False)
        else:
            if is_assigned:
                self._remove_action_assignment(action_identifier)
            action.blockSignals(True)
            action.setChecked(self._is_action_assigned(action_identifier))
            action.blockSignals(False)

    def _is_action_assigned(self, action_identifier):
        return any(value == action_identifier for key, value in orbit_configuration.items() if key.startswith("button"))

    def _remove_action_assignment(self, action_identifier):
        for key, value in list(orbit_configuration.items()):
            if key.startswith("button") and value == action_identifier:
                self._remove_button(key)
                break

    def _add_new_tool(self, action_identifier):
        numeric_keys = [
            int(k.replace("button", "")) for k in orbit_configuration.keys() if k.startswith("button") and k.replace("button", "").isdigit()
        ]
        new_idx = max(numeric_keys + [0]) + 1
        button_id = f"button{new_idx}"
        orbit_configuration[button_id] = action_identifier
        save_orbit_button_config()
        self._create_orbit_button(button_id, action_identifier)

    def _remove_button(self, button_id):
        btn = self.button_widgets.pop(button_id, None)
        if button_id in orbit_configuration:
            del orbit_configuration[button_id]
            save_orbit_button_config()

        if btn:
            self._remove_from_flow_layout(btn)
            if btn in self.orbit_buttons:
                self.orbit_buttons.remove(btn)
            btn.deleteLater()


class OrbitWindow(customDialogs.QFlatCloseableFloatingWidget, OrbitWindowMixin):
    def __init__(self, parent=None, offset_x=0, offset_y=0, rebuild=False):
        super().__init__(popup=False, parent=parent)
        self.setObjectName("orbit_window")
        self.setWindowTitle("Orbit")

        self._setup_orbit_ui()
        self._hovered = False
        self._auto_transparency = _auto_transparency_enabled()

        self.fade_timer = QtCore.QTimer(self)
        self.fade_timer.setSingleShot(True)
        self.fade_timer.timeout.connect(self._apply_transparency)

        self.settings_timer = QtCore.QTimer(self)
        self.settings_timer.timeout.connect(self._check_settings)
        self.settings_timer.start(500)

        from TheKeyMachine.mods import settingsMod as settings

        saved_geom = settings.get_setting("orbit_geometry", namespace=ORBIT_SETTINGS_NAMESPACE)

        self.adjustSize()

        if saved_geom and len(saved_geom) == 4 and not rebuild:
            x, y, w, h = saved_geom
            self.setGeometry(x, y, w, h)
        elif saved_geom and len(saved_geom) >= 2:
            x, y = saved_geom[0], saved_geom[1]
            if rebuild:
                self.move(x, y)
            else:
                self.setGeometry(x, y, self.width(), self.height())
        else:
            if offset_x != 0 or offset_y != 0:
                cursor_pos = QtGui.QCursor.pos()
                self.move(cursor_pos + QtCore.QPoint(offset_x, offset_y))
            else:
                self.place_near_cursor()

        self.update_transparency_state(False)

    def _check_settings(self):
        new_state = _auto_transparency_enabled()
        if new_state != self._auto_transparency:
            self._auto_transparency = new_state
            self.update_transparency_state(self._hovered)

    def _apply_transparency(self):
        if self._hovered:
            return
        if self._auto_transparency:
            self.setWindowOpacity(0.45)
        else:
            self.setWindowOpacity(1.0)

    def enterEvent(self, event):
        super().enterEvent(event)
        self.update_transparency_state(True)

    def leaveEvent(self, event):
        super().leaveEvent(event)
        self.update_transparency_state(False)

    def showEvent(self, event):
        super().showEvent(event)
        self.update_transparency_state(self.rect().contains(self.mapFromGlobal(QtGui.QCursor.pos())))

    def update_transparency_state(self, hovered):
        self._hovered = hovered
        self.fade_timer.stop()
        if not self._auto_transparency:
            self.setWindowOpacity(1.0)
            return

        if hovered:
            self.setWindowOpacity(0.80)
        else:
            self.setWindowOpacity(0.80)
            self.fade_timer.start(800)

    def hideEvent(self, event):
        from TheKeyMachine.mods import settingsMod as settings

        settings.set_setting(
            "orbit_geometry",
            [self.pos().x(), self.pos().y(), self.width(), self.height()],
            namespace=ORBIT_SETTINGS_NAMESPACE,
        )
        super().hideEvent(event)

    def closeEvent(self, event):
        _emit_orbit_window_state(False)
        super().closeEvent(event)


def orbit_window(*args, offset_x=0, offset_y=0, rebuild=False, reuse_existing=False):
    existing_win = get_orbit_window()
    if reuse_existing and not rebuild and offset_x == 0 and offset_y == 0 and existing_win:
        if not existing_win.isVisible():
            existing_win.show()
        existing_win.raise_()
        existing_win.activateWindow()
        _emit_orbit_window_state(True)
        return existing_win

    if cmds.window("orbit_window", exists=True):
        cmds.deleteUI("orbit_window")

    parent = wrapInstance(int(mui.MQtUtil.mainWindow()), QtWidgets.QWidget)
    win = OrbitWindow(parent=parent, offset_x=offset_x, offset_y=offset_y, rebuild=rebuild)

    def _on_destroyed(*_):
        _emit_orbit_window_state(False)

    win.destroyed.connect(_on_destroyed)
    win.show()
    _emit_orbit_window_state(True)
    return win


orbit_toolbar_toggle = ToolbarWindowToggle(
    is_orbit_window_open,
    lambda: orbit_window(reuse_existing=True),
    close_orbit_window,
    orbit_window_bus.stateChanged,
)


def bind_orbit_toolbar_button(button):
    orbit_toolbar_toggle.attach_button(button)


def toggle_orbit_window():
    if orbit_toolbar_toggle:
        orbit_toolbar_toggle.toggle()
    else:
        if is_orbit_window_open():
            close_orbit_window()
        else:
            orbit_window(reuse_existing=True)


# ________________________________________________ Selection Sets Floating Window  ______________________________________ #


class SelectionSetsWindowBus(QtCore.QObject):
    stateChanged = QtCore.Signal(bool)


selection_sets_window_bus = SelectionSetsWindowBus()


def _emit_selection_sets_window_state(is_open):
    try:
        selection_sets_window_bus.stateChanged.emit(bool(is_open))
    except Exception:
        pass


def _resolve_toolbar_controller(controller=None):
    if controller:
        return controller
    try:
        from TheKeyMachine.core.toolbar import get_toolbar  # type: ignore
    except Exception:
        return None
    return get_toolbar()


def get_selection_sets_window():
    for widget in QtWidgets.QApplication.topLevelWidgets():
        if isinstance(widget, SelectionSetsWindow) and wutil.is_valid_widget(widget):
            return widget
    return None


def is_selection_sets_window_open():
    win = get_selection_sets_window()
    return bool(win and win.isVisible())


def close_selection_sets_window():
    win = get_selection_sets_window()
    if win and wutil.is_valid_widget(win):
        win.close()
    else:
        _emit_selection_sets_window_state(False)


def selection_sets_window(*args, controller=None, reuse_existing=True):
    controller = _resolve_toolbar_controller(controller)
    win = get_selection_sets_window()
    if reuse_existing and win and wutil.is_valid_widget(win):
        if not win.isVisible():
            win.show()
        win.raise_()
        win.activateWindow()
        _emit_selection_sets_window_state(True)
        return win

    parent = wrapInstance(int(mui.MQtUtil.mainWindow()), QtWidgets.QWidget)
    win = SelectionSetsWindow(controller=controller, parent=parent)

    def _on_destroyed(*_):
        _emit_selection_sets_window_state(False)

    win.destroyed.connect(_on_destroyed)
    win.show()
    _emit_selection_sets_window_state(True)
    return win


_selection_sets_open_fn = lambda: selection_sets_window(controller=None, reuse_existing=True)
_selection_sets_toolbar_toggle = ToolbarWindowToggle(
    is_selection_sets_window_open,
    lambda: _selection_sets_open_fn(),
    close_selection_sets_window,
    selection_sets_window_bus.stateChanged,
)


def toggle_selection_sets_window(controller=None):
    global _selection_sets_open_fn
    controller = _resolve_toolbar_controller(controller)
    if controller is not None:
        _selection_sets_open_fn = lambda: selection_sets_window(controller=controller, reuse_existing=True)
    if _selection_sets_toolbar_toggle:
        _selection_sets_toolbar_toggle.toggle()
    else:
        if is_selection_sets_window_open():
            close_selection_sets_window()
        else:
            selection_sets_window(controller=controller, reuse_existing=True)


def refresh_selection_sets_window():
    win = get_selection_sets_window()
    if win and wutil.is_valid_widget(win):
        win.refresh()


_selection_set_creation_dialog = None


class SelectionSetCreationDialog(customDialogs.QFlatCloseableFloatingWidget):
    def __init__(self, controller, parent=None):
        super().__init__(popup=False, parent=parent)
        self.controller = controller
        self.setObjectName("selection_set_creation_dialog")
        self.setWindowTitle("Create Selection Set")
        fixed_width = wutil.DPI(680)
        self.setMinimumWidth(fixed_width)
        self.setMaximumWidth(fixed_width)
        self.setMinimumHeight(wutil.DPI(120))

        self.flow_container = cw.QFlowContainer()
        self.flow_layout = cw.QFlowLayout(
            self.flow_container,
            margin=wutil.DPI(6),
            Hspacing=wutil.DPI(8),
            alignment=QtCore.Qt.AlignLeft,
        )
        self.flow_container.setMinimumHeight(wutil.DPI(40))
        self.flow_container.setSizePolicy(QtWidgets.QSizePolicy.Expanding, QtWidgets.QSizePolicy.Fixed)
        self._configure_top_row()
        self._build_controls()

    def _configure_top_row(self):
        close_btn = self.close_button
        while self.top_bar_layout.count():
            item = self.top_bar_layout.takeAt(0)
            widget = item.widget()
            if widget and widget is not close_btn:
                widget.setParent(None)
        self.top_bar_layout.addWidget(self.flow_container, 1)
        self.top_bar_layout.addWidget(close_btn, 0, QtCore.Qt.AlignRight)

    def _build_controls(self):
        self.name_field = QtWidgets.QLineEdit()
        self.name_field.setPlaceholderText("Set name and click a color")
        self.name_field.setMinimumWidth(wutil.DPI(200))
        self.name_field.setFixedHeight(wutil.DPI(30))
        self.name_field.setStyleSheet(
            """
            QLineEdit {
                background-color: #272727;
                border: 1px solid #434343;
                border-radius: 6px;
                color: #e0e0e0;
                padding: 4px 8px;
            }
            """
        )
        self.flow_layout.addWidget(self.name_field)

        self.group_combo = QtWidgets.QComboBox()
        self.group_combo.setFixedHeight(wutil.DPI(30))
        self.group_combo.setMinimumWidth(wutil.DPI(150))
        self.group_combo.setStyleSheet(
            """
            QComboBox {
                background-color: #2f2f2f;
                border-radius: 6px;
                border: 1px solid #434343;
                color: #d5d5d5;
                padding-left: 8px;
            }
            QComboBox::drop-down {
                border: none;
            }
            """
        )
        if hasattr(self.controller, "update_set_group_menu"):
            self.controller.update_set_group_menu(self.group_combo)
        self.flow_layout.addWidget(self.group_combo)

        self.create_group_button = cw.QFlatButton(text="New Group")
        self.create_group_button.clicked.connect(self._create_group)
        self.flow_layout.addWidget(self.create_group_button)

        for suffix, color_hex in color_codes.items():
            btn = self._create_color_button(suffix, color_hex)
            self.flow_layout.addWidget(btn)

    def _create_group(self):
        if self.controller:
            self.controller.create_new_set_group(self.name_field, self.group_combo)

    def _create_set(self, suffix):
        if self.controller:
            self.controller.create_new_set_and_update_buttons(suffix, self.name_field, self.group_combo)

    def _create_color_button(self, suffix, color_hex):
        icon = self._build_color_icon(color_hex)
        label = ""
        if hasattr(self.controller, "color_names"):
            label = self.controller.color_names.get(suffix, "")
        tooltip = f"Create {label or suffix.replace('_', '').title()} Set"
        btn = cw.QFlatToolButton(icon=icon, tooltip_template=tooltip)
        btn.clicked.connect(lambda _, s=suffix: self._create_set(s))
        return btn

    def _build_color_icon(self, color_hex):
        size = wutil.DPI(24)
        pixmap = QtGui.QPixmap(size, size)
        pixmap.fill(QtGui.QColor(color_hex))
        painter = QtGui.QPainter(pixmap)
        painter.setPen(QtGui.QPen(QtGui.QColor("#111111"), 2))
        painter.drawRoundedRect(1, 1, size - 2, size - 2, 6, 6)
        painter.end()
        return QtGui.QIcon(pixmap)


def open_selection_set_creation_dialog(controller=None, parent=None):
    global _selection_set_creation_dialog
    controller = _resolve_toolbar_controller(controller)
    if controller is None:
        return None
    if parent is None or not wutil.is_valid_widget(parent):
        parent = wrapInstance(int(mui.MQtUtil.mainWindow()), QtWidgets.QWidget)

    if _selection_set_creation_dialog and wutil.is_valid_widget(_selection_set_creation_dialog):
        _selection_set_creation_dialog.close()

    dialog = SelectionSetCreationDialog(controller=controller, parent=parent)

    def _clear_reference(*_):
        global _selection_set_creation_dialog
        _selection_set_creation_dialog = None

    dialog.destroyed.connect(_clear_reference)
    dialog.show()
    _selection_set_creation_dialog = dialog
    return dialog


def open_selection_set_members(set_name):
    parent = wrapInstance(int(mui.MQtUtil.mainWindow()), QtWidgets.QWidget)
    dlg = SelectionSetMembersDialog(set_name=set_name, parent=parent)
    dlg.show()
    return dlg


class SelectionSetMembersDialog(customDialogs.QFlatCloseableFloatingWidget):
    def __init__(self, set_name, parent=None):
        super().__init__(popup=False, parent=parent)
        self.setObjectName("selection_set_members_dialog")
        self.setWindowTitle("Set Items")
        self.setMinimumWidth(wutil.DPI(220))
        self.setMinimumHeight(wutil.DPI(260))
        self.set_name = set_name

        self.list_widget = QtWidgets.QListWidget()
        self.list_widget.setSelectionMode(QtWidgets.QAbstractItemView.ExtendedSelection)
        self.list_widget.itemSelectionChanged.connect(self._sync_selection)
        self.mainLayout.addWidget(self.list_widget, 1)

        reload_btn = cw.QFlatButton(text="Reload", icon_path=media.reload_image, highlight=True)
        reload_btn.clicked.connect(self.reload_members)
        self.mainLayout.addWidget(reload_btn)

        self.reload_members()

    def reload_members(self):
        members = cmds.sets(self.set_name, q=True) or []
        self.list_widget.blockSignals(True)
        self.list_widget.clear()
        for item in sorted(members):
            self.list_widget.addItem(item)
        self.list_widget.selectAll()
        self.list_widget.blockSignals(False)
        self._sync_selection()

    def _sync_selection(self):
        selected = [item.text() for item in self.list_widget.selectedItems()]
        if selected:
            cmds.select(selected, replace=True)
        else:
            cmds.select(clear=True)


class SelectionSetsWindow(customDialogs.QFlatCloseableFloatingWidget):
    def __init__(self, controller=None, parent=None):
        super().__init__(popup=False, parent=parent)
        self.controller = controller or _resolve_toolbar_controller(controller)
        self._creation_dialog = None
        self.setObjectName("selection_sets_window")
        self.setWindowTitle("Selection Sets")
        self.setMinimumWidth(wutil.DPI(360))
        self.setMinimumHeight(wutil.DPI(260))
        margins = self.mainLayout.contentsMargins()
        self.mainLayout.setContentsMargins(0, margins.top(), 0, margins.bottom())
        self._section_menu_targets = []
        self._build_ui()
        self._hovered = False
        self._auto_transparency = _auto_transparency_enabled()
        self.fade_timer = QtCore.QTimer(self)
        self.fade_timer.setSingleShot(True)
        self.fade_timer.timeout.connect(self._apply_transparency)
        self.settings_timer = QtCore.QTimer(self)
        self.settings_timer.timeout.connect(self._check_settings)
        self.settings_timer.start(500)
        self.adjustSize()
        self._restore_geometry()
        self.update_transparency_state(False)
        self.refresh()

    def _build_ui(self):
        use_shared_header = all(hasattr(self, name) for name in ("clear_header_right_widgets", "set_header_left_widget", "add_header_right_widget"))
        if use_shared_header:
            # Use the shared header layout from QFlatCloseableFloatingWidget:
            # left content (scroll) | separator | pinned tools section + close.
            self.clear_header_right_widgets()
            self.close_button.setToolTip("Close Select Sets")
            # Match Orbit: leave a small breathing room between the close button and the window edge.
            if hasattr(self, "header_right_layout") and self.header_right_layout:
                self.header_right_layout.setContentsMargins(0, 0, wutil.DPI(6), 0)

            self.scroll_area = QtWidgets.QScrollArea()
            self.scroll_area.setWidgetResizable(True)
            self.scroll_area.setFrameShape(QtWidgets.QFrame.NoFrame)
            # Let the window shrink; don't let scroll contents force a tall minimum.
            self.scroll_area.setMinimumHeight(0)
            self.scroll_area.setSizePolicy(QtWidgets.QSizePolicy.Expanding, QtWidgets.QSizePolicy.Expanding)
            self.set_header_left_widget(self.scroll_area, stretch=1)

            self.scroll_widget = QtWidgets.QWidget()
            self.scroll_widget.setMinimumSize(0, 0)
            self.scroll_layout = QtWidgets.QVBoxLayout(self.scroll_widget)
            self.scroll_layout.setContentsMargins(0, 0, 0, 0)
            self.scroll_layout.setSpacing(wutil.DPI(10))
            self.scroll_layout.addStretch()
            self.scroll_area.setWidget(self.scroll_widget)

            self.header_section = cw.QFlatSectionWidget(spacing=wutil.DPI(2), hiddeable=True)
            self.header_section.setSizePolicy(QtWidgets.QSizePolicy.Maximum, QtWidgets.QSizePolicy.Fixed)
            section_layout = self.header_section.layout()
            if section_layout:
                section_layout.setContentsMargins(0, 0, 0, 0)
                section_layout.setSpacing(0)
            self.header_section.setContentsMargins(0, 0, 0, 0)
            self.add_header_right_widget(self.header_section, before_close=True)

            self.add_button = self._create_header_button(
                media.add_selection_set_image,
                "Create Selection Set",
                self._open_set_creation_window,
                key="selection_sets_add_btn",
                default_visible=True,
            )
            self.refresh_button = self._create_header_button(
                media.reload_image,
                "Reload Selection Sets",
                self.refresh,
                key="selection_sets_refresh_btn",
                default_visible=False,
            )
            self.export_button = self._create_header_button(
                media.move_selection_set_image,
                "Export Selection Sets",
                self._export_sets,
                key="selection_sets_export_btn",
                default_visible=False,
            )
            self.import_button = self._create_header_button(
                media.selector_selection_set_image,
                "Import Selection Sets",
                self._import_sets,
                key="selection_sets_import_btn",
                default_visible=False,
            )
            self._install_header_context_menu()
            for btn in (self.add_button, self.refresh_button, self.export_button, self.import_button):
                self._register_section_menu_target(btn)
            return

        # Fallback for older sessions where customDialogs wasn't reloaded yet.
        self.top_bar_layout.setContentsMargins(0, 0, 0, 0)
        self.top_bar_layout.setSpacing(0)

        close_btn = self.close_button
        while self.top_bar_layout.count():
            item = self.top_bar_layout.takeAt(0)
            widget = item.widget()
            if widget and widget is not close_btn:
                widget.setParent(None)

        self.scroll_area = QtWidgets.QScrollArea()
        self.scroll_area.setWidgetResizable(True)
        self.scroll_area.setFrameShape(QtWidgets.QFrame.NoFrame)
        self.scroll_area.setMinimumHeight(0)
        self.scroll_area.setSizePolicy(QtWidgets.QSizePolicy.Expanding, QtWidgets.QSizePolicy.Expanding)
        self.top_bar_layout.addWidget(self.scroll_area)

        self.scroll_widget = QtWidgets.QWidget()
        self.scroll_widget.setMinimumSize(0, 0)
        self.scroll_layout = QtWidgets.QVBoxLayout(self.scroll_widget)
        self.scroll_layout.setContentsMargins(0, 0, 0, 0)
        self.scroll_layout.setSpacing(wutil.DPI(10))
        self.scroll_layout.addStretch()
        self.scroll_area.setWidget(self.scroll_widget)

        self.header_spacer = QtWidgets.QWidget()
        self.header_spacer.setMinimumWidth(wutil.DPI(90))
        spacer_layout = QtWidgets.QHBoxLayout(self.header_spacer)
        spacer_layout.setContentsMargins(0, 0, 0, 0)
        spacer_layout.setSpacing(0)
        spacer_layout.addStretch(1)
        self.top_bar_layout.addWidget(self.header_spacer, 1)

        self.header_separator = QtWidgets.QFrame()
        self.header_separator.setFrameShape(QtWidgets.QFrame.VLine)
        self.header_separator.setFrameShadow(QtWidgets.QFrame.Plain)
        self.header_separator.setStyleSheet("background-color: #1f1f1f;")
        self.header_separator.setFixedWidth(max(1, wutil.DPI(1)))
        self.top_bar_layout.addWidget(self.header_separator)

        self.header_controls_container = QtWidgets.QWidget()
        self.header_controls_container.setSizePolicy(QtWidgets.QSizePolicy.Expanding, QtWidgets.QSizePolicy.Expanding)
        controls_layout = QtWidgets.QHBoxLayout(self.header_controls_container)
        controls_layout.setContentsMargins(0, 0, wutil.DPI(6), 0)
        controls_layout.setSpacing(max(1, wutil.DPI(2)))
        controls_layout.setAlignment(QtCore.Qt.AlignRight | QtCore.Qt.AlignVCenter)

        self.header_section = cw.QFlatSectionWidget(spacing=wutil.DPI(2), hiddeable=True)
        self.header_section.setSizePolicy(QtWidgets.QSizePolicy.Maximum, QtWidgets.QSizePolicy.Fixed)
        section_layout = self.header_section.layout()
        if section_layout:
            section_layout.setContentsMargins(0, 0, 0, 0)
            section_layout.setSpacing(0)
        self.header_section.setContentsMargins(0, 0, 0, 0)
        controls_layout.addWidget(self.header_section, 0, QtCore.Qt.AlignRight)
        close_btn.setToolTip("Close Select Sets")
        controls_layout.addWidget(close_btn, 0, QtCore.Qt.AlignRight)
        self.top_bar_layout.addWidget(self.header_controls_container, 0)

        self.add_button = self._create_header_button(
            media.add_selection_set_image,
            "Create Selection Set",
            self._open_set_creation_window,
            key="selection_sets_add_btn",
            default_visible=True,
        )
        self.refresh_button = self._create_header_button(
            media.reload_image,
            "Reload Selection Sets",
            self.refresh,
            key="selection_sets_refresh_btn",
            default_visible=False,
        )
        self.export_button = self._create_header_button(
            media.move_selection_set_image,
            "Export Selection Sets",
            self._export_sets,
            key="selection_sets_export_btn",
            default_visible=False,
        )
        self.import_button = self._create_header_button(
            media.selector_selection_set_image,
            "Import Selection Sets",
            self._import_sets,
            key="selection_sets_import_btn",
            default_visible=False,
        )
        self._install_header_context_menu()
        for btn in (self.add_button, self.refresh_button, self.export_button, self.import_button):
            self._register_section_menu_target(btn)

    def _create_header_button(self, icon, tooltip, callback, key, default_visible):
        btn = cw.QFlatToolButton(icon=icon, tooltip_template=tooltip)
        btn.setFixedSize(wutil.DPI(26), wutil.DPI(26))
        btn.setIconSize(QtCore.QSize(wutil.DPI(20), wutil.DPI(20)))
        btn.clicked.connect(callback)
        if hasattr(self, "header_section") and self.header_section:
            self.header_section.addWidget(
                btn,
                label=tooltip,
                key=key,
                default_visible=default_visible,
                description=tooltip,
                tooltip_template=tooltip,
            )
        return btn

    def _install_header_context_menu(self):
        # Reset previously installed filters (if any) before wiring new targets
        for target in getattr(self, "_section_menu_targets", []):
            if target:
                target.removeEventFilter(self)
        self._section_menu_targets = []
        self._register_section_menu_target(self.header_section)
        self._register_section_menu_target(self.header_right_container)
        self._register_section_menu_target(self.close_button)

    def _register_section_menu_target(self, widget):
        if not widget:
            return
        widget.setContextMenuPolicy(QtCore.Qt.CustomContextMenu)
        widget.customContextMenuRequested.connect(self._open_section_menu)
        widget.installEventFilter(self)
        self._section_menu_targets.append(widget)

    def _open_section_menu(self, *_):
        menu_fn = getattr(self.header_section, "_show_menu", None)
        if callable(menu_fn):
            menu_fn()

    def eventFilter(self, obj, event):
        if event.type() == QtCore.QEvent.ContextMenu and obj in getattr(self, "_section_menu_targets", []):
            self._open_section_menu()
            return True
        return super().eventFilter(obj, event)

    def _open_set_creation_window(self):
        controller = self.controller or _resolve_toolbar_controller()
        if controller:
            open_selection_set_creation_dialog(controller=controller, parent=self)

    def _open_menu(self):
        menu = cw.OpenMenuWidget()
        export_action = menu.addAction("Export Sets")
        export_action.triggered.connect(self._export_sets)
        import_action = menu.addAction("Import Sets")
        import_action.triggered.connect(self._import_sets)
        menu.exec_(QtGui.QCursor.pos())

    def _export_sets(self):
        controller = self.controller or _resolve_toolbar_controller()
        if controller and self._has_exportable_sets(controller):
            controller.export_sets()

    def _import_sets(self):
        controller = self.controller or _resolve_toolbar_controller()
        if controller:
            controller.import_sets()

    def _has_exportable_sets(self, controller=None):
        controller = controller or self.controller or _resolve_toolbar_controller()
        if controller is None:
            return False
        set_groups = controller.get_set_groups()
        for set_group in set_groups:
            sub_sets = cmds.sets(set_group, q=True) or []
            for subset in sub_sets:
                if cmds.objExists(subset):
                    return True
        wutil.make_inViewMessage("No sets to export")
        return False

    def _check_settings(self):
        new_state = _auto_transparency_enabled()
        if new_state != self._auto_transparency:
            self._auto_transparency = new_state
            self.update_transparency_state(self._hovered)

    def _apply_transparency(self):
        if self._hovered:
            return
        if self._auto_transparency:
            self.setWindowOpacity(0.45)
        else:
            self.setWindowOpacity(1.0)

    def enterEvent(self, event):
        super().enterEvent(event)
        self.update_transparency_state(True)

    def leaveEvent(self, event):
        super().leaveEvent(event)
        self.update_transparency_state(False)

    def showEvent(self, event):
        super().showEvent(event)
        self.update_transparency_state(self.rect().contains(self.mapFromGlobal(QtGui.QCursor.pos())))

    def update_transparency_state(self, hovered):
        self._hovered = hovered
        self.fade_timer.stop()
        if not self._auto_transparency:
            self.setWindowOpacity(1.0)
            return

        if hovered:
            self.setWindowOpacity(0.80)
        else:
            self.setWindowOpacity(0.80)
            self.fade_timer.start(800)

    def _restore_geometry(self):
        saved_geom = settings.get_setting(
            "selection_sets_geometry",
            namespace=SELECTION_SETS_SETTINGS_NAMESPACE,
        )
        if not saved_geom:
            return
        if len(saved_geom) == 4:
            x, y, w, h = saved_geom
            self.setGeometry(x, y, w, h)
        elif len(saved_geom) >= 2:
            self.move(saved_geom[0], saved_geom[1])

    def hideEvent(self, event):
        settings.set_setting(
            "selection_sets_geometry",
            [self.pos().x(), self.pos().y(), self.width(), self.height()],
            namespace=SELECTION_SETS_SETTINGS_NAMESPACE,
        )
        super().hideEvent(event)

    def closeEvent(self, event):
        _emit_selection_sets_window_state(False)
        super().closeEvent(event)

    def refresh(self):
        self._clear_scroll()
        controller = self.controller or _resolve_toolbar_controller()
        if controller is None:
            self._add_empty_state("Toolbar not available.")
            return

        sel_root = "TheKeyMachine_SelectionSet"
        set_groups = controller.get_set_groups()
        if not set_groups:
            self._add_empty_state("Create your first selection set from the toolbar button.")
            return

        set_groups.sort(key=lambda g: (g != "main_setgroup", g))

        for set_group in set_groups:
            group_widget = self._build_group_section(controller, set_group, set_groups, sel_root)
            if group_widget:
                self.scroll_layout.insertWidget(self.scroll_layout.count() - 1, group_widget)

    def _clear_scroll(self):
        while self.scroll_layout.count() > 1:
            item = self.scroll_layout.takeAt(0)
            widget = item.widget()
            if widget:
                widget.setParent(None)
                widget.deleteLater()

    def _add_empty_state(self, message):
        # Intentionally no placeholder widget: keep the layout clean when empty.
        return

    def _build_group_section(self, controller, set_group, all_groups, sel_root):
        sub_sets = cmds.sets(set_group, q=True) or []
        group_widget = QtWidgets.QFrame()
        group_layout = QtWidgets.QVBoxLayout(group_widget)
        group_layout.setContentsMargins(0, 0, 0, 0)
        group_layout.setSpacing(wutil.DPI(6))

        header_button = QtWidgets.QPushButton(set_group.replace("_setgroup", ""))
        header_button.setCursor(QtCore.Qt.PointingHandCursor)
        header_button.clicked.connect(lambda _, sg=set_group: controller.toggle_setgroup_visibility(sg))
        header_button.setContextMenuPolicy(QtCore.Qt.CustomContextMenu)
        header_button.customContextMenuRequested.connect(lambda *_: self._show_group_menu(controller, set_group))

        hidden = True
        for subset in sub_sets:
            if cmds.objExists(subset) and not cmds.getAttr(f"{subset}.hidden"):
                hidden = False
                break

        text_color = "#636363" if hidden else "#66949d"
        bg_color = "#393939" if hidden else "#292929"
        header_button.setStyleSheet(
            "QPushButton {color: %s; background-color: %s; border-radius: 6px; border: 1px solid #1f1f1f; font-weight: bold;}"
            % (text_color, bg_color)
        )
        group_layout.addWidget(header_button)

        flow_container = QtWidgets.QWidget()
        flow_layout = cw.QFlowLayout(flow_container, margin=0, Hspacing=wutil.DPI(6), Vspacing=wutil.DPI(6), alignment=QtCore.Qt.AlignLeft)

        for subset in sorted(sub_sets, key=lambda s: (s.split("_")[-1], s)):
            if not cmds.objExists(subset):
                continue
            if cmds.getAttr(f"{subset}.hidden"):
                continue
            button = self._create_set_button(controller, subset, all_groups, sel_root)
            if button:
                flow_layout.addWidget(button)

        if flow_layout.count() == 0:
            placeholder = QtWidgets.QLabel("No visible sets")
            placeholder.setStyleSheet("color: #777777;")
            flow_layout.addWidget(placeholder)

        group_layout.addWidget(flow_container)
        return group_widget

    def _create_set_button(self, controller, subset, all_groups, sel_root):
        split_name = subset.split("_")
        if len(split_name) < 3:
            return None
        color_suffix = split_name[-1]
        set_name = "_".join(split_name[:-2])

        button = QtWidgets.QPushButton(set_name)
        button.setCursor(QtCore.Qt.PointingHandCursor)
        button.clicked.connect(lambda _, s=subset: controller.handle_set_selection(s, False, False))
        button.setContextMenuPolicy(QtCore.Qt.CustomContextMenu)
        button.customContextMenuRequested.connect(lambda *_: self._show_set_menu(controller, subset, all_groups, sel_root))

        color = color_codes.get(f"_{color_suffix}", "#333333")
        hover = color_codes_hover.get(f"_{color_suffix}", "#454545")
        button.setStyleSheet(
            """
            QPushButton {
                color: #1a1a1a;
                background-color: %s;
                border-radius: 6px;
                border: 1px solid #1f1f1f;
                padding: %dpx;
                font-weight: bold;
            }
            QPushButton:hover {
                background-color: %s;
            }
            """
            % (color, wutil.DPI(6), hover)
        )
        return button

    def _show_group_menu(self, controller, set_group):
        menu = cw.OpenMenuWidget()
        if set_group != "main_setgroup":
            rename_action = menu.addAction("Rename Group")
            rename_action.triggered.connect(lambda: controller.change_setgroup_name_window(set_group))
            menu.addSeparator()

        export_action = menu.addAction("Export Group")
        export_action.triggered.connect(lambda: controller.export_single_subgroup(set_group))
        delete_action = menu.addAction("Delete Group")
        delete_action.triggered.connect(lambda: controller.remove_set_group_and_update_buttons(set_group))
        menu.exec_(QtGui.QCursor.pos())

    def _show_set_menu(self, controller, subset, all_groups, sel_root):
        menu = cw.OpenMenuWidget()
        menu.addAction(QtGui.QIcon(media.add_to_selection_set_image), "Add Selection").triggered.connect(
            lambda: controller.add_selection_to_set(subset)
        )
        menu.addAction(QtGui.QIcon(media.remove_from_selection_set_image), "Remove Selection").triggered.connect(
            lambda: controller.remove_selection_from_set(subset)
        )
        menu.addSeparator()

        color_menu = cw.OpenMenuWidget("Change Color")
        color_menu_action = menu.addMenu(color_menu)
        for suffix, label in controller.color_names.items():
            action = color_menu.addAction(label)
            action.triggered.connect(lambda _, s=subset, suf=suffix: controller.set_set_color(s, suf))

        menu.addSeparator()
        menu.addAction(QtGui.QIcon(media.rename_selection_set_image), "Rename Set").triggered.connect(
            lambda: controller.change_set_name_window(subset, subset.rsplit("_", 1)[0])
        )
        menu.addAction(QtGui.QIcon(media.remove_selection_set_image), "Delete Set").triggered.connect(
            lambda: controller.remove_set_and_update_buttons(subset, subset.rsplit("_", 2)[-2] + "_setgroup")
        )
        menu.addSeparator()
        menu.addAction(QtGui.QIcon(media.selector_selection_set_image), "Selector").triggered.connect(lambda: open_selection_set_members(subset))

        move_menu = cw.OpenMenuWidget("Move To ...")
        menu.addMenu(move_menu)
        for group in all_groups:
            action = move_menu.addAction(group.replace("_setgroup", ""))
            action.setEnabled(group != subset.rsplit("_", 2)[-2] + "_setgroup")
            action.triggered.connect(lambda _, s=subset, g=group: controller.move_set_to_setgroup(s, g))

        menu.exec_(QtGui.QCursor.pos())


def bind_selection_sets_toolbar_button(button, controller=None):
    global _selection_sets_open_fn
    controller = _resolve_toolbar_controller(controller)
    if controller is not None:
        _selection_sets_open_fn = lambda: selection_sets_window(controller=controller, reuse_existing=True)
    if button:
        _selection_sets_toolbar_toggle.attach_button(button)


# ________________________________________________ Donate window  ______________________________________________________ #


def donate_window():
    from TheKeyMachine.widgets.customDialogs import QFlatConfirmDialog

    screen_width, screen_height = general.get_screen_resolution()

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
        icon=media.getImage("stripe.png"),
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
