from maya import cmds
from maya import OpenMaya as om

import TheKeyMachine.mods.selectionMod as selectionMod
from TheKeyMachine.tools import common as toolCommon
from TheKeyMachine.tools.gimbal_fixer.constants import ROTATE_ORDERS


class UndoSetup:
    chunk_opened = False

    def __enter__(self):
        self.chunk_opened = toolCommon.open_undo_chunk()

    def __exit__(self, *args):
        if self.chunk_opened:
            toolCommon.close_undo_chunk()


class StopRefresh:
    def __enter__(self):
        cmds.refresh(suspend=True)

    def __exit__(self, *args):
        cmds.refresh(suspend=False)


def has_rotate_order(obj):
    return cmds.objExists(obj) and cmds.attributeQuery("rotateOrder", node=obj, exists=True)


def rotate_gimbal_state(obj):
    rot_data = cmds.duplicate(obj, name="temp#", parentOnly=True)[0]
    tolerances = []
    for rot_order in ROTATE_ORDERS:
        cmds.xform(rot_data, preserve=True, rotateOrder=rot_order)
        tolerances.append(gimbal_tolerance(rot_data))
    cmds.delete(rot_data)
    return tolerances


def gimbal_tolerance(obj):
    rotate_order = ROTATE_ORDERS[cmds.getAttr(obj + ".rotateOrder")]
    mid_value = cmds.getAttr(obj + ".r" + rotate_order[1])
    return abs(((mid_value + 90) % 180) - 90) / 90


def selected_control():
    selection = selectionMod.get_selected_objects()
    return selection[0] if selection else None


def convert_rotation_order(rot_order="zxy"):
    if rot_order not in ROTATE_ORDERS:
        om.MGlobal.displayWarning("Wrong rotation order " + str(rot_order))
        return

    selection = selectionMod.get_selected_objects()
    if not selection:
        om.MGlobal.displayWarning("Please select a control.")
        return

    skipped = [obj for obj in selection if not has_rotate_order(obj)]
    selection = [obj for obj in selection if has_rotate_order(obj)]
    if skipped:
        om.MGlobal.displayWarning("Skipped objects without rotateOrder: " + ", ".join(skipped))
    if not selection:
        om.MGlobal.displayWarning("Please select a control with rotateOrder.")
        return

    current_time = cmds.currentTime(query=True)
    key_times = {}
    previous_orders = {}
    all_key_times = []
    keyed_objects = []
    unkeyed_objects = []

    for obj in selection:
        rotate_keys = cmds.keyframe(obj, attribute="rotate", query=True, timeChange=True)
        if rotate_keys:
            key_times[obj] = list(set(rotate_keys))
            previous_orders[obj] = ROTATE_ORDERS[cmds.getAttr(obj + ".rotateOrder")]
            all_key_times.extend(rotate_keys)
            keyed_objects.append(obj)
        else:
            unkeyed_objects.append(obj)

    with UndoSetup():
        if keyed_objects:
            all_key_times = sorted(set(all_key_times))
            with StopRefresh():
                for frame in all_key_times:
                    cmds.currentTime(frame, edit=True)
                    for obj in keyed_objects:
                        if frame in key_times[obj]:
                            cmds.setKeyframe(obj, attribute="rotate")

                for frame in all_key_times:
                    cmds.currentTime(frame, edit=True)
                    for obj in keyed_objects:
                        if frame in key_times[obj]:
                            cmds.xform(obj, preserve=True, rotateOrder=rot_order)
                            cmds.setKeyframe(obj, attribute="rotate")
                            cmds.xform(obj, preserve=False, rotateOrder=previous_orders[obj])

                cmds.currentTime(current_time, edit=True)

                for obj in keyed_objects:
                    cmds.xform(obj, preserve=False, rotateOrder=rot_order)
                    cmds.filterCurve(obj)

        for obj in unkeyed_objects:
            cmds.xform(obj, preserve=True, rotateOrder=rot_order)
