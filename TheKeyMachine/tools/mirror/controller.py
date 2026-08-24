"""Mirror and opposite-control behavior."""

from contextlib import contextmanager

from maya import cmds
from maya.api import OpenMaya as om

from TheKeyMachine.maya import animation, maya_api
from TheKeyMachine.tools.mirror import math as mirror_math
from TheKeyMachine.tools.snapshot_rig import rig_snapshot
from TheKeyMachine.tools import common as toolCommon
from TheKeyMachine.tools.copy_paste.controller import (
    ANIMATION_CONTROLS_KEY,
    ANIMATION_FRAME_KEY,
    ANIMATION_LAYERS_KEY,
    ANIMATION_META_KEY,
    ANIMATION_SCHEMA_VERSION,
    ANIMATION_TANGENT_KEY,
    _animation_data_timerange,
    _apply_animation_channels_to_targets,
    configure_copy_paste_operation,
    _query_layered_anim_channel_data,
    _transform_channel_values,
)
import TheKeyMachine.ui.widgets.util as wutil


_MATRIX_TRANSFORM_ATTRS = (
    "translateX", "translateY", "translateZ",
    "rotateX", "rotateY", "rotateZ",
    "scaleX", "scaleY", "scaleZ",
)
_MATRIX_ATTR_GROUPS = {
    "translateX": "translate", "translateY": "translate", "translateZ": "translate",
    "rotateX": "rotate", "rotateY": "rotate", "rotateZ": "rotate",
    "scaleX": "scale", "scaleY": "scale", "scaleZ": "scale",
}


# _____________________________ Opposite-name resolution ______________________________


def opposite_control_name(name):
    return rig_snapshot.opposite_control_name(name)


def find_opposite_name(name):
    return rig_snapshot.find_opposite_name(name)


def _node_identity(node):
    """Return a stable DAG identity for short- and long-name comparisons."""
    if not node:
        return None
    try:
        matches = cmds.ls(node, long=True) or []
    except (RuntimeError, TypeError, ValueError):
        matches = []
    return matches[0] if len(matches) == 1 else node


def _flat_matrix(values):
    if not values:
        return None
    values = values[0] if len(values) == 1 and isinstance(values[0], (list, tuple)) else values
    try:
        values = [float(value) for value in values]
    except (TypeError, ValueError):
        return None
    return values if len(values) == 16 else None


def _matrix_plug_value(node, attr, frame=None):
    try:
        kwargs = {"time": float(frame)} if frame is not None else {}
        return _flat_matrix(cmds.getAttr(f"{node}.{attr}", **kwargs))
    except (RuntimeError, TypeError, ValueError):
        return None


def _center_reflection_matrix(node):
    """Infer the center control's parent-local mirror plane from its snapshot."""
    directions = _control_directions(node)
    axis_attrs = ("translateX", "translateY", "translateZ")
    signs = [
        _effective_direction(node, attr, directions, is_center=True)
        for attr in axis_attrs
    ]
    # A geometric reflection has exactly one negative translation axis. Fall
    # back to parent-local X when custom channels provide no clear plane.
    if signs.count(-1) != 1:
        signs = [-1, 1, 1]
    return om.MMatrix((
        float(signs[0]), 0.0, 0.0, 0.0,
        0.0, float(signs[1]), 0.0, 0.0,
        0.0, 0.0, float(signs[2]), 0.0,
        0.0, 0.0, 0.0, 1.0,
    ))


def _mirrored_channel_matrix(node, frame=None, reflection=None):
    """Return a reflected channel matrix with animated parent motion removed."""
    world = maya_api.world_matrix_at_time(node, frame)
    parent_inverse = maya_api.parent_inverse_matrix_at_time(node, frame)
    if not world or not parent_inverse:
        return None
    try:
        world_matrix = om.MMatrix(world)
        if reflection is None:
            reflection = _center_reflection_matrix(node)
        parent_local = world_matrix * om.MMatrix(parent_inverse)
        channel_matrix = reflection * parent_local * reflection
        offset_parent = _matrix_plug_value(node, "offsetParentMatrix", frame)
        if offset_parent:
            channel_matrix *= om.MMatrix(offset_parent).inverse()
        return list(channel_matrix)
    except (RuntimeError, TypeError, ValueError):
        return None


