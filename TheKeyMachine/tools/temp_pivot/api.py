import json
import os

from maya import cmds

try:
    from maya.api import OpenMaya as om
except ImportError:
    om = None

import TheKeyMachine.core.runtimeManager as runtime
import TheKeyMachine.mods.generalMod as general
import TheKeyMachine.mods.selectionMod as selectionMod
from TheKeyMachine.tools import common as toolCommon
import TheKeyMachine.widgets.util as wutil


TEMP_PIVOT_NODE = "tkm_temp_pivot"
RUNTIME_KEY = "temp_pivot"

PIVOT_ATTRS = (
    "rotatePivot",
    "rotatePivotTranslate",
    "scalePivot",
    "scalePivotTranslate",
)

DRIVER_ATTRS = {
    "translate",
    "translateX",
    "translateY",
    "translateZ",
    "rotate",
    "rotateX",
    "rotateY",
    "rotateZ",
}

PIVOT_EDIT_ATTR_PREFIXES = (
    "rotatePivot",
    "rotatePivotTranslate",
    "scalePivot",
    "scalePivotTranslate",
)

_session = {
    "active": False,
    "selection": [],
    "signature": "",
    "relative_matrices": {},
    "suppress": False,
}


def _data_file():
    return general.get_temp_pivot_data_file()


def _load_data():
    path = _data_file()
    if not os.path.exists(path):
        return {"sessions": {}}
    try:
        with open(path, "r") as stream:
            data = json.load(stream)
    except (OSError, ValueError, TypeError):
        return {"sessions": {}}
    if not isinstance(data, dict):
        return {"sessions": {}}
    data.setdefault("sessions", {})
    return data


def _save_data(data):
    folder = general.get_temp_pivot_data_folder()
    os.makedirs(folder, exist_ok=True)
    with open(_data_file(), "w") as stream:
        json.dump(data, stream, indent=2)


def _selection_signature(selection):
    return "|".join(selection or [])


def _existing_nodes(nodes):
    return [node for node in nodes or [] if cmds.objExists(node)]


def _matrix(node):
    return cmds.xform(node, query=True, matrix=True, worldSpace=True)


def _world_rotate_pivot(node):
    try:
        return cmds.xform(node, query=True, rotatePivot=True, worldSpace=True)
    except (RuntimeError, ValueError, TypeError, AttributeError, KeyError, IndexError):
        matrix_values = _matrix(node)
        return [matrix_values[12], matrix_values[13], matrix_values[14]]


def _mmatrix(matrix_values):
    if om is None:
        raise RuntimeError("maya.api.OpenMaya is required for Temp Pivot")
    return om.MMatrix(matrix_values)


def _matrix_list(matrix_value):
    try:
        return [float(value) for value in matrix_value]
    except TypeError:
        return [matrix_value.getElement(row, col) for row in range(4) for col in range(4)]


def _set_matrix_translation(matrix_value, position):
    matrix_value = _mmatrix(_matrix_list(matrix_value))
    for index, value in enumerate(position or [0.0, 0.0, 0.0]):
        matrix_value.setElement(3, index, float(value))
    return matrix_value


def _object_pivot_space_matrix(node):
    return _set_matrix_translation(_mmatrix(_matrix(node)), _world_rotate_pivot(node))


def _ensure_root():
    if not cmds.objExists("TheKeyMachine"):
        general.create_TheKeyMachine_node()
    return "TheKeyMachine"


def _ensure_pivot_node():
    if cmds.objExists(TEMP_PIVOT_NODE):
        pivot = TEMP_PIVOT_NODE
    else:
        pivot = cmds.createNode("transform", name=TEMP_PIVOT_NODE)

    try:
        parent = cmds.listRelatives(pivot, parent=True, fullPath=False) or []
        if not parent or parent[0] != "TheKeyMachine":
            cmds.parent(pivot, _ensure_root())
    except (RuntimeError, ValueError, TypeError, AttributeError, KeyError, IndexError):
        pass

    return pivot


