"""Checkable toggle to pause the Maya viewport refresh for performance."""

from TheKeyMachine.core import i18n
from TheKeyMachine.maya import viewport as maya_viewport
from TheKeyMachine.tools.background_runners import api as background_runner_api
from TheKeyMachine.tools.background_runners import service as background_runner_service


def is_viewport_paused():
    """Whether the viewport refresh toggle is currently checked."""
    return maya_viewport.is_paused()


def set_viewport_paused(paused=False, *_args):
    """Pause or resume the viewport refresh to improve performance."""
    return maya_viewport.set_paused(paused)


def is_auto_pause_enabled():
    """Whether automatic viewport pause is enabled."""
    return maya_viewport.is_auto_pause_enabled()


def set_auto_pause_enabled(enabled=False, *_args):
    """Automatically pause viewport refresh while letting key edits update."""
    return background_runner_api.set_auto_pause_viewport(enabled)


def auto_pause_changed_signal():
    return background_runner_service.changed_signal_for_runner(
        background_runner_service.AUTO_PAUSE_VIEWPORT_ID
    )


def build_pause_viewport_context_menu(menu, source_widget=None):
    _ = source_widget
    from TheKeyMachine.core.Qt import QtGui  # type: ignore
    from TheKeyMachine.data import icons
    from TheKeyMachine.tools import common as toolCommon

    action = menu.addAction(
        QtGui.QIcon(icons.auto_pause_viewport),
        i18n.tr_text("Auto Pause Viewport"),
        callback=set_auto_pause_enabled,
        command_id="auto_pause_viewport",
        description=i18n.tr_text("Automatically pause viewport refresh and briefly refresh after animation key changes."),
        tooltip=i18n.tr_text("Automatically pause viewport refresh and briefly refresh after animation key changes."),
        open=True,
    )
    toolCommon.connect_checkable_action(
        action,
        getter=is_auto_pause_enabled,
        signal=auto_pause_changed_signal(),
    )
    return False
