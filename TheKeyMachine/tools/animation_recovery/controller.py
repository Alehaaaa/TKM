"""Persistent, scene-scoped animation recovery snapshots."""

from __future__ import absolute_import

from contextlib import contextmanager
from datetime import datetime
import io
import json
import os
import struct
import time
import uuid
import zlib

from maya import cmds

try:
    from maya.api import OpenMaya as om
except ImportError:
    om = None

from TheKeyMachine.core import six
from TheKeyMachine.core.Qt import QtCore
from TheKeyMachine.mods import generalMod as general
from TheKeyMachine.mods import settingsMod as settings
from TheKeyMachine.tools import common as toolCommon
from TheKeyMachine.widgets import util as wutil


SETTINGS_NAMESPACE = "animation_recovery"
ENABLED_SETTING = "enabled"
PROMPTED_SETTING = "startup_prompted"
RUNTIME_DAG_KEY = "animation_recovery:dag"
RUNTIME_ANIMATION_KEY = "animation_recovery:animation"
RUNTIME_SCENE_KEY = "animation_recovery:scene"
RUNTIME_TRANSFORM_KEY = "animation_recovery:transforms"
SCENE_NODE = "TheKeyMachine"
SCENE_ID_ATTRIBUTE = "tkmAnimationRecoverySceneId"
SCHEMA_VERSION = 5
BASELINE_INTERVAL = 50
MAX_BASELINE_GENERATIONS = 20
SNAPSHOT_DELAY_MS = 350
REWATCH_DELAY_MS = 100
RECOVERY_EXTENSION = ".tkmrec"
FULL_SNAPSHOT_FLAG = 0x80
REASON_CODES = {
    "animation": 0,
    "dag": 1,
    "scene_save": 2,
    "recovery": 3,
    "transform": 4,
}
REASONS_BY_CODE = {code: reason for reason, code in REASON_CODES.items()}

_SERVICE = None


def is_enabled():
    return bool(settings.get_setting(ENABLED_SETTING, False, namespace=SETTINGS_NAMESPACE))


def was_startup_prompted():
    return bool(settings.get_setting(PROMPTED_SETTING, False, namespace=SETTINGS_NAMESPACE))


def mark_startup_prompted():
    settings.set_setting(PROMPTED_SETTING, True, namespace=SETTINGS_NAMESPACE)


def recovery_root():
    return os.path.join(
        general.USER_FOLDER_PATH,
        "TheKeyMachine_user_data",
        "animation_recovery",
    )


def _safe_filename_timestamp(now=None):
    value = now or datetime.now()
    timestamp = time.mktime(value.timetuple()) + (value.microsecond / 1000000.0)
    return "{:.8f}".format(timestamp)


def _parse_filename_timestamp(path):
    value = os.path.splitext(os.path.basename(path))[0]
    try:
        return datetime.fromtimestamp(float(value))
    except (TypeError, ValueError, OverflowError):
        pass
    for date_format in ("%Y-%m-%d_%H-%M-%S-%f", "%Y%m%dT%H%M%S_%f"):
        try:
            return datetime.strptime(value, date_format)
        except (TypeError, ValueError):
            continue
    return datetime.fromtimestamp(os.path.getmtime(path))


def _filename_timestamp_value(path):
    try:
        return float(os.path.splitext(os.path.basename(path))[0])
    except (TypeError, ValueError):
        created = _parse_filename_timestamp(path)
        return time.mktime(created.timetuple()) + (created.microsecond / 1000000.0)


def _pack_endpoint(endpoint):
    return [endpoint.get("plug"), endpoint.get("node_uuid")]


def _unpack_endpoint(endpoint):
    plug = endpoint[0] if endpoint else None
    node, attribute = _split_plug(plug)
    return {
        "plug": plug,
        "node": node,
        "node_uuid": endpoint[1] if len(endpoint) > 1 else None,
        "attribute": attribute,
    }


def _pack_curve(curve):
    tangents = curve.get("tangents") or {}
    return [
        curve.get("name"),
        curve.get("uuid"),
        curve.get("node_type"),
        1 if curve.get("unitless_input") else 0,
        curve.get("positions") or [],
        curve.get("values") or [],
        [tangents.get(key) or [] for key in ("itt", "ott", "ia", "oa", "iw", "ow")],
        1 if curve.get("weighted_tangents") else 0,
        curve.get("pre_infinity", 0),
        curve.get("post_infinity", 0),
        [_pack_endpoint(item) for item in curve.get("input_connections") or []],
        [_pack_endpoint(item) for item in curve.get("output_connections") or []],
    ]


def _unpack_curve(curve):
    tangent_values = curve[6] if len(curve) > 6 else []
    tangent_keys = ("itt", "ott", "ia", "oa", "iw", "ow")
    return {
        "name": curve[0],
        "uuid": curve[1],
        "node_type": curve[2],
        "unitless_input": bool(curve[3]),
        "positions": curve[4],
        "values": curve[5],
        "tangents": {
            key: tangent_values[index] if index < len(tangent_values) else []
            for index, key in enumerate(tangent_keys)
        },
        "weighted_tangents": bool(curve[7]),
        "pre_infinity": curve[8],
        "post_infinity": curve[9],
        "input_connections": [_unpack_endpoint(item) for item in curve[10]],
        "output_connections": [_unpack_endpoint(item) for item in curve[11]],
    }


def _pack_payload(payload):
    details = payload.get("meta") or {}
    return [
        [
            details.get("source_file"),
            details.get("location"),
            details.get("current_frame"),
            details.get("playback_range"),
            details.get("animation_range"),
            details.get("selected_objects"),
            details.get("source_mtime"),
            details.get("parent_checkpoint"),
        ],
        [_pack_curve(curve) for curve in payload.get("curves") or []],
        [
            [
                item.get("name"),
                item.get("uuid"),
                [[name, value] for name, value in sorted((item.get("attributes") or {}).items())],
            ]
            for item in payload.get("objects") or []
        ],
        [
            [
                item.get("name"),
                item.get("uuid"),
                [_pack_endpoint(endpoint) for endpoint in item.get("output_connections") or []],
            ]
            for item in payload.get("removed_curves") or []
        ],
    ]


def _unpack_payload(payload, version=1, reason="animation", full_snapshot=False):
    details = payload[0] if payload else []
    curves = payload[1] if len(payload) > 1 else []
    objects = payload[2] if len(payload) > 2 else []
    removed_curves = payload[3] if len(payload) > 3 else []
    return {
        "meta": {
            "version": version,
            "reason": reason,
            "full_snapshot": bool(full_snapshot),
            "source_file": details[0] if len(details) > 0 else None,
            "location": details[1] if len(details) > 1 else None,
            "current_frame": details[2] if len(details) > 2 else None,
            "playback_range": details[3] if len(details) > 3 else None,
            "animation_range": details[4] if len(details) > 4 else None,
            "selected_objects": details[5] if len(details) > 5 else None,
            "source_mtime": details[6] if len(details) > 6 else None,
            "parent_checkpoint": details[7] if len(details) > 7 else None,
        },
        "curves": [_unpack_curve(curve) for curve in curves],
        "objects": [
            {
                "name": item[0],
                "uuid": item[1],
                "attributes": dict(item[2]),
            }
            for item in objects
        ],
        "removed_curves": [
            {
                "name": item[0] if item else None,
                "uuid": item[1] if len(item) > 1 else None,
                "output_connections": [
                    _unpack_endpoint(endpoint)
                    for endpoint in (item[2] if len(item) > 2 else [])
                ],
            }
            for item in removed_curves
        ],
    }