def _copy_solver_settings(source, target):
    for attr in (
        "rotateOrder", "rotateAxis", "rotatePivot", "rotatePivotTranslate",
        "scalePivot", "scalePivotTranslate",
    ):
        try:
            value = cmds.getAttr(f"{source}.{attr}")
            if isinstance(value, (list, tuple)) and len(value) == 1:
                value = value[0]
            if isinstance(value, (list, tuple)):
                cmds.setAttr(f"{target}.{attr}", *value)
            else:
                cmds.setAttr(f"{target}.{attr}", value)
        except (RuntimeError, TypeError, ValueError):
            continue


@contextmanager
def _matrix_channel_solver(node):
    """Decompose reflected matrices using a transform with matching pivots/axes."""
    solver = cmds.createNode("transform", name="tkmMirrorMatrixSolver#", skipSelect=True)
    try:
        _copy_solver_settings(node, solver)
        reflection = _center_reflection_matrix(node)

        def solve(frame=None):
            matrix = _mirrored_channel_matrix(node, frame, reflection=reflection)
            if not matrix:
                return {}
            try:
                rotate_axis = cmds.getAttr(f"{node}.rotateAxis")[0]
                axis_rotation = om.MEulerRotation(*(
                    om.MAngle(float(value), om.MAngle.kDegrees).asRadians()
                    for value in rotate_axis
                )).asQuaternion()
                axis_transform = om.MTransformationMatrix()
                axis_transform.setRotation(axis_rotation)
                combined_transform = om.MTransformationMatrix(om.MMatrix(matrix))
                total_rotation = combined_transform.rotation(asQuaternion=True)
                total_rotation_transform = om.MTransformationMatrix()
                total_rotation_transform.setRotation(total_rotation)
                channel_rotation_matrix = (
                    axis_transform.asMatrix().inverse()
                    * total_rotation_transform.asMatrix()
                )
                euler = om.MTransformationMatrix(
                    channel_rotation_matrix
                ).rotation(asQuaternion=False)
                rotate_order = int(cmds.getAttr(f"{node}.rotateOrder"))
                euler.reorderIt(rotate_order)
                try:
                    kwargs = {"time": float(frame)} if frame is not None else {}
                    current_values = cmds.getAttr(f"{node}.rotate", **kwargs)[0]
                    current_euler = om.MEulerRotation(*(
                        om.MAngle(float(value), om.MAngle.kDegrees).asRadians()
                        for value in current_values
                    ), rotate_order)
                    euler = euler.closestSolution(current_euler)
                except (RuntimeError, TypeError, ValueError):
                    pass
                rotation = mirror_math.normalize_euler_degrees(tuple(
                    om.MAngle(value, om.MAngle.kRadians).asDegrees()
                    for value in (euler.x, euler.y, euler.z)
                ))
                scale = tuple(combined_transform.scale(om.MSpace.kTransform))

                cmds.setAttr(f"{solver}.translate", 0.0, 0.0, 0.0)
                cmds.setAttr(f"{solver}.rotate", *rotation)
                cmds.setAttr(f"{solver}.scale", *scale)
                pivot_matrix = cmds.xform(
                    solver, query=True, objectSpace=True, matrix=True,
                )
                translation = tuple(
                    float(matrix[index]) - float(pivot_matrix[index])
                    for index in (12, 13, 14)
                )
                return {
                    "translateX": translation[0],
                    "translateY": translation[1],
                    "translateZ": translation[2],
                    "rotateX": rotation[0],
                    "rotateY": rotation[1],
                    "rotateZ": rotation[2],
                    "scaleX": scale[0],
                    "scaleY": scale[1],
                    "scaleZ": scale[2],
                }
            except (RuntimeError, TypeError, ValueError):
                return {}

        yield solve
    finally:
        if cmds.objExists(solver):
            cmds.delete(solver)


