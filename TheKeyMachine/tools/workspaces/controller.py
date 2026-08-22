"""

TheKeyMachine - Animation Toolset for Maya Animators


This file is part of TheKeyMachine, an open source software for Autodesk Maya licensed under the GNU General Public License v3.0 (GPL-3.0).
You are free to use, modify, and distribute this code under the terms of the GPL-3.0 license.
By using this code, you agree to keep it open source and share any modifications.
This code is provided "as is," without any warranty. For the full license text, visit https://www.gnu.org/licenses/gpl-3.0.html

https://alehaaaa.github.io/TKM/

Modified by: Alehaaaa / alehaaaa.github.io



"""

"""Reads and writes the live main/graph toolbars for the Workspaces editor.

Nothing here keeps its own copy of pin state: tool pins are always read from
and written to the same ``QFlatSectionWidget`` objects the real toolbar uses
(see ``widgets.toolbar_widgets``/``widgets.toolbar``), so the editor and the toolbar's
own right-click pinning menu can never drift apart.
"""

from TheKeyMachine.data.colors import COLORS
from TheKeyMachine.tools import registry
from TheKeyMachine.ui.widgets import toolbar_widgets
from TheKeyMachine.ui import toolbar_modes
from TheKeyMachine.core import workspaces
from TheKeyMachine.tools.graph_toolbar import controller as graph_toolbar
from TheKeyMachine.core import settings
from TheKeyMachine.ui.widgets import util as wutil


TOOLBARS = (
    {"id": "main", "label": "Main Toolbar"},
    {"id": "graph", "label": "Graph Editor Toolbar"},
)

WORKSPACES_NAMESPACE = workspaces.WORKSPACES_NAMESPACE


def get_toolbars():
    """Live-translated ``TOOLBARS`` for the Toolbar column.

    "Graph Editor Toolbar" reuses the exact same id already translated for
    the toolbar pinning menu's own entry; "Main Toolbar" gets its own id
    since nothing else in the app names that toolbar as a menu item.
    """
    from TheKeyMachine.core import i18n

    return [
        {"id": "main", "label": i18n.tr("workspaces_toolbar_main", "Main Toolbar")},
        {"id": "graph", "label": i18n.tr("graph_editor_toolbar", "Graph Editor Toolbar")},
    ]


def get_alignment_options():
    """Return the same live-translated modes used by every toolbar menu."""
    return toolbar_modes.translated_options()


# --------------------------------------------------------------------------- live widgets

def get_toolbar_instance():
    from TheKeyMachine.ui.widgets import toolbar as toolbar_module

    return toolbar_module.get_toolbar()


def get_toolbar_widget(toolbar_id):
    """Return the live ``QFlatToolbar`` for *toolbar_id*, or ``None`` if not open."""
    if toolbar_id == "graph":
        widget = graph_toolbar.get_widget()
    else:
        inst = get_toolbar_instance()
        widget = getattr(inst, "main_toolbar_widget", None)
    return widget if wutil.is_valid_widget(widget) else None


# --------------------------------------------------------------------------- position (docking)

def get_position_options(toolbar_id):
    """List of ``(position_id, label, description)`` rows for the Position column."""
    from TheKeyMachine.core import i18n

    if toolbar_id == "graph":
        # graph_toolbar.DOCK_OPTIONS is the raw (id, English label, English
        # description) data the graph toolbar's own dock menu also reads --
        # see widgets.toolbar_menus.build_graph_dock_menu, which translates the same
        # tuple at its point of use via the same "graph_dock_{id}" ids rather
        # than baking translation into the tuple itself (language can change
        # at runtime; a module-level constant can't).
        return [
            (
                position,
                i18n.tr("graph_dock_{}".format(position), label),
                i18n.tr("graph_dock_{}_desc".format(position), description),
            )
            for position, label, description in graph_toolbar.DOCK_OPTIONS
        ]

    from TheKeyMachine.ui.widgets import toolbar as toolbar_module

    options = []
    for orient, orient_label in toolbar_module.DOCKING_ORIENTATIONS.items():
        # Bare "Top"/"Bottom" translations, distinct from dock_orient_{orient}
        # (used by the main dock menu, phrased as "To Top"/"To Bottom" --
        # correct there, but the wrong grammar to splice into "{orient} of
        # {area}" below).
        orient_word = i18n.tr(
            "position_orient_{}".format(orient), orient_label.replace("To ", "")
        )
        for area, area_label in toolbar_module.DOCKING_AREAS.items():
            position_id = "{}::{}".format(area, orient)
            area_word = i18n.tr("dock_area_{}".format(area), area_label)
            label = i18n.tr("workspace_position_label", "{orient} of {area}").format(
                orient=orient_word, area=area_word
            )
            description = i18n.tr("workspace_position_desc", "Dock the toolbar {position}.").format(
                position=label
            )
            options.append((position_id, label, description))
    return options


