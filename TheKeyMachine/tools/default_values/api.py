from TheKeyMachine.tools.default_values import controller


def apply_all(*_args):
    return controller.apply_defaults()


def apply_translations(*_args):
    return controller.apply_defaults(translations=True)


def apply_rotations(*_args):
    return controller.apply_defaults(rotations=True)


def apply_scales(*_args):
    return controller.apply_defaults(scales=True)


def apply_trs(*_args):
    return controller.apply_defaults(translations=True, rotations=True, scales=True)


def save_selected(*_args):
    return controller.save_selected()


def remove_selected(*_args):
    return controller.remove_selected()


def clear_all(*_args):
    return controller.clear_all()
