"""
Shared toolbar widget factories.

This module handles toolbox entries whose descriptor is a widget or a
settings-backed check button, so the main toolbar and Graph Editor toolbar
build the same controls from the same definitions.
"""

import TheKeyMachine.mods.settingsMod as settings  # type: ignore
import TheKeyMachine.mods.generalMod as general  # type: ignore
import TheKeyMachine.mods.keyToolsMod as keyTools  # type: ignore
from TheKeyMachine.data import icons
import TheKeyMachine.mods.updater as updater  # type: ignore
import TheKeyMachine.core.trigger as trigger  # type: ignore
import TheKeyMachine.mods.selectionMod as selectionMod  # type: ignore
import TheKeyMachine.core.runtimeManager as runtime  # type: ignore
import TheKeyMachine.core.toolMenus as toolMenus  # type: ignore
import TheKeyMachine.tools.attribute_switcher.api as attributeSwitcherApi  # type: ignore
import TheKeyMachine.tools.graph_toolbar.api as graphToolbarApi  # type: ignore
import TheKeyMachine.tools.orbit.api as orbitApi  # type: ignore
import TheKeyMachine.tools.selection_sets.api as selectionSetsApi  # type: ignore
from TheKeyMachine.tools import common as toolCommon  # type: ignore
from TheKeyMachine.tools.link_objects.pulse_thread import LinkObjectPulseThread  # type: ignore
import TheKeyMachine.sliders as sliders  # type: ignore
from TheKeyMachine.widgets import sliderWidget as sw  # type: ignore
from TheKeyMachine.widgets import customWidgets as cw  # type: ignore
from TheKeyMachine.widgets import util as wutil  # type: ignore
from TheKeyMachine.mods.tooltipsMod import QFlatTooltipManager

try:
    from PySide6 import QtCore, QtGui, QtWidgets  # type: ignore
    from shiboken6 import isValid  # type: ignore
except ImportError:
    from PySide2 import QtCore, QtGui, QtWidgets  # type: ignore
    from shiboken2 import isValid  # type: ignore


MAIN_SPECIAL_TOOL_KEYS = {
    "animation_offset",
    "micro_move",
    "orbit",
    "selection_sets",
    "attribute_switcher",
    "custom_graph",
    "selector",
    "settings",
}

GRAPH_SPECIAL_TOOL_KEYS = {
    "orbit",
    "selection_sets",
    "attribute_switcher",
    "custom_graph",
    "selector",
    "settings",
}


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

    signal = spec.get("changed_signal")
    if signal is not None:
        def _sync_setting_toggle(*_args, target=widget, toggle_spec=spec):
            sync_setting_toggle(target, toggle_spec)

        signal.connect(_sync_setting_toggle)
        _retain_setting_toggle_slot(widget, _sync_setting_toggle)
        destroyed = getattr(widget, "destroyed", None)
        if destroyed is not None:
            def _disconnect_sync(*_args, source_signal=signal, source_slot=_sync_setting_toggle):
                _disconnect_setting_toggle_signal(source_signal, source_slot)

            destroyed.connect(_disconnect_sync)
            _retain_setting_toggle_slot(widget, _disconnect_sync)


def sync_setting_toggle(widget, spec):
    if not _is_valid_setting_toggle_target(widget):
        return False
    return toolCommon.set_checked_safely(widget, spec["get_checked"]())


def _is_valid_setting_toggle_target(widget):
    if widget is None:
        return False
    try:
        return bool(isValid(widget))
    except Exception:
        return False


def _disconnect_setting_toggle_signal(signal, slot):
    try:
        signal.disconnect(slot)
    except Exception:
        pass


def _retain_setting_toggle_slot(widget, slot):
    slots = getattr(widget, "_tkm_setting_toggle_slots", [])
    slots.append(slot)
    widget._tkm_setting_toggle_slots = slots


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


