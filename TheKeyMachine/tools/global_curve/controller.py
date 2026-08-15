"""Live Graph Editor Global Curves which reshape captured animation curves."""

from __future__ import annotations

import bisect
import math

from maya import cmds
from maya.api import OpenMaya as om  # type: ignore
from maya.api import OpenMayaAnim as oma  # type: ignore

from TheKeyMachine.core import runtime, settings
from TheKeyMachine.maya import maya_api
from TheKeyMachine.maya import selection as maya_selection
from TheKeyMachine.ui.widgets import util as wutil


ROOT_NAME = "TKM_GlobalCurves"
NODE_PREFIX = "TKM_GlobalCurve"
DRIVER_ATTR = "globalCurve"
TAG_ATTR = "tkmGlobalCurve"
CALLBACK_KEY = "global_curve:curve_edits"
SCENE_CALLBACK_KEY = "global_curve:scene_changes"
DISPLAY_ITEMS_CONNECTION = "TKM_GlobalCurveItems"
DISPLAY_CONNECTION = "TKM_GlobalCurveDisplay"

_TANGENT_MODE_SETTING = "global_curve_tangent_mode"
_AFFECT_TIME_SETTING = "global_curve_affect_time"
_SNAP_KEYS_SETTING = "global_curve_snap_keys"

_SESSIONS = []
_PROCESSING = False
_DISPLAY_SOURCE_CONNECTION = None
_DISPLAY_TOUCHED_CONNECTIONS = set()


def _setting(name, default):
    return settings.get_setting(name, default)


def _set_setting(name, value):
    settings.set_setting(name, value)
    return value


def tangent_mode_choices():
    return [
        {"label": "Don't Affect Tangents", "value": "none"},
        {"label": "Affect Only Fixed Tangents", "value": "fixed"},
        {"label": "Affect Any Tangents", "value": "any"},
    ]


def get_tangent_mode():
    value = str(_setting(_TANGENT_MODE_SETTING, "none"))
    return value if value in {"none", "fixed", "any"} else "none"


def set_tangent_mode(value="none", *_args):
    return _set_setting(_TANGENT_MODE_SETTING, value if value in {"none", "fixed", "any"} else "none")


def get_affect_time():
    return bool(_setting(_AFFECT_TIME_SETTING, False))


def set_affect_time(enabled=False, *_args):
    return _set_setting(_AFFECT_TIME_SETTING, bool(enabled))


def get_snap_keys():
    return bool(_setting(_SNAP_KEYS_SETTING, True))


def set_snap_keys(enabled=False, *_args):
    return _set_setting(_SNAP_KEYS_SETTING, bool(enabled))


def _unique(items):
    result = []
    for item in items or ():
        if item and item not in result:
            result.append(item)
    return result


def _is_anim_curve(node):
    try:
        return bool(cmds.objExists(node) and cmds.nodeType(node).startswith("animCurve"))
    except (RuntimeError, TypeError, ValueError, AttributeError):
        return False


def _is_global_curve(curve):
    try:
        destinations = cmds.listConnections(curve + ".output", source=False, destination=True, plugs=True) or []
        return any(cmds.objExists(plug.split(".", 1)[0] + "." + TAG_ATTR) for plug in destinations)
    except (RuntimeError, TypeError, ValueError, AttributeError, IndexError):
        return False


def _captured_curves():
    """Prefer explicitly selected curves, then outliner selection, then shown curves."""
    def eligible(items):
        return [curve for curve in _unique(items) if _is_anim_curve(curve) and not _is_global_curve(curve)]

    curves = eligible(maya_selection.get_graph_editor_explicitly_selected_curves())
    if not curves:
        curves = eligible(maya_selection.get_graph_editor_selected_curves())
    if not curves:
        try:
            curves = eligible(cmds.animCurveEditor(
                maya_selection.GRAPH_EDITOR, query=True, curvesShown=True
            ) or [])
        except (RuntimeError, TypeError, ValueError, AttributeError):
            curves = []
    return curves


def _query_array(curve, flag, count, default):
    try:
        values = cmds.keyTangent(curve, query=True, **{flag: True}) or []
    except (RuntimeError, TypeError, ValueError, AttributeError):
        values = []
    values = list(values)
    if len(values) < count:
        values.extend([default] * (count - len(values)))
    return values[:count]


