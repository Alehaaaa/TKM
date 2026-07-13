from functools import partial

from TheKeyMachine.Qt import QtCore  # type: ignore

from TheKeyMachine.data import icons
import TheKeyMachine.mods.keyToolsMod as keyTools
import TheKeyMachine.mods.helperMod as helper
import TheKeyMachine.mods.barMod as bar
import TheKeyMachine.mods.generalMod as general
import TheKeyMachine.mods.settingsMod as settings
import TheKeyMachine.mods.uiMod as ui
import TheKeyMachine.core.trigger as trigger
import TheKeyMachine.core.toolMenus as toolMenus
import TheKeyMachine.tools.attribute_switcher.api as attributeSwitcherApi
import TheKeyMachine.tools.graph_toolbar.api as graphToolbarApi
import TheKeyMachine.tools.isolate_bookmarks.api as isolateBookmarksApi
import TheKeyMachine.tools.gimbal_fixer.api as gimbalFixerApi
import TheKeyMachine.tools.orbit.api as orbitApi
import TheKeyMachine.tools.selection_sets.api as selectionSetsApi
import TheKeyMachine.tools.temp_pivot.api as tempPivotApi
from TheKeyMachine.tools import colors as toolColors

"""
TheKeyMachine Toolbox
====================
Centralized definitions for all tools to ensure consistent naming, 
icons, callbacks, and documentation across different UI contexts 
(Main Toolbar, Custom Graph, Context Menus).
"""


def _tangent_shortcuts(tool_id, tangent_type, tangent_label, *, maya_default=True, all_keys_callback=None):
    def _set_tangent(handle_mode="both", key_scope="selection"):
        if tangent_type == "bouncy":
            return keyTools.bouncy_tangets(handle_mode=handle_mode, key_scope=key_scope)
        return bar.setTangent(tangent_type, handle_mode=handle_mode, key_scope=key_scope)

    shortcuts = []
    if maya_default:
        shortcuts.append(
            {
                "id": tool_id,
                "label": "Set Maya Default Tangent",
                "keys": [QtCore.Qt.Key_Control],
                "callback": lambda t=tangent_type: bar.set_maya_default_tangent(t),
                "tooltip": "Use {} for newly created keys.".format(tangent_label),
            }
        )

    if tangent_type != "step":
        shortcuts.extend(
            [
                {
                    "id": tool_id,
                    "label": "{} Both Ends".format(tangent_label),
                    "keys": [QtCore.Qt.Key_Alt, QtCore.Qt.Key_Shift],
                    "callback": lambda: _set_tangent("both", "selection"),
                    "tooltip": "Set {} on the current selection.".format(tangent_label.lower()),
                },
                {
                    "id": tool_id,
                    "label": "{} First Key".format(tangent_label),
                    "keys": [QtCore.Qt.Key_Shift],
                    "callback": lambda: _set_tangent("both", "first"),
                    "tooltip": "Set {} on the first key.".format(tangent_label.lower()),
                },
                {
                    "id": tool_id,
                    "label": "{} In".format(tangent_label),
                    "keys": [QtCore.Qt.Key_Control, QtCore.Qt.Key_Shift],
                    "callback": lambda: _set_tangent("in", "selection"),
                    "tooltip": "Set the in {} on the current selection.".format(tangent_label.lower()),
                },
                {
                    "id": tool_id,
                    "label": "{} Last Key".format(tangent_label),
                    "keys": [QtCore.Qt.Key_Alt],
                    "callback": lambda: _set_tangent("both", "last"),
                    "tooltip": "Set {} on the last key.".format(tangent_label.lower()),
                },
                {
                    "id": tool_id,
                    "label": "{} Out".format(tangent_label),
                    "keys": [QtCore.Qt.Key_Control, QtCore.Qt.Key_Alt],
                    "callback": lambda: _set_tangent("out", "selection"),
                    "tooltip": "Set the out {} on the current selection.".format(tangent_label.lower()),
                },
            ]
        )

    shortcuts.append(
        {
            "id": tool_id,
            "label": "{} All Keys".format(tangent_label),
            "keys": [QtCore.Qt.Key_Control, QtCore.Qt.Key_Shift, QtCore.Qt.Key_Alt],
            "callback": all_keys_callback or (lambda: _set_tangent("both", "all")),
            "tooltip": "Set {} on all keys.".format(tangent_label.lower()),
        }
    )
    return shortcuts


def _tool_menu_builder(builder_name, **pdefault_kwargs):
    def _build(menu, source_widget=None):

        builder = getattr(toolMenus, builder_name)
        return builder(menu, source_widget=source_widget, **pdefault_kwargs)

    return _build


def _toolbar_controller_enabled(controller_attr):
    try:
        from TheKeyMachine.core.toolbar import get_toolbar
    except Exception:
        return False
    toolbar = get_toolbar()
    controller = getattr(toolbar, controller_attr, None) if toolbar else None
    is_enabled = getattr(controller, "is_enabled", None)
    return bool(is_enabled()) if callable(is_enabled) else False


def _set_animation_offset_enabled(enabled):
    try:
        from TheKeyMachine.core.toolbar import get_toolbar
    except Exception:
        return None
    toolbar = get_toolbar()
    if toolbar:
        return toolbar.toggleAnimOffsetButton(bool(enabled))
    return None


def _set_micro_move_enabled(enabled):
    try:
        from TheKeyMachine.core.toolbar import get_toolbar
    except Exception:
        return None
    toolbar = get_toolbar()
    if toolbar:
        return toolbar.toggle_micro_move_button(bool(enabled))
    return None


def _set_orbit_window_open(enabled):
    return orbitApi.orbit_window(reuse_existing=True) if enabled else orbitApi.close_orbit_window()


def _set_attribute_switcher_window_open(enabled):
    return attributeSwitcherApi.attribute_switcher_window(reuse_existing=True, popup=False) if enabled else attributeSwitcherApi.close_attribute_switcher_window()


def _set_gimbal_fixer_window_open(enabled):
    return gimbalFixerApi.gimbal_fixer_window() if enabled else gimbalFixerApi.close_gimbal_fixer_window()


def _set_selection_sets_window_open(enabled):
    return selectionSetsApi.selection_sets_window(reuse_existing=True) if enabled else selectionSetsApi.close_selection_sets_window()


def _get_overshoot_sliders_enabled():
    return bool(settings.get_setting("sliders_overshoot", False))


def _set_overshoot_sliders_enabled(enabled):
    settings.set_setting("sliders_overshoot", bool(enabled))
    try:
        import TheKeyMachine.core.runtimeManager as runtime
        manager = runtime.get_runtime_manager()
        manager.overshootChanged.emit(bool(enabled))
        manager.set_tool_state("overshoot_sliders", bool(enabled))
    except Exception:
        pass


def toggle_overshoot_sliders_enabled(*_args, **_kwargs):
    state = not _get_overshoot_sliders_enabled()
    _set_overshoot_sliders_enabled(state)
    return state


def _get_link_autolink_enabled():
    return bool(settings.get_setting("link_checkbox_state", False))


def _set_link_autolink_enabled(enabled):
    enabled = bool(enabled)
    settings.set_setting("link_checkbox_state", enabled)
    try:
        from TheKeyMachine.core.toolbar import get_toolbar
        toolbar = get_toolbar()
        if toolbar:
            toolbar.link_checkbox_state = enabled
    except Exception:
        pass
    if enabled:
        keyTools.add_link_obj_callbacks()
    else:
        keyTools.remove_link_obj_callbacks()
    try:
        import TheKeyMachine.core.runtimeManager as runtime
        runtime.get_runtime_manager().set_tool_state("link_autolink", enabled)
    except Exception:
        pass


