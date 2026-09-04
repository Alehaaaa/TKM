"""
Centralized Maya runtime manager for TheKeyMachine.

- Owns Maya callbacks (OpenMaya + scriptJobs) and guarantees cleanup on unload/reload.
- Emits Qt signals when runtime events fire so UI can subscribe without creating its own jobs.
- Tracks managed Qt widgets that should be cleaned up with their owner or on shutdown.
"""

from __future__ import annotations

import json
import sys
from contextlib import contextmanager
from typing import Any, Callable, Dict, List, Optional

from maya import cmds

from TheKeyMachine.core.Qt import QtCompat, QtCore, QtWidgets  # type: ignore
from TheKeyMachine.maya import maya_api

try:
    from maya.api import OpenMaya as om  # type: ignore
except ImportError:  # pragma: no cover
    om = None

try:
    from maya import OpenMaya as om1  # type: ignore
except ImportError:  # pragma: no cover
    om1 = None

try:
    from maya.api import OpenMayaAnim as oma  # type: ignore
except ImportError:  # pragma: no cover
    oma = None

try:
    from maya import OpenMayaUI as omui  # type: ignore
except ImportError:  # pragma: no cover
    omui = None


# This is the one deliberate exception to TKM's "no per-tool optionVars"
# rule (see core/settings.py, which every other module uses instead). It
# isn't a user preference -- it's a live status flag recording native
# OpenMaya callback / scriptJob ids owned by *this* session, so a leftover
# Python reload or crash can be detected and cleaned up on the next load.
# It has to be a real Maya optionVar (not the JSON preferences file) because
# it must survive a `TheKeyMachine` Python module reload within the same
# Maya session, independent of any file I/O.
_OPTIONVAR_NAME = "TKM_RuntimeManager"
_APP_RUNTIME_ATTRIBUTE = "_tkm_runtime_manager"
_TRANSIENT_WIDGET_PROPERTY = "tkm_managed_transient"
_MANAGER: Optional["RuntimeManager"] = None
_TKM_FLOATING_WIDGET_PROPERTY = "tkm_floating_widget"
_TKM_WORKSPACE_CONTROLS = ("kWorkspaceControl",)


def _load_state() -> Dict[str, Any]:
    try:
        if cmds.optionVar(exists=_OPTIONVAR_NAME):
            raw = cmds.optionVar(q=_OPTIONVAR_NAME)
            if isinstance(raw, str) and raw:
                return json.loads(raw)
    except (RuntimeError, ValueError, TypeError, AttributeError, KeyError, IndexError):
        pass
    return {"om": [], "scriptjob": []}


def _save_state(state: Dict[str, Any]) -> None:
    if not (state.get("om") or state.get("scriptjob")):
        _clear_state()
        return
    try:
        cmds.optionVar(sv=(_OPTIONVAR_NAME, json.dumps(state)))
    except (RuntimeError, ValueError, TypeError, AttributeError, KeyError, IndexError):
        pass


def _clear_state() -> None:
    try:
        if cmds.optionVar(exists=_OPTIONVAR_NAME):
            cmds.optionVar(remove=_OPTIONVAR_NAME)
    except (RuntimeError, ValueError, TypeError, AttributeError, KeyError, IndexError):
        pass


def has_persisted_callback_state() -> bool:
    state = _load_state()
    has_callbacks = bool(state.get("om") or state.get("scriptjob"))
    if not has_callbacks:
        _clear_state()
    return has_callbacks


def _scriptjob_exists(job_id: int) -> bool:
    try:
        return bool(cmds.scriptJob(exists=int(job_id)))
    except (RuntimeError, ValueError, TypeError, AttributeError, KeyError, IndexError):
        return False


def _kill_scriptjob(job_id: int) -> None:
    try:
        if _scriptjob_exists(int(job_id)):
            cmds.scriptJob(kill=int(job_id), force=True)
    except (RuntimeError, ValueError, TypeError, AttributeError, KeyError, IndexError):
        pass


def _remove_om_callback(callback_id: int) -> None:
    removed = False
    if om:
        try:
            om.MMessage.removeCallback(int(callback_id))
            removed = True
        except (RuntimeError, ValueError, TypeError, AttributeError, KeyError, IndexError):
            pass
    if not removed and om1:
        try:
            om1.MMessage.removeCallback(int(callback_id))
        except (RuntimeError, ValueError, TypeError, AttributeError, KeyError, IndexError):
            pass


def cleanup_orphaned_callbacks() -> None:
    """
    Best-effort cleanup for callbacks that may have survived a python reload.
    Safe to call even if Maya APIs are partially unavailable.
    """
    state = _load_state()

    # OpenMaya callbacks
    for cb_id in state.get("om", []) or []:
        _remove_om_callback(int(cb_id))

    # scriptJobs
    for job_id in state.get("scriptjob", []) or []:
        _kill_scriptjob(int(job_id))

    _clear_state()


def cleanup_orphaned_widgets() -> None:
    """Delete transient TKM widgets that survived an interrupted reload."""
    app = QtWidgets.QApplication.instance()
    if app is None:
        return
    all_widgets = getattr(app, "allWidgets", None)
    if not callable(all_widgets):
        return
    for widget in list(all_widgets()):
        try:
            if not _is_tkm_cleanup_widget(widget):
                continue
            _safe_delete_widget(widget)
        except Exception:
            pass


def cleanup_previous_runtime(current=None) -> None:
    """Shut down the runtime retained by Maya's QApplication across reloads."""
    app = QtWidgets.QApplication.instance()
    if app is None:
        return
    previous = getattr(app, _APP_RUNTIME_ATTRIBUTE, None)
    if previous is None or previous is current:
        return
    if QtCompat.isValid(previous):
        try:
            previous.shutdown()
        except Exception:
            pass
        try:
            previous.deleteLater()
        except Exception:
            pass
    try:
        delattr(app, _APP_RUNTIME_ATTRIBUTE)
    except Exception:
        pass


