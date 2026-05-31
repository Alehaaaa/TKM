import math

from maya import cmds
from maya import OpenMaya as om


class GimbalAnalyzer:
    def __init__(self):
        self.rotation_orders = {
            "xyz": om.MEulerRotation.kXYZ,
            "yzx": om.MEulerRotation.kYZX,
            "zxy": om.MEulerRotation.kZXY,
            "xzy": om.MEulerRotation.kXZY,
            "yxz": om.MEulerRotation.kYXZ,
            "zyx": om.MEulerRotation.kZYX,
        }

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
        return self.rotation_orders.get(order, om.MEulerRotation.kZYX)

    def _safe_get_depend_node(self, sel_list, index=0):
        try:
            return sel_list.getDependNode(index)
        except TypeError:
            mobj = om.MObject()
            sel_list.getDependNode(index, mobj)
            return mobj

    def get_rotation(self, obj):
        sel = om.MSelectionList()
        sel.add(obj)
        node = self._safe_get_depend_node(sel, 0)
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
