"""

TheKeyMachine - Animation Toolset for Maya Animators


This file is part of TheKeyMachine, an open source software for Autodesk Maya licensed under the GNU General Public License v3.0 (GPL-3.0).
You are free to use, modify, and distribute this code under the terms of the GPL-3.0 license.
By using this code, you agree to keep it open source and share any modifications.
This code is provided "as is," without any warranty. For the full license text, visit https://www.gnu.org/licenses/gpl-3.0.html

thekeymachine.xyz / x@thekeymachine.xyz

Developed by: Rodrigo Torres / rodritorres.com
Modified by: Alehaaaa / alehaaaa.github.io



"""

from maya import cmds, mel

try:
    import maya.OpenMaya as om  # type: ignore
except ImportError:
    import maya.api.OpenMaya as om  # type: ignore

from TheKeyMachine.Qt import QtCore, QtGui

QRegularExpression = getattr(QtCore, "QRegularExpression", None) or getattr(QtCore, "QRegExp")
QRegularExpressionValidator = getattr(QtGui, "QRegularExpressionValidator", None) or getattr(QtGui, "QRegExpValidator")


import json
import os
import math
import re
import shutil
from collections import Counter
from contextlib import contextmanager

import TheKeyMachine.core.runtimeManager as runtime
from TheKeyMachine.core import curveFitting


import TheKeyMachine.widgets.util as wutil
import TheKeyMachine.widgets.timeline as timelineWidgets
import TheKeyMachine.widgets.customWidgets as customWidgets
import TheKeyMachine.widgets.customDialogs as customDialogs
import TheKeyMachine.mods.generalMod as general
import TheKeyMachine.mods.helperMod as helper
import TheKeyMachine.mods.settingsMod as settings
from TheKeyMachine.data import icons
from TheKeyMachine.tools import common as toolCommon
from TheKeyMachine.tools import clipboard
import TheKeyMachine.mods.selectionMod as selectionMod


SHARE_KEYS_MODE_SETTING = "share_keys_mode"
SHARE_KEYS_MODE_PRESERVE_TANGENT = "preserve_tangent_type"
SHARE_KEYS_MODE_PRESERVE_SHAPE = "preserve_anim_curve_shape"
BAKE_TANGENT_MODE_SETTING = "bake_tangent_mode"
BAKE_TANGENT_MODE_STEP = "step_tangent"
BAKE_TANGENT_MODE_KEEP_TYPE = "keep_tangent_type"
BAKE_TANGENT_MODE_KEEP_SHAPE = "keep_animation_curve_shapes"
BAKE_TANGENT_MODES = (BAKE_TANGENT_MODE_STEP, BAKE_TANGENT_MODE_KEEP_TYPE, BAKE_TANGENT_MODE_KEEP_SHAPE)

BAKE_UNDO_HELP = {
    1: ("Bake on Ones", helper.bake_animation_1_tooltip_text),
    2: ("Bake on Twos", helper.bake_animation_2_tooltip_text),
    3: ("Bake on Threes", helper.bake_animation_3_tooltip_text),
    4: ("Bake on Fours", helper.bake_animation_4_tooltip_text),
}
_key_clipboard_start_frame = None
_paste_to_dialog = None


# _____________________________________________________ General _______________________________________________________________#


def smart_rotation_manipulator():
    actual_mode = cmds.currentCtx()
    mel.eval("buildRotateMM")
    current_rotate_mode = cmds.manipRotateContext("Rotate", q=True, mode=True)
    if actual_mode == "RotateSuperContext":
        if current_rotate_mode == 0:
            cmds.manipRotateContext("Rotate", e=True, mode=1)
        if current_rotate_mode == 1:
            cmds.manipRotateContext("Rotate", e=True, mode=2)
        if current_rotate_mode == 2:
            cmds.manipRotateContext("Rotate", e=True, mode=0)


def smart_rotation_manipulator_release():
    mel.eval("destroySTRSMarkingMenu RotateTool")


def smart_translate_manipulator():
    actual_mode = cmds.currentCtx()
    mel.eval("buildTranslateMM")
    current_move_mode = cmds.manipMoveContext("Move", q=True, mode=True)
    if actual_mode == "moveSuperContext":
        if current_move_mode == 0:
            cmds.manipMoveContext("Move", e=True, mode=2)
        else:
            cmds.manipMoveContext("Move", e=True, mode=0)


def smart_translate_manipulator_release():
    mel.eval("destroySTRSMarkingMenu MoveTool")


def clear_timeslider_selection():
    # fix temporal para limpiar el timeslider
    selection = selectionMod.get_selected_objects()
    cmds.select(selection)


def _begin_timeline_context_tint(default_mode, key, owner=None, color=None):
    import TheKeyMachine.mods.barMod as bar

    return timelineWidgets.begin_timeline_context(
        default_mode=default_mode,
        color=color or bar._active_tint_color(key),
        owner=owner,
        key=key,
    )


def _begin_timeline_tint(timerange, key, owner=None, color=None):
    import TheKeyMachine.mods.barMod as bar

    return timelineWidgets.begin_timeline_tint(
        timerange=timerange,
        color=color or bar._active_tint_color(key),
        owner=owner,
        key=key,
    )


def _timeline_tint_color(key):
    import TheKeyMachine.mods.barMod as bar

    return bar._active_tint_color(key)


def _get_default_value_for_attribute(obj, attr, data):
    short_name = obj.split("|")[-1]
    parts = short_name.split(":")
    namespace = parts[0] if len(parts) > 1 else "default"
    short_object_name = parts[-1]
    attr_full = "{}.{}".format(short_object_name, attr)

    if namespace in data and attr_full in data[namespace]:
        return data[namespace][attr_full]

    default_value = cmds.attributeQuery(attr, node=obj, listDefault=True)
    if default_value:
        return default_value[0]
    return None


def resolve_tool_targets(default_mode="all_animation", ordered_selection=False, long_names=True):
    selection_context = selectionMod.resolve_target_context()
    target_plugs = selection_context["plugs"]
    source = selection_context["source"]
    has_graph_keys = selection_context["has_graph_keys"]
    time_context = timelineWidgets.resolve_time_context(default_mode=default_mode)
    selected_keyframes = selectionMod.get_graph_editor_selected_keyframes() if has_graph_keys else []

    target_objects = selectionMod.object_names_from_plugs(target_plugs)

    if not target_objects:
        target_objects = selectionMod.get_selected_objects(orderedSelection=ordered_selection, long=long_names)

    selected_channels = selectionMod.attribute_names_from_plugs(target_plugs)
    selected_curves = selectionMod.get_anim_curves_from_plugs(target_plugs)

    return {
        "target_plugs": target_plugs,
        "target_objects": target_objects,
        "selected_channels": selected_channels,
        "selected_curves": selected_curves,
        "selected_keyframes": selected_keyframes,
        "time_context": time_context,
        "source": source,
        "has_graph_keys": has_graph_keys,
    }


def get_share_keys_mode():
    return settings.get_setting(SHARE_KEYS_MODE_SETTING, SHARE_KEYS_MODE_PRESERVE_TANGENT)


def set_share_keys_mode(mode):
    if mode not in (SHARE_KEYS_MODE_PRESERVE_TANGENT, SHARE_KEYS_MODE_PRESERVE_SHAPE):
        mode = SHARE_KEYS_MODE_PRESERVE_TANGENT
    settings.set_setting(SHARE_KEYS_MODE_SETTING, mode)


def get_bake_tangent_mode():
    mode = settings.get_setting(BAKE_TANGENT_MODE_SETTING, BAKE_TANGENT_MODE_KEEP_TYPE)
    return mode if mode in BAKE_TANGENT_MODES else BAKE_TANGENT_MODE_KEEP_TYPE


def set_bake_tangent_mode(mode):
    if mode not in BAKE_TANGENT_MODES:
        mode = BAKE_TANGENT_MODE_KEEP_TYPE
    settings.set_setting(BAKE_TANGENT_MODE_SETTING, mode)
    return mode


def _most_common_tangent_type(values):
    values = [value for value in (values or []) if value]
    if not values:
        return None
    return Counter(values).most_common(1)[0][0]


def _unique(items):
    return list(dict.fromkeys(items or []))


def _anim_curves_for_objects(objects):
    return selectionMod.get_anim_curves_for_nodes(objects)


def _set_missing_keys(curves, frames, insert=False, operation=None):
    for curve in _unique(curves):
        for frame in frames:
            if operation and operation.cancelled:
                return
            if cmds.keyframe(curve, query=True, time=(frame, frame)):
                if operation:
                    operation.step()
                continue
            if insert:
                cmds.setKeyframe(curve, time=(frame,), insert=True)
            else:
                cmds.setKeyframe(curve, time=(frame,))
            if operation:
                operation.step()


def _set_keys_on_frames(curves, frames):
    for curve in _unique(curves):
        for frame in frames:
            cmds.setKeyframe(curve, time=(frame,))


def _normalize_key_frames(frames):
    normalized = []
    for frame in frames or []:
        try:
            frame_value = float(frame)
        except Exception:
            continue
        if int(frame_value) == frame_value:
            frame_value = int(frame_value)
        normalized.append(frame_value)
    return sorted(set(normalized))


def _apply_step_tangents(curves, time_range):
    for curve in _unique(curves):
        cmds.keyTangent(
            curve,
            edit=True,
            time=time_range,
            inTangentType="stepnext",
            outTangentType="step",
        )


# Estas dos funciones la idea era usarlas para hacer overlap


def find_root_in_selection(objects):
    """
    Encuentra el nodo raíz en una selección.
    Sube por la jerarquía hasta el nodo raíz y verifica si los hijos están en la lista.
    """
    # Ordenamos los objetos por nombre para garantizar que procesamos primero el nodo padre si está presente.
    objects_sorted = sorted(objects)

    for obj in objects_sorted:
        # Obtiene la lista de descendientes
        descendants = cmds.listRelatives(obj, allDescendents=True) or []

        # Verifica si algún descendiente coincide con nuestra lista de objetos
        matching_descendants = [desc for desc in descendants if desc in objects]

        # Si hay coincidencias, significa que el objeto actual es un nodo raíz para los objetos seleccionados.
        if matching_descendants:
            return obj

    return None


def find_all_roots_in_selection():
    """
    Identifica todos los nodos raíces en la selección.
    """
    selection = selectionMod.get_selected_objects()
    root_nodes = []

    while selection:
        root_node = find_root_in_selection(selection)
        if root_node:
            root_nodes.append(root_node)

            # Obtiene la lista de descendientes del nodo raíz
            descendants = cmds.listRelatives(root_node, allDescendents=True) or []

            # Elimina el nodo raíz y todos sus descendientes de la lista de selección
            for obj in [root_node] + descendants:
                if obj in selection:
                    selection.remove(obj)
        else:
            break

    return root_nodes


# --------------------------------------------------- LINK OBJECTS -----------------------------------------------------


# Variables globales
relative_data = {}


def load_relative_data():
    global relative_data

    matrix_file_path = general.get_copy_link_data_file()

    # Verificar si el archivo existe
    if not os.path.exists(matrix_file_path):
        cmds.warning("No saved relative matrix data found")
        return

    # Leer el diccionario del archivo JSON
    with open(matrix_file_path, "r") as f:
        relative_data = json.load(f)


def copy_link(*args):
    matrix_file_path = general.get_copy_link_data_file()

    seleccion = selectionMod.get_selected_objects()
    if len(seleccion) < 2:
        return wutil.make_inViewMessage("Select at least 2 objects")

    main_obj = seleccion[-1]
    follow_objs = seleccion[:-1]

    save_dict = {"main_obj": main_obj, "relative_matrices": {}}

    for follow_obj in follow_objs:
        main_matrix = cmds.xform(main_obj, query=True, matrix=True, worldSpace=True)
        follow_matrix = cmds.xform(follow_obj, query=True, matrix=True, worldSpace=True)

        main_mmatrix = om.MMatrix(main_matrix)
        follow_mmatrix = om.MMatrix(follow_matrix)

        relative_matrix = follow_mmatrix * main_mmatrix.inverse()

        # Guardar la matriz relativa en el diccionario
        save_dict["relative_matrices"][follow_obj] = [relative_matrix.getElement(i, j) for i in range(4) for j in range(4)]

    # Guardar el diccionario en un archivo JSON

    matrix_file_folder = general.get_copy_link_data_folder()
    os.makedirs(matrix_file_folder, exist_ok=True)
    with open(matrix_file_path, "w") as f:
        json.dump(save_dict, f)

    wutil.make_inViewMessage("Copied link data")

    load_relative_data()


def paste_link(*args):
    global relative_data

    main_obj = relative_data.get("main_obj")
    relative_matrices = relative_data.get("relative_matrices", {})

    # No necesitamos verificar la selección. Usamos directamente los objetos de relative_data.
    follow_objs = list(relative_matrices.keys())

    # Verificar si existe un rango seleccionado en el timeline
    playback_range = cmds.playbackOptions(query=True, minTime=True), cmds.playbackOptions(query=True, maxTime=True)
    range_start, range_end = cmds.timeControl("timeControl1", q=True, rangeArray=True)

    if range_start != playback_range[0] or range_end != playback_range[1]:
        frames = list(range(int(range_start), int(range_end)))
    else:
        # Si no hay un rango seleccionado, aplicar solo al frame actual
        frames = [cmds.currentTime(query=True)]

    for frame in frames:
        cmds.currentTime(frame)

        for follow_obj in follow_objs:
            if follow_obj in relative_matrices:
                relative_matrix_list = relative_matrices[follow_obj]
                relative_matrix = om.MMatrix()
                for i in range(4):
                    for j in range(4):
                        relative_matrix.setElement(i, j, relative_matrix_list[i * 4 + j])

                main_matrix = cmds.xform(main_obj, query=True, matrix=True, worldSpace=True)
                main_mmatrix = om.MMatrix(main_matrix)

                new_follow_matrix = relative_matrix * main_mmatrix
                new_follow_matrix_list = [new_follow_matrix.getElement(i, j) for i in range(4) for j in range(4)]

                cmds.xform(follow_obj, matrix=new_follow_matrix_list, worldSpace=True)
                cmds.setKeyframe(follow_obj, attribute="translate", t=frame)
                cmds.setKeyframe(follow_obj, attribute="rotate", t=frame)
                cmds.setKeyframe(follow_obj, attribute="scale", t=frame)
            else:
                cmds.warning(f"Could not save relative matrix for {follow_obj}")



def paste_link_callback():
    global relative_data

    main_obj = relative_data.get("main_obj")
    relative_matrices = relative_data.get("relative_matrices", {})

    # No necesitamos verificar la selección. Usamos directamente los objetos de relative_data.
    follow_objs = list(relative_matrices.keys())

    for follow_obj in follow_objs:
        if follow_obj in relative_matrices:
            relative_matrix_list = relative_matrices[follow_obj]
            relative_matrix = om.MMatrix()
            for i in range(4):
                for j in range(4):
                    relative_matrix.setElement(i, j, relative_matrix_list[i * 4 + j])

            main_matrix = cmds.xform(main_obj, query=True, matrix=True, worldSpace=True)
            main_mmatrix = om.MMatrix(main_matrix)

            new_follow_matrix = relative_matrix * main_mmatrix
            new_follow_matrix_list = [new_follow_matrix.getElement(i, j) for i in range(4) for j in range(4)]

            cmds.xform(follow_obj, matrix=new_follow_matrix_list, worldSpace=True)

        else:
            cmds.warning(f"Could not save relative matrix for {follow_obj}")


process_callback = False
LINK_OBJECTS_RUNTIME_KEY = "link_objects_auto_link"


def add_link_obj_callbacks(*args):
    global relative_data, process_callback

    process_callback = True
    manager = runtime.get_runtime_manager()
    manager.disconnect_callbacks(LINK_OBJECTS_RUNTIME_KEY)

    # Obtén el nombre del objeto principal desde relative_data
    main_obj_name = relative_data.get("main_obj")
    if not main_obj_name:
        cmds.warning("Relative data object not found")
        return

    attribute_cb = manager.add_node_attribute_changed_callback(main_obj_name, attribute_callback_function, key=LINK_OBJECTS_RUNTIME_KEY)
    time_cb = manager.connect_signal(manager.time_changed, time_callback_function, key=LINK_OBJECTS_RUNTIME_KEY, unique=False)

    if attribute_cb is None or not time_cb:
        manager.disconnect_callbacks(LINK_OBJECTS_RUNTIME_KEY)
        cmds.warning("Could not register link object callbacks")


def attribute_callback_function(msg, plug, otherPlug, clientData):
    global process_callback

    if not process_callback:
        return

    if msg & om.MNodeMessage.kAttributeSet:
        process_callback = False
        paste_link_callback()
        process_callback = True


def time_callback_function(clientData):
    global process_callback
    if not process_callback:
        return
    process_callback = False
    paste_link_callback()  # Llamada a tu función set_matrix
    process_callback = True


def remove_link_obj_callbacks(*args):
    try:
        runtime.get_runtime_manager().disconnect_callbacks(LINK_OBJECTS_RUNTIME_KEY)
    except Exception as e:
        import TheKeyMachine.mods.reportMod as report

        report.report_detected_exception(e, context="relative matrix callback cleanup")


# ---------------------------------------------------------- SHARE KEYS ---------------------------------------------------------


def share_keys(*args):
    target_info = resolve_tool_targets(default_mode="all_animation", ordered_selection=True, long_names=True)
    objetos = target_info["target_objects"]
    target_plugs = target_info["target_plugs"]
    time_context = target_info["time_context"]

    if not objetos and not target_plugs:
        return wutil.make_inViewMessage("Select at least one object")

    all_frames = set()
    object_plug_frames = {obj: {} for obj in objetos}

    for plug in target_plugs:
        if not cmds.objExists(plug) or "." not in plug:
            continue
        obj = plug.split(".", 1)[0]
        if time_context.mode == "all_animation":
            plug_frames = cmds.keyframe(plug, query=True, timeChange=True) or []
        else:
            plug_frames = cmds.keyframe(plug, query=True, time=time_context.timerange, timeChange=True) or []
        normalized_frames = {int(frame) if int(frame) == frame else frame for frame in plug_frames}
        if not normalized_frames:
            continue
        object_plug_frames.setdefault(obj, {})[plug] = normalized_frames
        all_frames.update(normalized_frames)

    if not all_frames:
        return wutil.make_inViewMessage("No keys found in selection")

    shared_frames = sorted(all_frames)
    preserve_curve_shape = get_share_keys_mode() == SHARE_KEYS_MODE_PRESERVE_SHAPE

    with toolCommon.tool_operation(
        tool_id="share_keys",
        label="Share Keys",
        progress=True,
        progress_max=sum(len(plugs) * len(shared_frames) for plugs in object_plug_frames.values()),
        undo=True,
        tint="range",
        timerange=(int(shared_frames[0]), int(shared_frames[-1])),
        tint_color=_timeline_tint_color("share_keys"),
    ) as operation:
        operation.start()
        for objeto in objetos:
            for plug, existing_frames in object_plug_frames.get(objeto, {}).items():
                node_name, attribute_name = plug.split(".", 1)
                for frame in shared_frames:
                    if operation.cancelled:
                        return
                    if frame not in existing_frames:
                        set_keyframe_kwargs = {
                            "attribute": attribute_name,
                            "time": (frame,),
                        }
                        if preserve_curve_shape:
                            set_keyframe_kwargs["insert"] = True
                        cmds.setKeyframe(node_name, **set_keyframe_kwargs)
                    operation.step()


