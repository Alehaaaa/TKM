"""TKM Menu behavior boundary."""

import os

from maya import cmds


def _save_scene_as():
    scene_name = cmds.file(query=True, sceneName=True) or ""
    current_type = cmds.file(query=True, type=True) or []
    current_type = current_type[0] if isinstance(current_type, (list, tuple)) and current_type else current_type
    default_filter = "Maya Binary (*.mb)" if current_type == "mayaBinary" else "Maya ASCII (*.ma)"
    result = cmds.fileDialog2(
        fileMode=0,
        caption="Save Scene As Before Reloading TheKeyMachine",
        fileFilter="Maya ASCII (*.ma);;Maya Binary (*.mb)",
        selectFileFilter=default_filter,
        returnFilter=True,
    )
    if not result:
        return False

    target_path = result[0]
    selected_filter = result[1] if len(result) > 1 else default_filter
    extension = os.path.splitext(target_path)[1].lower()
    if extension not in (".ma", ".mb"):
        extension = ".mb" if "Binary" in selected_filter else ".ma"
        target_path += extension
    file_type = "mayaBinary" if extension == ".mb" else "mayaAscii"

    try:
        cmds.file(rename=target_path)
        cmds.file(save=True, force=True, type=file_type)
    except (RuntimeError, ValueError, TypeError) as error:
        if scene_name:
            try:
                cmds.file(rename=scene_name)
            except (RuntimeError, ValueError, TypeError):
                pass
        cmds.warning("Scene could not be saved; TheKeyMachine was not reloaded: {}".format(error))
        return False
    return True


def _save_scene():
    if not (cmds.file(query=True, sceneName=True) or ""):
        return _save_scene_as()
    try:
        cmds.file(save=True, force=True)
    except (RuntimeError, ValueError, TypeError) as error:
        cmds.warning("Scene could not be saved; TheKeyMachine was not reloaded: {}".format(error))
        return False
    return True


def reload_toolbar_with_scene_prompt(anchor_widget=None):
    import TheKeyMachine
    from TheKeyMachine.tools.tkm_menu import widgets

    choice = widgets.show_reload_scene_prompt(anchor_widget=anchor_widget)
    if choice == "save":
        if not _save_scene():
            return False
    elif choice == "save_as":
        if not _save_scene_as():
            return False
    elif choice != "skip":
        return False
    return TheKeyMachine.reload()
