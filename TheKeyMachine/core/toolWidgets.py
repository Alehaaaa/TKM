"""
Shared toolbar widget factories.

This module handles toolbox entries whose descriptor is a widget or a
settings-backed check button, so the main toolbar and Graph Editor toolbar
build the same controls from the same definitions.
"""

import importlib
import random
import warnings

import TheKeyMachine.mods.settingsMod as settings  # type: ignore
import TheKeyMachine.mods.shelfMod as shelf  # type: ignore
import TheKeyMachine.mods.generalMod as general  # type: ignore
from TheKeyMachine.data import icons
import TheKeyMachine.mods.updater as updater  # type: ignore
import TheKeyMachine.core.trigger as trigger  # type: ignore
import TheKeyMachine.mods.selectionMod as selectionMod  # type: ignore
import TheKeyMachine.core.runtimeManager as runtime  # type: ignore
import TheKeyMachine.core.toolMenus as toolMenus  # type: ignore
import TheKeyMachine.tools.animation_offset.api as animationOffsetApi  # type: ignore
import TheKeyMachine.tools.attribute_switcher.api as attributeSwitcherApi  # type: ignore
import TheKeyMachine.tools.depth_mover.api as depthMoverApi  # type: ignore
import TheKeyMachine.tools.gimbal_fixer.api as gimbalFixerApi  # type: ignore
import TheKeyMachine.tools.micro_move.api as microMoveApi  # type: ignore
import TheKeyMachine.core.connectEntries as connectEntries
import TheKeyMachine.tools.orbit.api as orbitApi  # type: ignore
import TheKeyMachine.tools.selection_sets.api as selectionSetsApi  # type: ignore
from TheKeyMachine.tools import common as toolCommon  # type: ignore
from TheKeyMachine.widgets import sliderWidget as sw  # type: ignore
from TheKeyMachine.widgets import customWidgets as cw  # type: ignore
from TheKeyMachine.widgets import customDialogs  # type: ignore
from TheKeyMachine.widgets import util as wutil  # type: ignore

from TheKeyMachine.core.Qt import QtCompat, QtCore, QtGui  # type: ignore


MAIN_SPECIAL_TOOL_KEYS = {
    "orbit",
    "selection_sets",
    "attribute_switcher",
    "selector",
    "TKM",
}

GRAPH_SPECIAL_TOOL_KEYS = {
    "orbit",
    "selection_sets",
    "attribute_switcher",
    "selector",
    "TKM",
}


def _tooltip_description(data):
    tooltip = (data or {}).get("tooltip")
    return (data or {}).get("description") or (tooltip if isinstance(tooltip, str) else "")


