from TheKeyMachine.tools.nudge import controller


def nudge_left(*_args):
    return controller.nudge_range(-1)


def nudge_right(*_args):
    return controller.nudge_range(1)


def nudge_left_all_keys(*_args):
    return controller.nudge_all_keys(-1)


def nudge_right_all_keys(*_args):
    return controller.nudge_all_keys(1)


def nudge_left_scene(*_args):
    return controller.nudge_scene(-1)


def nudge_right_scene(*_args):
    return controller.nudge_scene(1)


def nudge_insert_inbetween(*_args):
    return controller.shift_inbetween(1)


def nudge_remove_inbetween(*_args):
    return controller.shift_inbetween(-1)


def nudge_insert_inbetween_scene(*_args):
    return controller.shift_inbetween(1, scene=True)


def nudge_remove_inbetween_scene(*_args):
    return controller.shift_inbetween(-1, scene=True)
