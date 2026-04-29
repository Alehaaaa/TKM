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

try:
    from PySide6.QtGui import QRegularExpressionValidator  # type: ignore
    from PySide6.QtCore import QRegularExpression  # type: ignore
except ImportError:
    from PySide2.QtGui import QRegExpValidator  # type: ignore
    from PySide2.QtCore import QRegExp  # type: ignore

    QRegularExpression = QRegExp
    QRegularExpressionValidator = QRegExpValidator


import json
import os
import sys
import math
import re
from collections import Counter

import TheKeyMachine.core.runtime_manager as runtime


import TheKeyMachine.widgets.util as wutil
import TheKeyMachine.widgets.timeline as timelineWidgets
import TheKeyMachine.mods.generalMod as general
import TheKeyMachine.mods.helperMod as helper
import TheKeyMachine.mods.settingsMod as settings
from TheKeyMachine.tools import common as toolCommon
from TheKeyMachine.core import selection_targets


python_version = f"{sys.version_info.major}{sys.version_info.minor}"
SHARE_KEYS_MODE_SETTING = "share_keys_mode"
SHARE_KEYS_MODE_PRESERVE_TANGENT = "preserve_tangent_type"
SHARE_KEYS_MODE_PRESERVE_SHAPE = "preserve_anim_curve_shape"

BAKE_UNDO_HELP = {
    1: ("Bake on Ones", helper.bake_animation_1_tooltip_text),
    2: ("Bake on Twos", helper.bake_animation_2_tooltip_text),
    3: ("Bake on Threes", helper.bake_animation_3_tooltip_text),
    4: ("Bake on Fours", helper.bake_animation_4_tooltip_text),
}


# _____________________________________________________ General _______________________________________________________________#


def clear_timeslider_selection():
    # fix temporal para limpiar el timeslider
    selection = selection_targets.get_selected_objects()
    cmds.select(selection)


def get_time_range_selected():
    aTimeSlider = selection_targets.get_playback_slider()
    timeRange = cmds.timeControl(aTimeSlider, q=True, rangeArray=True)

    # Verificar que el rango de tiempo seleccionado no esta vacío
    if timeRange[0] == timeRange[1]:
        return None

    return timeRange


# Esta es una version nueva que evalua correctamente si es un rango o no. Dejo la otra porque se usa en algunos sitios. Hay que limpiar.
def get_selected_time_range():
    time_range = selection_targets.get_selected_time_slider_range()
    if not time_range:
        return None
    return [time_range[0], time_range[1]]


def get_graph_editor_selected_keyframes():
    anim_curves = cmds.keyframe(q=True, selected=True, name=True)
    if not anim_curves:
        return []

    selected_frames = set(selection_targets.get_graph_editor_selected_frames())
    keyframes = []
    for curve in anim_curves:
        curve_frames = cmds.keyframe(curve, q=True, selected=True) or []
        keyframes.extend((curve, frame) for frame in curve_frames if int(frame) in selected_frames)

    return keyframes


def get_working_time_context(default_mode="all_animation"):
    return timelineWidgets.resolve_time_context(default_mode=default_mode)


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


def getSelectedCurves():
    curveNames = []

    # get the current selection list
    selectionList = om.MSelectionList()
    om.MGlobal.getActiveSelectionList(selectionList)

    # filter through the anim curves
    listIter = om.MItSelectionList(selectionList, om.MFn.kAnimCurve)
    while not listIter.isDone():
        # Retrieve current item's MObject
        mobj = om.MObject()
        listIter.getDependNode(mobj)

        # Convert MObject to MFnDependencyNode
        depNodeFn = om.MFnDependencyNode(mobj)
        curveName = depNodeFn.name()

        curveNames.append(curveName)
        listIter.next()

    return curveNames


def get_selected_channels():
    # Obtén el nombre del Channel Box principal
    main_channel_box = mel.eval("global string $gChannelBoxName; $temp=$gChannelBoxName;")
    selected_channels = cmds.channelBox(main_channel_box, query=True, selectedMainAttributes=True)

    return selected_channels


def resolve_tool_targets(default_mode="all_animation", ordered_selection=False, long_names=True):
    target_plugs, source, _time_range, has_graph_keys = selection_targets.resolve_target_attribute_plugs()
    time_context = get_working_time_context(default_mode=default_mode)
    selected_keyframes = get_graph_editor_selected_keyframes() if has_graph_keys else []

    target_objects = []
    seen_objects = set()
    for plug in target_plugs:
        if "." not in plug:
            continue
        obj = plug.split(".", 1)[0]
        if obj in seen_objects:
            continue
        seen_objects.add(obj)
        target_objects.append(obj)

    if not target_objects:
        target_objects = selection_targets.get_selected_objects(orderedSelection=ordered_selection, long=long_names)

    selected_channels = []
    seen_channels = set()
    for plug in target_plugs:
        if "." not in plug:
            continue
        attr = plug.split(".", 1)[1]
        if attr in seen_channels:
            continue
        seen_channels.add(attr)
        selected_channels.append(attr)

    selected_curves = []
    seen_curves = set()
    for plug in target_plugs:
        curves = cmds.listConnections(plug, source=True, destination=False, type="animCurve") or []
        for curve in curves:
            if curve in seen_curves:
                continue
            seen_curves.add(curve)
            selected_curves.append(curve)

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
    selection = selection_targets.get_selected_objects()
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

    seleccion = selection_targets.get_selected_objects()
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


