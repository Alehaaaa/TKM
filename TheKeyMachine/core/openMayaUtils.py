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

try:
    from maya.api import OpenMayaAnim as oma  # type: ignore
except ImportError:  # pragma: no cover
    oma = None


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


def mobject_name(node, absolute=True):
    """Return the dependency-node name for an MObject or Maya node name."""
    fn = dependency_node_fn(node)
    if fn is None:
        return None
    if absolute:
        try:
            return fn.absoluteName()
        except Exception:
            pass
    try:
        return fn.name()
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


def mplug_from_name(plug_name):
    """Resolve a complete Maya plug path, including arrays and compounds."""
    if om is None or not plug_name:
        return None
    try:
        selection = om.MSelectionList()
        selection.add(str(plug_name))
        return selection.getPlug(0)
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


def closest_euler_angle_cut(value, reference):
    """Return value's full-turn-equivalent angle closest to reference.

    Inputs and output use Maya's current UI angle unit. MEulerRotation performs
    the closest-cut calculation in radians.
    """
    if om is None:
        return None
    try:
        source_radians = om.MAngle(float(value), om.MAngle.uiUnit()).asRadians()
        reference_radians = om.MAngle(float(reference), om.MAngle.uiUnit()).asRadians()
        source = om.MEulerRotation(source_radians, 0.0, 0.0, om.MEulerRotation.kXYZ)
        target = om.MEulerRotation(reference_radians, 0.0, 0.0, om.MEulerRotation.kXYZ)
        closest = source.closestCut(target)
        return om.MAngle(closest.x, om.MAngle.kRadians).asUnits(om.MAngle.uiUnit())
    except Exception:
        return None


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


def set_numeric_plug_value(plug_name, value, tolerance=0.000001):
    try:
        node, attr = str(plug_name).split(".", 1)
    except ValueError:
        return False
    plug = find_plug(node, attr)
    if plug is None:
        return False
    try:
        value = float(value)
        if abs(float(plug.asDouble()) - value) > tolerance:
            plug.setDouble(value)
        return True
    except Exception:
        return False


def anim_curve_fn(curve):
    if om is None or oma is None or not curve:
        return None
    mobject = mobject_from_node(curve)
    if mobject is None:
        return None
    try:
        if not mobject.hasFn(om.MFn.kAnimCurve):
            return None
        return oma.MFnAnimCurve(mobject)
    except Exception:
        return None


def time_unit():
    if om is None:
        return None
    try:
        return om.MTime.uiUnit()
    except Exception:
        return om.MTime.kFilm


def current_time():
    """Return Maya's current time in the active UI time unit."""
    if oma is None:
        return None
    try:
        return float(oma.MAnimControl.currentTime().asUnits(time_unit()))
    except Exception:
        return None


def set_current_time(time):
    """Set Maya's current time through MAnimControl, outside command undo."""
    if om is None or oma is None:
        return False
    try:
        oma.MAnimControl.setCurrentTime(om.MTime(float(time), time_unit()))
        return True
    except Exception:
        return False


def add_event_callback(event_name, callback):
    """Register a Maya event callback and return its numeric callback ID."""
    if om is None or not event_name or not callable(callback):
        return None
    try:
        return int(om.MEventMessage.addEventCallback(str(event_name), callback))
    except Exception:
        return None


def remove_callback(callback_id):
    """Remove a Maya API callback without raising for stale callback IDs."""
    if om is None or callback_id is None:
        return False
    try:
        om.MMessage.removeCallback(int(callback_id))
        return True
    except Exception:
        return False


def _anim_curve_fns(curves):
    if om is None or oma is None:
        return []
    selection = om.MSelectionList()
    count = 0
    for curve in dict.fromkeys(curves or []):
        if not curve:
            continue
        try:
            selection.add(str(curve))
            count += 1
        except Exception:
            continue

    functions = []
    for selection_index in range(count):
        try:
            node = selection.getDependNode(selection_index)
            if not node.hasFn(om.MFn.kAnimCurve):
                continue
            functions.append(oma.MFnAnimCurve(node))
        except Exception:
            continue
    return functions


def _anim_curve_key_count(fn):
    value = fn.numKeys
    return int(value() if callable(value) else value)


def _anim_curve_input(fn, index, unit):
    return float(fn.input(index).asUnits(unit))


