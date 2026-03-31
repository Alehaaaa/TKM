"""
TheKeyMachine - Sliders Configuration

Definitions of all slider modes, labels, and icons.
"""

try:
    from PySide6 import QtCore
except ImportError:
    from PySide2 import QtCore

import TheKeyMachine.mods.mediaMod as media


CTRL = QtCore.Qt.Key_Control
SHIFT = QtCore.Qt.Key_Shift
ALT = QtCore.Qt.Key_Alt
MID = QtCore.Qt.MiddleButton

TANGENT_MODES = [
    {
        "label": "Blend to Best Guess Tangent",
        "key": "blend_best_guess",
        "icon": media.asset_path("auto_tangent_image"),
        "shortcut": [CTRL, ALT],
        "description": "Blends the selected tangents toward a 'best guess' smooth orientation based on neighbors.",
    },
    {
        "label": "Blend to Polished Tangent",
        "key": "blend_polished",
        "icon": media.asset_path("spline_tangent_image"),
        "shortcut": [CTRL],
        "description": "Blends tangents toward a manual 'polished' curve look.",
    },
    {
        "label": "Blend to Flow Tangent",
        "key": "blend_flow",
        "icon": media.asset_path("flat_tangent_image"),
        "shortcut": [SHIFT],
        "description": "Adjusts tangents to create a natural flow between keyframes.",
    },
    {
        "label": "Blend to Bounce Tangent",
        "key": "blend_bounce",
        "icon": media.asset_path("bouncy_tangent_image"),
        "shortcut": [ALT],
        "description": "Sets tangents to create a sharp 'bounce' effect at the keyframe.",
    },
    {
        "label": "Blend to Auto Tangent",
        "key": "blend_auto",
        "icon": media.asset_path("auto_tangent_image"),
        "shortcut": [CTRL, SHIFT],
        "description": "Blends toward the standard Maya 'Auto' tangent type.",
    },
    {
        "label": "Blend to Spline Tangent",
        "key": "blend_spline",
        "icon": media.asset_path("spline_tangent_image"),
        "shortcut": [ALT, SHIFT],
        "description": "Blends toward the standard Maya 'Spline' tangent type.",
    },
    {
        "label": "Blend to Clamped Tangent",
        "key": "blend_clamped",
        "icon": media.asset_path("clamped_tangent_image"),
        "shortcut": [SHIFT, MID],
        "description": "Blends toward the standard Maya 'Clamped' tangent type.",
    },
    {
        "label": "Blend to Linear Tangent",
        "key": "blend_linear",
        "icon": media.asset_path("linear_tangent_image"),
        "shortcut": [CTRL, MID],
        "description": "Blends toward the standard Maya 'Linear' tangent type.",
    },
    {
        "label": "Blend to Flat Tangent",
        "key": "blend_flat",
        "icon": media.asset_path("flat_tangent_image"),
        "shortcut": [CTRL, ALT, SHIFT],
        "description": "Blends toward the standard Maya 'Flat' tangent type.",
    },
    {
        "label": "Blend to Plateau Tangent",
        "key": "blend_plateau",
        "icon": media.asset_path("plateau_tangent_image"),
        "shortcut": [ALT, MID],
        "description": "Blends toward the standard Maya 'Plateau' tangent type.",
    },
]

TWEEN_MODES = [
    {
        "label": "Tweener",
        "key": "tweener",
        "icon": "TW",
        "shortcut": [ALT],
        "description": "Classic tweener behavior, blending values between the previous and next keyframes.",
    },
    {
        "label": "Tweener World Space",
        "key": "tweener_worldspace",
        "icon": "TW",
        "shortcut": [ALT, MID],
        "description": "Performs tweening in World Space for more accurate spatial interpolations.",
        "worldSpace": True,
    },
    "separator",
    {
        "label": "Blend to Buffer",
        "key": "blend_to_buffer",
        "icon": "BB",
        "shortcut": [CTRL, ALT, SHIFT],
        "description": "Blends the current pose toward the pose stored in the buffer.",
    },
    {
        "label": "Blend to Default",
        "key": "blend_to_default",
        "icon": "BD",
        "shortcut": [ALT, SHIFT],
        "description": "Blends the current pose toward the object's default/bind pose.",
    },
    {
        "label": "Blend to Ease",
        "key": "blend_to_ease",
        "icon": "BE",
        "shortcut": [CTRL, SHIFT],
        "description": "Applies an ease in/out curve blending to the current value.",
    },
    {
        "label": "Blend to Frame",
        "key": "blend_to_frame",
        "icon": "BF",
        "frameButtons": True,
        "shortcut": [CTRL],
        "description": "Blends the current pose toward the values at a specific frame (user-defined).",
    },
    {
        "label": "Blend to Frame World Space",
        "key": "blend_to_frame_ws",
        "icon": "BF",
        "frameButtons": True,
        "shortcut": [CTRL, MID],
        "description": "Blends toward a specific frame value using World Space coordinates.",
        "worldSpace": True,
    },
    {
        "label": "Blend to Neighbors",
        "key": "blend_to_neighbors",
        "icon": "BN",
        "shortcut": [SHIFT],
        "description": "Blends values toward the immediate previous or next keyframe neighbor.",
    },
    {
        "label": "Blend to Neighbors World Space",
        "key": "blend_to_neighbors_ws",
        "icon": "BN",
        "shortcut": [SHIFT, MID],
        "description": "Blends toward neighbors using World Space coordinates.",
        "worldSpace": True,
    },
    {
        "label": "Blend to Infinity",
        "key": "blend_to_infinity",
        "icon": "BI",
        "shortcut": [CTRL, ALT],
        "description": "Blends the pose toward the pre-infinity or post-infinity value.",
    },
    {
        "label": "Blend to Infinity World Space",
        "key": "blend_to_infinity_ws",
        "icon": "BI",
        "shortcut": [CTRL, ALT, MID],
        "description": "Blends toward infinity values in World Space.",
        "worldSpace": True,
    },
    {
        "label": "Blend to Undo",
        "key": "blend_to_undo",
        "icon": "BU",
        "shortcut": [CTRL, SHIFT, MID],
        "description": "Blends the current pose back toward the state before the slider interaction started.",
    },
]

