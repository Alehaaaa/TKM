"""Snapshot Rig storage and analysis for opposite, default-pose, and mirror data.

A rig is identified by the Maya node UUID of its topmost transform (its
"root group"), not by namespace or file path -- the same rig referenced under
a different namespace, or opened in a different Maya session/machine sharing
the user data folder, resolves to the same UUID-named snapshot folder. If a
rig's root transform is deleted and recreated (a full rebuild/re-export), its UUID
changes and any existing snapshot data becomes orphaned under the old id --
this is an inherent limitation of node-identity, not something this module
solves.

Only the explicit "Snapshot ..." registry actions persist analysis to disk
(via ``merge_control_entries``). Ordinary default/opposite/mirror operations
read a cached snapshot when one exists and otherwise analyze on the fly
in-memory only, through ``resolve_control_snapshot`` -- nothing is written
unless the user explicitly snapshots.
"""

import copy
import json
import math
import os
import tempfile
from contextlib import contextmanager

from maya import cmds

import TheKeyMachine.core.application as general
from TheKeyMachine.tools.mirror import math as mirror_math


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
    ("Left", "Right"),
    ("Right", "Left"),
    ("left_", "right_"),
    ("right_", "left_"),
    ("_left", "_right"),
    ("_right", "_left"),
    ("_left_", "_right_"),
    ("_right_", "_left_"),
]
MIRROR_NAME_ALIASES = [
    ("Mover", "Translate"),
    ("Translate", "Mover"),
]

CENTER_INVERT_ATTRS = {"translateX", "rotateY", "rotateZ", "tx", "ry", "rz"}
MIRROR_ATTRS_TO_IGNORE = {
    "tag",
    "rotateOrder", "ro",
    "rotateAxis", "rotateAxisX", "rotateAxisY", "rotateAxisZ", "rax", "ray", "raz",
    "jointOrient", "jointOrientX", "jointOrientY", "jointOrientZ", "jox", "joy", "joz",
    "rotatePivot", "rotatePivotX", "rotatePivotY", "rotatePivotZ", "rpx", "rpy", "rpz",
    "rotatePivotTranslate", "rotatePivotTranslateX", "rotatePivotTranslateY",
    "rotatePivotTranslateZ", "rpt", "rptx", "rpty", "rptz",
    "scalePivot", "scalePivotX", "scalePivotY", "scalePivotZ", "spx", "spy", "spz",
    "scalePivotTranslate", "scalePivotTranslateX", "scalePivotTranslateY",
    "scalePivotTranslateZ", "spt", "sptx", "spty", "sptz",
    "segmentScaleCompensate", "ssc", "inheritsTransform", "it",
}
MIRROR_FIXED_KEEP_ATTRS = {
    "scale", "scaleX", "scaleY", "scaleZ", "sx", "sy", "sz",
}
_MIRROR_PROBE_DELTA = 0.1
_MIRROR_EFFECT_EPSILON = 1e-10
MIRROR_PROGRESS_WEIGHT = 4
_OPPOSITE_UNSET = object()


# ____________________________ Opposite-name pattern matching ________________________


def opposite_control_name(name):
    """Return the configured opposite control name without querying the scene."""
    candidates = opposite_control_candidates(name)
    return candidates[0] if candidates else None


def opposite_control_candidates(name):
    """Return all supported opposite names, including secondary aliases."""
    return mirror_math.opposite_name_candidates(
        name, MIRROR_PATTERNS, MIRROR_NAME_ALIASES,
    )


def find_selected_opposite(node, selected_nodes):
    """Resolve an opposite unambiguously within one already-grouped rig selection."""
    candidate_keys = {
        control_key(candidate) for candidate in opposite_control_candidates(control_key(node))
    }
    matches = [
        candidate for candidate in selected_nodes
        if candidate != node and control_key(candidate) in candidate_keys
    ]
    return matches[0] if len(matches) == 1 else None


