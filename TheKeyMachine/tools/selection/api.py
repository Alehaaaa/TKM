"""Public entry point for selection tools."""

from TheKeyMachine.tools.selection import controller


def open_selector(*args):
    return controller.open_selector(*args)


def select_hierarchy(*args, tool_operation=None):
    return controller.select_hierarchy(*args, tool_operation=tool_operation)


def select_rig_controls(*args, tool_operation=None):
    return controller.select_rig_controls(*args, tool_operation=tool_operation)


def select_rig_controls_animated(*args, tool_operation=None):
    return controller.select_rig_controls_animated(
        *args, tool_operation=tool_operation
    )


def select_all_animation_curves(*args):
    return controller.select_all_animation_curves(*args)


def clear_selected_keys(*args):
    return controller.clear_selected_keys(*args)
