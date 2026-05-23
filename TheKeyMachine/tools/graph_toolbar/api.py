try:
    from PySide6 import QtCore
except ImportError:
    from PySide2 import QtCore

import TheKeyMachine.mods.settingsMod as settings
import TheKeyMachine.widgets.util as wutil
import TheKeyMachine.core.runtimeManager as runtime
from TheKeyMachine.tools import common as toolCommon


GRAPH_TOOLBAR_ENABLED_SETTING = "graph_toolbar_enabled"


class CustomGraphBus(QtCore.QObject):
    graph_toolbar_enabled_changed = QtCore.Signal(bool)


custom_graph_bus = CustomGraphBus()


def get_graph_toolbar_checkbox_state() -> bool:
    return bool(settings.get_setting(GRAPH_TOOLBAR_ENABLED_SETTING, True))


def is_graph_toolbar_visible() -> bool:
    try:
        from TheKeyMachine.core import customGraph

        widget = customGraph.getCustomGraphWidget()
        return bool(widget and wutil.is_valid_widget(widget) and widget.isVisible())
    except (ImportError, RuntimeError, ValueError, TypeError, AttributeError, KeyError, IndexError):
        return False


def emit_graph_toolbar_state() -> None:
    try:
        custom_graph_bus.graph_toolbar_enabled_changed.emit(get_graph_toolbar_checkbox_state())
    except (RuntimeError, ValueError, TypeError, AttributeError, KeyError, IndexError):
        pass


def sync_graph_toolbar_watch() -> None:
    try:
        runtime.get_runtime_manager().set_graph_editor_watch_enabled(get_graph_toolbar_checkbox_state())
    except (RuntimeError, ValueError, TypeError, AttributeError, KeyError, IndexError):
        pass


def bind_graph_toolbar_toggle(widget) -> None:
    if widget is None:
        return
    toolCommon.bind_checked_signal(
        widget,
        custom_graph_bus.graph_toolbar_enabled_changed,
        get_graph_toolbar_checkbox_state,
        attr_name="_tkm_graph_toolbar_sync_relay",
    )
    toolCommon.sync_checked(widget, get_graph_toolbar_checkbox_state)


def set_graph_toolbar_enabled(enabled: bool, *, apply: bool = True) -> None:
    enabled = bool(enabled)
    settings.set_setting(GRAPH_TOOLBAR_ENABLED_SETTING, enabled)
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
    except (RuntimeError, ValueError, TypeError, AttributeError, KeyError, IndexError):
        if enabled:
            customGraph.createCustomGraph()
        else:
            customGraph.removeCustomGraph()


def shutdown_graph_toolbar_runtime() -> None:
    """Remove the live Graph Editor toolbar without changing the saved preference."""
    try:
        runtime.get_runtime_manager().set_graph_editor_watch_enabled(False)
    except (RuntimeError, ValueError, TypeError, AttributeError, KeyError, IndexError):
        pass

    try:
        from TheKeyMachine.core import customGraph

        customGraph.removeCustomGraph()
    except (ImportError, RuntimeError, ValueError, TypeError, AttributeError, KeyError, IndexError):
        pass
