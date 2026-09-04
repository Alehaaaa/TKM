"""Callback-recorded launch recovery; uses the existing recovery window."""
from datetime import datetime
import json
import os

from maya import cmds
from maya import OpenMaya as file_api

from TheKeyMachine.core import trigger
from TheKeyMachine.core.Qt import QtCore
from TheKeyMachine.tools.animation_recovery import storage


def _read_record(root, name):
    try:
        with open(os.path.join(root, name), "rb") as stream:
            return json.load(stream)
    except (OSError, ValueError):
        return {}


def record_crash_save(controller):
    """Called synchronously from kBeforeSave, while the save filename is valid."""
    path = str(file_api.MFileIO.beforeSaveFilename())
    name = os.path.basename(path)
    if "[Recovered-" not in name or not name.endswith("].ma"):
        return False
    record = {"path": path, "scene_id": controller.current_scene_id()}
    storage.atomic_write(os.path.join(controller.recovery_root(), "crash-save.json"),
                         json.dumps(record).encode("utf-8"))
    return True


def launch_candidates(controller):
    """Read exact recorded paths only. Called on the disk worker."""
    root = controller.recovery_root()
    crash = _read_record(root, "crash-save.json")
    crash_path = crash.get("path")
    if not crash_path or not os.path.isfile(crash_path):
        crash = None
    latest = _read_record(root, "last-checkpoint.json")
    path = latest.get("path")
    candidate = None
    if path and controller._recovery_scene_id(path):
        try:
            meta = storage.read_manifest(path)["meta"]
            source = os.path.join(meta.get("location") or "", meta.get("source_file") or "")
            if os.path.isfile(source) and controller._filename_timestamp_value(path) > os.path.getmtime(source):
                valid = controller._newest_valid_recovery(
                    controller._recovery_paths(controller._recovery_scene_id(path)))
                if valid and controller._filename_timestamp_value(valid) > os.path.getmtime(source):
                    candidate = valid
        except (OSError, ValueError, KeyError):
            pass
    return candidate, crash


def show_launch(controller, candidates):
    checkpoint, crash = candidates
    if not checkpoint and not crash:
        return
    from TheKeyMachine.tools.animation_recovery import widgets
    entries = []
    if crash:
        path = crash["path"]
        entries.append({"path": path, "created": datetime.fromtimestamp(os.path.getmtime(path)),
                        "reason": "crash", "status": "green", "change": "Crash Save",
                        "source_file": os.path.basename(path), "location": os.path.dirname(path)})
    scene_id = controller._recovery_scene_id(checkpoint) if checkpoint else crash.get("scene_id")
    selected = checkpoint
    if crash and (not checkpoint or os.path.getmtime(crash["path"]) > controller._filename_timestamp_value(checkpoint)):
        selected = crash["path"]
    controller.get_service()._last_prompted_checkpoint = checkpoint
    widgets.show_dialog(scene_id=scene_id, selected_path=selected, startup=True, extra_entries=entries)


def load_selected(controller, path, crash=False):
    """The existing Recover button opens the source, then applies all animation."""
    if cmds.file(query=True, modified=True):
        # Reuse the existing window; leave unsaved work available to save.
        cmds.warning("Save the current scene before opening a recovery scene.")
        return False
    if crash:
        cmds.file(path, open=True)
        return True
    meta = storage.read_manifest(path)["meta"]
    source = os.path.join(meta.get("location") or "", meta.get("source_file") or "")
    if not os.path.isfile(source):
        raise ValueError("The recovery source scene is missing: " + source)
    scene_id = controller._recovery_scene_id(path)
    if not scene_id:
        raise ValueError("Checkpoint is outside the recovery folder")
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
