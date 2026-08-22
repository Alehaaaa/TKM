"""

TheKeyMachine - Animation Toolset for Maya Animators


This file is part of TheKeyMachine, an open source software for Autodesk Maya licensed under the GNU General Public License v3.0 (GPL-3.0).
You are free to use, modify, and distribute this code under the terms of the GPL-3.0 license.
By using this code, you agree to keep it open source and share any modifications.
This code is provided "as is," without any warranty. For the full license text, visit https://www.gnu.org/licenses/gpl-3.0.html

https://alehaaaa.github.io/TKM/

Developed by: Rodrigo Torres / rodritorres.com
Modified by: Alehaaaa / alehaaaa.github.io



"""

# Maya related imports
from maya import cmds, mel, OpenMayaUI as mui
from maya.app.general.mayaMixin import MayaQWidgetDockableMixin  # type: ignore

from TheKeyMachine.core.Qt import QtCompat, QtCore, QtWidgets  # type: ignore


from TheKeyMachine.core import settings  # type: ignore
import TheKeyMachine.tools.bug_report.controller as report  # type: ignore
from TheKeyMachine.ui.widgets import toolbar_widgets  # type: ignore
from TheKeyMachine.ui import toolbar_modes  # type: ignore
from TheKeyMachine.core import runtime  # type: ignore
from TheKeyMachine.tools.graph_toolbar import controller as graph_toolbar  # type: ignore
import TheKeyMachine.tools.isolate.api as isolateApi  # type: ignore

import TheKeyMachine.tools.selection_sets.api as selectionSetsApi  # type: ignore

from TheKeyMachine.ui.widgets import customWidgets as cw  # type: ignore
from TheKeyMachine.ui.widgets import util as wutil  # type: ignore

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
DEFAULT_DOCKING_POSITION = ("TimeSlider", "top")


def _normalize_docking_position(value):
    try:
        layout, area = value
    except (TypeError, ValueError):
        return list(DEFAULT_DOCKING_POSITION)
    if layout not in DOCKING_AREAS or area not in DOCKING_ORIENTATIONS:
        return list(DEFAULT_DOCKING_POSITION)
    return [layout, area]