def _write_recovery_atomic(path, payload):
    folder = os.path.dirname(path)
    if not os.path.isdir(folder):
        try:
            os.makedirs(folder)
        except OSError:
            if not os.path.isdir(folder):
                raise
    temporary = path + ".tmp"
    packed = _pack_payload(payload)
    serialized = json.dumps(packed, ensure_ascii=False, separators=(",", ":")).encode("utf-8")
    meta = payload.get("meta") or {}
    reason = meta.get("reason") or "animation"
    reason_byte = REASON_CODES.get(reason, 0)
    if meta.get("full_snapshot"):
        reason_byte |= FULL_SNAPSHOT_FLAG
    header = struct.pack("BB", SCHEMA_VERSION, reason_byte)
    compiled = header + zlib.compress(serialized, 9)
    try:
        with io.open(temporary, "wb") as stream:
            stream.write(compiled)
            stream.flush()
            os.fsync(stream.fileno())
        replace = getattr(os, "replace", os.rename)
        replace(temporary, path)
    except Exception:
        try:
            if os.path.isfile(temporary):
                os.remove(temporary)
        except OSError:
            pass
        raise


def _load_recovery(path):
    if path.lower().endswith(".json"):
        with io.open(path, "r", encoding="utf-8") as stream:
            return json.load(stream)
    with io.open(path, "rb") as stream:
        compiled = stream.read()
    if compiled[:1] == b"x":
        # Compatibility with the short-lived initial compact format.
        legacy = json.loads(zlib.decompress(compiled).decode("utf-8"))
        if legacy and isinstance(legacy[0], int):
            return _unpack_payload(legacy[1:], version=legacy[0], full_snapshot=True)
        return _unpack_payload(legacy, full_snapshot=True)
    if len(compiled) < 3:
        raise ValueError("Invalid Animation Recovery file")
    version, reason_code = struct.unpack("BB", compiled[:2])
    if version < 1 or version > SCHEMA_VERSION:
        raise ValueError("Unsupported Animation Recovery version: {}".format(version))
    serialized = zlib.decompress(compiled[2:]).decode("utf-8")
    return _unpack_payload(
        json.loads(serialized),
        version=version,
        reason=REASONS_BY_CODE.get(reason_code & ~FULL_SNAPSHOT_FLAG, "animation"),
        full_snapshot=(version < 4 or bool(reason_code & FULL_SNAPSHOT_FLAG)),
    )


def _recovery_reason(path):
    if path.lower().endswith(".json"):
        try:
            return (_load_recovery(path).get("meta") or {}).get("reason") or "animation"
        except Exception:
            return "animation"
    try:
        with io.open(path, "rb") as stream:
            header = stream.read(2)
        if header[:1] == b"x" or len(header) < 2:
            return "animation"
        _version, reason_code = struct.unpack("BB", header)
        return REASONS_BY_CODE.get(reason_code & ~FULL_SNAPSHOT_FLAG, "animation")
    except Exception:
        return "animation"


def _recovery_header(path):
    """Return the lightweight format metadata needed to build a replay chain."""
    if path.lower().endswith(".json"):
        payload = _load_recovery(path)
        meta = payload.get("meta") or {}
        try:
            version = int(meta.get("version") or 1)
        except (TypeError, ValueError):
            version = 1
        return version, bool(version < 4 or meta.get("full_snapshot"))
    with io.open(path, "rb") as stream:
        header = stream.read(2)
    if header[:1] == b"x":
        return 1, True
    if len(header) < 2:
        raise ValueError("Invalid Animation Recovery file")
    version, reason_code = struct.unpack("BB", header)
    if version < 1 or version > SCHEMA_VERSION:
        raise ValueError("Unsupported Animation Recovery version: {}".format(version))
    return version, bool(version < 4 or reason_code & FULL_SNAPSHOT_FLAG)


def _maya_file_io_active():
    """Avoid DG inspection while Maya is reading or writing scene data."""
    file_io = getattr(om, "MFileIO", None) if om is not None else None
    if file_io is None:
        return False
    for method_name in (
        "isReadingFile",
        "isOpeningFile",
        "isImportingFile",
        "isReferencingFile",
        "isWritingFile",
    ):
        method = getattr(file_io, method_name, None)
        try:
            if callable(method) and method():
                return True
        except Exception:
            continue
    return False


def _node_uuid(node):
    try:
        values = cmds.ls(node, uuid=True) or []
        return values[0] if values else None
    except Exception:
        return None


def _split_plug(plug):
    if not plug or "." not in plug:
        return plug, ""
    return plug.split(".", 1)


def _endpoint_data(plug):
    node, attribute = _split_plug(plug)
    return {
        "plug": plug,
        "node": node,
        "node_uuid": _node_uuid(node),
        "attribute": attribute,
    }


RECOVERABLE_ATTRIBUTE_TYPES = (
    "bool", "byte", "char", "short", "long", "enum",
    "float", "double", "doubleAngle", "doubleLinear", "time",
)


def _recoverable_attributes(node):
    """Return writable scalar channels, including custom enum controls."""
    try:
        candidates = cmds.listAttr(node, keyable=True, scalar=True) or []
        candidates += cmds.listAttr(node, channelBox=True, scalar=True) or []
    except Exception:
        candidates = []
    result = []
    for attribute in candidates:
        if attribute in result:
            continue
        plug = "{}.{}".format(node, attribute)
        try:
            if (
                cmds.objExists(plug)
                and not cmds.getAttr(plug, lock=True)
                and cmds.getAttr(plug, type=True) in RECOVERABLE_ATTRIBUTE_TYPES
            ):
                result.append(attribute)
        except Exception:
            continue
    return result


def _attribute_is_animated(node, attribute):
    try:
        return bool(cmds.keyframe(
            "{}.{}".format(node, attribute),
            query=True,
            keyframeCount=True,
        ))
    except Exception:
        return False


def _capture_object_state(node, attributes=None):
    if not node or not cmds.objExists(node):
        return None
    captured_attributes = {}
    attribute_names = _recoverable_attributes(node) if attributes is None else attributes
    for attribute in attribute_names:
        if _attribute_is_animated(node, attribute):
            continue
        plug = "{}.{}".format(node, attribute)
        if not cmds.objExists(plug):
            continue
        try:
            captured_attributes[attribute] = cmds.getAttr(plug)
        except Exception:
            continue
    if not captured_attributes:
        return None
    return {
        "name": node,
        "uuid": _node_uuid(node),
        "attributes": captured_attributes,
    }


def _connections(plug, source, destination):
    try:
        plugs = cmds.listConnections(
            plug,
            source=source,
            destination=destination,
            plugs=True,
            skipConversionNodes=False,
        ) or []
    except Exception:
        plugs = []
    return sorted(
        (_endpoint_data(item) for item in plugs),
        key=lambda item: item.get("plug") or "",
    )


def _query_values(command, curve, flag):
    try:
        return list(command(curve, query=True, **{flag: True}) or [])
    except Exception:
        return []


