"""Mirror and opposite-control behavior."""

import json
import os

from maya import cmds

import TheKeyMachine.mods.generalMod as general
import TheKeyMachine.mods.reportMod as report
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


def _timeline_tint_color(key):
    import TheKeyMachine.mods.barMod as bar

    return bar._active_tint_color(key)

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


def opposite_control_name(name):
    """Return the configured opposite control name without querying the scene."""
    namespace, _, control_name = name.rpartition(":")
    for pattern, opposite_pattern in MIRROR_PATTERNS:
        if pattern in control_name:
            new_control_name = control_name.replace(pattern, opposite_pattern, 1)
            return f"{namespace}:{new_control_name}" if namespace else new_control_name
    return None


def find_opposite_name(name):
    """Return the configured opposite control when it exists in the scene."""
    opposite_name = opposite_control_name(name)
    return opposite_name if opposite_name and cmds.objExists(opposite_name) else None


# ___________________________ SELECT OPPOSITE _____________________________________

def select_opposite(*args):
    global MIRROR_PATTERNS

    selected_objects = selectionMod.get_selected_objects()
    opposite_controls = []

    for obj in selected_objects:
        opposite_obj = find_opposite_name(obj)
        if opposite_obj and cmds.objExists(opposite_obj):
            opposite_controls.append(opposite_obj)

    if opposite_controls:
        cmds.select(opposite_controls)


def add_select_opposite(*args):
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


def copy_opposite(*args):
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
        ATTRIBUTES_TO_IGNORE = {"tag"}
        exceptions = load_exceptions()

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
                            current_value = apply_exception(exceptions, obj, attr, current_value)
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
        exceptions = load_exceptions()

        def swap_control_values(control1, control2):
            if not cmds.objExists(control1):
                return

            attrs_to_swap = _mirror_keyable_attrs(control1)
            if not attrs_to_swap:
                return

            for attr in attrs_to_swap:
                if not _attr_settable(control1, attr):
                    continue

                try:
                    value1 = cmds.getAttr(f"{control1}.{attr}")

                    # Aplicar excepciones si es necesario
                    value1 = apply_exception(exceptions, control1, attr, value1)

                    if control2 and cmds.objExists(control2) and _attr_settable(control2, attr):
                        value2 = cmds.getAttr(f"{control2}.{attr}")
                        value2 = apply_exception(exceptions, control2, attr, value2)

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


def load_exceptions():
    mirror_exceptions_file_path = general.get_mirror_exceptions_file()
    if os.path.exists(mirror_exceptions_file_path):
        try:
            with open(mirror_exceptions_file_path, "r") as file:
                return json.load(file)
        except Exception:
            return {}
    return {}


def apply_exception(exceptions, control, attr, value):
    control_name = control.rsplit(":", 1)[-1]
    exception_type = (exceptions.get(control_name) or {}).get(attr)
    if exception_type == "invert":
        if isinstance(value, list):
            return [apply_exception(exceptions, control, attr, item) for item in value]
        if isinstance(value, tuple):
            return tuple(apply_exception(exceptions, control, attr, item) for item in value)
        if isinstance(value, (int, float)):
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

    exceptions = load_exceptions()
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
                cmds.setAttr(f"{target}.{attr}", apply_exception(exceptions, source, attr, value))
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

    exceptions = load_exceptions()
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
                    lambda value, node=source, channel=attr: apply_exception(exceptions, node, channel, value),
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


def _update_mirror_exceptions(exception_type):
    selected_controls = selectionMod.get_selected_objects()
    selected_channels = selectionMod.get_selected_channels()
    if not selected_controls or not selected_channels:
        action = "create an exception" if exception_type else "remove exceptions"
        return wutil.make_inViewMessage(f"Select controls and channels to {action}")

    exceptions = load_exceptions()
    for control in selected_controls:
        control_name = control.rsplit(":", 1)[-1]
        control_exceptions = exceptions.setdefault(control_name, {})
        for channel in selected_channels:
            long_name = cmds.attributeQuery(channel, node=control, longName=True)
            if exception_type:
                control_exceptions[long_name] = exception_type
            else:
                control_exceptions.pop(long_name, None)
        if not control_exceptions:
            exceptions.pop(control_name, None)

    json_path = general.get_mirror_exceptions_file()
    os.makedirs(os.path.dirname(json_path), exist_ok=True)
    with open(json_path, "w") as file:
        json.dump(exceptions, file, indent=4)
    cmds.warning("Exception created" if exception_type else "Exception removed")


def add_invert_exception(*args):
    return _update_mirror_exceptions("invert")


def add_keep_exception(*args):
    return _update_mirror_exceptions("keep")


def remove_exception(*args):
    return _update_mirror_exceptions(None)
