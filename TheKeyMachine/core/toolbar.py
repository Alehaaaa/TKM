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

from functools import partial

try:
    from importlib import reload, import_module, invalidate_caches
except ImportError:
    import_module = None
    invalidate_caches = None
    from imp import reload
except ImportError:
    import_module = None
    invalidate_caches = None
    pass

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
import TheKeyMachine.mods.updater as updater  # type: ignore
import TheKeyMachine.core.toolbox as toolbox  # type: ignore
import TheKeyMachine.core.callback_manager as callbacks  # type: ignore

from TheKeyMachine.widgets import sliderWidget as sw  # type: ignore
from TheKeyMachine.widgets import customWidgets as cw  # type: ignore
from TheKeyMachine.widgets import customDialogs as customDialogs  # type: ignore
from TheKeyMachine.widgets import util as wutil  # type: ignore
import TheKeyMachine.sliders as sliders  # type: ignore

from TheKeyMachine.tooltips import QFlatTooltipManager

mods = [general, ui, keyTools, helper, media, bar, hotkeys, settings, cg, updater, style, sw, cw, customDialogs, wutil, sliders, toolbox]

for m in mods:
    if m:
        reload(m)

# -----------------------------------------------------------------------------------------------------------------------------
#              TheKeyMachine configuration is loaded from the JSON, or the default installation paths are used.               #
# -----------------------------------------------------------------------------------------------------------------------------
INSTALL_PATH = general.config["INSTALL_PATH"]
USER_FOLDER_PATH = general.config["USER_FOLDER_PATH"]
INTERNET_CONNECTION = general.config["INTERNET_CONNECTION"]
BUG_REPORT = general.config["BUG_REPORT"]
CUSTOM_TOOLS_MENU = general.config["CUSTOM_TOOLS_MENU"]
CUSTOM_TOOLS_EDITABLE_BY_USER = general.config["CUSTOM_TOOLS_EDITABLE_BY_USER"]
CUSTOM_SCRIPTS_MENU = general.config["CUSTOM_SCRIPTS_MENU"]
CUSTOM_SCRIPTS_EDITABLE_BY_USER = general.config["CUSTOM_SCRIPTS_EDITABLE_BY_USER"]


# -----------------------------------------------------------------------------------------------------------------------------
#    It attempts to load the user_preferences. If this is a new installation, it won't exist and the file must be created     #
# -----------------------------------------------------------------------------------------------------------------------------


# Attempt to import the user preferences module
try:
    from TheKeyMachine_user_data.preferences import user_preferences  # type: ignore
except ImportError:
    user_preferences = None


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

    reload(TheKeyMachine_user_data)  # type: ignore
    import TheKeyMachine_user_data.connect  # type: ignore
except ImportError:
    reload(TheKeyMachine_user_data)


# -----------------------------------------------------------------------------------------------------------------------------
#                                          Creation of the toolbar and UI class                                               #
# -----------------------------------------------------------------------------------------------------------------------------


WorkspaceName = "k"
selection_sets_workspace = "s"


COLOR = ui.Color()


