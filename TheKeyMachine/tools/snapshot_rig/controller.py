"""Rig snapshot capture: opposite-control, default-pose and mirror data."""

from contextlib import nullcontext

from TheKeyMachine.tools.snapshot_rig import rig_snapshot
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

    attrs_by_control = {
        control: rig_snapshot.snapshot_attrs(control)
        for group in groups.values()
        for control in group["controls"]
    }
    opposite_weight = int("opposite" in kinds)
    attr_weight = (
        int("default" in kinds)
        + rig_snapshot.MIRROR_PROGRESS_WEIGHT * int("mirror" in kinds)
    )
    total = sum(
        opposite_weight + len(attrs_by_control[control]) * attr_weight
        for group in groups.values()
        for control in group["controls"]
    )
    with toolCommon.tool_operation(
        tool_id=tool_id,
        label=label,
        progress=True,
        progress_max=total,
        undo=False,
    ) as operation:
        operation.start()
        processor = operation.set_status(label)
        probe_session = (
            rig_snapshot.mirror_probe_session()
            if "mirror" in kinds
            else nullcontext()
        )
        with probe_session:
            for rig_id, group in groups.items():
                if processor.cancelled:
                    break
                opposite_entries = {}
                default_entries = {}
                mirror_entries = {}
                for control in group["controls"]:
                    if processor.cancelled:
                        break
                    shortname = rig_snapshot.control_key(control)
                    if "opposite" in kinds:
                        opposite_entries[shortname] = rig_snapshot.capture_opposite(control)
                        processor.step()
                    if "default" in kinds:
                        default_values = rig_snapshot.capture_default_values(
                            control,
                            attrs=attrs_by_control[control],
                            processor=processor,
                        )
                        if processor.cancelled:
                            break
                        default_entries[shortname] = default_values
                    if "mirror" in kinds and not processor.cancelled:
                        directions = rig_snapshot.capture_mirror_directions(
                            control,
                            attrs=attrs_by_control[control],
                            processor=processor,
                        )
                        if processor.cancelled:
                            break
                        mirror_entries[shortname] = directions
                if opposite_entries:
                    rig_snapshot.merge_control_entries(rig_id, "opposite", opposite_entries)
                if default_entries:
                    rig_snapshot.merge_control_entries(rig_id, "default", default_entries)
                if mirror_entries:
                    rig_snapshot.merge_control_entries(
                        rig_id, "mirror", mirror_entries, replace=True,
                    )

    message = f"{label} cancelled" if processor.cancelled else f"{label} saved"
    wutil.make_inViewMessage(message)


def snapshot_rig(*args):
    return _snapshot_controls(
        ("opposite", "default", "mirror"), tool_id="snapshot_rig", label="Snapshot Rig"
    )


def snapshot_default(*args):
    return _snapshot_controls(("default",), tool_id="snapshot_default", label="Snapshot Default")


def snapshot_opposite(*args):
    return _snapshot_controls(("opposite",), tool_id="snapshot_opposite", label="Snapshot Opposite")


def snapshot_mirror(*args):
    return _snapshot_controls(("mirror",), tool_id="snapshot_mirror", label="Snapshot Mirror")
