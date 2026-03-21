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

# Maya related imports
from maya import cmds, mel, utils, OpenMayaUI as mui
from maya.app.general.mayaMixin import MayaQWidgetDockableMixin

try:
    from PySide6 import QtWidgets, QtCore, QtGui
    from PySide6.QtCore import QTimer
    from shiboken6 import wrapInstance, isValid

    QActionGroup = QtGui.QActionGroup

except ImportError:
    from PySide2 import QtWidgets, QtCore, QtGui
    from PySide2.QtCore import QTimer
    from shiboken2 import wrapInstance, isValid

    QActionGroup = QtWidgets.QActionGroup


# Standard library imports
import os
import re
import time
import json
import shutil
import platform
import threading
import importlib

from functools import partial


# -----------------------------------------------------------------------------------------------------------------------------
#                                    We load the necessary modules for TheKeyMachine                                          #
# -----------------------------------------------------------------------------------------------------------------------------


import TheKeyMachine.mods.generalMod as general  # type: ignore
import TheKeyMachine.mods.uiMod as ui  # type: ignore
import TheKeyMachine.mods.keyToolsMod as keyTools  # type: ignore

# import TheKeyMachine.mods.selSetsMod as selSets  # type: ignore
import TheKeyMachine.mods.helperMod as helper  # type: ignore
import TheKeyMachine.mods.mediaMod as media  # type: ignore
import TheKeyMachine.mods.styleMod as style  # type: ignore
import TheKeyMachine.mods.barMod as bar  # type: ignore
import TheKeyMachine.mods.hotkeysMod as hotkeys  # type: ignore
import TheKeyMachine.mods.settingsMod as settings  # type: ignore
import TheKeyMachine.core.customGraph as cg  # type: ignore

from TheKeyMachine.widgets import sliderWidget as sw  # type: ignore
from TheKeyMachine.widgets import customWidgets as cw  # type: ignore
from TheKeyMachine.widgets import util as wutil  # type: ignore
import TheKeyMachine.tooltips as tooltips  # type: ignore
import TheKeyMachine.tooltips.tooltip as tt  # type: ignore
import TheKeyMachine.sliders as sliders  # type: ignore


# -----------------------------------------------------------------------------------------------------------------------------
#              TheKeyMachine configuration is loaded from the JSON, or the default installation paths are used.               #
# -----------------------------------------------------------------------------------------------------------------------------


INSTALL_PATH = general.config["INSTALL_PATH"]
USER_FOLDER_PATH = general.config["USER_FOLDER_PATH"]
UPDATER = general.config["UPDATER"]
BUG_REPORT = general.config["BUG_REPORT"]
CUSTOM_TOOLS_MENU = general.config["CUSTOM_TOOLS_MENU"]
CUSTOM_TOOLS_EDITABLE_BY_USER = general.config["CUSTOM_TOOLS_EDITABLE_BY_USER"]
CUSTOM_SCRIPTS_MENU = general.config["CUSTOM_SCRIPTS_MENU"]
CUSTOM_SCRIPTS_EDITABLE_BY_USER = general.config["CUSTOM_SCRIPTS_EDITABLE_BY_USER"]


# -----------------------------------------------------------------------------------------------------------------------------
#    It attempts to load the user_preferences. If this is a new installation, it won't exist and the file must be created     #
# -----------------------------------------------------------------------------------------------------------------------------


USER_PREFERENCE_FILE = os.path.normpath(os.path.join(USER_FOLDER_PATH, "TheKeyMachine_user_data", "preferences", "user_preferences.py"))
USER_PREFERENCE_FILE_CODE = """
#____________________ TheKeyMachine User Preferences  ________________________ #

show_tooltips = True
toolbar_icon_w = 28
toolbar_icon_h = 28
toolbar_size = 1580
"""


if not os.path.exists(USER_PREFERENCE_FILE):
    os.makedirs(os.path.dirname(USER_PREFERENCE_FILE), exist_ok=True)
    with open(USER_PREFERENCE_FILE, "w") as file:
        file.write(USER_PREFERENCE_FILE_CODE)

# Attempt to import the user preferences module
try:
    from TheKeyMachine_user_data.preferences import user_preferences  # type: ignore
except ImportError as e:
    print(f"Error al importar: {e}")


# -----------------------------------------------------------------------------------------------------------------------------
#      It attempts to load the Connect modules. If this is a new installation, they need to be copied to the user folder      #
# -----------------------------------------------------------------------------------------------------------------------------


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
    os.path.join(USER_FOLDER_PATH, "TheKeyMachine_user_data/connect/scripts/__init__.py"),
]

# Ensure that destination directories exist
os.makedirs(os.path.dirname(destino_toolbox), exist_ok=True)
os.makedirs(os.path.dirname(destino_scripts), exist_ok=True)

# Create empty __init__.py files if they don't already exist
for init_path in init_paths:
    if not os.path.isfile(init_path):
        open(init_path, "a").close()

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
    import TheKeyMachine_user_data  # type: ignore

    importlib.reload(TheKeyMachine_user_data)  # type: ignore
    import TheKeyMachine_user_data.connect  # type: ignore

    import TheKeyMachine_user_data.connect.tools.tools as connectToolBox  # type: ignore
    import TheKeyMachine_user_data.connect.scripts.scripts as cbScripts  # type: ignore
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
    tt,
    tooltips,
    sw,
    cw,
]

for module in modules_to_reload:
    importlib.reload(module)


# -----------------------------------------------------------------------------------------------------------------------------
#                                          Creation of the toolbar and UI class                                               #
# -----------------------------------------------------------------------------------------------------------------------------


WorkspaceName = "k"
selection_sets_workspace = "s"


COLOR = ui.Color()