def has_previous_runtime(current=None) -> bool:
    app = QtWidgets.QApplication.instance()
    if app is None:
        return False
    previous = getattr(app, _APP_RUNTIME_ATTRIBUTE, None)
    return previous is not None and previous is not current


def _safe_process_events() -> None:
    app = QtWidgets.QApplication.instance()
    if app is None:
        return
    try:
        app.processEvents()
        app.sendPostedEvents(None, QtCore.QEvent.DeferredDelete)
        app.processEvents()
    except Exception:
        pass


def delete_widget(widget) -> None:
    """Hide and schedule a widget for deletion without making it top-level."""
    if widget is None:
        return
    try:
        if not QtCompat.isValid(widget):
            return
    except Exception:
        pass
    try:
        widget.blockSignals(True)
    except Exception:
        pass
    try:
        widget.hide()
    except Exception:
        pass
    try:
        parent = widget.parentWidget()
        layout = parent.layout() if parent is not None and QtCompat.isValid(parent) else None
        if layout is not None:
            layout.removeWidget(widget)
    except Exception:
        pass
    try:
        widget.close()
    except Exception:
        pass
    try:
        widget.deleteLater()
    except Exception:
        pass


def _safe_delete_widget(widget) -> None:
    if widget is None:
        return
    delete_tint = getattr(widget, "delete_tint", None)
    if callable(delete_tint):
        try:
            delete_tint()
            return
        except Exception:
            pass
    delete_widget(widget)


def _is_tkm_cleanup_widget(widget) -> bool:
    if widget is None:
        return False
    try:
        if not QtCompat.isValid(widget):
            return False
    except Exception:
        return False
    try:
        if bool(widget.property(_TRANSIENT_WIDGET_PROPERTY)) or bool(widget.property(_TKM_FLOATING_WIDGET_PROPERTY)):
            return True
    except Exception:
        pass
    try:
        if widget.__class__.__name__ == "TimelineTint":
            return True
    except Exception:
        pass
    return False


def cleanup_tkm_widgets(process_events=True) -> None:
    cleanup_orphaned_widgets()
    if process_events:
        _safe_process_events()


def cleanup_workspace_controls(process_events=True) -> None:
    for control_name in _TKM_WORKSPACE_CONTROLS:
        try:
            if cmds.workspaceControl(control_name, q=True, exists=True):
                cmds.deleteUI(control_name, control=True)
        except Exception:
            try:
                if cmds.control(control_name, exists=True):
                    cmds.deleteUI(control_name)
            except Exception:
                pass
        try:
            if cmds.workspaceControlState(control_name, exists=True):
                cmds.workspaceControlState(control_name, remove=True)
        except Exception:
            pass
    if process_events:
        _safe_process_events()


def shutdown_tool_modules() -> None:
    """Stop module-level workers, dialogs, native contexts, and exception hooks."""
    module_cleanups = (
        ("TheKeyMachine.tools.bug_report.controller", "uninstall_bug_exception_handler"),
        ("TheKeyMachine.maya.shelf", "cleanup_open_menus"),
        ("TheKeyMachine.tools.common", "finish_active_progress"),
        ("TheKeyMachine.tools.graph_toolbar.controller", "shutdown_graph_toolbar_runtime"),
        ("TheKeyMachine.ui.tooltips", "shutdown"),
        ("TheKeyMachine.ui.widgets.timeline", "shutdown"),
        ("TheKeyMachine.maya.runtime", "shutdown_all"),
    )
    for module_name, attr_name in module_cleanups:
        module = sys.modules.get(module_name)
        if module is None:
            continue
        cleanup = getattr(module, attr_name, None)
        if not callable(cleanup):
            continue
        try:
            cleanup()
        except Exception:
            pass

    api_modules = [
        module
        for name, module in tuple(sys.modules.items())
        if name.startswith("TheKeyMachine.tools.") and name.endswith(".api") and module is not None
    ]
    for module in api_modules:
        for attr_name in ("cleanup", "shutdown"):
            cleanup = getattr(module, attr_name, None)
            if callable(cleanup):
                try:
                    cleanup()
                except Exception:
                    pass
                break

    registry_module = sys.modules.get("TheKeyMachine.tools.registry")
    reset_cache = getattr(registry_module, "reset_package_cache", None)
    if callable(reset_cache):
        reset_cache()

    trigger_module = sys.modules.get("TheKeyMachine.core.trigger")
    reset_registry = getattr(trigger_module, "reset_registry", None)
    if callable(reset_registry):
        reset_registry()


def cleanup_for_reload(delete_workspace=True, process_events=True) -> None:
    """Best-effort full cleanup before unloading, reloading, or replacing TKM files."""
    shutdown_tool_modules()
    shutdown_runtime_manager(cleanup_widgets=False)
    cleanup_tkm_widgets(process_events=False)
    if delete_workspace:
        cleanup_workspace_controls(process_events=False)
    if process_events:
        _safe_process_events()


def _qt_modifiers_to_mask(modifiers) -> int:
    mask = 0
    try:
        if modifiers & QtCore.Qt.ShiftModifier:
            mask |= 1
        if modifiers & QtCore.Qt.ControlModifier:
            mask |= 4
        if modifiers & QtCore.Qt.AltModifier:
            mask |= 8
    except (RuntimeError, ValueError, TypeError, AttributeError, KeyError, IndexError):
        pass
    return mask


def get_modifier_mask() -> int:
    manager = _MANAGER
    if manager is not None:
        state = manager.get_modifier_state()
        return (1 if state["shift"] else 0) | (4 if state["ctrl"] else 0) | (8 if state["alt"] else 0)

    try:
        app = QtWidgets.QApplication.instance()
        if app:
            return _qt_modifiers_to_mask(app.keyboardModifiers())
    except (RuntimeError, ValueError, TypeError, AttributeError, KeyError, IndexError):
        pass

    try:
        return int(cmds.getModifiers())
    except (RuntimeError, ValueError, TypeError, AttributeError, KeyError, IndexError):
        return 0