def _first_key_after(fn, time, unit):
    low = 0
    high = _anim_curve_key_count(fn)
    while low < high:
        middle = (low + high) // 2
        if _anim_curve_input(fn, middle, unit) <= time:
            low = middle + 1
        else:
            high = middle
    return low


def _last_key_before(fn, time, unit):
    return _first_key_after(fn, time - 0.0000000001, unit) - 1


def step_anim_curve_key_time(
    curves,
    current,
    amount,
    time_range=None,
    tolerance=0.000001,
):
    """Step through the union of curve keys without scanning every key."""
    try:
        current = float(current)
        amount = int(amount)
        tolerance = abs(float(tolerance))
    except (TypeError, ValueError, OverflowError):
        return None
    if not amount:
        return current

    bounds = None
    if time_range:
        try:
            bounds = tuple(sorted((
                float(time_range[0]),
                float(time_range[1]),
            )))
        except (IndexError, TypeError, ValueError):
            bounds = None

    functions = _anim_curve_fns(curves)
    if not functions:
        return None
    unit = time_unit()
    direction = 1 if amount > 0 else -1

    def candidate(fn, position, wrap=False):
        count = _anim_curve_key_count(fn)
        if not count:
            return None
        lower = bounds[0] if bounds else None
        upper = bounds[1] if bounds else None
        if direction > 0:
            threshold = position + tolerance
            if lower is not None:
                threshold = max(threshold, lower - tolerance)
            if wrap:
                index = 0 if lower is None else _first_key_after(
                    fn, lower - tolerance, unit
                )
            else:
                index = _first_key_after(fn, threshold, unit)
            if index >= count:
                return None
        else:
            threshold = position - tolerance
            if upper is not None:
                threshold = min(threshold, upper + tolerance)
            if wrap:
                index = count - 1 if upper is None else _last_key_before(
                    fn, upper + tolerance, unit
                )
            else:
                index = _last_key_before(fn, threshold, unit)
            if index < 0:
                return None
        value = _anim_curve_input(fn, index, unit)
        if lower is not None and value < lower - tolerance:
            return None
        if upper is not None and value > upper + tolerance:
            return None
        return value

    position = current
    for _step in range(abs(amount)):
        candidates = [
            value
            for value in (
                candidate(fn, position)
                for fn in functions
            )
            if value is not None
        ]
        if not candidates:
            candidates = [
                value
                for value in (
                    candidate(fn, position, wrap=True)
                    for fn in functions
                )
                if value is not None
            ]
        if not candidates:
            return None
        position = min(candidates) if direction > 0 else max(candidates)
    return position


def _matrix_values(matrix):
    try:
        return [
            float(matrix[row][column])
            for row in range(4)
            for column in range(4)
        ]
    except Exception:
        return None


def _command_matrix_values(raw):
    if not raw:
        return None
    values = raw[0] if len(raw) == 1 and isinstance(raw[0], (list, tuple)) else raw
    try:
        values = [float(value) for value in values]
    except Exception:
        return None
    return values if len(values) == 16 else None


def world_matrix_at_time(node, time=None):
    """Evaluate a world matrix without changing Maya's current time."""
    if om is not None:
        try:
            plug = find_plug(node, "worldMatrix")
            if plug is not None:
                plug = plug.elementByLogicalIndex(0)
                context = (
                    om.MDGContext.kNormal
                    if time is None
                    else om.MDGContext(mtime(time))
                )
                matrix_object = plug.asMObject(context)
                values = _matrix_values(om.MFnMatrixData(matrix_object).matrix())
                if values is not None:
                    return values
        except Exception:
            pass

    try:
        from maya import cmds

        kwargs = {"time": float(time)} if time is not None else {}
        return _command_matrix_values(
            cmds.getAttr("{}.worldMatrix[0]".format(node), **kwargs)
        )
    except Exception:
        return None


def mtime(time):
    if om is None:
        return None
    return om.MTime(float(time), time_unit())


def anim_curve_value(fn, index, fallback=None):
    if fn is None or index is None:
        return fallback
    try:
        return fn.value(index)
    except Exception:
        return fallback


def anim_curve_value_at_time(fn, time, fallback=None):
    if fn is None:
        return fallback
    index = anim_curve_key_index(fn, time)
    if index is not None:
        return anim_curve_value(fn, index, fallback=fallback)
    try:
        target = mtime(time)
        if target is None:
            return fallback
        return fn.evaluate(target)
    except Exception:
        return fallback


