import importlib
import json
import os
import pkgutil
import sys
from types import MappingProxyType


class ToolObject(object):
    """Declarative metadata owned by one tool package."""

    ORDER = 1000
    TOOLS = {}
    SECTION = None
    SECTIONS = ()
    # Set by _collect_package_definitions() to this package's __init__.py path,
    # so i18n.load_package_lang() can find its optional lang.json.
    _package_file = None

    @classmethod
    def tools(cls):
        return cls._resolve_icons(dict(cls.TOOLS or {}))

    @classmethod
    def _resolve_icons(cls, value, key=None):
        if isinstance(value, dict):
            return {
                item_key: cls._resolve_icons(item_value, key=item_key)
                for item_key, item_value in value.items()
            }
        if isinstance(value, list):
            return [cls._resolve_icons(item) for item in value]
        if isinstance(value, tuple):
            return tuple(cls._resolve_icons(item) for item in value)
        if key in {"icon", "command_icon"} and isinstance(value, str) and value:
            if os.path.isabs(value):
                return value
            from TheKeyMachine.data import icons

            resolved = icons.get(value)
            if not resolved:
                raise ValueError("{} references unknown icon {!r}".format(cls.__name__, value))
            return resolved
        return value

    @classmethod
    def sections(cls):
        descriptors = []
        if cls.SECTION:
            descriptors.append(cls.SECTION)
        descriptors.extend(cls.SECTIONS or ())

        sections = {}
        for descriptor in descriptors:
            section = dict(descriptor)
            section_id = section.pop("id", None)
            if not section_id:
                raise ValueError("{} section is missing an id".format(cls.__name__))
            if section_id in sections:
                raise ValueError("{} defines section {} twice".format(cls.__name__, section_id))
            sections[section_id] = cls._resolve_icons(section)
        return sections


def load_tooltips(package_file):
    """Load and resolve a tool package's tooltip.json file."""
    tooltip_path = os.path.join(os.path.dirname(package_file), "tooltip.json")
    with open(tooltip_path, "r", encoding="utf-8") as stream:
        payload = json.load(stream)

    from TheKeyMachine.data.movies import TooltipMedia
    from TheKeyMachine.ui.tooltips import separator

    def _resolve(value):
        if isinstance(value, list):
            return [_resolve(item) for item in value]
        if isinstance(value, dict):
            if set(value) == {"platform"}:
                variants = value["platform"]
                if not isinstance(variants, dict):
                    raise TypeError("Tooltip platform variants must be a mapping")
                selected = variants.get(sys.platform, variants.get("default"))
                return _resolve(selected)
            if set(value) == {"movie"}:
                filename = value["movie"]
                if not os.path.splitext(filename)[1]:
                    filename += ".gif"
                movie_path = os.path.join(os.path.dirname(tooltip_path), "media", filename)
                if not os.path.isfile(movie_path):
                    raise FileNotFoundError(
                        "Tooltip movie {!r} is missing from {}".format(filename, movie_path)
                    )
                return TooltipMedia(movie_path)
            if set(value) == {"separator"} and value["separator"] is True:
                return separator
            return {key: _resolve(item) for key, item in value.items()}
        return value

    return _resolve(payload)


from TheKeyMachine.core.Qt import QtCore  # type: ignore

from TheKeyMachine.core import trigger
from TheKeyMachine.ui.widgets import toolbar_menus
from TheKeyMachine.data.colors import COLORS

_PACKAGE_TOOL_DEFINITIONS = None
_PACKAGE_SECTION_DEFINITIONS = None
_CHOICE_SETTINGS_BY_OWNER = None




