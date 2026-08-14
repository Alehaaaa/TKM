"""Maya-runtime services used across TheKeyMachine.

This module owns Maya version capabilities, native plug-in lifecycle, and the
managed scene-node wrapper. OpenMaya helpers remain separately importable
because they intentionally support capability checks outside Maya.
"""

from __future__ import annotations


# Maya version capabilities
import functools
import re

from maya import cmds


@functools.lru_cache(maxsize=None)
def major_version(value=None):
    """Return the four-digit release from Maya or an explicit version value."""
    raw_value = cmds.about(version=True) if value is None else value
    match = re.search(r"20\d{2}", str(raw_value))
    if not match:
        raise RuntimeError(
            "Could not determine the Maya version from {!r}.".format(raw_value)
        )
    return int(match.group())


def is_at_least(version):
    """Return whether the running Maya release is at least ``version``."""
    try:
        return major_version() >= int(version)
    except Exception:
        return False


@functools.lru_cache(maxsize=1)
def supports_playback_selection():
    """Return whether editable playback-selection flags are actually available."""
    if not is_at_least(2024):
        return False
    try:
        cmds.playbackOptions(query=True, selectionVisible=True)
    except Exception:
        return False
    return True


# Native plug-in lifecycle
import contextlib
import logging
import os
import platform
import sys

from maya import cmds, mel


_PLUGIN_SPECS = {}


def maya_major_version(value=None):
    """Return the four-digit Maya release used by the native binary matrix."""
    return str(major_version(value))


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


# Managed scene nodes
from maya import cmds

import TheKeyMachine.core.application as general


ROOT_NAME = "TheKeyMachine"

_LOCKED_TRANSFORM_ATTRS = (
    "translateX", "translateY", "translateZ",
    "rotateX", "rotateY", "rotateZ",
    "scaleX", "scaleY", "scaleZ",
    "visibility",
)