BLEND_MODES = [
    {
        "label": "Connect to Neighbors",
        "key": "connect_neighbors",
        "icon": "CN",
        "shortcut": [CTRL, SHIFT, MID],
        "description": "Smoothly connects the current curve selection to its surrounding neighbors.",
    },
    {
        "label": "Ease In | Out",
        "key": "ease_in_out",
        "icon": "EI",
        "shortcut": [CTRL, SHIFT],
        "description": "Applies an ease-in/ease-out transformation to the selected curve segment.",
    },
    {
        "label": "Gap Stitcher",
        "key": "gap_stitcher",
        "icon": "GS",
        "shortcut": [CTRL, MID],
        "description": "Closes gaps in animation by stitching curve segments together.",
    },
    {
        "label": "Noise | Wave",
        "key": "noise_wave",
        "icon": "NW",
        "shortcut": [CTRL, ALT, SHIFT, MID],
        "description": "Adds procedural noise (drag left) or sine waves (drag right) to the curve.",
    },
    {
        "label": "Pull | Push",
        "key": "pull_push",
        "icon": "PP",
        "shortcut": [ALT],
        "description": "Pulls keys toward the average value or pushes them away for exaggerating motion.",
    },
    {
        "label": "Simplify | Bake Keys",
        "key": "simplify_bake",
        "icon": "SB",
        "shortcut": [CTRL, ALT, SHIFT],
        "description": "Reduces keyframe density (Simplify) or adds keys to every frame (Bake).",
    },
    {
        "label": "Smooth | Rough",
        "key": "smooth_rough",
        "icon": "SR",
        "shortcut": [SHIFT],
        "description": "Smooths the curve (drag left) or adds jittery roughness (drag right).",
    },
    {
        "label": "Time Offsetter",
        "key": "time_offsetter",
        "icon": "TO",
        "shortcut": [CTRL, ALT],
        "description": "Shifts the timing of the selected keyframes forward or backward.",
    },
    {
        "label": "Time Offsetter Stagger",
        "key": "time_offsetter_stagger",
        "icon": "TS",
        "shortcut": [CTRL, ALT, MID],
        "description": "Applies a staggered time offset across multiple selected objects.",
    },
    "separator",
    {
        "label": "Scale From Average",
        "key": "scale_average",
        "icon": "SA",
        "shortcut": [ALT, SHIFT, MID],
        "description": "Scales the curve values relative to their average value.",
    },
    {
        "label": "Scale From Default",
        "key": "scale_default",
        "icon": "SD",
        "shortcut": [ALT, SHIFT],
        "description": "Scales the curve values relative to the default zero-point.",
    },
    {
        "label": "Scale From Frame",
        "key": "scale_frame",
        "icon": "SF",
        "shortcut": [CTRL],
        "frameButtons": True,
        "description": "Scales the curve relative to the value at the current frame.",
    },
    {
        "label": "Scale From Neighbor Left",
        "key": "scale_neighbor_left",
        "icon": "SL",
        "shortcut": [SHIFT, MID],
        "description": "Scales the curve relative to the value of the left neighbor keyframe.",
    },
    {
        "label": "Scale From Neighbor Right",
        "key": "scale_neighbor_right",
        "icon": "SRi",
        "shortcut": [ALT, MID],
        "description": "Scales the curve relative to the value of the right neighbor keyframe.",
    },
]
