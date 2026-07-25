from functools import partial
import warnings

from maya import cmds

from TheKeyMachine.core.Qt import QtCore, QtGui, QtWidgets

import TheKeyMachine.mods.generalMod as general
from TheKeyMachine.data import icons
import TheKeyMachine.mods.settingsMod as settings
import TheKeyMachine.mods.shelfMod as shelf
import TheKeyMachine.mods.updater as updater
import TheKeyMachine.core.toolWidgets as toolWidgets
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
                "callback": None if tool.get("type") == "setting" else tool.get("callback"),
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
    if tool.get("type") == "setting":
        spec = toolWidgets.setting_specs().get(tool_id)
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


def build_declared_menu(definition, parent_widget=None):
    """Build a package-declared menu without tool-specific core code."""
    from TheKeyMachine.core import toolbox

    menu = cw.MenuWidget(
        QtGui.QIcon(definition.get("icon") or ""),
        definition.get("label", ""),
        parent=parent_widget,
        description=definition.get("description", ""),
    )
    for item in definition.get("items", ()):
        if item == "separator":
            menu.addSeparator()
            continue
        if isinstance(item, str):
            _add_toolbox_action(menu, item)
            continue
        available = item.get("available", True)
        if not bool(available() if callable(available) else available):
            continue
        if item.get("separator_before"):
            menu.addSeparator()
        item_type = item.get("type", "command")
        if item_type == "widget":
            factory = item.get("factory")
            if not callable(factory):
                raise TypeError("Declared menu widget requires a callable factory")
            action = factory(menu, **dict(item.get("kwargs") or {}))
            if action is not None:
                menu.addAction(action)
            continue
        if item_type == "choice":
            getter = item.get("get_value")
            setter = item.get("set_value")
            if not callable(getter) or not callable(setter):
                raise TypeError("Declared menu choice requires get_value and set_value")
            current_value = getter()
            group = QtGui.QActionGroup(menu)
            group.setExclusive(True)
            choice_groups = getattr(menu, "_tkm_choice_groups", None)
            if choice_groups is None:
                choice_groups = []
                menu._tkm_choice_groups = choice_groups
            choice_groups.append(group)
            choices = item.get("items", ())
            if callable(choices):
                choices = choices()
            for choice in choices:
                value = choice.get("value")
                _add_checkable_action(
                    menu,
                    choice.get("label", str(value)),
                    toolCommon.mark_non_tool_action(
                        partial(_apply_checked_value, setter, value)
                    ),
                    checked=value == current_value,
                    group=group,
                    description=choice.get("description", ""),
                    open_menu=True,
                )
            continue
        if item_type == "section":
            menu.addSection(item.get("label", ""))
            continue
        if item_type == "dynamic_menu":
            builder = item.get("builder")
            if not callable(builder):
                raise TypeError("Declared dynamic menu requires a callable builder")
            child = cw.MenuWidget(
                _qicon(item.get("icon")),
                item.get("label", ""),
                parent=menu,
                description=item.get("description", ""),
            )
            placeholder = child.addAction("Loading…")
            placeholder.setEnabled(False)
            child.aboutToShow.connect(partial(builder, child))
            menu.addMenu(child, description=item.get("description", ""))
            continue
        if item_type == "menu":
            child = build_declared_menu(item, parent_widget=menu)
            menu.addMenu(child, description=item.get("description", ""))
            continue

        command_id = item.get("command") or item.get("id")
        fields = {key: item[key] for key in ("label", "callback", "icon", "description", "tooltip") if key in item}
        if item_type == "check":
            tool = toolbox.get_tool(command_id, **fields) if command_id else fields
            action = _add_checkable_action(
                menu,
                label=tool.get("label", ""),
                callback=tool.get("set_checked") or tool.get("callback"),
                icon=tool.get("icon"),
                description=tool.get("description", ""),
                tooltip=tool.get("tooltip"),
                checked=bool((tool.get("get_checked") or item.get("get_checked") or (lambda: False))()),
            )
            signal = tool.get("changed_signal") or item.get("changed_signal")
            if signal is not None:
                toolCommon.connect_checkable_action(
                    action,
                    getter=tool.get("get_checked"),
                    setter=tool.get("set_checked") or tool.get("callback"),
                    signal=signal,
                )
            continue
        _add_action(menu, command_id=command_id, **fields)
    return menu


