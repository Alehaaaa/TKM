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

try:
    from PySide6 import QtWidgets, QtCore, QtGui  # type: ignore
    from shiboken6 import isValid  # type: ignore
except ImportError:
    from PySide2 import QtWidgets, QtCore, QtGui  # type: ignore
    from shiboken2 import isValid  # type: ignore


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

# import TheKeyMachine.mods.selSetsMod as selSets  # type: ignore
import TheKeyMachine.mods.helperMod as helper  # type: ignore
import TheKeyMachine.mods.mediaMod as media  # type: ignore
import TheKeyMachine.mods.styleMod as style  # type: ignore
import TheKeyMachine.mods.barMod as bar  # type: ignore
import TheKeyMachine.mods.settingsMod as settings  # type: ignore
import TheKeyMachine.core.customGraph as cg  # type: ignore
import TheKeyMachine.mods.updater as updater  # type: ignore
import TheKeyMachine.core.toolMenus as toolMenus  # type: ignore
import TheKeyMachine.core.toolbox as toolbox  # type: ignore
import TheKeyMachine.core.runtime_manager as runtime  # type: ignore
import TheKeyMachine.core.trigger as trigger  # type: ignore
import TheKeyMachine.tools.animation_offset.api as animationOffsetApi  # type: ignore
import TheKeyMachine.tools.attribute_switcher.api as attributeSwitcherApi  # type: ignore
import TheKeyMachine.tools.graph_toolbar.api as graphToolbarApi  # type: ignore
import TheKeyMachine.tools.micro_move.api as microMoveApi  # type: ignore
import TheKeyMachine.tools.ibookmarks.api as iBookmarksApi  # type: ignore

from TheKeyMachine.tools.link_objects.pulse_thread import LinkObjectPulseThread  # type: ignore
from TheKeyMachine.tools.selection_sets.controller import SelectionSetsController  # type: ignore
from TheKeyMachine.tools import colors as toolColors  # type: ignore

from TheKeyMachine.core import selection_targets

from TheKeyMachine.widgets import sliderWidget as sw  # type: ignore
from TheKeyMachine.widgets import customWidgets as cw  # type: ignore
from TheKeyMachine.widgets import customDialogs as customDialogs  # type: ignore
from TheKeyMachine.widgets import util as wutil  # type: ignore
import TheKeyMachine.sliders as sliders  # type: ignore

from TheKeyMachine.tooltips import QFlatTooltipManager


