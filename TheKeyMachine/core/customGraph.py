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

import maya.cmds as cmds
import maya.OpenMayaUI as mui

import importlib

try:
    from PySide2 import QtCore, QtGui, QtWidgets
    from PySide2.QtWidgets import QActionGroup
except ImportError:
    from PySide6 import QtCore, QtGui, QtWidgets
    from PySide6.QtGui import QActionGroup


# -----------------------------------------------------------------------------------------------------------------------------
#                                             Loading necessary modules from TheKeyMachine                                    #
# -----------------------------------------------------------------------------------------------------------------------------

import TheKeyMachine.mods.generalMod as general
import TheKeyMachine.mods.uiMod as ui
import TheKeyMachine.mods.keyToolsMod as keyTools
import TheKeyMachine.mods.selSetsMod as selSets
import TheKeyMachine.mods.mediaMod as media
import TheKeyMachine.mods.styleMod as style
import TheKeyMachine.core.toolbox as toolbox
from TheKeyMachine.tools import colors as toolColors

from TheKeyMachine.widgets import sliderWidget as sw  # type: ignore
from TheKeyMachine.widgets import customWidgets as cw  # type: ignore
from TheKeyMachine.widgets import util as wutil  # type: ignore
import TheKeyMachine.mods.helperMod as helper  # type: ignore
import TheKeyMachine.mods.settingsMod as settings  # type: ignore
import TheKeyMachine.sliders as sliders  # type: ignore
import TheKeyMachine.tools.graph_toolbar.api as graphToolbarApi  # type: ignore

mods = [general, ui, keyTools, selSets, media, style, sw, cw, helper, sliders, toolbox]

for m in mods:
    importlib.reload(m)


UI_COLORS = toolColors.UI_COLORS

_GRAPH_TOOLBAR_OBJECT = "tkm_customGraph_flowToolbar"
_GRAPH_TOOLBAR_DOCK_SETTING = "graph_toolbar_dock_position"
_DOCK_BOTTOM_GRAPH = "bottom_graph_editor"
_DOCK_TOP_GRAPH = "top_graph_editor"
_DOCK_BOTTOM_MENU = "bottom_menu"
_DOCK_OPTIONS = (
    (_DOCK_TOP_GRAPH, "Top of Graph Editor", "Place the toolbar at the top of the Graph Editor."),
    (_DOCK_BOTTOM_GRAPH, "Bottom of Graph Editor", "Place the toolbar at the bottom of the Graph Editor."),
    # (_DOCK_BOTTOM_MENU, "Bottom of Menu", "Place the toolbar directly below the Graph Editor menu."),
)
_GRAPH_TOOLBAR_WIDGET = None


def _normalize_dock_position(position=None):
    allowed_positions = {position for position, _label, _description in _DOCK_OPTIONS}
    position = position or settings.get_setting(_GRAPH_TOOLBAR_DOCK_SETTING, _DOCK_BOTTOM_GRAPH)
    return position if position in allowed_positions else _DOCK_BOTTOM_GRAPH


def _graph_toolbar_alignment():
    align_str = settings.get_setting("graph_toolbar_alignment", "Center")
    if align_str == "Center":
        return QtCore.Qt.AlignHCenter
    if align_str == "Right":
        return QtCore.Qt.AlignRight
    return QtCore.Qt.AlignLeft


def _find_graph_editor_widget():
    graph_ptr = mui.MQtUtil.findControl("graphEditor1")
    return wutil.get_maya_qt(graph_ptr, QtWidgets.QWidget) if graph_ptr else None


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


def _iter_graph_toolbar_widgets():
    graph_qw = _find_graph_editor_widget()
    if not graph_qw:
        return []
    return [widget for widget in graph_qw.findChildren(QtWidgets.QWidget, _GRAPH_TOOLBAR_OBJECT) if wutil.is_valid_widget(widget)]


def _delete_graph_toolbar_widget(toolbar_widget):
    if toolbar_widget and wutil.is_valid_widget(toolbar_widget):
        try:
            parent = toolbar_widget.parentWidget()
            if parent and parent.layout():
                parent.layout().removeWidget(toolbar_widget)
            toolbar_widget.setObjectName("{}_deleted".format(_GRAPH_TOOLBAR_OBJECT))
            toolbar_widget.setParent(None)
            toolbar_widget.deleteLater()
        except Exception:
            pass


