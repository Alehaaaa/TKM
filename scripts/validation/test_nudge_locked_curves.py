"""Focused regression checks for locked animation-layer weight curves."""

import importlib.util
import pathlib
import sys
import types
import unittest


ROOT = pathlib.Path(__file__).resolve().parents[2]
CONTROLLER = ROOT / "TheKeyMachine" / "tools" / "nudge" / "controller.py"
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))


class _FakeCmds(object):
    locked_plugs = set()

    @classmethod
    def getAttr(cls, plug, lock=False):
        return bool(lock and plug in cls.locked_plugs)

    @staticmethod
    def lockNode(_node, query=False, lock=False):
        return [False]

    @staticmethod
    def objExists(_node):
        return True


def _module(name, **attributes):
    module = types.ModuleType(name)
    for key, value in attributes.items():
        setattr(module, key, value)
    return module


def _load_controller():
    fake_animation = _module(
        "TheKeyMachine.maya.animation",
        weight_curves=lambda layer: ["weightCurve"] if layer == "LayerA" else [],
        layer_graph=types.SimpleNamespace(ownership=lambda *_args, **_kwargs: {}),
    )
    fake_selection = _module(
        "TheKeyMachine.maya.selection",
        get_anim_curve_output_plugs=lambda _curves: [],
    )
    fake_animation_tools_api = _module("TheKeyMachine.tools.animation_tools.api")
    modules = {
        "maya": _module("maya", cmds=_FakeCmds),
        "TheKeyMachine.maya": _module(
            "TheKeyMachine.maya",
            animation=fake_animation,
            maya_api=_module("TheKeyMachine.maya.maya_api"),
            selection=fake_selection,
        ),
        "TheKeyMachine.core": _module(
            "TheKeyMachine.core",
            settings=_module("TheKeyMachine.core.settings"),
        ),
        "TheKeyMachine.tools.common": _module("TheKeyMachine.tools.common"),
        "TheKeyMachine.ui.widgets.timeline": _module("TheKeyMachine.ui.widgets.timeline"),
        "TheKeyMachine.ui.widgets.util": _module("TheKeyMachine.ui.widgets.util"),
        "TheKeyMachine.tools.animation_tools": _module(
            "TheKeyMachine.tools.animation_tools", api=fake_animation_tools_api
        ),
        "TheKeyMachine.tools.animation_tools.api": fake_animation_tools_api,
    }
    saved = {name: sys.modules.get(name) for name in modules}
    sys.modules.update(modules)
    try:
        spec = importlib.util.spec_from_file_location("_tkm_nudge_regression", CONTROLLER)
        controller = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(controller)
        return controller
    finally:
        for name, previous in saved.items():
            if previous is None:
                sys.modules.pop(name, None)
            else:
                sys.modules[name] = previous


class LockedWeightCurveTests(unittest.TestCase):
    def setUp(self):
        _FakeCmds.locked_plugs = set()
        self.controller = _load_controller()
        self.context = {
            "root_name": "BaseAnimation",
            "context": {
                "layers": {
                    "LayerA": {"name": "LayerA", "locked": False, "root": False},
                }
            },
        }

    def test_locked_weight_plug_excludes_its_curve(self):
        _FakeCmds.locked_plugs = {"LayerA.weight"}
        edit_filter = self.controller._CurveEditFilter(self.context)
        self.assertFalse(edit_filter.is_editable("weightCurve"))

    def test_unlocked_weight_plug_keeps_its_curve_editable(self):
        edit_filter = self.controller._CurveEditFilter(self.context)
        self.assertTrue(edit_filter.is_editable("weightCurve"))


if __name__ == "__main__":
    unittest.main()