# ___________________________ SELECT OPPOSITE _____________________________________

def select_opposite(*args):
    selected_objects = list(animation.current_selection_snapshot().objects)
    opposite_controls = []

    for obj in selected_objects:
        opposite_obj = find_opposite_name(obj)
        if opposite_obj:
            opposite_controls.append(opposite_obj)

    if opposite_controls:
        cmds.select(opposite_controls)


def add_select_opposite(*args):
    selected_objects = list(animation.current_selection_snapshot().objects)
    opposite_controls = []

    for obj in selected_objects:
        opposite_obj = find_opposite_name(obj)
        if opposite_obj:
            opposite_controls.append(opposite_obj)

    if opposite_controls:
        cmds.select(opposite_controls, add=True)


# ___________________________ Copy Opposite _____________________________________


def copy_opposite(*args):
    operation = toolCommon.require_tool_operation()
    try:
        selected_objects = list(animation.current_selection_snapshot().objects)
        operation.set_total(len(selected_objects)).set_status("Copy Opposite")
        ATTRIBUTES_TO_IGNORE = {"tag"}

        def replace_pattern_in_attribute(attr):
            for from_pattern, to_pattern in rig_snapshot.MIRROR_PATTERNS:
                if from_pattern in attr:
                    return attr.replace(from_pattern, to_pattern)
            return attr

        for obj in selected_objects:
            if operation.cancelled:
                break
            opposite_obj = find_opposite_name(obj)

            # Comprobamos si el objeto opuesto es válido y existe
            if opposite_obj:
                keyable_attrs = cmds.listAttr(obj, keyable=True) or []
                directions = _control_directions(obj)

                for attr in keyable_attrs:
                    if attr in ATTRIBUTES_TO_IGNORE:
                        continue

                    opposite_attr = replace_pattern_in_attribute(attr)

                    if not cmds.getAttr(f"{opposite_obj}.{opposite_attr}", lock=True):
                        try:
                            current_value = cmds.getAttr(f"{obj}.{attr}")
                            current_value = apply_exception(
                                obj, attr, current_value, directions=directions,
                                target=opposite_obj, target_attr=opposite_attr,
                            )
                            cmds.setAttr(f"{opposite_obj}.{opposite_attr}", current_value)
                        except Exception as e:
                            import TheKeyMachine.tools.bug_report.controller as report

                            report.report_detected_exception(e, context="copy opposite attribute compile")
            operation.step()
    except Exception as e:
        cmds.warning("Error during copy: {}".format(str(e)))


# ________________________________________________________________ MIRROR _______________________________________________________________________ #


