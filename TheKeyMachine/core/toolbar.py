
'''

    TheKeyMachine - Animation Toolset for Maya Animators                                           
                                                                                                                                              
                                                                                                                                              
    This file is part of TheKeyMachine, an open source software for Autodesk Maya licensed under the GNU General Public License v3.0 (GPL-3.0).                                           
    You are free to use, modify, and distribute this code under the terms of the GPL-3.0 license.                                              
    By using this code, you agree to keep it open source and share any modifications.                                                          
    This code is provided "as is," without any warranty. For the full license text, visit https://www.gnu.org/licenses/gpl-3.0.html

    thekeymachine.xyz / x@thekeymachine.xyz                                                                                                                                        
                                                                                                                                              
    Developed by: Rodrigo Torres / rodritorres.com                                                                                             
    Modified by: Alehaaaa / alehaaaa.github.io                                                                                                 
                                                                                                                                             


'''


# Maya related imports
import maya.cmds as cmds
import maya.mel as mel
import maya.utils as utils
import maya.OpenMaya as om
import maya.OpenMayaUI as mui
try:
    from shiboken6 import wrapInstance, getCppPointer # type: ignore 
    from PySide6 import QtWidgets, QtCore, QtGui # type: ignore
    from PySide6.QtGui import QActionGroup # type: ignore
    from PySide6.QtWidgets import QApplication, QDialog # type: ignore
    from PySide6.QtCore import QTimer # type: ignore # , Signal
except ImportError:
    # Qt related imports
    from shiboken2 import wrapInstance, getCppPointer
    from PySide2 import QtWidgets, QtCore, QtGui
    from PySide2.QtWidgets import QApplication, QDesktopWidget, QDialog, QActionGroup
    from PySide2.QtCore import QTimer # , Signal

    

# Standard library imports
import os
import sys
import shutil
import platform
import re
import time
import json
import functools
from functools import partial
import threading
import importlib
import urllib.request
from urllib.parse import urlencode
import ssl
import base64



# -----------------------------------------------------------------------------------------------------------------------------
#                                    We load the necessary modules for TheKeyMachine                                          #
# -----------------------------------------------------------------------------------------------------------------------------


import TheKeyMachine.mods.generalMod as general # type: ignore
import TheKeyMachine.mods.uiMod as ui # type: ignore
import TheKeyMachine.mods.keyToolsMod as keyTools # type: ignore
import TheKeyMachine.mods.selSetsMod as selSets # type: ignore
import TheKeyMachine.mods.helperMod as helper # type: ignore
import TheKeyMachine.mods.mediaMod as media # type: ignore
import TheKeyMachine.mods.styleMod as style # type: ignore
import TheKeyMachine.mods.barMod as bar # type: ignore
import TheKeyMachine.mods.hotkeysMod as hotkeys # type: ignore
import TheKeyMachine.core.customGraph as cg # type: ignore

from TheKeyMachine.widgets import sliderWidget as sw # type: ignore
from TheKeyMachine.widgets import menuWidget as mw # type: ignore



# -----------------------------------------------------------------------------------------------------------------------------
#              TheKeyMachine configuration is loaded from the JSON, or the default installation paths are used.               #
# -----------------------------------------------------------------------------------------------------------------------------


from TheKeyMachine.mods.generalMod import config # type: ignore

INSTALL_PATH                    = config["INSTALL_PATH"]
USER_FOLDER_PATH                = config["USER_FOLDER_PATH"]
UPDATER                         = config["UPDATER"]
BUG_REPORT                      = config["BUG_REPORT"]
CUSTOM_TOOLS_MENU               = config["CUSTOM_TOOLS_MENU"]
CUSTOM_TOOLS_EDITABLE_BY_USER   = config["CUSTOM_TOOLS_EDITABLE_BY_USER"]
CUSTOM_SCRIPTS_MENU             = config["CUSTOM_SCRIPTS_MENU"]
CUSTOM_SCRIPTS_EDITABLE_BY_USER = config["CUSTOM_SCRIPTS_EDITABLE_BY_USER"]


# -----------------------------------------------------------------------------------------------------------------------------
#    It attempts to load the user_preferences. If this is a new installation, it won't exist and the file must be created     #
# -----------------------------------------------------------------------------------------------------------------------------



USER_PREFERENCE_FILE = os.path.normpath(os.path.join(USER_FOLDER_PATH, "TheKeyMachine_user_data/preferences/user_preferences.py"))
USER_PREFERENCE_FILE_CODE = '''
#____________________ TheKeyMachine User Preferences  ________________________ #

show_tooltips = True
toolbar_icon_w = 28
toolbar_icon_h = 28
toolbar_size = 1580
'''


if not os.path.exists(USER_PREFERENCE_FILE):
    os.makedirs(os.path.dirname(USER_PREFERENCE_FILE), exist_ok=True)
    with open(USER_PREFERENCE_FILE, "w") as file:
        file.write(USER_PREFERENCE_FILE_CODE)

# Attempt to import the user preferences module
try:
    import TheKeyMachine_user_data.preferences.user_preferences as user_preferences # type: ignore
except ImportError as e:
    print(f"Error al importar: {e}")



# -----------------------------------------------------------------------------------------------------------------------------
#      It attempts to load the Connect modules. If this is a new installation, they need to be copied to the user folder      #
# -----------------------------------------------------------------------------------------------------------------------------



import os
import shutil
import time

# Define module import paths
origen_toolbox = os.path.join(INSTALL_PATH, "TheKeyMachine/connect/tools/tools.py")
origen_scripts = os.path.join(INSTALL_PATH, "TheKeyMachine/connect/scripts/scripts.py")
destino_toolbox = os.path.join(USER_FOLDER_PATH, "TheKeyMachine_user_data/connect/tools/tools.py")
destino_scripts = os.path.join(USER_FOLDER_PATH, "TheKeyMachine_user_data/connect/scripts/scripts.py")

# Define paths for __init__.py files in each directory
init_paths = [
    os.path.join(USER_FOLDER_PATH, "TheKeyMachine_user_data/__init__.py"),
    os.path.join(USER_FOLDER_PATH, "TheKeyMachine_user_data/connect/__init__.py"),
    os.path.join(USER_FOLDER_PATH, "TheKeyMachine_user_data/connect/tools/__init__.py"),
    os.path.join(USER_FOLDER_PATH, "TheKeyMachine_user_data/connect/scripts/__init__.py")
]

# Ensure that destination directories exist
os.makedirs(os.path.dirname(destino_toolbox), exist_ok=True)
os.makedirs(os.path.dirname(destino_scripts), exist_ok=True)

# Create empty __init__.py files if they don't already exist
for init_path in init_paths:
    if not os.path.isfile(init_path):
        open(init_path, 'a').close()

# Check if files exist at the destination path
toolbox_exists = os.path.isfile(destino_toolbox)
scripts_exists = os.path.isfile(destino_scripts)

# If they don't exist, copy them from the original source location
if not toolbox_exists:
    shutil.copyfile(origen_toolbox, destino_toolbox)
    time.sleep(1)

if not scripts_exists:
    shutil.copyfile(origen_scripts, destino_scripts)
    time.sleep(1)

# Intentar importar los módulos
try:
    import TheKeyMachine_user_data # type: ignore
    importlib.reload(TheKeyMachine_user_data) # type: ignore
    import TheKeyMachine_user_data.connect # type: ignore

    import TheKeyMachine_user_data.connect.tools.tools as connectToolBox # type: ignore
    import TheKeyMachine_user_data.connect.scripts.scripts as cbScripts # type: ignore
except ImportError as e:
    importlib.reload(TheKeyMachine_user_data)
    print(f"Error al importar: {e}")





# -----------------------------------------------------------------------------------------------------------------------------
#                                                    Reload modules                                                           #
# -----------------------------------------------------------------------------------------------------------------------------

modules_to_reload = [
    general,
    bar,
    ui,
    keyTools,
    helper,
    media,
    style,
    cg,
    hotkeys,
    user_preferences,
    connectToolBox,
    cbScripts,
    sw,
    mw,
]

for module in modules_to_reload:
    importlib.reload(module)


# -----------------------------------------------------------------------------------------------------------------------------
#                                          Creation of the toolbar and UI class                                               #
# -----------------------------------------------------------------------------------------------------------------------------


current_blend_slider_mode = "BL"
toggleAnimOffsetButtonState = False
micro_move_button_state = False
WorkspaceName = 'k'
selection_sets_workspace = 's'


COLOR = ui.Color()


