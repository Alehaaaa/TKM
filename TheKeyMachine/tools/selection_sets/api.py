import os


try:
    from PySide2 import QtCore, QtGui, QtWidgets
except ImportError:
    from PySide6 import QtCore, QtGui, QtWidgets

import TheKeyMachine.mods.generalMod as general
import TheKeyMachine.mods.mediaMod as media
import TheKeyMachine.mods.settingsMod as settings
from TheKeyMachine.tools import colors as toolColors
from TheKeyMachine.tools import common as toolCommon
from TheKeyMachine.tools.common import ToolbarWindowToggle
from TheKeyMachine.widgets import customDialogs, customWidgets as cw, util as wutil

SELECTION_SETS_SETTINGS_NAMESPACE = "selection_sets_window"
SELECTION_SETS_AUTO_TRANSPARENCY_KEY = "selection_sets_auto_transparency"

SELECTION_SET_COLORS = toolColors.SELECTION_SET_COLORS
SELECTION_SET_COLOR_BY_SUFFIX = toolColors.SELECTION_SET_COLOR_BY_SUFFIX
SELECTION_SET_DEFAULT_COLOR = toolColors.SELECTION_SET_DEFAULT_COLOR
selection_set_color_names = {color.suffix: color.label for color in SELECTION_SET_COLORS}


def get_selection_set_color(suffix, fallback=None):
    return toolColors.get_selection_set_color(suffix, fallback=fallback)


_selection_set_creation_dialog = None


def _window_class():
    from TheKeyMachine.tools.selection_sets.customDialogs import SelectionSetsWindow

    return SelectionSetsWindow


def _creation_dialog_class():
    from TheKeyMachine.tools.selection_sets.customDialogs import SelectionSetCreationDialog

    return SelectionSetCreationDialog


def _members_dialog_class():
    from TheKeyMachine.tools.selection_sets.customDialogs import SelectionSetMembersDialog

    return SelectionSetMembersDialog


def _parent_widget():
    return wutil.get_maya_qt(qt=QtWidgets.QWidget)


def _emit_selection_sets_window_state(is_open):
    try:
        selection_sets_window_bus.stateChanged.emit(bool(is_open))
    except Exception:
        pass


def _resolve_toolbar_controller(controller=None):
    if controller:
        return controller
    try:
        from TheKeyMachine.core.toolbar import get_toolbar
    except Exception:
        return None
    return get_toolbar()


def _selection_sets_auto_transparency_enabled():
    return settings.get_setting(SELECTION_SETS_AUTO_TRANSPARENCY_KEY, True, namespace=SELECTION_SETS_SETTINGS_NAMESPACE)


def _set_selection_sets_auto_transparency_enabled(enabled):
    settings.set_setting(SELECTION_SETS_AUTO_TRANSPARENCY_KEY, bool(enabled), namespace=SELECTION_SETS_SETTINGS_NAMESPACE)
    win = get_selection_sets_window()
    if win and wutil.is_valid_widget(win):
        win._auto_transparency = bool(enabled)
        win.update_transparency_state(win._hovered)


def _selection_sets_stays_on_top():
    return settings.get_setting("stays_on_top", False, namespace=SELECTION_SETS_SETTINGS_NAMESPACE)


def _set_selection_sets_stays_on_top(enabled):
    settings.set_setting("stays_on_top", bool(enabled), namespace=SELECTION_SETS_SETTINGS_NAMESPACE)
    win = get_selection_sets_window()
    if win and wutil.is_valid_widget(win):
        win.apply_stay_on_top_setting()


class SelectionSetsWindowBus(QtCore.QObject):
    stateChanged = QtCore.Signal(bool)


selection_sets_window_bus = SelectionSetsWindowBus()


def get_selection_sets_window():
    window_class = _window_class()
    for widget in QtWidgets.QApplication.topLevelWidgets():
        if isinstance(widget, window_class) and wutil.is_valid_widget(widget):
            return widget
    return None


def is_selection_sets_window_open():
    win = get_selection_sets_window()
    return bool(win and win.isVisible())


def close_selection_sets_window():
    win = get_selection_sets_window()
    if win and wutil.is_valid_widget(win):
        win.close()
    else:
        _emit_selection_sets_window_state(False)


def selection_sets_window(*args, controller=None, reuse_existing=True):
    controller = _resolve_toolbar_controller(controller)
    win = get_selection_sets_window()
    if reuse_existing and win and wutil.is_valid_widget(win):
        if controller is not None:
            win.controller = controller
        reconnect = getattr(win, "_connect_selection_callback", None)
        if callable(reconnect):
            reconnect()
        if not win.isVisible():
            win.show()
        refresh_match_states = getattr(win, "_update_button_match_states", None)
        if callable(refresh_match_states):
            refresh_match_states()
        win.apply_stay_on_top_setting()
        clamp = getattr(win, "clamp_to_current_screen", None)
        if callable(clamp):
            clamp()
        win.raise_()
        win.activateWindow()
        _emit_selection_sets_window_state(True)
        return win

    win = _window_class()(controller=controller, parent=_parent_widget())

    def _on_destroyed(*_):
        _emit_selection_sets_window_state(False)

    win.destroyed.connect(_on_destroyed)
    win.show()
    if not getattr(win, "_restored_geometry", False):
        _place_selection_sets_window_default(win)
    _emit_selection_sets_window_state(True)
    return win