def mirror(*args):
    target_info = animation.resolve_context(
        default_mode="current_frame", include_channels=True
    )
    selected_controls = target_info.objects
    if not selected_controls:
        return wutil.make_inViewMessage("Select at least one object")

    time_context = target_info.time
    if time_context.mode != "current_frame":
        # A time-slider range or Graph Editor key selection is active -- mirror
        # just those keys instead of swapping the current frame's live value.
        return _mirror_keys(selected_controls, time_context, tool_id="mirror", label="Mirror")

    operation = toolCommon.require_tool_operation()
    try:
        selected_channels = set(target_info.channels or [])
        operation.set_total(len(selected_controls)).set_status("Mirror")
        toolCommon.ensure_operation_tint(
            operation,
            tint="context",
            default_mode="current_frame",
            tint_key="mirror",
        )
        pending_writes = []

        def swap_control_values(control1, control2):
            if not cmds.objExists(control1):
                return

            attrs_to_swap = _target_attrs(control1, selected_channels)
            if not attrs_to_swap:
                return
            directions1 = _control_directions(control1)
            directions2 = _control_directions(control2) if control2 else {}
            defaults1 = _control_defaults(control1)
            defaults2 = _control_defaults(control2) if control2 else defaults1
            matrix_values = {}
            if not control2:
                with _matrix_channel_solver(control1) as solve_matrix:
                    matrix_values = solve_matrix()

            for attr in attrs_to_swap:
                if not _attr_settable(control1, attr):
                    continue

                try:
                    value1 = cmds.getAttr(f"{control1}.{attr}")
                    if not control2 and attr in matrix_values:
                        value1 = matrix_values[attr]
                    else:
                        value1 = apply_exception(
                            control1, attr, value1, directions=directions1,
                            target=control2, source_defaults=defaults1,
                            target_defaults=defaults2,
                        )

                    if control2 and cmds.objExists(control2) and _attr_settable(control2, attr):
                        value2 = cmds.getAttr(f"{control2}.{attr}")
                        value2 = apply_exception(
                            control2, attr, value2, directions=directions2,
                            target=control1, source_defaults=defaults2,
                            target_defaults=defaults1,
                        )

                        pending_writes.append((control2, attr, value1))
                        pending_writes.append((control1, attr, value2))
                    else:  # Solo un control (central o único)
                        # ``apply_exception`` includes the conventional center
                        # directions and mirrors around this control's default.
                        pending_writes.append((control1, attr, value1))

                except Exception as e:
                    cmds.warning(f"Could not process the attribute {attr} on {control1}: {str(e)}")

        def mirror_controls():
            processed_controls = set()

            for control in selected_controls:
                if operation.cancelled:
                    break
                control_identity = _node_identity(control)
                if control_identity in processed_controls:
                    operation.step()
                    continue

                opposite_name = find_opposite_name(control)
                if opposite_name:
                    # Si el control opuesto no está seleccionado, aún así procede con el espejado
                    swap_control_values(control, opposite_name)
                    processed_controls.add(control_identity)
                    processed_controls.add(_node_identity(opposite_name))
                else:
                    # Tratar como control central o único si no se encuentra un opuesto
                    swap_control_values(control, None)
                    processed_controls.add(control_identity)

                operation.step()

        mirror_controls()
        if not operation.cancelled:
            for control, attr, value in pending_writes:
                try:
                    cmds.setAttr(f"{control}.{attr}", value)
                except Exception as e:
                    cmds.warning(f"Could not set the attribute {attr} on {control}: {str(e)}")
    except Exception as e:
        cmds.warning("Error during mirroring: {}".format(str(e)))


# ------------------------------- mirror to opposite


def _mirror_token_side(token):
    clean = str(token or "").strip("_").lower()
    if clean in {"r", "rt", "rg", "rf", "right"}:
        return "right"
    if clean in {"l", "lf", "left"}:
        return "left"
    return None


def _mirror_control_side(control):
    _namespace, _sep, control_name = control.rpartition(":")
    for pattern, _opposite_pattern in rig_snapshot.MIRROR_PATTERNS:
        if pattern in control_name:
            return _mirror_token_side(pattern)
    return None


def _control_directions(control):
    if not control:
        return {}
    return rig_snapshot.resolve_control_snapshot(
        control, "mirror", compute_fn=lambda _node: {},
    ) or {}


def _control_defaults(control):
    if not control:
        return {}
    try:
        return rig_snapshot.resolve_control_snapshot(
            control, "default", compute_fn=lambda _node: {},
        ) or {}
    except (RuntimeError, TypeError, ValueError):
        return {}


def _attribute_default(control, attr, defaults):
    if not control:
        return None
    stored = rig_snapshot.get_attr_value(control, defaults, attr)
    if stored is not None:
        return stored
    try:
        fallback = cmds.attributeQuery(attr, node=control, listDefault=True)
    except (RuntimeError, TypeError, ValueError):
        fallback = None
    return fallback[0] if fallback else None