TOOL_DEFINITIONS = {
    "toolbar_toggle": {
        "type": "tool",
        "label": "Toggle Toolbar",
        "icon": icons.tkm_main,
        "tooltip": "Show or hide the TheKeyMachine toolbar.",
    },
    "toolbar_add_shelf_button": {
        "type": "tool",
        "label": "Add Toggle Button To Shelf",
        "icon": icons.tkm_main,
        "tooltip": "Add a Maya shelf button that toggles the TheKeyMachine toolbar.",
    },
    "toolbar_reload": {
        "type": "tool",
        "label": "Reload",
        "icon": icons.reload,
        "tooltip": "Reload the TheKeyMachine toolbar and apply code or layout changes.",
    },
    "toolbar_unload": {
        "type": "tool",
        "label": "Unload",
        "icon": icons.close,
        "tooltip": "Unload the TheKeyMachine toolbar and stop its runtime tools.",
    },
    "toolbar_uninstall": {
        "type": "tool",
        "label": "Uninstall",
        "icon": icons.remove,
        "callback": ui.uninstall,
        "tooltip": "Remove TheKeyMachine from Maya.",
    },
    "check_for_updates": {
        "type": "tool",
        "label": "Check for Updates",
        "icon": icons.check_updates,
        "tooltip": "Check online for a newer TheKeyMachine release.",
    },
    "main_preferences_menu": {
        "type": "menu",
        "label": "Preferences",
        "icon": icons.settings,
        "tooltip": "Open general toolbar options.",
    },
    "start_with_maya": {
        "type": "check",
        "label": "Start with Maya",
        "callback": ui.install_userSetup,
        "tooltip": "Load TheKeyMachine automatically when Maya starts.",
    },
    "show_tooltips": {
        "type": "check",
        "label": "Show Tooltips",
        "callback": toolMenus.update_show_tooltips,
        "tooltip": "Show detailed help when hovering over tools and menu actions.",
    },
    "main_dock_menu": {
        "type": "menu",
        "label": "Dock",
        "icon": icons.dock,
        "tooltip": "Move the toolbar to a different Maya area.",
    },
    "main_system_menu": {
        "type": "menu",
        "label": "System",
        "icon": icons.system,
        "tooltip": "Open maintenance actions.",
    },
    "graph_settings_menu": {
        "type": "menu",
        "label": "Settings",
        "icon": icons.settings,
        "tooltip": "Open Graph Editor toolbar settings.",
    },
    "graph_dock_menu": {
        "type": "menu",
        "label": "Dock",
        "icon": icons.dock,
        "tooltip": "Move the Graph Editor toolbar.",
    },
    "help_menu": {
        "type": "menu",
        "label": "Help",
        "icon": icons.help,
        "tooltip": "Open docs, support, and community links.",
    },

    # ---------------------------------------------------------------  WINDOWS  --------------------------------------------------------------

    "orbit_window": {
        "type": "tool",
        "label": "Orbit Window",
        "icon": icons.orbit_ui,
        "callback": trigger.make_command_callback("orbit_window"),
    },
    "hotkeys_window": {
        "type": "tool",
        "label": "Hotkeys",
        "icon": icons.hotkeys,
        "tooltip": "Open the TheKeyMachine hotkey editor.",
        "callback": trigger.make_command_callback("hotkeys_window"),
    },
    "about_window": {
        "type": "tool",
        "label": "About",
        "icon": icons.about,
        "tooltip": "Show TheKeyMachine version, credits, and project information.",
        "callback": trigger.make_command_callback("about_window"),
    },
    "donate_window": {
        "type": "tool",
        "label": "Donate",
        "icon": icons.donate,
        "tooltip": helper.donate_tooltip_text,
        "callback": trigger.make_command_callback("donate_window"),
    },
    "bug_report_window": {
        "type": "tool",
        "label": "Bug Report",
        "icon": icons.bug,
        "tooltip": "Open the bug report window to save a report with your notes and current error details.",
        "callback": trigger.make_command_callback("bug_report_window"),
    },

    # ---------------------------------------------------------------  SMART TOOLS  --------------------------------------------------------------

    "smart_rotation": {
        "type": "tool",
        "label": "Smart Rotation",
        "icon": icons.tangent_auto,
    },
    "smart_rotation_release": {
        "type": "tool",
        "label": "Smart Rotation Release",
        "icon": icons.tangent_auto,
    },
    "smart_translation": {
        "type": "tool",
        "label": "Smart Translation",
        "icon": icons.cube,
    },
    "smart_translation_release": {
        "type": "tool",
        "label": "Smart Translation Release",
        "icon": icons.cube,
    },


    "depth_mover": {
        "type": "tool",
        "label": "Depth Mover",
        "icon": icons.depth_mover,
    },

    # ---------------------------------------------------------------  SHARE KEYS  --------------------------------------------------------------

    "share_keys": {
        "type": "tool",
        "label": "Share Keys",
        "text": "sK",
        "icon": icons.share_keys,
        "callback": keyTools.share_keys,
        "menu": _tool_menu_builder("build_share_keys_menu"),
        "tooltip": helper.share_keys_tooltip_text,
    },
    "share_keys_from_last_selected": {
        "type": "tool",
        "label": "Share Keys From Last Selected",
        "text": "sK",
        "icon": icons.share_keys,
        "callback": keyTools.share_keys_from_last_selected,
        "tooltip": helper.share_keys_from_last_selected_tooltip_text,
        "default": False,
    },
    "reblock": {
        "type": "tool",
        "label": "reBlock",
        "text": "rB",
        "icon": icons.reblock,
        "callback": keyTools.reblock_move,
        "tooltip": helper.reblock_move_tooltip_text,
    },

    # ---------------------------------------------------------------  BAKE ANIMATION  --------------------------------------------------------------

    "bake_animation_custom": {
        "type": "tool",
        "label": "Bake Custom Interval",
        "text": "BA",
        "icon": icons.bake_animation_custom,
        "callback": bar.bake_animation_custom_window,
        "tooltip": helper.bake_animation_custom_tooltip_text,
    },
    "bake_animation_from_last_selected": {
        "type": "tool",
        "label": "Bake From Last Selected",
        "text": "BA",
        "icon": icons.bake_animation_1,
        "callback": keyTools.bake_animation_from_last_selected,
        "tooltip": helper.bake_animation_from_last_selected_tooltip_text,
        "default": False,
    },
    "bake_animation_1": {
        "type": "tool",
        "label": "Bake on Ones",
        "text": "BA",
        "icon": icons.bake_animation_1,
        "callback": keyTools.bake_animation_1,
        "menu": _tool_menu_builder("build_bake_menu"),
        "tooltip": helper.bake_animation_1_tooltip_text,
    },
    "bake_animation_2": {
        "type": "tool",
        "label": "Bake on Twos",
        "text": "BA",
        "icon": icons.bake_animation_2,
        "callback": keyTools.bake_animation_2,
        "tooltip": helper.bake_animation_2_tooltip_text,
    },
    "bake_animation_3": {
        "type": "tool",
        "label": "Bake on Threes",
        "text": "BA",
        "icon": icons.bake_animation_3,
        "callback": keyTools.bake_animation_3,
        "tooltip": helper.bake_animation_3_tooltip_text,
    },
    "bake_animation_4": {
        "type": "tool",
        "label": "Bake on Fours",
        "text": "BA",
        "icon": icons.bake_animation_3,
        "callback": keyTools.bake_animation_4,
        "tooltip": helper.bake_animation_4_tooltip_text,
    },

    # ---------------------------------------------------------------  TOOL DIALOGS  --------------------------------------------------------------

    "orbit": {
        "type": "check",
        "state_key": "orbit",
        "label": "Orbit",
        "text": "Orb",
        "icon": icons.orbit_ui,
        "callback": orbitApi.toggle_orbit_window,
        "get_checked": orbitApi.is_orbit_window_open,
        "set_checked": _set_orbit_window_open,
        "bind_checked_fn": orbitApi.bind_orbit_toolbar_button,
        "tooltip": helper.orbit_tooltip_text,
    },
    "attribute_switcher": {
        "type": "check",
        "state_key": "attribute_switcher",
        "label": "Attribute Switcher",
        "text": "SSw",
        "icon": icons.attribute_switcher,
        "callback": attributeSwitcherApi.toggle_attribute_switcher_window,
        "get_checked": attributeSwitcherApi.is_attribute_switcher_window_open,
        "set_checked": _set_attribute_switcher_window_open,
        "bind_checked_fn": attributeSwitcherApi.bind_attribute_switcher_toolbar_button,
        "tooltip": helper.attribute_switcher_tooltip_text,
    },
    "gimbal": {
        "type": "check",
        "state_key": "gimbal",
        "label": "Gimbal Fixer",
        "text": "Gim",
        "icon": icons.reblock,
        "callback": gimbalFixerApi.toggle_gimbal_fixer_window,
        "get_checked": gimbalFixerApi.is_gimbal_fixer_window_open,
        "set_checked": _set_gimbal_fixer_window_open,
        "bind_checked_fn": gimbalFixerApi.bind_gimbal_fixer_toolbar_button,
        "tooltip": helper.gimbal_fixer_tooltip_text,
    },

    # ---------------------------------------------------------------  TEMP PIVOT --------------------------------------------------------------

    "temp_pivot": {
        "type": "check",
        "state_key": "temp_pivot",
        "label": "Temp Pivot",
        "text": "TP",
        "icon": icons.temp_pivot,
        "callback": tempPivotApi.toggle_temp_pivot,
        "get_checked": tempPivotApi.is_temp_pivot_active,
        "set_checked": tempPivotApi.toggle_temp_pivot,
        "bind_checked_fn": tempPivotApi.bind_temp_pivot_toolbar_button,
        "tooltip": helper.temp_pivot_tooltip_text,
    },
    "temp_pivot_last_object": {
        "type": "tool",
        "label": "Temp Pivot to Last Object",
        "icon": icons.temp_pivot_last_object,
        "callback": tempPivotApi.create_last_object_temp_pivot,
        "tooltip": helper.temp_pivot_last_object_tooltip_text,
        "pinnable": False,
    },
    "temp_pivot_centered": {
        "type": "tool",
        "label": "Temp Pivot Centered",
        "icon": icons.temp_pivot,
        "callback": tempPivotApi.create_centered_temp_pivot,
        "tooltip": helper.temp_pivot_centered_tooltip_text,
    },
    "temp_pivot_worldspace": {
        "type": "tool",
        "label": "Temp Pivot WorldSpace",
        "icon": icons.temp_pivot_worldspace,
        "callback": tempPivotApi.create_worldspace_temp_pivot,
        "tooltip": helper.temp_pivot_worldspace_tooltip_text,
    },
    "temp_pivot_edit": {
        "type": "tool",
        "label": "Edit Temp Pivot",
        "icon": icons.temp_pivot_edit,
        "callback": tempPivotApi.edit_temp_pivot,
        "tooltip": helper.temp_pivot_edit_tooltip_text,
    },
    "temp_pivot_reset": {
        "type": "tool",
        "label": "Reset Temp Pivot",
        "icon": icons.temp_pivot_reset,
        "callback": tempPivotApi.reset_temp_pivot,
        "tooltip": helper.temp_pivot_reset_tooltip_text,
    },
    "temp_pivot_help": {
        "type": "tool",
        "label": "Help",
        "tooltip": "Open Documentation for Temp Pivots tools.",
        "icon": icons.help,
        "callback": lambda: general.open_url("https://thekeymachine.gitbook.io/base/the-toolbar/animation-tools/temp-pivots"),
        "pinnable": False,
    },
    "micro_move": {
        "type": "check",
        "state_key": "micro_move",
        "label": "Micro Move",
        "text": "MM",
        "icon": icons.ruler,
        "callback": trigger.make_command_callback("micro_move"),
        "get_checked": lambda: _toolbar_controller_enabled("micro_move_controller"),
        "set_checked": _set_micro_move_enabled,
        "tooltip": helper.micro_move_tooltip_text,
    },

    # ----------------------------------------------  SETTINGS  --------------------------------------------------------

    "overshoot_sliders": {
        "type": "check",
        "state_key": "overshoot_sliders",
        "label": "Overshoot Sliders",
        "menu_label": "Overshoot Sliders",
        "text": "OS",
        "icon": icons.sliders_overshoot,
        "callback": trigger.make_command_callback("overshoot_sliders"),
        "get_checked": _get_overshoot_sliders_enabled,
        "set_checked": _set_overshoot_sliders_enabled,
        "tooltip": "Set range for sliders to -150/150, from -100/100.",
        "setting_toggle": "overshoot_sliders",
    },
    "attribute_switcher_euler_filter": {
        "type": "check",
        "state_key": "attribute_switcher_euler_filter",
        "label": "Auto Euler Filter",
        "menu_label": "Auto Euler Filter",
        "text": "EF",
        "icon": icons.euler_filter,
        "callback": trigger.make_command_callback("attribute_switcher_euler_filter"),
        "get_checked": attributeSwitcherApi.is_euler_filter_enabled,
        "set_checked": attributeSwitcherApi.set_euler_filter_enabled,
        "tooltip": "Apply Euler filtering after Attribute Switcher changes rotation order.",
        "setting_toggle": "attribute_switcher_euler_filter",
    },

    # ----------------------------------------------  NUDGE  --------------------------------------------------------

    "nudge_value": {
        "type": "widget",
        "label": "Nudge Value",
        "tooltip": "Set the number of frames used by the Nudge and Inbetween tools.",
        "default": True,
    },
    "nudge_left": {
        "type": "tool",
        "label": "Nudge Left",
        "icon": icons.nudge_left,
        "callback": trigger.make_command_callback("nudge_left"),
        "menu": _tool_menu_builder("build_nudge_left_menu"),
        "tooltip": helper.nudge_left_tooltip_text,
    },
    "nudge_left_all_keys": {
        "type": "tool",
        "label": "Nudge Left All Keys",
        "icon": icons.nudge_left_all_keys,
        "callback": trigger.make_command_callback("nudge_left_all_keys"),
        "tooltip": helper.nudge_left_tooltip_text,
        "default": False,
    },
    "nudge_left_scene": {
        "type": "tool",
        "label": "Nudge Left Scene",
        "icon": icons.nudge_left_scene,
        "callback": trigger.make_command_callback("nudge_left_scene"),
        "tooltip": helper.nudge_left_tooltip_text,
        "default": False,
    },

    "nudge_right": {
        "type": "tool",
        "label": "Nudge Right",
        "icon": icons.nudge_right,
        "callback": trigger.make_command_callback("nudge_right"),
        "menu": _tool_menu_builder("build_nudge_right_menu"),
        "tooltip": helper.nudge_right_tooltip_text,
    },
    "nudge_right_all_keys": {
        "type": "tool",
        "label": "Nudge Right All Keys",
        "icon": icons.nudge_right_all_keys,
        "callback": trigger.make_command_callback("nudge_right_all_keys"),
        "tooltip": helper.nudge_right_tooltip_text,
        "default": False,
    },
    "nudge_right_scene": {
        "type": "tool",
        "label": "Nudge Right Scene",
        "icon": icons.nudge_right_scene,
        "callback": trigger.make_command_callback("nudge_right_scene"),
        "tooltip": helper.nudge_right_tooltip_text,
        "default": False,
    },

    "nudge_insert_inbetween": {
        "type": "tool",
        "label": "Insert Inbetween",
        "icon": icons.nudge_insert_inbetween,
        "callback": trigger.make_command_callback("nudge_insert_inbetween"),
        "tooltip": helper.insert_inbetween_tooltip_text,
    },
    "nudge_insert_inbetween_scene": {
        "type": "tool",
        "label": "Insert Inbetween Scene",
        "icon": icons.nudge_insert_inbetween_scene,
        "callback": trigger.make_command_callback("nudge_insert_inbetween_scene"),
        "tooltip": helper.insert_inbetween_tooltip_text,
        "default": False,
    },
    "nudge_remove_inbetween": {
        "type": "tool",
        "label": "Remove Inbetween",
        "icon": icons.nudge_remove_inbetween,
        "callback": trigger.make_command_callback("nudge_remove_inbetween"),
        "tooltip": helper.remove_inbetween_tooltip_text,
    },
    "nudge_remove_inbetween_scene": {
        "type": "tool",
        "label": "Remove Inbetween Scene",
        "icon": icons.nudge_remove_inbetween_scene,
        "callback": trigger.make_command_callback("nudge_remove_inbetween_scene"),
        "tooltip": helper.remove_inbetween_tooltip_text,
        "default": False,
    },

    # ----------------------------------------------  SELECTIONS  --------------------------------------------------------

    "clear_selected_keys": {
        "type": "tool",
        "label": "Clear Selection",
        "text": "x",
        "callback": trigger.make_command_callback("clear_selected_keys", keyTools.clear_selected_keys),
        "tooltip": helper.clear_selected_keys_widget_tooltip_text,
    },
    "select_scene_animation": {
        "type": "tool",
        "label": "Select Scene Anim",
        "text": "s",
        "callback": keyTools.select_all_animation_curves,
        "tooltip": helper.select_scene_animation_widget_tooltip_text,
    },
    "delete_static_animation": {
        "type": "tool",
        "label": "Remove Static Anim Curves",
        "text": "S",
        "icon": icons.delete_animation,
        "tooltip": helper.delete_static_animation_tooltip_text,
        "callback": trigger.make_command_callback("remove_static_anim_curves"),
    },
    "apply_smart_euler_filter": {
        "type": "tool",
        "label": "Apply Smart Euler Filter",
        "icon": icons.euler_filter,
        "tooltip": helper.apply_smart_euler_filter_tooltip_text,
        "callback": trigger.make_command_callback("apply_smart_euler_filter"),
    },
    "clear_animation": {
        "type": "tool",
        "label": "Clear Animation",
        "icon": icons.delete_animation,
        "tooltip": helper.clear_animation_keys_tooltip_text,
        "callback": trigger.make_command_callback("clear_animation"),
    },
    "copy_keys": {
        "type": "tool",
        "label": "Copy Keys",
        "icon": icons.copy_animation,
        "tooltip": helper.copy_keys_tooltip_text,
        "callback": trigger.make_command_callback("copy_keys"),
    },
    "crop_animation": {
        "type": "tool",
        "label": "Crop Animation",
        "icon": icons.isolate,
        "tooltip": helper.crop_animation_tooltip_text,
        "callback": trigger.make_command_callback("crop_animation"),
    },
    "cut_keys": {
        "type": "tool",
        "label": "Cut Keys",
        "icon": icons.get("eraser"),
        "tooltip": helper.cut_keys_tooltip_text,
        "callback": trigger.make_command_callback("cut_keys"),
    },
    "delete_keys": {
        "type": "tool",
        "label": "Delete Keys",
        "icon": icons.trash,
        "tooltip": helper.delete_keys_tooltip_text,
        "callback": trigger.make_command_callback("delete_keys"),
    },
    "paste_keys": {
        "type": "tool",
        "label": "Paste Keys",
        "icon": icons.paste_animation,
        "tooltip": helper.paste_keys_tooltip_text,
        "callback": trigger.make_command_callback("paste_keys"),
    },
    "paste_keys_relative": {
        "type": "tool",
        "label": "Paste Keys Relative",
        "icon": icons.paste_insert_animation,
        "tooltip": helper.paste_keys_relative_tooltip_text,
        "callback": trigger.make_command_callback("paste_keys_relative"),
    },
    "remove_redundant_keys": {
        "type": "tool",
        "label": "Remove Redundant Keys",
        "icon": icons.remove_redundant_keys,
        "tooltip": helper.remove_redundant_keys_tooltip_text,
        "callback": trigger.make_command_callback("remove_redundant_keys"),
    },
    "remove_static_anim_curves": {
        "type": "tool",
        "label": "Remove Static Anim Curves",
        "icon": icons.remove_static_anim_curves,
        "tooltip": helper.remove_static_anim_curves_tooltip_text,
        "callback": trigger.make_command_callback("remove_static_anim_curves"),
    },
    "reverse_animation": {
        "type": "tool",
        "label": "Reverse Animation",
        "icon": icons.get("flip"),
        "tooltip": helper.reverse_animation_tooltip_text,
        "callback": trigger.make_command_callback("reverse_animation"),
    },
    "set_smart_key": {
        "type": "tool",
        "label": "Set Smart Key",
        "text": "S",
        "tooltip": helper.set_smart_key_tooltip_text,
        "callback": trigger.make_command_callback("set_smart_key"),
    },
    "set_smart_key_all_channels": {
        "type": "tool",
        "label": "Set Smart Key All Channels",
        "text": "S+",
        "tooltip": helper.set_smart_key_all_channels_tooltip_text,
        "callback": trigger.make_command_callback("set_smart_key_all_channels"),
    },
    "graph_match_keys": {
        "type": "tool",
        "label": "Match Curves",
        "text": "M",
        "icon": icons.align,
        "tooltip": helper.graph_match_keys_tooltip_text,
        "callback": lambda: keyTools.graph_match_keys(),
    },
    "graph_flip": {
        "type": "tool",
        "label": "Flip Curves",
        "text": "F",
        "tooltip": helper.flip_tooltip_text,
        "callback": lambda: keyTools.flipCurves(),
    },
    "snap": {
        "type": "tool",
        "label": "Snap Keys",
        "text": "SpK",
        "icon": icons.snap,
        "tooltip": helper.snap_tooltip_text,
        "callback": lambda: keyTools.snapKeyframes(),
    },
    "graph_overlap_forward": {
        "type": "tool",
        "label": "Overlap Forward",
        "text": "O>",
        "tooltip": helper.overlap_tooltip_text,
        "callback": keyTools.overlap_forward,
    },
    "graph_overlap_backward": {
        "type": "tool",
        "label": "Overlap Backward",
        "text": "O<",
        "tooltip": helper.overlap_tooltip_text,
        "callback": keyTools.overlap_backward,
    },

# ---------------------------------------------------------------  ISOLATE --------------------------------------------------------------

    "isolate_master": {
        "type": "tool",
        "label": "Isolate",
        "icon": icons.isolate,
        "callback": bar.isolate_master,
        "tooltip": helper.isolate_tooltip_text,
    },
    "isolate_down_level": {
        "type": "widget",
        "label": "Down one level",
    },
    "isolate_bookmarks": {
        "type": "tool",
        "label": "Isolate Bookmarks",
        "icon": icons.isolate_bookmarks,
        "callback": isolateBookmarksApi.create_isolate_bookmarks_window,
        "tooltip": helper.isolate_bookmarks_window_tooltip_text,
    },
    "isolate_help": {
        "type": "tool",
        "label": "Help",
        "tooltip": "Open Documentation for Isolate tools.",
        "icon": icons.help,
        "callback": lambda: general.open_url("https://thekeymachine.gitbook.io/base/the-toolbar/animation-tools/isolate"),
        "pinnable": False,
    },

# ---------------------------------------------------------------  DEFAULT POSE --------------------------------------------------------------

    "default_object_values": {
        "type": "tool",
        "label": "Default Pose",
        "icon": icons.default,
        "callback": keyTools.default_object_values,
        "tooltip": helper.default_values_tooltip_text,
    },
    "default_translations": {
        "type": "tool",
        "label": "Default Translations",
        "text": "RT",
        "icon": icons.default,
        "callback": lambda: keyTools.default_object_values(default_translations=True),
        "tooltip": helper.default_translations_tooltip_text,
    },
    "default_rotations": {
        "type": "tool",
        "label": "Default Rotations",
        "text": "RR",
        "icon": icons.default,
        "callback": lambda: keyTools.default_object_values(default_rotations=True),
        "tooltip": helper.default_rotations_tooltip_text,
    },
    "default_scales": {
        "type": "tool",
        "label": "Default Scales",
        "text": "RS",
        "icon": icons.default,
        "callback": lambda: keyTools.default_object_values(default_scales=True),
        "tooltip": helper.default_scales_tooltip_text,
    },
    "default_trs": {
        "type": "tool",
        "label": "Default Translation Rotation Scale",
        "text": "RTRS",
        "icon": icons.default,
        "callback": lambda: keyTools.default_object_values(
            default_translations=True,
            default_rotations=True,
            default_scales=True,
        ),
        "tooltip": helper.default_trs_tooltip_text,
    },

    "delete_all_animation": {
        "type": "tool",
        "label": "Clear Animation",
        "icon": icons.delete_animation,
        "callback": trigger.make_command_callback("clear_animation"),
        "tooltip": helper.delete_animation_tooltip_text,
    },

    "default_set_defaults": {
        "type": "tool",
        "label": "Set Default Values For Selected",
        "icon": icons.default,
        "callback": keyTools.save_default_values,
    },
    "default_restore_defaults": {
        "type": "tool",
        "label": "Restore Default Values For Selected",
        "icon": icons.default,
        "callback": keyTools.remove_default_values_for_selected_object,
    },
    "default_clear_all": {
        "type": "tool",
        "label": "Clear All Default Settings",
        "icon": icons.default,
        "callback": keyTools.restore_default_data,
    },

    "default_help": {
        "type": "tool",
        "label": "Help",
        "tooltip": "Open Documentation for Default tools.",
        "icon": icons.help,
        "callback": lambda: general.open_url("https://thekeymachine.gitbook.io/base/the-toolbar/animation-tools/default-to-default"),
        "pinnable": False,
    },

    # ---------------------------------------------------------------  SELECT --------------------------------------------------------------

    "select_rig_controls": {
        "type": "tool",
        "label": "Select Rig Controls",
        "icon": icons.select_rig_controls,
        "callback": bar.select_rig_controls,
        "tooltip": helper.select_rig_controls_tooltip_text,
    },
    "select_rig_controls_animated": {
        "type": "tool",
        "label": "Select Animated Rig Controls",
        "icon": icons.select_rig_controls_animated,
        "tooltip": helper.select_rig_controls_animated_tooltip_text,
        "callback": bar.select_rig_controls_animated,
    },
    "select_opposite": {
        "type": "tool",
        "label": "Select Opposite",
        "icon": icons.opposite_select,
        "callback": keyTools.selectOpposite,
        "tooltip": helper.opposite_select_tooltip_text,
    },

    # ---------------------------------------------------------------  SELECTION SETS --------------------------------------------------------------

    "selection_sets": {
        "type": "check",
        "state_key": "selection_sets",
        "label": "Selection Sets",
        "text": "SS",
        "icon": icons.selection_sets,
        "callback": selectionSetsApi.toggle_selection_sets_window,
        "get_checked": selectionSetsApi.is_selection_sets_window_open,
        "set_checked": _set_selection_sets_window_open,
        "bind_checked_fn": selectionSetsApi.bind_selection_sets_toolbar_button,
        "tooltip": helper.selection_sets_tooltip_text,
    },
    "selection_sets_quick_export": {
        "type": "tool",
        "label": "Quick Export",
        "text": "QEx",
        "icon": icons.selection_sets_export,
        "tooltip": helper.quick_export_selection_sets_tooltip_text,
        "callback": selectionSetsApi.quick_export_selection_sets,
    },
    "selection_sets_quick_import": {
        "type": "tool",
        "label": "Quick Import",
        "text": "QIm",
        "icon": icons.selection_sets_import,
        "tooltip": helper.quick_import_selection_sets_tooltip_text,
        "callback": selectionSetsApi.quick_import_selection_sets,
    },
    "selection_sets_export": {
        "type": "tool",
        "label": "Export",
        "text": "Ex",
        "icon": icons.selection_sets_export,
        "tooltip": helper.export_selection_sets_tooltip_text,
        "callback": selectionSetsApi.export_selection_sets,
    },
    "selection_sets_import": {
        "type": "tool",
        "label": "Import",
        "text": "Im",
        "icon": icons.selection_sets_import,
        "tooltip": helper.import_selection_sets_tooltip_text,
        "callback": selectionSetsApi.import_selection_sets,
    },
    "selection_sets_clear_all": {
        "type": "tool",
        "label": "Clear All Select Sets",
        "text": "Clr",
        "icon": icons.trash,
        "tooltip": helper.clear_selection_sets_tooltip_text,
        "callback": selectionSetsApi.clear_all_selection_sets,
    },
    "custom_graph": {
        "type": "check",
        "state_key": "custom_graph",
        "label": "Graph Editor Toolbar",
        "menu_label": "Show Graph Editor Toolbar",
        "text": "GE",
        "icon": icons.customGraph,
        "callback": trigger.make_command_callback("custom_graph"),
        "get_checked": graphToolbarApi.get_graph_toolbar_checkbox_state,
        "set_checked": lambda state: graphToolbarApi.set_graph_toolbar_enabled(bool(state), apply=True),
        "tooltip": helper.customGraph_tooltip_text,
        "setting_toggle": "custom_graph",
    },
    "graph_extra_tools": {
        "type": "menu",
        "label": "Graph Extras",
        "text": "E",
        "menu": _tool_menu_builder("build_graph_extra_tools_menu"),
        "tooltip": helper.extra_tools_tooltip_text,
    },
    "select_hierarchy": {
        "type": "tool",
        "label": "Select Hierarchy",
        "icon": icons.select_hierarchy,
        "callback": bar.selectHierarchy,
        "tooltip": helper.select_hierarchy_tooltip_text,
    },
    "selector": {
        "type": "tool",
        "label": "Selector",
        "icon": icons.selector,
        "callback": bar.selector_window,
        "tooltip": helper.selector_tooltip_text,
        "default": True,
    },

    # ---------------------------------------------------------------  TEMP LOCATOR  --------------------------------------------------------------

    "create_locator": {
        "type": "tool",
        "label": "Create Locator",
        "icon": icons.cube,
        "callback": bar.createLocator,
        "tooltip": helper.createLocator_tooltip_text,
    },
    "locator_select_temp": {
        "type": "tool",
        "label": "Select Temp Locators",
        "icon": icons.cube,
        "callback": bar.selectTempLocators,
        "tooltip": "Select all temporary locators in the scene.",
    },
    "locator_remove_temp": {
        "type": "tool",
        "label": "Remove Temp Locators",
        "icon": icons.cube,
        "callback": bar.deleteTempLocators,
        "tooltip": "Remove all temporary locators from the scene.",
    },

    # ---------------------------------------------------------------  COPY POSE/ANIMATION --------------------------------------------------------------

    "copy_pose": {
        "type": "tool",
        "label": "Copy Pose",
        "icon": icons.copy_pose,
        "callback": keyTools.copy_pose,
        "menu": toolMenus.build_copy_pose_menu,
        "tooltip": helper.copy_pose_tooltip_text,
    },
    "paste_pose": {
        "type": "tool",
        "label": "Paste Pose",
        "icon": icons.paste_pose,
        "callback": keyTools.paste_pose,
        "tooltip": helper.paste_pose_tooltip_text,
    },
    "paste_pose_to": {
        "type": "tool",
        "label": "Paste Pose To",
        "icon": icons.paste_pose,
        "callback": keyTools.paste_pose_to,
    },
    "export_pose_file": {
        "type": "tool",
        "label": "Export Pose",
        "icon": icons.export,
        "callback": keyTools.export_pose_file,
        "tooltip": "Export the copied pose data to a JSON file.",
    },
    "import_pose_file": {
        "type": "tool",
        "label": "Import Pose",
        "icon": icons.import_icon if hasattr(icons, "import_icon") else icons.get("import"),
        "callback": keyTools.import_pose_file,
        "tooltip": "Import copied pose data from a JSON file.",
    },
    "copy_animation": {
        "type": "tool",
        "label": "Copy Animation",
        "icon": icons.copy_animation,
        "callback": keyTools.copy_animation,
        "menu": toolMenus.build_copy_animation_menu,
        "tooltip": helper.copy_animation_tooltip_text,
    },

    "paste_animation": {
        "type": "tool",
        "label": "Paste Replace Animation",
        "icon": icons.paste_animation,
        "callback": keyTools.paste_animation,
        "tooltip": helper.paste_animation_tooltip_text,
    },
    "paste_insert_animation": {
        "type": "tool",
        "label": "Paste Insert Animation",
        "icon": icons.paste_insert_animation,
        "callback": keyTools.paste_insert_animation,
        "tooltip": helper.paste_insert_animation_tooltip_text,
    },
    "paste_animation_to": {
        "type": "tool",
        "label": "Paste Animation To",
        "icon": icons.paste_animation,
        "callback": keyTools.paste_animation_to,
    },
    "export_animation_file": {
        "type": "tool",
        "label": "Export Animation",
        "icon": icons.export,
        "callback": keyTools.export_animation_file,
        "tooltip": "Export the copied animation data to a JSON file.",
    },
    "import_animation_file": {
        "type": "tool",
        "label": "Import Animation",
        "icon": icons.import_icon if hasattr(icons, "import_icon") else icons.get("import"),
        "callback": keyTools.import_animation_file,
        "tooltip": "Import copied animation data from a JSON file.",
    },

    "pose_help": {
        "type": "tool",
        "label": "Help",
        "tooltip": "Open Documentation for Copy/Paste Pose tools.",
        "icon": icons.help,
        "callback": lambda: general.open_url(
            "https://thekeymachine.gitbook.io/base/the-toolbar/animation-tools/copy-paste-animation#pose-tools"
        ),
        "pinnable": False,
    },
    "copy_animation_help": {
        "type": "tool",
        "label": "Help",
        "tooltip": "Open Documentation for Copy/Paste Animation tools.",
        "icon": icons.help,
        "callback": lambda: general.open_url("https://thekeymachine.gitbook.io/base/the-toolbar/animation-tools/copy-paste-animation"),
        "pinnable": False,
    },

    # ---------------------------------------------------------------  FOLLOW CAMERAS --------------------------------------------------------------

    "follow_cam": {
        "type": "tool",
        "label": "Follow Cam",
        "icon": icons.follow_cam,
        "callback": lambda *args: bar.create_follow_cam(translation=True, rotation=True),
        "tooltip": helper.follow_cam_tooltip_text,
    },
    "follow_cam_translation": {
        "type": "tool",
        "label": "Follow only Translation",
        "icon": icons.follow_cam,
        "callback": lambda: bar.create_follow_cam(translation=True, rotation=False),
        "tooltip": helper.follow_cam_tooltip_text,
    },
    "follow_cam_rotation": {
        "type": "tool",
        "label": "Follow only Rotation",
        "icon": icons.follow_cam,
        "callback": lambda: bar.create_follow_cam(translation=False, rotation=True),
        "tooltip": helper.follow_cam_tooltip_text,
    },
    "follow_cam_remove": {
        "type": "tool",
        "label": "Remove Follow Cam",
        "icon": icons.remove,
        "callback": bar.remove_followCam,
    },
    "animation_offset": {
        "type": "check",
        "state_key": "animation_offset",
        "label": "Anim Offset",
        "icon": icons.animation_offset,
        "callback": trigger.make_command_callback("animation_offset"),
        "get_checked": lambda: _toolbar_controller_enabled("animation_offset_controller"),
        "set_checked": _set_animation_offset_enabled,
        "tooltip": helper.animation_offset_tooltip_text,
    },
    "ws_copy_frame": {
        "type": "tool",
        "label": "Copy World Space",
        "icon": icons.worldspace_copy_frame,
        "callback": bar.copy_worldspace_single_frame,
        "tooltip": helper.copy_worldspace_tooltip_text,
    },

    # ---------------------------------------------------------------  ALIGN OBJECTS --------------------------------------------------------------

    "align_objects": {
        "type": "tool",
        "label": "Align Objects",
        "icon": icons.align,
        "callback": bar.align_selected_objects,
        "tooltip": helper.align_tooltip_text,
    },
    "align_objects_all_keys": {
        "type": "tool",
        "label": "Align Objects All Keys",
        "icon": icons.align,
        "callback": partial(bar.align_selected_objects, key_scope="all"),
        "tooltip": helper.align_tooltip_text,
    },
    "align_object_translation": {
        "type": "tool",
        "label": "Align Object Translation",
        "icon": icons.align,
        "callback": partial(bar.align_selected_objects, pos=True, rot=False, scl=False),
    },
    "align_object_translation_all_keys": {
        "type": "tool",
        "label": "Align Object Translation All Keys",
        "tooltip": "Align translation over all keyed frames.",
        "icon": icons.align,
        "callback": partial(bar.align_selected_objects, pos=True, rot=False, scl=False, key_scope="all"),
    },
    "align_object_rotation": {
        "type": "tool",
        "label": "Align Object Rotation",
        "icon": icons.align,
        "callback": partial(bar.align_selected_objects, pos=False, rot=True, scl=False),
    },
    "align_object_rotation_all_keys": {
        "type": "tool",
        "label": "Align Object Rotation All Keys",
        "tooltip": "Align rotation over all keyed frames.",
        "icon": icons.align,
        "callback": partial(bar.align_selected_objects, pos=False, rot=True, scl=False, key_scope="all"),
    },
    "align_object_scale": {
        "type": "tool",
        "label": "Align Object Scale",
        "icon": icons.align,
        "callback": partial(bar.align_selected_objects, pos=False, rot=False, scl=True),
    },
    "align_object_scale_all_keys": {
        "type": "tool",
        "label": "Align Object Scale All Keys",
        "tooltip": "Align scale over all keyed frames.",
        "icon": icons.align,
        "callback": partial(bar.align_selected_objects, pos=False, rot=False, scl=True, key_scope="all"),
    },
    "align_objects_help": {
        "type": "tool",
        "label": "Align Objects Help",
        "tooltip": "Open Documentation for Align tools.",
        "icon": icons.help,
        "callback": lambda: general.open_url("https://thekeymachine.gitbook.io/base/the-toolbar/animation-tools/match-align"),
        "pinnable": False,
    },

    # ---------------------------------------------------------------  TRACER --------------------------------------------------------------

    "create_tracer": {
        "type": "tool",
        "label": "Tracer",
        "icon": icons.tracer,
        "callback": bar.create_tracer,
        "menu": _tool_menu_builder("build_tracer_menu"),
        "tooltip": helper.tracer_tooltip_text,
    },
    "tracer_refresh": {
        "type": "tool",
        "label": "Refresh Tracer",
        "icon": icons.tracer_refresh,
        "callback": bar.tracer_refresh,
        "tooltip": helper.tracer_refresh_tooltip_text,
    },
    "tracer_show_hide": {
        "type": "tool",
        "label": "Toggle Tracer",
        "icon": icons.tracer_show_hide,
        "callback": bar.tracer_show_hide,
        "tooltip": helper.tracer_toggle_tooltip_text,
    },
    "tracer_offset_node": {
        "type": "tool",
        "label": "Select Offset Object",
        "icon": icons.tracer_select_offset,
        "callback": bar.select_tracer_offset_node,
        "tooltip": helper.tracer_offset_tooltip_text,
    },
    "tracer_grey": {
        "type": "tool",
        "label": "Tracer Style: Grey",
        "icon": icons.tracer_grey,
        "callback": bar.set_tracer_grey_color,
        "tooltip": helper.tracer_grey_tooltip_text,
    },
    "tracer_red": {
        "type": "tool",
        "label": "Tracer Style: Red",
        "icon": icons.tracer_red,
        "callback": bar.set_tracer_red_color,
        "tooltip": helper.tracer_red_tooltip_text,
    },
    "tracer_blue": {
        "type": "tool",
        "label": "Tracer Style: Blue",
        "icon": icons.tracer_blue,
        "callback": bar.set_tracer_blue_color,
        "tooltip": helper.tracer_blue_tooltip_text,
    },
    "tracer_remove": {
        "type": "tool",
        "label": "Remove Tracer",
        "icon": icons.tracer_remove,
        "callback": bar.remove_tracer_node,
        "tooltip": helper.tracer_remove_tooltip_text,
    },
    "tracer_connected": {
        "type": "widget",
        "label": "Connected",
        "tooltip": helper.tracer_connected_tooltip_text,
    },

# ---------------------------------------------------------------  MIRROR --------------------------------------------------------------

    "mirror": {
        "type": "tool",
        "label": "Mirror",
        "icon": icons.mirror,
        "callback": keyTools.mirror,
        "tooltip": helper.mirror_tooltip_text,
    },
    "mirror_to_right": {
        "type": "tool",
        "label": "Mirror to Right",
        "icon": icons.mirror,
        "callback": keyTools.mirror_to_right,
        "tooltip": helper.mirror_to_right_tooltip_text,
    },
    "mirror_to_left": {
        "type": "tool",
        "label": "Mirror to Left",
        "icon": icons.mirror,
        "callback": keyTools.mirror_to_left,
        "tooltip": helper.mirror_to_left_tooltip_text,
    },
    "mirror_all_keys": {
        "type": "tool",
        "label": "Mirror All Keys",
        "icon": icons.mirror,
        "callback": keyTools.mirror_all_keys,
        "tooltip": helper.mirror_all_keys_tooltip_text,
    },
    "mirror_add_invert": {
        "type": "tool",
        "label": "Add Exception Invert",
        "icon": icons.mirror,
        "callback": keyTools.add_mirror_invert_exception,
        "tooltip": helper.mirror_add_invert_tooltip_text,
    },
    "mirror_add_keep": {
        "type": "tool",
        "label": "Add Exception Keep",
        "icon": icons.mirror,
        "callback": keyTools.add_mirror_keep_exception,
        "tooltip": helper.mirror_add_keep_tooltip_text,
    },
    "mirror_remove_exc": {
        "type": "tool",
        "label": "Remove Exception",
        "icon": icons.mirror,
        "callback": keyTools.remove_mirror_invert_exception,
        "tooltip": helper.mirror_remove_exception_tooltip_text,
    },
    "mirror_help": {
        "type": "tool",
        "label": "Help",
        "tooltip": "Open Documentation for Mirror tools.",
        "icon": icons.help,
        "callback": lambda: general.open_url("https://thekeymachine.gitbook.io/base/the-toolbar/animation-tools/mirror"),
        "pinnable": False,
    },
    "opposite_add": {
        "type": "tool",
        "label": "Add Opposite",
        "icon": icons.opposite_add,
        "callback": keyTools.addSelectOpposite,
        "tooltip": helper.opposite_add_tooltip_text,
    },
    "opposite_copy": {
        "type": "tool",
        "label": "Copy Opposite",
        "icon": icons.opposite_copy,
        "callback": keyTools.copyOpposite,
        "tooltip": helper.opposite_copy_tooltip_text,
    },
    "paste_opposite_animation": {
        "type": "tool",
        "label": "Paste Opposite",
        "icon": icons.paste_opposite_animation,
        "callback": keyTools.paste_opposite_animation,
    },
    "paste_mirror_pose": {
        "type": "tool",
        "label": "Paste Mirror Pose",
        "icon": icons.paste_opposite_animation,
        "callback": keyTools.paste_mirror_pose,
    },

# ---------------------------------------------------------------  LINK OBJECTS --------------------------------------------------------------

    "link_copy": {
        "type": "tool",
        "label": "Copy Link Position",
        "icon": icons.link_relative,
        "callback": keyTools.copy_link,
        "tooltip": helper.link_objects_tooltip_text,
    },
    "link_paste": {
        "type": "tool",
        "label": "Paste Link Position",
        "icon": icons.link_relative_paste,
        "callback": keyTools.paste_link,
        "tooltip": helper.paste_link_tooltip_text,
    },
    "link_autolink": {
        "type": "check",
        "state_key": "link_autolink",
        "label": "Auto Link Position",
        "icon": icons.link_relative_on,
        "checkable": True,
        "get_checked": _get_link_autolink_enabled,
        "set_checked": _set_link_autolink_enabled,
        "tooltip": helper.auto_link_tooltip_text,
    },
    "link_help": {
        "type": "tool",
        "label": "Help",
        "tooltip": "Open Documentation for Link Objects tools.",
        "icon": icons.help,
        "callback": lambda: general.open_url("https://thekeymachine.gitbook.io/base/the-toolbar/animation-tools/link-objects"),
        "pinnable": False,
    },


    # ---------------------------------------------------------------  WORLD SPACE --------------------------------------------------------------

    "ws_copy_range": {
        "type": "tool",
        "label": "Copy World Space - Selected Range",
        "icon": icons.worldspace_copy_animation,
        "callback": bar.copy_range_worldspace_animation,
        "tooltip": helper.copy_worldspace_range_tooltip_text,
    },
    "ws_paste_frame": {
        "type": "tool",
        "label": "Paste World Space",
        "icon": icons.worldspace_paste_frame,
        "callback": bar.paste_worldspace_single_frame,
        "tooltip": helper.paste_worldspace_tooltip_text,
    },
    "ws_paste": {
        "type": "tool",
        "label": "Paste World Space - All Animation",
        "icon": icons.worldspace_paste_animation,
        "callback": bar.worldspace_paste_animation,
        "tooltip": helper.paste_worldspace_animation_tooltip_text,
    },
    "worldspace_help": {
        "type": "tool",
        "label": "Help - World Space",
        "tooltip": "Open Documentation for World Space tools.",
        "icon": icons.help,
        "callback": lambda: general.open_url(
            "https://thekeymachine.gitbook.io/base/the-toolbar/animation-tools/copy-paste-animation#worldspace-tools"
        ),
        "pinnable": False,
    },
    "custom_tools": {
        "type": "menu",
        "label": "Custom Tools",
        "icon": icons.tools_folder,
        "callback": trigger.make_command_callback("custom_tools"),
        "menu": _tool_menu_builder("build_custom_tools_menu"),
        "tooltip": helper.custom_tools_tooltip_text,
    },
    "custom_scripts": {
        "type": "menu",
        "label": "Custom Scripts",
        "icon": icons.scripts_folder,
        "callback": trigger.make_command_callback("custom_scripts"),
        "menu": _tool_menu_builder("build_custom_scripts_menu"),
        "tooltip": helper.custom_scripts_tooltip_text,
    },
    "background_runners": {
        "type": "menu",
        "label": "Background Runners",
        "icon": icons.background_runners_0,
        "tooltip": "Toggle persistent automatic helpers and background tool runners.",
        "menu": _tool_menu_builder("build_background_runners_menu"),
    },
    "TKM": {
        "type": "menu",
        "label": "TheKeyMachine",
        "icon": icons.tkm_main,
        "tooltip": "Access global preferences, check for updates, and view credits.",
    },
    "graph_isolate_curves": {
        "type": "tool",
        "label": "Isolate Curves",
        "icon": icons.isolate,
        "callback": keyTools.isolateCurve,
        "tooltip": helper.graph_isolate_curves_tooltip_text,
    },
    "graph_select_object_from_curve": {
        "type": "tool",
        "label": "Select Object from Curve",
        "icon": icons.isolate,
        "callback": keyTools.select_objects_from_selected_curves,
    },
    "graph_toggle_mute": {
        "type": "tool",
        "label": "Mute Curves",
        "text": "Mt",
        "callback": keyTools.toggleMute,
        "tooltip": helper.graph_mute_tooltip_text,
    },
    "graph_toggle_lock": {
        "type": "tool",
        "label": "Lock Curves",
        "text": "Lk",
        "callback": keyTools.toggleLock,
        "tooltip": helper.graph_lock_tooltip_text,
    },
    "enable_graph_filter": {
        "type": "tool",
        "label": "Enable Graph Filter",
        "text": "EnF",
        "callback": ui.filterMode_sync_on,
        "tooltip": helper.graph_filter_tooltip_text,
    },
    "disable_graph_filter": {
        "type": "tool",
        "label": "Disable Graph Filter",
        "text": "DiF",
        "callback": ui.filterMode_sync_off,
        "tooltip": helper.graph_filter_tooltip_text,
    },


    # ---------------------------------------------------- TANGENTS ---------------------------------------------

    "tangent_cycle_matcher": {
        "type": "tool",
        "label": "Cycle Matcher",
        "text": "CM",
        "icon": icons.match_curve_cycle,
        "callback": keyTools.match_curve_cycle,
        "menu": _tool_menu_builder("build_cycle_matcher_menu", icon=icons.match_curve_cycle),
        "tooltip": helper.tangent_cycle_matcher_tooltip_text,
    },
    "tangent_bouncy": {
        "type": "tool",
        "label": "Bouncy Tangent",
        "text": "BO",
        "icon": icons.tangent_bouncy,
        "callback": keyTools.bouncy_tangets,
        "menu": _tool_menu_builder(
            "build_tangent_menu", tangent_type="bouncy", tangent_label="Bouncy Tangent", icon=icons.tangent_bouncy
        ),
        "tooltip": helper.tangent_bouncy_tooltip_text,
    },
    "tangent_auto": {
        "type": "tool",
        "label": "Auto Tangent",
        "text": "AU",
        "icon": icons.tangent_auto,
        "callback": lambda: bar.setTangent("auto"),
        "menu": _tool_menu_builder(
            "build_tangent_menu",
            tangent_type="auto",
            tangent_label="Auto Tangent",
            icon=icons.tangent_auto,
            maya_default_tangent=True,
        ),
        "tooltip": helper.auto_tangent_tooltip_text,
    },
    "tangent_spline": {
        "type": "tool",
        "label": "Spline Tangent",
        "text": "SP",
        "icon": icons.tangent_spline,
        "callback": lambda: bar.setTangent("spline"),
        "menu": _tool_menu_builder(
            "build_tangent_menu",
            tangent_type="spline",
            tangent_label="Spline Tangent",
            icon=icons.tangent_spline,
            maya_default_tangent=True,
        ),
        "tooltip": helper.spline_tangent_tooltip_text,
    },
    "tangent_clamped": {
        "type": "tool",
        "label": "Clamped Tangent",
        "text": "CL",
        "icon": icons.tangent_clamped,
        "callback": lambda: bar.setTangent("clamped"),
        "menu": _tool_menu_builder(
            "build_tangent_menu",
            tangent_type="clamped",
            tangent_label="Clamped Tangent",
            icon=icons.tangent_clamped,
            maya_default_tangent=True,
        ),
        "tooltip": helper.clamped_tangent_tooltip_text,
    },
    "tangent_linear": {
        "type": "tool",
        "label": "Linear Tangent",
        "text": "LI",
        "icon": icons.tangent_linear,
        "callback": lambda: bar.setTangent("linear"),
        "menu": _tool_menu_builder(
            "build_tangent_menu",
            tangent_type="linear",
            tangent_label="Linear Tangent",
            icon=icons.tangent_linear,
            maya_default_tangent=True,
        ),
        "tooltip": helper.linear_tangent_tooltip_text,
    },
    "tangent_flat": {
        "type": "tool",
        "label": "Flat Tangent",
        "text": "FT",
        "icon": icons.tangent_flat,
        "callback": lambda: bar.setTangent("flat"),
        "menu": _tool_menu_builder(
            "build_tangent_menu",
            tangent_type="flat",
            tangent_label="Flat Tangent",
            icon=icons.tangent_flat,
            maya_default_tangent=True,
        ),
        "tooltip": helper.flat_tangent_tooltip_text,
    },
    "tangent_step": {
        "type": "tool",
        "label": "Step Tangent",
        "text": "ST",
        "icon": icons.tangent_step,
        "callback": lambda: bar.setTangent("step"),
        "menu": _tool_menu_builder(
            "build_tangent_menu",
            tangent_type="step",
            tangent_label="Step Tangent",
            icon=icons.tangent_step,
            maya_default_tangent=True,
        ),
        "tooltip": helper.step_tangent_tooltip_text,
    },
    "tangent_plateau": {
        "type": "tool",
        "label": "Plateau Tangent",
        "text": "PT",
        "icon": icons.tangent_plateau,
        "callback": lambda: bar.setTangent("plateau"),
        "menu": _tool_menu_builder(
            "build_tangent_menu",
            tangent_type="plateau",
            tangent_label="Plateau Tangent",
            icon=icons.tangent_plateau,
            maya_default_tangent=True,
        ),
        "tooltip": helper.plateau_tangent_tooltip_text,
    },
}
TOOL_SECTION_DEFINITIONS = {
    # --- Hotkey/System Tools ---
    "system": {
        "label": "TKM Menu",
        "hiddeable": False,
        "toolbar_ids": ("main",),
        "items": [
            {
                "id": "TKM",
                "default": True
            },
            {"id": "main_preferences_menu", "default": False},
            {"id": "main_dock_menu", "default": False},
            {"id": "main_system_menu", "default": False},
            {"id": "help_menu", "default": False},
            {"id": "toolbar_toggle", "default": False},
            {"id": "toolbar_add_shelf_button", "default": False},
            {"id": "toolbar_reload", "default": False},
            {"id": "toolbar_unload", "default": False},
            {"id": "toolbar_uninstall", "default": False},
            {"id": "check_for_updates", "default": False},
            {"id": "hotkeys_window", "default": False},
            {"id": "about_window", "default": False},
            {"id": "donate_window", "default": False},
            {"id": "bug_report_window", "default": False},
            ],
    },
    # --- Key Editing ---
    "nudge_tools": {
        "label": "Nudge",
        "color": toolColors.TOOLBAR_GREEN,
        "items": [
            {
                "id": "nudge_left",
                "default": True,
                "shortcuts": [
                    {"id": "nudge_remove_inbetween", "keys": [QtCore.Qt.Key_Shift]},
                    {"id": "nudge_left_all_keys", "keys": [QtCore.Qt.Key_Control, QtCore.Qt.Key_Shift]},
                    {"id": "nudge_left_scene", "keys": [QtCore.Qt.Key_Alt, QtCore.Qt.Key_Control, QtCore.Qt.Key_Shift]}
                ],
            },
            {"id": "nudge_remove_inbetween"},
            {
                "id": "nudge_right",
                "default": True,
                "shortcuts": [
                    {"id": "nudge_insert_inbetween", "keys": [QtCore.Qt.Key_Shift]},
                    {"id": "nudge_right_all_keys", "keys": [QtCore.Qt.Key_Control, QtCore.Qt.Key_Shift]},
                    {"id": "nudge_right_scene", "keys": [QtCore.Qt.Key_Alt, QtCore.Qt.Key_Control, QtCore.Qt.Key_Shift]}
                ],
            },
            {"id": "nudge_insert_inbetween"},
            {"id": "nudge_left_all_keys", "default": False},
            {"id": "nudge_left_scene", "default": False},
            {"id": "nudge_right_all_keys", "default": False},
            {"id": "nudge_right_scene", "default": False},
            {"id": "nudge_insert_inbetween_scene", "default": False},
            {"id": "nudge_remove_inbetween_scene", "default": False},
            {"type": "widget", "id": "nudge_value", "default": True},
        ],
    },
    "default_tools": {
        "label": "Default",
        "color": toolColors.TOOLBAR_GREEN,
        "items": [
            {
                "id": "default_object_values",
                "default": True,
                "shortcuts": [
                    {"id": "default_translations", "keys": [QtCore.Qt.Key_Shift]},
                    {"id": "default_rotations", "keys": [QtCore.Qt.Key_Control]},
                    {"id": "default_scales", "keys": [QtCore.Qt.Key_Alt]},
                    {"id": "default_trs", "keys": [QtCore.Qt.Key_Control, QtCore.Qt.Key_Shift]},
                    {"id": "default_set_defaults", "keys": [QtCore.Qt.Key_Alt, QtCore.Qt.Key_Control, QtCore.Qt.Key_Shift]},
                ],
            },
            {"id": "default_translations"},
            {"id": "default_rotations"},
            {"id": "default_scales"},
            {"id": "default_trs"},
            "separator",
            {"id": "default_set_defaults"},
            {"id": "default_restore_defaults"},
            "separator",
            {"id": "default_clear_all"},
            "separator",
            {"id": "default_help"},
        ],
    },
    "bake_tools": {
        "label": "Bake",
        "color": toolColors.TOOLBAR_GREEN,
        "items": [
            {
                "id": "bake_animation_1",
                "default": True,
                "shortcuts": [
                    {"id": "bake_animation_2", "keys": [QtCore.Qt.Key_Control]},
                    {"id": "bake_animation_3", "keys": [QtCore.Qt.Key_Shift]},
                    {"id": "bake_animation_4", "keys": [QtCore.Qt.Key_Control, QtCore.Qt.Key_Shift]},
                    {"id": "bake_animation_custom", "keys": [QtCore.Qt.Key_Alt]},
                    {"id": "bake_animation_from_last_selected", "keys": [QtCore.Qt.Key_Alt, QtCore.Qt.Key_Shift]},
                ],
            },
            {"id": "bake_animation_2"},
            {"id": "bake_animation_3"},
            {"id": "bake_animation_4"},
            {"id": "bake_animation_custom"},
            "separator",
            {"id": "bake_animation_from_last_selected", "default": False},
        ],
    },
    "key_sync_tools": {
        "label": "Key Sync",
        "color": toolColors.TOOLBAR_GREEN,
        "items": [
            {
                "id": "share_keys",
                "default": True,
                "shortcuts": [
                    {"id": "share_keys_from_last_selected", "keys": [QtCore.Qt.Key_Control]},
                    {"id": "reblock", "keys": [QtCore.Qt.Key_Shift]},
                ],
            },
            {"id": "reblock"},
            "separator",
            {"id": "share_keys_from_last_selected", "default": False},
        ],
    },
    "key_selection_tools": {
        "label": "Key Selection",
        "color": toolColors.TOOLBAR_GREEN,
        "items": [
            {"id": "clear_selected_keys"},
            {"id": "select_scene_animation"},
        ],
    },
    "main_key_editing": {
        "label": "Key Editing",
        "color": toolColors.TOOLBAR_GREEN,
        "toolbar": False,
        "items": [
            {"section": "nudge_tools"},
            "separator",
            {"section": "key_sync_tools"},
            {"id": "clear_selected_keys"},
            {"id": "select_scene_animation"},
            "separator",
            {"section": "bake_tools"},
        ],
    },
    # --- Sliders ---
    "slider_blend": {
        "label": "Blend Sliders",
        "color": toolColors.TOOLBAR_GREEN,
        "icon_color": toolColors.SLIDER_ICON_GREEN,
        "type": "slider",
        "slider_type": "blend",
        "modes_attr": "BLEND_MODES",
        "default_modes": ["connect_neighbors"],
    },
    "slider_tween": {
        "label": "Tween Sliders",
        "color": toolColors.TOOLBAR_YELLOW,
        "icon_color": toolColors.SLIDER_ICON_YELLOW,
        "type": "slider",
        "slider_type": "tween",
        "modes_attr": "TWEEN_MODES",
        "default_modes": ["tweener"],
    },
    "slider_tangent": {
        "label": "Tangent Sliders",
        "color": toolColors.TOOLBAR_ORANGE,
        "icon_color": toolColors.SLIDER_ICON_ORANGE,
        "icon": icons.tangent_auto,
        "type": "slider",
        "slider_type": "tangent",
        "modes_attr": "TANGENT_MODES",
        "default_modes": ["blend_best_guess"],
    },
    # --- Scene Tools ---
    "pointer_tools": {
        "label": "Pointer",
        "items": [
            "separator",
            {"id": "depth_mover"},
        ],
    },
    "isolate_tools": {
        "label": "Isolate Tools",
        "items": [
            {
                "id": "isolate_master",
                "default": True,
                "shortcuts": [
                    {"id": "isolate_bookmarks", "keys": [QtCore.Qt.Key_Control]},
                ],
            },
            {"id": "isolate_bookmarks"},
            "separator",
            {"type": "widget", "id": "isolate_down_level"},
            "separator",
            {"id": "isolate_help"},
        ],
    },
    "locator_tools": {
        "label": "Locators",
        "color": toolColors.TOOLBAR_RED,
        "items": [
            {"id": "create_locator", "shortcuts": [
                {"id": "locator_select_temp", "keys": [QtCore.Qt.Key_Control]},
                {"id": "locator_remove_temp", "keys": [QtCore.Qt.Key_Control, QtCore.Qt.Key_Shift, QtCore.Qt.Key_Alt]}]},
            {"id": "locator_select_temp"},
            {"id": "locator_remove_temp"},
        ],
    },
    # --- Selection & Pose ---
    "selector_tools": {
        "label": "Selector",
        "color": toolColors.TOOLBAR_GREEN,
        "items": [
            {"id": "selector"},
            {"id": "select_hierarchy"},
        ],
    },
    "opposite_tools": {
        "label": "Opposite",
        "color": toolColors.TOOLBAR_GREEN,
        "items": [
            {
                "id": "select_opposite",
                "default": True,
                "shortcuts": [
                    {"id": "opposite_add", "keys": [QtCore.Qt.Key_Shift]},
                    {"id": "opposite_copy", "keys": [QtCore.Qt.Key_Alt]},
                ],
            },
            {"id": "opposite_add"},
            {"id": "opposite_copy"},
        ],
    },
    "mirror_tools": {
        "label": "Mirror",
        "color": toolColors.TOOLBAR_GREEN,
        "items": [
            {
                "id": "mirror",
                "default": True,
                "shortcuts": [
                    {"id": "mirror_add_invert", "keys": [QtCore.Qt.Key_Shift]},
                    {"id": "mirror_add_keep", "keys": [QtCore.Qt.Key_Control]},
                    {"id": "mirror_remove_exc", "keys": [QtCore.Qt.Key_Control, QtCore.Qt.Key_Shift]},
                ],
            },
            {"id": "mirror_to_right"},
            {"id": "mirror_to_left"},
            {"id": "mirror_all_keys"},
            "separator",
            {"id": "mirror_add_invert"},
            {"id": "mirror_add_keep"},
            {"id": "mirror_remove_exc"},
            "separator",
            {"id": "mirror_help"},
        ],
    },
    "align_tools": {
        "label": "Align Objects",
        "color": toolColors.TOOLBAR_GREEN,
        "items": [
            {
                "id": "align_objects",
                "default": True,
                "shortcuts": [
                    {
                        "id": "align_objects_all_keys",
                        "label": "Align Objects All Keys",
                        "keys": [QtCore.Qt.Key_Alt],
                    },
                    {"id": "align_object_translation", "keys": [QtCore.Qt.Key_Shift]},
                    {
                        "id": "align_object_translation_all_keys",
                        "label": "Align Object Translation All Keys",
                        "keys": [QtCore.Qt.Key_Alt, QtCore.Qt.Key_Shift],
                    },
                    {"id": "align_object_rotation", "keys": [QtCore.Qt.Key_Control]},
                    {
                        "id": "align_object_rotation_all_keys",
                        "label": "Align Object Rotation All Keys",
                        "keys": [QtCore.Qt.Key_Alt, QtCore.Qt.Key_Control],
                    },
                    {"id": "align_object_scale", "keys": [QtCore.Qt.Key_Control, QtCore.Qt.Key_Shift]},
                    {
                        "id": "align_object_scale_all_keys",
                        "label": "Align Object Scale All Keys",
                        "keys": [QtCore.Qt.Key_Alt, QtCore.Qt.Key_Control, QtCore.Qt.Key_Shift],
                    },
                ],
            },
            {"id": "align_object_translation"},
            {"id": "align_object_rotation"},
            {"id": "align_object_scale"},
            "separator",
            {"id": "align_objects_all_keys"},
            {"id": "align_object_translation_all_keys"},
            {"id": "align_object_rotation_all_keys"},
            {"id": "align_object_scale_all_keys"},
            "separator",
            {"id": "align_objects_help"},
        ],
    },
    "selection_tools": {
        "label": "Selection",
        "color": toolColors.TOOLBAR_GREEN,
        "toolbar": False,
        "items": [
            {"id": "selector"},
            {"section": "opposite_tools"},
            {"section": "mirror_tools"},
            {"id": "select_hierarchy"},
        ],
    },
    "pose_animation_section": {
        "label": "Pose & Animation",
        "color": toolColors.TOOLBAR_GREEN,
        "items": [
            {
                "id": "copy_pose",
                "default": True,
                "shortcuts": [
                    {"id": "paste_pose", "keys": [QtCore.Qt.Key_Control]},
                    {"id": "paste_pose_to", "keys": [QtCore.Qt.Key_Shift]},
                ],
            },
            {"id": "paste_pose"},
            {"id": "paste_pose_to"},
            {"id": "export_pose_file"},
            {"id": "import_pose_file"},
            "separator",
            {
                "id": "copy_animation",
                "default": True,
                "shortcuts": [
                    {"id": "paste_animation", "keys": [QtCore.Qt.Key_Shift]},
                    {"id": "paste_insert_animation", "keys": [QtCore.Qt.Key_Control]},
                    {"id": "paste_opposite_animation", "keys": [QtCore.Qt.Key_Control, QtCore.Qt.Key_Shift]},
                ],
            },
            {"id": "paste_animation"},
            {"id": "paste_insert_animation"},
            {"id": "paste_opposite_animation"},
            {"id": "paste_animation_to"},
            {"id": "export_animation_file"},
            {"id": "import_animation_file"},
        ],
    },
    # --- Tangents ---
    "tangent_buttons": {
        "label": "Tangents",
        "icon": icons.tangent_auto,
        "color": toolColors.TOOLBAR_ORANGE,
        "items": [
            {"id": "tangent_cycle_matcher"},
            {
                "id": "tangent_bouncy",
                "default": True,
                "shortcuts": _tangent_shortcuts(
                    "tangent_bouncy",
                    "bouncy",
                    "Bouncy Tangent",
                    maya_default=False,
                    all_keys_callback=lambda: keyTools.bouncy_tangets(key_scope="all"),
                ),
            },
            "separator",
            {
                "id": "tangent_auto",
                "default": True,
                "shortcuts": _tangent_shortcuts("tangent_auto", "auto", "Auto Tangent"),
            },
            {
                "id": "tangent_spline",
                "default": True,
                "shortcuts": _tangent_shortcuts("tangent_spline", "spline", "Spline Tangent"),
            },
            {
                "id": "tangent_clamped",
                "shortcuts": _tangent_shortcuts("tangent_clamped", "clamped", "Clamped Tangent"),
            },
            {
                "id": "tangent_linear",
                "default": True,
                "shortcuts": _tangent_shortcuts("tangent_linear", "linear", "Linear Tangent"),
            },
            {
                "id": "tangent_flat",
                "shortcuts": _tangent_shortcuts("tangent_flat", "flat", "Flat Tangent"),
            },
            {
                "id": "tangent_step",
                "default": True,
                "shortcuts": _tangent_shortcuts("tangent_step", "step", "Step Tangent"),
            },
            {
                "id": "tangent_plateau",
                "shortcuts": _tangent_shortcuts("tangent_plateau", "plateau", "Plateau Tangent"),
            },
        ],
    },
    "manipulator_tools": {
        "label": "Manipulators",
        "items": [
            {"id": "smart_rotation"},
            {"id": "smart_rotation_release"},
            {"id": "smart_translation"},
            {"id": "smart_translation_release"},
            {"id": "depth_mover"},
        ],
    },
    # --- Special Tools ---
    "animation_offset_tools": {
        "label": "Animation Offset",
        "color": toolColors.TOOLBAR_PURPLE,
        "items": [
            {"id": "animation_offset", "default": True},
        ],
    },
    "micro_move_tools": {
        "label": "Micro Move",
        "color": toolColors.TOOLBAR_PURPLE,
        "items": [
            {"id": "micro_move"},
        ],
    },
    "temp_pivot_tools": {
        "label": "Temp Pivot",
        "color": toolColors.TOOLBAR_PURPLE,
        "items": [
            {
                "id": "temp_pivot",
                "default": True,
                "shortcuts": [
                    {"id": "temp_pivot_reset", "keys": [QtCore.Qt.Key_Alt, QtCore.Qt.Key_Control]},
                    {"id": "temp_pivot_centered", "keys": [QtCore.Qt.Key_Control]},
                    {"id": "temp_pivot_last_object", "keys": [QtCore.Qt.Key_Shift]},
                    {"id": "temp_pivot_worldspace", "keys": [QtCore.Qt.Key_Shift, QtCore.Qt.Key_Control]},
                    {"id": "temp_pivot_edit", "keys": [QtCore.Qt.Key_Alt]},
                ],
            },
            {"id": "temp_pivot_last_object"},
            {"id": "temp_pivot_centered"},
            {"id": "temp_pivot_worldspace"},
            "separator",
            {"id": "temp_pivot_edit"},
            {"id": "temp_pivot_reset"},
            "separator",
            {"id": "temp_pivot_help"},
        ],
    },
    "follow_cam_tools": {
        "label": "Follow Cam",
        "color": toolColors.TOOLBAR_PURPLE,
        "items": [
            {
                "id": "follow_cam",
                "default": True,
                "shortcuts": [
                    {"id": "follow_cam_translation", "keys": [QtCore.Qt.Key_Shift]},
                    {"id": "follow_cam_rotation", "keys": [QtCore.Qt.Key_Control]},
                    {"id": "follow_cam_remove", "keys": [QtCore.Qt.Key_Control, QtCore.Qt.Key_Alt]},
                ],
            },
            {"id": "follow_cam_translation"},
            {"id": "follow_cam_rotation"},
            "separator",
            {"id": "follow_cam_remove"},
        ],
    },
    "special_tools_section": {
        "label": "Special Tools",
        "color": toolColors.TOOLBAR_PURPLE,
        "toolbar": False,
        "items": [
            {"id": "animation_offset"},
            "separator",
            {"id": "micro_move"},
            "separator",
            {"section": "temp_pivot_tools"},
            {"section": "follow_cam_tools"},
        ],
    },
    # --- Links & Worldspace ---
    "link_worldspace_tools": {
        "label": "Links & Worldspace",
        "color": toolColors.TOOLBAR_GREEN,
        "items": [
            {
                "id": "link_copy",
                "default": True,
                "shortcuts": [
                    {"id": "link_paste", "keys": [QtCore.Qt.Key_Control]},
                    {"id": "link_autolink", "keys": [QtCore.Qt.Key_Alt]},
                ],
            },
            {"id": "link_autolink"},
            "separator",
            {"id": "link_paste"},
            "separator",
            {
                "id": "ws_copy_frame",
                "label": "Copy World Space",
                "default": True,
                "shortcuts": [
                    {"id": "ws_paste_frame", "keys": [QtCore.Qt.Key_Control]},
                    {"id": "ws_copy_range", "keys": [QtCore.Qt.Key_Shift]},
                    {"id": "ws_paste", "keys": [QtCore.Qt.Key_Control, QtCore.Qt.Key_Shift]},
                ],
            },
            {"id": "ws_copy_range"},
            "separator",
            {"id": "ws_paste_frame"},
            {"id": "ws_paste"},
        ],
    },
    "attribute_tools": {
        "label": "Attributes Switcher",
        "color": toolColors.TOOLBAR_GREEN,
        "items": [
            {"id": "attribute_switcher", "default": True},
            {"id": "gimbal"},
        ],
    },
    # --- Workspaces & Extensions ---
    "selection_set_tools": {
        "label": "Selection Sets",
        "items": [
            {
                "id": "selection_sets",
                "default": True,
                "shortcuts": [
                    {"id": "selection_sets_quick_export", "keys": [QtCore.Qt.Key_Control]},
                    {"id": "selection_sets_quick_import", "keys": [QtCore.Qt.Key_Control, QtCore.Qt.Key_Shift]},
                    {"id": "selection_sets_export", "keys": [QtCore.Qt.Key_Alt]},
                    {"id": "selection_sets_import", "keys": [QtCore.Qt.Key_Control, QtCore.Qt.Key_Alt]},
                    {"id": "selection_sets_clear_all", "keys": [QtCore.Qt.Key_Control, QtCore.Qt.Key_Alt, QtCore.Qt.Key_Shift]},
                ],
            },
            {"id": "selection_sets_quick_export"},
            {"id": "selection_sets_quick_import"},
            {"id": "selection_sets_export"},
            {"id": "selection_sets_import"},
            {"id": "selection_sets_clear_all"},
        ],
    },
    "orbit_tools": {
        "label": "Orbit",
        "items": [
            {"id": "orbit", "default": True},
        ],
    },
    "tracer_tools": {
        "label": "Tracer",
        "color": toolColors.TOOLBAR_RED,
        "items": [
            {
                "id": "create_tracer",
                "default": True,
                "shortcuts": [
                    {"id": "tracer_refresh", "keys": [QtCore.Qt.Key_Control]},
                    {"id": "tracer_show_hide", "keys": [QtCore.Qt.Key_Shift]},
                    {"id": "tracer_remove", "keys": [QtCore.Qt.Key_Control, QtCore.Qt.Key_Alt]},
                ],
            },
            {"type": "widget", "id": "tracer_connected"},
            "separator",
            {"id": "tracer_refresh"},
            {"id": "tracer_show_hide"},
            {"id": "tracer_offset_node"},
            "separator",
            {"id": "tracer_grey"},
            {"id": "tracer_red"},
            {"id": "tracer_blue"},
            "separator",
            {"id": "tracer_remove"},
        ],
    },
    "global_tools": {
        "label": "Global Tools",
        "toolbar_ids": ("main",),
        "items": [
            {"type": "widget", "id": "attribute_switcher_euler_filter", "default": True},
            {"type": "widget", "id": "overshoot_sliders", "default": True},
            {"type": "widget", "id": "custom_graph", "default": True},
        ],
    },
    "background_runner_tools": {
        "label": "Background Runners",
        "items": [
            {"id": "background_runners", "default": True},
        ],
    },
    "extension_tools": {
        "label": "Extensions",
        "toolbar": True,
        "items": [
            {"id": "custom_tools"},
            {"id": "custom_scripts"},
        ],
    },
    # --- Extra Specific ---
    "extra_tools": {
        "label": "Extra Tools",
        "items": [
            {"id": "graph_extra_tools", "default": True},
            {
                "id": "select_rig_controls",
                "default": True,
                "shortcuts": [{"id": "select_rig_controls_animated", "keys": [QtCore.Qt.Key_Control]}],
            },
            {"id": "select_rig_controls_animated"},
            "separator",
            {"id": "graph_select_object_from_curve"},
            {"id": "graph_isolate_curves"},
            "separator",
            {"id": "graph_flip"},
            {"id": "graph_overlap_forward", "shortcuts": [{"id": "graph_overlap_backward", "keys": [QtCore.Qt.Key_Shift]}]},
            "separator",
            {"id": "graph_toggle_mute"},
            {"id": "graph_toggle_lock"},
            {"id": "graph_match_keys"},
            {
                "id": "enable_graph_filter",
                "shortcuts": [
                    {"id": "disable_graph_filter", "keys": [QtCore.Qt.Key_Control]},
                ],
            },
        ],
    },
    "anim_curve_tools": {
        "label": "Anim Curve Tools",
        "items": [
            {"id": "apply_smart_euler_filter"},
            {"id": "clear_animation"},
            {"id": "copy_keys"},
            {"id": "crop_animation"},
            {"id": "cut_keys"},
            {"id": "delete_keys"},
            {"id": "paste_keys"},
            {"id": "paste_keys_relative"},
            {"id": "remove_redundant_keys"},
            {"id": "remove_static_anim_curves"},
            {"id": "reverse_animation"},
            {"id": "set_smart_key"},
            {"id": "set_smart_key_all_channels"},
            "separator",
            {"id": "snap", "default": True},
        ],
    },
}

