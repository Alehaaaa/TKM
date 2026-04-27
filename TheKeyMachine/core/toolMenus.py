try:
    from importlib import reload
except ImportError:
    from imp import reload

from functools import partial

from maya import cmds, mel

try:
    from PySide6 import QtCore, QtGui

    QActionGroup = QtGui.QActionGroup
except ImportError:
    from PySide2 import QtCore, QtGui, QtWidgets

    QActionGroup = QtWidgets.QActionGroup

import TheKeyMachine.mods.hotkeysMod as hotkeys
import TheKeyMachine.mods.generalMod as general
import TheKeyMachine.mods.keyToolsMod as keyTools
import TheKeyMachine.mods.mediaMod as media
import TheKeyMachine.mods.settingsMod as settings
import TheKeyMachine.mods.uiMod as ui
import TheKeyMachine.mods.updater as updater
import TheKeyMachine.tools.graph_toolbar.api as graphToolbarApi
import TheKeyMachine.widgets.customWidgets as cw
from TheKeyMachine.widgets import util as wutil


def _command_callback(command, is_python):
    if is_python:
        return lambda: exec(command)
    return lambda: mel.eval(command)


def _resolve_dot_image(image):
    dot_images = {
        "dot_green.png": media.dot_green_image,
        "dot_blue.png": media.dot_blue_image,
        "dot_red.png": media.dot_red_image,
        "dot_grey.png": media.dot_grey_image,
        "dot_yellow.png": media.dot_yellow_image,
    }
    return dot_images.get(image, image)


def _populate_connect_menu(menu, module, order_attr, id_prefix, config_folder, config_file):
    reload(module)
    menu.clear()

    name_to_id = {}
    for index in range(1, 100):
        item_id = "{}{}".format(id_prefix, str(index).zfill(2))
        try:
            name_to_id[getattr(module, "{}_name".format(item_id))] = item_id
        except AttributeError:
            break

    for item_name in getattr(module, order_attr, []):
        if not item_name:
            continue
        item_id = name_to_id.get(item_name)
        if not item_id:
            continue
        try:
            name = getattr(module, "{}_name".format(item_id))
            image = _resolve_dot_image(getattr(module, "{}_image".format(item_id)))
            is_python = getattr(module, "{}_is_python".format(item_id))
            command = getattr(module, "{}_command".format(item_id))
        except AttributeError:
            continue

        if not name:
            continue
        if name == "separator":
            menu.addSeparator()
        else:
            menu.addAction(QtGui.QIcon(image), name, callback=_command_callback(command, is_python))

    menu.addSeparator()
    menu.addAction(
        QtGui.QIcon(media.settings_image),
        "Open config file",
        callback=lambda: general.open_file(config_folder, config_file),
    )


def build_custom_tools_menu(menu, source_widget=None):
    import TheKeyMachine_user_data.connect.tools.tools as connectToolBox

    _populate_connect_menu(
        menu,
        connectToolBox,
        order_attr="tool_order",
        id_prefix="t",
        config_folder="TheKeyMachine_user_data/connect/tools",
        config_file="tools.py",
    )


def build_custom_scripts_menu(menu, source_widget=None):
    import TheKeyMachine_user_data.connect.scripts.scripts as cbScripts

    _populate_connect_menu(
        menu,
        cbScripts,
        order_attr="scripts_order",
        id_prefix="s",
        config_folder="TheKeyMachine_user_data/connect/scripts",
        config_file="scripts.py",
    )


def build_extra_graph_tools_menu(menu, source_widget=None):
    menu.addAction("Select object from selected curve", callback=lambda: keyTools.select_objects_from_selected_curves())


def build_share_keys_menu(menu, source_widget=None):
    _ = source_widget
    action_group = QActionGroup(menu)
    action_group.setExclusive(True)

    preserve_tangent_action = menu.addAction("Preserve Tangent Type")
    preserve_tangent_action.setCheckable(True)
    preserve_tangent_action.setChecked(keyTools.get_share_keys_mode() == keyTools.SHARE_KEYS_MODE_PRESERVE_TANGENT)
    preserve_tangent_action.triggered.connect(lambda checked=False: keyTools.set_share_keys_mode(keyTools.SHARE_KEYS_MODE_PRESERVE_TANGENT))
    action_group.addAction(preserve_tangent_action)

    preserve_shape_action = menu.addAction("Preserve Anim Curve Shape")
    preserve_shape_action.setCheckable(True)
    preserve_shape_action.setChecked(keyTools.get_share_keys_mode() == keyTools.SHARE_KEYS_MODE_PRESERVE_SHAPE)
    preserve_shape_action.triggered.connect(lambda checked=False: keyTools.set_share_keys_mode(keyTools.SHARE_KEYS_MODE_PRESERVE_SHAPE))
    action_group.addAction(preserve_shape_action)

    menu.addSeparator()


