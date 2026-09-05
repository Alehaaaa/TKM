"""Immutable recovery data: value files reference shared metadata by filename.

A checkpoint is the commit record. Dependencies are flushed before publishing it,
so an interrupted write never exposes a partially committed checkpoint.
"""
import hashlib
import json
import os
import threading
import zlib

VERSION = 8
VALUE_FIELDS = {
    "curves": ("positions", "values", "tangents", "weighted_tangents",
               "pre_infinity", "post_infinity"),
    "objects": ("attributes",),
    "layers": ("weight", "mute", "solo", "override", "passthrough", "lock",
               "rotation_accumulation_mode", "scale_accumulation_mode"),
}


def _encode(value):
    return json.dumps(value, sort_keys=True, ensure_ascii=False,
                      separators=(",", ":"), allow_nan=False).encode("utf-8")


def atomic_write(path, data):
    os.makedirs(os.path.dirname(path), exist_ok=True)
    temporary = path + ".tmp"
    try:
        with open(temporary, "wb") as stream:
            stream.write(data)
            stream.flush()
            os.fsync(stream.fileno())
        os.replace(temporary, path)
    finally:
        if os.path.exists(temporary):
            os.remove(temporary)


def _put(folder, value, suffix, prefix=""):
    data = _encode(value)
    name = prefix + hashlib.sha256(data).hexdigest() + suffix
    path = os.path.join(folder, name)
    if not os.path.exists(path):
        atomic_write(path, zlib.compress(data, 1))
    return name


def _read(folder, name):
    if not isinstance(name, str) or os.path.basename(name) != name:
        raise ValueError("Invalid recovery dependency")
    with open(os.path.join(folder, name), "rb") as stream:
        data = zlib.decompress(stream.read())
    expected = name.rsplit(".", 2)[-2]
    if hashlib.sha256(data).hexdigest() != expected:
        raise ValueError("Corrupt recovery dependency: " + name)
    return json.loads(data.decode("utf-8"))


def _split_values(value, leaves):
    if isinstance(value, dict):
        return {key: _split_values(item, leaves) for key, item in sorted(value.items())}
    index = len(leaves)
    leaves.append(value)
    return index


def _join_values(layout, leaves):
    if isinstance(layout, dict):
        return {key: _join_values(item, leaves) for key, item in layout.items()}
    return leaves[layout]


def write(path, payload, reason_byte):
    folder = os.path.dirname(path)
    manifest = {"meta": payload["meta"],
                "removed_curves": payload.get("removed_curves") or []}
    for kind, fields in VALUE_FIELDS.items():
        references = []
        for item in payload.get(kind) or []:
            metadata = {key: value for key, value in item.items() if key not in fields}
            # Field names live with object metadata; data files contain only values.
            leaves = []
            layout = _split_values({key: item[key] for key in fields if key in item}, leaves)
            metadata_id = _put(os.path.join(folder, "metadata"),
                               [metadata, layout], ".jsonz").split(".")[0]
            references.append(_put(os.path.join(folder, "values"),
                                   leaves, ".animdata",
                                   metadata_id + "."))
        manifest[kind] = references
    atomic_write(path, bytes((VERSION, reason_byte)) + zlib.compress(_encode(manifest), 1))


def read_manifest(path):
    with open(path, "rb") as stream:
        data = stream.read()
    return json.loads(zlib.decompress(data[2:]).decode("utf-8"))


def read(path):
    manifest = read_manifest(path)
    folder = os.path.dirname(path)
    payload = {"meta": manifest["meta"], "removed_curves": manifest["removed_curves"]}
    for kind in VALUE_FIELDS:
        items = []
        for name in manifest[kind]:
            values = _read(os.path.join(folder, "values"), name)
            metadata, layout = _read(os.path.join(folder, "metadata"),
                                     name.split(".")[0] + ".jsonz")
            items.append(dict(metadata, **_join_values(layout, values)))
        payload[kind] = items
    return payload


def prune_dependencies(folder, checkpoints):
    """Collect immutable data only after all retained commit records are read."""
    values = set()
    for checkpoint in checkpoints:
        manifest = read_manifest(checkpoint)
        for kind in VALUE_FIELDS:
            values.update(manifest[kind])
    metadata = {name.split(".")[0] + ".jsonz" for name in values}
    for subfolder, live, suffix in (("values", values, ".animdata"),
                                    ("metadata", metadata, ".jsonz")):
        directory = os.path.join(folder, subfolder)
        if not os.path.isdir(directory):
            continue
        for name in os.listdir(directory):
            if name.endswith(suffix) and name not in live:
                os.remove(os.path.join(directory, name))


def dependencies_exist(path):
    """Cheap startup check; full integrity validation runs in the reader worker."""
    manifest = read_manifest(path)
    folder = os.path.dirname(path)
    for kind in VALUE_FIELDS:
        for name in manifest[kind]:
            if os.path.basename(name) != name:
                return False
            if not os.path.isfile(os.path.join(folder, "values", name)):
                return False
            if not os.path.isfile(os.path.join(folder, "metadata", name.split(".")[0] + ".jsonz")):
                return False
    return True


_STATE_LOCK = threading.RLock()


def recovery_state(root):
    """Small shared state for the latest tracked event and dismissed offers."""
    with _STATE_LOCK:
        try:
            with open(os.path.join(root, "recovery-state.json"), "rb") as stream:
                state = json.load(stream)
                return state if isinstance(state, dict) else {}
        except (OSError, ValueError):
            return {}


def update_recovery_state(root, event=None, dismissed=()):
    # Serialize worker checkpoint commits and main-thread close/crash callbacks.
    # Event time, rather than write completion order, determines what is latest.
    with _STATE_LOCK:
        state = recovery_state(root)
        latest = state.get("latest") or {}
        if event and event["timestamp"] >= latest.get("timestamp", 0):
            state["latest"] = event
        if dismissed:
            state["dismissed"] = sorted(set(state.get("dismissed", [])) | set(dismissed))
        atomic_write(os.path.join(root, "recovery-state.json"), _encode(state))
