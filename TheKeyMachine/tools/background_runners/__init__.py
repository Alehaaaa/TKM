from TheKeyMachine.core.toolbox import ToolObject, load_tooltips
from TheKeyMachine.tools.background_runners import api


TOOLTIPS = load_tooltips(__file__)


class BackgroundRunnersToolObject(ToolObject):
    ORDER = 980
    TOOLS = {
        "background_runners": {
            "type": "menu", "label": "Background Runners", "icon": "background_runners_0",
            "callback": api.show_menu, "menu": api.build_menu,
            "tooltip": TOOLTIPS["background_runners"],
        },
        "background_runner_channelbox_selection_highlight": {
            "type": "tool", "label": "Channel Box Selection Timeline Highlight",
            "callback": api.toggle_channelbox_selection_highlight,
            "tooltip": TOOLTIPS["channelbox_selection_highlight"],
        },
        "background_runner_channelbox_clear_on_selection_change": {
            "type": "tool", "label": "Channel Box Clear Selection",
            "callback": api.toggle_channelbox_clear_on_selection_change,
            "tooltip": TOOLTIPS["channelbox_clear_on_selection_change"],
        },
        "background_runner_camera_orbit_selection": {
            "type": "tool", "label": "Camera Orbit Selection",
            "callback": api.toggle_camera_orbit_selection,
            "tooltip": TOOLTIPS["camera_orbit_selection"],
        },
        "hide_static_animation_curves": {
            "type": "tool", "label": "Auto Hide Static Animation Curves",
            "callback": api.toggle_hide_static_animation_curves,
            "tooltip": TOOLTIPS["hide_static_animation_curves"],
        },
        "background_runner_animation_recovery": {
            "type": "tool", "label": "Animation Recovery",
            "callback": api.toggle_animation_recovery,
            "tooltip": TOOLTIPS["animation_recovery"],
        },
        "background_runner_anim_layer_weights": {
            "type": "tool", "label": "Anim Layer Weights",
            "callback": api.toggle_anim_layer_weights,
            "tooltip": TOOLTIPS["anim_layer_weights"],
        },
        "background_runner_selector_toolbar_pin": {
            "type": "tool", "label": "Selected Object Display",
            "callback": api.toggle_selector_toolbar_pin,
            "tooltip": TOOLTIPS["selector_toolbar_pin"],
        },
    }
    SECTION = {
        "id": "background_runner_tools",
        "label": "Background Runners",
        "items": [{"id": "background_runners"}],
    }