def _frames_from_last_selected(time_context=None):
    selection = selectionMod.get_selected_objects(orderedSelection=True, long=True)
    if len(selection) < 2:
        wutil.make_inViewMessage("Select targets, then the source object last")
        return None, [], []

    source = selection[-1]
    targets = selection[:-1]
    query_kwargs = {"query": True, "timeChange": True}
    if time_context and time_context.mode != "all_animation":
        query_kwargs["time"] = time_context.timerange
    frames = cmds.keyframe(source, **query_kwargs) or []
    frames = _normalize_key_frames(frames)
    if not frames:
        wutil.make_inViewMessage("Last selected object has no keys")
        return source, targets, []
    return source, targets, frames


def _bake_curves_to_source_frames(curves, frames, operation=None, preserve_shape=False):
    curves = _unique(curves)
    frames = _normalize_key_frames(frames)
    if not curves or not frames:
        return

    frame_lookup = set(frames)
    time_range = (frames[0], frames[-1])
    shape_data = curveFitting.capture(curves, frames) if preserve_shape else {}
    for curve in curves:
        if operation and operation.cancelled:
            return
        for frame in frames:
            sampled = (shape_data.get(curve) or {}).get(float(frame))
            if sampled:
                cmds.setKeyframe(curve, time=(frame,), value=sampled["value"])
            else:
                cmds.setKeyframe(curve, time=(frame,))
        existing_frames = _normalize_key_frames(cmds.keyframe(curve, query=True, time=time_range, timeChange=True) or [])
        for frame in existing_frames:
            if frame not in frame_lookup:
                cmds.cutKey(curve, time=(frame, frame), option="keys")
        if operation:
            operation.step()
    if preserve_shape:
        curveFitting.apply(shape_data)


def share_keys_from_last_selected(*args):
    time_context = timelineWidgets.resolve_time_context(default_mode="all_animation")
    _source, targets, frames = _frames_from_last_selected(time_context)
    if not frames:
        return

    keep_curve_shape = get_share_keys_mode() == SHARE_KEYS_MODE_PRESERVE_SHAPE
    curves_by_target = {target: _anim_curves_for_objects([target]) for target in targets}
    with toolCommon.tool_operation(
        tool_id="share_keys",
        label="Share Keys",
        progress=True,
        progress_max=sum(len(curves) * len(frames) for curves in curves_by_target.values()),
        undo=True,
        tint="range",
        timerange=(int(frames[0]), int(frames[-1])),
        tint_color=_timeline_tint_color("share_keys"),
    ) as operation:
        for target in targets:
            if operation.cancelled:
                return
            _set_missing_keys(curves_by_target[target], frames, insert=keep_curve_shape, operation=operation)


# ______________________________________ ReBlock Move


def reblock_move(*args):
    # Obtener la lista de objetos seleccionados
    objetos = selectionMod.get_selected_objects(long=True)  # Usar nombres largos para mayor precisión

    # Verificar que haya al menos un objeto seleccionado
    if len(objetos) < 1:
        return

    curvas = selectionMod.get_anim_curves_for_nodes(objetos, include_shapes=True)

    # Crear un diccionario para contar perfiles
    perfiles = Counter()

    # Identificar perfil de cada curva y actualizar el contador
    for curva in curvas:
        keyframes = cmds.keyframe(curva, query=True, timeChange=True)
        if keyframes is None:
            continue
        fotogramas = tuple(sorted(keyframes))
        perfiles[fotogramas] += 1

    # Identificar el perfil mayoritario
    perfil_mayoritario, _ = perfiles.most_common(1)[0]

    # Corregir curvas que no coinciden con el perfil mayoritario
    for curva in curvas:
        keyframes = cmds.keyframe(curva, query=True, timeChange=True)
        if keyframes is None:
            continue
        fotogramas = tuple(sorted(keyframes))

        if fotogramas != perfil_mayoritario:
            # Ajustar el número de keyframes
            if len(fotogramas) < len(perfil_mayoritario):
                # Añadir keyframes faltantes
                for frame in perfil_mayoritario:
                    if frame not in fotogramas:
                        cmds.setKeyframe(curva, time=frame, value=0)  # Añadir keyframe en la posición correcta

            elif len(fotogramas) > len(perfil_mayoritario):
                # Eliminar keyframes sobrantes
                for frame in fotogramas:
                    if frame not in perfil_mayoritario:
                        cmds.cutKey(curva, time=(frame, frame), option="keys")  # Eliminar keyframe

            # Volver a obtener los keyframes después de añadir/eliminar
            keyframes = cmds.keyframe(curva, query=True, timeChange=True)
            fotogramas = tuple(sorted(keyframes))

            # Determinar si la curva minoritaria está adelantada o retrasada
            adelantada = fotogramas[0] > perfil_mayoritario[0]

            # Mover keyframes en la dirección adecuada
            rango_keyframes = range(min(len(fotogramas), len(perfil_mayoritario)))
            if adelantada:
                # Mover keyframes de inicio a fin
                for i in rango_keyframes:
                    frame = fotogramas[i]
                    frame_objetivo = perfil_mayoritario[i]
                    cmds.keyframe(curva, edit=True, time=(frame,), timeChange=frame_objetivo)
            else:
                # Mover keyframes de fin a inicio
                for i in reversed(rango_keyframes):
                    frame = fotogramas[i]
                    frame_objetivo = perfil_mayoritario[i]
                    cmds.keyframe(curva, edit=True, time=(frame,), timeChange=frame_objetivo)


def reblock_insert(*args):
    # Obtener la lista de objetos actualmente seleccionados en la escena
    objetos = selectionMod.get_selected_objects()

    # Verificar que haya al menos dos objetos seleccionados
    if len(objetos) < 2:
        return wutil.make_inViewMessage("Select at least 2 objects")

    # Crear una lista de fotogramas clave de todos los objetos
    frames_claves = []
    for objeto in objetos:
        fotogramas = cmds.keyframe(objeto, query=True, timeChange=True)
        if fotogramas is not None:
            frames_claves.extend(fotogramas)

    # Identificar los fotogramas clave "mayoritarios" como los más comunes
    contador_frames = Counter(frames_claves)
    frames_mayoritarios = {frame for frame, count in contador_frames.items() if count >= len(objetos) / 2}

    for objeto in objetos:
        # Obtener los fotogramas clave específicos del objeto actual
        frames_objeto = set(cmds.keyframe(objeto, query=True, timeChange=True) or [])

        for frame in frames_objeto:
            # Si el fotograma no es mayoritario, encontrar el fotograma mayoritario más cercano y insertar una nueva clave allí
            if frame not in frames_mayoritarios:
                frame_mayoritario_cercano = min(frames_mayoritarios, key=lambda x: abs(x - frame))
                valor = cmds.keyframe(objeto, query=True, time=(frame, frame), valueChange=True)
                if valor:
                    cmds.setKeyframe(objeto, time=frame_mayoritario_cercano, value=valor[0], insert=True)
                    cmds.cutKey(objeto, time=(frame, frame))


# ___________________________ BAKE ANIM  _____________________________________


def _validate_bake_interval(value):
    try:
        interval = float(value)
    except (TypeError, ValueError):
        raise ValueError("Bake interval must be a number")
    if not math.isfinite(interval) or interval <= 0:
        raise ValueError("Bake interval must be greater than zero")
    return int(interval) if interval.is_integer() else interval


def _bake_sample_times(start_frame, end_frame, interval):
    return curveFitting.sample_times(start_frame, end_frame, interval)


def bake_animation(bake_interval=1, window=None):
    try:
        bake_interval = _validate_bake_interval(bake_interval)
    except ValueError as error:
        return wutil.make_inViewMessage(str(error))

    bake_title, bake_tooltip = BAKE_UNDO_HELP.get(bake_interval, ("Bake Animation", helper.bake_animation_custom_tooltip_text))
    tool_key = "bake_animation_{}".format(bake_interval) if bake_interval in BAKE_UNDO_HELP else "bake_animation_custom"

    try:
        target_info = resolve_tool_targets(default_mode="all_animation", ordered_selection=True, long_names=True)
        selected_objects = target_info["target_objects"]
        selected_channels = target_info["selected_channels"]

        if not selected_objects:
            return wutil.make_inViewMessage("Select at least one object for baking")

        time_context = target_info["time_context"]
        start_frame, end_frame = time_context.timerange
        bake_tangent_mode = get_bake_tangent_mode()
        curves_to_update = _unique(target_info["selected_curves"])
        if not curves_to_update:
            curves_to_update = _anim_curves_for_objects(selected_objects)

        tangent_types_by_curve = {}
        curve_shape_data = {}
        if bake_tangent_mode == BAKE_TANGENT_MODE_KEEP_TYPE:
            for curve in curves_to_update:
                in_tangent = _most_common_tangent_type(
                    cmds.keyTangent(curve, query=True, time=(start_frame, end_frame), inTangentType=True)
                )
                out_tangent = _most_common_tangent_type(
                    cmds.keyTangent(curve, query=True, time=(start_frame, end_frame), outTangentType=True)
                )
                if in_tangent or out_tangent:
                    tangent_types_by_curve[curve] = (in_tangent, out_tangent)
        elif bake_tangent_mode == BAKE_TANGENT_MODE_KEEP_SHAPE:
            sample_times = _bake_sample_times(start_frame, end_frame, bake_interval)
            curve_shape_data = curveFitting.capture(curves_to_update, sample_times)

        with toolCommon.tool_operation(
            tool_id=tool_key,
            label=bake_title,
            progress=True,
            progress_max=max(1, int((end_frame - start_frame) / float(bake_interval or 1)) + 1),
            undo=True,
            tint="range",
            timerange=time_context.timerange,
            tint_color=_timeline_tint_color(tool_key),
            anchor_widget=window,
        ) as operation:
            operation.start()
            # Hacer bake a las curvas de animación de los objetos seleccionados.
            bake_kwargs = dict(
                time=(start_frame, end_frame),
                sampleBy=bake_interval,
                preserveOutsideKeys=True,
                # A sparse bake can legitimately add no keys to an existing
                # anim curve.  Keep-shape mode still needs a key at every
                # sample; bakeResults samples the evaluated curve before it
                # replaces the animation, preserving those full-frame values.
                sparseAnimCurveBake=False,
                removeBakedAttributeFromLayer=False,
                bakeOnOverrideLayer=False,
                controlPoints=False,
                shape=True,
            )
            if selected_channels:
                bake_kwargs["attribute"] = selected_channels
            cmds.bakeResults(selected_objects, **bake_kwargs)
            operation.step(amount=operation.progress.max_value if operation.progress else 1)

            if bake_tangent_mode == BAKE_TANGENT_MODE_STEP:
                _apply_step_tangents(curves_to_update, (start_frame, end_frame))
            elif bake_tangent_mode == BAKE_TANGENT_MODE_KEEP_TYPE:
                for curve, (in_tangent, out_tangent) in tangent_types_by_curve.items():
                    tangent_kwargs = {}
                    if in_tangent:
                        tangent_kwargs["inTangentType"] = in_tangent
                    if out_tangent:
                        tangent_kwargs["outTangentType"] = out_tangent
                    if tangent_kwargs:
                        cmds.keyTangent(curve, edit=True, time=(start_frame, end_frame), **tangent_kwargs)
            elif bake_tangent_mode == BAKE_TANGENT_MODE_KEEP_SHAPE:
                curveFitting.apply(curve_shape_data)

    except Exception as e:
        cmds.warning("An error occurred: {}".format(e))

    if window:
        window.close()


def bake_animation_from_last_selected(*args):
    time_context = timelineWidgets.resolve_time_context(default_mode="all_animation")
    _source, targets, frames = _frames_from_last_selected(time_context)
    if not frames:
        return

    current_time = cmds.currentTime(query=True)
    curves_by_target = {target: _anim_curves_for_objects([target]) for target in targets}
    try:
        with toolCommon.tool_operation(
            tool_id="bake_animation_1",
            label="Bake Animation",
            progress=True,
            progress_max=sum(len(curves) for curves in curves_by_target.values()),
            undo=True,
            tint="range",
            timerange=(int(frames[0]), int(frames[-1])),
            tint_color=_timeline_tint_color("bake_animation_1"),
        ) as operation:
            for target in targets:
                if operation.cancelled:
                    return
                curves = curves_by_target[target]
                tangent_mode = get_bake_tangent_mode()
                _bake_curves_to_source_frames(
                    curves,
                    frames,
                    operation=operation,
                    preserve_shape=tangent_mode == BAKE_TANGENT_MODE_KEEP_SHAPE,
                )

                if tangent_mode == BAKE_TANGENT_MODE_STEP:
                    _apply_step_tangents(curves, (frames[0], frames[-1]))
    finally:
        cmds.currentTime(current_time)


def bake_animation_1(*args):
    bake_animation(bake_interval=1)


def bake_animation_2(*args):
    bake_animation(bake_interval=2)


def bake_animation_3(*args):
    bake_animation(bake_interval=3)


def bake_animation_4(*args):
    bake_animation(bake_interval=4)


# ____________________________________________________ ShiftKeys Box _____________________________________________________________#


def delete_keyframes_before_current_time():
    # Obtén los objetos seleccionados
    selected = selectionMod.get_selected_objects()

    if not selected:
        return wutil.make_inViewMessage("Select at least one object")

    # Obtiene el tiempo actual
    current_time = cmds.currentTime(query=True)

    for obj in selected:
        # Obtiene todos los keyframes del objeto
        keyframes = cmds.keyframe(obj, query=True)

        if not keyframes:
            continue

        # Elimina los keyframes que están antes de la currentTime
        for keyframe in sorted(keyframes):
            if keyframe < current_time:
                cmds.cutKey(obj, time=(keyframe, keyframe))


def delete_keyframes_after_current_time():
    # Obtén los objetos seleccionados
    selected = selectionMod.get_selected_objects()

    if not selected:
        return wutil.make_inViewMessage("Select at least one object")

    # Obtiene el tiempo actual
    current_time = cmds.currentTime(query=True)

    for obj in selected:
        # Obtiene todos los keyframes del objeto
        keyframes = cmds.keyframe(obj, query=True)

        if not keyframes:
            continue

        # Elimina los keyframes que están después de la currentTime
        for keyframe in sorted(keyframes):
            if keyframe > current_time:
                cmds.cutKey(obj, time=(keyframe, keyframe))


def select_all_animation_curves(*args):
    # Tipos de curvas de animación que quieres seleccionar
    tipos_de_curvas = ["animCurveTL", "animCurveTA", "animCurveTT", "animCurveTU"]

    # Lista para almacenar las curvas seleccionadas
    curvas_seleccionadas = []

    # Recorre todos los tipos de curvas y busca las que coinciden
    for tipo in tipos_de_curvas:
        curvas = cmds.ls(type=tipo)
        if curvas:
            curvas_seleccionadas.extend(curvas)

    # Selecciona las curvas encontradas
    if curvas_seleccionadas:
        cmds.select(curvas_seleccionadas)
        cmds.selectKey(add=True)
    else:
        wutil.make_inViewMessage("No anim curves found")


def clear_selected_keys(*args):
    cmds.selectKey(clear=True)


# For Hotkeys


# _____


def insert_inbetween(count=1, *args):
    _relative_timechange(count)


def remove_inbetween(count=1, *args):
    _relative_timechange(-count)


def _scene_anim_curves():
    curves = []
    for curve_type in ("animCurveTL", "animCurveTA", "animCurveTT", "animCurveTU"):
        curves.extend(cmds.ls(type=curve_type) or [])
    return _unique(curves)


def _target_anim_curves():
    target_info = resolve_tool_targets(default_mode="all_animation", ordered_selection=True, long_names=True)
    curves = _unique(target_info.get("selected_curves"))
    if curves:
        return curves
    return _anim_curves_for_objects(target_info.get("target_objects"))


def nudge_all_keys(offset, *args):
    curves = _target_anim_curves()
    if not curves:
        return wutil.make_inViewMessage("No animation curves found")
    offset = int(offset)
    if not offset:
        return
    with toolCommon.tool_operation(tool_id="nudge_all_keys", label="Nudge All Keys", progress=True, progress_max=1, undo=True):
        cmds.keyframe(curves, edit=True, relative=True, includeUpperBound=True, option="over", timeChange=offset)
        _nudge_current_time(offset)


def nudge_scene_keys(offset, *args):
    curves = _scene_anim_curves()
    if not curves:
        return wutil.make_inViewMessage("No anim curves found")
    offset = int(offset)
    if not offset:
        return
    with toolCommon.tool_operation(tool_id="nudge_scene_keys", label="Nudge Scene Keys", progress=True, progress_max=1, undo=True):
        cmds.keyframe(curves, edit=True, relative=True, includeUpperBound=True, option="over", timeChange=offset)
        _nudge_current_time(offset)


def inbetween_scene(count=1, *args):
    curves = _scene_anim_curves()
    if not curves:
        return wutil.make_inViewMessage("No anim curves found")
    count = int(count)
    if not count:
        return
    current = cmds.currentTime(q=True)
    with toolCommon.tool_operation(tool_id="inbetween_scene", label="Inbetween Scene", progress=True, progress_max=1, undo=True):
        cmds.keyframe(curves, edit=True, time=("{}:".format(current + 1),), relative=True, timeChange=count, option="over")


def _relative_timechange(count):
    if not cmds.keyframe(query=True):
        return
    count = int(count)
    current = cmds.currentTime(q=True)
    cmds.keyframe(time=("{}:".format(current + 1),), relative=True, timeChange=count, option="over")


def nudge_value(default=1):
    try:
        return int(settings.get_setting("nudge_value", default))
    except Exception:
        return default


def _nudge_current_time(offset):
    try:
        cmds.currentTime(cmds.currentTime(q=True) + int(offset))
    except Exception:
        pass


