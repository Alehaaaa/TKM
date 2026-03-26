"""
Centralized Maya callback manager for TheKeyMachine.

- Owns Maya callbacks (OpenMaya + scriptJobs) and guarantees cleanup on unload/reload.
- Emits Qt signals when callbacks fire so UI can subscribe without creating its own jobs.
"""

from __future__ import annotations

import json
from typing import Any, Callable, Dict, List, Optional

from maya import cmds

try:
    from PySide6 import QtCore  # type: ignore
except Exception:  # pragma: no cover
    from PySide2 import QtCore  # type: ignore

try:
    from maya.api import OpenMaya as om  # type: ignore
except Exception:  # pragma: no cover
    om = None


_OPTIONVAR_NAME = "TKM_CallbackManager"
_MANAGER: Optional["CallbackManager"] = None


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


class CallbackManager(QtCore.QObject):
    callback_fired = QtCore.Signal(str)

    # Common / high-value signals
    selection_changed = QtCore.Signal()
    scene_opened = QtCore.Signal()
    scene_new = QtCore.Signal()

    def __init__(self, parent=None):
        super().__init__(parent=parent)
        self._started = False
        self._om_callbacks: Dict[str, List[int]] = {}
        self._scriptjobs: Dict[str, List[int]] = {}

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

        self._started = True
        self._persist_state()

    def shutdown(self) -> None:
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

        self._persist_state()


def get_callback_manager(start: bool = True) -> CallbackManager:
    global _MANAGER
    if _MANAGER is None:
        _MANAGER = CallbackManager()
    if start:
        _MANAGER.start()
    return _MANAGER


def shutdown_callback_manager() -> None:
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
    else:
        cleanup_orphaned_callbacks()
