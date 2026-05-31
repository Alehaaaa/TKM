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

import maya.cmds as cmds
import maya.mel as mel
from maya import OpenMaya as om

from TheKeyMachine.Qt import QtCore, QtGui, QtWidgets


import json
import os
import sys
import math
import importlib

# ----------------------------------------------------------------------


import TheKeyMachine.mods.keyToolsMod as keyTools
import TheKeyMachine.mods.generalMod as general
import TheKeyMachine.mods.helperMod as helper
from TheKeyMachine.data import icons
import TheKeyMachine.widgets.customDialogs as customDialogs
import TheKeyMachine.widgets.customWidgets as cw
import TheKeyMachine.widgets.timeline as timelineWidgets
import TheKeyMachine.widgets.util as wutil
import TheKeyMachine.mods.selectionMod as selectionMod
from TheKeyMachine.tools import common as toolCommon


# -------------------------------------------------------------------------


global down_one_level
down_one_level_var = False


def _active_tint_color(key=None, default=None):
    if isinstance(key, str) and key.startswith("#"):
        return key

    if key:
        try:
            import TheKeyMachine.core.toolbox as toolbox

            color = toolbox.get_tool_tint_color(key)
            if color is not None:
                return color
        except Exception:
            pass

    if isinstance(default, str):
        return default if default.startswith("#") else None
    return default


def openCustomGraph():
    import TheKeyMachine.core.customGraph

    importlib.reload(TheKeyMachine.core.customGraph)
    TheKeyMachine.core.customGraph.openCustomGraph()


def delete_animation():
    # Obtener canales seleccionados
    target_info = keyTools.resolve_tool_targets(default_mode="all_animation", ordered_selection=True, long_names=True)
    selection = target_info["target_objects"]
    target_plugs = target_info["target_plugs"]
    selected_channels = target_info["selected_channels"]

    # Obtener selección actual
    if not selection and not target_plugs:
        return
    time_context = target_info["time_context"]
    tint_session = timelineWidgets.begin_timeline_context(
        default_mode="all_animation",
        color=_active_tint_color("delete_all_animation"),
        key="delete_all_animation",
    )

    try:
        if target_info["has_graph_keys"]:
            for curve, frame in target_info["selected_keyframes"]:
                cmds.cutKey(curve, time=(frame, frame), clear=True)
            return

        if target_plugs:
            cut_kwargs = {"clear": True}
            if time_context.mode == "time_slider_range":
                cut_kwargs["time"] = (time_context.start_frame, time_context.end_frame)
            for plug in target_plugs:
                cmds.cutKey(plug, **cut_kwargs)
            return

        cut_kwargs = {"clear": True}
        if selected_channels:
            cut_kwargs["attribute"] = selected_channels
        if time_context.mode == "time_slider_range":
            cut_kwargs["time"] = (time_context.start_frame, time_context.end_frame)

        for obj in selection:
            cmds.cutKey(obj, **cut_kwargs)
    finally:
        tint_session.finish()


def createLocator():
    selection = selectionMod.get_selected_objects()
    if selection:
        # Verificar si el grupo 'TheKeyMachine' existe, si no, crearlo
        if not cmds.objExists("TheKeyMachine"):
            general.create_TheKeyMachine_node()

        # Verificar si el grupo 'temp_locators' existe, si no, crearlo
        if not cmds.objExists("temp_locators"):
            cmds.group(em=True, name="temp_locators")
            # Hacer 'temp_locators' hijo de 'TheKeyMachine'
            cmds.parent("temp_locators", "TheKeyMachine")

        for i, obj in enumerate(selection):
            locator = cmds.spaceLocator()[0]
            cmds.matchTransform(locator, obj)

            cmds.setAttr(locator + ".overrideEnabled", 1)
            cmds.setAttr(locator + ".overrideColor", 13)

            cmds.setAttr(locator + ".localScaleZ", 5)
            cmds.setAttr(locator + ".localScaleX", 5)
            cmds.setAttr(locator + ".localScaleY", 5)

            locator = cmds.rename(locator, f"tkm_temp_locator_{i}")  # Renombrar el locator con un índice único y almacenar el nuevo nombre

            # Añadir el locator al grupo 'temp_locators'
            cmds.parent(locator, "temp_locators")
        cmds.select(selection)


def selectTempLocators(*args):
    # Buscar en la escena los objetos con el patrón 'tkm_temp_locator_*'
    potential_locators = cmds.ls("tkm_temp_locator_*")

    # Filtrar la lista para solo obtener objetos que terminen con un número
    locators = [loc for loc in potential_locators if loc.split("_")[-1].isdigit()]

    if locators:
        cmds.select(locators)


def deleteTempLocators(*args):
    if cmds.objExists("temp_locators"):
        # Lista todos los hijos del grupo 'temp_locators' y los borra
        potential_locators = cmds.ls("tkm_temp_locator_*")
        locators = [loc for loc in potential_locators if loc.split("_")[-1].isdigit()]
        if locators:
            cmds.delete(locators)


# ___________________________ Set Tangets _______________________________________


def _set_tangent_on_target(target, tangent_type, time_range, handle_mode="both"):
    kwargs = {"time": time_range}
    if handle_mode in ("both", "out"):
        kwargs["ott"] = tangent_type
    if handle_mode in ("both", "in"):
        if tangent_type == "step":
            if handle_mode == "in":
                kwargs["itt"] = "stepnext"
        else:
            kwargs["itt"] = tangent_type
    if len(kwargs) <= 1:
        return
    cmds.keyTangent(target, **kwargs)


def _normalize_curve_frames(curve_frames):
    frames = []
    for frame in curve_frames or []:
        try:
            frames.append(int(round(frame)))
        except Exception:
            continue
    return sorted(set(frames))


def _collect_target_curves(target_info):
    curves = []
    seen = set()

    for curve in target_info.get("selected_curves") or []:
        if curve and curve not in seen:
            seen.add(curve)
            curves.append(curve)

    target_plugs = target_info.get("target_plugs") or []
    if target_plugs:
        for plug in target_plugs:
            plug_curves = cmds.listConnections(plug, source=True, destination=False, type="animCurve") or []
            for curve in plug_curves:
                if curve and curve not in seen:
                    seen.add(curve)
                    curves.append(curve)
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


def _resolve_tangent_target_info():
    target_objects = selectionMod.get_selected_objects(orderedSelection=True, long=False)
    selected_channels = selectionMod.get_selected_channels() or []

    target_plugs = []
    selected_curves = []
    seen_curves = set()

    if selected_channels:
        for obj in target_objects:
            for attr in selected_channels:
                plug = "{}.{}".format(obj, attr)
                if not cmds.objExists(plug):
                    continue
                target_plugs.append(plug)
                curves = cmds.listConnections(plug, source=True, destination=False, type="animCurve") or []
                for curve in curves:
                    if curve and curve not in seen_curves:
                        seen_curves.add(curve)
                        selected_curves.append(curve)

    return {
        "target_plugs": target_plugs,
        "target_objects": target_objects,
        "selected_channels": selected_channels,
        "selected_curves": selected_curves,
    }