def setting_specs():
    specs = {}
    import TheKeyMachine.core.toolbox as toolbox

    for tool_id, tool in toolbox.get_tool_definitions().items():
        if tool.get("type") != "setting":
            continue
        package_name = tool.get("_package")
        if not package_name:
            raise RuntimeError("Setting {!r} has no owning package".format(tool_id))
        api = importlib.import_module(package_name + ".api")
        resolver = getattr(api, "get_setting_spec", None)
        if not callable(resolver):
            raise RuntimeError("{} must expose api.get_setting_spec()".format(package_name))
        behavior = resolver(tool_id)
        if not isinstance(behavior, dict) or not callable(behavior.get("get_checked")) or not callable(behavior.get("set_checked")):
            raise RuntimeError("{} returned an invalid setting spec for {!r}".format(package_name, tool_id))
        spec = {
            "id": tool_id,
            "label": tool.get("label", tool_id),
            "menu_label": tool.get("menu_label") or tool.get("label", tool_id),
            "text": tool.get("text"),
            "icon": tool.get("icon"),
            "description": _tooltip_description(tool),
            "tooltip": tool.get("tooltip"),
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
        return bool(QtCompat.isValid(widget))
    except Exception:
        return False


def _disconnect_setting_toggle_signal(signal, slot):
    with warnings.catch_warnings():
        warnings.simplefilter("ignore", RuntimeWarning)
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
    if tool_id == "animation_offset":
        data["changed_signal"] = animationOffsetApi.get_controller().stateChanged
    elif tool_id == "depth_mover":
        data["changed_signal"] = depthMoverApi.get_controller().stateChanged
    elif tool_id == "micro_move":
        data["changed_signal"] = microMoveApi.get_controller().stateChanged
    btn = cw.create_tool_button_from_data(data)
    if tool_id == "background_runners":
        bind_background_runners_activity_button(btn)
    section.addWidget(
        btn,
        data.get("label", ""),
        tool_id or "",
        default=data.get("default", True),
        description=_tooltip_description(data),
        tooltip=data.get("tooltip"),
        tooltip_enabled=data.get("tooltip_enabled", True),
        pinnable=data.get("pinnable", True),
    )
    return btn


def _refresh_connect_entry_section(section, kind):
    if not wutil.is_valid_widget(section):
        return

    for entry_id in getattr(section, "_tkm_connect_entry_ids", ()):
        section.removeWidgetByKey(entry_id)

    entry_ids = []
    for entry in connectEntries.load_entries(kind):
        if entry.get("type") != "entry":
            continue
        item = {
            "id": entry["id"],
            "type": "tool",
            "label": entry["label"],
            "icon": entry["icon"],
            "text": entry["text"],
            "callback": entry["callback"],
            "description": entry.get("description"),
            "tooltip": entry.get("tooltip"),
            "tooltip_enabled": True,
            "default": False,
        }
        add_tool_button(section, item)
        entry_ids.append(entry["id"])
    section._tkm_connect_entry_ids = tuple(entry_ids)

    parent = section.parentWidget()
    if parent and hasattr(parent, "_update_height"):
        QtCore.QTimer.singleShot(0, parent._update_height)


def add_connect_entries_section(new_section_fn, toolbar_id):
    import TheKeyMachine.core.toolbox as toolbox

    for kind in connectEntries.SOURCES:
        spec = connectEntries.source_spec(kind)
        section = new_section_fn()
        namespace = spec["namespace"]
        if toolbar_id != "main":
            namespace = "{}_{}".format(namespace, toolbar_id)
        section.set_settings_namespace(namespace)
        folder_tool = toolbox.get_tool(spec["folder_tool_id"], default=True)
        section.set_menu_identity(spec["label"], folder_tool.get("icon"))
        add_tool_button(section, folder_tool)
        section.addSeparator()
        _refresh_connect_entry_section(section, kind)

        def _on_entries_changed(changed_kind, target=section, source_kind=kind):
            if changed_kind == source_kind:
                _refresh_connect_entry_section(target, source_kind)

        toolCommon.replace_tracked_connection(
            section,
            "_tkm_connect_entries_changed",
            connectEntries.connect_entries_bus.entriesChanged,
            _on_entries_changed,
            parent=section,
        )


def bind_background_runners_activity_button(btn):
    if not wutil.is_valid_widget(btn):
        return btn

    default_icon = icons.background_runners_0
    activity_icons = [
        icons.background_runners_1,
        icons.background_runners_2,
        icons.background_runners_3,
        icons.background_runners_4,
    ]
    btn.setIcon(QtGui.QIcon(default_icon))

    timer = getattr(btn, "_tkm_background_runner_activity_timer", None)
    if timer is None:
        timer = QtCore.QTimer(btn)
        timer.setInterval(90)
        btn._tkm_background_runner_activity_timer = timer

    state = {"index": 0, "sequence": []}

    def _show_default():
        if wutil.is_valid_widget(btn):
            btn.setIcon(QtGui.QIcon(default_icon))

    def _advance_icon():
        if not wutil.is_valid_widget(btn):
            timer.stop()
            return
        sequence = state.get("sequence") or []
        index = state.get("index", 0)
        if index >= len(sequence):
            timer.stop()
            _show_default()
            return
        btn.setIcon(QtGui.QIcon(sequence[index]))
        state["index"] = index + 1

    with warnings.catch_warnings():
        warnings.simplefilter("ignore", RuntimeWarning)
        try:
            timer.timeout.disconnect()
        except Exception:
            pass
    timer.timeout.connect(_advance_icon)

    def _pulse(*_args):
        if not wutil.is_valid_widget(btn):
            return
        timer.stop()
        sequence_len = random.randint(1, 2)
        state["sequence"] = [random.choice(activity_icons) for _idx in range(sequence_len)]
        state["index"] = 0
        _advance_icon()
        timer.start()

    manager = runtime.get_runtime_manager(start=False)
    signal = getattr(manager, "backgroundRunnerTriggered", None)
    if signal is not None:
        toolCommon.replace_tracked_connection(
            btn,
            "_tkm_background_runner_activity_connection",
            signal,
            _pulse,
            parent=btn,
        )
    return btn


def add_selector_button(section, item_data):
    import TheKeyMachine.core.toolbox as toolbox

    selector_tool = toolbox.get_tool("selector", **{k: v for k, v in item_data.items() if k not in {"id", "shortcuts"}})
    btn = cw.QFlatSelectorButton(
        icon=selector_tool.get("icon"),
        tooltip=selector_tool.get("tooltip"),
        description=_tooltip_description(selector_tool),
    )
    btn.configure_from_data(selector_tool)

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
        description=_tooltip_description(selector_tool),
        tooltip=selector_tool.get("tooltip"),
        pinnable=selector_tool.get("pinnable", True),
    )

    def update_selector_button_text(*_args, button=btn):
        if not wutil.is_valid_widget(button):
            return
        button.setCount(len(selectionMod.get_valid_selected_objects()))

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
    return isinstance(item_data, dict) and item_data.get("type") in {"widget", "setting"}


