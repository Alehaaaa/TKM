"""Background-runner command adapters."""

from TheKeyMachine.core import backgroundRunners


def toggle_channelbox_selection_highlight(*_args):
    return backgroundRunners.toggle_channelbox_selection_highlight()


def toggle_channelbox_clear_on_selection_change(*_args):
    return backgroundRunners.toggle_channelbox_clear_on_selection_change()


def toggle_camera_orbit_selection(*_args):
    return backgroundRunners.toggle_camera_orbit_selection()


def toggle_hide_static_animation_curves(*_args):
    return backgroundRunners.toggle_hide_static_animation_curves()
