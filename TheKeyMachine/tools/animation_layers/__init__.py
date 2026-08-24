"""

TheKeyMachine - Animation Toolset for Maya Animators


This file is part of TheKeyMachine, an open source software for Autodesk Maya licensed under the GNU General Public License v3.0 (GPL-3.0).
You are free to use, modify, and distribute this code under the terms of the GPL-3.0 license.
By using this code, you agree to keep it open source and share any modifications.
This code is provided "as is," without any warranty. For the full license text, visit https://www.gnu.org/licenses/gpl-3.0.html

https://alehaaaa.github.io/TKM/

Modified by: Alehaaaa / alehaaaa.github.io



"""

from TheKeyMachine.core.Qt import QtCore  # type: ignore

from TheKeyMachine.tools.registry import ToolObject, load_tooltips
from TheKeyMachine.data.colors import COLORS
from TheKeyMachine.tools.animation_layers import api


TOOLTIPS = load_tooltips(__file__)


class AnimationLayersToolObject(ToolObject):
    ORDER = 850
    TOOLS = {
        "animation_layers": {
            "type": "check",
            "state_key": "animation_layers",
            "label": "Animation Layers",
            "text": "Lyr",
            "icon": "animation_layers",
            "callback": api.toggle_window,
            "get_checked": api.is_animation_layers_window_open,
            "set_checked": api.toggle_window,
            "bind_checked_fn": api.bind_animation_layers_toolbar_button,
            "tooltip": TOOLTIPS["animation_layers"],
        },
        "animation_layers_smart_merge": {
            "type": "tool", "label": "Smart Merge Selected", "text": "Mrg",
            "icon": "layer_merge", "callback": api.smart_merge_selected_layers,
            "tooltip": TOOLTIPS["smart_merge"],
        },
        "animation_layers_export": {
            "type": "tool", "label": "Export", "text": "Ex",
            "icon": "export", "callback": api.export_selected_layers,
            "tooltip": TOOLTIPS["export"],
            "operation": {"undo": False},
        },
        "animation_layers_import": {
            "type": "tool", "label": "Import", "text": "Im",
            "icon": "import", "callback": api.import_layers_file,
            "tooltip": TOOLTIPS["import"],
        },
    }
    SECTION = {
        "id": "animation_layer_tools", "i18n_key": "animation_layers",
        "label": "Animation Layers",
        "color": COLORS.toolbar.turquoise.hex,
        "items": [
            {"id": "animation_layers", "shortcuts": [
                {"id": "animation_layers_smart_merge", "keys": [QtCore.Qt.Key_Control]},
                {"id": "animation_layers_export", "keys": [QtCore.Qt.Key_Alt]},
                {"id": "animation_layers_import", "keys": [QtCore.Qt.Key_Control, QtCore.Qt.Key_Alt]},
            ]},
            {"id": "animation_layers_smart_merge"},
            {"id": "animation_layers_export"},
            {"id": "animation_layers_import"},
        ],
    }
