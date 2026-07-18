"""Public entry point for application-wide toolbar settings."""

from TheKeyMachine.tools.global_tools import controller


def toggle_euler_filter(*_args):
    return controller.toggle_euler_filter()


def toggle_overshoot_sliders(*_args):
    return controller.toggle_overshoot_sliders()


def toggle_graph_toolbar(*_args):
    return controller.toggle_graph_toolbar()


def get_setting_spec(setting_id):
    return controller.get_setting_spec(setting_id)
