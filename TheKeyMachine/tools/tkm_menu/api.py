def updates_available():
    from TheKeyMachine.core import application

    return bool(application.config.get("INTERNET_CONNECTION", True))


def bug_reports_available():
    from TheKeyMachine.core import application

    return bool(application.config.get("BUG_REPORT", True))


_DEBUG_MODULE_NAME = "TheKeyMachine.core.debug"


def _load_debug_module(reload_module=False):
    import importlib

    debug_module = importlib.import_module(_DEBUG_MODULE_NAME)
    if reload_module:
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
    from TheKeyMachine.maya import shelf
    return shelf.show_tool_menu_at_cursor(tool_id)


show_menu._tkm_non_tool_action = True


def create_logo_action(parent, clickable=True):
    from TheKeyMachine.tools.tkm_menu import widgets

    return widgets.LogoAction(parent, clickable=clickable)


def toggle_toolbar(*_args):
    from TheKeyMachine.ui.widgets import toolbar
    return toolbar.toggle()


def add_shelf_button(*_args):
    from TheKeyMachine.maya import shelf
    return shelf.create_main_shelf_button()


def reload_toolbar(*_args, anchor_widget=None):
    from TheKeyMachine.tools import common as toolCommon
    from TheKeyMachine.tools.tkm_menu import controller

    # Reload is a system action, not tool work. Cancel delayed/active ETA UI
    # before showing a prompt that may remain open for an arbitrary duration.
    toolCommon.finish_active_progress()
    return controller.reload_toolbar_with_scene_prompt(anchor_widget=anchor_widget)


reload_toolbar._tkm_non_tool_action = True


def unload_toolbar(*_args):
    from TheKeyMachine.ui.widgets import toolbar
    from TheKeyMachine.core import runtime

    toolbar_instance = toolbar.get_toolbar()
    if toolbar_instance:
        return toolbar_instance.unload()
    return runtime.cleanup_for_reload(delete_workspace=True, process_events=True)


def uninstall(*_args):
    from TheKeyMachine.core import application as general
    return general.uninstall()


def check_for_updates(*_args, **kwargs):
    from TheKeyMachine.tools.update import controller as updates
    return updates.check_for_updates(
        force=True,
        tool_operation=kwargs.pop("tool_operation", None),
    )


def install_update(latest_version, *_args, **kwargs):
    from TheKeyMachine.tools.update import controller as updates
    return updates.install_update(
        latest_version,
        tool_operation=kwargs.pop("tool_operation", None),
    )


def set_start_with_maya(enabled, *_args):
    from TheKeyMachine.core import application as general
    return general.install_userSetup(enabled)


def starts_with_maya():
    from TheKeyMachine.core import application as general
    return bool(general.check_userSetup())


def set_tooltips_enabled(enabled, *_args):
    from TheKeyMachine.core import settings
    from TheKeyMachine.ui.tooltips import QFlatTooltipManager

    enabled = bool(enabled)
    settings.set_setting("show_tooltips", enabled)
    QFlatTooltipManager.enabled = enabled
    if not enabled:
        QFlatTooltipManager.hide()


def tooltips_enabled():
    from TheKeyMachine.core import settings
    return bool(settings.get_setting("show_tooltips", True))


def dock_toolbar(*_args, **target):
    from TheKeyMachine.ui.widgets import toolbar
    instance = toolbar.get_toolbar()
    if instance:
        return instance.dock_to_ui(**target)


def _docking_position():
    from TheKeyMachine.ui.widgets import toolbar
    from TheKeyMachine.core import settings

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
    from TheKeyMachine.core import i18n
    from TheKeyMachine.ui.widgets import toolbar

    return [
        {
            "label": i18n.tr("dock_orient_{}".format(value), label),
            "value": value,
            "description": i18n.tr(
                "dock_orient_{}_desc".format(value),
                "Place the toolbar on the {} side.".format(value),
            ),
        }
        for value, label in toolbar.DOCKING_ORIENTATIONS.items()
    ]


def dock_layout_choices():
    from TheKeyMachine.core import i18n
    from TheKeyMachine.ui.widgets import toolbar

    return [
        {
            "label": i18n.tr("dock_area_{}".format(value), label),
            "value": value,
            "description": i18n.tr(
                "dock_area_{}_desc".format(value),
                "Dock the toolbar in {}.".format(label),
            ),
        }
        for value, label in toolbar.DOCKING_AREAS.items()
    ]


def set_alignment(alignment_name, *_args):
    from TheKeyMachine.core import settings
    from TheKeyMachine.ui import toolbar_modes
    alignment_name = toolbar_modes.normalize(alignment_name)
    settings.set_setting(toolbar_modes.MAIN_ALIGNMENT_SETTING, alignment_name)

    from TheKeyMachine.ui.widgets import toolbar
    from TheKeyMachine.ui.widgets import toolbar_widgets
    instance = toolbar.get_toolbar()
    if instance:
        return toolbar_widgets.set_main_toolbar_icon_alignment(instance, alignment_name)


def get_alignment(*_args):
    from TheKeyMachine.core import settings
    from TheKeyMachine.ui import toolbar_modes
    return toolbar_modes.normalize(
        settings.get_setting(
            toolbar_modes.MAIN_ALIGNMENT_SETTING,
            toolbar_modes.DEFAULT_ALIGNMENT,
        )
    )


def alignment_choices():
    from TheKeyMachine.ui import toolbar_modes

    return [
        {
            "label": label,
            "value": value,
            "description": description,
        }
        for value, label, description in toolbar_modes.translated_options()
    ]



def open_url(url, *_args):
    from TheKeyMachine.core import application
    return application.open_url(url)


def show_hotkeys(*_args):
    from TheKeyMachine.tools.hotkeys import controller as hotkeys
    return hotkeys.show_hotkeys_window()


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
    from TheKeyMachine.tools.bug_report import controller as bug_reporting
    return bug_reporting.bug_report_window()


def populate_languages_menu(menu, *_args):
    """Populate (or repopulate) the Languages submenu in place.

    Used as the ``dynamic_menu`` builder for the nested "System" submenu in
    the TKM logo's mega-menu; ``toolbar_menus.build_main_system_menu`` reuses the
    same ``toolbar_menus.populate_languages_menu`` implementation for the
    standalone System button, so the two surfaces can never drift apart.
    """
    from TheKeyMachine.ui.widgets import toolbar_menus
    return toolbar_menus.populate_languages_menu(menu)
