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


# Every other name this module exposes (`create`, `remove`, `ensure`,
# `get_widget`, `apply_alignment`, `move_dock`,
# `get_graph_toolbar_checkbox_state`, `is_graph_toolbar_visible`,
# `emit_graph_toolbar_state`, `sync_graph_toolbar_watch`,
# `bind_graph_toolbar_toggle`, `set_graph_toolbar_enabled`,
# `shutdown_graph_toolbar_runtime`, ...) is a pure 1:1 forward to the
# identically-named function on `controller` -- this module is the tool
# package's stable public facade (other packages import `...api`, not
# `...controller`, and `runtimeManager` even resolves
# "graph_toolbar.api" by string at shutdown), so the names need to keep
# working, but there's no reason to hand-write a wrapper per name just to
# call straight through. Resolve them lazily instead.
def __getattr__(name):
    return getattr(controller, name)
