from TheKeyMachine.tools.gimbal_fixer.controller import GimbalAnalyzer, convert_rotation_order


__all__ = [
    "convert_rotation_order",
    "bind_gimbal_fixer_toolbar_button",
    "close_gimbal_fixer_window",
    "show_gimbal_fixer_window",
    "is_gimbal_fixer_window_open",
    "toggle",
    "GimbalAnalyzer",
]


def _widgets():
    # Deferred: gimbal_fixer.widgets defines the popup window class, which
    # only needs to exist once the window is actually shown -- not just to
    # register this tool's toolbar button and callbacks.
    from TheKeyMachine.tools.gimbal_fixer import widgets

    return widgets


def bind_gimbal_fixer_toolbar_button(button):
    return _widgets().bind_gimbal_fixer_toolbar_button(button)


def close_gimbal_fixer_window():
    return _widgets().close_gimbal_fixer_window()


def is_gimbal_fixer_window_open():
    return _widgets().is_gimbal_fixer_window_open()


def show_gimbal_fixer_window(*args, **kwargs):
    return _widgets().show_gimbal_fixer_window(*args, **kwargs)


def toggle(checked=None, *_args):
    if isinstance(checked, bool):
        return show_gimbal_fixer_window() if checked else close_gimbal_fixer_window()
    return _widgets().gimbal_fixer_toolbar_toggle.toggle()
