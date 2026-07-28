"""Custom Tools menu construction."""

from TheKeyMachine.core.Qt import QtGui
from TheKeyMachine.core import i18n
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
        i18n.tr("open_config_file", "Open config file"),
        callback=controller.open_config,
        description=i18n.tr("open_config_file_desc", "Open the Custom Tools configuration file."),
    )
    return False
