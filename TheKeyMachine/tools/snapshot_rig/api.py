from TheKeyMachine.tools.snapshot_rig import controller


def snapshot_rig(*args, **kwargs):
    return controller.snapshot_rig(*args, **kwargs)


def snapshot_default(*args):
    return controller.snapshot_default(*args)


def snapshot_opposite(*args):
    return controller.snapshot_opposite(*args)


def snapshot_mirror(*args):
    return controller.snapshot_mirror(*args)


def remove_selected_opposites(*args, **kwargs):
    return controller.remove_selected_opposites(*args, **kwargs)


def clear_all_opposites(*args, **kwargs):
    return controller.clear_all_opposites(*args, **kwargs)


def remove_selected_mirrors(*args, **kwargs):
    return controller.remove_selected_mirrors(*args, **kwargs)


def clear_all_mirrors(*args, **kwargs):
    return controller.clear_all_mirrors(*args, **kwargs)
