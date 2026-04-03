"""
Central asset registry for image paths used across TheKeyMachine.
"""

from __future__ import annotations

import os

import TheKeyMachine.tools.colors as toolColors
from TheKeyMachine.mods.generalMod import config


INSTALL_PATH = config["INSTALL_PATH"]
IMAGE_ROOT = os.path.join(INSTALL_PATH, "TheKeyMachine", "data", "img")
SELECTION_SETS_ROOT = os.path.join(IMAGE_ROOT, "selection_sets")


_ASSET_FILES = {
    "tool_icon": "TheKeyMachine_icon.png",
    "stripe_image": "stripe.png",
    "TheKeyMachine_logo_250_image": "TheKeyMachine_logo_250.png",
    "tkm_node_image": "tkm_node.png",
    "install_image": "install.png",
    "skip_image": "skip.png",
    "nudge_left_image": "nudge_left.svg",
    "nudge_right_image": "nudge_right.svg",
    "insert_inbetween_image": "nudge_insert_inbetween.svg",
    "remove_inbetween_image": "nudge_remove_inbetween.svg",
    "pointer_image": "pointer.svg",
    "depth_mover_image": "depth_mover.svg",
    "select_rig_controls_image": "select_rig_controls.svg",
    "select_rig_controls_animated_image": "select_rig_controls_animated.svg",
    "isolate_image": "isolate.svg",
    "create_locator_image": "cube.svg",
    "align_menu_image": "magnet.svg",
    "tracer_image": "tracer.svg",
    "reset_animation_image": "eraser.svg",
    "delete_animation_image": "delete_animation.svg",
    "match_image": "magnet.svg",
    "opposite_select_image": "opposite_select.svg",
    "opposite_copy_image": "opposite_copy.svg",
    "opposite_add_image": "opposite_add.svg",
    "mirror_image": "mirror.svg",
    "copy_animation_image": "copy_animation.svg",
    "paste_animation_image": "paste_animation.svg",
    "paste_insert_animation_image": "paste_insert_animation.svg",
    "paste_opposite_animation_image": "paste_opposite_animation.svg",
    "copy_pose_image": "copy_pose.svg",
    "paste_pose_image": "paste_pose.svg",
    "reblock_keys_image": "reblock.svg",
    "share_keys_image": "share_keys.svg",
    "bake_animation_custom_image": "bake_animation_custom.svg",
    "bake_animation_1_image": "bake_animation_1.svg",
    "bake_animation_2_image": "bake_animation_2.svg",
    "bake_animation_3_image": "bake_animation_3.svg",
    "selector_image": "selector.svg",
    "select_hierarchy_image": "select_hierarchy.svg",
    "animation_offset_image": "animation_offset.svg",
    "follow_cam_image": "camera.svg",
    "link_objects_image": "link_relative.svg",
    "link_objects_copy_image": "link_relative_copy.svg",
    "link_objects_paste_image": "link_relative_paste.svg",
    "link_objects_on_image": "link_relative_on.svg",
    "worldspace_copy_animation_image": "worldspace_copy_animation.svg",
    "worldspace_paste_animation_image": "worldspace_paste_animation.svg",
    "worldspace_copy_frame_image": "worldspace_copy_frame.svg",
    "worldspace_paste_frame_image": "worldspace_paste_frame.svg",
    "temp_pivot_image": "temp_pivot.svg",
    "temp_pivot_use_last_image": "temp_pivot_use_last.svg",
    "ruler_image": "ruler.svg",
    "auto_tangent_image": "tangent_auto.svg",
    "spline_tangent_image": "tangent_spline.svg",
    "clamped_tangent_image": "tangent_clamped.svg",
    "linear_tangent_image": "tangent_linear.svg",
    "flat_tangent_image": "tangent_flat.svg",
    "step_tangent_image": "tangent_step.svg",
    "plateau_tangent_image": "tangent_plateau.svg",
    "bouncy_tangent_image": "tangent_bouncy.svg",
    "match_curve_cycle_image": "match_curve_cycle.svg",
    "bouncy_curve_image": "bouncy_curve.svg",
    "playblast_image": "playblast.svg",
    "selection_sets_image": "selection_sets.svg",
    "hotkeys_image": "hotkeys.svg",
    "selection_sets_add_image": "selection_sets_add.svg",
    "selection_sets_reload_image": "selection_sets_reload.svg",
    "selection_sets_import_image": "selection_sets_import.svg",
    "selection_sets_export_image": "selection_sets_export.svg",
    "customGraph_image": "customGraph.svg",
    "orbit_ui_image": "orbit_ui.svg",
    "attribute_switcher_image": "attribute_switcher.svg",
    "globe_image": "globe.svg",
    "custom_tools_image": "tools_folder.svg",
    "custom_scripts_image": "scripts_folder.svg",
    "settings_image": "settings.svg",
    "settings_update_image": "settings_update.svg",
    "close_image": "close.svg",
    "apply_image": "apply.svg",
    "cancel_image": "cancel.svg",
    "add_image": "add.svg",
    "subtract_image": "subtract.svg",
    "rename_image": "rename.svg",
    "trash_image": "trash.svg",
    "success_image": "success.svg",
    "warning_image": "warning.svg",
    "dot_green_image": "dot_green.png",
    "dot_red_image": "dot_red.png",
    "dot_grey_image": "dot_grey.png",
    "dot_blue_image": "dot_blue.png",
    "dot_yellow_image": "dot_yellow.png",
    "dot_pins_image": "dot_round.png",
    "color_image": "color.svg",
    "reload_image": "reload.png",
    "remove_image": "remove.svg",
    "dock_image": "dock.png",
    "check_updates_image": "check_updates.svg",
    "check_updates_image_available": "check_updates_available.svg",
    "report_a_bug_image": "bug.svg",
    "about_image": "about.png",
    "refresh_image": "refresh.svg",
    "help_menu_image": "help.svg",
    "ibookmarks_menu_image": "ibookmarks_menu.png",
    "discord_image": "discord.svg",
    "youtube_image": "youtube.svg",
    "tracer_show_hide_image": "tracer_show_hide.svg",
    "tracer_select_offset_image": "tracer_select_offset.svg",
    "tracer_set_color_image": "tracer_set_color.svg",
    "tracer_red_image": "tracer_red.svg",
    "tracer_grey_image": "tracer_grey.svg",
    "tracer_blue_image": "tracer_blue.svg",
}

