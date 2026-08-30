"""Maya-side state and commands for the Onion Skin viewport renderer."""

from __future__ import absolute_import

from maya import cmds  # type: ignore

from TheKeyMachine.core import runtime, settings
from TheKeyMachine.data import icons
from TheKeyMachine.maya import maya_api
from TheKeyMachine.maya.runtime import TkmSceneNode
from TheKeyMachine.tools.onion_skin import diagnostics


SETTINGS_NAMESPACE = "onion_skin"
OVERRIDE_NAME = "tkmOnionSkinRenderer"
SCENE_NODE = "Onion_Skin"
OBJECTS_ATTRIBUTE = "managedObjects"

DEFAULTS = {
    "relative_frames": [-2, -1, 1, 2],
    "relative_opacities": {"-2": 30, "-1": 55, "1": 55, "2": 30},
    "absolute_frames": [],
    "absolute_opacities": {},
    "past_color": [72, 210, 151],
    "future_color": [238, 100, 100],
    "absolute_color": [100, 150, 245],
    "display_style": "shape",
    "global_opacity": 70,
    "outline_width": 3,
    "draw_behind": True,
    "relative_to_keys": False,
    "relative_step": 1,
    "max_buffer_size": 200,
    "auto_clear_buffer": True,
    "ghost_inbetweens": False,
    "inbetween_count": 1,
}

# Settings that change *which* frames the renderer needs (as opposed to a
# purely cosmetic tweak like opacity or outline width, which every already
# -captured ghost still applies live at blend time -- see BlendOperation.shader()).
# Only these are worth kicking the auto-updater for; anything else would
# just evict and needlessly recapture ghosts that didn't actually go stale.
_FRAME_SET_SETTINGS = frozenset(
    {"relative_to_keys", "relative_step", "ghost_inbetweens", "inbetween_count"}
)

_renderer = None
_last_panel = None
_preference_cache = None


def _scene_node(create=False):
    path = "|{}|{}".format("TheKeyMachine", SCENE_NODE)
    if cmds.objExists(path):
        return TkmSceneNode(path)
    if not create:
        return None
    return TkmSceneNode.root().child(
        SCENE_NODE,
        lock_transform=True,
        icon=icons.get("onion_skin"),
    )


def _objects_plug(create=False):
    node = _scene_node(create=create)
    if node is None:
        return None
    plug = "{}.{}".format(node.name, OBJECTS_ATTRIBUTE)
    if not cmds.objExists(plug) and create:
        cmds.addAttr(
            node.name,
            longName=OBJECTS_ATTRIBUTE,
            attributeType="message",
            multi=True,
            hidden=True,
        )
    return plug if cmds.objExists(plug) else None


def _canonical_object_name(name):
    matches = cmds.ls(name, long=True) or []
    return matches[0] if matches else None


def load_scene_objects():
    """Read managed objects from message connections on this tool's scene node."""
    plug = _objects_plug(create=False)
    if not plug:
        return []
    names = []
    for index in cmds.getAttr(plug, multiIndices=True) or []:
        destination = "{}[{}]".format(plug, index)
        source = cmds.connectionInfo(destination, sourceFromDestination=True) or ""
        name = _canonical_object_name(source.rsplit(".", 1)[0]) if source else None
        if name and name not in names:
            names.append(name)
    diagnostics.log("scene objects loaded", objects=names)
    return names


def save_scene_objects(objects):
    """Persist object references as rename-safe Maya message connections."""
    names = []
    for value in objects or []:
        name = _canonical_object_name(value)
        if name and name not in names:
            names.append(name)
    existing_node = _scene_node(create=False)
    plug = _objects_plug(create=bool(names) or existing_node is not None)
    if not plug:
        return []

    existing_indices = set(cmds.getAttr(plug, multiIndices=True) or [])
    for index, name in enumerate(names):
        destination = "{}[{}]".format(plug, index)
        source = cmds.connectionInfo(destination, sourceFromDestination=True) or ""
        source_name = (
            _canonical_object_name(source.rsplit(".", 1)[0]) if source else None
        )
        if source_name == name:
            existing_indices.discard(index)
            continue
        if source:
            cmds.disconnectAttr(source, destination)
        cmds.connectAttr(
            "{}.message".format(name),
            destination,
            force=True,
        )
        existing_indices.discard(index)

    for index in sorted(existing_indices):
        destination = "{}[{}]".format(plug, index)
        source = cmds.connectionInfo(destination, sourceFromDestination=True) or ""
        if source:
            cmds.disconnectAttr(source, destination)
        try:
            cmds.removeMultiInstance(destination, b=True)
        except Exception:
            pass
    diagnostics.log("scene objects saved", objects=names)
    return names


