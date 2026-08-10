"""Snapshot Rig storage and analysis for opposite, default-pose, and mirror data.

A rig is identified by the Maya node UUID of its topmost transform (its
"root group"), not by namespace or file path -- the same rig referenced under
a different namespace, or opened in a different Maya session/machine sharing
the user data folder, resolves to the same UUID-named snapshot folder. If a
rig's root transform is deleted and recreated (a full rebuild/re-export), its UUID
changes and any existing snapshot data becomes orphaned under the old id --
this is an inherent limitation of node-identity, not something this module
solves.

Only the explicit "Snapshot ..." toolbox actions persist analysis to disk
(via ``merge_control_entries``). Ordinary default/opposite/mirror operations
read a cached snapshot when one exists and otherwise analyze on the fly
in-memory only, through ``resolve_control_snapshot`` -- nothing is written
unless the user explicitly snapshots.
"""

import copy
import json
import os
import tempfile
from contextlib import contextmanager

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

CENTER_INVERT_ATTRS = {"translateX", "rotateY", "rotateZ", "tx", "ry", "rz"}
_MIRROR_PROBE_DELTA = 0.1
_MIRROR_EFFECT_EPSILON = 1e-10
MIRROR_PROGRESS_WEIGHT = 4


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
    if opposite_name and cmds.objExists(opposite_name):
        return opposite_name

    # Long DAG paths keep the source control's parent path when the leaf name
    # is swapped. Left/right controls commonly live below different parent
    # groups, so that otherwise valid candidate does not exist. Resolve the
    # namespaced leaf independently, then keep the result within the source rig
    # when Maya reports more than one matching DAG node.
    leaf_name = name.rsplit("|", 1)[-1]
    if leaf_name == name:
        return None
    opposite_leaf = opposite_control_name(leaf_name)
    if not opposite_leaf:
        return None
    matches = cmds.ls(opposite_leaf, long=True) or []
    if len(matches) == 1:
        return matches[0]
    if not matches:
        return None

    source_root = get_rig_root(name)
    same_rig_matches = [match for match in matches if get_rig_root(match) == source_root]
    return same_rig_matches[0] if len(same_rig_matches) == 1 else None


def control_key(node):
    """Namespace- and path-stripped key used to index a snapshotted control."""
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
    spanning multiple rigs is split so each rig gets its own snapshot folder.
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
SNAPSHOT_KINDS = ("opposite", "default", "mirror")


def _snapshots_folder():
    return general.get_tool_data_path("rig_snapshot")


def _snapshot_folder(rig_id):
    if (not isinstance(rig_id, str) or not rig_id
            or rig_id in {".", ".."}
            or os.path.basename(rig_id) != rig_id):
        raise ValueError(f"Invalid rig snapshot id: {rig_id!r}")
    return os.path.join(_snapshots_folder(), rig_id)


def _section_path(rig_id, kind):
    if kind not in SNAPSHOT_KINDS:
        raise ValueError(f"Unknown snapshot kind: {kind}")
    return os.path.join(_snapshot_folder(rig_id), f"{kind}.json")


def _empty_snapshot():
    return {
        "pairs": [],
        "centers": [],
        "defaults": {},
        "mirror_directions": {},
    }


def _opposite_payload(data):
    opposites = {name: None for name in data.get("centers", [])}
    for pair in data.get("pairs", []):
        if isinstance(pair, (list, tuple)) and len(pair) == 2:
            opposites[pair[0]] = pair[1]
    return opposites


def _load_json_dict(path):
    try:
        with open(path, "r", encoding="utf-8") as stream:
            loaded = json.load(stream)
        return loaded if isinstance(loaded, dict) else {}
    except (OSError, ValueError, TypeError):
        return {}


def _load_control_map(path):
    return {
        name: values
        for name, values in _load_json_dict(path).items()
        if isinstance(name, str) and isinstance(values, dict)
    }


