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
from maya import cmds, mel, OpenMayaUI as mui
from maya.app.general.mayaMixin import MayaQWidgetDockableMixin  # type: ignore

from TheKeyMachine.Qt import QtCompat, QtCore, QtGui, QtWidgets  # type: ignore


# Standard library imports
import os
import time
import shutil

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
import TheKeyMachine.mods.helperMod as helper  # type: ignore
from TheKeyMachine.data import icons
import TheKeyMachine.mods.styleMod as style  # type: ignore
import TheKeyMachine.mods.barMod as bar  # type: ignore
import TheKeyMachine.mods.settingsMod as settings  # type: ignore
import TheKeyMachine.core.customGraph as cg  # type: ignore
import TheKeyMachine.mods.updater as updater  # type: ignore
import TheKeyMachine.core.toolMenus as toolMenus  # type: ignore
import TheKeyMachine.core.toolbox as toolbox  # type: ignore
import TheKeyMachine.core.toolWidgets as toolWidgets  # type: ignore
import TheKeyMachine.core.runtimeManager as runtime  # type: ignore
import TheKeyMachine.tools.animation_offset.api as animationOffsetApi  # type: ignore
import TheKeyMachine.tools.graph_toolbar.api as graphToolbarApi  # type: ignore
import TheKeyMachine.tools.gimbal_fixer.api as gimbalFixerApi  # type: ignore
import TheKeyMachine.tools.micro_move.api as microMoveApi  # type: ignore
import TheKeyMachine.tools.isolate_bookmarks.api as isolateBookmarksApi  # type: ignore

from TheKeyMachine.tools.link_objects.pulse_thread import LinkObjectPulseThread  # type: ignore
from TheKeyMachine.tools.selection_sets.controller import SelectionSetsController  # type: ignore
from TheKeyMachine.tools import colors as toolColors  # type: ignore

from TheKeyMachine.widgets import customWidgets as cw  # type: ignore
from TheKeyMachine.widgets import customDialogs as customDialogs  # type: ignore
from TheKeyMachine.widgets import util as wutil  # type: ignore

QT_WIDGET_SIZE_MAX = 16777215


