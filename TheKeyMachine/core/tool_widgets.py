"""
Shared toolbar widget factories.

This module handles toolbox entries whose descriptor is a widget or a
settings-backed check button, so the main toolbar and Graph Editor toolbar
build the same controls from the same definitions.
"""

import TheKeyMachine.mods.settingsMod as settings  # type: ignore
import TheKeyMachine.core.runtime_manager as runtime  # type: ignore
import TheKeyMachine.tools.attribute_switcher.api as attributeSwitcherApi  # type: ignore
import TheKeyMachine.tools.graph_toolbar.api as graphToolbarApi  # type: ignore
from TheKeyMachine.tools import common as toolCommon  # type: ignore
from TheKeyMachine.widgets import customWidgets as cw  # type: ignore
from TheKeyMachine.widgets import util as wutil  # type: ignore


def setting_toggle_specs():
    manager = runtime.get_runtime_manager()

    def _get_overshoot():
        return settings.get_setting("sliders_overshoot", False)

    def _set_overshoot(state):
        settings.set_setting("sliders_overshoot", bool(state))
        manager.overshootChanged.emit(bool(state))

    def _get_euler_filter():
        return attributeSwitcherApi.get_attribute_switcher_euler_filter_enabled()

    def _set_euler_filter(state):
        attributeSwitcherApi.set_attribute_switcher_euler_filter_enabled(bool(state))

    def _set_graph_toolbar(state):
        graphToolbarApi.set_graph_toolbar_enabled(bool(state), apply=True)

    behaviors = {
        "overshoot_sliders": {
            "get_checked": _get_overshoot,
            "set_checked": _set_overshoot,
            "changed_signal": manager.overshootChanged,
        },
        "attribute_switcher_euler_filter": {
            "get_checked": _get_euler_filter,
            "set_checked": _set_euler_filter,
            "changed_signal": manager.eulerFilterChanged,
        },
        "custom_graph": {
            "get_checked": graphToolbarApi.get_graph_toolbar_checkbox_state,
            "set_checked": _set_graph_toolbar,
            "changed_signal": graphToolbarApi.custom_graph_bus.graph_toolbar_enabled_changed,
        },
    }

    specs = {}
    import TheKeyMachine.core.toolbox as toolbox

    for tool_id, behavior in behaviors.items():
        tool = toolbox.get_tool(tool_id)
        if not tool.get("setting_toggle"):
            continue
        spec = {
            "key": tool.get("key", tool_id),
            "label": tool.get("label", tool_id),
            "menu_label": tool.get("menu_label") or tool.get("label", tool_id),
            "text": tool.get("text"),
            "icon": tool.get("icon"),
            "description": tool.get("description", ""),
            "tooltip_template": tool.get("tooltip_template"),
        }
        spec.update(behavior)
        specs[tool_id] = spec
    return specs


def bind_setting_toggle(widget, spec):
    widget.setCheckable(True)
    sync_setting_toggle(widget, spec)

    def _sync(_enabled=None, w=widget, s=spec):
        if w is None or not wutil.is_valid_widget(w):
            return
        toolCommon.set_checked_safely(w, s["get_checked"]())

    signal = spec.get("changed_signal")
    if signal is not None:
        toolCommon.replace_tracked_connection(
            widget,
            "_tkm_setting_toggle_sync_relay",
            signal,
            _sync,
            parent=widget,
        )


def sync_setting_toggle(widget, spec):
    toolCommon.set_checked_safely(widget, spec["get_checked"]())


def create_widget_from_data(section, item_data, owner=None):
    widget_key = item_data.get("key") or item_data.get("id")

    if widget_key == "nudge_value":
        widget = cw.QFlatSpinBox()
        widget.setFixedWidth(wutil.DPI(50))
        section.addWidget(
            widget,
            item_data.get("label", "Nudge Value"),
            widget_key,
            default=item_data.get("default", True),
            tooltip_template=item_data.get("tooltip_template"),
        )
        if owner is not None:
            owner.move_keyframes_intField = widget
        return widget

    spec = setting_toggle_specs().get(widget_key)
    if not spec:
        return None

    resolved = dict(spec)
    resolved.update({k: v for k, v in item_data.items() if k not in {"id", "type"}})

    data = {
        "key": resolved["key"],
        "label": resolved["label"],
        "text": resolved.get("text"),
        "icon": resolved.get("icon"),
        "description": resolved.get("description", ""),
        "tooltip_template": resolved.get("tooltip_template"),
        "checkable": True,
        "set_checked_fn": spec["get_checked"],
        "bind_checked_fn": lambda widget, s=spec: bind_setting_toggle(widget, s),
        "callback": spec["set_checked"],
    }
    btn = cw.create_tool_button_from_data(data)
    section.addWidget(btn, data["label"], data["key"], default=resolved.get("default", True))
    return btn