class toolbar(MayaQWidgetDockableMixin, QtWidgets.QDialog):
    def __init__(self, parent=None):
        super().__init__(parent=parent)

        self._shutting_down = False
        self._graph_toolbar_sync_timer = QtCore.QTimer(self)
        self._graph_toolbar_sync_timer.setSingleShot(True)
        self._graph_toolbar_sync_timer.timeout.connect(self._sync_graph_toolbar)
        self._height_timer = QtCore.QTimer(self)
        self._height_timer.setSingleShot(True)
        self._height_timer.timeout.connect(self.update_height)
        self._dock_refresh_timer = QtCore.QTimer(self)
        self._dock_refresh_timer.setSingleShot(True)
        self._dock_refresh_timer.timeout.connect(self._refresh_dock_ui)
        self._dock_widget = None

        # Start the manager while this widget is still unmarked so its orphan
        # sweep only removes leftovers from earlier sessions.
        self._runtime_manager = runtime.get_runtime_manager()

        self.setWindowTitle("TheKeyMachine")
        self.setObjectName(WORKSPACE_NAME)
        self.setProperty("tkm_floating_widget", True)
        self.setContextMenuPolicy(QtCore.Qt.PreventContextMenu)
        self.selection_sets_controller = selectionSetsApi.get_controller(owner=self)

        report.install_bug_exception_handler()
        graph_toolbar.sync_graph_toolbar_watch()
        self._runtime_manager.scene_opened.connect(self._on_scene_opened)
        self._runtime_manager.scene_new.connect(self._on_scene_opened)
        self._runtime_manager.graph_editor_opened.connect(self._on_graph_editor_opened)

        self.tabbar_painter = None

        # Initial state variables from settings
        self.orbit_button_widget = None

        self.docking_position = _normalize_docking_position(
            settings.get_setting("docking_position", DEFAULT_DOCKING_POSITION)
        )
        self.docking_orients = dict(DOCKING_ORIENTATIONS)
        self.docking_layouts = dict(DOCKING_AREAS)

        self.setgroup_states = {}
        self.setgroup_buttons = {}

        self.buildUI()

        # Reconcile Graph Editor state at startup; ongoing tracking uses the event filter.
        self._schedule_graph_toolbar_sync()

    def closeEvent(self, event):
        """
        Handles the close event for the toolbar window.
        Stops all background threads and performs necessary cleanup.
        """
        global _toolbar_instance
        self._begin_shutdown()
        owns_runtime = _toolbar_instance is self
        if owns_runtime:
            _toolbar_instance = None
            try:
                runtime.shutdown_runtime_manager(cleanup_widgets=False)
            except (RuntimeError, ValueError, AttributeError, KeyError, IndexError):
                pass

        self._delete_tabbar_painter()

        super().closeEvent(event)

    def _delete_tabbar_painter(self):
        if self.tabbar_painter and QtCompat.isValid(self.tabbar_painter):
            runtime.delete_widget(self.tabbar_painter)
        self.tabbar_painter = None

    def _begin_shutdown(self):
        if self._shutting_down:
            return
        self._shutting_down = True
        try:
            self._graph_toolbar_sync_timer.stop()
            self._height_timer.stop()
            self._dock_refresh_timer.stop()
        except (RuntimeError, ValueError, TypeError, AttributeError, KeyError, IndexError):
            pass

    def _is_active(self):
        return not self._shutting_down and QtCompat.isValid(self)

    def _on_scene_opened(self, *_args):
        if not self._is_active():
            return
        isolateApi.update_isolate_popup_menu()

    def _on_graph_editor_opened(self, *_args):
        if not self._is_active():
            return
        self._schedule_graph_toolbar_sync()

    def _schedule_graph_toolbar_sync(self):
        if not self._is_active() or self._graph_toolbar_sync_timer.isActive():
            return
        self._graph_toolbar_sync_timer.start(0)

    def _sync_graph_toolbar(self):
        if not self._is_active():
            return
        if not settings.get_setting("graph_toolbar_enabled", True):
            return

        graph_vis = cmds.getPanel(vis=True) or []
        if "graphEditor1" in graph_vis:
            graph_toolbar.ensure()

    def showWindow(self):
        if not self._is_active():
            return False

        if not self.isDockable():
            self._parent_to_dock_target()
            _layout, area = self.docking_position
            self.show(
                dockable=True,
                floating=False,
                area=area,
                retain=False,
            )
            if not self.isDockable():
                raise RuntimeError("Maya did not create the toolbar workspace control")
        else:
            self.show()

        self._bind_dock_events()
        self._queue_dock_refresh()
        self._height_timer.start(500)
        return True

    def showEvent(self, event):
        super().showEvent(event)
        if self._is_active():
            self._height_timer.start(0)

    def hideEvent(self, event):
        self._delete_tabbar_painter()
        super().hideEvent(event)

    def _bind_dock_events(self):
        dock_widget = self.parentWidget()
        if dock_widget is None or dock_widget is self._dock_widget:
            return
        self._dock_widget = dock_widget

        for signal_name in ("visibilityChanged", "topLevelChanged"):
            signal = getattr(dock_widget, signal_name, None)
            if signal is not None:
                signal.connect(self._queue_dock_refresh)

    def _queue_dock_refresh(self, *_args):
        if self._is_active():
            self._dock_refresh_timer.start(0)

    def _refresh_dock_ui(self):
        if not self._is_active() or not self.isVisible() or self.isFloating():
            self._delete_tabbar_painter()
            return
        self.ensure_shelf_painter()
        self._height_timer.start(0)

    def ensure_shelf_painter(self):
        if not self._is_active():
            return False

        if self.tabbar_painter and QtCompat.isValid(self.tabbar_painter):
            self.tabbar_painter.show()
            self.tabbar_painter.sync_geometry()
            return True

        qctrl = mui.MQtUtil.findControl(WORKSPACE_CONTROL_NAME)
        if not qctrl:
            return False
        control = wutil.get_maya_qt(qctrl, QtWidgets.QWidget)
        if control is None or not QtCompat.isValid(control):
            return False

        try:
            tab_handle = control.parentWidget()
            while tab_handle is not None and not isinstance(tab_handle, QtWidgets.QTabWidget):
                tab_handle = tab_handle.parentWidget()
            if tab_handle is None or not QtCompat.isValid(tab_handle):
                return False

            control.setSizePolicy(QtWidgets.QSizePolicy.Minimum, QtWidgets.QSizePolicy.Minimum)
            if tab_handle.tabPosition() != QtWidgets.QTabWidget.West:
                tab_handle.setTabPosition(QtWidgets.QTabWidget.West)
                self._queue_dock_refresh()
                return False
            tab_bar = tab_handle.tabBar()
            if self.isFloating():
                tab_bar.setVisible(False)
                return False

            tab_bar.setVisible(True)
            tab_bar.setFixedHeight(wutil.DPI(1000))
            self.tabbar_painter = cw.QFlatTabBarPainter(tab_bar, tab_handle)
            return True
        except RuntimeError:
            return False

    def update_height(self):
        if not self._is_active():
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
                self.tabbar_painter.sync_geometry()
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
        if self._is_active():
            self._height_timer.start(0)

    def resizeEvent(self, event):
        super().resizeEvent(event)
        # Trigger height update when internal width changes (wrapping happens)
        self.update_height()

    @staticmethod
    def _dock_target_name(layout):
        component_names = {
            "TimeSlider": "Time Slider",
            "RangeSlider": "Range Slider",
            "Shelf": "Shelf",
        }
        component = component_names.get(layout)
        if component:
            return mel.eval('getUIComponentToolBar("{}", false)'.format(component))
        return layout

    def _parent_to_dock_target(self):
        target_name = self._dock_target_name(self.docking_position[0])
        target_pointer = mui.MQtUtil.findControl(target_name)
        if not target_pointer:
            raise RuntimeError("Maya docking target is unavailable: {}".format(target_name))
        target = wutil.get_maya_qt(target_pointer, QtWidgets.QWidget)
        if target is None or not QtCompat.isValid(target):
            raise RuntimeError("Maya docking target is invalid: {}".format(target_name))

        dock_parent = next(
            (child for child in target.findChildren(QtWidgets.QWidget) if not child.objectName()),
            None,
        )
        if dock_parent is None:
            raise RuntimeError("Maya docking target has no content: {}".format(target_name))
        self.setParent(dock_parent)

    def dock_to_ui(self, layout=None, orient=None):
        current_layout, current_orient = self.docking_position
        layout = layout or current_layout
        orient = orient or current_orient
        if layout not in DOCKING_AREAS or orient not in DOCKING_ORIENTATIONS:
            return False
        if not wutil.check_visible_layout(layout):
            return False

        self._delete_tabbar_painter()
        cmds.workspaceControl(
            WORKSPACE_CONTROL_NAME,
            edit=True,
            dockToControl=(self._dock_target_name(layout), orient),
            tabPosition=("west", 0),
            resizeWidth=900,
            resizeHeight=40,
        )

        self.docking_position = [layout, orient]
        settings.set_setting("docking_position", self.docking_position)
        self._sync_dock_action_groups()
        self._queue_dock_refresh()
        return True

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
        import TheKeyMachine

        return TheKeyMachine.reload()

    def unload(self, *args):
        """
        Closes the tool and removes callbacks (safe to call multiple times).
        """
        global _toolbar_instance
        self._begin_shutdown()
        _toolbar_instance = None

        try:
            runtime.cleanup_for_reload(delete_workspace=True, process_events=True)
        except (RuntimeError, ValueError, TypeError, AttributeError, KeyError, IndexError):
            pass

    def buildUI(self):
        ### ______________________________________________________ TOOLBAR LAYOUT _____________________________________________________________________###

        if self.layout():
            QtWidgets.QWidget().setLayout(self.layout())

        self.setSizePolicy(QtWidgets.QSizePolicy.Preferred, QtWidgets.QSizePolicy.Minimum)
        self.main_layout = QtWidgets.QHBoxLayout(self)
        self.main_layout.setContentsMargins(0, 0, 0, 0)

        toolbar_alignment = toolbar_widgets.get_main_toolbar_icon_alignment()
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

        toolbar_widgets.populate_main_toolbar_from_layout("main", new_section, self)
        toolbar_widgets.bind_toolbar_pinning_context(self.main_toolbar_widget, parent_widget=self)
        self.main_toolbar_widget.set_single_line(
            toolbar_modes.is_single_line(
                settings.get_setting(
                    toolbar_modes.MAIN_ALIGNMENT_SETTING,
                    toolbar_modes.DEFAULT_ALIGNMENT,
                )
            )
        )

        # Extract TKM button to a separate layout to the left
        from TheKeyMachine.tools import registry
        tkm_tool = registry.get_tool("TKM")
        self.tkm_btn = cw.create_tool_button_from_data(tkm_tool)
        self.tkm_btn.setObjectName("TKM_toolbar_button")

        self.tkm_layout = QtWidgets.QVBoxLayout()
        self.tkm_layout.setContentsMargins(0, 6, 0, 0)
        self.tkm_layout.addWidget(self.tkm_btn)
        self.tkm_layout.addStretch()
        self.main_layout.insertLayout(0, self.tkm_layout)

        # This button lives outside every section (it's pulled into its own
        # layout above, not added via toolbar_widgets.add_tool_button), so it
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
            if not QtCompat.isValid(_toolbar_instance) or getattr(_toolbar_instance, "_shutting_down", False):
                _toolbar_instance = None
        except (RuntimeError, TypeError):
            _toolbar_instance = None
    return _toolbar_instance


