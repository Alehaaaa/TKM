"""Rig snapshot capture: opposite-control, default-pose and mirror data."""

from TheKeyMachine.core import rig_snapshot
import TheKeyMachine.mods.selectionMod as selectionMod
from TheKeyMachine.tools import common as toolCommon
import TheKeyMachine.widgets.util as wutil


def _snapshot_controls(kinds, tool_id, label):
    selected_controls = selectionMod.get_selected_objects(long=True)
    if not selected_controls:
        return wutil.make_inViewMessage("Select at least one object")

    groups = rig_snapshot.group_controls_by_rig(selected_controls)
    if not groups:
        return wutil.make_inViewMessage("Selected controls are not part of a recognizable rig")

    total = sum(len(group["controls"]) for group in groups.values())
    with toolCommon.tool_operation(
        tool_id=tool_id,
        label=label,
        progress=True,
        progress_max=total,
        undo=False,
    ) as operation:
        operation.start()
        for rig_id, group in groups.items():
            if operation.cancelled:
                break
            opposite_entries = {}
            default_entries = {}
            for control in group["controls"]:
                if operation.cancelled:
                    break
                shortname = rig_snapshot.control_key(control)
                if "opposite" in kinds:
                    opposite_entries[shortname] = rig_snapshot.capture_opposite(control)
                if "default" in kinds:
                    default_entries[shortname] = rig_snapshot.capture_default_values(control)
                operation.step()
            if opposite_entries:
                rig_snapshot.merge_control_entries(rig_id, "opposite", opposite_entries)
            if default_entries:
                rig_snapshot.merge_control_entries(rig_id, "default", default_entries)

    wutil.make_inViewMessage(f"{label} saved")


def snapshot_rig(*args):
    return _snapshot_controls(("opposite", "default"), tool_id="snapshot_rig", label="Snapshot Rig")


def snapshot_default(*args):
    return _snapshot_controls(("default",), tool_id="snapshot_default", label="Snapshot Default")


def snapshot_opposite(*args):
    return _snapshot_controls(("opposite",), tool_id="snapshot_opposite", label="Snapshot Opposite")


def snapshot_mirror(*args):
    # Mirror exceptions are rule-based (see mirror.controller.apply_exception) and
    # only ever persist actual overrides -- there is nothing to auto-capture for a
    # control with no manually-set exception. Add Exception Invert/Keep (in the
    # Mirror tool) already write straight to the rig snapshot.
    selected_controls = selectionMod.get_selected_objects(long=True)
    if not selected_controls:
        return wutil.make_inViewMessage("Select at least one object")
    if not rig_snapshot.group_controls_by_rig(selected_controls):
        return wutil.make_inViewMessage("Selected controls are not part of a recognizable rig")
    return wutil.make_inViewMessage(
        "Mirror exceptions are saved automatically via Add Exception Invert/Keep"
    )
