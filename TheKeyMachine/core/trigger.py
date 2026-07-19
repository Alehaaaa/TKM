"""Command discovery and dispatch for tools, hotkeys, and shelf buttons."""

from __future__ import annotations

import importlib
import inspect
import keyword
from dataclasses import dataclass
from functools import wraps
from typing import Callable, Dict, Optional


SLIDER_BUTTON_VALUES = (-150, -125, -105, -100, -50, -15, -5, 0, 5, 15, 50, 100, 105, 125, 150)

_COMMANDS: Dict[str, Callable] = {}
_COMMAND_POLICIES: Dict[str, "OperationPolicy"] = {}
_SLIDER_EXECUTORS: Dict[str, Callable] = {}
_DISCOVERY_COMPLETE = False
_DISCOVERY_IN_PROGRESS = False


@dataclass(frozen=True)
class OperationPolicy:
    progress: bool = True
    undo: bool = True
    suspend_refresh: bool = False


def _policy_from_definition(command_name: str, definition, callback: Optional[Callable] = None) -> OperationPolicy:
    explicit = (definition or {}).get("operation") or {}
    if explicit:
        return OperationPolicy(
            progress=bool(explicit.get("progress", True)),
            undo=bool(explicit.get("undo", True)),
            suspend_refresh=bool(explicit.get("suspend_refresh", False)),
        )
    if getattr(callback, "_tkm_non_tool_action", False):
        return OperationPolicy(progress=False, undo=False)
    interactive = (definition or {}).get("type") == "menu" or command_name.endswith(("_menu", "_window"))
    return OperationPolicy(progress=not interactive, undo=not interactive)


def register_command(name: str, callback: Callable, policy: Optional[OperationPolicy] = None) -> Callable:
    """Register a callable behind the shared tool-operation boundary."""
    if not name or not callable(callback):
        raise ValueError("Commands require a name and callable callback")
    if policy is not None:
        _COMMAND_POLICIES[name] = policy
    elif name not in _COMMAND_POLICIES:
        _COMMAND_POLICIES[name] = _policy_from_definition(name, {}, callback)

    if getattr(callback, "_tkm_tool_dispatch", False) and getattr(callback, "_tkm_command_name", None) == name:
        dispatched = callback
    else:
        dispatched = _make_dispatched_command(name, callback)
    _COMMANDS[name] = dispatched
    return dispatched


def reset_registry() -> None:
    """Discard discovered commands and package-backed executors for reload."""
    global _DISCOVERY_COMPLETE, _DISCOVERY_IN_PROGRESS
    _COMMANDS.clear()
    _COMMAND_POLICIES.clear()
    _SLIDER_EXECUTORS.clear()
    _DISCOVERY_COMPLETE = False
    _DISCOVERY_IN_PROGRESS = False


def _make_dispatched_command(name: str, callback: Callable) -> Callable:
    @wraps(callback)
    def _dispatch(*args, **kwargs):
        from TheKeyMachine.tools import common as toolCommon

        label = kwargs.pop("_tkm_tool_label", None)
        anchor_widget = kwargs.pop("_tkm_anchor_widget", None)
        kwargs.pop("tool_operation", None)
        policy = _COMMAND_POLICIES.get(name) or _policy_from_definition(name, {}, callback)
        with toolCommon.tool_operation(
            tool_id=name,
            label=label,
            anchor_widget=anchor_widget,
            progress=policy.progress,
            undo=policy.undo,
            suspend_refresh=policy.suspend_refresh,
        ) as operation:
            call_kwargs = dict(kwargs)
            call_kwargs.setdefault("anchor_widget", anchor_widget)
            call_kwargs.setdefault("tool_operation", operation)
            return callback(*args, **_supported_callback_kwargs(callback, call_kwargs))

    _dispatch.__name__ = name
    _dispatch._tkm_tool_dispatch = True
    _dispatch._tkm_command_name = name
    _dispatch._tkm_registered_callback = callback
    return _dispatch


def _discover_commands() -> None:
    global _DISCOVERY_COMPLETE, _DISCOVERY_IN_PROGRESS
    if _DISCOVERY_COMPLETE or _DISCOVERY_IN_PROGRESS:
        return

    _DISCOVERY_IN_PROGRESS = True
    try:
        from TheKeyMachine.core import toolbox

        for tool_id, definition in toolbox.get_tool_definitions().items():
            callback = definition.get("callback")
            if callable(callback):
                register_command(
                    tool_id,
                    callback,
                    policy=_policy_from_definition(tool_id, definition, callback),
                )

        for section_id, section in toolbox.get_section_definitions().items():
            if section.get("type") == "slider":
                _register_slider_section(section_id, section)
        _DISCOVERY_COMPLETE = True
    finally:
        _DISCOVERY_IN_PROGRESS = False