def _curve_frames_in_time_context(curve, time_context):
    if not curve or not time_context:
        return []

    if time_context.mode == "current_frame":
        return [int(cmds.currentTime(query=True))]

    try:
        curve_frames = cmds.keyframe(curve, query=True, time=time_context.timerange, timeChange=True) or []
    except Exception:
        curve_frames = []

    frames = _normalize_curve_frames(curve_frames)
    if time_context.mode == "graph_editor_keys":
        selected_frames = {int(frame) for frame in (time_context.frames or ())}
        if selected_frames:
            frames = [frame for frame in frames if frame in selected_frames]
    return frames


def _resolve_tangent_time_context(key_scope):
    default_mode = "all_animation" if key_scope == "all" else "current_frame"
    return timelineWidgets.resolve_time_context(default_mode=default_mode)


def _filter_tangent_targets_by_scope(targets, key_scope):
    scoped_targets = {curve: list(frames or []) for curve, frames in (targets or {}).items() if frames}
    if not scoped_targets:
        return {}

    if key_scope not in ("first", "last"):
        return scoped_targets

    all_frames = sorted({frame for frames in scoped_targets.values() for frame in frames})
    if not all_frames:
        return {}

    target_frame = all_frames[0] if key_scope == "first" else all_frames[-1]
    return {curve: [target_frame] for curve, frames in scoped_targets.items() if target_frame in frames}


def _collect_tangent_targets(key_scope="selection"):
    time_context = _resolve_tangent_time_context(key_scope)
    target_info = _resolve_tangent_target_info()
    if not target_info.get("target_objects") and not target_info.get("target_plugs"):
        return {}

    selected_keyframes = []
    if key_scope != "all" and time_context.mode == "graph_editor_keys":
        selected_keyframes = selectionMod.get_graph_editor_selected_keyframes()

    if selected_keyframes:
        frames_by_curve = {}
        for curve, frame in selected_keyframes:
            frames_by_curve.setdefault(curve, set()).add(int(frame))
        return _filter_tangent_targets_by_scope({curve: sorted(frames) for curve, frames in frames_by_curve.items() if frames}, key_scope)

    curves = _collect_target_curves(target_info)
    targets = {}
    for curve in curves:
        frames = _curve_frames_in_time_context(curve, time_context)
        if frames:
            targets[curve] = frames
    return _filter_tangent_targets_by_scope(targets, key_scope)


def _tangent_target_range(targets):
    frames = sorted({frame for curve_frames in (targets or {}).values() for frame in curve_frames})
    if not frames:
        return None
    return frames[0], frames[-1]


def setTangent(tangent_type, handle_mode="both", key_scope="selection", tint_color=None):
    time_context = _resolve_tangent_time_context(key_scope)
    targets = _collect_tangent_targets(key_scope=key_scope)
    if not targets:
        return wutil.make_inViewMessage("No animation curves available to set tangents.")

    timerange = time_context.timerange if key_scope == "all" else (_tangent_target_range(targets) or time_context.timerange)
    if not timerange:
        return wutil.make_inViewMessage("No animation keys available to set tangents.")

    tangent_tool_key = "tangent_{}".format(tangent_type)
    tint_session = timelineWidgets.begin_timeline_tint(
        timerange=timerange,
        color=tint_color or _active_tint_color(tangent_tool_key),
        key=tangent_tool_key,
    )
    try:
        for curve, frames in targets.items():
            for frame in frames:
                _set_tangent_on_target(curve, tangent_type, (frame, frame), handle_mode=handle_mode)
    finally:
        tint_session.finish()


def align_selected_objects(*args, pos=True, rot=True, scl=False):
    # Obtener los objetos seleccionados
    sel = selectionMod.get_selected_objects()

    # Asegurarse de que hay al menos dos objetos seleccionados
    if len(sel) < 2:
        return wutil.make_inViewMessage("Select at least two objects")

    # Obtener el objeto destino (último objeto en la lista de selección)
    target_obj = sel[-1]
    source_objs = sel[:-1]  # Todos los objetos excepto el último (objeto destino)

    # Obtener el tiempo actual
    current_time = cmds.currentTime(query=True)

    # Suspender la actualización de la vista
    cmds.refresh(suspend=True)

    try:
        # Obtener el rango de tiempo seleccionado
        time_range = selectionMod.get_selected_time_slider_range()

        # Crear una barra de progreso
        gMainProgressBar = mel.eval("$tmp = $gMainProgressBar")
        cmds.progressBar(gMainProgressBar, edit=True, beginProgress=True, isInterruptable=True, status="Alineando objetos...", maxValue=100)

        try:
            # Si hay un rango de tiempo seleccionado y no es igual al tiempo actual
            if time_range and time_range[0] != current_time:
                start_frame, end_frame = time_range[0], time_range[1]

                # Calcular el número total de frames en el rango
                total_frames = int(end_frame - start_frame + 1)

                # Iterar sobre cada frame en el rango y alinear los objetos
                for frame in range(int(start_frame), int(end_frame) + 1):
                    # Mover el tiempo actual al frame
                    cmds.currentTime(frame)

                    # Alinear los objetos fuente con el objeto destino en este frame
                    for source_obj in source_objs:
                        cmds.matchTransform(source_obj, target_obj, pos=pos, rot=rot, scl=scl)

                        # Definir un keyframe para el objeto fuente en este punto en el tiempo
                        cmds.setKeyframe(source_obj)

                    # Actualizar la barra de progreso
                    cmds.progressBar(gMainProgressBar, edit=True, progress=int((frame - start_frame) / total_frames * 100))

            else:
                # Si no hay un rango de tiempo seleccionado o es igual al tiempo actual, alinear en el tiempo actual
                for source_obj in source_objs:
                    cmds.matchTransform(source_obj, target_obj, pos=pos, rot=rot, scl=scl)
        finally:
            # Terminar la barra de progreso
            cmds.progressBar(gMainProgressBar, edit=True, endProgress=True)
    finally:
        # Reanudar la actualización de la vista
        cmds.refresh(suspend=False)


# ___________________________ iso Rig _____________________________________


def toggle_down_one_level(value):
    global down_one_level_var
    down_one_level_var = value


def get_root_node(node, down_one_level=False):
    previous_node = None

    # Obtén el nombre completo del nodo para evitar conflictos de nombres duplicados
    node = cmds.ls(node, long=True)[0]

    while True:
        parents = cmds.listRelatives(node, parent=True, fullPath=True)

        if not parents:
            # Si down_one_level está activado, queremos el nodo anterior al nodo raíz
            # Si estamos en el nodo raíz y down_one_level está activado, devolveremos el previous_node
            # Si down_one_level no está activado, simplemente devolveremos el nodo actual
            return previous_node if down_one_level else node

        # Guardar el nodo actual antes de movernos al siguiente nodo padre
        previous_node = node

        # Actualizar el nodo actual al nodo padre para la próxima iteración
        node = parents[0]


