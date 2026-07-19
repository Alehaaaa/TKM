import json
import os

from maya import cmds

from TheKeyMachine.core import animation_context
from TheKeyMachine.mods import generalMod as general
from TheKeyMachine.mods import selectionMod
from TheKeyMachine.tools import common as toolCommon
from TheKeyMachine.widgets import util as wutil


TRANSLATION_ATTRS = {"translate", "translateX", "translateY", "translateZ"}
ROTATION_ATTRS = {"rotate", "rotateX", "rotateY", "rotateZ"}
SCALE_ATTRS = {"scale", "scaleX", "scaleY", "scaleZ"}


def _data_path():
    return general.get_set_default_data_file()


def _load_data():
    path = _data_path()
    if not os.path.isfile(path):
        return {}
    try:
        with open(path, "r", encoding="utf-8") as stream:
            data = json.load(stream)
        return data if isinstance(data, dict) else {}
    except (OSError, ValueError, TypeError):
        return {}


def _save_data(data):
    path = _data_path()
    os.makedirs(os.path.dirname(path), exist_ok=True)
    with open(path, "w", encoding="utf-8") as stream:
        json.dump(data, stream, indent=4, sort_keys=True)


def _object_identity(node):
    basename = node.rsplit("|", 1)[-1]
    if ":" not in basename:
        return "default", basename
    return basename.rsplit(":", 1)


def _stored_default(node, attr, data):
    namespace, short_name = _object_identity(node)
    stored = data.get(namespace, {}).get("{}.{}".format(short_name, attr))
    if stored is not None:
        return stored
    fallback = cmds.attributeQuery(attr, node=node, listDefault=True)
    return fallback[0] if fallback else None


def save_selected():
    selected = selectionMod.get_selected_objects(long=True)
    if not selected:
        return wutil.make_inViewMessage("Select at least one object.")
    data = _load_data()
    for node in selected:
        namespace, short_name = _object_identity(node)
        values = data.setdefault(namespace, {})
        for attr in cmds.listAttr(node, keyable=True, unlocked=True, visible=True) or []:
            if attr != "tag":
                values["{}.{}".format(short_name, attr)] = cmds.getAttr("{}.{}".format(node, attr))
    _save_data(data)
    wutil.make_inViewMessage("Default values saved.")


def remove_selected():
    selected = selectionMod.get_selected_objects(long=True)
    if not selected:
        return wutil.make_inViewMessage("Select at least one object.")
    data = _load_data()
    for node in selected:
        namespace, short_name = _object_identity(node)
        values = data.get(namespace, {})
        prefix = short_name + "."
        data[namespace] = {key: value for key, value in values.items() if not key.startswith(prefix)}
        if not data[namespace]:
            data.pop(namespace, None)
    _save_data(data)
    wutil.make_inViewMessage("Saved defaults removed for the selection.")


def clear_all():
    if not os.path.isfile(_data_path()):
        return wutil.make_inViewMessage("No saved default values found.")
    _save_data({})
    wutil.make_inViewMessage("All saved default values cleared.")


def _matches(attr, translations, rotations, scales):
    if not any((translations, rotations, scales)):
        return True
    return ((translations and attr in TRANSLATION_ATTRS)
            or (rotations and attr in ROTATION_ATTRS)
            or (scales and attr in SCALE_ATTRS))


def apply_defaults(translations=False, rotations=False, scales=False):
    tool_id = "default_trs" if all((translations, rotations, scales)) else (
        "default_translations" if translations else "default_rotations" if rotations else
        "default_scales" if scales else "default_object_values"
    )
    data = _load_data()
    target_info = animation_context.resolve_targets(default_mode="current_frame", ordered_selection=True, long_names=True)
    selected = target_info["target_objects"]
    if not selected and not target_info["target_plugs"]:
        return wutil.make_inViewMessage("Select objects, channels, or Graph Editor keys.")

    with toolCommon.tool_operation(tool_id=tool_id, undo=True, tint="context", default_mode="current_frame"):
        if target_info["time_context"].mode == "graph_editor_keys":
            for curve, frame in target_info["selected_keyframes"]:
                destinations = cmds.listConnections(curve + ".output", plugs=True, source=False, destination=True) or []
                if not destinations or "." not in destinations[0]:
                    continue
                node, attr = destinations[0].split(".", 1)
                if not _matches(attr, translations, rotations, scales):
                    continue
                value = _stored_default(node, attr, data)
                if value is not None:
                    cmds.keyframe(curve, edit=True, valueChange=value, time=(frame, frame))
            return

        for plug in target_info["target_plugs"]:
            if "." not in plug:
                continue
            node, attr = plug.split(".", 1)
            if not _matches(attr, translations, rotations, scales) or cmds.getAttr(plug, lock=True):
                continue
            value = _stored_default(node, attr, data)
            if value is None:
                continue
            time_context = target_info["time_context"]
            if time_context.mode == "current_frame":
                cmds.setAttr(plug, value)
                continue
            for frame in cmds.keyframe(plug, query=True, time=time_context.timerange) or []:
                cmds.setKeyframe(node, attribute=attr, time=(frame,), value=value)