class toolbar(object):
    open_new_scene_scriptJob = None

    def __init__(self):
        self.bar_center_value = 10
        self.anim_offset_run_timer = True
        self.toggleAnimOffsetButtonState = False
        self.micro_move_button_state = False
        self.micro_move_run_timer = True
        self.animation_offset_original_values = {}
        self.move_keyframes_intField = None
        self.setgroup_states = {}
        self.setgroup_buttons = {}
        self.tc = threading.Thread(target=self.toolbar_center_time, args=(1,))      # Create a thread to center the toolbar
        self.run_centerToolbar = True
        self.tc.start()



        # When loading a new scene, the on_scene_opened() function is executed, which includes, among other things, the function to update the selectionSets.
        # This first if statement checks whether the scriptJob exists; if not, it either creates or deletes it.
        if toolbar.open_new_scene_scriptJob is not None and self.isScriptJobActive(toolbar.open_new_scene_scriptJob):
            cmds.scriptJob(kill=toolbar.open_new_scene_scriptJob, force=True)


        # Function that runs when new scenes are opened
        def on_scene_opened():
            self.update_selectionSets_on_new_scene()
            self.update_popup_menu()
        toolbar.open_new_scene_scriptJob = cmds.scriptJob(event=("SceneOpened", on_scene_opened))



        # Utility for determining screen resolution
        screen_width, screen_height = self.get_screen_resolution()
        self.screen_width = screen_width
        #print(f"Screen width: {self.screen_width}")


        # Attempt to load customGraph
        QTimer.singleShot(6000, self.load_customGraph_try_01)




    def get_screen_resolution(self):
        app = QApplication.instance()
        if not app:
            app = QApplication([])

        try:
            # PySide2
            from PySide2.QtGui import QDesktopWidget
            desktop = QDesktopWidget()
            screen_rect = desktop.screenGeometry()
        except ImportError:
            # PySide6
            screen = app.primaryScreen()
            screen_rect = screen.geometry()

        screen_width = screen_rect.width()
        screen_height = screen_rect.height()
        
        return screen_width, screen_height



    # These two functions attempt to check if the Graph Editor is open and load customGraph in that case; they are made with two attempts
    def load_customGraph_try_01(self):
        graph_vis = cmds.getPanel(vis=True)
        if graph_vis and "graphEditor1" in graph_vis:
            cg.createCustomGraph()
        else:
            QTimer.singleShot(8000, self.load_customGraph_try_02)

    def load_customGraph_try_02(self):
        graph_vis = cmds.getPanel(vis=True)
        if graph_vis and "graphEditor1" in graph_vis:
            cg.createCustomGraph()
        else:
            pass


    # For use with toggle functionality on Shelf or Launcher
    def toggle(self, *args):
        if cmds.workspaceControl(WorkspaceName, query=True, exists=True):
            if cmds.workspaceControl(WorkspaceName, query=True, visible=True):
                cmds.workspaceControl(WorkspaceName, edit=True, visible=False, actLikeMayaUIElement=True)
            else:
                cmds.workspaceControl(WorkspaceName, edit=True, restore=True, actLikeMayaUIElement=True)
        else:
            self.reload()


    def create_shelf_icon(self, *args):
        button_name = "TheKeyMachine"
        command = "import TheKeyMachine;TheKeyMachine.toggle()"
        icon_path = media.shelf_icon
        icon_path = os.path.normpath(icon_path)
        current_shelf_tab = cmds.tabLayout("ShelfLayout", query=True, selectTab=True)
        cmds.shelfButton(parent=current_shelf_tab, image=icon_path, command=command, label=button_name)
    

    # Evaluate if the scriptJob that launches on_scene_opened() is active
    def isScriptJobActive(self, jobId):
        activeJobs = cmds.scriptJob(listJobs=True)
        for job in activeJobs:
            if str(jobId) in job:
                return True
        return False


    # Update the iBookmarks menu when scene changes
    def update_popup_menu(self):

        if not cmds.objExists("iBookmarks"):

            # Limpia el menú popup actual
            cmds.popupMenu('isolate_button_popupMenu', e=True, deleteAllItems=True)

            # Agrega un ítem para abrir la ventana de bookmarks
            cmds.menuItem(l="Bookmarks", c=lambda x: create_ibookmarks_window(), annotation="Open isolate bookmarks window", image=media.ibookmarks_menu_image, parent='isolate_button_popupMenu') # type: ignore
            cmds.menuItem(divider=True, parent='isolate_button_popupMenu')
            cmds.menuItem('down_level_checkbox', l="Down one level", annotation="", checkBox=False, c=lambda x: bar.toggle_down_one_level(x), parent='isolate_button_popupMenu')

        else:

            # Obtén todos los nombres de los bookmarks existentes
            bookmarks = cmds.listRelatives("iBookmarks", children=True) or []

            # Limpia el menú popup actual
            cmds.popupMenu('isolate_button_popupMenu', e=True, deleteAllItems=True)

            # Agrega un ítem por cada bookmark existente
            for bookmark in bookmarks:
                text = bookmark.replace('_ibookmark', '')
                cmds.menuItem(
                    l=text, 
                    parent='isolate_button_popupMenu',
                    image=media.grey_menu_image,
                    c=lambda x, text=text: isolate_bookmark(bookmark_name=text)) # type: ignore

            cmds.menuItem(divider=True, parent='isolate_button_popupMenu')

            # Agrega un ítem para abrir la ventana de bookmarks
            cmds.menuItem(l="Bookmarks", c=lambda x: create_ibookmarks_window(), annotation="Open isolate bookmarks window", image=media.ibookmarks_menu_image, parent='isolate_button_popupMenu') # type: ignore
            cmds.menuItem(divider=True, parent='isolate_button_popupMenu')
            cmds.menuItem('down_level_checkbox', l="Down one level", annotation="", checkBox=False, c=lambda x: bar.toggle_down_one_level(x), parent='isolate_button_popupMenu')




    def update_selectionSets_on_new_scene(self):
        if cmds.window("SetCreationWindow", exists=True):
            cmds.deleteUI("SetCreationWindow")

        # First verification to check if the SelectionSets workspace exists.
        # If it doesn't exist and trying to assign `vis_state` results in an error.
        if cmds.workspaceControl(selection_sets_workspace, query=True, exists=True):
            vis_state = cmds.workspaceControl(selection_sets_workspace, query=True, visible=True )
            if vis_state:
                if cmds.objExists("TheKeyMachine_SelectionSet"):
                    self.create_buttons_for_sel_sets()
                else:
                    self.selection_sets_empty_setup()
            else:
                pass # The selection set workspace is hidden; nothing needs to be done
        else:
            pass



    def reload(*args):
        toolbar_module_name = 'TheKeyMachine.core.toolbar'
        customGraph_module_name = 'TheKeyMachine.core.customGraph'
        
        # Importa el módulo y recarga
        toolbar_module = importlib.import_module(toolbar_module_name)
        customGraph_module = importlib.import_module(customGraph_module_name)


        # If the scriptJob already exists and is active, terminate it
        if hasattr(toolbar_module.toolbar, 'open_new_scene_scriptJob') and toolbar_module.toolbar().isScriptJobActive(toolbar_module.toolbar.open_new_scene_scriptJob):
            cmds.scriptJob(kill=toolbar_module.toolbar.open_new_scene_scriptJob, force=True)

        if cmds.workspaceControl(WorkspaceName, q=True, exists=True):
            # Borrar el workspaceControl
            cmds.deleteUI(WorkspaceName, control=True)

        importlib.reload(toolbar_module)
        importlib.reload(customGraph_module)
        toolbar_module.tb.startUI()



    # _______________________________________________________ SELECTION SET ________________________________________________________



    def export_sets(self, *args):
        file_path, _ = QtWidgets.QFileDialog.getSaveFileName(None, "Export Sets", "", "JSON Files (*.json);;All Files (*)")

        if not file_path:
            return

        set_data = {"set_groups": []}

        set_groups = self.get_set_groups()
        for set_group in set_groups:
            set_group_data = {"name": set_group.replace("_setgroup", ""), "sets": []}
            sub_sel_sets = cmds.sets(set_group, q=True) or []
            for sub_sel_set in sub_sel_sets:
                if cmds.objExists(sub_sel_set):
                    split_name = sub_sel_set.split('_')
                    color_suffix = split_name[-1]
                    set_name = "_".join(split_name[:-1])
                    set_group_data["sets"].append({"name": set_name, "color_suffix": color_suffix, "objects": cmds.sets(sub_sel_set, q=True)})
            set_data["set_groups"].append(set_group_data)

        with open(file_path, "w") as file:
            json.dump(set_data, file, indent=4)


    def export_single_subgroup(self, set_group_name, *args):
        file_path, _ = QtWidgets.QFileDialog.getSaveFileName(None, "Export Set Group", "", "JSON Files (*.json);;All Files (*)")

        if not file_path:
            return

        set_data = {"set_groups": []}
        set_group_data = {"name": set_group_name.replace("_setgroup", ""), "sets": []}

        sub_sel_sets = cmds.sets(set_group_name, q=True) or []
        for sub_sel_set in sub_sel_sets:
            if cmds.objExists(sub_sel_set):
                split_name = sub_sel_set.split('_')
                color_suffix = split_name[-1]
                set_name = "_".join(split_name[:-1])
                set_group_data["sets"].append({"name": set_name, "color_suffix": color_suffix, "objects": cmds.sets(sub_sel_set, q=True)})

        set_data["set_groups"].append(set_group_data)

        with open(file_path, "w") as file:
            json.dump(set_data, file, indent=4)



    def import_sets(self, *args):
        file_path, _ = QtWidgets.QFileDialog.getOpenFileName(None, "Import Sets", "", "JSON Files (*.json);;All Files (*)")

        if not file_path:
            return

        with open(file_path, "r") as file:
            set_data = json.load(file)

        set_groups_data = set_data.get("set_groups", [])

        # This is added to avoid errors if the workspace control exists but is empty and attempts to import something
        sel_set_name = "TheKeyMachine_SelectionSet"
        if not cmds.objExists(sel_set_name):
            # Crea el conjunto de selección si no existe
            cmds.sets(name=sel_set_name, empty=True)

        for set_group_data in set_groups_data:
            set_group_name = set_group_data["name"]
            set_group_name_with_suffix = f"{set_group_name}_setgroup"

            if not cmds.objExists(set_group_name_with_suffix):
                cmds.sets(name=set_group_name_with_suffix, empty=True)
                cmds.sets(set_group_name_with_suffix, add="TheKeyMachine_SelectionSet")

            sets_data = set_group_data.get("sets", [])

            for set_info in sets_data:
                set_name = set_info["name"]
                color_suffix = set_info["color_suffix"]
                set_name_with_suffix = f"{set_name}_{color_suffix}"

                if not cmds.objExists(set_name_with_suffix):
                    new_set = cmds.sets(name=set_name_with_suffix, empty=True)
                    cmds.addAttr(new_set, longName="hidden", attributeType="bool", defaultValue=False)
                    cmds.sets(new_set, add=set_group_name_with_suffix)

                objects = set_info.get("objects", [])
                for obj in objects:
                    if cmds.objExists(obj):
                        cmds.sets(obj, add=set_name_with_suffix)

        # Actualizar los botones después de importar los sets
        QTimer.singleShot(500, self.create_buttons_for_sel_sets)



    def rename_setgroup(self, old_setgroup_name, new_setgroup_name, *args):

        # Check that the new name is not empty
        if not new_setgroup_name.strip():
            cmds.warning("Please enter a valid set group name")
            return

        # # Check that the new name does not already exist in the scene
        # if cmds.objExists(new_setgroup_name):
        #     cmds.warning(f"A set group named '{new_setgroup_name}' already exists. Please choose a different name")
        #     return

        # # Check that the new name does not start with a number
        # if re.match(r"^\d", new_setgroup_name):
        #     cmds.warning("Set group name cannot start with a number")
        #     return

        # # Check that the new name does not contain invalid characters or spaces for Maya
        # if not re.match(r"^[A-Za-z_][A-Za-z0-9_]*$", new_setgroup_name):
        #     cmds.warning("Set group name contains invalid characters or spaces. Only letters, numbers, and underscores are allowed")
        #     return


        # Let cmds.rename handle the renaming logic/permissions


        # Check that the name is not "main" or "Main"
        if new_setgroup_name.lower() == "main":
            cmds.warning("Cannot rename set group 'main'")
            return

        # Add the "_setgroup" suffix to the new name
        new_setgroup_name = f"{new_setgroup_name.strip()}_setgroup"

        # Rename the set group in a deferred callback
        def rename_setgroup_deferred():
            cmds.rename(old_setgroup_name, new_setgroup_name)

        cmds.evalDeferred(rename_setgroup_deferred)

        # Close the change name window if it exists
        if cmds.window("changeSetGroupNameWindow", exists=True):
            cmds.deleteUI("changeSetGroupNameWindow")

        # Update the buttons for set groups
        cmds.evalDeferred(self.create_buttons_for_sel_sets)




    def change_setgroup_name_window(self, setgroup_name, *args):

        if cmds.window("SetGroupNameWindow", exists=True):
            cmds.deleteUI("SetGroupNameWindow")

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

        def on_return_pressed(setgroup_name_field, *args):
            new_setgroup_name = setgroup_name_field.text()
            if new_setgroup_name:
                original_setgroup_name = setgroup_name_field.property("annotation")
                self.rename_setgroup(original_setgroup_name, new_setgroup_name)  # Asumiendo que tienes una función llamada rename_setgroup
                window.close()

        parent = self.maya_main_window()

        window = QtWidgets.QWidget(parent, QtCore.Qt.Window | QtCore.Qt.FramelessWindowHint)
        window.resize(200, 80)
        window.setObjectName('SetGroupNameWindow')
        window.setWindowTitle('Rename Set Group')
        window.setWindowOpacity(1.0)
        window.setAttribute(QtCore.Qt.WA_TranslucentBackground)

        window.mousePressEvent = mousePressEvent
        window.mouseMoveEvent = mouseMoveEvent
        window.mouseReleaseEvent = mouseReleaseEvent

        central_widget = QtWidgets.QWidget(window)
        # central_widget.setStyleSheet("background-color: #444; border-radius: 10px;")
        layout = QtWidgets.QVBoxLayout(central_widget)
        layout.setContentsMargins(10, 10, 10, 10)

        window_layout = QtWidgets.QVBoxLayout(window)
        window_layout.addWidget(central_widget)
        window.setLayout(window_layout)

        close_button = QtWidgets.QPushButton('X')
        close_button.setFixedSize(20, 20)
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

        setgroup_name_field = QtWidgets.QLineEdit(central_widget)
        setgroup_name_field.returnPressed.connect(lambda: on_return_pressed(setgroup_name_field))
        setgroup_name_field.setPlaceholderText("Rename Set Group")
        setgroup_name_field.setProperty("annotation", setgroup_name)
        setgroup_name_field.setFixedSize(190, 25)
        setgroup_name_field.setStyleSheet(
            "QLineEdit {"
            "    background-color: #252525;"
            "    color: #cccccc;"
            "    border: none;"
            "    padding: 2px;"
            "    border-radius: 4px;"
            "}"
        )

        rename_button = QtWidgets.QPushButton("Rename Set Group")
        rename_button.setFixedSize(190, 30)
        rename_button.setStyleSheet(
            "QPushButton {"
            "    color: #ccc;"
            "    background-color: #555;"
            "    border-radius: 5px;"
            "    font: 12px;"
            "}"
            "QPushButton:hover:!pressed {"
            "    color: #fff;"
            "    background-color: #666;"
            "    border-radius: 5px;"
            "    font: 12px;"
            "}"
        )
        rename_button.clicked.connect(lambda: on_return_pressed(setgroup_name_field))

        layout.addWidget(close_button, alignment=QtCore.Qt.AlignRight)
        layout.addWidget(setgroup_name_field)
        layout.addWidget(rename_button)

        window.show()

        # Adjust the window position
        parent_geometry = parent.geometry()
        x = parent_geometry.x() + parent_geometry.width() / 2 - window.width() / 2 - 120
        y = parent_geometry.y() + parent_geometry.height() / 2 - window.height() / 2 + 150
        window.move(x, y)



    def rename_set(self, old_set_name, new_set_name, set_group=None, *args):
        # Check that the new name is not empty
        if not new_set_name.strip():
            cmds.warning("Please enter a valid set name")
            return

        # Check that the new name does not already exist in the scene
        current_color_suffix = old_set_name.rsplit("_", 1)[-1]
        new_set_name_with_color = f"{new_set_name}_{set_group}_{current_color_suffix}"

        if cmds.objExists(new_set_name_with_color):
            cmds.warning(f"A set named '{new_set_name_with_color}' already exists. Please choose a different name")
            return

        # # Check that the new name does not start with a number
        # if re.match(r"^\d", new_set_name):
        #     cmds.warning("Set name cannot start with a number")
        #     return

        # # Check that the new name does not contain invalid characters or spaces for Maya
        # if not re.match(r"^[A-Za-z_][A-Za-z0-9_]*$", new_set_name):
        #     cmds.warning("Set name contains invalid characters or spaces. Only letters, numbers, and underscores are allowed")
        #     return

        
        # Let cmds.rename handle the renaming logic/permissions



        # Rename the selection group
        def rename_set_deferred():
            cmds.rename(old_set_name, new_set_name_with_color)

        cmds.evalDeferred(rename_set_deferred)

        # Close the change set name window if it exists
        if cmds.window("changeSetNameWindow", exists=True):
            cmds.deleteUI("changeSetNameWindow")

        # Update the buttons for selection groups
        cmds.evalDeferred(self.create_buttons_for_sel_sets)



    def change_set_name_window(self, set_name, set_group=None, *args):

        if cmds.window("SetNameWindow", exists=True):
            cmds.deleteUI("SetNameWindow")

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

        def on_return_pressed(set_name_field, *args):
            new_set_name = set_name_field.text()
            if new_set_name:
                set_name = set_name_field.property("annotation")
                self.rename_set(set_name, new_set_name)
                window.close()

        parent = self.maya_main_window()
        window = QtWidgets.QWidget(parent, QtCore.Qt.Window | QtCore.Qt.FramelessWindowHint)
        window.resize(200, 80)
        window.setObjectName('SetNameWindow')
        window.setWindowTitle('Rename Set')
        window.setWindowOpacity(1.0)
        window.setAttribute(QtCore.Qt.WA_TranslucentBackground)  # Hacer el fondo translúcido

        window.mousePressEvent = mousePressEvent
        window.mouseMoveEvent = mouseMoveEvent
        window.mouseReleaseEvent = mouseReleaseEvent

        central_widget = QtWidgets.QWidget(window)
        # central_widget.setStyleSheet("background-color: #444; border-radius: 10px;")  # Color de fondo y borde redondeado
        layout = QtWidgets.QVBoxLayout(central_widget)
        layout.setContentsMargins(10, 10, 10, 10)

        window_layout = QtWidgets.QVBoxLayout(window)
        window_layout.addWidget(central_widget)
        window.setLayout(window_layout)  # Usar el layout en la ventana principal

        close_button = QtWidgets.QPushButton('X')
        close_button.setFixedSize(20, 20)
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
        
        set_name_field = QtWidgets.QLineEdit(central_widget)
        set_name_field.returnPressed.connect(lambda: on_return_pressed(set_name_field))
        set_name_field.setPlaceholderText("Rename Set")
        set_name_field.setProperty("annotation", set_name)
        set_name_field.setFixedSize(190, 25)
        set_name_field.setStyleSheet(
            "QLineEdit {"
            "    background-color: #252525;"
            "    color: #cccccc;"
            "    border: none;"
            "    padding: 2px;"
            "    border-radius: 4px;"  # Aquí ajustas el redondeo
            "}"
        )

        rename_button = QtWidgets.QPushButton("Rename Set")
        rename_button.setFixedSize(190, 30)
        rename_button.setStyleSheet(
            "QPushButton {"
            "    color: #ccc;"
            "    background-color: #555;"
            "    border-radius: 5px;"
            "    font: 12px;"
            "}"
            "QPushButton:hover:!pressed {"
            "    color: #fff;"
            "    background-color: #666;"
            "    border-radius: 5px;"
            "    font: 12px;"
            "}"
        )
        rename_button.clicked.connect(lambda: on_return_pressed(set_name_field))
        layout.addWidget(close_button, alignment=QtCore.Qt.AlignRight)
        layout.addWidget(set_name_field)
        layout.addWidget(rename_button)

        window.show()

        # Adjust the window position
        parent_geometry = parent.geometry()
        x = parent_geometry.x() + parent_geometry.width() / 2 - window.width() / 2 - 120
        y = parent_geometry.y() + parent_geometry.height() / 2 - window.height() / 2 + 150
        window.move(x, y)


    def set_set_color(self, set_name, color_suffix, *args):
        # Get the node of the current selection group
        set_node = cmds.ls(set_name)

        # Check that the selection group exists
        if not set_node:
            cmds.warning(f"Set '{set_name}' does not exist")
            return

        # Remove the underscore from the color suffix
        color_suffix = color_suffix.strip('_')

        # Get the current color suffix of the group
        current_color_suffix = set_name.rsplit("_", 1)[-1]

        # Create a new name for the group with the updated color suffix
        new_set_name = set_name.replace(current_color_suffix, color_suffix)

        # Check that the new name does not already exist in the scene
        if cmds.objExists(new_set_name):
            cmds.warning(f"A set named '{new_set_name}' already exists. Please choose a different color")
            return

        # Rename the selection group with the updated color suffix
        cmds.rename(set_node, new_set_name)

        # Close the color selection window if it exists
        if cmds.window("changeSetColorWindow", exists=True):
            cmds.deleteUI("changeSetColorWindow")

        # Update the buttons for selection groups
        cmds.evalDeferred(self.create_buttons_for_sel_sets)




    def create_new_set_group(self, set_name_field_widget, set_group_combo_widget, *args):
        new_set_group_name = set_name_field_widget.text()

        sel_set_name = "TheKeyMachine_SelectionSet"
        main_setgroup_name = "main_setgroup"

        if not cmds.objExists(sel_set_name):
            # Create the selection group if it does not exist
            cmds.sets(name=sel_set_name, empty=True)

        if not cmds.objExists(main_setgroup_name):
            # Create the generic set group if it does not exist
            cmds.sets(name=main_setgroup_name, empty=True)
            
            # Add the generic group to the primary selection group "TheKeyMachine_SelectionSet"
            cmds.sets(main_setgroup_name, add=sel_set_name)
        

        # Replace spaces with underscores
        new_set_group_name = new_set_group_name.replace(' ', '_')

        # Validate that the set group name is valid
        if not re.match("^[a-zA-Z_][a-zA-Z0-9_]*$", new_set_group_name):
            cmds.warning("Invalid set group name. Name cannot start with a number or contain invalid characters")
            return

        # Add the "_setgroup" suffix to the set group name
        new_set_group_name += "_setgroup"

        # Create the new set group as a child of the selection group "TheKeyMachine_SelectionSets"
        if not cmds.objExists(new_set_group_name):
            cmds.sets(name=new_set_group_name, empty=True)
            cmds.sets(new_set_group_name, add="TheKeyMachine_SelectionSet")

            # Update the dropdown menu for set groups
            self.update_set_group_menu(set_group_combo_widget)

            new_group_name = set_name_field_widget.text()
            set_group_combo_widget.setCurrentText(new_group_name)


            # Clear the textField after creating the set group
            set_name_field_widget.clear()

            # Delay the update of buttons
            cmds.evalDeferred(self.create_buttons_for_sel_sets)


        else:
            cmds.warning(f"{new_set_group_name} already exists")




    def open_set_creation_window(self):

        if cmds.window("SetCreationWindow", exists=True):
            cmds.deleteUI("SetCreationWindow")

        sel_set_name = "TheKeyMachine_SelectionSet"
        main_setgroup_name = "main_setgroup"

        if not cmds.objExists(sel_set_name):
            # Crea el conjunto de selección si no existe
            cmds.sets(name=sel_set_name, empty=True)

        if not cmds.objExists(main_setgroup_name):
            # Crea el conjunto de selección genérico si no existe
            cmds.sets(name=main_setgroup_name, empty=True)

            # Añade el conjunto genérico al conjunto principal "TheKeyMachine_SelectionSet"
            cmds.sets(main_setgroup_name, add=sel_set_name)


        # Variables para el drag
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


        parent = self.maya_main_window()

        window = QtWidgets.QWidget(parent, QtCore.Qt.Window | QtCore.Qt.FramelessWindowHint)
        window.resize(200, 120)
        window.setObjectName('SetCreationWindow')
        window.setWindowTitle('Set Creation')
        window.setWindowOpacity(1.0)
        window.setAttribute(QtCore.Qt.WA_TranslucentBackground)

        window.mousePressEvent = mousePressEvent
        window.mouseMoveEvent = mouseMoveEvent
        window.mouseReleaseEvent = mouseReleaseEvent

        central_widget = QtWidgets.QWidget(window)
        # central_widget.setStyleSheet("background-color: #444; border-radius: 10px;")
        layout = QtWidgets.QVBoxLayout(central_widget)
        layout.setContentsMargins(10, 10, 10, 10)

        window_layout = QtWidgets.QVBoxLayout(window)
        window_layout.addWidget(central_widget)
        window.setLayout(window_layout)

        close_button = QtWidgets.QPushButton('X')
        close_button.setFixedSize(20, 20)
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

        set_name_field = QtWidgets.QLineEdit(central_widget)
        set_name_field.setPlaceholderText("Set name and click a color")
        set_name_field.setFixedSize(340, 30)
        set_name_field.setStyleSheet(
            "QLineEdit {"
            "    background-color: #252525;"
            "    font-size: 13px;"
            "    color: #cccccc;"
            "    border: none;"
            "    padding: 2px;"
            "    border-radius: 4px;"
            "}"
        )

        set_group_combo = QtWidgets.QComboBox(central_widget)
        set_group_combo.setFixedSize(260, 30)
        self.update_set_group_menu(set_group_combo)  # Asumiendo que esto llena el combo box

        image_path = media.getImage("drop_down_arrow.svg")  # Asumiendo que esta función devuelve la ruta completa de la imagen.
        image_path = image_path.replace("\\", "/")

        set_group_combo.setStyleSheet(f"""
            QComboBox {{
                background-color: #353535;
                border-radius: 5px;
                padding: 5px;
                font-size: 13px;
                border: 1px solid #444;
                color: #999;
            }}
            QComboBox::drop-down {{
                border: none;
                padding: 5px;
                color: #cccccc;
                font-size: 16px;
            }}
            QComboBox::down-arrow {{
                image: url({image_path});
            }}
            QComboBox QAbstractItemView {{
                background-color: #333333;
                border-radius: 0px;
                selection-background-color: #555555;
                color: #cccccc;
            }}
            QComboBox QAbstractItemView::item {{
                min-height: 30px;  # Ajusta la altura según tus necesidades
                padding-left: 5px;
            }}
            QComboBox QAbstractItemView::item::selected {{
                border-radius: 0px;
                padding: 5px;
            }}
        """)

        create_setgroup_button = QtWidgets.QPushButton("Group")
        create_setgroup_button.setFixedSize(70, 28) 

        create_setgroup_button.setStyleSheet(
            "QPushButton {"
            "    color: #aaa;"
            "    background-color: #585858;"
            "    border-radius: 5px;"
            "    font: 12px;"
            "}"
            "QPushButton:hover:!pressed {"
            "    color: #ccc;"
            "    background-color: #656565;"
            "    border-radius: 5px;"
            "    font: 12px;"
            "}"
        )
        create_setgroup_button.clicked.connect(lambda: self.create_new_set_group(set_name_field, set_group_combo))


        # Crea un nuevo layout horizontal y añade ambos widgets:
        group_layout = QtWidgets.QHBoxLayout()
        group_layout.addWidget(set_group_combo)
        group_layout.addWidget(create_setgroup_button)

        # Luego, añade este nuevo layout al layout principal:
        layout.addWidget(close_button, alignment=QtCore.Qt.AlignRight)
        layout.addWidget(set_name_field)
        layout.addLayout(group_layout)


        color_button_layout = QtWidgets.QHBoxLayout()

        for color_suffix, hex_code in ui.color_codes.items():
            button = QtWidgets.QPushButton("")
            if self.screen_width == 3840:
                button.setFixedSize(50, 50)
            else:
                button.setFixedSize(34, 34)
            hover_color = ui.color_codes_hover.get(color_suffix, hex_code)  # Asegura un valor por defecto
            button.setStyleSheet(
                "QPushButton {"
                f"    background-color: {hex_code};"
                "    border-radius: 5px;"
                "}"
                f"QPushButton:hover {{"
                f"    background-color: {hover_color};"
                "    border-radius: 5px;"
                "}}"
            )
            button.clicked.connect(lambda c=color_suffix, field=set_name_field, combo=set_group_combo: self.create_new_set_and_update_buttons(c, field, combo))


            color_button_layout.addWidget(button)

        if self.screen_width == 3840:
            window.resize(750, 350)
            layout.setContentsMargins(20, 20, 20, 20)
            close_button.setFixedSize(35, 35)
            set_name_field.setFixedSize(700, 50)
            set_name_field.setStyleSheet(
                "QLineEdit {"
                "    background-color: #252525;"
                "    font-size: 20px;"
                "    color: #cccccc;"
                "    border: none;"
                "    padding: 2px;"
                "    border-radius: 4px;"
                "}"
            )
            set_group_combo.setFixedSize(535, 50)
            set_group_combo.setStyleSheet(f"""
                QComboBox {{
                    background-color: #353535;
                    border-radius: 5px;
                    padding: 5px;
                    font-size: 18px;
                    border: 1px solid #444;
                    color: #999;
                }}
                QComboBox::drop-down {{
                    border: none;
                    padding: 5px;
                    color: #cccccc;
                    font-size: 18px;
                }}
                QComboBox::down-arrow {{
                    image: url({image_path});
                }}
                QComboBox QAbstractItemView {{
                    background-color: #333333;
                    border-radius: 0px;
                    selection-background-color: #555555;
                    color: #cccccc;
                }}
                QComboBox QAbstractItemView::item {{
                    min-height: 30px;  # Ajusta la altura según tus necesidades
                    padding-left: 5px;
                }}
                QComboBox QAbstractItemView::item::selected {{
                    border-radius: 0px;
                    padding: 5px;
                }}
            """)
            create_setgroup_button.setFixedSize(150, 50) 
            create_setgroup_button.setStyleSheet(
                "QPushButton {"
                "    color: #aaa;"
                "    background-color: #585858;"
                "    border-radius: 5px;"
                "    font: 18px;"
                "}"
                "QPushButton:hover:!pressed {"
                "    color: #ccc;"
                "    background-color: #656565;"
                "    border-radius: 5px;"
                "    font: 18px;"
                "}"
            )




        layout.addLayout(color_button_layout)
        window.show()

        # Ajustar la posición de la ventana
        parent_geometry = parent.geometry()
        x = parent_geometry.x() + parent_geometry.width() / 2 - window.width() / 2 - 100
        y = parent_geometry.y() + parent_geometry.height() / 2 - window.height() / 2 + 100
        window.move(x, y)



    def update_set_group_menu(self, combo_widget):
        # Limpiar elementos existentes
        combo_widget.clear()

        # Agregar nuevos grupos al comboBox
        for set_group in self.get_set_groups():
            # Obtener el nombre del setgroup sin el sufijo "_setgroup"
            display_name = set_group.replace("_setgroup", "")
            combo_widget.addItem(display_name, set_group)


    def get_set_groups(self):
        if cmds.objExists("TheKeyMachine_SelectionSet"):
            all_sets = cmds.sets("TheKeyMachine_SelectionSet", q=True) or []
            return [s for s in all_sets if s.endswith("_setgroup")]
        else:
            return []



    def create_new_set_and_update_buttons(self, color_suffix, set_name_field, set_group_combo, *args):

        selection = cmds.ls(selection=True)

        if not selection:
            print("Select at least on object")
        else:

            new_set_name = set_name_field.text()
            set_group_name = set_group_combo.currentText()

            sel_set_name = "TheKeyMachine_SelectionSet"
            main_setgroup_name = "main_setgroup"

            if not cmds.objExists(sel_set_name):
                # Crea el conjunto de selección si no existe
                cmds.sets(name=sel_set_name, empty=True)

            if not cmds.objExists(main_setgroup_name):
                # Crea el conjunto de selección genérico si no existe
                cmds.sets(name=main_setgroup_name, empty=True)

                # Añade el conjunto genérico al conjunto principal "TheKeyMachine_SelectionSet"
                cmds.sets(main_setgroup_name, add=sel_set_name)

            # Reemplaza los espacios por guiones bajos
            new_set_name = new_set_name.replace(' ', '_')

            # Verificar que el nombre del set es válido
            if not re.match("^[a-zA-Z_][a-zA-Z0-9_]*$", new_set_name):
                cmds.warning("Invalid set name. Name can't start with a number or contain invalid characters")
                return

            # Añadir el sufijo del color y el nombre del setgroup al nombre del set
            new_set_name += f"_{set_group_name}{color_suffix}"


            set_group_with_suffix = f"{set_group_name}_setgroup"

            if not cmds.objExists(set_group_with_suffix):
                new_set_group = cmds.sets(name=set_group_with_suffix, empty=True)
                cmds.sets(new_set_group, add=sel_set_name)


            # Crear el nuevo set como hijo del set group seleccionado
            if not cmds.objExists(new_set_name):
                # Crear el conjunto de selección y establecer el atributo "hidden" en 0
                new_set = cmds.sets(name=new_set_name, empty=True)
                cmds.addAttr(new_set, longName="hidden", attributeType="bool", defaultValue=False)

                # Asegúrate de que se selecciona algo en la escena
                if cmds.ls(selection=True):
                    # Añade la selección actual al nuevo conjunto de selección
                    cmds.sets(cmds.ls(selection=True), add=new_set)

                # Añade el nuevo conjunto al conjunto del grupo seleccionado (con el sufijo "_setgroup")
                set_group_with_suffix = set_group_name + "_setgroup"
                if cmds.objExists(set_group_with_suffix):
                    cmds.sets(new_set, add=set_group_with_suffix)

                # Actualizar los botones
                self.create_buttons_for_sel_sets()
                set_name_field.clear()

            else:
                cmds.warning(f"{new_set_name} already exists")




    def move_set_to_setgroup(self, set_name, target_setgroup):
        # Verificar si el conjunto de selección y el setgroup de destino existen
        if cmds.objExists(set_name) and cmds.objExists(target_setgroup):
            # Obtener el setgroup actual del conjunto de selección
            current_setgroup = cmds.listSets(object=set_name, extendToShape=True)
            if current_setgroup:
                current_setgroup = current_setgroup[0]

                # Verificar si el conjunto de selección ya está en el setgroup de destino
                if current_setgroup == target_setgroup:
                    cmds.warning(f"The set '{set_name}' is already in the setgroup '{target_setgroup}'")
                else:
                    # Mover el conjunto de selección al setgroup de destino
                    cmds.sets(set_name, e=True, remove=current_setgroup)
                    cmds.sets(set_name, e=True, add=target_setgroup)
                    cmds.warning("Set moved")
                    cmds.evalDeferred(self.create_buttons_for_sel_sets)
            else:
                cmds.warning(f"The set is not part of any setgroup")
        else:
            cmds.warning("Invalid set or setgroup names")



    def handle_set_selection(self, set_name, shift_pressed, ctrl_pressed):
        mods = cmds.getModifiers()
        shift_pressed = bool(mods % 2)  # Shift
        ctrl_pressed = bool(mods % 3)  # Control

        # Verificar si el conjunto de selección es válido
        if cmds.objExists(set_name):
            # Si la tecla "Shift" está presionada, agregar objetos a la selección actual
            if shift_pressed:
                cmds.select(set_name, add=True)
            # Si la tecla "Control" está presionada, eliminar objetos de la selección actual
            elif ctrl_pressed:
                cmds.select(set_name, d=True)
            else:
                # Si no, simplemente seleccionar los objetos del conjunto
                cmds.select(set_name)



    def add_selection_to_set(self, set_name, *args):

        #Añade la selección actual a un conjunto de selección dado.

        # Asegúrate de que haya algo seleccionado en la escena
        if not cmds.ls(selection=True):
            print("Select at least one object")
            return

        # Asegúrate de que el set exista
        if not cmds.objExists(set_name):
            cmds.warning(f"Set {set_name} does not exist")
            return

        # Añade la selección al conjunto de selección
        cmds.sets(cmds.ls(selection=True), add=set_name)

    def remove_selection_from_set(self, set_name, *args):

        if not cmds.ls(selection=True):
            print("Select at least one object")
            return

        # Asegúrate de que el set exista
        if not cmds.objExists(set_name):
            cmds.warning(f"Set {set_name} does not exist")
            return

        # Elimina la selección del conjunto de selección
        cmds.sets(cmds.ls(selection=True), remove=set_name)


    color_names = {
        "_01": "Gray",
        "_02": "Beige",
        "_03": "Aqua",
        "_04": "Blue",
        "_05": "Purple",
        "_06": "Green",
        "_07": "Mute red",
        "_08": "Red"
    }
    
    def create_color_submenu(self, set_name, parent_menu):
        # Los botones de color
        color_buttons = [([0.51, 0.55, 0.56], "_01"), ([0.90, 0.84, 0.68], "_02"), ([0.64, 0.80, 0.75], "_03"),
                         ([0.45, 0.71, 0.63], "_04"), ([0.76, 0.58, 0.57], "_05"), ([0.66, 0.39, 0.40], "_06"), 
                         ([0.50, 0.50, 0.63], "_07"), ([0.50, 0.50, 0.63], "_08")]

        for color_value, color_suffix in color_buttons:
            color_name = self.color_names.get(color_suffix, "Default")

            # Aquí, asumimos que las imágenes se llaman "_01.png", "_02.png", etc.
            # Por lo que simplemente añadimos ".png" al sufijo.
            image_name = color_suffix + ".svg"
            image_path = self.getImage(image_name)

            cmds.menuItem(
                label=color_name,
                image=image_path,  # Agregando la imagen al menuItem
                parent=parent_menu,
                command=functools.partial(self.set_set_color, set_name, color_suffix)
            )




    def clear_selection_sets(self, *args):
        # Borra todos los botones existentes
        children = cmds.flowLayout("selection_sets_flow_layout", q=True, ca=True)
        if children:
            for child in children:
                cmds.deleteUI(child)

        # Crea el botón 'SET' sin importar si hay conjuntos de selección o no
        cmds.separator(style='none', width=5, p="selection_sets_flow_layout")
        selset_button = cmds.iconTextButton(l=' SET ', image=media.add_selection_set_image, h=28, w=28, c=self.open_set_creation_window, p="selection_sets_flow_layout")
        cmds.separator(style='none', width=5, p="selection_sets_flow_layout")
        cmds.popupMenu(parent=selset_button)
        cmds.menuItem(label="Export Sets", c=self.export_sets)
        cmds.menuItem(label="Import Sets", c=self.import_sets)



    def selection_sets_empty_setup(self, *args):
        # Borra todos los botones existentes
        children = cmds.flowLayout("selection_sets_flow_layout", q=True, ca=True)
        if children:
            for child in children:
                cmds.deleteUI(child)

        # Crear el botón 'SET' sin importar si hay conjuntos de selección o no
        cmds.separator(style='none', width=5, p="selection_sets_flow_layout")
        selset_button = cmds.iconTextButton(l=' SET ', image=media.add_selection_set_image, h=32, w=32, c=self.selection_sets_setup, p="selection_sets_flow_layout")
        cmds.separator(style='none', width=5, p="selection_sets_flow_layout")
        cmds.popupMenu(parent=selset_button)
        cmds.menuItem(label="Export Sets", c=self.export_sets)
        cmds.menuItem(label="Import Sets", c=self.import_sets)



    # Set workspace settings for selection sets based on interface when user loads Maya
    def selection_sets_setup(self, *args):
        self.create_buttons_for_sel_sets()
        self.open_set_creation_window()


    def create_buttons_for_sel_sets(self, *args):
        mods = cmds.getModifiers()
        shift_pressed = bool(mods % 2)  # Shift
        ctrl_pressed = bool(mods % 4)  # Control

        sel_set_name = "TheKeyMachine_SelectionSet"
        main_setgroup_name = "main_setgroup"

        if not cmds.objExists(sel_set_name):
            # Crea el conjunto de selección si no existe
            cmds.sets(name=sel_set_name, empty=True)

        if not cmds.objExists(main_setgroup_name):
            # Crea el conjunto de selección genérico si no existe
            cmds.sets(name=main_setgroup_name, empty=True)

            # Añade el conjunto genérico al conjunto principal "TheKeyMachine_SelectionSet"
            cmds.sets(main_setgroup_name, add=sel_set_name)

        # Borra todos los botones existentes
        children = cmds.flowLayout("selection_sets_flow_layout", q=True, ca=True)
        if children:
            for child in children:
                cmds.deleteUI(child)

        # Crear el botón 'SET' sin importar si hay conjuntos de selección o no
        cmds.separator(style='none', width=5, p="selection_sets_flow_layout")
        selset_button = cmds.iconTextButton(l=' SET ', image=media.add_selection_set_image, h=32, w=32, c=self.open_set_creation_window, p="selection_sets_flow_layout")
        cmds.separator(style='none', width=5, p="selection_sets_flow_layout")
        cmds.popupMenu(parent=selset_button)
        cmds.menuItem(label="Export Sets", c=self.export_sets)
        cmds.menuItem(label="Import Sets", c=self.import_sets)

        # Obtiene todos los grupos de conjuntos
        set_groups = self.get_set_groups()

        # Ordenar los setgroups alfabéticamente, pero asegurándose de que "main_setgroup" esté primero
        set_groups.sort(key=lambda g: (g != "main_setgroup", g))

        # Si no hay grupos de conjuntos, no hay nada más que hacer
        if not set_groups:
            return


        # Para cada grupo de conjuntos, obtén sus conjuntos de selección y crea botones para ellos
        for set_group in set_groups:
            # Obtiene todos los conjuntos de selección en el grupo de conjuntos actual
            sub_sel_sets = cmds.sets(set_group, q=True) or []

            # Ordena los conjuntos de selección por el código de color en el nombre
            sub_sel_sets.sort(key=lambda s: (s.split('_')[-1], s.split('_')[:-1]))

            # Obtener el estado de oculto o visible del setgroup
            setgroup_hidden = all(cmds.getAttr(f"{sub_sel_set}.hidden") for sub_sel_set in sub_sel_sets)

            # Establecer el color de fondo en función del estado del setgroup
            button_color = "#393939" if setgroup_hidden else "#292929"
            button_text_color = "#636363" if setgroup_hidden else "#66949d"

            # Obtener el nombre del setgroup sin el sufijo "_setgroup"
            setgroup_name_without_suffix = set_group.replace("_setgroup", "")
            button_label = f"{setgroup_name_without_suffix}"

            # Crear el botón del setgroup y asignarle un ID único
            toggle_command = partial(self.toggle_setgroup_visibility, set_group)
            setgroup_button_width = max(60, len(setgroup_name_without_suffix) * 9)
            button = cmds.button(f"setgroup_button_{set_group}", label=button_label, h=32, width=setgroup_button_width, parent="selection_sets_flow_layout", command=toggle_command)
            button_widget = wrapInstance(int(mui.MQtUtil.findControl(button)), QtWidgets.QPushButton)

            if self.screen_width == 3840:
                button_widget.setStyleSheet('''
                    QPushButton {
                        color: %s;
                        background-color: %s;
                        border-radius: 6px;
                        border: 2px solid #333;
                        font: 18px;
                    }
                    QPushButton:hover:!pressed {
                        color: #5B8189;
                        background-color: %s;
                        border-radius: 6px;
                        border: 2px solid #333;
                        font: 18px;
                    }
                ''' % (button_text_color, button_color, button_color))
            else:
                button_widget.setStyleSheet('''
                    QPushButton {
                        color: %s;
                        background-color: %s;
                        border-radius: 6px;
                        border: 2px solid #333;
                        font: 11px;
                    }
                    QPushButton:hover:!pressed {
                        color: #5B8189;
                        background-color: %s;
                        border-radius: 6px;
                        border: 2px solid #333;
                        font: 11px;
                    }
                ''' % (button_text_color, button_color, button_color))


            cmds.popupMenu(parent=button)
            # Verificar si el setgroup es el "main" y no agregar el menuItem "Rename Group" en ese caso
            if set_group != "main_setgroup":
                cmds.menuItem(label="Rename Group", command=lambda x, set_group=set_group: self.change_setgroup_name_window(set_group))
                cmds.menuItem(divider=True)
            cmds.menuItem(label="Export Group", command=lambda x, g=set_group: self.export_single_subgroup(g))
            cmds.menuItem(label="Delete Group", command=lambda x, g=set_group: self.remove_set_group_and_update_buttons(g))

        cmds.separator(style='none', width=10, p="selection_sets_flow_layout") # Espacio entre los botones de los sets pertenecientes a cada grupo

        # Para cada grupo de conjuntos, obtén sus conjuntos de selección y crea botones para ellos
        for set_group in set_groups:
            # Obtiene todos los conjuntos de selección en el grupo de conjuntos actual
            sub_sel_sets = cmds.sets(set_group, q=True) or []

            # Ordena los conjuntos de selección por el código de color en el nombre
            sub_sel_sets.sort(key=lambda s: (s.split('_')[-1], s.split('_')[:-1]))

            setgroup_hidden = all(cmds.getAttr(f"{sub_sel_set}.hidden") for sub_sel_set in sub_sel_sets)

            # Crear botones para cada conjunto de selección
            button_color = "#252525" if setgroup_hidden else "#333333"


            for sub_sel_set in sub_sel_sets:
                # Asegúrate de que el conjunto de selección es válido
                

                if cmds.objExists(sub_sel_set):
                    split_name = sub_sel_set.split('_')
                    color_suffix = split_name[-1]
                    set_name = "_".join(split_name[:-2])  # Une todas las partes del nombre, excepto las dos últimas partes.


                    # Obtiene el valor del color del código de color
                    button_color_hex = ui.color_codes.get(f"_{color_suffix}", "#333333")  # Default to white (#FFFFFF) if color_suffix not found
                    button_color_hex_hover = ui.color_codes_hover.get(f"_{color_suffix}", "#333333")  # Default to white (#FFFFFF) if color_suffix not found

                    # Calcula el ancho del botón en función del número de caracteres en la etiqueta
                    button_width = max(60, len(set_name) * 8)


                    # Verificar el valor del atributo "hidden" del conjunto de selección
                    is_hidden = cmds.getAttr(f"{sub_sel_set}.hidden")
                    # Si el conjunto está oculto, no mostrar el botón
                    if is_hidden:
                        continue


                    # Obtiene los miembros del conjunto de selección
                    members = cmds.sets(sub_sel_set, q=True)

                    # Crea una cadena con los nombres de los miembros separados por comas
                    members_string = ", ".join(m for m in (members or []) if cmds.objExists(m))

                    

                    # El botón selecciona los miembros del conjunto de selección al hacer clic en él
                    button = cmds.button(label=set_name, h=32, width=button_width, command=lambda x, s=sub_sel_set: self.handle_set_selection(s, shift_pressed, ctrl_pressed), parent="selection_sets_flow_layout")
                    button_widget = wrapInstance(int(mui.MQtUtil.findControl(button)), QtWidgets.QPushButton)

                    if self.screen_width == 3840:  
                        style_sheet = '''
                            QPushButton {{
                                color: #333333;
                                background-color: {color};
                                border-radius: 6px;
                                border: 2px solid #333;
                                font: 18px;
                            }}
                            QPushButton:hover:!pressed {{
                                color: #333333;
                                background-color: {color_over};
                                border-radius: 6px;
                                border: 2px solid #333;
                                font: 18px;
                            }}
                        '''.format(color=button_color_hex, color_over=button_color_hex_hover)
                    else:
                        style_sheet = '''
                            QPushButton {{
                                color: #333333;
                                background-color: {color};
                                border-radius: 6px;
                                border: 2px solid #333;
                                font: 11px;
                            }}
                            QPushButton:hover:!pressed {{
                                color: #333333;
                                background-color: {color_over};
                                border-radius: 6px;
                                border: 2px solid #333;
                                font: 11px;
                            }}
                        '''.format(color=button_color_hex, color_over=button_color_hex_hover)


                    button_widget.setStyleSheet(style_sheet)



                    # Crea un menú emergente con una opción de "Delete set"
                    selset_button = cmds.popupMenu(parent=button)



                    # Menu button Selection Sets --------

                    cmds.menuItem(label="Add Selection", image=media.add_to_selection_set_image, command=lambda x, s=sub_sel_set: self.add_selection_to_set(s), p=selset_button)
                    cmds.menuItem(label="Remove Selection", image=media.remove_from_selection_set_image, command=lambda x, s=sub_sel_set: self.remove_selection_from_set(s), p=selset_button)
                    cmds.menuItem(divider=True, p=selset_button)

                    color_menu = cmds.menuItem(subMenu=True, label="Change Color", image=media.change_selection_set_color_image, p=selset_button)
                    self.create_color_submenu(sub_sel_set, color_menu)

                    cmds.menuItem(label="Rename Set", image=media.rename_selection_set_image, c=functools.partial(self.change_set_name_window, sub_sel_set, set_group), p=selset_button)                
                    cmds.menuItem(divider=True, p=selset_button)

                    cmds.menuItem(label="Delete Set", image=media.remove_selection_set_image, command=lambda x, s=sub_sel_set, g=set_group: self.remove_set_and_update_buttons(s, g), p=selset_button)        
                    cmds.menuItem(divider=True, p=selset_button)
                   
                    # Muestra ventana select items
                    cmds.menuItem(label="Selector", image=media.selector_selection_set_image, command=lambda x, s=sub_sel_set: self.select_set_items_window(s), p=selset_button)
                    move_selset_submenu = cmds.menuItem(subMenu=True, image=media.move_selection_set_image, label="Move to ...", p=selset_button)

                    # Obtener los setgroups que están dentro de "TheKeyMachine_SelectionSet"
                    valid_setgroups = [sg for sg in set_groups if cmds.sets(sg, isMember=sel_set_name)]

                    # Agregar un elemento en el menú emergente para cada setgroup válido
                    for valid_setgroup in valid_setgroups:
                        # Obtener el nombre del setgroup sin el sufijo "_setgroup"
                        setgroup_name_without_suffix = valid_setgroup.replace("_setgroup", "")
                        
                        # Agregar un elemento en el menú emergente para cada setgroup válido
                        cmds.menuItem(label=setgroup_name_without_suffix, command=lambda x, s=sub_sel_set, g=valid_setgroup: self.move_set_to_setgroup(s, g), p=move_selset_submenu)


    def select_set_items_window(self, set_name):
        # Obtener los miembros del conjunto de selección
        members = cmds.sets(set_name, q=True)

        # Ordenar los miembros alfabéticamente
        members.sort()

        # Crear la ventana
        window_name = "selectItemsWindow"
        if cmds.window(window_name, exists=True):
            cmds.deleteUI(window_name)

        window = cmds.window(window_name, title="Set Items", widthHeight=(210, 250))
        cmds.paneLayout()

        # Agregar una lista para mostrar los miembros del conjunto de selección
        member_list = cmds.textScrollList(nr=32, allowMultiSelection=True, width=100, height=100)

        # Agregar los miembros a la lista ordenada alfabéticamente
        cmds.textScrollList(member_list, edit=True, append=members)

        # Agregar una función para el evento changeCommand
        cmds.textScrollList(member_list, edit=True, sc=functools.partial(self.select_items_from_list, member_list))

        cmds.showWindow(window)

    def select_items_from_list(self, list_name, *args):
        # Obtener los elementos seleccionados en la lista
        selected_items = cmds.textScrollList(list_name, query=True, selectItem=True)

        # Seleccionar los objetos en la escena
        cmds.select(selected_items, replace=True)



    def remove_set_and_update_buttons(self, set_name, set_group, *args):

        if cmds.objExists(set_name):

            # Si el set existe, quitarlo del setgroup
            if cmds.objExists(set_name) and cmds.objExists(set_group):
                cmds.sets(set_name, remove=set_group)
            cmds.delete(set_name)

            # Retrasar la actualización de los botones
            cmds.evalDeferred(self.create_buttons_for_sel_sets)
        else:
            cmds.evalDeferred(self.create_buttons_for_sel_sets)



    def remove_set_group_and_update_buttons(self, set_group, *args):
        if cmds.objExists(set_group):
            # Obtiene todos los conjuntos de selección en el grupo de conjuntos
            sub_sel_sets = cmds.sets(set_group, q=True) or []

            # Verifica si el setgroup está vacío después de eliminar los conjuntos de selección
            sub_sel_sets_after_deletion = cmds.sets(set_group, q=True) or []  # Verificar si la lista de conjuntos de selección está vacía
            if not sub_sel_sets_after_deletion:
                # Borra cada conjunto de selección
                for sub_sel_set in sub_sel_sets:
                    if cmds.objExists(sub_sel_set):
                        cmds.delete(sub_sel_set)


                # Borra el setgroup solo si está vacío
                cmds.delete(set_group)
            else:
                # Si el setgroup no está vacío, se debe mostrar un mensaje en la consola
                cmds.warning(f"{set_group} is not empty. Please remove all sets in the setgroup first")

        # Retrasar la actualización de los botones
        cmds.evalDeferred(self.create_buttons_for_sel_sets)
        if cmds.window("setCreationWindow", exists=True):
            self.open_set_creation_window()



    def toggle_setgroup_visibility(self, set_group, *args):
        # Verificar si el setgroup existe
        if cmds.objExists(set_group):
            
            # Obtener todos los conjuntos de selección en el grupo de conjuntos
            sub_sel_sets = cmds.sets(set_group, q=True) or []
            
            # Si no hay sub_sel_sets, simplemente retornar
            if not sub_sel_sets:
                return
            
            # Determinar el estado actual de visibilidad consultando el primer sub_sel_set
            current_state = not bool(cmds.getAttr(f"{sub_sel_sets[0]}.hidden"))

            # Cambiar el estado actual (True -> False, False -> True)
            new_state = not current_state
            self.setgroup_states[set_group] = new_state



            # Cambiar el color de fondo del botón en función del estado actual
            button_color = [0.21, 0.25, 0.26] if new_state else [0.11, 0.15, 0.16]
            cmds.button(f"setgroup_button_{set_group}", edit=True, bgc=button_color)

            # Iterar sobre cada conjunto de selección y cambiar el valor del atributo "hidden"

            for sub_sel_set in sub_sel_sets:
                if cmds.objExists(sub_sel_set):

                    cmds.setAttr(f"{sub_sel_set}.hidden", int(not new_state))
                
            # Retrasar la actualización de los botones
            cmds.evalDeferred(self.create_buttons_for_sel_sets)







    # ______________________________________________ SELECION SETS END ___________________________________________________






    def deleteBar(*args):
        cmds.deleteUI(WorkspaceName, control=True)


    def centerBar(*args):

        import TheKeyMachine.core.toolbar # type: ignore
        TheKeyMachine.core.toolbar.tb.centrar()



    def getImage(self, image):
        img_dir = os.path.join(INSTALL_PATH, "TheKeyMachine/data/img/")

        # Ruta del archivo de configuración
        fullImgDir = os.path.join(img_dir, image)

        return fullImgDir

    