def _workspace_control_exists():
    return mui.MQtUtil.findControl(WORKSPACE_CONTROL_NAME) is not None


def _needs_pre_show_cleanup():
    return (
        _workspace_control_exists()
        or runtime.has_previous_runtime()
        or runtime.has_persisted_callback_state()
    )


def show(cleanup_existing=True):
    global _toolbar_instance

    existing = get_toolbar()
    if existing is not None:
        if existing.isVisible():
            return existing
        try:
            if existing.showWindow():
                return existing
        except (RuntimeError, ValueError, TypeError, AttributeError, KeyError, IndexError):
            pass
        if _toolbar_instance is existing:
            _toolbar_instance = None
        try:
            existing._begin_shutdown()
            runtime.cleanup_for_reload(delete_workspace=True, process_events=True)
        except (RuntimeError, ValueError, TypeError, AttributeError, KeyError, IndexError):
            pass
        else:
            cleanup_existing = False

    if cleanup_existing and _needs_pre_show_cleanup():
        try:
            runtime.cleanup_for_reload(delete_workspace=True, process_events=True)
        except (RuntimeError, ValueError, TypeError, AttributeError, KeyError, IndexError):
            pass

    instance = None
    try:
        instance = toolbar()
        _toolbar_instance = instance
        instance.showWindow()
    except Exception:
        if _toolbar_instance is instance:
            _toolbar_instance = None
        try:
            if instance is not None:
                instance._begin_shutdown()
                instance.close()
                instance.deleteLater()
            runtime.cleanup_for_reload(delete_workspace=True, process_events=True)
        except Exception:
            pass
        raise
    return instance


def unload(*_args):
    toolbar_instance = get_toolbar()
    if toolbar_instance is not None:
        return toolbar_instance.unload()
    return runtime.cleanup_for_reload(delete_workspace=True, process_events=True)


def toggle():
    toolbar_instance = get_toolbar()
    try:
        if toolbar_instance is not None:
            if toolbar_instance.isVisible():
                toolbar_instance.hide()
                return False
            toolbar_instance.showWindow()
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
        toolbar_widgets.show_welcome_shelf_prompt(anchor)

    QtCore.QTimer.singleShot(700, _show_welcome_prompt)
