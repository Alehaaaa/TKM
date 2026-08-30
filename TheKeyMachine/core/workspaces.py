"""Global toolbar workspace definitions, persistence, and application logic."""

import re

from TheKeyMachine.core import settings

# Namespace + keys used by the Workspaces editor (tools/workspaces) for data
# that does not belong in the default preferences file: user-created
# workspaces and display-name overrides for any workspace (built-in or not).
WORKSPACES_NAMESPACE = "workspaces"
CUSTOM_WORKSPACES_SETTING = "custom_workspaces"
NAME_OVERRIDES_SETTING = "workspace_name_overrides"

WORKSPACES = [
    {"id": "standard",     "name": "Standard"},
    {"id": "professional", "name": "Professional"},
    {"id": "minimal",      "name": "Minimal"},
]

WORKSPACE_SETTING   = "toolbar_workspace"
MODIFIED_SETTING    = "toolbar_workspace_modified"

_STANDARD_MAIN = frozenset([
    "smart_euler_filter", "align_objects", "animation_offset", "animation_tools",
    "animation_recovery",
    "attribute_switcher", "background_runners", "bake_animation_1", "blend_connect_neighbors",
    "copy_animation", "copy_pose", "create_tracer", "onion_skin", "default_object_values",
    "delete_all_animation", "depth_mover", "follow_cam", "gimbal", "graph_extra_tools",
    "isolate_master", "copy_link", "micro_move", "mirror", "nudge_left", "nudge_right", "nudge_value",
    "orbit", "remove_redundant_keys", "search_window", "select_rig_controls", "selection_sets", "selector",
    "share_keys", "snap", "tangent_auto", "tangent_bouncy", "tangent_linear", "tangent_spline", "tangent_step",
    "temp_pivot", "tween_tweener", "copy_worldspace"
])

_STANDARD_GRAPH = frozenset([
    "align_objects", "animation_offset", "attribute_switcher", "bake_animation_1",
    "global_curve", "copy_animation", "copy_pose", "create_tracer", "custom_graph", "default_object_values", "follow_cam", "graph_extra_tools",
    "isolate_master", "copy_link", "mirror", "nudge_left", "nudge_right", "nudge_value", "orbit", "overshoot_sliders", "pause_viewport", "select_opposite",
    "select_rig_controls", "selection_sets", "selector", "share_keys", "snap", "tangent_auto", "tangent_bouncy", "tangent_linear",
    "tangent_spline", "tangent_step", "temp_pivot", "copy_worldspace"
])

_MINIMAL_MAIN = frozenset([
    "nudge_left", "nudge_right", "nudge_value",
    "blend_connect_neighbors",
    "tween_tweener",
    "tangent_auto", "tangent_linear", "tangent_step",
    "selector", "selection_sets",
    "copy_animation", "copy_pose",
    "mirror", "align_objects",
    "copy_link", "copy_worldspace",
    "attribute_switcher",
    "temp_pivot",
    "micro_move",
    "animation_offset",
    "create_tracer", "onion_skin",
    "animation_tools",
    "animation_recovery",
    "smart_euler_filter",
    "select_rig_controls",
    "background_runners",
    "search_window"
])

_PROFESSIONAL_MAIN = frozenset([
    "nudge_value",
    "blend_connect_neighbors",
    "tween_tweener",
    "selector",
    "copy_pose", "copy_animation",
    "copy_link", "copy_worldspace",
    "temp_pivot",
    "animation_offset",
    "create_tracer", "onion_skin",
    "animation_tools",
    "animation_recovery"
])

WORKSPACE_DEFAULTS = {
    "standard": {
        "alignment": "Center",
        "pins": {
            "main": _STANDARD_MAIN,
            "graph": _STANDARD_GRAPH
        }
    },
    "professional": {
        "alignment": "Right",
        "pins": {
            "main": _PROFESSIONAL_MAIN,
            "graph": _STANDARD_GRAPH - {"search_window", "background_runners", "custom_tools", "create_tracer", "orbit"}
        }
    },
    "minimal": {
        "alignment": "Right",
        "pins": {
            "main": _MINIMAL_MAIN,
            "graph": _MINIMAL_MAIN
        }
    }
}


def get_active_workspace() -> str:
    return settings.get_setting(WORKSPACE_SETTING, "standard")


def set_active_workspace(ws_id: str):
    settings.set_settings({
        WORKSPACE_SETTING: ws_id,
        MODIFIED_SETTING: False
    })


def is_workspace_modified() -> bool:
    return settings.get_setting(MODIFIED_SETTING, False)


def mark_workspace_modified(modified: bool = True):
    settings.set_setting(MODIFIED_SETTING, modified)


def get_custom_workspaces() -> list:
    return settings.get_setting(CUSTOM_WORKSPACES_SETTING, [], namespace=WORKSPACES_NAMESPACE) or []


def _set_custom_workspaces(entries) -> None:
    settings.set_setting(CUSTOM_WORKSPACES_SETTING, entries, namespace=WORKSPACES_NAMESPACE)


def set_custom_workspaces(entries) -> None:
    """Replace the full list of custom workspaces (used by import/export)."""
    _set_custom_workspaces(list(entries or []))


def set_name_overrides(overrides: dict) -> None:
    """Replace the full set of workspace display-name overrides (import/export)."""
    settings.set_setting(NAME_OVERRIDES_SETTING, dict(overrides or {}), namespace=WORKSPACES_NAMESPACE)


def get_name_overrides() -> dict:
    return settings.get_setting(NAME_OVERRIDES_SETTING, {}, namespace=WORKSPACES_NAMESPACE) or {}