def move_keyframes_in_range(*args):
    offset = nudge_value()
    if args and isinstance(args[0], (int, float)):
        offset = offset * int(args[0])

    if not offset:
        return

    current_time = cmds.currentTime(q=True)
    target_info = resolve_tool_targets(default_mode="all_animation", ordered_selection=True, long_names=True)
    selection = target_info["target_objects"]
    target_plugs = target_info["target_plugs"]
    target_curves = target_info["selected_curves"]
    time_context = target_info["time_context"]
    has_range = time_context.mode == "time_slider_range"
    start_frame, end_frame = time_context.timerange

    with toolCommon.tool_operation(tool_id="move_keyframes_in_range", label="Move Keyframes", progress=True, progress_max=1, undo=True):
        if target_info["has_graph_keys"]:
            cmds.keyframe(edit=True, animation="keys", relative=True, includeUpperBound=True, option="over", timeChange=offset)
            _nudge_current_time(offset)
            return

        if has_range:
            animation_curves = list(dict.fromkeys(target_curves))
            if not animation_curves and selection:
                animation_curves = cmds.keyframe(selection, q=True, name=True) or []
            if not animation_curves:
                return

            curves_in_range = [curve for curve in animation_curves if cmds.keyframe(curve, query=True, time=(start_frame, end_frame))]

            if not curves_in_range:
                return

            cmds.keyframe(
                curves_in_range,
                edit=True,
                relative=True,
                includeUpperBound=True,
                option="over",
                time=(start_frame, end_frame),
                timeChange=offset,
            )
            cmds.currentTime(current_time + offset)
            try:
                cmds.playbackOptions(sst=start_frame + offset, set=end_frame + offset, sv=True)
            except Exception:
                pass
            return

        if not target_plugs:
            return

        plugs_with_key_at_current = []
        grouped_source_times = {}

        for plug in target_plugs:
            key_times = cmds.keyframe(plug, query=True, tc=True) or []
            if not key_times:
                continue

            key_times = sorted(set(key_times))

            if current_time in key_times:
                plugs_with_key_at_current.append(plug)
                continue

            if offset > 0:
                candidates = [t for t in key_times if t < current_time]
                source_time = candidates[-1] if candidates else None
            else:
                candidates = [t for t in key_times if t > current_time]
                source_time = candidates[0] if candidates else None

            if source_time is not None:
                grouped_source_times.setdefault(source_time, []).append(plug)

        if plugs_with_key_at_current:
            cmds.keyframe(
                plugs_with_key_at_current, edit=True, relative=True, option="over", time=(current_time, current_time), timeChange=offset
            )
            cmds.currentTime(current_time + offset)
            return

        for source_time, plugs in grouped_source_times.items():
            cmds.keyframe(plugs, edit=True, absolute=True, option="over", time=(source_time, source_time), timeChange=current_time)


# _____________________________________________________ Key Tools  Customgraph _______________________________________________________________#


def deleteStaticCurves():
    # Obtener los objetos seleccionados con sus nombres completos una sola vez
    selected_objects = selectionMod.get_selected_objects(long=True)

    curves_to_delete = []
    for curve in selectionMod.get_anim_curves_for_nodes(selected_objects, include_shapes=True):
        values = cmds.keyframe(curve, query=True, valueChange=True) or []
        if len(set(values)) == 1:
            curves_to_delete.append(curve)

    # Eliminar todas las curvas recopiladas en un solo comando
    if curves_to_delete:
        cmds.delete(curves_to_delete)


# --------------------------------------------------- Anim Curve hotkey helpers ---------------------------------------------------


@contextmanager
def _animation_command_context(label, tint_key=None, default_mode="all_animation", timerange=None, tint=True):
    """Wrap animation hotkey commands with the shared tool operation.

    tint=False disables the timeline/context tint for commands that should feel silent.
    """
    operation_tint = "none"
    if tint:
        operation_tint = "range" if timerange is not None else "context"

    with toolCommon.tool_operation(
        tool_id=tint_key,
        label=label,
        progress=True,
        progress_max=1,
        undo=True,
        undo_name=toolCommon.make_undo_chunk_name(title=label),
        tint=operation_tint,
        timerange=timerange,
        default_mode=default_mode,
        tint_key=tint_key,
        tint_color=_timeline_tint_color(tint_key) if tint_key and operation_tint != "none" else None,
    ):
        yield


def _selection_time_kwargs(time_context):
    if not time_context:
        return {}
    if time_context.mode in ("graph_editor_keys", "time_slider_range"):
        return {"time": (time_context.start_frame, time_context.end_frame)}
    return {}


def _selected_key_times_for_curve(curve):
    try:
        return cmds.keyframe(curve, query=True, selected=True, timeChange=True) or []
    except (RuntimeError, ValueError, TypeError, AttributeError, KeyError, IndexError):
        return []


def _key_times_for_curve_context(curve, target_info):
    time_context = (target_info or {}).get("time_context")
    if time_context and time_context.mode == "graph_editor_keys":
        return _selected_key_times_for_curve(curve)

    query_kwargs = {"query": True, "timeChange": True}
    if time_context and time_context.mode == "time_slider_range":
        query_kwargs["time"] = time_context.timerange

    try:
        return cmds.keyframe(curve, **query_kwargs) or []
    except (RuntimeError, ValueError, TypeError, AttributeError, KeyError, IndexError):
        return []


def _resolve_key_command_targets(default_mode="all_animation", include_shapes=True):
    """Return the selection context in the shapes most key-edit commands need."""
    target_info = resolve_tool_targets(default_mode=default_mode, ordered_selection=True, long_names=True)
    channel_plugs, channel_source = selectionMod.get_attribute_plugs_from_nodes(selectionMod.get_selected_objects(long=True))
    if channel_source == "channel_box" and channel_plugs:
        target_info = dict(target_info)
        target_info["target_plugs"] = _unique(channel_plugs)
        target_info["target_objects"] = selectionMod.object_names_from_plugs(channel_plugs)
        target_info["selected_channels"] = selectionMod.attribute_names_from_plugs(channel_plugs)
        target_info["selected_curves"] = selectionMod.get_anim_curves_from_plugs(channel_plugs)
        target_info["selected_keyframes"] = []
        target_info["source"] = "channel_box"
        target_info["has_graph_keys"] = False

    target_plugs = _unique(target_info.get("target_plugs"))
    selected_objects = _unique(target_info.get("target_objects"))
    selected_channels = _unique(target_info.get("selected_channels"))

    if include_shapes and selected_objects:
        shaped_objects = list(selected_objects)
        for obj in selected_objects:
            shaped_objects.extend(cmds.listRelatives(obj, shapes=True, fullPath=True) or [])
        selected_objects = _unique(shaped_objects)

    return target_info, target_plugs, selected_objects, selected_channels


def _curves_for_key_selection(target_info=None, include_shapes=True):
    if target_info is None:
        target_info, _target_plugs, _selected_objects, _selected_channels = _resolve_key_command_targets(
            include_shapes=include_shapes
        )

    curves = _unique(target_info.get("selected_curves"))
    if curves:
        return curves

    target_plugs = _unique(target_info.get("target_plugs"))
    curves.extend(selectionMod.get_anim_curves_from_plugs(target_plugs))
    if _is_explicit_channel_source(target_info.get("source")):
        return _unique(curves)

    selected_objects = _unique(target_info.get("target_objects"))
    curves.extend(selectionMod.get_anim_curves_for_nodes(selected_objects, include_shapes=include_shapes))
    return _unique(curves)


def _resolve_anim_curve_tool_context(default_mode="all_animation", include_shapes=True):
    target_info, _target_plugs, _selected_objects, _selected_channels = _resolve_key_command_targets(
        default_mode=default_mode,
        include_shapes=include_shapes,
    )
    curves = _curves_for_key_selection(target_info, include_shapes=include_shapes)
    return target_info, _unique(curves)


def _key_selection_range(target_info, target_plugs=None, selected_objects=None, selected_channels=None):
    time_context = target_info.get("time_context")
    if time_context and time_context.mode == "graph_editor_keys" and time_context.frames:
        return time_context.start_frame, time_context.end_frame

    frames = []
    query_kwargs = {"query": True, "timeChange": True}
    if time_context and time_context.mode == "time_slider_range":
        query_kwargs["time"] = time_context.timerange

    if target_plugs:
        for plug in target_plugs:
            frames.extend(cmds.keyframe(plug, **query_kwargs) or [])
    else:
        kwargs = dict(query_kwargs)
        if selected_channels:
            kwargs["attribute"] = selected_channels
        for obj in selected_objects or []:
            frames.extend(cmds.keyframe(obj, **kwargs) or [])

    if not frames:
        return None
    return min(frames), max(frames)


def _capture_key_selection_context():
    scene_selection = cmds.ls(selection=True, long=True) or []
    key_selection = []
    try:
        selected_curves = cmds.keyframe(query=True, selected=True, name=True) or []
    except (RuntimeError, ValueError, TypeError, AttributeError, KeyError, IndexError):
        selected_curves = []

    for curve in _unique(selected_curves):
        try:
            frames = cmds.keyframe(curve, query=True, selected=True, timeChange=True) or []
        except (RuntimeError, ValueError, TypeError, AttributeError, KeyError, IndexError):
            frames = []
        key_selection.extend((curve, frame) for frame in frames)

    return scene_selection, key_selection


def _restore_key_selection_context(context):
    scene_selection, key_selection = context

    try:
        cmds.selectKey(clear=True)
    except (RuntimeError, ValueError, TypeError, AttributeError, KeyError, IndexError):
        pass

    for curve, frame in key_selection:
        try:
            if cmds.keyframe(curve, query=True, time=(frame, frame)):
                cmds.selectKey(curve, add=True, keyframe=True, time=(frame, frame))
        except (RuntimeError, ValueError, TypeError, AttributeError, KeyError, IndexError):
            continue

    try:
        existing_selection = [item for item in scene_selection if cmds.objExists(item)]
        if existing_selection:
            cmds.select(existing_selection, replace=True)
        else:
            cmds.select(clear=True)
    except (RuntimeError, ValueError, TypeError, AttributeError, KeyError, IndexError):
        pass


def _filter_curves_preserving_selection(curves, filter_name, command_label, target_info):
    selection_context = _capture_key_selection_context()
    time_kwargs = _selection_time_kwargs(target_info.get("time_context"))
    try:
        try:
            if time_kwargs:
                return cmds.filterCurve(curves, filter=filter_name, **time_kwargs)
            return cmds.filterCurve(curves, filter=filter_name)
        except (RuntimeError, TypeError) as exc:
            if time_kwargs:
                cmds.warning("{} could not run on the selected time range: {}".format(command_label, exc))
                return None
            raise
    finally:
        _restore_key_selection_context(selection_context)


def _run_key_command(
    command,
    command_name,
    default_mode="all_animation",
    **base_kwargs
):
    target_info, target_plugs, selected_objects, _selected_channels = _resolve_key_command_targets(
        default_mode=default_mode,
        include_shapes=False,
    )

    has_graph_keys = bool(target_info.get("has_graph_keys"))
    time_context = target_info.get("time_context")
    source = target_info.get("source")

    target_plugs = _unique(target_plugs)
    selected_objects = _unique(selected_objects)

    if not target_plugs and not selected_objects and not has_graph_keys:
        return wutil.make_inViewMessage("Select at least one object, channel, or key")

    with toolCommon.tool_operation(
        tool_id=command_name,
        label=toolCommon.humanize_tool_name(command_name),
        progress=False,
        undo=True,
        undo_name=toolCommon.make_undo_chunk_name(tool_id=command_name),
    ):
        kwargs = dict(base_kwargs)

        if has_graph_keys:
            kwargs.setdefault("animation", "keys")
            return command(**kwargs)

        kwargs.update(_selection_time_kwargs(time_context))

        if default_mode == "current_frame" and not _has_key_time_filter(kwargs):
            frame = cmds.currentTime(query=True)
            kwargs["time"] = (frame, frame)

        if source == "channel_box" and target_plugs:
            return _run_command_on_plugs(command, target_plugs, **kwargs)

        targets = target_plugs if _is_explicit_channel_source(source) else selected_objects
        if not targets:
            targets = target_plugs or selected_objects
        return command(targets, **kwargs)


def _has_key_time_filter(kwargs):
    return any(key in kwargs for key in ("time", "index", "float"))


def _is_explicit_channel_source(source):
    return source in (
        "channel_box",
        "graph_editor",
        "graph_editor_outliner",
    )


def _run_command_on_plugs(command, plugs, **kwargs):
    result = None
    for plug in plugs or []:
        if not plug or "." not in plug:
            continue
        node, attr = plug.rsplit(".", 1)
        result = command(node, attribute=attr, **kwargs)
    return result


def _paste_key_targets(target_plugs, selected_objects, selected_channels, **kwargs):
    if target_plugs:
        return _run_command_on_plugs(cmds.pasteKey, target_plugs, **kwargs)

    if selected_channels:
        kwargs["attribute"] = selected_channels
    return cmds.pasteKey(selected_objects, **kwargs)


def apply_smart_euler_filter(*args):
    target_info, _target_plugs, _selected_objects, _selected_channels = _resolve_key_command_targets(default_mode="all_animation")
    curves = []
    for curve in _curves_for_key_selection(target_info):
        if selectionMod.is_rotation_anim_curve(curve):
            curves.append(curve)

    if not curves:
        return wutil.make_inViewMessage("No rotation animation curves found")

    with _animation_command_context("Apply Smart Euler Filter", "apply_smart_euler_filter"):
        return _filter_curves_preserving_selection(curves, "euler", "Apply Smart Euler Filter", target_info)


def clear_animation_keys(*args):
    return _run_key_command(cmds.cutKey, "clear_animation", clear=True)


def copy_keys(*args):
    global _key_clipboard_start_frame

    target_info, target_plugs, selected_objects, selected_channels = _resolve_key_command_targets(default_mode="all_animation")
    key_range = _key_selection_range(target_info, target_plugs, selected_objects, selected_channels)
    _key_clipboard_start_frame = key_range[0] if key_range else None
    return _run_key_command(cmds.copyKey, "copy_keys", option="keys")


def cut_keys(*args):
    global _key_clipboard_start_frame

    target_info, target_plugs, selected_objects, selected_channels = _resolve_key_command_targets(default_mode="all_animation")
    key_range = _key_selection_range(target_info, target_plugs, selected_objects, selected_channels)
    _key_clipboard_start_frame = key_range[0] if key_range else None
    return _run_key_command(cmds.cutKey, "cut_keys", option="keys")


def delete_keys(*args):
    return _run_key_command(
        cmds.cutKey,
        "delete_keys",
        default_mode="current_frame",
        clear=True,
    )


def paste_keys(*args):
    target_info, target_plugs, selected_objects, selected_channels = _resolve_key_command_targets(
        default_mode="current_frame", include_shapes=False
    )
    if not target_plugs and not selected_objects:
        return wutil.make_inViewMessage("Select at least one object or channel")

    with _animation_command_context("Paste Keys", "paste_keys", default_mode="current_frame"):
        kwargs = {"option": "merge"}
        return _paste_key_targets(target_plugs, selected_objects, selected_channels, **kwargs)


def paste_keys_relative(*args):
    global _key_clipboard_start_frame

    target_info, target_plugs, selected_objects, selected_channels = _resolve_key_command_targets(
        default_mode="current_frame", include_shapes=False
    )
    if not target_plugs and not selected_objects:
        return wutil.make_inViewMessage("Select at least one object or channel")

    paste_time = target_info["time_context"].start_frame
    with _animation_command_context("Paste Keys Relative", "paste_keys_relative", default_mode="current_frame"):
        time_offset = paste_time
        if _key_clipboard_start_frame is not None:
            time_offset = paste_time - _key_clipboard_start_frame
        kwargs = {"option": "merge", "timeOffset": time_offset}
        return _paste_key_targets(target_plugs, selected_objects, selected_channels, **kwargs)


def crop_animation(*args):
    target_info, target_plugs, selected_objects, selected_channels = _resolve_key_command_targets(default_mode="all_animation")
    if not target_plugs and not selected_objects:
        return wutil.make_inViewMessage("Select at least one object or channel")

    time_context = target_info["time_context"]
    crop_range = (time_context.start_frame, time_context.end_frame)
    curves = _curves_for_key_selection(target_info)
    if not curves:
        return wutil.make_inViewMessage("No animation curves found")

    with _animation_command_context("Crop Animation", "crop_animation", timerange=crop_range):
        for curve in curves:
            frames = cmds.keyframe(curve, query=True, timeChange=True) or []
            for frame in frames:
                if frame < crop_range[0] or frame > crop_range[1]:
                    cmds.cutKey(curve, time=(frame, frame), clear=True)


def remove_redundant_keys(*args):
    target_info, _target_plugs, _selected_objects, _selected_channels = _resolve_key_command_targets(default_mode="all_animation")
    curves = _curves_for_key_selection(target_info)
    if not curves:
        return wutil.make_inViewMessage("No animation curves found")

    time_context = target_info["time_context"]
    _range = (time_context.start_frame, time_context.end_frame)

    with _animation_command_context("Remove Redundant Keys", "remove_redundant_keys", timerange=_range, tint=False):
        return _filter_curves_preserving_selection(curves, "simplify", "Remove Redundant Keys", target_info)


def _is_scoped_key_context(target_info):
    time_context = (target_info or {}).get("time_context")
    return bool(time_context and time_context.mode in ("graph_editor_keys", "time_slider_range"))


def _curve_values_for_context(curve, target_info):
    values = []
    for key_time in _key_times_for_curve_context(curve, target_info):
        try:
            key_values = cmds.keyframe(curve, time=(key_time, key_time), query=True, valueChange=True) or []
        except (RuntimeError, ValueError, TypeError, AttributeError, KeyError, IndexError):
            key_values = []
        values.extend(key_values)
    return values


def _remove_static_curve_context(curve, target_info):
    if not _is_scoped_key_context(target_info):
        cmds.delete(curve)
        return True

    removed = False
    time_context = target_info.get("time_context")
    if time_context and time_context.mode == "graph_editor_keys":
        for key_time in _selected_key_times_for_curve(curve):
            cmds.cutKey(curve, time=(key_time, key_time), clear=True)
            removed = True
        return removed

    time_kwargs = _selection_time_kwargs(time_context)
    if time_kwargs:
        cmds.cutKey(curve, clear=True, **time_kwargs)
        removed = True
    return removed


def remove_static_anim_curves(*args):
    target_info, _target_plugs, _selected_objects, _selected_channels = _resolve_key_command_targets(default_mode="all_animation")
    curves = _curves_for_key_selection(target_info)
    if not curves:
        return wutil.make_inViewMessage("No animation curves found")

    curves_to_delete = []
    for curve in curves:
        values = _curve_values_for_context(curve, target_info)
        if values and len(set(values)) == 1:
            curves_to_delete.append(curve)

    if not curves_to_delete:
        return wutil.make_inViewMessage("No static animation curves found")

    time_context = target_info["time_context"]
    _range = (time_context.start_frame, time_context.end_frame)

    with _animation_command_context("Remove Static Anim Curves", "remove_static_anim_curves", timerange=_range, tint=False):
        removed = False
        for curve in _unique(curves_to_delete):
            removed = _remove_static_curve_context(curve, target_info) or removed
        if not removed:
            return wutil.make_inViewMessage("No static animation curves found")