def sync_main_dock_menu(toolbar):
    if not wutil.is_valid_widget(getattr(toolbar, "dock_menu", None)):
        return

    for action in toolbar.dock_menu.actions():
        orient = next(
            (
                key
                for key, name in toolbar.docking_orients.items()
                if name == action.text()
            ),
            None,
        )
        if orient:
            is_current = orient == toolbar.docking_position[1]
            action.setChecked(is_current)
            action.setEnabled(not is_current)
            continue
        layout = next((key for key, name in toolbar.docking_layouts.items() if name == action.text()), None)
        if layout:
            is_current = layout == toolbar.docking_position[0]
            action.setChecked(is_current)
            action.setEnabled(
                not is_current and wutil.check_visible_layout(layout)
            )


def _dock_toolbar(toolbar, checked, **target):
    if checked:
        toolbar.dock_to_ui(**target)


def build_main_dock_menu(toolbar):
    toolbar.dock_menu = cw.MenuWidget(QtGui.QIcon(icons.dock), "Dock", description="Move the toolbar to a different Maya area.")

    toolbar.pos_ac_group = QtGui.QActionGroup(toolbar)
    toolbar.pos_ac_group.setExclusive(True)
    for orient, name in toolbar.docking_orients.items():
        is_current = orient == toolbar.docking_position[1]
        ori_btn = _add_checkable_action(
            toolbar.dock_menu,
            name,
            toolCommon.mark_non_tool_action(
                partial(_dock_toolbar, toolbar, orient=orient)
            ),
            checked=is_current,
            group=toolbar.pos_ac_group,
            description="Place the toolbar on the {} side.".format(name.lower()),
        )
        if is_current:
            ori_btn.setEnabled(False)

    toolbar.dock_menu.addSeparator()

    toolbar.dock_ac_group = QtGui.QActionGroup(toolbar)
    toolbar.dock_ac_group.setExclusive(True)
    for layout, name in toolbar.docking_layouts.items():
        is_current = layout == toolbar.docking_position[0]
        dock_btn = _add_checkable_action(
            toolbar.dock_menu,
            name,
            toolCommon.mark_non_tool_action(
                partial(_dock_toolbar, toolbar, layout=layout)
            ),
            checked=is_current,
            group=toolbar.dock_ac_group,
            description="Dock the toolbar in {}.".format(name),
        )
        if is_current:
            dock_btn.setEnabled(False)

    toolbar.dock_menu.aboutToShow.connect(partial(sync_main_dock_menu, toolbar))
    return toolbar.dock_menu


def build_toolbar_pinning_menu(parent_widget, toolbar_widget):
    """Build the pinning menu's structure: submenus, actions, icons, connections.

    The available tools are fixed once the toolbar is populated, so this is
    meant to run once per toolbar instance. Per-open state (pin checkmarks,
    active workspace, current alignment) is not baked in here; it is applied
    by ``refresh_toolbar_pinning_menu`` right before the (cached) menu pops
    back up.
    """
    menu = cw.MenuWidget(parent_widget, tearoff=False)
    from TheKeyMachine.tools.tkm_menu import api as tkmMenuApi

    menu.addAction(tkmMenuApi.create_logo_action(menu, clickable=False))

    sections = getattr(toolbar_widget, "_tkm_sections", []) or []
    menu._tkm_section_menus = []
    for section in sections:
        if not wutil.is_valid_widget(section) or not getattr(section, "has_pinnable_items", lambda: False)():
            continue

        icon_path = getattr(section, "menu_icon", lambda: None)()
        label = getattr(section, "menu_label", lambda: "Tools")().replace("&", "&&")
        section_menu = cw.OpenMenuWidget(QtGui.QIcon(icon_path or ""), label)
        section.populate_pinning_menu(section_menu)
        menu.addMenu(section_menu, description="Pin tools in {}.".format(label))
        menu._tkm_section_menus.append((section, section_menu))

    if sections:
        from TheKeyMachine.core import toolWorkspaces
        def on_pins_changed(*args, **kwargs):
            is_deviating = toolWorkspaces.is_current_workspace_deviating(sections)
            toolWorkspaces.mark_workspace_modified(is_deviating)

        for section in sections:
            if hasattr(section, "pinsChanged"):
                toolCommon.replace_tracked_connection(
                    section,
                    "_tkm_toolbar_workspace_pin_connection",
                    section.pinsChanged,
                    on_pins_changed,
                    parent=menu,
                )

        _add_toolbar_pinning_footer(menu, toolbar_widget, sections)

    return menu