def get_setting(key):
    if _preference_cache is not None and key in _preference_cache:
        return _preference_cache[key]
    default = DEFAULTS.get(key)
    return settings.get_setting(key, default, namespace=SETTINGS_NAMESPACE)


def set_setting(key, value, apply=True, refresh_window=True):
    global _preference_cache
    settings.set_setting(key, value, namespace=SETTINGS_NAMESPACE)
    if _preference_cache is not None:
        _preference_cache[key] = value
    renderer = get_renderer(create=False)
    if renderer is not None and apply:
        renderer.apply_preferences(load_preferences())
        if key in _FRAME_SET_SETTINGS:
            _bake_missing_frames()
    if refresh_window:
        _refresh_window()
    return value


def load_preferences():
    global _preference_cache
    if _preference_cache is None:
        _preference_cache = dict((key, get_setting(key)) for key in DEFAULTS)
    return dict(_preference_cache)


def get_renderer(create=False):
    global _renderer
    if _renderer is None and create:
        from TheKeyMachine.tools.onion_skin.renderer import OnionSkinRenderOverride

        _renderer = OnionSkinRenderOverride(OVERRIDE_NAME)
        _renderer.apply_preferences(load_preferences(), refresh=False)
        _renderer.set_objects(load_scene_objects(), refresh=False)
        diagnostics.log("renderer created", override=OVERRIDE_NAME)
    return _renderer


def initialize_renderer():
    renderer = get_renderer(create=True)
    diagnostics.log(
        "runtime",
        maya_version=cmds.about(version=True),
        api_version=cmds.about(apiVersion=True),
    )
    renderer.register()
    diagnostics.log("renderer ready", registered=renderer.is_registered())
    return renderer


def shutdown_renderer():
    global _renderer
    set_enabled(False)
    if _renderer is not None:
        _renderer.deregister()
        _renderer = None
        diagnostics.log("renderer shut down")


def _model_panels():
    try:
        return cmds.getPanel(type="modelPanel") or []
    except Exception:
        return []


def _focused_model_panel():
    try:
        panel = cmds.getPanel(withFocus=True)
        if panel in _model_panels():
            return panel
    except Exception:
        pass
    for panel in _model_panels():
        try:
            if cmds.modelEditor(panel, query=True, activeView=True):
                return panel
        except Exception:
            pass
    panels = _model_panels()
    return panels[0] if panels else None


def _panel_override(panel):
    try:
        return cmds.modelEditor(panel, query=True, rendererOverrideName=True) or ""
    except Exception:
        return ""


def active_panels():
    return [panel for panel in _model_panels() if _panel_override(panel) == OVERRIDE_NAME]


def is_enabled():
    return bool(active_panels())


def set_enabled(enabled, *_args, **_kwargs):
    global _last_panel
    enabled = bool(enabled)
    if enabled:
        initialize_renderer()
        panel = _last_panel if _last_panel in _model_panels() else _focused_model_panel()
        diagnostics.log(
            "enable requested",
            focused_panel=panel,
            available_panels=_model_panels(),
        )
        if panel:
            try:
                cmds.modelEditor(panel, edit=True, rendererOverrideName=OVERRIDE_NAME)
                _last_panel = panel
                diagnostics.log(
                    "viewport override applied",
                    panel=panel,
                    active_override=_panel_override(panel),
                )
            except Exception as exc:
                diagnostics.log_error("viewport override failed", exc, panel=panel)
                cmds.warning("Onion Skin: couldn't enable the viewport renderer: {}".format(exc))
        else:
            diagnostics.log("viewport override skipped", reason="no model panel")
    else:
        for panel in active_panels():
            try:
                cmds.modelEditor(panel, edit=True, rendererOverrideName="")
                _last_panel = panel
                diagnostics.log("viewport override removed", panel=panel)
            except Exception as exc:
                diagnostics.log_error("viewport override removal failed", exc, panel=panel)
    runtime.get_runtime_manager().set_control_state("onion_skin_toggle", is_enabled())
    _refresh_window()
    _sync_auto_update()
    return is_enabled()