def _load_direction_map(path):
    directions = {}
    for name, values in _load_control_map(path).items():
        valid_values = {
            attr: direction
            for attr, direction in values.items()
            if (isinstance(attr, str) and not isinstance(direction, bool)
                and direction in (-1, 1))
        }
        if valid_values:
            directions[name] = valid_values
    return directions


def _write_json_dict(path, payload):
    """Atomically replace one compact snapshot section."""
    folder = os.path.dirname(path)
    os.makedirs(folder, exist_ok=True)
    descriptor, temporary_path = tempfile.mkstemp(
        prefix=".{}-".format(os.path.basename(path)), suffix=".tmp", dir=folder,
    )
    try:
        with os.fdopen(descriptor, "w", encoding="utf-8") as stream:
            json.dump(
                payload, stream,
                ensure_ascii=False, separators=(",", ":"), sort_keys=True,
            )
        os.replace(temporary_path, path)
    except Exception:
        try:
            os.close(descriptor)
        except OSError:
            pass
        try:
            os.remove(temporary_path)
        except OSError:
            pass
        raise


def list_rig_ids():
    folder = _snapshots_folder()
    if not os.path.isdir(folder):
        return []
    return sorted(
        name for name in os.listdir(folder)
        if os.path.isdir(os.path.join(folder, name))
        and any(
            os.path.isfile(_section_path(name, kind))
            for kind in SNAPSHOT_KINDS
        )
    )


def load_rig_snapshot(rig_id):
    if rig_id in _CACHE:
        return _CACHE[rig_id]
    data = _empty_snapshot()
    opposites = _load_json_dict(_section_path(rig_id, "opposite"))
    data["pairs"] = sorted(
        [name, opposite]
        for name, opposite in opposites.items()
        if isinstance(name, str) and isinstance(opposite, str)
    )
    data["centers"] = sorted(
        name for name, opposite in opposites.items()
        if isinstance(name, str) and opposite is None
    )
    data["defaults"] = _load_control_map(_section_path(rig_id, "default"))
    data["mirror_directions"] = _load_direction_map(_section_path(rig_id, "mirror"))
    _CACHE[rig_id] = data
    return data


def save_rig_snapshot(rig_id, data, kind):
    if kind == "opposite":
        payload = _opposite_payload(data)
    elif kind == "default":
        payload = data.get("defaults", {})
    elif kind == "mirror":
        payload = data.get("mirror_directions", {})
    else:
        raise ValueError(f"Unknown snapshot kind: {kind}")

    _write_json_dict(_section_path(rig_id, kind), payload)
    _CACHE[rig_id] = data


def clear_section(rig_id, kind):
    data = copy.deepcopy(load_rig_snapshot(rig_id))
    if kind == "opposite":
        data["pairs"] = []
        data["centers"] = []
    elif kind == "default":
        data["defaults"] = {}
    elif kind == "mirror":
        data["mirror_directions"] = {}
    else:
        raise ValueError(f"Unknown snapshot kind: {kind}")
    save_rig_snapshot(rig_id, data, kind)


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
        return data.get("mirror_directions", {}).get(shortname)
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


def merge_control_entries(rig_id, kind, entries, replace=False):
    """Persist ``entries`` into the rig's independent file for ``kind``.

    Only touches the given controls -- everything else in that section is left
    untouched, so re-snapshotting a couple of controls updates just those.
    """
    if not entries:
        return
    data = copy.deepcopy(load_rig_snapshot(rig_id))
    if kind == "opposite":
        _merge_opposite_entries(data, entries)
    elif kind == "default":
        _merge_replace_entries(data.setdefault("defaults", {}), entries)
    elif kind == "mirror":
        directions = data.setdefault("mirror_directions", {})
        if replace:
            _merge_replace_entries(directions, entries)
        else:
            _merge_attr_entries(directions, entries)
    else:
        raise ValueError(f"Unknown snapshot kind: {kind}")
    save_rig_snapshot(rig_id, data, kind)


