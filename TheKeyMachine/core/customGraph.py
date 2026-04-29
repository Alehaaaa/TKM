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

import maya.cmds as cmds # type: ignore
import maya.OpenMayaUI as mui # type: ignore

import importlib

try:
    from PySide2 import QtCore, QtGui, QtWidgets # type: ignore
except ImportError:
    from PySide6 import QtCore, QtGui, QtWidgets # type: ignore


# -----------------------------------------------------------------------------------------------------------------------------
#                                             Loading necessary modules from TheKeyMachine                                    #
# -----------------------------------------------------------------------------------------------------------------------------

import TheKeyMachine.mods.generalMod as general
import TheKeyMachine.mods.uiMod as ui
import TheKeyMachine.mods.keyToolsMod as keyTools
import TheKeyMachine.mods.selSetsMod as selSets
import TheKeyMachine.mods.mediaMod as media
import TheKeyMachine.mods.styleMod as style
import TheKeyMachine.core.toolMenus as toolMenus
import TheKeyMachine.core.toolbox as toolbox
import TheKeyMachine.core.tool_widgets as toolWidgets
import TheKeyMachine.core.trigger as trigger

from TheKeyMachine.widgets import sliderWidget as sw  # type: ignore
from TheKeyMachine.widgets import customWidgets as cw  # type: ignore
from TheKeyMachine.widgets import util as wutil  # type: ignore
import TheKeyMachine.mods.helperMod as helper  # type: ignore
import TheKeyMachine.mods.settingsMod as settings  # type: ignore
import TheKeyMachine.sliders as sliders  # type: ignore
import TheKeyMachine.tools.graph_toolbar.api as graphToolbarApi  # type: ignore

mods = [general, ui, keyTools, selSets, media, style, sw, cw, helper, sliders, toolMenus, toolbox, toolWidgets, trigger]

for m in mods:
    importlib.reload(m)


_GRAPH_TOOLBAR_OBJECT = "tkm_customGraph_flowToolbar"
_GRAPH_TOOLBAR_DOCK_SETTING = "graph_toolbar_dock_position"
_DOCK_BOTTOM_GRAPH = "bottom_graph_editor"
_DOCK_TOP_GRAPH = "top_graph_editor"
_DOCK_BOTTOM_MENU = "bottom_menu"
_DOCK_OPTIONS = (
    (_DOCK_BOTTOM_MENU, "Under Menu", "Place the toolbar directly below the Graph Editor menu."),
    (_DOCK_TOP_GRAPH, "Top of Graph Editor", "Place the toolbar at the top of the Graph Editor."),
    (_DOCK_BOTTOM_GRAPH, "Bottom of Graph Editor", "Place the toolbar at the bottom of the Graph Editor."),
)
_DOCK_POSITION_IDS = {position for position, _label, _description in _DOCK_OPTIONS}

_ALIGNMENT_DICT = {
    "Left": QtCore.Qt.AlignLeft,
    "Center": QtCore.Qt.AlignHCenter,
    "Right": QtCore.Qt.AlignRight,
}

_GRAPH_TOOLBAR_WIDGET = None


def _graph_toolbar_alignment():
    align_str = settings.get_setting("graph_toolbar_alignment", "Center")
    return _ALIGNMENT_DICT.get(align_str, QtCore.Qt.AlignHCenter)


def _find_graph_editor_widget():
    graph_ptr = mui.MQtUtil.findControl("graphEditor1")
    graph_qw = wutil.get_maya_qt(graph_ptr, QtWidgets.QWidget) if graph_ptr else None
    if graph_qw:
        for child in graph_qw.children():
            if not isinstance(child, QtWidgets.QWidget):
                continue
            if isinstance(child, QtWidgets.QMenuBar) or child.objectName() == _GRAPH_TOOLBAR_OBJECT:
                continue
            if child.layout():
                return child
    return graph_qw


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

    toolbar_widget = graph_qw.findChild(QtWidgets.QWidget, _GRAPH_TOOLBAR_OBJECT)
    if toolbar_widget and wutil.is_valid_widget(toolbar_widget):
        _GRAPH_TOOLBAR_WIDGET = toolbar_widget
        return toolbar_widget

    _GRAPH_TOOLBAR_WIDGET = None
    return None


def removeCustomGraph() -> None:
    global _GRAPH_TOOLBAR_WIDGET
    graph_qw = _find_graph_editor_widget()
    if graph_qw:
        for toolbar_widget in graph_qw.findChildren(QtWidgets.QWidget, _GRAPH_TOOLBAR_OBJECT):
            if not wutil.is_valid_widget(toolbar_widget):
                continue
            try:
                parent = toolbar_widget.parentWidget()
                if parent and parent.layout():
                    parent.layout().removeWidget(toolbar_widget)
                toolbar_widget.setObjectName("{}_deleted".format(_GRAPH_TOOLBAR_OBJECT))
                toolbar_widget.setParent(None)
                toolbar_widget.deleteLater()
            except Exception:
                pass
    _GRAPH_TOOLBAR_WIDGET = None
    graphToolbarApi.emit_graph_toolbar_state()

