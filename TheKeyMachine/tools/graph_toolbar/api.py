from maya import cmds

try:
    from PySide6 import QtCore
except Exception:
    from PySide2 import QtCore

import TheKeyMachine.mods.settingsMod as settings
import TheKeyMachine.widgets.util as wutil
import TheKeyMachine.core.runtime_manager as runtime


_GRAPH_LAYOUT = "customGraph_columnLayout"


class CustomGraphBus(QtCore.QObject):
    graph_toolbar_enabled_changed = QtCore.Signal(bool)


custom_graph_bus = CustomGraphBus()


def get_graph_toolbar_checkbox_state() -> bool:
    return bool(settings.get_setting("graph_toolbar_enabled", True))


def is_graph_toolbar_visible() -> bool:
    return bool(cmds.columnLayout(_GRAPH_LAYOUT, exists=True))


def emit_graph_toolbar_state() -> None:
    try:
        custom_graph_bus.graph_toolbar_enabled_changed.emit(get_graph_toolbar_checkbox_state())
    except Exception:
        pass


def sync_graph_toolbar_watch() -> None:
    try:
        runtime.get_runtime_manager().set_graph_editor_watch_enabled(get_graph_toolbar_checkbox_state())
    except Exception:
        pass


def _disconnect_graph_toolbar_sync(callback) -> None:
    try:
        custom_graph_bus.graph_toolbar_enabled_changed.disconnect(callback)
    except Exception:
        pass


def _set_checked_safely(widget, checked: bool) -> bool:
    signal_blocker = getattr(widget, "blockSignals", None)
    blocked = False
    if callable(signal_blocker):
        try:
            blocked = widget.blockSignals(True)
        except Exception:
            blocked = False
    try:
        widget.setChecked(bool(checked))
        return True
    except Exception:
        return False
    finally:
        if callable(signal_blocker):
            try:
                widget.blockSignals(blocked)
            except Exception:
                pass


def bind_graph_toolbar_toggle(widget) -> None:
    if not widget:
        return

    def _sync(enabled):
        try:
            if not wutil.is_valid_widget(widget):
                _disconnect_graph_toolbar_sync(_sync)
                return
        except Exception:
            pass

        if not _set_checked_safely(widget, bool(enabled)):
            _disconnect_graph_toolbar_sync(_sync)

    try:
        _set_checked_safely(widget, get_graph_toolbar_checkbox_state())
    except Exception:
        pass

    try:
        custom_graph_bus.graph_toolbar_enabled_changed.connect(_sync)
    except Exception:
        pass

    destroyed_signal = getattr(widget, "destroyed", None)
    if destroyed_signal:
        try:
            destroyed_signal.connect(lambda *_: _disconnect_graph_toolbar_sync(_sync))
        except Exception:
            pass


def set_graph_toolbar_enabled(enabled: bool, *, apply: bool = True) -> None:
    settings.set_setting("graph_toolbar_enabled", bool(enabled))
    sync_graph_toolbar_watch()
    emit_graph_toolbar_state()
    if not apply:
        return

    from TheKeyMachine.core import customGraph

    if enabled and is_graph_toolbar_visible():
        return

    try:
        if enabled:
            QtCore.QTimer.singleShot(0, customGraph.createCustomGraph)
        else:
            QtCore.QTimer.singleShot(0, customGraph.removeCustomGraph)
    except Exception:
        if enabled:
            customGraph.createCustomGraph()
        else:
            customGraph.removeCustomGraph()
