"""Shared per-rig snapshot store for opposite-control, default-pose and mirror data.

A rig is identified by the Maya node UUID of its topmost transform (its
"root group"), not by namespace or file path -- the same rig referenced under
a different namespace, or opened in a different Maya session/machine sharing
the user data folder, resolves to the same snapshot file. If a rig's root
transform is deleted and recreated (a full rebuild/re-export), its UUID
changes and any existing snapshot data becomes orphaned under the old id --
this is an inherent limitation of node-identity, not something this module
solves.

Only the explicit "Snapshot ..." toolbox actions persist analysis to disk
(via ``merge_control_entries``). Ordinary default/opposite/mirror operations
read a cached snapshot when one exists and otherwise analyze on the fly
in-memory only, through ``resolve_control_snapshot`` -- nothing is written
unless the user explicitly snapshots.
"""

import json
import os

from maya import cmds

import TheKeyMachine.mods.generalMod as general


MIRROR_PATTERNS = [
    ("R_", "L_"),
    ("L_", "R_"),
    ("_R", "_L"),
    ("_L", "_R"),
    ("_R_", "_L_"),
    ("_L_", "_R_"),
    ("r_", "l_"),
    ("l_", "r_"),
    ("_r_", "_l_"),
    ("_l_", "_r_"),
    ("_rt_", "_lf_"),
    ("_lf_", "_rt_"),
    ("_rg_", "_lf_"),
    ("_lf_", "_rg_"),
    ("_lf", "_rg"),
    ("_rg", "_lf"),
    ("RF_", "LF_"),
    ("LF_", "RF_"),
    ("left_", "right_"),
    ("right_", "left_"),
    ("_left", "_right_"),
    ("_right", "_left"),
    ("_left_", "_right_"),
    ("_right_", "_left_"),
]


# ____________________________ Opposite-name pattern matching ________________________


def opposite_control_name(name):
    """Return the configured opposite control name without querying the scene."""
    namespace, _, control_name = name.rpartition(":")
    for pattern, opposite_pattern in MIRROR_PATTERNS:
        if pattern in control_name:
            new_control_name = control_name.replace(pattern, opposite_pattern, 1)
            return f"{namespace}:{new_control_name}" if namespace else new_control_name
    return None


def find_opposite_name(name):
    """Return the configured opposite control when it exists in the scene."""
    opposite_name = opposite_control_name(name)
    return opposite_name if opposite_name and cmds.objExists(opposite_name) else None


def control_key(node):
    """Namespace- and path-stripped key used to index a control in a rig file."""
    return node.rsplit("|", 1)[-1].rpartition(":")[2]


# ____________________________ Rig identity ___________________________________________


def get_rig_root(node):
    """Walk ``node`` up to its topmost DAG ancestor -- treated as the rig's root."""
    current = node
    while True:
        parents = cmds.listRelatives(current, parent=True, fullPath=True) or []
        if not parents:
            return current
        current = parents[0]


def get_rig_id(node):
    """Return the rig's identity: the Maya node UUID of its root transform."""
    root = get_rig_root(node)
    uuids = cmds.ls(root, uuid=True) or []
    return uuids[0] if uuids else None


def group_controls_by_rig(nodes):
    """Split ``nodes`` by the rig (root UUID) each belongs to.

    Returns {rig_id: {"root": root, "controls": [nodes...]}}. A selection
    spanning multiple rigs is split so each rig gets its own group/file.
    """
    groups = {}
    for node in nodes:
        rig_id = get_rig_id(node)
        if not rig_id:
            continue
        group = groups.setdefault(rig_id, {"root": get_rig_root(node), "controls": []})
        group["controls"].append(node)
    return groups


# ____________________________ Snapshot store (disk) __________________________________


_CACHE = {}


def _rigs_folder():
    return general.get_tool_data_path("rig_snapshot", "rigs")


def _snapshot_path(rig_id):
    return os.path.join(_rigs_folder(), f"{rig_id}.json")


def _empty_snapshot(rig_id):
    return {
        "schema_version": 1,
        "rig_id": rig_id,
        "pairs": [],
        "centers": [],
        "defaults": {},
        "mirror_exceptions": {},
    }


def list_rig_ids():
    folder = _rigs_folder()
    if not os.path.isdir(folder):
        return []
    return [os.path.splitext(name)[0] for name in os.listdir(folder) if name.endswith(".json")]


def load_rig_snapshot(rig_id):
    if rig_id in _CACHE:
        return _CACHE[rig_id]
    data = _empty_snapshot(rig_id)
    path = _snapshot_path(rig_id)
    if os.path.isfile(path):
        try:
            with open(path, "r", encoding="utf-8") as stream:
                loaded = json.load(stream)
            if isinstance(loaded, dict):
                for key in data:
                    if key in loaded:
                        data[key] = loaded[key]
        except (OSError, ValueError, TypeError):
            pass
    _CACHE[rig_id] = data
    return data


