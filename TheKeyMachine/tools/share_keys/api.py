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


def share_keys_mode_choices():
    """Live-translated choice list for the Share Keys menu's mode picker.

    Built fresh on every menu open (see ``widgets.toolbar_menus.build_declared_menu``'s
    ``"choice"`` handling, which calls this instead of a static list), the
    same pattern already used by ``tkm_menu.api``'s alignment/dock choices.
    """
    from TheKeyMachine.core import i18n

    return [
        {
            "value": SHARE_KEYS_MODE_PRESERVE_TANGENT,
            "label": i18n.tr("share_keys_mode_preserve_tangent", "Keep Tangent Type"),
            "description": i18n.tr(
                "share_keys_mode_preserve_tangent_desc",
                "Add missing keys without changing tangent type.",
            ),
        },
        {
            "value": SHARE_KEYS_MODE_PRESERVE_SHAPE,
            "label": i18n.tr("share_keys_mode_preserve_shape", "Keep Anim Curve Shape"),
            "description": i18n.tr(
                "share_keys_mode_preserve_shape_desc",
                "Insert missing keys while preserving animation curve shape.",
            ),
        },
    ]


def bake_tangent_mode_choices():
    """Live-translated choice list for the Bake menu's tangent-mode picker."""
    from TheKeyMachine.core import i18n

    return [
        {
            "value": BAKE_TANGENT_MODE_STEP,
            "label": i18n.tr("bake_tangent_mode_step", "Bake To Step Tangent"),
            "description": i18n.tr(
                "bake_tangent_mode_step_desc",
                "Bake keys, then turn baked tangents to stepped.",
            ),
        },
        {
            "value": BAKE_TANGENT_MODE_KEEP_TYPE,
            "label": i18n.tr("share_keys_mode_preserve_tangent", "Keep Tangent Type"),
            "description": i18n.tr(
                "bake_tangent_mode_keep_type_desc",
                "Bake keys without forcing the baked keys to stepped tangents.",
            ),
        },
        {
            "value": BAKE_TANGENT_MODE_KEEP_SHAPE,
            "label": i18n.tr("bake_tangent_mode_keep_shape", "Keep Animation Curve Shapes"),
            "description": i18n.tr(
                "bake_tangent_mode_keep_shape_desc",
                "Bake while preserving animation curve shapes where Maya can do so.",
            ),
        },
    ]


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


def bake_animation_custom(*args, anchor_widget=None):
    from TheKeyMachine.tools.share_keys.widgets import open_custom_bake
    return open_custom_bake(anchor_button=anchor_widget)