def get_modifier_state() -> Dict[str, bool]:
    mask = get_modifier_mask()
    return {
        "ctrl": bool(mask & 4),
        "shift": bool(mask & 1),
        "alt": bool(mask & 8),
    }


@contextmanager
def suppress_undo_notifications():
    """Prevent tool-owned Undo sampling from cancelling active interactions."""
    manager = get_runtime_manager()
    suppression_count = getattr(manager, "_undo_notification_suppression", 0)
    manager._undo_notification_suppression = suppression_count + 1
    try:
        yield
    finally:
        manager._undo_notification_suppression = max(0, manager._undo_notification_suppression - 1)


class RuntimeManager(QtCore.QObject):
    callback_fired = QtCore.Signal(str)

    # Common / high-value signals
    scene_opened = QtCore.Signal()
    scene_new = QtCore.Signal()
    scene_saved = QtCore.Signal()
    scene_before_saved = QtCore.Signal()

    selection_changed = QtCore.Signal()
    time_changed = QtCore.Signal()
    undo_performed = QtCore.Signal()
    graph_editor_opened = QtCore.Signal()

    modifiers_changed = QtCore.Signal(bool, bool, bool)
    overshootChanged = QtCore.Signal(bool)
    eulerFilterChanged = QtCore.Signal(bool)
    nudgeValueChanged = QtCore.Signal(int)
    backgroundRunnerChanged = QtCore.Signal(str, bool)
    backgroundRunnerTriggered = QtCore.Signal(str)
    playbackStateChanged = QtCore.Signal(bool)
    toolStateChanged = QtCore.Signal(str, bool)
    controlStateChanged = QtCore.Signal(str, object)

    def __init__(self, parent=None):
        super().__init__(parent=parent)
        self._started = False
        self._om_callbacks: Dict[str, List[int]] = {}
        self._scriptjobs: Dict[str, List[int]] = {}
        self._signal_connections: Dict[str, List[tuple]] = {}
        self._managed_widgets: Dict[str, QtWidgets.QWidget] = {}
        self._tool_states: Dict[str, bool] = {}
        self._control_states: Dict[str, Any] = {}

        self._graph_editor_visible = False
        self._graph_editor_watch_enabled = False

        self._ui_watch_timer = QtCore.QTimer(self)
        self._ui_watch_timer.setSingleShot(True)
        self._ui_watch_timer.timeout.connect(self._check_graph_editor_state)

        self._modifier_watch_enabled = True
        self._ctrl_pressed = False
        self._shift_pressed = False
        self._alt_pressed = False
        self._playback_active = False
        self._undo_notification_suppression = 0
        self._anim_curve_coalesce_depth = 0
        self._anim_curve_coalesced = {}
        self._anim_curve_coalesce_preset = None

        self._event_filter_installed = False
        self._event_filter_watchers: Dict[str, Callable[..., Any]] = {}
        self._background_runner_controller = None
        self._defer_callback_persistence = False

        self._background_start_timer = QtCore.QTimer(self)
        self._background_start_timer.setSingleShot(True)
        self._background_start_timer.timeout.connect(self._start_background_runners)

    # ----------------------------
    # Lifecycle
    # ----------------------------
    def start(self) -> None:
        if self._started:
            return

        cleanup_previous_runtime(current=self)
        cleanup_orphaned_callbacks()
        cleanup_orphaned_widgets()

        app = QtWidgets.QApplication.instance()
        if app is not None:
            setattr(app, _APP_RUNTIME_ATTRIBUTE, self)

        self._defer_callback_persistence = True
        try:
            # Built-in, long-lived callbacks while the tool is loaded.
            self._install_scene_callbacks()
            self._install_selection_callback()
            self._install_time_changed_callback()
            self._install_undo_callback()
            self._install_playback_state_callback()
            self._refresh_event_filter_state()
        except Exception:
            self._defer_callback_persistence = False
            self._remove_event_filter()
            self._remove_all()
            _clear_state()
            if app is not None and getattr(app, _APP_RUNTIME_ATTRIBUTE, None) is self:
                try:
                    delattr(app, _APP_RUNTIME_ATTRIBUTE)
                except Exception:
                    pass
            raise

        self._defer_callback_persistence = False
        self._started = True
        self._persist_state()
        self._background_start_timer.start(0)

    def shutdown(self, cleanup_widgets: bool = True) -> None:
        self._shutdown_background_runners()
        self._remove_event_filter()
        self._shutdown_tool_controllers()
        self._clear_managed_widgets()
        if cleanup_widgets:
            cleanup_orphaned_widgets()
        # Native tool contexts must be removed before their plug-ins unload.
        try:
            from TheKeyMachine.maya import runtime as maya_runtime
            maya_runtime.shutdown_all()
        except Exception:
            pass
        self._remove_all()
        self._started = False
        _clear_state()
        app = QtWidgets.QApplication.instance()
        if app is not None and getattr(app, _APP_RUNTIME_ATTRIBUTE, None) is self:
            try:
                delattr(app, _APP_RUNTIME_ATTRIBUTE)
            except Exception:
                pass

    def _shutdown_tool_controllers(self) -> None:
        cleanups = []
        try:
            from TheKeyMachine.tools.animation_offset import api as animationOffsetApi
            cleanups.append(animationOffsetApi.cleanup)
        except Exception:
            pass
        try:
            from TheKeyMachine.tools.micro_move import api as microMoveApi
            cleanups.append(microMoveApi.cleanup)
        except Exception:
            pass
        try:
            from TheKeyMachine.tools.depth_mover import api as depthMoverApi
            cleanups.append(depthMoverApi.cleanup)
        except Exception:
            pass
        try:
            from TheKeyMachine.tools.animation_tools import api as animationToolsApi
            cleanups.append(animationToolsApi.cleanup)
        except Exception:
            pass
        try:
            from TheKeyMachine.maya import viewport as viewportApi
            cleanups.append(viewportApi.cleanup)
        except Exception:
            pass

        for cleanup in cleanups:
            try:
                cleanup()
            except Exception:
                pass

    # ----------------------------
    # Registration helpers
    # ----------------------------
    def add_maya_event_callback(
        self,
        event_name: str,
        handler: Callable[..., Any],
        key: Optional[str] = None,
        one_shot: bool = False,
    ) -> Optional[int]:
        """
        Adds a Maya event callback using OpenMaya (preferred) and tracks it for cleanup.
        """
        if not om:
            return None

        callback_key = key or f"event:{event_name}"
        cb_id_holder: Dict[str, Optional[int]] = {"id": None}

        def _wrapped(*args):
            if one_shot and cb_id_holder["id"] is not None:
                self._remove_om_callback_id(cb_id_holder["id"])
            try:
                handler(*args)
            finally:
                self._emit(callback_key)

        cb_id = om.MEventMessage.addEventCallback(event_name, _wrapped)
        cb_id_holder["id"] = int(cb_id)
        self._track_om(callback_key, int(cb_id))
        return int(cb_id)

    def add_scriptjob(
        self,
        *,
        event: Any = None,
        condition: Any = None,
        key: str,
        callback: Callable[..., Any],
        run_once: bool = False,
        kill_with_scene: bool = False,
    ) -> Optional[int]:
        """
        Adds a Maya scriptJob and tracks it for cleanup.
        Prefer add_maya_event_callback() when possible; scriptJobs exist for edge cases.
        """

        def _wrapped(*args):
            try:
                callback(*args)
            finally:
                self._emit(key)

        try:
            if condition is not None:
                if isinstance(condition, (list, tuple)) and len(condition) == 2:
                    job_id = cmds.scriptJob(
                        conditionChange=(condition[0], _wrapped),
                        runOnce=bool(run_once),
                        killWithScene=bool(kill_with_scene),
                    )
                else:
                    job_id = cmds.scriptJob(
                        conditionChange=(condition, _wrapped),
                        runOnce=bool(run_once),
                        killWithScene=bool(kill_with_scene),
                    )
            elif isinstance(event, (list, tuple)) and len(event) == 2:
                job_id = cmds.scriptJob(event=(event[0], _wrapped), runOnce=bool(run_once), killWithScene=bool(kill_with_scene))
            else:
                job_id = cmds.scriptJob(event=(event, _wrapped), runOnce=bool(run_once), killWithScene=bool(kill_with_scene))
        except (RuntimeError, ValueError, TypeError, AttributeError, KeyError, IndexError):
            return None

        if job_id is None:
            return None
        try:
            job_id = int(job_id)
        except (TypeError, ValueError):
            return None
        self._track_scriptjob(key, job_id)
        return job_id

    def is_playing(self) -> bool:
        return bool(self._playback_active)

    def add_node_attribute_changed_callback(
        self,
        node: Any,
        handler: Callable[..., Any],
        *,
        key: str,
        client_data: Any = None,
    ) -> Optional[int]:
        if not om:
            return None

        mobject = maya_api.mobject_from_node(node)
        if mobject is None:
            return None

        def _wrapped(*args):
            try:
                handler(*args)
            finally:
                self._emit(key)

        try:
            cb_id = om.MNodeMessage.addAttributeChangedCallback(mobject, _wrapped, client_data)
        except (RuntimeError, ValueError, TypeError, AttributeError, KeyError, IndexError):
            return None

        self._track_om(key, int(cb_id))
        return int(cb_id)

    def add_node_attribute_changed_callbacks(
        self,
        nodes: Any,
        handler: Callable[..., Any],
        *,
        key: str,
    ) -> List[int]:
        """Register the same attribute callback on many nodes with one state write."""
        if not om:
            return []
        callback_ids = []
        for node in nodes or []:
            mobject = maya_api.mobject_from_node(node)
            if mobject is None:
                continue

            def _make_callback(node_name):
                def _wrapped(*args):
                    try:
                        handler(*(args + (node_name,)))
                    finally:
                        self._emit(key)
                return _wrapped

            try:
                callback_id = om.MNodeMessage.addAttributeChangedCallback(
                    mobject,
                    _make_callback(node),
                )
            except (RuntimeError, ValueError, TypeError, AttributeError, KeyError, IndexError):
                continue
            callback_ids.append(int(callback_id))

        if callback_ids:
            self._om_callbacks.setdefault(key, []).extend(callback_ids)
            self._persist_state()
        return callback_ids

    def add_node_lifecycle_callbacks(self, node_type, handler, *, key):
        """Own DG creation/deletion callbacks, including non-DAG anim curves."""
        if not om:
            return []
        result = []
        for register in (om.MDGMessage.addNodeAddedCallback, om.MDGMessage.addNodeRemovedCallback):
            callback_id = register(handler, node_type)
            self._track_om(key, int(callback_id))
            result.append(int(callback_id))
        return result

    def add_dag_change_callback(self, handler: Callable[..., Any], *, key: str) -> Optional[int]:
        """Register one callback for DAG hierarchy changes and own its cleanup."""
        if not om:
            return None

        def _wrapped(*args):
            try:
                handler(*args)
            finally:
                self._emit(key)

        try:
            cb_id = om.MDagMessage.addAllDagChangesCallback(_wrapped)
        except (RuntimeError, ValueError, TypeError, AttributeError, KeyError, IndexError):
            return None
        self._track_om(key, int(cb_id))
        return int(cb_id)

    def add_anim_curve_edited_callback(
        self,
        handler: Callable[..., Any],
        *,
        key: str,
        coalesce: bool = True,
    ) -> Optional[int]:
        """Register Maya's batched animation-curve edit callback."""
        if not oma:
            return None

        queue_key = object()

        def _wrapped(*args):
            if coalesce and self._anim_curve_coalesce_depth:
                self._queue_anim_curve_callback(queue_key, handler, key, args)
                return
            try:
                handler(*args)
            finally:
                self._emit(key)

        try:
            cb_id = oma.MAnimMessage.addAnimCurveEditedCallback(_wrapped)
        except (RuntimeError, ValueError, TypeError, AttributeError, KeyError, IndexError):
            return None
        self._track_om(key, int(cb_id))
        return int(cb_id)

    def add_anim_keyframe_edited_callback(self, handler: Callable[..., Any], *, key: str) -> Optional[int]:
        """Register Maya's keyframe edit callback and own its cleanup."""
        if not oma:
            return None

        def _wrapped(*args):
            try:
                handler(*args)
            finally:
                self._emit(key)

        try:
            cb_id = oma.MAnimMessage.addAnimKeyframeEditedCallback(_wrapped)
        except (RuntimeError, ValueError, TypeError, AttributeError, KeyError, IndexError):
            return None
        self._track_om(key, int(cb_id))
        return int(cb_id)

    def add_3d_view_pre_render_callback(
        self,
        panel: str,
        handler: Callable[..., Any],
        *,
        key: str,
    ) -> Optional[int]:
        """Register a 3D-view pre-render callback and own its cleanup."""
        if not omui or not panel:
            return None

        def _wrapped(*args):
            try:
                handler(*args)
            finally:
                self._emit(key)

        try:
            cb_id = omui.MUiMessage.add3dViewPreRenderMsgCallback(str(panel), _wrapped)
        except (RuntimeError, ValueError, TypeError, AttributeError, KeyError, IndexError):
            return None
        self._track_om(key, int(cb_id))
        return int(cb_id)

    def _queue_anim_curve_callback(self, queue_key, handler, key, args):
        entry = self._anim_curve_coalesced.setdefault(
            queue_key,
            {"handler": handler, "key": key, "objects": {}},
        )
        if self._anim_curve_coalesce_preset is not None:
            if not entry["objects"]:
                entry["objects"].update(self._anim_curve_coalesce_preset)
            return
        try:
            curves = args[0]
            for index in range(len(curves)):
                handle = om.MObjectHandle(curves[index])
                entry["objects"][int(handle.hashCode())] = handle
        except Exception:
            pass

    def _flush_anim_curve_callbacks(self):
        queued = list(self._anim_curve_coalesced.values())
        self._anim_curve_coalesced.clear()
        for entry in queued:
            curves = om.MObjectArray()
            for handle in entry["objects"].values():
                try:
                    if handle.isValid() and handle.isAlive():
                        curves.append(handle.object())
                except Exception:
                    continue
            try:
                entry["handler"](curves, None)
            except Exception:
                pass
            finally:
                self._emit(entry["key"])

    @contextmanager
    def coalesce_anim_curve_callbacks(self, curves=None):
        """Deliver bulk secondary curve edits once per registered handler."""
        if not self._anim_curve_coalesce_depth and curves is not None:
            preset = {}
            for curve in curves:
                try:
                    handle = om.MObjectHandle(curve)
                    preset[int(handle.hashCode())] = handle
                except Exception:
                    continue
            self._anim_curve_coalesce_preset = preset
        self._anim_curve_coalesce_depth += 1
        try:
            yield
        finally:
            self._anim_curve_coalesce_depth = max(
                0, self._anim_curve_coalesce_depth - 1
            )
            if not self._anim_curve_coalesce_depth:
                try:
                    self._flush_anim_curve_callbacks()
                finally:
                    self._anim_curve_coalesce_preset = None

    def connect_signal(self, signal: Any, handler: Callable[..., Any], *, key: str, unique: bool = True) -> bool:
        if signal is None or handler is None:
            return False
        if unique:
            self.disconnect_callbacks(key)
        try:
            signal.connect(handler)
        except (RuntimeError, ValueError, TypeError, AttributeError, KeyError, IndexError):
            return False
        self._signal_connections.setdefault(key, []).append((signal, handler))
        return True

    def disconnect_callbacks(self, key: str) -> None:
        # Callback groups can contain thousands of scene-node watchers. Remove
        # the group in one pass and persist once instead of rewriting the
        # optionVar after every callback.
        for cb_id in self._om_callbacks.pop(key, []) or []:
            _remove_om_callback(int(cb_id))

        for job_id in list(self._scriptjobs.get(key, []) or []):
            _kill_scriptjob(int(job_id))
        self._scriptjobs.pop(key, None)

        for signal, handler in self._signal_connections.pop(key, []) or []:
            try:
                signal.disconnect(handler)
            except (RuntimeError, ValueError, TypeError, AttributeError, KeyError, IndexError):
                pass

        if self._event_filter_watchers.pop(key, None) is not None:
            self._refresh_event_filter_state()

        self._persist_state()

    def register_managed_widget(self, widget, key: Optional[str] = None, owner=None):
        if widget is None:
            return None

        try:
            widget.setProperty(_TRANSIENT_WIDGET_PROPERTY, True)
        except Exception:
            pass

        if key:
            existing = self._managed_widgets.get(key)
            if existing is not None and existing is not widget:
                self._safe_delete_widget(existing)
            self._managed_widgets[key] = widget

        def _cleanup(*_args):
            if not key:
                return
            if self._managed_widgets.get(key) is widget:
                self._managed_widgets.pop(key, None)

        try:
            widget.destroyed.connect(_cleanup)
        except (RuntimeError, ValueError, TypeError, AttributeError, KeyError, IndexError):
            pass

        if owner is not None and hasattr(owner, "destroyed"):
            try:
                owner.destroyed.connect(lambda *_: self._safe_delete_widget(widget))
            except (RuntimeError, ValueError, TypeError, AttributeError, KeyError, IndexError):
                pass

        return widget

    def clear_managed_widget(self, key: str) -> None:
        widget = self._managed_widgets.pop(key, None)
        self._safe_delete_widget(widget)

    def background_runners(self):
        if self._background_runner_controller is None:
            from TheKeyMachine.tools.background_runners import service as background_runners

            self._background_runner_controller = background_runners.get_controller(self)
        return self._background_runner_controller

    def set_tool_state(self, key: str, state: bool, *, emit: bool = True) -> bool:
        if not key:
            return False
        state = bool(state)
        changed = self._tool_states.get(key) != state
        if not changed and emit:
            return state
        self._tool_states[key] = state
        self.set_control_state(key, state, emit=emit)
        if emit:
            try:
                self.toolStateChanged.emit(str(key), state)
            except (RuntimeError, ValueError, TypeError, AttributeError, KeyError, IndexError):
                pass
        return state

    def set_control_state(self, key: str, value: Any, *, emit: bool = True):
        """Publish an arbitrary shared UI state value."""
        if not key:
            return value
        changed = key not in self._control_states or self._control_states[key] != value
        self._control_states[key] = value
        if emit and changed:
            try:
                self.controlStateChanged.emit(str(key), value)
            except (RuntimeError, ValueError, TypeError, AttributeError, KeyError, IndexError):
                pass
        return value

    def has_control_state(self, key: str) -> bool:
        return bool(key and key in self._control_states)

    def get_control_state(self, key: str, default=None):
        return self._control_states.get(key, default) if key else default

    def get_tool_state(self, key: str, default: bool = False) -> bool:
        if not key:
            return bool(default)
        return bool(self._tool_states.get(key, default))

    def sync_tool_state(self, key: str, getter: Callable[[], Any]) -> bool:
        if not key or not callable(getter):
            return False
        try:
            state = bool(getter())
        except (RuntimeError, ValueError, TypeError, AttributeError, KeyError, IndexError):
            state = False
        return self.set_tool_state(key, state)

    # ----------------------------
    # Internal installs
    # ----------------------------
    def _install_selection_callback(self) -> None:
        if not om:
            return

        def _on_selection_changed(*_args):
            self._emit("selection_changed")
            try:
                self.selection_changed.emit()
            except (RuntimeError, ValueError, TypeError, AttributeError, KeyError, IndexError):
                pass

        cb_id = om.MEventMessage.addEventCallback("SelectionChanged", _on_selection_changed)
        self._track_om("selection_changed", int(cb_id))

    def _install_time_changed_callback(self) -> None:
        if not om:
            return

        def _on_time_changed(*_args):
            self._emit("time_changed")
            try:
                self.time_changed.emit()
            except (RuntimeError, ValueError, TypeError, AttributeError, KeyError, IndexError):
                pass

        cb_id = om.MEventMessage.addEventCallback("timeChanged", _on_time_changed)
        self._track_om("time_changed", int(cb_id))

    def _query_playback_state(self) -> bool:
        try:
            return bool(cmds.play(query=True, state=True))
        except (RuntimeError, ValueError, TypeError, AttributeError, KeyError, IndexError):
            return False

    def _install_playback_state_callback(self) -> None:
        self._playback_active = self._query_playback_state()

        def _on_playback_state_changed(*_args):
            playing = self._query_playback_state()
            if playing == self._playback_active:
                return
            self._playback_active = playing
            try:
                self.playbackStateChanged.emit(playing)
            except (RuntimeError, ValueError, TypeError, AttributeError, KeyError, IndexError):
                pass

        self.add_scriptjob(
            condition="playingBack",
            key="playback_state",
            callback=_on_playback_state_changed,
        )

    def _install_undo_callback(self) -> None:
        if not om:
            return

        def _on_undo(*_args):
            if getattr(self, "_undo_notification_suppression", 0):
                return
            self._emit("undo_performed")
            try:
                self.undo_performed.emit()
            except (RuntimeError, ValueError, TypeError, AttributeError, KeyError, IndexError):
                pass

        cb_id = om.MEventMessage.addEventCallback("Undo", _on_undo)
        self._track_om("undo_performed", int(cb_id))

    def _install_scene_callbacks(self) -> None:
        if not om:
            return

        def _after_open(*_args):
            self._emit("scene_opened")
            try:
                self.scene_opened.emit()
            except (RuntimeError, ValueError, TypeError, AttributeError, KeyError, IndexError):
                pass

        def _after_new(*_args):
            self._emit("scene_new")
            try:
                self.scene_new.emit()
            except (RuntimeError, ValueError, TypeError, AttributeError, KeyError, IndexError):
                pass

        def _after_save(*_args):
            self._emit("scene_saved")
            try:
                self.scene_saved.emit()
            except (RuntimeError, ValueError, TypeError, AttributeError, KeyError, IndexError):
                pass

        def _before_save(*_args):
            self._emit("scene_before_saved")
            try:
                self.scene_before_saved.emit()
            except (RuntimeError, ValueError, TypeError, AttributeError, KeyError, IndexError):
                pass

        callbacks = (
            ("scene_opened", om.MSceneMessage.kAfterOpen, _after_open),
            ("scene_new", om.MSceneMessage.kAfterNew, _after_new),
            ("scene_saved", om.MSceneMessage.kAfterSave, _after_save),
            ("scene_before_saved", om.MSceneMessage.kBeforeSave, _before_save),
        )
        for key, event, handler in callbacks:
            cb_id = om.MSceneMessage.addCallback(event, handler)
            self._track_om(key, int(cb_id))

    def _start_background_runners(self) -> None:
        if not self._started:
            return
        try:
            self.background_runners().start_enabled()
        except Exception:
            pass

    def _shutdown_background_runners(self) -> None:
        try:
            self._background_start_timer.stop()
        except (RuntimeError, ValueError, TypeError, AttributeError, KeyError, IndexError):
            pass
        background_runners = sys.modules.get("TheKeyMachine.tools.background_runners.service")
        shutdown_controller = getattr(background_runners, "shutdown_controller", None)
        if callable(shutdown_controller):
            try:
                shutdown_controller()
            except Exception:
                pass
        elif self._background_runner_controller is not None:
            try:
                self._background_runner_controller.shutdown()
            except Exception:
                pass
        self._background_runner_controller = None

    def _install_event_filter(self) -> None:
        if self._event_filter_installed:
            return
        try:
            app = QtWidgets.QApplication.instance()
            if app:
                app.installEventFilter(self)
                self._event_filter_installed = True
        except (RuntimeError, ValueError, TypeError, AttributeError, KeyError, IndexError):
            pass
        self._sync_enabled_ui_watchers()

    def _remove_event_filter(self) -> None:
        if not self._event_filter_installed:
            return
        try:
            app = QtWidgets.QApplication.instance()
            if app:
                app.removeEventFilter(self)
        except (RuntimeError, ValueError, TypeError, AttributeError, KeyError, IndexError):
            pass
        self._event_filter_installed = False
        self._reset_graph_editor_watch()
        self._reset_modifier_state()

    def set_graph_editor_watch_enabled(self, enabled: bool) -> None:
        self._graph_editor_watch_enabled = bool(enabled)
        self._refresh_event_filter_state()
        if self._graph_editor_watch_enabled:
            self._schedule_graph_editor_check()
        else:
            self._reset_graph_editor_watch()

    def set_modifier_watch_enabled(self, enabled: bool) -> None:
        self._modifier_watch_enabled = bool(enabled)
        self._refresh_event_filter_state()
        if self._modifier_watch_enabled:
            self._sync_modifier_state()
        else:
            self._reset_modifier_state()

    def _refresh_event_filter_state(self) -> None:
        if self._should_install_event_filter():
            self._install_event_filter()
        else:
            self._remove_event_filter()

    def _should_install_event_filter(self) -> bool:
        return bool(self._graph_editor_watch_enabled or self._modifier_watch_enabled or self._event_filter_watchers)

    def add_event_filter_watcher(self, key: str, callback: Callable[..., Any]) -> bool:
        """Delegate an app-level ``QApplication.installEventFilter()`` to the
        shared runtime instead of a tool self-managing its own -- every event
        the app sees is forwarded to *callback(obj, event)* until
        ``remove_event_filter_watcher()``/``disconnect_callbacks(key)`` tears
        it down. One real app-level filter backs every registered watcher,
        the same way one set of scriptJobs backs every ``add_scriptjob()``
        caller; *key* both identifies the watcher and doubles as its
        ``disconnect_callbacks()`` cleanup group, so a tool window can retire
        its scriptjobs and its event-filter watcher with a single call.
        """
        if not key or not callable(callback):
            return False
        self._event_filter_watchers[key] = callback
        self._refresh_event_filter_state()
        return True

    def remove_event_filter_watcher(self, key: str) -> None:
        if self._event_filter_watchers.pop(key, None) is not None:
            self._refresh_event_filter_state()

    def _sync_enabled_ui_watchers(self) -> None:
        if self._graph_editor_watch_enabled:
            self._schedule_graph_editor_check()
        if self._modifier_watch_enabled:
            self._sync_modifier_state()

    def _reset_graph_editor_watch(self) -> None:
        self._graph_editor_visible = False
        try:
            self._ui_watch_timer.stop()
        except (RuntimeError, ValueError, TypeError, AttributeError, KeyError, IndexError):
            pass

    def _reset_modifier_state(self) -> None:
        self._set_modifier_state(False, False, False)

    def _set_modifier_state(self, ctrl: bool, shift: bool, alt: bool) -> None:
        ctrl = bool(ctrl)
        shift = bool(shift)
        alt = bool(alt)
        if (ctrl, shift, alt) == (self._ctrl_pressed, self._shift_pressed, self._alt_pressed):
            return
        self._ctrl_pressed = ctrl
        self._shift_pressed = shift
        self._alt_pressed = alt
        self._emit("modifiers_changed")
        try:
            self.modifiers_changed.emit(ctrl, shift, alt)
        except (RuntimeError, ValueError, TypeError, AttributeError, KeyError, IndexError):
            pass

    def _sync_modifier_state(self, modifiers=None) -> None:
        if not self._modifier_watch_enabled:
            return
        try:
            if modifiers is None:
                app = QtWidgets.QApplication.instance()
                modifiers = app.keyboardModifiers() if app else QtCore.Qt.NoModifier
        except (RuntimeError, ValueError, TypeError, AttributeError, KeyError, IndexError):
            modifiers = QtCore.Qt.NoModifier

        self._set_modifier_state(
            bool(modifiers & QtCore.Qt.ControlModifier),
            bool(modifiers & QtCore.Qt.ShiftModifier),
            bool(modifiers & QtCore.Qt.AltModifier),
        )

    def get_modifier_state(self) -> Dict[str, bool]:
        return {
            "ctrl": self._ctrl_pressed,
            "shift": self._shift_pressed,
            "alt": self._alt_pressed,
        }

    def _schedule_graph_editor_check(self) -> None:
        if not self._ui_watch_timer.isActive():
            self._ui_watch_timer.start(0)

    def _check_graph_editor_state(self) -> None:
        try:
            graph_vis = cmds.getPanel(vis=True) or []
            visible = "graphEditor1" in graph_vis
        except (RuntimeError, ValueError, TypeError, AttributeError, KeyError, IndexError):
            visible = False

        if visible == self._graph_editor_visible:
            return

        self._graph_editor_visible = visible
        if visible:
            self._emit_graph_editor_opened()

    def _emit_graph_editor_opened(self) -> None:
        try:
            if not self._graph_editor_visible:
                return
            self._emit("graph_editor_opened")
            self.graph_editor_opened.emit()
        except (RuntimeError, ValueError, TypeError, AttributeError, KeyError, IndexError):
            pass

    def eventFilter(self, obj, event):
        try:
            event_type = event.type()
        except (RuntimeError, ValueError, TypeError, AttributeError, KeyError, IndexError):
            return False
        self._handle_modifier_event(event_type, event)
        self._handle_graph_editor_event(obj, event_type)
        for watcher in list(self._event_filter_watchers.values()):
            try:
                watcher(obj, event)
            except (RuntimeError, ValueError, TypeError, AttributeError, KeyError, IndexError):
                pass
        return False

    def _handle_modifier_event(self, event_type, event) -> None:
        if not self._modifier_watch_enabled:
            return
        if event_type in {QtCore.QEvent.KeyPress, QtCore.QEvent.KeyRelease, QtCore.QEvent.ShortcutOverride}:
            try:
                self._sync_modifier_state(event.modifiers())
            except (RuntimeError, ValueError, TypeError, AttributeError, KeyError, IndexError):
                self._sync_modifier_state()
            return
        if event_type in {QtCore.QEvent.ApplicationDeactivate, QtCore.QEvent.WindowDeactivate, QtCore.QEvent.FocusOut}:
            self._reset_modifier_state()

    def _handle_graph_editor_event(self, obj, event_type) -> None:
        if not self._graph_editor_watch_enabled:
            return
        if event_type not in {
            QtCore.QEvent.Show,
            QtCore.QEvent.Hide,
            QtCore.QEvent.Close,
            QtCore.QEvent.Destroy,
            QtCore.QEvent.WindowActivate,
        }:
            return
        if self._looks_like_graph_editor(obj):
            self._schedule_graph_editor_check()

    def _looks_like_graph_editor(self, obj) -> bool:
        try:
            object_name = obj.objectName() or ""
        except (RuntimeError, ValueError, TypeError, AttributeError, KeyError, IndexError):
            object_name = ""

        try:
            window_title = obj.windowTitle() or ""
        except (RuntimeError, ValueError, TypeError, AttributeError, KeyError, IndexError):
            window_title = ""

        return "graphEditor1" in object_name or "Graph Editor" in window_title

    # ----------------------------
    # Emit + tracking
    # ----------------------------
    def _emit(self, key: str) -> None:
        try:
            self.callback_fired.emit(key)
        except (RuntimeError, ValueError, TypeError, AttributeError, KeyError, IndexError):
            pass

    def _track_om(self, key: str, cb_id: int) -> None:
        self._om_callbacks.setdefault(key, []).append(int(cb_id))
        self._persist_state()

    def _track_scriptjob(self, key: str, job_id: int) -> None:
        self._scriptjobs.setdefault(key, []).append(int(job_id))
        self._persist_state()

    def _persist_state(self) -> None:
        if self._defer_callback_persistence:
            return
        state = {
            "om": sorted({cb_id for ids in self._om_callbacks.values() for cb_id in ids}),
            "scriptjob": sorted({job_id for ids in self._scriptjobs.values() for job_id in ids}),
        }
        _save_state(state)

    # ----------------------------
    # Removal
    # ----------------------------
    def _remove_om_callback_id(self, cb_id: int) -> None:
        _remove_om_callback(int(cb_id))
        for key, ids in list(self._om_callbacks.items()):
            self._om_callbacks[key] = [i for i in ids if int(i) != int(cb_id)]
            if not self._om_callbacks[key]:
                self._om_callbacks.pop(key, None)
        self._persist_state()

    def _remove_all(self) -> None:
        # Remove OpenMaya callbacks
        for cb_id in [cb_id for ids in self._om_callbacks.values() for cb_id in ids]:
            _remove_om_callback(int(cb_id))
        self._om_callbacks.clear()

        # Remove scriptJobs
        for job_id in [job_id for ids in self._scriptjobs.values() for job_id in ids]:
            _kill_scriptjob(int(job_id))
        self._scriptjobs.clear()

        for connections in self._signal_connections.values():
            for signal, handler in connections:
                try:
                    signal.disconnect(handler)
                except (RuntimeError, ValueError, TypeError, AttributeError, KeyError, IndexError):
                    pass
        self._signal_connections.clear()

        self._persist_state()

    def _safe_delete_widget(self, widget) -> None:
        _safe_delete_widget(widget)

    def _clear_managed_widgets(self) -> None:
        for key, widget in list(self._managed_widgets.items()):
            self._safe_delete_widget(widget)
        self._managed_widgets.clear()


def get_runtime_manager(start: bool = True) -> RuntimeManager:
    global _MANAGER
    if _MANAGER is not None and not QtCompat.isValid(_MANAGER):
        _MANAGER = None
    if _MANAGER is None:
        _MANAGER = RuntimeManager()
    if start:
        _MANAGER.start()
    return _MANAGER


def get_existing_runtime_manager() -> Optional[RuntimeManager]:
    global _MANAGER
    if _MANAGER is not None and not QtCompat.isValid(_MANAGER):
        _MANAGER = None
    return _MANAGER


def shutdown_runtime_manager(cleanup_widgets: bool = True) -> None:
    global _MANAGER
    if _MANAGER is not None:
        if QtCompat.isValid(_MANAGER):
            try:
                _MANAGER.shutdown(cleanup_widgets=cleanup_widgets)
            except (RuntimeError, ValueError, TypeError, AttributeError, KeyError, IndexError):
                pass
            try:
                _MANAGER.deleteLater()
            except (RuntimeError, ValueError, TypeError, AttributeError, KeyError, IndexError):
                pass
        _MANAGER = None
    cleanup_previous_runtime()
    cleanup_orphaned_callbacks()
    if cleanup_widgets:
        cleanup_orphaned_widgets()
