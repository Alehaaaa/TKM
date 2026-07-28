"""Background Runners menu construction."""

from TheKeyMachine.core.Qt import QtGui
from TheKeyMachine.core import backgroundRunners
from TheKeyMachine.data import icons
from TheKeyMachine.tools import common as toolCommon
from TheKeyMachine.tools.background_runners import controller


def build_menu(menu, source_widget=None):
    _ = source_widget
    from TheKeyMachine.core import toolbox, trigger

    from TheKeyMachine.core import i18n

    for runner_id, spec in backgroundRunners.get_runner_specs().items():
        command_id = spec.get("command_id", runner_id)
        # Route the click through the same registered command every hotkey,
        # shelf button, and Hotkeys-editor row for this runner already goes
        # through (see backgroundRunners.RUNNER_COMMAND_IDS), instead of
        # toggling the runner's state directly -- one dispatch path, one
        # place that decides what "run this" means. That same registered
        # tool is also this menu's only source for label/description text,
        # so a runner entry translates exactly like its Hotkeys-editor row
        # and shelf button do, via the package's own lang.json -- no
        # separate copy of the string lives in backgroundRunners.py's specs.
        tool = toolbox.get_tool(command_id) if trigger.has_command(command_id) else {}
        callback = tool.get("callback") if tool else None
        tooltip = tool.get("tooltip")
        label = tool.get("menu_label") or tool.get("label") or spec.get("label", runner_id)
        description = tool.get("description") or (tooltip if isinstance(tooltip, str) else spec.get("description") or "")
        action = menu.addAction(
            QtGui.QIcon(spec.get("icon") or ""),
            label,
            callback=callback,
            command_id=command_id,
            description=description,
            tooltip=tooltip,
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
        i18n.tr("turn_all_off", "Turn All Off"),
        callback=toolCommon.mark_non_tool_action(controller.turn_all_off),
        description=i18n.tr("turn_all_off_desc", "Disable every background runner."),
    )
    menu.addAction(
        QtGui.QIcon(icons.reload),
        i18n.tr("restore_runner_defaults", "Restore Defaults"),
        callback=toolCommon.mark_non_tool_action(controller.restore_defaults),
        description=i18n.tr("restore_runner_defaults_desc", "Restore the default background-runner states."),
    )
    return False