def add_selector_button(section, item_data):
    import TheKeyMachine.core.toolbox as toolbox

    selector_tool = toolbox.get_tool("selector", **{k: v for k, v in item_data.items() if k not in {"id", "shortcuts"}})
    btn = cw.QFlatSelectorButton(
        icon=selector_tool.get("icon"),
        tooltip_template=selector_tool.get("tooltip_template"),
        description=selector_tool.get("description"),
    )

    callback = selector_tool.get("callback")
    if callback:

        def _clicked_cb(*_args, cb=callback, b=btn):
            return b.triggerToolCallback(cb)

        btn.clicked.connect(_clicked_cb)

    section.addWidget(
        btn,
        selector_tool.get("label", "Selector"),
        selector_tool.get("id", "selector"),
        default=selector_tool.get("default", True),
        description=selector_tool.get("description"),
        tooltip_template=selector_tool.get("tooltip_template"),
        pinnable=selector_tool.get("pinnable", True),
    )

    def update_selector_button_text(*_args, button=btn):
        if not wutil.is_valid_widget(button):
            return
        button.setCount(selectionMod.get_selected_object_count())

    toolCommon.replace_tracked_connection(
        btn,
        "_tkm_selector_count_sync",
        runtime.get_runtime_manager().selection_changed,
        update_selector_button_text,
        parent=btn,
    )
    update_selector_button_text()
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

    if widget_key == "selector":
        return add_selector_button(section, item_data)

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


def add_animation_offset_button(section, item_data, owner):
    import TheKeyMachine.core.toolbox as toolbox

    tool = toolbox.get_tool("animation_offset", **{k: v for k, v in item_data.items() if k != "id"})
    btn = cw.create_tool_button_from_data(tool)
    btn.setObjectName("anim_offset_button")
    btn.setCheckable(True)
    btn.setChecked(bool(getattr(owner, "toggleAnimOffsetButtonState", False)))
    owner.animation_offset_button_widget = btn
    section.addWidget(
        btn,
        tool.get("label", "Anim Offset"),
        tool.get("id", "animation_offset"),
        default=tool.get("default", True),
        description=tool.get("description"),
        tooltip_template=tool.get("tooltip_template"),
        pinnable=tool.get("pinnable", True),
    )
    return btn


def add_micro_move_button(section, item_data, owner):
    import TheKeyMachine.core.toolbox as toolbox

    tool = toolbox.get_tool("micro_move", **{k: v for k, v in item_data.items() if k != "id"})
    btn = cw.create_tool_button_from_data(tool)
    btn.setObjectName("micro_move_button")
    btn.setCheckable(True)
    btn.setChecked(owner.micro_move_controller.is_enabled())
    section.addWidget(
        btn,
        tool.get("label", "Micro Move"),
        tool.get("id", "micro_move"),
        default=tool.get("default", True),
        description=tool.get("description"),
        tooltip_template=tool.get("tooltip_template"),
        pinnable=tool.get("pinnable", True),
    )
    return btn


def add_setting_toggle_widget(section, item_data, spec_key, owner=None):
    data = dict(item_data)
    data["id"] = spec_key
    return create_widget_from_data(section, data, owner=owner)


def add_bound_tool_button(section, item_data, bind_fn):
    btn = add_tool_button(section, item_data, overrides={"callback": None})
    bind_fn(btn)
    return btn


def create_main_widget_from_data(section, item_data, owner):
    widget_key = item_key(item_data)
    if widget_key == "nudge_value":
        return create_widget_from_data(section, item_data, owner=owner)
    if widget_key == "selector":
        return add_selector_button(section, item_data)
    if widget_key == "animation_offset":
        return add_animation_offset_button(section, item_data, owner)
    if widget_key == "micro_move":
        return add_micro_move_button(section, item_data, owner)
    if widget_key == "custom_graph":
        return add_setting_toggle_widget(section, item_data, "custom_graph", owner=owner)
    return create_widget_from_data(section, item_data, owner=owner)


