from functools import partial

from maya import cmds

from TheKeyMachine.Qt import QtCore, QtGui, QtWidgets

QActionGroup = QtGui.QActionGroup

import TheKeyMachine.mods.generalMod as general
import TheKeyMachine.mods.helperMod as helper
import TheKeyMachine.mods.keyToolsMod as keyTools
from TheKeyMachine.data import icons
import TheKeyMachine.mods.settingsMod as settings
import TheKeyMachine.mods.uiMod as ui
import TheKeyMachine.mods.updater as updater
import TheKeyMachine.core.toolWidgets as toolWidgets
import TheKeyMachine.core.backgroundRunners as backgroundRunners
import TheKeyMachine.core.connectEntries as connectEntries
import TheKeyMachine.tools.graph_toolbar.api as graphToolbarApi
from TheKeyMachine.tools import common as toolCommon
import TheKeyMachine.widgets.customWidgets as cw
from TheKeyMachine.widgets import util as wutil


TOOLBAR_ALIGNMENTS = {
    "Left": QtCore.Qt.AlignLeft,
    "Center": QtCore.Qt.AlignHCenter,
    "Right": QtCore.Qt.AlignRight,
}
TOOLBAR_ALIGNMENT_NAMES = tuple(TOOLBAR_ALIGNMENTS)


def toolbar_alignment_map():
    return dict(TOOLBAR_ALIGNMENTS)


def toolbar_alignment_value(alignment_name):
    return TOOLBAR_ALIGNMENTS.get(alignment_name, QtCore.Qt.AlignHCenter)


TOOLBAR_ALIGNMENT_LABEL = "Align %s"
TOOLBAR_ALIGNMENT_DESC = "Align toolbar icons to the %s."
UNSET = object()


def _resolve_action_fields(command_id=None, tool_lookup=None, **overrides):
    fields = {}
    if command_id:
        if not callable(tool_lookup):
            raise TypeError("tool_lookup must be callable for command-backed actions")
        tool = tool_lookup(command_id)
        tooltip = tool.get("tooltip")
        fields.update(
            {
                "label": tool.get("menu_label") or tool.get("label") or command_id,
                "callback": None if tool.get("setting_toggle") else tool.get("callback"),
                "icon": tool.get("icon"),
                "description": tooltip if isinstance(tooltip, str) else "",
                "tooltip": tooltip,
                "command_icon": tool.get("icon"),
            }
        )
    fields.update(overrides)
    fields.setdefault("label", command_id or "")
    fields.setdefault("callback", None)
    fields.setdefault("icon", None)
    fields.setdefault("description", "")
    fields.setdefault("tooltip", None)
    fields.setdefault("command_icon", fields.get("icon"))
    return fields


def update_show_tooltips(value):
    """Persist and immediately apply the shared tooltip preference."""
    from TheKeyMachine.mods.tooltipsMod import QFlatTooltipManager

    enabled = bool(value)
    settings.set_setting("show_tooltips", enabled)
    QFlatTooltipManager.enabled = enabled
    if not enabled:
        QFlatTooltipManager.hide()


def _source_tool_key(source_widget):
    return getattr(source_widget, "_section_key", None) if source_widget else None


def _qicon(icon):
    return icon if isinstance(icon, QtGui.QIcon) else QtGui.QIcon(icon or "")


def _add_action(
    menu,
    label=UNSET,
    callback=UNSET,
    *,
    icon=UNSET,
    description=UNSET,
    tooltip=UNSET,
    command_id=None,
    command_icon=UNSET,
    open_menu=False,
):
    from TheKeyMachine.core import toolbox

    explicit = {
        key: value
        for key, value in {
            "label": label,
            "callback": callback,
            "icon": icon,
            "description": description,
            "tooltip": tooltip,
            "command_icon": command_icon,
        }.items()
        if value is not UNSET
    }
    fields = _resolve_action_fields(command_id, toolbox.get_tool if command_id else None, **explicit)

    args = (_qicon(fields["icon"]), fields["label"]) if fields["icon"] is not None else (fields["label"],)
    return menu.addAction(
        *args,
        callback=fields["callback"],
        description=fields["description"] or "",
        tooltip=fields["tooltip"],
        command_id=command_id,
        command_icon=fields["command_icon"],
        open=open_menu,
    )


