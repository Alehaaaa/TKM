"""Share Keys, Reblock, and Bake behavior."""

import math
from collections import Counter

from maya import cmds

from TheKeyMachine.core import animation_context, curveFitting
from TheKeyMachine.mods import selectionMod
from TheKeyMachine.mods import settingsMod as settings
from TheKeyMachine.tools import common as toolCommon
from TheKeyMachine.widgets import timeline as timelineWidgets
from TheKeyMachine.widgets import util as wutil

SHARE_KEYS_MODE_SETTING = "share_keys_mode"
SHARE_KEYS_MODE_PRESERVE_TANGENT = "preserve_tangent_type"
SHARE_KEYS_MODE_PRESERVE_SHAPE = "preserve_anim_curve_shape"
BAKE_TANGENT_MODE_SETTING = "bake_tangent_mode"
BAKE_TANGENT_MODE_STEP = "step_tangent"
BAKE_TANGENT_MODE_KEEP_TYPE = "keep_tangent_type"
BAKE_TANGENT_MODE_KEEP_SHAPE = "keep_animation_curve_shapes"
BAKE_TANGENT_MODES = (BAKE_TANGENT_MODE_STEP, BAKE_TANGENT_MODE_KEEP_TYPE, BAKE_TANGENT_MODE_KEEP_SHAPE)
BAKE_TITLES = {
    1: "Bake on Ones",
    2: "Bake on Twos",
    3: "Bake on Threes",
    4: "Bake on Fours",
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
        existing_frames = set(
            _normalize_key_frames(
                cmds.keyframe(
                    curve,
                    query=True,
                    time=(frames[0], frames[-1]),
                    timeChange=True,
                )
                or []
            )
        )
        for frame in frames:
            if operation and operation.cancelled:
                return
            if frame in existing_frames:
                if operation:
                    operation.step()
                continue
            if insert:
                cmds.setKeyframe(curve, time=(frame,), insert=True)
            else:
                cmds.setKeyframe(curve, time=(frame,))
            existing_frames.add(frame)
            if operation:
                operation.step()


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

def share_keys(*args):
    target_info = animation_context.resolve_targets(default_mode="all_animation", ordered_selection=True, long_names=True)
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
    operation = toolCommon.current_tool_operation()
    if operation:
        operation.set_total(len(curvas))

    # Crear un diccionario para contar perfiles
    perfiles = Counter()
    frames_by_curve = {}

    # Identificar perfil de cada curva y actualizar el contador
    for curva in curvas:
        keyframes = cmds.keyframe(curva, query=True, timeChange=True)
        if keyframes is None:
            continue
        fotogramas = tuple(sorted(keyframes))
        frames_by_curve[curva] = fotogramas
        perfiles[fotogramas] += 1

    if not perfiles:
        return wutil.make_inViewMessage("No animation curves found")

    # Identificar el perfil mayoritario
    perfil_mayoritario, _ = perfiles.most_common(1)[0]

    # Corregir curvas que no coinciden con el perfil mayoritario
    for curva in curvas:
        if operation and operation.cancelled:
            return
        fotogramas = frames_by_curve.get(curva)
        if fotogramas is None:
            if operation:
                operation.step()
            continue

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
        if operation:
            operation.step()


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
    if not frames_mayoritarios:
        return wutil.make_inViewMessage("No shared key pattern found")

    operation = toolCommon.current_tool_operation()
    if operation:
        operation.set_total(len(objetos))

    for objeto in objetos:
        if operation and operation.cancelled:
            return
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
        if operation:
            operation.step()


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

    bake_title = BAKE_TITLES.get(bake_interval, "Bake Animation")
    tool_key = "bake_animation_{}".format(bake_interval) if bake_interval in BAKE_TITLES else "bake_animation_custom"

    try:
        target_info = animation_context.resolve_targets(default_mode="all_animation", ordered_selection=True, long_names=True)
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