def reverse_animation(*args):
    target_info, _target_plugs, _selected_objects, _selected_channels = _resolve_key_command_targets(default_mode="all_animation")
    curves = _curves_for_key_selection(target_info)
    if not curves:
        return wutil.make_inViewMessage("No animation curves found")

    time_context = target_info["time_context"]
    reverse_range = (time_context.start_frame, time_context.end_frame)
    with _animation_command_context("Reverse Animation", "reverse_animation", timerange=reverse_range):
        pivot = (reverse_range[0] + reverse_range[1]) * 0.5
        for curve in curves:
            cmds.scaleKey(curve, time=reverse_range, timeScale=-1, timePivot=pivot)


def _frames_for_key_time_context(time_context):
    frames = tuple(getattr(time_context, "frames", ()) or ())
    if frames:
        return frames
    return (time_context.start_frame,)


def _curve_output_plug(curve):
    destinations = selectionMod.get_anim_curve_output_plugs([curve])
    return destinations[0] if destinations else None


def _curve_value_at_frame(curve, frame):
    try:
        values = cmds.keyframe(curve, query=True, eval=True, time=(frame, frame)) or []
        if values:
            return values[0]
    except (RuntimeError, ValueError, TypeError, AttributeError, KeyError, IndexError):
        pass

    plug = _curve_output_plug(curve)
    if plug:
        try:
            return cmds.getAttr(plug, time=frame)
        except (RuntimeError, ValueError, TypeError, AttributeError, KeyError, IndexError):
            pass
    return None


def _nearest_curve_key_time(curve, frame):
    try:
        key_times = cmds.keyframe(curve, query=True, timeChange=True) or []
    except (RuntimeError, ValueError, TypeError, AttributeError, KeyError, IndexError):
        key_times = []
    if not key_times:
        return None
    return min(key_times, key=lambda key_time: abs(key_time - frame))


def _curve_tangent_types_at_frame(curve, frame):
    source_time = frame
    try:
        key_exists = bool(cmds.keyframe(curve, query=True, time=(frame, frame)))
    except (RuntimeError, ValueError, TypeError, AttributeError, KeyError, IndexError):
        key_exists = False
    if not key_exists:
        source_time = _nearest_curve_key_time(curve, frame)
    if source_time is None:
        return None, None

    try:
        in_types = cmds.keyTangent(curve, query=True, time=(source_time, source_time), inTangentType=True) or []
        out_types = cmds.keyTangent(curve, query=True, time=(source_time, source_time), outTangentType=True) or []
    except (RuntimeError, ValueError, TypeError, AttributeError, KeyError, IndexError):
        return None, None

    return (in_types[0] if in_types else None), (out_types[0] if out_types else None)


def _set_key_on_curve_preserving_tangent(curve, frame):
    value = _curve_value_at_frame(curve, frame)
    if value is None:
        return False

    in_tangent, out_tangent = _curve_tangent_types_at_frame(curve, frame)
    cmds.setKeyframe(curve, time=(frame,), value=value)

    tangent_kwargs = {}
    if in_tangent:
        tangent_kwargs["inTangentType"] = in_tangent
    if out_tangent:
        tangent_kwargs["outTangentType"] = out_tangent
    if tangent_kwargs:
        cmds.keyTangent(curve, edit=True, time=(frame, frame), **tangent_kwargs)
    return True


def _set_selected_graph_editor_curves_current_time():
    curves = _unique(selectionMod.get_graph_editor_selected_curves())
    if not curves:
        return False
    frame = cmds.currentTime(query=True)
    keyed = False
    for curve in curves:
        keyed = _set_key_on_curve_preserving_tangent(curve, frame) or keyed
    return keyed


def set_smart_key(*args):
    target_info, target_plugs, selected_objects, selected_channels = _resolve_key_command_targets(
        default_mode="current_frame",
        include_shapes=False,
    )

    selected_objects = _unique(selected_objects)
    target_plugs = _unique(target_plugs)

    frames = _frames_for_key_time_context(target_info["time_context"])
    source = target_info.get("source")

    with _animation_command_context(
        "Set Smart Key",
        tint=False,
    ):
        keyed = _set_selected_graph_editor_curves_current_time()

        if not keyed and _is_explicit_channel_source(source) and target_plugs:
            if source == "channel_box":
                for plug in target_plugs:
                    if not plug or "." not in plug:
                        continue

                    node, attr = plug.rsplit(".", 1)

                    try:
                        for frame in frames:
                            cmds.setKeyframe(node, attribute=attr, time=(frame,))
                            keyed = True
                    except (RuntimeError, ValueError, TypeError):
                        pass
            else:
                curves = _curves_for_key_selection(target_info, include_shapes=False)
                curve_frames = frames
                if source in ("graph_editor", "graph_editor_outliner") and not target_info.get("selected_keyframes"):
                    curve_frames = (cmds.currentTime(query=True),)

                for curve in curves:
                    for frame in curve_frames:
                        keyed = _set_key_on_curve_preserving_tangent(curve, frame) or keyed

        elif not keyed:
            if not selected_objects:
                return wutil.make_inViewMessage("Select at least one object")

            curves = _curves_for_key_selection(target_info, include_shapes=False)
            for curve in curves:
                for frame in frames:
                    keyed = _set_key_on_curve_preserving_tangent(curve, frame) or keyed

            if not keyed and target_plugs:
                for plug in target_plugs:
                    if not plug or "." not in plug:
                        continue
                    node, attr = plug.rsplit(".", 1)
                    try:
                        for frame in frames:
                            cmds.setKeyframe(node, attribute=attr, time=(frame,))
                            keyed = True
                    except (RuntimeError, ValueError, TypeError):
                        pass

        if not keyed:
            return wutil.make_inViewMessage("No keyable channels found")


def set_smart_key_all_channels(*args):
    target_info, _target_plugs, selected_objects, _selected_channels = _resolve_key_command_targets(
        default_mode="current_frame",
        include_shapes=False,
    )

    selected_objects = _unique(selected_objects)

    frames = _frames_for_key_time_context(target_info["time_context"])

    with _animation_command_context(
        "Set Smart Key All Channels",
        tint=False,
    ):
        if not selected_objects:
            return wutil.make_inViewMessage("Select at least one object")

        keyed = False
        for obj in selected_objects:
            attrs = selectionMod.get_keyable_scalar_attributes(obj)
            if not attrs:
                continue

            try:
                for frame in frames:
                    cmds.setKeyframe(obj, attribute=attrs, time=(frame,))
                    keyed = True
            except (RuntimeError, ValueError, TypeError):
                pass

        if not keyed:
            return wutil.make_inViewMessage("No keyable channels found")


def _snap_curve_key(curve, key_time):
    rounded_time = round(key_time)
    if float(rounded_time) == float(key_time):
        return False

    try:
        # Sample the curve at the destination frame.  Reusing the sub-frame
        # key's value would effectively move the key and change the curve's
        # pose at the closest full frame.
        values = cmds.keyframe(curve, time=(rounded_time, rounded_time), query=True, eval=True) or []
        in_tangents = cmds.keyTangent(curve, time=(key_time,), query=True, inTangentType=True) or []
        out_tangents = cmds.keyTangent(curve, time=(key_time,), query=True, outTangentType=True) or []
    except (RuntimeError, ValueError, TypeError, AttributeError, KeyError, IndexError):
        return False

    if not values:
        return False

    try:
        # Create/replace the destination first.  Cutting the only key from an
        # anim curve can make Maya delete the curve node, leaving a stale name
        # for setKeyframe (for example, "...rotateX15").
        cmds.setKeyframe(curve, time=(rounded_time,), value=values[0])
        cmds.cutKey(curve, time=(key_time, key_time), clear=True)
    except (RuntimeError, ValueError, TypeError):
        return False

    tangent_kwargs = {}
    if in_tangents:
        tangent_kwargs["inTangentType"] = in_tangents[0]
    if out_tangents:
        tangent_kwargs["outTangentType"] = out_tangents[0]
    if tangent_kwargs:
        try:
            cmds.keyTangent(curve, time=(rounded_time,), edit=True, **tangent_kwargs)
        except (RuntimeError, ValueError, TypeError):
            # The sampled key is still valid when Maya cannot apply a tangent
            # type (for example on a curve with restricted tangent settings).
            pass
    return True


def snapKeyframes():
    target_info, _target_plugs, _selected_objects, _selected_channels = _resolve_key_command_targets(
        default_mode="all_animation",
        include_shapes=True,
    )
    curves = _curves_for_key_selection(target_info)
    if not curves:
        return wutil.make_inViewMessage("No animation curves found")

    curve_key_times = [
        (curve, list(_key_times_for_curve_context(curve, target_info)))
        for curve in curves
    ]
    work_items = sum(len(key_times) for _curve, key_times in curve_key_times)

    snapped = False
    with toolCommon.tool_operation(
        tool_id="snap",
        label="Snap Keyframes",
        progress=True,
        progress_max=work_items,
        undo=True,
        tint="context",
        default_mode="all_animation",
        tint_key="snap",
        tint_color=_timeline_tint_color("snap"),
    ) as operation:
        operation.start()
        for curve, key_times in curve_key_times:
            for key_time in key_times:
                if operation.cancelled:
                    return
                snapped = _snap_curve_key(curve, key_time) or snapped
                operation.step()

    if not snapped:
        return wutil.make_inViewMessage("No sub-frame keys found")


def shareKeys():
    # Obtener los keyframes de todas las curvas
    all_times = cmds.keyframe(query=True, timeChange=True)

    # Obtener las curvas seleccionadas
    selected_curves = cmds.keyframe(selected=True, query=True, name=True)

    # Verificar si hay al menos una curva seleccionada
    if selected_curves:
        for curve in selected_curves:
            # Obtener el valor del primer y último keyframe de la curva seleccionada
            first_frame_value = cmds.keyframe(curve, query=True, time=(all_times[0], all_times[0]), valueChange=True)
            last_frame_value = cmds.keyframe(curve, query=True, time=(all_times[-1], all_times[-1]), valueChange=True)

            # Si la curva tiene keyframes, establecer todos los keyframes con el valor del primer y último frame
            if first_frame_value and last_frame_value:
                first_frame_value = first_frame_value[0]
                last_frame_value = last_frame_value[0]

                # Crear todos los keyframes con el mismo valor del primer y último frame
                for time in all_times:
                    if time == all_times[0] or time == all_times[-1]:
                        cmds.setKeyframe(curve, time=time, value=first_frame_value)
                    else:
                        # Obtener la lista de los keyframes actuales de la curva
                        curve_times = cmds.keyframe(curve, query=True, timeChange=True)
                        if time in curve_times:
                            # Si el frame actual ya tiene un keyframe, usar su valor
                            frame_value = cmds.keyframe(curve, query=True, time=(time, time), valueChange=True)[0]
                        else:
                            # Si no, usar el valor del primer keyframe
                            frame_value = first_frame_value

                        cmds.setKeyframe(curve, time=time, value=frame_value)


def graph_match_keys():
    target_info, selected_curves = _resolve_anim_curve_tool_context()
    if len(selected_curves) < 2:
        return wutil.make_inViewMessage("Select at least two animation curves")

    source_curve = selected_curves[-1]
    source_times = _key_times_for_curve_context(source_curve, target_info)
    source_values = [
        (time, (cmds.keyframe(source_curve, query=True, time=(time, time), valueChange=True) or [None])[0])
        for time in source_times
    ]
    source_values = [(time, value) for time, value in source_values if value is not None]
    if not source_values:
        return wutil.make_inViewMessage("No source keys found")

    source_time_set = {time for time, _value in source_values}
    with _animation_command_context("Match Keys", "graph_match_keys", tint=False):
        for curve in selected_curves[:-1]:
            curve_times = set(_key_times_for_curve_context(curve, target_info))
            for frame in curve_times - source_time_set:
                cmds.cutKey(curve, time=(frame, frame), clear=True)
            for time, value in source_values:
                cmds.setKeyframe(curve, time=(time,), value=value)


def _flip_curve_context(curve, target_info):
    values = _curve_values_for_context(curve, target_info)
    if not values:
        return False

    pivot = (min(values) + max(values)) / 2.0
    time_context = target_info.get("time_context")
    if time_context and time_context.mode == "graph_editor_keys":
        flipped = False
        for key_time in _selected_key_times_for_curve(curve):
            value = (cmds.keyframe(curve, query=True, time=(key_time, key_time), valueChange=True) or [None])[0]
            if value is None:
                continue
            cmds.keyframe(curve, edit=True, time=(key_time, key_time), valueChange=pivot + (pivot - value))
            flipped = True
        return flipped

    kwargs = _selection_time_kwargs(time_context)
    cmds.scaleKey(curve, valueScale=-1, valuePivot=pivot, **kwargs)
    return True


def flipCurves():
    target_info, selected_curves = _resolve_anim_curve_tool_context()
    if not selected_curves:
        return wutil.make_inViewMessage("Select at least one animation curve")

    with _animation_command_context("Flip Curves", "graph_flip", tint=False):
        flipped = False
        for curve in selected_curves:
            flipped = _flip_curve_context(curve, target_info) or flipped
        if not flipped:
            return wutil.make_inViewMessage("No keys found")


def flipKeyGroup():
    return flipCurves()


def flipFromKeyframe():
    selectedCurves = cmds.keyframe(n=1, sl=1, q=1)

    if selectedCurves is not None:
        for piv in selectedCurves:
            pivot = cmds.keyframe(query=True, valueChange=True)[0]

        for s in selectedCurves:
            cmds.scaleKey(s, valueScale=-1, valuePivot=pivot, scaleSpecifiedKeys=1)
    else:
        cmds.warning("No keys selected")


# ------------------------------ OVERLAP


def _overlap_curves(frames_to_move, label, tint_key):
    target_info, selected_curves = _resolve_anim_curve_tool_context()
    if not selected_curves:
        return wutil.make_inViewMessage("Select animation curves, channels, or animated objects")

    time_kwargs = _selection_time_kwargs(target_info.get("time_context"))
    with _animation_command_context(label, tint_key, tint=False):
        for index, curve in enumerate(selected_curves):
            cmds.keyframe(
                curve,
                edit=True,
                includeUpperBound=True,
                relative=True,
                option="over",
                timeChange=index * frames_to_move,
                **time_kwargs
            )


def overlap_forward(*args):
    return _overlap_curves(1, "Overlap Forward", "graph_overlap_forward")


def overlap_backward(*args):
    return _overlap_curves(-1, "Overlap Backward", "graph_overlap_backward")


# __________________________________________________ Iso / Mute / Lock ____________________________________________________________#


def isolateCurve():
    # Obtén las curvas seleccionadas en el Graph Editor
    selected_objects = selectionMod.get_graph_editor_outliner_items()

    if not selected_objects:
        cmds.warning("There are not selected curves in Graph Editor")
    else:
        for s in selected_objects:
            mel.eval("isolateAnimCurve true {} {};".format(selectionMod.GRAPH_EDITOR_OUTLINER, selectionMod.GRAPH_EDITOR))


def toggleMute():
    # Obtener las curvas seleccionadas en el Graph Editor
    selected_curves = selectionMod.get_graph_editor_outliner_items()

    if selected_curves:
        for curve in selected_curves:
            # Reemplazar guiones bajos por puntos en el nombre del canal
            # curve = curve.replace("_", "")

            # Consultar si el canal está en mute
            is_muted = cmds.mute(curve, q=True)

            if is_muted:
                # Desactivar el mute del canal
                cmds.mute(curve, disable=True)
            else:
                # Activar el mute del canal
                cmds.mute(curve)


def toggleLock():
    # Obtén las curvas seleccionadas en el Graph Editor
    selected_objects = selectionMod.get_graph_editor_outliner_items()

    # Si no hay objetos seleccionados, lanza un error
    if not selected_objects:
        cmds.warning("There are not selected curves in Graph Editor")
        return

    # Por cada objeto seleccionado
    for obj in selected_objects:
        if selectionMod.is_anim_curve(obj):
            anim_curves = [obj]
        else:
            anim_curves = selectionMod.get_anim_curves_for_nodes([obj], include_shapes=True)

        # Si no hay curvas de animación, lanza un error y continua con el siguiente objeto
        if not anim_curves:
            cmds.warning(f"No animation curves found for {obj}")
            continue

        # Por cada curva de animación
        for curve in anim_curves:
            # Obtén el estado actual de bloqueo (lock) de la curva
            is_locked = cmds.getAttr(curve + ".ktv", lock=True)

            # Si la curva está bloqueada (locked), desbloquéala (unlock).
            # Si no está bloqueada (unlocked), blóquela (lock).
            cmds.setAttr(curve + ".ktv", lock=not is_locked)


# _____________________________________________________ Resets _______________________________________________________________#


def save_default_values(*args):
    # Obtener objetos seleccionados
    objetos_seleccionados = selectionMod.get_selected_objects(long=True)

    json_file_path = general.get_set_default_data_file()

    # Asegurar que la carpeta donde se guardará el archivo exista
    os.makedirs(os.path.dirname(json_file_path), exist_ok=True)

    # Leer datos existentes del archivo JSON, si existe
    if os.path.exists(json_file_path):
        with open(json_file_path, "r") as file:
            data = json.load(file)
    else:
        data = {}

    for obj in objetos_seleccionados:
        # Extraer el namespace y el nombre corto del objeto
        partes = obj.split(":")
        namespace = partes[0] if len(partes) > 1 else "default"
        nombre_corto = partes[-1]

        # Agregar namespace al diccionario si no existe
        if namespace not in data:
            data[namespace] = {}

        # Obtener atributos claveables que no estén ocultos o bloqueados
        atributos = cmds.listAttr(obj, keyable=True, unlocked=True, visible=True) or []

        # Actualizar o agregar valores de los atributos, excluyendo el atributo "tag"
        for attr in atributos:
            if attr == "tag":
                continue  # Ignorar el atributo "tag"
            atributo_completo = f"{nombre_corto}.{attr}"
            valor = cmds.getAttr(f"{obj}.{attr}")
            data[namespace][atributo_completo] = valor

    # Guardar los datos actualizados en un archivo JSON
    with open(json_file_path, "w") as file:
        json.dump(data, file, indent=4)

    wutil.make_inViewMessage("Default values saved")