def _add_checkable_action(menu, label=UNSET, callback=UNSET, checked=False, group=None, **kwargs):
    action = _add_action(menu, label, callback=callback, **kwargs)
    action.setCheckable(True)
    if group is not None:
        group.addAction(action)
    action.setChecked(bool(checked))
    return action


def _add_action_specs(menu, specs):
    actions = []
    for spec in specs:
        if spec is None or spec == "separator":
            menu.addSeparator()
            continue
        actions.append(_add_action(menu, **spec))
    return actions


def build_copy_pose_menu(menu, source_widget=None):
    """Populate the focused right-click menu for the Copy Pose button."""
    _add_action_specs(
        menu,
        [
            {"command_id": "paste_pose"},
            {"command_id": "paste_mirror_pose"},
            "separator",
            {"command_id": "paste_pose_to", "label": "Paste Pose To..."},
            "separator",
            {"command_id": "import_pose_file", "label": "Import Pose"},
            {"command_id": "export_pose_file", "label": "Export Pose"},
        ],
    )
    # This menu replaces the generic actions supplied by the toolbar group.
    return False


def build_copy_animation_menu(menu, source_widget=None):
    """Populate the focused right-click menu for the Copy Animation button."""
    _add_action_specs(
        menu,
        [
            {"command_id": "paste_insert_animation", "label": "Paste Insert"},
            {"command_id": "paste_animation", "label": "Paste Replace"},
            {"command_id": "paste_opposite_animation", "label": "Paste Mirror Animation"},
            "separator",
            {"command_id": "paste_animation_to", "label": "Paste Animation To..."},
            "separator",
            {"command_id": "import_animation_file", "label": "Import Animation"},
            {"command_id": "export_animation_file", "label": "Export Animation"},
        ],
    )
    return False


def _apply_checked_value(setter, value, checked):
    if checked:
        return setter(value)
    return None


def _add_toolbox_action(menu, tool_id):
    from TheKeyMachine.core import toolbox

    if not toolbox.is_tool_available(tool_id):
        return None
    tool = toolbox.get_tool(tool_id)
    action = _add_action(menu, command_id=tool.get("id", tool_id))
    if tool.get("setting_toggle"):
        spec = toolWidgets.setting_toggle_specs().get(tool_id)
        if spec:
            toolCommon.connect_checkable_action(
                action,
                getter=spec["get_checked"],
                setter=spec["set_checked"],
                signal=spec.get("changed_signal"),
            )
    return action


def _add_toolbox_actions(menu, items, source_widget=None):
    source_key = _source_tool_key(source_widget)
    for item in items:
        if item == "separator":
            menu.addSeparator()
        elif item != source_key:
            _add_toolbox_action(menu, item)


def _register_menu_builder(command_id, builder):
    try:
        from TheKeyMachine.mods import shelfMod

        shelfMod.register_menu_builder(command_id, builder)
    except Exception:
        pass


def _add_registered_menu(parent_menu, builder, *, command_id, command_icon=UNSET, description=UNSET):
    _register_menu_builder(command_id, builder)
    from TheKeyMachine.core import toolbox

    explicit = {}
    if command_icon is not UNSET:
        explicit["command_icon"] = command_icon
    if description is not UNSET:
        explicit["description"] = description
    fields = _resolve_action_fields(command_id, toolbox.get_tool, **explicit)
    return parent_menu.addMenu(
        builder(),
        command_id=command_id,
        command_icon=fields["command_icon"],
        description=fields["description"],
    )


def _add_exclusive_setting_actions(menu, specs, current_value, setter, group_attr=None):
    group = QActionGroup(menu)
    group.setExclusive(True)
    if group_attr:
        setattr(menu, group_attr, group)

    for label, value, description in specs:
        _add_checkable_action(
            menu,
            label,
            partial(_apply_checked_value, setter, value),
            checked=value == current_value,
            group=group,
            description=description,
        )
    return group

