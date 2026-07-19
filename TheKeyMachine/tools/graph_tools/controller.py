from maya import cmds, mel

from TheKeyMachine.core import animation_context
import TheKeyMachine.mods.selectionMod as selectionMod
from TheKeyMachine.tools import common as toolCommon
from TheKeyMachine.widgets import util as wutil


def _operation(tool_id, label):
    return toolCommon.tool_operation(tool_id=tool_id, label=label, undo=True, progress=False)


def match_keys(*_args):
    target_info, curves = animation_context.resolve_curve_context()
    if len(curves) < 2:
        return wutil.make_inViewMessage("Select at least two animation curves")
    source_values = animation_context.key_data(curves[-1], target_info)
    if not source_values:
        return wutil.make_inViewMessage("No source keys found")
    source_times = {time for time, _value in source_values}
    with _operation("graph_match_keys", "Match Curves"):
        for curve in curves[:-1]:
            for frame in set(animation_context.key_times(curve, target_info)) - source_times:
                cmds.cutKey(curve, time=(frame, frame), clear=True)
            for time, value in source_values:
                cmds.setKeyframe(curve, time=(time,), value=value)


def flip_curves(*_args):
    target_info, curves = animation_context.resolve_curve_context()
    if not curves:
        return wutil.make_inViewMessage("Select at least one animation curve")
    flipped = False
    with _operation("graph_flip", "Flip Curves"):
        for curve in curves:
            key_data = animation_context.key_data(curve, target_info)
            if not key_data:
                continue
            values = [value for _time, value in key_data]
            pivot = (min(values) + max(values)) / 2.0
            time_context = target_info.get("time_context")
            if time_context and time_context.mode == "graph_editor_keys":
                for key_time, value in key_data:
                    cmds.keyframe(curve, edit=True, time=(key_time, key_time), valueChange=pivot * 2.0 - value)
            else:
                kwargs = animation_context.selection_time_kwargs(time_context)
                cmds.scaleKey(curve, valueScale=-1, valuePivot=pivot, **kwargs)
            flipped = True
    if not flipped:
        return wutil.make_inViewMessage("No keys found")


def overlap_curves(direction, *_args):
    target_info, curves = animation_context.resolve_curve_context()
    if not curves:
        return wutil.make_inViewMessage("Select animation curves, channels, or animated objects")
    direction = 1 if direction >= 0 else -1
    tool_id = "graph_overlap_forward" if direction > 0 else "graph_overlap_backward"
    label = "Overlap Forward" if direction > 0 else "Overlap Backward"
    kwargs = animation_context.selection_time_kwargs(target_info.get("time_context"))
    with _operation(tool_id, label):
        for index, curve in enumerate(curves):
            cmds.keyframe(curve, edit=True, includeUpperBound=True, relative=True,
                          option="over", timeChange=index * direction, **kwargs)


def isolate_curves(*_args):
    if not selectionMod.get_graph_editor_outliner_items():
        return wutil.make_inViewMessage("Select curves in the Graph Editor")
    mel.eval("isolateAnimCurve true {} {};".format(
        selectionMod.GRAPH_EDITOR_OUTLINER, selectionMod.GRAPH_EDITOR
    ))


def toggle_mute(*_args):
    curves = selectionMod.get_graph_editor_outliner_items()
    if not curves:
        return wutil.make_inViewMessage("Select curves in the Graph Editor")
    with _operation("graph_toggle_mute", "Mute Curves"):
        for curve in curves:
            if cmds.mute(curve, query=True):
                cmds.mute(curve, disable=True)
            else:
                cmds.mute(curve)


def toggle_lock(*_args):
    items = selectionMod.get_graph_editor_outliner_items()
    if not items:
        return wutil.make_inViewMessage("Select curves in the Graph Editor")
    with _operation("graph_toggle_lock", "Lock Curves"):
        for item in items:
            curves = [item] if selectionMod.is_anim_curve(item) else selectionMod.get_anim_curves_for_nodes([item], include_shapes=True)
            for curve in curves or ():
                plug = curve + ".ktv"
                cmds.setAttr(plug, lock=not cmds.getAttr(plug, lock=True))


def select_objects_from_selected_curves(*_args):
    curves = cmds.keyframe(query=True, name=True, selected=True) or []
    if not curves:
        return wutil.make_inViewMessage("Select keys in the Graph Editor")
    selection = selectionMod.get_selected_objects()
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
    return bool(enabled)
