"""Viewport-level Maya helpers."""

from maya import cmds, utils

from TheKeyMachine.core import runtime
from TheKeyMachine.core import settings


_COMMAND_ERRORS = (
    RuntimeError,
    ValueError,
    TypeError,
    AttributeError,
    KeyError,
    IndexError,
)
_CALLBACK_KEY = "viewport:auto_pause"
_HUD_NAME = "TKM_PauseViewportButton"
# Persisted in the shared TKM preferences store (see core/settings.py)
# instead of a dedicated Maya optionVar, so it syncs with the rest of TKM's
# state instead of living separately in userPrefs.mel.
_VIEWPORT_SETTINGS_NAMESPACE = "viewport"
_AUTO_PAUSE_SETTING = "auto_pause_enabled"
_auto_pause_enabled = False
_auto_refresh_active = False
_auto_refresh_generation = 0
_pending_auto_refresh_generation = None


def _manager(start=True):
    try:
        return (
            runtime.get_runtime_manager()
            if start
            else runtime.get_existing_runtime_manager()
        )
    except _COMMAND_ERRORS:
        return None


def _remove_callbacks():
    manager = _manager(start=False)
    if manager is not None:
        manager.disconnect_callbacks(_CALLBACK_KEY)


def _safe_refresh(suspend=None, force=False):
    try:
        if suspend is not None:
            cmds.refresh(suspend=bool(suspend))
        if force:
            cmds.refresh(force=True)
        return True
    except _COMMAND_ERRORS:
        return False


def _force_viewport_update():
    _safe_refresh(force=True)


def _hud_exists():
    try:
        return bool(cmds.headsUpDisplay(_HUD_NAME, exists=True))
    except _COMMAND_ERRORS:
        return False


def _show_pause_hud():
    if _hud_exists():
        return
    try:
        cmds.hudButton(
            _HUD_NAME,
            allowOverlap=True,
            section=7,
            block=5,
            blockSize="large",
            visible=True,
            label="Viewport Suspended (Click Here to Unlock)",
            buttonWidth=300,
            buttonShape="roundRectangle",
            releaseCommand=lambda *_args: set_paused(False),
        )
    except _COMMAND_ERRORS:
        pass


def _hide_pause_hud():
    if not _hud_exists():
        return
    try:
        cmds.headsUpDisplay(_HUD_NAME, remove=True)
    except _COMMAND_ERRORS:
        pass


def is_paused():
    """Return whether TKM's manual viewport suspend is currently enabled."""
    return _hud_exists()


def set_paused(paused, *_args):
    """Manually suspend or resume viewport refresh."""
    paused = bool(paused)
    if paused:
        _show_pause_hud()
        _safe_refresh(suspend=True)
        return True

    _hide_pause_hud()
    _safe_refresh(suspend=False)
    _force_viewport_update()
    if _auto_pause_enabled:
        _install_auto_pause_callbacks()
    return False


def toggle_paused(*_args):
    return set_paused(not is_paused())


def is_auto_pause_enabled():
    global _auto_pause_enabled
    saved = bool(
        settings.get_setting(
            _AUTO_PAUSE_SETTING, False, namespace=_VIEWPORT_SETTINGS_NAMESPACE
        )
    )
    if saved and not _auto_pause_enabled:
        _auto_pause_enabled = True
        _install_auto_pause_callbacks()
    return bool(_auto_pause_enabled)


def set_auto_pause_enabled(enabled, *_args):
    """Enable callback-driven viewport suspend with edit-triggered refreshes."""
    global _auto_pause_enabled
    _auto_pause_enabled = bool(enabled)
    _invalidate_pending_auto_refresh()
    settings.set_setting(
        _AUTO_PAUSE_SETTING, _auto_pause_enabled, namespace=_VIEWPORT_SETTINGS_NAMESPACE
    )

    _remove_callbacks()
    if _auto_pause_enabled:
        _install_auto_pause_callbacks()
        if not is_paused():
            _safe_refresh(suspend=True)
    elif not is_paused():
        _safe_refresh(suspend=False)
        _force_viewport_update()
    return _auto_pause_enabled


def toggle_auto_pause(*_args):
    return set_auto_pause_enabled(not is_auto_pause_enabled())


def apply_auto_pause(enabled, *_args):
    """Set manual suspend only when auto pause is enabled."""
    if is_auto_pause_enabled():
        return set_paused(enabled)
    return is_paused()


def _iter_model_panels():
    try:
        panels = cmds.getPanel(type="modelPanel") or []
    except _COMMAND_ERRORS:
        return []
    result = []
    for panel in panels:
        try:
            control = cmds.modelPanel(panel, query=True, control=True)
        except _COMMAND_ERRORS:
            control = None
        result.append(control or panel)
    return result


def _install_auto_pause_callbacks():
    _remove_callbacks()
    if not _auto_pause_enabled:
        return

    manager = _manager()
    if manager is None:
        return
    for panel in _iter_model_panels():
        manager.add_3d_view_pre_render_callback(
            panel,
            _on_pre_render,
            key=_CALLBACK_KEY,
        )
    manager.add_anim_curve_edited_callback(
        _on_anim_curve_edited,
        key=_CALLBACK_KEY,
        coalesce=False,
    )
    manager.add_anim_keyframe_edited_callback(
        _on_anim_keyframe_edited,
        key=_CALLBACK_KEY,
    )


def _suspend_if_auto():
    if not _auto_pause_enabled or _auto_refresh_active or is_paused():
        return
    _safe_refresh(suspend=True)


def _invalidate_pending_auto_refresh():
    global _auto_refresh_generation, _pending_auto_refresh_generation
    _auto_refresh_generation += 1
    _pending_auto_refresh_generation = None


def _schedule_auto_refresh():
    global _pending_auto_refresh_generation
    if not _auto_pause_enabled or is_paused():
        return
    if _pending_auto_refresh_generation is not None:
        return

    generation = _auto_refresh_generation
    _pending_auto_refresh_generation = generation
    try:
        utils.executeDeferred(
            lambda generation=generation: _flush_auto_refresh(generation)
        )
    except _COMMAND_ERRORS:
        if _pending_auto_refresh_generation == generation:
            _pending_auto_refresh_generation = None


def _flush_auto_refresh(generation):
    global _auto_refresh_active, _pending_auto_refresh_generation
    if _pending_auto_refresh_generation != generation:
        return
    _pending_auto_refresh_generation = None
    if generation != _auto_refresh_generation:
        return
    if not _auto_pause_enabled or is_paused():
        return

    _auto_refresh_active = True
    try:
        _safe_refresh(suspend=False)
        _force_viewport_update()
    finally:
        _auto_refresh_active = False
        if _auto_pause_enabled and not is_paused():
            _safe_refresh(suspend=True)


def _on_pre_render(*_args):
    _suspend_if_auto()


def _on_anim_curve_edited(*_args):
    _suspend_if_auto()


def _on_anim_keyframe_edited(*_args):
    # MAnimMessage is still enumerating callbacks here. Defer all refresh work
    # so viewport rendering cannot re-enter Maya's animation callback dispatch.
    _schedule_auto_refresh()


def cleanup():
    global _auto_pause_enabled
    _auto_pause_enabled = False
    _invalidate_pending_auto_refresh()
    _remove_callbacks()
    _hide_pause_hud()
    _safe_refresh(suspend=False)
