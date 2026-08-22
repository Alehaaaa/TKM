"""

TheKeyMachine - Animation Toolset for Maya Animators


This file is part of TheKeyMachine, an open source software for Autodesk Maya licensed under the GNU General Public License v3.0 (GPL-3.0).
You are free to use, modify, and distribute this code under the terms of the GPL-3.0 license.
By using this code, you agree to keep it open source and share any modifications.
This code is provided "as is," without any warranty. For the full license text, visit https://www.gnu.org/licenses/gpl-3.0.html

https://alehaaaa.github.io/TKM/

Modified by: Alehaaaa / alehaaaa.github.io



"""

"""External entry points for the Animation Layers window.

Mirrors ``tools.attribute_switcher.api``: a module-level singleton window,
a ``WindowStateBus`` for toolbar-button sync, and a ``ToolbarWindowToggle``
so hotkeys/shelf/search and the toolbar button all open/close the same
instance through the standard ``tool_operation()`` dispatch boundary.
"""

from TheKeyMachine.core.Qt import QtCore, QtGui, QtWidgets  # type: ignore

from TheKeyMachine.data import icons
from TheKeyMachine.core import settings
from TheKeyMachine.core import runtime
from TheKeyMachine.tools import common as toolCommon
from TheKeyMachine.tools.common import ToolbarWindowToggle
from TheKeyMachine.tools.animation_layers import controller
from TheKeyMachine.ui.widgets import customWidgets as widgets, util as wutil

__all__ = [
    "animation_layers_window",
    "close_animation_layers_window",
    "toggle_window",
    "show",
    "popup",
    "is_stay_on_top",
    "set_stay_on_top",
    "bind_animation_layers_toolbar_button",
    "smart_merge_selected_layers",
    "export_selected_layers",
    "import_layers_file",
]

SETTINGS_NAMESPACE = "animation_layers"
STAYS_ON_TOP_KEY = "stays_on_top"
AUTO_TRANSPARENCY_KEY = "auto_transparency"

_animation_layers_instance = None
animation_layers_window_bus = toolCommon.WindowStateBus()


def _window_class():
    from TheKeyMachine.tools.animation_layers.widgets import AnimationLayersWindow

    return AnimationLayersWindow


def _emit_animation_layers_window_state(is_open):
    state = bool(is_open)
    try:
        animation_layers_window_bus.stateChanged.emit(state)
    except Exception:
        pass
    runtime.get_runtime_manager().set_tool_state("animation_layers", state)


def is_stay_on_top():
    return settings.get_setting(STAYS_ON_TOP_KEY, False, namespace=SETTINGS_NAMESPACE)


def is_auto_transparency_enabled():
    return settings.get_setting(AUTO_TRANSPARENCY_KEY, False, namespace=SETTINGS_NAMESPACE)


def set_auto_transparency_enabled(enabled):
    settings.set_setting(AUTO_TRANSPARENCY_KEY, bool(enabled), namespace=SETTINGS_NAMESPACE)
    dlg = get_animation_layers_window()
    if dlg and wutil.is_valid_widget(dlg):
        dlg._auto_transparency = bool(enabled)
        dlg.update_transparency_state(False)


def set_stay_on_top(enabled):
    settings.set_setting(STAYS_ON_TOP_KEY, bool(enabled), namespace=SETTINGS_NAMESPACE)
    dlg = get_animation_layers_window()
    if dlg and wutil.is_valid_widget(dlg):
        dlg.setWindowFlag(QtCore.Qt.WindowStaysOnTopHint, bool(enabled))
        dlg.show()
        dlg.raise_()
        dlg.activateWindow()


def get_animation_layers_window():
    global _animation_layers_instance
    if _animation_layers_instance and wutil.is_valid_widget(_animation_layers_instance):
        return _animation_layers_instance
    _animation_layers_instance = None
    return None


def is_animation_layers_window_open():
    dlg = get_animation_layers_window()
    return bool(dlg and dlg.isVisible())


def close_animation_layers_window():
    dlg = get_animation_layers_window()
    if dlg and wutil.is_valid_widget(dlg):
        dlg.close()
    _emit_animation_layers_window_state(False)