TOOLBAR_SECTION_IDS = {
    # Preserve the original registry order. Split packages stay adjacent to the
    # section they belonged to before tool discovery was package-based.
    "main": (
        "system",
        "nudge_tools", "default_tools", "bake_tools", "key_sync_tools",
        "slider_blend", "slider_tween", "slider_tangent",
        "isolate_tools", "selection_tools", "opposite_tools", "mirror_tools", "align_tools",
        "pose_animation_section", "tangents", "manipulator_tools",
        "animation_offset_tools", "movers_tools",
        "temp_pivot_tools", "follow_cam_tools", "temporal_controls_tools",
        "link_tools",
        "attribute_tools", "selection_set_tools", "orbit_tools", "tracer_tools", "pause_viewport_tools",
        "global_tools",
        "graph_tools", "animation_tools", "animation_layer_tools", "custom_tools_section", "snapshot_rig_tools", "background_runner_tools",
        "animation_recovery_tools", "search_tools",
    ),
    "graph": (
        "nudge_tools", "default_tools", "bake_tools", "key_sync_tools",
        "slider_blend", "slider_tween", "slider_tangent",
        "isolate_tools", "selection_tools", "opposite_tools", "mirror_tools", "align_tools",
        "pose_animation_section", "tangents",
        "animation_offset_tools",
        "link_tools",
        "attribute_tools", "selection_set_tools", "orbit_tools",
        "global_curve_tools", "graph_tools", "animation_tools", "custom_tools_section", "snapshot_rig_tools",
    ),
}


def get_ordered_section_ids(toolbar_id):
    """Return *toolbar_id*'s section ids, honoring a user-saved drag-and-drop reorder.

    The Workspaces editor lets users drag sections into a new order and persists
    that order under the "workspaces" settings namespace. Everything that used
    to read ``TOOLBAR_SECTION_IDS`` directly should go through this instead so a
    saved reorder survives a toolbar reload / Maya restart.

    Sections built with ``"hiddeable": False`` (the fixed "TKM Menu" section)
    are never offered up for reordering and always keep their original index;
    only the remaining, editable sections are permuted among each other.
    """
    base = TOOLBAR_SECTION_IDS.get(toolbar_id, ())
    try:
        from TheKeyMachine.core import settings

        custom_order = settings.get_setting(
            "section_order_{}".format(toolbar_id), None, namespace="workspaces"
        )
    except Exception:
        custom_order = None

    if not custom_order:
        return base

    definitions = _section_definitions()
    fixed_by_index = {}
    movable = []
    for index, section_id in enumerate(base):
        section_def = definitions.get(section_id) or {}
        if section_def.get("hiddeable", True) is False:
            fixed_by_index[index] = section_id
        else:
            movable.append(section_id)

    movable_set = set(movable)
    ordered_movable = []
    seen_movable = set()
    for section_id in custom_order:
        if section_id in movable_set and section_id not in seen_movable:
            ordered_movable.append(section_id)
            seen_movable.add(section_id)

    # A saved order may predate newly added sections. Insert those sections next
    # to their nearest canonical successor instead of appending them all at the
    # end. For example, Snapshot Rig was introduced immediately before
    # Background Runners and should appear there for existing workspaces too.
    for index, section_id in enumerate(movable):
        if section_id in ordered_movable:
            continue
        following = next(
            (candidate for candidate in movable[index + 1:] if candidate in ordered_movable),
            None,
        )
        if following is None:
            ordered_movable.append(section_id)
        else:
            ordered_movable.insert(ordered_movable.index(following), section_id)

    result = []
    movable_iter = iter(ordered_movable)
    for index in range(len(base)):
        result.append(fixed_by_index[index] if index in fixed_by_index else next(movable_iter))
    return tuple(result)


def is_pinned_by_default(toolbar_id, tool_id):
    from TheKeyMachine.core import workspaces
    active_ws = workspaces.get_active_workspace()
    ws = workspaces.WORKSPACE_DEFAULTS.get(active_ws, workspaces.WORKSPACE_DEFAULTS["standard"])
    pins = ws["pins"].get(toolbar_id, frozenset())
    return tool_id in pins


def _tool_object_from_package(package):
    candidates = []
    for value in vars(package).values():
        if isinstance(value, type) and issubclass(value, ToolObject) and value is not ToolObject:
            candidates.append(value)
    if not candidates:
        return None
    if len(candidates) > 1:
        raise RuntimeError(
            "Tool package {} defines multiple ToolObject classes: {}".format(
                package.__name__, ", ".join(candidate.__name__ for candidate in candidates)
            )
        )
    return candidates[0]