class toolbar(MayaQWidgetDockableMixin, QtWidgets.QDialog):
    def __init__(self, parent=None):
        super().__init__(parent=parent)
        self.setWindowTitle("TheKeyMachine")
        self.setObjectName(WorkspaceName)
        self.setContextMenuPolicy(QtCore.Qt.PreventContextMenu)

        self._callback_manager = callbacks.get_callback_manager()
        self._callback_manager.scene_opened.connect(self._on_scene_opened)
        self._callback_manager.scene_new.connect(self._on_scene_opened)

        self.shelf_painter = None
        self.current_layout = cmds.workspaceLayoutManager(q=True, current=True)

        # Initial state variables from settingsMod
        self.toggleAnimOffsetButtonState = settings.get_setting("toggleAnimOffsetButtonState", False)
        self.micro_move_button_state = settings.get_setting("micro_move_button_state", False)
        self.link_checkbox_state = settings.get_setting("link_checkbox_state", False)
        self.orbit_button_widget = None

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

        self.anim_offset_run_timer = True
        self.micro_move_run_timer = True
        self.animation_offset_original_values = {}
        self.setgroup_states = {}
        self.setgroup_buttons = {}

        # Link object runtime states
        self.link_obj_image_timer = False
        self.link_obj_toggle_state = False
        self.link_obj_thread = None

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
        global _toolbar_instance
        _toolbar_instance = None

        try:
            callbacks.shutdown_callback_manager()
        except Exception:
            pass

        # Stop animation offset thread
        self.anim_offset_run_timer = False
        if hasattr(self, "anim_offset_thread") and self.anim_offset_thread and self.anim_offset_thread.is_alive():
            self.anim_offset_thread.join(timeout=0.5)

        # Stop micro move thread
        self.micro_move_run_timer = False
        if hasattr(self, "micro_move_thread_obj") and self.micro_move_thread_obj and self.micro_move_thread_obj.is_alive():
            self.micro_move_thread_obj.join(timeout=0.5)

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

    def _on_scene_opened(self, *_args):
        if not isValid(self):
            return
        self.update_selectionSets_on_new_scene()
        self.update_popup_menu()

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

        control.setSizePolicy(QtWidgets.QSizePolicy.Minimum, QtWidgets.QSizePolicy.Minimum)

        if self.isFloating():
            return tab_handle.tabBar().setVisible(False)

        self.shelf_painter = cw.QFlatShelfPainter(tab_handle)
        self.shelf_painter.setGeometry(tab_handle.geometry())
        self.shelf_painter.updateDrawingParameters(tabbar_width=tab_handle.tabBar().geometry())
        self.shelf_painter.move(tab_handle.tabBar().pos())

        self.shelf_painter.show()
        # tab_handle.tabBar().setVisible(True)

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
        icon_path = media.tool_icon
        icon_path = os.path.normpath(icon_path)
        current_shelf_tab = cmds.tabLayout("ShelfLayout", query=True, selectTab=True)
        cmds.shelfButton(parent=current_shelf_tab, image=icon_path, command=command, label=button_name)

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
                    image=media.grey_got_image,
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
                    image=media.grey_got_image,
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

        try:
            callbacks.shutdown_callback_manager()
        except Exception:
            pass

        try:
            for widget in QtWidgets.QApplication.topLevelWidgets():
                if widget.property("tkm_floating_widget"):
                    widget.close()
                    try:
                        widget.deleteLater()
                    except Exception:
                        pass
        except Exception:
            pass

        # Importa el módulo y recarga
        toolbar_module = import_module(toolbar_module_name)
        customGraph_module = import_module(customGraph_module_name)

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

        reload(toolbar_module)
        reload(customGraph_module)

        # Use the global show() instead of module-level 'tb'
        toolbar_module.show()

    def unload(self, *args):
        """
        Closes the tool and removes callbacks (safe to call multiple times).
        """
        global _toolbar_instance
        _toolbar_instance = None

        try:
            callbacks.shutdown_callback_manager()
        except Exception:
            pass

        try:
            for widget in QtWidgets.QApplication.topLevelWidgets():
                if widget.property("tkm_floating_widget"):
                    widget.close()
                    try:
                        widget.deleteLater()
                    except Exception:
                        pass
        except Exception:
            pass

        try:
            workspace_control = WorkspaceName + "WorkspaceControl"
            if cmds.workspaceControl(workspace_control, q=True, exists=True):
                cmds.deleteUI(workspace_control, control=True)
        except Exception:
            pass

        try:
            if isValid(self):
                self.blockSignals(True)
                self.close()
                self.deleteLater()
        except Exception:
            pass

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
        new_set_name_with_color = f"{new_set_name}_{current_color_suffix}"

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
        ui.open_selection_set_creation_dialog(controller=self)

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

    def get_selection_sets(self):
        sel_set_name = "TheKeyMachine_SelectionSet"
        if not cmds.objExists(sel_set_name):
            return []
        self._migrate_legacy_selection_set_groups(sel_set_name)
        selection_sets = []
        for node in cmds.sets(sel_set_name, q=True) or []:
            if not cmds.objExists(node):
                continue
            if str(node).endswith("_setgroup"):
                continue
            selection_sets.append(node)
        return selection_sets

    def _ensure_selection_sets_root(self):
        sel_set_name = "TheKeyMachine_SelectionSet"

        if not cmds.objExists(sel_set_name):
            cmds.sets(name=sel_set_name, empty=True)

        self._migrate_legacy_selection_set_groups(sel_set_name)
        return sel_set_name

    def _migrate_legacy_selection_set_groups(self, sel_set_name):
        legacy_groups = [node for node in (cmds.sets(sel_set_name, q=True) or []) if str(node).endswith("_setgroup")]
        for legacy_group in legacy_groups:
            for subset in cmds.sets(legacy_group, q=True) or []:
                if not cmds.objExists(subset):
                    continue
                try:
                    cmds.sets(subset, add=sel_set_name)
                except Exception:
                    pass
                try:
                    cmds.sets(subset, remove=legacy_group)
                except Exception:
                    pass
            if cmds.objExists(legacy_group):
                members_left = cmds.sets(legacy_group, q=True) or []
                if not members_left:
                    try:
                        cmds.delete(legacy_group)
                    except Exception:
                        pass

    def create_new_set_and_update_buttons(self, color_suffix, set_name_field, set_group_combo=None, *args):
        selection = cmds.ls(selection=True)
        if not selection:
            wutil.make_inViewMessage("No selection to create set")
            return False

        new_set_name = set_name_field.text()
        sel_set_name = self._ensure_selection_sets_root()

        new_set_name = new_set_name.replace(" ", "_")

        if not re.match("^[a-zA-Z_][a-zA-Z0-9_]*$", new_set_name):
            cmds.warning("Invalid set name. Name can't start with a number or contain invalid characters")
            return False

        new_set_name += f"{color_suffix}"

        if not cmds.objExists(new_set_name):
            new_set = cmds.sets(name=new_set_name, empty=True)
            cmds.addAttr(new_set, longName="hidden", attributeType="bool", defaultValue=False)

            if cmds.ls(selection=True):
                cmds.sets(cmds.ls(selection=True), add=new_set)

            cmds.sets(new_set, add=sel_set_name)

            self.create_buttons_for_sel_sets()
            set_name_field.clear()
            return True

        else:
            cmds.warning(f"{new_set_name} already exists")
            return False

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
        selection = cmds.ls(selection=True)
        if not selection:
            return wutil.make_inViewMessage("No selection to add")
        elif not cmds.objExists(set_name):
            return cmds.warning(f"Set {set_name} does not exist")

        cmds.sets(selection, add=set_name)

    def remove_selection_from_set(self, set_name, *args):
        selection = cmds.ls(selection=True)
        if not selection:
            return wutil.make_inViewMessage("No selection to remove")
        elif not cmds.objExists(set_name):
            return cmds.warning(f"Set {set_name} does not exist")

        cmds.sets(selection, remove=set_name)

    def update_selection_to_set(self, set_name, *args):
        selection = cmds.ls(selection=True)
        if not selection:
            return wutil.make_inViewMessage("No selection to update")
        elif not cmds.objExists(set_name):
            return cmds.warning(f"Set {set_name} does not exist")

        current_members = cmds.sets(set_name, q=True) or []
        if current_members:
            cmds.sets(current_members, remove=set_name)
        cmds.sets(selection, add=set_name)

    def delete_sets_by_color_suffix(self, color_suffix, *args):
        target_suffix = color_suffix if str(color_suffix).startswith("_") else f"_{color_suffix}"
        removed_any = False

        for subset in list(self.get_selection_sets()):
            if not cmds.objExists(subset):
                continue
            if not subset.endswith(target_suffix):
                continue
            if cmds.objExists("TheKeyMachine_SelectionSet"):
                try:
                    cmds.sets(subset, remove="TheKeyMachine_SelectionSet")
                except Exception:
                    pass
            cmds.delete(subset)
            removed_any = True

        if removed_any:
            cmds.evalDeferred(self.create_buttons_for_sel_sets)

    color_names = {
        "_01": "Red Light",
        "_02": "Red",
        "_03": "Red Dark",
        "_04": "Orange Light",
        "_05": "Orange",
        "_06": "Orange Dark",
        "_07": "Yellow Light",
        "_08": "Yellow",
        "_09": "Yellow Dark",
        "_10": "Green Light",
        "_11": "Green",
        "_12": "Green Dark",
        "_13": "Blue Light",
        "_14": "Blue",
        "_15": "Blue Dark",
        "_16": "Teal Light",
        "_17": "Teal",
        "_18": "Teal Dark",
        "_19": "Purple Light",
        "_20": "Purple",
        "_21": "Purple Dark",
        "_22": "Pink Light",
        "_23": "Pink",
        "_24": "Pink Dark",
    }

    def create_color_submenu(self, set_name, parent_menu):
        for color_suffix, image_path in media.selection_set_color_images.items():
            color_name = self.color_names.get(color_suffix, "Default")

            cmds.menuItem(
                label=color_name,
                image=image_path,
                parent=parent_menu,
                command=partial(self.set_set_color, set_name, color_suffix),
            )

    def clear_selection_sets(self, *args):
        ui.refresh_selection_sets_window()

    def selection_sets_empty_setup(self, *args):
        ui.close_selection_sets_window()

    def selection_sets_setup(self, *args):
        ui.open_selection_sets_toolbar_action(controller=self)

    def create_buttons_for_sel_sets(self, *args):
        ui.refresh_selection_sets_window()

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

    def remove_set_and_update_buttons(self, set_name, set_group=None, *args):
        if cmds.objExists(set_name):
            if cmds.objExists("TheKeyMachine_SelectionSet"):
                try:
                    cmds.sets(set_name, remove="TheKeyMachine_SelectionSet")
                except Exception:
                    pass
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

        if selection:
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

    def toggle_micro_move_button(self, checked=None):
        if checked is not None:
            self.micro_move_button_state = checked
        else:
            self.micro_move_button_state = not self.micro_move_button_state

        settings.set_setting("micro_move_button_state", self.micro_move_button_state)

        if self.micro_move_button_state:
            cmds.undoInfo(openChunk=True)
            # cmds.iconTextButton("micro_move_button", e=True, bgc=(0.3, 0.3, 0.3))
            self.micro_move_run_timer = True
            bar.activate_micro_move()

            # Initialize thread variable if not already
            self.micro_move_thread_obj = threading.Thread(target=self.micro_move_thread, args=(0.5,))
            self.micro_move_thread_obj.start()

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
            if hasattr(self, "micro_move_thread_obj") and self.micro_move_thread_obj and self.micro_move_thread_obj.is_alive():
                self.micro_move_thread_obj.join()  # Wait for the thread to finish

    def micro_move_thread(self, interval):
        def micro_move_run():
            if not isValid(self):
                return
            bar.activate_micro_move()

        while self.micro_move_run_timer and isValid(self):
            time.sleep(interval)
            utils.executeDeferred(micro_move_run)

    def _setup_orbit_toolbar_button(self, button_widget):
        self.orbit_button_widget = button_widget
        ui.bind_orbit_toolbar_button(button_widget)

    def _on_orbit_button_toggled(self, checked):
        if self._orbit_button_sync:
            return
        if checked:
            ui.orbit_window(reuse_existing=True)
        else:
            ui.close_orbit_window()

    def _on_orbit_window_state_changed(self, is_open):
        if not self.orbit_button_widget:
            return
        self._orbit_button_sync = True
        try:
            self.orbit_button_widget.setChecked(is_open)
        finally:
            self._orbit_button_sync = False

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
        print("User preference file: " + settings.get_preferences_file())
        print("")
        print(f"Screen resolution: {width}x{height}")
        print(f"Toolbar size: {toolbar_s}")
        print(f"Toolbar width: {tkm_toolbar_width}")
        print(f"Toolbar sides: {sobrante}")
        print(f"Toolbar push: {margen}")
        print("")
        print("_________________________________________________________")

    def start_selection_sets_UI(self):
        ui.open_selection_sets_toolbar_action(controller=self)

    # Crea el selection sets workspace ----------------------------------------------------------------------------

    def create_selection_sets_workspace(self):
        ui.open_selection_sets_toolbar_action(controller=self)

    def toggle_selection_sets_workspace(self, *args):
        ui.toggle_selection_sets_window(controller=self)

    def set_reload(self):
        import TheKeyMachine.core.toolbar as t  # type: ignore

        reload(t)

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
                    if cmds.getPanel(typeOf=currentPanel) != "modelPanel":
                        currentPanel = cmds.playblast(activeEditor=True)
                    if cmds.getPanel(typeOf=currentPanel) != "modelPanel":
                        return wutil.inViewMessage("Focus on a camera or viewport")

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
                    cmds.warning(f"No objects in bookmark '{bookmark_name}'")
            else:
                cmds.warning(f"Bookmark '{bookmark_name}' not found")
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
        ### ______________________________________________________ TOOLBAR ICON SIZE  ___________________________________________________
        alignments = {"Left": QtCore.Qt.AlignLeft, "Center": QtCore.Qt.AlignHCenter, "Right": QtCore.Qt.AlignRight}

        def get_current_icon_alignment():
            toolbar_alignment_str = settings.get_setting("toolbar_icon_alignment", "Center")
            return alignments.get(toolbar_alignment_str, QtCore.Qt.AlignHCenter)

        def update_toolbar_icon_alignment(alignment, value):
            if alignment and value:
                settings.set_setting("toolbar_icon_alignment", alignment)
                self.toolbar_layout.setAlignment(value)
                self.toolbar_layout.update()

        ### ______________________________________________________ TOOLBAR LAYOUT _____________________________________________________________________###

        if self.layout():
            QtWidgets.QWidget().setLayout(self.layout())

        self.setSizePolicy(QtWidgets.QSizePolicy.Preferred, QtWidgets.QSizePolicy.Minimum)
        self.main_layout = QtWidgets.QHBoxLayout(self)
        self.main_layout.setContentsMargins(0, 0, 0, 0)
        self.main_toolbar_widget = cw.QFlowContainer()
        self.main_layout.addWidget(self.main_toolbar_widget)

        # Use QFlowLayout to allow wrapping
        toolbar_alignment = get_current_icon_alignment()
        self.toolbar_layout = cw.QFlowLayout(self.main_toolbar_widget, margin=2, Wspacing=10, Hspacing=6, alignment=toolbar_alignment)

        def new_section(spacing=0, hiddeable=True):
            sec = cw.QFlatSectionWidget(spacing=spacing, hiddeable=hiddeable)
            self.toolbar_layout.addWidget(sec)
            return sec

        # Placeholder for tooltip functions to be defined later
        show_tooltips = settings.get_setting("show_tooltips", True)

        # _____________________ Key Editing Section __________________________________________________ #
        sec = new_section()

        sec.addWidgetGroup(
            [
                {
                    "key": "move_left",
                    "label": "Nudge Left",
                    "icon_path": media.nudge_left_image,
                    "callback": lambda: keyTools.move_keyframes_in_range(-self.move_keyframes_intField.value()),
                    "description": "Nudge selected keys to the left.",
                    "default": True,
                },
                {
                    "key": "nudge_remove_inbetween",
                    "label": "Remove Inbetween",
                    "icon_path": media.remove_inbetween_image,
                    "callback": lambda: keyTools.remove_inbetween(self.move_keyframes_intField.value()),
                },
            ],
        )

        sec.addWidgetGroup(
            [
                {
                    "key": "move_right",
                    "label": "Nudge Right",
                    "icon_path": media.nudge_right_image,
                    "callback": lambda: keyTools.move_keyframes_in_range(self.move_keyframes_intField.value()),
                    "description": "Nudge selected keys to the right.",
                    "default": True,
                },
                {
                    "key": "nudge_insert_inbetween",
                    "label": "Insert Inbetween",
                    "icon_path": media.insert_inbetween_image,
                    "callback": lambda: keyTools.insert_inbetween(self.move_keyframes_intField.value()),
                },
            ],
        )

        self.move_keyframes_intField = cw.QFlatSpinBox()
        self.move_keyframes_intField.setFixedWidth(50)
        sec.addWidget(self.move_keyframes_intField, "Nudge Value", "nudge_val")

        clear_btn = cw.QFlatToolButton(text="x")
        clear_btn.clicked.connect(keyTools.clear_selected_keys)
        sec.addWidget(
            clear_btn,
            "Clear Selection",
            "clear_sel",
            default_visible=False,
            tooltip_template=helper.clear_selected_keys_widget_tooltip_text,
        )
        select_scene_btn = cw.QFlatToolButton(text="s")
        select_scene_btn.clicked.connect(keyTools.select_all_animation_curves)
        sec.addWidget(
            select_scene_btn,
            "Select Scene Anim",
            "select_scene",
            default_visible=False,
            tooltip_template=helper.select_scene_animation_widget_tooltip_text,
        )

        # _____________________ BlendSlider ____________________________ #

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

        def add_mode_sliders(modes_list, prefix, color, change_func, drop_func, default_modes=None):
            # Create a new section for each slider color/type
            sec = new_section()

            # Static default list for "Pin Defaults" — uses provided list or falls back to first mode
            if default_modes:
                static_default_keys = [f"{prefix}_{k}" for k in default_modes]
            else:
                first_mode = modes_list[0]["key"] if isinstance(modes_list[0], dict) else modes_list[1]["key"]
                static_default_keys = [f"{prefix}_{first_mode}"]

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
                        # Switch to solo mode logic: simply update instance and metadata
                        slider_instance.setCurrentMode(new_mode)
                        m_info = next((item for item in modes_list if isinstance(item, dict) and item["key"] == new_mode), None)
                        if m_info:
                            slider_instance.setTooltipInfo(m_info["label"], m_info.get("description", ""))

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

                # Add to section with registration
                sec.addWidget(s, label, f"{prefix}_{key}", default_visible=is_visible, description=desc)

            # Add the final pin actions (Pin Defaults/All)
            sec.add_final_actions(static_default_keys)

        # Create separate sections for Blend and Tween sliders - Standardized setting names
        add_mode_sliders(
            sliders.BLEND_MODES,
            "blend",
            COLOR.color.green,
            sliders.execute_curve_modifier,
            sliders.stop_dragging,
            default_modes=["connect_neighbors"],
        )
        add_mode_sliders(
            sliders.TWEEN_MODES,
            "tween",
            COLOR.color.yellow,
            sliders.execute_tween,
            sliders.stop_dragging,
            default_modes=["tweener"],
        )

        # ----------------------------------------------- ToolsButtons -------------------------------------------------------- #

        # Pointer  -------------------------------------------------------------------------

        sec = new_section()

        sec.addWidgetGroup(
            [
                {
                    "key": "select_rig_controls",
                    "label": "Select Rig Controls",
                    "icon_path": media.select_rig_controls_image,
                    "callback": bar.select_rig_controls,
                    "tooltip_template": helper.select_rig_controls_tooltip_text,
                    "default": True,
                },
                {
                    "key": "pointer_sel_anim_rig",
                    "label": "Select Animated Rig Controls",
                    "icon_path": media.select_animated_rig_controls_image,
                    "callback": bar.select_animated_rig_controls,
                },
                "separator",
                {"key": "pointer_depth_mover", "label": "Depth Mover", "icon_path": media.depth_mover_image, "callback": bar.depth_mover},
            ],
        )

        # Isolate -------------------------------------------------------------------------

        sec.addWidgetGroup(
            [
                {
                    "key": "isolate",
                    "label": "Isolate",
                    "icon_path": media.isolate_image,
                    "callback": bar.isolate_master,
                    "tooltip_template": helper.isolate_tooltip_text,
                    "default": True,
                },
                {
                    "key": "isolate_bookmarks",
                    "label": "Bookmarks",
                    "icon_path": media.ibookmarks_menu_image,
                    "callback": self.create_ibookmarks_window,
                },
                "separator",
                {
                    "key": "isolate_down_level",
                    "label": "Down one level",
                    "checkable": True,
                    "is_checked_fn": lambda: bar.down_one_level,  # Assuming bar.down_one_level tracks state
                    "callback": bar.toggle_down_one_level,
                    "pinnable": False,
                },
                "separator",
                {
                    "key": "isolate_help",
                    "label": "Help",
                    "icon_path": media.help_menu_image,
                    "callback": lambda: general.open_url("https://thekeymachine.gitbook.io/base/the-toolbar/animation-tools/isolate"),
                    "pinnable": False,
                },
            ],
        )

        self.update_selectionSets_on_new_scene()

        # Create Locators  ----------------------------------------------------------------
        sec.addWidgetGroup(
            [
                {
                    "key": "create_locator",
                    "label": "Create Locator",
                    "icon_path": media.create_locator_image,
                    "callback": bar.createLocator,
                    "tooltip_template": helper.createLocator_tooltip_text,
                    "default": True,
                },
                {
                    "key": "locator_select_temp",
                    "label": "Select temp locators",
                    "icon_path": media.create_locator_image,
                    "callback": bar.selectTempLocators,
                },
                {
                    "key": "locator_remove_temp",
                    "label": "Remove temp locators",
                    "icon_path": media.create_locator_image,
                    "callback": bar.deleteTempLocators,
                },
            ],
        )

        # align / match transforms ----------------------------------------------------------

        sec.addWidgetGroup(
            [
                {
                    "key": "align",
                    "label": "Align",
                    "icon_path": media.match_image,
                    "callback": bar.align_selected_objects,
                    "tooltip_template": helper.align_tooltip_text,
                    "default": True,
                },
                {
                    "key": "align_translation",
                    "label": "Translation",
                    "icon_path": media.align_menu_image,
                    "callback": partial(bar.align_selected_objects, pos=True, rot=False, scl=False),
                },
                {
                    "key": "align_rotation",
                    "label": "Rotation",
                    "icon_path": media.align_menu_image,
                    "callback": partial(bar.align_selected_objects, pos=False, rot=True, scl=False),
                },
                {
                    "key": "align_scale",
                    "label": "Scale",
                    "icon_path": media.align_menu_image,
                    "callback": partial(bar.align_selected_objects, pos=False, rot=False, scl=True),
                },
                "separator",
                {"key": "align_range", "label": "Match Range", "icon_path": media.match_image, "callback": bar.align_range},
                "separator",
                {
                    "key": "align_help",
                    "label": "Help",
                    "icon_path": media.help_menu_image,
                    "callback": lambda: general.open_url("https://thekeymachine.gitbook.io/base/the-toolbar/animation-tools/match-align"),
                    "pinnable": False,
                },
            ],
        )

        # Tracer -----------------------------------------------------------------------------
        sec.addWidgetGroup(
            [
                {
                    "key": "tracer",
                    "label": "Tracer",
                    "icon_path": media.tracer_menu_image,
                    "callback": bar.mod_tracer,
                    "tooltip_template": helper.tracer_tooltip_text,
                    "default": True,
                },
                {
                    "key": "tracer_connected",
                    "label": "Connected",
                    "checkable": True,
                    "is_checked_fn": lambda: getattr(bar, "is_tracer_connected", lambda: False)(),  # Assuming a state check exists
                    "callback": lambda x: bar.tracer_connected(connected=x, update_cb=bar.tracer_update_checkbox),
                    "pinnable": False,
                },
                "separator",
                {
                    "key": "tracer_refresh",
                    "label": "Refresh Tracer",
                    "icon_path": media.tracer_refresh_image,
                    "callback": bar.tracer_refresh,
                },
                {
                    "key": "tracer_show_hide",
                    "label": "Toggle Tracer",
                    "icon_path": media.tracer_show_hide_image,
                    "callback": bar.tracer_show_hide,
                },
                {
                    "key": "tracer_offset_node",
                    "label": "Select offset node",
                    "icon_path": media.tracer_select_offset_image,
                    "callback": bar.select_tracer_offset_node,
                },
                "separator",
                {
                    "key": "tracer_grey",
                    "label": "Tracer Style: Grey",
                    "icon_path": media.tracer_grey_image,
                    "callback": bar.set_tracer_grey_color,
                },
                {
                    "key": "tracer_red",
                    "label": "Tracer Style: Red",
                    "icon_path": media.tracer_red_image,
                    "callback": bar.set_tracer_red_color,
                },
                {
                    "key": "tracer_blue",
                    "label": "Tracer Style: Blue",
                    "icon_path": media.tracer_blue_image,
                    "callback": bar.set_tracer_blue_color,
                },
                "separator",
                {
                    "key": "tracer_remove",
                    "label": "Remove Tracer",
                    "icon_path": media.remove_image,
                    "callback": bar.remove_tracer_node,
                },
            ],
        )

        # Reset anim  -------------------------------------------------------------------------
        sec.addWidgetGroup(
            [
                {
                    "key": "reset_values",
                    "label": "Reset Values",
                    "icon_path": media.reset_animation_image,
                    "callback": keyTools.reset_objects_mods,
                    "tooltip_template": helper.reset_values_tooltip_text,
                    "default": True,
                },
                {
                    "key": "reset_set_defaults",
                    "label": "Set Default Values For Selected",
                    "icon_path": media.reset_animation_image,
                    "callback": keyTools.save_default_values,
                },
                {
                    "key": "reset_restore_defaults",
                    "label": "Restore Default Values For Selected",
                    "icon_path": media.reset_animation_image,
                    "callback": keyTools.remove_default_values_for_selected_object,
                },
                "separator",
                {
                    "key": "reset_clear_all",
                    "label": "Clear All Saved Data",
                    "icon_path": media.reset_animation_image,
                    "callback": keyTools.restore_default_data,
                },
                "separator",
                {
                    "key": "reset_help",
                    "label": "Help",
                    "icon_path": media.help_menu_image,
                    "callback": lambda: general.open_url("https://thekeymachine.gitbook.io/base/the-toolbar/animation-tools/reset-to-default"),
                    "pinnable": False,
                },
            ],
        )

        # Delete anim -------------------------------------------------------------------------
        delete_anim_btn = cw.QFlatToolButton(icon=media.delete_animation_image, tooltip_template=helper.delete_animation_tooltip_text)
        delete_anim_btn.clicked.connect(bar.mod_delete_animation)
        sec.addWidget(delete_anim_btn, "Delete Anim", "delete_anim", tooltip_template=helper.delete_animation_tooltip_text)

        selector_button_widget = cw.QFlatToolButton(tooltip_template=helper.selector_tooltip_text)
        selector_button_widget.setText("0")
        selector_button_widget.clicked.connect(bar.selector_window)
        sec.addWidget(selector_button_widget, "Selector", "selector", tooltip_template=helper.selector_tooltip_text)

        def update_selector_button_text():
            if not wutil.is_valid_widget(selector_button_widget):
                return
            selected_objects = cmds.ls(selection=True)
            num_selected = len(selected_objects)
            selector_button_widget.setText(str(num_selected))

        try:
            self._callback_manager.selection_changed.connect(update_selector_button_text)
        except Exception:
            pass
        update_selector_button_text()

        sec = new_section()

        # Select opposite ---------------------------------------------------------------------
        sec.addWidgetGroup(
            [
                {
                    "key": "select_opposite",
                    "label": "Select Opposite",
                    "icon_path": media.select_opposite_image,
                    "callback": keyTools.selectOpposite,
                    "tooltip_template": helper.select_opposite_tooltip_text,
                    "default": True,
                },
                {
                    "key": "add_opposite",
                    "label": "Add Opposite",
                    "icon_path": media.select_opposite_image,
                    "callback": keyTools.addSelectOpposite,
                    "tooltip_template": helper.add_opposite_tooltip_text,
                },
                {
                    "key": "copy_opposite",
                    "label": "Copy Opposite",
                    "icon_path": media.copy_opposite_image,
                    "callback": keyTools.copyOpposite,
                    "tooltip_template": helper.copy_opposite_tooltip_text,
                    "default": True,
                },
            ]
        )

        # Mirror -----------------------------------------------------------------------
        sec.addWidgetGroup(
            [
                {
                    "key": "mirror",
                    "label": "Mirror",
                    "icon_path": media.mirror_image,
                    "callback": keyTools.mirror,
                    "tooltip_template": helper.mirror_tooltip_text,
                    "default": True,
                },
                {
                    "key": "mirror_add_invert",
                    "label": "Add Exception Invert",
                    "icon_path": media.mirror_image,
                    "callback": keyTools.add_mirror_invert_exception,
                },
                {
                    "key": "mirror_add_keep",
                    "label": "Add Exception Keep",
                    "icon_path": media.mirror_image,
                    "callback": keyTools.add_mirror_keep_exception,
                },
                {
                    "key": "mirror_remove_exc",
                    "label": "Remove Exception",
                    "icon_path": media.mirror_image,
                    "callback": keyTools.remove_mirror_invert_exception,
                },
                "separator",
                {
                    "key": "mirror_help",
                    "label": "Help",
                    "icon_path": media.help_menu_image,
                    "callback": lambda: general.open_url("https://thekeymachine.gitbook.io/base/the-toolbar/animation-tools/mirror"),
                    "pinnable": False,
                },
            ],
        )

        # Copy Paste Pose -----------------------------------------------------------------------
        sec.addWidgetGroup(
            [
                {
                    "key": "copy_pose",
                    "label": "Copy Pose",
                    "icon_path": media.copy_pose_image,
                    "callback": keyTools.copy_pose,
                    "tooltip_template": helper.copy_pose_tooltip_text,
                    "default": True,
                },
                {"key": "cp_paste_pose", "label": "Paste Pose", "icon_path": media.paste_pose_image, "callback": keyTools.paste_pose},
                "separator",
                {
                    "key": "pose_help",
                    "label": "Help",
                    "icon_path": media.help_menu_image,
                    "callback": lambda: general.open_url(
                        "https://thekeymachine.gitbook.io/base/the-toolbar/animation-tools/copy-paste-animation#pose-tools"
                    ),
                    "pinnable": False,
                },
            ],
        )

        # Copy Paste Animation -----------------------------------------------------------------------
        sec.addWidgetGroup(
            [
                {
                    "key": "cp_copy_anim",
                    "label": "Copy Animation",
                    "icon_path": media.copy_animation_image,
                    "callback": keyTools.copy_animation,
                    "tooltip_template": helper.copy_animation_tooltip_text,
                    "default": True,
                },
                {
                    "key": "cp_paste_anim",
                    "label": "Paste Animation",
                    "icon_path": media.paste_animation_image,
                    "callback": keyTools.paste_animation,
                },
                {
                    "key": "cp_paste_ins",
                    "label": "Paste Insert",
                    "icon_path": media.paste_insert_animation_image,
                    "callback": keyTools.paste_insert_animation,
                },
                {
                    "key": "cp_paste_opp",
                    "label": "Paste Opposite",
                    "icon_path": media.paste_opposite_animation_image,
                    "callback": keyTools.paste_opposite_animation,
                },
                {
                    "key": "cp_paste_to",
                    "label": "Paste To",
                    "icon_path": media.paste_animation_image,
                    "callback": keyTools.paste_animation_to,
                },
                "separator",
                {
                    "key": "cp_help",
                    "label": "Help",
                    "icon_path": media.help_menu_image,
                    "callback": lambda: general.open_url("https://thekeymachine.gitbook.io/base/the-toolbar/animation-tools/copy-paste-animation"),
                    "pinnable": False,
                },
            ],
        )

        sec = new_section()

        # Select hierarchy -----------------------------------------------------------------------
        select_hierarchy_button_widget = cw.QFlatToolButton(icon=media.select_hierarchy_image, tooltip_template=helper.select_hierarchy_tooltip_text)
        select_hierarchy_button_widget.clicked.connect(bar.selectHierarchy)
        sec.addWidget(select_hierarchy_button_widget, "Select Hierarchy", "select_hierarchy", tooltip_template=helper.select_hierarchy_tooltip_text)

        # Animation offset -----------------------------------------------------------------------
        animation_offset_button_widget = cw.QFlatToolButton(icon=media.animation_offset_image, tooltip_template=helper.animation_offset_tooltip_text)
        animation_offset_button_widget.setObjectName("anim_offset_button")
        animation_offset_button_widget.clicked.connect(self.toggleAnimOffsetButton)
        sec.addWidget(animation_offset_button_widget, "Anim Offset", "anim_offset", tooltip_template=helper.animation_offset_tooltip_text)

        sec.addWidgetGroup(
            [
                {
                    "key": "follow_cam",
                    "label": "Follow Cam",
                    "icon_path": media.follow_cam_image,
                    "callback": lambda *args: bar.create_follow_cam(translation=True, rotation=True),
                    "tooltip_template": helper.follow_cam_tooltip_text,
                    "default": True,
                },
                {
                    "key": "fcam_trans_only",
                    "label": "Follow only Translation",
                    "icon_path": media.follow_cam_image,
                    "callback": lambda: bar.create_follow_cam(translation=True, rotation=False),
                },
                {
                    "key": "fcam_rot_only",
                    "label": "Follow only Rotation",
                    "icon_path": media.follow_cam_image,
                    "callback": lambda: bar.create_follow_cam(translation=False, rotation=True),
                },
                "separator",
                {"key": "fcam_remove", "label": "Remove followCam", "icon_path": media.remove_image, "callback": bar.remove_followCam},
            ],
        )

        # Copy Link -----------------------------------------------------------------------

        self.link_checkbox_state = settings.get_setting("link_checkbox_state", False)
        self.link_obj_image_timer = False
        self.link_obj_thread = None
        self.link_obj_toggle_state = False

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
            # If toggle_auto_link_callback is called from the menu, it should toggle the state.
            # If called from initialize_on_startup, it should just set it up based on current state.
            if args and isinstance(args[0], bool):
                # menu triggered
                self.link_checkbox_state = args[0]
            else:
                # manual call or no-arg (we don't want to toggle if it's already set)
                pass

            settings.set_setting("link_checkbox_state", self.link_checkbox_state)

            if self.link_checkbox_state:
                add_link_objects_callback()
            else:
                remove_link_objects_callback()

        link_objects_button_widget = cw.QFlatToolButton(icon=media.link_objects_image, tooltip_template=helper.link_objects_tooltip_text)
        link_objects_button_widget.clicked.connect(keyTools.mod_link_objects)

        # Initialize on startup
        if self.link_checkbox_state:
            add_link_objects_callback()

        link_objects_button_widget = sec.addWidgetGroup(
            [
                {
                    "key": "link_objects",
                    "label": "Link Objects",
                    "icon_path": media.link_objects_image,
                    "callback": keyTools.mod_link_objects,
                    "tooltip_template": helper.link_objects_tooltip_text,
                    "default": True,
                },
                {
                    "key": "link_copy",
                    "label": "Copy Link Position",
                    "icon_path": media.link_objects_copy_image,
                    "callback": keyTools.copy_link,
                },
                {
                    "key": "link_paste",
                    "label": "Paste Link Position",
                    "icon_path": media.link_objects_paste_image,
                    "callback": keyTools.paste_link,
                },
                "separator",
                {
                    "key": "link_autolink",
                    "label": "Auto-link",
                    "icon_path": media.link_objects_image,
                    "callback": toggle_auto_link_callback,
                    "checkable": True,
                    "is_checked_fn": lambda: self.link_checkbox_state,
                    "pinnable": False,
                },
                "separator",
                {
                    "key": "link_help",
                    "label": "Help",
                    "icon_path": media.help_menu_image,
                    "callback": lambda: general.open_url("https://thekeymachine.gitbook.io/base/the-toolbar/animation-tools/link-objects"),
                    "pinnable": False,
                },
            ],
        )

        # Copy World Space ----------------------------------------------------------------------------
        sec.addWidgetGroup(
            [
                # toolbox.get_tool("worldspace", default=True),
                toolbox.get_tool(
                    "ws_copy_frame",
                    label="Copy World Space",
                    icon_path=media.worldspace_copy_frame_image,
                    callback=bar.copy_worldspace_single_frame,
                    tooltip_template=helper.copy_worldspace_tooltip_text,
                    default=True,
                ),
                toolbox.get_tool(
                    "ws_copy_range",
                    label="Copy World Space - Selected Range",
                    icon_path=media.worldspace_copy_animation_image,
                    callback=bar.copy_range_worldspace_animation,
                    tooltip_template=helper.copy_worldspace_range_tooltip_text,
                ),
                "separator",
                toolbox.get_tool(
                    "ws_paste_frame",
                    label="Paste World Space",
                    icon_path=media.worldspace_paste_frame_image,
                    callback=bar.paste_worldspace_single_frame,
                    tooltip_template=helper.paste_worldspace_tooltip_text,
                ),
                toolbox.get_tool(
                    "ws_paste",
                    label="Paste World Space - All Animation",
                    icon_path=media.worldspace_paste_animation_image,
                    callback=bar.color_worldspace_paste_animation,
                    tooltip_template=helper.paste_worldspace_animation_tooltip_text,
                ),
                "separator",
                {
                    "key": "ws_help",
                    "label": "Help",
                    "description": "World Space tools.",
                    "icon_path": media.help_menu_image,
                    "callback": lambda: general.open_url(
                        "https://thekeymachine.gitbook.io/base/the-toolbar/animation-tools/copy-paste-animation#worldspace-tools"
                    ),
                    "pinnable": False,
                },
            ],
        )

        # Temp Pivot ----------------------------------------------------------------------------
        sec.addWidgetGroup(
            [
                toolbox.get_tool("temp_pivot", default=True),
                toolbox.get_tool(
                    "tp_last_used", label="Last pivot used", icon_path=media.temp_pivot_image, callback=lambda: bar.create_temp_pivot(True)
                ),
                "separator",
                {
                    "key": "tp_help",
                    "label": "Help",
                    "icon_path": media.help_menu_image,
                    "callback": lambda: general.open_url("https://thekeymachine.gitbook.io/base/the-toolbar/animation-tools/temp-pivots"),
                    "pinnable": False,
                },
            ],
        )

        # Micro Move ----------------------------------------------------------------------------
        micro_move_button_widget = cw.QFlatToolButton(icon=media.ruler_image, tooltip_template=helper.micro_move_tooltip_text)
        micro_move_button_widget.setObjectName("micro_move_button")
        micro_move_button_widget.setCheckable(True)
        micro_move_button_widget.setChecked(self.micro_move_button_state)
        micro_move_button_widget.clicked.connect(self.toggle_micro_move_button)
        sec.addWidget(micro_move_button_widget, "Micro Move", "micro_move", tooltip_template=helper.micro_move_tooltip_text)

        # Key Menu -------------------------------------------------------------------------------
        sec.addWidgetGroup(
            [
                toolbox.get_tool("bake_animation_1", key="bk_bake_anim_1", default=True),
                toolbox.get_tool("bake_animation_2", key="bk_bake_anim_2"),
                toolbox.get_tool("bake_animation_3", key="bk_bake_anim_3"),
                toolbox.get_tool("bake_animation_custom", key="bk_bake_anim_custom"),
            ],
        )
        sec.addWidgetGroup(
            [
                toolbox.get_tool("share_keys", default=True),
                toolbox.get_tool("reblock", key="bk_reblock"),
                toolbox.get_tool("gimbal", key="bk_gimbal"),
            ],
        )

        sec = new_section()

        # Selection Sets  ----------------------------------------------------------------------------
        selection_sets_button_widget = sec.addWidgetGroup(
            [
                toolbox.get_tool("selection_sets", callback=None, default=True),
                {
                    "key": "orbit_auto_transparency",
                    "label": "Auto Transparency",
                    "description": "Make floating windows translucent when not hovered.",
                    "checkable": True,
                    "is_checked_fn": lambda: settings.get_setting(
                        "orbit_auto_transparency",
                        True,
                        namespace=ui.ORBIT_SETTINGS_NAMESPACE,
                    ),
                    "callback": lambda state: settings.set_setting(
                        "orbit_auto_transparency",
                        state,
                        namespace=ui.ORBIT_SETTINGS_NAMESPACE,
                    ),
                    "pinnable": False,
                },
            ]
        )
        if selection_sets_button_widget:
            selection_sets_button_widget.setObjectName("toggle_selection_sets_workspace_b")
            ui.bind_selection_sets_toolbar_button(selection_sets_button_widget, controller=self)

        # customGraph ----------------------------------------------------------------------------
        def open_customGraph():
            import TheKeyMachine.core.customGraph as cg  # type: ignore

            cg.createCustomGraph(force=True)

        sec.addWidgetGroup([toolbox.get_tool("custom_graph", callback=open_customGraph, default=True)])

        # custom tools ----------------------------------------------------------------------------
        sec = new_section()
        orbit_button_widget = sec.addWidgetGroup(
            [
                toolbox.get_tool("orbit", callback=None, default=True),
                {
                    "key": "orbit_auto_transparency",
                    "label": "Auto Transparency",
                    "description": "Make the Orbit window translucent when not hovered.",
                    "checkable": True,
                    "is_checked_fn": lambda: settings.get_setting(
                        "orbit_auto_transparency",
                        True,
                        namespace=ui.ORBIT_SETTINGS_NAMESPACE,
                    ),
                    "callback": lambda state: settings.set_setting(
                        "orbit_auto_transparency",
                        state,
                        namespace=ui.ORBIT_SETTINGS_NAMESPACE,
                    ),
                    "pinnable": False,
                },
            ]
        )
        if orbit_button_widget:
            self._setup_orbit_toolbar_button(orbit_button_widget)

        invalidate_caches()
        import TheKeyMachine_user_data.connect.tools.tools as connectToolBox  # type: ignore

        def initialize_tool_menu():
            reload(connectToolBox)
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

        toolBox_button_widget = cw.QFlatToolButton(icon=media.custom_tools_image)
        toolBox_button_widget.setVisible(bool(CUSTOM_TOOLS_MENU))
        sec.addWidget(toolBox_button_widget, "Custom Tools", "custom_tools", tooltip_template=helper.custom_tools_tooltip_text)
        toolBox_menu = QtWidgets.QMenu(toolBox_button_widget)
        toolBox_button_widget.setContextMenuPolicy(QtCore.Qt.CustomContextMenu)
        toolBox_button_widget.customContextMenuRequested.connect(lambda pos: toolBox_menu.exec_(toolBox_button_widget.mapToGlobal(pos)))
        toolBox_button_widget.clicked.connect(lambda: toolBox_menu.exec_(QtGui.QCursor.pos()))

        initialize_tool_menu()

        # custom scripts ----------------------------------------------------------------------------
        import TheKeyMachine_user_data.connect.scripts.scripts as cbScripts  # type: ignore

        def initialize_scripts_menu():
            reload(cbScripts)
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

        customScripts_button_widget = cw.QFlatToolButton(icon=media.custom_scripts_image, tooltip_template=helper.custom_scripts_tooltip_text)
        customScripts_button_widget.setVisible(bool(CUSTOM_SCRIPTS_MENU))
        sec.addWidget(customScripts_button_widget, "Custom Scripts", "custom_scripts", tooltip_template=helper.custom_scripts_tooltip_text)

        customScripts_menu = QtWidgets.QMenu(customScripts_button_widget)
        customScripts_button_widget.setContextMenuPolicy(QtCore.Qt.CustomContextMenu)
        customScripts_button_widget.customContextMenuRequested.connect(
            lambda pos: customScripts_menu.exec_(customScripts_button_widget.mapToGlobal(pos))
        )
        customScripts_button_widget.clicked.connect(lambda: customScripts_menu.exec_(QtGui.QCursor.pos()))

        initialize_scripts_menu()

        # _____________________ Workspaces Section ____________________________ #
        sec = new_section(hiddeable=False)

        overshootSliders = settings.get_setting("sliders_overshoot", False)

        def _setOvershoot(state):
            settings.set_setting("sliders_overshoot", state)
            sw.globalSignals.overshootChanged.emit(state)

        toolbar_config_button_widget = cw.QFlatToolButton(icon=media.settings_image)
        toolbar_config_button_widget.setObjectName("settings_toolbar_button")
        sec.addWidget(
            toolbar_config_button_widget,
            "Settings",
            "settings",
            description="Access global preferences, check for updates, and view credits.",
        )

        # Build your menu with your cw.MenuWidget; make sure the button is the PARENT
        toolbar_menu = cw.MenuWidget(parent=toolbar_config_button_widget)
        toolbar_menu.addAction(cw.LogoAction(toolbar_menu))

        # === Help submenu ===
        help_menu = cw.MenuWidget(QtGui.QIcon(media.help_menu_image), "Help")
        toolbar_menu.addMenu(help_menu, description="Resources for help, documentation and community.")
        help_menu.addAction(
            QtGui.QIcon(media.report_a_bug_image),
            "Report a bug",
            ui.bug_report_window,
            description="Report any bug you may have encountered whilst using the software.",
        )
        help_menu.addSeparator()
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

        # === Settings submenu ===
        settings_menu = cw.MenuWidget(QtGui.QIcon(media.settings_image), "Settings")
        toolbar_menu.addMenu(settings_menu, description="Tool configuration, hotkeys and UI preferences.")
        settings_menu.addSection("Shelf icon")
        settings_menu.addAction(
            QtGui.QIcon(media.tool_icon),
            "Add Toggle Button To Shelf",
            self.create_shelf_icon,
            description="Creates a shelf button to show/hide this toolbar.",
        )

        run_on_startup_action = settings_menu.addAction(
            "Run on Startup", ui.install_userSetup, description="Make TKM run automatically when Maya starts."
        )
        run_on_startup_action.setCheckable(True)
        run_on_startup_action.setChecked(ui.check_userSetup())

        settings_menu.addSection("Tools settings")
        show_tooltips_action = settings_menu.addAction("Show tooltips", description="Show or hide floating tooltips.")
        show_tooltips_action.setCheckable(True)

        def update_show_tooltips(value):
            settings.set_setting("show_tooltips", value)
            QFlatTooltipManager.enabled = value

        show_tooltips_action.setChecked(show_tooltips)
        show_tooltips_action.toggled.connect(update_show_tooltips)

        overshoot_action = settings_menu.addAction("Overshoot Sliders", description="Allow sliders to reach values beyond -100 to 100.")
        overshoot_action.setCheckable(True)
        overshoot_action.setChecked(overshootSliders)
        overshoot_action.toggled.connect(_setOvershoot)

        graph_toolbar_enabled = settings.get_setting("graph_toolbar_enabled", True)
        graph_toolbar_action = settings_menu.addAction(
            QtGui.QIcon(media.customGraph_image),
            "Graph Editor Toolbar",
            description="Show or hide the TKM toolbar inside the Graph Editor.",
        )
        graph_toolbar_action.setCheckable(True)

        def _on_graph_toolbar_toggled(state):
            cg.set_graph_toolbar_enabled(bool(state))

        try:
            graph_toolbar_action.blockSignals(True)
            graph_toolbar_action.setChecked(graph_toolbar_enabled)
        finally:
            graph_toolbar_action.blockSignals(False)

        graph_toolbar_action.toggled.connect(_on_graph_toolbar_toggled)

        def _sync_graph_toolbar_action(enabled):
            try:
                graph_toolbar_action.blockSignals(True)
            except RuntimeError:
                try:
                    cg.custom_graph_bus.graph_toolbar_enabled_changed.disconnect(_sync_graph_toolbar_action)
                except Exception:
                    pass
                return

            try:
                graph_toolbar_action.setChecked(bool(enabled))
            except RuntimeError:
                try:
                    cg.custom_graph_bus.graph_toolbar_enabled_changed.disconnect(_sync_graph_toolbar_action)
                except Exception:
                    pass
                return
            finally:
                try:
                    graph_toolbar_action.blockSignals(False)
                except RuntimeError:
                    try:
                        cg.custom_graph_bus.graph_toolbar_enabled_changed.disconnect(_sync_graph_toolbar_action)
                    except Exception:
                        pass

        try:
            cg.custom_graph_bus.graph_toolbar_enabled_changed.connect(_sync_graph_toolbar_action)
        except Exception:
            pass

        def _disconnect_graph_toolbar_action(*_args):
            try:
                cg.custom_graph_bus.graph_toolbar_enabled_changed.disconnect(_sync_graph_toolbar_action)
            except Exception:
                pass

        try:
            graph_toolbar_action.destroyed.connect(_disconnect_graph_toolbar_action)
        except Exception:
            pass

        settings_menu.addSection("Toolbar's icons alignment")
        align_group = QActionGroup(settings_menu)
        for align_name, align_value in alignments.items():
            action = settings_menu.addAction(align_name, description=f"Align icons to the {align_name.lower()}.")
            action.setCheckable(True)
            align_group.addAction(action)
            if align_value == toolbar_alignment:
                action.setChecked(True)
            action.triggered.connect(lambda align_name=align_name, align_value=align_value: update_toolbar_icon_alignment(align_name, align_value))

        settings_menu.addSection("Hotkeys")
        settings_menu.addAction("Add TheKeyMachine Hotkeys", hotkeys.create_TheKeyMachine_hotkeys, description="Setup Maya hotkeys for TKM tools.")

        settings_menu.addSection("General")
        settings_menu.addAction(QtGui.QIcon(media.reload_image), "Reload", self.reload, description="Refresh the TKM interface.")
        settings_menu.addAction(QtGui.QIcon(media.close_image), "Unload", self.unload, description="Close TheKeyMachine and remove callbacks.")
        settings_menu.addAction(QtGui.QIcon(media.remove_image), "Uninstall", ui.uninstall, description="Remove TheKeyMachine from Maya.")

        toolbar_menu.addMenu(self._create_dock_menu(), description="Dock the toolbar to different Maya UI panels.")

        # Separators and others
        toolbar_menu.addSeparator()
        if INTERNET_CONNECTION:
            toolbar_menu.addAction(
                QtGui.QIcon(media.check_updates_image),
                "Check for updates",
                lambda: updater.check_for_updates(toolbar_config_button_widget, force=True),
                description="Check if there is a new version available.",
            )
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

        if INTERNET_CONNECTION:
            # Launch background update check
            updater.check_for_updates(toolbar_config_button_widget, warning=False, force=False)


_toolbar_instance = None


def get_toolbar():
    global _toolbar_instance
    return _toolbar_instance


def show():
    global _toolbar_instance

    try:
        callbacks.shutdown_callback_manager()
    except Exception:
        pass

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
