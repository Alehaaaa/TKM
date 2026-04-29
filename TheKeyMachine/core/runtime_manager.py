"""
Centralized Maya runtime manager for TheKeyMachine.

- Owns Maya callbacks (OpenMaya + scriptJobs) and guarantees cleanup on unload/reload.
- Emits Qt signals when runtime events fire so UI can subscribe without creating its own jobs.
- Tracks managed Qt widgets that should be cleaned up with their owner or on shutdown.
"""

from __future__ import annotations

import json
from typing import Any, Callable, Dict, List, Optional

from maya import cmds

try:
    from PySide6 import QtCore, QtWidgets  # type: ignore
except Exception:  # pragma: no cover
    from PySide2 import QtCore, QtWidgets  # type: ignore

try:
    from maya.api import OpenMaya as om  # type: ignore
except Exception:  # pragma: no cover
    om = None


_OPTIONVAR_NAME = "TKM_RuntimeManager"
_MANAGER: Optional["RuntimeManager"] = None
_ACTIVE_TOOL_SOURCE = None


def _load_state() -> Dict[str, Any]:
    try:
        if cmds.optionVar(exists=_OPTIONVAR_NAME):
            raw = cmds.optionVar(q=_OPTIONVAR_NAME)
            if isinstance(raw, str) and raw:
                return json.loads(raw)
    except Exception:
        pass
    return {"om": [], "scriptjob": []}


def _save_state(state: Dict[str, Any]) -> None:
    try:
        cmds.optionVar(sv=(_OPTIONVAR_NAME, json.dumps(state)))
    except Exception:
        pass


def _clear_state() -> None:
    try:
        if cmds.optionVar(exists=_OPTIONVAR_NAME):
            cmds.optionVar(remove=_OPTIONVAR_NAME)
    except Exception:
        pass


def cleanup_orphaned_callbacks() -> None:
    """
    Best-effort cleanup for callbacks that may have survived a python reload.
    Safe to call even if Maya APIs are partially unavailable.
    """
    state = _load_state()

    # OpenMaya callbacks
    if om:
        for cb_id in state.get("om", []) or []:
            try:
                om.MMessage.removeCallback(int(cb_id))
            except Exception:
                pass

    # scriptJobs
    for job_id in state.get("scriptjob", []) or []:
        try:
            cmds.scriptJob(kill=int(job_id), force=True)
        except Exception:
            pass

    _clear_state()


def _qt_modifiers_to_mask(modifiers) -> int:
    mask = 0
    try:
        if modifiers & QtCore.Qt.ShiftModifier:
            mask |= 1
        if modifiers & QtCore.Qt.ControlModifier:
            mask |= 4
        if modifiers & QtCore.Qt.AltModifier:
            mask |= 8
    except Exception:
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
    except Exception:
        pass

    try:
        return int(cmds.getModifiers())
    except Exception:
        return 0


def get_modifier_state() -> Dict[str, bool]:
    mask = get_modifier_mask()
    return {
        "ctrl": bool(mask & 4),
        "shift": bool(mask & 1),
        "alt": bool(mask & 8),
    }


def set_active_tool_source(widget) -> None:
    global _ACTIVE_TOOL_SOURCE
    _ACTIVE_TOOL_SOURCE = widget


def clear_active_tool_source(widget=None) -> None:
    global _ACTIVE_TOOL_SOURCE
    if widget is None or _ACTIVE_TOOL_SOURCE is widget:
        _ACTIVE_TOOL_SOURCE = None


def get_active_tool_source():
    return _ACTIVE_TOOL_SOURCE


