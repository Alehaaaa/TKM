"""Command discovery and dispatch for tools, hotkeys, and shelf buttons."""

from __future__ import annotations

import importlib
import inspect
from dataclasses import dataclass
from functools import wraps
from typing import Callable, Dict, Optional


SLIDER_BUTTON_VALUES = (
    -150, -125, -105, -100, -50, -15, -5,
    0,
    5, 15, 50, 100, 105, 125, 150,
)


@dataclass(frozen=True)
class OperationPolicy:
    """Execution behavior applied around one registered command."""

    progress: bool = True
    undo: bool = True
    suspend_refresh: bool = False
    preserve_time_selection: bool = False
    rollback_on_cancel: bool = False
    interruptable: bool = True
    show_success_message: bool = True
    capture_animation_context: bool = False
    queue_group: Optional[str] = None
    queue_delta: int = 0


@dataclass(frozen=True)
class _RegisteredCommand:
    callback: Callable
    policy: OperationPolicy
    dispatch: Callable


_COMMANDS: Dict[str, _RegisteredCommand] = {}
_SLIDER_EXECUTORS: Dict[str, Callable] = {}
_DISCOVERY_COMPLETE = False
_DISCOVERY_IN_PROGRESS = False
_SLIDER_POLICY = OperationPolicy(progress=False, undo=False)


def _policy_from_definition(
    command_name: str,
    definition,
    callback: Optional[Callable] = None,
) -> OperationPolicy:
    explicit = (definition or {}).get("operation") or {}
    if explicit:
        undo = bool(explicit.get("undo", True))
        interruptable = bool(explicit.get("interruptable", True))
        return OperationPolicy(
            progress=bool(explicit.get("progress", True)),
            undo=undo,
            suspend_refresh=bool(explicit.get("suspend_refresh", False)),
            preserve_time_selection=bool(
                explicit.get("preserve_time_selection", False)
            ),
            rollback_on_cancel=bool(
                explicit.get("rollback_on_cancel", undo and interruptable)
            ),
            interruptable=interruptable,
            show_success_message=bool(explicit.get("show_success_message", True)),
            capture_animation_context=bool(
                explicit.get("capture_animation_context", False)
            ),
            queue_group=explicit.get("queue_group"),
            queue_delta=int(explicit.get("queue_delta", 0)),
        )
    if getattr(callback, "_tkm_non_tool_action", False):
        return OperationPolicy(progress=False, undo=False)
    definition_type = (definition or {}).get("type")
    is_tool_operation = (
        definition_type in (None, "tool")
        and not command_name.endswith(("_menu", "_window"))
    )
    is_timed_action = (
        definition_type != "menu"
        and not command_name.endswith(("_menu", "_window"))
    )
    return OperationPolicy(
        progress=is_timed_action,
        undo=is_tool_operation,
        rollback_on_cancel=is_tool_operation,
    )


