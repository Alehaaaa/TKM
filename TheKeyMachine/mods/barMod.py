"""

TheKeyMachine - Animation Toolset for Maya Animators


This file is part of TheKeyMachine, an open source software for Autodesk Maya licensed under the GNU General Public License v3.0 (GPL-3.0).
You are free to use, modify, and distribute this code under the terms of the GPL-3.0 license.
By using this code, you agree to keep it open source and share any modifications.
This code is provided "as is," without any warranty. For the full license text, visit https://www.gnu.org/licenses/gpl-3.0.html

https://alehaaaa.github.io/TKM/

Developed by: Rodrigo Torres / rodritorres.com
Modified by: Alehaaaa / alehaaaa.github.io



"""

import maya.cmds as cmds
from maya import OpenMaya as om

from TheKeyMachine.Qt import QtWidgets


import importlib

# ----------------------------------------------------------------------


import TheKeyMachine.mods.keyToolsMod as keyTools
import TheKeyMachine.mods.generalMod as general
import TheKeyMachine.widgets.customDialogs as customDialogs
import TheKeyMachine.widgets.timeline as timelineWidgets
import TheKeyMachine.widgets.util as wutil
import TheKeyMachine.mods.selectionMod as selectionMod
from TheKeyMachine.tools import common as toolCommon
from TheKeyMachine.tools import clipboard
import TheKeyMachine.core.toolbox as toolbox
from TheKeyMachine.core import animation_context


# -------------------------------------------------------------------------


global down_one_level
down_one_level_var = False


def _active_tint_color(key=None, default=None):
    if isinstance(key, str) and key.startswith("#"):
        return key

    if key:
        try:
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


def create_locator():
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


def set_maya_default_tangent(tangent_type):
    cmds.keyTangent(**{"global": True, "inTangentType": tangent_type, "outTangentType": tangent_type})


def _normalize_curve_frames(curve_frames):
    frames = []
    for frame in curve_frames or []:
        try:
            frames.append(int(round(frame)))
        except Exception:
            continue
    return sorted(set(frames))


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
    default_mode = "all_animation" if key_scope == "all" else "current_frame"
    target_info, _plugs, _objects, _channels = animation_context.resolve_command_targets(
        default_mode=default_mode,
        include_shapes=True,
    )
    time_context = target_info["time_context"]
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

    curves = animation_context.curves(target_info)
    targets = {}
    for curve in curves:
        frames = _normalize_curve_frames(animation_context.key_times(curve, target_info))
        if frames:
            targets[curve] = frames
    return _filter_tangent_targets_by_scope(targets, key_scope)


def _tangent_target_range(targets):
    frames = sorted({frame for curve_frames in (targets or {}).values() for frame in curve_frames})
    if not frames:
        return None
    return frames[0], frames[-1]


def set_tangent(tangent_type, handle_mode="both", key_scope="selection", tint_color=None):
    default_mode = "all_animation" if key_scope == "all" else "current_frame"
    time_context = timelineWidgets.resolve_time_context(default_mode=default_mode)
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


def _collect_align_keyframes(objects):
    frames = set()
    for obj in objects or []:
        try:
            key_times = cmds.keyframe(obj, query=True, timeChange=True) or []
        except Exception:
            key_times = []
        for frame in key_times:
            try:
                frames.add(int(round(frame)))
            except Exception:
                continue
    return sorted(frames)


def align_selected_objects(*args, pos=True, rot=True, scl=False, key_scope="selection"):
    # Obtener los objetos seleccionados
    sel = selectionMod.get_selected_objects()

    # Asegurarse de que hay al menos dos objetos seleccionados
    if len(sel) < 2:
        return wutil.make_inViewMessage("Select at least two objects")

    # Obtener el objeto destino (último objeto en la lista de selección)
    target_obj = sel[-1]
    source_objs = sel[:-1]  # Todos los objetos excepto el último (objeto destino)

    with toolCommon.suspend_maya_refresh():
        frames_to_align = []
        set_keyframes = False
        if key_scope == "all":
            frames_to_align = _collect_align_keyframes(source_objs)
            if not frames_to_align:
                return wutil.make_inViewMessage("No animation keys available to align objects.")
            set_keyframes = True
        else:
            time_context = timelineWidgets.resolve_time_context(default_mode="current_frame")
            if time_context.mode in ("graph_editor_keys", "time_slider_range"):
                frames_to_align = list(time_context.frames)
                set_keyframes = True

        if frames_to_align:
            # Iterar sobre cada frame en el rango y alinear los objetos
            with toolCommon.tool_operation(
                tool_id="align_selected_objects",
                label="Aligning Objects",
                progress_max=len(frames_to_align),
                undo=True,
            ) as operation:
                for frame in operation.iterate(frames_to_align):
                    if operation.cancelled:
                        break
                    # Mover el tiempo actual al frame
                    cmds.currentTime(frame)

                    # Alinear los objetos fuente con el objeto destino en este frame
                    for source_obj in source_objs:
                        cmds.matchTransform(source_obj, target_obj, pos=pos, rot=rot, scl=scl)

                        # Definir un keyframe para el objeto fuente en este punto en el tiempo
                        if set_keyframes:
                            cmds.setKeyframe(source_obj)

        else:
            # Si no hay un rango de tiempo seleccionado o es igual al tiempo actual, alinear en el tiempo actual
            for source_obj in source_objs:
                cmds.matchTransform(source_obj, target_obj, pos=pos, rot=rot, scl=scl)
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