# Esta version esta simplificada y no mira si hay un rango seleccionado, de esta forma el callback
# es más rápido y actualiza sin dar problemas al rotar o mover el objeto


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
    chunk_opened = False
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
    tint_session = _begin_timeline_tint((int(shared_frames[0]), int(shared_frames[-1])), "share_keys")
    preserve_curve_shape = get_share_keys_mode() == SHARE_KEYS_MODE_PRESERVE_SHAPE

    try:
        toolCommon.open_undo_chunk(tool_id="share_keys", tooltip_template=helper.share_keys_tooltip_text)
        chunk_opened = True
        for objeto in objetos:
            for plug, existing_frames in object_plug_frames.get(objeto, {}).items():
                node_name, attribute_name = plug.split(".", 1)
                for frame in shared_frames:
                    if frame not in existing_frames:
                        set_keyframe_kwargs = {
                            "attribute": attribute_name,
                            "time": (frame,),
                        }
                        if preserve_curve_shape:
                            set_keyframe_kwargs["insert"] = True
                        cmds.setKeyframe(node_name, **set_keyframe_kwargs)
    finally:
        if chunk_opened:
            toolCommon.close_undo_chunk()
        if tint_session:
            tint_session.finish()


# ______________________________________ ReBlock Move


def reblock_move(*args):
    # Obtener la lista de objetos seleccionados
    objetos = selection_targets.get_selected_objects(long=True)  # Usar nombres largos para mayor precisión

    # Verificar que haya al menos un objeto seleccionado
    if len(objetos) < 1:
        return

    # Obtener las curvas de animación de los objetos seleccionados y sus shapes
    curvas = []
    objetos_procesados = set()  # Conjunto para almacenar nombres de objetos ya procesados

    for objeto in objetos:
        # Saltar objetos repetidos
        if objeto in objetos_procesados:
            continue
        objetos_procesados.add(objeto)

        # Obtener las curvas del transform node
        curvas_objeto = cmds.listConnections(objeto, type="animCurve")
        if curvas_objeto:
            curvas.extend(curvas_objeto)

        # Obtener las curvas del shape node
        shapes = cmds.listRelatives(objeto, shapes=True, fullPath=True)
        if shapes:
            for shape in shapes:
                curvas_shape = cmds.listConnections(shape, type="animCurve")
                if curvas_shape:
                    curvas.extend(curvas_shape)

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
    objetos = selection_targets.get_selected_objects()

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


def bake_animation(bake_interval=1, window=None):
    bake_title, bake_tooltip = BAKE_UNDO_HELP.get(bake_interval, ("Bake Animation", helper.bake_animation_custom_tooltip_text))
    tool_key = "bake_animation_{}".format(bake_interval) if bake_interval in BAKE_UNDO_HELP else "bake_animation_custom"
    toolCommon.open_undo_chunk(title=bake_title, tooltip_template=bake_tooltip)
    tint_session = None

    try:
        target_info = resolve_tool_targets(default_mode="all_animation", ordered_selection=True, long_names=True)
        selected_objects = target_info["target_objects"]
        selected_channels = target_info["selected_channels"]

        if not selected_objects:
            return wutil.make_inViewMessage("Select at least one object for baking")

        time_context = target_info["time_context"]
        start_frame, end_frame = time_context.timerange
        tint_session = _begin_timeline_tint(
            timerange=time_context.timerange,
            key=tool_key,
            owner=window,
        )

        # Hacer bake a las curvas de animación de los objetos seleccionados.
        bake_kwargs = dict(
            time=(start_frame, end_frame),
            sampleBy=bake_interval,
            preserveOutsideKeys=True,
            sparseAnimCurveBake=False,
            removeBakedAttributeFromLayer=False,
            bakeOnOverrideLayer=False,
            controlPoints=False,
            shape=True,
        )
        if selected_channels:
            bake_kwargs["attribute"] = selected_channels
        cmds.bakeResults(selected_objects, **bake_kwargs)

        # Cambiar las tangentes de las claves a stepped.
        curves_to_update = list(dict.fromkeys(target_info["selected_curves"]))
        if not curves_to_update:
            for obj in selected_objects:
                anim_curves = list(set(cmds.listConnections(obj, type="animCurve") or []))
                curves_to_update.extend(anim_curves)

        for curve in curves_to_update:
            cmds.keyTangent(
                curve,
                edit=True,
                time=(start_frame, end_frame),
                inTangentType="stepnext",
                outTangentType="step",
            )

    except Exception as e:
        cmds.warning("An error occurred: {}".format(e))

    finally:
        if tint_session:
            tint_session.finish()
        # Cerrar el chunk de undo
        toolCommon.close_undo_chunk()

    if window:
        window.close()


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
    selected = selection_targets.get_selected_objects()

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
    selected = selection_targets.get_selected_objects()

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


def __get_move_keyframes_offset():
    try:
        from TheKeyMachine.core import trigger

        return trigger.nudge_value()
    except Exception:
        pass
    return 1


def hotkey_move_keyframes_left():
    offset = __get_move_keyframes_offset()
    move_keyframes_in_range(-offset)


def hotkey_move_keyframes_right():
    offset = __get_move_keyframes_offset()
    move_keyframes_in_range(offset)


# _____


def insert_inbetween(count=1, *args):
    _relative_timechange(count)


def remove_inbetween(count=1, *args):
    _relative_timechange(-count)


def _relative_timechange(count):
    if not cmds.keyframe(query=True):
        return
    count = int(count)
    current = cmds.currentTime(q=True)
    cmds.keyframe(time=("{}:".format(current + 1),), relative=True, timeChange=count, option="over")