def _curve_snapshot(curve):
    try:
        times = list(cmds.keyframe(curve, query=True, timeChange=True) or [])
        values = list(cmds.keyframe(curve, query=True, valueChange=True) or [])
    except (RuntimeError, TypeError, ValueError, AttributeError):
        return None
    count = min(len(times), len(values))
    if not count:
        return None
    times, values = times[:count], values[:count]
    try:
        weighted = bool(cmds.keyTangent(curve, query=True, weightedTangents=True))
    except (RuntimeError, TypeError, ValueError, AttributeError):
        weighted = False
    return {
        "curve": curve,
        "times": times,
        "values": values,
        "in_types": _query_array(curve, "inTangentType", count, "auto"),
        "out_types": _query_array(curve, "outTangentType", count, "auto"),
        "in_angles": _query_array(curve, "inAngle", count, 0.0),
        "out_angles": _query_array(curve, "outAngle", count, 0.0),
        "in_weights": _query_array(curve, "inWeight", count, 1.0),
        "out_weights": _query_array(curve, "outWeight", count, 1.0),
        "weighted": weighted,
    }


def _evaluate(curve, time):
    try:
        values = cmds.keyframe(curve, query=True, eval=True, time=(time, time), valueChange=True) or []
        return float(values[0]) if values else 0.0
    except (RuntimeError, TypeError, ValueError, AttributeError, IndexError):
        return 0.0


def _api_key_count(fn):
    value = fn.numKeys
    return int(value() if callable(value) else value)


def _api_curve_type(fn):
    value = fn.animCurveType
    return value() if callable(value) else value


def _guide_state(fn):
    """Read one guide in a single API pass, including editable tangents."""
    if fn is None:
        return None
    try:
        count = _api_key_count(fn)
        state = {
            "times": [], "values": [],
            "in_angles": [], "out_angles": [],
            "in_weights": [], "out_weights": [],
            "weighted": bool(fn.isWeighted),
        }
        unit = om.MTime.uiUnit()
        for index in range(count):
            state["times"].append(float(fn.input(index).asUnits(unit)))
            state["values"].append(float(fn.value(index)))
            in_angle, in_weight = fn.getTangentAngleWeight(index, True)
            out_angle, out_weight = fn.getTangentAngleWeight(index, False)
            state["in_angles"].append(float(in_angle.asDegrees()))
            state["out_angles"].append(float(out_angle.asDegrees()))
            state["in_weights"].append(float(in_weight))
            state["out_weights"].append(float(out_weight))
        return state if state["times"] else None
    except Exception:
        return None


def _guide_signature(state):
    if not state:
        return ()
    return tuple(
        state[key] if isinstance(state[key], bool) else tuple(state[key])
        for key in (
            "times", "values", "in_angles", "out_angles",
            "in_weights", "out_weights", "weighted",
        )
    )


def _evaluate_guide(fn, time, fallback=0.0):
    try:
        return float(fn.evaluate(om.MTime(float(time), om.MTime.uiUnit())))
    except Exception:
        return float(fallback)


def _source_api(source):
    fn = source.get("api_fn")
    if fn is None:
        fn = maya_api.anim_curve_fn(source.get("curve"))
        if fn is None:
            return None
        source["api_fn"] = fn
        try:
            source["api_type"] = _api_curve_type(fn)
        except Exception:
            source["api_type"] = None
    return fn