# -----------------------------------------------------------------------------------------------------------------------------
#                                                       customGraph build                                                     #
# -----------------------------------------------------------------------------------------------------------------------------


def _place_graph_toolbar_widget(toolbar_widget, dock_position=None, graph_qw=None):
    if dock_position is None:
        dock_position = settings.get_setting(_GRAPH_TOOLBAR_DOCK_SETTING, _DOCK_BOTTOM_GRAPH)
    if dock_position not in _DOCK_POSITION_IDS:
        dock_position = _DOCK_BOTTOM_GRAPH

    if not graph_qw:
        graph_qw = _find_graph_editor_widget()
    graph_layout = graph_qw.layout() if graph_qw else None

    parent = toolbar_widget.parentWidget()
    if parent and parent.layout():
        parent.layout().removeWidget(toolbar_widget)
    toolbar_widget.setParent(graph_qw)

    if hasattr(graph_layout, "insertWidget"):
        if dock_position == _DOCK_BOTTOM_MENU:
            graph_layout.insertWidget(0, toolbar_widget)
        elif dock_position == _DOCK_TOP_GRAPH:
            graph_layout.insertWidget(1, toolbar_widget)
        else:  # _DOCK_BOTTOM_GRAPH
            graph_layout.addWidget(toolbar_widget)
    else:
        graph_layout.addWidget(toolbar_widget)

    toolbar_widget.show()
    return True


def applyCustomGraphAlignment(alignment_label=None):
    if alignment_label:
        settings.set_setting("graph_toolbar_alignment", alignment_label)

    toolbar_widget = getCustomGraphWidget()
    if not toolbar_widget:
        return False

    layout = toolbar_widget.layout()
    if not layout:
        return False

    try:
        layout.setAlignment(_graph_toolbar_alignment())
        layout.invalidate()
        toolbar_widget.updateGeometry()
        toolbar_widget.update()
        toolbar_widget._update_height()
        return True
    except Exception:
        return False


def moveCustomGraphDock(position=None):
    settings.set_setting(_GRAPH_TOOLBAR_DOCK_SETTING, position)
    toolbar_widget = getCustomGraphWidget()
    if toolbar_widget and wutil.is_valid_widget(toolbar_widget):
        if _place_graph_toolbar_widget(toolbar_widget, position):
            try:
                toolbar_widget._update_height()
            except Exception:
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


def _add_graph_slider_section_from_data(section_def, new_section_fn):
    sec = new_section_fn(color=section_def.get("color"))
    sec.set_settings_namespace("graph_toolbar_sliders")
    sec.set_persist_slider_modes(False)

    prefix = section_def["slider_type"]
    color = section_def["color"]
    modes = getattr(sliders, section_def["modes_attr"])
    default_modes = section_def.get("default_modes", [])
    static_default_keys = [f"{prefix}_{key}" for key in default_modes]

    for mode in modes:
        if mode == "separator":
            sec.addSeparator()
            continue
        if not isinstance(mode, dict):
            continue

        key = mode["key"]
        label = mode["label"]
        desc = mode.get("description", "")
        icon = mode.get("icon", "SL")
        is_visible = settings.get_setting(
            f"pin_{prefix}_{key}",
            f"{prefix}_{key}" in static_default_keys,
            namespace="graph_toolbar_sliders",
        )

        slider = sw.QFlatSliderWidget(
            f"graph_{prefix}_{key}",
            min=-100,
            max=100,
            text=icon,
            color=color,
            dragCommand=lambda mode_key, value, p=prefix, session=None: trigger.execute_slider(
                p,
                mode_key,
                value,
                session=session,
            ),
            tooltipTitle=label,
            tooltipDescription=desc,
        )
        slider.setModes(modes)
        slider.setCurrentMode(key)

        def make_mode_setter(slider_instance):
            def setter(new_mode, temporary=False):
                slider_instance.setCurrentMode(new_mode, temporary=temporary)
                mode_info = next((item for item in modes if isinstance(item, dict) and item["key"] == new_mode), None)
                if mode_info:
                    slider_instance.setTooltipInfo(mode_info["label"], mode_info.get("description", ""))
                if not temporary:
                    slider_instance.startFlash()

            return setter

        slider.modeRequested.connect(make_mode_setter(slider))
        sec.addWidget(slider, label, f"{prefix}_{key}", default=is_visible, description=desc)

    sec.add_final_actions(static_default_keys)
    return sec


