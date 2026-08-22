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

from maya import cmds # type: ignore

from TheKeyMachine.core.Qt import QtCore, QtWidgets  # type: ignore


# -----------------------------------------------------------------------------------------------------------------------------
#                                             Loading necessary modules from TheKeyMachine                                    #
# -----------------------------------------------------------------------------------------------------------------------------

from TheKeyMachine.ui.widgets import toolbar_menus
from TheKeyMachine.ui.widgets import toolbar_widgets
from TheKeyMachine.ui import toolbar_modes

from TheKeyMachine.ui.widgets import customWidgets as cw  # type: ignore
from TheKeyMachine.ui.widgets import util as wutil  # type: ignore
from TheKeyMachine.core import runtime, settings  # type: ignore
import TheKeyMachine.tools.graph_toolbar.controller as graphToolbarController  # type: ignore


_GRAPH_TOOLBAR_OBJECT = "tkm_customGraph_flowToolbar"
_DOCK_POSITION_IDS = {position for position, _label, _description in graphToolbarController.DOCK_OPTIONS}

_GRAPH_TOOLBAR_WIDGET = None
_CREATE_RETRY_TIMER = None


def _graph_toolbar_alignment():
    align_str = settings.get_setting(
        toolbar_modes.GRAPH_ALIGNMENT_SETTING,
        toolbar_modes.DEFAULT_ALIGNMENT,
    )
    return toolbar_modes.alignment_value(align_str)


def _graph_editor_control_widget():
    return wutil.get_control_widget("graphEditor1")


def _layout_widgets(layout):
    widgets = []
    for index in range(layout.count()):
        item = layout.itemAt(index)
        widget = item.widget() if item else None
        if widget is not None:
            widgets.append(widget)
    return widgets


def _graph_editor_layout_host():
    """Return a box-layout host and the native graph content row it owns."""
    graph_control = _graph_editor_control_widget()
    if not graph_control:
        return None, None, None

    layout = graph_control.layout()
    if isinstance(layout, QtWidgets.QBoxLayout):
        native_widgets = [
            widget
            for widget in _layout_widgets(layout)
            if widget.objectName() != _GRAPH_TOOLBAR_OBJECT and not isinstance(widget, QtWidgets.QMenuBar)
        ]
        if native_widgets:
            return graph_control, layout, native_widgets[-1]

    descendant = graph_control
    parent = graph_control.parentWidget()
    while parent is not None:
        layout = parent.layout()
        if isinstance(layout, QtWidgets.QBoxLayout) and layout.indexOf(descendant) >= 0:
            return parent, layout, descendant
        descendant = parent
        parent = parent.parentWidget()
    return None, None, None


def _find_graph_editor_widget():
    host, _layout, _content = _graph_editor_layout_host()
    return host


def getCustomGraphWidget():
    global _GRAPH_TOOLBAR_WIDGET

    graph_qw = _find_graph_editor_widget()
    if not graph_qw:
        _GRAPH_TOOLBAR_WIDGET = None
        return None

    if (
        _GRAPH_TOOLBAR_WIDGET
        and wutil.is_valid_widget(_GRAPH_TOOLBAR_WIDGET)
        and _GRAPH_TOOLBAR_WIDGET.objectName() == _GRAPH_TOOLBAR_OBJECT
        and graph_qw.isAncestorOf(_GRAPH_TOOLBAR_WIDGET)
    ):
        return _GRAPH_TOOLBAR_WIDGET

    for toolbar_widget in graph_qw.findChildren(QtWidgets.QWidget, _GRAPH_TOOLBAR_OBJECT):
        if wutil.is_valid_widget(toolbar_widget) and not toolbar_widget.isHidden():
            _GRAPH_TOOLBAR_WIDGET = toolbar_widget
            return toolbar_widget

    _GRAPH_TOOLBAR_WIDGET = None
    return None