def add_selected_objects(*_args, **_kwargs):
    renderer = initialize_renderer()
    selection = cmds.ls(selection=True, long=True) or []
    if selection:
        selection = _with_descendants(selection)
    diagnostics.log("add selection requested", selection=selection)
    if not selection:
        cmds.warning("Onion Skin: select one or more objects to add")
        return []
    changed = renderer.add_objects(selection, refresh=False)
    save_scene_objects(renderer.object_names())
    if changed:
        refresh_viewport()
    diagnostics.log("objects added", objects=renderer.object_names())
    _refresh_window()
    return renderer.object_names()


def _with_descendants(objects):
    expanded = []
    for name in objects:
        if name not in expanded:
            expanded.append(name)
        try:
            descendants = cmds.listRelatives(
                name, allDescendents=True, fullPath=True, type="transform"
            ) or []
        except Exception:
            descendants = []
        for child in descendants:
            if child not in expanded:
                expanded.append(child)
    return expanded


def remove_objects(objects):
    renderer = get_renderer(create=False)
    if renderer is not None:
        changed = renderer.remove_objects(objects, refresh=False)
        save_scene_objects(renderer.object_names())
        if changed:
            refresh_viewport()
    else:
        remove = set(objects or [])
        save_scene_objects([name for name in load_scene_objects() if name not in remove])
    _refresh_window()


def clear_objects(*_args):
    renderer = get_renderer(create=False)
    if renderer is not None:
        changed = renderer.clear_objects(refresh=False)
    else:
        changed = False
    save_scene_objects([])
    if changed:
        refresh_viewport()
    _refresh_window()


def object_names():
    renderer = get_renderer(create=False)
    return renderer.object_names() if renderer is not None else load_scene_objects()


def restore_scene_objects(renderer=None):
    renderer = renderer or get_renderer(create=False)
    names = load_scene_objects()
    if renderer is not None:
        renderer.set_objects(names, force=True)
        names = renderer.object_names()
    _refresh_window()
    return names


def clear_buffer(*_args, **_kwargs):
    renderer = get_renderer(create=False)
    if renderer is not None:
        renderer.clear_buffer()
        diagnostics.log("buffer cleared by user")


def refresh_current_frame(*_args, **_kwargs):
    renderer = get_renderer(create=False)
    current_time = maya_api.current_time()
    if renderer is not None and current_time is not None:
        renderer.invalidate_frame(current_time)
        diagnostics.log("current frame refreshed", frame=current_time)


def refresh_viewport():
    try:
        cmds.refresh(force=True)
    except Exception:
        pass


def display_style_choices():
    return [
        {"label": "Shaded", "value": "shaded", "description": "Keep the lighting and material read from nearby poses."},
        {"label": "Shape", "value": "shape", "description": "Read pose spacing and overlapping shapes as solid color."},
        {"label": "Outline", "value": "outline", "description": "Check arcs and contours without covering the current pose."},
    ]


def get_display_style():
    value = get_setting("display_style")
    return value if value in ("shaded", "shape", "outline") else "shape"


def set_display_style(value, *_args, **kwargs):
    value = str(value)
    if value not in ("shaded", "shape", "outline"):
        value = "shape"
    return set_setting(
        "display_style", value, refresh_window=kwargs.get("refresh_window", False)
    )


def opacity_choices():
    return [
        {"label": "{}%".format(value), "value": value, "description": "Show onion poses at {}% strength.".format(value)}
        for value in (25, 50, 70, 85, 100)
    ]


def get_global_opacity():
    return int(get_setting("global_opacity"))


def set_global_opacity(value, *_args, **kwargs):
    return set_setting(
        "global_opacity", int(value), refresh_window=kwargs.get("refresh_window", False)
    )


def outline_width_choices():
    return [
        {"label": "{} px".format(value), "value": value, "description": "Use a {} pixel contour in Outline style.".format(value)}
        for value in (1, 2, 3, 5, 8)
    ]