TOOLBAR_DEFAULT_SLIDER_MODES = {
    "main": {
        "slider_blend": ["connect_neighbors"],
        "slider_tween": ["tweener"],
        "slider_tangent": [],
    },
    "graph": {
        "slider_blend": ["connect_neighbors"],
        "slider_tween": ["tweener"],
        "slider_tangent": ["blend_best_guess"],
    },
}

def _apply_shortcuts(tool, item):
    shortcut_items = item.get("shortcuts") or []
    if not shortcut_items:
        return tool

    key_masks = (
        (QtCore.Qt.Key_Shift, 1),
        (QtCore.Qt.Key_Control, 4),
        (QtCore.Qt.Key_Alt, 8),
    )

    def shortcut_display(tool_state, keys):
        return {
            "icon": tool_state.get("icon"),
            "label": tool_state.get("label") or tool_state.get("status_title") or tool_state.get("id"),
            "keys": keys,
        }

    def shortcut_mask(keys):
        return sum(mask for key, mask in key_masks if key in (keys or []))

    shortcuts = []
    variants = []
    for index, shortcut_item in enumerate(shortcut_items):
        tool_id = shortcut_item.get("id")
        if not tool_id:
            continue
        overrides = {
            key: value
            for key, value in shortcut_item.items()
            if key not in {"id", "section", "shortcuts", "keys"}
        }
        if shortcut_item.get("callback") is not None:
            variant = dict(tool)
            variant.update(overrides)
            variant["id"] = shortcut_item.get("variant_id") or "{}__shortcut_{}".format(tool.get("id", tool_id), index)
            variant.pop("shortcut_variants", None)
        else:
            variant = get_tool(tool_id, **overrides)
        variant["mask"] = shortcut_mask(shortcut_item.get("keys", []))
        variant.setdefault("shortcuts", [])
        shortcuts.append(shortcut_display(variant, shortcut_item.get("keys", [])))
        variants.append(variant)

    tool["shortcuts"] = shortcuts
    tool["shortcut_variants"] = variants
    return tool


