"""Shared toolbar widget factories.

This module handles registry entries whose descriptor is a widget or a
settings-backed check button, so the main toolbar and Graph Editor toolbar
build the same controls from the same definitions.
"""

import importlib
import random
import warnings

from TheKeyMachine.core import settings  # type: ignore
from TheKeyMachine.maya import shelf  # type: ignore
from TheKeyMachine.data import icons
from TheKeyMachine.maya import selection  # type: ignore
from TheKeyMachine.core import runtime  # type: ignore
import TheKeyMachine.tools.animation_offset.api as animationOffsetApi  # type: ignore
import TheKeyMachine.tools.attribute_switcher.api as attributeSwitcherApi  # type: ignore
import TheKeyMachine.tools.depth_mover.api as depthMoverApi  # type: ignore
import TheKeyMachine.tools.gimbal_fixer.api as gimbalFixerApi  # type: ignore
import TheKeyMachine.tools.micro_move.api as microMoveApi  # type: ignore
from TheKeyMachine.tools.custom_tools import service as connect_entries
import TheKeyMachine.tools.orbit.api as orbitApi  # type: ignore
import TheKeyMachine.tools.selection_sets.api as selectionSetsApi  # type: ignore
from TheKeyMachine.tools import common as toolCommon  # type: ignore
from TheKeyMachine.ui.widgets import sliderWidget as sw  # type: ignore
from TheKeyMachine.ui.widgets import customWidgets as cw  # type: ignore
from TheKeyMachine.ui.widgets import customDialogs  # type: ignore
from TheKeyMachine.ui.widgets import util as wutil  # type: ignore
from TheKeyMachine.ui import toolbar_modes

from TheKeyMachine.core.Qt import QtCompat, QtCore, QtGui, QtWidgets  # type: ignore


