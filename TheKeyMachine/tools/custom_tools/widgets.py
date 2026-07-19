"""Custom Tools menu construction."""

from TheKeyMachine.core.Qt import QtGui
from TheKeyMachine.data import icons
from TheKeyMachine.tools.custom_tools import controller


def build_menu(menu, source_widget=None):
    _ = source_widget
    menu.clear()
    for entry in controller.entries(notify=True):
        if entry.get("type") != "entry":
            continue
        menu.addAction(
            QtGui.QIcon(entry.get("icon") or ""),
            entry.get("label", ""),
            callback=entry.get("callback"),
            description=entry.get("description", ""),
            tooltip=entry.get("tooltip"),
            tooltip_enabled=True,
            command_id=entry.get("id"),
        )

    menu.addSeparator()
    menu.addAction(
        QtGui.QIcon(icons.settings),
        "Open config file",
        callback=controller.open_config,
        description="Open the Custom Tools configuration file.",
    )
    return False
