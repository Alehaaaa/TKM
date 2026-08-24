import math

from maya import cmds
from maya.api import OpenMaya as om

from TheKeyMachine.maya import animation, maya_api
from TheKeyMachine.tools import common as toolCommon
from TheKeyMachine.tools.global_tools import controller as global_tools
from TheKeyMachine.ui.widgets import util as wutil
WINDOW_NAME = "gimbal_fixer"
ROTATE_ORDERS = ["xyz", "yzx", "zxy", "xzy", "yxz", "zyx"]


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
    selection = list(animation.current_selection_snapshot().objects)
    return selection[0] if selection else None


def convert_rotation_order(rot_order="zxy", tool_operation=None):
    if rot_order not in ROTATE_ORDERS:
        return wutil.make_inViewMessage("Invalid rotation order")

    operation = toolCommon.require_tool_operation(tool_operation)
    target_info = animation.resolve_context(
        default_mode="all_animation", include_channels=True, resolve_curves=True
    )
    selection = target_info.objects
    if not selection:
        return wutil.make_inViewMessage("Select a control")

    skipped = [obj for obj in selection if not has_rotate_order(obj)]
    selection = [obj for obj in selection if has_rotate_order(obj)]
    if skipped:
        wutil.make_inViewMessage("Skipped controls without rotation order")
    if not selection:
        return wutil.make_inViewMessage("Select a control with rotation order")

    current_time = target_info.selection_snapshot.current_time
    key_times = {}
    previous_orders = {}
    all_key_times = []
    keyed_objects = []
    unkeyed_objects = []

    for obj in selection:
        rotate_keys = cmds.keyframe(obj, attribute="rotate", query=True, timeChange=True)
        if rotate_keys:
            if target_info.time.mode == "graph_editor_keys":
                selected_times = {
                    float(frame)
                    for curve, frame in target_info.selected_keys
                    if curve in target_info.curves
                }
                rotate_keys = [frame for frame in rotate_keys if float(frame) in selected_times]
            elif target_info.time.mode == "time_slider_range":
                rotate_keys = [
                    frame for frame in rotate_keys
                    if target_info.time.start_frame <= frame <= target_info.time.end_frame
                ]
        if rotate_keys:
            key_times[obj] = set(rotate_keys)
            previous_orders[obj] = ROTATE_ORDERS[cmds.getAttr(obj + ".rotateOrder")]
            all_key_times.extend(key_times[obj])
            keyed_objects.append(obj)
        else:
            unkeyed_objects.append(obj)

    keyed_work = sum(len(key_times[obj]) for obj in keyed_objects)
    progress_total = keyed_work * 2 + len(keyed_objects) + len(unkeyed_objects)
    operation.set_total(max(1, progress_total)).set_status("Gimbal Fixer")
    try:
        if keyed_objects:
            all_key_times = sorted(set(all_key_times))
            for frame in all_key_times:
                if operation.cancelled:
                    break
                cmds.currentTime(frame, edit=True)
                for obj in keyed_objects:
                    if frame in key_times[obj]:
                        cmds.setKeyframe(obj, attribute="rotate")
                        operation.step()

            for frame in all_key_times:
                if operation.cancelled:
                    break
                cmds.currentTime(frame, edit=True)
                for obj in keyed_objects:
                    if frame in key_times[obj]:
                        cmds.xform(obj, preserve=True, rotateOrder=rot_order)
                        cmds.setKeyframe(obj, attribute="rotate")
                        cmds.xform(obj, preserve=False, rotateOrder=previous_orders[obj])
                        operation.step()

            cmds.currentTime(current_time, edit=True)

            for obj in keyed_objects:
                if operation.cancelled:
                    break
                cmds.xform(obj, preserve=False, rotateOrder=rot_order)
                operation.step()

            if global_tools.is_euler_filter_enabled():
                rotation_curves = []
                for obj in keyed_objects:
                    rotation_curves.extend(
                        animation.layer_graph.curves_for_plugs(
                            [f"{obj}.rx", f"{obj}.ry", f"{obj}.rz"],
                            include_all_layers=True,
                        )
                    )
                operation.set_status("Euler Filtering")
                with animation.preserve_key_selection():
                    animation.apply_smart_euler_filter(
                        rotation_curves, target_info, operation=operation
                    )

        for obj in unkeyed_objects:
            if operation.cancelled:
                break
            cmds.xform(obj, preserve=True, rotateOrder=rot_order)
            operation.step()
    finally:
        cmds.currentTime(current_time, edit=True)