def evaluate_anim_curve(fn, time, fallback=None):
    """Evaluate an animation curve directly without scanning its keys."""
    if fn is None:
        return fallback
    try:
        return fn.evaluate(mtime(time))
    except Exception:
        return fallback


def add_anim_curve_key(fn, time, change=None):
    if fn is None:
        return None
    target = mtime(time)
    if target is None:
        return None
    index = anim_curve_key_index(fn, time)
    if index is not None:
        return index
    try:
        value = fn.evaluate(target)
        if change is not None:
            return fn.addKey(target, value, change=change)
        return fn.addKey(target, value)
    except Exception:
        return None


def remove_anim_curve_key(fn, time, change=None):
    index = anim_curve_key_index(fn, time)
    if fn is None or index is None:
        return False
    try:
        if change is not None:
            fn.remove(index, change=change)
        else:
            fn.remove(index)
        return True
    except Exception:
        return False


def set_anim_curve_tangents(fn, time, in_angle, out_angle, change=None):
    """Set broken fixed tangents using Maya API angle/weight representation."""
    index = anim_curve_key_index(fn, time)
    if fn is None or index is None or om is None or oma is None:
        return False
    try:
        fn.setInTangentType(index, oma.MFnAnimCurve.kTangentFixed, change=change)
        fn.setOutTangentType(index, oma.MFnAnimCurve.kTangentFixed, change=change)
        fn.setTangentsLocked(index, False, change=change)
        fn.setTangent(index, om.MAngle(float(in_angle), om.MAngle.kDegrees), 1.0, True, change=change)
        fn.setTangent(index, om.MAngle(float(out_angle), om.MAngle.kDegrees), 1.0, False, change=change)
        return True
    except Exception:
        return False


def set_anim_curve_value_by_index(fn, index, value, change=None):
    if fn is None or index is None:
        return False
    try:
        if change is not None:
            fn.setValue(index, float(value), change=change)
        else:
            fn.setValue(index, float(value))
        return True
    except Exception:
        return False


def _anim_curve_type(fn):
    if fn is None:
        return None
    for getter in (
        lambda: fn.animCurveType(),
        lambda: fn.animCurveType,
    ):
        try:
            return getter()
        except Exception:
            pass
    return None


def anim_curve_value_to_attr_value(curve, value):
    """Convert an MFnAnimCurve value to command-layer attribute units."""
    if om is None or oma is None or curve is None:
        return value
    fn = anim_curve_fn(curve)
    curve_type = _anim_curve_type(fn)
    try:
        if curve_type == oma.MFnAnimCurve.kAnimCurveTA:
            return om.MAngle(float(value)).asUnits(om.MAngle.uiUnit())
    except Exception:
        pass
    try:
        if curve_type == oma.MFnAnimCurve.kAnimCurveTL:
            return om.MDistance(float(value)).asUnits(om.MDistance.uiUnit())
    except Exception:
        pass
    return value


def anim_curve_attr_value_to_curve_value(curve, value):
    """Convert a displayed Maya attribute value to MFnAnimCurve units."""
    if om is None or oma is None or curve is None:
        return value
    fn = anim_curve_fn(curve)
    curve_type = _anim_curve_type(fn)
    try:
        if curve_type == oma.MFnAnimCurve.kAnimCurveTA:
            return om.MAngle(float(value), om.MAngle.uiUnit()).asRadians()
    except Exception:
        pass
    try:
        if curve_type == oma.MFnAnimCurve.kAnimCurveTL:
            return om.MDistance(float(value), om.MDistance.uiUnit()).asCentimeters()
    except Exception:
        pass
    return value


def anim_curve_key_index(fn, time):
    if om is None or fn is None:
        return None
    try:
        target = om.MTime(float(time), time_unit())
        num_keys = fn.numKeys() if callable(fn.numKeys) else fn.numKeys
        for index in range(num_keys):
            if abs(fn.input(index).value - target.value) <= 0.000001:
                return index
    except Exception:
        return None
    return None


def set_anim_curve_key_value(curve, time, value, tolerance=0.000001):
    fn = anim_curve_fn(curve)
    index = anim_curve_key_index(fn, time)
    if index is None:
        return False
    try:
        value = float(value)
        if abs(float(fn.value(index)) - value) > tolerance:
            fn.setValue(index, value)
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