# ---------------------------------------- ANIMATION OFFSET ------------------------------------------------------#



    # Variable global para almacenar los valores originales de los keyframes
    animation_offset_original_values = {}

    def store_keyframes(self):
        global animation_offset_original_values

        # Obtener el rango de tiempo seleccionado en el Range Slider
        aTimeSlider = mel.eval('$tmpVar=$gPlayBackSlider')
        timeRange = cmds.timeControl(aTimeSlider, q=True, rangeArray=True)

        # Si no se selecciona un rango, utilizar todo el rango de la línea de tiempo
        if timeRange[1] - timeRange[0] == 1:
            timeRange = [cmds.playbackOptions(q=True, minTime=True), cmds.playbackOptions(q=True, maxTime=True)]

        selected_objects = cmds.ls(selection=True)

        for obj in selected_objects:
            attrs = cmds.listAttr(obj, keyable=True)
            if attrs:
                self.animation_offset_original_values[obj] = {}
                for attr in attrs:
                    attr_full_name = obj + '.' + attr
                    if cmds.getAttr(attr_full_name, settable=True):
                        keyframes = cmds.keyframe(obj, attribute=attr, query=True)
                        if keyframes:
                            self.animation_offset_original_values[obj][attr] = {frame: cmds.getAttr(attr_full_name, time=frame) for frame in keyframes if timeRange[0] <= frame <= timeRange[1]}

        # borra selected range slider 
        user_selected_objs = cmds.ls(selection=True)
        cmds.select(clear=True)
        cmds.select(obj)




    def adjust_keyframes(self):

        def _as_scalar(value):
            v = value
            while isinstance(v, (list, tuple)) and len(v) == 1:
                v = v[0]
            if isinstance(v, (list, tuple)):
                return None, False
            return v, True

        global animation_offset_original_values

        # Range del Time Slider
        aTimeSlider = mel.eval('$tmpVar=$gPlayBackSlider')
        timeRange = cmds.timeControl(aTimeSlider, q=True, rangeArray=True)
        if timeRange[1] - timeRange[0] == 1:
            timeRange = [
                cmds.playbackOptions(q=True, minTime=True),
                cmds.playbackOptions(q=True, maxTime=True),
            ]

        selected_objects = cmds.ls(selection=True)

        for obj in selected_objects:
            # SOLO escalares para evitar double3
            attrs = cmds.listAttr(obj, keyable=True, scalar=True) or []
            for attr in attrs:
                attr_full_name = obj + '.' + attr

                # salta bloqueados/no seteables y tipos no numéricos
                if not cmds.getAttr(attr_full_name, settable=True) or cmds.getAttr(attr_full_name, lock=True):
                    continue
                a_type = cmds.getAttr(attr_full_name, type=True)
                if a_type in ('enum', 'string', 'message'):
                    continue

                keyframes = cmds.keyframe(obj, attribute=attr, query=True)
                if not keyframes:
                    continue

                for frame in keyframes:
                    if not (timeRange[0] <= frame <= timeRange[1]):
                        continue

                    # valores actual y original
                    cur_raw = cmds.getAttr(attr_full_name, time=frame)
                    current_value, ok_cur = _as_scalar(cur_raw)

                    original_value = (
                        self.animation_offset_original_values
                        .get(obj, {})
                        .get(attr, {})
                        .get(frame)
                    )

                    if original_value is not None:
                        original_value, ok_org = _as_scalar(original_value)
                    else:
                        ok_org = False

                    if not (ok_cur and ok_org):
                        # si alguno no es escalar, ignora este par (evita restar listas)
                        continue

                    diff = current_value - original_value
                    if diff == 0:
                        continue

                    # aplica offset a todas las keys del rango (UNA sola vez por atributo)
                    for frame_to_update in keyframes:
                        if not (timeRange[0] <= frame_to_update <= timeRange[1]):
                            continue

                        orig_update = (
                            self.animation_offset_original_values
                            .get(obj, {})
                            .get(attr, {})
                            .get(frame_to_update)
                        )
                        if orig_update is None:
                            continue

                        orig_update, ok_upd = _as_scalar(orig_update)
                        if not ok_upd:
                            continue

                        new_val = orig_update + diff
                        cmds.setKeyframe(obj, attribute=attr, time=frame_to_update, value=new_val)


                    for fr in keyframes:
                        if timeRange[0] <= fr <= timeRange[1]:
                            self.animation_offset_original_values.setdefault(obj, {}).setdefault(attr, {})[fr] = cmds.getAttr(attr_full_name, time=fr)


                    break  # salimos del bucle de frames (ya aplicamos el offset para este attr)


    def offset_animation_deferred(self, interval):
        def adjust_offset_animation():
            self.adjust_keyframes()

        while self.anim_offset_run_timer:
            time.sleep(interval)
            utils.executeDeferred(adjust_offset_animation)


    def toggleAnimOffsetButton(self, *args):

        selection = cmds.ls(selection=True)

        if not selection:
            # Si no hay objetos seleccionados, muestra un mensaje de error
            print("Select one object")
        else:

            # Toggle button state
            self.toggleAnimOffsetButtonState = not self.toggleAnimOffsetButtonState

            if self.toggleAnimOffsetButtonState:
                cmds.undoInfo(openChunk=True)
                cmds.iconTextButton("anim_offset_button", e=True, bgc=(0.3, 0.3, 0.3))
                self.anim_offset_run_timer = True
                self.store_keyframes()

                t = threading.Thread(target=self.offset_animation_deferred, args=(0.3,))
                t.start()
            else:
                cmds.undoInfo(closeChunk=True)
                cmds.iconTextButton("anim_offset_button", e=True, bgc=(0.2, 0.2, 0.2))
                self.anim_offset_run_timer = False
                pass