def _merge_owned(target, owners, incoming, owner_name, kind):
    for item_id, definition in incoming.items():
        previous_owner = owners.get(item_id)
        if previous_owner:
            raise RuntimeError(
                "Duplicate {} id {!r} in {} and {}".format(kind, item_id, previous_owner, owner_name)
            )
        target[item_id] = definition
        owners[item_id] = owner_name


def _iter_section_items(items):
    for item in items or ():
        if isinstance(item, dict):
            yield item
            for shortcut in item.get("shortcuts") or ():
                if isinstance(shortcut, dict):
                    yield shortcut


def _iter_menu_leaf_items(items):
    """Flatten a declared menu tree into its leaf items, recursing into
    nested "type": "menu" submenus.

    A leaf is anything that isn't itself a submenu container: a bare string
    id, a plain command dict, a "choice"/"check"/"section" item, and so on.
    Used by ``_iter_menu_command_ids`` for validation, which only needs the
    leaves themselves. ``_iter_menu_choice_settings`` below does its own,
    separate recursion instead of building on this one, because it also has
    to track *which* enclosing submenu each choice sits in.
    """
    for item in items or ():
        if isinstance(item, dict) and item.get("type") == "menu":
            for leaf in _iter_menu_leaf_items(item.get("items")):
                yield leaf
            continue
        yield item


def _iter_menu_command_ids(items):
    for item in _iter_menu_leaf_items(items):
        if isinstance(item, str):
            if item != "separator":
                yield item
            continue
        if not isinstance(item, dict):
            continue
        if item.get("type") == "choice":
            # A choice item's "id" names its own setting group (see
            # tool_choice_settings()/_validate_definition_graph's separate
            # choice-id check below), not a reference to another tool --
            # unlike every other declared-menu item, where "id" is always a
            # tool reference.
            continue
        command_id = item.get("command") or item.get("id")
        if command_id:
            yield command_id


def _iter_menu_choice_settings(owner_id, items):
    """Yield ``(owner_id, choice_item)`` for every "type": "choice" leaf under *items*.

    A choice's owner is the nearest enclosing menu's "command"/"id" -- the
    same nearest-declared-identity rule ``widgets.toolbar_menus._declared_item_text``
    already uses for a submenu's own label/description -- falling back to
    the caller's *owner_id* when a choice sits directly in a menu with no
    nested submenu in between. That single rule is what lets a choice
    declared deep inside one tool's menu (the alignment picker nested in
    the "TKM" logo's own Preferences submenu) surface under the
    *standalone* tool that actually represents it on the section graph
    (the "Preferences" toolbar button, ``main_preferences_menu``) with no
    caller ever special-casing that nesting: this one walk is reused by
    both package validation and ``tool_choice_settings()`` below, so there
    is exactly one place that knows how ownership is resolved.
    """
    for item in items or ():
        if not isinstance(item, dict):
            continue
        if item.get("type") == "menu":
            nested_owner = item.get("command") or item.get("id") or owner_id
            for owner, choice_item in _iter_menu_choice_settings(nested_owner, item.get("items")):
                yield owner, choice_item
            continue
        if item.get("type") == "choice":
            yield owner_id, item


def _all_choice_settings_by_owner():
    by_owner = {}
    for tool_id, tool in _tool_definitions().items():
        menu = tool.get("menu")
        if not isinstance(menu, dict):
            continue
        for owner_id, choice_item in _iter_menu_choice_settings(tool_id, menu.get("items")):
            by_owner.setdefault(owner_id, []).append(choice_item)
    return by_owner