def get_tool(tool_id, **overrides):
    """Retrieve a tool definition with optional overrides."""
    if tool_id not in TOOL_DEFINITIONS:
        raise KeyError("Unknown tool id: {}".format(tool_id))

    tool = dict(TOOL_DEFINITIONS[tool_id])
    tool.update(overrides)
    tool.setdefault("id", tool_id)
    tool.setdefault("default", False)

    callback = tool.get("callback")
    if callback:
        if getattr(callback, "__name__", None) != tool_id:
            tool["callback"] = trigger.make_command_callback(tool_id, callback)
        elif not getattr(callback, "_tkm_trigger_proxy", False):
            trigger.register_command(tool_id, callback)
    elif callable(tool.get("menu")):
        def _show_menu_at_cursor(tid=tool_id):
            from TheKeyMachine.mods import shelfMod

            return shelfMod.show_tool_menu_at_cursor(tid)

        trigger.register_command(tool_id, _show_menu_at_cursor)
    return tool


def get_tool_section(section_id, resolve_items=True, toolbar_id=None):
    section_def = TOOL_SECTION_DEFINITIONS.get(section_id)
    if not section_def:
        return None

    section = dict(section_def)
    section["id"] = section_id
    section.setdefault("color", toolColors.TOOLBAR_GRAY)
    if toolbar_id and section.get("type") == "slider":
        section["default_modes"] = list(TOOLBAR_DEFAULT_SLIDER_MODES.get(toolbar_id, {}).get(section_id, []))
    if not resolve_items:
        section["items"] = list(section_def.get("items", []))
        return section

    resolved = []
    for item in section_def.get("items", []):
        if isinstance(item, str):
            resolved.append(item)
            continue
        section_ref = item.get("section")
        if section_ref:
            nested = get_tool_section(section_ref, toolbar_id=toolbar_id)
            if nested:
                resolved.append({"type": "group", "items": nested.get("items", []), "label": nested.get("label")})
            continue
        tool_id = item.get("id")
        if not tool_id:
            continue
        overrides = {key: value for key, value in item.items() if key not in {"id", "section", "shortcuts"}}
        resolved.append(_apply_shortcuts(get_tool(tool_id, **overrides), item))
    section["items"] = resolved
    return section