def add_main_tool_item(section, item_data, owner):
    key = item_key(item_data)
    if key == "selector":
        return add_selector_button(section, item_data)
    if key == "animation_offset":
        return add_animation_offset_button(section, item_data, owner)
    if key == "micro_move":
        return add_micro_move_button(section, item_data, owner)
    if key == "custom_graph":
        return add_setting_toggle_widget(section, item_data, "custom_graph", owner=owner)
    if key == "settings":
        return add_main_settings_button(section, item_data, owner)
    if key == "orbit":
        owner.orbit_button_widget = add_bound_tool_button(section, item_data, orbitApi.bind_orbit_toolbar_button)
        return owner.orbit_button_widget
    if key == "selection_sets":
        return add_bound_tool_button(
            section,
            item_data,
            lambda btn: selectionSetsApi.bind_selection_sets_toolbar_button(
                btn,
                controller=getattr(owner, "selection_sets_controller", None),
            ),
        )
    if key == "attribute_switcher":
        return add_bound_tool_button(section, item_data, attributeSwitcherApi.bind_attribute_switcher_toolbar_button)
    return add_tool_button(section, item_data)


def add_main_group_items(section, items, owner):
    return add_grouped_section_items(
        section,
        items,
        add_widget_item_fn=lambda nested_section, item: create_main_widget_from_data(nested_section, item, owner),
        add_group_items_fn=lambda nested_section, group_items: add_main_group_items(nested_section, group_items, owner),
    )


def add_link_tools_group(section, group_data, owner):
    owner.link_checkbox_state = settings.get_setting("link_checkbox_state", False)
    owner.link_obj_toggle_state = False
    link_btn_placeholder = []

    def pulse_link_obj_button(btn):
        if not wutil.is_valid_widget(owner):
            return
        owner.link_obj_toggle_state = not owner.link_obj_toggle_state
        new_image = icons.link_relative_on if owner.link_obj_toggle_state else icons.link_relative
        btn.setIcon(QtGui.QIcon(new_image))

    def start_link_obj_pulse(btn):
        if getattr(owner, "link_obj_pulse_thread", None):
            try:
                owner.link_obj_pulse_thread.stop()
                owner.link_obj_pulse_thread.wait(500)
            except (RuntimeError, ValueError, TypeError, AttributeError, KeyError, IndexError):
                pass
        owner.link_obj_pulse_thread = LinkObjectPulseThread(interval_seconds=0.3, parent=owner)
        owner.link_obj_pulse_thread.tick.connect(lambda: pulse_link_obj_button(btn))
        owner.link_obj_pulse_thread.start()

    def stop_link_obj_pulse():
        if getattr(owner, "link_obj_pulse_thread", None):
            try:
                owner.link_obj_pulse_thread.stop()
                owner.link_obj_pulse_thread.wait(500)
            except (RuntimeError, ValueError, TypeError, AttributeError, KeyError, IndexError):
                pass
            owner.link_obj_pulse_thread = None

    def toggle_auto_link_callback(state, btn):
        owner.link_checkbox_state = state
        settings.set_setting("link_checkbox_state", owner.link_checkbox_state)
        if owner.link_checkbox_state:
            start_link_obj_pulse(btn)
            keyTools.add_link_obj_callbacks()
        else:
            stop_link_obj_pulse()
            keyTools.remove_link_obj_callbacks()
            QtCore.QTimer.singleShot(800, lambda: btn.setIcon(QtGui.QIcon(icons.link_relative)))

    resolved_items = []
    for item in group_data["items"]:
        if isinstance(item, dict):
            item = dict(item)
            if item_key(item) == "link_autolink":
                item["callback"] = lambda state: toggle_auto_link_callback(state, link_btn_placeholder[0])
                item["set_checked_fn"] = lambda: owner.link_checkbox_state
        resolved_items.append(item)

    btn_group = section.addWidgetGroup(resolved_items)
    if btn_group:
        link_btn_placeholder.append(btn_group)
        if owner.link_checkbox_state:
            start_link_obj_pulse(btn_group)
            keyTools.add_link_obj_callbacks()
    return btn_group


def add_slider_section_from_data(section_def, new_section_fn, *, namespace, object_prefix, color=None):
    kwargs = {}
    if color is not None:
        kwargs["color"] = color
    section = new_section_fn(**kwargs)
    return add_slider_section(
        section,
        section_def,
        namespace=namespace,
        object_prefix=object_prefix,
    )


