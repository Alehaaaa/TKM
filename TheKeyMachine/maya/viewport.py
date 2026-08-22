"""Viewport-level Maya helpers."""

from maya import cmds


def is_paused():
    """Return whether Viewport 2.0 refresh is currently paused."""
    try:
        return bool(cmds.ogs(query=True, pause=True))
    except Exception:
        return False


def set_paused(paused, *_args):
    """Pause or resume the viewport refresh.

    ``cmds.ogs(pause=True)`` toggles Maya's own pause state rather than
    setting it directly, so this only calls it when the current state
    doesn't already match *paused*.
    """
    paused = bool(paused)
    try:
        if is_paused() != paused:
            cmds.ogs(pause=True)
    except Exception:
        pass
    return is_paused()


def toggle_paused(*_args):
    return set_paused(not is_paused())
