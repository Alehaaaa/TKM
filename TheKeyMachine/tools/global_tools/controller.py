"""State adapters for settings that affect TKM globally."""

from TheKeyMachine.core import runtime
from TheKeyMachine.core import settings


def _attribute_switcher_api():
    from TheKeyMachine.tools.attribute_switcher import api

    return api


def _graph_toolbar_controller():
    from TheKeyMachine.tools.graph_toolbar import controller

    return controller


def is_euler_filter_enabled():
    return _attribute_switcher_api().is_euler_filter_enabled()


def set_euler_filter_enabled(enabled):
    return _attribute_switcher_api().set_euler_filter_enabled(bool(enabled))


def toggle_euler_filter():
    state = not is_euler_filter_enabled()
    set_euler_filter_enabled(state)
    return state


def is_overshoot_enabled():
    return bool(settings.get_setting("sliders_overshoot", False))


def set_overshoot_enabled(enabled):
    state = bool(enabled)
    settings.set_setting("sliders_overshoot", state)
    manager = runtime.get_runtime_manager()
    manager.overshootChanged.emit(state)
    manager.set_tool_state("overshoot_sliders", state)
    return state


def toggle_overshoot_sliders():
    return set_overshoot_enabled(not is_overshoot_enabled())


def is_graph_toolbar_enabled():
    return _graph_toolbar_controller().get_graph_toolbar_checkbox_state()


def set_graph_toolbar_enabled(enabled):
    return _graph_toolbar_controller().set_graph_toolbar_enabled(bool(enabled), apply=True)


def toggle_graph_toolbar():
    return set_graph_toolbar_enabled(not is_graph_toolbar_enabled())


def get_setting_spec(setting_id):
    manager = runtime.get_runtime_manager(start=False)
    if setting_id == "smart_euler_filter":
        return {
            "get_checked": is_euler_filter_enabled,
            "set_checked": set_euler_filter_enabled,
            "changed_signal": manager.eulerFilterChanged,
        }
    if setting_id == "overshoot_sliders":
        return {
            "get_checked": is_overshoot_enabled,
            "set_checked": set_overshoot_enabled,
            "changed_signal": manager.overshootChanged,
        }
    if setting_id == "custom_graph":
        graph_controller = _graph_toolbar_controller()
        return {
            "get_checked": is_graph_toolbar_enabled,
            "set_checked": set_graph_toolbar_enabled,
            "changed_signal": graph_controller.custom_graph_bus.graph_toolbar_enabled_changed,
        }
    raise KeyError("Unknown global setting: {}".format(setting_id))