def move_keyframes_in_range(*args):
    if args and isinstance(args[0], (int, float)):
        offset = int(args[0])
    else:
        offset = __get_move_keyframes_offset()
        if args and args[0] == -1:
            offset = -offset

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

    toolCommon.open_undo_chunk(
        title="Nudge Keys Right" if offset > 0 else "Nudge Keys Left",
        tooltip_template=helper.nudge_keyright_b_widget_tooltip_text if offset > 0 else helper.nudge_keyleft_b_widget_tooltip_text,
    )
    try:
        if target_info["has_graph_keys"]:
            cmds.keyframe(edit=True, animation="keys", relative=True, includeUpperBound=True, option="over", timeChange=offset)
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
    finally:
        toolCommon.close_undo_chunk()


# _____________________________________________________ Key Tools  Customgraph _______________________________________________________________#


def deleteStaticCurves():
    # Obtener los objetos seleccionados con sus nombres completos una sola vez
    selected_objects = selection_targets.get_selected_objects(long=True)

    # También incluir las formas de los objetos seleccionados
    selected_shapes = []
    for obj in selected_objects:
        shapes = cmds.listRelatives(obj, shapes=True, fullPath=True)
        if shapes:
            selected_shapes.extend(shapes)

    # Fusionar las listas de objetos y formas
    all_selected = list(set(selected_objects + selected_shapes))

    # Recopilar todas las curvas de animación para todos los objetos seleccionados una sola vez
    curves_to_delete = []
    for obj in all_selected:
        anim_curves = cmds.listConnections(obj, type="animCurve", connections=False, plugs=False) or []
        for curve in anim_curves:
            # keyframes = cmds.keyframe(curve, query=True, timeChange=True) or []
            values = cmds.keyframe(curve, query=True, valueChange=True) or []
            if len(set(values)) == 1:  # Usar un conjunto para buscar valores únicos
                curves_to_delete.append(curve)

    # Eliminar todas las curvas recopiladas en un solo comando
    if curves_to_delete:
        cmds.delete(curves_to_delete)


def snapKeyframes():
    # Obtén la selección actual
    selected_objects = selection_targets.get_selected_objects()

    for obj in selected_objects:
        if not cmds.attributeQuery("translateX", node=obj, exists=True):
            print(f"Object {obj} is not animatable")
            continue

        # Obtén las curvas de animación para el objeto
        anim_curves = cmds.listConnections(obj, type="animCurve")

        # Si el objeto no tiene curvas de animación, continúa con el siguiente objeto
        if not anim_curves:
            continue

        for curve in anim_curves:
            # Obtén todos los keyframes para la curva
            keyframes = cmds.keyframe(curve, query=True)

            # Si no hay keyframes, continúa con la siguiente curva
            if not keyframes:
                continue

            for key in keyframes:
                # Si el keyframe no está en un fotograma completo, redondea al más cercano
                if not key.is_integer():
                    # Almacena el valor del keyframe antes de eliminarlo
                    value = cmds.keyframe(curve, time=(key, key), query=True, valueChange=True)

                    # Almacena las tangentes del keyframe antes de eliminarlo
                    in_tangent = cmds.keyTangent(curve, time=(key,), query=True, inTangentType=True)
                    out_tangent = cmds.keyTangent(curve, time=(key,), query=True, outTangentType=True)

                    # Borra el keyframe
                    cmds.cutKey(curve, time=(key, key))

                    # Redondea el fotograma
                    rounded_key = round(key)

                    # Establece el valor del keyframe borrado al nuevo fotograma redondeado
                    cmds.setKeyframe(curve, time=rounded_key, value=value[0])

                    # Establece las tangentes del keyframe redondeado
                    cmds.keyTangent(curve, time=(rounded_key,), edit=True, inTangentType=in_tangent[0])
                    cmds.keyTangent(curve, time=(rounded_key,), edit=True, outTangentType=out_tangent[0])


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


def match_keys():
    # Obtener las curvas seleccionadas
    selected_curves = cmds.keyframe(selected=True, query=True, name=True)

    # Verificar si hay al menos dos curvas seleccionadas
    if not selected_curves:
        return wutil.make_inViewMessage("Select at least two animation curves")

    else:
        # Obtener los keyframes de la primera curva seleccionada
        first_curve_times = cmds.keyframe(selected_curves[-1], query=True, timeChange=True)
        first_curve_values = cmds.keyframe(selected_curves[-1], query=True, valueChange=True)

        # Para cada curva restante, ajustar los keyframes para que coincidan con la primera curva
        for curve in selected_curves[:-1]:
            # Obtener los keyframes actuales de la curva
            curve_times = cmds.keyframe(curve, query=True, timeChange=True)

            # Borrar keyframes que no están en la primera curva
            extra_frames = set(curve_times) - set(first_curve_times)
            for frame in extra_frames:
                cmds.cutKey(curve, time=(frame, frame))

            # Agregar o ajustar keyframes para que coincidan con la primera curva
            for time, value in zip(first_curve_times, first_curve_values):
                cmds.setKeyframe(curve, time=time, value=value)


def flipCurves():
    selectedCurves = cmds.keyframe(n=1, sl=1, q=1)

    if selectedCurves is not None:
        for curve in selectedCurves:
            # Obtener todos los valores de keyframes para la curva
            values = cmds.keyframe(curve, query=True, valueChange=True)

            # Calcular el punto medio de los keyframes
            pivot = (min(values) + max(values)) / 2

            # Realizar el flip usando el punto medio como pivote
            cmds.scaleKey(curve, valueScale=-1, valuePivot=pivot)