def removeCustomGraph() -> None:
    global _GRAPH_TOOLBAR_WIDGET
    _cancel_create_retry()
    graph_qw = _find_graph_editor_widget()
    if graph_qw:
        for toolbar_widget in graph_qw.findChildren(QtWidgets.QWidget, _GRAPH_TOOLBAR_OBJECT):
            if not wutil.is_valid_widget(toolbar_widget):
                continue
            runtime.delete_widget(toolbar_widget)
    _GRAPH_TOOLBAR_WIDGET = None
    graphToolbarController.emit_graph_toolbar_state()


def _cancel_create_retry():
    global _CREATE_RETRY_TIMER
    timer = _CREATE_RETRY_TIMER
    _CREATE_RETRY_TIMER = None
    if timer is None:
        return
    try:
        timer.stop()
        timer.deleteLater()
    except (RuntimeError, ValueError, TypeError, AttributeError, KeyError, IndexError):
        pass


def _schedule_create_retry(attempt):
    global _CREATE_RETRY_TIMER
    _cancel_create_retry()
    timer = QtCore.QTimer()
    timer.setSingleShot(True)

    def _retry():
        global _CREATE_RETRY_TIMER
        try:
            _CREATE_RETRY_TIMER = None
            createCustomGraph(force=True, _attempt=attempt)
        finally:
            timer.deleteLater()

    timer.timeout.connect(_retry)
    _CREATE_RETRY_TIMER = timer
    timer.start(100)

# -----------------------------------------------------------------------------------------------------------------------------
#                                                       customGraph build                                                     #
# -----------------------------------------------------------------------------------------------------------------------------


def _place_graph_toolbar_widget(toolbar_widget, dock_position=None):
    if dock_position is None:
        dock_position = settings.get_setting(graphToolbarController.GRAPH_TOOLBAR_DOCK_SETTING, graphToolbarController.DOCK_BOTTOM_GRAPH)
    if dock_position not in _DOCK_POSITION_IDS:
        dock_position = graphToolbarController.DOCK_BOTTOM_GRAPH

    host, graph_layout, graph_content = _graph_editor_layout_host()
    if not host or not graph_layout or not graph_content:
        return False

    parent = toolbar_widget.parentWidget()
    if parent and parent.layout():
        parent.layout().removeWidget(toolbar_widget)
    toolbar_widget.setParent(host)
    toolbar_widget.setSizePolicy(QtWidgets.QSizePolicy.Expanding, QtWidgets.QSizePolicy.Fixed)

    graph_index = graph_layout.indexOf(graph_content)
    if dock_position == graphToolbarController.DOCK_BOTTOM_MENU:
        menu_indices = [
            graph_layout.indexOf(widget)
            for widget in _layout_widgets(graph_layout)
            if isinstance(widget, QtWidgets.QMenuBar)
        ]
        insert_index = max(menu_indices) + 1 if menu_indices else max(0, graph_index)
    elif dock_position == graphToolbarController.DOCK_TOP_GRAPH:
        insert_index = max(0, graph_index)
    else:  # graphToolbarController.DOCK_BOTTOM_GRAPH
        insert_index = graph_index + 1

    graph_layout.insertWidget(insert_index, toolbar_widget)

    toolbar_widget.show()
    graph_layout.invalidate()
    graph_layout.activate()
    return True


def applyCustomGraphAlignment(alignment_label=None):
    if alignment_label:
        settings.set_setting(
            toolbar_modes.GRAPH_ALIGNMENT_SETTING,
            toolbar_modes.normalize(alignment_label),
        )

    toolbar_widget = getCustomGraphWidget()
    if not toolbar_widget:
        return False

    layout = toolbar_widget.layout()
    if not layout:
        return False

    try:
        current_alignment = settings.get_setting(
            toolbar_modes.GRAPH_ALIGNMENT_SETTING,
            toolbar_modes.DEFAULT_ALIGNMENT,
        )
        toolbar_modes.apply_to(toolbar_widget, current_alignment)
        return True
    except (RuntimeError, ValueError, TypeError, AttributeError, KeyError, IndexError):
        return False


