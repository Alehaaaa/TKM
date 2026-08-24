from maya import cmds, mel

from TheKeyMachine.maya import animation
from TheKeyMachine.maya import selection as maya_selection
from TheKeyMachine.tools import common as toolCommon
from TheKeyMachine.ui.widgets import util as wutil


def match_keys(*_args, tool_operation=None, **_kwargs):
    target_info = animation.resolve_context(
        include_channels=True, include_shapes=True, resolve_curves=True
    )
    curves = target_info.curves
    if len(curves) < 2:
        return wutil.make_inViewMessage("Select at least two animation curves")
    source_values = target_info.key_data(curves[-1])
    if not source_values:
        return wutil.make_inViewMessage("No source keys found")
    source_times = {time for time, _value in source_values}
    operation = toolCommon.require_tool_operation(tool_operation)
    operation.set_total(len(curves) - 1)
    for curve in curves[:-1]:
        if operation.cancelled:
            return
        extra_frames = set(target_info.key_times(curve)) - source_times
        if extra_frames:
            cmds.cutKey(
                curve,
                time=[(frame, frame) for frame in sorted(extra_frames)],
                clear=True,
            )
        for time, value in source_values:
            cmds.setKeyframe(curve, time=(time,), value=value)
        operation.step()


def flip_curves(*_args, tool_operation=None, **_kwargs):
    target_info = animation.resolve_context(
        include_channels=True, include_shapes=True, resolve_curves=True
    )
    curves = target_info.curves
    if not curves:
        return wutil.make_inViewMessage("Select at least one animation curve")
    flipped = False
    toolCommon.require_tool_operation(tool_operation)
    for curve in curves:
        key_data = target_info.key_data(curve)
        if not key_data:
            continue
        values = [value for _time, value in key_data]
        pivot = (min(values) + max(values)) / 2.0
        time_context = target_info.time
        if time_context and time_context.mode == "graph_editor_keys":
            for key_time, value in key_data:
                cmds.keyframe(curve, edit=True, time=(key_time, key_time), valueChange=pivot * 2.0 - value)
        else:
            kwargs = animation.selection_time_kwargs(time_context)
            cmds.scaleKey(curve, valueScale=-1, valuePivot=pivot, **kwargs)
        flipped = True
    if not flipped:
        return animation.notify_empty("keys")


def overlap_curves(direction, *_args, tool_operation=None, **_kwargs):
    target_info = animation.resolve_context(
        include_channels=True, include_shapes=True, resolve_curves=True
    )
    curves = target_info.curves
    if not curves:
        return wutil.make_inViewMessage("Select animation curves, channels, or animated objects")
    direction = 1 if direction >= 0 else -1
    kwargs = animation.selection_time_kwargs(target_info.time)
    toolCommon.require_tool_operation(tool_operation)
    for index, curve in enumerate(curves):
        cmds.keyframe(curve, edit=True, includeUpperBound=True, relative=True,
                      option="over", timeChange=index * direction, **kwargs)


def isolate_curves(*_args, tool_operation=None, **_kwargs):
    target_info = animation.resolve_context(
        include_channels=False, include_shapes=True, resolve_curves=True
    )
    snapshot = target_info.selection_snapshot
    if not snapshot or not snapshot.graph_outliner_items:
        return wutil.make_inViewMessage("Select curves in the Graph Editor")
    toolCommon.require_tool_operation(tool_operation)
    mel.eval("isolateAnimCurve true {} {};".format(
        maya_selection.GRAPH_EDITOR_OUTLINER, maya_selection.GRAPH_EDITOR
    ))


def toggle_mute(*_args, tool_operation=None, **_kwargs):
    curves = animation.resolve_context(
        include_channels=False, include_shapes=True, resolve_curves=True
    ).curves
    if not curves:
        return wutil.make_inViewMessage("Select curves in the Graph Editor")
    toolCommon.require_tool_operation(tool_operation)
    for curve in curves:
        if cmds.mute(curve, query=True):
            cmds.mute(curve, disable=True)
        else:
            cmds.mute(curve)


def toggle_lock(*_args, tool_operation=None, **_kwargs):
    curves = animation.resolve_context(
        include_channels=False, include_shapes=True, resolve_curves=True
    ).curves
    if not curves:
        return wutil.make_inViewMessage("Select curves in the Graph Editor")
    toolCommon.require_tool_operation(tool_operation)
    for curve in curves:
        plug = curve + ".ktv"
        cmds.setAttr(plug, lock=not cmds.getAttr(plug, lock=True))


def select_objects_from_selected_curves(*_args, tool_operation=None, **_kwargs):
    curves = animation.resolve_context(
        include_channels=False, include_shapes=True, resolve_curves=True
    ).curves
    if not curves:
        return wutil.make_inViewMessage("Select curves in the Graph Editor")
    toolCommon.require_tool_operation(tool_operation)
    objects = set(maya_selection.object_names_from_plugs(
        maya_selection.get_anim_curve_output_plugs(curves)
    ))
    if objects:
        cmds.select(list(objects), replace=True)
    return list(objects)


_FILTER_ON = """
global proc syncChannelBoxFcurveEd() {
    string $objs[] = `ls -sl`;
    filterUIClearFilter graphEditor1OutlineEd;
    for ($obj in $objs) selectionConnection -e -select $obj graphEditor1FromOutliner;
}
syncChannelBoxFcurveEd();
"""
_FILTER_OFF = """
global proc syncChannelBoxFcurveEd() {}
syncChannelBoxFcurveEd();
filterUIClearFilter graphEditor1OutlineEd;
"""


def set_filter_enabled(enabled, *_args, tool_operation=None, **_kwargs):
    toolCommon.require_tool_operation(tool_operation)
    mel.eval(_FILTER_ON if enabled else _FILTER_OFF)
    maya_selection.refresh_graph_editor()
    return bool(enabled)
