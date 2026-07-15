"""Background workers used by the Search tool."""

from TheKeyMachine.Qt import QtCore  # type: ignore

from TheKeyMachine.tools.search import logic


class SearchCatalogThread(QtCore.QThread):
    """Build the shared tool catalog without blocking the Search window."""

    loaded = QtCore.Signal(object)
    failed = QtCore.Signal(str)

    def run(self):
        try:
            self.loaded.emit(logic.build_command_rows())
        except Exception as exc:
            self.failed.emit(str(exc))