def removeCustomGraph() -> None:
    global _GRAPH_TOOLBAR_WIDGET
    for toolbar_widget in _iter_graph_toolbar_widgets():
        _delete_graph_toolbar_widget(toolbar_widget)
    _GRAPH_TOOLBAR_WIDGET = None
    graphToolbarApi.emit_graph_toolbar_state()


def _show_graph_editor() -> None:
    """Open and raise Maya's Graph Editor window for explicit toolbar launches."""
    try:
        cmds.GraphEditor()
    except Exception:
        pass

    try:
        if cmds.window("graphEditor1Window", exists=True):
            cmds.showWindow("graphEditor1Window")
    except Exception:
        pass

    try:
        ptr = mui.MQtUtil.findWindow("graphEditor1Window")
        graph_window = wutil.get_maya_qt(ptr, QtWidgets.QWidget) if ptr else None
        if graph_window:
            if hasattr(graph_window, "showNormal"):
                graph_window.showNormal()
            graph_window.raise_()
            graph_window.activateWindow()
    except Exception:
        pass


# -----------------------------------------------------------------------------------------------------------------------------
#                                                       customGraph build                                                     #
# -----------------------------------------------------------------------------------------------------------------------------


def apply_base_stylesheet(button):
    """Fallback stylesheet for standard buttons if needed"""
    pass


def create_settings_menu(parent_button):
    """Creates a config menu consistent with the main toolbar"""
    import TheKeyMachine.mods.hotkeysMod as hotkeys

    menu = cw.MenuWidget(parent=parent_button)
    menu.addAction(cw.LogoAction(menu))

    # Settings submenu
    settings_menu = cw.MenuWidget(QtGui.QIcon(media.settings_image), "Settings", description="Tool configuration and preferences.")
    menu.addMenu(settings_menu)

    settings_menu.addSection("Graph toolbar")
    graph_toolbar_action = settings_menu.addAction(
        QtGui.QIcon(media.customGraph_image),
        "Graph Editor Toolbar",
        description="Show or hide the TKM toolbar inside the Graph Editor.",
    )
    graph_toolbar_action.setCheckable(True)

    def _on_graph_toolbar_toggled(state):
        graphToolbarApi.set_graph_toolbar_enabled(bool(state))

    graph_toolbar_action.toggled.connect(_on_graph_toolbar_toggled)
    graphToolbarApi.bind_graph_toolbar_toggle(graph_toolbar_action)

    dock_menu = cw.MenuWidget(QtGui.QIcon(media.dock_image), "Dock", description="Move the Graph Editor toolbar.")
    menu.addMenu(dock_menu)
    dock_group = QActionGroup(dock_menu)
    dock_group.setExclusive(True)


    dock_actions = {}
    for position, label, description in _DOCK_OPTIONS:
        action = dock_menu.addAction(label, description=description)
        action.setCheckable(True)
        dock_group.addAction(action)
        action.triggered.connect(lambda checked=False, p=position: moveCustomGraphDock(p))
        dock_actions[position] = action

    def _sync_dock_menu():
        current_position = settings.get_setting(_GRAPH_TOOLBAR_DOCK_SETTING, _DOCK_BOTTOM_GRAPH)
        if current_position not in dock_actions:
            current_position = _DOCK_BOTTOM_GRAPH
        for position, action in dock_actions.items():
            if not wutil.is_valid_widget(action):
                continue
            try:
                action.blockSignals(True)
                action.setChecked(position == current_position)
                action.blockSignals(False)
            except RuntimeError:
                continue

    _sync_dock_menu()

    settings_menu.addSection("Toolbar's icons alignment")
    align_group = QActionGroup(settings_menu)
    left_align = settings_menu.addAction("Left", description="Align icons to the left.")
    center_align = settings_menu.addAction("Center", description="Align icons to the center.")
    right_align = settings_menu.addAction("Right", description="Align icons to the right.")

    current_align = settings.get_setting("graph_toolbar_alignment", "Center")
    align_map = {"Left": left_align, "Center": center_align, "Right": right_align}

    for label, act in align_map.items():
        act.setCheckable(True)
        align_group.addAction(act)
        if label == current_align:
            act.setChecked(True)

        def set_align(state, alignment_label=label):
            if state:
                applyCustomGraphAlignment(alignment_label)

        act.toggled.connect(set_align)

    settings_menu.addSection("General")
    settings_menu.addAction(
        QtGui.QIcon(media.close_image),
        "Close",
        lambda: QtCore.QTimer.singleShot(0, removeCustomGraph),
        description="Close only the TKM Graph Editor toolbar.",
    )

    menu.addAction(
        QtGui.QIcon(media.hotkeys_image),
        "Hotkeys",
        hotkeys.show_hotkeys_window,
        description="Manage trigger hotkeys.",
    )

    menu.addSeparator()

    # Help submenu
    help_menu = cw.MenuWidget(QtGui.QIcon(media.help_menu_image), "Help", description="Resources for help and learning.")
    menu.addMenu(help_menu)
    help_menu.addAction(
        QtGui.QIcon(media.discord_image),
        "Discord Community",
        lambda: general.open_url("https://discord.gg/G2J5yyjz"),
        description="Join the community for support.",
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
        description="Watch tutorials.",
    )

    menu.addAction(QtGui.QIcon(media.about_image), "About", ui.about_window, description="Show version info and credits.")

    return menu