def apply_exception(
    control,
    attr,
    value,
    directions=None,
    target=None,
    target_attr=None,
    source_defaults=None,
    target_defaults=None,
    use_defaults=True,
):
    """Mirror ``value`` from ``control`` into ``target``'s value space.

    A sign by itself is only correct for zeroed controls.  Snapshot Rig also
    records non-zero default poses, so live and pose values apply the detected
    keep/invert direction to the offset from the source default and rebuild it
    around the target default. Raw animation-layer values opt out because
    additive layers are deltas. This preserves zero-default behavior.
    """
    if directions is None:
        directions = _control_directions(control)
    if target is None:
        try:
            target = find_opposite_name(control)
        except (RuntimeError, TypeError, ValueError):
            target = None
    is_center = not target or target == control
    direction = _effective_direction(
        control, attr, directions, is_center=is_center,
    )

    if not use_defaults:
        return _apply_direction(direction, value)

    if source_defaults is None:
        source_defaults = _control_defaults(control)
    if target_defaults is None:
        target_defaults = source_defaults if is_center else _control_defaults(target)
    source_default = _attribute_default(control, attr, source_defaults)
    target_default = (
        source_default if is_center
        else _attribute_default(target, target_attr or attr, target_defaults)
    )
    return _apply_direction(direction, value, source_default, target_default)


def _apply_direction(direction, value, source_default=0.0, target_default=0.0):
    return mirror_math.transform_value(
        value, direction, source_default, target_default,
    )


def _effective_direction(control, attr, directions, is_center=False):
    direction = rig_snapshot.get_attr_value(control, directions, attr)
    if direction is None:
        return -1 if is_center and attr in rig_snapshot.CENTER_INVERT_ATTRS else 1
    return direction


def _invert_tangent_angles(channel_data):
    """Reflect tangent slopes along with values for an inverted animation curve."""
    tangents = dict((channel_data or {}).get(ANIMATION_TANGENT_KEY) or {})
    for key in ("ia", "oa"):
        if key in tangents:
            tangents[key] = [
                -value if isinstance(value, (int, float)) and not isinstance(value, bool)
                else value
                for value in tangents[key]
            ]
    if tangents:
        channel_data[ANIMATION_TANGENT_KEY] = tangents
    for layer in (channel_data or {}).get(ANIMATION_LAYERS_KEY) or []:
        if isinstance(layer, dict) and isinstance(layer.get("data"), dict):
            _invert_tangent_angles(layer["data"])
    return channel_data


def _transform_mirror_channel(channel_data, transform_value, direction):
    transformed = _transform_channel_values(channel_data, transform_value)
    return _invert_tangent_angles(transformed) if direction == -1 else transformed


def _mirror_keyable_attrs(control):
    return [
        attr for attr in (cmds.listAttr(control, keyable=True) or [])
        if attr not in rig_snapshot.MIRROR_ATTRS_TO_IGNORE
    ]


def _target_attrs(control, selected_channels):
    """Restrict the mirrorable attrs of ``control`` to ``selected_channels`` when set."""
    attrs = _mirror_keyable_attrs(control)
    if not selected_channels:
        return attrs
    selected = set(selected_channels)
    matched = []
    for attr in attrs:
        try:
            short_attr = cmds.attributeQuery(attr, node=control, shortName=True)
        except (RuntimeError, TypeError, ValueError):
            short_attr = None
        if attr in selected or short_attr in selected:
            matched.append(attr)
    return matched


def _attr_settable(control, attr):
    try:
        return bool(cmds.getAttr(f"{control}.{attr}", settable=True))
    except Exception:
        return False


def _key_times_for_attr(control, attr, time_context):
    kwargs = {"query": True, "timeChange": True}
    if time_context.mode == "graph_editor_keys":
        kwargs["selected"] = True
    elif time_context.mode == "time_slider_range":
        kwargs["time"] = time_context.timerange
    try:
        return sorted(set(float(value) for value in (
            cmds.keyframe(f"{control}.{attr}", **kwargs) or []
        )))
    except (RuntimeError, TypeError, ValueError):
        return []


def _expanded_matrix_attrs(control, attrs):
    """Keep coupled TRS groups together when any axis in the group is targeted."""
    groups = {
        _MATRIX_ATTR_GROUPS[attr]
        for attr in attrs
        if attr in _MATRIX_ATTR_GROUPS
    }
    return [
        attr for attr in _MATRIX_TRANSFORM_ATTRS
        if _MATRIX_ATTR_GROUPS[attr] in groups and _attr_settable(control, attr)
    ]


