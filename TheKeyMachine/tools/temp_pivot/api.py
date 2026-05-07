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
TIME_SLIDER_CONNECTION = "tkm_temp_pivot_time_slider_connection"
DATA_OFFSETS_KEY = "offsets"
PLACEMENT_LAST_OBJECT = "last_object"
PLACEMENT_CENTERED = "centered"
PLACEMENT_WORLDSPACE = "worldspace"

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
    "relative_matrices": {},
    "placement_mode": PLACEMENT_LAST_OBJECT,
    "worldspace_matrix": None,
    "worldspace_origin_matrix": None,
    "previous_time_slider_connection": None,
    "pending_time_refresh": False,
    "suppress": False,
}
_session_offsets = {}


def _data_file():
    return general.get_temp_pivot_data_file()


def _load_data():
    path = _data_file()
    if not os.path.exists(path):
        return {DATA_OFFSETS_KEY: {}}
    try:
        with open(path, "r", encoding="utf-8") as stream:
            data = json.load(stream)
    except (OSError, ValueError, TypeError):
        return {DATA_OFFSETS_KEY: {}}
    if not isinstance(data, dict):
        return {DATA_OFFSETS_KEY: {}}
    data.setdefault(DATA_OFFSETS_KEY, {})
    return data


def _save_data(data):
    folder = general.get_temp_pivot_data_folder()
    os.makedirs(folder, exist_ok=True)
    with open(_data_file(), "w", encoding="utf-8") as stream:
        json.dump(data, stream, indent=2)


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


def _coerce_matrix_values(values):
    try:
        matrix_values = [float(value) for value in values]
    except (RuntimeError, ValueError, TypeError, AttributeError, KeyError, IndexError):
        return None
    if len(matrix_values) != 16:
        return None
    return matrix_values


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


def _playback_slider():
    try:
        return selectionMod.get_playback_slider()
    except (RuntimeError, ValueError, TypeError, AttributeError, KeyError, IndexError):
        return None


def _clear_time_slider_connection():
    slider = _playback_slider()
    if slider:
        connection = _session.get("previous_time_slider_connection") or "activeList"
        try:
            cmds.timeControl(slider, edit=True, mainListConnection=connection, forceRefresh=True)
        except (RuntimeError, ValueError, TypeError, AttributeError, KeyError, IndexError):
            pass
    _session["previous_time_slider_connection"] = None
    try:
        if cmds.selectionConnection(TIME_SLIDER_CONNECTION, query=True, exists=True):
            cmds.deleteUI(TIME_SLIDER_CONNECTION)
    except (RuntimeError, ValueError, TypeError, AttributeError, KeyError, IndexError):
        pass


def _sync_time_slider_to_original_selection():
    selection = _existing_nodes(_session.get("selection") or [])
    if not selection:
        return

    try:
        if not cmds.selectionConnection(TIME_SLIDER_CONNECTION, query=True, exists=True):
            cmds.selectionConnection(TIME_SLIDER_CONNECTION)
        cmds.selectionConnection(TIME_SLIDER_CONNECTION, edit=True, clear=True)
        for node in selection:
            cmds.selectionConnection(TIME_SLIDER_CONNECTION, edit=True, select=node)
    except (RuntimeError, ValueError, TypeError, AttributeError, KeyError, IndexError):
        return

    slider = _playback_slider()
    if not slider:
        return
    try:
        if _session.get("previous_time_slider_connection") is None:
            _session["previous_time_slider_connection"] = cmds.timeControl(slider, query=True, mainListConnection=True)
        cmds.timeControl(slider, edit=True, mainListConnection=TIME_SLIDER_CONNECTION, forceRefresh=True)
    except (RuntimeError, ValueError, TypeError, AttributeError, KeyError, IndexError):
        pass


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


def _place_pivot_for_current_preference(pivot, selection, placement_mode=None):
    placement_mode = placement_mode or _session.get("placement_mode") or PLACEMENT_LAST_OBJECT
    cmds.xform(pivot, matrix=_matrix_list(_origin_pivot_matrix(selection, placement_mode)), worldSpace=True)


def _origin_pivot_matrix(selection, placement_mode=None):
    placement_mode = placement_mode or _session.get("placement_mode") or PLACEMENT_LAST_OBJECT
    if placement_mode == PLACEMENT_WORLDSPACE:
        matrix_values = _coerce_matrix_values(_session.get("worldspace_origin_matrix") or _session.get("worldspace_matrix"))
        if matrix_values:
            return _mmatrix(matrix_values)
    if placement_mode == PLACEMENT_CENTERED:
        return _set_matrix_translation(_object_pivot_space_matrix(selection[-1]), _selection_transform_center(selection))
    return _object_pivot_space_matrix(selection[-1])