def _register_slider_section(section_id: str, section) -> None:
    prefix = section.get("slider_type")
    package_name = section.get("_package")
    if not prefix or not package_name:
        raise RuntimeError("Slider section {!r} is missing its type or owning package".format(section_id))

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
        if not mode_key:
            continue
        for value in SLIDER_BUTTON_VALUES:
            command_name = slider_command_name(prefix, mode_key, value)
            register_command(command_name, _slider_callback(execute, mode_key, value))


def _slider_callback(execute: Callable, mode: str, value: int) -> Callable:
    def _execute_slider_mode(session=None):
        return execute(mode, value, session=session)

    return _execute_slider_mode


def get_command(name: str) -> Optional[Callable]:
    _discover_commands()
    return _COMMANDS.get(name)


def execute_command(name: str, *args, **kwargs):
    """Execute a discovered command through its standardized operation."""
    callback = get_command(name)
    if callback is None:
        from TheKeyMachine.core import connectEntries

        if connectEntries.is_entry_command(name):
            return connectEntries.execute_entry_command(name)
        raise AttributeError("Unknown TheKeyMachine trigger command: {}".format(name))
    return callback(*args, **kwargs)


def list_commands() -> list[str]:
    _discover_commands()
    return sorted(_COMMANDS)


def has_command(name: str) -> bool:
    _discover_commands()
    return name in _COMMANDS


def command_name_for_callback(callback: Callable) -> Optional[str]:
    """Return the command identity associated with a callback."""
    if not callable(callback):
        return None
    if getattr(callback, "_tkm_trigger_proxy", False):
        return getattr(callback, "__name__", None)

    _discover_commands()
    for command_name, dispatched in _COMMANDS.items():
        registered = getattr(dispatched, "_tkm_registered_callback", None)
        if callback is dispatched or callback is registered:
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
    if not name.isidentifier() or keyword.iskeyword(name):
        raise ValueError("Trigger command is not a valid Python attribute: {}".format(name))
    serialized_args = ", ".join(repr(arg) for arg in args)
    return "import TheKeyMachine.core as TKM_CORE; TKM_CORE.trigger.{}({})".format(name, serialized_args)


def execute_slider(prefix: str, mode: str, value: int = 0, session=None):
    """Execute a slider through the API owned by its discovered tool package."""
    _discover_commands()
    execute = _SLIDER_EXECUTORS.get(prefix)
    if execute is None:
        raise ValueError("Unknown slider type: {}".format(prefix))
    return execute(mode, value, session=session)


def register_slider_mode(prefix: str, mode: str) -> None:
    """Register command variants for an already-discovered slider type."""
    _discover_commands()
    execute = _SLIDER_EXECUTORS.get(prefix)
    if execute is None:
        raise ValueError("Unknown slider type: {}".format(prefix))
    for value in SLIDER_BUTTON_VALUES:
        register_command(slider_command_name(prefix, mode, value), _slider_callback(execute, mode, value))


def slider_command_name(prefix: str, mode: str, value: int = 0) -> str:
    base_command_name = "slider_{}_{}".format(prefix, mode)
    value = int(value)
    if value == 0:
        return base_command_name
    return "{}_{}".format(base_command_name, _slider_value_suffix(value))


def _supported_callback_kwargs(callback: Callable, kwargs):
    if not kwargs:
        return kwargs
    try:
        parameters = inspect.signature(callback).parameters.values()
    except Exception:
        return kwargs
    if any(parameter.kind == inspect.Parameter.VAR_KEYWORD for parameter in parameters):
        return kwargs
    supported = {
        parameter.name
        for parameter in parameters
        if parameter.kind in (inspect.Parameter.POSITIONAL_OR_KEYWORD, inspect.Parameter.KEYWORD_ONLY)
    }
    return {key: value for key, value in kwargs.items() if key in supported}


def _slider_value_suffix(value: int) -> str:
    value = int(value)
    return "neg{}".format(abs(value)) if value < 0 else str(value)


def __getattr__(name: str):
    if has_command(name):
        return make_command_callback(name)
    from TheKeyMachine.core import connectEntries

    if connectEntries.is_entry_command(name):
        return make_command_callback(name)
    raise AttributeError(name)