def _capture_center_key_plan(source, attrs, time_context):
    """Capture a complete center-control result without changing animation."""
    matrix_seed_attrs = [attr for attr in attrs if attr in _MATRIX_ATTR_GROUPS]
    times_by_attr = {
        attr: _key_times_for_attr(source, attr, time_context)
        for attr in matrix_seed_attrs
    }
    frames = sorted(set(
        frame for attr_times in times_by_attr.values() for frame in attr_times
    ))
    matrix_attrs = _expanded_matrix_attrs(
        source,
        [attr for attr, attr_times in times_by_attr.items() if attr_times],
    )
    solved_frames = {}
    if frames and matrix_attrs:
        # Sample every result before changing any curve. Otherwise editing an
        # early key can alter interpolation and contaminate later samples.
        with _matrix_channel_solver(source) as solve_matrix:
            solved_frames = {
                frame: solve_matrix(frame)
                for frame in frames
            }

    # Non-transform/custom channels still use their saved keep/invert rule and
    # the existing layer-aware payload path.
    directions = _control_directions(source)
    custom_channels = {}
    for attr in attrs:
        if attr in _MATRIX_ATTR_GROUPS or not _attr_settable(source, attr):
            continue
        channel_data = _query_layered_anim_channel_data(
            f"{source}.{attr}", time_context,
        )
        if not channel_data.get(ANIMATION_FRAME_KEY) and not channel_data.get(ANIMATION_LAYERS_KEY):
            continue
        direction = _effective_direction(
            source, attr, directions, is_center=True,
        )
        custom_channels[attr] = _transform_mirror_channel(
            channel_data,
            lambda value, channel=attr: apply_exception(
                source, channel, value, directions=directions,
                target=None, use_defaults=False,
            ),
            direction,
        )
    custom_frames = []
    for channel_data in custom_channels.values():
        custom_frames.extend(channel_data.get(ANIMATION_FRAME_KEY) or [])
    return {
        "source": source,
        "frames": sorted(set(float(frame) for frame in frames + custom_frames)),
        "matrix_attrs": matrix_attrs,
        "solved_frames": solved_frames,
        "custom_channels": custom_channels,
    }


def _apply_center_key_plan(plan):
    source = plan["source"]
    keyed = 0
    for frame, values in (plan.get("solved_frames") or {}).items():
        for attr in plan.get("matrix_attrs") or []:
            if attr not in values:
                continue
            try:
                result = cmds.setKeyframe(
                    source,
                    attribute=attr,
                    time=(frame,),
                    value=values[attr],
                )
                keyed += int(bool(result))
            except (RuntimeError, TypeError, ValueError):
                continue
    custom_channels = plan.get("custom_channels") or {}
    if custom_channels:
        keyed += _apply_animation_channels_to_targets(
            [source], custom_channels, replace=True,
        )
    return keyed


def _mirror_center_keys(source, attrs, time_context):
    """Capture then apply one center control (used by focused callers/tests)."""
    plan = _capture_center_key_plan(source, attrs, time_context)
    return _apply_center_key_plan(plan), plan["frames"]


def _capture_pair_key_channels(source, target, attrs, time_context):
    directions = _control_directions(source)
    channels = {}
    for attr in attrs:
        if not _attr_settable(source, attr) or not _attr_settable(target, attr):
            continue
        channel_data = _query_layered_anim_channel_data(
            f"{source}.{attr}", time_context,
        )
        if not channel_data.get(ANIMATION_FRAME_KEY) and not channel_data.get(ANIMATION_LAYERS_KEY):
            continue
        direction = _effective_direction(
            source, attr, directions, is_center=False,
        )
        channels[attr] = _transform_mirror_channel(
            channel_data,
            lambda value, node=source, destination=target, channel=attr,
            saved=directions: apply_exception(
                node, channel, value, directions=saved, target=destination,
                use_defaults=False,
            ),
            direction,
        )
    return channels