def _session_offset_key(selection, placement_mode=None):
    return json.dumps(
        {
            "placement_mode": placement_mode or _session.get("placement_mode") or PLACEMENT_LAST_OBJECT,
            "selection": list(selection or []),
        },
        sort_keys=True,
    )


def _session_offsets_data():
    data = _load_data()
    offsets = data.get(DATA_OFFSETS_KEY)
    if not isinstance(offsets, dict):
        offsets = {}
        data[DATA_OFFSETS_KEY] = offsets
    return data, offsets


def _save_session_offset():
    if not is_temp_pivot_active():
        return
    selection = _existing_nodes(_session.get("selection") or [])
    if not selection:
        return
    placement_mode = _session.get("placement_mode") or PLACEMENT_LAST_OBJECT
    origin_matrix = _origin_pivot_matrix(selection, placement_mode)
    key = _session_offset_key(selection, placement_mode)
    offset_values = _matrix_list(_driver_matrix(TEMP_PIVOT_NODE) * origin_matrix.inverse())
    _session_offsets[key] = offset_values

    data, offsets = _session_offsets_data()
    offsets[key] = {
        "placement_mode": placement_mode,
        "selection": selection,
        "offset_matrix": offset_values,
    }
    try:
        _save_data(data)
    except (OSError, TypeError, ValueError):
        pass


def _apply_session_offset(pivot, selection, placement_mode=None):
    placement_mode = placement_mode or _session.get("placement_mode") or PLACEMENT_LAST_OBJECT
    key = _session_offset_key(selection, placement_mode)
    offset_values = _coerce_matrix_values(_session_offsets.get(key))
    if not offset_values:
        offset_values = _coerce_matrix_values((_session_offsets_data()[1].get(key) or {}).get("offset_matrix"))
        if offset_values:
            _session_offsets[key] = offset_values
    if not offset_values:
        return False
    origin_matrix = _origin_pivot_matrix(selection, placement_mode)
    cmds.xform(pivot, matrix=_matrix_list(_mmatrix(offset_values) * origin_matrix), worldSpace=True)
    return True


def _driver_matrix(pivot):
    matrix_value = _mmatrix(_matrix(pivot))
    return _set_matrix_translation(matrix_value, _world_rotate_pivot(pivot))


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


def _restore_original_selection():
    selection = _existing_nodes(_session.get("selection") or [])
    if selection:
        cmds.select(selection, replace=True)
    else:
        cmds.select(clear=True)


def _reset_session_state(selection=None):
    _session.update(
        {
            "active": False,
            "selection": list(selection or []),
            "relative_matrices": {},
            "placement_mode": PLACEMENT_LAST_OBJECT,
            "worldspace_matrix": None,
            "worldspace_origin_matrix": None,
            "previous_time_slider_connection": None,
            "pending_time_refresh": False,
            "suppress": False,
        }
    )


def _end_session(restore_selection=True):
    _save_session_offset()
    try:
        runtime.get_runtime_manager().disconnect_callbacks(RUNTIME_KEY)
    except (RuntimeError, ValueError, TypeError, AttributeError, KeyError, IndexError):
        pass
    _clear_time_slider_connection()

    selection = list(_session.get("selection") or [])
    _reset_session_state(selection)
    _session["suppress"] = True
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


def _reset_pivot_to_current_preference(select_pivot=False, clear_pivot_edits=False):
    if not is_temp_pivot_active():
        return
    selection = _existing_nodes(_session.get("selection") or [])
    if not selection:
        _end_session(restore_selection=True)
        return

    _session["suppress"] = True
    try:
        if clear_pivot_edits:
            _clear_pivot_transform(TEMP_PIVOT_NODE)
        _place_pivot_for_current_preference(
            TEMP_PIVOT_NODE,
            selection,
            placement_mode=_session.get("placement_mode"),
        )
    finally:
        _session["suppress"] = False
    _session["relative_matrices"] = _relative_matrices(TEMP_PIVOT_NODE, selection)
    _sync_time_slider_to_original_selection()
    if select_pivot:
        _select_pivot_for_transform(TEMP_PIVOT_NODE)


