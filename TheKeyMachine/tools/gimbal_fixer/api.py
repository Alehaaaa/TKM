from TheKeyMachine.tools.gimbal_fixer.controller import GimbalAnalyzer, convert_rotation_order
from TheKeyMachine.tools.gimbal_fixer.widgets import (
    bind_gimbal_fixer_toolbar_button,
    close_gimbal_fixer_window,
    is_gimbal_fixer_window_open,
    show_gimbal_fixer_window,
    gimbal_fixer_toolbar_toggle,
)


__all__ = [
    "convert_rotation_order",
    "bind_gimbal_fixer_toolbar_button",
    "close_gimbal_fixer_window",
    "show_gimbal_fixer_window",
    "is_gimbal_fixer_window_open",
    "gimbal_fixer_toolbar_toggle",
    "toggle",
    "GimbalAnalyzer",
]


def toggle(checked=None, *_args):
    if isinstance(checked, bool):
        return show_gimbal_fixer_window() if checked else close_gimbal_fixer_window()
    return gimbal_fixer_toolbar_toggle.toggle()