def flipKeyGroup():
    # Obtener las curvas con keyframes seleccionados
    selectedCurves = cmds.keyframe(q=True, name=True, sl=True)

    if selectedCurves is not None:
        for curve in selectedCurves:
            # Obtener los tiempos de los keyframes seleccionados para la curva
            selected_times = cmds.keyframe(curve, query=True, timeChange=True, sl=True)

            # Obtener los valores de los keyframes seleccionados en base a los tiempos
            selected_values = [cmds.keyframe(curve, query=True, time=(t, t), valueChange=True)[0] for t in selected_times]

            # Calcular el punto medio de los keyframes seleccionados
            pivot = (min(selected_values) + max(selected_values)) / 2

            # Realizar el flip de los keyframes seleccionados usando el punto medio como pivote
            for t in selected_times:
                value = cmds.keyframe(curve, query=True, time=(t, t), valueChange=True)[0]
                flipped_value = pivot + (pivot - value)  # Calcula el valor opuesto en relación al pivot
                cmds.keyframe(curve, edit=True, time=(t, t), valueChange=flipped_value)
    else:
        return wutil.make_inViewMessage("Select at least one keyframe in Graph Editor")


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


def mod_overlap_animation(*args):
    # Get the current state of the modifiers
    mods = runtime.get_modifier_mask()
    shift_pressed = bool(mods & 1)

    if shift_pressed:
        overlap_backward()
    else:
        overlap_forward()


def overlap_forward(*args):
    frames_to_move = 1

    # Obtén el orden de los objetos seleccionados
    selected_objects_order = selection_targets.get_selected_objects(orderedSelection=True, long=True)
    # Intenta obtener las curvas seleccionadas del Graph Editor
    selected_anim_curves = getSelectedCurves()

    # Si no hay curvas seleccionadas en el Graph Editor, obtén las curvas de los canales seleccionados
    if not selected_anim_curves:
        selected_channels = get_selected_channels()

        # Si no hay canales seleccionados, muestra un mensaje al usuario y termina la ejecución
        if not selected_channels:
            return wutil.make_inViewMessage("Select animation curves or channels in the Channel Box")

        selected_anim_curves = [
            cmds.listConnections(f"{obj}.{channel}", type="animCurve")[0]
            for obj in selected_objects_order
            for channel in selected_channels
            if cmds.listConnections(f"{obj}.{channel}", type="animCurve")
        ]

    # Elimina los duplicados de la lista manteniendo el orden original
    seen = set()
    selected_anim_curves = [x for x in selected_anim_curves if x not in seen and not seen.add(x)]

    # Si hay curvas seleccionadas...
    if selected_anim_curves:
        for i, curve in enumerate(selected_anim_curves):
            cmds.keyframe(curve, edit=True, includeUpperBound=True, relative=True, option="over", timeChange=i * frames_to_move)


def overlap_backward(*args):
    frames_to_move = -1

    # Obtén el orden de los objetos seleccionados
    selected_objects_order = selection_targets.get_selected_objects(orderedSelection=True, long=True)

    # Intenta obtener las curvas seleccionadas del Graph Editor
    selected_anim_curves = getSelectedCurves()

    # Si no hay curvas seleccionadas en el Graph Editor, obtén las curvas de los canales seleccionados
    if not selected_anim_curves:
        selected_channels = get_selected_channels()

        # Si no hay canales seleccionados, muestra un mensaje al usuario y termina la ejecución
        if not selected_channels:
            return wutil.make_inViewMessage("Select animation curves or channels in the Channel Box")

        selected_anim_curves = [
            cmds.listConnections(f"{obj}.{channel}", type="animCurve")[0]
            for obj in selected_objects_order
            for channel in selected_channels
            if cmds.listConnections(f"{obj}.{channel}", type="animCurve")
        ]

    # Elimina los duplicados de la lista manteniendo el orden original
    seen = set()
    selected_anim_curves = [x for x in selected_anim_curves if x not in seen and not seen.add(x)]

    # Si hay curvas seleccionadas...
    if selected_anim_curves:
        for i, curve in enumerate(selected_anim_curves):
            cmds.keyframe(curve, edit=True, includeUpperBound=True, relative=True, option="over", timeChange=i * frames_to_move)


# __________________________________________________ Iso / Mute / Lock ____________________________________________________________#


def isolateCurve():
    # Obtén las curvas seleccionadas en el Graph Editor
    selected_objects = selection_targets.get_graph_editor_outliner_items()

    if not selected_objects:
        cmds.warning("There are not selected curves in Graph Editor")
    else:
        for s in selected_objects:
            mel.eval("isolateAnimCurve true {} {};".format(selection_targets.GRAPH_EDITOR_OUTLINER, selection_targets.GRAPH_EDITOR))


def toggleMute():
    # Obtener las curvas seleccionadas en el Graph Editor
    selected_curves = selection_targets.get_graph_editor_outliner_items()

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
    selected_objects = selection_targets.get_graph_editor_outliner_items()

    # Si no hay objetos seleccionados, lanza un error
    if not selected_objects:
        cmds.warning("There are not selected curves in Graph Editor")
        return

    # Por cada objeto seleccionado
    for obj in selected_objects:
        # Obtén las curvas de animación de este objeto
        anim_curves = cmds.listConnections(obj, type="animCurve")

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


def default_objects_mods(*args):
    # Get the current state of the modifiers
    mods = runtime.get_modifier_mask()
    shift_pressed = bool(mods & 1)
    ctrl_pressed = bool(mods & 4)

    if shift_pressed:
        default_object_values(default_translations=True)
    elif ctrl_pressed:
        default_object_values(default_rotations=True)
    else:
        default_object_values()