def moveCustomGraphDock(position=None):
    settings.set_setting(graphToolbarController.GRAPH_TOOLBAR_DOCK_SETTING, position)
    toolbar_widget = getCustomGraphWidget()
    if toolbar_widget and wutil.is_valid_widget(toolbar_widget):
        if _place_graph_toolbar_widget(toolbar_widget, position):
            try:
                toolbar_widget._update_height()
            except (RuntimeError, ValueError, TypeError, AttributeError, KeyError, IndexError):
                pass
    else:
        createCustomGraph(force=True)


def ensureCustomGraph():
    if not settings.get_setting("graph_toolbar_enabled", True):
        removeCustomGraph()
        return None

    toolbar_widget = getCustomGraphWidget()
    if toolbar_widget and wutil.is_valid_widget(toolbar_widget):
        _place_graph_toolbar_widget(toolbar_widget)
        applyCustomGraphAlignment()
        return toolbar_widget

    createCustomGraph(force=True)
    return getCustomGraphWidget()


def createCustomGraph(*_args, force: bool = False, _attempt: int = 0, **_kwargs):
    global _GRAPH_TOOLBAR_WIDGET

    if not settings.get_setting("graph_toolbar_enabled", True):
        return removeCustomGraph()

    # Idempotency guard: more than one startup/panel-open trigger can land
    # here for the same already-open Graph Editor (the watch timer and the
    # toolbar's own startup sync both race to call this). Reuse an existing,
    # still-valid toolbar instead of tearing it down and rebuilding every
    # section from scratch -- the same outcome ensureCustomGraph() already
    # gets by checking first.
    existing = getCustomGraphWidget()
    if existing and wutil.is_valid_widget(existing):
        _place_graph_toolbar_widget(existing)
        applyCustomGraphAlignment()
        return existing

    graph_vis = cmds.getPanel(vis=True)
    if "graphEditor1" not in graph_vis:
        if not force:
            return

        if cmds.window("graphEditor1Window", exists=True):
            cmds.showWindow("graphEditor1Window")
        else:
            cmds.GraphEditor()

        graph_vis = cmds.getPanel(vis=True) or []
        if "graphEditor1" not in graph_vis:
            if _attempt < 5:
                _schedule_create_retry(_attempt + 1)
            return

    removeCustomGraph()

    graph_qw = _find_graph_editor_widget()
    if not graph_qw:
        return
    graph_host, _graph_layout, _graph_content = _graph_editor_layout_host()
    if not graph_host:
        return

    flow_qw = cw.QFlatToolbar(
        parent=graph_host,
        settings_namespace="graph_toolbar_toolbuttons",
        margin=2,
        spacing_w=10,
        spacing_h=6,
        alignment=_graph_toolbar_alignment(),
    )
    flow_qw.setObjectName(_GRAPH_TOOLBAR_OBJECT)
    flow_qw.setProperty("tkm_managed_transient", True)
    flow_qw.hide()
    _GRAPH_TOOLBAR_WIDGET = flow_qw

    def new_section(hiddeable=True, color=None):
        return flow_qw.add_section(
            hiddeable=hiddeable,
            color=color,
        )

    def _build_graph_settings_menu(_menu, source_widget=None):
        return toolbar_menus.build_graph_settings_menu(
            source_widget or flow_qw,
            dock_options=graphToolbarController.DOCK_OPTIONS,
            dock_setting=graphToolbarController.GRAPH_TOOLBAR_DOCK_SETTING,
            default_dock_position=graphToolbarController.DOCK_BOTTOM_GRAPH,
            move_dock_fn=moveCustomGraphDock,
            apply_alignment_fn=applyCustomGraphAlignment,
        )

    toolbar_widgets.populate_graph_toolbar_from_layout(new_section, _build_graph_settings_menu, toolbar_widget=flow_qw)
    toolbar_widgets.bind_toolbar_pinning_context(flow_qw)

    _place_graph_toolbar_widget(flow_qw)
    height_timer = QtCore.QTimer(flow_qw)
    height_timer.setSingleShot(True)
    height_timer.timeout.connect(flow_qw._update_height)
    flow_qw._tkm_initial_height_timer = height_timer
    height_timer.start(50)