def _find_pattern_opposite(name):
    """Return the name-pattern opposite without consulting saved snapshots."""
    direct_candidates = opposite_control_candidates(name)
    direct_matches = [candidate for candidate in direct_candidates if cmds.objExists(candidate)]
    if len(direct_matches) == 1:
        return direct_matches[0]
    if len(direct_matches) > 1:
        source_root = get_rig_root(name)
        same_rig = [
            candidate for candidate in direct_matches
            if get_rig_root(candidate) == source_root
        ]
        return same_rig[0] if len(same_rig) == 1 else None

    # Long DAG paths keep the source control's parent path when the leaf name
    # is swapped. Left/right controls commonly live below different parent
    # groups, so that otherwise valid candidate does not exist. Resolve the
    # namespaced leaf independently, then keep the result within the source rig
    # when Maya reports more than one matching DAG node.
    leaf_name = name.rsplit("|", 1)[-1]
    if leaf_name == name:
        return None
    opposite_leaves = opposite_control_candidates(leaf_name)
    if not opposite_leaves:
        return None
    matches = []
    for opposite_leaf in opposite_leaves:
        for match in cmds.ls(opposite_leaf, long=True) or []:
            if match not in matches:
                matches.append(match)
    if len(matches) == 1:
        return matches[0]
    if not matches:
        return None

    source_root = get_rig_root(name)
    same_rig_matches = [match for match in matches if get_rig_root(match) == source_root]
    return same_rig_matches[0] if len(same_rig_matches) == 1 else None


def _resolve_control_key(node, shortname):
    """Resolve a snapshot short name to a control in ``node``'s rig."""
    leaf_name = node.rsplit("|", 1)[-1]
    namespace, separator, _control_name = leaf_name.rpartition(":")
    candidate = f"{namespace}:{shortname}" if separator else shortname
    matches = cmds.ls(candidate, long=True) or []
    if not matches and cmds.objExists(candidate):
        return candidate
    if len(matches) == 1:
        return matches[0]
    if not matches:
        return None
    source_root = get_rig_root(node)
    same_rig_matches = [match for match in matches if get_rig_root(match) == source_root]
    return same_rig_matches[0] if len(same_rig_matches) == 1 else None


def find_opposite_name(name, use_snapshot=True):
    """Return the saved opposite, falling back to name-pattern analysis."""
    if use_snapshot:
        rig_id = get_rig_id(name)
        if rig_id:
            cached = get_cached_entry(rig_id, control_key(name), "opposite")
            if cached == "":
                return None
            if cached:
                resolved = _resolve_control_key(name, cached)
                if resolved:
                    return resolved
    return _find_pattern_opposite(name)


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


def has_snapshot_section(rig_id, kind):
    """Return whether this rig already has a persisted snapshot section."""
    return bool(rig_id and os.path.isfile(_section_path(rig_id, kind)))


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
    opposite = find_opposite_name(node, use_snapshot=False)
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


def _central_response(node, plug, value, probe_delta):
    """Measure a channel's local world-matrix response without pose bias."""
    try:
        plus = _probe_matrix(node, plug, value + probe_delta)
        minus = _probe_matrix(node, plug, value - probe_delta)
    finally:
        cmds.setAttr(plug, value)
    return mirror_math.matrix_delta(plus, minus)


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

        source_response = _central_response(
            source, source_plug, source_value, probe_delta,
        )
        target_response = (
            source_response
            if source == target
            else _central_response(target, target_plug, target_value, probe_delta)
        )
        return mirror_math.response_direction(
            source_response, target_response, epsilon=_MIRROR_EFFECT_EPSILON,
        )
    except (RuntimeError, TypeError, ValueError):
        if source_value is not None:
            _restore_plug(source_plug, source_value)
        if target_plug != source_plug and target_value is not None:
            _restore_plug(target_plug, target_value)
        return None


def snapshot_attrs(node):
    """Return the attributes considered by default and mirror snapshots."""
    try:
        return cmds.listAttr(node, keyable=True, unlocked=True, visible=True) or []
    except (RuntimeError, TypeError, ValueError):
        return []


def _pose_reference_value(node, attr, saved_defaults):
    stored = get_attr_value(node, saved_defaults, attr)
    if stored is not None:
        return stored
    try:
        fallback = cmds.attributeQuery(attr, node=node, listDefault=True)
    except (RuntimeError, TypeError, ValueError):
        fallback = None
    return fallback[0] if fallback else None


def _pose_values_differ(current, reference):
    if isinstance(current, bool) or isinstance(reference, bool):
        return current != reference
    if isinstance(current, (int, float)) and isinstance(reference, (int, float)):
        tolerance = max(1e-4, abs(float(reference)) * 1e-6)
        return abs(float(current) - float(reference)) > tolerance
    return False