def get_current_position(toolbar_id):
    if toolbar_id == "graph":
        return settings.get_setting(graph_toolbar.GRAPH_TOOLBAR_DOCK_SETTING, graph_toolbar.DOCK_BOTTOM_GRAPH)

    inst = get_toolbar_instance()
    if inst is not None:
        layout, orient = inst.docking_position
    else:
        layout, orient = settings.get_setting("docking_position", ["TimeSlider", "top"])
    return "{}::{}".format(layout, orient)


def set_position(toolbar_id, position_id):
    if not position_id:
        return
    if toolbar_id == "graph":
        graph_toolbar.move_dock(position_id)
        return

    area, _, orient = position_id.partition("::")
    inst = get_toolbar_instance()
    if inst is not None:
        inst.dock_to_ui(layout=area, orient=orient)
    else:
        settings.set_setting("docking_position", [area, orient])


# --------------------------------------------------------------------------- alignment

def get_current_alignment(toolbar_id):
    if toolbar_id == "graph":
        setting_key = toolbar_modes.GRAPH_ALIGNMENT_SETTING
    else:
        setting_key = toolbar_modes.MAIN_ALIGNMENT_SETTING
    return toolbar_modes.normalize(
        settings.get_setting(setting_key, toolbar_modes.DEFAULT_ALIGNMENT)
    )


def set_alignment(toolbar_id, alignment_name):
    if toolbar_id == "graph":
        graph_toolbar.apply_alignment(alignment_name)
        return

    inst = get_toolbar_instance()
    if inst is not None:
        toolbar_widgets.set_main_toolbar_icon_alignment(inst, alignment_name)
    else:
        settings.set_setting(
            toolbar_modes.MAIN_ALIGNMENT_SETTING,
            toolbar_modes.normalize(alignment_name),
        )


# --------------------------------------------------------------------------- sections

def _toolbar_section_defs(toolbar_id):
    """All section defs for *toolbar_id*, unfiltered, in build order.

    This order matches ``widget._tkm_sections`` positionally: every entry here
    gets exactly one ``QFlatSectionWidget`` when the toolbar is populated (see
    ``widgets.toolbar_widgets.populate_main_toolbar_from_layout`` /
    ``populate_graph_toolbar_from_layout``).
    """
    return registry.get_toolbar_sections(toolbar_id, resolve_items=False)


def get_sections(toolbar_id):
    """Ordered ``{"id", "label", "color"}`` rows for a toolbar's *editable* sections.

    Sections built with ``"hiddeable": False`` (the fixed "TKM Menu" section
    holding the toolbar's own menu buttons) never get pin metadata -- nothing
    in them can be shown/hidden or reordered -- and its button lives outside
    the toolbar's own flow layout entirely. Neither belongs in an editor
    about pinning and reordering, so they're left out here.
    """
    return [
        {
            "id": section_def["id"],
            "label": section_def.get("label") or section_def["id"],
            "color": section_def.get("color") or COLORS.toolbar.gray.hex,
        }
        for section_def in _toolbar_section_defs(toolbar_id)
        if section_def.get("hiddeable", True)
    ]


