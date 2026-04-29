try:
    from PySide6 import QtCore
except Exception:
    from PySide2 import QtCore

import TheKeyMachine.mods.settingsMod as settings
import TheKeyMachine.widgets.util as wutil
import TheKeyMachine.core.runtime_manager as runtime
from TheKeyMachine.tools import common as toolCommon


class CustomGraphBus(QtCore.QObject):
    graph_toolbar_enabled_changed = QtCore.Signal(bool)


custom_graph_bus = CustomGraphBus()


def get_graph_toolbar_checkbox_state() -> bool:
    return bool(settings.get_setting("graph_toolbar_enabled", True))


def is_graph_toolbar_visible() -> bool:
    try:
        from TheKeyMachine.core import customGraph

        widget = customGraph.getCustomGraphWidget()
        return bool(widget and wutil.is_valid_widget(widget) and widget.isVisible())
    except Exception:
        return False


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
    relays = getattr(custom_graph_bus, "_tkm_graph_toolbar_sync_relays", [])
    remaining = []
    for relay, relay_callback in relays:
        if relay_callback is callback:
            try:
                relay.deleteLater()
            except Exception:
                pass
        else:
            remaining.append((relay, relay_callback))
    custom_graph_bus._tkm_graph_toolbar_sync_relays = remaining


def bind_graph_toolbar_toggle(widget) -> None:
    if widget is None:
        return

    def _sync(enabled):
        try:
            if not wutil.is_valid_widget(widget):
                _disconnect_graph_toolbar_sync(_sync)
                return
        except Exception:
            pass

        if not toolCommon.set_checked_safely(widget, bool(enabled)):
            _disconnect_graph_toolbar_sync(_sync)

    try:
        toolCommon.set_checked_safely(widget, get_graph_toolbar_checkbox_state())
    except Exception:
        pass

    relay = toolCommon.replace_tracked_connection(
        widget,
        "_tkm_graph_toolbar_sync_relay",
        custom_graph_bus.graph_toolbar_enabled_changed,
        _sync,
        parent=widget,
    )
    relays = getattr(custom_graph_bus, "_tkm_graph_toolbar_sync_relays", [])
    relays = [(existing_relay, callback) for existing_relay, callback in relays if callback is not _sync]
    if relay is not None:
        relays.append((relay, _sync))
    custom_graph_bus._tkm_graph_toolbar_sync_relays = relays

    destroyed_signal = getattr(widget, "destroyed", None)
    if destroyed_signal:
        toolCommon.replace_tracked_connection(
            widget,
            "_tkm_graph_toolbar_destroyed_slot",
            destroyed_signal,
            lambda *_: _disconnect_graph_toolbar_sync(_sync),
            parent=widget,
        )


def set_graph_toolbar_enabled(enabled: bool, *, apply: bool = True) -> None:
    settings.set_setting("graph_toolbar_enabled", bool(enabled))
    sync_graph_toolbar_watch()
    emit_graph_toolbar_state()
    if not apply:
        return

    from TheKeyMachine.core import customGraph

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
