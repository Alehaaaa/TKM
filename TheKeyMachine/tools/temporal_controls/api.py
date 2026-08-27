"""Public entry points for Temporal Controls. Thin wrappers around ``controller``."""

from TheKeyMachine.tools.temporal_controls import SPACES, SWITCHABLE_SPACES, SYSTEMS
from TheKeyMachine.tools.temporal_controls import controller
from TheKeyMachine.tools.temporal_controls.controller import (
    DEFAULT_SPACE,
    DEFAULT_SYSTEM,
    EXTRA_ATTR,
    ORIENTATIONS,
    SIZE_NUDGE_STEP,
    TAG_ATTR,
    TkmSceneNode,
    controls_bus,
)

__all__ = [
    "DEFAULT_SPACE",
    "DEFAULT_SYSTEM",
    "EXTRA_ATTR",
    "ORIENTATIONS",
    "SIZE_NUDGE_STEP",
    "SPACES",
    "SWITCHABLE_SPACES",
    "SYSTEMS",
    "TAG_ATTR",
    "TkmSceneNode",
    "controls_bus",
    "add_child_control",
    "add_parent_control",
    "bake_control",
    "bake_controls",
    "clear_last_used_options",
    "create_controls",
    "create_controls_with_options",
    "edit_pivot",
    "get_bake_mode",
    "get_control_color",
    "get_control_orientation",
    "get_control_orientation_space",
    "get_control_position_space",
    "get_control_shape_id",
    "get_last_used_options",
    "is_control_space_locked",
    "is_super_mode_enabled",
    "list_panel_rigs",
    "list_rigs",
    "mute_and_bake",
    "mute_and_revert",
    "open_temp_controls_panel",
    "remove_extra_control",
    "reset_pivot",
    "revert_controls",
    "root_target_for",
    "save_last_used_options",
    "scale_control",
    "set_bake_mode",
    "set_control_orientation",
    "set_control_shape",
    "set_control_space",
    "set_control_space_locked",
    "set_rig_color",
    "set_super_mode_enabled",
    "switch_controls_to_camera_space",
    "switch_controls_to_child_space",
    "switch_controls_to_object_space",
    "switch_controls_to_relative_space",
    "switch_controls_to_world_space",
    "toggle_temporal_control_rigs",
]


# ----------------------------------------------------------------------
# Entry point / dialog plumbing
# ----------------------------------------------------------------------


def create_controls(*_args):
    return controller.create_controls(*_args)


def save_last_used_options(system, position_space, orientation_space, color_suffix):
    return controller.save_last_used_options(
        system, position_space, orientation_space, color_suffix
    )


def clear_last_used_options():
    return controller.clear_last_used_options()


def get_last_used_options():
    return controller.get_last_used_options()


def get_bake_mode():
    return controller.get_bake_mode()


def set_bake_mode(mode_id):
    return controller.set_bake_mode(mode_id)


def is_super_mode_enabled():
    return controller.is_super_mode_enabled()


def set_super_mode_enabled(enabled):
    return controller.set_super_mode_enabled(enabled)


# ----------------------------------------------------------------------
# Create
# ----------------------------------------------------------------------


def create_controls_with_options(
    objects,
    system=DEFAULT_SYSTEM,
    position_space=DEFAULT_SPACE,
    orientation_space=DEFAULT_SPACE,
    label="",
    color=None,
    anchor_widget=None,
    tool_operation=None,
):
    return controller.create_controls_with_options(
        objects,
        system=system,
        position_space=position_space,
        orientation_space=orientation_space,
        label=label,
        color=color,
        anchor_widget=anchor_widget,
        tool_operation=tool_operation,
    )


# ----------------------------------------------------------------------
# Temp Controls Panel: shape / size / orientation
# ----------------------------------------------------------------------


def get_control_orientation(control):
    return controller.get_control_orientation(control)


def get_control_shape_id(control):
    return controller.get_control_shape_id(control)


def get_control_color(control):
    return controller.get_control_color(control)


def set_rig_color(root_target, color_hex):
    return controller.set_rig_color(root_target, color_hex)


def scale_control(control, factor):
    return controller.scale_control(control, factor)


def set_control_orientation(control, orientation_id):
    return controller.set_control_orientation(control, orientation_id)


def set_control_shape(control, shape_id):
    return controller.set_control_shape(control, shape_id)


# ----------------------------------------------------------------------
# Position / Orientation space conversion & live switching
# ----------------------------------------------------------------------


def switch_controls_to_world_space(*_args, tool_operation=None):
    return controller.switch_controls_to_world_space(
        *_args, tool_operation=tool_operation
    )


def switch_controls_to_object_space(*_args, tool_operation=None):
    return controller.switch_controls_to_object_space(
        *_args, tool_operation=tool_operation
    )


def switch_controls_to_camera_space(*_args, tool_operation=None):
    return controller.switch_controls_to_camera_space(
        *_args, tool_operation=tool_operation
    )


def switch_controls_to_relative_space(*_args, tool_operation=None):
    return controller.switch_controls_to_relative_space(
        *_args, tool_operation=tool_operation
    )


def switch_controls_to_child_space(*_args, tool_operation=None):
    return controller.switch_controls_to_child_space(
        *_args, tool_operation=tool_operation
    )


def get_control_position_space(control):
    return controller.get_control_position_space(control)


def get_control_orientation_space(control):
    return controller.get_control_orientation_space(control)


def is_control_space_locked(control):
    return controller.is_control_space_locked(control)


def set_control_space_locked(control, locked):
    return controller.set_control_space_locked(control, locked)


def toggle_temporal_control_rigs(*_args, enabled=None, tool_operation=None):
    return controller.toggle_temporal_control_rigs(
        *_args, enabled=enabled, tool_operation=tool_operation
    )


def set_control_space(control, group_kind, space_id, tool_operation=None):
    return controller.set_control_space(
        control, group_kind, space_id, tool_operation=tool_operation
    )


# ----------------------------------------------------------------------
# Bake / Revert
# ----------------------------------------------------------------------


def bake_control(control):
    return controller.bake_control(control)


def bake_controls(*_args, tool_operation=None):
    return controller.bake_controls(*_args, tool_operation=tool_operation)


def revert_controls(*_args, tool_operation=None):
    return controller.revert_controls(*_args, tool_operation=tool_operation)


def mute_and_revert(*_args):
    return controller.mute_and_revert(*_args)


def mute_and_bake(*_args):
    return controller.mute_and_bake(*_args)


# ----------------------------------------------------------------------
# Temp Controls Panel: rig list, add/remove control, pivot
# ----------------------------------------------------------------------


def list_rigs():
    return controller.list_rigs()


def list_panel_rigs():
    return controller.list_panel_rigs()


def root_target_for(control):
    return controller.root_target_for(control)


def add_parent_control(control):
    return controller.add_parent_control(control)


def add_child_control(parent_control):
    return controller.add_child_control(parent_control)


def remove_extra_control(control):
    return controller.remove_extra_control(control)


def edit_pivot(control):
    return controller.edit_pivot(control)


def reset_pivot(control):
    return controller.reset_pivot(control)


def open_temp_controls_panel(*_args):
    return controller.open_temp_controls_panel(*_args)