def is_group_item(item_data):
    return isinstance(item_data, dict) and item_data.get("type") == "group"


def is_action_item(item_data):
    if not isinstance(item_data, dict):
        return False
    return item_data.get("type") not in {"widget", "setting", "group"}


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


def build_slider_section(
    section,
    section_def,
    modes,
    execute,
    create_session,
    *,
    namespace,
    object_prefix,
):
    section.set_settings_namespace(namespace)
    prefix = section_def["slider_type"]
    color = section_def["color"]
    icon_color = section_def.get("icon_color", color)
    import TheKeyMachine.core.toolbox as toolbox

    toolbar_id = section_def.get("_toolbar_id")
    default_keys = [
        f"{prefix}_{mode.key}"
        for mode in modes
        if hasattr(mode, "key") and toolbox.is_pinned_by_default(toolbar_id, f"{prefix}_{mode.key}")
    ]

    for mode in modes:
        if mode == "separator":
            section.addSeparator()
            continue
        if not hasattr(mode, "key"):
            continue

        key = mode.key
        label = mode.label
        desc = mode.description
        mode_data = mode.widget_data()
        slot_key = f"{prefix}_{key}"

        slider = sw.QFlatSliderWidget(
            f"{object_prefix}_{prefix}_{key}",
            min=-100,
            max=100,
            text=mode_data.get("icon") or mode_data.get("text") or "SL",
            color=color,
            icon_color=icon_color,
            dragCommand=lambda mode_key, value, session=None, callback=execute: callback(
                mode_key, value, session=session
            ),
            sessionFactory=create_session,
            tooltipTitle=label,
            tooltipDescription=desc,
            tooltip=mode.tooltip,
        )
        slider.setModes(modes)
        slider.setCurrentMode(key)

        def make_mode_setter(slider_instance):
            def setter(new_mode, temporary=False):
                slider_instance.setCurrentMode(new_mode, temporary=temporary)
                if not temporary:
                    slider_instance.startModeTransition()

            return setter

        slider.modeRequested.connect(make_mode_setter(slider))
        section.addWidget(
            slider,
            label,
            slot_key,
            default=slot_key in default_keys,
            description=desc,
            tooltip=mode.tooltip,
        )

    section._default_keys = default_keys
    return section


def create_widget_from_data(section, item_data, owner=None):
    widget_key = item_key(item_data)

    factory = item_data.get("widget_factory")
    if callable(factory):
        return factory(section, item_data, owner=owner)

    if widget_key == "selector":
        return add_selector_button(section, item_data)

    spec = setting_specs().get(widget_key)
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
        "tooltip": resolved.get("tooltip"),
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
        description=_tooltip_description(data),
        tooltip=data.get("tooltip"),
        pinnable=resolved.get("pinnable", True),
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
    if widget_key == "selector":
        return add_selector_button(section, item_data)
    return create_widget_from_data(section, item_data, owner=owner)


def add_main_tool_item(section, item_data, owner):
    key = item_key(item_data)
    factory = item_data.get("widget_factory")
    if callable(factory):
        return factory(section, item_data, owner=owner)
    if key == "selector":
        return add_selector_button(section, item_data)
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
    if key == "gimbal":
        return add_bound_tool_button(section, item_data, gimbalFixerApi.bind_gimbal_fixer_toolbar_button)
    return add_tool_button(section, item_data)


