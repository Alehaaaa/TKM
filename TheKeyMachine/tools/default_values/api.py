from TheKeyMachine.tools.default_values import controller


def apply_all(*_args, **kwargs):
    return controller.apply_defaults(tool_operation=kwargs.pop("tool_operation", None))


def apply_translations(*_args, **kwargs):
    return controller.apply_defaults(translations=True, tool_operation=kwargs.pop("tool_operation", None))


def apply_rotations(*_args, **kwargs):
    return controller.apply_defaults(rotations=True, tool_operation=kwargs.pop("tool_operation", None))


def apply_scales(*_args, **kwargs):
    return controller.apply_defaults(scales=True, tool_operation=kwargs.pop("tool_operation", None))


def apply_trs(*_args, **kwargs):
    return controller.apply_defaults(translations=True, rotations=True, scales=True, tool_operation=kwargs.pop("tool_operation", None))


def remove_selected(*_args, **kwargs):
    return controller.remove_selected(tool_operation=kwargs.pop("tool_operation", None))


def clear_all(*_args, **kwargs):
    return controller.clear_all(tool_operation=kwargs.pop("tool_operation", None))
