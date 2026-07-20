"""Copy Relationship behavior and runtime callbacks."""

from maya import cmds
from maya.api import OpenMaya as om

import TheKeyMachine.core.runtimeManager as runtime
from TheKeyMachine.core import toolbox
import TheKeyMachine.mods.selectionMod as selectionMod
import TheKeyMachine.mods.settingsMod as settings
from TheKeyMachine.tools import clipboard
from TheKeyMachine.tools import common as toolCommon
from TheKeyMachine.widgets import timeline as timelineWidgets
from TheKeyMachine.widgets import util as wutil


RUNTIME_KEY = "link_objects_auto_link"
SETTING_KEY = "link_checkbox_state"
_callback_suspended = False


def _matrix(values):
    values = list(values or ())
    if len(values) != 16:
        raise ValueError("Expected a 16-value Maya transform matrix")
    return om.MMatrix(values)


def _matrix_values(matrix):
    return [float(value) for value in matrix]


def _load_relationship(warn=True):
    data = clipboard.load(
        "copy_link",
        "No relationship data found. Copy a relationship first" if warn else None,
    )
    if not isinstance(data, dict):
        return None
    driver = data.get("main_obj")
    offsets = data.get("relative_matrices")
    if not driver or not isinstance(offsets, dict) or not offsets:
        if warn:
            cmds.warning("Saved relationship data is invalid")
        return None
    return data


def _existing_relationship(data, warn=True):
    if not data:
        return None, []
    driver = data["main_obj"]
    if not cmds.objExists(driver):
        if warn:
            cmds.warning("Relationship driver no longer exists: {}".format(driver))
        return None, []
    followers = [node for node in data["relative_matrices"] if cmds.objExists(node)]
    if not followers and warn:
        cmds.warning("No saved relationship followers exist in the scene")
    return driver, followers


def copy_relationship(*_args, tool_operation=None, **_kwargs):
    selection = selectionMod.get_selected_objects()
    if len(selection) < 2:
        return wutil.make_inViewMessage("Select followers first, then the driver")

    driver = selection[-1]
    followers = selection[:-1]
    driver_matrix = _matrix(cmds.xform(driver, query=True, matrix=True, worldSpace=True))
    driver_inverse = driver_matrix.inverse()
    offsets = {}

    for follower in followers:
        follower_matrix = _matrix(cmds.xform(follower, query=True, matrix=True, worldSpace=True))
        offsets[follower] = _matrix_values(follower_matrix * driver_inverse)

    clipboard.save(
        "copy_link",
        {"main_obj": driver, "relative_matrices": offsets},
    )
    if is_auto_link_enabled():
        enable_auto_link()
    if tool_operation is not None:
        tool_operation.success = True
        tool_operation.success_message = "Relationship Copied"
    else:
        wutil.make_inViewMessage("Relationship Copied")
    return True


def _apply_relationship(data, *, keyframe=False, frame=None, warn=True):
    driver, followers = _existing_relationship(data, warn=warn)
    if not driver or not followers:
        return 0

    driver_matrix = _matrix(cmds.xform(driver, query=True, matrix=True, worldSpace=True))
    applied = 0
    for follower in followers:
        try:
            offset_matrix = _matrix(data["relative_matrices"][follower])
            cmds.xform(
                follower,
                matrix=_matrix_values(offset_matrix * driver_matrix),
                worldSpace=True,
            )
            if keyframe:
                cmds.setKeyframe(
                    follower,
                    attribute=("translate", "rotate", "scale"),
                    time=(frame if frame is not None else cmds.currentTime(query=True)),
                )
            applied += 1
        except (RuntimeError, TypeError, ValueError) as error:
            import TheKeyMachine.mods.reportMod as report

            report.report_detected_exception(error, context="apply relationship to {}".format(follower))
    return applied


def _begin_paste_tint(timerange, tool_id, tool_operation=None, anchor_widget=None):
    tint_session = timelineWidgets.begin_timeline_tint(
        timerange=timerange,
        color=toolbox.get_tool_tint_color(tool_id),
        owner=anchor_widget,
        key=tool_id,
    )
    if tool_operation is not None:
        tool_operation.timerange = timerange
        tool_operation.tint_session = tint_session
        return None
    return tint_session


def _relationship_key_times(data, timerange):
    driver, followers = _existing_relationship(data)
    if not driver or not followers:
        return []
    try:
        key_times = cmds.keyframe(
            [driver] + followers,
            query=True,
            time=timerange,
            timeChange=True,
        ) or []
    except (RuntimeError, TypeError, ValueError):
        return []
    return sorted({float(frame) for frame in key_times})


