"""Host-independent lifecycle regressions: python3 -m unittest discover -s scripts/validation.

Extract dependency-heavy entry points so these tests can exercise their control
flow without importing Maya widgets or initializing a user's Maya environment.
"""

import ast
import os
from pathlib import Path
import shutil
import sys
import tempfile
from types import SimpleNamespace
import unittest
from unittest.mock import Mock, patch


ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT))
from TheKeyMachine.core import lifecycle


def definitions(relative_path, names, namespace=None, class_name=None):
    namespace = {} if namespace is None else namespace
    tree = ast.parse((ROOT / relative_path).read_text())
    if class_name:
        tree = next(node for node in tree.body
                    if isinstance(node, ast.ClassDef) and node.name == class_name)
    nodes = [node for node in tree.body
             if isinstance(node, (ast.FunctionDef, ast.ClassDef)) and node.name in names]
    assert len(nodes) == len(names), names
    future = ast.ImportFrom(module="__future__", names=[ast.alias(name="annotations")], level=0)
    module = ast.fix_missing_locations(ast.Module(body=[future] + nodes, type_ignores=[]))
    exec(compile(module, relative_path, "exec"), namespace)
    return namespace


class LifecycleTests(unittest.TestCase):
    def setUp(self):
        self.hooks = lifecycle._hooks.copy()
        lifecycle._hooks.clear()

    def tearDown(self):
        lifecycle._hooks.clear()
        lifecycle._hooks.update(self.hooks)

    def test_operation_preflight_blocks_before_ui_or_workers(self):
        events = []
        operation = SimpleNamespace(accepts_deferred_commands=True,
                                    undo_chunk_opened=False, refresh_suspended=False)
        definitions("TheKeyMachine/tools/common.py", {"check_operation_shutdown"}, {
            "on_shutdown": lifecycle.on_shutdown, "ShutdownPhase": lifecycle.ShutdownPhase,
            "ShutdownBlocked": lifecycle.ShutdownBlocked, "_TOOL_OPERATION_STACK": [operation],
            "__name__": "operation_test",
        })
        @lifecycle.on_shutdown(phase=lifecycle.ShutdownPhase.QUIESCE)
        def readers(): events.append("readers")
        @lifecycle.on_shutdown(phase=lifecycle.ShutdownPhase.UI)
        def ui(): events.append("ui")
        with self.assertRaises(lifecycle.ShutdownBlocked): lifecycle.shutdown()
        self.assertEqual(events, [])
        operation.accepts_deferred_commands = False
        operation.undo_chunk_opened = True
        with self.assertRaises(lifecycle.ShutdownBlocked): lifecycle.shutdown()
        operation.undo_chunk_opened = False
        self.assertEqual(lifecycle.shutdown(), ())
        self.assertEqual(events, ["readers", "ui"])

    def test_unexpected_preflight_failure_also_stops_teardown(self):
        ui = Mock()
        @lifecycle.on_shutdown(phase=lifecycle.ShutdownPhase.PREFLIGHT)
        def broken(): raise ValueError("broken preflight")
        @lifecycle.on_shutdown(phase=lifecycle.ShutdownPhase.UI)
        def teardown(): ui()
        with self.assertLogs(lifecycle._logger, level="ERROR"):
            with self.assertRaises(lifecycle.ShutdownBlocked): lifecycle.shutdown()
        ui.assert_not_called()
        self.assertFalse(lifecycle._running)

    def test_teardown_failures_are_reported_and_other_owners_run(self):
        calls = []
        @lifecycle.on_shutdown(phase=lifecycle.ShutdownPhase.UI)
        def broken(): raise ValueError("broken UI")
        @lifecycle.on_shutdown(phase=lifecycle.ShutdownPhase.TOOLS)
        def tool(): calls.append("tool")
        with self.assertLogs(lifecycle._logger, level="ERROR"):
            failures = lifecycle.shutdown()
        self.assertEqual(len(failures), 1)
        self.assertEqual(calls, ["tool"])


class CallbackStateTests(unittest.TestCase):
    def setUp(self):
        self.app = SimpleNamespace()
        self.cmds = Mock()
        self.cmds.optionVar.return_value = True
        self.removed = []
        self.namespace = {
            "QtWidgets": SimpleNamespace(QApplication=SimpleNamespace(instance=lambda: self.app)),
            "cmds": self.cmds, "_OPTIONVAR_NAME": "TKM_RuntimeManager",
            "_APP_CALLBACK_ATTRIBUTE": "_tkm_callback_state",
            "_remove_om_callback": lambda value: self.removed.append(value),
            "_kill_scriptjob": lambda value: self.removed.append(value),
        }
        self.names = {"_load_state", "_save_state", "_clear_state", "cleanup_orphaned_callbacks"}
        definitions("TheKeyMachine/core/runtime.py", self.names, self.namespace)

    def test_legacy_persisted_ids_are_discarded_without_native_removal(self):
        self.namespace["cleanup_orphaned_callbacks"]()
        self.assertEqual(self.removed, [])
        self.cmds.optionVar.assert_any_call(remove="TKM_RuntimeManager")

    def test_same_process_reload_retains_cleanup_ownership(self):
        self.namespace["_save_state"]({"om": [41], "scriptjob": [42]})
        reloaded = dict(self.namespace)
        definitions("TheKeyMachine/core/runtime.py", self.names, reloaded)
        reloaded["cleanup_orphaned_callbacks"]()
        self.assertEqual(self.removed, [41, 42])
        self.assertFalse(hasattr(self.app, "_tkm_callback_state"))

    def test_new_application_has_no_previous_process_ids(self):
        self.namespace["_save_state"]({"om": [41], "scriptjob": [42]})
        self.app = SimpleNamespace()
        self.namespace["cleanup_orphaned_callbacks"]()
        self.assertEqual(self.removed, [])


