"""Mirror and opposite-control behavior."""

from maya import cmds

from TheKeyMachine.core import rig_snapshot
import TheKeyMachine.mods.selectionMod as selectionMod
from TheKeyMachine.tools import common as toolCommon
from TheKeyMachine.tools.copy_paste.controller import (
    ANIMATION_CONTROLS_KEY,
    ANIMATION_FRAME_KEY,
    ANIMATION_LAYERS_KEY,
    ANIMATION_META_KEY,
    ANIMATION_SCHEMA_VERSION,
    _animation_data_timerange,
    _apply_animation_channels_to_targets,
    _copy_paste_operation,
    _query_layered_anim_channel_data,
    _transform_channel_values,
)
import TheKeyMachine.widgets.timeline as timelineWidgets
import TheKeyMachine.widgets.util as wutil


# _____________________________ Opposite-name resolution ______________________________


def opposite_control_name(name):
    return rig_snapshot.opposite_control_name(name)


def find_opposite_name(name):
    return rig_snapshot.find_opposite_name(name)


# ___________________________ SELECT OPPOSITE _____________________________________

def select_opposite(*args):
    selected_objects = selectionMod.get_selected_objects()
    opposite_controls = []

    for obj in selected_objects:
        opposite_obj = find_opposite_name(obj)
        if opposite_obj:
            opposite_controls.append(opposite_obj)

    if opposite_controls:
        cmds.select(opposite_controls)


def add_select_opposite(*args):
    selected_objects = selectionMod.get_selected_objects()
    opposite_controls = []

    for obj in selected_objects:
        opposite_obj = find_opposite_name(obj)
        if opposite_obj:
            opposite_controls.append(opposite_obj)

    if opposite_controls:
        cmds.select(opposite_controls, add=True)


# ___________________________ Copy Opposite _____________________________________


def copy_opposite(*args):
    operation_manager = None
    operation_context = None
    try:
        selected_objects = selectionMod.get_selected_objects()
        operation_manager = toolCommon.tool_operation(
            tool_id="copy_opposite",
            label="Copy Opposite",
            progress=True,
            progress_max=len(selected_objects),
            undo=True
        )
        operation_context = operation_manager.__enter__()
        operation_context.start()
        ATTRIBUTES_TO_IGNORE = {"tag"}

        def replace_pattern_in_attribute(attr):
            for from_pattern, to_pattern in rig_snapshot.MIRROR_PATTERNS:
                if from_pattern in attr:
                    return attr.replace(from_pattern, to_pattern)
            return attr

        for obj in selected_objects:
            if operation_context.cancelled:
                break
            opposite_obj = find_opposite_name(obj)

            # Comprobamos si el objeto opuesto es válido y existe
            if opposite_obj:
                keyable_attrs = cmds.listAttr(obj, keyable=True) or []

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
        if operation_manager and operation_context is not None:
            try:
                operation_manager.__exit__(None, None, None)
            except Exception:
                pass


# ________________________________________________________________ MIRROR _______________________________________________________________________ #


def mirror(*args):
    selected_controls = selectionMod.get_selected_objects()
    if not selected_controls:
        return wutil.make_inViewMessage("Select at least one object")

    time_context = timelineWidgets.resolve_time_context(default_mode="current_frame")
    if time_context.mode != "current_frame":
        # A time-slider range or Graph Editor key selection is active -- mirror
        # just those keys instead of swapping the current frame's live value.
        return _mirror_keys(selected_controls, time_context, tool_id="mirror", label="Mirror")

    operation_manager = None
    operation_context = None
    try:
        selected_channels = set(selectionMod.get_selected_channels() or [])

        operation_manager = toolCommon.tool_operation(
            tool_id="mirror",
            label="Mirror",
            progress=True,
            progress_max=len(selected_controls),
            undo=True,
            tint="context",
            default_mode="current_frame",
            tint_key="mirror",
        )
        operation_context = operation_manager.__enter__()
        operation_context.start()

        def swap_control_values(control1, control2):
            if not cmds.objExists(control1):
                return

            attrs_to_swap = _target_attrs(control1, selected_channels)
            if not attrs_to_swap:
                return

            for attr in attrs_to_swap:
                if not _attr_settable(control1, attr):
                    continue

                try:
                    value1 = cmds.getAttr(f"{control1}.{attr}")
                    value1 = apply_exception(control1, attr, value1)

                    if control2 and cmds.objExists(control2) and _attr_settable(control2, attr):
                        value2 = cmds.getAttr(f"{control2}.{attr}")
                        value2 = apply_exception(control2, attr, value2)

                        cmds.setAttr(f"{control2}.{attr}", value1)
                        cmds.setAttr(f"{control1}.{attr}", value2)
                    else:  # Solo un control (central o único)
                        exceptions = rig_snapshot.resolve_control_snapshot(control1, "mirror", compute_fn=lambda n: {})
                        if attr in (exceptions or {}):
                            exception_type = exceptions[attr]
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
                    swap_control_values(control, opposite_name)
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
        if operation_manager and operation_context is not None:
            try:
                operation_manager.__exit__(None, None, None)
            except Exception:
                pass


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