def _paste_relationship_over_range(
    data,
    timerange,
    *,
    tool_operation=None,
    anchor_widget=None,
    tool_id="link_paste_range",
):
    global _callback_suspended

    timerange = (float(timerange[0]), float(timerange[1]))
    local_tint = _begin_paste_tint(
        timerange,
        tool_id,
        tool_operation=tool_operation,
        anchor_widget=anchor_widget,
    )
    frames = _relationship_key_times(data, timerange)
    if not frames:
        if local_tint is not None:
            local_tint.finish()
        wutil.make_inViewMessage("No relationship object keys found in the animation range")
        return False

    if tool_operation is not None:
        tool_operation.set_total(len(frames), reset=True)
        tool_operation.set_status("Pasting Relationship")

    original_time = cmds.currentTime(query=True)
    applied_frames = 0
    _callback_suspended = True
    try:
        with toolCommon.suspend_maya_refresh():
            for frame in frames:
                if tool_operation is not None and tool_operation.cancelled:
                    break
                cmds.currentTime(frame)
                if _apply_relationship(
                    data,
                    keyframe=True,
                    frame=frame,
                    warn=not applied_frames,
                ):
                    applied_frames += 1
                if tool_operation is not None:
                    tool_operation.step()
    finally:
        cmds.currentTime(original_time)
        _callback_suspended = False
        if local_tint is not None:
            local_tint.finish()

    if applied_frames and tool_operation is not None:
        tool_operation.success = True
        tool_operation.success_message = "Relationship Pasted to Range"
    return bool(applied_frames)


def paste_relationship(*_args, tool_operation=None, anchor_widget=None, **_kwargs):
    data = _load_relationship()
    if not data:
        return False

    selected_range = selectionMod.get_selected_time_slider_range()
    if selected_range:
        return _paste_relationship_over_range(
            data,
            selected_range,
            tool_operation=tool_operation,
            anchor_widget=anchor_widget,
            tool_id="link_paste",
        )

    frame = cmds.currentTime(query=True)
    local_tint = _begin_paste_tint(
        (frame, frame),
        "link_paste",
        tool_operation=tool_operation,
        anchor_widget=anchor_widget,
    )
    try:
        applied = _apply_relationship(data, keyframe=True, frame=frame)
    finally:
        if local_tint is not None:
            local_tint.finish()
    if not applied:
        return False
    if tool_operation is not None:
        tool_operation.success = True
        tool_operation.success_message = "Relationship Pasted"
    return True


def paste_relationship_to_range(
    *_args,
    tool_operation=None,
    anchor_widget=None,
    **_kwargs
):
    data = _load_relationship()
    if not data:
        return False
    timerange = (
        selectionMod.get_selected_time_slider_range()
        or timelineWidgets.get_playback_range()
    )
    return _paste_relationship_over_range(
        data,
        timerange,
        tool_operation=tool_operation,
        anchor_widget=anchor_widget,
    )


def _auto_apply(*_args):
    global _callback_suspended

    if _callback_suspended:
        return
    data = _load_relationship(warn=False)
    if not data:
        return
    _callback_suspended = True
    try:
        _apply_relationship(data, keyframe=False, warn=False)
    finally:
        _callback_suspended = False


def _driver_changed(message, _plug, _other_plug, _client_data):
    if message & om.MNodeMessage.kAttributeSet:
        _auto_apply()


def _restore_auto_link(*_args):
    if settings.get_setting(SETTING_KEY, False) and not enable_auto_link():
        settings.set_setting(SETTING_KEY, False)


def enable_auto_link():
    manager = runtime.get_runtime_manager()
    manager.disconnect_callbacks(RUNTIME_KEY)
    data = _load_relationship(warn=False)
    driver, _followers = _existing_relationship(data, warn=False)
    if not driver:
        return False
    attribute_callback = manager.add_node_attribute_changed_callback(
        driver,
        _driver_changed,
        key=RUNTIME_KEY,
    )
    time_callback = manager.connect_signal(
        manager.time_changed,
        _auto_apply,
        key=RUNTIME_KEY,
        unique=False,
    )
    scene_open_callback = manager.connect_signal(
        manager.scene_opened,
        _restore_auto_link,
        key=RUNTIME_KEY,
        unique=False,
    )
    scene_new_callback = manager.connect_signal(
        manager.scene_new,
        _restore_auto_link,
        key=RUNTIME_KEY,
        unique=False,
    )
    if attribute_callback is None or not all((time_callback, scene_open_callback, scene_new_callback)):
        manager.disconnect_callbacks(RUNTIME_KEY)
        return False
    return True


def disable_auto_link():
    runtime.get_runtime_manager(start=False).disconnect_callbacks(RUNTIME_KEY)


def is_auto_link_enabled():
    enabled = bool(settings.get_setting(SETTING_KEY, False))
    if enabled and not enable_auto_link():
        settings.set_setting(SETTING_KEY, False)
        return False
    return enabled


def set_auto_link_enabled(enabled, *args, **kwargs):
    enabled = bool(enabled)
    if enabled and not enable_auto_link():
        settings.set_setting(SETTING_KEY, False)
        wutil.make_inViewMessage("Copy a valid relationship before enabling Auto Link")
        return False
    settings.set_setting(SETTING_KEY, enabled)
    if not enabled:
        disable_auto_link()
    return enabled
