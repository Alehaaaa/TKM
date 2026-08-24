"""Share Keys, Reblock, and Bake behavior."""

import math
from collections import Counter

from maya import cmds

from TheKeyMachine.maya import animation
from TheKeyMachine.maya import selection as maya_selection
from TheKeyMachine.core import settings
from TheKeyMachine.tools import common as toolCommon
from TheKeyMachine.ui.widgets import timeline as timelineWidgets
from TheKeyMachine.ui.widgets import util as wutil

SHARE_KEYS_MODE_SETTING = "share_keys_mode"
SHARE_KEYS_MODE_PRESERVE_TANGENT = "preserve_tangent_type"
SHARE_KEYS_MODE_PRESERVE_SHAPE = "preserve_anim_curve_shape"
BAKE_TANGENT_MODE_SETTING = "bake_tangent_mode"
BAKE_TANGENT_MODE_STEP = "step_tangent"
BAKE_TANGENT_MODE_KEEP_TYPE = "keep_tangent_type"
BAKE_TANGENT_MODE_KEEP_SHAPE = "keep_animation_curve_shapes"
BAKE_TANGENT_MODES = (
    BAKE_TANGENT_MODE_STEP,
    BAKE_TANGENT_MODE_KEEP_TYPE,
    BAKE_TANGENT_MODE_KEEP_SHAPE,
)
BAKE_TITLES = {
    1: "Bake on Ones",
    2: "Bake on Twos",
    3: "Bake on Threes",
    4: "Bake on Fours",
}


def get_share_keys_mode():
    return settings.get_setting(
        SHARE_KEYS_MODE_SETTING, SHARE_KEYS_MODE_PRESERVE_TANGENT
    )


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


def _curves_by_object(target_info, objects):
    """Resolve each object's exact plugs through the shared layer scope."""
    plugs_by_object = {obj: [] for obj in objects or []}
    for plug in target_info.plugs or []:
        if not plug or "." not in plug:
            continue
        obj = plug.rsplit(".", 1)[0]
        if obj in plugs_by_object:
            plugs_by_object[obj].append(plug)
    return {
        obj: target_info.curves_for_plugs(plugs_by_object.get(obj) or [])
        for obj in objects or []
    }


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
    selection = maya_selection.get_selected_objects()
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


def share_keys(*args, tool_operation=None, **_kwargs):
    operation = toolCommon.require_tool_operation(tool_operation)
    target_info = animation.resolve_context(
        default_mode="all_animation",
        include_shapes=True,
        resolve_curves=True,
    )
    if not target_info.objects and target_info.source != "graph_editor":
        return wutil.make_inViewMessage("Select at least one object")

    curves = _unique(target_info.curves)
    frames_by_curve = {
        curve: set(_normalize_key_frames(target_info.key_times(curve)))
        for curve in curves
    }
    all_frames = set().union(*frames_by_curve.values()) if frames_by_curve else set()

    if not all_frames:
        return animation.notify_empty("keys", "share")

    shared_frames = sorted(all_frames)
    preserve_curve_shape = get_share_keys_mode() == SHARE_KEYS_MODE_PRESERVE_SHAPE

    operation.set_total(len(curves) * len(shared_frames))
    toolCommon.ensure_operation_tint(
        operation,
        tint="range",
        timerange=(int(shared_frames[0]), int(shared_frames[-1])),
        tint_key="share_keys",
    )
    _set_missing_keys(
        curves,
        shared_frames,
        insert=preserve_curve_shape,
        operation=operation,
    )


def _frames_from_last_selected(target_info):
    selection = target_info.objects or []
    if len(selection) < 2:
        wutil.make_inViewMessage("Select targets, then the source object last")
        return None, [], []

    source = selection[-1]
    targets = selection[:-1]
    source_curves = _curves_by_object(target_info, [source]).get(source) or []
    frames = [
        frame
        for curve in source_curves
        for frame in target_info.key_times(curve)
    ]
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
    shape_data = animation.capture_curve_shape(curves, frames) if preserve_shape else {}
    for curve in curves:
        if operation and operation.cancelled:
            return
        for frame in frames:
            sampled = (shape_data.get(curve) or {}).get(float(frame))
            if sampled:
                cmds.setKeyframe(curve, time=(frame,), value=sampled["value"])
            else:
                cmds.setKeyframe(curve, time=(frame,))
        existing_frames = _normalize_key_frames(
            cmds.keyframe(curve, query=True, time=time_range, timeChange=True) or []
        )
        for frame in existing_frames:
            if frame not in frame_lookup:
                cmds.cutKey(curve, time=(frame, frame), option="keys")
        if operation:
            operation.step()
    if preserve_shape:
        animation.apply_curve_shape(shape_data)