def refresh_toolbar_pinning_menu(menu, toolbar_widget):
    """Resync a cached pinning menu's per-open state without rebuilding it.

    Only checkmarks/labels that can drift between two openings of the same
    menu are touched here: pin state per tool, the active workspace, and the
    current icon alignment. No actions, icons, or connections are recreated.
    """
    if not wutil.is_valid_widget(menu):
        return

    for section, section_menu in getattr(menu, "_tkm_section_menus", ()):
        if wutil.is_valid_widget(section) and wutil.is_valid_widget(section_menu):
            section._sync_pin_menu_actions(section_menu)

    _refresh_toolbar_pinning_footer(menu, toolbar_widget)


def _refresh_toolbar_pinning_footer(menu, toolbar_widget):
    from TheKeyMachine.core import toolWorkspaces

    workspace_actions = getattr(menu, "_tkm_workspace_actions", None) or {}
    if workspace_actions:
        active_ws = toolWorkspaces.get_active_workspace()
        for ws in toolWorkspaces.WORKSPACES:
            action = workspace_actions.get(ws["id"])
            if not wutil.is_valid_widget(action):
                continue
            label, is_current = _workspace_action_state(ws, active_ws)
            blocked = action.blockSignals(True)
            try:
                action.setText(label)
                action.setChecked(is_current)
            finally:
                action.blockSignals(blocked)

    alignment_actions = getattr(menu, "_tkm_alignment_actions", None) or {}
    setting_key = getattr(menu, "_tkm_alignment_setting_key", None)
    if alignment_actions and setting_key and wutil.is_valid_widget(toolbar_widget):
        current_align = settings.get_setting(setting_key, "Center")
        for label, action in alignment_actions.items():
            if not wutil.is_valid_widget(action):
                continue
            blocked = action.blockSignals(True)
            try:
                action.setChecked(label == current_align)
            finally:
                action.blockSignals(blocked)


def show_toolbar_pinning_menu(toolbar_widget, global_pos):
    """Show the toolbar's pinning menu for this context request.

    The menu is built once per toolbar instance and cached on the widget,
    since the toolbox's tool set never changes while the toolbar is alive.
    Later right-clicks just refresh the state that *can* change between
    openings (pins, active workspace, alignment) instead of tearing down
    and rebuilding every submenu/action/icon from scratch.
    """
    if not wutil.is_valid_widget(toolbar_widget):
        return False
    closed_at = getattr(toolbar_widget, "_tkm_pinning_menu_closed_at", 0)
    if QtCore.QDateTime.currentMSecsSinceEpoch() - closed_at < 150:
        return True

    menu = getattr(toolbar_widget, "_tkm_pinning_menu", None)
    if menu is not None and not wutil.is_valid_widget(menu):
        menu = None
        toolbar_widget._tkm_pinning_menu = None

    if menu is not None and menu.isVisible():
        return True

    if menu is None:
        menu = build_toolbar_pinning_menu(toolbar_widget, toolbar_widget)
        if not menu.actions():
            menu.deleteLater()
            return False

        def _on_menu_closed():
            if wutil.is_valid_widget(toolbar_widget):
                toolbar_widget._tkm_pinning_menu_closed_at = (
                    QtCore.QDateTime.currentMSecsSinceEpoch()
                )

        menu.aboutToHide.connect(_on_menu_closed)
        toolbar_widget._tkm_pinning_menu = menu
    else:
        refresh_toolbar_pinning_menu(menu, toolbar_widget)

    menu.popup(global_pos)
    return True