def _cache_bulk_source_state(source):
    """Cache native key/tangent arrays used by Maya's one-call bulk replace."""
    fn = _source_api(source)
    if fn is None or source.get("api_type") not in (
        oma.MFnAnimCurve.kAnimCurveTA,
        oma.MFnAnimCurve.kAnimCurveTL,
        oma.MFnAnimCurve.kAnimCurveTU,
    ):
        return False
    try:
        count = _api_key_count(fn)
        inputs = om.MTimeArray()
        in_types, out_types = om.MIntArray(), om.MIntArray()
        in_x, in_y = om.MDoubleArray(), om.MDoubleArray()
        out_x, out_y = om.MDoubleArray(), om.MDoubleArray()
        tangent_locks, weight_locks = om.MIntArray(), om.MIntArray()
        for index in range(count):
            inputs.append(fn.input(index))
            in_types.append(fn.inTangentType(index))
            out_types.append(fn.outTangentType(index))
            x, y = fn.getTangentXY(index, True)
            in_x.append(x)
            in_y.append(y)
            x, y = fn.getTangentXY(index, False)
            out_x.append(x)
            out_y.append(y)
            tangent_locks.append(fn.tangentsLocked(index))
            weight_locks.append(fn.weightsLocked(index))
        source["bulk_state"] = {
            "inputs": inputs,
            "in_types": in_types,
            "out_types": out_types,
            "in_x": in_x,
            "in_y": in_y,
            "out_x": out_x,
            "out_y": out_y,
            "tangent_locks": tangent_locks,
            "weight_locks": weight_locks,
        }
        return True
    except Exception:
        source.pop("bulk_state", None)
        return False


def _bulk_set_values(source, fn, values):
    """Replace every value with one native edit and one Graph Editor dirty."""
    state = source.get("bulk_state")
    if not state or len(state["inputs"]) != len(values):
        return False
    try:
        output_values = om.MDoubleArray(
            [_api_output_value(source, value) for value in values]
        )
        fn.addKeysWithTangents(
            state["inputs"],
            output_values,
            tangentInTypeArray=state["in_types"],
            tangentOutTypeArray=state["out_types"],
            tangentInXArray=state["in_x"],
            tangentInYArray=state["in_y"],
            tangentOutXArray=state["out_x"],
            tangentOutYArray=state["out_y"],
            tangentsLockedArray=state["tangent_locks"],
            weightsLockedArray=state["weight_locks"],
            convertUnits=False,
            keepExistingKeys=False,
        )
        return True
    except Exception:
        return False


def _api_output_value(source, value):
    """Convert command-layer key values to MFnAnimCurve internal units."""
    curve_type = source.get("api_type")
    value = float(value)
    if curve_type in (oma.MFnAnimCurve.kAnimCurveTA, oma.MFnAnimCurve.kAnimCurveUA):
        return om.MAngle(value, om.MAngle.uiUnit()).asRadians()
    if curve_type in (oma.MFnAnimCurve.kAnimCurveTL, oma.MFnAnimCurve.kAnimCurveUL):
        return om.MDistance(value, om.MDistance.uiUnit()).asCentimeters()
    if curve_type in (oma.MFnAnimCurve.kAnimCurveTT, oma.MFnAnimCurve.kAnimCurveUT):
        return om.MTime(value, om.MTime.uiUnit()).asUnits(om.MTime.kSeconds)
    return value


def _api_input(source, value):
    curve_type = source.get("api_type")
    if curve_type in (
        oma.MFnAnimCurve.kAnimCurveTA,
        oma.MFnAnimCurve.kAnimCurveTL,
        oma.MFnAnimCurve.kAnimCurveTT,
        oma.MFnAnimCurve.kAnimCurveTU,
    ):
        return om.MTime(float(value), om.MTime.uiUnit())
    return float(value)


def _point_distance(point, start, end):
    x, y = point
    x1, y1 = start
    x2, y2 = end
    dx, dy = x2 - x1, y2 - y1
    if abs(dx) + abs(dy) < 1e-12:
        return math.hypot(x - x1, y - y1)
    return abs(dy * x - dx * y + x2 * y1 - y2 * x1) / math.hypot(dx, dy)


def _simplify_points(times, values):
    """Ramer-Douglas-Peucker in normalized time/value space."""
    if len(times) <= 3:
        return list(zip(times, values))
    time_span = max(times) - min(times) or 1.0
    value_span = max(values) - min(values) or 1.0
    points = [((time - min(times)) / time_span, (value - min(values)) / value_span) for time, value in zip(times, values)]

    def reduce(first, last, keep):
        distance, index = 0.0, None
        for candidate in range(first + 1, last):
            current = _point_distance(points[candidate], points[first], points[last])
            if current > distance:
                distance, index = current, candidate
        if index is not None and distance > 0.035:
            keep.add(index)
            reduce(first, index, keep)
            reduce(index, last, keep)

    kept = {0, len(points) - 1}
    reduce(0, len(points) - 1, kept)
    return [(times[index], values[index]) for index in sorted(kept)]


