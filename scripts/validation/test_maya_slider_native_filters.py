"""Integration tests for the selectable Maya-native slider filters (#59)."""

import pathlib
import sys
import types
import unittest


ROOT = pathlib.Path(__file__).resolve().parents[2]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

import maya.standalone

maya.standalone.initialize(name="python")

from maya import cmds
from maya.api import OpenMayaAnim as oma

from TheKeyMachine.tools.slider_blend import controller


def _session(curve, times, preview=False):
    return types.SimpleNamespace(
        preview=preview,
        anim_change=oma.MAnimCurveChange() if preview else None,
        cache=types.SimpleNamespace(original_keyframes={}, auxiliary={}),
        targets=types.SimpleNamespace(
            resolved=True,
            curves=[curve],
            affected_map={curve: list(times)},
            time_range=None,
            has_graph_keys=True,
        ),
    )


def _keyed_curve(name, values):
    node = cmds.createNode("transform", name=name)
    plug = "{}.translateX".format(node)
    for time, value in enumerate(values, 1):
        cmds.setKeyframe(plug, time=time, value=value)
    return (cmds.listConnections(plug, source=True, destination=False, type="animCurve") or [None])[0]


class MayaNativeSliderFilterTests(unittest.TestCase):
    def setUp(self):
        cmds.file(new=True, force=True)

    def test_gaussian_smooth_changes_values_without_changing_key_times(self):
        values = [0, 6, -3, 8, -2, 7, 0, 5, -4, 1]
        curve = _keyed_curve("NativeSmoothNode", values)
        times_before = cmds.keyframe(curve, query=True, timeChange=True)
        values_before = cmds.keyframe(curve, query=True, valueChange=True)
        original_getter = controller.get_smooth_algorithm
        controller.get_smooth_algorithm = lambda: controller.ALGORITHM_MAYA_NATIVE
        try:
            controller.apply_smooth(_session(curve, times_before), factor=1.0)
        finally:
            controller.get_smooth_algorithm = original_getter
        self.assertEqual(cmds.keyframe(curve, query=True, timeChange=True), times_before)
        self.assertNotEqual(cmds.keyframe(curve, query=True, valueChange=True), values_before)

    def test_native_simplify_removes_redundant_keys(self):
        values = [float(index) + (0.001 if index % 2 else -0.001) for index in range(12)]
        curve = _keyed_curve("NativeSimplifyNode", values)
        times = cmds.keyframe(curve, query=True, timeChange=True)
        original_getter = controller.get_simplify_algorithm
        controller.get_simplify_algorithm = lambda: controller.ALGORITHM_MAYA_NATIVE
        try:
            controller.apply_simplify(_session(curve, times), None, 1.0)
        finally:
            controller.get_simplify_algorithm = original_getter
        remaining = cmds.keyframe(curve, query=True, timeChange=True)
        self.assertLess(len(remaining), len(times))
        self.assertEqual(remaining[0], times[0])
        self.assertEqual(remaining[-1], times[-1])

    def test_native_preview_is_fully_reversible(self):
        values = [0, 6, -3, 8, -2, 7, 0, 5]
        curve = _keyed_curve("NativePreviewNode", values)
        times = cmds.keyframe(curve, query=True, timeChange=True)
        values_before = cmds.keyframe(curve, query=True, valueChange=True)
        session = _session(curve, times, preview=True)
        original_getter = controller.get_smooth_algorithm
        controller.get_smooth_algorithm = lambda: controller.ALGORITHM_MAYA_NATIVE
        try:
            controller.apply_smooth(session, factor=1.0)
        finally:
            controller.get_smooth_algorithm = original_getter
        self.assertNotEqual(cmds.keyframe(curve, query=True, valueChange=True), values_before)
        session.anim_change.undoIt()
        self.assertEqual(cmds.keyframe(curve, query=True, valueChange=True), values_before)

    def test_repeated_gaussian_preview_uses_drag_start_values(self):
        values = [0, 6, -3, 8, -2, 7, 0, 5]
        curve = _keyed_curve("RepeatedPreviewNode", values)
        reference = _keyed_curve("SinglePreviewNode", values)
        times = cmds.keyframe(curve, query=True, timeChange=True)
        session = _session(curve, times, preview=True)
        reference_session = _session(reference, times, preview=True)
        original_getter = controller.get_smooth_algorithm
        controller.get_smooth_algorithm = lambda: controller.ALGORITHM_MAYA_NATIVE
        try:
            controller.apply_smooth(session, factor=0.3)
            controller.apply_smooth(session, factor=0.8)
            controller.apply_smooth(reference_session, factor=0.8)
        finally:
            controller.get_smooth_algorithm = original_getter
        repeated_values = cmds.keyframe(curve, query=True, valueChange=True)
        reference_values = cmds.keyframe(reference, query=True, valueChange=True)
        self.assertEqual(repeated_values, reference_values)


if __name__ == "__main__":
    try:
        unittest.main(exit=False)
    finally:
        maya.standalone.uninitialize()