def save_default_values(*args):
    # Obtener objetos seleccionados
    objetos_seleccionados = selection_targets.get_selected_objects(long=True)

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
    objetos_seleccionados = selection_targets.get_selected_objects(long=True)

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
    if default_trs:
        title = "Reset Translation Rotation Scale"
        tooltip_template = helper.default_trs_tooltip_text
    elif default_scales:
        title = "Reset Scales"
        tooltip_template = helper.default_scales_tooltip_text
    elif default_rotations:
        title = "Reset Rotation"
        tooltip_template = helper.default_rotations_tooltip_text
    elif default_translations:
        title = "Reset Translation"
        tooltip_template = helper.default_translations_tooltip_text
    else:
        title = None
        tooltip_template = helper.default_values_tooltip_text

    toolCommon.open_undo_chunk(
        tool_id="default_objects_mods",
        title=title,
        tooltip_template=tooltip_template,
    )
    tint_session = None
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
        tint_session = _begin_timeline_context_tint("current_frame", "default_objects_mods")

        selected_objects = target_info["target_objects"]
        target_plugs = target_info["target_plugs"]

        if time_context.mode == "graph_editor_keys":
            for curve, frame in target_info["selected_keyframes"]:
                target_plugs = cmds.listConnections(curve + ".output", plugs=True, source=False, destination=True) or []
                if not target_plugs:
                    continue
                obj, attr = target_plugs[0].split(".", 1)
                if default_translations and not attr.startswith("translate"):
                    continue
                if default_rotations and not attr.startswith("rotate"):
                    continue
                if default_scales and not attr.startswith("scale"):
                    continue
                if not any((default_translations, default_rotations, default_scales)):
                    pass
                elif not (
                    (default_translations and attr.startswith("translate"))
                    or (default_rotations and attr.startswith("rotate"))
                    or (default_scales and attr.startswith("scale"))
                ):
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
            if default_translations and not attr.startswith("translate"):
                continue
            if default_rotations and not attr.startswith("rotate"):
                continue
            if default_scales and not attr.startswith("scale"):
                continue
            if any((default_translations, default_rotations, default_scales)) and not (
                (default_translations and attr.startswith("translate"))
                or (default_rotations and attr.startswith("rotate"))
                or (default_scales and attr.startswith("scale"))
            ):
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
        if tint_session:
            tint_session.finish()
        if selected_objects:
            cmds.select(selected_objects, replace=True)
        else:
            cmds.select(clear=True)
        toolCommon.close_undo_chunk()


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
    selected_curves = selection_targets.get_graph_editor_outliner_items()

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
    selected_objects = selection_targets.get_selected_objects()
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
        mel.eval("isolateAnimCurve true {} {};".format(selection_targets.GRAPH_EDITOR_OUTLINER, selection_targets.GRAPH_EDITOR))
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


def selectOppositeHandler(*args):
    mods = runtime.get_modifier_mask()
    shift_pressed = bool(mods & 1)

    if shift_pressed:
        addSelectOpposite(args)
    else:
        selectOpposite(args)


def selectOpposite(*args):
    global MIRROR_PATTERNS

    selected_objects = selection_targets.get_selected_objects()
    opposite_controls = []

    for obj in selected_objects:
        opposite_obj = find_opposite_name(obj)
        if opposite_obj and cmds.objExists(opposite_obj):
            opposite_controls.append(opposite_obj)

    if opposite_controls:
        cmds.select(opposite_controls)


def addSelectOpposite(*args):
    global MIRROR_PATTERNS

    selected_objects = selection_targets.get_selected_objects()
    opposite_controls = []

    for obj in selected_objects:
        opposite_obj = find_opposite_name(obj)
        if opposite_obj and cmds.objExists(opposite_obj):
            opposite_controls.append(opposite_obj)

    if opposite_controls:
        cmds.select(opposite_controls, add=True)


# ___________________________ Copy Opposite _____________________________________


def copyOpposite(*args):
    toolCommon.open_undo_chunk(tool_id="opposite_copy")

    try:
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

        selected_objects = selection_targets.get_selected_objects()

        for obj in selected_objects:
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

    except Exception as e:
        cmds.warning("Error during copy: {}".format(str(e)))
    finally:
        toolCommon.close_undo_chunk()


# ________________________________________________________________ MIRROR _______________________________________________________________________ #


def load_exceptions():
    mirror_exceptions_file_path = general.get_mirror_exceptions_file()
    if os.path.exists(mirror_exceptions_file_path):
        with open(mirror_exceptions_file_path, "r") as file:
            return json.load(file)
    else:
        return {}


def mirror(*args):
    toolCommon.open_undo_chunk(tool_id="mirror")

    try:
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
            selected_controls = selection_targets.get_selected_objects()

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
    except Exception as e:
        cmds.warning("Error during mirroring: {}".format(str(e)))
    finally:
        toolCommon.close_undo_chunk()


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
        selected_controls = selection_targets.get_selected_objects()

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


# _____________________________________ add exception


def add_mirror_invert_exception(*args):
    def get_selected_channels():
        main_channel_box = mel.eval("global string $gChannelBoxName; $temp=$gChannelBoxName;")
        selected_channels = cmds.channelBox(main_channel_box, query=True, selectedMainAttributes=True)
        return selected_channels

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
        selected_controls = selection_targets.get_selected_objects()
        selected_channels = get_selected_channels()

        if selected_controls and selected_channels:
            add_exceptions_to_json(selected_controls, selected_channels, mirror_exceptions_file_path)
            cmds.warning("Exception created")
        else:
            wutil.make_inViewMessage("Select controls and channels to create an exception")

    create_mirror_exception()


