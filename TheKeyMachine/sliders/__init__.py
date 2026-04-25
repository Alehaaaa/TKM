"""
TheKeyMachine Sliders Module: A unified system for managing Tween, Blend, and Curve sliders.
"""

from TheKeyMachine.tooltips import parse_tt
from .manager import TWEEN_MODES, BLEND_MODES, TANGENT_MODES


def start_dragging(mode):
    from . import api
    return api.start_dragging(mode)


def execute_tween(mode, value, world_space=False, session=None):
    from . import api
    return api.execute_tween(mode, value, world_space=world_space, session=session)


def execute_blend_to_frame_with_button_values(value, session=None):
    from . import api
    return api.execute_blend_to_frame_with_button_values(value, session=session)


def execute_curve_modifier(mode, value, session=None):
    from . import api
    return api.execute_curve_modifier(mode, value, session=session)


def execute_tangent_blend(mode, value, session=None):
    from . import api
    return api.execute_tangent_blend(mode, value, session=session)


def stop_dragging(session=None):
    from . import api
    return api.stop_dragging(session=session)


__all__ = [
    "execute_tween",
    "execute_blend_to_frame_with_button_values",
    "execute_curve_modifier",
    "execute_tangent_blend",
    "start_dragging",
    "stop_dragging",
    "parse_tt",
    "TWEEN_MODES",
    "BLEND_MODES",
    "TANGENT_MODES",
]