def build_tangent_menu(menu, tangent_type, tangent_label, icon_path=None, source_widget=None, maya_default_tangent=False):
    import TheKeyMachine.mods.barMod as bar

    tint_color = cw.get_widget_tint_color(source_widget)

    def _set_tangent(handle_mode, key_scope, tint):
        if tangent_type == "bouncy":
            return keyTools.bouncy_tangets(
                handle_mode=handle_mode,
                key_scope=key_scope,
                tint_color=tint,
            )

        return bar.setTangent(
            tangent_type,
            handle_mode=handle_mode,
            key_scope=key_scope,
            tint_color=tint,
        )

    def _add_action(handle_mode, handle_label, key_scope, scope_label):
        menu.addAction(
            QtGui.QIcon(icon_path or ""),
            handle_label,
            lambda _checked=False, h=handle_mode, s=key_scope, c=tint_color: _set_tangent(h, s, c),
            description="Set {}.".format(scope_label.lower()),
        )

    def _set_maya_default_tangent():
        cmds.keyTangent(**{"global": True, "inTangentType": tangent_type, "outTangentType": tangent_type})

    _add_action("in", "In Tangent", "selection", "the in tangent on the current selection")
    _add_action("out", "Out Tangent", "selection", "the out tangent on the current selection")
    menu.addSeparator()
    _add_action("both", "First Key", "first", "the first key")
    _add_action("both", "Last Key", "last", "the last key")
    menu.addSeparator()
    _add_action("both", "All Keys", "all", "all keys")

    if maya_default_tangent:
        menu.addAction(
            QtGui.QIcon(icon_path or ""),
            "Set Maya Default Tangent",
            lambda _checked=False: _set_maya_default_tangent(),
            description="Use {} for newly created keys.".format(tangent_label),
        )


def build_cycle_matcher_menu(menu, icon_path=None, source_widget=None):
    def _add_action(target_key, label):
        menu.addAction(
            QtGui.QIcon(icon_path or ""),
            label,
            lambda _checked=False, k=target_key: keyTools.match_curve_cycle(target_key=k),
            description="Match the cycle on the {}.".format(label.lower()),
        )

    _add_action("first", "First Key")
    _add_action("last", "Last Key")


def sync_main_dock_menu(toolbar):
    if not wutil.is_valid_widget(getattr(toolbar, "dock_menu", None)):
        return

    for action in toolbar.dock_menu.actions():
        layout = next((key for key, name in toolbar.docking_layouts.items() if name == action.text()), None)
        if layout:
            if layout == toolbar.docking_position[0]:
                action.setEnabled(False)
                continue
            action.setEnabled(wutil.check_visible_layout(layout))


def build_main_dock_menu(toolbar):
    toolbar.dock_menu = cw.MenuWidget(QtGui.QIcon(media.dock_image), "Dock", description="Move the toolbar to a different Maya area.")

    toolbar.pos_ac_group = QActionGroup(toolbar)
    for orient, name in toolbar.docking_orients.items():
        ori_btn = toolbar.dock_menu.addAction(name, description="Place the toolbar on the {} side.".format(name.lower()))
        ori_btn.setCheckable(True)
        toolbar.pos_ac_group.addAction(ori_btn)
        ori_btn.triggered.connect(partial(toolbar.dock_to_ui, orient=orient))
        if orient == toolbar.docking_position[1]:
            ori_btn.setChecked(True)
            ori_btn.setEnabled(False)

    toolbar.dock_menu.addSeparator()

    toolbar.dock_ac_group = QActionGroup(toolbar)
    for layout, name in toolbar.docking_layouts.items():
        dock_btn = toolbar.dock_menu.addAction(name, description="Dock the toolbar in {}.".format(name))
        dock_btn.setCheckable(True)
        toolbar.dock_ac_group.addAction(dock_btn)
        dock_btn.triggered.connect(partial(toolbar.dock_to_ui, layout=layout))
        if layout == toolbar.docking_position[0]:
            dock_btn.setChecked(True)
            dock_btn.setEnabled(False)

    toolbar.dock_menu.aboutToShow.connect(lambda: sync_main_dock_menu(toolbar))
    return toolbar.dock_menu


