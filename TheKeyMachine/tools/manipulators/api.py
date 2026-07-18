"""Public entry point for smart manipulator hotkeys."""

from TheKeyMachine.tools.manipulators import controller


def smart_rotation(*args):
    return controller.smart_rotation(*args)


def smart_rotation_release(*args):
    return controller.smart_rotation_release(*args)


def smart_translation(*args):
    return controller.smart_translation(*args)


def smart_translation_release(*args):
    return controller.smart_translation_release(*args)
