"""Module-owned shutdown hooks, independent of Maya and Qt.

Register at import time with ``@on_shutdown()``. Hooks must be idempotent and
run on Maya's main thread. Registrations remain available after unload so
reopening the UI without reimporting modules keeps the same cleanup coverage.
"""

from enum import IntEnum
import logging


class ShutdownBlocked(RuntimeError):
    """Cleanup cannot proceed while a dependent resource is still busy."""


class ShutdownPhase(IntEnum):
    QUIESCE = -1
    UI = 0
    OPERATIONS = 1
    BACKGROUND = 2
    TOOLS = 3
    NATIVE = 4
    CACHES = 5


_hooks = {}
_running = False
_logger = logging.getLogger(__name__)


def on_shutdown(*, phase=ShutdownPhase.TOOLS):
    """Register a zero-argument function; reimports replace the same owner.

    The decorator returns the original function, preserving its normal API.
    Phase ordering releases dependants before their shared dependencies.
    """
    if not isinstance(phase, ShutdownPhase):
        raise TypeError("phase must be a ShutdownPhase")

    def register(callback):
        if not callable(callback):
            raise TypeError("shutdown hook must be callable")
        key = (callback.__module__, callback.__qualname__)
        _hooks[key] = (phase, callback)
        return callback

    return register


def shutdown():
    """Run a stable ordered snapshot, returning the names of failed hooks.

    A failing hook cannot skip other owners. Nested shutdown calls are no-ops;
    registrations made during shutdown take effect on the next call.
    """
    global _running
    if _running:
        return ()
    _running = True
    failures = []
    try:
        ordered = sorted(_hooks.items(), key=lambda item: (item[1][0], item[0]))
        for (module, name), (_, callback) in ordered:
            try:
                callback()
            except ShutdownBlocked:
                raise
            except Exception:
                owner = module + "." + name
                failures.append(owner)
                _logger.exception("Shutdown hook failed: %s", owner)
    finally:
        _running = False
    return tuple(failures)