def restore_default_data(*args):
    json_file_path = general.get_set_default_data_file()

    # Verificar si el archivo existe y vaciar su contenido
    if os.path.exists(json_file_path):
        with open(json_file_path, "w") as file:
            json.dump({}, file)  # Escribe un diccionario vacío en el archivo

        cmds.warning("All default values restored")
    else:
        return wutil.make_inViewMessage("No default values found to restore")


def remove_default_values_for_selected_object(*args):
    json_file_path = general.get_set_default_data_file()

    # Leer datos existentes del archivo JSON, si existe
    if os.path.exists(json_file_path):
        with open(json_file_path, "r") as file:
            data = json.load(file)
    else:
        return wutil.make_inViewMessage("No default values found to remove")

    # Obtener objetos seleccionados
    objetos_seleccionados = selectionMod.get_selected_objects(long=True)

    for obj in objetos_seleccionados:
        # Extraer el namespace y el nombre corto del objeto
        partes = obj.split(":")
        namespace = partes[0] if len(partes) > 1 else "default"
        nombre_corto = partes[-1]

        # Eliminar la información del objeto del JSON
        if namespace in data:
            # Crear una lista de claves a eliminar para evitar modificar el diccionario durante la iteración
            keys_to_remove = [key for key in data[namespace] if key.startswith(nombre_corto + "")]

            for key in keys_to_remove:
                del data[namespace][key]

            # Si el namespace queda vacío, eliminarlo también
            if not data[namespace]:
                del data[namespace]

    # Guardar los datos actualizados en un archivo JSON
    with open(json_file_path, "w") as file:
        json.dump(data, file, indent=4)

    wutil.make_inViewMessage("Default values removed")


def default_object_values(default_translations=False, default_rotations=False, default_scales=False):
    default_trs = default_translations and default_rotations and default_scales
    has_transform_filter = any((default_translations, default_rotations, default_scales))
    translation_attrs = {"translate", "translateX", "translateY", "translateZ"}
    rotation_attrs = {"rotate", "rotateX", "rotateY", "rotateZ"}
    scale_attrs = {"scale", "scaleX", "scaleY", "scaleZ"}

    def _matches_requested_default_attrs(attr):
        if not has_transform_filter:
            return True
        return (
            (default_translations and attr in translation_attrs)
            or (default_rotations and attr in rotation_attrs)
            or (default_scales and attr in scale_attrs)
        )

    if default_trs:
        tool_id = "default_trs"
    elif default_scales:
        tool_id = "default_scales"
    elif default_rotations:
        tool_id = "default_rotations"
    elif default_translations:
        tool_id = "default_translations"
    else:
        tool_id = "default_object_values"

    operation_context = None
    selected_objects = []

    try:
        json_file_path = general.get_set_default_data_file()

        # Leer datos del archivo JSON si existe
        if os.path.exists(json_file_path):
            with open(json_file_path, "r") as file:
                data = json.load(file)
        else:
            data = {}

        target_info = resolve_tool_targets(default_mode="current_frame", ordered_selection=True, long_names=True)
        time_context = target_info["time_context"]
        operation_context = toolCommon.tool_operation(
            tool_id=tool_id,
            label=toolCommon.humanize_tool_name(tool_id),
            progress=True,
            progress_max=1,
            undo=True,
            undo_name=toolCommon.make_undo_chunk_name(tool_id=tool_id),
            tint="context" if time_context.mode in ("graph_editor_keys", "time_slider_range") else "none",
            default_mode="current_frame",
            tint_key="default_object_values",
            tint_color=_timeline_tint_color("default_object_values"),
        )
        operation_context.__enter__()

        selected_objects = target_info["target_objects"]
        target_plugs = target_info["target_plugs"]

        if time_context.mode == "graph_editor_keys":
            for curve, frame in target_info["selected_keyframes"]:
                target_plugs = cmds.listConnections(curve + ".output", plugs=True, source=False, destination=True) or []
                if not target_plugs:
                    continue
                obj, attr = target_plugs[0].split(".", 1)
                if not _matches_requested_default_attrs(attr):
                    continue
                default_value = _get_default_value_for_attribute(obj, attr, data)
                if default_value is None:
                    continue
                try:
                    cmds.keyframe(curve, edit=True, valueChange=default_value, time=(frame, frame))
                except Exception as e:
                    print(f"Could not process the attribute {attr} on {obj}: {str(e)}")
            return

        for attr_plug in target_plugs:
            if "." not in attr_plug:
                continue
            obj, attr = attr_plug.split(".", 1)
            if not _matches_requested_default_attrs(attr):
                continue

            try:
                is_locked = cmds.getAttr(attr_plug, lock=True)
                if is_locked:
                    continue

                connections = cmds.listConnections(attr_plug, source=True, destination=False, plugs=True)
                if connections:
                    node_type = cmds.nodeType(connections[0].split(".")[0])
                    if node_type not in ["animCurveTL", "animCurveTA", "animCurveTT", "animCurveTU"]:
                        cmds.disconnectAttr(connections[0], attr_plug)

                default_value = _get_default_value_for_attribute(obj, attr, data)
                if default_value is None:
                    continue

                if time_context.mode == "current_frame":
                    cmds.setAttr(attr_plug, default_value)
                    continue

                keyframes = cmds.keyframe(attr_plug, query=True, time=(time_context.start_frame, time_context.end_frame)) or []
                for frame in sorted(set(int(k) for k in keyframes)):
                    cmds.setKeyframe(obj, attribute=attr, time=(frame,), value=default_value)
            except Exception as e:
                print(f"Could not process the attribute {attr} on {obj}: {str(e)}")
                continue

    except Exception as e:
        cmds.warning("Error during default: {}".format(str(e)))
    finally:
        if selected_objects:
            cmds.select(selected_objects, replace=True)
        else:
            cmds.select(clear=True)
        if operation_context:
            try:
                operation_context.__exit__(None, None, None)
            except Exception:
                pass


def get_default_value(node):
    type = cmds.nodeType(node)

    if "animCurve" in type:
        target = cmds.listConnections(node + ".output", plugs=True, destination=False, source=True)
        if target:
            object, attr = target[0].split("")
        else:
            object, attr = None, None
    else:
        object, attr = node.split("")

    if not object or not attr:
        return None

    if cmds.attributeQuery(attr, node=object, exists=True):
        default_value = cmds.attributeQuery(attr, node=object, listDefault=True)[0]
        return default_value

    return None


def get_default_value_main():
    selected_curves = selectionMod.get_graph_editor_outliner_items()

    if selected_curves:
        for curve in selected_curves:
            selected_keyframes = cmds.keyframe(curve, query=True, selected=True, timeChange=True)
            if selected_keyframes:
                for keyframe in selected_keyframes:
                    default_value = get_default_value(curve)
                    if default_value is not None:
                        cmds.keyframe(curve, edit=True, valueChange=default_value, time=(keyframe, keyframe))


# _____________________________________________________ select object from selected curve _______________________________________________________________#


def get_namespace_from_selection(*args):
    # Obtener el namespace del objeto seleccionado (si existe)
    selected_objects = selectionMod.get_selected_objects()
    if selected_objects:
        object_name = selected_objects[0]
        if ":" in object_name:
            return object_name.split(":")[0]
    return None


def select_objects_from_selected_curves(*args):
    # Obtener los nombres de las curvas seleccionadas en el Graph Editor
    selected_curves = cmds.keyframe(query=True, name=True, selected=True)
    if not selected_curves:
        return

    # Obtener el namespace del objeto seleccionado
    namespace = get_namespace_from_selection()

    # Obtener y seleccionar los objetos asociados a las curvas seleccionadas
    selected_objects = set()
    for curve_name in selected_curves:
        object_name = "_".join(curve_name.split("_")[:-1])  # Eliminar el sufijo "_rotateY"

        # Agregar el namespace al nombre del objeto si existe
        if namespace:
            object_name_with_namespace = f"{namespace}:{object_name}"
            if cmds.objExists(object_name_with_namespace):
                object_name = object_name_with_namespace

        if cmds.objExists(object_name):
            selected_objects.add(object_name)

    if selected_objects:
        cmds.selectKey(selected_curves, add=True)  # Seleccionar las claves en el Graph Editor
        mel.eval("isolateAnimCurve true {} {};".format(selectionMod.GRAPH_EDITOR_OUTLINER, selectionMod.GRAPH_EDITOR))
        cmds.select(list(selected_objects), replace=True)  # Seleccionar los objetos en la vista 3D


# _____________________________ Patrones Mirror ______________________________________


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


# __________ Funcion para buscar control opuesto ___________________________________


def find_opposite_name(name):
    global MIRROR_PATTERNS
    # Divide el nombre en partes (namespace y nombre del control)
    namespace, _, control_name = name.rpartition(":")

    for pattern, opposite_pattern in MIRROR_PATTERNS:
        if pattern in control_name:
            new_control_name = control_name.replace(pattern, opposite_pattern, 1)
            possible_opposite_name = f"{namespace}:{new_control_name}" if namespace else new_control_name
            if cmds.objExists(possible_opposite_name):
                return possible_opposite_name

    return None


# ___________________________ SELECT OPPOSITE _____________________________________

def selectOpposite(*args):
    global MIRROR_PATTERNS

    selected_objects = selectionMod.get_selected_objects()
    opposite_controls = []

    for obj in selected_objects:
        opposite_obj = find_opposite_name(obj)
        if opposite_obj and cmds.objExists(opposite_obj):
            opposite_controls.append(opposite_obj)

    if opposite_controls:
        cmds.select(opposite_controls)


def addSelectOpposite(*args):
    global MIRROR_PATTERNS

    selected_objects = selectionMod.get_selected_objects()
    opposite_controls = []

    for obj in selected_objects:
        opposite_obj = find_opposite_name(obj)
        if opposite_obj and cmds.objExists(opposite_obj):
            opposite_controls.append(opposite_obj)

    if opposite_controls:
        cmds.select(opposite_controls, add=True)


# ___________________________ Copy Opposite _____________________________________


def copyOpposite(*args):
    operation_context = None
    try:
        selected_objects = selectionMod.get_selected_objects()
        operation_context = toolCommon.tool_operation(
            tool_id="copy_opposite",
            label="Copy Opposite",
            progress=True,
            progress_max=len(selected_objects),
            undo=True
        )
        operation_context.__enter__()
        operation_context.start()
        mirror_exceptions_file_path = general.get_mirror_exceptions_file()
        ATTRIBUTES_TO_IGNORE = {"tag"}

        def load_exceptions(file_path):
            if os.path.exists(file_path):
                with open(file_path, "r") as file:
                    return json.load(file)
            else:
                return {}

        exceptions = load_exceptions(mirror_exceptions_file_path)

        def apply_exception(control, attr, value):
            control_name = control.rsplit(":", 1)[-1]
            if control_name in exceptions and attr in exceptions[control_name]:
                exception_type = exceptions[control_name][attr]
                if exception_type == "invert":
                    return -value
            return value

        def replace_pattern_in_attribute(attr):
            for from_pattern, to_pattern in MIRROR_PATTERNS:
                if from_pattern in attr:
                    return attr.replace(from_pattern, to_pattern)
            return attr

        for obj in selected_objects:
            if operation_context.cancelled:
                break
            opposite_obj = find_opposite_name(obj)

            # Comprobamos si el objeto opuesto es válido y existe
            if opposite_obj and cmds.objExists(opposite_obj):
                keyable_attrs = cmds.listAttr(obj, keyable=True)

                for attr in keyable_attrs:
                    if attr in ATTRIBUTES_TO_IGNORE:
                        continue

                    opposite_attr = replace_pattern_in_attribute(attr)

                    if not cmds.getAttr(f"{opposite_obj}.{opposite_attr}", lock=True):
                        try:
                            current_value = cmds.getAttr(f"{obj}.{attr}")
                            current_value = apply_exception(obj, attr, current_value)
                            cmds.setAttr(f"{opposite_obj}.{opposite_attr}", current_value)
                        except Exception as e:
                            import TheKeyMachine.mods.reportMod as report

                            report.report_detected_exception(e, context="copy opposite attribute compile")
            operation_context.step()
    except Exception as e:
        cmds.warning("Error during copy: {}".format(str(e)))
    finally:
        if operation_context:
            try:
                operation_context.__exit__(None, None, None)
            except Exception:
                pass


# ________________________________________________________________ MIRROR _______________________________________________________________________ #


def load_exceptions():
    mirror_exceptions_file_path = general.get_mirror_exceptions_file()
    if os.path.exists(mirror_exceptions_file_path):
        with open(mirror_exceptions_file_path, "r") as file:
            return json.load(file)
    else:
        return {}


def mirror(*args):
    operation_context = None
    try:
        selected_controls = selectionMod.get_selected_objects()
        if not selected_controls:
            return wutil.make_inViewMessage("Select at least one object")

        operation_context = toolCommon.tool_operation(
            tool_id="mirror",
            label="Mirror",
            progress=True,
            progress_max=len(selected_controls),
            undo=True,
            tint="context",
            default_mode="current_frame",
            tint_key="mirror",
            tint_color=_timeline_tint_color("mirror"),
        )
        operation_context.__enter__()
        operation_context.start()
        global MIRROR_PATTERNS
        mirror_exceptions_file_path = general.get_mirror_exceptions_file()

        ATTRIBUTES_TO_IGNORE = {"tag"}

        # Cargar excepciones
        def load_exceptions(file_path):
            if os.path.exists(file_path):
                with open(file_path, "r") as file:
                    return json.load(file)
            else:
                return {}

        exceptions = load_exceptions(mirror_exceptions_file_path)

        def find_pattern_in_name(name, patterns):
            for pattern in patterns:
                if pattern in name:
                    return True
            return False

        def is_attribute_modifiable(control, attr):
            return cmds.getAttr(f"{control}.{attr}", settable=True)

        def find_opposite_name(name):
            # Divide el nombre en partes (namespace y nombre del control)
            namespace, _, control_name = name.rpartition(":")

            for pattern, opposite_pattern in MIRROR_PATTERNS:
                # Revisa si el patrón está en el nombre del control
                if pattern in control_name:
                    # Realiza el reemplazo solo para la primera aparición del patrón
                    new_control_name = control_name.replace(pattern, opposite_pattern, 1)
                    possible_opposite_name = f"{namespace}:{new_control_name}" if namespace else new_control_name
                    # print(f"Intentando reemplazar {pattern} por {opposite_pattern} en {control_name}, resultado: {possible_opposite_name}")  # Impresión de depuración
                    if cmds.objExists(possible_opposite_name):
                        return possible_opposite_name

            return None

        def apply_exception(control, attr, value):
            # Obtén el nombre del control sin el namespace
            control_name = control.rsplit(":", 1)[-1]

            if control_name in exceptions and attr in exceptions[control_name]:
                exception_type = exceptions[control_name][attr]
                if exception_type == "invert":
                    return -value
                elif exception_type == "keep":
                    return value  # Mantener el mismo valor
            return value

        def swap_control_values(control1, control2):
            if not cmds.objExists(control1):
                return

            attrs_to_swap = cmds.listAttr(control1, keyable=True)
            if not attrs_to_swap:
                return

            for attr in attrs_to_swap:
                if attr in ATTRIBUTES_TO_IGNORE or not is_attribute_modifiable(control1, attr):
                    continue

                try:
                    value1 = cmds.getAttr(f"{control1}.{attr}")

                    # Aplicar excepciones si es necesario
                    value1 = apply_exception(control1, attr, value1)

                    if control2 and cmds.objExists(control2) and is_attribute_modifiable(control2, attr):
                        value2 = cmds.getAttr(f"{control2}.{attr}")
                        value2 = apply_exception(control2, attr, value2)

                        cmds.setAttr(f"{control2}.{attr}", value1)
                        cmds.setAttr(f"{control1}.{attr}", value2)
                    else:  # Solo un control (central o único)
                        # Verificar si hay excepción para este control y atributo
                        control_name = control1.rsplit(":", 1)[-1]
                        if control_name in exceptions and attr in exceptions[control_name]:
                            exception_type = exceptions[control_name][attr]
                            if exception_type == "invert":
                                cmds.setAttr(f"{control1}.{attr}", value1 * 1)

                        else:
                            # Invertir solo los atributos específicos si no hay excepciones
                            if attr in ["translateX", "rotateZ", "rotateY"]:
                                cmds.setAttr(f"{control1}.{attr}", value1 * -1)

                except Exception as e:
                    cmds.warning(f"Could not process the attribute {attr} on {control1}: {str(e)}")

        def mirror_controls():
            processed_controls = set()

            for control in selected_controls:
                if operation_context and operation_context.cancelled:
                    break
                if control in processed_controls:
                    if operation_context:
                        operation_context.step()
                    continue

                opposite_name = find_opposite_name(control)
                if opposite_name:
                    # Si el control opuesto no está seleccionado, aún así procede con el espejado
                    swap_control_values(control, opposite_name if cmds.objExists(opposite_name) else None)
                    processed_controls.add(control)
                    if opposite_name:
                        processed_controls.add(opposite_name)
                else:
                    # Tratar como control central o único si no se encuentra un opuesto
                    swap_control_values(control, None)
                    processed_controls.add(control)
                
                if operation_context:
                    operation_context.step()

        mirror_controls()
    except Exception as e:
        cmds.warning("Error during mirroring: {}".format(str(e)))
    finally:
        if operation_context:
            try:
                operation_context.__exit__(None, None, None)
            except Exception:
                pass


# ------------------------------- mirror to opposite