class ToolbarEntryTests(unittest.TestCase):
    def test_show_does_not_register_a_python_workspace_close_command(self):
        ns = definitions("TheKeyMachine/ui/widgets/toolbar.py", {"showWindow"},
                         class_name="toolbar")
        owner = SimpleNamespace(
            _is_active=lambda: True, isDockable=Mock(side_effect=[False, True]),
            _parent_to_dock_target=Mock(), docking_position=("TimeSlider", "top"),
            show=Mock(), _bind_dock_events=Mock(), _bind_workspace_visible_change=Mock(),
            _queue_dock_refresh=Mock(), _height_timer=Mock(),
        )
        self.assertTrue(ns["showWindow"](owner))
        self.assertNotIn("closeCallback", owner.show.call_args.kwargs)

    def test_reload_veto_preserves_modules_and_resets_reentrancy_guard(self):
        import TheKeyMachine
        from TheKeyMachine import core
        runtime = SimpleNamespace(_CLEANING_UP=False,
                                  cleanup_for_reload=Mock(side_effect=lifecycle.ShutdownBlocked("busy")))
        with patch.object(core, "runtime", runtime, create=True):
            before = {key: value for key, value in sys.modules.items()
                      if key.startswith("TheKeyMachine.")}
            with self.assertRaises(lifecycle.ShutdownBlocked): TheKeyMachine.reload()
        self.assertFalse(TheKeyMachine._reload_in_progress)
        for name, module in before.items(): self.assertIs(sys.modules[name], module)

    def test_blocked_unload_does_not_retire_toolbar(self):
        owner = SimpleNamespace(_begin_shutdown=Mock())
        cleanup = Mock(side_effect=lifecycle.ShutdownBlocked("busy"))
        ns = definitions("TheKeyMachine/ui/widgets/toolbar.py", {"unload"}, {
            "_toolbar_instance": owner, "runtime": Mock(),
        }, class_name="toolbar")
        method = ns["unload"]
        ns["unload"] = cleanup
        with self.assertRaises(lifecycle.ShutdownBlocked): method(owner)
        owner._begin_shutdown.assert_not_called()
        self.assertIs(ns["_toolbar_instance"], owner)

    def test_dock_close_is_deferred_and_coalesced(self):
        ns = definitions("TheKeyMachine/ui/widgets/toolbar.py", {"dockCloseEventTriggered"},
                         class_name="toolbar")
        owner = SimpleNamespace(_is_active=lambda: True, _close_pending=False,
                                _single_shot=Mock(), _finish_close=Mock())
        ns["dockCloseEventTriggered"](owner)
        ns["dockCloseEventTriggered"](owner)
        owner._single_shot.assert_called_once_with(0, owner._finish_close)

    def test_blocked_dock_close_restores_visibility(self):
        cmds = Mock()
        ns = definitions("TheKeyMachine/ui/widgets/toolbar.py", {"_finish_close"}, {
            "ShutdownBlocked": lifecycle.ShutdownBlocked, "cmds": cmds,
        }, class_name="toolbar")
        owner = SimpleNamespace(_close_pending=True, showWindow=Mock(),
                                unload=Mock(side_effect=lifecycle.ShutdownBlocked("busy")))
        ns["_finish_close"](owner)
        owner.showWindow.assert_called_once()
        self.assertFalse(owner._close_pending)

    def test_startup_is_idempotent_and_skips_batch(self):
        import TheKeyMachine
        toolbar = Mock()
        cmds = SimpleNamespace(about=Mock(return_value=False))
        widgets = SimpleNamespace(toolbar=toolbar)
        with patch.dict(sys.modules, {"maya": SimpleNamespace(cmds=cmds),
                                      "TheKeyMachine.ui.widgets": widgets}):
            TheKeyMachine.startup()
            TheKeyMachine.startup()
            self.assertEqual(toolbar.show.call_count, 2)
            toolbar.toggle.assert_not_called()
            cmds.about.return_value = True
            self.assertIsNone(TheKeyMachine.startup())
            self.assertEqual(toolbar.show.call_count, 2)


class StartupScriptTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.path = Path(self.temp.name) / "userSetup.py"
        self.ns = definitions("TheKeyMachine/core/application.py", {
            "install_userSetup", "refresh_userSetup", "_replace_startup_file",
        }, {"_user_setup_path": lambda: str(self.path), "os": os,
            "shutil": shutil, "tempfile": tempfile})

    def test_legacy_refresh_preserves_external_code_encoding_and_newlines(self):
        before = (b"# coding: latin-1\r\n# caf\xe9\r\nTheKeyMachine.toggle()\r\n"
                  b"# start TheKeyMachine\r\nfrom maya import cmds\r\n"
                  b'cmds.evalDeferred("import TheKeyMachine; TheKeyMachine.toggle()")\r\n'
                  b"# end TheKeyMachine\r\n# outside\r\n")
        self.path.write_bytes(before)
        self.ns["refresh_userSetup"]()
        expected = before.replace(b"import TheKeyMachine; TheKeyMachine.toggle()",
                                  b"import TheKeyMachine; TheKeyMachine.startup()")
        self.assertEqual(self.path.read_bytes(), expected)
        self.ns["refresh_userSetup"]()
        self.assertEqual(self.path.read_bytes(), expected)

    def test_refresh_does_not_enable_startup_or_rewrite_incomplete_block(self):
        for content in (b"# user's script\n", b"# start TheKeyMachine\nimport TheKeyMachine; TheKeyMachine.toggle()\n"):
            self.path.write_bytes(content)
            self.ns["refresh_userSetup"]()
            self.assertEqual(self.path.read_bytes(), content)

    def test_reinstall_keeps_required_cmds_import(self):
        self.ns["install_userSetup"]()
        self.ns["install_userSetup"]()
        content = self.path.read_text()
        self.assertEqual(content.count("from maya import cmds"), 1)
        self.assertIn("TheKeyMachine.startup()", content)
        compile(content, "userSetup.py", "exec")


class InstallAndBindingTests(unittest.TestCase):
    def test_installer_does_not_purge_modules_after_cleanup_veto(self):
        package = object()
        runtime = SimpleNamespace(cleanup_for_reload=Mock(side_effect=lifecycle.ShutdownBlocked("busy")))
        modules = {"TheKeyMachine": package, "TheKeyMachine.core.runtime": runtime}
        ns = definitions("TheKeyMachine_Drag&Drop_installer.py",
                         {"cleanup_running_tkm", "unload_tkm_modules"},
                         {"sys": SimpleNamespace(modules=modules)})
        with self.assertRaises(lifecycle.ShutdownBlocked): ns["unload_tkm_modules"]()
        self.assertIs(modules["TheKeyMachine"], package)
        self.assertIs(modules["TheKeyMachine.core.runtime"], runtime)

    def test_update_does_not_commit_after_cleanup_veto_and_cleans_staging(self):
        from TheKeyMachine import core
        operation = Mock(cancelled=False)
        operation.run_worker.side_effect = [None, ("staging", "package")]
        runtime = SimpleNamespace(cleanup_for_reload=Mock(side_effect=lifecycle.ShutdownBlocked("busy")))
        os = Mock()
        os.path.isfile.return_value = True
        shutil = Mock()
        commit = Mock()
        ns = definitions("TheKeyMachine/tools/update/controller.py", {"install"}, {
            "toolCommon": SimpleNamespace(require_tool_operation=lambda op: op),
            "os": os, "shutil": shutil, "__file__": "controller.py",
            "_stage_update_archive": Mock(), "_commit_staged_update": commit,
        })
        with patch.object(core, "runtime", runtime, create=True):
            with self.assertRaises(lifecycle.ShutdownBlocked):
                ns["install"](file_path="update.zip", tool_operation=operation)
        self.assertEqual(operation.run_worker.call_count, 2)
        commit.assert_not_called()
        shutil.rmtree.assert_called_once_with("staging", ignore_errors=True)

    def test_qt_binding_follows_host_major(self):
        ns = definitions("TheKeyMachine/core/Qt.py", {"_maya_binding"})
        for version, expected in [("5.15.2", "PySide2"), ("6.5.3", "PySide6")]:
            with self.subTest(version=version), patch.dict(sys.modules, {
                "maya": SimpleNamespace(cmds=SimpleNamespace(about=lambda **kw: version)),
            }):
                self.assertEqual(ns["_maya_binding"](), expected)

    def test_unknown_host_qt_does_not_fall_back_to_arbitrary_binding(self):
        ns = definitions("TheKeyMachine/core/Qt.py", {"_maya_binding"})
        with patch.dict(sys.modules, {
            "maya": SimpleNamespace(cmds=SimpleNamespace(about=lambda **kw: "7.0")),
        }):
            with self.assertRaises(ImportError): ns["_maya_binding"]()


if __name__ == "__main__":
    unittest.main()