def _guide_points(sources):
    if len(sources) == 1:
        return _simplify_points(sources[0]["times"], sources[0]["values"])
    times = sorted({time for source in sources for time in source["times"]})
    return [(time, sum(_evaluate(source["curve"], time) for source in sources) / len(sources)) for time in times]


def _next_holder_name():
    if not cmds.objExists(NODE_PREFIX):
        return NODE_PREFIX
    index = 2
    while cmds.objExists("{}{}".format(NODE_PREFIX, index)):
        index += 1
    return "{}{}".format(NODE_PREFIX, index)


def _set_do_not_write(node):
    """Keep the session-only guide nodes out of saved Maya scenes."""
    try:
        from maya.api import OpenMaya as om

        mobject = maya_api.mobject_from_node(node)
        if mobject is not None:
            om.MFnDependencyNode(mobject).setDoNotWrite(True)
    except (ImportError, RuntimeError, TypeError, ValueError, AttributeError):
        pass


def _ensure_root():
    if cmds.objExists(ROOT_NAME):
        return ROOT_NAME
    root = cmds.createNode("transform", name=ROOT_NAME, skipSelect=True)
    _set_do_not_write(root)
    try:
        cmds.setAttr(root + ".hiddenInOutliner", True)
    except (RuntimeError, TypeError, ValueError, AttributeError):
        pass
    return root


def _make_guide(points):
    holder = cmds.createNode(
        "transform", name=_next_holder_name(), parent=_ensure_root(), skipSelect=True
    )
    cmds.addAttr(holder, longName=DRIVER_ATTR, attributeType="double", keyable=True)
    cmds.addAttr(holder, longName=TAG_ATTR, attributeType="bool", defaultValue=True)
    cmds.setAttr(holder + "." + TAG_ATTR, lock=True)
    _set_do_not_write(holder)
    try:
        cmds.setAttr(holder + ".hiddenInOutliner", True)
    except (RuntimeError, TypeError, ValueError, AttributeError):
        pass
    for time, value in points:
        cmds.setKeyframe(holder, attribute=DRIVER_ATTR, time=(time,), value=value)
    curve = (cmds.listConnections(holder + "." + DRIVER_ATTR, source=True, destination=False, type="animCurve") or [None])[0]
    if curve:
        try:
            cmds.keyTangent(curve, edit=True, inTangentType="spline", outTangentType="spline")
        except (RuntimeError, TypeError, ValueError, AttributeError):
            pass
        _set_do_not_write(curve)
    return holder, curve


def _publish_state():
    state = has_global_curves()
    try:
        runtime.get_runtime_manager().set_control_state("global_curve", state)
    except (RuntimeError, TypeError, ValueError, AttributeError):
        pass
    return state


def _install_callback():
    manager = runtime.get_runtime_manager()
    manager.disconnect_callbacks(CALLBACK_KEY)
    manager.disconnect_callbacks(SCENE_CALLBACK_KEY)
    if _SESSIONS:
        manager.add_anim_curve_edited_callback(_on_curve_edited, key=CALLBACK_KEY)
        manager.connect_signal(manager.scene_new, remove_all, key=SCENE_CALLBACK_KEY, unique=False)
        manager.connect_signal(manager.scene_opened, remove_all, key=SCENE_CALLBACK_KEY, unique=False)
        manager.connect_signal(manager.graph_editor_opened, _refresh_graph_display, key=SCENE_CALLBACK_KEY, unique=False)
        manager.connect_signal(manager.selection_changed, _refresh_graph_display, key=SCENE_CALLBACK_KEY, unique=False)


def _ui_exists(name):
    try:
        return bool(cmds.selectionConnection(name, exists=True))
    except (RuntimeError, TypeError, ValueError, AttributeError):
        return False


def _delete_display_connection(name):
    if not _ui_exists(name):
        return
    try:
        cmds.deleteUI(name)
    except (RuntimeError, TypeError, ValueError, AttributeError):
        pass


def _global_display_plugs():
    plugs = []
    for session in _SESSIONS:
        plug = "{}.{}".format(session["holder"], DRIVER_ATTR)
        if cmds.objExists(plug):
            plugs.append(plug)
    return plugs


