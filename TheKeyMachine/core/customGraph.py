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

from TheKeyMachine.widgets import sliderWidget as sw  # type: ignore
from TheKeyMachine.widgets import customWidgets as cw  # type: ignore
from TheKeyMachine.widgets import util as wutil  # type: ignore
import TheKeyMachine.mods.helperMod as helper  # type: ignore
import TheKeyMachine.mods.settingsMod as settings  # type: ignore
import TheKeyMachine.sliders as sliders  # type: ignore

mods = [general, ui, keyTools, selSets, media, style, sw, cw, helper, sliders]

for m in mods:
    importlib.reload(m)


COLOR = ui.Color()


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

    settings_menu.addSection("Hotkeys")
    settings_menu.addAction("Add TKM Hotkeys", hotkeys.create_TheKeyMachine_hotkeys, description="Setup Maya hotkeys.")

    settings_menu.addSection("General")
    settings_menu.addAction(QtGui.QIcon(media.reload_image), "Reload", createCustomGraph, description="Refresh the TKM interface.")

    menu.addSeparator()
    menu.addAction(QtGui.QIcon(media.about_image), "About", ui.about_window, description="Show version info and credits.")

    return menu


def create_tool_button(icon=None, text="", tooltip="", description="", command=None, p=None):
    """Helper to create a QFlatToolButton with our tooltip system"""
    btn = cw.QFlatToolButton(icon=icon, text=text)
    if tooltip:
        btn.setToolTipData(text=tooltip, description=description)
    if command:
        btn.clicked.connect(command)
    if p:
        p.addWidget(btn)
    return btn