def share_keys_from_last_selected(*args, tool_operation=None, **_kwargs):
    operation = toolCommon.require_tool_operation(tool_operation)
    target_info = animation.resolve_context(
        default_mode="all_animation",
        include_graph=False,
        include_shapes=True,
        resolve_curves=False,
    )
    _source, targets, frames = _frames_from_last_selected(target_info)
    if not frames:
        return

    keep_curve_shape = get_share_keys_mode() == SHARE_KEYS_MODE_PRESERVE_SHAPE
    curves_by_target = _curves_by_object(target_info, targets)
    operation.set_total(sum(
        len(curves) * len(frames) for curves in curves_by_target.values()
    ))
    toolCommon.ensure_operation_tint(
        operation,
        tint="range",
        timerange=(int(frames[0]), int(frames[-1])),
        tint_key="share_keys_from_last_selected",
    )
    for target in targets:
        if operation.cancelled:
            return
        _set_missing_keys(
            curves_by_target[target],
            frames,
            insert=keep_curve_shape,
            operation=operation,
        )


# ______________________________________ ReBlock Move
def reblock_move(*args, tool_operation=None, **_kwargs):
    """Adjust animation curves to match the majority keyframe timing pattern."""
    target_info = animation.resolve_context(
        default_mode="all_animation",
        include_shapes=True,
        resolve_curves=True,
    )
    if not target_info.objects:
        return

    curves = target_info.curves
    if not curves:
        return animation.notify_empty("animation", "reblock")

    profiles = Counter()
    frames_by_curve = {}

    for curve in curves:
        keyframes = target_info.key_times(curve)
        if not keyframes:
            continue
        frames = tuple(sorted(keyframes))
        frames_by_curve[curve] = frames
        profiles[frames] += 1

    if not profiles:
        return animation.notify_empty("keys", "reblock")

    majority_profile, _ = profiles.most_common(1)[0]

    operation = toolCommon.require_tool_operation(tool_operation)
    operation.set_total(len(curves))
    for curve in curves:
        if operation.cancelled:
            return
        frames = frames_by_curve.get(curve)
        if frames is None:
            operation.step()
            continue

        if frames != majority_profile:
            shape_data = animation.capture_curve_shape([curve], majority_profile)
            if not shape_data.get(curve):
                operation.step()
                continue
            remove_frames = [
                frame for frame in frames if frame not in majority_profile
            ]
            if remove_frames:
                cmds.cutKey(
                    curve,
                    time=[(frame, frame) for frame in remove_frames],
                    clear=True,
                )
            animation.apply_curve_shape(
                shape_data,
                preserve_tangent_types=True,
            )
        operation.step()


def reblock_insert(*args, tool_operation=None, **_kwargs):
    """Insert missing strict-majority key times across resolved curves."""
    target_info = animation.resolve_context(
        default_mode="all_animation",
        include_shapes=True,
        resolve_curves=True,
    )
    curves = _unique(target_info.curves)
    if len(curves) < 2:
        return wutil.make_inViewMessage("Select at least 2 animated channels")

    frames_by_curve = {
        curve: _normalize_key_frames(target_info.key_times(curve))
        for curve in curves
    }
    all_keyframes = [
        frame
        for frames in frames_by_curve.values()
        for frame in frames
    ]

    frame_counts = Counter(all_keyframes)
    minimum_count = len(curves) // 2 + 1
    majority_frames = {
        frame for frame, count in frame_counts.items() if count >= minimum_count
    }
    if not majority_frames:
        return wutil.make_inViewMessage("No shared key pattern found")

    operation = toolCommon.require_tool_operation(tool_operation)
    operation.set_total(len(curves))
    for curve in curves:
        if operation.cancelled:
            return
        existing_frames = set(frames_by_curve.get(curve) or [])
        for frame in sorted(majority_frames - existing_frames):
            try:
                cmds.setKeyframe(curve, time=(frame,), insert=True)
            except (RuntimeError, ValueError, TypeError):
                pass
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
    return animation.sample_times(start_frame, end_frame, interval)