def _capture_curve(curve):
    node_type = cmds.nodeType(curve)
    unitless_input = node_type.startswith("animCurveU")
    positions = _query_values(cmds.keyframe, curve, "floatChange" if unitless_input else "timeChange")
    values = _query_values(cmds.keyframe, curve, "valueChange")
    tangent_data = {}
    for short_name, query_name in (
        ("itt", "inTangentType"),
        ("ott", "outTangentType"),
        ("ia", "inAngle"),
        ("oa", "outAngle"),
        ("iw", "inWeight"),
        ("ow", "outWeight"),
    ):
        tangent_data[short_name] = _query_values(cmds.keyTangent, curve, query_name)
    weighted_values = _query_values(cmds.keyTangent, curve, "weightedTangents")
    weighted = bool(weighted_values[0]) if weighted_values else False

    def _attribute(name, default=0):
        try:
            return cmds.getAttr("{}.{}".format(curve, name))
        except Exception:
            return default

    return {
        "name": curve,
        "uuid": _node_uuid(curve),
        "node_type": node_type,
        "unitless_input": unitless_input,
        "positions": positions,
        "values": values,
        "tangents": tangent_data,
        "weighted_tangents": weighted,
        "pre_infinity": _attribute("preInfinity"),
        "post_infinity": _attribute("postInfinity"),
        "input_connections": _connections("{}.input".format(curve), True, False),
        "output_connections": _connections("{}.output".format(curve), False, True),
    }


def _scene_snapshot_meta(scene_id, reason, created, curves):
    try:
        source_path = cmds.file(query=True, sceneName=True) or ""
    except Exception:
        source_path = ""

    def _playback_value(flag, default=None):
        try:
            return cmds.playbackOptions(query=True, **{flag: True})
        except Exception:
            return default

    try:
        current_frame = cmds.currentTime(query=True)
    except Exception:
        current_frame = None
    try:
        selected_count = len(cmds.ls(selection=True, long=True) or [])
    except Exception:
        selected_count = None
    try:
        source_mtime = os.path.getmtime(source_path) if source_path else None
    except OSError:
        source_mtime = None

    return {
        "type": "animation_recovery",
        "version": SCHEMA_VERSION,
        "scene_id": scene_id,
        "created_at": created.isoformat(),
        "reason": reason,
        "source_file": os.path.basename(source_path) if source_path else None,
        "location": os.path.dirname(source_path) if source_path else None,
        "current_frame": current_frame,
        "playback_range": [
            _playback_value("minTime"),
            _playback_value("maxTime"),
        ],
        "animation_range": [
            _playback_value("animationStartTime"),
            _playback_value("animationEndTime"),
        ],
        "selected_objects": selected_count,
        "source_mtime": source_mtime,
        "curve_count": len(curves),
        "key_count": sum(len(curve.get("positions") or []) for curve in curves),
    }


def capture_scene_animation(scene_id, reason="animation"):
    curves = sorted(set(cmds.ls(type="animCurve") or []))
    captured = []
    for curve in curves:
        try:
            curve_data = _capture_curve(curve)
            if curve_data.get("positions"):
                captured.append(curve_data)
        except Exception:
            continue
    now = datetime.now()
    return {
        "meta": _scene_snapshot_meta(scene_id, reason, now, captured),
        "curves": captured,
    }, now


def _edited_curve_names(callback_args):
    if not callback_args or om is None:
        return []
    objects = callback_args[0]
    names = []
    try:
        count = len(objects)
    except Exception:
        try:
            count = objects.length()
        except Exception:
            return []
    for index in range(count):
        try:
            name = om.MFnDependencyNode(objects[index]).name()
        except Exception:
            continue
        if name and name not in names:
            names.append(name)
    return names


def _scene_node():
    return SCENE_NODE if cmds.objExists(SCENE_NODE) else None


def ensure_scene_id():
    """Create the TKM parent only while recovery is active and persist its ID."""
    previous_selection = cmds.ls(selection=True, long=True) or []
    try:
        if not _scene_node():
            general.create_TheKeyMachine_node()
        node = _scene_node()
        if not node:
            return None
        plug = "{}.{}".format(node, SCENE_ID_ATTRIBUTE)
        if not cmds.objExists(plug):
            cmds.addAttr(
                node,
                longName=SCENE_ID_ATTRIBUTE,
                niceName="Animation Recovery Scene ID",
                dataType="string",
            )
        else:
            try:
                cmds.addAttr(
                    plug,
                    edit=True,
                    niceName="Animation Recovery Scene ID",
                    hidden=False,
                )
            except Exception:
                pass
        try:
            scene_id = cmds.getAttr(plug) or ""
        except Exception:
            scene_id = ""
        if not scene_id:
            try:
                cmds.setAttr(plug, lock=False)
            except Exception:
                pass
            scene_id = six.text_type(uuid.uuid4())
            cmds.setAttr(plug, scene_id, type="string")
        try:
            cmds.setAttr(plug, lock=True, keyable=False, channelBox=False)
        except Exception:
            pass
        return scene_id
    finally:
        try:
            if previous_selection:
                cmds.select(previous_selection, replace=True)
            else:
                cmds.select(clear=True)
        except Exception:
            pass


def current_scene_id(create=False):
    node = _scene_node()
    plug = "{}.{}".format(node, SCENE_ID_ATTRIBUTE) if node else None
    if plug and cmds.objExists(plug):
        try:
            value = cmds.getAttr(plug)
            if value:
                return value
        except Exception:
            pass
    return ensure_scene_id() if create else None


def scene_recovery_folder(scene_id=None, create=False):
    scene_id = scene_id or current_scene_id(create=create)
    if not scene_id:
        return None
    folder = os.path.join(recovery_root(), scene_id)
    if create and not os.path.isdir(folder):
        os.makedirs(folder)
    return folder


def _recovery_paths(scene_id=None):
    folder = scene_recovery_folder(scene_id=scene_id, create=False)
    if not folder or not os.path.isdir(folder):
        return []
    paths = [
        os.path.join(folder, filename)
        for filename in os.listdir(folder)
        if filename.lower().endswith((RECOVERY_EXTENSION, ".json"))
    ]
    paths.sort(key=_parse_filename_timestamp)
    return paths


def _recovery_scene_id(path):
    """Return the owning scene ID for a checkpoint directly under the recovery root."""
    root = os.path.realpath(recovery_root())
    folder = os.path.realpath(os.path.dirname(path))
    if os.path.dirname(folder) != root:
        return None
    return os.path.basename(folder) or None


def list_recoveries(scene_id=None):
    paths = _recovery_paths(scene_id=scene_id)
    entries = []
    for index, path in enumerate(paths):
        entries.append({
            "change": index + 1,
            "path": path,
            "created": _parse_filename_timestamp(path),
            "reason": _recovery_reason(path),
        })
    entries.reverse()
    return entries


def newer_recovery_for_current_scene(scene_id=None):
    """Return the newest checkpoint when it is newer than the opened scene."""
    try:
        scene_path = cmds.file(query=True, sceneName=True) or ""
    except Exception:
        scene_path = ""
    if not scene_path or not os.path.isfile(scene_path):
        return None
    entries = list_recoveries(scene_id=scene_id)
    if not entries:
        return None
    latest = entries[0]
    try:
        scene_mtime = os.path.getmtime(scene_path)
        checkpoint_time = time.mktime(latest["created"].timetuple()) + (
            latest["created"].microsecond / 1000000.0
        )
    except (KeyError, OSError, TypeError, ValueError, OverflowError):
        return None
    if checkpoint_time <= scene_mtime:
        return None

    try:
        details = recovery_details(latest["path"])
    except Exception:
        details = {}
    if latest.get("reason") == "scene_save":
        source_file = details.get("source_file")
        location = details.get("location")
        saved_path = os.path.join(location, source_file) if location and source_file else ""
        same_path = bool(saved_path) and os.path.normcase(os.path.realpath(saved_path)) == os.path.normcase(
            os.path.realpath(scene_path)
        )
        saved_mtime = details.get("source_mtime")
        if same_path and saved_mtime is not None and scene_mtime >= float(saved_mtime):
            return None
        # Legacy scene-save points predate exact mtime storage. Their timestamp
        # is naturally a fraction later than the file they describe.
        if same_path and saved_mtime is None and checkpoint_time - scene_mtime < 2.0:
            return None
    return latest["path"]