def _editor_main_connection():
    try:
        if cmds.animCurveEditor(maya_selection.GRAPH_EDITOR, exists=True):
            return cmds.animCurveEditor(
                maya_selection.GRAPH_EDITOR, query=True, mainListConnection=True
            )
    except (RuntimeError, TypeError, ValueError, AttributeError):
        pass
    return None


def _repair_obsolete_display_connection(current=None):
    """Recover editors left attached to a proxy used by older builds."""
    if current is None:
        current = _editor_main_connection()
    try:
        editor_exists = bool(
            cmds.animCurveEditor(maya_selection.GRAPH_EDITOR, exists=True)
        )
    except (RuntimeError, TypeError, ValueError, AttributeError):
        editor_exists = False
    if editor_exists and (not current or current == DISPLAY_CONNECTION):
        try:
            cmds.animCurveEditor(
                maya_selection.GRAPH_EDITOR,
                edit=True,
                forceMainConnection=maya_selection.GRAPH_EDITOR_OUTLINER,
            )
            cmds.animCurveEditor(
                maya_selection.GRAPH_EDITOR,
                query=True,
                curvesShownForceUpdate=True,
            )
            current = maya_selection.GRAPH_EDITOR_OUTLINER
        except (RuntimeError, TypeError, ValueError, AttributeError):
            return current

    # Never delete a UI connection while the editor is still using it.
    if current != DISPLAY_CONNECTION:
        _delete_display_connection(DISPLAY_CONNECTION)
        _delete_display_connection(DISPLAY_ITEMS_CONNECTION)
    return current


def _sync_display_items(*_args):
    global _DISPLAY_SOURCE_CONNECTION
    if not _SESSIONS:
        return False

    current = _repair_obsolete_display_connection(_editor_main_connection())
    if current and current != DISPLAY_CONNECTION:
        _DISPLAY_SOURCE_CONNECTION = current
    source = _DISPLAY_SOURCE_CONNECTION or maya_selection.GRAPH_EDITOR_OUTLINER

    try:
        items = list(cmds.selectionConnection(source, query=True, object=True) or [])
        changed = False
        for plug in _global_display_plugs():
            if plug not in items:
                cmds.selectionConnection(source, edit=True, select=plug)
                items.append(plug)
                changed = True
        _DISPLAY_TOUCHED_CONNECTIONS.add(source)
        if changed:
            cmds.animCurveEditor(
                maya_selection.GRAPH_EDITOR,
                query=True,
                curvesShownForceUpdate=True,
            )
        return True
    except (RuntimeError, TypeError, ValueError, AttributeError):
        return False


def _refresh_graph_display(*_args):
    """Append Global Curve plugs to Maya's existing Graph Editor input."""
    global _DISPLAY_SOURCE_CONNECTION
    if not _SESSIONS:
        return False
    current = _editor_main_connection()
    current = _repair_obsolete_display_connection(current)
    if not current:
        return False
    if current and current != DISPLAY_CONNECTION:
        _DISPLAY_SOURCE_CONNECTION = current
    if _sync_display_items():
        return True
    return False


def _remove_graph_display():
    """Remove only Global Curve plugs, preserving the editor's native input."""
    global _DISPLAY_SOURCE_CONNECTION, _DISPLAY_TOUCHED_CONNECTIONS
    current = _repair_obsolete_display_connection(_editor_main_connection())
    sources = set(_DISPLAY_TOUCHED_CONNECTIONS)
    if _DISPLAY_SOURCE_CONNECTION:
        sources.add(_DISPLAY_SOURCE_CONNECTION)
    if current and current != DISPLAY_CONNECTION:
        sources.add(current)
    plugs = _global_display_plugs()

    for source in sources:
        for plug in plugs:
            try:
                cmds.selectionConnection(source, edit=True, deselect=plug)
            except (RuntimeError, TypeError, ValueError, AttributeError):
                pass
    try:
        if cmds.animCurveEditor(maya_selection.GRAPH_EDITOR, exists=True):
            cmds.animCurveEditor(
                maya_selection.GRAPH_EDITOR,
                query=True,
                curvesShownForceUpdate=True,
            )
    except (RuntimeError, TypeError, ValueError, AttributeError):
        pass
    _delete_display_connection(DISPLAY_CONNECTION)
    _delete_display_connection(DISPLAY_ITEMS_CONNECTION)
    _DISPLAY_SOURCE_CONNECTION = None
    _DISPLAY_TOUCHED_CONNECTIONS = set()


