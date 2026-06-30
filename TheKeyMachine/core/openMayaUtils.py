"""
Small OpenMaya API 2.0 helpers shared by core tools.

These helpers avoid command-layer writes for simple dependency-node plug edits,
which keeps automatic/background updates out of Maya undo history.
"""

from __future__ import annotations

try:
    from maya.api import OpenMaya as om  # type: ignore
except ImportError:  # pragma: no cover
    om = None


def is_available():
    return om is not None


def mobject_from_node(node):
    if om is None or not node:
        return None
    try:
        if isinstance(node, om.MObject):
            return node
        selection = om.MSelectionList()
        selection.add(str(node))
        return selection.getDependNode(0)
    except Exception:
        return None


def dependency_node_fn(node):
    mobject = mobject_from_node(node)
    if mobject is None:
        return None
    try:
        return om.MFnDependencyNode(mobject)
    except Exception:
        return None


def find_plug(node, attr, want_networked=False):
    fn = dependency_node_fn(node)
    if fn is None:
        return None
    try:
        return fn.findPlug(str(attr), bool(want_networked))
    except Exception:
        return None


def values_match(current, target, tolerance=0.000001):
    try:
        return all(abs(float(a) - float(b)) <= tolerance for a, b in zip(current, target))
    except Exception:
        return False


def set_plug_double(node, attr, value, tolerance=0.000001):
    plug = find_plug(node, attr)
    if plug is None:
        return False
    try:
        value = float(value)
        if abs(float(plug.asDouble()) - value) <= tolerance:
            return False
        plug.setDouble(value)
        return True
    except Exception:
        return False


def set_plug_vector(node, attr, values, tolerance=0.000001):
    plug = find_plug(node, attr)
    if plug is None:
        return False

    try:
        target = tuple(float(value) for value in values)
    except Exception:
        return False
    if len(target) != 3:
        return False

    try:
        children = [plug.child(index) for index in range(3)] if plug.isCompound else []
        if len(children) == 3:
            current = tuple(child.asDouble() for child in children)
            if values_match(current, target, tolerance=tolerance):
                return False
            for child, value in zip(children, target):
                child.setDouble(value)
            return True

        if plug.isArray:
            return False

        current = plug.asMDataHandle().asDouble3()
        if values_match(current, target, tolerance=tolerance):
            return False
        data = om.MFnNumericData().create(om.MFnNumericData.k3Double, target[0], target[1], target[2])
        plug.setMObject(data)
        return True
    except Exception:
        return False
