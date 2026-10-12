"""Behavior and command-count regressions for shared and tool-specific paths."""

from types import MethodType, SimpleNamespace
import unittest
from unittest.mock import Mock

from test_toolbar_lifecycle import definitions


class WorkerTests(unittest.TestCase):
    def setUp(self):
        self.thread = Mock(side_effect=lambda fn, *args, **kwargs: fn(*args, **kwargs))
        self.ns = definitions("TheKeyMachine/tools/common.py", {"run_worker"}, {
            "WORKER_MIN_WORK_ITEMS": 8, "_run_worker_thread": self.thread,
        }, class_name="ToolOperation")
        self.owner = SimpleNamespace(_worker_wait_depth=0)

    def test_small_coordinator_errors_are_never_retried(self):
        for error in (TypeError("edit failed"), ValueError("edit failed")):
            callback = Mock(side_effect=error)
            with self.assertRaises(type(error)):
                self.ns["run_worker"](self.owner, callback, work_items=1)
            callback.assert_called_once_with()
        self.thread.assert_not_called()

    def test_unknown_io_uses_worker_and_restores_depth_after_failure(self):
        callback = Mock(side_effect=RuntimeError("network failed"))
        with self.assertRaises(RuntimeError):
            self.ns["run_worker"](self.owner, callback)
        self.thread.assert_called_once_with(callback)
        self.assertEqual(self.owner._worker_wait_depth, 0)


class BatchHarness:
    def __init__(self):
        self.cancelled = False
        self.worker_starts = 0
        self.crossings = 0
        self.in_main = True
        self.steps = []

    def set_total(self, total, **kwargs): self.total = total
    def set_status(self, status): self.status = status
    def step(self, amount):
        assert self.in_main
        self.steps.append(amount)

    def run_on_main(self, fn, *args):
        previous = self.in_main
        self.crossings += not previous
        self.in_main = True
        try: return fn(*args)
        finally: self.in_main = previous

    def run_worker(self, fn, **kwargs):
        self.worker_starts += 1
        self.in_main = False
        try: return fn()
        finally: self.in_main = True


class BatchTests(unittest.TestCase):
    def setUp(self):
        self.process = definitions("TheKeyMachine/tools/common.py", {"process"},
                                   class_name="ToolOperation")["process"]

    def test_single_batch_avoids_thread_and_preserves_progress(self):
        owner = BatchHarness()
        result = self.process(owner, range(64), sum, batch_size=100, strategy="worker")
        self.assertEqual(result, [sum(range(64))])
        self.assertEqual(owner.worker_starts, 0)
        self.assertEqual(owner.steps, [64])

    def test_multiple_batches_edit_and_progress_in_one_crossing(self):
        owner = BatchHarness()
        result = self.process(owner, range(250), sum, batch_size=100, strategy="worker")
        self.assertEqual(sum(result), sum(range(250)))
        self.assertEqual(owner.worker_starts, 1)
        self.assertEqual(owner.crossings, 3)
        self.assertEqual(owner.steps, [100, 100, 50])

    def test_cancellation_stops_before_next_batch(self):
        owner = BatchHarness()
        def edit(batch):
            owner.cancelled = True
            return tuple(batch)
        result = self.process(owner, range(20), edit, batch_size=5, strategy="worker")
        self.assertEqual(result, [tuple(range(5))])
        self.assertEqual(owner.steps, [5])

    def test_failed_batch_does_not_advance_progress(self):
        owner = BatchHarness()
        edit = Mock(side_effect=ValueError("invalid edit"))
        with self.assertRaises(ValueError):
            self.process(owner, range(20), edit, batch_size=5, strategy="worker")
        self.assertEqual(owner.steps, [])
        self.assertEqual(edit.call_count, 1)