def tool_choice_settings(tool_id):
    """Return every "type": "choice" item owned by *tool_id*.

    ``get_tool()`` replaces a tool's declared "menu" dict with a callable
    that builds the actual Qt menu (see the ``tool["menu"] = lambda ...``
    assignment below), so introspecting the *declared* choice items -- each
    one a setting owned by a tool's dropdown, like Bake's tangent mode,
    Share Keys' Keep Anim Curve Shape picker, or the Preferences alignment
    picker -- has to read the raw package definitions instead, via
    ``_iter_menu_choice_settings``'s ownership walk. ``tools.hotkeys.controller``
    calls this once per tool it already visits to expose each choice value
    as its own row for Search and the Hotkeys editor, instead of
    re-implementing declared-menu traversal or special-casing any one
    tool's nesting.
    """
    global _CHOICE_SETTINGS_BY_OWNER
    if _CHOICE_SETTINGS_BY_OWNER is None:
        _CHOICE_SETTINGS_BY_OWNER = _all_choice_settings_by_owner()
    return _CHOICE_SETTINGS_BY_OWNER.get(tool_id, [])


def apply_choice_value(setter, value, checked, state_key=None):
    """Apply *value* through *setter* when a choice row's checkbox turns on.

    Shared by every surface that reaches a declared "choice" menu item's
    boolean-in/value-out setter through a checkable control: the menu radio
    group ``widgets.toolbar_menus.build_declared_menu`` builds, and the individual
    per-value rows ``tools.hotkeys.controller`` derives from the same declared choice
    for Search and the Hotkeys editor. A choice group is mutually exclusive
    -- unchecking a row has nothing of its own to apply, only checking one
    does.

    When *state_key* is given (every caller that has a stable choice id
    passes its own), a successful apply also publishes *value* under that
    key via ``runtime.set_control_state`` -- the app's existing
    generic shared-control-state channel. ``widgets.util.bind_choice_row_state``
    subscribes each Search/Hotkeys row for the same choice to that channel,
    so picking a value through the live dropdown menu, a hotkey, or any one
    row updates every other row for that setting immediately, from this one
    place, instead of each surface needing its own refresh logic.
    """
    if not checked:
        return None
    result = setter(value)
    if state_key:
        from TheKeyMachine.core import runtime

        runtime.get_runtime_manager().set_control_state(state_key, value)
    return result


def choice_setting_command_name(choice_id, value):
    """Return the trigger command name for one value of a "choice" setting.

    Mirrors ``slider_command_name`` -- a stable, collision-free name
    composed from the setting's own id and one of its values. Shared by
    ``register_choice_setting_commands()`` below (which registers the
    command) and ``tools.hotkeys.controller`` (which references the same name to
    build a Search/Hotkeys row for that value), so there is exactly one
    formula for the name.
    """
    return "{}__{}".format(choice_id, value)


def _choice_setting_callback(choice_id, setter, value):
    def _apply_choice_setting(*_args, **_kwargs):
        return apply_choice_value(setter, value, True, state_key=choice_id)

    return _apply_choice_setting


def register_choice_setting_commands():
    """Register each declared choice so hotkeys can use it immediately."""
    global _CHOICE_SETTINGS_BY_OWNER
    if _CHOICE_SETTINGS_BY_OWNER is None:
        _CHOICE_SETTINGS_BY_OWNER = _all_choice_settings_by_owner()

    for choice_items in _CHOICE_SETTINGS_BY_OWNER.values():
        for choice_item in choice_items:
            choice_id = choice_item.get("id")
            setter = choice_item.get("set_value")
            if not choice_id or not callable(setter):
                continue
            choices = choice_item.get("items", ())
            if callable(choices):
                choices = choices()
            for choice in choices:
                value = choice.get("value")
                trigger.register_command(
                    choice_setting_command_name(choice_id, value),
                    _choice_setting_callback(choice_id, setter, value),
                    policy=trigger.OperationPolicy(progress=False, undo=False),
                )