class TkmSceneNode:
    """A single node in TheKeyMachine's scene-node hierarchy (the root or a child).

    Every instance simply wraps an existing Maya node name; the class does not
    cache or track renames. Use ``TkmSceneNode.root()`` to get (and lazily
    create) TheKeyMachine's root node, then call ``.child(...)`` on it to get
    or create tool-owned nodes underneath.
    """

    def __init__(self, name):
        self.name = name

    def __repr__(self):
        return "TkmSceneNode({!r})".format(self.name)

    def __eq__(self, other):
        return isinstance(other, TkmSceneNode) and self.name == other.name

    def __hash__(self):
        return hash(self.name)

    # ------------------------------------------------------------------
    # Construction
    # ------------------------------------------------------------------

    @classmethod
    def root(cls):
        """Return TheKeyMachine's root scene node, creating it if missing."""
        if not cmds.objExists(ROOT_NAME):
            node = cmds.createNode(
                "dagContainer", name=ROOT_NAME, skipSelect=True
            )
            cmds.setAttr(node + ".iconName", general.get_tkm_node_image(), type="string")
            cls(node).lock_transform()
            cmds.addAttr(
                node,
                longName="version",
                niceName="version",
                attributeType="enum",
                enumName="v{} {}".format(
                    general.get_thekeymachine_version(),
                    general.get_thekeymachine_stage_version(),
                ),
                keyable=True,
            )
            cmds.addAttr(
                node,
                longName="series",
                niceName="series",
                attributeType="enum",
                enumName=general.get_thekeymachine_codename(),
                keyable=True,
            )
        return cls(ROOT_NAME)

    @classmethod
    def root_exists(cls):
        """Return True without creating the root node (use before optional cleanup)."""
        return cmds.objExists(ROOT_NAME)

    def child(self, name, *, node_type="transform", lock_transform=False, icon=None):
        """Return the child node *name* under this node, creating/re-homing it as needed.

        Safe to call repeatedly: an existing node is reused, and if it was ever
        moved elsewhere in the scene it is re-parented back under this node.

        Pass *icon* (a path from ``TheKeyMachine.data.icons``) to give the node
        its owning tool's icon in the outliner, the same way ``root()`` stamps
        the TKM icon on the root node. Only ``dagContainer`` nodes support a
        custom outliner icon, so supplying *icon* creates the node as one
        regardless of *node_type*.
        """
        if not cmds.objExists(name):
            node = cmds.createNode(
                "dagContainer" if icon else node_type,
                name=name,
                skipSelect=True,
            )
            if icon:
                cmds.setAttr(node + ".iconName", icon, type="string")
            if lock_transform:
                TkmSceneNode(node).lock_transform()
        else:
            node = name

        current_parents = cmds.listRelatives(node, parent=True, fullPath=False) or []
        if not current_parents or current_parents[0] != self.name:
            cmds.parent(node, self.name)

        return TkmSceneNode(node)

    # ------------------------------------------------------------------
    # Introspection
    # ------------------------------------------------------------------

    @property
    def exists(self):
        return cmds.objExists(self.name)

    def children(self):
        """Return the direct children of this node as ``TkmSceneNode`` wrappers."""
        if not self.exists:
            return []
        return [TkmSceneNode(child) for child in cmds.listRelatives(self.name, children=True, fullPath=False) or []]

    def is_managed(self):
        """Return True if this node exists and lives under TheKeyMachine root."""
        if not self.exists:
            return False
        if self.name == ROOT_NAME:
            return True
        long_names = cmds.ls(self.name, long=True) or []
        return bool(long_names) and "|{}|".format(ROOT_NAME) in long_names[0]

    @staticmethod
    def info():
        """Return TheKeyMachine's version/build info (does not require the root node)."""
        return {
            "version": general.get_thekeymachine_version(),
            "stage": general.get_thekeymachine_stage_version(),
            "build": general.get_thekeymachine_build_version(),
            "codename": general.get_thekeymachine_codename(),
        }

    # ------------------------------------------------------------------
    # Attributes
    # ------------------------------------------------------------------

    def get_attr(self, attribute, default=None):
        plug = "{}.{}".format(self.name, attribute)
        if not cmds.objExists(plug):
            return default
        return cmds.getAttr(plug)

    def set_attr(self, attribute, value, **add_attr_kwargs):
        """Set a custom attribute on this node, adding it first if it doesn't exist yet.

        Refuses to touch the TKM root: the root only ever parents other tools'
        nodes and must stay free of tool-owned data. Create a child with
        ``TkmSceneNode.root().child(...)`` and stamp the attribute there instead.
        """
        if self.name == ROOT_NAME:
            raise RuntimeError(
                "TkmSceneNode: refusing to set '{}' on the TheKeyMachine root node. "
                "Tools must not store data on the shared root -- create a child node "
                "with root().child(your_node_name) and set the attribute there.".format(attribute)
            )
        plug = "{}.{}".format(self.name, attribute)
        if not cmds.objExists(plug):
            if isinstance(value, str) and "dataType" not in add_attr_kwargs and "attributeType" not in add_attr_kwargs:
                add_attr_kwargs["dataType"] = "string"
            cmds.addAttr(self.name, longName=attribute, **add_attr_kwargs)
        if isinstance(value, str) and cmds.getAttr(plug, type=True) == "string":
            cmds.setAttr(plug, value, type="string")
        else:
            cmds.setAttr(plug, value)

    # ------------------------------------------------------------------
    # Maintenance
    # ------------------------------------------------------------------

    def lock_transform(self):
        """Lock and hide the standard transform attributes (idempotent)."""
        for attr in _LOCKED_TRANSFORM_ATTRS:
            plug = "{}.{}".format(self.name, attr)
            if cmds.objExists(plug):
                cmds.setAttr(plug, lock=True, keyable=False, channelBox=False)

    def delete(self):
        """Delete this node. Refuses to delete the TKM root -- every tool's nodes
        hang off it, so only Maya (deleting the whole scene node) removes it."""
        if self.name == ROOT_NAME:
            raise RuntimeError(
                "TkmSceneNode: refusing to delete the TheKeyMachine root node. "
                "Delete the specific child node your tool owns instead."
            )
        if self.exists:
            cmds.delete(self.name)
