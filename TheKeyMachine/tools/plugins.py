"""Prebuilt native Maya plug-in selection, loading, validation, and cleanup."""

import contextlib
import logging
import os
import platform
import re
import sys

from maya import cmds, mel


_PLUGIN_SPECS = {}


def maya_major_version(value=None):
    """Return the four-digit Maya release used by the native binary matrix."""
    value = cmds.about(version=True) if value is None else value
    match = re.search(r"\d{4}", str(value))
    if not match:
        raise RuntimeError("Could not determine the Maya version from {!r}.".format(value))
    return match.group(0)


def platform_name(value=None):
    value = sys.platform if value is None else str(value)
    if value == "win32":
        return "windows"
    if value == "darwin":
        return "macos"
    if value.startswith("linux"):
        return "linux"
    raise RuntimeError("Native plug-ins do not support platform {!r}.".format(value))


def architecture_name(value=None):
    value = platform.machine() if value is None else value
    normalized = str(value).strip().lower()
    if normalized in ("amd64", "x64", "x86_64"):
        return "x86_64"
    if normalized in ("aarch64", "arm64"):
        return "arm64"
    raise RuntimeError("Native plug-ins do not support architecture {!r}.".format(value))


class NativePluginSpec(object):
    def __init__(
        self,
        *,
        label,
        plugin_directory,
        output_name,
        registry_name,
        required_commands=(),
        build_command=None,
        expected_build=None,
        expected_build_file="build-id.txt",
        context_fallbacks=None,
    ):
        self.label = str(label)
        self.plugin_directory = os.path.realpath(plugin_directory)
        self.output_name = str(output_name)
        self.registry_name = str(registry_name)
        self.required_commands = tuple(required_commands)
        self.build_command = build_command
        self.expected_build = expected_build
        self.expected_build_file = expected_build_file
        self.context_fallbacks = dict(context_fallbacks or {})

        current_platform = platform_name()
        current_architecture = architecture_name()
        extension = {
            "macos": ".bundle",
            "windows": ".mll",
            "linux": ".so",
        }[current_platform]
        self.build_directory = os.path.join(
            self.plugin_directory,
            "__builds__",
            "{}-{}".format(current_platform, current_architecture),
            "maya{}".format(maya_major_version()),
        )
        self.path = os.path.join(self.build_directory, self.output_name + extension)
        if self.expected_build is None and self.expected_build_file:
            manifest = os.path.join(self.build_directory, self.expected_build_file)
            if os.path.isfile(manifest):
                with open(manifest, "r") as stream:
                    self.expected_build = stream.read().strip() or None
        _PLUGIN_SPECS[self.registry_name] = self


def normalized_path(path):
    return os.path.normcase(os.path.realpath(path))


def command_exists(command_name):
    return bool(command_name and mel.eval('exists "{}"'.format(command_name)))


def context_exists(context_name):
    try:
        return bool(cmds.contextInfo(context_name, exists=True))
    except Exception:
        return False


def delete_context(context_name):
    if not context_exists(context_name):
        return False
    try:
        cmds.deleteUI(context_name, toolContext=True)
        return True
    except Exception:
        return False


def create_context(spec, command_name, context_name):
    for value in (command_name, context_name):
        if not str(value).replace("_", "").isalnum():
            raise ValueError("Invalid {} context identifier: {}".format(spec.label, value))
    try:
        mel.eval('{} "{}"'.format(command_name, context_name))
    except RuntimeError as error:
        raise RuntimeError(
            "{} plug-in could not create {} using {}: {}".format(
                spec.label, context_name, command_name, error
            )
        )


def loaded_plugin(spec):
    expected_path = normalized_path(spec.path)
    for plugin_name in cmds.pluginInfo(query=True, listPlugins=True) or []:
        try:
            if not cmds.pluginInfo(plugin_name, query=True, loaded=True):
                continue
            if normalized_path(cmds.pluginInfo(plugin_name, query=True, path=True)) == expected_path:
                return plugin_name
        except (RuntimeError, TypeError):
            continue
    return None


def plugin_build_id(spec):
    if not spec.build_command:
        return None
    result = getattr(cmds, spec.build_command)()
    if isinstance(result, (list, tuple)):
        result = result[0] if result else ""
    return str(result)


def is_ready(spec):
    if not loaded_plugin(spec):
        return False
    if not all(command_exists(command) for command in spec.required_commands):
        return False
    if spec.expected_build is not None:
        try:
            return plugin_build_id(spec) == spec.expected_build
        except (RuntimeError, AttributeError, TypeError):
            return False
    return True


def _restore_context(spec):
    current = cmds.currentCtx()
    fallback = spec.context_fallbacks.get(current)
    if fallback:
        try:
            cmds.setToolTo(fallback)
        except Exception:
            pass