def animation_layers_window(reuse_existing=True, popup=False, anchor_button=None):
    global _animation_layers_instance
    dlg = get_animation_layers_window()
    if not (reuse_existing and dlg and wutil.is_valid_widget(dlg)):
        close_animation_layers_window()
        dlg = _window_class()(parent=wutil.get_maya_qt(qt=QtWidgets.QWidget), popup=popup)

        created_dialog = dlg

        def _on_destroyed(*_):
            global _animation_layers_instance
            if _animation_layers_instance is not created_dialog:
                return
            _animation_layers_instance = None
            _emit_animation_layers_window_state(False)

        dlg.destroyed.connect(_on_destroyed)
        _animation_layers_instance = dlg
    else:
        dlg.refresh()

    dlg.setWindowFlag(QtCore.Qt.WindowStaysOnTopHint, is_stay_on_top())
    if anchor_button and wutil.is_valid_widget(anchor_button):
        dlg.present_above_toolbar_button(anchor_button)
    elif popup:
        dlg.present_beside_cursor()
    else:
        dlg.present_floating_window()

    _emit_animation_layers_window_state(True)
    return dlg


animation_layers_toolbar_toggle = ToolbarWindowToggle(
    is_animation_layers_window_open,
    lambda anchor_button=None: animation_layers_window(
        reuse_existing=True,
        popup=False,
        anchor_button=anchor_button,
    ),
    close_animation_layers_window,
    animation_layers_window_bus.stateChanged,
    tool_id="animation_layers",
)


def _refresh_open_window():
    dlg = get_animation_layers_window()
    if dlg and wutil.is_valid_widget(dlg):
        dlg.refresh()


def smart_merge_selected_layers(*_args):
    """Toolbar-button/shortcut/menu quick action -- bakes the layers
    currently selected in the scene (see ``controller.selected_layer_names``)
    without needing the Animation Layers window open first."""
    layer_names = controller.selected_layer_names()
    if len(layer_names) < 2:
        wutil.make_inViewMessage("Select two or more animation layers to merge")
        return
    try:
        with toolCommon.tool_operation(
            tool_id="animation_layers_merge",
            label="Smart Merge Animation Layers",
            undo=True,
            progress=True,
        ) as operation:
            operation.start()
            controller.smart_merge_layers(layer_names, operation=operation)
    except RuntimeError as exc:
        wutil.make_inViewMessage(str(exc))
        return
    _refresh_open_window()


def export_selected_layers(*_args):
    layer_names = controller.selected_layer_names()
    if not layer_names:
        wutil.make_inViewMessage("Select one or more animation layers to export")
        return
    with toolCommon.tool_operation(tool_id="animation_layers_export", label="Export Animation Layers", undo=False) as operation:
        try:
            controller.export_selected(layer_names, operation=operation)
        except RuntimeError as exc:
            wutil.make_inViewMessage(str(exc))


def import_layers_file(*_args):
    try:
        with toolCommon.tool_operation(tool_id="animation_layers_import", label="Import Animation Layers", undo=True) as operation:
            controller.import_from_file(operation=operation)
    except RuntimeError as exc:
        wutil.make_inViewMessage(str(exc))
        return
    _refresh_open_window()


def build_animation_layers_context_menu(parent=None):
    menu = widgets.OpenMenuWidget(parent)

    menu.addAction(
        QtGui.QIcon(icons.get("layer_merge")),
        "Smart Merge Selected",
        description="Bake the selected layers together, sampling only the frames where they actually have weight.",
    ).triggered.connect(lambda *_: smart_merge_selected_layers())

    menu.addSeparator()

    menu.addAction(
        QtGui.QIcon(icons.get("export")),
        "Export Selected",
        description="Export the selected layers (and their animation) to a file.",
    ).triggered.connect(lambda *_: export_selected_layers())

    menu.addAction(
        QtGui.QIcon(icons.get("import")),
        "Import",
        description="Import previously exported animation layers.",
    ).triggered.connect(lambda *_: import_layers_file())

    menu.addSeparator()

    toolCommon.add_floating_window_actions(
        menu,
        is_stay_on_top,
        set_stay_on_top,
    )
    return menu


def bind_animation_layers_toolbar_button(button):
    button.connect_window_toggle(
        animation_layers_toolbar_toggle,
        context_attr="_tkm_animation_layers_context_menu_slot",
        menu_factory=lambda parent: build_animation_layers_context_menu(parent=parent),
    )
    return True


def toggle_window(checked=None, *_args):
    if isinstance(checked, bool):
        return (
            animation_layers_window(reuse_existing=True, popup=False)
            if checked
            else close_animation_layers_window()
        )
    if animation_layers_toolbar_toggle:
        return animation_layers_toolbar_toggle.toggle()
    elif is_animation_layers_window_open():
        return close_animation_layers_window()
    return animation_layers_window(reuse_existing=True, popup=False)


def show():
    return animation_layers_window(reuse_existing=True, popup=False)


def popup():
    return animation_layers_window(reuse_existing=True, popup=True)
