"""Background Runners menu construction."""

from functools import partial

from TheKeyMachine.core.Qt import QtGui
from TheKeyMachine.core import backgroundRunners
from TheKeyMachine.data import icons
from TheKeyMachine.tools import common as toolCommon
from TheKeyMachine.tools.background_runners import controller


def _toggle_runner_action(action, runner_id, *_args):
    """Toggle authoritative runner state, then mirror it on the menu action."""
    enabled = backgroundRunners.toggle_runner_enabled(runner_id)
    toolCommon.set_checked_safely(action, enabled)


def build_menu(menu, source_widget=None):
    _ = source_widget
    for runner_id, spec in backgroundRunners.get_runner_specs().items():
        action = menu.addAction(
            QtGui.QIcon(spec.get("icon") or ""),
            spec.get("label", runner_id),
            description=spec.get("description") or "",
            open=True,
        )
        toolCommon.connect_checkable_action(
            action,
            getter=spec.get("get_enabled"),
            signal=spec.get("changed_signal"),
        )
        action.triggered.connect(
            partial(_toggle_runner_action, action, runner_id)
        )

    menu.addSeparator()
    menu.addAction(
        QtGui.QIcon(icons.cancel),
        "Turn All Off",
        callback=toolCommon.mark_non_tool_action(controller.turn_all_off),
        description="Disable every background runner.",
    )
    menu.addAction(
        QtGui.QIcon(icons.reload),
        "Restore Defaults",
        callback=toolCommon.mark_non_tool_action(controller.restore_defaults),
        description="Restore the default background-runner states.",
    )
    return False