def get_outline_width():
    return int(get_setting("outline_width"))


def set_outline_width(value, *_args):
    return set_setting("outline_width", int(value), refresh_window=False)


def buffer_size_choices():
    return [
        {
            "label": "{} Frames".format(value),
            "value": value,
            "description": (
                "Keep up to {} visited frames, adjusted to the viewport memory budget."
            ).format(value),
        }
        for value in (50, 100, 200, 400)
    ]


def get_max_buffer_size():
    return int(get_setting("max_buffer_size"))


def set_max_buffer_size(value, *_args):
    return set_setting("max_buffer_size", int(value), refresh_window=False)


def is_draw_behind():
    return bool(get_setting("draw_behind"))


def set_draw_behind(value, *_args):
    return set_setting("draw_behind", bool(value), refresh_window=False)


def is_auto_clear_buffer():
    return bool(get_setting("auto_clear_buffer"))


def set_auto_clear_buffer(value, *_args):
    return set_setting("auto_clear_buffer", bool(value), refresh_window=False)


def is_relative_to_keys():
    return bool(get_setting("relative_to_keys"))


def set_relative_to_keys(value, *_args):
    return set_setting("relative_to_keys", bool(value), refresh_window=False)


def is_ghost_inbetweens():
    return bool(get_setting("ghost_inbetweens"))


def set_ghost_inbetweens(value, *_args):
    return set_setting("ghost_inbetweens", bool(value), refresh_window=False)


def inbetween_count_choices():
    return [
        {
            "label": "{} Sample{}".format(value, "" if value == 1 else "s"),
            "value": value,
            "description": (
                "Show {} evenly spaced sample{} between the current pose and each nearby key."
            ).format(value, "" if value == 1 else "s"),
        }
        for value in (1, 2, 3, 4)
    ]


def get_inbetween_count():
    return int(get_setting("inbetween_count"))


def set_inbetween_count(value, *_args):
    return set_setting("inbetween_count", max(1, min(4, int(value))), refresh_window=False)


def frame_step_choices():
    return [
        {
            "label": "{} Frame{}".format(value, "" if value == 1 else "s"),
            "value": value,
            "description": "Compare poses every {} frame{}.".format(
                value, "" if value == 1 else "s"
            ),
        }
        for value in (1, 2, 3, 4, 6, 8)
    ]


def get_relative_step():
    return int(get_setting("relative_step"))


def set_relative_step(value, *_args):
    return set_setting("relative_step", max(1, int(value)), refresh_window=False)


def set_relative_frames(frames, opacities=None, refresh_window=True):
    global _preference_cache
    frames = sorted(set(int(frame) for frame in frames if int(frame) != 0))
    values = {"relative_frames": frames}
    if opacities is not None:
        values["relative_opacities"] = dict((str(int(key)), int(value)) for key, value in opacities.items())
    settings.set_settings(values, namespace=SETTINGS_NAMESPACE)
    if _preference_cache is not None:
        _preference_cache.update(values)
    renderer = get_renderer(create=False)
    if renderer is not None:
        renderer.apply_preferences(load_preferences())
        _bake_missing_frames()
    if refresh_window:
        _refresh_window()


# The fixed set of offsets the right-click menu's "Nearby Frames" submenu
# offers -- matches the range the old window UI used to show as rows.
NEARBY_FRAME_OFFSETS = (-4, -3, -2, -1, 1, 2, 3, 4)


def relative_frame_default_opacity(offset):
    """Fall-off used for a nearby-frame ghost that has no explicit opacity yet."""
    return max(20, 70 - 18 * (abs(int(offset)) - 1))


def is_relative_frame_enabled(offset):
    return int(offset) in set(int(value) for value in get_setting("relative_frames") or [])


