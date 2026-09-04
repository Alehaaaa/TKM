"""Background-runner command adapters."""

from TheKeyMachine.tools.background_runners import service as background_runners


def toggle_channelbox_selection_highlight(*_args):
    return background_runners.toggle_channelbox_selection_highlight()


def toggle_channelbox_clear_on_selection_change(*_args):
    return background_runners.toggle_channelbox_clear_on_selection_change()


def toggle_camera_orbit_selection(*_args):
    return background_runners.toggle_camera_orbit_selection()


def toggle_hide_static_animation_curves(*_args):
    return background_runners.toggle_hide_static_animation_curves()


def toggle_animation_recovery(*_args):
    return background_runners.toggle_animation_recovery()


def toggle_anim_layer_weights(*_args):
    return background_runners.toggle_anim_layer_weights()


def toggle_selector_toolbar_pin(*_args):
    return background_runners.toggle_selector_toolbar_pin()


def toggle_pause_viewport_auto(*_args):
    return background_runners.toggle_pause_viewport_auto()


def set_pause_viewport_auto(enabled, *_args):
    return background_runners.set_runner_enabled(
        background_runners.AUTO_PAUSE_VIEWPORT_ID, enabled
    )


def turn_all_off(*_args):
    return background_runners.turn_all_runners_off()


def restore_defaults(*_args):
    return background_runners.restore_runner_defaults()
