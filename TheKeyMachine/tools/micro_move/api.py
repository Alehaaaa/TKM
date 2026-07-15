import os

from maya.api import OpenMaya as om
from maya import cmds, utils

from TheKeyMachine.Qt import QtCompat, QtCore
from TheKeyMachine.data import icons

import TheKeyMachine.core.runtimeManager as runtime
from TheKeyMachine.tools import common as toolCommon
from TheKeyMachine.tools import plugins


MICRO_MOVE_CONTEXT = "microMoveCtx"
MICRO_ROTATE_CONTEXT = "microRotateCtx"
MOVE_CONTEXT = "moveSuperContext"
ROTATE_CONTEXT = "RotateSuperContext"
SELECT_CONTEXT = "selectSuperContext"
MOVE_CONTEXT_COMMAND = "tkmMicroMoveContextCmd"
ROTATE_CONTEXT_COMMAND = "tkmMicroRotateContextCmd"
BUILD_COMMAND = "tkmMicroMoveBuild"
CONFIGURE_COMMAND = "tkmMicroMoveConfigure"
REFRESH_COMMAND = "tkmMicroMoveRefresh"
EXPECTED_PLUGIN_BUILD = "2026_07_15_native_cpp_13"
LEGACY_HELPERS_GROUP = "tkm_microMove_helpers"

PLUGIN_SOURCE_PATH = os.path.join(os.path.dirname(__file__), "plugin.cpp")
PLUGIN_SPEC = plugins.NativePluginSpec(
    label="Micro Move",
    source_paths=(PLUGIN_SOURCE_PATH,),
    output_name="tkmMicroMove",
    registry_name="tkmMicroMovePlugin",
    build_recipe="cross-platform-cpp17-maya-image-v1",
    required_commands=(
        MOVE_CONTEXT_COMMAND,
        ROTATE_CONTEXT_COMMAND,
        BUILD_COMMAND,
        CONFIGURE_COMMAND,
        REFRESH_COMMAND,
    ),
    build_command=BUILD_COMMAND,
    expected_build=EXPECTED_PLUGIN_BUILD,
    context_fallbacks={
        MICRO_MOVE_CONTEXT: MOVE_CONTEXT,
        MICRO_ROTATE_CONTEXT: ROTATE_CONTEXT,
    },
)
RUNTIME_CALLBACK_KEY = "micro_move:tool_changed"
_CONTROLLER = None


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


def _plugin_cursor_paths():
    cursor_paths = (
        icons.micro_manipulator_open,
        icons.micro_manipulator,
        icons.ruler,
    )
    missing_paths = [path for path in cursor_paths if not os.path.isfile(path)]
    if missing_paths:
        raise RuntimeError(
            "Micro Move cursor image is missing: {}".format(
                ", ".join(missing_paths)
            )
        )
    return cursor_paths


def _ensure_micro_contexts():
    """Load the native plug-in and recreate its MPx contexts."""
    _remove_legacy_helpers()
    plugins.ensure_contexts(
        PLUGIN_SPEC,
        (
            (MOVE_CONTEXT_COMMAND, MICRO_MOVE_CONTEXT),
            (ROTATE_CONTEXT_COMMAND, MICRO_ROTATE_CONTEXT),
        ),
        configure_command=CONFIGURE_COMMAND,
        configure_args=_plugin_cursor_paths(),
    )