def isolate_master():
    # Use the global state for down_one_level
    down_one_level = down_one_level_var

    # Guardar la selección actual
    current_selection = selectionMod.get_selected_objects()

    # Obtener los objetos actualmente seleccionados
    selected_objects = selectionMod.get_selected_objects()
    currentPanel = cmds.getPanel(wf=True)
    if not currentPanel or cmds.getPanel(typeOf=currentPanel) != "modelPanel":
        visible_model_panels = cmds.getPanel(visiblePanels=True) or []
        currentPanel = next((panel for panel in visible_model_panels if cmds.getPanel(typeOf=panel) == "modelPanel"), None)
    if not currentPanel or cmds.getPanel(typeOf=currentPanel) != "modelPanel":
        return
    currentState = cmds.isolateSelect(currentPanel, query=True, state=True)

    # Si no hay objetos seleccionados y el estado de aislamiento es 0, salimos de la función.
    if not selected_objects and currentState == 0:
        return
    # Si no hay objetos seleccionados pero el aislamiento está activado, lo desactivamos.
    elif not selected_objects and currentState == 1:
        cmds.isolateSelect(currentPanel, state=0)
        return
    else:
        # Para cada objeto seleccionado, encontrar y seleccionar el objeto raíz
        for selected_object in selected_objects:
            root_object = get_root_node(selected_object, down_one_level=down_one_level)
            cmds.select(root_object, add=True)  # Añadir el objeto raíz a la selección

        # Fix para activar/desactivar el icono isolate que en maya 2024 esta en otro layout

        new_maya_version = cmds.about(version=True) in ["2024", "2025"]

        if currentState == 0:
            cmds.isolateSelect(currentPanel, state=1)
            cmds.isolateSelect(currentPanel, addSelected=True)

            # Fix para activar y desactivar el icono de maya del isolate
            if currentPanel == "modelPanel1":
                if new_maya_version:
                    cmds.iconTextCheckBox(
                        "MainPane|viewPanes|modelPanel1|modelPanel1|modelEditorIconBar|flowLayout3|formLayout24|IsolateSelectedBtn",
                        edit=True,
                        value=True,
                    )
                else:
                    cmds.iconTextCheckBox(
                        "MainPane|viewPanes|modelPanel1|modelPanel1|modelEditorIconBar|flowLayout3|formLayout25|IsolateSelectedBtn",
                        edit=True,
                        value=True,
                    )

            elif currentPanel == "modelPanel2":
                if new_maya_version:
                    cmds.iconTextCheckBox(
                        "MainPane|viewPanes|modelPanel2|modelPanel2|modelEditorIconBar|flowLayout4|formLayout31|IsolateSelectedBtn",
                        edit=True,
                        value=True,
                    )
                else:
                    cmds.iconTextCheckBox(
                        "MainPane|viewPanes|modelPanel2|modelPanel2|modelEditorIconBar|flowLayout4|formLayout32|IsolateSelectedBtn",
                        edit=True,
                        value=True,
                    )

            elif currentPanel == "modelPanel3":
                if new_maya_version:
                    cmds.iconTextCheckBox(
                        "MainPane|viewPanes|modelPanel3|modelPanel3|modelEditorIconBar|flowLayout5|formLayout38|IsolateSelectedBtn",
                        edit=True,
                        value=True,
                    )
                else:
                    cmds.iconTextCheckBox(
                        "MainPane|viewPanes|modelPanel3|modelPanel3|modelEditorIconBar|flowLayout5|formLayout39|IsolateSelectedBtn",
                        edit=True,
                        value=True,
                    )

            elif currentPanel == "modelPanel4":
                if new_maya_version:
                    cmds.iconTextCheckBox(
                        "MainPane|viewPanes|modelPanel4|modelPanel4|modelEditorIconBar|flowLayout6|formLayout45|IsolateSelectedBtn",
                        edit=True,
                        value=True,
                    )
                else:
                    cmds.iconTextCheckBox(
                        "MainPane|viewPanes|modelPanel4|modelPanel4|modelEditorIconBar|flowLayout6|formLayout46|IsolateSelectedBtn",
                        edit=True,
                        value=True,
                    )

        else:
            cmds.isolateSelect(currentPanel, state=0)
            cmds.isolateSelect(currentPanel, removeSelected=True)

            # Fix para activar y desactivar el icono de maya del isolate
            if currentPanel == "modelPanel1":
                if new_maya_version:
                    cmds.iconTextCheckBox(
                        "MainPane|viewPanes|modelPanel1|modelPanel1|modelEditorIconBar|flowLayout3|formLayout24|IsolateSelectedBtn",
                        edit=True,
                        value=False,
                    )
                else:
                    cmds.iconTextCheckBox(
                        "MainPane|viewPanes|modelPanel1|modelPanel1|modelEditorIconBar|flowLayout3|formLayout25|IsolateSelectedBtn",
                        edit=True,
                        value=False,
                    )

            elif currentPanel == "modelPanel2":
                if new_maya_version:
                    cmds.iconTextCheckBox(
                        "MainPane|viewPanes|modelPanel2|modelPanel2|modelEditorIconBar|flowLayout4|formLayout31|IsolateSelectedBtn",
                        edit=True,
                        value=False,
                    )
                else:
                    cmds.iconTextCheckBox(
                        "MainPane|viewPanes|modelPanel2|modelPanel2|modelEditorIconBar|flowLayout4|formLayout32|IsolateSelectedBtn",
                        edit=True,
                        value=False,
                    )

            elif currentPanel == "modelPanel3":
                if new_maya_version:
                    cmds.iconTextCheckBox(
                        "MainPane|viewPanes|modelPanel3|modelPanel3|modelEditorIconBar|flowLayout5|formLayout38|IsolateSelectedBtn",
                        edit=True,
                        value=False,
                    )
                else:
                    cmds.iconTextCheckBox(
                        "MainPane|viewPanes|modelPanel3|modelPanel3|modelEditorIconBar|flowLayout5|formLayout39|IsolateSelectedBtn",
                        edit=True,
                        value=False,
                    )

            elif currentPanel == "modelPanel4":
                if new_maya_version:
                    cmds.iconTextCheckBox(
                        "MainPane|viewPanes|modelPanel4|modelPanel4|modelEditorIconBar|flowLayout6|formLayout45|IsolateSelectedBtn",
                        edit=True,
                        value=False,
                    )
                else:
                    cmds.iconTextCheckBox(
                        "MainPane|viewPanes|modelPanel4|modelPanel4|modelEditorIconBar|flowLayout6|formLayout46|IsolateSelectedBtn",
                        edit=True,
                        value=False,
                    )

    # Restaurar la selección previa
    if current_selection:
        cmds.select(current_selection)
    else:
        cmds.select(clear=True)  # Borra la selección si no había nada seleccionado previamente


# ____________________________ selector jerarquia


def select_curves_with_ctrl(obj):
    # Obtén los descendientes del objeto
    children = cmds.listRelatives(obj, allDescendents=True, type="nurbsCurve")
    if children:
        # Invertir el orden de los hijos
        children.reverse()

        for child in children:
            try:
                # Comprueba si el descendiente es de tipo nurbsCurve
                if cmds.nodeType(child) == "nurbsCurve":
                    # Obtiene el transformador de la forma nurbsCurve
                    transform = cmds.listRelatives(child, parent=True)[0]
                    cmds.select(transform, add=True)
            except Exception as e:
                # Manejar cualquier excepción y continuar con el siguiente descendiente
                import TheKeyMachine.mods.reportMod as report

                report.report_detected_exception(e, context="select hierarchy curves")
                continue