def reorder_sections(toolbar_id, new_order_ids):
    """Persist a drag-and-drop reorder (of the editable sections) and, if the
    toolbar is open, reflow it live. Fixed/non-editable sections keep their
    original position; only editable sections are permuted among themselves.
    """
    full_old_order = [section_def["id"] for section_def in _toolbar_section_defs(toolbar_id)]

    settings.set_setting(
        "section_order_{}".format(toolbar_id), list(new_order_ids), namespace=WORKSPACES_NAMESPACE
    )

    # Re-read after persisting: this reflects the full order (fixed sections
    # kept in place, editable ones permuted) that registry.get_toolbar_sections
    # will now build from.
    full_new_order = [section_def["id"] for section_def in _toolbar_section_defs(toolbar_id)]

    widget = get_toolbar_widget(toolbar_id)
    if widget is not None and hasattr(widget, "reorder_sections"):
        try:
            widget.reorder_sections(full_old_order, full_new_order)
        except (RuntimeError, ValueError, TypeError, AttributeError, KeyError, IndexError):
            pass


def get_color_groups(toolbar_id):
    """Ordered color-group rows for the Workspaces editor.

    Each row is one contiguous run of same-colored sections (see
    ``registry.group_sections_by_color``), presented -- and reordered -- as one
    atomic unit instead of individual sections. A group has no identity of
    its own beyond "these section ids share a color run right now": it is
    recomputed fresh from the current section order every time this is
    called, so if reordering groups happens to land two same-colored runs
    next to each other, they simply present as one merged group afterwards.
    """
    sections = get_sections(toolbar_id)
    groups = []
    for member_sections in registry.group_sections_by_color(sections):
        section_ids = tuple(section["id"] for section in member_sections)
        groups.append(
            {
                "id": "::".join(section_ids),
                "color": member_sections[0]["color"],
                "sections": member_sections,
                "section_ids": section_ids,
            }
        )
    return groups


def _color_groups_by_id(toolbar_id):
    return {group["id"]: group for group in get_color_groups(toolbar_id)}


def reorder_color_groups(toolbar_id, new_group_id_order):
    """Persist a drag-and-drop reorder of whole color groups.

    Each group is flattened back to its member section ids (kept in their
    existing relative order) before delegating to ``reorder_sections``, so
    the persisted order is still a plain section-id sequence -- groups are
    purely a presentation concept, not a stored one.
    """
    groups_by_id = _color_groups_by_id(toolbar_id)
    new_section_order = []
    for group_id in new_group_id_order:
        group = groups_by_id.get(group_id)
        if group:
            new_section_order.extend(group["section_ids"])
    reorder_sections(toolbar_id, new_section_order)


def watch_group_pins(toolbar_id, group_id, callback):
    """Connect *callback* to every member section's ``pinsChanged`` signal.

    Mirrors ``watch_section_pins`` for a whole color group at once. Returns
    the list of connected live section widgets (empty if the toolbar isn't
    open), to be passed to ``unwatch_group_pins`` later.
    """
    group = _color_groups_by_id(toolbar_id).get(group_id)
    if not group:
        return []
    watched = []
    for section_id in group["section_ids"]:
        section = watch_section_pins(toolbar_id, section_id, callback)
        if section is not None:
            watched.append(section)
    return watched


def unwatch_group_pins(sections, callback):
    for section in sections:
        unwatch_section_pins(section, callback)


def get_live_section(toolbar_id, section_id):
    """Return the open toolbar's live ``QFlatSectionWidget`` for *section_id*, if any."""
    widget = get_toolbar_widget(toolbar_id)
    if widget is None:
        return None

    section_ids = [section_def["id"] for section_def in _toolbar_section_defs(toolbar_id)]
    live_sections = list(getattr(widget, "_tkm_sections", ()))
    if len(section_ids) != len(live_sections):
        return None

    try:
        index = section_ids.index(section_id)
    except ValueError:
        return None
    return live_sections[index]


# --------------------------------------------------------------------------- tools (pins)

def _tool_row(tool_id, label, icon, text, description):
    """One row's display data. ``badge_text`` is only ever used when there's no icon."""
    return {
        "id": tool_id,
        "label": label or tool_id,
        "icon": icon,
        "badge_text": None if icon else text,
        "description": description or "",
    }


