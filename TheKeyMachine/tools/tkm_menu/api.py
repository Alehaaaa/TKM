def updates_available():
    from TheKeyMachine.mods import generalMod

    return bool(generalMod.config.get("INTERNET_CONNECTION", True))


def bug_reports_available():
    from TheKeyMachine.mods import generalMod

    return bool(generalMod.config.get("BUG_REPORT", True))


def show_menu(tool_id="TKM", *_args):
    from TheKeyMachine.mods import shelfMod
    return shelfMod.show_tool_menu_at_cursor(tool_id)


show_menu._tkm_non_tool_action = True


def create_logo_action(parent, clickable=True):
    from TheKeyMachine.tools.tkm_menu import widgets

    return widgets.LogoAction(parent, clickable=clickable)


def toggle_toolbar(*_args):
    from TheKeyMachine.core import toolbar
    return toolbar.toggle()


def add_shelf_button(*_args):
    from TheKeyMachine.mods import shelfMod
    return shelfMod.create_main_shelf_button()


def reload_toolbar(*_args, anchor_widget=None):
    from TheKeyMachine.tools import common as toolCommon
    from TheKeyMachine.tools.tkm_menu import controller

    # Reload is a system action, not tool work. Cancel delayed/active ETA UI
    # before showing a prompt that may remain open for an arbitrary duration.
    toolCommon.finish_active_progress()
    return controller.reload_toolbar_with_scene_prompt(anchor_widget=anchor_widget)


reload_toolbar._tkm_non_tool_action = True


def unload_toolbar(*_args):
    from TheKeyMachine.core import toolbar
    return toolbar.unload_current()


def uninstall(*_args):
    from TheKeyMachine.mods import uiMod
    return uiMod.uninstall()


def check_for_updates(*_args):
    from TheKeyMachine.mods import updater
    return updater.check_for_updates(force=True)


def set_start_with_maya(enabled, *_args):
    from TheKeyMachine.mods import uiMod
    return uiMod.install_userSetup(enabled)


def starts_with_maya():
    from TheKeyMachine.mods import uiMod
    return bool(uiMod.check_userSetup())


def set_tooltips_enabled(enabled, *_args):
    from TheKeyMachine.mods import settingsMod
    from TheKeyMachine.mods.tooltipsMod import QFlatTooltipManager

    enabled = bool(enabled)
    settingsMod.set_setting("show_tooltips", enabled)
    QFlatTooltipManager.enabled = enabled
    if not enabled:
        QFlatTooltipManager.hide()


def tooltips_enabled():
    from TheKeyMachine.mods import settingsMod
    return bool(settingsMod.get_setting("show_tooltips", True))


def dock_toolbar(*_args, **target):
    from TheKeyMachine.core import toolbar
    instance = toolbar.get_toolbar()
    if instance:
        return instance.dock_to_ui(**target)


def set_alignment(alignment_name, *_args):
    from TheKeyMachine.core import toolWidgets, toolbar
    instance = toolbar.get_toolbar()
    if instance:
        return toolWidgets.set_main_toolbar_icon_alignment(instance, alignment_name)


def open_url(url, *_args):
    from TheKeyMachine.mods import generalMod
    return generalMod.open_url(url)


def show_hotkeys(*_args):
    from TheKeyMachine.mods import hotkeysMod
    return hotkeysMod.show_hotkeys_window()


def show_version_history(*_args):
    from TheKeyMachine.tools.tkm_menu import widgets
    return widgets.show_version_history_dialog()


def show_about(*_args):
    from TheKeyMachine.tools.tkm_menu import widgets
    return widgets.show_about()


def show_donate(*_args):
    from TheKeyMachine.tools.tkm_menu import widgets
    return widgets.show_donate()


def show_bug_report(*_args):
    from TheKeyMachine.mods import reportMod
    return reportMod.bug_report_window()
