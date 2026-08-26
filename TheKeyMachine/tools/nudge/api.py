from TheKeyMachine.tools.nudge import controller


def is_snap_collision_enabled():
    return controller.is_snap_collision_enabled()


def set_snap_collision_enabled(enabled=False, *_args, **_kwargs):
    return controller.set_snap_collision_enabled(enabled)


def _step(kwargs, default):
    try:
        return int(kwargs.pop("steps", default))
    except (TypeError, ValueError):
        return int(default)


def nudge_left(*_args, **kwargs):
    return controller.nudge_range(
        _step(kwargs, -1), tool_operation=kwargs.pop("tool_operation", None)
    )


def nudge_right(*_args, **kwargs):
    return controller.nudge_range(
        _step(kwargs, 1), tool_operation=kwargs.pop("tool_operation", None)
    )


def nudge_left_all_keys(*_args, **kwargs):
    return controller.nudge_all_keys(
        _step(kwargs, -1), tool_operation=kwargs.pop("tool_operation", None)
    )


def nudge_right_all_keys(*_args, **kwargs):
    return controller.nudge_all_keys(
        _step(kwargs, 1), tool_operation=kwargs.pop("tool_operation", None)
    )


def nudge_left_scene(*_args, **kwargs):
    return controller.nudge_scene(
        _step(kwargs, -1), tool_operation=kwargs.pop("tool_operation", None)
    )


def nudge_right_scene(*_args, **kwargs):
    return controller.nudge_scene(
        _step(kwargs, 1), tool_operation=kwargs.pop("tool_operation", None)
    )


def nudge_insert_inbetween(*_args, **kwargs):
    return controller.shift_inbetween(
        _step(kwargs, 1), tool_operation=kwargs.pop("tool_operation", None)
    )


def nudge_remove_inbetween(*_args, **kwargs):
    return controller.shift_inbetween(
        _step(kwargs, -1), tool_operation=kwargs.pop("tool_operation", None)
    )


def nudge_insert_inbetween_scene(*_args, **kwargs):
    return controller.shift_inbetween(
        _step(kwargs, 1),
        scene=True,
        tool_operation=kwargs.pop("tool_operation", None),
    )


def nudge_remove_inbetween_scene(*_args, **kwargs):
    return controller.shift_inbetween(
        _step(kwargs, -1),
        scene=True,
        tool_operation=kwargs.pop("tool_operation", None),
    )