def _populate_connect_menu(menu, kind):
    spec = connectEntries.source_spec(kind)
    entries = connectEntries.load_entries(kind, notify=True)
    menu.clear()

    for entry in entries:
        if entry["type"] == "separator":
            continue
        menu.addAction(
            QtGui.QIcon(entry["icon"]) if entry["icon"] else QtGui.QIcon(),
            entry["label"],
            callback=entry["callback"],
            tooltip_enabled=False,
        )

    menu.addSeparator()
    menu.addAction(
        QtGui.QIcon(icons.settings),
        "Open config file",
        callback=lambda: general.open_file(spec["folder"], spec["file"]),
        description="Open the {} configuration file.".format(spec["label"]),
    )


def build_custom_tools_menu(menu, source_widget=None):
    _populate_connect_menu(menu, "tools")


def build_custom_scripts_menu(menu, source_widget=None):
    _populate_connect_menu(menu, "scripts")


def build_background_runners_menu(menu, source_widget=None):
    _ = source_widget
    for runner_id, spec in backgroundRunners.get_runner_specs().items():
        getter = spec.get("get_enabled")
        action = _add_checkable_action(
            menu,
            spec.get("label", runner_id),
            partial(backgroundRunners.set_runner_enabled, runner_id),
            checked=getter() if callable(getter) else False,
            icon=spec.get("icon"),
            description=spec.get("description") or "",
            open_menu=True,
        )

        signal = spec.get("changed_signal")
        if signal is not None and callable(getter):
            toolCommon.replace_tracked_connection(
                action,
                "_tkm_background_runner_action_sync",
                signal,
                lambda *_args, target=action, state_fn=getter: toolCommon.set_checked_safely(target, state_fn()),
                parent=action,
            )
    return False


def build_graph_extra_tools_menu(menu, source_widget=None):
    _add_toolbox_actions(
        menu,
        (
            "graph_select_object_from_curve",
            "graph_isolate_curves",
            "separator",
            "graph_flip",
            "graph_overlap_forward",
            "graph_overlap_backward",
            "separator",
            "graph_toggle_mute",
            "graph_toggle_lock",
        ),
        source_widget,
    )


def build_share_keys_menu(menu, source_widget=None):
    _add_exclusive_setting_actions(
        menu,
        (
            (
                "Keep Tangent Type",
                keyTools.SHARE_KEYS_MODE_PRESERVE_TANGENT,
                "Add missing keys without changing tangent type.",
            ),
            (
                "Keep Anim Curve Shape",
                keyTools.SHARE_KEYS_MODE_PRESERVE_SHAPE,
                "Insert missing keys while preserving animation curve shape.",
            ),
        ),
        keyTools.get_share_keys_mode(),
        keyTools.set_share_keys_mode,
    )
    menu.addSeparator()
    _add_toolbox_actions(menu, ("share_keys", "reblock", "separator", "share_keys_from_last_selected"), source_widget)
    return False


def build_bake_menu(menu, source_widget=None):
    _add_exclusive_setting_actions(
        menu,
        (
            (
                "Bake To Step Tangent",
                keyTools.BAKE_TANGENT_MODE_STEP,
                "Bake keys, then turn baked tangents to stepped.",
            ),
            (
                "Keep Tangent Type",
                keyTools.BAKE_TANGENT_MODE_KEEP_TYPE,
                "Bake keys without forcing the baked keys to stepped tangents.",
            ),
            (
                "Keep Animation Curve Shapes",
                keyTools.BAKE_TANGENT_MODE_KEEP_SHAPE,
                "Bake while preserving animation curve shapes where Maya can do so.",
            ),
        ),
        keyTools.get_bake_tangent_mode(),
        keyTools.set_bake_tangent_mode,
        group_attr="_tkm_bake_tangent_group",
    )
    menu.addSeparator()
    _add_toolbox_actions(
        menu,
        (
            "bake_animation_1",
            "bake_animation_2",
            "bake_animation_3",
            "bake_animation_4",
            "bake_animation_custom",
            "separator",
            "bake_animation_from_last_selected",
        ),
        source_widget,
    )
    return False


