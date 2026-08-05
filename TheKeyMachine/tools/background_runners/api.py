"""Public entry point for background-runner toggles."""

from TheKeyMachine.tools.background_runners import controller


def build_menu(menu, source_widget=None):
    from TheKeyMachine.tools.background_runners import widgets

    return widgets.build_menu(menu, source_widget=source_widget)


def show_menu(*_args):
    from TheKeyMachine.mods import shelfMod

    return shelfMod.show_tool_menu_at_cursor("background_runners")


def toggle_channelbox_selection_highlight(*args):
    return controller.toggle_channelbox_selection_highlight(*args)


def toggle_channelbox_clear_on_selection_change(*args):
    return controller.toggle_channelbox_clear_on_selection_change(*args)


def toggle_camera_orbit_selection(*args):
    return controller.toggle_camera_orbit_selection(*args)


def toggle_hide_static_animation_curves(*args):
    return controller.toggle_hide_static_animation_curves(*args)


def toggle_animation_recovery(*args):
    return controller.toggle_animation_recovery(*args)


def toggle_anim_layer_weights(*args):
    return controller.toggle_anim_layer_weights(*args)


def turn_all_off(*args):
    return controller.turn_all_off(*args)


def restore_defaults(*args):
    return controller.restore_defaults(*args)
