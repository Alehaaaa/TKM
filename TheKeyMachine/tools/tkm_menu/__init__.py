from functools import partial

from TheKeyMachine.core.toolbox import ToolObject, load_tooltips
from TheKeyMachine.tools.tkm_menu import api


TOOLTIPS = load_tooltips(__file__)


class TkmMenuToolObject(ToolObject):
    ORDER = 10
    TOOLS = {
        "TKM": {
            "type": "menu", "label": "TheKeyMachine", "icon": "tkm_main", "tooltip": TOOLTIPS["menu"],
            "callback": api.show_menu,
            "menu": {
                "label": "TheKeyMachine", "items": [
                    {"type": "widget", "factory": api.create_logo_action},
                    {"type": "menu", "label": "Preferences", "icon": "settings", "items": [
                        "toolbar_add_shelf_button", {"type": "check", "command": "start_with_maya"},
                        {"type": "check", "command": "show_tooltips"}, "separator",
                        {"type": "section", "label": "Alignment"},
                        {"type": "choice", "get_value": api.get_alignment, "set_value": api.set_alignment, "items": [
                            {"label": "Align Left", "value": "Left", "description": "Align toolbar icons to the left."},
                            {"label": "Align Center", "value": "Center", "description": "Align toolbar icons to the center."},
                            {"label": "Align Right", "value": "Right", "description": "Align toolbar icons to the right."},
                        ]},
                    ]},
                    "hotkeys_window",
                    {"type": "menu", "label": "Dock", "icon": "dock", "items": [
                        {"label": "Top", "callback": partial(api.dock_toolbar, orient="top")},
                        {"label": "Bottom", "callback": partial(api.dock_toolbar, orient="bottom")},
                        "separator",
                        {"label": "Time Slider", "callback": partial(api.dock_toolbar, layout="TimeSlider")},
                        {"label": "Range Slider", "callback": partial(api.dock_toolbar, layout="RangeSlider")},
                    ]},
                    {"type": "menu", "label": "System", "icon": "system", "items": [
                        "toolbar_reload", "toolbar_unload", "toolbar_uninstall",
                    ]},
                    "separator",
                    {"type": "menu", "label": "Help", "icon": "help", "items": [
                        "bug_report_window", "separator",
                        {"label": "Documentation", "icon": "help", "callback": partial(api.open_url, "https://thekeymachine.gitbook.io/base")},
                        {"label": "Discord", "icon": "discord", "callback": partial(api.open_url, "https://discord.gg/G2J5yyjz")},
                        {"label": "YouTube", "icon": "youtube", "callback": partial(api.open_url, "https://www.youtube.com/@TheKeyMachineAnimationTools")},
                    ]},
                    "donate_window", "check_for_updates", "about_window",
                ]
            },
        },
        "toolbar_toggle": {"type": "tool", "label": "Toggle Toolbar", "icon": "tkm_main", "callback": api.toggle_toolbar, "tooltip": TOOLTIPS["toggle"]},
        "toolbar_add_shelf_button": {"type": "tool", "label": "Add Toggle Button To Shelf", "icon": "tkm_main", "callback": api.add_shelf_button, "tooltip": TOOLTIPS["shelf"]},
        "toolbar_reload": {"type": "tool", "label": "Reload", "icon": "reload", "callback": api.reload_toolbar, "tooltip": TOOLTIPS["reload"]},
        "toolbar_unload": {"type": "tool", "label": "Unload", "icon": "close", "callback": api.unload_toolbar, "tooltip": TOOLTIPS["unload"]},
        "toolbar_uninstall": {"type": "tool", "label": "Uninstall", "icon": "remove", "callback": api.uninstall, "tooltip": TOOLTIPS["uninstall"]},
        "check_for_updates": {"type": "tool", "label": "Check for Updates", "icon": "check_updates", "callback": api.check_for_updates, "available": api.updates_available, "tooltip": TOOLTIPS["updates"]},
        "main_preferences_menu": {"type": "menu", "label": "Preferences", "icon": "settings", "callback": partial(api.show_menu, "main_preferences_menu"), "tooltip": TOOLTIPS["preferences"]},
        "start_with_maya": {"type": "check", "label": "Start with Maya", "callback": api.set_start_with_maya, "get_checked": api.starts_with_maya, "set_checked": api.set_start_with_maya, "tooltip": TOOLTIPS["startup"]},
        "show_tooltips": {"type": "check", "label": "Show Tooltips", "callback": api.set_tooltips_enabled, "get_checked": api.tooltips_enabled, "set_checked": api.set_tooltips_enabled, "tooltip": TOOLTIPS["tooltips"]},
        "main_dock_menu": {"type": "menu", "label": "Dock", "icon": "dock", "callback": partial(api.show_menu, "main_dock_menu"), "tooltip": TOOLTIPS["dock"]},
        "main_system_menu": {"type": "menu", "label": "System", "icon": "system", "callback": partial(api.show_menu, "main_system_menu"), "tooltip": TOOLTIPS["system"]},
        "help_menu": {"type": "menu", "label": "Help", "icon": "help", "callback": partial(api.show_menu, "help_menu"), "tooltip": TOOLTIPS["help"]},
        "hotkeys_window": {"type": "tool", "label": "Hotkeys", "icon": "hotkeys", "callback": api.show_hotkeys, "tooltip": TOOLTIPS["hotkeys"]},
        "version_history_window": {"type": "tool", "label": "Version History", "icon": "about", "callback": api.show_version_history, "tooltip": TOOLTIPS["history"]},
        "about_window": {"type": "tool", "label": "About", "icon": "about", "callback": api.show_about, "tooltip": TOOLTIPS["about"]},
        "donate_window": {"type": "tool", "label": "Donate", "icon": "donate", "callback": api.show_donate, "tooltip": TOOLTIPS["donate"]},
        "bug_report_window": {"type": "tool", "label": "Bug Report", "icon": "bug", "callback": api.show_bug_report, "available": api.bug_reports_available, "tooltip": TOOLTIPS["bug_report"]},
    }
    SECTION = {
            "id": "system",
            "label": "TKM Menu", "hiddeable": False,
            "items": [
                {"id": "TKM"},
                *({"id": tool_id} for tool_id in (
                    "main_preferences_menu", "main_dock_menu", "main_system_menu", "help_menu",
                    "toolbar_toggle", "toolbar_add_shelf_button", "toolbar_reload", "toolbar_unload",
                    "toolbar_uninstall", "check_for_updates", "hotkeys_window", "version_history_window",
                    "about_window", "donate_window", "bug_report_window",
                )),
            ],
        }