def _add_graph_section_items(sec, items, graph_settings_menu_fn, toolbar_widget=None):
    def add_tool_item(item):
        btn = cw.create_tool_button_from_data(item)
        sec.addWidget(
            btn,
            item.get("label", ""),
            item.get("key", ""),
            default=item.get("default", True),
            description=item.get("description"),
            tooltip_template=item.get("tooltip_template"),
            pinnable=item.get("pinnable", True),
        )
        return btn

    for item in items:
        if item == "separator":
            sec.addSeparator()
            continue
        if not isinstance(item, dict):
            continue
        if item.get("type") == "widget":
            toolWidgets.create_widget_from_data(sec, item, owner=toolbar_widget)
            continue
        if item.get("type") == "group":
            _add_graph_group(sec, item.get("items", []), graph_settings_menu_fn, toolbar_widget=toolbar_widget)
            continue

        if item.get("key") == "settings":
            settings_tool = dict(item)
            settings_tool["menu"] = graph_settings_menu_fn
            settings_btn = cw.create_tool_button_from_data(settings_tool)
            sec.addWidget(
                settings_btn,
                settings_tool.get("label", "Settings"),
                settings_tool.get("key", "settings"),
                default=settings_tool.get("default", True),
                description=settings_tool.get("description"),
            )
            continue

        add_tool_item(item)


def _add_graph_group(sec, items, graph_settings_menu_fn, toolbar_widget=None):
    group_run = []

    def flush_group_run():
        if not group_run:
            return
        while group_run and group_run[0] == "separator":
            sec.addSeparator()
            group_run.pop(0)
        if group_run:
            sec.addWidgetGroup(list(group_run))
        group_run[:] = []

    for item in items:
        if isinstance(item, dict) and item.get("type") == "widget":
            flush_group_run()
            toolWidgets.create_widget_from_data(sec, item, owner=toolbar_widget)
            continue
        if isinstance(item, dict) and item.get("type") == "group":
            flush_group_run()
            _add_graph_group(sec, item.get("items", []), graph_settings_menu_fn, toolbar_widget=toolbar_widget)
            continue
        group_run.append(item)

    flush_group_run()


def _populate_graph_toolbar_from_layout(new_section_fn, graph_settings_menu_fn, toolbar_widget=None):
    sections = toolbox.get_toolbar_sections("graph", resolve_items=False)
    grouped_section_ids = {"graph_key_tools", "default_tools"}
    for section_def in sections:
        if section_def.get("type") == "slider":
            _add_graph_slider_section_from_data(section_def, new_section_fn)
            continue

        sec = new_section_fn(
            color=section_def.get("color"),
            hiddeable=section_def.get("hiddeable", True),
        )
        resolved_section = toolbox.get_tool_section(section_def["id"])
        if section_def["id"] in grouped_section_ids:
            _add_graph_group(sec, resolved_section["items"], graph_settings_menu_fn, toolbar_widget=toolbar_widget)
            continue

        _add_graph_section_items(sec, resolved_section["items"], graph_settings_menu_fn, toolbar_widget=toolbar_widget)


def createCustomGraph(*_args, force: bool = False, _attempt: int = 0, **_kwargs):
    global _GRAPH_TOOLBAR_WIDGET

    if not force and not settings.get_setting("graph_toolbar_enabled", True):
        return removeCustomGraph()

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
                QtCore.QTimer.singleShot(100, lambda: createCustomGraph(force=True, _attempt=_attempt + 1))
            return

    removeCustomGraph()

    graph_qw = _find_graph_editor_widget()
    if not graph_qw:
        return

    flow_qw = cw.QFlowContainer()
    flow_qw.setObjectName(_GRAPH_TOOLBAR_OBJECT)
    flow_qw.hide()
    _GRAPH_TOOLBAR_WIDGET = flow_qw

    flowtoolbar_layout = cw.QFlowLayout(flow_qw, margin=2, Wspacing=10, Hspacing=6, alignment=_graph_toolbar_alignment())

    def new_section(hiddeable=True, color=None):
        sec = cw.QFlatSectionWidget(
            hiddeable=hiddeable,
            settings_namespace="graph_toolbar_toolbuttons",
            color=color,
        )
        flowtoolbar_layout.addWidget(sec)
        return sec

    def _build_graph_settings_menu(_menu, source_widget=None):
        return toolMenus.build_graph_settings_menu(
            source_widget or flow_qw,
            dock_options=_DOCK_OPTIONS,
            dock_setting=_GRAPH_TOOLBAR_DOCK_SETTING,
            default_dock_position=_DOCK_BOTTOM_GRAPH,
            move_dock_fn=moveCustomGraphDock,
            apply_alignment_fn=applyCustomGraphAlignment,
            remove_toolbar_fn=removeCustomGraph,
        )

    _populate_graph_toolbar_from_layout(new_section, _build_graph_settings_menu, toolbar_widget=flow_qw)

    def _on_toolbar_context_menu(pos):
        if flow_qw.childAt(pos):
            return
        settings_menu = _build_graph_settings_menu(None, source_widget=flow_qw)
        settings_menu.exec_(QtGui.QCursor.pos())

    flow_qw.setContextMenuPolicy(QtCore.Qt.CustomContextMenu)
    flow_qw.customContextMenuRequested.connect(_on_toolbar_context_menu)

    _place_graph_toolbar_widget(flow_qw, graph_qw=graph_qw)
    QtCore.QTimer.singleShot(50, flow_qw._update_height)
