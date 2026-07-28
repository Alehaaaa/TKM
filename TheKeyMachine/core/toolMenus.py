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


def _declared_item_text(item, toolbox_module, fallback_command_id=None):
    """Resolve a declarative menu item's live label/description.

    Menu/dynamic_menu/section headers are declared once as plain Python
    dicts at package-import time, then reused (the same dict object) on
    every rebuild -- so a bare ``"label": "Preferences"`` string never
    picks up a language switch on its own, unlike leaf command items, which
    already re-resolve through ``toolbox.get_tool()`` on every rebuild.

    Two ways for a declared item to opt into translation, without any
    per-package special-casing:
    - ``"command"``/``"id"``: reuse an existing registered tool's own
      label/description (its ``lang.json`` entry), for items that mirror a
      real tool one-to-one (e.g. the "Preferences" submenu mirrors the
      standalone ``main_preferences_menu`` tool).
    - ``"i18n_key"``: look up a chrome-only string (one with no tool id of
      its own, like a plain section header) in ``data/lang/ui.json`` via
      ``i18n.tr()``.
    Neither key present: fall back to the literal ``"label"``/``"description"``,
    unchanged -- every other package's declared menus keep working exactly
    as before.
    """
    label = item.get("label", "")
    description = item.get("description", "")

    command_id = item.get("command") or item.get("id") or fallback_command_id
    if command_id:
        tool = toolbox_module.get_tool(command_id)
        tooltip = tool.get("tooltip")
        label = tool.get("menu_label") or tool.get("label") or label
        description = tool.get("description") or (tooltip if isinstance(tooltip, str) else description)
        return label, description

    i18n_key = item.get("i18n_key")
    if i18n_key:
        from TheKeyMachine.core import i18n

        label = i18n.tr(i18n_key, label)
        description = i18n.tr("{}_desc".format(i18n_key), description)

    return label, description


