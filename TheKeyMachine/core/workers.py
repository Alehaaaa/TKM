"""Cooperative Qt workers for background reads and network I/O.

Scene-mutating operations keep using tools.common's operation coordinator.
"""

from TheKeyMachine.core.Qt import QtCore
from time import monotonic

from TheKeyMachine.core.lifecycle import on_shutdown, ShutdownPhase, ShutdownBlocked


_BACKGROUND_THREADS = set()


class BackgroundThread(QtCore.QThread):
    """Keep background I/O alive safely if its UI owner is destroyed.

    Interruption is cooperative: detach result delivery immediately, then let
    the running call finish. Never terminate a thread or delete it while running.
    Subclasses declare their output signals and honor interruption in loops.
    """

    result_signals = ()
    join_on_shutdown = False

    def __init__(self, parent=None):
        super().__init__(QtCore.QCoreApplication.instance())
        self._cancelled = False
        _BACKGROUND_THREADS.add(self)
        self.finished.connect(self._release)
        if parent is not None:
            parent.destroyed.connect(self.cancel)

    def _release(self):
        _BACKGROUND_THREADS.discard(self)
        self.deleteLater()

    def cancel(self, *_args):
        self._cancelled = True
        self.requestInterruption()
        for name in self.result_signals:
            try:
                getattr(self, name).disconnect()
            except (RuntimeError, TypeError):
                pass
        if not self.isRunning():
            self._release()


@on_shutdown(phase=ShutdownPhase.QUIESCE)
def shutdown_background_threads():
    threads = tuple(_BACKGROUND_THREADS)
    for thread in threads:
        thread.cancel()
    # Catalog readers can import modules or touch command caches. They must
    # exit before teardown. Bound the total wait; never pump Qt events here.
    deadline = monotonic() + 0.2
    for thread in threads:
        if thread.join_on_shutdown and thread.isRunning():
            remaining_ms = max(0, int((deadline - monotonic()) * 1000))
            if not thread.wait(remaining_ms):
                raise ShutdownBlocked(
                    "A background reader is still finishing. Retry reload once it completes."
                )


class BackgroundCallThread(BackgroundThread):
    """Run a zero-arg callable off the Qt main thread and emit its result.

    Some data a window needs to open (Search and the Hotkeys editor both
    build a catalog of every declared tool, shortcut, and setting) is pure
    Python with no Maya API calls, but walking the whole registry is
    perceptible enough that building it synchronously on Maya's main thread
    would visibly hang the UI. Pass the build function in and run it here
    instead of hand-rolling another one-off QThread subclass per caller.
    """

    join_on_shutdown = True
    result_signals = ("loaded", "failed")
    loaded = QtCore.Signal(object)
    failed = QtCore.Signal(str)

    def __init__(self, func, parent=None):
        super().__init__(parent)
        self._func = func

    def run(self):
        try:
            if self._cancelled or self.isInterruptionRequested():
                return
            result = self._func()
            if not self._cancelled and not self.isInterruptionRequested():
                self.loaded.emit(result)
        except Exception as exc:
            if not self._cancelled and not self.isInterruptionRequested():
                self.failed.emit(str(exc))
