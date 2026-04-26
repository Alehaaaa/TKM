"""
TheKeyMachine Sliders Module: A unified system for managing Tween, Blend, and Curve sliders.
"""

from TheKeyMachine.tooltips import parse_tt
from .manager import TWEEN_MODES, BLEND_MODES, TANGENT_MODES


def execute_tween_slider(mode, value, world_space=False, session=None):
    from . import api

    return api.execute_tween_slider(mode, value, world_space=world_space, session=session)


def execute_blend_to_frame_with_button_values(value, session=None):
    from . import api

    return api.execute_blend_to_frame_with_button_values(value, session=session)


def execute_blend_slider(mode, value, session=None):
    from . import api

    return api.execute_blend_slider(mode, value, session=session)


def execute_tangent_slider(mode, value, session=None):
    from . import api

    return api.execute_tangent_slider(mode, value, session=session)


def stop_dragging(session=None):
    from . import api

    return api.stop_dragging(session=session)


__all__ = [
    "execute_tween_slider",
    "execute_blend_to_frame_with_button_values",
    "execute_blend_slider",
    "execute_tangent_slider",
    "start_dragging",
    "stop_dragging",
    "parse_tt",
    "TWEEN_MODES",
    "BLEND_MODES",
    "TANGENT_MODES",
]