class MicroMoveController(QtCore.QObject):
    stateChanged = QtCore.Signal(bool)

    def __init__(self, manager):
        super().__init__(manager)
        self._manager = manager
        self._enabled = False
        self._sync_pending = False
        self._refresh_pending = False
        self._changing_context = False
        self._last_micro_context = MICRO_MOVE_CONTEXT
        current_context = cmds.currentCtx()
        self._previous_context = (
            current_context
            if current_context not in (MICRO_MOVE_CONTEXT, MICRO_ROTATE_CONTEXT)
            else SELECT_CONTEXT
        )
        self._install_tool_changed_callback()

    def is_enabled(self):
        return bool(
            self._enabled
            and cmds.currentCtx() in (MICRO_MOVE_CONTEXT, MICRO_ROTATE_CONTEXT)
        )

    def _publish_state(self):
        state = self.is_enabled()
        self.stateChanged.emit(state)
        self._manager.set_tool_state("micro_move", state)

    def _install_tool_changed_callback(self):
        self._manager.disconnect_callbacks(RUNTIME_CALLBACK_KEY)
        self._manager.add_maya_event_callback(
            "PostToolChanged",
            self._on_tool_changed,
            key=RUNTIME_CALLBACK_KEY,
        )

    def _connect_runtime_events(self):
        toolCommon.replace_tracked_connections(
            self,
            "_runtime_event_relays",
            (
                (self._manager.selection_changed, self._request_manipulator_refresh),
                (self._manager.time_changed, self._request_manipulator_refresh),
                (self._manager.undo_performed, self._request_manipulator_refresh),
            ),
            parent=self,
        )

    def _disconnect_runtime_events(self):
        toolCommon.clear_tracked_connections(self, "_runtime_event_relays")

    def _remove_tool_changed_callback(self):
        self._manager.disconnect_callbacks(RUNTIME_CALLBACK_KEY)

    def _request_manipulator_refresh(self):
        if not self._enabled or self._refresh_pending:
            return
        self._refresh_pending = True

        def _refresh():
            self._refresh_pending = False
            if not self._enabled or not QtCompat.isValid(self):
                return
            if cmds.currentCtx() not in (MICRO_MOVE_CONTEXT, MICRO_ROTATE_CONTEXT):
                return
            if plugins.command_exists(REFRESH_COMMAND):
                getattr(cmds, REFRESH_COMMAND)()

        utils.executeDeferred(_refresh)

    def _on_tool_changed(self, *_args):
        if self._changing_context or self._sync_pending:
            return
        self._sync_pending = True

        def _deferred_sync():
            self._sync_pending = False
            if not QtCompat.isValid(self):
                return
            current_context = cmds.currentCtx()
            if not self._enabled:
                if current_context not in (MICRO_MOVE_CONTEXT, MICRO_ROTATE_CONTEXT):
                    self._previous_context = current_context
                    return
                target_context = self._context_for_source(self._previous_context)
                if current_context != target_context:
                    self._set_context(target_context)
                self._last_micro_context = target_context
                self._enabled = True
                self._connect_runtime_events()
                self._publish_state()
                return
            self._sync_context(initial=False)

        utils.executeDeferred(_deferred_sync)

    def _set_context(self, context_name):
        if context_name in (MICRO_MOVE_CONTEXT, MICRO_ROTATE_CONTEXT):
            self._last_micro_context = context_name
        else:
            self._previous_context = context_name
        if cmds.currentCtx() == context_name:
            return
        self._changing_context = True
        try:
            cmds.setToolTo(context_name)
        finally:
            self._changing_context = False

    def _cleanup_native_resources(self, restore_standard_context):
        try:
            plugins.unload(
                PLUGIN_SPEC,
                restore_context=bool(restore_standard_context),
            )
        except Exception as error:
            try:
                om.MGlobal.displayWarning(
                    "Micro Move cleanup was incomplete: {}".format(error)
                )
            except Exception:
                pass

    def _preferred_context(self):
        return (
            self._last_micro_context
            if self._last_micro_context in (MICRO_MOVE_CONTEXT, MICRO_ROTATE_CONTEXT)
            else MICRO_MOVE_CONTEXT
        )

    def _context_for_source(self, source_context):
        if source_context == MOVE_CONTEXT:
            return MICRO_MOVE_CONTEXT
        if source_context == ROTATE_CONTEXT:
            return MICRO_ROTATE_CONTEXT
        return self._preferred_context()

    def _sync_context(self, initial=False):
        current_context = cmds.currentCtx()

        if current_context == SELECT_CONTEXT:
            if initial:
                self._set_context(self._preferred_context())
            else:
                self._previous_context = current_context
                self.deactivate(restore_standard_context=False)
            return

        if current_context == MOVE_CONTEXT:
            self._set_context(MICRO_MOVE_CONTEXT)
            return
        if current_context == ROTATE_CONTEXT:
            self._set_context(MICRO_ROTATE_CONTEXT)
            return
        if current_context in (MICRO_MOVE_CONTEXT, MICRO_ROTATE_CONTEXT):
            self._last_micro_context = current_context
            return

        if initial:
            self._set_context(self._preferred_context())
        else:
            self._previous_context = current_context
            self.deactivate(restore_standard_context=False)

    def activate(self):
        if self._enabled:
            self._sync_context(initial=True)
            return
        toolCommon.deactivate_other_manipulator_tools("micro_move")
        _ensure_micro_contexts()
        self._enabled = True
        try:
            self._install_tool_changed_callback()
            self._connect_runtime_events()
            self._sync_context(initial=True)
        except Exception:
            self._enabled = False
            self._remove_tool_changed_callback()
            self._disconnect_runtime_events()
            self._publish_state()
            raise
        self._publish_state()

    def deactivate(self, restore_standard_context=True):
        was_enabled = self._enabled
        self._enabled = False
        self._sync_pending = False
        self._refresh_pending = False
        self._disconnect_runtime_events()

        if restore_standard_context and was_enabled:
            current_context = cmds.currentCtx()
            if current_context == MICRO_MOVE_CONTEXT:
                self._set_context(MOVE_CONTEXT)
            elif current_context == MICRO_ROTATE_CONTEXT:
                self._set_context(ROTATE_CONTEXT)

        self._publish_state()

    def shutdown(self):
        self.deactivate(restore_standard_context=True)
        self._remove_tool_changed_callback()
        self._cleanup_native_resources(restore_standard_context=True)

    def toggle(self, checked=None):
        if checked is None:
            checked = not self._enabled

        if bool(checked):
            self.activate()
        else:
            self.deactivate()


def get_controller(create=True):
    global _CONTROLLER
    if _CONTROLLER is not None and not QtCompat.isValid(_CONTROLLER):
        _CONTROLLER = None
    if _CONTROLLER is None and create:
        _CONTROLLER = MicroMoveController(runtime.get_runtime_manager())
    return _CONTROLLER


def is_enabled():
    controller = get_controller(create=False)
    return bool(controller and controller.is_enabled())


def activate(*_args):
    return get_controller().activate()


def toggle(checked=None, *_args):
    return get_controller().toggle(checked)


def cleanup():
    global _CONTROLLER
    controller = get_controller(create=False)
    _CONTROLLER = None
    if controller is not None:
        controller.shutdown()
        controller.deleteLater()
        return
    plugins.unload(PLUGIN_SPEC, restore_context=True)
