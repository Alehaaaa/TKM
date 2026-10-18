"""Run the #58 regression against a real Maya installation via mayapy."""

import pathlib
import sys
import unittest


ROOT = pathlib.Path(__file__).resolve().parents[2]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

import maya.standalone

maya.standalone.initialize(name="python")

from maya import cmds

from TheKeyMachine.maya import animation
from TheKeyMachine.tools.nudge import controller as nudge


class _ImmediateOperation(object):
    """Minimal synchronous ToolOperation for headless mayapy integration."""

    cancelled = False

    def run_on_main(self, callback, *args, **kwargs):
        return callback(*args, **kwargs)

    def run_worker(self, callback, *args, **kwargs):
        kwargs.pop("work_items", None)
        return callback(*args, **kwargs)

    def set_total(self, *_args, **_kwargs):
        return self

    def set_status(self, *_args, **_kwargs):
        return self

    def step(self, *_args, **_kwargs):
        return self

    def process(self, items, callback, batch_size=100, **_kwargs):
        items = list(items or [])
        return [callback(items[index:index + batch_size]) for index in range(0, len(items), batch_size)]


class MayaLockedWeightCurveTests(unittest.TestCase):
    def setUp(self):
        cmds.file(new=True, force=True)
        self.node = cmds.createNode("transform", name="NudgeIssue58Node")
        cmds.select(self.node, replace=True)
        self.layer = cmds.animLayer("NudgeIssue58Layer")
        cmds.animLayer(self.layer, edit=True, addSelectedObjects=True)
        cmds.setKeyframe(
            "{}.translateX".format(self.node),
            time=1,
            value=0,
            animLayer=self.layer,
        )
        cmds.setKeyframe(
            "{}.translateX".format(self.node),
            time=3,
            value=1,
            animLayer=self.layer,
        )
        cmds.setKeyframe("{}.weight".format(self.layer), time=1, value=0)
        cmds.setKeyframe("{}.weight".format(self.layer), time=3, value=1)

    def test_locked_weight_curve_is_skipped_while_layer_keys_still_move(self):
        weight_curve = animation.weight_curves(self.layer)[0]
        layer_curve = cmds.animLayer(
            self.layer,
            query=True,
            findCurveForPlug="{}.translateX".format(self.node),
        )
        if isinstance(layer_curve, (list, tuple)):
            layer_curve = layer_curve[0]

        cmds.setAttr("{}.weight".format(self.layer), lock=True)
        layer_context = animation.layer_cache.tool_context()
        edit_filter = nudge._CurveEditFilter(
            layer_context,
            plugs=["{}.translateX".format(self.node)],
        )

        editable = nudge._editable_curves(
            [layer_curve, weight_curve],
            edit_filter=edit_filter,
        )
        self.assertIn(layer_curve, editable)
        self.assertNotIn(weight_curve, editable)

        weight_times_before = cmds.keyframe(weight_curve, query=True, timeChange=True)
        cmds.selectKey(layer_curve, replace=True, time=(1, 3))
        cmds.selectKey(weight_curve, add=True, time=(1, 3))
        original_snap_setting = nudge.is_snap_collision_enabled
        nudge.is_snap_collision_enabled = lambda: False
        try:
            nudge.nudge_range(1, tool_operation=_ImmediateOperation())
        finally:
            nudge.is_snap_collision_enabled = original_snap_setting
        self.assertEqual(
            cmds.keyframe(layer_curve, query=True, timeChange=True),
            [2.0, 3.0],
        )
        self.assertEqual(
            cmds.keyframe(weight_curve, query=True, timeChange=True),
            weight_times_before,
        )


if __name__ == "__main__":
    try:
        unittest.main(exit=False)
    finally:
        maya.standalone.uninitialize()
