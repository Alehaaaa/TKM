"""Manifest discovery and execution for user-defined tools."""

from importlib import import_module, invalidate_caches, reload
import os
import re
import shutil

from maya import cmds, mel

from TheKeyMachine.Qt import QtCore
from TheKeyMachine.data import icons
import TheKeyMachine.mods.generalMod as general


PACKAGE_ROOT = os.path.dirname(os.path.dirname(__file__))
USER_DATA_PACKAGE = "TheKeyMachine_user_data"
USER_CONNECT_PACKAGE = USER_DATA_PACKAGE + ".connect"
CALLABLE_REFERENCE = re.compile(r"^[A-Za-z_]\w*(?:\.[A-Za-z_]\w*)*:[A-Za-z_]\w*(?:\.[A-Za-z_]\w*)*$")

SOURCES = {
    "tools": {
        "package": USER_CONNECT_PACKAGE + ".tools",
        "module": USER_CONNECT_PACKAGE + ".tools.manifest",
        "registry": "TOOLS",
        "folder": "TheKeyMachine_user_data/connect/tools",
        "file": "manifest.py",
        "label": "Custom Tools",
        "namespace": "custom_tools_toolbar",
        "folder_tool_id": "custom_tools",
    },
}


class ConnectEntriesBus(QtCore.QObject):
    entriesChanged = QtCore.Signal(str)


connect_entries_bus = ConnectEntriesBus()
_signatures = {}


def source_spec(kind):
    if kind not in SOURCES:
        raise KeyError("Unknown custom entry source: {}".format(kind))
    return SOURCES[kind]


def entry_key(kind, source_id):
    return "custom_{}_{}".format(kind, source_id)


def _user_path(relative_path):
    return os.path.normpath(os.path.join(general.USER_FOLDER_PATH, relative_path))


def source_folder(kind):
    return _user_path(source_spec(kind)["folder"])


def _ensure_package(directory):
    os.makedirs(directory, exist_ok=True)
    init_file = os.path.join(directory, "__init__.py")
    if not os.path.exists(init_file):
        with open(init_file, "a", encoding="utf-8"):
            pass


def _copy_missing_tree(source, destination):
    if not os.path.isdir(source):
        return
    for root, directories, filenames in os.walk(source):
        directories[:] = [name for name in directories if name != "__pycache__"]
        relative_root = os.path.relpath(root, source)
        destination_root = destination if relative_root == "." else os.path.join(destination, relative_root)
        os.makedirs(destination_root, exist_ok=True)
        for filename in filenames:
            if filename.endswith((".pyc", ".pyo")):
                continue
            destination_file = os.path.join(destination_root, filename)
            if not os.path.exists(destination_file):
                shutil.copy2(os.path.join(root, filename), destination_file)


def ensure_connect_workspace():
    """Create each custom package and seed its template on first use."""
    user_data_root = _user_path(USER_DATA_PACKAGE)
    connect_root = _user_path(USER_CONNECT_PACKAGE.replace(".", "/"))
    _ensure_package(user_data_root)
    _ensure_package(connect_root)

    for kind in SOURCES:
        destination = source_folder(kind)
        _ensure_package(destination)
        manifest = os.path.join(destination, source_spec(kind)["file"])
        if not os.path.isfile(manifest):
            _copy_missing_tree(os.path.join(PACKAGE_ROOT, "connect", kind), destination)
    invalidate_caches()


def _load_module(module_name):
    invalidate_caches()
    module = import_module(module_name)
    return reload(module)


def _resolve_icon(kind, icon):
    if not icon:
        return None
    if not isinstance(icon, str):
        return icon
    # Maya exposes built-in Qt resources with paths such as :/mel_tab.png.
    if icon.startswith(":/"):
        return icon
    if icon.startswith("icons."):
        return icons.get(icon.split(".", 1)[1])
    if os.path.isabs(icon):
        return icon

    local_icon = os.path.normpath(os.path.join(source_folder(kind), icon))
    if os.path.isfile(local_icon):
        return local_icon
    return icons.get(icon, local_icon)