def add_main_help_menu(parent_menu):
    help_menu = cw.MenuWidget(QtGui.QIcon(media.help_menu_image), "Help")
    parent_menu.addMenu(help_menu, description="Docs, support, and community links.")
    help_menu.addAction(QtGui.QIcon(media.report_a_bug_image), "Report a Bug", ui.bug_report_window, description="Send a bug report.")
    help_menu.addSeparator()
    help_menu.addAction(
        QtGui.QIcon(media.discord_image),
        "Discord",
        lambda: general.open_url("https://discord.gg/G2J5yyjz"),
        description="Open the community server.",
    )
    help_menu.addAction(
        QtGui.QIcon(media.help_menu_image),
        "Documentation",
        lambda: general.open_url("https://thekeymachine.gitbook.io/base"),
        description="Open the docs.",
    )
    help_menu.addAction(
        QtGui.QIcon(media.youtube_image),
        "YouTube",
        lambda: general.open_url("https://www.youtube.com/@TheKeyMachineAnimationTools"),
        description="Watch tutorials and demos.",
    )
    return help_menu


def add_main_system_menu(toolbar, parent_menu):
    system_menu = cw.MenuWidget(QtGui.QIcon(media.system_image), "System")
    parent_menu.addMenu(system_menu, description="Maintenance actions.")
    system_menu.addAction(QtGui.QIcon(media.reload_image), "Reload", toolbar.reload, description="Refresh the TKM interface.")
    system_menu.addAction(QtGui.QIcon(media.close_image), "Unload", toolbar.unload, description="Close TheKeyMachine and remove callbacks.")
    system_menu.addAction(QtGui.QIcon(media.remove_image), "Uninstall", ui.uninstall, description="Remove TheKeyMachine from Maya.")
    return system_menu


def add_main_preferences_menu(
    toolbar,
    parent_menu,
    show_tooltips,
    alignments,
    toolbar_alignment,
    update_show_tooltips,
    update_toolbar_icon_alignment,
):
    preferences_menu = cw.OpenMenuWidget(QtGui.QIcon(media.settings_image), "Preferences")
    parent_menu.addMenu(preferences_menu, description="General toolbar options.")
    setting_toggles = toolbar._settings_toggle_specs()

    preferences_menu.addSection("Startup")
    preferences_menu.addAction(
        QtGui.QIcon(media.asset_path("tool_icon")),
        "Create a Shelf Button",
        toolbar.create_shelf_icon,
        description="Add a shelf button for showing or hiding the toolbar.",
    )

    run_on_startup_action = preferences_menu.addAction(
        "Start with Maya", ui.install_userSetup, description="Load TheKeyMachine automatically when Maya starts."
    )
    run_on_startup_action.setCheckable(True)
    run_on_startup_action.setChecked(ui.check_userSetup())

    show_tooltips_action = preferences_menu.addAction("Show Tooltips", description="Show tooltip popups.")
    show_tooltips_action.setCheckable(True)
    show_tooltips_action.setChecked(show_tooltips)
    show_tooltips_action.toggled.connect(update_show_tooltips)

    preferences_menu.addSection("Alignment")
    align_group = QActionGroup(preferences_menu)
    for align_name, align_value in alignments.items():
        action = preferences_menu.addAction(align_name, description="Align toolbar icons to the {}.".format(align_name.lower()))
        action.setCheckable(True)
        align_group.addAction(action)
        if align_value == toolbar_alignment:
            action.setChecked(True)
        action.triggered.connect(lambda _checked=False, n=align_name, v=align_value: update_toolbar_icon_alignment(n, v))

    preferences_menu.addSection("Display")

    display_actions = []
    for spec_key in ("overshoot_sliders", "attribute_switcher_euler_filter", "custom_graph"):
        spec = setting_toggles[spec_key]
        action = preferences_menu.addAction(
            QtGui.QIcon(spec.get("icon_path") or ""),
            spec["menu_label"],
            description=spec.get("description", ""),
        )
        action.toggled.connect(spec["set_checked"])
        toolbar._bind_setting_toggle(action, spec)
        display_actions.append((action, spec))

    def _sync_display_actions():
        for action, spec in display_actions:
            toolbar._sync_setting_toggle(action, spec)

    parent_menu.aboutToShow.connect(_sync_display_actions)
    preferences_menu.aboutToShow.connect(_sync_display_actions)
    return preferences_menu