def select_hierarchy():
    # Obtener la selección actual
    selection = selectionMod.get_selected_objects()

    if selection:
        for obj in selection:
            select_curves_with_ctrl(obj)


# ---------------------------------------------------  COPY/PASTE WORLDSPACE ANIMATION  ------------------------------------------------------#

def worldspace_copy_animation(*args):
    target_info = animation_context.resolve_targets(default_mode="all_animation", ordered_selection=True, long_names=False)
    selected_objects = target_info["target_objects"]
    if not selected_objects:
        return

    # Comprobar si los objetos seleccionados tienen claves de animación
    if not cmds.keyframe(selected_objects, query=True):
        return

    animation_data = {}

    # Guardar el tiempo actual antes de realizar cambios
    original_time = cmds.currentTime(query=True)

    time_context = target_info["time_context"]
    keyframe_query = {"query": True}
    if time_context.mode != "all_animation":
        keyframe_query["time"] = time_context.timerange

    try:
        all_keyframes = sorted(list(set(cmds.keyframe(selected_objects, **keyframe_query) or [])))
        if not all_keyframes:
            return

        with toolCommon.tool_operation(
            tool_id="worldspace",
            label="World Space animation copied",
            progress=True,
            progress_max=len(all_keyframes),
            tint="range",
            timerange=(int(all_keyframes[0]), int(all_keyframes[-1])),
            undo=False,
            suspend_refresh=True,
        ) as operation:
            for frame in all_keyframes:
                if operation.cancelled:
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

                operation.step()

            # Save to clipboard
            payload = {
                "meta": {"ordered_objects": selected_objects},
                "data": animation_data,
            }
            clipboard.save("worldspace", payload)
            operation.success = True
    finally:
        # Restaurar el tiempo actual a su estado original
        cmds.currentTime(original_time)


# -------------------- Copy range World Space


def copy_range_worldspace_animation(*args):
    target_info = animation_context.resolve_targets(default_mode="current_frame", ordered_selection=True, long_names=False)
    selected_objects = target_info["target_objects"]
    if not selected_objects:
        return

    time_context = target_info["time_context"]
    if time_context.mode != "time_slider_range":
        return copy_worldspace_single_frame(*args)

    animation_data = {}

    # Guardar el tiempo actual antes de realizar cambios
    original_time = cmds.currentTime(query=True)

    frames_to_copy = list(time_context.frames or [])

    try:
        if not frames_to_copy:
            return

        with toolCommon.tool_operation(
            tool_id="ws_copy_range",
            label="World Space range copied",
            progress=True,
            progress_max=len(frames_to_copy),
            tint="range",
            timerange=(int(frames_to_copy[0]), int(frames_to_copy[-1])),
            undo=False,
            suspend_refresh=True,
        ) as operation:
            for frame in frames_to_copy:
                if operation.cancelled:
                    break

                cmds.currentTime(frame)

                for source_obj in selected_objects:
                    worldspace_values = cmds.xform(source_obj, query=True, translation=True, worldSpace=True) + cmds.xform(
                        source_obj, query=True, rotation=True, worldSpace=True
                    )
                    if source_obj not in animation_data:
                        animation_data[source_obj] = {}

                    animation_data[source_obj][int(frame)] = worldspace_values

                operation.step()

            # Save to clipboard
            payload = {
                "meta": {"ordered_objects": selected_objects},
                "data": animation_data,
            }
            clipboard.save("worldspace", payload)
            operation.success = True
    finally:
        timelineWidgets.clear_time_slider_selection()
        cmds.currentTime(original_time)