def resolve_control_snapshot(node, kind, compute_fn):
    """Read a cached snapshot entry for ``node``, or compute it in-memory only.

    This is the "instant snapshot" used by ordinary operations: a persisted
    rig snapshot folder is consulted if one exists; otherwise
    ``compute_fn(node)`` runs and its result is returned WITHOUT being written
    to disk.
    """
    rig_id = get_rig_id(node)
    if rig_id is not None:
        cached = get_cached_entry(rig_id, control_key(node), kind)
        if cached is not None:
            return cached
    return compute_fn(node)


def get_attr_value(node, values, attr, default=None):
    """Read an attr entry stored under its Maya short name."""
    if not isinstance(values, dict):
        return default
    if attr in values:
        return values[attr]
    try:
        short_attr = cmds.attributeQuery(attr, node=node, shortName=True)
    except (RuntimeError, TypeError, ValueError):
        short_attr = None
    return values.get(short_attr, default) if short_attr else default


# ____________________________ Capture helpers (used by Snapshot actions) ______________


def capture_opposite(node):
    """Resolve node's opposite control, namespace-stripped, or None if it's a center."""
    opposite = find_opposite_name(node)
    return control_key(opposite) if opposite else None


def _differs_from_default(value, default_value):
    if isinstance(value, (int, float)) and isinstance(default_value, (int, float)):
        return abs(value - default_value) > 1e-9
    return value != default_value


def _world_matrix(node):
    values = cmds.xform(node, query=True, matrix=True, worldSpace=True)
    if not values or len(values) != 16:
        raise ValueError(f"Unable to read a world matrix for {node}")
    return tuple(float(value) for value in values)


def _matrix_delta(matrix, baseline):
    return tuple(value - base for value, base in zip(matrix, baseline))


def _reflect_matrix_delta(delta):
    """Reflect a row-major Maya matrix delta across the world YZ plane."""
    signs = (-1.0, 1.0, 1.0, 1.0)
    return tuple(
        delta[row * 4 + column] * signs[row] * signs[column]
        for row in range(4)
        for column in range(4)
    )


def _matrix_delta_score(first, second):
    return sum((a - b) ** 2 for a, b in zip(first, second))


def _direction_from_deltas(source_delta, target_keep_delta, target_invert_delta):
    """Return 1/-1 for a clear keep/invert match, otherwise None."""
    desired = _reflect_matrix_delta(source_delta)
    if _matrix_delta_score(desired, (0.0,) * 16) <= _MIRROR_EFFECT_EPSILON:
        return None
    keep_score = _matrix_delta_score(desired, target_keep_delta)
    invert_score = _matrix_delta_score(desired, target_invert_delta)
    difference = abs(keep_score - invert_score)
    if difference <= max(_MIRROR_EFFECT_EPSILON, min(keep_score, invert_score) * 0.05):
        return None
    return -1 if invert_score < keep_score else 1


def _probe_matrix(node, plug, value):
    cmds.setAttr(plug, value)
    return _world_matrix(node)


def _restore_plug(plug, value):
    try:
        cmds.setAttr(plug, value)
    except (RuntimeError, TypeError, ValueError):
        return False
    return True


@contextmanager
def mirror_probe_session():
    """Keep temporary mirror probes out of Maya's undo queue and dirty state."""
    try:
        undo_enabled = bool(cmds.undoInfo(query=True, state=True))
    except (RuntimeError, TypeError, ValueError):
        undo_enabled = False
    try:
        scene_was_modified = bool(cmds.file(query=True, modified=True))
    except (RuntimeError, TypeError, ValueError):
        scene_was_modified = True

    try:
        if undo_enabled:
            try:
                cmds.undoInfo(stateWithoutFlush=False)
            except (RuntimeError, TypeError, ValueError):
                undo_enabled = False
        yield
    finally:
        if undo_enabled:
            try:
                cmds.undoInfo(stateWithoutFlush=True)
            except (RuntimeError, TypeError, ValueError):
                pass
        if not scene_was_modified:
            try:
                cmds.file(modified=False)
            except (RuntimeError, TypeError, ValueError):
                pass


