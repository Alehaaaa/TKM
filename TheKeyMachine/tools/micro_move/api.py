import math
import os
import sys
import time

from maya.api import OpenMaya as om
from maya.api import OpenMayaUI as omui
from maya import cmds, mel, utils

from TheKeyMachine.Qt import QtCompat, QtCore, QtGui, QtWidgets

import TheKeyMachine.core.runtimeManager as runtime
from TheKeyMachine.data import icons


MICRO_MOVE_CONTEXT = "microMoveCtx"
MICRO_ROTATE_CONTEXT = "microRotateCtx"
MOVE_CONTEXT = "moveSuperContext"
ROTATE_CONTEXT = "RotateSuperContext"
SELECT_CONTEXT = "selectSuperContext"
MOVE_CONTEXT_COMMAND = "tkmMicroMoveContextCmd"
ROTATE_CONTEXT_COMMAND = "tkmMicroRotateContextCmd"
BUILD_COMMAND = "tkmMicroMoveBuild"
EXPECTED_PLUGIN_BUILD = "2026_07_15_native_converter_4"
LEGACY_HELPERS_GROUP = "tkm_microMove_helpers"

MICRO_MIN_GAIN = 1.0 / 6.0
MICRO_MAX_GAIN = 1.0
MICRO_ACCEL_START_PX_PER_SECOND = 120.0
MICRO_ACCEL_FULL_PX_PER_SECOND = 1400.0
MICRO_DRAG_THRESHOLD = 3
MICRO_ROTATE_DEGREES_PER_PIXEL = 0.35

PLUGIN_PATH = os.path.join(os.path.dirname(__file__), "plugin.py")
PLUGIN_REGISTRY_NAME = "tkmMicroMovePlugin"
CONTROLLER_APP_ATTRIBUTE = "_tkm_micro_move_controller"

_cursor_sample_position = None
_cursor_sample_time = None
_cursor_speed = 0.0
_manipulator_drag_active = False


def _build_micro_cursor(image_name):
    image_path = icons.path(image_name)
    pixmap = QtGui.QPixmap(image_path) if image_path else QtGui.QPixmap()
    if pixmap.isNull():
        return None
    return QtGui.QCursor(
        pixmap.scaled(
            33,
            33,
            QtCore.Qt.IgnoreAspectRatio,
            QtCore.Qt.SmoothTransformation,
        ),
        3,
        3,
    )


_MICRO_CURSOR_OPEN = _build_micro_cursor("micro_manipulator_open.png")
_MICRO_CURSOR_PINCHED = _build_micro_cursor("micro_manipulator.png")


def _clear_micro_cursor():
    """Remove only the cursor installed by this Micro Move controller."""
    # Earlier Micro Move builds used QApplication's override stack.  Remove a
    # leftover only when its pixels match one of our cursors; never drain
    # Maya's (or another tool's) cursor overrides.
    app = QtWidgets.QApplication.instance()
    if app is not None:
        override = app.overrideCursor()
        if override is not None:
            try:
                override_image = override.pixmap().toImage()
                micro_images = (
                    cursor.pixmap().toImage()
                    for cursor in (_MICRO_CURSOR_OPEN, _MICRO_CURSOR_PINCHED)
                    if cursor is not None
                )
                if any(override_image == image for image in micro_images):
                    app.restoreOverrideCursor()
            except Exception:
                pass

    controller = _active_controller()
    if controller is not None:
        controller._clear_viewport_cursor()


def _cursor_position():
    position = QtGui.QCursor.pos()
    return position.x(), position.y()


def _reset_cursor_acceleration():
    global _cursor_sample_position, _cursor_sample_time, _cursor_speed
    _cursor_sample_position = _cursor_position()
    _cursor_sample_time = time.perf_counter()
    _cursor_speed = 0.0