class DefaultValuesTests(unittest.TestCase):
    def test_sparse_keys_share_lookup_and_edit_without_touching_gaps(self):
        values = {frame: float(frame) for frame in range(100)}
        def edit(curve, **kwargs):
            for start, end in kwargs["time"]:
                self.assertEqual(start, end)
                values[start] = kwargs["valueChange"]
        cmds = SimpleNamespace(listConnections=Mock(return_value=["control.translateX"]),
                               keyframe=Mock(side_effect=edit))
        default = Mock(return_value=0.0)
        ns = definitions("TheKeyMachine/tools/default_values/controller.py", {
            "_apply_selected_key_defaults", "_matches",
        }, {"cmds": cmds, "_stored_default": default,
            "TRANSLATION_ATTRS": {"translateX"}, "ROTATION_ATTRS": {"rotateX"},
            "SCALE_ATTRS": {"scaleX"}})
        operation = Mock(cancelled=False)
        frames = list(range(0, 100, 2))
        ns["_apply_selected_key_defaults"]([( "curve", frame) for frame in frames],
                                           operation, True, False, False)
        self.assertEqual(cmds.listConnections.call_count, 1)
        self.assertEqual(cmds.keyframe.call_count, 1)
        default.assert_called_once_with("control", "translateX")
        self.assertEqual(values, {frame: 0.0 if frame % 2 == 0 else float(frame)
                                  for frame in range(100)})
        operation.step.assert_called_once_with(50)

    def test_cancelled_defaults_do_not_query_or_edit(self):
        cmds = Mock()
        ns = definitions("TheKeyMachine/tools/default_values/controller.py", {
            "_apply_selected_key_defaults",
        }, {"cmds": cmds})
        ns["_apply_selected_key_defaults"]([("curve", 1)], Mock(cancelled=True), False, False, False)
        self.assertEqual(cmds.mock_calls, [])


class GimbalTests(unittest.TestCase):
    def test_rotation_samples_are_shared_between_candidate_orders(self):
        class Rotation:
            def __init__(self, x, y, z, order):
                self.x, self.y, self.z, self.order = x, y, z, order
            def reorderIt(self, order): self.x += order
        ns = definitions("TheKeyMachine/tools/gimbal_fixer/controller.py", {
            "compute_all_percentages",
        }, {"cmds": SimpleNamespace(keyframe=Mock(return_value=[1, 2, 3])),
            "om": SimpleNamespace(MEulerRotation=Rotation)}, class_name="GimbalAnalyzer")
        owner = SimpleNamespace(
            _rotation_at_time=Mock(side_effect=lambda obj, frame, orders: Rotation(frame, 0, 0, 0)),
            convert_order_string=lambda order: order,
            compute_gimbal_percentage=lambda rotation: rotation.x,
        )
        self.assertEqual(ns["compute_all_percentages"](owner, "control", list(range(6))),
                         [3, 4, 5, 6, 7, 8])
        self.assertEqual(owner._rotation_at_time.call_count, 3)


class AlignTests(unittest.TestCase):
    def test_layered_key_collection_batches_only_editable_curves(self):
        context = SimpleNamespace(destination_for_plug=lambda plug: {
            "blocked": plug == "b.rx", "layer": "layer",
        })
        animation = SimpleNamespace(has_anim_layers=Mock(return_value=True),
            layer_graph=SimpleNamespace(curve_for_plug=lambda plug, **kwargs: plug + "Curve"))
        cmds = SimpleNamespace(keyframe=Mock(return_value=[1, 4, 1, 2]))
        ns = definitions("TheKeyMachine/tools/align/api.py", {"_collect_keyframes"},
                         {"animation": animation, "cmds": cmds})
        self.assertEqual(ns["_collect_keyframes"](["a", "b"], ["tx", "rx"], context), [1, 2, 4])
        cmds.keyframe.assert_called_once_with(["a.txCurve", "a.rxCurve", "b.txCurve"],
                                            query=True, timeChange=True)
        animation.has_anim_layers.assert_called_once_with()

    def test_empty_targets_do_not_query_current_maya_selection(self):
        animation = SimpleNamespace(has_anim_layers=Mock(return_value=False))
        cmds = Mock()
        ns = definitions("TheKeyMachine/tools/align/api.py", {"_collect_keyframes"},
                         {"animation": animation, "cmds": cmds})
        self.assertEqual(ns["_collect_keyframes"]([], None, object()), [])
        cmds.keyframe.assert_not_called()


if __name__ == "__main__":
    unittest.main()
