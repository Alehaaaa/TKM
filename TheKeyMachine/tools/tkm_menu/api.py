def updates_available():
    from TheKeyMachine.mods import generalMod

    return bool(generalMod.config.get("INTERNET_CONNECTION", True))


def bug_reports_available():
    from TheKeyMachine.mods import generalMod

    return bool(generalMod.config.get("BUG_REPORT", True))


_DEBUG_MODULE_NAME = "TheKeyMachine.core.debug"


def _load_debug_module(reload_module=False):
    """Load the canonical debug module, replacing stale pre-move aliases."""
    import importlib
    import sys

    debug_module = sys.modules.get(_DEBUG_MODULE_NAME)
    if debug_module is not None and (
        getattr(debug_module, "__name__", None) != _DEBUG_MODULE_NAME
        or getattr(debug_module, "__spec__", None) is None
    ):
        sys.modules.pop(_DEBUG_MODULE_NAME, None)
        debug_module = None

    if debug_module is None:
        debug_module = importlib.import_module(_DEBUG_MODULE_NAME)
    elif reload_module:
        debug_module = importlib.reload(debug_module)
    return debug_module


def tool_debug_enabled():
    try:
        return _load_debug_module().is_enabled()
    except Exception:
        return False


def rebuild_debug_menu(menu):
    """Reload developer actions and repopulate the submenu before it opens."""
    try:
        return _load_debug_module(reload_module=True).populate_menu(menu)
    except Exception as error:
        menu.clear()
        action = menu.addAction("Debug menu unavailable")
        action.setEnabled(False)
        try:
            from maya import cmds

            cmds.warning("TheKeyMachine debug menu could not reload: {}".format(error))
        except Exception:
            pass
        return menu


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
    from TheKeyMachine.mods import generalMod as general
    return general.uninstall()


def check_for_updates(*_args):
    from TheKeyMachine.mods import updater
    return updater.check_for_updates(force=True)


def set_start_with_maya(enabled, *_args):
    from TheKeyMachine.mods import generalMod as general
    return general.install_userSetup(enabled)


def starts_with_maya():
    from TheKeyMachine.mods import generalMod as general
    return bool(general.check_userSetup())


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


def _docking_position():
    from TheKeyMachine.core import toolbar
    from TheKeyMachine.mods import settingsMod as settings

    instance = toolbar.get_toolbar()
    position = (
        instance.docking_position
        if instance
        else settings.get_setting("docking_position", ["TimeSlider", "top"])
    )
    position = list(position or ["TimeSlider", "top"])
    valid_areas = set(toolbar.DOCKING_AREAS)
    valid_orientations = set(toolbar.DOCKING_ORIENTATIONS)
    if len(position) != 2:
        return ["TimeSlider", "top"]
    if position[0] not in valid_areas:
        position[0] = "TimeSlider"
    if position[1] not in valid_orientations:
        position[1] = "top"
    return position


def get_dock_orientation(*_args):
    return _docking_position()[1]


def set_dock_orientation(orientation, *_args):
    return dock_toolbar(orient=orientation)


def get_dock_layout(*_args):
    return _docking_position()[0]


def set_dock_layout(layout, *_args):
    return dock_toolbar(layout=layout)


def dock_orientation_choices():
    from TheKeyMachine.core import toolbar

    return [
        {
            "label": label,
            "value": value,
            "description": "Place the toolbar on the {} side.".format(value),
        }
        for value, label in toolbar.DOCKING_ORIENTATIONS.items()
    ]


def dock_layout_choices():
    from TheKeyMachine.core import toolbar

    return [
        {
            "label": label,
            "value": value,
            "description": "Dock the toolbar in {}.".format(label),
        }
        for value, label in toolbar.DOCKING_AREAS.items()
    ]


def set_alignment(alignment_name, *_args):
    from TheKeyMachine.mods import settingsMod as settings
    settings.set_setting("toolbar_icon_alignment", alignment_name)

    from TheKeyMachine.core import toolWidgets, toolbar
    instance = toolbar.get_toolbar()
    if instance:
        return toolWidgets.set_main_toolbar_icon_alignment(instance, alignment_name)


def get_alignment(*_args):
    from TheKeyMachine.mods import settingsMod as settings
    return settings.get_setting("toolbar_icon_alignment", "Center")



def open_url(url, *_args):
    from TheKeyMachine.mods import generalMod
    return generalMod.open_url(url)


def show_hotkeys(*_args):
    from TheKeyMachine.mods import hotkeysMod
    return hotkeysMod.show_hotkeys_window()


def show_workspaces(*_args):
    from TheKeyMachine.tools.workspaces import api as workspacesApi
    return workspacesApi.show_workspaces_window()


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