class _IgnorePyNodeCleanupWarning(logging.Filter):
    """Match only PyMEL's benign 'no PyNode registered' cleanup warning."""

    _NEEDLE = "could not find an associated PyNode registered"

    def filter(self, record):
        return self._NEEDLE not in record.getMessage()


@contextlib.contextmanager
def _suppress_pymel_node_cleanup_warnings():
    """Silence PyMEL's benign node-cleanup warning during plug-in unload.

    When a plug-in that registers custom node types (e.g. manipulator
    containers) is unloaded, PyMEL's own bookkeeping in
    ``pymel.internal.factories`` tries to remove a matching PyNode class for
    each type. Node types that were never wrapped with ``pm.PyNode(...)``
    (true here, since TKM uses ``maya.api.OpenMaya`` / ``cmds`` and PyMEL is
    only ever an incidental, third-party import in the session) have no such
    class to remove, so PyMEL logs a warning even though nothing is wrong.

    Only touch the logger if PyMEL is actually loaded, and use a message
    filter rather than raising the log level so any other, genuinely useful
    warning that ``pymel.internal.factories`` might log during the same
    call still comes through untouched.
    """
    if "pymel.internal.factories" not in sys.modules:
        yield
        return
    pymel_logger = logging.getLogger("pymel.internal.factories")
    node_cleanup_filter = _IgnorePyNodeCleanupWarning()
    pymel_logger.addFilter(node_cleanup_filter)
    try:
        yield
    finally:
        if node_cleanup_filter in pymel_logger.filters:
            pymel_logger.removeFilter(node_cleanup_filter)


def unload(spec, restore_context=True):
    if restore_context:
        _restore_context(spec)
    for context_name in spec.context_fallbacks:
        delete_context(context_name)

    plugin_name = loaded_plugin(spec)
    if not plugin_name:
        return False
    with _suppress_pymel_node_cleanup_warnings():
        cmds.unloadPlugin(plugin_name)
    if plugin_name in (cmds.pluginInfo(query=True, listPlugins=True) or []):
        try:
            cmds.pluginInfo(plugin_name, edit=True, remove=True)
        except RuntimeError:
            pass
    return True


def load(spec, force_reload=False):
    if is_ready(spec) and not force_reload:
        return loaded_plugin(spec)

    if not os.path.isfile(spec.path):
        raise RuntimeError(
            "{} has no prebuilt plug-in for Maya {} on {}-{}. "
            "Install a complete TKM release containing the native binary matrix.".format(
                spec.label,
                maya_major_version(),
                platform_name(),
                architecture_name(),
            )
        )

    if loaded_plugin(spec):
        unload(spec, restore_context=True)
    loaded_names = cmds.loadPlugin(spec.path, name=spec.registry_name, quiet=True)
    plugin_name = loaded_names[0] if loaded_names else loaded_plugin(spec)

    try:
        missing = [command for command in spec.required_commands if not command_exists(command)]
        if missing:
            raise RuntimeError(
                "{} plug-in {} loaded but did not register: {}".format(
                    spec.label, plugin_name or spec.path, ", ".join(missing)
                )
            )
        if spec.expected_build is not None:
            loaded_build = plugin_build_id(spec)
            if loaded_build != spec.expected_build:
                raise RuntimeError(
                    "{} loaded stale native code: expected {}, Maya reported {}.".format(
                        spec.label, spec.expected_build, loaded_build
                    )
                )
    except Exception as validation_error:
        try:
            unload(spec, restore_context=True)
        except Exception as rollback_error:
            raise RuntimeError(
                "{} Validation failed and rollback was incomplete: {}".format(
                    validation_error, rollback_error
                )
            ) from validation_error
        raise
    return plugin_name


def ensure_contexts(spec, context_commands, configure_command=None, configure_args=()):
    """Load, configure, and recreate a native tool's Maya contexts."""
    pairs = tuple(context_commands)
    load(spec)
    if configure_command:
        if not command_exists(configure_command):
            raise RuntimeError(
                "{} plug-in did not register {}.".format(spec.label, configure_command)
            )
        getattr(cmds, configure_command)(*tuple(configure_args))

    for _command_name, context_name in pairs:
        delete_context(context_name)

    created = []
    try:
        for command_name, context_name in pairs:
            create_context(spec, command_name, context_name)
            created.append(context_name)
    except Exception:
        for context_name in reversed(created):
            delete_context(context_name)
        raise
    return tuple(created)


def shutdown_all():
    for spec in reversed(tuple(_PLUGIN_SPECS.values())):
        try:
            unload(spec, restore_context=True)
        except Exception:
            pass