def _validate_definition_graph(tools, sections):
    errors = []
    pinnable_ids = set(tools)
    for section_id, section in sections.items():
        if section.get("type") == "slider":
            prefix = section.get("slider_type")
            for mode in section.get("modes") or ():
                mode_key = getattr(mode, "key", None)
                if prefix and mode_key:
                    pinnable_ids.add("{}_{}".format(prefix, mode_key))
        for item in _iter_section_items(section.get("items")):
            tool_id = item.get("id")
            section_ref = item.get("section")
            if tool_id and tool_id not in tools and not callable(item.get("callback")):
                errors.append("section {!r} references unknown tool {!r}".format(section_id, tool_id))
            if section_ref and section_ref not in sections:
                errors.append("section {!r} references unknown section {!r}".format(section_id, section_ref))

    for toolbar_id, section_ids in TOOLBAR_SECTION_IDS.items():
        for section_id in section_ids:
            if section_id not in sections:
                errors.append("toolbar {!r} references unknown section {!r}".format(toolbar_id, section_id))
    from TheKeyMachine.core import workspaces
    for workspace in workspaces.WORKSPACE_DEFAULTS.values():
        for toolbar_id, tool_ids in workspace["pins"].items():
            for tool_id in tool_ids:
                if tool_id not in pinnable_ids:
                    errors.append("workspace pins unknown tool {!r} in toolbar {!r}".format(tool_id, toolbar_id))

    # Uses the raw *tools* argument, not _tool_definitions() -- this runs
    # while _PACKAGE_TOOL_DEFINITIONS is still being assembled, before that
    # cache exists. tool_choice_settings() reuses the exact same
    # _iter_menu_choice_settings ownership walk once the cache is up, so
    # this check and that lookup can never disagree about who owns what.
    choice_setting_owners = {}
    for tool_id, tool in tools.items():
        menu = tool.get("menu")
        if not isinstance(menu, dict):
            continue
        for command_id in _iter_menu_command_ids(menu.get("items")):
            if command_id not in tools:
                errors.append("tool {!r} menu references unknown command {!r}".format(tool_id, command_id))
        for owner_id, choice_item in _iter_menu_choice_settings(tool_id, menu.get("items")):
            choice_id = choice_item.get("id")
            if not choice_id:
                errors.append(
                    "tool {!r} declares a \"choice\" menu setting (owner {!r}) with no stable \"id\" -- "
                    "Search and the Hotkeys editor need one to expose each value as its own row".format(
                        tool_id, owner_id
                    )
                )
                continue
            previous_owner = choice_setting_owners.get(choice_id)
            if previous_owner:
                errors.append(
                    "choice setting id {!r} is declared twice, under owners {!r} and {!r}".format(
                        choice_id, previous_owner, owner_id
                    )
                )
            else:
                choice_setting_owners[choice_id] = owner_id
    if errors:
        raise RuntimeError("Invalid tool package graph:\n- " + "\n- ".join(errors))


def _collect_package_definitions():
    import TheKeyMachine.tools as tools_package

    tools = {}
    sections = {}
    tool_owners = {}
    section_owners = {}
    packages = []
    import_errors = []
    prefix = tools_package.__name__ + "."
    for module_info in pkgutil.iter_modules(tools_package.__path__, prefix):
        if not module_info.ispkg:
            continue
        try:
            package = importlib.import_module(module_info.name)
            tool_object = _tool_object_from_package(package)
        except Exception as exc:
            import_errors.append("{}: {}".format(module_info.name, exc))
            continue
        if tool_object is None:
            continue
        tool_object._package_file = getattr(package, "__file__", None)
        packages.append((tool_object.ORDER, module_info.name, tool_object))

    if import_errors:
        raise RuntimeError("Unable to import tool packages:\n- " + "\n- ".join(import_errors))

    for _order, package_name, tool_object in sorted(packages, key=lambda item: (item[0], item[1])):
        package_tools = tool_object.tools()
        for definition in package_tools.values():
            definition.setdefault("_package", package_name)
            definition.setdefault("_package_file", tool_object._package_file)
        package_sections = tool_object.sections()
        for definition in package_sections.values():
            definition.setdefault("_package", package_name)
            definition.setdefault("_package_file", tool_object._package_file)
        _merge_owned(tools, tool_owners, package_tools, package_name, "tool")
        _merge_owned(sections, section_owners, package_sections, package_name, "section")
    _validate_definition_graph(tools, sections)
    return tools, sections