def set_relative_frame_enabled(offset, enabled, *_args):
    """Toggle one nearby-frame ghost on/off -- the menu row's checkable callback.

    New ghosts pick up the same distance-based opacity fall-off the window's
    per-offset rows used to default to; there's no per-offset opacity control
    in the menu, only the enable/disable that's the actual "setting" here.
    """
    offset = int(offset)
    enabled = bool(enabled)
    frames = set(int(value) for value in get_setting("relative_frames") or [])
    opacities = dict(get_setting("relative_opacities") or {})
    if enabled:
        frames.add(offset)
        opacities.setdefault(str(offset), relative_frame_default_opacity(offset))
    else:
        frames.discard(offset)
    # The window never displays nearby-frame state (see NEARBY_FRAME_OFFSETS'
    # own docstring -- that's menu-only), so there's nothing there to rebuild.
    set_relative_frames(frames, opacities, refresh_window=False)


def set_absolute_frames(frames, opacities=None, refresh_window=True):
    global _preference_cache
    frames = sorted(set(int(frame) for frame in frames))
    values = {"absolute_frames": frames}
    if opacities is not None:
        values["absolute_opacities"] = dict((str(int(key)), int(value)) for key, value in opacities.items())
    settings.set_settings(values, namespace=SETTINGS_NAMESPACE)
    if _preference_cache is not None:
        _preference_cache.update(values)
    renderer = get_renderer(create=False)
    if renderer is not None:
        renderer.apply_preferences(load_preferences())
        _bake_missing_frames()
    if refresh_window:
        _refresh_window()


def _held_pose_state():
    """The current (frames, opacities) pair, in the mutable form every held-pose edit starts from."""
    frames = list(get_setting("absolute_frames") or [])
    opacities = dict(get_setting("absolute_opacities") or {})
    return frames, opacities


def add_current_absolute_frame(*_args):
    """Hold the current pose -- the "Hold Current Pose" button's callback."""
    current_time = maya_api.current_time()
    if current_time is None:
        diagnostics.log("hold pose skipped", reason="current time unavailable")
        return
    frame = int(round(current_time))
    frames, opacities = _held_pose_state()
    if frame not in frames:
        frames.append(frame)
    opacities.setdefault(str(frame), 50)
    diagnostics.log("pose held", frame=frame)
    set_absolute_frames(frames, opacities)


def set_absolute_frame_opacity(frame, opacity):
    """Update one held pose's strength -- the window's per-row opacity slider."""
    frame = int(frame)
    frames, opacities = _held_pose_state()
    opacities[str(frame)] = int(opacity)
    set_absolute_frames(frames, opacities, refresh_window=False)


def remove_absolute_frame(frame):
    """Drop one held pose -- the window row's remove button.

    Unlike set_absolute_frame_opacity() (a cosmetic, in-place slider tweak
    that leaves every row where it is), this changes which rows exist, so
    it needs the window to actually rebuild its list -- refresh_window
    stays at its default True.
    """
    frame = int(frame)
    frames, opacities = _held_pose_state()
    frames = [value for value in frames if int(value) != frame]
    opacities.pop(str(frame), None)
    diagnostics.log("held pose removed", frame=frame)
    set_absolute_frames(frames, opacities)


def _refresh_window():
    try:
        from TheKeyMachine.tools.onion_skin import api

        api.refresh_open_window()
    except Exception:
        pass


def _sync_auto_update():
    try:
        from TheKeyMachine.tools.onion_skin import api

        api.sync_auto_update()
    except Exception:
        pass


def _bake_missing_frames():
    # A settings or list change (turning on Ghost In-Betweens, switching to
    # Neighboring Key Poses, adding/removing a held pose or nearby frame...)
    # can grow the set of frames the renderer now needs. Nothing already
    # cached went stale here -- only the *set* of wanted frames changed --
    # so this only ever bakes whatever's newly missing, immediately and
    # directly, the same way the manual Refresh button already bakes the
    # current frame. It deliberately does NOT go through
    # OnionUpdateController.request_refresh(): that path first evicts every
    # required frame's cache, which is the right call for an actual pose
    # edit (an already-cached ghost can now show the wrong pose) but would
    # otherwise throw away perfectly good, still-valid ghosts just to
    # trickle-rebake them a couple at a time through the debounced
    # scheduler -- which is also why, without this, a newly added held pose
    # or toggled frame previously only appeared once the next scrub or edit
    # happened to trigger a bake.
    try:
        from TheKeyMachine.tools.onion_skin import api

        api.bake_missing_frames_now()
    except Exception:
        pass