def save_rig_snapshot(rig_id, data):
    path = _snapshot_path(rig_id)
    os.makedirs(os.path.dirname(path), exist_ok=True)
    with open(path, "w", encoding="utf-8") as stream:
        json.dump(data, stream, indent=4, sort_keys=True)
    _CACHE[rig_id] = data


def clear_section(rig_id, kind):
    data = load_rig_snapshot(rig_id)
    if kind == "opposite":
        data["pairs"] = []
        data["centers"] = []
    elif kind == "default":
        data["defaults"] = {}
    elif kind == "mirror":
        data["mirror_exceptions"] = {}
    else:
        raise ValueError(f"Unknown snapshot kind: {kind}")
    save_rig_snapshot(rig_id, data)


# ____________________________ Per-control read/write __________________________________


def _pair_partner(data, shortname):
    for pair in data.get("pairs", []):
        if shortname in pair:
            return pair[1] if pair[0] == shortname else pair[0]
    return None


def get_cached_entry(rig_id, shortname, kind):
    data = load_rig_snapshot(rig_id)
    if kind == "opposite":
        if shortname in data.get("centers", []):
            return ""  # analyzed, confirmed no opposite -- distinct from "not yet analyzed" (None)
        return _pair_partner(data, shortname)
    if kind == "default":
        return data.get("defaults", {}).get(shortname)
    if kind == "mirror":
        return data.get("mirror_exceptions", {}).get(shortname)
    raise ValueError(f"Unknown snapshot kind: {kind}")


def _merge_opposite_entries(data, entries):
    pairs = {tuple(sorted(pair)) for pair in data.get("pairs", [])}
    centers = set(data.get("centers", []))
    for shortname, opposite in entries.items():
        pairs = {pair for pair in pairs if shortname not in pair}
        centers.discard(shortname)
        if opposite:
            pairs = {pair for pair in pairs if opposite not in pair}
            centers.discard(opposite)
            pairs.add(tuple(sorted((shortname, opposite))))
        else:
            centers.add(shortname)
    data["pairs"] = sorted(list(pair) for pair in pairs)
    data["centers"] = sorted(centers)


def _merge_replace_entries(bucket, entries):
    for shortname, values in entries.items():
        if values:
            bucket[shortname] = values
        else:
            bucket.pop(shortname, None)


def _merge_attr_entries(bucket, entries):
    for shortname, values in entries.items():
        if not values:
            continue
        merged = dict(bucket.get(shortname, {}))
        merged.update(values)
        merged = {attr: value for attr, value in merged.items() if value is not None}
        if merged:
            bucket[shortname] = merged
        else:
            bucket.pop(shortname, None)


def merge_control_entries(rig_id, kind, entries):
    """Persist ``entries`` (``{shortname: value}``) for ``kind`` into the rig file.

    Only touches the given controls -- everything else in the file is left
    untouched, so re-snapshotting a couple of controls updates just those.
    """
    if not entries:
        return
    data = load_rig_snapshot(rig_id)
    if kind == "opposite":
        _merge_opposite_entries(data, entries)
    elif kind == "default":
        _merge_replace_entries(data.setdefault("defaults", {}), entries)
    elif kind == "mirror":
        _merge_attr_entries(data.setdefault("mirror_exceptions", {}), entries)
    else:
        raise ValueError(f"Unknown snapshot kind: {kind}")
    save_rig_snapshot(rig_id, data)


def resolve_control_snapshot(node, kind, compute_fn):
    """Read a cached snapshot entry for ``node``, or compute it in-memory only.

    This is the "instant snapshot" used by ordinary operations: a persisted
    rig file is consulted if one exists; otherwise ``compute_fn(node)`` runs
    and its result is returned WITHOUT being written to disk.
    """
    rig_id = get_rig_id(node)
    if rig_id is not None:
        cached = get_cached_entry(rig_id, control_key(node), kind)
        if cached is not None:
            return cached
    return compute_fn(node)


# ____________________________ Capture helpers (used by Snapshot actions) ______________


def capture_opposite(node):
    """Resolve node's opposite control, namespace-stripped, or None if it's a center."""
    opposite = find_opposite_name(node)
    return control_key(opposite) if opposite else None


def _differs_from_default(value, default_value):
    if isinstance(value, (int, float)) and isinstance(default_value, (int, float)):
        return abs(value - default_value) > 1e-9
    return value != default_value


def capture_default_values(node):
    """Capture only the attrs whose current value deviates from Maya's own default."""
    values = {}
    for attr in cmds.listAttr(node, keyable=True, unlocked=True, visible=True) or []:
        if attr == "tag":
            continue
        plug = f"{node}.{attr}"
        current = cmds.getAttr(plug)
        fallback = cmds.attributeQuery(attr, node=node, listDefault=True)
        default_value = fallback[0] if fallback else None
        if default_value is None or _differs_from_default(current, default_value):
            values[attr] = current
    return values