def reset_package_cache():
    """Force package metadata to be rediscovered after an in-process reload."""
    global _PACKAGE_TOOL_DEFINITIONS, _PACKAGE_SECTION_DEFINITIONS, _CHOICE_SETTINGS_BY_OWNER
    _PACKAGE_TOOL_DEFINITIONS = None
    _PACKAGE_SECTION_DEFINITIONS = None
    _CHOICE_SETTINGS_BY_OWNER = None


def _package_definitions():
    global _PACKAGE_TOOL_DEFINITIONS, _PACKAGE_SECTION_DEFINITIONS
    if _PACKAGE_TOOL_DEFINITIONS is None:
        tools, sections = _collect_package_definitions()
        # Wrap (not copy) the memoized registry. get_tool()/get_tool_section()
        # already make their own per-item dict(...) copy before applying
        # overrides -- nothing needs a fresh top-level copy of the whole
        # registry on every lookup, and this used to be called on every
        # tool/section resolution for every button on both toolbars.
        # MappingProxyType keeps callers from accidentally mutating the
        # shared cache while costing nothing to construct (unlike dict(...),
        # which copies every entry).
        _PACKAGE_TOOL_DEFINITIONS = MappingProxyType(tools)
        _PACKAGE_SECTION_DEFINITIONS = MappingProxyType(sections)
    return _PACKAGE_TOOL_DEFINITIONS, _PACKAGE_SECTION_DEFINITIONS


def _tool_definitions():
    package_tools, _package_sections = _package_definitions()
    return package_tools


def _section_definitions():
    _package_tools, package_sections = _package_definitions()
    return package_sections


def get_tool_definitions():
    return _tool_definitions()


def get_section_definitions():
    return _section_definitions()


def _apply_shortcuts(tool, item):
    shortcut_items = item.get("shortcuts") or []
    if not shortcut_items:
        return tool

    key_masks = (
        (QtCore.Qt.Key_Shift, 1),
        (QtCore.Qt.Key_Control, 4),
        (QtCore.Qt.Key_Alt, 8),
    )

    def shortcut_display(tool_state, keys):
        return {
            "icon": tool_state.get("icon"),
            "label": tool_state.get("label") or tool_state.get("status_title") or tool_state.get("id"),
            "keys": keys,
        }

    def shortcut_mask(keys):
        return sum(mask for key, mask in key_masks if key in (keys or []))

    shortcuts = []
    variants = []
    for index, shortcut_item in enumerate(shortcut_items):
        tool_id = shortcut_item.get("id")
        if not tool_id:
            continue
        overrides = {
            key: value
            for key, value in shortcut_item.items()
            if key not in {"id", "section", "shortcuts", "keys"}
        }
        if shortcut_item.get("callback") is not None:
            variant = dict(tool)
            variant.update(overrides)
            variant["id"] = shortcut_item.get("variant_id") or "{}__shortcut_{}".format(tool.get("id", tool_id), index)
            variant.pop("shortcut_variants", None)
        else:
            variant = get_tool(tool_id, **overrides)
        variant["mask"] = shortcut_mask(shortcut_item.get("keys", []))
        variant.setdefault("shortcuts", [])
        shortcuts.append(shortcut_display(variant, shortcut_item.get("keys", [])))
        variants.append(variant)

    tool["shortcuts"] = shortcuts
    tool["shortcut_variants"] = variants
    return tool


