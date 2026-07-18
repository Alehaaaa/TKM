"""Smart rotation and translation manipulator behavior."""

from maya import cmds, mel


def smart_rotation(*_args):
    current_context = cmds.currentCtx()
    mel.eval("buildRotateMM")
    if current_context != "RotateSuperContext":
        return
    current_mode = cmds.manipRotateContext("Rotate", query=True, mode=True)
    cmds.manipRotateContext("Rotate", edit=True, mode=(current_mode + 1) % 3)


def smart_rotation_release(*_args):
    mel.eval("destroySTRSMarkingMenu RotateTool")


def smart_translation(*_args):
    current_context = cmds.currentCtx()
    mel.eval("buildTranslateMM")
    if current_context != "moveSuperContext":
        return
    current_mode = cmds.manipMoveContext("Move", query=True, mode=True)
    cmds.manipMoveContext("Move", edit=True, mode=2 if current_mode == 0 else 0)


def smart_translation_release(*_args):
    mel.eval("destroySTRSMarkingMenu MoveTool")