def _has_any_selection_sets(controller=None):
    controller = _resolve_toolbar_controller(controller)
    return bool(controller and controller.get_selection_sets())


def _can_open_selection_set_creation(show_message=True):
    if wutil.get_selected_objects():
        return True
    if show_message:
        wutil.make_inViewMessage("Select something first")
    return False


def _open_selection_sets_from_toolbar(controller=None):
    controller = _resolve_toolbar_controller(controller)
    if not _has_any_selection_sets(controller):
        if not _can_open_selection_set_creation(show_message=True):
            _emit_selection_sets_window_state(False)
            return
        open_selection_set_creation_dialog(
            controller=controller,
            on_created=lambda: selection_sets_window(controller=controller, reuse_existing=True),
            on_rejected=lambda: _emit_selection_sets_window_state(False),
        )
        return
    selection_sets_window(controller=controller, reuse_existing=True)


def open_selection_sets_toolbar_action(controller=None):
    _open_selection_sets_from_toolbar(controller=controller)


_selection_sets_open_fn = lambda: _open_selection_sets_from_toolbar(controller=None)
_selection_sets_toolbar_toggle = ToolbarWindowToggle(
    is_selection_sets_window_open,
    lambda: _selection_sets_open_fn(),
    close_selection_sets_window,
    selection_sets_window_bus.stateChanged,
)


def toggle_selection_sets_window(controller=None):
    global _selection_sets_open_fn
    controller = _resolve_toolbar_controller(controller)
    if controller is not None:
        _selection_sets_open_fn = lambda: _open_selection_sets_from_toolbar(controller=controller)
    if _selection_sets_toolbar_toggle:
        _selection_sets_toolbar_toggle.toggle()
    elif is_selection_sets_window_open():
        close_selection_sets_window()
    else:
        _open_selection_sets_from_toolbar(controller=controller)


def refresh_selection_sets_window():
    win = get_selection_sets_window()
    if win and wutil.is_valid_widget(win):
        win.refresh()


def _get_selection_sets_toolbar_button():
    button = getattr(_selection_sets_toolbar_toggle, "_button", None)
    if button and wutil.is_valid_widget(button) and button.isVisible():
        return button
    return None


def _place_selection_sets_window_default(win):
    if not win or not wutil.is_valid_widget(win):
        return
    win.place_above_toolbar_button(_get_selection_sets_toolbar_button())


def _selection_sets_quick_file():
    quick_dir = os.path.join(general.config["USER_FOLDER_PATH"], "TheKeyMachine_user_data", "selection_sets")
    os.makedirs(quick_dir, exist_ok=True)
    return os.path.join(quick_dir, "quick_selection_sets.json")


def quick_import_selection_sets(controller=None):
    controller = _resolve_toolbar_controller(controller)
    if controller:
        controller.import_sets(_selection_sets_quick_file())


def quick_export_selection_sets(controller=None):
    controller = _resolve_toolbar_controller(controller)
    if controller:
        controller.export_sets(_selection_sets_quick_file())


def import_selection_sets(controller=None):
    controller = _resolve_toolbar_controller(controller)
    if controller:
        controller.import_sets()


def export_selection_sets(controller=None):
    controller = _resolve_toolbar_controller(controller)
    if controller:
        controller.export_sets()


def clear_all_selection_sets(controller=None, parent=None):
    _confirm_clear_selection_sets(controller=controller, parent=parent)


def restore_selection_sets_default_position(controller=None):
    settings.set_setting("selection_sets_geometry", None, namespace=SELECTION_SETS_SETTINGS_NAMESPACE)
    win = get_selection_sets_window()
    if win and wutil.is_valid_widget(win):
        _place_selection_sets_window_default(win)


def _confirm_clear_selection_sets(controller=None, parent=None):
    controller = _resolve_toolbar_controller(controller)
    if controller is None:
        return
    clicked = customDialogs.QFlatConfirmDialog.question(
        parent=parent,
        window="Selection Sets",
        title="Clear all selection sets?",
        message="This will delete every selection set in the current scene.",
        buttons=[customDialogs.QFlatConfirmDialog.Yes, customDialogs.QFlatConfirmDialog.Cancel],
        highlight="Yes",
        closeButton=False,
    )
    if clicked and clicked.get("name") == "Yes":
        controller.clear_selection_sets()