def get_tool(tool_id, **overrides):
    """Retrieve a tool definition with optional overrides."""
    definitions = _tool_definitions()
    if tool_id not in definitions:
        raise KeyError("Unknown tool id: {}".format(tool_id))

    tool = dict(definitions[tool_id])
    from TheKeyMachine.core import i18n
    tool = i18n.localize_tool(tool.get("i18n_key", tool_id), tool)
    tool.update(overrides)
    tool.setdefault("id", tool_id)
    tool.setdefault("default", False)

    menu_definition = tool.get("menu")
    if isinstance(menu_definition, dict):
        # A tool's own right-click "menu" dict is declared once, inline,
        # right next to its "label"/"tooltip" -- it has no "command"/"id" of
        # its own to translate by, but it always belongs to *this* tool_id,
        # so pass that along as the fallback lang.json key instead of
        # requiring every package to redundantly repeat "command": tool_id
        # on every such menu (see toolbar_menus._declared_item_text).
        tool["menu"] = lambda _menu, source_widget=None, definition=menu_definition, owner_id=tool_id: toolbar_menus.build_declared_menu(
            definition, parent_widget=source_widget, owner_command_id=owner_id
        )

    callback = tool.get("callback")
    if callback and not (
        getattr(callback, "_tkm_trigger_proxy", False)
        or getattr(callback, "_tkm_tool_dispatch", False)
    ):
        # Every surface executes the registered command. Keeping same-named API
        # callbacks direct used to give toolbar/menu clicks a different
        # progress, undo, and refresh path than hotkeys and shelf buttons.
        tool["callback"] = trigger.make_command_callback(tool_id, callback)
    return tool


def is_tool_available(tool_id):
    definition = _tool_definitions().get(tool_id, {})
    available = definition.get("available", True)
    return bool(available() if callable(available) else available)


_ITEM_OVERRIDE_EXCLUDED_KEYS = {"id", "section", "shortcuts", "default"}


def _item_overrides(item):
    """Fields on a section item that override its tool definition's own.

    A section item is mostly identity (``"id"``) plus layout/behavior keys
    that don't belong on the tool itself (``"section"``, ``"shortcuts"``,
    ``"default"``) -- everything else is a per-placement override passed
    straight through to ``get_tool(tool_id, **overrides)``. Both
    ``get_tool_section``'s item-resolution loop and
    ``resolve_section_shortcuts``'s targeted re-resolution need exactly this
    same split, so it lives here once instead of twice.
    """
    return {key: value for key, value in item.items() if key not in _ITEM_OVERRIDE_EXCLUDED_KEYS}


def get_tool_section(section_id, resolve_items=True, toolbar_id=None):
    definitions = _section_definitions()
    section_def = definitions.get(section_id)
    if not section_def:
        return None

    section = dict(section_def)
    section["id"] = section_id
    section["_toolbar_id"] = toolbar_id
    section.setdefault("color", COLORS.toolbar.gray.hex)
    if section.get("label"):
        from TheKeyMachine.core import i18n

        section["label"] = i18n.localize_section_label(
            section.get("i18n_key", section_id),
            section.get("_package_file"),
            section["label"],
        )
    if not resolve_items:
        section["items"] = list(section_def.get("items", []))
        return section

    resolved = []
    for item in section_def.get("items", []):
        if isinstance(item, str):
            resolved.append(item)
            continue
        section_ref = item.get("section")
        if section_ref:
            nested = get_tool_section(section_ref, toolbar_id=toolbar_id)
            if nested:
                resolved.append({"type": "group", "items": nested.get("items", []), "label": nested.get("label")})
            continue
        tool_id = item.get("id")
        if not tool_id or not is_tool_available(tool_id):
            continue
        tool = get_tool(tool_id, **_item_overrides(item))
        tool["default"] = is_pinned_by_default(toolbar_id, tool_id)
        resolved.append(_apply_shortcuts(tool, item))
    section["items"] = resolved
    return section