def _refresh_after_time_change():
    _session["pending_time_refresh"] = False
    if _session["suppress"] or not _session["active"]:
        return
    if _session.get("placement_mode") == PLACEMENT_WORLDSPACE:
        selection = _existing_nodes(_session.get("selection") or [])
        if not selection:
            _end_session(restore_selection=True)
            return
        _session["relative_matrices"] = _relative_matrices(TEMP_PIVOT_NODE, selection)
        _sync_time_slider_to_original_selection()
        return
    _reset_pivot_to_current_preference(select_pivot=False)


def _on_time_changed(*args):
    if _session["suppress"] or not _session["active"] or _session.get("pending_time_refresh"):
        return
    _session["pending_time_refresh"] = True
    try:
        cmds.evalDeferred(_refresh_after_time_change, lowestPriority=True)
    except (RuntimeError, ValueError, TypeError, AttributeError, KeyError, IndexError):
        _refresh_after_time_change()


def _connect_callbacks(pivot):
    manager = runtime.get_runtime_manager()
    manager.disconnect_callbacks(RUNTIME_KEY)
    attr_cb = manager.add_node_attribute_changed_callback(pivot, _on_pivot_attribute_changed, key=RUNTIME_KEY)
    selection_cb = manager.add_maya_event_callback("SelectionChanged", _on_selection_changed, key=RUNTIME_KEY)
    time_cb = manager.add_maya_event_callback("timeChanged", _on_time_changed, key=RUNTIME_KEY)
    if attr_cb is None or selection_cb is None or time_cb is None:
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
        _sync_time_slider_to_original_selection()
        return
    if cmds.currentCtx() == "selectSuperContext":
        cmds.setToolTo("moveSuperContext")
    try:
        cmds.ctxEditMode()
    except (RuntimeError, ValueError, TypeError, AttributeError, KeyError, IndexError):
        pass


def create_temp_pivot(*args, centered=False, worldspace=False):
    if is_temp_pivot_active():
        _end_session(restore_selection=True)

    selection = selectionMod.get_selected_objects(long=True, ordered=True)
    selection = [node for node in selection if cmds.objExists(node) and node != TEMP_PIVOT_NODE]
    if not selection:
        return wutil.make_inViewMessage("Select at least one object")

    open_chunk = False
    try:
        open_chunk = toolCommon.open_undo_chunk()

        if worldspace:
            placement_mode = PLACEMENT_WORLDSPACE
        elif centered:
            placement_mode = PLACEMENT_CENTERED
        else:
            placement_mode = PLACEMENT_LAST_OBJECT

        pivot = _ensure_pivot_node()
        _session["suppress"] = True
        recovered_offset = False
        origin_matrix = None
        try:
            _clear_pivot_transform(pivot)
            _place_pivot_for_current_preference(
                pivot,
                selection,
                placement_mode=placement_mode,
            )
            origin_matrix = _matrix(pivot)
            recovered_offset = _apply_session_offset(pivot, selection, placement_mode)
        finally:
            _session["suppress"] = False

        _session.update(
            {
                "active": True,
                "selection": list(selection),
                "relative_matrices": _relative_matrices(pivot, selection),
                "placement_mode": placement_mode,
                "worldspace_matrix": _matrix(pivot) if placement_mode == PLACEMENT_WORLDSPACE else None,
                "worldspace_origin_matrix": origin_matrix if placement_mode == PLACEMENT_WORLDSPACE else None,
                "suppress": False,
            }
        )
        _connect_callbacks(pivot)

        if recovered_offset:
            _select_pivot_for_transform(pivot)
        else:
            _enter_pivot_edit_mode(pivot)
        _sync_time_slider_to_original_selection()
        _emit_temp_pivot_state_changed()

    except Exception as exc:
        try:
            runtime.get_runtime_manager().disconnect_callbacks(RUNTIME_KEY)
        except Exception:
            pass
        _clear_time_slider_connection()
        _reset_session_state(selection if "selection" in locals() else None)
        import TheKeyMachine.mods.reportMod as report

        report.report_detected_exception(exc, context="temp pivot")
    finally:
        if open_chunk:
            toolCommon.close_undo_chunk(open_chunk)


def create_centered_temp_pivot(*args):
    return create_temp_pivot(*args, centered=True)


def create_last_object_temp_pivot(*args):
    return create_temp_pivot(*args)


def create_worldspace_temp_pivot(*args):
    return create_temp_pivot(*args, worldspace=True)


def reset_temp_pivot(*args):
    _reset_pivot_to_current_preference(select_pivot=True, clear_pivot_edits=True)


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