def populate_main_toolbar_from_layout(layout_id, new_section_fn, owner):
    import TheKeyMachine.core.toolbox as toolbox

    sections = toolbox.get_toolbar_sections(layout_id, resolve_items=False)
    for section_def in sections:
        sec_id = section_def["id"]

        if section_def.get("type") == "slider":
            section = add_slider_section_from_data(
                section_def,
                new_section_fn,
                namespace="main_toolbar_sliders",
                object_prefix="bar",
            )
            if section:
                section.set_menu_identity(section_def.get("label"), toolbox.get_section_icon(section_def["id"]))
            continue

        section = new_section_fn(
            color=section_def.get("color"),
            hiddeable=section_def.get("hiddeable", True),
        )
        section.set_menu_identity(section_def.get("label"), toolbox.get_section_icon(sec_id))
        resolved_section = toolbox.get_tool_section(sec_id, toolbar_id="main")

        if sec_id == "link_tools":
            add_link_tools_group(section, {"items": resolved_section["items"]}, owner)
            continue

        if section_should_use_group_menu(section_def, resolved_section["items"], special_keys=MAIN_SPECIAL_TOOL_KEYS):
            add_main_group_items(section, resolved_section["items"], owner)
            continue

        add_section_items(
            section,
            resolved_section["items"],
            add_tool_item_fn=lambda nested_section, item: add_main_tool_item(nested_section, item, owner),
            add_widget_item_fn=lambda nested_section, item: create_main_widget_from_data(nested_section, item, owner),
            add_group_items_fn=lambda nested_section, group_items: add_main_group_items(nested_section, group_items, owner),
        )


def add_main_settings_button(section, item_data, owner):
    import TheKeyMachine.core.toolbox as toolbox

    show_tooltips = settings.get_setting("show_tooltips", True)
    toolbar_alignment = get_main_toolbar_icon_alignment()
    internet_connection = general.config.get("INTERNET_CONNECTION", True)

    def update_show_tooltips(value):
        settings.set_setting("show_tooltips", value)
        QFlatTooltipManager.enabled = value

    def update_toolbar_icon_alignment(alignment_name):
        set_main_toolbar_icon_alignment(owner, alignment_name)

    def _build_settings_menu(_menu, source_widget=None):
        return toolMenus.build_main_settings_menu(
            owner,
            source_widget or btn,
            show_tooltips=show_tooltips,
            toolbar_alignment=toolbar_alignment,
            update_show_tooltips=update_show_tooltips,
            update_toolbar_icon_alignment=update_toolbar_icon_alignment,
            internet_connection=internet_connection,
        )

    settings_tool = toolbox.get_tool("settings", menu=_build_settings_menu)
    btn = add_tool_button(section, settings_tool)
    btn.setObjectName("settings_toolbar_button")

    toolbar_widget = owner.main_toolbar_widget

    def _on_toolbar_context_menu(pos):
        if not toolMenus.should_show_toolbar_pinning_menu(toolbar_widget, pos):
            return
        pinning_menu = toolMenus.build_toolbar_pinning_menu(toolbar_widget, toolbar_widget)
        if pinning_menu.actions():
            pinning_menu.exec_(toolbar_widget.mapToGlobal(pos))

    toolbar_widget.setContextMenuPolicy(QtCore.Qt.CustomContextMenu)
    toolCommon.replace_tracked_connection(
        toolbar_widget,
        "_tkm_toolbar_pinning_context",
        toolbar_widget.customContextMenuRequested,
        _on_toolbar_context_menu,
        parent=toolbar_widget,
    )

    if internet_connection:
        updater.check_for_updates(btn, warning=False, force=False)

    return btn


def get_main_toolbar_icon_alignment():
    alignment_name = settings.get_setting("toolbar_icon_alignment", "Center")
    return toolMenus.toolbar_alignment_value(alignment_name)


