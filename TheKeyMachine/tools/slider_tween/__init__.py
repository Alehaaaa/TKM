from TheKeyMachine.core.Qt import QtCore  # type: ignore
from TheKeyMachine.core.toolbox import ToolObject, load_tooltips
from TheKeyMachine.data import colors as toolColors
from TheKeyMachine.sliders import SliderMode


TOOLTIPS = load_tooltips(__file__)
CTRL = QtCore.Qt.Key_Control
SHIFT = QtCore.Qt.Key_Shift
ALT = QtCore.Qt.Key_Alt
MID = QtCore.Qt.MiddleButton


MODES = [
    SliderMode("tweener", "Tweener", "TW", (ALT,), tooltip=TOOLTIPS["tweener"]),
    SliderMode("tweener_worldspace", "Tweener World Space", "TW", (ALT, MID), tooltip=TOOLTIPS["tweener_worldspace"], world_space=True),
    "separator",
    SliderMode("blend_to_buffer", "Blend to Buffer", "BB", (CTRL, ALT, SHIFT), tooltip=TOOLTIPS["blend_to_buffer"]),
    SliderMode("blend_to_default", "Blend to Default", "BD", (ALT, SHIFT), tooltip=TOOLTIPS["blend_to_default"]),
    SliderMode("blend_to_ease", "Blend to Ease", "BE", (CTRL, SHIFT), tooltip=TOOLTIPS["blend_to_ease"]),
    SliderMode("blend_to_frame", "Blend to Frame", "BF", (CTRL,), tooltip=TOOLTIPS["blend_to_frame"], frame_buttons=True),
    SliderMode("blend_to_frame_ws", "Blend to Frame World Space", "BF", (CTRL, MID), tooltip=TOOLTIPS["blend_to_frame_ws"], world_space=True, frame_buttons=True),
    SliderMode("blend_to_neighbors", "Blend to Neighbors", "BN", (SHIFT,), tooltip=TOOLTIPS["blend_to_neighbors"]),
    SliderMode("blend_to_neighbors_ws", "Blend to Neighbors World Space", "BN", (SHIFT, MID), tooltip=TOOLTIPS["blend_to_neighbors_ws"], world_space=True),
    SliderMode("blend_to_infinity", "Blend to Infinity", "BI", (CTRL, ALT), tooltip=TOOLTIPS["blend_to_infinity"]),
    SliderMode("blend_to_infinity_ws", "Blend to Infinity World Space", "BI", (CTRL, ALT, MID), tooltip=TOOLTIPS["blend_to_infinity_ws"], world_space=True),
    SliderMode("blend_to_undo", "Blend to Undo", "BU", (CTRL, SHIFT, MID), tooltip=TOOLTIPS["blend_to_undo"]),
]

from TheKeyMachine.tools.slider_tween import widgets


class TweenSliderToolObject(ToolObject):
    ORDER = 370
    SECTION = {
        "id": "slider_tween",
        "label": "Tween Sliders",
        "color": toolColors.TOOLBAR_YELLOW,
        "icon_color": toolColors.SLIDER_ICON_YELLOW,
        "type": "slider",
        "slider_type": "tween",
        "modes": MODES,
        "section_factory": widgets.create_section,
    }
