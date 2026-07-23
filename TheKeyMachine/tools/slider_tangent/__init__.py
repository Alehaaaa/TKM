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
    SliderMode("blend_best_guess", "Blend to Best Guess Tangent", shortcut=(CTRL, ALT), icon="slider_tangent/tangent_auto", tooltip=TOOLTIPS["blend_best_guess"]),
    SliderMode("blend_polished", "Blend to Polished Tangent", shortcut=(CTRL,), icon="slider_tangent/tangent_spline", tooltip=TOOLTIPS["blend_polished"]),
    SliderMode("blend_flow", "Blend to Flow Tangent", shortcut=(SHIFT,), icon="slider_tangent/tangent_flat", tooltip=TOOLTIPS["blend_flow"]),
    SliderMode("blend_bounce", "Blend to Bounce Tangent", shortcut=(ALT,), icon="slider_tangent/tangent_bouncy", tooltip=TOOLTIPS["blend_bounce"]),
    SliderMode("blend_auto", "Blend to Auto Tangent", shortcut=(CTRL, SHIFT), icon="slider_tangent/tangent_auto", tooltip=TOOLTIPS["blend_auto"]),
    SliderMode("blend_spline", "Blend to Spline Tangent", shortcut=(ALT, SHIFT), icon="slider_tangent/tangent_spline", tooltip=TOOLTIPS["blend_spline"]),
    SliderMode("blend_clamped", "Blend to Clamped Tangent", shortcut=(SHIFT, MID), icon="slider_tangent/tangent_clamped", tooltip=TOOLTIPS["blend_clamped"]),
    SliderMode("blend_linear", "Blend to Linear Tangent", shortcut=(CTRL, MID), icon="slider_tangent/tangent_linear", tooltip=TOOLTIPS["blend_linear"]),
    SliderMode("blend_flat", "Blend to Flat Tangent", shortcut=(CTRL, ALT, SHIFT), icon="slider_tangent/tangent_flat", tooltip=TOOLTIPS["blend_flat"]),
    SliderMode("blend_plateau", "Blend to Plateau Tangent", shortcut=(ALT, MID), icon="slider_tangent/tangent_plateau", tooltip=TOOLTIPS["blend_plateau"]),
]

from TheKeyMachine.tools.slider_tangent import widgets


class TangentSliderToolObject(ToolObject):
    ORDER = 380
    SECTION = {
        "id": "slider_tangent",
        "label": "Tangent Sliders",
        "icon": "slider_tangent/tangent_auto",
        "color": COLORS.toolbar.orange.hex,
        "icon_color": COLORS.ui.orange.hex,
        "type": "slider",
        "slider_type": "tangent",
        "modes": MODES,
        "section_factory": widgets.create_section,
    }