def pose_likely_not_default(groups, attrs_by_control):
    """Detect a clearly posed selection without guessing from rig rest offsets.

    A saved default is strong evidence and needs only one control with several
    changed channels. Without one, require several changed *animated* channels
    across multiple controls; custom rigs with non-zero unkeyed rest values are
    therefore not treated as posed merely because Maya's plug defaults are zero.
    """
    for rig_id, group in (groups or {}).items():
        has_saved_default = has_snapshot_section(rig_id, "default")
        changed_attrs = 0
        changed_controls = 0
        saved_changed_attrs = 0
        saved_changed_controls = 0
        animated_changed_attrs = 0
        animated_changed_controls = 0
        raw_transform_attrs = 0
        raw_transform_controls = 0
        extreme_rotation_controls = 0
        for control in group.get("controls", ()):
            saved_entry = (
                get_cached_entry(rig_id, control_key(control), "default")
                if has_saved_default else None
            )
            saved_defaults = saved_entry or {}
            control_changed = 0
            control_animated = 0
            control_raw_transforms = 0
            control_extreme_rotation = False
            for attr in attrs_by_control.get(control, ()):
                if attr == "tag" or attr in MIRROR_ATTRS_TO_IGNORE:
                    continue
                plug = f"{control}.{attr}"
                try:
                    current = cmds.getAttr(plug)
                    reference = _pose_reference_value(control, attr, saved_defaults)
                    maya_default = _pose_reference_value(control, attr, {})
                    short_attr = cmds.attributeQuery(
                        attr, node=control, shortName=True,
                    ) or attr
                except (RuntimeError, TypeError, ValueError):
                    continue
                is_transform = short_attr in {"tx", "ty", "tz", "rx", "ry", "rz"}
                if is_transform and _pose_values_differ(current, maya_default):
                    control_raw_transforms += 1
                    if (
                        short_attr in {"rx", "ry", "rz"}
                        and isinstance(current, (int, float))
                        and isinstance(maya_default, (int, float))
                        and abs(float(current) - float(maya_default)) > 180.0
                    ):
                        control_extreme_rotation = True
                if not _pose_values_differ(current, reference):
                    continue
                control_changed += 1
                try:
                    keyed = bool(cmds.keyframe(plug, query=True, keyframeCount=True))
                except (RuntimeError, TypeError, ValueError):
                    keyed = False
                if keyed:
                    control_animated += 1
            if control_changed:
                changed_controls += 1
                changed_attrs += control_changed
                if saved_entry is not None:
                    saved_changed_controls += 1
                    saved_changed_attrs += control_changed
            if control_animated:
                animated_changed_controls += 1
                animated_changed_attrs += control_animated
            if control_raw_transforms:
                raw_transform_controls += 1
                raw_transform_attrs += control_raw_transforms
            if control_extreme_rotation:
                extreme_rotation_controls += 1

        if saved_changed_controls >= 1 and saved_changed_attrs >= 2:
            return True
        if animated_changed_controls >= 2 and animated_changed_attrs >= 3:
            return True
        # On a first snapshot there is no trustworthy rig-specific reference.
        # Several meaningful TR offsets are enough to ask (not assume): the
        # user can confirm a custom non-zero rest pose in the anchored prompt.
        if (
            not has_saved_default
            and raw_transform_controls >= 2
            and raw_transform_attrs >= 3
        ):
            return True
        # Also recover from a previously captured bad default that matches the
        # current pose. Very large Euler branches or a quarter of the selected
        # rig carrying multiple raw TR offsets are implausible enough to ask.
        control_count = len(group.get("controls", ()))
        widespread_minimum = max(5, int(math.ceil(control_count * 0.25)))
        if extreme_rotation_controls >= 2:
            return True
        if (
            raw_transform_controls >= widespread_minimum
            and raw_transform_attrs >= raw_transform_controls * 2
        ):
            return True
    return False


def capture_mirror_directions(
    node, attrs=None, processor=None, opposite=_OPPOSITE_UNSET,
):
    """Probe mirror direction/orientation and return only required overrides."""
    if opposite is _OPPOSITE_UNSET:
        opposite = find_opposite_name(node, use_snapshot=False)
    target = opposite or node
    is_center = opposite is None
    overrides = {}
    for attr in snapshot_attrs(node) if attrs is None else attrs:
        if processor and processor.cancelled:
            break
        try:
            if (attr in MIRROR_ATTRS_TO_IGNORE
                    or attr in MIRROR_FIXED_KEEP_ATTRS
                    or not cmds.attributeQuery(attr, node=target, exists=True)):
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
