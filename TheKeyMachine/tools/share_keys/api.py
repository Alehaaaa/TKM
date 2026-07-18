"""Public entry point for Share Keys, Reblock, and Bake."""

from TheKeyMachine.tools.share_keys import controller


SHARE_KEYS_MODE_PRESERVE_TANGENT = controller.SHARE_KEYS_MODE_PRESERVE_TANGENT
SHARE_KEYS_MODE_PRESERVE_SHAPE = controller.SHARE_KEYS_MODE_PRESERVE_SHAPE
BAKE_TANGENT_MODE_STEP = controller.BAKE_TANGENT_MODE_STEP
BAKE_TANGENT_MODE_KEEP_TYPE = controller.BAKE_TANGENT_MODE_KEEP_TYPE
BAKE_TANGENT_MODE_KEEP_SHAPE = controller.BAKE_TANGENT_MODE_KEEP_SHAPE


def get_share_keys_mode(): return controller.get_share_keys_mode()
def set_share_keys_mode(mode): return controller.set_share_keys_mode(mode)
def get_bake_tangent_mode(): return controller.get_bake_tangent_mode()
def set_bake_tangent_mode(mode): return controller.set_bake_tangent_mode(mode)


def share_keys(*args): return controller.share_keys(*args)
def share_keys_from_last_selected(*args): return controller.share_keys_from_last_selected(*args)
def reblock_move(*args): return controller.reblock_move(*args)
def reblock_insert(*args): return controller.reblock_insert(*args)
def bake_animation(*args, **kwargs): return controller.bake_animation(*args, **kwargs)
def bake_animation_1(*args): return controller.bake_animation_1(*args)
def bake_animation_2(*args): return controller.bake_animation_2(*args)
def bake_animation_3(*args): return controller.bake_animation_3(*args)
def bake_animation_4(*args): return controller.bake_animation_4(*args)
def bake_animation_from_last_selected(*args): return controller.bake_animation_from_last_selected(*args)


def bake_animation_custom(*args):
    from TheKeyMachine.tools.share_keys.widgets import open_custom_bake
    return open_custom_bake()