def _create(curves=None):
    curves = curves or _captured_curves()
    sources = [source for source in (_curve_snapshot(curve) for curve in curves) if source]
    if not sources:
        return wutil.make_inViewMessage("Select curves or show animated curves in the Graph Editor")
    points = _guide_points(sources)
    if not points:
        return wutil.make_inViewMessage("No keys found on the captured curves")
    holder, curve = _make_guide(points)
    if not curve:
        if cmds.objExists(holder):
            cmds.delete(holder)
        return wutil.make_inViewMessage("Could not create the Global Curve")
    guide_fn = maya_api.anim_curve_fn(curve)
    guide = _guide_state(guide_fn)
    if not guide:
        if cmds.objExists(holder):
            cmds.delete(holder)
        return wutil.make_inViewMessage("Could not read the Global Curve")
    for source in sources:
        _cache_bulk_source_state(source)
    session = {
        "holder": holder,
        "curve": curve,
        "guide_fn": guide_fn,
        "sources": sources,
        "guide": guide,
        "baseline_values": {
            source["curve"]: [
                _evaluate_guide(guide_fn, time) for time in source["times"]
            ]
            for source in sources
        },
    }
    session["signature"] = _guide_signature(guide)
    _SESSIONS.append(session)
    _install_callback()
    _refresh_graph_display()
    # Maya rebuilds the Graph Editor connection after the toolbar command
    # returns. Reattach once after that native rebuild; no polling is needed.
    try:
        cmds.evalDeferred(_refresh_graph_display, lowestPriority=True)
    except (RuntimeError, TypeError, ValueError, AttributeError):
        pass
    _publish_state()
    return holder


def create_additional(*_args):
    return _create()


def has_global_curves():
    _prune_sessions()
    if _SESSIONS:
        return True
    try:
        return bool(cmds.ls("*." + TAG_ATTR, objectsOnly=True) or [])
    except (RuntimeError, TypeError, ValueError, AttributeError):
        return False


def set_enabled(enabled=False, *_args):
    if bool(enabled):
        return _create() if not has_global_curves() else True
    return remove_all()


def _remove_session(session):
    if session in _SESSIONS:
        _SESSIONS.remove(session)
    holder = session.get("holder")
    if holder and cmds.objExists(holder):
        cmds.delete(holder)


def remove_all(*_args):
    global _PROCESSING
    _PROCESSING = True
    try:
        runtime.get_runtime_manager().disconnect_callbacks(CALLBACK_KEY)
        runtime.get_runtime_manager().disconnect_callbacks(SCENE_CALLBACK_KEY)
        _remove_graph_display()
        for session in list(_SESSIONS):
            _remove_session(session)
        try:
            tagged = cmds.ls("*." + TAG_ATTR, objectsOnly=True) or []
        except (RuntimeError, TypeError, ValueError, AttributeError):
            tagged = []
        if tagged:
            cmds.delete(_unique(tagged))
        if cmds.objExists(ROOT_NAME):
            cmds.delete(ROOT_NAME)
    finally:
        _SESSIONS[:] = []
        _PROCESSING = False
    _publish_state()
    return False


def recapture_active(*_args):
    _prune_sessions()
    if not _SESSIONS:
        return _create()
    session = _SESSIONS[-1]
    requested = _captured_curves()
    old_curves = [source["curve"] for source in session["sources"] if cmds.objExists(source["curve"])]
    curves = requested or old_curves
    _remove_session(session)
    _install_callback()
    return _create(curves=curves)


def _prune_sessions():
    removed = False
    for session in list(_SESSIONS):
        if not cmds.objExists(session.get("holder", "")) or not cmds.objExists(session.get("curve", "")):
            _SESSIONS.remove(session)
            removed = True
    if removed:
        _install_callback()