def build_selection_sets_context_menu(parent=None, controller=None):
    controller = _resolve_toolbar_controller(controller)
    menu = cw.OpenMenuWidget(parent)

    auto_transparency_action = menu.addAction(
        QtGui.QIcon(media.selection_sets_image),
        "Auto Transparency",
        description="Make the floating Selection Sets palette translucent when the cursor is not over it.",
    )
    auto_transparency_action.setCheckable(True)
    auto_transparency_action.setChecked(_selection_sets_auto_transparency_enabled())
    auto_transparency_action.triggered.connect(_set_selection_sets_auto_transparency_enabled)

    menu.addSeparator()

    menu.addAction(
        QtGui.QIcon(media.selection_sets_import_image),
        "Quick Import",
        description="Import selection sets from the shared quick file.",
    ).triggered.connect(lambda *_: controller and controller.import_sets(_selection_sets_quick_file()))

    menu.addAction(
        QtGui.QIcon(media.selection_sets_export_image),
        "Quick Export",
        description="Export selection sets to the shared quick file, overwriting it.",
    ).triggered.connect(lambda *_: controller and controller.export_sets(_selection_sets_quick_file()))

    menu.addAction(
        QtGui.QIcon(media.selection_sets_import_image),
        "Import",
        description="Import selection sets from a chosen file.",
    ).triggered.connect(lambda *_: controller and controller.import_sets())

    menu.addAction(
        QtGui.QIcon(media.selection_sets_export_image),
        "Export",
        description="Export selection sets to a chosen file.",
    ).triggered.connect(lambda *_: controller and controller.export_sets())

    menu.addSeparator()
    menu.addAction(
        QtGui.QIcon(media.trash_image),
        "Clear All Select Sets",
        description="Delete every selection set in the current scene.",
    ).triggered.connect(lambda *_: _confirm_clear_selection_sets(controller=controller, parent=parent))

    menu.addSeparator()

    stays_on_top_action = menu.addAction(
        QtGui.QIcon(media.settings_image),
        "Stay on Top",
        description="Keep the floating Selection Sets palette above other Maya windows.",
    )
    stays_on_top_action.setCheckable(True)
    stays_on_top_action.setChecked(_selection_sets_stays_on_top())
    stays_on_top_action.triggered.connect(_set_selection_sets_stays_on_top)

    menu.addAction(
        QtGui.QIcon(media.selection_sets_reload_image),
        "Restore Position",
        description="Reset the floating Selection Sets palette to its default position above the Selection Sets toolbar button.",
    ).triggered.connect(lambda *_: restore_selection_sets_default_position(controller=controller))

    return menu


def open_selection_set_creation_dialog(controller=None, parent=None, on_created=None, on_rejected=None):
    global _selection_set_creation_dialog
    controller = _resolve_toolbar_controller(controller)
    if controller is None:
        return None
    if not _can_open_selection_set_creation(show_message=True):
        if callable(on_rejected):
            on_rejected()
        return None

    find_matching = getattr(controller, "find_matching_selection_set", None)
    if callable(find_matching):
        matching_set = find_matching()
        if matching_set:
            show_matching_message = getattr(controller, "show_matching_selection_set_message", None)
            if callable(show_matching_message):
                show_matching_message(matching_set)
            else:
                wutil.make_inViewMessage(f"Selection already matches set: {matching_set}")
            if callable(on_rejected):
                on_rejected()
            return None

    if parent is None or not wutil.is_valid_widget(parent):
        parent = _parent_widget()

    if _selection_set_creation_dialog and wutil.is_valid_widget(_selection_set_creation_dialog):
        _selection_set_creation_dialog.close()

    dialog = _creation_dialog_class()(
        controller=controller,
        parent=parent,
        on_created=on_created,
        on_rejected=on_rejected,
    )

    def _clear_reference(*_):
        global _selection_set_creation_dialog
        _selection_set_creation_dialog = None

    dialog.destroyed.connect(_clear_reference)
    dialog.show()
    dialog.raise_()
    dialog.activateWindow()
    QtCore.QTimer.singleShot(0, dialog._focus_name_field)
    _selection_set_creation_dialog = dialog
    return dialog


def open_selection_set_members(set_name):
    dlg = _members_dialog_class()(set_name=set_name, parent=_parent_widget())
    dlg.show()
    return dlg


def bind_selection_sets_toolbar_button(button, controller=None):
    global _selection_sets_open_fn
    controller = _resolve_toolbar_controller(controller)
    if controller is not None:
        _selection_sets_open_fn = lambda: _open_selection_sets_from_toolbar(controller=controller)
    if button:
        def _selection_sets_mouse_press(event, b=button, c=controller):
            if event.button() == QtCore.Qt.LeftButton:
                variant = getattr(b, "_get_active_shortcut_variant", lambda: None)()
                if variant and int(variant.get("mask", 0)):
                    b.triggerToolCallback(lambda: toggle_selection_sets_window(controller=c))
                    event.accept()
                    return True
            return False

        toolCommon.set_mouse_press_handler(
            button,
            "_tkm_selection_sets_mouse_press_filter",
            _selection_sets_mouse_press,
        )
        toolCommon.bind_toolbar_button_context_menu(
            _selection_sets_toolbar_toggle,
            button,
            "_tkm_selection_sets_context_menu_slot",
            lambda parent, c=controller: build_selection_sets_context_menu(parent=parent, controller=c),
        )