def _get_vector_attr(node, attr):
    try:
        value = cmds.getAttr("{}.{}".format(node, attr))[0]
    except (RuntimeError, ValueError, TypeError, AttributeError, KeyError, IndexError):
        return [0.0, 0.0, 0.0]
    return [float(value[0]), float(value[1]), float(value[2])]


def _set_vector_attr(node, attr, value):
    if not value or len(value) != 3:
        value = [0.0, 0.0, 0.0]
    try:
        cmds.setAttr("{}.{}".format(node, attr), float(value[0]), float(value[1]), float(value[2]), type="double3")
    except (RuntimeError, ValueError, TypeError, AttributeError, KeyError, IndexError):
        pass


def _emit_temp_pivot_state_changed():
    try:
        runtime.get_runtime_manager().callback_fired.emit(RUNTIME_KEY)
    except (RuntimeError, ValueError, TypeError, AttributeError, KeyError, IndexError):
        pass


def _capture_pivot_attrs(pivot):
    return {attr: _get_vector_attr(pivot, attr) for attr in PIVOT_ATTRS}


def _apply_pivot_attrs(pivot, attrs=None):
    attrs = attrs or {}
    for attr in PIVOT_ATTRS:
        _set_vector_attr(pivot, attr, attrs.get(attr, [0.0, 0.0, 0.0]))


def _restore_transform_locks(node, values):
    for attr, value in values.items():
        try:
            cmds.setAttr("{}.{}".format(node, attr), value)
        except (RuntimeError, ValueError, TypeError, AttributeError, KeyError, IndexError):
            pass


def _clear_pivot_transform(pivot):
    attrs = {
        "translateX": 0.0,
        "translateY": 0.0,
        "translateZ": 0.0,
        "rotateX": 0.0,
        "rotateY": 0.0,
        "rotateZ": 0.0,
        "scaleX": 1.0,
        "scaleY": 1.0,
        "scaleZ": 1.0,
    }
    _restore_transform_locks(pivot, attrs)
    _apply_pivot_attrs(pivot)


def _place_pivot_at_last_selected(pivot, selection):
    cmds.xform(pivot, matrix=_matrix_list(_object_pivot_space_matrix(selection[-1])), worldSpace=True)


def _selection_transform_center(selection):
    positions = []
    for node in selection:
        matrix_values = _matrix(node)
        positions.append([matrix_values[12], matrix_values[13], matrix_values[14]])
    count = float(len(positions) or 1)
    return [
        sum(position[index] for position in positions) / count
        for index in range(3)
    ]


def _place_pivot_at_selection_center(pivot, selection):
    matrix_value = _set_matrix_translation(_object_pivot_space_matrix(selection[-1]), _selection_transform_center(selection))
    cmds.xform(pivot, matrix=_matrix_list(matrix_value), worldSpace=True)


def _driver_matrix(pivot):
    matrix_value = _mmatrix(_matrix(pivot))
    return _set_matrix_translation(matrix_value, _world_rotate_pivot(pivot))


def _saved_offset_matrix(pivot, selection):
    if not selection:
        return None
    reference_matrix = _object_pivot_space_matrix(selection[-1])
    return _matrix_list(_driver_matrix(pivot) * reference_matrix.inverse())


def _apply_saved_offset(pivot, selection, saved_entry):
    offset_values = (saved_entry or {}).get("pivot_offset_matrix")
    if offset_values:
        reference_matrix = _object_pivot_space_matrix(selection[-1])
        cmds.xform(pivot, matrix=_matrix_list(_mmatrix(offset_values) * reference_matrix), worldSpace=True)
        _apply_pivot_attrs(pivot)
        return True

    pivot_attrs = (saved_entry or {}).get("pivot_attrs")
    if pivot_attrs:
        _place_pivot_at_last_selected(pivot, selection)
        _apply_pivot_attrs(pivot, pivot_attrs)
        return True

    return False


