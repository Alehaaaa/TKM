"""Qt lifetime tests, runnable with mayapy without starting Maya or userSetup.

QT_QPA_PLATFORM=offscreen mayapy -m unittest discover -s scripts/validation -v
"""

import importlib.util
import os
from pathlib import Path
import sys
import threading
import unittest
from unittest.mock import patch


ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT))
os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

try:
    import maya.cmds as cmds
    try:
        from PySide6 import QtCore, QtWidgets
    except ImportError:
        from PySide2 import QtCore, QtWidgets
except ImportError:
    QtCore = QtWidgets = None


@unittest.skipIf(QtCore is None, "Requires Maya's bundled PySide; run with mayapy")
class QtLifetimeTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        # Standalone mayapy has no cmds.about until Maya initializes. Supply only
        # the host version query; do not initialize Maya or touch user preferences.
        cls.about_patch = patch.object(cmds, "about", lambda **kw: QtCore.qVersion(), create=True)
        cls.about_patch.start()
        cls.app = QtWidgets.QApplication.instance() or QtWidgets.QApplication([])
        from TheKeyMachine.core import workers, lifecycle, Qt
        cls.workers = workers
        cls.lifecycle = lifecycle
        cls.qt = Qt

    @classmethod
    def tearDownClass(cls):
        cls.about_patch.stop()

    def tearDown(self):
        self.workers.shutdown_for_application_exit()
        self.app.processEvents()
        self.app.sendPostedEvents(None, QtCore.QEvent.DeferredDelete)

    def test_adapter_uses_native_binding_despite_environment_preference(self):
        expected = "PySide6" if QtCore.qVersion().startswith("6.") else "PySide2"
        self.assertEqual(self.qt.__binding__, expected)
        with patch.dict(os.environ, {"QT_PREFERRED_BINDING": "PyQt6"}):
            spec = importlib.util.spec_from_file_location("_test_qt_adapter", ROOT / "TheKeyMachine/core/Qt.py")
            module = importlib.util.module_from_spec(spec)
            with patch.dict(sys.modules, {spec.name: module}):
                spec.loader.exec_module(module)
            self.assertEqual(module.__binding__, expected)

    def test_reader_veto_leaves_result_delivery_connected(self):
        release = threading.Event()
        entered = threading.Event()
        result = []
        def read():
            entered.set()
            release.wait(2)
            return "catalog"
        worker = self.workers.BackgroundCallThread(read)
        worker.loaded.connect(result.append)
        worker.start()
        self.assertTrue(entered.wait(1))
        try:
            with self.assertRaises(self.lifecycle.ShutdownBlocked):
                self.workers.shutdown_background_threads()
            self.assertFalse(worker._cancelled)
        finally:
            release.set()
            self.assertTrue(worker.wait(1000))
        self.app.processEvents()
        self.assertEqual(result, ["catalog"])

    def test_exit_hook_joins_worker_after_toolbar_unload(self):
        entered = threading.Event()
        class NetworkWorker(self.workers.BackgroundThread):
            def run(self):
                entered.set()
                self.msleep(60)
        worker = NetworkWorker()
        worker.start()
        self.assertTrue(entered.wait(1))
        self.workers.shutdown_background_threads()
        self.assertTrue(worker._cancelled)
        self.app.aboutToQuit.emit()
        self.assertFalse(worker.isRunning())

    def test_exit_hook_covers_workers_from_multiple_package_generations(self):
        old_hook = getattr(self.app, self.workers._APP_EXIT_HOOK_ATTRIBUTE, None)
        entered = threading.Event()
        class OldWorker(self.workers.BackgroundThread):
            def run(self):
                entered.set()
                self.msleep(60)
        old = OldWorker()
        old.start()
        self.assertTrue(entered.wait(1))
        spec = importlib.util.spec_from_file_location("_test_new_workers", ROOT / "TheKeyMachine/core/workers.py")
        new = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(new)
        current = new.BackgroundCallThread(lambda: "new")
        current.start()
        self.assertIn(old, new._application_threads())
        if old_hook is not None:
            self.assertIs(getattr(self.app, new._APP_EXIT_HOOK_ATTRIBUTE), old_hook)
        self.app.aboutToQuit.emit()
        self.assertFalse(old.isRunning())
        self.assertFalse(current.isRunning())


if __name__ == "__main__":
    unittest.main()