def _micro_gain():
    global _cursor_sample_position, _cursor_sample_time, _cursor_speed
    current_position = _cursor_position()
    now = time.perf_counter()

    if _cursor_sample_position is None or _cursor_sample_time is None:
        _cursor_sample_position = current_position
        _cursor_sample_time = now
        return MICRO_MIN_GAIN

    if current_position != _cursor_sample_position:
        elapsed = max(now - _cursor_sample_time, 0.001)
        distance = math.hypot(
            current_position[0] - _cursor_sample_position[0],
            current_position[1] - _cursor_sample_position[1],
        )
        _cursor_speed = distance / elapsed
        _cursor_sample_position = current_position
        _cursor_sample_time = now

    acceleration_range = (
        MICRO_ACCEL_FULL_PX_PER_SECOND - MICRO_ACCEL_START_PX_PER_SECOND
    )
    amount = (_cursor_speed - MICRO_ACCEL_START_PX_PER_SECOND) / acceleration_range
    amount = max(0.0, min(1.0, amount))
    amount = amount * amount * (3.0 - (2.0 * amount))
    return MICRO_MIN_GAIN + ((MICRO_MAX_GAIN - MICRO_MIN_GAIN) * amount)


def begin_manipulator_drag():
    """Called by the MPx manipulator when a native handle is pressed."""
    global _manipulator_drag_active
    _manipulator_drag_active = True
    _reset_cursor_acceleration()
    controller = _active_controller()
    if controller is not None:
        controller._set_viewport_cursor(pinched=True)


def manipulator_drag_gain():
    """Called from MPxManipContainer.doDrag to scale the latest plug delta."""
    return _micro_gain()


def end_manipulator_drag(restore_open_cursor=True):
    """Called by the MPx manipulator when its native handle is released."""
    global _manipulator_drag_active
    _manipulator_drag_active = False
    controller = _active_controller()
    if controller is not None:
        if restore_open_cursor:
            controller._set_viewport_cursor(pinched=False)
        else:
            controller._clear_viewport_cursor()


def _active_controller():
    app = QtWidgets.QApplication.instance()
    if app is None:
        return None
    controller = getattr(app, CONTROLLER_APP_ATTRIBUTE, None)
    if controller is None or not controller._owns_controller_instance():
        return None
    return controller


def _remove_legacy_helpers():
    if not cmds.objExists(LEGACY_HELPERS_GROUP):
        return

    original_selection = cmds.ls(selection=True, long=True) or []
    try:
        cmds.lockNode(LEGACY_HELPERS_GROUP, lock=False)
    except Exception:
        pass
    cmds.delete(LEGACY_HELPERS_GROUP)

    valid_selection = [node for node in original_selection if cmds.objExists(node)]
    if valid_selection:
        cmds.select(valid_selection, replace=True)
    else:
        cmds.select(clear=True)


def _context_exists(context_name):
    try:
        return bool(cmds.contextInfo(context_name, exists=True))
    except Exception:
        return False


def _delete_context(context_name):
    if not _context_exists(context_name):
        return
    try:
        cmds.deleteUI(context_name, toolContext=True)
    except Exception:
        pass


def _normalized_path(path):
    return os.path.normcase(os.path.realpath(path))


def _loaded_micro_move_plugin():
    """Return the registry name loaded from our exact file path."""
    expected_path = _normalized_path(PLUGIN_PATH)
    for plugin_name in cmds.pluginInfo(query=True, listPlugins=True) or []:
        try:
            if not cmds.pluginInfo(plugin_name, query=True, loaded=True):
                continue
            plugin_path = cmds.pluginInfo(plugin_name, query=True, path=True)
            if _normalized_path(plugin_path) == expected_path:
                return plugin_name
        except (RuntimeError, TypeError):
            continue
    return None


def _command_exists(command_name):
    return bool(mel.eval('exists "{}"'.format(command_name)))


def _plugin_build_id():
    result = getattr(cmds, BUILD_COMMAND)()
    if isinstance(result, (list, tuple)):
        result = result[0] if result else ""
    return str(result)


def _unload_micro_move_plugin():
    plugin_name = _loaded_micro_move_plugin()
    if not plugin_name:
        return
    cmds.unloadPlugin(plugin_name)
    try:
        cmds.pluginInfo(plugin_name, edit=True, remove=True)
    except RuntimeError:
        pass