def _relative_matrices(pivot, selection):
    pivot_matrix = _driver_matrix(pivot)
    pivot_inverse = pivot_matrix.inverse()
    result = {}
    for node in selection:
        if not cmds.objExists(node):
            continue
        result[node] = _matrix_list(_mmatrix(_matrix(node)) * pivot_inverse)
    return result


def _apply_relative_matrices():
    if not _session["active"] or _session["suppress"] or not cmds.objExists(TEMP_PIVOT_NODE):
        return

    pivot_matrix = _driver_matrix(TEMP_PIVOT_NODE)
    for node, relative_values in list(_session["relative_matrices"].items()):
        if not cmds.objExists(node):
            continue
        new_matrix = _mmatrix(relative_values) * pivot_matrix
        try:
            cmds.xform(node, matrix=_matrix_list(new_matrix), worldSpace=True)
        except (RuntimeError, ValueError, TypeError, AttributeError, KeyError, IndexError):
            pass


def _attr_from_plug(plug):
    try:
        return plug.name().split(".", 1)[-1]
    except (RuntimeError, ValueError, TypeError, AttributeError, KeyError, IndexError):
        return ""


def _is_driver_attr(attr):
    return attr in DRIVER_ATTRS


def _is_pivot_edit_attr(attr):
    return any(attr.startswith(prefix) for prefix in PIVOT_EDIT_ATTR_PREFIXES)


def _refresh_relative_matrices():
    if not _session["active"] or not cmds.objExists(TEMP_PIVOT_NODE):
        return
    selection = _existing_nodes(_session.get("selection") or [])
    if not selection:
        return
    _session["relative_matrices"] = _relative_matrices(TEMP_PIVOT_NODE, selection)


def _on_pivot_attribute_changed(msg, plug, other_plug, client_data):
    if om is None or not (msg & om.MNodeMessage.kAttributeSet):
        return
    attr = _attr_from_plug(plug)
    if _is_driver_attr(attr):
        _apply_relative_matrices()
    elif _is_pivot_edit_attr(attr):
        _refresh_relative_matrices()


def _save_current_session():
    signature = _session.get("signature")
    if not signature or not cmds.objExists(TEMP_PIVOT_NODE):
        return

    data = _load_data()
    selection = list(_session.get("selection") or [])
    data.setdefault("sessions", {})[signature] = {
        "selection": selection,
        "pivot_offset_matrix": _saved_offset_matrix(TEMP_PIVOT_NODE, selection),
        "pivot_attrs": _capture_pivot_attrs(TEMP_PIVOT_NODE),
    }
    _save_data(data)


def _restore_original_selection():
    selection = _existing_nodes(_session.get("selection") or [])
    if selection:
        cmds.select(selection, replace=True)
    else:
        cmds.select(clear=True)


def _end_session(restore_selection=True):
    _save_current_session()
    try:
        runtime.get_runtime_manager().disconnect_callbacks(RUNTIME_KEY)
    except (RuntimeError, ValueError, TypeError, AttributeError, KeyError, IndexError):
        pass

    selection = list(_session.get("selection") or [])
    _session.update(
        {
            "active": False,
            "selection": selection,
            "signature": "",
            "relative_matrices": {},
            "suppress": True,
        }
    )
    try:
        if restore_selection:
            _restore_original_selection()
    finally:
        _session["suppress"] = False
        _emit_temp_pivot_state_changed()


def is_temp_pivot_active():
    return bool(_session.get("active") and cmds.objExists(TEMP_PIVOT_NODE))


def end_temp_pivot(*args):
    if is_temp_pivot_active():
        _end_session(restore_selection=True)


def _on_selection_changed(*args):
    if _session["suppress"] or not _session["active"]:
        return

    current_selection = selectionMod.get_selected_objects(long=False, ordered=True)
    if current_selection == [TEMP_PIVOT_NODE]:
        return

    _end_session(restore_selection=True)