class toolbar(MayaQWidgetDockableMixin, QtWidgets.QDialog):
    open_new_scene_scriptJob = None
    selection_script_job = None

    def __init__(self, parent=None):
        super().__init__(parent=parent)
        self.setWindowTitle("TheKeyMachine")
        self.setObjectName(WorkspaceName)
        self.setContextMenuPolicy(QtCore.Qt.PreventContextMenu)

        self.shelf_painter = None
        self.current_layout = cmds.workspaceLayoutManager(q=True, current=True)

        # Initial state variables from settingsMod
        self.current_blend_slider_mode = settings.get_setting("current_blend_slider_mode", "BN")
        self.toggleAnimOffsetButtonState = settings.get_setting("toggleAnimOffsetButtonState", False)
        self.micro_move_button_state = settings.get_setting("micro_move_button_state", False)
        self.link_checkbox_state = settings.get_setting("link_checkbox_state", False)

        self.docking_position = settings.get_setting("docking_position", ["TimeSlider", "top"])
        self.docking_orients = {
            "top": "To Top",
            "bottom": "To Bottom",
        }
        self.docking_layouts = {
            "AttributeEditor": "Attribute Editor",
            "ChannelBoxLayerEditor": "Channel Box",
            "Outliner": "Outliner",
            "MainPane": "Main Viewport",
            "TimeSlider": "Time Slider",
            "RangeSlider": "Range Slider",
            "Shelf": "Shelf",
        }

        self.bar_center_value = 10
        self.anim_offset_run_timer = True
        self.micro_move_run_timer = True
        self.animation_offset_original_values = {}
        self.setgroup_states = {}
        self.setgroup_buttons = {}
        self.run_centerToolbar = False

        # Link object runtime states
        self.link_obj_image_timer = False
        self.link_obj_toggle_state = False
        self.link_obj_thread = None

        # When loading a new scene, the on_scene_opened() function is executed, which includes, among other things, the function to update the selectionSets.
        # This first if statement checks whether the scriptJob exists; if not, it either creates or deletes it.
        if toolbar.open_new_scene_scriptJob is not None and self.isScriptJobActive(toolbar.open_new_scene_scriptJob):
            cmds.scriptJob(kill=toolbar.open_new_scene_scriptJob, force=True)

        # Function that runs when new scenes are opened
        def on_scene_opened():
            if not isValid(self):
                return
            self.update_selectionSets_on_new_scene()
            self.update_popup_menu()

        toolbar.open_new_scene_scriptJob = cmds.scriptJob(event=("SceneOpened", on_scene_opened))

        # Utility for determining screen resolution
        screen_width, screen_height = wutil.get_screen_resolution()
        self.screen_width = screen_width

        self.buildUI()

        # Attempt to load customGraph
        QTimer.singleShot(6000, self.load_customGraph_try_01)

    def closeEvent(self, event):
        """
        Handles the close event for the toolbar window.
        Stops all background threads and performs necessary cleanup.
        """
        # Stop animation offset thread
        self.anim_offset_run_timer = False
        if hasattr(self, "anim_offset_thread") and self.anim_offset_thread and self.anim_offset_thread.is_alive():
            self.anim_offset_thread.join(timeout=0.5)

        # Stop micro move thread
        self.micro_move_run_timer = False
        if hasattr(self, "micro_move_thread") and self.micro_move_thread and self.micro_move_thread.is_alive():
            self.micro_move_thread.join(timeout=0.5)

        # Stop link objects image toggle thread
        self.link_obj_image_timer = False
        if hasattr(self, "link_obj_thread") and self.link_obj_thread and self.link_obj_thread.is_alive():
            self.link_obj_thread.join(timeout=0.5)

        # Cleanup painter
        if self.shelf_painter and isValid(self.shelf_painter):
            try:
                self.shelf_painter.setParent(None)
                self.shelf_painter.deleteLater()
            except Exception:
                pass
            self.shelf_painter = None

        super().closeEvent(event)

    def showWindow(self):
        # Build up kwargs for the visibleChangeCommand
        visible_change_kwargs = {
            "visibleChangeCommand": self.visible_change_command,
        }

        # Show the window first to ensure parenting is established
        self.show(dockable=True, retain=False, **visible_change_kwargs)

        # Now we can safely check for workspace names
        try:
            parent = self.parent()
            workspace_control = parent.objectName() if parent and isValid(parent) else self.objectName() + "WorkspaceControl"
        except (RuntimeError, AttributeError):
            workspace_control = self.objectName() + "WorkspaceControl"

        # Build up kwargs for the workspaceControl command
        kwargs = {
            "e": True,
            "visibleChangeCommand": self.visible_change_command,
        }

        if self.isFloating():
            kwargs["tp"] = ["west", 0]
            kwargs["rsw"] = 900
            kwargs["rsh"] = 40

        # Check if it was just created
        if cmds.workspaceControl(workspace_control, q=True, exists=True):
            try:
                layout, orient = self.docking_position
                if wutil.check_visible_layout(layout):
                    dock_to = self.get_dock_to_control_name(layout)
                    cmds.workspaceControl(workspace_control, edit=True, dtc=(dock_to, orient))

                cmds.workspaceControl(workspace_control, edit=True, tabPosition=["west", 0])
            except Exception:
                pass

            # Update the workspace control with our kwargs (like visibleChangeCommand)
            cmds.workspaceControl(workspace_control, **kwargs)

        # Force initial resize
        QTimer.singleShot(200, self.shelf_tabbar)
        QTimer.singleShot(500, self.update_height)

    def visible_change_command(self, *args):
        if not isValid(self):
            return

        if not self.isDockable():
            return
        if self.current_layout != cmds.workspaceLayoutManager(q=1, current=True):
            self.current_layout = cmds.workspaceLayoutManager(q=1, current=True)
            if not self.isVisible():
                if isValid(self):
                    cmds.evalDeferred(show, lowestPriority=True)

                if self.shelf_painter and isValid(self.shelf_painter):
                    self.shelf_painter.show()
                else:
                    cmds.evalDeferred(self.shelf_tabbar, lowestPriority=True)
                return

        if not self.isFloating():
            workspace_control = self.parent().objectName() if self.parent() else self.objectName() + "WorkspaceControl"
            if cmds.workspaceControl(workspace_control, q=True, collapse=True):
                timer = QTimer(self)
                timer.setSingleShot(True)

                timer.timeout.connect(
                    partial(
                        cmds.workspaceControl,
                        workspace_control,
                        e=True,
                        collapse=False,
                        tp=["west", 0],
                    )
                )
                timer.start(100)
            if self.shelf_painter and isValid(self.shelf_painter):
                self.shelf_painter.show()
            else:
                cmds.evalDeferred(self.shelf_tabbar, lowestPriority=True)
        else:
            if self.shelf_painter and isValid(self.shelf_painter):
                self.shelf_painter.hide()

        self.update_height()

    def shelf_tabbar(self):
        if not isValid(self):
            return

        if self.shelf_painter and isValid(self.shelf_painter):
            try:
                self.shelf_painter.setParent(None)
                self.shelf_painter.deleteLater()
            except Exception:
                pass

            self.shelf_painter = None

        workspace_control = self.parent().objectName() if self.parent() else self.objectName() + "WorkspaceControl"
        qctrl = mui.MQtUtil.findControl(workspace_control)
        control = wutil.get_maya_qt(qctrl)
        tab_handle = control.parent().parent()

        if self.isFloating():
            return tab_handle.tabBar().setVisible(False)

        self.shelf_painter = cw.QFlatShelfPainter(tab_handle)
        self.shelf_painter.setGeometry(tab_handle.geometry())
        self.shelf_painter.updateDrawingParameters(tabbar_width=tab_handle.tabBar().geometry())
        self.shelf_painter.move(tab_handle.tabBar().pos())

        self.shelf_painter.show()
        tab_handle.tabBar().setVisible(True)

    def update_height(self):
        if not self.isFloating():
            workspace_control = self.parent().objectName() if self.parent() else self.objectName() + "WorkspaceControl"
            tkm_widget = mui.MQtUtil.findControl(workspace_control)
            if not tkm_widget:
                return
            tkm_ui = wutil.get_maya_qt(tkm_widget, QtWidgets.QWidget)
            tkm_ui = tkm_ui.parent().parent()

            self.setSizePolicy(QtWidgets.QSizePolicy.Expanding, QtWidgets.QSizePolicy.Expanding)
            self.main_toolbar_widget._update_height()
            tkm_ui.resize(tkm_ui.width(), wutil.DPI(self.main_toolbar_widget.height() + 4))
            # tkm_ui.setFixedHeight(wutil.DPI(self.main_toolbar_widget.height() + 4))

    def resizeEvent(self, event):
        super().resizeEvent(event)
        # Trigger height update when internal width changes (wrapping happens)
        self.update_height()

    def get_dock_to_control_name(self, layout):
        if layout == "TimeSlider":
            return mel.eval('getUIComponentToolBar("Time Slider", false)')
        elif layout == "RangeSlider":
            return mel.eval('getUIComponentToolBar("Range Slider", false)')
        elif layout == "Shelf":
            return mel.eval('getUIComponentToolBar("Shelf", false)')
        return layout

    def dock_to_ui(self, layout=None, orient=None):
        if not layout:
            layout_name = self.dock_ac_group.checkedAction().text()
            index = list(self.docking_layouts.values()).index(layout_name)
            layout = list(self.docking_layouts.keys())[index]
        if not orient:
            orient_name = self.pos_ac_group.checkedAction().text()
            index = list(self.docking_orients.values()).index(orient_name)
            orient = list(self.docking_orients.keys())[index]

        # Enable / Disable actions
        self.pos_ac_group.checkedAction().setEnabled(False)
        self.dock_ac_group.checkedAction().setEnabled(False)

        for group in [self.pos_ac_group, self.dock_ac_group]:
            for action in group.actions():
                if action and isValid(action):
                    action.setEnabled(not action.isChecked())

        # Build up kwargs for the workspaceControl command
        kwargs = {
            "e": True,
            "visibleChangeCommand": self.visible_change_command,
            "tp": ["west", 0],
            "rsw": 900,
            "rsh": 40,
        }

        if wutil.check_visible_layout(layout):
            dock_to = self.get_dock_to_control_name(layout)
            kwargs["dockToControl"] = [dock_to, orient]
            self.docking_position = [layout, orient]
            settings.set_setting("docking_position", self.docking_position)

        # Make the workspaceControl call just once
        workspace_control = self.parent().objectName() if self.parent() else self.objectName() + "WorkspaceControl"
        cmds.workspaceControl(workspace_control, **kwargs)

    def update_dock_menu(self):
        """Update the enabled state of dock buttons before the menu is shown"""
        if not isValid(self.dock_menu):
            return

        for action in self.dock_menu.actions():
            layout = next(
                (key for key, name in self.docking_layouts.items() if name == action.text()),
                None,
            )
            if layout:
                if layout == self.docking_position[0]:
                    action.setEnabled(False)
                    continue
                action.setEnabled(wutil.check_visible_layout(layout))

    def _create_dock_menu(self):
        self.dock_menu = cw.MenuWidget(QtGui.QIcon(media.dock_image), "Dock Window", description="Dock the toolbar to different Maya UI panels.")

        self.pos_ac_group = QActionGroup(self)
        for orient, name in self.docking_orients.items():
            ori_btn = self.dock_menu.addAction(name, description="Dock TKM {} of the widget.".format(name))
            ori_btn.setCheckable(True)
            self.pos_ac_group.addAction(ori_btn)
            ori_btn.triggered.connect(partial(self.dock_to_ui, orient=orient))
            if orient == self.docking_position[1]:
                ori_btn.setChecked(True)
                ori_btn.setEnabled(False)

        self.dock_menu.addSeparator()

        self.dock_ac_group = QActionGroup(self)
        for layout, name in self.docking_layouts.items():
            dock_btn = self.dock_menu.addAction(name, description="Dock TKM to the {} widget.".format(name))
            dock_btn.setCheckable(True)
            self.dock_ac_group.addAction(dock_btn)

            dock_btn.triggered.connect(partial(self.dock_to_ui, layout=layout))
            if layout == self.docking_position[0]:
                dock_btn.setChecked(True)
                dock_btn.setEnabled(False)

        self.dock_menu.aboutToShow.connect(self.update_dock_menu)

        return self.dock_menu

    # These two functions attempt to check if the Graph Editor is open and load customGraph in that case; they are made with two attempts
    def load_customGraph_try_01(self):
        if not isValid(self):
            return
        graph_vis = cmds.getPanel(vis=True)
        if graph_vis and "graphEditor1" in graph_vis:
            cg.createCustomGraph()
        else:
            QTimer.singleShot(8000, self.load_customGraph_try_02)

    def load_customGraph_try_02(self):
        if not isValid(self):
            return
        graph_vis = cmds.getPanel(vis=True)
        if graph_vis and "graphEditor1" in graph_vis:
            cg.createCustomGraph()
        else:
            pass

    # For use with toggle functionality on Shelf or Launcher
    def toggle(self, *args):
        self.showWindow()

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
    def update_popup_menu(self, *args):
        if not isValid(self):
            return

        if not cmds.objExists("iBookmarks"):
            if cmds.popupMenu("isolate_button_popupMenu", exists=True):
                # Limpia el menú popup actual
                cmds.popupMenu("isolate_button_popupMenu", e=True, deleteAllItems=True)

                # Agrega un ítem para abrir la ventana de bookmarks
                cmds.menuItem(
                    l="Bookmarks",
                    c=lambda x: self.create_ibookmarks_window(),
                    annotation="Open isolate bookmarks window",
                    image=media.ibookmarks_menu_image,
                    parent="isolate_button_popupMenu",
                )  # type: ignore
                cmds.menuItem(divider=True, parent="isolate_button_popupMenu")
                cmds.menuItem(
                    "down_level_checkbox",
                    l="Down one level",
                    annotation="",
                    checkBox=False,
                    c=lambda x: bar.toggle_down_one_level(x),
                    parent="isolate_button_popupMenu",
                )
            return

        # Obtén todos los nombres de los bookmarks existentes
        bookmarks = cmds.listRelatives("iBookmarks", children=True) or []

        if cmds.popupMenu("isolate_button_popupMenu", exists=True):
            # Limpia el menú popup actual
            cmds.popupMenu("isolate_button_popupMenu", e=True, deleteAllItems=True)

            # Agrega un ítem por cada bookmark existente
            for bookmark in bookmarks:
                text = bookmark.replace("_ibookmark", "")
                cmds.menuItem(
                    l=text,
                    parent="isolate_button_popupMenu",
                    image=media.grey_menu_image,
                    c=lambda x, text=text: self.isolate_bookmark(bookmark_name=text),
                )

            cmds.menuItem(divider=True, parent="isolate_button_popupMenu")

            # Agrega un ítem para abrir la ventana de bookmarks
            cmds.menuItem(
                l="Bookmarks",
                c=lambda x: self.create_ibookmarks_window(),
                annotation="Open isolate bookmarks window",
                image=media.ibookmarks_menu_image,
                parent="isolate_button_popupMenu",
            )
            cmds.menuItem(divider=True, parent="isolate_button_popupMenu")
            cmds.menuItem(
                "down_level_checkbox",
                l="Down one level",
                annotation="",
                checkBox=False,
                c=lambda x: bar.toggle_down_one_level(x),
                parent="isolate_button_popupMenu",
            )

        else:
            # Obtén todos los nombres de los bookmarks existentes
            bookmarks = cmds.listRelatives("iBookmarks", children=True) or []

            # Limpia el menú popup actual
            cmds.popupMenu("isolate_button_popupMenu", e=True, deleteAllItems=True)

            # Agrega un ítem por cada bookmark existente
            for bookmark in bookmarks:
                text = bookmark.replace("_ibookmark", "")
                cmds.menuItem(
                    l=text,
                    parent="isolate_button_popupMenu",
                    image=media.grey_menu_image,
                    c=lambda x, text=text: self.isolate_bookmark(bookmark_name=text),
                )  # type: ignore

            cmds.menuItem(divider=True, parent="isolate_button_popupMenu")

            # Agrega un ítem para abrir la ventana de bookmarks
            cmds.menuItem(
                l="Bookmarks",
                c=lambda x: self.create_ibookmarks_window(),
                annotation="Open isolate bookmarks window",
                image=media.ibookmarks_menu_image,
                parent="isolate_button_popupMenu",
            )  # type: ignore
            cmds.menuItem(divider=True, parent="isolate_button_popupMenu")
            cmds.menuItem(
                "down_level_checkbox",
                l="Down one level",
                annotation="",
                checkBox=False,
                c=lambda x: bar.toggle_down_one_level(x),
                parent="isolate_button_popupMenu",
            )

    def update_selectionSets_on_new_scene(self):
        if not isValid(self):
            return
        if cmds.window("SetCreationWindow", exists=True):
            cmds.deleteUI("SetCreationWindow")

        # First verification to check if the SelectionSets workspace exists.
        # If it doesn't exist and trying to assign `vis_state` results in an error.
        if cmds.workspaceControl(selection_sets_workspace, query=True, exists=True):
            vis_state = cmds.workspaceControl(selection_sets_workspace, query=True, visible=True)
            if vis_state:
                if cmds.objExists("TheKeyMachine_SelectionSet"):
                    self.create_buttons_for_sel_sets()
                else:
                    self.selection_sets_empty_setup()

            # The selection set workspace is hidden; nothing needs to be done

    def reload(self, *args):
        toolbar_module_name = "TheKeyMachine.core.toolbar"
        customGraph_module_name = "TheKeyMachine.core.customGraph"

        # Importa el módulo y recarga
        toolbar_module = importlib.import_module(toolbar_module_name)
        customGraph_module = importlib.import_module(customGraph_module_name)

        # Force kill scriptjobs like cams.py
        for j in cmds.scriptJob(listJobs=True):
            if "TheKeyMachine" in j or "TheKeyMachine.core.toolbar" in j:
                if ":" in j:
                    try:
                        _id = int(j.split(":")[0])
                        cmds.scriptJob(kill=_id, force=True)
                    except Exception:
                        pass

        # Close and delete the UI
        try:
            workspace_control = WorkspaceName + "WorkspaceControl"
            if cmds.workspaceControl(workspace_control, q=True, exists=True):
                cmds.deleteUI(workspace_control, control=True)
        except Exception:
            pass

        if isValid(self):
            try:
                self.blockSignals(True)
                self.close()
            except Exception:
                pass

        importlib.reload(toolbar_module)
        importlib.reload(customGraph_module)

        # Use the global show() instead of module-level 'tb'
        toolbar_module.show()

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
                    split_name = sub_sel_set.split("_")
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
                split_name = sub_sel_set.split("_")
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
        window.setObjectName("SetGroupNameWindow")
        window.setWindowTitle("Rename Set Group")
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

        close_button = QtWidgets.QPushButton("X")
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
            "QLineEdit {    background-color: #252525;    color: #cccccc;    border: none;    padding: 2px;    border-radius: 4px;}"
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
        window.setObjectName("SetNameWindow")
        window.setWindowTitle("Rename Set")
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

        close_button = QtWidgets.QPushButton("X")
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
        color_suffix = color_suffix.strip("_")

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
        new_set_group_name = new_set_group_name.replace(" ", "_")

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
        window.setObjectName("SetCreationWindow")
        window.setWindowTitle("Set Creation")
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

        close_button = QtWidgets.QPushButton("X")
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
                "QPushButton {{"
                f"    background-color: {hex_code};"
                "    border-radius: 5px;"
                "}}"
                "QPushButton:hover {{"
                f"    background-color: {hover_color};"
                "    border-radius: 5px;"
                "}}"
            )
            button.clicked.connect(
                lambda c=color_suffix, field=set_name_field, combo=set_group_combo: self.create_new_set_and_update_buttons(c, field, combo)
            )

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
            new_set_name = new_set_name.replace(" ", "_")

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
                cmds.warning("The set is not part of any setgroup")
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

        # Añade la selección actual a un conjunto de selección dado.

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

    color_names = {"_01": "Gray", "_02": "Beige", "_03": "Aqua", "_04": "Blue", "_05": "Purple", "_06": "Green", "_07": "Mute red", "_08": "Red"}

    def create_color_submenu(self, set_name, parent_menu):
        # Los botones de color
        color_buttons = [
            ([0.51, 0.55, 0.56], "_01"),
            ([0.90, 0.84, 0.68], "_02"),
            ([0.64, 0.80, 0.75], "_03"),
            ([0.45, 0.71, 0.63], "_04"),
            ([0.76, 0.58, 0.57], "_05"),
            ([0.66, 0.39, 0.40], "_06"),
            ([0.50, 0.50, 0.63], "_07"),
            ([0.50, 0.50, 0.63], "_08"),
        ]

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
                command=partial(self.set_set_color, set_name, color_suffix),
            )

    def clear_selection_sets(self, *args):
        # Borra todos los botones existentes
        children = cmds.flowLayout("selection_sets_flow_layout", q=True, ca=True)
        if children:
            for child in children:
                cmds.deleteUI(child)

        # Crea el botón 'SET' sin importar si hay conjuntos de selección o no
        cmds.separator(style="none", width=5, p="selection_sets_flow_layout")
        selset_button = cmds.iconTextButton(
            l=" SET ", image=media.add_selection_set_image, h=28, w=28, c=self.open_set_creation_window, p="selection_sets_flow_layout"
        )
        cmds.separator(style="none", width=5, p="selection_sets_flow_layout")
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
        cmds.separator(style="none", width=5, p="selection_sets_flow_layout")
        selset_button = cmds.iconTextButton(
            l=" SET ", image=media.add_selection_set_image, h=32, w=32, c=self.selection_sets_setup, p="selection_sets_flow_layout"
        )
        cmds.separator(style="none", width=5, p="selection_sets_flow_layout")
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
        cmds.separator(style="none", width=5, p="selection_sets_flow_layout")
        selset_button = cmds.iconTextButton(
            l=" SET ", image=media.add_selection_set_image, h=32, w=32, c=self.open_set_creation_window, p="selection_sets_flow_layout"
        )
        cmds.separator(style="none", width=5, p="selection_sets_flow_layout")
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
            sub_sel_sets.sort(key=lambda s: (s.split("_")[-1], s.split("_")[:-1]))

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
            button = cmds.button(
                f"setgroup_button_{set_group}",
                label=button_label,
                h=32,
                width=setgroup_button_width,
                parent="selection_sets_flow_layout",
                command=toggle_command,
            )
            button_widget = wrapInstance(int(mui.MQtUtil.findControl(button)), QtWidgets.QPushButton)

            if self.screen_width == 3840:
                button_widget.setStyleSheet(
                    """
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
                """
                    % (button_text_color, button_color, button_color)
                )
            else:
                button_widget.setStyleSheet(
                    """
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
                """
                    % (button_text_color, button_color, button_color)
                )

            cmds.popupMenu(parent=button)
            # Verificar si el setgroup es el "main" y no agregar el menuItem "Rename Group" en ese caso
            if set_group != "main_setgroup":
                cmds.menuItem(label="Rename Group", command=lambda x, set_group=set_group: self.change_setgroup_name_window(set_group))
                cmds.menuItem(divider=True)
            cmds.menuItem(label="Export Group", command=lambda x, g=set_group: self.export_single_subgroup(g))
            cmds.menuItem(label="Delete Group", command=lambda x, g=set_group: self.remove_set_group_and_update_buttons(g))

        cmds.separator(style="none", width=10, p="selection_sets_flow_layout")  # Espacio entre los botones de los sets pertenecientes a cada grupo

        # Para cada grupo de conjuntos, obtén sus conjuntos de selección y crea botones para ellos
        for set_group in set_groups:
            # Obtiene todos los conjuntos de selección en el grupo de conjuntos actual
            sub_sel_sets = cmds.sets(set_group, q=True) or []

            # Ordena los conjuntos de selección por el código de color en el nombre
            sub_sel_sets.sort(key=lambda s: (s.split("_")[-1], s.split("_")[:-1]))

            setgroup_hidden = all(cmds.getAttr(f"{sub_sel_set}.hidden") for sub_sel_set in sub_sel_sets)

            # Crear botones para cada conjunto de selección
            button_color = "#252525" if setgroup_hidden else "#333333"

            for sub_sel_set in sub_sel_sets:
                # Asegúrate de que el conjunto de selección es válido

                if cmds.objExists(sub_sel_set):
                    split_name = sub_sel_set.split("_")
                    color_suffix = split_name[-1]
                    set_name = "_".join(split_name[:-2])  # Une todas las partes del nombre, excepto las dos últimas partes.

                    # Obtiene el valor del color del código de color
                    button_color_hex = ui.color_codes.get(f"_{color_suffix}", "#333333")  # Default to white (#FFFFFF) if color_suffix not found
                    button_color_hex_hover = ui.color_codes_hover.get(
                        f"_{color_suffix}", "#333333"
                    )  # Default to white (#FFFFFF) if color_suffix not found

                    # Calcula el ancho del botón en función del número de caracteres en la etiqueta
                    button_width = max(60, len(set_name) * 8)

                    # Verificar el valor del atributo "hidden" del conjunto de selección
                    is_hidden = cmds.getAttr(f"{sub_sel_set}.hidden")
                    # Si el conjunto está oculto, no mostrar el botón
                    if is_hidden:
                        continue

                    # # Obtiene los miembros del conjunto de selección
                    # members = cmds.sets(sub_sel_set, q=True)

                    # # Crea una cadena con los nombres de los miembros separados por comas
                    # members_string = ", ".join(m for m in (members or []) if cmds.objExists(m))

                    # El botón selecciona los miembros del conjunto de selección al hacer clic en él
                    button = cmds.button(
                        label=set_name,
                        h=32,
                        width=button_width,
                        command=lambda x, s=sub_sel_set: self.handle_set_selection(s, shift_pressed, ctrl_pressed),
                        parent="selection_sets_flow_layout",
                    )
                    button_widget = wrapInstance(int(mui.MQtUtil.findControl(button)), QtWidgets.QPushButton)

                    if self.screen_width == 3840:
                        style_sheet = """
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
                        """.format(color=button_color_hex, color_over=button_color_hex_hover)
                    else:
                        style_sheet = """
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
                        """.format(color=button_color_hex, color_over=button_color_hex_hover)

                    button_widget.setStyleSheet(style_sheet)

                    # Crea un menú emergente con una opción de "Delete set"
                    selset_button = cmds.popupMenu(parent=button)

                    # Menu button Selection Sets --------

                    cmds.menuItem(
                        label="Add Selection",
                        image=media.add_to_selection_set_image,
                        command=lambda x, s=sub_sel_set: self.add_selection_to_set(s),
                        p=selset_button,
                    )
                    cmds.menuItem(
                        label="Remove Selection",
                        image=media.remove_from_selection_set_image,
                        command=lambda x, s=sub_sel_set: self.remove_selection_from_set(s),
                        p=selset_button,
                    )
                    cmds.menuItem(divider=True, p=selset_button)

                    color_menu = cmds.menuItem(subMenu=True, label="Change Color", image=media.change_selection_set_color_image, p=selset_button)
                    self.create_color_submenu(sub_sel_set, color_menu)

                    cmds.menuItem(
                        label="Rename Set",
                        image=media.rename_selection_set_image,
                        c=partial(self.change_set_name_window, sub_sel_set, set_group),
                        p=selset_button,
                    )
                    cmds.menuItem(divider=True, p=selset_button)

                    cmds.menuItem(
                        label="Delete Set",
                        image=media.remove_selection_set_image,
                        command=lambda x, s=sub_sel_set, g=set_group: self.remove_set_and_update_buttons(s, g),
                        p=selset_button,
                    )
                    cmds.menuItem(divider=True, p=selset_button)

                    # Muestra ventana select items
                    cmds.menuItem(
                        label="Selector",
                        image=media.selector_selection_set_image,
                        command=lambda x, s=sub_sel_set: self.select_set_items_window(s),
                        p=selset_button,
                    )
                    move_selset_submenu = cmds.menuItem(subMenu=True, image=media.move_selection_set_image, label="Nudge to ...", p=selset_button)

                    # Obtener los setgroups que están dentro de "TheKeyMachine_SelectionSet"
                    valid_setgroups = [sg for sg in set_groups if cmds.sets(sg, isMember=sel_set_name)]

                    # Agregar un elemento en el menú emergente para cada setgroup válido
                    for valid_setgroup in valid_setgroups:
                        # Obtener el nombre del setgroup sin el sufijo "_setgroup"
                        setgroup_name_without_suffix = valid_setgroup.replace("_setgroup", "")

                        # Agregar un elemento en el menú emergente para cada setgroup válido
                        cmds.menuItem(
                            label=setgroup_name_without_suffix,
                            command=lambda x, s=sub_sel_set, g=valid_setgroup: self.move_set_to_setgroup(s, g),
                            p=move_selset_submenu,
                        )

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
        cmds.textScrollList(member_list, edit=True, sc=partial(self.select_items_from_list, member_list))

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
        aTimeSlider = mel.eval("$tmpVar=$gPlayBackSlider")
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
                    attr_full_name = obj + "." + attr
                    if cmds.getAttr(attr_full_name, settable=True):
                        keyframes = cmds.keyframe(obj, attribute=attr, query=True)
                        if keyframes:
                            self.animation_offset_original_values[obj][attr] = {
                                frame: cmds.getAttr(attr_full_name, time=frame) for frame in keyframes if timeRange[0] <= frame <= timeRange[1]
                            }

        # borra selected range slider
        cmds.ls(selection=True)
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
        aTimeSlider = mel.eval("$tmpVar=$gPlayBackSlider")
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
                attr_full_name = obj + "." + attr

                # salta bloqueados/no seteables y tipos no numéricos
                if not cmds.getAttr(attr_full_name, settable=True) or cmds.getAttr(attr_full_name, lock=True):
                    continue
                a_type = cmds.getAttr(attr_full_name, type=True)
                if a_type in ("enum", "string", "message"):
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

                    original_value = self.animation_offset_original_values.get(obj, {}).get(attr, {}).get(frame)

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

                        orig_update = self.animation_offset_original_values.get(obj, {}).get(attr, {}).get(frame_to_update)
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
            if not isValid(self):
                return
            self.adjust_keyframes()

        while self.anim_offset_run_timer and isValid(self):
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
            settings.set_setting("toggleAnimOffsetButtonState", self.toggleAnimOffsetButtonState)

            if self.toggleAnimOffsetButtonState:
                cmds.undoInfo(openChunk=True)
                cmds.iconTextButton("anim_offset_button", e=True, bgc=(0.3, 0.3, 0.3))
                self.anim_offset_run_timer = True

                # Initialize thread variable if not already
                self.anim_offset_thread = threading.Thread(target=self.offset_animation_deferred, args=(0.3,))
                self.anim_offset_thread.start()
                self.store_keyframes()

            else:
                cmds.undoInfo(closeChunk=True)
                cmds.iconTextButton("anim_offset_button", e=True, bgc=(0.2, 0.2, 0.2))
                self.anim_offset_run_timer = False
                if self.anim_offset_thread and self.anim_offset_thread.is_alive():
                    self.anim_offset_thread.join()  # Wait for the thread to finish
                pass

    # ---------------------------------------------------------------

    def toggle_micro_move_button(self, *args):

        self.micro_move_button_state = not self.micro_move_button_state
        settings.set_setting("micro_move_button_state", self.micro_move_button_state)

        if self.micro_move_button_state:
            cmds.undoInfo(openChunk=True)
            # cmds.iconTextButton("micro_move_button", e=True, bgc=(0.3, 0.3, 0.3))
            self.micro_move_run_timer = True
            bar.activate_micro_move()

            # Initialize thread variable if not already
            self.micro_move_thread = threading.Thread(target=self.micro_move_thread, args=(0.5,))
            self.micro_move_thread.start()

        else:
            self.micro_move_run_timer = False
            cmds.undoInfo(closeChunk=True)
            # current_context = cmds.currentCtx()
            # microMoveContext = "microMoveCtx"
            # microRotateContext = "microRotateCtx"
            # cmds.iconTextButton("micro_move_button", e=True, bgc=(0.2, 0.2, 0.2))

            # El thread tarda en pararse así que necesitamos crear esto y así salirnos en barMod de la ejecución
            cmds.manipMoveContext("dummyCtx")
            cmds.setToolTo("dummyCtx")
            if self.micro_move_thread and self.micro_move_thread.is_alive():
                self.micro_move_thread.join()  # Wait for the thread to finish

    def micro_move_thread(self, interval):
        def micro_move_run():
            if not isValid(self):
                return
            bar.activate_micro_move()

        while self.micro_move_run_timer and isValid(self):
            time.sleep(interval)
            utils.executeDeferred(micro_move_run)

        self.run_centerToolbar = False

    def show_sys_info(self):

        os_info = platform.system() + " " + platform.release()

        tkm_stage = general.get_thekeymachine_version()
        tkm_version = general.get_thekeymachine_version()

        app = QtWidgets.QApplication.instance()
        if not app:
            app = QtWidgets.QApplication([])

        try:
            # PySide2
            desktop = QtWidgets.QDesktopWidget()
            screen_rect = desktop.screenGeometry()
        except Exception:
            # PySide6
            screen = app.primaryScreen()
            screen_rect = screen.geometry()
        width, height = screen_rect.width(), screen_rect.height()

        tkm_toolbar_width = cmds.workspaceControl(WorkspaceName, query=True, width=True)
        toolbar_s = settings.get_setting("toolbar_size", 1580)
        sobrante = tkm_toolbar_width - toolbar_s

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

    def start_selection_sets_UI(self):
        # Crea el selection sets workspace
        target_dock = WorkspaceName + "WorkspaceControl"
        if cmds.workspaceControl(selection_sets_workspace, query=True, exists=True) is False:
            cmds.workspaceControl(
                selection_sets_workspace,
                ih=35,
                li=True,
                tp=["west", True],
                floating=False,
                dtc=[target_dock, "bottom"],
                vis=False,
            )
            cmds.workspaceControl(selection_sets_workspace, edit=True, tabPosition=["west", True])
        else:
            cmds.workspaceControl(selection_sets_workspace, edit=True, restore=False)
            self.update_selectionSets_on_new_scene()

    # Crea el selection sets workspace ----------------------------------------------------------------------------

    def create_selection_sets_workspace(self):
        cmds.flowLayout("selection_sets_flow_layout", columnSpacing=1, wr=True, w=150)
        self.selection_sets_empty_setup()

    def toggle_selection_sets_workspace(self, *args):
        if cmds.workspaceControl(selection_sets_workspace, query=True, exists=True):
            vis_state = cmds.workspaceControl(selection_sets_workspace, query=True, visible=True)

            if vis_state:
                cmds.workspaceControl(selection_sets_workspace, edit=True, visible=False)
            else:
                cmds.workspaceControl(selection_sets_workspace, edit=True, restore=True)
                self.create_buttons_for_sel_sets()
        else:
            cmds.workspaceControl(
                selection_sets_workspace,
                ih=35,
                li=True,
                tp=["west", True],
                floating=False,
                dtc=["k", "bottom"],
                vis=True,
            )
            cmds.workspaceControl(selection_sets_workspace, edit=True, tabPosition=["west", True])
            self.update_selectionSets_on_new_scene()

    def set_reload(self):

        import TheKeyMachine.core.toolbar as t  # type: ignore

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
            title="Create Bookmark",
            message="Enter bookmark name:",
            button=["Create", "Cancel"],
            defaultButton="Create",
            cancelButton="Cancel",
            dismissString="Cancel",
        )

        if text == "Create":
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
                obj_name = obj.split("|")[-1]

                # Si el nombre del objeto contiene "->", eliminar la parte anterior a esos caracteres
                if "->" in obj_name:
                    obj_name = obj_name.split("->")[-1]

                # Eliminar cualquier punto en el nombre del objeto (para imagePlanes)
                obj_name = obj_name.replace(".", "_")
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
            bookmark_name = bookmark_name.replace("_ibookmark", "")
            # Encontrar el nodo del bookmark
            bookmark_node = f"{bookmark_name}_ibookmark"
            if cmds.objExists(bookmark_node):
                # Obtener todos los objetos dentro del nodo de bookmark
                objects = cmds.listRelatives(bookmark_node, allDescendents=True, fullPath=True)  # Usa fullPath=True aquí
                if objects:
                    selected_objects = []
                    for obj in objects:
                        # Remover "_ibook" del final del nombre del objeto
                        obj_name = obj.rsplit("|", 1)[-1].replace("_ibook", "")
                        # Remover el sufijo que coincide con el texto de la lista de bookmarks
                        obj_name = obj_name.replace(f"_{bookmark_name}", "")

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
            cmds.select(current_selection, replace=True)

    def update_bookmark_list(self, list_widget, *args):
        bookmarks = cmds.listRelatives("iBookmarks", children=True) or []
        cmds.textScrollList(list_widget, edit=True, removeAll=True)  # Limpiar la lista
        for bookmark in bookmarks:
            text = bookmark.replace("_ibookmark", "")
            cmds.textScrollList(list_widget, edit=True, append=text)

    def create_ibookmarks_window(self, *args):

        original_selection = cmds.ls(selection=True)

        if cmds.window("iBookmarksWindow", exists=True):
            cmds.deleteUI("iBookmarksWindow")

        window = cmds.window(
            "iBookmarksWindow", title="Isolate Bookmarks", widthHeight=(265, 140), sizeable=False
        )  # Hacer la ventana no redimensionable
        main_layout = cmds.columnLayout(adjustableColumn=True, rowSpacing=10, columnAlign="center")

        # Crear un formLayout para controlar la disposición de los elementos
        form_layout = cmds.formLayout()

        # Columna de la izquierda con la lista
        list_widget = cmds.textScrollList(allowMultiSelection=False, h=130)

        # Columna de la derecha con los botones
        button_layout = cmds.columnLayout(adjustableColumn=True, columnAlign="center")
        cmds.button(label="Create", command=lambda x: self.create_bookmark(list_widget), width=90)  # Ajustar el ancho del botón
        cmds.button(label="Remove", command=lambda x: self.remove_bookmark(list_widget), width=90)  # Ajustar el ancho del botón
        cmds.button(label="Isolate", command=lambda x: self.isolate_bookmark(list_widget), width=90)  # Ajustar el ancho del botón

        # Establecer las restricciones de disposición en el formLayout
        cmds.formLayout(
            form_layout,
            edit=True,
            attachForm=[(list_widget, "left", 5), (list_widget, "top", 5), (button_layout, "top", 5), (button_layout, "right", 5)],
            attachControl=[(list_widget, "right", 5, button_layout)],
        )

        cmds.setParent(main_layout)  # Regresar al layout principal
        cmds.showWindow(window)
        self.create_ibookmark_node()
        self.update_bookmark_list(list_widget)

        # Restaurar la selección original
        if original_selection:
            cmds.select(original_selection, replace=True)
        else:
            cmds.select(clear=True)

    def buildUI(self):
        # Fix para que no de error, por si no lee el ancho del ViewPanel

        if self.bar_center_value is None:
            self.bar_center_value = 1

        # Reconstruir column y row layouts
        if cmds.rowLayout("rowtoolbar", exists=True):
            cmds.deleteUI("rowtoolbar")

        ### ______________________________________________________ TOOLBAR ICON SIZE  ___________________________________________________

        def get_current_icon_alignment():
            return read_toolbar_icon_alignment()

        def read_toolbar_icon_alignment():
            return settings.get_setting("toolbar_icon_alignment", "Center")

        def update_toolbar_icon_alignment(alignment):
            if alignment:
                settings.set_setting("toolbar_icon_alignment", alignment)
                self.reload()

        ### ______________________________________________________ TOOLBAR LAYOUT _____________________________________________________________________###

        if self.layout():
            QtWidgets.QWidget().setLayout(self.layout())

        self.setSizePolicy(QtWidgets.QSizePolicy.Preferred, QtWidgets.QSizePolicy.Minimum)
        self.main_layout = QtWidgets.QHBoxLayout(self)
        self.main_layout.setContentsMargins(0, 0, 0, 0)
        self.main_toolbar_widget = cw.QFlowContainer()
        self.main_layout.addWidget(self.main_toolbar_widget)

        # Use QFlowLayout to allow wrapping
        toolbar_alignment_str = get_current_icon_alignment()
        qt_alignment = QtCore.Qt.AlignLeft
        if toolbar_alignment_str == "Right":
            qt_alignment = QtCore.Qt.AlignRight
        elif toolbar_alignment_str == "Center":
            qt_alignment = QtCore.Qt.AlignHCenter

        rowtoolbar_layout = cw.QFlowLayout(self.main_toolbar_widget, margin=2, Wspacing=18, Hspacing=6, alignment=qt_alignment)

        def new_section(spacing=2, hiddeable=True):
            sec = cw.QFlatSectionWidget(spacing=spacing, hiddeable=hiddeable)
            rowtoolbar_layout.addWidget(sec)
            return sec

        # Placeholder for tooltip functions to be defined later
        show_tooltips = settings.get_setting("show_tooltips", True)
        self._toggle_tooltips_func = None

        sec = new_section(spacing=8)

        # _____________________ Key Editing Section __________________________________________________ #
        sec = new_section(spacing=2)

        nudge_keyleft_b_widget = cw.QFlatToolButton(icon=media.nudge_left_image, description="Nudge Left")
        nudge_keyleft_b_widget.clicked.connect(lambda: keyTools.move_keyframes_in_range(-self.move_keyframes_intField.value()))
        sec.addWidget(nudge_keyleft_b_widget, "Nudge Left", "move_left")

        nudge_keyright_b_widget = cw.QFlatToolButton(icon=media.nudge_right_image, description="Nudge Right")
        nudge_keyright_b_widget.clicked.connect(lambda: keyTools.move_keyframes_in_range(self.move_keyframes_intField.value()))
        sec.addWidget(nudge_keyright_b_widget, "Nudge Right", "move_right")

        self.move_keyframes_intField = cw.QFlatSpinBox()
        self.move_keyframes_intField.setFixedSize(50, 24)
        self.move_keyframes_intField.setMinimum(1)
        self.move_keyframes_intField.setValue(1)
        self.move_keyframes_intField.setStyleSheet("border: 0px;border-radius: 5px;")
        sec.addWidget(self.move_keyframes_intField, "Nudge Value", "nudge_val")

        remove_inbetween_b_widget = cw.QFlatToolButton()
        remove_inbetween_b_widget.setText(" - ")
        remove_inbetween_b_widget.clicked.connect(keyTools.remove_inbetween)
        sec.addWidget(remove_inbetween_b_widget, "Remove Inbetween", "remove_inbetween")

        insert_inbetween_b_widget = cw.QFlatToolButton()
        insert_inbetween_b_widget.setText(" + ")
        insert_inbetween_b_widget.clicked.connect(keyTools.insert_inbetween)
        sec.addWidget(insert_inbetween_b_widget, "Insert Inbetween", "insert_inbetween")

        clear_selected_keys_widget = cw.QFlatToolButton()
        clear_selected_keys_widget.setText(" x ")
        clear_selected_keys_widget.clicked.connect(keyTools.clear_selected_keys)
        sec.addWidget(clear_selected_keys_widget, "Clear Selection", "clear_sel")

        select_scene_animation_widget = cw.QFlatToolButton()
        select_scene_animation_widget.setText(" s ")
        select_scene_animation_widget.clicked.connect(keyTools.select_all_animation_curves)
        sec.addWidget(select_scene_animation_widget, "Select Scene Anim", "select_scene")

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
                with open(json_file_path, "r") as file:
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
                        namespace = obj.split(":")[0] if ":" in obj else "default"

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

        def update_button_with_current_frame(button_name):
            # Obtener el número del frame actual
            current_frame = cmds.currentTime(query=True)
            # Actualizar el texto del botón con el número del frame
            cmds.button(button_name, edit=True, label=str(int(current_frame)))

        # _____________________ Sliders Sections ____________________________ #
        blend_to_key_left_b_qt = cw.QFlatToolButton()
        blend_to_key_left_b_qt.setText("1")
        blend_to_key_left_b_qt.setFixedSize(25, 16)
        blend_to_key_left_b_qt.hide()
        blend_to_key_left_b_qt.clicked.connect(lambda: blend_to_key_left_b_qt.setText(str(int(cmds.currentTime(q=True)))))

        blend_to_key_right_b_qt = cw.QFlatToolButton()
        blend_to_key_right_b_qt.setText("1")
        blend_to_key_right_b_qt.setFixedSize(25, 16)
        blend_to_key_right_b_qt.hide()
        blend_to_key_right_b_qt.clicked.connect(lambda: blend_to_key_right_b_qt.setText(str(int(cmds.currentTime(q=True)))))

        def blend_to_frame_with_button_values(percentage):
            left_frame_label = blend_to_key_left_b_qt.text()
            right_frame_label = blend_to_key_right_b_qt.text()
            try:
                left_frame = int(left_frame_label)
            except ValueError:
                left_frame = None
            try:
                right_frame = int(right_frame_label)
            except ValueError:
                right_frame = None
            keyTools.blend_to_frame(percentage, left_frame, right_frame)

        def add_mode_sliders(modes_list, default_key_setting, prefix, color, change_func, drop_func, default_modes=None, ws_support=False):
            # Create a new section for each slider color/type
            sec = new_section(spacing=4)

            current_default = settings.get_setting(
                default_key_setting, modes_list[0]["key"] if isinstance(modes_list[0], dict) else modes_list[1]["key"]
            )

            # Static default list for "Pin Defaults" — uses provided list or falls back to current default
            if default_modes:
                static_default_keys = [f"{prefix}_{k}" for k in default_modes]
            else:
                static_default_keys = [f"{prefix}_{current_default}"]

            for m in modes_list:
                if m == "separator":
                    sec.addSeparator()
                    continue
                if not isinstance(m, dict):
                    continue

                key = m["key"]
                label = m["label"]
                desc = m.get("description", "")
                icon = m.get("icon", "SL")

                # Check for specialized commands
                command = None
                show_frames = False

                if key == "blend_to_frame":
                    command = blend_to_frame_with_button_values
                    show_frames = True

                # Determine initial visibility: pinned setting takes priority, fallback to default_modes membership
                is_visible = settings.get_setting(f"pin_{prefix}_{key}", f"{prefix}_{key}" in static_default_keys)

                s = sw.QFlatSliderWidget(
                    f"bar_{prefix}_{key}",
                    min=-100,
                    max=100,
                    text=icon,
                    color=color,
                    dragCommand=command or (lambda v, k=key: change_func(k, v)),
                    dropCommand=drop_func,
                    tooltipTitle=label,
                    tooltipDescription=desc,
                )
                s.setModes(modes_list)
                s.setCurrentMode(key)

                # Setup mode switching
                def make_mode_setter(slider_instance, prefix_val, show_f):
                    def setter(new_mode):
                        # Use standardized setting names: current_blend_mode, current_tween_mode
                        settings.set_setting(f"current_{prefix_val}_mode", new_mode)
                        slider_instance.setCurrentMode(new_mode)
                        m_info = next((item for item in modes_list if isinstance(item, dict) and item["key"] == new_mode), None)
                        if m_info:
                            slider_instance.set_tooltip_info(m_info["label"], m_info.get("description", ""))

                        # Handle specialized frames visibility
                        if new_mode == "blend_to_frame":
                            blend_to_key_left_b_qt.show()
                            blend_to_key_right_b_qt.show()
                            slider_instance.setDragCommand(blend_to_frame_with_button_values)
                        else:
                            blend_to_key_left_b_qt.hide()
                            blend_to_key_right_b_qt.hide()
                            slider_instance.setDragCommand(lambda v, nk=new_mode: change_func(nk, v))

                        slider_instance.startFlash()

                    return setter

                s.modeSelected.connect(make_mode_setter(s, prefix, show_frames))

                if ws_support:
                    is_ws = "worldspace" in key.lower() or "world space" in key.lower()
                    s.setWorldSpace(is_ws)

                # Add to section with registration
                sec.addWidget(s, label, f"{prefix}_{key}", default_visible=is_visible, description=desc)

            # Add the final pin actions (Pin Defaults/All)
            sec.add_final_actions(static_default_keys)

        # Create separate sections for Blend and Tween sliders - Standardized setting names
        add_mode_sliders(
            sliders.BLEND_MODES,
            "current_blend_mode",
            "blend",
            COLOR.color.green,
            sliders.execute_curve_modifier,
            sliders.stop_dragging,
            default_modes=["connect_neighbors"],
        )
        add_mode_sliders(
            sliders.TWEEN_MODES,
            "current_tween_mode",
            "tween",
            COLOR.color.yellow,
            sliders.execute_tween,
            sliders.stop_dragging,
            default_modes=["tweener"],
            ws_support=True,
        )

        # ----------------------------------------------- ToolsButtons -------------------------------------------------------- #

        # Pointer  -------------------------------------------------------------------------

        sec = new_section()

        pointer_button_widget = cw.QFlatToolButton(icon=media.pointer_image, tooltip=helper.pointer_tooltip_text)
        pointer_button_widget.clicked.connect(bar.isolate_master)
        sec.addWidget(pointer_button_widget, "Pointer", "pointer")

        pointer_menu = QtWidgets.QMenu(pointer_button_widget)
        pointer_menu.addAction(QtGui.QIcon(media.select_rig_controls_image), "Select Rig Controls", bar.select_rig_controls)
        pointer_menu.addAction(
            QtGui.QIcon(media.select_animated_rig_controls_image), "Select Animated Rig Controls", bar.select_animated_rig_controls
        )
        pointer_menu.addSeparator()
        pointer_menu.addAction(QtGui.QIcon(media.depth_mover_image), "Depth Mover", bar.depth_mover)

        pointer_button_widget.setMenu(pointer_menu)
        pointer_button_widget.setPopupMode(QtWidgets.QToolButton.InstantPopup)

        # Isolate -------------------------------------------------------------------------

        isolate_button_widget = cw.QFlatToolButton(icon=media.isolate_image, tooltip=helper.isolate_tooltip_text)
        isolate_button_widget.clicked.connect(bar.isolate_master)
        sec.addWidget(isolate_button_widget, "Isolate", "isolate")

        isolate_menu = QtWidgets.QMenu(isolate_button_widget)
        isolate_menu.addAction(QtGui.QIcon(media.ibookmarks_menu_image), "Bookmarks", self.create_ibookmarks_window)
        isolate_menu.addSeparator()
        action_down_level = isolate_menu.addAction("Down one level")
        action_down_level.setCheckable(True)
        action_down_level.triggered.connect(bar.toggle_down_one_level)
        isolate_menu.addSeparator()
        isolate_menu.addAction(
            QtGui.QIcon(media.help_menu_image),
            "Help",
            lambda: general.open_url("https://thekeymachine.gitbook.io/base/the-toolbar/animation-tools/isolate"),
        )

        isolate_button_widget.setContextMenuPolicy(QtCore.Qt.CustomContextMenu)
        isolate_button_widget.customContextMenuRequested.connect(lambda pos: isolate_menu.exec_(isolate_button_widget.mapToGlobal(pos)))

        self.update_selectionSets_on_new_scene()

        # Create Locators  ----------------------------------------------------------------
        createLocator_button_widget = cw.QFlatToolButton(icon=media.create_locator_image, tooltip=helper.createLocator_tooltip_text)
        createLocator_button_widget.clicked.connect(bar.createLocator)
        sec.addWidget(createLocator_button_widget, "Create Locator", "create_locator")

        createLocator_menu = QtWidgets.QMenu(createLocator_button_widget)
        createLocator_menu.addAction(QtGui.QIcon(media.create_locator_image), "Select temp locators", bar.selectTempLocators)
        createLocator_menu.addAction(QtGui.QIcon(media.create_locator_image), "Remove temp locators", bar.deleteTempLocators)

        createLocator_button_widget.setContextMenuPolicy(QtCore.Qt.CustomContextMenu)
        createLocator_button_widget.customContextMenuRequested.connect(
            lambda pos: createLocator_menu.exec_(createLocator_button_widget.mapToGlobal(pos))
        )

        # align / match transforms ----------------------------------------------------------

        align_button_widget = cw.QFlatToolButton(icon=media.match_image, tooltip=helper.align_tooltip_text)
        align_button_widget.clicked.connect(bar.align_selected_objects)
        sec.addWidget(align_button_widget, "Align", "align")
        align_menu = QtWidgets.QMenu(align_button_widget)
        align_menu.addAction(QtGui.QIcon(media.align_menu_image), "Translation", partial(bar.align_selected_objects, pos=True, rot=False, scl=False))
        align_menu.addAction(QtGui.QIcon(media.align_menu_image), "Rotation", partial(bar.align_selected_objects, pos=False, rot=True, scl=False))
        align_menu.addAction(QtGui.QIcon(media.align_menu_image), "Scale", partial(bar.align_selected_objects, pos=False, rot=False, scl=True))
        align_menu.addSeparator()
        align_menu.addAction(QtGui.QIcon(media.match_image), "Match Range", bar.align_range)
        align_menu.addSeparator()
        align_menu.addAction(
            QtGui.QIcon(media.help_menu_image),
            "Help",
            lambda: general.open_url("https://thekeymachine.gitbook.io/base/the-toolbar/animation-tools/match-align"),
        )

        align_button_widget.setContextMenuPolicy(QtCore.Qt.CustomContextMenu)
        align_button_widget.customContextMenuRequested.connect(lambda pos: align_menu.exec_(align_button_widget.mapToGlobal(pos)))

        # Tracer -----------------------------------------------------------------------------
        tracer_button_widget = cw.QFlatToolButton(icon=media.tracer_menu_image, tooltip=helper.tracer_tooltip_text)
        tracer_button_widget.clicked.connect(bar.mod_tracer)
        sec.addWidget(tracer_button_widget, "Tracer", "tracer")

        tracer_menu = QtWidgets.QMenu(tracer_button_widget)
        action_tracer_connected = tracer_menu.addAction("Connected")
        action_tracer_connected.setCheckable(True)
        action_tracer_connected.triggered.connect(lambda x: bar.tracer_connected(connected=x, update_cb=bar.tracer_update_checkbox))

        tracer_menu.addAction(QtGui.QIcon(media.tracer_refresh_image), "Refresh", bar.tracer_refresh)
        tracer_menu.addAction(QtGui.QIcon(media.tracer_show_hide_image), "Show/Hide", bar.tracer_show_hide)
        tracer_menu.addAction(QtGui.QIcon(media.tracer_select_offset_image), "Select offset node", bar.select_tracer_offset_node)
        tracer_menu.addSeparator()

        tracer_style_sub_menu = tracer_menu.addMenu("Style")
        tracer_style_sub_menu.setIcon(QtGui.QIcon(media.tracer_set_color_image))
        tracer_style_sub_menu.addAction(QtGui.QIcon(media.tracer_grey_image), "Grey", bar.set_tracer_grey_color)
        tracer_style_sub_menu.addAction(QtGui.QIcon(media.tracer_red_image), "Red", bar.set_tracer_red_color)
        tracer_style_sub_menu.addAction(QtGui.QIcon(media.tracer_blue_image), "Blue", bar.set_tracer_blue_color)

        tracer_menu.addSeparator()
        tracer_menu.addAction(QtGui.QIcon(media.tracer_remove_image), "Remove", bar.remove_tracer_node)

        tracer_button_widget.setContextMenuPolicy(QtCore.Qt.CustomContextMenu)
        tracer_button_widget.customContextMenuRequested.connect(lambda pos: tracer_menu.exec_(tracer_button_widget.mapToGlobal(pos)))

        # Reset anim  -------------------------------------------------------------------------
        reset_values_button_widget = cw.QFlatToolButton(icon=media.reset_animation_image, tooltip=helper.reset_values_tooltip_text)
        reset_values_button_widget.clicked.connect(keyTools.reset_objects_mods)
        sec.addWidget(reset_values_button_widget, "Reset Values", "reset_values")

        reset_values_menu = QtWidgets.QMenu(reset_values_button_widget)
        reset_values_menu.addAction(QtGui.QIcon(media.reset_animation_image), "Set Default Values For Selected", keyTools.save_default_values)
        reset_values_menu.addAction(
            QtGui.QIcon(media.reset_animation_image), "Restore Default Values For Selected", keyTools.remove_default_values_for_selected_object
        )
        reset_values_menu.addSeparator()
        reset_values_menu.addAction(QtGui.QIcon(media.reset_animation_image), "Clear All Saved Data", keyTools.restore_default_data)
        reset_values_menu.addSeparator()
        reset_values_menu.addAction(
            QtGui.QIcon(media.help_menu_image),
            "Help",
            lambda: general.open_url("https://thekeymachine.gitbook.io/base/the-toolbar/animation-tools/reset-to-default"),
        )

        reset_values_button_widget.setContextMenuPolicy(QtCore.Qt.CustomContextMenu)
        reset_values_button_widget.customContextMenuRequested.connect(
            lambda pos: reset_values_menu.exec_(reset_values_button_widget.mapToGlobal(pos))
        )

        # Delete anim -------------------------------------------------------------------------
        deleteAnim_button_widget = cw.QFlatToolButton(icon=media.delete_animation_image, tooltip=helper.delete_animation_tooltip_text)
        deleteAnim_button_widget.clicked.connect(bar.mod_delete_animation)
        sec.addWidget(deleteAnim_button_widget, "Delete Anim", "delete_anim")

        selector_button_widget = cw.QFlatToolButton(tooltip=helper.selector_tooltip_text)
        selector_button_widget.setText("0")
        selector_button_widget.clicked.connect(bar.selector_window)
        sec.addWidget(selector_button_widget, "Selector", "selector")

        def update_selector_button_text():
            if not wutil.is_valid_widget(selector_button_widget):
                return
            selected_objects = cmds.ls(selection=True)
            num_selected = len(selected_objects)
            selector_button_widget.setText(str(num_selected))

        if toolbar.selection_script_job is not None and self.isScriptJobActive(toolbar.selection_script_job):
            cmds.scriptJob(kill=toolbar.selection_script_job, force=True)
        toolbar.selection_script_job = cmds.scriptJob(event=["SelectionChanged", update_selector_button_text])
        update_selector_button_text()

        sec = new_section()

        # Select opposite ---------------------------------------------------------------------
        select_opposite_button_widget = cw.QFlatToolButton(icon=media.select_opposite_image, tooltip=helper.select_opposite_tooltip_text)
        select_opposite_button_widget.clicked.connect(keyTools.selectOppositeHandler)
        sec.addWidget(select_opposite_button_widget, "Select Opposite", "select_opposite")

        # Copy opposite -----------------------------------------------------------------------
        copy_opposite_button_widget = cw.QFlatToolButton(icon=media.copy_opposite_image, tooltip=helper.copy_opposite_tooltip_text)
        copy_opposite_button_widget.clicked.connect(keyTools.copyOpposite)
        sec.addWidget(copy_opposite_button_widget, "Copy Opposite", "copy_opposite")

        # Mirror -----------------------------------------------------------------------
        mirror_button_widget = cw.QFlatToolButton(icon=media.mirror_image, tooltip=helper.mirror_tooltip_text)
        mirror_button_widget.clicked.connect(keyTools.mirror)
        sec.addWidget(mirror_button_widget, "Mirror", "mirror")

        mirror_menu = QtWidgets.QMenu(mirror_button_widget)
        mirror_menu.addAction(QtGui.QIcon(media.mirror_image), "Add Excepction Invert", keyTools.add_mirror_invert_exception)
        mirror_menu.addAction(QtGui.QIcon(media.mirror_image), "Add Excepction Keep", keyTools.add_mirror_keep_exception)
        mirror_menu.addAction(QtGui.QIcon(media.mirror_image), "Remove Exception", keyTools.remove_mirror_invert_exception)
        mirror_menu.addSeparator()
        mirror_menu.addAction(
            QtGui.QIcon(media.help_menu_image),
            "Help",
            lambda: general.open_url("https://thekeymachine.gitbook.io/base/the-toolbar/animation-tools/mirror"),
        )

        mirror_button_widget.setContextMenuPolicy(QtCore.Qt.CustomContextMenu)
        mirror_button_widget.customContextMenuRequested.connect(lambda pos: mirror_menu.exec_(mirror_button_widget.mapToGlobal(pos)))

        # Copy Paste Animation -----------------------------------------------------------------------
        copy_paste_animation_button_widget = cw.QFlatToolButton(
            icon=media.copy_paste_animation_image, tooltip=helper.copy_paste_animation_tooltip_text
        )
        copy_paste_animation_button_widget.clicked.connect(keyTools.copy_animation)
        sec.addWidget(copy_paste_animation_button_widget, "Copy/Paste Anim", "copy_paste_anim")

        cp_menu = QtWidgets.QMenu(copy_paste_animation_button_widget)
        cp_menu.addAction(QtGui.QIcon(media.copy_paste_animation_image), "Copy Animation", keyTools.copy_animation)
        cp_menu.addAction(QtGui.QIcon(media.paste_animation_image), "Paste Animation", keyTools.paste_animation)
        cp_menu.addAction(QtGui.QIcon(media.paste_insert_animation_image), "Paste Insert", keyTools.paste_insert_animation)
        cp_menu.addAction(QtGui.QIcon(media.paste_opposite_animation_image), "Paste Opposite", keyTools.paste_opposite_animation)
        cp_menu.addAction(QtGui.QIcon(media.paste_animation_image), "Paste To", lambda: keyTools.paste_animation_to())
        cp_menu.addSeparator()
        cp_menu.addAction(QtGui.QIcon(media.copy_pose_image), "Copy Pose", keyTools.copy_pose)
        cp_menu.addAction(QtGui.QIcon(media.paste_pose_image), "Paste Pose", keyTools.paste_pose)
        cp_menu.addSeparator()
        cp_menu.addAction(
            QtGui.QIcon(media.help_menu_image),
            "Help",
            lambda: general.open_url("https://thekeymachine.gitbook.io/base/the-toolbar/animation-tools/copy-paste-animation"),
        )

        copy_paste_animation_button_widget.setContextMenuPolicy(QtCore.Qt.CustomContextMenu)
        copy_paste_animation_button_widget.customContextMenuRequested.connect(
            lambda pos: cp_menu.exec_(copy_paste_animation_button_widget.mapToGlobal(pos))
        )

        # Select hierarchy -----------------------------------------------------------------------
        select_hierarchy_button_widget = cw.QFlatToolButton(icon=media.select_hierarchy_image, tooltip=helper.select_hierarchy_tooltip_text)
        select_hierarchy_button_widget.clicked.connect(bar.selectHierarchy)
        sec.addWidget(select_hierarchy_button_widget, "Select Hierarchy", "select_hierarchy")

        # Animation offset -----------------------------------------------------------------------
        animation_offset_button_widget = cw.QFlatToolButton(icon=media.animation_offset_image, tooltip=helper.animation_offset_tooltip_text)
        animation_offset_button_widget.setObjectName("anim_offset_button")
        animation_offset_button_widget.clicked.connect(self.toggleAnimOffsetButton)
        sec.addWidget(animation_offset_button_widget, "Anim Offset", "anim_offset")

        # FollowCam------------------------------------------------------------------------------
        create_follow_cam_button_widget = cw.QFlatToolButton(icon=media.follow_cam_image, tooltip=helper.follow_cam_tooltip_text)
        create_follow_cam_button_widget.clicked.connect(lambda *args: bar.create_follow_cam(translation=True, rotation=True))
        sec.addWidget(create_follow_cam_button_widget, "Follow Cam", "follow_cam")

        follow_cam_menu = QtWidgets.QMenu(create_follow_cam_button_widget)
        follow_cam_menu.addAction(
            QtGui.QIcon(media.follow_cam_image), "Follow only Translation", lambda *args: bar.create_follow_cam(translation=True, rotation=False)
        )
        follow_cam_menu.addAction(
            QtGui.QIcon(media.follow_cam_image), "Follow only Rotation", lambda *args: bar.create_follow_cam(translation=False, rotation=True)
        )
        follow_cam_menu.addSeparator()
        follow_cam_menu.addAction(QtGui.QIcon(media.remove_followCam), "Remove followCam", bar.remove_followCam)

        create_follow_cam_button_widget.setContextMenuPolicy(QtCore.Qt.CustomContextMenu)
        create_follow_cam_button_widget.customContextMenuRequested.connect(
            lambda pos: follow_cam_menu.exec_(create_follow_cam_button_widget.mapToGlobal(pos))
        )

        # Copy Link -----------------------------------------------------------------------

        self.link_checkbox_state = settings.get_setting("link_checkbox_state", False)
        self.link_obj_image_timer = False
        self.link_obj_thread = None
        self.link_obj_toggle_state = False

        link_objects_button_widget = cw.QFlatToolButton(icon=media.link_objects_image, tooltip=helper.link_objects_tooltip_text)
        link_objects_button_widget.clicked.connect(keyTools.mod_link_objects)
        sec.addWidget(link_objects_button_widget, "Link Objects", "link_objects")

        # ------funciones para crear el flashing icon al crear el auto-link callback

        def toggle_link_obj_button_image():
            if not isValid(self):
                return
            # For simplicity, we can use a custom property or just toggle based on a global state
            self.link_obj_toggle_state = not self.link_obj_toggle_state

            new_image = media.link_objects_on_image if self.link_obj_toggle_state else media.link_objects_image
            link_objects_button_widget.setIcon(QtGui.QIcon(new_image))

        def change_link_obj_image(interval):
            while self.link_obj_image_timer and isValid(self):
                time.sleep(interval)
                utils.executeDeferred(toggle_link_obj_button_image)

        def start_link_obj_toggle_image_thread():
            self.link_obj_image_timer = True
            self.link_obj_thread = threading.Thread(target=change_link_obj_image, args=(0.3,))
            self.link_obj_thread.start()

        def stop_link_obj_toggle_image_thread():
            self.link_obj_image_timer = False

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
            link_objects_button_widget.setIcon(QtGui.QIcon(media.link_objects_image))

        def toggle_auto_link_callback(*args):
            self.link_checkbox_state = not self.link_checkbox_state
            settings.set_setting("link_checkbox_state", self.link_checkbox_state)

            if self.link_checkbox_state:
                add_link_objects_callback()
            else:
                remove_link_objects_callback()

            action_auto_link.setChecked(self.link_checkbox_state)

        link_objects_menu = QtWidgets.QMenu(link_objects_button_widget)
        link_objects_menu.addAction(QtGui.QIcon(media.link_objects_image), "Copy Link Position", keyTools.copy_link)
        link_objects_menu.addAction(QtGui.QIcon(media.link_objects_image), "Paste Link Position", keyTools.paste_link)
        link_objects_menu.addSeparator()
        action_auto_link = link_objects_menu.addAction("Auto-link")
        action_auto_link.setCheckable(True)
        action_auto_link.setChecked(self.link_checkbox_state)
        action_auto_link.triggered.connect(toggle_auto_link_callback)

        link_objects_menu.addSeparator()
        link_objects_menu.addAction(
            QtGui.QIcon(media.help_menu_image),
            "Help",
            lambda: general.open_url("https://thekeymachine.gitbook.io/base/the-toolbar/animation-tools/link-objects"),
        )

        link_objects_button_widget.setContextMenuPolicy(QtCore.Qt.CustomContextMenu)
        link_objects_button_widget.customContextMenuRequested.connect(
            lambda pos: link_objects_menu.exec_(link_objects_button_widget.mapToGlobal(pos))
        )

        # Copy WorldSpace ----------------------------------------------------------------------------
        copy_worldspace_button_widget = cw.QFlatToolButton(icon=media.copy_worldspace_animation_image, tooltip=helper.copy_worldspace_tooltip_text)
        copy_worldspace_button_widget.clicked.connect(bar.mod_copy_worldspace_animation)
        sec.addWidget(copy_worldspace_button_widget, "Worldspace", "worldspace")

        ws_menu = QtWidgets.QMenu(copy_worldspace_button_widget)
        ws_menu.addAction(QtGui.QIcon(media.copy_worldspace_animation_image), "Copy Worldspace - All Animation", bar.color_copy_worldspace_animation)
        ws_menu.addAction(QtGui.QIcon(media.copy_worldspace_animation_image), "Copy Worldspace - Selected Range", bar.copy_range_worldspace_animation)
        ws_menu.addAction(QtGui.QIcon(media.paste_worldspace_animation_image), "Paste Worldspace", bar.color_paste_worldspace_animation)
        ws_menu.addSeparator()
        ws_menu.addAction(
            QtGui.QIcon(media.copy_worldspace_frame_animation_image), "Copy Worldspace - Current Frame", bar.copy_worldspace_single_frame
        )
        ws_menu.addAction(QtGui.QIcon(media.paste_worldspace_frame_animation_image), "Paste Worldspace", bar.paste_worldspace_single_frame)
        ws_menu.addSeparator()
        ws_menu.addAction(
            QtGui.QIcon(media.help_menu_image),
            "Help",
            lambda: general.open_url("https://thekeymachine.gitbook.io/base/the-toolbar/animation-tools/copy-worldspace"),
        )

        copy_worldspace_button_widget.setContextMenuPolicy(QtCore.Qt.CustomContextMenu)
        copy_worldspace_button_widget.customContextMenuRequested.connect(lambda pos: ws_menu.exec_(copy_worldspace_button_widget.mapToGlobal(pos)))

        # Temp Pivot ----------------------------------------------------------------------------
        temp_pivot_button_widget = cw.QFlatToolButton(icon=media.temp_pivot_image, tooltip=helper.temp_pivot_tooltip_text)
        temp_pivot_button_widget.clicked.connect(lambda *args: bar.create_temp_pivot(False))
        sec.addWidget(temp_pivot_button_widget, "Temp Pivot", "temp_pivot")

        tp_menu = QtWidgets.QMenu(temp_pivot_button_widget)
        tp_menu.addAction(QtGui.QIcon(media.temp_pivot_image), "Last pivot used", lambda *args: bar.create_temp_pivot(True))
        tp_menu.addSeparator()
        tp_menu.addAction(
            QtGui.QIcon(media.help_menu_image),
            "Help",
            lambda: general.open_url("https://thekeymachine.gitbook.io/base/the-toolbar/animation-tools/temp-pivots"),
        )

        temp_pivot_button_widget.setContextMenuPolicy(QtCore.Qt.CustomContextMenu)
        temp_pivot_button_widget.customContextMenuRequested.connect(lambda pos: tp_menu.exec_(temp_pivot_button_widget.mapToGlobal(pos)))

        # Micro Move ----------------------------------------------------------------------------
        micro_move_button_widget = cw.QFlatToolButton(icon=media.ruler_image, tooltip=helper.micro_move_tooltip_text)
        micro_move_button_widget.setObjectName("micro_move_button")
        micro_move_button_widget.clicked.connect(self.toggle_micro_move_button)
        sec.addWidget(micro_move_button_widget, "Micro Move", "micro_move")

        # Key Menu -------------------------------------------------------------------------------
        block_keys_button_widget = cw.QFlatToolButton(icon=media.reblock_keys_image, tooltip=helper.block_keys_tooltip_text)
        block_keys_button_widget.clicked.connect(keyTools.share_keys)
        sec.addWidget(block_keys_button_widget, "Block Keys", "block_keys")

        block_keys_menu = QtWidgets.QMenu(block_keys_button_widget)
        block_keys_menu.addAction(QtGui.QIcon(media.reblock_keys_image), "reBlock", keyTools.reblock_move)
        block_keys_menu.addAction(QtGui.QIcon(media.reblock_keys_image), "Share Keys", keyTools.share_keys)
        block_keys_menu.addAction(QtGui.QIcon(media.reblock_keys_image), "Bake Anim", keyTools.bake_anim_window)
        block_keys_menu.addAction(QtGui.QIcon(media.reblock_keys_image), "ToolBox Orbit", lambda: ui.orbit_window(0, 0))
        block_keys_menu.addAction(QtGui.QIcon(media.reblock_keys_image), "Gimbal Fixer", bar.gimbal_fixer_window)

        block_keys_button_widget.setContextMenuPolicy(QtCore.Qt.CustomContextMenu)
        block_keys_button_widget.customContextMenuRequested.connect(lambda pos: block_keys_menu.exec_(block_keys_button_widget.mapToGlobal(pos)))

        sec = new_section()

        # Selection Sets  ----------------------------------------------------------------------------
        selection_sets_button_widget = cw.QFlatToolButton(icon=media.selection_sets_image, tooltip=helper.selection_sets_tooltip_text)
        selection_sets_button_widget.setObjectName("toggle_selection_sets_workspace_b")
        selection_sets_button_widget.clicked.connect(self.toggle_selection_sets_workspace)
        sec.addWidget(selection_sets_button_widget, "Selection Sets", "selection_sets")

        # customGraph ----------------------------------------------------------------------------
        def open_customGraph():
            import TheKeyMachine.core.customGraph as cg  # type: ignore

            cg.createCustomGraph()

        open_custom_graph_button_widget = cw.QFlatToolButton(icon=media.customGraph_image, tooltip=helper.customGraph_tooltip_text)
        open_custom_graph_button_widget.clicked.connect(open_customGraph)
        sec.addWidget(open_custom_graph_button_widget, "Custom Graph", "custom_graph")

        # custom tools ----------------------------------------------------------------------------
        importlib.invalidate_caches()
        import TheKeyMachine_user_data.connect.tools.tools as connectToolBox  # type: ignore

        def initialize_tool_menu():
            importlib.reload(connectToolBox)
            toolBox_menu.clear()

            # Generar un mapeo de nombre a ID
            name_to_id = {}
            for i in range(1, 100):  # Asumiendo un máximo de 99 herramientas
                tool_id = f"t{str(i).zfill(2)}"
                try:
                    tool_name = getattr(connectToolBox, f"{tool_id}_name")
                    name_to_id[tool_name] = tool_id
                except AttributeError:
                    break

            def create_command_func(command, is_python):
                if is_python:
                    return lambda: exec(command)
                else:
                    return lambda: mel.eval(command)

            for tool_name in connectToolBox.tool_order:
                if tool_name:
                    tool_id = name_to_id.get(tool_name)
                    if not tool_id:
                        continue
                    try:
                        name = getattr(connectToolBox, f"{tool_id}_name")
                        image = getattr(connectToolBox, f"{tool_id}_image")
                        is_python = getattr(connectToolBox, f"{tool_id}_is_python")
                        command = getattr(connectToolBox, f"{tool_id}_command")

                        if not name:
                            continue

                        # fix para mostrar imagenes
                        dot_images = {
                            "green_dot.png": media.green_dot_image,
                            "blue_dot.png": media.blue_dot_image,
                            "red_dot.png": media.red_dot_image,
                            "grey_dot.png": media.grey_dot_image,
                            "yellow_dot.png": media.yellow_dot_image,
                        }
                        if image in dot_images:
                            image = dot_images[image]

                        if name == "separator":
                            toolBox_menu.addSeparator()
                        else:
                            cmd_func = create_command_func(command, is_python)
                            toolBox_menu.addAction(QtGui.QIcon(image), name, cmd_func)
                    except AttributeError:
                        pass

            toolBox_menu.addSeparator()
            toolBox_menu.addAction(
                QtGui.QIcon(media.settings_image),
                "Open config file",
                lambda: general.open_file("TheKeyMachine_user_data/connect/tools", "tools.py"),
            )
            toolBox_menu.addAction(QtGui.QIcon(media.reload_image), "Reload menu", initialize_tool_menu)

        toolBox_button_widget = cw.QFlatToolButton(icon=media.custom_tools_image, tooltip=helper.custom_tools_tooltip_text)
        toolBox_button_widget.setVisible(bool(CUSTOM_TOOLS_MENU))
        sec.addWidget(toolBox_button_widget, "Custom Tools", "custom_tools")

        toolBox_menu = QtWidgets.QMenu(toolBox_button_widget)
        toolBox_button_widget.setContextMenuPolicy(QtCore.Qt.CustomContextMenu)
        toolBox_button_widget.customContextMenuRequested.connect(lambda pos: toolBox_menu.exec_(toolBox_button_widget.mapToGlobal(pos)))
        toolBox_button_widget.clicked.connect(lambda: toolBox_menu.exec_(QtGui.QCursor.pos()))

        initialize_tool_menu()

        # custom scripts ----------------------------------------------------------------------------
        import TheKeyMachine_user_data.connect.scripts.scripts as cbScripts  # type: ignore

        def initialize_scripts_menu():
            importlib.reload(cbScripts)
            customScripts_menu.clear()

            # Generar un mapeo de nombre a ID
            name_to_id = {}
            for i in range(1, 100):  # Asumiendo un máximo de 99 scripts
                script_id = f"s{str(i).zfill(2)}"
                try:
                    script_name = getattr(cbScripts, f"{script_id}_name")
                    name_to_id[script_name] = script_id
                except AttributeError:
                    break

            def create_command_func(command, is_python):
                if is_python:
                    return lambda: exec(command)
                else:
                    return lambda: mel.eval(command)

            for script_name in cbScripts.scripts_order:
                if script_name:
                    script_id = name_to_id.get(script_name)
                    if not script_id:
                        continue
                    try:
                        name = getattr(cbScripts, f"{script_id}_name")
                        image = getattr(cbScripts, f"{script_id}_image")
                        is_python = getattr(cbScripts, f"{script_id}_is_python")
                        command = getattr(cbScripts, f"{script_id}_command")

                        if not name:
                            continue

                        # fix para mostrar imagenes
                        dot_images = {
                            "green_dot.png": media.green_dot_image,
                            "blue_dot.png": media.blue_dot_image,
                            "red_dot.png": media.red_dot_image,
                            "grey_dot.png": media.grey_dot_image,
                            "yellow_dot.png": media.yellow_dot_image,
                        }
                        if image in dot_images:
                            image = dot_images[image]

                        if name == "separator":
                            customScripts_menu.addSeparator()
                        else:
                            cmd_func = create_command_func(command, is_python)
                            customScripts_menu.addAction(QtGui.QIcon(image), name, cmd_func)
                    except AttributeError:
                        pass

            customScripts_menu.addSeparator()
            customScripts_menu.addAction(
                QtGui.QIcon(media.settings_image),
                "Open scripts file",
                lambda: general.open_file("TheKeyMachine_user_data/connect/scripts", "scripts.py"),
            )
            customScripts_menu.addAction(QtGui.QIcon(media.reload_image), "Reload menu", initialize_scripts_menu)

        customScripts_button_widget = cw.QFlatToolButton(icon=media.custom_scripts_image, tooltip=helper.custom_scripts_tooltip_text)
        customScripts_button_widget.setVisible(bool(CUSTOM_SCRIPTS_MENU))
        sec.addWidget(customScripts_button_widget, "Custom Scripts", "custom_scripts")

        customScripts_menu = QtWidgets.QMenu(customScripts_button_widget)
        customScripts_button_widget.setContextMenuPolicy(QtCore.Qt.CustomContextMenu)
        customScripts_button_widget.customContextMenuRequested.connect(
            lambda pos: customScripts_menu.exec_(customScripts_button_widget.mapToGlobal(pos))
        )
        customScripts_button_widget.clicked.connect(lambda: customScripts_menu.exec_(QtGui.QCursor.pos()))

        initialize_scripts_menu()

        # _____________________ Workspaces Section ____________________________ #
        sec = new_section(spacing=2, hiddeable=False)

        overshootSliders = settings.get_setting("sliders_overshoot", False)

        def _setOvershoot(state):
            settings.set_setting("sliders_overshoot", state)
            sw.globalSignals.overshootChanged.emit(state)

        toolbar_config_button_widget = cw.QFlatToolButton(icon=media.settings_image)
        toolbar_config_button_widget.setObjectName("settings_toolbar_button")
        sec.addWidget(toolbar_config_button_widget, "Settings", "settings")

        # Build your menu with your cw.MenuWidget; make sure the button is the PARENT
        toolbar_menu = cw.MenuWidget(parent=toolbar_config_button_widget)

        # === Help submenu ===
        help_menu = cw.MenuWidget(QtGui.QIcon(media.help_menu_image), "Help")
        toolbar_menu.addMenu(help_menu, description="Resources for help, documentation and community.")
        help_menu.addAction(
            QtGui.QIcon(media.discord_image),
            "Discord Community",
            lambda: general.open_url("https://discord.gg/G2J5yyjz"),
            description="Join the community for questions and support.",
        )
        help_menu.addAction(
            QtGui.QIcon(media.help_menu_image),
            "Knowledge base",
            lambda: general.open_url("https://thekeymachine.gitbook.io/base"),
            description="Read the official documentation.",
        )
        help_menu.addAction(
            QtGui.QIcon(media.youtube_image),
            "Youtube channel",
            lambda: general.open_url("https://www.youtube.com/@TheKeyMachineAnimationTools"),
            description="Watch tutorials and features demos.",
        )

        # === Config submenu ===
        config_menu = cw.MenuWidget(QtGui.QIcon(media.settings_image), "Config")
        toolbar_menu.addMenu(config_menu, description="Tool configuration, hotkeys and UI preferences.")
        config_menu.addSection("Shelf icon")
        config_menu.addAction("Add Toggle Button To Shelf", self.create_shelf_icon, description="Creates a shelf button to show/hide this toolbar.")

        config_menu.addSection("Tools settings")
        show_tooltips_action = config_menu.addAction("Show tooltips", description="Show or hide floating tooltips.")
        show_tooltips_action.setCheckable(True)

        def read_show_tooltips():
            return settings.get_setting("show_tooltips", True)

        def update_show_tooltips(value):
            settings.set_setting("show_tooltips", value)

        def update_tooltips():
            show_tooltips_val = read_show_tooltips()

            from TheKeyMachine.tooltips import QFlatTooltipManager

            QFlatTooltipManager.enabled = show_tooltips_val

            def get_safe_helper(attr_name):
                return getattr(helper, attr_name, "")

            buttons_and_tooltips = [
                (pointer_button_widget, get_safe_helper("pointer_tooltip_text")),
                (isolate_button_widget, get_safe_helper("isolate_tooltip_text")),
                (block_keys_button_widget, get_safe_helper("block_keys_tooltip_text")),
                (createLocator_button_widget, get_safe_helper("createLocator_tooltip_text")),
                (align_button_widget, get_safe_helper("align_tooltip_text")),
                (tracer_button_widget, get_safe_helper("tracer_tooltip_text")),
                (deleteAnim_button_widget, get_safe_helper("delete_animation_tooltip_text")),
                (reset_values_button_widget, get_safe_helper("reset_values_tooltip_text")),
                (select_opposite_button_widget, get_safe_helper("select_opposite_tooltip_text")),
                (copy_opposite_button_widget, get_safe_helper("copy_opposite_tooltip_text")),
                (mirror_button_widget, get_safe_helper("mirror_tooltip_text")),
                (copy_paste_animation_button_widget, get_safe_helper("copy_paste_animation_tooltip_text")),
                (selector_button_widget, get_safe_helper("selector_tooltip_text")),
                (select_hierarchy_button_widget, get_safe_helper("select_hierarchy_tooltip_text")),
                (animation_offset_button_widget, get_safe_helper("animation_offset_tooltip_text")),
                (link_objects_button_widget, get_safe_helper("link_objects_tooltip_text")),
                (create_follow_cam_button_widget, get_safe_helper("follow_cam_tooltip_text")),
                (copy_worldspace_button_widget, get_safe_helper("copy_worldspace_tooltip_text")),
                (temp_pivot_button_widget, get_safe_helper("temp_pivot_tooltip_text")),
                (micro_move_button_widget, get_safe_helper("micro_move_tooltip_text")),
                (selection_sets_button_widget, get_safe_helper("selection_sets_tooltip_text")),
                (open_custom_graph_button_widget, get_safe_helper("customGraph_tooltip_text")),
                (toolBox_button_widget, get_safe_helper("custom_tools_tooltip_text")),
                (customScripts_button_widget, get_safe_helper("custom_scripts_tooltip_text")),
                (self.move_keyframes_intField, get_safe_helper("move_keyframes_intField_widget_tooltip_text")),
                (nudge_keyleft_b_widget, get_safe_helper("nudge_keyleft_b_widget_tooltip_text")),
                (remove_inbetween_b_widget, get_safe_helper("remove_inbetween_b_widget_tooltip_text")),
                (insert_inbetween_b_widget, get_safe_helper("insert_inbetween_b_widget_tooltip_text")),
                (nudge_keyright_b_widget, get_safe_helper("nudge_keyright_b_widget_tooltip_text")),
                (clear_selected_keys_widget, get_safe_helper("clear_selected_keys_widget_tooltip_text")),
                (select_scene_animation_widget, get_safe_helper("select_scene_animation_widget_tooltip_text")),
                (toolbar_config_button_widget, "<b>Config</b><br><br>Open TheKeyMachine configuration and help menu."),
            ]

            for button_widget, tooltip_html in buttons_and_tooltips:
                try:
                    if not show_tooltips_val:
                        pass

                    if hasattr(button_widget, "set_tooltip_info"):
                        button_widget.set_tooltip_info(*sliders.parse_tt(tooltip_html))
                    elif hasattr(button_widget, "set_tooltip_data"):
                        button_widget.set_tooltip_data(text=tooltip_html)
                except Exception:
                    pass

        def toggle_tooltips(value):
            update_show_tooltips(value)
            update_tooltips()

        self._toggle_tooltips_func = toggle_tooltips
        show_tooltips_action.setChecked(show_tooltips)
        show_tooltips_action.toggled.connect(self._toggle_tooltips_func)

        # Initial call
        update_tooltips()

        overshoot_action = config_menu.addAction("Overshoot Sliders", description="Allow sliders to reach values beyond -100 to 100.")
        overshoot_action.setCheckable(True)
        overshoot_action.setChecked(overshootSliders)
        overshoot_action.toggled.connect(_setOvershoot)

        config_menu.addSection("Toolbar's icons alignment")
        align_group = QActionGroup(config_menu)
        left_align_action = config_menu.addAction("Left", description="Align icons to the left.")
        center_align_action = config_menu.addAction("Center", description="Align icons to the center.")
        right_align_action = config_menu.addAction("Right", description="Align icons to the right.")
        for act in (left_align_action, center_align_action, right_align_action):
            act.setCheckable(True)
            align_group.addAction(act)

        left_align_action.triggered.connect(lambda: update_toolbar_icon_alignment("Left"))
        center_align_action.triggered.connect(lambda: update_toolbar_icon_alignment("Center"))
        right_align_action.triggered.connect(lambda: update_toolbar_icon_alignment("Right"))

        current_align = get_current_icon_alignment()
        {"Left": left_align_action, "Center": center_align_action, "Right": right_align_action}.get(current_align, center_align_action).setChecked(
            True
        )

        config_menu.addSection("Hotkeys")
        config_menu.addAction("Add TheKeyMachine Hotkeys", hotkeys.create_TheKeyMachine_hotkeys, description="Setup Maya hotkeys for TKM tools.")

        config_menu.addSection("General")
        config_menu.addAction(QtGui.QIcon(media.reload_image), "Reload", self.reload, description="Refresh the TKM interface.")

        toolbar_menu.addMenu(self._create_dock_menu(), description="Dock the toolbar to different Maya UI panels.")

        # Separators and others
        toolbar_menu.addSeparator()
        toolbar_menu.addAction(QtGui.QIcon(media.uninstall_image), "Uninstall", ui.uninstall, description="Remove TheKeyMachine from Maya.")
        toolbar_menu.addSeparator()
        toolbar_menu.addAction(QtGui.QIcon(media.about_image), "About", ui.about_window, description="Show version info and credits.")

        def _open_menu_at_cursor():
            toolbar_menu.popup(QtGui.QCursor.pos())

        def _on_toolbar_context_menu(pos):
            if self.main_toolbar_widget.childAt(pos):
                return
            _open_menu_at_cursor()

        toolbar_config_button_widget.clicked.connect(_open_menu_at_cursor)
        toolbar_config_button_widget.setContextMenuPolicy(QtCore.Qt.CustomContextMenu)
        toolbar_config_button_widget.customContextMenuRequested.connect(lambda _pos: _open_menu_at_cursor())

        self.main_toolbar_widget.setContextMenuPolicy(QtCore.Qt.CustomContextMenu)
        self.main_toolbar_widget.customContextMenuRequested.connect(_on_toolbar_context_menu)


_toolbar_instance = None


def get_toolbar():
    global _toolbar_instance
    return _toolbar_instance


def show():
    global _toolbar_instance

    # Close existing UI robustly
    try:
        workspace_control = WorkspaceName + "WorkspaceControl"
        if cmds.workspaceControl(workspace_control, q=True, exists=True):
            cmds.deleteUI(workspace_control, control=True)
    except Exception:
        pass

    if _toolbar_instance and isValid(_toolbar_instance):
        try:
            _toolbar_instance.close()
            _toolbar_instance.deleteLater()
        except Exception:
            pass

    _toolbar_instance = toolbar()
    _toolbar_instance.showWindow()


def toggle():
    global _toolbar_instance

    try:
        workspace_control = WorkspaceName + "WorkspaceControl"
        if cmds.workspaceControl(workspace_control, query=True, exists=True):
            vis_state = cmds.workspaceControl(workspace_control, query=True, visible=True)

            if vis_state:
                cmds.workspaceControl(workspace_control, edit=True, visible=False)
            else:
                cmds.workspaceControl(workspace_control, edit=True, restore=True)
            return
    except Exception:
        pass
    _toolbar_instance = toolbar()
    _toolbar_instance.showWindow()