def set_main_toolbar_icon_alignment(owner, alignment_name):
    settings.set_setting("toolbar_icon_alignment", alignment_name)
    toolbar_widget = getattr(owner, "main_toolbar_widget", None)
    if not wutil.is_valid_widget(toolbar_widget):
        return

    layout = toolbar_widget.layout()
    if layout:
        layout.setAlignment(toolMenus.toolbar_alignment_value(alignment_name))
        layout.invalidate()

    toolbar_widget.updateGeometry()
    toolbar_widget.update()
    if hasattr(owner, "update_height"):
        owner.update_height()


def add_graph_tool_item(section, item_data, graph_settings_menu_fn):
    if item_key(item_data) == "selector":
        return add_selector_button(section, item_data)
    overrides = {"menu": graph_settings_menu_fn} if item_key(item_data) == "settings" else None
    return add_tool_button(section, item_data, overrides=overrides)


def add_graph_group_items(section, items, graph_settings_menu_fn, toolbar_widget=None):
    return add_grouped_section_items(
        section,
        items,
        add_widget_item_fn=lambda nested_section, item: create_widget_from_data(nested_section, item, owner=toolbar_widget),
        add_group_items_fn=lambda nested_section, group_items: add_graph_group_items(
            nested_section,
            group_items,
            graph_settings_menu_fn,
            toolbar_widget=toolbar_widget,
        ),
    )


def add_graph_section_items(section, items, graph_settings_menu_fn, toolbar_widget=None):
    add_section_items(
        section,
        items,
        add_tool_item_fn=lambda nested_section, item: add_graph_tool_item(nested_section, item, graph_settings_menu_fn),
        add_widget_item_fn=lambda nested_section, item: create_widget_from_data(nested_section, item, owner=toolbar_widget),
        add_group_items_fn=lambda nested_section, group_items: add_graph_group_items(
            nested_section,
            group_items,
            graph_settings_menu_fn,
            toolbar_widget=toolbar_widget,
        ),
    )


def populate_graph_toolbar_from_layout(new_section_fn, graph_settings_menu_fn, toolbar_widget=None):
    import TheKeyMachine.core.toolbox as toolbox

    sections = toolbox.get_toolbar_sections("graph", resolve_items=False)
    for section_def in sections:
        if section_def.get("type") == "slider":
            section = add_slider_section_from_data(
                section_def,
                new_section_fn,
                namespace="graph_toolbar_sliders",
                object_prefix="graph",
                color=section_def.get("color"),
            )
            if section:
                section.set_menu_identity(section_def.get("label"), toolbox.get_section_icon(section_def["id"]))
            continue

        section = new_section_fn(
            color=section_def.get("color"),
            hiddeable=section_def.get("hiddeable", True),
        )
        section.set_menu_identity(section_def.get("label"), toolbox.get_section_icon(section_def["id"]))
        resolved_section = toolbox.get_tool_section(section_def["id"], toolbar_id="graph")
        if section_should_use_group_menu(section_def, resolved_section["items"], special_keys=GRAPH_SPECIAL_TOOL_KEYS):
            add_graph_group_items(section, resolved_section["items"], graph_settings_menu_fn, toolbar_widget=toolbar_widget)
            continue
        add_graph_section_items(section, resolved_section["items"], graph_settings_menu_fn, toolbar_widget=toolbar_widget)


def bind_toolbar_pinning_context(toolbar_widget):
    def _on_toolbar_context_menu(pos):
        if not toolMenus.should_show_toolbar_pinning_menu(toolbar_widget, pos):
            return
        pinning_menu = toolMenus.build_toolbar_pinning_menu(toolbar_widget, toolbar_widget)
        if pinning_menu.actions():
            pinning_menu.exec_(toolbar_widget.mapToGlobal(pos))

    toolbar_widget.setContextMenuPolicy(QtCore.Qt.CustomContextMenu)
    return toolCommon.replace_tracked_connection(
        toolbar_widget,
        "_tkm_toolbar_pinning_context",
        toolbar_widget.customContextMenuRequested,
        _on_toolbar_context_menu,
        parent=toolbar_widget,
    )