def build_tangent_menu(menu, tangent_type, tangent_label, icon=None, source_widget=None, maya_default_tangent=False):
    import TheKeyMachine.mods.barMod as bar

    tint_color = cw.get_widget_tint_color(source_widget)

    def _set_tangent(handle_mode, key_scope, tint):
        if tangent_type == "bouncy":
            return keyTools.bouncy_tangents(
                handle_mode=handle_mode,
                key_scope=key_scope,
                tint_color=tint,
            )

        return bar.set_tangent(
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
        bar.set_maya_default_tangent(tangent_type)

    if tangent_type != "step":
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
    _ = source_widget
    for target_key, label in (("first", "First Key"), ("last", "Last Key")):
        _add_action(
            menu,
            label,
            partial(keyTools.match_curve_cycle, target_key=target_key),
            icon=icon,
            description="Match the cycle on the {}.".format(label.lower()),
        )


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
        QtGui.QIcon(icons.tracer),
        "Auto Update",
        description="Keep the tracer connected for live updates.",
        tooltip=helper.tracer_connected_tooltip_text,
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
    _add_action_specs(
        menu,
        (
            {"command_id": "tracer_refresh"},
            {"command_id": "tracer_show_hide"},
            {"command_id": "tracer_offset_node"},
        ),
    )

    menu.addSeparator()
    style_menu = cw.MenuWidget(QtGui.QIcon(icons.tracer), "Style", menu, description="Choose the active tracer trail display style.")
    menu.addMenu(style_menu, description="Choose the active tracer trail display style.")
    _add_action_specs(
        style_menu,
        (
            {"command_id": "tracer_grey"},
            {"command_id": "tracer_red"},
            {"command_id": "tracer_blue"},
        ),
    )

    menu.addSeparator()
    _add_action(menu, command_id="tracer_remove")


def _build_nudge_menu(menu, direction):
    tool_ids = (
        ("nudge_left_all_keys", "nudge_left_scene", "nudge_remove_inbetween", "nudge_remove_inbetween_scene")
        if direction == "left"
        else ("nudge_right_all_keys", "nudge_right_scene", "nudge_insert_inbetween", "nudge_insert_inbetween_scene")
    )
    _add_toolbox_actions(menu, tool_ids[:2])
    menu.addSeparator()
    _add_toolbox_actions(menu, tool_ids[2:])
    return False


def build_nudge_left_menu(menu, source_widget=None):
    _ = source_widget
    return _build_nudge_menu(menu, "left")


def build_nudge_right_menu(menu, source_widget=None):
    _ = source_widget
    return _build_nudge_menu(menu, "right")


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


def _dock_toolbar(toolbar, checked, **target):
    if checked:
        toolbar.dock_to_ui(**target)


def build_main_dock_menu(toolbar):
    toolbar.dock_menu = cw.MenuWidget(QtGui.QIcon(icons.dock), "Dock", description="Move the toolbar to a different Maya area.")

    toolbar.pos_ac_group = QActionGroup(toolbar)
    toolbar.pos_ac_group.setExclusive(True)
    for orient, name in toolbar.docking_orients.items():
        is_current = orient == toolbar.docking_position[1]
        ori_btn = _add_checkable_action(
            toolbar.dock_menu,
            name,
            partial(_dock_toolbar, toolbar, orient=orient),
            checked=is_current,
            group=toolbar.pos_ac_group,
            description="Place the toolbar on the {} side.".format(name.lower()),
        )
        if is_current:
            ori_btn.setEnabled(False)

    toolbar.dock_menu.addSeparator()

    toolbar.dock_ac_group = QActionGroup(toolbar)
    toolbar.dock_ac_group.setExclusive(True)
    for layout, name in toolbar.docking_layouts.items():
        is_current = layout == toolbar.docking_position[0]
        dock_btn = _add_checkable_action(
            toolbar.dock_menu,
            name,
            partial(_dock_toolbar, toolbar, layout=layout),
            checked=is_current,
            group=toolbar.dock_ac_group,
            description="Dock the toolbar in {}.".format(name),
        )
        if is_current:
            dock_btn.setEnabled(False)

    toolbar.dock_menu.aboutToShow.connect(partial(sync_main_dock_menu, toolbar))
    return toolbar.dock_menu


def build_toolbar_pinning_menu(parent_widget, toolbar_widget):
    menu = cw.MenuWidget(parent_widget, tearoff=False)
    menu.addAction(cw.LogoAction(menu, clickable=False))
    
    sections = getattr(toolbar_widget, "_tkm_sections", []) or []
    for section in sections:
        if not wutil.is_valid_widget(section) or not getattr(section, "has_pinnable_items", lambda: False)():
            continue

        icon_path = getattr(section, "menu_icon", lambda: None)()
        label = getattr(section, "menu_label", lambda: "Tools")().replace("&", "&&")
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
        icon=icons.warning,
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


def _add_alignment_actions(menu, current_alignment, apply_alignment_fn, names=TOOLBAR_ALIGNMENT_NAMES):
    group = QActionGroup(menu)
    group.setExclusive(True)
    actions = {}
    for label in names:
        actions[label] = _add_checkable_action(
            menu,
            TOOLBAR_ALIGNMENT_LABEL % label,
            partial(_apply_checked_value, apply_alignment_fn, label),
            checked=label == current_alignment,
            group=group,
            description=TOOLBAR_ALIGNMENT_DESC % label.lower(),
        )
    return group, actions


def _add_toolbar_pinning_footer(menu, toolbar_widget, sections):
    menu.addSeparator()

    setting_key, apply_alignment_fn = _toolbar_alignment_context(toolbar_widget)
    current_align = settings.get_setting(setting_key, "Center")
    menu._tkm_alignment_group, menu._tkm_alignment_actions = _add_alignment_actions(
        menu,
        current_align,
        apply_alignment_fn,
        names=("Left", "Right", "Center"),
    )

    menu.addSeparator()
    menu.addAction(
        QtGui.QIcon(icons.reload),
        "Restore Defaults",
        lambda: _restore_toolbar_pinning_defaults(menu, toolbar_widget, sections, apply_alignment_fn),
        description="Restore toolbar pins and alignment defaults.",
    )

    graph_toolbar_action = menu.addAction(
        QtGui.QIcon(icons.customGraph),
        "Graph Editor Toolbar",
        description="Show or hide the TKM toolbar inside the Graph Editor.",
    )
    toolCommon.connect_checkable_action(
        graph_toolbar_action,
        getter=graphToolbarApi.get_graph_toolbar_checkbox_state,
        setter=lambda state: graphToolbarApi.set_graph_toolbar_enabled(bool(state)),
        signal=graphToolbarApi.custom_graph_bus.graph_toolbar_enabled_changed,
    )


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


def build_other_sources_help_menu():
    help_menu = cw.MenuWidget(QtGui.QIcon(icons.help), "Help")
    if general.config.get("BUG_REPORT", True):
        _add_toolbox_actions(help_menu, ("bug_report_window",))
        help_menu.addSeparator()
    links = (
        ("Discord", icons.discord, "https://discord.gg/G2J5yyjz", "Open the community server."),
        ("Documentation", icons.help, "https://thekeymachine.gitbook.io/base", "Open the docs."),
        ("YouTube", icons.youtube, "https://www.youtube.com/@TheKeyMachineAnimationTools", "Watch tutorials and demos."),
    )
    _add_action_specs(
        help_menu,
        (
            {
                "label": label,
                "icon": icon,
                "callback": partial(general.open_url, url),
                "description": description,
            }
            for label, icon, url, description in links
        ),
    )
    return help_menu


def add_other_sources_help_menu(parent_menu):
    return _add_registered_menu(
        parent_menu,
        build_other_sources_help_menu,
        command_id="help_menu",
    )


def build_main_system_menu(toolbar):
    system_menu = cw.MenuWidget(QtGui.QIcon(icons.system), "System")
    _add_action_specs(
        system_menu,
        (
            {
                "callback": toolbar.reload,
                "command_id": "toolbar_reload",
            },
            {
                "callback": toolbar.unload,
                "command_id": "toolbar_unload",
            },
            {"command_id": "toolbar_uninstall"},
        ),
    )
    return system_menu


def add_main_system_menu(toolbar, parent_menu):
    return _add_registered_menu(
        parent_menu,
        partial(build_main_system_menu, toolbar),
        command_id="main_system_menu",
    )


def build_main_preferences_menu(
    toolbar,
    show_tooltips,
    toolbar_alignment,
    update_toolbar_icon_alignment,
):
    preferences_menu = cw.OpenMenuWidget(QtGui.QIcon(icons.settings), "Preferences")
    preferences_menu.addSection("Startup")
    _add_action(
        preferences_menu,
        "Create a Shelf Button",
        toolbar.create_shelf_icon,
        command_id="toolbar_add_shelf_button",
    )

    _add_checkable_action(
        preferences_menu,
        command_id="start_with_maya",
        checked=ui.check_userSetup(),
    )

    _add_checkable_action(
        preferences_menu,
        command_id="show_tooltips",
        checked=show_tooltips,
    )

    preferences_menu.addSection("Alignment")
    align_group = QActionGroup(preferences_menu)
    align_group.setExclusive(True)
    for align_name, align_value in TOOLBAR_ALIGNMENTS.items():
        _add_checkable_action(
            preferences_menu,
            TOOLBAR_ALIGNMENT_LABEL % align_name,
            partial(_apply_checked_value, update_toolbar_icon_alignment, align_name),
            checked=align_value == toolbar_alignment,
            group=align_group,
        )

    preferences_menu.addSection("Display")
    return preferences_menu


def add_main_preferences_menu(
    toolbar,
    parent_menu,
    show_tooltips,
    toolbar_alignment,
    update_toolbar_icon_alignment,
):
    # Registered menu builders can outlive the menu that registered them.
    # Resolve mutable preferences when the builder is invoked, not here.
    def builder():
        return build_main_preferences_menu(
            toolbar,
            show_tooltips=settings.get_setting("show_tooltips", True),
            toolbar_alignment=toolWidgets.get_main_toolbar_icon_alignment(),
            update_toolbar_icon_alignment=update_toolbar_icon_alignment,
        )

    return _add_registered_menu(
        parent_menu,
        builder,
        command_id="main_preferences_menu",
    )


def _current_main_toolbar():
    try:
        from TheKeyMachine.core import toolbar as toolbar_module

        return toolbar_module.get_toolbar()
    except Exception:
        return None


def _main_menu_builders(toolbar):
    alignment_callback = partial(toolWidgets.set_main_toolbar_icon_alignment, toolbar)
    common = {
        "show_tooltips": settings.get_setting("show_tooltips", True),
        "toolbar_alignment": toolWidgets.get_main_toolbar_icon_alignment(),
        "update_toolbar_icon_alignment": alignment_callback,
    }
    return {
        "TKM": partial(
            build_main_settings_menu,
            toolbar,
            None,
            internet_connection=general.config.get("INTERNET_CONNECTION", True),
            **common
        ),
        "main_preferences_menu": partial(build_main_preferences_menu, toolbar, **common),
        "main_system_menu": partial(build_main_system_menu, toolbar),
        "main_dock_menu": partial(build_main_dock_menu, toolbar),
    }


def _graph_menu_builders():
    from TheKeyMachine.core import customGraph

    return {
        "graph_settings_menu": partial(build_graph_settings_submenu, customGraph.applyCustomGraphAlignment),
        "graph_dock_menu": partial(
            build_graph_dock_menu,
            customGraph._DOCK_OPTIONS,
            customGraph._GRAPH_TOOLBAR_DOCK_SETTING,
            customGraph._DOCK_BOTTOM_GRAPH,
            customGraph.moveCustomGraphDock,
        ),
    }


def build_menu_for_shelf(command_id):
    builders = {"help_menu": build_other_sources_help_menu}

    toolbar = _current_main_toolbar()
    if toolbar:
        builders.update(_main_menu_builders(toolbar))

    if command_id in ("graph_settings_menu", "graph_dock_menu"):
        builders.update(_graph_menu_builders())

    builder = builders.get(command_id)
    return builder() if builder else None


def build_main_settings_menu(
    toolbar,
    parent_button,
    show_tooltips,
    toolbar_alignment,
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
        update_toolbar_icon_alignment=update_toolbar_icon_alignment,
    )
    _add_action(toolbar_menu, command_id="hotkeys_window")
    _add_registered_menu(
        toolbar_menu,
        partial(build_main_dock_menu, toolbar),
        command_id="main_dock_menu",
    )
    add_main_system_menu(toolbar, toolbar_menu)
    toolbar_menu.addSeparator()
    add_other_sources_help_menu(toolbar_menu)
    
    _add_toolbox_actions(toolbar_menu, ("donate_window",))
    if internet_connection:
        _add_action(
            toolbar_menu,
            callback=lambda: updater.check_for_updates(parent_button, force=True),
            command_id="check_for_updates",
        )
    _add_action(toolbar_menu, command_id="about_window")
    return toolbar_menu


def build_graph_settings_submenu(apply_alignment_fn):
    settings_menu = cw.MenuWidget(QtGui.QIcon(icons.settings), "Settings", description="Tool configuration and preferences.")

    settings_menu.addSection("Graph toolbar")
    graph_toolbar_action = settings_menu.addAction(
        QtGui.QIcon(icons.customGraph),
        "Graph Editor Toolbar",
        description="Show or hide the TKM toolbar inside the Graph Editor.",
    )
    toolCommon.connect_checkable_action(
        graph_toolbar_action,
        getter=graphToolbarApi.get_graph_toolbar_checkbox_state,
        setter=lambda state: graphToolbarApi.set_graph_toolbar_enabled(bool(state)),
        signal=graphToolbarApi.custom_graph_bus.graph_toolbar_enabled_changed,
    )

    settings_menu.addSection("Toolbar's icons alignment")
    current_align = settings.get_setting("graph_toolbar_alignment", "Center")
    settings_menu._tkm_alignment_group, settings_menu._tkm_alignment_actions = _add_alignment_actions(
        settings_menu,
        current_align,
        apply_alignment_fn,
    )

    settings_menu.addSection("General")
    settings_menu.addAction(
        QtGui.QIcon(icons.close),
        "Close",
        lambda: QtCore.QTimer.singleShot(0, lambda: graphToolbarApi.set_graph_toolbar_enabled(False)),
        description="Hide the TKM Graph Editor toolbar and keep it disabled.",
    )
    return settings_menu


def build_graph_dock_menu(dock_options, dock_setting, default_dock_position, move_dock_fn):
    dock_menu = cw.MenuWidget(QtGui.QIcon(icons.dock), "Dock", description="Move the Graph Editor toolbar.")
    dock_group = QActionGroup(dock_menu)
    dock_group.setExclusive(True)

    dock_actions = {}
    for position, label, description in dock_options:
        dock_actions[position] = _add_checkable_action(
            dock_menu,
            label,
            partial(_apply_checked_value, move_dock_fn, position),
            group=dock_group,
            description=description,
        )

    current_position = settings.get_setting(dock_setting, default_dock_position)
    if current_position not in dock_actions:
        current_position = default_dock_position
    for position, action in dock_actions.items():
        toolCommon.set_checked_safely(action, position == current_position)
    return dock_menu


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
    build_settings_submenu = partial(build_graph_settings_submenu, apply_alignment_fn)
    build_dock_submenu = partial(
        build_graph_dock_menu,
        dock_options,
        dock_setting,
        default_dock_position,
        move_dock_fn,
    )

    _add_registered_menu(
        menu,
        build_settings_submenu,
        command_id="graph_settings_menu",
    )
    _add_registered_menu(
        menu,
        build_dock_submenu,
        command_id="graph_dock_menu",
    )

    _add_action(menu, command_id="hotkeys_window")
    menu.addSeparator()
    add_other_sources_help_menu(menu)

    _add_action(menu, command_id="about_window")
    return menu
