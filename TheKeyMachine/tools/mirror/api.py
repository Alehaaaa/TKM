from TheKeyMachine.tools.mirror import controller


def select_opposite(*args):
    return controller.select_opposite(*args)


def add_select_opposite(*args):
    return controller.add_select_opposite(*args)


def copy_opposite(*args):
    return controller.copy_opposite(*args)


def mirror(*args):
    return controller.mirror(*args)


def mirror_to_right(*args):
    return controller.mirror_to_right(*args)


def mirror_to_left(*args):
    return controller.mirror_to_left(*args)


def mirror_all_keys(*args):
    return controller.mirror_all_keys(*args)


def add_invert_exception(*args):
    return controller.add_invert_exception(*args)


def add_keep_exception(*args):
    return controller.add_keep_exception(*args)


def remove_exception(*args):
    return controller.remove_exception(*args)
