"""Public entry point for animation tools."""

from TheKeyMachine.tools.animation_tools import controller


REMOVE_REDUNDANT_MODE_FLAT = controller.REMOVE_REDUNDANT_MODE_FLAT
REMOVE_REDUNDANT_MODE_ALL = controller.REMOVE_REDUNDANT_MODE_ALL


def apply_smart_euler_filter(*args, **kwargs):
    return controller.apply_smart_euler_filter(*args, **kwargs)


def clear_animation_keys(*args):
    return controller.clear_animation_keys(*args)


def copy_keys(*args):
    return controller.copy_keys(*args)


def crop_animation(*args, **kwargs):
    return controller.crop_animation(*args, **kwargs)


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


def paste_keys(*args, **kwargs):
    return controller.paste_keys(*args, **kwargs)


def paste_keys_relative(*args, **kwargs):
    return controller.paste_keys_relative(*args, **kwargs)


def remove_redundant_keys(*args, **kwargs):
    return controller.remove_redundant_keys(*args, **kwargs)


def get_remove_redundant_mode():
    return controller.get_remove_redundant_mode()


def set_remove_redundant_mode(mode):
    return controller.set_remove_redundant_mode(mode)


def remove_static_anim_curves(*args, **kwargs):
    return controller.remove_static_anim_curves(*args, **kwargs)


def reverse_animation(*args, **kwargs):
    return controller.reverse_animation(*args, **kwargs)


def set_smart_key(*args, **kwargs):
    return controller.set_smart_key(*args, **kwargs)


def set_smart_key_all_channels(*args, **kwargs):
    return controller.set_smart_key_all_channels(*args, **kwargs)


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