def _place_graph_toolbar_widget(toolbar_widget, dock_position=None):
    dock_position = _normalize_dock_position(dock_position)

    graph_qw = _find_graph_editor_widget()
    graph_layout = graph_qw.layout() if graph_qw else None
    if not graph_layout or not wutil.is_valid_widget(toolbar_widget):
        return False

    parent = toolbar_widget.parentWidget()
    if parent and parent.layout():
        parent.layout().removeWidget(toolbar_widget)
    toolbar_widget.setParent(graph_qw)

    if dock_position == _DOCK_TOP_GRAPH:
        graph_layout.insertWidget(0, toolbar_widget)
    # if dock_position == _DOCK_BOTTOM_MENU:
    #     graph_layout.insertWidget(0, toolbar_widget)
    # elif dock_position == _DOCK_TOP_GRAPH:
    #     graph_layout.insertWidget(0, toolbar_widget)
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
    position = _normalize_dock_position(position)
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


def create_tool_button(
    icon=None,
    text="",
    tooltip_template="",
    description="",
    command=None,
    shortcuts=None,
    shortcut_variants=None,
    status_title=None,
    status_description=None,
    p=None,
):
    """Helper to create a QFlatToolButton with our tooltip system"""
    btn = cw.create_tool_button_from_data(
        {
            "icon_path": icon,
            "text": text,
            "tooltip_template": tooltip_template,
            "description": description,
            "callback": command,
            "shortcuts": shortcuts,
            "shortcut_variants": shortcut_variants,
            "status_title": status_title,
            "status_description": status_description,
        }
    )
    if p:
        p.addWidget(btn)
    return btn


def create_toolbox_button(tool_id, p=None, **overrides):
    tool_data = toolbox.get_tool(tool_id, **overrides)
    btn = cw.create_tool_button_from_data(tool_data)
    if p:
        p.addWidget(btn)
    return btn


