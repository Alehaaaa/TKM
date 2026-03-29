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
import TheKeyMachine.mods.reportMod as report  # type: ignore
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
import TheKeyMachine.core.runtime_manager as runtime  # type: ignore
import TheKeyMachine.tools.animation_offset.api as animationOffsetApi  # type: ignore
import TheKeyMachine.tools.graph_toolbar.api as graphToolbarApi  # type: ignore
import TheKeyMachine.tools.micro_move.api as microMoveApi  # type: ignore
import TheKeyMachine.tools.ibookmarks.api as iBookmarksApi  # type: ignore
from TheKeyMachine.tools import colors as toolColors  # type: ignore

from TheKeyMachine.widgets import sliderWidget as sw  # type: ignore
from TheKeyMachine.widgets import customWidgets as cw  # type: ignore
from TheKeyMachine.widgets import customDialogs as customDialogs  # type: ignore
from TheKeyMachine.widgets import util as wutil  # type: ignore
import TheKeyMachine.sliders as sliders  # type: ignore

import TheKeyMachine_user_data.connect.tools.tools as connectToolBox  # type: ignore
import TheKeyMachine_user_data.connect.scripts.scripts as cbScripts  # type: ignore


from TheKeyMachine.tooltips import QFlatTooltipManager


class LinkObjectImageThread(QtCore.QThread):
    tick = QtCore.Signal()

    def __init__(self, interval_seconds=0.3, parent=None):
        super().__init__(parent)
        self._interval_ms = max(1, int(float(interval_seconds) * 1000))
        self._running = False

    def run(self):
        self._running = True
        while self._running:
            self.msleep(self._interval_ms)
            if not self._running:
                break
            self.tick.emit()

    def stop(self):
        self._running = False

mods = [
    general,
    ui,
    report,
    keyTools,
    helper,
    media,
    bar,
    hotkeys,
    settings,
    cg,
    updater,
    style,
    sw,
    cw,
    customDialogs,
    wutil,
    sliders,
    toolbox,
    animationOffsetApi,
    graphToolbarApi,
    microMoveApi,
    iBookmarksApi,
    connectToolBox,
    cbScripts,
]

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


UI_COLORS = toolColors.UI_COLORS