def register_command(
    name: str,
    callback: Callable,
    policy: Optional[OperationPolicy] = None,
) -> Callable:
    """Register a callable behind the shared tool-operation boundary."""
    if not name or not callable(callback):
        raise ValueError("Commands require a name and callable callback")

    existing = _COMMANDS.get(name)
    if policy is not None:
        resolved_policy = policy
    elif existing is not None:
        resolved_policy = existing.policy
    else:
        resolved_policy = _policy_from_definition(name, {}, callback)

    original = getattr(callback, "_tkm_registered_callback", callback)

    try:
        parameters = tuple(inspect.signature(original).parameters.values())
    except (TypeError, ValueError):
        accepted_keywords = None
    else:
        accepts_any_keyword = any(
            parameter.kind == inspect.Parameter.VAR_KEYWORD
            for parameter in parameters
        )
        accepted_keywords = None if accepts_any_keyword else {
            parameter.name
            for parameter in parameters
            if parameter.kind
            in (
                inspect.Parameter.POSITIONAL_OR_KEYWORD,
                inspect.Parameter.KEYWORD_ONLY,
            )
        }

    @wraps(original)
    def dispatch(*args, **kwargs):
        from TheKeyMachine.tools import common as toolCommon

        label = kwargs.pop("_tkm_tool_label", None)
        anchor = kwargs.pop("_tkm_anchor_widget", None)
        selection_snapshot = kwargs.pop("_tkm_selection_snapshot", None)
        if "tool_operation" in kwargs:
            raise TypeError(
                "Registered commands own their ToolOperation; callers must not "
                "inject one"
            )

        active_operation = toolCommon.current_tool_operation()
        queued_delta = kwargs.get("steps", resolved_policy.queue_delta)
        if (
            active_operation is not None
            and getattr(active_operation, "accepts_deferred_commands", False)
        ):
            deferred_kwargs = dict(kwargs)
            if label is not None:
                deferred_kwargs["_tkm_tool_label"] = label
            if anchor is not None:
                deferred_kwargs["_tkm_anchor_widget"] = anchor
            return toolCommon.defer_tool_callback(
                dispatch,
                *args,
                _tkm_queue_group=resolved_policy.queue_group,
                _tkm_queue_delta=queued_delta,
                _tkm_queue_argument="steps",
                **deferred_kwargs
            )

        with toolCommon.tool_operation(
            tool_id=name,
            label=label,
            anchor_widget=anchor,
            progress=resolved_policy.progress,
            undo=resolved_policy.undo,
            suspend_refresh=resolved_policy.suspend_refresh,
            preserve_time_selection=resolved_policy.preserve_time_selection,
            rollback_on_cancel=resolved_policy.rollback_on_cancel,
            interruptable=resolved_policy.interruptable,
            show_success_message=resolved_policy.show_success_message,
            selection_snapshot=selection_snapshot,
        ) as operation:
            if (
                resolved_policy.capture_animation_context
                and operation.selection_snapshot is None
            ):
                from TheKeyMachine.maya import animation

                operation.selection_snapshot = animation.capture_selection_snapshot()
            call_kwargs = dict(kwargs)
            call_kwargs.setdefault("anchor_widget", anchor)
            call_kwargs.setdefault("tool_operation", operation)
            if accepted_keywords is not None:
                call_kwargs = {
                    key: value
                    for key, value in call_kwargs.items()
                    if key in accepted_keywords
                }

            return original(*args, **call_kwargs)

    dispatch.__name__ = name
    dispatch._tkm_command_name = name
    dispatch._tkm_registered_callback = original
    _COMMANDS[name] = _RegisteredCommand(original, resolved_policy, dispatch)
    return dispatch


def reset_registry() -> None:
    """Discard discovered commands and package-backed executors for reload."""
    global _DISCOVERY_COMPLETE, _DISCOVERY_IN_PROGRESS
    _COMMANDS.clear()
    _SLIDER_EXECUTORS.clear()
    _DISCOVERY_COMPLETE = False
    _DISCOVERY_IN_PROGRESS = False

def _register_slider_commands(prefix: str, mode: str, execute: Callable) -> None:
    for value in SLIDER_BUTTON_VALUES:
        def execute_mode(
            session=None,
            _execute=execute,
            _mode=mode,
            _value=value,
        ):
            return _execute(_mode, _value, session=session)

        register_command(
            slider_command_name(prefix, mode, value),
            execute_mode,
            policy=_SLIDER_POLICY,
        )