mods = [
    general,
    ui,
    report,
    keyTools,
    helper,
    media,
    bar,
    settings,
    cg,
    updater,
    style,
    sw,
    cw,
    customDialogs,
    wutil,
    sliders,
    toolMenus,
    toolbox,
    animationOffsetApi,
    graphToolbarApi,
    microMoveApi,
    iBookmarksApi,
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

        # Stop link objects button pulse thread
        if hasattr(self, "link_obj_pulse_thread") and self.link_obj_pulse_thread:
            try:
                self.link_obj_pulse_thread.stop()
                self.link_obj_pulse_thread.wait(500)
            except Exception:
                pass
            self.link_obj_pulse_thread = None

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
        self.update_iBookmarks_menu()

    def toggle_selection_sets_workspace(self, *args):
        return self.selection_sets_controller.toggle_selection_sets_workspace(*args)

    def _on_graph_editor_opened(self, *_args):
        if not isValid(self):
            return
        if not settings.get_setting("graph_toolbar_enabled", True):
            return
        QtCore.QTimer.singleShot(0, cg.createCustomGraph)

    def _sync_graph_editor_on_startup(self):
        if not isValid(self):
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
            except Exception:
                pass

            # Update the workspace control with our kwargs (like visibleChangeCommand)
            cmds.workspaceControl(WORKSPACE_CONTROL_NAME, **kwargs)

        # Force initial resize
        QtCore.QTimer.singleShot(200, self.shelf_tabbar)
        QtCore.QTimer.singleShot(500, self.update_height)

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

        qctrl = mui.MQtUtil.findControl(WORKSPACE_CONTROL_NAME)
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
            tkm_widget = mui.MQtUtil.findControl(WORKSPACE_CONTROL_NAME)
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
        cmds.workspaceControl(WORKSPACE_CONTROL_NAME, **kwargs)

    def _settings_toggle_specs(self):
        def _get_overshoot():
            return settings.get_setting("sliders_overshoot", False)

        def _set_overshoot(state):
            settings.set_setting("sliders_overshoot", bool(state))
            sw.globalSignals.overshootChanged.emit(bool(state))

        def _get_euler_filter():
            return settings.get_setting(
                "euler_filter",
                True,
                namespace=attributeSwitcherApi.ATTRIBUTE_SWITCHER_SETTINGS_NAMESPACE,
            )

        def _set_euler_filter(state):
            settings.set_setting(
                "euler_filter",
                bool(state),
                namespace=attributeSwitcherApi.ATTRIBUTE_SWITCHER_SETTINGS_NAMESPACE,
            )
            dlg = attributeSwitcherApi.get_attribute_switcher_window()
            if dlg and wutil.is_valid_widget(dlg):
                try:
                    dlg.euler_filter = bool(state)
                except Exception:
                    pass
            sw.globalSignals.eulerFilterChanged.emit(bool(state))

        def _set_graph_toolbar(state):
            report.safe_execute(
                graphToolbarApi.set_graph_toolbar_enabled,
                bool(state),
                apply=True,
                context="graph toolbar toggle",
            )

        return {
            "overshoot_sliders": {
                "key": "overshoot_sliders",
                "label": "Overshoot Sliders",
                "menu_label": "Overshoot Sliders",
                "text": "OS",
                "icon": media.sliders_overshoot_image,
                "description": "Set range for sliders to -150/150, from -100/100.",
                "get_checked": _get_overshoot,
                "set_checked": _set_overshoot,
                "changed_signal": sw.globalSignals.overshootChanged,
            },
            "attribute_switcher_euler_filter": {
                "key": "attribute_switcher_euler_filter",
                "label": "Auto Euler Filter",
                "menu_label": "Auto Euler Filter",
                "text": "EF",
                "icon": media.euler_filter_image,
                "description": "Apply Euler filtering after Attribute Switcher changes rotation order.",
                "get_checked": _get_euler_filter,
                "set_checked": _set_euler_filter,
                "changed_signal": sw.globalSignals.eulerFilterChanged,
            },
            "custom_graph": {
                "key": "custom_graph",
                "label": "Graph Editor Toolbar",
                "menu_label": "Show Graph Editor Toolbar",
                "text": "GE",
                "icon": media.customGraph_image,
                "description": "Show the TKM toolbar in the Graph Editor.",
                "get_checked": graphToolbarApi.get_graph_toolbar_checkbox_state,
                "set_checked": _set_graph_toolbar,
                "changed_signal": graphToolbarApi.custom_graph_bus.graph_toolbar_enabled_changed,
            },
        }

    def _set_checked_safely(self, widget, checked):
        if widget is None or not isValid(widget):
            return
        try:
            previous = widget.blockSignals(True)
        except Exception:
            previous = False
        try:
            widget.setChecked(bool(checked))
        except Exception:
            pass
        try:
            widget.blockSignals(previous)
        except Exception:
            pass

    def _sync_setting_toggle(self, widget, spec):
        self._set_checked_safely(widget, spec["get_checked"]())

    def _bind_setting_toggle(self, widget, spec):
        if widget is None:
            return
        widget.setCheckable(True)
        self._sync_setting_toggle(widget, spec)

        def _sync(_enabled=None, w=widget, s=spec):
            if w is None or not isValid(w):
                return
            self._sync_setting_toggle(w, s)

        signal = spec.get("changed_signal")
        try:
            signal.connect(_sync)
        except Exception:
            pass

    def create_shelf_icon(self, *args):
        button_name = "TheKeyMachine"
        command = "import TheKeyMachine;TheKeyMachine.toggle()"
        icon = media.asset_path("tool_icon")
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

    # Update the iBookmarks menu when scene changes
    def update_iBookmarks_menu(self, *args):
        if not isValid(self):
            return
        iBookmarksApi.update_isolate_popup_menu()

    # For use with toggle functionality on Shelf or Launcher
    def toggle(self, *args):
        self.showWindow()

    def reload(self, *args):
        toolbar_module_name = "TheKeyMachine.core.toolbar"
        customGraph_module_name = "TheKeyMachine.core.customGraph"

        try:
            report.uninstall_bug_exception_handler()
        except Exception:
            pass

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
            if cmds.workspaceControl(WORKSPACE_CONTROL_NAME, q=True, exists=True):
                cmds.deleteUI(WORKSPACE_CONTROL_NAME, control=True)
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
            report.uninstall_bug_exception_handler()
        except Exception:
            pass

        try:
            if graphToolbarApi.is_graph_toolbar_visible() or graphToolbarApi.get_graph_toolbar_checkbox_state():
                graphToolbarApi.set_graph_toolbar_enabled(False)
        except Exception:
            pass

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
            if cmds.workspaceControl(WORKSPACE_CONTROL_NAME, q=True, exists=True):
                cmds.deleteUI(WORKSPACE_CONTROL_NAME, control=True)
        except Exception:
            pass

        try:
            if isValid(self):
                self.blockSignals(True)
                self.close()
                self.deleteLater()
        except Exception:
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

    def _create_nudge_value_widget(self, sec, item_data):
        self.move_keyframes_intField = cw.QFlatSpinBox()
        self.move_keyframes_intField.setFixedWidth(wutil.DPI(50))
        sec.addWidget(
            self.move_keyframes_intField,
            item_data.get("label", "Nudge Value"),
            item_data.get("key", "nudge_value"),
            default=item_data.get("default", True),
            tooltip_template=item_data.get("tooltip_template"),
        )
        return self.move_keyframes_intField

    def _create_selector_widget(self, sec, item_data):
        selector_tool = toolbox.get_tool("selector", **{k: v for k, v in item_data.items() if k not in {"id", "shortcuts"}})
        btn = cw.QFlatSelectorButton(icon=selector_tool.get("icon"), tooltip_template=selector_tool.get("tooltip_template"))
        btn.clicked.connect(selector_tool.get("callback"))
        sec.addWidget(
            btn,
            selector_tool.get("label", "Selector"),
            selector_tool.get("key", "selector"),
            default=selector_tool.get("default", True),
            tooltip_template=selector_tool.get("tooltip_template"),
            pinnable=selector_tool.get("pinnable", True),
        )

        def update_selector_button_text(btn=btn):
            if not wutil.is_valid_widget(btn):
                return
            num_selected = selection_targets.get_selected_object_count()
            btn.setCount(num_selected)

        try:
            self._runtime_manager.selection_changed.connect(update_selector_button_text)
        except Exception:
            pass
        update_selector_button_text()
        return btn

    def _create_animation_offset_widget(self, sec, item_data):
        tool = toolbox.get_tool("animation_offset")
        btn = cw.create_tool_button_from_data(tool)
        btn.setObjectName("anim_offset_button")
        btn.setCheckable(True)
        btn.setChecked(bool(self.toggleAnimOffsetButtonState))
        self.animation_offset_button_widget = btn
        sec.addWidget(
            btn,
            tool.get("label", "Anim Offset"),
            tool.get("key", "animation_offset"),
            tooltip_template=tool.get("tooltip_template"),
        )
        return btn

    def _create_micro_move_widget(self, sec, item_data):
        tool = toolbox.get_tool("micro_move")
        btn = cw.create_tool_button_from_data(tool)
        btn.setObjectName("micro_move_button")
        btn.setCheckable(True)
        btn.setChecked(self.micro_move_controller.is_enabled())
        sec.addWidget(
            btn,
            tool.get("label", "Micro Move"),
            tool.get("key", "micro_move"),
            tooltip_template=tool.get("tooltip_template"),
        )
        return btn

    def _create_setting_toggle_widget(self, sec, item_data, spec_key):
        specs = self._settings_toggle_specs()
        spec = specs.get(spec_key)
        if not spec:
            return None

        # Build descriptor bridging specs to tool buttons
        data = {
            "key": spec["key"],
            "label": spec["label"],
            "text": spec.get("text"),
            "icon": spec.get("icon"),
            "description": spec.get("description", ""),
            "checkable": True,
            "set_checked_fn": spec["get_checked"],
            "bind_checked_fn": lambda widget, s=spec: self._bind_setting_toggle(widget, s),
            "callback": spec["set_checked"],
        }

        btn = cw.create_tool_button_from_data(data)
        sec.addWidget(btn, data["label"], data["key"], default=item_data.get("default", True))
        return btn

    def _create_toolbar_widget_from_data(self, sec, item):
        widget_key = item.get("key") or item.get("id")
        factory_name = f"_create_{widget_key}_widget"
        if hasattr(self, factory_name):
            return getattr(self, factory_name)(sec, item)
        else:
            return self._create_setting_toggle_widget(sec, item, widget_key)
        return None

    def _add_group_items(self, sec, items):
        group_tools = [item for item in items if not (isinstance(item, dict) and item.get("type") == "widget")]
        if group_tools:
            sec.addWidgetGroup(group_tools)

        for group_item in items:
            if isinstance(group_item, dict) and group_item.get("type") == "widget":
                self._create_toolbar_widget_from_data(sec, group_item)

    def _create_link_tools_group(self, sec, group_data):
        self.link_checkbox_state = settings.get_setting("link_checkbox_state", False)
        self.link_obj_toggle_state = False
        link_btn_placeholder = []

        def pulse_link_obj_button(btn):
            if not isValid(self):
                return
            self.link_obj_toggle_state = not self.link_obj_toggle_state
            new_image = media.link_objects_on_image if self.link_obj_toggle_state else media.link_objects_image
            btn.setIcon(QtGui.QIcon(new_image))

        def start_link_obj_pulse(btn):
            if hasattr(self, "link_obj_pulse_thread") and self.link_obj_pulse_thread:
                try:
                    self.link_obj_pulse_thread.stop()
                    self.link_obj_pulse_thread.wait(500)
                except Exception:
                    pass
            self.link_obj_pulse_thread = LinkObjectPulseThread(interval_seconds=0.3, parent=self)
            self.link_obj_pulse_thread.tick.connect(partial(pulse_link_obj_button, btn))
            self.link_obj_pulse_thread.start()

        def stop_link_obj_pulse():
            if hasattr(self, "link_obj_pulse_thread") and self.link_obj_pulse_thread:
                try:
                    self.link_obj_pulse_thread.stop()
                    self.link_obj_pulse_thread.wait(500)
                except Exception:
                    pass
                self.link_obj_pulse_thread = None

        def toggle_auto_link_callback(state, btn):
            self.link_checkbox_state = state
            settings.set_setting("link_checkbox_state", self.link_checkbox_state)
            if self.link_checkbox_state:
                start_link_obj_pulse(btn)
                keyTools.add_link_obj_callbacks()
            else:
                stop_link_obj_pulse()
                keyTools.remove_link_obj_callbacks()
                QtCore.QTimer.singleShot(800, lambda: btn.setIcon(QtGui.QIcon(media.link_objects_image)))

        resolved_items = []
        for item in group_data["items"]:
            if isinstance(item, dict):
                if item.get("key") == "link_autolink":
                    item["callback"] = lambda state: toggle_auto_link_callback(state, link_btn_placeholder[0])
                    item["set_checked_fn"] = lambda: self.link_checkbox_state
            resolved_items.append(item)

        btn_group = sec.addWidgetGroup(resolved_items)
        if btn_group:
            link_btn_placeholder.append(btn_group)
            if self.link_checkbox_state:
                start_link_obj_pulse(btn_group)
                keyTools.add_link_obj_callbacks()
        return btn_group

    def _populate_toolbar_from_layout(self, layout_id, new_section_fn):
        sections = toolbox.get_toolbar_sections(layout_id, resolve_items=False)
        for section_def in sections:
            sec_id = section_def["id"]
            sec_color = section_def.get("color")
            sec_hiddeable = section_def.get("hiddeable", True)

            if section_def.get("type") == "slider":
                self._add_slider_section_from_data(section_def, new_section_fn)
                continue

            sec = new_section_fn(color=sec_color, hiddeable=sec_hiddeable)
            resolved_section = toolbox.get_tool_section(sec_id)
            for item in resolved_section["items"]:
                if item == "separator":
                    sec.addSeparator()
                    continue

                if isinstance(item, dict):
                    if item.get("type") == "group":
                        if item.get("label") == "Links":
                            self._create_link_tools_group(sec, item)
                        else:
                            self._add_group_items(sec, item["items"])
                        continue

                    if item.get("type") == "widget":
                        self._create_toolbar_widget_from_data(sec, item)
                        continue

                    # Special tool overrides
                    if item.get("id") == "selector" or item.get("key") == "selector":
                        self._create_selector_widget(sec, item)
                        continue
                    if item.get("key") == "animation_offset":
                        self._create_animation_offset_widget(sec, item)
                        continue
                    if item.get("key") == "micro_move":
                        self._create_micro_move_widget(sec, item)
                        continue
                    if item.get("key") == "orbit":
                        self.orbit_button_widget = cw.create_tool_button_from_data(item, callback=None)
                        sec.addWidget(self.orbit_button_widget, item["label"], item["key"])
                        ui.bind_orbit_toolbar_button(self.orbit_button_widget)
                        continue
                    if item.get("key") == "selection_sets":
                        ss_btn = cw.create_tool_button_from_data(item, callback=None)
                        sec.addWidget(ss_btn, item["label"], item["key"])
                        ui.bind_selection_sets_toolbar_button(ss_btn, controller=self.selection_sets_controller)
                        continue
                    if item.get("key") == "attribute_switcher":
                        as_btn = cw.create_tool_button_from_data(item, callback=None)
                        sec.addWidget(as_btn, item["label"], item["key"])
                        ui.bind_attribute_switcher_toolbar_button(as_btn)
                        continue
                    if item.get("key") == "custom_graph":
                        self._create_setting_toggle_widget(sec, item, "custom_graph")
                        continue
                    if item.get("key") == "settings":
                        self._add_settings_button(sec, item)
                        continue

                    # Default tool
                    btn = cw.create_tool_button_from_data(item)
                    sec.addWidget(
                        btn,
                        item.get("label", ""),
                        item.get("key", ""),
                        default=item.get("default", True),
                        pinnable=item.get("pinnable", True),
                    )

    def _add_slider_section_from_data(self, section_def, new_section_fn):
        sec = new_section_fn()
        sec.set_settings_namespace("main_toolbar_sliders")
        sec.set_persist_slider_modes(False)

        prefix = section_def["slider_type"]
        color = section_def["color"]
        modes = getattr(sliders, section_def["modes_attr"])
        default_modes = section_def.get("default_modes", [])
        static_default_keys = [f"{prefix}_{k}" for k in default_modes]

        for m in modes:
            if m == "separator":
                sec.addSeparator()
                continue
            if not isinstance(m, dict):
                continue

            key = m["key"]
            label = m["label"]
            desc = m.get("description", "")
            icon = m.get("icon", "SL")
            is_visible = settings.get_setting(
                f"pin_{prefix}_{key}", f"{prefix}_{key}" in static_default_keys, namespace="main_toolbar_sliders"
            )

            s = sw.QFlatSliderWidget(
                f"bar_{prefix}_{key}",
                min=-100,
                max=100,
                text=icon,
                color=color,
                dragCommand=lambda mode_key, v, p=prefix, session=None: trigger.execute_slider(p, mode_key, v, session=session),
                tooltipTitle=label,
                tooltipDescription=desc,
            )
            s.setModes(modes)
            s.setCurrentMode(key)

            def make_mode_setter(slider_instance):
                def setter(new_mode, temporary=False):
                    slider_instance.setCurrentMode(new_mode, temporary=temporary)
                    m_info = next((item for item in modes if isinstance(item, dict) and item["key"] == new_mode), None)
                    if m_info:
                        slider_instance.setTooltipInfo(m_info["label"], m_info.get("description", ""))
                    if not temporary:
                        slider_instance.startFlash()

                return setter

            s.modeRequested.connect(make_mode_setter(s))
            sec.addWidget(s, label, f"{prefix}_{key}", default=is_visible, description=desc)

        sec.add_final_actions(static_default_keys)

        if prefix == "blend":
            self.blend_slider_widget = s  # Keep last as ref if needed? No, this adds all.
            # Actually we might want a specific slider widget reference.
        elif prefix == "tween":
            self.tween_slider_widget = s

    def _get_current_icon_alignment(self):
        alignment_name = settings.get_setting("toolbar_icon_alignment", "Center")
        alignments = {"Left": QtCore.Qt.AlignLeft, "Center": QtCore.Qt.AlignHCenter, "Right": QtCore.Qt.AlignRight}
        return alignments.get(alignment_name, QtCore.Qt.AlignHCenter)

    def _add_settings_button(self, sec, item):
        show_tooltips = settings.get_setting("show_tooltips", True)
        alignments = {"Left": QtCore.Qt.AlignLeft, "Center": QtCore.Qt.AlignHCenter, "Right": QtCore.Qt.AlignRight}
        toolbar_alignment = self._get_current_icon_alignment()
        INTERNET_CONNECTION = general.config.get("INTERNET_CONNECTION", True)

        def update_show_tooltips(value):
            settings.set_setting("show_tooltips", value)
            QFlatTooltipManager.enabled = value

        def update_toolbar_icon_alignment(alignment_name):
            settings.set_setting("toolbar_icon_alignment", alignment_name)
            # self.buildUI()

        def _build_settings_menu(_menu, source_widget=None):
            return toolMenus.build_main_settings_menu(
                self,
                source_widget or btn,
                show_tooltips=show_tooltips,
                alignments=alignments,
                toolbar_alignment=toolbar_alignment,
                update_show_tooltips=update_show_tooltips,
                update_toolbar_icon_alignment=update_toolbar_icon_alignment,
                internet_connection=INTERNET_CONNECTION,
            )

        settings_tool = toolbox.get_tool("settings", menu=_build_settings_menu)
        btn = cw.create_tool_button_from_data(settings_tool)
        btn.setObjectName("settings_toolbar_button")
        sec.addWidget(btn, settings_tool.get("label", "Settings"), settings_tool.get("key", "settings"))

        def _open_menu_at_cursor():
            toolbar_menu = _build_settings_menu(None, source_widget=btn)
            toolbar_menu.popup(QtGui.QCursor.pos())

        def _on_toolbar_context_menu(pos):
            if self.main_toolbar_widget.childAt(pos):
                return
            _open_menu_at_cursor()

        self.main_toolbar_widget.setContextMenuPolicy(QtCore.Qt.CustomContextMenu)
        self.main_toolbar_widget.customContextMenuRequested.connect(_on_toolbar_context_menu)

        if INTERNET_CONNECTION:
            updater.check_for_updates(btn, warning=False, force=False)

    def buildUI(self):
        ### ______________________________________________________ TOOLBAR LAYOUT _____________________________________________________________________###

        if self.layout():
            QtWidgets.QWidget().setLayout(self.layout())

        self.setSizePolicy(QtWidgets.QSizePolicy.Preferred, QtWidgets.QSizePolicy.Minimum)
        self.main_layout = QtWidgets.QHBoxLayout(self)
        self.main_layout.setContentsMargins(0, 0, 0, 0)
        self.main_toolbar_widget = cw.QFlowContainer()
        self.main_layout.addWidget(self.main_toolbar_widget)

        # Use QFlowLayout to allow wrapping
        toolbar_alignment = self._get_current_icon_alignment()
        self.toolbar_layout = cw.QFlowLayout(self.main_toolbar_widget, margin=2, Wspacing=10, Hspacing=6, alignment=toolbar_alignment)

        def new_section(spacing=0, hiddeable=True, color=None):
            sec = cw.QFlatSectionWidget(
                spacing=spacing,
                hiddeable=hiddeable,
                settings_namespace="main_toolbar_toolbuttons",
                color=color,
            )
            self.toolbar_layout.addWidget(sec)
            return sec

        self._populate_toolbar_from_layout("main", new_section)


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
        if cmds.workspaceControl(WORKSPACE_CONTROL_NAME, q=True, exists=True):
            cmds.deleteUI(WORKSPACE_CONTROL_NAME, control=True)
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
        if cmds.workspaceControl(WORKSPACE_CONTROL_NAME, query=True, exists=True):
            vis_state = cmds.workspaceControl(WORKSPACE_CONTROL_NAME, query=True, visible=True)

            if vis_state:
                cmds.workspaceControl(WORKSPACE_CONTROL_NAME, edit=True, visible=False)
            else:
                cmds.workspaceControl(WORKSPACE_CONTROL_NAME, edit=True, restore=True)
            return
    except Exception:
        pass
    _toolbar_instance = toolbar()
    _toolbar_instance.showWindow()