def get_section_icon(section_id):
    section = get_tool_section(section_id, toolbar_id="main")
    if not section:
        return None
    if section.get("icon"):
        return section.get("icon")

    def find_icon(items):
        for item in items:
            if item == "separator" or not isinstance(item, dict):
                continue
            if item.get("type") == "group":
                icon = find_icon(item.get("items", []))
                if icon:
                    return icon
                continue
            icon = item.get("icon")
            if icon:
                return icon
        return None

    return find_icon(section.get("items", []))


def get_tool_tint_color(tool_id, default=None):
    def find_tint(item, inherited_color=None):
        if item == "separator" or item is None:
            return None
        if not isinstance(item, dict):
            return None

        section_ref = item.get("section")
        if section_ref:
            section = TOOL_SECTION_DEFINITIONS.get(section_ref)
            if not section:
                return None
            section_color = section.get("color", toolColors.TOOLBAR_GRAY)
            for child in section.get("items", []):
                color = find_tint(child, inherited_color=section_color)
                if color is not None:
                    return color
            return None

        if item.get("id") == tool_id:
            return inherited_color

        for shortcut in item.get("shortcuts") or []:
            color = find_tint(shortcut, inherited_color=inherited_color)
            if color is not None:
                return color
        return None

    for section in TOOL_SECTION_DEFINITIONS.values():
        section_color = section.get("color", toolColors.TOOLBAR_GRAY)
        for item in section.get("items", []):
            color = find_tint(item, inherited_color=section_color)
            if color is not None:
                return color
    return default


def get_toolbar_sections(layout_id, resolve_items=True):
    if layout_id not in ("main", "graph"):
        return []
    section_ids = [
        section_id
        for section_id, definition in TOOL_SECTION_DEFINITIONS.items()
        if not definition.get("hotkeys")
        and definition.get("toolbar") is not False
        and layout_id in definition.get("toolbar_ids", ("main", "graph"))
    ]
    return [
        section
        for section in (
            get_tool_section(section_id, resolve_items=resolve_items, toolbar_id=layout_id)
            for section_id in section_ids
        )
        if section is not None
    ]
