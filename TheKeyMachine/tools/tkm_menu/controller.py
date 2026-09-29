"""Compatibility facade for TKM Menu behavior."""


def _save_scene_as():
    from TheKeyMachine.tools.tkm_menu import api

    return api._save_scene_as_before_reload()


def _save_scene():
    from TheKeyMachine.tools.tkm_menu import api

    return api._save_scene_before_reload()


def reload_toolbar_with_scene_prompt(anchor_widget=None):
    from TheKeyMachine.tools.tkm_menu import api

    return api._reload_toolbar_with_scene_prompt(anchor_widget=anchor_widget)