def selectHierarchy():
    # Obtener la selección actual
    selection = selectionMod.get_selected_objects()

    if selection:
        for obj in selection:
            select_curves_with_ctrl(obj)


# ---------------------------------------------------  COPY/PASTE WORLDSPACE ANIMATION  ------------------------------------------------------#

def worldspace_copy_animation(*args):
    target_info = keyTools.resolve_tool_targets(default_mode="all_animation", ordered_selection=True, long_names=False)
    selected_objects = target_info["target_objects"]
    if not selected_objects:
        return

    # Comprobar si los objetos seleccionados tienen claves de animación
    if not cmds.keyframe(selected_objects, query=True):
        return

    animation_data = {}

    # Guardar el tiempo actual antes de realizar cambios
    original_time = cmds.currentTime(query=True)

    # Suspender la actualización de la vista
    cmds.refresh(suspend=True)

    # Crear una barra de progreso
    gMainProgressBar = mel.eval("$tmp = $gMainProgressBar")
    time_context = target_info["time_context"]
    keyframe_query = {"query": True}
    if time_context.mode != "all_animation":
        keyframe_query["time"] = time_context.timerange
    total_frames = len(set(cmds.keyframe(selected_objects, **keyframe_query) or []))
    cmds.progressBar(
        gMainProgressBar,
        edit=True,
        beginProgress=True,
        isInterruptable=True,
        status="Copying World Space animation...",
        maxValue=total_frames,
    )

    tint_session = None

    try:
        all_keyframes = sorted(list(set(cmds.keyframe(selected_objects, **keyframe_query) or [])))
        if all_keyframes:
            tint_session = timelineWidgets.begin_timeline_tint(
                timerange=(int(all_keyframes[0]), int(all_keyframes[-1])),
                color=_active_tint_color("worldspace"),
                key="worldspace",
            )
        for frame in all_keyframes:
            # Verificar si el proceso fue interrumpido por el usuario
            if cmds.progressBar(gMainProgressBar, query=True, isCancelled=True):
                break

            cmds.currentTime(frame)

            for source_obj in selected_objects:
                # Asegurarse de que el objeto tiene claves en este frame
                if cmds.keyframe(source_obj, query=True, time=(frame, frame)):
                    worldspace_values = cmds.xform(source_obj, query=True, translation=True, worldSpace=True) + cmds.xform(
                        source_obj, query=True, rotation=True, worldSpace=True
                    )
                    if source_obj not in animation_data:
                        animation_data[source_obj] = {}

                    animation_data[source_obj][int(frame)] = worldspace_values

            # Actualizar la barra de progreso
            cmds.progressBar(gMainProgressBar, edit=True, step=1)

        # Save to JSON

        worldspace_anim_data_file = general.get_copy_worldspace_data_file()
        worldspace_anim_data_folder = general.get_copy_worldspace_data_folder()

        if not os.path.exists(worldspace_anim_data_folder):
            os.makedirs(worldspace_anim_data_folder)

        payload = {
            "meta": {"ordered_objects": selected_objects},
            "data": animation_data,
        }
        with open(worldspace_anim_data_file, "w") as json_file:
            json.dump(payload, json_file)

    finally:
        if tint_session:
            tint_session.finish()
        # Restaurar la actualización de la vista y cerrar la barra de progreso
        cmds.refresh(suspend=False)
        cmds.progressBar(gMainProgressBar, edit=True, endProgress=True)
        # Restaurar el tiempo actual a su estado original
        cmds.currentTime(original_time)
        wutil.make_inViewMessage("World Space animation copied")


# -------------------- Copy range World Space


def copy_range_worldspace_animation(*args):
    target_info = keyTools.resolve_tool_targets(default_mode="all_animation", ordered_selection=True, long_names=False)
    selected_objects = target_info["target_objects"]
    if not selected_objects:
        return

    # Comprobar si los objetos seleccionados tienen claves de animación
    if not cmds.keyframe(selected_objects, query=True):
        return

    time_context = target_info["time_context"]
    time_range = time_context.timerange if time_context.mode != "current_frame" else None

    animation_data = {}
    tint_session = None
    tint_session = None

    # Guardar el tiempo actual antes de realizar cambios
    original_time = cmds.currentTime(query=True)

    # Suspender la actualización de la vista
    cmds.refresh(suspend=True)

    attributes = {
        "query": True,
    }
    if time_range:
        attributes["time"] = (time_range[0], time_range[1])

    # Crear una barra de progreso
    gMainProgressBar = mel.eval("$tmp = $gMainProgressBar")
    all_keyframes = sorted(list(set(cmds.keyframe(selected_objects, **attributes))))
    total_frames = len(all_keyframes)
    cmds.progressBar(
        gMainProgressBar,
        edit=True,
        beginProgress=True,
        isInterruptable=True,
        status="Copying World Space animation...",
        maxValue=total_frames,
    )

    try:
        if all_keyframes:
            tint_session = timelineWidgets.begin_timeline_tint(
                timerange=(int(all_keyframes[0]), int(all_keyframes[-1])),
                color=_active_tint_color("ws_copy_range"),
                key="ws_copy_range",
            )

        for frame in all_keyframes:
            # Verificar si el proceso fue interrumpido por el usuario
            if cmds.progressBar(gMainProgressBar, query=True, isCancelled=True):
                break

            cmds.currentTime(frame)

            for source_obj in selected_objects:
                # Asegurarse de que el objeto tiene claves en este frame
                if cmds.keyframe(source_obj, query=True, time=(frame, frame)):
                    worldspace_values = cmds.xform(source_obj, query=True, translation=True, worldSpace=True) + cmds.xform(
                        source_obj, query=True, rotation=True, worldSpace=True
                    )
                    if source_obj not in animation_data:
                        animation_data[source_obj] = {}

                    animation_data[source_obj][int(frame)] = worldspace_values

            # Actualizar la barra de progreso
            cmds.progressBar(gMainProgressBar, edit=True, step=1)

        # Save to JSON
        worldspace_anim_data_file = general.get_copy_worldspace_data_file()
        worldspace_anim_data_folder = general.get_copy_worldspace_data_folder()

        if not os.path.exists(worldspace_anim_data_folder):
            os.makedirs(worldspace_anim_data_folder)

        payload = {
            "meta": {"ordered_objects": selected_objects},
            "data": animation_data,
        }
        with open(worldspace_anim_data_file, "w") as json_file:
            json.dump(payload, json_file)

    finally:
        if tint_session:
            tint_session.finish()
        # Restaurar la actualización de la vista y cerrar la barra de progreso
        cmds.refresh(suspend=False)
        cmds.progressBar(gMainProgressBar, edit=True, endProgress=True)
        # Restaurar el tiempo actual a su estado original
        keyTools.clear_timeslider_selection()
        cmds.currentTime(original_time)
        wutil.make_inViewMessage("World Space animation copied")


# ............. copy single frame World Space


