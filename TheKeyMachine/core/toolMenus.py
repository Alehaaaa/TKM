try:
    from importlib import reload
except ImportError:
    from imp import reload

from functools import partial

from maya import cmds, mel

try:
    from PySide6 import QtCore, QtGui, QtWidgets

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
import TheKeyMachine.core.tool_widgets as toolWidgets
import TheKeyMachine.tools.graph_toolbar.api as graphToolbarApi
import TheKeyMachine.widgets.customWidgets as cw
from TheKeyMachine.widgets import util as wutil


TOOLBAR_ALIGNMENT_NAMES = ("Left", "Center", "Right")


def toolbar_alignment_map():
    return {
        "Left": QtCore.Qt.AlignLeft,
        "Center": QtCore.Qt.AlignHCenter,
        "Right": QtCore.Qt.AlignRight,
    }


def toolbar_alignment_value(alignment_name):
    return toolbar_alignment_map().get(alignment_name, QtCore.Qt.AlignHCenter)


TOOLBAR_ALIGNMENT_LABEL = "Align %s"
TOOLBAR_ALIGNMENT_DESC = "Align toolbar icons to the %s."

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


def build_tangent_menu(menu, tangent_type, tangent_label, icon=None, source_widget=None, maya_default_tangent=False):
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
            QtGui.QIcon(icon or ""),
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
            QtGui.QIcon(icon or ""),
            "Set Maya Default Tangent",
            lambda _checked=False: _set_maya_default_tangent(),
            description="Use {} for newly created keys.".format(tangent_label),
        )


def build_cycle_matcher_menu(menu, icon=None, source_widget=None):
    def _add_action(target_key, label):
        menu.addAction(
            QtGui.QIcon(icon or ""),
            label,
            lambda _checked=False, k=target_key: keyTools.match_curve_cycle(target_key=k),
            description="Match the cycle on the {}.".format(label.lower()),
        )

    _add_action("first", "First Key")
    _add_action("last", "Last Key")


def build_tracer_menu(menu, source_widget=None):
    import TheKeyMachine.mods.barMod as bar

    _ = source_widget

    def _tracer_is_connected():
        try:
            return (
                cmds.objExists("tracer")
                and cmds.objExists("tracerHandleShape")
                and cmds.isConnected("tracer.points", "tracerHandleShape.points")
            )
        except (RuntimeError, ValueError, TypeError, AttributeError, KeyError, IndexError):
            return False

    auto_update_action = menu.addAction(
        QtGui.QIcon(media.tracer_image),
        "Auto Update",
        description="Keep the tracer connected for live updates.",
    )
    auto_update_action.setCheckable(True)

    def _sync_auto_update_action():
        auto_update_action.blockSignals(True)
        auto_update_action.setChecked(_tracer_is_connected())
        auto_update_action.blockSignals(False)

    def _set_auto_update(checked):
        bar.tracer_connected(bool(checked), update_cb=auto_update_action.setChecked)
        _sync_auto_update_action()

    _sync_auto_update_action()
    auto_update_action.toggled.connect(_set_auto_update)
    menu.aboutToShow.connect(_sync_auto_update_action)

    menu.addSeparator()
    menu.addAction(QtGui.QIcon(media.refresh_image), "Refresh Tracer", bar.tracer_refresh)
    menu.addAction(QtGui.QIcon(media.tracer_show_hide_image), "Toggle Tracer", bar.tracer_show_hide)
    menu.addAction(QtGui.QIcon(media.tracer_select_offset_image), "Select Offset Object", bar.select_tracer_offset_node)

    menu.addSeparator()
    style_menu = menu.addMenu(QtGui.QIcon(media.tracer_image), "Style")
    style_menu.addAction(QtGui.QIcon(media.tracer_grey_image), "Tracer Style: Grey", bar.set_tracer_grey_color)
    style_menu.addAction(QtGui.QIcon(media.tracer_red_image), "Tracer Style: Red", bar.set_tracer_red_color)
    style_menu.addAction(QtGui.QIcon(media.tracer_blue_image), "Tracer Style: Blue", bar.set_tracer_blue_color)

    menu.addSeparator()
    menu.addAction(QtGui.QIcon(media.remove_image), "Remove Tracer", bar.remove_tracer_node)


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


