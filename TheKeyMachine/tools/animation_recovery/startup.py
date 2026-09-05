"""Callback-recorded launch recovery; uses the existing recovery window."""
from datetime import datetime
import os
import time

from maya import cmds
from maya import OpenMaya as file_api

from TheKeyMachine.core import trigger
from TheKeyMachine.core.Qt import QtCore
from TheKeyMachine.tools.animation_recovery import storage


def record_crash_save(controller):
    """Called only by kBeforeSave; never searches for files."""
    path = str(file_api.MFileIO.beforeSaveFilename())
    if "[Recovered-" not in os.path.basename(path) or not path.endswith("].ma"):
        return False
    timestamp = time.time()
    storage.update_recovery_state(controller.recovery_root(), event={
        "kind": "crash", "path": path, "scene_id": controller.current_scene_id(),
        "timestamp": timestamp, "token": "{}:{}".format(path, time.time_ns()),
    })
    return True


def dismiss_candidates(controller, tokens):
    if tokens:
        storage.update_recovery_state(controller.recovery_root(), dismissed=tokens)


def launch_candidates(controller):
    """Validate the single latest tracked event on the disk worker."""
    state = storage.recovery_state(controller.recovery_root())
    event = state.get("latest") or {}
    path = event.get("path")
    if not path or not os.path.isfile(path) or event.get("token") in state.get("dismissed", []):
        return None, None
    if event.get("kind") == "crash":
        return None, event
    if event.get("kind") != "animation" or not controller._recovery_scene_id(path):
        return None, None
    meta = storage.read_manifest(path)["meta"]
    source = os.path.join(meta.get("location") or "", meta.get("source_file") or "")
    if not os.path.isfile(source) or event["timestamp"] <= os.path.getmtime(source):
        return None, None
    valid = controller._newest_valid_recovery(
        controller._recovery_paths(controller._recovery_scene_id(path)))
    if not valid or controller._filename_timestamp_value(valid) <= os.path.getmtime(source):
        return None, None
    return valid, None


def show_recovery(controller, checkpoint=None, crash=None, reopen_scene=False):
    """One automatic-offer path for launch and already-open scenes."""
    tokens = [checkpoint] if checkpoint else []
    if crash:
        tokens.append(crash["token"])
    dismissed = storage.recovery_state(controller.recovery_root()).get("dismissed", [])
    if not tokens or all(token in dismissed for token in tokens):
        return
    from TheKeyMachine.tools.animation_recovery import widgets
    entries = []
    selected = checkpoint
    scene_id = controller._recovery_scene_id(checkpoint) if checkpoint else None
    if crash:
        selected = crash["path"]
        scene_id = crash.get("scene_id")
        entries.append({"path": selected, "created": datetime.fromtimestamp(crash["timestamp"]),
                        "reason": "crash", "status": "green", "change": "Crash Save",
                        "source_file": os.path.basename(selected), "location": os.path.dirname(selected)})
    controller.get_service()._last_prompted_checkpoint = selected
    widgets.show_dialog(scene_id=scene_id, selected_path=selected, startup=reopen_scene,
                        extra_entries=entries, dismissal_tokens=tokens)


def show_launch(controller, candidates):
    checkpoint, crash = candidates
    show_recovery(controller, checkpoint, crash, reopen_scene=True)


def load_selected(controller, path, crash=False):
    """Apply to the owning open scene; open a source file only for another scene."""
    if crash:
        if cmds.file(query=True, modified=True):
            cmds.warning("Save the current scene before opening a recovery scene.")
            return False
        cmds.file(path, open=True)
        return True
    scene_id = controller._recovery_scene_id(path)
    if not scene_id:
        raise ValueError("Checkpoint is outside the recovery folder")
    if controller.current_scene_id() == scene_id:
        # Also handles untitled scenes and checkpoints captured before Save As.
        # No file replacement is needed, so unsaved edits do not block recovery.
        cmds.select(clear=True)
        return trigger.execute_command("animation_recovery_restore", path)
    meta = storage.read_manifest(path)["meta"]
    source = os.path.join(meta.get("location") or "", meta.get("source_file") or "")
    if not source:
        # The scene may have acquired a filename after this checkpoint.
        for checkpoint in reversed(controller._recovery_paths(scene_id)):
            details = storage.read_manifest(checkpoint)["meta"]
            candidate = os.path.join(details.get("location") or "", details.get("source_file") or "")
            if os.path.isfile(candidate):
                source = candidate
                break
    if not source:
        return trigger.execute_command("animation_recovery_restore", path)
    if not os.path.isfile(source):
        raise ValueError("The recovery source scene is missing: " + source)
    if cmds.file(query=True, modified=True):
        cmds.warning("Save the current scene before opening a recovery scene.")
        return False
    service = controller.get_service()
    if service is None:
        raise RuntimeError("Animation Recovery is not running")
    with service.restoring():
        cmds.file(source, open=True)
        if controller.current_scene_id() != scene_id:
            if service._opened_scene_had_id:
                raise ValueError("The source scene has a different recovery identity")
            plug = "{}.{}".format(controller._scene_node(), controller.SCENE_ID_ATTRIBUTE)
            cmds.setAttr(plug, lock=False)
            try:
                cmds.setAttr(plug, scene_id, type="string")
            finally:
                cmds.setAttr(plug, lock=True)
            service.scene_id = scene_id
            service._initialize_history_state()
        service._last_prompted_checkpoint = path
        cmds.select(clear=True)
        return trigger.execute_command("animation_recovery_restore", path)


class _LaunchRead(QtCore.QRunnable):
    def __init__(self, controller, signals):
        super().__init__()
        self.controller, self.signals = controller, signals

    def run(self):
        try:
            result = launch_candidates(self.controller)
        except Exception:
            result = None
        self.signals.emit(result)


def begin_launch_read(controller, service):
    if cmds.about(batch=True):
        service._finish_launch_recovery(None)
        return
    service._thread_pool.start(_LaunchRead(controller, service.launchReady))
