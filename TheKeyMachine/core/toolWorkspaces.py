from TheKeyMachine.mods import settingsMod

WORKSPACES = [
    {"id": "standard",     "name": "Standard"},
    {"id": "professional", "name": "Professional"},
    {"id": "minimal",      "name": "Minimal"},
]

WORKSPACE_SETTING   = "toolbar_workspace"
MODIFIED_SETTING    = "toolbar_workspace_modified"

_STANDARD_MAIN = frozenset([
    "attribute_switcher_euler_filter", "align_objects", "animation_offset", "animation_tools",
    "animation_recovery",
    "attribute_switcher", "background_runners", "bake_animation_1", "blend_connect_neighbors",
    "copy_animation", "copy_pose", "create_tracer", "default_object_values",
    "delete_all_animation", "depth_mover", "follow_cam", "gimbal", "graph_extra_tools",
    "isolate_master", "link_copy", "micro_move", "mirror", "nudge_left", "nudge_right", "nudge_value",
    "orbit", "remove_redundant_keys", "search_window", "select_rig_controls", "selection_sets", "selector",
    "share_keys", "snap", "tangent_auto", "tangent_bouncy", "tangent_linear", "tangent_spline", "tangent_step",
    "temp_pivot", "tween_tweener", "ws_copy_frame"
])

_STANDARD_GRAPH = frozenset([
    "align_objects", "animation_offset", "attribute_switcher", "bake_animation_1",
    "copy_animation", "copy_pose", "create_tracer", "custom_graph", "default_object_values", "follow_cam", "graph_extra_tools",
    "isolate_master", "link_copy", "mirror", "nudge_left", "nudge_right", "nudge_value", "orbit", "overshoot_sliders", "select_opposite",
    "select_rig_controls", "selection_sets", "selector", "share_keys", "snap", "tangent_auto", "tangent_bouncy", "tangent_linear",
    "tangent_spline", "tangent_step", "temp_pivot", "ws_copy_frame"
])

_MINIMAL_MAIN = frozenset([
    "nudge_left", "nudge_right", "nudge_value",
    "blend_connect_neighbors",
    "tween_tweener",
    "tangent_auto", "tangent_linear", "tangent_step",
    "selector", "selection_sets",
    "copy_animation", "copy_pose",
    "mirror", "align_objects",
    "link_copy", "ws_copy_frame",
    "attribute_switcher",
    "temp_pivot",
    "micro_move",
    "animation_offset",
    "create_tracer",
    "animation_tools",
    "animation_recovery",
    "attribute_switcher_euler_filter",
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
    "link_copy", "ws_copy_frame",
    "temp_pivot",
    "animation_offset",
    "create_tracer",
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
    return settingsMod.get_setting(WORKSPACE_SETTING, "standard")


def set_active_workspace(ws_id: str):
    settingsMod.set_settings({
        WORKSPACE_SETTING: ws_id,
        MODIFIED_SETTING: False
    })


def is_workspace_modified() -> bool:
    return settingsMod.get_setting(MODIFIED_SETTING, False)


def mark_workspace_modified(modified: bool = True):
    settingsMod.set_setting(MODIFIED_SETTING, modified)


def get_active_workspace_name() -> str:
    ws_id = get_active_workspace()
    for ws in WORKSPACES:
        if ws["id"] == ws_id:
            return ws["name"]
    return "Standard"


def get_workspace_label(ws_id: str) -> str:
    name = "Standard"
    for ws in WORKSPACES:
        if ws["id"] == ws_id:
            name = ws["name"]
            break
    
    if ws_id == get_active_workspace() and is_workspace_modified():
        return f"{name} *"
    return name


def apply_workspace(ws_id: str, sections, apply_alignment_fn):
    set_active_workspace(ws_id)
    ws = WORKSPACE_DEFAULTS.get(ws_id)
    if not ws:
        return
    
    for section in sections:
        ns = getattr(section, "_settings_namespace", "") or ""
        section_toolbar_id = "graph" if "graph" in ns else "main"
        pins = ws["pins"].get(section_toolbar_id, set())
        
        pin_states = {}
        if hasattr(section, "_menu_metadata"):
            for item in section._menu_metadata:
                if item.get("type") == "widget" and item.get("id"):
                    pin_key = item["id"]
                    expected_visible = pin_key in pins
                    actual_visible = False
                    if hasattr(section, "_is_pin_key_checked"):
                        actual_visible = section._is_pin_key_checked(pin_key)
                        
                    if expected_visible != actual_visible:
                        pin_states[pin_key] = expected_visible
                
        if pin_states:
            section._apply_widget_pin_states(pin_states)

    if apply_alignment_fn:
        apply_alignment_fn(ws["alignment"])


def restore_workspace_defaults(sections, apply_alignment_fn):
    ws_id = get_active_workspace()
    apply_workspace(ws_id, sections, apply_alignment_fn)

def is_current_workspace_deviating(sections, get_alignment_fn=None):
    ws_id = get_active_workspace()
    ws = WORKSPACE_DEFAULTS.get(ws_id)
    if not ws:
        return False
        
    if get_alignment_fn:
        current_align = get_alignment_fn()
        if current_align and current_align != ws["alignment"]:
            return True
            
    for section in sections:
        ns = getattr(section, "_settings_namespace", "") or ""
        section_toolbar_id = "graph" if "graph" in ns else "main"
        expected_pins = ws["pins"].get(section_toolbar_id, set())
        
        if hasattr(section, "_menu_metadata"):
            for item in section._menu_metadata:
                if item.get("type") == "widget" and item.get("id"):
                    pin_key = item["id"]
                    expected_visible = pin_key in expected_pins
                    # To check visibility without touching UI, we can use _is_pin_key_checked
                    actual_visible = False
                    if hasattr(section, "_is_pin_key_checked"):
                        actual_visible = section._is_pin_key_checked(pin_key)
                    if expected_visible != actual_visible:
                        return True
                        
    return False
