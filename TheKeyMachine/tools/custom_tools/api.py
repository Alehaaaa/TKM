"""Public entry point for user-defined custom tools."""


def build_menu(menu, source_widget=None):
    from TheKeyMachine.tools.custom_tools import widgets

    return widgets.build_menu(menu, source_widget=source_widget)


def show_menu(*_args):
    from TheKeyMachine.mods import shelfMod

    return shelfMod.show_tool_menu_at_cursor("custom_tools")