def copy_worldspace_single_frame(*args):
    selected_objects = selectionMod.get_selected_objects(orderedSelection=True)
    if not selected_objects:
        return

    animation_data = {}

    # Obtener el tiempo actual
    current_time = cmds.currentTime(query=True)
    tint_session = timelineWidgets.begin_timeline_tint(
        timerange=(int(current_time), int(current_time)),
        color=_active_tint_color("ws_copy_frame"),
        key="ws_copy_frame",
    )

    try:
        for source_obj in selected_objects:
            worldspace_values = cmds.xform(source_obj, query=True, translation=True, worldSpace=True) + cmds.xform(
                source_obj, query=True, rotation=True, worldSpace=True
            )
            animation_data[source_obj] = {int(current_time): worldspace_values}

        # Save to JSON
        worldspace_anim_data_file = general.get_copy_worldspace_single_frame_data_file()
        worldspace_anim_data_folder = general.get_copy_worldspace_single_frame_data_folder()

        if not os.path.exists(worldspace_anim_data_folder):
            os.makedirs(worldspace_anim_data_folder)

        payload = {
            "meta": {"ordered_objects": selected_objects},
            "data": animation_data,
        }
        with open(worldspace_anim_data_file, "w") as json_file:
            json.dump(payload, json_file)

        wutil.make_inViewMessage("World Space values for current frame copied")
    finally:
        tint_session.finish()


def paste_worldspace_single_frame(*args):
    chunk_opened = False
    tint_session = None
    try:
        chunk_opened = toolCommon.open_undo_chunk()

        # Rutas
        worldspace_anim_data_file = general.get_copy_worldspace_single_frame_data_file()

        if not os.path.exists(worldspace_anim_data_file):
            return cmds.warning("No World Space data found")

        with open(worldspace_anim_data_file, "r") as json_file:
            payload = json.load(json_file)

        selection_mismatch_message = "Selection missmatched to paste worldspace"

        if isinstance(payload, dict) and "data" in payload:
            animation_data = payload.get("data") or {}
            ordered_sources = (payload.get("meta") or {}).get("ordered_objects") or list(animation_data.keys())
        else:
            animation_data = payload or {}
            ordered_sources = list(animation_data.keys())

        ordered_sources = [obj for obj in ordered_sources if obj in animation_data]
        if not ordered_sources:
            return wutil.make_inViewMessage("No World Space data found")

        frame_range = timelineWidgets.get_animation_data_timerange(
            {obj_name: {"frames": list((animation_data.get(obj_name) or {}).keys())} for obj_name in ordered_sources},
            frame_key="frames",
        )
        if frame_range:
            tint_session = timelineWidgets.begin_timeline_tint(
                timerange=frame_range,
                color=_active_tint_color("ws_paste_frame"),
                key="ws_paste_frame",
            )

        target_objects = selectionMod.get_selected_objects(orderedSelection=True)

        # No selection: paste back to the originally copied objects (if they still exist)
        if not target_objects:
            target_objects = ordered_sources
            missing = [obj for obj in target_objects if not cmds.objExists(obj)]
            if missing:
                return wutil.make_inViewMessage(selection_mismatch_message)

        source_count = len(ordered_sources)
        target_count = len(target_objects)

        # Multi-source pastes require matching selection size
        if source_count > 1 and target_count != source_count:
            return wutil.make_inViewMessage(selection_mismatch_message)

        def _first_frame_values(obj_name):
            obj_data = animation_data.get(obj_name) or {}
            if not isinstance(obj_data, dict) or not obj_data:
                return None
            first_frame = next(iter(obj_data))
            return obj_data[first_frame]

        # Single-source: paste to any selection size (same transform for all targets)
        if source_count == 1:
            values = _first_frame_values(ordered_sources[0])
            if not values:
                return wutil.make_inViewMessage("No World Space data found")
            for obj in target_objects:
                if cmds.objExists(obj):
                    cmds.xform(obj, translation=values[:3], worldSpace=True)
                    cmds.xform(obj, rotation=values[3:], worldSpace=True)
            return

        # Multi-source: paste in order (source[0]->target[0], ...)
        for idx, target_obj in enumerate(target_objects):
            source_obj = ordered_sources[idx]
            values = _first_frame_values(source_obj)
            if not values:
                return wutil.make_inViewMessage("No World Space data found")
            if cmds.objExists(target_obj):
                cmds.xform(target_obj, translation=values[:3], worldSpace=True)
                cmds.xform(target_obj, rotation=values[3:], worldSpace=True)

        return

    finally:
        if tint_session:
            tint_session.finish()
        if chunk_opened:
            try:
                toolCommon.close_undo_chunk()
            except Exception:
                pass


def worldspace_paste_animation(*args):
    chunk_opened = False
    tint_session = None

    original_time = cmds.currentTime(query=True)
    worldspace_anim_data_file = general.get_copy_worldspace_data_file()

    try:
        chunk_opened = toolCommon.open_undo_chunk()
        if not os.path.exists(worldspace_anim_data_file):
            return wutil.make_inViewMessage("No World Space animation data found")

        with open(worldspace_anim_data_file, "r") as json_file:
            payload = json.load(json_file)

        selection_mismatch_message = "Selection missmatched to paste worldspace"

        if isinstance(payload, dict) and "data" in payload:
            animation_data = payload.get("data") or {}
            ordered_sources = (payload.get("meta") or {}).get("ordered_objects") or list(animation_data.keys())
        else:
            animation_data = payload or {}
            ordered_sources = list(animation_data.keys())

        ordered_sources = [obj for obj in ordered_sources if obj in animation_data]
        if not ordered_sources:
            return wutil.make_inViewMessage("No World Space animation data found")

        target_objects = selectionMod.get_selected_objects(orderedSelection=True)

        # No selection: paste back to the originally copied objects (if they still exist)
        if not target_objects:
            target_objects = ordered_sources
            missing = [obj for obj in target_objects if not cmds.objExists(obj)]
            if missing:
                return wutil.make_inViewMessage(selection_mismatch_message)

        source_count = len(ordered_sources)
        target_count = len(target_objects)

        # Multi-source pastes require matching selection size
        if source_count > 1 and target_count != source_count:
            return wutil.make_inViewMessage(selection_mismatch_message)

        # Map source data -> target objects (preserve order)
        if source_count == 1:
            mapping = [(ordered_sources[0], t) for t in target_objects]
        else:
            mapping = list(zip(ordered_sources, target_objects))

        # Cut existing animation on targets
        for _, target_obj in mapping:
            if cmds.objExists(target_obj):
                cmds.cutKey(target_obj, attribute=["tx", "ty", "tz", "rx", "ry", "rz"])

        # Frames to paste (union of used sources)
        mapped_animation_data = {}
        frame_set = set()
        for source_obj, _ in mapping:
            obj_data = animation_data.get(source_obj) or {}
            if isinstance(obj_data, dict):
                mapped_animation_data[source_obj] = {"frames": list(obj_data.keys())}
                for frame_key in obj_data.keys():
                    try:
                        frame_set.add(int(frame_key))
                    except Exception:
                        continue

        paste_range = timelineWidgets.get_animation_data_timerange(mapped_animation_data, frame_key="frames")
        if not paste_range:
            return wutil.make_inViewMessage("No World Space animation data found")

        tint_session = timelineWidgets.begin_timeline_tint(
            timerange=paste_range,
            color=_active_tint_color("ws_paste"),
            key="ws_paste",
        )

        all_frames = sorted(frame_set)

        cmds.refresh(suspend=True)

        gMainProgressBar = mel.eval("$tmp = $gMainProgressBar")
        cmds.progressBar(
            gMainProgressBar,
            edit=True,
            beginProgress=True,
            isInterruptable=True,
            status="Pasting World Space animation...",
            maxValue=len(all_frames),
        )

        try:
            for frame in all_frames:
                cmds.progressBar(gMainProgressBar, edit=True, step=1)
                if cmds.progressBar(gMainProgressBar, query=True, isCancelled=True):
                    break

                cmds.currentTime(frame)
                frame_key = str(frame)
                for source_obj, target_obj in mapping:
                    if not cmds.objExists(target_obj):
                        continue
                    obj_data = animation_data.get(source_obj) or {}
                    if not isinstance(obj_data, dict):
                        continue
                    if frame_key not in obj_data:
                        continue
                    values = obj_data[frame_key]
                    cmds.xform(target_obj, translation=values[:3], worldSpace=True)
                    cmds.xform(target_obj, rotation=values[3:], worldSpace=True)
                    cmds.setKeyframe(target_obj)

        finally:
            valid_targets = [t for _, t in mapping if cmds.objExists(t)]
            if valid_targets:
                cmds.filterCurve(valid_targets)
            cmds.refresh(suspend=False)
            cmds.progressBar(gMainProgressBar, edit=True, endProgress=True)
            cmds.currentTime(original_time)
            pass

    finally:
        if tint_session:
            tint_session.finish()
        if chunk_opened:
            try:
                toolCommon.close_undo_chunk()
            except Exception:
                pass


