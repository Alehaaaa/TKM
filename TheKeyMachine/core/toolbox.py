import importlib
import json
import os
import pkgutil


class ToolObject(object):
    """Declarative metadata owned by one tool package."""

    ORDER = 1000
    TOOLS = {}
    SECTION = None
    SECTIONS = ()

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
    from TheKeyMachine.mods.tooltipsMod import separator

    def _resolve(value):
        if isinstance(value, list):
            return [_resolve(item) for item in value]
        if isinstance(value, dict):
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

import TheKeyMachine.core.trigger as trigger
import TheKeyMachine.core.toolMenus as toolMenus
from TheKeyMachine.data.colors import COLORS

_PACKAGE_TOOL_DEFINITIONS = None
_PACKAGE_SECTION_DEFINITIONS = None




TOOLBAR_SECTION_IDS = {
    # Preserve the original toolbox order. Split packages stay adjacent to the
    # section they belonged to before tool discovery was package-based.
    "main": (
        "system",
        "nudge_tools", "default_tools", "bake_tools", "key_sync_tools",
        "slider_blend", "slider_tween", "slider_tangent",
        "isolate_tools", "locator_tools", "selection_tools", "opposite_tools", "mirror_tools", "align_tools",
        "pose_animation_section", "tangents", "manipulator_tools",
        "animation_offset_tools", "movers_tools",
        "temp_pivot_tools", "follow_cam_tools",
        "link_tools", "worldspace_tools",
        "attribute_tools", "selection_set_tools", "orbit_tools", "tracer_tools",
        "global_tools",
        "graph_tools", "animation_tools", "custom_tools_section", "background_runner_tools", "search_tools",
    ),
    "graph": (
        "nudge_tools", "default_tools", "bake_tools", "key_sync_tools",
        "slider_blend", "slider_tween", "slider_tangent",
        "isolate_tools", "locator_tools", "selection_tools", "opposite_tools", "mirror_tools", "align_tools",
        "pose_animation_section", "tangents", "manipulator_tools",
        "animation_offset_tools", "movers_tools",
        "temp_pivot_tools", "follow_cam_tools",
        "link_tools", "worldspace_tools",
        "attribute_tools", "selection_set_tools", "orbit_tools", "tracer_tools",
        "graph_tools", "animation_tools", "custom_tools_section",
    ),
}


def is_pinned_by_default(toolbar_id, tool_id):
    from TheKeyMachine.core import toolWorkspaces
    active_ws = toolWorkspaces.get_active_workspace()
    ws = toolWorkspaces.WORKSPACE_DEFAULTS.get(active_ws, toolWorkspaces.WORKSPACE_DEFAULTS["standard"])
    pins = ws["pins"].get(toolbar_id, frozenset())
    return tool_id in pins


def is_section_on_toolbar(toolbar_id, section_id):
    return section_id in TOOLBAR_SECTION_IDS.get(toolbar_id, ())


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


def _iter_menu_command_ids(items):
    for item in items or ():
        if isinstance(item, str):
            if item != "separator":
                yield item
            continue
        if not isinstance(item, dict):
            continue
        if item.get("type") == "menu":
            for command_id in _iter_menu_command_ids(item.get("items")):
                yield command_id
            continue
        command_id = item.get("command") or item.get("id")
        if command_id:
            yield command_id


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
    from TheKeyMachine.core import toolWorkspaces
    for workspace in toolWorkspaces.WORKSPACE_DEFAULTS.values():
        for toolbar_id, tool_ids in workspace["pins"].items():
            for tool_id in tool_ids:
                if tool_id not in pinnable_ids:
                    errors.append("workspace pins unknown tool {!r} in toolbar {!r}".format(tool_id, toolbar_id))

    for tool_id, tool in tools.items():
        menu = tool.get("menu")
        if not isinstance(menu, dict):
            continue
        for command_id in _iter_menu_command_ids(menu.get("items")):
            if command_id not in tools:
                errors.append("tool {!r} menu references unknown command {!r}".format(tool_id, command_id))
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
        packages.append((tool_object.ORDER, module_info.name, tool_object))

    if import_errors:
        raise RuntimeError("Unable to import tool packages:\n- " + "\n- ".join(import_errors))

    for _order, package_name, tool_object in sorted(packages, key=lambda item: (item[0], item[1])):
        package_tools = tool_object.tools()
        for definition in package_tools.values():
            definition.setdefault("_package", package_name)
        package_sections = tool_object.sections()
        for definition in package_sections.values():
            definition.setdefault("_package", package_name)
        _merge_owned(tools, tool_owners, package_tools, package_name, "tool")
        _merge_owned(sections, section_owners, package_sections, package_name, "section")
    _validate_definition_graph(tools, sections)
    return tools, sections


def reset_package_cache():
    """Force package metadata to be rediscovered after an in-process reload."""
    global _PACKAGE_TOOL_DEFINITIONS, _PACKAGE_SECTION_DEFINITIONS
    _PACKAGE_TOOL_DEFINITIONS = None
    _PACKAGE_SECTION_DEFINITIONS = None


def _package_definitions():
    global _PACKAGE_TOOL_DEFINITIONS, _PACKAGE_SECTION_DEFINITIONS
    if _PACKAGE_TOOL_DEFINITIONS is None:
        (
            _PACKAGE_TOOL_DEFINITIONS,
            _PACKAGE_SECTION_DEFINITIONS,
        ) = _collect_package_definitions()
    return _PACKAGE_TOOL_DEFINITIONS, _PACKAGE_SECTION_DEFINITIONS


def _tool_definitions():
    package_tools, _package_sections = _package_definitions()
    return dict(package_tools)


def _section_definitions():
    _package_tools, package_sections = _package_definitions()
    return dict(package_sections)


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
    tool.update(overrides)
    tool.setdefault("id", tool_id)
    tool.setdefault("default", False)

    menu_definition = tool.get("menu")
    if isinstance(menu_definition, dict):
        tool["menu"] = lambda _menu, source_widget=None, definition=menu_definition: toolMenus.build_declared_menu(
            definition, parent_widget=source_widget
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


def get_tool_section(section_id, resolve_items=True, toolbar_id=None):
    definitions = _section_definitions()
    section_def = definitions.get(section_id)
    if not section_def:
        return None

    section = dict(section_def)
    section["id"] = section_id
    section["_toolbar_id"] = toolbar_id
    section.setdefault("color", COLORS.toolbar.gray.hex)
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
        overrides = {key: value for key, value in item.items() if key not in {"id", "section", "shortcuts", "default"}}
        tool = get_tool(tool_id, **overrides)
        tool["default"] = is_pinned_by_default(toolbar_id, tool_id)
        resolved.append(_apply_shortcuts(tool, item))
    section["items"] = resolved
    return section


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


def get_toolbar_sections(layout_id, resolve_items=True):
    if not layout_id:
        return []
    definitions = _section_definitions()
    section_ids = [
        section_id
        for section_id in TOOLBAR_SECTION_IDS.get(layout_id, ())
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
