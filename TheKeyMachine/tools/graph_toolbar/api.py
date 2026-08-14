"""Menu callbacks for the Graph Editor toolbar tool package."""


def _show_menu(command_id):
    from TheKeyMachine.maya import shelf

    return shelf.show_tool_menu_at_cursor(command_id)


def show_settings_menu(*_args):
    return _show_menu("graph_settings_menu")


def show_dock_menu(*_args):
    return _show_menu("graph_dock_menu")