# ............. copy single frame World Space


def copy_worldspace_single_frame(*args):
    selected_objects = selectionMod.get_selected_objects(orderedSelection=True)
    if not selected_objects:
        return

    animation_data = {}

    # Obtener el tiempo actual
    current_time = cmds.currentTime(query=True)

    try:
        with toolCommon.tool_operation(
            tool_id="ws_copy_frame",
            label="World Space current frame copied",
            progress=False,
            tint="current",
            undo=False,
            suspend_refresh=True,
        ) as operation:
            for source_obj in selected_objects:
                worldspace_values = cmds.xform(source_obj, query=True, translation=True, worldSpace=True) + cmds.xform(
                    source_obj, query=True, rotation=True, worldSpace=True
                )
                animation_data[source_obj] = {int(current_time): worldspace_values}

            # Save to clipboard
            payload = {
                "meta": {"ordered_objects": selected_objects},
                "data": animation_data,
            }
            clipboard.save("worldspace_frame", payload)
            operation.success = True

    finally:
        pass


def paste_worldspace_single_frame(*args):
    operation_context = None
    tint_session = None
    try:
        operation_context = toolCommon.tool_operation(
            tool_id="ws_paste_frame",
            label="Paste World Space Frame",
            progress=False,
            undo=True,
        )
        operation_context.__enter__()

        # Load from clipboard
        payload = clipboard.load("worldspace_frame", "No World Space data found. Please copy a frame first.")
        if payload is None:
            return

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
        if operation_context:
            try:
                operation_context.__exit__(None, None, None)
            except Exception:
                pass


def _worldspace_frame_number(frame_key):
    try:
        return int(round(float(frame_key)))
    except Exception:
        return None


def _worldspace_frame_value_map(obj_data):
    values_by_frame = {}
    if not isinstance(obj_data, dict):
        return values_by_frame
    for frame_key, values in obj_data.items():
        frame = _worldspace_frame_number(frame_key)
        if frame is not None:
            values_by_frame[frame] = values
    return values_by_frame


def worldspace_paste_animation(*args):
    original_time = cmds.currentTime(query=True)
    try:
        with toolCommon.tool_operation(
            tool_id="ws_paste",
            label="Paste World Space Animation",
            progress=False,
            undo=True,
            suspend_refresh=True,
        ) as operation:
            payload = clipboard.load("worldspace", "No World Space animation data found. Please copy first.")
            if payload is None:
                return

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
            mapped_frame_values = {}
            frame_set = set()
            for source_obj, _ in mapping:
                values_by_frame = _worldspace_frame_value_map(animation_data.get(source_obj) or {})
                if values_by_frame:
                    mapped_frame_values[source_obj] = values_by_frame
                    mapped_animation_data[source_obj] = {"frames": list(values_by_frame.keys())}
                    frame_set.update(values_by_frame.keys())

            paste_range = timelineWidgets.get_animation_data_timerange(mapped_animation_data, frame_key="frames")
            if not paste_range:
                return wutil.make_inViewMessage("No World Space animation data found")

            operation.timerange = paste_range
            operation.tint = "range"

            all_frames = sorted(frame_set)

            # Reconfigure progress now that we know max items
            operation.progress_obj.max_items = len(all_frames)
            operation.progress_obj._enabled = True

            for frame in all_frames:
                if operation.cancelled:
                    break

                cmds.currentTime(frame)
                for source_obj, target_obj in mapping:
                    if not cmds.objExists(target_obj):
                        continue
                    values = (mapped_frame_values.get(source_obj) or {}).get(frame)
                    if values is None:
                        continue
                    cmds.xform(target_obj, translation=values[:3], worldSpace=True)
                    cmds.xform(target_obj, rotation=values[3:], worldSpace=True)
                    cmds.setKeyframe(target_obj, time=(frame,), attribute=["tx", "ty", "tz", "rx", "ry", "rz"])
                operation.step()

            valid_targets = [t for _, t in mapping if cmds.objExists(t)]
            if valid_targets:
                cmds.filterCurve(valid_targets)
            
            operation.success = True

    finally:
        cmds.currentTime(original_time)


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
FOLLOW_CAM_GROUP = "tkm_followCam"
FOLLOW_CAM_ORIGINAL_CAMERA_ATTR = "tkmOriginalCamera"