def build_toolbar_pinning_menu(parent_widget, toolbar_widget):
    menu = cw.MenuWidget(parent_widget, tearoff=False)
    menu.addAction(cw.LogoAction(menu, clickable=False))
    
    sections = getattr(toolbar_widget, "_tkm_sections", []) or []
    for section in sections:
        if not wutil.is_valid_widget(section) or not getattr(section, "has_pinnable_items", lambda: False)():
            continue

        icon_path = getattr(section, "menu_icon", lambda: None)()
        label = getattr(section, "menu_label", lambda: "Tools")()
        section_menu = cw.OpenMenuWidget(QtGui.QIcon(icon_path or ""), label)
        section.populate_pinning_menu(section_menu)
        menu.addMenu(section_menu, description="Pin tools in {}.".format(label))

    if sections:
        _add_toolbar_pinning_footer(menu, toolbar_widget, sections)

    return menu


def _toolbar_alignment_context(toolbar_widget):
    is_graph_toolbar = toolbar_widget.objectName() == "tkm_customGraph_flowToolbar"
    setting_key = "graph_toolbar_alignment" if is_graph_toolbar else "toolbar_icon_alignment"

    def _apply_alignment(alignment_label):
        settings.set_setting(setting_key, alignment_label)

        if is_graph_toolbar:
            try:
                from TheKeyMachine.core import customGraph

                customGraph.applyCustomGraphAlignment(alignment_label)
            except (ImportError, RuntimeError, ValueError, TypeError, AttributeError, KeyError, IndexError):
                pass
            return

        parent = toolbar_widget.parent() if wutil.is_valid_widget(toolbar_widget) else None
        while parent:
            if hasattr(parent, "set_toolbar_icon_alignment"):
                parent.set_toolbar_icon_alignment(alignment_label)
                return
            parent = parent.parent()

        layout = toolbar_widget.layout() if wutil.is_valid_widget(toolbar_widget) else None
        if layout:
            layout.setAlignment(toolbar_alignment_value(alignment_label))
            layout.invalidate()
            toolbar_widget.updateGeometry()
            toolbar_widget.update()

        parent = toolbar_widget.parent() if wutil.is_valid_widget(toolbar_widget) else None
        while parent:
            if hasattr(parent, "update_height"):
                QtCore.QTimer.singleShot(0, parent.update_height)
                break
            if hasattr(parent, "_update_height"):
                QtCore.QTimer.singleShot(0, parent._update_height)
                break
            parent = parent.parent()

    return setting_key, _apply_alignment


def _restore_toolbar_pinning_defaults(menu, toolbar_widget, sections, apply_alignment_fn):
    from TheKeyMachine.widgets import customDialogs

    menu.close()
    clicked = customDialogs.QFlatConfirmDialog.question(
        menu.parent(),
        "Restore Defaults",
        "Restore the toolbar pins and alignment to their default values?",
        buttons=[customDialogs.QFlatConfirmDialog.Yes, customDialogs.QFlatConfirmDialog.Cancel],
        highlight=customDialogs.QFlatConfirmDialog.Yes,
        title="Restore toolbar defaults?",
        icon=media.warning_image,
    )
    if clicked != customDialogs.QFlatConfirmDialog.Yes:
        return

    for section in sections:
        if not wutil.is_valid_widget(section):
            continue
        if getattr(section, "_all_modes", None):
            section.pin_defaults(getattr(section, "_default_keys", []))
        else:
            section.pin_widget_defaults()

    apply_alignment_fn("Center")

    if wutil.is_valid_widget(toolbar_widget):
        layout = toolbar_widget.layout()
        if layout:
            layout.invalidate()
        toolbar_widget.updateGeometry()
        toolbar_widget.update()


