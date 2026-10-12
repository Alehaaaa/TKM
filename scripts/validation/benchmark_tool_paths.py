"""Synthetic Maya scene checks and timings; run explicitly with mayapy.

Creates an isolated Maya profile and a disposable batch scene. Never connects
to a running Maya GUI. Timings describe these fixtures, not production rigs.
"""

import json
import math
import os
from pathlib import Path
import statistics
import tempfile
import time
from types import SimpleNamespace

from test_toolbar_lifecycle import definitions


class CountedCommands:
    def __init__(self, commands):
        self.commands = commands
        self.counts = {}

    def __getattr__(self, name):
        def call(*args, **kwargs):
            self.counts[name] = self.counts.get(name, 0) + 1
            return getattr(self.commands, name)(*args, **kwargs)
        return call


class Operation:
    cancelled = False
    def set_total(self, total): pass
    def step(self, amount=1): pass


def benchmark(cmds, om):
    cmds.undoInfo(state=True)
    counted = CountedCommands(cmds)
    defaults = definitions("TheKeyMachine/tools/default_values/controller.py", {
        "_apply_selected_key_defaults", "_matches",
    }, {"cmds": counted, "_stored_default": lambda node, attr: 0.0})
    controls = [cmds.createNode("transform", name="auditControl#") for _ in range(10)]
    selected = []
    curves = []
    for node in controls:
        for frame in range(1, 101):
            cmds.setKeyframe(node, attribute="translateX", time=frame, value=frame)
        curve = cmds.keyframe(node, attribute="translateX", query=True, name=True)[0]
        curves.append(curve)
        selected.extend((curve, frame) for frame in range(1, 101, 2))

    def reference_defaults():
        for curve, frame in selected:
            counted.listConnections(curve + ".output", plugs=True, source=False, destination=True)
            counted.keyframe(curve, edit=True, valueChange=0.0, time=(frame, frame))

    def optimized_defaults():
        defaults["_apply_selected_key_defaults"](selected, Operation(), False, False, False)

    result = {}
    expected = [0.0 if frame % 2 else float(frame) for frame in range(1, 101)]
    for name, callback in (("reference", reference_defaults), ("optimized", optimized_defaults)):
        samples = []
        for _ in range(3):
            counted.counts.clear()
            cmds.undoInfo(openChunk=True)
            try:
                started = time.perf_counter()
                callback()
                samples.append((time.perf_counter() - started) * 1000)
            finally:
                cmds.undoInfo(closeChunk=True)
            for curve in curves:
                assert cmds.keyframe(curve, query=True, valueChange=True) == expected
            cmds.undo()
            for curve in curves:
                assert cmds.keyframe(curve, query=True, valueChange=True) == list(range(1, 101))
        result["defaults_" + name] = {"median_ms": round(statistics.median(samples), 3),
                                     "commands": dict(counted.counts)}

    node = controls[0]
    for frame in range(1, 81):
        for index, attr in enumerate(("rotateX", "rotateY", "rotateZ")):
            cmds.setKeyframe(node, attribute=attr, time=frame,
                            value=math.sin(frame * .1 + index) * 80)
    ns = definitions("TheKeyMachine/tools/gimbal_fixer/controller.py", {"GimbalAnalyzer"}, {
        "cmds": counted, "om": om, "math": math,
        "maya_api": SimpleNamespace(rotate_order_enum=lambda order: getattr(om.MEulerRotation, "k" + order.upper())),
    })
    analyzer = ns["GimbalAnalyzer"]()
    orders = ["xyz", "yzx", "zxy", "xzy", "yxz", "zyx"]

    def reference_gimbal():
        frames = set()
        for attr in ("rotateX", "rotateY", "rotateZ"):
            frames.update(counted.keyframe(node, attribute=attr, query=True, timeChange=True) or [])
        values = []
        for order in orders:
            worst = 0
            for frame in sorted(frames):
                rotation = analyzer._rotation_at_time(node, frame, orders)
                reordered = om.MEulerRotation(rotation.x, rotation.y, rotation.z, rotation.order)
                reordered.reorderIt(analyzer.convert_order_string(order))
                worst = max(worst, analyzer.compute_gimbal_percentage(reordered))
            values.append(worst)
        return values

    expected = reference_gimbal()
    for name, callback in (("reference", reference_gimbal),
                           ("optimized", lambda: analyzer.compute_all_percentages(node, orders))):
        samples = []
        for _ in range(3):
            counted.counts.clear()
            started = time.perf_counter()
            assert callback() == expected
            samples.append((time.perf_counter() - started) * 1000)
        result["gimbal_" + name] = {"median_ms": round(statistics.median(samples), 3),
                                   "commands": dict(counted.counts)}
    print(json.dumps(result, indent=2))


if __name__ == "__main__":
    with tempfile.TemporaryDirectory(prefix="tkm-tool-benchmark-") as profile:
        os.environ.update(MAYA_APP_DIR=profile, MAYA_SKIP_USERSETUP_PY="1",
                          MAYA_DISABLE_CIP="1", MAYA_DISABLE_CER="1", QT_QPA_PLATFORM="offscreen")
        import maya.standalone
        maya.standalone.initialize(name="python")
        try:
            from maya import cmds
            from maya.api import OpenMaya as om
            benchmark(cmds, om)
        finally:
            maya.standalone.uninitialize()
