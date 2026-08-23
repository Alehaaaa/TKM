from TheKeyMachine.core.Qt import QtCore

from TheKeyMachine.core import settings
import TheKeyMachine.ui.widgets.util as wutil
from TheKeyMachine.core import runtime
from TheKeyMachine.tools import common as toolCommon


GRAPH_TOOLBAR_ENABLED_SETTING = "graph_toolbar_enabled"
GRAPH_TOOLBAR_DOCK_SETTING = "graph_toolbar_dock_position"

# Anchor positions for the Graph Editor toolbar.
DOCK_OVER_MENU = "bottom_menu"  # directly below the Graph Editor's own menu bar
DOCK_OVER_GRAPH = "top_graph_editor"  # between the native button toolbar and the graph panel
DOCK_UNDER_GRAPH = "bottom_graph_editor"  # below the whole Graph Editor content

DOCK_DEFAULT = DOCK_OVER_GRAPH

DOCK_OPTIONS = (
    (DOCK_OVER_MENU, "Over Menu", "Place the toolbar directly below the Graph Editor menu."),
    (DOCK_OVER_GRAPH, "Over Graph", "Place the toolbar between the native toolbar and the graph panel."),
    (DOCK_UNDER_GRAPH, "Under Graph", "Place the toolbar below the graph panel."),
)


def _widgets():
    from TheKeyMachine.tools.graph_toolbar import widgets

    return widgets


def get_widget():
    return _widgets().getCustomGraphWidget()


def create(*args, **kwargs):
    return _widgets().createCustomGraph(*args, **kwargs)


def remove():
    return _widgets().removeCustomGraph()


def ensure():
    return _widgets().ensureCustomGraph()


def apply_alignment(alignment_label=None):
    return _widgets().applyCustomGraphAlignment(alignment_label)


def move_dock(position=None):
    return _widgets().moveCustomGraphDock(position)


class CustomGraphBus(QtCore.QObject):
    graph_toolbar_enabled_changed = QtCore.Signal(bool)


custom_graph_bus = CustomGraphBus()
_APPLY_TIMER = None


def _apply_enabled_state() -> None:
    if get_graph_toolbar_checkbox_state():
        create()
    else:
        remove()


def _get_apply_timer():
    global _APPLY_TIMER
    if _APPLY_TIMER is None:
        _APPLY_TIMER = QtCore.QTimer(custom_graph_bus)
        _APPLY_TIMER.setSingleShot(True)
        _APPLY_TIMER.timeout.connect(_apply_enabled_state)
    return _APPLY_TIMER


def _dispose_apply_timer() -> None:
    global _APPLY_TIMER
    timer = _APPLY_TIMER
    _APPLY_TIMER = None
    if timer is None:
        return
    try:
        timer.stop()
        timer.timeout.disconnect(_apply_enabled_state)
        timer.deleteLater()
    except (RuntimeError, ValueError, TypeError, AttributeError, KeyError, IndexError):
        pass


def get_graph_toolbar_checkbox_state() -> bool:
    return bool(settings.get_setting(GRAPH_TOOLBAR_ENABLED_SETTING, True))


def is_graph_toolbar_visible() -> bool:
    try:
        widget = get_widget()
        return bool(widget and wutil.is_valid_widget(widget) and widget.isVisible())
    except (ImportError, RuntimeError, ValueError, TypeError, AttributeError, KeyError, IndexError):
        return False


def emit_graph_toolbar_state() -> None:
    state = get_graph_toolbar_checkbox_state()
    try:
        custom_graph_bus.graph_toolbar_enabled_changed.emit(state)
    except (RuntimeError, ValueError, TypeError, AttributeError, KeyError, IndexError):
        pass
    manager = runtime.get_existing_runtime_manager()
    if manager is not None:
        try:
            manager.set_tool_state("custom_graph", state)
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

    try:
        _get_apply_timer().start(0)
    except (RuntimeError, ValueError, TypeError, AttributeError, KeyError, IndexError):
        _apply_enabled_state()


def shutdown_graph_toolbar_runtime() -> None:
    """Remove the live Graph Editor toolbar without changing the saved preference."""
    _dispose_apply_timer()
    manager = runtime.get_existing_runtime_manager()
    if manager is not None:
        try:
            manager.set_graph_editor_watch_enabled(False)
        except (RuntimeError, ValueError, TypeError, AttributeError, KeyError, IndexError):
            pass

    try:
        remove()
    except (ImportError, RuntimeError, ValueError, TypeError, AttributeError, KeyError, IndexError):
        pass
