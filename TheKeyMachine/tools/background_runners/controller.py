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


def toggle_animation_recovery(*_args):
    return backgroundRunners.toggle_animation_recovery()


def toggle_anim_layer_weights(*_args):
    return backgroundRunners.toggle_anim_layer_weights()


def turn_all_off(*_args):
    return backgroundRunners.turn_all_runners_off()


def restore_defaults(*_args):
    return backgroundRunners.restore_runner_defaults()
