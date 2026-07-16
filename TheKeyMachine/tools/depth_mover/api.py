"""Native Depth Mover context lifecycle."""

import os

from maya.api import OpenMaya as om
from maya import cmds, utils

from TheKeyMachine.Qt import QtCompat, QtCore
from TheKeyMachine.data import icons
import TheKeyMachine.core.runtimeManager as runtime
from TheKeyMachine.tools import common as toolCommon
from TheKeyMachine.tools import plugins


DEPTH_CONTEXT = "tkmDepthMoverCtx"
DEPTH_CONTEXT_COMMAND = "tkmDepthMoverNativeContextCmd"
BUILD_COMMAND = "tkmDepthMoverNativeBuild"
CONFIGURE_COMMAND = "tkmDepthMoverNativeConfigure"
EXPECTED_PLUGIN_BUILD = "2026_07_15_native_cpp_9"
SELECT_CONTEXT = "selectSuperContext"

PLUGIN_SPEC = plugins.NativePluginSpec(
    label="Depth Mover",
    plugin_directory=os.path.dirname(__file__),
    output_name="tkmDepthMoverNative",
    registry_name="tkmDepthMoverNativePlugin",
    required_commands=(DEPTH_CONTEXT_COMMAND, BUILD_COMMAND, CONFIGURE_COMMAND),
    build_command=BUILD_COMMAND,
    expected_build=EXPECTED_PLUGIN_BUILD,
    context_fallbacks={DEPTH_CONTEXT: SELECT_CONTEXT},
)
RUNTIME_CALLBACK_KEY = "depth_mover:tool_changed"
_CONTROLLER = None


def _has_transform_selection():
    return bool(cmds.ls(selection=True, type="transform"))


def _warn_selection_required():
    om.MGlobal.displayWarning("Select something to depth move.")


def _ensure_context():
    plugins.ensure_contexts(
        PLUGIN_SPEC,
        ((DEPTH_CONTEXT_COMMAND, DEPTH_CONTEXT),),
        configure_command=CONFIGURE_COMMAND,
        configure_args=(icons.depth_mover,),
    )


def cleanup():
    global _CONTROLLER
    controller = get_controller(create=False)
    _CONTROLLER = None
    if controller is not None:
        controller.shutdown()
        controller.deleteLater()
        return
    plugins.unload(PLUGIN_SPEC, restore_context=True)


class DepthMoverController(QtCore.QObject):
    stateChanged = QtCore.Signal(bool)

    def __init__(self, manager):
        super().__init__(manager)
        self._manager = manager
        self._enabled = False
        self._changing_context = False
        self._sync_pending = False
        current_context = cmds.currentCtx()
        self._fallback_context = (
            current_context if current_context != DEPTH_CONTEXT else SELECT_CONTEXT
        )
        self._install_callback()

    def is_enabled(self):
        return bool(
            self._enabled
            and plugins.loaded_plugin(PLUGIN_SPEC)
            and cmds.currentCtx() == DEPTH_CONTEXT
        )

    def _publish_state(self):
        state = self.is_enabled()
        self.stateChanged.emit(state)
        self._manager.set_tool_state("depth_mover", state)

    def _install_callback(self):
        self._manager.disconnect_callbacks(RUNTIME_CALLBACK_KEY)
        self._manager.add_maya_event_callback(
            "PostToolChanged",
            self._on_tool_changed,
            key=RUNTIME_CALLBACK_KEY,
        )

    def _remove_callback(self):
        self._manager.disconnect_callbacks(RUNTIME_CALLBACK_KEY)

    def _set_context(self, context_name):
        if cmds.currentCtx() == context_name:
            return
        if context_name != DEPTH_CONTEXT:
            self._fallback_context = context_name
        self._changing_context = True
        try:
            cmds.setToolTo(context_name)
        finally:
            self._changing_context = False

    def _on_tool_changed(self, *_args):
        if self._changing_context or self._sync_pending:
            return
        self._sync_pending = True

        def _sync():
            self._sync_pending = False
            if not QtCompat.isValid(self):
                return
            current_context = cmds.currentCtx()
            if current_context == DEPTH_CONTEXT:
                if not _has_transform_selection():
                    self._enabled = False
                    fallback = self._fallback_context
                    if (
                        fallback == DEPTH_CONTEXT
                        or not plugins.context_exists(fallback)
                    ):
                        fallback = SELECT_CONTEXT
                    self._set_context(fallback)
                    self._publish_state()
                    _warn_selection_required()
                    return
                if not self._enabled:
                    self._enabled = True
                    self._publish_state()
                return
            self._fallback_context = current_context
            if self._enabled:
                self.deactivate(restore_select=False)

        utils.executeDeferred(_sync)

    def activate(self):
        if self.is_enabled():
            return DEPTH_CONTEXT
        toolCommon.deactivate_other_manipulator_tools("depth_mover")
        if not _has_transform_selection():
            _warn_selection_required()
            self._publish_state()
            return None
        self._fallback_context = cmds.currentCtx()
        _ensure_context()
        self._enabled = True
        self._set_context(DEPTH_CONTEXT)
        self._publish_state()
        return DEPTH_CONTEXT

    def deactivate(self, restore_select=True):
        was_enabled = self._enabled
        self._enabled = False
        self._sync_pending = False
        if restore_select and was_enabled and cmds.currentCtx() == DEPTH_CONTEXT:
            self._set_context(SELECT_CONTEXT)
        self._publish_state()

    def shutdown(self):
        self.deactivate(restore_select=True)
        self._remove_callback()
        try:
            plugins.unload(PLUGIN_SPEC, restore_context=True)
        except Exception as error:
            om.MGlobal.displayWarning(
                "Depth Mover cleanup was incomplete: {}".format(error)
            )

    def toggle(self, checked=None):
        enabled = self.is_enabled()
        target = not enabled if checked is None else bool(checked)
        return self.activate() if target else self.deactivate()


def get_controller(create=True):
    global _CONTROLLER
    if _CONTROLLER is not None and not QtCompat.isValid(_CONTROLLER):
        _CONTROLLER = None
    if _CONTROLLER is None and create:
        _CONTROLLER = DepthMoverController(runtime.get_runtime_manager())
    return _CONTROLLER


def is_enabled():
    controller = get_controller(create=False)
    return bool(controller and controller.is_enabled())


def activate(*_args):
    return get_controller().activate()


def toggle(checked=None, *_args):
    return get_controller().toggle(checked)