class RuntimeManager(QtCore.QObject):
    callback_fired = QtCore.Signal(str)

    # Common / high-value signals
    scene_opened = QtCore.Signal()
    scene_new = QtCore.Signal()

    selection_changed = QtCore.Signal()
    time_changed = QtCore.Signal()
    undo_performed = QtCore.Signal()
    graph_editor_opened = QtCore.Signal()

    modifiers_changed = QtCore.Signal(bool, bool, bool)
    overshootChanged = QtCore.Signal(bool)
    eulerFilterChanged = QtCore.Signal(bool)

    def __init__(self, parent=None):
        super().__init__(parent=parent)
        self._started = False
        self._om_callbacks: Dict[str, List[int]] = {}
        self._scriptjobs: Dict[str, List[int]] = {}
        self._signal_connections: Dict[str, List[tuple]] = {}
        self._managed_widgets: Dict[str, QtWidgets.QWidget] = {}

        self._graph_editor_visible = False
        self._graph_editor_watch_enabled = False

        self._ui_watch_timer = QtCore.QTimer(self)
        self._ui_watch_timer.setSingleShot(True)
        self._ui_watch_timer.timeout.connect(self._check_graph_editor_state)

        self._modifier_watch_enabled = True
        self._ctrl_pressed = False
        self._shift_pressed = False
        self._alt_pressed = False

        self._event_filter_installed = False

    # ----------------------------
    # Lifecycle
    # ----------------------------
    def start(self) -> None:
        if self._started:
            return

        cleanup_orphaned_callbacks()

        # Built-in, long-lived callbacks while the tool is loaded.
        self._install_scene_callbacks()
        self._install_selection_callback()
        self._install_time_changed_callback()
        self._install_undo_callback()
        self._refresh_event_filter_state()

        self._started = True
        self._persist_state()

    def shutdown(self) -> None:
        self._remove_event_filter()
        self._clear_managed_widgets()
        self._remove_all()
        self._started = False
        _clear_state()

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
            if isinstance(event, (list, tuple)) and len(event) == 2:
                job_id = cmds.scriptJob(event=(event[0], _wrapped), runOnce=bool(run_once), killWithScene=bool(kill_with_scene))
            else:
                job_id = cmds.scriptJob(event=(event, _wrapped), runOnce=bool(run_once), killWithScene=bool(kill_with_scene))
        except Exception:
            return None

        self._track_scriptjob(key, int(job_id))
        return int(job_id)

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

        try:
            if isinstance(node, om.MObject):
                mobject = node
            else:
                selection_list = om.MSelectionList()
                selection_list.add(str(node))
                mobject = selection_list.getDependNode(0)
        except Exception:
            return None

        def _wrapped(*args):
            try:
                handler(*args)
            finally:
                self._emit(key)

        try:
            cb_id = om.MNodeMessage.addAttributeChangedCallback(mobject, _wrapped, client_data)
        except Exception:
            return None

        self._track_om(key, int(cb_id))
        return int(cb_id)

    def connect_signal(self, signal: Any, handler: Callable[..., Any], *, key: str, unique: bool = True) -> bool:
        if signal is None or handler is None:
            return False
        if unique:
            self.disconnect_callbacks(key)
        try:
            signal.connect(handler)
        except Exception:
            return False
        self._signal_connections.setdefault(key, []).append((signal, handler))
        return True

    def disconnect_callbacks(self, key: str) -> None:
        for cb_id in list(self._om_callbacks.get(key, []) or []):
            self._remove_om_callback_id(cb_id)

        for job_id in list(self._scriptjobs.get(key, []) or []):
            try:
                cmds.scriptJob(kill=int(job_id), force=True)
            except Exception:
                pass
        self._scriptjobs.pop(key, None)

        for signal, handler in self._signal_connections.pop(key, []) or []:
            try:
                signal.disconnect(handler)
            except Exception:
                pass

        self._persist_state()

    def register_managed_widget(self, widget, key: Optional[str] = None, owner=None):
        if widget is None:
            return None

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
        except Exception:
            pass

        if owner is not None and hasattr(owner, "destroyed"):
            try:
                owner.destroyed.connect(lambda *_: self._safe_delete_widget(widget))
            except Exception:
                pass

        return widget

    def clear_managed_widget(self, key: str) -> None:
        widget = self._managed_widgets.pop(key, None)
        self._safe_delete_widget(widget)

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
            except Exception:
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
            except Exception:
                pass

        cb_id = om.MEventMessage.addEventCallback("timeChanged", _on_time_changed)
        self._track_om("time_changed", int(cb_id))

    def _install_undo_callback(self) -> None:
        if not om:
            return

        def _on_undo(*_args):
            self._emit("undo_performed")
            try:
                self.undo_performed.emit()
            except Exception:
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
            except Exception:
                pass

        def _after_new(*_args):
            self._emit("scene_new")
            try:
                self.scene_new.emit()
            except Exception:
                pass

        cb_open = om.MSceneMessage.addCallback(om.MSceneMessage.kAfterOpen, _after_open)
        cb_new = om.MSceneMessage.addCallback(om.MSceneMessage.kAfterNew, _after_new)
        self._track_om("scene_opened", int(cb_open))
        self._track_om("scene_new", int(cb_new))

    def _install_event_filter(self) -> None:
        if self._event_filter_installed:
            return
        try:
            app = QtWidgets.QApplication.instance()
            if app:
                app.installEventFilter(self)
                self._event_filter_installed = True
        except Exception:
            pass
        self._sync_enabled_ui_watchers()

    def _remove_event_filter(self) -> None:
        if not self._event_filter_installed:
            return
        try:
            app = QtWidgets.QApplication.instance()
            if app:
                app.removeEventFilter(self)
        except Exception:
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
        return bool(self._graph_editor_watch_enabled or self._modifier_watch_enabled)

    def _sync_enabled_ui_watchers(self) -> None:
        if self._graph_editor_watch_enabled:
            self._schedule_graph_editor_check()
        if self._modifier_watch_enabled:
            self._sync_modifier_state()

    def _reset_graph_editor_watch(self) -> None:
        self._graph_editor_visible = False
        try:
            self._ui_watch_timer.stop()
        except Exception:
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
        except Exception:
            pass

    def _sync_modifier_state(self, modifiers=None) -> None:
        if not self._modifier_watch_enabled:
            return
        try:
            if modifiers is None:
                app = QtWidgets.QApplication.instance()
                modifiers = app.keyboardModifiers() if app else QtCore.Qt.NoModifier
        except Exception:
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
        except Exception:
            visible = False

        if visible == self._graph_editor_visible:
            return

        self._graph_editor_visible = visible
        try:
            if visible:
                QtCore.QTimer.singleShot(0, self._emit_graph_editor_opened)
        except Exception:
            pass

    def _emit_graph_editor_opened(self) -> None:
        try:
            if not self._graph_editor_visible:
                return
            self._emit("graph_editor_opened")
            self.graph_editor_opened.emit()
        except Exception:
            pass

    def eventFilter(self, obj, event):
        try:
            event_type = event.type()
        except Exception:
            return False
        self._handle_modifier_event(event_type, event)
        self._handle_graph_editor_event(obj, event_type)
        return False

    def _handle_modifier_event(self, event_type, event) -> None:
        if not self._modifier_watch_enabled:
            return
        if event_type in {QtCore.QEvent.KeyPress, QtCore.QEvent.KeyRelease, QtCore.QEvent.ShortcutOverride}:
            try:
                self._sync_modifier_state(event.modifiers())
            except Exception:
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
        except Exception:
            object_name = ""

        try:
            window_title = obj.windowTitle() or ""
        except Exception:
            window_title = ""

        return "graphEditor1" in object_name or "Graph Editor" in window_title

    # ----------------------------
    # Emit + tracking
    # ----------------------------
    def _emit(self, key: str) -> None:
        try:
            self.callback_fired.emit(key)
        except Exception:
            pass

    def _track_om(self, key: str, cb_id: int) -> None:
        self._om_callbacks.setdefault(key, []).append(int(cb_id))
        self._persist_state()

    def _track_scriptjob(self, key: str, job_id: int) -> None:
        self._scriptjobs.setdefault(key, []).append(int(job_id))
        self._persist_state()

    def _persist_state(self) -> None:
        state = {
            "om": sorted({cb_id for ids in self._om_callbacks.values() for cb_id in ids}),
            "scriptjob": sorted({job_id for ids in self._scriptjobs.values() for job_id in ids}),
        }
        _save_state(state)

    # ----------------------------
    # Removal
    # ----------------------------
    def _remove_om_callback_id(self, cb_id: int) -> None:
        if not om:
            return
        try:
            om.MMessage.removeCallback(int(cb_id))
        except Exception:
            pass
        for key, ids in list(self._om_callbacks.items()):
            self._om_callbacks[key] = [i for i in ids if int(i) != int(cb_id)]
            if not self._om_callbacks[key]:
                self._om_callbacks.pop(key, None)
        self._persist_state()

    def _remove_all(self) -> None:
        # Remove OpenMaya callbacks
        if om:
            for cb_id in [cb_id for ids in self._om_callbacks.values() for cb_id in ids]:
                try:
                    om.MMessage.removeCallback(int(cb_id))
                except Exception:
                    pass
        self._om_callbacks.clear()

        # Remove scriptJobs
        for job_id in [job_id for ids in self._scriptjobs.values() for job_id in ids]:
            try:
                cmds.scriptJob(kill=int(job_id), force=True)
            except Exception:
                pass
        self._scriptjobs.clear()

        for connections in self._signal_connections.values():
            for signal, handler in connections:
                try:
                    signal.disconnect(handler)
                except Exception:
                    pass
        self._signal_connections.clear()

        self._persist_state()

    def _safe_delete_widget(self, widget) -> None:
        if widget is None:
            return
        try:
            widget.hide()
        except Exception:
            pass
        try:
            widget.setParent(None)
        except Exception:
            pass
        try:
            widget.deleteLater()
        except Exception:
            pass

    def _clear_managed_widgets(self) -> None:
        for key, widget in list(self._managed_widgets.items()):
            self._safe_delete_widget(widget)
        self._managed_widgets.clear()


def get_runtime_manager(start: bool = True) -> RuntimeManager:
    global _MANAGER
    if _MANAGER is None:
        _MANAGER = RuntimeManager()
    if start:
        _MANAGER.start()
    return _MANAGER


def shutdown_runtime_manager() -> None:
    global _MANAGER
    if _MANAGER is not None:
        try:
            _MANAGER.shutdown()
        except Exception:
            pass
        try:
            _MANAGER.deleteLater()
        except Exception:
            pass
        _MANAGER = None