def resolve_section_shortcuts(section_id, wanted_ids=None):
    """Freshly re-translate just the modifier-key shortcut data for a section.

    A tool's "shortcuts" hint list and held-modifier "shortcut_variants"
    (see ``_apply_shortcuts``) are baked into its widget once, at build
    time -- unlike a plain label/tooltip, they aren't recoverable from
    ``get_tool(tool_id)`` alone, since they live on the *section* item, not
    the tool definition. A translation refresh still needs fresh, re-localized
    copies of them, but only for the handful of items in a section that
    actually declare "shortcuts" (most don't). Reusing
    ``get_tool_section``'s full ``resolve_items=True`` pass would also
    re-resolve every item's icon and default-pin state for nothing, so this
    walks the raw (unresolved) item list directly and calls the same
    ``get_tool`` + ``_apply_shortcuts`` pair only for items that need it,
    optionally further limited to ``wanted_ids`` (a caller's already-built
    widget keys, letting it skip items it isn't even tracking).

    Returns ``{item_id: (shortcuts, shortcut_variants)}``.
    """
    section = get_tool_section(section_id, resolve_items=False)
    if not section:
        return {}

    wanted = set(wanted_ids) if wanted_ids is not None else None
    resolved = {}

    def _walk(items):
        for item in items or ():
            if not isinstance(item, dict):
                continue
            section_ref = item.get("section")
            if section_ref:
                nested = get_tool_section(section_ref, resolve_items=False)
                if nested:
                    _walk(nested.get("items", []))
                continue
            item_id = item.get("id")
            if not item_id or not item.get("shortcuts"):
                continue
            if wanted is not None and item_id not in wanted:
                continue
            if not is_tool_available(item_id):
                continue
            tool = _apply_shortcuts(get_tool(item_id, **_item_overrides(item)), item)
            resolved[item_id] = (tool.get("shortcuts", []), tool.get("shortcut_variants", []))

    _walk(section.get("items", []))
    return resolved


def get_section_icon(section_id):
    section = get_tool_section(section_id)
    if not section:
        return None
    if section.get("icon"):
        return section.get("icon")

    def find_icon(items):
        for item in items:
            if item == "separator" or not isinstance(item, dict):
                continue
            if item.get("type") == "group":
                icon = find_icon(item.get("items", []))
                if icon:
                    return icon
                continue
            icon = item.get("icon")
            if icon:
                return icon
        return None

    return find_icon(section.get("items", []))


def get_tool_tint_color(tool_id, default=None):
    section_definitions = _section_definitions()

    def find_tint(item, inherited_color=None):
        if item == "separator" or item is None:
            return None
        if not isinstance(item, dict):
            return None

        section_ref = item.get("section")
        if section_ref:
            section = section_definitions.get(section_ref)
            if not section:
                return None
            section_color = section.get("color", COLORS.toolbar.gray.hex)
            for child in section.get("items", []):
                color = find_tint(child, inherited_color=section_color)
                if color is not None:
                    return color
            return None

        if item.get("id") == tool_id:
            return inherited_color

        for shortcut in item.get("shortcuts") or []:
            color = find_tint(shortcut, inherited_color=inherited_color)
            if color is not None:
                return color
        return None

    for section in section_definitions.values():
        section_color = section.get("color", COLORS.toolbar.gray.hex)
        for item in section.get("items", []):
            color = find_tint(item, inherited_color=section_color)
            if color is not None:
                return color
    return default


def group_sections_by_color(sections):
    """Group *sections* (dicts with a ``"color"`` key) into runs of consecutive matching colors.

    Returns a list of lists, each holding the original section dicts for one
    contiguous same-color run, in their original order. Two sections of the
    same color that are not adjacent produce two separate runs.

    Used by the Workspaces editor to present -- and reorder -- whole color
    runs as one unit instead of individual sections. The toolbar's own
    inter-section spacing does *not* use this: it compares each *visible*
    section's live color directly at layout time (see
    ``customWidgets.QFlowLayout``), since a hidden (unpinned) section can drop
    out of a run and change which sections actually end up adjacent.
    """
    groups = []
    previous_color = object()
    for section in sections:
        color = section.get("color")
        if not groups or color != previous_color:
            groups.append([])
        groups[-1].append(section)
        previous_color = color
    return groups


def get_toolbar_sections(layout_id, resolve_items=True):
    if not layout_id:
        return []
    definitions = _section_definitions()
    section_ids = [
        section_id
        for section_id in get_ordered_section_ids(layout_id)
        for definition in (definitions.get(section_id),)
        if definition is not None
        if not definition.get("hotkeys")
        and definition.get("toolbar") is not False
    ]
    return [
        section
        for section in (
            get_tool_section(section_id, resolve_items=resolve_items, toolbar_id=layout_id)
            for section_id in section_ids
        )
        if section is not None
    ]