def _add_toolbar_pinning_footer(menu, toolbar_widget, sections):
    menu.addSeparator()

    setting_key, apply_alignment_fn = _toolbar_alignment_context(toolbar_widget)
    align_group = QActionGroup(menu)
    align_group.setExclusive(True)
    menu._tkm_alignment_group = align_group
    align_actions = {}

    current_align = settings.get_setting(setting_key, "Center")

    for alignment_label in ("Left", "Right", "Center"):
        action = menu.addAction(
            TOOLBAR_ALIGNMENT_LABEL % alignment_label,
            description=TOOLBAR_ALIGNMENT_DESC % alignment_label.lower(),
        )
        action.setCheckable(True)
        action.setChecked(alignment_label == current_align)
        action.toggled.connect(
            lambda checked=False, label=alignment_label: apply_alignment_fn(label) if checked else None
        )
        align_group.addAction(action)
        align_actions[alignment_label] = action

    menu._tkm_alignment_actions = align_actions

    menu.addSeparator()
    menu.addAction(
        QtGui.QIcon(media.reload_image),
        "Restore Defaults",
        lambda: _restore_toolbar_pinning_defaults(menu, toolbar_widget, sections, apply_alignment_fn),
        description="Restore toolbar pins and alignment defaults.",
    )

    graph_toolbar_action = menu.addAction(
        QtGui.QIcon(media.customGraph_image),
        "Graph Editor Toolbar",
        description="Show or hide the TKM toolbar inside the Graph Editor.",
    )
    graph_toolbar_action.setCheckable(True)
    graph_toolbar_action.toggled.connect(lambda state: graphToolbarApi.set_graph_toolbar_enabled(bool(state)))
    graphToolbarApi.bind_graph_toolbar_toggle(graph_toolbar_action)


def should_show_toolbar_pinning_menu(toolbar_widget, pos):
    """Return True only when the toolbar background owns this context click."""
    if not wutil.is_valid_widget(toolbar_widget):
        return False

    child = toolbar_widget.childAt(pos)
    if child is None:
        return True

    sections = {
        section
        for section in getattr(toolbar_widget, "_tkm_sections", []) or []
        if wutil.is_valid_widget(section)
    }
    interactive_classes = (
        QtWidgets.QAbstractButton,
        QtWidgets.QAbstractSpinBox,
        QtWidgets.QComboBox,
        QtWidgets.QLineEdit,
        QtWidgets.QSlider,
    )

    widget = child
    while widget is not None and widget is not toolbar_widget:
        if widget in sections:
            return True
        if isinstance(widget, interactive_classes):
            return False
        if widget.contextMenuPolicy() in (QtCore.Qt.CustomContextMenu, QtCore.Qt.ActionsContextMenu):
            return False
        widget = widget.parentWidget()

    return child is toolbar_widget


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
    toolbar_alignment,
    update_show_tooltips,
    update_toolbar_icon_alignment,
):
    preferences_menu = cw.OpenMenuWidget(QtGui.QIcon(media.settings_image), "Preferences")
    parent_menu.addMenu(preferences_menu, description="General toolbar options.")
    setting_toggles = toolWidgets.setting_toggle_specs()

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
    for align_name, align_value in toolbar_alignment_map().items():
        action = preferences_menu.addAction(
            TOOLBAR_ALIGNMENT_LABEL % align_name,
            description=TOOLBAR_ALIGNMENT_DESC % align_name.lower(),
        )
        action.setCheckable(True)
        align_group.addAction(action)
        if align_value == toolbar_alignment:
            action.setChecked(True)
        action.triggered.connect(lambda _checked=False, n=align_name: update_toolbar_icon_alignment(n))

    preferences_menu.addSection("Display")

    display_actions = []
    for spec_key in ("overshoot_sliders", "attribute_switcher_euler_filter", "custom_graph"):
        spec = setting_toggles[spec_key]
        action = preferences_menu.addAction(
            QtGui.QIcon(spec.get("icon") or ""),
            spec["menu_label"],
            description=spec.get("description", ""),
        )
        action.toggled.connect(spec["set_checked"])
        toolWidgets.bind_setting_toggle(action, spec)
        display_actions.append((action, spec))

    def _sync_display_actions():
        for action, spec in display_actions:
            toolWidgets.sync_setting_toggle(action, spec)

    parent_menu.aboutToShow.connect(_sync_display_actions)
    preferences_menu.aboutToShow.connect(_sync_display_actions)
    return preferences_menu


def build_main_settings_menu(
    toolbar,
    parent_button,
    show_tooltips,
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
        label: settings_menu.addAction(
            TOOLBAR_ALIGNMENT_LABEL % label,
            description=TOOLBAR_ALIGNMENT_DESC % label.lower(),
        )
        for label in TOOLBAR_ALIGNMENT_NAMES
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
        lambda: QtCore.QTimer.singleShot(0, lambda: graphToolbarApi.set_graph_toolbar_enabled(False)),
        description="Hide the TKM Graph Editor toolbar and keep it disabled.",
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