def _entity_matches(left, right):
    left_uuid = left.get("uuid")
    right_uuid = right.get("uuid")
    if left_uuid and right_uuid:
        return left_uuid == right_uuid
    left_name = left.get("name")
    return bool(left_name and left_name == right.get("name"))


def _curve_targets(curve):
    targets = set()
    for endpoint in curve.get("output_connections") or []:
        node_id = endpoint.get("node_uuid") or endpoint.get("node")
        attribute = endpoint.get("attribute")
        if node_id and attribute:
            targets.add((node_id, attribute))
        elif endpoint.get("plug"):
            targets.add((None, endpoint.get("plug")))
    return targets


def _curve_matches(left, right):
    if _entity_matches(left, right):
        return True
    left_targets = _curve_targets(left)
    right_targets = _curve_targets(right)
    return bool(left_targets and right_targets and left_targets.intersection(right_targets))


def _curve_marker(curve, fallback_name=None):
    return {
        "name": curve.get("name") or fallback_name,
        "uuid": curve.get("uuid"),
        "output_connections": curve.get("output_connections") or [],
    }


def _removed_curve_attributes(removed_curves):
    """Map removed curve outputs to the static channels they leave behind."""
    if not removed_curves:
        return {}
    uuid_lookup = _uuid_lookup()
    result = {}
    for marker in removed_curves:
        for endpoint in marker.get("output_connections") or []:
            plug = _resolve_endpoint(endpoint, uuid_lookup)
            node, attribute = _split_plug(plug)
            if node and attribute:
                result.setdefault(node, set()).add(attribute)
    return result


def _merge_curve(items, item):
    items[:] = [existing for existing in items if not _curve_matches(existing, item)]
    items.append(item)


def _remove_curve(items, marker):
    items[:] = [existing for existing in items if not _curve_matches(existing, marker)]


def _merge_object(items, item):
    for existing in items:
        if not _entity_matches(existing, item):
            continue
        existing["name"] = item.get("name") or existing.get("name")
        existing["uuid"] = item.get("uuid") or existing.get("uuid")
        existing.setdefault("attributes", {}).update(item.get("attributes") or {})
        return
    items.append({
        "name": item.get("name"),
        "uuid": item.get("uuid"),
        "attributes": dict(item.get("attributes") or {}),
    })


def _recovery_chain_paths(path):
    """Return the shortest complete checkpoint chain ending at *path*."""
    target = os.path.realpath(path)
    folder = os.path.dirname(target)
    paths = _recovery_paths(scene_id=os.path.basename(folder))
    target_index = None
    for index, checkpoint_path in enumerate(paths):
        if os.path.realpath(checkpoint_path) == target:
            target_index = index
            break
    if target_index is None:
        raise ValueError("Recovery checkpoint is not part of the current scene")

    start_index = 0
    for index in range(target_index, -1, -1):
        version, full_snapshot = _recovery_header(paths[index])
        # Only schema 5+ baselines contain complete curve and object state.
        if version >= 5 and full_snapshot:
            start_index = index
            break
    return paths[start_index:target_index + 1]


def _load_merged_recovery(path, operation=None, chain_paths=None):
    """Rebuild one point by replaying its verified checkpoint chain."""
    target = os.path.realpath(path)
    paths = chain_paths or _recovery_chain_paths(path)
    curves = []
    objects = []
    target_payload = None
    previous_name = None
    for checkpoint_path in paths:
        if operation and operation.cancelled:
            return None
        payload = _load_recovery(checkpoint_path)
        meta = payload.get("meta") or {}
        try:
            version = int(meta.get("version") or 1)
        except (TypeError, ValueError):
            version = 1
        full_snapshot = bool(version < 4 or meta.get("full_snapshot"))
        if version >= 5 and not full_snapshot:
            parent = meta.get("parent_checkpoint")
            if not parent or parent != previous_name:
                raise ValueError(
                    "Animation Recovery chain is incomplete before {}".format(
                        os.path.basename(checkpoint_path)
                    )
                )
        if full_snapshot:
            curves = []
            if version >= 5:
                objects = []
        for marker in payload.get("removed_curves") or []:
            _remove_curve(curves, marker)
        for curve in payload.get("curves") or []:
            _merge_curve(curves, curve)
        for object_data in payload.get("objects") or []:
            _merge_object(objects, object_data)
        previous_name = os.path.basename(checkpoint_path)
        if operation and operation.step(status="Reading recovery history"):
            return None
        if os.path.realpath(checkpoint_path) == target:
            target_payload = payload
            break
    if target_payload is None:
        raise ValueError("Recovery checkpoint is not part of the current scene")
    return {
        "meta": target_payload.get("meta") or {},
        "curves": sorted(curves, key=lambda item: item.get("name") or ""),
        "objects": sorted(objects, key=lambda item: item.get("name") or ""),
    }


def _newest_valid_recovery(paths):
    """Return the newest checkpoint whose complete replay chain is readable."""
    for checkpoint_path in reversed(paths or []):
        try:
            _load_merged_recovery(checkpoint_path)
        except Exception:
            continue
        return checkpoint_path
    return None


def _prune_recovery_history(scene_id):
    """Keep recent complete baseline generations without orphaning deltas."""
    paths = _recovery_paths(scene_id=scene_id)
    baseline_indices = []
    for index, checkpoint_path in enumerate(paths):
        try:
            version, full_snapshot = _recovery_header(checkpoint_path)
        except Exception:
            continue
        if version >= 5 and full_snapshot:
            baseline_indices.append(index)
    if len(baseline_indices) <= MAX_BASELINE_GENERATIONS:
        return 0

    cutoff = baseline_indices[-MAX_BASELINE_GENERATIONS]
    removed = 0
    for checkpoint_path in paths[:cutoff]:
        try:
            os.remove(checkpoint_path)
            removed += 1
        except OSError:
            continue
    return removed


def delete_recovery(path):
    if not path or not os.path.isfile(path):
        return False
    expected_root = os.path.realpath(recovery_root()) + os.sep
    real_path = os.path.realpath(path)
    if not real_path.startswith(expected_root):
        return False
    os.remove(real_path)
    return True


def recovery_details(path):
    payload = _load_recovery(path)
    meta = dict(payload.get("meta") or {})
    meta.setdefault("created", _parse_filename_timestamp(path))
    created_at = meta.get("created_at")
    if created_at:
        try:
            meta["created"] = datetime.strptime(created_at.split(".", 1)[0], "%Y-%m-%dT%H:%M:%S")
        except (TypeError, ValueError):
            pass
    return meta


def _uuid_lookup():
    try:
        nodes = cmds.ls(dependencyNodes=True, long=True) or []
        uuids = cmds.ls(nodes, uuid=True) or []
        if len(nodes) == len(uuids):
            return dict(zip(uuids, nodes))
    except Exception:
        pass
    return {}


