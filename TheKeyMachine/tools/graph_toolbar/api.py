"""Public entry point for the Graph Editor toolbar."""

from TheKeyMachine.tools.graph_toolbar import controller


GRAPH_TOOLBAR_DOCK_SETTING = controller.GRAPH_TOOLBAR_DOCK_SETTING
DOCK_BOTTOM_GRAPH = controller.DOCK_BOTTOM_GRAPH
DOCK_TOP_GRAPH = controller.DOCK_TOP_GRAPH
DOCK_BOTTOM_MENU = controller.DOCK_BOTTOM_MENU
DOCK_OPTIONS = controller.DOCK_OPTIONS
custom_graph_bus = controller.custom_graph_bus


def _show_menu(command_id):
    from TheKeyMachine.mods import shelfMod

    return shelfMod.show_tool_menu_at_cursor(command_id)


def show_settings_menu(*_args):
    return _show_menu("graph_settings_menu")


def show_dock_menu(*_args):
    return _show_menu("graph_dock_menu")


def get_widget():
    return controller.get_widget()


def create(*args, **kwargs):
    return controller.create(*args, **kwargs)


def remove():
    return controller.remove()


def ensure():
    return controller.ensure()


def apply_alignment(alignment_label=None):
    return controller.apply_alignment(alignment_label)


def move_dock(position=None):
    return controller.move_dock(position)


def get_graph_toolbar_checkbox_state():
    return controller.get_graph_toolbar_checkbox_state()


def is_graph_toolbar_visible():
    return controller.is_graph_toolbar_visible()


def emit_graph_toolbar_state():
    return controller.emit_graph_toolbar_state()


def sync_graph_toolbar_watch():
    return controller.sync_graph_toolbar_watch()


def bind_graph_toolbar_toggle(widget):
    return controller.bind_graph_toolbar_toggle(widget)


def set_graph_toolbar_enabled(enabled, *, apply=True):
    return controller.set_graph_toolbar_enabled(enabled, apply=apply)


def shutdown_graph_toolbar_runtime():
    return controller.shutdown_graph_toolbar_runtime()
