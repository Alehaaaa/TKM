"""Utility functions for consistent toolbar button binding.

This module defines a helper that abstracts the pattern used in the various
tool API modules for binding a toolbar button to a `ToolbarWindowToggle`
instance and optionally attaching a context menu.
"""

from typing import Callable, Any

from TheKeyMachine.tools import common as toolCommon


def bind_toolbar_button_common(
    toggle_obj: Any,
    button: Any,
    context_attr: str,
    menu_builder: Callable[[Any], Any],
) -> None:
    """Bind a toolbar button to a toggle object.

    The function mirrors the logic previously duplicated in each API module:
    * If the button provides a ``connect_window_toggle`` method, we use it.
    * Otherwise we fall back to ``toolCommon.bind_toolbar_button_context_menu``.

    Parameters
    ----------
    toggle_obj: Any
        The ``ToolbarWindowToggle`` instance controlling the window state.
    button: Any
        The toolbar button widget.
    context_attr: str
        Attribute name used to store the generated context menu slot on the button.
    menu_builder: Callable[[Any], Any]
        Factory returning a ``QMenu`` (or compatible widget) when called with the
        menu's parent widget.
    """
    connect_window_toggle = getattr(button, "connect_window_toggle", None)
    if callable(connect_window_toggle):
        button.connect_window_toggle(
            toggle_obj,
            context_attr=context_attr,
            menu_factory=menu_builder,
        )
    else:
        toolCommon.bind_toolbar_button_context_menu(
            toggle_obj,
            button,
            context_attr,
            menu_builder,
        )