def _resolve_endpoint(endpoint, uuid_lookup):
    attribute = endpoint.get("attribute")
    node_uuid = endpoint.get("node_uuid")
    node = uuid_lookup.get(node_uuid)
    resolved = "{}.{}".format(node, attribute) if node and attribute else None
    if resolved and cmds.objExists(resolved):
        return resolved
    if node_uuid:
        return None
    plug = endpoint.get("plug")
    if plug and cmds.objExists(plug):
        return plug
    node = endpoint.get("node")
    resolved = "{}.{}".format(node, attribute) if node and attribute else None
    return resolved if resolved and cmds.objExists(resolved) else None


def _connect_curve(curve, curve_data, uuid_lookup):
    curve_input = "{}.input".format(curve)
    curve_output = "{}.output".format(curve)
    for endpoint in curve_data.get("input_connections") or []:
        source = _resolve_endpoint(endpoint, uuid_lookup)
        if not source:
            continue
        try:
            if not cmds.isConnected(source, curve_input):
                cmds.connectAttr(source, curve_input, force=True)
        except Exception:
            pass


def _has_resolvable_curve_output(curve_data, uuid_lookup):
    outputs = curve_data.get("output_connections") or []
    return not outputs or any(_resolve_endpoint(endpoint, uuid_lookup) for endpoint in outputs)
    for endpoint in curve_data.get("output_connections") or []:
        destination = _resolve_endpoint(endpoint, uuid_lookup)
        if not destination:
            continue
        try:
            if not cmds.isConnected(curve_output, destination):
                cmds.connectAttr(curve_output, destination, force=True)
        except Exception:
            pass


def _set_curve_keys(curve, curve_data, operation=None):
    positions = curve_data.get("positions") or []
    values = curve_data.get("values") or []
    tangents = curve_data.get("tangents") or {}
    unitless_input = bool(curve_data.get("unitless_input"))
    current_positions = _query_values(
        cmds.keyframe,
        curve,
        "floatChange" if unitless_input else "timeChange",
    )
    try:
        cmds.setAttr("{}.preInfinity".format(curve), curve_data.get("pre_infinity", 0))
        cmds.setAttr("{}.postInfinity".format(curve), curve_data.get("post_infinity", 0))
    except Exception:
        pass
    for index, (position, value) in enumerate(zip(positions, values)):
        key_argument = {"float": position} if unitless_input else {"time": position}
        try:
            cmds.setKeyframe(curve, value=value, **key_argument)
        except Exception:
            if operation:
                operation.step()
            continue

        if operation and operation.step():
            return False

    saved_positions = set(float(position) for position in positions)
    for position in current_positions:
        if float(position) in saved_positions:
            continue
        cut_argument = {"float": (position, position)} if unitless_input else {"time": (position, position)}
        try:
            cmds.cutKey(curve, clear=True, **cut_argument)
        except Exception:
            pass

    try:
        cmds.keyTangent(
            curve,
            edit=True,
            weightedTangents=bool(curve_data.get("weighted_tangents")),
        )
    except Exception:
        pass

    for index in range(min(len(positions), len(values))):
        type_arguments = {}
        detail_arguments = {}
        for short_name, edit_name in (
            ("itt", "inTangentType"),
            ("ott", "outTangentType"),
            ("ia", "inAngle"),
            ("oa", "outAngle"),
            ("iw", "inWeight"),
            ("ow", "outWeight"),
        ):
            values_for_field = tangents.get(short_name) or []
            if index >= len(values_for_field) or values_for_field[index] is None:
                continue
            target = type_arguments if short_name in ("itt", "ott") else detail_arguments
            target[edit_name] = values_for_field[index]
        try:
            if type_arguments:
                cmds.keyTangent(curve, edit=True, index=(index, index), **type_arguments)
            if detail_arguments:
                cmds.keyTangent(curve, edit=True, index=(index, index), **detail_arguments)
                if type_arguments:
                    cmds.keyTangent(curve, edit=True, index=(index, index), **type_arguments)
        except Exception:
            pass
    return True


def _curve_maps(curves=None):
    curves = list(curves) if curves is not None else (cmds.ls(type="animCurve") or [])
    by_name = {curve: curve for curve in curves}
    by_uuid = {}
    for curve in curves:
        curve_uuid = _node_uuid(curve)
        if curve_uuid:
            by_uuid[curve_uuid] = curve
    return curves, by_name, by_uuid


def _selected_transform_nodes():
    result = []
    for selected in cmds.ls(selection=True, long=True, objectsOnly=True) or []:
        node = selected
        try:
            if cmds.nodeType(node) not in ("transform", "joint"):
                parents = cmds.listRelatives(node, parent=True, fullPath=True) or []
                node = parents[0] if parents else None
        except Exception:
            node = None
        if node and node not in result:
            result.append(node)
    return result


def _has_active_selection():
    try:
        return bool(cmds.ls(selection=True, long=True) or [])
    except Exception:
        return False


def _filter_recovery_to_selection(curves_data, objects_data, selected_nodes):
    if not selected_nodes:
        return [], [], []
    selected_names = set(selected_nodes)
    selected_short_names = set(node.rsplit("|", 1)[-1] for node in selected_nodes)
    selected_uuids = set(filter(None, (_node_uuid(node) for node in selected_nodes)))

    try:
        current_curves = set(cmds.listConnections(selected_nodes, type="animCurve") or [])
        current_curves.update(cmds.keyframe(selected_nodes, query=True, name=True) or [])
    except Exception:
        current_curves = set()
    current_curve_uuids = set(filter(None, (_node_uuid(curve) for curve in current_curves)))

    def _matches_node(node, node_uuid):
        if node_uuid:
            return node_uuid in selected_uuids
        return (
            node in selected_names
            or (node and node.rsplit("|", 1)[-1] in selected_short_names)
        )

    filtered_objects = [
        item for item in objects_data
        if _matches_node(item.get("name"), item.get("uuid"))
    ]
    filtered_curves = []
    for curve_data in curves_data:
        if (
            curve_data.get("name") in current_curves
            or curve_data.get("uuid") in current_curve_uuids
            or any(
                _matches_node(endpoint.get("node"), endpoint.get("node_uuid"))
                for endpoint in curve_data.get("output_connections") or []
            )
        ):
            filtered_curves.append(curve_data)
    return filtered_curves, filtered_objects, sorted(current_curves)


def _restore_object_states(objects_data, uuid_lookup, operation=None):
    for object_data in objects_data:
        attributes = object_data.get("attributes") or {}
        node_uuid = object_data.get("uuid")
        node = uuid_lookup.get(node_uuid)
        if (not node or not cmds.objExists(node)) and not node_uuid:
            node = object_data.get("name")
        if not node or not cmds.objExists(node):
            if operation and operation.step(len(attributes)):
                return False
            continue
        for attribute, value in attributes.items():
            if operation and operation.cancelled:
                return False
            plug = "{}.{}".format(node, attribute)
            try:
                if cmds.objExists(plug) and cmds.getAttr(plug, settable=True):
                    cmds.setAttr(plug, value)
            except Exception:
                pass
            if operation and operation.step():
                return False
    return True