def build_main_settings_menu(
    toolbar,
    parent_button,
    show_tooltips,
    alignments,
    toolbar_alignment,
    update_show_tooltips,
    update_toolbar_icon_alignment,
    internet_connection=False,
):
    toolbar_menu = cw.MenuWidget(parent=parent_button)
    toolbar_menu.addAction(cw.LogoAction(toolbar_menu))
    add_main_preferences_menu(
        toolbar,
        toolbar_menu,
        show_tooltips=show_tooltips,
        alignments=alignments,
        toolbar_alignment=toolbar_alignment,
        update_show_tooltips=update_show_tooltips,
        update_toolbar_icon_alignment=update_toolbar_icon_alignment,
    )
    toolbar_menu.addAction(
        QtGui.QIcon(media.hotkeys_image),
        "Hotkeys",
        hotkeys.show_hotkeys_window,
        description="Edit keyboard shortcuts for TheKeyMachine tools.",
    )
    toolbar_menu.addMenu(build_main_dock_menu(toolbar), description="Move the toolbar to a different Maya area.")
    add_main_system_menu(toolbar, toolbar_menu)
    toolbar_menu.addSeparator()
    add_main_help_menu(toolbar_menu)
    if internet_connection:
        toolbar_menu.addAction(
            QtGui.QIcon(media.check_updates_image),
            "Check for updates",
            lambda: updater.check_for_updates(parent_button, force=True),
            description="Look for a new version.",
        )
    toolbar_menu.addAction(QtGui.QIcon(media.about_image), "About", ui.about_window, description="Show version info and credits.")
    return toolbar_menu


def build_graph_settings_menu(
    parent_button,
    dock_options,
    dock_setting,
    default_dock_position,
    move_dock_fn,
    apply_alignment_fn,
    remove_toolbar_fn,
):
    menu = cw.MenuWidget(parent=parent_button)
    menu.addAction(cw.LogoAction(menu))

    settings_menu = cw.MenuWidget(QtGui.QIcon(media.settings_image), "Settings", description="Tool configuration and preferences.")
    menu.addMenu(settings_menu)

    settings_menu.addSection("Graph toolbar")
    graph_toolbar_action = settings_menu.addAction(
        QtGui.QIcon(media.customGraph_image),
        "Graph Editor Toolbar",
        description="Show or hide the TKM toolbar inside the Graph Editor.",
    )
    graph_toolbar_action.setCheckable(True)
    graph_toolbar_action.toggled.connect(lambda state: graphToolbarApi.set_graph_toolbar_enabled(bool(state)))
    graphToolbarApi.bind_graph_toolbar_toggle(graph_toolbar_action)

    dock_menu = cw.MenuWidget(QtGui.QIcon(media.dock_image), "Dock", description="Move the Graph Editor toolbar.")
    menu.addMenu(dock_menu)
    dock_group = QActionGroup(dock_menu)
    dock_group.setExclusive(True)

    dock_actions = {}
    for position, label, description in dock_options:
        action = dock_menu.addAction(label, description=description)
        action.setCheckable(True)
        dock_group.addAction(action)
        action.triggered.connect(lambda checked=False, p=position: move_dock_fn(p))
        dock_actions[position] = action

    current_position = settings.get_setting(dock_setting, default_dock_position)
    if current_position not in dock_actions:
        current_position = default_dock_position
    for position, action in dock_actions.items():
        action.setChecked(position == current_position)

    settings_menu.addSection("Toolbar's icons alignment")
    align_group = QActionGroup(settings_menu)
    align_actions = {
        "Left": settings_menu.addAction("Left", description="Align icons to the left."),
        "Center": settings_menu.addAction("Center", description="Align icons to the center."),
        "Right": settings_menu.addAction("Right", description="Align icons to the right."),
    }
    current_align = settings.get_setting("graph_toolbar_alignment", "Center")
    for label, action in align_actions.items():
        action.setCheckable(True)
        align_group.addAction(action)
        action.setChecked(label == current_align)
        action.toggled.connect(lambda state, alignment_label=label: apply_alignment_fn(alignment_label) if state else None)

    settings_menu.addSection("General")
    settings_menu.addAction(
        QtGui.QIcon(media.close_image),
        "Close",
        lambda: QtCore.QTimer.singleShot(0, remove_toolbar_fn),
        description="Close only the TKM Graph Editor toolbar.",
    )

    menu.addAction(QtGui.QIcon(media.hotkeys_image), "Hotkeys", hotkeys.show_hotkeys_window, description="Manage trigger hotkeys.")
    menu.addSeparator()

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