def _purge_micro_move_plugin_module_cache():
    """Remove only Python modules loaded from this exact plugin.py path."""
    expected_path = _normalized_path(PLUGIN_PATH)
    for module_name, module in list(sys.modules.items()):
        module_path = getattr(module, "__file__", None)
        if not module_path:
            continue
        try:
            matches = _normalized_path(module_path) == expected_path
        except (TypeError, ValueError, OSError):
            matches = False
        if matches:
            sys.modules.pop(module_name, None)


def _load_micro_move_plugin(force_reload=False):
    plugin_name = _loaded_micro_move_plugin()
    commands_ready = all(
        _command_exists(command_name)
        for command_name in (
            MOVE_CONTEXT_COMMAND,
            ROTATE_CONTEXT_COMMAND,
            BUILD_COMMAND,
        )
    )
    build_ready = False
    if commands_ready:
        try:
            build_ready = (
                _plugin_build_id() == EXPECTED_PLUGIN_BUILD
            )
        except (RuntimeError, AttributeError, TypeError):
            build_ready = False
    if plugin_name and commands_ready and build_ready and not force_reload:
        return plugin_name

    # Reload an earlier copy of this exact plug-in if it did not register the
    # expected commands. A generic basename check is deliberately avoided:
    # many Maya tools contain a file named plugin.py.
    if plugin_name:
        _unload_micro_move_plugin()

    _purge_micro_move_plugin_module_cache()

    loaded_names = cmds.loadPlugin(
        PLUGIN_PATH,
        name=PLUGIN_REGISTRY_NAME,
        quiet=True,
    )
    plugin_name = loaded_names[0] if loaded_names else _loaded_micro_move_plugin()
    missing_commands = [
        command_name
        for command_name in (
            MOVE_CONTEXT_COMMAND,
            ROTATE_CONTEXT_COMMAND,
            BUILD_COMMAND,
        )
        if not _command_exists(command_name)
    ]
    if missing_commands:
        raise RuntimeError(
            "Micro Move plug-in {} loaded but did not register: {}".format(
                plugin_name or PLUGIN_PATH,
                ", ".join(missing_commands),
            )
        )
    loaded_build = _plugin_build_id()
    if loaded_build != EXPECTED_PLUGIN_BUILD:
        raise RuntimeError(
            "Micro Move loaded stale Python plug-in code: expected build {}, "
            "Maya reported {}.".format(EXPECTED_PLUGIN_BUILD, loaded_build)
        )
    return plugin_name


def _create_plugin_context(command_name, context_name):
    if not command_name.replace("_", "").isalnum():
        raise ValueError("Invalid Micro Move context command name.")
    if not context_name.replace("_", "").isalnum():
        raise ValueError("Invalid Micro Move context name.")
    try:
        mel.eval('{} "{}"'.format(command_name, context_name))
    except RuntimeError as error:
        raise RuntimeError(
            "Micro Move plug-in could not create {} using {}: {}".format(
                context_name,
                command_name,
                error,
            )
        )


def _ensure_micro_contexts():
    """Load the Python plug-in and create its native MPx contexts."""
    _remove_legacy_helpers()
    _delete_context(MICRO_MOVE_CONTEXT)
    _delete_context(MICRO_ROTATE_CONTEXT)
    _load_micro_move_plugin(force_reload=True)
    _create_plugin_context(MOVE_CONTEXT_COMMAND, MICRO_MOVE_CONTEXT)
    _create_plugin_context(ROTATE_CONTEXT_COMMAND, MICRO_ROTATE_CONTEXT)


def activate_micro_move(*_args):
    current_context = cmds.currentCtx()
    _ensure_micro_contexts()
    target_context = (
        MICRO_ROTATE_CONTEXT
        if current_context in (ROTATE_CONTEXT, MICRO_ROTATE_CONTEXT)
        else MICRO_MOVE_CONTEXT
    )
    cmds.setToolTo(target_context)
    return target_context