def restore_recovery(path):
    checkpoint_scene_id = _recovery_scene_id(path)
    scene_id = current_scene_id(create=False)
    if not checkpoint_scene_id:
        raise ValueError("Recovery checkpoint is outside the Animation Recovery folder")
    if not scene_id or checkpoint_scene_id != scene_id:
        raise ValueError("This recovery belongs to another Maya scene")
    chain_paths = _recovery_chain_paths(path)
    service = get_service()
    with service.restoring() if service else _null_context():
        with toolCommon.tool_operation(
            tool_id="animation_recovery_restore",
            label="Recovering Animation",
            progress=True,
            progress_max=max(1, len(chain_paths)),
            undo=True,
            undo_name=toolCommon.make_undo_chunk_name(tool_id="animation_recovery_restore"),
            suspend_refresh=True,
        ) as operation:
            payload = _load_merged_recovery(path, operation=operation, chain_paths=chain_paths)
            if payload is None:
                return False
            curves_data = payload.get("curves") or []
            objects_data = payload.get("objects") or []
            meta = payload.get("meta") or {}
            if meta.get("type") not in (None, "animation_recovery"):
                raise ValueError("Not an Animation Recovery file")
            if meta.get("scene_id") and scene_id and meta.get("scene_id") != scene_id:
                raise ValueError("This recovery belongs to another Maya scene")

            selection_scoped = _has_active_selection()
            selected_nodes = _selected_transform_nodes()
            scoped_curves = None
            if selection_scoped:
                curves_data, objects_data, scoped_curves = _filter_recovery_to_selection(
                    curves_data,
                    objects_data,
                    selected_nodes,
                )
                if not curves_data and not objects_data:
                    wutil.make_inViewMessage("No recovery data for the selected objects")
                    return False
            current_curves = _curve_maps(scoped_curves)[0]
            _all_curves, by_name, by_uuid = _curve_maps()
            saved_uuids = set(item.get("uuid") for item in curves_data if item.get("uuid"))
            saved_legacy_names = set(
                item.get("name") for item in curves_data
                if item.get("name") and not item.get("uuid")
            )
            extra_curves = [
                curve for curve in current_curves
                if _node_uuid(curve) not in saved_uuids and curve not in saved_legacy_names
            ]
            key_total = sum(len(item.get("positions") or []) for item in curves_data)
            attribute_total = sum(len(item.get("attributes") or {}) for item in objects_data)
            operation.set_total(
                len(chain_paths) + len(extra_curves) + key_total + attribute_total,
                reset=False,
            )
            operation.set_status("Applying recovery")
            for curve in extra_curves:
                if operation.cancelled:
                    return False
                try:
                    cmds.delete(curve)
                except Exception:
                    pass
                operation.step()

            uuid_lookup = _uuid_lookup()
            for curve_data in curves_data:
                if operation.cancelled:
                    return False
                curve_uuid = curve_data.get("uuid")
                curve = by_uuid.get(curve_uuid)
                if not curve and not curve_uuid:
                    curve = by_name.get(curve_data.get("name"))
                if not curve or not cmds.objExists(curve):
                    if not _has_resolvable_curve_output(curve_data, uuid_lookup):
                        if operation.step(len(curve_data.get("positions") or [])):
                            return False
                        continue
                    curve = cmds.createNode(curve_data.get("node_type") or "animCurveTU", name=curve_data.get("name"))
                _connect_curve(curve, curve_data, uuid_lookup)
                if not _set_curve_keys(curve, curve_data, operation=operation):
                    return False
            if not _restore_object_states(objects_data, uuid_lookup, operation=operation):
                return False

    wutil.make_inViewMessage("Animation recovered")
    return True


@contextmanager
def _null_context():
    yield


class _SnapshotWriterSignals(QtCore.QObject):
    saved = QtCore.Signal(str)
    failed = QtCore.Signal(str)


class _SnapshotWriteTask(QtCore.QRunnable):
    def __init__(self, path, payload, signals):
        QtCore.QRunnable.__init__(self)
        self.path = path
        self.payload = payload
        self.signals = signals
        self.setAutoDelete(True)

    def run(self):
        try:
            meta = self.payload.get("meta") or {}
            parent_name = meta.get("parent_checkpoint")
            if not meta.get("full_snapshot") and parent_name:
                parent_path = os.path.join(os.path.dirname(self.path), parent_name)
                if not os.path.isfile(parent_path):
                    raise IOError(
                        "Animation Recovery parent checkpoint was not saved: {}".format(
                            parent_name
                        )
                    )
            _write_recovery_atomic(self.path, self.payload)
            scene_id = _recovery_scene_id(self.path)
            if scene_id and meta.get("full_snapshot"):
                try:
                    _prune_recovery_history(scene_id)
                except Exception:
                    # Retention is maintenance; a successfully written recovery
                    # must remain successful if old files cannot be removed.
                    pass
        except Exception as exc:
            self.signals.failed.emit(six.text_type(exc))
            return
        self.signals.saved.emit(self.path)