def _mirror_keys(selected_controls, time_context, tool_id, label, target_side=None):
    selected_channels = set(animation.current_selection_snapshot().channels)
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
    processed_frames = set()
    source_side = (
        "left" if target_side == "right"
        else "right" if target_side == "left"
        else None
    )
    center_plans = []
    pair_plans = []

    operation = configure_copy_paste_operation(
        tool_id,
        label,
        tint="range",
        progress_max=len(selected_controls),
    )
    operation.start()
    for source in selected_controls:
        if operation.cancelled:
            break
        source_identity = _node_identity(source)
        if source_identity in processed_controls:
            operation.step()
            continue
        if source_side and _mirror_control_side(source) != source_side:
            operation.step()
            continue
        target = find_opposite_name(source)
        if target_side and (
            not target or _mirror_control_side(target) != target_side
        ):
            operation.step()
            continue
        if not target or not cmds.objExists(target):
            attrs = _target_attrs(source, selected_channels)
            center_plan = _capture_center_key_plan(source, attrs, time_context)
            if center_plan["frames"]:
                center_plans.append(center_plan)
                processed_frames.update(center_plan["frames"])
            processed_controls.add(source_identity)
            operation.step()
            continue
        processed_controls.add(source_identity)
        processed_controls.add(_node_identity(target))
        target_channels = _capture_pair_key_channels(
            source, target,
            _target_attrs(source, selected_channels),
            time_context,
        )
        if target_channels:
            pair_plans.append((target, target_channels))
            channel_range = _animation_data_timerange({
                ANIMATION_CONTROLS_KEY: {target: target_channels},
            })
            if channel_range:
                processed_frames.update(channel_range)

        # Regular Mirror is a true two-sided swap. Directional commands
        # intentionally capture only source -> destination.
        if target_side is None:
            source_channels = _capture_pair_key_channels(
                target, source,
                _target_attrs(target, selected_channels),
                time_context,
            )
            if source_channels:
                pair_plans.append((source, source_channels))
                channel_range = _animation_data_timerange({
                    ANIMATION_CONTROLS_KEY: {source: source_channels},
                })
                if channel_range:
                    processed_frames.update(channel_range)

        operation.step()

    # Nothing is written until every selected control has been sampled.
    # Cancellation during capture therefore leaves the scene untouched.
    if not operation.cancelled:
        for plan in center_plans:
            key_count += _apply_center_key_plan(plan)
        for destination, channels in pair_plans:
            key_count += _apply_animation_channels_to_targets(
                [destination], channels, replace=True,
            )
            mirrored_data[ANIMATION_CONTROLS_KEY][destination] = channels

    if key_count:
        payload_range = _animation_data_timerange(mirrored_data)
        if payload_range:
            processed_frames.update(payload_range)
        timerange = (
            (min(processed_frames), max(processed_frames))
            if processed_frames else None
        )
        operation.succeed(label, timerange=timerange)
    else:
        cmds.warning("No mirrorable animation keys found")


def _mirror_current_values(target_side=None, operation=None):
    target_info = animation.resolve_context(
        default_mode="current_frame", include_channels=True
    )
    selected_controls = target_info.objects
    if not selected_controls:
        return wutil.make_inViewMessage("Select at least one object")

    selected_channels = set(target_info.channels or [])
    copied = 0
    source_side = (
        "left" if target_side == "right"
        else "right" if target_side == "left"
        else None
    )
    jobs = []
    seen_pairs = set()

    for source in selected_controls:
        if operation and operation.cancelled:
            break
        if source_side and _mirror_control_side(source) != source_side:
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

        pair = frozenset((_node_identity(source), _node_identity(target)))
        if pair in seen_pairs:
            if operation:
                operation.step()
            continue
        seen_pairs.add(pair)
        directions = _control_directions(source)
        source_defaults = _control_defaults(source)
        target_defaults = _control_defaults(target)
        values = {}
        for attr in _target_attrs(source, selected_channels):
            if not _attr_settable(source, attr) or not _attr_settable(target, attr):
                continue
            try:
                values[attr] = cmds.getAttr(f"{source}.{attr}")
            except (RuntimeError, TypeError, ValueError):
                continue
        jobs.append((
            source, target, values, directions,
            source_defaults, target_defaults,
        ))
        if operation:
            operation.step()

    # Apply only after every source has been captured. This guarantees a
    # directional mirror never reads a destination value it just overwrote.
    for source, target, values, directions, source_defaults, target_defaults in jobs:
        if operation and operation.cancelled:
            break
        for attr, value in values.items():
            try:
                cmds.setAttr(
                    f"{target}.{attr}",
                    apply_exception(
                        source, attr, value, directions=directions, target=target,
                        source_defaults=source_defaults, target_defaults=target_defaults,
                    ),
                )
                copied += 1
            except Exception as e:
                cmds.warning(f"Could not mirror {source}.{attr} to {target}: {str(e)}")

    if not copied:
        cmds.warning("No mirrorable opposite controls or attributes found")
    return copied