def is_custom_workspace(ws_id: str) -> bool:
    return any(entry.get("id") == ws_id for entry in get_custom_workspaces())


def list_workspaces() -> list:
    """Every workspace selectable in the Workspaces editor: built-ins, then user-created ones."""
    overrides = get_name_overrides()
    entries = [
        {"id": ws["id"], "name": overrides.get(ws["id"], ws["name"]), "builtin": True}
        for ws in WORKSPACES
    ]
    for custom in get_custom_workspaces():
        entries.append({
            "id": custom["id"],
            "name": overrides.get(custom["id"], custom.get("name", "Workspace")),
            "builtin": False,
        })
    return entries


def _all_workspace_ids() -> set:
    return {ws["id"] for ws in WORKSPACES} | {entry.get("id") for entry in get_custom_workspaces()}


def _slugify_workspace_name(name: str) -> str:
    existing_ids = _all_workspace_ids()
    base = re.sub(r"[^a-z0-9]+", "_", (name or "workspace").strip().lower()).strip("_") or "workspace"
    candidate = base
    counter = 2
    while candidate in existing_ids:
        candidate = "{}_{}".format(base, counter)
        counter += 1
    return candidate


def create_workspace(name: str, snapshot: dict) -> str:
    """Create a new custom workspace from a per-toolbar snapshot.

    ``snapshot`` looks like::

        {"main":  {"alignment": "Center", "pins": [...tool ids...],
                   "docking": ["TimeSlider", "top"], "section_order": [...ids...]},
         "graph": {"alignment": "Center", "pins": [...tool ids...],
                   "docking": "bottom_graph_editor", "section_order": [...ids...]}}
    """
    entries = get_custom_workspaces()
    ws_id = _slugify_workspace_name(name)
    entries.append({"id": ws_id, "name": (name or "Workspace").strip() or "Workspace", "snapshot": snapshot or {}})
    _set_custom_workspaces(entries)
    return ws_id


def get_custom_workspace_snapshot(ws_id: str):
    for entry in get_custom_workspaces():
        if entry.get("id") == ws_id:
            return entry.get("snapshot") or {}
    return None


def rename_workspace(ws_id: str, new_name: str) -> bool:
    new_name = (new_name or "").strip()
    if not new_name or not ws_id:
        return False

    if any(ws["id"] == ws_id for ws in WORKSPACES):
        overrides = get_name_overrides()
        overrides[ws_id] = new_name
        settings.set_setting(NAME_OVERRIDES_SETTING, overrides, namespace=WORKSPACES_NAMESPACE)
        return True

    entries = get_custom_workspaces()
    for entry in entries:
        if entry.get("id") == ws_id:
            entry["name"] = new_name
            _set_custom_workspaces(entries)
            return True
    return False


def delete_workspace(ws_id: str) -> bool:
    """Remove a custom workspace. Built-in workspaces can't be deleted."""
    if not ws_id or not is_custom_workspace(ws_id):
        return False

    entries = [entry for entry in get_custom_workspaces() if entry.get("id") != ws_id]
    _set_custom_workspaces(entries)

    overrides = get_name_overrides()
    if ws_id in overrides:
        overrides.pop(ws_id, None)
        settings.set_setting(NAME_OVERRIDES_SETTING, overrides, namespace=WORKSPACES_NAMESPACE)

    if get_active_workspace() == ws_id:
        set_active_workspace("standard")
    return True


def get_active_workspace_name() -> str:
    ws_id = get_active_workspace()
    for entry in list_workspaces():
        if entry["id"] == ws_id:
            return entry["name"]
    return "Standard"


def get_workspace_label(ws_id: str) -> str:
    name = "Standard"
    for entry in list_workspaces():
        if entry["id"] == ws_id:
            name = entry["name"]
            break

    if ws_id == get_active_workspace() and is_workspace_modified():
        return f"{name} *"
    return name


def _pin_state_changes(section, expected_pins):
    """Return only pin states that differ from one toolbar section."""
    if not hasattr(section, "_menu_metadata"):
        return {}
    get_checked = getattr(section, "_is_pin_key_checked", None)
    changes = {}
    for item in section._menu_metadata:
        pin_key = item.get("id")
        if item.get("type") != "widget" or not pin_key:
            continue
        expected = pin_key in expected_pins
        actual = bool(get_checked and get_checked(pin_key))
        if actual != expected:
            changes[pin_key] = expected
    return changes


def _workspace_pins(workspace, section):
    namespace = getattr(section, "_settings_namespace", "") or ""
    toolbar_id = "graph" if "graph" in namespace else "main"
    return workspace["pins"].get(toolbar_id, set())


def apply_workspace(ws_id: str, sections, apply_alignment_fn):
    set_active_workspace(ws_id)
    ws = WORKSPACE_DEFAULTS.get(ws_id)
    if not ws:
        return

    for section in sections:
        pin_states = _pin_state_changes(section, _workspace_pins(ws, section))
        if pin_states:
            section._apply_widget_pin_states(pin_states)

    if apply_alignment_fn:
        apply_alignment_fn(ws["alignment"])


def restore_workspace_defaults(sections, apply_alignment_fn):
    apply_workspace(get_active_workspace(), sections, apply_alignment_fn)


def is_current_workspace_deviating(sections, get_alignment_fn=None):
    ws = WORKSPACE_DEFAULTS.get(get_active_workspace())
    if not ws:
        return False

    if get_alignment_fn:
        current_align = get_alignment_fn()
        if current_align and current_align != ws["alignment"]:
            return True

    return any(
        _pin_state_changes(section, _workspace_pins(ws, section))
        for section in sections
    )