class AnimationRecoveryService(QtCore.QObject):
    snapshotSaved = QtCore.Signal(str)

    def __init__(self, manager):
        QtCore.QObject.__init__(self, manager)
        self.manager = manager
        self.scene_id = None
        self._suspend_count = 0
        self._pending_reason = None
        self._pending_curve_names = set()
        self._pending_object_names = set()
        self._pending_object_attributes = {}
        self._full_refresh_pending = False
        self._curve_cache = None
        self._object_cache = {}
        self._attribute_cache = {}
        self._last_snapshot_timestamp = 0.0
        self._last_checkpoint_name = None
        self._snapshots_since_baseline = 0
        self._last_prompted_checkpoint = None
        self._timer = QtCore.QTimer(self)
        self._timer.setSingleShot(True)
        self._timer.setInterval(SNAPSHOT_DELAY_MS)
        self._timer.timeout.connect(self.capture_now)
        self._rewatch_timer = QtCore.QTimer(self)
        self._rewatch_timer.setSingleShot(True)
        self._rewatch_timer.setInterval(REWATCH_DELAY_MS)
        self._rewatch_timer.timeout.connect(self._watch_scene_objects)
        self._thread_pool = QtCore.QThreadPool(self)
        self._thread_pool.setMaxThreadCount(1)
        self._writer_signals = _SnapshotWriterSignals(self)
        self._writer_signals.saved.connect(self._on_snapshot_saved)
        self._writer_signals.failed.connect(self._on_snapshot_failed)

    @contextmanager
    def suspended(self):
        self._suspend_count += 1
        self._timer.stop()
        try:
            yield
        finally:
            self._suspend_count = max(0, self._suspend_count - 1)

    def discard_pending(self):
        """Discard deferred work so a recovery never becomes a checkpoint."""
        self._timer.stop()
        self._pending_reason = None
        self._pending_curve_names.clear()
        self._pending_object_names.clear()
        self._pending_object_attributes.clear()
        self._full_refresh_pending = False

    @contextmanager
    def restoring(self):
        self.discard_pending()
        with self.suspended():
            try:
                yield
            finally:
                self.discard_pending()

    def _initialize_history_state(self):
        """Use only a checkpoint with a fully readable chain as the next parent."""
        self._last_checkpoint_name = None
        self._last_snapshot_timestamp = 0.0
        self._snapshots_since_baseline = 0
        if not self.scene_id:
            return

        paths = _recovery_paths(scene_id=self.scene_id)
        if not paths:
            return
        self._last_snapshot_timestamp = _filename_timestamp_value(paths[-1])
        valid_path = _newest_valid_recovery(paths)
        if not valid_path:
            self._snapshots_since_baseline = BASELINE_INTERVAL
            return

        self._last_checkpoint_name = os.path.basename(valid_path)
        if os.path.realpath(valid_path) != os.path.realpath(paths[-1]):
            self._snapshots_since_baseline = BASELINE_INTERVAL
            return
        try:
            chain_paths = _recovery_chain_paths(valid_path)
            version, full_snapshot = _recovery_header(chain_paths[0])
            baseline_offset = 1 if version >= 5 and full_snapshot else 0
            self._snapshots_since_baseline = max(0, len(chain_paths) - baseline_offset)
        except Exception:
            self._last_checkpoint_name = None
            self._snapshots_since_baseline = BASELINE_INTERVAL

    def start(self):
        if self.scene_id:
            return self
        with self.suspended():
            self.scene_id = ensure_scene_id()
        if not self.scene_id:
            return self
        self._initialize_history_state()
        self.manager.add_anim_curve_edited_callback(
            self._animation_changed,
            key=RUNTIME_ANIMATION_KEY,
        )
        self.manager.add_dag_change_callback(
            self._dag_changed,
            key=RUNTIME_DAG_KEY,
        )
        self.manager.connect_signal(
            self.manager.scene_opened,
            self._scene_opened,
            key=RUNTIME_SCENE_KEY + ":open",
        )
        self.manager.connect_signal(
            self.manager.scene_new,
            self._scene_changed,
            key=RUNTIME_SCENE_KEY + ":new",
        )
        self.manager.connect_signal(
            self.manager.scene_saved,
            self._scene_saved,
            key=RUNTIME_SCENE_KEY + ":save",
        )
        self._watch_scene_objects()
        QtCore.QTimer.singleShot(0, self._show_recovery_if_scene_is_older)
        return self

    def shutdown(self):
        self._timer.stop()
        self._rewatch_timer.stop()
        if not self._thread_pool.waitForDone(2000):
            self._thread_pool.waitForDone(-1)
        for key in (
            RUNTIME_ANIMATION_KEY,
            RUNTIME_DAG_KEY,
            RUNTIME_SCENE_KEY + ":open",
            RUNTIME_SCENE_KEY + ":new",
            RUNTIME_SCENE_KEY + ":save",
            RUNTIME_TRANSFORM_KEY,
        ):
            self.manager.disconnect_callbacks(key)
        self.scene_id = None
        self._curve_cache = None
        self.discard_pending()
        self._object_cache.clear()
        self._attribute_cache.clear()
        self._last_snapshot_timestamp = 0.0
        self._last_checkpoint_name = None
        self._snapshots_since_baseline = 0
        self._last_prompted_checkpoint = None

    def _scene_changed(self, *_args):
        with self.suspended():
            self.discard_pending()
            self._curve_cache = None
            self._object_cache.clear()
            self._attribute_cache.clear()
            self.scene_id = ensure_scene_id()
            self._initialize_history_state()
            self._last_prompted_checkpoint = None
        self._rewatch_timer.start()

    def _scene_opened(self, *_args):
        self._scene_changed()
        QtCore.QTimer.singleShot(0, self._show_recovery_if_scene_is_older)

    def _show_recovery_if_scene_is_older(self):
        if self._suspend_count or not self.scene_id:
            return
        try:
            if cmds.about(batch=True):
                return
        except Exception:
            pass
        checkpoint = newer_recovery_for_current_scene(scene_id=self.scene_id)
        if not checkpoint or checkpoint == self._last_prompted_checkpoint:
            return
        self._last_prompted_checkpoint = checkpoint
        try:
            from TheKeyMachine.tools.animation_recovery import widgets

            widgets.show_dialog()
        except Exception as exc:
            try:
                cmds.warning("Animation Recovery could not open: {}".format(exc))
            except Exception:
                pass

    def _animation_changed(self, *args):
        if _maya_file_io_active():
            return
        curve_names = _edited_curve_names(args)
        self.schedule_snapshot(
            "animation",
            curve_names=curve_names,
            full=not bool(curve_names),
        )

    def _scene_saved(self, *_args):
        if self._timer.isActive():
            self.capture_now()
        self.capture_now(reason="scene_save")

    def _dag_changed(self, *_args):
        if _maya_file_io_active():
            return
        self._rewatch_timer.start()
        self.schedule_snapshot("dag", full=True)

    def _watch_scene_objects(self):
        if self._suspend_count or not self.scene_id:
            return
        self.manager.disconnect_callbacks(RUNTIME_TRANSFORM_KEY)
        nodes = set(cmds.ls(type="transform", long=True) or [])
        nodes.update(cmds.ls(type="joint", long=True) or [])
        # Discover channels lazily on first edit. Registering callbacks is
        # already proportional to scene size; startup should not also query
        # every attribute on every transform.
        self._attribute_cache = {
            node: attributes
            for node, attributes in self._attribute_cache.items()
            if node in nodes
        }
        self.manager.add_node_attribute_changed_callbacks(
            sorted(nodes),
            self._object_attribute_changed,
            key=RUNTIME_TRANSFORM_KEY,
        )

    def _object_attribute_changed(self, *args):
        if self._suspend_count or om is None or len(args) < 2 or _maya_file_io_active():
            return
        message, plug = args[0], args[1]
        node = args[-1]
        structure_change = (
            om.MNodeMessage.kAttributeAdded
            | om.MNodeMessage.kAttributeRemoved
            | om.MNodeMessage.kAttributeRenamed
            | om.MNodeMessage.kAttributeKeyable
            | om.MNodeMessage.kAttributeUnkeyable
            | om.MNodeMessage.kAttributeLocked
            | om.MNodeMessage.kAttributeUnlocked
        )
        if message & structure_change:
            self._attribute_cache[node] = set(_recoverable_attributes(node))
            try:
                attribute = plug.partialName(useLongNames=True)
            except Exception:
                attribute = None
            if attribute in self._attribute_cache[node]:
                if _attribute_is_animated(node, attribute):
                    return
                self.schedule_snapshot(
                    "transform",
                    object_attributes={node: [attribute]},
                )
            return
        if not (message & om.MNodeMessage.kAttributeSet):
            return
        try:
            attribute = plug.partialName(useLongNames=True)
        except Exception:
            return
        attributes = self._attribute_cache.get(node)
        if attributes is None:
            attributes = set(_recoverable_attributes(node))
            self._attribute_cache[node] = attributes
        if attribute not in attributes:
            return
        if _attribute_is_animated(node, attribute):
            return
        self.schedule_snapshot(
            "transform",
            object_attributes={node: [attribute]},
        )

    def schedule_snapshot(
        self,
        reason="animation",
        curve_names=None,
        object_names=None,
        object_attributes=None,
        full=False,
    ):
        if self._suspend_count or not self.scene_id:
            return
        self._pending_reason = reason
        self._pending_curve_names.update(curve_names or [])
        self._pending_object_names.update(object_names or [])
        for node, attributes in (object_attributes or {}).items():
            self._pending_object_attributes.setdefault(node, set()).update(attributes or [])
        self._full_refresh_pending = self._full_refresh_pending or bool(full)
        self._timer.start()

    def _full_payload(self, reason, force_baseline=False):
        payload, created = capture_scene_animation(self.scene_id, reason=reason)
        current_cache = {
            curve_data.get("name"): curve_data
            for curve_data in payload.get("curves") or []
            if curve_data.get("name")
        }
        baseline = self._curve_cache is None or bool(force_baseline)
        previous_cache = self._curve_cache or {}
        if baseline:
            changed_curves = list(current_cache.values())
            removed_curves = []
        else:
            changed_curves = [
                curve_data
                for name, curve_data in current_cache.items()
                if previous_cache.get(name) != curve_data
            ]
            removed_curves = [
                _curve_marker(curve_data, fallback_name=name)
                for name, curve_data in previous_cache.items()
                if name not in current_cache
            ]
        self._curve_cache = current_cache
        payload["curves"] = changed_curves
        payload["removed_curves"] = removed_curves
        payload["meta"]["full_snapshot"] = baseline
        return payload, created

    def _incremental_payload(self, reason, changed_names):
        current_names = set(cmds.ls(type="animCurve") or [])
        changed_curves = []
        removed_curves = []
        for cached_name in list(self._curve_cache):
            if cached_name not in current_names:
                removed = self._curve_cache.pop(cached_name, None)
                if removed:
                    removed_curves.append(_curve_marker(removed, fallback_name=cached_name))
        for curve in changed_names:
            if curve not in current_names:
                removed = self._curve_cache.pop(curve, None)
                if removed and not any(_curve_matches(removed, item) for item in removed_curves):
                    removed_curves.append(_curve_marker(removed, fallback_name=curve))
                continue
            try:
                curve_data = _capture_curve(curve)
            except Exception:
                continue
            if curve_data.get("positions"):
                if self._curve_cache.get(curve) != curve_data:
                    changed_curves.append(curve_data)
                self._curve_cache[curve] = curve_data
            else:
                removed = self._curve_cache.pop(curve, None)
                if removed:
                    removed_curves.append(_curve_marker(removed, fallback_name=curve))

        created = datetime.now()
        payload = {
            "meta": _scene_snapshot_meta(self.scene_id, reason, created, changed_curves),
            "curves": changed_curves,
            "removed_curves": removed_curves,
        }
        return payload, created

    def _captured_objects(
        self,
        changed_names=None,
        changed_attributes=None,
        all_objects=False,
        complete_snapshot=False,
    ):
        requested = {
            node: set(attributes)
            for node, attributes in (changed_attributes or {}).items()
        }
        for node in changed_names or []:
            requested[node] = None
        if all_objects:
            names = set(cmds.ls(type="transform", long=True) or [])
            names.update(cmds.ls(type="joint", long=True) or [])
            requested.update((node, None) for node in names)
        changed_objects = []
        if complete_snapshot:
            self._object_cache.clear()
        for node, attributes in requested.items():
            node_uuid = _node_uuid(node)
            cache_key = node_uuid or node
            state = _capture_object_state(node, attributes=attributes)
            if state:
                cached = self._object_cache.get(cache_key) or {
                    "name": state.get("name"),
                    "uuid": state.get("uuid"),
                    "attributes": {},
                }
                changed_values = dict(state.get("attributes") or {}) if complete_snapshot else {
                    name: value
                    for name, value in (state.get("attributes") or {}).items()
                    if cached["attributes"].get(name) != value
                }
                cached["name"] = state.get("name")
                cached["uuid"] = state.get("uuid")
                cached["attributes"].update(state.get("attributes") or {})
                self._object_cache[cache_key] = cached
                if changed_values:
                    changed_objects.append({
                        "name": state.get("name"),
                        "uuid": state.get("uuid"),
                        "attributes": changed_values,
                    })
            else:
                self._object_cache.pop(cache_key, None)
        return changed_objects

    def capture_now(self, reason=None, full=False, all_objects=False):
        if self._suspend_count or not self.scene_id:
            return None
        self._timer.stop()
        reason = reason or self._pending_reason or "animation"
        changed_names = set(self._pending_curve_names)
        changed_objects = set(self._pending_object_names)
        changed_object_attributes = {
            node: set(attributes)
            for node, attributes in self._pending_object_attributes.items()
        }
        force_baseline = self._snapshots_since_baseline >= BASELINE_INTERVAL
        full = bool(full or self._full_refresh_pending or self._curve_cache is None or force_baseline)
        self._pending_reason = None
        self._pending_curve_names.clear()
        self._pending_object_names.clear()
        self._pending_object_attributes.clear()
        self._full_refresh_pending = False
        with self.suspended():
            if full:
                payload, created = self._full_payload(reason, force_baseline=force_baseline)
            else:
                payload, created = self._incremental_payload(reason, changed_names)
            for node, attributes in _removed_curve_attributes(
                payload.get("removed_curves") or []
            ).items():
                changed_object_attributes.setdefault(node, set()).update(attributes)
            complete_snapshot = bool((payload.get("meta") or {}).get("full_snapshot"))
            payload["objects"] = self._captured_objects(
                changed_names=changed_objects,
                changed_attributes=changed_object_attributes,
                all_objects=all_objects or complete_snapshot,
                complete_snapshot=complete_snapshot,
            )
            if (
                reason in ("animation", "transform")
                and not payload.get("curves")
                and not payload.get("objects")
                and not payload.get("removed_curves")
            ):
                return None
            folder = scene_recovery_folder(self.scene_id, create=True)
            timestamp = max(
                float(_safe_filename_timestamp(created)),
                self._last_snapshot_timestamp + 0.000001,
            )
            path = os.path.join(folder, "{:.8f}{}".format(timestamp, RECOVERY_EXTENSION))
            while os.path.exists(path):
                timestamp += 0.000001
                path = os.path.join(folder, "{:.8f}{}".format(timestamp, RECOVERY_EXTENSION))
            self._last_snapshot_timestamp = timestamp
            payload["meta"]["parent_checkpoint"] = self._last_checkpoint_name
            self._last_checkpoint_name = os.path.basename(path)
            if complete_snapshot:
                self._snapshots_since_baseline = 0
            else:
                self._snapshots_since_baseline += 1
        self._thread_pool.start(_SnapshotWriteTask(path, payload, self._writer_signals))
        return path

    def _on_snapshot_saved(self, path):
        self.snapshotSaved.emit(path)
        try:
            self.manager.backgroundRunnerTriggered.emit("animation_recovery")
        except Exception:
            pass

    def _on_snapshot_failed(self, message):
        # Any queued delta may depend on the failed point. Rebuild both caches
        # so the next real checkpoint is a self-contained baseline.
        self._curve_cache = None
        self._object_cache.clear()
        self._initialize_history_state()
        self._snapshots_since_baseline = BASELINE_INTERVAL
        try:
            cmds.warning("Animation Recovery could not save a snapshot: {}".format(message))
        except Exception:
            pass