def add_mirror_keep_exception(*args):
    def get_selected_channels():
        main_channel_box = mel.eval("global string $gChannelBoxName; $temp=$gChannelBoxName;")
        selected_channels = cmds.channelBox(main_channel_box, query=True, selectedMainAttributes=True)
        return selected_channels

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
        selected_controls = selection_targets.get_selected_objects()
        selected_channels = get_selected_channels()

        if selected_controls and selected_channels:
            add_exceptions_to_json(selected_controls, selected_channels, mirror_exceptions_file_path)
            cmds.warning("Exception created")
        else:
            wutil.make_inViewMessage("Select controls and channels to create an exception")

    create_mirror_exception()


# _____________________________________ remove exception


def remove_mirror_invert_exception(*args):
    def get_selected_channels():
        main_channel_box = mel.eval("global string $gChannelBoxName; $temp=$gChannelBoxName;")
        selected_channels = cmds.channelBox(main_channel_box, query=True, selectedMainAttributes=True)
        return selected_channels

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
        selected_controls = selection_targets.get_selected_objects()
        selected_channels = get_selected_channels()

        if selected_controls and selected_channels:
            remove_exceptions_from_json(selected_controls, selected_channels, mirror_exceptions_file_path)
            print("Exception removed")
        else:
            wutil.make_inViewMessage("Select controls and channels to remove exceptions")

    remove_mirror_exceptions()


# ______________________________________________________COPY PASTE ANIMATION ______________________________________________________________________________#


def copy_animation(*args):
    def get_animated_channels(control):
        animated_channels = []
        attributes = cmds.listAttr(control, keyable=True)
        for attr in attributes:
            if cmds.getAttr(f"{control}.{attr}", se=True):  # se = settable
                connections = cmds.listConnections(f"{control}.{attr}", s=True, d=False)
                if connections:
                    animated_channels.append(attr)
        return animated_channels

    # Función para guardar la animación en un archivo JSON
    def save_animation_to_json(json_file_path, animation_data):
        # Asegurar que la carpeta donde se guardará el archivo exista
        os.makedirs(os.path.dirname(json_file_path), exist_ok=True)

        with open(json_file_path, "w") as json_file:
            json.dump(animation_data, json_file, indent=4)

    selected_objects = selection_targets.get_selected_objects()

    if not selected_objects:
        return

    time_context = get_working_time_context(default_mode="all_animation")
    animation_data = {}
    tint_session = None

    try:
        # Procesar cada objeto seleccionado
        for control in selected_objects:
            control_name = control.rsplit(":", 1)[-1]  # Eliminar namespace
            animated_channels = get_animated_channels(control)

            # Obtener la animación de los canales animados
            animation_data[control_name] = {}
            for channel in animated_channels:
                if time_context.mode == "graph_editor_keys":
                    selected_frames = set(time_context.frames)
                    keyframes = cmds.keyframe(f"{control}.{channel}", query=True) or []
                    keyframes = [frame for frame in keyframes if int(frame) in selected_frames]
                    values = [cmds.keyframe(f"{control}.{channel}", query=True, vc=True, time=(frame, frame))[0] for frame in keyframes]
                elif time_context.mode == "time_slider_range":
                    keyframes = cmds.keyframe(
                        f"{control}.{channel}",
                        query=True,
                        time=(time_context.start_frame, time_context.end_frame),
                    )
                    values = cmds.keyframe(
                        f"{control}.{channel}",
                        query=True,
                        vc=True,
                        time=(time_context.start_frame, time_context.end_frame),
                    )
                else:
                    keyframes = cmds.keyframe(f"{control}.{channel}", query=True)
                    values = cmds.keyframe(f"{control}.{channel}", query=True, vc=True)
                animation_data[control_name][channel] = {"keyframes": keyframes, "values": values}

        json_file_path = general.get_copy_animation_file()

        save_animation_to_json(json_file_path, animation_data)

        tint_range = None
        if time_context.mode == "time_slider_range":
            tint_range = time_context.timerange
            clear_timeslider_selection()
        elif time_context.mode == "all_animation":
            tint_range = timelineWidgets.get_playback_range()
        else:
            tint_range = timelineWidgets.get_animation_data_timerange(animation_data)

        if tint_range:
            tint_session = _begin_timeline_tint(
                timerange=tint_range,
                key="copy_animation",
            )

        wutil.make_inViewMessage("Animation saved")
    except Exception as e:
        cmds.warning(f"Error saving animation: {e}")
    finally:
        if tint_session:
            tint_session.finish()


# PASTE ANIMATION ___________________________________________________________________________


def paste_animation(*args):
    def apply_animation_from_json(json_file_path, selected_objects):
        # Leer el archivo JSON
        with open(json_file_path, "r") as json_file:
            animation_data = json.load(json_file)

        # Aplicar animación a los objetos seleccionados
        for control in selected_objects:
            control_name = control.rsplit(":", 1)[-1]  # Eliminar namespace

            if control_name in animation_data:
                for channel, anim_data in animation_data[control_name].items():
                    # Borrar animación existente
                    cmds.cutKey(control, time=(0, 10000), attribute=channel, option="keys")

                    # Aplicar nueva animación
                    for frame, value in zip(anim_data["keyframes"], anim_data["values"]):
                        cmds.setKeyframe(control, time=frame, attribute=channel, value=value)
        return timelineWidgets.get_animation_data_timerange(animation_data)

    # Obtener los objetos seleccionados
    selected_objects = selection_targets.get_selected_objects()

    if not selected_objects:
        return

    json_file_path = general.get_copy_animation_file()

    # Aplicar animación a los objetos seleccionados
    tint_session = None
    try:
        paste_range = apply_animation_from_json(json_file_path, selected_objects)
        if paste_range:
            tint_session = _begin_timeline_tint(
                timerange=paste_range,
                key="paste_animation",
            )
    finally:
        if tint_session:
            tint_session.finish()

    wutil.make_inViewMessage("Animation restored")