def mirror_to_right(*args):
    target_info = animation.resolve_context(default_mode="current_frame", include_channels=True)
    selected_controls = target_info.objects
    time_context = target_info.time
    if time_context.mode != "current_frame":
        return _mirror_keys(
            selected_controls,
            time_context,
            tool_id="mirror_to_right",
            label="Mirror To Right",
            target_side="right",
        )
    operation = toolCommon.require_tool_operation()
    operation.set_total(len(selected_controls)).set_status("Mirror To Right")
    toolCommon.ensure_operation_tint(
        operation,
        tint="context",
        default_mode="current_frame",
        tint_key="mirror_to_right",
    )
    return _mirror_current_values(target_side="right", operation=operation)


def mirror_to_left(*args):
    target_info = animation.resolve_context(default_mode="current_frame", include_channels=True)
    selected_controls = target_info.objects
    time_context = target_info.time
    if time_context.mode != "current_frame":
        return _mirror_keys(
            selected_controls,
            time_context,
            tool_id="mirror_to_left",
            label="Mirror To Left",
            target_side="left",
        )
    operation = toolCommon.require_tool_operation()
    operation.set_total(len(selected_controls)).set_status("Mirror To Left")
    toolCommon.ensure_operation_tint(
        operation,
        tint="context",
        default_mode="current_frame",
        tint_key="mirror_to_left",
    )
    return _mirror_current_values(target_side="left", operation=operation)


def mirror_all_keys(*args):
    target_info = animation.resolve_context(default_mode="all_animation", include_channels=True)
    selected_controls = target_info.objects
    if not selected_controls:
        return wutil.make_inViewMessage("Select at least one object")

    time_context = target_info.time
    return _mirror_keys(selected_controls, time_context, tool_id="mirror_all_keys", label="Animation Mirrored")


def _update_mirror_directions(direction):
    snapshot = animation.current_selection_snapshot()
    selected_controls = list(snapshot.objects)
    selected_channels = list(snapshot.channels)
    if not selected_controls or not selected_channels:
        action = "create an exception" if direction is not None else "remove exceptions"
        return wutil.make_inViewMessage(f"Select controls and channels to {action}")

    groups = rig_snapshot.group_controls_by_rig(selected_controls)
    if not groups:
        return wutil.make_inViewMessage("Selected controls are not part of a recognizable rig")

    for rig_id, group in groups.items():
        entries = {}
        for control in group["controls"]:
            control_entries = {}
            for channel in selected_channels:
                short_name = cmds.attributeQuery(channel, node=control, shortName=True)
                control_entries[short_name] = direction
            entries[rig_snapshot.control_key(control)] = control_entries
        rig_snapshot.merge_control_entries(rig_id, "mirror", entries)

    cmds.warning("Exception created" if direction is not None else "Exception removed")


def add_invert_exception(*args):
    return _update_mirror_directions(-1)


def add_keep_exception(*args):
    return _update_mirror_directions(1)


def remove_exception(*args):
    return _update_mirror_directions(None)
