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

from TheKeyMachine.core.Qt import QtCompat, QtCore, QtWidgets  # type: ignore


from functools import partial

from importlib import import_module, reload

import TheKeyMachine.mods.settingsMod as settings  # type: ignore
import TheKeyMachine.mods.reportMod as report  # type: ignore
import TheKeyMachine.core.toolWidgets as toolWidgets  # type: ignore
import TheKeyMachine.core.runtimeManager as runtime  # type: ignore
import TheKeyMachine.tools.graph_toolbar.api as graphToolbarApi  # type: ignore
import TheKeyMachine.tools.isolate.api as isolateApi  # type: ignore

import TheKeyMachine.tools.selection_sets.api as selectionSetsApi  # type: ignore

from TheKeyMachine.widgets import customWidgets as cw  # type: ignore
from TheKeyMachine.widgets import util as wutil  # type: ignore

QT_WIDGET_SIZE_MAX = 16777215

# -----------------------------------------------------------------------------------------------------------------------------
#    It attempts to load the user_preferences. If this is a new installation, it won't exist and the file must be created     #
# -----------------------------------------------------------------------------------------------------------------------------
#                                          Creation of the toolbar and UI class                                               #
# -----------------------------------------------------------------------------------------------------------------------------


WORKSPACE_NAME = "k"
WORKSPACE_CONTROL_NAME = WORKSPACE_NAME + "WorkspaceControl"

DOCKING_ORIENTATIONS = {
    "top": "To Top",
    "bottom": "To Bottom",
}
DOCKING_AREAS = {
    "AttributeEditor": "Attribute Editor",
    "ChannelBoxLayerEditor": "Channel Box",
    "Outliner": "Outliner",
    "MainPane": "Main Viewport",
    "TimeSlider": "Time Slider",
    "RangeSlider": "Range Slider",
    "Shelf": "Shelf",
}


