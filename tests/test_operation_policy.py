import unittest

from TheKeyMachine.core import trigger


class OperationPolicyTests(unittest.TestCase):
    def test_regular_tool_is_timed_and_undoable(self):
        policy = trigger._policy_from_definition(
            "example",
            {"type": "tool"},
        )
        self.assertTrue(policy.progress)
        self.assertTrue(policy.undo)
        self.assertTrue(policy.rollback_on_cancel)

    def test_check_action_is_timed_without_an_undo_chunk(self):
        policy = trigger._policy_from_definition(
            "example_check",
            {"type": "check"},
        )
        self.assertTrue(policy.progress)
        self.assertFalse(policy.undo)
        self.assertFalse(policy.rollback_on_cancel)

    def test_non_undoable_explicit_action_does_not_roll_back(self):
        policy = trigger._policy_from_definition(
            "copy_data",
            {"type": "tool", "operation": {"undo": False}},
        )
        self.assertFalse(policy.undo)
        self.assertFalse(policy.rollback_on_cancel)

    def test_explicit_policy_carries_complete_operation_behavior(self):
        policy = trigger._policy_from_definition(
            "example",
            {
                "type": "tool",
                "operation": {
                    "progress": True,
                    "undo": False,
                    "suspend_refresh": True,
                    "preserve_time_selection": True,
                    "rollback_on_cancel": True,
                    "interruptable": False,
                    "show_success_message": False,
                    "capture_animation_context": True,
                    "queue_group": "example_steps",
                    "queue_delta": -1,
                },
            },
        )
        self.assertTrue(policy.progress)
        self.assertFalse(policy.undo)
        self.assertTrue(policy.suspend_refresh)
        self.assertTrue(policy.preserve_time_selection)
        self.assertTrue(policy.rollback_on_cancel)
        self.assertFalse(policy.interruptable)
        self.assertFalse(policy.show_success_message)
        self.assertTrue(policy.capture_animation_context)
        self.assertEqual(policy.queue_group, "example_steps")
        self.assertEqual(policy.queue_delta, -1)


if __name__ == "__main__":
    unittest.main()