# Tool keys that get special handling (bound callbacks, custom widgets, ...)
# instead of a plain toolbutton, on both the main toolbar and the Graph
# Editor toolbar -- the two toolbars share one tool registry, so the set of
# keys that need special-casing is the same for both.
TOOLBAR_SPECIAL_TOOL_KEYS = {
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
    from TheKeyMachine.tools import registry

    for tool_id, tool in registry.get_tool_definitions().items():
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
    elif tool_id == "animation_recovery":
        from TheKeyMachine.tools.animation_recovery import api as animationRecoveryApi

        animationRecoveryApi.bind_toolbar_button(btn)
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
    for entry in connect_entries.load_entries(kind):
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
    from TheKeyMachine.tools import registry

    for kind in connect_entries.SOURCES:
        spec = connect_entries.source_spec(kind)
        section = new_section_fn()
        namespace = spec["namespace"]
        if toolbar_id != "main":
            namespace = "{}_{}".format(namespace, toolbar_id)
        section.set_settings_namespace(namespace)
        folder_tool = registry.get_tool(spec["folder_tool_id"], default=True)
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
            connect_entries.connect_entries_bus.entriesChanged,
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
    from TheKeyMachine.tools import registry

    selector_tool = registry.get_tool("selector", **{k: v for k, v in item_data.items() if k not in {"id", "shortcuts"}})
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
        button.setCount(len(selection.get_valid_selected_objects()))

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
    """Render a resolved registry item list in descriptor order."""
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
    are inserted where they appear in the registry definition, so sections such as Nudge,
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
    from TheKeyMachine.tools import registry
    from TheKeyMachine.core import i18n

    toolbar_id = section_def.get("_toolbar_id")
    default_keys = [
        f"{prefix}_{mode.key}"
        for mode in modes
        if hasattr(mode, "key") and registry.is_pinned_by_default(toolbar_id, f"{prefix}_{mode.key}")
    ]

    # SliderMode instances carry their own label/tooltip instead of living in
    # the registry.get_tool() registry (see ui/sliders), but each slider
    # package still gets a lang.json keyed the same way as any other tool.
    # Localizing the whole list once (rather than per-mode) is what lets the
    # widget's own mode-switch menu -- which reads straight from its stored
    # mode list -- show every mode translated too, not just the active one.
    package_file = section_def.get("_package_file")
    localized_modes = i18n.localize_slider_modes(modes, package_file)
    # Remembered so a later language change can redo this exact call and
    # push the result straight into each already-built slider widget --
    # see QFlatSectionWidget.refresh_translations().
    section._tkm_slider_source_modes = modes
    section._tkm_slider_package_file = package_file
    section._tkm_slider_prefix = prefix

    for mode in localized_modes:
        if mode == "separator":
            section.addSeparator()
            continue
        if not hasattr(mode, "key"):
            continue

        key = mode.key
        label = mode.label
        tooltip = mode.tooltip
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
            tooltip=tooltip,
        )
        slider.setModes(localized_modes)
        slider.setCurrentMode(key)

        # A permanent mode-switch request (right-click) and a temporary one
        # (modifier-preview) are both routed to the section itself, exactly
        # like every other slider/toolbutton event this loop wires up via
        # section.addWidget() below -- see
        # QFlatSectionWidget._on_slider_mode_requested.
        section.addWidget(
            slider,
            label,
            slot_key,
            default=slot_key in default_keys,
            description=desc,
            tooltip=tooltip,
            icon=mode_data.get("icon"),
            command_icon=mode_data.get("icon"),
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


def _populate_toolbar_from_layout(
    layout_id,
    toolbar_id,
    new_section_fn,
    *,
    slider_namespace,
    slider_object_prefix,
    add_tool_item_fn,
    add_widget_item_fn,
    add_group_items_fn,
    animations_widget,
):
    """Shared skeleton for building a toolbar's sections from the tool registry.

    The main toolbar and the Graph Editor toolbar read from the same
    declarative tool/section definitions and walk them identically --
    connect-entries sections, slider sections, then plain/grouped tool
    sections. What differs between the two toolbars is *what* gets built
    for a given tool item (a plain button, a bound special widget, or a
    settings toggle) and the extra context that construction needs (the
    main-window ``owner`` vs. the Graph Editor's settings-menu factory).
    That's supplied by the caller as the ``add_*_fn`` callbacks.
    """
    from TheKeyMachine.tools import registry

    sections = registry.get_toolbar_sections(layout_id, resolve_items=False)
    for section_def in sections:
        sec_id = section_def["id"]

        if section_def.get("type") == "connect_entries":
            add_connect_entries_section(new_section_fn, toolbar_id)
            continue

        if section_def.get("type") == "slider":
            section = add_slider_section_from_data(
                section_def,
                new_section_fn,
                namespace=slider_namespace,
                object_prefix=slider_object_prefix,
                color=section_def.get("color"),
            )
            if section:
                section._tkm_section_id = section_def["id"]
                section.set_menu_identity(
                    section_def.get("label"),
                    registry.get_section_icon(section_def["id"]),
                )
            continue

        section = new_section_fn(
            color=section_def.get("color"),
            hiddeable=section_def.get("hiddeable", True),
        )
        section._tkm_section_id = sec_id
        section.set_menu_identity(
            section_def.get("label"),
            registry.get_section_icon(sec_id),
        )
        resolved_section = registry.get_tool_section(sec_id, toolbar_id=toolbar_id)

        if section_should_use_group_menu(
            section_def, resolved_section["items"], special_keys=TOOLBAR_SPECIAL_TOOL_KEYS
        ):
            add_group_items_fn(section, resolved_section["items"])
            continue

        add_section_items(
            section,
            resolved_section["items"],
            add_tool_item_fn=add_tool_item_fn,
            add_widget_item_fn=add_widget_item_fn,
            add_group_items_fn=add_group_items_fn,
        )

    for section in getattr(animations_widget, "_tkm_sections", ()) if animations_widget is not None else ():
        section.enable_entry_animations()

    if animations_widget is not None:
        _bind_toolbar_translation_refresh(animations_widget)


def _refresh_toolbar_translations(toolbar_widget, *_args):
    from TheKeyMachine.tools import registry

    for section in getattr(toolbar_widget, "_tkm_sections", ()) or ():
        if not wutil.is_valid_widget(section):
            continue
        section.refresh_translations()

        # A section's menu identity (label shown in the right-click pinning
        # menu) is set once at build time from the same translated section
        # label -- see _populate_toolbar_from_layout -- so it needs the same
        # explicit re-apply as its buttons/sliders on a language switch.
        section_id = getattr(section, "_tkm_section_id", None)
        if not section_id:
            continue
        section_def = registry.get_tool_section(section_id, resolve_items=False)
        if section_def:
            section.set_menu_identity(
                section_def.get("label"),
                registry.get_section_icon(section_id),
            )


def _bind_toolbar_translation_refresh(toolbar_widget):
    """Keep already-built toolbar buttons in sync with language switches.

    Sections are fixed for the toolbar's lifetime (this runs once per
    toolbar build/reload, same assumption as the pinning menu), so each
    section's own already-built buttons need an explicit refresh on
    language change -- unlike the dropdown menus in toolbar_menus.py, which
    rebuild fresh on every open and pick a switch up on their own.
    """
    from TheKeyMachine.core import i18n

    def _on_language_changed(*_args, widget=toolbar_widget):
        _refresh_toolbar_translations(widget)

    toolCommon.replace_tracked_connection(
        toolbar_widget,
        "_tkm_toolbar_translation_connection",
        i18n.bus.languageChanged,
        _on_language_changed,
        parent=toolbar_widget,
    )


def populate_main_toolbar_from_layout(layout_id, new_section_fn, owner):
    _populate_toolbar_from_layout(
        layout_id,
        "main",
        new_section_fn,
        slider_namespace="main_toolbar_sliders",
        slider_object_prefix="bar",
        add_tool_item_fn=lambda nested_section, item: add_main_tool_item(nested_section, item, owner),
        add_widget_item_fn=lambda nested_section, item: create_main_widget_from_data(nested_section, item, owner),
        add_group_items_fn=lambda nested_section, group_items: add_main_group_items(nested_section, group_items, owner),
        animations_widget=getattr(owner, "main_toolbar_widget", None),
    )


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
    alignment_name = settings.get_setting(
        toolbar_modes.MAIN_ALIGNMENT_SETTING,
        toolbar_modes.DEFAULT_ALIGNMENT,
    )
    return toolbar_modes.alignment_value(alignment_name)


def set_main_toolbar_icon_alignment(owner, alignment_name):
    alignment_name = toolbar_modes.normalize(alignment_name)
    settings.set_setting(toolbar_modes.MAIN_ALIGNMENT_SETTING, alignment_name)
    toolbar_widget = getattr(owner, "main_toolbar_widget", None)
    if not wutil.is_valid_widget(toolbar_widget):
        return

    toolbar_modes.apply_to(toolbar_widget, alignment_name)
    update_height = getattr(owner, "update_height", None)
    if callable(update_height):
        QtCore.QTimer.singleShot(0, update_height)


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


def populate_graph_toolbar_from_layout(new_section_fn, graph_settings_menu_fn, toolbar_widget=None):
    _populate_toolbar_from_layout(
        "graph",
        "graph",
        new_section_fn,
        slider_namespace="graph_toolbar_sliders",
        slider_object_prefix="graph",
        add_tool_item_fn=lambda nested_section, item: add_graph_tool_item(nested_section, item, graph_settings_menu_fn),
        add_widget_item_fn=lambda nested_section, item: create_widget_from_data(nested_section, item, owner=toolbar_widget),
        add_group_items_fn=lambda nested_section, group_items: add_graph_group_items(
            nested_section, group_items, graph_settings_menu_fn, toolbar_widget=toolbar_widget
        ),
        animations_widget=toolbar_widget,
    )


class _ToolbarPinningEventFilter(QtCore.QObject):
    """Handle context-menu events from otherwise empty dock areas.

    Installing this on the *parent* dock widget ensures that any blank area
    (e.g. around the TKM button) also responds without hijacking child widgets'
    own context menus.
    """

    def __init__(self, toolbar_widget, parent=None):
        super().__init__(parent)
        self._toolbar_widget = toolbar_widget

    def eventFilter(self, obj, event):
        from TheKeyMachine.ui.widgets import toolbar_menus

        if event.type() == QtCore.QEvent.ContextMenu:
            tw = self._toolbar_widget
            if QtCompat.isValid(tw):
                try:
                    global_pos = event.globalPos()
                    local_pos = tw.mapFromGlobal(global_pos)
                except RuntimeError:
                    return False
                if not toolbar_menus.should_show_toolbar_pinning_menu(tw, local_pos):
                    return False
                if toolbar_menus.show_toolbar_pinning_menu(tw, global_pos):
                    event.accept()
                    return True
        return False


def bind_toolbar_pinning_context(toolbar_widget, parent_widget=None):
    """Bind the right-click pinning context menu to *toolbar_widget*.

    If *parent_widget* is supplied (typically the top-level dock container that
    also hosts the TKM button), a QObject event-filter is installed on it so
    that a right-click *anywhere* on the toolbar, including empty areas and
    the TKM button column, opens the same pinning menu.
    """
    from TheKeyMachine.ui.widgets import toolbar_menus

    # QScrollArea owns a viewport and a content widget, so background context
    # events can land on any of the three. Bind all of them to one menu path.
    context_targets = [toolbar_widget]
    if isinstance(toolbar_widget, QtWidgets.QScrollArea):
        context_targets.extend((toolbar_widget.viewport(), toolbar_widget.widget()))

    for index, target in enumerate(context_targets):
        if target is None:
            continue

        def _on_toolbar_context_menu(pos, source=target):
            global_pos = source.mapToGlobal(pos)
            toolbar_pos = toolbar_widget.mapFromGlobal(global_pos)
            if not toolbar_menus.should_show_toolbar_pinning_menu(toolbar_widget, toolbar_pos):
                return
            toolbar_menus.show_toolbar_pinning_menu(toolbar_widget, global_pos)

        target.setContextMenuPolicy(QtCore.Qt.CustomContextMenu)
        toolCommon.replace_tracked_connection(
            target,
            "_tkm_toolbar_pinning_context_{}".format(index),
            target.customContextMenuRequested,
            _on_toolbar_context_menu,
            parent=target,
        )

    # ── Event-filter on the parent dock so the whole toolbar responds ─────────
    if parent_widget is not None and parent_widget is not toolbar_widget:
        event_filter = _ToolbarPinningEventFilter(toolbar_widget, parent=parent_widget)
        parent_widget.installEventFilter(event_filter)
        # Store a reference so it isn't garbage-collected
        parent_widget._tkm_pinning_event_filter = event_filter