def _capture_attr_direction(source, target, attr):
    source_plug = f"{source}.{attr}"
    target_plug = f"{target}.{attr}"
    source_value = None
    target_value = None
    try:
        source_value = cmds.getAttr(source_plug)
        target_value = cmds.getAttr(target_plug)
        if (isinstance(source_value, bool) or isinstance(target_value, bool)
                or not isinstance(source_value, (int, float))
                or not isinstance(target_value, (int, float))):
            return None
        if (not cmds.getAttr(source_plug, settable=True)
                or not cmds.getAttr(target_plug, settable=True)):
            return None
        probe_delta = (
            1
            if isinstance(source_value, int) or isinstance(target_value, int)
            else _MIRROR_PROBE_DELTA
        )

        source_base = _world_matrix(source)
        target_base = source_base if source == target else _world_matrix(target)
        try:
            source_plus = _probe_matrix(source, source_plug, source_value + probe_delta)
        finally:
            cmds.setAttr(source_plug, source_value)
        source_delta = _matrix_delta(source_plus, source_base)

        try:
            target_plus = _probe_matrix(target, target_plug, target_value + probe_delta)
            cmds.setAttr(target_plug, target_value)
            target_minus = _probe_matrix(target, target_plug, target_value - probe_delta)
        finally:
            cmds.setAttr(target_plug, target_value)

        return _direction_from_deltas(
            source_delta,
            _matrix_delta(target_plus, target_base),
            _matrix_delta(target_minus, target_base),
        )
    except (RuntimeError, TypeError, ValueError):
        if source_value is not None:
            _restore_plug(source_plug, source_value)
        if target_plug != source_plug and target_value is not None:
            _restore_plug(target_plug, target_value)
        return None


def snapshot_attrs(node):
    """Return the attributes considered by default and mirror snapshots."""
    return cmds.listAttr(node, keyable=True, unlocked=True, visible=True) or []


def capture_mirror_directions(node, attrs=None, processor=None):
    """Probe mirror direction/orientation and return only required overrides."""
    opposite = find_opposite_name(node)
    target = opposite or node
    is_center = opposite is None
    overrides = {}
    for attr in snapshot_attrs(node) if attrs is None else attrs:
        if processor and processor.cancelled:
            break
        try:
            if attr == "tag" or not cmds.attributeQuery(attr, node=target, exists=True):
                continue
            short_attr = cmds.attributeQuery(attr, node=node, shortName=True) or attr
            direction = _capture_attr_direction(node, target, attr)
            if direction is None:
                continue
            default_direction = -1 if is_center and attr in CENTER_INVERT_ATTRS else 1
            if direction != default_direction:
                overrides[short_attr] = direction
        except (RuntimeError, TypeError, ValueError):
            pass
        finally:
            if processor:
                processor.step(amount=MIRROR_PROGRESS_WEIGHT)
    return overrides


def capture_default_values(node, attrs=None, processor=None):
    """Capture only the attrs whose current value deviates from Maya's own default."""
    values = {}
    for attr in snapshot_attrs(node) if attrs is None else attrs:
        if processor and processor.cancelled:
            break
        try:
            if attr == "tag":
                continue
            plug = f"{node}.{attr}"
            current = cmds.getAttr(plug)
            fallback = cmds.attributeQuery(attr, node=node, listDefault=True)
            short_attr = cmds.attributeQuery(attr, node=node, shortName=True) or attr
            default_value = fallback[0] if fallback else None
            if default_value is None or _differs_from_default(current, default_value):
                values[short_attr] = current
        except (RuntimeError, TypeError, ValueError):
            # Some third-party rigs expose malformed or otherwise non-queryable
            # attribute names through listAttr (for example a name containing a
            # character Maya replaces with '?'). One bad plug must not prevent
            # the remaining controls and attributes from being snapshotted.
            pass
        finally:
            if processor:
                processor.step()
    return values