def _connect_callbacks(pivot):
    manager = runtime.get_runtime_manager()
    manager.disconnect_callbacks(RUNTIME_KEY)
    attr_cb = manager.add_node_attribute_changed_callback(pivot, _on_pivot_attribute_changed, key=RUNTIME_KEY)
    selection_cb = manager.add_maya_event_callback("SelectionChanged", _on_selection_changed, key=RUNTIME_KEY)
    if attr_cb is None or selection_cb is None:
        manager.disconnect_callbacks(RUNTIME_KEY)
        raise RuntimeError("Could not register Temp Pivot callbacks")


def _enter_pivot_edit_mode(pivot):
    cmds.select(pivot, replace=True)
    if cmds.currentCtx() == "selectSuperContext":
        cmds.setToolTo("moveSuperContext")
    try:
        cmds.ctxEditMode()
    except (RuntimeError, ValueError, TypeError, AttributeError, KeyError, IndexError):
        pass


def _select_pivot_for_transform(pivot):
    cmds.select(pivot, replace=True)
    if cmds.currentCtx() == "selectSuperContext":
        cmds.setToolTo("moveSuperContext")


def edit_temp_pivot(*args):
    if is_temp_pivot_active():
        _enter_pivot_edit_mode(TEMP_PIVOT_NODE)
        return
    if cmds.currentCtx() == "selectSuperContext":
        cmds.setToolTo("moveSuperContext")
    try:
        cmds.ctxEditMode()
    except (RuntimeError, ValueError, TypeError, AttributeError, KeyError, IndexError):
        pass


def create_temp_pivot(use_saved_position=False, centered=False, *args):
    if is_temp_pivot_active():
        _end_session(restore_selection=True)

    selection = selectionMod.get_selected_objects(long=True, ordered=True)
    selection = [node for node in selection if cmds.objExists(node) and node != TEMP_PIVOT_NODE]
    if not selection:
        return wutil.make_inViewMessage("Select at least one object")

    open_chunk = False
    try:
        open_chunk = toolCommon.open_undo_chunk()

        signature = _selection_signature(selection)
        saved_entry = _load_data().get("sessions", {}).get(signature)

        pivot = _ensure_pivot_node()
        _session["suppress"] = True
        _clear_pivot_transform(pivot)
        if centered:
            _place_pivot_at_selection_center(pivot, selection)
        elif not _apply_saved_offset(pivot, selection, saved_entry):
            _place_pivot_at_last_selected(pivot, selection)
        _session["suppress"] = False

        _session.update(
            {
                "active": True,
                "selection": list(selection),
                "signature": signature,
                "relative_matrices": _relative_matrices(pivot, selection),
                "suppress": False,
            }
        )
        _connect_callbacks(pivot)

        if saved_entry:
            _select_pivot_for_transform(pivot)
        else:
            _enter_pivot_edit_mode(pivot)
        _emit_temp_pivot_state_changed()

    except Exception as exc:
        try:
            runtime.get_runtime_manager().disconnect_callbacks(RUNTIME_KEY)
        except Exception:
            pass
        import TheKeyMachine.mods.reportMod as report

        report.report_detected_exception(exc, context="temp pivot")
    finally:
        if open_chunk:
            toolCommon.close_undo_chunk(open_chunk)


def create_centered_temp_pivot(*args):
    return create_temp_pivot(centered=True, *args)


def toggle_temp_pivot(checked=None, *args):
    if checked is False:
        end_temp_pivot()
        return
    if is_temp_pivot_active():
        end_temp_pivot()
        return
    return create_temp_pivot(*args)


def bind_temp_pivot_toolbar_button(widget):
    if widget is None:
        return

    def _sync_from_runtime(key=None):
        if key not in (None, RUNTIME_KEY, "selection_changed"):
            return
        toolCommon.set_checked_safely(widget, is_temp_pivot_active())

    _sync_from_runtime()
    manager = runtime.get_runtime_manager()
    toolCommon.replace_tracked_connection(
        widget,
        "_tkm_temp_pivot_state_sync",
        manager.callback_fired,
        _sync_from_runtime,
        parent=widget,
    )