def _iter_leaf_tools(items):
    """Flatten a resolved section's ``items`` down to actual tool dicts.

    Most sections list their tools flat. ``link_tools`` (labeled
    "Relationships & Worldspace" on the toolbar) instead nests two whole
    sub-sections via ``{"section": ...}`` refs, which ``registry.get_tool_section``
    resolves into ``{"type": "group", "items": [...]}`` wrappers -- the real
    tool dicts are one level deeper, under that wrapper's own ``"items"``.
    Recursing here (groups can in principle nest further) is the one place
    that needs to know about this shape; everything else just gets tools.
    """
    for item in items or ():
        if item == "separator" or not isinstance(item, dict):
            continue
        if item.get("type") == "group":
            for leaf in _iter_leaf_tools(item.get("items")):
                yield leaf
            continue
        if item.get("id"):
            yield item


def get_section_tools(toolbar_id, section_id):
    """Pinnable tool rows for a section: id/label/icon/badge_text/description + live-checked state.

    Sections come in exactly two shapes, and each is read from its one real
    source of truth -- no probing/fallback between them:

    * Ordinary sections list their tools under ``"items"``, resolved through
      ``registry.get_tool_section`` (every item there comes from the tool's
      own registry entry via ``registry.get_tool``).
    * Slider sections (``section_def["type"] == "slider"``) have no
      ``"items"`` at all -- one pinnable slot per ``SliderMode`` in
      ``section_def["modes"]`` instead, keyed exactly like
      ``widgets.toolbar_widgets.build_slider_section`` keys them
      (``"{slider_type}_{mode.key}"``).

    Either way, whether a row is currently pinned comes from the live
    ``QFlatSectionWidget`` when the toolbar is open (every widget slot is
    registered there regardless of whether it also has pin *menu* metadata),
    or from the active workspace's defaults when it isn't.
    """
    # One resolve, not two: ``resolve_items=True`` only ever touches the
    # "items" key (empty for slider sections, since those declare "modes"
    # instead) -- "type"/"slider_type"/"modes" pass through untouched either
    # way, so there's no need for a separate resolve_items=False call just to
    # branch on section type first.
    section_def = registry.get_tool_section(section_id, resolve_items=True, toolbar_id=toolbar_id)
    if not section_def:
        return []

    if section_def.get("type") == "slider":
        prefix = section_def["slider_type"]
        entries = []
        for mode in section_def.get("modes", []):
            if not hasattr(mode, "key"):
                continue
            data = mode.widget_data()
            entries.append(
                _tool_row(
                    "{}_{}".format(prefix, data["key"]),
                    data.get("label"),
                    data.get("icon"),
                    data.get("text"),
                    data.get("description"),
                )
            )
    else:
        entries = [
            _tool_row(
                item["id"],
                item.get("label"),
                item.get("command_icon") or item.get("icon"),
                item.get("text"),
                item.get("description"),
            )
            for item in _iter_leaf_tools(section_def.get("items", []))
            if item.get("pinnable", True) is not False
        ]

    live_section = get_live_section(toolbar_id, section_id)
    for entry in entries:
        entry["checked"] = (
            live_section._is_pin_key_checked(entry["id"])
            if live_section is not None
            else registry.is_pinned_by_default(toolbar_id, entry["id"])
        )
    return entries


def set_tool_pinned(toolbar_id, section_id, tool_id, pinned):
    live_section = get_live_section(toolbar_id, section_id)
    if live_section is None:
        return False
    live_section._apply_widget_pin_states({tool_id: bool(pinned)})
    return True


def watch_section_pins(toolbar_id, section_id, callback):
    """Connect *callback* to the live section's ``pinsChanged`` signal, if open.

    Returns the connected section widget (needed to disconnect later), or
    ``None`` when the toolbar isn't open.
    """
    live_section = get_live_section(toolbar_id, section_id)
    if live_section is not None:
        live_section.pinsChanged.connect(callback)
    return live_section


def unwatch_section_pins(section, callback):
    if section is None or not wutil.is_valid_widget(section):
        return
    try:
        section.pinsChanged.disconnect(callback)
    except (RuntimeError, TypeError):
        pass


# --------------------------------------------------------------------------- workspaces

def list_workspaces():
    return workspaces.list_workspaces()


def get_active_workspace():
    return workspaces.get_active_workspace()


def rename_workspace(ws_id, new_name):
    return workspaces.rename_workspace(ws_id, new_name)


def is_custom_workspace(ws_id):
    return workspaces.is_custom_workspace(ws_id)


def delete_workspace(ws_id):
    return workspaces.delete_workspace(ws_id)