def createCustomGraph():
    def add_to_flow(widget):
        if widget and wutil.is_valid_widget(widget):
            flowtoolbar_layout.addWidget(widget)
        return widget

    graph_vis = cmds.getPanel(vis=True)
    layout = "customGraph_columnLayout"

    if "graphEditor1" in graph_vis:
        if cmds.columnLayout(layout, exists=True):
            cmds.deleteUI(layout)
            cmds.columnLayout(layout, adj=1, p="graphEditor1")
        else:
            cmds.columnLayout(layout, adj=1, p="graphEditor1")
    else:
        cmds.GraphEditor()
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

    def new_section(hiddeable=True):
        sec = cw.QFlatSectionWidget(hiddeable=hiddeable)
        flowtoolbar_layout.addWidget(sec)
        return sec

    parent_ptr = mui.MQtUtil.findControl(layout)
    parent_qw = wutil.get_maya_qt(parent_ptr, QtWidgets.QWidget)
    if parent_qw and parent_qw.layout():
        parent_qw.layout().addWidget(flow_qw)

    # ________________ Key Tools Buttons  ___________________#
    sec = new_section()

    btn_static = create_tool_button(
        icon=media.delete_animation_image,
        text="S",
        tooltip="Static",
        description="Remove all statics curves",
        command=lambda: keyTools.deleteStaticCurves(),
    )
    sec.addWidget(btn_static, "Static", "static")

    btn_share = create_tool_button(
        icon=media.share_keys_image,
        text="H",
        tooltip="Share",
        description="Share keys between curves to ensure both curves have the same keys in the same position.",
        command=lambda: keyTools.shareKeys(),
    )
    sec.addWidget(btn_share, "Share", "share")

    btn_match = create_tool_button(
        icon=media.match_image,
        text="M",
        tooltip="Match",
        description="Makes a match of one curve with another, in this way both curves will be the same.",
        command=lambda: keyTools.match_keys(),
    )
    sec.addWidget(btn_match, "Match", "match")

    btn_flip = create_tool_button(
        text="F", tooltip="Flip", description="Inverts the selected curve vertically.", command=lambda: keyTools.flipCurves()
    )
    sec.addWidget(btn_flip, "Flip", "flip")

    btn_snap = create_tool_button(
        text="Sn",
        tooltip="Snap",
        description="Performs a cleanup and repositioning of the keys that are in a sub-frame to the nearest frame.",
        command=lambda: keyTools.snapKeyframes(),
    )
    sec.addWidget(btn_snap, "Snap", "snap")

    btn_overlap = create_tool_button(
        text="O",
        tooltip="Overlap",
        description="Applies an overlap frame to the selected curves.",
        command=keyTools.mod_overlap_animation,
    )
    sec.addWidget(btn_overlap, "Overlap", "overlap")

    btn_reblock = create_tool_button(
        icon=media.reblock_keys_image,
        text="rB",
        tooltip="reBlock",
        description="reBlock allows you to realign all the curves so that all their keyframes match up.",
        command=keyTools.reblock_move,
    )
    sec.addWidget(btn_reblock, "reBlock", "reblock")
    extra_btn = create_tool_button(text="E", tooltip="Extra", description="Additional curve utilities.", command=lambda: keyTools.snapKeyframes())
    sec.addWidget(extra_btn, "Extra Tools", "extra")
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
            is_visible = settings.get_setting(f"pin_{prefix}_{key}", f"{prefix}_{key}" in static_default_keys)

            s = sw.QFlatSliderWidget(
                f"graph_{prefix}_{key}",
                min=-100,
                max=100,
                text=icon,
                color=color,
                dragCommand=None or (lambda v, k=key: change_func(k, v)),
                dropCommand=drop_func,
                tooltipTitle=label,
                tooltipDescription=desc,
            )
            s.setModes(modes_list)
            s.setCurrentMode(key)

            # Setup mode switching for this specific slider instance
            def make_mode_setter(slider_instance, prefix_val):
                def setter(new_mode):
                    # For compatibility, if they change mode via the slider's OWN menu,
                    # we update the global setting and the slider's state.
                    settings.set_setting(f"graph_{prefix_val}_mode", new_mode)
                    slider_instance.setCurrentMode(new_mode)
                    # Find info for new mode to update tooltip
                    m_info = next((item for item in modes_list if isinstance(item, dict) and item["key"] == new_mode), None)
                    if m_info:
                        slider_instance.setTooltipInfo(m_info["label"], m_info.get("description", ""))
                    slider_instance.startFlash()

                return setter

            s.modeSelected.connect(make_mode_setter(s, prefix))

            sec.addWidget(s, label, f"{prefix}_{key}", default_visible=is_visible, description=desc)

        # Add the final pin actions at the bottom of the section menu
        sec.add_final_actions(static_default_keys)

    add_mode_sliders(
        sliders.TWEEN_MODES,
        "graph_tween_mode",
        "tween",
        COLOR.color.yellow,
        sliders.execute_tween,
        sliders.stop_dragging,
        default_modes=["tweener"],
        ws_support=True,
    )
    add_mode_sliders(
        sliders.BLEND_MODES,
        "graph_blend_mode",
        "blend",
        COLOR.color.green,
        sliders.execute_curve_modifier,
        sliders.stop_dragging,
        default_modes=["connect_neighbors"],
    )
    add_mode_sliders(
        sliders.TANGENT_MODES,
        "graph_tangent_mode",
        "tangent",
        COLOR.color.orange,
        sliders.execute_tangent_blend,
        sliders.stop_dragging,
        default_modes=["blend_best_guess"],
    )

    # _________________  Iso / Mute / Lock  _________________#
    sec = new_section()
    btn_iso = create_tool_button(
        icon=media.isolate_image,
        tooltip="Isolate Curves",
        description="Isolate selected curves.",
        command=lambda: keyTools.isolateCurve(),
    )
    sec.addWidget(btn_iso, "Isolate", "iso")

    btn_mute = create_tool_button(text="Mt", tooltip="Mute", description="Toggle mute on selected curves.", command=lambda: keyTools.toggleMute())
    sec.addWidget(btn_mute, "Mute", "mute")

    btn_lock = create_tool_button(text="Lk", tooltip="Lock", description="Toggle lock on selected curves.", command=lambda: keyTools.toggleLock())
    sec.addWidget(btn_lock, "Lock", "lock")

    btn_fi = create_tool_button(
        text="Fi",
        tooltip="Filter",
        command=lambda: ui.customGraph_filter_mods(),
        description="Filter selection in the GraphEditor. Shift+Click to deactivate.",
    )
    sec.addWidget(btn_fi, "Filter", "filter")

    # ____________________  Resets  _________________________#
    sec = new_section()
    btn_reset = create_tool_button(
        icon=media.reset_animation_image,
        text="R",
        tooltip="Reset",
        description="Reset the selected curves to their default values.",
        command=lambda: keyTools.get_default_value_main(),
    )
    sec.addWidget(btn_reset, "Reset", "reset")

    # ________________  SelSets Buttons  ____________________#
    # sec = new_section()
    # color_map = {
    #     "1": "#CBC8AD",
    #     "2": "#7BA399",
    #     "3": "#93C2AD",
    #     "4": "#C29591",
    #     "5": "#A86465",
    # }
    # for i in range(1, 6):
    #     s_id = str(i)
    #     s_name = "button_" + s_id
    #     btn = create_tool_button(text=s_id, tooltip="SelSet 0{}".format(s_id), description="Left-click to select, Right-click for options.", p=sec)
    #     btn.setStyleSheet("QPushButton {{ background-color: {}; color: #333; }}".format(color_map.get(s_id, "#555")))

    #     # Action menu
    #     menu = cw.MenuWidget(parent=btn)
    #     menu.addAction("Set", partial(selSets.set_button_value, s_name))
    #     menu.addSeparator()
    #     menu.addAction("Add", partial(selSets.add_button_selection, s_name))
    #     menu.addAction("Remove", partial(selSets.remove_button_selection, s_name))
    #     menu.addSeparator()
    #     menu.addAction("Lock", partial(selSets.lock_button_selection, s_name))
    #     menu.addAction("Unlock", partial(selSets.unlock_button_selection, s_name))

    #     btn = create_tool_button(text=s_id, tooltip="SelSet 0{}".format(s_id), description="Left-click to select, Right-click for options.")
    #     sec.addWidget(btn, "Set 0{}".format(s_id), "set_{}".format(s_id))
    #     btn.setStyleSheet("QPushButton {{ background-color: {}; color: #333; }}".format(color_map.get(s_id, "#555")))

    #     # Re-parent the menu to the button after it's created
    #     menu.setParent(btn)
    #     btn.clicked.connect(partial(selSets.handle_button_selection, s_name))
    #     btn.setContextMenuPolicy(QtCore.Qt.CustomContextMenu)
    #     btn.customContextMenuRequested.connect(lambda pos, m=menu, b=btn: m.exec_(b.mapToGlobal(pos)))

    # ________________ Cycle / Bouncy ___________________#
    sec = new_section()
    btn_cycle = create_tool_button(
        icon=media.match_curve_cycle_image,
        tooltip="Cycle Matcher",
        description="Curve cycle matcher.",
        command=keyTools.match_curve_cycle,
    )
    sec.addWidget(btn_cycle, "Cycle Matcher", "cycle")

    btn_bouncy = create_tool_button(
        icon=media.bouncy_curve_image, tooltip="Bouncy", description="Set bouncy tangents.", command=keyTools.bouncy_tangets
    )
    sec.addWidget(btn_bouncy, "Bouncy", "bouncy")

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

    config_btn = create_tool_button(icon=media.settings_image, tooltip="Config", description="Tool configuration and preferences.")
    sec.addWidget(config_btn, "Config", "config")

    settings_menu = create_settings_menu(config_btn)

    def _open_settings_menu():
        settings_menu.exec_(QtGui.QCursor.pos())

    def _on_toolbar_context_menu(pos):
        if flow_qw.childAt(pos):
            return
        _open_settings_menu()

    config_btn.clicked.connect(_open_settings_menu)
    config_btn.setContextMenuPolicy(QtCore.Qt.CustomContextMenu)
    config_btn.customContextMenuRequested.connect(lambda pos: _open_settings_menu())

    flow_qw.setContextMenuPolicy(QtCore.Qt.CustomContextMenu)
    flow_qw.customContextMenuRequested.connect(_on_toolbar_context_menu)

    QtCore.QTimer.singleShot(50, flow_qw._update_height)