def _toolbar_alignment_context(toolbar_widget):
    is_graph_toolbar = toolbar_widget.objectName() == "tkm_customGraph_flowToolbar"
    setting_key = "graph_toolbar_alignment" if is_graph_toolbar else "toolbar_icon_alignment"

    def _apply_alignment(alignment_label):
        settings.set_setting(setting_key, alignment_label)

        if is_graph_toolbar:
            try:
                from TheKeyMachine.tools.graph_toolbar import api as graph_toolbar_api

                graph_toolbar_api.apply_alignment(alignment_label)
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

    return setting_key, _apply_alignment


def _restore_toolbar_pinning_defaults(menu, toolbar_widget, sections, apply_alignment_fn):
    from TheKeyMachine.widgets import customDialogs
    from TheKeyMachine.core import toolWorkspaces

    # Block pinsChanged on all sections while closing the menu so the
    # deviation check is not triggered N times before the dialog opens.
    for section in sections:
        if hasattr(section, "blockSignals"):
            section.blockSignals(True)
    try:
        menu.close()
    finally:
        for section in sections:
            if hasattr(section, "blockSignals"):
                section.blockSignals(False)

    ws_name = toolWorkspaces.get_active_workspace_name()
    clicked = customDialogs.QFlatConfirmDialog.question(
        menu.parent(),
        "Restore Defaults",
        "Restore the '{}' workspace defaults?".format(ws_name),
        buttons=[customDialogs.QFlatConfirmDialog.Yes, customDialogs.QFlatConfirmDialog.Cancel],
        highlight=customDialogs.QFlatConfirmDialog.Yes,
        title="Restore toolbar defaults?",
        icon=icons.warning,
    )
    if clicked != customDialogs.QFlatConfirmDialog.Yes:
        return

    toolWorkspaces.restore_workspace_defaults(sections, apply_alignment_fn)

    if wutil.is_valid_widget(toolbar_widget):
        layout = toolbar_widget.layout()
        if layout:
            layout.invalidate()
        toolbar_widget.updateGeometry()
        toolbar_widget.update()


def _add_alignment_actions(menu, current_alignment, apply_alignment_fn, sections, names=TOOLBAR_ALIGNMENT_NAMES):
    from TheKeyMachine.core import toolWorkspaces
    group = QtGui.QActionGroup(menu)
    group.setExclusive(True)
    actions = {}
    
    def apply_align(checked, a):
        if checked:
            apply_alignment_fn(a)
            is_deviating = toolWorkspaces.is_current_workspace_deviating(sections, get_alignment_fn=lambda: a)
            toolWorkspaces.mark_workspace_modified(is_deviating)
            
    for label in names:
        actions[label] = _add_checkable_action(
            menu,
            TOOLBAR_ALIGNMENT_LABEL % label,
            toolCommon.mark_non_tool_action(partial(apply_align, a=label)),
            checked=label == current_alignment,
            group=group,
            description=TOOLBAR_ALIGNMENT_DESC % label.lower(),
            open_menu=True,
        )
    return group, actions


def _workspace_action_state(ws, active_ws):
    """Single source of truth for a workspace action's label/checked state.

    Shared by the initial build and by the cached-menu refresh pass so the
    two can never compute this differently.
    """
    from TheKeyMachine.core import toolWorkspaces

    is_current = ws["id"] == active_ws
    label = toolWorkspaces.get_workspace_label(ws["id"]) if is_current else ws["name"]
    return label, is_current