def export_workspaces_data():
    """Everything the Workspaces editor owns that isn't derived from the toolbars themselves."""
    return {
        "custom_workspaces": workspaces.get_custom_workspaces(),
        "name_overrides": workspaces.get_name_overrides(),
    }


def import_workspaces_data(data):
    """Merge an exported workspaces file in: existing ids/overrides are replaced, others kept."""
    if not isinstance(data, dict):
        return False

    incoming_workspaces = data.get("custom_workspaces")
    if isinstance(incoming_workspaces, list):
        merged = {entry.get("id"): entry for entry in workspaces.get_custom_workspaces() if entry.get("id")}
        for entry in incoming_workspaces:
            if isinstance(entry, dict) and entry.get("id"):
                merged[entry["id"]] = entry
        workspaces.set_custom_workspaces(list(merged.values()))

    incoming_overrides = data.get("name_overrides")
    if isinstance(incoming_overrides, dict):
        merged_overrides = workspaces.get_name_overrides()
        merged_overrides.update(incoming_overrides)
        workspaces.set_name_overrides(merged_overrides)

    return True


def _snapshot_toolbar(toolbar_id):
    sections = get_sections(toolbar_id)
    pins = []
    for section in sections:
        for tool in get_section_tools(toolbar_id, section["id"]):
            if tool["checked"]:
                pins.append(tool["id"])

    return {
        "alignment": get_current_alignment(toolbar_id),
        "pins": pins,
        "docking": get_current_position(toolbar_id),
        "section_order": [section["id"] for section in sections],
    }


def snapshot_current_configuration():
    return {"main": _snapshot_toolbar("main"), "graph": _snapshot_toolbar("graph")}


def create_workspace_from_current(name):
    snapshot = snapshot_current_configuration()
    ws_id = workspaces.create_workspace(name, snapshot)
    workspaces.set_active_workspace(ws_id)
    return ws_id


def _apply_snapshot_toolbar(toolbar_id, toolbar_snapshot):
    if not toolbar_snapshot:
        return

    alignment = toolbar_snapshot.get("alignment")
    if alignment:
        set_alignment(toolbar_id, alignment)

    docking = toolbar_snapshot.get("docking")
    if docking:
        set_position(toolbar_id, docking)

    section_order = toolbar_snapshot.get("section_order")
    if section_order:
        reorder_sections(toolbar_id, section_order)

    pins = set(toolbar_snapshot.get("pins") or [])
    for section in get_sections(toolbar_id):
        live_section = get_live_section(toolbar_id, section["id"])
        if live_section is None:
            continue
        states = {
            item["id"]: (item["id"] in pins)
            for item in getattr(live_section, "_menu_metadata", [])
            if item.get("type") == "widget" and item.get("id")
        }
        if states:
            live_section._apply_widget_pin_states(states)


def apply_workspace(ws_id):
    """Make *ws_id* the active workspace and apply it to both live toolbars."""
    if workspaces.is_custom_workspace(ws_id):
        snapshot = workspaces.get_custom_workspace_snapshot(ws_id) or {}
        workspaces.set_active_workspace(ws_id)
        _apply_snapshot_toolbar("main", snapshot.get("main"))
        _apply_snapshot_toolbar("graph", snapshot.get("graph"))
        return

    # Built-in workspace: reuse the same apply routine the toolbars' own
    # right-click pinning menus use, once per toolbar, so both stay in sync.
    main_widget = get_toolbar_widget("main")
    if main_widget is not None:
        inst = get_toolbar_instance()
        main_alignment_fn = (
            (lambda name, inst=inst: toolbar_widgets.set_main_toolbar_icon_alignment(inst, name))
            if inst is not None
            else None
        )
        workspaces.apply_workspace(ws_id, list(getattr(main_widget, "_tkm_sections", ())), main_alignment_fn)

    graph_widget = get_toolbar_widget("graph")
    if graph_widget is not None:
        workspaces.apply_workspace(
            ws_id, list(getattr(graph_widget, "_tkm_sections", ())), graph_toolbar.apply_alignment
        )

    if main_widget is None and graph_widget is None:
        # Neither toolbar is open -- at least persist the active id.
        workspaces.set_active_workspace(ws_id)