def add_main_group_items(section, items, owner):
    return add_grouped_section_items(
        section,
        items,
        add_widget_item_fn=lambda nested_section, item: create_main_widget_from_data(nested_section, item, owner),
        add_group_items_fn=lambda nested_section, group_items: add_main_group_items(nested_section, group_items, owner),
    )


def add_slider_section_from_data(section_def, new_section_fn, *, namespace, object_prefix, color=None):
    kwargs = {}
    if color is not None:
        kwargs["color"] = color
    section = new_section_fn(**kwargs)
    factory = section_def.get("section_factory")
    if not callable(factory):
        raise ValueError("Slider section {} has no section_factory".format(section_def.get("id")))
    return factory(
        section, section_def,
        namespace=namespace,
        object_prefix=object_prefix,
    )


def populate_main_toolbar_from_layout(layout_id, new_section_fn, owner):
    import TheKeyMachine.core.toolbox as toolbox

    sections = toolbox.get_toolbar_sections(layout_id, resolve_items=False)
    for section_def in sections:
        sec_id = section_def["id"]

        if section_def.get("type") == "connect_entries":
            add_connect_entries_section(new_section_fn, "main")
            continue

        if section_def.get("type") == "slider":
            section = add_slider_section_from_data(
                section_def,
                new_section_fn,
                namespace="main_toolbar_sliders",
                object_prefix="bar",
            )
            if section:
                section.set_menu_identity(
                    section_def.get("label"),
                    toolbox.get_section_icon(section_def["id"]),
                )
            continue

        section = new_section_fn(
            color=section_def.get("color"),
            hiddeable=section_def.get("hiddeable", True),
        )
        section.set_menu_identity(
            section_def.get("label"),
            toolbox.get_section_icon(sec_id),
        )
        resolved_section = toolbox.get_tool_section(sec_id, toolbar_id="main")

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

    toolbar_widget = getattr(owner, "main_toolbar_widget", None)
    for section in getattr(toolbar_widget, "_tkm_sections", ()) if toolbar_widget is not None else ():
        section.enable_entry_animations()


def show_welcome_shelf_prompt(anchor_button):
    if not wutil.is_valid_widget(anchor_button):
        return

    add_button = customDialogs.QFlatConfirmDialog.CustomButton("Add to Shelf", positive=True, icon=icons.add_to_shelf)
    no_button = customDialogs.QFlatConfirmDialog.CustomButton("No", positive=False, icon=icons.cancel)
    clicked = customDialogs.QFlatTooltipConfirm.question(
        anchor_button,
        title="Add TheKeyMachine to your shelf?",
        message="Create a shelf button so you can show or hide the toolbar quickly.",
        buttons=[add_button, no_button],
        icon=icons.tkm_main,
        highlight=add_button,
    )
    if clicked and clicked.get("positive"):
        shelf.create_main_shelf_button()


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


def add_graph_tool_item(section, item_data, graph_settings_menu_fn):
    if item_key(item_data) == "selector":
        return add_selector_button(section, item_data)
    overrides = {"menu": graph_settings_menu_fn} if item_key(item_data) == "TKM" else None
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
        if section_def.get("type") == "connect_entries":
            add_connect_entries_section(new_section_fn, "graph")
            continue

        if section_def.get("type") == "slider":
            section = add_slider_section_from_data(
                section_def,
                new_section_fn,
                namespace="graph_toolbar_sliders",
                object_prefix="graph",
                color=section_def.get("color"),
            )
            if section:
                section.set_menu_identity(
                    section_def.get("label"),
                    toolbox.get_section_icon(section_def["id"]),
                )
            continue

        section = new_section_fn(
            color=section_def.get("color"),
            hiddeable=section_def.get("hiddeable", True),
        )
        section.set_menu_identity(
            section_def.get("label"),
            toolbox.get_section_icon(section_def["id"]),
        )
        resolved_section = toolbox.get_tool_section(section_def["id"], toolbar_id="graph")
        if section_should_use_group_menu(section_def, resolved_section["items"], special_keys=GRAPH_SPECIAL_TOOL_KEYS):
            add_graph_group_items(section, resolved_section["items"], graph_settings_menu_fn, toolbar_widget=toolbar_widget)
            continue
        add_graph_section_items(section, resolved_section["items"], graph_settings_menu_fn, toolbar_widget=toolbar_widget)

    for section in getattr(toolbar_widget, "_tkm_sections", ()) if toolbar_widget is not None else ():
        section.enable_entry_animations()


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