class MicroMoveController(QtCore.QObject):
    stateChanged = QtCore.Signal(bool)

    def __init__(self, owner):
        super().__init__(owner)
        self._owner = owner
        self._enabled = False
        self._tool_changed_callback = None
        self._sync_pending = False
        self._changing_context = False
        self._event_filter_installed = False
        self._cursor_widget = None
        self._claim_controller_instance()
        owner.destroyed.connect(self._on_owner_destroyed)

    def _claim_controller_instance(self):
        """Make this Maya session's sole active Micro Move event owner."""
        app = QtWidgets.QApplication.instance()
        if app is None:
            return

        controllers = []
        previous = getattr(app, CONTROLLER_APP_ATTRIBUTE, None)
        if previous is not None and previous is not self:
            controllers.append(previous)

        for widget in list(app.allWidgets()):
            if widget is self._owner:
                continue
            controller = getattr(widget, "micro_move_controller", None)
            if (
                controller is not None
                and controller is not self
                and controller not in controllers
            ):
                controllers.append(controller)

        for controller in controllers:
            try:
                controller.deactivate()
            except Exception:
                try:
                    app.removeEventFilter(controller)
                except Exception:
                    pass

        setattr(app, CONTROLLER_APP_ATTRIBUTE, self)

    def _release_controller_instance(self):
        app = QtWidgets.QApplication.instance()
        if (
            app is not None
            and getattr(app, CONTROLLER_APP_ATTRIBUTE, None) is self
        ):
            try:
                delattr(app, CONTROLLER_APP_ATTRIBUTE)
            except Exception:
                pass

    def _owns_controller_instance(self):
        app = QtWidgets.QApplication.instance()
        return (
            app is not None
            and getattr(app, CONTROLLER_APP_ATTRIBUTE, None) is self
        )

    def is_enabled(self):
        return self._enabled

    def _publish_state(self):
        state = self.is_enabled()
        self.stateChanged.emit(state)
        runtime.get_runtime_manager().set_tool_state("micro_move", state)

    def _install_tool_changed_callback(self):
        if self._tool_changed_callback is not None:
            return
        self._tool_changed_callback = om.MEventMessage.addEventCallback(
            "PostToolChanged", self._on_tool_changed
        )

    def _remove_tool_changed_callback(self):
        callback_id = self._tool_changed_callback
        self._tool_changed_callback = None
        if callback_id is None:
            return
        try:
            om.MMessage.removeCallback(callback_id)
        except Exception:
            pass

    def _install_mouse_event_filter(self):
        if self._event_filter_installed:
            return
        app = QtWidgets.QApplication.instance()
        if app is None:
            return
        app.installEventFilter(self)
        self._event_filter_installed = True

    def _remove_mouse_event_filter(self):
        if not self._event_filter_installed:
            return
        self._event_filter_installed = False
        app = QtWidgets.QApplication.instance()
        if app is not None:
            app.removeEventFilter(self)

    def eventFilter(self, watched, event):
        if not self._owns_controller_instance():
            return False
        if self._enabled and cmds.currentCtx() in (
            MICRO_MOVE_CONTEXT,
            MICRO_ROTATE_CONTEXT,
        ):
            event_type = event.type()
            if (
                event_type == QtCore.QEvent.MouseMove
                and not _manipulator_drag_active
            ):
                panel = self._model_panel_under_pointer()
                if panel:
                    self._remember_viewport_widget(panel)
                    self._set_viewport_cursor(pinched=False)
        return False

    @staticmethod
    def _model_panel_under_pointer():
        panel = cmds.getPanel(underPointer=True)
        if not panel:
            return None
        try:
            return panel if cmds.getPanel(typeOf=panel) == "modelPanel" else None
        except RuntimeError:
            return None

    def _remember_viewport_widget(self, panel):
        view = omui.M3dView.getM3dViewFromModelPanel(panel)
        pointer = view.widget()
        if pointer:
            widget = QtCompat.wrapInstance(
                int(pointer),
                QtWidgets.QWidget,
            )
            previous_widget = self._cursor_widget
            if (
                previous_widget is not None
                and previous_widget is not widget
                and QtCompat.isValid(previous_widget)
            ):
                previous_widget.unsetCursor()
            self._cursor_widget = widget

    def _set_viewport_cursor(self, pinched=False):
        widget = self._cursor_widget
        if widget is None or not QtCompat.isValid(widget):
            return
        cursor = _MICRO_CURSOR_PINCHED if pinched else _MICRO_CURSOR_OPEN
        if cursor is not None:
            widget.setCursor(cursor)

    def _clear_viewport_cursor(self):
        widget = self._cursor_widget
        self._cursor_widget = None
        if widget is not None and QtCompat.isValid(widget):
            widget.unsetCursor()

    def _on_owner_destroyed(self, *_args):
        """Clear transient state even when Maya destroys the toolbar directly."""
        self._enabled = False
        self._sync_pending = False
        self._remove_tool_changed_callback()
        self._remove_mouse_event_filter()
        self._clear_viewport_cursor()
        self._release_controller_instance()
        end_manipulator_drag(restore_open_cursor=False)
        _clear_micro_cursor()

    def _on_tool_changed(self, *_args):
        if not self._enabled or self._changing_context or self._sync_pending:
            return
        self._sync_pending = True

        def _deferred_sync():
            self._sync_pending = False
            if not self._enabled or not QtCompat.isValid(self._owner):
                return
            self._sync_context(initial=False)

        utils.executeDeferred(_deferred_sync)

    def _set_context(self, context_name):
        if cmds.currentCtx() == context_name:
            self._set_viewport_cursor(pinched=False)
            return
        self._changing_context = True
        try:
            cmds.setToolTo(context_name)
            self._set_viewport_cursor(pinched=False)
        finally:
            self._changing_context = False

    def _sync_context(self, initial=False):
        current_context = cmds.currentCtx()

        if current_context == SELECT_CONTEXT:
            if initial:
                self._set_context(MICRO_MOVE_CONTEXT)
            else:
                self.deactivate(restore_standard_context=False)
            return

        if current_context == MOVE_CONTEXT:
            self._set_context(MICRO_MOVE_CONTEXT)
            return
        if current_context == ROTATE_CONTEXT:
            self._set_context(MICRO_ROTATE_CONTEXT)
            return
        if current_context in (MICRO_MOVE_CONTEXT, MICRO_ROTATE_CONTEXT):
            self._set_viewport_cursor(pinched=False)
            return

        if initial:
            self._set_context(MICRO_MOVE_CONTEXT)
        else:
            self.deactivate(restore_standard_context=False)

    def activate(self):
        self._claim_controller_instance()
        if self._enabled:
            self._sync_context(initial=True)
            return
        _clear_micro_cursor()
        _ensure_micro_contexts()
        self._enabled = True
        try:
            self._install_tool_changed_callback()
            self._install_mouse_event_filter()
            self._sync_context(initial=True)
        except Exception:
            self._enabled = False
            self._remove_tool_changed_callback()
            self._remove_mouse_event_filter()
            _clear_micro_cursor()
            self._publish_state()
            raise
        self._publish_state()

    def deactivate(self, restore_standard_context=True):
        was_enabled = self._enabled
        self._enabled = False
        self._sync_pending = False
        self._remove_tool_changed_callback()
        self._remove_mouse_event_filter()
        self._clear_viewport_cursor()
        self._release_controller_instance()
        end_manipulator_drag(restore_open_cursor=False)
        _clear_micro_cursor()

        if restore_standard_context and was_enabled:
            current_context = cmds.currentCtx()
            if current_context == MICRO_MOVE_CONTEXT:
                self._set_context(MOVE_CONTEXT)
            elif current_context == MICRO_ROTATE_CONTEXT:
                self._set_context(ROTATE_CONTEXT)

        _delete_context(MICRO_MOVE_CONTEXT)
        _delete_context(MICRO_ROTATE_CONTEXT)
        try:
            _unload_micro_move_plugin()
        except RuntimeError:
            pass

        self._publish_state()

    def toggle(self, checked=None, button_widget=None):
        if checked is None:
            checked = not self._enabled

        if bool(checked):
            self.activate()
        else:
            self.deactivate()
