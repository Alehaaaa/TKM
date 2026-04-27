try:
    from PySide6 import QtCore  # type: ignore
except ImportError:
    from PySide2 import QtCore  # type: ignore


class LinkObjectPulseThread(QtCore.QThread):
    tick = QtCore.Signal()

    def __init__(self, interval_seconds=0.3, parent=None):
        super().__init__(parent)
        self._interval_ms = max(1, int(float(interval_seconds) * 1000))
        self._running = False

    def run(self):
        self._running = True
        while self._running:
            self.msleep(self._interval_ms)
            if not self._running:
                break
            self.tick.emit()

    def stop(self):
        self._running = False