def _mapped_time(time, baseline, current):
    if not baseline or not current or len(baseline) != len(current):
        return time
    if len(baseline) == 1:
        return time + current[0] - baseline[0]
    if time <= baseline[0]:
        return time + current[0] - baseline[0]
    if time >= baseline[-1]:
        return time + current[-1] - baseline[-1]
    index = max(0, min(len(baseline) - 2, bisect.bisect_right(baseline, time) - 1))
    left, right = baseline[index], baseline[index + 1]
    ratio = (time - left) / (right - left or 1.0)
    return current[index] + ratio * (current[index + 1] - current[index])


def _nearest_guide_index(time, guide_times):
    index = bisect.bisect_left(guide_times, time)
    if index <= 0:
        return 0
    if index >= len(guide_times):
        return len(guide_times) - 1
    before = index - 1
    return before if abs(guide_times[before] - time) <= abs(guide_times[index] - time) else index


def _restore_tangents(curve, source, guide, current_guide, times, tangent_mode):
    if tangent_mode == "none":
        return
    try:
        cmds.keyTangent(curve, edit=True, weightedTangents=source["weighted"])
    except (RuntimeError, TypeError, ValueError, AttributeError):
        pass
    for index, time in enumerate(times):
        in_type, out_type = source["in_types"][index], source["out_types"][index]
        in_angle, out_angle = source["in_angles"][index], source["out_angles"][index]
        in_weight, out_weight = source["in_weights"][index], source["out_weights"][index]
        apply_in = tangent_mode == "any" or (tangent_mode == "fixed" and in_type == "fixed")
        apply_out = tangent_mode == "any" or (tangent_mode == "fixed" and out_type == "fixed")
        if tangent_mode != "none" and guide["times"] and current_guide["times"]:
            guide_index = _nearest_guide_index(source["times"][index], guide["times"])
            current_index = _nearest_guide_index(times[index], current_guide["times"])
            if apply_in:
                in_angle += current_guide["in_angles"][current_index] - guide["in_angles"][guide_index]
                in_weight = max(0.0001, in_weight + current_guide["in_weights"][current_index] - guide["in_weights"][guide_index])
                if tangent_mode == "any":
                    in_type = "fixed"
            if apply_out:
                out_angle += current_guide["out_angles"][current_index] - guide["out_angles"][guide_index]
                out_weight = max(0.0001, out_weight + current_guide["out_weights"][current_index] - guide["out_weights"][guide_index])
                if tangent_mode == "any":
                    out_type = "fixed"
        try:
            cmds.keyTangent(curve, edit=True, index=(index, index), inTangentType=in_type, outTangentType=out_type)
            cmds.keyTangent(
                curve, edit=True, index=(index, index),
                inAngle=in_angle, outAngle=out_angle,
                inWeight=in_weight, outWeight=out_weight,
            )
        except (RuntimeError, TypeError, ValueError, AttributeError):
            pass


def _strict_snapped_times(times):
    """Snap an ordered key set without collapsing two keys onto one frame."""
    result = []
    for time in times:
        snapped = float(round(time))
        if result and snapped <= result[-1]:
            snapped = result[-1] + 1.0
        result.append(snapped)
    return result


def _retime_curve(source, fn, times, values):
    """Replace time/value arrays natively, with rollback on partial failure."""
    try:
        count = _api_key_count(fn)
        current_times = list(source["times"])
    except Exception:
        return False
    if count != len(times) or len(current_times) != len(times):
        return False
    state = source.get("bulk_state")
    if state is not None:
        change = oma.MAnimCurveChange()
        try:
            inputs = om.MTimeArray(
                [om.MTime(float(time), om.MTime.uiUnit()) for time in times]
            )
            output_values = om.MDoubleArray(
                [_api_output_value(source, value) for value in values]
            )
            for index in reversed(range(count)):
                fn.remove(index, change=change)
            fn.addKeysWithTangents(
                inputs,
                output_values,
                tangentInTypeArray=state["in_types"],
                tangentOutTypeArray=state["out_types"],
                tangentInXArray=state["in_x"],
                tangentInYArray=state["in_y"],
                tangentOutXArray=state["out_x"],
                tangentOutYArray=state["out_y"],
                tangentsLockedArray=state["tangent_locks"],
                weightsLockedArray=state["weight_locks"],
                convertUnits=False,
                keepExistingKeys=False,
                change=change,
            )
            state["inputs"] = inputs
            return True
        except Exception:
            try:
                change.undoIt()
            except Exception:
                pass
            return False

    temporary_start = max(current_times + list(times)) + 1000.0
    change = oma.MAnimCurveChange()
    try:
        # Collision-free temporary positions keep every key index stable.
        for index in reversed(range(count)):
            fn.setInput(index, _api_input(source, temporary_start + index), change=change)
        for index, (time, value) in enumerate(zip(times, values)):
            fn.setInput(index, _api_input(source, time), change=change)
            fn.setValue(index, _api_output_value(source, value), change=change)
        return True
    except Exception:
        try:
            change.undoIt()
        except Exception:
            pass
        return False