def mirror_to_opposite(*args):
    global MIRROR_PATTERNS
    mirror_exceptions_file_path = general.get_mirror_exceptions_file()

    ATTRIBUTES_TO_IGNORE = {"tag"}

    # Cargar excepciones
    def load_exceptions(file_path):
        if os.path.exists(file_path):
            with open(file_path, "r") as file:
                return json.load(file)
        else:
            return {}

    exceptions = load_exceptions(mirror_exceptions_file_path)

    def find_pattern_in_name(name, patterns):
        for pattern in patterns:
            if pattern in name:
                return True
        return False

    def is_attribute_modifiable(control, attr):
        return cmds.getAttr(f"{control}.{attr}", settable=True)

    def find_opposite_name(name):
        # Divide el nombre en partes (namespace y nombre del control)
        namespace, _, control_name = name.rpartition(":")

        for pattern, opposite_pattern in MIRROR_PATTERNS:
            # Revisa si el patrón está en el nombre del control
            if pattern in control_name:
                # Realiza el reemplazo solo para la primera aparición del patrón
                new_control_name = control_name.replace(pattern, opposite_pattern, 1)
                possible_opposite_name = f"{namespace}:{new_control_name}" if namespace else new_control_name
                # print(f"Intentando reemplazar {pattern} por {opposite_pattern} en {control_name}, resultado: {possible_opposite_name}")  # Impresión de depuración
                if cmds.objExists(possible_opposite_name):
                    return possible_opposite_name

        return None

    def apply_exception(control, attr, value):
        # Obtén el nombre del control sin el namespace
        control_name = control.rsplit(":", 1)[-1]

        if control_name in exceptions and attr in exceptions[control_name]:
            exception_type = exceptions[control_name][attr]
            if exception_type == "invert":
                return -value
        return value

    def swap_control_values(control1, control2):
        if not cmds.objExists(control1):
            return

        attrs_to_swap = cmds.listAttr(control1, keyable=True)
        if not attrs_to_swap:
            return

        for attr in attrs_to_swap:
            if attr in ATTRIBUTES_TO_IGNORE or not is_attribute_modifiable(control1, attr):
                continue

            try:
                value1 = cmds.getAttr(f"{control1}.{attr}")

                # Aplicar excepciones si es necesario
                modified_value1 = apply_exception(control1, attr, value1)

                if control2 and cmds.objExists(control2) and is_attribute_modifiable(control2, attr):
                    # Aplicar los valores modificados de control1 a control2
                    cmds.setAttr(f"{control2}.{attr}", modified_value1)
                else:  # Solo un control (central o único)
                    # Verificar si hay excepción para este control y atributo
                    control_name = control1.rsplit(":", 1)[-1]
                    if control_name in exceptions and attr in exceptions[control_name]:
                        exception_type = exceptions[control_name][attr]
                        if exception_type == "invert":
                            cmds.setAttr(f"{control1}.{attr}", modified_value1)
                    else:
                        # Invertir solo los atributos específicos si no hay excepciones
                        if attr in ["translateX", "rotateZ", "rotateY"]:
                            cmds.setAttr(f"{control1}.{attr}", modified_value1)

            except Exception as e:
                cmds.warning(f"Could not process the attribute {attr} on {control1}: {str(e)}")

    def mirror_controls():
        selected_controls = selectionMod.get_selected_objects()

        if not selected_controls:
            return wutil.make_inViewMessage("Select at least one object")

        processed_controls = set()

        for control in selected_controls:
            if control in processed_controls:
                continue

            opposite_name = find_opposite_name(control)
            if opposite_name:
                # Si el control opuesto no está seleccionado, aún así procede con el espejado
                swap_control_values(control, opposite_name if cmds.objExists(opposite_name) else None)
                processed_controls.add(control)
                if opposite_name:
                    processed_controls.add(opposite_name)
            else:
                # Tratar como control central o único si no se encuentra un opuesto
                swap_control_values(control, None)
                processed_controls.add(control)

    mirror_controls()


def _mirror_token_side(token):
    clean = str(token or "").strip("_").lower()
    if clean in {"r", "rt", "rg", "rf", "right"}:
        return "right"
    if clean in {"l", "lf", "left"}:
        return "left"
    return None


def _mirror_control_side(control):
    _namespace, _sep, control_name = control.rpartition(":")
    for pattern, _opposite_pattern in MIRROR_PATTERNS:
        if pattern in control_name:
            return _mirror_token_side(pattern)
    return None


def _load_mirror_exceptions():
    mirror_exceptions_file_path = general.get_mirror_exceptions_file()
    if os.path.exists(mirror_exceptions_file_path):
        try:
            with open(mirror_exceptions_file_path, "r") as file:
                return json.load(file)
        except Exception:
            return {}
    return {}


def _mirror_exception_value(exceptions, control, attr, value):
    control_name = control.rsplit(":", 1)[-1]
    exception_type = (exceptions.get(control_name) or {}).get(attr)
    if exception_type == "invert":
        return -value
    return value


def _mirror_keyable_attrs(control):
    return [attr for attr in (cmds.listAttr(control, keyable=True) or []) if attr != "tag"]


def _attr_settable(control, attr):
    try:
        return cmds.objExists(f"{control}.{attr}") and cmds.getAttr(f"{control}.{attr}", settable=True)
    except Exception:
        return False


def _mirror_current_values(target_side=None, operation=None):
    selected_controls = selectionMod.get_selected_objects()
    if not selected_controls:
        return wutil.make_inViewMessage("Select at least one object")

    exceptions = _load_mirror_exceptions()
    copied = 0

    for source in selected_controls:
        if operation and operation.cancelled:
            break
        if target_side and _mirror_control_side(source) == target_side:
            if operation:
                operation.step()
            continue

        target = find_opposite_name(source)
        if not target or not cmds.objExists(target):
            if operation:
                operation.step()
            continue
        if target_side and _mirror_control_side(target) != target_side:
            if operation:
                operation.step()
            continue

        for attr in _mirror_keyable_attrs(source):
            if not _attr_settable(source, attr) or not _attr_settable(target, attr):
                continue
            try:
                value = cmds.getAttr(f"{source}.{attr}")
                cmds.setAttr(f"{target}.{attr}", _mirror_exception_value(exceptions, source, attr, value))
                copied += 1
            except Exception as e:
                cmds.warning(f"Could not mirror {source}.{attr} to {target}: {str(e)}")
        
        if operation:
            operation.step()

    if not copied:
        cmds.warning("No mirrorable opposite controls or attributes found")
    return copied


def mirror_to_right(*args):
    selected_controls = selectionMod.get_selected_objects()
    with toolCommon.tool_operation(
        tool_id="mirror_to_right",
        label="Mirror To Right",
        progress=True,
        progress_max=len(selected_controls) if selected_controls else 0,
        undo=True,
        tint="context",
        default_mode="current_frame",
        tint_key="mirror_to_right",
        tint_color=_timeline_tint_color("mirror_to_right"),
    ) as operation:
        operation.start()
        return _mirror_current_values(target_side="right", operation=operation)


def mirror_to_left(*args):
    selected_controls = selectionMod.get_selected_objects()
    with toolCommon.tool_operation(
        tool_id="mirror_to_left",
        label="Mirror To Left",
        progress=True,
        progress_max=len(selected_controls) if selected_controls else 0,
        undo=True,
        tint="context",
        default_mode="current_frame",
        tint_key="mirror_to_left",
        tint_color=_timeline_tint_color("mirror_to_left"),
    ) as operation:
        operation.start()
        return _mirror_current_values(target_side="left", operation=operation)


def mirror_all_keys(*args):
    selected_controls = selectionMod.get_selected_objects()
    if not selected_controls:
        return wutil.make_inViewMessage("Select at least one object")

    exceptions = _load_mirror_exceptions()
    time_context = timelineWidgets.resolve_time_context(default_mode="all_animation")
    mirrored_data = {
        ANIMATION_META_KEY: {
            "type": "animation",
            "version": ANIMATION_SCHEMA_VERSION,
            "range": None,
        },
        ANIMATION_CONTROLS_KEY: {},
    }
    key_count = 0
    processed_controls = set()

    with _copy_paste_operation(
        "mirror_all_keys",
        "Animation Mirrored",
        undo=True,
        tint="range",
        progress=True,
        progress_max=len(selected_controls),
    ) as state:
        operation = state["operation"]
        operation.start()
        for source in selected_controls:
            if operation.cancelled:
                break
            if source in processed_controls:
                operation.step()
                continue
            target = find_opposite_name(source)
            if not target or not cmds.objExists(target):
                operation.step()
                continue
            processed_controls.add(source)
            processed_controls.add(target)

            target_channels = {}
            for attr in _mirror_keyable_attrs(source):
                if not _attr_settable(source, attr) or not _attr_settable(target, attr):
                    continue
                plug = f"{source}.{attr}"
                channel_data = _query_layered_anim_channel_data(plug, time_context)
                if not channel_data.get(ANIMATION_FRAME_KEY) and not channel_data.get(ANIMATION_LAYERS_KEY):
                    continue
                target_channels[attr] = _transform_channel_values(
                    channel_data,
                    lambda value, node=source, channel=attr: _mirror_exception_value(exceptions, node, channel, value),
                )

            if target_channels:
                key_count += _apply_animation_channels_to_targets([target], target_channels, replace=True)
                mirrored_data[ANIMATION_CONTROLS_KEY][target] = target_channels

            operation.step()

        if key_count:
            state["timerange"] = _animation_data_timerange(mirrored_data)
            state["success"] = True
        else:
            cmds.warning("No mirrorable animation keys found")


# _____________________________________ add exception


def add_mirror_invert_exception(*args):
    def get_long_name(obj, short_name):
        """Obtiene el nombre largo del atributo a partir de su nombre corto."""
        return cmds.attributeQuery(short_name, node=obj, longName=True)

    def add_exceptions_to_json(selected_controls, selected_channels, json_path):
        # Asegurar que la carpeta donde se guardará el archivo exista
        os.makedirs(os.path.dirname(json_path), exist_ok=True)

        # Leer datos existentes del archivo JSON, si existe
        if os.path.exists(json_path):
            with open(json_path, "r") as file:
                exceptions = json.load(file)
        else:
            exceptions = {}

        # Añade las nuevas excepciones
        for control in selected_controls:
            control_name = control.rsplit(":", 1)[-1]
            if control_name not in exceptions:
                exceptions[control_name] = {}
            for channel in selected_channels:
                long_name = get_long_name(control, channel)
                exceptions[control_name][long_name] = "invert"

        # Guarda las excepciones actualizadas en el archivo JSON
        with open(json_path, "w") as file:
            json.dump(exceptions, file, indent=4)

    def create_mirror_exception():
        mirror_exceptions_file_path = general.get_mirror_exceptions_file()
        selected_controls = selectionMod.get_selected_objects()
        selected_channels = selectionMod.get_selected_channels()

        if selected_controls and selected_channels:
            add_exceptions_to_json(selected_controls, selected_channels, mirror_exceptions_file_path)
            cmds.warning("Exception created")
        else:
            wutil.make_inViewMessage("Select controls and channels to create an exception")

    create_mirror_exception()


def add_mirror_keep_exception(*args):
    def get_long_name(obj, short_name):
        """Obtiene el nombre largo del atributo a partir de su nombre corto."""
        return cmds.attributeQuery(short_name, node=obj, longName=True)

    def add_exceptions_to_json(selected_controls, selected_channels, json_path):
        # Asegurar que la carpeta donde se guardará el archivo exista
        os.makedirs(os.path.dirname(json_path), exist_ok=True)

        # Leer datos existentes del archivo JSON, si existe
        if os.path.exists(json_path):
            with open(json_path, "r") as file:
                exceptions = json.load(file)
        else:
            exceptions = {}

        # Añade las nuevas excepciones
        for control in selected_controls:
            control_name = control.rsplit(":", 1)[-1]
            if control_name not in exceptions:
                exceptions[control_name] = {}
            for channel in selected_channels:
                long_name = get_long_name(control, channel)
                exceptions[control_name][long_name] = "keep"

        # Guarda las excepciones actualizadas en el archivo JSON
        with open(json_path, "w") as file:
            json.dump(exceptions, file, indent=4)

    def create_mirror_exception():
        mirror_exceptions_file_path = general.get_mirror_exceptions_file()
        selected_controls = selectionMod.get_selected_objects()
        selected_channels = selectionMod.get_selected_channels()

        if selected_controls and selected_channels:
            add_exceptions_to_json(selected_controls, selected_channels, mirror_exceptions_file_path)
            cmds.warning("Exception created")
        else:
            wutil.make_inViewMessage("Select controls and channels to create an exception")

    create_mirror_exception()


# _____________________________________ remove exception


def remove_mirror_invert_exception(*args):
    def get_long_name(obj, short_name):
        """Obtiene el nombre largo del atributo a partir de su nombre corto."""
        return cmds.attributeQuery(short_name, node=obj, longName=True)

    def remove_exceptions_from_json(selected_controls, selected_channels, json_path):
        if os.path.exists(json_path):
            with open(json_path, "r") as file:
                exceptions = json.load(file)
        else:
            exceptions = {}

        # Elimina las excepciones para los controles y canales seleccionados
        for control in selected_controls:
            # Obtén el nombre del control sin el namespace
            control_name = control.rsplit(":", 1)[-1]

            if control_name in exceptions:
                for channel in selected_channels:
                    long_name = get_long_name(control, channel)
                    if long_name in exceptions[control_name]:
                        del exceptions[control_name][long_name]

        # Guarda las excepciones actualizadas en el archivo JSON
        with open(json_path, "w") as file:
            json.dump(exceptions, file, indent=4)

    def remove_mirror_exceptions():
        mirror_exceptions_file_path = general.get_mirror_exceptions_file()
        selected_controls = selectionMod.get_selected_objects()
        selected_channels = selectionMod.get_selected_channels()

        if selected_controls and selected_channels:
            remove_exceptions_from_json(selected_controls, selected_channels, mirror_exceptions_file_path)
            print("Exception removed")
        else:
            wutil.make_inViewMessage("Select controls and channels to remove exceptions")

    remove_mirror_exceptions()


# ______________________________________________________COPY PASTE ANIMATION ______________________________________________________________________________#


def _load_copy_paste_json(json_file_path, missing_warning):
    """Load JSON from an explicit file path (kept for internal use)."""
    return clipboard.load_raw(json_file_path, missing_warning)


def _load_pose_json():
    return clipboard.load("pose", "No pose file found. Please copy pose first")


def _save_copy_paste_json(json_file_path, data):
    """Save JSON to an explicit file path (kept for internal use)."""
    os.makedirs(os.path.dirname(json_file_path), exist_ok=True)
    with open(json_file_path, "w", encoding="utf-8") as json_file:
        json.dump(data, json_file, indent=4)


def _copy_paste_file_dialog(caption, file_mode):
    result = cmds.fileDialog2(fileMode=file_mode, caption=caption, fileFilter="JSON Files (*.json)")
    return result[0] if result else None


def _export_copy_paste_file(slot_or_path, caption):
    """Export clipboard slot (or explicit path) to a user-chosen file."""
    # If it looks like a slot key, delegate to clipboard.export_dialog
    if slot_or_path in ("animation", "pose", "worldspace", "worldspace_frame", "copy_link", "temp_pivot"):
        return clipboard.export_dialog(slot_or_path, caption)
    # Legacy: explicit file path
    if not os.path.exists(slot_or_path):
        return wutil.make_inViewMessage("No copied data found")
    target_path = _copy_paste_file_dialog(caption, 0)
    if not target_path:
        return None
    if not target_path.lower().endswith(".json"):
        target_path += ".json"
    os.makedirs(os.path.dirname(target_path), exist_ok=True)
    shutil.copyfile(slot_or_path, target_path)
    return wutil.make_inViewMessage("File exported")


def _import_copy_paste_file(slot_or_path, caption):
    """Import a user-chosen file into clipboard slot (or explicit path)."""
    if slot_or_path in ("animation", "pose", "worldspace", "worldspace_frame", "copy_link", "temp_pivot"):
        return clipboard.import_dialog(slot_or_path, caption)
    source_path = _copy_paste_file_dialog(caption, 1)
    if not source_path:
        return None
    data = clipboard.load_raw(source_path, "Could not import file")
    if data is None:
        return None
    _save_copy_paste_json(slot_or_path, data)
    return wutil.make_inViewMessage("File imported")

ANIMATION_SCHEMA_VERSION = 3
ANIMATION_CONTROLS_KEY = "controls"
ANIMATION_META_KEY = "meta"
ANIMATION_FRAME_KEY = "k"
ANIMATION_VALUE_KEY = "v"
ANIMATION_STATIC_VALUE_KEY = "sv"
ANIMATION_TANGENT_KEY = "t"
ANIMATION_LAYERS_KEY = "ly"
ANIMATION_LAYER_WEIGHT_KEY = "w"
TANGENT_KEYS = {
    "itt": "inTangentType",
    "ott": "outTangentType",
    "ia": "inAngle",
    "oa": "outAngle",
    "iw": "inWeight",
    "ow": "outWeight",
    "wt": "weightedTangents",
}


def _is_animation_payload(data):
    return isinstance(data, dict) and isinstance(data.get(ANIMATION_CONTROLS_KEY), dict)


def _animation_controls(animation_data):
    return (animation_data or {}).get(ANIMATION_CONTROLS_KEY) or {}


def _copy_paste_targets(saved_data, selected_objects):
    if selected_objects:
        return selected_objects
    data = _animation_controls(saved_data) if _is_animation_payload(saved_data) else (saved_data or {})
    return [control for control in data.keys() if cmds.objExists(control)]


def _animation_layer_items(channel_data):
    layers = channel_data.get(ANIMATION_LAYERS_KEY) or []
    if isinstance(layers, dict):
        return [(layer_name, layer_data, layer_data.get(ANIMATION_LAYER_WEIGHT_KEY) or {}) for layer_name, layer_data in layers.items()]
    items = []
    for entry in layers:
        if isinstance(entry, dict):
            items.append((entry.get("layer"), entry.get("data") or {}, entry.get("weight") or {}))
    return items


def _animation_layer_names(channel_data):
    return [layer_name for layer_name, _layer_data, _weight_data in _animation_layer_items(channel_data) if layer_name]


def _animation_data_key_count(animation_data, targets=None):
    count = 0
    controls = _animation_controls(animation_data)
    target_names = set(targets or controls.keys())
    for control, channels in controls.items():
        if control not in target_names:
            continue
        for anim_data in (channels or {}).values():
            count += len(anim_data.get(ANIMATION_FRAME_KEY) or [])
            for _layer_name, layer_data, weight_data in _animation_layer_items(anim_data):
                count += len(layer_data.get(ANIMATION_FRAME_KEY) or [])
                count += len(weight_data.get(ANIMATION_FRAME_KEY) or [])
    return count


def _animation_data_apply_count(animation_data, targets=None):
    count = _animation_data_key_count(animation_data, targets=targets)
    controls = _animation_controls(animation_data)
    target_names = set(targets or controls.keys())
    for control, channels in controls.items():
        if control not in target_names:
            continue
        for anim_data in (channels or {}).values():
            if ANIMATION_STATIC_VALUE_KEY in (anim_data or {}):
                count += 1
    return count


def _time_context_tint_range(time_context):
    if not time_context:
        return None
    if time_context.mode in ("graph_editor_keys", "time_slider_range"):
        return time_context.timerange
    if time_context.mode == "all_animation":
        return timelineWidgets.get_playback_range()
    return time_context.timerange


def _shift_timerange(timerange, offset):
    if not timerange:
        return None
    return (timerange[0] + offset, timerange[1] + offset)


def _animation_data_timerange(animation_data):
    meta_range = ((animation_data or {}).get(ANIMATION_META_KEY) or {}).get("range")
    if meta_range and len(meta_range) >= 2:
        return meta_range[0], meta_range[1]
    frames = []
    for channels in _animation_controls(animation_data).values():
        for anim_data in (channels or {}).values():
            frames.extend(anim_data.get(ANIMATION_FRAME_KEY) or [])
            for _layer_name, layer_data, weight_data in _animation_layer_items(anim_data):
                frames.extend(layer_data.get(ANIMATION_FRAME_KEY) or [])
                frames.extend(weight_data.get(ANIMATION_FRAME_KEY) or [])
    return timelineWidgets.get_frames_timerange(frames)


