"""Background Runners menu construction."""

from functools import partial

from TheKeyMachine.core.Qt import QtGui
from TheKeyMachine.core import backgroundRunners
from TheKeyMachine.tools import common as toolCommon


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
            setter=partial(backgroundRunners.set_runner_enabled, runner_id),
            signal=spec.get("changed_signal"),
        )
    return False