mods = [
    general,
    ui,
    report,
    keyTools,
    helper,
    bar,
    settings,
    cg,
    updater,
    style,
    cw,
    customDialogs,
    wutil,
    toolMenus,
    toolbox,
    toolWidgets,
    animationOffsetApi,
    graphToolbarApi,
    gimbalFixerApi,
    microMoveApi,
    isolateBookmarksApi,
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


WORKSPACE_NAME = "k"
WORKSPACE_CONTROL_NAME = WORKSPACE_NAME + "WorkspaceControl"


UI_COLORS = toolColors.UI_COLORS


class toolbar(MayaQWidgetDockableMixin, QtWidgets.QDialog):
    def __init__(self, parent=None):
        super().__init__(parent=parent)
        self.setWindowTitle("TheKeyMachine")
        self.setObjectName(WORKSPACE_NAME)
        self.setContextMenuPolicy(QtCore.Qt.PreventContextMenu)
        self.selection_sets_controller = SelectionSetsController(owner=self)

        self._runtime_manager = runtime.get_runtime_manager()
        report.install_bug_exception_handler()
        graphToolbarApi.sync_graph_toolbar_watch()
        self._runtime_manager.scene_opened.connect(self._on_scene_opened)
        self._runtime_manager.scene_new.connect(self._on_scene_opened)
        self._runtime_manager.graph_editor_opened.connect(self._on_graph_editor_opened)

        self.tabbar_painter = None
        self._height_update_pending = False
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
        self.link_obj_toggle_state = False
        self.link_obj_pulse_thread = None

        self.buildUI()

        # Reconcile Graph Editor state at startup; ongoing tracking uses the event filter.
        QtCore.QTimer.singleShot(0, self._sync_graph_editor_on_startup)

    def closeEvent(self, event):
        """
        Handles the close event for the toolbar window.
        Stops all background threads and performs necessary cleanup.
        """
        global _toolbar_instance
        _toolbar_instance = None

        try:
            runtime.shutdown_runtime_manager()
        except (RuntimeError, ValueError, TypeError, AttributeError, KeyError, IndexError):
            pass

        was_anim_offset_active = self.toggleAnimOffsetButtonState
        self.animation_offset_controller.deactivate()
        if was_anim_offset_active:
            try:
                cmds.undoInfo(closeChunk=True)
            except (RuntimeError, ValueError, TypeError, AttributeError, KeyError, IndexError):
                pass

        self.micro_move_controller.deactivate()

        # Stop link objects button pulse thread
        if hasattr(self, "link_obj_pulse_thread") and self.link_obj_pulse_thread:
            try:
                self.link_obj_pulse_thread.stop()
                self.link_obj_pulse_thread.wait(500)
            except (RuntimeError, ValueError, TypeError, AttributeError, KeyError, IndexError):
                pass
            self.link_obj_pulse_thread = None

        self._delete_tabbar_painter()

        super().closeEvent(event)

    def _delete_tabbar_painter(self):
        if self.tabbar_painter and QtCompat.isValid(self.tabbar_painter):
            try:
                self.tabbar_painter.setParent(None)
                self.tabbar_painter.deleteLater()
            except (RuntimeError, ValueError, TypeError, AttributeError, KeyError, IndexError):
                pass
        self.tabbar_painter = None

    def _on_scene_opened(self, *_args):
        if not QtCompat.isValid(self):
            return
        self.update_isolate_bookmarks_menu()

    def toggle_selection_sets_workspace(self, *args):
        return self.selection_sets_controller.toggle_selection_sets_workspace(*args)

    def _on_graph_editor_opened(self, *_args):
        if not QtCompat.isValid(self):
            return
        if not settings.get_setting("graph_toolbar_enabled", True):
            return
        QtCore.QTimer.singleShot(0, cg.createCustomGraph)

    def _sync_graph_editor_on_startup(self):
        if not QtCompat.isValid(self):
            return
        if not settings.get_setting("graph_toolbar_enabled", True):
            return

        graph_vis = cmds.getPanel(vis=True) or []
        if "graphEditor1" in graph_vis:
            QtCore.QTimer.singleShot(0, cg.createCustomGraph)

    def showWindow(self):
        # Build up kwargs for the visibleChangeCommand
        visible_change_kwargs = {
            "visibleChangeCommand": self.visible_change_command,
        }

        # Show the window first to ensure parenting is established
        self.show(dockable=True, retain=False, **visible_change_kwargs)

        kwargs = {
            "e": True,
            "visibleChangeCommand": self.visible_change_command,
        }

        if self.isFloating():
            kwargs["tp"] = ["west", 0]
            kwargs["rsw"] = 900
            kwargs["rsh"] = 40

        if cmds.workspaceControl(WORKSPACE_CONTROL_NAME, q=True, exists=True):
            try:
                layout, orient = self.docking_position
                if wutil.check_visible_layout(layout):
                    dock_to = self.get_dock_to_control_name(layout)
                    cmds.workspaceControl(WORKSPACE_CONTROL_NAME, edit=True, dtc=(dock_to, orient))

                cmds.workspaceControl(WORKSPACE_CONTROL_NAME, edit=True, tabPosition=["west", 0])
            except (RuntimeError, ValueError, TypeError, AttributeError, KeyError, IndexError):
                pass

            # Update the workspace control with our kwargs (like visibleChangeCommand)
            cmds.workspaceControl(WORKSPACE_CONTROL_NAME, **kwargs)

        # Force initial resize
        QtCore.QTimer.singleShot(200, self.shelf_tabbar)
        QtCore.QTimer.singleShot(500, self.update_height)

    def visible_change_command(self, *args):
        if not QtCompat.isValid(self):
            return

        if not self.isDockable():
            return
        if self.current_layout != cmds.workspaceLayoutManager(q=1, current=True):
            self.current_layout = cmds.workspaceLayoutManager(q=1, current=True)
            if not self.isVisible():
                if QtCompat.isValid(self):
                    cmds.evalDeferred(show, lowestPriority=True)

                if self.tabbar_painter and QtCompat.isValid(self.tabbar_painter):
                    self.tabbar_painter.show()
                else:
                    cmds.evalDeferred(self.shelf_tabbar, lowestPriority=True)
                return

        if not self.isFloating():
            if cmds.workspaceControl(WORKSPACE_CONTROL_NAME, q=True, collapse=True):
                timer = QtCore.QTimer(self)
                timer.setSingleShot(True)

                timer.timeout.connect(
                    partial(
                        cmds.workspaceControl,
                        WORKSPACE_CONTROL_NAME,
                        e=True,
                        collapse=False,
                        tp=["west", 0],
                    )
                )
                timer.start(100)
            if self.tabbar_painter and QtCompat.isValid(self.tabbar_painter):
                self.tabbar_painter.show()
            else:
                cmds.evalDeferred(self.shelf_tabbar, lowestPriority=True)
        else:
            if self.tabbar_painter and QtCompat.isValid(self.tabbar_painter):
                self.tabbar_painter.hide()

        self.update_height()

    def shelf_tabbar(self):
        if not QtCompat.isValid(self):
            return

        self._delete_tabbar_painter()

        qctrl = mui.MQtUtil.findControl(WORKSPACE_CONTROL_NAME)
        control = wutil.get_maya_qt(qctrl)
        tab_handle = control.parent().parent()

        control.setSizePolicy(QtWidgets.QSizePolicy.Minimum, QtWidgets.QSizePolicy.Minimum)

        tab_bar = tab_handle.tabBar()
        if self.isFloating():
            return tab_bar.setVisible(False)

        # Temporary tab-bar experiment: paint the shelf treatment directly on
        # Maya's tab bar instead of creating the full-height shelf overlay.
        tab_bar.setVisible(True)
        tab_bar.setFixedHeight(wutil.DPI(1000))

        self.tabbar_painter = cw.QFlatTabBarPainter(tab_bar, tab_handle)

    def update_height(self):
        if not QtCompat.isValid(self):
            return
        tkm_widget = mui.MQtUtil.findControl(WORKSPACE_CONTROL_NAME)
        if not tkm_widget:
            return
        workspace_widget = wutil.get_maya_qt(tkm_widget, QtWidgets.QWidget)
        if workspace_widget is None or not QtCompat.isValid(workspace_widget):
            return

        try:
            parent = workspace_widget.parentWidget()
            dock_container = parent.parentWidget() if parent and QtCompat.isValid(parent) else None

            if self.isFloating():
                for widget in (self, workspace_widget, dock_container):
                    self._set_qt_height(widget)
                return

            self.main_toolbar_widget._update_height()
            # QFlowLayout already includes its equal top and bottom contents
            # margins. Extra outer height collects below the fixed flow widget
            # and makes the bottom padding appear larger than the top.
            target_height = max(1, int(self.main_toolbar_widget.height()))

            # Keep Maya's workspaceControl sizing policy untouched. Lock only the
            # hosted Qt widgets; setFixedHeight can then be revised whenever the
            # flow container reports a different content height.
            self.setSizePolicy(QtWidgets.QSizePolicy.Expanding, QtWidgets.QSizePolicy.Fixed)
            for widget in (self, workspace_widget):
                self._set_qt_height(widget, target_height)

            # Maya places the workspace child below a small native frame/tab
            # inset. Give the dock pane the same allowance below the child so
            # the flow layout's bottom margin is not clipped by that frame.
            dock_height = target_height
            if dock_container is not None and QtCompat.isValid(dock_container):
                workspace_top = workspace_widget.mapTo(
                    dock_container,
                    QtCore.QPoint(0, 0),
                ).y()
                dock_height += max(0, int(workspace_top) * 2)
                self._set_qt_height(dock_container, dock_height)
            self._resize_dock_splitter(workspace_widget, dock_height)
            if self.tabbar_painter and QtCompat.isValid(self.tabbar_painter):
                self.tabbar_painter.syncGeometry()
        except RuntimeError:
            # Maya may destroy/rebuild a workspaceControl between a deferred
            # validity check and the following Qt call. A later layout event
            # will reacquire the current control and apply the height again.
            return

    @staticmethod
    def _set_qt_height(widget, height=None):
        """Set or release a Qt height without touching workspaceControl flags."""
        if widget is None or not QtCompat.isValid(widget):
            return
        if height is None:
            widget.setMinimumHeight(0)
            widget.setMaximumHeight(QT_WIDGET_SIZE_MAX)
        else:
            widget.setFixedHeight(int(height))

    @staticmethod
    def _resize_dock_splitter(workspace_widget, target_height):
        """Make Maya's vertical dock splitter honor a content-driven height."""
        if workspace_widget is None or not QtCompat.isValid(workspace_widget):
            return
        child = workspace_widget
        parent = child.parentWidget()
        while parent is not None and QtCompat.isValid(parent):
            if isinstance(parent, QtWidgets.QSplitter) and parent.orientation() == QtCore.Qt.Vertical:
                direct_child = child
                while direct_child.parentWidget() is not parent:
                    direct_child = direct_child.parentWidget()
                    if direct_child is None:
                        return
                index = parent.indexOf(direct_child)
                sizes = parent.sizes()
                if index < 0 or index >= len(sizes):
                    return

                difference = int(target_height) - sizes[index]
                sizes[index] = int(target_height)
                other_indices = [i for i in range(len(sizes)) if i != index]
                if other_indices:
                    # Exchange space with the largest neighboring pane. This
                    # works for both growth and shrinkage without resizing the
                    # Maya main window itself.
                    donor = max(other_indices, key=lambda i: sizes[i])
                    sizes[donor] = max(1, sizes[donor] - difference)
                parent.setSizes(sizes)
                parent.updateGeometry()
                return
            child = parent
            parent = parent.parentWidget()

    def _on_toolbar_content_height_changed(self, _height):
        if self._height_update_pending:
            return
        self._height_update_pending = True

        def _apply_height():
            self._height_update_pending = False
            if QtCompat.isValid(self):
                self.update_height()

        QtCore.QTimer.singleShot(0, _apply_height)

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
                if action and QtCompat.isValid(action):
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
        cmds.workspaceControl(WORKSPACE_CONTROL_NAME, **kwargs)

    def create_shelf_icon(self, *args):
        button_name = "TheKeyMachine"
        command = "import TheKeyMachine;TheKeyMachine.toggle()"
        icon = icons.tkm_main
        icon = os.path.normpath(icon)
        current_shelf_tab = cmds.tabLayout("ShelfLayout", query=True, selectTab=True)

        for child in cmds.shelfLayout(current_shelf_tab, query=True, childArray=True) or []:
            if cmds.objectTypeUI(child) != "shelfButton":
                continue

            if (
                cmds.shelfButton(child, query=True, label=True) == button_name
                or cmds.shelfButton(child, query=True, command=True) == command
            ):
                cmds.deleteUI(child)

        cmds.shelfButton(parent=current_shelf_tab, image=icon, command=command, label=button_name)

    # Update the isolate_bookmarks menu when scene changes
    def update_isolate_bookmarks_menu(self, *args):
        if not QtCompat.isValid(self):
            return
        isolateBookmarksApi.update_isolate_popup_menu()

    # For use with toggle functionality on Shelf or Launcher
    def toggle(self, *args):
        self.showWindow()

    def reload(self, *args):
        toolbar_module_name = "TheKeyMachine.core.toolbar"
        customGraph_module_name = "TheKeyMachine.core.customGraph"

        try:
            report.uninstall_bug_exception_handler()
        except (RuntimeError, ValueError, TypeError, AttributeError, KeyError, IndexError):
            pass

        try:
            runtime.shutdown_runtime_manager()
        except (RuntimeError, ValueError, TypeError, AttributeError, KeyError, IndexError):
            pass

        try:
            for widget in QtWidgets.QApplication.topLevelWidgets():
                if widget.property("tkm_floating_widget"):
                    widget.close()
                    try:
                        widget.deleteLater()
                    except (RuntimeError, ValueError, TypeError, AttributeError, KeyError, IndexError):
                        pass
        except (RuntimeError, ValueError, TypeError, AttributeError, KeyError, IndexError):
            pass

        # Importa el módulo y recarga
        toolbar_module = import_module(toolbar_module_name)
        customGraph_module = import_module(customGraph_module_name)

        # Close and delete the UI
        try:
            if cmds.workspaceControl(WORKSPACE_CONTROL_NAME, q=True, exists=True):
                cmds.deleteUI(WORKSPACE_CONTROL_NAME, control=True)
        except (RuntimeError, ValueError, TypeError, AttributeError, KeyError, IndexError):
            pass

        if QtCompat.isValid(self):
            try:
                self.blockSignals(True)
                self.close()
            except (RuntimeError, ValueError, TypeError, AttributeError, KeyError, IndexError):
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
            report.uninstall_bug_exception_handler()
        except (RuntimeError, ValueError, TypeError, AttributeError, KeyError, IndexError):
            pass

        graphToolbarApi.shutdown_graph_toolbar_runtime()

        try:
            runtime.shutdown_runtime_manager()
        except (RuntimeError, ValueError, TypeError, AttributeError, KeyError, IndexError):
            pass

        try:
            for widget in QtWidgets.QApplication.topLevelWidgets():
                if widget.property("tkm_floating_widget"):
                    widget.close()
                    try:
                        widget.deleteLater()
                    except (RuntimeError, ValueError, TypeError, AttributeError, KeyError, IndexError):
                        pass
        except (RuntimeError, ValueError, TypeError, AttributeError, KeyError, IndexError):
            pass

        try:
            if cmds.workspaceControl(WORKSPACE_CONTROL_NAME, q=True, exists=True):
                cmds.deleteUI(WORKSPACE_CONTROL_NAME, control=True)
        except (RuntimeError, ValueError, TypeError, AttributeError, KeyError, IndexError):
            pass

        try:
            if QtCompat.isValid(self):
                self.blockSignals(True)
                self.close()
                self.deleteLater()
        except (RuntimeError, ValueError, TypeError, AttributeError, KeyError, IndexError):
            pass

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

    def _populate_toolbar_from_layout(self, layout_id, new_section_fn):
        return toolWidgets.populate_main_toolbar_from_layout(layout_id, new_section_fn, self)

    def _get_current_icon_alignment(self):
        return toolWidgets.get_main_toolbar_icon_alignment()

    def set_toolbar_icon_alignment(self, alignment_name):
        return toolWidgets.set_main_toolbar_icon_alignment(self, alignment_name)

    def buildUI(self):
        ### ______________________________________________________ TOOLBAR LAYOUT _____________________________________________________________________###

        if self.layout():
            QtWidgets.QWidget().setLayout(self.layout())

        self.setSizePolicy(QtWidgets.QSizePolicy.Preferred, QtWidgets.QSizePolicy.Minimum)
        self.main_layout = QtWidgets.QHBoxLayout(self)
        self.main_layout.setContentsMargins(0, 0, 0, 0)

        toolbar_alignment = self._get_current_icon_alignment()
        self.main_toolbar_widget = cw.QFlatToolbar(
            parent=self,
            settings_namespace="main_toolbar_toolbuttons",
            margin=2,
            spacing_w=10,
            spacing_h=6,
            alignment=toolbar_alignment,
        )
        self.main_toolbar_widget.heightChanged.connect(self._on_toolbar_content_height_changed)
        self.main_layout.addWidget(self.main_toolbar_widget)

        def new_section(spacing=0, hiddeable=True, color=None):
            return self.main_toolbar_widget.add_section(
                spacing=spacing,
                hiddeable=hiddeable,
                color=color,
            )

        self._populate_toolbar_from_layout("main", new_section)


_toolbar_instance = None


def get_toolbar():
    global _toolbar_instance
    return _toolbar_instance


def show():
    global _toolbar_instance

    try:
        runtime.shutdown_runtime_manager()
    except (RuntimeError, ValueError, TypeError, AttributeError, KeyError, IndexError):
        pass

    # Close existing UI robustly
    try:
        if cmds.workspaceControl(WORKSPACE_CONTROL_NAME, q=True, exists=True):
            cmds.deleteUI(WORKSPACE_CONTROL_NAME, control=True)
    except (RuntimeError, ValueError, TypeError, AttributeError, KeyError, IndexError):
        pass

    if _toolbar_instance and QtCompat.isValid(_toolbar_instance):
        try:
            _toolbar_instance.close()
            _toolbar_instance.deleteLater()
        except (RuntimeError, ValueError, TypeError, AttributeError, KeyError, IndexError):
            pass

    _toolbar_instance = toolbar()
    _toolbar_instance.showWindow()


def toggle():
    global _toolbar_instance
    try:
        if cmds.workspaceControl(WORKSPACE_CONTROL_NAME, query=True, exists=True):
            vis_state = cmds.workspaceControl(WORKSPACE_CONTROL_NAME, query=True, visible=True)

            if vis_state:
                cmds.workspaceControl(WORKSPACE_CONTROL_NAME, edit=True, visible=False)
            else:
                cmds.workspaceControl(WORKSPACE_CONTROL_NAME, edit=True, restore=True)
            return
    except (RuntimeError, ValueError, TypeError, AttributeError, KeyError, IndexError):
        pass
    _toolbar_instance = toolbar()
    _toolbar_instance.showWindow()


def welcome():
    show()

    def _show_welcome_prompt():
        toolbar_instance = get_toolbar()
        if not toolbar_instance or not QtCompat.isValid(toolbar_instance):
            return
        anchor = toolbar_instance.findChild(QtWidgets.QWidget, "TKM_toolbar_button")
        if not wutil.is_valid_widget(anchor):
            return
        toolWidgets.show_welcome_shelf_prompt(anchor, toolbar_instance)

    QtCore.QTimer.singleShot(700, _show_welcome_prompt)


def _call_toolbar_method(method_name, *args, **kwargs):
    toolbar_instance = get_toolbar()
    if not toolbar_instance:
        return None
    method = getattr(toolbar_instance, method_name, None)
    if not callable(method):
        return None
    return method(*args, **kwargs)


def reload_current(*args, **kwargs):
    return _call_toolbar_method("reload", *args, **kwargs)


def unload_current(*args, **kwargs):
    return _call_toolbar_method("unload", *args, **kwargs)


def create_shelf_icon_current(*args, **kwargs):
    return _call_toolbar_method("create_shelf_icon", *args, **kwargs)


def toggle_animation_offset(checked=None, *args, **kwargs):
    state = args[0] if args else kwargs.get("checked", checked)
    return _call_toolbar_method("toggleAnimOffsetButton", state)


def toggle_micro_move(checked=None, *args, **kwargs):
    state = args[0] if args else kwargs.get("checked", checked)
    return _call_toolbar_method("toggle_micro_move_button", state)


def toggle_selection_sets_workspace(*args, **kwargs):
    return _call_toolbar_method("toggle_selection_sets_workspace", *args, **kwargs)