def _query_anim_channel_data(source, time_context):
    if time_context.mode == "graph_editor_keys":
        selected_frames = set(time_context.frames)
        keyframes = cmds.keyframe(source, query=True) or []
        keyframes = [frame for frame in keyframes if int(frame) in selected_frames]
        values = [cmds.keyframe(source, query=True, vc=True, time=(frame, frame))[0] for frame in keyframes]
    elif time_context.mode == "time_slider_range":
        keyframes = cmds.keyframe(source, query=True, time=(time_context.start_frame, time_context.end_frame))
        values = cmds.keyframe(source, query=True, vc=True, time=(time_context.start_frame, time_context.end_frame))
    else:
        keyframes = cmds.keyframe(source, query=True)
        values = cmds.keyframe(source, query=True, vc=True)

    keyframes = keyframes or []
    values = values or []
    return {
        ANIMATION_FRAME_KEY: keyframes,
        ANIMATION_VALUE_KEY: values,
        ANIMATION_TANGENT_KEY: _query_key_tangent_data(source, keyframes),
    }


def _query_static_channel_value(plug):
    try:
        value = cmds.getAttr(plug)
    except Exception:
        return {}
    return {ANIMATION_STATIC_VALUE_KEY: value}


def _anim_layer_is_muted(layer_name):
    if not layer_name:
        return False
    try:
        return bool(cmds.animLayer(layer_name, query=True, mute=True))
    except Exception:
        return False


def _query_layered_anim_channel_data(plug, time_context):
    try:
        from TheKeyMachine.core import animlayers
        layer_entries = animlayers.get_anim_curves_by_layer_for_plug(plug)
    except Exception:
        layer_entries = []

    if not layer_entries:
        return _query_anim_channel_data(plug, time_context)

    channel_data = {}
    layer_data = []
    for entry in layer_entries:
        curve = entry.get("curve")
        if not curve:
            continue
        layer_name = entry.get("layer")
        if _anim_layer_is_muted(layer_name):
            continue
        data = _query_anim_channel_data(curve, time_context)
        if not data.get(ANIMATION_FRAME_KEY):
            continue
        weight_data = _query_anim_layer_weight_data(layer_name, time_context)
        if layer_name:
            layer_data.append({"layer": layer_name, "data": data, "weight": weight_data})
        else:
            channel_data.update(data)

    if layer_data:
        channel_data[ANIMATION_LAYERS_KEY] = layer_data
    return channel_data


def _query_anim_layer_weight_data(layer_name, time_context):
    if not layer_name:
        return {}
    weight_plug = "{}.weight".format(layer_name)
    if not cmds.objExists(weight_plug):
        return {}
    data = _query_anim_channel_data(weight_plug, time_context)
    return data if data else {}


def _ensure_anim_layer_for_plug(layer_name, target, channel):
    if not layer_name:
        return None
    try:
        existing = cmds.ls(type="animLayer") or []
        if layer_name not in existing:
            cmds.animLayer(layer_name)
    except Exception:
        return None

    plug = "{}.{}".format(target, channel)
    previous_selection = None
    for add_call in (
        lambda: cmds.animLayer(layer_name, edit=True, attribute=plug),
        lambda: cmds.select(target, replace=True) or cmds.animLayer(layer_name, edit=True, addSelectedObjects=True),
        lambda: cmds.animLayer(layer_name, edit=True, attribute=plug),
    ):
        try:
            if previous_selection is None:
                try:
                    previous_selection = cmds.ls(selection=True, long=True) or []
                except Exception:
                    previous_selection = []
            add_call()
            break
        except Exception:
            continue
    if previous_selection is not None:
        try:
            cmds.select(previous_selection, replace=True)
        except Exception:
            pass
    return layer_name


def _ensure_anim_layers_for_channel(target, channel, channel_data):
    for layer_name, _layer_data, _weight_data in _animation_layer_items(channel_data):
        if not layer_name:
            continue
        _ensure_anim_layer_for_plug(layer_name, target, channel)


def _apply_anim_layer_weight_data(layer_name, target, weight_data, progress=None):
    if not layer_name or not weight_data:
        return 0
    applied = 0
    try:
        layer_plug = "{}.weight".format(layer_name)
        if not cmds.objExists(layer_plug):
            return 0
        keyframes = weight_data.get(ANIMATION_FRAME_KEY) or []
        values = weight_data.get(ANIMATION_VALUE_KEY) or []
        if not keyframes or not values:
            return 0
        for key_time, value in zip(keyframes, values):
            try:
                cmds.setKeyframe(layer_name, time=(key_time,), attribute="weight", value=value)
                applied += 1
            except Exception:
                pass
            if progress and progress.step():
                return applied
    except Exception:
        return 0
    return applied


def _transform_channel_values(channel_data, transform_value):
    transformed = dict(channel_data or {})
    transformed[ANIMATION_VALUE_KEY] = [transform_value(v) for v in channel_data.get(ANIMATION_VALUE_KEY) or []]
    layers = []
    for layer_name, layer_data, weight_data in _animation_layer_items(channel_data):
        layer_entry = {"layer": layer_name, "data": _transform_channel_values(layer_data, transform_value)}
        if weight_data:
            layer_entry["weight"] = _transform_channel_values(weight_data, transform_value)
        layers.append(layer_entry)
    if layers:
        transformed[ANIMATION_LAYERS_KEY] = layers
    return transformed


def _maybe_apply_paste_range(paste_range, anchor_widget=None):
    if not paste_range:
        return
    try:
        start_frame, end_frame = int(paste_range[0]), int(paste_range[1])
        current_range = (
            int(cmds.playbackOptions(query=True, minTime=True)),
            int(cmds.playbackOptions(query=True, maxTime=True)),
        )
    except Exception:
        return
    if current_range == (start_frame, end_frame):
        return

    apply_button = customDialogs.QFlatConfirmDialog.CustomButton("Apply Range", positive=True, icon=icons.apply)
    no_button = customDialogs.QFlatConfirmDialog.CustomButton("No", positive=False, icon=icons.cancel)
    clicked = customDialogs.QFlatTooltipConfirm.question(
        anchor_widget or wutil.get_maya_qt(),
        title="Apply paste range?",
        message="Set the timeline range to {} - {} from the copied data?".format(start_frame, end_frame),
        buttons=[apply_button, no_button],
        icon=icons.paste_animation,
        highlight=apply_button,
    )
    if clicked and clicked.get("positive"):
        cmds.playbackOptions(
            minTime=start_frame,
            maxTime=end_frame,
            animationStartTime=start_frame,
            animationEndTime=end_frame,
        )


def _refresh_animation_view():
    try:
        current_time = cmds.currentTime(query=True)
        cmds.currentTime(current_time, edit=True)
    except Exception:
        pass
    try:
        cmds.dgdirty(allPlugs=True)
    except Exception:
        pass
    try:
        cmds.refresh(force=True)
    except Exception:
        pass


def _query_key_tangent_data(plug, keyframes):
    tangent_data = {short_key: [] for short_key in TANGENT_KEYS}

    # Most animation copies contain a contiguous curve/range. Query every
    # tangent property once for that range instead of once per property/key.
    if keyframes:
        time_range = (min(keyframes), max(keyframes))
        try:
            range_frames = cmds.keyframe(plug, query=True, time=time_range) or []
        except Exception:
            range_frames = []
        if len(range_frames) == len(keyframes) and all(
            abs(float(a) - float(b)) <= 0.000001 for a, b in zip(range_frames, keyframes)
        ):
            for short_key, query_key in TANGENT_KEYS.items():
                if short_key == "wt":
                    continue
                try:
                    values = cmds.keyTangent(plug, query=True, time=time_range, **{query_key: True}) or []
                except Exception:
                    values = []
                tangent_data[short_key] = list(values[:len(keyframes)])
                if len(tangent_data[short_key]) < len(keyframes):
                    tangent_data[short_key].extend([None] * (len(keyframes) - len(tangent_data[short_key])))
            try:
                weighted_values = cmds.keyTangent(plug, query=True, weightedTangents=True) or []
                weighted = bool(weighted_values[0] if isinstance(weighted_values, list) else weighted_values)
            except Exception:
                weighted = None
            tangent_data["wt"] = [weighted] * len(keyframes)
            return tangent_data

    # Sparse graph-editor selections need exact per-key queries.
    for frame in keyframes or []:
        time_arg = (frame, frame)
        for short_key, query_key in TANGENT_KEYS.items():
            if short_key == "wt":
                continue
            try:
                values = cmds.keyTangent(plug, query=True, time=time_arg, **{query_key: True}) or []
                tangent_data[short_key].append(values[0] if values else None)
            except Exception:
                tangent_data[short_key].append(None)
        try:
            weighted = cmds.keyTangent(plug, query=True, weightedTangents=True)
            tangent_data["wt"].append(bool(weighted[0] if isinstance(weighted, list) else weighted))
        except Exception:
            tangent_data["wt"].append(None)
    return tangent_data


def _apply_key_tangent_data(target, channel, key_time, tangent_data, index, layer_name=None):
    if not tangent_data:
        return

    def _value(name):
        values = tangent_data.get(name) or []
        return values[index] if index < len(values) else None

    def _edit_tangent(**kwargs):
        if not kwargs:
            return
        try:
            if layer_name:
                kwargs["animLayer"] = layer_name
            cmds.keyTangent(target, attribute=channel, time=(key_time,), edit=True, **kwargs)
        except Exception as e:
            import TheKeyMachine.mods.reportMod as report

            report.report_detected_exception(e, context="paste animation tangent data")

    in_type = _value("itt")
    out_type = _value("ott")
    type_kwargs = {}
    if in_type is not None:
        type_kwargs["inTangentType"] = in_type
    if out_type is not None:
        type_kwargs["outTangentType"] = out_type

    detail_kwargs = {}
    if in_type not in ("auto", "autoease", "autoEase", "autoMix"):
        in_angle = _value("ia")
        in_weight = _value("iw")
        if in_angle is not None:
            detail_kwargs["inAngle"] = in_angle
        if in_weight is not None:
            detail_kwargs["inWeight"] = in_weight
    if out_type not in ("auto", "autoease", "autoEase", "autoMix"):
        out_angle = _value("oa")
        out_weight = _value("ow")
        if out_angle is not None:
            detail_kwargs["outAngle"] = out_angle
        if out_weight is not None:
            detail_kwargs["outWeight"] = out_weight

    _edit_tangent(**type_kwargs)
    _edit_tangent(**detail_kwargs)
    if detail_kwargs:
        _edit_tangent(**type_kwargs)


def _apply_channel_weighted_tangents(target, channel, tangent_data, layer_name=None):
    weighted_values = (tangent_data or {}).get("wt") or []
    weighted = next((value for value in weighted_values if value is not None), None)
    if weighted is None:
        return
    try:
        kwargs = {"weightedTangents": bool(weighted)}
        if layer_name:
            kwargs["animLayer"] = layer_name
        cmds.keyTangent(target, attribute=channel, edit=True, **kwargs)
    except Exception:
        pass


def _attr_exists_and_settable(node, attr):
    full_attr = f"{node}.{attr}"
    if not cmds.objExists(full_attr):
        return False
    try:
        return bool(cmds.getAttr(full_attr, settable=True))
    except Exception:
        return False


def _set_attr_value(plug, value):
    if isinstance(value, list):
        if len(value) == 1 and isinstance(value[0], (list, tuple)):
            cmds.setAttr(plug, *value[0])
        else:
            cmds.setAttr(plug, *value)
    else:
        cmds.setAttr(plug, value)


@contextmanager
def _copy_paste_operation(
    tool_id,
    success_message,
    undo=False,
    tint="none",
    default_mode="current_frame",
    timerange=None,
    progress=False,
    progress_max=0,
):
    state = {"success": False, "timerange": None, "operation": None}
    tint_session = None
    operation_tint = "none"
    operation_timerange = None
    if tint == "range" and timerange:
        operation_tint = "range"
        operation_timerange = timerange
    elif tint == "current":
        operation_tint = "current"
    try:
        with toolCommon.tool_operation(
            tool_id=tool_id,
            label=success_message,
            progress=progress,
            progress_max=progress_max,
            undo=undo,
            undo_name=toolCommon.make_undo_chunk_name(tool_id=tool_id),
            tint=operation_tint,
            timerange=operation_timerange,
            default_mode=default_mode,
            tint_key=tool_id,
            tint_color=_timeline_tint_color(tool_id) if operation_tint != "none" else None,
        ) as operation:
            state["operation"] = operation
            yield state

        if state.get("success"):
            if tint == "range" and state.get("timerange") and operation_tint == "none" and not tint_session:
                tint_session = _begin_timeline_tint(state["timerange"], tool_id)
            wutil.make_inViewMessage(success_message)
    finally:
        if tint_session:
            tint_session.finish()


def _apply_animation_channels_to_targets(
    targets,
    channels_data,
    replace=False,
    insert_time=None,
    time_shift=None,
    replace_range=(0, 10000),
    progress=None,
):
    keys_set = 0
    attr_settable_cache = {}
    progress_batch_size = 25

    def _apply_channel_data(target, channel, channel_data, layer_name=None):
        applied = 0
        pending_progress = 0
        keyframes = channel_data.get(ANIMATION_FRAME_KEY) or []
        values = channel_data.get(ANIMATION_VALUE_KEY) or []
        if not keyframes or not values:
            return applied

        paste_layer = _ensure_anim_layer_for_plug(layer_name, target, channel) if layer_name else None
        channel_time_shift = time_shift
        if channel_time_shift is None:
            channel_time_shift = insert_time - keyframes[0] if insert_time is not None else 0
        tangent_data = channel_data.get(ANIMATION_TANGENT_KEY) or {}
        _apply_channel_weighted_tangents(target, channel, tangent_data, layer_name=paste_layer)
        for key_index, (frame, value) in enumerate(zip(keyframes, values)):
            try:
                key_time = frame + channel_time_shift
                key_kwargs = {"time": (key_time,), "attribute": channel, "value": value}
                if paste_layer:
                    key_kwargs["animLayer"] = paste_layer
                cmds.setKeyframe(target, **key_kwargs)
                _apply_key_tangent_data(target, channel, key_time, tangent_data, key_index, layer_name=paste_layer)
                applied += 1
            except Exception as e:
                import TheKeyMachine.mods.reportMod as report

                report.report_detected_exception(e, context="paste animation set key")
            pending_progress += 1
            if progress and pending_progress >= progress_batch_size:
                if progress.step(amount=pending_progress):
                    return applied
                pending_progress = 0
        if progress and pending_progress:
            progress.step(amount=pending_progress)
        return applied

    with toolCommon.suspend_maya_refresh():
        for target in targets or []:
            for channel, anim_data in (channels_data or {}).items():
                if progress and progress.cancelled:
                    return keys_set
                cache_key = (target, channel)
                if cache_key not in attr_settable_cache:
                    attr_settable_cache[cache_key] = _attr_exists_and_settable(target, channel)
                if not attr_settable_cache[cache_key]:
                    continue

                _ensure_anim_layers_for_channel(target, channel, anim_data)

                if replace:
                    try:
                        cmds.cutKey(target, time=replace_range, attribute=channel, option="keys")
                    except Exception:
                        pass

                if ANIMATION_STATIC_VALUE_KEY in (anim_data or {}):
                    try:
                        value = anim_data.get(ANIMATION_STATIC_VALUE_KEY)
                        _set_attr_value(f"{target}.{channel}", value)
                        keys_set += 1
                    except Exception as e:
                        import TheKeyMachine.mods.reportMod as report

                        report.report_detected_exception(e, context="paste animation static attribute set")
                    if progress:
                        progress.step()

                keys_set += _apply_channel_data(target, channel, anim_data)
                for layer_name, layer_data, weight_data in _animation_layer_items(anim_data):
                    if progress and progress.cancelled:
                        return keys_set
                    keys_set += _apply_channel_data(target, channel, layer_data, layer_name=layer_name)
                    keys_set += _apply_anim_layer_weight_data(layer_name, target, weight_data, progress=progress)

    return keys_set


def _select_existing_targets(targets):
    targets = [target for target in (targets or []) if target and cmds.objExists(target)]
    if not targets:
        return
    try:
        cmds.select(targets, replace=True)
    except Exception:
        pass


def _apply_animation_data(animation_data, selected_objects, replace=False, insert_time=None, progress=None):
    targets = _copy_paste_targets(animation_data, selected_objects)
    if not targets:
        return 0, []

    controls = _animation_controls(animation_data)
    keys_set = 0
    pasted_targets = []
    for control in targets:
        if control in controls:
            applied = _apply_animation_channels_to_targets(
                [control],
                controls[control],
                replace=replace,
                insert_time=insert_time,
                progress=progress,
            )
            keys_set += applied
            if applied:
                pasted_targets.append(control)

    return keys_set, pasted_targets


def _is_valid_pose_attribute_value(value):
    if isinstance(value, (float, int)):
        return True
    if isinstance(value, list) and all(isinstance(v, (float, int)) for v in value):
        return True
    if (
        isinstance(value, list)
        and len(value) == 1
        and isinstance(value[0], (list, tuple))
        and all(isinstance(v, (float, int)) for v in value[0])
    ):
        return True
    if isinstance(value, str) and not re.search(r"[# ]", value):
        return True
    return False


def _apply_pose_data(pose_data, selected_objects):
    targets = _copy_paste_targets(pose_data, selected_objects)
    if not targets:
        return 0, []

    attrs_set = 0
    pasted_targets = []
    for control in targets:
        if control not in pose_data:
            continue
        control_attrs_set = 0
        for attr, value in pose_data[control].items():
            if not _is_valid_pose_attribute_value(value):
                continue
            if not _attr_exists_and_settable(control, attr):
                continue
            try:
                _set_attr_value(f"{control}.{attr}", value)
                attrs_set += 1
                control_attrs_set += 1
            except RuntimeError as e:
                import TheKeyMachine.mods.reportMod as report

                report.report_detected_exception(e, context="paste pose attribute set")
        if control_attrs_set:
            pasted_targets.append(control)

    return attrs_set, pasted_targets