# ____________________________________ Tracer _______________________________________________

def create_tracer(*args):
    selected_objects = selectionMod.get_selected_objects()

    # Verificar si hay exactamente un objeto seleccionado.
    if len(selected_objects) != 1:
        return wutil.make_inViewMessage("Select only one object")

    # Verifica o crea el grupo 'TheKeyMachine'
    if not cmds.objExists("TheKeyMachine"):
        general.create_TheKeyMachine_node()

    # Verifica si 'CTracer' existe y si no, lo crea o lo reinicia
    if cmds.objExists("TKM_Tracer"):
        cmds.delete("TKM_Tracer")

    selected_objects_start = selectionMod.get_selected_objects()
    cmds.createNode("transform", name="TKM_Tracer")
    cmds.parent("TKM_Tracer", "TheKeyMachine")

    # Crea un nuevo nodo para 'tracer_offset' dentro de 'TKM_Tracer'
    cmds.createNode("transform", name="tracer_offset")
    cmds.parent("tracer_offset", "TKM_Tracer")

    cmds.select(selected_objects_start)

    selected_objects = selectionMod.get_selected_objects()

    if not selected_objects:
        return wutil.make_inViewMessage("Select an object to trace")

    if cmds.objExists("tracerHandle"):
        cmds.delete("tracerHandle")

    startFrame = cmds.playbackOptions(query=True, minTime=True)
    endFrame = cmds.playbackOptions(query=True, maxTime=True)
    cmds.snapshot(n="tracer", mt=True, constructionHistory=True, startTime=startFrame, endTime=endFrame, increment=1)
    cmds.setAttr("tracerHandleShape.trailDrawMode", 1)
    cmds.setAttr("tracerHandleShape.extraTrailColor", 0.8143, 0.5109, 0.5318, type="double3")
    cmds.setAttr("tracerHandleShape.trailColor", 0.4398, 0.1724, 0.1908, type="double3")
    cmds.setAttr("tracerHandleShape.keyframeColor", 1.0, 1.0, 1.0, type="double3")
    cmds.disconnectAttr("tracer.points", "tracerHandleShape.points")
    cmds.parent("tracerHandle", "tracer_offset")  # Coloca "tracerHandle" dentro de "tracer_offset"
    tracer_update_checkbox(False)
    cmds.select(selected_objects)


def select_tracer_offset_node(*args):
    if cmds.objExists("tracer_offset"):
        cmds.select("tracer_offset", replace=True)


def remove_tracer_node(*args):
    if cmds.objExists("TKM_Tracer"):
        cmds.delete("TKM_Tracer")


def tracer_connected(connected=False, update_cb=None, *args):
    if not cmds.objExists("tracerHandle"):
        return wutil.make_inViewMessage("No tracer node in the scene")

    is_connected = cmds.isConnected("tracer.points", "tracerHandleShape.points")

    # Si queremos conectar pero ya está conectado, o si queremos desconectar pero ya está desconectado, regresamos.
    if (connected and is_connected) or (not connected and not is_connected):
        return

    if connected:
        cmds.connectAttr("tracer.points", "tracerHandleShape.points", force=True)
        cmds.setAttr("tracer.increment", 1)
    else:
        cmds.disconnectAttr("tracer.points", "tracerHandleShape.points")

    # Actualizamos el estado del checkbox si se proporciona la función de actualización.
    if update_cb:
        update_cb(connected)


def tracer_update_checkbox(value):
    if cmds.menuItem("tracer_checkbox_menuItem", exists=True):
        cmds.menuItem("tracer_checkbox_menuItem", e=True, checkBox=value)


def tracer_refresh(*args):
    if not cmds.objExists("tracerHandle"):
        return wutil.make_inViewMessage("No tracer node in the scene")
    else:
        is_connected = cmds.isConnected("tracer.points", "tracerHandleShape.points")
        if not is_connected:
            cmds.connectAttr("tracer.points", "tracerHandleShape.points", force=True)
            cmds.setAttr("tracer.increment", 1)
            cmds.setAttr("tracer.increment", 2)
            cmds.setAttr("tracer.increment", 1)
            cmds.disconnectAttr("tracer.points", "tracerHandleShape.points")


def set_tracer_blue_color(*args):
    if cmds.objExists("tracerHandle"):
        cmds.setAttr("tracerHandleShape.extraTrailColor", 0.1615, 0.1766, 0.3581, type="double3")
        cmds.setAttr("tracerHandleShape.trailColor", 0.2879, 0.2932, 0.358, type="double3")
        cmds.setAttr("tracerHandleShape.keyframeColor", 1.0, 1.0, 1.0, type="double3")


def set_tracer_red_color(*args):
    if cmds.objExists("tracerHandle"):
        cmds.setAttr("tracerHandleShape.extraTrailColor", 0.8143, 0.5109, 0.5318, type="double3")
        cmds.setAttr("tracerHandleShape.trailColor", 0.4398, 0.1724, 0.1908, type="double3")
        cmds.setAttr("tracerHandleShape.keyframeColor", 1.0, 1.0, 1.0, type="double3")