def _active_model_panel():
    candidates = []
    for query in (
        lambda: cmds.getPanel(withFocus=True),
        lambda: cmds.playblast(activeEditor=True),
        lambda: cmds.getPanel(visiblePanels=True),
    ):
        try:
            result = query()
        except Exception:
            continue
        candidates.extend(result if isinstance(result, (list, tuple)) else [result])

    for panel in candidates:
        if not panel:
            continue
        try:
            if cmds.getPanel(typeOf=panel) == "modelPanel":
                return panel
        except Exception:
            continue
    return None


def _camera_transform(camera):
    if not camera or not cmds.objExists(camera):
        return None
    try:
        if cmds.nodeType(camera) == "camera":
            parents = cmds.listRelatives(camera, parent=True, fullPath=True) or []
            return parents[0] if parents else None
    except Exception:
        return None
    return camera


def _is_follow_camera(camera):
    camera = _camera_transform(camera)
    if not camera or not cmds.objExists("followCam"):
        return False
    camera_paths = cmds.ls(camera, long=True) or []
    follow_paths = cmds.ls("followCam", long=True) or []
    return bool(set(camera_paths).intersection(follow_paths))


def _stored_follow_camera():
    plug = "{}.{}".format(FOLLOW_CAM_GROUP, FOLLOW_CAM_ORIGINAL_CAMERA_ATTR)
    if cmds.objExists(plug):
        try:
            camera = cmds.getAttr(plug)
            if camera and cmds.objExists(camera):
                return camera
        except Exception:
            pass
    return None


def _store_follow_camera(camera):
    if not camera or not cmds.objExists(FOLLOW_CAM_GROUP):
        return
    plug = "{}.{}".format(FOLLOW_CAM_GROUP, FOLLOW_CAM_ORIGINAL_CAMERA_ATTR)
    if not cmds.objExists(plug):
        cmds.addAttr(FOLLOW_CAM_GROUP, longName=FOLLOW_CAM_ORIGINAL_CAMERA_ATTR, dataType="string")
    cmds.setAttr(plug, camera, type="string")


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
    panel = _active_model_panel()
    if not panel:
        return wutil.make_inViewMessage("Focus a model viewport before creating Follow Cam")
    camera = _camera_transform(cmds.modelEditor(panel, query=True, camera=True))
    if not camera:
        return wutil.make_inViewMessage("The active viewport has no valid camera")
    stored_camera = _stored_follow_camera()
    viewing_follow_cam = _is_follow_camera(camera)
    if not viewing_follow_cam:
        followCam_original_camera = camera
    elif stored_camera:
        followCam_original_camera = stored_camera

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

    _store_follow_camera(followCam_original_camera or stored_camera or "persp")

    # Si la cámara activa en el panel no es 'followCam', cambia la vista a 'followCam'
    if not viewing_follow_cam:
        cmds.lookThru(panel, follow_cam)

    cmds.select(selected_objects)


def remove_followCam(*args):
    global followCam_original_camera
    if not cmds.objExists(FOLLOW_CAM_GROUP):
        return wutil.make_inViewMessage("No followCam in the scene")

    panel = _active_model_panel()
    restore_camera = _stored_follow_camera() or followCam_original_camera
    if not restore_camera or not cmds.objExists(restore_camera):
        restore_camera = "persp" if cmds.objExists("persp") else None

    cmds.delete(FOLLOW_CAM_GROUP)
    followCam_original_camera = None

    if panel and restore_camera:
        cmds.lookThru(panel, restore_camera)


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
                if selectionMod.is_node_animated(transform):
                    controls.append(transform)
            elif cmds.nodeType(transform) == "transform":
                shapes = cmds.listRelatives(transform, shapes=True, fullPath=True)
                if shapes:
                    for shape in shapes:
                        if cmds.nodeType(shape) == "nurbsCurve":
                            if selectionMod.is_node_animated(transform):
                                controls.append(transform)

        children = cmds.listRelatives(node, children=True, fullPath=True)
        if children:
            for child in children:
                controls += find_controls(child)

        cache[node] = controls
        return controls

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


# _______________________________________________ BAKE CUSTOM INTERVAL __________________________________________________


def bake_animation_custom_window(*args):
    def on_bake(value, dialog):
        # QFlatNumberInput supplies an integer spin-box value. Validation and
        # dialog closing are owned by bake_animation so every entry point uses
        # the same interval rules and lifecycle.
        return keyTools.bake_animation(bake_interval=value, window=dialog)

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