def copy_animation(*args):
    def get_animation_channels(control):
        channels = []
        for attr in cmds.listAttr(control, keyable=True) or []:
            if attr == "tag":
                continue
            if _attr_exists_and_settable(control, attr):
                channels.append(attr)
        return channels

    selected_objects = selectionMod.get_selected_objects()

    if not selected_objects:
        return

    time_context = timelineWidgets.resolve_time_context(default_mode="all_animation")
    tint_range = _time_context_tint_range(time_context)
    animation_data = {
        ANIMATION_META_KEY: {
            "type": "animation",
            "version": ANIMATION_SCHEMA_VERSION,
            "range": list(tint_range) if tint_range else None,
        },
        ANIMATION_CONTROLS_KEY: {},
    }
    controls_data = animation_data[ANIMATION_CONTROLS_KEY]
    channel_total = sum(len(get_animation_channels(control)) for control in selected_objects)

    try:
        with _copy_paste_operation(
            "copy_animation", "Animation Copied", tint="range", timerange=tint_range,
            progress=True, progress_max=channel_total,
        ) as operation:
            processor = operation["operation"]
            processor.set_status("Copying Animation")
            for control in selected_objects:
                if processor.cancelled:
                    return
                control_name = control
                animated_channels = get_animation_channels(control)

                controls_data[control_name] = {}
                for channel in animated_channels:
                    plug = f"{control}.{channel}"
                    channel_data = _query_layered_anim_channel_data(plug, time_context)
                    if channel_data.get(ANIMATION_FRAME_KEY) or channel_data.get(ANIMATION_LAYERS_KEY):
                        controls_data[control_name][channel] = channel_data
                    else:
                        static_data = _query_static_channel_value(plug)
                        if static_data:
                            controls_data[control_name][channel] = static_data
                    processor.step()

            if time_context.mode == "time_slider_range":
                clear_timeslider_selection()
            elif time_context.mode not in ("all_animation", "graph_editor_keys"):
                tint_range = _animation_data_timerange(animation_data)

            animation_data[ANIMATION_META_KEY]["range"] = list(tint_range) if tint_range else None
            clipboard.save("animation", animation_data)

            operation["timerange"] = tint_range
            operation["success"] = True
    except Exception as e:
        cmds.warning(f"Error saving animation: {e}")


# PASTE ANIMATION ___________________________________________________________________________


def paste_animation(*args, anchor_widget=None):
    selected_objects = selectionMod.get_selected_objects()

    animation_data = clipboard.load("animation", "No animation file found. Please copy animation first")
    if not animation_data:
        return

    targets = _copy_paste_targets(animation_data, selected_objects)
    paste_range = _animation_data_timerange(animation_data)
    key_count = _animation_data_apply_count(animation_data, targets=targets)
    prompt_range = None
    with _copy_paste_operation("paste_animation", "Animation Pasted", undo=True, tint="range", timerange=paste_range, progress=True, progress_max=key_count) as operation:
        processor = operation["operation"].set_status("Pasting Animation")
        keys_set, pasted_targets = _apply_animation_data(animation_data, selected_objects, replace=True, progress=processor)
        if keys_set:
            operation["timerange"] = paste_range
            operation["success"] = True
            _select_existing_targets(pasted_targets)
            _refresh_animation_view()
            prompt_range = paste_range
        else:
            cmds.warning("No matching animation targets found")
    _maybe_apply_paste_range(prompt_range, anchor_widget=anchor_widget)


# PASTE INSERT _________________________________________________________________________


def paste_insert_animation(*args, anchor_widget=None):
    selected_objects = selectionMod.get_selected_objects()
    current_time = cmds.currentTime(query=True)

    animation_data = clipboard.load("animation", "No animation file found. Please copy animation first")
    if not animation_data:
        return

    targets = _copy_paste_targets(animation_data, selected_objects)
    source_range = _animation_data_timerange(animation_data)
    first_source_frame = source_range[0] if source_range else current_time
    paste_range = _shift_timerange(source_range, current_time - first_source_frame)
    key_count = _animation_data_apply_count(animation_data, targets=targets)
    prompt_range = None
    with _copy_paste_operation("paste_insert_animation", "Animation Pasted", undo=True, tint="range", timerange=paste_range, progress=True, progress_max=key_count) as operation:
        processor = operation["operation"].set_status("Pasting Animation")
        keys_set, pasted_targets = _apply_animation_data(animation_data, selected_objects, insert_time=current_time, progress=processor)
        if keys_set:
            operation["timerange"] = paste_range
            operation["success"] = True
            _select_existing_targets(pasted_targets)
            _refresh_animation_view()
            prompt_range = paste_range
        else:
            cmds.warning("No matching animation targets found")
    _maybe_apply_paste_range(prompt_range, anchor_widget=anchor_widget)


# PASTE OPPOSITE ________________________________________________________________________


def paste_opposite_animation(*args, anchor_widget=None):
    mirror_exceptions_file_path = general.get_mirror_exceptions_file()

    # ATTRIBUTES_TO_IGNORE = {"tag"}

    def load_exceptions(file_path):
        if os.path.exists(file_path):
            with open(file_path, "r") as file:
                return json.load(file)
        else:
            return {}

    exceptions = load_exceptions(mirror_exceptions_file_path)

    def find_mirror_control(control_name):
        for pattern, opposite_pattern in MIRROR_PATTERNS:
            if pattern in control_name:
                return control_name.replace(pattern, opposite_pattern, 1)
        return None

    def mirror_value(attr, value):
        if attr in exceptions.get(control_name, {}):
            exception_type = exceptions[control_name][attr]
            if exception_type == "invert":
                return -value
        if attr in [""]:
            return -value
        return value

    animation_data = clipboard.load("animation", "No animation file found. Please copy animation first")
    if not animation_data:
        return

    paste_range = _animation_data_timerange(animation_data)
    key_count = _animation_data_apply_count(animation_data)
    controls = _animation_controls(animation_data)
    prompt_range = None
    with _copy_paste_operation("paste_opposite_animation", "Animation Pasted", undo=True, tint="range", timerange=paste_range, progress=True, progress_max=key_count) as operation:
        keys_set = 0
        pasted_targets = []
        processor = operation["operation"].set_status("Pasting Opposite Animation")
        for control_name, anim_data in controls.items():
            if processor.cancelled:
                break
            mirror_control_name = find_mirror_control(control_name)

            if mirror_control_name:
                full_mirror_control_name = next((c for c in cmds.ls() if c.endswith(mirror_control_name)), None)
                if not full_mirror_control_name:
                    continue

                mirrored_channels = {}
                for channel, channel_data in anim_data.items():
                    mirrored_channels[channel] = _transform_channel_values(
                        channel_data,
                        lambda value, attr=channel: mirror_value(attr, value),
                    )
                applied = _apply_animation_channels_to_targets(
                    [full_mirror_control_name],
                    mirrored_channels,
                    replace=True,
                    progress=processor,
                )
                keys_set += applied
                if applied:
                    pasted_targets.append(full_mirror_control_name)

        if keys_set:
            operation["timerange"] = paste_range
            operation["success"] = True
            _select_existing_targets(pasted_targets)
            _refresh_animation_view()
            prompt_range = paste_range
        else:
            cmds.warning("No matching animation targets found")
    _maybe_apply_paste_range(prompt_range, anchor_widget=anchor_widget)


def paste_animation_to(source_control_name=None, replace=True, insert_at_current=False, *args, anchor_widget=None, **kwargs):
    global _paste_to_dialog

    try:
        animation_data = clipboard.load("animation", "No animation file found. Please copy animation first")
    except Exception as e:
        cmds.warning("Error reading animation file: {}".format(e))
        return
    if animation_data is None:
        return

    if not isinstance(animation_data, dict) or not animation_data:
        cmds.warning("Animation file is empty or invalid")
        return

    def _apply_mappings(mappings, insert=False):
        current_time = cmds.currentTime(query=True) if insert else None
        pasted_data = {}
        source_range = _animation_data_timerange(animation_data)
        first_source_frame = source_range[0] if source_range else current_time
        paste_range = _shift_timerange(source_range, current_time - first_source_frame) if insert else source_range
        controls = _animation_controls(animation_data)
        key_count = sum(
            _animation_data_apply_count({ANIMATION_CONTROLS_KEY: {source_node: controls.get(source_node, {})}})
            for source_node, _ in mappings
        )
        prompt_range = None
        with _copy_paste_operation("paste_animation_to", "Animation Pasted", undo=True, tint="range", timerange=paste_range, progress=True, progress_max=key_count) as operation:
            total_keys_set = 0
            pasted_targets = []
            processor = operation["operation"].set_status("Pasting Animation")
            for source_node, target_node in mappings:
                if processor.cancelled:
                    break
                src_channels = controls.get(source_node, {})
                applied = _apply_animation_channels_to_targets(
                    [target_node],
                    src_channels,
                    replace=not insert,
                    insert_time=current_time if insert else None,
                    replace_range=(0, 1e6),
                    progress=processor,
                )
                total_keys_set += applied
                if applied:
                    pasted_targets.append(target_node)
                if src_channels:
                    pasted_data[target_node] = src_channels

            if total_keys_set == 0:
                cmds.warning("No keys were pasted. Check that destination controls have the needed attributes and that the source has keyframes.")
                return False

            operation["timerange"] = paste_range or _animation_data_timerange(animation_data)
            operation["success"] = True
            _select_existing_targets(pasted_targets)
            _refresh_animation_view()
            prompt_range = operation["timerange"]
        _maybe_apply_paste_range(prompt_range, anchor_widget=anchor_widget)
        return True

    _paste_to_dialog = customWidgets.PasteToDialog(_animation_controls(animation_data), _apply_mappings, data_label="animation")
    _paste_to_dialog.show()


def paste_pose_to(*args, anchor_widget=None, **kwargs):
    global _paste_to_dialog

    pose_data = _load_pose_json()
    if not pose_data:
        return

    def _apply_mappings(mappings, insert=False):
        with _copy_paste_operation("paste_pose_to", "Pose Pasted", undo=True, tint="current") as operation:
            attrs_set = 0
            pasted_targets = []
            for source_node, target_node in mappings:
                source_attrs = pose_data.get(source_node, {})
                target_pose_data = {target_node: source_attrs}
                target_attrs_set, target_pasted = _apply_pose_data(target_pose_data, [target_node])
                attrs_set += target_attrs_set
                pasted_targets.extend(target_pasted)

            if not attrs_set:
                cmds.warning("No pose values were pasted. Check that destination controls have the needed attributes.")
                return False

            operation["success"] = True
            _select_existing_targets(pasted_targets)
            return True

    _paste_to_dialog = customWidgets.PasteToDialog(pose_data, _apply_mappings, data_label="pose")
    _paste_to_dialog.show()


def export_animation_file(*args):
    return clipboard.export_dialog("animation", "Export Animation")


def import_animation_file(*args):
    return clipboard.import_dialog("animation", "Import Animation")


# COPY POSE ________________________________________________________________________


def copy_pose(*args):
    selected_objects = selectionMod.get_selected_objects()

    if not selected_objects:
        return

    pose_data = {}

    with _copy_paste_operation("copy_pose", "Pose Copied", tint="current") as operation:
        for control in selected_objects:
            control_name = control
            attributes = cmds.listAttr(control, keyable=True, unlocked=True)

            if attributes is None:
                continue

            pose_data[control_name] = {}
            for attr in attributes:
                try:
                    values = cmds.getAttr(f"{control}.{attr}")
                    pose_data[control_name][attr] = values
                except Exception as e:
                    import TheKeyMachine.mods.reportMod as report

                    report.report_detected_exception(e, context="copy pose attribute read")

        clipboard.save("pose", pose_data)
        operation["success"] = True


def export_pose_file(*args):
    return clipboard.export_dialog("pose", "Export Pose")


def import_pose_file(*args):
    return clipboard.import_dialog("pose", "Import Pose")


# PASTE POSE _____________________________________________________________


def paste_pose(*args):
    selected_objects = selectionMod.get_selected_objects()

    pose_data = _load_pose_json()
    if not pose_data:
        return

    with _copy_paste_operation("paste_pose", "Pose Pasted", undo=True, tint="current") as operation:
        attrs_set, pasted_targets = _apply_pose_data(pose_data, selected_objects)
        if attrs_set:
            operation["success"] = True
            _select_existing_targets(pasted_targets)
        else:
            cmds.warning("No matching pose targets found")


# ______________________________________________ TANGENTS


# MATCH CYCLE


def _copy_curve_key_state(curve, source_time, target_time):
    source_value = cmds.keyframe(curve, time=(source_time, source_time), query=True, valueChange=True)[0]
    source_in_tangent_type = cmds.keyTangent(curve, time=(source_time,), query=True, inTangentType=True)[0]
    source_out_tangent_type = cmds.keyTangent(curve, time=(source_time,), query=True, outTangentType=True)[0]
    source_in_angle = cmds.keyTangent(curve, time=(source_time,), query=True, inAngle=True)[0]
    source_out_angle = cmds.keyTangent(curve, time=(source_time,), query=True, outAngle=True)[0]

    cmds.keyframe(curve, time=(target_time, target_time), valueChange=source_value)
    cmds.keyTangent(
        curve,
        time=(target_time,),
        edit=True,
        inTangentType=source_in_tangent_type,
        outTangentType=source_out_tangent_type,
    )
    cmds.keyTangent(curve, time=(target_time,), edit=True, inAngle=source_in_angle, outAngle=source_out_angle)


def match_curve_cycle(*args, target_key="last"):
    curveNames = selectionMod.get_graph_editor_selected_curves()

    for curve in curveNames:
        firstKeyTime = cmds.findKeyframe(curve, which="first")
        lastKeyTime = cmds.findKeyframe(curve, which="last")

        if target_key == "first":
            _copy_curve_key_state(curve, lastKeyTime, firstKeyTime)
        else:
            _copy_curve_key_state(curve, firstKeyTime, lastKeyTime)


# Bouncy Tangent tangets


def calculateTangentAngle(curve, time1, value1, time2, value2):
    # Calcula el ángulo de la tangente entre dos keyframes
    if time2 - time1 == 0:
        return 0  # Evitar división por cero
    angle_radians = math.atan2(value2 - value1, time2 - time1)
    angle_degrees = math.degrees(angle_radians)
    return angle_degrees


def _collect_bouncy_target_curves(target_info):
    curves = []
    seen = set()

    for curve in target_info.get("selected_curves") or []:
        if curve and curve not in seen:
            seen.add(curve)
            curves.append(curve)

    if curves:
        return curves

    for curve in selectionMod.get_anim_curves_from_plugs(target_info.get("target_plugs") or []):
        if curve and curve not in seen:
            seen.add(curve)
            curves.append(curve)

    if curves:
        return curves

    target_objects = target_info.get("target_objects") or []
    selected_channels = target_info.get("selected_channels") or None
    time_context = target_info.get("time_context")
    query_kwargs = {"query": True, "name": True}
    if selected_channels:
        query_kwargs["attribute"] = selected_channels
    if time_context and time_context.mode == "time_slider_range":
        query_kwargs["time"] = time_context.timerange

    for obj in target_objects:
        obj_curves = cmds.keyframe(obj, **query_kwargs) or []
        for curve in obj_curves:
            if curve and curve not in seen:
                seen.add(curve)
                curves.append(curve)

    return curves


def _filter_bouncy_keyframes_by_scope(target_keyframes, key_scope):
    if key_scope not in ("first", "last"):
        return target_keyframes

    frames = sorted({float(frame) for _curve, frame in target_keyframes})
    if not frames:
        return []

    target_frame = frames[0] if key_scope == "first" else frames[-1]
    return [(curve, frame) for curve, frame in target_keyframes if float(frame) == target_frame]


def _collect_bouncy_target_keyframes(target_info, key_scope="selection"):
    selected_keyframes = target_info.get("selected_keyframes") or []
    if selected_keyframes and key_scope != "all":
        return _filter_bouncy_keyframes_by_scope(
            [(curve, float(frame)) for curve, frame in selected_keyframes],
            key_scope,
        )

    time_context = target_info.get("time_context")
    curves = _collect_bouncy_target_curves(target_info)
    targets = []
    seen = set()

    if not time_context:
        return targets

    for curve in curves:
        if time_context.mode == "time_slider_range":
            key_times = cmds.keyframe(curve, query=True, time=time_context.timerange, timeChange=True) or []
        else:
            current_frame = time_context.timerange[0]
            key_times = cmds.keyframe(curve, query=True, time=(current_frame, current_frame), timeChange=True) or []

        for frame in key_times:
            item = (curve, float(frame))
            if item in seen:
                continue
            seen.add(item)
            targets.append(item)

    return _filter_bouncy_keyframes_by_scope(targets, key_scope)


def bouncy_tangets(*args, angle_adjustment_factor=1.3, handle_mode="both", key_scope="selection", tint_color=None):  # Ajuste de ángulo
    default_mode = "all_animation" if key_scope == "all" else "current_frame"
    target_info = resolve_tool_targets(default_mode=default_mode, ordered_selection=True, long_names=False)
    target_keyframes = _collect_bouncy_target_keyframes(target_info, key_scope=key_scope)

    if not target_keyframes:
        return wutil.make_inViewMessage("No animation keys available to set tangents.")

    time_context = target_info.get("time_context")
    if target_info.get("selected_keyframes"):
        frames = sorted({int(frame) for _curve, frame in target_keyframes})
        tint_range = (frames[0], frames[-1])
    else:
        tint_range = time_context.timerange if time_context else None

    tint_session = _begin_timeline_tint(tint_range, "tangent_bouncy", color=tint_color) if tint_range else None
    try:
        for curve, time in target_keyframes:
            keyTimes = cmds.keyframe(curve, query=True, timeChange=True) or []
            keyValues = cmds.keyframe(curve, query=True, valueChange=True) or []
            if not keyTimes or not keyValues:
                continue

            currentIndex = None
            for index, key_time in enumerate(keyTimes):
                if abs(float(key_time) - float(time)) < 1e-4:
                    currentIndex = index
                    break
            if currentIndex is None:
                continue

            if currentIndex > 0:
                inAngle = calculateTangentAngle(
                    curve, keyTimes[currentIndex - 1], keyValues[currentIndex - 1], time, keyValues[currentIndex]
                )
            else:
                inAngle = 0

            if currentIndex < len(keyTimes) - 1:
                outAngle = calculateTangentAngle(
                    curve, time, keyValues[currentIndex], keyTimes[currentIndex + 1], keyValues[currentIndex + 1]
                )
            else:
                outAngle = 0

            adjusted_in_angle = max(-85, min(85, inAngle * angle_adjustment_factor))
            adjusted_out_angle = max(-85, min(85, outAngle * angle_adjustment_factor))

            tangent_kwargs = {
                "time": (time, time),
                "edit": True,
                "lock": False,
                "absolute": True,
            }
            if handle_mode in ("both", "in"):
                tangent_kwargs["inAngle"] = adjusted_in_angle
            if handle_mode in ("both", "out"):
                tangent_kwargs["outAngle"] = adjusted_out_angle
            if "inAngle" in tangent_kwargs or "outAngle" in tangent_kwargs:
                cmds.keyTangent(curve, **tangent_kwargs)
    finally:
        if tint_session:
            tint_session.finish()