def apply_exception(control, attr, value):
    exceptions = rig_snapshot.resolve_control_snapshot(control, "mirror", compute_fn=lambda n: {})
    return _apply_exception_type((exceptions or {}).get(attr), value)


def _apply_exception_type(exception_type, value):
    if exception_type == "invert":
        if isinstance(value, list):
            return [_apply_exception_type(exception_type, item) for item in value]
        if isinstance(value, tuple):
            return tuple(_apply_exception_type(exception_type, item) for item in value)
        if isinstance(value, (int, float)):
            return -value
    return value


def _mirror_keyable_attrs(control):
    return [attr for attr in (cmds.listAttr(control, keyable=True) or []) if attr != "tag"]


def _target_attrs(control, selected_channels):
    """Restrict the mirrorable attrs of ``control`` to ``selected_channels`` when set."""
    attrs = _mirror_keyable_attrs(control)
    if not selected_channels:
        return attrs
    return [attr for attr in attrs if attr in selected_channels]


def _attr_settable(control, attr):
    try:
        return bool(cmds.getAttr(f"{control}.{attr}", settable=True))
    except Exception:
        return False


def _mirror_keys(selected_controls, time_context, tool_id, label):
    selected_channels = set(selectionMod.get_selected_channels() or [])
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
        tool_id,
        label,
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
            for attr in _target_attrs(source, selected_channels):
                if not _attr_settable(source, attr) or not _attr_settable(target, attr):
                    continue
                plug = f"{source}.{attr}"
                channel_data = _query_layered_anim_channel_data(plug, time_context)
                if not channel_data.get(ANIMATION_FRAME_KEY) and not channel_data.get(ANIMATION_LAYERS_KEY):
                    continue
                target_channels[attr] = _transform_channel_values(
                    channel_data,
                    lambda value, node=source, channel=attr: apply_exception(node, channel, value),
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


def _mirror_current_values(target_side=None, operation=None):
    selected_controls = selectionMod.get_selected_objects()
    if not selected_controls:
        return wutil.make_inViewMessage("Select at least one object")

    selected_channels = set(selectionMod.get_selected_channels() or [])
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

        for attr in _target_attrs(source, selected_channels):
            if not _attr_settable(source, attr) or not _attr_settable(target, attr):
                continue
            try:
                value = cmds.getAttr(f"{source}.{attr}")
                cmds.setAttr(f"{target}.{attr}", apply_exception(source, attr, value))
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
    ) as operation:
        operation.start()
        return _mirror_current_values(target_side="left", operation=operation)


def mirror_all_keys(*args):
    selected_controls = selectionMod.get_selected_objects()
    if not selected_controls:
        return wutil.make_inViewMessage("Select at least one object")

    time_context = timelineWidgets.resolve_time_context(default_mode="all_animation")
    return _mirror_keys(selected_controls, time_context, tool_id="mirror_all_keys", label="Animation Mirrored")


def _update_mirror_exceptions(exception_type):
    selected_controls = selectionMod.get_selected_objects()
    selected_channels = selectionMod.get_selected_channels()
    if not selected_controls or not selected_channels:
        action = "create an exception" if exception_type else "remove exceptions"
        return wutil.make_inViewMessage(f"Select controls and channels to {action}")

    groups = rig_snapshot.group_controls_by_rig(selected_controls)
    if not groups:
        return wutil.make_inViewMessage("Selected controls are not part of a recognizable rig")

    for rig_id, group in groups.items():
        entries = {}
        for control in group["controls"]:
            control_entries = {}
            for channel in selected_channels:
                long_name = cmds.attributeQuery(channel, node=control, longName=True)
                control_entries[long_name] = exception_type
            entries[rig_snapshot.control_key(control)] = control_entries
        rig_snapshot.merge_control_entries(rig_id, "mirror", entries)

    cmds.warning("Exception created" if exception_type else "Exception removed")


def add_invert_exception(*args):
    return _update_mirror_exceptions("invert")


def add_keep_exception(*args):
    return _update_mirror_exceptions("keep")


def remove_exception(*args):
    return _update_mirror_exceptions(None)