def _qualified_module_name(kind, module_name):
    package = source_spec(kind)["package"]
    if module_name.startswith("."):
        return package + module_name
    if module_name.startswith(USER_DATA_PACKAGE + ".") or module_name.startswith("TheKeyMachine."):
        return module_name
    return package + "." + module_name


def _call_target(kind, target, args=None, kwargs=None):
    if ":" not in target:
        raise ValueError("Callable references must use 'module:function': {}".format(target))
    module_name, attribute_path = target.rsplit(":", 1)
    module = _load_module(_qualified_module_name(kind, module_name))
    callback = module
    for attribute in attribute_path.split("."):
        callback = getattr(callback, attribute)
    if not callable(callback):
        raise TypeError("Custom entry target is not callable: {}".format(target))
    return callback(*(args or ()), **(kwargs or {}))


def _execute(kind, run_spec):
    if callable(run_spec):
        return run_spec()
    if isinstance(run_spec, str):
        if CALLABLE_REFERENCE.fullmatch(run_spec):
            return _call_target(kind, run_spec)
        namespace = {"__name__": "__tkm_custom_entry__", "cmds": cmds, "mel": mel}
        exec(run_spec, namespace, namespace)
        return None
    if not isinstance(run_spec, dict):
        raise TypeError("Custom entry 'run' must be callable, a string, or a dictionary")
    if "call" in run_spec:
        return _call_target(kind, run_spec["call"], run_spec.get("args"), run_spec.get("kwargs"))
    if "python" in run_spec:
        namespace = {"__name__": "__tkm_custom_entry__", "cmds": cmds, "mel": mel}
        exec(run_spec["python"], namespace, namespace)
        return None
    if "mel" in run_spec:
        return mel.eval(run_spec["mel"])
    raise ValueError("Custom entry 'run' dictionary requires 'call', 'python', or 'mel'")


def _entry_callback(kind, run_spec):
    return lambda: _execute(kind, run_spec)


def _manifest_entries(kind):
    spec = source_spec(kind)
    module = _load_module(spec["module"])
    registry = getattr(module, spec["registry"], None)
    if not isinstance(registry, dict):
        raise TypeError("{}.{} must be a dictionary".format(spec["module"], spec["registry"]))

    entries = []
    for name, definition in registry.items():
        if not isinstance(definition, dict) or definition.get("enabled", True) is False:
            continue
        run_spec = definition.get("run")
        if run_spec is None and "mel" in definition:
            run_spec = {"mel": definition["mel"]}
        if run_spec is None:
            continue
        label = str(name)
        source_id = str(definition.get("id", label))
        icon = _resolve_icon(kind, definition.get("icon"))
        button_text = "".join(character for character in label if character.isalnum())[:3].upper()
        entries.append(
            {
                "type": "entry",
                "kind": kind,
                "source_id": source_id,
                "id": entry_key(kind, source_id),
                "label": label,
                "icon": icon,
                "text": None if icon else button_text,
                "run": run_spec,
                "callback": _entry_callback(kind, run_spec),
            }
        )

    return entries


def _signature_value(value):
    if callable(value):
        return (getattr(value, "__module__", ""), getattr(value, "__qualname__", repr(value)))
    if isinstance(value, dict):
        return tuple(sorted((key, _signature_value(item)) for key, item in value.items()))
    if isinstance(value, (list, tuple)):
        return tuple(_signature_value(item) for item in value)
    return value


def _signature(entries):
    return tuple(
        (
            entry.get("source_id"),
            entry.get("label"),
            entry.get("icon"),
            entry.get("text"),
            _signature_value(entry.get("run")),
        )
        for entry in entries
    )


def load_entries(kind, notify=False):
    ensure_connect_workspace()
    try:
        entries = _manifest_entries(kind)
    except (ImportError, AttributeError, RuntimeError, ValueError, TypeError, SyntaxError) as error:
        cmds.warning("Could not load custom {}: {}".format(kind, error))
        entries = []

    signature = _signature(entries)
    previous = _signatures.get(kind)
    _signatures[kind] = signature
    if notify and previous is not None and signature != previous:
        connect_entries_bus.entriesChanged.emit(kind)
    return entries
