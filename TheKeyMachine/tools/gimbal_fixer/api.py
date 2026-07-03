from TheKeyMachine.tools.gimbal_fixer.controller import convert_rotation_order
from TheKeyMachine.tools.gimbal_fixer.customDialogs import (
    bind_gimbal_fixer_toolbar_button,
    close_gimbal_fixer_window,
    is_gimbal_fixer_window_open,
    show_gimbal_fixer_window,
    toggle_gimbal_fixer_window,
)


__all__ = [
    "convert_rotation_order",
    "bind_gimbal_fixer_toolbar_button",
    "close_gimbal_fixer_window",
    "gimbal_fixer_window",
    "is_gimbal_fixer_window_open",
    "toggle_gimbal_fixer_window",
]


def gimbal_fixer_window(*_args):
    return show_gimbal_fixer_window()
