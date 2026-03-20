"""
TheKeyMachine - Sliders Configuration

Definitions of all slider modes, labels, and icons.
"""

TANGENT_MODES = [
    {
        "label": "Blend to Best Guess Tangent",
        "key": "blend_best_guess",
        "icon": "BG",
        "description": "Blends the selected tangents toward a 'best guess' smooth orientation based on neighbors.",
    },
    {
        "label": "Blend to Polished Tangent",
        "key": "blend_polished",
        "icon": "PO",
        "description": "Blends tangents toward a manual 'polished' curve look.",
    },
    {
        "label": "Blend to Flow Tangent",
        "key": "blend_flow",
        "icon": "FL",
        "description": "Adjusts tangents to create a natural flow between keyframes.",
    },
    {
        "label": "Blend to Bounce Tangent",
        "key": "blend_bounce",
        "icon": "BO",
        "description": "Sets tangents to create a sharp 'bounce' effect at the keyframe.",
    },
    {"label": "Blend to Auto Tangent", "key": "blend_auto", "icon": "AU", "description": "Blends toward the standard Maya 'Auto' tangent type."},
    {
        "label": "Blend to Spline Tangent",
        "key": "blend_spline",
        "icon": "SP",
        "description": "Blends toward the standard Maya 'Spline' tangent type.",
    },
    {
        "label": "Blend to Clamped Tangent",
        "key": "blend_clamped",
        "icon": "CL",
        "description": "Blends toward the standard Maya 'Clamped' tangent type.",
    },
    {
        "label": "Blend to Linear Tangent",
        "key": "blend_linear",
        "icon": "LI",
        "description": "Blends toward the standard Maya 'Linear' tangent type.",
    },
    {"label": "Blend to Flat Tangent", "key": "blend_flat", "icon": "FT", "description": "Blends toward the standard Maya 'Flat' tangent type."},
    {
        "label": "Blend to Plateau Tangent",
        "key": "blend_plateau",
        "icon": "PT",
        "description": "Blends toward the standard Maya 'Plateau' tangent type.",
    },
]

TWEEN_MODES = [
    {
        "label": "Tweener",
        "key": "tweener",
        "icon": "TW",
        "description": "Classic tweener behavior, blending values between the previous and next keyframes.",
    },
    {
        "label": "Tweener World Space",
        "key": "tweener_worldspace",
        "icon": "TW",
        "description": "Performs tweening in world space for more accurate spatial interpolations.",
    },
    "separator",
    {
        "label": "Blend to Buffer",
        "key": "blend_to_buffer",
        "icon": "BB",
        "description": "Blends the current pose toward the pose stored in the buffer.",
    },
    {
        "label": "Blend to Default",
        "key": "blend_to_default",
        "icon": "BD",
        "description": "Blends the current pose toward the object's default/bind pose.",
    },
    {"label": "Blend to Ease", "key": "blend_to_ease", "icon": "BE", "description": "Applies an ease in/out curve blending to the current value."},
    {
        "label": "Blend to Frame",
        "key": "blend_to_frame",
        "icon": "BF",
        "description": "Blends the current pose toward the values at a specific frame (user-defined).",
    },
    {
        "label": "Blend to Frame World Space",
        "key": "blend_to_frame_ws",
        "icon": "BF",
        "description": "Blends toward a specific frame value using world space coordinates.",
    },
    {
        "label": "Blend to Neighbors",
        "key": "blend_to_neighbors",
        "icon": "BN",
        "description": "Blends values toward the immediate previous or next keyframe neighbor.",
    },
    {
        "label": "Blend to Neighbors World Space",
        "key": "blend_to_neighbors_ws",
        "icon": "BN",
        "description": "Blends toward neighbors using world space coordinates.",
    },
    {
        "label": "Blend to Infinity",
        "key": "blend_to_infinity",
        "icon": "BI",
        "description": "Blends the pose toward the pre-infinity or post-infinity value.",
    },
    {
        "label": "Blend to Infinity World Space",
        "key": "blend_to_infinity_ws",
        "icon": "BI",
        "description": "Blends toward infinity values in world space.",
    },
    {
        "label": "Blend to Undo",
        "key": "blend_to_undo",
        "icon": "BU",
        "description": "Blends the current pose back toward the state before the slider interaction started.",
    },
]

BLEND_MODES = [
    {
        "label": "Connect to Neighbors",
        "key": "connect_neighbors",
        "icon": "CN",
        "description": "Smoothly connects the current curve selection to its surrounding neighbors.",
    },
    {
        "label": "Ease In | Out",
        "key": "ease_in_out",
        "icon": "EI",
        "description": "Applies an ease-in/ease-out transformation to the selected curve segment.",
    },
    {"label": "Gap Stitcher", "key": "gap_stitcher", "icon": "GS", "description": "Closes gaps in animation by stitching curve segments together."},
    {
        "label": "Noise | Wave",
        "key": "noise_wave",
        "icon": "NW",
        "description": "Adds procedural noise (drag left) or sine waves (drag right) to the curve.",
    },
    {
        "label": "Pull | Push",
        "key": "pull_push",
        "icon": "PP",
        "description": "Pulls keys toward the average value or pushes them away for exaggerating motion.",
    },
    {
        "label": "Simplify | Bake Keys",
        "key": "simplify_bake",
        "icon": "SB",
        "description": "Reduces keyframe density (Simplify) or adds keys to every frame (Bake).",
    },
    {
        "label": "Smooth | Rough",
        "key": "smooth_rough",
        "icon": "SR",
        "description": "Smooths the curve (drag left) or adds jittery roughness (drag right).",
    },
    {
        "label": "Time Offsetter",
        "key": "time_offsetter",
        "icon": "TO",
        "description": "Shifts the timing of the selected keyframes forward or backward.",
    },
    {
        "label": "Time Offsetter Stagger",
        "key": "time_offsetter_stagger",
        "icon": "TS",
        "description": "Applies a staggered time offset across multiple selected objects.",
    },
    "separator",
    {"label": "Scale From Average", "key": "scale_average", "icon": "SA", "description": "Scales the curve values relative to their average value."},
    {
        "label": "Scale From Default",
        "key": "scale_default",
        "icon": "SD",
        "description": "Scales the curve values relative to the default zero-point.",
    },
    {"label": "Scale From Frame", "key": "scale_frame", "icon": "SF", "description": "Scales the curve relative to the value at the current frame."},
    {
        "label": "Scale From Neighbor Left",
        "key": "scale_neighbor_left",
        "icon": "SL",
        "description": "Scales the curve relative to the value of the left neighbor keyframe.",
    },
    {
        "label": "Scale From Neighbor Right",
        "key": "scale_neighbor_right",
        "icon": "SRi",
        "description": "Scales the curve relative to the value of the right neighbor keyframe.",
    },
]
