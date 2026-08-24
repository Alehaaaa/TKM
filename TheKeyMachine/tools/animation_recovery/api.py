"""Public Animation Recovery UI and lifecycle entry points."""

from functools import partial

from TheKeyMachine.core.Qt import QtCore
from TheKeyMachine.data import icons
from TheKeyMachine.tools.animation_recovery import controller
from TheKeyMachine.ui.widgets import customDialogs
from TheKeyMachine.ui.widgets import util as wutil


def _enable_prompt(anchor_widget):
    enable_button = customDialogs.QFlatDialogButton(
        "Enable",
        positive=True,
        icon=icons.apply,
    )
    not_now_button = customDialogs.QFlatDialogButton(
        "Not Now",
        positive=False,
        icon=icons.cancel,
    )
    return customDialogs.QFlatTooltipConfirm.question(
        anchor_widget,
        title="Enable Animation Recovery?",
        message=(
            "Automatically keep scene-scoped animation snapshots after animation "
            "and hierarchy changes. Recovery remains enabled on future Maya starts."
        ),
        buttons=[enable_button, not_now_button],
        icon=icons.animation_recovery,
        highlight=enable_button,
    )


def offer_enable(anchor_widget=None, startup=False):
    if controller.is_enabled():
        return True
    anchor_widget = anchor_widget if wutil.is_valid_widget(anchor_widget) else wutil.get_maya_qt()
    clicked = _enable_prompt(anchor_widget)
    if startup:
        controller.mark_startup_prompted()
    if clicked and clicked.get("positive"):
        controller.set_enabled(True)
        return True
    return False


def _offer_startup_enable(button):
    if not wutil.is_valid_widget(button):
        return
    if controller.is_enabled() or controller.was_startup_prompted():
        return
    offer_enable(button, startup=True)


def bind_toolbar_button(button):
    if wutil.is_valid_widget(button):
        QtCore.QTimer.singleShot(650, partial(_offer_startup_enable, button))
    return button


def show(*_args, **kwargs):
    anchor_widget = kwargs.get("anchor_widget")
    if not controller.is_enabled() and not offer_enable(anchor_widget):
        return None
    from TheKeyMachine.tools.animation_recovery import widgets

    return widgets.show_dialog()


def restore(path, tool_operation=None):
    return controller.restore_recovery(path, tool_operation=tool_operation)


def set_enabled(enabled):
    return controller.set_enabled(enabled)


def is_enabled():
    return controller.is_enabled()


def cleanup():
    try:
        from TheKeyMachine.tools.animation_recovery import widgets

        widgets.close_dialog()
    except Exception:
        pass
    controller.shutdown()
