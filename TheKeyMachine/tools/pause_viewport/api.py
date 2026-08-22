"""Checkable toggle to pause the Maya viewport refresh for performance."""

from TheKeyMachine.maya import viewport as maya_viewport


def is_viewport_paused():
    """Whether the viewport refresh toggle is currently checked."""
    return maya_viewport.is_paused()


def set_viewport_paused(paused=False, *_args):
    """Pause or resume the viewport refresh to improve performance."""
    return maya_viewport.set_paused(paused)
