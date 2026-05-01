"""
Shared toolbar widget factories.

This module handles toolbox entries whose descriptor is a widget or a
settings-backed check button, so the main toolbar and Graph Editor toolbar
build the same controls from the same definitions.
"""

import TheKeyMachine.mods.settingsMod as settings  # type: ignore
import TheKeyMachine.core.trigger as trigger  # type: ignore
import TheKeyMachine.core.runtime_manager as runtime  # type: ignore
import TheKeyMachine.tools.attribute_switcher.api as attributeSwitcherApi  # type: ignore
import TheKeyMachine.tools.graph_toolbar.api as graphToolbarApi  # type: ignore
from TheKeyMachine.tools import common as toolCommon  # type: ignore
import TheKeyMachine.sliders as sliders  # type: ignore
from TheKeyMachine.widgets import sliderWidget as sw  # type: ignore
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
            "id": tool.get("id", tool_id),
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


def add_tool_button(section, item_data, *, overrides=None):
    data = dict(item_data)
    if overrides:
        data.update(overrides)
    tool_id = item_key(data)
    btn = cw.create_tool_button_from_data(data)
    section.addWidget(
        btn,
        data.get("label", ""),
        tool_id or "",
        default=data.get("default", True),
        description=data.get("description"),
        tooltip_template=data.get("tooltip_template"),
        pinnable=data.get("pinnable", True),
    )
    return btn


def item_key(item_data):
    if not isinstance(item_data, dict):
        return None
    return item_data.get("id")


def is_widget_item(item_data):
    return isinstance(item_data, dict) and item_data.get("type") == "widget"


def is_group_item(item_data):
    return isinstance(item_data, dict) and item_data.get("type") == "group"


def is_action_item(item_data):
    if not isinstance(item_data, dict):
        return False
    return item_data.get("type") not in {"widget", "group"}


def section_should_use_group_menu(section_def, items, *, special_keys=None):
    if section_def.get("hiddeable", True) is False:
        return False
    if any(is_group_item(item) for item in items):
        return False

    special_keys = set(special_keys or ())
    item_keys = {item_key(item) for item in items if isinstance(item, dict)}
    if item_keys & special_keys:
        return False
    if any(isinstance(item, dict) and callable(item.get("menu")) for item in items):
        return False

    action_items = [
        item
        for item in items
        if is_action_item(item) and item.get("pinnable", True) is not False
    ]
    return (
        any(item == "separator" for item in items)
        or any(isinstance(item, dict) and item.get("shortcuts") for item in items)
        or len(action_items) > 1
    )


def add_section_items(section, items, *, add_tool_item_fn, add_widget_item_fn, add_group_items_fn=None):
    """Render a resolved toolbox item list in descriptor order."""
    group_renderer = add_group_items_fn or (
        lambda nested_section, nested_items: add_grouped_section_items(
            nested_section,
            nested_items,
            add_widget_item_fn=add_widget_item_fn,
        )
    )

    for item in items:
        if item == "separator":
            section.addSeparator()
            continue
        if not isinstance(item, dict):
            continue
        if is_widget_item(item):
            add_widget_item_fn(section, item)
            continue
        if is_group_item(item):
            group_renderer(section, item.get("items", []))
            continue
        add_tool_item_fn(section, item)


def add_grouped_section_items(section, items, *, add_widget_item_fn, add_group_items_fn=None):
    """
    Render a section as grouped action buttons while keeping widget descriptors in order.

    Contiguous action descriptors become one shared right-click menu. Widget descriptors
    are inserted where they appear in the toolbox definition, so sections such as Nudge,
    Isolate, and Tracer do not drift into bespoke ordering rules.
    """
    group_run = []

    def flush_group_run():
        if not group_run:
            return
        while group_run and group_run[0] == "separator":
            section.addSeparator()
            group_run.pop(0)
        if group_run:
            section.addWidgetGroup(list(group_run))
        group_run[:] = []

    group_renderer = add_group_items_fn or (
        lambda nested_section, nested_items: add_grouped_section_items(
            nested_section,
            nested_items,
            add_widget_item_fn=add_widget_item_fn,
        )
    )

    for item in items:
        if is_widget_item(item):
            flush_group_run()
            add_widget_item_fn(section, item)
            continue
        if is_group_item(item):
            flush_group_run()
            group_renderer(section, item.get("items", []))
            continue
        group_run.append(item)

    flush_group_run()


