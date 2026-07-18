from maya import cmds

import TheKeyMachine.mods.selectionMod as selectionMod
from TheKeyMachine.tools import common as toolCommon
import TheKeyMachine.widgets.timeline as timelineWidgets
import TheKeyMachine.widgets.util as wutil


def _collect_keyframes(objects):
    frames = set()
    for obj in objects or []:
        for frame in cmds.keyframe(obj, query=True, timeChange=True) or []:
            frames.add(int(round(frame)))
    return sorted(frames)


def align_selected_objects(*_args, **kwargs):
    pos = kwargs.get("pos", True)
    rot = kwargs.get("rot", True)
    scl = kwargs.get("scl", False)
    key_scope = kwargs.get("key_scope", "selection")
    selection = selectionMod.get_selected_objects()
    if len(selection) < 2:
        return wutil.make_inViewMessage("Select at least two objects")

    source_objects = selection[:-1]
    target_object = selection[-1]
    with toolCommon.suspend_maya_refresh():
        frames = []
        set_keys = False
        if key_scope == "all":
            frames = _collect_keyframes(source_objects)
            if not frames:
                return wutil.make_inViewMessage(
                    "No animation keys available to align objects."
                )
            set_keys = True
        else:
            time_context = timelineWidgets.resolve_time_context(
                default_mode="current_frame"
            )
            if time_context.mode in ("graph_editor_keys", "time_slider_range"):
                frames = list(time_context.frames)
                set_keys = True

        if not frames:
            for source_object in source_objects:
                cmds.matchTransform(
                    source_object, target_object, pos=pos, rot=rot, scl=scl
                )
            return

        with toolCommon.tool_operation(
            tool_id="align_selected_objects",
            label="Aligning Objects",
            progress_max=len(frames),
            undo=True,
        ) as operation:
            for frame in operation.iterate(frames):
                if operation.cancelled:
                    break
                cmds.currentTime(frame)
                for source_object in source_objects:
                    cmds.matchTransform(
                        source_object, target_object, pos=pos, rot=rot, scl=scl
                    )
                    if set_keys:
                        cmds.setKeyframe(source_object)
