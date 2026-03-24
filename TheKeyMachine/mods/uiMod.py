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
    "paste_worldspace_single_frame": "bar.paste_worldspace_single_frame",
}


iconos_acciones = {
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
    "accion_temp_pivot": media.temp_pivot_image,
    "keyTools.copy_pose": media.copy_pose_image,
    "keyTools.paste_pose": media.paste_pose_image,
    "bar.copy_worldspace_single_frame": media.worldspace_copy_frame_image,
    "bar.paste_worldspace_single_frame": media.worldspace_paste_frame_image,
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
        bar.mod_delete_animation()
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
        "button7": "isolate_master",
    }

    # Crear el directorio si no existe
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
                configuracion_orbit[key] = value
    except FileNotFoundError:
        # Crear el archivo si no existe
        with open(config_path, "w") as file:
            for key, value in configuracion_orbit.items():
                file.write(f"{key} = '{value}'\n")

    return configuracion_orbit


configuracion_orbit = leer_configuracion_orbit()


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
            (media.paste_animation_image, "Paste Animation", "paste_animation", getattr(helper, "copy_animation_tooltip_text", "Paste Animation")),
            (
                media.paste_insert_animation_image,
                "Paste Insert Animation",
                "paste_insert_animation",
                getattr(helper, "copy_animation_tooltip_text", "Paste Insert Animation"),
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
            (media.temp_pivot_image, "Temp Pivot", "accion_temp_pivot", getattr(helper, "temp_pivot_tooltip_text", "Temp Pivot")),
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

        if hasattr(self, "top_bar_layout") and self.top_bar_layout.parentWidget() == self:
            self.top_bar_layout.setParent(None)
            self.top_bar_layout.deleteLater()

        self.orbit_layout = QtWidgets.QHBoxLayout()
        self.orbit_layout.setContentsMargins(0, 0, 0, 0)
        self.orbit_layout.setSpacing(wutil.DPI(15))

        self.mainLayout.addLayout(self.orbit_layout)

        self.botones = []
        configuracion_orbit = leer_configuracion_orbit()

        button_keys = sorted(
            [k for k in configuracion_orbit.keys() if k.startswith("button")],
            key=lambda x: int(x.replace("button", "")) if x.replace("button", "").isdigit() else 99,
        )

        for button_id in button_keys:
            action_name = configuracion_orbit.get(button_id, "")
            icon_path = iconos_acciones.get(acciones.get(action_name, ""), media.isolate_image)

            label = "Tool"
            tooltip_text = label
            for ic, lbl, a, tt in self._get_menu_items():
                if a == action_name:
                    label = lbl
                    tooltip_text = tt
                    break

            btn = cw.QFlatToolButton(icon=icon_path or None, tooltip_template=tooltip_text)

            btn.setFixedSize(wutil.DPI(26), wutil.DPI(26))
            btn.setIconSize(QtCore.QSize(wutil.DPI(20), wutil.DPI(20)))

            btn.clicked.connect(partial(ejecutar_accion, action_name))

            btn.setContextMenuPolicy(QtCore.Qt.CustomContextMenu)
            btn.customContextMenuRequested.connect(lambda pos: self._setup_orbit_button_menu(btn, button_id))

            self.orbit_layout.addWidget(btn)
            self.botones.append(btn)

        separator = QtWidgets.QFrame()
        separator.setFrameShape(QtWidgets.QFrame.VLine)
        separator.setFrameShadow(QtWidgets.QFrame.Sunken)
        separator.setFixedSize(2, wutil.DPI(20))
        separator.setStyleSheet("QFrame { background-color: #3d3d3d; border: none; }")
        self.orbit_layout.addWidget(separator)

        self.add_button = cw.QFlatToolButton(text="+", tooltip_template="Add Tool Option", description="Assign an extra tool to your Orbit window.")
        self.add_button.setFixedSize(wutil.DPI(20), wutil.DPI(20))

        self.add_button.setStyleSheet(
            self.add_button.styleSheet()
            + " QToolButton { color: #888888; font-size: "
            + str(wutil.DPI(18))
            + "px; } QToolButton:hover { color: #ffffff; }"
        )
        self.add_button.clicked.connect(self._setup_add_button_menu)

        self.orbit_layout.addWidget(self.add_button)
        self.close_button.setFixedSize(wutil.DPI(20), wutil.DPI(20))

        self.close_button.setParent(None)
        self.orbit_layout.addWidget(self.close_button)

    def _update_button(self, btn, icon_path, action_identifier, label, button_id):
        btn.setIcon(QtGui.QIcon(icon_path))
        btn.setToolTipData(tooltip_template=label)
        try:
            btn.clicked.disconnect()
        except Exception:
            pass
        btn.clicked.connect(lambda: ejecutar_accion(action_identifier))
        if action_identifier in acciones:
            configuracion_orbit[button_id] = action_identifier
            guardar_configuracion_botones()

    def _setup_orbit_button_menu(self, btn, button_id):
        menu = cw.MenuWidget()
        for icon_path, label, action_ident, tooltip_text in self._get_menu_items():
            action = menu.addAction(QtGui.QIcon(icon_path), label)
            action.triggered.connect(partial(self._update_button, btn, icon_path, action_ident, tooltip_text, button_id))

        menu.addSeparator()
        remove_action = menu.addAction("Remove this Button")
        remove_action.triggered.connect(partial(self._remove_button, button_id))

        menu.exec_(QtGui.QCursor.pos())

    def _setup_add_button_menu(self, pos):
        menu = cw.MenuWidget()
        for icon_path, label, action_ident, tooltip_text in self._get_menu_items():
            action = menu.addAction(QtGui.QIcon(icon_path), label)
            action.triggered.connect(partial(self._add_new_tool, action_ident))
            if configuracion_orbit.get(action_ident):
                action.setEnabled(False)

        menu.exec_(QtGui.QCursor.pos())

    def _add_new_tool(self, action_identifier):
        new_idx = max([int(k.replace("button", "")) for k in configuracion_orbit.keys() if k.startswith("button")] + [0]) + 1
        button_id = f"button{new_idx}"
        configuracion_orbit[button_id] = action_identifier
        guardar_configuracion_botones()
        QtCore.QTimer.singleShot(50, lambda: orbit_window(rebuild=True))

    def _remove_button(self, button_id):
        if button_id in configuracion_orbit:
            del configuracion_orbit[button_id]
            guardar_configuracion_botones()
        QtCore.QTimer.singleShot(50, lambda: orbit_window(rebuild=True))


class OrbitWindow(customDialogs.QFlatCloseableFloatingWidget, OrbitWindowMixin):
    def __init__(self, parent=None, offset_x=0, offset_y=0, rebuild=False):
        super().__init__(popup=False, parent=parent)
        self.setObjectName("orbit_window")
        self.setWindowTitle("Orbit")

        self._setup_orbit_ui()
        self._hovered = False

        self.fade_timer = QtCore.QTimer(self)
        self.fade_timer.setSingleShot(True)
        self.fade_timer.timeout.connect(self._apply_transparency)

        self.settings_timer = QtCore.QTimer(self)
        self.settings_timer.timeout.connect(self._check_settings)
        self.settings_timer.start(500)

        from TheKeyMachine.mods import settingsMod as settings

        saved_geom = settings.get_setting("orbit_geometry")

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
        if not self._hovered:
            from TheKeyMachine.mods import settingsMod as settings

            auto_transparency = settings.get_setting("orbit_auto_transparency", False)
            if auto_transparency and not self.fade_timer.isActive():
                self.setWindowOpacity(0.60)
            elif not auto_transparency:
                self.setWindowOpacity(1.0)

    def _apply_transparency(self):
        from TheKeyMachine.mods import settingsMod as settings

        if not self._hovered and settings.get_setting("orbit_auto_transparency", False):
            self.setWindowOpacity(0.60)

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
        self.setWindowOpacity(1.0)
        if not hovered:
            self.fade_timer.start(800)

    def hideEvent(self, event):
        from TheKeyMachine.mods import settingsMod as settings

        settings.set_setting("orbit_geometry", [self.pos().x(), self.pos().y(), self.width(), self.height()])
        super().hideEvent(event)


def orbit_window(*args, offset_x=0, offset_y=0, rebuild=False):
    if cmds.window("orbit_window", exists=True):
        cmds.deleteUI("orbit_window")

    parent = wrapInstance(int(mui.MQtUtil.mainWindow()), QtWidgets.QWidget)
    win = OrbitWindow(parent=parent, offset_x=offset_x, offset_y=offset_y, rebuild=rebuild)
    win.show()


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


def validate_form(name, explanation):
    if not name.strip() or not explanation.strip():
        return False
    return True


def bug_report_window(*args):
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

    def limit_textbox_characters(textbox, max_chars):
        current_text = textbox.toPlainText()
        if len(current_text) > max_chars:
            textbox.setPlainText(current_text[:max_chars])
            textbox.moveCursor(QtGui.QTextCursor.End)

    parent = wrapInstance(int(mui.MQtUtil.mainWindow()), QtWidgets.QWidget)

    window = QtWidgets.QWidget(parent, QtCore.Qt.Window | QtCore.Qt.FramelessWindowHint)
    window.resize(600, 700)
    window.setObjectName("BugReportWindow")
    window.setWindowTitle("Report a Bug")
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
    # email_label_style = "color: #bbb; font-size: 12px;"
    # error_label_style = "color: #bbb; font-size: 12px;"
    # script_editor_label_style = "color: #bbb; font-size: 12px;"
    confirmation_label_style = "color: #9bbbca;"

    input_style = "background-color:  #2d2d2d ; font-size: 12px; border: none; border-radius: 5px; color: #bbb;"
    textbox_style = "background-color: #2d2d2d; font-size: 12px; border: none; border-radius: 5px; color: #bbb;"

    if screen_width == 3840:
        # Styles
        apology_label_style = "color: #d37457; font-size: 30px;"
        apology_text_style = "color: #ccc; font-size: 18px;"
        name_label_style = "color: #bbb; font-size: 20px;"
        # email_label_style = "color: #bbb; font-size: 20px;"
        # error_label_style = "color: #bbb; font-size: 20px;"
        # script_editor_label_style = "color: #bbb; font-size: 20px;"
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

    close_button = QtWidgets.QPushButton("X")
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

    # email_label = QtWidgets.QLabel("")
    email_input = QtWidgets.QLineEdit()
    email_input.setStyleSheet(input_style)
    email_input.setFixedSize(300, 25)
    email_input.setPlaceholderText("Your email")
    email_input.setMaxLength(50)

    explanation_label = QtWidgets.QLabel("")
    explanation_textbox = QtWidgets.QTextEdit()
    explanation_textbox.setStyleSheet(textbox_style)
    explanation_textbox.setPlaceholderText(
        "Please describe the problem or error you're experiencing. To identify and correct the issue, it's essential to reproduce it. Detail step-by-step the actions you've taken and specify which tool is causing the error"
    )
    explanation_textbox.textChanged.connect(lambda: limit_textbox_characters(explanation_textbox, 1200))

    script_error_label = QtWidgets.QLabel("")
    script_error_textbox = QtWidgets.QTextEdit()
    script_error_textbox.setStyleSheet(textbox_style)
    script_error_textbox.setPlaceholderText(
        "If you see any errors in the Script Editor, please copy and paste the code here. The last 3 or 4 lines should be sufficient"
    )
    script_error_textbox.textChanged.connect(lambda: limit_textbox_characters(script_error_textbox, 1200))

    confirmation_label = QtWidgets.QLabel("<br>")
    confirmation_label.setStyleSheet(confirmation_label_style)

    send_button = QtWidgets.QPushButton("Send bug")
    send_button.setFixedSize(550, 40)
    send_button.setStyleSheet(button_style)
    send_button.clicked.connect(
        lambda: on_send_click(name_input, email_input, explanation_textbox, script_error_textbox, confirmation_label, window, send_button)
    )

    layout.addWidget(close_button, alignment=QtCore.Qt.AlignRight)
    layout.addWidget(apology_label, alignment=QtCore.Qt.AlignCenter)
    layout.addWidget(apology_label2, alignment=QtCore.Qt.AlignCenter)
    layout.addWidget(apology_label3, alignment=QtCore.Qt.AlignCenter)
    layout.addWidget(confirmation_label, alignment=QtCore.Qt.AlignCenter)
    # layout.addWidget(name_label)
    layout.addWidget(name_input)
    # layout.addWidget(email_label)
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