def add_slider_section(section, section_def, *, namespace, object_prefix):
    section.set_settings_namespace(namespace)
    section.set_persist_slider_modes(False)

    prefix = section_def["slider_type"]
    color = section_def["color"]
    modes = getattr(sliders, section_def["modes_attr"])
    default_keys = [f"{prefix}_{key}" for key in section_def.get("default_modes", [])]

    for mode in modes:
        if mode == "separator":
            section.addSeparator()
            continue
        if not isinstance(mode, dict):
            continue

        key = mode["key"]
        label = mode["label"]
        desc = mode.get("description", "")
        is_visible = settings.get_setting(
            f"pin_{prefix}_{key}",
            f"{prefix}_{key}" in default_keys,
            namespace=namespace,
        )

        slider = sw.QFlatSliderWidget(
            f"{object_prefix}_{prefix}_{key}",
            min=-100,
            max=100,
            text=mode.get("icon", "SL"),
            color=color,
            dragCommand=lambda mode_key, value, p=prefix, session=None: trigger.execute_slider(p, mode_key, value, session=session),
            tooltipTitle=label,
            tooltipDescription=desc,
        )
        slider.setModes(modes)
        slider.setCurrentMode(key)

        def make_mode_setter(slider_instance):
            def setter(new_mode, temporary=False):
                slider_instance.setCurrentMode(new_mode, temporary=temporary)
                mode_info = next((item for item in modes if isinstance(item, dict) and item["key"] == new_mode), None)
                if mode_info:
                    slider_instance.setTooltipInfo(mode_info["label"], mode_info.get("description", ""))
                if not temporary:
                    slider_instance.startFlash()

            return setter

        slider.modeRequested.connect(make_mode_setter(slider))
        section.addWidget(slider, label, f"{prefix}_{key}", default=is_visible, description=desc)

    section.add_final_actions(default_keys)
    return section


def create_widget_from_data(section, item_data, owner=None):
    widget_key = item_key(item_data)

    if widget_key == "nudge_value":
        widget = cw.QFlatSpinBox()
        widget.setFixedWidth(wutil.DPI(50))

        initial_value = settings.get_setting("nudge_value", 1)
        widget.setValue(initial_value)

        manager = runtime.get_runtime_manager()

        def _on_value_changed(val):
            settings.set_setting("nudge_value", val)
            manager.nudgeValueChanged.emit(val)

        widget.valueChanged.connect(_on_value_changed)

        def _sync_value(val, w=widget):
            if wutil.is_valid_widget(w):
                blocked = w.blockSignals(True)
                w.setValue(val)
                w.blockSignals(blocked)

        toolCommon.replace_tracked_connection(
            widget,
            "_tkm_nudge_value_sync",
            manager.nudgeValueChanged,
            _sync_value,
            parent=widget,
        )

        section.addWidget(
            widget,
            item_data.get("label", "Nudge Value"),
            widget_key,
            default=item_data.get("default", True),
            description=item_data.get("description"),
            tooltip_template=item_data.get("tooltip_template"),
            pinnable=item_data.get("pinnable", True),
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
        "id": resolved["id"],
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
    section.addWidget(
        btn,
        data["label"],
        data["id"],
        default=resolved.get("default", True),
        description=data.get("description"),
        tooltip_template=data.get("tooltip_template"),
        pinnable=resolved.get("pinnable", True),
    )
    return btn