# PASTE INSERT _________________________________________________________________________


def paste_insert_animation(*args):
    def apply_animation_from_json(json_file_path, selected_objects, insert_time):
        # Leer el archivo JSON
        with open(json_file_path, "r") as json_file:
            animation_data = json.load(json_file)

        # Aplicar animación a los objetos seleccionados
        for control in selected_objects:
            control_name = control.rsplit(":", 1)[-1]  # Eliminar namespace

            if control_name in animation_data:
                for channel, anim_data in animation_data[control_name].items():
                    if anim_data["keyframes"]:
                        # Calcular la diferencia de tiempo
                        time_diff = insert_time - anim_data["keyframes"][0]

                        # Insertar animación ajustada
                        for frame, value in zip(anim_data["keyframes"], anim_data["values"]):
                            adjusted_frame = frame + time_diff
                            cmds.setKeyframe(control, time=adjusted_frame, attribute=channel, value=value)

    # Obtener los objetos seleccionados y el tiempo actual
    selected_objects = selection_targets.get_selected_objects()
    current_time = cmds.currentTime(query=True)

    if not selected_objects:
        return

    json_file_path = general.get_copy_animation_file()

    # Aplicar animación a los objetos seleccionados en el tiempo actual
    apply_animation_from_json(json_file_path, selected_objects, current_time)

    wutil.make_inViewMessage("Animation inserted")


# PASTE OPPOSITE ________________________________________________________________________


def paste_opposite_animation(*args):
    mirror_exceptions_file_path = general.get_mirror_exceptions_file()

    # ATTRIBUTES_TO_IGNORE = {"tag"}

    # Cargar excepciones
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

    json_file_path = general.get_copy_animation_file()

    with open(json_file_path, "r") as json_file:
        animation_data = json.load(json_file)

    for control_name, anim_data in animation_data.items():
        mirror_control_name = find_mirror_control(control_name)

        if mirror_control_name:
            full_mirror_control_name = next((c for c in cmds.ls() if c.endswith(mirror_control_name)), None)
            if not full_mirror_control_name:
                continue

            for channel, channel_data in anim_data.items():
                mirrored_values = [mirror_value(channel, v) for v in channel_data["values"]]
                cmds.cutKey(full_mirror_control_name, time=(0, 10000), attribute=channel, option="keys")
                for frame, value in zip(channel_data["keyframes"], mirrored_values):
                    cmds.setKeyframe(full_mirror_control_name, time=frame, attribute=channel, value=value)

    wutil.make_inViewMessage("Mirror Animation Restored")


def paste_animation_to(source_control_name=None, replace=True, insert_at_current=False, *args, **kwargs):
    # Utilidades locales
    def _short(name):
        # quita namespace si lo hay
        return name.rsplit(":", 1)[-1]

    def _attr_exists_and_settable(node, attr):
        if not cmds.objExists(node):
            return False
        full_attr = f"{node}.{attr}"
        if not cmds.objExists(full_attr):
            return False
        try:
            # settable=True y no locked
            return cmds.getAttr(full_attr, se=True) and not cmds.getAttr(full_attr, lock=True)
        except Exception:
            return False

    def _load_animation(json_file_path):
        with open(json_file_path, "r") as f:
            return json.load(f)

    # Destinos: selección actual
    targets = selection_targets.get_selected_objects()
    if not targets:
        return wutil.make_inViewMessage("Select at least one destination control")

    # Cargar JSON
    json_file_path = general.get_copy_animation_file()
    if not os.path.exists(json_file_path):
        cmds.warning("No animation file found. Please copy animation first")
        return

    try:
        animation_data = _load_animation(json_file_path)
    except Exception as e:
        cmds.warning("Error reading animation file: {}".format(e))
        return

    if not isinstance(animation_data, dict) or not animation_data:
        cmds.warning("Animation file is empty or invalid")
        return

    # Determinar ORIGEN
    available_sources = list(animation_data.keys())

    if source_control_name is None:
        if len(available_sources) == 1:
            source_control_name = available_sources[0]
        else:
            cmds.warning(
                "Multiple sources found in animation file. Please specify source_control_name. Available: {}".format(
                    ", ".join(available_sources)
                )
            )
            return
    else:
        # Aceptar tanto con como sin namespace; normalizamos a corto
        source_control_name = _short(source_control_name)

    # Buscar el nombre EXACTO en el JSON por comparación de cortos
    matched_source = None
    for k in available_sources:
        if _short(k) == source_control_name:
            matched_source = k
            break

    if matched_source is None:
        cmds.warning(
            "Source control '{}' not found in animation file. Available: {}".format(source_control_name, ", ".join(available_sources))
        )
        return

    src_channels = animation_data.get(matched_source, {})
    if not src_channels:
        cmds.warning("No channel data found for source '{}'.".format(matched_source))
        return

    # Calcular desplazamiento temporal si insertamos en el tiempo actual
    time_shift = 0.0
    if insert_at_current:
        # Primer key del primer canal que tenga keys
        first_key_time = None
        for ch, data in src_channels.items():
            kfs = data.get("keyframes") or []
            if kfs:
                t0 = kfs[0]
                if first_key_time is None or (t0 is not None and t0 < first_key_time):
                    first_key_time = t0
        if first_key_time is not None:
            current = cmds.currentTime(query=True)
            time_shift = current - first_key_time

    # Aplicar a cada destino seleccionado
    total_keys_set = 0
    for dst in targets:
        # Para logs legibles, también mostramos el corto
        # dst_short = _short(dst)

        for channel, anim_data in src_channels.items():
            keyframes = anim_data.get("keyframes") or []
            values = anim_data.get("values") or []

            if not keyframes or not values:
                continue

            if not _attr_exists_and_settable(dst, channel):
                # Canal no existe en el destino; lo saltamos
                continue

            if replace:
                try:
                    cmds.cutKey(dst, time=(0, 1e6), attribute=channel, option="keys")
                except Exception:
                    pass

            # Pegar keys (con posible desplazamiento)
            for frame, value in zip(keyframes, values):
                t = frame + time_shift
                try:
                    cmds.setKeyframe(dst, time=t, attribute=channel, value=value)
                    total_keys_set += 1
                except Exception as e:
                    # Si un key falla, seguimos con los demás canales
                    import TheKeyMachine.mods.reportMod as report

                    report.report_detected_exception(e, context="paste animation set key")

    if total_keys_set == 0:
        cmds.warning("No keys were pasted. Check that destination controls have the needed attributes and that the source has keyframes.")
    else:
        mode = "inserted at current time" if insert_at_current else "pasted"
        repl = " (replaced existing keys)" if replace else ""
        cmds.warning(
            "Animation {} from '{}' to {} target(s){} — {} keys set.".format(
                mode, _short(matched_source), len(targets), repl, total_keys_set
            )
        )


