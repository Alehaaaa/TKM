"""Background Runners menu construction."""

from TheKeyMachine.core.Qt import QtGui
from TheKeyMachine.core import backgroundRunners
from TheKeyMachine.data import icons
from TheKeyMachine.tools import common as toolCommon
from TheKeyMachine.tools.background_runners import controller


def build_menu(menu, source_widget=None):
    _ = source_widget
    from TheKeyMachine.core import toolbox, trigger

    for runner_id, spec in backgroundRunners.get_runner_specs().items():
        command_id = spec.get("command_id", runner_id)
        # Route the click through the same registered command every hotkey,
        # shelf button, and Hotkeys-editor row for this runner already goes
        # through (see backgroundRunners.RUNNER_COMMAND_IDS), instead of
        # toggling the runner's state directly -- one dispatch path, one
        # place that decides what "run this" means.
        callback = toolbox.get_tool(command_id).get("callback") if trigger.has_command(command_id) else None
        action = menu.addAction(
            QtGui.QIcon(spec.get("icon") or ""),
            spec.get("label", runner_id),
            callback=callback,
            command_id=command_id,
            description=spec.get("description") or "",
            open=True,
        )
        toolCommon.connect_checkable_action(
            action,
            getter=spec.get("get_enabled"),
            signal=spec.get("changed_signal"),
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