def bake_animation(bake_interval=1, window=None, tool_operation=None):
    operation = toolCommon.require_tool_operation(tool_operation)
    try:
        bake_interval = _validate_bake_interval(bake_interval)
    except ValueError as error:
        return wutil.make_inViewMessage(str(error))

    tool_key = (
        "bake_animation_{}".format(bake_interval)
        if bake_interval in BAKE_TITLES
        else "bake_animation_custom"
    )

    try:
        target_info = animation.resolve_context(
            default_mode="all_animation",
            include_shapes=True,
            resolve_curves=True,
        )
        selected_objects = target_info.objects
        selected_channels = target_info.channels

        if not selected_objects:
            return wutil.make_inViewMessage("Select at least one object for baking")

        time_context = target_info.time
        start_frame, end_frame = time_context.timerange
        bake_tangent_mode = get_bake_tangent_mode()
        curves_to_update = _unique(target_info.curves)

        tangent_types_by_curve = {}
        curve_shape_data = {}
        if bake_tangent_mode == BAKE_TANGENT_MODE_KEEP_TYPE:
            for curve in curves_to_update:
                in_tangent = _most_common_tangent_type(
                    cmds.keyTangent(
                        curve,
                        query=True,
                        time=(start_frame, end_frame),
                        inTangentType=True,
                    )
                )
                out_tangent = _most_common_tangent_type(
                    cmds.keyTangent(
                        curve,
                        query=True,
                        time=(start_frame, end_frame),
                        outTangentType=True,
                    )
                )
                if in_tangent or out_tangent:
                    tangent_types_by_curve[curve] = (in_tangent, out_tangent)
        elif bake_tangent_mode == BAKE_TANGENT_MODE_KEEP_SHAPE:
            sample_times = _bake_sample_times(start_frame, end_frame, bake_interval)
            curve_shape_data = animation.capture_curve_shape(curves_to_update, sample_times)

        operation.set_total(max(
            1, int((end_frame - start_frame) / float(bake_interval or 1)) + 1
        ))
        toolCommon.ensure_operation_tint(
            operation,
            tint="range",
            timerange=time_context.timerange,
            tint_key=tool_key,
        )
        operation.start()
        # Hacer bake a las curvas de animación de los objetos seleccionados.
        bake_kwargs = {
            "time": (start_frame, end_frame),
            "sampleBy": bake_interval,
            "preserveOutsideKeys": True,
            # A sparse bake can legitimately add no keys to an existing
            # anim curve.  Keep-shape mode still needs a key at every
            # sample; bakeResults samples the evaluated curve before it
            # replaces the animation, preserving those full-frame values.
            "sparseAnimCurveBake": False,
            "removeBakedAttributeFromLayer": False,
            "bakeOnOverrideLayer": False,
            "controlPoints": False,
            "shape": True,
        }
        if selected_channels:
            bake_kwargs["attribute"] = selected_channels
        cmds.bakeResults(selected_objects, **bake_kwargs)
        operation.step(
            amount=operation.progress.max_value if operation.progress else 1
        )

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
                    cmds.keyTangent(
                        curve,
                        edit=True,
                        time=(start_frame, end_frame),
                        **tangent_kwargs,
                    )
        elif bake_tangent_mode == BAKE_TANGENT_MODE_KEEP_SHAPE:
            animation.apply_curve_shape(curve_shape_data)

    except Exception as e:
        cmds.warning("An error occurred: {}".format(e))

    if window:
        window.close()


def bake_animation_from_last_selected(*args, tool_operation=None, **_kwargs):
    operation = toolCommon.require_tool_operation(tool_operation)
    target_info = animation.resolve_context(
        default_mode="all_animation",
        include_graph=False,
        include_shapes=True,
        resolve_curves=False,
    )
    _source, targets, frames = _frames_from_last_selected(target_info)
    if not frames:
        return

    current_time = cmds.currentTime(query=True)
    curves_by_target = _curves_by_object(target_info, targets)
    operation.set_total(sum(len(curves) for curves in curves_by_target.values()))
    toolCommon.ensure_operation_tint(
        operation,
        tint="range",
        timerange=(int(frames[0]), int(frames[-1])),
        tint_key="bake_animation_from_last_selected",
    )
    try:
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


def bake_animation_1(*args, tool_operation=None, **_kwargs):
    return bake_animation(bake_interval=1, tool_operation=tool_operation)


def bake_animation_2(*args, tool_operation=None, **_kwargs):
    return bake_animation(bake_interval=2, tool_operation=tool_operation)


def bake_animation_3(*args, tool_operation=None, **_kwargs):
    return bake_animation(bake_interval=3, tool_operation=tool_operation)


def bake_animation_4(*args, tool_operation=None, **_kwargs):
    return bake_animation(bake_interval=4, tool_operation=tool_operation)
