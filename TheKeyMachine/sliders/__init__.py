"""
TheKeyMachine Sliders Module: A unified system for managing Tween, Blend, and Curve sliders.
"""

from .manager import execute_tween, execute_curve_modifier, execute_tangent_blend
from .utils import stop_dragging
from TheKeyMachine.tooltips import parse_tt
from .config import TWEEN_MODES, BLEND_MODES, TANGENT_MODES


__all__ = [
    "execute_tween",
    "execute_curve_modifier",
    "execute_tangent_blend",
    "stop_dragging",
    "parse_tt",
    "TWEEN_MODES",
    "BLEND_MODES",
    "TANGENT_MODES",
]