#---------------------------------------------------------------

    def toggle_micro_move_button(self, *args):

        self.micro_move_button_state = not self.micro_move_button_state

        if self.micro_move_button_state:
            cmds.undoInfo(openChunk=True)
            # cmds.iconTextButton("micro_move_button", e=True, bgc=(0.3, 0.3, 0.3))
            self.micro_move_run_timer = True
            bar.activate_micro_move()

            t = threading.Thread(target=self.micro_move_thread, args=(0.5,))
            t.start()

        else:
            self.micro_move_run_timer = False
            cmds.undoInfo(closeChunk=True)
            current_context = cmds.currentCtx()
            microMoveContext = "microMoveCtx"
            microRotateContext = "microRotateCtx"
            # cmds.iconTextButton("micro_move_button", e=True, bgc=(0.2, 0.2, 0.2))

            # El thread tarda en pararse así que necesitamos crear esto y así salirnos en barMod de la ejecución
            cmds.manipMoveContext('dummyCtx')
            cmds.setToolTo('dummyCtx')



    def micro_move_thread(self, interval):
        def micro_move_run():
            bar.activate_micro_move()

        while self.micro_move_run_timer: 
            time.sleep(interval)
            utils.executeDeferred(micro_move_run)



    # ____________________________________ Center Toolbar ____________________________________



    def toolbar_center_time(self, interval):
        def centerBar_run():
            self.centrar()

        
        while self.run_centerToolbar: 
            time.sleep(interval)
            utils.executeDeferred(centerBar_run)




    def centrar(self):
        try:
            if cmds.workspaceControl(WorkspaceName, query=True, exists=True):

                # Obtener e imprimir las dimensiones del workspaceControl
                workspace_width = cmds.workspaceControl(WorkspaceName, query=True, width=True)

                # Calcula los pixeles que sobran si quitamos al ancho total de la vista el tamaño de la toolbar
                sobrante = workspace_width - user_preferences.toolbar_size


                screen_width, screen_height = self.get_screen_resolution()
                self.screen_width = screen_width

                #Obsoleto
                #desktop = QDesktopWidget()
                #screen_resolution = desktop.screenGeometry()
                #screen_width = screen_resolution.width()

                if screen_width == 3840:
                    margen = sobrante / 5
                else:
                    margen = sobrante / 2

                # El margen que necesitamos meter en el separador de la izq es la mitad de lo que sobra

                if margen < 10:
                    margen = 10

                self.bar_center_value = margen

                cmds.separator("centerRow", edit=True, width=self.bar_center_value)
                return self.bar_center_value
            else:
                self.stop_center_toolbar_thread()
        except RuntimeError as e:
            if 'Object \'centerRow\' not found' in str(e):
                self.stop_center_toolbar_thread()
                print("Error: ", e)


    def stop_center_toolbar_thread(self):
        self.run_centerToolbar = False





    def show_sys_info(self):

        os_info = platform.system() + " " + platform.release()

        tkm_stage = general.get_thekeymachine_version()
        tkm_version = general.get_thekeymachine_version()

        app = QApplication.instance()
        if not app:
            app = QApplication([])

        desktop = QDesktopWidget()
        screen_resolution = desktop.screenGeometry()
        width, height = screen_resolution.width(), screen_resolution.height()

        tkm_toolbar_width = cmds.workspaceControl(WorkspaceName, query=True, width=True)
        sobrante = tkm_toolbar_width - user_preferences.toolbar_size
        toolbar_s = user_preferences.toolbar_size

        # El margen que necesitamos meter en el separador de la izq es la mitad de lo que sobra
        margen = sobrante / 2


        print("_____________________ TKM sys info ______________________")
        print("")
        print(f"TKM version: {tkm_stage} v{tkm_version}")
        print("Operating System: " + os_info)
        print("Install path: " + INSTALL_PATH)
        print("User folder path: " + USER_FOLDER_PATH)
        print("User preference file: " + USER_PREFERENCE_FILE)
        print("")
        print(f"Screen resolution: {width}x{height}")
        print(f"Toolbar size: {toolbar_s}")
        print(f"Toolbar width: {tkm_toolbar_width}")
        print(f"Toolbar sides: {sobrante}")
        print(f"Toolbar push: {margen}")
        print("")
        print("_________________________________________________________")
    # _______________________________________  end center toolbar _____________________________________




    def startUI(self):

        MAIN_WORKAREA = mel.eval('$gWorkAreaForm=$gWorkAreaForm')
        MAIN_PANE = mel.eval('$gViewportWorkspaceControl=$gViewportWorkspaceControl')
        CHAN_LAYER_EDITOR = mel.eval('getUIComponentDockControl("Channel Box / Layer Editor", false)')
        OUTLINER = mel.eval('getUIComponentDockControl("Outliner", false)')
        SHELF = mel.eval('getUIComponentToolBar("Shelf", false)')
        TIME_SLIDER = mel.eval('getUIComponentToolBar("Time Slider", false)')
        RANGE_SLIDER = mel.eval('getUIComponentToolBar("Range Slider", false)')
        COMMAND_LINE = mel.eval('getUIComponentToolBar("Command Line", false)')
        HELP_LINE = mel.eval('getUIComponentToolBar("Help Line", false)')
        TOOL_BOX = mel.eval('getUIComponentToolBar("Tool Box", false)')


        if cmds.workspaceControl(WorkspaceName, query=True, exists=True) is False:
            cmds.workspaceControl(WorkspaceName, dtm=["bottom", False],  ih=30, li=True, hp="fixed", tp=["west", True], floating=False, uiScript='from TheKeyMachine.core.toolbar import tb\ntb.buildUI()', actLikeMayaUIElement=True)

            cmds.workspaceControl(WorkspaceName, edit=True, dtc=( TIME_SLIDER ,"top"))
        else:
            cmds.workspaceControl(WorkspaceName, edit=True, restore=True, actLikeMayaUIElement=True)


        # Fix para dejar la tab en el lado izquierdo, debería arreglar el error al reinstalar
        if cmds.workspaceControl(WorkspaceName, query=True, exists=True):
            cmds.workspaceControl(WorkspaceName, edit=True, tabPosition=["west", True])
        else:
            pass


        # Crea el selection sets workspace
        if cmds.workspaceControl(selection_sets_workspace, query=True, exists=True) is False:
            cmds.workspaceControl(selection_sets_workspace,  ih=35, li=True, tp=["west", True], floating=False, dtc=["k","bottom"], retain=True, vis=False, uiScript='from TheKeyMachine.core.toolbar import tb\ntb.create_selection_sets_workspace()', actLikeMayaUIElement=True)
            cmds.workspaceControl(selection_sets_workspace, edit=True, tabPosition=["west", True])
        else:
            cmds.workspaceControl(selection_sets_workspace, edit=True, restore=False, actLikeMayaUIElement=True)
            self.update_selectionSets_on_new_scene()



    # Crea el selection sets workspace ----------------------------------------------------------------------------

    def create_selection_sets_workspace(self):
        cmds.flowLayout('selection_sets_flow_layout', columnSpacing=1, wr=True, w=150)
        self.selection_sets_empty_setup()



    def toggle_selection_sets_workspace(self, *args):
        if cmds.workspaceControl(selection_sets_workspace, query=True, exists=True):
            vis_state = cmds.workspaceControl(selection_sets_workspace, query=True, visible=True )

            if vis_state:
                cmds.workspaceControl(selection_sets_workspace, edit=True, visible=False)
            else:
                cmds.workspaceControl(selection_sets_workspace, edit=True, restore=True, actLikeMayaUIElement=True)
                self.create_buttons_for_sel_sets()
        else:
            cmds.workspaceControl(selection_sets_workspace, ih=35, li=True, tp=["west", True], floating=False, dtc=["k","bottom"], retain=True, vis=True, uiScript='from TheKeyMachine.core.toolbar import tb\ntb.create_selection_sets_workspace()', actLikeMayaUIElement=True)
            cmds.workspaceControl(selection_sets_workspace, edit=True, tabPosition=["west", True])
            self.update_selectionSets_on_new_scene()




    def set_reload(self):

        import TheKeyMachine.core.toolbar as t # type: ignore
        importlib.reload(t)




    def maya_main_window(self, *args):
        main_window_ptr = mui.MQtUtil.mainWindow()
        return wrapInstance(int(main_window_ptr), QtWidgets.QWidget)






    # ___________________________________________ iBookmarks _____________________________________________________________ #


    def create_ibookmark_node(self, *args):
        if not cmds.objExists("TheKeyMachine"):
            general.create_TheKeyMachine_node()
        if not cmds.objExists("iBookmarks"):
            general.create_ibookmarks_node()

            

    def create_bookmark(self, list_widget, *args):
        current_selection = cmds.ls(selection=True)
        if not current_selection:
            print("Select at least one object")
            return

        text = cmds.promptDialog(
            title='Create Bookmark',
            message='Enter bookmark name:',
            button=['Create', 'Cancel'],
            defaultButton='Create',
            cancelButton='Cancel',
            dismissString='Cancel'
        )

        if text == 'Create':
            bookmark_name = cmds.promptDialog(query=True, text=True)
            if not bookmark_name:  # Validar si el campo de texto está vacío
                cmds.warning("Bookmark name cannot be empty")
                return

            # Validar el nombre del bookmark usando una expresión regular
            if not re.match(r"^[a-zA-Z_][a-zA-Z0-9_]*$", bookmark_name):
                cmds.warning("Invalid bookmark name. It should start with a letter or underscore and contain only letters, numbers, and underscores")
                return

            self.create_ibookmark_node()
            bookmark_node = cmds.group(em=True, name=f"{bookmark_name}_ibookmark")
            cmds.parent(bookmark_node, "iBookmarks")

            new_groups = []  # Lista para almacenar los nuevos grupos

            for obj in current_selection:
                # Obtener el nombre del objeto sin la ruta (si existe)
                obj_name = obj.split('|')[-1]
                
                # Si el nombre del objeto contiene "->", eliminar la parte anterior a esos caracteres
                if "->" in obj_name:
                    obj_name = obj_name.split("->")[-1]

                # Eliminar cualquier punto en el nombre del objeto (para imagePlanes)
                obj_name = obj_name.replace('.', '_')  
                new_group = cmds.group(em=True, name=f"{obj_name}_{bookmark_name}_ibook")
                cmds.parent(new_group, bookmark_node)
                new_groups.append(new_group)  # Agregar el nuevo grupo a la lista

            # Desemparentar los objetos después de crear todos los grupos
            for new_group in new_groups:
                cmds.select(new_group, add=True)

            self.update_bookmark_list(list_widget)
        cmds.select(clear=True)
        self.update_popup_menu()




    def remove_bookmark(self, list_widget, *args):
        item = cmds.textScrollList(list_widget, query=True, selectItem=True)
        if item:
            text = item[0]
            bookmark_node = f"{text}_ibookmark"
            cmds.delete(bookmark_node)  # Eliminar el nodo del bookmark
            self.update_bookmark_list(list_widget)
            self.update_popup_menu()



    def isolate_bookmark(self, list_widget=None, bookmark_name=None, *args):
        current_selection = cmds.ls(selection=True, long=True)  # Obtén los nombres completos de los objetos seleccionados

        # Si bookmark_name no es proporcionado, obténlo del list_widget
        if not bookmark_name and list_widget:
            item = cmds.textScrollList(list_widget, query=True, selectItem=True)
            if item:
                bookmark_name = item[0]

        if bookmark_name:
            # Remover '_ibookmark' del final del nombre para obtener el nombre del bookmark
            bookmark_name = bookmark_name.replace('_ibookmark', '')
            # Encontrar el nodo del bookmark
            bookmark_node = f"{bookmark_name}_ibookmark"
            if cmds.objExists(bookmark_node):
                # Obtener todos los objetos dentro del nodo de bookmark
                objects = cmds.listRelatives(bookmark_node, allDescendents=True, fullPath=True)  # Usa fullPath=True aquí
                if objects:
                    selected_objects = []
                    for obj in objects:
                        # Remover "_ibook" del final del nombre del objeto
                        obj_name = obj.rsplit('|', 1)[-1].replace('_ibook', '')
                        # Remover el sufijo que coincide con el texto de la lista de bookmarks
                        obj_name = obj_name.replace(f'_{bookmark_name}', '')
                        
                        # Asegúrate de que el objeto exista antes de agregarlo a la lista de objetos seleccionados
                        if cmds.objExists(obj_name):
                            selected_objects.append(obj_name)

                    # Obtener el estado actual del aislamiento
                    currentPanel = cmds.getPanel(wf=True)
                    panelType = cmds.getPanel(typeOf=currentPanel)
                    if panelType == "modelPanel":
                        currentState = cmds.isolateSelect(currentPanel, query=True, state=True)
                        cmds.select(selected_objects)
                        # If the isolation is not active, we activate it and add the selection
                        if currentState == 0:
                            cmds.isolateSelect(currentPanel, state=1)
                            cmds.isolateSelect(currentPanel, addSelected=True)
                        else:
                            # Si el aislamiento está activo, vaciamos la selección actual y añadimos la nueva selección
                            cmds.isolateSelect(currentPanel, state=0)
                            cmds.isolateSelect(currentPanel, state=1)
                            cmds.isolateSelect(currentPanel, addSelected=True)

                    else:
                        cmds.warning("Please set the focus on a camera or viewport")


                else:
                    cmds.warning(f"No hay objetos dentro del bookmark '{bookmark_name}'")
            else:
                cmds.warning(f"Bookmark '{bookmark_name}' no encontrado en la escena")
        else:
            cmds.warning("No bookmark selected")

        # Restaurar la selección original al final de la función
        cmds.select(clear=True)
        if current_selection:
            cmds.select(current_selection)





    def update_bookmark_list(self, list_widget, *args):
        bookmarks = cmds.listRelatives("iBookmarks", children=True) or []
        cmds.textScrollList(list_widget, edit=True, removeAll=True)  # Limpiar la lista
        for bookmark in bookmarks:
            text = bookmark.replace('_ibookmark', '')
            cmds.textScrollList(list_widget, edit=True, append=text)


    def create_ibookmarks_window(self, *args):

        original_selection = cmds.ls(selection=True)

        if cmds.window("iBookmarksWindow", exists=True):
            cmds.deleteUI("iBookmarksWindow")

        window = cmds.window("iBookmarksWindow", title="Isolate Bookmarks", widthHeight=(265, 140), sizeable=False)  # Hacer la ventana no redimensionable
        main_layout = cmds.columnLayout(adjustableColumn=True, rowSpacing=10, columnAlign="center")

        # Crear un formLayout para controlar la disposición de los elementos
        form_layout = cmds.formLayout()
        
        # Columna de la izquierda con la lista
        list_widget = cmds.textScrollList(allowMultiSelection=False, h=130)
        
        # Columna de la derecha con los botones
        button_layout = cmds.columnLayout(adjustableColumn=True, columnAlign="center")
        create_button = cmds.button(label="Create", command=lambda x: self.create_bookmark(list_widget), width=90)  # Ajustar el ancho del botón
        remove_button = cmds.button(label="Remove", command=lambda x: self.remove_bookmark(list_widget), width=90)  # Ajustar el ancho del botón
        isolate_button = cmds.button(label="Isolate", command=lambda x: self.isolate_bookmark(list_widget), width=90)  # Ajustar el ancho del botón
        
        # Establecer las restricciones de disposición en el formLayout
        cmds.formLayout(form_layout, edit=True,
                        attachForm=[(list_widget, 'left', 5), (list_widget, 'top', 5),
                                    (button_layout, 'top', 5), (button_layout, 'right', 5)],
                        attachControl=[(list_widget, 'right', 5, button_layout)])
        
        cmds.setParent(main_layout)  # Regresar al layout principal
        cmds.showWindow(window)
        self.create_ibookmark_node()
        self.update_bookmark_list(list_widget)

        # Restaurar la selección original
        if original_selection:
            cmds.select(original_selection, replace=True)
        else:
            cmds.select(clear=True)




    def update_popup_menu(self, *args):

        if not cmds.objExists("iBookmarks"):
            return

        # Obtén todos los nombres de los bookmarks existentes
        bookmarks = cmds.listRelatives("iBookmarks", children=True) or []

        # Limpia el menú popup actual
        cmds.popupMenu(self.isolate_button_popupMenu, e=True, deleteAllItems=True)

        # Agrega un ítem por cada bookmark existente
        for bookmark in bookmarks:
            text = bookmark.replace('_ibookmark', '')
            cmds.menuItem(l=text, parent=self.isolate_button_popupMenu, image=media.grey_menu_image, c=lambda x, text=text: self.isolate_bookmark(bookmark_name=text))


        cmds.menuItem(divider=True, parent=self.isolate_button_popupMenu)

        # Agrega un ítem para abrir la ventana de bookmarks
        cmds.menuItem(l="Bookmarks", c=lambda x: self.create_ibookmarks_window(), annotation="Open isolate bookmarks window", image=media.ibookmarks_menu_image, parent=self.isolate_button_popupMenu)
        cmds.menuItem(divider=True, parent=self.isolate_button_popupMenu)
        cmds.menuItem('down_level_checkbox', l="Down one level", annotation="", checkBox=False, c=lambda x: bar.toggle_down_one_level(x), parent=self.isolate_button_popupMenu)










    def buildUI(self):
        # Fix para que no de error, por si no lee el ancho del ViewPanel

        if self.bar_center_value == None:
            self.bar_center_value = 1


        # Reconstruir column y row layouts
        if cmds.columnLayout("columntoolbar", exists=True):
            cmds.deleteUI("columntoolbar")

        if cmds.rowLayout("rowtoolbar", exists=True):
            cmds.deleteUI("rowtoolbar")




        ### ______________________________________________________ TOOLBAR ICON SIZE  ___________________________________________________

        def get_current_icon_size():
            w, h, size = read_toolbar_icon_size()
            if w == 26 and h == 26:
                return "Small"
            elif w == 28 and h == 28:
                return "Medium"
            elif w == 31 and h == 31:
                return "Big"
            else:
                return None  # Esta línea es en caso de que las dimensiones no coincidan con ninguno de los tamaños esperados


        def read_toolbar_icon_size():

            scripts_dir = os.path.join(USER_FOLDER_PATH, "TheKeyMachine_user_data/preferences")
            config_file = os.path.join(scripts_dir, "user_preferences.py")

            if os.path.isfile(config_file):
                config = {}
                exec(compile(open(config_file).read(), config_file, 'exec'), config)
                toolbar_icon_w = config.get('toolbar_icon_w', 28)
                toolbar_icon_h = config.get('toolbar_icon_h', 28)
                toolbar_size = config.get('toolbar_size', 1550)
                return toolbar_icon_w, toolbar_icon_h, toolbar_size
            else:
                # Valores por defecto si no se encuentra el archivo de configuración
                return 28, 28, 1550

        def update_toolbar_icon_size(w, h, size):
            scripts_dir = os.path.join(USER_FOLDER_PATH, "TheKeyMachine_user_data/preferences")
            config_file = os.path.join(scripts_dir, "user_preferences.py")

            with open(config_file, 'r') as f:
                config_data = f.read()

            new_data = ''
            size_set = False
            w_set = h_set = False

            for line in config_data.split('\n'):
                if line.strip().startswith('toolbar_icon_w'):
                    new_data += f'toolbar_icon_w = {w}\n'
                    w_set = True
                elif line.strip().startswith('toolbar_icon_h'):
                    new_data += f'toolbar_icon_h = {h}\n'
                    h_set = True
                elif line.strip().startswith('toolbar_size'):
                    new_data += f'toolbar_size = {size}\n'
                    size_set = True
                else:
                    new_data += line + '\n'

            # En caso de que las variables no existieran previamente, las agregamos al final del archivo
            if not w_set:
                new_data += f'toolbar_icon_w = {w}\n'
            if not h_set:
                new_data += f'toolbar_icon_h = {h}\n'
            if not size_set:
                new_data += f'toolbar_size = {size}\n'

            with open(config_file, 'w') as f:
                f.write(new_data)




        def set_icon_size_small(value):
            if value:
                update_toolbar_icon_size(26, 26, 1550)
                self.reload()
        def set_icon_size_medium(value):
            if value:
                update_toolbar_icon_size(28, 28, 1580)
                self.reload()

        def set_icon_size_big(value):
            if value:
                update_toolbar_icon_size(31, 31, 1650)
                self.reload()


        ### ______________________________________________________ TOOLTIPS ___________________________________________________

        def read_show_tooltips():
            scripts_dir = os.path.join(USER_FOLDER_PATH, "TheKeyMachine_user_data/preferences")
            config_file = os.path.join(scripts_dir, "user_preferences.py")
            
            if os.path.isfile(config_file):
                config = {}
                exec(compile(open(config_file).read(), config_file, 'exec'), config)
                show_tooltips = config.get('show_tooltips', True)
                return show_tooltips
            else:
                # Valor por defecto si no se encuentra el archivo de configuración
                return True

        def update_show_tooltips(value):
            scripts_dir = os.path.join(USER_FOLDER_PATH, "TheKeyMachine_user_data/preferences")
            config_file = os.path.join(scripts_dir, "user_preferences.py")

            with open(config_file, 'r') as f:
                config_data = f.read()

            # Reemplazar la línea que contiene 'show_tooltips' con el nuevo valor
            new_data = ''
            for line in config_data.split('\n'):
                if line.strip().startswith('show_tooltips'):
                    new_data += f'show_tooltips = {value}\n'
                else:
                    new_data += line + '\n'
            
            # Escribir los nuevos datos en el archivo de configuración
            with open(config_file, 'w') as f:
                f.write(new_data)



        def toggle_tooltips(value):
            # Actualizar el valor de `show_tooltips` en el archivo de configuración
            update_show_tooltips(value)
            update_tooltips()

        # Mirar en el fichero de configuracion si los tooltips estan en True o False
        show_tooltips = read_show_tooltips()


        def update_tooltips():
            # Leer el valor actual de show_tooltips
            show_tooltips = read_show_tooltips()

            
            # Lista que contiene los widgets y los textos de los tooltips
            buttons_and_tooltips = [
                (pointer_button_widget, helper.pointer_tooltip_text),
                (isolate_button_widget, helper.isolate_tooltip_text),
                (block_keys_button_widget, helper.block_keys_tooltip_text),
                (createLocator_button_widget, helper.createLocator_tooltip_text),
                (align_button_widget, helper.align_tooltip_text),
                (tracer_button_widget, helper.tracer_tooltip_text),
                (deleteAnim_button_widget, helper.delete_animation_tooltip_text),
                (reset_values_button_widget, helper.reset_values_tooltip_text),
                (select_opposite_button_widget, helper.select_opposite_tooltip_text),
                (copy_opposite_button_widget, helper.copy_opposite_tooltip_text),
                (mirror_button_widget, helper.mirror_tooltip_text),
                (copy_paste_animation_button_widget, helper.copy_paste_animation_tooltip_text),
                (selector_button_widget, helper.selector_tooltip_text),
                (select_hierarchy_button_widget, helper.select_hierarchy_tooltip_text),
                (animation_offset_button_widget, helper.animation_offset_tooltip_text),
                (link_objects_button_widget, helper.link_objects_tooltip_text),
                (create_follow_cam_button_widget, helper.follow_cam_tooltip_text),
                (copy_worldspace_button_widget, helper.copy_worldspace_tooltip_text),
                (temp_pivot_button_widget, helper.temp_pivot_tooltip_text),
                (micro_move_button_widget, helper.micro_move_tooltip_text),
                (selection_sets_button_widget, helper.selection_sets_tooltip_text),
                (open_custom_graph_button_widget, helper.customGraph_tooltip_text),
                # (toolBox_button_widget, helper.custom_tools_tooltip_text),
                # (customScripts_button_widget, helper.custom_scripts_tooltip_text),

                (move_key_left_b_widget, helper.move_key_left_b_widget_tooltip_text),
                (remove_inbetween_b_widget, helper.remove_inbetween_b_widget_tooltip_text),
                (add_inbetween_b_widget, helper.add_inbetween_b_widget_tooltip_text),
                (move_key_right_b_widget, helper.move_key_right_b_widget_tooltip_text),
                (clear_selected_keys_widget, helper.clear_selected_keys_widget_tooltip_text),
                (select_scene_animation_widget, helper.select_scene_animation_widget_tooltip_text),

                (barTweenSlider_widget, helper.blend_to_frame_slider_tooltip_text),
                (barBlendSlider_widget, helper.blend_to_frame_slider_tooltip_text),

            ]



            # Estilos CSS para los tooltips
            style_enabled = """
            QToolTip {
                color: #ccc;
                border: 3px solid #333;
                background-color:  #4a4a4a;
                padding: 4px;
                border-radius: 4px;
            }
            """

            # Iterar sobre cada botón y su tooltip para establecer el tooltip según el valor de show_tooltips
            for button_widget, tooltip_text in buttons_and_tooltips:
                button_widget.setToolTip(tooltip_text if show_tooltips else "")
                button_widget.setStyleSheet(style_enabled)





        ### ______________________________________________________ TOOLBAR LAYOUT _____________________________________________________________________###

        row_center_value = 10

        cmds.columnLayout("columntoolbar", columnAttach=('both', 1), h=38, cal="center", adj=True, columnWidth=900)
        
        cmds.rowLayout("rowtoolbar", h=38, nc=60, p="columntoolbar")
        cmds.separator("centerRow", style='none', width=row_center_value, p="rowtoolbar") 

        row_ptr = mui.MQtUtil.findControl("rowtoolbar")
        row_qw = wrapInstance(int(row_ptr), QtWidgets.QWidget)
        rowtoolbar_layout = row_qw.layout()


        # _____________________ keyBox__________________________________________________ #



        move_key_left_b = cmds.button(l=" < ", h=22, w=26, p="rowtoolbar", c=partial(keyTools.move_keyframes_in_range, -1))
        move_key_left_b_widget = wrapInstance(int(mui.MQtUtil.findControl(move_key_left_b)), QtWidgets.QPushButton)
        move_key_left_b_widget.setToolTip("")


        remove_inbetween_b = cmds.button(l=" - ", h=22, w=26, p="rowtoolbar", c=keyTools.remove_inbetween)
        remove_inbetween_b_widget = wrapInstance(int(mui.MQtUtil.findControl(remove_inbetween_b)), QtWidgets.QPushButton)
        remove_inbetween_b_widget.setToolTip("")

    
        self.move_keyframes_intField = cmds.intField("move_keyframes_int", width=38, h=22, minValue=1, value=1, bgc=[0.14,0.14,0.14], p="rowtoolbar")
        desplazamiento = cmds.intField("move_keyframes_int", q=True, value=True)

        add_inbetween_b = cmds.button(l=" + ", h=22, w=26, bgc=[0.23,0.23,0.23], p="rowtoolbar", c=keyTools.add_inbetween)
        add_inbetween_b_widget = wrapInstance(int(mui.MQtUtil.findControl(add_inbetween_b)), QtWidgets.QPushButton)
        add_inbetween_b_widget.setToolTip("")


        move_key_right_b = cmds.button(l=" > ", h=22, w=26, p="rowtoolbar", c=partial(keyTools.move_keyframes_in_range, desplazamiento))
        move_key_right_b_widget = wrapInstance(int(mui.MQtUtil.findControl(move_key_right_b)), QtWidgets.QPushButton)
        move_key_right_b_widget.setToolTip("")


        separator = cmds.separator(style='none', width=8)


        clear_selected_keys = cmds.button(l=" x ", h=22, w=20, p="rowtoolbar", c=keyTools.clear_selected_keys)
        clear_selected_keys_widget = wrapInstance(int(mui.MQtUtil.findControl(clear_selected_keys)), QtWidgets.QPushButton)
        clear_selected_keys_widget.setToolTip("")


        select_scene_animation = cmds.button(l=" s ", h=22, w=20, p="rowtoolbar", c=keyTools.select_all_animation_curves)
        select_scene_animation_widget = wrapInstance(int(mui.MQtUtil.findControl(select_scene_animation)), QtWidgets.QPushButton)
        select_scene_animation_widget.setToolTip("")



        # _____________________ BlendSlider ____________________________ #

        # Al final de customGraph.py hay un if-else para mostrar u ocultar el tween slider dependiendo de 
        # si el graph editor esta en modo dock o no. Con esto se evita duplicar el slider



        # def update_blend_label_with_slider_value(value):
        #     rounded_value = abs(round(value * 2))
        #     cmds.text('barBlendSliderLabelText', edit=True, label=str(rounded_value))

        # Wrapper para el modo Pull/Push
        def pull_push_wrapper(value):
            keyTools.blend_pull_and_push(value / 10.0)  # Ajusta el valor antes de pasarlo
            # update_blend_label_with_slider_value(value)

        def blend_to_frame_wrapper(value):
            blend_to_frame_with_button_values(value)
            # update_blend_label_with_slider_value(value)






        def blend_to_default_wrapper(value):

            selected_objects = cmds.ls(selection=True, long=True)
            if not selected_objects:
                return

            json_file_path = keyTools.general.get_set_default_data_file()

            # Leer datos guardados si existen
            if os.path.exists(json_file_path):
                with open(json_file_path, 'r') as file:
                    data = json.load(file)
            else:
                data = {}

            for obj in selected_objects:
                attrs = cmds.listAttr(obj, keyable=True)
                if not attrs:
                    continue

                for attr in attrs:
                    try:
                        attr_full = f"{obj}.{attr}"
                        namespace = obj.split(':')[0] if ':' in obj else 'default'

                        # Obtener valor actual
                        current_value = cmds.getAttr(attr_full)

                        # Obtener valor por defecto desde JSON o Maya
                        if namespace in data and attr_full in data[namespace]:
                            default_value = data[namespace][attr_full]
                        else:
                            default_query = cmds.attributeQuery(attr, node=obj, listDefault=True)
                            default_value = default_query[0] if default_query else current_value

                        # Interpolar entre el valor actual y el valor por defecto
                        new_value = (1 - value) * current_value + value * default_value

                        # Aplicar nuevo valor suavizado
                        cmds.setAttr(attr_full, new_value)

                    except Exception as e:
                        print(f"Error blending {attr} on {obj}: {str(e)}")

            # update_blend_label_with_slider_value(value)





        def blend_slider_wrapper(value):
            keyTools.handle_autokey_start()
            keyTools.blend_to_key(value)  # Llama a la función tween original
            # update_blend_label_with_slider_value(value) 

        # def reset_blend_slider_label_after_drag(value):
        #     global current_blend_slider_mode
        #     # Restablece la etiqueta a "0"
        #     label = "BL"
        #     if current_blend_slider_mode == 'pull_push':
        #         label = "PP"
        #     if current_blend_slider_mode == 'blend_to_frame':
        #         label = "BK"
        #     if current_blend_slider_mode == 'blend_to_default':
        #         label = "BD"
        #     cmds.text('barBlendSliderLabelText', edit=True, label=label)
        #     # Llama a la función tweenSliderReset
        #     keyTools.handle_autokey_end()
        #     keyTools.blendSliderReset(barBlendSlider)



        def update_button_with_current_frame(button_name):
            # Obtener el número del frame actual
            current_frame = cmds.currentTime(query=True)
            # Actualizar el texto del botón con el número del frame
            cmds.button(button_name, edit=True, label=str(int(current_frame)))


        def set_blend_slider_command(mode):
            global current_blend_slider_mode
            current_blend_slider_mode = mode

            match mode:
                case 'pull_push':
                    barBlendSlider_widget.setText("PP")
                    barBlendSlider_widget.setDragCommand(pull_push_wrapper)
                
                    cmds.button('blend_to_key_left', edit=True, vis=False, w=1, h=1)
                    cmds.button('blend_to_key_right', edit=True, vis=False, w=1, h=1)

                case 'blend':
                    barBlendSlider_widget.setText("BL")
                    barBlendSlider_widget.setDragCommand(blend_slider_wrapper)
                
                    cmds.button('blend_to_key_left', edit=True, vis=False, w=1, h=1)
                    cmds.button('blend_to_key_right', edit=True, vis=False, w=1, h=1)
                    
                case 'blend_to_default':
                    barBlendSlider_widget.setText("BD")
                    barBlendSlider_widget.setDragCommand(blend_to_default_wrapper)
                
                    cmds.button('blend_to_key_left', edit=True, vis=False, w=1, h=1)
                    cmds.button('blend_to_key_right', edit=True, vis=False, w=1, h=1)

                case 'blend_to_frame':
                    barBlendSlider_widget.setText("BK")
                    barBlendSlider_widget.setDragCommand(blend_to_frame_wrapper)
                
                    cmds.button('blend_to_key_left', edit=True, vis=True, w=25, h=16)
                    cmds.button('blend_to_key_right', edit=True, vis=True, w=25, h=16)


        def blend_to_frame_with_button_values(percentage):
            left_frame_label = cmds.button('blend_to_key_left', query=True, label=True)
            right_frame_label = cmds.button('blend_to_key_right', query=True, label=True)

            # Convierte las etiquetas a números si es posible, de lo contrario usa None
            try:
                left_frame = int(left_frame_label)
            except ValueError:
                left_frame = None

            try:
                right_frame = int(right_frame_label)
            except ValueError:
                right_frame = None

            # Llama a blend_to_frame con los valores de los botones
            keyTools.blend_to_frame(percentage, left_frame, right_frame)


        cmds.separator(style='none', width=15, p="rowtoolbar")

        
        blend_to_key_left_button = cmds.button('blend_to_key_left', l="1", vis=False, w=1, h=1, c=lambda x: update_button_with_current_frame('blend_to_key_left'), p="rowtoolbar")

        # Slider Widget Blend Slider
        barBlendSlider_widget = sw.SliderWidget("bar_blend_slider", min=-100, max=100, value=0, text="BN", color=COLOR.color.green, dragCommand=blend_slider_wrapper, p=rowtoolbar_layout)
        barBlendSlider = barBlendSlider_widget.objectName()

        blend_to_key_right_button = cmds.button('blend_to_key_right', l="1", vis=False, w=1, h=1, c=lambda x: update_button_with_current_frame('blend_to_key_right'), p="rowtoolbar")


        barBlendSlider_popup_menu = cmds.popupMenu(button=3, ctl=False, alt=False, parent=barBlendSlider)


        # Blend slider menu
        # Crear una colección de radio buttons
        radio_collection = cmds.radioCollection()

        # Crear los items de menú y agregarlos a la colección
        cmds.radioMenuItemCollection(radio_collection)
        
        # Agrega los items de menú con radio buttons
        bar_blend_blend_menu = cmds.menuItem(l="Blend", radioButton=True, p=barBlendSlider_popup_menu, command=lambda x: set_blend_slider_command('blend'))
        bar_blend_default_menu = cmds.menuItem(l="Blend to Default", radioButton=True, p=barBlendSlider_popup_menu, command=lambda x: set_blend_slider_command('blend_to_default'))
        bar_blend_blend_to_key_menu = cmds.menuItem(l="Blend to Frame", radioButton=True, p=barBlendSlider_popup_menu, command=lambda x: set_blend_slider_command('blend_to_frame'))
        bar_blend_pull_push_menu = cmds.menuItem(l="Pull / Push", radioButton=True, p=barBlendSlider_popup_menu, command=lambda x: set_blend_slider_command('pull_push'))

        cmds.menuItem(bar_blend_blend_menu, edit=True, radioButton=True)
        


        # _____________________ TweenSlider ____________________________ #

        # Al final de customGraph.py hay un if-else para mostrar u ocultar el tween slider dependiendo de 
        # si el graph editor esta en modo dock o no. Con esto se evita duplicar el slider


        def tween_wrapper(value):
            keyTools.handle_autokey_start()
            keyTools.tween(value)  # Llama a la función tween original

        def tween_drop_wrapper():
            keyTools.handle_autokey_end()
            keyTools.tweenSliderReset(barTweenSlider)



        def set_tween_slider_command(mode, *args):
            match mode:
                case 'tweener':
                    # barTweenSlider_widget.setText("TW")
                    barTweenSlider_widget.setWorldSpace(False)
                    barTweenSlider_widget.setDragCommand(tween_wrapper)
                case 'tweener_worldspace':
                    # barTweenSlider_widget.setText("WL")
                    barTweenSlider_widget.setWorldSpace(True)
                    barTweenSlider_widget.setDragCommand(tween_wrapper)
                    

        # Slider Widget Tween Slider
        barTweenSlider_widget = sw.SliderWidget("bar_tween_slider", min=-120, max=120, value=0, text="TW", color=COLOR.color.yellow, dragCommand=tween_wrapper, dropCommand=tween_drop_wrapper, p=rowtoolbar_layout)
        barTweenSlider = barTweenSlider_widget.objectName()

        cmds.separator("bar_tween_slider_separator", style='none', width=10, p="rowtoolbar")



        barTweenSlider_popup_menu = cmds.popupMenu(button=3, ctl=False, alt=False, parent=barTweenSlider)


        # Tween slider menu
        # Crear una colección de radio buttons
        radio_collection = cmds.radioCollection()

        # Crear los items de menú y agregarlos a la colección
        cmds.radioMenuItemCollection(radio_collection)
        
        # Agrega los items de menú con radio buttons
        bar_tween_menu = cmds.menuItem(l="Tweener", radioButton=True, p=barTweenSlider_popup_menu, command=lambda x: set_tween_slider_command('tweener'))
        bar_tween_worldspace_menu = cmds.menuItem(l="Tweener World Space", radioButton=True, p=barTweenSlider_popup_menu, command=lambda x: set_tween_slider_command('tweener_worldspace'))

        cmds.menuItem(bar_tween_menu, edit=True, radioButton=True)





        # ----------------------------------------------- ToolsButtons -------------------------------------------------------- #




        # Pointer  -------------------------------------------------------------------------

        pointer_button = cmds.iconTextButton(l="", w=user_preferences.toolbar_icon_w, h=user_preferences.toolbar_icon_h, image=media.pointer_image, c=bar.isolate_master, p="rowtoolbar")
        pointer_button_widget = wrapInstance(int(mui.MQtUtil.findControl(pointer_button)), QtWidgets.QWidget)
        pointer_button_widget.setToolTip("")

        pointer_button_popupMenu = cmds.popupMenu(button=1, ctl=False, alt=False, parent=pointer_button)
        cmds.menuItem(l="Select Rig Controls", c=bar.select_rig_controls, image=media.select_rig_controls_image, parent=pointer_button_popupMenu)
        cmds.menuItem(l="Select Animated Rig Controls ", c=bar.select_animated_rig_controls, image=media.select_animated_rig_controls_image, parent=pointer_button_popupMenu)
        cmds.menuItem(divider=True, parent=pointer_button_popupMenu)
        cmds.menuItem(l="Depth Mover", c=bar.depth_mover, image=media.depth_mover_image, parent=pointer_button_popupMenu)
        #cmds.menuItem(divider=True, parent=pointer_button_popupMenu)
        #cmds.menuItem(l="Help",  c=lambda x: general.open_url("https://thekeymachine.gitbook.io/base/the-toolbar/animation-tools/isolate"), image=media.help_menu_image, parent=pointer_button_popupMenu)





        # Isolate -------------------------------------------------------------------------

        isolate_button = cmds.iconTextButton(l="", w=user_preferences.toolbar_icon_w, h=user_preferences.toolbar_icon_h, image=media.isolate_image, c=bar.isolate_master, p="rowtoolbar")
        isolate_button_widget = wrapInstance(int(mui.MQtUtil.findControl(isolate_button)), QtWidgets.QWidget)
        isolate_button_widget.setToolTip("")

        self.isolate_button_popupMenu = cmds.popupMenu('isolate_button_popupMenu', button=3, ctl=False, alt=False, parent=isolate_button)
        cmds.menuItem(l="Bookmarks", c=lambda x: self.create_ibookmarks_window(), image=media.ibookmarks_menu_image, parent=self.isolate_button_popupMenu)
        cmds.menuItem(divider=True, parent=self.isolate_button_popupMenu)
        cmds.menuItem('down_level_checkbox', l="Down one level", checkBox=False, c=lambda x: bar.toggle_down_one_level(x), parent=self.isolate_button_popupMenu)
        cmds.menuItem(divider=True, parent=self.isolate_button_popupMenu)
        cmds.menuItem(l="Help",  c=lambda x: general.open_url("https://thekeymachine.gitbook.io/base/the-toolbar/animation-tools/isolate"), image=media.help_menu_image, parent=self.isolate_button_popupMenu)




        # Esta linea hay que meterla en el scriptJOb de cuando se abre una escena nueva
        self.update_popup_menu()



        # Create Locators  ----------------------------------------------------------------
        createLocator_button = cmds.iconTextButton(l="", w=user_preferences.toolbar_icon_w, h=user_preferences.toolbar_icon_h, image=media.create_locator_image, c=bar.createLocator, p="rowtoolbar")
        createLocator_button_widget = wrapInstance(int(mui.MQtUtil.findControl(createLocator_button)), QtWidgets.QWidget)
        createLocator_button_widget.setToolTip("")

        createLocator_popup_menu = cmds.popupMenu(parent=createLocator_button)
        cmds.menuItem(l="Select temp locators", c=bar.selectTempLocators, image=media.create_locator_image, p=createLocator_popup_menu)
        cmds.menuItem(l="Remove temp locators", c=bar.deleteTempLocators, image=media.create_locator_image, p=createLocator_popup_menu)
        createLocator_button_widget = wrapInstance(int(mui.MQtUtil.findControl(createLocator_button)), QtWidgets.QWidget)





        # align / match transforms ----------------------------------------------------------

        align_button = cmds.iconTextButton(l="", w=user_preferences.toolbar_icon_w, h=user_preferences.toolbar_icon_h, image=media.align_menu_image, c=bar.align_selected_objects, p="rowtoolbar")
        align_popup_menu = cmds.popupMenu(parent=align_button)
        cmds.menuItem(l="Translation", c=partial(bar.align_selected_objects, pos=True, rot=False, scl=False), image=media.align_menu_image, p=align_popup_menu)
        cmds.menuItem(l="Rotation", c=partial(bar.align_selected_objects, pos=False, rot=True, scl=False), image=media.align_menu_image, p=align_popup_menu)
        cmds.menuItem(l="Scale", c=partial(bar.align_selected_objects, pos=False, rot=False, scl=True), image=media.align_menu_image, p=align_popup_menu)

        align_button_widget = wrapInstance(int(mui.MQtUtil.findControl(align_button)), QtWidgets.QWidget)
        align_button_widget.setToolTip("")




        # Tracer -----------------------------------------------------------------------------

        tracer_button = cmds.iconTextButton(l="", c=bar.mod_tracer, h=user_preferences.toolbar_icon_h, w=user_preferences.toolbar_icon_w, image=media.tracer_menu_image, p="rowtoolbar")
        
        tracer_popup_menu = cmds.popupMenu(parent=tracer_button)
        tracer_checkbox = cmds.menuItem('tracer_checkbox_menuItem', l="Connected", checkBox=False, c=lambda x: bar.tracer_connected(connected=x, update_cb=bar.tracer_update_checkbox), p=tracer_popup_menu)
        cmds.menuItem(l="Refresh", image=media.tracer_refresh_image, c=bar.tracer_refresh, p=tracer_popup_menu)
        cmds.menuItem(l="Show/Hide", image=media.tracer_show_hide_image, c=bar.tracer_show_hide, p=tracer_popup_menu) 
        cmds.menuItem(l="Select offset node", image=media.tracer_select_offset_image, c=bar.select_tracer_offset_node, p=tracer_popup_menu)
        cmds.menuItem(divider=True, parent=tracer_popup_menu)

        tracer_style_sub_menu = cmds.menuItem(l="Style", image=media.tracer_set_color_image, subMenu=True, parent=tracer_popup_menu)
        cmds.menuItem(l="Grey", image=media.tracer_grey_image, c=bar.set_tracer_grey_color, p=tracer_style_sub_menu)
        cmds.menuItem(l="Red", image=media.tracer_red_image, c=bar.set_tracer_red_color, p=tracer_style_sub_menu)
        cmds.menuItem(l="Blue", image=media.tracer_blue_image, c=bar.set_tracer_blue_color, p=tracer_style_sub_menu)
        cmds.menuItem(divider=True, parent=tracer_popup_menu)
        cmds.menuItem(l="Remove", image=media.tracer_remove_image, c=bar.remove_tracer_node, p=tracer_popup_menu)

        tracer_button_widget = wrapInstance(int(mui.MQtUtil.findControl(tracer_button)), QtWidgets.QWidget)
        tracer_button_widget.setToolTip("")






        # Reset anim  -------------------------------------------------------------------------
        reset_values_button = cmds.iconTextButton(l="", h=user_preferences.toolbar_icon_h, w=user_preferences.toolbar_icon_w, image=media.reset_animation_image, c=keyTools.reset_objects_mods, p="rowtoolbar")
        reset_values_button_widget = wrapInstance(int(mui.MQtUtil.findControl(reset_values_button)), QtWidgets.QWidget)
        reset_values_button_widget.setToolTip("")

        reset_values_popup_menu = cmds.popupMenu(parent=reset_values_button)
        cmds.menuItem(l="Set Default Values For Selected", c=keyTools.save_default_values, image=media.reset_animation_image, p=reset_values_popup_menu)
        cmds.menuItem(l="Restore Default Values For Selected", c=keyTools.remove_default_values_for_selected_object, image=media.reset_animation_image, p=reset_values_popup_menu)
        cmds.menuItem(divider=True, parent=reset_values_popup_menu)
        cmds.menuItem(l="Clear All Saved Data", c=keyTools.restore_default_data, image=media.reset_animation_image, p=reset_values_popup_menu)
        cmds.menuItem(divider=True, parent=reset_values_popup_menu)
        cmds.menuItem(l="Help", image=media.help_menu_image, c=lambda x: general.open_url("https://thekeymachine.gitbook.io/base/the-toolbar/animation-tools/reset-to-default"), p=reset_values_popup_menu)



        # Delete anim -------------------------------------------------------------------------
        deleteAnim_button = cmds.iconTextButton(l="", h=user_preferences.toolbar_icon_h, w=user_preferences.toolbar_icon_w, image=media.delete_animation_image, c=bar.mod_delete_animation, p="rowtoolbar")
        deleteAnim_button_widget = wrapInstance(int(mui.MQtUtil.findControl(deleteAnim_button)), QtWidgets.QWidget)
        deleteAnim_button_widget.setToolTip("")




        # Selector -----------------------------------------------------------------------

        def update_button_text():
            if not cmds.control('selector_button', exists=True):
                return

            selected_objects = cmds.ls(selection=True)
            num_selected = len(selected_objects)
            cmds.button('selector_button', edit=True, label=str(num_selected))

        scriptjob_id = cmds.scriptJob(event=["SelectionChanged", update_button_text])



        selector_button = cmds.button('selector_button', l="0", h=user_preferences.toolbar_icon_h, w=user_preferences.toolbar_icon_w, c=bar.selektor_window, p="rowtoolbar")
        selector_button_widget = wrapInstance(int(mui.MQtUtil.findControl(selector_button)), QtWidgets.QWidget)
        selector_button_widget.setToolTip("")

        cmds.separator(w=20, vis=False, p="rowtoolbar")


        # Select opposite ---------------------------------------------------------------------
        select_opposite_button = cmds.iconTextButton(l="", h=user_preferences.toolbar_icon_h, w=user_preferences.toolbar_icon_w, image=media.select_opposite_image, c=keyTools.selectOpposite, p="rowtoolbar")
        select_opposite_button_widget = wrapInstance(int(mui.MQtUtil.findControl(select_opposite_button)), QtWidgets.QWidget)
        select_opposite_button_widget.setToolTip("")



        # Copy opposite -----------------------------------------------------------------------
        copy_opposite_button = cmds.iconTextButton(l="", h=user_preferences.toolbar_icon_h, w=user_preferences.toolbar_icon_w, image=media.copy_opposite_image, c=keyTools.copyOpposite, p="rowtoolbar")
        copy_opposite_button_widget = wrapInstance(int(mui.MQtUtil.findControl(copy_opposite_button)), QtWidgets.QWidget)
        copy_opposite_button_widget.setToolTip("")


        # Mirror -----------------------------------------------------------------------
        mirror_button = cmds.iconTextButton(l="", h=user_preferences.toolbar_icon_h, w=user_preferences.toolbar_icon_w, image=media.mirror_image, c=keyTools.mirror, p="rowtoolbar")
        mirror_button_widget = wrapInstance(int(mui.MQtUtil.findControl(mirror_button)), QtWidgets.QWidget)
        mirror_button_widget.setToolTip("")

        mirror_popup_menu = cmds.popupMenu(parent=mirror_button)
        #cmds.menuItem(l="Mirror to opposite", c=keyTools.mirror_to_opposite, image=media.mirror_image, p=mirror_popup_menu)
        cmds.menuItem(l="Add Excepction Invert", c=keyTools.add_mirror_invert_exception, image=media.mirror_image, p=mirror_popup_menu)
        cmds.menuItem(l="Add Excepction Keep", c=keyTools.add_mirror_keep_exception, image=media.mirror_image, p=mirror_popup_menu)
        cmds.menuItem(l="Remove Exception", c=keyTools.remove_mirror_invert_exception, image=media.mirror_image, p=mirror_popup_menu)
        cmds.menuItem(divider=True, parent=mirror_popup_menu)
        cmds.menuItem(l="Help", image=media.help_menu_image, c=lambda x: general.open_url("https://thekeymachine.gitbook.io/base/the-toolbar/animation-tools/mirror"), p=mirror_popup_menu)




        # Copy Paste Animation -----------------------------------------------------------------------
        copy_paste_animation_button = cmds.iconTextButton(l="", h=user_preferences.toolbar_icon_h, w=user_preferences.toolbar_icon_w, image=media.copy_paste_animation_image, c=keyTools.copy_animation, p="rowtoolbar")
        copy_paste_animation_button_widget = wrapInstance(int(mui.MQtUtil.findControl(copy_paste_animation_button)), QtWidgets.QWidget)
        copy_paste_animation_button_widget.setToolTip("")

        copy_paste_animation_popup_menu = cmds.popupMenu(parent=copy_paste_animation_button)
        cmds.menuItem(l="Copy Animation", c=keyTools.copy_animation, image=media.copy_paste_animation_image, p=copy_paste_animation_popup_menu)
        cmds.menuItem(l="Paste Animation", c=keyTools.paste_animation, image=media.paste_animation_image, p=copy_paste_animation_popup_menu)
        cmds.menuItem(l="Paste Insert", c=keyTools.paste_insert_animation, image=media.paste_insert_animation_image, p=copy_paste_animation_popup_menu)
        cmds.menuItem(l="Paste Opposite", c=keyTools.paste_opposite_animation, image=media.paste_opposite_animation_image, p=copy_paste_animation_popup_menu)
        cmds.menuItem(l="Paste To", c=lambda *_: keyTools.paste_animation_to(), image=media.paste_animation_image, p=copy_paste_animation_popup_menu)
        cmds.menuItem(divider=True, parent=copy_paste_animation_popup_menu)
        cmds.menuItem(l="Copy Pose", c=keyTools.copy_pose, image=media.copy_pose_image, p=copy_paste_animation_popup_menu)
        cmds.menuItem(l="Paste Pose", c=keyTools.paste_pose, image=media.paste_pose_image, p=copy_paste_animation_popup_menu)
        cmds.menuItem(divider=True, parent=copy_paste_animation_popup_menu)

        cmds.menuItem(l="Help", image=media.help_menu_image, c=lambda x: general.open_url("https://thekeymachine.gitbook.io/base/the-toolbar/animation-tools/copy-paste-animation"), p=copy_paste_animation_popup_menu)




        # Select hierarchy -----------------------------------------------------------------------
        select_hierarchy_button = cmds.iconTextButton(l="", h=user_preferences.toolbar_icon_h, w=user_preferences.toolbar_icon_w, image=media.select_hierarchy_image, c=bar.selectHierarchy, p="rowtoolbar")
        select_hierarchy_button_widget = wrapInstance(int(mui.MQtUtil.findControl(select_hierarchy_button)), QtWidgets.QWidget)
        select_hierarchy_button_widget.setToolTip("")


        # Animation offset -----------------------------------------------------------------------
        animation_offset_button = cmds.iconTextButton("anim_offset_button", l="", h=user_preferences.toolbar_icon_h, w=user_preferences.toolbar_icon_w, image=media.animation_offset_image, c=self.toggleAnimOffsetButton, p="rowtoolbar")
        animation_offset_button_widget = wrapInstance(int(mui.MQtUtil.findControl(animation_offset_button)), QtWidgets.QWidget)
        animation_offset_button_widget.setToolTip("")




        # FollowCam------------------------------------------------------------------------------
        create_follow_cam_button = cmds.iconTextButton(l="", image=media.follow_cam_image, h=user_preferences.toolbar_icon_h, w=user_preferences.toolbar_icon_w, c= lambda *args: bar.create_follow_cam(translation=True, rotation=True), p="rowtoolbar")
        create_follow_cam_button_widget = wrapInstance(int(mui.MQtUtil.findControl(create_follow_cam_button)), QtWidgets.QWidget)
        create_follow_cam_button_widget.setToolTip("")

        create_follow_cam_popup_menu = cmds.popupMenu(parent=create_follow_cam_button)
        cmds.menuItem(l="Follow only Translation", c= lambda *args: bar.create_follow_cam(translation=True, rotation=False), image=media.follow_cam_image, p=create_follow_cam_popup_menu)
        cmds.menuItem(l="Follow only Rotation", c= lambda *args: bar.create_follow_cam(translation=False, rotation=True), image=media.follow_cam_image, p=create_follow_cam_popup_menu)
        cmds.menuItem(divider=True, parent=create_follow_cam_popup_menu)
        cmds.menuItem(l="Remove followCam", image=media.remove_followCam, c=bar.remove_followCam, p=create_follow_cam_popup_menu)



        # Copy Link -----------------------------------------------------------------------


        # ------funciones para crear el flashing icon al crear el auto-link callback
        global link_obj_image_timer
        link_obj_image_timer = True

        link_objects_button = None 

        def toggle_link_obj_button_image():
            if not cmds.iconTextButton(link_objects_button, exists=True):
                return
            
            current_image = cmds.iconTextButton(link_objects_button, q=True, image=True)
            new_image = media.link_objects_on_image if current_image == media.link_objects_image else media.link_objects_image
            cmds.iconTextButton(link_objects_button, edit=True, image=new_image)

        def change_link_obj_image(interval):
            while link_obj_image_timer: 
                time.sleep(interval)
                utils.executeDeferred(toggle_link_obj_button_image)

        def start_link_obj_toggle_image_thread():
            global link_obj_image_timer, t
            link_obj_image_timer = True
            t = threading.Thread(target=change_link_obj_image, args=(0.3,))
            t.start()

        def stop_link_obj_toggle_image_thread():
            global link_obj_image_timer
            link_obj_image_timer = False


        # Añade el auto-link callback
        def add_link_objects_callback(*args):
            start_link_obj_toggle_image_thread()
            keyTools.add_link_obj_callbacks()

        # Borra el auto-link callback.
        def remove_link_objects_callback(*args):
            stop_link_obj_toggle_image_thread()
            keyTools.remove_link_obj_callbacks()
            QTimer.singleShot(800, restore_link_objects_image)


        def restore_link_objects_image():
            cmds.iconTextButton(link_objects_button, edit=True, image=media.link_objects_image)


        global link_checkbox_state
        link_checkbox_state = False

        def toggle_auto_link_callback(*args):
            global link_checkbox_state

            link_checkbox_state = not link_checkbox_state

            if link_checkbox_state:
                add_link_objects_callback()
            else:
                remove_link_objects_callback()

            cmds.menuItem('auto_link_obj', edit=True, checkBox=link_checkbox_state)



        link_objects_button = cmds.iconTextButton(l="", h=user_preferences.toolbar_icon_h, w=user_preferences.toolbar_icon_w, image=media.link_objects_image, c=keyTools.mod_link_objects, p="rowtoolbar")
        link_objects_button_widget = wrapInstance(int(mui.MQtUtil.findControl(link_objects_button)), QtWidgets.QWidget)
        link_objects_button_widget.setToolTip("")

        link_objects_popup_menu = cmds.popupMenu(button=3, ctl=False, alt=False, parent=link_objects_button)
        cmds.menuItem(l="Copy Link Position", image=media.link_objects_image, c=keyTools.copy_link, p=link_objects_popup_menu)
        cmds.menuItem(l="Paste Link Position", image=media.link_objects_image, c=keyTools.paste_link, p=link_objects_popup_menu)
        cmds.menuItem(divider=True, parent=link_objects_popup_menu)
        cmds.menuItem('auto_link_obj', l="Auto-link", checkBox=link_checkbox_state, c=toggle_auto_link_callback, p=link_objects_popup_menu)

        cmds.menuItem(divider=True, parent=link_objects_popup_menu)
        cmds.menuItem(l="Help", image=media.help_menu_image, c=lambda x: general.open_url("https://thekeymachine.gitbook.io/base/the-toolbar/animation-tools/link-objects"), p=link_objects_popup_menu)





        # Copy WorldSpace ----------------------------------------------------------------------------
        copy_worldspace_button = cmds.iconTextButton(l="", h=user_preferences.toolbar_icon_h, w=user_preferences.toolbar_icon_w, c=bar.mod_copy_worldspace_animation, image=media.copy_worldspace_animation_image, parent="rowtoolbar")
        copy_worldspace_button_widget = wrapInstance(int(mui.MQtUtil.findControl(copy_worldspace_button)), QtWidgets.QWidget)
        copy_worldspace_button_widget.setToolTip("")

        copy_worldspace_button_popup_menu = cmds.popupMenu(parent=copy_worldspace_button)
        cmds.menuItem(l="Copy Worldspace - All Animation", image=media.copy_worldspace_animation_image, c=bar.color_copy_worldspace_animation, p=copy_worldspace_button_popup_menu)
        cmds.menuItem(l="Copy Worldspace - Selected Range", image=media.copy_worldspace_animation_image, c=bar.copy_range_worldspace_animation, p=copy_worldspace_button_popup_menu)
        cmds.menuItem(l="Paste Worldspace", image=media.paste_worldspace_animation_image, c=bar.color_paste_worldspace_animation, p=copy_worldspace_button_popup_menu) 
        cmds.menuItem(divider=True, parent=copy_worldspace_button_popup_menu)
        cmds.menuItem(l="Copy Worldspace - Current Frame", image=media.copy_worldspace_frame_animation_image, c=bar.copy_worldspace_single_frame, p=copy_worldspace_button_popup_menu)
        cmds.menuItem(l="Paste Worldspace", image=media.paste_worldspace_frame_animation_image, c=bar.paste_worldspace_single_frame, p=copy_worldspace_button_popup_menu) 
        cmds.menuItem(divider=True, parent=copy_worldspace_button_popup_menu)
        cmds.menuItem(l="Help",  c=lambda x: general.open_url("https://thekeymachine.gitbook.io/base/the-toolbar/animation-tools/copy-worldspace"), image=media.help_menu_image, parent=copy_worldspace_button_popup_menu)



        # Temp Pivot ----------------------------------------------------------------------------
        temp_pivot_button = cmds.iconTextButton(l="", h=user_preferences.toolbar_icon_h, w=user_preferences.toolbar_icon_w, image=media.temp_pivot_image, c=lambda *args: bar.create_temp_pivot(False), parent="rowtoolbar")
        temp_pivot_button_widget = wrapInstance(int(mui.MQtUtil.findControl(temp_pivot_button)), QtWidgets.QWidget)
        temp_pivot_button_widget.setToolTip("")

        temp_pivot_button_popup_menu = cmds.popupMenu(parent=temp_pivot_button)
        cmds.menuItem(l="Last pivot used", c=lambda *args: bar.create_temp_pivot(True), image=media.temp_pivot_image, p=temp_pivot_button_popup_menu)
        cmds.menuItem(divider=True, parent=temp_pivot_button_popup_menu)
        cmds.menuItem(l="Help",  c=lambda x: general.open_url("https://thekeymachine.gitbook.io/base/the-toolbar/animation-tools/temp-pivots"), image=media.help_menu_image, parent=temp_pivot_button_popup_menu)



        # Micro Move ----------------------------------------------------------------------------
        micro_move_button = cmds.iconTextButton('micro_move_button', l="", h=user_preferences.toolbar_icon_h, w=user_preferences.toolbar_icon_w, image=media.ruler_image, c=self.toggle_micro_move_button, parent="rowtoolbar")
        micro_move_button_widget = wrapInstance(int(mui.MQtUtil.findControl(micro_move_button)), QtWidgets.QWidget)
        micro_move_button_widget.setToolTip("")


        # Key Menu -------------------------------------------------------------------------------
        block_keys_button = cmds.iconTextButton(l="", w=user_preferences.toolbar_icon_w, h=user_preferences.toolbar_icon_h, image=media.reblock_keys_image, c=keyTools.share_keys, p="rowtoolbar")
        
        block_keys_popup_menu = cmds.popupMenu(button=1, ctl=False, alt=False, parent=block_keys_button)
        block_keys_button_widget = wrapInstance(int(mui.MQtUtil.findControl(block_keys_button)), QtWidgets.QWidget)
        block_keys_button_widget.setToolTip("")


        # ReBlock & Share Keys
        reblock_keys_menu = cmds.menuItem(l="reBlock", c=keyTools.reblock_move, image=media.reblock_keys_image, p=block_keys_popup_menu)
        share_keys_menu = cmds.menuItem(l="Share Keys", c=keyTools.share_keys, image=media.reblock_keys_image, p=block_keys_popup_menu)

        # Bake Anim 
        bake_animation_sub_menu = cmds.menuItem(l="Bake Anim", c=keyTools.bake_anim_window, image=media.reblock_keys_image, p=block_keys_popup_menu)

        # Orbit
        orbit_sub_menu = cmds.menuItem(l="ToolBox Orbit", c=lambda x: ui.orbit_window(0, 0), image=media.reblock_keys_image, p=block_keys_popup_menu)
        # Gimbal Fixer
        gimbal_fixer_sub_menu = cmds.menuItem(l="Gimbal Fixer", c=bar.gimbal_fixer_window, image=media.reblock_keys_image, p=block_keys_popup_menu)

        cmds.setParent('..', menu=True)



        # Anim tangents ----------------------------------------------------------------------------

        cmds.separator(style='none', width=22, p="rowtoolbar")
        cmds.iconTextButton(l="", h=user_preferences.toolbar_icon_h, w=user_preferences.toolbar_icon_w, image=media.auto_tangent_image,  c=lambda *args: bar.setTangent('auto'), annotation="Auto Tangent", p="rowtoolbar")
        cmds.iconTextButton(l="", h=user_preferences.toolbar_icon_h, w=20, image=media.spline_tangent_image,  c=lambda *args: bar.setTangent('spline'),  annotation="Spline Tangent", p="rowtoolbar")
        cmds.iconTextButton(l="", h=user_preferences.toolbar_icon_h, w=20, image=media.linear_tangent_image,  c=lambda *args: bar.setTangent('linear'),  annotation="Linear Tangent", p="rowtoolbar")
        cmds.iconTextButton(l="", h=user_preferences.toolbar_icon_h, w=20, image=media.step_tangent_image,  c=lambda *args: bar.setTangent('step'),  annotation="Step Tangent", p="rowtoolbar")
        cmds.separator(style='none', width=18, p="rowtoolbar")
       
        # Selection Sets  ----------------------------------------------------------------------------


        selection_sets_button = cmds.iconTextButton("toggle_selection_sets_workspace_b", l='', image=media.selection_sets_image, h=user_preferences.toolbar_icon_h, w=user_preferences.toolbar_icon_w, c=self.toggle_selection_sets_workspace, p="rowtoolbar")
        selection_sets_button_widget = wrapInstance(int(mui.MQtUtil.findControl(selection_sets_button)), QtWidgets.QWidget)
        selection_sets_button_widget.setToolTip("")

        
        # customGraph ----------------------------------------------------------------------------
  
        def open_customGraph():

            import TheKeyMachine.core.customGraph as cg # type: ignore
            cg.createCustomGraph()


        open_custom_graph_button = cmds.iconTextButton(l="", image=media.customGraph_image, h=user_preferences.toolbar_icon_h, w=user_preferences.toolbar_icon_w, c=open_customGraph, p="rowtoolbar")
        open_custom_graph_button_widget = wrapInstance(int(mui.MQtUtil.findControl(open_custom_graph_button)), QtWidgets.QWidget)
        open_custom_graph_button_widget.setToolTip("")


        """
        # custom tools ----------------------------------------------------------------------------
        if CUSTOM_TOOLS_MENU:
            cmds.separator(style='none', width=18, p="rowtoolbar")
            toolBox_button = cmds.iconTextButton(l="", image=media.custom_tools_image, h=user_preferences.toolbar_icon_h, w=user_preferences.toolbar_icon_w, vis=CUSTOM_TOOLS_MENU, p="rowtoolbar")
        else:
            cmds.separator(style='none', width=10, p="rowtoolbar")
            toolBox_button = cmds.iconTextButton(l="", image=media.custom_tools_image, h=1, w=1, vis=CUSTOM_TOOLS_MENU)

        toolBox_button_widget = wrapInstance(int(mui.MQtUtil.findControl(toolBox_button)), QtWidgets.QWidget)
        toolBox_button_widget.setToolTip("")

        toolBox_popup_menu = cmds.popupMenu(button=1, ctl=False, alt=False, parent=toolBox_button)


        def initialize_tool_menu(*args):
            importlib.reload(connectToolBox)
            # Eliminar los elementos existentes del menú
            children = cmds.popupMenu(toolBox_popup_menu, q=True, itemArray=True)
            if children:
                for child in children:
                    label = cmds.menuItem(child, q=True, label=True)
                    cmds.deleteUI(child)
            
            # Generar un mapeo de nombre a ID
            name_to_id = {}
            for i in range(1, 100):  # Asumiendo un máximo de 99 herramientas
                tool_id = f"t{str(i).zfill(2)}"
                try:
                    tool_name = getattr(connectToolBox, f"{tool_id}_name")
                    name_to_id[tool_name] = tool_id
                except AttributeError:
                    break  # Sal del bucle si hemos alcanzado el último ID definido

            # Definir una función interna para crear las funciones de comando
            def create_command_func(command, is_python):
                if is_python:
                    return lambda x: exec(command)
                else:
                    return lambda x: mel.eval(command)

            # Iterar sobre tool_order usando el nombre para encontrar el ID
            for tool_name in connectToolBox.tool_order:
                if tool_name:  # Esta condición se cumple si tool_name no está vacío
                    tool_id = name_to_id.get(tool_name)
                    if not tool_id:
                        print(f"ID not found for the tool named '{tool_name}'")
                        continue

                    try:
                        name = getattr(connectToolBox, f"{tool_id}_name")
                        image = getattr(connectToolBox, f"{tool_id}_image")
                        is_python = getattr(connectToolBox, f"{tool_id}_is_python")
                        command = getattr(connectToolBox, f"{tool_id}_command")

                        if not name:
                            continue

                        # fix para mostrar imagenes
                        if image == "green_dot.png":
                            image = media.green_dot_image

                        if image == "blue_dot.png":
                            image = media.blue_dot_image

                        if image == "red_dot.png":
                            image = media.red_dot_image

                        if image == "grey_dot.png":
                            image = media.grey_dot_image

                        if image == "yellow_dot.png":
                            image = media.yellow_dot_image


                        if name == "separator":
                            cmds.menuItem(divider=True, parent=toolBox_popup_menu)
                        else:
                            command_func = create_command_func(command, is_python)
                            cmds.menuItem(label=name, image=image, parent=toolBox_popup_menu, command=command_func)
                    except AttributeError:
                        print(f"ID not found for the tool named '{tool_id}'")

            # Añadir los elementos fijos al final del menú
            cmds.menuItem(divider=True, vis=CUSTOM_TOOLS_EDITABLE_BY_USER, parent=toolBox_popup_menu)
            cmds.menuItem(label="Open config file", vis=CUSTOM_TOOLS_EDITABLE_BY_USER, image=media.settings_image, c=lambda x: general.open_file("TheKeyMachine_user_data/connect/tools", "tools.py"), parent=toolBox_popup_menu)
            cmds.menuItem(label="Reload menu", vis=CUSTOM_TOOLS_EDITABLE_BY_USER, image=media.reload_image, c=initialize_tool_menu, parent=toolBox_popup_menu)

        # Llama a la función para inicializar el menú
        initialize_tool_menu()
        """


        """
        # custom scripts ----------------------------------------------------------------------------

        if CUSTOM_SCRIPTS_MENU:
            customScripts_button = cmds.iconTextButton(l="", image=media.custom_scripts_image, vis=CUSTOM_SCRIPTS_MENU, h=user_preferences.toolbar_icon_h, w=user_preferences.toolbar_icon_w, p="rowtoolbar")
        else:
            customScripts_button = cmds.iconTextButton(l="", image=media.custom_scripts_image, vis=CUSTOM_SCRIPTS_MENU, h=1, w=1)

        customScripts_button_widget = wrapInstance(int(mui.MQtUtil.findControl(customScripts_button)), QtWidgets.QWidget)
        customScripts_button_widget.setToolTip("")

        customScripts_popup_menu = cmds.popupMenu(button=1, ctl=False, alt=False, parent=customScripts_button)


        def initialize_scripts_menu(*args):

            importlib.reload(cbScripts)
            
            # Eliminar los elementos existentes del menú
            children = cmds.popupMenu(customScripts_popup_menu, q=True, itemArray=True)
            if children:
                for child in children:
                    label = cmds.menuItem(child, q=True, label=True)
                    cmds.deleteUI(child)
                    
            # Generar un mapeo de nombre a ID
            name_to_id = {}
            for i in range(1, 100):  # Asumiendo un máximo de 99 scripts
                script_id = f"s{str(i).zfill(2)}"
                try:
                    script_name = getattr(cbScripts, f"{script_id}_name")
                    name_to_id[script_name] = script_id
                except AttributeError:
                    break  # Sal del bucle si hemos alcanzado el último ID definido

            # Definir una función interna para crear las funciones de comando
            def create_command_func(command, is_python):
                if is_python:
                    return lambda x: exec(command)
                else:
                    return lambda x: mel.eval(command)

            # Iterar sobre script_order usando el nombre para encontrar el ID
            for script_name in cbScripts.scripts_order:
                if script_name:  # Esta condición se cumple si script_name no está vacío
                    script_id = name_to_id.get(script_name)
                    if not script_id:
                        print(f"ID not found for the script named '{script_name}'")
                        continue

                    try:
                        name = getattr(cbScripts, f"{script_id}_name")
                        image = getattr(cbScripts, f"{script_id}_image")
                        is_python = getattr(cbScripts, f"{script_id}_is_python")
                        command = getattr(cbScripts, f"{script_id}_command")

                        if not name:
                            continue

                        # fix para mostrar imagenes
                        if image == "green_dot.png":
                            image = media.green_dot_image

                        if image == "blue_dot.png":
                            image = media.blue_dot_image

                        if image == "red_dot.png":
                            image = media.red_dot_image

                        if image == "grey_dot.png":
                            image = media.grey_dot_image

                        if image == "yellow_dot.png":
                            image = media.yellow_dot_image


                        if name == "separator":
                            cmds.menuItem(divider=True, parent=customScripts_popup_menu)
                        else:
                            command_func = create_command_func(command, is_python)
                            cmds.menuItem(label=name, image=image, parent=customScripts_popup_menu, command=command_func)
                    except AttributeError:
                        print(f"ID not found for the script named '{script_id}'")

            # Añadir los elementos fijos al final del menú
            cmds.menuItem(divider=True, vis=CUSTOM_SCRIPTS_EDITABLE_BY_USER, parent=customScripts_popup_menu)
            cmds.menuItem(label="Open config file", vis=CUSTOM_SCRIPTS_EDITABLE_BY_USER, image=media.settings_image, c=lambda x: general.open_file("TheKeyMachine_user_data/connect/scripts", "scripts.py"), parent=customScripts_popup_menu)
            cmds.menuItem(label="Reload menu", vis=CUSTOM_SCRIPTS_EDITABLE_BY_USER, image=media.reload_image, c=initialize_scripts_menu, parent=customScripts_popup_menu)

        # Llama a la función para inicializar el menú
        initialize_scripts_menu()
        """




        #_____________________ configAbout Menu _____________________________#

        overshootSliders = False
        
        def _setOvershoot(state):
            for slider in {barBlendSlider_widget, barTweenSlider_widget}:
                slider.setOvershoot(state)
        _setOvershoot(overshootSliders)


        toolbar_config_button = cmds.iconTextButton("settings_toolbar_button", l="", w=user_preferences.toolbar_icon_w, h=user_preferences.toolbar_icon_h, image=media.settings_image, p="rowtoolbar")
        # Wrap the Maya control into a Qt widget
        toolbar_config_button_widget = wrapInstance(
            int(mui.MQtUtil.findControl(toolbar_config_button)),
            QtWidgets.QPushButton
        )

        # Build your menu with your mw.MenuWidget; make sure the button is the PARENT
        toolbar_menu = mw.MenuWidget(parent=toolbar_config_button_widget)

        # === Help submenu ===
        help_menu = toolbar_menu.addMenu(QtGui.QIcon(media.help_menu_image), "Help")
        help_menu.addAction(QtGui.QIcon(media.discord_image), "Discord Community",
                            lambda: general.open_url("https://discord.gg/G2J5yyjz"))
        help_menu.addAction(QtGui.QIcon(media.help_menu_image), "Knowledge base",
                            lambda: general.open_url("https://thekeymachine.gitbook.io/base"))
        help_menu.addAction(QtGui.QIcon(media.youtube_image), "Youtube channel",
                            lambda: general.open_url("https://www.youtube.com/@TheKeyMachineAnimationTools"))

        # === Config submenu ===
        config_menu = toolbar_menu.addMenu(QtGui.QIcon(media.settings_image), "Config")

        config_menu.addSection("Shelf icon")
        config_menu.addAction("Add Toggle Button To Shelf", self.create_shelf_icon)

        config_menu.addSection("Tools settings")
        show_tooltips_action = config_menu.addAction("Show tooltips")
        show_tooltips_action.setCheckable(True)
        show_tooltips_action.setChecked(show_tooltips)
        show_tooltips_action.toggled.connect(toggle_tooltips)

        overshoot_action = config_menu.addAction("Overshoot Sliders")
        overshoot_action.setCheckable(True)
        overshoot_action.setChecked(overshootSliders)
        overshoot_action.toggled.connect(_setOvershoot)

        config_menu.addSection("Toolbar's icons size")
        size_group = QActionGroup(config_menu)
        small_action = config_menu.addAction("Small")
        medium_action = config_menu.addAction("Medium")
        big_action = config_menu.addAction("Big")
        for act in (small_action, medium_action, big_action):
            act.setCheckable(True)
            size_group.addAction(act)

        small_action.triggered.connect(lambda: set_icon_size_small())
        medium_action.triggered.connect(lambda: set_icon_size_medium())
        big_action.triggered.connect(lambda: set_icon_size_big())

        current_size = get_current_icon_size()
        {"Small": small_action, "Medium": medium_action, "Big": big_action}.get(current_size, medium_action).setChecked(True)

        config_menu.addSection("Hotkeys")
        config_menu.addAction("Add TheKeyMachine Hotkeys", hotkeys.create_TheKeyMachine_hotkeys)

        config_menu.addSection("General")
        config_menu.addAction(QtGui.QIcon(media.reload_image), "Reload", self.reload)

        # Separators and others
        toolbar_menu.addSeparator()
        toolbar_menu.addAction(QtGui.QIcon(media.uninstall_image), "Uninstall", ui.uninstall)
        toolbar_menu.addSeparator()
        toolbar_menu.addAction(QtGui.QIcon(media.about_image), "About", ui.about_window)

        # --- OPEN AT CURSOR POSITION (left & right click) ---
        # IMPORTANT: don't call setMenu(); we handle showing explicitly at the cursor
        def _open_menu_at_cursor():
            toolbar_menu.popup(QtGui.QCursor.pos())

        toolbar_config_button_widget.clicked.connect(_open_menu_at_cursor)
        toolbar_config_button_widget.setContextMenuPolicy(QtCore.Qt.CustomContextMenu)
        toolbar_config_button_widget.customContextMenuRequested.connect(lambda _pos: _open_menu_at_cursor())

        

        # crea los tooltips
        update_tooltips()


tb = toolbar()