def createCustomGraph(*_args, force: bool = False, _attempt: int = 0, **_kwargs):
    global _GRAPH_TOOLBAR_WIDGET

    if not force and not settings.get_setting("graph_toolbar_enabled", True):
        return removeCustomGraph()

    graph_vis = cmds.getPanel(vis=True)
    if "graphEditor1" not in graph_vis:
        if not force:
            return
        _show_graph_editor()
        graph_vis = cmds.getPanel(vis=True) or []
        if "graphEditor1" not in graph_vis:
            if _attempt < 5:
                QtCore.QTimer.singleShot(100, lambda: createCustomGraph(force=True, _attempt=_attempt + 1))
            return

    removeCustomGraph()

    graph_qw = _find_graph_editor_widget()
    if not graph_qw or not graph_qw.layout():
        return

    flow_qw = cw.QFlowContainer(graph_qw)
    flow_qw.setObjectName(_GRAPH_TOOLBAR_OBJECT)
    flow_qw.hide()
    _GRAPH_TOOLBAR_WIDGET = flow_qw

    flowtoolbar_layout = cw.QFlowLayout(flow_qw, margin=2, Wspacing=18, Hspacing=6, alignment=_graph_toolbar_alignment())

    def new_section(hiddeable=True, color=None):
        sec = cw.QFlatSectionWidget(
            hiddeable=hiddeable,
            settings_namespace="graph_toolbar_toolbuttons",
            color=color,
        )
        flowtoolbar_layout.addWidget(sec)
        return sec

    # ________________ Key Tools Buttons  ___________________#
    sec = new_section()

    sec.addWidgetGroup(
        [
            toolbox.get_tool("static", default=True),
            toolbox.get_tool("share_keys", text="sK", default=True),
            toolbox.get_tool("match", text="M", default=True),
            toolbox.get_tool("flip", text="F", default=True),
            toolbox.get_tool("snap", text="Sn", default=True),
            toolbox.get_tool("overlap", text="O", default=True),
            {
                "key": "extra",
                "label": "Extra Tools",
                "text": "E",
                "tooltip_template": helper.extra_tools_tooltip_text,
                "description": "Open extra graph tools.",
                "default": True,
            },
        ]
    )

    # Extra/Misc (Retrieving the object to add a menu)
    extra_btn = sec._widgets.get("extra")
    if extra_btn and wutil.is_valid_widget(extra_btn):
        extra_menu = cw.MenuWidget(parent=extra_btn)
        extra_menu.addAction("Select object from selected curve", lambda: keyTools.select_objects_from_selected_curves())
        extra_btn.setContextMenuPolicy(QtCore.Qt.CustomContextMenu)
        extra_btn.customContextMenuRequested.connect(lambda pos: extra_menu.exec_(extra_btn.mapToGlobal(pos)))
        extra_btn.clicked.connect(lambda: extra_menu.exec_(QtGui.QCursor.pos()))

    # _________________  Slider Logic & Wrappers ____________________#

    # 1. Sliders Sections - Tween, Blend, and Tangent
    def add_mode_sliders(modes_list, prefix, color, change_func, drop_func, default_modes=None, ws_support=False):
        # Create a new section for each slider color/type
        sec = new_section()
        sec.set_settings_namespace("graph_toolbar_sliders")
        sec.set_persist_slider_modes(False)

        # Static default list for "Pin Defaults"
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

            # Determine initial visibility: pinned setting takes priority, fallback to default_modes membership
            is_visible = settings.get_setting(f"pin_{prefix}_{key}", f"{prefix}_{key}" in static_default_keys, namespace="graph_toolbar_sliders")

            s = sw.QFlatSliderWidget(
                f"graph_{prefix}_{key}",
                min=-100,
                max=100,
                text=icon,
                color=color,
                dragCommand=(lambda mode_key, v, session=None: change_func(mode_key, v, session=session)),
                dropCommand=drop_func,
                tooltipTitle=label,
                tooltipDescription=desc,
            )
            s.setModes(modes_list)
            s.setCurrentMode(key)

            # Setup mode switching for this specific slider instance
            def make_mode_setter(slider_instance, prefix_val):
                def setter(new_mode, temporary=False):
                    slider_instance.setCurrentMode(new_mode, temporary=temporary)
                    # Find info for new mode to update tooltip
                    m_info = next((item for item in modes_list if isinstance(item, dict) and item["key"] == new_mode), None)
                    if m_info:
                        slider_instance.setTooltipInfo(m_info["label"], m_info.get("description", ""))
                    if not temporary:
                        slider_instance.startFlash()

                return setter

            s.modeRequested.connect(make_mode_setter(s, prefix))

            sec.addWidget(s, label, f"{prefix}_{key}", default_visible=is_visible, description=desc)

        # Add the final pin actions at the bottom of the section menu
        sec.add_final_actions(static_default_keys)

    add_mode_sliders(
        sliders.TWEEN_MODES,
        "tween",
        UI_COLORS.yellow.hex,
        sliders.execute_tween,
        sliders.stop_dragging,
        default_modes=["tweener"],
        ws_support=True,
    )
    add_mode_sliders(
        sliders.BLEND_MODES,
        "blend",
        UI_COLORS.green.hex,
        sliders.execute_curve_modifier,
        sliders.stop_dragging,
        default_modes=["connect_neighbors"],
    )
    add_mode_sliders(
        sliders.TANGENT_MODES,
        "tangent",
        UI_COLORS.orange.hex,
        sliders.execute_tangent_blend,
        sliders.stop_dragging,
        default_modes=["blend_best_guess"],
    )

    # _________________  Iso / Mute / Lock  _________________#
    sec = new_section()
    btn_iso = create_toolbox_button("graph_isolate_curves")
    sec.addWidget(btn_iso, "Isolate", "iso")

    btn_mute = create_toolbox_button("graph_toggle_mute")
    sec.addWidget(btn_mute, "Mute", "mute")

    btn_lock = create_toolbox_button("graph_toggle_lock")
    sec.addWidget(btn_lock, "Lock", "lock")

    btn_fi = create_toolbox_button("graph_filter", callback=lambda: ui.customGraph_filter_mods())
    sec.addWidget(btn_fi, "Filter", "filter")

    # ____________________  Resets  _________________________#
    sec = new_section()
    sec.addWidgetGroup(toolbox.get_tool_group("reset_tools"))

    # _________________  Tangents  ____________________#
    sec = new_section(color=toolColors.orange)
    btn_cycle = create_toolbox_button("tangent_cycle_matcher")
    sec.addWidget(btn_cycle, "Cycle Matcher", "cycle", default_visible=False)

    btn_bouncy = create_toolbox_button("tangent_bouncy")
    sec.addWidget(btn_bouncy, "Bouncy Tangent", "bouncy")

    btn_tangent_auto = create_toolbox_button("tangent_auto")
    sec.addWidget(btn_tangent_auto, "Auto Tangent", "tangent_auto")

    btn_tangent_spline = create_toolbox_button("tangent_spline")
    sec.addWidget(btn_tangent_spline, "Spline Tangent", "tangent_spline")

    btn_tangent_clamped = create_toolbox_button("tangent_clamped")
    sec.addWidget(btn_tangent_clamped, "Clamped Tangent", "tangent_clamped", default_visible=False)

    btn_tangent_linear = create_toolbox_button("tangent_linear")
    sec.addWidget(btn_tangent_linear, "Linear Tangent", "tangent_linear")

    btn_tangent_flat = create_toolbox_button("tangent_flat")
    sec.addWidget(btn_tangent_flat, "Flat Tangent", "tangent_flat", default_visible=False)

    btn_tangent_step = create_toolbox_button("tangent_step")
    sec.addWidget(btn_tangent_step, "Step Tangent", "tangent_step")

    btn_tangent_plateau = create_toolbox_button("tangent_plateau")
    sec.addWidget(btn_tangent_plateau, "Plateau Tangent", "tangent_plateau", default_visible=False)

    # _________________  Opacity Slider  ____________________#

    def set_opacity_from_slider(value):
        # Normalize percent to 0..1
        v = value / 100.0
        graph_editor_window = get_graph_editor_window()
        if graph_editor_window is None:
            cmds.warning("GraphEditor opacity is not available when it's docked")
        else:
            graph_editor_window.setWindowOpacity(v)

    def get_graph_editor_window():
        if not cmds.window("graphEditor1Window", exists=True):
            cmds.GraphEditor()
        ptr = mui.MQtUtil.findWindow("graphEditor1Window")
        if ptr is not None:
            return wutil.get_maya_qt(ptr, QtWidgets.QWidget)
        else:
            return None

    # ________________ System/Core Section ___________________#
    sec = new_section(hiddeable=False)

    settings_btn = create_tool_button(
        icon=media.settings_image,
        description="Access Graph Editor toolbar preferences, and view credits.",
        status_title="Settings",
    )
    sec.addWidget(settings_btn, "Settings", "settings")

    def _open_settings_menu():
        settings_menu = create_settings_menu(settings_btn)
        try:
            settings_menu.exec_(QtGui.QCursor.pos())
        finally:
            try:
                settings_menu.deleteLater()
            except Exception:
                pass

    def _on_toolbar_context_menu(pos):
        if flow_qw.childAt(pos):
            return
        _open_settings_menu()

    settings_btn.clicked.connect(_open_settings_menu)
    settings_btn.setContextMenuPolicy(QtCore.Qt.CustomContextMenu)
    settings_btn.customContextMenuRequested.connect(lambda pos: _open_settings_menu())

    flow_qw.setContextMenuPolicy(QtCore.Qt.CustomContextMenu)
    flow_qw.customContextMenuRequested.connect(_on_toolbar_context_menu)

    _place_graph_toolbar_widget(flow_qw)
    QtCore.QTimer.singleShot(50, flow_qw._update_height)