class toolbar(MayaQWidgetDockableMixin, QtWidgets.QDialog):
    def __init__(self, parent=None):
        super().__init__(parent=parent)
        self.setWindowTitle("TheKeyMachine")
        self.setObjectName(WorkspaceName)
        self.setContextMenuPolicy(QtCore.Qt.PreventContextMenu)

        self._runtime_manager = runtime.get_runtime_manager()
        report.install_bug_exception_handler()
        graphToolbarApi.sync_graph_toolbar_watch()
        self._runtime_manager.scene_opened.connect(self._on_scene_opened)
        self._runtime_manager.scene_new.connect(self._on_scene_opened)
        self._runtime_manager.graph_editor_opened.connect(self._on_graph_editor_opened)

        self.shelf_painter = None
        self.current_layout = cmds.workspaceLayoutManager(q=True, current=True)

        # Initial state variables from settingsMod
        self.toggleAnimOffsetButtonState = False
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

        self.animation_offset_controller = animationOffsetApi.AnimationOffsetController(self)
        self.micro_move_controller = microMoveApi.MicroMoveController(self)
        self.animation_offset_button_widget = None
        self.setgroup_states = {}
        self.setgroup_buttons = {}

        # Link object runtime states
        self.link_obj_image_timer = False
        self.link_obj_toggle_state = False
        self.link_obj_thread = None

        self.buildUI()

        # Reconcile Graph Editor state at startup; ongoing tracking uses the event filter.
        QTimer.singleShot(0, self._sync_graph_editor_on_startup)

    def closeEvent(self, event):
        """
        Handles the close event for the toolbar window.
        Stops all background threads and performs necessary cleanup.
        """
        global _toolbar_instance
        _toolbar_instance = None

        try:
            runtime.shutdown_runtime_manager()
        except Exception:
            pass

        was_anim_offset_active = self.toggleAnimOffsetButtonState
        self.animation_offset_controller.deactivate()
        if was_anim_offset_active:
            try:
                cmds.undoInfo(closeChunk=True)
            except Exception:
                pass

        self.micro_move_controller.deactivate()

        # Stop link objects image toggle thread
        self.link_obj_image_timer = False
        if hasattr(self, "link_obj_thread") and self.link_obj_thread:
            try:
                self.link_obj_thread.stop()
                self.link_obj_thread.wait(500)
            except Exception:
                pass
            self.link_obj_thread = None

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
        self.update_selectionSets()
        self.update_iBookmarks_menu()

    def _on_graph_editor_opened(self, *_args):
        if not isValid(self):
            return
        if not settings.get_setting("graph_toolbar_enabled", True):
            return
        QTimer.singleShot(0, cg.createCustomGraph)

    def _sync_graph_editor_on_startup(self):
        if not isValid(self):
            return
        if not settings.get_setting("graph_toolbar_enabled", True):
            return

        graph_vis = cmds.getPanel(vis=True) or []
        if "graphEditor1" in graph_vis:
            QTimer.singleShot(0, cg.createCustomGraph)

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

    def create_shelf_icon(self, *args):
        button_name = "TheKeyMachine"
        command = "import TheKeyMachine;TheKeyMachine.toggle()"
        icon_path = media.tool_icon
        icon_path = os.path.normpath(icon_path)
        current_shelf_tab = cmds.tabLayout("ShelfLayout", query=True, selectTab=True)
        cmds.shelfButton(parent=current_shelf_tab, image=icon_path, command=command, label=button_name)

    # Update the iBookmarks menu when scene changes
    def update_iBookmarks_menu(self, *args):
        if not isValid(self):
            return
        iBookmarksApi.update_isolate_popup_menu()

    def update_selectionSets(self):
        if not isValid(self):
            return

        # First verification to check if the SelectionSets workspace exists.
        # If it doesn't exist and trying to assign `vis_state` results in an error.
        if cmds.workspaceControl(selection_sets_workspace, query=True, exists=True):
            vis_state = cmds.workspaceControl(selection_sets_workspace, query=True, visible=True)
            if vis_state:
                if cmds.objExists("TheKeyMachine_SelectionSet"):
                    self.create_buttons_for_sel_sets()
                else:
                    self.selection_sets_empty_setup()

    # For use with toggle functionality on Shelf or Launcher
    def toggle(self, *args):
        self.showWindow()

    def reload(self, *args):
        toolbar_module_name = "TheKeyMachine.core.toolbar"
        customGraph_module_name = "TheKeyMachine.core.customGraph"

        try:
            runtime.shutdown_runtime_manager()
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
            runtime.shutdown_runtime_manager()
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

    def export_sets(self, file_path=None, *args):
        if not file_path:
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

        export_dir = os.path.dirname(file_path)
        if export_dir:
            os.makedirs(export_dir, exist_ok=True)

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

    def import_sets(self, file_path=None, *args):
        if not file_path:
            file_path, _ = QtWidgets.QFileDialog.getOpenFileName(None, "Import Sets", "", "JSON Files (*.json);;All Files (*)")

        if not file_path:
            return

        if not os.path.isfile(file_path):
            wutil.make_inViewMessage("Selection sets file not found")
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
        selection_sets = []
        for node in cmds.sets(sel_set_name, q=True) or []:
            if not cmds.objExists(node):
                continue
            if str(node).endswith("_setgroup"):
                continue
            selection_sets.append(node)
        return selection_sets

    def _normalize_scene_members(self, items):
        if not items:
            return set()
        normalized = cmds.ls(items, long=True) or []
        return set(normalized or items)

    def _find_matching_selection_set(self, selection):
        target_members = self._normalize_scene_members(selection)
        if not target_members:
            return None

        for subset in self.get_selection_sets():
            if not cmds.objExists(subset):
                continue
            subset_members = self._normalize_scene_members(cmds.sets(subset, q=True) or [])
            if subset_members == target_members:
                return subset
        return None

    def get_selection_set_display_name(self, set_name):
        if not set_name:
            return ""
        split_name = str(set_name).split("_")
        if len(split_name) >= 2:
            return "_".join(split_name[:-1])
        return str(set_name)

    def find_matching_selection_set(self, selection=None):
        if selection is None:
            selection = wutil.get_selected_objects()
        return self._find_matching_selection_set(selection)

    def show_matching_selection_set_message(self, set_name):
        if set_name:
            display_name = self.get_selection_set_display_name(set_name)
            wutil.make_inViewMessage(f"Selection already matches set: {display_name or set_name}")

    def _ensure_selection_sets_root(self):
        sel_set_name = "TheKeyMachine_SelectionSet"

        if not cmds.objExists(sel_set_name):
            cmds.sets(name=sel_set_name, empty=True)

        return sel_set_name

    def create_new_set_and_update_buttons(self, color_suffix, set_name_field, set_group_combo=None, *args):
        selection = wutil.get_selected_objects()
        if not selection:
            wutil.make_inViewMessage("Select something first")
            return False

        matching_set = self._find_matching_selection_set(selection)
        if matching_set:
            self.show_matching_selection_set_message(matching_set)
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

            if wutil.get_selected_objects():
                cmds.sets(wutil.get_selected_objects(), add=new_set)

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
        mods = runtime.get_modifier_mask()
        shift_pressed = bool(mods & 1)
        ctrl_pressed = bool(mods & 4)

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
        selection = wutil.get_selected_objects()
        if not selection:
            return wutil.make_inViewMessage("No selection to add")
        elif not cmds.objExists(set_name):
            return cmds.warning(f"Set {set_name} does not exist")

        cmds.sets(selection, add=set_name)

    def remove_selection_from_set(self, set_name, *args):
        selection = wutil.get_selected_objects()
        if not selection:
            return wutil.make_inViewMessage("No selection to remove")
        elif not cmds.objExists(set_name):
            return cmds.warning(f"Set {set_name} does not exist")

        cmds.sets(selection, remove=set_name)

    def update_selection_to_set(self, set_name, *args):
        selection = wutil.get_selected_objects()
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

    color_names = dict(ui.selectionSetsApi.selection_set_color_names)

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
        removed_any = False
        sel_set_name = "TheKeyMachine_SelectionSet"

        for subset in list(self.get_selection_sets()):
            if not cmds.objExists(subset):
                continue
            try:
                if cmds.objExists(sel_set_name):
                    cmds.sets(subset, remove=sel_set_name)
            except Exception:
                pass
            try:
                cmds.delete(subset)
                removed_any = True
            except Exception:
                pass

        if cmds.objExists(sel_set_name):
            try:
                members = cmds.sets(sel_set_name, q=True) or []
            except Exception:
                members = []
            if not members:
                try:
                    cmds.delete(sel_set_name)
                except Exception:
                    pass

        if removed_any:
            ui.refresh_selection_sets_window()
            wutil.make_inViewMessage("All selection sets cleared")

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

    def toggleAnimOffsetButton(self, checked=None):
        button_widget = self.sender() if hasattr(self, "sender") else None
        report.safe_execute(
            self.animation_offset_controller.toggle,
            checked,
            button_widget=button_widget or self.animation_offset_button_widget,
            context="animation offset toggle",
        )
        self.toggleAnimOffsetButtonState = self.animation_offset_controller.is_enabled()
        target_button = button_widget or self.animation_offset_button_widget
        if target_button:
            blocked = target_button.blockSignals(True)
            try:
                target_button.setChecked(bool(self.toggleAnimOffsetButtonState))
            finally:
                target_button.blockSignals(blocked)

    # ---------------------------------------------------------------

    def toggle_micro_move_button(self, checked=None):
        button_widget = self.sender() if hasattr(self, "sender") else None
        report.safe_execute(
            self.micro_move_controller.toggle,
            checked,
            button_widget=button_widget,
            context="micro move toggle",
        )
        current_state = self.micro_move_controller.is_enabled()
        if button_widget:
            blocked = button_widget.blockSignals(True)
            try:
                button_widget.setChecked(bool(current_state))
            finally:
                button_widget.blockSignals(blocked)

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

        def new_section(spacing=0, hiddeable=True, color=None):
            sec = cw.QFlatSectionWidget(spacing=spacing, hiddeable=hiddeable, color=color)
            self.toolbar_layout.addWidget(sec)
            return sec

        # Placeholder for tooltip functions to be defined later
        show_tooltips = settings.get_setting("show_tooltips", True)

        # _____________________ Key Editing Section __________________________________________________ #
        sec = new_section(color=toolColors.green)

        sec.addWidgetGroup(
            [
                toolbox.get_tool(
                    "move_left",
                    callback=lambda: keyTools.move_keyframes_in_range(-self.move_keyframes_intField.value()),
                    shortcut_variants=[
                        {
                            "mask": 1,
                            "text": "-IB",
                            "icon_path": media.remove_inbetween_image,
                            "tooltip_template": "Remove Inbetween",
                            "description": "Remove inbetweens using the current nudge step value.",
                            "callback": lambda: keyTools.remove_inbetween(self.move_keyframes_intField.value()),
                        }
                    ],
                    default=True,
                ),
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
                toolbox.get_tool(
                    "move_right",
                    callback=lambda: keyTools.move_keyframes_in_range(self.move_keyframes_intField.value()),
                    shortcut_variants=[
                        {
                            "mask": 1,
                            "text": "+IB",
                            "icon_path": media.insert_inbetween_image,
                            "tooltip_template": "Insert Inbetween",
                            "description": "Insert inbetweens using the current nudge step value.",
                            "callback": lambda: keyTools.insert_inbetween(self.move_keyframes_intField.value()),
                        }
                    ],
                    default=True,
                ),
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
        sec.addWidgetGroup(
            [
                toolbox.get_tool("share_keys", default=True),
                toolbox.get_tool("reblock", key="bk_reblock"),
                # toolbox.get_tool("gimbal", key="bk_gimbal"),
            ],
        )

        clear_btn = cw.QFlatToolButton(text="x")
        clear_btn.clicked.connect(lambda *_args, w=clear_btn: w.triggerToolCallback(keyTools.clear_selected_keys))
        sec.addWidget(
            clear_btn,
            "Clear Selection",
            "clear_sel",
            default_visible=False,
            tooltip_template=helper.clear_selected_keys_widget_tooltip_text,
        )
        select_scene_btn = cw.QFlatToolButton(text="s")
        select_scene_btn.clicked.connect(lambda *_args, w=select_scene_btn: w.triggerToolCallback(keyTools.select_all_animation_curves))
        sec.addWidget(
            select_scene_btn,
            "Select Scene Anim",
            "select_scene",
            default_visible=False,
            tooltip_template=helper.select_scene_animation_widget_tooltip_text,
        )


        # Key Menu -------------------------------------------------------------------------------
        sec.addWidgetGroup(
            [
                toolbox.get_tool("bake_animation_1", key="bk_bake_anim_1", default=True),
                toolbox.get_tool("bake_animation_2", key="bk_bake_anim_2"),
                toolbox.get_tool("bake_animation_3", key="bk_bake_anim_3"),
                toolbox.get_tool("bake_animation_4", key="bk_bake_anim_4"),
                toolbox.get_tool("bake_animation_custom", key="bk_bake_anim_custom"),
            ],
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
            selected_objects = wutil.get_selected_objects(long=True)
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
                        report.report_detected_exception(e, context="blend to default")

            # update_blend_label_with_slider_value(value)

        def update_button_with_current_frame(button_name):
            # Obtener el número del frame actual
            current_frame = cmds.currentTime(query=True)
            # Actualizar el texto del botón con el número del frame
            cmds.button(button_name, edit=True, label=str(int(current_frame)))

        # _____________________ Sliders Sections ____________________________ #
        # Temporary disable: frame capture buttons for Blend to Frame sliders.
        # blend_to_key_left_b_qt = cw.QFlatToolButton()
        # blend_to_key_left_b_qt.setText("1")
        # blend_to_key_left_b_qt.setFixedSize(25, 16)
        # blend_to_key_left_b_qt.hide()
        # blend_to_key_left_b_qt.clicked.connect(lambda: blend_to_key_left_b_qt.setText(str(int(cmds.currentTime(q=True)))))

        # blend_to_key_right_b_qt = cw.QFlatToolButton()
        # blend_to_key_right_b_qt.setText("1")
        # blend_to_key_right_b_qt.setFixedSize(25, 16)
        # blend_to_key_right_b_qt.hide()
        # blend_to_key_right_b_qt.clicked.connect(lambda: blend_to_key_right_b_qt.setText(str(int(cmds.currentTime(q=True)))))

        def blend_to_frame_with_button_values(percentage):
            # Temporary disable: frame buttons are commented out, so defer to tool defaults.
            left_frame = None
            right_frame = None
            keyTools.blend_to_frame(percentage, left_frame, right_frame)

        def add_mode_sliders(modes_list, prefix, color, change_func, drop_func, default_modes=None):
            # Create a new section for each slider color/type
            sec = new_section()
            sec.set_settings_namespace("main_toolbar_sliders")

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
                is_visible = settings.get_setting(f"pin_{prefix}_{key}", f"{prefix}_{key}" in static_default_keys, namespace="main_toolbar_sliders")

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
                    def setter(new_mode, temporary=False):
                        # Switch to solo mode logic: simply update instance and metadata
                        slider_instance.setCurrentMode(new_mode, temporary=temporary)
                        m_info = next((item for item in modes_list if isinstance(item, dict) and item["key"] == new_mode), None)
                        if m_info:
                            slider_instance.setTooltipInfo(m_info["label"], m_info.get("description", ""))

                        # Handle specialized frames visibility
                        if new_mode == "blend_to_frame":
                            # Temporary disable: frame capture buttons for Blend to Frame sliders.
                            # blend_to_key_left_b_qt.show()
                            # blend_to_key_right_b_qt.show()
                            slider_instance.setDragCommand(blend_to_frame_with_button_values)
                        else:
                            # Temporary disable: frame capture buttons for Blend to Frame sliders.
                            # blend_to_key_left_b_qt.hide()
                            # blend_to_key_right_b_qt.hide()
                            slider_instance.setDragCommand(lambda v, nk=new_mode: change_func(nk, v))

                        if not temporary:
                            slider_instance.startFlash()

                    return setter

                s.modeRequested.connect(make_mode_setter(s, prefix, show_frames))

                # Add to section with registration
                sec.addWidget(s, label, f"{prefix}_{key}", default_visible=is_visible, description=desc)

            # Add the final pin actions (Pin Defaults/All)
            sec.add_final_actions(static_default_keys)

        # Create separate sections for Blend and Tween sliders - Standardized setting names
        add_mode_sliders(
            sliders.BLEND_MODES,
            "blend",
            UI_COLORS.green.hex,
            sliders.execute_curve_modifier,
            sliders.stop_dragging,
            default_modes=["connect_neighbors"],
        )
        add_mode_sliders(
            sliders.TWEEN_MODES,
            "tween",
            UI_COLORS.yellow.hex,
            sliders.execute_tween,
            sliders.stop_dragging,
            default_modes=["tweener"],
        )

        # ----------------------------------------------- ToolsButtons -------------------------------------------------------- #

        # Pointer  -------------------------------------------------------------------------

        sec = new_section(color=toolColors.red)

        sec.addWidgetGroup(
            [
                toolbox.get_tool("select_rig_controls", default=True),
                {
                    "key": "pointer_sel_anim_rig",
                    "label": "Select Animated Rig Controls",
                    "icon_path": media.select_rig_controls_animated_image,
                    "callback": bar.select_rig_controls_animated,
                },
                "separator",
                {"key": "pointer_depth_mover", "label": "Depth Mover", "icon_path": media.depth_mover_image, "callback": bar.depth_mover},
            ],
        )

        # Isolate -------------------------------------------------------------------------

        sec.addWidgetGroup(
            [
                {
                    **toolbox.get_tool("isolate_master"),
                    "key": "isolate",
                    "default": True,
                },
                {
                    "key": "isolate_bookmarks",
                    "label": "Bookmarks",
                    "icon_path": media.ibookmarks_menu_image,
                    "callback": iBookmarksApi.create_ibookmarks_window,
                },
                "separator",
                {
                    "key": "isolate_down_level",
                    "label": "Down one level",
                    "checkable": True,
                    "set_checked_fn": lambda: bar.down_one_level,  # Assuming bar.down_one_level tracks state
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

        self.update_selectionSets()

        # Create Locators  ----------------------------------------------------------------
        sec.addWidgetGroup(
            [
                {
                    **toolbox.get_tool("create_locator"),
                    "key": "create_locator",
                    "default": True,
                },
                toolbox.get_tool("locator_select_temp"),
                toolbox.get_tool("locator_remove_temp"),
            ],
        )

        # align / match transforms ----------------------------------------------------------

        sec.addWidgetGroup(
            [
                toolbox.get_tool("align_selected_objects", key="align", default=True),
                toolbox.get_tool("align_translation"),
                toolbox.get_tool("align_rotation"),
                toolbox.get_tool("align_scale"),
                "separator",
                toolbox.get_tool("align_range"),
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
                toolbox.get_tool("mod_tracer", key="tracer", callback=bar.create_tracer, default=True),
                {
                    "key": "tracer_connected",
                    "label": "Connected",
                    "checkable": True,
                    "set_checked_fn": lambda: getattr(bar, "is_tracer_connected", lambda: False)(),  # Assuming a state check exists
                    "callback": lambda x: bar.tracer_connected(connected=x, update_cb=bar.tracer_update_checkbox),
                    "pinnable": False,
                },
                "separator",
                toolbox.get_tool("tracer_refresh"),
                toolbox.get_tool("tracer_show_hide"),
                toolbox.get_tool("tracer_offset_node"),
                "separator",
                toolbox.get_tool("tracer_grey"),
                toolbox.get_tool("tracer_red"),
                toolbox.get_tool("tracer_blue"),
                "separator",
                toolbox.get_tool("tracer_remove"),
            ],
        )

        # Reset anim  -------------------------------------------------------------------------
        sec.addWidgetGroup(
            [
                toolbox.get_tool("reset_objects_mods", key="reset_values", callback=keyTools.reset_object_values, default=True),
                toolbox.get_tool("reset_set_defaults"),
                toolbox.get_tool("reset_restore_defaults"),
                "separator",
                toolbox.get_tool("reset_clear_all"),
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
        delete_anim_tool = toolbox.get_tool("deleteAnimation")
        delete_anim_btn = cw.create_tool_button_from_data(delete_anim_tool)
        sec.addWidget(
            delete_anim_btn,
            delete_anim_tool.get("label", "Delete Anim"),
            "delete_anim",
            tooltip_template=delete_anim_tool.get("tooltip_template"),
            description=delete_anim_tool.get("description"),
        )

        sec = new_section(color=toolColors.green)

        selector_tool = toolbox.get_tool("selector")
        selector_button_widget = cw.QFlatSelectorButton(
            icon=selector_tool.get("icon_path"),
            tooltip_template=selector_tool.get("tooltip_template"),
        )
        selector_button_widget.clicked.connect(selector_tool.get("callback"))
        sec.addWidget(
            selector_button_widget,
            selector_tool.get("label", "Selector"),
            selector_tool.get("key", "selector"),
            tooltip_template=selector_tool.get("tooltip_template"),
        )

        def update_selector_button_text():
            if not wutil.is_valid_widget(selector_button_widget):
                return
            num_selected = wutil.get_selected_object_count()
            selector_button_widget.setCount(num_selected)

        try:
            self._runtime_manager.selection_changed.connect(update_selector_button_text)
        except Exception:
            pass
        update_selector_button_text()

        # Select opposite ---------------------------------------------------------------------
        sec.addWidgetGroup(
            [
                toolbox.get_tool("selectOpposite", key="opposite_select", default=True),
                toolbox.get_tool("opposite_add"),
                toolbox.get_tool("opposite_copy"),
            ]
        )

        # Mirror -----------------------------------------------------------------------
        sec.addWidgetGroup(
            [
                {
                    **toolbox.get_tool("mirror"),
                    "key": "mirror",
                    "default": True,
                },
                toolbox.get_tool("mirror_add_invert"),
                toolbox.get_tool("mirror_add_keep"),
                toolbox.get_tool("mirror_remove_exc"),
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

        # Select hierarchy -----------------------------------------------------------------------
        select_hierarchy_tool = toolbox.get_tool("selectHierarchy")
        select_hierarchy_button_widget = cw.create_tool_button_from_data(select_hierarchy_tool)
        sec.addWidget(
            select_hierarchy_button_widget,
            select_hierarchy_tool.get("label", "Select Hierarchy"),
            "select_hierarchy",
            tooltip_template=select_hierarchy_tool.get("tooltip_template"),
            description=select_hierarchy_tool.get("description"),
        )

        sec = new_section(color=toolColors.green)

        # Copy Paste Pose -----------------------------------------------------------------------
        sec.addWidgetGroup(
            [
                toolbox.get_tool("copy_pose", default=True),
                toolbox.get_tool("cp_paste_pose"),
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
                toolbox.get_tool("copy_animation", key="cp_copy_anim", default=True),
                toolbox.get_tool("cp_paste_anim"),
                toolbox.get_tool("cp_paste_ins"),
                toolbox.get_tool("cp_paste_opp"),
                toolbox.get_tool("cp_paste_to"),
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

        sec = new_section(color=toolColors.purple)

        # Animation Offset -----------------------------------------------------------------------
        animation_offset_tool = toolbox.get_tool("animation_offset")
        animation_offset_button_widget = cw.create_tool_button_from_data(animation_offset_tool, callback=None)
        animation_offset_button_widget.setObjectName("anim_offset_button")
        animation_offset_button_widget.setCheckable(True)
        animation_offset_button_widget.setChecked(bool(self.toggleAnimOffsetButtonState))
        animation_offset_button_widget.clicked.connect(self.toggleAnimOffsetButton)
        self.animation_offset_button_widget = animation_offset_button_widget
        sec.addWidget(
            animation_offset_button_widget,
            animation_offset_tool.get("label", "Anim Offset"),
            animation_offset_tool.get("key", "animation_offset"),
            tooltip_template=animation_offset_tool.get("tooltip_template"),
        )

        sec = new_section(color=toolColors.purple)

        # Temp Pivot ----------------------------------------------------------------------------
        sec.addWidgetGroup(
            [
                toolbox.get_tool("temp_pivot", default=True),
                toolbox.get_tool("tp_last_used"),
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
        micro_move_tool = toolbox.get_tool("micro_move")
        micro_move_button_widget = cw.create_tool_button_from_data(micro_move_tool, callback=None)
        micro_move_button_widget.setObjectName("micro_move_button")
        micro_move_button_widget.setCheckable(True)
        micro_move_button_widget.setChecked(self.micro_move_controller.is_enabled())
        micro_move_button_widget.clicked.connect(self.toggle_micro_move_button)
        sec.addWidget(
            micro_move_button_widget,
            micro_move_tool.get("label", "Micro Move"),
            micro_move_tool.get("key", "micro_move"),
            tooltip_template=micro_move_tool.get("tooltip_template"),
        )

        sec.addWidgetGroup(
            [
                toolbox.get_tool("follow_cam", default=True),
                toolbox.get_tool("fcam_trans_only"),
                toolbox.get_tool("fcam_rot_only"),
                "separator",
                toolbox.get_tool("fcam_remove"),
            ],
        )

        sec = new_section(color=toolColors.green)

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

        def start_link_obj_toggle_image_thread():
            self.link_obj_image_timer = True
            if self.link_obj_thread:
                try:
                    self.link_obj_thread.stop()
                    self.link_obj_thread.wait(500)
                except Exception:
                    pass
            self.link_obj_thread = LinkObjectImageThread(interval_seconds=0.3, parent=self)
            self.link_obj_thread.tick.connect(toggle_link_obj_button_image)
            self.link_obj_thread.start()

        def stop_link_obj_toggle_image_thread():
            self.link_obj_image_timer = False
            if self.link_obj_thread:
                try:
                    self.link_obj_thread.stop()
                    self.link_obj_thread.wait(500)
                except Exception:
                    pass
                self.link_obj_thread = None

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

        # Initialize on startup
        if self.link_checkbox_state:
            add_link_objects_callback()

        link_objects_button_widget = sec.addWidgetGroup(
            [
                toolbox.get_tool("mod_link_objects", key="link_objects", callback=keyTools.copy_link, default=True),
                toolbox.get_tool("link_copy"),
                toolbox.get_tool("link_paste"),
                "separator",
                {
                    "key": "link_autolink",
                    "label": "Auto-link",
                    "icon_path": media.link_objects_image,
                    "callback": toggle_auto_link_callback,
                    "checkable": True,
                    "set_checked_fn": lambda: self.link_checkbox_state,
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
                toolbox.get_tool("copy_worldspace_single_frame", key="ws_copy_frame", label="Copy World Space", default=True),
                toolbox.get_tool("ws_copy_range"),
                "separator",
                toolbox.get_tool("ws_paste_frame"),
                toolbox.get_tool("ws_paste"),
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

        attribute_switcher_button_widget = sec.addWidgetGroup(
            [
                toolbox.get_tool("attribute_switcher", callback=None, default=True),
            ],
        )
        if attribute_switcher_button_widget:
            attribute_switcher_button_widget.setObjectName("toggle_attribute_switcher_window_b")
            ui.bind_attribute_switcher_toolbar_button(attribute_switcher_button_widget)

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
                    "set_checked_fn": lambda: settings.get_setting(
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

        # custom tools ----------------------------------------------------------------------------
        orbit_button_widget = sec.addWidgetGroup(
            [
                toolbox.get_tool("orbit", callback=None, default=True),
                {
                    "key": "orbit_auto_transparency",
                    "label": "Auto Transparency",
                    "description": "Make the Orbit window translucent when not hovered.",
                    "checkable": True,
                    "set_checked_fn": lambda: settings.get_setting(
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

        # customGraph ----------------------------------------------------------------------------
        graph_toolbar_button = sec.addWidgetGroup(
            [
                toolbox.get_tool(
                    "custom_graph",
                    checkable=True,
                    set_checked=lambda: settings.get_setting("graph_toolbar_enabled", True),
                    callback=lambda state: report.safe_execute(
                        graphToolbarApi.set_graph_toolbar_enabled,
                        bool(state),
                        apply=True,
                        context="graph toolbar toggle",
                    ),
                    default_visible=False,
                )
            ]
        )
        if graph_toolbar_button:
            graph_toolbar_button.setObjectName("toggle_graph_toolbar_button")
            graphToolbarApi.bind_graph_toolbar_toggle(graph_toolbar_button)

        invalidate_caches()

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

        custom_tools_tool = toolbox.get_tool("custom_tools")
        toolBox_button_widget = cw.create_tool_button_from_data(custom_tools_tool, callback=None)
        toolBox_button_widget.setVisible(bool(CUSTOM_TOOLS_MENU))
        sec.addWidget(
            toolBox_button_widget,
            custom_tools_tool.get("label", "Custom Tools"),
            custom_tools_tool.get("key", "custom_tools"),
            tooltip_template=custom_tools_tool.get("tooltip_template"),
            default_visible=False,
        )
        toolBox_menu = QtWidgets.QMenu(toolBox_button_widget)
        toolBox_menu.aboutToShow.connect(initialize_tool_menu)
        toolBox_button_widget.setContextMenuPolicy(QtCore.Qt.CustomContextMenu)
        toolBox_button_widget.customContextMenuRequested.connect(lambda pos: toolBox_menu.exec_(toolBox_button_widget.mapToGlobal(pos)))
        toolBox_button_widget.clicked.connect(lambda: toolBox_menu.exec_(QtGui.QCursor.pos()))

        # custom scripts ----------------------------------------------------------------------------

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

        custom_scripts_tool = toolbox.get_tool("custom_scripts")
        customScripts_button_widget = cw.create_tool_button_from_data(custom_scripts_tool, callback=None)
        customScripts_button_widget.setVisible(bool(CUSTOM_SCRIPTS_MENU))
        sec.addWidget(
            customScripts_button_widget,
            custom_scripts_tool.get("label", "Custom Scripts"),
            custom_scripts_tool.get("key", "custom_scripts"),
            tooltip_template=custom_scripts_tool.get("tooltip_template"),
            default_visible=False,
        )

        customScripts_menu = QtWidgets.QMenu(customScripts_button_widget)
        customScripts_button_widget.setContextMenuPolicy(QtCore.Qt.CustomContextMenu)
        customScripts_button_widget.customContextMenuRequested.connect(
            lambda pos: customScripts_menu.exec_(customScripts_button_widget.mapToGlobal(pos))
        )
        customScripts_menu.aboutToShow.connect(initialize_scripts_menu)
        customScripts_button_widget.clicked.connect(lambda: customScripts_menu.exec_(QtGui.QCursor.pos()))

        # initialize_scripts_menu()

        # _____________________ Workspaces Section ____________________________ #
        sec = new_section(hiddeable=False)

        overshootSliders = settings.get_setting("sliders_overshoot", False)

        def _setOvershoot(state):
            settings.set_setting("sliders_overshoot", state)
            sw.globalSignals.overshootChanged.emit(state)

        settings_tool = toolbox.get_tool("settings")
        toolbar_config_button_widget = cw.create_tool_button_from_data(settings_tool, callback=None)
        toolbar_config_button_widget.setObjectName("settings_toolbar_button")
        sec.addWidget(
            toolbar_config_button_widget,
            settings_tool.get("label", "Settings"),
            settings_tool.get("key", "settings"),
            description=settings_tool.get("description"),
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

        graph_toolbar_action = settings_menu.addAction(
            QtGui.QIcon(media.customGraph_image),
            "Graph Editor Toolbar",
            description="Show or hide the TKM toolbar inside the Graph Editor.",
        )
        graph_toolbar_action.setCheckable(True)

        def _on_graph_toolbar_toggled(state):
            report.safe_execute(graphToolbarApi.set_graph_toolbar_enabled, bool(state), context="graph toolbar toggle")
            try:
                graph_toolbar_action.setChecked(bool(graphToolbarApi.get_graph_toolbar_checkbox_state()))
            except Exception:
                pass

        graph_toolbar_action.toggled.connect(_on_graph_toolbar_toggled)
        graphToolbarApi.bind_graph_toolbar_toggle(graph_toolbar_action)

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
        runtime.shutdown_runtime_manager()
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