# COPY POSE ________________________________________________________________________


def copy_pose(*args):
    def save_pose_to_json(json_file_path, pose_data):
        os.makedirs(os.path.dirname(json_file_path), exist_ok=True)
        with open(json_file_path, "w") as json_file:
            json.dump(pose_data, json_file, indent=4)

    selected_objects = selection_targets.get_selected_objects()

    if not selected_objects:
        return

    pose_data = {}
    tint_session = _begin_timeline_context_tint("current_frame", "copy_pose")

    try:
        # Procesar cada objeto seleccionado
        for control in selected_objects:
            control_name = control.rsplit(":", 1)[-1]  # Eliminar namespace
            attributes = cmds.listAttr(control, keyable=True)

            if attributes is None:
                continue  # Si no hay atributos keyable, continuar con el siguiente objeto

            pose_data[control_name] = {}
            for attr in attributes:
                if not cmds.getAttr(f"{control}.{attr}", lock=True) and cmds.getAttr(f"{control}.{attr}", keyable=True):
                    try:
                        values = cmds.getAttr(f"{control}.{attr}")
                        pose_data[control_name][attr] = values
                    except Exception as e:
                        import TheKeyMachine.mods.reportMod as report

                        report.report_detected_exception(e, context="copy pose attribute read")
                        pass  # Ignorar atributos que no pueden ser leídos

        json_file_path = general.get_copy_paste_pose_file()

        save_pose_to_json(json_file_path, pose_data)

        wutil.make_inViewMessage("Pose saved")
    finally:
        tint_session.finish()


# PASTE POSE _____________________________________________________________


def paste_pose(*args):
    def is_valid_attribute_value(value):
        """
        Valida si el valor del atributo es estándar (numérico o lista numérica)
        y no contiene caracteres inusuales como '#'.
        """
        if isinstance(value, (float, int)):
            return True
        if isinstance(value, list) and all(isinstance(v, (float, int)) for v in value):
            return True
        if isinstance(value, str) and not re.search(r"[# ]", value):
            return True
        return False

    def apply_pose_from_json(json_file_path, selected_objects):
        # Leer el archivo JSON
        with open(json_file_path, "r") as json_file:
            pose_data = json.load(json_file)

        # Aplicar pose a los objetos seleccionados
        for control in selected_objects:
            control_name = control.rsplit(":", 1)[-1]  # Eliminar namespace

            if control_name in pose_data:
                for attr, value in pose_data[control_name].items():
                    # Validar el valor del atributo
                    if not is_valid_attribute_value(value):
                        continue

                    # Aplicar valor al atributo
                    if not cmds.getAttr(f"{control}.{attr}", lock=True):
                        try:
                            if isinstance(value, list):
                                cmds.setAttr(f"{control}.{attr}", *value)
                            else:
                                cmds.setAttr(f"{control}.{attr}", value)
                        except RuntimeError as e:
                            import TheKeyMachine.mods.reportMod as report

                            report.report_detected_exception(e, context="paste pose attribute set")

    # Obtener los objetos seleccionados
    selected_objects = selection_targets.get_selected_objects()

    if not selected_objects:
        return

    json_file_path = general.get_copy_paste_pose_file()
    tint_session = _begin_timeline_context_tint("current_frame", "paste_pose")

    try:
        # Aplicar pose a los objetos seleccionados
        apply_pose_from_json(json_file_path, selected_objects)

        wutil.make_inViewMessage("Pose pasted")
    finally:
        tint_session.finish()


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
    curveNames = getSelectedCurves()

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

    for plug in target_info.get("target_plugs") or []:
        plug_curves = cmds.listConnections(plug, source=True, destination=False, type="animCurve") or []
        for curve in plug_curves:
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
        return wutil.make_inViewMessage("No animation keys available for bouncy tangents.")

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