def _discover_commands() -> None:
    global _DISCOVERY_COMPLETE, _DISCOVERY_IN_PROGRESS
    if _DISCOVERY_COMPLETE or _DISCOVERY_IN_PROGRESS:
        return

    _DISCOVERY_IN_PROGRESS = True
    try:
        from TheKeyMachine.tools.custom_tools import service as connect_entries
        from TheKeyMachine.tools import registry

        for tool_id, definition in registry.get_tool_definitions().items():
            callback = definition.get("callback")
            if callable(callback):
                register_command(
                    tool_id,
                    callback,
                    policy=_policy_from_definition(tool_id, definition, callback),
                )

        for section_id, section in registry.get_section_definitions().items():
            if section.get("type") != "slider":
                continue

            prefix = section.get("slider_type")
            package_name = section.get("_package")
            if not prefix or not package_name:
                raise RuntimeError(
                    "Slider section {!r} is missing its type or owning package".format(
                        section_id
                    )
                )

            api = importlib.import_module(package_name + ".api")
            execute = getattr(api, "execute", None)
            if not callable(execute):
                raise RuntimeError("{} must expose api.execute()".format(package_name))

            previous = _SLIDER_EXECUTORS.get(prefix)
            if previous is not None and previous is not execute:
                raise RuntimeError("Duplicate slider type {!r}".format(prefix))
            _SLIDER_EXECUTORS[prefix] = execute

            for mode in section.get("modes") or ():
                mode_key = getattr(mode, "key", None)
                if mode_key:
                    _register_slider_commands(prefix, mode_key, execute)

        for kind in connect_entries.SOURCES:
            for entry in connect_entries.load_entries(kind):
                callback = entry.get("callback")
                if entry.get("type") == "entry" and callable(callback):
                    register_command(entry["id"], callback)

        registry.register_choice_setting_commands()
        _DISCOVERY_COMPLETE = True
    finally:
        _DISCOVERY_IN_PROGRESS = False

def has_command(name: str) -> bool:
    _discover_commands()
    return name in _COMMANDS


def list_commands() -> list[str]:
    _discover_commands()
    return sorted(_COMMANDS)


def operation_policy(name: str) -> OperationPolicy:
    """Return the standardized execution policy for a registered command."""
    _discover_commands()
    command = _COMMANDS.get(name)
    return (
        command.policy
        if command
        else _policy_from_definition(name, {"type": "tool"})
    )


def execute_command(name: str, *args, **kwargs):
    """Execute a discovered command through its standardized operation."""
    _discover_commands()
    command = _COMMANDS.get(name)
    if command:
        return command.dispatch(*args, **kwargs)

    from TheKeyMachine.tools.custom_tools import service as connect_entries

    if connect_entries.is_entry_command(name):
        return connect_entries.execute_entry_command(name)
    raise AttributeError("Unknown TheKeyMachine trigger command: {}".format(name))


def command_name_for_callback(callback: Callable) -> Optional[str]:
    """Return the command identity associated with a callback."""
    if not callable(callback):
        return None
    if getattr(callback, "_tkm_trigger_proxy", False):
        return getattr(callback, "__name__", None)

    _discover_commands()
    for command_name, command in _COMMANDS.items():
        if callback is command.dispatch or callback is command.callback:
            return command_name
    return None


def make_command_callback(name: str, callback: Optional[Callable] = None) -> Callable:
    """Return a stable proxy suitable for widgets, Maya hotkeys, and shelves."""
    if callback is not None:
        register_command(name, callback)

    def _proxy(*args, **kwargs):
        return execute_command(name, *args, **kwargs)

    _proxy.__name__ = name
    _proxy._tkm_trigger_proxy = True
    return _proxy


def command_string(name: str, *args) -> str:
    """Return a Maya-friendly Python command string."""
    if not isinstance(name, str) or not name:
        raise ValueError("Trigger commands require a non-empty string name")
    serialized_args = ", ".join(repr(arg) for arg in args)
    return (
        "from TheKeyMachine.core import trigger; "
        "trigger.execute_command({!r}{}{})".format(
            name,
            ", " if serialized_args else "",
            serialized_args,
        )
    )


def slider_command_name(prefix: str, mode: str, value: int = 0) -> str:
    base_command_name = "slider_{}_{}".format(prefix, mode)
    value = int(value)
    if value == 0:
        return base_command_name
    suffix = "neg{}".format(abs(value)) if value < 0 else str(value)
    return "{}_{}".format(base_command_name, suffix)
