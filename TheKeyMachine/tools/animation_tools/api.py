"""Public entry point for animation tools."""

from TheKeyMachine.tools.animation_tools import controller


REMOVE_REDUNDANT_MODE_FLAT = controller.REMOVE_REDUNDANT_MODE_FLAT
REMOVE_REDUNDANT_MODE_ALL = controller.REMOVE_REDUNDANT_MODE_ALL


def apply_smart_euler_filter(*args):
    return controller.apply_smart_euler_filter(*args)


def clear_animation_keys(*args):
    return controller.clear_animation_keys(*args)


def copy_keys(*args):
    return controller.copy_keys(*args)


def crop_animation(*args):
    return controller.crop_animation(*args)


def cut_keys(*args):
    return controller.cut_keys(*args)


def delete_keys(*args):
    return controller.delete_keys(*args)


def go_to_next_key(*args):
    return controller.go_to_next_key(*args)


def go_to_previous_key(*args):
    return controller.go_to_previous_key(*args)


def go_to_next_frame(*args):
    return controller.go_to_next_frame(*args)


def go_to_previous_frame(*args):
    return controller.go_to_previous_frame(*args)


def paste_keys(*args):
    return controller.paste_keys(*args)


def paste_keys_relative(*args):
    return controller.paste_keys_relative(*args)


def remove_redundant_keys(*args):
    return controller.remove_redundant_keys(*args)


def get_remove_redundant_mode():
    return controller.get_remove_redundant_mode()


def set_remove_redundant_mode(mode):
    return controller.set_remove_redundant_mode(mode)


def remove_redundant_mode_choices():
    """Live-translated choice list for the Remove Redundant Keys menu's mode picker.

    Built fresh on every menu open (see ``widgets.toolbar_menus.build_declared_menu``'s
    ``"choice"`` handling, which calls this instead of a static list), the
    same pattern already used by ``tkm_menu.api``'s alignment/dock choices.
    """
    from TheKeyMachine.core import i18n

    return [
        {
            "value": REMOVE_REDUNDANT_MODE_FLAT,
            "label": i18n.tr("remove_redundant_mode_flat", "Only Affect Flat Keys"),
            "description": i18n.tr(
                "remove_redundant_mode_flat_desc",
                "Remove only interior keys from flat-value runs. Non-flat motion keys are left untouched.",
            ),
        },
        {
            "value": REMOVE_REDUNDANT_MODE_ALL,
            "label": i18n.tr("remove_redundant_mode_all", "All Redundant"),
            "description": i18n.tr(
                "remove_redundant_mode_all_desc",
                "Simplify all redundant keys on the active curves while preserving the current key selection.",
            ),
        },
    ]


def remove_static_anim_curves(*args):
    return controller.remove_static_anim_curves(*args)


def reverse_animation(*args):
    return controller.reverse_animation(*args)


def set_smart_key(*args):
    return controller.set_smart_key(*args)


def set_smart_key_all_channels(*args):
    return controller.set_smart_key_all_channels(*args)


def snap_keyframes(*args):
    return controller.snap_keyframes(*args)


def clear_selected_keys(*args):
    return controller.clear_selected_keys(*args)


def select_all_animation_curves(*args):
    return controller.select_all_animation_curves(*args)


def delete_keyframes_before_current_time(*args):
    return controller.delete_keyframes_before_current_time(*args)


def delete_keyframes_after_current_time(*args):
    return controller.delete_keyframes_after_current_time(*args)


def cleanup():
    return controller.cleanup()
