from TheKeyMachine.core.Qt import QtCore  # type: ignore
from TheKeyMachine.core.toolbox import ToolObject, load_tooltips
from TheKeyMachine.data.colors import COLORS
from TheKeyMachine.tools.sliders import SliderMode


TOOLTIPS = load_tooltips(__file__)
CTRL = QtCore.Qt.Key_Control
SHIFT = QtCore.Qt.Key_Shift
ALT = QtCore.Qt.Key_Alt
MID = QtCore.Qt.MiddleButton


MODES = [
    SliderMode("connect_neighbors", "Connect to Neighbors", "CN", (CTRL, SHIFT, MID), tooltip=TOOLTIPS["connect_neighbors"]),
    SliderMode("ease_in_out", "Ease In | Out", "EI", (CTRL, SHIFT), tooltip=TOOLTIPS["ease_in_out"]),
    SliderMode("gap_stitcher", "Gap Stitcher", "GS", (CTRL, MID), tooltip=TOOLTIPS["gap_stitcher"]),
    SliderMode("noise_wave", "Noise | Wave", "NW", (CTRL, ALT, SHIFT, MID), tooltip=TOOLTIPS["noise_wave"]),
    SliderMode("pull_push", "Pull | Push", "PP", (ALT,), tooltip=TOOLTIPS["pull_push"]),
    SliderMode("simplify_bake", "Simplify | Bake Keys", "SB", (CTRL, ALT, SHIFT), tooltip=TOOLTIPS["simplify_bake"]),
    SliderMode("smooth_rough", "Smooth | Rough", "SR", (SHIFT,), tooltip=TOOLTIPS["smooth_rough"]),
    SliderMode("time_offsetter", "Time Offsetter", "TO", (CTRL, ALT), tooltip=TOOLTIPS["time_offsetter"]),
    SliderMode("time_offsetter_stagger", "Time Offsetter Stagger", "TS", (CTRL, ALT, MID), tooltip=TOOLTIPS["time_offsetter_stagger"]),
    "separator",
    SliderMode("scale_average", "Scale From Average", "SA", (ALT, SHIFT, MID), tooltip=TOOLTIPS["scale_average"]),
    SliderMode("scale_default", "Scale From Default", "SD", (ALT, SHIFT), tooltip=TOOLTIPS["scale_default"]),
    SliderMode("scale_frame", "Scale From Frame", "SF", (CTRL,), tooltip=TOOLTIPS["scale_frame"], frame_buttons=True),
    SliderMode("scale_neighbor_left", "Scale From Neighbor Left", "SL", (SHIFT, MID), tooltip=TOOLTIPS["scale_neighbor_left"]),
    SliderMode("scale_neighbor_right", "Scale From Neighbor Right", "SR", (ALT, MID), tooltip=TOOLTIPS["scale_neighbor_right"]),
]

from TheKeyMachine.tools.slider_blend import widgets


class BlendSliderToolObject(ToolObject):
    ORDER = 360
    SECTION = {
        "id": "slider_blend",
        "label": "Blend Sliders",
        "icon": "slider_blend/connect_neighbors",
        "color": COLORS.toolbar.green.hex,
        "icon_color": COLORS.ui.green.hex,
        "type": "slider",
        "slider_type": "blend",
        "modes": MODES,
        "section_factory": widgets.create_section,
    }