def get_service():
    return _SERVICE


def start(manager=None):
    global _SERVICE
    if _SERVICE is not None:
        if not _SERVICE.scene_id:
            _SERVICE.start()
        return _SERVICE
    if manager is None:
        from TheKeyMachine.core import runtimeManager as runtime

        manager = runtime.get_runtime_manager()
    _SERVICE = AnimationRecoveryService(manager)
    _SERVICE.start()
    return _SERVICE


def set_enabled(enabled, manager=None):
    from TheKeyMachine.core import backgroundRunners

    runner_controller = (
        backgroundRunners.get_controller(manager)
        if manager is not None
        else backgroundRunners.get_controller()
    )
    runner_controller.set_enabled(
        backgroundRunners.ANIMATION_RECOVERY_ID,
        bool(enabled),
    )
    return bool(enabled)


def set_persisted_enabled(enabled):
    enabled = bool(enabled)
    settings.set_setting(ENABLED_SETTING, enabled, namespace=SETTINGS_NAMESPACE)
    mark_startup_prompted()
    return enabled


def shutdown():
    global _SERVICE
    if _SERVICE is not None:
        try:
            _SERVICE.shutdown()
            _SERVICE.setParent(None)
            _SERVICE.deleteLater()
        except Exception:
            pass
    _SERVICE = None
