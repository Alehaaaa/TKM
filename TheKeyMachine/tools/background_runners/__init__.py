from TheKeyMachine.tools.registry import ToolObject, load_tooltips
from TheKeyMachine.data.colors import COLORS
from TheKeyMachine.tools.background_runners import api


TOOLTIPS = load_tooltips(__file__)


class BackgroundRunnersToolObject(ToolObject):
    ORDER = 980
    TOOLS = {
        "background_runners": {
            "type": "menu", "label": "Background Runners", "icon": "background_runners_0",
            "callback": api.show_menu, "menu": api.build_menu,
            "tooltip": TOOLTIPS["background_runners"],
            "keywords": ["background services", "automatic task runners"],
        },
        "background_runner_channelbox_selection_highlight": {
            "type": "tool", "label": "Channel Box Selection Timeline Highlight",
            "callback": api.toggle_channelbox_selection_highlight,
            "tooltip": TOOLTIPS["channelbox_selection_highlight"],
            "keywords": ["channelbox selection timeline highlight", "attribute editor selection selection timeline highlight"],
        },
        "background_runner_channelbox_clear_on_selection_change": {
            "type": "tool", "label": "Channel Box Clear Selection",
            "callback": api.toggle_channelbox_clear_on_selection_change,
            "tooltip": TOOLTIPS["channelbox_clear_on_selection_change"],
            "keywords": ["channelbox clear selection", "attribute editor selection clear selection"],
        },
        "background_runner_camera_orbit_selection": {
            "type": "tool", "label": "Camera Orbit Selection",
            "callback": api.toggle_camera_orbit_selection,
            "tooltip": TOOLTIPS["camera_orbit_selection"],
            "keywords": ["camera orbit pickion", "camera orbit chooseion"],
        },
        "hide_static_animation_curves": {
            "type": "tool", "label": "Auto Hide Static Animation Curves",
            "callback": api.toggle_hide_static_animation_curves,
            "tooltip": TOOLTIPS["hide_static_animation_curves"],
            "keywords": ["auto hide static motion curves", "auto hide static keyframe animation curves"],
        },
        "background_runner_animation_recovery": {
            "type": "tool", "label": "Animation Recovery",
            "callback": api.toggle_animation_recovery,
            "tooltip": TOOLTIPS["animation_recovery"],
            "keywords": ["automatic animation recovery", "background animation backup"],
        },
        "background_runner_anim_layer_weights": {
            "type": "tool", "label": "Anim Layer Weights",
            "callback": api.toggle_anim_layer_weights,
            "tooltip": TOOLTIPS["anim_layer_weights"],
            "keywords": ["background runner anim layer anim layer weights", "anim layer weights command"],
        },
        "background_runner_selector_toolbar_pin": {
            "type": "tool", "label": "Selected Object Display",
            "callback": api.toggle_selector_toolbar_pin,
            "tooltip": TOOLTIPS["selector_toolbar_pin"],
            "keywords": ["picked object toolbar display", "chosen control indicator"],
        },
    }
    SECTION = {
        "id": "background_runner_tools", "i18n_key": "background_runners",
        "label": "Background Runners",
        "color": COLORS.toolbar.light_gray.hex,
        "items": [{"id": "background_runners"}],
    }