class GimbalAnalyzer:
    def radians_to_degrees(self, radians):
        return radians * (180.0 / math.pi)

    def get_middle_axis_value(self, rotation):
        return {
            om.MEulerRotation.kZXY: rotation.x,
            om.MEulerRotation.kZYX: rotation.y,
            om.MEulerRotation.kXZY: rotation.z,
            om.MEulerRotation.kXYZ: rotation.y,
            om.MEulerRotation.kYZX: rotation.z,
            om.MEulerRotation.kYXZ: rotation.x,
        }[rotation.order]

    def compute_gimbal_percentage(self, rotation):
        mid = self.radians_to_degrees(self.get_middle_axis_value(rotation))
        return int(abs(((mid + 90) % 180) - 90) / 90 * 100)

    def convert_order_string(self, order):
        enum = maya_api.rotate_order_enum(order)
        return enum if enum is not None else om.MEulerRotation.kZYX

    def get_rotation(self, obj):
        node = maya_api.mobject_from_node(obj)
        if node is None:
            return om.MEulerRotation()
        tfm = om.MFnTransform(node)
        return tfm.rotation()

    def get_rotation_order_list(self, obj):
        if cmds.attributeQuery("rotateOrder", node=obj, exists=True):
            return cmds.attributeQuery("rotateOrder", node=obj, listEnum=True)[0].split(":")
        return []

    def _rotation_at_time(self, obj, frame, order_list):
        rx = cmds.getAttr("%s.rotateX" % obj, time=frame)
        ry = cmds.getAttr("%s.rotateY" % obj, time=frame)
        rz = cmds.getAttr("%s.rotateZ" % obj, time=frame)
        idx = int(cmds.getAttr("%s.rotateOrder" % obj, time=frame))
        idx = max(0, min(idx, len(order_list) - 1)) if order_list else 0
        current_order = order_list[idx] if order_list else "xyz"

        return om.MEulerRotation(
            math.radians(rx or 0.0),
            math.radians(ry or 0.0),
            math.radians(rz or 0.0),
            self.convert_order_string(current_order),
        )

    def compute_all_percentages(self, obj, order_list):
        key_times = set()
        for attr in ("rotateX", "rotateY", "rotateZ"):
            attr_key_times = cmds.keyframe(obj, attribute=attr, query=True, timeChange=True)
            if attr_key_times:
                key_times.update(attr_key_times)
        if not key_times:
            key_times = {cmds.currentTime(query=True)}

        percentages = []
        for target_order_name in order_list:
            target_order = self.convert_order_string(target_order_name)
            worst = 0
            for frame in sorted(key_times):
                rotation = self._rotation_at_time(obj, frame, order_list)
                reordered = om.MEulerRotation(rotation.x, rotation.y, rotation.z, rotation.order)
                reordered.reorderIt(target_order)
                worst = max(worst, self.compute_gimbal_percentage(reordered))
            percentages.append(worst)
        return percentages

    def classify_percentages(self, percentages):
        labels = [""] * len(percentages)
        if not percentages or len(set(percentages)) == 1:
            return labels

        best = min(percentages)
        for index, value in enumerate(percentages):
            diff = value - best
            if diff == 0:
                labels[index] = "Best"
            elif diff <= 2:
                labels[index] = "Good"
            elif diff <= 6:
                labels[index] = "OK"
        return labels

    def analyze(self, obj):
        order_list = self.get_rotation_order_list(obj)
        if not order_list:
            return {}

        percentages = self.compute_all_percentages(obj, order_list)
        labels = self.classify_percentages(percentages)

        return {
            order: {"percentage": percentages[index], "label": labels[index]}
            for index, order in enumerate(order_list)
        }
