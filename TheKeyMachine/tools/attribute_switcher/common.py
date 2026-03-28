import math

from maya import cmds
from maya import OpenMaya as om

import TheKeyMachine.mods.mediaMod as media
from TheKeyMachine.tools import colors as toolColors


ATTRIBUTE_SWITCHER_SETTINGS_NAMESPACE = "attribute_switcher_window"
ATTRIBUTE_SWITCHER_GEOMETRY_KEY = "attribute_switcher_geometry"
ATTRIBUTE_SWITCHER_STAYS_ON_TOP_KEY = "attribute_switcher_stays_on_top"


UI_COLOR = toolColors.UI_COLORS
ACCENT_DARK_COLOR = toolColors.get_selection_set_color("_12")
ACCENT_MAIN_COLOR = toolColors.get_selection_set_color("_11")
ACCENT_LIGHT_COLOR = toolColors.get_selection_set_color("_10")

COLOR_BG_MAIN = UI_COLOR.dark_gray.hex
COLOR_BG_POPUP = UI_COLOR.gray.hex
COLOR_BG_TRACK = UI_COLOR.darker_gray.hex
COLOR_ACCENT_DARK = ACCENT_DARK_COLOR.base.hex
COLOR_ACCENT_MAIN = ACCENT_MAIN_COLOR.base.hex
COLOR_ACCENT_LIGHT = ACCENT_LIGHT_COLOR.base.hex
COLOR_ACCENT_HOVER = ACCENT_MAIN_COLOR.hover.hex
COLOR_ACCENT_WHITE = ACCENT_LIGHT_COLOR.hover.hex
COLOR_TEXT_MAIN = UI_COLOR.darker_gray.hex
COLOR_TEXT_SECONDARY = UI_COLOR.dark_white.hex
COLOR_BLEND_MULTI = ACCENT_DARK_COLOR.hover.hex

ATTRIBUTE_SWITCHER_GLOBE_IMAGE = media.globe_image


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

    def convert_order_string(self, s):
        return self.rotation_orders.get(s, om.MEulerRotation.kZYX)

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

    def _rotation_at_time(self, obj, t, order_list):
        rx = cmds.getAttr("%s.rotateX" % obj, time=t)
        ry = cmds.getAttr("%s.rotateY" % obj, time=t)
        rz = cmds.getAttr("%s.rotateZ" % obj, time=t)
        idx = int(cmds.getAttr("%s.rotateOrder" % obj, time=t))
        idx = max(0, min(idx, len(order_list) - 1)) if order_list else 0
        current_order_str = order_list[idx] if order_list else "xyz"

        return om.MEulerRotation(
            math.radians(rx or 0.0),
            math.radians(ry or 0.0),
            math.radians(rz or 0.0),
            self.convert_order_string(current_order_str),
        )

    def compute_all_percentages(self, obj, order_list):
        key_times = set()
        for attr in ("rotateX", "rotateY", "rotateZ"):
            key_times_for_attr = cmds.keyframe(obj, attribute=attr, query=True, timeChange=True)
            if key_times_for_attr:
                key_times.update(key_times_for_attr)
        if not key_times:
            key_times = {cmds.currentTime(query=True)}

        percentages = []
        for target_order_str in order_list:
            target_order = self.convert_order_string(target_order_str)
            worst = 0
            for frame in sorted(key_times):
                rot_t = self._rotation_at_time(obj, frame, order_list)
                reordered = om.MEulerRotation(rot_t.x, rot_t.y, rot_t.z, rot_t.order)
                reordered.reorderIt(target_order)
                worst = max(worst, self.compute_gimbal_percentage(reordered))
            percentages.append(worst)
        return percentages

    def classify_percentages(self, percentages):
        labels = [""] * len(percentages)
        if not percentages or len(set(percentages)) == 1:
            return labels

        best = min(percentages)
        for i, val in enumerate(percentages):
            diff = val - best
            if diff == 0:
                labels[i] = "Best"
            elif diff <= 2:
                labels[i] = "Good"
            elif diff <= 6:
                labels[i] = "OK"
        return labels

    def analyze(self, obj):
        order_list = self.get_rotation_order_list(obj)
        if not order_list:
            return {}

        percentages = self.compute_all_percentages(obj, order_list)
        labels = self.classify_percentages(percentages)

        return {
            order: {"percentage": percentages[i], "label": labels[i]}
            for i, order in enumerate(order_list)
        }