class toolbar(MayaQWidgetDockableMixin, QtWidgets.QDialog):
    def __init__(self, parent=None):
        super().__init__(parent=parent)

        # Start the manager while this widget is still unmarked so its orphan
        # sweep only removes leftovers from earlier sessions.
        self._runtime_manager = runtime.get_runtime_manager()

        self.setWindowTitle("TheKeyMachine")
        self.setObjectName(WORKSPACE_NAME)
        self.setProperty("tkm_floating_widget", True)
        self.setContextMenuPolicy(QtCore.Qt.PreventContextMenu)
        self.selection_sets_controller = selectionSetsApi.get_controller(owner=self)

        report.install_bug_exception_handler()
        graphToolbarApi.sync_graph_toolbar_watch()
        self._runtime_manager.scene_opened.connect(self._on_scene_opened)
        self._runtime_manager.scene_new.connect(self._on_scene_opened)
        self._runtime_manager.graph_editor_opened.connect(self._on_graph_editor_opened)

        self.tabbar_painter = None
        self._height_update_pending = False
        self.current_layout = cmds.workspaceLayoutManager(q=True, current=True)

        # Initial state variables from settingsMod
        self.orbit_button_widget = None

        self.docking_position = settings.get_setting("docking_position", ["TimeSlider", "top"])
        self.docking_orients = dict(DOCKING_ORIENTATIONS)
        self.docking_layouts = dict(DOCKING_AREAS)

        self.setgroup_states = {}
        self.setgroup_buttons = {}

        self.buildUI()

        # Reconcile Graph Editor state at startup; ongoing tracking uses the event filter.
        QtCore.QTimer.singleShot(0, self._sync_graph_editor_on_startup)

    def closeEvent(self, event):
        """
        Handles the close event for the toolbar window.
        Stops all background threads and performs necessary cleanup.
        """
        global _toolbar_instance
        owns_runtime = _toolbar_instance is self
        if owns_runtime:
            _toolbar_instance = None
            try:
                runtime.shutdown_runtime_manager(cleanup_widgets=False)
            except TypeError:
                # Supports the first hot reload from a runtimeManager module
                # loaded before cleanup_widgets was introduced.
                runtime.shutdown_runtime_manager()
            except (RuntimeError, ValueError, AttributeError, KeyError, IndexError):
                pass

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
        isolateApi.update_isolate_popup_menu()

    def _on_graph_editor_opened(self, *_args):
        if not QtCompat.isValid(self):
            return
        if not settings.get_setting("graph_toolbar_enabled", True):
            return
        # ensure() reuses an already-valid toolbar instead of tearing it down
        # and rebuilding every section from scratch -- this and
        # _sync_graph_editor_on_startup() can both fire for the same
        # already-open Graph Editor during the same startup window.
        QtCore.QTimer.singleShot(0, graphToolbarApi.ensure)

    def _sync_graph_editor_on_startup(self):
        if not QtCompat.isValid(self):
            return
        if not settings.get_setting("graph_toolbar_enabled", True):
            return

        graph_vis = cmds.getPanel(vis=True) or []
        if "graphEditor1" in graph_vis:
            QtCore.QTimer.singleShot(0, graphToolbarApi.ensure)

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
        if not self.ensure_shelf_painter():
            cmds.evalDeferred(self.ensure_shelf_painter, lowestPriority=True)
        QtCore.QTimer.singleShot(500, self.update_height)

    def visible_change_command(self, *args):
        if not QtCompat.isValid(self):
            return

        if not self.isDockable():
            return
        if not cmds.workspaceControl(
            WORKSPACE_CONTROL_NAME, query=True, visible=True
        ):
            self._delete_tabbar_painter()
            return
        if self.current_layout != cmds.workspaceLayoutManager(q=1, current=True):
            self.current_layout = cmds.workspaceLayoutManager(q=1, current=True)
            if not self.isVisible():
                if QtCompat.isValid(self):
                    cmds.evalDeferred(show, lowestPriority=True)

                if self.tabbar_painter and QtCompat.isValid(self.tabbar_painter):
                    self.tabbar_painter.show()
                else:
                    cmds.evalDeferred(
                        self.ensure_shelf_painter, lowestPriority=True
                    )
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
                cmds.evalDeferred(
                    self.ensure_shelf_painter, lowestPriority=True
                )
        else:
            if self.tabbar_painter and QtCompat.isValid(self.tabbar_painter):
                self.tabbar_painter.hide()

        self.update_height()

    def ensure_shelf_painter(self):
        if not QtCompat.isValid(self):
            return False

        if self.tabbar_painter and QtCompat.isValid(self.tabbar_painter):
            self.tabbar_painter.show()
            self.tabbar_painter.syncGeometry()
            return True

        qctrl = mui.MQtUtil.findControl(WORKSPACE_CONTROL_NAME)
        if not qctrl:
            return False
        control = wutil.get_maya_qt(qctrl)
        if control is None or not QtCompat.isValid(control):
            return False
        control_parent = control.parent()
        tab_handle = control_parent.parent() if control_parent else None
        if tab_handle is None or not QtCompat.isValid(tab_handle):
            return False

        control.setSizePolicy(QtWidgets.QSizePolicy.Minimum, QtWidgets.QSizePolicy.Minimum)

        tab_bar = tab_handle.tabBar()
        if self.isFloating():
            tab_bar.setVisible(False)
            return False

        # Temporary tab-bar experiment: paint the shelf treatment directly on
        # Maya's tab bar instead of creating the full-height shelf overlay.
        tab_bar.setVisible(True)
        tab_bar.setFixedHeight(wutil.DPI(1000))

        self.tabbar_painter = cw.QFlatTabBarPainter(tab_bar, tab_handle)
        return True

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
        current_layout, current_orient = self.docking_position
        layout = layout or current_layout
        orient = orient or current_orient

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
            self._sync_dock_action_groups()

        # Make the workspaceControl call just once
        cmds.workspaceControl(WORKSPACE_CONTROL_NAME, **kwargs)

    def _sync_dock_action_groups(self):
        """Keep toolbar-owned groups aligned with docking from any menu."""
        current_layout, current_orient = self.docking_position
        targets = (
            (
                getattr(self, "pos_ac_group", None),
                self.docking_orients,
                current_orient,
            ),
            (
                getattr(self, "dock_ac_group", None),
                self.docking_layouts,
                current_layout,
            ),
        )
        for group, labels, current_value in targets:
            if group is None:
                continue
            current_label = labels[current_value]
            for action in group.actions():
                if action and QtCompat.isValid(action):
                    is_current = action.text() == current_label
                    action.setChecked(is_current)
                    action.setEnabled(not is_current)

    # For use with toggle functionality on Shelf or Launcher
    def toggle(self, *args):
        self.showWindow()

    def reload(self, *args):
        global _toolbar_instance
        toolbar_module_name = "TheKeyMachine.core.toolbar"
        graph_toolbar_widgets_name = "TheKeyMachine.tools.graph_toolbar.widgets"

        # A delayed closeEvent from this widget must not clear or shut down the
        # replacement toolbar after the module dictionary has been reloaded.
        if _toolbar_instance is self:
            _toolbar_instance = None

        try:
            runtime.cleanup_for_reload(delete_workspace=True, process_events=True)
        except (RuntimeError, ValueError, TypeError, AttributeError, KeyError, IndexError):
            pass

        # Importa el módulo y recarga
        toolbar_module = import_module(toolbar_module_name)
        graph_toolbar_widgets = import_module(graph_toolbar_widgets_name)

        reload(toolbar_module)
        reload(graph_toolbar_widgets)

        # Cleanup was completed and flushed above. Running it again here can
        # queue deletion of the newly hosted workspace-control child.
        toolbar_module.show(cleanup_existing=False)

    def unload(self, *args):
        """
        Closes the tool and removes callbacks (safe to call multiple times).
        """
        global _toolbar_instance
        _toolbar_instance = None

        try:
            runtime.cleanup_for_reload(delete_workspace=True, process_events=True)
        except (RuntimeError, ValueError, TypeError, AttributeError, KeyError, IndexError):
            pass

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
        toolWidgets.bind_toolbar_pinning_context(self.main_toolbar_widget, parent_widget=self)

        # Extract TKM button to a separate layout to the left
        import TheKeyMachine.core.toolbox as toolbox
        tkm_tool = toolbox.get_tool("TKM")
        self.tkm_btn = cw.create_tool_button_from_data(tkm_tool)
        self.tkm_btn.setObjectName("TKM_toolbar_button")

        self.tkm_layout = QtWidgets.QVBoxLayout()
        self.tkm_layout.setContentsMargins(0, 6, 0, 0)
        self.tkm_layout.addWidget(self.tkm_btn)
        self.tkm_layout.addStretch()
        self.main_layout.insertLayout(0, self.tkm_layout)

        # This button lives outside every section (it's pulled into its own
        # layout above, not added via toolWidgets.add_tool_button), so it
        # isn't reached by _bind_toolbar_translation_refresh's per-section
        # loop -- refresh it directly the same way, through the same
        # lang.json-backed lookup every other translated button uses.
        from TheKeyMachine.core import i18n
        from TheKeyMachine.tools import common as toolCommon

        def _on_tkm_button_language_changed(*_args, button=self.tkm_btn):
            cw.refresh_tool_button_translation(button, "TKM")

        toolCommon.replace_tracked_connection(
            self.tkm_btn,
            "_tkm_button_translation_connection",
            i18n.bus.languageChanged,
            _on_tkm_button_language_changed,
            parent=self.tkm_btn,
        )