def build_declared_menu(definition, parent_widget=None, owner_command_id=None):
    """Build a package-declared menu without tool-specific core code."""
    from TheKeyMachine.core import toolbox

    menu_label, menu_description = _declared_item_text(definition, toolbox, fallback_command_id=owner_command_id)
    menu = cw.MenuWidget(
        QtGui.QIcon(definition.get("icon") or ""),
        menu_label,
        parent=parent_widget,
        description=menu_description,
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
            label, _description = _declared_item_text(item, toolbox)
            menu.addSection(label)
            continue
        if item_type == "dynamic_menu":
            builder = item.get("builder")
            if not callable(builder):
                raise TypeError("Declared dynamic menu requires a callable builder")
            label, description = _declared_item_text(item, toolbox)
            child = cw.MenuWidget(
                _qicon(item.get("icon")),
                label,
                parent=menu,
                description=description,
            )
            placeholder = child.addAction("Loading…")
            placeholder.setEnabled(False)
            child.aboutToShow.connect(partial(builder, child))
            menu.addMenu(child, description=description)
            continue
        if item_type == "menu":
            child = build_declared_menu(item, parent_widget=menu)
            _label, description = _declared_item_text(item, toolbox)
            menu.addMenu(child, description=description)
            continue

        command_id = item.get("command") or item.get("id")
        fields = {key: item[key] for key in ("label", "callback", "icon", "description", "tooltip") if key in item}
        if not command_id:
            label, description = _declared_item_text(item, toolbox)
            if "label" in fields:
                fields["label"] = label
            if "description" in fields:
                fields["description"] = description
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
    from TheKeyMachine.core import i18n

    toolbar.dock_menu = cw.MenuWidget(
        QtGui.QIcon(icons.dock),
        i18n.tr("dock_menu", "Dock"),
        description=i18n.tr("dock_menu_desc", "Move the toolbar to a different Maya area."),
    )

    toolbar.pos_ac_group = QtGui.QActionGroup(toolbar)
    toolbar.pos_ac_group.setExclusive(True)
    for orient, name in toolbar.docking_orients.items():
        is_current = orient == toolbar.docking_position[1]
        ori_btn = _add_checkable_action(
            toolbar.dock_menu,
            i18n.tr("dock_orient_{}".format(orient), name),
            toolCommon.mark_non_tool_action(
                partial(_dock_toolbar, toolbar, orient=orient)
            ),
            checked=is_current,
            group=toolbar.pos_ac_group,
            description=i18n.tr(
                "dock_orient_{}_desc".format(orient),
                "Place the toolbar on the {} side.".format(name.lower()),
            ),
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
            i18n.tr("dock_area_{}".format(layout), name),
            toolCommon.mark_non_tool_action(
                partial(_dock_toolbar, toolbar, layout=layout)
            ),
            checked=is_current,
            group=toolbar.dock_ac_group,
            description=i18n.tr(
                "dock_area_{}_desc".format(layout),
                "Dock the toolbar in {}.".format(name),
            ),
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
    from TheKeyMachine.core import i18n

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
        menu.addMenu(section_menu, description=i18n.tr("pin_tools_in", "Pin tools in {}.").format(label))
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

    # This menu is built once and cached for the toolbar's lifetime (see the
    # module docstring above), unlike the System/Preferences/Dock/Help
    # submenus, which are rebuilt fresh on every open and so already pick up
    # a language change on their own. Its alignment labels and "Restore
    # Defaults"/"Graph Editor Toolbar" footer are translated at build time,
    # so a later language switch needs to explicitly drop this cache --
    # tracked per toolbar instance so re-running this (it only ever runs
    # once per toolbar) doesn't stack duplicate connections.
    from TheKeyMachine.core import i18n

    toolCommon.replace_tracked_connection(
        toolbar_widget,
        "_tkm_pinning_menu_language_connection",
        i18n.bus.languageChanged,
        partial(_invalidate_toolbar_pinning_menu, toolbar_widget),
        parent=menu,
    )

    return menu


def _invalidate_toolbar_pinning_menu(toolbar_widget, *_args):
    """Drop the cached pinning menu so its next open rebuilds with the new language."""
    if not wutil.is_valid_widget(toolbar_widget):
        return
    menu = getattr(toolbar_widget, "_tkm_pinning_menu", None)
    toolbar_widget._tkm_pinning_menu = None
    if menu is not None and wutil.is_valid_widget(menu):
        menu.deleteLater()


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
        for ws in toolWorkspaces.list_workspaces():
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


def _workspace_menu_fingerprint():
    """A snapshot of "what the workspace footer should currently show".

    Compared against what a cached pinning menu was built with, so
    ``show_toolbar_pinning_menu`` can tell -- without any cooperation from
    whatever created/renamed/deleted a workspace -- whether that footer is
    now stale. Includes names (not just ids) so a rename invalidates it too,
    not only an add/remove.
    """
    from TheKeyMachine.core import toolWorkspaces

    return tuple((ws["id"], ws["name"]) for ws in toolWorkspaces.list_workspaces())


def show_toolbar_pinning_menu(toolbar_widget, global_pos):
    """Show the toolbar's pinning menu for this context request.

    The menu is built once per toolbar instance and cached on the widget,
    since the toolbox's tool set never changes while the toolbar is alive.
    Later right-clicks just refresh the state that *can* change between
    openings (pins, active workspace, alignment) instead of tearing down
    and rebuilding every submenu/action/icon from scratch.

    The one part of it that isn't fixed for the toolbar's lifetime is its
    workspace footer: workspaces can be created, renamed, or deleted at any
    time from the Workspaces editor, and a plain label refresh can't add or
    remove an action. Rather than relying on every place that mutates the
    workspace list to remember to invalidate this cache, the cached menu is
    fingerprinted at build time and compared against the live workspace list
    on every open -- any difference (add, remove, or rename) drops the whole
    cached menu and forces the fresh rebuild below.
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

    if (
        menu is not None
        and getattr(menu, "_tkm_workspace_fingerprint", None) != _workspace_menu_fingerprint()
    ):
        menu.deleteLater()
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
    from TheKeyMachine.core import i18n, toolWorkspaces
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
            i18n.tr("align_{}_label".format(label.lower()), TOOLBAR_ALIGNMENT_LABEL % label),
            toolCommon.mark_non_tool_action(partial(apply_align, a=label)),
            checked=label == current_alignment,
            group=group,
            description=i18n.tr("align_{}_desc".format(label.lower()), TOOLBAR_ALIGNMENT_DESC % label.lower()),
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
    from TheKeyMachine.tools.workspaces import controller as workspacesController

    group = QtGui.QActionGroup(menu)
    group.setExclusive(True)
    actions = {}

    active_ws = toolWorkspaces.get_active_workspace()

    for ws in toolWorkspaces.list_workspaces():
        label, is_current = _workspace_action_state(ws, active_ws)

        # Built-in and custom workspaces apply through the same one call:
        # the Workspaces editor's controller already knows how to tell them
        # apart (a custom one replays its saved snapshot; a built-in one
        # uses the fixed defaults these very ``sections``/``apply_alignment_fn``
        # would otherwise be needed for), so this menu doesn't need its own
        # copy of that branch.
        def apply_ws(checked, ws_id=ws["id"]):
            if checked:
                workspacesController.apply_workspace(ws_id)

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
    from TheKeyMachine.core import i18n

    menu.addSeparator()

    setting_key, apply_alignment_fn = _toolbar_alignment_context(toolbar_widget)
    menu._tkm_alignment_setting_key = setting_key

    menu._tkm_workspace_group, menu._tkm_workspace_actions = _add_workspace_actions(menu, sections, apply_alignment_fn)
    menu._tkm_workspace_fingerprint = _workspace_menu_fingerprint()

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
        i18n.tr("restore_defaults", "Restore Defaults"),
        restore_defaults_callback,
        description=i18n.tr("restore_defaults_desc", "Restore toolbar pins and alignment defaults."),
    )

    graph_toolbar_action = menu.addAction(
        QtGui.QIcon(icons.customGraph),
        i18n.tr("graph_editor_toolbar", "Graph Editor Toolbar"),
        description=i18n.tr("graph_editor_toolbar_desc", "Show or hide the TKM toolbar inside the Graph Editor."),
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
    from TheKeyMachine.core import i18n

    help_menu = cw.MenuWidget(QtGui.QIcon(icons.help), i18n.tr("help_menu", "Help"))
    if general.config.get("BUG_REPORT", True):
        _add_toolbox_actions(help_menu, ("bug_report_window",))
        help_menu.addSeparator()
    links = (
        (
            i18n.tr("discord", "Discord"), icons.discord, "https://discord.gg/G2J5yyjz",
            i18n.tr("discord_desc", "Open the community server."),
        ),
        (
            i18n.tr("documentation", "Documentation"), icons.help, "https://thekeymachine.gitbook.io/base",
            i18n.tr("documentation_desc", "Open the docs."),
        ),
        (
            i18n.tr("youtube", "YouTube"), icons.youtube, "https://www.youtube.com/@TheKeyMachineAnimationTools",
            i18n.tr("youtube_desc", "Watch tutorials and demos."),
        ),
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


def populate_languages_menu(menu):
    """(Re)fill the Languages submenu in place: current state, freshly resolved.

    Shared by the standalone System button's submenu (built fresh on every
    open via ``_add_registered_menu``, like its System/Preferences/Dock/Help
    siblings) and the TKM logo mega-menu's nested "System" > "Languages"
    ``dynamic_menu`` slot -- one implementation, so the two surfaces can't
    drift apart.
    """
    from TheKeyMachine.core import i18n

    menu.clear()
    menu._tkm_language_fingerprint = (i18n.get_language(), i18n.get_translate_tool_names())

    _add_checkable_action(
        menu,
        i18n.tr("translate_tool_names_label", "Translate Tool Names"),
        toolCommon.mark_non_tool_action(
            lambda checked: i18n.set_translate_tool_names(checked)
        ),
        checked=i18n.get_translate_tool_names(),
        description=i18n.tr(
            "translate_tool_names_desc",
            "Also translate tool names, not just descriptions and messages.",
        ),
    )

    menu.addSeparator()

    group = QtGui.QActionGroup(menu)
    group.setExclusive(True)
    current_language = i18n.get_language()
    for code, info in i18n.available_languages().items():
        _add_checkable_action(
            menu,
            info.get("native") or info.get("name") or code,
            toolCommon.mark_non_tool_action(
                partial(_apply_checked_value, i18n.set_language, code)
            ),
            checked=code == current_language,
            group=group,
            description="{} ({})".format(info.get("name") or code, code),
            open_menu=True,
        )
    return menu


def build_languages_menu():
    from TheKeyMachine.core import i18n

    menu = cw.MenuWidget(QtGui.QIcon(icons.globe), i18n.tr("languages_menu", "Languages"))
    populate_languages_menu(menu)
    return menu


def build_main_system_menu(toolbar):
    from TheKeyMachine.core import i18n

    system_menu = cw.MenuWidget(QtGui.QIcon(icons.system), i18n.tr("system_menu", "System"))
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
    system_menu.addSeparator()
    _add_registered_menu(
        system_menu,
        build_languages_menu,
        command_id="languages_menu",
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
    from TheKeyMachine.core import i18n

    preferences_menu = cw.OpenMenuWidget(QtGui.QIcon(icons.settings), i18n.tr("preferences_menu", "Preferences"))
    preferences_menu.addSection(i18n.tr("startup_section", "Startup"))
    _add_action(
        preferences_menu,
        i18n.tr("create_shelf_button", "Create a Shelf Button"),
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

    preferences_menu.addSection(i18n.tr("alignment_section", "Alignment"))
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

    preferences_menu.addSection(i18n.tr("display_section", "Display"))
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
        "languages_menu": build_languages_menu,
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
    _add_action(toolbar_menu, command_id="workspaces_window")
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
    from TheKeyMachine.core import i18n

    settings_menu = cw.MenuWidget(
        QtGui.QIcon(icons.settings),
        i18n.tr("settings_menu", "Settings"),
        description=i18n.tr("settings_menu_desc", "Tool configuration and preferences."),
    )

    settings_menu.addSection(i18n.tr("graph_toolbar_section", "Graph toolbar"))
    graph_toolbar_action = settings_menu.addAction(
        QtGui.QIcon(icons.customGraph),
        i18n.tr("graph_editor_toolbar", "Graph Editor Toolbar"),
        description=i18n.tr("graph_editor_toolbar_desc", "Show or hide the TKM toolbar inside the Graph Editor."),
    )
    toolCommon.connect_checkable_action(
        graph_toolbar_action,
        getter=graphToolbarApi.get_graph_toolbar_checkbox_state,
        setter=lambda state: graphToolbarApi.set_graph_toolbar_enabled(bool(state)),
        signal=graphToolbarApi.custom_graph_bus.graph_toolbar_enabled_changed,
    )

    settings_menu.addSection(i18n.tr("toolbar_icons_alignment_section", "Toolbar's icons alignment"))
    current_align = settings.get_setting("graph_toolbar_alignment", "Center")
    settings_menu._tkm_alignment_group, settings_menu._tkm_alignment_actions = _add_alignment_actions(
        settings_menu,
        current_align,
        apply_alignment_fn,
    )

    settings_menu.addSection(i18n.tr("general_section", "General"))
    settings_menu.addAction(
        QtGui.QIcon(icons.close),
        i18n.tr("close", "Close"),
        toolCommon.mark_non_tool_action(
            lambda: QtCore.QTimer.singleShot(
                0, lambda: graphToolbarApi.set_graph_toolbar_enabled(False)
            )
        ),
        description=i18n.tr("close_graph_toolbar_desc", "Hide the TKM Graph Editor toolbar and keep it disabled."),
    )
    return settings_menu


def build_graph_dock_menu(dock_options, dock_setting, default_dock_position, move_dock_fn):
    from TheKeyMachine.core import i18n

    dock_menu = cw.MenuWidget(
        QtGui.QIcon(icons.dock),
        i18n.tr("dock_menu", "Dock"),
        description=i18n.tr("graph_dock_menu_desc", "Move the Graph Editor toolbar."),
    )
    dock_group = QtGui.QActionGroup(dock_menu)
    dock_group.setExclusive(True)

    dock_actions = {}
    for position, label, description in dock_options:
        dock_actions[position] = _add_checkable_action(
            dock_menu,
            i18n.tr("graph_dock_{}".format(position), label),
            toolCommon.mark_non_tool_action(
                partial(_apply_checked_value, move_dock_fn, position)
            ),
            group=dock_group,
            description=i18n.tr("graph_dock_{}_desc".format(position), description),
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
