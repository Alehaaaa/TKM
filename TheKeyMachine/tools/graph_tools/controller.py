from maya import cmds, mel

from TheKeyMachine.maya import animation
from TheKeyMachine.maya import selection as maya_selection
from TheKeyMachine.tools import common as toolCommon
from TheKeyMachine.ui.widgets import util as wutil


def _operation(tool_id, label):
    return toolCommon.tool_operation(tool_id=tool_id, label=label, undo=True, progress=False)


def match_keys(*_args):
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
    with _operation("graph_match_keys", "Match Curves") as operation:
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


def flip_curves(*_args):
    target_info = animation.resolve_context(
        include_channels=True, include_shapes=True, resolve_curves=True
    )
    curves = target_info.curves
    if not curves:
        return wutil.make_inViewMessage("Select at least one animation curve")
    flipped = False
    with _operation("graph_flip", "Flip Curves"):
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


def overlap_curves(direction, *_args):
    target_info = animation.resolve_context(
        include_channels=True, include_shapes=True, resolve_curves=True
    )
    curves = target_info.curves
    if not curves:
        return wutil.make_inViewMessage("Select animation curves, channels, or animated objects")
    direction = 1 if direction >= 0 else -1
    tool_id = "graph_overlap_forward" if direction > 0 else "graph_overlap_backward"
    label = "Overlap Forward" if direction > 0 else "Overlap Backward"
    kwargs = animation.selection_time_kwargs(target_info.time)
    with _operation(tool_id, label):
        for index, curve in enumerate(curves):
            cmds.keyframe(curve, edit=True, includeUpperBound=True, relative=True,
                          option="over", timeChange=index * direction, **kwargs)


def isolate_curves(*_args):
    if not maya_selection.get_graph_editor_outliner_items():
        return wutil.make_inViewMessage("Select curves in the Graph Editor")
    mel.eval("isolateAnimCurve true {} {};".format(
        maya_selection.GRAPH_EDITOR_OUTLINER, maya_selection.GRAPH_EDITOR
    ))


def toggle_mute(*_args):
    curves = maya_selection.get_graph_editor_outliner_items()
    if not curves:
        return wutil.make_inViewMessage("Select curves in the Graph Editor")
    with _operation("graph_toggle_mute", "Mute Curves"):
        for curve in curves:
            if cmds.mute(curve, query=True):
                cmds.mute(curve, disable=True)
            else:
                cmds.mute(curve)


def toggle_lock(*_args):
    items = maya_selection.get_graph_editor_outliner_items()
    if not items:
        return wutil.make_inViewMessage("Select curves in the Graph Editor")
    with _operation("graph_toggle_lock", "Lock Curves"):
        for item in items:
            curves = (
                [item]
                if maya_selection.is_anim_curve(item)
                else maya_selection.get_anim_curves_for_nodes(
                    [item], include_shapes=True
                )
            )
            for curve in curves or ():
                plug = curve + ".ktv"
                cmds.setAttr(plug, lock=not cmds.getAttr(plug, lock=True))


def select_objects_from_selected_curves(*_args):
    curves = cmds.keyframe(query=True, name=True, selected=True) or []
    if not curves:
        return wutil.make_inViewMessage("Select keys in the Graph Editor")
    selection = maya_selection.get_selected_objects()
    namespace = selection[0].split(":", 1)[0] if selection and ":" in selection[0] else None
    objects = set()
    for curve in curves:
        name = "_".join(curve.split("_")[:-1])
        namespaced = "{}:{}".format(namespace, name) if namespace else name
        if cmds.objExists(namespaced):
            objects.add(namespaced)
        elif cmds.objExists(name):
            objects.add(name)
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


def set_filter_enabled(enabled):
    mel.eval(_FILTER_ON if enabled else _FILTER_OFF)
    maya_selection.refresh_graph_editor()
    return bool(enabled)