def _apply_session(
    session, current_guide, affect_time, snap, tangent_mode,
    tangent_jobs,
):
    guide = session["guide"]
    guide_fn = session.get("guide_fn")
    value_cache = {}
    for source in session["sources"]:
        curve = source["curve"]
        fn = _source_api(source)
        if fn is None:
            continue
        new_times, new_values = [], []
        baseline_values = session["baseline_values"][curve]
        for index, original_time in enumerate(source["times"]):
            new_time = _mapped_time(original_time, guide["times"], current_guide["times"]) if affect_time else original_time
            cache_key = round(float(new_time), 9)
            if cache_key not in value_cache:
                guide_value = _evaluate_guide(guide_fn, new_time)
                value_cache[cache_key] = guide_value
            else:
                guide_value = value_cache[cache_key]
            delta = guide_value - baseline_values[index]
            new_times.append(new_time)
            new_values.append(source["values"][index] + delta)
        if affect_time and snap:
            new_times = _strict_snapped_times(new_times)
        try:
            if affect_time:
                if not _retime_curve(source, fn, new_times, new_values):
                    continue
            else:
                if _api_key_count(fn) != len(new_values):
                    continue
                if tangent_mode == "none" and _bulk_set_values(
                    source, fn, new_values
                ):
                    pass
                else:
                    for index, value in enumerate(new_values):
                        fn.setValue(index, _api_output_value(source, value))
            if tangent_mode != "none":
                tangent_jobs.append(
                    (curve, source, guide, current_guide, new_times, tangent_mode)
                )
        except Exception:
            continue


def _on_curve_edited(*_args):
    """Apply guide edits inside Maya's callback, without Qt deferral."""
    if _PROCESSING:
        return
    edited = set()
    try:
        curves = _args[0]
        for index in range(len(curves)):
            edited.add(om.MFnDependencyNode(curves[index]).name())
    except Exception:
        pass
    guides = {session.get("curve") for session in _SESSIONS}
    pending = edited.intersection(guides) if edited else guides
    if not pending:
        return
    _process_curve_edits(pending)


def _process_curve_edits(pending):
    global _PROCESSING
    if _PROCESSING:
        return
    _prune_sessions()
    changed = []
    for session in _SESSIONS:
        if pending and session.get("curve") not in pending:
            continue
        current_guide = _guide_state(session.get("guide_fn"))
        signature = _guide_signature(current_guide)
        if signature and signature != session.get("signature"):
            changed.append((session, signature, current_guide))
    if not changed:
        return
    affect_time = get_affect_time()
    snap = get_snap_keys()
    tangent_mode = get_tangent_mode()
    _PROCESSING = True
    tangent_jobs = []
    affected_objects = []
    for session, _signature, _current_guide in changed:
        for source in session["sources"]:
            fn = _source_api(source)
            if fn is not None:
                try:
                    affected_objects.append(fn.object())
                except Exception:
                    pass
    try:
        with runtime.get_runtime_manager().coalesce_anim_curve_callbacks(
            affected_objects
        ):
            for session, signature, current_guide in changed:
                _apply_session(
                    session, current_guide, affect_time, snap, tangent_mode,
                    tangent_jobs,
                )
            for job in tangent_jobs:
                _restore_tangents(*job)
        for session, signature, _current_guide in changed:
            session["signature"] = signature
    except Exception:
        pass
    finally:
        _PROCESSING = False


def cleanup():
    """Runtime shutdown hook: delete transient guides and detach every callback."""
    return remove_all()