_ASSET_ALIASES = {
    "update_image": "settings_update_image",
    "grey_got_image": "dot_grey_image",
}

_selection_set_icon_shade_names = {
    "light": "Light",
    "base": "",
    "dark": "Dark",
}


def _resolve_asset_name(name: str) -> str:
    return _ASSET_ALIASES.get(name, name)


def getImage(image: str) -> str:
    return os.path.join(IMAGE_ROOT, image)


def getSelectionSetsImage(image: str) -> str:
    return os.path.join(SELECTION_SETS_ROOT, image)


def asset_path(name: str, default=None):
    asset_name = _resolve_asset_name(name)
    filename = _ASSET_FILES.get(asset_name)
    if not filename:
        return default
    return getImage(filename)


def has_asset(name: str) -> bool:
    return asset_path(name) is not None


def require_asset(name: str) -> str:
    path = asset_path(name)
    if path is None:
        raise AttributeError("Unknown media asset: {}".format(name))
    return path


def get(name, default=None):
    return asset_path(name, default=default)


def _selection_set_icon_filename(color):
    shade = _selection_set_icon_shade_names.get(color.shade, "")
    return "_{}{}_set.svg".format(color.family, shade)


selection_set_color_icon_names = {color.suffix: _selection_set_icon_filename(color) for color in toolColors.SELECTION_SET_COLORS}
selection_set_color_images = {suffix: getSelectionSetsImage(filename) for suffix, filename in selection_set_color_icon_names.items()}
selection_set_color_trash_images = {
    suffix: getSelectionSetsImage(filename.replace(".svg", "_trash.svg")) for suffix, filename in selection_set_color_icon_names.items()
}


def __getattr__(name):
    path = asset_path(name)
    if path is not None:
        return path
    if name.endswith("_image"):
        return None
    raise AttributeError(name)
