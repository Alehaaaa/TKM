"""Public entry point for user-defined custom tools."""


def build_menu(menu, source_widget=None):
    from TheKeyMachine.tools.custom_tools import widgets

    return widgets.build_menu(menu, source_widget=source_widget)


def show_menu(*_args):
    from TheKeyMachine.maya import shelf

    return shelf.show_tool_menu_at_cursor("custom_tools")