def _add_workspace_actions(menu, sections, apply_alignment_fn):
    from TheKeyMachine.core import toolWorkspaces

    group = QtGui.QActionGroup(menu)
    group.setExclusive(True)
    actions = {}

    active_ws = toolWorkspaces.get_active_workspace()

    for ws in toolWorkspaces.WORKSPACES:
        label, is_current = _workspace_action_state(ws, active_ws)

        def apply_ws(checked, ws_id=ws["id"]):
            if checked:
                toolWorkspaces.apply_workspace(ws_id, sections, apply_alignment_fn)

        actions[ws["id"]] = _add_checkable_action(
            menu,
            label,
            toolCommon.mark_non_tool_action(apply_ws),
            checked=is_current,
            group=group,
            description="Apply the {} workspace.".format(ws["name"]),
            open_menu=True,
        )
    return group, actions

def _add_toolbar_pinning_footer(menu, toolbar_widget, sections):
    menu.addSeparator()

    setting_key, apply_alignment_fn = _toolbar_alignment_context(toolbar_widget)
    menu._tkm_alignment_setting_key = setting_key

    menu._tkm_workspace_group, menu._tkm_workspace_actions = _add_workspace_actions(menu, sections, apply_alignment_fn)

    menu.addSeparator()

    current_align = settings.get_setting(setting_key, "Center")
    menu._tkm_alignment_group, menu._tkm_alignment_actions = _add_alignment_actions(
        menu,
        current_align,
        apply_alignment_fn,
        sections,
    )

    menu.addSeparator()
    restore_defaults_callback = toolCommon.mark_non_tool_action(
        partial(
            _restore_toolbar_pinning_defaults,
            menu,
            toolbar_widget,
            sections,
            apply_alignment_fn,
        )
    )
    menu.addAction(
        QtGui.QIcon(icons.reload),
        "Restore Defaults",
        restore_defaults_callback,
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
            {"command_id": "toolbar_reload"},
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
        shelf.create_main_shelf_button,
        command_id="toolbar_add_shelf_button",
    )

    _add_checkable_action(
        preferences_menu,
        command_id="start_with_maya",
        checked=general.check_userSetup(),
    )

    _add_checkable_action(
        preferences_menu,
        command_id="show_tooltips",
        checked=show_tooltips,
    )

    preferences_menu.addSection("Alignment")
    current_align = "Center"
    for k, v in TOOLBAR_ALIGNMENTS.items():
        if v == toolbar_alignment:
            current_align = k
            break

    preferences_menu._tkm_alignment_group, preferences_menu._tkm_alignment_actions = _add_alignment_actions(
        preferences_menu,
        current_align,
        update_toolbar_icon_alignment,
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
    from TheKeyMachine.tools.graph_toolbar import api as graph_toolbar_api

    return {
        "graph_settings_menu": partial(build_graph_settings_submenu, graph_toolbar_api.apply_alignment),
        "graph_dock_menu": partial(
            build_graph_dock_menu,
            graph_toolbar_api.DOCK_OPTIONS,
            graph_toolbar_api.GRAPH_TOOLBAR_DOCK_SETTING,
            graph_toolbar_api.DOCK_BOTTOM_GRAPH,
            graph_toolbar_api.move_dock,
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
    from TheKeyMachine.tools.tkm_menu import api as tkmMenuApi

    toolbar_menu.addAction(tkmMenuApi.create_logo_action(toolbar_menu))
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
        toolCommon.mark_non_tool_action(
            lambda: QtCore.QTimer.singleShot(
                0, lambda: graphToolbarApi.set_graph_toolbar_enabled(False)
            )
        ),
        description="Hide the TKM Graph Editor toolbar and keep it disabled.",
    )
    return settings_menu


def build_graph_dock_menu(dock_options, dock_setting, default_dock_position, move_dock_fn):
    dock_menu = cw.MenuWidget(QtGui.QIcon(icons.dock), "Dock", description="Move the Graph Editor toolbar.")
    dock_group = QtGui.QActionGroup(dock_menu)
    dock_group.setExclusive(True)

    dock_actions = {}
    for position, label, description in dock_options:
        dock_actions[position] = _add_checkable_action(
            dock_menu,
            label,
            toolCommon.mark_non_tool_action(
                partial(_apply_checked_value, move_dock_fn, position)
            ),
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
    from TheKeyMachine.tools.tkm_menu import api as tkmMenuApi

    menu.addAction(tkmMenuApi.create_logo_action(menu))
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