_toolbar_instance = None


def get_toolbar():
    global _toolbar_instance
    if _toolbar_instance is not None:
        try:
            if not QtCompat.isValid(_toolbar_instance):
                _toolbar_instance = None
        except (RuntimeError, TypeError):
            _toolbar_instance = None
    return _toolbar_instance


def show(cleanup_existing=True):
    global _toolbar_instance

    if cleanup_existing:
        try:
            runtime.cleanup_for_reload(delete_workspace=True, process_events=True)
        except (RuntimeError, ValueError, TypeError, AttributeError, KeyError, IndexError):
            pass

    instance = toolbar()
    _toolbar_instance = instance
    try:
        instance.showWindow()
    except Exception:
        if _toolbar_instance is instance:
            _toolbar_instance = None
        try:
            instance.close()
            instance.deleteLater()
            runtime.cleanup_workspace_controls(process_events=True)
        except Exception:
            pass
        raise
    return instance


def toggle():
    toolbar_instance = get_toolbar()
    try:
        if toolbar_instance is not None and cmds.workspaceControl(WORKSPACE_CONTROL_NAME, query=True, exists=True):
            vis_state = cmds.workspaceControl(WORKSPACE_CONTROL_NAME, query=True, visible=True)

            if vis_state:
                toolbar_instance._delete_tabbar_painter()
                cmds.workspaceControl(WORKSPACE_CONTROL_NAME, edit=True, visible=False)
                return False
            else:
                cmds.workspaceControl(WORKSPACE_CONTROL_NAME, edit=True, restore=True)
                if not toolbar_instance.ensure_shelf_painter():
                    cmds.evalDeferred(
                        toolbar_instance.ensure_shelf_painter,
                        lowestPriority=True,
                    )
                return True
    except (RuntimeError, ValueError, TypeError, AttributeError, KeyError, IndexError):
        pass
    show()
    return True


def welcome():
    show()

    def _show_welcome_prompt():
        toolbar_instance = get_toolbar()
        if not toolbar_instance or not QtCompat.isValid(toolbar_instance):
            return
        anchor = toolbar_instance.findChild(QtWidgets.QWidget, "TKM_toolbar_button")
        if not wutil.is_valid_widget(anchor):
            return
        toolWidgets.show_welcome_shelf_prompt(anchor)

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
