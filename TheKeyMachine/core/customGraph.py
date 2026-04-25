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

_GRAPH_LAYOUT = "customGraph_columnLayout"


def removeCustomGraph() -> None:
    if cmds.columnLayout(_GRAPH_LAYOUT, exists=True):
        try:
            cmds.deleteUI(_GRAPH_LAYOUT)
        except Exception:
            pass
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
                settings.set_setting("graph_toolbar_alignment", alignment_label)
                createCustomGraph()

        act.toggled.connect(set_align)

    settings_menu.addAction(
        QtGui.QIcon(media.hotkeys_image),
        "Hotkeys",
        hotkeys.show_hotkeys_window,
        description="Manage trigger hotkeys.",
    )

    settings_menu.addSection("General")
    settings_menu.addAction(
        QtGui.QIcon(media.close_image),
        "Close",
        lambda: QtCore.QTimer.singleShot(0, removeCustomGraph),
        description="Close only the TKM Graph Editor toolbar.",
    )

    menu.addSeparator()
    menu.addAction(QtGui.QIcon(media.about_image), "About", ui.about_window, description="Show version info and credits.")

    return menu


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
    if not force and not settings.get_setting("graph_toolbar_enabled", True):
        removeCustomGraph()
        return

    def add_to_flow(widget):
        if widget and wutil.is_valid_widget(widget):
            flowtoolbar_layout.addWidget(widget)
        return widget

    graph_vis = cmds.getPanel(vis=True)
    layout = _GRAPH_LAYOUT

    if "graphEditor1" not in graph_vis:
        if not force:
            return
        _show_graph_editor()
        graph_vis = cmds.getPanel(vis=True) or []
        if "graphEditor1" not in graph_vis:
            if _attempt < 5:
                QtCore.QTimer.singleShot(100, lambda: createCustomGraph(force=True, _attempt=_attempt + 1))
            return

    if "graphEditor1" in graph_vis:
        if cmds.columnLayout(layout, exists=True):
            cmds.deleteUI(layout)
            cmds.columnLayout(layout, adj=1, p="graphEditor1")
        else:
            cmds.columnLayout(layout, adj=1, p="graphEditor1")

    flow_qw = cw.QFlowContainer()
    flow_qw.setObjectName("tkm_customGraph_flowToolbar")

    align_str = settings.get_setting("graph_toolbar_alignment", "Center")
    align_val = QtCore.Qt.AlignLeft
    if align_str == "Center":
        align_val = QtCore.Qt.AlignHCenter
    elif align_str == "Right":
        align_val = QtCore.Qt.AlignRight

    flowtoolbar_layout = cw.QFlowLayout(flow_qw, margin=2, Wspacing=18, Hspacing=6, alignment=align_val)

    def new_section(hiddeable=True, color=None):
        sec = cw.QFlatSectionWidget(hiddeable=hiddeable, color=color)
        flowtoolbar_layout.addWidget(sec)
        return sec

    parent_ptr = mui.MQtUtil.findControl(layout)
    parent_qw = wutil.get_maya_qt(parent_ptr, QtWidgets.QWidget)
    if parent_qw and parent_qw.layout():
        parent_qw.layout().addWidget(flow_qw)

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
    def add_mode_sliders(modes_list, default_key_setting, prefix, color, change_func, drop_func, default_modes=None, ws_support=False):
        # Create a new section for each slider color/type
        sec = new_section()
        sec.set_settings_namespace("graph_toolbar_sliders")

        current_default = settings.get_setting(default_key_setting, modes_list[0]["key"] if isinstance(modes_list[0], dict) else modes_list[1]["key"])

        # Static default list for "Pin Defaults"
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
                    # For compatibility, if they change mode via the slider's OWN menu,
                    # we update the global setting and the slider's state.
                    if not temporary:
                        settings.set_setting(f"graph_{prefix_val}_mode", new_mode)
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
        "graph_tween_mode",
        "tween",
        UI_COLORS.yellow.hex,
        sliders.execute_tween,
        sliders.stop_dragging,
        default_modes=["tweener"],
        ws_support=True,
    )
    add_mode_sliders(
        sliders.BLEND_MODES,
        "graph_blend_mode",
        "blend",
        UI_COLORS.green.hex,
        sliders.execute_curve_modifier,
        sliders.stop_dragging,
        default_modes=["connect_neighbors"],
    )
    add_mode_sliders(
        sliders.TANGENT_MODES,
        "tangent_mode",
        "tangent",
        "#ea7760",
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

    settings_menu = create_settings_menu(settings_btn)

    def _open_settings_menu():
        settings_menu.exec_(QtGui.QCursor.pos())

    def _on_toolbar_context_menu(pos):
        if flow_qw.childAt(pos):
            return
        _open_settings_menu()

    settings_btn.clicked.connect(_open_settings_menu)
    settings_btn.setContextMenuPolicy(QtCore.Qt.CustomContextMenu)
    settings_btn.customContextMenuRequested.connect(lambda pos: _open_settings_menu())

    flow_qw.setContextMenuPolicy(QtCore.Qt.CustomContextMenu)
    flow_qw.customContextMenuRequested.connect(_on_toolbar_context_menu)

    QtCore.QTimer.singleShot(50, flow_qw._update_height)