def set_tracer_grey_color(*args):
    if cmds.objExists("tracerHandle"):
        cmds.setAttr("tracerHandleShape.extraTrailColor", 0.2879, 0.2932, 0.358, type="double3")
        cmds.setAttr("tracerHandleShape.trailColor", 0.122, 0.122, 0.122, type="double3")
        cmds.setAttr("tracerHandleShape.keyframeColor", 1.0, 1.0, 1.0, type="double3")


def tracer_show_hide(*args):
    if cmds.objExists("tracerHandle"):
        visibility = cmds.getAttr("tracerHandle.visibility")
        cmds.setAttr("tracerHandle.visibility", not visibility)


# FollowCam _________________________________________________________________

followCam_original_camera = None


def create_follow_cam(translation=True, rotation=True, *args):
    global followCam_original_camera

    # Obtén el objeto seleccionado en la escena
    selected_objects = selectionMod.get_selected_objects()

    # Verifica si existe el grupo "TheKeyMachine"
    if not cmds.objExists("TheKeyMachine"):
        general.create_TheKeyMachine_node()

    if not selected_objects:
        return wutil.make_inViewMessage("Select at least one object")

    target_object = selected_objects[0]

    # Obtén el panel con el foco actualmente y encuentra la cámara activa
    panel = cmds.playblast(activeEditor=True)
    camera = cmds.modelEditor(panel, query=True, camera=True)
    followCam_original_camera = camera

    # Si ya existe el nodo "tkm_followCam", crea una cámara y grupo temporales
    if cmds.objExists("tkm_followCam"):
        follow_cam = cmds.duplicate(camera, name="followCam_tmp")[0]
        follow_cam_group = cmds.group(follow_cam, name="tkm_followCam_tmp")
    else:
        # Duplica la cámara activa y renómbrala
        follow_cam = cmds.duplicate(camera, name="followCam")[0]
        follow_cam_group = cmds.group(follow_cam, name="tkm_followCam")

    # Mueve el grupo "tkm_followCam" dentro del grupo "TheKeyMachine"
    cmds.parent(follow_cam_group, "TheKeyMachine")

    # Desparenta temporalmente el nodo del dagContainer
    cmds.parent(follow_cam_group, world=True)

    if translation and not rotation:
        cmds.pointConstraint(target_object, follow_cam_group, maintainOffset=True)
    else:
        # Usa comandos de Python en lugar de MEL para establecer parentConstraint
        skip_trans = []
        skip_rot = []

        if not translation:
            skip_trans = ["x", "y", "z"]
        if not rotation:
            skip_rot = ["x", "y", "z"]

        cmds.parentConstraint(target_object, follow_cam_group, maintainOffset=True, skipTranslate=skip_trans, skipRotate=skip_rot)

    # Regresa el nodo al dagContainer
    cmds.parent(follow_cam_group, "TheKeyMachine")

    # Si se creó un grupo y una cámara temporal, renombra estos para reemplazar los existentes
    if cmds.objExists("tkm_followCam_tmp"):
        cmds.delete("tkm_followCam")
        cmds.rename("tkm_followCam_tmp", "tkm_followCam")
        cmds.rename("followCam_tmp", "followCam")
        follow_cam = "followCam"  # Asegura que follow_cam contenga el nombre correcto de la cámara

    # Si la cámara activa en el panel no es 'followCam', cambia la vista a 'followCam'
    if camera != "followCam":
        cmds.lookThru(panel, follow_cam)

    cmds.select(selected_objects)


def remove_followCam(*args):
    global followCam_original_camera
    # Obtén el panel con el foco actualmente
    panel = cmds.playblast(activeEditor=True)
    # current_camera = cmds.modelEditor(panel, query=True, camera=True)

    if cmds.objExists("tkm_followCam"):
        cmds.delete("tkm_followCam")

        # Si el nombre de la cámara actual no es "persp", cambia la vista a "persp"
        print(followCam_original_camera)
        cmds.lookThru(panel, followCam_original_camera)
    else:
        wutil.make_inViewMessage("No followCam in the scene")


# ________________________SELECTOR______________


def selector_window(*args):
    # Check if anything is selected first
    if not selectionMod.get_selected_objects():
        return

    # Search for an existing instance of the selector window
    for widget in QtWidgets.QApplication.topLevelWidgets():
        if isinstance(widget, customDialogs.QFlatSelectorDialog):
            widget.close()
            widget.deleteLater()

    # If no instance exists, create a new one
    dlg = customDialogs.QFlatSelectorDialog()
    dlg.place_near_cursor()
    dlg.activateWindow()
    dlg.list_widget.setFocus()


def select_objects_from_list(list_name, *args):
    # Obtener los elementos seleccionados en la lista
    selected_objects = cmds.textScrollList(list_name, query=True, selectItem=True)

    # Seleccionar los objetos en la escena
    cmds.select(selected_objects, replace=True)


def reload_selected_objects(list_name, *args):
    selected_objects = selectionMod.get_selected_objects()
    sorted_objects = sorted(selected_objects)

    # Borrar los elementos actuales en la lista
    cmds.textScrollList(list_name, edit=True, removeAll=True)

    # Agregar los objetos seleccionados ordenados alfabéticamente a la lista
    cmds.textScrollList(list_name, edit=True, append=sorted_objects)


# _____________________ SELECT RIG CHARACTER CONTROLS


def select_rig_controls(*args):
    def find_curves(node):
        curves = []
        shapes = cmds.listRelatives(node, shapes=True, fullPath=True)
        if shapes:
            for shape in shapes:
                if cmds.nodeType(shape) == "nurbsCurve":
                    curves.append(node)
        children = cmds.listRelatives(node, children=True, fullPath=True)
        if children:
            for child in children:
                curves += find_curves(child)
        return curves

    selected = selectionMod.get_selected_objects(long=True)

    if not selected:
        return

    # Obtener los namespaces de los objetos seleccionados
    namespaces = set()
    no_namespace = False
    for obj in selected:
        namespace_parts = obj.split(":")
        if len(namespace_parts) > 1:
            namespace = namespace_parts[0]
            namespaces.add(namespace)
        else:
            no_namespace = True

    all_curves = []

    for obj in selected:
        while True:
            parent = cmds.listRelatives(obj, parent=True, fullPath=True)
            if parent:
                obj = parent[0]
            else:
                break

        curves = find_curves(obj)
        all_curves += curves

    cmds.select(clear=True)

    if all_curves:
        if namespaces:  # Si hay namespaces, filtra las curvas que comiencen con algún namespace
            filtered_curves = [curve for curve in all_curves if any(curve.startswith(ns + ":") for ns in namespaces)]
        else:
            filtered_curves = all_curves

        if no_namespace:  # Si hay objetos sin namespace, incluye curvas sin namespace
            filtered_curves += [curve for curve in all_curves if ":" not in curve]

        cmds.select(filtered_curves, replace=True)
    else:
        cmds.warning("There are no curve-type controls to select")


# ______________ SELECT ANIMATED RIG CONTROLS


def select_rig_controls_animated(*args):
    cache = {}

    def find_controls(node):
        if node in cache:
            return cache[node]

        controls = []
        transforms = cmds.listRelatives(node, parent=True, fullPath=True) or [node]
        for transform in transforms:
            # Comprobar si el transform es un joint
            if cmds.nodeType(transform) == "joint":
                if is_animated_and_keyable(transform):
                    controls.append(transform)
            elif cmds.nodeType(transform) == "transform":
                shapes = cmds.listRelatives(transform, shapes=True, fullPath=True)
                if shapes:
                    for shape in shapes:
                        if cmds.nodeType(shape) == "nurbsCurve":
                            if is_animated_and_keyable(transform):
                                controls.append(transform)

        children = cmds.listRelatives(node, children=True, fullPath=True)
        if children:
            for child in children:
                controls += find_controls(child)

        cache[node] = controls
        return controls

    def is_animated_and_keyable(node):
        if node in cache:
            return cache[node]

        attrs = cmds.listAttr(node, keyable=True)
        if not attrs:
            cache[node] = False
            return False

        for attr in attrs:
            if not cmds.getAttr(node + "." + attr, lock=True):
                connections = cmds.listConnections(node + "." + attr, type="animCurve")
                if connections:
                    for conn in connections:
                        if cmds.nodeType(conn) in ["animCurveTA", "animCurveTL", "animCurveTU"]:
                            cache[node] = True
                            return True

        cache[node] = False
        return False

    selected = selectionMod.get_selected_objects(long=True)

    if not selected:
        return

    namespaces = set()
    for obj in selected:
        namespace_parts = obj.split(":")
        if len(namespace_parts) > 1:
            namespace = namespace_parts[0]
            namespaces.add(namespace)

    all_controls = []

    for obj in selected:
        while True:
            parent = cmds.listRelatives(obj, parent=True, fullPath=True)
            if parent:
                obj = parent[0]
            else:
                break

        controls = find_controls(obj)
        all_controls += controls

    cmds.select(clear=True)

    if all_controls:
        if namespaces:  # Si hay namespaces, filtra los controles que comienzan con alguno de los namespaces
            filtered_controls = [control for control in all_controls if any(control.startswith(ns + ":") for ns in namespaces)]
        else:  # Si no hay namespaces, selecciona todos los controles tal como están
            filtered_controls = all_controls

        cmds.select(filtered_controls, replace=True)
    else:
        cmds.warning("There are no suitable controls to select")


# _______________________________________ DEPTH MOVER


def activeCamera():
    panel = cmds.playblast(activeEditor=True)

    if not panel:
        return None

    camShape = cmds.modelEditor(panel, query=True, camera=True)
    if not camShape:
        return None

    if cmds.nodeType(camShape) == "transform":
        return camShape
    elif cmds.nodeType(camShape) in ["camera", "stereoRigCamera"]:
        return cmds.listRelatives(camShape, parent=True, path=True)[0]
    return None


class Coord3D:
    def __init__(self, x=0, y=0, z=0):
        self.x, self.y, self.z = x, y, z

    def __iter__(self):
        return iter((self.x, self.y, self.z))

    def __add__(self, other):
        return Coord3D(self.x + other.x, self.y + other.y, self.z + other.z)

    def __sub__(self, other):
        return Coord3D(self.x - other.x, self.y - other.y, self.z - other.z)

    def __mul__(self, other):
        if isinstance(other, Coord3D):
            return Coord3D(self.x * other.x, self.y * other.y, self.z * other.z)
        elif isinstance(other, (float, int)):
            return Coord3D(self.x * other, self.y * other, self.z * other)
        raise TypeError("Unsupported operand type(s) for *: 'Coord3D' and '{}'".format(type(other).__name__))

    def magnitude(self):
        return math.sqrt(self.x**2 + self.y**2 + self.z**2)

    def normalize(self):
        mag = self.magnitude()
        return Coord3D(self.x / mag, self.y / mag, self.z / mag) if mag else self


class MouseDragger(object):
    def __init__(self, name="mlMouseDraggerContext", title="MouseDragger", multiplier=0.1, cursor="hand"):
        self.multiplier = multiplier
        self.draggerContext = name
        if not cmds.draggerContext(self.draggerContext, exists=True):
            self.draggerContext = cmds.draggerContext(self.draggerContext)

        cmds.draggerContext(
            self.draggerContext,
            edit=True,
            pressCommand=self.onPress,
            dragCommand=self.onDrag,
            releaseCommand=self.onRelease,
            cursor=cursor,
            drawString=title,
            undoMode="all",
        )

    def onPress(self):
        self.anchorPoint = cmds.draggerContext(self.draggerContext, query=True, anchorPoint=True)
        self.chunk_opened = toolCommon.open_undo_chunk()

    def onDrag(self):
        dragPoint = cmds.draggerContext(self.draggerContext, query=True, dragPoint=True)
        self.x = (dragPoint[0] - self.anchorPoint[0]) * self.multiplier
        self.y = (dragPoint[1] - self.anchorPoint[1]) * self.multiplier
        self.performDrag()
        cmds.refresh()

    def onRelease(self):
        cmds.setToolTo("selectSuperContext")
        if self.chunk_opened:
            toolCommon.close_undo_chunk()

    def performDrag(self):
        pass

    def activateTool(self):
        cmds.setToolTo(self.draggerContext)


class DepthControlDragger(MouseDragger):
    def __init__(self):
        super(DepthControlDragger, self).__init__(name="mlDepthControlDraggerContext", title="DepthControl", multiplier=0.1)

        cam = activeCamera()
        if not cam:
            om.MGlobal.displayWarning("No camera found.")
            return

        sel = selectionMod.get_selected_objects()
        if not sel:
            om.MGlobal.displayWarning("Please select an object.")
            return

        self.cameraCoord = Coord3D(*cmds.xform(cam, query=True, worldSpace=True, rotatePivot=True))
        self.objs = [
            (obj, Coord3D(*cmds.xform(obj, query=True, worldSpace=True, rotatePivot=True)) - self.cameraCoord)
            for obj in sel
            if cmds.getAttr(obj + ".translate", settable=True)
        ]

        if not self.objs:
            om.MGlobal.displayWarning("Selected objects do not have translate attributes to apply this tool.")
            return

        self.activateTool()

    def performDrag(self):
        for obj, coord in self.objs:
            newPos = (coord.normalize() * self.x) + coord + self.cameraCoord
            cmds.move(newPos.x, newPos.y, newPos.z, obj, absolute=True, worldSpace=True)


def depth_mover(*args):
    DepthControlDragger()


# _______________________________________________ BAKE CUSTOM INTERVAL __________________________________________________


def bake_animation_custom_window(*args):
    def on_bake(value, dialog):
        try:
            bake_interval = float(value)
        except ValueError:
            return wutil.make_inViewMessage("Please enter a valid number for bake interval.")

        keyTools.bake_animation(bake_interval=bake_interval, window=dialog)
        dialog.close()

    # close previous instances
    for widget in QtWidgets.QApplication.topLevelWidgets():
        if isinstance(widget, customDialogs.QFlatNumberInput) and widget.windowTitle() == "Bake Custom Interval":
            widget.close()
            widget.deleteLater()

    dlg = customDialogs.QFlatNumberInput(
        callback=on_bake,
        parent=None,
    )
    dlg.place_near_cursor()
